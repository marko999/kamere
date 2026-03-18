"""GPS simulator — estimates travel + wait time to each border crossing."""

import math
import sqlite3
from datetime import datetime, timedelta, timezone

from .config import CROSSINGS
from .database import _BORDER_MAP

# ---------------------------------------------------------------------------
# Crossing coordinates (approximate WGS-84)
# ---------------------------------------------------------------------------

CROSSING_COORDS: dict[str, tuple[float, float]] = {
    "djala": (46.0891, 19.0897),
    "kelebija": (46.1714, 19.5478),
    "horgos": (46.1547, 19.9764),
    "jabuka": (46.1831, 20.6478),
    "gostun": (43.3753, 19.8406),
    "spiljani": (43.3528, 19.7361),
    "batrovci": (45.0536, 19.1042),
    "sid": (45.1172, 19.2194),
    "vatin": (44.7500, 21.3833),
    "kotroman": (44.1503, 19.3136),
    "mali_zvornik": (44.3881, 19.1064),
    "sremska_raca": (44.9736, 19.2833),
    "trbusnica": (44.0547, 19.3542),
    "vrska_cuka": (43.2050, 22.4208),
    "gradina": (43.2208, 22.6844),
    "presevo": (42.3058, 21.6403),
    "bregana": (45.8378, 15.7000),
    "macelj": (46.2317, 15.8572),
    "pasjak": (45.4653, 14.2878),
    "bajakovo": (45.0539, 19.0958),
    "stara_gradiska": (45.1428, 17.2500),
}


# ---------------------------------------------------------------------------
# Haversine
# ---------------------------------------------------------------------------

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance between two WGS-84 points in kilometres."""
    R = 6371.0  # Earth mean radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _crossing_id(name: str) -> str:
    return name.lower().replace(" ", "_")


def _crossing_name_map() -> dict[str, str]:
    """Return {crossing_id: crossing_name} for all configured crossings."""
    return {_crossing_id(n): n for n in CROSSINGS}


def _growth_rate(conn: sqlite3.Connection, crossing_id: str) -> float:
    """Compute wait-time growth rate (min/hour) over the last 30 minutes.

    Strategy: split the last 30 min of readings into two halves,
    compare their average estimated_wait_min.  Return the hourly
    extrapolation of the difference.
    """
    now = datetime.now(timezone.utc)
    since = (now - timedelta(minutes=30)).isoformat()

    rows = conn.execute(
        """
        SELECT timestamp, estimated_wait_min
        FROM readings
        WHERE crossing_id = ? AND timestamp > ? AND estimated_wait_min IS NOT NULL
        ORDER BY timestamp ASC
        """,
        (crossing_id, since),
    ).fetchall()

    if len(rows) < 2:
        return 0.0

    mid = len(rows) // 2
    first_half = [r["estimated_wait_min"] for r in rows[:mid]]
    second_half = [r["estimated_wait_min"] for r in rows[mid:]]

    avg_first = sum(first_half) / len(first_half) if first_half else 0.0
    avg_second = sum(second_half) / len(second_half) if second_half else 0.0

    # Difference is over ~15 min; extrapolate to 1 hour
    diff_per_15 = avg_second - avg_first
    return diff_per_15 * 4.0  # 15 min -> 60 min


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def simulate(
    conn: sqlite3.Connection,
    user_lat: float,
    user_lon: float,
    speed_kmh: float = 100,
) -> list[dict]:
    """Simulate travel to every crossing and predict arrival wait times.

    Args:
        conn: Open SQLite connection (row_factory = sqlite3.Row).
        user_lat: User latitude (WGS-84).
        user_lon: User longitude (WGS-84).
        speed_kmh: Average driving speed in km/h (default 100).

    Returns:
        List of dicts sorted by total_time_min (ascending = best option first).
    """
    name_map = _crossing_name_map()
    results: list[dict] = []

    for cid, (clat, clon) in CROSSING_COORDS.items():
        dist = haversine_km(user_lat, user_lon, clat, clon)
        eta_hours = dist / speed_kmh if speed_kmh > 0 else 0.0
        eta_minutes = eta_hours * 60.0

        # Current wait time
        row = conn.execute(
            "SELECT estimated_wait_min, weather, car_count, truck_count, bus_count "
            "FROM readings WHERE crossing_id = ? ORDER BY timestamp DESC LIMIT 1",
            (cid,),
        ).fetchone()

        current_wait = 0.0
        current_weather = None
        current_vehicles = 0
        if row:
            current_wait = row["estimated_wait_min"] or 0.0
            current_weather = row["weather"]
            current_vehicles = (
                (row["car_count"] or 0)
                + (row["truck_count"] or 0)
                + (row["bus_count"] or 0)
            )

        # Growth rate & prediction
        gr = _growth_rate(conn, cid)
        predicted_wait = max(0.0, current_wait + gr * eta_hours)

        total = eta_minutes + predicted_wait

        # Resolve crossing name and border
        cname = name_map.get(cid, cid.replace("_", " ").title())
        border = _BORDER_MAP.get(cname, "")

        results.append({
            "crossing_id": cid,
            "crossing_name": cname,
            "country_border": border,
            "distance_km": round(dist, 1),
            "eta_minutes": round(eta_minutes, 1),
            "current_wait_min": round(current_wait, 1),
            "predicted_wait_min": round(predicted_wait, 1),
            "total_time_min": round(total, 1),
            "growth_rate_min_per_h": round(gr, 1),
            "current_weather": current_weather,
            "current_vehicles": current_vehicles,
        })

    results.sort(key=lambda r: r["total_time_min"])
    return results
