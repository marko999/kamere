"""Vehicle tracking across consecutive frames using the Hungarian algorithm.

Matches YOLO detections from frame T0 to frame T1 for each camera
independently.  Frames are ~30 seconds apart, so vehicles may have moved
significantly — matching relies on centroid distance with an IoU tiebreaker.
"""

import logging
import math

import numpy as np
from scipy.optimize import linear_sum_assignment

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _centroid(bbox: list) -> tuple[float, float]:
    """Return (cx, cy) center of a bounding box [x1, y1, x2, y2]."""
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def _bbox_area(bbox: list) -> float:
    """Return area of a bounding box [x1, y1, x2, y2]."""
    x1, y1, x2, y2 = bbox
    w = max(0.0, x2 - x1)
    h = max(0.0, y2 - y1)
    return w * h


def _iou(bbox1: list, bbox2: list) -> float:
    """Compute Intersection over Union of two bounding boxes."""
    x1 = max(bbox1[0], bbox2[0])
    y1 = max(bbox1[1], bbox2[1])
    x2 = min(bbox1[2], bbox2[2])
    y2 = min(bbox1[3], bbox2[3])

    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    inter_area = inter_w * inter_h

    area1 = _bbox_area(bbox1)
    area2 = _bbox_area(bbox2)
    union = area1 + area2 - inter_area

    if union <= 0:
        return 0.0
    return inter_area / union


# ---------------------------------------------------------------------------
# VehicleTracker
# ---------------------------------------------------------------------------

_UNREACHABLE_COST = 1e6
_DEFAULT_MAX_DISTANCE = 200.0   # pixels
_IOU_WEIGHT = 0.5               # how much (1 - IoU) contributes to cost


class VehicleTracker:
    """Tracks vehicles across frames for each camera independently."""

    def __init__(self, max_distance: float = _DEFAULT_MAX_DISTANCE):
        self._prev: dict[str, list[dict]] = {}
        self._max_distance = max_distance

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, camera_id: str, detections: list[dict]) -> dict:
        """
        Match current detections with previous frame's detections for this
        camera.

        Args:
            camera_id: unique camera identifier.
            detections: list of detection dicts from detector.py, each has
                ``{"class": "car", "confidence": 0.85, "bbox": [x1,y1,x2,y2]}``.

        Returns a dict with keys *matches*, *unmatched_new*, *unmatched_gone*,
        and *has_previous*.
        """
        try:
            return self._update_inner(camera_id, detections)
        except Exception:
            log.exception("tracker: error updating camera %s", camera_id)
            # Safe fallback — treat everything as new, store for next time.
            self._prev[camera_id] = list(detections)
            return {
                "matches": [],
                "unmatched_new": list(detections),
                "unmatched_gone": [],
                "has_previous": False,
            }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _update_inner(self, camera_id: str, detections: list[dict]) -> dict:
        prev = self._prev.get(camera_id)
        has_previous = prev is not None

        # First frame for this camera — nothing to match against.
        if not has_previous:
            self._prev[camera_id] = list(detections)
            return {
                "matches": [],
                "unmatched_new": list(detections),
                "unmatched_gone": [],
                "has_previous": False,
            }

        # Previous exists but one side is empty.
        if len(prev) == 0:
            self._prev[camera_id] = list(detections)
            return {
                "matches": [],
                "unmatched_new": list(detections),
                "unmatched_gone": [],
                "has_previous": True,
            }

        if len(detections) == 0:
            self._prev[camera_id] = []
            return {
                "matches": [],
                "unmatched_new": [],
                "unmatched_gone": list(prev),
                "has_previous": True,
            }

        # ----- Build cost matrix (rows=prev, cols=curr) ----- #
        prev_centroids = [_centroid(d["bbox"]) for d in prev]
        curr_centroids = [_centroid(d["bbox"]) for d in detections]

        n_prev = len(prev)
        n_curr = len(detections)
        cost = np.zeros((n_prev, n_curr), dtype=np.float64)

        for i in range(n_prev):
            for j in range(n_curr):
                px, py = prev_centroids[i]
                cx, cy = curr_centroids[j]
                dist = math.hypot(cx - px, cy - py)

                if dist > self._max_distance:
                    cost[i, j] = _UNREACHABLE_COST
                else:
                    iou_score = _iou(prev[i]["bbox"], detections[j]["bbox"])
                    cost[i, j] = dist + (1.0 - iou_score) * _IOU_WEIGHT * self._max_distance

        # ----- Hungarian assignment ----- #
        row_idx, col_idx = linear_sum_assignment(cost)

        matched_prev: set[int] = set()
        matched_curr: set[int] = set()
        matches: list[dict] = []

        for r, c in zip(row_idx, col_idx):
            if cost[r, c] >= _UNREACHABLE_COST:
                continue  # Too far apart — not a real match.

            p_bbox = prev[r]["bbox"]
            c_bbox = detections[c]["bbox"]
            p_cent = prev_centroids[r]
            c_cent = curr_centroids[c]
            displacement = math.hypot(c_cent[0] - p_cent[0], c_cent[1] - p_cent[1])

            prev_area = _bbox_area(p_bbox)
            curr_area = _bbox_area(c_bbox)
            area_ratio = (curr_area / prev_area) if prev_area > 0 else 0.0

            matches.append({
                "class": detections[c]["class"],
                "prev_bbox": p_bbox,
                "curr_bbox": c_bbox,
                "prev_centroid": p_cent,
                "curr_centroid": c_cent,
                "displacement_px": round(displacement, 1),
                "bbox_area_ratio": round(area_ratio, 3),
            })

            matched_prev.add(r)
            matched_curr.add(c)

        unmatched_new = [detections[j] for j in range(n_curr) if j not in matched_curr]
        unmatched_gone = [prev[i] for i in range(n_prev) if i not in matched_prev]

        log.debug(
            "tracker [%s]: %d matched, %d new, %d gone",
            camera_id, len(matches), len(unmatched_new), len(unmatched_gone),
        )

        # Store current detections as the new previous state.
        self._prev[camera_id] = list(detections)

        return {
            "matches": matches,
            "unmatched_new": unmatched_new,
            "unmatched_gone": unmatched_gone,
            "has_previous": True,
        }
