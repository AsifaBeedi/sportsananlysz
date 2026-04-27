from __future__ import annotations

from math import atan2, degrees
from typing import Any

import cv2
import numpy as np


class RacketTracker:
    def __init__(self, sport: str) -> None:
        self.sport = sport
        self.path_history: dict[int, list[dict[str, Any]]] = {}
        self.equipment_name = equipment_name_for_sport(sport)
        self.proxy_mode = proxy_mode_for_sport(sport)

    def update(
        self,
        players: list[dict[str, Any]],
        event_summary: dict[str, Any],
        annotated_frame: np.ndarray,
        frame_index: int,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        primary_player_id = event_summary.get("primary_player_id")
        active_track_ids: list[int] = []
        latest_primary_state: dict[str, Any] | None = None

        for player in players:
            track_id = player["track_id"]
            if track_id != primary_player_id or player.get("pose") is None:
                player["racket"] = {
                    "active": False,
                    "equipment_name": self.equipment_name,
                    "proxy_mode": self.proxy_mode,
                    "proxy_side": None,
                    "handle_point": None,
                    "tip_point": None,
                    "angle_deg": None,
                    "path_history": [],
                    "path_length_px": 0.0,
                    "swing_direction": None,
                    "stroke_plane": None,
                    "shot_label_candidate": player.get("event_state", {}).get("shot_label_candidate"),
                }
                continue

            racket_state = self._estimate_racket_proxy(player, frame_index)
            if racket_state["active"]:
                active_track_ids.append(track_id)
                self._draw_racket_overlay(annotated_frame, racket_state)
                latest_primary_state = racket_state

            player["racket"] = racket_state

        summary = {
            "sport_mode": self.sport,
            "equipment_name": self.equipment_name,
            "proxy_mode": self.proxy_mode,
            "primary_player_id": primary_player_id,
            "active_track_ids": active_track_ids,
            "active_count": len(active_track_ids),
            "latest_primary_state": latest_primary_state,
            "recent_primary_path": latest_primary_state["path_history"] if latest_primary_state else [],
        }
        return players, summary

    def _estimate_racket_proxy(self, player: dict[str, Any], frame_index: int) -> dict[str, Any]:
        keypoints = player["pose"]["keypoints"]
        shot_label = player.get("event_state", {}).get("shot_label_candidate")
        ball_proximity_px = (player.get("event_state") or {}).get("ball_proximity_px")

        proxy_side = choose_proxy_side(self.sport, keypoints, shot_label)
        if proxy_side is None:
            return {
                "active": False,
                "equipment_name": self.equipment_name,
                "proxy_mode": self.proxy_mode,
                "proxy_side": None,
                "handle_point": None,
                "tip_point": None,
                "angle_deg": None,
                "path_history": [],
                "path_length_px": 0.0,
                "swing_direction": None,
                "stroke_plane": None,
                "shot_label_candidate": shot_label,
            }

        shoulder = to_point(keypoints.get(f"{proxy_side}_shoulder"))
        elbow = to_point(keypoints.get(f"{proxy_side}_elbow"))
        wrist = to_point(keypoints.get(f"{proxy_side}_wrist"))
        if wrist is None:
            return {
                "active": False,
                "equipment_name": self.equipment_name,
                "proxy_mode": self.proxy_mode,
                "proxy_side": proxy_side,
                "handle_point": None,
                "tip_point": None,
                "angle_deg": None,
                "path_history": [],
                "path_length_px": 0.0,
                "swing_direction": None,
                "stroke_plane": None,
                "shot_label_candidate": shot_label,
            }

        base_vector = None
        handle_point = wrist
        if elbow is not None:
            base_vector = np.array([wrist[0] - elbow[0], wrist[1] - elbow[1]], dtype=float)
        elif shoulder is not None:
            base_vector = np.array([wrist[0] - shoulder[0], wrist[1] - shoulder[1]], dtype=float)

        if base_vector is None or np.linalg.norm(base_vector) == 0:
            return {
                "active": False,
                "equipment_name": self.equipment_name,
                "proxy_mode": self.proxy_mode,
                "proxy_side": proxy_side,
                "handle_point": list(map(int, wrist)),
                "tip_point": None,
                "angle_deg": None,
                "path_history": [],
                "path_length_px": 0.0,
                "swing_direction": None,
                "stroke_plane": None,
                "shot_label_candidate": shot_label,
            }

        extension_length = proxy_extension_length(self.sport, player["bbox"], shot_label, ball_proximity_px)
        unit_vector = base_vector / np.linalg.norm(base_vector)
        tip_x = int(round(wrist[0] + (unit_vector[0] * extension_length)))
        tip_y = int(round(wrist[1] + (unit_vector[1] * extension_length)))
        tip_point = (tip_x, tip_y)

        history = self.path_history.setdefault(player["track_id"], [])
        history.append(
            {
                "frame_index": frame_index,
                "tip_point": [tip_x, tip_y],
            }
        )
        if len(history) > 25:
            history.pop(0)

        tip_history = [tuple(sample["tip_point"]) for sample in history]
        angle_deg = round(float(degrees(atan2(-unit_vector[1], unit_vector[0]))), 2)
        path_length_px = round(path_length(tip_history), 2)
        swing_direction = infer_swing_direction(tip_history)
        stroke_plane = classify_stroke_plane(angle_deg)

        return {
            "active": True,
            "equipment_name": self.equipment_name,
            "proxy_mode": self.proxy_mode,
            "proxy_side": proxy_side,
            "handle_point": [int(round(wrist[0])), int(round(wrist[1]))],
            "tip_point": [tip_x, tip_y],
            "angle_deg": angle_deg,
            "path_history": [[point[0], point[1]] for point in tip_history[-12:]],
            "history_samples": history[-12:],
            "path_length_px": path_length_px,
            "swing_direction": swing_direction,
            "stroke_plane": stroke_plane,
            "shot_label_candidate": shot_label,
        }

    def _draw_racket_overlay(self, frame: np.ndarray, racket_state: dict[str, Any]) -> None:
        handle_point = racket_state.get("handle_point")
        tip_point = racket_state.get("tip_point")
        if handle_point is None or tip_point is None:
            return

        handle_tuple = (handle_point[0], handle_point[1])
        tip_tuple = (tip_point[0], tip_point[1])
        cv2.line(frame, handle_tuple, tip_tuple, (255, 0, 255), 3)
        cv2.circle(frame, tip_tuple, 5, (255, 0, 255), -1)

        path_history = racket_state.get("path_history", [])
        for index in range(1, len(path_history)):
            prev_point = tuple(path_history[index - 1])
            current_point = tuple(path_history[index])
            cv2.line(frame, prev_point, current_point, (255, 105, 180), 2)

        cv2.putText(
            frame,
            f"{self.equipment_name.title()}:{racket_state['proxy_side']} {int(racket_state['angle_deg'])}",
            (tip_tuple[0] + 8, tip_tuple[1] - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 0, 255),
            2,
        )


def choose_proxy_side(
    sport: str,
    keypoints: dict[str, dict[str, float] | None],
    shot_label: str | None,
) -> str | None:
    left_shoulder = to_point(keypoints.get("left_shoulder"))
    right_shoulder = to_point(keypoints.get("right_shoulder"))
    left_wrist = to_point(keypoints.get("left_wrist"))
    right_wrist = to_point(keypoints.get("right_wrist"))

    if shot_label == "serve_candidate":
        candidates = []
        if left_wrist is not None:
            candidates.append(("left", left_wrist[1]))
        if right_wrist is not None:
            candidates.append(("right", right_wrist[1]))
        return min(candidates, key=lambda item: item[1])[0] if candidates else None

    if sport in {"volleyball", "basketball"}:
        candidates = []
        if left_wrist is not None:
            candidates.append(("left", left_wrist[1]))
        if right_wrist is not None:
            candidates.append(("right", right_wrist[1]))
        return min(candidates, key=lambda item: item[1])[0] if candidates else None

    if sport == "cricket" and shot_label in {"defensive_block_candidate", "straight_bat_candidate"}:
        candidates = []
        if left_wrist is not None:
            candidates.append(("left", abs(left_wrist[0] - (left_shoulder[0] if left_shoulder else left_wrist[0]))))
        if right_wrist is not None:
            candidates.append(("right", abs(right_wrist[0] - (right_shoulder[0] if right_shoulder else right_wrist[0]))))
        if candidates:
            return max(candidates, key=lambda item: item[1])[0]

    left_extension = distance(left_shoulder, left_wrist)
    right_extension = distance(right_shoulder, right_wrist)
    if left_extension is None and right_extension is None:
        return None
    if right_extension is None:
        return "left"
    if left_extension is None:
        return "right"
    return "left" if left_extension > right_extension else "right"


def to_point(point: dict[str, float] | None) -> tuple[float, float] | None:
    if point is None:
        return None
    return (point["x"], point["y"])


def distance(point_a: tuple[float, float] | None, point_b: tuple[float, float] | None) -> float | None:
    if point_a is None or point_b is None:
        return None
    return float(np.sqrt((point_a[0] - point_b[0]) ** 2 + (point_a[1] - point_b[1]) ** 2))


def path_length(points: list[tuple[int, int]]) -> float:
    if len(points) < 2:
        return 0.0
    total = 0.0
    for index in range(1, len(points)):
        total += float(np.sqrt((points[index][0] - points[index - 1][0]) ** 2 + (points[index][1] - points[index - 1][1]) ** 2))
    return total


def infer_swing_direction(points: list[tuple[int, int]]) -> str | None:
    if len(points) < 3:
        return None
    start_x, start_y = points[0]
    end_x, end_y = points[-1]
    delta_x = end_x - start_x
    delta_y = end_y - start_y

    if abs(delta_x) > abs(delta_y):
        return "left_to_right" if delta_x > 0 else "right_to_left"
    if abs(delta_y) > 6:
        return "upward" if delta_y < 0 else "downward"
    return "compact"


def equipment_name_for_sport(sport: str) -> str:
    mapping = {
        "tennis": "racket",
        "badminton": "racket",
        "table_tennis": "paddle",
        "cricket": "bat",
        "baseball": "bat",
        "hockey": "stick",
        "volleyball": "hands",
        "basketball": "hands",
    }
    return mapping.get(sport, "equipment")


def proxy_mode_for_sport(sport: str) -> str:
    mapping = {
        "tennis": "racket_proxy",
        "badminton": "racket_proxy",
        "table_tennis": "paddle_proxy",
        "cricket": "bat_proxy",
        "baseball": "bat_proxy",
        "hockey": "stick_proxy",
        "volleyball": "hand_proxy",
        "basketball": "hand_proxy",
    }
    return mapping.get(sport, "equipment_proxy")


def proxy_extension_length(
    sport: str,
    bbox: list[int],
    shot_label: str | None,
    ball_proximity_px: float | None,
) -> float:
    player_height = bbox[3] - bbox[1]
    base = max(24.0, player_height * 0.22)
    if sport == "cricket":
        base = max(28.0, player_height * 0.28)
        if shot_label in {"defensive_block_candidate", "straight_bat_candidate"}:
            base *= 1.08
        if ball_proximity_px is not None and ball_proximity_px < 35:
            base *= 1.05
    elif sport == "baseball":
        base = max(26.0, player_height * 0.26)
    elif sport == "hockey":
        base = max(26.0, player_height * 0.24)
    elif sport == "badminton":
        base = max(24.0, player_height * 0.22)
    elif sport == "table_tennis":
        base = max(18.0, player_height * 0.16)
    elif sport == "volleyball":
        base = max(18.0, player_height * 0.18)
    elif sport == "basketball":
        base = max(18.0, player_height * 0.19)
    return float(base)


def classify_stroke_plane(angle_deg: float | None) -> str | None:
    if angle_deg is None:
        return None
    normalized = abs(angle_deg)
    if normalized >= 65:
        return "vertical"
    if normalized >= 25:
        return "diagonal"
    return "horizontal"
