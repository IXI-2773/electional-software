"""Advanced analysis orchestration for election snapshots and candidates."""

from __future__ import annotations

from typing import Mapping

from .control_index import build_control_index_report
from .contradictions import detect_contradictions
from .models import AdvancedAnalysisReport
from .planet_roles import resolve_planet_roles
from .resistance import build_resistance_analysis_report
from .significator_purity import build_significator_purity_profiles


def build_advanced_analysis_report(snapshot: Mapping[str, object]) -> AdvancedAnalysisReport:
    objective = str(snapshot.get("objective") or "Launch or publish")
    role_profiles = tuple(resolve_planet_roles(snapshot, objective))
    purity_profiles = tuple(build_significator_purity_profiles(snapshot, role_profiles, objective))
    contradictions = tuple(detect_contradictions(snapshot, role_profiles, purity_profiles))
    control_index = build_control_index_report(snapshot, role_profiles, purity_profiles)
    resistance_analysis = build_resistance_analysis_report(snapshot, role_profiles, purity_profiles, objective)
    warnings: list[str] = []
    warnings.extend(control_index.warnings)
    warnings.extend(resistance_analysis.warnings)
    for profile in purity_profiles:
        warnings.extend(profile.warnings)
    final_tactical_interpretation = _tactical_interpretation(snapshot, contradictions, control_index, resistance_analysis)
    confidence = round(
        max(
            0.2,
            min(
                0.99,
                (
                    sum(profile.confidence for profile in role_profiles) / max(1, len(role_profiles))
                    + sum(profile.confidence for profile in purity_profiles) / max(1, len(purity_profiles))
                    + control_index.confidence
                    + resistance_analysis.confidence
                )
                / 4.0,
            ),
        ),
        2,
    )
    return AdvancedAnalysisReport(
        planet_roles=role_profiles,
        significator_purity=purity_profiles,
        contradictions=contradictions,
        control_index=control_index,
        resistance_analysis=resistance_analysis,
        final_tactical_interpretation=final_tactical_interpretation,
        warnings=tuple(dict.fromkeys(str(item) for item in warnings if item))[:8],
        confidence=confidence,
    )


def annotate_advanced_analysis(windows: list[dict[str, object]]) -> list[dict[str, object]]:
    annotated: list[dict[str, object]] = []
    for window in windows:
        item = dict(window)
        report = build_advanced_analysis_report(item)
        item["advancedAnalysis"] = report.to_json()
        item["advanced_analysis"] = item["advancedAnalysis"]
        item["engine_schema_version"] = "phase1_advanced_analysis_v1"
        annotated.append(item)
    return annotated


def _tactical_interpretation(
    snapshot: Mapping[str, object],
    contradictions: tuple,
    control_index,
    resistance_analysis,
) -> str:
    score = int(snapshot.get("score", 0) or 0)
    contradiction_severity = {item.severity for item in contradictions}
    if "critical" in contradiction_severity:
        return "Hard contradictions dominate this chart. Do not let the surface score override the structural conflicts."
    if score >= 80 and "major" in contradiction_severity:
        return "Useable, but a core support factor is contaminated. Prefer this only if practical constraints matter or cleaner candidates are unavailable."
    if control_index.band in {"user_has_strong_control", "user_has_advantage"} and resistance_analysis.advantage in {"user_advantage", "strong_user_advantage"}:
        return "The chart gives the user tactical leverage. Favor it if the objective depends on control, authority, or response."
    if resistance_analysis.advantage in {"opponent_advantage", "strong_opponent_advantage"}:
        return "The chart favors resistance or the opposing side. Continue searching unless the matter is uncontested."
    return "Advanced analysis is mixed. Treat the chart as workable only if the key significators and control profile fit the real objective."
