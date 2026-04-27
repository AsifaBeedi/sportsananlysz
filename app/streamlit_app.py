from __future__ import annotations

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from sports_analytics.dashboard_utils import (
    LATEST_SESSION_OPTION,
    build_match_rows,
    build_session_rows,
    current_data_age_seconds,
    get_display_video,
    discover_local_video_files,
    discover_session_records,
    event_table,
    find_all_bad_frames,
    find_all_snippets,
    format_session_label,
    format_value,
    freshness_label,
    get_preview_frame,
    load_stats,
    primary_player,
    preview_from_session_record,
    save_uploaded_video,
    selected_session_record,
    sessions_for_match,
)
from sports_analytics.profiles import capability_label, get_sport_profile, supported_sports
from sports_analytics.run_control import (
    launch_analysis_process,
    load_job_state,
    read_job_log_tail,
    refresh_job_state,
    stop_active_job,
)

# ─── Sport metadata ───────────────────────────────────────────────────────────

_SPORT_META: dict[str, tuple[str, str]] = {
    "tennis":   ("Tennis", "Swing analysis, ball tracking & stroke classification"),
    "badminton": ("Badminton", "Racket movement, shuttle contact & recovery mechanics"),
    "table_tennis": ("Table Tennis", "Paddle strokes, reaction windows & compact posture"),
    "cricket":  ("Cricket", "Bat motion, stroke classification & bowling events"),
    "baseball": ("Baseball", "Pitch windows, swing detection & bat contact"),
    "hockey":   ("Hockey", "Puck tracking, stick motion & possession analysis"),
    "volleyball": ("Volleyball", "Serve, set, spike, block & dig analysis"),
    "basketball": ("Basketball", "Preview lane for dribble, pass, drive & shot-attempt cues"),
}

_SPORT_ICONS = {
    "tennis":   "T",
    "badminton": "BD",
    "table_tennis": "TT",
    "cricket":  "C",
    "baseball": "B",
    "hockey":   "H",
    "volleyball": "V",
    "basketball": "K",
}

_RACKET_SPORTS = {"tennis", "badminton", "table_tennis"}
_PRIMARY_SPORTS = ("tennis", "badminton", "table_tennis")

def _sport_label(sport: str) -> str:
    name, _ = _SPORT_META.get(str(sport).lower(), (sport.title(), ""))
    return name

def _sport_desc(sport: str) -> str:
    _, desc = _SPORT_META.get(str(sport).lower(), ("", ""))
    return desc

def _is_running(job_state) -> bool:
    return job_state is not None and job_state.get("status") == "running"


def _latest_session_id_for_sport(sport: str, session_records: list[dict]) -> str:
    sport = str(sport).lower()
    for record in session_records:
        if str(record.get("sport", "")).lower() == sport:
            return str(record["session_id"])
    return LATEST_SESSION_OPTION


# ─── Theme ────────────────────────────────────────────────────────────────────

def inject_theme() -> None:
    st.markdown("""
    <style>
    /* ── Foundations ── */
    :root {
        --page-bg:      #edf2f7;
        --panel-bg:     rgba(255,255,255,0.95);
        --panel-border: rgba(15,23,42,0.09);
        --text-strong:  #0f2137;
        --text-muted:   #5a7083;
        --accent:       #0d9488;
        --accent-dark:  #0f766e;
        --accent-deep:  #134e4a;
        --sidebar-bg:   #0f1923;
    }

    [data-testid="stAppViewContainer"] {
        background:
            radial-gradient(ellipse at 0%   0%,  rgba(13,148,136,0.12) 0%, transparent 50%),
            radial-gradient(ellipse at 100% 0%,  rgba(245,158,11,0.08) 0%, transparent 40%),
            radial-gradient(ellipse at 50%  100%,rgba(15,23,42,0.04)   0%, transparent 60%),
            linear-gradient(160deg, #f0f7f9 0%, #e8f0f5 100%);
        min-height: 100vh;
    }

    .main .block-container {
        max-width: 1260px;
        padding: 1.2rem 2rem 4rem 2rem;
    }

    /* ── Typography ── */
    .stApp h1,.stApp h2,.stApp h3,.stApp h4,
    .stApp p,.stApp label,.stApp span,.stApp li,
    .stApp [data-testid="stMarkdownContainer"],
    .stApp [data-testid="stMarkdownContainer"] p { color: var(--text-strong); }
    .stApp .stCaption, [data-testid="stCaptionContainer"], small {
        color: var(--text-muted) !important;
    }

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(175deg, #0f1923 0%, #111c28 60%, #0d1820 100%);
        border-right: 1px solid rgba(255,255,255,0.06);
    }
    section[data-testid="stSidebar"] > div { padding-top: 0; }

    /* Force ALL sidebar text white */
    section[data-testid="stSidebar"],
    section[data-testid="stSidebar"] * {
        color: rgba(255,255,255,0.88) !important;
    }

    /* Sidebar selectbox */
    section[data-testid="stSidebar"] .stSelectbox > div > div {
        background: rgba(255,255,255,0.07) !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        border-radius: 10px !important;
        color: rgba(255,255,255,0.9) !important;
    }
    section[data-testid="stSidebar"] .stSelectbox svg { color: rgba(255,255,255,0.6) !important; fill: rgba(255,255,255,0.6) !important; }

    /* Sidebar nav buttons — inactive */
    section[data-testid="stSidebar"] .stButton > button {
        background: rgba(255,255,255,0.05) !important;
        border: 1px solid rgba(255,255,255,0.10) !important;
        border-radius: 12px !important;
        color: rgba(255,255,255,0.72) !important;
        font-size: 0.93rem !important;
        font-weight: 500 !important;
        min-height: 2.6rem !important;
        text-align: left !important;
        box-shadow: none !important;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(255,255,255,0.10) !important;
        color: rgba(255,255,255,0.95) !important;
        border-color: rgba(255,255,255,0.20) !important;
    }
    /* Sidebar nav button — active (primary) */
    section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #0d9488, #0f766e) !important;
        border-color: rgba(13,148,136,0.4) !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 14px rgba(13,148,136,0.35) !important;
    }

    /* Sidebar toggle */
    section[data-testid="stSidebar"] .stToggle span { color: rgba(255,255,255,0.88) !important; }

    /* ── Main buttons ── */
    .stButton > button, .stDownloadButton > button {
        background: linear-gradient(135deg, #1e293b, #334155);
        color: #f8fafc !important;
        border: 1px solid rgba(15,23,42,0.15);
        border-radius: 12px;
        font-weight: 600;
        min-height: 2.8rem;
        box-shadow: 0 4px 16px rgba(15,23,42,0.12);
        transition: all 0.15s;
    }
    .stButton > button:hover { border-color: rgba(13,148,136,0.5); color: #fff !important; }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #0d9488, #0f766e) !important;
        border-color: rgba(13,148,136,0.3) !important;
        box-shadow: 0 6px 20px rgba(13,148,136,0.30) !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #0f9e92, #0f8073) !important;
    }

    /* ── Inputs ── */
    .stRadio [role="radiogroup"] {
        background: rgba(255,255,255,0.75);
        border: 1px solid var(--panel-border);
        border-radius: 16px;
        padding: 0.45rem 0.65rem;
        gap: 0.35rem;
    }
    .stRadio [role="radiogroup"] label {
        background: rgba(255,255,255,0.88);
        border: 1px solid rgba(15,23,42,0.08);
        border-radius: 999px;
        padding: 0.18rem 0.65rem;
        color: var(--text-strong) !important;
        font-size: 0.9rem;
    }
    .stSelectbox > div > div, .stTextInput > div > div > input {
        background: rgba(255,255,255,0.92) !important;
        color: var(--text-strong) !important;
        border: 1px solid var(--panel-border) !important;
        border-radius: 12px !important;
    }
    .stTextInput > label, .stSelectbox label, .stRadio > label,
    .stFileUploader label { color: var(--text-strong) !important; font-weight: 600; }

    /* ── Metric cards ── */
    div[data-testid="stMetric"] {
        background: var(--panel-bg);
        border: 1px solid var(--panel-border);
        border-radius: 20px;
        padding: 1.1rem 1.2rem;
        box-shadow: 0 8px 28px rgba(15,23,42,0.07);
    }
    div[data-testid="stMetricLabel"]  { font-weight: 600; color: var(--text-muted) !important; font-size:0.8rem; letter-spacing:0.04em; text-transform:uppercase; }
    div[data-testid="stMetricValue"]  { color: var(--text-strong) !important; font-size:1.65rem; font-weight:700; }
    div[data-testid="stMetricDelta"]  { color: var(--accent) !important; }

    /* ── Alerts / expanders / dataframes ── */
    [data-testid="stAlert"]     { border-radius: 16px; border: 1px solid rgba(15,23,42,0.07); }
    [data-testid="stExpander"]  { background: rgba(255,255,255,0.80); border: 1px solid var(--panel-border); border-radius: 16px; overflow: hidden; }
    [data-testid="stDataFrame"] { background: rgba(255,255,255,0.80); border-radius: 16px; border: 1px solid var(--panel-border); }
    [data-testid="stTabs"] [role="tab"] { font-weight: 600; font-size: 0.9rem; }

    /* ── Custom components ── */
    .page-header {
        background: linear-gradient(135deg, rgba(13,148,136,0.14) 0%, rgba(15,23,42,0.06) 100%);
        border: 1px solid rgba(13,148,136,0.18);
        border-radius: 20px;
        padding: 1.3rem 1.6rem;
        margin-bottom: 1.4rem;
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    .page-header-icon {
        width: 52px; height: 52px;
        background: linear-gradient(135deg, #0d9488, #134e4a);
        border-radius: 14px;
        display: flex; align-items: center; justify-content: center;
        font-size: 1.5rem; font-weight: 900; color: #fff;
        flex-shrink: 0;
        box-shadow: 0 6px 18px rgba(13,148,136,0.30);
    }
    .page-header-text h2 { margin:0; font-size:1.35rem; font-weight:700; color:var(--text-strong); }
    .page-header-text p  { margin:0; color:var(--text-muted); font-size:0.9rem; margin-top:0.15rem; }
    .status-pill {
        display: inline-flex; align-items: center; gap: 0.4rem;
        border-radius: 999px; padding: 0.3rem 0.9rem;
        font-size: 0.83rem; font-weight: 700;
    }
    .status-pill.running { background:rgba(22,163,74,0.12); color:#15803d; border:1px solid rgba(22,163,74,0.25); }
    .status-pill.idle    { background:rgba(15,23,42,0.07);  color:#526174; border:1px solid rgba(15,23,42,0.12); }
    .status-pill.recent  { background:rgba(217,119,6,0.10); color:#b45309; border:1px solid rgba(217,119,6,0.22); }
    .step-label {
        font-size: 0.72rem; font-weight: 800; letter-spacing: 0.10em;
        text-transform: uppercase; color: var(--accent) !important;
        margin: 1.3rem 0 0.35rem 0;
    }
    .hero-frame { border-radius: 20px; overflow: hidden; box-shadow: 0 20px 56px rgba(15,23,42,0.14); margin-bottom: 1rem; }
    .empty-frame {
        background: rgba(255,255,255,0.6);
        border: 2px dashed rgba(15,23,42,0.13);
        border-radius: 20px; padding: 5rem 2rem;
        text-align: center; color: var(--text-muted);
        margin-bottom: 1rem; font-size: 1.05rem;
    }
    .sidebar-section-label {
        font-size: 0.68rem; font-weight: 800;
        letter-spacing: 0.12em; text-transform: uppercase;
        color: rgba(255,255,255,0.38) !important;
        margin: 0.1rem 0 0.5rem 0.2rem;
    }
    .sidebar-logo {
        padding: 1.4rem 1rem 0.8rem 1rem;
        border-bottom: 1px solid rgba(255,255,255,0.07);
        margin-bottom: 0.5rem;
    }
    .sidebar-logo h2 {
        margin: 0; font-size: 1.2rem; font-weight: 800;
        color: #fff !important; letter-spacing: -0.01em;
    }
    .sidebar-logo p { margin: 0.15rem 0 0 0; font-size: 0.8rem; color: rgba(255,255,255,0.45) !important; }
    </style>
    """, unsafe_allow_html=True)


