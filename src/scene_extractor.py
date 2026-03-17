"""
Scene extraction module — extracts everything possible from border crossing
camera frames using pure OpenCV. Complements YOLO vehicle detection with
road condition, light detection, image quality, booth counting, traffic
density, brightness zones, and dominant colors.
"""

import logging
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Road surface condition
# ---------------------------------------------------------------------------

def _analyze_road_surface(frame: np.ndarray) -> str:
    """
    Analyze the bottom 40% of the frame (road area) to estimate surface
    condition based on brightness, reflection variance, and saturation.

    Returns: "dry", "wet", "snow", or "unknown"
    """
    try:
        h, w = frame.shape[:2]
        road_region = frame[int(h * 0.6):, :]
        hsv = cv2.cvtColor(road_region, cv2.COLOR_BGR2HSV)
        v = hsv[:, :, 2]

        brightness = float(np.mean(v))
        saturation = float(np.mean(hsv[:, :, 1]))

        # Check for reflections by looking at brightness variance across
        # horizontal strips — wet roads create specular highlights that
        # cause large swings in mean brightness from strip to strip.
        strip_height = 20
        strip_means = [
            float(np.mean(v[i : i + strip_height, :]))
            for i in range(0, v.shape[0] - strip_height, strip_height)
        ]
        reflection_var = float(np.var(strip_means)) if strip_means else 0.0

        # Snow / ice: very bright, almost no color
        if brightness > 200 and saturation < 30:
            return "snow"

        # Wet: high variance across strips OR generally bright with high
        # per-pixel brightness spread (reflections)
        if reflection_var > 500 or (brightness > 100 and float(np.std(v)) > 60):
            return "wet"

        return "dry"

    except Exception:
        logger.exception("Road surface analysis failed")
        return "unknown"


# ---------------------------------------------------------------------------
# 2. Headlight / taillight detection
# ---------------------------------------------------------------------------

