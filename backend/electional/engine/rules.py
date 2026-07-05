"""Pure-Python electional rule evaluations."""

from __future__ import annotations

from typing import Mapping, Sequence

from ..aspects import angular_distance, format_orb
from ..judgment import judgment_rule_factors

NAKSHATRAS = (
    "Ashwini",
    "Bharani",
    "Krittika",
    "Rohini",
    "Mrigashira",
    "Ardra",
    "Punarvasu",
    "Pushya",
    "Ashlesha",
    "Magha",
    "Purva Phalguni",
    "Uttara Phalguni",
    "Hasta",
    "Chitra",
    "Swati",
    "Vishakha",
    "Anuradha",
    "Jyeshtha",
    "Mula",
    "Purva Ashadha",
    "Uttara Ashadha",
    "Shravana",
    "Dhanishta",
    "Shatabhisha",
    "Purva Bhadrapada",
    "Uttara Bhadrapada",
    "Revati",
)

TITHI_NAMES = (
    "Pratipada",
    "Dvitiya",
    "Tritiya",
    "Chaturthi",
    "Panchami",
    "Shashthi",
    "Saptami",
    "Ashtami",
    "Navami",
    "Dashami",
    "Ekadashi",
    "Dwadashi",
    "Trayodashi",
    "Chaturdashi",
    "Purnima",
    "Pratipada",
    "Dvitiya",
    "Tritiya",
    "Chaturthi",
    "Panchami",
    "Shashthi",
    "Saptami",
    "Ashtami",
    "Navami",
    "Dashami",
    "Ekadashi",
    "Dwadashi",
    "Trayodashi",
    "Chaturdashi",
    "Amavasya",
)

SOLAR_RULE_BODIES = {"Mercury", "Venus", "Mars", "Jupiter", "Saturn"}


