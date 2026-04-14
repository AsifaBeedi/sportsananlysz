from __future__ import annotations

import json
import time
import base64
from datetime import datetime
from pathlib import Path
import re

import streamlit as st

# ============================================================================
# DIRECT FILE READING - Ignores JSON paths completely
# ============================================================================

def find_all_bad_frames():
    """Directly read all JPG files from data/review_frames"""
    review_dir = Path("data/review_frames")
    if not review_dir.exists():
        return []
    
    frames = []
    for img_path in sorted(review_dir.glob("*.jpg")):
        name = img_path.stem
        numbers = re.findall(r'\d+', name)
        frame_num = numbers[1] if len(numbers) > 1 else "unknown"
        
        if "Low_Posture" in name or "Low Posture" in name:
            score_match = re.search(r'\((\d+)\)', name)
            score = score_match.group(1) if score_match else "?"
            reason = f"Low Posture Score ({score})"
        elif "injury" in name.lower():
            reason = "Injury Risk Detected"
        else:
            reason = "Flagged Frame"
        
        timestamp_match = re.search(r'(\d+\.?\d*)s', name)
        timestamp = f"{timestamp_match.group(1)}s" if timestamp_match else "-"
        
        frames.append({
            "path": img_path,
            "frame_index": frame_num,
            "reason": reason,
            "timestamp": timestamp,
            "filename": img_path.name
        })
    return frames

def find_all_snippets():
    """Directly read all MP4 files from data/snippets"""
    snippets_dir = Path("data/snippets")
    if not snippets_dir.exists():
        return {}
    
    snippets = {}
    for video_path in snippets_dir.glob("*.mp4"):
        name = video_path.stem
        if "contact" in name:
            metric = "contact_candidate"
        elif "injury_risk_player_1" in name:
            metric = "injury_risk_player_1"
        elif "injury_risk_player_2" in name:
            metric = "injury_risk_player_2"
        elif "injury_risk_player_6" in name:
            metric = "injury_risk_player_6"
        elif "injury_risk_player_14" in name:
            metric = "injury_risk_player_14"
        else:
            metric = "other"
        
        if metric not in snippets:
            snippets[metric] = []
        snippets[metric].append(video_path)
    
    return snippets

def get_preview_frame():
    """Get preview frame from root"""
    paths = [
        Path("latest_annotated_frame.jpg"),
        Path("data/latest_annotated_frame.jpg"),
    ]
    for p in paths:
        if p.exists():
            return p
    return None

def get_output_video():
    """Get output video from root"""
    paths = [
        Path("annotated_match_output.mp4"),
        Path("data/annotated_match_output.mp4"),
    ]
    for p in paths:
        if p.exists():
            return p
    return None

def play_video(video_path):
    """Play video using HTML5 player (works every time)"""
    if not video_path or not video_path.exists():
        st.warning("Video file not found")
        return False
    
    try:
        with open(video_path, "rb") as f:
            video_bytes = f.read()
        
        video_base64 = base64.b64encode(video_bytes).decode()
        file_size = video_path.stat().st_size / (1024 * 1024)
        
        st.markdown(
            f'''
            <video width="100%" controls autoplay>
                <source src="data:video/mp4;base64,{video_base64}" type="video/mp4">
                Your browser does not support the video tag.
            </video>
            ''',
            unsafe_allow_html=True
        )
        st.caption(f"File: {video_path.name} | Size: {file_size:.1f} MB")
        return True
    except Exception as e:
        st.error(f"Error playing video: {e}")
        return False

# ============================================================================
# LOAD DATA FROM JSON
# ============================================================================

def find_stats_file():
    """Find match_stats.json"""
    paths = [
        Path("match_stats.json"),
        Path("data/match_stats.json"),
        Path("data/models/scripts/match_stats.json"),
    ]
    for p in paths:
        if p.exists():
            return p
    return None

