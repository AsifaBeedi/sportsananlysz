from __future__ import annotations

from typing import Any

import numpy as np


class EventEngine:
    def __init__(self, sport: str) -> None:
        self.sport = sport
        self.tennis_engine = TennisEventEngine() if sport == "tennis" else None

    def update(
        self,
        players: list[dict[str, Any]],
        ball_tracking: dict[str, Any],
        frame_index: int,
        fps: float,
        frame_size: dict[str, int],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if self.tennis_engine is None:
            for player in players:
                player["event_state"] = {
                    "swing_phase": "unsupported",
                    "activity_score": 0.0,
                    "ball_proximity_px": None,
                    "shot_label_candidate": None,
                    "contact_candidate": False,
                }
            return players, default_event_summary(frame_index)

        return self.tennis_engine.update(players, ball_tracking, frame_index, fps, frame_size)


class TennisEventEngine:
    def __init__(self) -> None:
        self.player_histories: dict[int, list[dict[str, Any]]] = {}
        self.active_windows: dict[int, dict[str, Any]] = {}
        self.recent_events: list[dict[str, Any]] = []
        self.last_contact_frame_by_player: dict[int, int] = {}

    def update(
        self,
        players: list[dict[str, Any]],
        ball_tracking: dict[str, Any],
        frame_index: int,
        fps: float,
        frame_size: dict[str, int],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        primary_player_id = choose_primary_player(players)
        current_frame_events: list[dict[str, Any]] = []
        active_swing_player_ids: list[int] = []

        for player in players:
            track_id = player["track_id"]
            pose = player.get("pose")
            is_primary_player = track_id == primary_player_id
            if pose is None:
                player["event_state"] = {
                    "swing_phase": "idle",
                    "activity_score": 0.0,
                    "ball_proximity_px": None,
                    "shot_label_candidate": None,
                    "contact_candidate": False,
                }
                continue

            snapshot = build_player_snapshot(player, frame_index)
            history = self.player_histories.setdefault(track_id, [])
            previous_snapshot = history[-1] if history else None
            history.append(snapshot)
            if len(history) > 20:
                history.pop(0)

            activity_score = compute_activity_score(previous_snapshot, snapshot)
            ball_proximity_px = compute_ball_proximity(snapshot, ball_tracking)
            shot_label_candidate = (
                classify_tennis_shot(snapshot, ball_tracking, frame_size) if is_primary_player else None
            )
            contact_candidate = (
                is_contact_candidate(activity_score, ball_proximity_px, ball_tracking, frame_index)
                if is_primary_player
                else False
            )
            swing_phase = (
                self._update_swing_window(
                    track_id,
                    frame_index,
                    fps,
                    activity_score,
                    shot_label_candidate,
                    current_frame_events,
                )
                if is_primary_player
                else "idle"
            )

            if swing_phase != "idle":
                active_swing_player_ids.append(track_id)

            if contact_candidate:
                last_contact_frame = self.last_contact_frame_by_player.get(track_id, -999)
                if frame_index - last_contact_frame >= 10:
                    contact_event = {
                        "event_type": "contact_candidate",
                        "frame_index": frame_index,
                        "timestamp_seconds": round(frame_index / fps, 2) if fps else 0.0,
                        "track_id": track_id,
                        "shot_label": shot_label_candidate,
                        "ball_proximity_px": round(ball_proximity_px, 2) if ball_proximity_px is not None else None,
                        "activity_score": round(activity_score, 2),
                        "primary_player": is_primary_player,
                    }
                    self.recent_events.append(contact_event)
                    current_frame_events.append(contact_event)
                    self.last_contact_frame_by_player[track_id] = frame_index

            player["event_state"] = {
                "swing_phase": swing_phase,
                "activity_score": round(activity_score, 2),
                "ball_proximity_px": round(ball_proximity_px, 2) if ball_proximity_px is not None else None,
                "shot_label_candidate": shot_label_candidate,
                "contact_candidate": contact_candidate,
                "primary_player": is_primary_player,
            }

        self.recent_events = self.recent_events[-12:]
        return players, {
            "sport_mode": "tennis",
            "primary_player_id": primary_player_id,
            "active_swing_player_ids": active_swing_player_ids,
            "active_swing_count": len(active_swing_player_ids),
            "current_frame_events": current_frame_events,
            "recent_events": self.recent_events[-8:],
            "recent_event_count": len(self.recent_events[-8:]),
            "contact_candidate_count": sum(
                1 for event in self.recent_events[-8:] if event["event_type"] == "contact_candidate"
            ),
        }

    def _update_swing_window(
        self,
        track_id: int,
        frame_index: int,
        fps: float,
        activity_score: float,
        shot_label_candidate: str | None,
        current_frame_events: list[dict[str, Any]],
    ) -> str:
        threshold_prepare = 10.0
        threshold_active = 18.0
        active_window = self.active_windows.get(track_id)

        if activity_score >= threshold_prepare:
            if active_window is None:
                active_window = {
                    "start_frame": frame_index,
                    "last_active_frame": frame_index,
                    "peak_activity_score": activity_score,
                    "shot_label_candidate": shot_label_candidate,
                }
                self.active_windows[track_id] = active_window
            else:
                active_window["last_active_frame"] = frame_index
                active_window["peak_activity_score"] = max(active_window["peak_activity_score"], activity_score)
                if shot_label_candidate is not None:
                    active_window["shot_label_candidate"] = shot_label_candidate

            return "active_swing" if activity_score >= threshold_active else "preparation"

        if active_window is not None:
            if frame_index - active_window["last_active_frame"] <= 3:
                return "follow_through"

            swing_event = {
                "event_type": "swing_window",
                "frame_index": active_window["last_active_frame"],
                "timestamp_seconds": round(active_window["last_active_frame"] / fps, 2) if fps else 0.0,
                "track_id": track_id,
                "shot_label": active_window["shot_label_candidate"],
                "start_frame": active_window["start_frame"],
                "end_frame": active_window["last_active_frame"],
                "duration_frames": active_window["last_active_frame"] - active_window["start_frame"] + 1,
                "peak_activity_score": round(active_window["peak_activity_score"], 2),
            }
            self.recent_events.append(swing_event)
            current_frame_events.append(swing_event)
            del self.active_windows[track_id]

        return "idle"


def build_player_snapshot(player: dict[str, Any], frame_index: int) -> dict[str, Any]:
    pose = player.get("pose", {})
    keypoints = pose.get("keypoints", {})
    left_wrist = keypoints.get("left_wrist")
    right_wrist = keypoints.get("right_wrist")
    left_shoulder = keypoints.get("left_shoulder")
    right_shoulder = keypoints.get("right_shoulder")
    left_hip = keypoints.get("left_hip")
    right_hip = keypoints.get("right_hip")
    angles_deg = pose.get("angles_deg", {})
    posture = pose.get("posture", {})

    return {
        "frame_index": frame_index,
        "track_id": player["track_id"],
        "center": player["center"],
        "bbox": player["bbox"],
        "left_wrist": to_point(left_wrist),
        "right_wrist": to_point(right_wrist),
        "shoulder_mid": midpoint(left_shoulder, right_shoulder),
        "hip_mid": midpoint(left_hip, right_hip),
        "avg_elbow_deg": average_defined(angles_deg.get("left_elbow_deg"), angles_deg.get("right_elbow_deg")),
        "posture_score": posture.get("posture_score"),
    }


def compute_activity_score(previous: dict[str, Any] | None, current: dict[str, Any]) -> float:
    if previous is None:
        return 0.0

    left_wrist_delta = distance_or_zero(previous.get("left_wrist"), current.get("left_wrist"))
    right_wrist_delta = distance_or_zero(previous.get("right_wrist"), current.get("right_wrist"))
    center_delta = distance_or_zero(previous.get("center"), current.get("center"))
    elbow_delta = abs((current.get("avg_elbow_deg") or 0.0) - (previous.get("avg_elbow_deg") or 0.0))

    wrist_activity = max(left_wrist_delta, right_wrist_delta)
    score = wrist_activity + (0.6 * center_delta) + (0.4 * elbow_delta)
    return round(float(score), 2)


def compute_ball_proximity(snapshot: dict[str, Any], ball_tracking: dict[str, Any]) -> float | None:
    ball_center = ball_tracking.get("smoothed_center")
    if ball_center is None:
        return None

    candidate_points = [
        snapshot.get("left_wrist"),
        snapshot.get("right_wrist"),
        snapshot.get("center"),
        snapshot.get("shoulder_mid"),
    ]
    distances = [
        euclidean_distance(ball_center, point)
        for point in candidate_points
        if point is not None
    ]
    return round(min(distances), 2) if distances else None


def is_contact_candidate(
    activity_score: float,
    ball_proximity_px: float | None,
    ball_tracking: dict[str, Any],
    frame_index: int,
) -> bool:
    if ball_proximity_px is None or ball_proximity_px > 55:
        return False

    if activity_score < 10:
        return False

    latest_direction_change = ball_tracking.get("latest_direction_change")
    if latest_direction_change is None:
        return True

    return abs(frame_index - latest_direction_change["frame_index"]) <= 2


def classify_tennis_shot(
    snapshot: dict[str, Any],
    ball_tracking: dict[str, Any],
    frame_size: dict[str, int],
) -> str | None:
    ball_center = ball_tracking.get("smoothed_center")
    if ball_center is None:
        return None

    shoulder_mid = snapshot.get("shoulder_mid")
    hip_mid = snapshot.get("hip_mid")
    left_wrist = snapshot.get("left_wrist")
    right_wrist = snapshot.get("right_wrist")
    if shoulder_mid is None or hip_mid is None:
        return None

    ball_x, ball_y = ball_center
    frame_height = frame_size["height"]
    player_center_y = snapshot["center"][1]

    hitting_side = nearest_side(ball_center, left_wrist, right_wrist)
    if ball_y < shoulder_mid[1]:
        return "serve_candidate"
    if player_center_y < frame_height * 0.45:
        return "volley_candidate"
    if hitting_side == "right":
        return "forehand_candidate"
    if hitting_side == "left":
        return "backhand_candidate"
    return None


def choose_primary_player(players: list[dict[str, Any]]) -> int | None:
    candidates = [player for player in players if player.get("pose") is not None]
    if not candidates:
        candidates = players
    if not candidates:
        return None

    primary = max(
        candidates,
        key=lambda player: bbox_area(player["bbox"]) + (player["center"][1] * 10),
    )
    return primary["track_id"]


def default_event_summary(frame_index: int) -> dict[str, Any]:
    return {
        "sport_mode": "generic",
        "primary_player_id": None,
        "active_swing_player_ids": [],
        "active_swing_count": 0,
        "current_frame_events": [],
        "recent_events": [],
        "recent_event_count": 0,
        "contact_candidate_count": 0,
    }


def to_point(point: dict[str, float] | None) -> tuple[float, float] | None:
    if point is None:
        return None
    return (point["x"], point["y"])


def midpoint(
    left_point: dict[str, float] | None,
    right_point: dict[str, float] | None,
) -> tuple[float, float] | None:
    if left_point is None or right_point is None:
        return None
    return ((left_point["x"] + right_point["x"]) / 2, (left_point["y"] + right_point["y"]) / 2)


def nearest_side(
    ball_center: list[int],
    left_wrist: tuple[float, float] | None,
    right_wrist: tuple[float, float] | None,
) -> str | None:
    left_distance = euclidean_distance(ball_center, left_wrist) if left_wrist is not None else None
    right_distance = euclidean_distance(ball_center, right_wrist) if right_wrist is not None else None

    if left_distance is None and right_distance is None:
        return None
    if right_distance is None:
        return "left"
    if left_distance is None:
        return "right"
    return "left" if left_distance < right_distance else "right"


def bbox_area(bbox: list[int]) -> int:
    return max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1])


def average_defined(*values: float | None) -> float | None:
    defined = [value for value in values if value is not None]
    if not defined:
        return None
    return round(sum(defined) / len(defined), 2)


def distance_or_zero(point_a: list[int] | tuple[float, float] | None, point_b: list[int] | tuple[float, float] | None) -> float:
    if point_a is None or point_b is None:
        return 0.0
    return euclidean_distance(point_a, point_b)


def euclidean_distance(point_a: list[int] | tuple[float, float], point_b: list[int] | tuple[float, float]) -> float:
    return float(np.sqrt((point_a[0] - point_b[0]) ** 2 + (point_a[1] - point_b[1]) ** 2))
