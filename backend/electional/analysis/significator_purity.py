"""Score the purity of key electional significators."""

from __future__ import annotations

from typing import Mapping, Sequence

from .helpers import (
    BAD_HOUSES,
    applying_stress_to,
    detected_aspects_for,
    dignity_score,
    moon_non_void,
    natural_significators_for,
    position_by_name,
    profile_confidence,
    solar_phase,
    clamp_score,
)
from .models import PlanetRoleProfile, SignificatorPurityProfile


def build_significator_purity_profiles(
    snapshot: Mapping[str, object],
    role_profiles: Sequence[PlanetRoleProfile],
    objective: str | None = None,
) -> list[SignificatorPurityProfile]:
    objective_name = str(objective or snapshot.get("objective") or "Launch or publish")
    by_name = position_by_name(snapshot.get("positions", []) if isinstance(snapshot.get("positions"), Sequence) else [])
    role_map = {profile.planet: profile for profile in role_profiles}
    key_planets = _key_significators(snapshot, role_profiles, objective_name)
    purity_profiles: list[SignificatorPurityProfile] = []

    for planet_name in key_planets:
        planet = by_name.get(planet_name)
        role_profile = role_map.get(planet_name)
        if planet is None or role_profile is None:
            purity_profiles.append(
                SignificatorPurityProfile(
                    planet=planet_name,
                    purity_score=None,
                    purity_band="unknown",
                    summary=f"{planet_name}: insufficient chart data to judge purity.",
                    positive_factors=(),
                    negative_factors=(),
                    confidence=profile_confidence(warnings=[f"Missing data for {planet_name}."], missing_required=1),
                    warnings=(f"Missing data for {planet_name}.",),
                )
            )
            continue

        positives: list[str] = []
        negatives: list[str] = []
        warnings: list[str] = list(role_profile.warnings)
        score = 50.0

        dignity = dignity_score(planet)
        if dignity >= 4:
            positives.append("dignified")
            score += 18
        elif dignity >= 1:
            positives.append("some dignity")
            score += 8
        elif dignity <= -4:
            negatives.append("debilitated dignity")
            score -= 18
        elif dignity < 0:
            negatives.append("weak dignity")
            score -= 8

        house = int(planet.get("house", 0) or 0)
        if planet.get("isAngular"):
            positives.append("angular")
            score += 12
        elif house in BAD_HOUSES:
            negatives.append(f"placed in {house}th house")
            score -= 14
        elif house in {3, 6, 9, 12}:
            negatives.append("cadent")
            score -= 10

        if planet.get("isRetrograde"):
            negatives.append("retrograde")
            score -= 12
        else:
            positives.append("direct")
            score += 4

        phase = solar_phase(planet)
        if phase == "combust":
            negatives.append("combust")
            score -= 18
        elif phase == "under beams":
            negatives.append("under beams")
            score -= 12

        roles = set(role_profile.roles)
        if "natural_benefic" in roles:
            positives.append("natural benefic")
            score += 8
        if "functional_benefic" in roles and "natural_malefic" in roles:
            positives.append("matter-relevant malefic")
            score += 10
        if "functional_malefic" in roles:
            negatives.append("bad-house contamination")
            score -= 16
        if "election_bad_house_lord" in roles:
            negatives.append("rules bad house")
            score -= 12
        if "lord_of_matter" in roles:
            positives.append("controls the matter")
            score += 10
        if "lord_of_ascendant" in roles:
            positives.append("supports the ascendant side")
            score += 8

        if applying_stress_to(snapshot, planet_name):
            negatives.append("applying to malefic or stress")
            score -= 12
        if _applying_to_benefic(snapshot, planet_name):
            positives.append("applying to benefic support")
            score += 8
        if _supports_asc_or_matter(snapshot, planet_name, role_profiles):
            positives.append("supports key significators")
            score += 6

        if planet_name == "Moon":
            if moon_non_void(snapshot):
                positives.append("Moon not void")
                score += 8
            else:
                negatives.append("void Moon")
                score -= 20
        if _near_malefic_angle(snapshot, planet_name):
            negatives.append("near angular malefic pressure")
            score -= 10

        score = clamp_score(score)
        band = _purity_band(score)
        summary = _purity_summary(planet_name, score, band, positives, negatives)
        confidence = profile_confidence(warnings=warnings, missing_required=0)
        purity_profiles.append(
            SignificatorPurityProfile(
                planet=planet_name,
                purity_score=score,
                purity_band=band,
                summary=summary,
                positive_factors=tuple(positives[:6]),
                negative_factors=tuple(negatives[:6]),
                confidence=confidence,
                warnings=tuple(dict.fromkeys(warnings)),
            )
        )

    return purity_profiles


