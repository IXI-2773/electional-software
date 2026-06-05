"""Text formatting helpers for reports and backend explanations."""

from __future__ import annotations

from typing import Mapping

BENEFIC_NAMES = {"Venus", "Jupiter"}
CHALLENGING_NAMES = {"Mars", "Saturn"}

from .aspect_highlights import aspect_strength, strongest_aspect_result
from .chart import format_angle, format_position
from .locations import LocationPreset
from .presets import RULERS
from .search import has_major_stress


def score_diagnostic_lines(snapshot: dict[str, object]) -> list[str]:
    breakdown = snapshot.get("scoreBreakdown")
    if not isinstance(breakdown, dict):
        return ["- Diagnostics unavailable."]
    diagnostics = breakdown.get("diagnostics")
    if not isinstance(diagnostics, dict):
        return ["- Diagnostics unavailable."]

    lines: list[str] = []
    for key, label in (
        ("readiness", "Readiness"),
        ("volatility", "Volatility"),
        ("cleanliness", "Cleanliness"),
        ("confidence", "Confidence"),
    ):
        metric = diagnostics.get(key)
        if not isinstance(metric, dict):
            continue
        lines.append(
            f"- {label}: {metric.get('score', 'n/a')} ({metric.get('band', 'n/a')})"
            + (f" - {metric.get('summary')}" if metric.get("summary") else "")
        )

    signals = diagnostics.get("signals")
    if isinstance(signals, dict):
        if signals.get("applyingSupport"):
            lines.append("- Signal: applying support is present.")
        if signals.get("angularBenefic"):
            lines.append("- Signal: angular benefic emphasis is present.")
        if signals.get("majorStress"):
            lines.append("- Signal: major stress is present.")
        if signals.get("angularMalefic"):
            lines.append("- Signal: angular malefic pressure is present.")
        if signals.get("moonNonVoid") is False:
            lines.append("- Signal: Moon is void or uncertain.")
        anti_patterns = signals.get("objectiveAntiPatterns")
        if isinstance(anti_patterns, list) and anti_patterns:
            for note in anti_patterns[:3]:
                lines.append(f"- Anti-pattern: {note}")

    return lines or ["- Diagnostics unavailable."]


def angle_testimony_lines(snapshot: dict[str, object]) -> list[str]:
    breakdown = snapshot.get("scoreBreakdown")
    diagnostics = breakdown.get("diagnostics", {}) if isinstance(breakdown, dict) else {}
    angles = diagnostics.get("angles", {}) if isinstance(diagnostics, dict) else {}
    if not isinstance(angles, dict):
        return ["- Angle testimony unavailable."]
    lines = [
        "Angle Testimony",
        str(angles.get("summary", "No angle summary available.")),
        f"Score impact: {float(angles.get('scoreImpact', 0)):+.1f}",
        (
            f"Benefics {float(angles.get('beneficSupport', 0)):+.1f}; "
            f"malefics {float(angles.get('maleficPressure', 0)):+.1f}; "
            f"luminaries {float(angles.get('luminarySupport', 0)):+.1f}; "
            f"other {float(angles.get('neutralEmphasis', 0)):+.1f}."
        ),
    ]
    factors = angles.get("factors", [])
    if isinstance(factors, list) and factors:
        lines.extend(["", "Angular Bodies"])
        for factor in factors[:8]:
            if not isinstance(factor, dict):
                continue
            lines.append(
                (
                    f"- {factor.get('title', 'Angular body')}: "
                    f"{float(factor.get('distance', 0)):.1f} deg from {factor.get('angle', 'angle')} "
                    f"{factor.get('phaseLabel', '') or ''} "
                    f"{('exact in ' + str(factor.get('timeToExactText'))) if factor.get('timeToExactText') else ''} "
                    f"({float(factor.get('scoreImpact', 0)):+.1f})"
                )
            )
    return lines


def build_diagnostics_page(snapshot: dict[str, object]) -> str:
    breakdown = snapshot.get("scoreBreakdown", {})
    evaluation = breakdown.get("evaluation", {}) if isinstance(breakdown, dict) else {}
    return (
        "Window Diagnostics\n"
        f"Score: {snapshot.get('score', 'n/a')}  "
        f"Band: {evaluation.get('band', 'n/a')}  "
        f"Grade: {evaluation.get('grade', 'n/a')}\n\n"
        "Backend Metrics\n"
        + "\n".join(score_diagnostic_lines(snapshot))
        + "\n\nAngles\n"
        + "\n".join(angle_testimony_lines(snapshot))
        + "\n\nScore Evaluation\n"
        + "\n".join(score_evaluation_lines(snapshot))
    )


def format_dignity_summary(planet: dict[str, object]) -> str:
    dignity = planet.get("dignity", {})
    if not isinstance(dignity, dict):
        return "Unknown"
    bound_lord = dignity.get("boundLord") or "-"
    own_bound = " own bound" if dignity.get("isOwnBound") else ""
    return f"{dignity.get('label', 'Unknown')} / Bound {bound_lord}{own_bound}"


def format_motion_summary(planet: dict[str, object]) -> str:
    motion = planet.get("motion", {})
    if not isinstance(motion, dict):
        return "Motion unknown"
    daily_change = float(motion.get("dailyLongitudeChange", 0))
    summary = f"{motion.get('label', 'Motion unknown')} {daily_change:+.2f} deg/day"
    station = motion.get("station")
    if isinstance(station, dict) and station.get("isInStationWindow"):
        days = station.get("daysFromStation")
        days_text = f", {float(days):+.1f}d" if days is not None else ""
        summary += f" ({station.get('phase', 'station window')}{days_text})"
    return summary


def format_lunar_phase(snapshot: dict[str, object]) -> str:
    phase = snapshot.get("lunarPhase")
    if not isinstance(phase, dict):
        return "Lunar phase unavailable."
    trend = "waxing" if phase.get("isWaxing") else "waning"
    if phase.get("name") in {"New Moon", "Full Moon"}:
        trend = "turning point"
    return (
        f"{phase.get('name', 'Moon phase')} "
        f"({float(phase.get('illumination', 0)) * 100:.0f}% lit, "
        f"age {float(phase.get('ageDays', 0)):.1f} days, {trend})"
    )


def condition_lines(snapshot: dict[str, object]) -> list[str]:
    lines = ["Moon", f"- Phase: {format_lunar_phase(snapshot)}"]
    positions = snapshot.get("positions", [])
    if not isinstance(positions, list):
        return lines + ["", "Motion", "- Planetary motion unavailable."]

    retrograde = [planet for planet in positions if isinstance(planet, dict) and planet.get("isRetrograde")]
    stationary = [
        planet
        for planet in positions
        if isinstance(planet, dict) and isinstance(planet.get("motion"), dict) and planet["motion"].get("isStationary")
    ]
    lines.extend(["", "Motion"])
    if retrograde:
        lines.append(
            "- Retrograde: "
            + ", ".join(f"{planet['name']} ({format_motion_summary(planet)})" for planet in retrograde)
        )
    else:
        lines.append("- Retrograde: none among calculated planets.")
    if stationary:
        lines.append(
            "- Stationary: "
            + ", ".join(f"{planet['name']} ({format_motion_summary(planet)})" for planet in stationary)
        )
    rule_evaluations = snapshot.get("ruleEvaluations", {})
    if isinstance(rule_evaluations, dict):
        lunar_context = rule_evaluations.get("lunarContext", {})
        planetary_hour = rule_evaluations.get("planetaryHour", {})
        if isinstance(lunar_context, dict):
            nakshatra = lunar_context.get("nakshatra", {})
            tithi = lunar_context.get("tithi", {})
            lines.extend(["", "Sidereal Lunar Context"])
            if isinstance(nakshatra, dict):
                lines.append(
                    f"- Nakshatra: {nakshatra.get('name')} pada {nakshatra.get('pada')} "
                    f"(#{nakshatra.get('index')})."
                )
            if isinstance(tithi, dict):
                lines.append(f"- Tithi: {tithi.get('paksha')} {tithi.get('name')} (#{tithi.get('number')}).")
        if isinstance(planetary_hour, dict) and planetary_hour.get("available"):
            lines.extend(
                [
                    "",
                    "Planetary Hour",
                    (
                        f"- Day ruler: {planetary_hour.get('dayRuler')}; "
                        f"{planetary_hour.get('period')} hour {planetary_hour.get('hourNumber')} "
                        f"ruled by {planetary_hour.get('hourRuler')} "
                        f"({float(planetary_hour.get('scoreImpact', 0)):+.1f})."
                    ),
                    f"- Period: {planetary_hour.get('periodStartText')} to {planetary_hour.get('periodEndText')}.",
                ]
            )

    lines.extend(["", "Election Flags", *election_flag_lines(snapshot)])
    rules = rule_lines(snapshot)
    if rules:
        lines.extend(["", "Pure Python Rules", *rules])
    timing = snapshot.get("timingProfile", {})
    if isinstance(timing, dict):
        lines.extend(["", "Aspect Timing", f"- {timing.get('summary', 'Timing profile unavailable.')}"])
    return lines


