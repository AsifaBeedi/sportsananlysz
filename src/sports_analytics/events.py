from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np


class EventEngine:
    def __init__(self, sport: str) -> None:
        self.sport = sport
        self.tennis_engine = TennisEventEngine(sport) if sport in {"tennis", "badminton", "table_tennis"} else None
        self.cricket_engine = CricketEventEngine() if sport == "cricket" else None
        self.baseball_engine = BaseballEventEngine() if sport == "baseball" else None
        self.hockey_engine = HockeyEventEngine() if sport == "hockey" else None
        self.volleyball_engine = VolleyballEventEngine() if sport == "volleyball" else None
        self.basketball_engine = BasketballEventEngine() if sport == "basketball" else None

    def update(
        self,
        players: list[dict[str, Any]],
        ball_tracking: dict[str, Any],
        frame_index: int,
        fps: float,
        frame_size: dict[str, int],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if self.tennis_engine is not None:
            players, summary = self.tennis_engine.update(players, ball_tracking, frame_index, fps, frame_size)
            return players, enrich_event_summary(players, ball_tracking, summary)

        if self.cricket_engine is not None:
            players, summary = self.cricket_engine.update(players, ball_tracking, frame_index, fps, frame_size)
            return players, enrich_event_summary(players, ball_tracking, summary)

        if self.baseball_engine is not None:
            players, summary = self.baseball_engine.update(players, ball_tracking, frame_index, fps, frame_size)
            return players, enrich_event_summary(players, ball_tracking, summary)

        if self.hockey_engine is not None:
            players, summary = self.hockey_engine.update(players, ball_tracking, frame_index, fps, frame_size)
            return players, enrich_event_summary(players, ball_tracking, summary)

        if self.volleyball_engine is not None:
            players, summary = self.volleyball_engine.update(players, ball_tracking, frame_index, fps, frame_size)
            return players, enrich_event_summary(players, ball_tracking, summary)

        if self.basketball_engine is not None:
            players, summary = self.basketball_engine.update(players, ball_tracking, frame_index, fps, frame_size)
            return players, enrich_event_summary(players, ball_tracking, summary)

        for player in players:
            player["event_state"] = {
                "swing_phase": "unsupported",
                "activity_score": 0.0,
                "ball_proximity_px": None,
                "shot_label_candidate": None,
                "contact_candidate": False,
            }
        return players, enrich_event_summary(players, ball_tracking, default_event_summary(frame_index))


class TennisEventEngine:
    def __init__(self, sport_mode: str = "tennis") -> None:
        self.sport_mode = sport_mode
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
            "sport_mode": self.sport_mode,
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
        threshold_prepare = 12.0
        threshold_active = 18.0
        min_swing_duration_frames = 4
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

            duration = active_window["last_active_frame"] - active_window["start_frame"] + 1
            if duration >= min_swing_duration_frames:
                swing_event = {
                    "event_type": "swing_window",
                    "frame_index": active_window["last_active_frame"],
                    "timestamp_seconds": round(active_window["last_active_frame"] / fps, 2) if fps else 0.0,
                    "track_id": track_id,
                    "shot_label": active_window["shot_label_candidate"],
                    "start_frame": active_window["start_frame"],
                    "end_frame": active_window["last_active_frame"],
                    "duration_frames": duration,
                    "peak_activity_score": round(active_window["peak_activity_score"], 2),
                }
                self.recent_events.append(swing_event)
                current_frame_events.append(swing_event)
            del self.active_windows[track_id]

        return "idle"


class CricketEventEngine:
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
            if len(history) > 24:
                history.pop(0)

            activity_score = compute_activity_score(previous_snapshot, snapshot)
            ball_proximity_px = compute_ball_proximity(snapshot, ball_tracking)
            shot_label_candidate = (
                classify_cricket_shot(snapshot, ball_tracking, frame_size) if is_primary_player else None
            )
            contact_candidate = (
                is_cricket_contact_candidate(activity_score, ball_proximity_px, ball_tracking, frame_index)
                if is_primary_player
                else False
            )
            swing_phase = (
                self._update_stroke_window(
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
                        "event_type": "bat_contact_candidate",
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
            "sport_mode": "cricket",
            "primary_player_id": primary_player_id,
            "active_swing_player_ids": active_swing_player_ids,
            "active_swing_count": len(active_swing_player_ids),
            "current_frame_events": current_frame_events,
            "recent_events": self.recent_events[-8:],
            "recent_event_count": len(self.recent_events[-8:]),
            "contact_candidate_count": sum(
                1 for event in self.recent_events[-8:] if event["event_type"] == "bat_contact_candidate"
            ),
        }

    def _update_stroke_window(
        self,
        track_id: int,
        frame_index: int,
        fps: float,
        activity_score: float,
        shot_label_candidate: str | None,
        current_frame_events: list[dict[str, Any]],
    ) -> str:
        threshold_prepare = 8.0
        threshold_active = 14.0
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

            return "active_stroke" if activity_score >= threshold_active else "setup"

        if active_window is not None:
            if frame_index - active_window["last_active_frame"] <= 3:
                return "follow_through"

            stroke_event = {
                "event_type": "stroke_window",
                "frame_index": active_window["last_active_frame"],
                "timestamp_seconds": round(active_window["last_active_frame"] / fps, 2) if fps else 0.0,
                "track_id": track_id,
                "shot_label": active_window["shot_label_candidate"],
                "start_frame": active_window["start_frame"],
                "end_frame": active_window["last_active_frame"],
                "duration_frames": active_window["last_active_frame"] - active_window["start_frame"] + 1,
                "peak_activity_score": round(active_window["peak_activity_score"], 2),
            }
            self.recent_events.append(stroke_event)
            current_frame_events.append(stroke_event)
            del self.active_windows[track_id]

        return "idle"


class BaseballEventEngine:
    def __init__(self) -> None:
        self.player_histories: dict[int, list[dict[str, Any]]] = {}
        self.active_windows: dict[int, dict[str, Any]] = {}
        self.recent_events: list[dict[str, Any]] = []
        self.last_contact_frame_by_player: dict[int, int] = {}
        self.last_pitch_window_frame_by_player: dict[int, int] = {}

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
            if len(history) > 24:
                history.pop(0)

            activity_score = compute_activity_score(previous_snapshot, snapshot)
            ball_proximity_px = compute_ball_proximity(snapshot, ball_tracking)
            shot_label_candidate = (
                classify_baseball_swing(snapshot, ball_tracking, frame_size) if is_primary_player else None
            )
            contact_candidate = (
                is_baseball_contact_candidate(activity_score, ball_proximity_px, ball_tracking, frame_index)
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

            if is_primary_player and is_baseball_pitch_window(snapshot, ball_tracking):
                last_pitch_frame = self.last_pitch_window_frame_by_player.get(track_id, -999)
                if frame_index - last_pitch_frame >= 6:
                    pitch_event = {
                        "event_type": "pitch_window",
                        "frame_index": frame_index,
                        "timestamp_seconds": round(frame_index / fps, 2) if fps else 0.0,
                        "track_id": track_id,
                        "shot_label": shot_label_candidate,
                        "ball_proximity_px": round(ball_proximity_px, 2) if ball_proximity_px is not None else None,
                        "activity_score": round(activity_score, 2),
                        "primary_player": True,
                    }
                    self.recent_events.append(pitch_event)
                    current_frame_events.append(pitch_event)
                    self.last_pitch_window_frame_by_player[track_id] = frame_index

            if swing_phase != "idle":
                active_swing_player_ids.append(track_id)

            if contact_candidate:
                last_contact_frame = self.last_contact_frame_by_player.get(track_id, -999)
                if frame_index - last_contact_frame >= 10:
                    contact_event = {
                        "event_type": "bat_contact_candidate",
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
            "sport_mode": "baseball",
            "primary_player_id": primary_player_id,
            "active_swing_player_ids": active_swing_player_ids,
            "active_swing_count": len(active_swing_player_ids),
            "current_frame_events": current_frame_events,
            "recent_events": self.recent_events[-8:],
            "recent_event_count": len(self.recent_events[-8:]),
            "contact_candidate_count": sum(
                1 for event in self.recent_events[-8:] if event["event_type"] == "bat_contact_candidate"
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
        threshold_prepare = 9.0
        threshold_active = 15.0
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

            return "active_swing" if activity_score >= threshold_active else "load"

        if active_window is not None:
            if frame_index - active_window["last_active_frame"] <= 3:
                return "follow_through"

            swing_event = {
                "event_type": "bat_swing_window",
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


class HockeyEventEngine:
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
        possessing_player_id = find_possessing_player(players, ball_tracking)

        for player in players:
            track_id = player["track_id"]
            pose = player.get("pose")
            is_primary_player = track_id == primary_player_id
            has_possession = track_id == possessing_player_id
            if pose is None:
                player["event_state"] = {
                    "swing_phase": "idle",
                    "activity_score": 0.0,
                    "ball_proximity_px": None,
                    "shot_label_candidate": None,
                    "contact_candidate": False,
                    "possession_candidate": has_possession,
                }
                continue

            snapshot = build_player_snapshot(player, frame_index)
            history = self.player_histories.setdefault(track_id, [])
            previous_snapshot = history[-1] if history else None
            history.append(snapshot)
            if len(history) > 24:
                history.pop(0)

            activity_score = compute_activity_score(previous_snapshot, snapshot)
            ball_proximity_px = compute_ball_proximity(snapshot, ball_tracking)
            shot_label_candidate = (
                classify_hockey_play(snapshot, ball_tracking, frame_size) if is_primary_player else None
            )
            contact_candidate = (
                is_hockey_shot_candidate(activity_score, ball_proximity_px, ball_tracking, frame_index)
                if is_primary_player
                else False
            )
            stick_phase = (
                self._update_stick_window(
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

            if stick_phase != "idle":
                active_swing_player_ids.append(track_id)

            if contact_candidate:
                last_contact_frame = self.last_contact_frame_by_player.get(track_id, -999)
                if frame_index - last_contact_frame >= 10:
                    contact_event = {
                        "event_type": "stick_contact_candidate",
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
                "swing_phase": stick_phase,
                "activity_score": round(activity_score, 2),
                "ball_proximity_px": round(ball_proximity_px, 2) if ball_proximity_px is not None else None,
                "shot_label_candidate": shot_label_candidate,
                "contact_candidate": contact_candidate,
                "possession_candidate": has_possession,
                "primary_player": is_primary_player,
            }

        self.recent_events = self.recent_events[-12:]
        return players, {
            "sport_mode": "hockey",
            "primary_player_id": primary_player_id,
            "active_swing_player_ids": active_swing_player_ids,
            "active_swing_count": len(active_swing_player_ids),
            "current_frame_events": current_frame_events,
            "recent_events": self.recent_events[-8:],
            "recent_event_count": len(self.recent_events[-8:]),
            "contact_candidate_count": sum(
                1 for event in self.recent_events[-8:] if event["event_type"] == "stick_contact_candidate"
            ),
            "possessing_player_id": possessing_player_id,
        }

    def _update_stick_window(
        self,
        track_id: int,
        frame_index: int,
        fps: float,
        activity_score: float,
        shot_label_candidate: str | None,
        current_frame_events: list[dict[str, Any]],
    ) -> str:
        threshold_prepare = 9.0
        threshold_active = 16.0
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

            return "active_shot" if activity_score >= threshold_active else "wind_up"

        if active_window is not None:
            if frame_index - active_window["last_active_frame"] <= 3:
                return "follow_through"

            stick_event = {
                "event_type": "stick_motion_window",
                "frame_index": active_window["last_active_frame"],
                "timestamp_seconds": round(active_window["last_active_frame"] / fps, 2) if fps else 0.0,
                "track_id": track_id,
                "shot_label": active_window["shot_label_candidate"],
                "start_frame": active_window["start_frame"],
                "end_frame": active_window["last_active_frame"],
                "duration_frames": active_window["last_active_frame"] - active_window["start_frame"] + 1,
                "peak_activity_score": round(active_window["peak_activity_score"], 2),
            }
            self.recent_events.append(stick_event)
            current_frame_events.append(stick_event)
            del self.active_windows[track_id]

        return "idle"


class VolleyballEventEngine:
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
            if len(history) > 24:
                history.pop(0)

            activity_score = compute_activity_score(previous_snapshot, snapshot)
            ball_proximity_px = compute_ball_proximity(snapshot, ball_tracking)
            shot_label_candidate = (
                classify_volleyball_play(snapshot, previous_snapshot, ball_tracking, frame_size)
                if is_primary_player
                else None
            )
            contact_candidate = (
                is_volleyball_contact_candidate(activity_score, ball_proximity_px, ball_tracking, frame_index)
                if is_primary_player
                else False
            )
            play_phase = (
                self._update_action_window(
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

            if play_phase != "idle":
                active_swing_player_ids.append(track_id)

            if contact_candidate:
                last_contact_frame = self.last_contact_frame_by_player.get(track_id, -999)
                if frame_index - last_contact_frame >= 8:
                    contact_event = {
                        "event_type": "ball_contact_candidate",
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
                "swing_phase": play_phase,
                "activity_score": round(activity_score, 2),
                "ball_proximity_px": round(ball_proximity_px, 2) if ball_proximity_px is not None else None,
                "shot_label_candidate": shot_label_candidate,
                "contact_candidate": contact_candidate,
                "primary_player": is_primary_player,
            }

        self.recent_events = self.recent_events[-12:]
        return players, {
            "sport_mode": "volleyball",
            "primary_player_id": primary_player_id,
            "active_swing_player_ids": active_swing_player_ids,
            "active_swing_count": len(active_swing_player_ids),
            "current_frame_events": current_frame_events,
            "recent_events": self.recent_events[-8:],
            "recent_event_count": len(self.recent_events[-8:]),
            "contact_candidate_count": sum(
                1 for event in self.recent_events[-8:] if event["event_type"] == "ball_contact_candidate"
            ),
        }

    def _update_action_window(
        self,
        track_id: int,
        frame_index: int,
        fps: float,
        activity_score: float,
        shot_label_candidate: str | None,
        current_frame_events: list[dict[str, Any]],
    ) -> str:
        threshold_prepare = 9.0
        threshold_active = 15.0
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

            return "active_play" if activity_score >= threshold_active else "approach"

        if active_window is not None:
            if frame_index - active_window["last_active_frame"] <= 3:
                return "follow_through"

            play_event = {
                "event_type": volleyball_event_type_for_label(active_window["shot_label_candidate"]),
                "frame_index": active_window["last_active_frame"],
                "timestamp_seconds": round(active_window["last_active_frame"] / fps, 2) if fps else 0.0,
                "track_id": track_id,
                "shot_label": active_window["shot_label_candidate"],
                "start_frame": active_window["start_frame"],
                "end_frame": active_window["last_active_frame"],
                "duration_frames": active_window["last_active_frame"] - active_window["start_frame"] + 1,
                "peak_activity_score": round(active_window["peak_activity_score"], 2),
            }
            self.recent_events.append(play_event)
            current_frame_events.append(play_event)
            del self.active_windows[track_id]

        return "idle"


class BasketballEventEngine:
    def __init__(self) -> None:
        self.player_histories: dict[int, list[dict[str, Any]]] = {}
        self.active_windows: dict[int, dict[str, Any]] = {}
        self.recent_events: list[dict[str, Any]] = []
        self.last_control_frame_by_player: dict[int, int] = {}
        self.last_dribble_frame_by_player: dict[int, int] = {}
        self.last_release_frame_by_player: dict[int, int] = {}
        self.last_ball_handler_id: int | None = None
        self.active_possession_window: dict[str, Any] | None = None
        self.possession_window_count = 0
        self.dribble_count_estimate = 0
        self.shot_release_count = 0

    def update(
        self,
        players: list[dict[str, Any]],
        ball_tracking: dict[str, Any],
        frame_index: int,
        fps: float,
        frame_size: dict[str, int],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        current_frame_events: list[dict[str, Any]] = []
        active_swing_player_ids: list[int] = []
        snapshots_by_player: dict[int, dict[str, Any]] = {}
        control_profiles: dict[int, dict[str, Any]] = {}

        for player in players:
            track_id = player["track_id"]
            pose = player.get("pose")
            if pose is None:
                continue

            snapshot = build_player_snapshot(player, frame_index)
            history = self.player_histories.setdefault(track_id, [])
            history.append(snapshot)
            if len(history) > 24:
                history.pop(0)

            snapshots_by_player[track_id] = snapshot
            control_profiles[track_id] = compute_basketball_control_profile(
                snapshot,
                ball_tracking,
                frame_size=frame_size,
            )

        ball_handler_id = self._select_ball_handler(players, control_profiles, ball_tracking)
        primary_player_id = ball_handler_id if ball_handler_id is not None else choose_primary_player(players)
        self._update_possession_window(
            ball_handler_id,
            frame_index,
            fps,
            control_profiles,
            current_frame_events,
        )

        for player in players:
            track_id = player["track_id"]
            pose = player.get("pose")
            is_primary_player = track_id == primary_player_id
            possession_candidate = track_id == ball_handler_id
            if pose is None:
                player["event_state"] = {
                    "swing_phase": "idle",
                    "activity_score": 0.0,
                    "ball_proximity_px": None,
                    "ball_control_score": 0.0,
                    "ball_control_zone": "none",
                    "ball_height_band": None,
                    "shot_label_candidate": None,
                    "contact_candidate": False,
                    "release_candidate": False,
                    "primary_player": is_primary_player,
                    "possession_candidate": possession_candidate,
                }
                continue

            history = self.player_histories.get(track_id, [])
            snapshot = snapshots_by_player.get(track_id)
            previous_snapshot = history[-2] if len(history) >= 2 else None
            activity_score = compute_activity_score(previous_snapshot, snapshot)
            control_profile = control_profiles.get(
                track_id,
                {
                    "ball_proximity_px": None,
                    "control_score": 0.0,
                    "control_zone": "loose",
                    "ball_height_band": None,
                    "closest_hand_distance_px": None,
                },
            )
            ball_proximity_px = control_profile.get("ball_proximity_px")
            shot_label_candidate = (
                classify_basketball_play(
                    snapshot,
                    previous_snapshot,
                    ball_tracking,
                    frame_size,
                    control_profile=control_profile,
                )
                if (is_primary_player or possession_candidate)
                else None
            )
            control_candidate = is_basketball_control_candidate(
                ball_proximity_px,
                ball_tracking,
                possession_candidate=possession_candidate,
                control_profile=control_profile,
            )
            release_candidate = is_basketball_shot_release_candidate(
                shot_label_candidate,
                control_profile,
                ball_tracking,
            )
            dribble_bounce_candidate = is_basketball_dribble_bounce_candidate(
                shot_label_candidate,
                control_profile,
                ball_tracking,
            )
            play_phase = (
                self._update_action_window(
                    track_id,
                    frame_index,
                    fps,
                    activity_score,
                    float(control_profile.get("control_score", 0.0) or 0.0),
                    shot_label_candidate,
                    current_frame_events,
                )
                if (is_primary_player or possession_candidate)
                else "idle"
            )

            if play_phase != "idle":
                active_swing_player_ids.append(track_id)

            if control_candidate:
                last_control_frame = self.last_control_frame_by_player.get(track_id, -999)
                if frame_index - last_control_frame >= 8:
                    control_event = {
                        "event_type": "ball_control_candidate",
                        "frame_index": frame_index,
                        "timestamp_seconds": round(frame_index / fps, 2) if fps else 0.0,
                        "track_id": track_id,
                        "shot_label": shot_label_candidate,
                        "ball_proximity_px": round(ball_proximity_px, 2) if ball_proximity_px is not None else None,
                        "activity_score": round(activity_score, 2),
                        "primary_player": is_primary_player,
                    }
                    self.recent_events.append(control_event)
                    current_frame_events.append(control_event)
                    self.last_control_frame_by_player[track_id] = frame_index

            if dribble_bounce_candidate:
                last_dribble_frame = self.last_dribble_frame_by_player.get(track_id, -999)
                if frame_index - last_dribble_frame >= 5:
                    dribble_event = {
                        "event_type": "dribble_bounce_candidate",
                        "frame_index": frame_index,
                        "timestamp_seconds": round(frame_index / fps, 2) if fps else 0.0,
                        "track_id": track_id,
                        "shot_label": shot_label_candidate,
                        "ball_proximity_px": round(ball_proximity_px, 2) if ball_proximity_px is not None else None,
                        "control_score": round(float(control_profile.get("control_score", 0.0) or 0.0), 2),
                    }
                    self.recent_events.append(dribble_event)
                    current_frame_events.append(dribble_event)
                    self.last_dribble_frame_by_player[track_id] = frame_index
                    self.dribble_count_estimate += 1

            if release_candidate:
                last_release_frame = self.last_release_frame_by_player.get(track_id, -999)
                if frame_index - last_release_frame >= 7:
                    release_event = {
                        "event_type": "shot_release_candidate",
                        "frame_index": frame_index,
                        "timestamp_seconds": round(frame_index / fps, 2) if fps else 0.0,
                        "track_id": track_id,
                        "shot_label": shot_label_candidate,
                        "ball_proximity_px": round(ball_proximity_px, 2) if ball_proximity_px is not None else None,
                        "control_score": round(float(control_profile.get("control_score", 0.0) or 0.0), 2),
                    }
                    self.recent_events.append(release_event)
                    current_frame_events.append(release_event)
                    self.last_release_frame_by_player[track_id] = frame_index
                    self.shot_release_count += 1

            player["event_state"] = {
                "swing_phase": play_phase,
                "activity_score": round(activity_score, 2),
                "ball_proximity_px": round(ball_proximity_px, 2) if ball_proximity_px is not None else None,
                "ball_control_score": round(float(control_profile.get("control_score", 0.0) or 0.0), 2),
                "ball_control_zone": control_profile.get("control_zone"),
                "ball_height_band": control_profile.get("ball_height_band"),
                "shot_label_candidate": shot_label_candidate,
                "contact_candidate": control_candidate,
                "release_candidate": release_candidate,
                "primary_player": is_primary_player,
                "possession_candidate": possession_candidate,
            }

        self.recent_events = self.recent_events[-12:]
        ball_handler_profile = control_profiles.get(ball_handler_id, {}) if ball_handler_id is not None else {}
        return players, {
            "sport_mode": "basketball",
            "primary_player_id": primary_player_id,
            "ball_handler_candidate_id": ball_handler_id,
            "ball_handler_control_score": round(
                float(ball_handler_profile.get("control_score", 0.0) or 0.0),
                2,
            ) if ball_handler_id is not None else None,
            "ball_handler_control_zone": ball_handler_profile.get("control_zone") if ball_handler_id is not None else None,
            "active_swing_player_ids": active_swing_player_ids,
            "active_swing_count": len(active_swing_player_ids),
            "current_frame_events": current_frame_events,
            "recent_events": self.recent_events[-8:],
            "recent_event_count": len(self.recent_events[-8:]),
            "contact_candidate_count": sum(
                1 for event in self.recent_events[-8:] if event["event_type"] == "ball_control_candidate"
            ),
            "possession_window_count": self.possession_window_count,
            "dribble_count_estimate": self.dribble_count_estimate,
            "shot_release_count": self.shot_release_count,
        }

    def _update_action_window(
        self,
        track_id: int,
        frame_index: int,
        fps: float,
        activity_score: float,
        control_score: float,
        shot_label_candidate: str | None,
        current_frame_events: list[dict[str, Any]],
    ) -> str:
        threshold_prepare = 10.0
        threshold_active = 16.0
        active_window = self.active_windows.get(track_id)

        if activity_score >= threshold_prepare and (control_score >= 24.0 or shot_label_candidate is not None):
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

            return "active_play" if activity_score >= threshold_active else "setup"

        if active_window is not None:
            if frame_index - active_window["last_active_frame"] <= 3:
                return "follow_through"

            duration = active_window["last_active_frame"] - active_window["start_frame"] + 1
            if duration >= 3 or active_window["shot_label_candidate"] is not None:
                play_event = {
                    "event_type": basketball_event_type_for_label(active_window["shot_label_candidate"]),
                    "frame_index": active_window["last_active_frame"],
                    "timestamp_seconds": round(active_window["last_active_frame"] / fps, 2) if fps else 0.0,
                    "track_id": track_id,
                    "shot_label": active_window["shot_label_candidate"],
                    "start_frame": active_window["start_frame"],
                    "end_frame": active_window["last_active_frame"],
                    "duration_frames": duration,
                    "peak_activity_score": round(active_window["peak_activity_score"], 2),
                }
                self.recent_events.append(play_event)
                current_frame_events.append(play_event)
            del self.active_windows[track_id]

        return "idle"

    def _select_ball_handler(
        self,
        players: list[dict[str, Any]],
        control_profiles: dict[int, dict[str, Any]],
        ball_tracking: dict[str, Any],
    ) -> int | None:
        best_track_id: int | None = None
        best_score = -1.0

        for player in players:
            track_id = player["track_id"]
            control_profile = control_profiles.get(track_id)
            if control_profile is None:
                continue

            score = float(control_profile.get("control_score", 0.0) or 0.0)
            if track_id == self.last_ball_handler_id:
                score += 10.0
            if ball_tracking.get("detected_this_frame"):
                score += 4.0

            if score > best_score:
                best_score = score
                best_track_id = track_id

        if best_track_id is None:
            self.last_ball_handler_id = None
            return None

        previous_id = self.last_ball_handler_id
        if previous_id is not None and previous_id in control_profiles:
            previous_score = float(control_profiles[previous_id].get("control_score", 0.0) or 0.0)
            if previous_id != best_track_id and previous_score >= max(28.0, best_score - 8.0):
                best_track_id = previous_id
                best_score = previous_score

        if best_score < 30.0:
            fallback_player_id = find_possessing_player(players, ball_tracking)
            if fallback_player_id is not None:
                fallback_profile = control_profiles.get(fallback_player_id, {})
                if float(fallback_profile.get("control_score", 0.0) or 0.0) >= 22.0:
                    best_track_id = fallback_player_id
                    best_score = float(fallback_profile.get("control_score", 0.0) or 0.0)

        if best_score < 24.0:
            self.last_ball_handler_id = None
            return None

        self.last_ball_handler_id = best_track_id
        return best_track_id

    def _update_possession_window(
        self,
        ball_handler_id: int | None,
        frame_index: int,
        fps: float,
        control_profiles: dict[int, dict[str, Any]],
        current_frame_events: list[dict[str, Any]],
    ) -> None:
        if ball_handler_id is None:
            if self.active_possession_window is not None and frame_index - self.active_possession_window["last_frame"] > 2:
                self._close_possession_window(fps, current_frame_events)
            return

        control_profile = control_profiles.get(ball_handler_id, {})
        control_score = round(float(control_profile.get("control_score", 0.0) or 0.0), 2)
        control_zone = control_profile.get("control_zone")
        active_window = self.active_possession_window

        if active_window is None:
            self.active_possession_window = {
                "track_id": ball_handler_id,
                "start_frame": frame_index,
                "last_frame": frame_index,
                "peak_control_score": control_score,
                "control_zone": control_zone,
            }
            return

        if active_window["track_id"] == ball_handler_id:
            active_window["last_frame"] = frame_index
            active_window["peak_control_score"] = max(active_window["peak_control_score"], control_score)
            if control_zone is not None:
                active_window["control_zone"] = control_zone
            return

        self._close_possession_window(fps, current_frame_events)
        self.active_possession_window = {
            "track_id": ball_handler_id,
            "start_frame": frame_index,
            "last_frame": frame_index,
            "peak_control_score": control_score,
            "control_zone": control_zone,
        }

    def _close_possession_window(
        self,
        fps: float,
        current_frame_events: list[dict[str, Any]],
    ) -> None:
        active_window = self.active_possession_window
        if active_window is None:
            return

        duration = active_window["last_frame"] - active_window["start_frame"] + 1
        if duration >= 4:
            possession_event = {
                "event_type": "possession_window",
                "frame_index": active_window["last_frame"],
                "timestamp_seconds": round(active_window["last_frame"] / fps, 2) if fps else 0.0,
                "track_id": active_window["track_id"],
                "shot_label": None,
                "start_frame": active_window["start_frame"],
                "end_frame": active_window["last_frame"],
                "duration_frames": duration,
                "peak_control_score": round(active_window["peak_control_score"], 2),
                "control_zone": active_window.get("control_zone"),
            }
            self.recent_events.append(possession_event)
            current_frame_events.append(possession_event)
            self.possession_window_count += 1

        self.active_possession_window = None


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

    if activity_score < 12:
        return False

    # Require an actual ball direction change — avoids constant firing at session
    # start and between rallies when no direction change has been recorded yet.
    latest_direction_change = ball_tracking.get("latest_direction_change")
    if latest_direction_change is None:
        return False

    return abs(frame_index - latest_direction_change["frame_index"]) <= 4


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
        # Distinguish serve (ball rising — toss) from overhead smash (ball descending).
        ball_history = ball_tracking.get("history", [])
        recent_y = [
            entry["smoothed_center"][1]
            for entry in ball_history[-4:]
            if entry.get("smoothed_center")
        ]
        ball_descending = len(recent_y) >= 2 and recent_y[-1] > recent_y[0]
        return "overhead_candidate" if ball_descending else "serve_candidate"

    if player_center_y < frame_height * 0.45:
        return "volley_candidate"
    if hitting_side == "right":
        return "forehand_candidate"
    if hitting_side == "left":
        return "backhand_candidate"
    return None


def is_cricket_contact_candidate(
    activity_score: float,
    ball_proximity_px: float | None,
    ball_tracking: dict[str, Any],
    frame_index: int,
) -> bool:
    if ball_proximity_px is None or ball_proximity_px > 70:
        return False

    if activity_score < 8:
        return False

    latest_direction_change = ball_tracking.get("latest_direction_change")
    if latest_direction_change is None:
        return True

    return abs(frame_index - latest_direction_change["frame_index"]) <= 3


def classify_cricket_shot(
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
    shoulder_x, shoulder_y = shoulder_mid
    hip_y = hip_mid[1]
    frame_width = frame_size["width"]
    lateral_offset = ball_x - shoulder_x
    hitting_side = nearest_side(ball_center, left_wrist, right_wrist)

    if ball_y >= hip_y + 12:
        return "defensive_block_candidate"
    if ball_y <= shoulder_y - 18:
        return "cut_or_loft_candidate"
    if lateral_offset > frame_width * 0.06 and hitting_side == "right":
        return "off_drive_candidate"
    if lateral_offset < -(frame_width * 0.06) and hitting_side == "left":
        return "leg_side_candidate"
    return "straight_bat_candidate"


def is_baseball_contact_candidate(
    activity_score: float,
    ball_proximity_px: float | None,
    ball_tracking: dict[str, Any],
    frame_index: int,
) -> bool:
    if ball_proximity_px is None or ball_proximity_px > 75:
        return False

    if activity_score < 9:
        return False

    latest_direction_change = ball_tracking.get("latest_direction_change")
    if latest_direction_change is None:
        return True

    return abs(frame_index - latest_direction_change["frame_index"]) <= 3


def is_baseball_pitch_window(
    snapshot: dict[str, Any],
    ball_tracking: dict[str, Any],
) -> bool:
    ball_center = ball_tracking.get("smoothed_center")
    shoulder_mid = snapshot.get("shoulder_mid")
    hip_mid = snapshot.get("hip_mid")
    if ball_center is None or shoulder_mid is None or hip_mid is None:
        return False

    ball_x, ball_y = ball_center
    center_x, _ = snapshot["center"]
    return shoulder_mid[1] - 24 <= ball_y <= hip_mid[1] + 18 and abs(ball_x - center_x) <= 95


def classify_baseball_swing(
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
    shoulder_x, shoulder_y = shoulder_mid
    hip_y = hip_mid[1]
    frame_width = frame_size["width"]
    lateral_offset = ball_x - shoulder_x
    hitting_side = nearest_side(ball_center, left_wrist, right_wrist)

    if ball_y < shoulder_y - 20:
        return "uppercut_candidate"
    if ball_y > hip_y + 18:
        return "low_ball_candidate"
    if lateral_offset > frame_width * 0.08 and hitting_side == "right":
        return "pull_side_candidate"
    if lateral_offset < -(frame_width * 0.08) and hitting_side == "left":
        return "opposite_field_candidate"
    return "level_swing_candidate"


def is_hockey_shot_candidate(
    activity_score: float,
    ball_proximity_px: float | None,
    ball_tracking: dict[str, Any],
    frame_index: int,
) -> bool:
    if ball_proximity_px is None or ball_proximity_px > 80:
        return False
    if activity_score < 9:
        return False
    latest_direction_change = ball_tracking.get("latest_direction_change")
    if latest_direction_change is None:
        return True
    return abs(frame_index - latest_direction_change["frame_index"]) <= 3


def is_volleyball_contact_candidate(
    activity_score: float,
    ball_proximity_px: float | None,
    ball_tracking: dict[str, Any],
    frame_index: int,
) -> bool:
    if ball_proximity_px is None or ball_proximity_px > 85:
        return False
    if activity_score < 10:
        return False

    latest_direction_change = ball_tracking.get("latest_direction_change")
    if latest_direction_change is None:
        return True
    return abs(frame_index - latest_direction_change["frame_index"]) <= 4


def is_basketball_control_candidate(
    ball_proximity_px: float | None,
    ball_tracking: dict[str, Any],
    *,
    possession_candidate: bool,
    control_profile: dict[str, Any],
) -> bool:
    if not possession_candidate:
        return False
    if ball_proximity_px is None or ball_proximity_px > 95:
        return False
    if float(control_profile.get("control_score", 0.0) or 0.0) < 32.0:
        return False
    return bool(ball_tracking.get("detected_this_frame") or ball_tracking.get("active"))


def classify_hockey_play(
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
    shoulder_x, shoulder_y = shoulder_mid
    hip_y = hip_mid[1]
    frame_width = frame_size["width"]
    lateral_offset = ball_x - shoulder_x
    hitting_side = nearest_side(ball_center, left_wrist, right_wrist)

    if ball_y >= hip_y - 10:
        if abs(lateral_offset) > frame_width * 0.05:
            return "slap_shot_candidate"
        return "wrist_shot_candidate"

    if ball_y >= shoulder_y + 15:
        return "backhand_candidate" if hitting_side == "left" else "forehand_pass_candidate"

    return "deflection_candidate"


def classify_volleyball_play(
    snapshot: dict[str, Any],
    previous_snapshot: dict[str, Any] | None,
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
    shoulder_x, shoulder_y = shoulder_mid
    frame_height = frame_size["height"]
    frame_width = frame_size["width"]
    lateral_offset = ball_x - shoulder_x
    wrists_above_shoulders = sum(
        1 for wrist in (left_wrist, right_wrist) if wrist is not None and wrist[1] <= shoulder_y - 8
    )
    player_lift = 0.0
    if previous_snapshot is not None:
        player_lift = float(previous_snapshot["center"][1] - snapshot["center"][1])

    if wrists_above_shoulders >= 2 and abs(lateral_offset) <= frame_width * 0.05:
        if player_lift > 10 and ball_y <= shoulder_y - 20:
            return "block_candidate"
        return "set_candidate"

    if ball_y <= frame_height * 0.28 and wrists_above_shoulders >= 1:
        return "serve_candidate"

    if wrists_above_shoulders >= 1 and player_lift > 6 and ball_y <= shoulder_y + 8:
        return "spike_candidate"

    if ball_y >= hip_mid[1] - 8:
        return "dig_candidate"

    if wrists_above_shoulders >= 1 and ball_y <= shoulder_y + 18:
        return "jump_attack_candidate"

    return None


def classify_basketball_play(
    snapshot: dict[str, Any],
    previous_snapshot: dict[str, Any] | None,
    ball_tracking: dict[str, Any],
    frame_size: dict[str, int],
    *,
    control_profile: dict[str, Any],
) -> str | None:
    ball_center = ball_tracking.get("detected_center") or ball_tracking.get("smoothed_center")
    if ball_center is None:
        return None

    shoulder_mid = snapshot.get("shoulder_mid")
    hip_mid = snapshot.get("hip_mid")
    left_wrist = snapshot.get("left_wrist")
    right_wrist = snapshot.get("right_wrist")
    if shoulder_mid is None or hip_mid is None:
        return None

    ball_x, ball_y = ball_center
    shoulder_x, shoulder_y = shoulder_mid
    hip_y = hip_mid[1]
    frame_width = frame_size["width"]
    lateral_offset = ball_x - shoulder_x
    wrists_above_shoulders = sum(
        1 for wrist in (left_wrist, right_wrist) if wrist is not None and wrist[1] <= shoulder_y - 10
    )
    ball_motion = summarize_ball_motion(ball_tracking)
    control_score = float(control_profile.get("control_score", 0.0) or 0.0)
    player_shift = 0.0
    if previous_snapshot is not None:
        player_shift = float(
            np.sqrt(
                (snapshot["center"][0] - previous_snapshot["center"][0]) ** 2
                + (snapshot["center"][1] - previous_snapshot["center"][1]) ** 2
            )
        )

    if wrists_above_shoulders >= 1 and ball_y <= shoulder_y - 12 and ball_motion["vertical_bias"] <= -8:
        return "shot_attempt_candidate"
    if control_score >= 38.0 and player_shift > 12 and ball_y <= hip_y + 18:
        return "drive_candidate"
    if (
        control_score >= 28.0
        and abs(lateral_offset) >= frame_width * 0.08
        and shoulder_y - 16 <= ball_y <= hip_y + 20
        and abs(ball_motion["horizontal_bias"]) >= frame_width * 0.02
    ):
        return "pass_candidate"
    if (
        control_score >= 30.0
        and hip_y - 6 <= ball_y <= hip_y + 55
        and abs(lateral_offset) <= frame_width * 0.06
        and (ball_motion["down_then_up"] or ball_motion["vertical_bias"] >= 8)
    ):
        return "dribble_candidate"
    if (
        ball_y <= shoulder_y + 6
        and player_shift <= 8
        and ball_motion["up_then_down"]
    ):
        return "rebound_candidate"
    return None


def compute_basketball_control_profile(
    snapshot: dict[str, Any],
    ball_tracking: dict[str, Any],
    *,
    frame_size: dict[str, int],
) -> dict[str, Any]:
    ball_center = ball_tracking.get("detected_center") or ball_tracking.get("smoothed_center")
    if ball_center is None:
        return {
            "ball_proximity_px": None,
            "closest_hand_distance_px": None,
            "torso_distance_px": None,
            "control_score": 0.0,
            "control_zone": "none",
            "ball_height_band": None,
        }

    left_wrist = snapshot.get("left_wrist")
    right_wrist = snapshot.get("right_wrist")
    shoulder_mid = snapshot.get("shoulder_mid")
    hip_mid = snapshot.get("hip_mid")

    hand_distances = [
        euclidean_distance(ball_center, wrist)
        for wrist in (left_wrist, right_wrist)
        if wrist is not None
    ]
    closest_hand_distance = min(hand_distances) if hand_distances else None
    torso_distance = euclidean_distance(ball_center, snapshot["center"])
    ball_proximity_px = compute_ball_proximity(snapshot, ball_tracking)

    control_score = 0.0
    if closest_hand_distance is not None:
        control_score += max(0.0, 70.0 - closest_hand_distance) * 1.15
    control_score += max(0.0, 115.0 - torso_distance) * 0.32

    if point_in_expanded_bbox(ball_center, snapshot["bbox"], margin=18):
        control_score += 10.0

    ball_height_band = None
    if shoulder_mid is not None and hip_mid is not None:
        ball_height_band = basketball_ball_height_band(ball_center[1], shoulder_mid[1], hip_mid[1])
        if ball_height_band in {"chest", "waist", "below_waist"}:
            control_score += 8.0
        elif ball_height_band == "above_shoulders":
            control_score += 5.0

    if not ball_tracking.get("detected_this_frame"):
        control_score *= 0.88

    control_zone = "loose"
    if closest_hand_distance is not None and closest_hand_distance <= 26:
        control_zone = "hands"
    elif torso_distance <= 60 and ball_height_band in {"chest", "waist", "below_waist"}:
        control_zone = "pocket"
    elif closest_hand_distance is not None and closest_hand_distance <= 72:
        control_zone = "extended"

    return {
        "ball_proximity_px": round(ball_proximity_px, 2) if ball_proximity_px is not None else None,
        "closest_hand_distance_px": round(closest_hand_distance, 2) if closest_hand_distance is not None else None,
        "torso_distance_px": round(torso_distance, 2),
        "control_score": round(min(control_score, 100.0), 2),
        "control_zone": control_zone,
        "ball_height_band": ball_height_band,
    }


def summarize_ball_motion(ball_tracking: dict[str, Any], *, window: int = 6) -> dict[str, float | bool]:
    history = [
        entry
        for entry in ball_tracking.get("history", [])
        if entry.get("smoothed_center") is not None
    ]
    if len(history) < 2:
        return {
            "horizontal_bias": 0.0,
            "vertical_bias": 0.0,
            "down_then_up": False,
            "up_then_down": False,
        }

    recent = history[-window:]
    first_center = recent[0]["smoothed_center"]
    last_center = recent[-1]["smoothed_center"]
    x_deltas = [
        recent[index + 1]["smoothed_center"][0] - recent[index]["smoothed_center"][0]
        for index in range(len(recent) - 1)
    ]
    y_deltas = [
        recent[index + 1]["smoothed_center"][1] - recent[index]["smoothed_center"][1]
        for index in range(len(recent) - 1)
    ]
    down_then_up = any(delta >= 3 for delta in y_deltas[:-1]) and any(delta <= -3 for delta in y_deltas[1:])
    up_then_down = any(delta <= -3 for delta in y_deltas[:-1]) and any(delta >= 3 for delta in y_deltas[1:])
    return {
        "horizontal_bias": round(float(last_center[0] - first_center[0]), 2),
        "vertical_bias": round(float(last_center[1] - first_center[1]), 2),
        "down_then_up": down_then_up,
        "up_then_down": up_then_down,
    }


def is_basketball_dribble_bounce_candidate(
    shot_label_candidate: str | None,
    control_profile: dict[str, Any],
    ball_tracking: dict[str, Any],
) -> bool:
    if shot_label_candidate != "dribble_candidate":
        return False
    if float(control_profile.get("control_score", 0.0) or 0.0) < 30.0:
        return False
    if control_profile.get("ball_height_band") not in {"waist", "below_waist"}:
        return False

    ball_motion = summarize_ball_motion(ball_tracking)
    return bool(ball_motion["down_then_up"])


def is_basketball_shot_release_candidate(
    shot_label_candidate: str | None,
    control_profile: dict[str, Any],
    ball_tracking: dict[str, Any],
) -> bool:
    if shot_label_candidate != "shot_attempt_candidate":
        return False
    if control_profile.get("ball_height_band") != "above_shoulders":
        return False
    if float(control_profile.get("control_score", 0.0) or 0.0) < 24.0:
        return False

    ball_motion = summarize_ball_motion(ball_tracking)
    return bool(ball_motion["vertical_bias"] <= -12)


def volleyball_event_type_for_label(shot_label: str | None) -> str:
    mapping = {
        "serve_candidate": "serve_window",
        "set_candidate": "set_window",
        "spike_candidate": "spike_window",
        "block_candidate": "block_window",
        "dig_candidate": "dig_candidate",
        "jump_attack_candidate": "jump_attack_candidate",
    }
    return mapping.get(shot_label, "volleyball_action_window")


def basketball_event_type_for_label(shot_label: str | None) -> str:
    mapping = {
        "dribble_candidate": "dribble_window",
        "pass_candidate": "pass_window",
        "drive_candidate": "drive_window",
        "shot_attempt_candidate": "shot_attempt_window",
        "rebound_candidate": "rebound_candidate",
    }
    return mapping.get(shot_label, "basketball_action_window")


def find_possessing_player(players: list[dict[str, Any]], ball_tracking: dict[str, Any]) -> int | None:
    ball_center = ball_tracking.get("smoothed_center")
    if ball_center is None or not players:
        return None

    min_dist: float | None = None
    possessing_id: int | None = None
    for player in players:
        dist = euclidean_distance(ball_center, player["center"])
        if min_dist is None or dist < min_dist:
            min_dist = dist
            possessing_id = player["track_id"]

    if min_dist is not None and min_dist <= 120:
        return possessing_id
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
        "action_window_count": 0,
        "dominant_event_type": None,
        "dominant_shot_label": None,
        "confidence_score": 0.0,
        "confidence_label": "low",
        "event_evidence": {
            "ball_track_active": False,
            "tracked_player_count": 0,
            "primary_activity_score": 0.0,
            "avg_recent_activity_score": 0.0,
            "avg_recent_ball_proximity_px": None,
            "shot_label_variety": 0,
        },
    }


def enrich_event_summary(
    players: list[dict[str, Any]],
    ball_tracking: dict[str, Any],
    summary: dict[str, Any],
) -> dict[str, Any]:
    enriched = dict(summary)
    recent_events = list(enriched.get("recent_events", []))
    current_frame_events = list(enriched.get("current_frame_events", []))
    combined_events = [*recent_events, *current_frame_events]

    event_counter = Counter(
        str(event.get("event_type") or "unknown")
        for event in combined_events
        if event.get("event_type")
    )
    shot_counter = Counter(
        str(event.get("shot_label"))
        for event in combined_events
        if event.get("shot_label")
    )

    primary_player_id = enriched.get("primary_player_id")
    primary_player = next((player for player in players if player.get("track_id") == primary_player_id), None)
    primary_state = (primary_player.get("event_state") or {}) if primary_player else {}

    activity_values = [
        float(event.get("activity_score"))
        for event in combined_events
        if event.get("activity_score") is not None
    ]
    proximity_values = [
        float(event.get("ball_proximity_px"))
        for event in combined_events
        if event.get("ball_proximity_px") is not None
    ]
    tracked_player_count = sum(1 for player in players if player.get("pose") is not None)
    ball_track_active = bool(ball_tracking.get("active"))
    recent_event_count = int(enriched.get("recent_event_count", 0) or 0)
    contact_candidate_count = int(enriched.get("contact_candidate_count", 0) or 0)
    active_swing_count = int(enriched.get("active_swing_count", 0) or 0)
    shot_label_variety = len(shot_counter)

    confidence_score = 0.0
    confidence_score += 0.22 if ball_track_active else 0.0
    confidence_score += min(recent_event_count, 4) * 0.1
    confidence_score += min(contact_candidate_count, 2) * 0.14
    confidence_score += 0.12 if active_swing_count > 0 else 0.0
    confidence_score += 0.14 if shot_counter else 0.0
    confidence_score += 0.08 if tracked_player_count > 0 else 0.0
    confidence_score += 0.08 if float(primary_state.get("activity_score") or 0.0) >= 12.0 else 0.0
    if proximity_values:
        confidence_score += 0.12 if min(proximity_values) <= 120.0 else 0.06
    confidence_score = round(min(confidence_score, 1.0), 2)

    if confidence_score >= 0.72:
        confidence_label = "high"
    elif confidence_score >= 0.42:
        confidence_label = "medium"
    else:
        confidence_label = "low"

    enriched["action_window_count"] = sum(
        count for event_type, count in event_counter.items() if "window" in event_type
    )
    enriched["dominant_event_type"] = event_counter.most_common(1)[0][0] if event_counter else None
    enriched["dominant_shot_label"] = shot_counter.most_common(1)[0][0] if shot_counter else None
    enriched["confidence_score"] = confidence_score
    enriched["confidence_label"] = confidence_label
    enriched["event_evidence"] = {
        "ball_track_active": ball_track_active,
        "tracked_player_count": tracked_player_count,
        "primary_activity_score": round(float(primary_state.get("activity_score") or 0.0), 2),
        "avg_recent_activity_score": round(sum(activity_values) / len(activity_values), 2) if activity_values else 0.0,
        "avg_recent_ball_proximity_px": round(sum(proximity_values) / len(proximity_values), 2) if proximity_values else None,
        "shot_label_variety": shot_label_variety,
    }
    return enriched


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


def basketball_ball_height_band(ball_y: float, shoulder_y: float, hip_y: float) -> str:
    if ball_y <= shoulder_y - 10:
        return "above_shoulders"
    if ball_y <= shoulder_y + 28:
        return "chest"
    if ball_y <= hip_y + 10:
        return "waist"
    return "below_waist"


def point_in_expanded_bbox(
    point: list[int] | tuple[float, float],
    bbox: list[int],
    *,
    margin: int = 0,
) -> bool:
    return (
        bbox[0] - margin <= point[0] <= bbox[2] + margin
        and bbox[1] - margin <= point[1] <= bbox[3] + margin
    )


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