def nakshatra_for_longitude(longitude: float) -> dict[str, object]:
    span = 360 / 27
    normalized = longitude % 360
    index = int(normalized // span)
    position = normalized - index * span
    pada = int(position // (span / 4)) + 1
    return {
        "name": NAKSHATRAS[index],
        "index": index + 1,
        "pada": min(4, pada),
        "degreeIntoNakshatra": position,
    }


def tithi_from_phase(phase_angle: float) -> dict[str, object]:
    normalized = phase_angle % 360
    index = int(normalized // 12)
    paksha = "Shukla" if index < 15 else "Krishna"
    return {
        "name": TITHI_NAMES[index],
        "number": index + 1,
        "paksha": paksha,
        "phaseAngle": normalized,
    }


def lunar_rule_context(positions: Sequence[Mapping[str, object]], lunar_phase: Mapping[str, object]) -> dict[str, object]:
    moon = next((planet for planet in positions if planet.get("name") == "Moon"), None)
    if not moon:
        return {}
    return {
        "nakshatra": nakshatra_for_longitude(float(moon["longitude"])),
        "tithi": tithi_from_phase(float(lunar_phase.get("phaseAngle", 0))),
    }


def solar_condition_for_body(body: Mapping[str, object], sun: Mapping[str, object]) -> dict[str, object]:
    separation = angular_distance(float(body["longitude"]), float(sun["longitude"]))
    name = str(body["name"])
    if separation <= 0.283333:
        return {
            "id": f"{name.lower()}-cazimi",
            "category": "solar-condition",
            "severity": "support",
            "title": f"{name} cazimi",
            "body": name,
            "scoreImpact": 5.0,
            "detail": f"{name} is in the heart of the Sun ({format_orb(separation)}), a rare empowerment condition.",
        }
    if separation <= 8.5:
        return {
            "id": f"{name.lower()}-combust",
            "category": "solar-condition",
            "severity": "warning",
            "title": f"{name} combust",
            "body": name,
            "scoreImpact": -5.0,
            "detail": f"{name} is combust the Sun ({format_orb(separation)}), weakening its ability to act cleanly.",
        }
    if separation <= 15:
        return {
            "id": f"{name.lower()}-under-beams",
            "category": "solar-condition",
            "severity": "caution",
            "title": f"{name} under beams",
            "body": name,
            "scoreImpact": -2.0,
            "detail": f"{name} is under the Sun's beams ({format_orb(separation)}), reducing visibility and clarity.",
        }
    return {
        "id": f"{name.lower()}-clear-of-beams",
        "category": "solar-condition",
        "severity": "info",
        "title": f"{name} clear of beams",
        "body": name,
        "scoreImpact": 0.0,
        "detail": f"{name} is clear of the Sun's beams ({format_orb(separation)}).",
    }


def evaluate_electional_rules(
    positions: Sequence[Mapping[str, object]],
    lunar_phase: Mapping[str, object],
    zodiac_system_id: str,
    planetary_hour: Mapping[str, object] | None = None,
    constellation_context: Mapping[str, object] | None = None,
    judgment_contexts: Mapping[str, Mapping[str, object]] | None = None,
    traditional_rules_enabled: bool = True,
) -> dict[str, object]:
    by_name = {str(planet.get("name")): planet for planet in positions}
    sun = by_name.get("Sun")
    solar_rules = []
    if sun:
        for name in ("Mercury", "Venus", "Mars", "Jupiter", "Saturn"):
            body = by_name.get(name)
            if body:
                solar_rules.append(solar_condition_for_body(body, sun))

    lunar_context = lunar_rule_context(positions, lunar_phase)
    rules = [rule for rule in solar_rules if rule["severity"] != "info"]
    phase_name = str(lunar_phase.get("name", ""))
    if phase_name in {"New Moon", "Full Moon"}:
        rules.append(
            {
                "id": "lunation-turning-point",
                "category": "moon",
                "severity": "caution",
                "title": f"{phase_name} turning point",
                "body": "Moon",
                "scoreImpact": -1.0,
                "detail": f"{phase_name} is powerful but unstable for elections that need steady development.",
            }
        )

    if isinstance(planetary_hour, Mapping) and planetary_hour.get("available"):
        hour_ruler = str(planetary_hour.get("hourRuler", ""))
        impact = float(planetary_hour.get("scoreImpact", 0))
        if impact:
            severity = "support" if impact > 0 else "caution"
            rules.append(
                {
                    "id": f"planetary-hour-{hour_ruler.lower()}",
                    "category": "planetary-hour",
                    "severity": severity,
                    "title": f"{hour_ruler} planetary hour",
                    "body": hour_ruler,
                    "scoreImpact": impact,
                    "detail": (
                        f"The selected moment falls in the {hour_ruler} planetary hour "
                        f"during the {planetary_hour.get('period')} period."
                    ),
                }
            )

    if isinstance(constellation_context, Mapping):
        rising = constellation_context.get("rising", {})
        if isinstance(rising, Mapping):
            tempo = rising.get("tempo", {})
            if isinstance(tempo, Mapping) and float(tempo.get("scoreImpact", 0)):
                impact = float(tempo.get("scoreImpact", 0))
                label = str(tempo.get("label", "tempo"))
                rules.append(
                    {
                        "id": f"ascensional-tempo-{label}",
                        "category": "ascensional-proportion",
                        "severity": "support" if impact > 0 else "caution",
                        "title": f"Ascendant rising tempo: {label}",
                        "body": "ASC",
                        "scoreImpact": impact,
                        "detail": (
                            f"The Ascendant is moving about {float(rising.get('ascendantSpeedDegPerHour', 0)):.1f} deg/hour; "
                            f"{tempo.get('summary', 'ascensional tempo noted')}."
                        ),
                    }
                )
            span_context = rising.get("spanContext", {})
            asc_constellation = rising.get("ascendantConstellation", {})
            if isinstance(span_context, Mapping) and float(span_context.get("scoreImpact", 0)):
                impact = float(span_context.get("scoreImpact", 0))
                label = str(span_context.get("label", "span"))
                rules.append(
                    {
                        "id": f"ascendant-constellation-span-{label}",
                        "category": "constellation-proportion",
                        "severity": "support" if impact > 0 else "caution",
                        "title": f"ASC constellation span: {label}",
                        "body": "ASC",
                        "scoreImpact": impact,
                        "detail": (
                            f"The Ascendant is in {asc_constellation.get('name', 'its constellation')} "
                            f"({float(asc_constellation.get('spanDegrees', 0)):.1f} deg wide); "
                            f"{span_context.get('summary', 'constellation span noted')}."
                        ),
                    }
                )

    if traditional_rules_enabled and isinstance(judgment_contexts, Mapping):
        rules.extend(judgment_rule_factors(judgment_contexts))

    return {
        "zodiacSystemId": zodiac_system_id,
        "traditionalRulesEnabled": traditional_rules_enabled,
        "traditionalRulesNote": (
            "Traditional rulership and dignity rules are disabled in True 13-Sign mode."
            if not traditional_rules_enabled
            else ""
        ),
        "lunarContext": lunar_context,
        "planetaryHour": dict(planetary_hour or {}),
        "constellationContext": dict(constellation_context or {}),
        "judgmentContexts": dict(judgment_contexts or {}),
        "solarConditions": solar_rules,
        "rules": rules,
        "scoreImpact": sum(float(rule.get("scoreImpact", 0)) for rule in rules),
    }


def rule_score(rule_evaluations: Mapping[str, object] | None) -> float:
    if not isinstance(rule_evaluations, Mapping):
        return 0.0
    return float(rule_evaluations.get("scoreImpact", 0))

