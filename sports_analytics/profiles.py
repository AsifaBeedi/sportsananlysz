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
    notes: tuple[str, ...]


SPORT_PROFILES: dict[str, SportProfile] = {
    "tennis": SportProfile(
        name="tennis",
        display_name="Tennis",
        demo_video="tennis.mp4",
        equipment_name="racket",
        ball_name="tennis ball",
        ball_like_object_name="sports ball",
        notes=(
            "Primary demo profile for the current project.",
            "Racket analytics will serve as the tennis equivalent of bat analytics.",
        ),
    ),
    "cricket": SportProfile(
        name="cricket",
        display_name="Cricket",
        demo_video="sports.mp4",
        equipment_name="bat",
        ball_name="cricket ball",
        ball_like_object_name="sports ball",
        notes=(
            "Uses the shared player and ball pipeline.",
            "Bat, stroke, and contact logic will be layered on top in later phases.",
        ),
    ),
    "baseball": SportProfile(
        name="baseball",
        display_name="Baseball",
        demo_video="sports.mp4",
        equipment_name="bat",
        ball_name="baseball",
        ball_like_object_name="sports ball",
        notes=(
            "Uses the shared player and ball pipeline.",
            "Pitch, swing, and contact event logic will be added in later phases.",
        ),
    ),
    "hockey": SportProfile(
        name="hockey",
        display_name="Hockey",
        demo_video="hockey.mp4",
        equipment_name="stick",
        ball_name="puck",
        ball_like_object_name="small game object",
        notes=(
            "Player tracking can reuse the shared core.",
            "Puck tracking will likely need a custom path because generic sports-ball detection is weaker here.",
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
