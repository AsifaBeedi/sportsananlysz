from __future__ import annotations

from typing import Any

import numpy as np


class BallSpeedEstimator:
    def __init__(self, meters_per_pixel: float | None = None) -> None:
        self.meters_per_pixel = meters_per_pixel

    def update(
        self,
        ball_tracking: dict[str, Any],
        event_summary: dict[str, Any],
        fps: float,
    ) -> dict[str, Any]:
        history = ball_tracking.get("history", [])
        speed_series = build_speed_series(history, fps, self.meters_per_pixel)

        current_speed = speed_series[-1] if speed_series else None
        measured_speeds = [item["speed_px_per_sec"] for item in speed_series if item["source"] == "measured"]
        avg_recent_speed = round(sum(measured_speeds[-5:]) / len(measured_speeds[-5:]), 2) if measured_speeds else None
        peak_speed = round(max(measured_speeds), 2) if measured_speeds else None

        contact_event = latest_contact_event(event_summary.get("recent_events", []))
        contact_comparison = build_contact_comparison(contact_event, speed_series)

        return {
            "active": bool(speed_series),
            "meters_per_pixel": self.meters_per_pixel,
            "current_speed": current_speed,
            "avg_recent_speed_px_per_sec": avg_recent_speed,
            "peak_speed_px_per_sec": peak_speed,
            "speed_series": speed_series[-10:],
            "contact_comparison": contact_comparison,
        }


def build_speed_series(
    history: list[dict[str, Any]],
    fps: float,
    meters_per_pixel: float | None,
) -> list[dict[str, Any]]:
    if len(history) < 2 or not fps:
        return []

    series: list[dict[str, Any]] = []
    for index in range(1, len(history)):
        previous = history[index - 1]
        current = history[index]
        start_frame = previous["frame_index"]
        end_frame = current["frame_index"]
        frame_delta = max(1, end_frame - start_frame)
        dt = frame_delta / fps

        prev_point = previous["smoothed_center"]
        current_point = current["smoothed_center"]
        distance_px = float(np.sqrt((current_point[0] - prev_point[0]) ** 2 + (current_point[1] - prev_point[1]) ** 2))
        speed_px_per_sec = round(distance_px / dt, 2)

        source = (
            "measured"
            if previous["status"] == "detected" and current["status"] == "detected"
            else "interpolated"
        )
        speed_mps = round(speed_px_per_sec * meters_per_pixel, 3) if meters_per_pixel is not None else None
        speed_kmh = round(speed_mps * 3.6, 2) if speed_mps is not None else None

        series.append(
            {
                "start_frame": start_frame,
                "end_frame": end_frame,
                "timestamp_seconds": round(end_frame / fps, 2),
                "distance_px": round(distance_px, 2),
                "speed_px_per_sec": speed_px_per_sec,
                "speed_m_per_sec": speed_mps,
                "speed_km_per_hr": speed_kmh,
                "source": source,
            }
        )

    return series


def latest_contact_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for event in reversed(events):
        if event.get("event_type") == "contact_candidate":
            return event
    return None


def build_contact_comparison(
    contact_event: dict[str, Any] | None,
    speed_series: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if contact_event is None or not speed_series:
        return None

    contact_frame = contact_event["frame_index"]
    before_segments = [item for item in speed_series if item["end_frame"] <= contact_frame and item["source"] == "measured"]
    after_segments = [item for item in speed_series if item["start_frame"] >= contact_frame and item["source"] == "measured"]

    before_segment = before_segments[-1] if before_segments else None
    after_segment = after_segments[0] if after_segments else None

    if before_segment is None and after_segment is None:
        return None

    before_speed = before_segment["speed_px_per_sec"] if before_segment else None
    after_speed = after_segment["speed_px_per_sec"] if after_segment else None
    speed_delta = round(after_speed - before_speed, 2) if before_speed is not None and after_speed is not None else None

    comparison = {
        "contact_frame": contact_frame,
        "shot_label": contact_event.get("shot_label"),
        "before_speed_px_per_sec": before_speed,
        "after_speed_px_per_sec": after_speed,
        "speed_delta_px_per_sec": speed_delta,
        "before_speed_segment": before_segment,
        "after_speed_segment": after_segment,
    }

    if before_segment and before_segment.get("speed_km_per_hr") is not None:
        comparison["before_speed_km_per_hr"] = before_segment["speed_km_per_hr"]
    else:
        comparison["before_speed_km_per_hr"] = None

    if after_segment and after_segment.get("speed_km_per_hr") is not None:
        comparison["after_speed_km_per_hr"] = after_segment["speed_km_per_hr"]
    else:
        comparison["after_speed_km_per_hr"] = None

    if comparison["before_speed_km_per_hr"] is not None and comparison["after_speed_km_per_hr"] is not None:
        comparison["speed_delta_km_per_hr"] = round(
            comparison["after_speed_km_per_hr"] - comparison["before_speed_km_per_hr"],
            2,
        )
    else:
        comparison["speed_delta_km_per_hr"] = None

    return comparison
