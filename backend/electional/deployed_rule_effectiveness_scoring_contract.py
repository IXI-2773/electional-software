"""Scoring-contract validation for deployed-rule effectiveness without score execution."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from . import deployed_rule_effectiveness_evaluation_spec as spec_backend
from . import deployed_rule_effectiveness_readiness as readiness_backend
from . import deployed_rule_operational_telemetry as telemetry_backend
from . import deployed_rule_outcome_truth_source as truth_backend
from .canonical_rule_runtime import _atomic_write_json, _hash_payload, _now, _read_json, _restore_json, _safe_id
from .source_documents import SOURCE_DOCUMENT_ROOT

PLAN_DIR = "deployed_rule_effectiveness_scoring_contract/plans"
RESULT_DIR = "deployed_rule_effectiveness_scoring_contract/results"
RECEIPT_DIR = "deployed_rule_effectiveness_scoring_contract/receipts"
PLAN_INDEX = "deployed_rule_effectiveness_scoring_contract_plan_index.json"
RESULT_INDEX = "deployed_rule_effectiveness_scoring_contract_result_index.json"
RECEIPT_INDEX = "deployed_rule_effectiveness_scoring_contract_receipt_index.json"

SCORING_CONTRACT_MANIFEST_SCHEMA_VERSION = "deployed_rule_effectiveness_scoring_contract_manifest_v1"
SCORING_CONTRACT_WORKSPACE_SCHEMA_VERSION = "deployed_rule_effectiveness_scoring_contract_workspace_v1"
SCORING_CONTRACT_PLAN_SCHEMA_VERSION = "deployed_rule_effectiveness_scoring_contract_plan_v1"
SCORING_CONTRACT_RESULT_SCHEMA_VERSION = "deployed_rule_effectiveness_scoring_contract_result_v1"
SCORING_CONTRACT_RECEIPT_SCHEMA_VERSION = "deployed_rule_effectiveness_scoring_contract_receipt_v1"
SCORING_CONTRACT_SCHEMA_VERSION = "deployed_rule_effectiveness_scoring_contract_v1"
REQUIRED_CONFIRMATION = "RECORD_EFFECTIVENESS_SCORING_CONTRACT_RESULT"

SCORING_CONTRACT_STATUSES = [
    "scoring_contract_ready_for_engine_design",
    "scoring_contract_blocked_missing_readiness",
    "scoring_contract_blocked_missing_spec",
    "scoring_contract_blocked_missing_outcome_truth",
    "scoring_contract_blocked_incomplete_truth_records",
    "scoring_contract_blocked_missing_denominator_inputs",
    "scoring_contract_blocked_missing_numerator_inputs",
    "scoring_contract_blocked_unsupported_metrics",
    "blocked",
    "stale",
    "corrupt",
]

PUBLIC_FUNCTIONS = [
    "get_deployed_rule_effectiveness_scoring_contract_manifest",
    "build_deployed_rule_effectiveness_scoring_contract_workspace",
    "validate_deployed_rule_effectiveness_scoring_contract_eligibility",
    "build_deployed_rule_effectiveness_scoring_contract_plan",
    "record_deployed_rule_effectiveness_scoring_contract_result",
    "load_deployed_rule_effectiveness_scoring_contract_result",
    "get_deployed_rule_effectiveness_scoring_contract_health",
    "format_deployed_rule_effectiveness_scoring_contract_report",
]


def get_deployed_rule_effectiveness_scoring_contract_manifest(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    return {
        "schema_version": SCORING_CONTRACT_MANIFEST_SCHEMA_VERSION,
        "scoring_contract_schema_version": SCORING_CONTRACT_SCHEMA_VERSION,
        "required_identifiers": [
            "canonical_rule_id",
            "production_deployment_result_id",
            "production_target_id",
            "deployed_rule_id",
            "telemetry_snapshot_id",
            "readiness_result_id",
            "effectiveness_spec_result_id",
            "outcome_truth_source_result_id",
            "outcome_truth_record_set_id",
            "observation_window_start",
            "observation_window_end",
        ],
        "statuses": list(SCORING_CONTRACT_STATUSES),
        "metric_families": [
            "accuracy_like_contract",
            "false_positive_false_negative_contract",
            "precision_recall_like_contract",
            "calibration_like_contract",
            "runtime_reliability_contract",
        ],
        "effectiveness_score_calculated": False,
        "correctness_calculated": False,
        "rates_calculated": False,
        "phase_9w_not_scoring_input": True,
        "runtime_completion_not_correctness": True,
        "source_availability_not_effectiveness": True,
        "confirmation_required": REQUIRED_CONFIRMATION,
    }


def build_deployed_rule_effectiveness_scoring_contract_workspace(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result_id: str,
    effectiveness_spec_result_id: str,
    outcome_truth_source_result_id: str,
    outcome_truth_record_set_id: str,
    observation_window_start: str,
    observation_window_end: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    context = _scoring_contract_context(
        canonical_rule_id=canonical_rule_id,
        production_deployment_result_id=production_deployment_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
        telemetry_snapshot_id=telemetry_snapshot_id,
        readiness_result_id=readiness_result_id,
        effectiveness_spec_result_id=effectiveness_spec_result_id,
        outcome_truth_source_result_id=outcome_truth_source_result_id,
        outcome_truth_record_set_id=outcome_truth_record_set_id,
        observation_window_start=observation_window_start,
        observation_window_end=observation_window_end,
        root=root,
    )
    return {
        "schema_version": SCORING_CONTRACT_WORKSPACE_SCHEMA_VERSION,
        "scoring_contract_schema_version": SCORING_CONTRACT_SCHEMA_VERSION,
        "status": context["status"],
        "canonical_rule_id": canonical_rule_id,
        "production_deployment_result_id": production_deployment_result_id,
        "production_target_id": production_target_id,
        "deployed_rule_id": deployed_rule_id,
        "telemetry_snapshot_id": telemetry_snapshot_id,
        "readiness_result_id": readiness_result_id,
        "effectiveness_spec_result_id": effectiveness_spec_result_id,
        "outcome_truth_source_result_id": outcome_truth_source_result_id,
        "outcome_truth_record_set_id": outcome_truth_record_set_id,
        "observation_window_start": observation_window_start,
        "observation_window_end": observation_window_end,
        "valid_execution_attempt_count": context["valid_execution_attempt_count"],
        "valid_truth_record_count": context["valid_truth_record_count"],
        "expected_outcomes_available": context["criteria"]["expected_outcomes_available"],
        "actual_or_adjudicated_outcomes_available": context["criteria"]["actual_or_adjudicated_outcomes_available"],
        "metric_contracts": deepcopy(context["metric_contracts"]),
        "denominator_contract": deepcopy(context["denominator_contract"]),
        "numerator_contract": deepcopy(context["numerator_contract"]),
        "denominator_input_readiness": context["denominator_input_readiness"],
        "numerator_input_readiness": context["numerator_input_readiness"],
        "outcome_truth_readiness": context["outcome_truth_readiness"],
        "criteria": deepcopy(context["criteria"]),
        "blockers": list(context["blockers"]),
        "warnings": list(context["warnings"]),
        "recommended_action": _recommended_action(context["status"]),
        "effectiveness_score_calculated": False,
        "correctness_calculated": False,
        "rates_calculated": False,
    }


def validate_deployed_rule_effectiveness_scoring_contract_eligibility(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result_id: str,
    effectiveness_spec_result_id: str,
    outcome_truth_source_result_id: str,
    outcome_truth_record_set_id: str,
    observation_window_start: str,
    observation_window_end: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    context = _scoring_contract_context(
        canonical_rule_id=canonical_rule_id,
        production_deployment_result_id=production_deployment_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
        telemetry_snapshot_id=telemetry_snapshot_id,
        readiness_result_id=readiness_result_id,
        effectiveness_spec_result_id=effectiveness_spec_result_id,
        outcome_truth_source_result_id=outcome_truth_source_result_id,
        outcome_truth_record_set_id=outcome_truth_record_set_id,
        observation_window_start=observation_window_start,
        observation_window_end=observation_window_end,
        root=root,
    )
    return {
        "status": context["status"],
        "criteria": deepcopy(context["criteria"]),
        "blockers": list(context["blockers"]),
        "warnings": list(context["warnings"]),
        "metric_contracts": deepcopy(context["metric_contracts"]),
        "numerator_contract": deepcopy(context["numerator_contract"]),
        "denominator_contract": deepcopy(context["denominator_contract"]),
        "numerator_input_readiness": context["numerator_input_readiness"],
        "denominator_input_readiness": context["denominator_input_readiness"],
        "outcome_truth_readiness": context["outcome_truth_readiness"],
        "scoring_support_status": context["scoring_support_status"],
        "effectiveness_score_calculated": False,
        "correctness_calculated": False,
        "rates_calculated": False,
    }


def build_deployed_rule_effectiveness_scoring_contract_plan(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result_id: str,
    effectiveness_spec_result_id: str,
    outcome_truth_source_result_id: str,
    outcome_truth_record_set_id: str,
    observation_window_start: str,
    observation_window_end: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    context = _scoring_contract_context(
        canonical_rule_id=canonical_rule_id,
        production_deployment_result_id=production_deployment_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
        telemetry_snapshot_id=telemetry_snapshot_id,
        readiness_result_id=readiness_result_id,
        effectiveness_spec_result_id=effectiveness_spec_result_id,
        outcome_truth_source_result_id=outcome_truth_source_result_id,
        outcome_truth_record_set_id=outcome_truth_record_set_id,
        observation_window_start=observation_window_start,
        observation_window_end=observation_window_end,
        root=base,
    )
    plan = _plan_payload(context)
    path = _plan_path(base, str(plan["effectiveness_scoring_contract_plan_id"]))
    existing = _read_json(path)
    if isinstance(existing, Mapping):
        if str(existing.get("plan_fingerprint") or "") == str(plan.get("plan_fingerprint") or ""):
            return {
                "status": "planned",
                "effectiveness_scoring_contract_plan_id": plan["effectiveness_scoring_contract_plan_id"],
                "writes_performed": 0,
                **_plan_summary(existing),
            }
        return {
            "status": "corrupt",
            "effectiveness_scoring_contract_plan_id": plan["effectiveness_scoring_contract_plan_id"],
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["effectiveness_scoring_contract_plan_divergence"],
        }
    before_plan = _read_json(path)
    before_index = _read_json(base / "indexes" / PLAN_INDEX)
    try:
        _atomic_write_json(path, plan)
        _update_plan_index(base)
    except Exception:
        _restore_json(path, before_plan)
        _restore_json(base / "indexes" / PLAN_INDEX, before_index)
        return {
            "status": "corrupt",
            "effectiveness_scoring_contract_plan_id": plan["effectiveness_scoring_contract_plan_id"],
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["effectiveness_scoring_contract_plan_write_failure"],
        }
    return {
        "status": "planned",
        "effectiveness_scoring_contract_plan_id": plan["effectiveness_scoring_contract_plan_id"],
        "writes_performed": 1,
        **_plan_summary(plan),
    }


def record_deployed_rule_effectiveness_scoring_contract_result(
    effectiveness_scoring_contract_plan_id: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    if confirmation != REQUIRED_CONFIRMATION:
        return {
            "status": "blocked",
            "effectiveness_scoring_contract_plan_id": effectiveness_scoring_contract_plan_id,
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["effectiveness_scoring_contract_confirmation_required"],
        }
    plan = _read_json(_plan_path(base, effectiveness_scoring_contract_plan_id))
    if not isinstance(plan, Mapping):
        return {
            "status": "blocked",
            "effectiveness_scoring_contract_plan_id": effectiveness_scoring_contract_plan_id,
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["effectiveness_scoring_contract_plan_missing"],
        }
    context = _scoring_contract_context(
        canonical_rule_id=str(plan.get("canonical_rule_id") or ""),
        production_deployment_result_id=str(plan.get("production_deployment_result_id") or ""),
        production_target_id=str(plan.get("production_target_id") or ""),
        deployed_rule_id=str(plan.get("deployed_rule_id") or ""),
        telemetry_snapshot_id=str(plan.get("telemetry_snapshot_id") or ""),
        readiness_result_id=str(plan.get("readiness_result_id") or ""),
        effectiveness_spec_result_id=str(plan.get("effectiveness_spec_result_id") or ""),
        outcome_truth_source_result_id=str(plan.get("outcome_truth_source_result_id") or ""),
        outcome_truth_record_set_id=str(plan.get("outcome_truth_record_set_id") or ""),
        observation_window_start=str(plan.get("observation_window_start") or ""),
        observation_window_end=str(plan.get("observation_window_end") or ""),
        root=base,
    )
    current_plan = _plan_payload(context)
    if str(current_plan.get("plan_fingerprint") or "") != str(plan.get("plan_fingerprint") or ""):
        return {
            "status": "stale",
            "effectiveness_scoring_contract_plan_id": effectiveness_scoring_contract_plan_id,
            "writes_performed": 0,
            "warnings": list(context["warnings"]),
            "blockers": ["effectiveness_scoring_contract_plan_stale"],
        }
    result_id = _result_id(effectiveness_scoring_contract_plan_id)
    receipt_id = _receipt_id(result_id)
    result = {
        "schema_version": SCORING_CONTRACT_RESULT_SCHEMA_VERSION,
        "scoring_contract_schema_version": SCORING_CONTRACT_SCHEMA_VERSION,
        "effectiveness_scoring_contract_result_id": result_id,
        "effectiveness_scoring_contract_plan_id": effectiveness_scoring_contract_plan_id,
        "effectiveness_scoring_contract_receipt_id": receipt_id,
        "scoring_contract_status": context["status"],
        "canonical_rule_id": context["canonical_rule_id"],
        "production_deployment_result_id": context["production_deployment_result_id"],
        "production_target_id": context["production_target_id"],
        "deployed_rule_id": context["deployed_rule_id"],
        "telemetry_snapshot_id": context["telemetry_snapshot_id"],
        "readiness_result_id": context["readiness_result_id"],
        "effectiveness_spec_result_id": context["effectiveness_spec_result_id"],
        "outcome_truth_source_result_id": context["outcome_truth_source_result_id"],
        "outcome_truth_record_set_id": context["outcome_truth_record_set_id"],
        "observation_window_start": context["observation_window_start"],
        "observation_window_end": context["observation_window_end"],
        "metric_contracts": deepcopy(context["metric_contracts"]),
        "denominator_contract": deepcopy(context["denominator_contract"]),
        "numerator_contract": deepcopy(context["numerator_contract"]),
        "criteria": deepcopy(context["criteria"]),
        "warnings": list(context["warnings"]),
        "blockers": list(context["blockers"]),
        "scoring_support_status": context["scoring_support_status"],
        "readiness_result_fingerprint": context["readiness_result_fingerprint"],
        "effectiveness_spec_result_fingerprint": context["effectiveness_spec_result_fingerprint"],
        "outcome_truth_source_result_fingerprint": context["outcome_truth_source_result_fingerprint"],
        "outcome_truth_record_set_fingerprint": context["outcome_truth_record_set_fingerprint"],
        "telemetry_snapshot_fingerprint": context["telemetry_snapshot_fingerprint"],
        "recorded_at_utc": _now(),
        "effectiveness_score_calculated": False,
        "correctness_calculated": False,
        "rates_calculated": False,
    }
    result["result_fingerprint"] = _hash_payload(
        {key: result.get(key) for key in sorted(result) if key not in {"result_fingerprint", "recorded_at_utc"}}
    )
    receipt = {
        "schema_version": SCORING_CONTRACT_RECEIPT_SCHEMA_VERSION,
        "scoring_contract_schema_version": SCORING_CONTRACT_SCHEMA_VERSION,
        "effectiveness_scoring_contract_receipt_id": receipt_id,
        "effectiveness_scoring_contract_result_id": result_id,
        "effectiveness_scoring_contract_plan_id": effectiveness_scoring_contract_plan_id,
        "scoring_contract_status": context["status"],
        "result_fingerprint": result["result_fingerprint"],
        "recorded_at_utc": result["recorded_at_utc"],
    }
    existing = _read_json(_result_path(base, result_id))
    if isinstance(existing, Mapping):
        if str(existing.get("result_fingerprint") or "") == str(result.get("result_fingerprint") or ""):
            return {
                "status": "already_recorded",
                "effectiveness_scoring_contract_result_id": result_id,
                "writes_performed": 0,
                **_result_summary(existing),
            }
        return {
            "status": "corrupt",
            "effectiveness_scoring_contract_result_id": result_id,
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["effectiveness_scoring_contract_result_conflict"],
        }
    before_result = _read_json(_result_path(base, result_id))
    before_receipt = _read_json(_receipt_path(base, receipt_id))
    before_result_index = _read_json(base / "indexes" / RESULT_INDEX)
    before_receipt_index = _read_json(base / "indexes" / RECEIPT_INDEX)
    try:
        _atomic_write_json(_result_path(base, result_id), result)
        _atomic_write_json(_receipt_path(base, receipt_id), receipt)
        _update_result_index(base)
        _update_receipt_index(base)
    except Exception:
        _restore_json(_result_path(base, result_id), before_result)
        _restore_json(_receipt_path(base, receipt_id), before_receipt)
        _restore_json(base / "indexes" / RESULT_INDEX, before_result_index)
        _restore_json(base / "indexes" / RECEIPT_INDEX, before_receipt_index)
        return {
            "status": "corrupt",
            "effectiveness_scoring_contract_result_id": result_id,
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["effectiveness_scoring_contract_result_write_failure"],
        }
    return {
        "status": context["status"],
        "effectiveness_scoring_contract_result_id": result_id,
        "writes_performed": 1,
        **_result_summary(result),
    }


def load_deployed_rule_effectiveness_scoring_contract_result(
    effectiveness_scoring_contract_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = Path(root)
    payload = _read_json(_result_path(base, effectiveness_scoring_contract_result_id))
    if not isinstance(payload, Mapping):
        return {
            "status": "blocked",
            "effectiveness_scoring_contract_result_id": effectiveness_scoring_contract_result_id,
            "warnings": [],
            "blockers": ["effectiveness_scoring_contract_result_missing"],
        }
    receipt = _read_json(_receipt_path(base, str(payload.get("effectiveness_scoring_contract_receipt_id") or "")))
    if not isinstance(receipt, Mapping):
        return {
            "status": "corrupt",
            "effectiveness_scoring_contract_result_id": effectiveness_scoring_contract_result_id,
            "warnings": [],
            "blockers": ["effectiveness_scoring_contract_receipt_missing"],
        }
    return {
        "status": str(payload.get("scoring_contract_status") or "corrupt"),
        "effectiveness_scoring_contract_result": dict(payload),
        "effectiveness_scoring_contract_receipt": dict(receipt),
        "warnings": [],
        "blockers": [],
    }


def get_deployed_rule_effectiveness_scoring_contract_health(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = Path(root)
    plan_items = _load_all(base / PLAN_DIR)
    result_items = _load_all(base / RESULT_DIR)
    receipt_items = _load_all(base / RECEIPT_DIR)
    warnings: list[str] = []
    blockers: list[str] = []
    result_ids = {str(item.get("effectiveness_scoring_contract_result_id") or "") for item in result_items}
    for receipt in receipt_items:
        if str(receipt.get("effectiveness_scoring_contract_result_id") or "") not in result_ids:
            blockers.append("effectiveness_scoring_contract_receipt_references_missing_result")
    indexed_plan_ids = {str(item.get("effectiveness_scoring_contract_plan_id") or "") for item in _index_items(base / "indexes" / PLAN_INDEX)}
    for plan in plan_items:
        if str(plan.get("effectiveness_scoring_contract_plan_id") or "") not in indexed_plan_ids:
            warnings.append("effectiveness_scoring_contract_plan_missing_from_index")
    status = "healthy" if not blockers and not warnings else "warning" if warnings and not blockers else "blocked"
    return {
        "status": status,
        "health_scope": "repository-wide",
        "plan_count": len(plan_items),
        "result_count": len(result_items),
        "receipt_count": len(receipt_items),
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
    }


def format_deployed_rule_effectiveness_scoring_contract_report(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result_id: str,
    effectiveness_spec_result_id: str,
    outcome_truth_source_result_id: str,
    outcome_truth_record_set_id: str,
    observation_window_start: str,
    observation_window_end: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    eligibility = validate_deployed_rule_effectiveness_scoring_contract_eligibility(
        canonical_rule_id,
        production_deployment_result_id,
        production_target_id,
        deployed_rule_id,
        telemetry_snapshot_id,
        readiness_result_id,
        effectiveness_spec_result_id,
        outcome_truth_source_result_id,
        outcome_truth_record_set_id,
        observation_window_start,
        observation_window_end,
        root=root,
    )
    lines = [
        "Deployed Rule Effectiveness Scoring Contract",
        f"Scoring-contract status: {eligibility.get('status')}",
        "This is a scoring contract only; no effectiveness score was calculated.",
        "No correctness score was calculated.",
        "No rate was calculated.",
        "Source availability is not effectiveness.",
        "Execution completion is not correctness.",
        "Phase 9W acceptance is not scoring input.",
        "Future scoring engine remains separate.",
        "Metric families are contract definitions only.",
        "Numerator and denominator contracts are definitions only.",
        f"Scoring support status: {eligibility.get('scoring_support_status')}",
        f"Outcome-truth readiness: {eligibility.get('outcome_truth_readiness')}",
        f"Denominator readiness: {eligibility.get('denominator_input_readiness')}",
        f"Numerator readiness: {eligibility.get('numerator_input_readiness')}",
    ]
    blockers = list(eligibility.get("blockers", []))
    warnings = list(eligibility.get("warnings", []))
    if blockers:
        lines.append("Blockers: " + ", ".join(blockers))
    if warnings:
        lines.append("Warnings: " + ", ".join(warnings))
    lines.append("Recommended next step: " + _recommended_action(str(eligibility.get("status") or "blocked")))
    return "\n".join(lines)


def _scoring_contract_context(
    *,
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result_id: str,
    effectiveness_spec_result_id: str,
    outcome_truth_source_result_id: str,
    outcome_truth_record_set_id: str,
    observation_window_start: str,
    observation_window_end: str,
    root: Path | str,
) -> dict[str, Any]:
    base = Path(root)
    readiness_result_path = readiness_backend._result_path(base, readiness_result_id)
    spec_result_path = spec_backend._result_path(base, effectiveness_spec_result_id)
    truth_result_path = truth_backend._result_path(base, outcome_truth_source_result_id)
    record_set_path = truth_backend._record_set_path(base, outcome_truth_record_set_id)
    snapshot_path = telemetry_backend._snapshot_path(base, telemetry_snapshot_id)
    if not (
        readiness_result_path.exists()
        and spec_result_path.exists()
        and truth_result_path.exists()
        and record_set_path.exists()
        and snapshot_path.exists()
    ):
        criteria = {
            "readiness_result_exists": readiness_result_path.exists(),
            "readiness_result_ready_for_effectiveness_evaluation": False,
            "readiness_result_fingerprint_verified": False,
            "effectiveness_spec_result_exists": spec_result_path.exists(),
            "effectiveness_spec_result_allows_scoring_contract": False,
            "effectiveness_spec_result_fingerprint_verified": False,
            "outcome_truth_source_result_exists": truth_result_path.exists(),
            "outcome_truth_source_available": False,
            "outcome_truth_source_result_fingerprint_verified": False,
            "outcome_truth_record_set_exists": record_set_path.exists(),
            "outcome_truth_records_valid": False,
            "truth_records_bind_to_execution_attempts": False,
            "expected_outcomes_available": False,
            "actual_or_adjudicated_outcomes_available": False,
            "denominator_inputs_defined": False,
            "numerator_inputs_defined": False,
            "unsupported_metrics_excluded": False,
            "phase9w_not_used_as_scoring_input": True,
            "runtime_completion_not_used_as_correctness": True,
            "source_availability_not_used_as_effectiveness": True,
            "effectiveness_score_not_calculated": True,
            "rates_not_calculated": True,
        }
        blockers: list[str] = []
        if not criteria["readiness_result_exists"]:
            blockers.append("effectiveness_readiness_result_missing")
        if not criteria["effectiveness_spec_result_exists"]:
            blockers.append("effectiveness_evaluation_spec_result_missing")
        if not criteria["outcome_truth_source_result_exists"]:
            blockers.append("outcome_truth_source_result_missing")
        if not criteria["outcome_truth_record_set_exists"]:
            blockers.append("outcome_truth_record_set_missing")
        if not snapshot_path.exists():
            blockers.append("telemetry_snapshot_missing")
        return {
            "status": "blocked",
            "canonical_rule_id": canonical_rule_id,
            "production_deployment_result_id": production_deployment_result_id,
            "production_target_id": production_target_id,
            "deployed_rule_id": deployed_rule_id,
            "telemetry_snapshot_id": telemetry_snapshot_id,
            "readiness_result_id": readiness_result_id,
            "effectiveness_spec_result_id": effectiveness_spec_result_id,
            "outcome_truth_source_result_id": outcome_truth_source_result_id,
            "outcome_truth_record_set_id": outcome_truth_record_set_id,
            "observation_window_start": observation_window_start,
            "observation_window_end": observation_window_end,
            "criteria": criteria,
            "blockers": blockers,
            "warnings": [],
            "valid_execution_attempt_count": 0,
            "valid_truth_record_count": 0,
            "metric_contracts": {},
            "denominator_contract": {"denominator_ready": False},
            "numerator_contract": {"numerator_ready": False},
            "denominator_input_readiness": "blocked",
            "numerator_input_readiness": "blocked",
            "outcome_truth_readiness": "blocked",
            "scoring_support_status": "blocked",
            "readiness_result_fingerprint": "",
            "effectiveness_spec_result_fingerprint": "",
            "outcome_truth_source_result_fingerprint": "",
            "outcome_truth_record_set_fingerprint": "",
            "telemetry_snapshot_fingerprint": "",
        }
    manifest = get_deployed_rule_effectiveness_scoring_contract_manifest(root=base)
    readiness_loaded = readiness_backend.load_deployed_rule_effectiveness_readiness_result(readiness_result_id, root=base)
    readiness_result = readiness_loaded.get("effectiveness_readiness_result") if isinstance(readiness_loaded.get("effectiveness_readiness_result"), Mapping) else None
    readiness_receipt = readiness_loaded.get("effectiveness_readiness_receipt") if isinstance(readiness_loaded.get("effectiveness_readiness_receipt"), Mapping) else None
    spec_loaded = spec_backend.load_deployed_rule_effectiveness_evaluation_spec_result(effectiveness_spec_result_id, root=base)
    spec_result = spec_loaded.get("effectiveness_evaluation_spec_result") if isinstance(spec_loaded.get("effectiveness_evaluation_spec_result"), Mapping) else None
    spec_receipt = spec_loaded.get("effectiveness_evaluation_spec_receipt") if isinstance(spec_loaded.get("effectiveness_evaluation_spec_receipt"), Mapping) else None
    truth_loaded = truth_backend.load_deployed_rule_outcome_truth_source_result(outcome_truth_source_result_id, root=base)
    truth_result = truth_loaded.get("outcome_truth_source_result") if isinstance(truth_loaded.get("outcome_truth_source_result"), Mapping) else None
    truth_receipt = truth_loaded.get("outcome_truth_source_receipt") if isinstance(truth_loaded.get("outcome_truth_source_receipt"), Mapping) else None
    record_set_loaded = truth_backend.load_deployed_rule_outcome_truth_record_set(outcome_truth_record_set_id, root=base)
    record_set = record_set_loaded.get("outcome_truth_record_set") if isinstance(record_set_loaded.get("outcome_truth_record_set"), Mapping) else None
    truth_records = list(record_set_loaded.get("outcome_truth_records", [])) if isinstance(record_set_loaded, Mapping) else []
    snapshot = _read_json(telemetry_backend._snapshot_path(base, telemetry_snapshot_id))

    criteria = {
        "readiness_result_exists": False,
        "readiness_result_ready_for_effectiveness_evaluation": False,
        "readiness_result_fingerprint_verified": False,
        "effectiveness_spec_result_exists": False,
        "effectiveness_spec_result_allows_scoring_contract": False,
        "effectiveness_spec_result_fingerprint_verified": False,
        "outcome_truth_source_result_exists": False,
        "outcome_truth_source_available": False,
        "outcome_truth_source_result_fingerprint_verified": False,
        "outcome_truth_record_set_exists": False,
        "outcome_truth_records_valid": False,
        "truth_records_bind_to_execution_attempts": False,
        "expected_outcomes_available": False,
        "actual_or_adjudicated_outcomes_available": False,
        "denominator_inputs_defined": False,
        "numerator_inputs_defined": False,
        "unsupported_metrics_excluded": False,
        "phase9w_not_used_as_scoring_input": True,
        "runtime_completion_not_used_as_correctness": True,
        "source_availability_not_used_as_effectiveness": True,
        "effectiveness_score_not_calculated": True,
        "rates_not_calculated": True,
    }
    blockers: list[str] = []
    warnings: list[str] = []

    valid_execution_attempt_count = int((readiness_result or {}).get("valid_execution_attempt_count") or 0) if isinstance(readiness_result, Mapping) else 0
    snapshot_event_ids = {str(item or "") for item in list((snapshot or {}).get("validated_event_ids", []) or []) if str(item or "")}
    record_items = [dict(item) for item in truth_records if isinstance(item, Mapping)]
    valid_truth_records = [item for item in record_items if str(item.get("truth_status") or "") == "valid"]

    if isinstance(readiness_result, Mapping):
        criteria["readiness_result_exists"] = True
        if spec_backend._readiness_result_fingerprint(readiness_result) == str(readiness_result.get("result_fingerprint") or ""):
            criteria["readiness_result_fingerprint_verified"] = True
        else:
            blockers.append("readiness_result_fingerprint_invalid")
        if not isinstance(readiness_receipt, Mapping) or str(readiness_receipt.get("result_fingerprint") or "") != str(readiness_result.get("result_fingerprint") or ""):
            blockers.append("readiness_receipt_mismatch")
        if (
            str(readiness_result.get("canonical_rule_id") or "") != canonical_rule_id
            or str(readiness_result.get("production_deployment_result_id") or "") != production_deployment_result_id
            or str(readiness_result.get("production_target_id") or "") != production_target_id
            or str(readiness_result.get("deployed_rule_id") or "") != deployed_rule_id
            or str(readiness_result.get("telemetry_snapshot_id") or "") != telemetry_snapshot_id
            or str(readiness_result.get("observation_window_start") or "") != observation_window_start
            or str(readiness_result.get("observation_window_end") or "") != observation_window_end
        ):
            blockers.append("readiness_result_identity_mismatch")
        if str(readiness_result.get("readiness_status") or "") == "ready_for_effectiveness_evaluation":
            criteria["readiness_result_ready_for_effectiveness_evaluation"] = True
    else:
        blockers.append("readiness_result_missing")

    if isinstance(spec_result, Mapping):
        criteria["effectiveness_spec_result_exists"] = True
        if _spec_result_fingerprint(spec_result) == str(spec_result.get("result_fingerprint") or ""):
            criteria["effectiveness_spec_result_fingerprint_verified"] = True
        else:
            blockers.append("effectiveness_spec_result_fingerprint_invalid")
        if not isinstance(spec_receipt, Mapping) or str(spec_receipt.get("result_fingerprint") or "") != str(spec_result.get("result_fingerprint") or ""):
            blockers.append("effectiveness_spec_result_receipt_mismatch")
        if (
            str(spec_result.get("canonical_rule_id") or "") != canonical_rule_id
            or str(spec_result.get("production_deployment_result_id") or "") != production_deployment_result_id
            or str(spec_result.get("production_target_id") or "") != production_target_id
            or str(spec_result.get("deployed_rule_id") or "") != deployed_rule_id
            or str(spec_result.get("telemetry_snapshot_id") or "") != telemetry_snapshot_id
            or str(spec_result.get("readiness_result_id") or "") != readiness_result_id
            or str(spec_result.get("observation_window_start") or "") != observation_window_start
            or str(spec_result.get("observation_window_end") or "") != observation_window_end
        ):
            blockers.append("effectiveness_spec_result_identity_mismatch")
        if str(spec_result.get("spec_status") or "") in {"spec_ready_scoring_blocked_missing_outcome_truth", "spec_ready_for_scoring_engine_design"}:
            criteria["effectiveness_spec_result_allows_scoring_contract"] = True
    else:
        blockers.append("effectiveness_spec_result_missing")

    if isinstance(truth_result, Mapping):
        criteria["outcome_truth_source_result_exists"] = True
        if _result_fingerprint(truth_result) == str(truth_result.get("result_fingerprint") or ""):
            criteria["outcome_truth_source_result_fingerprint_verified"] = True
        else:
            blockers.append("outcome_truth_source_result_fingerprint_invalid")
        if not isinstance(truth_receipt, Mapping) or str(truth_receipt.get("result_fingerprint") or "") != str(truth_result.get("result_fingerprint") or ""):
            blockers.append("outcome_truth_source_result_receipt_mismatch")
        if (
            str(truth_result.get("canonical_rule_id") or "") != canonical_rule_id
            or str(truth_result.get("production_deployment_result_id") or "") != production_deployment_result_id
            or str(truth_result.get("production_target_id") or "") != production_target_id
            or str(truth_result.get("deployed_rule_id") or "") != deployed_rule_id
            or str(truth_result.get("telemetry_snapshot_id") or "") != telemetry_snapshot_id
            or str(truth_result.get("readiness_result_id") or "") != readiness_result_id
            or str(truth_result.get("effectiveness_spec_result_id") or "") != effectiveness_spec_result_id
            or str(truth_result.get("outcome_truth_record_set_id") or "") != outcome_truth_record_set_id
            or str(truth_result.get("observation_window_start") or "") != observation_window_start
            or str(truth_result.get("observation_window_end") or "") != observation_window_end
        ):
            blockers.append("outcome_truth_source_result_identity_mismatch")
        if str(truth_result.get("source_status") or "") == "outcome_truth_source_available":
            criteria["outcome_truth_source_available"] = True
    else:
        blockers.append("outcome_truth_source_result_missing")

    if isinstance(record_set, Mapping):
        criteria["outcome_truth_record_set_exists"] = True
        if (
            str(record_set.get("canonical_rule_id") or "") != canonical_rule_id
            or str(record_set.get("production_deployment_result_id") or "") != production_deployment_result_id
            or str(record_set.get("production_target_id") or "") != production_target_id
            or str(record_set.get("deployed_rule_id") or "") != deployed_rule_id
            or str(record_set.get("telemetry_snapshot_id") or "") != telemetry_snapshot_id
            or str(record_set.get("observation_window_start") or "") != observation_window_start
            or str(record_set.get("observation_window_end") or "") != observation_window_end
        ):
            blockers.append("outcome_truth_record_set_identity_mismatch")
        criteria["outcome_truth_records_valid"] = bool(valid_truth_records) and len(valid_truth_records) == len(record_items)
        criteria["expected_outcomes_available"] = bool(valid_truth_records) and all(bool(str(item.get("expected_outcome") or "").strip()) for item in valid_truth_records)
        criteria["actual_or_adjudicated_outcomes_available"] = bool(valid_truth_records) and all(bool(str(item.get("actual_or_adjudicated_outcome") or "").strip()) for item in valid_truth_records)
        criteria["truth_records_bind_to_execution_attempts"] = bool(valid_truth_records) and all(
            bool(str(item.get("execution_event_id") or "").strip()) and (
                not snapshot_event_ids or str(item.get("execution_event_id") or "") in snapshot_event_ids
            )
            for item in valid_truth_records
        )
    else:
        blockers.append("outcome_truth_record_set_missing")

    denominator_contract = _denominator_contract(
        valid_execution_attempt_count=valid_execution_attempt_count,
        truth_records_valid=criteria["outcome_truth_records_valid"],
        truth_records_bind_to_execution_attempts=criteria["truth_records_bind_to_execution_attempts"],
        expected_outcomes_available=criteria["expected_outcomes_available"],
        actual_outcomes_available=criteria["actual_or_adjudicated_outcomes_available"],
    )
    numerator_contract = _numerator_contract(
        expected_outcomes_available=criteria["expected_outcomes_available"],
        actual_outcomes_available=criteria["actual_or_adjudicated_outcomes_available"],
    )
    criteria["denominator_inputs_defined"] = bool(denominator_contract["denominator_ready"])
    criteria["numerator_inputs_defined"] = bool(numerator_contract["numerator_ready"])
    metric_contracts = _metric_contracts(
        expected_outcomes_available=criteria["expected_outcomes_available"],
        actual_outcomes_available=criteria["actual_or_adjudicated_outcomes_available"],
        denominator_ready=criteria["denominator_inputs_defined"],
        snapshot=snapshot if isinstance(snapshot, Mapping) else None,
    )
    criteria["unsupported_metrics_excluded"] = all(
        bool(item.get("metric_family_status") == "blocked_unsupported" and item.get("unsupported_reason")) or item.get("metric_family_status") == "supported_for_engine_design"
        for item in metric_contracts.values()
        if isinstance(item, Mapping)
    )

    if not criteria["readiness_result_exists"]:
        status = "scoring_contract_blocked_missing_readiness"
    elif not criteria["effectiveness_spec_result_exists"]:
        status = "scoring_contract_blocked_missing_spec"
    elif not criteria["outcome_truth_source_result_exists"] or not criteria["outcome_truth_source_available"] or not criteria["outcome_truth_record_set_exists"]:
        status = "scoring_contract_blocked_missing_outcome_truth"
    elif not criteria["outcome_truth_records_valid"] or not criteria["truth_records_bind_to_execution_attempts"]:
        status = "scoring_contract_blocked_incomplete_truth_records"
    elif not criteria["denominator_inputs_defined"]:
        status = "scoring_contract_blocked_missing_denominator_inputs"
    elif not criteria["numerator_inputs_defined"]:
        status = "scoring_contract_blocked_missing_numerator_inputs"
    elif not _any_metric_family_supported(metric_contracts):
        status = "scoring_contract_blocked_unsupported_metrics"
    elif blockers:
        status = "blocked"
    else:
        status = "scoring_contract_ready_for_engine_design"

    if not criteria["effectiveness_spec_result_allows_scoring_contract"]:
        blockers.append("effectiveness_spec_result_not_ready_for_scoring_contract")
        if status == "scoring_contract_ready_for_engine_design":
            status = "blocked"
    if not criteria["readiness_result_ready_for_effectiveness_evaluation"]:
        blockers.append("readiness_not_ready_for_effectiveness_evaluation")
        if status == "scoring_contract_ready_for_engine_design":
            status = "scoring_contract_blocked_missing_readiness"

    scoring_support_status = "ready_for_engine_design" if status == "scoring_contract_ready_for_engine_design" else "blocked"
    return {
        "status": status,
        "canonical_rule_id": canonical_rule_id,
        "production_deployment_result_id": production_deployment_result_id,
        "production_target_id": production_target_id,
        "deployed_rule_id": deployed_rule_id,
        "telemetry_snapshot_id": telemetry_snapshot_id,
        "readiness_result_id": readiness_result_id,
        "effectiveness_spec_result_id": effectiveness_spec_result_id,
        "outcome_truth_source_result_id": outcome_truth_source_result_id,
        "outcome_truth_record_set_id": outcome_truth_record_set_id,
        "observation_window_start": observation_window_start,
        "observation_window_end": observation_window_end,
        "criteria": criteria,
        "blockers": _dedupe(blockers),
        "warnings": _dedupe(warnings),
        "valid_execution_attempt_count": valid_execution_attempt_count,
        "valid_truth_record_count": len(valid_truth_records),
        "denominator_contract": denominator_contract,
        "numerator_contract": numerator_contract,
        "metric_contracts": metric_contracts,
        "denominator_input_readiness": "ready" if criteria["denominator_inputs_defined"] else "blocked",
        "numerator_input_readiness": "ready" if criteria["numerator_inputs_defined"] else "blocked",
        "outcome_truth_readiness": "ready" if criteria["outcome_truth_source_available"] and criteria["outcome_truth_records_valid"] else "blocked",
        "scoring_support_status": scoring_support_status,
        "readiness_result_fingerprint": str((readiness_result or {}).get("result_fingerprint") or ""),
        "effectiveness_spec_result_fingerprint": str((spec_result or {}).get("result_fingerprint") or ""),
        "outcome_truth_source_result_fingerprint": str((truth_result or {}).get("result_fingerprint") or ""),
        "outcome_truth_record_set_fingerprint": str((record_set or {}).get("record_set_fingerprint") or ""),
        "telemetry_snapshot_fingerprint": str((snapshot or {}).get("snapshot_fingerprint") or "") if isinstance(snapshot, Mapping) else "",
        "manifest": manifest,
    }


def _metric_contracts(
    *,
    expected_outcomes_available: bool,
    actual_outcomes_available: bool,
    denominator_ready: bool,
    snapshot: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    truth_ready = expected_outcomes_available and actual_outcomes_available
    runtime_fields = ["execution_status", "duration_ms"]
    confidence_supported = False
    if isinstance(snapshot, Mapping):
        confidence_supported = bool(snapshot.get("prediction_confidence_available"))
    return {
        "accuracy_like_contract": {
            "metric_family_id": "accuracy_like_contract",
            "metric_family_status": "supported_for_engine_design" if truth_ready and denominator_ready else "blocked_missing_truth_or_denominator",
            "required_numerator_inputs": ["deterministic_comparison_rule", "expected_outcome", "actual_or_adjudicated_outcome"],
            "required_denominator_inputs": ["eligible_execution_attempt_count", "valid_truth_record_count"],
            "required_outcome_truth_fields": ["expected_outcome", "actual_or_adjudicated_outcome"],
            "required_execution_event_fields": ["execution_event_id"],
            "unsupported_reason": None if truth_ready and denominator_ready else "outcome_truth_or_denominator_unavailable",
            "current_evidence_support": truth_ready and denominator_ready,
            "calculation_performed": False,
        },
        "false_positive_false_negative_contract": {
            "metric_family_id": "false_positive_false_negative_contract",
            "metric_family_status": "blocked_unsupported",
            "required_numerator_inputs": ["expected_class", "actual_or_adjudicated_class", "confusion_category_mapping"],
            "required_denominator_inputs": ["classified_execution_attempt_count"],
            "required_outcome_truth_fields": ["expected_outcome", "actual_or_adjudicated_outcome"],
            "required_execution_event_fields": ["execution_event_id"],
            "unsupported_reason": "target_class_semantics_unavailable",
            "current_evidence_support": False,
            "calculation_performed": False,
        },
        "precision_recall_like_contract": {
            "metric_family_id": "precision_recall_like_contract",
            "metric_family_status": "blocked_unsupported",
            "required_numerator_inputs": ["positive_class_definition", "predicted_positive_count", "actual_positive_count"],
            "required_denominator_inputs": ["predicted_positive_population", "actual_positive_population"],
            "required_outcome_truth_fields": ["expected_outcome", "actual_or_adjudicated_outcome"],
            "required_execution_event_fields": ["execution_event_id"],
            "unsupported_reason": "positive_class_definition_unavailable",
            "current_evidence_support": False,
            "calculation_performed": False,
        },
        "calibration_like_contract": {
            "metric_family_id": "calibration_like_contract",
            "metric_family_status": "supported_for_engine_design" if confidence_supported and truth_ready else "blocked_unsupported",
            "required_numerator_inputs": ["predicted_probability_or_confidence", "actual_or_adjudicated_outcome", "binning_rule"],
            "required_denominator_inputs": ["confidence_binned_attempt_count"],
            "required_outcome_truth_fields": ["actual_or_adjudicated_outcome"],
            "required_execution_event_fields": ["execution_event_id", "prediction_confidence"],
            "unsupported_reason": None if confidence_supported and truth_ready else "prediction_confidence_unavailable",
            "current_evidence_support": confidence_supported and truth_ready,
            "calculation_performed": False,
        },
        "runtime_reliability_contract": {
            "metric_family_id": "runtime_reliability_contract",
            "metric_family_status": "supported_for_engine_design" if denominator_ready else "blocked_missing_denominator",
            "required_numerator_inputs": ["completed_execution_count", "failed_execution_count", "duration_availability"],
            "required_denominator_inputs": ["eligible_execution_attempt_count"],
            "required_outcome_truth_fields": [],
            "required_execution_event_fields": runtime_fields,
            "unsupported_reason": None if denominator_ready else "eligible_execution_attempts_unavailable",
            "current_evidence_support": denominator_ready,
            "calculation_performed": False,
        },
    }


def _denominator_contract(
    *,
    valid_execution_attempt_count: int,
    truth_records_valid: bool,
    truth_records_bind_to_execution_attempts: bool,
    expected_outcomes_available: bool,
    actual_outcomes_available: bool,
) -> dict[str, Any]:
    ready = bool(valid_execution_attempt_count > 0 and truth_records_valid and truth_records_bind_to_execution_attempts and expected_outcomes_available and actual_outcomes_available)
    return {
        "eligible_attempts_definition": "execution attempts within the explicit observation window that bind to exactly one valid outcome-truth record",
        "required_execution_binding": "execution_event_id must bind to a validated execution attempt",
        "required_outcome_truth_binding": "truth record must bind to the same canonical rule, deployment result, deployed rule, snapshot, and observation window",
        "duplicate_handling": "exclude duplicate truth records by record fingerprint and unique record id",
        "invalid_or_corrupt_record_exclusion": True,
        "unsupported_skipped_treatment": "unsupported or incomplete truth records do not enter the denominator",
        "observation_window_match_required": True,
        "denominator_ready": ready,
        "calculation_performed": False,
    }


def _numerator_contract(
    *,
    expected_outcomes_available: bool,
    actual_outcomes_available: bool,
) -> dict[str, Any]:
    ready = bool(expected_outcomes_available and actual_outcomes_available)
    return {
        "future_numerator_represents": "future metric-family-specific counts or distributions derived from expected-versus-actual outcome comparison",
        "required_comparison_rule": "deterministic expected-versus-actual comparison rule must be defined by a future scoring engine",
        "required_expected_actual_fields": ["expected_outcome", "actual_or_adjudicated_outcome"],
        "unsupported_reason": None if ready else "expected_or_actual_outcome_missing",
        "numerator_ready": ready,
        "calculation_performed": False,
    }


def _any_metric_family_supported(metric_contracts: Mapping[str, Mapping[str, Any]]) -> bool:
    return any(
        isinstance(item, Mapping) and item.get("metric_family_status") == "supported_for_engine_design"
        for item in metric_contracts.values()
    )


def _spec_result_fingerprint(payload: Mapping[str, Any]) -> str:
    return _hash_payload(
        {key: payload.get(key) for key in sorted(payload) if key not in {"result_fingerprint", "recorded_at_utc"}}
    )


def _result_fingerprint(payload: Mapping[str, Any]) -> str:
    return _hash_payload(
        {key: payload.get(key) for key in sorted(payload) if key not in {"result_fingerprint", "recorded_at_utc"}}
    )


def _plan_payload(context: Mapping[str, Any]) -> dict[str, Any]:
    plan_id = _plan_id(context)
    plan = {
        "schema_version": SCORING_CONTRACT_PLAN_SCHEMA_VERSION,
        "scoring_contract_schema_version": SCORING_CONTRACT_SCHEMA_VERSION,
        "effectiveness_scoring_contract_plan_id": plan_id,
        "canonical_rule_id": context.get("canonical_rule_id"),
        "production_deployment_result_id": context.get("production_deployment_result_id"),
        "production_target_id": context.get("production_target_id"),
        "deployed_rule_id": context.get("deployed_rule_id"),
        "telemetry_snapshot_id": context.get("telemetry_snapshot_id"),
        "readiness_result_id": context.get("readiness_result_id"),
        "effectiveness_spec_result_id": context.get("effectiveness_spec_result_id"),
        "outcome_truth_source_result_id": context.get("outcome_truth_source_result_id"),
        "outcome_truth_record_set_id": context.get("outcome_truth_record_set_id"),
        "observation_window_start": context.get("observation_window_start"),
        "observation_window_end": context.get("observation_window_end"),
        "scoring_contract_status": context.get("status"),
        "metric_contracts": deepcopy(context.get("metric_contracts")),
        "denominator_contract": deepcopy(context.get("denominator_contract")),
        "numerator_contract": deepcopy(context.get("numerator_contract")),
        "criteria": deepcopy(context.get("criteria")),
        "warnings": list(context.get("warnings", [])),
        "blockers": list(context.get("blockers", [])),
        "scoring_support_status": context.get("scoring_support_status"),
        "readiness_result_fingerprint": context.get("readiness_result_fingerprint"),
        "effectiveness_spec_result_fingerprint": context.get("effectiveness_spec_result_fingerprint"),
        "outcome_truth_source_result_fingerprint": context.get("outcome_truth_source_result_fingerprint"),
        "outcome_truth_record_set_fingerprint": context.get("outcome_truth_record_set_fingerprint"),
        "telemetry_snapshot_fingerprint": context.get("telemetry_snapshot_fingerprint"),
        "effectiveness_score_calculated": False,
        "correctness_calculated": False,
        "rates_calculated": False,
    }
    plan["plan_fingerprint"] = _hash_payload(
        {key: plan.get(key) for key in sorted(plan) if key != "plan_fingerprint"}
    )
    return plan


def _plan_summary(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "plan_fingerprint": plan.get("plan_fingerprint"),
        "scoring_contract_status": plan.get("scoring_contract_status"),
        "scoring_support_status": plan.get("scoring_support_status"),
        "warnings": list(plan.get("warnings", [])),
        "blockers": list(plan.get("blockers", [])),
    }


def _result_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "scoring_contract_status": result.get("scoring_contract_status"),
        "result_fingerprint": result.get("result_fingerprint"),
        "warnings": list(result.get("warnings", [])),
        "blockers": list(result.get("blockers", [])),
    }


def _plan_id(context: Mapping[str, Any]) -> str:
    fingerprint = _hash_payload(
        {
            "canonical_rule_id": context.get("canonical_rule_id"),
            "production_deployment_result_id": context.get("production_deployment_result_id"),
            "production_target_id": context.get("production_target_id"),
            "deployed_rule_id": context.get("deployed_rule_id"),
            "telemetry_snapshot_id": context.get("telemetry_snapshot_id"),
            "readiness_result_id": context.get("readiness_result_id"),
            "effectiveness_spec_result_id": context.get("effectiveness_spec_result_id"),
            "outcome_truth_source_result_id": context.get("outcome_truth_source_result_id"),
            "outcome_truth_record_set_id": context.get("outcome_truth_record_set_id"),
            "observation_window_start": context.get("observation_window_start"),
            "observation_window_end": context.get("observation_window_end"),
        }
    )
    return f"deployed_rule_effectiveness_scoring_contract_plan_{fingerprint[:24]}"


def _result_id(plan_id: str) -> str:
    return f"deployed_rule_effectiveness_scoring_contract_result_{_safe_id(plan_id)[-24:]}"


def _receipt_id(result_id: str) -> str:
    return f"deployed_rule_effectiveness_scoring_contract_receipt_{_safe_id(result_id)[-24:]}"


def _plan_path(base: Path, plan_id: str) -> Path:
    return base / PLAN_DIR / f"{_safe_id(plan_id)}.json"


def _result_path(base: Path, result_id: str) -> Path:
    return base / RESULT_DIR / f"{_safe_id(result_id)}.json"


def _receipt_path(base: Path, receipt_id: str) -> Path:
    return base / RECEIPT_DIR / f"{_safe_id(receipt_id)}.json"


def _update_plan_index(base: Path) -> None:
    items = [
        {
            "effectiveness_scoring_contract_plan_id": item.get("effectiveness_scoring_contract_plan_id"),
            "production_deployment_result_id": item.get("production_deployment_result_id"),
            "deployed_rule_id": item.get("deployed_rule_id"),
            "telemetry_snapshot_id": item.get("telemetry_snapshot_id"),
            "scoring_contract_status": item.get("scoring_contract_status"),
            "plan_fingerprint": item.get("plan_fingerprint"),
        }
        for item in _load_all(base / PLAN_DIR)
    ]
    _atomic_write_json(base / "indexes" / PLAN_INDEX, {"schema_version": "deployed_rule_effectiveness_scoring_contract_plan_index_v1", "items": items, "updated_at_utc": _now()})


def _update_result_index(base: Path) -> None:
    items = [
        {
            "effectiveness_scoring_contract_result_id": item.get("effectiveness_scoring_contract_result_id"),
            "effectiveness_scoring_contract_plan_id": item.get("effectiveness_scoring_contract_plan_id"),
            "production_deployment_result_id": item.get("production_deployment_result_id"),
            "deployed_rule_id": item.get("deployed_rule_id"),
            "scoring_contract_status": item.get("scoring_contract_status"),
        }
        for item in _load_all(base / RESULT_DIR)
    ]
    _atomic_write_json(base / "indexes" / RESULT_INDEX, {"schema_version": "deployed_rule_effectiveness_scoring_contract_result_index_v1", "items": items, "updated_at_utc": _now()})


def _update_receipt_index(base: Path) -> None:
    items = [
        {
            "effectiveness_scoring_contract_receipt_id": item.get("effectiveness_scoring_contract_receipt_id"),
            "effectiveness_scoring_contract_result_id": item.get("effectiveness_scoring_contract_result_id"),
            "scoring_contract_status": item.get("scoring_contract_status"),
        }
        for item in _load_all(base / RECEIPT_DIR)
    ]
    _atomic_write_json(base / "indexes" / RECEIPT_INDEX, {"schema_version": "deployed_rule_effectiveness_scoring_contract_receipt_index_v1", "items": items, "updated_at_utc": _now()})


def _index_items(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    items = payload.get("items") if isinstance(payload, Mapping) else None
    if not isinstance(items, list):
        return []
    return [dict(item) for item in items if isinstance(item, Mapping)]


def _load_all(folder: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not folder.exists():
        return items
    for path in sorted(folder.glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping):
            items.append(dict(payload))
    return items


def _ensure_dirs(root: Path | str) -> Path:
    base = Path(root)
    for folder in (PLAN_DIR, RESULT_DIR, RECEIPT_DIR, "indexes"):
        (base / folder).mkdir(parents=True, exist_ok=True)
    for path, schema in (
        (base / "indexes" / PLAN_INDEX, "deployed_rule_effectiveness_scoring_contract_plan_index_v1"),
        (base / "indexes" / RESULT_INDEX, "deployed_rule_effectiveness_scoring_contract_result_index_v1"),
        (base / "indexes" / RECEIPT_INDEX, "deployed_rule_effectiveness_scoring_contract_receipt_index_v1"),
    ):
        if not path.exists():
            _atomic_write_json(path, {"schema_version": schema, "items": [], "updated_at_utc": _now()})
    return base


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        text = str(item or "")
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _recommended_action(status: str) -> str:
    if status == "scoring_contract_ready_for_engine_design":
        return "Proceed to a separate scoring-contract seam or future engine-design phase without executing any score."
    if status == "scoring_contract_blocked_missing_readiness":
        return "Record a valid ready_for_effectiveness_evaluation readiness result first."
    if status == "scoring_contract_blocked_missing_spec":
        return "Record an effectiveness-evaluation specification result first."
    if status == "scoring_contract_blocked_missing_outcome_truth":
        return "Register and record a valid outcome-truth source before building a scoring contract."
    if status == "scoring_contract_blocked_incomplete_truth_records":
        return "Repair outcome-truth record completeness and execution bindings before future scoring work."
    if status == "scoring_contract_blocked_missing_denominator_inputs":
        return "Restore denominator inputs before any future scoring engine work."
    if status == "scoring_contract_blocked_missing_numerator_inputs":
        return "Restore numerator comparison inputs before any future scoring engine work."
    if status == "scoring_contract_blocked_unsupported_metrics":
        return "Limit future scoring-engine work to supported metric families or define the missing semantics first."
    if status == "stale":
        return "Rebuild the scoring-contract plan against current readiness, specification, truth, and telemetry state."
    if status == "corrupt":
        return "Inspect immutable scoring-contract records for divergence before any future scoring work."
    return "Review the scoring-contract evidence chain before any future scoring-engine design."
