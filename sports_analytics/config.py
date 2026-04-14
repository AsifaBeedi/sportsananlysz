from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .profiles import get_sport_profile


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJECT_ROOT / "data" / "models" / "scripts"
DEFAULT_MODEL_PATH = ASSETS_DIR / "yolov8n.pt"
DEFAULT_POSE_MODEL_PATH = ASSETS_DIR / "yolov8n-pose.pt"
DEFAULT_VIDEO_PATH = ASSETS_DIR / "tennis.mp4"
DEFAULT_STATS_PATH = PROJECT_ROOT / "match_stats.json"
LEGACY_STATS_PATH = ASSETS_DIR / "match_stats.json"
DEFAULT_PREVIEW_FRAME_PATH = PROJECT_ROOT / "latest_annotated_frame.jpg"
DEFAULT_OUTPUT_VIDEO_PATH = PROJECT_ROOT / "annotated_match_output.mp4"


@dataclass(frozen=True)
class AppConfig:
    sport: str = "tennis"
    model_path: Path = DEFAULT_MODEL_PATH
    pose_model_path: Path = DEFAULT_POSE_MODEL_PATH
    video_path: Path = DEFAULT_VIDEO_PATH
    stats_path: Path = DEFAULT_STATS_PATH
    preview_frame_path: Path = DEFAULT_PREVIEW_FRAME_PATH
    output_video_path: Path = DEFAULT_OUTPUT_VIDEO_PATH
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
    display_window_name: str = "Sports CCTV Analysis"

    @property
    def sport_profile(self):
        return get_sport_profile(self.sport)
