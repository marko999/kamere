"""Queue growth rate and trend computation."""

import json
import sqlite3
from datetime import datetime, timedelta, timezone


def compute_trend(conn: sqlite3.Connection, crossing_id: str, window_minutes: int = 30) -> dict:
    """Compute queue trend from recent readings.

    Queries the last *window_minutes* of readings for *crossing_id* where
    ``estimated_wait_min > 0``, splits them into a first and second half by
    time, and derives a growth rate and qualitative trend label.

    Args:
        conn: An open SQLite connection (with ``row_factory = sqlite3.Row``).
        crossing_id: The crossing id (e.g. ``"batrovci"``).
        window_minutes: How far back to look (default 30).

    Returns:
        A dict with keys:
            - trend: ``"growing"`` | ``"stable"`` | ``"shrinking"`` | ``"unknown"``
            - trend_arrow: ``"↑"`` | ``"→"`` | ``"↓"`` | ``"—"``
            - growth_rate_min_per_h: float or None  (change in wait minutes per hour)
            - current_wait: float or None  (most recent estimated_wait_min)
            - queue_inflow_rate: float or None  (net vehicles per minute)
    """

    unknown = {
        "trend": "unknown",
        "trend_arrow": "\u2014",  # em-dash
        "growth_rate_min_per_h": None,
        "current_wait": None,
        "queue_inflow_rate": None,
    }

    since = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    since_iso = since.isoformat()

    rows = conn.execute(
        """
        SELECT timestamp, estimated_wait_min, raw_json
        FROM readings
        WHERE crossing_id = ?
          AND timestamp > ?
          AND estimated_wait_min > 0
        ORDER BY timestamp ASC
        """,
        (crossing_id, since_iso),
    ).fetchall()

    if len(rows) < 3:
        # Not enough data to determine a trend.
        # Still try to report current_wait from the most recent reading.
        latest = conn.execute(
            "SELECT estimated_wait_min FROM readings "
            "WHERE crossing_id = ? ORDER BY timestamp DESC LIMIT 1",
            (crossing_id,),
        ).fetchone()
        if latest and latest["estimated_wait_min"] is not None:
            unknown["current_wait"] = latest["estimated_wait_min"]
        return unknown

    # ----- Split into first half / second half by index -----
    mid = len(rows) // 2
    first_half = rows[:mid]
    second_half = rows[mid:]

    avg_first = sum(r["estimated_wait_min"] for r in first_half) / len(first_half)
    avg_second = sum(r["estimated_wait_min"] for r in second_half) / len(second_half)

    # Time span in hours between the midpoints of each half
    def _midpoint_ts(half):
        """Return the average timestamp (as datetime) of a list of rows."""
        times = []
        for r in half:
            ts_str = r["timestamp"]
            # Handle both Z-suffix and +00:00 formats
            try:
                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue
            times.append(dt.timestamp())
        if not times:
            return None
        return datetime.fromtimestamp(sum(times) / len(times), tz=timezone.utc)

    mid1 = _midpoint_ts(first_half)
    mid2 = _midpoint_ts(second_half)

    if mid1 is None or mid2 is None or mid1 >= mid2:
        return unknown

    time_span_hours = (mid2 - mid1).total_seconds() / 3600.0
    if time_span_hours < 1e-6:
        return unknown

    growth_rate = (avg_second - avg_first) / time_span_hours

    # Classify
    if growth_rate > 1.0:
        trend = "growing"
        arrow = "\u2191"  # ↑
    elif growth_rate < -1.0:
        trend = "shrinking"
        arrow = "\u2193"  # ↓
    else:
        trend = "stable"
        arrow = "\u2192"  # →

    current_wait = rows[-1]["estimated_wait_min"]

    # ----- Queue inflow rate (net vehicles / minute) -----
    queue_inflow_rate = _compute_inflow_rate(rows)

    return {
        "trend": trend,
        "trend_arrow": arrow,
        "growth_rate_min_per_h": round(growth_rate, 1),
        "current_wait": current_wait,
        "queue_inflow_rate": queue_inflow_rate,
    }


def _compute_inflow_rate(rows) -> float | None:
    """Compute average net inflow rate from raw_json vehicle counts.

    Looks for ``vehicles_entered`` and ``vehicles_exited`` in each reading's
    ``raw_json``.  Returns net vehicles per minute, or None if data is missing.
    """
    entered_total = 0
    exited_total = 0
    count = 0

    for r in rows:
        raw = r["raw_json"]
        if not raw:
            continue
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            continue

        ve = data.get("vehicles_entered")
        vx = data.get("vehicles_exited")
        if ve is not None and vx is not None:
            entered_total += ve
            exited_total += vx
            count += 1

    if count < 2:
        return None

    # Total time span for the rows that had inflow data
    first_ts = None
    last_ts = None
    for r in rows:
        raw = r["raw_json"]
        if not raw:
            continue
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            continue
        if data.get("vehicles_entered") is None:
            continue
        ts_str = r["timestamp"]
        try:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue
        if first_ts is None or dt < first_ts:
            first_ts = dt
        if last_ts is None or dt > last_ts:
            last_ts = dt

    if first_ts is None or last_ts is None or first_ts >= last_ts:
        return None

    span_minutes = (last_ts - first_ts).total_seconds() / 60.0
    if span_minutes < 0.1:
        return None

    net = entered_total - exited_total
    rate = net / span_minutes
    return round(rate, 2)
