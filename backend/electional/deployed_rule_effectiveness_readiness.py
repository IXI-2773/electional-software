"""Readiness gate for later effectiveness evaluation from real execution telemetry."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from . import certified_rule_post_deployment_acceptance as acceptance_backend
from . import certified_rule_production_deployment as deployment_backend
from . import deployed_rule_operational_telemetry as telemetry_backend
from . import production_deployment_adapter as adapter_backend
from .canonical_rule_runtime import _atomic_write_json, _hash_payload, _now, _read_json, _restore_json, _safe_id, load_canonical_rule
from .rule_effectiveness_analysis import _ensure_analysis_dirs
from .source_documents import SOURCE_DOCUMENT_ROOT

PLAN_DIR = "deployed_rule_effectiveness_readiness/plans"
RESULT_DIR = "deployed_rule_effectiveness_readiness/results"
RECEIPT_DIR = "deployed_rule_effectiveness_readiness/receipts"
PLAN_INDEX = "deployed_rule_effectiveness_readiness_plan_index.json"
RESULT_INDEX = "deployed_rule_effectiveness_readiness_result_index.json"
RECEIPT_INDEX = "deployed_rule_effectiveness_readiness_receipt_index.json"

PLAN_SCHEMA = "deployed_rule_effectiveness_readiness_plan_v1"
RESULT_SCHEMA = "deployed_rule_effectiveness_readiness_result_v1"
RECEIPT_SCHEMA = "deployed_rule_effectiveness_readiness_receipt_v1"
READINESS_SCHEMA_VERSION = "deployed_rule_effectiveness_readiness_v1"
MANIFEST_SCHEMA = "deployed_rule_effectiveness_readiness_manifest_v1"
REQUIRED_CONFIRMATION = "RECORD_EFFECTIVENESS_READINESS_RESULT"
MINIMUM_EXECUTION_ATTEMPTS = 30
READINESS_STATUSES = [
    "ready_for_effectiveness_evaluation",
    "not_ready",
    "blocked_no_execution_events",
    "blocked_no_execution_producer",
    "blocked",
    "stale",
    "corrupt",
]
PUBLIC_FUNCTIONS = [
    "build_deployed_rule_effectiveness_readiness_workspace",
    "validate_deployed_rule_effectiveness_readiness_eligibility",
    "build_deployed_rule_effectiveness_readiness_plan",
    "record_deployed_rule_effectiveness_readiness_result",
    "load_deployed_rule_effectiveness_readiness_result",
    "get_deployed_rule_effectiveness_readiness_health",
    "format_deployed_rule_effectiveness_readiness_report",
    "get_deployed_rule_effectiveness_readiness_manifest",
]


def get_deployed_rule_effectiveness_readiness_manifest(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    telemetry_manifest = telemetry_backend.get_deployed_rule_operational_telemetry_manifest(root=root)
    producer = _execution_producer(telemetry_manifest)
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "readiness_schema_version": READINESS_SCHEMA_VERSION,
        "required_identifiers": [
            "canonical_rule_id",
            "production_deployment_result_id",
            "production_target_id",
            "deployed_rule_id",
            "telemetry_snapshot_id",
            "observation_window_start",
            "observation_window_end",
        ],
        "readiness_statuses": list(READINESS_STATUSES),
        "execution_producer_available": bool(producer),
        "execution_producer_id": (producer or {}).get("producer_id"),
        "execution_producer_fingerprint": (producer or {}).get("producer_fingerprint"),
        "minimum_execution_attempts": MINIMUM_EXECUTION_ATTEMPTS,
        "effectiveness_evaluation_status": "not_performed",
    }
    manifest["manifest_fingerprint"] = _hash_payload(
        {key: manifest.get(key) for key in sorted(manifest) if key != "manifest_fingerprint"}
    )
    return manifest


def build_deployed_rule_effectiveness_readiness_workspace(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    observation_window_start: str,
    observation_window_end: str,
    *,
    post_deployment_result_id: str | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    context = _readiness_context(
        canonical_rule_id=canonical_rule_id,
        production_deployment_result_id=production_deployment_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
        telemetry_snapshot_id=telemetry_snapshot_id,
        observation_window_start=observation_window_start,
        observation_window_end=observation_window_end,
        post_deployment_result_id=post_deployment_result_id,
        root=root,
    )
    snapshot = context["snapshot"]
    manifest = context["manifest"]
    producer = context["execution_producer"]
    return {
        "status": context["status"],
        "canonical_rule_id": canonical_rule_id,
        "production_deployment_result_id": production_deployment_result_id,
        "production_target_id": production_target_id,
        "deployed_rule_id": deployed_rule_id,
        "telemetry_snapshot_id": telemetry_snapshot_id,
        "post_deployment_result_id": post_deployment_result_id,
        "execution_producer_available": bool(producer),
        "execution_producer_id": (producer or {}).get("producer_id"),
        "execution_producer_fingerprint": (producer or {}).get("producer_fingerprint"),
        "execution_event_count": snapshot.get("execution_event_count") if isinstance(snapshot, Mapping) else 0,
        "execution_completion_count": snapshot.get("execution_completion_count") if isinstance(snapshot, Mapping) else 0,
        "execution_failure_count": snapshot.get("execution_failure_count") if isinstance(snapshot, Mapping) else 0,
        "metric_availability": deepcopy_listfree(snapshot.get("metric_availability")) if isinstance(snapshot, Mapping) else {},
        "observation_window_start": observation_window_start,
        "observation_window_end": observation_window_end,
        "snapshot_observation_start": snapshot.get("observation_start") if isinstance(snapshot, Mapping) else None,
        "snapshot_observation_end": snapshot.get("observation_end") if isinstance(snapshot, Mapping) else None,
        "snapshot_completeness_status": snapshot.get("snapshot_completeness_status") if isinstance(snapshot, Mapping) else None,
        "effectiveness_evaluation_status": snapshot.get("effectiveness_evaluation_status") if isinstance(snapshot, Mapping) else None,
        "warnings": list(context["warnings"]),
        "blockers": list(context["blockers"]),
        "recommended_action": _recommended_action(context["status"]),
    }


def validate_deployed_rule_effectiveness_readiness_eligibility(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    observation_window_start: str,
    observation_window_end: str,
    *,
    post_deployment_result_id: str | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    context = _readiness_context(
        canonical_rule_id=canonical_rule_id,
        production_deployment_result_id=production_deployment_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
        telemetry_snapshot_id=telemetry_snapshot_id,
        observation_window_start=observation_window_start,
        observation_window_end=observation_window_end,
        post_deployment_result_id=post_deployment_result_id,
        root=root,
    )
    return {
        "status": context["status"],
        "criteria": dict(context["criteria"]),
        "blockers": list(context["blockers"]),
        "warnings": list(context["warnings"]),
        "execution_producer_status": "available" if context["execution_producer"] else "missing",
        "execution_event_count": context["execution_event_count"],
        "valid_execution_attempt_count": context["valid_execution_attempt_count"],
        "minimum_execution_attempt_count": MINIMUM_EXECUTION_ATTEMPTS,
        "denominator_readiness": context["denominator_readiness"],
        "observation_window_readiness": context["observation_window_readiness"],
        "sample_sufficiency_status": context["sample_sufficiency_status"],
        "effectiveness_evaluation_status": context["effectiveness_evaluation_status"],
        "recommended_action": _recommended_action(context["status"]),
    }


def build_deployed_rule_effectiveness_readiness_plan(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    observation_window_start: str,
    observation_window_end: str,
    *,
    post_deployment_result_id: str | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    context = _readiness_context(
        canonical_rule_id=canonical_rule_id,
        production_deployment_result_id=production_deployment_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
        telemetry_snapshot_id=telemetry_snapshot_id,
        observation_window_start=observation_window_start,
        observation_window_end=observation_window_end,
        post_deployment_result_id=post_deployment_result_id,
        root=base,
    )
    plan = _plan_payload(context)
    path = _plan_path(base, str(plan["effectiveness_readiness_plan_id"]))
    existing = _read_json(path)
    if isinstance(existing, Mapping):
        if str(existing.get("plan_fingerprint") or "") == str(plan.get("plan_fingerprint") or ""):
            return {"status": "planned", "effectiveness_readiness_plan_id": plan["effectiveness_readiness_plan_id"], "writes_performed": 0, **_plan_summary(plan)}
        return {"status": "corrupt", "effectiveness_readiness_plan_id": plan["effectiveness_readiness_plan_id"], "writes_performed": 0, "warnings": [], "blockers": ["effectiveness_readiness_plan_divergence"]}
    before_plan = _read_json(path)
    before_index = _read_json(base / "indexes" / PLAN_INDEX)
    try:
        _atomic_write_json(path, plan)
        _update_plan_index(base)
    except Exception:
        _restore_json(path, before_plan)
        _restore_json(base / "indexes" / PLAN_INDEX, before_index)
        return {"status": "corrupt", "effectiveness_readiness_plan_id": plan["effectiveness_readiness_plan_id"], "writes_performed": 0, "warnings": [], "blockers": ["effectiveness_readiness_plan_write_failure"]}
    return {"status": "planned", "effectiveness_readiness_plan_id": plan["effectiveness_readiness_plan_id"], "writes_performed": 1, **_plan_summary(plan)}


def record_deployed_rule_effectiveness_readiness_result(
    effectiveness_readiness_plan_id: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    if confirmation != REQUIRED_CONFIRMATION:
        return {"status": "blocked", "effectiveness_readiness_plan_id": effectiveness_readiness_plan_id, "writes_performed": 0, "warnings": [], "blockers": ["effectiveness_readiness_confirmation_required"]}
    plan = _read_json(_plan_path(base, effectiveness_readiness_plan_id))
    if not isinstance(plan, Mapping):
        return {"status": "blocked", "effectiveness_readiness_plan_id": effectiveness_readiness_plan_id, "writes_performed": 0, "warnings": [], "blockers": ["effectiveness_readiness_plan_missing"]}
    context = _readiness_context(
        canonical_rule_id=str(plan.get("canonical_rule_id") or ""),
        production_deployment_result_id=str(plan.get("production_deployment_result_id") or ""),
        production_target_id=str(plan.get("production_target_id") or ""),
        deployed_rule_id=str(plan.get("deployed_rule_id") or ""),
        telemetry_snapshot_id=str(plan.get("telemetry_snapshot_id") or ""),
        observation_window_start=str(plan.get("observation_window_start") or ""),
        observation_window_end=str(plan.get("observation_window_end") or ""),
        post_deployment_result_id=_text(plan.get("post_deployment_result_id")),
        root=base,
    )
    current_plan = _plan_payload(context)
    if str(current_plan.get("plan_fingerprint") or "") != str(plan.get("plan_fingerprint") or ""):
        return {"status": "stale", "effectiveness_readiness_plan_id": effectiveness_readiness_plan_id, "writes_performed": 0, "warnings": list(context["warnings"]), "blockers": ["effectiveness_readiness_plan_stale"]}
    if str(current_plan.get("effectiveness_evaluation_status") or "") != "not_performed":
        return {"status": "blocked", "effectiveness_readiness_plan_id": effectiveness_readiness_plan_id, "writes_performed": 0, "warnings": [], "blockers": ["effectiveness_evaluation_already_performed"]}

    result_id = _result_id(effectiveness_readiness_plan_id)
    receipt_id = _receipt_id(result_id)
    result = {
        "schema_version": RESULT_SCHEMA,
        "effectiveness_readiness_schema_version": READINESS_SCHEMA_VERSION,
        "effectiveness_readiness_result_id": result_id,
        "effectiveness_readiness_plan_id": effectiveness_readiness_plan_id,
        "effectiveness_readiness_receipt_id": receipt_id,
        **{key: current_plan.get(key) for key in (
            "canonical_rule_id",
            "production_deployment_result_id",
            "production_target_id",
            "deployed_rule_id",
            "telemetry_snapshot_id",
            "post_deployment_result_id",
            "observation_window_start",
            "observation_window_end",
            "execution_producer_id",
            "execution_producer_fingerprint",
            "execution_event_count",
            "execution_completion_count",
            "execution_failure_count",
            "valid_execution_attempt_count",
            "minimum_execution_attempt_count",
            "denominator_readiness",
            "observation_window_readiness",
            "sample_sufficiency_status",
            "criteria",
            "warnings",
            "blockers",
            "effectiveness_evaluation_status",
            "telemetry_snapshot_fingerprint",
            "production_deployment_result_fingerprint",
            "canonical_rule_fingerprint",
            "deployed_rule_fingerprint",
            "production_transaction_id",
            "document_id",
            "source_revision",
            "plan_fingerprint",
        )},
        "readiness_status": context["status"],
        "recorded_at_utc": _now(),
    }
    result["result_fingerprint"] = _hash_payload({key: result.get(key) for key in sorted(result) if key not in {"result_fingerprint", "recorded_at_utc"}})
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "effectiveness_readiness_schema_version": READINESS_SCHEMA_VERSION,
        "effectiveness_readiness_receipt_id": receipt_id,
        "effectiveness_readiness_result_id": result_id,
        "effectiveness_readiness_plan_id": effectiveness_readiness_plan_id,
        "readiness_status": context["status"],
        "result_fingerprint": result["result_fingerprint"],
        "recorded_at_utc": result["recorded_at_utc"],
    }
    existing = _read_json(_result_path(base, result_id))
    if isinstance(existing, Mapping):
        if str(existing.get("result_fingerprint") or "") == str(result.get("result_fingerprint") or ""):
            return {"status": "already_recorded", "effectiveness_readiness_result_id": result_id, "writes_performed": 0, **_result_summary(existing)}
        return {"status": "conflict", "effectiveness_readiness_result_id": result_id, "writes_performed": 0, "warnings": [], "blockers": ["effectiveness_readiness_result_conflict"]}
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
        return {"status": "corrupt", "effectiveness_readiness_result_id": result_id, "writes_performed": 0, "warnings": [], "blockers": ["effectiveness_readiness_result_write_failure"]}
    return {"status": context["status"], "effectiveness_readiness_result_id": result_id, "writes_performed": 1, **_result_summary(result)}


def load_deployed_rule_effectiveness_readiness_result(
    effectiveness_readiness_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    payload = _read_json(_result_path(base, effectiveness_readiness_result_id))
    if not isinstance(payload, Mapping):
        return {"status": "blocked", "effectiveness_readiness_result_id": effectiveness_readiness_result_id, "warnings": [], "blockers": ["effectiveness_readiness_result_missing"]}
    receipt = _read_json(_receipt_path(base, str(payload.get("effectiveness_readiness_receipt_id") or "")))
    if not isinstance(receipt, Mapping):
        return {"status": "corrupt", "effectiveness_readiness_result_id": effectiveness_readiness_result_id, "warnings": [], "blockers": ["effectiveness_readiness_receipt_missing"]}
    return {
        "status": str(payload.get("readiness_status") or "corrupt"),
        "effectiveness_readiness_result": dict(payload),
        "effectiveness_readiness_receipt": dict(receipt),
        "warnings": [],
        "blockers": [],
    }


def get_deployed_rule_effectiveness_readiness_health(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_dirs(root)
    plan_items = _load_all(base / PLAN_DIR)
    result_items = _load_all(base / RESULT_DIR)
    receipt_items = _load_all(base / RECEIPT_DIR)
    blockers: list[str] = []
    warnings: list[str] = []
    result_ids = {str(item.get("effectiveness_readiness_result_id") or "") for item in result_items}
    for receipt in receipt_items:
        if str(receipt.get("effectiveness_readiness_result_id") or "") not in result_ids:
            blockers.append("effectiveness_readiness_receipt_references_missing_result")
    indexed_plan_ids = {str(item.get("effectiveness_readiness_plan_id") or "") for item in _index_items(base / "indexes" / PLAN_INDEX)}
    for plan in plan_items:
        if str(plan.get("effectiveness_readiness_plan_id") or "") not in indexed_plan_ids:
            warnings.append("effectiveness_readiness_plan_missing_from_index")
    status = "healthy" if not blockers and not warnings else "warning" if warnings and not blockers else "blocked"
    return {
        "status": status,
        "plan_count": len(plan_items),
        "result_count": len(result_items),
        "receipt_count": len(receipt_items),
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
    }


def format_deployed_rule_effectiveness_readiness_report(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    observation_window_start: str,
    observation_window_end: str,
    *,
    post_deployment_result_id: str | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    eligibility = validate_deployed_rule_effectiveness_readiness_eligibility(
        canonical_rule_id,
        production_deployment_result_id,
        production_target_id,
        deployed_rule_id,
        telemetry_snapshot_id,
        observation_window_start,
        observation_window_end,
        post_deployment_result_id=post_deployment_result_id,
        root=root,
    )
    lines = [
        "Deployed Rule Effectiveness Readiness",
        f"Canonical rule ID: {canonical_rule_id}",
        f"Deployed rule ID: {deployed_rule_id}",
        f"Production deployment result ID: {production_deployment_result_id}",
        f"Telemetry snapshot ID: {telemetry_snapshot_id}",
        f"Readiness status: {eligibility.get('status')}",
        "Readiness boundary: eligible for later effectiveness evaluation only; this is not an effectiveness score.",
        f"Execution producer status: {eligibility.get('execution_producer_status')}",
        f"Valid execution attempts: {eligibility.get('valid_execution_attempt_count')}/{eligibility.get('minimum_execution_attempt_count')}",
        f"Denominator readiness: {eligibility.get('denominator_readiness')}",
        f"Observation-window readiness: {eligibility.get('observation_window_readiness')}",
        f"Sample sufficiency: {eligibility.get('sample_sufficiency_status')}",
        f"Effectiveness evaluation status: {eligibility.get('effectiveness_evaluation_status')}",
        "Execution event semantics: evaluation_completed means runtime returned normally; evaluation_failed means runtime failed.",
        "Unsupported execution semantics: skipped and fallback remain unavailable, not zero effectiveness.",
    ]
    blockers = list(eligibility.get("blockers", []))
    warnings = list(eligibility.get("warnings", []))
    if blockers:
        lines.append("Blockers: " + ", ".join(blockers))
    if warnings:
        lines.append("Warnings: " + ", ".join(warnings))
    return "\n".join(lines)


def _readiness_context(
    *,
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    observation_window_start: str,
    observation_window_end: str,
    post_deployment_result_id: str | None,
    root: Path | str,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    manifest = get_deployed_rule_effectiveness_readiness_manifest(root=base)
    telemetry_manifest = telemetry_backend.get_deployed_rule_operational_telemetry_manifest(root=base)
    deployment_loaded = deployment_backend.load_certified_rule_production_deployment_result(production_deployment_result_id, root=base)
    deployment_result = deployment_loaded.get("production_deployment_result") if isinstance(deployment_loaded.get("production_deployment_result"), Mapping) else {}
    receipt_payload = deployment_backend._find_receipt_for_result(
        base,
        production_deployment_result_id,
    ) or {}
    snapshot = _read_json(telemetry_backend._snapshot_path(base, telemetry_snapshot_id))
    current_state = adapter_backend.read_production_deployment_state(
        production_target_id,
        transaction_id=str((deployment_result or {}).get("production_transaction_id") or ""),
        root=base,
    )
    source_rule_loaded = load_canonical_rule(canonical_rule_id, root=base)
    source_rule = source_rule_loaded.get("rule") if isinstance(source_rule_loaded.get("rule"), Mapping) else {}
    deployed_rule_loaded = load_canonical_rule(deployed_rule_id, root=base)
    deployed_rule = deployed_rule_loaded.get("rule") if isinstance(deployed_rule_loaded.get("rule"), Mapping) else {}
    acceptance_result = None
    if post_deployment_result_id:
        acceptance_loaded = acceptance_backend.load_certified_rule_post_deployment_acceptance_result(post_deployment_result_id, root=base)
        acceptance_result = acceptance_loaded.get("post_deployment_acceptance_result") if isinstance(acceptance_loaded.get("post_deployment_acceptance_result"), Mapping) else {}

    blockers: list[str] = []
    warnings: list[str] = []
    criteria = {name: False for name in (
        "phase_9v_deployment_completed",
        "deployed_instance_bound_to_phase_9v_result",
        "canonical_source_rule_unchanged",
        "telemetry_snapshot_exists",
        "telemetry_snapshot_binds_expected_deployed_rule",
        "telemetry_snapshot_binds_expected_phase_9v_result",
        "observation_window_explicit",
        "snapshot_covers_observation_window",
        "snapshot_not_truncated",
        "execution_producer_available",
        "execution_events_present",
        "execution_events_validated",
        "denominator_semantics_available",
        "sample_sufficiency_rule_defined",
        "sample_sufficiency_met",
        "phase_9w_not_used_as_effectiveness_evidence",
        "effectiveness_not_performed",
    )}

    producer = _execution_producer(telemetry_manifest)
    if producer:
        criteria["execution_producer_available"] = True
    else:
        blockers.append("execution_producer_missing")

    if deployment_result:
        if str(deployment_result.get("canonical_rule_id") or "") == canonical_rule_id and str(deployment_result.get("production_target_id") or "") == production_target_id:
            if str(deployment_result.get("deployed_rule_id") or "") == deployed_rule_id:
                criteria["deployed_instance_bound_to_phase_9v_result"] = True
            else:
                blockers.append("deployed_rule_binding_mismatch")
        else:
            blockers.append("phase_9v_identity_mismatch")
        if str(deployment_result.get("final_status") or "") == "completed" and str(receipt_payload.get("result_fingerprint") or "") == str(deployment_result.get("result_fingerprint") or ""):
            criteria["phase_9v_deployment_completed"] = True
        else:
            blockers.append("phase_9v_deployment_not_completed")
    else:
        blockers.append("phase_9v_deployment_result_missing")

    if source_rule and str(source_rule.get("rule_fingerprint") or "") == str(deployment_result.get("canonical_rule_fingerprint") or ""):
        criteria["canonical_source_rule_unchanged"] = True
    else:
        blockers.append("canonical_source_rule_drifted")

    if isinstance(snapshot, Mapping):
        criteria["telemetry_snapshot_exists"] = True
        expected_snapshot_fingerprint = telemetry_backend._snapshot_fingerprint(snapshot)
        if str(snapshot.get("snapshot_fingerprint") or "") != str(expected_snapshot_fingerprint or ""):
            blockers.append("telemetry_snapshot_fingerprint_invalid")
        if str(snapshot.get("deployed_rule_id") or "") == deployed_rule_id:
            criteria["telemetry_snapshot_binds_expected_deployed_rule"] = True
        else:
            blockers.append("telemetry_snapshot_deployed_rule_mismatch")
        if str(snapshot.get("production_deployment_result_id") or "") == production_deployment_result_id:
            criteria["telemetry_snapshot_binds_expected_phase_9v_result"] = True
        else:
            blockers.append("telemetry_snapshot_deployment_result_mismatch")
        if str(snapshot.get("observation_start") or "") == observation_window_start and str(snapshot.get("observation_end") or "") == observation_window_end:
            criteria["snapshot_covers_observation_window"] = True
        else:
            blockers.append("telemetry_snapshot_observation_window_mismatch")
        if str(snapshot.get("snapshot_completeness_status") or "") == "complete":
            criteria["snapshot_not_truncated"] = True
        else:
            blockers.append("telemetry_snapshot_incomplete")
    else:
        blockers.append("telemetry_snapshot_missing")

    if _text(observation_window_start) and _text(observation_window_end):
        criteria["observation_window_explicit"] = True
    else:
        blockers.append("observation_window_not_explicit")

    execution_event_count = int((snapshot or {}).get("execution_event_count") or 0) if isinstance(snapshot, Mapping) else 0
    completion_count = int((snapshot or {}).get("execution_completion_count") or 0) if isinstance(snapshot, Mapping) else 0
    failure_count = int((snapshot or {}).get("execution_failure_count") or 0) if isinstance(snapshot, Mapping) else 0
    valid_execution_attempt_count = completion_count + failure_count
    metric_availability = dict((snapshot or {}).get("metric_availability") or {}) if isinstance(snapshot, Mapping) else {}

    if execution_event_count > 0:
        criteria["execution_events_present"] = True
    else:
        blockers.append("execution_events_absent")
    if execution_event_count == valid_execution_attempt_count and int((snapshot or {}).get("invalid_event_count") or 0) == 0 and int((snapshot or {}).get("corrupt_event_count") or 0) == 0:
        criteria["execution_events_validated"] = True
    else:
        blockers.append("execution_events_invalid_or_corrupt")
    if (
        criteria["observation_window_explicit"]
        and metric_availability.get("execution_completion_count") in {"available", "execution_producer_available_no_events_observed"}
        and metric_availability.get("execution_failure_count") in {"available", "execution_producer_available_no_events_observed"}
        and metric_availability.get("execution_skip_count") == "unsupported_by_producer"
        and metric_availability.get("fallback_count") == "unsupported_by_producer"
    ):
        criteria["denominator_semantics_available"] = True
    else:
        blockers.append("denominator_semantics_unavailable")
    criteria["sample_sufficiency_rule_defined"] = True
    if valid_execution_attempt_count >= MINIMUM_EXECUTION_ATTEMPTS:
        criteria["sample_sufficiency_met"] = True
    if str((snapshot or {}).get("effectiveness_evaluation_status") or "") == "not_performed" and str(manifest.get("effectiveness_evaluation_status") or "") == "not_performed":
        criteria["effectiveness_not_performed"] = True
    else:
        blockers.append("effectiveness_already_performed")
    criteria["phase_9w_not_used_as_effectiveness_evidence"] = True

    # Current-state drift converts otherwise valid evidence into stale.
    if str((current_state or {}).get("transaction_state") or "") != "committed" or str((current_state or {}).get("verification_status") or "") != "verified_committed":
        blockers.append("current_production_state_stale")
    if deployed_rule and str(deployed_rule.get("rule_fingerprint") or "") != str(deployment_result.get("deployed_rule_fingerprint") or ""):
        blockers.append("deployed_rule_drifted")
    if acceptance_result and str(acceptance_result.get("decision_status") or "") == "accepted":
        warnings.append("phase_9w_acceptance_present_but_not_effectiveness_evidence")

    denominator_readiness = "ready" if criteria["denominator_semantics_available"] else "not_ready"
    observation_window_readiness = "ready" if criteria["observation_window_explicit"] and criteria["snapshot_covers_observation_window"] and criteria["snapshot_not_truncated"] else "not_ready"
    sample_sufficiency_status = "met" if criteria["sample_sufficiency_met"] else "not_met"
    effectiveness_status = str((snapshot or {}).get("effectiveness_evaluation_status") or "not_performed") if isinstance(snapshot, Mapping) else "not_performed"
    status = _readiness_status(criteria, blockers, execution_event_count, bool(producer))
    if status == "corrupt":
        warnings = []
    return {
        "base": base,
        "manifest": manifest,
        "telemetry_manifest": telemetry_manifest,
        "execution_producer": producer,
        "deployment_result": dict(deployment_result) if isinstance(deployment_result, Mapping) else {},
        "snapshot": dict(snapshot) if isinstance(snapshot, Mapping) else {},
        "current_state": dict(current_state) if isinstance(current_state, Mapping) else {},
        "source_rule": dict(source_rule) if isinstance(source_rule, Mapping) else {},
        "deployed_rule": dict(deployed_rule) if isinstance(deployed_rule, Mapping) else {},
        "criteria": criteria,
        "blockers": _dedupe(blockers),
        "warnings": _dedupe(warnings),
        "status": status,
        "execution_event_count": execution_event_count,
        "valid_execution_attempt_count": valid_execution_attempt_count,
        "denominator_readiness": denominator_readiness,
        "observation_window_readiness": observation_window_readiness,
        "sample_sufficiency_status": sample_sufficiency_status,
        "effectiveness_evaluation_status": effectiveness_status,
        "observation_window_start": observation_window_start,
        "observation_window_end": observation_window_end,
        "post_deployment_result_id": post_deployment_result_id,
    }


def _readiness_status(criteria: Mapping[str, bool], blockers: list[str], execution_event_count: int, producer_available: bool) -> str:
    if not producer_available:
        return "blocked_no_execution_producer"
    if any(item in {"telemetry_snapshot_fingerprint_invalid", "execution_events_invalid_or_corrupt"} for item in blockers):
        return "corrupt"
    if any("stale" in item or "drifted" in item for item in blockers):
        return "stale"
    if execution_event_count <= 0:
        return "blocked_no_execution_events"
    if not criteria.get("sample_sufficiency_met"):
        return "not_ready"
    required = [
        "phase_9v_deployment_completed",
        "deployed_instance_bound_to_phase_9v_result",
        "canonical_source_rule_unchanged",
        "telemetry_snapshot_exists",
        "telemetry_snapshot_binds_expected_deployed_rule",
        "telemetry_snapshot_binds_expected_phase_9v_result",
        "observation_window_explicit",
        "snapshot_covers_observation_window",
        "snapshot_not_truncated",
        "execution_producer_available",
        "execution_events_present",
        "execution_events_validated",
        "denominator_semantics_available",
        "sample_sufficiency_rule_defined",
        "sample_sufficiency_met",
        "phase_9w_not_used_as_effectiveness_evidence",
        "effectiveness_not_performed",
    ]
    if all(criteria.get(item) for item in required):
        return "ready_for_effectiveness_evaluation"
    return "blocked" if blockers else "not_ready"


def _plan_payload(context: Mapping[str, Any]) -> dict[str, Any]:
    deployment_result = dict(context.get("deployment_result") or {})
    snapshot = dict(context.get("snapshot") or {})
    producer = dict(context.get("execution_producer") or {})
    plan = {
        "schema_version": PLAN_SCHEMA,
        "effectiveness_readiness_schema_version": READINESS_SCHEMA_VERSION,
        "effectiveness_readiness_plan_id": _plan_id(
            canonical_rule_id=str(deployment_result.get("canonical_rule_id") or ""),
            deployed_rule_id=str(deployment_result.get("deployed_rule_id") or ""),
            production_deployment_result_id=str(deployment_result.get("production_deployment_result_id") or ""),
            telemetry_snapshot_id=str(snapshot.get("snapshot_id") or ""),
            observation_window_start=str(context.get("observation_window_start") or ""),
            observation_window_end=str(context.get("observation_window_end") or ""),
        ),
        "canonical_rule_id": deployment_result.get("canonical_rule_id"),
        "canonical_rule_fingerprint": deployment_result.get("canonical_rule_fingerprint"),
        "deployed_rule_id": deployment_result.get("deployed_rule_id"),
        "deployed_rule_fingerprint": deployment_result.get("deployed_rule_fingerprint"),
        "production_deployment_result_id": deployment_result.get("production_deployment_result_id"),
        "production_deployment_result_fingerprint": deployment_result.get("result_fingerprint"),
        "production_target_id": deployment_result.get("production_target_id"),
        "production_transaction_id": deployment_result.get("production_transaction_id"),
        "telemetry_snapshot_id": snapshot.get("snapshot_id"),
        "telemetry_snapshot_fingerprint": snapshot.get("snapshot_fingerprint"),
        "post_deployment_result_id": context.get("post_deployment_result_id"),
        "observation_window_start": context.get("observation_window_start"),
        "observation_window_end": context.get("observation_window_end"),
        "execution_producer_id": producer.get("producer_id"),
        "execution_producer_fingerprint": producer.get("producer_fingerprint"),
        "execution_event_count": context.get("execution_event_count"),
        "execution_completion_count": snapshot.get("execution_completion_count"),
        "execution_failure_count": snapshot.get("execution_failure_count"),
        "valid_execution_attempt_count": context.get("valid_execution_attempt_count"),
        "minimum_execution_attempt_count": MINIMUM_EXECUTION_ATTEMPTS,
        "denominator_readiness": context.get("denominator_readiness"),
        "observation_window_readiness": context.get("observation_window_readiness"),
        "sample_sufficiency_status": context.get("sample_sufficiency_status"),
        "criteria": dict(context.get("criteria") or {}),
        "warnings": list(context.get("warnings") or []),
        "blockers": list(context.get("blockers") or []),
        "effectiveness_evaluation_status": context.get("effectiveness_evaluation_status"),
        "readiness_status": context.get("status"),
        "document_id": deployment_result.get("document_id"),
        "source_revision": deployment_result.get("source_revision"),
    }
    plan["plan_fingerprint"] = _hash_payload({key: plan.get(key) for key in sorted(plan) if key != "plan_fingerprint"})
    return plan


def _execution_producer(manifest: Mapping[str, Any]) -> dict[str, Any] | None:
    for item in manifest.get("producers", []):
        if isinstance(item, Mapping) and str(item.get("producer_id") or "") == telemetry_backend.EXECUTION_PRODUCER_ID:
            return dict(item)
    return None


def _plan_id(
    *,
    canonical_rule_id: str,
    deployed_rule_id: str,
    production_deployment_result_id: str,
    telemetry_snapshot_id: str,
    observation_window_start: str,
    observation_window_end: str,
) -> str:
    suffix = _hash_payload(
        {
            "canonical_rule_id": canonical_rule_id,
            "deployed_rule_id": deployed_rule_id,
            "production_deployment_result_id": production_deployment_result_id,
            "telemetry_snapshot_id": telemetry_snapshot_id,
            "observation_window_start": observation_window_start,
            "observation_window_end": observation_window_end,
        }
    )[7:19]
    return f"effectiveness_readiness_plan_{_safe_id(production_deployment_result_id)}_{suffix}"


def _result_id(plan_id: str) -> str:
    return f"{plan_id}_result"


def _receipt_id(result_id: str) -> str:
    return f"{result_id}_receipt"


def _plan_path(base: Path, plan_id: str) -> Path:
    return base / PLAN_DIR / f"{_safe_id(plan_id)}.json"


def _result_path(base: Path, result_id: str) -> Path:
    return base / RESULT_DIR / f"{_safe_id(result_id)}.json"


def _receipt_path(base: Path, receipt_id: str) -> Path:
    return base / RECEIPT_DIR / f"{_safe_id(receipt_id)}.json"


def _update_plan_index(base: Path) -> None:
    items = [
        {
            "effectiveness_readiness_plan_id": item.get("effectiveness_readiness_plan_id"),
            "production_deployment_result_id": item.get("production_deployment_result_id"),
            "deployed_rule_id": item.get("deployed_rule_id"),
            "telemetry_snapshot_id": item.get("telemetry_snapshot_id"),
            "readiness_status": item.get("readiness_status"),
            "plan_fingerprint": item.get("plan_fingerprint"),
        }
        for item in _load_all(base / PLAN_DIR)
    ]
    _atomic_write_json(base / "indexes" / PLAN_INDEX, {"schema_version": "deployed_rule_effectiveness_readiness_plan_index_v1", "items": items, "updated_at_utc": _now()})


def _update_result_index(base: Path) -> None:
    items = [
        {
            "effectiveness_readiness_result_id": item.get("effectiveness_readiness_result_id"),
            "effectiveness_readiness_plan_id": item.get("effectiveness_readiness_plan_id"),
            "production_deployment_result_id": item.get("production_deployment_result_id"),
            "deployed_rule_id": item.get("deployed_rule_id"),
            "readiness_status": item.get("readiness_status"),
        }
        for item in _load_all(base / RESULT_DIR)
    ]
    _atomic_write_json(base / "indexes" / RESULT_INDEX, {"schema_version": "deployed_rule_effectiveness_readiness_result_index_v1", "items": items, "updated_at_utc": _now()})


def _update_receipt_index(base: Path) -> None:
    items = [
        {
            "effectiveness_readiness_receipt_id": item.get("effectiveness_readiness_receipt_id"),
            "effectiveness_readiness_result_id": item.get("effectiveness_readiness_result_id"),
            "readiness_status": item.get("readiness_status"),
        }
        for item in _load_all(base / RECEIPT_DIR)
    ]
    _atomic_write_json(base / "indexes" / RECEIPT_INDEX, {"schema_version": "deployed_rule_effectiveness_readiness_receipt_index_v1", "items": items, "updated_at_utc": _now()})


def _index_items(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    items = payload.get("items") if isinstance(payload, Mapping) else None
    if not isinstance(items, list):
        return []
    return [dict(item) for item in items if isinstance(item, Mapping)]


def _plan_summary(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "readiness_status": plan.get("readiness_status"),
        "plan_fingerprint": plan.get("plan_fingerprint"),
        "valid_execution_attempt_count": plan.get("valid_execution_attempt_count"),
        "minimum_execution_attempt_count": plan.get("minimum_execution_attempt_count"),
        "warnings": list(plan.get("warnings", [])),
        "blockers": list(plan.get("blockers", [])),
    }


def _result_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "readiness_status": result.get("readiness_status"),
        "canonical_rule_id": result.get("canonical_rule_id"),
        "deployed_rule_id": result.get("deployed_rule_id"),
        "production_deployment_result_id": result.get("production_deployment_result_id"),
        "telemetry_snapshot_id": result.get("telemetry_snapshot_id"),
        "valid_execution_attempt_count": result.get("valid_execution_attempt_count"),
        "warnings": list(result.get("warnings", [])),
        "blockers": list(result.get("blockers", [])),
    }


def _load_all(folder: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping):
            items.append(dict(payload))
    return items


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in items if str(item)))


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def deepcopy_listfree(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): deepcopy_listfree(item) for key, item in value.items()}
    if isinstance(value, list):
        return [deepcopy_listfree(item) for item in value]
    return value


def _recommended_action(status: str) -> str:
    return {
        "ready_for_effectiveness_evaluation": "Effectiveness evaluation may begin in a later phase using this frozen readiness evidence.",
        "not_ready": "Continue collecting real execution telemetry until the minimum attempt threshold is met.",
        "blocked_no_execution_events": "Record real execution telemetry through the trusted execution runtime before evaluating readiness.",
        "blocked_no_execution_producer": "Restore the authoritative execution telemetry producer before evaluating readiness.",
        "blocked": "Resolve binding or evidence blockers before evaluating readiness.",
        "stale": "Rebuild the telemetry snapshot and readiness plan from current authoritative deployment state.",
        "corrupt": "Inspect immutable telemetry or readiness records for corruption before proceeding.",
    }.get(status, "Continue effectiveness-readiness review.")


def _ensure_dirs(root: Path | str) -> Path:
    base = _ensure_analysis_dirs(root)
    for folder in (PLAN_DIR, RESULT_DIR, RECEIPT_DIR, "indexes"):
        (base / folder).mkdir(parents=True, exist_ok=True)
    return base