def _detect_lights(frame: np.ndarray) -> dict:
    """
    Detect headlight and taillight blobs in the frame.

    Headlights: very bright (V > 240), low saturation (S < 60) — white/yellow.
    Taillights: red hue (H < 10 or H > 170), medium+ brightness (V > 150),
                high saturation (S > 100).

    Returns:
        {"headlight_count": int, "taillight_count": int, "lights_detected": bool}
    """
    default = {"headlight_count": 0, "taillight_count": 0, "lights_detected": False}

    try:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        h_ch, s_ch, v_ch = cv2.split(hsv)

        # --- Headlights: bright, desaturated blobs ---
        head_mask = cv2.inRange(hsv, np.array([0, 0, 240]), np.array([180, 60, 255]))
        head_mask = cv2.morphologyEx(
            head_mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        )
        head_contours, _ = cv2.findContours(head_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Filter: keep small, compact contours (area 20–3000 px)
        headlight_blobs = [
            c for c in head_contours
            if 20 <= cv2.contourArea(c) <= 3000
        ]

        # --- Taillights: red hue, saturated, reasonably bright ---
        red_low1 = cv2.inRange(hsv, np.array([0, 100, 150]), np.array([10, 255, 255]))
        red_low2 = cv2.inRange(hsv, np.array([170, 100, 150]), np.array([180, 255, 255]))
        tail_mask = cv2.bitwise_or(red_low1, red_low2)
        tail_mask = cv2.morphologyEx(
            tail_mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        )
        tail_contours, _ = cv2.findContours(tail_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        taillight_blobs = [
            c for c in tail_contours
            if 20 <= cv2.contourArea(c) <= 3000
        ]

        # Rough pair estimate: lights usually come in pairs
        headlight_count = max(1, len(headlight_blobs)) // 2
        taillight_count = max(1, len(taillight_blobs)) // 2

        # If we found zero blobs, counts should genuinely be 0
        if len(headlight_blobs) == 0:
            headlight_count = 0
        if len(taillight_blobs) == 0:
            taillight_count = 0

        return {
            "headlight_count": headlight_count,
            "taillight_count": taillight_count,
            "lights_detected": (headlight_count + taillight_count) > 0,
        }

    except Exception:
        logger.exception("Light detection failed")
        return default


# ---------------------------------------------------------------------------
# 3. Image quality metrics
# ---------------------------------------------------------------------------

def _assess_image_quality(frame: np.ndarray) -> dict:
    """
    Compute sharpness, brightness, contrast, noise, and a composite quality
    score.  ``is_reliable`` indicates whether YOLO detections from this
    frame should be trusted.

    Returns:
        {
            "sharpness": float,
            "brightness": float,      # 0-255
            "contrast": float,
            "noise_level": float,
            "quality_score": float,    # 0-1
            "is_reliable": bool,       # quality_score > 0.3
        }
    """
    default: dict[str, Any] = {
        "sharpness": 0.0,
        "brightness": 0.0,
        "contrast": 0.0,
        "noise_level": 0.0,
        "quality_score": 0.0,
        "is_reliable": False,
    }

    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Sharpness — Laplacian variance (higher = sharper)
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # Brightness
        brightness = float(np.mean(gray))

        # Contrast — standard deviation of pixel intensities
        contrast = float(np.std(gray))

        # Noise estimate — high-frequency residual after Gaussian blur
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        diff = cv2.absdiff(gray, blurred)
        noise_level = float(np.mean(diff))

        # --- Composite quality score (0–1) ---
        # Sharpness: typical range ~10–2000+; map [0, 500] -> [0, 1]
        s_norm = min(sharpness / 500.0, 1.0)

        # Brightness: ideal around 100-160; penalize extremes
        if brightness < 20 or brightness > 245:
            b_norm = 0.0
        elif 80 <= brightness <= 180:
            b_norm = 1.0
        else:
            # Linear ramp in 20-80 and 180-245
            if brightness < 80:
                b_norm = (brightness - 20) / 60.0
            else:
                b_norm = (245 - brightness) / 65.0

        # Contrast: typical range 20-80; map [0, 60] -> [0, 1]
        c_norm = min(contrast / 60.0, 1.0)

        # Noise: lower is better; map [0, 20] -> [1, 0]
        n_norm = max(1.0 - noise_level / 20.0, 0.0)

        quality_score = round((s_norm + b_norm + c_norm + n_norm) / 4.0, 3)

        return {
            "sharpness": round(sharpness, 2),
            "brightness": round(brightness, 2),
            "contrast": round(contrast, 2),
            "noise_level": round(noise_level, 2),
            "quality_score": quality_score,
            "is_reliable": quality_score > 0.3,
        }

    except Exception:
        logger.exception("Image quality assessment failed")
        return default


# ---------------------------------------------------------------------------
# 4. Active booth / lane detection
# ---------------------------------------------------------------------------

def _detect_active_booths(frame: np.ndarray) -> dict:
    """
    Look for brightly-lit vertical rectangles in the middle band of the
    frame (30%-60% height) — border control booths usually have overhead
    lighting that makes them stand out.

    Returns:
        {"estimated_active_booths": int, "booth_regions": list[list[int]]}
    """
    default: dict[str, Any] = {"estimated_active_booths": 0, "booth_regions": []}

    try:
        h, w = frame.shape[:2]
        y_start = int(h * 0.3)
        y_end = int(h * 0.6)
        middle_band = frame[y_start:y_end, :]

        gray = cv2.cvtColor(middle_band, cv2.COLOR_BGR2GRAY)

        # Threshold to isolate bright regions (booths are lit up)
        _, bright_mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

        # Morphological close to merge nearby bright pixels into blocks
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 15))
        bright_mask = cv2.morphologyEx(bright_mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(bright_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        booth_regions: list[list[int]] = []
        band_height = y_end - y_start
        min_area = band_height * 10  # at least ~10px wide

        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            area = cw * ch
            if area < min_area:
                continue

            aspect_ratio = ch / cw if cw > 0 else 0

            # Booths are taller than wide (aspect > 1.0) or at least
            # reasonably sized rectangles
            if aspect_ratio >= 0.8 and ch > band_height * 0.3:
                # Map back to full-frame coordinates
                booth_regions.append([x, y + y_start, x + cw, y + y_start + ch])

        return {
            "estimated_active_booths": len(booth_regions),
            "booth_regions": booth_regions,
        }

    except Exception:
        logger.exception("Booth detection failed")
        return default


# ---------------------------------------------------------------------------
# 5. Traffic density
# ---------------------------------------------------------------------------

def _compute_traffic_density(frame: np.ndarray, detections: dict) -> dict:
    """
    Compute how much of the frame is covered by detected vehicles.

    Returns:
        {
            "vehicles_per_1000px2": float,
            "frame_coverage_pct": float,
            "density_level": str,  # empty / light / moderate / heavy / gridlock
        }
    """
    default: dict[str, Any] = {
        "vehicles_per_1000px2": 0.0,
        "frame_coverage_pct": 0.0,
        "density_level": "empty",
    }

    try:
        h, w = frame.shape[:2]
        frame_area = h * w
        if frame_area == 0:
            return default

        # Vehicle classes (excluding person/bicycle for density)
        vehicle_classes = {"car", "truck", "bus", "motorcycle"}

        bbox_area_sum = 0.0
        vehicle_count = 0

        for det in detections.get("detections", []):
            if det.get("class") not in vehicle_classes:
                continue
            bbox = det.get("bbox", [])
            if len(bbox) != 4:
                continue
            x1, y1, x2, y2 = bbox
            bbox_area_sum += max(0.0, (x2 - x1) * (y2 - y1))
            vehicle_count += 1

        coverage_pct = round((bbox_area_sum / frame_area) * 100, 2)
        vehicles_per_1000 = round((bbox_area_sum / frame_area) * 1000, 3)

        if coverage_pct < 1:
            level = "empty"
        elif coverage_pct < 5:
            level = "light"
        elif coverage_pct < 15:
            level = "moderate"
        elif coverage_pct < 30:
            level = "heavy"
        else:
            level = "gridlock"

        return {
            "vehicles_per_1000px2": vehicles_per_1000,
            "frame_coverage_pct": coverage_pct,
            "density_level": level,
        }

    except Exception:
        logger.exception("Traffic density computation failed")
        return default


# ---------------------------------------------------------------------------
# 6. Brightness zones (3x3 grid)
# ---------------------------------------------------------------------------

def _brightness_zones(frame: np.ndarray) -> list[list[float]]:
    """
    Divide the frame into a 3x3 grid and return the mean brightness of
    each cell.  Useful for understanding layout (sky vs road vs structures).

    Returns a 3x3 list of floats (row-major).
    """
    default = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]

    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]

        rows = 3
        cols = 3
        grid: list[list[float]] = []

        for r in range(rows):
            row_vals: list[float] = []
            y_start = int(h * r / rows)
            y_end = int(h * (r + 1) / rows)
            for c in range(cols):
                x_start = int(w * c / cols)
                x_end = int(w * (c + 1) / cols)
                cell = gray[y_start:y_end, x_start:x_end]
                row_vals.append(round(float(np.mean(cell)), 1))
            grid.append(row_vals)

        return grid

    except Exception:
        logger.exception("Brightness zone computation failed")
        return default


# ---------------------------------------------------------------------------
# 7. Dominant colors (k-means)
# ---------------------------------------------------------------------------

def _dominant_colors(frame: np.ndarray, k: int = 3) -> list[dict]:
    """
    Find the top *k* dominant colors in the frame using OpenCV k-means on
    a downsampled version of the image.

    Returns:
        [{"rgb": [r, g, b], "percentage": float}, ...]
        sorted by descending percentage.
    """
    default: list[dict] = []

    try:
        # Downsample for speed — resize to max 100px on the long side
        h, w = frame.shape[:2]
        scale = 100.0 / max(h, w)
        small = cv2.resize(frame, (max(1, int(w * scale)), max(1, int(h * scale))))

        # Reshape to (N, 3) float32 array
        pixels = small.reshape(-1, 3).astype(np.float32)

        if pixels.shape[0] < k:
            return default

        # cv2.kmeans criteria: stop after 10 iterations or epsilon 1.0
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, labels, centers = cv2.kmeans(
            pixels, k, None, criteria, attempts=3, flags=cv2.KMEANS_PP_CENTERS
        )

        # Count pixels per cluster
        label_counts = np.bincount(labels.flatten(), minlength=k)
        total = label_counts.sum()
        if total == 0:
            return default

        results = []
        for i in range(k):
            bgr = centers[i]
            # Convert BGR -> RGB
            rgb = [int(round(bgr[2])), int(round(bgr[1])), int(round(bgr[0]))]
            pct = round(float(label_counts[i]) / total, 3)
            results.append({"rgb": rgb, "percentage": pct})

        # Sort by percentage descending
        results.sort(key=lambda x: x["percentage"], reverse=True)
        return results

    except Exception:
        logger.exception("Dominant color extraction failed")
        return default


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def extract_scene_info(frame: np.ndarray, detections: dict) -> dict:
    """
    Deep scene analysis extracting everything possible from the frame.

    Args:
        frame: BGR numpy array from camera.
        detections: dict from detector.py with "detections" and "counts" keys.
            Each detection has:
                {"class": "car", "confidence": 0.85, "bbox": [x1, y1, x2, y2]}

    Returns:
        Dict with keys: road_condition, headlights, image_quality, booths,
        traffic_density, brightness_zones, dominant_colors.
    """
    if frame is None or frame.size == 0:
        logger.warning("extract_scene_info called with empty frame")
        return {
            "road_condition": "unknown",
            "headlights": {
                "headlight_count": 0,
                "taillight_count": 0,
                "lights_detected": False,
            },
            "image_quality": {
                "sharpness": 0.0,
                "brightness": 0.0,
                "contrast": 0.0,
                "noise_level": 0.0,
                "quality_score": 0.0,
                "is_reliable": False,
            },
            "booths": {"estimated_active_booths": 0, "booth_regions": []},
            "traffic_density": {
                "vehicles_per_1000px2": 0.0,
                "frame_coverage_pct": 0.0,
                "density_level": "empty",
            },
            "brightness_zones": [
                [0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0],
                [0.0, 0.0, 0.0],
            ],
            "dominant_colors": [],
        }

    if detections is None:
        detections = {"detections": [], "counts": {}}

    return {
        "road_condition": _analyze_road_surface(frame),
        "headlights": _detect_lights(frame),
        "image_quality": _assess_image_quality(frame),
        "booths": _detect_active_booths(frame),
        "traffic_density": _compute_traffic_density(frame, detections),
        "brightness_zones": _brightness_zones(frame),
        "dominant_colors": _dominant_colors(frame),
    }
