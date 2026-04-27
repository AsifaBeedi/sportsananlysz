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
        session_recommendations.extend(
            build_session_trend_recommendations(primary_player, events, racket, ball_speed, sport)
        )
    else:
        session_recommendations.extend(build_capture_quality_recommendations(events, sport))

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


def build_session_trend_recommendations(
    player: dict[str, Any],
    events: dict[str, Any],
    racket: dict[str, Any],
    ball_speed: dict[str, Any],
    sport: str,
) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    posture = (player.get("pose") or {}).get("posture", {})
    posture_score = posture.get("posture_score")
    recent_events = list(events.get("recent_events", []))
    event_types = {str(event.get("event_type")) for event in recent_events}
    shot_labels = [str(event.get("shot_label")) for event in recent_events if event.get("shot_label")]
    dominant_shot_label = max(set(shot_labels), key=shot_labels.count) if shot_labels else None
    latest_primary_state = racket.get("latest_primary_state") or {}
    current_speed = ball_speed.get("current_speed") or {}
    confidence_label = str(events.get("confidence_label", "low")).lower()
    confidence_score = events.get("confidence_score")

    if posture_score is not None and posture_score >= 82:
        recommendations.append(
            recommendation(
                category="posture",
                priority="low",
                title="Base posture looks stable through the tracked window",
                detail="The tracked athlete is holding a strong base. Keep that posture and build the next gains through timing and path quality.",
                evidence={"posture_score": posture_score},
            )
        )

    if recent_events and events.get("contact_candidate_count", 0) == 0:
        if sport == "cricket":
            recommendations.append(
                recommendation(
                    category="timing",
                    priority="medium",
                    title="Batting windows are visible, but contact is not being confirmed clearly yet",
                    detail="The stroke shape is being tracked, but the contact signal is weak. Keep the batter centered in frame and extend the clip around impact.",
                    evidence={"event_types": sorted(event_types), "shot_labels": shot_labels[-4:]},
                )
            )
        elif sport == "baseball":
            recommendations.append(
                recommendation(
                    category="timing",
                    priority="medium",
                    title="Swing windows are visible, but contact timing still looks uncertain",
                    detail="The hitting motion is being picked up, but the contact candidate signal is weak. A cleaner side-on angle and a slightly longer clip should help.",
                    evidence={"event_types": sorted(event_types), "shot_labels": shot_labels[-4:]},
                )
            )
        elif sport in {"tennis", "badminton", "table_tennis"}:
            recommendations.append(
                recommendation(
                    category="timing",
                    priority="medium",
                    title="Swing motion is being tracked, but contact timing is not strongly confirmed",
                    detail="The stroke window is present, but the ball-contact signal is weak. Keep both athlete and ball clearer in frame through impact.",
                    evidence={"event_types": sorted(event_types), "shot_labels": shot_labels[-4:]},
                )
            )
        elif sport == "hockey":
            recommendations.append(
                recommendation(
                    category="puck_tracking",
                    priority="medium",
                    title="Stick motion is being tracked, but puck interaction is still weak",
                    detail="The shot window is visible, but the puck-contact or possession signal is not strong enough yet. A tighter crop or cleaner puck visibility should help.",
                    evidence={"event_types": sorted(event_types), "shot_labels": shot_labels[-4:]},
                )
            )
        elif sport == "volleyball":
            recommendations.append(
                recommendation(
                    category="timing",
                    priority="medium",
                    title="Volleyball action windows are visible, but ball contact is still weak",
                    detail="The action shape is being tracked, but the contact signal is weak. Keep the ball and the lead player visible above shoulder height for longer.",
                    evidence={"event_types": sorted(event_types), "shot_labels": shot_labels[-4:]},
                )
            )
        elif sport == "basketball":
            recommendations.append(
                recommendation(
                    category="timing",
                    priority="medium",
                    title="Ball-handler windows are visible, but release timing is still early",
                    detail="The model is picking up ball-handler activity, but the pass or shot timing signal is still weak. Keep the ball visible on every frame through the action.",
                    evidence={"event_types": sorted(event_types), "shot_labels": shot_labels[-4:]},
                )
            )

    if dominant_shot_label is not None:
        title_map = {
            "off_drive_candidate": "Off-drive pattern is showing up consistently",
            "pull_side_candidate": "Pull-side pattern is showing up consistently",
            "level_swing_candidate": "Level swing shape is showing up consistently",
            "wrist_shot_candidate": "Wrist-shot shape is showing up consistently",
            "slap_shot_candidate": "Slap-shot motion is showing up consistently",
            "serve_candidate": "Serve-like overhead pattern is showing up consistently",
            "set_candidate": "Set-like hand shape is showing up consistently",
            "spike_candidate": "Spike-like attack pattern is showing up consistently",
            "block_candidate": "Block-like overhead pattern is showing up consistently",
            "dig_candidate": "Dig-like recovery pattern is showing up consistently",
            "dribble_candidate": "Dribble rhythm is showing up consistently",
            "pass_candidate": "Pass-like release shape is showing up consistently",
            "drive_candidate": "Drive-like attack pattern is showing up consistently",
            "shot_attempt_candidate": "Shot-attempt shape is showing up consistently",
            "rebound_candidate": "Rebound-like recovery timing is showing up consistently",
        }
        detail_map = {
            "off_drive_candidate": "That is a useful batting cue. Keep the bat face controlled and let the front side stay balanced through contact.",
            "pull_side_candidate": "That pattern can create power, but make sure the barrel stays in the zone long enough to avoid rolling over early.",
            "level_swing_candidate": "That is a solid hitting foundation. Keep that flatter path and refine contact timing next.",
            "wrist_shot_candidate": "That release pattern is visible. Keep the puck close to the blade and finish toward the target.",
            "slap_shot_candidate": "The load and release shape is visible. Focus on clean stick flex and a strong target-line follow-through.",
            "serve_candidate": "The overhead serve shape is visible. Keep a clean toss line and reach fully through contact.",
            "set_candidate": "The hand position suggests a set pattern. Focus on staying square and releasing with soft, even hands.",
            "spike_candidate": "The attack shape is visible. Keep your jump timing synced to the ball and reach high before snapping through the hit.",
            "block_candidate": "The block pattern is visible. Keep both hands high and pressed over the plane instead of reaching late.",
            "dig_candidate": "The recovery shape is visible. Keep a lower base and let the platform angle do more of the control work.",
            "dribble_candidate": "The dribble rhythm is showing up. Keep the ball tight to the body and avoid letting it drift too far outside the control pocket.",
            "pass_candidate": "The pass-release shape is visible. Stay balanced on the catch so the release line stays cleaner.",
            "drive_candidate": "The downhill attack pattern is visible. Keep the first step strong and protect the ball through the lane.",
            "shot_attempt_candidate": "The shot-attempt shape is visible. Keep the elbow under the ball and finish high through the release.",
            "rebound_candidate": "The rebound-like recovery is visible. Win the first inside position before reaching for the ball.",
        }
        recommendations.append(
            recommendation(
                category="pattern",
                priority="low",
                title=title_map.get(dominant_shot_label, "A repeatable shot pattern is showing up"),
                detail=detail_map.get(
                    dominant_shot_label,
                    "The same shot pattern is appearing multiple times in the tracked window, which is useful for repeatability work.",
                ),
                evidence={"dominant_shot_label": dominant_shot_label, "shot_labels": shot_labels[-6:]},
            )
        )

    if confidence_label == "high":
        recommendations.append(
            recommendation(
                category="analysis_quality",
                priority="low",
                title="Inference evidence looks stable through this session",
                detail="Ball visibility, action timing, and repeatable event cues are lining up well enough to trust this clip more than a sparse baseline run.",
                evidence={"confidence_label": confidence_label, "confidence_score": confidence_score},
            )
        )
    elif recent_events and confidence_label == "low":
        recommendations.append(
            recommendation(
                category="analysis_quality",
                priority="medium",
                title="Action cues are visible, but the evidence is still partial",
                detail="This session has some event windows, but the supporting ball or contact evidence is still weak. Treat the current inference as directional rather than final.",
                evidence={"confidence_label": confidence_label, "confidence_score": confidence_score},
            )
        )

    if sport == "basketball":
        possession_window_count = int(events.get("possession_window_count", 0) or 0)
        dribble_count_estimate = int(events.get("dribble_count_estimate", 0) or 0)
        shot_release_count = int(events.get("shot_release_count", 0) or 0)
        if possession_window_count > 0 or dribble_count_estimate > 0 or shot_release_count > 0:
            recommendations.append(
                recommendation(
                    category="ball_handler",
                    priority="low",
                    title="Ball-handler continuity is showing up across the clip",
                    detail="The basketball lane is now holding possession windows and bounce or release moments more consistently. Use those windows to review handle control and release timing.",
                    evidence={
                        "possession_window_count": possession_window_count,
                        "dribble_count_estimate": dribble_count_estimate,
                        "shot_release_count": shot_release_count,
                    },
                )
            )

    if latest_primary_state.get("path_length_px") not in (None, 0) and latest_primary_state.get("path_length_px", 0) < 120:
        recommendations.append(
            recommendation(
                category="path_length",
                priority="medium",
                title=f"Increase the {str(latest_primary_state.get('equipment_name', 'equipment')).lower()} path through the action",
                detail="The tracked path is short, which usually means the motion is getting cut off too early. Try to extend through contact and the follow-through.",
                evidence={
                    "equipment_name": latest_primary_state.get("equipment_name"),
                    "path_length_px": latest_primary_state.get("path_length_px"),
                    "swing_direction": latest_primary_state.get("swing_direction"),
                    "stroke_plane": latest_primary_state.get("stroke_plane"),
                },
            )
        )

    if current_speed.get("speed_px_per_sec") is None and not recent_events:
        recommendations.extend(build_capture_quality_recommendations(events, sport))

    return dedupe_recommendations(recommendations)


