"""Electional window scoring."""

from __future__ import annotations

from typing import Mapping, Sequence

from .fixed_stars import fixed_star_score
from .models import ScoreBreakdown, ScoreReason
from .presets import ElectionalPreset, dignity_score, filter_positions_for_preset
from .rules import rule_score
from .search import (
    has_angular_benefic,
    has_angular_malefic,
    has_applying_support,
    has_major_stress,
    moon_is_non_void,
    objective_antipattern_notes,
)

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
SCORE_CATEGORIES = {
    "support-aspects": "Aspect quality",
    "mixed-aspects": "Aspect quality",
    "stress-aspects": "Aspect quality",
    "applying-support": "Aspect timing",
    "applying-stress": "Aspect timing",
    "preferred-aspects": "Objective fit",
    "close-contacts": "Aspect timing",
    "angularity": "Planet condition",
    "essential-dignity": "Planet condition",
    "fixed-stars": "Fixed stars",
    "electional-rules": "Electional rules",
    "aspect-timing": "Aspect timing",
    "retrograde-pressure": "Risk pressure",
    "objective-weighting": "Objective fit",
}

OBJECTIVE_PROFILES = {
    "Launch or publish": {
        "support": 1.1,
        "stress": 1.05,
        "applying_support": 1.3,
        "applying_stress": 1.05,
        "preferred": 1.2,
        "angularity": 1.2,
        "dignity": 0.95,
        "retrograde": 1.0,
        "timing": 1.15,
        "rules": 1.05,
    },
    "Meeting or negotiation": {
        "support": 1.15,
        "stress": 1.25,
        "applying_support": 1.25,
        "applying_stress": 1.2,
        "preferred": 1.1,
        "angularity": 0.9,
        "dignity": 1.0,
        "retrograde": 1.0,
        "timing": 1.1,
        "rules": 1.1,
    },
    "Travel departure": {
        "support": 1.0,
        "stress": 1.2,
        "applying_support": 1.2,
        "applying_stress": 1.2,
        "preferred": 1.1,
        "angularity": 0.85,
        "dignity": 0.95,
        "retrograde": 1.35,
        "timing": 1.25,
        "rules": 1.15,
    },
    "Money or business": {
        "support": 1.05,
        "stress": 1.15,
        "applying_support": 1.15,
        "applying_stress": 1.1,
        "preferred": 1.2,
        "angularity": 1.0,
        "dignity": 1.25,
        "retrograde": 1.15,
        "timing": 1.05,
        "rules": 1.05,
    },
}


def objective_profile(objective: str | None) -> Mapping[str, float]:
    return OBJECTIVE_PROFILES.get(str(objective or ""), {})


def weighted_value(value: float, profile: Mapping[str, float], key: str) -> float:
    return value * float(profile.get(key, 1.0))


def clamp_metric(value: float) -> int:
    return max(0, min(99, round(value)))


def metric_band(score: int, *, kind: str) -> str:
    if kind == "volatility":
        if score >= 75:
            return "High"
        if score >= 55:
            return "Active"
        if score >= 35:
            return "Moderate"
        return "Low"
    if kind == "confidence":
        if score >= 80:
            return "High"
        if score >= 65:
            return "Solid"
        if score >= 50:
            return "Cautious"
        return "Low"
    if score >= 80:
        return "Strong"
    if score >= 65:
        return "Usable"
    if score >= 50:
        return "Conditional"
    return "Weak"


