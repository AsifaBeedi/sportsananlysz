from __future__ import annotations

from typing import Any


def generate_recommendations(
    players: list[dict[str, Any]],
    events: dict[str, Any],
    racket: dict[str, Any],
    ball_speed: dict[str, Any],
    sport: str,
) -> dict[str, Any]:
    primary_player_id = events.get("primary_player_id")
    primary_player = next((player for player in players if player["track_id"] == primary_player_id), None)

    session_recommendations: list[dict[str, Any]] = []
    player_recommendations: dict[int, list[dict[str, Any]]] = {}

    if primary_player is not None:
        primary_recommendations = build_primary_player_recommendations(primary_player, events, racket, ball_speed, sport)
        player_recommendations[primary_player["track_id"]] = primary_recommendations
        session_recommendations.extend(primary_recommendations)

    for player in players:
        if player["track_id"] == primary_player_id:
            continue

        posture = (player.get("pose") or {}).get("posture")
        if posture is None:
            continue

        supporting_recommendations = build_secondary_player_recommendations(player)
        if supporting_recommendations:
            player_recommendations[player["track_id"]] = supporting_recommendations

    deduped_session_recommendations = dedupe_recommendations(session_recommendations)
    return {
        "sport_mode": sport,
        "primary_player_id": primary_player_id,
        "session_recommendations": deduped_session_recommendations,
        "player_recommendations": player_recommendations,
        "recommendation_count": len(deduped_session_recommendations),
    }


def build_primary_player_recommendations(
    player: dict[str, Any],
    events: dict[str, Any],
    racket: dict[str, Any],
    ball_speed: dict[str, Any],
    sport: str,
) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    posture = (player.get("pose") or {}).get("posture", {})
    posture_components = posture.get("components", {})
    event_state = player.get("event_state") or {}
    racket_state = player.get("racket") or {}
    speed_comparison = ball_speed.get("contact_comparison")

    posture_score = posture.get("posture_score")
    if posture_score is not None and posture_score < 75:
        recommendations.append(
            recommendation(
                category="posture",
                priority="high",
                title="Add more athletic loading before contact",
                detail="The posture score is below target, mainly due to stiff lower-body mechanics.",
                evidence={
                    "posture_score": posture_score,
                    "avg_knee_deg": posture_components.get("avg_knee_deg"),
                    "avg_hip_deg": posture_components.get("avg_hip_deg"),
                },
            )
        )

    coaching_notes = posture.get("coaching_notes", [])
    if any("knee bend" in note.lower() for note in coaching_notes):
        recommendations.append(
            recommendation(
                category="movement",
                priority="medium",
                title="Use deeper knee bend during preparation",
                detail="The current frame suggests limited knee loading, which reduces explosive setup.",
                evidence={"coaching_notes": coaching_notes},
            )
        )

    if any("upright and stiff" in note.lower() for note in coaching_notes):
        recommendations.append(
            recommendation(
                category="posture",
                priority="medium",
                title="Relax the hips and avoid a rigid upright stance",
                detail="A softer hip set should help transfer force into the shot more efficiently.",
                evidence={"coaching_notes": coaching_notes},
            )
        )

    shot_label = event_state.get("shot_label_candidate")
    swing_direction = racket_state.get("swing_direction")
    if sport == "tennis" and shot_label == "serve_candidate" and swing_direction == "upward":
        recommendations.append(
            recommendation(
                category="technique",
                priority="low",
                title="Serve motion shows a useful upward swing path",
                detail="Keep this upward racket path, then refine contact timing and lower-body drive.",
                evidence={
                    "shot_label_candidate": shot_label,
                    "swing_direction": swing_direction,
                    "racket_path_length_px": racket_state.get("path_length_px"),
                },
            )
        )

    if speed_comparison is not None:
        before_speed = speed_comparison.get("before_speed_px_per_sec")
        after_speed = speed_comparison.get("after_speed_px_per_sec")
        speed_delta = speed_comparison.get("speed_delta_px_per_sec")
        if before_speed is not None and after_speed is not None and speed_delta is not None:
            if speed_delta <= 0:
                recommendations.append(
                    recommendation(
                        category="contact",
                        priority="high",
                        title="Improve contact quality to increase ball speed after impact",
                        detail="The tracked ball speed did not rise after the contact candidate frame.",
                        evidence=speed_comparison,
                    )
                )
            elif speed_delta < 20:
                recommendations.append(
                    recommendation(
                        category="contact",
                        priority="medium",
                        title="Contact timing looks decent but could produce more acceleration",
                        detail="Ball speed increased only modestly across the contact window.",
                        evidence=speed_comparison,
                    )
                )

    ball_proximity = event_state.get("ball_proximity_px")
    if event_state.get("swing_phase") == "active_swing" and ball_proximity is not None and ball_proximity > 70:
        recommendations.append(
            recommendation(
                category="timing",
                priority="medium",
                title="Bring the strike zone closer to the moving ball",
                detail="The ball remains relatively far from the primary swing path in the current frame.",
                evidence={
                    "ball_proximity_px": ball_proximity,
                    "swing_phase": event_state.get("swing_phase"),
                    "shot_label_candidate": shot_label,
                },
            )
        )

    if racket_state.get("path_length_px", 0) < 160 and event_state.get("swing_phase") != "idle":
        recommendations.append(
            recommendation(
                category="swing_path",
                priority="medium",
                title="Lengthen the swing path through the ball",
                detail="The racket proxy path is compact for an active swing window.",
                evidence={
                    "racket_path_length_px": racket_state.get("path_length_px"),
                    "swing_direction": racket_state.get("swing_direction"),
                },
            )
        )

    return dedupe_recommendations(recommendations)


def build_secondary_player_recommendations(player: dict[str, Any]) -> list[dict[str, Any]]:
    posture = (player.get("pose") or {}).get("posture", {})
    score = posture.get("posture_score")
    if score is None or score >= 70:
        return []

    return [
        recommendation(
            category="supporting_player",
            priority="low",
            title="Monitor supporting-player posture consistency",
            detail="A secondary tracked athlete is showing a posture score below the current target.",
            evidence={
                "track_id": player["track_id"],
                "posture_score": score,
                "coaching_notes": posture.get("coaching_notes", []),
            },
        )
    ]


def recommendation(
    *,
    category: str,
    priority: str,
    title: str,
    detail: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "category": category,
        "priority": priority,
        "title": title,
        "detail": detail,
        "evidence": evidence,
    }


def dedupe_recommendations(recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for item in recommendations:
        key = (item["category"], item["title"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
