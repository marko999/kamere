"""Queue dynamics analysis from vehicle tracking data.

Estimates queue speed, wait times, and throughput by measuring how vehicles
move between consecutive frames. No external APIs or guessing formulas --
everything is derived from pixel-level displacement measurements.
"""

import logging
from collections import deque
from statistics import mean

logger = logging.getLogger(__name__)

# Vehicle classes that constitute a queue (exclude person, bicycle)
_QUEUE_VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle"}

# Speed filtering thresholds (pixels per frame)
_MAX_DISPLACEMENT_PX = 100  # above this, probably a wrong match
_MIN_DISPLACEMENT_PX = 0.5  # below this, noise / stationary parked vehicle

# Minimum average speed to consider queue "moving" (px/s)
_MOVING_THRESHOLD_PX_S = 0.5


def analyze_queue(
    tracker_result: dict,
    detections: dict,
    frame_interval: float = 30.0,
) -> dict:
    """
    Analyze queue dynamics from tracker matches.

    Args:
        tracker_result: dict from VehicleTracker.update() with keys:
            - matches: list of dicts with prev_centroid, curr_centroid,
              displacement_px, bbox_area_ratio
            - unmatched_new: list of new detections
            - unmatched_gone: list of departed detections
            - has_previous: bool
        detections: dict from detector.detect() with keys:
            - detections: list of {"class", "confidence", "bbox"}
            - counts: {"car": N, "truck": N, ...}
        frame_interval: seconds between frames (default 30)

    Returns:
        dict with queue analysis fields. See module docstring for details.
    """
    try:
        return _analyze_queue_inner(tracker_result, detections, frame_interval)
    except Exception:
        logger.exception("Queue analysis failed, returning empty result")
        return _empty_result()


def _analyze_queue_inner(
    tracker_result: dict,
    detections: dict,
    frame_interval: float,
) -> dict:
    has_previous = tracker_result.get("has_previous", False)
    matches = tracker_result.get("matches", [])
    unmatched_new = tracker_result.get("unmatched_new", [])
    unmatched_gone = tracker_result.get("unmatched_gone", [])

    det_list = detections.get("detections", [])

    # --- Queue length from ALL current detections ---
    queue_length_px = _compute_queue_length(det_list)

    # --- Vehicle entry/exit counts ---
    vehicles_entered = len(unmatched_new)
    vehicles_exited = len(unmatched_gone)

    # --- First frame: no tracking data yet ---
    if not has_previous:
        logger.debug("First frame — no previous data for speed calculation")
        return {
            "avg_speed_px_s": None,
            "max_speed_px_s": None,
            "min_speed_px_s": None,
            "queue_length_px": queue_length_px,
            "estimated_wait_s": None,
            "estimated_wait_min": None,
            "queue_moving": None,
            "vehicles_tracked": 0,
            "vehicles_entered": vehicles_entered,
            "vehicles_exited": vehicles_exited,
            "throughput_per_min": None,
        }

    # --- Speed calculation from matched vehicles ---
    speeds = _compute_speeds(matches, frame_interval)
    vehicles_tracked = len(matches)

    if not speeds:
        # No valid speed measurements
        logger.debug(
            "No valid speed measurements from %d matches", len(matches)
        )
        throughput = _compute_throughput(vehicles_exited, frame_interval)
        return {
            "avg_speed_px_s": None,
            "max_speed_px_s": None,
            "min_speed_px_s": None,
            "queue_length_px": queue_length_px,
            "estimated_wait_s": None,
            "estimated_wait_min": None,
            "queue_moving": None,
            "vehicles_tracked": vehicles_tracked,
            "vehicles_entered": vehicles_entered,
            "vehicles_exited": vehicles_exited,
            "throughput_per_min": throughput,
        }

    avg_speed = mean(speeds)
    max_speed = max(speeds)
    min_speed = min(speeds)
    queue_moving = avg_speed > _MOVING_THRESHOLD_PX_S

    # --- Wait time estimation ---
    estimated_wait_s = None
    estimated_wait_min = None

    if queue_moving and avg_speed > 0 and queue_length_px is not None:
        estimated_wait_s = queue_length_px / avg_speed
        estimated_wait_min = round(estimated_wait_s / 60.0, 1)
        estimated_wait_s = round(estimated_wait_s, 1)

    throughput = _compute_throughput(vehicles_exited, frame_interval)

    return {
        "avg_speed_px_s": round(avg_speed, 3),
        "max_speed_px_s": round(max_speed, 3),
        "min_speed_px_s": round(min_speed, 3),
        "queue_length_px": queue_length_px,
        "estimated_wait_s": estimated_wait_s,
        "estimated_wait_min": estimated_wait_min,
        "queue_moving": queue_moving,
        "vehicles_tracked": vehicles_tracked,
        "vehicles_entered": vehicles_entered,
        "vehicles_exited": vehicles_exited,
        "throughput_per_min": throughput,
    }


def _compute_queue_length(det_list: list) -> float | None:
    """Compute queue length as spread of vehicle centroids along dominant axis.

    Only considers vehicle classes (car, truck, bus, motorcycle).
    Uses the axis (X or Y) with higher variance as the queue direction.
    """
    centroids = []
    for det in det_list:
        cls = det.get("class", "")
        if cls not in _QUEUE_VEHICLE_CLASSES:
            continue

        bbox = det.get("bbox")
        if not bbox or len(bbox) != 4:
            continue

        x1, y1, x2, y2 = bbox
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        centroids.append((cx, cy))

    if len(centroids) < 2:
        # Need at least 2 vehicles to measure a spread
        return None

    xs = [c[0] for c in centroids]
    ys = [c[1] for c in centroids]

    # Determine dominant axis by variance
    var_x = _variance(xs)
    var_y = _variance(ys)

    if var_x >= var_y:
        # Queue runs horizontally
        spread = max(xs) - min(xs)
    else:
        # Queue runs vertically
        spread = max(ys) - min(ys)

    return round(spread, 1)


