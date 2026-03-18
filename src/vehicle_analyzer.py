"""Detailed per-vehicle analysis using pure OpenCV on YOLO bounding boxes.

Extracts vehicle colors, size estimates, spacing patterns, and license plate
region detection from each detected vehicle in the frame. No external APIs
or ML models beyond what YOLO already provided -- everything here is classical
computer vision on the cropped bounding box regions.
"""

import logging
from statistics import mean, stdev

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Vehicle classes we analyze (same set as queue_analyzer)
_VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle"}

# HSV color ranges for named color classification.
# Order matters: checked top-to-bottom, first match wins.
# Each entry: (name, hue_range, sat_range, val_range)
# hue_range can be a single (lo, hi) or a list of (lo, hi) for wrap-around colors.
_COLOR_RANGES = [
    # Black: very low value regardless of hue/saturation
    ("black", None, None, (0, 50)),
    # White: very low saturation, high value
    ("white", None, (0, 30), (180, 255)),
    # Gray/Silver: low saturation, mid value
    ("gray/silver", None, (0, 30), (50, 180)),
    # Red wraps around hue 0: two ranges
    ("red", [(0, 10), (170, 180)], (70, 255), (70, 255)),
    # Yellow
    ("yellow", [(20, 35)], (70, 255), (100, 255)),
    # Green
    ("green", [(35, 85)], (40, 255), (40, 255)),
    # Blue
    ("blue", [(100, 130)], (50, 255), (50, 255)),
    # Brown/Beige
    ("brown/beige", [(10, 20)], (50, 255), (50, 255)),
]

# Size category thresholds (relative_size = bbox_area / frame_area)
_SIZE_THRESHOLDS = [
    (0.01, "small"),       # motorcycles, distant vehicles
    (0.05, "medium"),      # cars at medium distance
    (0.15, "large"),       # trucks, buses, close vehicles
    (float("inf"), "very_large"),  # very close, likely front of queue
]

# Spacing formation thresholds (average gap in pixels)
_SPACING_TIGHT = 20
_SPACING_NORMAL = 60

# License plate aspect ratio bounds (width / height)
_PLATE_ASPECT_MIN = 3.0
_PLATE_ASPECT_MAX = 5.0

# License plate dimension constraints (pixels)
_PLATE_MIN_WIDTH = 40
_PLATE_MIN_HEIGHT = 10
_PLATE_MAX_HEIGHT = 40


# ---------------------------------------------------------------------------
# Color extraction
# ---------------------------------------------------------------------------


def _get_vehicle_color(frame: np.ndarray, bbox: list) -> dict:
    """Extract dominant color of a vehicle from its bounding box region.

    Crops the center 60% of the bbox to avoid background edges, converts
    to HSV, and classifies into a named color using simple range matching.

    Returns:
        {"color_name": "white", "rgb": [240, 238, 235], "hsv": [0, 5, 240]}
    """
    try:
        x1, y1, x2, y2 = [int(v) for v in bbox]
        h_frame, w_frame = frame.shape[:2]

        # Clamp to frame boundaries
        x1 = max(0, min(x1, w_frame - 1))
        y1 = max(0, min(y1, h_frame - 1))
        x2 = max(x1 + 1, min(x2, w_frame))
        y2 = max(y1 + 1, min(y2, h_frame))

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return _default_color()

        # Take center 60% to avoid background at edges
        ch, cw = crop.shape[:2]
        margin_x = int(cw * 0.2)
        margin_y = int(ch * 0.2)
        center_crop = crop[margin_y:ch - margin_y, margin_x:cw - margin_x]

        if center_crop.size == 0:
            center_crop = crop  # fallback to full crop if too small

        # Convert to HSV
        hsv_crop = cv2.cvtColor(center_crop, cv2.COLOR_BGR2HSV)

        # Compute mean HSV values
        mean_hsv = cv2.mean(hsv_crop)[:3]  # (H, S, V)
        mean_h, mean_s, mean_v = mean_hsv

        # Compute mean RGB (OpenCV is BGR)
        mean_bgr = cv2.mean(center_crop)[:3]
        mean_rgb = [int(round(mean_bgr[2])), int(round(mean_bgr[1])), int(round(mean_bgr[0]))]

        # Classify color
        color_name = _classify_color(mean_h, mean_s, mean_v)

        return {
            "color_name": color_name,
            "rgb": mean_rgb,
            "hsv": [int(round(mean_h)), int(round(mean_s)), int(round(mean_v))],
        }

    except Exception:
        logger.exception("Color extraction failed for bbox %s", bbox)
        return _default_color()


