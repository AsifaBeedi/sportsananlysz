from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .baseline import build_baseline_output
from .profiles import get_sport_profile

LATEST_SESSION_OPTION = "__latest__"
SESSIONS_DIR = Path("data/outputs/sessions")
LOCAL_VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv")
MIN_OUTPUT_VIDEO_BYTES = 4_096


def existing_path(value: Any) -> Path | None:
    if not value:
        return None
    path = Path(str(value))
    return path if path.exists() else None


def existing_video_path(value: Any, *, min_size_bytes: int = 1) -> Path | None:
    path = existing_path(value)
    if path is None or not path.is_file():
        return None
    if path.suffix.lower() not in LOCAL_VIDEO_EXTENSIONS:
        return None
    if path.stat().st_size < max(0, int(min_size_bytes)):
        return None
    return path


def discover_local_video_files(*, limit: int = 20) -> list[Path]:
    search_roots = [
        Path("data/videos"),
    ]
    discovered: list[Path] = []
    seen: set[Path] = set()

    for root in search_roots:
        if not root.exists():
            continue
        for path in root.iterdir():
            if not path.is_file() or path.suffix.lower() not in LOCAL_VIDEO_EXTENSIONS:
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            discovered.append(resolved)

    discovered.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return discovered[:limit]


def discover_session_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not SESSIONS_DIR.exists():
        return records

    for stats_path in SESSIONS_DIR.glob("*/stats.json"):
        try:
            with stats_path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            continue

        session_dir = stats_path.parent
        records.append(
            {
                "session_id": payload.get("session_id") or session_dir.name,
                "session_dir": str(session_dir),
                "stats_path": str(stats_path),
                "sport": payload.get("sport", "unknown"),
                "match_id": payload.get("match_id") or (payload.get("match") or {}).get("match_id"),
                "camera_id": payload.get("camera_id") or (payload.get("match") or {}).get("camera_id"),
                "camera_label": (payload.get("match") or {}).get("camera_label"),
                "camera_role": (payload.get("match") or {}).get("camera_role"),
                "source_video": payload.get("source_video", "unknown"),
                "status": payload.get("status", "unknown"),
                "session_started_at": payload.get("session_started_at"),
                "last_updated_at": payload.get("last_updated_at"),
            }
        )

    records.sort(key=session_sort_key, reverse=True)
    return records


def session_sort_key(record: dict[str, Any]) -> float:
    for key in ("last_updated_at", "session_started_at"):
        parsed = parse_iso_timestamp(record.get(key))
        if parsed is not None:
            return parsed.timestamp()

    stats_path = existing_path(record.get("stats_path"))
    if stats_path is not None:
        return stats_path.stat().st_mtime
    return 0.0


def format_session_label(session_id: str, session_records: list[dict[str, Any]]) -> str:
    if session_id == LATEST_SESSION_OPTION:
        return "Latest session"

    record = next((item for item in session_records if item["session_id"] == session_id), None)
    if record is None:
        return session_id

    sport = str(record.get("sport", "unknown")).title()
    video = record.get("source_video", "unknown")
    status = str(record.get("status", "unknown")).title()
    camera_label = record.get("camera_label") or record.get("camera_id")
    match_id = record.get("match_id")
    if match_id and camera_label:
        return f"{record['session_id']} | {sport} | {camera_label} | {status}"
    return f"{record['session_id']} | {sport} | {video} | {status}"


