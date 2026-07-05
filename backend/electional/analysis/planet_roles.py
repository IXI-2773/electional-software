"""Resolve planet roles for advanced election analysis."""

from __future__ import annotations

from typing import Mapping, Sequence

from .helpers import (
    BAD_HOUSES,
    TRADITIONAL_PLANETS,
    house_ruler,
    matter_houses_for,
    moon_non_void,
    natural_role,
    natural_significators_for,
    objective_mode,
    position_by_name,
    profile_confidence,
    solar_phase,
)
from .models import PlanetRoleProfile


OBJECTIVE_ROLE_MAP: dict[str, tuple[str, ...]] = {
    "exam": ("communication_lord", "exam_lord"),
    "legal_dispute": ("legal_lord",),
    "business_launch": ("money_lord", "authority_lord"),
    "money_business": ("money_lord", "resource_lord"),
    "message_contact": ("communication_lord",),
    "relationship": ("relationship_lord",),
    "travel": ("travel_lord",),
}


def resolve_planet_roles(snapshot: Mapping[str, object], objective: str | None = None) -> list[PlanetRoleProfile]:
    objective_name = str(objective or snapshot.get("objective") or "Launch or publish")
    positions = snapshot.get("positions", [])
    house_cusps = snapshot.get("houseCusps", [])
    by_name = position_by_name(positions if isinstance(positions, Sequence) else [])
    warnings: list[str] = []
    if not isinstance(house_cusps, Sequence) or not house_cusps:
        warnings.append("Missing house cusps: cannot resolve full house lordship.")

    asc_lord = house_ruler(house_cusps, 1) if isinstance(house_cusps, Sequence) else None
    moon = by_name.get("Moon")
    moon_sign = str((moon or {}).get("zodiac", {}).get("sign", "")) if isinstance((moon or {}).get("zodiac"), Mapping) else ""
    lord_of_moon = house_ruler(
        [{"house": 1, "zodiac": {"sign": moon_sign}}] if moon_sign else [],
        1,
    ) if moon_sign else None
    planetary_hour = snapshot.get("planetaryHour", {})
    hour_lord = str(planetary_hour.get("hourRuler") or "") if isinstance(planetary_hour, Mapping) else ""
    matter_context = snapshot.get("matterLordContext", {})
    year_lord = str(matter_context.get("yearLord") or "Sun") if isinstance(matter_context, Mapping) else "Sun"
    matter_houses = matter_houses_for(objective_name)
    matter_lords = {house_ruler(house_cusps, house) for house in matter_houses} if isinstance(house_cusps, Sequence) else set()
    natural_significators = set(natural_significators_for(objective_name))
    mode = objective_mode(objective_name)
    lord_of_7th = house_ruler(house_cusps, 7) if isinstance(house_cusps, Sequence) else None
    lord_of_10th = house_ruler(house_cusps, 10) if isinstance(house_cusps, Sequence) else None
    lord_of_4th = house_ruler(house_cusps, 4) if isinstance(house_cusps, Sequence) else None
    lord_of_2nd = house_ruler(house_cusps, 2) if isinstance(house_cusps, Sequence) else None
    lord_of_3rd = house_ruler(house_cusps, 3) if isinstance(house_cusps, Sequence) else None
    lord_of_9th = house_ruler(house_cusps, 9) if isinstance(house_cusps, Sequence) else None

    profiles: list[PlanetRoleProfile] = []
    for planet_name in tuple(by_name) if by_name else TRADITIONAL_PLANETS:
        planet = by_name.get(planet_name)
        role_tags: list[str] = []
        local_warnings = list(warnings)

        natural = natural_role(planet_name)
        if natural:
            role_tags.append(natural)
        if planet_name in {"Sun", "Moon"}:
            role_tags.append("luminary")
        elif planet_name in {"Mercury", "Venus", "Mars"}:
            role_tags.append("personal_planet")
        elif planet_name in {"Jupiter", "Saturn"}:
            role_tags.append("social_planet")
        else:
            role_tags.append("outer_planet")

        if planet_name == asc_lord:
            role_tags.append("lord_of_ascendant")
        if planet_name == lord_of_moon:
            role_tags.append("lord_of_moon")
        if planet_name == hour_lord:
            role_tags.append("lord_of_hour")
        if planet_name == year_lord:
            role_tags.append("lord_of_year")

        bad_house_hits = 0
        for house in range(1, 13):
            ruler = house_ruler(house_cusps, house) if isinstance(house_cusps, Sequence) else None
            if ruler != planet_name:
                continue
            if house != 1:
                role_tags.append(f"lord_of_{house}{_house_suffix(house)}")
            if house in BAD_HOUSES:
                role_tags.append("election_bad_house_lord")
                bad_house_hits += 1
        if planet_name in matter_lords:
            role_tags.append("lord_of_matter")
        if planet_name == lord_of_7th:
            role_tags.append("opponent_lord")
        if planet_name == lord_of_10th:
            role_tags.extend(["authority_lord", "outcome_lord" if mode == "business_launch" else ""])
        if planet_name == lord_of_4th:
            role_tags.append("outcome_lord")
        if planet_name == lord_of_2nd:
            role_tags.extend(["resource_lord", "money_lord"])
        if planet_name == lord_of_3rd:
            role_tags.append("communication_lord")
        if planet_name == lord_of_9th:
            role_tags.extend(["exam_lord", "legal_lord", "travel_lord"])
        if planet_name == lord_of_7th and mode == "relationship":
            role_tags.append("relationship_lord")
        if planet_name in natural_significators:
            role_tags.extend(OBJECTIVE_ROLE_MAP.get(mode, ()))

        if bad_house_hits:
            role_tags.append("natal_bad_house_lord")
        if natural == "natural_benefic" and ("election_bad_house_lord" in role_tags or "natal_bad_house_lord" in role_tags):
            role_tags.append("functional_malefic")
        elif natural == "natural_malefic" and "lord_of_matter" in role_tags:
            role_tags.append("functional_benefic")
        elif planet_name == "Mercury":
            if solar_phase(planet) in {"combust", "under beams"} or bool((planet or {}).get("isRetrograde")):
                role_tags.append("functional_malefic")
            elif mode in {"exam", "message_contact", "money_business", "business_launch"}:
                role_tags.append("functional_benefic")
        elif natural == "natural_benefic":
            role_tags.append("functional_benefic")
        elif natural == "natural_malefic":
            role_tags.append("functional_malefic")

        if planet is None:
            local_warnings.append(f"Missing planet data for {planet_name}.")
        if planet_name == "Moon" and not moon_non_void(snapshot):
            local_warnings.append("Moon is void or uncertain.")
        if planet_name == "Mercury" and mode == "exam":
            role_tags.append("exam_lord")
        if planet_name == "Mercury" and mode == "message_contact":
            role_tags.append("communication_lord")

        role_tags = [tag for tag in dict.fromkeys(tag for tag in role_tags if tag)]
        summary = _role_summary(planet_name, role_tags, planet, objective_name)
        confidence = profile_confidence(warnings=local_warnings, missing_required=0 if planet is not None else 1)
        profiles.append(
            PlanetRoleProfile(
                planet=planet_name,
                roles=tuple(role_tags),
                role_summary=summary,
                confidence=confidence,
                warnings=tuple(dict.fromkeys(local_warnings)),
            )
        )
    return profiles


