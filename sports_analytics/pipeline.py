from __future__ import annotations

import os
import time
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from ultralytics import YOLO

from .ball_speed import BallSpeedEstimator
from .config import AppConfig
from .events import EventEngine, default_event_summary
from .impact_power import ImpactPowerEstimator
from .posture import analyze_posture
from .pose import build_pose_metrics, draw_pose_overlay, extract_pose_detections, match_pose_detections_to_players
from .racket import RacketTracker
from .recommendations import generate_recommendations
from .clip_manager import ClipManager
from .session_io import SessionWriter


PERSON_CLASS_ID = 0
BALL_CLASS_ID = 32


@dataclass
class FrameResult:
    annotated_frame: np.ndarray
    payload: dict[str, Any]


class SportsAnalyticsPipeline:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.model = YOLO(str(config.model_path))
        self.pose_model = YOLO(str(config.pose_model_path))
        self.event_engine = EventEngine(config.sport)
        self.racket_tracker = RacketTracker(config.sport)
        self.ball_speed_estimator = BallSpeedEstimator(config.ball_meters_per_pixel)
        self.impact_power_estimator = ImpactPowerEstimator(config.ball_meters_per_pixel)
        self.next_track_id = 1
        self.active_tracks: dict[int, dict[str, Any]] = {}
        self.player_positions: dict[int, tuple[int, int]] = {}
        self.track_history: dict[int, list[tuple[int, int]]] = {}
        self.ball_history: list[dict[str, Any]] = []
        self.ball_direction_change_candidates: list[dict[str, Any]] = []
        self.ball_last_center: tuple[int, int] | None = None
        self.ball_last_bbox: list[int] | None = None
        self.ball_missed_frames = 0

    def process_frame(self, frame: np.ndarray, frame_index: int, fps: float) -> FrameResult:
        results = self.model.predict(
            frame,
            classes=list(self.config.tracked_classes),
            conf=self.config.detection_confidence,
            verbose=False,
        )
        pose_results = self.pose_model.predict(
            frame,
            conf=self.config.pose_detection_confidence,
            verbose=False,
        )

        annotated_frame = frame.copy()
        player_detections: list[dict[str, Any]] = []
        ball_detections: list[dict[str, Any]] = []

        if results and results[0].boxes is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            classes = results[0].boxes.cls.cpu().numpy()
            confidences = results[0].boxes.conf.cpu().numpy()

            for i, box in enumerate(boxes):
                x1, y1, x2, y2 = map(int, box)
                cls = int(classes[i])
                confidence = round(float(confidences[i]), 4)
                center_x = int((x1 + x2) / 2)
                center_y = int((y1 + y2) / 2)

                if cls == BALL_CLASS_ID:
                    ball_detections.append(
                        {
                            "bbox": [x1, y1, x2, y2],
                            "center": [center_x, center_y],
                            "confidence": confidence,
                        }
                    )
                    continue

                if cls != PERSON_CLASS_ID:
                    continue

                player_detections.append(
                    {
                        "bbox": [x1, y1, x2, y2],
                        "center": [center_x, center_y],
                    }
                )

        pose_detections = extract_pose_detections(
            pose_results,
            keypoint_confidence=self.config.keypoint_confidence,
        )
        players = self._build_tracked_players(player_detections, annotated_frame, frame_index)
        players, pose_summary = self._attach_pose_data(players, pose_detections, annotated_frame)
        ball_tracking = self._update_ball_track(ball_detections, annotated_frame, frame_index)
        players, event_summary = self.event_engine.update(
            players,
            ball_tracking,
            frame_index,
            fps,
            {"width": int(frame.shape[1]), "height": int(frame.shape[0])},
        )
        players, racket_summary = self.racket_tracker.update(players, event_summary, annotated_frame, frame_index)
        speed_summary = self.ball_speed_estimator.update(ball_tracking, event_summary, fps)
        impact_power_summary = self.impact_power_estimator.update(racket_summary, speed_summary, event_summary, fps)
        recommendations = generate_recommendations(
            players,
            event_summary,
            racket_summary,
            speed_summary,
            self.config.sport,
        )
        payload = self._build_payload(
            frame,
            frame_index,
            fps,
            players,
            ball_detections,
            ball_tracking,
            pose_detections,
            pose_summary,
            event_summary,
            racket_summary,
            speed_summary,
            impact_power_summary,
            recommendations,
        )
        return FrameResult(annotated_frame=annotated_frame, payload=payload)

    def _build_tracked_players(
        self,
        player_detections: list[dict[str, Any]],
        annotated_frame: np.ndarray,
        frame_index: int,
    ) -> list[dict[str, Any]]:
        players: list[dict[str, Any]] = []
        assignments = self._assign_track_ids(player_detections, frame_index)

        for detection_index, detection in enumerate(player_detections):
            track_id = assignments[detection_index]
            x1, y1, x2, y2 = detection["bbox"]
            center_x, center_y = detection["center"]

            width = x2 - x1
            height = y2 - y1
            speed_px = None
            if track_id in self.player_positions:
                prev_x, prev_y = self.player_positions[track_id]
                distance = np.sqrt((center_x - prev_x) ** 2 + (center_y - prev_y) ** 2)
                speed_px = round(float(distance), 2)

            self.player_positions[track_id] = (center_x, center_y)
            trail = self.track_history.setdefault(track_id, [])
            trail.append((center_x, center_y))
            if len(trail) > 30:
                trail.pop(0)

            fall_candidate = width > height * 1.2
            players.append(
                {
                    "track_id": track_id,
                    "bbox": [x1, y1, x2, y2],
                    "center": [center_x, center_y],
                    "speed_px": speed_px,
                    "fall_candidate": fall_candidate,
                    "trail_length": len(trail),
                    "pose": None,
                    "event_state": None,
                }
            )

            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
            cv2.putText(
                annotated_frame,
                f"ID:{track_id}",
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 0, 0),
                2,
            )

            if speed_px is not None:
                cv2.putText(
                    annotated_frame,
                    f"Speed:{int(speed_px)}",
                    (x1, y2 + 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2,
                )

            if fall_candidate:
                cv2.putText(
                    annotated_frame,
                    "FALL DETECTED",
                    (x1, y1 - 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255),
                    3,
                )

            for j in range(1, len(trail)):
                cv2.line(
                    annotated_frame,
                    trail[j - 1],
                    trail[j],
                    (255, 255, 0),
                    2,
                )

        return players

    def _attach_pose_data(
        self,
        players: list[dict[str, Any]],
        pose_detections: list[dict[str, Any]],
        annotated_frame: np.ndarray,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        matches = match_pose_detections_to_players(players, pose_detections)
        players_with_pose = 0
        trunk_lean_values: list[float] = []
        posture_scores: list[int] = []
        risk_flagged_player_ids: list[int] = []

        for player_index, player in enumerate(players):
            pose_index = matches.get(player_index)
            if pose_index is None:
                continue

            pose_detection = pose_detections[pose_index]
            pose_metrics = build_pose_metrics(pose_detection["keypoints"])
            posture_analysis = analyze_posture(pose_metrics)
            if pose_metrics["trunk_lean_deg"] is not None:
                trunk_lean_values.append(pose_metrics["trunk_lean_deg"])
            posture_scores.append(posture_analysis["posture_score"])
            if posture_analysis["injury_risk_flags"]:
                risk_flagged_player_ids.append(player["track_id"])

            player["pose"] = {
                "confidence": pose_detection["confidence"],
                "bbox": pose_detection["bbox"],
                "keypoints": pose_detection["keypoints"],
                "angles_deg": pose_metrics,
                "posture": posture_analysis,
            }
            players_with_pose += 1
            draw_pose_overlay(annotated_frame, pose_detection["keypoints"])

            trunk_lean_label = pose_metrics["trunk_lean_deg"]
            if trunk_lean_label is not None:
                cv2.putText(
                    annotated_frame,
                    f"Trunk:{int(trunk_lean_label)}",
                    (player["bbox"][0], player["bbox"][1] - 45),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (0, 255, 255),
                    2,
                )

            cv2.putText(
                annotated_frame,
                f"Posture:{posture_analysis['posture_score']}",
                (player["bbox"][0], player["bbox"][1] - 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 255, 0) if posture_analysis["posture_score"] >= 85 else (0, 215, 255),
                2,
            )

        pose_summary = {
            "pose_detections": len(pose_detections),
            "players_with_pose": players_with_pose,
            "matched_player_ids": [players[index]["track_id"] for index in matches],
            "avg_trunk_lean_deg": round(sum(trunk_lean_values) / len(trunk_lean_values), 2)
            if trunk_lean_values
            else None,
            "avg_posture_score": round(sum(posture_scores) / len(posture_scores), 2) if posture_scores else None,
            "injury_risk_player_ids": risk_flagged_player_ids,
            "injury_risk_count": len(risk_flagged_player_ids),
        }
        return players, pose_summary

    def _assign_track_ids(
        self,
        player_detections: list[dict[str, Any]],
        frame_index: int,
    ) -> dict[int, int]:
        assignments: dict[int, int] = {}
        unmatched_detection_indexes = set(range(len(player_detections)))

        for track_id, track_state in list(self.active_tracks.items()):
            if frame_index - track_state["last_seen_frame"] > self.config.max_track_age_frames:
                del self.active_tracks[track_id]
                continue

            best_index = None
            best_distance = self.config.max_tracking_distance_px + 1
            track_center_x, track_center_y = track_state["center"]

            for detection_index in unmatched_detection_indexes:
                detection_center_x, detection_center_y = player_detections[detection_index]["center"]
                distance = float(
                    np.sqrt(
                        (detection_center_x - track_center_x) ** 2
                        + (detection_center_y - track_center_y) ** 2
                    )
                )
                if distance < best_distance:
                    best_distance = distance
                    best_index = detection_index

            if best_index is None or best_distance > self.config.max_tracking_distance_px:
                continue

            assignments[best_index] = track_id
            unmatched_detection_indexes.remove(best_index)

        for detection_index in unmatched_detection_indexes:
            assignments[detection_index] = self.next_track_id
            self.next_track_id += 1

        for detection_index, track_id in assignments.items():
            self.active_tracks[track_id] = {
                "center": tuple(player_detections[detection_index]["center"]),
                "last_seen_frame": frame_index,
            }

        return assignments

    def _update_ball_track(
        self,
        ball_detections: list[dict[str, Any]],
        annotated_frame: np.ndarray,
        frame_index: int,
    ) -> dict[str, Any]:
        selected_detection = self._select_primary_ball(ball_detections)
        status = "lost"
        raw_center = None
        smoothed_center = None
        bbox = None
        confidence = None

        if selected_detection is not None:
            raw_center = tuple(selected_detection["center"])
            bbox = selected_detection["bbox"]
            confidence = selected_detection["confidence"]
            self.ball_last_center = raw_center
            self.ball_last_bbox = bbox
            self.ball_missed_frames = 0
            status = "detected"
        elif self.ball_last_center is not None and self.ball_missed_frames < self.config.ball_max_track_gap_frames:
            raw_center = self.ball_last_center
            bbox = self.ball_last_bbox
            self.ball_missed_frames += 1
            status = "interpolated"
        else:
            self.ball_last_center = None
            self.ball_last_bbox = None
            self.ball_missed_frames = 0

        if raw_center is not None:
            smoothed_center = self._record_ball_point(
                frame_index=frame_index,
                raw_center=raw_center,
                bbox=bbox,
                status=status,
                confidence=confidence,
            )
            self._draw_ball_overlay(annotated_frame, raw_center, smoothed_center, bbox, status)
            self._register_direction_change_candidate(frame_index)

        self._draw_ball_trail(annotated_frame)

        recent_history = self.ball_history[-self.config.ball_history_size :]
        latest_direction_change = (
            self.ball_direction_change_candidates[-1] if self.ball_direction_change_candidates else None
        )

        return {
            "active": raw_center is not None,
            "status": status,
            "missed_frames": self.ball_missed_frames,
            "trajectory_length": len(recent_history),
            "raw_center": list(raw_center) if raw_center is not None else None,
            "smoothed_center": list(smoothed_center) if smoothed_center is not None else None,
            "bbox": bbox,
            "confidence": confidence,
            "history": recent_history,
            "direction_change_candidates": self.ball_direction_change_candidates[-5:],
            "latest_direction_change": latest_direction_change,
        }

    def _select_primary_ball(self, ball_detections: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not ball_detections:
            return None

        if self.ball_last_center is None:
            return max(ball_detections, key=lambda ball: ball["confidence"])

        best_ball = None
        best_distance = self.config.ball_max_tracking_distance_px + 1
        for ball in ball_detections:
            center_x, center_y = ball["center"]
            distance = float(
                np.sqrt(
                    (center_x - self.ball_last_center[0]) ** 2
                    + (center_y - self.ball_last_center[1]) ** 2
                )
            )
            if distance < best_distance:
                best_distance = distance
                best_ball = ball

        if best_ball is not None and best_distance <= self.config.ball_max_tracking_distance_px:
            return best_ball

        return max(ball_detections, key=lambda ball: ball["confidence"])

    def _record_ball_point(
        self,
        *,
        frame_index: int,
        raw_center: tuple[int, int],
        bbox: list[int] | None,
        status: str,
        confidence: float | None,
    ) -> tuple[int, int]:
        recent_confirmed_centers = [
            tuple(entry["raw_center"])
            for entry in self.ball_history
            if entry["status"] == "detected"
        ][-(self.config.ball_smoothing_window - 1) :]
        smoothing_centers = recent_confirmed_centers + [raw_center]
        smoothed_x = int(round(sum(point[0] for point in smoothing_centers) / len(smoothing_centers)))
        smoothed_y = int(round(sum(point[1] for point in smoothing_centers) / len(smoothing_centers)))
        smoothed_center = (smoothed_x, smoothed_y)

        self.ball_history.append(
            {
                "frame_index": frame_index,
                "raw_center": list(raw_center),
                "smoothed_center": list(smoothed_center),
                "bbox": bbox,
                "status": status,
                "confidence": confidence,
            }
        )

        if len(self.ball_history) > self.config.ball_history_size:
            self.ball_history.pop(0)

        return smoothed_center

    def _draw_ball_overlay(
        self,
        annotated_frame: np.ndarray,
        raw_center: tuple[int, int],
        smoothed_center: tuple[int, int],
        bbox: list[int] | None,
        status: str,
    ) -> None:
        color = (0, 0, 255) if status == "detected" else (0, 165, 255)

        if bbox is not None:
            x1, y1, x2, y2 = bbox
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)

        cv2.circle(annotated_frame, raw_center, 4, color, -1)
        cv2.circle(annotated_frame, smoothed_center, 6, (0, 255, 255), 2)
        cv2.putText(
            annotated_frame,
            f"BALL {status.upper()}",
            (smoothed_center[0] + 8, smoothed_center[1] - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            2,
        )

    def _draw_ball_trail(self, annotated_frame: np.ndarray) -> None:
        for i in range(1, len(self.ball_history)):
            previous_entry = self.ball_history[i - 1]
            current_entry = self.ball_history[i]
            prev_point = tuple(previous_entry["smoothed_center"])
            current_point = tuple(current_entry["smoothed_center"])
            line_color = (0, 255, 255) if current_entry["status"] == "detected" else (0, 165, 255)
            cv2.line(annotated_frame, prev_point, current_point, line_color, 2)

    def _register_direction_change_candidate(self, frame_index: int) -> None:
        valid_points = [tuple(entry["smoothed_center"]) for entry in self.ball_history[-6:]]
        if len(valid_points) < 3:
            return

        p1 = np.array(valid_points[-3], dtype=float)
        p2 = np.array(valid_points[-2], dtype=float)
        p3 = np.array(valid_points[-1], dtype=float)
        v1 = p2 - p1
        v2 = p3 - p2

        if np.linalg.norm(v1) < 2 or np.linalg.norm(v2) < 2:
            return

        cosine = float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
        if cosine > 0.4:
            return

        candidate = {
            "frame_index": frame_index,
            "location": list(valid_points[-2]),
            "cosine": round(cosine, 3),
        }

        last_candidate = self.ball_direction_change_candidates[-1] if self.ball_direction_change_candidates else None
        if last_candidate and last_candidate["frame_index"] == frame_index:
            return

        self.ball_direction_change_candidates.append(candidate)
        if len(self.ball_direction_change_candidates) > 10:
            self.ball_direction_change_candidates.pop(0)

    def _build_payload(
        self,
        frame: np.ndarray,
        frame_index: int,
        fps: float,
        players: list[dict[str, Any]],
        ball_detections: list[dict[str, Any]],
        ball_tracking: dict[str, Any],
        pose_detections: list[dict[str, Any]],
        pose_summary: dict[str, Any],
        event_summary: dict[str, Any],
        racket_summary: dict[str, Any],
        speed_summary: dict[str, Any],
        impact_power_summary: dict[str, Any],
        recommendations: dict[str, Any],
    ) -> dict[str, Any]:
        fall_alerts = sum(1 for player in players if player["fall_candidate"])
        current_speed = speed_summary["current_speed"]
        current_speed_px_per_sec = current_speed["speed_px_per_sec"] if current_speed is not None else None
        current_speed_km_per_hr = current_speed["speed_km_per_hr"] if current_speed is not None else None
        contact_power_proxy = impact_power_summary.get("contact_power_proxy")
        contact_power_score = contact_power_proxy.get("power_score") if contact_power_proxy is not None else None
        return {
            "status": "running",
            "phase": "phase_9_dashboard",
            "core_mode": "sport_agnostic",
            "sport": self.config.sport,
            "sport_profile": {
                "display_name": self.config.sport_profile.display_name,
                "equipment_name": self.config.sport_profile.equipment_name,
                "ball_name": self.config.sport_profile.ball_name,
                "ball_like_object_name": self.config.sport_profile.ball_like_object_name,
            },
            "source_video": Path(self.config.video_path).name,
            "model": Path(self.config.model_path).name,
            "pose_model": Path(self.config.pose_model_path).name,
            "frame_index": frame_index,
            "fps": round(float(fps), 2) if fps else 0.0,
            "timestamp_seconds": round(frame_index / fps, 2) if fps else 0.0,
            "frame_size": {
                "width": int(frame.shape[1]),
                "height": int(frame.shape[0]),
            },
            "summary": {
                "players_detected": len(players),
                "tracked_player_ids": [player["track_id"] for player in players],
                "balls_detected": len(ball_detections),
                "ball_track_active": ball_tracking["active"],
                "ball_trajectory_length": ball_tracking["trajectory_length"],
                "pose_detections": len(pose_detections),
                "players_with_pose": pose_summary["players_with_pose"],
                "avg_posture_score": pose_summary["avg_posture_score"],
                "injury_risk_count": pose_summary["injury_risk_count"],
                "active_swing_count": event_summary["active_swing_count"],
                "recent_event_count": event_summary["recent_event_count"],
                "contact_candidate_count": event_summary["contact_candidate_count"],
                "racket_track_active": racket_summary["active_count"] > 0,
                "racket_path_length_px": (
                    racket_summary["latest_primary_state"]["path_length_px"]
                    if racket_summary["latest_primary_state"] is not None
                    else 0.0
                ),
                "ball_speed_px_per_sec": current_speed_px_per_sec,
                "ball_speed_km_per_hr": current_speed_km_per_hr,
                "impact_power_score": contact_power_score,
                "recommendation_count": recommendations["recommendation_count"],
                "fall_alerts": fall_alerts,
            },
            "players": players,
            "ball": {
                "detections": ball_detections,
                "primary_detection": ball_detections[0] if ball_detections else None,
            },
            "ball_tracking": ball_tracking,
            "pose": {
                "detections": pose_detections,
                "summary": pose_summary,
            },
            "events": event_summary,
            "racket": racket_summary,
            "ball_speed": speed_summary,
            "impact_power": impact_power_summary,
            "recommendations": recommendations,
            "notes": [
                "Phase 8 recommendation engine is active.",
                "Recommendations combine posture, event, racket, and speed signals into explainable coaching feedback.",
                "Ball speed and contact power are approximation features unless camera calibration is available.",
                *self.config.sport_profile.notes,
            ],
        }


def run_video_session(
    config: AppConfig,
    *,
    display: bool = True,
    max_frames: int | None = None,
) -> None:
    cap = cv2.VideoCapture(str(config.video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open video: {config.video_path}")

    pipeline = SportsAnalyticsPipeline(config)
    writer = SessionWriter(config.stats_path, config.mirror_stats_paths)
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    session_started_at = time.time()
    session_started_at_iso = iso_now()
    session_id = f"{config.sport}-{int(session_started_at)}"
    clear_preview_frame(config.preview_frame_path)
    video_writer = build_video_writer(config.output_video_path, fps, frame_width, frame_height)
    clip_manager = ClipManager(session_id=session_id, data_dir=config.stats_path.parent / "data")
    last_payload: dict[str, Any] = {
        "status": "starting",
        "phase": "phase_9_dashboard",
        "core_mode": "sport_agnostic",
        "session_id": session_id,
        "session_started_at": session_started_at_iso,
        "last_updated_at": session_started_at_iso,
        "sport": config.sport,
        "sport_profile": {
            "display_name": config.sport_profile.display_name,
            "equipment_name": config.sport_profile.equipment_name,
            "ball_name": config.sport_profile.ball_name,
            "ball_like_object_name": config.sport_profile.ball_like_object_name,
        },
        "source_video": Path(config.video_path).name,
        "preview_frame_path": str(config.preview_frame_path),
        "output_video_path": str(config.output_video_path),
        "model": Path(config.model_path).name,
        "pose_model": Path(config.pose_model_path).name,
        "frame_index": 0,
        "fps": round(float(fps), 2) if fps else 0.0,
        "timestamp_seconds": 0.0,
        "frame_size": {"width": 0, "height": 0},
        "summary": {
            "players_detected": 0,
            "tracked_player_ids": [],
            "balls_detected": 0,
            "ball_track_active": False,
            "ball_trajectory_length": 0,
            "pose_detections": 0,
            "players_with_pose": 0,
            "avg_posture_score": None,
            "injury_risk_count": 0,
            "active_swing_count": 0,
            "recent_event_count": 0,
            "contact_candidate_count": 0,
            "racket_track_active": False,
            "racket_path_length_px": 0.0,
            "ball_speed_px_per_sec": None,
            "ball_speed_km_per_hr": None,
            "impact_power_score": None,
            "recommendation_count": 0,
            "fall_alerts": 0,
        },
        "players": [],
        "ball": {
            "detections": [],
            "primary_detection": None,
        },
        "ball_tracking": {
            "active": False,
            "status": "waiting",
            "missed_frames": 0,
            "trajectory_length": 0,
            "raw_center": None,
            "smoothed_center": None,
            "bbox": None,
            "confidence": None,
            "history": [],
            "direction_change_candidates": [],
            "latest_direction_change": None,
        },
        "pose": {
            "detections": [],
            "summary": {
                "pose_detections": 0,
                "players_with_pose": 0,
                "matched_player_ids": [],
                "avg_trunk_lean_deg": None,
                "avg_posture_score": None,
                "injury_risk_player_ids": [],
                "injury_risk_count": 0,
            },
        },
        "events": default_event_summary(0),
        "racket": {
            "sport_mode": config.sport,
            "primary_player_id": None,
            "active_track_ids": [],
            "active_count": 0,
            "latest_primary_state": None,
            "recent_primary_path": [],
        },
        "ball_speed": {
            "active": False,
            "meters_per_pixel": config.ball_meters_per_pixel,
            "current_speed": None,
            "avg_recent_speed_px_per_sec": None,
            "peak_speed_px_per_sec": None,
            "speed_series": [],
            "contact_comparison": None,
        },
        "impact_power": {
            "active": False,
            "latest_racket_speed": None,
            "racket_speed_series": [],
            "contact_power_proxy": None,
        },
        "recommendations": {
            "sport_mode": config.sport,
            "primary_player_id": None,
            "session_recommendations": [],
            "player_recommendations": {},
            "recommendation_count": 0,
        },
        "notes": [
            "Session initialized.",
            "Waiting for frame processing to begin.",
        ],
    }
    writer.write(last_payload)

    frame_index = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            result = pipeline.process_frame(frame, frame_index, fps)
            last_payload = result.payload
            last_payload["session_id"] = session_id
            last_payload["session_started_at"] = session_started_at_iso
            last_payload["last_updated_at"] = iso_now()
            last_payload["preview_frame_path"] = str(config.preview_frame_path)
            last_payload["output_video_path"] = str(config.output_video_path)
            last_payload["runtime_seconds"] = round(time.time() - session_started_at, 2)

            # --- ClipManager: feed buffer and trigger clips/bad-frames ---
            clip_manager.update_buffer(result.annotated_frame, frame_index)

            # Trigger a snippet on each new contact candidate
            if last_payload["events"].get("contact_candidate_count", 0) > 0:
                clip_manager.trigger_snippet(
                    metric_name="contact_candidate",
                    frame_index=frame_index,
                    fps=fps or 25.0,
                    frame_width=frame_width,
                    frame_height=frame_height,
                )

            # Trigger a snippet for any player flagged with injury risk this frame
            for risk_pid in last_payload["pose"]["summary"].get("injury_risk_player_ids", []):
                clip_manager.trigger_snippet(
                    metric_name=f"injury_risk_player_{risk_pid}",
                    frame_index=frame_index,
                    fps=fps or 25.0,
                    frame_width=frame_width,
                    frame_height=frame_height,
                )

            # Save a bad-frame JPEG when any player's posture score is poor
            timestamp_sec = frame_index / fps if fps else 0.0
            for player in last_payload.get("players", []):
                posture = (player.get("pose") or {}).get("posture") or {}
                posture_score = posture.get("posture_score")
                if posture_score is not None and posture_score < 60:
                    clip_manager.check_and_save_bad_frame(
                        annotated_frame=result.annotated_frame,
                        reason=f"Low Posture Score ({posture_score}) – Player {player['track_id']}",
                        timestamp_seconds=timestamp_sec,
                        frame_index=frame_index,
                    )

            last_payload["clip_summary"] = clip_manager.get_summary()
            # -----------------------------------------------------------------

            write_preview_frame(config.preview_frame_path, result.annotated_frame)
            if video_writer is not None:
                video_writer.write(result.annotated_frame)
            writer.write(last_payload)

            if display:
                cv2.imshow(config.display_window_name, result.annotated_frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    last_payload["status"] = "stopped"
                    last_payload["last_updated_at"] = iso_now()
                    last_payload["notes"] = [
                        "Session stopped by the user.",
                        "Phase 8 recommendation output remains available in match_stats.json.",
                    ]
                    writer.write(last_payload)
                    break

            frame_index += 1
            if max_frames is not None and frame_index >= max_frames:
                last_payload["status"] = "completed"
                last_payload["last_updated_at"] = iso_now()
                last_payload["notes"] = [
                    f"Processed {frame_index} frames for Phase 8 validation.",
                    "Run without --max-frames for the full session.",
                ]
                writer.write(last_payload)
                break
    finally:
        cap.release()
        if video_writer is not None:
            video_writer.release()
        clip_manager.release_all()
        if display:
            cv2.destroyAllWindows()

    if last_payload["status"] == "running":
        last_payload["status"] = "completed"
        last_payload["last_updated_at"] = iso_now()
        last_payload["clip_summary"] = clip_manager.get_summary()
        last_payload["notes"] = [
            "Video processing completed.",
            "Phase 8 recommendation output is ready for the dashboard.",
            f"ClipManager saved {clip_manager.get_summary()['snippet_count']} snippet(s) and "
            f"{clip_manager.get_summary()['bad_frame_count']} bad frame(s).",
        ]
        writer.write(last_payload)


def iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def clear_preview_frame(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def write_preview_frame(path: Path, frame: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    success, encoded = cv2.imencode(".jpg", frame)
    if not success:
        return

    temp_path = path.with_name(f"{path.name}.{os.getpid()}.{int(time.time() * 1000)}.tmp")
    temp_path.write_bytes(encoded.tobytes())

    try:
        for _ in range(20):
            try:
                temp_path.replace(path)
                return
            except PermissionError:
                time.sleep(0.1)
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


def build_video_writer(path: Path, fps: float, frame_width: int, frame_height: int) -> cv2.VideoWriter | None:
    if frame_width <= 0 or frame_height <= 0:
        return None

    path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    video_writer = cv2.VideoWriter(str(path), fourcc, fps or 25.0, (frame_width, frame_height))
    if not video_writer.isOpened():
        return None
    return video_writer
