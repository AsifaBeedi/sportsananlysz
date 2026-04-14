from __future__ import annotations

from typing import Any

import cv2
import numpy as np


KEYPOINT_NAMES = (
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
)

SKELETON_EDGES = (
    ("left_shoulder", "right_shoulder"),
    ("left_shoulder", "left_elbow"),
    ("left_elbow", "left_wrist"),
    ("right_shoulder", "right_elbow"),
    ("right_elbow", "right_wrist"),
    ("left_shoulder", "left_hip"),
    ("right_shoulder", "right_hip"),
    ("left_hip", "right_hip"),
    ("left_hip", "left_knee"),
    ("left_knee", "left_ankle"),
    ("right_hip", "right_knee"),
    ("right_knee", "right_ankle"),
)


def extract_pose_detections(results: list[Any], *, keypoint_confidence: float) -> list[dict[str, Any]]:
    detections: list[dict[str, Any]] = []
    if not results or results[0].boxes is None or results[0].keypoints is None:
        return detections

    boxes = results[0].boxes.xyxy.cpu().numpy()
    confidences = results[0].boxes.conf.cpu().numpy()
    keypoints_xy = results[0].keypoints.xy.cpu().numpy()
    keypoints_conf = results[0].keypoints.conf
    keypoints_conf_array = keypoints_conf.cpu().numpy() if keypoints_conf is not None else None

    for index, box in enumerate(boxes):
        x1, y1, x2, y2 = map(int, box)
        center_x = int((x1 + x2) / 2)
        center_y = int((y1 + y2) / 2)
        named_keypoints: dict[str, dict[str, float] | None] = {}

        for point_index, name in enumerate(KEYPOINT_NAMES):
            point_x, point_y = keypoints_xy[index][point_index]
            confidence = (
                float(keypoints_conf_array[index][point_index])
                if keypoints_conf_array is not None
                else 1.0
            )
            if confidence < keypoint_confidence:
                named_keypoints[name] = None
                continue

            named_keypoints[name] = {
                "x": round(float(point_x), 2),
                "y": round(float(point_y), 2),
                "confidence": round(confidence, 4),
            }

        detections.append(
            {
                "bbox": [x1, y1, x2, y2],
                "center": [center_x, center_y],
                "confidence": round(float(confidences[index]), 4),
                "keypoints": named_keypoints,
            }
        )

    return detections


def match_pose_detections_to_players(
    players: list[dict[str, Any]],
    pose_detections: list[dict[str, Any]],
) -> dict[int, int]:
    matches: dict[int, int] = {}
    unused_pose_indexes = set(range(len(pose_detections)))

    ranked_pairs: list[tuple[float, float, int, int]] = []
    for player_index, player in enumerate(players):
        for pose_index, pose in enumerate(pose_detections):
            iou = bbox_iou(player["bbox"], pose["bbox"])
            distance = center_distance(player["center"], pose["center"])
            ranked_pairs.append((-iou, distance, player_index, pose_index))

    ranked_pairs.sort()
    for negative_iou, distance, player_index, pose_index in ranked_pairs:
        if player_index in matches or pose_index not in unused_pose_indexes:
            continue

        iou = -negative_iou
        if iou < 0.05 and distance > 120:
            continue

        matches[player_index] = pose_index
        unused_pose_indexes.remove(pose_index)

    return matches


def build_pose_metrics(keypoints: dict[str, dict[str, float] | None]) -> dict[str, float | None]:
    left_elbow = angle_from_names(keypoints, "left_shoulder", "left_elbow", "left_wrist")
    right_elbow = angle_from_names(keypoints, "right_shoulder", "right_elbow", "right_wrist")
    left_knee = angle_from_names(keypoints, "left_hip", "left_knee", "left_ankle")
    right_knee = angle_from_names(keypoints, "right_hip", "right_knee", "right_ankle")
    left_hip = angle_from_names(keypoints, "left_shoulder", "left_hip", "left_knee")
    right_hip = angle_from_names(keypoints, "right_shoulder", "right_hip", "right_knee")
    trunk_lean = trunk_lean_degrees(keypoints)

    return {
        "left_elbow_deg": left_elbow,
        "right_elbow_deg": right_elbow,
        "left_knee_deg": left_knee,
        "right_knee_deg": right_knee,
        "left_hip_deg": left_hip,
        "right_hip_deg": right_hip,
        "trunk_lean_deg": trunk_lean,
    }


