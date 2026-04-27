from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sports_analytics.config import (
    AppConfig,
    DEFAULT_MODEL_PATH,
    DEFAULT_OUTPUT_VIDEO_PATH,
    DEFAULT_POSE_MODEL_PATH,
    DEFAULT_SOURCE_TYPE,
    DEFAULT_STATS_PATH,
    DEFAULT_VIDEO_PATH,
)
from sports_analytics.input_sources import supported_source_types
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
    parser.add_argument(
        "--source-type",
        choices=supported_source_types(),
        default=DEFAULT_SOURCE_TYPE,
        help="Input source type: file, demo, webcam, or rtsp.",
    )
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Generic source value. For file/demo use a path, for webcam use an index like 0, for rtsp use the stream URL.",
    )
    parser.add_argument(
        "--match-id",
        type=str,
        default=None,
        help="Optional Level 1 multi-camera match group identifier.",
    )
    parser.add_argument(
        "--camera-id",
        type=str,
        default=None,
        help="Optional camera identifier within the match group, for example cam_a or endline_1.",
    )
    parser.add_argument(
        "--camera-label",
        type=str,
        default=None,
        help="Optional camera label to show in the dashboard, for example Side Camera.",
    )
    parser.add_argument(
        "--camera-role",
        type=str,
        default=None,
        help="Optional camera role such as side, endline, wide, or overhead.",
    )
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
    parser.add_argument(
        "--writer-codec",
        choices=("auto", "mp4v", "avc1", "h264", "none"),
        default="auto",
        help="Preferred output video codec. Use 'mp4v' on Windows if H.264/OpenH264 is noisy or unavailable.",
    )
    parser.add_argument(
        "--no-output-video",
        action="store_true",
        help="Skip writing output.mp4. Useful for faster smoke tests and environments with codec issues.",
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
        source_type=args.source_type,
        source_uri=args.source,
        match_id=args.match_id,
        camera_id=args.camera_id,
        camera_label=args.camera_label,
        camera_role=args.camera_role,
        stats_path=args.stats.resolve(),
        output_video_path=args.output_video.resolve(),
        detection_confidence=args.conf,
        pose_detection_confidence=args.pose_conf,
        ball_meters_per_pixel=args.ball_meters_per_pixel,
        write_output_video=not args.no_output_video,
        video_writer_codec=args.writer_codec,
    )
    run_video_session(
        config,
        display=not args.no_display,
        max_frames=args.max_frames,
    )


if __name__ == "__main__":
    main()
