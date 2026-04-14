from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sports_analytics.config import (
    AppConfig,
    DEFAULT_MODEL_PATH,
    DEFAULT_OUTPUT_VIDEO_PATH,
    DEFAULT_POSE_MODEL_PATH,
    DEFAULT_STATS_PATH,
    DEFAULT_VIDEO_PATH,
)
from sports_analytics.pipeline import run_video_session
from sports_analytics.profiles import supported_sports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the sports analytics pipeline.")
    parser.add_argument(
        "--sport",
        choices=supported_sports(),
        default="tennis",
        help="Sport profile to use for the session.",
    )
    parser.add_argument("--video", type=Path, default=DEFAULT_VIDEO_PATH, help="Path to the input video.")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH, help="Path to the YOLO model.")
    parser.add_argument("--pose-model", type=Path, default=DEFAULT_POSE_MODEL_PATH, help="Path to the YOLO pose model.")
    parser.add_argument("--stats", type=Path, default=DEFAULT_STATS_PATH, help="Path to the analytics JSON file.")
    parser.add_argument(
        "--output-video",
        type=Path,
        default=DEFAULT_OUTPUT_VIDEO_PATH,
        help="Path to save the annotated processed video.",
    )
    parser.add_argument("--conf", type=float, default=0.6, help="Detection confidence threshold.")
    parser.add_argument("--pose-conf", type=float, default=0.4, help="Pose detection confidence threshold.")
    parser.add_argument(
        "--ball-meters-per-pixel",
        type=float,
        default=None,
        help="Optional calibration scale for real-world ball speed conversion.",
    )
    parser.add_argument("--max-frames", type=int, default=None, help="Optional frame cap for validation runs.")
    parser.add_argument("--no-display", action="store_true", help="Run without opening the OpenCV preview window.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = AppConfig(
        sport=args.sport,
        model_path=args.model.resolve(),
        pose_model_path=args.pose_model.resolve(),
        video_path=args.video.resolve(),
        stats_path=args.stats.resolve(),
        output_video_path=args.output_video.resolve(),
        detection_confidence=args.conf,
        pose_detection_confidence=args.pose_conf,
        ball_meters_per_pixel=args.ball_meters_per_pixel,
    )
    run_video_session(
        config,
        display=not args.no_display,
        max_frames=args.max_frames,
    )


if __name__ == "__main__":
    main()
