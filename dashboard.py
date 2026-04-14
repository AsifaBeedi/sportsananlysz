from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import streamlit as st


STATS_PATH = Path("match_stats.json")
UPLOADS_DIR = Path("uploaded_videos")
MAX_HISTORY_POINTS = 120
FRESHNESS_WARNING_SECONDS = 5.0


def default_payload() -> dict:
    return {
        "status": "idle",
        "phase": "phase_9_dashboard",
        "session_id": None,
        "session_started_at": None,
        "last_updated_at": None,
        "sport": "tennis",
        "sport_profile": {
            "display_name": "Tennis",
            "equipment_name": "racket",
            "ball_name": "tennis ball",
            "ball_like_object_name": "sports ball",
        },
        "source_video": "tennis.mp4",
        "preview_frame_path": "latest_annotated_frame.jpg",
        "output_video_path": "annotated_match_output.mp4",
        "frame_index": 0,
        "timestamp_seconds": 0.0,
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
        "ball": {"detections": [], "primary_detection": None},
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
        "events": {
            "sport_mode": "tennis",
            "primary_player_id": None,
            "active_swing_player_ids": [],
            "active_swing_count": 0,
            "current_frame_events": [],
            "recent_events": [],
            "recent_event_count": 0,
            "contact_candidate_count": 0,
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
        "clip_summary": {
            "snippet_index": {},
            "snippet_count": 0,
            "bad_frames": [],
            "bad_frame_count": 0,
        },
        "notes": ["Waiting for analytics output..."],
    }


def merge_with_defaults(data: dict, defaults: dict) -> dict:
    merged = dict(defaults)
    for key, value in data.items():
        default_value = defaults.get(key)
        if isinstance(value, dict) and isinstance(default_value, dict):
            merged[key] = merge_with_defaults(value, default_value)
        else:
            merged[key] = value
    return merged


def load_stats() -> dict:
    defaults = default_payload()
    if not STATS_PATH.exists():
        return defaults

    try:
        with STATS_PATH.open(encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError):
        broken_payload = merge_with_defaults({}, defaults)
        broken_payload["status"] = "unavailable"
        broken_payload["notes"] = ["Could not read analytics output yet."]
        return broken_payload

    if "summary" in data:
        return merge_with_defaults(data, defaults)

    legacy_payload = merge_with_defaults({}, defaults)
    legacy_payload.update(
        {
            "status": "legacy",
            "phase": "prototype",
            "sport": "unknown",
            "sport_profile": {
                "display_name": "Unknown",
                "equipment_name": "equipment",
                "ball_name": "ball",
                "ball_like_object_name": "game object",
            },
            "summary": {
                "players_detected": data.get("players", 0),
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
            "notes": ["Legacy stats format detected."],
        }
    )
    return legacy_payload


def format_value(value: object, digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.{digits}f}{suffix}"
    return f"{value}{suffix}"


def metric_delta(current: object, previous: object, digits: int = 2) -> str | None:
    if current is None or previous is None:
        return None
    if not isinstance(current, (int, float)) or not isinstance(previous, (int, float)):
        return None
    change = current - previous
    if abs(change) < 1e-9:
        return "0"
    return f"{change:+.{digits}f}"


def parse_iso_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def current_data_age_seconds(data: dict) -> float | None:
    updated_at = parse_iso_timestamp(data.get("last_updated_at"))
    if updated_at is not None:
        return max(0.0, round((datetime.now() - updated_at).total_seconds(), 2))

    if STATS_PATH.exists():
        return max(0.0, round(datetime.now().timestamp() - STATS_PATH.stat().st_mtime, 2))

    return None


def freshness_label(age_seconds: float | None, status: str) -> str:
    if age_seconds is None:
        return "Unknown"
    if status == "running" and age_seconds <= FRESHNESS_WARNING_SECONDS:
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
    if age_seconds <= FRESHNESS_WARNING_SECONDS:
        return "Updated"
    return "Old Output"


def reset_dashboard_files() -> None:
    payload = default_payload()
    STATS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    preview_path = Path(payload["preview_frame_path"])
    try:
        preview_path.unlink(missing_ok=True)
    except OSError:
        pass


def update_history(data: dict) -> list[dict]:
    frame_index = int(data.get("frame_index", 0) or 0)
    session_key = (
        data.get("sport", "unknown"),
        data.get("source_video", "unknown"),
    )
    history_key = "dashboard_history"
    session_key_name = "dashboard_session_key"

    if st.session_state.get(session_key_name) != session_key:
        st.session_state[session_key_name] = session_key
        st.session_state[history_key] = []

    history = st.session_state.setdefault(history_key, [])
    if history and frame_index < history[-1]["frame_index"]:
        history.clear()

    if history and frame_index == history[-1]["frame_index"]:
        return history

    summary = data.get("summary", {})
    history.append(
        {
            "frame_index": frame_index,
            "timestamp_seconds": data.get("timestamp_seconds"),
            "players_detected": summary.get("players_detected"),
            "ball_speed_px_per_sec": summary.get("ball_speed_px_per_sec"),
            "impact_power_score": summary.get("impact_power_score"),
            "avg_posture_score": summary.get("avg_posture_score"),
            "active_swing_count": summary.get("active_swing_count"),
            "contact_candidate_count": summary.get("contact_candidate_count"),
            "recommendation_count": summary.get("recommendation_count"),
            "injury_risk_count": summary.get("injury_risk_count"),
        }
    )
    if len(history) > MAX_HISTORY_POINTS:
        del history[:-MAX_HISTORY_POINTS]
    return history


def primary_player(players: list[dict], primary_player_id: int | None) -> dict | None:
    if primary_player_id is None:
        return players[0] if players else None
    for player in players:
        if player.get("track_id") == primary_player_id:
            return player
    return players[0] if players else None


def player_table(players: list[dict]) -> list[dict]:
    rows = []
    for player in players:
        posture = (player.get("pose") or {}).get("posture", {})
        event_state = player.get("event_state") or {}
        racket_state = player.get("racket") or {}
        rows.append(
            {
                "Player ID": player.get("track_id"),
                "Speed (px/frame)": player.get("speed_px"),
                "Posture": posture.get("posture_label"),
                "Posture Score": posture.get("posture_score"),
                "Risk": posture.get("injury_risk_level"),
                "Swing Phase": event_state.get("swing_phase"),
                "Shot Candidate": event_state.get("shot_label_candidate"),
                "Racket Direction": racket_state.get("swing_direction"),
            }
        )
    return rows


def event_table(recent_events: list[dict]) -> list[dict]:
    rows = []
    for event in recent_events:
        rows.append(
            {
                "Frame": event.get("frame_index"),
                "Type": event.get("event_type"),
                "Player": event.get("player_id"),
                "Shot": event.get("shot_label"),
                "Phase": event.get("swing_phase"),
                "Ball Proximity": event.get("ball_proximity_px"),
            }
        )
    return rows


def recommendation_table(recommendations: list[str]) -> list[dict]:
    return [{"Recommendation": item} for item in recommendations]


def compact_evidence(evidence: dict | None) -> dict:
    if not evidence:
        return {}

    filtered: dict[str, object] = {}
    preferred_keys = (
        "posture_score",
        "avg_knee_deg",
        "avg_hip_deg",
        "ball_proximity_px",
        "shot_label_candidate",
        "shot_label",
        "swing_direction",
        "racket_path_length_px",
        "contact_frame",
        "before_speed_px_per_sec",
        "after_speed_px_per_sec",
        "speed_delta_px_per_sec",
        "track_id",
    )
    for key in preferred_keys:
        value = evidence.get(key)
        if value is not None:
            filtered[key] = value

    coaching_notes = evidence.get("coaching_notes")
    if coaching_notes:
        filtered["coaching_notes"] = coaching_notes

    if not filtered:
        for key, value in evidence.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                filtered[key] = value
            if len(filtered) >= 6:
                break

    return filtered


def render_recommendation_card(item: dict, clip_summary: dict | None = None) -> None:
    category = str(item.get("category", "general")).replace("_", " ").title()
    priority = str(item.get("priority", "info")).upper()
    title = item.get("title", "Recommendation")
    detail = item.get("detail", "")
    evidence = compact_evidence(item.get("evidence"))

    # Map recommendation category to a ClipManager metric name so we can
    # link the card to any saved snippet for that metric type.
    CATEGORY_TO_METRIC: dict[str, str] = {
        "posture": "contact_candidate",
        "injury_risk": "injury_risk_player_1",
        "swing": "contact_candidate",
        "ball_speed": "contact_candidate",
        "contact": "contact_candidate",
    }
    raw_category = str(item.get("category", "")).lower()
    linked_metric = CATEGORY_TO_METRIC.get(raw_category)

    with st.container(border=True):
        st.markdown(f"**{title}**")
        st.caption(f"{category} | Priority: {priority}")
        if detail:
            st.write(detail)
        if evidence:
            with st.expander("Why this showed up"):
                st.write(evidence)
        # --- Phase 5: Watch Clip button ---
        if clip_summary and linked_metric:
            snippet_paths = clip_summary.get("snippet_index", {}).get(linked_metric, [])
            if snippet_paths:
                with st.expander("▶ Watch Clip"):
                    for clip_path in snippet_paths[-3:]:  # show up to 3 most recent
                        p = Path(clip_path)
                        if p.exists():
                            st.caption(f"Clip: {p.name}")
                            st.video(str(p))


def render_note(note: str) -> None:
    lowered = note.lower()
    if "active" in lowered or "completed" in lowered:
        st.success(note)
        return
    if "warning" in lowered or "risk" in lowered or "alert" in lowered:
        st.warning(note)
        return
    st.info(note)


def render_key_value_block(title: str, items: list[tuple[str, object]]) -> None:
    st.subheader(title)
    for label, value in items:
        display_value = value if value not in (None, "", [], {}) else "-"
        st.write(f"**{label}:** {display_value}")


def save_uploaded_video(uploaded_file) -> Path:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    target_path = UPLOADS_DIR / Path(uploaded_file.name).name
    target_path.write_bytes(uploaded_file.getbuffer())
    return target_path


def render_login_page() -> None:
    st.title("Sports AI Access")
    st.caption("Dummy authentication page for the project flow.")

    left_col, right_col = st.columns([3, 2])
    with left_col:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")

        if submitted:
            if username.strip() and password.strip():
                st.session_state["authenticated"] = True
                st.session_state["username"] = username.strip()
                st.session_state["app_page"] = "Live"
                st.rerun()
            else:
                st.error("Enter any non-empty username and password to continue.")

    with right_col:
        st.info("This is a dummy authentication screen. Any non-empty username and password will work.")
        st.write(
            {
                "next_screen_options": ["Live", "Upload Video", "Dashboard"],
                "demo_profile": "Tennis",
            }
        )


def render_sidebar(data: dict, history: list[dict]) -> None:
    summary = data.get("summary", {})
    sport_profile = data.get("sport_profile", {})
    ball_tracking = data.get("ball_tracking", {})
    notes = data.get("notes", [])

    st.sidebar.title("Session")
    st.sidebar.caption("Sport-agnostic core")
    st.sidebar.write(f"Sport: {sport_profile.get('display_name', data.get('sport', 'unknown'))}")
    st.sidebar.write(f"Phase: {data.get('phase', 'unknown')}")
    st.sidebar.write(f"Status: {data.get('status', 'unknown')}")
    st.sidebar.write(f"Session ID: {data.get('session_id') or '-'}")
    st.sidebar.write(f"Video: {data.get('source_video', 'unknown')}")
    st.sidebar.write(f"Frame: {data.get('frame_index', 0)}")
    st.sidebar.write(f"Time: {format_value(data.get('timestamp_seconds'), 2, ' s')}")

    st.sidebar.divider()
    st.sidebar.metric("History Points", len(history))
    st.sidebar.metric("Tracked Players", len(summary.get("tracked_player_ids", [])))
    st.sidebar.metric("Ball Track", "Live" if ball_tracking.get("active") else "Waiting")
    st.sidebar.metric("Recent Alerts", summary.get("injury_risk_count", 0) + summary.get("fall_alerts", 0))

    if notes:
        st.sidebar.divider()
        st.sidebar.subheader("Notes")
        for note in notes[:4]:
            st.sidebar.write(f"- {note}")


st.set_page_config(page_title="Sports AI Analytics Dashboard", layout="wide")

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "username" not in st.session_state:
    st.session_state["username"] = ""
if "app_page" not in st.session_state:
    st.session_state["app_page"] = "Live"
if "auto_refresh" not in st.session_state:
    st.session_state["auto_refresh"] = True

if not st.session_state["authenticated"]:
    render_login_page()
    st.stop()

data = load_stats()
summary = data.get("summary", {})
sport_profile = data.get("sport_profile", {})
pose_summary = data.get("pose", {}).get("summary", {})
events = data.get("events", {})
racket = data.get("racket", {})
ball_tracking = data.get("ball_tracking", {})
ball_speed = data.get("ball_speed", {})
impact_power = data.get("impact_power", {})
recommendations = data.get("recommendations", {})
players = data.get("players", [])
data_age_seconds = current_data_age_seconds(data)
data_freshness = freshness_label(data_age_seconds, str(data.get("status", "unknown")))
preview_frame_path = Path(data.get("preview_frame_path", "latest_annotated_frame.jpg"))
output_video_path = Path(data.get("output_video_path", "annotated_match_output.mp4"))

history = update_history(data)
render_sidebar(data, history)
if st.sidebar.button("Log Out"):
    st.session_state["authenticated"] = False
    st.session_state["username"] = ""
    st.rerun()

primary = primary_player(players, events.get("primary_player_id"))
primary_posture = ((primary.get("pose") or {}).get("posture", {}) if primary else {})
primary_event_state = (primary.get("event_state") or {} if primary else {})
primary_racket = (primary.get("racket") or {} if primary else {})
previous_history = history[-2] if len(history) > 1 else {}

st.title("SPORTS AI ANALYTICS DASHBOARD")
st.caption(
    f"{sport_profile.get('display_name', data.get('sport', 'Unknown'))} profile | "
    f"{sport_profile.get('equipment_name', 'equipment').title()} tracking | "
    f"Sport-agnostic analytics core"
)
nav_cols = st.columns([2, 1, 1, 1, 3])
selected_page = nav_cols[0].radio(
    "Mode",
    ["Live", "Upload Video", "Dashboard"],
    horizontal=True,
    index=["Live", "Upload Video", "Dashboard"].index(st.session_state.get("app_page", "Live")),
    label_visibility="collapsed",
)
st.session_state["app_page"] = selected_page
if nav_cols[1].button("Refresh"):
    st.rerun()
if nav_cols[2].button("Reset View"):
    reset_dashboard_files()
    st.rerun()
auto_refresh = nav_cols[3].toggle(
    "Auto",
    value=st.session_state.get("auto_refresh", True),
    help="Refresh the dashboard every 2 seconds.",
)
st.session_state["auto_refresh"] = auto_refresh
nav_cols[4].caption(
    "After login, use Live for the current session, Upload Video to save a new file, and Dashboard for full analytics."
)

session_cols = st.columns([2, 1, 1, 2])
session_cols[0].metric("Video Being Processed", data.get("source_video", "unknown"))
session_cols[1].metric("Data State", data_freshness)
session_cols[2].metric("Data Age", format_value(data_age_seconds, 1, " s"))
session_cols[3].metric("Session ID", data.get("session_id") or "-")

if data_freshness == "Stale":
    st.warning(
        "The dashboard is showing the last saved session output. Start the detector or click Refresh after new frames are processed."
    )
elif data_freshness == "Old Output":
    st.info("This dashboard is showing the most recent completed run, not a currently updating live session.")

if selected_page == "Upload Video":
    st.subheader("Upload Video")
    st.caption("Upload a match file here. It will be saved locally for later processing.")

    uploaded_file = st.file_uploader(
        "Choose a video",
        type=["mp4", "mov", "avi", "mkv"],
        accept_multiple_files=False,
    )
    if uploaded_file is not None:
        saved_path = save_uploaded_video(uploaded_file)
        st.session_state["uploaded_video_path"] = str(saved_path)
        st.success(f"Video saved to {saved_path}")

    uploaded_video_path = st.session_state.get("uploaded_video_path")
    if uploaded_video_path:
        st.write("Saved upload:")
        st.code(uploaded_video_path)
        st.caption("Use this command later to process the uploaded file:")
        st.code(
            f'python data\\models\\scripts\\detects_players.py --sport tennis --video "{uploaded_video_path}" --no-display'
        )

    st.stop()

if selected_page == "Live":
    live_cols = st.columns([3, 2])
    with live_cols[0]:
        st.subheader("Live Analysis Frame")
        if preview_frame_path.exists():
            st.image(str(preview_frame_path), use_container_width=True, caption=f"Annotated frame from {data.get('source_video', 'unknown')}")
        else:
            st.info("No analyzed frame is available yet. Run the detector to generate the live preview.")

    with live_cols[1]:
        render_key_value_block(
            "Live Session Status",
            [
                ("Session ID", data.get("session_id")),
                ("Session Started", data.get("session_started_at")),
                ("Last Updated", data.get("last_updated_at")),
                ("Session State", data_freshness),
                ("Source Video", data.get("source_video")),
                ("Frame Index", data.get("frame_index")),
                ("Runtime (s)", data.get("runtime_seconds")),
            ],
        )
        if output_video_path.exists():
            st.caption(f"Processed video saved at: {output_video_path}")

    live_metrics = st.columns(5)
    live_metrics[0].metric("Players", format_value(summary.get("players_detected"), 0))
    live_metrics[1].metric("Ball Speed", format_value(summary.get("ball_speed_px_per_sec"), 2, " px/s"))
    live_metrics[2].metric("Swings", format_value(summary.get("active_swing_count"), 0))
    live_metrics[3].metric("Impact Power", format_value(summary.get("impact_power_score"), 1))
    live_metrics[4].metric("Advice", format_value(summary.get("recommendation_count"), 0))

    if output_video_path.exists():
        st.subheader("Latest Processed Match Video")
        st.video(str(output_video_path))

    notes = data.get("notes", [])
    if notes:
        st.subheader("Pipeline Notes")
        for note in notes:
            render_note(note)

    if auto_refresh:
        time.sleep(2)
        st.rerun()
    st.stop()

preview_cols = st.columns([3, 2])
with preview_cols[0]:
    st.subheader("Live Analysis Frame")
    if preview_frame_path.exists():
        st.image(str(preview_frame_path), use_container_width=True, caption=f"Annotated frame from {data.get('source_video', 'unknown')}")
    else:
        st.info("No analyzed frame is available yet. Run the detector to generate the live preview.")

with preview_cols[1]:
    render_key_value_block(
        "Live Session Status",
        [
            ("Session ID", data.get("session_id")),
            ("Session Started", data.get("session_started_at")),
            ("Last Updated", data.get("last_updated_at")),
            ("Session State", data_freshness),
            ("Source Video", data.get("source_video")),
            ("Frame Index", data.get("frame_index")),
            ("Runtime (s)", data.get("runtime_seconds")),
        ],
    )
    if output_video_path.exists():
        st.caption(f"Processed video saved at: {output_video_path}")

metric_cols = st.columns(6)
metric_cols[0].metric(
    "Players",
    format_value(summary.get("players_detected"), 0),
    metric_delta(summary.get("players_detected"), previous_history.get("players_detected"), 0),
)
metric_cols[1].metric(
    "Ball Speed",
    format_value(summary.get("ball_speed_px_per_sec"), 2, " px/s"),
    metric_delta(summary.get("ball_speed_px_per_sec"), previous_history.get("ball_speed_px_per_sec")),
)
metric_cols[2].metric(
    "Posture",
    format_value(summary.get("avg_posture_score"), 0),
    metric_delta(summary.get("avg_posture_score"), previous_history.get("avg_posture_score")),
)
metric_cols[3].metric(
    "Swings",
    format_value(summary.get("active_swing_count"), 0),
    metric_delta(summary.get("active_swing_count"), previous_history.get("active_swing_count"), 0),
)
metric_cols[4].metric(
    "Impact Power",
    format_value(summary.get("impact_power_score"), 1),
    metric_delta(summary.get("impact_power_score"), previous_history.get("impact_power_score")),
)
metric_cols[5].metric(
    "Advice",
    format_value(summary.get("recommendation_count"), 0),
    metric_delta(summary.get("recommendation_count"), previous_history.get("recommendation_count"), 0),
)

overview_tab, motion_tab, recommendations_tab, history_tab, review_tab, raw_tab = st.tabs(
    ["Overview", "Motion", "Recommendations", "History", "🔍 Review Room", "Raw Data"]
)
clip_summary = data.get("clip_summary", {})

with overview_tab:
    summary_cols = st.columns(3)

    with summary_cols[0]:
        render_key_value_block(
            "Session Summary",
            [
                ("Status", data.get("status", "unknown")),
                ("Phase", data.get("phase", "unknown")),
                ("Sport", sport_profile.get("display_name", data.get("sport", "unknown"))),
                ("Equipment", sport_profile.get("equipment_name", "unknown")),
                ("Ball Type", sport_profile.get("ball_name", "unknown")),
                ("Source Video", data.get("source_video", "unknown")),
            ],
        )

    with summary_cols[1]:
        render_key_value_block(
            "Live Technique Snapshot",
            [
                ("Primary Player ID", events.get("primary_player_id")),
                ("Players With Pose", pose_summary.get("players_with_pose", 0)),
                ("Average Posture Score", pose_summary.get("avg_posture_score")),
                ("Injury Risk Players", pose_summary.get("injury_risk_player_ids", [])),
                ("Current Swing Phase", primary_event_state.get("swing_phase")),
                ("Shot Candidate", primary_event_state.get("shot_label_candidate")),
            ],
        )
        posture_score = primary_posture.get("posture_score")
        if isinstance(posture_score, (int, float)):
            st.progress(max(0.0, min(float(posture_score) / 100.0, 1.0)), text=f"Primary posture score: {posture_score}")

    with summary_cols[2]:
        render_key_value_block(
            "Ball And Equipment Snapshot",
            [
                ("Ball Track Status", ball_tracking.get("status")),
                ("Ball Track Active", ball_tracking.get("active")),
                ("Trajectory Length", ball_tracking.get("trajectory_length")),
                ("Latest Ball Center", ball_tracking.get("smoothed_center")),
                ("Racket Track Active", summary.get("racket_track_active")),
                ("Racket Path Length (px)", summary.get("racket_path_length_px")),
                ("Racket Direction", primary_racket.get("swing_direction")),
                ("Impact Power Score", summary.get("impact_power_score")),
            ],
        )

    st.subheader("Tracked Players")
    player_rows = player_table(players)
    if player_rows:
        st.dataframe(player_rows, use_container_width=True, hide_index=True)
    else:
        st.info("No tracked players available yet.")

with motion_tab:
    motion_cols = st.columns(2)

    with motion_cols[0]:
        st.subheader("Ball Speed Trend")
        speed_series = ball_speed.get("speed_series", [])
        speed_values = [point.get("speed_px_per_sec") for point in speed_series if point.get("speed_px_per_sec") is not None]
        if speed_values:
            st.line_chart({"Ball speed (px/s)": speed_values}, use_container_width=True)
        else:
            st.info("Ball speed trend will appear once a tracked trajectory is available.")

        st.write(
            {
                "current_speed_px_per_sec": ball_speed.get("current_speed"),
                "avg_recent_speed_px_per_sec": ball_speed.get("avg_recent_speed_px_per_sec"),
                "peak_speed_px_per_sec": ball_speed.get("peak_speed_px_per_sec"),
                "contact_speed_comparison": ball_speed.get("contact_comparison"),
            }
        )

    with motion_cols[1]:
        st.subheader("Session Progress")
        posture_values = [row["avg_posture_score"] for row in history if row.get("avg_posture_score") is not None]
        if posture_values:
            st.line_chart({"Posture score": posture_values}, use_container_width=True)
        else:
            st.info("Posture trend will appear once pose data is matched to players.")

        event_chart = {
            "Swings": [row.get("active_swing_count", 0) for row in history],
            "Contacts": [row.get("contact_candidate_count", 0) for row in history],
            "Impact Power": [row.get("impact_power_score", 0) or 0 for row in history],
            "Recommendations": [row.get("recommendation_count", 0) for row in history],
        }
        if history:
            st.bar_chart(event_chart, use_container_width=True)

    detail_cols = st.columns(2)
    with detail_cols[0]:
        st.subheader("Ball Tracking Detail")
        st.write(
            {
                "status": ball_tracking.get("status"),
                "missed_frames": ball_tracking.get("missed_frames"),
                "raw_center": ball_tracking.get("raw_center"),
                "smoothed_center": ball_tracking.get("smoothed_center"),
                "latest_direction_change": ball_tracking.get("latest_direction_change"),
            }
        )
        recent_history = ball_tracking.get("history", [])[-8:]
        if recent_history:
            st.dataframe(recent_history, use_container_width=True, hide_index=True)

    with detail_cols[1]:
        st.subheader("Racket Motion Detail")
        st.write(
            {
                "active_track_ids": racket.get("active_track_ids", []),
                "latest_primary_state": racket.get("latest_primary_state"),
                "recent_primary_path_points": len(racket.get("recent_primary_path", [])),
            }
        )
        power_proxy = impact_power.get("contact_power_proxy")
        if power_proxy:
            render_key_value_block(
                "Contact Power Proxy",
                [
                    ("Power Score", power_proxy.get("power_score")),
                    ("Power Level", power_proxy.get("power_level")),
                    ("Shot Label", power_proxy.get("shot_label")),
                    ("Racket Speed (px/s)", power_proxy.get("racket_speed_px_per_sec")),
                    ("Ball Speed Gain (px/s)", power_proxy.get("ball_speed_gain_px_per_sec")),
                ],
            )
            st.caption(power_proxy.get("method"))
            st.caption(power_proxy.get("limitations"))

with recommendations_tab:
    recommendation_cols = st.columns(2)

    with recommendation_cols[0]:
        st.subheader("Session Recommendations")
        session_recommendations = recommendations.get("session_recommendations", [])
        if session_recommendations:
            for item in session_recommendations:
                render_recommendation_card(item, clip_summary=clip_summary)
        else:
            st.success("No session-level recommendations yet.")

    with recommendation_cols[1]:
        st.subheader("Player Coaching Notes")
        player_recommendations = recommendations.get("player_recommendations", {})
        if player_recommendations:
            for player_id, items in player_recommendations.items():
                st.markdown(f"**Player {player_id}**")
                for item in items:
                    render_recommendation_card(item, clip_summary=clip_summary)
        else:
            st.success("No player-specific coaching notes yet.")

    risk_cols = st.columns(2)
    with risk_cols[0]:
        st.subheader("Risk And Alert Summary")
        risk_metric_cols = st.columns(2)
        risk_metric_cols[0].metric("Injury Risk Flags", summary.get("injury_risk_count", 0))
        risk_metric_cols[1].metric("Fall Alerts", summary.get("fall_alerts", 0))
        st.write(
            {
                "players_with_pose": pose_summary.get("players_with_pose"),
                "primary_posture_label": primary_posture.get("posture_label"),
                "primary_risk_level": primary_posture.get("injury_risk_level"),
            }
        )
        risk_flags = primary_posture.get("injury_risk_flags", [])
        if risk_flags:
            st.caption("Primary player risk flags")
            for flag in risk_flags:
                st.warning(flag)

    with risk_cols[1]:
        st.subheader("Recent Events")
        event_rows = event_table(events.get("recent_events", []))
        if event_rows:
            st.dataframe(event_rows, use_container_width=True, hide_index=True)
        else:
            st.info("No recent events available yet.")

with history_tab:
    st.subheader("Runtime Session History")
    st.caption("This in-app history buffer prepares the dashboard for future saved-session comparison.")

    if history:
        history_rows = [
            {
                "frame_index": row.get("frame_index"),
                "timestamp_seconds": row.get("timestamp_seconds"),
                "players_detected": row.get("players_detected"),
                "ball_speed_px_per_sec": row.get("ball_speed_px_per_sec"),
                "impact_power_score": row.get("impact_power_score"),
                "avg_posture_score": row.get("avg_posture_score"),
                "active_swing_count": row.get("active_swing_count"),
                "contact_candidate_count": row.get("contact_candidate_count"),
                "recommendation_count": row.get("recommendation_count"),
                "injury_risk_count": row.get("injury_risk_count"),
            }
            for row in history
        ]
        st.dataframe(history_rows, use_container_width=True, hide_index=True)
    else:
        st.info("History will populate as new frames are processed.")

    history_chart_cols = st.columns(2)
    with history_chart_cols[0]:
        posture_chart_values = [row.get("avg_posture_score") for row in history if row.get("avg_posture_score") is not None]
        if posture_chart_values:
            st.line_chart({"Posture score": posture_chart_values}, use_container_width=True)

    with history_chart_cols[1]:
        alert_chart = {
            "Injury risk": [row.get("injury_risk_count", 0) for row in history],
            "Impact power": [row.get("impact_power_score", 0) or 0 for row in history],
            "Recommendations": [row.get("recommendation_count", 0) for row in history],
        }
        if history:
            st.bar_chart(alert_chart, use_container_width=True)

# ---------------------------------------------------------------------------
# Phase 4 – Review Room tab
# ---------------------------------------------------------------------------
with review_tab:
    st.subheader("🔍 Review Room")
    st.caption(
        "Frames where any player's posture score dropped below the threshold, or injury risk was flagged, "
        "are automatically saved here. Use these to review exact moments of poor form."
    )

    bad_frames: list[dict] = clip_summary.get("bad_frames", [])
    snippet_index: dict = clip_summary.get("snippet_index", {})
    snippet_count: int = clip_summary.get("snippet_count", 0)
    bad_frame_count: int = clip_summary.get("bad_frame_count", 0)

    review_metric_cols = st.columns(3)
    review_metric_cols[0].metric("Flagged Frames", bad_frame_count)
    review_metric_cols[1].metric("Metric Clips Saved", snippet_count)
    review_metric_cols[2].metric("Clip Types", len(snippet_index))

    st.divider()

    # --- Flagged frame gallery ---
    st.subheader("Flagged Frame Gallery")
    if bad_frames:
        # Show 3 images per row
        COLS_PER_ROW = 3
        for row_start in range(0, len(bad_frames), COLS_PER_ROW):
            batch = bad_frames[row_start : row_start + COLS_PER_ROW]
            cols = st.columns(COLS_PER_ROW)
            for col, frame_record in zip(cols, batch):
                frame_path = Path(frame_record.get("frame_path", ""))
                reason = frame_record.get("reason", "Unknown reason")
                timestamp = frame_record.get("timestamp", "-")
                frame_idx = frame_record.get("frame_index", "-")
                with col:
                    if frame_path.exists():
                        st.image(
                            str(frame_path),
                            caption=f"⏱ {timestamp}  |  Frame {frame_idx}",
                            use_container_width=True,
                        )
                    else:
                        st.warning("Frame file not found.")
                    st.error(f"⚠ {reason}")
    else:
        st.success("No flagged frames yet. Good form so far, or the session has not started.")

    st.divider()

    # --- Metric snippet video player ---
    st.subheader("Metric Clip Viewer")
    st.caption("Select a metric type below to play the saved video clip for that event.")
    if snippet_index:
        selected_metric = st.selectbox(
            "Choose a metric clip to play",
            options=list(snippet_index.keys()),
            format_func=lambda k: k.replace("_", " ").title(),
            key="review_room_metric_select",
        )
        clips_for_metric = snippet_index.get(selected_metric, [])
        if clips_for_metric:
            for idx, clip_path in enumerate(clips_for_metric, start=1):
                p = Path(clip_path)
                st.caption(f"Clip {idx} — {p.name}")
                if p.exists():
                    st.video(str(p))
                else:
                    st.warning(f"Clip file missing: {p.name}")
        else:
            st.info("No clips saved for this metric yet.")
    else:
        st.info("No metric clips have been saved yet. Run the detector to generate them.")

with raw_tab:
    raw_cols = st.columns(2)

    with raw_cols[0]:
        st.subheader("Primary Player Detail")
        if primary:
            st.json(primary)
        else:
            st.info("No primary player available yet.")

    with raw_cols[1]:
        st.subheader("Impact And Recommendation Snapshot")
        st.json(
            {
                "impact_power": impact_power,
                "recommendations": recommendations,
            }
        )

    if output_video_path.exists():
        st.subheader("Processed Match Video")
        st.video(str(output_video_path))

    st.subheader("Current Payload")
    st.json(data)

notes = data.get("notes", [])
if notes:
    st.subheader("Pipeline Notes")
    for note in notes:
        render_note(note)

if auto_refresh:
    time.sleep(2)
    st.rerun()
