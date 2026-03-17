"""FastAPI application — serves the Kamere API and static files."""

import json
import os
import glob
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import CAMERAS, CROSSINGS, FRAMES_DIR, get_cameras_for_crossing
from .database import init_db, get_all_latest, get_latest_reading, DB_PATH

# ---------------------------------------------------------------------------
# DB connection (managed via lifespan)
# ---------------------------------------------------------------------------

db_conn = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_conn
    db_conn = init_db(DB_PATH)
    yield
    db_conn.close()


app = FastAPI(title="Kamere", lifespan=lifespan)

# ---------------------------------------------------------------------------
# CORS — allow everything for MVP
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Build a lookup:  crossing_name  ->  crossing_id  (lowercase, underscores)
_CROSSING_ID_MAP: dict[str, str] = {
    name: name.lower().replace(" ", "_") for name in CROSSINGS
}

# Reverse lookup:  crossing_id  ->  crossing_name
_CROSSING_NAME_MAP: dict[str, str] = {v: k for k, v in _CROSSING_ID_MAP.items()}

# Pre-compute country_border from the crossings table seed logic in database.py
# (We import the border map indirectly by reading it from the DB at startup,
#  but since the DB is seeded from config, we can derive it here too.)
from .database import _BORDER_MAP  # noqa: E402


def _crossing_id(name: str) -> str:
    """Convert a crossing name to its database id."""
    return name.lower().replace(" ", "_")


def _parse_reading(row: dict) -> dict:
    """Turn a DB reading row into a clean API dict.

    Parses raw_json and merges tracking fields into the top level.
    Drops internal fields (id, rn).
    """
    out = {
        "crossing_id": row.get("crossing_id"),
        "camera_id": row.get("camera_id"),
        "timestamp": row.get("timestamp"),
        "car_count": row.get("car_count"),
        "truck_count": row.get("truck_count"),
        "bus_count": row.get("bus_count"),
        "motorcycle_count": row.get("motorcycle_count"),
        "person_count": row.get("person_count"),
        "active_lanes": row.get("active_lanes"),
        "weather": row.get("weather"),
        "queue_length_m": row.get("queue_length_m"),
        "congestion_trend": row.get("congestion_trend"),
        "anomalies": row.get("anomalies"),
        "estimated_wait_min": row.get("estimated_wait_min"),
    }

    # Parse raw_json and merge tracking data
    raw = row.get("raw_json")
    tracking = {}
    if raw:
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            tracking = {
                "queue_moving": parsed.get("queue_moving"),
                "queue_length_px": parsed.get("queue_length_px"),
                "avg_speed_px_s": parsed.get("avg_speed_px_s"),
                "throughput_per_min": parsed.get("throughput_per_min"),
                "vehicles_tracked": parsed.get("vehicles_tracked"),
            }
            # Scene extraction data
            scene = parsed.get("scene", {})
            if scene:
                tracking["road_condition"] = scene.get("road_condition")
                tracking["headlights"] = scene.get("headlights")
                tracking["image_quality"] = scene.get("image_quality")
                tracking["booths"] = scene.get("booths")
                tracking["traffic_density"] = scene.get("traffic_density")
                tracking["dominant_colors"] = scene.get("dominant_colors")
            # Vehicle detail data
            vdetails = parsed.get("vehicle_details", {})
            if vdetails:
                tracking["color_distribution"] = vdetails.get("color_distribution")
                tracking["spacing"] = vdetails.get("spacing")
                tracking["vehicles"] = vdetails.get("vehicles")
                tracking["total_analyzed"] = vdetails.get("total_analyzed")
        except (json.JSONDecodeError, TypeError):
            pass

    out.update(tracking)
    return out


def _pick_representative(readings: list[dict]) -> dict | None:
    """Pick the representative reading for a crossing.

    Strategy: the reading with the highest estimated_wait_min (worst case).
    If all are None, use the most recent by timestamp.
    """
    if not readings:
        return None

    with_wait = [r for r in readings if r.get("estimated_wait_min") is not None]
    if with_wait:
        return max(with_wait, key=lambda r: r["estimated_wait_min"])

    # Fall back to most recent
    return max(readings, key=lambda r: r.get("timestamp") or "")


def _camera_info(cam: dict) -> dict:
    """Extract the public-facing camera info from a config camera dict."""
    return {
        "id": cam["id"],
        "name": cam["name"],
        "direction": cam["direction"],
    }


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


@app.get("/api/crossings")
async def list_crossings():
    """Return all crossings with their latest readings."""

    # Get latest reading per camera (not per crossing) so we can pick worst-case.
    # The window function partitions by camera_id to get one row per camera.
    rows = db_conn.execute(
        """
        SELECT *
        FROM (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY camera_id ORDER BY timestamp DESC
            ) AS rn
            FROM readings
        )
        WHERE rn = 1
        ORDER BY crossing_id, camera_id
        """
    ).fetchall()

    # Group readings by crossing_id
    readings_by_crossing: dict[str, list[dict]] = {}
    for row in rows:
        r = _parse_reading(dict(row))
        cid = r["crossing_id"]
        readings_by_crossing.setdefault(cid, []).append(r)

    # Build response
    crossings = []
    for name in CROSSINGS:
        cid = _crossing_id(name)
        cameras = get_cameras_for_crossing(name)
        camera_list = [_camera_info(c) for c in cameras]

        latest_readings = readings_by_crossing.get(cid, [])
        representative = _pick_representative(latest_readings)

        crossings.append({
            "id": cid,
            "name": name,
            "country_border": _BORDER_MAP.get(name, ""),
            "cameras": camera_list,
            "latest": representative,
        })

    return {"crossings": crossings}


@app.get("/api/crossings/{crossing_id}")
async def get_crossing(crossing_id: str):
    """Return a single crossing with latest + 24h history."""

    name = _CROSSING_NAME_MAP.get(crossing_id)
    if name is None:
        raise HTTPException(status_code=404, detail="Crossing not found")

    cameras = get_cameras_for_crossing(name)
    camera_list = [_camera_info(c) for c in cameras]

    # Latest reading (single, most recent for this crossing)
    latest_row = get_latest_reading(db_conn, crossing_id)
    latest = _parse_reading(latest_row) if latest_row else None

    # History — last 24 hours
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    since_iso = since.isoformat()

    history_rows = db_conn.execute(
        "SELECT * FROM readings WHERE crossing_id = ? AND timestamp > ? ORDER BY timestamp DESC",
        (crossing_id, since_iso),
    ).fetchall()

    history = [_parse_reading(dict(r)) for r in history_rows]

    return {
        "crossing": {
            "id": crossing_id,
            "name": name,
            "country_border": _BORDER_MAP.get(name, ""),
        },
        "cameras": camera_list,
        "latest": latest,
        "history": history,
    }


@app.get("/api/cameras/{camera_id}/frame")
async def get_camera_frame(camera_id: str):
    """Serve the latest frame image for a camera."""

    pattern = os.path.join(FRAMES_DIR, f"{camera_id}_*.jpg")
    files = glob.glob(pattern)

    if not files:
        raise HTTPException(status_code=404, detail="No frame available")

    # Pick the most recent file (highest timestamp suffix)
    latest_file = max(files)
    return FileResponse(latest_file, media_type="image/jpeg")


# ---------------------------------------------------------------------------
# Static files / SPA
# ---------------------------------------------------------------------------


@app.get("/")
async def index():
    """Serve the main HTML page."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if not os.path.isfile(index_path):
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(index_path)


# Mount static directory (CSS, JS, images) — must come after explicit routes
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
