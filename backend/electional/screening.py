"""Calculated screening summaries for electional utility dialogs."""

from __future__ import annotations

from datetime import timedelta

from .aspects import ASPECT_BY_ID, angular_distance, format_orb
from .chart import build_snapshot_for_moment, format_position
from .judgment import solar_visibility_diagnostic
from .locations import LocationPreset


def solar_elongation_summary(snapshot: dict[str, object]) -> list[str]:
    positions = {str(planet["name"]): planet for planet in snapshot["positions"]}
    sun = positions.get("Sun")
    if not sun:
        return ["Sun position is unavailable."]

    condition_context = snapshot.get("planetConditionContext", {})
    conditions = {
        str(condition.get("name")): condition
        for condition in condition_context.get("conditions", [])
        if isinstance(condition_context, dict) and isinstance(condition, dict)
    }
    lines = [f"Sun: {format_position(sun)}", "", "Body          Separation   Side      Phase                Note"]
    for name in ("Mercury", "Venus", "Mars", "Jupiter", "Saturn"):
        planet = positions.get(name)
        if not planet:
            continue
        condition = conditions.get(name, {})
        diagnostic = condition.get("visibilityDiagnostic", {}) if isinstance(condition, dict) else {}
        if not isinstance(diagnostic, dict) or not diagnostic:
            signed_from_sun = ((float(planet["longitude"]) - float(sun["longitude"]) + 180) % 360) - 180
            diagnostic = solar_visibility_diagnostic(name, angular_distance(float(sun["longitude"]), float(planet["longitude"])), signed_from_sun)
        separation = float(diagnostic.get("solarSeparation", angular_distance(float(sun["longitude"]), float(planet["longitude"]))))
        side = str(diagnostic.get("side", "n/a"))
        label = str(diagnostic.get("label", "n/a"))
        note = str(diagnostic.get("note", "diagnostic unavailable"))
        lines.append(f"{name:<13} {separation:>5.1f} deg     {side:<8} {label:<20} {note}")
    return lines


def moon_void_course_summary(
    start_snapshot: dict[str, object],
    location: LocationPreset,
    selected_aspects: list[str],
) -> list[str]:
    preset = start_snapshot["preset"]
    start = start_snapshot["date"]
    current_moon = next(planet for planet in start_snapshot["positions"] if planet["name"] == "Moon")
    current_sign = str(current_moon["zodiac"]["sign"])
    best_contact: dict[str, object] | None = None

    for minutes in range(10, 60 * 72 + 1, 10):
        moment = start + timedelta(minutes=minutes)
        snapshot = build_snapshot_for_moment(
            moment,
            location,
            preset,
            selected_aspects,
            start_snapshot["zodiacSystem"].id,
            start_snapshot["houseSystem"].id,
        )
        moon = next(planet for planet in snapshot["positions"] if planet["name"] == "Moon")
        if moon["zodiac"]["sign"] != current_sign:
            exit_text = snapshot["formattedTime"]
            if not best_contact:
                return [
                    f"Moon is void of course in {current_sign}.",
                    f"No selected major Moon aspect perfects before sign change at {exit_text}.",
                ]
            return [
                f"Moon is not void of course in {current_sign}.",
                (
                    f"Next selected Moon contact: {best_contact['label']} near {best_contact['time']} "
                    f"with {best_contact['orbText']} orb."
                ),
                f"Moon leaves {current_sign} at {exit_text}.",
            ]

        moon_longitude = float(moon["longitude"])
        for planet in snapshot["positions"]:
            if planet["name"] == "Moon":
                continue
            distance = angular_distance(moon_longitude, float(planet["longitude"]))
            for aspect_id in selected_aspects:
                aspect = ASPECT_BY_ID.get(aspect_id)
                if not aspect:
                    continue
                orb = abs(distance - aspect.angle)
                if orb <= 0.35:
                    return [
                        f"Moon is not void of course in {current_sign}.",
                        (
                            f"Next selected Moon contact: Moon {aspect.name.lower()} {planet['name']} "
                            f"near {snapshot['formattedTime']} with {format_orb(orb)} orb."
                        ),
                    ]
                if best_contact is None or orb < float(best_contact["orb"]):
                    best_contact = {
                        "label": f"Moon {aspect.name.lower()} {planet['name']}",
                        "time": snapshot["formattedTime"],
                        "orb": orb,
                        "orbText": format_orb(orb),
                    }

    return [f"Moon stayed in {current_sign} through the scan range. Extend scan later if needed."]