def election_flag_lines(snapshot: dict[str, object]) -> list[str]:
    flags = []
    aspects = snapshot.get("detectedAspects", [])
    positions = snapshot.get("positions", [])
    if isinstance(aspects, list):
        applying_support = [
            str(aspect.get("label"))
            for aspect in aspects
            if isinstance(aspect, dict) and aspect.get("isApplying") and aspect.get("tone") == "support"
        ]
        applying_stress = [
            str(aspect.get("label"))
            for aspect in aspects
            if isinstance(aspect, dict) and aspect.get("isApplying") and aspect.get("tone") == "stress"
        ]
        if applying_support:
            flags.append("- Tightening support: " + ", ".join(applying_support[:3]) + ".")
        if applying_stress:
            flags.append("- Tightening stress: " + ", ".join(applying_stress[:3]) + ".")

    if isinstance(positions, list):
        angular_benefics = [
            str(planet.get("name"))
            for planet in positions
            if isinstance(planet, dict) and planet.get("isAngular") and planet.get("name") in BENEFIC_NAMES
        ]
        angular_challenges = [
            str(planet.get("name"))
            for planet in positions
            if isinstance(planet, dict) and planet.get("isAngular") and planet.get("name") in CHALLENGING_NAMES
        ]
        if angular_benefics:
            flags.append("- Angular benefic emphasis: " + ", ".join(angular_benefics[:3]) + ".")
        if angular_challenges:
            flags.append("- Angular malefic pressure: " + ", ".join(angular_challenges[:3]) + ".")

    phase = snapshot.get("lunarPhase")
    if isinstance(phase, dict):
        phase_name = str(phase.get("name") or "")
        if phase.get("isWaxing"):
            flags.append(f"- {phase_name} favors building, growth, and visibility.")
        elif phase_name:
            flags.append(f"- {phase_name} favors completion, release, or reduction.")

    return flags or ["- No major condition flags from the current rule set."]


def format_aspect_summary(aspect: dict[str, object]) -> str:
    phase_label = str(aspect.get("phaseLabel") or "Unknown")
    change = float(aspect.get("orbChangePerDay", 0))
    timing = ""
    if aspect.get("isApplying") and aspect.get("timeToExactText"):
        timing = f", exact in {aspect['timeToExactText']}"
        if aspect.get("perfectsAtText"):
            timing += f" near {aspect['perfectsAtText']}"
    if aspect.get("phase") == "unknown":
        return f"{aspect['label']} ({aspect['orbText']} orb, phase unknown)"
    return f"{aspect['label']} ({aspect['orbText']} orb, {phase_label.lower()}, {change:+.2f} deg/day{timing})"


def format_planet_focus(planet: dict[str, object], aspects: list[dict[str, object]]) -> str:
    name = str(planet["name"])
    related = [aspect for aspect in aspects if name in aspect.get("bodies", [])]
    dignity = planet.get("dignity", {})
    dignity_label = dignity.get("label", "Unknown")
    bound_lord = dignity.get("boundLord") or "Unknown"
    angle = planet.get("closestAngle", {})
    lines = [
        f"{name}: {format_position(planet)} in House {planet['house']}.",
        (
            f"Dignity: {dignity_label}. Egyptian bound: {bound_lord}. "
            f"Closest angle: {angle.get('shortName', 'n/a')} at {angle.get('distance', 0):.1f} deg."
        ),
        f"Motion: {format_motion_summary(planet)}.",
    ]
    if dignity.get("isOwnBound"):
        lines.append(f"{name} is in its own Egyptian bound, adding minor essential dignity.")
    if planet.get("isAngular"):
        lines.append(f"{name} is angular, so it is emphasized in this window.")
    if related:
        lines.append("Contacts: " + ", ".join(format_aspect_summary(aspect) for aspect in related[:4]) + ".")
    else:
        lines.append("No selected major aspects are currently in orb for this body.")
    return "\n".join(lines)


def build_medieval_data_page(snapshot: dict[str, object]) -> str:
    evaluation_lines = score_evaluation_lines(snapshot)
    reason_lines = score_reason_lines(snapshot)[:5]
    flag_lines = election_flag_lines(snapshot)[:4]
    active_rules = rule_lines(snapshot)[:6]
    supportive = [
        str(aspect.get("label"))
        for aspect in snapshot.get("detectedAspects", [])
        if isinstance(aspect, dict) and aspect.get("tone") == "support"
    ][:4]
    stressful = [
        str(aspect.get("label"))
        for aspect in snapshot.get("detectedAspects", [])
        if isinstance(aspect, dict) and aspect.get("tone") == "stress"
    ][:4]
    angular = [
        f"{planet.get('name')} near {planet.get('closestAngle', {}).get('shortName', 'angle')}"
        for planet in snapshot.get("positions", [])
        if isinstance(planet, dict) and planet.get("isAngular")
    ][:4]
    planetary_hour = snapshot.get("planetaryHour", {})
    planetary_hour_line = (
        f"- {planetary_hour.get('period', 'n/a').title()} hour {planetary_hour.get('hourNumber')} ruled by {planetary_hour.get('hourRuler')}"
        if isinstance(planetary_hour, dict) and planetary_hour.get("available")
        else "- Planetary hour unavailable."
    )
    lot_lines = (
        "\n".join(
            f"- {lot['name']}: {format_position(lot)} H{lot['house']} | {lot['formula']}"
            + (f" | {lot.get('topic')}" if lot.get("topic") else "")
            for lot in snapshot.get("lots", [])
        )
        if snapshot.get("lots")
        else "- No lots calculated."
    )
    return (
        f"Medieval Data Page\n"
        f"Model: {snapshot['preset'].name}\n"
        f"Zodiac: {snapshot['zodiacSystem'].name}\n"
        f"House system: {snapshot['houseSystem'].name}\n"
        f"Ayanamsha: {float(snapshot['ayanamsha']):.3f} deg\n"
        + (
            "Traditional scoring: disabled in True 13-Sign mode\n"
            if not snapshot.get("traditionalRulesEnabled", True)
            else ""
        )
        + f"Score: {snapshot['score']}\n"
        f"Lunar phase: {format_lunar_phase(snapshot)}\n\n"
        "Verdict\n"
        + "\n".join(evaluation_lines)
        + "\n\nBalance of Testimony\n"
        + (f"- Supportive contacts: {', '.join(supportive)}\n" if supportive else "- Supportive contacts: none selected in orb.\n")
        + (f"- Stressful contacts: {', '.join(stressful)}\n" if stressful else "- Stressful contacts: none selected in orb.\n")
        + (f"- Angular emphasis: {', '.join(angular)}\n" if angular else "- Angular emphasis: none among the currently selected planets.\n")
        + f"{planetary_hour_line}\n\n"
        + "Score Reasons\n"
        + "\n".join(reason_lines)
        + "\n\nElection Flags\n"
        + "\n".join(flag_lines)
        + "\n\nMoon and Significators\n"
        + "\n".join(judgment_context_lines(snapshot, "significatorContext"))
        + "\n\n"
        + "\n".join(judgment_context_lines(snapshot, "moonCondition"))
        + "\n\nHouse Rulers and Reception\n"
        + "\n".join(judgment_context_lines(snapshot, "houseRulerContext"))
        + "\n\n"
        + "\n".join(judgment_context_lines(snapshot, "receptionContext"))
        + "\n\nPlanet Condition and Aspects\n"
        + "\n".join(judgment_context_lines(snapshot, "planetConditionContext"))
        + "\n\n"
        + "\n".join(judgment_context_lines(snapshot, "advancedAspectContext"))
        + "\n\nRules\n"
        + ("\n".join(active_rules) if active_rules else "- No active caution/support rules.")
        + "\n\nLots\n"
        + lot_lines
    )


def build_transit_search_page(
    input_snapshot: dict[str, object],
    selected_window: dict[str, object],
    windows: list[dict[str, object]],
    location: LocationPreset,
    search_summary: str,
    rejection_summary: dict[str, object] | None = None,
) -> str:
    try:
        delta_minutes = round((selected_window["date"] - input_snapshot["date"]).total_seconds() / 60)
    except (KeyError, TypeError, AttributeError):
        delta_label = "n/a"
    else:
        sign = "+" if delta_minutes >= 0 else "-"
        minutes = abs(int(delta_minutes))
        hours, remaining_minutes = divmod(minutes, 60)
        if hours and remaining_minutes:
            delta_label = f"{sign}{hours}h {remaining_minutes}m"
        elif hours:
            delta_label = f"{sign}{hours}h"
        else:
            delta_label = f"{sign}{remaining_minutes}m"

    ranked_lines = []
    for index, window in enumerate(windows[:8], start=1):
        aspect_labels = ", ".join(str(aspect.get("label")) for aspect in window.get("detectedAspects", [])[:2] if isinstance(aspect, dict))
        ranked_lines.append(
            f"#{index}  {window.get('formattedTime', 'time n/a')}  "
            f"score {window.get('score', '?')}  "
            f"{window.get('note', 'No note available.')}"
            + (f"  [{aspect_labels}]" if aspect_labels else "")
        )

    aspect_patterns: dict[str, dict[str, object]] = {}
    for window in windows:
        if not isinstance(window, dict):
            continue
        score = float(window.get("score", 0))
        for aspect in window.get("detectedAspects", []):
            if not isinstance(aspect, dict):
                continue
            label = str(aspect.get("label") or aspect.get("aspectName") or "Aspect")
            item = aspect_patterns.setdefault(
                label,
                {
                    "label": label,
                    "tone": aspect.get("tone", "mixed"),
                    "count": 0,
                    "bestScore": -999.0,
                    "bestTime": "",
                    "totalScore": 0.0,
                },
            )
            item["count"] = int(item["count"]) + 1
            item["totalScore"] = float(item["totalScore"]) + score
            if score > float(item["bestScore"]):
                item["bestScore"] = score
                item["bestTime"] = str(window.get("formattedTime", "time n/a"))
                item["tone"] = aspect.get("tone", item.get("tone", "mixed"))

    aspect_pattern_lines = []
    ranked_patterns = sorted(
        aspect_patterns.values(),
        key=lambda item: (float(item["bestScore"]), int(item["count"]), float(item["totalScore"])),
        reverse=True,
    )
    for item in ranked_patterns[:5]:
        aspect_pattern_lines.append(
            f"- {item['label']} ({item.get('tone', 'mixed')}): "
            f"seen {item['count']}x; best score {float(item['bestScore']):.0f} at {item.get('bestTime') or 'time n/a'}"
        )

    rejection_lines = []
    if isinstance(rejection_summary, dict) and rejection_summary.get("count"):
        top_reasons = rejection_summary.get("topReasons", [])
        samples = rejection_summary.get("samples", [])
        rejection_lines.extend(
            [
                "Rejected Windows",
                f"- Rejected during filtering: {rejection_summary.get('count', 0)}",
            ]
        )
        if isinstance(top_reasons, list) and top_reasons:
            for reason, count in top_reasons[:4]:
                rejection_lines.append(f"- {reason}: {count}")
        if isinstance(samples, list) and samples:
            rejection_lines.append("")
            rejection_lines.append("Rejected Samples")
            for sample in samples[:3]:
                if not isinstance(sample, dict):
                    continue
                rejection_lines.append(
                    f"- {sample.get('formattedTime', 'time unavailable')} score {sample.get('score', '?')}: "
                    + "; ".join(str(reason) for reason in sample.get("reasons", [])[:2])
                )

    return (
        "Transit Search Page\n"
        f"Objective: {selected_window.get('title', 'Electional window')}\n"
        f"Location: {location.name}\n"
        f"Search profile: {search_summary}\n"
        f"Point configuration: {selected_window.get('preset').name if selected_window.get('preset') else 'n/a'}\n\n"
        "Current State\n"
        f"- Search start: {input_snapshot.get('formattedTime', 'n/a')}\n"
        f"- Selected window: {selected_window.get('formattedTime', 'n/a')}\n"
        f"- Difference: {delta_label}\n"
        f"- Selected score: {selected_window.get('score', '?')}\n"
        f"- Timing summary: {selected_window.get('timingProfile', {}).get('summary', 'Timing profile unavailable.')}\n\n"
        "Selected Diagnostics\n"
        + "\n".join(score_diagnostic_lines(selected_window))
        + "\n\n"
        "Best Aspect Patterns\n"
        + ("\n".join(aspect_pattern_lines) if aspect_pattern_lines else "- No aspect patterns available in ranked windows.")
        + "\n\n"
        "Ranked Windows\n"
        + ("\n".join(ranked_lines) if ranked_lines else "- No ranked windows matched the current filters.")
        + ("\n\n" + "\n".join(rejection_lines) if rejection_lines else "")
    )


