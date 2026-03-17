"""YOLO vehicle detection using ultralytics."""

from ultralytics import YOLO
import numpy as np

# Load model once at module level
model = None

# COCO class IDs we care about
_CLASSES_OF_INTEREST = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}

# Categories we track (used to guarantee all keys exist in counts)
_CATEGORIES = ["car", "truck", "bus", "motorcycle", "person", "bicycle"]


def load_model(model_name: str = "yolov8n.pt"):
    """Load YOLO model. Uses yolov8n (nano) for speed."""
    global model
    model = YOLO(model_name)


def detect(frame: np.ndarray, confidence: float = 0.3) -> dict:
    """
    Run YOLO detection on a frame.

    Returns:
    {
        "detections": [
            {"class": "car", "confidence": 0.85, "bbox": [x1, y1, x2, y2]},
            ...
        ],
        "counts": {
            "car": 5,
            "truck": 2,
            "bus": 0,
            "motorcycle": 1,
            "person": 3,
            "bicycle": 0,
        }
    }
    """
    global model

    # Auto-load if needed
    if model is None:
        try:
            load_model()
        except Exception as e:
            print(f"[detector] Failed to load YOLO model: {e}")
            return _empty_result()

    try:
        results = model.predict(frame, conf=confidence, verbose=False)
    except Exception as e:
        print(f"[detector] Detection failed: {e}")
        return _empty_result()

    detections = []
    counts = {cat: 0 for cat in _CATEGORIES}

    for result in results:
        boxes = result.boxes
        if boxes is None:
            continue

        for i in range(len(boxes)):
            cls_id = int(boxes.cls[i].item())
            if cls_id not in _CLASSES_OF_INTEREST:
                continue

            category = _CLASSES_OF_INTEREST[cls_id]
            conf = round(float(boxes.conf[i].item()), 3)
            bbox = boxes.xyxy[i].tolist()
            bbox = [round(v, 1) for v in bbox]

            detections.append({
                "class": category,
                "confidence": conf,
                "bbox": bbox,
            })
            counts[category] += 1

    return {"detections": detections, "counts": counts}


def _empty_result() -> dict:
    """Return an empty detection result."""
    return {
        "detections": [],
        "counts": {cat: 0 for cat in _CATEGORIES},
    }