def _key_significators(
    snapshot: Mapping[str, object],
    role_profiles: Sequence[PlanetRoleProfile],
    objective: str,
) -> list[str]:
    names = ["Moon"]
    for profile in role_profiles:
        roles = set(profile.roles)
        if roles.intersection(
            {
                "lord_of_ascendant",
                "lord_of_matter",
                "lord_of_hour",
                "lord_of_year",
                "opponent_lord",
                "authority_lord",
                "outcome_lord",
            }
        ):
            names.append(profile.planet)
    names.extend(natural_significators_for(objective))
    names.extend(["Venus", "Jupiter", "Mars", "Saturn"])
    return list(dict.fromkeys(name for name in names if name))


def _applying_to_benefic(snapshot: Mapping[str, object], planet_name: str) -> bool:
    for aspect in detected_aspects_for(snapshot, planet_name):
        if aspect.get("tone") != "support" or not aspect.get("isApplying"):
            continue
        bodies = {str(body) for body in aspect.get("bodies", []) if body}
        if bodies.intersection({"Venus", "Jupiter"}) and planet_name in bodies:
            return True
    return False


def _supports_asc_or_matter(
    snapshot: Mapping[str, object],
    planet_name: str,
    role_profiles: Sequence[PlanetRoleProfile],
) -> bool:
    target_names = {
        profile.planet
        for profile in role_profiles
        if {"lord_of_ascendant", "lord_of_matter"}.intersection(profile.roles)
    }
    target_names.discard(planet_name)
    return bool(target_names) and _applying_to_targets(snapshot, planet_name, target_names)


def _applying_to_targets(snapshot: Mapping[str, object], planet_name: str, targets: set[str]) -> bool:
    for aspect in detected_aspects_for(snapshot, planet_name):
        if aspect.get("tone") != "support" or not aspect.get("isApplying"):
            continue
        bodies = {str(body) for body in aspect.get("bodies", []) if body}
        if planet_name in bodies and bodies.intersection(targets):
            return True
    return False


def _near_malefic_angle(snapshot: Mapping[str, object], planet_name: str) -> bool:
    for position in snapshot.get("positions", []):
        if not isinstance(position, Mapping) or position.get("name") not in {"Mars", "Saturn"}:
            continue
        if not position.get("isAngular"):
            continue
        closest = position.get("closestAngle", {})
        try:
            if isinstance(closest, Mapping) and float(closest.get("distance", 99) or 99) <= 4.0 and planet_name != position.get("name"):
                return True
        except (TypeError, ValueError):
            continue
    return False


def _purity_band(score: int) -> str:
    if score >= 85:
        return "clean"
    if score >= 70:
        return "useful"
    if score >= 50:
        return "mixed"
    if score >= 30:
        return "corrupted"
    return "hostile"


def _purity_summary(
    planet_name: str,
    score: int,
    band: str,
    positives: Sequence[str],
    negatives: Sequence[str],
) -> str:
    if positives and negatives:
        return f"{planet_name} is {band}: {', '.join(positives[:2])}, but {', '.join(negatives[:2])}."
    if positives:
        return f"{planet_name} is {band}: {', '.join(positives[:3])}."
    if negatives:
        return f"{planet_name} is {band}: {', '.join(negatives[:3])}."
    return f"{planet_name} purity is {band} at {score}/100."