def _classify_color(h: float, s: float, v: float) -> str:
    """Classify an HSV triplet into a named color."""
    for name, hue_ranges, sat_range, val_range in _COLOR_RANGES:
        # Check value range
        if val_range is not None:
            if not (val_range[0] <= v <= val_range[1]):
                continue

        # Check saturation range
        if sat_range is not None:
            if not (sat_range[0] <= s <= sat_range[1]):
                continue

        # Check hue range (may be None for achromatic colors)
        if hue_ranges is not None:
            hue_match = False
            for hlo, hhi in hue_ranges:
                if hlo <= h <= hhi:
                    hue_match = True
                    break
            if not hue_match:
                continue

        return name

    return "other"


def _default_color() -> dict:
    """Return a safe default when color extraction fails."""
    return {"color_name": "unknown", "rgb": [0, 0, 0], "hsv": [0, 0, 0]}


# ---------------------------------------------------------------------------
# Size estimation
# ---------------------------------------------------------------------------


def _estimate_vehicle_size(bbox: list, frame_shape: tuple) -> dict:
    """Estimate vehicle size from its bounding box relative to the frame.

    Returns:
        {
            "width_px": int,
            "height_px": int,
            "area_px": int,
            "relative_size": float,  # bbox area / frame area
            "size_category": str,    # "small", "medium", "large", "very_large"
        }
    """
    try:
        x1, y1, x2, y2 = [int(v) for v in bbox]
        width_px = max(abs(x2 - x1), 1)
        height_px = max(abs(y2 - y1), 1)
        area_px = width_px * height_px

        frame_h, frame_w = frame_shape[:2]
        frame_area = max(frame_h * frame_w, 1)
        relative_size = area_px / frame_area

        size_category = "very_large"  # default if nothing matches
        for threshold, category in _SIZE_THRESHOLDS:
            if relative_size < threshold:
                size_category = category
                break

        return {
            "width_px": width_px,
            "height_px": height_px,
            "area_px": area_px,
            "relative_size": round(relative_size, 6),
            "size_category": size_category,
        }

    except Exception:
        logger.exception("Size estimation failed for bbox %s", bbox)
        return {
            "width_px": 0,
            "height_px": 0,
            "area_px": 0,
            "relative_size": 0.0,
            "size_category": "unknown",
        }


# ---------------------------------------------------------------------------
# Vehicle spacing analysis
# ---------------------------------------------------------------------------


def _compute_vehicle_spacing(detections: list[dict]) -> dict:
    """Analyze spacing between consecutive vehicles in the queue.

    Determines the dominant queue axis from centroid variance, sorts vehicles
    along that axis, and computes gap statistics between consecutive pairs.

    Returns:
        {
            "avg_spacing_px": float | None,
            "min_spacing_px": float | None,
            "max_spacing_px": float | None,
            "spacing_uniformity": float | None,  # std/mean
            "formation": str,  # "tight", "normal", "spread", "single"
        }
    """
    try:
        # Filter to vehicle classes only
        centroids = []
        for det in detections:
            cls = det.get("class", "")
            if cls not in _VEHICLE_CLASSES:
                continue
            bbox = det.get("bbox")
            if not bbox or len(bbox) != 4:
                continue
            x1, y1, x2, y2 = bbox
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            centroids.append((cx, cy))

        if len(centroids) <= 1:
            return _default_spacing("single")

        # Determine dominant axis by variance
        xs = [c[0] for c in centroids]
        ys = [c[1] for c in centroids]
        var_x = _variance(xs)
        var_y = _variance(ys)

        # Sort along dominant axis and extract positions
        if var_x >= var_y:
            # Queue runs horizontally
            centroids.sort(key=lambda c: c[0])
            positions = [c[0] for c in centroids]
        else:
            # Queue runs vertically
            centroids.sort(key=lambda c: c[1])
            positions = [c[1] for c in centroids]

        # Compute gaps between consecutive vehicles
        gaps = []
        for i in range(1, len(positions)):
            gap = abs(positions[i] - positions[i - 1])
            gaps.append(gap)

        if not gaps:
            return _default_spacing("single")

        avg_spacing = mean(gaps)
        min_spacing = min(gaps)
        max_spacing = max(gaps)

        # Uniformity: std / mean (low = uniform, high = irregular)
        if len(gaps) >= 2 and avg_spacing > 0:
            spacing_uniformity = round(stdev(gaps) / avg_spacing, 3)
        else:
            spacing_uniformity = 0.0

        # Classify formation
        if avg_spacing < _SPACING_TIGHT:
            formation = "tight"
        elif avg_spacing < _SPACING_NORMAL:
            formation = "normal"
        else:
            formation = "spread"

        return {
            "avg_spacing_px": round(avg_spacing, 1),
            "min_spacing_px": round(min_spacing, 1),
            "max_spacing_px": round(max_spacing, 1),
            "spacing_uniformity": spacing_uniformity,
            "formation": formation,
        }

    except Exception:
        logger.exception("Vehicle spacing computation failed")
        return _default_spacing("single")


