"""Text formatting helpers for reports and backend explanations."""

from __future__ import annotations

BENEFIC_NAMES = {"Venus", "Jupiter"}
CHALLENGING_NAMES = {"Mars", "Saturn"}

from .chart import format_position
from .locations import LocationPreset


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
        f"Score reasons:\n{chr(10).join(score_reason_lines(selected_window))}\n"
        f"Planetary hour:\n{chr(10).join(planetary_hour_lines) or '- Planetary hour unavailable.'}\n"
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
