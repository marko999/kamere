"""SQLite database layer for Kamere readings."""

import json
import sqlite3
from datetime import datetime, timezone

from .config import CAMERAS, CROSSINGS, DB_PATH

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS crossings (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    country_border  TEXT
);

CREATE TABLE IF NOT EXISTS readings (
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
    raw_json            TEXT,
    FOREIGN KEY (crossing_id) REFERENCES crossings(id)
);
"""

# ---------------------------------------------------------------------------
# Crossing → country-border mapping (best-effort from camera sources)
# ---------------------------------------------------------------------------

_BORDER_MAP: dict[str, str] = {
    # MUP — Serbian crossings
    "Djala":          "SRB-HUN",
    "Kelebija":       "SRB-HUN",
    "Horgos":         "SRB-HUN",
    "Jabuka":         "SRB-ROU",
    "Vatin":          "SRB-ROU",
    "Gostun":         "SRB-MNE",
    "Spiljani":       "SRB-MNE",
    "Batrovci":       "SRB-HRV",
    "Sid":            "SRB-HRV",
    "Kotroman":       "SRB-BIH",
    "Mali Zvornik":   "SRB-BIH",
    "Sremska Raca":   "SRB-BIH",
    "Trbusnica":      "SRB-BIH",
    "Vrska Cuka":     "SRB-BGR",
    "Gradina":        "SRB-BGR",
    "Presevo":        "SRB-MKD",
    # HAK — Croatian crossings
    "Bregana":        "HRV-SLO",
    "Macelj":         "HRV-SLO",
    "Pasjak":         "HRV-SLO",
    "Bajakovo":       "SRB-HRV",
    "Stara Gradiska": "HRV-BIH",
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def init_db(db_path: str | None = None) -> sqlite3.Connection:
    """Create tables (if needed), seed crossings, and return a connection.

    Args:
        db_path: Path to the SQLite file. Defaults to config.DB_PATH.

    Returns:
        An open sqlite3.Connection with row_factory set to sqlite3.Row.
    """
    if db_path is None:
        db_path = DB_PATH

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript(_SCHEMA)

    # Seed crossings from config
    for name in CROSSINGS:
        border = _BORDER_MAP.get(name, "")
        conn.execute(
            "INSERT OR IGNORE INTO crossings (id, name, country_border) VALUES (?, ?, ?)",
            (name.lower().replace(" ", "_"), name, border),
        )
    conn.commit()
    return conn


def save_reading(conn: sqlite3.Connection, reading: dict) -> int:
    """Insert a single reading row.

    Args:
        conn: An open database connection.
        reading: Dict whose keys match the readings column names.
                 Missing keys default to None.

    Returns:
        The rowid of the newly inserted row.
    """
    cols = [
        "crossing_id",
        "camera_id",
        "timestamp",
        "car_count",
        "truck_count",
        "bus_count",
        "motorcycle_count",
        "person_count",
        "active_lanes",
        "weather",
        "queue_length_m",
        "congestion_trend",
        "anomalies",
        "estimated_wait_min",
        "raw_json",
    ]

    # Default timestamp to now (UTC ISO format) if not provided
    if "timestamp" not in reading or reading["timestamp"] is None:
        reading["timestamp"] = datetime.now(timezone.utc).isoformat()

    # If raw_json value is a dict/list, serialise it
    raw = reading.get("raw_json")
    if isinstance(raw, (dict, list)):
        reading["raw_json"] = json.dumps(raw, ensure_ascii=False)

    values = [reading.get(c) for c in cols]
    placeholders = ", ".join("?" for _ in cols)
    col_names = ", ".join(cols)

    cur = conn.execute(
        f"INSERT INTO readings ({col_names}) VALUES ({placeholders})",
        values,
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def get_latest_reading(conn: sqlite3.Connection, crossing_id: str) -> dict | None:
    """Return the most recent reading for a crossing, or None.

    Args:
        conn: An open database connection.
        crossing_id: The crossing id (e.g. "batrovci").

    Returns:
        A dict with all reading columns, or None if no reading exists.
    """
    row = conn.execute(
        "SELECT * FROM readings WHERE crossing_id = ? ORDER BY timestamp DESC LIMIT 1",
        (crossing_id,),
    ).fetchone()

    if row is None:
        return None
    return dict(row)


def get_all_latest(conn: sqlite3.Connection) -> list[dict]:
    """Return the latest reading for every crossing that has at least one.

    Uses a window function to pick the newest row per crossing_id.

    Returns:
        List of dicts, one per crossing (only crossings with readings).
    """
    rows = conn.execute(
        """
        SELECT *
        FROM (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY crossing_id ORDER BY timestamp DESC
            ) AS rn
            FROM readings
        )
        WHERE rn = 1
        ORDER BY crossing_id
        """
    ).fetchall()

    return [dict(r) for r in rows]