def _variance(values: list[float]) -> float:
    """Compute population variance of a list of floats."""
    if len(values) < 2:
        return 0.0
    m = mean(values)
    return sum((v - m) ** 2 for v in values) / len(values)


def _default_spacing(formation: str = "single") -> dict:
    """Return a safe default spacing result."""
    return {
        "avg_spacing_px": None,
        "min_spacing_px": None,
        "max_spacing_px": None,
        "spacing_uniformity": None,
        "formation": formation,
    }


# ---------------------------------------------------------------------------
# License plate region detection
# ---------------------------------------------------------------------------


def _detect_plate_region(frame: np.ndarray, bbox: list) -> dict | None:
    """Detect potential license plate region in a vehicle bounding box.

    Uses Canny edge detection and contour filtering to find rectangular
    regions with European plate aspect ratios (~3:1 to 5:1). Does NOT
    perform OCR -- just locates the plate region.

    Returns:
        {"plate_bbox": [x1, y1, x2, y2], "plate_type": "european"} or None
    """
    try:
        x1, y1, x2, y2 = [int(v) for v in bbox]
        h_frame, w_frame = frame.shape[:2]

        # Clamp to frame boundaries
        x1 = max(0, min(x1, w_frame - 1))
        y1 = max(0, min(y1, h_frame - 1))
        x2 = max(x1 + 1, min(x2, w_frame))
        y2 = max(y1 + 1, min(y2, h_frame))

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return None

        # Convert to grayscale
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

        # Apply bilateral filter to reduce noise while keeping edges
        gray = cv2.bilateralFilter(gray, 11, 17, 17)

        # Canny edge detection
        edges = cv2.Canny(gray, 30, 200)

        # Find contours
        contours, _ = cv2.findContours(
            edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
        )

        # Sort by area descending -- larger plate candidates first
        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        for contour in contours[:30]:  # only check top 30 contours
            # Get bounding rectangle
            rx, ry, rw, rh = cv2.boundingRect(contour)

            # Filter by dimension constraints
            if rw < _PLATE_MIN_WIDTH:
                continue
            if rh < _PLATE_MIN_HEIGHT or rh > _PLATE_MAX_HEIGHT:
                continue

            # Check aspect ratio (European plates are wide rectangles)
            if rh == 0:
                continue
            aspect = rw / rh

            if _PLATE_ASPECT_MIN <= aspect <= _PLATE_ASPECT_MAX:
                plate_type = "european"
                # Return bbox relative to the vehicle crop
                return {
                    "plate_bbox": [rx, ry, rx + rw, ry + rh],
                    "plate_type": plate_type,
                }

        return None

    except Exception:
        logger.exception("Plate detection failed for bbox %s", bbox)
        return None


# ---------------------------------------------------------------------------
# Main analysis function
# ---------------------------------------------------------------------------


def analyze_vehicles(frame: np.ndarray, detections: dict) -> dict:
    """Detailed analysis of each detected vehicle.

    Combines per-vehicle color, size, and plate detection with aggregate
    statistics like color distribution and inter-vehicle spacing.

    Args:
        frame: BGR numpy array (the full camera frame).
        detections: dict from detector.py with keys:
            - "detections": [{"class": "car", "confidence": 0.85,
                              "bbox": [x1, y1, x2, y2]}, ...]
            - "counts": {"car": N, ...}

    Returns:
        {
            "vehicles": [per-vehicle detail dicts],
            "color_distribution": {"white": 3, "black": 2, ...},
            "spacing": spacing analysis dict,
            "total_analyzed": int,
        }
    """
    try:
        return _analyze_vehicles_inner(frame, detections)
    except Exception:
        logger.exception("Vehicle analysis failed, returning empty result")
        return _empty_result()


def _analyze_vehicles_inner(frame: np.ndarray, detections: dict) -> dict:
    """Inner implementation of analyze_vehicles (unwrapped from try/except)."""
    det_list = detections.get("detections", [])

    vehicles_detail = []
    color_distribution: dict[str, int] = {}

    for det in det_list:
        if det.get("class") not in _VEHICLE_CLASSES:
            continue

        bbox = det.get("bbox")
        if not bbox or len(bbox) != 4:
            logger.debug("Skipping detection with invalid bbox: %s", det)
            continue

        size = _estimate_vehicle_size(bbox, frame.shape)

        vehicles_detail.append({
            "class": det["class"],
            "confidence": det.get("confidence", 0.0),
            "bbox": bbox,
            "size": size,
        })

    spacing = _compute_vehicle_spacing(det_list)

    return {
        "vehicles": vehicles_detail,
        "spacing": spacing,
        "total_analyzed": len(vehicles_detail),
    }


def _empty_result() -> dict:
    """Return a safe empty result for when analysis fails."""
    return {
        "vehicles": [],
        "color_distribution": {},
        "spacing": _default_spacing("single"),
        "total_analyzed": 0,
    }
