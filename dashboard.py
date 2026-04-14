from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import streamlit as st

# ============================================================================
# PATH HELPER - Works with YOUR exact folder structure
# ============================================================================

def find_stats_file() -> Path:
    """Find match_stats.json in your folder structure."""
    possible_paths = [
        Path("data/match_stats.json"),                    # Your JSON location
        Path("match_stats.json"),
        Path("data/models/scripts/match_stats.json"),
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    return Path("data/match_stats.json")


def make_portable_path(file_path: str) -> Path:
    """Convert any path to work with your folder structure."""
    if not file_path:
        return Path("")
    
    path = Path(file_path)
    
    # If it already exists, return it
    if path.exists():
        return path
    
    # Get just the filename
    filename = path.name
    
    # Search in your actual folder structure
    search_locations = [
        Path("data/review_frames") / filename,   # Your bad frames
        Path("data/snippets") / filename,        # Your video clips
        Path("data") / filename,                  # Preview frame & output video
        Path("review_frames") / filename,
        Path("snippets") / filename,
        Path(filename),
    ]
    
    for loc in search_locations:
        if loc.exists():
            return loc
    
    return path


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
    """Load stats from match_stats.json in your folder structure."""
    defaults = default_payload()
    stats_path = find_stats_file()
    
    if not stats_path.exists():
        st.warning(f"Stats file not found at: {stats_path}")
        return defaults

    try:
        with stats_path.open(encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError) as e:
        broken_payload = merge_with_defaults({}, defaults)
        broken_payload["status"] = "unavailable"
        broken_payload["notes"] = [f"Could not read analytics output: {str(e)}"]
        return broken_payload

    if "summary" in data:
        return merge_with_defaults(data, defaults)

    legacy_payload = merge_with_defaults({}, defaults)
    legacy_payload.update(
        {
            "status": "legacy",
            "phase": "prototype",
            "sport": "unknown",
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
                "Player": event.get("track_id"),
                "Shot": event.get("shot_label"),
                "Timestamp (s)": event.get("timestamp_seconds"),
            }
        )
    return rows


def render_recommendation_card(item: dict) -> None:
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


# ============================================================================
# MAIN APP
# ============================================================================

st.set_page_config(page_title="Sports AI Analytics Dashboard", layout="wide")

# Initialize session state
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = True
if "auto_refresh" not in st.session_state:
    st.session_state["auto_refresh"] = False
if "selected_frame" not in st.session_state:
    st.session_state.selected_frame = None

# Load data
data = load_stats()
summary = data.get("summary", {})
sport_profile = data.get("sport_profile", {})
pose_summary = data.get("pose", {}).get("summary", {})
events = data.get("events", {})
ball_tracking = data.get("ball_tracking", {})
ball_speed = data.get("ball_speed", {})
impact_power = data.get("impact_power", {})
recommendations = data.get("recommendations", {})
players = data.get("players", [])
clip_summary = data.get("clip_summary", {})
data_age_seconds = current_data_age_seconds(data)
data_freshness = freshness_label(data_age_seconds, str(data.get("status", "unknown")))

# Fix paths for your folder structure
preview_frame_path = make_portable_path(data.get("preview_frame_path", ""))
output_video_path = make_portable_path(data.get("output_video_path", ""))

primary = primary_player(players, events.get("primary_player_id"))

# ============================================================================
# SIDEBAR
# ============================================================================

st.sidebar.title("🎾 Session")
st.sidebar.caption("Sport-agnostic core")
st.sidebar.write(f"**Sport:** {sport_profile.get('display_name', data.get('sport', 'unknown'))}")
st.sidebar.write(f"**Phase:** {data.get('phase', 'unknown')}")
st.sidebar.write(f"**Status:** {data.get('status', 'unknown')}")
st.sidebar.write(f"**Session ID:** {data.get('session_id') or '-'}")
st.sidebar.write(f"**Video:** {data.get('source_video', 'unknown')}")
st.sidebar.write(f"**Frame:** {data.get('frame_index', 0)}")
st.sidebar.write(f"**Time:** {format_value(data.get('timestamp_seconds'), 2, ' s')}")

st.sidebar.divider()
st.sidebar.metric("👥 Tracked Players", len(summary.get("tracked_player_ids", [])))
st.sidebar.metric("🎯 Ball Track", "Active" if ball_tracking.get("active") else "Waiting")
st.sidebar.metric("💡 Recommendations", summary.get("recommendation_count", 0))

notes = data.get("notes", [])
if notes:
    st.sidebar.divider()
    st.sidebar.subheader("📝 Notes")
    for note in notes[:4]:
        st.sidebar.write(f"- {note}")

# ============================================================================
# MAIN CONTENT
# ============================================================================

st.title("🎾 SPORTS AI ANALYTICS DASHBOARD")
st.caption(f"{sport_profile.get('display_name', data.get('sport', 'Unknown'))} | Real-time player & ball tracking | Sport-agnostic core")

# Refresh controls
col1, col2, col3, col4 = st.columns([1, 1, 1, 6])
if col1.button("🔄 Refresh", use_container_width=True):
    st.rerun()
auto_refresh = col2.toggle("Auto Refresh", value=st.session_state.get("auto_refresh", False))
st.session_state["auto_refresh"] = auto_refresh
if col3.button("📁 Show Paths", use_container_width=True):
    with st.expander("File Paths Debug"):
        st.write(f"Stats file: {find_stats_file()}")
        st.write(f"Preview frame: {preview_frame_path}")
        st.write(f"Preview exists: {preview_frame_path.exists()}")
        st.write(f"Output video: {output_video_path}")
        st.write(f"Output exists: {output_video_path.exists()}")
        st.write(f"Review frames dir: {Path('data/review_frames').exists()}")
        st.write(f"Snippets dir: {Path('data/snippets').exists()}")

# ============================================================================
# METRIC ROW
# ============================================================================

st.subheader("📊 Live Metrics")
metric_cols = st.columns(6)
metric_cols[0].metric("👥 Players", format_value(summary.get("players_detected"), 0))
metric_cols[1].metric("⚡ Ball Speed", format_value(summary.get("ball_speed_px_per_sec"), 2, " px/s"))
metric_cols[2].metric("🧘 Posture", format_value(summary.get("avg_posture_score"), 0))
metric_cols[3].metric("🏓 Swings", format_value(summary.get("active_swing_count"), 0))
metric_cols[4].metric("💪 Impact", format_value(summary.get("impact_power_score"), 1))
metric_cols[5].metric("💡 Advice", format_value(summary.get("recommendation_count"), 0))

# ============================================================================
# LIVE ANALYSIS FRAME & STATUS
# ============================================================================

live_cols = st.columns([3, 2])

with live_cols[0]:
    st.subheader("📸 Live Analysis Frame")
    if preview_frame_path.exists():
        st.image(str(preview_frame_path), use_container_width=True,
                 caption=f"Frame {data.get('frame_index', 0)} at {data.get('timestamp_seconds', 0)}s")
    else:
        st.warning("Preview frame not found")
        st.info(f"Looking for: {preview_frame_path}")
        st.caption("Make sure latest_annotated_frame.jpg is in the 'data/' folder")

with live_cols[1]:
    render_key_value_block(
        "📋 Session Status",
        [
            ("Session ID", data.get("session_id")),
            ("Session Started", data.get("session_started_at")),
            ("Last Updated", data.get("last_updated_at")),
            ("Status", data_freshness),
            ("Source Video", data.get("source_video")),
            ("Frame Index", data.get("frame_index")),
            ("Runtime", format_value(data.get("runtime_seconds"), 1, " s")),
        ],
    )
    if output_video_path.exists():
        st.video(str(output_video_path))
    elif data.get("output_video_path"):
        st.info(f"Output video: {Path(data.get('output_video_path')).name}")

# ============================================================================
# TABS
# ============================================================================

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📊 Overview", "📈 Motion", "💡 Recommendations", "🔍 Review Room", "📄 Raw Data"]
)