def default_payload():
    return {
        "status": "idle",
        "phase": "phase_9_dashboard",
        "core_mode": "sport_agnostic",
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

def load_stats():
    """Load stats from match_stats.json"""
    defaults = default_payload()
    stats_path = find_stats_file()
    
    if not stats_path:
        return defaults

    try:
        with stats_path.open(encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return defaults

    for key in defaults:
        if key not in data:
            data[key] = defaults[key]
    
    return data

def format_value(value, digits=2, suffix=""):
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.{digits}f}{suffix}"
    return f"{value}{suffix}"

def metric_delta(current, previous, digits=2):
    if current is None or previous is None:
        return None
    if not isinstance(current, (int, float)) or not isinstance(previous, (int, float)):
        return None
    change = current - previous
    if abs(change) < 1e-9:
        return "0"
    return f"{change:+.{digits}f}"

def parse_iso_timestamp(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None

def current_data_age_seconds(data):
    updated_at = parse_iso_timestamp(data.get("last_updated_at"))
    if updated_at is not None:
        return max(0.0, round((datetime.now() - updated_at).total_seconds(), 2))
    return None

def freshness_label(age_seconds, status):
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

def primary_player(players, primary_player_id):
    if primary_player_id is None:
        return players[0] if players else None
    for player in players:
        if player.get("track_id") == primary_player_id:
            return player
    return players[0] if players else None

def player_table(players):
    rows = []
    for player in players:
        posture = (player.get("pose") or {}).get("posture", {})
        event_state = player.get("event_state") or {}
        racket_state = player.get("racket") or {}
        rows.append({
            "Player ID": player.get("track_id"),
            "Speed (px/frame)": player.get("speed_px"),
            "Posture": posture.get("posture_label"),
            "Posture Score": posture.get("posture_score"),
            "Risk": posture.get("injury_risk_level"),
            "Swing Phase": event_state.get("swing_phase"),
            "Shot Candidate": event_state.get("shot_label_candidate"),
            "Racket Direction": racket_state.get("swing_direction"),
        })
    return rows

def event_table(recent_events):
    rows = []
    for event in recent_events:
        rows.append({
            "Frame": event.get("frame_index"),
            "Type": event.get("event_type"),
            "Player": event.get("track_id"),
            "Shot": event.get("shot_label"),
            "Timestamp (s)": event.get("timestamp_seconds"),
        })
    return rows

def render_recommendation_card(item):
    category = str(item.get("category", "general")).replace("_", " ").title()
    priority = str(item.get("priority", "info")).upper()
    title = item.get("title", "Recommendation")
    detail = item.get("detail", "")
    evidence = item.get("evidence", {})

    with st.container(border=True):
        st.markdown(f"**{title}**")
        st.caption(f"{category} | Priority: {priority}")
        if detail:
            st.write(detail)
        if evidence:
            with st.expander("Why this showed up"):
                st.json(evidence)

def render_note(note):
    lowered = note.lower()
    if "active" in lowered or "completed" in lowered:
        st.success(note)
        return
    if "warning" in lowered or "risk" in lowered or "alert" in lowered:
        st.warning(note)
        return
    st.info(note)

def render_key_value_block(title, items):
    st.subheader(title)
    for label, value in items:
        display_value = value if value not in (None, "", [], {}) else "-"
        st.write(f"**{label}:** {display_value}")

def save_uploaded_video(uploaded_file):
    UPLOADS_DIR = Path("uploaded_videos")
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    target_path = UPLOADS_DIR / Path(uploaded_file.name).name
    target_path.write_bytes(uploaded_file.getbuffer())
    return target_path

def render_login_page():
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

def render_sidebar(data, history):
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

def update_history(data):
    frame_index = int(data.get("frame_index", 0) or 0)
    session_key = (data.get("sport", "unknown"), data.get("source_video", "unknown"))
    session_key_name = "dashboard_session_key"
    history_key = "dashboard_history"

    if st.session_state.get(session_key_name) != session_key:
        st.session_state[session_key_name] = session_key
        st.session_state[history_key] = []

    history = st.session_state.setdefault(history_key, [])
    if history and frame_index < history[-1]["frame_index"]:
        history.clear()

    if history and frame_index == history[-1]["frame_index"]:
        return history

    summary = data.get("summary", {})
    history.append({
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
    })
    
    MAX_HISTORY_POINTS = 120
    if len(history) > MAX_HISTORY_POINTS:
        del history[:-MAX_HISTORY_POINTS]
    return history

def reset_dashboard_files():
    payload = default_payload()
    stats_path = find_stats_file()
    if stats_path:
        stats_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

# ============================================================================
# MAIN APP
# ============================================================================

st.set_page_config(page_title="Sports AI Analytics Dashboard", layout="wide")

# Initialize session state
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "username" not in st.session_state:
    st.session_state["username"] = ""
if "app_page" not in st.session_state:
    st.session_state["app_page"] = "Live"
if "auto_refresh" not in st.session_state:
    st.session_state["auto_refresh"] = False
if "selected_video" not in st.session_state:
    st.session_state.selected_video = None
if "selected_review_frame" not in st.session_state:
    st.session_state.selected_review_frame = None

# Authentication
if not st.session_state["authenticated"]:
    render_login_page()
    st.stop()

# Load data
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
notes = data.get("notes", [])
data_age_seconds = current_data_age_seconds(data)
data_freshness = freshness_label(data_age_seconds, str(data.get("status", "unknown")))

# Directly read files
bad_frames = find_all_bad_frames()
snippets = find_all_snippets()
preview_path = get_preview_frame()
output_video_path = get_output_video()

# Update history
history = update_history(data)
previous_history = history[-2] if len(history) > 1 else {}

# Get primary player
primary = primary_player(players, events.get("primary_player_id"))
primary_posture = ((primary.get("pose") or {}).get("posture", {}) if primary else {})
primary_event_state = (primary.get("event_state") or {} if primary else {})
primary_racket = (primary.get("racket") or {} if primary else {})

# ============================================================================
# SIDEBAR
# ============================================================================
render_sidebar(data, history)

if st.sidebar.button("Log Out"):
    st.session_state["authenticated"] = False
    st.session_state["username"] = ""
    st.rerun()

# ============================================================================
# MAIN CONTENT
# ============================================================================

st.title("SPORTS AI ANALYTICS DASHBOARD")
st.caption(
    f"{sport_profile.get('display_name', data.get('sport', 'Unknown'))} profile | "
    f"{sport_profile.get('equipment_name', 'equipment').title()} tracking | "
    f"Sport-agnostic analytics core"
)

# Navigation
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

# Session info row
session_cols = st.columns([2, 1, 1, 2])
session_cols[0].metric("Video Being Processed", data.get("source_video", "unknown"))
session_cols[1].metric("Data State", data_freshness)
session_cols[2].metric("Data Age", format_value(data_age_seconds, 1, " s"))
session_cols[3].metric("Session ID", data.get("session_id") or "-")

if data_freshness == "Stale":
    st.warning("Dashboard showing last saved session. Start detector or click Refresh.")
elif data_freshness == "Old Output":
    st.info("Showing most recent completed run, not an updating live session.")

# ============================================================================
# UPLOAD VIDEO PAGE
# ============================================================================
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
        st.code(f'python detector.py --sport tennis --video "{uploaded_video_path}"')

    st.stop()

# ============================================================================
# LIVE PAGE
# ============================================================================
if selected_page == "Live":
    live_cols = st.columns([3, 2])
    with live_cols[0]:
        st.subheader("Live Analysis Frame")
        if preview_path and preview_path.exists():
            st.image(str(preview_path), use_container_width=True, 
                     caption=f"Annotated frame from {data.get('source_video', 'unknown')}")
        else:
            st.info("No analyzed frame available. Run detector to generate preview.")

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
        if output_video_path and output_video_path.exists():
            st.caption(f"Processed video saved at: {output_video_path}")

    live_metrics = st.columns(5)
    live_metrics[0].metric("Players", format_value(summary.get("players_detected"), 0))
    live_metrics[1].metric("Ball Speed", format_value(summary.get("ball_speed_px_per_sec"), 2, " px/s"))
    live_metrics[2].metric("Swings", format_value(summary.get("active_swing_count"), 0))
    live_metrics[3].metric("Impact Power", format_value(summary.get("impact_power_score"), 1))
    live_metrics[4].metric("Advice", format_value(summary.get("recommendation_count"), 0))

    if output_video_path and output_video_path.exists():
        st.subheader("Latest Processed Match Video")
        play_video(output_video_path)

    if notes:
        st.subheader("Pipeline Notes")
        for note in notes:
            render_note(note)

    if auto_refresh:
        time.sleep(2)
        st.rerun()
    st.stop()

# ============================================================================
# DASHBOARD PAGE (Full Analytics)
# ============================================================================

preview_cols = st.columns([3, 2])
with preview_cols[0]:
    st.subheader("Live Analysis Frame")
    if preview_path and preview_path.exists():
        st.image(str(preview_path), use_container_width=True,
                 caption=f"Annotated frame from {data.get('source_video', 'unknown')}")
    else:
        st.info("No analyzed frame available. Run detector to generate preview.")

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
    if output_video_path and output_video_path.exists():
        st.caption(f"Processed video saved at: {output_video_path}")

# Metrics row with deltas
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

# ============================================================================
# TABS
# ============================================================================
overview_tab, motion_tab, recommendations_tab, history_tab, review_tab, raw_tab = st.tabs(
    ["Overview", "Motion", "Recommendations", "History", "Review Room", "Raw Data"]
)

# ----------------------------------------------------------------------------
# OVERVIEW TAB
# ----------------------------------------------------------------------------
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
            st.progress(max(0.0, min(float(posture_score) / 100.0, 1.0)), 
                       text=f"Primary posture score: {posture_score}")

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

# ----------------------------------------------------------------------------
# MOTION TAB
# ----------------------------------------------------------------------------
with motion_tab:
    motion_cols = st.columns(2)

    with motion_cols[0]:
        st.subheader("Ball Speed Trend")
        speed_series = ball_speed.get("speed_series", [])
        speed_values = [point.get("speed_px_per_sec") for point in speed_series 
                       if point.get("speed_px_per_sec") is not None]
        if speed_values:
            st.line_chart({"Ball speed (px/s)": speed_values}, use_container_width=True)
        else:
            st.info("Ball speed trend will appear once a tracked trajectory is available.")

        st.write({
            "current_speed_px_per_sec": ball_speed.get("current_speed"),
            "avg_recent_speed_px_per_sec": ball_speed.get("avg_recent_speed_px_per_sec"),
            "peak_speed_px_per_sec": ball_speed.get("peak_speed_px_per_sec"),
            "contact_speed_comparison": ball_speed.get("contact_comparison"),
        })

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
        st.write({
            "status": ball_tracking.get("status"),
            "missed_frames": ball_tracking.get("missed_frames"),
            "raw_center": ball_tracking.get("raw_center"),
            "smoothed_center": ball_tracking.get("smoothed_center"),
            "latest_direction_change": ball_tracking.get("latest_direction_change"),
        })
        recent_history = ball_tracking.get("history", [])[-8:]
        if recent_history:
            st.dataframe(recent_history, use_container_width=True, hide_index=True)

    with detail_cols[1]:
        st.subheader("Racket Motion Detail")
        st.write({
            "active_track_ids": racket.get("active_track_ids", []),
            "latest_primary_state": racket.get("latest_primary_state"),
            "recent_primary_path_points": len(racket.get("recent_primary_path", [])),
        })
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

# ----------------------------------------------------------------------------
# RECOMMENDATIONS TAB
# ----------------------------------------------------------------------------
with recommendations_tab:
    recommendation_cols = st.columns(2)

    with recommendation_cols[0]:
        st.subheader("Session Recommendations")
        session_recommendations = recommendations.get("session_recommendations", [])
        if session_recommendations:
            for item in session_recommendations:
                render_recommendation_card(item)
        else:
            st.success("No session-level recommendations yet.")

    with recommendation_cols[1]:
        st.subheader("Player Coaching Notes")
        player_recommendations = recommendations.get("player_recommendations", {})
        if player_recommendations:
            for player_id, items in player_recommendations.items():
                st.markdown(f"**Player {player_id}**")
                for item in items:
                    render_recommendation_card(item)
        else:
            st.success("No player-specific coaching notes yet.")

    risk_cols = st.columns(2)
    with risk_cols[0]:
        st.subheader("Risk And Alert Summary")
        risk_metric_cols = st.columns(2)
        risk_metric_cols[0].metric("Injury Risk Flags", summary.get("injury_risk_count", 0))
        risk_metric_cols[1].metric("Fall Alerts", summary.get("fall_alerts", 0))
        st.write({
            "players_with_pose": pose_summary.get("players_with_pose"),
            "primary_posture_label": primary_posture.get("posture_label"),
            "primary_risk_level": primary_posture.get("injury_risk_level"),
        })
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

# ----------------------------------------------------------------------------
# HISTORY TAB
# ----------------------------------------------------------------------------
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
        posture_chart_values = [row.get("avg_posture_score") for row in history 
                               if row.get("avg_posture_score") is not None]
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

# ----------------------------------------------------------------------------
# REVIEW ROOM TAB
# ----------------------------------------------------------------------------
with review_tab:
    st.subheader("Review Room")
    st.caption(
        "Frames where any player's posture score dropped below the threshold, or injury risk was flagged, "
        "are automatically saved here. Use these to review exact moments of poor form."
    )

    review_metric_cols = st.columns(3)
    review_metric_cols[0].metric("Flagged Frames", len(bad_frames))
    review_metric_cols[1].metric("Metric Clips Saved", sum(len(v) for v in snippets.values()))
    review_metric_cols[2].metric("Clip Types", len(snippets))

    st.divider()

    # Flagged frame gallery
    st.subheader("Flagged Frame Gallery")
    if bad_frames:
        COLS_PER_ROW = 3
        for row_start in range(0, len(bad_frames), COLS_PER_ROW):
            batch = bad_frames[row_start:row_start + COLS_PER_ROW]
            cols = st.columns(COLS_PER_ROW)
            
            for col, frame_record in zip(cols, batch):
                with col:
                    if frame_record["path"].exists():
                        if st.button(f"▶ Frame {frame_record['frame_index']}", key=f"btn_{frame_record['frame_index']}", use_container_width=True):
                            st.session_state.selected_review_frame = frame_record['frame_index']
                        st.image(str(frame_record["path"]), use_container_width=True)
                        st.caption(f"⏱ {frame_record['timestamp']}")
                        st.error(frame_record['reason'])
                    else:
                        st.warning(f"Missing: {frame_record['filename']}")
                        st.caption(f"Frame {frame_record['frame_index']}")
        
        # Show selected clip
        if st.session_state.selected_review_frame:
            st.divider()
            st.subheader(f"Clip for Frame {st.session_state.selected_review_frame}")
            frame_str = str(st.session_state.selected_review_frame)
            found_clip = None
            for metric, clips in snippets.items():
                for clip_path in clips:
                    if frame_str in clip_path.stem:
                        found_clip = clip_path
                        break
                if found_clip:
                    break
            
            if found_clip and found_clip.exists():
                play_video(found_clip)
            else:
                st.info("No video clip found for this exact frame. Try selecting from dropdown below.")
    else:
        st.success("No flagged frames yet. Good form so far, or the session has not started.")

    st.divider()

    # Metric snippet video player
    st.subheader("Metric Clip Viewer")
    st.caption("Select a metric type below to play the saved video clip for that event.")
    if snippets:
        selected_metric = st.selectbox(
            "Choose a metric clip to play",
            options=list(snippets.keys()),
            format_func=lambda k: k.replace("_", " ").title(),
            key="review_room_metric_select",
        )
        clips_for_metric = snippets.get(selected_metric, [])
        if clips_for_metric:
            for idx, clip_path in enumerate(clips_for_metric, start=1):
                st.caption(f"Clip {idx} — {clip_path.name}")
                play_video(clip_path)
        else:
            st.info("No clips saved for this metric yet.")
    else:
        st.info("No metric clips have been saved yet. Run the detector to generate them.")

# ----------------------------------------------------------------------------
# RAW DATA TAB
# ----------------------------------------------------------------------------
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
        st.json({
            "impact_power": impact_power,
            "recommendations": recommendations,
        })

    if output_video_path and output_video_path.exists():
        st.subheader("Processed Match Video")
        play_video(output_video_path)

    st.subheader("Current Payload")
    st.json(data)

# ============================================================================
# NOTES & AUTO REFRESH
# ============================================================================
if notes:
    st.subheader("Pipeline Notes")
    for note in notes:
        render_note(note)

if auto_refresh:
    time.sleep(2)
    st.rerun()