"""Chart control index for advanced election analysis."""

from __future__ import annotations

from typing import Mapping, Sequence

from .helpers import applying_stress_to, clamp_score, profile_confidence
from .models import ControlIndexReport, ControlSideReport, PlanetRoleProfile, SignificatorPurityProfile


def build_control_index_report(
    snapshot: Mapping[str, object],
    role_profiles: Sequence[PlanetRoleProfile],
    purity_profiles: Sequence[SignificatorPurityProfile],
) -> ControlIndexReport:
    role_map = {profile.planet: profile for profile in role_profiles}
    purity_map = {profile.planet: profile for profile in purity_profiles}
    warnings: list[str] = []

    asc_planets = _planets_for_roles(role_profiles, {"lord_of_ascendant"})
    matter_planets = _planets_for_roles(role_profiles, {"lord_of_matter"})
    user_planets = asc_planets | matter_planets | {"Moon"}
    opponent_planets = _planets_for_roles(role_profiles, {"opponent_lord"})
    authority_planets = _planets_for_roles(role_profiles, {"authority_lord"})
    has_required_user_side = bool(asc_planets)

    if not has_required_user_side:
        warnings.append("Missing Lord of Ascendant: user control cannot be fully judged.")
    user_strength = _side_strength(user_planets, purity_map)
    opponent_strength = _side_strength(opponent_planets, purity_map)
    authority_strength = _side_strength(authority_planets, purity_map)

    score = 50
    supports: list[str] = []
    risks: list[str] = []

    asc_lord = next((planet for planet in user_planets if "lord_of_ascendant" in set(role_map.get(planet, PlanetRoleProfile("", (), "", 0.0)).roles)), "")
    if asc_lord:
        asc_purity = purity_map.get(asc_lord)
        if asc_purity and asc_purity.purity_score is not None:
            score += max(-10, min(14, round((asc_purity.purity_score - 50) * 0.35)))
            if asc_purity.purity_score >= 70:
                supports.append("Lord of Ascendant is usefully placed.")
            elif asc_purity.purity_score < 50:
                risks.append("Lord of Ascendant is weak or corrupted.")
    if user_strength is not None and opponent_strength is not None:
        delta = user_strength - opponent_strength
        score += max(-16, min(16, round(delta * 0.4)))
        if delta >= 10:
            supports.append("User side is stronger than the 7th-house side.")
        elif delta <= -10:
            risks.append("Opponent side is stronger than the Ascendant side.")

    matter_lord = next((planet for planet in user_planets if "lord_of_matter" in set(role_map.get(planet, PlanetRoleProfile("", (), "", 0.0)).roles)), "")
    if matter_lord and not applying_stress_to(snapshot, "Moon", [matter_lord]):
        supports.append("Moon does not directly attack the matter lord.")
    if matter_lord and _moon_supports(snapshot, matter_lord):
        score += 8
        supports.append("Moon supports Lord of Matter.")
    elif opponent_planets and _moon_supports(snapshot, *opponent_planets):
        score -= 10
        risks.append("Moon applies to the opponent side.")

    for role in role_profiles:
        if "natural_malefic" in role.roles and "functional_benefic" not in role.roles:
            purity = purity_map.get(role.planet)
            if purity and purity.purity_score is not None and purity.purity_score < 45 and _is_angular(snapshot, role.planet):
                score -= 10
                risks.append(f"{role.planet} is an uncontrolled angular malefic.")

    if authority_strength is not None and authority_strength >= 70:
        supports.append("Authority side is stable or favorable.")
        score += 4
    elif authority_strength is not None and authority_strength < 45:
        risks.append("Authority side is unstable or hostile.")
        score -= 4

    score = clamp_score(score)
    band = _control_band(score)
    summary = _control_summary(score, band)
    confidence = profile_confidence(warnings=warnings, missing_required=0 if has_required_user_side else 1)
    return ControlIndexReport(
        control_score=score if has_required_user_side else None,
        band=band if has_required_user_side else "unknown",
        summary=summary if has_required_user_side else "Insufficient data to judge chart control.",
        user_side=ControlSideReport(tuple(sorted(user_planets)), user_strength),
        resistance_side=ControlSideReport(tuple(sorted(opponent_planets)), opponent_strength),
        authority_side=ControlSideReport(tuple(sorted(authority_planets)), authority_strength),
        main_supports=tuple(dict.fromkeys(supports))[:4],
        main_risks=tuple(dict.fromkeys(risks))[:4],
        confidence=confidence,
        warnings=tuple(warnings),
    )


def _planets_for_roles(role_profiles: Sequence[PlanetRoleProfile], wanted: set[str]) -> set[str]:
    return {profile.planet for profile in role_profiles if wanted.intersection(profile.roles)}


def _side_strength(planets: set[str], purity_map: Mapping[str, SignificatorPurityProfile]) -> int | None:
    scores = [purity_map[planet].purity_score for planet in planets if planet in purity_map and purity_map[planet].purity_score is not None]
    return round(sum(scores) / len(scores)) if scores else None


def _moon_supports(snapshot: Mapping[str, object], *targets: str) -> bool:
    for aspect in snapshot.get("detectedAspects", []):
        if not isinstance(aspect, Mapping) or aspect.get("tone") != "support" or not aspect.get("isApplying"):
            continue
        bodies = {str(body) for body in aspect.get("bodies", []) if body}
        if "Moon" in bodies and bodies.intersection(set(targets)):
            return True
    return False


def _is_angular(snapshot: Mapping[str, object], planet_name: str) -> bool:
    for position in snapshot.get("positions", []):
        if isinstance(position, Mapping) and position.get("name") == planet_name:
            return bool(position.get("isAngular"))
    return False


def _control_band(score: int) -> str:
    if score >= 80:
        return "user_has_strong_control"
    if score >= 65:
        return "user_has_advantage"
    if score >= 50:
        return "contested"
    if score >= 35:
        return "resistance_has_advantage"
    return "user_lacks_control"


def _control_summary(score: int, band: str) -> str:
    text = {
        "user_has_strong_control": "The election strongly favors user control.",
        "user_has_advantage": "The election gives the user moderate control.",
        "contested": "Control is contested and mixed.",
        "resistance_has_advantage": "Resistance currently has the advantage.",
        "user_lacks_control": "The user lacks control in this chart.",
    }
    return f"{text.get(band, 'Control is mixed.')} ({score}/100)"