# ---------------------------------------------------------------------------
# TAB 1: OVERVIEW
# ---------------------------------------------------------------------------
with tab1:
    st.subheader("👥 Tracked Players")
    player_rows = player_table(players)
    if player_rows:
        st.dataframe(player_rows, use_container_width=True, hide_index=True)
    else:
        st.info("No tracked players available yet.")
    
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        render_key_value_block(
            "📋 Session Summary",
            [
                ("Status", data.get("status")),
                ("Sport", sport_profile.get("display_name")),
                ("Equipment", sport_profile.get("equipment_name")),
                ("Players with Pose", pose_summary.get("players_with_pose", 0)),
                ("Average Posture Score", pose_summary.get("avg_posture_score")),
                ("Injury Risk Players", pose_summary.get("injury_risk_player_ids", [])),
            ],
        )
    with col2:
        render_key_value_block(
            "🎯 Ball & Racket Tracking",
            [
                ("Ball Track Active", "Yes" if ball_tracking.get("active") else "No"),
                ("Trajectory Length", ball_tracking.get("trajectory_length")),
                ("Racket Track Active", "Yes" if summary.get("racket_track_active") else "No"),
                ("Racket Path Length", format_value(summary.get("racket_path_length_px"), 1, " px")),
                ("Primary Player", events.get("primary_player_id")),
            ],
        )

