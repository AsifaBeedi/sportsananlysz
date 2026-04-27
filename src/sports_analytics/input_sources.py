from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2

from .config import ASSETS_DIR, AppConfig


SUPPORTED_SOURCE_TYPES = ("file", "demo", "webcam", "rtsp")
FALLBACK_DEMO_VIDEO = "football.mp4"


@dataclass(frozen=True)
class ResolvedInputSource:
    source_type: str
    open_target: str | int
    source_label: str
    source_video: str
    source_uri: str | None
    metadata: dict[str, Any]

    def open_capture(self) -> cv2.VideoCapture:
        return cv2.VideoCapture(self.open_target)


def supported_source_types() -> tuple[str, ...]:
    return SUPPORTED_SOURCE_TYPES


def resolve_input_source(config: AppConfig) -> ResolvedInputSource:
    source_type = str(config.source_type or "file").strip().lower()
    if source_type not in SUPPORTED_SOURCE_TYPES:
        supported = ", ".join(SUPPORTED_SOURCE_TYPES)
        raise ValueError(f"Unsupported source type '{config.source_type}'. Supported source types: {supported}.")

    if source_type == "file":
        return resolve_file_source(config)
    if source_type == "demo":
        return resolve_demo_source(config)
    if source_type == "webcam":
        return resolve_webcam_source(config)
    return resolve_rtsp_source(config)


def resolve_file_source(config: AppConfig) -> ResolvedInputSource:
    path_value = Path(config.source_uri) if config.source_uri else config.video_path
    path = path_value.expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    else:
        path = path.resolve()

    if not path.exists():
        raise ValueError(f"File source does not exist: {path}")
    if not path.is_file():
        raise ValueError(f"File source is not a file: {path}")

    return ResolvedInputSource(
        source_type="file",
        open_target=str(path),
        source_label=f"File: {path.name}",
        source_video=path.name,
        source_uri=str(path),
        metadata={
            "path": str(path),
            "name": path.name,
        },
    )


def resolve_demo_source(config: AppConfig) -> ResolvedInputSource:
    demo_value = config.source_uri or config.sport_profile.demo_video
    demo_path = Path(demo_value)
    if not demo_path.is_absolute():
        demo_path = (ASSETS_DIR / demo_path).resolve()
    else:
        demo_path = demo_path.resolve()

    if not demo_path.exists():
        raise ValueError(f"Demo source does not exist: {demo_path}")
    if not demo_path.is_file():
        raise ValueError(f"Demo source is not a file: {demo_path}")

    resolved_demo_path = demo_path
    metadata: dict[str, Any] = {
        "path": str(demo_path),
        "name": demo_path.name,
        "requested_demo": demo_path.name,
    }

    if not supports_multi_frame_decode(demo_path):
        fallback_path = (ASSETS_DIR / FALLBACK_DEMO_VIDEO).resolve()
        if fallback_path.exists() and fallback_path.is_file() and supports_multi_frame_decode(fallback_path):
            resolved_demo_path = fallback_path
            metadata.update(
                {
                    "path": str(fallback_path),
                    "name": fallback_path.name,
                    "fallback_from": demo_path.name,
                    "fallback_reason": (
                        "Requested demo asset does not provide a stable multi-frame decode in this environment."
                    ),
                }
            )

    return ResolvedInputSource(
        source_type="demo",
        open_target=str(resolved_demo_path),
        source_label=f"Demo: {resolved_demo_path.name}",
        source_video=resolved_demo_path.name,
        source_uri=str(resolved_demo_path),
        metadata=metadata,
    )


def resolve_webcam_source(config: AppConfig) -> ResolvedInputSource:
    raw_value = (config.source_uri or "0").strip()
    open_target: str | int = raw_value
    metadata: dict[str, Any] = {}

    if raw_value.isdigit():
        camera_index = int(raw_value)
        open_target = camera_index
        metadata["camera_index"] = camera_index
        source_video = f"webcam_{camera_index}"
    else:
        metadata["device"] = raw_value
        source_video = f"webcam_{raw_value}"

    return ResolvedInputSource(
        source_type="webcam",
        open_target=open_target,
        source_label=f"Webcam: {raw_value}",
        source_video=source_video,
        source_uri=raw_value,
        metadata=metadata,
    )


def resolve_rtsp_source(config: AppConfig) -> ResolvedInputSource:
    raw_value = (config.source_uri or "").strip()
    if not raw_value:
        raise ValueError("RTSP source requires --source with an RTSP/IP stream URL.")

    return ResolvedInputSource(
        source_type="rtsp",
        open_target=raw_value,
        source_label="RTSP stream",
        source_video=raw_value,
        source_uri=raw_value,
        metadata={
            "url": raw_value,
        },
    )


def supports_multi_frame_decode(path: Path, *, required_frames: int = 2) -> bool:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        cap.release()
        return False

    decoded_frames = 0
    try:
        while decoded_frames < required_frames:
            ret, _ = cap.read()
            if not ret:
                break
            decoded_frames += 1
    finally:
        cap.release()

    return decoded_frames >= required_frames
