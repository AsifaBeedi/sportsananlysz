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
from .baseline import build_baseline_output
from .config import AppConfig, build_session_id
from .events import EventEngine, default_event_summary
from .impact_power import ImpactPowerEstimator
from .input_sources import resolve_input_source
from .posture import analyze_posture
from .pose import build_pose_metrics, draw_pose_overlay, extract_pose_detections, match_pose_detections_to_players
from .puck_tracker import HockeyPuckDetector
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


class SessionPerformanceCollector:
    def __init__(self) -> None:
        self.frame_series: list[dict[str, Any]] = []
        self.event_timeline: list[dict[str, Any]] = []
        self.event_keys: set[tuple[Any, ...]] = set()
        self.event_type_counts: dict[str, int] = {}
        self.shot_type_counts: dict[str, int] = {}

    def update(self, payload: dict[str, Any]) -> None:
        players = payload.get("players", [])
        primary_player_id = (payload.get("events") or {}).get("primary_player_id")
        primary_player = next((player for player in players if player.get("track_id") == primary_player_id), None)
        primary_posture = ((primary_player.get("pose") or {}).get("posture", {}) if primary_player else {})
        primary_event_state = (primary_player.get("event_state") or {} if primary_player else {})
        primary_racket_state = (primary_player.get("racket") or {} if primary_player else {})
        latest_racket_speed = ((payload.get("impact_power") or {}).get("latest_racket_speed") or {})
        previous_shot_label = self.frame_series[-1].get("shot_label_candidate") if self.frame_series else None

        frame_sample = {
            "frame_index": payload.get("frame_index"),
            "timestamp_seconds": payload.get("timestamp_seconds"),
            "players_detected": (payload.get("summary") or {}).get("players_detected"),
            "players_with_pose": (payload.get("summary") or {}).get("players_with_pose"),
            "avg_posture_score": (payload.get("summary") or {}).get("avg_posture_score"),
            "primary_posture_score": primary_posture.get("posture_score"),
            "active_swing_count": (payload.get("summary") or {}).get("active_swing_count"),
            "activity_score": primary_event_state.get("activity_score"),
            "ball_proximity_px": primary_event_state.get("ball_proximity_px"),
            "ball_control_score": primary_event_state.get("ball_control_score"),
            "ball_speed_px_per_sec": (payload.get("summary") or {}).get("ball_speed_px_per_sec"),
            "impact_power_score": (payload.get("summary") or {}).get("impact_power_score"),
            "equipment_path_length_px": primary_racket_state.get("path_length_px"),
            "equipment_angle_deg": primary_racket_state.get("angle_deg"),
            "equipment_speed_px_per_sec": latest_racket_speed.get("speed_px_per_sec"),
            "shot_label_candidate": primary_event_state.get("shot_label_candidate"),
            "swing_phase": primary_event_state.get("swing_phase"),
            "recommendation_count": (payload.get("recommendations") or {}).get("recommendation_count"),
        }

        if not self.frame_series or self.frame_series[-1].get("frame_index") != frame_sample.get("frame_index"):
            self.frame_series.append(frame_sample)
            if len(self.frame_series) > 240:
                self.frame_series.pop(0)

        shot_label_candidate = frame_sample.get("shot_label_candidate")
        if shot_label_candidate and shot_label_candidate != previous_shot_label:
            shot_label_key = str(shot_label_candidate)
            self.shot_type_counts[shot_label_key] = self.shot_type_counts.get(shot_label_key, 0) + 1

        for event in (payload.get("events") or {}).get("current_frame_events", []):
            key = (
                event.get("event_type"),
                event.get("frame_index"),
                event.get("track_id"),
                event.get("shot_label"),
            )
            if key in self.event_keys:
                continue
            self.event_keys.add(key)
            self.event_timeline.append(
                {
                    "event_type": event.get("event_type"),
                    "frame_index": event.get("frame_index"),
                    "timestamp_seconds": event.get("timestamp_seconds"),
                    "track_id": event.get("track_id"),
                    "shot_label": event.get("shot_label"),
                    "activity_score": event.get("activity_score"),
                    "ball_proximity_px": event.get("ball_proximity_px"),
                    "duration_frames": event.get("duration_frames"),
                    "peak_activity_score": event.get("peak_activity_score"),
                }
            )
            if len(self.event_timeline) > 80:
                self.event_timeline.pop(0)

            event_type = str(event.get("event_type") or "unknown")
            self.event_type_counts[event_type] = self.event_type_counts.get(event_type, 0) + 1
            shot_label = event.get("shot_label")
            if shot_label:
                self.shot_type_counts[str(shot_label)] = self.shot_type_counts.get(str(shot_label), 0) + 1

    def build_payload(self) -> dict[str, Any]:
        posture_values = [
            float(item["primary_posture_score"])
            for item in self.frame_series
            if item.get("primary_posture_score") is not None
        ]
        ball_speed_values = [
            float(item["ball_speed_px_per_sec"])
            for item in self.frame_series
            if item.get("ball_speed_px_per_sec") is not None
        ]
        equipment_speed_values = [
            float(item["equipment_speed_px_per_sec"])
            for item in self.frame_series
            if item.get("equipment_speed_px_per_sec") is not None
        ]
        activity_values = [
            float(item["activity_score"])
            for item in self.frame_series
            if item.get("activity_score") is not None
        ]
        control_values = [
            float(item["ball_control_score"])
            for item in self.frame_series
            if item.get("ball_control_score") is not None
        ]
        event_counter: dict[str, int] = dict(sorted(self.event_type_counts.items()))
        shot_counter: dict[str, int] = dict(sorted(self.shot_type_counts.items()))
        dominant_event_type = max(event_counter, key=event_counter.get) if event_counter else None
        dominant_shot_label = max(shot_counter, key=shot_counter.get) if shot_counter else None
        inference_quality_score = 0.0
        inference_quality_score += 0.2 if len(self.frame_series) >= 20 else 0.1 if self.frame_series else 0.0
        inference_quality_score += min(len(self.event_timeline), 6) * 0.08
        inference_quality_score += 0.15 if dominant_shot_label else 0.0
        inference_quality_score += 0.12 if ball_speed_values else 0.0
        inference_quality_score += 0.12 if equipment_speed_values else 0.0
        inference_quality_score += 0.08 if posture_values else 0.0
        inference_quality_score += 0.1 if control_values else 0.0
        inference_quality_score = round(min(inference_quality_score, 1.0), 2)
        if inference_quality_score >= 0.75:
            inference_quality_label = "high"
        elif inference_quality_score >= 0.45:
            inference_quality_label = "medium"
        else:
            inference_quality_label = "low"

        return {
            "frame_series": self.frame_series[-180:],
            "event_timeline": self.event_timeline[-40:],
            "event_type_counts": event_counter,
            "shot_type_counts": shot_counter,
            "summary": {
                "sample_count": len(self.frame_series),
                "event_count": len(self.event_timeline),
                "peak_primary_posture_score": round(max(posture_values), 2) if posture_values else None,
                "peak_ball_speed_px_per_sec": round(max(ball_speed_values), 2) if ball_speed_values else None,
                "peak_equipment_speed_px_per_sec": round(max(equipment_speed_values), 2) if equipment_speed_values else None,
                "peak_activity_score": round(max(activity_values), 2) if activity_values else None,
                "peak_ball_control_score": round(max(control_values), 2) if control_values else None,
                "dominant_event_type": dominant_event_type,
                "dominant_shot_label": dominant_shot_label,
                "inference_quality_score": inference_quality_score,
                "inference_quality_label": inference_quality_label,
                "detected_shot_labels": sorted(self.shot_type_counts.keys()),
            },
        }


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
        self.previous_object_gray: np.ndarray | None = None
        self.hockey_puck_detector: HockeyPuckDetector | None = (
            HockeyPuckDetector() if config.sport == "hockey" else None
        )

    def process_frame(self, frame: np.ndarray, frame_index: int, fps: float) -> FrameResult:
        frame = ensure_bgr_frame(frame)
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
                            "source": "yolo_sports_ball",
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
        if not ball_detections and self.hockey_puck_detector is not None:
            puck_detection = self.hockey_puck_detector.detect(
                frame, player_detections, self.ball_last_center
            )
            if puck_detection is not None:
                ball_detections.append(puck_detection)
        if not ball_detections and self.config.sport == "basketball":
            basketball_detection = self._detect_basketball_ball_candidate(frame, players)
            if basketball_detection is not None:
                ball_detections.append(basketball_detection)
        if not ball_detections:
            fallback_detection = self._detect_motion_object(frame, player_detections)
            if fallback_detection is not None:
                ball_detections.append(fallback_detection)

        self._update_motion_reference_frame(frame)

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
        detected_center = None
        tracked_center = None
        smoothed_center = None
        bbox = None
        confidence = None

        if selected_detection is not None:
            detected_center = tuple(selected_detection["center"])
            tracked_center = detected_center
            bbox = selected_detection["bbox"]
            confidence = selected_detection["confidence"]
            self.ball_last_center = tracked_center
            self.ball_last_bbox = bbox
            self.ball_missed_frames = 0
            status = "detected"
        elif self.ball_last_center is not None and self.ball_missed_frames < self.config.ball_max_track_gap_frames:
            tracked_center = self.ball_last_center
            bbox = self.ball_last_bbox
            self.ball_missed_frames += 1
            status = "interpolated"
        else:
            self.ball_last_center = None
            self.ball_last_bbox = None
            self.ball_missed_frames = 0

        if tracked_center is not None:
            smoothed_center = self._record_ball_point(
                frame_index=frame_index,
                detected_center=detected_center,
                tracked_center=tracked_center,
                bbox=bbox,
                status=status,
                confidence=confidence,
            )
            self._draw_ball_overlay(annotated_frame, tracked_center, smoothed_center, bbox, status)
            if detected_center is not None:
                self._register_direction_change_candidate(frame_index)

        self._draw_ball_trail(annotated_frame)

        recent_history = self.ball_history[-self.config.ball_history_size :]
        latest_direction_change = (
            self.ball_direction_change_candidates[-1] if self.ball_direction_change_candidates else None
        )
        tracking_mode = (
            str(selected_detection.get("source", self.config.sport_profile.object_tracking_mode))
            if selected_detection is not None
            else self.config.sport_profile.object_tracking_mode
        )

        return {
            "active": tracked_center is not None,
            "detected_this_frame": detected_center is not None,
            "status": status,
            "tracking_mode": tracking_mode,
            "missed_frames": self.ball_missed_frames,
            "trajectory_length": len(recent_history),
            "frame_detection_count": len(ball_detections),
            "detected_center": list(detected_center) if detected_center is not None else None,
            "tracked_center": list(tracked_center) if tracked_center is not None else None,
            "raw_center": list(tracked_center) if tracked_center is not None else None,
            "smoothed_center": list(smoothed_center) if smoothed_center is not None else None,
            "bbox": bbox,
            "confidence": confidence,
            "selected_detection": selected_detection,
            "frame_detections": ball_detections,
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
        best_score = -1.0
        for ball in ball_detections:
            center_x, center_y = ball["center"]
            distance = float(
                np.sqrt(
                    (center_x - self.ball_last_center[0]) ** 2
                    + (center_y - self.ball_last_center[1]) ** 2
                )
            )
            confidence = float(ball.get("confidence") or 0.0)
            distance_score = max(
                0.0,
                1.0 - min(distance, self.config.ball_max_tracking_distance_px * 2) / max(self.config.ball_max_tracking_distance_px * 2, 1.0),
            )
            area_score = 0.0
            if self.ball_last_bbox is not None:
                last_area = bbox_area(self.ball_last_bbox)
                current_area = bbox_area(ball["bbox"])
                if last_area > 0 and current_area > 0:
                    area_score = 1.0 - abs(current_area - last_area) / max(last_area, current_area)
            score = (distance_score * 0.55) + (confidence * 0.35) + (max(0.0, area_score) * 0.10)
            if score > best_score:
                best_score = score
                best_ball = ball

        if best_ball is not None:
            distance = euclidean_distance(best_ball["center"], self.ball_last_center)
            if distance <= self.config.ball_max_tracking_distance_px:
                return best_ball

        if best_ball is not None and best_score >= 0.45:
            return best_ball

        return max(ball_detections, key=lambda ball: ball["confidence"])

    def _detect_motion_object(
        self,
        frame: np.ndarray,
        player_detections: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if self.config.sport_profile.object_tracking_mode != "motion_fallback" and self.ball_last_center is None:
            return None

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        previous_gray = self.previous_object_gray
        if previous_gray is None:
            return None

        frame_height, frame_width = gray.shape[:2]
        if self.config.sport_profile.object_tracking_mode == "motion_fallback":
            min_area = max(6, int((frame_width * frame_height) * 0.00003))
            max_area = max(min_area + 1, int((frame_width * frame_height) * 0.002))
            source_name = "motion_fallback"
        else:
            min_area = max(4, int((frame_width * frame_height) * 0.00001))
            max_area = max(min_area + 1, int((frame_width * frame_height) * 0.00045))
            source_name = "motion_recovery"

        diff = cv2.absdiff(previous_gray, gray)
        _, threshold = cv2.threshold(diff, 22, 255, cv2.THRESH_BINARY)
        threshold = cv2.dilate(threshold, None, iterations=2)
        contours, _ = cv2.findContours(threshold, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best_detection = None
        best_score = -1.0
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < min_area or area > max_area:
                continue

            x, y, w, h = cv2.boundingRect(contour)
            center_x = int(x + w / 2)
            center_y = int(y + h / 2)

            if any(_point_inside_bbox((center_x, center_y), player["bbox"]) for player in player_detections):
                continue

            if self.ball_last_center is not None:
                distance = float(
                    np.sqrt(
                        (center_x - self.ball_last_center[0]) ** 2
                        + (center_y - self.ball_last_center[1]) ** 2
                    )
                )
                if (
                    self.config.sport_profile.object_tracking_mode != "motion_fallback"
                    and distance > self.config.ball_max_tracking_distance_px * 1.4
                ):
                    continue
            else:
                distance = 0.0

            score = area
            if self.ball_last_center is not None:
                score -= min(distance, self.config.ball_max_tracking_distance_px)

            if score > best_score:
                best_score = score
                best_detection = {
                    "bbox": [x, y, x + w, y + h],
                    "center": [center_x, center_y],
                    "confidence": round(min(0.49, area / max(max_area, 1)), 4),
                    "source": source_name,
                }

        return best_detection

    def _detect_basketball_ball_candidate(
        self,
        frame: np.ndarray,
        players: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        previous_gray = self.previous_object_gray
        if previous_gray is None or not players:
            return None

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        frame_height, frame_width = gray.shape[:2]
        min_area = max(3, int((frame_width * frame_height) * 0.000004))
        max_area = max(min_area + 1, int((frame_width * frame_height) * 0.00035))

        diff = cv2.absdiff(previous_gray, gray)
        _, threshold = cv2.threshold(diff, 14, 255, cv2.THRESH_BINARY)
        threshold = cv2.dilate(threshold, None, iterations=2)
        contours, _ = cv2.findContours(threshold, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best_detection = None
        best_score = -1.0
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < min_area or area > max_area:
                continue

            x, y, w, h = cv2.boundingRect(contour)
            if min(w, h) <= 1:
                continue

            aspect_ratio = max(w, h) / max(min(w, h), 1)
            if aspect_ratio > 2.6:
                continue

            center_x = int(x + w / 2)
            center_y = int(y + h / 2)
            candidate_center = (center_x, center_y)

            best_player_score = None
            for player in players:
                bbox = player["bbox"]
                expanded_bbox = [
                    max(0, bbox[0] - 28),
                    max(0, bbox[1] - 28),
                    min(frame_width - 1, bbox[2] + 28),
                    min(frame_height - 1, bbox[3] + 40),
                ]
                if not _point_inside_bbox(candidate_center, expanded_bbox):
                    continue

                pose = player.get("pose") or {}
                keypoints = pose.get("keypoints") or {}
                wrist_points = []
                for wrist_name in ("left_wrist", "right_wrist"):
                    wrist = keypoints.get(wrist_name)
                    if wrist is not None:
                        wrist_points.append((int(round(wrist["x"])), int(round(wrist["y"]))))

                wrist_distance = min(
                    (euclidean_distance(candidate_center, wrist_point) for wrist_point in wrist_points),
                    default=float("inf"),
                )
                torso_distance = euclidean_distance(candidate_center, tuple(player["center"]))
                inside_bbox_bonus = 16.0 if _point_inside_bbox(candidate_center, bbox) else 0.0
                proximity_score = max(0.0, 90.0 - min(wrist_distance, 90.0))
                torso_score = max(0.0, 110.0 - min(torso_distance, 110.0)) * 0.25
                player_score = inside_bbox_bonus + proximity_score + torso_score

                if best_player_score is None or player_score > best_player_score:
                    best_player_score = player_score

            if best_player_score is None or best_player_score < 18.0:
                continue

            continuity_bonus = 0.0
            if self.ball_last_center is not None:
                distance = euclidean_distance(candidate_center, self.ball_last_center)
                continuity_bonus = max(
                    0.0,
                    self.config.ball_max_tracking_distance_px * 1.5 - distance,
                ) * 0.2

            roundness_bonus = max(0.0, 10.0 - abs(w - h) * 1.5)
            score = best_player_score + continuity_bonus + roundness_bonus + min(area, 28.0)
            if score > best_score:
                best_score = score
                best_detection = {
                    "bbox": [x, y, x + w, y + h],
                    "center": [center_x, center_y],
                    "confidence": round(min(0.54, 0.18 + (score / 220.0)), 4),
                    "source": "basketball_motion_recovery",
                }

        return best_detection

    def _update_motion_reference_frame(self, frame: np.ndarray) -> None:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        self.previous_object_gray = cv2.GaussianBlur(gray, (5, 5), 0)

    def _record_ball_point(
        self,
        *,
        frame_index: int,
        detected_center: tuple[int, int] | None,
        tracked_center: tuple[int, int],
        bbox: list[int] | None,
        status: str,
        confidence: float | None,
    ) -> tuple[int, int]:
        recent_confirmed_centers = [
            tuple(entry.get("detected_center") or entry["tracked_center"])
            for entry in self.ball_history
            if entry.get("detected_this_frame")
        ][-(self.config.ball_smoothing_window - 1) :]
        smoothing_centers = recent_confirmed_centers + [tracked_center]
        smoothed_x = int(round(sum(point[0] for point in smoothing_centers) / len(smoothing_centers)))
        smoothed_y = int(round(sum(point[1] for point in smoothing_centers) / len(smoothing_centers)))
        smoothed_center = (smoothed_x, smoothed_y)

        self.ball_history.append(
            {
                "frame_index": frame_index,
                "detected_this_frame": detected_center is not None,
                "detected_center": list(detected_center) if detected_center is not None else None,
                "tracked_center": list(tracked_center),
                "raw_center": list(tracked_center),
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
            f"{self.config.sport_profile.ball_name.upper()} {status.upper()}",
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
        baseline = build_baseline_output(
            sport=self.config.sport,
            sport_profile=self.config.sport_profile,
            tracked_player_ids=[player["track_id"] for player in players],
            players_detected=len(players),
            balls_detected=len(ball_detections),
            ball_track_active=ball_tracking["active"],
            ball_trajectory_length=ball_tracking["trajectory_length"],
            players_with_pose=pose_summary["players_with_pose"],
            avg_posture_score=pose_summary["avg_posture_score"],
            injury_risk_count=pose_summary["injury_risk_count"],
            racket_track_active=racket_summary["active_count"] > 0,
            racket_path_length_px=(
                racket_summary["latest_primary_state"]["path_length_px"]
                if racket_summary["latest_primary_state"] is not None
                else 0.0
            ),
            recommendation_count=recommendations["recommendation_count"],
            recent_event_count=event_summary["recent_event_count"],
            contact_candidate_count=event_summary["contact_candidate_count"],
            object_tracking_provider=ball_tracking["tracking_mode"],
        )
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
                "object_tracking_mode": self.config.sport_profile.object_tracking_mode,
                "capability_level": self.config.sport_profile.capability_level,
                "advanced_event_status": self.config.sport_profile.advanced_event_status,
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
            "baseline": baseline,
            "players": players,
            "ball": {
                "detections": ball_detections,
                "primary_detection": ball_tracking.get("selected_detection"),
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
    resolved_source = resolve_input_source(config)
    cap = resolved_source.open_capture()
    if not cap.isOpened():
        raise RuntimeError(
            f"Unable to open {resolved_source.source_type} source: {resolved_source.source_uri or resolved_source.source_label}"
        )

    pipeline = SportsAnalyticsPipeline(config)
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    frame_width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)  or 0)
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    _raw_total   = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)  or 0)
    total_frames = _raw_total if _raw_total > 0 else None
    video_duration_seconds = round(total_frames / fps, 2) if (total_frames and fps) else None
    session_started_at = time.time()
    session_started_at_iso = iso_now()
    session_id = build_session_id(config.sport, session_started_at)
    session_paths = config.build_session_paths(session_id)
    match_metadata = build_match_metadata(config, session_id)
    writer = SessionWriter(session_paths.stats_path, config.latest_stats_paths)
    clear_preview_frame(session_paths.preview_frame_path)
    video_writer = (
        build_video_writer(
            session_paths.output_video_path,
            fps,
            frame_width,
            frame_height,
            codec_preference=config.video_writer_codec,
        )
        if config.write_output_video
        else None
    )
    clip_manager = ClipManager(session_id=session_id, data_dir=session_paths.session_dir)
    performance_collector = SessionPerformanceCollector()
    last_payload: dict[str, Any] = {
        "status": "starting",
        "phase": "phase_9_dashboard",
        "core_mode": "sport_agnostic",
        "session_id": session_id,
        "session_dir": str(session_paths.session_dir),
        "stats_path": str(session_paths.stats_path),
        "session_started_at": session_started_at_iso,
        "last_updated_at": session_started_at_iso,
        "sport": config.sport,
        "match_id": match_metadata["match_id"],
        "camera_id": match_metadata["camera_id"],
        "source": {
            "type": resolved_source.source_type,
            "label": resolved_source.source_label,
            "uri": resolved_source.source_uri,
            "metadata": resolved_source.metadata,
        },
        "match": match_metadata,
        "sport_profile": {
            "display_name": config.sport_profile.display_name,
            "equipment_name": config.sport_profile.equipment_name,
            "ball_name": config.sport_profile.ball_name,
            "ball_like_object_name": config.sport_profile.ball_like_object_name,
            "object_tracking_mode": config.sport_profile.object_tracking_mode,
            "capability_level": config.sport_profile.capability_level,
            "advanced_event_status": config.sport_profile.advanced_event_status,
        },
        "source_video": resolved_source.source_video,
        "preview_frame_path": str(session_paths.preview_frame_path),
        "output_video_path": str(session_paths.output_video_path),
        "model": Path(config.model_path).name,
        "pose_model": Path(config.pose_model_path).name,
        "frame_index": 0,
        "total_frames": total_frames,
        "fps": round(float(fps), 2) if fps else 0.0,
        "timestamp_seconds": 0.0,
        "video_duration_seconds": video_duration_seconds,
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
        "baseline": build_baseline_output(
            sport=config.sport,
            sport_profile=config.sport_profile,
            object_tracking_provider=config.sport_profile.object_tracking_mode,
        ),
        "players": [],
        "ball": {
            "detections": [],
            "primary_detection": None,
        },
        "ball_tracking": {
            "active": False,
            "detected_this_frame": False,
            "status": "waiting",
            "tracking_mode": config.sport_profile.object_tracking_mode,
            "missed_frames": 0,
            "trajectory_length": 0,
            "frame_detection_count": 0,
            "detected_center": None,
            "tracked_center": None,
            "raw_center": None,
            "smoothed_center": None,
            "bbox": None,
            "confidence": None,
            "selected_detection": None,
            "frame_detections": [],
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
        "performance_metrics": performance_collector.build_payload(),
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
            last_payload["session_dir"] = str(session_paths.session_dir)
            last_payload["stats_path"] = str(session_paths.stats_path)
            last_payload["session_started_at"] = session_started_at_iso
            last_payload["last_updated_at"] = iso_now()
            last_payload["source_video"] = resolved_source.source_video
            last_payload["match_id"] = match_metadata["match_id"]
            last_payload["camera_id"] = match_metadata["camera_id"]
            last_payload["source"] = {
                "type": resolved_source.source_type,
                "label": resolved_source.source_label,
                "uri": resolved_source.source_uri,
                "metadata": resolved_source.metadata,
            }
            last_payload["match"] = match_metadata
            last_payload["preview_frame_path"] = str(session_paths.preview_frame_path)
            last_payload["output_video_path"] = str(session_paths.output_video_path)
            last_payload["runtime_seconds"] = round(time.time() - session_started_at, 2)
            last_payload["total_frames"] = total_frames
            last_payload["video_duration_seconds"] = video_duration_seconds

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

            # Trigger a clip for each completed swing/stroke/stick window that has a shot label.
            # This captures validation footage for every labeled tennis, cricket, baseball, and hockey event.
            for event in last_payload["events"].get("current_frame_events", []):
                event_type = event.get("event_type", "")
                shot_label = event.get("shot_label")
                if event_type in {
                    "swing_window",
                    "stroke_window",
                    "bat_swing_window",
                    "stick_motion_window",
                } and shot_label:
                    clip_manager.trigger_snippet(
                        metric_name=f"{event_type}_{shot_label}",
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
            performance_collector.update(last_payload)
            last_payload["performance_metrics"] = performance_collector.build_payload()
            # -----------------------------------------------------------------

            should_write_stats = should_persist_frame(frame_index, config.stats_write_interval_frames)
            should_write_preview = should_persist_frame(frame_index, config.preview_write_interval_frames)

            if should_write_preview:
                write_preview_frame(session_paths.preview_frame_path, result.annotated_frame)

            if video_writer is None and config.write_output_video:
                video_writer = build_video_writer(
                    session_paths.output_video_path,
                    fps or 25.0,
                    int(result.annotated_frame.shape[1]),
                    int(result.annotated_frame.shape[0]),
                    codec_preference=config.video_writer_codec,
                )
            if video_writer is not None:
                video_writer.write(result.annotated_frame)
            if should_write_stats:
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
                    last_payload["performance_metrics"] = performance_collector.build_payload()
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
                last_payload["performance_metrics"] = performance_collector.build_payload()
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
        last_payload["performance_metrics"] = performance_collector.build_payload()
        writer.write(last_payload)


def iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def build_match_metadata(config: AppConfig, session_id: str) -> dict[str, Any]:
    match_id = (str(config.match_id).strip() if config.match_id else "") or None
    camera_id = (str(config.camera_id).strip() if config.camera_id else "") or None
    camera_label = (str(config.camera_label).strip() if config.camera_label else "") or None
    camera_role = (str(config.camera_role).strip() if config.camera_role else "") or None
    return {
        "match_id": match_id,
        "camera_id": camera_id,
        "camera_label": camera_label or camera_id or "Primary Camera",
        "camera_role": camera_role or "single",
        "is_multi_camera": bool(match_id and (camera_id or camera_label)),
        "session_id": session_id,
    }


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


def should_persist_frame(frame_index: int, interval_frames: int) -> bool:
    interval = max(1, int(interval_frames or 1))
    return frame_index == 0 or (frame_index % interval) == 0


def build_video_writer(
    path: Path,
    fps: float,
    frame_width: int,
    frame_height: int,
    *,
    codec_preference: str = "auto",
) -> cv2.VideoWriter | None:
    if frame_width <= 0 or frame_height <= 0:
        return None

    path.parent.mkdir(parents=True, exist_ok=True)
    for fourcc_str in preferred_video_codecs(codec_preference):
        fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
        writer = cv2.VideoWriter(str(path), fourcc, fps or 25.0, (frame_width, frame_height))
        if writer.isOpened():
            return writer
    return None


def preferred_video_codecs(codec_preference: str | None) -> tuple[str, ...]:
    configured = str(codec_preference or os.getenv("SPORTS_AI_VIDEO_CODEC") or "auto").strip().lower()
    explicit = {
        "mp4v": ("mp4v",),
        "avc1": ("avc1",),
        "h264": ("H264",),
        "none": (),
    }
    if configured in explicit:
        return explicit[configured]

    # Default to browser-friendly codecs first so Streamlit video playback keeps
    # working as expected. Use explicit `mp4v` or `--no-output-video` when you
    # want the faster/safer Windows path instead.
    if os.name == "nt":
        return ("avc1", "H264", "mp4v")
    return ("avc1", "H264", "mp4v")


def ensure_bgr_frame(frame: np.ndarray) -> np.ndarray:
    if frame.ndim == 2:
        return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

    if frame.ndim == 3 and frame.shape[2] == 4:
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

    return frame


def _point_inside_bbox(point: tuple[int, int], bbox: list[int]) -> bool:
    x, y = point
    x1, y1, x2, y2 = bbox
    return x1 <= x <= x2 and y1 <= y <= y2


def bbox_area(bbox: list[int] | None) -> int:
    if bbox is None:
        return 0
    return max(0, bbox[2] - bbox[0]) * max(0, bbox[3] - bbox[1])


def euclidean_distance(point_a: list[int] | tuple[int, int], point_b: list[int] | tuple[int, int]) -> float:
    return float(np.sqrt((point_a[0] - point_b[0]) ** 2 + (point_a[1] - point_b[1]) ** 2))