def _variance(values: list[float]) -> float:
    """Compute population variance of a list of floats."""
    if len(values) < 2:
        return 0.0
    m = mean(values)
    return sum((v - m) ** 2 for v in values) / len(values)


def _compute_speeds(
    matches: list[dict], frame_interval: float
) -> list[float]:
    """Extract valid per-vehicle speeds from tracker matches.

    Filters out likely mismatches (displacement > 100px) and noise
    (displacement < 2px).
    """
    if frame_interval <= 0:
        logger.warning("Invalid frame_interval=%s, cannot compute speeds",
                       frame_interval)
        return []

    speeds = []
    for match in matches:
        displacement = match.get("displacement_px")
        if displacement is None:
            continue

        # Filter outliers and noise
        if displacement > _MAX_DISPLACEMENT_PX:
            logger.debug(
                "Ignoring match with displacement %.1f px (likely wrong match)",
                displacement,
            )
            continue
        if displacement < _MIN_DISPLACEMENT_PX:
            continue

        speed = displacement / frame_interval
        speeds.append(speed)

    return speeds


def _compute_throughput(
    vehicles_exited: int, frame_interval: float
) -> float | None:
    """Estimate throughput in vehicles per minute from exited vehicle count."""
    if frame_interval <= 0:
        return None
    if vehicles_exited == 0:
        return 0.0
    return round(vehicles_exited / frame_interval * 60.0, 2)


def _empty_result() -> dict:
    """Return a safe empty result for when analysis fails."""
    return {
        "avg_speed_px_s": None,
        "max_speed_px_s": None,
        "min_speed_px_s": None,
        "queue_length_px": None,
        "estimated_wait_s": None,
        "estimated_wait_min": None,
        "queue_moving": None,
        "vehicles_tracked": 0,
        "vehicles_entered": 0,
        "vehicles_exited": 0,
        "throughput_per_min": None,
    }


# ---------------------------------------------------------------------------
# Rolling history for smoothing across frames
# ---------------------------------------------------------------------------


class QueueHistory:
    """Keeps rolling history of queue measurements per camera for smoothing.

    Individual frame-to-frame measurements are noisy. This class maintains
    a sliding window of recent analyses per camera and returns smoothed
    (averaged) values.
    """

    # Fields that get averaged across the window
    _NUMERIC_FIELDS = (
        "avg_speed_px_s",
        "max_speed_px_s",
        "min_speed_px_s",
        "queue_length_px",
        "throughput_per_min",
    )

    def __init__(self, window: int = 10):
        if window < 1:
            raise ValueError(f"window must be >= 1, got {window}")
        self._window = window
        self._history: dict[str, deque] = {}

    def add(self, camera_id: str, analysis: dict) -> dict:
        """Add an analysis result and return a smoothed version.

        The smoothed version averages numeric fields over the last N readings,
        skipping None values. Wait time is recomputed from smoothed queue
        length and speed. Non-numeric fields come from the latest reading.

        Args:
            camera_id: unique camera identifier
            analysis: dict returned by analyze_queue()

        Returns:
            Smoothed analysis dict with the same keys.
        """
        if camera_id not in self._history:
            self._history[camera_id] = deque(maxlen=self._window)

        self._history[camera_id].append(analysis)

        return self._smooth(camera_id, analysis)

    def _smooth(self, camera_id: str, latest: dict) -> dict:
        """Produce a smoothed result from the history window."""
        history = self._history[camera_id]

        smoothed = dict(latest)  # start with latest values

        # Average each numeric field, skipping Nones
        for field in self._NUMERIC_FIELDS:
            values = [
                entry[field]
                for entry in history
                if entry.get(field) is not None
            ]
            if values:
                smoothed[field] = round(mean(values), 3)
            else:
                smoothed[field] = None

        # Recompute wait time from smoothed speed and queue length
        avg_speed = smoothed.get("avg_speed_px_s")
        queue_length = smoothed.get("queue_length_px")

        if (
            avg_speed is not None
            and avg_speed > _MOVING_THRESHOLD_PX_S
            and queue_length is not None
            and queue_length > 0
        ):
            smoothed["estimated_wait_s"] = round(queue_length / avg_speed, 1)
            smoothed["estimated_wait_min"] = round(
                queue_length / avg_speed / 60.0, 1
            )
            smoothed["queue_moving"] = True
        elif avg_speed is not None and avg_speed <= _MOVING_THRESHOLD_PX_S:
            smoothed["estimated_wait_s"] = None
            smoothed["estimated_wait_min"] = None
            smoothed["queue_moving"] = False
        else:
            smoothed["estimated_wait_s"] = None
            smoothed["estimated_wait_min"] = None
            smoothed["queue_moving"] = latest.get("queue_moving")

        # These come directly from the latest reading (not averaged)
        smoothed["vehicles_tracked"] = latest.get("vehicles_tracked", 0)
        smoothed["vehicles_entered"] = latest.get("vehicles_entered", 0)
        smoothed["vehicles_exited"] = latest.get("vehicles_exited", 0)

        return smoothed

    def clear(self, camera_id: str | None = None):
        """Clear history for a specific camera or all cameras."""
        if camera_id is None:
            self._history.clear()
        else:
            self._history.pop(camera_id, None)

    def __len__(self) -> int:
        """Total number of cameras being tracked."""
        return len(self._history)

    def history_length(self, camera_id: str) -> int:
        """Number of readings stored for a camera."""
        if camera_id not in self._history:
            return 0
        return len(self._history[camera_id])
