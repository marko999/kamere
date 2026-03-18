"""Scene analysis — extracts higher-level info from frame + detections + tracking."""

import json
from datetime import datetime, timezone

import cv2
import numpy as np


def analyze_scene(frame: np.ndarray, detections: dict, queue_data: dict | None = None,
                   view_type: str = "approach") -> dict:
    """
    Analyze the full scene from frame, YOLO detections, and queue tracking data.

    Args:
        frame: camera frame as numpy array
        detections: dict from detector.detect()
        queue_data: dict from queue_analyzer.analyze_queue() (None on first frame)
        view_type: "queue" (reliable), "approach" (partial), "post_control" (no wait data)

    Returns dict with all scene analysis fields.
    """
    counts = detections.get("counts", {})

    car_count = counts.get("car", 0)
    truck_count = counts.get("truck", 0)
    bus_count = counts.get("bus", 0)
    motorcycle_count = counts.get("motorcycle", 0)
    person_count = counts.get("person", 0)
    bicycle_count = counts.get("bicycle", 0)

    weather = _detect_weather(frame)
    anomalies = _detect_anomalies(
        car_count, truck_count, bus_count, motorcycle_count, weather, queue_data
    )

    # Wait time comes from tracking, not guessing
    estimated_wait_min = None
    queue_moving = None
    queue_length_px = None
    avg_speed_px_s = None
    throughput_per_min = None
    vehicles_tracked = 0

    total_vehicles = car_count + truck_count + bus_count + motorcycle_count

    if queue_data and total_vehicles > 0 and view_type != "post_control":
        # Only report wait time if camera sees the queue (not post-control zone)
        estimated_wait_min = queue_data.get("estimated_wait_min")
        queue_moving = queue_data.get("queue_moving")
        queue_length_px = queue_data.get("queue_length_px")
        avg_speed_px_s = queue_data.get("avg_speed_px_s")
        throughput_per_min = queue_data.get("throughput_per_min")
        vehicles_tracked = queue_data.get("vehicles_tracked", 0)

    return {
        "car_count": car_count,
        "truck_count": truck_count,
        "bus_count": bus_count,
        "motorcycle_count": motorcycle_count,
        "person_count": person_count,
        "bicycle_count": bicycle_count,
        "weather": weather,
        "active_lanes": None,
        "queue_length_m": None,
        "congestion_trend": None,
        "anomalies": anomalies,
        "estimated_wait_min": estimated_wait_min,
        # Extra tracking fields (stored in raw_json)
        "queue_moving": queue_moving,
        "queue_length_px": queue_length_px,
        "avg_speed_px_s": avg_speed_px_s,
        "throughput_per_min": throughput_per_min,
        "vehicles_tracked": vehicles_tracked,
        "view_type": view_type,
    }


# ---------------------------------------------------------------------------
# Weather detection (simple CV heuristics)
# ---------------------------------------------------------------------------

def _detect_weather(frame: np.ndarray) -> str:
    """
    Classify weather from frame using simple image stats.

    Returns one of: "clear", "overcast", "fog", "night", "unknown".
    """
    try:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    except Exception:
        return "unknown"

    h, s, v = cv2.split(hsv)

    brightness = float(np.mean(v))
    contrast = float(np.std(v))
    saturation = float(np.mean(s))

    # Night: very dark
    if brightness < 40:
        return "night"

    # Fog: low brightness + very low contrast
    if brightness < 100 and contrast < 20:
        return "fog"

    # Check sky color in top 20% of frame
    height = frame.shape[0]
    sky_region = hsv[:int(height * 0.2), :, :]
    sky_h, sky_s, sky_v = cv2.split(sky_region)

    sky_brightness = float(np.mean(sky_v))
    sky_hue = float(np.mean(sky_h))
    sky_saturation = float(np.mean(sky_s))

    # Blue sky: hue roughly 90-130 in OpenCV (0-180 scale), decent saturation
    if 90 <= sky_hue <= 130 and sky_saturation > 40 and sky_brightness > 120:
        return "clear"

    # Overcast: low saturation + moderate brightness
    if saturation < 40 and brightness < 80:
        return "overcast"

    # Low contrast overall suggests overcast
    if contrast < 35 and saturation < 50:
        return "overcast"

    # Default: if bright enough, assume clear
    if brightness > 100:
        return "clear"

    return "unknown"


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------

def _detect_anomalies(
    car_count: int,
    truck_count: int,
    bus_count: int,
    motorcycle_count: int,
    weather: str,
    queue_data: dict | None = None,
) -> str:
    """Detect anomalies and return as comma-separated string."""
    anomalies = []
    total_vehicles = car_count + truck_count + bus_count + motorcycle_count

    # Possibly closed: no vehicles during daytime
    if total_vehicles == 0 and weather not in ("night", "unknown"):
        anomalies.append("possibly_closed")

    # Buses slow everything down
    if bus_count > 0:
        anomalies.append("buses_present")

    # Heavy truck traffic
    if car_count > 0 and truck_count > car_count * 2:
        anomalies.append("heavy_truck_traffic")
    elif car_count == 0 and truck_count > 2:
        anomalies.append("heavy_truck_traffic")

    # Queue stopped (from tracking data)
    if queue_data and queue_data.get("queue_moving") is False and total_vehicles > 0:
        anomalies.append("queue_stopped")

    return ",".join(anomalies)


# ---------------------------------------------------------------------------
# Database reading builder
# ---------------------------------------------------------------------------

def build_reading(camera: dict, analysis: dict) -> dict:
    """Build a reading dict ready for database insertion."""
    reading = {
        "crossing_id": camera["crossing"].lower().replace(" ", "_"),
        "camera_id": camera["id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    reading.update(analysis)
    reading["raw_json"] = json.dumps(analysis)
    return reading