def build_decision_brief_page(
    input_snapshot: dict[str, object],
    selected_window: dict[str, object],
    objective: str,
    location: LocationPreset,
) -> str:
    breakdown = selected_window.get("scoreBreakdown", {})
    evaluation = breakdown.get("evaluation", {}) if isinstance(breakdown, dict) else {}
    strengths = evaluation.get("strengths", []) if isinstance(evaluation, dict) else []
    risks = evaluation.get("risks", []) if isinstance(evaluation, dict) else []
    fit_matches = int(breakdown.get("objectiveMatches", 0)) if isinstance(breakdown, dict) else 0
    support_aspects = [
        str(aspect.get("label"))
        for aspect in selected_window.get("detectedAspects", [])
        if isinstance(aspect, dict) and aspect.get("tone") == "support"
    ][:3]
    stress_aspects = [
        str(aspect.get("label"))
        for aspect in selected_window.get("detectedAspects", [])
        if isinstance(aspect, dict) and aspect.get("tone") == "stress"
    ][:3]
    try:
        delta_minutes = round((selected_window["date"] - input_snapshot["date"]).total_seconds() / 60)
    except (KeyError, TypeError, AttributeError):
        delta_label = "n/a"
    else:
        sign = "+" if delta_minutes >= 0 else "-"
        minutes = abs(int(delta_minutes))
        hours, remaining = divmod(minutes, 60)
        delta_label = f"{sign}{hours}h {remaining}m" if hours and remaining else f"{sign}{hours}h" if hours else f"{sign}{remaining}m"

    fit_label = "High fit" if fit_matches >= 2 else "Moderate fit" if fit_matches == 1 else "Open fit"
    action_lines = objective_recommendation_lines(selected_window, objective)

    return (
        "Decision Brief\n"
        f"Objective: {objective}\n"
        f"Location: {location.name}\n"
        f"Selected window: {selected_window.get('formattedTime', 'n/a')}\n"
        f"Window quality: {evaluation.get('band', 'n/a')} / Grade {evaluation.get('grade', 'n/a')}\n"
        f"Objective fit: {fit_label} ({fit_matches} preferred aspect match{'es' if fit_matches != 1 else ''})\n"
        f"Timing offset from search start: {delta_label}\n\n"
        "Backend Read\n"
        + "\n".join(score_diagnostic_lines(selected_window)[:6])
        + "\n\n"
        "Recommendation\n"
        f"- {selected_window.get('note', 'No recommendation note available.')}\n"
        + "\n".join(action_lines)
        + "\n\n"
        "Why It Matches\n"
        + ("- Strengths: " + "; ".join(str(item) for item in strengths[:3]) + "\n" if strengths else "- Strengths: no strong support categories surfaced.\n")
        + ("- Supportive contacts: " + "; ".join(support_aspects) + "\n" if support_aspects else "- Supportive contacts: none currently selected in orb.\n")
        + "\n"
        "Watchouts\n"
        + ("- Risks: " + "; ".join(str(item) for item in risks[:3]) + "\n" if risks else "- Risks: no major risk categories surfaced.\n")
        + ("- Stressful contacts: " + "; ".join(stress_aspects) + "\n" if stress_aspects else "- Stressful contacts: none currently selected in orb.\n")
        + "\n"
        "Understanding\n"
        + "\n".join(score_reason_lines(selected_window)[:5])
        + "\n\nTiming\n"
        + f"- {selected_window.get('timingProfile', {}).get('summary', 'Timing profile unavailable.')}\n"
        + "\n".join(election_flag_lines(selected_window)[:3])
    )


def objective_recommendation_lines(selected_window: dict[str, object], objective: str) -> list[str]:
    objective_key = objective.lower()
    score = int(selected_window.get("score", 0))
    fit = int(selected_window.get("scoreBreakdown", {}).get("objectiveMatches", 0))
    major_stress = has_major_stress(selected_window)
    support_labels = [
        str(aspect.get("label"))
        for aspect in selected_window.get("detectedAspects", [])
        if isinstance(aspect, dict) and aspect.get("tone") == "support"
    ]
    angular_labels = [
        str(planet.get("name"))
        for planet in selected_window.get("positions", [])
        if isinstance(planet, dict) and planet.get("isAngular")
    ]

    if "launch" in objective_key or "publish" in objective_key:
        lines = [
            "- Favor this when the goal is visibility, momentum, and a confident public start."
        ]
        if fit >= 2:
            lines.append("- The window matches the launch objective strongly enough to prioritize over nearby alternatives.")
        if angular_labels:
            lines.append(f"- Angular emphasis can help visibility and traction: {', '.join(angular_labels[:2])}.")
    elif "meeting" in objective_key or "negotiation" in objective_key:
        lines = [
            "- Favor this when you want smoother agreement, listening, and lower friction."
        ]
        if support_labels:
            lines.append(f"- Supportive contacts may help cooperation and tone-setting: {', '.join(support_labels[:2])}.")
        if major_stress:
            lines.append("- Be cautious: the chart still carries enough tension to trigger defensiveness or hard bargaining.")
    elif "travel" in objective_key:
        lines = [
            "- Favor this when reliability, clean timing, and fewer disruptions matter more than publicity."
        ]
        if score >= 76:
            lines.append("- This looks usable for departure timing if logistics and local conditions are already in place.")
        if major_stress:
            lines.append("- Watch for avoidable pressure or delays before locking the departure time.")
    elif "money" in objective_key or "business" in objective_key:
        lines = [
            "- Favor this when the aim is steadier value, practical gains, and manageable downside."
        ]
        if fit >= 1:
            lines.append("- The chart shows at least one direct objective match, which is useful for business timing.")
        if major_stress:
            lines.append("- Risk controls matter here because the stress profile is still strong enough to erode gains.")
    else:
        lines = [
            f"- Use this when you want a cleaner {objective.lower()} push with the current support profile."
            if score >= 76
            else f"- Use this carefully for {objective.lower()} only if the timing constraints matter more than perfect conditions."
        ]

    if major_stress and all("stress" not in line.lower() and "risk" not in line.lower() for line in lines):
        lines.append("- Major stress is present, so give extra weight to downside management before committing.")
    return lines


