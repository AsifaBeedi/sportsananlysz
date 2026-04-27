from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

import sys

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from sports_analytics.config import (
    SESSION_OUTPUT_VIDEO_FILENAME,
    SESSION_PREVIEW_FILENAME,
    SESSION_STATS_FILENAME,
)
from sports_analytics.input_sources import supported_source_types
from sports_analytics.profiles import supported_sports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the structure of a saved session payload.")
    parser.add_argument("stats_path", nargs="?", help="Path to a stats.json file to validate.")
    parser.add_argument("--latest", action="store_true", help="Validate the latest saved session instead of a direct path.")
    parser.add_argument("--sport", choices=supported_sports(), default=None, help="Limit --latest lookup to one sport.")
    return parser.parse_args()


def find_latest_stats_path(sport: str | None = None) -> Path | None:
    sessions_dir = PROJECT_ROOT / "data" / "sessions"
    pattern = f"{sport}-*/{SESSION_STATS_FILENAME}" if sport else f"*/{SESSION_STATS_FILENAME}"
    candidates = sorted(sessions_dir.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def load_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_payload(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        payload = load_payload(path)
    except Exception as exc:
        return [f"Failed to read JSON from {path}: {exc}"]

    if not isinstance(payload, dict):
        return ["Payload must be a JSON object."]

    required_top_level = {
        "status": str,
        "session_id": str,
        "session_dir": str,
        "stats_path": str,
        "sport": str,
        "source": dict,
        "sport_profile": dict,
        "source_video": str,
        "preview_frame_path": str,
        "output_video_path": str,
        "summary": dict,
        "baseline": dict,
        "players": list,
        "events": dict,
        "recommendations": (dict, list),
        "notes": list,
    }
    for key, expected_type in required_top_level.items():
        value = payload.get(key)
        if value is None:
            errors.append(f"Missing required top-level key: {key}")
        elif not isinstance(value, expected_type):
            errors.append(f"Key '{key}' has wrong type: expected {expected_type}, got {type(value)}")

    sport = payload.get("sport")
    if isinstance(sport, str) and sport not in supported_sports():
        errors.append(f"Unsupported sport value in payload: {sport}")

    source = payload.get("source")
    if isinstance(source, dict):
        for key in ("type", "label", "metadata"):
            if key not in source:
                errors.append(f"Source payload missing key: {key}")
        source_type = source.get("type")
        if isinstance(source_type, str) and source_type not in supported_source_types():
            errors.append(f"Unsupported source type in payload: {source_type}")

    summary = payload.get("summary")
    if isinstance(summary, dict):
        for key in (
            "players_detected",
            "tracked_player_ids",
            "balls_detected",
            "ball_track_active",
            "players_with_pose",
            "recent_event_count",
            "contact_candidate_count",
            "recommendation_count",
        ):
            if key not in summary:
                errors.append(f"Summary payload missing key: {key}")

    baseline = payload.get("baseline")
    if isinstance(baseline, dict):
        if "modules" not in baseline or not isinstance(baseline.get("modules"), dict):
            errors.append("Baseline payload must contain a 'modules' object.")

    session_dir = Path(str(payload.get("session_dir", "")))
    stats_path = Path(str(payload.get("stats_path", "")))
    preview_frame_path = Path(str(payload.get("preview_frame_path", "")))
    output_video_path = Path(str(payload.get("output_video_path", "")))

    if session_dir.name != str(payload.get("session_id", "")):
        errors.append("Session directory name should match session_id.")
    if stats_path.name != SESSION_STATS_FILENAME:
        errors.append(f"Session stats filename should be {SESSION_STATS_FILENAME}.")
    if preview_frame_path.name != SESSION_PREVIEW_FILENAME:
        errors.append(f"Session preview filename should be {SESSION_PREVIEW_FILENAME}.")
    if output_video_path.name != SESSION_OUTPUT_VIDEO_FILENAME:
        errors.append(f"Session output filename should be {SESSION_OUTPUT_VIDEO_FILENAME}.")
    if stats_path.parent != session_dir:
        errors.append("stats_path should live inside session_dir.")
    if preview_frame_path.parent != session_dir:
        errors.append("preview_frame_path should live inside session_dir.")
    if output_video_path.parent != session_dir:
        errors.append("output_video_path should live inside session_dir.")

    return errors


def main() -> int:
    args = parse_args()
    stats_path: Path | None
    if args.latest:
        stats_path = find_latest_stats_path(args.sport)
        if stats_path is None:
            print("No saved sessions found for validation.")
            return 1
    elif args.stats_path:
        stats_path = Path(args.stats_path).expanduser()
        if not stats_path.is_absolute():
            stats_path = (PROJECT_ROOT / stats_path).resolve()
    else:
        print("Provide a stats path or use --latest.")
        return 1

    if not stats_path.exists():
        print(f"Stats file does not exist: {stats_path}")
        return 1

    errors = validate_payload(stats_path)
    if errors:
        print(f"Payload validation failed for {stats_path}")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Payload validation passed: {stats_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