def build_window_diagnostics(
    detected_aspects: Sequence[Mapping[str, object]],
    positions: Sequence[Mapping[str, object]],
    rule_evaluations: Mapping[str, object] | None,
    *,
    objective: str | None,
    objective_matches: int,
    angularity: float,
    dignity: float,
    retrograde: float,
    support_count: int,
    stress_count: int,
    mixed_count: int,
    applying_support_count: int,
    applying_stress_count: int,
) -> dict[str, object]:
    judgment_contexts = (
        rule_evaluations.get("judgmentContexts", {})
        if isinstance(rule_evaluations, Mapping)
        else {}
    )
    moon_condition = judgment_contexts.get("moonCondition", {}) if isinstance(judgment_contexts, Mapping) else {}
    window = {
        "objective": objective,
        "detectedAspects": list(detected_aspects),
        "positions": list(positions),
        "moonCondition": moon_condition if isinstance(moon_condition, Mapping) else {},
    }
    major_stress = has_major_stress(window)
    applying_support = has_applying_support(window)
    angular_benefic = has_angular_benefic(window)
    angular_malefic = has_angular_malefic(window)
    moon_non_void = moon_is_non_void(window)
    anti_patterns = objective_antipattern_notes(window, objective)
    rules = rule_evaluations.get("rules", []) if isinstance(rule_evaluations, Mapping) else []
    rule_count = len(rules) if isinstance(rules, list) else 0

    readiness = clamp_metric(
        52
        + objective_matches * 8
        + support_count * 5
        + applying_support_count * 7
        + max(0.0, angularity) * 0.9
        + max(0.0, dignity) * 1.4
        + (8 if angular_benefic else 0)
        - stress_count * 4
        - applying_stress_count * 6
        - min(retrograde, 10.0)
        - (10 if angular_malefic else 0)
        - (8 if not moon_non_void else 0)
        - (8 if anti_patterns else 0)
    )
    volatility = clamp_metric(
        18
        + stress_count * 8
        + applying_stress_count * 10
        + mixed_count * 4
        + min(retrograde, 12.0)
        + (12 if major_stress else 0)
        + (8 if angular_malefic else 0)
        - support_count * 2
        - applying_support_count * 3
    )
    cleanliness = clamp_metric(
        84
        - stress_count * 8
        - mixed_count * 5
        - min(retrograde, 10.0)
        - (14 if major_stress else 0)
        - (12 if angular_malefic else 0)
        - (10 if not moon_non_void else 0)
        - (10 if anti_patterns else 0)
        + applying_support_count * 2
    )
    confidence = clamp_metric(
        56
        + objective_matches * 7
        + applying_support_count * 5
        + rule_count * 2
        + (6 if moon_non_void else -8)
        + (6 if not major_stress else -12)
        + (5 if angular_benefic else 0)
        + (4 if not angular_malefic else -8)
        - mixed_count * 3
        - stress_count * 2
        - applying_stress_count * 5
        - min(retrograde, 10.0)
        - (6 if anti_patterns else 0)
    )

    return {
        "readiness": {
            "score": readiness,
            "band": metric_band(readiness, kind="readiness"),
            "summary": "How ready the window looks for decisive action.",
        },
        "volatility": {
            "score": volatility,
            "band": metric_band(volatility, kind="volatility"),
            "summary": "How turbulent or pressure-prone the window looks.",
        },
        "cleanliness": {
            "score": cleanliness,
            "band": metric_band(cleanliness, kind="cleanliness"),
            "summary": "How free the chart is from conflicting or muddy signals.",
        },
        "confidence": {
            "score": confidence,
            "band": metric_band(confidence, kind="confidence"),
            "summary": "How trustworthy the backend evaluation looks from the available signals.",
        },
        "signals": {
            "majorStress": major_stress,
            "applyingSupport": applying_support,
            "angularBenefic": angular_benefic,
            "angularMalefic": angular_malefic,
            "moonNonVoid": moon_non_void,
            "objectiveAntiPatterns": anti_patterns,
        },
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


def score_band(score: int) -> str:
    if score >= 86:
        return "Prime"
    if score >= 76:
        return "Strong"
    if score >= 60:
        return "Workable"
    if score >= 45:
        return "Fragile"
    return "Avoid"


def score_grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def score_accounting(reasons: Sequence[ScoreReason], raw_score: float, final_score: int) -> dict[str, object]:
    category_totals: dict[str, float] = {}
    positive_total = 0.0
    negative_total = 0.0
    for reason in reasons:
        if reason.code == "base":
            continue
        category = SCORE_CATEGORIES.get(reason.code, "Other")
        value = float(reason.value)
        category_totals[category] = category_totals.get(category, 0.0) + value
        if value >= 0:
            positive_total += value
        else:
            negative_total += value

    return {
        "startingScore": 58,
        "categoryTotals": category_totals,
        "positiveTotal": positive_total,
        "negativeTotal": negative_total,
        "netAdjustment": positive_total + negative_total,
        "rawScore": raw_score,
        "finalScore": final_score,
    }


def score_evaluation(
    final_score: int,
    accounting: Mapping[str, object],
    reasons: Sequence[ScoreReason],
) -> dict[str, object]:
    category_totals = accounting.get("categoryTotals", {})
    if not isinstance(category_totals, Mapping):
        category_totals = {}
    strengths = [
        f"{category} {float(value):+.1f}"
        for category, value in sorted(category_totals.items(), key=lambda item: float(item[1]), reverse=True)
        if float(value) > 0
    ][:3]
    risks = [
        f"{category} {float(value):+.1f}"
        for category, value in sorted(category_totals.items(), key=lambda item: float(item[1]))
        if float(value) < 0
    ][:3]
    biggest_reason = max(
        (reason for reason in reasons if reason.code != "base"),
        key=lambda reason: abs(float(reason.value)),
        default=None,
    )
    band = score_band(final_score)
    summary = f"{band} electional window with net {float(accounting.get('netAdjustment', 0)):+.1f} points."
    if biggest_reason:
        summary += f" Largest factor: {biggest_reason.label} {float(biggest_reason.value):+.1f}."

    return {
        "band": band,
        "grade": score_grade(final_score),
        "summary": summary,
        "strengths": strengths,
        "risks": risks,
    }


def score_window(
    detected_aspects: Sequence[Mapping[str, object]],
    positions: Sequence[Mapping[str, object]],
    preset: ElectionalPreset,
    fixed_star_contacts: Sequence[Mapping[str, object]] = (),
    rule_evaluations: Mapping[str, object] | None = None,
    objective: str | None = None,
) -> int:
    return int(score_breakdown(detected_aspects, positions, preset, fixed_star_contacts, rule_evaluations, objective)["score"])


def score_breakdown(
    detected_aspects: Sequence[Mapping[str, object]],
    positions: Sequence[Mapping[str, object]],
    preset: ElectionalPreset,
    fixed_star_contacts: Sequence[Mapping[str, object]] = (),
    rule_evaluations: Mapping[str, object] | None = None,
    objective: str | None = None,
) -> dict[str, object]:
    return score_breakdown_model(detected_aspects, positions, preset, fixed_star_contacts, rule_evaluations, objective).to_json()


def score_breakdown_model(
    detected_aspects: Sequence[Mapping[str, object]],
    positions: Sequence[Mapping[str, object]],
    preset: ElectionalPreset,
    fixed_star_contacts: Sequence[Mapping[str, object]] = (),
    rule_evaluations: Mapping[str, object] | None = None,
    objective: str | None = None,
) -> ScoreBreakdown:
    counts = tone_counts(detected_aspects)
    applying_counts = applying_tone_counts(detected_aspects)
    scoring = preset.scoring
    profile = objective_profile(objective)
    objective_matches = sum(1 for aspect in detected_aspects if aspect.get("aspectId") in preset.preferred_aspects)
    close_contacts = sum(1 for aspect in detected_aspects if float(aspect.get("orb", 99)) <= scoring.close_contact_orb)
    preset_positions = filter_positions_for_preset(positions, preset)
    angularity = angularity_score(preset_positions)
    dignity = dignity_score(positions, preset)
    retrograde = retrograde_pressure(preset_positions)
    support_points = weighted_value(counts["support"] * scoring.support_weight, profile, "support")
    mixed_points = counts["mixed"] * scoring.mixed_weight
    stress_points = weighted_value(-(counts["stress"] * scoring.stress_penalty), profile, "stress")
    applying_support_points = weighted_value(applying_counts["support"] * 2, profile, "applying_support")
    applying_stress_points = weighted_value(-(applying_counts["stress"] * 2), profile, "applying_stress")
    preferred_points = weighted_value(objective_matches * scoring.preferred_weight, profile, "preferred")
    close_contact_points = close_contacts * scoring.close_contact_weight
    angularity_points = weighted_value(angularity * scoring.angular_multiplier, profile, "angularity")
    dignity_points = weighted_value(dignity * scoring.dignity_weight, profile, "dignity")
    retrograde_points = weighted_value(-retrograde, profile, "retrograde")
    fixed_star_points = fixed_star_score(fixed_star_contacts)
    rule_points = weighted_value(rule_score(rule_evaluations), profile, "rules")
    timing_points = weighted_value(aspect_timing_score(detected_aspects), profile, "timing")
    objective_weighting_points = (
        support_points
        + stress_points
        + applying_support_points
        + applying_stress_points
        + preferred_points
        + angularity_points
        + dignity_points
        + retrograde_points
        + rule_points
        + timing_points
        - (counts["support"] * scoring.support_weight)
        - (-(counts["stress"] * scoring.stress_penalty))
        - (applying_counts["support"] * 2)
        - (-(applying_counts["stress"] * 2))
        - (objective_matches * scoring.preferred_weight)
        - (angularity * scoring.angular_multiplier)
        - (dignity * scoring.dignity_weight)
        - (-retrograde)
        - rule_score(rule_evaluations)
        - aspect_timing_score(detected_aspects)
    )

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
        ScoreReason("objective-weighting", f"{objective or 'General'} weighting", objective_weighting_points),
    )
    final_score = round(max(10, min(99, raw_score)))
    accounting = score_accounting(reasons, raw_score, final_score)
    evaluation = score_evaluation(final_score, accounting, reasons)
    diagnostics = build_window_diagnostics(
        detected_aspects,
        positions,
        rule_evaluations,
        objective=objective,
        objective_matches=objective_matches,
        angularity=angularity,
        dignity=dignity,
        retrograde=retrograde,
        support_count=counts["support"],
        stress_count=counts["stress"],
        mixed_count=counts["mixed"],
        applying_support_count=applying_counts["support"],
        applying_stress_count=applying_counts["stress"],
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
        accounting=accounting,
        evaluation=evaluation,
        diagnostics=diagnostics,
        raw_score=raw_score,
        score=final_score,
        reasons=reasons,
    )