def _house_suffix(house: int) -> str:
    return {
        1: "st",
        2: "nd",
        3: "rd",
    }.get(house if house < 20 else house % 10, "th")


def _role_summary(
    planet_name: str,
    roles: Sequence[str],
    planet: Mapping[str, object] | None,
    objective: str,
) -> str:
    summary_parts: list[str] = []
    if "natural_benefic" in roles:
        summary_parts.append("Natural benefic")
    elif "natural_malefic" in roles:
        summary_parts.append("Natural malefic")
    elif "luminary" in roles:
        summary_parts.append("Luminary")
    if "lord_of_ascendant" in roles:
        summary_parts.append("Lord of Ascendant")
    if "lord_of_matter" in roles:
        summary_parts.append("Lord of Matter")
    if any(role.endswith("_lord") and not role.startswith("lord_of_") for role in roles):
        summary_parts.append("objective-specific significator")
    if "functional_malefic" in roles and "natural_benefic" in roles:
        summary_parts.append("contaminated by bad-house rulership")
    if "functional_benefic" in roles and "natural_malefic" in roles:
        summary_parts.append("contextually useful despite natural malefic status")
    if planet_name == "Mercury" and "exam_lord" in roles:
        summary_parts.append(f"key for {objective.lower()}")
    if planet is not None and solar_phase(planet) in {"combust", "under beams"}:
        summary_parts.append(f"solar damage: {solar_phase(planet)}")
    return ", ".join(summary_parts) if summary_parts else f"{planet_name} roles resolved."