def build_capture_quality_recommendations(events: dict[str, Any], sport: str) -> list[dict[str, Any]]:
    if events.get("recent_event_count", 0) > 0:
        return []

    detail = {
        "tennis": "Keep the hitter and ball in frame for a little longer around contact so the model can confirm swing and timing together.",
        "badminton": "Keep the athlete, racket, and shuttle path visible through the overhead or net action so the model can confirm timing together.",
        "table_tennis": "Use a clean table-side angle with the player, paddle, and ball visible through short exchanges so reaction timing is easier to confirm.",
        "cricket": "Try a longer batting clip with the striker centered in frame so the model can lock onto bat path and contact more confidently.",
        "baseball": "Use a cleaner side-on batting angle and keep the hitter in frame longer so the swing window is easier to confirm.",
        "hockey": "Use a tighter angle on the puck carrier or shooter so stick motion and puck interaction stay visible longer.",
        "volleyball": "Keep the ball and lead player visible above shoulder height for longer so the model can separate set, spike, and block windows more clearly.",
        "basketball": "Keep the ball visible on every frame during dribbles, passes, and shot releases so the model can preserve frame-wise ball detection.",
    }.get(sport, "Use a longer, cleaner clip with the athlete centered in frame.")

    return [
        recommendation(
            category="capture_quality",
            priority="medium",
            title="The current clip needs a clearer action window for stronger inference",
            detail=detail,
            evidence={"recent_event_count": events.get("recent_event_count", 0), "sport_mode": sport},
        )
    ]


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
    ball_control_score = event_state.get("ball_control_score")
    ball_control_zone = event_state.get("ball_control_zone")
    ball_height_band = event_state.get("ball_height_band")
    swing_direction = racket_state.get("swing_direction")
    if sport in {"tennis", "badminton", "table_tennis"} and shot_label == "serve_candidate" and swing_direction == "upward":
        action_name = {
            "tennis": "Serve",
            "badminton": "Overhead or serve",
            "table_tennis": "Serve",
        }.get(sport, "Serve")
        recommendations.append(
            recommendation(
                category="technique",
                priority="low",
                title=f"{action_name} motion shows a useful upward swing path",
                detail="Keep this upward racket path, then refine contact timing and lower-body drive.",
                evidence={
                    "shot_label_candidate": shot_label,
                    "swing_direction": swing_direction,
                    "racket_path_length_px": racket_state.get("path_length_px"),
                },
            )
        )

    if sport in {"tennis", "badminton"} and shot_label == "overhead_candidate":
        recommendations.append(
            recommendation(
                category="technique",
                priority="low",
                title="Overhead smash position is being detected",
                detail="Drive through the ball with a firm wrist snap at contact. Keep your hitting shoulder up and track the ball early.",
                evidence={
                    "shot_label_candidate": shot_label,
                    "ball_proximity_px": event_state.get("ball_proximity_px"),
                    "activity_score": event_state.get("activity_score"),
                },
            )
        )

    if sport == "cricket" and shot_label == "straight_bat_candidate":
        recommendations.append(
            recommendation(
                category="technique",
                priority="low",
                title="Straight-bat shape is showing up in the current batting window",
                detail="Keep that compact bat path and add cleaner footwork alignment as the next refinement.",
                evidence={
                    "shot_label_candidate": shot_label,
                    "swing_direction": swing_direction,
                    "racket_path_length_px": racket_state.get("path_length_px"),
                },
            )
        )

    if sport == "cricket" and shot_label == "defensive_block_candidate":
        recommendations.append(
            recommendation(
                category="shot_selection",
                priority="low",
                title="Defensive shot posture is being detected",
                detail="That can be useful for control, but look for a more decisive transfer when you want scoring intent.",
                evidence={
                    "shot_label_candidate": shot_label,
                    "ball_proximity_px": event_state.get("ball_proximity_px"),
                },
            )
        )

    if sport == "baseball" and shot_label == "level_swing_candidate":
        recommendations.append(
            recommendation(
                category="technique",
                priority="low",
                title="Level-swing path is showing up in the current hitting window",
                detail="That is a useful baseline swing shape. Keep the barrel path level and clean up contact timing next.",
                evidence={
                    "shot_label_candidate": shot_label,
                    "swing_direction": swing_direction,
                    "racket_path_length_px": racket_state.get("path_length_px"),
                },
            )
        )

    if sport == "baseball" and shot_label == "uppercut_candidate":
        recommendations.append(
            recommendation(
                category="bat_path",
                priority="medium",
                title="The current swing path looks steep under the ball",
                detail="If you want more controlled contact, flatten the barrel path slightly through the hitting zone.",
                evidence={
                    "shot_label_candidate": shot_label,
                    "ball_proximity_px": event_state.get("ball_proximity_px"),
                    "stroke_plane": racket_state.get("stroke_plane"),
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

    if sport == "basketball" and event_state.get("possession_candidate"):
        if ball_control_score is not None and ball_control_score < 34:
            recommendations.append(
                recommendation(
                    category="ball_control",
                    priority="medium",
                    title="Tighten the ball-handler control window",
                    detail="The system sees you as the likely handler, but the control score is still loose. Keep the ball closer to the hip and hands through the move.",
                    evidence={
                        "ball_control_score": ball_control_score,
                        "ball_control_zone": ball_control_zone,
                        "ball_height_band": ball_height_band,
                    },
                )
            )
        elif ball_control_score is not None and ball_control_score >= 55:
            recommendations.append(
                recommendation(
                    category="ball_control",
                    priority="low",
                    title="Ball control looks stable in the current window",
                    detail="The handle is staying in a cleaner control pocket. Use that stable gather to read the next pass or shot earlier.",
                    evidence={
                        "ball_control_score": ball_control_score,
                        "ball_control_zone": ball_control_zone,
                    },
                )
            )

    if sport == "basketball" and event_state.get("release_candidate"):
        recommendations.append(
            recommendation(
                category="shooting",
                priority="low",
                title="Shot-release timing is being picked up",
                detail="The ball is separating upward through the release window. Keep the gather clean and finish all the way through the shooting line.",
                evidence={
                    "shot_label_candidate": shot_label,
                    "ball_control_score": ball_control_score,
                    "ball_height_band": ball_height_band,
                },
            )
        )

    ball_proximity = event_state.get("ball_proximity_px")
    # Only fire the timing reminder when the swing is truly active AND ball is far
    # AND the player is generating significant movement — avoids firing during normal
    # approach steps where proximity is expected to be high.
    if (
        event_state.get("swing_phase") == "active_swing"
        and ball_proximity is not None
        and ball_proximity > 70
        and event_state.get("activity_score", 0) > 15
    ):
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

    # Only fire the path-length note on follow_through (after the swing completes),
    # not throughout the active phase where the path naturally starts at zero.
    if racket_state.get("path_length_px", 0) < 160 and event_state.get("swing_phase") == "follow_through":
        recommendations.append(
            recommendation(
                category="swing_path",
                priority="medium",
                title="Lengthen the swing path through the ball",
                detail="The racket proxy path was compact for this swing window.",
                evidence={
                    "racket_path_length_px": racket_state.get("path_length_px"),
                    "swing_direction": racket_state.get("swing_direction"),
                },
            )
        )

    if sport == "cricket" and racket_state.get("path_length_px", 0) < 140 and event_state.get("swing_phase") == "active_stroke":
        recommendations.append(
            recommendation(
                category="bat_path",
                priority="medium",
                title="Let the bat travel farther through the stroke",
                detail="The current cricket stroke window looks compact, which can reduce control and extension through impact.",
                evidence={
                    "racket_path_length_px": racket_state.get("path_length_px"),
                    "shot_label_candidate": shot_label,
                    "swing_phase": event_state.get("swing_phase"),
                },
            )
        )

    if sport == "baseball" and racket_state.get("path_length_px", 0) < 145 and event_state.get("swing_phase") == "active_swing":
        recommendations.append(
            recommendation(
                category="bat_path",
                priority="medium",
                title="Let the bat stay in the zone longer through contact",
                detail="The current baseball swing window looks compact, which can reduce plate coverage and quality of contact.",
                evidence={
                    "racket_path_length_px": racket_state.get("path_length_px"),
                    "shot_label_candidate": shot_label,
                    "swing_phase": event_state.get("swing_phase"),
                },
            )
        )

    if sport == "hockey" and shot_label == "wrist_shot_candidate":
        recommendations.append(
            recommendation(
                category="technique",
                priority="low",
                title="Wrist shot shape is being detected",
                detail="Keep the puck on the blade through the release and snap the wrists to add velocity off the stick.",
                evidence={
                    "shot_label_candidate": shot_label,
                    "ball_proximity_px": event_state.get("ball_proximity_px"),
                },
            )
        )

    if sport == "hockey" and shot_label == "slap_shot_candidate":
        recommendations.append(
            recommendation(
                category="technique",
                priority="medium",
                title="Slap shot motion is showing up in the current window",
                detail="Load through the stick flex phase and drive the follow-through toward the target.",
                evidence={
                    "shot_label_candidate": shot_label,
                    "activity_score": event_state.get("activity_score"),
                },
            )
        )

    if sport == "hockey" and shot_label == "backhand_candidate":
        recommendations.append(
            recommendation(
                category="technique",
                priority="low",
                title="Backhand play is being detected",
                detail="Roll the top hand through the release to get elevation and aim on backhand attempts.",
                evidence={
                    "shot_label_candidate": shot_label,
                    "ball_proximity_px": event_state.get("ball_proximity_px"),
                },
            )
        )

    if sport == "hockey" and event_state.get("possession_candidate") and event_state.get("swing_phase") == "idle":
        recommendations.append(
            recommendation(
                category="puck_control",
                priority="low",
                title="In possession window — look for a quick decision",
                detail="You appear nearest the puck proxy. Scan for a shooting or passing lane before the window closes.",
                evidence={
                    "possession_candidate": True,
                    "ball_proximity_px": event_state.get("ball_proximity_px"),
                },
            )
        )

    if sport == "hockey" and racket_state.get("path_length_px", 0) < 140 and event_state.get("swing_phase") == "active_shot":
        recommendations.append(
            recommendation(
                category="stick_path",
                priority="medium",
                title="Extend the stick through the shooting motion",
                detail="The current stick path looks compact for an active shot window. A longer extension adds accuracy and power.",
                evidence={
                    "racket_path_length_px": racket_state.get("path_length_px"),
                    "shot_label_candidate": shot_label,
                    "swing_phase": event_state.get("swing_phase"),
                },
            )
        )

    if sport == "volleyball" and shot_label == "serve_candidate":
        recommendations.append(
            recommendation(
                category="technique",
                priority="low",
                title="Serve-like overhead motion is being detected",
                detail="Keep the toss in front of the hitting shoulder and finish with full reach through contact.",
                evidence={
                    "shot_label_candidate": shot_label,
                    "swing_direction": swing_direction,
                    "racket_path_length_px": racket_state.get("path_length_px"),
                },
            )
        )

    if sport == "volleyball" and shot_label == "set_candidate":
        recommendations.append(
            recommendation(
                category="technique",
                priority="low",
                title="Set-like hand position is being detected",
                detail="Stay balanced under the ball and release with even hands so the ball leaves cleanly from the forehead window.",
                evidence={
                    "shot_label_candidate": shot_label,
                    "ball_proximity_px": event_state.get("ball_proximity_px"),
                },
            )
        )

    if sport == "volleyball" and shot_label == "spike_candidate":
        recommendations.append(
            recommendation(
                category="attack",
                priority="medium",
                title="Spike motion is being detected",
                detail="Focus on matching your jump to the ball height and reaching high before snapping through the hit.",
                evidence={
                    "shot_label_candidate": shot_label,
                    "swing_direction": swing_direction,
                    "ball_proximity_px": event_state.get("ball_proximity_px"),
                },
            )
        )

    if sport == "volleyball" and shot_label == "block_candidate":
        recommendations.append(
            recommendation(
                category="block",
                priority="medium",
                title="Block posture is being detected",
                detail="Keep both hands high early and press over the plane instead of reaching late at the ball.",
                evidence={
                    "shot_label_candidate": shot_label,
                    "ball_proximity_px": event_state.get("ball_proximity_px"),
                },
            )
        )

    if sport == "volleyball" and shot_label == "dig_candidate":
        recommendations.append(
            recommendation(
                category="defense",
                priority="medium",
                title="Dig or recovery posture is being detected",
                detail="Sink the hips a little more and let the platform angle control the rebound instead of popping upward too early.",
                evidence={
                    "shot_label_candidate": shot_label,
                    "posture_score": posture_score,
                },
            )
        )

    if sport == "basketball" and shot_label == "dribble_candidate":
        recommendations.append(
            recommendation(
                category="ball_control",
                priority="low",
                title="Dribble control shape is being detected",
                detail="Keep the dribble pocket close to the hip and avoid reaching across the body if you want a cleaner next move.",
                evidence={
                    "shot_label_candidate": shot_label,
                    "ball_proximity_px": event_state.get("ball_proximity_px"),
                },
            )
        )

    if sport == "basketball" and shot_label == "pass_candidate":
        recommendations.append(
            recommendation(
                category="passing",
                priority="low",
                title="Pass-release shape is being detected",
                detail="Square the shoulders before release so the ball line stays cleaner and more repeatable.",
                evidence={
                    "shot_label_candidate": shot_label,
                    "swing_direction": swing_direction,
                },
            )
        )

    if sport == "basketball" and shot_label == "drive_candidate":
        recommendations.append(
            recommendation(
                category="drive",
                priority="medium",
                title="Drive posture is being detected",
                detail="Stay low through the first step and keep the ball protected instead of letting it swing wide from the body.",
                evidence={
                    "shot_label_candidate": shot_label,
                    "activity_score": event_state.get("activity_score"),
                    "ball_proximity_px": event_state.get("ball_proximity_px"),
                },
            )
        )

    if sport == "basketball" and shot_label == "shot_attempt_candidate":
        recommendations.append(
            recommendation(
                category="shooting",
                priority="medium",
                title="Shot-attempt motion is being detected",
                detail="Keep the elbow stacked under the ball and finish fully through the release window.",
                evidence={
                    "shot_label_candidate": shot_label,
                    "ball_proximity_px": event_state.get("ball_proximity_px"),
                    "swing_direction": swing_direction,
                },
            )
        )

    if sport == "basketball" and shot_label == "rebound_candidate":
        recommendations.append(
            recommendation(
                category="rebound",
                priority="medium",
                title="Rebound timing is being detected",
                detail="Attack the ball with two hands and establish body position before reaching high.",
                evidence={
                    "shot_label_candidate": shot_label,
                    "posture_score": posture_score,
                },
            )
        )

    if sport == "basketball" and event_state.get("possession_candidate") and event_state.get("swing_phase") == "idle":
        recommendations.append(
            recommendation(
                category="ball_control",
                priority="low",
                title="Ball-handler window is active",
                detail="The system thinks this player is closest to the ball. Use that frame to review spacing, posture, and next-action options.",
                evidence={
                    "possession_candidate": True,
                    "ball_proximity_px": event_state.get("ball_proximity_px"),
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
