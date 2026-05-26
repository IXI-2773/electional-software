"""Electional window scoring."""

from __future__ import annotations

from typing import Mapping, Sequence

from .presets import ElectionalPreset, dignity_score, filter_positions_for_preset

BENEFIC_BODIES = {"Venus", "Jupiter"}
CHALLENGING_BODIES = {"Mars", "Saturn"}
ANGULAR_ORB = 8


def tone_counts(detected_aspects: Sequence[Mapping[str, object]]) -> dict[str, int]:
    counts = {"support": 0, "stress": 0, "mixed": 0}
    for aspect in detected_aspects:
        tone = str(aspect.get("tone"))
        if tone in counts:
            counts[tone] += 1
    return counts


def angularity_score(positions: Sequence[Mapping[str, object]]) -> float:
    score = 0.0
    for planet in positions:
        if not planet.get("isAngular"):
            continue

        closest_angle = planet.get("closestAngle") or {}
        distance = float(closest_angle.get("distance", ANGULAR_ORB))
        closeness = max(1, ANGULAR_ORB - distance)
        name = str(planet["name"])

        if name in BENEFIC_BODIES:
            score += 7 + closeness
        elif name in CHALLENGING_BODIES:
            score -= 5 + closeness
        else:
            score += 2

    return score


def score_window(
    detected_aspects: Sequence[Mapping[str, object]],
    positions: Sequence[Mapping[str, object]],
    preset: ElectionalPreset,
) -> int:
    counts = tone_counts(detected_aspects)
    scoring = preset.scoring
    objective_matches = sum(1 for aspect in detected_aspects if aspect.get("aspectId") in preset.preferred_aspects)
    close_contacts = sum(1 for aspect in detected_aspects if float(aspect.get("orb", 99)) <= scoring.close_contact_orb)
    preset_positions = filter_positions_for_preset(positions, preset)

    raw_score = (
        58
        + counts["support"] * scoring.support_weight
        + counts["mixed"] * scoring.mixed_weight
        + objective_matches * scoring.preferred_weight
        + close_contacts * scoring.close_contact_weight
        + angularity_score(preset_positions) * scoring.angular_multiplier
        + dignity_score(positions, preset) * scoring.dignity_weight
        - counts["stress"] * scoring.stress_penalty
    )

    return round(max(10, min(99, raw_score)))
