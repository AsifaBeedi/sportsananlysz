from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any


class SessionWriter:
    def __init__(self, primary_path: Path, mirror_paths: tuple[Path, ...] = ()) -> None:
        self.primary_path = primary_path
        self.mirror_paths = mirror_paths

    def write(self, payload: dict[str, Any]) -> None:
        serialized = json.dumps(payload, indent=2)
        self._write_atomic(self.primary_path, serialized)

        for path in self.mirror_paths:
            if path != self.primary_path:
                try:
                    self._write_atomic(path, serialized)
                except PermissionError:
                    # Mirrors are best-effort compatibility writes. The session-local
                    # primary output must succeed; a blocked legacy mirror should not
                    # break the whole pipeline.
                    continue

    @staticmethod
    def _write_atomic(path: Path, serialized: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        last_error: PermissionError | None = None
        temp_path: Path | None = None
        for _ in range(20):
            temp_path = path.with_name(f"{path.name}.{os.getpid()}.{int(time.time() * 1000)}.tmp")
            try:
                temp_path.write_text(serialized, encoding="utf-8")
                temp_path.replace(path)
                return
            except PermissionError as error:
                last_error = error
                if temp_path is not None:
                    try:
                        temp_path.unlink(missing_ok=True)
                    except OSError:
                        pass
                time.sleep(0.1)

        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass

        if last_error is not None:
            raise last_error


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def discover_session_records(sessions_root: Path) -> list[dict[str, Any]]:
    if not sessions_root.exists():
        return []

    records: list[dict[str, Any]] = []
    for stats_path in sessions_root.glob("*/stats.json"):
        payload = read_json(stats_path)
        if payload is None:
            continue

        session_dir = stats_path.parent
        record = {
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
            "preview_frame_path": payload.get("preview_frame_path"),
            "output_video_path": payload.get("output_video_path"),
        }
        records.append(record)

    records.sort(key=session_record_sort_key, reverse=True)
    return records


def session_record_sort_key(record: dict[str, Any]) -> tuple[int, float]:
    for key in ("last_updated_at", "session_started_at"):
        parsed = parse_iso_timestamp(record.get(key))
        if parsed is not None:
            return (1, parsed.timestamp())

    stats_path_value = record.get("stats_path")
    if not stats_path_value:
        return (0, 0.0)

    try:
        return (0, Path(str(stats_path_value)).stat().st_mtime)
    except OSError:
        return (0, 0.0)


def parse_iso_timestamp(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
