"""Specification-only contract for future deployed-rule effectiveness evaluation."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from . import deployed_rule_effectiveness_readiness as readiness_backend
from . import deployed_rule_operational_telemetry as telemetry_backend
from .canonical_rule_runtime import _atomic_write_json, _hash_payload, _now, _read_json, _restore_json, _safe_id
from .rule_effectiveness_analysis import _ensure_analysis_dirs
from .source_documents import SOURCE_DOCUMENT_ROOT

PLAN_DIR = "deployed_rule_effectiveness_evaluation_spec/plans"
RESULT_DIR = "deployed_rule_effectiveness_evaluation_spec/results"
RECEIPT_DIR = "deployed_rule_effectiveness_evaluation_spec/receipts"
PLAN_INDEX = "deployed_rule_effectiveness_evaluation_spec_plan_index.json"
RESULT_INDEX = "deployed_rule_effectiveness_evaluation_spec_result_index.json"
RECEIPT_INDEX = "deployed_rule_effectiveness_evaluation_spec_receipt_index.json"

PLAN_SCHEMA = "deployed_rule_effectiveness_evaluation_spec_plan_v1"
RESULT_SCHEMA = "deployed_rule_effectiveness_evaluation_spec_result_v1"
RECEIPT_SCHEMA = "deployed_rule_effectiveness_evaluation_spec_receipt_v1"
SPEC_SCHEMA_VERSION = "deployed_rule_effectiveness_evaluation_spec_v1"
MANIFEST_SCHEMA = "deployed_rule_effectiveness_evaluation_spec_manifest_v1"
REQUIRED_CONFIRMATION = "RECORD_EFFECTIVENESS_EVALUATION_SPEC_RESULT"
DEFAULT_METRIC_CONTRACT_ID = "deployed_rule_effectiveness_metric_contract_v1"

SPEC_STATUSES = [
    "spec_ready_scoring_blocked_missing_outcome_truth",
    "spec_ready_scoring_blocked_missing_readiness",
    "spec_ready_scoring_blocked_insufficient_events",
    "spec_ready_scoring_blocked_missing_denominator",
    "spec_ready_scoring_blocked_unsupported_metric",
    "spec_ready_for_scoring_engine_design",
    "blocked",
    "stale",
    "corrupt",
]

PUBLIC_FUNCTIONS = [
    "build_deployed_rule_effectiveness_evaluation_spec_workspace",
    "validate_deployed_rule_effectiveness_evaluation_spec_eligibility",
    "build_deployed_rule_effectiveness_evaluation_spec_plan",
    "record_deployed_rule_effectiveness_evaluation_spec_result",
    "load_deployed_rule_effectiveness_evaluation_spec_result",
    "get_deployed_rule_effectiveness_evaluation_spec_health",
    "format_deployed_rule_effectiveness_evaluation_spec_report",
    "get_deployed_rule_effectiveness_evaluation_spec_manifest",
]


def get_deployed_rule_effectiveness_evaluation_spec_manifest(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    telemetry_manifest = telemetry_backend.get_deployed_rule_operational_telemetry_manifest(root=root)
    producer = _execution_producer(telemetry_manifest)
    metric_contract = _metric_contract(outcome_truth_available=False, denominator_contract_available=False)
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "effectiveness_evaluation_spec_schema_version": SPEC_SCHEMA_VERSION,
        "required_identifiers": [
            "canonical_rule_id",
            "production_deployment_result_id",
            "production_target_id",
            "deployed_rule_id",
            "telemetry_snapshot_id",
            "readiness_result_id",
            "observation_window_start",
            "observation_window_end",
        ],
        "spec_statuses": list(SPEC_STATUSES),
        "metric_contract_id": DEFAULT_METRIC_CONTRACT_ID,
        "execution_producer_available": bool(producer),
        "execution_producer_id": (producer or {}).get("producer_id"),
        "runtime_completion_not_correctness": True,
        "phase_9w_not_effectiveness_evidence": True,
        "outcome_truth_source_status": "unavailable_in_repository",
        "effectiveness_evaluation_status": "not_performed",
        "supported_metric_categories": sorted(metric_contract),
    }
    manifest["manifest_fingerprint"] = _hash_payload(
        {key: manifest.get(key) for key in sorted(manifest) if key != "manifest_fingerprint"}
    )
    return manifest


def build_deployed_rule_effectiveness_evaluation_spec_workspace(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result_id: str,
    observation_window_start: str,
    observation_window_end: str,
    *,
    metric_contract_id: str | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    context = _spec_context(
        canonical_rule_id=canonical_rule_id,
        production_deployment_result_id=production_deployment_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
        telemetry_snapshot_id=telemetry_snapshot_id,
        readiness_result_id=readiness_result_id,
        observation_window_start=observation_window_start,
        observation_window_end=observation_window_end,
        metric_contract_id=metric_contract_id,
        root=root,
    )
    return {
        "status": context["status"],
        "canonical_rule_id": canonical_rule_id,
        "production_deployment_result_id": production_deployment_result_id,
        "production_target_id": production_target_id,
        "deployed_rule_id": deployed_rule_id,
        "telemetry_snapshot_id": telemetry_snapshot_id,
        "readiness_result_id": readiness_result_id,
        "observation_window_start": observation_window_start,
        "observation_window_end": observation_window_end,
        "readiness_status": context["readiness_status"],
        "execution_producer_status": "available" if context["execution_producer"] else "missing",
        "execution_attempt_count": context["execution_attempt_count"],
        "denominator_readiness": context["denominator_readiness"],
        "sample_sufficiency_status": context["sample_sufficiency_status"],
        "outcome_truth_status": context["outcome_truth_status"],
        "metric_contract_id": context["metric_contract_id"],
        "metric_contract_status": context["metric_contract_status"],
        "scoring_support_status": context["scoring_support_status"],
        "metric_contract": deepcopy(context["metric_contract"]),
        "warnings": list(context["warnings"]),
        "blockers": list(context["blockers"]),
        "recommended_action": _recommended_action(context["status"]),
    }


def validate_deployed_rule_effectiveness_evaluation_spec_eligibility(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result_id: str,
    observation_window_start: str,
    observation_window_end: str,
    *,
    metric_contract_id: str | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    context = _spec_context(
        canonical_rule_id=canonical_rule_id,
        production_deployment_result_id=production_deployment_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
        telemetry_snapshot_id=telemetry_snapshot_id,
        readiness_result_id=readiness_result_id,
        observation_window_start=observation_window_start,
        observation_window_end=observation_window_end,
        metric_contract_id=metric_contract_id,
        root=root,
    )
    return {
        "status": context["status"],
        "criteria": deepcopy(context["criteria"]),
        "blockers": list(context["blockers"]),
        "warnings": list(context["warnings"]),
        "readiness_status": context["readiness_status"],
        "valid_execution_attempt_count": context["execution_attempt_count"],
        "outcome_truth_status": context["outcome_truth_status"],
        "metric_contract_status": context["metric_contract_status"],
        "scoring_support_status": context["scoring_support_status"],
        "effectiveness_evaluation_status": context["effectiveness_evaluation_status"],
        "recommended_action": _recommended_action(context["status"]),
    }


def build_deployed_rule_effectiveness_evaluation_spec_plan(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result_id: str,
    observation_window_start: str,
    observation_window_end: str,
    *,
    metric_contract_id: str | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    context = _spec_context(
        canonical_rule_id=canonical_rule_id,
        production_deployment_result_id=production_deployment_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
        telemetry_snapshot_id=telemetry_snapshot_id,
        readiness_result_id=readiness_result_id,
        observation_window_start=observation_window_start,
        observation_window_end=observation_window_end,
        metric_contract_id=metric_contract_id,
        root=base,
    )
    plan = _plan_payload(context)
    path = _plan_path(base, str(plan["effectiveness_evaluation_spec_plan_id"]))
    existing = _read_json(path)
    if isinstance(existing, Mapping):
        if str(existing.get("plan_fingerprint") or "") == str(plan.get("plan_fingerprint") or ""):
            return {
                "status": "planned",
                "effectiveness_evaluation_spec_plan_id": plan["effectiveness_evaluation_spec_plan_id"],
                "writes_performed": 0,
                **_plan_summary(existing),
            }
        return {
            "status": "corrupt",
            "effectiveness_evaluation_spec_plan_id": plan["effectiveness_evaluation_spec_plan_id"],
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["effectiveness_evaluation_spec_plan_divergence"],
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
            "effectiveness_evaluation_spec_plan_id": plan["effectiveness_evaluation_spec_plan_id"],
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["effectiveness_evaluation_spec_plan_write_failure"],
        }
    return {
        "status": "planned",
        "effectiveness_evaluation_spec_plan_id": plan["effectiveness_evaluation_spec_plan_id"],
        "writes_performed": 1,
        **_plan_summary(plan),
    }


def record_deployed_rule_effectiveness_evaluation_spec_result(
    effectiveness_evaluation_spec_plan_id: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    if confirmation != REQUIRED_CONFIRMATION:
        return {
            "status": "blocked",
            "effectiveness_evaluation_spec_plan_id": effectiveness_evaluation_spec_plan_id,
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["effectiveness_evaluation_spec_confirmation_required"],
        }
    plan = _read_json(_plan_path(base, effectiveness_evaluation_spec_plan_id))
    if not isinstance(plan, Mapping):
        return {
            "status": "blocked",
            "effectiveness_evaluation_spec_plan_id": effectiveness_evaluation_spec_plan_id,
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["effectiveness_evaluation_spec_plan_missing"],
        }
    context = _spec_context(
        canonical_rule_id=str(plan.get("canonical_rule_id") or ""),
        production_deployment_result_id=str(plan.get("production_deployment_result_id") or ""),
        production_target_id=str(plan.get("production_target_id") or ""),
        deployed_rule_id=str(plan.get("deployed_rule_id") or ""),
        telemetry_snapshot_id=str(plan.get("telemetry_snapshot_id") or ""),
        readiness_result_id=str(plan.get("readiness_result_id") or ""),
        observation_window_start=str(plan.get("observation_window_start") or ""),
        observation_window_end=str(plan.get("observation_window_end") or ""),
        metric_contract_id=_text(plan.get("metric_contract_id")),
        root=base,
    )
    current_plan = _plan_payload(context)
    if str(current_plan.get("plan_fingerprint") or "") != str(plan.get("plan_fingerprint") or ""):
        return {
            "status": "stale",
            "effectiveness_evaluation_spec_plan_id": effectiveness_evaluation_spec_plan_id,
            "writes_performed": 0,
            "warnings": list(context["warnings"]),
            "blockers": ["effectiveness_evaluation_spec_plan_stale"],
        }
    result_id = _result_id(effectiveness_evaluation_spec_plan_id)
    receipt_id = _receipt_id(result_id)
    result = {
        "schema_version": RESULT_SCHEMA,
        "effectiveness_evaluation_spec_schema_version": SPEC_SCHEMA_VERSION,
        "effectiveness_evaluation_spec_result_id": result_id,
        "effectiveness_evaluation_spec_plan_id": effectiveness_evaluation_spec_plan_id,
        "effectiveness_evaluation_spec_receipt_id": receipt_id,
        **{
            key: current_plan.get(key)
            for key in (
                "canonical_rule_id",
                "production_deployment_result_id",
                "production_target_id",
                "deployed_rule_id",
                "telemetry_snapshot_id",
                "readiness_result_id",
                "observation_window_start",
                "observation_window_end",
                "readiness_status",
                "valid_execution_attempt_count",
                "outcome_truth_status",
                "metric_contract_id",
                "metric_contract_status",
                "scoring_support_status",
                "criteria",
                "warnings",
                "blockers",
                "effectiveness_evaluation_status",
                "readiness_result_fingerprint",
                "telemetry_snapshot_fingerprint",
                "plan_fingerprint",
            )
        },
        "spec_status": context["status"],
        "recorded_at_utc": _now(),
    }
    result["result_fingerprint"] = _hash_payload(
        {key: result.get(key) for key in sorted(result) if key not in {"result_fingerprint", "recorded_at_utc"}}
    )
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "effectiveness_evaluation_spec_schema_version": SPEC_SCHEMA_VERSION,
        "effectiveness_evaluation_spec_receipt_id": receipt_id,
        "effectiveness_evaluation_spec_result_id": result_id,
        "effectiveness_evaluation_spec_plan_id": effectiveness_evaluation_spec_plan_id,
        "spec_status": context["status"],
        "result_fingerprint": result["result_fingerprint"],
        "recorded_at_utc": result["recorded_at_utc"],
    }
    existing = _read_json(_result_path(base, result_id))
    if isinstance(existing, Mapping):
        if str(existing.get("result_fingerprint") or "") == str(result.get("result_fingerprint") or ""):
            return {
                "status": "already_recorded",
                "effectiveness_evaluation_spec_result_id": result_id,
                "writes_performed": 0,
                **_result_summary(existing),
            }
        return {
            "status": "conflict",
            "effectiveness_evaluation_spec_result_id": result_id,
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["effectiveness_evaluation_spec_result_conflict"],
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
            "effectiveness_evaluation_spec_result_id": result_id,
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["effectiveness_evaluation_spec_result_write_failure"],
        }
    return {
        "status": context["status"],
        "effectiveness_evaluation_spec_result_id": result_id,
        "writes_performed": 1,
        **_result_summary(result),
    }


def load_deployed_rule_effectiveness_evaluation_spec_result(
    effectiveness_evaluation_spec_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    payload = _read_json(_result_path(base, effectiveness_evaluation_spec_result_id))
    if not isinstance(payload, Mapping):
        return {
            "status": "blocked",
            "effectiveness_evaluation_spec_result_id": effectiveness_evaluation_spec_result_id,
            "warnings": [],
            "blockers": ["effectiveness_evaluation_spec_result_missing"],
        }
    receipt = _read_json(_receipt_path(base, str(payload.get("effectiveness_evaluation_spec_receipt_id") or "")))
    if not isinstance(receipt, Mapping):
        return {
            "status": "corrupt",
            "effectiveness_evaluation_spec_result_id": effectiveness_evaluation_spec_result_id,
            "warnings": [],
            "blockers": ["effectiveness_evaluation_spec_receipt_missing"],
        }
    return {
        "status": str(payload.get("spec_status") or "corrupt"),
        "effectiveness_evaluation_spec_result": dict(payload),
        "effectiveness_evaluation_spec_receipt": dict(receipt),
        "warnings": [],
        "blockers": [],
    }


def get_deployed_rule_effectiveness_evaluation_spec_health(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_dirs(root)
    plan_items = _load_all(base / PLAN_DIR)
    result_items = _load_all(base / RESULT_DIR)
    receipt_items = _load_all(base / RECEIPT_DIR)
    warnings: list[str] = []
    blockers: list[str] = []
    result_ids = {str(item.get("effectiveness_evaluation_spec_result_id") or "") for item in result_items}
    for receipt in receipt_items:
        if str(receipt.get("effectiveness_evaluation_spec_result_id") or "") not in result_ids:
            blockers.append("effectiveness_evaluation_spec_receipt_references_missing_result")
    indexed_plan_ids = {str(item.get("effectiveness_evaluation_spec_plan_id") or "") for item in _index_items(base / "indexes" / PLAN_INDEX)}
    for plan in plan_items:
        if str(plan.get("effectiveness_evaluation_spec_plan_id") or "") not in indexed_plan_ids:
            warnings.append("effectiveness_evaluation_spec_plan_missing_from_index")
    status = "healthy" if not blockers and not warnings else "warning" if warnings and not blockers else "blocked"
    return {
        "status": status,
        "plan_count": len(plan_items),
        "result_count": len(result_items),
        "receipt_count": len(receipt_items),
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
    }


def format_deployed_rule_effectiveness_evaluation_spec_report(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result_id: str,
    observation_window_start: str,
    observation_window_end: str,
    *,
    metric_contract_id: str | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    eligibility = validate_deployed_rule_effectiveness_evaluation_spec_eligibility(
        canonical_rule_id,
        production_deployment_result_id,
        production_target_id,
        deployed_rule_id,
        telemetry_snapshot_id,
        readiness_result_id,
        observation_window_start,
        observation_window_end,
        metric_contract_id=metric_contract_id,
        root=root,
    )
    lines = [
        "Deployed Rule Effectiveness Evaluation Specification",
        f"Canonical rule ID: {canonical_rule_id}",
        f"Deployed rule ID: {deployed_rule_id}",
        f"Production deployment result ID: {production_deployment_result_id}",
        f"Telemetry snapshot ID: {telemetry_snapshot_id}",
        f"Readiness result ID: {readiness_result_id}",
        f"Specification status: {eligibility.get('status')}",
        "This is specification only; no effectiveness score was calculated.",
        "Readiness is not effectiveness.",
        "Execution completion is not correctness.",
        "Absence of failures is not success.",
        "Phase 9W acceptance is not effectiveness evidence.",
        f"Outcome-truth status: {eligibility.get('outcome_truth_status')}",
        f"Metric contract status: {eligibility.get('metric_contract_status')}",
        f"Scoring support status: {eligibility.get('scoring_support_status')}",
        f"Readiness status: {eligibility.get('readiness_status')}",
        f"Valid execution attempts: {eligibility.get('valid_execution_attempt_count')}",
        f"Effectiveness evaluation status: {eligibility.get('effectiveness_evaluation_status')}",
    ]
    blockers = list(eligibility.get("blockers", []))
    warnings = list(eligibility.get("warnings", []))
    if blockers:
        lines.append("Blockers: " + ", ".join(blockers))
    if warnings:
        lines.append("Warnings: " + ", ".join(warnings))
    lines.append("Recommended next step: " + str(eligibility.get("recommended_action") or "Define a grounded outcome-truth source before any scoring design."))
    return "\n".join(lines)


def _spec_context(
    *,
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result_id: str,
    observation_window_start: str,
    observation_window_end: str,
    metric_contract_id: str | None,
    root: Path | str,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    manifest = get_deployed_rule_effectiveness_evaluation_spec_manifest(root=base)
    readiness_loaded = readiness_backend.load_deployed_rule_effectiveness_readiness_result(readiness_result_id, root=base)
    readiness_result = readiness_loaded.get("effectiveness_readiness_result") if isinstance(readiness_loaded.get("effectiveness_readiness_result"), Mapping) else None
    readiness_receipt = readiness_loaded.get("effectiveness_readiness_receipt") if isinstance(readiness_loaded.get("effectiveness_readiness_receipt"), Mapping) else None
    readiness_plan = _read_json(
        readiness_backend._plan_path(base, str((readiness_result or {}).get("effectiveness_readiness_plan_id") or ""))
    )
    snapshot = _read_json(telemetry_backend._snapshot_path(base, telemetry_snapshot_id))
    telemetry_manifest = telemetry_backend.get_deployed_rule_operational_telemetry_manifest(root=base)
    producer = _execution_producer(telemetry_manifest)
    blockers: list[str] = []
    warnings: list[str] = []
    criteria = {
        "readiness_result_exists": False,
        "readiness_result_ready_for_effectiveness_evaluation": False,
        "readiness_result_fingerprint_verified": False,
        "telemetry_snapshot_exists": False,
        "telemetry_snapshot_fingerprint_verified": False,
        "execution_events_present": False,
        "valid_execution_attempts_sufficient": False,
        "denominator_contract_available": False,
        "runtime_completion_not_treated_as_correctness": True,
        "phase_9w_not_used_as_effectiveness_evidence": True,
        "outcome_truth_source_available": False,
        "outcome_truth_binding_defined": False,
        "metric_contract_defined": False,
        "unsupported_metrics_excluded": False,
        "effectiveness_score_not_calculated": True,
    }

    readiness_status = str((readiness_result or {}).get("readiness_status") or "")
    if isinstance(readiness_result, Mapping):
        criteria["readiness_result_exists"] = True
        if _readiness_result_fingerprint(readiness_result) == str(readiness_result.get("result_fingerprint") or ""):
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
        if readiness_status == "ready_for_effectiveness_evaluation":
            criteria["readiness_result_ready_for_effectiveness_evaluation"] = True
    else:
        blockers.append("readiness_result_missing")

    if isinstance(snapshot, Mapping):
        criteria["telemetry_snapshot_exists"] = True
        if str(snapshot.get("snapshot_fingerprint") or "") == str(telemetry_backend._snapshot_fingerprint(snapshot) or ""):
            criteria["telemetry_snapshot_fingerprint_verified"] = True
        else:
            blockers.append("telemetry_snapshot_fingerprint_invalid")
    else:
        blockers.append("telemetry_snapshot_missing")

    execution_attempt_count = int((readiness_result or {}).get("valid_execution_attempt_count") or 0) if isinstance(readiness_result, Mapping) else 0
    denominator_readiness = str((readiness_result or {}).get("denominator_readiness") or "not_ready") if isinstance(readiness_result, Mapping) else "not_ready"
    sample_sufficiency_status = str((readiness_result or {}).get("sample_sufficiency_status") or "not_met") if isinstance(readiness_result, Mapping) else "not_met"
    if int((readiness_result or {}).get("execution_event_count") or 0) > 0:
        criteria["execution_events_present"] = True
    if execution_attempt_count >= readiness_backend.MINIMUM_EXECUTION_ATTEMPTS:
        criteria["valid_execution_attempts_sufficient"] = True
    if denominator_readiness == "ready":
        criteria["denominator_contract_available"] = True

    metric_contract = _metric_contract(
        outcome_truth_available=criteria["outcome_truth_source_available"],
        denominator_contract_available=criteria["denominator_contract_available"],
    )
    criteria["metric_contract_defined"] = True
    criteria["unsupported_metrics_excluded"] = True

    effectiveness_evaluation_status = str((readiness_result or {}).get("effectiveness_evaluation_status") or manifest.get("effectiveness_evaluation_status") or "not_performed")
    if effectiveness_evaluation_status != "not_performed":
        blockers.append("effectiveness_evaluation_already_performed")

    if not criteria["readiness_result_exists"]:
        status = "spec_ready_scoring_blocked_missing_readiness"
    elif not criteria["readiness_result_fingerprint_verified"] or not criteria["telemetry_snapshot_fingerprint_verified"]:
        status = "corrupt"
    elif "readiness_result_identity_mismatch" in blockers:
        status = "stale"
    elif not criteria["readiness_result_ready_for_effectiveness_evaluation"]:
        blockers.append(f"readiness_status_{readiness_status or 'missing'}")
        status = "spec_ready_scoring_blocked_missing_readiness"
    elif not criteria["execution_events_present"] or not criteria["valid_execution_attempts_sufficient"]:
        status = "spec_ready_scoring_blocked_insufficient_events"
    elif not criteria["denominator_contract_available"]:
        status = "spec_ready_scoring_blocked_missing_denominator"
    elif not criteria["outcome_truth_source_available"] or not criteria["outcome_truth_binding_defined"]:
        blockers.append("outcome_truth_source_unavailable")
        status = "spec_ready_scoring_blocked_missing_outcome_truth"
    elif not _any_scoring_metric_supported(metric_contract):
        status = "spec_ready_scoring_blocked_unsupported_metric"
    else:
        status = "spec_ready_for_scoring_engine_design"

    scoring_support_status = "blocked_missing_outcome_truth" if status == "spec_ready_scoring_blocked_missing_outcome_truth" else "ready_for_engine_design" if status == "spec_ready_for_scoring_engine_design" else "blocked"
    metric_contract_status = "defined_without_outcome_truth" if not criteria["outcome_truth_source_available"] else "defined"
    outcome_truth_status = "unavailable_in_repository"
    return {
        "base": base,
        "status": status,
        "canonical_rule_id": canonical_rule_id,
        "production_deployment_result_id": production_deployment_result_id,
        "production_target_id": production_target_id,
        "deployed_rule_id": deployed_rule_id,
        "telemetry_snapshot_id": telemetry_snapshot_id,
        "readiness_result_id": readiness_result_id,
        "observation_window_start": observation_window_start,
        "observation_window_end": observation_window_end,
        "manifest": manifest,
        "execution_producer": producer,
        "readiness_status": readiness_status or "missing",
        "readiness_plan": dict(readiness_plan) if isinstance(readiness_plan, Mapping) else None,
        "readiness_result": dict(readiness_result) if isinstance(readiness_result, Mapping) else None,
        "readiness_receipt": dict(readiness_receipt) if isinstance(readiness_receipt, Mapping) else None,
        "readiness_result_fingerprint": str((readiness_result or {}).get("result_fingerprint") or ""),
        "telemetry_snapshot": dict(snapshot) if isinstance(snapshot, Mapping) else None,
        "telemetry_snapshot_fingerprint": str((snapshot or {}).get("snapshot_fingerprint") or "") if isinstance(snapshot, Mapping) else "",
        "criteria": criteria,
        "blockers": _dedupe(blockers),
        "warnings": _dedupe(warnings),
        "execution_attempt_count": execution_attempt_count,
        "denominator_readiness": denominator_readiness,
        "sample_sufficiency_status": sample_sufficiency_status,
        "outcome_truth_status": outcome_truth_status,
        "metric_contract_id": _normalize_metric_contract_id(metric_contract_id),
        "metric_contract_status": metric_contract_status,
        "metric_contract": metric_contract,
        "scoring_support_status": scoring_support_status,
        "effectiveness_evaluation_status": effectiveness_evaluation_status,
    }


def _metric_contract(*, outcome_truth_available: bool, denominator_contract_available: bool) -> dict[str, dict[str, Any]]:
    missing_truth = "outcome_truth_source_unavailable"
    return {
        "accuracy_like_metric": {
            "required_inputs": ["expected_outcome", "actual_outcome", "correctness_label"],
            "required_denominator": "adjudicated_execution_attempt_count",
            "required_numerator": "correct_prediction_count",
            "current_telemetry_support": False,
            "outcome_truth_required": True,
            "unsupported_reason": None if outcome_truth_available and denominator_contract_available else missing_truth,
        },
        "precision_recall_like_metric": {
            "required_inputs": ["expected_outcome", "actual_outcome", "prediction_label"],
            "required_denominator": "positive_and_negative_label_population",
            "required_numerator": "true_positive_false_positive_false_negative_counts",
            "current_telemetry_support": False,
            "outcome_truth_required": True,
            "unsupported_reason": None if outcome_truth_available and denominator_contract_available else missing_truth,
        },
        "false_positive_false_negative_metric": {
            "required_inputs": ["expected_outcome", "actual_outcome", "prediction_label"],
            "required_denominator": "classified_execution_attempt_count",
            "required_numerator": "false_positive_and_false_negative_counts",
            "current_telemetry_support": False,
            "outcome_truth_required": True,
            "unsupported_reason": None if outcome_truth_available and denominator_contract_available else missing_truth,
        },
        "calibration_like_metric": {
            "required_inputs": ["expected_outcome", "actual_outcome", "prediction_confidence"],
            "required_denominator": "confidence_binned_execution_attempt_count",
            "required_numerator": "observed_outcome_distribution_by_bin",
            "current_telemetry_support": False,
            "outcome_truth_required": True,
            "unsupported_reason": None if outcome_truth_available and denominator_contract_available else missing_truth,
        },
        "latency_or_runtime_reliability_metric": {
            "required_inputs": ["duration_ms", "execution_status", "runtime_outcome_status"],
            "required_denominator": "valid_execution_attempt_count",
            "required_numerator": "successful_runtime_completion_count_or_latency_samples",
            "current_telemetry_support": True,
            "outcome_truth_required": False,
            "unsupported_reason": None if denominator_contract_available else "denominator_contract_unavailable",
        },
    }


def _any_scoring_metric_supported(metric_contract: Mapping[str, Mapping[str, Any]]) -> bool:
    for item in metric_contract.values():
        if not isinstance(item, Mapping):
            continue
        if item.get("unsupported_reason") is None:
            return True
    return False


def _readiness_result_fingerprint(payload: Mapping[str, Any]) -> str:
    return _hash_payload(
        {key: payload.get(key) for key in sorted(payload) if key not in {"result_fingerprint", "recorded_at_utc"}}
    )


def _execution_producer(manifest: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    producers = list((manifest or {}).get("producers", []) or [])
    for item in producers:
        if isinstance(item, Mapping) and str(item.get("producer_id") or "") == telemetry_backend.EXECUTION_PRODUCER_ID:
            return item
    return None


def _plan_payload(context: Mapping[str, Any]) -> dict[str, Any]:
    plan_id = _plan_id(
        str(context.get("canonical_rule_id") or ""),
        str(context.get("production_deployment_result_id") or ""),
        str(context.get("production_target_id") or ""),
        str(context.get("deployed_rule_id") or ""),
        str(context.get("telemetry_snapshot_id") or ""),
        str(context.get("readiness_result_id") or ""),
        str(context.get("observation_window_start") or ""),
        str(context.get("observation_window_end") or ""),
        str(context.get("metric_contract_id") or ""),
    )
    plan = {
        "schema_version": PLAN_SCHEMA,
        "effectiveness_evaluation_spec_schema_version": SPEC_SCHEMA_VERSION,
        "effectiveness_evaluation_spec_plan_id": plan_id,
        "canonical_rule_id": context.get("canonical_rule_id"),
        "production_deployment_result_id": context.get("production_deployment_result_id"),
        "production_target_id": context.get("production_target_id"),
        "deployed_rule_id": context.get("deployed_rule_id"),
        "telemetry_snapshot_id": context.get("telemetry_snapshot_id"),
        "readiness_result_id": context.get("readiness_result_id"),
        "observation_window_start": context.get("observation_window_start"),
        "observation_window_end": context.get("observation_window_end"),
        "readiness_status": context.get("readiness_status"),
        "valid_execution_attempt_count": context.get("execution_attempt_count"),
        "outcome_truth_status": context.get("outcome_truth_status"),
        "metric_contract_id": context.get("metric_contract_id"),
        "metric_contract_status": context.get("metric_contract_status"),
        "scoring_support_status": context.get("scoring_support_status"),
        "criteria": deepcopy(context.get("criteria")),
        "warnings": list(context.get("warnings", [])),
        "blockers": list(context.get("blockers", [])),
        "effectiveness_evaluation_status": context.get("effectiveness_evaluation_status"),
        "readiness_result_fingerprint": context.get("readiness_result_fingerprint"),
        "telemetry_snapshot_fingerprint": context.get("telemetry_snapshot_fingerprint"),
    }
    plan["plan_fingerprint"] = _hash_payload(
        {key: plan.get(key) for key in sorted(plan) if key not in {"plan_fingerprint"}}
    )
    return plan


def _plan_summary(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "plan_fingerprint": plan.get("plan_fingerprint"),
        "scoring_support_status": plan.get("scoring_support_status"),
        "readiness_status": plan.get("readiness_status"),
        "metric_contract_status": plan.get("metric_contract_status"),
        "outcome_truth_status": plan.get("outcome_truth_status"),
        "warnings": list(plan.get("warnings", [])),
        "blockers": list(plan.get("blockers", [])),
    }


def _result_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "spec_status": result.get("spec_status"),
        "result_fingerprint": result.get("result_fingerprint"),
        "warnings": list(result.get("warnings", [])),
        "blockers": list(result.get("blockers", [])),
    }


def _plan_id(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result_id: str,
    observation_window_start: str,
    observation_window_end: str,
    metric_contract_id: str,
) -> str:
    fingerprint = _hash_payload(
        {
            "canonical_rule_id": canonical_rule_id,
            "production_deployment_result_id": production_deployment_result_id,
            "production_target_id": production_target_id,
            "deployed_rule_id": deployed_rule_id,
            "telemetry_snapshot_id": telemetry_snapshot_id,
            "readiness_result_id": readiness_result_id,
            "observation_window_start": observation_window_start,
            "observation_window_end": observation_window_end,
            "metric_contract_id": metric_contract_id,
        }
    )
    return f"deployed_rule_effectiveness_evaluation_spec_plan_{fingerprint[:24]}"


def _result_id(plan_id: str) -> str:
    return f"deployed_rule_effectiveness_evaluation_spec_result_{_safe_id(plan_id)[-24:]}"


def _receipt_id(result_id: str) -> str:
    return f"deployed_rule_effectiveness_evaluation_spec_receipt_{_safe_id(result_id)[-24:]}"


def _plan_path(base: Path, plan_id: str) -> Path:
    return base / PLAN_DIR / f"{_safe_id(plan_id)}.json"


def _result_path(base: Path, result_id: str) -> Path:
    return base / RESULT_DIR / f"{_safe_id(result_id)}.json"


def _receipt_path(base: Path, receipt_id: str) -> Path:
    return base / RECEIPT_DIR / f"{_safe_id(receipt_id)}.json"


def _update_plan_index(base: Path) -> None:
    items = []
    for path in sorted((base / PLAN_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping):
            items.append(
                {
                    "effectiveness_evaluation_spec_plan_id": payload.get("effectiveness_evaluation_spec_plan_id"),
                    "canonical_rule_id": payload.get("canonical_rule_id"),
                    "deployed_rule_id": payload.get("deployed_rule_id"),
                    "telemetry_snapshot_id": payload.get("telemetry_snapshot_id"),
                    "readiness_result_id": payload.get("readiness_result_id"),
                    "plan_fingerprint": payload.get("plan_fingerprint"),
                }
            )
    _atomic_write_json(base / "indexes" / PLAN_INDEX, {"schema_version": "deployed_rule_effectiveness_evaluation_spec_plan_index_v1", "items": items, "updated_at_utc": _now()})


def _update_result_index(base: Path) -> None:
    items = []
    for path in sorted((base / RESULT_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping):
            items.append(
                {
                    "effectiveness_evaluation_spec_result_id": payload.get("effectiveness_evaluation_spec_result_id"),
                    "effectiveness_evaluation_spec_plan_id": payload.get("effectiveness_evaluation_spec_plan_id"),
                    "spec_status": payload.get("spec_status"),
                    "result_fingerprint": payload.get("result_fingerprint"),
                }
            )
    _atomic_write_json(base / "indexes" / RESULT_INDEX, {"schema_version": "deployed_rule_effectiveness_evaluation_spec_result_index_v1", "items": items, "updated_at_utc": _now()})


def _update_receipt_index(base: Path) -> None:
    items = []
    for path in sorted((base / RECEIPT_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping):
            items.append(
                {
                    "effectiveness_evaluation_spec_receipt_id": payload.get("effectiveness_evaluation_spec_receipt_id"),
                    "effectiveness_evaluation_spec_result_id": payload.get("effectiveness_evaluation_spec_result_id"),
                    "spec_status": payload.get("spec_status"),
                    "result_fingerprint": payload.get("result_fingerprint"),
                }
            )
    _atomic_write_json(base / "indexes" / RECEIPT_INDEX, {"schema_version": "deployed_rule_effectiveness_evaluation_spec_receipt_index_v1", "items": items, "updated_at_utc": _now()})


def _load_all(folder: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping):
            items.append(dict(payload))
    return items


def _index_items(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    if not isinstance(payload, Mapping):
        return []
    return [dict(item) for item in list(payload.get("items", []) or []) if isinstance(item, Mapping)]


def _ensure_dirs(root: Path | str) -> Path:
    base = _ensure_analysis_dirs(root)
    for folder in (PLAN_DIR, RESULT_DIR, RECEIPT_DIR, "indexes"):
        (base / folder).mkdir(parents=True, exist_ok=True)
    for path, payload in (
        (base / "indexes" / PLAN_INDEX, {"schema_version": "deployed_rule_effectiveness_evaluation_spec_plan_index_v1", "items": [], "updated_at_utc": _now()}),
        (base / "indexes" / RESULT_INDEX, {"schema_version": "deployed_rule_effectiveness_evaluation_spec_result_index_v1", "items": [], "updated_at_utc": _now()}),
        (base / "indexes" / RECEIPT_INDEX, {"schema_version": "deployed_rule_effectiveness_evaluation_spec_receipt_index_v1", "items": [], "updated_at_utc": _now()}),
    ):
        if not path.exists():
            _atomic_write_json(path, payload)
    return base


def _recommended_action(status: str) -> str:
    if status == "spec_ready_for_scoring_engine_design":
        return "Define the scoring engine against the recorded outcome-truth contract."
    if status == "spec_ready_scoring_blocked_missing_outcome_truth":
        return "Add one authoritative outcome-truth source before designing effectiveness scoring."
    if status == "spec_ready_scoring_blocked_missing_readiness":
        return "Record a valid ready_for_effectiveness_evaluation readiness result first."
    if status == "spec_ready_scoring_blocked_insufficient_events":
        return "Collect enough validated execution attempts before designing scoring."
    if status == "spec_ready_scoring_blocked_missing_denominator":
        return "Restore denominator semantics before any scoring contract work."
    if status == "spec_ready_scoring_blocked_unsupported_metric":
        return "Narrow the future metric set to supported evidence contracts only."
    if status == "stale":
        return "Rebuild the specification plan against current readiness and telemetry state."
    return "Resolve evidence corruption before any later effectiveness work."


def _normalize_metric_contract_id(value: str | None) -> str:
    text = _text(value)
    return text or DEFAULT_METRIC_CONTRACT_ID


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered
