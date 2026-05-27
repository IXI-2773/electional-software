"""Electional window scoring."""

from __future__ import annotations

from typing import Mapping, Sequence

from .fixed_stars import fixed_star_score
from .models import ScoreBreakdown, ScoreReason
from .presets import ElectionalPreset, dignity_score, filter_positions_for_preset
from .rules import rule_score

BENEFIC_BODIES = {"Venus", "Jupiter"}
CHALLENGING_BODIES = {"Mars", "Saturn"}
ANGULAR_ORB = 8
RETROGRADE_WEIGHTS = {
    "Mercury": 4,
    "Venus": 4,
    "Mars": 4,
    "Jupiter": 3,
    "Saturn": 3,
    "Uranus": 1.5,
    "Neptune": 1.5,
    "Pluto": 1.5,
}
TIMING_SUPPORT_WEIGHTS = {
    "soon": 3.0,
    "near-term": 2.0,
    "later": 0.5,
}
TIMING_STRESS_WEIGHTS = {
    "soon": -3.0,
    "near-term": -2.0,
    "later": -0.5,
}


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


def retrograde_pressure(positions: Sequence[Mapping[str, object]]) -> float:
    pressure = 0.0
    for planet in positions:
        if not planet.get("isRetrograde"):
            continue
        pressure += RETROGRADE_WEIGHTS.get(str(planet.get("name")), 1)
    return pressure


def applying_tone_counts(detected_aspects: Sequence[Mapping[str, object]]) -> dict[str, int]:
    counts = {"support": 0, "stress": 0}
    for aspect in detected_aspects:
        if not aspect.get("isApplying"):
            continue
        tone = str(aspect.get("tone"))
        if tone in counts:
            counts[tone] += 1
    return counts


def aspect_timing_score(detected_aspects: Sequence[Mapping[str, object]]) -> float:
    score = 0.0
    for aspect in detected_aspects:
        if not aspect.get("isApplying"):
            continue
        quality = str(aspect.get("timingQuality") or "")
        tone = str(aspect.get("tone") or "")
        if tone == "support":
            score += TIMING_SUPPORT_WEIGHTS.get(quality, 0.0)
        elif tone == "stress":
            score += TIMING_STRESS_WEIGHTS.get(quality, 0.0)
    return score


def score_window(
    detected_aspects: Sequence[Mapping[str, object]],
    positions: Sequence[Mapping[str, object]],
    preset: ElectionalPreset,
    fixed_star_contacts: Sequence[Mapping[str, object]] = (),
    rule_evaluations: Mapping[str, object] | None = None,
) -> int:
    return int(score_breakdown(detected_aspects, positions, preset, fixed_star_contacts, rule_evaluations)["score"])


def score_breakdown(
    detected_aspects: Sequence[Mapping[str, object]],
    positions: Sequence[Mapping[str, object]],
    preset: ElectionalPreset,
    fixed_star_contacts: Sequence[Mapping[str, object]] = (),
    rule_evaluations: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return score_breakdown_model(detected_aspects, positions, preset, fixed_star_contacts, rule_evaluations).to_json()


def score_breakdown_model(
    detected_aspects: Sequence[Mapping[str, object]],
    positions: Sequence[Mapping[str, object]],
    preset: ElectionalPreset,
    fixed_star_contacts: Sequence[Mapping[str, object]] = (),
    rule_evaluations: Mapping[str, object] | None = None,
) -> ScoreBreakdown:
    counts = tone_counts(detected_aspects)
    applying_counts = applying_tone_counts(detected_aspects)
    scoring = preset.scoring
    objective_matches = sum(1 for aspect in detected_aspects if aspect.get("aspectId") in preset.preferred_aspects)
    close_contacts = sum(1 for aspect in detected_aspects if float(aspect.get("orb", 99)) <= scoring.close_contact_orb)
    preset_positions = filter_positions_for_preset(positions, preset)
    angularity = angularity_score(preset_positions)
    dignity = dignity_score(positions, preset)
    retrograde = retrograde_pressure(preset_positions)
    support_points = counts["support"] * scoring.support_weight
    mixed_points = counts["mixed"] * scoring.mixed_weight
    stress_points = -(counts["stress"] * scoring.stress_penalty)
    applying_support_points = applying_counts["support"] * 2
    applying_stress_points = -(applying_counts["stress"] * 2)
    preferred_points = objective_matches * scoring.preferred_weight
    close_contact_points = close_contacts * scoring.close_contact_weight
    angularity_points = angularity * scoring.angular_multiplier
    dignity_points = dignity * scoring.dignity_weight
    retrograde_points = -retrograde
    fixed_star_points = fixed_star_score(fixed_star_contacts)
    rule_points = rule_score(rule_evaluations)
    timing_points = aspect_timing_score(detected_aspects)

    raw_score = (
        58
        + support_points
        + mixed_points
        + preferred_points
        + close_contact_points
        + applying_support_points
        + applying_stress_points
        + angularity_points
        + dignity_points
        + fixed_star_points
        + rule_points
        + timing_points
        + retrograde_points
        + stress_points
    )
    reasons = (
        ScoreReason("base", "Base electional viability", 58),
        ScoreReason("support-aspects", "Supportive aspects", support_points, count=counts["support"]),
        ScoreReason("mixed-aspects", "Mixed aspects", mixed_points, count=counts["mixed"]),
        ScoreReason("stress-aspects", "Stress aspects", stress_points, count=counts["stress"]),
        ScoreReason("applying-support", "Applying supportive aspects", applying_support_points, count=applying_counts["support"]),
        ScoreReason("applying-stress", "Applying stress aspects", applying_stress_points, count=applying_counts["stress"]),
        ScoreReason("preferred-aspects", "Preferred aspect types", preferred_points, count=objective_matches),
        ScoreReason("close-contacts", "Close contacts", close_contact_points, count=close_contacts),
        ScoreReason("angularity", "Angular planet emphasis", angularity_points, raw=angularity),
        ScoreReason("essential-dignity", "Essential dignity", dignity_points, raw=dignity),
        ScoreReason("fixed-stars", "Fixed star contacts", fixed_star_points, count=len(fixed_star_contacts)),
        ScoreReason("electional-rules", "Electional rules", rule_points),
        ScoreReason("aspect-timing", "Aspect perfection timing", timing_points),
        ScoreReason("retrograde-pressure", "Retrograde pressure", retrograde_points, raw=retrograde),
    )

    return ScoreBreakdown(
        base=58,
        support=counts["support"],
        mixed=counts["mixed"],
        stress=counts["stress"],
        applying_support=applying_counts["support"],
        applying_stress=applying_counts["stress"],
        objective_matches=objective_matches,
        close_contacts=close_contacts,
        angularity=angularity,
        dignity=dignity,
        retrograde_pressure=retrograde,
        fixed_star=fixed_star_points,
        electional_rules=rule_points,
        aspect_timing=timing_points,
        raw_score=raw_score,
        score=round(max(10, min(99, raw_score))),
        reasons=reasons,
    )
