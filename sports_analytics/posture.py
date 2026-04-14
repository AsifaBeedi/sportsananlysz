from __future__ import annotations

from typing import Any


def analyze_posture(angles_deg: dict[str, float | None]) -> dict[str, Any]:
    score = 100
    coaching_notes: list[str] = []
    injury_risk_flags: list[str] = []

    left_elbow = angles_deg.get("left_elbow_deg")
    right_elbow = angles_deg.get("right_elbow_deg")
    left_knee = angles_deg.get("left_knee_deg")
    right_knee = angles_deg.get("right_knee_deg")
    left_hip = angles_deg.get("left_hip_deg")
    right_hip = angles_deg.get("right_hip_deg")
    trunk_lean = angles_deg.get("trunk_lean_deg")

    avg_knee = average_defined(left_knee, right_knee)
    avg_elbow = average_defined(left_elbow, right_elbow)
    avg_hip = average_defined(left_hip, right_hip)
    knee_balance_gap = pair_gap(left_knee, right_knee)
    elbow_balance_gap = pair_gap(left_elbow, right_elbow)

    if trunk_lean is None:
        score -= 8
        coaching_notes.append("Trunk lean is unclear in the current frame.")
    elif trunk_lean > 25:
        score -= 20
        coaching_notes.append("Excessive trunk lean detected.")
        injury_risk_flags.append("excessive_trunk_lean")
    elif trunk_lean > 15:
        score -= 10
        coaching_notes.append("Moderate trunk lean suggests balance drift.")

    if avg_knee is None:
        score -= 8
        coaching_notes.append("Knee loading is not fully visible.")
    elif avg_knee > 170:
        score -= 15
        coaching_notes.append("Limited knee bend reduces athletic loading.")
    elif avg_knee < 105:
        score -= 12
        coaching_notes.append("Very deep knee bend may indicate heavy joint loading.")
        injury_risk_flags.append("deep_knee_load")

    if knee_balance_gap is not None and knee_balance_gap > 18:
        score -= 8
        coaching_notes.append("Lower-body balance looks uneven between sides.")
        injury_risk_flags.append("lower_body_imbalance")

    if avg_elbow is not None and avg_elbow > 175:
        score -= 8
        coaching_notes.append("Arm extension looks close to locked out.")
        injury_risk_flags.append("arm_overextension")
    elif avg_elbow is not None and avg_elbow < 75:
        score -= 8
        coaching_notes.append("Arm position looks overly compressed.")

    if elbow_balance_gap is not None and elbow_balance_gap > 25:
        score -= 6
        coaching_notes.append("Upper-body symmetry looks inconsistent.")

    if avg_hip is not None and avg_hip > 175:
        score -= 8
        coaching_notes.append("Hip posture looks upright and stiff.")
    elif avg_hip is not None and avg_hip < 120:
        score -= 10
        coaching_notes.append("Hip loading looks aggressive and may need monitoring.")
        injury_risk_flags.append("aggressive_hip_load")

    if trunk_lean is not None and avg_knee is not None and trunk_lean < 3 and avg_knee > 170:
        score -= 8
        coaching_notes.append("Posture looks rigid rather than athletically loaded.")

    score = max(0, min(100, score))
    posture_label = score_to_posture_label(score)
    injury_risk_level = risk_level_from_flags(injury_risk_flags)

    if not coaching_notes:
        coaching_notes.append("Posture looks stable in the current frame.")

    return {
        "posture_score": score,
        "posture_label": posture_label,
        "injury_risk_level": injury_risk_level,
        "injury_risk_flags": injury_risk_flags,
        "coaching_notes": coaching_notes,
        "components": {
            "avg_knee_deg": avg_knee,
            "avg_elbow_deg": avg_elbow,
            "avg_hip_deg": avg_hip,
            "knee_balance_gap_deg": knee_balance_gap,
            "elbow_balance_gap_deg": elbow_balance_gap,
            "trunk_lean_deg": trunk_lean,
        },
    }


def average_defined(*values: float | None) -> float | None:
    defined = [value for value in values if value is not None]
    if not defined:
        return None
    return round(sum(defined) / len(defined), 2)


def pair_gap(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return round(abs(left - right), 2)


def score_to_posture_label(score: int) -> str:
    if score >= 85:
        return "strong"
    if score >= 70:
        return "watch"
    return "needs_attention"


def risk_level_from_flags(flags: list[str]) -> str:
    if len(flags) >= 3:
        return "high"
    if len(flags) >= 1:
        return "medium"
    return "low"
