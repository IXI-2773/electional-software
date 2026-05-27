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
    lines.extend(["", "Election Flags", *election_flag_lines(snapshot)])
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
    if aspect.get("phase") == "unknown":
        return f"{aspect['label']} ({aspect['orbText']} orb, phase unknown)"
    return f"{aspect['label']} ({aspect['orbText']} orb, {phase_label.lower()}, {change:+.2f} deg/day)"


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
        f"retrograde pressure {float(breakdown.get('retrogradePressure', 0)):.1f}; "
        f"raw {float(breakdown.get('rawScore', 0)):.1f} -> final {breakdown.get('score', snapshot.get('score', '?'))}."
    )


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


def build_report_text(
    selected_window: dict[str, object] | None,
    windows: list[dict[str, object]],
    location: LocationPreset | None,
) -> str:
    if not selected_window or not location:
        return "No electional report calculated."

    aspects = "\n".join(f"- {format_aspect_summary(aspect)}" for aspect in selected_window["detectedAspects"])
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
    ranked_windows = "\n".join(format_window_label(index, window) for index, window in enumerate(windows, start=1))

    return (
        "Electional Software Report\n"
        f"Location: {location.name}\n"
        f"Time: {selected_window['formattedTime']}\n"
        f"Zodiac system: {selected_window['zodiacSystem'].name}\n"
        f"House system: {selected_window['houseSystem'].name}\n"
        f"Ayanamsha: {float(selected_window['ayanamsha']):.3f} deg\n"
        f"Score: {selected_window['score']}\n"
        f"Lunar phase: {format_lunar_phase(selected_window)}\n"
        f"Score explanation: {format_score_breakdown(selected_window)}\n"
        f"Score reasons:\n{chr(10).join(score_reason_lines(selected_window))}\n"
        f"Conditions:\n{chr(10).join(condition_lines(selected_window))}\n"
        f"Window: {selected_window.get('title', 'Electional window')}\n"
        f"Note: {selected_window.get('note', '')}\n\n"
        f"Ranked Windows:\n{ranked_windows}\n\n"
        f"Aspects:\n{aspects or '- No selected major aspects in orb.'}\n\n"
        f"Lots:\n{lots or '- No lots calculated.'}\n\n"
        f"Planets:\n{planets}\n"
    )
