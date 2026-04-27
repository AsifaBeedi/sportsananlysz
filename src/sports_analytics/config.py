from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import re

from .profiles import get_sport_profile


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
VIDEOS_DIR = DATA_DIR / "videos"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
SESSIONS_DIR = DATA_DIR / "outputs" / "sessions"
MATCHES_DIR = DATA_DIR / "matches"
ASSETS_DIR = VIDEOS_DIR
MODEL_DIR = PROJECT_ROOT / "models"
DEFAULT_MODEL_PATH = MODEL_DIR / "yolov8n.pt"
DEFAULT_POSE_MODEL_PATH = MODEL_DIR / "yolov8n-pose.pt"
DEFAULT_VIDEO_PATH = VIDEOS_DIR / "tennis.mp4"
DEFAULT_SOURCE_TYPE = "file"
DEFAULT_STATS_PATH = OUTPUTS_DIR / "match_stats.json"
LEGACY_STATS_PATH = PROJECT_ROOT / "match_stats.json"
DEFAULT_PREVIEW_FRAME_PATH = OUTPUTS_DIR / "review_frames" / "latest_annotated_frame.jpg"
DEFAULT_OUTPUT_VIDEO_PATH = OUTPUTS_DIR / "processed_video.mp4"
SESSION_STATS_FILENAME = "stats.json"
SESSION_PREVIEW_FILENAME = "preview.jpg"
SESSION_OUTPUT_VIDEO_FILENAME = "output.mp4"


def normalize_session_token(value: str) -> str:
    lowered = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    collapsed = re.sub(r"-{2,}", "-", lowered)
    return collapsed.strip("-") or "session"


def build_session_id(sport: str, started_at: float | None = None) -> str:
    timestamp = datetime.fromtimestamp(started_at or datetime.now().timestamp()).strftime("%Y%m%d-%H%M%S")
    return f"{normalize_session_token(sport)}-{timestamp}"


@dataclass(frozen=True)
class SessionPaths:
    session_id: str
    session_dir: Path
    stats_path: Path
    preview_frame_path: Path
    output_video_path: Path


@dataclass(frozen=True)
class AppConfig:
    sport: str = "tennis"
    model_path: Path = DEFAULT_MODEL_PATH
    pose_model_path: Path = DEFAULT_POSE_MODEL_PATH
    video_path: Path = DEFAULT_VIDEO_PATH
    source_type: str = DEFAULT_SOURCE_TYPE
    source_uri: str | None = None
    match_id: str | None = None
    camera_id: str | None = None
    camera_label: str | None = None
    camera_role: str | None = None
    stats_path: Path = DEFAULT_STATS_PATH
    preview_frame_path: Path = DEFAULT_PREVIEW_FRAME_PATH
    output_video_path: Path = DEFAULT_OUTPUT_VIDEO_PATH
    session_root_dir: Path = SESSIONS_DIR
    match_root_dir: Path = MATCHES_DIR
    mirror_stats_paths: tuple[Path, ...] = field(default_factory=lambda: (LEGACY_STATS_PATH,))
    detection_confidence: float = 0.6
    pose_detection_confidence: float = 0.4
    keypoint_confidence: float = 0.35
    tracked_classes: tuple[int, ...] = (0, 32)
    max_tracking_distance_px: float = 120.0
    max_track_age_frames: int = 10
    ball_max_tracking_distance_px: float = 180.0
    ball_max_track_gap_frames: int = 8
    ball_smoothing_window: int = 5
    ball_history_size: int = 60
    ball_meters_per_pixel: float | None = None
    stats_write_interval_frames: int = 3
    preview_write_interval_frames: int = 3
    write_output_video: bool = True
    video_writer_codec: str = "auto"
    display_window_name: str = "Sports CCTV Analysis"

    @property
    def sport_profile(self):
        return get_sport_profile(self.sport)

    def build_session_paths(self, session_id: str) -> SessionPaths:
        session_dir = self.session_root_dir / session_id
        return SessionPaths(
            session_id=session_id,
            session_dir=session_dir,
            stats_path=session_dir / SESSION_STATS_FILENAME,
            preview_frame_path=session_dir / SESSION_PREVIEW_FILENAME,
            output_video_path=session_dir / SESSION_OUTPUT_VIDEO_FILENAME,
        )

    @property
    def latest_stats_paths(self) -> tuple[Path, ...]:
        unique_paths: list[Path] = []
        for path in (self.stats_path, *self.mirror_stats_paths):
            if path not in unique_paths:
                unique_paths.append(path)
        return tuple(unique_paths)