def build_window_comparison_page(
    input_snapshot: dict[str, object],
    windows: list[dict[str, object]],
    objective: str,
) -> str:
    lines = ["Candidate Comparison", f"Objective: {objective}", ""]
    if not windows:
        return "\n".join(lines + ["- No candidate windows available."])
    for index, window in enumerate(windows[:6], start=1):
        breakdown = window.get("scoreBreakdown", {})
        evaluation = breakdown.get("evaluation", {}) if isinstance(breakdown, dict) else {}
        fit_matches = int(breakdown.get("objectiveMatches", 0)) if isinstance(breakdown, dict) else 0
        strengths = evaluation.get("strengths", []) if isinstance(evaluation, dict) else []
        risks = evaluation.get("risks", []) if isinstance(evaluation, dict) else []
        support = sum(1 for aspect in window.get("detectedAspects", []) if isinstance(aspect, dict) and aspect.get("tone") == "support")
        stress = sum(1 for aspect in window.get("detectedAspects", []) if isinstance(aspect, dict) and aspect.get("tone") == "stress")
        angular = sum(1 for planet in window.get("positions", []) if isinstance(planet, dict) and planet.get("isAngular"))
        try:
            delta_minutes = round((window["date"] - input_snapshot["date"]).total_seconds() / 60)
        except (KeyError, TypeError, AttributeError):
            delta_label = "n/a"
        else:
            sign = "+" if delta_minutes >= 0 else "-"
            minutes = abs(int(delta_minutes))
            hours, remaining = divmod(minutes, 60)
            delta_label = f"{sign}{hours}h {remaining}m" if hours and remaining else f"{sign}{hours}h" if hours else f"{sign}{remaining}m"
        lines.extend(
            [
                f"#{index}  {window.get('formattedTime', 'n/a')}  Score {window.get('score', '?')}  {evaluation.get('band', 'n/a')}",
                f"  Fit {fit_matches}  +{support}/!{stress}  Angular {angular}  Offset {delta_label}",
                f"  Diagnostics: {'; '.join(item[2:] for item in score_diagnostic_lines(window)[:4])}",
                f"  Best use: {window.get('title', 'Electional window')}",
                f"  Strength: {strengths[0] if strengths else 'n/a'}",
                f"  Risk: {risks[0] if risks else 'n/a'}",
                f"  Timing: {window.get('timingProfile', {}).get('summary', 'Timing profile unavailable.')}",
                f"  Note: {window.get('note', '')}",
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def build_comparison_export_text(
    input_snapshot: dict[str, object],
    selected_window: dict[str, object],
    windows: list[dict[str, object]],
    objective: str,
    location: LocationPreset,
) -> str:
    return (
        "Electional Decision Sheet\n"
        f"Objective: {objective}\n"
        f"Location: {location.name}\n\n"
        + build_decision_brief_page(input_snapshot, selected_window, objective, location)
        + "\n\n"
        + build_window_comparison_page(input_snapshot, windows, objective)
    )


def build_classical_point_data_page(snapshot: dict[str, object]) -> str:
    planet_lines = []
    for planet in snapshot.get("positions", []):
        if not isinstance(planet, dict):
            continue
        angular = f" | {planet.get('closestAngle', {}).get('shortName', 'angle')} {float(planet.get('closestAngle', {}).get('distance', 0)):.1f} deg" if isinstance(planet.get("closestAngle"), dict) else ""
        planet_lines.append(
            f"- {planet.get('name', 'Planet')}: {format_position(planet)} | H{planet.get('house', '?')} | "
            f"{format_dignity_summary(planet)} | {format_motion_summary(planet)}{angular}"
        )

    lot_lines = []
    for lot in snapshot.get("lots", []):
        if not isinstance(lot, dict):
            continue
        lot_lines.append(
            f"- {lot.get('name', 'Lot')}: {format_position(lot)} | H{lot.get('house', '?')} | "
            f"{lot.get('formula', 'Formula n/a')}"
            + (f" | {lot.get('topic')}" if lot.get("topic") else "")
        )

    node_lines = []
    for node in snapshot.get("lunarNodes", []):
        if not isinstance(node, dict):
            continue
        node_lines.append(
            f"- {node.get('name', 'Node')}: {format_position(node)} | H{node.get('house', '?')} | "
            f"{node.get('calculation', 'node calculation')}"
        )

    cusp_lines = []
    for cusp in snapshot.get("houseCusps", []):
        if not isinstance(cusp, dict):
            continue
        cusp_lines.append(f"- House {cusp.get('house', '?')}: {format_position(cusp)}")

    angle_lines = []
    for angle in snapshot.get("angles", []):
        if not isinstance(angle, dict):
            continue
        angle_lines.append(f"- {format_angle(angle)}")

    star_contact_lines = []
    for contact in snapshot.get("fixedStarContacts", []):
        if not isinstance(contact, dict):
            continue
        star_contact_lines.append(f"- {format_fixed_star_contact(contact)}")

    return (
        "Classical Point Data\n"
        f"Model: {snapshot['preset'].name}\n"
        f"Zodiac: {snapshot['zodiacSystem'].name}\n"
        f"House system: {snapshot['houseSystem'].name}\n"
        f"Ayanamsha: {float(snapshot['ayanamsha']):.3f} deg\n"
        f"Score: {snapshot['score']}\n\n"
        "Planets\n"
        + ("\n".join(planet_lines) if planet_lines else "- No planets calculated.")
        + "\n\nAngles\n"
        + ("\n".join(angle_lines) if angle_lines else "- No angles calculated.")
        + "\n\nHouse Cusps\n"
        + ("\n".join(cusp_lines) if cusp_lines else "- No house cusps calculated.")
        + "\n\nArabic Lots\n"
        + ("\n".join(lot_lines) if lot_lines else "- No lots calculated.")
        + "\n\nLunar Nodes\n"
        + ("\n".join(node_lines) if node_lines else "- No lunar nodes calculated.")
        + "\n\nFixed Star Contacts\n"
        + ("\n".join(star_contact_lines) if star_contact_lines else "- No fixed-star conjunctions within the diagnostic star orb.")
    )


def format_score_breakdown(snapshot: dict[str, object]) -> str:
    breakdown = snapshot.get("scoreBreakdown")
    if not isinstance(breakdown, dict):
        return "Score breakdown unavailable."
    return (
        f"Base {breakdown.get('base', 58)}; "
        f"support {breakdown.get('support', 0)}, mixed {breakdown.get('mixed', 0)}, stress {breakdown.get('stress', 0)}; "
        f"applying +{breakdown.get('applyingSupport', 0)}/!{breakdown.get('applyingStress', 0)}; "
        f"preferred aspects {breakdown.get('objectiveMatches', 0)}; "
        f"close contacts {breakdown.get('closeContacts', 0)}; "
        f"angularity {float(breakdown.get('angularity', 0)):.1f}; "
        f"dignity {float(breakdown.get('dignity', 0)):.1f}; "
        f"fixed stars {float(breakdown.get('fixedStar', 0)):+.1f}; "
        f"rules {float(breakdown.get('electionalRules', 0)):+.1f}; "
        f"timing {float(breakdown.get('aspectTiming', 0)):+.1f}; "
        f"retrograde pressure {float(breakdown.get('retrogradePressure', 0)):.1f}; "
        f"raw {float(breakdown.get('rawScore', 0)):.1f} -> final {breakdown.get('score', snapshot.get('score', '?'))}."
    )


def score_accounting_lines(snapshot: dict[str, object]) -> list[str]:
    breakdown = snapshot.get("scoreBreakdown")
    if not isinstance(breakdown, dict):
        return ["- Score accounting unavailable."]
    accounting = breakdown.get("accounting")
    if not isinstance(accounting, dict):
        return ["- Score accounting unavailable."]
    lines = [
        (
            f"- Start {float(accounting.get('startingScore', 58)):.1f}; "
            f"positive {float(accounting.get('positiveTotal', 0)):+.1f}; "
            f"negative {float(accounting.get('negativeTotal', 0)):+.1f}; "
            f"net {float(accounting.get('netAdjustment', 0)):+.1f}; "
            f"raw {float(accounting.get('rawScore', 0)):.1f}; final {accounting.get('finalScore', breakdown.get('score', '?'))}."
        )
    ]
    category_totals = accounting.get("categoryTotals")
    if isinstance(category_totals, dict):
        for category, value in sorted(category_totals.items(), key=lambda item: abs(float(item[1])), reverse=True):
            lines.append(f"- {category}: {float(value):+.1f}")
    return lines


def constellation_lines(snapshot: dict[str, object]) -> list[str]:
    context = snapshot.get("constellationContext")
    if not isinstance(context, dict):
        return ["- Constellation proportion data unavailable."]
    rising = context.get("rising", {})
    if not isinstance(rising, dict):
        return ["- Rising constellation data unavailable."]
    asc = rising.get("ascendantConstellation", {})
    tempo = rising.get("tempo", {})
    span_context = rising.get("spanContext", {})
    lines = ["Unequal Ecliptic Constellations"]
    if isinstance(asc, dict):
        next_constellation = asc.get("nextConstellation", {})
        next_name = next_constellation.get("name", "next constellation") if isinstance(next_constellation, dict) else "next constellation"
        lines.extend(
            [
                (
                    f"- ASC: {asc.get('name', 'n/a')} "
                    f"({float(asc.get('spanDegrees', 0)):.1f} deg, "
                    f"{float(asc.get('spanRatioToSign', 0)):.2f}x a 30 deg sign)."
                ),
                (
                    f"- Through span: {float(asc.get('percentThrough', 0)) * 100:.0f}%; "
                    f"{float(asc.get('distanceToEndDegrees', 0)):.1f} deg to {next_name}."
                ),
            ]
        )
    lines.extend(
        [
            "",
            "Ascensional Motion",
            (
                f"- Speed: {float(rising.get('ascendantSpeedDegPerHour', 0)):.1f} deg/hour "
                f"({tempo.get('label', 'n/a') if isinstance(tempo, dict) else 'n/a'}, "
                f"{float(tempo.get('scoreImpact', 0)):+.1f} pts)."
            ),
            (
                f"- Current constellation rising time: "
                f"{float(rising.get('currentConstellationRisingMinutes', 0)):.0f} min; "
                f"current 30 deg sign: {float(rising.get('currentSignRisingMinutes', 0)):.0f} min."
            ),
            f"- Estimated time to next constellation boundary: {float(rising.get('minutesToNextConstellation', 0)):.0f} min.",
        ]
    )
    if isinstance(span_context, dict):
        lines.append(f"- Span factor: {span_context.get('label', 'n/a')} ({float(span_context.get('scoreImpact', 0)):+.1f} pts).")
    bodies = []
    for point in context.get("positions", []):
        if not isinstance(point, dict) or point.get("name") not in {"Sun", "Moon", "Mercury", "Venus", "Mars"}:
            continue
        constellation = point.get("constellation")
        if isinstance(constellation, dict):
            bodies.append(f"{point.get('name')}: {constellation.get('name')} ({float(constellation.get('spanDegrees', 0)):.0f} deg)")
    if bodies:
        lines.extend(["", "Key Bodies", "- " + "; ".join(bodies)])
    source_note = context.get("sourceNote")
    if source_note:
        lines.extend(["", f"Note: {source_note}"])
    return lines


JUDGMENT_CONTEXT_LABELS = {
    "significatorContext": "Significators",
    "moonCondition": "Moon Condition",
    "houseRulerContext": "House Rulers",
    "angleContext": "Angles",
    "receptionContext": "Reception",
    "planetConditionContext": "Planet Condition",
    "declinationContext": "Declination",
    "advancedAspectContext": "Advanced Aspects",
    "fixedStarContext": "Fixed Stars",
    "constellationContext": "Constellation / Rising",
}


def judgment_context_lines(snapshot: dict[str, object], context_key: str) -> list[str]:
    context = snapshot.get(context_key)
    if not isinstance(context, dict):
        return [f"- {JUDGMENT_CONTEXT_LABELS.get(context_key, context_key)} unavailable."]
    lines = [
        JUDGMENT_CONTEXT_LABELS.get(context_key, context_key),
        str(context.get("summary", "No summary available.")),
        f"Score impact: {float(context.get('scoreImpact', 0)):+.1f}",
        f"Confidence: {context.get('confidence', 'n/a')}",
    ]
    factors = context.get("factors", [])
    if isinstance(factors, list) and factors:
        lines.extend(["", "Factors"])
        for factor in factors:
            if not isinstance(factor, dict):
                continue
            lines.append(
                (
                    f"- {factor.get('title', 'Factor')}: "
                    f"{factor.get('detail', '')} "
                    f"({float(factor.get('scoreImpact', 0)):+.1f})"
                )
            )
    return lines


def _factor_context_impact(snapshot: dict[str, object], context_key: str) -> float:
    context = snapshot.get(context_key)
    if context_key == "constellationContext":
        rising = context.get("rising", {}) if isinstance(context, dict) else {}
        return float(rising.get("scoreImpact", 0)) if isinstance(rising, dict) else 0.0
    return float(context.get("scoreImpact", 0)) if isinstance(context, dict) else 0.0


def _factor_delta_text(current: float, baseline: dict[str, object] | None, context_key: str) -> str:
    if not baseline:
        return ""
    previous = _factor_context_impact(baseline, context_key)
    delta = current - previous
    if abs(delta) < 0.05:
        return " | unchanged vs start"
    direction = "improved" if delta > 0 else "worsened"
    return f" | {direction} {delta:+.1f} vs start"


def factor_explorer_lines(snapshot: dict[str, object], baseline: dict[str, object] | None = None) -> list[str]:
    lines = ["Factor Explorer", f"Score: {snapshot.get('score', 'n/a')}"]
    if baseline and baseline is not snapshot:
        try:
            delta = int(snapshot.get("score", 0)) - int(baseline.get("score", 0))
            lines.append(f"Compared with search-start chart: {delta:+d} points.")
        except (TypeError, ValueError):
            lines.append("Compared with search-start chart: n/a.")
    for context_key, label in JUDGMENT_CONTEXT_LABELS.items():
        context = snapshot.get(context_key)
        impact = _factor_context_impact(snapshot, context_key)
        lines.extend(["", f"{label} ({impact:+.1f}{_factor_delta_text(impact, baseline if baseline is not snapshot else None, context_key)})"])
        if context_key == "constellationContext":
            lines.extend(constellation_lines(snapshot)[:8])
            continue
        if not isinstance(context, dict):
            lines.append("- Unavailable.")
            continue
        factors = context.get("factors", [])
        if not isinstance(factors, list) or not factors:
            lines.append(f"- {context.get('summary', 'No scored factors.')}")
            continue
        for factor in factors[:8]:
            if isinstance(factor, dict):
                lines.append(
                    f"- {factor.get('title', 'Factor')} [{factor.get('severity', 'info')}]: "
                    f"{float(factor.get('scoreImpact', 0)):+.1f}"
                )
    return lines


def advisor_lines(
    snapshot: dict[str, object],
    baseline: dict[str, object] | None = None,
    objective: str = "",
) -> list[str]:
    score = int(snapshot.get("score", 0) or 0)
    breakdown = snapshot.get("scoreBreakdown")
    evaluation = breakdown.get("evaluation", {}) if isinstance(breakdown, dict) else {}
    band = evaluation.get("band", "n/a") if isinstance(evaluation, dict) else "n/a"
    grade = evaluation.get("grade", "n/a") if isinstance(evaluation, dict) else "n/a"
    lines = [
        "Election Advisor",
        f"Objective: {objective or snapshot.get('title', 'Election')}",
        f"Score: {score} ({band} / Grade {grade})",
        "",
        "Verdict",
        f"- {_advisor_verdict(score, has_major_stress(snapshot))}",
    ]
    if baseline and baseline is not snapshot:
        try:
            delta = score - int(baseline.get("score", 0) or 0)
        except (TypeError, ValueError):
            delta = None
        lines.append(f"- Change from search start: {delta:+d} points." if delta is not None else "- Change from search start: n/a.")

    support_factors, caution_factors = _advisor_factor_groups(snapshot)
    lines.extend(["", "Best Supports"])
    lines.extend(support_factors[:4] or ["- No strong scored supports surfaced yet."])
    lines.extend(["", "Needs Attention"])
    lines.extend(caution_factors[:4] or ["- No major scored cautions surfaced yet."])
    lines.extend(["", "Open Next"])
    lines.extend(_advisor_tool_suggestions(snapshot, support_factors, caution_factors))
    return lines


def _advisor_verdict(score: int, major_stress: bool) -> str:
    if score >= 85 and not major_stress:
        return "Strong candidate. Use the Factor Explorer and Timing page to protect the exact minute."
    if score >= 75:
        return "Usable candidate with conditions. Inspect cautions before committing."
    if score >= 62:
        return "Mixed candidate. Compare nearby windows and look for cleaner Moon or significator support."
    return "Weak candidate. Use search tools to move the window unless timing constraints are unavoidable."


def _advisor_factor_groups(snapshot: dict[str, object]) -> tuple[list[str], list[str]]:
    supports: list[tuple[float, str]] = []
    cautions: list[tuple[float, str]] = []
    for context_key, label in JUDGMENT_CONTEXT_LABELS.items():
        context = snapshot.get(context_key)
        if not isinstance(context, dict):
            continue
        factors = context.get("factors", [])
        if not isinstance(factors, list):
            continue
        for factor in factors:
            if not isinstance(factor, dict):
                continue
            impact = float(factor.get("scoreImpact", 0) or 0)
            title = str(factor.get("title", "Factor"))
            detail = str(factor.get("detail", "")).strip()
            line = f"- {label}: {title} ({impact:+.1f})" + (f" - {detail}" if detail else "")
            if impact > 0:
                supports.append((impact, line))
            elif impact < 0:
                cautions.append((abs(impact), line))
    supports.sort(key=lambda item: item[0], reverse=True)
    cautions.sort(key=lambda item: item[0], reverse=True)
    return [line for _impact, line in supports], [line for _impact, line in cautions]


def _advisor_tool_suggestions(snapshot: dict[str, object], supports: list[str], cautions: list[str]) -> list[str]:
    suggestions = ["- Factor Explorer: see every scored layer and what changed from the search-start chart."]
    aspects = snapshot.get("detectedAspects", [])
    aspect_items = aspects if isinstance(aspects, list) else []
    has_stress_contact = any(isinstance(aspect, dict) and aspect.get("tone") == "stress" for aspect in aspect_items)
    if has_major_stress(snapshot) or has_stress_contact:
        suggestions.append("- Timing + Aspects: inspect the next stress contact before locking the minute.")
    moon_context = snapshot.get("moonCondition")
    if isinstance(moon_context, dict) and (moon_context.get("scoreImpact", 0) or 0) < 0:
        suggestions.append("- Moon + Void Course: check whether lunar condition is the main blocker.")
    planet_context = snapshot.get("planetConditionContext")
    if isinstance(planet_context, dict) and (planet_context.get("scoreImpact", 0) or 0) < 0:
        suggestions.append("- Planet Condition + Heliacal Search: review combustion, beams, stations, and slow motion.")
    reception_context = snapshot.get("receptionContext")
    if isinstance(reception_context, dict) and (reception_context.get("scoreImpact", 0) or 0) > 0:
        suggestions.append("- Reception: use the reception page to explain why a hard contact may be softened.")
    angle_context = snapshot.get("angleContext")
    if isinstance(angle_context, dict) and angle_context.get("factors"):
        suggestions.append("- Angles: inspect which planets are carrying the chart through ASC, MC, DSC, or IC.")
    constellation_context = snapshot.get("constellationContext")
    if isinstance(constellation_context, dict):
        rising = constellation_context.get("rising", {})
        if isinstance(rising, dict) and abs(float(rising.get("scoreImpact", 0) or 0)) > 0:
            suggestions.append("- Constellations: review rising speed and boundary timing before fine-tuning ASC.")
    if supports and cautions:
        suggestions.append("- Compare: check whether nearby windows keep the support while dropping the largest caution.")
    return suggestions[:6]


def improvement_guide_lines(
    snapshot: dict[str, object],
    baseline: dict[str, object] | None = None,
) -> list[str]:
    lines = ["Score Improvement Guide", f"Current score: {snapshot.get('score', 'n/a')}"]
    if baseline and baseline is not snapshot:
        try:
            delta = int(snapshot.get("score", 0) or 0) - int(baseline.get("score", 0) or 0)
            lines.append(f"Change from search start: {delta:+d} points.")
        except (TypeError, ValueError):
            lines.append("Change from search start: n/a.")
    moves = _improvement_moves(snapshot)
    blockers = _improvement_blockers(snapshot)
    lines.extend(["", "Best Moves"])
    lines.extend(moves[:6] or ["- Run a wider search, then compare nearby candidates for stronger support and lower pressure."])
    lines.extend(["", "Main Blockers"])
    lines.extend(blockers[:6] or ["- No clear blocker surfaced; use Factor Explorer to inspect smaller testimony layers."])
    lines.extend(["", "Fine Tuning"])
    lines.extend(_fine_tuning_lines(snapshot))
    return lines


def _improvement_moves(snapshot: dict[str, object]) -> list[str]:
    moves: list[str] = []
    diagnostics = _score_diagnostics(snapshot)
    signals = diagnostics.get("signals", {}) if isinstance(diagnostics, dict) else {}
    if isinstance(signals, dict):
        if not signals.get("applyingSupport"):
            moves.append("- Search for the next window with an applying supportive aspect; this usually improves timing confidence.")
        if signals.get("majorStress"):
            moves.append("- Move the minute away from tight applying stress or compare windows just before/after the stress peak.")
        if signals.get("angularMalefic"):
            moves.append("- Adjust time until Mars/Saturn are farther from ASC, MC, DSC, or IC.")
        if not signals.get("angularBenefic"):
            moves.append("- Try to bring Venus or Jupiter closer to ASC or MC for cleaner visible support.")
        if signals.get("moonNonVoid") is False:
            moves.append("- Shift to a non-void Moon or wait for the Moon's next applying contact.")
        anti_patterns = signals.get("objectiveAntiPatterns")
        if isinstance(anti_patterns, list) and anti_patterns:
            moves.append("- Change objective filters or timing to remove the top objective anti-pattern.")

    angle_context = snapshot.get("angleContext")
    if isinstance(angle_context, dict):
        for factor in angle_context.get("factors", []) if isinstance(angle_context.get("factors"), list) else []:
            if not isinstance(factor, dict):
                continue
            impact = float(factor.get("scoreImpact", 0) or 0)
            if impact < 0:
                moves.append(f"- Reduce {factor.get('body', 'malefic')} angular pressure near {factor.get('angle', 'angle')}.")
                break
    planet_context = snapshot.get("planetConditionContext")
    if isinstance(planet_context, dict) and float(planet_context.get("scoreImpact", 0) or 0) < 0:
        moves.append("- Check Planet Condition for stations, retrogrades, combustion, or under-beams pressure before accepting the time.")
    return _dedupe_lines(moves)


def _improvement_blockers(snapshot: dict[str, object]) -> list[str]:
    blockers: list[tuple[float, str]] = []
    breakdown = snapshot.get("scoreBreakdown")
    reasons = breakdown.get("reasons", []) if isinstance(breakdown, dict) else []
    if isinstance(reasons, list):
        for reason in reasons:
            if not isinstance(reason, dict):
                continue
            value = float(reason.get("value", 0) or 0)
            if value < 0:
                blockers.append((abs(value), f"- {reason.get('label', reason.get('code', 'Score factor'))}: {value:+.1f}"))
    for context_key, label in JUDGMENT_CONTEXT_LABELS.items():
        context = snapshot.get(context_key)
        if not isinstance(context, dict):
            continue
        for factor in context.get("factors", []) if isinstance(context.get("factors"), list) else []:
            if not isinstance(factor, dict):
                continue
            impact = float(factor.get("scoreImpact", 0) or 0)
            if impact < 0:
                blockers.append((abs(impact), f"- {label}: {factor.get('title', 'Factor')} ({impact:+.1f})"))
    blockers.sort(key=lambda item: item[0], reverse=True)
    return _dedupe_lines([line for _impact, line in blockers])


def _fine_tuning_lines(snapshot: dict[str, object]) -> list[str]:
    timing = snapshot.get("timingProfile")
    lines: list[str] = []
    if isinstance(timing, dict):
        next_support = timing.get("nextSupport")
        next_stress = timing.get("nextStress")
        if isinstance(next_support, dict):
            lines.append(f"- Protect support: {next_support.get('label')} exact in {next_support.get('timeToExactText', 'n/a')}.")
        if isinstance(next_stress, dict):
            lines.append(f"- Watch stress: {next_stress.get('label')} exact in {next_stress.get('timeToExactText', 'n/a')}.")
    angles = snapshot.get("angleContext")
    if isinstance(angles, dict) and angles.get("factors"):
        lines.append("- Use the Angles tab after every time shift; angle testimony can change quickly.")
    if snapshot.get("constellationContext"):
        lines.append("- Use Constellations when the ASC is near a boundary or rising speed is unusual.")
    return lines or ["- Compare adjacent windows in 5 to 15 minute increments and keep the one with fewer cautions."]


def _score_diagnostics(snapshot: dict[str, object]) -> dict[str, object]:
    breakdown = snapshot.get("scoreBreakdown")
    diagnostics = breakdown.get("diagnostics", {}) if isinstance(breakdown, dict) else {}
    return diagnostics if isinstance(diagnostics, dict) else {}


def _dedupe_lines(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for line in lines:
        if line in seen:
            continue
        seen.add(line)
        unique.append(line)
    return unique


def score_evaluation_lines(snapshot: dict[str, object]) -> list[str]:
    breakdown = snapshot.get("scoreBreakdown")
    if not isinstance(breakdown, dict):
        return ["- Score evaluation unavailable."]
    evaluation = breakdown.get("evaluation")
    if not isinstance(evaluation, dict):
        return ["- Score evaluation unavailable."]
    lines = [
        f"- Band: {evaluation.get('band', 'n/a')} / Grade {evaluation.get('grade', 'n/a')}",
        f"- {evaluation.get('summary', 'No evaluation summary.')}",
    ]
    strengths = evaluation.get("strengths")
    risks = evaluation.get("risks")
    if isinstance(strengths, list) and strengths:
        lines.append("- Strengths: " + "; ".join(str(item) for item in strengths))
    if isinstance(risks, list) and risks:
        lines.append("- Risks: " + "; ".join(str(item) for item in risks))
    return lines


def _float_value(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _position_by_name(snapshot: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    positions = snapshot.get("positions", [])
    if not isinstance(positions, list):
        return {}
    return {
        str(planet.get("name")): planet
        for planet in positions
        if isinstance(planet, Mapping) and planet.get("name")
    }


def _house_class(house: object) -> tuple[str, float]:
    try:
        house_number = int(house)
    except (TypeError, ValueError):
        return "unknown house", 0.0
    if house_number in {1, 4, 7, 10}:
        return "angular", 1.5
    if house_number in {2, 5, 8, 11}:
        return "succedent", 0.7
    return "cadent", -0.2


def _dignity_label_and_score(planet: Mapping[str, object] | None) -> tuple[str, float]:
    if not isinstance(planet, Mapping):
        return "dignity unavailable", 0.0
    dignity = planet.get("dignity")
    if isinstance(dignity, Mapping):
        label = str(dignity.get("label") or "Peregrine")
        return label, _float_value(dignity.get("score"))
    return "dignity unavailable", 0.0


def _planet_condition_phrase(planet: Mapping[str, object] | None) -> str:
    if not isinstance(planet, Mapping):
        return "not found in the selected point set."
    house = planet.get("house", "n/a")
    house_label, _house_score = _house_class(house)
    dignity_label, dignity_score = _dignity_label_and_score(planet)
    pieces = [f"House {house} ({house_label})", f"{dignity_label} {dignity_score:+.0f}"]
    closest_angle = planet.get("closestAngle")
    if isinstance(closest_angle, Mapping):
        short_name = closest_angle.get("shortName") or closest_angle.get("name")
        distance = closest_angle.get("distance")
        if short_name and distance is not None:
            pieces.append(f"nearest {short_name} {_float_value(distance):.1f} deg")
    if planet.get("isRetrograde"):
        pieces.append("retrograde")
    return "; ".join(pieces)


def _angle_sign(snapshot: Mapping[str, object], angle_id: str, fallback_house: int) -> str:
    angles = snapshot.get("angles", [])
    if isinstance(angles, list):
        for angle in angles:
            if not isinstance(angle, Mapping) or angle.get("id") != angle_id:
                continue
            zodiac = angle.get("zodiac")
            if isinstance(zodiac, Mapping) and zodiac.get("sign"):
                return str(zodiac.get("sign"))
    house_cusps = snapshot.get("houseCusps", [])
    if isinstance(house_cusps, list):
        for cusp in house_cusps:
            if not isinstance(cusp, Mapping) or cusp.get("house") != fallback_house:
                continue
            zodiac = cusp.get("zodiac")
            if isinstance(zodiac, Mapping) and zodiac.get("sign"):
                return str(zodiac.get("sign"))
    return ""


def _aspect_label(aspect: Mapping[str, object]) -> str:
    label = aspect.get("label")
    if label:
        return str(label)
    bodies = aspect.get("bodies", [])
    aspect_name = str(aspect.get("aspectName") or "aspect").lower()
    if isinstance(bodies, list) and len(bodies) == 2:
        return f"{bodies[0]} {aspect_name} {bodies[1]}"
    return str(aspect.get("aspectName") or "Aspect")


def _aspect_strength_score(
    aspect: Mapping[str, object],
    positions_by_name: Mapping[str, Mapping[str, object]],
    priority_bodies: set[str],
) -> float:
    return aspect_strength(aspect, positions_by_name, priority_bodies)


def format_aspect_highlight(result: Mapping[str, object] | None) -> str:
    """Render one strongest-aspect result for dashboards and reports."""

    if not result:
        return "No selected major aspect in orb."
    label = _aspect_label(result)
    tone = str(result.get("tone") or "mixed").title()
    phase = str(result.get("phaseLabel") or ("Applying" if result.get("isApplying") else "Separating"))
    orb = str(result.get("orbText") or f"{_float_value(result.get('orb')):.2f} deg")
    exact = str(result.get("perfectsAtText") or result.get("timeToExactText") or "exact timing n/a")
    time = str(result.get("formattedTime") or "")
    strength = _float_value(result.get("strength"))
    relevance = "supportive electional contact" if result.get("tone") == "support" else "stress to manage" if result.get("tone") == "stress" else "mixed testimony"
    text = f"{label} | {tone} | orb {orb} | {phase.lower()} | peak {exact} | strength {strength:.1f} | {relevance}"
    return f"{text}\n{time}" if time else text


def format_aspect_highlight_dashboard(highlights: Mapping[str, object] | None) -> str:
    """Compact current/day/24-hour strongest-aspect block."""

    if not highlights:
        return "Aspect dashboard unavailable."
    sections = (
        ("Current", highlights.get("current")),
        ("Local Day", highlights.get("localDay")),
        ("Next 24h", highlights.get("rolling24Hours")),
    )
    lines: list[str] = []
    for title, result in sections:
        lines.append(title)
        lines.append(format_aspect_highlight(result if isinstance(result, Mapping) else None))
        lines.append("")
    return "\n".join(lines).strip()


def _analysis_score_band(score: int) -> str:
    if score >= 90:
        return "Prime"
    if score >= 80:
        return "Strong"
    if score >= 70:
        return "Workable"
    if score >= 60:
        return "Mixed"
    return "Weak"


def build_analysis_page(
    snapshot: dict[str, object],
    windows: list[dict[str, object]],
    location: object,
    highlights: Mapping[str, object] | None = None,
    search_summary: str = "",
    rejection_summary: Mapping[str, object] | None = None,
) -> str:
    """Full electional analysis page content."""

    traditional_enabled = bool(snapshot.get("traditionalRulesEnabled", True))
    rejection_summary = rejection_summary or {}
    breakdown = snapshot.get("scoreBreakdown", {})
    diagnostics = breakdown.get("diagnostics", {}) if isinstance(breakdown, Mapping) else {}
    strongest = strongest_aspect_result(snapshot)
    timeline = highlights.get("timeline", []) if isinstance(highlights, Mapping) else []
    rolling = highlights.get("rollingTimeline", []) if isinstance(highlights, Mapping) else []
    location_name = getattr(location, "name", "Location unavailable")
    timezone = getattr(location, "timezone", "Timezone unavailable")
    score = int(snapshot.get("score", 0) or 0)
    rules_note = (
        "Traditional dignity/rulership sections are unavailable in True 13-Sign mode; aspect, house, motion, and angularity testimony remain active."
        if not traditional_enabled
        else "Traditional dignity and rulership testimony is enabled for this zodiac framework."
    )
    diagnostic_lines = score_diagnostic_lines(snapshot)
    if isinstance(diagnostics, Mapping):
        diagnostic_lines.extend(
            f"- {label.title()}: {value.get('summary', value.get('band', 'n/a'))}"
            for label, value in diagnostics.items()
            if isinstance(value, Mapping) and label in {"readiness", "cleanliness", "volatility", "confidence"}
        )

    lines = [
        "Analysis",
        "",
        "Executive Judgment And Recommendation",
        f"- Score {score} / {_analysis_score_band(score)}.",
        f"- Recommendation: {snapshot.get('title', 'Electional window')}. {snapshot.get('note', '')}",
        f"- Strongest at displayed time: {format_aspect_highlight(strongest)}",
        "",
        "Current, Local-Day, And Rolling-24-Hour Aspect Highlights",
        format_aspect_highlight_dashboard(highlights),
        "",
        "Local-Day Aspect Timeline",
    ]
    lines.extend(
        f"- {format_aspect_highlight(item)}"
        for item in timeline[:8]
        if isinstance(item, Mapping)
    )
    if len(lines) and lines[-1] == "Local-Day Aspect Timeline":
        lines.append("- No local-day aspect highlights available.")

    lines.extend(["", "Rolling Next-24-Hour Aspect Timeline"])
    rolling_lines = [
        f"- {format_aspect_highlight(item)}"
        for item in rolling[:8]
        if isinstance(item, Mapping)
    ]
    lines.extend(rolling_lines or ["- No rolling-24-hour aspect highlights available."])
    lines.extend(
        [
            "",
            "Aspectarian",
            format_aspectarian(snapshot),
            "",
            "Moon Condition And Timing",
            "\n".join(judgment_context_lines(snapshot, "moonCondition")),
            "",
            "Planet Condition, Motion, Dignity Availability, And Angularity",
            rules_note,
            "\n".join(judgment_context_lines(snapshot, "planetConditionContext")),
            "",
            "Houses, Cusps, Rulers, And Angles",
            "\n".join(angle_testimony_lines(snapshot)),
            "\n".join(judgment_context_lines(snapshot, "houseRulerContext")) if traditional_enabled else "House ruler judgment unavailable in True 13-Sign mode.",
            "",
            "Support, Stress, Readiness, Cleanliness, Volatility, And Confidence",
            f"- Score explanation: {format_score_breakdown(snapshot)}",
            "\n".join(diagnostic_lines),
            "",
            "Electional Rules, Warnings, And Rejected-Window Reasons",
            "\n".join(rule_lines(snapshot)) or "- No active rule warnings/support lines.",
            f"- Search summary: {search_summary or 'Search summary unavailable.'}",
            f"- Rejections: {dict(rejection_summary)}",
            "",
            "Location, Timezone, Zodiac, House System, And Engine Validation",
            f"- Location: {location_name}",
            f"- Timezone: {timezone}",
            f"- Chart time: {snapshot.get('formattedTime', 'time unavailable')}",
            f"- Zodiac: {snapshot['zodiacSystem'].name}",
            f"- House system: {snapshot['houseSystem'].name}",
            f"- Engine: {snapshot.get('engine', 'engine unavailable')}",
            f"- Candidate windows in current search: {len(windows)}",
        ]
    )
    return "\n".join(str(line) for line in lines if line is not None)


def strongest_aspect_analysis_lines(snapshot: dict[str, object]) -> list[str]:
    """Explain the most important aspect with house, dignity, and angle lord context."""

    positions_by_name = _position_by_name(snapshot)
    aspects = snapshot.get("detectedAspects", [])
    if not positions_by_name:
        return ["Strongest Aspect", "- Planet positions are unavailable."]
    if not isinstance(aspects, list) or not aspects:
        return ["Strongest Aspect", "- No selected major aspects in orb."]

    asc_sign = _angle_sign(snapshot, "asc", 1)
    tenth_sign = _angle_sign(snapshot, "mc", 10)
    asc_lord = RULERS.get(asc_sign, "")
    tenth_lord = RULERS.get(tenth_sign, "")
    priority_bodies = {name for name in (asc_lord, tenth_lord, "Moon") if name}
    scored_aspects = [
        (
            _aspect_strength_score(aspect, positions_by_name, priority_bodies),
            aspect,
        )
        for aspect in aspects
        if isinstance(aspect, Mapping)
    ]
    if not scored_aspects:
        return ["Strongest Aspect", "- No readable aspect contacts in the selected chart."]
    strength, strongest = max(scored_aspects, key=lambda item: item[0])
    bodies = strongest.get("bodies", [])
    body_names = [str(body) for body in bodies] if isinstance(bodies, list) else []
    orb_text = strongest.get("orbText") or f"{_float_value(strongest.get('orb')):.2f} deg"
    phase = "applying" if strongest.get("isApplying") else str(strongest.get("phaseLabel") or "phase unknown").lower()
    tone = str(strongest.get("tone") or "mixed")
    role_notes = []
    for name in body_names:
        if name == asc_lord:
            role_notes.append(f"{name} is the ASC lord")
        if name == tenth_lord:
            role_notes.append(f"{name} is the 10th lord")
        if name == "Moon":
            role_notes.append("Moon carries timing and flow")

    lines = [
        "Strongest Aspect",
        f"- {_aspect_label(strongest)} ({tone}); strength {strength:.1f}.",
        f"- Orb: {orb_text}; motion: {phase}.",
    ]
    if role_notes:
        lines.append("- Key role: " + "; ".join(dict.fromkeys(role_notes)) + ".")
    lines.extend(["", "Why It Scores Strongly"])
    for name in body_names:
        planet = positions_by_name.get(name)
        lines.append(f"- {name}: {_planet_condition_phrase(planet)}.")
    lines.extend(
        [
            "",
            "Angles And Lords",
            (
                f"- ASC: {asc_sign or 'n/a'}; ASC lord {asc_lord or 'n/a'} is "
                f"{_planet_condition_phrase(positions_by_name.get(asc_lord))}"
            ),
            (
                f"- 10th/MC: {tenth_sign or 'n/a'}; 10th lord {tenth_lord or 'n/a'} is "
                f"{_planet_condition_phrase(positions_by_name.get(tenth_lord))}"
            ),
        ]
    )
    house_rulers = snapshot.get("houseRulerContext", {})
    if isinstance(house_rulers, Mapping):
        summary = house_rulers.get("summary")
        if summary:
            lines.append(f"- Objective houses: {summary}")
    return lines


def format_aspectarian(snapshot: dict[str, object]) -> str:
    """Render a compact aspectarian-style table for the selected chart."""

    planets = [planet for planet in snapshot.get("positions", []) if isinstance(planet, dict)]
    aspects = snapshot.get("detectedAspects", [])
    if not planets:
        return "Aspectarian unavailable."
    names = [str(planet.get("name", "")) for planet in planets]
    abbreviations = [name[:3].title() for name in names]
    by_pair = {}
    if isinstance(aspects, list):
        for aspect in aspects:
            if not isinstance(aspect, dict):
                continue
            bodies = aspect.get("bodies", [])
            if not isinstance(bodies, list) or len(bodies) != 2:
                continue
            key = frozenset(str(body) for body in bodies)
            by_pair[key] = aspect

    lines = ["Aspectarian", "      " + " ".join(f"{abbr:>4}" for abbr in abbreviations)]
    glyphs = {
        "Conjunction": "Conj",
        "Trine": "Tri",
        "Square": "Sqr",
        "Opposition": "Opp",
        "Sextile": "Sex",
    }
    for row_index, row_name in enumerate(names):
        row = [f"{abbreviations[row_index]:<5}"]
        for column_index, column_name in enumerate(names):
            if column_index <= row_index:
                row.append("   .")
                continue
            aspect = by_pair.get(frozenset((row_name, column_name)))
            if not aspect:
                row.append("   -")
                continue
            marker = glyphs.get(str(aspect.get("aspectName")), str(aspect.get("aspectName", ""))[:3].title())
            tone = "!" if aspect.get("tone") == "stress" else "+" if aspect.get("tone") == "support" else "*"
            row.append(f"{tone}{marker[:3]:>3}")
        lines.append(" ".join(row))

    lines.extend(["", "Legend: + supportive, ! stressful, * mixed.", "", *strongest_aspect_analysis_lines(snapshot)])
    return "\n".join(lines)


def rule_lines(snapshot: dict[str, object]) -> list[str]:
    rule_evaluations = snapshot.get("ruleEvaluations")
    if not isinstance(rule_evaluations, dict):
        return []
    rules = rule_evaluations.get("rules", [])
    if not isinstance(rules, list):
        return []
    lines = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        impact = float(rule.get("scoreImpact", 0))
        lines.append(f"- {rule.get('title', 'Rule')}: {rule.get('detail', '')} ({impact:+.1f})")
    return lines


def score_reason_lines(snapshot: dict[str, object]) -> list[str]:
    breakdown = snapshot.get("scoreBreakdown")
    if not isinstance(breakdown, dict):
        return ["- Score reasons unavailable."]
    reasons = breakdown.get("reasons")
    if not isinstance(reasons, list):
        return ["- Score reasons unavailable."]
    lines = []
    for reason in reasons:
        if not isinstance(reason, dict):
            continue
        value = float(reason.get("value", 0))
        count = reason.get("count")
        detail = f" x{count}" if count is not None else ""
        lines.append(f"- {reason.get('label', reason.get('code', 'Reason'))}{detail}: {value:+.1f}")
    return lines or ["- Score reasons unavailable."]


def format_window_label(rank: int, window: dict[str, object]) -> str:
    support = sum(1 for aspect in window["detectedAspects"] if aspect["tone"] == "support")
    stress = sum(1 for aspect in window["detectedAspects"] if aspect["tone"] == "stress")
    return f"{rank}. {window['time']}  Score {window['score']}  +{support}/!{stress}  {window['title']}"


def format_fixed_star_contact(contact: dict[str, object]) -> str:
    score = float(contact.get("score", 0))
    score_text = f"{score:+.1f}" if score else "0.0"
    limit_text = contact.get("orbLimitText")
    latitude_text = contact.get("latitudeDistanceText")
    precision = contact.get("precision")
    strength = contact.get("contactStrength")
    details = [f"{contact['orbText']} longitude orb"]
    if limit_text:
        details.append(f"limit {limit_text}")
    if latitude_text:
        details.append(f"latitude gap {latitude_text}")
    if precision:
        details.append(str(precision))
    if strength is not None:
        details.append(f"strength {float(strength):.2f}")
    details.extend([str(contact.get("tone", "mixed")), score_text])
    return f"{contact['label']} ({', '.join(details)})"


def build_report_text(
    selected_window: dict[str, object] | None,
    windows: list[dict[str, object]],
    location: LocationPreset | None,
) -> str:
    if not selected_window or not location:
        return "No electional report calculated."

    aspects = "\n".join(f"- {format_aspect_summary(aspect)}" for aspect in selected_window["detectedAspects"])
    fixed_star_contacts = "\n".join(
        f"- {format_fixed_star_contact(contact)}: {contact.get('note', '')}"
        for contact in selected_window.get("fixedStarContacts", [])
    )
    planets = "\n".join(
        (
            f"- {planet['name']}: {format_position(planet)} House {planet['house']} "
            f"({format_dignity_summary(planet)}; {format_motion_summary(planet)})"
        )
        for planet in selected_window["positions"]
    )
    lots = "\n".join(
        (
            f"- {lot['name']}: {format_position(lot)} House {lot['house']} "
            f"({lot['formula']}, {lot['sect']} chart; {lot.get('topic', 'n/a')})"
        )
        for lot in selected_window.get("lots", [])
    )
    nodes = "\n".join(
        (
            f"- {node['name']}: {format_position(node)} House {node['house']} "
            f"({node.get('calculation', 'node calculation')})"
        )
        for node in selected_window.get("lunarNodes", [])
    )
    ranked_windows = "\n".join(format_window_label(index, window) for index, window in enumerate(windows, start=1))
    backend = selected_window.get("calculationBackend", {})
    backend_lines = []
    if isinstance(backend, dict):
        backend_lines.extend(
            [
                f"- Active engine: {backend.get('activeEngine', selected_window['engine'])}",
                f"- Ephemeris path: {backend.get('ephemerisPath', 'n/a')}",
                f"- Ephemeris files: {backend.get('ephemerisFileCount', 'n/a')}",
            ]
        )
        if backend.get("fallbackReason"):
            backend_lines.append(f"- Fallback: {backend['fallbackReason']}")
    notes = "\n".join(f"- {note}" for note in selected_window.get("calculationNotes", []))
    rules = "\n".join(rule_lines(selected_window))
    planetary_hour = selected_window.get("planetaryHour", {})
    planetary_hour_lines = []
    if isinstance(planetary_hour, dict) and planetary_hour.get("available"):
        planetary_hour_lines = [
            f"- Day ruler: {planetary_hour.get('dayRuler')}",
            f"- Hour ruler: {planetary_hour.get('hourRuler')}",
            f"- Hour: {planetary_hour.get('period')} {planetary_hour.get('hourNumber')}",
            f"- Period: {planetary_hour.get('periodStartText')} to {planetary_hour.get('periodEndText')}",
        ]

    return (
        "Electional Software Report\n"
        f"Location: {location.name}\n"
        f"Time: {selected_window['formattedTime']}\n"
        f"Zodiac system: {selected_window['zodiacSystem'].name}\n"
        f"House system: {selected_window['houseSystem'].name}\n"
        f"Ayanamsha: {float(selected_window['ayanamsha']):.3f} deg\n"
        + (
            "Traditional scoring: disabled in True 13-Sign mode\n"
            if not selected_window.get("traditionalRulesEnabled", True)
            else ""
        )
        + f"Score: {selected_window['score']}\n"
        f"Lunar phase: {format_lunar_phase(selected_window)}\n"
        f"Aspect timing: {selected_window.get('timingProfile', {}).get('summary', 'Timing profile unavailable.')}\n"
        f"Score explanation: {format_score_breakdown(selected_window)}\n"
        f"Score accounting:\n{chr(10).join(score_accounting_lines(selected_window))}\n"
        f"Score evaluation:\n{chr(10).join(score_evaluation_lines(selected_window))}\n"
        f"Score diagnostics:\n{chr(10).join(score_diagnostic_lines(selected_window))}\n"
        f"Score reasons:\n{chr(10).join(score_reason_lines(selected_window))}\n"
        f"Angle testimony:\n{chr(10).join(angle_testimony_lines(selected_window))}\n"
        f"Advisor:\n{chr(10).join(advisor_lines(selected_window, None, str(selected_window.get('title', 'Election'))))}\n"
        f"Improvement guide:\n{chr(10).join(improvement_guide_lines(selected_window))}\n"
        f"Planetary hour:\n{chr(10).join(planetary_hour_lines) or '- Planetary hour unavailable.'}\n"
        f"Significators:\n{chr(10).join(judgment_context_lines(selected_window, 'significatorContext'))}\n"
        f"Moon condition:\n{chr(10).join(judgment_context_lines(selected_window, 'moonCondition'))}\n"
        f"House rulers:\n{chr(10).join(judgment_context_lines(selected_window, 'houseRulerContext'))}\n"
        f"Reception:\n{chr(10).join(judgment_context_lines(selected_window, 'receptionContext'))}\n"
        f"Planet condition:\n{chr(10).join(judgment_context_lines(selected_window, 'planetConditionContext'))}\n"
        f"Declination:\n{chr(10).join(judgment_context_lines(selected_window, 'declinationContext'))}\n"
        f"Advanced aspects:\n{chr(10).join(judgment_context_lines(selected_window, 'advancedAspectContext'))}\n"
        f"Fixed stars:\n{chr(10).join(judgment_context_lines(selected_window, 'fixedStarContext'))}\n"
        f"Constellation proportions:\n{chr(10).join(constellation_lines(selected_window))}\n"
        f"Factor explorer:\n{chr(10).join(factor_explorer_lines(selected_window))}\n"
        f"Calculation backend:\n{chr(10).join(backend_lines) or '- Backend unavailable.'}\n"
        f"Calculation notes:\n{notes or '- No calculation warnings.'}\n"
        f"Conditions:\n{chr(10).join(condition_lines(selected_window))}\n"
        f"Rules:\n{rules or '- No active caution/support rules.'}\n"
        f"Window: {selected_window.get('title', 'Electional window')}\n"
        f"Note: {selected_window.get('note', '')}\n\n"
        f"Ranked Windows:\n{ranked_windows}\n\n"
        f"Aspects:\n{aspects or '- No selected major aspects in orb.'}\n\n"
        f"Aspect strength:\n{chr(10).join(strongest_aspect_analysis_lines(selected_window))}\n\n"
        f"Aspectarian:\n{format_aspectarian(selected_window)}\n\n"
        f"Fixed Star Contacts:\n{fixed_star_contacts or '- No fixed-star conjunctions within the diagnostic star orb.'}\n\n"
        f"Lunar Nodes:\n{nodes or '- No lunar nodes calculated.'}\n\n"
        f"Lots:\n{lots or '- No lots calculated.'}\n\n"
        f"Planets:\n{planets}\n"
    )
