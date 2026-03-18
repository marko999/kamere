"""Tests for the GPS simulator module."""

import sqlite3
from datetime import datetime, timedelta, timezone

from src.simulator import CROSSING_COORDS, haversine_km, simulate


def _make_db():
    """Create an in-memory DB with the readings table and seed crossings."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE crossings (
            id              TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            country_border  TEXT
        );
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
        """
    )
    # Seed a couple of crossings
    conn.execute(
        "INSERT INTO crossings (id, name, country_border) VALUES (?, ?, ?)",
        ("batrovci", "Batrovci", "SRB-HRV"),
    )
    conn.execute(
        "INSERT INTO crossings (id, name, country_border) VALUES (?, ?, ?)",
        ("horgos", "Horgos", "SRB-HUN"),
    )
    conn.commit()
    return conn


def _insert_reading(conn, crossing_id, wait_min, minutes_ago=0, weather="clear"):
    ts = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    conn.execute(
        "INSERT INTO readings (crossing_id, camera_id, timestamp, car_count, truck_count, bus_count, weather, estimated_wait_min) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (crossing_id, crossing_id + "_1", ts, 5, 2, 0, weather, wait_min),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_haversine_belgrade_to_batrovci():
    """Belgrade (44.8176, 20.4633) to Batrovci (45.0536, 19.1042) ~120km."""
    d = haversine_km(44.8176, 20.4633, 45.0536, 19.1042)
    assert 100 <= d <= 140, f"Expected ~120 km, got {d:.1f} km"


def test_haversine_same_point():
    d = haversine_km(44.0, 20.0, 44.0, 20.0)
    assert d == 0.0


def test_simulate_returns_sorted_results():
    conn = _make_db()
    _insert_reading(conn, "batrovci", 30.0, minutes_ago=1)
    _insert_reading(conn, "horgos", 5.0, minutes_ago=1)

    # User is in Belgrade
    results = simulate(conn, 44.8176, 20.4633, speed_kmh=100)
    assert len(results) == len(CROSSING_COORDS)

    # Should be sorted by total_time_min ascending
    for i in range(len(results) - 1):
        assert results[i]["total_time_min"] <= results[i + 1]["total_time_min"], (
            f"Results not sorted: index {i} ({results[i]['total_time_min']}) > index {i+1} ({results[i+1]['total_time_min']})"
        )


def test_predicted_wait_not_negative():
    conn = _make_db()
    # Insert a shrinking trend: earlier was 40 min, now is 5 min
    _insert_reading(conn, "batrovci", 40.0, minutes_ago=25)
    _insert_reading(conn, "batrovci", 35.0, minutes_ago=20)
    _insert_reading(conn, "batrovci", 10.0, minutes_ago=10)
    _insert_reading(conn, "batrovci", 5.0, minutes_ago=1)

    results = simulate(conn, 44.8176, 20.4633, speed_kmh=100)

    for r in results:
        assert r["predicted_wait_min"] >= 0, (
            f"Negative predicted wait for {r['crossing_id']}: {r['predicted_wait_min']}"
        )


def test_crossing_coords_valid():
    """All crossing coordinates must be in Balkans range."""
    for cid, (lat, lon) in CROSSING_COORDS.items():
        assert 42 <= lat <= 47, f"{cid}: latitude {lat} out of Balkans range (42-47)"
        assert 14 <= lon <= 23, f"{cid}: longitude {lon} out of Balkans range (14-23)"


def test_simulate_empty_db():
    """Simulate works with no readings at all (zero wait times)."""
    conn = _make_db()
    results = simulate(conn, 44.8176, 20.4633, speed_kmh=100)
    assert len(results) == len(CROSSING_COORDS)
    for r in results:
        assert r["current_wait_min"] == 0.0
        assert r["predicted_wait_min"] == 0.0


def test_simulate_result_fields():
    """Each result dict must contain all expected keys."""
    conn = _make_db()
    _insert_reading(conn, "batrovci", 15.0)

    results = simulate(conn, 44.8176, 20.4633, speed_kmh=100)
    expected_keys = {
        "crossing_id", "crossing_name", "country_border",
        "distance_km", "eta_minutes", "current_wait_min",
        "predicted_wait_min", "total_time_min", "growth_rate_min_per_h",
        "current_weather", "current_vehicles",
    }
    for r in results:
        assert expected_keys.issubset(r.keys()), f"Missing keys in {r['crossing_id']}: {expected_keys - r.keys()}"


def test_total_time_is_travel_plus_wait():
    """total_time_min should equal eta_minutes + predicted_wait_min."""
    conn = _make_db()
    _insert_reading(conn, "batrovci", 20.0, minutes_ago=1)

    results = simulate(conn, 44.8176, 20.4633, speed_kmh=100)
    for r in results:
        expected = round(r["eta_minutes"] + r["predicted_wait_min"], 1)
        assert r["total_time_min"] == expected, (
            f"{r['crossing_id']}: total_time_min {r['total_time_min']} != eta + predicted_wait {expected}"
        )
