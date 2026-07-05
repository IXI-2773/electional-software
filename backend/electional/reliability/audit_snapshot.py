"""Complete audit snapshot construction across all implemented phases."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Mapping

from .dashboard import ENGINE_VERSION
from .feature_registry import feature_registry_json
from .phase_coverage_audit import build_phase_coverage_audit


def build_audit_snapshot(snapshot: Mapping[str, object]) -> dict[str, object]:
    advanced = snapshot.get("advancedAnalysis") if isinstance(snapshot.get("advancedAnalysis"), Mapping) else {}
    tactical = snapshot.get("tacticalAnalysis") if isinstance(snapshot.get("tacticalAnalysis"), Mapping) else {}
    registry = feature_registry_json()
    coverage = build_phase_coverage_audit()
    warnings: list[str] = []
    phase1 = {
        "planet_roles": _section(advanced, "planet_roles", warnings),
        "significator_purity": _section(advanced, "significator_purity", warnings),
        "contradictions": _section(advanced, "contradictions", warnings),
        "control_index": _section(advanced, "control_index", warnings),
        "resistance_analysis": _section(advanced, "resistance_analysis", warnings),
    }
    fast_lane = _fast_lane_block(snapshot, tactical)
    phase2 = {
        "final_command": _section(tactical, "final_command", warnings),
        "timing_traps": _section(tactical, "timing_traps", warnings),
        "action_moment": _section(tactical, "action_moment", warnings),
        "event_playbook": _section(tactical, "playbook", warnings),
        "practicality": _section(tactical, "practicality", warnings),
        "strategic_calendar_context": _section(tactical, "strategic_calendar_context", warnings),
        "candidate_tactical_comparison": {"status": "available" if tactical else "unavailable"},
        "fast_lane": fast_lane,
    }
    payload = {
        "audit_snapshot": {
            "version_info": {"engine_version": ENGINE_VERSION, "schema_version": "phase3_reliability_v1", "created_at": datetime.now(UTC).isoformat()},
            "feature_registry": registry,
            "phase_coverage_audit": coverage,
            "input": {"date": _string(snapshot.get("date")), "objective": snapshot.get("objective"), "formattedTime": snapshot.get("formattedTime")},
            "phase4_profile": {
                "search_profile_id": snapshot.get("search_profile_id"),
                "search_profile_version": snapshot.get("search_profile_version"),
                "objective_pack_version": snapshot.get("objective_pack_version"),
            },
            "location": snapshot.get("location", {"status": "unavailable"}),
            "timezone": snapshot.get("timezone", {"status": "unavailable"}),
            "chart_data": {"positions": len(snapshot.get("positions", [])) if isinstance(snapshot.get("positions"), list) else 0, "houses": len(snapshot.get("houseCusps", [])) if isinstance(snapshot.get("houseCusps"), list) else 0},
            "data_quality": snapshot.get("accuracyAudit", {"status": "unavailable"}),
            "hard_gates": {"status": _hard_gate_status(snapshot), "failure_analysis": snapshot.get("failureAnalysis", {"status": "unavailable"})},
            "score": snapshot.get("score"),
            "grade": _grade(snapshot),
            "confidence": _confidence(snapshot),
            "score_ledger": snapshot.get("scoreBreakdown", {}).get("accounting", {"status": "unavailable"}) if isinstance(snapshot.get("scoreBreakdown"), Mapping) else {"status": "unavailable"},
            "core_search_analysis": {"search_reason_log": snapshot.get("searchReasonLog", {"status": "unavailable"}), "rarity": snapshot.get("rarity", {"status": "unavailable"})},
            "phase1_advanced_analysis": phase1,
            "phase2_tactical_analysis": phase2,
            "phase3_reliability": {
                "regression_replay_status": {"status": "not_run"},
                "outcome_calibration_context": {"status": "not_run"},
                "rule_performance_context": {"status": "not_run"},
                "review_queue_flags": [],
            },
            "warnings": warnings + list(coverage.get("warnings", [])),
            "limitations": ["Replay and calibration require prior snapshots or outcome records."],
        }
    }
    payload["audit_snapshot"]["reproducibility_hash"] = _hash(payload["audit_snapshot"])
    return payload


def _section(source: object, key: str, warnings: list[str]) -> object:
    if isinstance(source, Mapping) and key in source:
        return source[key]
    warnings.append(f"{key} unavailable in audit snapshot.")
    return {"status": "unavailable", "warning": f"{key} missing"}


def _fast_lane_block(snapshot: Mapping[str, object], tactical: object) -> dict[str, object]:
    fast = tactical.get("fast_lane", {}) if isinstance(tactical, Mapping) and isinstance(tactical.get("fast_lane"), Mapping) else {}
    command = tactical.get("final_command", {}) if isinstance(tactical, Mapping) and isinstance(tactical.get("final_command"), Mapping) else {}
    window = command.get("use_window", {}) if isinstance(command, Mapping) and isinstance(command.get("use_window"), Mapping) else {}
    return {
        "command": fast.get("command", "unavailable"),
        "window": f"{window.get('start', 'unknown')}/{window.get('end', 'unknown')}",
        "best_minute": window.get("best_minute", fast.get("best", "unknown")),
        "cutoff": window.get("cutoff", fast.get("cutoff", "unknown")),
        "main_reason": fast.get("main_reason", ""),
        "main_risk": fast.get("main_risk", ""),
        "action_moment": fast.get("action", ""),
        "confidence": fast.get("confidence"),
        "hard_gate_status": _hard_gate_status(snapshot),
        "data_confidence_warning": _data_confidence_warning(tactical),
    }


def _hard_gate_status(snapshot: Mapping[str, object]) -> str:
    if snapshot.get("hardReject"):
        return "failed"
    failure = snapshot.get("failureAnalysis")
    hard = failure.get("hardFailures") if isinstance(failure, Mapping) else None
    return "failed" if isinstance(hard, list) and hard else "passed"


def _data_confidence_warning(tactical: object) -> str | None:
    fast = tactical.get("fast_lane", {}) if isinstance(tactical, Mapping) else {}
    warnings = fast.get("warnings", []) if isinstance(fast, Mapping) else []
    return str(warnings[0]) if isinstance(warnings, list) and warnings else None


def _grade(snapshot: Mapping[str, object]) -> object:
    breakdown = snapshot.get("scoreBreakdown")
    evaluation = breakdown.get("evaluation") if isinstance(breakdown, Mapping) else None
    return evaluation.get("grade") if isinstance(evaluation, Mapping) else None


def _confidence(snapshot: Mapping[str, object]) -> float | None:
    breakdown = snapshot.get("scoreBreakdown")
    diagnostics = breakdown.get("diagnostics") if isinstance(breakdown, Mapping) else None
    confidence = diagnostics.get("confidence") if isinstance(diagnostics, Mapping) else None
    score = confidence.get("score") if isinstance(confidence, Mapping) else None
    try:
        value = float(score)
    except (TypeError, ValueError):
        return None
    return value / 100 if value > 1 else value


def _string(value: object) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _hash(payload: Mapping[str, object]) -> str:
    text = json.dumps(payload, sort_keys=True, default=str)
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
