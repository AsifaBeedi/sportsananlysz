from __future__ import annotations

from typing import Any

import cv2
import numpy as np


# Puck contours below this circularity are rejected (elongated noise, player silhouettes).
# 1.0 = perfect circle. 0.3 allows for motion blur and partial occlusion.
_MIN_CIRCULARITY = 0.3

# Player bboxes are expanded by this many pixels before exclusion to avoid treating
# puck-shaped blobs partially overlapping a player body as valid puck candidates.
_PLAYER_BBOX_EXPAND_PX = 14

# Puck candidates beyond this distance from every tracked player are unlikely during
# active play. A large penalty is applied rather than a hard cutoff (puck can be in
# flight briefly far from all players).
_NEAR_PLAYER_BONUS_RADIUS_PX = 180.0

# Score bonus applied when a candidate is very close to the predicted next position.
_CONTINUITY_BONUS_MAX = 15.0

# Hard cutoff: candidates more than this far from the last known position are rejected
# (same as the pipeline's ball_max_tracking_distance_px).
_MAX_TRACKING_DISTANCE_PX = 180.0


class HockeyPuckDetector:
    """
    Frame-differencing puck detector with hockey-specific constraints:
    - Tight area bounds matching real puck pixel sizes
    - Circularity filter to reject elongated noise
    - Expanded player-body exclusion zone
    - Near-player proximity bonus
    - Strong positional continuity preference
    """

    def __init__(self) -> None:
        self.previous_gray: np.ndarray | None = None

    def detect(
        self,
        frame: np.ndarray,
        player_detections: list[dict[str, Any]],
        last_puck_center: tuple[int, int] | None,
    ) -> dict[str, Any] | None:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        previous = self.previous_gray
        self.previous_gray = gray_blurred
        if previous is None:
            return None

        frame_height, frame_width = gray.shape[:2]
        frame_area = frame_width * frame_height

        # Puck-specific area range: smaller minimum, tighter maximum than generic fallback.
        min_area = max(8, int(frame_area * 0.000025))
        max_area = min(350, int(frame_area * 0.0012))
        if max_area <= min_area:
            max_area = min_area + 1

        diff = cv2.absdiff(previous, gray_blurred)
        # Lower diff threshold than generic (20 vs 22) to catch fast-moving small pucks.
        _, thresh = cv2.threshold(diff, 20, 255, cv2.THRESH_BINARY)
        # Single dilate pass — keeps blobs tighter for puck-scale objects.
        thresh = cv2.dilate(thresh, None, iterations=1)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        expanded_bboxes = [
            _expand_bbox(p["bbox"], _PLAYER_BBOX_EXPAND_PX)
            for p in player_detections
        ]

        best_detection: dict[str, Any] | None = None
        best_score = -1.0

        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < min_area or area > max_area:
                continue

            perimeter = float(cv2.arcLength(contour, True))
            circularity = (4.0 * np.pi * area / (perimeter * perimeter)) if perimeter > 0 else 0.0
            if circularity < _MIN_CIRCULARITY:
                continue

            x, y, w, h = cv2.boundingRect(contour)
            cx = int(x + w / 2)
            cy = int(y + h / 2)

            if any(_point_inside_bbox((cx, cy), bbox) for bbox in expanded_bboxes):
                continue

            # Hard distance cutoff when we have a tracked position.
            if last_puck_center is not None:
                dist_to_last = _dist(cx, cy, last_puck_center[0], last_puck_center[1])
                if dist_to_last > _MAX_TRACKING_DISTANCE_PX:
                    continue
                continuity_bonus = max(
                    0.0,
                    _CONTINUITY_BONUS_MAX * (1.0 - dist_to_last / _MAX_TRACKING_DISTANCE_PX),
                )
            else:
                continuity_bonus = 0.0

            # Proximity bonus when puck candidate is near at least one player.
            player_bonus = 0.0
            if player_detections:
                min_player_dist = min(
                    _dist(cx, cy, p["center"][0], p["center"][1])
                    for p in player_detections
                )
                if min_player_dist < _NEAR_PLAYER_BONUS_RADIUS_PX:
                    player_bonus = 5.0 * (1.0 - min_player_dist / _NEAR_PLAYER_BONUS_RADIUS_PX)

            score = circularity * 10.0 + continuity_bonus + player_bonus

            if score > best_score:
                best_score = score
                best_detection = {
                    "bbox": [x, y, x + w, y + h],
                    "center": [cx, cy],
                    "confidence": round(min(0.49, circularity * 0.55), 4),
                    "source": "hockey_puck",
                }

        return best_detection


def _expand_bbox(bbox: list[int], px: int) -> list[int]:
    return [bbox[0] - px, bbox[1] - px, bbox[2] + px, bbox[3] + px]


def _point_inside_bbox(point: tuple[int, int], bbox: list[int]) -> bool:
    x, y = point
    return bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]


def _dist(x1: int | float, y1: int | float, x2: int | float, y2: int | float) -> float:
    return float(np.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2))
