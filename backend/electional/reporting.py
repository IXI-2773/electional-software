"""Text formatting helpers for reports and backend explanations."""

from __future__ import annotations

BENEFIC_NAMES = {"Venus", "Jupiter"}
CHALLENGING_NAMES = {"Mars", "Saturn"}

from .chart import format_angle, format_position
from .locations import LocationPreset
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
    return f"{motion.get('label', 'Motion unknown')} {daily_change:+.2f} deg/day"


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
        f"Score: {snapshot['score']}\n"
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
        + ("\n".join(star_contact_lines) if star_contact_lines else "- No fixed-star conjunctions within 1 degree.")
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
    "receptionContext": "Reception",
    "planetConditionContext": "Planet Condition",
    "advancedAspectContext": "Advanced Aspects",
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


def factor_explorer_lines(snapshot: dict[str, object], baseline: dict[str, object] | None = None) -> list[str]:
    lines = ["Factor Explorer", f"Score: {snapshot.get('score', 'n/a')}"]
    if baseline and baseline is not snapshot:
        try:
            delta = int(snapshot.get("score", 0)) - int(baseline.get("score", 0))
            lines.append(f"Compared with search-start chart: {delta:+d} points.")
        except (TypeError, ValueError):
            lines.append("Compared with search-start chart: n/a.")
    for context_key, label in JUDGMENT_CONTEXT_LABELS.items():
        if context_key == "constellationContext":
            context = snapshot.get(context_key)
            rising = context.get("rising", {}) if isinstance(context, dict) else {}
            impact = float(rising.get("scoreImpact", 0)) if isinstance(rising, dict) else 0.0
        else:
            context = snapshot.get(context_key)
            impact = float(context.get("scoreImpact", 0)) if isinstance(context, dict) else 0.0
        lines.extend(["", f"{label} ({impact:+.1f})"])
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

    lines.extend(["", "Legend: + supportive, ! stressful, * mixed."])
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
    return f"{contact['label']} ({contact['orbText']} orb, {contact.get('tone', 'mixed')}, {score_text})"


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
        f"Score: {selected_window['score']}\n"
        f"Lunar phase: {format_lunar_phase(selected_window)}\n"
        f"Aspect timing: {selected_window.get('timingProfile', {}).get('summary', 'Timing profile unavailable.')}\n"
        f"Score explanation: {format_score_breakdown(selected_window)}\n"
        f"Score accounting:\n{chr(10).join(score_accounting_lines(selected_window))}\n"
        f"Score evaluation:\n{chr(10).join(score_evaluation_lines(selected_window))}\n"
        f"Score diagnostics:\n{chr(10).join(score_diagnostic_lines(selected_window))}\n"
        f"Score reasons:\n{chr(10).join(score_reason_lines(selected_window))}\n"
        f"Planetary hour:\n{chr(10).join(planetary_hour_lines) or '- Planetary hour unavailable.'}\n"
        f"Significators:\n{chr(10).join(judgment_context_lines(selected_window, 'significatorContext'))}\n"
        f"Moon condition:\n{chr(10).join(judgment_context_lines(selected_window, 'moonCondition'))}\n"
        f"House rulers:\n{chr(10).join(judgment_context_lines(selected_window, 'houseRulerContext'))}\n"
        f"Reception:\n{chr(10).join(judgment_context_lines(selected_window, 'receptionContext'))}\n"
        f"Planet condition:\n{chr(10).join(judgment_context_lines(selected_window, 'planetConditionContext'))}\n"
        f"Advanced aspects:\n{chr(10).join(judgment_context_lines(selected_window, 'advancedAspectContext'))}\n"
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
        f"Aspectarian:\n{format_aspectarian(selected_window)}\n\n"
        f"Fixed Star Contacts:\n{fixed_star_contacts or '- No fixed-star conjunctions within 1 degree.'}\n\n"
        f"Lunar Nodes:\n{nodes or '- No lunar nodes calculated.'}\n\n"
        f"Lots:\n{lots or '- No lots calculated.'}\n\n"
        f"Planets:\n{planets}\n"
    )
