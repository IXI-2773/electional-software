"""Opponent and resistance analysis for advanced election logic."""

from __future__ import annotations

from typing import Mapping, Sequence

from .helpers import objective_mode, profile_confidence
from .models import PlanetRoleProfile, ResistanceAnalysisReport, ResistanceSideReport, SignificatorPurityProfile


def build_resistance_analysis_report(
    snapshot: Mapping[str, object],
    role_profiles: Sequence[PlanetRoleProfile],
    purity_profiles: Sequence[SignificatorPurityProfile],
    objective: str | None = None,
) -> ResistanceAnalysisReport:
    objective_name = str(objective or snapshot.get("objective") or "Launch or publish")
    mode = objective_mode(objective_name)
    purity_map = {profile.planet: profile for profile in purity_profiles}
    warnings: list[str] = []

    asc_significators = _side_planets(role_profiles, {"lord_of_ascendant"})
    matter_significators = _side_planets(role_profiles, {"lord_of_matter"})
    user_significators = asc_significators | matter_significators | {"Moon"}
    opponent_significators = _side_planets(role_profiles, {"opponent_lord"})
    authority_significators = _side_planets(role_profiles, {"authority_lord"})
    outcome_significators = _side_planets(role_profiles, {"outcome_lord"})

    if mode == "exam":
        opponent_significators = _side_planets(role_profiles, {"exam_lord"})
        authority_significators = _side_planets(role_profiles, {"authority_lord"})
    elif mode == "message_contact":
        opponent_significators = _side_planets(role_profiles, {"opponent_lord", "relationship_lord"})
    elif mode == "relationship":
        opponent_significators = _side_planets(role_profiles, {"opponent_lord", "relationship_lord"})

    user_side = _build_side_report(user_significators, purity_map, "User side")
    opponent_side = _build_side_report(opponent_significators, purity_map, "Opponent side")
    authority_side = _build_side_report(authority_significators, purity_map, "Authority side")
    outcome_side = _build_side_report(outcome_significators, purity_map, "Outcome side")

    available_scores = [item for item in (user_side.strength, opponent_side.strength, authority_side.strength, outcome_side.strength) if item is not None]
    if not available_scores or user_side.strength is None or not asc_significators:
        warnings.append("Missing house-role data for a full side comparison.")
        return ResistanceAnalysisReport(
            resistance_mode=mode,
            user_side=user_side,
            opponent_side=opponent_side,
            authority_side=authority_side,
            outcome_side=outcome_side,
            advantage="unknown",
            advantage_score=None,
            main_reasons=(),
            risks=tuple(warnings),
            confidence=profile_confidence(warnings=warnings, missing_required=1),
            warnings=tuple(warnings),
        )

    opponent_strength = int(opponent_side.strength if opponent_side.strength is not None else 50)
    delta = int(user_side.strength or 0) - opponent_strength
    advantage = _advantage_label(delta)

    reasons: list[str] = []
    risks: list[str] = []
    if delta >= 12:
        reasons.append("Lord of Ascendant side is stronger than the opposing side.")
    elif delta <= -12:
        risks.append("Opponent or authority side is stronger than the Ascendant side.")
    if outcome_side.strength is not None:
        if outcome_side.strength >= opponent_strength:
            reasons.append("Outcome side does not lean toward the opponent.")
            delta += 3
        else:
            risks.append("Outcome side leans away from the user.")
            delta -= 3
    if authority_side.strength is not None:
        if authority_side.strength >= 70:
            reasons.append("Authority side is neutral to favorable.")
            if mode in {"exam", "legal_dispute"}:
                delta += 4
        elif authority_side.strength <= 45:
            risks.append("Authority side is hostile or unsupportive.")
            if mode in {"exam", "legal_dispute"}:
                delta -= 6

    advantage = _advantage_label(delta)

    return ResistanceAnalysisReport(
        resistance_mode=mode,
        user_side=user_side,
        opponent_side=opponent_side,
        authority_side=authority_side,
        outcome_side=outcome_side,
        advantage=advantage,
        advantage_score=delta,
        main_reasons=tuple(dict.fromkeys(reasons))[:4],
        risks=tuple(dict.fromkeys(risks))[:4],
        confidence=profile_confidence(warnings=warnings, missing_required=0),
        warnings=tuple(warnings),
    )


def _side_planets(role_profiles: Sequence[PlanetRoleProfile], roles: set[str]) -> set[str]:
    return {profile.planet for profile in role_profiles if roles.intersection(profile.roles)}


def _build_side_report(
    planets: set[str],
    purity_map: Mapping[str, SignificatorPurityProfile],
    label: str,
) -> ResistanceSideReport:
    strengths = [purity_map[planet].purity_score for planet in planets if planet in purity_map and purity_map[planet].purity_score is not None]
    purity = round(sum(strengths) / len(strengths)) if strengths else None
    strength = purity
    if strength is None:
        summary = f"{label} is unknown."
    elif strength >= 75:
        summary = f"{label} is strong."
    elif strength >= 60:
        summary = f"{label} is moderately strong."
    elif strength >= 45:
        summary = f"{label} is mixed."
    else:
        summary = f"{label} is weak or contaminated."
    return ResistanceSideReport(tuple(sorted(planets)), strength, purity, summary)


def _advantage_label(delta: int) -> str:
    if delta >= 20:
        return "strong_user_advantage"
    if delta >= 8:
        return "user_advantage"
    if delta <= -20:
        return "strong_opponent_advantage"
    if delta <= -8:
        return "opponent_advantage"
    return "contested"