def build_session_rows(session_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for record in session_records:
        rows.append(
            {
                "Session ID": record.get("session_id"),
                "Sport": str(record.get("sport", "unknown")).title(),
                "Match": record.get("match_id") or "-",
                "Camera": record.get("camera_label") or record.get("camera_id") or "-",
                "Video": record.get("source_video", "unknown"),
                "Status": str(record.get("status", "unknown")).title(),
                "Started": record.get("session_started_at") or "-",
                "Updated": record.get("last_updated_at") or "-",
            }
        )
    return rows


def group_sessions_by_match(session_records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in session_records:
        match_id = record.get("match_id")
        if not match_id:
            continue
        grouped.setdefault(str(match_id), []).append(record)

    for records in grouped.values():
        records.sort(key=session_sort_key, reverse=True)
    return grouped


def sessions_for_match(session_records: list[dict[str, Any]], match_id: str | None) -> list[dict[str, Any]]:
    if not match_id:
        return []
    return group_sessions_by_match(session_records).get(str(match_id), [])


def build_match_rows(session_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for match_id, records in group_sessions_by_match(session_records).items():
        sports = sorted({str(record.get("sport", "unknown")).title() for record in records})
        cameras = [
            record.get("camera_label") or record.get("camera_id") or record.get("session_id")
            for record in records
        ]
        rows.append(
            {
                "Match ID": match_id,
                "Sport(s)": ", ".join(sports),
                "Camera Count": len(records),
                "Cameras": ", ".join(cameras),
                "Latest Update": records[0].get("last_updated_at") or records[0].get("session_started_at") or "-",
            }
        )
    rows.sort(key=lambda row: row["Latest Update"], reverse=True)
    return rows


def preview_from_session_record(record: dict[str, Any]) -> Path | None:
    session_dir = existing_path(record.get("session_dir"))
    if session_dir is None:
        return None
    preview_path = session_dir / "preview.jpg"
    return preview_path if preview_path.exists() else None


def selected_session_record(
    selected_session_id: str, session_records: list[dict[str, Any]]
) -> dict[str, Any] | None:
    if selected_session_id == LATEST_SESSION_OPTION:
        return session_records[0] if session_records else None
    return next((record for record in session_records if record["session_id"] == selected_session_id), None)


def resolve_session_dir(data: dict[str, Any]) -> Path | None:
    session_dir = existing_path(data.get("session_dir"))
    if session_dir is not None and session_dir.is_dir():
        return session_dir

    stats_path = existing_path(data.get("stats_path"))
    if stats_path is not None:
        return stats_path.parent

    return None


def infer_snippet_metric(path: Path) -> str:
    name = path.stem
    if "contact" in name:
        return "contact_candidate"
    if "injury_risk_player_" in name:
        match = re.search(r"injury_risk_player_\d+", name)
        return match.group(0) if match else "other"
    return "other"


def _scan_bad_frames_from_dir(review_dir: Path | None) -> list[dict[str, Any]]:
    if review_dir is None or not review_dir.exists():
        return []

    frames = []
    for img_path in sorted(review_dir.glob("*.jpg")):
        name = img_path.stem
        numbers = re.findall(r"\d+", name)
        frame_num = numbers[1] if len(numbers) > 1 else "unknown"

        if "Low_Posture" in name or "Low Posture" in name:
            score_match = re.search(r"\((\d+)\)", name)
            score = score_match.group(1) if score_match else "?"
            reason = f"Low Posture Score ({score})"
        elif "injury" in name.lower():
            reason = "Injury Risk Detected"
        else:
            reason = "Flagged Frame"

        timestamp_match = re.search(r"(\d+\.?\d*)s", name)
        timestamp = f"{timestamp_match.group(1)}s" if timestamp_match else "-"

        frames.append(
            {
                "path": img_path,
                "frame_index": frame_num,
                "reason": reason,
                "timestamp": timestamp,
                "filename": img_path.name,
            }
        )
    return frames


def find_all_bad_frames(data: dict[str, Any]) -> list[dict[str, Any]]:
    clip_summary = data.get("clip_summary", {})
    saved_frames = []
    for record in clip_summary.get("bad_frames", []):
        frame_path = existing_path(record.get("frame_path"))
        if frame_path is None:
            continue
        saved_frames.append(
            {
                "path": frame_path,
                "frame_index": record.get("frame_index", "unknown"),
                "reason": record.get("reason", "Flagged Frame"),
                "timestamp": record.get("timestamp", "-"),
                "filename": frame_path.name,
            }
        )
    if saved_frames:
        return saved_frames

    session_dir = resolve_session_dir(data)
    session_frames = _scan_bad_frames_from_dir(session_dir / "review_frames" if session_dir is not None else None)
    if session_frames:
        return session_frames

    return _scan_bad_frames_from_dir(Path("data/review_frames"))


def _scan_snippets_from_dir(snippets_dir: Path | None) -> dict[str, list[Path]]:
    if snippets_dir is None or not snippets_dir.exists():
        return {}

    snippets: dict[str, list[Path]] = {}
    for video_path in sorted(snippets_dir.glob("*.mp4")):
        metric = infer_snippet_metric(video_path)
        snippets.setdefault(metric, []).append(video_path)
    return snippets


def find_all_snippets(data: dict[str, Any]) -> dict[str, list[Path]]:
    clip_summary = data.get("clip_summary", {})
    snippet_index = clip_summary.get("snippet_index", {})
    if snippet_index:
        snippets: dict[str, list[Path]] = {}
        for metric, paths in snippet_index.items():
            resolved_paths = [path for path in (existing_path(item) for item in paths) if path is not None]
            if resolved_paths:
                snippets[metric] = resolved_paths
        if snippets:
            return snippets

    session_dir = resolve_session_dir(data)
    session_snippets = _scan_snippets_from_dir(session_dir / "snippets" if session_dir is not None else None)
    if session_snippets:
        return session_snippets

    return _scan_snippets_from_dir(Path("data/snippets"))


def get_preview_frame(data: dict[str, Any]) -> Path | None:
    preview_path = existing_path(data.get("preview_frame_path"))
    if preview_path is not None:
        return preview_path

    session_dir = resolve_session_dir(data)
    session_preview = existing_path(session_dir / "preview.jpg" if session_dir is not None else None)
    if session_preview is not None:
        return session_preview

    for path in (
        Path("outputs/review_frames/latest_annotated_frame.jpg"),
        Path("latest_annotated_frame.jpg"),
        Path("data/latest_annotated_frame.jpg"),
    ):
        if path.exists():
            return path
    return None


def get_output_video(data: dict[str, Any]) -> Path | None:
    output_path = existing_video_path(
        data.get("output_video_path"),
        min_size_bytes=MIN_OUTPUT_VIDEO_BYTES,
    )
    if output_path is not None:
        return output_path

    session_dir = resolve_session_dir(data)
    session_output = existing_video_path(
        session_dir / "output.mp4" if session_dir is not None else None,
        min_size_bytes=MIN_OUTPUT_VIDEO_BYTES,
    )
    if session_output is not None:
        return session_output

    for path in (
        Path("outputs/processed_video.mp4"),
        Path("annotated_match_output.mp4"),
        Path("data/annotated_match_output.mp4"),
    ):
        if existing_video_path(path, min_size_bytes=MIN_OUTPUT_VIDEO_BYTES) is not None:
            return path
    return None


def get_source_video(data: dict[str, Any]) -> Path | None:
    source_payload = data.get("source") or {}
    metadata = source_payload.get("metadata") or {}
    candidates = [
        source_payload.get("uri"),
        metadata.get("path"),
    ]

    source_video = data.get("source_video")
    if source_video:
        candidates.extend(
            [
                Path("data/videos") / str(source_video),
                Path("data/models/scripts") / str(source_video),
            ]
        )

    for candidate in candidates:
        path = existing_video_path(candidate)
        if path is not None:
            return path
    return None


def get_display_video(data: dict[str, Any]) -> tuple[Path | None, str]:
    output_path = existing_video_path(
        data.get("output_video_path"),
        min_size_bytes=MIN_OUTPUT_VIDEO_BYTES,
    )
    if output_path is None:
        session_dir = resolve_session_dir(data)
        output_path = existing_video_path(
            session_dir / "output.mp4" if session_dir is not None else None,
            min_size_bytes=MIN_OUTPUT_VIDEO_BYTES,
        )
    if output_path is not None:
        return output_path, "Processed Video"

    source_path = get_source_video(data)
    if source_path is not None:
        return source_path, "Source Video"

    output_path = get_output_video(data)
    if output_path is not None:
        return output_path, "Processed Video"

    return None, "Video"


def find_stats_file(
    selected_session_id: str | None = None, session_records: list[dict[str, Any]] | None = None
) -> Path | None:
    if session_records is None:
        session_records = discover_session_records()

    if selected_session_id and selected_session_id != LATEST_SESSION_OPTION:
        for record in session_records:
            if record["session_id"] == selected_session_id:
                stats_path = existing_path(record.get("stats_path"))
                if stats_path is not None:
                    return stats_path

    if session_records:
        latest_stats_path = existing_path(session_records[0].get("stats_path"))
        if latest_stats_path is not None:
            return latest_stats_path

    for path in (
        Path("outputs/match_stats.json"),
        Path("match_stats.json"),
        Path("data/match_stats.json"),
        Path("data/models/scripts/match_stats.json"),
    ):
        if path.exists():
            return path
    return None


def default_payload() -> dict[str, Any]:
    default_profile = get_sport_profile("tennis")
    return {
        "status": "idle",
        "phase": "phase_9_dashboard",
        "core_mode": "sport_agnostic",
        "session_id": None,
        "session_started_at": None,
        "last_updated_at": None,
        "match_id": None,
        "camera_id": None,
        "match": {
            "match_id": None,
            "camera_id": None,
            "camera_label": None,
            "camera_role": "single",
            "is_multi_camera": False,
            "session_id": None,
        },
        "sport": "tennis",
        "source": {
            "type": "file",
            "label": "File: tennis.mp4",
            "uri": "data/videos/tennis.mp4",
            "metadata": {},
        },
        "sport_profile": {
            "display_name": "Tennis",
            "equipment_name": "racket",
            "ball_name": "tennis ball",
            "ball_like_object_name": "sports ball",
            "object_tracking_mode": "yolo_sports_ball",
            "capability_level": "full_demo",
            "advanced_event_status": "tennis_specific",
        },
        "source_video": "tennis.mp4",
        "model": "yolov8n.pt",
        "pose_model": "yolov8n-pose.pt",
        "frame_index": 0,
        "fps": 25.0,
        "timestamp_seconds": 0.0,
        "frame_size": {"width": 360, "height": 640},
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
            sport="tennis",
            sport_profile=default_profile,
            object_tracking_provider="yolo_sports_ball",
        ),
        "players": [],
        "ball": {"detections": [], "primary_detection": None},
        "ball_tracking": {
            "active": False,
            "detected_this_frame": False,
            "status": "waiting",
            "tracking_mode": "yolo_sports_ball",
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
        "events": {
            "sport_mode": "tennis",
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
        },
        "racket": {
            "sport_mode": "tennis",
            "primary_player_id": None,
            "active_track_ids": [],
            "active_count": 0,
            "latest_primary_state": None,
            "recent_primary_path": [],
        },
        "ball_speed": {
            "active": False,
            "meters_per_pixel": None,
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
            "sport_mode": "tennis",
            "primary_player_id": None,
            "session_recommendations": [],
            "player_recommendations": {},
            "recommendation_count": 0,
        },
        "performance_metrics": {
            "frame_series": [],
            "event_timeline": [],
            "event_type_counts": {},
            "shot_type_counts": {},
            "summary": {
                "sample_count": 0,
                "event_count": 0,
                "peak_primary_posture_score": None,
                "peak_ball_speed_px_per_sec": None,
                "peak_equipment_speed_px_per_sec": None,
                "peak_activity_score": None,
                "peak_ball_control_score": None,
                "dominant_event_type": None,
                "dominant_shot_label": None,
                "inference_quality_score": 0.0,
                "inference_quality_label": "low",
                "detected_shot_labels": [],
            },
        },
        "clip_summary": {
            "snippet_index": {},
            "snippet_count": 0,
            "bad_frames": [],
            "bad_frame_count": 0,
        },
        "notes": ["Waiting for analytics output..."],
    }


def load_stats(
    selected_session_id: str | None = None, session_records: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    defaults = default_payload()
    stats_path = find_stats_file(selected_session_id=selected_session_id, session_records=session_records)
    if not stats_path:
        return defaults

    try:
        with stats_path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return defaults

    for key in defaults:
        if key not in data:
            data[key] = defaults[key]

    sport_name = str(data.get("sport", "tennis"))
    try:
        sport_profile = get_sport_profile(sport_name)
    except ValueError:
        sport_name = "tennis"
        sport_profile = get_sport_profile("tennis")

    profile_payload = data.setdefault("sport_profile", {})
    profile_payload.setdefault("display_name", sport_profile.display_name)
    profile_payload.setdefault("equipment_name", sport_profile.equipment_name)
    profile_payload.setdefault("ball_name", sport_profile.ball_name)
    profile_payload.setdefault("ball_like_object_name", sport_profile.ball_like_object_name)
    profile_payload.setdefault("object_tracking_mode", sport_profile.object_tracking_mode)
    profile_payload.setdefault("capability_level", sport_profile.capability_level)
    profile_payload.setdefault("advanced_event_status", sport_profile.advanced_event_status)
    match_payload = data.setdefault("match", {})
    match_payload.setdefault("match_id", data.get("match_id"))
    match_payload.setdefault("camera_id", data.get("camera_id"))
    match_payload.setdefault("camera_label", match_payload.get("camera_id"))
    match_payload.setdefault("camera_role", "single")
    match_payload.setdefault("is_multi_camera", bool(match_payload.get("match_id") and match_payload.get("camera_id")))
    match_payload.setdefault("session_id", data.get("session_id"))
    data.setdefault("match_id", match_payload.get("match_id"))
    data.setdefault("camera_id", match_payload.get("camera_id"))

    ball_tracking_payload = data.setdefault("ball_tracking", {})
    ball_tracking_payload.setdefault("tracking_mode", sport_profile.object_tracking_mode)
    ball_tracking_payload.setdefault("detected_this_frame", False)
    ball_tracking_payload.setdefault("frame_detection_count", 0)
    ball_tracking_payload.setdefault("detected_center", ball_tracking_payload.get("raw_center"))
    ball_tracking_payload.setdefault("tracked_center", ball_tracking_payload.get("raw_center"))
    ball_tracking_payload.setdefault("selected_detection", None)
    ball_tracking_payload.setdefault("frame_detections", [])

    if "baseline" not in data or not isinstance(data.get("baseline"), dict):
        summary = data.get("summary", {})
        ball_tracking = data.get("ball_tracking", {})
        pose_summary = data.get("pose", {}).get("summary", {})
        racket = data.get("racket", {})
        recommendations = data.get("recommendations", {})
        events = data.get("events", {})

        latest_primary_state = racket.get("latest_primary_state") or {}
        data["baseline"] = build_baseline_output(
            sport=sport_name,
            sport_profile=sport_profile,
            tracked_player_ids=list(summary.get("tracked_player_ids", [])),
            players_detected=int(summary.get("players_detected", 0) or 0),
            balls_detected=int(summary.get("balls_detected", 0) or 0),
            ball_track_active=bool(ball_tracking.get("active", False)),
            ball_trajectory_length=int(ball_tracking.get("trajectory_length", 0) or 0),
            players_with_pose=int(pose_summary.get("players_with_pose", 0) or 0),
            avg_posture_score=pose_summary.get("avg_posture_score"),
            injury_risk_count=int(pose_summary.get("injury_risk_count", 0) or 0),
            racket_track_active=bool(summary.get("racket_track_active", False)),
            racket_path_length_px=latest_primary_state.get("path_length_px", 0.0),
            recommendation_count=int(recommendations.get("recommendation_count", 0) or 0),
            recent_event_count=int(events.get("recent_event_count", 0) or 0),
            contact_candidate_count=int(events.get("contact_candidate_count", 0) or 0),
            object_tracking_provider=str(
                ball_tracking.get("tracking_mode", sport_profile.object_tracking_mode)
            ),
        )

    if "performance_metrics" not in data or not isinstance(data.get("performance_metrics"), dict):
        primary = primary_player(data.get("players", []), (data.get("events") or {}).get("primary_player_id"))
        primary_posture = ((primary.get("pose") or {}).get("posture", {}) if primary else {})
        primary_event_state = (primary.get("event_state") or {} if primary else {})
        primary_racket = (primary.get("racket") or {} if primary else {})
        latest_racket_speed = ((data.get("impact_power") or {}).get("latest_racket_speed") or {})
        recent_events = list((data.get("events") or {}).get("recent_events", []))
        event_type_counts: dict[str, int] = {}
        shot_type_counts: dict[str, int] = {}
        for event in recent_events:
            event_type = str(event.get("event_type") or "unknown")
            event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
            shot_label = event.get("shot_label")
            if shot_label:
                shot_type_counts[str(shot_label)] = shot_type_counts.get(str(shot_label), 0) + 1

        data["performance_metrics"] = {
            "frame_series": [
                {
                    "frame_index": data.get("frame_index"),
                    "timestamp_seconds": data.get("timestamp_seconds"),
                    "players_detected": summary.get("players_detected"),
                    "players_with_pose": summary.get("players_with_pose"),
                    "avg_posture_score": summary.get("avg_posture_score"),
                    "primary_posture_score": primary_posture.get("posture_score"),
                    "active_swing_count": summary.get("active_swing_count"),
                    "activity_score": primary_event_state.get("activity_score"),
                    "ball_proximity_px": primary_event_state.get("ball_proximity_px"),
                    "ball_control_score": primary_event_state.get("ball_control_score"),
                    "ball_speed_px_per_sec": summary.get("ball_speed_px_per_sec"),
                    "impact_power_score": summary.get("impact_power_score"),
                    "equipment_path_length_px": primary_racket.get("path_length_px"),
                    "equipment_angle_deg": primary_racket.get("angle_deg"),
                    "equipment_speed_px_per_sec": latest_racket_speed.get("speed_px_per_sec"),
                    "shot_label_candidate": primary_event_state.get("shot_label_candidate"),
                    "swing_phase": primary_event_state.get("swing_phase"),
                    "recommendation_count": (data.get("recommendations") or {}).get("recommendation_count"),
                }
            ],
            "event_timeline": recent_events[-20:],
            "event_type_counts": event_type_counts,
            "shot_type_counts": shot_type_counts,
            "summary": {
                "sample_count": 1,
                "event_count": len(recent_events),
                "peak_primary_posture_score": primary_posture.get("posture_score"),
                "peak_ball_speed_px_per_sec": summary.get("ball_speed_px_per_sec"),
                "peak_equipment_speed_px_per_sec": latest_racket_speed.get("speed_px_per_sec"),
                "peak_activity_score": primary_event_state.get("activity_score"),
                "peak_ball_control_score": primary_event_state.get("ball_control_score"),
                "dominant_event_type": max(event_type_counts, key=event_type_counts.get) if event_type_counts else None,
                "dominant_shot_label": max(shot_type_counts, key=shot_type_counts.get) if shot_type_counts else None,
                "inference_quality_score": 0.35 if recent_events else 0.15,
                "inference_quality_label": "medium" if recent_events else "low",
                "detected_shot_labels": sorted(shot_type_counts.keys()),
            },
        }

    data.setdefault("stats_path", str(stats_path))
    return data


def format_value(value: Any, digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.{digits}f}{suffix}"
    return f"{value}{suffix}"


def metric_delta(current: Any, previous: Any, digits: int = 2) -> str | None:
    if current is None or previous is None:
        return None
    if not isinstance(current, (int, float)) or not isinstance(previous, (int, float)):
        return None
    change = current - previous
    if abs(change) < 1e-9:
        return "0"
    return f"{change:+.{digits}f}"


def parse_iso_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def current_data_age_seconds(data: dict[str, Any]) -> float | None:
    updated_at = parse_iso_timestamp(data.get("last_updated_at"))
    if updated_at is not None:
        return max(0.0, round((datetime.now() - updated_at).total_seconds(), 2))
    return None


def freshness_label(age_seconds: float | None, status: str) -> str:
    if age_seconds is None:
        return "Unknown"
    if status == "running":
        return "Running"
    if status == "starting":
        return "Starting"
    if status == "completed":
        return "Completed"
    if status == "stopped":
        return "Stopped"
    if status == "idle":
        return "Waiting"
    if status == "legacy":
        return "Legacy"
    return "Updated"


def primary_player(players: list[dict[str, Any]], primary_player_id: Any) -> dict[str, Any] | None:
    if primary_player_id is None:
        return players[0] if players else None
    for player in players:
        if player.get("track_id") == primary_player_id:
            return player
    return players[0] if players else None


def player_table(players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for player in players:
        posture = (player.get("pose") or {}).get("posture", {})
        event_state = player.get("event_state") or {}
        racket_state = player.get("racket") or {}
        equipment_name = str(racket_state.get("equipment_name", "equipment")).title()
        rows.append(
            {
                "Player ID": player.get("track_id"),
                "Speed (px/frame)": player.get("speed_px"),
                "Posture": posture.get("posture_label"),
                "Posture Score": posture.get("posture_score"),
                "Risk": posture.get("injury_risk_level"),
                "Swing Phase": event_state.get("swing_phase"),
                "Shot Candidate": event_state.get("shot_label_candidate"),
                f"{equipment_name} Direction": racket_state.get("swing_direction"),
                f"{equipment_name} Plane": racket_state.get("stroke_plane"),
            }
        )
    return rows


def event_table(recent_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for event in recent_events:
        rows.append(
            {
                "Frame": event.get("frame_index"),
                "Type": event.get("event_type"),
                "Player": event.get("track_id"),
                "Shot": event.get("shot_label"),
                "Timestamp (s)": event.get("timestamp_seconds"),
            }
        )
    return rows


def save_uploaded_video(uploaded_file: Any) -> Path:
    uploads_dir = Path("data/videos")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    target_path = uploads_dir / Path(uploaded_file.name).name
    target_path.write_bytes(uploaded_file.getbuffer())
    return target_path
