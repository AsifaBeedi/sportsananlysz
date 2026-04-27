from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SportProfile:
    name: str
    display_name: str
    demo_video: str
    equipment_name: str
    ball_name: str
    ball_like_object_name: str
    object_tracking_mode: str
    capability_level: str
    advanced_event_status: str
    notes: tuple[str, ...]


SPORT_PROFILES: dict[str, SportProfile] = {
    "tennis": SportProfile(
        name="tennis",
        display_name="Tennis",
        demo_video="tennis.mp4",
        equipment_name="racket",
        ball_name="tennis ball",
        ball_like_object_name="sports ball",
        object_tracking_mode="yolo_sports_ball",
        capability_level="full_demo",
        advanced_event_status="tennis_specific",
        notes=(
            "Primary demo profile for the current project.",
            "Racket analytics will serve as the tennis equivalent of bat analytics.",
        ),
    ),
    "badminton": SportProfile(
        name="badminton",
        display_name="Badminton",
        demo_video="tennis.mp4",
        equipment_name="racket",
        ball_name="shuttle",
        ball_like_object_name="shuttle or sports ball",
        object_tracking_mode="yolo_sports_ball",
        capability_level="racket_preview",
        advanced_event_status="badminton_preview",
        notes=(
            "Uses the shared racket-sport pipeline while badminton-specific detectors are added.",
            "Best current use is posture, overhead action, recovery movement, and first-pass contact review.",
        ),
    ),
    "table_tennis": SportProfile(
        name="table_tennis",
        display_name="Table Tennis",
        demo_video="tennis.mp4",
        equipment_name="paddle",
        ball_name="table tennis ball",
        ball_like_object_name="small sports ball",
        object_tracking_mode="yolo_sports_ball",
        capability_level="racket_preview",
        advanced_event_status="table_tennis_preview",
        notes=(
            "Uses the shared racket-sport pipeline while table-tennis-specific detectors are added.",
            "Best current use is compact posture, stroke rhythm, reaction windows, and first-pass contact review.",
        ),
    ),
    "cricket": SportProfile(
        name="cricket",
        display_name="Cricket",
        demo_video="sports.mp4",
        equipment_name="bat",
        ball_name="cricket ball",
        ball_like_object_name="sports ball",
        object_tracking_mode="yolo_sports_ball",
        capability_level="baseline_core",
        advanced_event_status="cricket_basic",
        notes=(
            "Uses the shared player and ball pipeline.",
            "Basic bat, stroke, and contact candidate logic is now active.",
            "Cricket-specific event quality is still early and should be treated as a first-pass signal.",
        ),
    ),
    "baseball": SportProfile(
        name="baseball",
        display_name="Baseball",
        demo_video="sports.mp4",
        equipment_name="bat",
        ball_name="baseball",
        ball_like_object_name="sports ball",
        object_tracking_mode="yolo_sports_ball",
        capability_level="baseline_core",
        advanced_event_status="baseball_basic",
        notes=(
            "Uses the shared player and ball pipeline.",
            "Basic pitch-window, swing-window, and bat-contact candidate logic is now active.",
            "Baseball-specific event quality is still early and should be treated as a first-pass signal.",
        ),
    ),
    "hockey": SportProfile(
        name="hockey",
        display_name="Hockey",
        demo_video="hockey.mp4",
        equipment_name="stick",
        ball_name="puck",
        ball_like_object_name="small game object",
        object_tracking_mode="hockey_puck",
        capability_level="baseline_core",
        advanced_event_status="hockey_basic",
        notes=(
            "Basic stick-motion window, puck possession candidate, and shot candidate logic is active.",
            "Puck tracking uses a dedicated hockey detector with circularity filtering and player-proximity scoring.",
            "Use hockey analytics as an early read on stick patterns and possession zones, not as a finished engine yet.",
        ),
    ),
    "volleyball": SportProfile(
        name="volleyball",
        display_name="Volleyball",
        demo_video="volley.mp4",
        equipment_name="hands",
        ball_name="volleyball",
        ball_like_object_name="sports ball",
        object_tracking_mode="yolo_sports_ball",
        capability_level="baseline_core",
        advanced_event_status="volleyball_basic",
        notes=(
            "Uses the shared player, pose, and ball pipeline.",
            "Basic serve, set, spike, block, and dig heuristics are active.",
            "Volleyball-specific event quality is still early and should be treated as a first-pass signal.",
        ),
    ),
    "basketball": SportProfile(
        name="basketball",
        display_name="Basketball",
        demo_video="Screen Recording 2026-04-23 162316.mp4",
        equipment_name="hands",
        ball_name="basketball",
        ball_like_object_name="sports ball",
        object_tracking_mode="yolo_sports_ball",
        capability_level="baseline_limited",
        advanced_event_status="basketball_preview",
        notes=(
            "Basketball is currently an early preview lane rather than a finished sport engine.",
            "The current path focuses on ball visibility, player pose, and first-pass ball-handler heuristics.",
            "Treat drive, pass, dribble, and shot-attempt cues as exploratory signals until possession logic is added.",
        ),
    ),
}


def get_sport_profile(name: str) -> SportProfile:
    normalized_name = name.strip().lower()
    try:
        return SPORT_PROFILES[normalized_name]
    except KeyError as exc:
        supported = ", ".join(sorted(SPORT_PROFILES))
        raise ValueError(f"Unsupported sport '{name}'. Supported sports: {supported}.") from exc


def supported_sports() -> tuple[str, ...]:
    return tuple(sorted(SPORT_PROFILES))


def capability_label(value: str) -> str:
    mapping = {
        "full_demo": "Full Demo",
        "racket_preview": "Racket Preview",
        "baseline_core": "Baseline Core",
        "baseline_limited": "Baseline Limited",
        "tennis_specific": "Tennis-Specific",
        "badminton_preview": "Badminton Preview",
        "table_tennis_preview": "Table Tennis Preview",
        "cricket_basic": "Cricket Basic",
        "baseball_basic": "Baseball Basic",
        "hockey_basic": "Hockey Basic",
        "volleyball_basic": "Volleyball Basic",
        "basketball_preview": "Basketball Preview",
        "planned": "Planned",
        "yolo_sports_ball": "YOLO Sports Ball",
        "motion_fallback": "Motion Fallback",
        "hockey_puck": "Hockey Puck Detector",
    }
    return mapping.get(value, value.replace("_", " ").title())
