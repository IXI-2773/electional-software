"""Detect contradictions in advanced election analysis."""

from __future__ import annotations

from typing import Mapping, Sequence

from .helpers import detected_aspects_for, moon_non_void, objective_mode, profile_confidence
from .models import ContradictionFinding, PlanetRoleProfile, SignificatorPurityProfile


def detect_contradictions(
    snapshot: Mapping[str, object],
    role_profiles: Sequence[PlanetRoleProfile],
    purity_profiles: Sequence[SignificatorPurityProfile],
) -> list[ContradictionFinding]:
    role_map = {profile.planet: profile for profile in role_profiles}
    purity_map = {profile.planet: profile for profile in purity_profiles}
    findings: list[ContradictionFinding] = []

    for benefic_name in ("Venus", "Jupiter"):
        role_profile = role_map.get(benefic_name)
        purity_profile = purity_map.get(benefic_name)
        if not role_profile or not purity_profile:
            continue
        if "functional_malefic" in role_profile.roles and _moon_applies_to(snapshot, benefic_name):
            findings.append(
                ContradictionFinding(
                    id="benefic_contaminated_by_bad_house",
                    severity="major",
                    title="Benefic support is contaminated",
                    description=f"Moon applies to {benefic_name}, but {benefic_name} carries bad-house contamination.",
                    affected_planets=("Moon", benefic_name),
                    affected_scores=("moon_support", "benefic_support"),
                    recommendation="Reduce clean benefic testimony and treat the support as mixed.",
                    confidence=min(role_profile.confidence, purity_profile.confidence),
                    impact="confidence downgrade",
                )
            )

    mercury_role = role_map.get("Mercury")
    mercury_purity = purity_map.get("Mercury")
    mercury_position = _position(snapshot, "Mercury")
    if mercury_role and mercury_purity and mercury_position:
        phase = str((mercury_position.get("solarCondition") or {}).get("phase") or "")
        if mercury_purity.purity_score is not None and mercury_purity.purity_score >= 55 and phase in {"combust", "under beams"}:
            findings.append(
                ContradictionFinding(
                    id="mercury_strong_but_combust",
                    severity="major",
                    title="Strong Mercury, but combust",
                    description=f"Mercury shows useful strength, but solar damage is present: {phase}.",
                    affected_planets=("Mercury",),
                    affected_scores=("communication_support", "exam_support"),
                    recommendation="Downgrade Mercury support from strong to mixed.",
                    confidence=min(mercury_role.confidence, mercury_purity.confidence),
                    impact="confidence downgrade",
                )
            )

    for malefic_name in ("Mars", "Saturn"):
        role_profile = role_map.get(malefic_name)
        purity_profile = purity_map.get(malefic_name)
        if not role_profile or not purity_profile:
            continue
        if "lord_of_matter" in role_profile.roles and "natural_malefic" in role_profile.roles:
            severity = "warning" if purity_profile.purity_score and purity_profile.purity_score >= 50 else "major"
            findings.append(
                ContradictionFinding(
                    id="matter_ruling_malefic",
                    severity=severity,
                    title="Matter-ruling malefic needs containment",
                    description=f"{malefic_name} rules the matter, but it remains a natural malefic and needs context-sensitive reading.",
                    affected_planets=(malefic_name,),
                    affected_scores=("matter_support", "risk_profile"),
                    recommendation="Treat the malefic as potentially useful, but do not count it as clean help.",
                    confidence=min(role_profile.confidence, purity_profile.confidence),
                    impact="explanatory",
                )
            )

    fragility = snapshot.get("fragility")
    if not isinstance(fragility, Mapping):
        stability = snapshot.get("windowStability", {})
        fragility = stability.get("fragility", {}) if isinstance(stability, Mapping) else {}
    if int(snapshot.get("score", 0) or 0) >= 85 and isinstance(fragility, Mapping) and str(fragility.get("band") or "") == "High":
        findings.append(
            ContradictionFinding(
                id="high_score_fragile_window",
                severity="warning",
                title="High score, but fragile timing window",
                description="The chart scores highly, but the usable minute range is fragile.",
                affected_planets=(),
                affected_scores=("score", "window_stability"),
                recommendation="Reduce tactical confidence and prefer a wider stable window if available.",
                confidence=profile_confidence(warnings=["High fragility window."], missing_required=0),
                impact="risk increase",
            )
        )

    clean_benefic = role_map.get("Jupiter")
    if clean_benefic and "functional_malefic" not in clean_benefic.roles and _moon_applies_to(snapshot, "Jupiter"):
        # Do not emit a false contamination contradiction for a clean benefic.
        pass

    findings.sort(key=lambda item: (_severity_rank(item.severity), item.id))
    return findings


def _severity_rank(severity: str) -> int:
    return {
        "critical": 0,
        "major": 1,
        "warning": 2,
        "info": 3,
    }.get(severity, 4)


def _position(snapshot: Mapping[str, object], planet_name: str) -> Mapping[str, object] | None:
    for position in snapshot.get("positions", []):
        if isinstance(position, Mapping) and position.get("name") == planet_name:
            return position
    return None


def _moon_applies_to(snapshot: Mapping[str, object], planet_name: str) -> bool:
    for aspect in detected_aspects_for(snapshot, "Moon"):
        if aspect.get("tone") != "support" or not aspect.get("isApplying"):
            continue
        bodies = {str(body) for body in aspect.get("bodies", []) if body}
        if planet_name in bodies:
            return True
    return False
