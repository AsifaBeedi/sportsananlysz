from __future__ import annotations

from typing import Any

from .profiles import SportProfile


def _module_status(
    capability_level: str,
    advanced_event_status: str,
    module_name: str,
    *,
    object_tracking_mode: str = "",
) -> str:
    if module_name == "advanced_events":
        return "planned" if advanced_event_status == "planned" else "active"
    if module_name == "object_tracking" and object_tracking_mode in {"motion_fallback", "hockey_puck"}:
        return "limited"
    return "active"


def build_baseline_output(
    *,
    sport: str,
    sport_profile: SportProfile,
    tracked_player_ids: list[int] | None = None,
    players_detected: int = 0,
    balls_detected: int = 0,
    ball_track_active: bool = False,
    ball_trajectory_length: int = 0,
    players_with_pose: int = 0,
    avg_posture_score: float | None = None,
    injury_risk_count: int = 0,
    racket_track_active: bool = False,
    racket_path_length_px: float | None = 0.0,
    recommendation_count: int = 0,
    recent_event_count: int = 0,
    contact_candidate_count: int = 0,
    object_tracking_provider: str | None = None,
) -> dict[str, Any]:
    tracked_ids = tracked_player_ids or []
    capability_level = sport_profile.capability_level
    advanced_event_status = sport_profile.advanced_event_status

    return {
        "schema_version": 1,
        "sport": sport,
        "mode": capability_level,
        "advanced_event_status": advanced_event_status,
        "minimum_output_defined": True,
        "modules": {
            "player_tracking": {
                "status": _module_status(capability_level, advanced_event_status, "player_tracking"),
                "players_detected": players_detected,
                "tracked_player_ids": tracked_ids,
            },
            "object_tracking": {
                "status": _module_status(
                    capability_level,
                    advanced_event_status,
                    "object_tracking",
                    object_tracking_mode=sport_profile.object_tracking_mode,
                ),
                "object_name": sport_profile.ball_name,
                "provider": object_tracking_provider or sport_profile.object_tracking_mode,
                "detections": balls_detected,
                "track_active": ball_track_active,
                "trajectory_length": ball_trajectory_length,
            },
            "pose": {
                "status": _module_status(capability_level, advanced_event_status, "pose"),
                "players_with_pose": players_with_pose,
            },
            "posture": {
                "status": _module_status(capability_level, advanced_event_status, "posture"),
                "avg_posture_score": avg_posture_score,
                "injury_risk_count": injury_risk_count,
            },
            "equipment_motion": {
                "status": _module_status(capability_level, advanced_event_status, "equipment_motion"),
                "equipment_name": sport_profile.equipment_name,
                "track_active": racket_track_active,
                "path_length_px": racket_path_length_px,
            },
            "recommendations": {
                "status": _module_status(capability_level, advanced_event_status, "recommendations"),
                "count": recommendation_count,
            },
            "advanced_events": {
                "status": _module_status(capability_level, advanced_event_status, "advanced_events"),
                "mode": advanced_event_status,
                "recent_event_count": recent_event_count,
                "contact_candidate_count": contact_candidate_count,
            },
        },
    }
