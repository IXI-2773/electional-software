"""Controlled review surface for promoted proposal to rule activation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .citation_draft_review import _atomic_write_json, _hash_payload, _now, _read_json, _restore_json
from .document_manifest import calculate_document_revision_state, validate_source_locator
from .pdf_viewport import _blocked
from .proposal_promotion import (
    _load_promotion_review_by_id,
    _load_proposal,
    _load_receipt_for_proposal,
    _matching_revalidation,
    _proposal_locator,
    validate_proposal_promotion_provenance,
)
from .canonical_rule_runtime import (
    _hash_payload as _canonical_hash_payload,
    _index_path as _canonical_rule_index_path,
    _load_index as _load_canonical_rule_index,
    _rule_path as _canonical_rule_path,
    create_canonical_rule,
    deactivate_canonical_rule,
    get_canonical_rule_runtime_capability,
    load_canonical_rule,
    list_canonical_rules,
    validate_canonical_rule_record,
)
from .source_documents import SOURCE_DOCUMENT_ROOT
from .source_impact_analysis import QUEUE_INDEX, _queue_item_path, _update_queue_index, ensure_source_impact_dirs, list_source_revalidation_queue
from .source_knowledge import ensure_source_knowledge_dirs

RULE_ACTIVATION_REVIEW_DIR = "proposal_rule_activation_reviews"
RULE_ACTIVATION_RECEIPT_DIR = "proposal_rule_activation_receipts"
RULE_ACTIVATION_BACKUP_DIR = "proposal_rule_activation_backups"
RULE_ACTIVATION_REVIEW_INDEX = "proposal_rule_activation_review_index.json"
RULE_ACTIVATION_RECEIPT_INDEX = "proposal_rule_activation_receipt_index.json"
RULE_ACTIVATION_REVIEW_SCHEMA_VERSION = "proposal_rule_activation_review_v1"
RULE_ACTIVATION_RECEIPT_SCHEMA_VERSION = "proposal_rule_activation_receipt_v1"
ALLOWED_DECISIONS = {"approve", "reject", "request_changes"}
HEALTH_STATUSES = {"healthy", "warning", "blocked", "stale", "corrupt", "empty", "unknown"}


def build_proposal_rule_activation_workspace(proposal_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = _ensure_rule_activation_dirs(root)
    proposal = _load_proposal(base, proposal_id)
    if proposal is None:
        return {"proposal_id": proposal_id, "status": "not_found", "warnings": ["proposal_not_found"]}
    promotion = validate_proposal_promotion_provenance(proposal_id, root=base)
    mapping = validate_promoted_proposal_rule_mapping(proposal_id, root=base)
    conflicts = analyze_proposal_rule_candidate_conflicts(proposal_id, root=base)
    review = _load_rule_activation_review_for_proposal(base, proposal_id)
    receipt = _load_rule_activation_receipt_for_proposal(base, proposal_id)
    promotion_receipt = _load_receipt_for_proposal(base, proposal_id)
    return {
        "proposal_id": proposal_id,
        "proposal_status": proposal.get("status"),
        "document_id": proposal.get("document_id"),
        "source_revision": proposal.get("source_revision"),
        "promotion_receipt_id": (promotion_receipt or {}).get("promotion_receipt_id"),
        "promotion_provenance_status": "valid" if promotion.get("valid") else "invalid",
        "rule_mapping_status": "valid" if mapping.get("mapping_valid") else "invalid",
        "rule_candidate_status": "ready" if mapping.get("mapping_valid") and not conflicts.get("blockers") else "storage_unavailable" if "rule_activation_storage_unavailable" in conflicts.get("blockers", []) else "blocked",
        "rule_activation_review_status": (review or {}).get("review_status", "pending"),
        "duplicate_status": conflicts.get("duplicate_status"),
        "conflict_status": conflicts.get("conflict_status"),
        "active_rule_id": (receipt or {}).get("rule_id"),
        "activation_receipt_id": (receipt or {}).get("activation_receipt_id"),
        "warnings": list(dict.fromkeys([*promotion.get("warnings", []), *mapping.get("warnings", []), *conflicts.get("warnings", [])])),
        "blockers": list(dict.fromkeys([*promotion.get("blockers", []), *mapping.get("blockers", []), *conflicts.get("blockers", [])])),
        "recommended_action": "Canonical mutable rule storage is unavailable in this repository." if "rule_activation_storage_unavailable" in conflicts.get("blockers", []) else "Review the structured rule candidate.",
    }


def validate_promoted_proposal_rule_mapping(proposal_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = _ensure_rule_activation_dirs(root)
    proposal = _load_proposal(base, proposal_id)
    if proposal is None:
        return {"proposal_id": proposal_id, "mapping_valid": False, "candidate": None, "warnings": [], "blockers": ["proposal_not_found"]}
    if str(proposal.get("status") or "") != "promoted":
        return {"proposal_id": proposal_id, "mapping_valid": False, "candidate": None, "warnings": [], "blockers": ["proposal_not_promoted"]}
    mapping = proposal.get("rule_mapping")
    if not isinstance(mapping, Mapping):
        return {"proposal_id": proposal_id, "mapping_valid": False, "candidate": None, "warnings": [], "blockers": ["proposal_not_rule_mappable"]}
    required = ("rule_type", "target", "scope", "condition", "operator", "value")
    missing = [field for field in required if mapping.get(field) is None or mapping.get(field) == ""]
    if missing:
        return {"proposal_id": proposal_id, "mapping_valid": False, "candidate": None, "warnings": [], "blockers": ["proposal_not_rule_mappable", *[f"missing_{field}" for field in missing]]}
    condition = mapping.get("condition")
    if not isinstance(condition, Mapping) or condition.get("field") in {None, ""}:
        return {"proposal_id": proposal_id, "mapping_valid": False, "candidate": None, "warnings": [], "blockers": ["proposal_not_rule_mappable", "missing_condition_field"]}
    candidate = {
        "rule_type": str(mapping.get("rule_type")),
        "target": str(mapping.get("target")),
        "scope": str(mapping.get("scope")),
        "condition": {
            "field": str(condition.get("field")),
            "operator": str(condition.get("operator") or mapping.get("operator")),
            "value": condition.get("value", mapping.get("value")),
        },
        "operator": str(mapping.get("operator")),
        "value": mapping.get("value"),
        "priority": int(mapping.get("priority", 50)),
        "enabled": bool(mapping.get("enabled", True)),
    }
    blockers = _validate_candidate_schema(candidate)
    return {
        "proposal_id": proposal_id,
        "mapping_valid": not blockers,
        "candidate": candidate if not blockers else None,
        "mapping_basis": ["explicit_proposal_target", "explicit_proposal_operator", "explicit_proposal_value"],
        "warnings": [],
        "blockers": blockers,
    }


def analyze_proposal_rule_candidate_conflicts(proposal_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = _ensure_rule_activation_dirs(root)
    mapping = validate_promoted_proposal_rule_mapping(proposal_id, root=base)
    if not mapping.get("mapping_valid"):
        return {
            "proposal_id": proposal_id,
            "duplicate_status": "none",
            "duplicate_count": 0,
            "conflict_status": "none",
            "conflict_count": 0,
            "requires_conflict_acknowledgement": False,
            "activation_allowed": False,
            "matches": [],
            "warnings": [],
            "blockers": list(mapping.get("blockers", [])),
        }
    store = _canonical_rule_store_state(base)
    if not store.get("available"):
        return {
            "proposal_id": proposal_id,
            "duplicate_status": "none",
            "duplicate_count": 0,
            "conflict_status": "none",
            "conflict_count": 0,
            "requires_conflict_acknowledgement": False,
            "activation_allowed": False,
            "matches": [],
            "warnings": [],
            "blockers": ["rule_activation_storage_unavailable"],
        }
    candidate = mapping["candidate"]
    matches: list[dict[str, object]] = []
    duplicate_status = "none"
    conflict_status = "none"
    blockers: list[str] = []
    warnings: list[str] = []
    for rule in store.get("active_rules", []):
        if not isinstance(rule, Mapping):
            continue
        if _rule_fingerprint(rule) == _rule_fingerprint(candidate):
            duplicate_status = "exact_duplicate"
            blockers.append("exact_active_rule_duplicate_exists")
            matches.append({"rule_id": rule.get("rule_id"), "relationship": "exact_duplicate", "matching_fields": ["target", "scope", "condition", "operator", "value"]})
        elif str(rule.get("target") or "") == str(candidate.get("target") or "") and str(rule.get("scope") or "") == str(candidate.get("scope") or ""):
            if str(rule.get("status") or "") != "active":
                duplicate_status = "inactive_equivalent"
                warnings.append("inactive_equivalent_requires_acknowledgement")
                matches.append({"rule_id": rule.get("rule_id"), "relationship": "inactive_equivalent", "matching_fields": ["target", "scope"]})
            elif rule.get("value") != candidate.get("value"):
                conflict_status = "critical_conflict"
                blockers.append("critical_rule_conflict_exists")
                matches.append({"rule_id": rule.get("rule_id"), "relationship": "critical_conflict", "matching_fields": ["target", "scope"]})
            else:
                conflict_status = "warning"
                warnings.append("one_noncritical_rule_conflict_requires_acknowledgement")
                matches.append({"rule_id": rule.get("rule_id"), "relationship": "conflict_warning", "matching_fields": ["target", "scope"]})
    return {
        "proposal_id": proposal_id,
        "duplicate_status": duplicate_status,
        "duplicate_count": sum(1 for item in matches if item["relationship"] in {"exact_duplicate", "inactive_equivalent"}),
        "conflict_status": conflict_status,
        "conflict_count": sum(1 for item in matches if "conflict" in item["relationship"]),
        "requires_conflict_acknowledgement": duplicate_status == "inactive_equivalent" or conflict_status == "warning",
        "activation_allowed": not blockers,
        "matches": matches,
        "warnings": list(dict.fromkeys(warnings)),
        "blockers": list(dict.fromkeys(blockers)),
    }


def save_proposal_rule_activation_decision(
    proposal_id: str,
    decision: str,
    reviewer_note: str | None = None,
    acknowledge_inactive_equivalent: bool = False,
    acknowledge_conflict: bool = False,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    if decision not in ALLOWED_DECISIONS:
        raise ValueError(f"Unsupported rule activation decision: {decision}")
    base = _ensure_rule_activation_dirs(root)
    proposal = _load_proposal(base, proposal_id)
    if proposal is None:
        raise FileNotFoundError(proposal_id)
    promotion = validate_proposal_promotion_provenance(proposal_id, root=base)
    mapping = validate_promoted_proposal_rule_mapping(proposal_id, root=base)
    conflicts = analyze_proposal_rule_candidate_conflicts(proposal_id, root=base)
    existing = _load_rule_activation_review_for_proposal(base, proposal_id)
    note = str(reviewer_note or "").strip() or None
    blockers: list[str] = []
    if decision == "approve":
        blockers.extend(promotion.get("blockers", []))
        blockers.extend(mapping.get("blockers", []))
        blockers.extend(conflicts.get("blockers", []))
        if conflicts.get("duplicate_status") == "inactive_equivalent" and not acknowledge_inactive_equivalent:
            blockers.append("inactive_equivalent_acknowledgement_required")
        if conflicts.get("conflict_status") == "warning" and not acknowledge_conflict:
            blockers.append("conflict_acknowledgement_required")
    else:
        if not note:
            blockers.append("reviewer_note_required")
    if blockers:
        return _blocked("rule_activation_review_blocked", blockers=list(dict.fromkeys(blockers)))
    candidate = mapping.get("candidate")
    payload = {
        "schema_version": RULE_ACTIVATION_REVIEW_SCHEMA_VERSION,
        "rule_activation_review_id": (existing or {}).get("rule_activation_review_id") or _rule_activation_review_id(proposal_id),
        "proposal_id": proposal_id,
        "document_id": proposal.get("document_id"),
        "source_revision": proposal.get("source_revision"),
        "decision": decision,
        "review_status": "approved" if decision == "approve" else "rejected" if decision == "reject" else "changes_requested",
        "acknowledge_inactive_equivalent": bool(acknowledge_inactive_equivalent),
        "acknowledge_conflict": bool(acknowledge_conflict),
        "candidate_snapshot": candidate,
        "candidate_fingerprint": _rule_fingerprint(candidate) if candidate else None,
        "promotion_provenance_snapshot": promotion,
        "conflict_snapshot": conflicts,
        "review_revision": int((existing or {}).get("review_revision") or 0) + (0 if existing and _same_review(existing, decision, note, acknowledge_inactive_equivalent, acknowledge_conflict) else 1),
        "reviewer_note": note,
        "created_at_utc": (existing or {}).get("created_at_utc") or _now(),
        "updated_at_utc": _now(),
        "warnings": conflicts.get("warnings", []),
    }
    if existing and _same_payload(existing, payload):
        return {"status": "saved", "review": existing, "writes_performed": 0}
    review_path = _rule_activation_review_path(base, str(payload["rule_activation_review_id"]))
    before_review = _read_json(review_path)
    before_index = _read_json(base / "indexes" / RULE_ACTIVATION_REVIEW_INDEX)
    try:
        _atomic_write_json(review_path, payload)
        _update_rule_activation_review_index(base)
    except Exception:
        _restore_json(review_path, before_review)
        _restore_json(base / "indexes" / RULE_ACTIVATION_REVIEW_INDEX, before_index)
        return {"status": "failed_rolled_back", "classification": "rule_activation_review_write_failure", "warnings": []}
    return {"status": "saved", "review": payload, "writes_performed": 1}


def activate_rule_from_promoted_proposal(rule_activation_review_id: str, confirmation: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    if confirmation != "ACTIVATE":
        return _blocked("activate_confirmation_required", blockers=["activate_confirmation_required"])
    base = _ensure_rule_activation_dirs(root)
    review = _load_rule_activation_review_by_id(base, rule_activation_review_id)
    if review is None:
        raise FileNotFoundError(rule_activation_review_id)
    proposal_id = str(review.get("proposal_id") or "")
    proposal = _load_proposal(base, proposal_id)
    promotion_receipt = _load_receipt_for_proposal(base, proposal_id)
    existing_receipt = _load_rule_activation_receipt_for_proposal(base, proposal_id)
    provenance = validate_proposal_promotion_provenance(proposal_id, root=base)
    mapping = validate_promoted_proposal_rule_mapping(proposal_id, root=base)
    if proposal is None:
        return _blocked("rule_activation_invalid", blockers=["proposal_not_found"])
    if promotion_receipt is None or promotion_receipt.get("promotion_status") != "completed":
        return _blocked("rule_activation_invalid", blockers=["promotion_receipt_missing"])
    if review.get("decision") != "approve":
        return _blocked("rule_activation_invalid", blockers=["rule_activation_review_not_approved"])
    if provenance.get("blockers"):
        return _blocked("rule_activation_invalid", blockers=list(provenance.get("blockers", [])))
    if mapping.get("blockers"):
        return _blocked("rule_activation_invalid", blockers=list(mapping.get("blockers", [])))
    candidate = mapping.get("candidate")
    candidate_fingerprint = _rule_fingerprint(candidate)
    if candidate_fingerprint != review.get("candidate_fingerprint"):
        return _blocked("rule_activation_invalid", blockers=["approved_candidate_fingerprint_mismatch"])
    capability = get_canonical_rule_runtime_capability(root=base)
    if not capability.get("available"):
        return _blocked("rule_activation_invalid", blockers=["rule_activation_storage_unavailable"])
    ensure_source_impact_dirs(base)
    if existing_receipt is not None:
        loaded_rule = load_canonical_rule(str(existing_receipt.get("rule_id") or ""), root=base)
        rule = loaded_rule.get("rule") if loaded_rule.get("status") == "loaded" else None
        revalidation = _load_rule_activation_revalidation(base, str(existing_receipt.get("activation_receipt_id") or ""), reason="proposal_rule_activation")
        if (
            isinstance(rule, dict)
            and rule.get("activation_receipt_id") == existing_receipt.get("activation_receipt_id")
            and str(rule.get("status") or "") == "active"
            and isinstance(revalidation, dict)
        ):
            return {
                "status": "already_activated",
                "proposal_id": proposal_id,
                "rule_id": existing_receipt.get("rule_id"),
                "activation_receipt_id": existing_receipt.get("activation_receipt_id"),
                "writes_performed": 0,
            }
        return _blocked("rule_activation_state_diverged", blockers=["rule_activation_state_diverged"])
    conflicts = analyze_proposal_rule_candidate_conflicts(proposal_id, root=base)
    if conflicts.get("blockers"):
        return _blocked("rule_activation_invalid", blockers=list(conflicts.get("blockers", [])))
    if conflicts.get("duplicate_status") == "inactive_equivalent" and not review.get("acknowledge_inactive_equivalent"):
        return _blocked("rule_activation_invalid", blockers=["inactive_equivalent_acknowledgement_required"])
    if conflicts.get("conflict_status") == "warning" and not review.get("acknowledge_conflict"):
        return _blocked("rule_activation_invalid", blockers=["conflict_acknowledgement_required"])
    receipt_id = _rule_activation_receipt_id(proposal_id)
    rule_id = _rule_id_for_candidate(proposal_id, candidate_fingerprint)
    rule_payload = {
        "schema_version": "canonical_mutable_rule_v1",
        "rule_id": rule_id,
        "rule_type": candidate.get("rule_type"),
        "target": candidate.get("target"),
        "scope": candidate.get("scope"),
        "condition": dict(candidate.get("condition") or {}),
        "operator": candidate.get("operator"),
        "value": candidate.get("value"),
        "priority": candidate.get("priority"),
        "enabled": bool(candidate.get("enabled")),
        "status": "active",
        "document_id": proposal.get("document_id"),
        "source_proposal_id": proposal_id,
        "source_promotion_receipt_id": promotion_receipt.get("promotion_receipt_id"),
        "source_rule_activation_review_id": rule_activation_review_id,
        "source_citation_ids": list(proposal.get("accepted_citation_ids", []) or []),
        "source_revision": proposal.get("source_revision"),
        "activation_receipt_id": receipt_id,
        "created_from": "promoted_proposal",
        "created_at_utc": _now(),
        "updated_at_utc": _now(),
    }
    validation = validate_canonical_rule_record(rule_payload, require_active=True)
    if not validation.get("valid"):
        return _blocked("rule_activation_invalid", blockers=list(validation.get("blockers", [])))
    before_rule_index_hash = _canonical_hash_payload(_load_canonical_rule_index(base))
    revalidation_id = _rule_activation_revalidation_id(receipt_id, "activation")
    receipt_payload = {
        "schema_version": RULE_ACTIVATION_RECEIPT_SCHEMA_VERSION,
        "activation_receipt_id": receipt_id,
        "proposal_id": proposal_id,
        "promotion_receipt_id": promotion_receipt.get("promotion_receipt_id"),
        "rule_activation_review_id": rule_activation_review_id,
        "rule_id": rule_id,
        "document_id": proposal.get("document_id"),
        "source_revision": proposal.get("source_revision"),
        "citation_ids": list(proposal.get("accepted_citation_ids", []) or []),
        "candidate_fingerprint": candidate_fingerprint,
        "before_rule_index_hash": before_rule_index_hash,
        "after_rule_index_hash": None,
        "created_rule_hash": None,
        "activation_status": "completed",
        "rollback_available": True,
        "created_at_utc": _now(),
        "warnings": [],
    }
    revalidation_payload = {
        "queue_item_id": revalidation_id,
        "document_id": proposal.get("document_id"),
        "change_type": "manual_review",
        "impact_severity": "medium",
        "status": "pending_review",
        "reason": "proposal_rule_activation",
        "proposal_id": proposal_id,
        "promotion_receipt_id": promotion_receipt.get("promotion_receipt_id"),
        "rule_activation_review_id": rule_activation_review_id,
        "activation_receipt_id": receipt_id,
        "rule_id": rule_id,
        "source_revision": proposal.get("source_revision"),
        "citation_ids": list(proposal.get("accepted_citation_ids", []) or []),
        "created_at_utc": _now(),
        "warnings": [],
        "dedupe_key": "sha256:" + _hash_payload({"activation_receipt_id": receipt_id, "reason": "proposal_rule_activation"}),
    }
    updated_review = dict(review)
    updated_review["review_status"] = "completed"
    updated_review["activation_receipt_id"] = receipt_id
    updated_review["active_rule_id"] = rule_id
    updated_review["updated_at_utc"] = _now()
    receipt_path = _rule_activation_receipt_path(base, receipt_id)
    review_path = _rule_activation_review_path(base, rule_activation_review_id)
    revalidation_path = _queue_item_path(base, revalidation_id)
    write_targets = {
        _canonical_rule_path(base, rule_id): _read_json(_canonical_rule_path(base, rule_id)),
        _canonical_rule_index_path(base): _read_json(_canonical_rule_index_path(base)),
        receipt_path: _read_json(receipt_path),
        base / "indexes" / RULE_ACTIVATION_RECEIPT_INDEX: _read_json(base / "indexes" / RULE_ACTIVATION_RECEIPT_INDEX),
        review_path: _read_json(review_path),
        base / "indexes" / RULE_ACTIVATION_REVIEW_INDEX: _read_json(base / "indexes" / RULE_ACTIVATION_REVIEW_INDEX),
        revalidation_path: _read_json(revalidation_path),
        base / "indexes" / QUEUE_INDEX: _read_json(base / "indexes" / QUEUE_INDEX),
    }
    try:
        created_rule = create_canonical_rule(rule_payload, confirmation="CREATE_RULE", root=base)
        if created_rule.get("status") not in {"created", "already_created"}:
            raise RuntimeError("canonical_rule_creation_failed")
        saved_rule_result = load_canonical_rule(rule_id, require_active=True, root=base)
        if saved_rule_result.get("status") != "loaded":
            raise RuntimeError("canonical_rule_load_failed")
        saved_rule = dict(saved_rule_result["rule"])
        receipt_payload["created_rule_hash"] = _hash_payload(saved_rule)
        receipt_payload["after_rule_index_hash"] = _canonical_hash_payload(_load_canonical_rule_index(base))
        _atomic_write_json(receipt_path, receipt_payload)
        _update_rule_activation_receipt_index(base)
        _atomic_write_json(review_path, updated_review)
        _update_rule_activation_review_index(base)
        _atomic_write_json(revalidation_path, revalidation_payload)
        _update_queue_index(base)
        if not _post_activation_validation(base, proposal_id, rule_id, receipt_id, candidate_fingerprint):
            raise RuntimeError("post_activation_validation_failed")
        return {
            "status": "activated",
            "proposal_id": proposal_id,
            "rule_activation_review_id": rule_activation_review_id,
            "rule_id": saved_rule.get("rule_id"),
            "rule_status": saved_rule.get("status"),
            "activation_receipt_id": receipt_id,
            "revalidation_id": revalidation_id,
            "revalidation_status": "pending_review",
            "warnings": [],
        }
    except Exception:
        rollback_verified = _rollback_paths(write_targets)
        return {
            "status": "rollback_failed" if not rollback_verified else "failed_rolled_back",
            "classification": "critical_recovery_failure" if not rollback_verified else "revalidation_creation_failure",
            "records_restored": len(write_targets),
            "new_records_removed": len(write_targets),
            "rollback_verified": rollback_verified,
            "warnings": [],
        }


def rollback_proposal_rule_activation(activation_receipt_id: str, confirmation: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    if confirmation != "ROLLBACK":
        return _blocked("rollback_confirmation_required", blockers=["rollback_confirmation_required"])
    base = _ensure_rule_activation_dirs(root)
    receipt = _load_rule_activation_receipt_by_id(base, activation_receipt_id)
    if receipt is None:
        return _blocked("activation_receipt_missing", blockers=["activation_receipt_missing"])
    rule_id = str(receipt.get("rule_id") or "")
    loaded_rule = load_canonical_rule(rule_id, root=base)
    rule = loaded_rule.get("rule") if loaded_rule.get("status") == "loaded" else None
    if not isinstance(rule, dict):
        return _blocked("rule_activation_state_diverged", blockers=["rule_activation_state_diverged"])
    if receipt.get("created_rule_hash") != _hash_payload(rule):
        return _blocked("rule_activation_state_diverged", blockers=["rule_activation_state_diverged"])
    if receipt.get("rollback_performed") is True and str(rule.get("status") or "") != "active":
        return {
            "status": "rollback_completed",
            "activation_receipt_id": activation_receipt_id,
            "rule_id": rule_id,
            "rule_removed_from_active_index": True,
            "rollback_verified": True,
            "rollback_revalidation_id": receipt.get("rollback_revalidation_id"),
            "warnings": [],
        }
    rollback_revalidation_id = _rule_activation_revalidation_id(activation_receipt_id, "rollback")
    rollback_revalidation = {
        "queue_item_id": rollback_revalidation_id,
        "document_id": receipt.get("document_id"),
        "change_type": "manual_review",
        "impact_severity": "medium",
        "status": "pending_review",
        "reason": "proposal_rule_activation_rollback",
        "activation_receipt_id": activation_receipt_id,
        "rule_id": rule_id,
        "source_revision": receipt.get("source_revision"),
        "citation_ids": list(receipt.get("citation_ids", []) or []),
        "created_at_utc": _now(),
        "warnings": [],
        "dedupe_key": "sha256:" + _hash_payload({"activation_receipt_id": activation_receipt_id, "reason": "proposal_rule_activation_rollback"}),
    }
    updated_receipt = dict(receipt)
    updated_receipt["rollback_performed"] = True
    updated_receipt["rollback_status"] = "completed"
    updated_receipt["rollback_revalidation_id"] = rollback_revalidation_id
    updated_receipt["rolled_back_at_utc"] = _now()
    receipt_path = _rule_activation_receipt_path(base, activation_receipt_id)
    rollback_path = _queue_item_path(base, rollback_revalidation_id)
    write_targets = {
        _canonical_rule_path(base, rule_id): _read_json(_canonical_rule_path(base, rule_id)),
        _canonical_rule_index_path(base): _read_json(_canonical_rule_index_path(base)),
        receipt_path: _read_json(receipt_path),
        base / "indexes" / RULE_ACTIVATION_RECEIPT_INDEX: _read_json(base / "indexes" / RULE_ACTIVATION_RECEIPT_INDEX),
        rollback_path: _read_json(rollback_path),
        base / "indexes" / QUEUE_INDEX: _read_json(base / "indexes" / QUEUE_INDEX),
    }
    try:
        deactivated = deactivate_canonical_rule(
            rule_id,
            reason=f"proposal_rule_activation:{activation_receipt_id}",
            confirmation="DEACTIVATE_RULE",
            root=base,
        )
        if deactivated.get("status") not in {"deactivated", "already_deactivated"}:
            raise RuntimeError("canonical_rule_deactivation_failed")
        _atomic_write_json(receipt_path, updated_receipt)
        _update_rule_activation_receipt_index(base)
        _atomic_write_json(rollback_path, rollback_revalidation)
        _update_queue_index(base)
    except Exception:
        rollback_verified = _rollback_paths(write_targets)
        return {
            "status": "rollback_failed",
            "classification": "critical_recovery_failure",
            "rollback_verified": rollback_verified,
            "warnings": [],
        }
    return {
        "status": "rollback_completed",
        "activation_receipt_id": activation_receipt_id,
        "rule_id": rule_id,
        "rule_removed_from_active_index": (load_canonical_rule(rule_id, root=base).get("rule") or {}).get("status") != "active",
        "rollback_verified": True,
        "rollback_revalidation_id": rollback_revalidation_id,
        "warnings": [],
    }


def get_proposal_rule_activation_health(document_id: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = _ensure_rule_activation_dirs(root)
    reviews = _load_rule_activation_reviews(base)
    receipts = _load_rule_activation_receipts(base)
    proposals = [item for item in _all_promoted_proposals(base) if document_id is None or item.get("document_id") == document_id]
    if not reviews and not receipts and not proposals:
        return {"status": "empty", "review_count": 0, "approved_waiting_count": 0, "activated_count": 0, "rolled_back_count": 0, "missing_receipt_count": 0, "missing_revalidation_count": 0, "divergent_state_count": 0, "warnings": [], "recommended_action": "Load a promoted proposal for rule activation review."}
    approved_waiting = sum(1 for item in reviews if item.get("review_status") == "approved")
    warnings = ["one_approved_rule_candidate_is_waiting_for_activation"] if approved_waiting else []
    missing_revalidation = sum(1 for item in receipts if _load_rule_activation_revalidation(base, str(item.get("activation_receipt_id") or ""), reason="proposal_rule_activation") is None)
    return {
        "status": "warning" if warnings or missing_revalidation else "healthy",
        "review_count": len(reviews),
        "approved_waiting_count": approved_waiting,
        "activated_count": len(receipts),
        "rolled_back_count": sum(1 for item in receipts if item.get("rollback_performed") is True),
        "missing_receipt_count": sum(1 for item in proposals if str(item.get("status") or "") == "promoted" and _load_rule_activation_receipt_for_proposal(base, str(item.get("proposal_id") or "")) is None),
        "missing_revalidation_count": missing_revalidation,
        "divergent_state_count": 0,
        "warnings": warnings,
        "recommended_action": "Review one approved candidate awaiting ACTIVATE confirmation." if approved_waiting else "Proposal rule activation health is good.",
    }


def format_proposal_rule_activation_report(
    proposal_id: str | None = None,
    rule_activation_review_id: str | None = None,
    activation_receipt_id: str | None = None,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    base = _ensure_rule_activation_dirs(root)
    review = _load_rule_activation_review_by_id(base, rule_activation_review_id) if rule_activation_review_id else None
    receipt = _load_rule_activation_receipt_by_id(base, activation_receipt_id) if activation_receipt_id else None
    target_proposal_id = proposal_id or str((review or {}).get("proposal_id") or (receipt or {}).get("proposal_id") or "")
    workspace = build_proposal_rule_activation_workspace(target_proposal_id, root=base) if target_proposal_id else {"status": "not_found"}
    if workspace.get("status") == "not_found":
        return "Proposal Rule Activation Report\n\nStatus: not_found"
    text = "\n".join(
        [
            "Proposal Rule Activation Report",
            "",
            f"Document: {workspace.get('document_id')}",
            f"Source Revision: {workspace.get('source_revision')}",
            f"Proposal: {workspace.get('proposal_id')}",
            f"Proposal Status: {workspace.get('proposal_status')}",
            "",
            "Rule Candidate:",
            f"- Mapping: {workspace.get('rule_mapping_status')}",
            f"- Schema: {'valid' if workspace.get('rule_mapping_status') == 'valid' else 'invalid'}",
            f"- Duplicate Status: {workspace.get('duplicate_status')}",
            f"- Conflict Status: {workspace.get('conflict_status')}",
            "",
            "Review:",
            f"- Decision: {(review or {}).get('decision', 'not_decided')}",
            f"- Review Status: {(review or {}).get('review_status', workspace.get('rule_activation_review_status'))}",
            "",
            "Activation:",
            f"- Rule ID: {workspace.get('active_rule_id') or 'none'}",
            f"- Rule Status: {'active' if workspace.get('active_rule_id') else 'inactive'}",
            f"- Receipt: {workspace.get('activation_receipt_id') or 'none'}",
            f"- Status: {'completed' if workspace.get('activation_receipt_id') else 'not_activated'}",
            "",
            "Revalidation:",
            f"- Status: {_report_revalidation_status(base, workspace.get('activation_receipt_id'))}",
            "",
            "Recovery:",
            f"- Rollback Available: {'Yes' if workspace.get('activation_receipt_id') else 'No'}",
            f"- Rollback Performed: {'Yes' if (receipt or {}).get('rollback_performed') else 'No'}",
            "",
            "Important:",
            "The rule was activated only after explicit review and ACTIVATE confirmation." if workspace.get("activation_receipt_id") else workspace.get("recommended_action"),
            "No scoring formula, objective pack, Fast Lane behavior, or existing active rule was modified.",
        ]
    )
    if public_safe:
        for needle in ("C:\\", "/Users/", "Traceback", "reviewer_note", "claim", "quote_excerpt", "selected_text", "token=", "secret"):
            text = text.replace(needle, "[redacted]")
    return text


def _ensure_rule_activation_dirs(root: Path | str) -> Path:
    base = ensure_source_knowledge_dirs(root)
    for folder in (RULE_ACTIVATION_REVIEW_DIR, RULE_ACTIVATION_RECEIPT_DIR, RULE_ACTIVATION_BACKUP_DIR):
        (base / folder).mkdir(parents=True, exist_ok=True)
    for index_name in (RULE_ACTIVATION_REVIEW_INDEX, RULE_ACTIVATION_RECEIPT_INDEX):
        path = base / "indexes" / index_name
        if not path.exists():
            _atomic_write_json(path, {"entries": [], "updated_at_utc": _now()})
    return base


def _validate_candidate_schema(candidate: Mapping[str, object]) -> list[str]:
    validation = validate_canonical_rule_record(
        {
            "schema_version": "canonical_mutable_rule_v1",
            "rule_id": "candidate_preview",
            "rule_type": candidate.get("rule_type"),
            "target": candidate.get("target"),
            "scope": candidate.get("scope"),
            "condition": candidate.get("condition"),
            "operator": candidate.get("operator"),
            "value": candidate.get("value"),
            "priority": candidate.get("priority"),
            "enabled": candidate.get("enabled"),
            "status": "active",
            "source_proposal_id": "proposal_preview",
            "source_revision": "preview_revision",
        }
    )
    return list(validation.get("blockers", []))


def _canonical_rule_store_state(root: Path) -> dict[str, object]:
    capability = get_canonical_rule_runtime_capability(root=root)
    listed = list_canonical_rules(limit=500, root=root) if capability.get("available") else {"items": []}
    return {"available": bool(capability.get("available")), "active_rules": list(listed.get("items", [])), "reason": "ok" if capability.get("available") else "unavailable"}


def _rule_activation_review_id(proposal_id: str) -> str:
    return f"proposal_rule_review_{_hash_payload({'proposal_id': proposal_id})[7:23]}"


def _rule_activation_review_path(root: Path, review_id: str) -> Path:
    return root / RULE_ACTIVATION_REVIEW_DIR / f"{review_id}.json"


def _rule_activation_receipt_path(root: Path, receipt_id: str) -> Path:
    return root / RULE_ACTIVATION_RECEIPT_DIR / f"{receipt_id}.json"


def _load_rule_activation_reviews(root: Path) -> list[dict[str, object]]:
    items = []
    for path in sorted((root / RULE_ACTIVATION_REVIEW_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _load_rule_activation_review_by_id(root: Path, review_id: str) -> dict[str, object] | None:
    payload = _read_json(_rule_activation_review_path(root, review_id))
    return payload if isinstance(payload, dict) else None


def _load_rule_activation_review_for_proposal(root: Path, proposal_id: str) -> dict[str, object] | None:
    for item in _load_rule_activation_reviews(root):
        if str(item.get("proposal_id") or "") == proposal_id:
            return item
    return None


def _load_rule_activation_receipts(root: Path) -> list[dict[str, object]]:
    items = []
    for path in sorted((root / RULE_ACTIVATION_RECEIPT_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _load_rule_activation_receipt_by_id(root: Path, receipt_id: str) -> dict[str, object] | None:
    payload = _read_json(_rule_activation_receipt_path(root, receipt_id))
    return payload if isinstance(payload, dict) else None


def _load_rule_activation_receipt_for_proposal(root: Path, proposal_id: str) -> dict[str, object] | None:
    for item in _load_rule_activation_receipts(root):
        if str(item.get("proposal_id") or "") == proposal_id:
            return item
    return None


def _update_rule_activation_review_index(root: Path) -> None:
    entries = []
    for item in _load_rule_activation_reviews(root):
        entries.append(
            {
                "rule_activation_review_id": item.get("rule_activation_review_id"),
                "proposal_id": item.get("proposal_id"),
                "document_id": item.get("document_id"),
                "decision": item.get("decision"),
                "review_status": item.get("review_status"),
                "updated_at_utc": item.get("updated_at_utc"),
            }
        )
    _atomic_write_json(root / "indexes" / RULE_ACTIVATION_REVIEW_INDEX, {"entries": entries, "updated_at_utc": _now()})


def _update_rule_activation_receipt_index(root: Path) -> None:
    entries = []
    for item in _load_rule_activation_receipts(root):
        entries.append(
            {
                "activation_receipt_id": item.get("activation_receipt_id"),
                "proposal_id": item.get("proposal_id"),
                "rule_id": item.get("rule_id"),
                "document_id": item.get("document_id"),
                "source_revision": item.get("source_revision"),
                "created_at_utc": item.get("created_at_utc"),
            }
        )
    _atomic_write_json(root / "indexes" / RULE_ACTIVATION_RECEIPT_INDEX, {"entries": entries, "updated_at_utc": _now()})


def _all_promoted_proposals(root: Path) -> list[dict[str, object]]:
    return [item for item in list_source_revalidation_queue(limit=0, root=root) if False] or [item for item in (_load_proposal(root, path.stem) for path in sorted((root / "proposals").glob("*.json"))) if isinstance(item, dict) and item.get("status") == "promoted"]


def _rule_fingerprint(payload: Mapping[str, object] | None) -> str | None:
    if not isinstance(payload, Mapping):
        return None
    normalized = {
        "rule_type": payload.get("rule_type"),
        "target": payload.get("target"),
        "scope": payload.get("scope"),
        "condition": payload.get("condition"),
        "operator": payload.get("operator"),
        "value": payload.get("value"),
        "priority": payload.get("priority"),
        "enabled": payload.get("enabled"),
    }
    return _hash_payload(normalized)


def _rule_activation_receipt_id(proposal_id: str) -> str:
    return f"proposal_rule_activation_receipt_{_hash_payload({'proposal_id': proposal_id})[7:23]}"


def _rule_id_for_candidate(proposal_id: str, candidate_fingerprint: str | None) -> str:
    return f"rule_{_hash_payload({'proposal_id': proposal_id, 'candidate_fingerprint': candidate_fingerprint})[7:23]}"


def _rule_activation_revalidation_id(activation_receipt_id: str, kind: str) -> str:
    return f"impact_{_hash_payload({'activation_receipt_id': activation_receipt_id, 'kind': kind})[7:23]}"


def _load_rule_activation_revalidation(root: Path, activation_receipt_id: str, *, reason: str) -> dict[str, object] | None:
    for item in list_source_revalidation_queue(limit=500, root=root).get("items", []):
        if not isinstance(item, dict):
            continue
        if item.get("activation_receipt_id") == activation_receipt_id and item.get("reason") == reason:
            return item
    return None


def _post_activation_validation(root: Path, proposal_id: str, rule_id: str, receipt_id: str, candidate_fingerprint: str | None) -> bool:
    loaded = load_canonical_rule(rule_id, require_active=True, root=root)
    rule = loaded.get("rule") if loaded.get("status") == "loaded" else None
    receipt = _load_rule_activation_receipt_by_id(root, receipt_id)
    revalidation = _load_rule_activation_revalidation(root, receipt_id, reason="proposal_rule_activation")
    if not isinstance(rule, dict) or str(rule.get("status") or "") != "active":
        return False
    if _rule_fingerprint(rule) != candidate_fingerprint:
        return False
    if not isinstance(receipt, dict) or receipt.get("rule_id") != rule_id:
        return False
    if not isinstance(revalidation, dict) or revalidation.get("rule_id") != rule_id:
        return False
    duplicates = [item for item in list_canonical_rules(status="active", limit=500, root=root).get("items", []) if _rule_fingerprint(item) == candidate_fingerprint]
    return len(duplicates) == 1 and receipt.get("proposal_id") == proposal_id


def _rollback_paths(targets: Mapping[Path, Any]) -> bool:
    for path, payload in targets.items():
        _restore_json(path, payload)
    return all(_read_json(path) == payload for path, payload in targets.items())


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"_", "-", "."} else "_" for char in str(value).strip()) or "object"


def _report_revalidation_status(root: Path, activation_receipt_id: Any) -> str:
    if not activation_receipt_id:
        return "none"
    item = _load_rule_activation_revalidation(root, str(activation_receipt_id), reason="proposal_rule_activation")
    return str((item or {}).get("status") or "none")


def _same_review(existing: Mapping[str, object], decision: str, note: str | None, ack_inactive: bool, ack_conflict: bool) -> bool:
    return existing.get("decision") == decision and existing.get("reviewer_note") == note and bool(existing.get("acknowledge_inactive_equivalent")) == bool(ack_inactive) and bool(existing.get("acknowledge_conflict")) == bool(ack_conflict)


def _same_payload(existing: Mapping[str, object], payload: Mapping[str, object]) -> bool:
    return all(existing.get(field) == payload.get(field) for field in ("decision", "review_status", "reviewer_note", "acknowledge_inactive_equivalent", "acknowledge_conflict", "candidate_fingerprint"))