# ---------------------------------------------------------------------------
# TAB 2: MOTION
# ---------------------------------------------------------------------------
with tab2:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🏃 Ball Speed Trend")
        speed_series = ball_speed.get("speed_series", [])
        if speed_series:
            speed_values = [s.get("speed_px_per_sec", 0) for s in speed_series if s.get("speed_px_per_sec") is not None]
            if speed_values:
                st.line_chart({"Ball Speed (px/s)": speed_values}, use_container_width=True)
        else:
            st.info("Ball speed data will appear once tracking is active")
        
        st.json({
            "Current Speed": ball_speed.get("current_speed"),
            "Peak Speed": ball_speed.get("peak_speed_px_per_sec"),
            "Average Speed": ball_speed.get("avg_recent_speed_px_per_sec"),
        })
    
    with col2:
        st.subheader("📅 Recent Events")
        recent_events = events.get("recent_events", [])
        if recent_events:
            st.dataframe(event_table(recent_events[-10:]), use_container_width=True, hide_index=True)
        else:
            st.info("No recent events recorded")
        
        st.subheader("🎾 Racket Speed")
        racket_speed_series = impact_power.get("racket_speed_series", [])
        if racket_speed_series:
            speed_values = [s.get("speed_px_per_sec", 0) for s in racket_speed_series]
            st.line_chart({"Racket Speed (px/s)": speed_values}, use_container_width=True)

# ---------------------------------------------------------------------------
# TAB 3: RECOMMENDATIONS
# ---------------------------------------------------------------------------
with tab3:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📋 Session Recommendations")
        session_recs = recommendations.get("session_recommendations", [])
        if session_recs:
            for rec in session_recs:
                render_recommendation_card(rec)
        else:
            st.success("No session recommendations yet")
    
    with col2:
        st.subheader("👤 Player Recommendations")
        player_recs = recommendations.get("player_recommendations", {})
        if player_recs:
            for player_id, recs in player_recs.items():
                st.markdown(f"**Player {player_id}**")
                for rec in recs:
                    render_recommendation_card(rec)
        else:
            st.success("No player recommendations yet")
    
    # Risk summary
    st.divider()
    st.subheader("⚠️ Risk & Alert Summary")
    risk_col1, risk_col2, risk_col3 = st.columns(3)
    risk_col1.metric("Injury Risk Flags", summary.get("injury_risk_count", 0))
    risk_col2.metric("Fall Alerts", summary.get("fall_alerts", 0))
    risk_col3.metric("Contact Candidates", summary.get("contact_candidate_count", 0))

