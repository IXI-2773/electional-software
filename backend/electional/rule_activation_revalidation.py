"""Runtime revalidation for active rules created through proposal activation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

from .citation_draft_review import _atomic_write_json, _hash_payload, _now, _read_json, _restore_json
from .pdf_viewport import _blocked
from .proposal_promotion import _load_proposal, _load_receipt_for_proposal, validate_proposal_promotion_provenance
from .proposal_rule_activation import (
    _load_rule_activation_receipt_by_id,
    _load_rule_activation_receipt_for_proposal,
    _rule_fingerprint,
    rollback_proposal_rule_activation,
)
from .rules import active_rule_index_hash, active_rule_index_state, load_rule
from .source_documents import SOURCE_DOCUMENT_ROOT
from .source_impact_analysis import QUEUE_INDEX, _queue_item_path, _update_queue_index, ensure_source_impact_dirs, list_source_revalidation_queue
from .source_knowledge import ensure_source_knowledge_dirs

REVALIDATION_REVIEW_DIR = "rule_activation_revalidation_reviews"
CERTIFICATION_RECEIPT_DIR = "rule_activation_certification_receipts"
REVIEW_INDEX = "rule_activation_revalidation_review_index.json"
CERTIFICATION_INDEX = "rule_activation_certification_receipt_index.json"
REVALIDATION_REVIEW_SCHEMA_VERSION = "rule_activation_revalidation_review_v1"
CERTIFICATION_RECEIPT_SCHEMA_VERSION = "rule_activation_certification_receipt_v1"
RUNTIME_VALIDATION_SCHEMA_VERSION = "rule_runtime_contract_validation_v1"
CONTRACT_PLAN_SCHEMA_VERSION = "rule_runtime_contract_plan_v1"
ALLOWED_DECISIONS = {"certify", "request_changes", "reject_and_rollback"}


def build_rule_activation_revalidation_workspace(revalidation_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = _ensure_rule_activation_revalidation_dirs(root)
    queue_item = _load_revalidation_item(base, revalidation_id)
    if queue_item is None:
        return {"revalidation_id": revalidation_id, "status": "not_found", "warnings": ["revalidation_not_found"]}
    provenance = validate_rule_activation_revalidation_provenance(revalidation_id, root=base)
    review = _load_revalidation_review_for_queue(base, revalidation_id)
    receipt = _load_certification_receipt_for_revalidation(base, revalidation_id)
    runtime_validation = _load_runtime_validation_for_revalidation(base, revalidation_id)
    plan = build_rule_runtime_contract_plan(revalidation_id, root=base)
    return {
        "revalidation_id": revalidation_id,
        "revalidation_status": queue_item.get("status"),
        "reason": queue_item.get("reason"),
        "rule_id": queue_item.get("rule_id"),
        "rule_status": "active" if provenance.get("rule_active") else "inactive",
        "proposal_id": queue_item.get("proposal_id"),
        "activation_receipt_id": queue_item.get("activation_receipt_id"),
        "activation_provenance_status": "valid" if provenance.get("valid") else "invalid",
        "runtime_evaluator_status": "available" if _load_canonical_rule_evaluator() is not None else "unavailable",
        "contract_plan_status": "ready" if not plan.get("blockers") else "blocked",
        "runtime_validation_status": str((runtime_validation or {}).get("status") or "not_run"),
        "review_status": str((review or {}).get("review_status") or "pending"),
        "certification_receipt_id": (receipt or {}).get("certification_receipt_id"),
        "warnings": list(dict.fromkeys([*provenance.get("warnings", []), *plan.get("warnings", [])])),
        "blockers": list(dict.fromkeys([*provenance.get("blockers", []), *plan.get("blockers", [])])),
        "recommended_action": "Run the focused runtime contract validation." if not provenance.get("blockers") else "Resolve runtime revalidation blockers before review.",
    }


def validate_rule_activation_revalidation_provenance(revalidation_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = _ensure_rule_activation_revalidation_dirs(root)
    queue_item = _load_revalidation_item(base, revalidation_id)
    if queue_item is None:
        return {"revalidation_id": revalidation_id, "valid": False, "warnings": [], "blockers": ["revalidation_not_found"]}
    blockers: list[str] = []
    if queue_item.get("reason") != "proposal_rule_activation":
        blockers.append("revalidation_reason_invalid")
    if queue_item.get("status") != "pending_review":
        blockers.append("revalidation_not_pending_review")
    rule_id = str(queue_item.get("rule_id") or "")
    rule = load_rule(rule_id, root=base) if rule_id else None
    activation_receipt = _load_rule_activation_receipt_by_id(base, str(queue_item.get("activation_receipt_id") or ""))
    proposal = _load_proposal(base, str(queue_item.get("proposal_id") or ""))
    promotion_receipt = _load_receipt_for_proposal(base, str(queue_item.get("proposal_id") or "")) if proposal is not None else None
    promotion_provenance = validate_proposal_promotion_provenance(str(queue_item.get("proposal_id") or ""), root=base) if proposal is not None else {"blockers": ["proposal_not_found"]}
    if not isinstance(rule, dict):
        blockers.append("active_rule_missing")
    if not isinstance(activation_receipt, dict):
        blockers.append("activation_receipt_missing")
    if proposal is None:
        blockers.append("proposal_not_found")
    if promotion_receipt is None:
        blockers.append("proposal_promotion_receipt_missing")
    if promotion_provenance.get("blockers"):
        blockers.extend(list(promotion_provenance.get("blockers", [])))
    if isinstance(rule, dict) and str(rule.get("status") or "") != "active":
        blockers.append("active_rule_not_active")
    if isinstance(activation_receipt, dict) and isinstance(rule, dict):
        if activation_receipt.get("rule_id") != rule_id:
            blockers.append("activation_receipt_rule_mismatch")
        if activation_receipt.get("created_rule_hash") != _hash_payload(rule):
            blockers.append("rule_hash_mismatch")
        if activation_receipt.get("candidate_fingerprint") != _rule_fingerprint(rule):
            blockers.append("candidate_fingerprint_mismatch")
    active_index_ids = {str(entry.get("rule_id") or "") for entry in active_rule_index_state(root=base).get("entries", []) if isinstance(entry, dict)}
    if rule_id and rule_id not in active_index_ids:
        blockers.append("active_rule_index_membership_missing")
    return {
        "revalidation_id": revalidation_id,
        "valid": not blockers,
        "rule_id": rule_id or None,
        "rule_active": isinstance(rule, dict) and str(rule.get("status") or "") == "active",
        "rule_hash_valid": isinstance(activation_receipt, dict) and isinstance(rule, dict) and activation_receipt.get("created_rule_hash") == _hash_payload(rule),
        "candidate_fingerprint_valid": isinstance(activation_receipt, dict) and isinstance(rule, dict) and activation_receipt.get("candidate_fingerprint") == _rule_fingerprint(rule),
        "proposal_provenance_valid": not promotion_provenance.get("blockers"),
        "citation_evidence_valid": not promotion_provenance.get("blockers"),
        "source_revision_current": "source_revision_changed" not in set(promotion_provenance.get("blockers", [])),
        "warnings": [],
        "blockers": list(dict.fromkeys(blockers)),
    }


def build_rule_runtime_contract_plan(revalidation_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = _ensure_rule_activation_revalidation_dirs(root)
    provenance = validate_rule_activation_revalidation_provenance(revalidation_id, root=base)
    if provenance.get("blockers"):
        return {"revalidation_id": revalidation_id, "cases": [], "warnings": [], "blockers": list(provenance.get("blockers", []))}
    rule = load_rule(str(provenance.get("rule_id") or ""), root=base)
    condition = dict((rule or {}).get("condition") or {})
    field = str(condition.get("field") or "")
    operator = str(condition.get("operator") or (rule or {}).get("operator") or "")
    value = condition.get("value")
    cases: list[dict[str, Any]] = []
    blockers: list[str] = []
    if not field or not operator:
        blockers.append("required_contract_case_cannot_be_built")
    else:
        positive, negative, boundary = _build_operator_cases(field, operator, value)
        if positive is None or negative is None:
            blockers.append("required_contract_case_cannot_be_built")
        else:
            cases.extend([positive, negative])
            if boundary is not None:
                cases.append(boundary)
    return {
        "schema_version": CONTRACT_PLAN_SCHEMA_VERSION,
        "revalidation_id": revalidation_id,
        "rule_id": provenance.get("rule_id"),
        "rule_fingerprint": _rule_fingerprint(rule if isinstance(rule, Mapping) else None),
        "evaluator_identity": "canonical_rule_evaluator" if _load_canonical_rule_evaluator() is not None else "rule_runtime_evaluator_unavailable",
        "cases": cases,
        "warnings": [],
        "blockers": blockers,
    }


def run_rule_runtime_contract_validation(revalidation_id: str, regenerate: bool = False, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = _ensure_rule_activation_revalidation_dirs(root)
    existing = None if regenerate else _load_runtime_validation_for_revalidation(base, revalidation_id)
    if isinstance(existing, dict) and existing.get("status") in {"passed", "passed_with_warnings", "blocked", "failed", "error", "stale"}:
        return existing
    provenance = validate_rule_activation_revalidation_provenance(revalidation_id, root=base)
    plan = build_rule_runtime_contract_plan(revalidation_id, root=base)
    runtime_validation_id = _runtime_validation_id(revalidation_id)
    queue_item = _load_revalidation_item(base, revalidation_id) or {}
    rule = load_rule(str(queue_item.get("rule_id") or ""), root=base)
    result = {
        "schema_version": RUNTIME_VALIDATION_SCHEMA_VERSION,
        "runtime_validation_id": runtime_validation_id,
        "revalidation_id": revalidation_id,
        "rule_id": queue_item.get("rule_id"),
        "status": "blocked",
        "required_case_count": len([case for case in plan.get("cases", []) if case.get("required")]),
        "passed_case_count": 0,
        "failed_case_count": 0,
        "exception_count": 0,
        "persistent_state_mutated": False,
        "cases": [],
        "rule_hash_before": _hash_payload(rule) if isinstance(rule, dict) else None,
        "rule_hash_after": _hash_payload(rule) if isinstance(rule, dict) else None,
        "warnings": [],
        "blockers": list(dict.fromkeys([*provenance.get("blockers", []), *plan.get("blockers", [])])),
    }
    evaluator = _load_canonical_rule_evaluator()
    if evaluator is None:
        result["blockers"] = list(dict.fromkeys([*result.get("blockers", []), "rule_runtime_evaluator_unavailable"]))
        _save_runtime_validation(base, result)
        return result
    try:
        before_state = _revalidation_persistent_state_hash(base, queue_item)
        normalized_cases = []
        passed = 0
        failed = 0
        exceptions = 0
        for case in plan.get("cases", []):
            actual = _normalize_evaluator_result(evaluator(rule, case.get("input", {})))
            expected = bool(case.get("expected_match"))
            status = "pass" if actual == expected else "fail"
            normalized_cases.append({"case_id": case.get("case_id"), "expected_match": expected, "actual_match": actual, "status": status})
            if status == "pass":
                passed += 1
            elif case.get("required"):
                failed += 1
        after_state = _revalidation_persistent_state_hash(base, queue_item)
        result.update(
            {
                "status": "passed" if failed == 0 and before_state == after_state else "failed",
                "passed_case_count": passed,
                "failed_case_count": failed,
                "exception_count": exceptions,
                "persistent_state_mutated": before_state != after_state,
                "cases": normalized_cases,
                "blockers": ["persistent_state_mutation_detected"] if before_state != after_state else ([] if failed == 0 else ["runtime_contract_case_failed"]),
            }
        )
    except Exception:
        result["status"] = "error"
        result["exception_count"] = 1
        result["blockers"] = ["runtime_evaluation_raised_exception"]
    _save_runtime_validation(base, result)
    return result


def save_rule_activation_revalidation_decision(
    revalidation_id: str,
    decision: str,
    reviewer_note: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    if decision not in ALLOWED_DECISIONS:
        raise ValueError(f"Unsupported rule activation revalidation decision: {decision}")
    base = _ensure_rule_activation_revalidation_dirs(root)
    workspace = build_rule_activation_revalidation_workspace(revalidation_id, root=base)
    if workspace.get("status") == "not_found":
        raise FileNotFoundError(revalidation_id)
    note = str(reviewer_note or "").strip() or None
    runtime_validation = run_rule_runtime_contract_validation(revalidation_id, root=base)
    blockers: list[str] = []
    if decision == "certify":
        if workspace.get("blockers"):
            blockers.extend(list(workspace.get("blockers", [])))
        if runtime_validation.get("status") not in {"passed", "passed_with_warnings"}:
            blockers.append("runtime_validation_not_certifiable")
        if runtime_validation.get("persistent_state_mutated"):
            blockers.append("persistent_state_mutation_detected")
        if runtime_validation.get("failed_case_count", 0):
            blockers.append("runtime_contract_case_failed")
    else:
        if not note:
            blockers.append("reviewer_note_required")
    if blockers:
        return _blocked("rule_activation_revalidation_review_blocked", blockers=list(dict.fromkeys(blockers)))
    existing = _load_revalidation_review_for_queue(base, revalidation_id)
    payload = {
        "schema_version": REVALIDATION_REVIEW_SCHEMA_VERSION,
        "revalidation_review_id": (existing or {}).get("revalidation_review_id") or _revalidation_review_id(revalidation_id),
        "revalidation_id": revalidation_id,
        "rule_id": workspace.get("rule_id"),
        "proposal_id": workspace.get("proposal_id"),
        "decision": decision,
        "review_status": "approved" if decision == "certify" else "changes_requested" if decision == "request_changes" else "rejected_pending_rollback",
        "runtime_validation_id": runtime_validation.get("runtime_validation_id"),
        "runtime_validation_fingerprint": _hash_payload(runtime_validation),
        "reviewer_note": note,
        "review_revision": int((existing or {}).get("review_revision") or 0) + (0 if existing and _same_review(existing, decision, note, runtime_validation) else 1),
        "created_at_utc": (existing or {}).get("created_at_utc") or _now(),
        "updated_at_utc": _now(),
        "warnings": list(runtime_validation.get("warnings", [])),
    }
    if existing and _same_payload(existing, payload):
        return {"status": "saved", "review": existing, "writes_performed": 0}
    path = _review_path(base, str(payload["revalidation_review_id"]))
    before_review = _read_json(path)
    before_index = _read_json(base / "indexes" / REVIEW_INDEX)
    try:
        _atomic_write_json(path, payload)
        _update_revalidation_review_index(base)
    except Exception:
        _restore_json(path, before_review)
        _restore_json(base / "indexes" / REVIEW_INDEX, before_index)
        return {"status": "failed_rolled_back", "classification": "revalidation_review_write_failure", "warnings": []}
    return {"status": "saved", "review": payload, "writes_performed": 1}


def complete_rule_activation_revalidation(revalidation_review_id: str, confirmation: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = _ensure_rule_activation_revalidation_dirs(root)
    review = _load_revalidation_review_by_id(base, revalidation_review_id)
    if review is None:
        raise FileNotFoundError(revalidation_review_id)
    revalidation_id = str(review.get("revalidation_id") or "")
    queue_item = _load_revalidation_item(base, revalidation_id)
    if queue_item is None:
        return _blocked("rule_certification_state_diverged", blockers=["matching_revalidation_missing"])
    certification_receipt = _load_certification_receipt_for_revalidation(base, revalidation_id)
    if review.get("decision") == "certify":
        if confirmation != "CERTIFY":
            return _blocked("certify_confirmation_required", blockers=["certify_confirmation_required"])
        runtime_validation = _load_runtime_validation_for_revalidation(base, revalidation_id)
        provenance = validate_rule_activation_revalidation_provenance(revalidation_id, root=base)
        if certification_receipt and queue_item.get("status") == "resolved":
            return {
                "status": "already_certified",
                "rule_id": queue_item.get("rule_id"),
                "certification_receipt_id": certification_receipt.get("certification_receipt_id"),
                "writes_performed": 0,
            }
        blockers: list[str] = []
        if provenance.get("blockers"):
            blockers.extend(list(provenance.get("blockers", [])))
        if not isinstance(runtime_validation, dict) or runtime_validation.get("status") not in {"passed", "passed_with_warnings"}:
            blockers.append("runtime_validation_not_certifiable")
        if runtime_validation and _hash_payload(runtime_validation) != review.get("runtime_validation_fingerprint"):
            blockers.append("runtime_validation_fingerprint_mismatch")
        if blockers:
            return _blocked("rule_certification_blocked", blockers=list(dict.fromkeys(blockers)))
        receipt_id = _certification_receipt_id(revalidation_id)
        receipt_payload = {
            "schema_version": CERTIFICATION_RECEIPT_SCHEMA_VERSION,
            "certification_receipt_id": receipt_id,
            "revalidation_id": revalidation_id,
            "revalidation_review_id": revalidation_review_id,
            "runtime_validation_id": runtime_validation.get("runtime_validation_id"),
            "rule_id": queue_item.get("rule_id"),
            "proposal_id": queue_item.get("proposal_id"),
            "activation_receipt_id": queue_item.get("activation_receipt_id"),
            "document_id": queue_item.get("document_id"),
            "source_revision": queue_item.get("source_revision"),
            "rule_hash": runtime_validation.get("rule_hash_after"),
            "runtime_validation_fingerprint": _hash_payload(runtime_validation),
            "required_case_count": runtime_validation.get("required_case_count"),
            "passed_case_count": runtime_validation.get("passed_case_count"),
            "certification_status": "completed",
            "created_at_utc": _now(),
            "warnings": [],
        }
        updated_queue = dict(queue_item)
        updated_queue["status"] = "resolved"
        updated_queue["resolution"] = "rule_runtime_certified"
        updated_queue["runtime_validation_id"] = runtime_validation.get("runtime_validation_id")
        updated_queue["certification_receipt_id"] = receipt_id
        updated_queue["resolved_at_utc"] = _now()
        queue_path = _queue_item_path(base, revalidation_id)
        receipt_path = _certification_receipt_path(base, receipt_id)
        write_targets = {
            receipt_path: _read_json(receipt_path),
            base / "indexes" / CERTIFICATION_INDEX: _read_json(base / "indexes" / CERTIFICATION_INDEX),
            queue_path: _read_json(queue_path),
            base / "indexes" / QUEUE_INDEX: _read_json(base / "indexes" / QUEUE_INDEX),
        }
        try:
            _atomic_write_json(receipt_path, receipt_payload)
            _update_certification_receipt_index(base)
            _atomic_write_json(queue_path, updated_queue)
            _update_queue_index(base)
        except Exception:
            rollback_verified = _rollback_paths(write_targets)
            return {"status": "failed_rolled_back", "classification": "certification_write_failure", "rollback_verified": rollback_verified, "warnings": []}
        return {
            "status": "certified",
            "revalidation_id": revalidation_id,
            "rule_id": queue_item.get("rule_id"),
            "certification_receipt_id": receipt_id,
            "runtime_validation_id": runtime_validation.get("runtime_validation_id"),
            "revalidation_status": "resolved",
            "resolution": "rule_runtime_certified",
            "warnings": [],
        }
    if review.get("decision") == "reject_and_rollback":
        if confirmation != "ROLLBACK":
            return _blocked("rollback_confirmation_required", blockers=["rollback_confirmation_required"])
        activation_receipt_id = str(queue_item.get("activation_receipt_id") or "")
        if queue_item.get("status") == "resolved" and queue_item.get("resolution") == "activation_rolled_back":
            return {"status": "already_rolled_back", "rule_id": queue_item.get("rule_id"), "writes_performed": 0}
        rollback = rollback_proposal_rule_activation(activation_receipt_id, confirmation="ROLLBACK", root=base)
        if rollback.get("status") != "rollback_completed":
            return {
                "status": "rollback_failed",
                "classification": "critical_recovery_failure",
                "rollback_verified": rollback.get("rollback_verified"),
                "warnings": list(rollback.get("warnings", [])),
            }
        updated_queue = dict(queue_item)
        updated_queue["status"] = "resolved"
        updated_queue["resolution"] = "activation_rolled_back"
        updated_queue["rollback_verified"] = True
        updated_queue["resolved_at_utc"] = _now()
        updated_queue["rollback_revalidation_id"] = rollback.get("rollback_revalidation_id")
        queue_path = _queue_item_path(base, revalidation_id)
        before_queue = _read_json(queue_path)
        before_index = _read_json(base / "indexes" / QUEUE_INDEX)
        try:
            _atomic_write_json(queue_path, updated_queue)
            _update_queue_index(base)
        except Exception:
            _restore_json(queue_path, before_queue)
            _restore_json(base / "indexes" / QUEUE_INDEX, before_index)
            return {"status": "rollback_failed", "classification": "critical_recovery_failure", "rollback_verified": True, "warnings": []}
        return {
            "status": "rejected_rolled_back",
            "revalidation_id": revalidation_id,
            "rule_id": queue_item.get("rule_id"),
            "activation_receipt_id": activation_receipt_id,
            "rollback_verified": True,
            "revalidation_status": "resolved",
            "resolution": "activation_rolled_back",
            "warnings": [],
        }
    return _blocked("rule_revalidation_completion_blocked", blockers=["request_changes_does_not_complete_revalidation"])


def get_rule_activation_revalidation_health(document_id: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = _ensure_rule_activation_revalidation_dirs(root)
    queue_items = [
        item
        for item in list_source_revalidation_queue(limit=500, root=base).get("items", [])
        if isinstance(item, dict) and item.get("reason") == "proposal_rule_activation" and (document_id is None or item.get("document_id") == document_id)
    ]
    reviews = _load_revalidation_reviews(base)
    receipts = _load_certification_receipts(base)
    if not queue_items and not reviews and not receipts:
        return {"status": "empty", "pending_revalidation_count": 0, "certified_rule_count": 0, "rolled_back_rule_count": 0, "failed_runtime_validation_count": 0, "mutation_detected_count": 0, "missing_receipt_count": 0, "divergent_state_count": 0, "warnings": [], "recommended_action": "Load a pending Phase 9D rule revalidation."}
    pending = sum(1 for item in queue_items if item.get("status") == "pending_review")
    approved_waiting = sum(1 for item in reviews if item.get("review_status") == "approved")
    failed_runtime = sum(1 for item in _iter_runtime_validations(base) if item.get("status") in {"failed", "error", "blocked"})
    mutation_detected = sum(1 for item in _iter_runtime_validations(base) if item.get("persistent_state_mutated") is True)
    missing_receipt = sum(1 for item in queue_items if item.get("status") == "resolved" and item.get("resolution") == "rule_runtime_certified" and _load_certification_receipt_for_revalidation(base, str(item.get("queue_item_id") or "")) is None)
    warnings = ["one_rule_is_waiting_for_runtime_revalidation"] if pending else []
    status = "blocked" if failed_runtime or mutation_detected else "warning" if warnings or missing_receipt or approved_waiting else "healthy"
    return {
        "status": status,
        "pending_revalidation_count": pending,
        "certified_rule_count": sum(1 for item in receipts if item.get("certification_status") == "completed"),
        "rolled_back_rule_count": sum(1 for item in queue_items if item.get("resolution") == "activation_rolled_back"),
        "failed_runtime_validation_count": failed_runtime,
        "mutation_detected_count": mutation_detected,
        "missing_receipt_count": missing_receipt,
        "divergent_state_count": 0,
        "warnings": warnings,
        "recommended_action": "Run the focused runtime validation for one active rule." if pending else "Rule activation runtime revalidation health is good.",
    }


def format_rule_activation_revalidation_report(
    revalidation_id: str | None = None,
    revalidation_review_id: str | None = None,
    certification_receipt_id: str | None = None,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    base = _ensure_rule_activation_revalidation_dirs(root)
    review = _load_revalidation_review_by_id(base, revalidation_review_id) if revalidation_review_id else None
    receipt = _load_certification_receipt_by_id(base, certification_receipt_id) if certification_receipt_id else None
    target_revalidation_id = revalidation_id or str((review or {}).get("revalidation_id") or (receipt or {}).get("revalidation_id") or "")
    workspace = build_rule_activation_revalidation_workspace(target_revalidation_id, root=base) if target_revalidation_id else {"status": "not_found"}
    runtime_validation = _load_runtime_validation_for_revalidation(base, target_revalidation_id) if target_revalidation_id else None
    if workspace.get("status") == "not_found":
        return "Rule Activation Revalidation Report\n\nStatus: not_found"
    text = "\n".join(
        [
            "Rule Activation Revalidation Report",
            "",
            f"Document: {workspace.get('document_id') or 'unknown'}",
            f"Source Revision: {_workspace_source_revision(base, target_revalidation_id)}",
            f"Rule: {workspace.get('rule_id')}",
            f"Rule Status: {workspace.get('rule_status')}",
            "",
            "Activation Provenance:",
            f"- Activation Receipt: {workspace.get('activation_provenance_status')}",
            f"- Proposal Provenance: {workspace.get('activation_provenance_status')}",
            f"- Citation Evidence: {workspace.get('activation_provenance_status')}",
            f"- Rule Hash: {'current' if not workspace.get('blockers') else 'blocked'}",
            "",
            "Runtime Contract:",
            f"- Required Cases: {runtime_validation.get('required_case_count', 0) if isinstance(runtime_validation, dict) else 0}",
            f"- Passed: {runtime_validation.get('passed_case_count', 0) if isinstance(runtime_validation, dict) else 0}",
            f"- Failed: {runtime_validation.get('failed_case_count', 0) if isinstance(runtime_validation, dict) else 0}",
            f"- Persistent Mutation Detected: {'Yes' if isinstance(runtime_validation, dict) and runtime_validation.get('persistent_state_mutated') else 'No'}",
            "",
            "Review:",
            f"- Decision: {(review or {}).get('decision', 'not_decided')}",
            f"- Review Status: {(review or {}).get('review_status', workspace.get('review_status'))}",
            "",
            "Certification:",
            f"- Receipt: {(receipt or {}).get('certification_receipt_id', 'none')}",
            f"- Status: {(receipt or {}).get('certification_status', 'not_completed')}",
            "",
            "Revalidation:",
            f"- Status: {workspace.get('revalidation_status')}",
            f"- Resolution: {(_load_revalidation_item(base, target_revalidation_id) or {}).get('resolution', 'pending')}",
            "",
            "Important:",
            "The rule was evaluated through the canonical read-only evaluator." if _load_canonical_rule_evaluator() is not None else "No safe single-rule canonical evaluator was discovered in this repository.",
            "No scoring, objective-pack, Fast Lane, or historical-replay workflow was executed.",
        ]
    )
    if public_safe:
        for needle in ("C:\\", "/Users/", "Traceback", "reviewer_note", "claim", "quote_excerpt", "selected_text", "token=", "secret"):
            text = text.replace(needle, "[redacted]")
    return text


def _ensure_rule_activation_revalidation_dirs(root: Path | str) -> Path:
    base = ensure_source_knowledge_dirs(root)
    ensure_source_impact_dirs(base)
    for folder in (REVALIDATION_REVIEW_DIR, CERTIFICATION_RECEIPT_DIR):
        (base / folder).mkdir(parents=True, exist_ok=True)
    for index_name in (REVIEW_INDEX, CERTIFICATION_INDEX):
        path = base / "indexes" / index_name
        if not path.exists():
            _atomic_write_json(path, {"entries": [], "updated_at_utc": _now()})
    return base


def _load_canonical_rule_evaluator() -> Callable[[Mapping[str, Any] | None, Mapping[str, Any]], Any] | None:
    return None


def _build_operator_cases(field: str, operator: str, value: Any) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    if operator == "equals":
        return (
            {"case_id": "positive_match", "case_type": "positive", "input": {field: value}, "expected_match": True, "required": True},
            {"case_id": "negative_nonmatch", "case_type": "negative", "input": {field: _different_value(value)}, "expected_match": False, "required": True},
            None,
        )
    if operator == "not_equals":
        return (
            {"case_id": "positive_match", "case_type": "positive", "input": {field: _different_value(value)}, "expected_match": True, "required": True},
            {"case_id": "negative_nonmatch", "case_type": "negative", "input": {field: value}, "expected_match": False, "required": True},
            None,
        )
    if operator == "contains" and isinstance(value, str):
        return (
            {"case_id": "positive_match", "case_type": "positive", "input": {field: f"prefix {value} suffix"}, "expected_match": True, "required": True},
            {"case_id": "negative_nonmatch", "case_type": "negative", "input": {field: "different_controlled_value"}, "expected_match": False, "required": True},
            None,
        )
    if operator == "in" and isinstance(value, list) and value:
        return (
            {"case_id": "positive_match", "case_type": "positive", "input": {field: value[0]}, "expected_match": True, "required": True},
            {"case_id": "negative_nonmatch", "case_type": "negative", "input": {field: _different_value(value[0])}, "expected_match": False, "required": True},
            None,
        )
    if operator in {"greater_than", "greater_than_or_equal", "less_than", "less_than_or_equal"} and isinstance(value, (int, float)) and not isinstance(value, bool):
        plus = value + 1
        minus = value - 1
        if operator == "greater_than":
            return (
                {"case_id": "positive_match", "case_type": "positive", "input": {field: plus}, "expected_match": True, "required": True},
                {"case_id": "negative_nonmatch", "case_type": "negative", "input": {field: value}, "expected_match": False, "required": True},
                {"case_id": "boundary_match", "case_type": "boundary", "input": {field: minus}, "expected_match": False, "required": False},
            )
        if operator == "greater_than_or_equal":
            return (
                {"case_id": "positive_match", "case_type": "positive", "input": {field: value}, "expected_match": True, "required": True},
                {"case_id": "negative_nonmatch", "case_type": "negative", "input": {field: minus}, "expected_match": False, "required": True},
                {"case_id": "boundary_match", "case_type": "boundary", "input": {field: plus}, "expected_match": True, "required": False},
            )
        if operator == "less_than":
            return (
                {"case_id": "positive_match", "case_type": "positive", "input": {field: minus}, "expected_match": True, "required": True},
                {"case_id": "negative_nonmatch", "case_type": "negative", "input": {field: value}, "expected_match": False, "required": True},
                {"case_id": "boundary_match", "case_type": "boundary", "input": {field: plus}, "expected_match": False, "required": False},
            )
        return (
            {"case_id": "positive_match", "case_type": "positive", "input": {field: value}, "expected_match": True, "required": True},
            {"case_id": "negative_nonmatch", "case_type": "negative", "input": {field: plus}, "expected_match": False, "required": True},
            {"case_id": "boundary_match", "case_type": "boundary", "input": {field: minus}, "expected_match": True, "required": False},
        )
    return None, None, None


def _different_value(value: Any) -> Any:
    if isinstance(value, bool):
        return not value
    if isinstance(value, (int, float)):
        return value + 1
    if isinstance(value, str):
        return f"{value}_different"
    return "different_controlled_value"


def _normalize_evaluator_result(result: Any) -> bool:
    if isinstance(result, bool):
        return result
    if isinstance(result, Mapping):
        if isinstance(result.get("matched"), bool):
            return bool(result.get("matched"))
        if isinstance(result.get("match"), bool):
            return bool(result.get("match"))
        if str(result.get("status") or "") in {"matched", "not_matched"}:
            return str(result.get("status")) == "matched"
    raise ValueError("canonical_evaluator_result_unsupported")


def _revalidation_persistent_state_hash(root: Path, queue_item: Mapping[str, Any]) -> str:
    payload = {
        "rule": load_rule(str(queue_item.get("rule_id") or ""), root=root),
        "queue_item": _load_revalidation_item(root, str(queue_item.get("queue_item_id") or "")),
        "active_rule_index_hash": active_rule_index_hash(root=root),
    }
    return _hash_payload(payload)


def _save_runtime_validation(root: Path, payload: Mapping[str, Any]) -> None:
    _atomic_write_json(_runtime_validation_path(root, str(payload.get("runtime_validation_id") or "")), dict(payload))


def _iter_runtime_validations(root: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted((root / REVALIDATION_REVIEW_DIR).glob("rule_runtime_validation_*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _load_runtime_validation_for_revalidation(root: Path, revalidation_id: str) -> dict[str, Any] | None:
    for item in _iter_runtime_validations(root):
        if str(item.get("revalidation_id") or "") == revalidation_id:
            return item
    return None


def _runtime_validation_id(revalidation_id: str) -> str:
    return f"rule_runtime_validation_{_hash_payload({'revalidation_id': revalidation_id})[7:23]}"


def _revalidation_review_id(revalidation_id: str) -> str:
    return f"rule_revalidation_review_{_hash_payload({'revalidation_id': revalidation_id})[7:23]}"


def _certification_receipt_id(revalidation_id: str) -> str:
    return f"rule_certification_receipt_{_hash_payload({'revalidation_id': revalidation_id})[7:23]}"


def _review_path(root: Path, review_id: str) -> Path:
    return root / REVALIDATION_REVIEW_DIR / f"{review_id}.json"


def _runtime_validation_path(root: Path, runtime_validation_id: str) -> Path:
    return root / REVALIDATION_REVIEW_DIR / f"{runtime_validation_id}.json"


def _certification_receipt_path(root: Path, receipt_id: str) -> Path:
    return root / CERTIFICATION_RECEIPT_DIR / f"{receipt_id}.json"


def _load_revalidation_item(root: Path, revalidation_id: str) -> dict[str, Any] | None:
    payload = _read_json(_queue_item_path(root, revalidation_id))
    return payload if isinstance(payload, dict) else None


def _load_revalidation_reviews(root: Path) -> list[dict[str, Any]]:
    items = []
    for path in sorted((root / REVALIDATION_REVIEW_DIR).glob("rule_revalidation_review_*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _load_revalidation_review_by_id(root: Path, review_id: str) -> dict[str, Any] | None:
    payload = _read_json(_review_path(root, review_id))
    return payload if isinstance(payload, dict) else None


def _load_revalidation_review_for_queue(root: Path, revalidation_id: str) -> dict[str, Any] | None:
    for item in _load_revalidation_reviews(root):
        if str(item.get("revalidation_id") or "") == revalidation_id:
            return item
    return None


def _load_certification_receipts(root: Path) -> list[dict[str, Any]]:
    items = []
    for path in sorted((root / CERTIFICATION_RECEIPT_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _load_certification_receipt_by_id(root: Path, receipt_id: str) -> dict[str, Any] | None:
    payload = _read_json(_certification_receipt_path(root, receipt_id))
    return payload if isinstance(payload, dict) else None


def _load_certification_receipt_for_revalidation(root: Path, revalidation_id: str) -> dict[str, Any] | None:
    for item in _load_certification_receipts(root):
        if str(item.get("revalidation_id") or "") == revalidation_id:
            return item
    return None


def _update_revalidation_review_index(root: Path) -> None:
    entries = []
    for item in _load_revalidation_reviews(root):
        entries.append(
            {
                "revalidation_review_id": item.get("revalidation_review_id"),
                "revalidation_id": item.get("revalidation_id"),
                "rule_id": item.get("rule_id"),
                "decision": item.get("decision"),
                "review_status": item.get("review_status"),
                "updated_at_utc": item.get("updated_at_utc"),
            }
        )
    _atomic_write_json(root / "indexes" / REVIEW_INDEX, {"entries": entries, "updated_at_utc": _now()})


def _update_certification_receipt_index(root: Path) -> None:
    entries = []
    for item in _load_certification_receipts(root):
        entries.append(
            {
                "certification_receipt_id": item.get("certification_receipt_id"),
                "revalidation_id": item.get("revalidation_id"),
                "rule_id": item.get("rule_id"),
                "document_id": item.get("document_id"),
                "created_at_utc": item.get("created_at_utc"),
            }
        )
    _atomic_write_json(root / "indexes" / CERTIFICATION_INDEX, {"entries": entries, "updated_at_utc": _now()})


def _same_review(existing: Mapping[str, Any], decision: str, note: str | None, runtime_validation: Mapping[str, Any]) -> bool:
    return existing.get("decision") == decision and existing.get("reviewer_note") == note and existing.get("runtime_validation_fingerprint") == _hash_payload(runtime_validation)


def _same_payload(existing: Mapping[str, Any], payload: Mapping[str, Any]) -> bool:
    return all(existing.get(field) == payload.get(field) for field in ("decision", "review_status", "reviewer_note", "runtime_validation_fingerprint"))


def _rollback_paths(targets: Mapping[Path, Any]) -> bool:
    for path, payload in targets.items():
        _restore_json(path, payload)
    return all(_read_json(path) == payload for path, payload in targets.items())


def _workspace_source_revision(root: Path, revalidation_id: str) -> Any:
    return (_load_revalidation_item(root, revalidation_id) or {}).get("source_revision", "unknown")
