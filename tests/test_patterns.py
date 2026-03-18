"""Tests for peak hours pattern analysis."""

import sqlite3
from datetime import datetime, timedelta, timezone

from src.patterns import get_hourly_pattern, get_peak_summaries


_READINGS_SCHEMA = """
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
    )
"""


def _create_test_db():
    """Create an in-memory DB with the readings schema and simulated data.

    Simulates hourly data with:
    - Low wait times at night (hours 0-5): ~2 min
    - Medium wait times morning/evening (hours 6-9, 17-23): ~8 min
    - High wait times midday (hours 10-16): ~25 min

    This ensures peak hours fall midday and quiet hours fall at night.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(_READINGS_SCHEMA)

    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Insert readings for 7 days, every hour, for crossing "batrovci"
    for day_offset in range(7):
        base_day = today - timedelta(days=day_offset)
        for hour in range(24):
            # Determine wait time based on hour (the UTC hour stored in timestamp)
            if 0 <= hour <= 5:
                wait = 2.0 + (hour * 0.3)  # ~2-3.5 min (night, quiet)
            elif 10 <= hour <= 16:
                wait = 20.0 + (hour - 10) * 1.5  # ~20-29 min (midday, peak)
            else:
                wait = 7.0 + (hour % 5)  # ~7-11 min (medium)

            ts = base_day.replace(hour=hour, minute=30).isoformat()
            conn.execute(
                """INSERT INTO readings
                   (crossing_id, camera_id, timestamp, car_count, estimated_wait_min)
                   VALUES (?, ?, ?, ?, ?)""",
                ("batrovci", "batrovci_1", ts, hour + 5, wait),
            )

    conn.commit()
    return conn


def test_peak_hours_are_midday():
    """Peak hours should include midday hours (10-16) where wait is highest."""
    conn = _create_test_db()
    result = get_hourly_pattern(conn, "batrovci", days=7)

    assert result["peak_hours"], "Expected peak hours but got none"
    # All peak hours should be in the 10-16 range
    for h in result["peak_hours"]:
        assert 10 <= h <= 16, f"Peak hour {h} is outside expected midday range 10-16"
    # Busiest hour should be in midday
    assert 10 <= result["busiest_hour"] <= 16
    conn.close()


def test_quiet_hours_are_night():
    """Quiet hours should include night hours (0-5) where wait is lowest."""
    conn = _create_test_db()
    result = get_hourly_pattern(conn, "batrovci", days=7)

    assert result["quiet_hours"], "Expected quiet hours but got none"
    # All quiet hours should be in the 0-5 range
    for h in result["quiet_hours"]:
        assert 0 <= h <= 5, f"Quiet hour {h} is outside expected night range 0-5"
    # Quietest hour should be at night
    assert 0 <= result["quietest_hour"] <= 5
    conn.close()


def test_no_data_returns_minimal():
    """With no readings, should return minimal response with empty peak_hours."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(_READINGS_SCHEMA)

    result = get_hourly_pattern(conn, "nonexistent", days=7)

    assert result["peak_hours"] == []
    assert result["quiet_hours"] == []
    assert result["peak_description"] is None
    assert result["busiest_hour"] is None
    assert result["total_readings"] == 0
    conn.close()


def test_avg_peak_higher_than_quiet():
    """Average wait during peak hours should be higher than during quiet hours."""
    conn = _create_test_db()
    result = get_hourly_pattern(conn, "batrovci", days=7)

    assert result["avg_peak_wait"] is not None, "Expected avg_peak_wait"
    assert result["avg_quiet_wait"] is not None, "Expected avg_quiet_wait"
    assert result["avg_peak_wait"] > result["avg_quiet_wait"], (
        f"Peak avg ({result['avg_peak_wait']}) should be > quiet avg ({result['avg_quiet_wait']})"
    )
    conn.close()


def test_peak_description_format():
    """Peak description should be a formatted hour range string."""
    conn = _create_test_db()
    result = get_hourly_pattern(conn, "batrovci", days=7)

    desc = result["peak_description"]
    assert desc is not None
    # Should contain time-like format (HH:00)
    assert ":00" in desc
    assert " - " in desc
    conn.close()


def test_get_peak_summaries():
    """get_peak_summaries should return a dict mapping crossing_id -> description."""
    conn = _create_test_db()
    summaries = get_peak_summaries(conn, days=7)

    assert "batrovci" in summaries
    assert summaries["batrovci"] is not None
    assert ":00" in summaries["batrovci"]
    conn.close()


def test_insufficient_data_returns_minimal():
    """With fewer than 100 readings, should return minimal response."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(_READINGS_SCHEMA)

    # Insert only 50 readings (below the 100 threshold)
    now = datetime.now(timezone.utc)
    for i in range(50):
        ts = (now - timedelta(minutes=i * 30)).isoformat()
        conn.execute(
            """INSERT INTO readings
               (crossing_id, camera_id, timestamp, car_count, estimated_wait_min)
               VALUES (?, ?, ?, ?, ?)""",
            ("test_crossing", "cam_1", ts, 5, 10.0),
        )
    conn.commit()

    result = get_hourly_pattern(conn, "test_crossing", days=7)
    assert result["peak_hours"] == []
    assert result["peak_description"] is None
    assert result["total_readings"] == 50
    conn.close()