# ---------------------------------------------------------------------------
# TAB 4: REVIEW ROOM
# ---------------------------------------------------------------------------
with tab4:
    st.subheader("🔍 Review Room")
    st.caption("Frames with poor posture or injury risk are automatically captured here. Click any frame to review the video clip.")
    
    bad_frames = clip_summary.get("bad_frames", [])
    snippet_index = clip_summary.get("snippet_index", {})
    snippet_count = clip_summary.get("snippet_count", 0)
    bad_frame_count = clip_summary.get("bad_frame_count", 0)
    
    # Summary metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("🚩 Flagged Frames", bad_frame_count)
    col2.metric("🎬 Video Clips", snippet_count)
    col3.metric("📊 Metric Types", len(snippet_index))
    
    st.divider()
    
    if bad_frames:
        st.subheader("🖼️ Flagged Frame Gallery")
        st.caption("Click 'Play' on any frame to see the corresponding video clip")
        
        # Display frames in a grid
        for i, frame_record in enumerate(bad_frames):
            frame_path = make_portable_path(frame_record.get("frame_path", ""))
            reason = frame_record.get("reason", "Unknown reason")
            timestamp = frame_record.get("timestamp", "-")
            frame_idx = frame_record.get("frame_index", "-")
            
            cols = st.columns([1, 3, 1, 1])
            with cols[0]:
                if frame_path.exists():
                    st.image(str(frame_path), use_container_width=True)
                else:
                    st.warning(f"Missing: {frame_path.name}")
                    st.caption(f"Expected in: data/review_frames/")
            
            with cols[1]:
                st.caption(f"**Frame {frame_idx}** at {timestamp}")
                st.write(reason[:150] if len(reason) > 150 else reason)
            
            with cols[2]:
                if st.button(f"▶ Play", key=f"play_{i}_{frame_idx}", use_container_width=True):
                    st.session_state.selected_frame = frame_idx
            
            with cols[3]:
                if st.button(f"📋 Copy", key=f"copy_{i}_{frame_idx}", use_container_width=True):
                    st.toast(f"Frame {frame_idx} info copied to clipboard")
            
            st.divider()
        
        # Show selected clip
        if st.session_state.selected_frame:
            st.subheader(f"🎥 Video Clip for Frame {st.session_state.selected_frame}")
            frame_str = str(st.session_state.selected_frame)
            found_clip = None
            found_metric = None
            
            for metric, clips in snippet_index.items():
                for clip_path in clips:
                    if frame_str in str(clip_path):
                        found_clip = make_portable_path(clip_path)
                        found_metric = metric
                        break
                if found_clip:
                    break
            
            if found_clip and found_clip.exists():
                st.caption(f"Metric type: {found_metric.replace('_', ' ').title()}")
                st.video(str(found_clip))
            else:
                st.info("No matching video clip found for this frame. Try selecting from the dropdown below.")
    else:
        st.success("✅ No flagged frames yet. Good form so far!")
    
    st.divider()
    
    # Metric clip dropdown
    st.subheader("🎥 Metric Clip Viewer")
    st.caption("Browse all saved clips by metric type")
    
    if snippet_index:
        selected_metric = st.selectbox(
            "Select metric type",
            options=list(snippet_index.keys()),
            format_func=lambda x: x.replace("_", " ").title(),
            key="metric_selector"
        )
        
        clips = snippet_index.get(selected_metric, [])
        st.caption(f"Found {len(clips)} clip(s) for this metric")
        
        for idx, clip_path_str in enumerate(clips, 1):
            clip = make_portable_path(clip_path_str)
            with st.container(border=True):
                st.caption(f"Clip {idx}: {clip.name}")
                if clip.exists():
                    st.video(str(clip))
                else:
                    st.warning(f"Clip file not found: {clip.name}")
                    st.caption(f"Expected location: data/snippets/")
    else:
        st.info("📭 No video clips available. Run the detector to generate clips for bad frames.")

# ---------------------------------------------------------------------------
# TAB 5: RAW DATA
# ---------------------------------------------------------------------------
with tab5:
    st.subheader("📄 Complete Analytics Data (JSON)")
    st.caption("This is the raw data from match_stats.json")
    st.json(data)

# ============================================================================
# PIPELINE NOTES
# ============================================================================
if notes:
    st.subheader("📝 Pipeline Notes")
    for note in notes:
        render_note(note)

# ============================================================================
# AUTO REFRESH
# ============================================================================
if auto_refresh:
    time.sleep(2)
    st.rerun()