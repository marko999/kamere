"""Tests for src.trend.compute_trend."""

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

# We test compute_trend directly (not via the package import) to avoid
# pulling in config/cameras which aren't needed for unit tests.
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.trend import compute_trend


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def conn():
    """In-memory SQLite database with the readings schema."""
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE readings (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            crossing_id         TEXT NOT NULL,
            camera_id           TEXT NOT NULL,
            timestamp           TEXT NOT NULL,
            car_count           INTEGER,
            truck_count         INTEGER,
            bus_count           INTEGER,
            motorcycle_count    INTEGER,
            person_count        INTEGER,
            active_lanes        INTEGER,
            weather             TEXT,
            queue_length_m      REAL,
            congestion_trend    TEXT,
            anomalies           TEXT,
            estimated_wait_min  REAL,
            raw_json            TEXT
        );
    """)
    return db


def _insert(conn, crossing_id, minutes_ago, wait_min, raw_json=None):
    """Insert a reading at *minutes_ago* before now with the given wait time."""
    ts = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    raw = json.dumps(raw_json) if raw_json else None
    conn.execute(
        """INSERT INTO readings
           (crossing_id, camera_id, timestamp, estimated_wait_min, raw_json)
           VALUES (?, ?, ?, ?, ?)""",
        (crossing_id, "cam_1", ts, wait_min, raw),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestUnknownTrend:
    """When there is insufficient data, trend should be 'unknown'."""

    def test_no_readings(self, conn):
        result = compute_trend(conn, "batrovci")
        assert result["trend"] == "unknown"
        assert result["trend_arrow"] == "\u2014"
        assert result["growth_rate_min_per_h"] is None
        assert result["current_wait"] is None

    def test_one_reading(self, conn):
        _insert(conn, "batrovci", 5, 10.0)
        result = compute_trend(conn, "batrovci")
        assert result["trend"] == "unknown"
        # current_wait should still be reported from the latest reading
        assert result["current_wait"] == 10.0

    def test_two_readings(self, conn):
        _insert(conn, "batrovci", 10, 8.0)
        _insert(conn, "batrovci", 5, 12.0)
        result = compute_trend(conn, "batrovci")
        assert result["trend"] == "unknown"

    def test_zero_wait_excluded(self, conn):
        """Readings with estimated_wait_min <= 0 are excluded from trend."""
        _insert(conn, "batrovci", 20, 0)
        _insert(conn, "batrovci", 15, 0)
        _insert(conn, "batrovci", 10, 0)
        _insert(conn, "batrovci", 5, 0)
        result = compute_trend(conn, "batrovci")
        assert result["trend"] == "unknown"


class TestGrowingTrend:
    """When wait times are increasing, trend should be 'growing'."""

    def test_clearly_growing(self, conn):
        # First half: ~10 min, second half: ~20 min over 20 minutes
        _insert(conn, "batrovci", 25, 8.0)
        _insert(conn, "batrovci", 20, 10.0)
        _insert(conn, "batrovci", 15, 12.0)
        _insert(conn, "batrovci", 10, 18.0)
        _insert(conn, "batrovci", 5, 20.0)
        _insert(conn, "batrovci", 2, 22.0)

        result = compute_trend(conn, "batrovci")
        assert result["trend"] == "growing"
        assert result["trend_arrow"] == "\u2191"
        assert result["growth_rate_min_per_h"] is not None
        assert result["growth_rate_min_per_h"] > 1.0
        assert result["current_wait"] == 22.0


class TestShrinkingTrend:
    """When wait times are decreasing, trend should be 'shrinking'."""

    def test_clearly_shrinking(self, conn):
        _insert(conn, "batrovci", 25, 30.0)
        _insert(conn, "batrovci", 20, 28.0)
        _insert(conn, "batrovci", 15, 25.0)
        _insert(conn, "batrovci", 10, 15.0)
        _insert(conn, "batrovci", 5, 10.0)
        _insert(conn, "batrovci", 2, 8.0)

        result = compute_trend(conn, "batrovci")
        assert result["trend"] == "shrinking"
        assert result["trend_arrow"] == "\u2193"
        assert result["growth_rate_min_per_h"] is not None
        assert result["growth_rate_min_per_h"] < -1.0


class TestStableTrend:
    """When wait times are roughly constant, trend should be 'stable'."""

    def test_flat_readings(self, conn):
        # All around 15 min, small noise
        _insert(conn, "batrovci", 25, 15.0)
        _insert(conn, "batrovci", 20, 15.1)
        _insert(conn, "batrovci", 15, 14.9)
        _insert(conn, "batrovci", 10, 15.2)
        _insert(conn, "batrovci", 5, 14.8)
        _insert(conn, "batrovci", 2, 15.0)

        result = compute_trend(conn, "batrovci")
        assert result["trend"] == "stable"
        assert result["trend_arrow"] == "\u2192"
        assert result["growth_rate_min_per_h"] is not None
        assert abs(result["growth_rate_min_per_h"]) <= 1.0


class TestInflowRate:
    """Test queue_inflow_rate computation from raw_json."""

    def test_inflow_rate_computed(self, conn):
        _insert(conn, "horgos", 20, 10.0, {"vehicles_entered": 5, "vehicles_exited": 3})
        _insert(conn, "horgos", 15, 12.0, {"vehicles_entered": 6, "vehicles_exited": 3})
        _insert(conn, "horgos", 10, 14.0, {"vehicles_entered": 7, "vehicles_exited": 4})
        _insert(conn, "horgos", 5, 16.0, {"vehicles_entered": 8, "vehicles_exited": 4})

        result = compute_trend(conn, "horgos")
        assert result["queue_inflow_rate"] is not None
        # Net = (5+6+7+8) - (3+3+4+4) = 26 - 14 = 12 over 15 min = 0.8/min
        assert abs(result["queue_inflow_rate"] - 0.8) < 0.05

    def test_no_inflow_data(self, conn):
        _insert(conn, "horgos", 20, 10.0)
        _insert(conn, "horgos", 15, 12.0)
        _insert(conn, "horgos", 10, 14.0)
        _insert(conn, "horgos", 5, 16.0)

        result = compute_trend(conn, "horgos")
        assert result["queue_inflow_rate"] is None


class TestWindowFiltering:
    """Readings outside the window should not be included."""

    def test_old_readings_excluded(self, conn):
        # These are outside the 30-min window
        _insert(conn, "batrovci", 60, 30.0)
        _insert(conn, "batrovci", 55, 28.0)
        _insert(conn, "batrovci", 50, 25.0)
        _insert(conn, "batrovci", 45, 20.0)

        # Only 2 within the window — not enough
        _insert(conn, "batrovci", 10, 5.0)
        _insert(conn, "batrovci", 5, 6.0)

        result = compute_trend(conn, "batrovci")
        assert result["trend"] == "unknown"

    def test_custom_window(self, conn):
        # Use a 60-min window to capture older readings
        _insert(conn, "batrovci", 55, 5.0)
        _insert(conn, "batrovci", 45, 7.0)
        _insert(conn, "batrovci", 35, 10.0)
        _insert(conn, "batrovci", 25, 15.0)
        _insert(conn, "batrovci", 15, 20.0)
        _insert(conn, "batrovci", 5, 25.0)

        result = compute_trend(conn, "batrovci", window_minutes=60)
        assert result["trend"] == "growing"


class TestCrossingIsolation:
    """Readings from different crossings should not mix."""

    def test_different_crossings(self, conn):
        # batrovci has growing data
        _insert(conn, "batrovci", 25, 5.0)
        _insert(conn, "batrovci", 20, 8.0)
        _insert(conn, "batrovci", 15, 12.0)
        _insert(conn, "batrovci", 10, 18.0)
        _insert(conn, "batrovci", 5, 22.0)
        _insert(conn, "batrovci", 2, 25.0)

        # horgos has shrinking data
        _insert(conn, "horgos", 25, 30.0)
        _insert(conn, "horgos", 20, 25.0)
        _insert(conn, "horgos", 15, 20.0)
        _insert(conn, "horgos", 10, 12.0)
        _insert(conn, "horgos", 5, 8.0)
        _insert(conn, "horgos", 2, 5.0)

        batrovci = compute_trend(conn, "batrovci")
        horgos = compute_trend(conn, "horgos")

        assert batrovci["trend"] == "growing"
        assert horgos["trend"] == "shrinking"
