"""Shared helpers for advanced analysis modules."""

from __future__ import annotations

from typing import Mapping, Sequence

from ..judgment import BENEFICS, MALEFICS, OBJECTIVE_MATTER_TOPICS, RULERS

TRADITIONAL_PLANETS = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn")
BAD_HOUSES = {6, 8, 12}


def position_by_name(positions: Sequence[Mapping[str, object]]) -> dict[str, Mapping[str, object]]:
    return {str(position.get("name")): position for position in positions if isinstance(position, Mapping)}


def house_ruler(house_cusps: Sequence[Mapping[str, object]], house_number: int) -> str | None:
    cusp = next((item for item in house_cusps if int(item.get("house", 0) or 0) == house_number), None)
    zodiac = cusp.get("zodiac") if isinstance(cusp, Mapping) else None
    sign = str(zodiac.get("sign") or "") if isinstance(zodiac, Mapping) else ""
    return RULERS.get(sign)


def dignity_score(planet: Mapping[str, object] | None) -> float:
    dignity = planet.get("dignity") if isinstance(planet, Mapping) else None
    if isinstance(dignity, Mapping):
        try:
            return float(dignity.get("score", 0) or 0)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def solar_phase(planet: Mapping[str, object] | None) -> str:
    solar = planet.get("solarCondition") if isinstance(planet, Mapping) else None
    return str(solar.get("phase") or "") if isinstance(solar, Mapping) else ""


def moon_non_void(snapshot: Mapping[str, object]) -> bool:
    moon_condition = snapshot.get("moonCondition")
    if not isinstance(moon_condition, Mapping):
        return True
    void_data = moon_condition.get("voidOfCourse")
    if not isinstance(void_data, Mapping):
        return True
    return not bool(void_data.get("isVoid"))


def detected_aspects_for(snapshot: Mapping[str, object], planet_name: str) -> list[Mapping[str, object]]:
    matches: list[Mapping[str, object]] = []
    for aspect in snapshot.get("detectedAspects", []):
        if not isinstance(aspect, Mapping):
            continue
        bodies = aspect.get("bodies", [])
        if isinstance(bodies, list) and planet_name in [str(body) for body in bodies]:
            matches.append(aspect)
    return matches


def applying_support_to(snapshot: Mapping[str, object], planet_name: str, targets: Sequence[str] = ()) -> bool:
    allowed = {str(target) for target in targets if target}
    for aspect in detected_aspects_for(snapshot, planet_name):
        if aspect.get("tone") != "support" or not aspect.get("isApplying"):
            continue
        if not allowed:
            return True
        bodies = {str(body) for body in aspect.get("bodies", []) if body}
        if bodies.intersection(allowed):
            return True
    return False


def applying_stress_to(snapshot: Mapping[str, object], planet_name: str, targets: Sequence[str] = ()) -> bool:
    allowed = {str(target) for target in targets if target}
    for aspect in detected_aspects_for(snapshot, planet_name):
        if aspect.get("tone") != "stress" or not aspect.get("isApplying"):
            continue
        if not allowed:
            return True
        bodies = {str(body) for body in aspect.get("bodies", []) if body}
        if bodies.intersection(allowed):
            return True
    return False


def matter_houses_for(objective: str) -> tuple[int, ...]:
    topic = OBJECTIVE_MATTER_TOPICS.get(objective, OBJECTIVE_MATTER_TOPICS.get("Launch or publish", {}))
    return tuple(int(house) for house in topic.get("houses", ()))


def natural_significators_for(objective: str) -> tuple[str, ...]:
    topic = OBJECTIVE_MATTER_TOPICS.get(objective, OBJECTIVE_MATTER_TOPICS.get("Launch or publish", {}))
    return tuple(str(name) for name in topic.get("natural", ()))


def natural_role(name: str) -> str | None:
    if name in BENEFICS:
        return "natural_benefic"
    if name in MALEFICS:
        return "natural_malefic"
    if name in {"Sun", "Moon"}:
        return "luminary"
    return None


def clamp_score(value: float) -> int:
    return max(0, min(100, round(value)))


def objective_mode(objective: str) -> str:
    lowered = str(objective or "").lower()
    if "legal" in lowered or "dispute" in lowered:
        return "legal_dispute"
    if "exam" in lowered or "cert" in lowered:
        return "exam"
    if "message" in lowered or "contact" in lowered:
        return "message_contact"
    if "relationship" in lowered:
        return "relationship"
    if "travel" in lowered:
        return "travel"
    if "money" in lowered or "business" in lowered:
        return "money_business"
    if "launch" in lowered or "publish" in lowered:
        return "business_launch"
    return "general"


def profile_confidence(*, warnings: Sequence[str], missing_required: int = 0) -> float:
    confidence = 0.95 - len(tuple(warnings)) * 0.08 - missing_required * 0.12
    return round(max(0.15, min(0.99, confidence)), 2)
