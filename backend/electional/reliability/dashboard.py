"""Reliability dashboard summaries."""

from __future__ import annotations

from typing import Mapping, Sequence

from .calibration import build_outcome_calibration
from .feature_registry import build_feature_registry, registry_summary
from .phase_coverage_audit import build_phase_coverage_audit
from .review_queue import ReviewQueueItem


ENGINE_VERSION = "0.9.0-phase3_reliability_v1"


def build_reliability_dashboard(
    *,
    outcomes: Sequence[Mapping[str, object]] = (),
    replay_result: Mapping[str, object] | None = None,
    review_items: Sequence[ReviewQueueItem] = (),
) -> dict[str, object]:
    registry = build_feature_registry()
    coverage = build_phase_coverage_audit(registry)
    calibration = build_outcome_calibration(outcomes)
    fast_lane = next((item for item in registry if item.feature_id == "phase2_fast_lane"), None)
    return {
        "engine_version": ENGINE_VERSION,
        "feature_registry_summary": registry_summary(registry),
        "phase_coverage_audit": coverage,
        "data_quality_health": "available",
        "replay_stability": replay_result or {"status": "not_run", "summary": "No replay result supplied."},
        "fast_lane_status": fast_lane.to_json() if fast_lane else {"status": "missing"},
        "fast_lane_drift_status": _fast_lane_drift(replay_result),
        "outcome_calibration": calibration,
        "rule_performance": calibration,
        "objective_reliability": {},
        "open_review_items": [item.to_json() for item in review_items],
    }


def format_reliability_dashboard(dashboard: Mapping[str, object]) -> str:
    summary = dashboard.get("feature_registry_summary", {})
    coverage = dashboard.get("phase_coverage_audit", {})
    fast_lane = dashboard.get("fast_lane_status", {})
    calibration = dashboard.get("outcome_calibration", {})
    review = dashboard.get("open_review_items", [])
    lines = [
        "Reliability Dashboard",
        f"Engine: {dashboard.get('engine_version', 'unknown')}",
        "Feature Coverage:",
    ]
    if isinstance(summary, Mapping):
        for phase in ("core", "phase1", "phase2", "phase3"):
            row = summary.get(phase, {})
            if isinstance(row, Mapping):
                lines.append(f"- {phase}: {row.get('implemented', 0)}/{row.get('total', 0)} implemented")
    if isinstance(fast_lane, Mapping):
        lines.extend(["Fast Lane:", f"- {fast_lane.get('status', 'unknown')}, tested {fast_lane.get('has_tests', False)}, replay-supported {fast_lane.get('replay_supported', False)}."])
    replay = dashboard.get("replay_stability", {})
    if isinstance(replay, Mapping):
        lines.extend(["Replay Stability:", f"- {replay.get('summary', replay.get('status', 'not run'))}"])
    if isinstance(calibration, Mapping):
        lines.extend(["Outcome Calibration:", f"- {calibration.get('sample_size', 0)} logged outcomes."])
    if isinstance(coverage, Mapping) and coverage.get("warnings"):
        lines.extend(["Coverage Warnings:", *[f"- {warning}" for warning in coverage.get("warnings", [])]])
    if isinstance(review, list):
        lines.extend(["Open Review:", f"- {len(review)} item(s)."])
    return "\n".join(lines)


def _fast_lane_drift(replay_result: Mapping[str, object] | None) -> dict[str, object]:
    if not replay_result:
        return {"status": "not_run"}
    drifts = replay_result.get("drifts", [])
    fast = [item for item in drifts if isinstance(item, Mapping) and item.get("category") == "phase2_fast_lane_drift"] if isinstance(drifts, list) else []
    return {"status": "drift" if fast else "no_drift", "count": len(fast)}
