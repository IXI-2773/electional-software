"""Central feature registry for core, Phase 1, Phase 2, and Phase 3."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class FeatureRegistryItem:
    feature_id: str
    name: str
    phase: str
    version: str | None
    module_path: str | None
    status: str
    has_tests: bool
    appears_in_report: bool
    appears_in_json_export: bool
    appears_in_audit_export: bool
    replay_supported: bool
    calibration_supported: bool
    warnings: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["warnings"] = list(self.warnings)
        return payload


def build_feature_registry() -> list[FeatureRegistryItem]:
    return [_item(*spec) for spec in _SPECS]


def feature_registry_json() -> dict[str, object]:
    items = build_feature_registry()
    return {
        "features": [item.to_json() for item in items],
        "summary": registry_summary(items),
    }


def registry_summary(items: list[FeatureRegistryItem]) -> dict[str, object]:
    phases = sorted({item.phase for item in items})
    return {
        phase: {
            "implemented": sum(1 for item in items if item.phase == phase and item.status == "implemented"),
            "total": sum(1 for item in items if item.phase == phase),
            "partial": sum(1 for item in items if item.phase == phase and item.status == "partial"),
            "missing": sum(1 for item in items if item.phase == phase and item.status == "missing"),
        }
        for phase in phases
    }


def item_by_id(feature_id: str, items: list[FeatureRegistryItem] | None = None) -> FeatureRegistryItem | None:
    for item in items or build_feature_registry():
        if item.feature_id == feature_id:
            return item
    return None


def _item(
    feature_id: str,
    name: str,
    phase: str,
    version: str | None,
    module_path: str | None,
    test_paths: tuple[str, ...],
    report: bool,
    json_export: bool,
    audit: bool,
    replay: bool,
    calibration: bool,
) -> FeatureRegistryItem:
    module_exists = _exists(module_path) if module_path else False
    has_tests = any(_exists(path) for path in test_paths)
    status = "implemented" if module_exists and has_tests else "partial" if module_exists or has_tests else "missing"
    if feature_id.startswith("phase3_") and feature_id not in _IMPLEMENTED_PHASE3:
        status = "partial" if module_exists else "missing"
    warnings: list[str] = []
    if not module_exists:
        warnings.append("module missing")
    if not has_tests:
        warnings.append("tests missing")
    if not json_export:
        warnings.append("json export missing")
    if not audit:
        warnings.append("audit export missing")
    if not replay:
        warnings.append("replay support missing")
    if not calibration:
        warnings.append("calibration support missing")
    return FeatureRegistryItem(
        feature_id,
        name,
        phase,
        version,
        module_path,
        status,
        has_tests,
        report,
        json_export,
        audit,
        replay,
        calibration,
        tuple(warnings),
    )


def _exists(path: str | None) -> bool:
    return bool(path) and (PROJECT_ROOT / path).exists()


_IMPLEMENTED_PHASE3 = {
    "phase3_engine_version_locking",
    "phase3_audit_snapshot",
    "phase3_regression_replay",
    "phase3_outcome_logging",
    "phase3_calibration_reports",
    "phase3_rule_performance",
    "phase3_historical_replay",
    "phase3_reliability_dashboard",
    "phase3_review_queue",
    "phase3_schema_migration",
    "phase3_reliability_exports",
}


_SPECS = (
    ("core_swiss_ephemeris", "Swiss Ephemeris", "core", "v1", "backend/electional/ephemeris.py", ("backend/tests/test_python_chart_engine.py",), True, True, True, True, False),
    ("core_fallback_handling", "Fallback Handling", "core", "v1", "backend/electional/professional.py", ("backend/tests/test_python_chart_engine.py",), True, True, True, True, False),
    ("core_data_quality_dashboard", "Data Quality Dashboard", "core", "v1", "backend/electional/accuracy.py", ("backend/tests/test_desktop_ui.py",), True, True, True, True, False),
    ("core_confidence_penalties", "Confidence Penalties", "core", "v1", "backend/electional/engine/confidence.py", ("backend/tests/test_python_chart_engine.py",), True, True, True, True, True),
    ("core_golden_chart_tests", "Golden Chart Tests", "core", "v1", "backend/tests/test_python_chart_engine.py", ("backend/tests/test_python_chart_engine.py",), False, False, True, True, False),
    ("core_differential_engine_tests", "Differential Engine Tests", "core", "v1", "backend/tests/test_python_chart_engine.py", ("backend/tests/test_python_chart_engine.py",), False, False, True, True, False),
    ("core_moon_logic", "Moon Logic", "core", "v1", "backend/electional/engine/moon.py", ("backend/tests/test_electional_core.py",), True, True, True, True, True),
    ("core_score_ledger", "Score Ledger", "core", "v1", "backend/electional/engine/scoring.py", ("backend/tests/test_electional_core.py",), True, True, True, True, True),
    ("core_red_team_review", "Red Team Review", "core", "v1", "backend/electional/engine/search.py", ("backend/tests/test_desktop_ui.py",), True, True, True, True, True),
    ("core_stable_window_search", "Stable Window Search", "core", "v1", "backend/electional/engine/search.py", ("backend/tests/test_electional_core.py",), True, True, True, True, True),
    ("core_pareto_ranking", "Pareto Ranking", "core", "v1", "backend/electional/engine/search.py", ("backend/tests/test_electional_core.py",), True, True, True, True, True),
    ("core_repair_suggestions", "Repair Suggestions", "core", "v1", "backend/electional/engine/search.py", ("backend/tests/test_desktop_ui.py",), True, True, True, True, True),
    ("core_long_range_scouting", "Long Range Scouting", "core", "v1", "backend/electional/long_range.py", ("backend/tests/test_long_range_scout.py",), True, True, True, True, True),
    ("core_failure_mode_classification", "Failure Mode Classification", "core", "v1", "backend/electional/engine/search.py", ("backend/tests/test_search_reason_log.py",), True, True, True, True, True),
    ("core_objective_specific_analyzers", "Objective Specific Analyzers", "core", "v1", "backend/electional/judgment.py", ("backend/tests/test_electional_core.py",), True, True, True, True, True),
    ("core_candidate_debate", "Candidate Debate", "core", "v1", "backend/electional/engine/search.py", ("backend/tests/test_electional_core.py",), True, True, True, True, True),
    ("core_search_reason_logs", "Search Reason Logs", "core", "v1", "backend/electional/engine/search.py", ("backend/tests/test_search_reason_log.py",), True, True, True, True, True),
    ("core_rarity_scoring", "Rarity Scoring", "core", "v1", "backend/electional/engine/search.py", ("backend/tests/test_search_reason_log.py",), True, True, True, True, True),
    ("core_emergency_least_bad", "Emergency Least Bad", "core", "v1", "backend/electional/engine/search.py", ("backend/tests/test_electional_core.py",), True, True, True, True, True),
    ("phase1_planet_role_resolver", "Planet Role Resolver", "phase1", "v1", "backend/electional/analysis/planet_roles.py", ("backend/tests/test_planet_role_resolver.py",), True, True, True, True, True),
    ("phase1_significator_purity", "Significator Purity", "phase1", "v1", "backend/electional/analysis/significator_purity.py", ("backend/tests/test_significator_purity.py",), True, True, True, True, True),
    ("phase1_contradiction_detection", "Contradiction Detection", "phase1", "v1", "backend/electional/analysis/contradictions.py", ("backend/tests/test_contradiction_detection.py",), True, True, True, True, True),
    ("phase1_chart_control_index", "Chart Control Index", "phase1", "v1", "backend/electional/analysis/control_index.py", ("backend/tests/test_control_index.py",), True, True, True, True, True),
    ("phase1_resistance_analysis", "Resistance Analysis", "phase1", "v1", "backend/electional/analysis/resistance.py", ("backend/tests/test_resistance_analysis.py",), True, True, True, True, True),
    ("phase2_final_command", "Final Command", "phase2", "v1", "backend/electional/analysis/final_command.py", ("backend/tests/test_final_command.py",), True, True, True, True, True),
    ("phase2_timing_trap_detector", "Timing Trap Detector", "phase2", "v1", "backend/electional/analysis/timing_traps.py", ("backend/tests/test_timing_traps.py",), True, True, True, True, True),
    ("phase2_action_moment_resolver", "Action Moment Resolver", "phase2", "v1", "backend/electional/analysis/action_moment.py", ("backend/tests/test_action_moment.py",), True, True, True, True, True),
    ("phase2_event_playbooks", "Event Playbooks", "phase2", "v1", "backend/electional/analysis/playbooks.py", ("backend/tests/test_playbooks.py",), True, True, True, True, True),
    ("phase2_practical_usability", "Practical Usability", "phase2", "v1", "backend/electional/analysis/practicality.py", ("backend/tests/test_practicality.py",), True, True, True, True, True),
    ("phase2_strategic_calendar", "Strategic Calendar", "phase2", "v1", "backend/electional/analysis/strategic_calendar.py", ("backend/tests/test_strategic_calendar.py",), True, True, True, True, True),
    ("phase2_calendar_export", "Calendar Export", "phase2", "v1", "backend/electional/calendar_export.py", ("backend/tests/test_calendar_export_phase2.py",), True, True, True, True, True),
    ("phase2_tactical_report", "Tactical Report", "phase2", "v1", "backend/electional/reports/text_report.py", ("backend/tests/test_tactical_report_integration.py",), True, True, True, True, True),
    ("phase2_candidate_comparison_tactical", "Candidate Comparison Tactical", "phase2", "v1", "backend/electional/reports/text_report.py", ("backend/tests/test_candidate_comparison_tactical.py",), True, True, True, True, True),
    ("phase2_fast_lane", "Fast Lane Mode", "phase2", "v1", "backend/electional/analysis/fast_lane.py", ("backend/tests/test_fast_lane.py",), True, True, True, True, True),
    ("phase3_engine_version_locking", "Engine Version Locking", "phase3", "v1", "backend/electional/reliability/audit_snapshot.py", ("backend/tests/test_audit_snapshot.py",), True, True, True, True, True),
    ("phase3_audit_snapshot", "Audit Snapshot", "phase3", "v1", "backend/electional/reliability/audit_snapshot.py", ("backend/tests/test_audit_snapshot.py",), True, True, True, True, True),
    ("phase3_regression_replay", "Regression Replay", "phase3", "v1", "backend/electional/reliability/regression_replay.py", ("backend/tests/test_regression_replay.py",), True, True, True, True, True),
    ("phase3_outcome_logging", "Outcome Logging", "phase3", "v1", "backend/electional/reliability/calibration.py", ("backend/tests/test_outcome_calibration.py",), True, True, True, True, True),
    ("phase3_calibration_reports", "Calibration Reports", "phase3", "v1", "backend/electional/reliability/calibration.py", ("backend/tests/test_outcome_calibration.py",), True, True, True, True, True),
    ("phase3_rule_performance", "Rule Performance", "phase3", "v1", "backend/electional/reliability/calibration.py", ("backend/tests/test_outcome_calibration.py",), True, True, True, True, True),
    ("phase3_rule_weight_experiments", "Rule Weight Experiments", "phase3", None, None, (), False, False, False, False, False),
    ("phase3_historical_replay", "Historical Replay", "phase3", "v1", "backend/electional/reliability/regression_replay.py", ("backend/tests/test_regression_replay.py",), True, True, True, True, True),
    ("phase3_reliability_dashboard", "Reliability Dashboard", "phase3", "v1", "backend/electional/reliability/dashboard.py", ("backend/tests/test_reliability_dashboard.py",), True, True, True, True, True),
    ("phase3_review_queue", "Review Queue", "phase3", "v1", "backend/electional/reliability/review_queue.py", ("backend/tests/test_review_queue.py",), True, True, True, True, True),
    ("phase3_schema_migration", "Schema Migration", "phase3", "v1", "backend/electional/reliability/audit_snapshot.py", ("backend/tests/test_audit_snapshot.py",), True, True, True, True, True),
    ("phase3_reliability_exports", "Reliability Exports", "phase3", "v1", "backend/electional/reliability/exports.py", ("backend/tests/test_reliability_exports.py",), True, True, True, True, True),
)