def draw_pose_overlay(frame: np.ndarray, keypoints: dict[str, dict[str, float] | None]) -> None:
    for start_name, end_name in SKELETON_EDGES:
        start_point = keypoints.get(start_name)
        end_point = keypoints.get(end_name)
        if start_point is None or end_point is None:
            continue
        cv2.line(
            frame,
            (int(start_point["x"]), int(start_point["y"])),
            (int(end_point["x"]), int(end_point["y"])),
            (0, 255, 255),
            2,
        )

    for point in keypoints.values():
        if point is None:
            continue
        cv2.circle(frame, (int(point["x"]), int(point["y"])), 3, (0, 255, 0), -1)


def bbox_iou(box_a: list[int], box_b: list[int]) -> float:
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_width = max(0, inter_x2 - inter_x1)
    inter_height = max(0, inter_y2 - inter_y1)
    intersection = inter_width * inter_height
    if intersection == 0:
        return 0.0

    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = area_a + area_b - intersection
    return float(intersection / union) if union else 0.0


def center_distance(center_a: list[int], center_b: list[int]) -> float:
    return float(np.sqrt((center_a[0] - center_b[0]) ** 2 + (center_a[1] - center_b[1]) ** 2))


def angle_from_names(
    keypoints: dict[str, dict[str, float] | None],
    name_a: str,
    name_b: str,
    name_c: str,
) -> float | None:
    point_a = keypoints.get(name_a)
    point_b = keypoints.get(name_b)
    point_c = keypoints.get(name_c)
    if point_a is None or point_b is None or point_c is None:
        return None

    return compute_angle(
        (point_a["x"], point_a["y"]),
        (point_b["x"], point_b["y"]),
        (point_c["x"], point_c["y"]),
    )


def compute_angle(
    point_a: tuple[float, float],
    point_b: tuple[float, float],
    point_c: tuple[float, float],
) -> float | None:
    vector_ab = np.array(point_a) - np.array(point_b)
    vector_cb = np.array(point_c) - np.array(point_b)
    norm_ab = np.linalg.norm(vector_ab)
    norm_cb = np.linalg.norm(vector_cb)
    if norm_ab == 0 or norm_cb == 0:
        return None

    cosine = np.dot(vector_ab, vector_cb) / (norm_ab * norm_cb)
    cosine = np.clip(cosine, -1.0, 1.0)
    angle = np.degrees(np.arccos(cosine))
    return round(float(angle), 2)


def trunk_lean_degrees(keypoints: dict[str, dict[str, float] | None]) -> float | None:
    left_shoulder = keypoints.get("left_shoulder")
    right_shoulder = keypoints.get("right_shoulder")
    left_hip = keypoints.get("left_hip")
    right_hip = keypoints.get("right_hip")
    if not all((left_shoulder, right_shoulder, left_hip, right_hip)):
        return None

    shoulder_mid = np.array(
        [
            (left_shoulder["x"] + right_shoulder["x"]) / 2,
            (left_shoulder["y"] + right_shoulder["y"]) / 2,
        ]
    )
    hip_mid = np.array(
        [
            (left_hip["x"] + right_hip["x"]) / 2,
            (left_hip["y"] + right_hip["y"]) / 2,
        ]
    )
    torso_vector = shoulder_mid - hip_mid
    vertical_vector = np.array([0.0, -1.0])

    torso_norm = np.linalg.norm(torso_vector)
    if torso_norm == 0:
        return None

    cosine = np.dot(torso_vector, vertical_vector) / (torso_norm * np.linalg.norm(vertical_vector))
    cosine = np.clip(cosine, -1.0, 1.0)
    angle = np.degrees(np.arccos(cosine))
    return round(float(abs(angle)), 2)
