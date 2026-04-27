from __future__ import annotations

from typing import Any

import numpy as np


class ImpactPowerEstimator:
    def __init__(self, meters_per_pixel: float | None = None) -> None:
        self.meters_per_pixel = meters_per_pixel

    def update(
        self,
        racket_summary: dict[str, Any],
        ball_speed_summary: dict[str, Any],
        event_summary: dict[str, Any],
        fps: float,
    ) -> dict[str, Any]:
        latest_primary_state = racket_summary.get("latest_primary_state")
        history_samples = latest_primary_state.get("history_samples", []) if latest_primary_state else []
        racket_speed_series = build_racket_speed_series(history_samples, fps, self.meters_per_pixel)
        latest_racket_speed = racket_speed_series[-1] if racket_speed_series else None

        contact_event = latest_contact_event(event_summary.get("recent_events", []))
        contact_power_proxy = build_contact_power_proxy(
            contact_event,
            racket_speed_series,
            ball_speed_summary.get("contact_comparison"),
        )

        return {
            "active": contact_power_proxy is not None,
            "latest_racket_speed": latest_racket_speed,
            "racket_speed_series": racket_speed_series[-10:],
            "contact_power_proxy": contact_power_proxy,
        }


def build_racket_speed_series(
    history_samples: list[dict[str, Any]],
    fps: float,
    meters_per_pixel: float | None,
) -> list[dict[str, Any]]:
    if len(history_samples) < 2 or not fps:
        return []

    series: list[dict[str, Any]] = []
    for index in range(1, len(history_samples)):
        previous = history_samples[index - 1]
        current = history_samples[index]
        start_frame = int(previous["frame_index"])
        end_frame = int(current["frame_index"])
        frame_delta = max(1, end_frame - start_frame)
        dt = frame_delta / fps

        prev_point = previous["tip_point"]
        current_point = current["tip_point"]
        distance_px = float(np.sqrt((current_point[0] - prev_point[0]) ** 2 + (current_point[1] - prev_point[1]) ** 2))
        speed_px_per_sec = round(distance_px / dt, 2)
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
            }
        )

    return series


def latest_contact_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for event in reversed(events):
        if event.get("event_type") in {"contact_candidate", "bat_contact_candidate"}:
            return event
    return None


def build_contact_power_proxy(
    contact_event: dict[str, Any] | None,
    racket_speed_series: list[dict[str, Any]],
    contact_comparison: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if contact_event is None or not racket_speed_series or contact_comparison is None:
        return None

    contact_frame = int(contact_event["frame_index"])
    racket_segment = nearest_racket_segment(racket_speed_series, contact_frame)
    if racket_segment is None:
        return None

    before_speed = contact_comparison.get("before_speed_px_per_sec")
    after_speed = contact_comparison.get("after_speed_px_per_sec")
    speed_delta = contact_comparison.get("speed_delta_px_per_sec")
    if before_speed is None or after_speed is None or speed_delta is None:
        return None

    positive_gain = max(0.0, float(speed_delta))
    proxy_raw = float(racket_segment["speed_px_per_sec"]) * positive_gain
    proxy_score = round(min(100.0, np.sqrt(proxy_raw) * 0.8), 2) if proxy_raw > 0 else 0.0

    if proxy_score >= 70:
        level = "high"
    elif proxy_score >= 35:
        level = "moderate"
    elif proxy_score > 0:
        level = "low"
    else:
        level = "minimal"

    proxy = {
        "contact_frame": contact_frame,
        "shot_label": contact_event.get("shot_label"),
        "racket_speed_px_per_sec": racket_segment["speed_px_per_sec"],
        "ball_before_speed_px_per_sec": before_speed,
        "ball_after_speed_px_per_sec": after_speed,
        "ball_speed_gain_px_per_sec": speed_delta,
        "power_score": proxy_score,
        "power_level": level,
        "method": (
            "Approximate proxy derived from tracked equipment-tip speed and ball-speed gain around the detected contact frame."
        ),
        "limitations": (
            "This is not a true physical power measurement. It depends on contact timing accuracy, tracking quality, "
            "and optional camera calibration."
        ),
        "racket_segment": racket_segment,
    }

    racket_speed_kmh = racket_segment.get("speed_km_per_hr")
    before_speed_kmh = contact_comparison.get("before_speed_km_per_hr")
    after_speed_kmh = contact_comparison.get("after_speed_km_per_hr")
    speed_delta_kmh = contact_comparison.get("speed_delta_km_per_hr")

    proxy["racket_speed_km_per_hr"] = racket_speed_kmh
    proxy["ball_before_speed_km_per_hr"] = before_speed_kmh
    proxy["ball_after_speed_km_per_hr"] = after_speed_kmh
    proxy["ball_speed_gain_km_per_hr"] = speed_delta_kmh
    return proxy


def nearest_racket_segment(
    racket_speed_series: list[dict[str, Any]],
    contact_frame: int,
) -> dict[str, Any] | None:
    before_segments = [item for item in racket_speed_series if item["end_frame"] <= contact_frame]
    after_segments = [item for item in racket_speed_series if item["start_frame"] >= contact_frame]

    if before_segments:
        return before_segments[-1]
    if after_segments:
        return after_segments[0]
    return None
