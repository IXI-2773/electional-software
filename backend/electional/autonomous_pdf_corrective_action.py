"""Single-PDF approved corrective action execution for autonomous PDF remediation."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from . import autonomous_pdf_benchmark as benchmark_backend
from . import autonomous_pdf_remediation as remediation_backend
from . import rule_effectiveness_analysis as analysis_backend
from .source_documents import SOURCE_DOCUMENT_ROOT

ACTION_DIR = "autonomous_pdf_corrective_actions"
RECEIPT_DIR = "autonomous_pdf_corrective_action_receipts"
ACTION_INDEX = "autonomous_pdf_corrective_action_index.json"
RECEIPT_INDEX = "autonomous_pdf_corrective_action_receipt_index.json"
ACTION_SCHEMA = "autonomous_pdf_corrective_action_v1"
RECEIPT_SCHEMA = "autonomous_pdf_corrective_action_receipt_v1"
CORRECTIVE_SCHEMA_VERSION = "autonomous_pdf_corrective_action_v1"
SUPPORTED_ACTIONS = {
    "close_expected_behavior",
    "close_no_action",
    "apply_benchmark_manifest_amendment",
    "request_new_source_revision",
    "create_phase_9j_fix_package",
    "create_phase_9k_fix_package",
}
REVIEW_ACTION_COMPATIBILITY = {
    "expected_conservative_behavior": {"close_expected_behavior"},
    "no_action": {"close_no_action"},
    "benchmark_manifest_review": {"apply_benchmark_manifest_amendment"},
    "source_document_review": {"request_new_source_revision"},
    "accept_for_targeted_fix": {"create_phase_9j_fix_package", "create_phase_9k_fix_package"},
}
PUBLIC_FUNCTIONS = [
    "build_autonomous_pdf_corrective_action_workspace",
    "build_autonomous_pdf_corrective_action_plan",
    "execute_autonomous_pdf_corrective_action",
    "load_autonomous_pdf_corrective_action",
    "verify_autonomous_pdf_corrective_action",
    "close_autonomous_pdf_corrective_action",
    "get_autonomous_pdf_corrective_action_health",
    "format_autonomous_pdf_corrective_action_report",
]


def build_autonomous_pdf_corrective_action_workspace(
    remediation_case_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    case, plan, review_receipt, benchmark_result, blockers = _load_case_context(base, remediation_case_id)
    if blockers:
        return {"status": "blocked", "remediation_case_id": remediation_case_id, "blockers": blockers, "warnings": []}
    assert case is not None and plan is not None and review_receipt is not None and benchmark_result is not None
    action = _find_action_for_case(base, remediation_case_id)
    receipts = _load_receipts_for_action(base, str((action or {}).get("corrective_action_id") or ""))
    return {
        "status": "ready_for_planning" if action is None else str(action.get("status") or "planned"),
        "remediation_case_id": remediation_case_id,
        "remediation_plan_id": case.get("remediation_plan_id"),
        "benchmark_result_id": case.get("benchmark_result_id"),
        "document_id": case.get("document_id"),
        "source_revision": case.get("source_revision"),
        "review_decision": case.get("review_decision"),
        "root_cause_classification": case.get("root_cause_classification"),
        "recommended_corrective_route": case.get("recommended_corrective_route"),
        "failed_release_gates": list(case.get("failed_release_gates", [])),
        "related_mismatch_ids": list(case.get("related_mismatch_ids", [])),
        "related_safety_violations": list(case.get("related_safety_violations", [])),
        "corrective_action_id": (action or {}).get("corrective_action_id"),
        "verification_outcome": (action or {}).get("verification_outcome"),
        "closure_status": (action or {}).get("closure_status"),
        "receipt_count": len(receipts),
        "recommended_action": "Build one approved corrective action plan.",
    }


def build_autonomous_pdf_corrective_action_plan(
    remediation_case_id: str,
    action_type: str,
    action_payload: dict | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    case, plan, review_receipt, benchmark_result, blockers = _load_case_context(base, remediation_case_id)
    if blockers:
        return {"status": "blocked", "remediation_case_id": remediation_case_id, "blockers": blockers, "warnings": []}
    assert case is not None and plan is not None and review_receipt is not None and benchmark_result is not None
    payload = deepcopy(action_payload or {})
    blockers.extend(_validate_action_compatibility(case, action_type))
    blockers.extend(_validate_action_payload(case, action_type, payload, benchmark_result, base))
    if blockers:
        return {"status": "blocked", "remediation_case_id": remediation_case_id, "action_type": action_type, "blockers": _dedupe(blockers), "warnings": []}
    action_fingerprint = _action_fingerprint(case, action_type, payload, review_receipt)
    corrective_action_id = _corrective_action_id(case, action_type, action_fingerprint)
    existing = _read_json(_action_path(base, corrective_action_id))
    if isinstance(existing, Mapping) and str(existing.get("action_fingerprint") or "") == action_fingerprint:
        return {"status": "planned", "corrective_action_id": corrective_action_id, "writes_performed": 0, "verification_required": bool(existing.get("verification_required"))}
    plan_payload = {
        "schema_version": ACTION_SCHEMA,
        "corrective_action_schema_version": CORRECTIVE_SCHEMA_VERSION,
        "corrective_action_id": corrective_action_id,
        "remediation_case_id": remediation_case_id,
        "remediation_plan_id": case.get("remediation_plan_id"),
        "benchmark_result_id": case.get("benchmark_result_id"),
        "document_id": case.get("document_id"),
        "source_revision": case.get("source_revision"),
        "review_receipt_id": review_receipt.get("corrective_source_receipt_id"),
        "review_decision": case.get("review_decision"),
        "action_type": action_type,
        "sanitized_action_payload_summary": _sanitize_action_payload(action_type, payload),
        "required_confirmation": "EXECUTE_ACTION",
        "original_benchmark_fingerprint": _benchmark_fingerprint(benchmark_result),
        "original_manifest_fingerprint": benchmark_result.get("benchmark_manifest_fingerprint"),
        "verification_required": action_type in {"apply_benchmark_manifest_amendment", "create_phase_9j_fix_package", "create_phase_9k_fix_package"},
        "action_fingerprint": action_fingerprint,
        "status": "planned",
        "execution_status": "planned",
        "verification_outcome": None,
        "closure_status": None,
        "payload": payload,
        "created_at_utc": str((existing or {}).get("created_at_utc") or analysis_backend._now()),
        "updated_at_utc": analysis_backend._now(),
    }
    before_action = _read_json(_action_path(base, corrective_action_id))
    before_index = _read_json(base / "indexes" / ACTION_INDEX)
    try:
        analysis_backend._atomic_write_json(_action_path(base, corrective_action_id), plan_payload)
        _update_action_index(base)
    except Exception:
        _restore_json(_action_path(base, corrective_action_id), before_action)
        _restore_json(base / "indexes" / ACTION_INDEX, before_index)
        return {"status": "corrupt", "remediation_case_id": remediation_case_id, "blockers": ["corrective_action_plan_write_failure"], "warnings": []}
    return {
        "status": "planned",
        "corrective_action_id": corrective_action_id,
        "remediation_case_id": remediation_case_id,
        "document_id": case.get("document_id"),
        "source_revision": case.get("source_revision"),
        "review_decision": case.get("review_decision"),
        "action_type": action_type,
        "required_confirmation": "EXECUTE_ACTION",
        "verification_required": plan_payload["verification_required"],
        "writes_performed": 1,
        "recommended_action": "Execute the approved corrective action with exact confirmation.",
    }


def execute_autonomous_pdf_corrective_action(
    corrective_action_id: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    action = _read_json(_action_path(base, corrective_action_id))
    if not isinstance(action, Mapping):
        return {"status": "blocked", "corrective_action_id": corrective_action_id, "blockers": ["corrective_action_missing"], "warnings": []}
    if confirmation != "EXECUTE_ACTION":
        return {"status": "blocked", "corrective_action_id": corrective_action_id, "blockers": ["execute_action_confirmation_required"], "warnings": []}
    if str(action.get("execution_status") or "") in {"executed", "closed", "verification_required", "requires_new_source_revision"} or str(action.get("closure_status") or ""):
        return {"status": "already_executed", "corrective_action_id": corrective_action_id, "writes_performed": 0}
    if str(action.get("status") or "") not in {"planned", "verification_required", "requires_new_source_revision", "executed", "closed"}:
        return {"status": "blocked", "corrective_action_id": corrective_action_id, "blockers": ["corrective_action_not_executable"], "warnings": []}
    result = _execute_action(base, dict(action))
    return result


def load_autonomous_pdf_corrective_action(
    corrective_action_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    payload = _read_json(_action_path(base, corrective_action_id))
    if not isinstance(payload, Mapping):
        return {"status": "not_found", "corrective_action_id": corrective_action_id, "corrective_action": None, "warnings": []}
    return {"status": "loaded", "corrective_action_id": corrective_action_id, "corrective_action": dict(payload), "warnings": []}


def verify_autonomous_pdf_corrective_action(
    corrective_action_id: str,
    new_benchmark_result_id: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    action = _read_json(_action_path(base, corrective_action_id))
    if not isinstance(action, Mapping):
        return {"status": "blocked", "corrective_action_id": corrective_action_id, "blockers": ["corrective_action_missing"], "warnings": []}
    if confirmation != "VERIFY_ACTION":
        return {"status": "blocked", "corrective_action_id": corrective_action_id, "blockers": ["verify_action_confirmation_required"], "warnings": []}
    if not bool(action.get("verification_required")):
        return {"status": "blocked", "corrective_action_id": corrective_action_id, "blockers": ["verification_not_required"], "warnings": []}
    if str(action.get("verification_benchmark_result_id") or "") == new_benchmark_result_id and str(action.get("verification_outcome") or ""):
        return {"status": "already_verified", "corrective_action_id": corrective_action_id, "writes_performed": 0}
    reused = remediation_backend.verify_autonomous_pdf_remediation(str(action.get("remediation_plan_id") or ""), new_benchmark_result_id, confirmation="VERIFY", root=base)
    if str(reused.get("status") or "") not in {"verified", "already_verified"}:
        return {"status": str(reused.get("status") or "blocked"), "corrective_action_id": corrective_action_id, "blockers": list(reused.get("blockers", [])), "warnings": list(reused.get("warnings", []))}
    verification_receipt = _latest_receipt(base, str(action.get("remediation_plan_id") or ""), "verification")
    payload = dict((verification_receipt or {}).get("payload") or {})
    classifications = {str(item.get("remediation_case_id") or ""): str(item.get("verification_status") or "unavailable") for item in payload.get("case_classifications", []) if isinstance(item, Mapping)}
    outcome = classifications.get(str(action.get("remediation_case_id") or ""), "unavailable")
    updated = dict(action)
    updated["verification_benchmark_result_id"] = new_benchmark_result_id
    updated["verification_outcome"] = outcome
    updated["verification_metric_deltas"] = deepcopy(dict(payload.get("metric_deltas") or {}))
    updated["status"] = "executed"
    updated["updated_at_utc"] = analysis_backend._now()
    receipt_payload = _receipt_payload(
        receipt_kind="verification",
        corrective_action_id=corrective_action_id,
        action=updated,
        payload={"new_benchmark_result_id": new_benchmark_result_id, "verification_outcome": outcome},
    )
    before_action = _read_json(_action_path(base, corrective_action_id))
    before_receipt = _read_json(_receipt_path(base, str(receipt_payload["corrective_action_receipt_id"])))
    before_action_index = _read_json(base / "indexes" / ACTION_INDEX)
    before_receipt_index = _read_json(base / "indexes" / RECEIPT_INDEX)
    try:
        analysis_backend._atomic_write_json(_action_path(base, corrective_action_id), updated)
        analysis_backend._atomic_write_json(_receipt_path(base, str(receipt_payload["corrective_action_receipt_id"])), receipt_payload)
        _update_action_index(base)
        _update_receipt_index(base)
    except Exception:
        _restore_json(_action_path(base, corrective_action_id), before_action)
        _restore_json(_receipt_path(base, str(receipt_payload["corrective_action_receipt_id"])), before_receipt)
        _restore_json(base / "indexes" / ACTION_INDEX, before_action_index)
        _restore_json(base / "indexes" / RECEIPT_INDEX, before_receipt_index)
        return {"status": "corrupt", "corrective_action_id": corrective_action_id, "blockers": ["corrective_action_verification_write_failure"], "warnings": []}
    return {"status": "verified", "corrective_action_id": corrective_action_id, "verification_outcome": outcome, "writes_performed": 2}


def close_autonomous_pdf_corrective_action(
    corrective_action_id: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    action = _read_json(_action_path(base, corrective_action_id))
    if not isinstance(action, Mapping):
        return {"status": "blocked", "corrective_action_id": corrective_action_id, "blockers": ["corrective_action_missing"], "warnings": []}
    if confirmation != "CLOSE_ACTION":
        return {"status": "blocked", "corrective_action_id": corrective_action_id, "blockers": ["close_action_confirmation_required"], "warnings": []}
    if str(action.get("closure_status") or ""):
        return {"status": "closed", "corrective_action_id": corrective_action_id, "writes_performed": 0}
    blockers = []
    execution_status = str(action.get("execution_status") or "")
    if execution_status == "rollback_failed":
        blockers.append("rollback_failed")
    if execution_status == "planned":
        blockers.append("execution_not_completed")
    if bool(action.get("verification_required")) and not str(action.get("verification_outcome") or ""):
        blockers.append("required_verification_missing")
    if blockers:
        return {"status": "blocked", "corrective_action_id": corrective_action_id, "blockers": blockers, "warnings": []}
    updated = dict(action)
    updated["closure_status"] = _closure_status(updated)
    updated["status"] = "closed"
    updated["updated_at_utc"] = analysis_backend._now()
    receipt_payload = _receipt_payload(
        receipt_kind="closure",
        corrective_action_id=corrective_action_id,
        action=updated,
        payload={"closure_status": updated["closure_status"]},
    )
    before_action = _read_json(_action_path(base, corrective_action_id))
    before_receipt = _read_json(_receipt_path(base, str(receipt_payload["corrective_action_receipt_id"])))
    before_action_index = _read_json(base / "indexes" / ACTION_INDEX)
    before_receipt_index = _read_json(base / "indexes" / RECEIPT_INDEX)
    try:
        analysis_backend._atomic_write_json(_action_path(base, corrective_action_id), updated)
        analysis_backend._atomic_write_json(_receipt_path(base, str(receipt_payload["corrective_action_receipt_id"])), receipt_payload)
        _update_action_index(base)
        _update_receipt_index(base)
    except Exception:
        _restore_json(_action_path(base, corrective_action_id), before_action)
        _restore_json(_receipt_path(base, str(receipt_payload["corrective_action_receipt_id"])), before_receipt)
        _restore_json(base / "indexes" / ACTION_INDEX, before_action_index)
        _restore_json(base / "indexes" / RECEIPT_INDEX, before_receipt_index)
        return {"status": "corrupt", "corrective_action_id": corrective_action_id, "blockers": ["corrective_action_closure_write_failure"], "warnings": []}
    return {"status": "closed", "corrective_action_id": corrective_action_id, "closure_status": updated["closure_status"], "writes_performed": 2}


def get_autonomous_pdf_corrective_action_health(
    corrective_action_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    actions = _load_all_actions(base)
    receipts = _load_all_receipts(base)
    if corrective_action_id:
        actions = [item for item in actions if str(item.get("corrective_action_id") or "") == corrective_action_id]
        receipts = [item for item in receipts if str(item.get("corrective_action_id") or "") == corrective_action_id]
    if not actions and not receipts:
        return {"status": "empty", "action_count": 0, "receipt_count": 0, "recommended_action": "Build one corrective action for a reviewed remediation case."}
    warnings: list[str] = []
    stale_count = 0
    if len({str(item.get("corrective_action_id") or "") for item in actions}) != len(actions):
        warnings.append("duplicate_corrective_action_ids")
    if len({str(item.get("corrective_action_receipt_id") or "") for item in receipts}) != len(receipts):
        warnings.append("duplicate_corrective_action_receipt_ids")
    for action in actions:
        if not _action_is_current(base, action):
            stale_count += 1
        if not _review_action_allowed(str(action.get("review_decision") or ""), str(action.get("action_type") or ""), str(action.get("root_cause_classification") or "")):
            warnings.append("review_action_incompatible")
        if str(action.get("closure_status") or "") and str(action.get("execution_status") or "") == "planned":
            warnings.append("invalid_closure_without_execution")
    status = "corrupt" if warnings else "stale" if stale_count else "healthy"
    return {
        "status": status,
        "action_count": len(actions),
        "receipt_count": len(receipts),
        "stale_action_count": stale_count,
        "warnings": _dedupe(warnings),
        "recommended_action": "Execute or verify the planned corrective action." if actions else "Build one corrective action plan.",
    }


def format_autonomous_pdf_corrective_action_report(
    corrective_action_id: str,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    loaded = load_autonomous_pdf_corrective_action(corrective_action_id, root=root)
    action = loaded.get("corrective_action")
    if not isinstance(action, Mapping):
        return "Autonomous PDF Corrective Action\n\nStatus: not_found"
    lines = [
        "Autonomous PDF Corrective Action",
        "",
        f"Document: {action.get('document_id')}",
        f"Source Revision: {action.get('source_revision')}",
        f"Remediation Case ID: {action.get('remediation_case_id')}",
        f"Action Type: {action.get('action_type')}",
        f"Review Decision: {action.get('review_decision')}",
        f"Original Benchmark Classification: {action.get('original_release_classification', 'unknown')}",
        f"Failed Gates: {', '.join(action.get('failed_release_gates', []) or ['none'])}",
        f"Action Status: {action.get('status')}",
        f"Execution Outcome: {action.get('execution_status')}",
        f"Verification Required: {'Yes' if action.get('verification_required') else 'No'}",
        f"Verification Outcome: {action.get('verification_outcome') or 'none'}",
        f"Closure Status: {action.get('closure_status') or 'open'}",
        f"Remaining Blockers: {', '.join(action.get('remaining_blockers', []) or ['none'])}",
        f"Recommended Action: {_recommended_next_action(action)}",
    ]
    if action.get("verification_metric_deltas"):
        lines.append("Metric Deltas:")
        for key, payload in (action.get("verification_metric_deltas") or {}).items():
            lines.append(f"- {key}: {_format_delta(payload)}")
    if not public_safe:
        lines.append(f"Action Fingerprint: {action.get('action_fingerprint')}")
    return "\n".join(lines)


def _ensure_dirs(root: Path | str) -> Path:
    base = remediation_backend._ensure_dirs(root)
    for folder in (ACTION_DIR, RECEIPT_DIR, "indexes"):
        (base / folder).mkdir(parents=True, exist_ok=True)
    defaults = (
        (ACTION_INDEX, "autonomous_pdf_corrective_action_index_v1"),
        (RECEIPT_INDEX, "autonomous_pdf_corrective_action_receipt_index_v1"),
    )
    for name, schema in defaults:
        path = base / "indexes" / name
        if not path.exists():
            analysis_backend._atomic_write_json(path, {"schema_version": schema, "items": [], "updated_at_utc": analysis_backend._now()})
    return base


def _load_case_context(base: Path, remediation_case_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    case = remediation_backend.load_autonomous_pdf_remediation_case(remediation_case_id, root=base).get("remediation_case")
    blockers: list[str] = []
    if not isinstance(case, Mapping):
        return None, None, None, None, ["remediation_case_missing"]
    plan_loaded = remediation_backend.load_autonomous_pdf_remediation_plan(str(case.get("remediation_plan_id") or ""), root=base)
    plan = plan_loaded.get("remediation_plan")
    if not isinstance(plan, Mapping):
        blockers.append("remediation_plan_missing")
    review_receipt = _find_review_receipt(base, str(case.get("remediation_plan_id") or ""), remediation_case_id, str(case.get("review_decision") or ""))
    if not str(case.get("review_decision") or ""):
        blockers.append("review_decision_missing")
    if review_receipt is None:
        blockers.append("review_receipt_missing")
    benchmark_result = benchmark_backend.load_autonomous_pdf_benchmark_result(str(case.get("benchmark_result_id") or ""), root=base).get("benchmark_result")
    if not isinstance(benchmark_result, Mapping):
        blockers.append("benchmark_result_missing")
    elif benchmark_result.get("stale"):
        blockers.append("benchmark_result_stale")
    if plan and str(plan.get("benchmark_result_id") or "") != str(case.get("benchmark_result_id") or ""):
        blockers.append("case_plan_benchmark_mismatch")
    if not str(case.get("document_id") or "") or remediation_backend._normalize_revision(case.get("source_revision")) is None:
        blockers.append("case_provenance_missing")
    if str(case.get("current_status") or "") == "closed":
        blockers.append("case_already_closed")
    return dict(case), dict(plan) if isinstance(plan, Mapping) else None, dict(review_receipt) if isinstance(review_receipt, Mapping) else None, dict(benchmark_result) if isinstance(benchmark_result, Mapping) else None, _dedupe(blockers)


def _validate_action_compatibility(case: Mapping[str, Any], action_type: str) -> list[str]:
    blockers = []
    if action_type not in SUPPORTED_ACTIONS:
        blockers.append("unsupported_action_type")
        return blockers
    if not _review_action_allowed(str(case.get("review_decision") or ""), action_type, str(case.get("root_cause_classification") or "")):
        blockers.append("review_action_incompatible")
    return blockers


def _validate_action_payload(case: Mapping[str, Any], action_type: str, payload: Mapping[str, Any], benchmark_result: Mapping[str, Any], base: Path) -> list[str]:
    blockers = []
    if action_type == "apply_benchmark_manifest_amendment":
        operation = str(payload.get("operation") or "")
        collection = str(payload.get("collection") or "")
        record = payload.get("record")
        if str(case.get("root_cause_classification") or "") != "benchmark_manifest_defect":
            blockers.append("benchmark_manifest_root_cause_required")
        if operation not in {"add_expected_record", "replace_expected_record", "remove_expected_record"}:
            blockers.append("unsupported_manifest_amendment_operation")
        if collection not in {"section_anchors", "citations", "proposals", "rule_candidates", "certified_rules", "blocked_candidates"}:
            blockers.append("unsupported_manifest_collection")
        if not isinstance(record, Mapping):
            blockers.append("manifest_record_required")
        manifest = _load_manifest_for_result(base, benchmark_result)
        if not isinstance(manifest, Mapping):
            blockers.append("benchmark_manifest_missing")
        elif "autonomous" in str(payload).lower():
            blockers.append("manifest_amendment_must_remain_independent")
    return blockers


def _review_action_allowed(review_decision: str, action_type: str, root_cause_classification: str) -> bool:
    allowed = REVIEW_ACTION_COMPATIBILITY.get(review_decision, set())
    if action_type not in allowed:
        return False
    if action_type == "create_phase_9j_fix_package":
        return root_cause_classification == "phase_9j_pipeline_defect"
    if action_type == "create_phase_9k_fix_package":
        return root_cause_classification == "phase_9k_comparison_defect"
    return True


def _action_fingerprint(case: Mapping[str, Any], action_type: str, payload: Mapping[str, Any], review_receipt: Mapping[str, Any]) -> str:
    return analysis_backend._hash_payload({
        "remediation_case_id": case.get("remediation_case_id"),
        "document_id": case.get("document_id"),
        "source_revision": case.get("source_revision"),
        "review_receipt_id": review_receipt.get("corrective_source_receipt_id"),
        "review_decision": case.get("review_decision"),
        "action_type": action_type,
        "payload": _sanitize_action_payload(action_type, payload),
        "schema": CORRECTIVE_SCHEMA_VERSION,
    })


def _corrective_action_id(case: Mapping[str, Any], action_type: str, action_fingerprint: str) -> str:
    return f"autonomous_corrective_action_{analysis_backend._hash_payload({'case': case.get('remediation_case_id'), 'action_type': action_type, 'action_fingerprint': action_fingerprint})[7:23]}"


def _sanitize_action_payload(action_type: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    if action_type == "apply_benchmark_manifest_amendment":
        return {
            "operation": payload.get("operation"),
            "collection": payload.get("collection"),
            "record_fingerprint": analysis_backend._hash_payload(payload.get("record", {})) if isinstance(payload.get("record"), Mapping) else None,
        }
    if action_type == "request_new_source_revision":
        return {"reason": str(payload.get("reason") or "source_revision_required")[:120]}
    return {"summary": str(payload.get("summary") or "bounded_corrective_action")[:160]}


def _execute_action(base: Path, action: dict[str, Any]) -> dict:
    action_type = str(action.get("action_type") or "")
    receipt_payload: dict[str, Any]
    updated = dict(action)
    manifest_before = None
    manifest_path = None
    before_action = _read_json(_action_path(base, str(action.get("corrective_action_id") or "")))
    before_receipt_index = _read_json(base / "indexes" / RECEIPT_INDEX)
    before_action_index = _read_json(base / "indexes" / ACTION_INDEX)
    receipt_payload = {}
    try:
        if action_type == "close_expected_behavior":
            updated["execution_status"] = "closed"
            updated["status"] = "closed"
            updated["closure_status"] = "accepted_expected_behavior"
        elif action_type == "close_no_action":
            updated["execution_status"] = "closed"
            updated["status"] = "closed"
            updated["closure_status"] = "closed_no_action"
        elif action_type == "request_new_source_revision":
            updated["execution_status"] = "requires_new_source_revision"
            updated["status"] = "requires_new_source_revision"
            updated["requested_source_revision_reason"] = str((action.get("payload") or {}).get("reason") or "new_source_revision_requested")
        elif action_type in {"create_phase_9j_fix_package", "create_phase_9k_fix_package"}:
            updated["execution_status"] = "verification_required"
            updated["status"] = "verification_required"
            updated["developer_fix_package"] = _build_fix_package(action)
        elif action_type == "apply_benchmark_manifest_amendment":
            benchmark_result = benchmark_backend.load_autonomous_pdf_benchmark_result(str(action.get("benchmark_result_id") or ""), root=base).get("benchmark_result")
            if not isinstance(benchmark_result, Mapping):
                return {"status": "blocked", "corrective_action_id": action.get("corrective_action_id"), "blockers": ["benchmark_result_missing"], "warnings": []}
            manifest = _load_manifest_for_result(base, benchmark_result)
            if not isinstance(manifest, Mapping):
                return {"status": "blocked", "corrective_action_id": action.get("corrective_action_id"), "blockers": ["benchmark_manifest_missing"], "warnings": []}
            if str(manifest.get("manifest_fingerprint") or "") != str(action.get("original_manifest_fingerprint") or ""):
                return {"status": "stale", "corrective_action_id": action.get("corrective_action_id"), "blockers": ["manifest_fingerprint_changed"], "warnings": []}
            manifest_before = deepcopy(dict(manifest))
            manifest_path = benchmark_backend._manifest_path(base, str(manifest.get("benchmark_id") or ""))
            amended = _apply_manifest_amendment(dict(manifest), dict(action.get("payload") or {}))
            amended["manifest_fingerprint"] = analysis_backend._hash_payload({k: v for k, v in amended.items() if k != "manifest_fingerprint"})
            validation_before = benchmark_backend._read_json(manifest_path)
            result = _write_manifest_with_validation(base, manifest_path, amended)
            if result == "rollback_failed":
                return {"status": "rollback_failed", "corrective_action_id": action.get("corrective_action_id"), "blockers": ["manifest_rollback_failed"], "warnings": []}
            if result == "failed_rolled_back":
                return {"status": "failed_rolled_back", "corrective_action_id": action.get("corrective_action_id"), "blockers": ["manifest_amendment_failed_rolled_back"], "warnings": []}
            updated["execution_status"] = "verification_required"
            updated["status"] = "verification_required"
            updated["updated_manifest_fingerprint"] = amended["manifest_fingerprint"]
            updated["previous_manifest_fingerprint"] = manifest_before.get("manifest_fingerprint")
            updated["manifest_amendment_evidence"] = {
                "previous_manifest_fingerprint": manifest_before.get("manifest_fingerprint"),
                "updated_manifest_fingerprint": amended.get("manifest_fingerprint"),
                "previous_manifest_snapshot_fingerprint": analysis_backend._hash_payload(manifest_before),
            }
        else:
            return {"status": "blocked", "corrective_action_id": action.get("corrective_action_id"), "blockers": ["unsupported_action_type"], "warnings": []}
        updated["updated_at_utc"] = analysis_backend._now()
        receipt_payload = _receipt_payload(
            receipt_kind="execution",
            corrective_action_id=str(action.get("corrective_action_id") or ""),
            action=updated,
            payload={
                "action_type": action_type,
                "payload_summary": _sanitize_action_payload(action_type, dict(action.get("payload") or {})),
                "manifest_evidence": updated.get("manifest_amendment_evidence"),
                "developer_fix_package": updated.get("developer_fix_package"),
            },
        )
        before_receipt = _read_json(_receipt_path(base, str(receipt_payload["corrective_action_receipt_id"])))
        analysis_backend._atomic_write_json(_action_path(base, str(action.get("corrective_action_id") or "")), updated)
        analysis_backend._atomic_write_json(_receipt_path(base, str(receipt_payload["corrective_action_receipt_id"])), receipt_payload)
        _update_action_index(base)
        _update_receipt_index(base)
        return {"status": str(updated.get("status") or "executed"), "corrective_action_id": action.get("corrective_action_id"), "execution_status": updated.get("execution_status"), "writes_performed": 2}
    except Exception:
        _restore_json(_action_path(base, str(action.get("corrective_action_id") or "")), before_action)
        _restore_json(base / "indexes" / ACTION_INDEX, before_action_index)
        _restore_json(base / "indexes" / RECEIPT_INDEX, before_receipt_index)
        if manifest_path is not None and manifest_before is not None:
            analysis_backend._atomic_write_json(manifest_path, manifest_before)
        return {"status": "corrupt", "corrective_action_id": action.get("corrective_action_id"), "blockers": ["corrective_action_execution_write_failure"], "warnings": []}


def _apply_manifest_amendment(manifest: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    expected = deepcopy(dict(manifest.get("expected") or {}))
    collection = str(payload.get("collection") or "")
    operation = str(payload.get("operation") or "")
    record = deepcopy(dict(payload.get("record") or {}))
    current = list(expected.get(collection, []) or [])
    key_fn = _manifest_key_fn(collection)
    record_key = key_fn(record)
    if operation == "add_expected_record":
        if any(key_fn(item) == record_key for item in current if isinstance(item, Mapping)):
            raise ValueError("duplicate_expected_identity")
        current.append(record)
    elif operation == "replace_expected_record":
        replaced = False
        target_key = payload.get("target_key") or record_key
        next_items = []
        for item in current:
            if isinstance(item, Mapping) and key_fn(item) == target_key and not replaced:
                next_items.append(record)
                replaced = True
            else:
                next_items.append(item)
        if not replaced:
            raise ValueError("expected_record_not_found")
        current = next_items
    elif operation == "remove_expected_record":
        target_key = payload.get("target_key") or record_key
        current = [item for item in current if not (isinstance(item, Mapping) and key_fn(item) == target_key)]
    else:
        raise ValueError("unsupported_manifest_operation")
    expected[collection] = current
    manifest["expected"] = expected
    return manifest


def _manifest_key_fn(collection: str):
    mapping = {
        "section_anchors": benchmark_backend._anchor_key,
        "citations": benchmark_backend._citation_key,
        "proposals": benchmark_backend._proposal_key,
        "rule_candidates": benchmark_backend._rule_candidate_key,
        "certified_rules": benchmark_backend._rule_key,
        "blocked_candidates": benchmark_backend._blocker_key,
    }
    return mapping[collection]


def _write_manifest_with_validation(base: Path, manifest_path: Path, amended: dict[str, Any]) -> str:
    before = benchmark_backend._read_json(manifest_path)
    try:
        analysis_backend._atomic_write_json(manifest_path, amended)
        validation = benchmark_backend.validate_autonomous_pdf_benchmark_manifest(str(amended.get("benchmark_id") or ""), root=base)
        if str(validation.get("status") or "") != "valid":
            raise ValueError("amended_manifest_invalid")
        written = benchmark_backend._read_json(manifest_path)
        if not isinstance(written, Mapping) or str(written.get("manifest_fingerprint") or "") != str(amended.get("manifest_fingerprint") or ""):
            raise ValueError("manifest_post_write_verification_failed")
        return "ok"
    except Exception:
        try:
            if before is None:
                if manifest_path.exists():
                    manifest_path.unlink()
            else:
                analysis_backend._atomic_write_json(manifest_path, before)
            restored = benchmark_backend._read_json(manifest_path)
            if (before is None and not manifest_path.exists()) or (isinstance(before, Mapping) and isinstance(restored, Mapping) and str(restored.get("manifest_fingerprint") or "") == str(before.get("manifest_fingerprint") or "")):
                return "failed_rolled_back"
            return "rollback_failed"
        except Exception:
            return "rollback_failed"


def _load_manifest_for_result(base: Path, benchmark_result: Mapping[str, Any]) -> dict[str, Any] | None:
    benchmark_id = _find_benchmark_id_for_result(base, str(benchmark_result.get("benchmark_result_id") or ""))
    if not benchmark_id:
        return None
    return benchmark_backend._read_json(benchmark_backend._manifest_path(base, benchmark_id))


def _find_benchmark_id_for_result(base: Path, benchmark_result_id: str) -> str | None:
    result = benchmark_backend._find_result_by_id(base, benchmark_result_id)
    if isinstance(result, Mapping):
        return str(result.get("benchmark_id") or "")
    return None


def _find_review_receipt(base: Path, remediation_plan_id: str, remediation_case_id: str, decision: str) -> dict[str, Any] | None:
    matches = []
    for item in remediation_backend._load_receipts_for_plan(base, remediation_plan_id):
        if str(item.get("receipt_kind") or "") != "review":
            continue
        payload = item.get("payload") or {}
        if str(payload.get("remediation_case_id") or "") == remediation_case_id:
            matches.append({
                "corrective_source_receipt_id": item.get("remediation_receipt_id"),
                "decision": payload.get("decision"),
                "note": payload.get("note"),
            })
    if len({str(item.get("decision") or "") for item in matches}) > 1:
        return None
    for item in matches:
        if str(item.get("decision") or "") == decision:
            return item
    return None


def _find_action_for_case(base: Path, remediation_case_id: str) -> dict[str, Any] | None:
    for item in _load_all_actions(base):
        if str(item.get("remediation_case_id") or "") == remediation_case_id:
            return item
    return None


def _latest_receipt(base: Path, remediation_plan_id: str, receipt_kind: str) -> dict[str, Any] | None:
    receipts = [item for item in remediation_backend._load_receipts_for_plan(base, remediation_plan_id) if str(item.get("receipt_kind") or "") == receipt_kind]
    return receipts[-1] if receipts else None


def _build_fix_package(action: Mapping[str, Any]) -> dict[str, Any]:
    phase = "9J" if str(action.get("action_type") or "") == "create_phase_9j_fix_package" else "9K"
    return {
        "affected_phase": phase,
        "remediation_case_id": action.get("remediation_case_id"),
        "stage": action.get("stage"),
        "reason_codes": list(action.get("reason_codes", [])),
        "mismatch_identities": list(action.get("related_mismatch_ids", [])),
        "failed_gates": list(action.get("failed_release_gates", [])),
        "safety_violations": list(action.get("related_safety_violations", [])),
        "expected_behavior": "Resolve only the bounded case without expanding scope.",
        "prohibited_scope_expansion": True,
        "verification_benchmark_required": True,
    }


def _closure_status(action: Mapping[str, Any]) -> str:
    if str(action.get("execution_status") or "") == "requires_new_source_revision":
        return "requires_new_source_revision"
    if str(action.get("action_type") or "") == "close_expected_behavior":
        return "accepted_expected_behavior"
    if str(action.get("action_type") or "") == "close_no_action":
        return "closed_no_action"
    return str(action.get("verification_outcome") or "persists")


def _action_is_current(base: Path, action: Mapping[str, Any]) -> bool:
    case, _plan, review_receipt, benchmark_result, blockers = _load_case_context(base, str(action.get("remediation_case_id") or ""))
    if blockers or case is None or review_receipt is None or benchmark_result is None:
        return False
    if str(action.get("action_fingerprint") or "") != _action_fingerprint(case, str(action.get("action_type") or ""), dict(action.get("payload") or {}), review_receipt):
        return False
    if str(action.get("original_benchmark_fingerprint") or "") != _benchmark_fingerprint(benchmark_result):
        return False
    if bool(action.get("verification_required")) and str(action.get("execution_status") or "") == "planned":
        return True
    if str(action.get("action_type") or "") == "apply_benchmark_manifest_amendment":
        manifest = _load_manifest_for_result(base, benchmark_result)
        if isinstance(manifest, Mapping) and str(manifest.get("manifest_fingerprint") or "") != str(action.get("original_manifest_fingerprint") or "") and str(action.get("execution_status") or "") == "planned":
            return False
    return True


def _receipt_payload(*, receipt_kind: str, corrective_action_id: str, action: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    receipt_id = f"autonomous_corrective_action_receipt_{analysis_backend._hash_payload({'kind': receipt_kind, 'corrective_action_id': corrective_action_id, 'payload': payload})[7:23]}"
    return {
        "schema_version": RECEIPT_SCHEMA,
        "corrective_action_receipt_id": receipt_id,
        "receipt_kind": receipt_kind,
        "corrective_action_id": corrective_action_id,
        "remediation_case_id": action.get("remediation_case_id"),
        "remediation_plan_id": action.get("remediation_plan_id"),
        "document_id": action.get("document_id"),
        "source_revision": action.get("source_revision"),
        "payload": deepcopy(dict(payload)),
        "created_at_utc": analysis_backend._now(),
    }


def _benchmark_fingerprint(result: Mapping[str, Any]) -> str:
    return remediation_backend._benchmark_fingerprint(result)


def _recommended_next_action(action: Mapping[str, Any]) -> str:
    if str(action.get("closure_status") or ""):
        return "Corrective action is closed for this remediation case."
    if bool(action.get("verification_required")) and not str(action.get("verification_outcome") or ""):
        return "Run a later same-revision benchmark and verify the action."
    if str(action.get("execution_status") or "") == "planned":
        return "Execute the approved corrective action."
    return "Close the corrective action when its current outcome is acceptable."


def _format_delta(payload: Any) -> str:
    return remediation_backend._format_delta(payload)


def _load_all_actions(base: Path) -> list[dict[str, Any]]:
    return _load_dir_json(base / ACTION_DIR, "corrective_action_id")


def _load_all_receipts(base: Path) -> list[dict[str, Any]]:
    return _load_dir_json(base / RECEIPT_DIR, "corrective_action_receipt_id")


def _load_receipts_for_action(base: Path, corrective_action_id: str) -> list[dict[str, Any]]:
    return [item for item in _load_all_receipts(base) if str(item.get("corrective_action_id") or "") == corrective_action_id]


def _update_action_index(base: Path) -> None:
    items = []
    for item in _load_all_actions(base):
        items.append({
            "corrective_action_id": item.get("corrective_action_id"),
            "remediation_case_id": item.get("remediation_case_id"),
            "action_type": item.get("action_type"),
            "status": item.get("status"),
            "document_id": item.get("document_id"),
            "source_revision": item.get("source_revision"),
        })
    analysis_backend._atomic_write_json(base / "indexes" / ACTION_INDEX, {"schema_version": "autonomous_pdf_corrective_action_index_v1", "items": sorted(items, key=lambda item: str(item.get("corrective_action_id") or "")), "updated_at_utc": analysis_backend._now()})


def _update_receipt_index(base: Path) -> None:
    items = []
    for item in _load_all_receipts(base):
        items.append({
            "corrective_action_receipt_id": item.get("corrective_action_receipt_id"),
            "corrective_action_id": item.get("corrective_action_id"),
            "receipt_kind": item.get("receipt_kind"),
            "document_id": item.get("document_id"),
            "source_revision": item.get("source_revision"),
        })
    analysis_backend._atomic_write_json(base / "indexes" / RECEIPT_INDEX, {"schema_version": "autonomous_pdf_corrective_action_receipt_index_v1", "items": sorted(items, key=lambda item: str(item.get("corrective_action_receipt_id") or "")), "updated_at_utc": analysis_backend._now()})


def _load_dir_json(folder: Path, required_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not folder.exists():
        return items
    for path in sorted(folder.glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping) and payload.get(required_id):
            items.append(dict(payload))
    return items


def _action_path(base: Path, corrective_action_id: str) -> Path:
    return base / ACTION_DIR / f"{analysis_backend._safe_id(corrective_action_id)}.json"


def _receipt_path(base: Path, corrective_action_receipt_id: str) -> Path:
    return base / RECEIPT_DIR / f"{analysis_backend._safe_id(corrective_action_receipt_id)}.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    return benchmark_backend._read_json(path)


def _restore_json(path: Path, payload: dict[str, Any] | None) -> None:
    benchmark_backend._restore_json(path, payload)


def _dedupe(values: list[str]) -> list[str]:
    return remediation_backend._dedupe(values)
