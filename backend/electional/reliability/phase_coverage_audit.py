"""Phase coverage audit for core, Phase 1, Phase 2, and Phase 3."""

from __future__ import annotations

from typing import Iterable

from .feature_registry import FeatureRegistryItem, build_feature_registry


def build_phase_coverage_audit(items: Iterable[FeatureRegistryItem] | None = None) -> dict[str, object]:
    registry = list(items or build_feature_registry())
    missing = [item for item in registry if item.status == "missing"]
    partial = [item for item in registry if item.status == "partial"]
    export_gaps = [item for item in registry if not item.appears_in_json_export or not item.appears_in_audit_export]
    replay_gaps = [item for item in registry if not item.replay_supported]
    calibration_gaps = [item for item in registry if not item.calibration_supported]
    test_gaps = [item for item in registry if not item.has_tests]
    return {
        "core_engine_coverage": _phase(registry, "core"),
        "phase1_advanced_analysis_coverage": _phase(registry, "phase1"),
        "phase2_tactical_output_coverage": _phase(registry, "phase2"),
        "phase3_reliability_coverage": _phase(registry, "phase3"),
        "missing_features": [_brief(item) for item in missing],
        "partial_features": [_brief(item) for item in partial],
        "export_gaps": [_brief(item) for item in export_gaps],
        "replay_gaps": [_brief(item) for item in replay_gaps],
        "calibration_gaps": [_brief(item) for item in calibration_gaps],
        "test_gaps": [_brief(item) for item in test_gaps],
        "warnings": _warnings(missing, partial, export_gaps, replay_gaps, calibration_gaps, test_gaps),
        "status": "complete" if not missing and not partial and not export_gaps and not replay_gaps and not calibration_gaps and not test_gaps else "needs_attention",
    }


def format_phase_coverage_audit(audit: dict[str, object]) -> str:
    lines = ["Phase Coverage Audit:"]
    for key, label in (
        ("core_engine_coverage", "Core"),
        ("phase1_advanced_analysis_coverage", "Phase 1"),
        ("phase2_tactical_output_coverage", "Phase 2"),
        ("phase3_reliability_coverage", "Phase 3"),
    ):
        section = audit.get(key, {})
        if isinstance(section, dict):
            lines.append(f"{label}: {section.get('implemented', 0)}/{section.get('total', 0)} implemented.")
    for key, label in (
        ("missing_features", "Missing"),
        ("partial_features", "Partial"),
        ("export_gaps", "Export gaps"),
        ("replay_gaps", "Replay gaps"),
        ("calibration_gaps", "Calibration gaps"),
        ("test_gaps", "Test gaps"),
    ):
        values = audit.get(key, [])
        if isinstance(values, list) and values:
            lines.append(f"{label}: " + ", ".join(str(item.get("feature_id")) for item in values[:6] if isinstance(item, dict)))
    return "\n".join(lines)


def _phase(items: list[FeatureRegistryItem], phase: str) -> dict[str, object]:
    phase_items = [item for item in items if item.phase == phase]
    return {
        "total": len(phase_items),
        "implemented": sum(1 for item in phase_items if item.status == "implemented"),
        "partial": sum(1 for item in phase_items if item.status == "partial"),
        "missing": sum(1 for item in phase_items if item.status == "missing"),
        "features": [item.to_json() for item in phase_items],
    }


def _brief(item: FeatureRegistryItem) -> dict[str, object]:
    return {
        "feature_id": item.feature_id,
        "name": item.name,
        "phase": item.phase,
        "status": item.status,
        "warnings": list(item.warnings),
    }


def _warnings(*groups: list[FeatureRegistryItem]) -> list[str]:
    warnings: list[str] = []
    labels = ("missing", "partial", "export", "replay", "calibration", "test")
    for label, group in zip(labels, groups):
        if group:
            warnings.append(f"{len(group)} {label} coverage issue(s).")
    return warnings
