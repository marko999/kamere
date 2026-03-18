"""Peak hours pattern analysis for border crossings."""

import sqlite3
from datetime import datetime, timedelta, timezone


def get_hourly_pattern(conn: sqlite3.Connection, crossing_id: str, days: int = 7) -> dict:
    """Returns hourly pattern with peak/quiet hours.

    Aggregates estimated_wait_min by hour-of-day over the last `days` days.
    Peak hours: where avg_wait > overall_avg * 1.5.
    Quiet hours: where avg_wait < overall_avg * 0.5.

    Args:
        conn: An open database connection.
        crossing_id: The crossing id (e.g. "batrovci").
        days: Number of days to look back.

    Returns:
        Dict with hourly breakdown, peak hours, quiet hours, and summary text.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    # Count total readings for this crossing in the period
    count_row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM readings WHERE crossing_id = ? AND timestamp > ?",
        (crossing_id, since),
    ).fetchone()
    total_readings = count_row["cnt"] if count_row else 0

    if total_readings < 100:
        return {
            "crossing_id": crossing_id,
            "days": days,
            "total_readings": total_readings,
            "hourly": [],
            "peak_hours": [],
            "quiet_hours": [],
            "peak_description": None,
            "quiet_description": None,
            "busiest_hour": None,
            "quietest_hour": None,
            "avg_peak_wait": None,
            "avg_quiet_wait": None,
            "overall_avg_wait": None,
        }

    # Aggregate by hour
    rows = conn.execute(
        """
        SELECT
            CAST(strftime('%H', timestamp) AS INTEGER) AS hour,
            AVG(estimated_wait_min) AS avg_wait,
            MAX(estimated_wait_min) AS max_wait,
            COUNT(*) AS reading_count
        FROM readings
        WHERE crossing_id = ? AND timestamp > ? AND estimated_wait_min IS NOT NULL
        GROUP BY strftime('%H', timestamp)
        ORDER BY hour
        """,
        (crossing_id, since),
    ).fetchall()

    if not rows:
        return {
            "crossing_id": crossing_id,
            "days": days,
            "total_readings": total_readings,
            "hourly": [],
            "peak_hours": [],
            "quiet_hours": [],
            "peak_description": None,
            "quiet_description": None,
            "busiest_hour": None,
            "quietest_hour": None,
            "avg_peak_wait": None,
            "avg_quiet_wait": None,
            "overall_avg_wait": None,
        }

    hourly = []
    for r in rows:
        hourly.append({
            "hour": r["hour"],
            "avg_wait": round(r["avg_wait"], 1) if r["avg_wait"] is not None else None,
            "max_wait": round(r["max_wait"], 1) if r["max_wait"] is not None else None,
            "reading_count": r["reading_count"],
        })

    # Overall average across all hours (weighted by reading count)
    total_wait_sum = sum(h["avg_wait"] * h["reading_count"] for h in hourly if h["avg_wait"] is not None)
    total_count = sum(h["reading_count"] for h in hourly if h["avg_wait"] is not None)
    overall_avg = total_wait_sum / total_count if total_count > 0 else 0

    # Peak: avg_wait > overall_avg * 1.5
    peak_hours = [h["hour"] for h in hourly if h["avg_wait"] is not None and h["avg_wait"] > overall_avg * 1.5]
    # Quiet: avg_wait < overall_avg * 0.5
    quiet_hours = [h["hour"] for h in hourly if h["avg_wait"] is not None and h["avg_wait"] < overall_avg * 0.5]

    # Busiest / quietest single hour
    hours_with_wait = [h for h in hourly if h["avg_wait"] is not None]
    busiest = max(hours_with_wait, key=lambda h: h["avg_wait"]) if hours_with_wait else None
    quietest = min(hours_with_wait, key=lambda h: h["avg_wait"]) if hours_with_wait else None

    # Average wait during peak / quiet hours
    peak_waits = [h["avg_wait"] for h in hourly if h["hour"] in peak_hours and h["avg_wait"] is not None]
    quiet_waits = [h["avg_wait"] for h in hourly if h["hour"] in quiet_hours and h["avg_wait"] is not None]
    avg_peak_wait = round(sum(peak_waits) / len(peak_waits), 1) if peak_waits else None
    avg_quiet_wait = round(sum(quiet_waits) / len(quiet_waits), 1) if quiet_waits else None

    return {
        "crossing_id": crossing_id,
        "days": days,
        "total_readings": total_readings,
        "hourly": hourly,
        "peak_hours": sorted(peak_hours),
        "quiet_hours": sorted(quiet_hours),
        "peak_description": _hours_to_range(peak_hours),
        "quiet_description": _hours_to_range(quiet_hours),
        "busiest_hour": busiest["hour"] if busiest else None,
        "quietest_hour": quietest["hour"] if quietest else None,
        "avg_peak_wait": avg_peak_wait,
        "avg_quiet_wait": avg_quiet_wait,
        "overall_avg_wait": round(overall_avg, 1),
    }


def get_peak_summaries(conn: sqlite3.Connection, days: int = 7) -> dict[str, str | None]:
    """Return crossing_id -> peak description for all crossings.

    Args:
        conn: An open database connection.
        days: Number of days to look back.

    Returns:
        Dict mapping crossing_id to peak_description (or None if insufficient data).
    """
    # Get all distinct crossing_ids from readings
    rows = conn.execute("SELECT DISTINCT crossing_id FROM readings").fetchall()
    crossing_ids = [r["crossing_id"] for r in rows]

    result: dict[str, str | None] = {}
    for cid in crossing_ids:
        pattern = get_hourly_pattern(conn, cid, days=days)
        result[cid] = pattern["peak_description"]

    return result


def _hours_to_range(hours: list[int]) -> str | None:
    """Convert a sorted list of hours into a human-readable range string.

    Examples:
        [10, 11, 12, 13, 14] -> "10:00 - 15:00"
        [8, 9, 14, 15, 16] -> "08:00 - 10:00, 14:00 - 17:00"
        [] -> None
    """
    if not hours:
        return None

    sorted_hours = sorted(hours)
    ranges = []
    start = sorted_hours[0]
    prev = sorted_hours[0]

    for h in sorted_hours[1:]:
        if h == prev + 1:
            prev = h
        else:
            ranges.append((start, prev + 1))
            start = h
            prev = h
    ranges.append((start, prev + 1))

    parts = []
    for s, e in ranges:
        parts.append(f"{s:02d}:00 - {e:02d}:00")

    return ", ".join(parts)
