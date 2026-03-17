"""Scene analysis — extracts higher-level info from frame + detections."""

import json
from datetime import datetime, timezone

import cv2
import numpy as np


def analyze_scene(frame: np.ndarray, detections: dict) -> dict:
    """
    Analyze the full scene from frame and YOLO detections.

    Returns:
    {
        "car_count": 5,
        "truck_count": 2,
        "bus_count": 0,
        "motorcycle_count": 1,
        "person_count": 3,
        "bicycle_count": 0,
        "weather": "clear",
        "active_lanes": None,
        "queue_length_m": None,
        "congestion_trend": None,
        "anomalies": "",
        "estimated_wait_min": 12.5,
    }
    """
    counts = detections.get("counts", {})

    car_count = counts.get("car", 0)
    truck_count = counts.get("truck", 0)
    bus_count = counts.get("bus", 0)
    motorcycle_count = counts.get("motorcycle", 0)
    person_count = counts.get("person", 0)
    bicycle_count = counts.get("bicycle", 0)

    weather = _detect_weather(frame)
    estimated_wait = _estimate_wait(car_count, truck_count, bus_count)
    anomalies = _detect_anomalies(
        car_count, truck_count, bus_count, motorcycle_count, weather
    )

    return {
        "car_count": car_count,
        "truck_count": truck_count,
        "bus_count": bus_count,
        "motorcycle_count": motorcycle_count,
        "person_count": person_count,
        "bicycle_count": bicycle_count,
        "weather": weather,
        "active_lanes": None,       # needs calibration per camera
        "queue_length_m": None,     # needs calibration per camera
        "congestion_trend": None,   # needs historical data
        "anomalies": anomalies,
        "estimated_wait_min": estimated_wait,
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
# Wait time estimation (rough placeholder)
# ---------------------------------------------------------------------------

def _estimate_wait(car_count: int, truck_count: int, bus_count: int) -> float:
    """
    Very rough wait time estimate in minutes.

    Formula: cars * 2 + trucks * 5 + buses * 8.
    Real calibration comes later with actual crossing data.
    """
    total = car_count * 2 + truck_count * 5 + bus_count * 8
    return round(float(total), 1)


# ---------------------------------------------------------------------------
# Anomaly detection
# ---------------------------------------------------------------------------

def _detect_anomalies(
    car_count: int,
    truck_count: int,
    bus_count: int,
    motorcycle_count: int,
    weather: str,
) -> str:
    """
    Detect anomalies and return as comma-separated string.
    """
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

    return ",".join(anomalies)


# ---------------------------------------------------------------------------
# Database reading builder
# ---------------------------------------------------------------------------

def build_reading(camera: dict, analysis: dict) -> dict:
    """
    Build a reading dict ready for database insertion.

    Args:
        camera: camera dict from config (must have "crossing" and "id" keys)
        analysis: dict returned by analyze_scene()

    Returns:
        Full reading dict with crossing_id, camera_id, timestamp, all
        analysis fields, and raw_json.
    """
    reading = {
        "crossing_id": camera["crossing"].lower().replace(" ", "_"),
        "camera_id": camera["id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    reading.update(analysis)
    reading["raw_json"] = json.dumps(analysis)
    return reading
