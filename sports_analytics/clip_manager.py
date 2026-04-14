from __future__ import annotations

import time
from collections import deque
from pathlib import Path
from typing import Any

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# How many frames to keep in the look-back buffer (pre-roll before trigger).
# At 30 fps this is 2 seconds of history.
BUFFER_PRE_FRAMES: int = 60

# How many frames to record AFTER a trigger (post-roll).
BUFFER_POST_FRAMES: int = 60

# Minimum gap in frames between two snippets of the SAME metric type.
# Prevents flooding disk when a metric fires on back-to-back frames.
SNIPPET_COOLDOWN_FRAMES: int = 90

# Minimum gap in frames between bad-frame saves for the SAME reason string.
# At 30 fps, 60 frames = 2 seconds between saves per reason.
BAD_FRAME_COOLDOWN_FRAMES: int = 60

# JPEG quality for bad-frame snapshots (0-100).
BAD_FRAME_JPEG_QUALITY: int = 92


# ---------------------------------------------------------------------------
# ClipManager
# ---------------------------------------------------------------------------


class ClipManager:
    """
    Manages two output artefact types:

    1. **Metric Snippets** – short MP4 clips centred around a notable event.
       Each clip contains BUFFER_PRE_FRAMES of look-back footage plus
       BUFFER_POST_FRAMES of forward footage, giving ~4 s at 30 fps.

    2. **Bad Frames** – single JPEG snapshots saved whenever a metric falls
       below an acceptable threshold (e.g. poor posture, injury risk).

    Usage inside the pipeline loop
    --------------------------------
    Call ``update_buffer`` once per frame with the annotated frame.
    Call ``trigger_snippet`` whenever a notable metric fires.
    Call ``check_and_save_bad_frame`` whenever a metric crosses a threshold.
    Call ``release_all`` at the end of the session to flush any open writers.
    """

    def __init__(
        self,
        session_id: str,
        data_dir: str | Path = "data",
        pre_frames: int = BUFFER_PRE_FRAMES,
        post_frames: int = BUFFER_POST_FRAMES,
        cooldown_frames: int = SNIPPET_COOLDOWN_FRAMES,
    ) -> None:
        self.session_id = session_id
        self.data_dir = Path(data_dir)
        self.snippets_dir = self.data_dir / "snippets"
        self.review_frames_dir = self.data_dir / "review_frames"
        self.pre_frames = pre_frames
        self.post_frames = post_frames
        self.cooldown_frames = cooldown_frames

        # Create output directories
        self.snippets_dir.mkdir(parents=True, exist_ok=True)
        self.review_frames_dir.mkdir(parents=True, exist_ok=True)

        # Rolling look-back buffer: stores (frame_index, annotated_frame) tuples
        self._buffer: deque[tuple[int, np.ndarray]] = deque(maxlen=pre_frames)

        # Active video writers: record_key -> state dict
        self._active: dict[str, dict[str, Any]] = {}

        # Cooldown tracker: metric_name -> last triggered frame_index
        self._last_triggered: dict[str, int] = {}

        # Bad-frame cooldown tracker: reason_key -> last saved frame_index
        self._bad_frame_last_saved: dict[str, int] = {}

        # Completed snippet paths: metric_name -> list of file paths
        # We store a list so multiple events of the same type are all kept.
        self.snippet_index: dict[str, list[str]] = {}

        # All saved bad frame records for this session
        self.bad_frames: list[dict[str, str]] = []

    # ------------------------------------------------------------------
    # Public API – called once per frame
    # ------------------------------------------------------------------

    def update_buffer(
        self,
        annotated_frame: np.ndarray,
        frame_index: int,
    ) -> None:
        """
        Must be called once per frame.
        Feeds the frame into the look-back buffer and advances any active
        snippet recordings.
        """
        self._buffer.append((frame_index, annotated_frame))
        self._advance_active_recordings(annotated_frame)

    # ------------------------------------------------------------------
    # Public API – trigger a metric snippet
    # ------------------------------------------------------------------

    def trigger_snippet(
        self,
        metric_name: str,
        frame_index: int,
        fps: float,
        frame_width: int,
        frame_height: int,
    ) -> None:
        """
        Trigger a new video snippet for the given metric.

        A per-metric cooldown prevents flooding disk with clips when a metric
        fires on every frame.  Clips that are already being recorded for this
        metric type are also blocked until they finish + cool down.
        """
        last = self._last_triggered.get(metric_name, -self.cooldown_frames - 1)
        if frame_index - last < self.cooldown_frames:
            return  # Still in cooldown

        # Build a filesystem-safe, unique key and path
        safe_name = metric_name.replace(" ", "_").replace("/", "-")
        timestamp_tag = int(time.time() * 1000)
        record_key = f"{self.session_id}__{safe_name}__{timestamp_tag}"
        clip_path = self.snippets_dir / f"{record_key}.mp4"

        # Prefer H.264 (avc1) for browser-compatible MP4 playback.
        # Fall back to mp4v if the OpenCV build does not support avc1.
        for codec in ("avc1", "mp4v"):
            fourcc = cv2.VideoWriter_fourcc(*codec)
            writer = cv2.VideoWriter(
                str(clip_path),
                fourcc,
                max(fps, 1.0),
                (frame_width, frame_height),
            )
            if writer.isOpened():
                break
        else:
            return  # Could not open any writer – skip silently

        # Flush pre-roll buffer into the clip first
        for _, buffered_frame in self._buffer:
            writer.write(buffered_frame)

        self._active[record_key] = {
            "writer": writer,
            "path": clip_path,
            "metric_name": metric_name,
            "frames_remaining": self.post_frames,
        }
        self._last_triggered[metric_name] = frame_index

    # ------------------------------------------------------------------
    # Public API – save a bad-metric frame
    # ------------------------------------------------------------------

    def check_and_save_bad_frame(
        self,
        annotated_frame: np.ndarray,
        reason: str,
        timestamp_seconds: float,
        frame_index: int,
    ) -> None:
        """
        Save a JPEG snapshot of the current frame when a metric is bad.

        A per-reason cooldown (BAD_FRAME_COOLDOWN_FRAMES) prevents saving
        hundreds of near-identical frames when a metric stays bad for many
        consecutive frames.

        ``reason`` is a short human-readable string that will appear in the
        Review Room tab, e.g. "Low Posture Score (42)" or "Injury Risk: knee".
        """
        # Cooldown check – use a normalised reason key so minor score
        # differences in the string don't bypass the guard.
        reason_key = reason[:40]
        last_saved = self._bad_frame_last_saved.get(reason_key, -BAD_FRAME_COOLDOWN_FRAMES - 1)
        if frame_index - last_saved < BAD_FRAME_COOLDOWN_FRAMES:
            return

        safe_reason = reason.replace(" ", "_").replace("/", "-")[:60]
        filename = f"{self.session_id}__{frame_index:06d}__{safe_reason}.jpg"
        snapshot_path = self.review_frames_dir / filename

        encode_params = [cv2.IMWRITE_JPEG_QUALITY, BAD_FRAME_JPEG_QUALITY]
        success, encoded = cv2.imencode(".jpg", annotated_frame, encode_params)
        if not success:
            return

        snapshot_path.write_bytes(encoded.tobytes())
        self._bad_frame_last_saved[reason_key] = frame_index

        self.bad_frames.append(
            {
                "frame_path": str(snapshot_path),
                "reason": reason,
                "timestamp": f"{timestamp_seconds:.2f}s",
                "frame_index": frame_index,
            }
        )

    # ------------------------------------------------------------------
    # Public API – session teardown
    # ------------------------------------------------------------------

    def release_all(self) -> None:
        """
        Flush and close all open video writers.  Call this at session end
        (in a finally block) to prevent truncated clip files.
        """
        for record_key, state in list(self._active.items()):
            state["writer"].release()
            self._register_completed_snippet(state)
        self._active.clear()

    # ------------------------------------------------------------------
    # Serialisable summary for match_stats.json
    # ------------------------------------------------------------------

    def get_summary(self) -> dict[str, Any]:
        """
        Returns a JSON-serialisable dict ready to be embedded in the
        session payload under the key ``"clip_summary"``.
        """
        return {
            "snippet_index": self.snippet_index,
            "snippet_count": sum(len(v) for v in self.snippet_index.values()),
            "bad_frames": self.bad_frames,
            "bad_frame_count": len(self.bad_frames),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _advance_active_recordings(self, annotated_frame: np.ndarray) -> None:
        """Write the current frame to every active recording and close any
        that have consumed all their post-roll frames."""
        completed: list[str] = []

        for record_key, state in self._active.items():
            state["writer"].write(annotated_frame)
            state["frames_remaining"] -= 1
            if state["frames_remaining"] <= 0:
                state["writer"].release()
                self._register_completed_snippet(state)
                completed.append(record_key)

        for record_key in completed:
            del self._active[record_key]

    def _register_completed_snippet(self, state: dict[str, Any]) -> None:
        """Add a finished clip path to the index keyed by metric name."""
        metric_name: str = state["metric_name"]
        path_str: str = str(state["path"])
        self.snippet_index.setdefault(metric_name, []).append(path_str)