# ─── Shared helpers ───────────────────────────────────────────────────────────

def play_video(path: Path) -> None:
    if not path or not path.exists():
        st.warning("Video file not found.")
        return
    size_mb = path.stat().st_size / 1_048_576
    # st.video streams from disk — works for large files and all supported codecs
    st.video(str(path))
    st.caption(f"{path.name}  ·  {size_mb:.1f} MB")


def render_page_header(icon: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""<div class="page-header">
              <div class="page-header-icon">{icon}</div>
              <div class="page-header-text"><h2>{title}</h2><p>{subtitle}</p></div>
            </div>""",
        unsafe_allow_html=True,
    )


def render_sport_support_notice(sport: str) -> None:
    sport = str(sport).lower()
    if sport == "volleyball":
        st.info(
            "Volleyball is currently in early sport-specific mode. "
            "Serve, set, spike, block, and dig heuristics are active, but this lane still needs longer clip validation and threshold tuning."
        )
    elif sport == "badminton":
        st.info(
            "Badminton is currently a racket-sport preview lane. "
            "It reuses shared racket, pose, and motion signals while shuttle-specific tracking is refined."
        )
    elif sport == "table_tennis":
        st.info(
            "Table tennis is currently a racket-sport preview lane. "
            "It reuses shared racket, pose, and compact-stroke signals while table-specific logic is refined."
        )
    elif sport == "basketball":
        st.info(
            "Basketball is currently a preview lane. Ball-handler, pass, drive, and shot-attempt cues may appear, "
            "but possession-heavy team reasoning is not ready yet."
        )
    elif sport == "hockey":
        st.info(
            "Hockey remains the most tracking-sensitive lane because puck visibility and clip quality affect event confidence heavily."
        )


def render_support_level_snapshot(
    *,
    capability_level: str,
    advanced_event_status: str,
    object_tracking_mode: str,
) -> None:
    support_label = capability_label(capability_level)
    event_label = capability_label(advanced_event_status)
    tracking_label = capability_label(object_tracking_mode)
    message = (
        f"Support level: {support_label}. "
        f"Event layer: {event_label}. "
        f"Tracking: {tracking_label}."
    )
    if capability_level == "full_demo":
        st.success(message)
    elif capability_level == "baseline_core":
        st.info(message)
    else:
        st.warning(message)


def status_pill_html(label: str, kind: str = "idle") -> str:
    dot = {"running": "&#9679;", "recent": "&#9679;", "idle": "&#9711;"}.get(kind, "&#9711;")
    return f'<span class="status-pill {kind}">{dot} {label}</span>'


def render_rec_card(item: dict) -> None:
    priority = str(item.get("priority", "info")).upper()
    dot = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(priority, "🔵")
    with st.container(border=True):
        col_a, col_b = st.columns([6, 1])
        col_a.markdown(f"**{item.get('title', 'Tip')}**")
        col_b.markdown(dot)
        detail = item.get("detail", "")
        if detail:
            st.write(detail)
        cat = str(item.get("category", "general")).replace("_", " ").title()
        st.caption(f"{cat}  ·  {priority}")
        if item.get("evidence"):
            with st.expander("Why this showed up", expanded=False):
                st.json(item["evidence"])


def _series_values(frame_series: list[dict], key: str) -> list[float]:
    values: list[float] = []
    for sample in frame_series:
        value = sample.get(key)
        if value is None:
            continue
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue
    return values


def build_inference_cards(
    performance_metrics: dict,
    events: dict,
    sport_profile: dict,
    primary_posture: dict,
) -> list[dict]:
    cards: list[dict] = []
    summary = performance_metrics.get("summary", {})
    shot_counts = performance_metrics.get("shot_type_counts", {})
    event_counts = performance_metrics.get("event_type_counts", {})
    frame_series = performance_metrics.get("frame_series", [])
    equipment_name = str(sport_profile.get("equipment_name", "equipment")).title()
    confidence_label = str(events.get("confidence_label", "low")).title()
    confidence_score = events.get("confidence_score")
    dominant_event = summary.get("dominant_event_type") or events.get("dominant_event_type")
    dominant_shot = summary.get("dominant_shot_label") or events.get("dominant_shot_label")
    inference_quality = str(summary.get("inference_quality_label", "low")).title()

    if not frame_series:
        return [
            {
                "category": "analysis",
                "priority": "medium",
                "title": "No session trend data has been saved yet",
                "detail": "Run a slightly longer clip or live session so posture, equipment motion, and event trends can build up.",
                "evidence": {"sample_count": 0},
            }
        ]

    cards.append(
        {
            "category": "confidence",
            "priority": "low" if confidence_label == "High" else "medium",
            "title": f"Inference confidence is currently {confidence_label.lower()}",
            "detail": (
                "The event engine now tracks confidence from ball visibility, action windows, and repeated shot cues."
            ),
            "evidence": {
                "confidence_score": confidence_score,
                "confidence_label": confidence_label.lower(),
                "inference_quality": inference_quality.lower(),
                "dominant_event_type": dominant_event,
                "dominant_shot_label": dominant_shot,
            },
        }
    )

    detected_shots = summary.get("detected_shot_labels", [])
    if detected_shots:
        cards.append(
            {
                "category": "inference",
                "priority": "low",
                "title": "Detected action patterns",
                "detail": "The session is now producing shot-pattern inference instead of only raw tracking.",
                "evidence": {"detected_shot_labels": detected_shots, "shot_type_counts": shot_counts},
            }
        )

    if dominant_event or dominant_shot:
        cards.append(
            {
                "category": "summary",
                "priority": "low",
                "title": "Dominant action summary",
                "detail": (
                    f"Most visible event: {str(dominant_event or 'unknown').replace('_', ' ')}. "
                    f"Most repeated shot label: {str(dominant_shot or 'not established').replace('_', ' ')}."
                ),
                "evidence": {
                    "dominant_event_type": dominant_event,
                    "dominant_shot_label": dominant_shot,
                    "event_type_counts": event_counts,
                    "shot_type_counts": shot_counts,
                },
            }
        )

    if event_counts:
        cards.append(
            {
                "category": "events",
                "priority": "low",
                "title": "Event engine is firing on this session",
                "detail": "Tracked event windows are being saved and counted across the session, which means the inference layer is active.",
                "evidence": {"event_type_counts": event_counts},
            }
        )

    if sport_profile.get("display_name") == "Basketball":
        possession_window_count = events.get("possession_window_count", 0)
        dribble_count_estimate = events.get("dribble_count_estimate", 0)
        shot_release_count = events.get("shot_release_count", 0)
        peak_control_score = summary.get("peak_ball_control_score")
        if possession_window_count or dribble_count_estimate or shot_release_count or peak_control_score is not None:
            cards.append(
                {
                    "category": "ball_handler",
                    "priority": "low",
                    "title": "Ball-handler control windows are being measured",
                    "detail": "The basketball preview now tracks handler continuity, bounce moments, and release cues instead of relying only on one nearest-player guess.",
                    "evidence": {
                        "possession_window_count": possession_window_count,
                        "dribble_count_estimate": dribble_count_estimate,
                        "shot_release_count": shot_release_count,
                        "peak_ball_control_score": peak_control_score,
                    },
                }
            )

    peak_activity = summary.get("peak_activity_score")
    if peak_activity is not None:
        cards.append(
            {
                "category": "movement",
                "priority": "low",
                "title": f"{equipment_name} motion intensity is being measured",
                "detail": "The dashboard is now tracking how active the motion gets instead of only showing one static frame.",
                "evidence": {"peak_activity_score": peak_activity},
            }
        )

    peak_path = max(_series_values(frame_series, "equipment_path_length_px"), default=None)
    if peak_path is not None:
        cards.append(
            {
                "category": "equipment_path",
                "priority": "low" if peak_path >= 120 else "medium",
                "title": f"{equipment_name} path length is now visible as a trend",
                "detail": (
                    "Longer paths usually indicate a fuller extension through the action."
                    if peak_path >= 120
                    else "The tracked path still looks short, so extension through the action can improve."
                ),
                "evidence": {"peak_equipment_path_px": round(peak_path, 2)},
            }
        )

    posture_score = primary_posture.get("posture_score")
    if posture_score is not None:
        cards.append(
            {
                "category": "posture",
                "priority": "low" if posture_score >= 80 else "medium",
                "title": "Primary posture score is available",
                "detail": (
                    "Body-shape inference is being captured properly for the lead athlete."
                    if posture_score >= 80
                    else "Pose inference is active, but the base posture can improve for cleaner mechanics."
                ),
                "evidence": {"primary_posture_score": posture_score, "posture_label": primary_posture.get("posture_label")},
            }
        )

    if not cards:
        cards.append(
            {
                "category": "analysis",
                "priority": "medium",
                "title": "Tracking is active, but the current clip is still a weak inference window",
                "detail": "The model is loading the session correctly, but use a longer or cleaner action clip to get stronger shot and contact inference.",
                "evidence": {"recent_event_count": events.get("recent_event_count", 0)},
            }
        )

    return cards


def render_match_context(data: dict) -> None:
    match_info = data.get("match") or {}
    match_id = match_info.get("match_id")
    camera_label = match_info.get("camera_label") or match_info.get("camera_id")
    camera_role = match_info.get("camera_role")
    if not match_id and not camera_label:
        return

    parts = []
    if match_id:
        parts.append(f"Match: `{match_id}`")
    if camera_label:
        parts.append(f"Camera: `{camera_label}`")
    if camera_role:
        parts.append(f"Role: `{camera_role}`")
    st.caption("  |  ".join(parts))


def render_performance_charts(performance_metrics: dict, sport_profile: dict) -> None:
    frame_series = performance_metrics.get("frame_series", [])
    summary = performance_metrics.get("summary", {})
    event_type_counts = performance_metrics.get("event_type_counts", {})
    shot_type_counts = performance_metrics.get("shot_type_counts", {})
    event_timeline = performance_metrics.get("event_timeline", [])
    equipment_name = str(sport_profile.get("equipment_name", "equipment")).title()

    if not frame_series:
        st.info("Performance charts appear once enough session samples have been saved.")
        return

    top = st.columns(4)
    top[0].metric("Samples", summary.get("sample_count", 0))
    top[1].metric("Peak Activity", _metric_val(summary.get("peak_activity_score"), 1))
    top[2].metric(f"Peak {equipment_name} Speed", _metric_val(summary.get("peak_equipment_speed_px_per_sec"), 1, " px/s"))
    top[3].metric("Inference Quality", str(summary.get("inference_quality_label", "low")).title())

    dominant_event = summary.get("dominant_event_type")
    dominant_shot = summary.get("dominant_shot_label")
    if dominant_event or dominant_shot:
        st.caption(
            "Dominant event: "
            f"{str(dominant_event or 'not established').replace('_', ' ').title()}  |  "
            "Dominant shot label: "
            f"{str(dominant_shot or 'not established').replace('_', ' ').title()}"
        )

    row1 = st.columns(2)
    posture_vals = _series_values(frame_series, "primary_posture_score")
    activity_vals = _series_values(frame_series, "activity_score")
    if posture_vals or activity_vals:
        row1[0].markdown("#### Posture vs Activity")
        chart_data = {}
        if posture_vals:
            chart_data["Posture Score"] = posture_vals
        if activity_vals:
            chart_data["Activity Score"] = activity_vals
        row1[0].line_chart(chart_data, use_container_width=True)
    else:
        row1[0].info("No posture/activity trend available yet.")

    equipment_path_vals = _series_values(frame_series, "equipment_path_length_px")
    equipment_speed_vals = _series_values(frame_series, "equipment_speed_px_per_sec")
    if equipment_path_vals or equipment_speed_vals:
        row1[1].markdown(f"#### {equipment_name} Motion")
        chart_data = {}
        if equipment_path_vals:
            chart_data[f"{equipment_name} Path (px)"] = equipment_path_vals
        if equipment_speed_vals:
            chart_data[f"{equipment_name} Speed (px/s)"] = equipment_speed_vals
        row1[1].line_chart(chart_data, use_container_width=True)
    else:
        row1[1].info(f"No {equipment_name.lower()} motion trend available yet.")

    row2 = st.columns(2)
    ball_speed_vals = _series_values(frame_series, "ball_speed_px_per_sec")
    impact_power_vals = _series_values(frame_series, "impact_power_score")
    if ball_speed_vals or impact_power_vals:
        row2[0].markdown(f"#### {str(sport_profile.get('ball_name', 'Ball')).title()} Speed and Impact")
        chart_data = {}
        if ball_speed_vals:
            chart_data["Ball Speed (px/s)"] = ball_speed_vals
        if impact_power_vals:
            chart_data["Impact Power"] = impact_power_vals
        row2[0].line_chart(chart_data, use_container_width=True)
    else:
        row2[0].info("No confirmed ball-speed trend available yet.")

    proximity_vals = _series_values(frame_series, "ball_proximity_px")
    recommendation_vals = _series_values(frame_series, "recommendation_count")
    if proximity_vals or recommendation_vals:
        row2[1].markdown("#### Contact Window and Coaching Pressure")
        chart_data = {}
        if proximity_vals:
            chart_data["Ball Proximity (px)"] = proximity_vals
        if recommendation_vals:
            chart_data["Recommendation Count"] = recommendation_vals
        row2[1].line_chart(chart_data, use_container_width=True)
    else:
        row2[1].info("No contact-window trend available yet.")

    if event_type_counts:
        st.markdown("#### Event Counts")
        st.bar_chart(event_type_counts, use_container_width=True)
    if shot_type_counts:
        st.markdown("#### Shot Pattern Counts")
        st.bar_chart(shot_type_counts, use_container_width=True)

    if event_timeline:
        st.markdown("#### Event Timeline")
        st.dataframe(event_table(event_timeline), use_container_width=True, hide_index=True)


def _metric_val(value, decimals: int = 1, suffix: str = "", zero_is_empty: bool = False) -> str:
    """Format a metric value. If zero_is_empty=True, treat 0 as not-yet-measured and show '—'."""
    if value is None:
        return "—"
    if zero_is_empty and (value == 0 or value == 0.0):
        return "—"
    try:
        return f"{float(value):.{decimals}f}{suffix}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_time(sec) -> str:
    if sec is None:
        return "--:--"
    sec = int(sec)
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def render_analysis_progress(data: dict, job_state, running: bool) -> None:
    frame_index    = int(data.get("frame_index", 0) or 0)
    timestamp_sec  = float(data.get("timestamp_seconds") or 0)
    runtime_sec    = data.get("runtime_seconds")
    total_frames   = data.get("total_frames")
    duration_sec   = data.get("video_duration_seconds")
    fps            = float(data.get("fps") or 0)
    source_type    = (data.get("source") or {}).get("type", "file")
    is_live_source = source_type in ("webcam", "rtsp")

    # Compute progress ratio (None = indeterminate / live)
    progress_ratio: float | None = None
    if not is_live_source and duration_sec and duration_sec > 0 and timestamp_sec >= 0:
        progress_ratio = min(timestamp_sec / duration_sec, 1.0)
    elif not is_live_source and total_frames and total_frames > 0 and frame_index >= 0:
        progress_ratio = min(frame_index / total_frames, 1.0)

    pct_str   = f"{int(progress_ratio * 100)} %" if progress_ratio is not None else "Live"
    pos_str   = _fmt_time(timestamp_sec)
    total_str = _fmt_time(duration_sec) if duration_sec else None
    time_str  = f"{pos_str} / {total_str}" if total_str else pos_str

    # Estimate remaining time
    eta_str: str | None = None
    if progress_ratio is not None and runtime_sec and progress_ratio > 0.01:
        remaining_sec = runtime_sec * (1.0 - progress_ratio) / progress_ratio
        eta_str = _fmt_time(remaining_sec)

    # Stat row
    stat_cols = st.columns(4)
    stat_cols[0].metric("Video Time",     time_str)
    stat_cols[1].metric("Analysis Time",  _fmt_time(runtime_sec) if runtime_sec else "--:--")
    stat_cols[2].metric("Progress",       pct_str)
    stat_cols[3].metric("ETA",            eta_str if (eta_str and running) else ("Done" if (progress_ratio and progress_ratio >= 0.99) else "—"))

    # Progress bar
    if is_live_source:
        # Continuous pulse for live sources
        pulse = (frame_index % 100) / 100.0 if frame_index else 0.0
        st.progress(pulse, text=f"Live capture  ·  Frame {frame_index:,}  ·  {pos_str} in")
    elif progress_ratio is not None:
        bar_text = (
            f"Frame {frame_index:,} of {total_frames:,}  ·  {pos_str}"
            + (f" / {_fmt_time(duration_sec)}" if duration_sec else "")
            + (f"  ·  {int(progress_ratio * 100)} % complete" if running else "  ·  Completed")
        )
        st.progress(progress_ratio, text=bar_text)
    elif running:
        st.progress(0, text=f"Analyzing  ·  Frame {frame_index:,}  ·  {pos_str} in")


def update_history(data: dict) -> list:
    frame_index = int(data.get("frame_index", 0) or 0)
    session_key = data.get("session_id") or (data.get("sport"), data.get("source_video"))
    if st.session_state.get("_hist_key") != session_key:
        st.session_state["_hist_key"] = session_key
        st.session_state["dashboard_history"] = []
    history = st.session_state.setdefault("dashboard_history", [])
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
    if len(history) > 120:
        del history[:-120]
    return history


# ─── Pages ────────────────────────────────────────────────────────────────────

def render_login_page() -> None:
    col, _ = st.columns([1, 2])
    with col:
        st.markdown("## Sports AI Analytics")
        st.markdown("Sign in to continue.")
        st.divider()
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Sign In", use_container_width=True):
                if username.strip() and password.strip():
                    st.session_state.update({
                        "authenticated": True,
                        "username": username.strip(),
                        "app_page": "Sports",
                    })
                    st.rerun()
                else:
                    st.error("Enter any username and password to continue.")


def render_sport_hub(session_records: list[dict], job_state: dict | None) -> None:
    render_page_header("AI", "Sports Dashboard", "Choose a sport workspace to start analysis and review sessions.")

    cols = st.columns(len(_PRIMARY_SPORTS))
    for col, sport in zip(cols, _PRIMARY_SPORTS):
        profile = get_sport_profile(sport)
        sport_sessions = [r for r in session_records if str(r.get("sport", "")).lower() == sport]
        latest_status = str(sport_sessions[0].get("status", "No sessions")).title() if sport_sessions else "No sessions"
        with col:
            st.markdown(f"### {_SPORT_ICONS.get(sport, 'S')} {profile.display_name}")
            st.caption(_sport_desc(sport))
            st.metric("Saved Sessions", len(sport_sessions))
            st.caption(f"Latest: {latest_status}")
            if st.button(f"Open {profile.display_name}", key=f"open_sport_{sport}", use_container_width=True, type="primary"):
                st.session_state["active_sport"] = sport
                st.session_state["upload_sport"] = sport
                st.session_state["selected_session_id"] = _latest_session_id_for_sport(sport, session_records)
                st.session_state["app_page"] = "Monitor"
                st.rerun()

    st.divider()
    left, right = st.columns([1, 1])
    with left:
        st.markdown("#### Racket Sports Focus")
        st.write("Tennis, badminton, and table tennis each open into their own dashboard workspace with Analyze, Monitor, Results, Health, Clips, and Sessions.")
    with right:
        st.markdown("#### Current Engine")
        st.write("Badminton and table tennis are preview lanes using the shared racket-sport foundation while we add sport-specific tracking and health rules.")
        if _is_running(job_state):
            st.success(f"Analysis running: {str(job_state.get('sport', 'unknown')).title()}")


def render_analyze_page(job_state, session_records: list) -> None:
    render_page_header("&#9654;", "New Analysis", "Pick a sport, choose your video source, then start.")

    running = _is_running(job_state)
    if running:
        sport_running = job_state.get("sport", "unknown").title()
        c1, c2 = st.columns([5, 1])
        c1.success(f"Analysis in progress  ·  **{sport_running}**")
        if c2.button("Stop", use_container_width=True):
            stop_active_job()
            st.rerun()
        st.divider()

    # Step 1 — Sport
    st.markdown('<p class="step-label">Step 1 &nbsp; Choose sport</p>', unsafe_allow_html=True)
    sports = list(supported_sports())
    selected_sport = st.selectbox(
        "Sport",
        options=sports,
        format_func=_sport_label,
        key="upload_sport",
        label_visibility="collapsed",
    )
    desc = _sport_desc(selected_sport)
    if desc:
        st.caption(desc)
    selected_profile = get_sport_profile(selected_sport)
    render_support_level_snapshot(
        capability_level=selected_profile.capability_level,
        advanced_event_status=selected_profile.advanced_event_status,
        object_tracking_mode=selected_profile.object_tracking_mode,
    )

    # Step 2 — Source
    st.markdown('<p class="step-label">Step 2 &nbsp; Choose source</p>', unsafe_allow_html=True)
    _VALID_MODES = ["Upload Video", "Saved Video", "Demo", "Webcam", "Live Stream"]
    if st.session_state.get("launch_source_mode") not in _VALID_MODES:
        st.session_state["launch_source_mode"] = "Upload Video"

    source_mode = st.radio(
        "Source",
        _VALID_MODES,
        horizontal=True,
        key="launch_source_mode",
        label_visibility="collapsed",
    )

    source_type  = "file"
    source_value = None
    can_start    = True

    if source_mode == "Upload Video":
        uploaded = st.file_uploader(
            "Drop your video here",
            type=["mp4", "mov", "avi", "mkv"],
            label_visibility="collapsed",
        )
        if uploaded:
            saved = save_uploaded_video(uploaded)
            st.session_state["uploaded_video_path"] = str(saved)
            st.success(f"Saved: {saved.name}")
        source_value = st.session_state.get("uploaded_video_path")
        if not source_value:
            can_start = False
            st.caption("Upload a video file to continue.")

    elif source_mode == "Saved Video":
        local_files = discover_local_video_files()
        if local_files:
            source_value = st.selectbox(
                "Choose a file",
                options=[str(p) for p in local_files],
                format_func=lambda p: Path(p).name,
                label_visibility="collapsed",
            )
        else:
            st.info("No saved videos found. Upload one above first.")
            can_start = False

    elif source_mode == "Demo":
        source_type = "demo"
        st.info(
            f"Uses the built-in demo clip for **{_sport_label(selected_sport)}**: "
            f"`{Path(selected_profile.demo_video).name}`."
        )

    elif source_mode == "Webcam":
        source_type  = "webcam"
        cam_val      = st.text_input("Camera index", value="0", label_visibility="collapsed",
                                     help="0 = default camera, 1 = second camera, etc.").strip()
        source_value = cam_val or "0"
        st.caption("Use 0 for your default webcam.")

    else:  # Live Stream
        source_type  = "rtsp"
        source_value = st.text_input(
            "Stream URL", placeholder="rtsp://192.168.1.x:554/stream",
            label_visibility="collapsed",
        ).strip()
        if not source_value:
            can_start = False
            st.caption("Paste your RTSP or IP camera URL.")

    # Step 3 — Start
    st.markdown('<p class="step-label">Step 3 &nbsp; Start</p>', unsafe_allow_html=True)
    if st.button(
        "Start Analysis" if not running else "Stop current job first",
        use_container_width=True,
        disabled=(running or not can_start),
        type="primary",
    ):
        launch_analysis_process(source_value, selected_sport, source_type=source_type, cwd=Path.cwd())
        st.session_state["selected_session_id"] = LATEST_SESSION_OPTION
        st.session_state["app_page"] = "Monitor"
        st.rerun()


def render_analyze_page_v2(job_state, session_records: list) -> None:
    active_sport = st.session_state.get("active_sport")
    active_profile = get_sport_profile(active_sport) if active_sport else None
    title = f"New {active_profile.display_name} Analysis" if active_profile else "New Analysis"
    render_page_header("&#9654;", title, "Choose your video source, then start.")

    running = _is_running(job_state)
    if running:
        sport_running = job_state.get("sport", "unknown").title()
        c1, c2 = st.columns([5, 1])
        c1.success(f"Analysis in progress  |  **{sport_running}**")
        if c2.button("Stop", use_container_width=True, key="analyze_v2_stop"):
            stop_active_job()
            st.rerun()
        st.divider()

    st.markdown('<p class="step-label">Step 1 &nbsp; Sport workspace</p>', unsafe_allow_html=True)
    if active_sport:
        selected_sport = active_sport
        st.session_state["upload_sport"] = active_sport
        st.info(f"{_sport_label(selected_sport)} dashboard")
    else:
        sports = list(supported_sports())
        selected_sport = st.selectbox(
            "Sport",
            options=sports,
            format_func=_sport_label,
            key="upload_sport",
            label_visibility="collapsed",
        )
    desc = _sport_desc(selected_sport)
    if desc:
        st.caption(desc)
    selected_profile = get_sport_profile(selected_sport)
    render_support_level_snapshot(
        capability_level=selected_profile.capability_level,
        advanced_event_status=selected_profile.advanced_event_status,
        object_tracking_mode=selected_profile.object_tracking_mode,
    )

    st.markdown('<p class="step-label">Step 2 &nbsp; Choose source</p>', unsafe_allow_html=True)
    valid_modes = ["Upload Video", "Saved Video", "Demo", "Webcam", "Live Stream"]
    if st.session_state.get("launch_source_mode") not in valid_modes:
        st.session_state["launch_source_mode"] = "Upload Video"

    source_mode = st.radio(
        "Source",
        valid_modes,
        horizontal=True,
        key="launch_source_mode",
        label_visibility="collapsed",
    )

    source_type = "file"
    source_value = None
    can_start = True

    if source_mode == "Upload Video":
        uploaded = st.file_uploader(
            "Drop your video here",
            type=["mp4", "mov", "avi", "mkv"],
            label_visibility="collapsed",
            key="analyze_v2_uploader",
        )
        if uploaded:
            saved = save_uploaded_video(uploaded)
            st.session_state["uploaded_video_path"] = str(saved)
            st.success(f"Saved: {saved.name}")
        source_value = st.session_state.get("uploaded_video_path")
        if not source_value:
            can_start = False
            st.caption("Upload a video file to continue.")
    elif source_mode == "Saved Video":
        local_files = discover_local_video_files()
        if local_files:
            source_value = st.selectbox(
                "Choose a file",
                options=[str(p) for p in local_files],
                format_func=lambda p: Path(p).name,
                label_visibility="collapsed",
                key="analyze_v2_saved_file",
            )
        else:
            st.info("No saved videos found. Upload one above first.")
            can_start = False
    elif source_mode == "Demo":
        source_type = "demo"
        st.info(
            f"Uses the built-in demo clip for **{_sport_label(selected_sport)}**: "
            f"`{Path(selected_profile.demo_video).name}`."
        )
    elif source_mode == "Webcam":
        source_type = "webcam"
        cam_val = st.text_input(
            "Camera index",
            value="0",
            label_visibility="collapsed",
            help="0 = default camera, 1 = second camera, etc.",
            key="analyze_v2_cam_index",
        ).strip()
        source_value = cam_val or "0"
        st.caption("Use 0 for your default webcam.")
    else:
        source_type = "rtsp"
        source_value = st.text_input(
            "Stream URL",
            placeholder="rtsp://192.168.1.x:554/stream",
            label_visibility="collapsed",
            key="analyze_v2_stream_url",
        ).strip()
        if not source_value:
            can_start = False
            st.caption("Paste your RTSP or IP camera URL.")

    st.markdown('<p class="step-label">Step 3 &nbsp; Match setup</p>', unsafe_allow_html=True)
    st.caption("Optional: add these fields to review multiple cameras under one match.")
    left_meta, right_meta = st.columns(2)
    st.session_state["match_id_input"] = left_meta.text_input(
        "Match ID",
        value=st.session_state.get("match_id_input", ""),
        placeholder="match-finals-01",
        key="analyze_v2_match_id",
    ).strip()
    st.session_state["camera_id_input"] = right_meta.text_input(
        "Camera ID",
        value=st.session_state.get("camera_id_input", ""),
        placeholder="cam_a",
        key="analyze_v2_camera_id",
    ).strip()
    left_meta_2, right_meta_2 = st.columns(2)
    st.session_state["camera_label_input"] = left_meta_2.text_input(
        "Camera Label",
        value=st.session_state.get("camera_label_input", ""),
        placeholder="Side Camera",
        key="analyze_v2_camera_label",
    ).strip()
    role_options = ["single", "side", "endline", "wide", "overhead", "custom"]
    current_role = st.session_state.get("camera_role_input", "single")
    st.session_state["camera_role_input"] = right_meta_2.selectbox(
        "Camera Role",
        options=role_options,
        index=role_options.index(current_role) if current_role in role_options else 0,
        key="analyze_v2_camera_role",
    )

    st.markdown('<p class="step-label">Step 4 &nbsp; Start</p>', unsafe_allow_html=True)
    if st.button(
        "Start Analysis" if not running else "Stop current job first",
        use_container_width=True,
        disabled=(running or not can_start),
        type="primary",
        key="analyze_v2_start",
    ):
        launch_analysis_process(
            source_value,
            selected_sport,
            source_type=source_type,
            match_id=st.session_state.get("match_id_input") or None,
            camera_id=st.session_state.get("camera_id_input") or None,
            camera_label=st.session_state.get("camera_label_input") or None,
            camera_role=st.session_state.get("camera_role_input") or None,
            cwd=Path.cwd(),
        )
        st.session_state["active_sport"] = selected_sport
        st.session_state["upload_sport"] = selected_sport
        st.session_state["selected_session_id"] = LATEST_SESSION_OPTION
        st.session_state["app_page"] = "Monitor"
        st.rerun()


def render_monitor_page(
    data: dict,
    summary: dict,
    sport_profile: dict,
    job_state,
    preview_path,
    display_video_path,
    display_video_label: str,
    source_info: dict,
    data_freshness: str,
    data_age_seconds,
    history: list,
    all_notes: list,
    performance_metrics: dict,
    auto_refresh: bool,
) -> None:
    running      = _is_running(job_state)
    sport_name   = sport_profile.get("display_name", data.get("sport", "Unknown"))
    source_label = source_info.get("label", data.get("source_video", "unknown"))
    sport_icon   = _SPORT_ICONS.get(str(data.get("sport", "")).lower(), "AI")

    # Page header
    if running:
        subtitle = f"Live analysis running  ·  {sport_name}  ·  {source_label}"
    elif data_freshness in ("Running", "Recent"):
        subtitle = f"Showing last session  ·  {sport_name}"
    else:
        subtitle = "No active session  ·  go to Analyze to start one"
    render_page_header(sport_icon, "Live Monitor", subtitle)
    render_match_context(data)
    render_sport_support_notice(data.get("sport", ""))
    render_support_level_snapshot(
        capability_level=str(sport_profile.get("capability_level", "baseline_limited")),
        advanced_event_status=str(sport_profile.get("advanced_event_status", "planned")),
        object_tracking_mode=str(sport_profile.get("object_tracking_mode", "yolo_sports_ball")),
    )

    # Stop button
    if running:
        _, stop_col = st.columns([6, 1])
        if stop_col.button("Stop Analysis", use_container_width=True):
            stop_active_job()
            st.rerun()

    # Progress bar
    render_analysis_progress(data, job_state, running)

    # Frame
    if preview_path and preview_path.exists():
        st.markdown('<div class="hero-frame">', unsafe_allow_html=True)
        st.image(str(preview_path), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="empty-frame">'
            'No frame yet<br><span style="font-size:0.9rem;opacity:0.6">'
            'Start an analysis to see live output here</span>'
            '</div>',
            unsafe_allow_html=True,
        )

    # Key metrics
    m = st.columns(5)
    m[0].metric("Players",       _metric_val(summary.get("players_detected"),         0))
    m[1].metric("Ball Speed",    _metric_val(summary.get("ball_speed_px_per_sec"),    1, " px/s", zero_is_empty=True))
    m[2].metric("Swings",        _metric_val(summary.get("active_swing_count"),       0))
    m[3].metric("Impact Power",  _metric_val(summary.get("impact_power_score"),       1, "",      zero_is_empty=True))
    m[4].metric("Coaching Tips", _metric_val(summary.get("recommendation_count"),     0))

    # Collapsed extras
    if history or performance_metrics.get("frame_series"):
        with st.expander("Performance Charts", expanded=False):
            c1, c2 = st.columns(2)
            frame_series = performance_metrics.get("frame_series", [])
            speed_vals = _series_values(frame_series, "ball_speed_px_per_sec")
            if speed_vals:
                c1.line_chart({"Ball Speed (px/s)": speed_vals}, use_container_width=True)
            posture_vals = _series_values(frame_series, "primary_posture_score")
            if posture_vals:
                c2.line_chart({"Posture Score": posture_vals}, use_container_width=True)

    if display_video_path and display_video_path.exists():
        with st.expander(display_video_label, expanded=False):
            if display_video_label != "Processed Video":
                st.info("Showing the original source clip because a browser-ready processed video is not available for this session yet.")
            play_video(display_video_path)

    log_tail = read_job_log_tail((job_state or {}).get("log_path"), max_lines=15)
    if log_tail:
        with st.expander("Job Log", expanded=False):
            st.code(log_tail)

    if all_notes:
        with st.expander("Pipeline Notes", expanded=False):
            for note in all_notes:
                low = note.lower()
                if any(w in low for w in ("active", "completed")):
                    st.success(note)
                elif any(w in low for w in ("warning", "risk", "alert")):
                    st.warning(note)
                else:
                    st.info(note)

    if auto_refresh and running:
        time.sleep(int(st.session_state.get("refresh_interval_seconds", 2)))
        st.rerun()


def render_multi_camera_tab(data: dict, session_records: list[dict]) -> None:
    match_info = data.get("match") or {}
    current_match_id = match_info.get("match_id")

    st.markdown("#### Match Groups")
    match_rows = build_match_rows(session_records)
    if match_rows:
        st.dataframe(match_rows, use_container_width=True, hide_index=True)
    else:
        st.info("No grouped multi-camera matches yet. Add a match ID when launching sessions to start grouping cameras.")

    if not current_match_id:
        st.info("This session is not assigned to a match yet. Use the Analyze page and fill in Match Setup to group cameras together.")
        return

    related_sessions = sessions_for_match(session_records, current_match_id)
    if not related_sessions:
        st.info(f"No grouped sessions found for match `{current_match_id}`.")
        return

    st.markdown(f"#### Cameras in `{current_match_id}`")
    st.dataframe(build_session_rows(related_sessions), use_container_width=True, hide_index=True)

    if len(related_sessions) < 2:
        st.caption("Launch at least one more camera into this match to unlock side-by-side review.")
        return

    options = [record["session_id"] for record in related_sessions]
    default_left = data.get("session_id") if data.get("session_id") in options else options[0]
    default_right = next((option for option in options if option != default_left), default_left)
    left_col, right_col = st.columns(2)
    left_session_id = left_col.selectbox(
        "Left Camera",
        options=options,
        index=options.index(default_left),
        format_func=lambda sid: format_session_label(sid, related_sessions),
        key="compare_left_session_id",
    )
    right_session_id = right_col.selectbox(
        "Right Camera",
        options=options,
        index=options.index(default_right),
        format_func=lambda sid: format_session_label(sid, related_sessions),
        key="compare_right_session_id",
    )

    left_record = selected_session_record(left_session_id, related_sessions)
    right_record = selected_session_record(right_session_id, related_sessions)
    compare_cols = st.columns(2)
    for col, record in zip(compare_cols, [left_record, right_record]):
        if record is None:
            continue
        camera_name = record.get("camera_label") or record.get("camera_id") or record.get("session_id")
        col.markdown(f"**{camera_name}**")
        col.caption(
            f"Role: {record.get('camera_role') or 'single'}  |  "
            f"Sport: {str(record.get('sport', 'unknown')).title()}  |  "
            f"Status: {str(record.get('status', 'unknown')).title()}"
        )
        preview_path = preview_from_session_record(record)
        if preview_path is not None:
            col.image(str(preview_path), use_container_width=True)
        else:
            col.info("No preview saved for this camera yet.")

    combined_rows: list[dict[str, object]] = []
    for record in [left_record, right_record]:
        if record is None:
            continue
        session_data = load_stats(selected_session_id=record["session_id"], session_records=session_records)
        camera_name = record.get("camera_label") or record.get("camera_id") or record.get("session_id")
        for event in (session_data.get("events") or {}).get("recent_events", []):
            combined_rows.append(
                {
                    "Camera": camera_name,
                    "Frame": event.get("frame_index"),
                    "Type": event.get("event_type"),
                    "Player": event.get("track_id"),
                    "Shot": event.get("shot_label"),
                    "Timestamp (s)": event.get("timestamp_seconds"),
                }
            )

    if combined_rows:
        combined_rows.sort(key=lambda row: (row.get("Timestamp (s)") or 0, str(row.get("Camera"))))
        st.markdown("#### Combined Event Timeline")
        st.dataframe(combined_rows, use_container_width=True, hide_index=True)


def _health_focus_for_sport(sport: str) -> list[dict[str, str]]:
    return {
        "tennis": [
            {"area": "Shoulder load", "detail": "Watch serve and overhead frames for high arm extension and trunk lean."},
            {"area": "Knee and hip base", "detail": "Review low posture scores during wide stance, split-step, and recovery moments."},
            {"area": "Cardio load", "detail": "Use activity spikes and rally length as an early proxy for intensity management."},
        ],
        "badminton": [
            {"area": "Landing mechanics", "detail": "Review jump and overhead frames for knee bend, trunk control, and balanced recovery."},
            {"area": "Shoulder and wrist load", "detail": "Track repeated overhead actions, especially smashes, clears, and fast defensive lifts."},
            {"area": "Recovery load", "detail": "Use direction-change and activity spikes as an early proxy for court coverage stress."},
        ],
        "table_tennis": [
            {"area": "Back and neck posture", "detail": "Review compact stance frames for excessive trunk lean or head-forward posture."},
            {"area": "Elbow and wrist repetition", "detail": "Track repeated short stroke windows for early overuse cues."},
            {"area": "Reaction load", "detail": "Use dense activity bursts as a proxy for quick exchange and recovery demand."},
        ],
    }.get(
        sport,
        [
            {"area": "Posture", "detail": "Review low posture frames and injury-risk flags from the pose model."},
            {"area": "Movement load", "detail": "Use activity trend and flagged clips as early workload indicators."},
        ],
    )


def render_health_tab(
    data: dict,
    summary: dict,
    sport_profile: dict,
    performance_metrics: dict,
    bad_frames: list,
    pose_summary: dict,
    primary_posture: dict,
) -> None:
    sport = str(data.get("sport", "")).lower()
    posture_score = primary_posture.get("posture_score")
    avg_posture = summary.get("avg_posture_score") or pose_summary.get("avg_posture_score")
    injury_count = summary.get("injury_risk_count", 0) or pose_summary.get("injury_risk_count", 0)
    flags = list(primary_posture.get("injury_risk_flags", []))
    activity_vals = _series_values(performance_metrics.get("frame_series", []), "primary_activity_score")

    st.markdown("#### Health Overview")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Posture", format_value(posture_score, suffix="/100") if posture_score is not None else "Pending")
    c2.metric("Average Posture", format_value(avg_posture, suffix="/100") if avg_posture is not None else "Pending")
    c3.metric("Risk Flags", int(injury_count or 0) + len(flags))
    c4.metric("Review Frames", len(bad_frames))

    left, right = st.columns([1.05, 0.95])
    with left:
        st.markdown("#### Body Mechanics")
        if posture_score is not None:
            st.progress(max(0.0, min(float(posture_score) / 100.0, 1.0)))
            st.caption(f"{posture_score} / 100 | {primary_posture.get('posture_label', 'Posture tracked')}")
        else:
            st.info("Posture tracking will appear here once a player pose is available.")

        components = primary_posture.get("components", {})
        if components:
            rows = [{"Metric": key.replace("_", " ").title(), "Value": value} for key, value in components.items()]
            st.dataframe(rows, use_container_width=True, hide_index=True)

        if activity_vals:
            st.markdown("#### Cardio / Intensity Proxy")
            st.line_chart({"Activity Score": activity_vals}, use_container_width=True)
            st.caption("This is an early workload proxy from movement intensity, not a medical heart-rate estimate.")
        else:
            st.info("Activity trend needs a longer tracked window.")

    with right:
        st.markdown("#### Injury Watch")
        if injury_count or flags:
            if injury_count:
                st.warning(f"{injury_count} injury-risk frame{'s' if injury_count != 1 else ''} detected.")
            for flag in flags:
                st.warning(str(flag).replace("_", " ").title())
        else:
            st.success("No active injury-risk flags in the current frame.")

        st.markdown("#### Sport Health Focus")
        for item in _health_focus_for_sport(sport):
            st.markdown(f"**{item['area']}**")
            st.caption(item["detail"])

        if bad_frames[:3]:
            st.markdown("#### Priority Review")
            for frame in bad_frames[:3]:
                st.caption(f"Frame {frame['frame_index']} | {frame['reason']}")


def render_results_page(
    data: dict,
    summary: dict,
    sport_profile: dict,
    events: dict,
    recommendations: dict,
    ball_speed: dict,
    history: list,
    performance_metrics: dict,
    bad_frames: list,
    snippets: dict,
    display_video_path,
    display_video_label: str,
    session_records: list,
    pose_summary: dict,
    primary_posture: dict,
) -> None:
    sport_name  = sport_profile.get("display_name", data.get("sport", "Unknown"))
    sport_icon  = _SPORT_ICONS.get(str(data.get("sport", "")).lower(), "AI")
    render_page_header(sport_icon, "Results", f"Session analytics for {sport_name}")
    render_match_context(data)
    render_sport_support_notice(data.get("sport", ""))
    render_support_level_snapshot(
        capability_level=str(sport_profile.get("capability_level", "baseline_limited")),
        advanced_event_status=str(sport_profile.get("advanced_event_status", "planned")),
        object_tracking_mode=str(sport_profile.get("object_tracking_mode", "yolo_sports_ball")),
    )

    coaching_tab, performance_tab, health_tab, multi_tab, sessions_tab, clips_tab = st.tabs(
        ["Coaching", "Performance", "Health", "Multi-Camera", "Past Sessions", "Clips"]
    )

    # ── Coaching ──────────────────────────────────────────────────────────────
    with coaching_tab:
        r_col, e_col = st.columns([1, 1])

        with r_col:
            st.markdown("#### Coaching Tips")
            all_recs = list(recommendations.get("session_recommendations", []))
            for items in recommendations.get("player_recommendations", {}).values():
                all_recs.extend(items)
            if not all_recs:
                all_recs = build_inference_cards(performance_metrics, events, sport_profile, primary_posture)
            if all_recs:
                for item in all_recs:
                    render_rec_card(item)
            else:
                st.success("No tips yet - analysis is still building data.")

            inj   = summary.get("injury_risk_count", 0)
            falls = summary.get("fall_alerts", 0)
            flags = primary_posture.get("injury_risk_flags", [])
            if inj or falls or flags:
                st.markdown("#### Risk Flags")
                if inj:
                    st.warning(f"{inj} injury risk flag{'s' if inj > 1 else ''} detected.")
                if falls:
                    st.warning(f"{falls} fall alert{'s' if falls > 1 else ''} detected.")
                for flag in flags:
                    st.warning(flag)

        with e_col:
            st.markdown("#### Inference Summary")
            for item in build_inference_cards(performance_metrics, events, sport_profile, primary_posture)[:3]:
                render_rec_card(item)

            st.markdown("#### Recent Events")
            event_rows = event_table(events.get("recent_events", []))
            if event_rows:
                st.dataframe(event_rows, use_container_width=True, hide_index=True)
            else:
                st.info("Events will appear as the analysis progresses.")

            posture_score = primary_posture.get("posture_score")
            if posture_score is not None:
                st.markdown("#### Posture Score")
                st.progress(max(0.0, min(float(posture_score) / 100.0, 1.0)))
                label = primary_posture.get("posture_label", "")
                st.caption(f"{posture_score} / 100  ·  {label}")

    # ── Performance ───────────────────────────────────────────────────────────
    with performance_tab:
        render_performance_charts(performance_metrics, sport_profile)

    with health_tab:
        render_health_tab(data, summary, sport_profile, performance_metrics, bad_frames, pose_summary, primary_posture)

    # ── Past Sessions ─────────────────────────────────────────────────────────
    with sessions_tab:
        st.markdown("#### Past Sessions")
        if session_records:
            rows = build_session_rows(session_records)
            if rows:
                st.dataframe(rows, use_container_width=True, hide_index=True)
            n = len(session_records)
            st.caption(f"{n} session{'s' if n != 1 else ''} found on disk.")
        else:
            st.info("No saved sessions yet. Run an analysis to see it here.")

    # ── Clips ─────────────────────────────────────────────────────────────────
    with clips_tab:
        if display_video_path and display_video_path.exists():
            st.markdown(f"#### {display_video_label}")
            if display_video_label != "Processed Video":
                st.info("Showing the original source clip because a browser-ready processed video is not available for this session yet.")
            play_video(display_video_path)
            st.divider()

        c1, c2, c3 = st.columns(3)
        c1.metric("Flagged Frames", len(bad_frames))
        c2.metric("Saved Clips",    sum(len(v) for v in snippets.values()))
        c3.metric("Clip Types",     len(snippets))

        if bad_frames:
            st.markdown("#### Flagged Frames")
            COLS = 3
            for i in range(0, len(bad_frames), COLS):
                batch = bad_frames[i:i + COLS]
                cols  = st.columns(COLS)
                for col, frame in zip(cols, batch):
                    if frame["path"].exists():
                        col.image(str(frame["path"]), use_container_width=True)
                        col.caption(f"Frame {frame['frame_index']}  ·  {frame['timestamp']}")
                        col.error(frame["reason"])
        else:
            st.success("No flagged frames — form looks good!")

        if snippets:
            st.divider()
            st.markdown("#### Event Clips")
            key = st.selectbox(
                "Clip type",
                options=list(snippets.keys()),
                format_func=lambda k: k.replace("_", " ").title(),
            )
            for clip_path in snippets.get(key, []):
                st.caption(clip_path.name)
                play_video(clip_path)


# ─── App bootstrap ────────────────────────────────────────────────────────────

def render_results_page_v2(
    data: dict,
    summary: dict,
    sport_profile: dict,
    events: dict,
    recommendations: dict,
    ball_speed: dict,
    history: list,
    performance_metrics: dict,
    bad_frames: list,
    snippets: dict,
    display_video_path,
    display_video_label: str,
    session_records: list,
    pose_summary: dict,
    primary_posture: dict,
) -> None:
    sport_key = str(data.get("sport", "")).lower()
    sport_name = sport_profile.get("display_name", data.get("sport", "Unknown"))
    sport_icon = _SPORT_ICONS.get(sport_key, "AI")
    page_title = f"{sport_name} Dashboard" if sport_key in _RACKET_SPORTS else "Results"
    render_page_header(sport_icon, page_title, f"Session analytics for {sport_name}")
    render_match_context(data)
    render_sport_support_notice(data.get("sport", ""))
    render_support_level_snapshot(
        capability_level=str(sport_profile.get("capability_level", "baseline_limited")),
        advanced_event_status=str(sport_profile.get("advanced_event_status", "planned")),
        object_tracking_mode=str(sport_profile.get("object_tracking_mode", "yolo_sports_ball")),
    )

    coaching_tab, performance_tab, health_tab, multi_tab, sessions_tab, clips_tab = st.tabs(
        ["Coaching", "Performance", "Health", "Multi-Camera", "Past Sessions", "Clips"]
    )

    with coaching_tab:
        r_col, e_col = st.columns([1, 1])

        with r_col:
            st.markdown("#### Coaching Tips")
            all_recs = list(recommendations.get("session_recommendations", []))
            for items in recommendations.get("player_recommendations", {}).values():
                all_recs.extend(items)
            if not all_recs:
                all_recs = build_inference_cards(performance_metrics, events, sport_profile, primary_posture)
            if all_recs:
                for item in all_recs:
                    render_rec_card(item)
            else:
                st.success("No tips yet - analysis is still building data.")

            inj = summary.get("injury_risk_count", 0)
            falls = summary.get("fall_alerts", 0)
            flags = primary_posture.get("injury_risk_flags", [])
            if inj or falls or flags:
                st.markdown("#### Risk Flags")
                if inj:
                    st.warning(f"{inj} injury risk flag{'s' if inj > 1 else ''} detected.")
                if falls:
                    st.warning(f"{falls} fall alert{'s' if falls > 1 else ''} detected.")
                for flag in flags:
                    st.warning(flag)

        with e_col:
            st.markdown("#### Inference Summary")
            for item in build_inference_cards(performance_metrics, events, sport_profile, primary_posture)[:3]:
                render_rec_card(item)

            st.markdown("#### Recent Events")
            event_rows = event_table(events.get("recent_events", []))
            if event_rows:
                st.dataframe(event_rows, use_container_width=True, hide_index=True)
            else:
                st.info("Events will appear as the analysis progresses.")

            posture_score = primary_posture.get("posture_score")
            if posture_score is not None:
                st.markdown("#### Posture Score")
                st.progress(max(0.0, min(float(posture_score) / 100.0, 1.0)))
                label = primary_posture.get("posture_label", "")
                st.caption(f"{posture_score} / 100  |  {label}")

    with performance_tab:
        render_performance_charts(performance_metrics, sport_profile)

    with health_tab:
        render_health_tab(data, summary, sport_profile, performance_metrics, bad_frames, pose_summary, primary_posture)

    with multi_tab:
        render_multi_camera_tab(data, session_records)

    with sessions_tab:
        st.markdown("#### Past Sessions")
        if session_records:
            rows = build_session_rows(session_records)
            if rows:
                st.dataframe(rows, use_container_width=True, hide_index=True)
            n = len(session_records)
            st.caption(f"{n} session{'s' if n != 1 else ''} found on disk.")
        else:
            st.info("No saved sessions yet. Run an analysis to see it here.")

    with clips_tab:
        if display_video_path and display_video_path.exists():
            st.markdown(f"#### {display_video_label}")
            if display_video_label != "Processed Video":
                st.info("Showing the original source clip because a browser-ready processed video is not available for this session yet.")
            play_video(display_video_path)
            st.divider()

        c1, c2, c3 = st.columns(3)
        c1.metric("Flagged Frames", len(bad_frames))
        c2.metric("Saved Clips", sum(len(v) for v in snippets.values()))
        c3.metric("Clip Types", len(snippets))

        if bad_frames:
            st.markdown("#### Flagged Frames")
            cols_per_row = 3
            for i in range(0, len(bad_frames), cols_per_row):
                batch = bad_frames[i:i + cols_per_row]
                cols = st.columns(cols_per_row)
                for col, frame in zip(cols, batch):
                    if frame["path"].exists():
                        col.image(str(frame["path"]), use_container_width=True)
                        col.caption(f"Frame {frame['frame_index']}  |  {frame['timestamp']}")
                        col.error(frame["reason"])
        else:
            st.success("No flagged frames - form looks good!")

        if snippets:
            st.divider()
            st.markdown("#### Event Clips")
            key = st.selectbox(
                "Clip type",
                options=list(snippets.keys()),
                format_func=lambda k: k.replace("_", " ").title(),
            )
            for clip_path in snippets.get(key, []):
                st.caption(clip_path.name)
                play_video(clip_path)


st.set_page_config(page_title="Sports AI", layout="wide", page_icon="S")
inject_theme()

_DEFAULTS: dict = {
    "authenticated": False,
    "username": "",
    "app_page": "Sports",
    "active_sport": None,
    "auto_refresh": True,
    "selected_session_id": LATEST_SESSION_OPTION,
    "upload_sport": "tennis",
    "launch_source_mode": "Upload Video",
    "uploaded_video_path": None,
    "match_id_input": "",
    "camera_id_input": "",
    "camera_label_input": "",
    "camera_role_input": "single",
    "refresh_interval_seconds": 2,
    "dashboard_history": [],
    "_hist_key": None,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

_PAGE_MAP = {"Live": "Monitor", "Upload Video": "Analyze", "Launch": "Analyze", "Dashboard": "Results"}
if st.session_state["app_page"] in _PAGE_MAP:
    st.session_state["app_page"] = _PAGE_MAP[st.session_state["app_page"]]
if st.session_state.get("app_page") in {"Analyze", "Monitor", "Results"} and not st.session_state.get("active_sport"):
    st.session_state["app_page"] = "Sports"

_SRC_MAP = {"upload": "Upload Video", "local file": "Saved Video",
            "demo": "Demo", "webcam": "Webcam", "rtsp": "Live Stream"}
if st.session_state.get("launch_source_mode") in _SRC_MAP:
    st.session_state["launch_source_mode"] = _SRC_MAP[st.session_state["launch_source_mode"]]

if not st.session_state["authenticated"]:
    render_login_page()
    st.stop()

# ─── Data loading ─────────────────────────────────────────────────────────────
session_records = discover_session_records()
active_sport = st.session_state.get("active_sport")
workspace_records = [
    r for r in session_records
    if not active_sport or str(r.get("sport", "")).lower() == str(active_sport).lower()
]
session_options = [LATEST_SESSION_OPTION, *[r["session_id"] for r in workspace_records]]
if st.session_state["selected_session_id"] not in session_options:
    st.session_state["selected_session_id"] = _latest_session_id_for_sport(active_sport, workspace_records) if active_sport else LATEST_SESSION_OPTION

load_session_id = st.session_state.get("selected_session_id")
if load_session_id == LATEST_SESSION_OPTION and active_sport:
    load_session_id = _latest_session_id_for_sport(active_sport, workspace_records)

job_state = refresh_job_state(load_job_state())

data = load_stats(
    selected_session_id=load_session_id,
    session_records=workspace_records if active_sport else session_records,
)
if active_sport and not workspace_records:
    profile = get_sport_profile(active_sport)
    data["sport"] = active_sport
    data["sport_profile"] = {
        "display_name": profile.display_name,
        "equipment_name": profile.equipment_name,
        "ball_name": profile.ball_name,
        "ball_like_object_name": profile.ball_like_object_name,
        "object_tracking_mode": profile.object_tracking_mode,
        "capability_level": profile.capability_level,
        "advanced_event_status": profile.advanced_event_status,
    }

summary         = data.get("summary", {})
sport_profile   = data.get("sport_profile", {})
events          = data.get("events", {})
ball_speed      = data.get("ball_speed", {})
recommendations = data.get("recommendations", {})
performance_metrics = data.get("performance_metrics", {})
players         = data.get("players", [])
notes           = data.get("notes", [])
source_info     = data.get("source", {})
pose_summary    = data.get("pose", {}).get("summary", {})

data_age_seconds  = current_data_age_seconds(data)
data_freshness    = freshness_label(data_age_seconds, str(data.get("status", "unknown")))
bad_frames        = find_all_bad_frames(data)
snippets          = find_all_snippets(data)
preview_path      = get_preview_frame(data)
display_video_path, display_video_label = get_display_video(data)
history           = update_history(data)

primary         = primary_player(players, events.get("primary_player_id"))
primary_posture = ((primary.get("pose") or {}).get("posture", {}) if primary else {})

all_notes = list(notes)
fallback_from = (data.get("source") or {}).get("metadata", {}).get("fallback_from")
if fallback_from:
    all_notes.append(
        f"Demo fallback: requested '{fallback_from}', "
        f"using '{data.get('source_video', 'fallback demo')}' for compatibility."
    )

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    username_display = st.session_state.get("username", "Analyst")
    active_sport = st.session_state.get("active_sport")
    active_profile = get_sport_profile(active_sport) if active_sport else None
    sport_name_cur = active_profile.display_name if active_profile else sport_profile.get("display_name", data.get("sport", "-"))

    # Logo block
    st.markdown(
        f'<div class="sidebar-logo">'
        f'<h2>Sports AI</h2>'
        f'<p>Welcome, {username_display}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Navigation buttons
    st.markdown('<p class="sidebar-section-label">Navigate</p>', unsafe_allow_html=True)
    current_page = st.session_state.get("app_page", "Monitor")
    _nav_items = [("&#8962;", "Sports", "Choose a sport dashboard")]
    if active_sport:
        st.caption(f"Workspace: {sport_name_cur}")
        _nav_items.extend([
            ("&#9654;", "Analyze",  f"Start a new {sport_name_cur} analysis"),
            ("&#128250;", "Monitor", f"Watch the {sport_name_cur} session feed"),
            ("&#128202;", "Results", f"Review {sport_name_cur} coaching and health"),
        ])
    for _html_icon, _page_name, _page_hint in _nav_items:
        _is_active = current_page == _page_name
        if st.button(
            f"{_page_name}",
            use_container_width=True,
            type="primary" if _is_active else "secondary",
            key=f"nav_{_page_name}",
            help=_page_hint,
        ):
            if _page_name == "Sports":
                st.session_state["active_sport"] = None
                st.session_state["selected_session_id"] = LATEST_SESSION_OPTION
            st.session_state["app_page"] = _page_name
            st.rerun()

    st.divider()

    # Session selector
    st.markdown('<p class="sidebar-section-label">Session</p>', unsafe_allow_html=True)
    if active_sport:
        st.selectbox(
            "session",
            options=session_options,
            format_func=lambda sid: "Latest in this sport" if sid == LATEST_SESSION_OPTION else format_session_label(sid, workspace_records),
            key="selected_session_id",
            label_visibility="collapsed",
        )
    else:
        st.caption("Choose a sport to see its sessions.")

    st.divider()

    # Status
    st.markdown('<p class="sidebar-section-label">Status</p>', unsafe_allow_html=True)
    if _is_running(job_state):
        run_sport = job_state.get("sport", "unknown").title()
        st.success(f"Running  ·  {run_sport}")
    else:
        st.markdown(
            f"<span style='color:rgba(255,255,255,0.45);font-size:0.85rem'>"
            f"Idle  ·  Last: {sport_name_cur}</span>",
            unsafe_allow_html=True,
        )

    st.divider()

    # Auto-refresh
    st.markdown('<p class="sidebar-section-label">Auto Refresh</p>', unsafe_allow_html=True)
    auto_refresh = st.toggle(
        "Enabled",
        value=st.session_state.get("auto_refresh", True),
        label_visibility="collapsed",
    )
    st.session_state["auto_refresh"] = auto_refresh
    if auto_refresh:
        ri = st.selectbox(
            "interval",
            options=[1, 2, 5, 10],
            index=[1, 2, 5, 10].index(int(st.session_state.get("refresh_interval_seconds", 2))),
            format_func=lambda v: f"Every {v}s",
            label_visibility="collapsed",
        )
        st.session_state["refresh_interval_seconds"] = ri

    st.divider()
    if st.button("Log Out", use_container_width=True):
        st.session_state["authenticated"] = False
        st.rerun()

# ─── Route ────────────────────────────────────────────────────────────────────
_page = st.session_state.get("app_page", "Monitor")

if _page == "Sports":
    render_sport_hub(session_records, job_state)

elif _page == "Analyze":
    render_analyze_page_v2(job_state, workspace_records)

elif _page == "Monitor":
    render_monitor_page(
        data, summary, sport_profile, job_state,
        preview_path, display_video_path, display_video_label, source_info,
        data_freshness, data_age_seconds, history, all_notes,
        performance_metrics,
        auto_refresh,
    )

else:
    render_results_page_v2(
        data, summary, sport_profile, events, recommendations, ball_speed,
        history, performance_metrics, bad_frames, snippets, display_video_path, display_video_label, workspace_records,
        pose_summary, primary_posture,
    )
