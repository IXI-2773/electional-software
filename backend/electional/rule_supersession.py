"""Controlled supersession of certified canonical rules."""

from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from .canonical_rule_runtime import (
    CANONICAL_RULE_DIR,
    CANONICAL_RULE_INDEX,
    create_canonical_rule,
    load_canonical_rule,
    validate_canonical_rule_record,
)
from .proposal_rule_activation import RULE_ACTIVATION_RECEIPT_DIR
from .proposal_promotion import PROMOTION_RECEIPT_DIR
from .rule_activation_revalidation import CERTIFICATION_RECEIPT_DIR
from .source_documents import SOURCE_DOCUMENT_ROOT
from .source_impact_analysis import QUEUE_INDEX
from .source_knowledge import ensure_source_knowledge_dirs

SUPERSESSION_REVIEW_DIR = "rule_supersession_reviews"
SUPERSESSION_CHAIN_DIR = "rule_supersession_chains"
SUPERSESSION_RECEIPT_DIR = "rule_supersession_receipts"
SUPERSESSION_BACKUP_DIR = "rule_supersession_backups"
SUPERSESSION_REVIEW_INDEX = "rule_supersession_review_index.json"
SUPERSESSION_CHAIN_INDEX = "rule_supersession_chain_index.json"
SUPERSESSION_RECEIPT_INDEX = "rule_supersession_receipt_index.json"
SUPERSESSION_REVIEW_SCHEMA = "rule_supersession_review_v1"
SUPERSESSION_CHAIN_SCHEMA = "rule_version_chain_v1"
SUPERSESSION_RECEIPT_SCHEMA = "rule_supersession_receipt_v1"


def build_rule_supersession_workspace(
    old_rule_id: str,
    replacement_proposal_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_supersession_dirs(root)
    provenance = validate_rule_supersession_provenance(old_rule_id, replacement_proposal_id, root=base)
    candidate = build_rule_supersession_candidate(old_rule_id, replacement_proposal_id, root=base)
    compatibility = analyze_rule_supersession_compatibility(old_rule_id, replacement_proposal_id, root=base)
    review = _load_review_for_pair(base, old_rule_id, replacement_proposal_id)
    receipt = _load_receipt_for_old_rule(base, old_rule_id)
    old_rule = _load_rule_record(base, old_rule_id)
    proposal = _load_proposal(base, replacement_proposal_id)
    active_successor = _find_active_successor(base, old_rule_id)
    warnings = _dedupe(list(provenance.get("warnings", [])) + list(candidate.get("warnings", [])) + list(compatibility.get("warnings", [])))
    blockers = _dedupe(list(provenance.get("blockers", [])) + list(candidate.get("blockers", [])) + list(compatibility.get("blockers", [])))
    return {
        "old_rule_id": old_rule_id,
        "old_rule_status": (old_rule or {}).get("status", "missing"),
        "old_rule_certification_status": "completed" if provenance.get("old_rule_certified") else "missing",
        "replacement_proposal_id": replacement_proposal_id,
        "replacement_proposal_status": (proposal or {}).get("status", "missing"),
        "replacement_mapping_status": candidate.get("candidate_status", "unknown"),
        "supersession_compatibility": compatibility.get("compatibility_status", "unknown"),
        "review_status": (review or {}).get("review_status", "pending"),
        "active_successor_rule_id": active_successor,
        "supersession_receipt_id": (receipt or {}).get("supersession_receipt_id"),
        "candidate_rule_id": candidate.get("candidate_rule_id"),
        "version_chain_id": _chain_id(base, old_rule_id),
        "rollback_available": bool((receipt or {}).get("rollback_available")),
        "replacement_revalidation_status": _receipt_revalidation_status(base, receipt),
        "warnings": warnings,
        "blockers": blockers,
        "recommended_action": "Review the proposed certified-rule replacement." if not blockers else "Resolve supersession blockers before approval.",
    }


def validate_rule_supersession_provenance(
    old_rule_id: str,
    replacement_proposal_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_supersession_dirs(root)
    blockers: list[str] = []
    old_rule = _load_rule_record(base, old_rule_id)
    activation = _load_activation_receipt_for_rule(base, old_rule_id)
    certification = _load_certification_receipt_for_rule(base, old_rule_id)
    replacement = _load_proposal(base, replacement_proposal_id)
    promotion = _load_promotion_receipt_for_proposal(base, replacement_proposal_id)
    if not isinstance(old_rule, dict):
        blockers.append("old_rule_missing")
    elif old_rule.get("status") != "active":
        blockers.append("old_rule_not_active")
    if not isinstance(activation, dict):
        blockers.append("old_rule_activation_receipt_missing")
    elif activation.get("rule_id") != old_rule_id:
        blockers.append("old_rule_activation_receipt_mismatch")
    if not isinstance(certification, dict):
        blockers.append("old_rule_certification_missing")
    elif certification.get("rule_id") != old_rule_id:
        blockers.append("old_rule_certification_mismatch")
    elif isinstance(old_rule, dict) and certification.get("rule_hash") != _hash_payload(old_rule):
        blockers.append("old_rule_certification_hash_mismatch")
    elif not _old_rule_revalidation_resolved(base, certification):
        blockers.append("old_rule_certification_revalidation_missing")
    if not isinstance(replacement, dict):
        blockers.append("replacement_proposal_missing")
    elif replacement.get("status") != "promoted":
        blockers.append("replacement_proposal_not_promoted")
    if not isinstance(promotion, dict):
        blockers.append("replacement_promotion_receipt_missing")
    elif promotion.get("promotion_status") != "completed":
        blockers.append("replacement_promotion_receipt_incomplete")
    if isinstance(replacement, dict):
        if not list(replacement.get("accepted_citation_ids", []) or []):
            blockers.append("replacement_citation_evidence_missing")
        if str(replacement.get("supersedes_rule_id") or "") != old_rule_id:
            blockers.append("replacement_intent_missing")
        if not isinstance(replacement.get("rule_mapping"), Mapping):
            blockers.append("replacement_structured_mapping_missing")
    if isinstance(replacement, dict) and isinstance(promotion, dict):
        if str(replacement.get("source_revision") or "") != str(promotion.get("source_revision") or ""):
            blockers.append("replacement_source_revision_changed")
    return {
        "valid": not blockers,
        "old_rule_id": old_rule_id,
        "old_rule_certified": isinstance(certification, dict) and "old_rule_certification_hash_mismatch" not in blockers,
        "replacement_proposal_id": replacement_proposal_id,
        "replacement_proposal_promoted": isinstance(replacement, dict) and replacement.get("status") == "promoted",
        "replacement_source_current": "replacement_source_revision_changed" not in blockers,
        "replacement_intent_valid": "replacement_intent_missing" not in blockers,
        "warnings": [],
        "blockers": _dedupe(blockers),
    }


def build_rule_supersession_candidate(
    old_rule_id: str,
    replacement_proposal_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_supersession_dirs(root)
    blockers: list[str] = []
    proposal = _load_proposal(base, replacement_proposal_id)
    old_rule = _load_rule_record(base, old_rule_id)
    if not isinstance(proposal, dict) or not isinstance(proposal.get("rule_mapping"), Mapping):
        blockers.append("replacement_structured_mapping_missing")
        return {
            "candidate_status": "invalid",
            "old_rule_id": old_rule_id,
            "candidate_rule_id": None,
            "candidate_fingerprint": None,
            "mapping_basis": [],
            "warnings": [],
            "blockers": blockers,
        }
    mapping = deepcopy(dict(proposal.get("rule_mapping") or {}))
    candidate = {
        "schema_version": "canonical_mutable_rule_v1",
        "rule_id": _candidate_rule_id(old_rule_id, replacement_proposal_id, mapping),
        "rule_type": mapping.get("rule_type") or mapping.get("rule_family"),
        "target": mapping.get("target"),
        "scope": mapping.get("scope"),
        "condition": deepcopy(dict(mapping.get("condition") or {})),
        "operator": mapping.get("operator"),
        "value": mapping.get("value"),
        "priority": mapping.get("priority", 50),
        "enabled": bool(mapping.get("enabled", True)),
        "status": "active",
        "document_id": proposal.get("document_id"),
        "supersedes_rule_id": old_rule_id,
        "source_proposal_id": replacement_proposal_id,
        "source_promotion_receipt_id": (_load_promotion_receipt_for_proposal(base, replacement_proposal_id) or {}).get("promotion_receipt_id"),
        "source_citation_ids": list(proposal.get("accepted_citation_ids", []) or []),
        "source_revision": proposal.get("source_revision"),
        "created_from": "rule_supersession",
        "created_at_utc": _now(),
        "updated_at_utc": _now(),
    }
    validation = validate_canonical_rule_record(candidate, require_active=True)
    blockers.extend(list(validation.get("blockers", [])))
    mapping_basis = [
        "explicit_supersedes_rule_id",
        "explicit_rule_target",
        "explicit_rule_operator",
        "explicit_rule_value",
    ]
    if isinstance(old_rule, dict) and str(old_rule.get("rule_id") or "") == str(candidate.get("rule_id") or ""):
        blockers.append("replacement_reuses_old_rule_id")
    return {
        "candidate_status": "valid" if not blockers else "invalid",
        "old_rule_id": old_rule_id,
        "candidate_rule_id": candidate.get("rule_id"),
        "candidate_fingerprint": validation.get("rule_fingerprint"),
        "candidate_rule": candidate,
        "mapping_basis": mapping_basis,
        "warnings": [],
        "blockers": _dedupe(blockers),
    }


def analyze_rule_supersession_compatibility(
    old_rule_id: str,
    replacement_proposal_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_supersession_dirs(root)
    old_rule = _load_rule_record(base, old_rule_id)
    candidate_info = build_rule_supersession_candidate(old_rule_id, replacement_proposal_id, root=base)
    candidate = candidate_info.get("candidate_rule")
    blockers = list(candidate_info.get("blockers", []))
    warnings: list[str] = []
    relationship = "unknown"
    if not isinstance(old_rule, dict) or not isinstance(candidate, Mapping):
        return {
            "compatibility_status": "blocked",
            "relationship": relationship,
            "exact_duplicate": False,
            "active_successor_exists": False,
            "requires_scope_acknowledgement": False,
            "supersession_allowed": False,
            "warnings": warnings,
            "blockers": _dedupe(blockers or ["supersession_comparison_unavailable"]),
        }
    if _candidate_behavior_signature(old_rule) == _candidate_behavior_signature(candidate):
        blockers.append("replacement_exact_duplicate")
        relationship = "exact_duplicate"
    elif str(old_rule.get("rule_type") or old_rule.get("rule_family") or "") != str(candidate.get("rule_type") or candidate.get("rule_family") or "") or str(old_rule.get("target") or "") != str(candidate.get("target") or ""):
        blockers.append("replacement_incompatible")
        relationship = "incompatible"
    elif str(old_rule.get("scope") or "") != str(candidate.get("scope") or ""):
        relationship = "scope_expansion" if len(str(candidate.get("scope") or "")) > len(str(old_rule.get("scope") or "")) else "scope_contraction"
        warnings.append("replacement_scope_is_broader" if relationship == "scope_expansion" else "replacement_scope_is_narrower")
    else:
        relationship = "valid_replacement"
    active_successor = _find_active_successor(base, old_rule_id)
    if active_successor and active_successor != candidate.get("rule_id"):
        blockers.append("active_successor_exists")
    requires_scope_ack = relationship in {"scope_expansion", "scope_contraction"}
    return {
        "compatibility_status": "blocked" if blockers else "warning" if warnings else "valid",
        "relationship": relationship,
        "exact_duplicate": relationship == "exact_duplicate",
        "active_successor_exists": bool(active_successor),
        "requires_scope_acknowledgement": requires_scope_ack,
        "supersession_allowed": not blockers,
        "warnings": warnings,
        "blockers": _dedupe(blockers),
    }


def save_rule_supersession_decision(
    old_rule_id: str,
    replacement_proposal_id: str,
    decision: str,
    reviewer_note: str | None = None,
    acknowledge_scope_change: bool = False,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_supersession_dirs(root)
    if decision not in {"approve", "reject", "request_changes"}:
        return {"status": "blocked", "blockers": ["supersession_decision_invalid"], "warnings": []}
    note = _non_empty_text(reviewer_note)
    if decision in {"reject", "request_changes"} and note is None:
        return {"status": "blocked", "blockers": ["reviewer_note_required"], "warnings": []}
    provenance = validate_rule_supersession_provenance(old_rule_id, replacement_proposal_id, root=base)
    candidate = build_rule_supersession_candidate(old_rule_id, replacement_proposal_id, root=base)
    compatibility = analyze_rule_supersession_compatibility(old_rule_id, replacement_proposal_id, root=base)
    blockers = []
    if decision == "approve":
        blockers.extend(list(provenance.get("blockers", [])))
        blockers.extend(list(candidate.get("blockers", [])))
        blockers.extend(list(compatibility.get("blockers", [])))
        if compatibility.get("requires_scope_acknowledgement") and not acknowledge_scope_change:
            blockers.append("scope_change_acknowledgement_required")
    if blockers:
        return {"status": "blocked", "blockers": _dedupe(blockers), "warnings": []}
    current = _load_review_for_pair(base, old_rule_id, replacement_proposal_id)
    payload = {
        "schema_version": SUPERSESSION_REVIEW_SCHEMA,
        "supersession_review_id": (current or {}).get("supersession_review_id") or _review_id(old_rule_id, replacement_proposal_id),
        "old_rule_id": old_rule_id,
        "replacement_proposal_id": replacement_proposal_id,
        "candidate_rule_id": candidate.get("candidate_rule_id"),
        "decision": decision,
        "review_status": "approved" if decision == "approve" else "rejected" if decision == "reject" else "changes_requested",
        "acknowledge_scope_change": bool(acknowledge_scope_change),
        "candidate_fingerprint": candidate.get("candidate_fingerprint"),
        "old_rule_fingerprint": _rule_fingerprint(old_rule_id, base),
        "review_revision": int((current or {}).get("review_revision") or 0) + 1,
        "created_at_utc": (current or {}).get("created_at_utc") or _now(),
        "updated_at_utc": _now(),
        "reviewer_note": note,
        "warnings": list(compatibility.get("warnings", [])),
    }
    before_record = _read_json(_review_path(base, str(payload["supersession_review_id"])))
    before_index = _read_json(_review_index_path(base))
    try:
        _atomic_write_json(_review_path(base, str(payload["supersession_review_id"])), payload)
        _update_review_index(base)
    except Exception:
        _restore_json(_review_path(base, str(payload["supersession_review_id"])), before_record)
        _restore_json(_review_index_path(base), before_index)
        return {"status": "failed_rolled_back", "classification": "supersession_review_write_failure", "warnings": []}
    return {"status": "saved", "review": payload, "warnings": list(payload.get("warnings", []))}


def supersede_certified_rule(
    supersession_review_id: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    if confirmation != "SUPERSEDE":
        return {"status": "blocked", "blockers": ["supersede_confirmation_required"], "warnings": []}
    base = _ensure_supersession_dirs(root)
    review = _load_review_by_id(base, supersession_review_id)
    if not isinstance(review, dict):
        return {"status": "blocked", "blockers": ["supersession_review_missing"], "warnings": []}
    receipt = _load_receipt_for_review(base, supersession_review_id)
    if review.get("review_status") == "completed" and isinstance(receipt, dict):
        if _supersession_state_matches_receipt(base, receipt):
            return {
                "status": "already_superseded",
                "old_rule_id": receipt.get("old_rule_id"),
                "new_rule_id": receipt.get("new_rule_id"),
                "supersession_receipt_id": receipt.get("supersession_receipt_id"),
                "writes_performed": 0,
            }
        return {"status": "blocked", "blockers": ["rule_supersession_state_diverged"], "warnings": []}
    if review.get("review_status") != "approved":
        return {"status": "blocked", "blockers": ["supersession_review_not_approved"], "warnings": []}
    old_rule_id = str(review.get("old_rule_id") or "")
    replacement_proposal_id = str(review.get("replacement_proposal_id") or "")
    provenance = validate_rule_supersession_provenance(old_rule_id, replacement_proposal_id, root=base)
    candidate_info = build_rule_supersession_candidate(old_rule_id, replacement_proposal_id, root=base)
    compatibility = analyze_rule_supersession_compatibility(old_rule_id, replacement_proposal_id, root=base)
    blockers = _dedupe(list(provenance.get("blockers", [])) + list(candidate_info.get("blockers", [])) + list(compatibility.get("blockers", [])))
    if compatibility.get("requires_scope_acknowledgement") and not review.get("acknowledge_scope_change"):
        blockers.append("scope_change_acknowledgement_required")
    old_rule = _load_rule_record(base, old_rule_id)
    if not isinstance(old_rule, dict):
        blockers.append("old_rule_missing")
    if review.get("old_rule_fingerprint") != _hash_payload(old_rule):
        blockers.append("old_rule_fingerprint_changed")
    if review.get("candidate_fingerprint") != candidate_info.get("candidate_fingerprint"):
        blockers.append("candidate_fingerprint_changed")
    if isinstance(receipt, dict):
        if _supersession_state_matches_receipt(base, receipt):
            return {
                "status": "already_superseded",
                "old_rule_id": receipt.get("old_rule_id"),
                "new_rule_id": receipt.get("new_rule_id"),
                "supersession_receipt_id": receipt.get("supersession_receipt_id"),
                "writes_performed": 0,
            }
        return {"status": "blocked", "blockers": ["rule_supersession_state_diverged"], "warnings": []}
    if blockers:
        return {"status": "blocked", "blockers": blockers, "warnings": list(compatibility.get("warnings", []))}
    candidate = deepcopy(dict(candidate_info["candidate_rule"]))
    new_rule_id = str(candidate["rule_id"])
    if _find_active_successor(base, old_rule_id):
        return {"status": "blocked", "blockers": ["active_successor_exists"], "warnings": []}
    old_updated = deepcopy(old_rule)
    old_updated["status"] = "inactive"
    old_updated["enabled"] = False
    old_updated["updated_at_utc"] = _now()
    old_updated["deactivated_at_utc"] = _now()
    old_updated["deactivation_reason"] = f"superseded_by:{new_rule_id}"
    old_updated["superseded_by_rule_id"] = new_rule_id
    old_updated["rule_fingerprint"] = _rule_fingerprint_from_payload(old_updated)
    before_active_index_hash = _hash_payload(_load_canonical_rule_index(base))
    created = create_canonical_rule(candidate, confirmation="CREATE_RULE", root=base)
    if created.get("status") not in {"created", "already_created"}:
        return {"status": "blocked", "blockers": ["replacement_rule_creation_failed"], "warnings": []}
    new_rule = _load_rule_record(base, new_rule_id)
    if not isinstance(new_rule, dict):
        return {"status": "blocked", "blockers": ["replacement_rule_missing_after_create"], "warnings": []}
    chain_before = _load_chain_for_rule(base, old_rule_id)
    chain_after = _next_chain_payload(base, chain_before, old_rule_id, new_rule_id)
    revalidation_id = _revalidation_id(new_rule_id, supersession_review_id)
    receipt_id = _receipt_id(supersession_review_id)
    for version in chain_after.get("versions", []):
        if version.get("rule_id") in {old_rule_id, new_rule_id}:
            version["supersession_receipt_id"] = receipt_id
    receipt_payload = {
        "schema_version": SUPERSESSION_RECEIPT_SCHEMA,
        "supersession_receipt_id": receipt_id,
        "supersession_review_id": supersession_review_id,
        "version_chain_id": chain_after["version_chain_id"],
        "old_rule_id": old_rule_id,
        "new_rule_id": new_rule_id,
        "replacement_proposal_id": replacement_proposal_id,
        "old_rule_fingerprint": _hash_payload(old_rule),
        "new_rule_fingerprint": _hash_payload(new_rule),
        "before_active_index_hash": before_active_index_hash,
        "after_active_index_hash": None,
        "old_rule_backup_hash": None,
        "new_rule_hash": _hash_payload(new_rule),
        "supersession_status": "completed",
        "rollback_available": True,
        "created_at_utc": _now(),
        "warnings": list(compatibility.get("warnings", [])),
    }
    revalidation = {
        "queue_item_id": revalidation_id,
        "document_id": candidate.get("document_id"),
        "change_type": "manual_review",
        "impact_severity": "medium",
        "status": "pending_review",
        "reason": "rule_supersession",
        "proposal_id": replacement_proposal_id,
        "old_rule_id": old_rule_id,
        "new_rule_id": new_rule_id,
        "version_chain_id": chain_after["version_chain_id"],
        "supersession_receipt_id": receipt_payload["supersession_receipt_id"],
        "rule_id": new_rule_id,
        "source_revision": candidate.get("source_revision"),
        "citation_ids": list(candidate.get("source_citation_ids", []) or []),
        "created_at_utc": _now(),
        "warnings": [],
        "dedupe_key": "sha256:" + _hash_payload({"supersession_receipt_id": receipt_payload["supersession_receipt_id"], "reason": "rule_supersession"}),
    }
    updated_review = deepcopy(review)
    updated_review["review_status"] = "completed"
    updated_review["updated_at_utc"] = _now()
    updated_review["supersession_receipt_id"] = receipt_payload["supersession_receipt_id"]
    review_path = _review_path(base, supersession_review_id)
    old_rule_path = _rule_path(base, old_rule_id)
    new_rule_path = _rule_path(base, new_rule_id)
    chain_path = _chain_path(base, chain_after["version_chain_id"])
    receipt_path = _receipt_path(base, receipt_payload["supersession_receipt_id"])
    revalidation_path = _queue_path(base, revalidation_id)
    backup_old_path = _backup_path(base, receipt_payload["supersession_receipt_id"], old_rule_id)
    backup_new_path = _backup_path(base, receipt_payload["supersession_receipt_id"], new_rule_id)
    write_targets = {
        old_rule_path: _read_json(old_rule_path),
        new_rule_path: _read_json(new_rule_path),
        _canonical_rule_index_path(base): _read_json(_canonical_rule_index_path(base)),
        chain_path: _read_json(chain_path),
        _chain_index_path(base): _read_json(_chain_index_path(base)),
        receipt_path: _read_json(receipt_path),
        _receipt_index_path(base): _read_json(_receipt_index_path(base)),
        revalidation_path: _read_json(revalidation_path),
        base / "indexes" / QUEUE_INDEX: _read_json(base / "indexes" / QUEUE_INDEX),
        review_path: _read_json(review_path),
        _review_index_path(base): _read_json(_review_index_path(base)),
    }
    try:
        _atomic_write_json(backup_old_path, old_rule)
        _atomic_write_json(backup_new_path, new_rule)
        receipt_payload["old_rule_backup_hash"] = _hash_payload(old_rule)
        _atomic_write_json(old_rule_path, old_updated)
        _atomic_write_json(_canonical_rule_index_path(base), _index_with_rule(_index_with_rule(_load_canonical_rule_index(base), old_updated), new_rule))
        receipt_payload["after_active_index_hash"] = _hash_payload(_load_canonical_rule_index(base))
        _atomic_write_json(chain_path, chain_after)
        _update_chain_index(base)
        _atomic_write_json(receipt_path, receipt_payload)
        _update_receipt_index(base)
        _atomic_write_json(revalidation_path, revalidation)
        _update_queue_index(base)
        _atomic_write_json(review_path, updated_review)
        _update_review_index(base)
    except Exception:
        rollback_verified = _rollback_paths(write_targets)
        return {
            "status": "rollback_failed" if not rollback_verified else "failed_rolled_back",
            "classification": "critical_recovery_failure" if not rollback_verified else "version_chain_commit_failure",
            "records_restored": len(write_targets),
            "new_records_removed": len(write_targets),
            "rollback_verified": rollback_verified,
            "warnings": [],
        }
    if not _exactly_one_active_version(base, chain_after["version_chain_id"], old_rule_id, new_rule_id):
        return {"status": "blocked", "blockers": ["rule_supersession_state_diverged"], "warnings": []}
    return {
        "status": "superseded",
        "supersession_review_id": supersession_review_id,
        "old_rule_id": old_rule_id,
        "old_rule_status": "inactive",
        "new_rule_id": new_rule_id,
        "new_rule_status": "active",
        "version_chain_id": chain_after["version_chain_id"],
        "supersession_receipt_id": receipt_payload["supersession_receipt_id"],
        "revalidation_id": revalidation_id,
        "revalidation_status": "pending_review",
        "warnings": list(receipt_payload.get("warnings", [])),
    }


def rollback_rule_supersession(
    supersession_receipt_id: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    if confirmation != "ROLLBACK_SUPERSESSION":
        return {"status": "blocked", "blockers": ["rollback_supersession_confirmation_required"], "warnings": []}
    base = _ensure_supersession_dirs(root)
    receipt = _load_receipt_by_id(base, supersession_receipt_id)
    if not isinstance(receipt, dict):
        return {"status": "blocked", "blockers": ["supersession_receipt_missing"], "warnings": []}
    if receipt.get("supersession_status") != "completed":
        return {"status": "blocked", "blockers": ["supersession_receipt_incomplete"], "warnings": []}
    old_rule_id = str(receipt.get("old_rule_id") or "")
    new_rule_id = str(receipt.get("new_rule_id") or "")
    old_rule = _load_rule_record(base, old_rule_id)
    new_rule = _load_rule_record(base, new_rule_id)
    chain = _load_chain_by_id(base, str(receipt.get("version_chain_id") or ""))
    if not isinstance(old_rule, dict) or not isinstance(new_rule, dict) or not isinstance(chain, dict):
        return {"status": "blocked", "blockers": ["supersession_receipt_state_missing"], "warnings": []}
    if _load_certification_receipt_for_rule(base, new_rule_id):
        return {"status": "blocked", "blockers": ["rollback_blocked_after_certification"], "warnings": []}
    if chain.get("current_active_rule_id") != new_rule_id:
        return {"status": "blocked", "blockers": ["rollback_blocked_after_later_supersession"], "warnings": []}
    if old_rule.get("status") != "inactive" or new_rule.get("status") != "active":
        return {"status": "blocked", "blockers": ["rollback_state_invalid"], "warnings": []}
    old_backup = _read_json(_backup_path(base, supersession_receipt_id, old_rule_id))
    if not isinstance(old_backup, dict):
        return {"status": "blocked", "blockers": ["rollback_backup_missing"], "warnings": []}
    restored_old = deepcopy(old_backup)
    restored_old["status"] = "active"
    restored_old["enabled"] = True
    restored_old.pop("deactivation_reason", None)
    restored_old.pop("superseded_by_rule_id", None)
    restored_old["updated_at_utc"] = _now()
    restored_old["rule_fingerprint"] = _rule_fingerprint_from_payload(restored_old)
    rolled_back_new = deepcopy(new_rule)
    rolled_back_new["status"] = "rolled_back"
    rolled_back_new["enabled"] = False
    rolled_back_new["updated_at_utc"] = _now()
    rolled_back_new["rolled_back_at_utc"] = _now()
    rolled_back_new["rule_fingerprint"] = _rule_fingerprint_from_payload(rolled_back_new)
    updated_chain = deepcopy(chain)
    updated_chain["current_active_rule_id"] = old_rule_id
    updated_chain["chain_revision"] = int(updated_chain.get("chain_revision") or len(updated_chain.get("versions", []))) + 1
    updated_chain["updated_at_utc"] = _now()
    updated_chain["last_rollback"] = {
        "supersession_receipt_id": supersession_receipt_id,
        "restored_rule_id": old_rule_id,
        "rolled_back_rule_id": new_rule_id,
        "rolled_back_at_utc": _now(),
    }
    for version in updated_chain.get("versions", []):
        if version.get("rule_id") == old_rule_id:
            version["status"] = "active"
        elif version.get("rule_id") == new_rule_id:
            version["status"] = "rolled_back"
    rollback_revalidation_id = _revalidation_id(old_rule_id, f"rollback:{supersession_receipt_id}")
    rollback_revalidation = {
        "queue_item_id": rollback_revalidation_id,
        "document_id": restored_old.get("document_id"),
        "change_type": "manual_review",
        "impact_severity": "medium",
        "status": "pending_review",
        "reason": "rule_supersession_rollback",
        "proposal_id": receipt.get("replacement_proposal_id"),
        "old_rule_id": old_rule_id,
        "new_rule_id": new_rule_id,
        "version_chain_id": receipt.get("version_chain_id"),
        "supersession_receipt_id": supersession_receipt_id,
        "rule_id": old_rule_id,
        "source_revision": restored_old.get("source_revision"),
        "citation_ids": list(restored_old.get("source_citation_ids", []) or []),
        "created_at_utc": _now(),
        "warnings": [],
        "dedupe_key": "sha256:" + _hash_payload({"supersession_receipt_id": supersession_receipt_id, "reason": "rule_supersession_rollback"}),
    }
    updated_receipt = deepcopy(receipt)
    updated_receipt["rollback_available"] = False
    updated_receipt["rolled_back_at_utc"] = _now()
    old_rule_path = _rule_path(base, old_rule_id)
    new_rule_path = _rule_path(base, new_rule_id)
    chain_path = _chain_path(base, str(receipt.get("version_chain_id") or ""))
    receipt_path = _receipt_path(base, supersession_receipt_id)
    rollback_path = _queue_path(base, rollback_revalidation_id)
    write_targets = {
        old_rule_path: _read_json(old_rule_path),
        new_rule_path: _read_json(new_rule_path),
        _canonical_rule_index_path(base): _read_json(_canonical_rule_index_path(base)),
        chain_path: _read_json(chain_path),
        _chain_index_path(base): _read_json(_chain_index_path(base)),
        receipt_path: _read_json(receipt_path),
        _receipt_index_path(base): _read_json(_receipt_index_path(base)),
        rollback_path: _read_json(rollback_path),
        base / "indexes" / QUEUE_INDEX: _read_json(base / "indexes" / QUEUE_INDEX),
    }
    try:
        _atomic_write_json(old_rule_path, restored_old)
        _atomic_write_json(new_rule_path, rolled_back_new)
        _atomic_write_json(_canonical_rule_index_path(base), _index_with_rule(_index_with_rule(_load_canonical_rule_index(base), restored_old), rolled_back_new))
        _atomic_write_json(chain_path, updated_chain)
        _update_chain_index(base)
        _atomic_write_json(receipt_path, updated_receipt)
        _update_receipt_index(base)
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
        "supersession_receipt_id": supersession_receipt_id,
        "restored_rule_id": old_rule_id,
        "restored_rule_status": "active",
        "rolled_back_rule_id": new_rule_id,
        "rolled_back_rule_status": "rolled_back",
        "version_chain_id": receipt.get("version_chain_id"),
        "rollback_revalidation_id": rollback_revalidation_id,
        "rollback_verified": True,
        "warnings": [],
    }


def format_rule_supersession_report(
    supersession_review_id: str | None = None,
    supersession_receipt_id: str | None = None,
    version_chain_id: str | None = None,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    base = _ensure_supersession_dirs(root)
    review = _load_review_by_id(base, supersession_review_id) if supersession_review_id else None
    receipt = _load_receipt_by_id(base, supersession_receipt_id) if supersession_receipt_id else None
    chain = _load_chain_by_id(base, version_chain_id or str((receipt or {}).get("version_chain_id") or "")) if (version_chain_id or (receipt or {}).get("version_chain_id")) else None
    workspace = build_rule_supersession_workspace(
        str((review or {}).get("old_rule_id") or (receipt or {}).get("old_rule_id") or ""),
        str((review or {}).get("replacement_proposal_id") or (receipt or {}).get("replacement_proposal_id") or ""),
        root=base,
    ) if review or receipt else {"recommended_action": "Load a certified rule supersession workspace."}
    lines = [
        "Rule Supersession Report",
        "",
        f"Version Chain: {str((chain or {}).get('version_chain_id') or (receipt or {}).get('version_chain_id') or 'none')}",
        "",
        "Previous Rule:",
        f"- Rule ID: {str((receipt or {}).get('old_rule_id') or (review or {}).get('old_rule_id') or 'none')}",
        f"- Previous Status: {'active' if not receipt else 'active'}",
        f"- Current Status: {workspace.get('old_rule_status', 'unknown')}",
        f"- Certification: {'valid at supersession time' if workspace.get('old_rule_certification_status') == 'completed' else 'missing'}",
        "",
        "Replacement:",
        f"- Rule ID: {str((receipt or {}).get('new_rule_id') or (review or {}).get('candidate_rule_id') or workspace.get('candidate_rule_id') or 'none')}",
        f"- Status: {str('rolled_back' if (chain or {}).get('last_rollback') else ((receipt and 'active') or 'pending'))}",
        f"- Source Proposal: {str((receipt or {}).get('replacement_proposal_id') or (review or {}).get('replacement_proposal_id') or 'none')}",
        f"- Runtime Certification: {_receipt_revalidation_status(base, receipt)}",
        "",
        "Supersession:",
        f"- Receipt: {str((receipt or {}).get('supersession_receipt_id') or 'none')}",
        f"- Status: {str((receipt or {}).get('supersession_status') or (review or {}).get('review_status') or 'not_completed')}",
        f"- Exactly One Active Version: {'Yes' if chain and _chain_active_count(chain) == 1 else 'No'}",
        "",
        "Revalidation:",
        f"- Status: {_receipt_revalidation_status(base, receipt)}",
        "",
        "Recovery:",
        f"- Rollback Available: {'Yes' if (receipt or {}).get('rollback_available') else 'No'}",
        f"- Rollback Performed: {'Yes' if (receipt or {}).get('rolled_back_at_utc') else 'No'}",
        "",
        "Important:",
        "The previous rule was preserved as historical state.",
        "The replacement rule has not inherited the previous rule's runtime certification.",
    ]
    if not public_safe and isinstance(review, dict):
        lines.extend(["", f"Reviewer Note: {review.get('reviewer_note') or 'none'}"])
    return "\n".join(lines)


def _ensure_supersession_dirs(root: Path | str) -> Path:
    base = ensure_source_knowledge_dirs(root)
    for name in (SUPERSESSION_REVIEW_DIR, SUPERSESSION_CHAIN_DIR, SUPERSESSION_RECEIPT_DIR, SUPERSESSION_BACKUP_DIR, "indexes"):
        (base / name).mkdir(parents=True, exist_ok=True)
    for path, payload in (
        (_review_index_path(base), {"schema_version": "rule_supersession_review_index_v1", "items": [], "updated_at_utc": _now()}),
        (_chain_index_path(base), {"schema_version": "rule_supersession_chain_index_v1", "items": [], "updated_at_utc": _now()}),
        (_receipt_index_path(base), {"schema_version": "rule_supersession_receipt_index_v1", "items": [], "updated_at_utc": _now()}),
    ):
        if not path.exists():
            _atomic_write_json(path, payload)
    return base


def _load_rule_record(root: Path, rule_id: str) -> dict[str, Any] | None:
    loaded = load_canonical_rule(rule_id, root=root)
    if loaded.get("status") == "loaded":
        return deepcopy(dict(loaded.get("rule") or {}))
    path = _rule_path(root, rule_id)
    payload = _read_json(path)
    return deepcopy(dict(payload)) if isinstance(payload, dict) else None


def _load_proposal(root: Path, proposal_id: str) -> dict[str, Any] | None:
    payload = _read_json(root / "proposals" / f"{_safe_id(proposal_id)}.json")
    return deepcopy(dict(payload)) if isinstance(payload, dict) else None


def _load_promotion_receipt_for_proposal(root: Path, proposal_id: str) -> dict[str, Any] | None:
    for path in sorted((root / PROMOTION_RECEIPT_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict) and str(payload.get("proposal_id") or "") == proposal_id:
            return deepcopy(dict(payload))
    return None


def _load_activation_receipt_for_rule(root: Path, rule_id: str) -> dict[str, Any] | None:
    for path in sorted((root / RULE_ACTIVATION_RECEIPT_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict) and str(payload.get("rule_id") or "") == rule_id and str(payload.get("activation_status") or "") == "completed":
            return deepcopy(dict(payload))
    return None


def _load_certification_receipt_for_rule(root: Path, rule_id: str) -> dict[str, Any] | None:
    matches = []
    for path in sorted((root / CERTIFICATION_RECEIPT_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict) and str(payload.get("rule_id") or "") == rule_id and str(payload.get("certification_status") or "") == "completed":
            matches.append(deepcopy(dict(payload)))
    return matches[-1] if matches else None


def _old_rule_revalidation_resolved(root: Path, certification: Mapping[str, Any] | None) -> bool:
    if not isinstance(certification, Mapping):
        return False
    queue = _read_json(_queue_path(root, str(certification.get("revalidation_id") or "")))
    return isinstance(queue, dict) and queue.get("status") == "resolved" and queue.get("resolution") == "rule_runtime_certified"


def _candidate_behavior_signature(rule: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "rule_type": rule.get("rule_type") or rule.get("rule_family"),
        "target": rule.get("target"),
        "scope": rule.get("scope"),
        "condition": deepcopy(dict(rule.get("condition") or {})),
        "operator": rule.get("operator"),
        "value": deepcopy(rule.get("value")),
        "priority": rule.get("priority"),
        "enabled": bool(rule.get("enabled")),
    }


def _candidate_rule_id(old_rule_id: str, proposal_id: str, mapping: Mapping[str, Any]) -> str:
    return f"rule_{_hash_payload({'old_rule_id': old_rule_id, 'proposal_id': proposal_id, 'mapping': _candidate_behavior_signature(mapping)})[7:23]}"


def _review_id(old_rule_id: str, proposal_id: str) -> str:
    return f"rule_supersession_review_{_hash_payload({'old_rule_id': old_rule_id, 'proposal_id': proposal_id})[7:23]}"


def _receipt_id(review_id: str) -> str:
    return f"rule_supersession_receipt_{_hash_payload({'review_id': review_id})[7:23]}"


def _revalidation_id(rule_id: str, seed: str) -> str:
    return f"impact_{_hash_payload({'rule_id': rule_id, 'seed': seed})[7:23]}"


def _chain_id(root: Path, rule_id: str) -> str:
    chain = _load_chain_for_rule(root, rule_id)
    if isinstance(chain, dict):
        return str(chain.get("version_chain_id") or "")
    return f"rule_chain_{_safe_id(rule_id)}"


def _load_chain_for_rule(root: Path, rule_id: str) -> dict[str, Any] | None:
    for path in sorted((root / SUPERSESSION_CHAIN_DIR).glob("*.json")):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        ids = {str(payload.get("root_rule_id") or "")}
        ids.update(str(item.get("rule_id") or "") for item in payload.get("versions", []) if isinstance(item, Mapping))
        if rule_id in ids:
            return deepcopy(dict(payload))
    return None


def _load_chain_by_id(root: Path, chain_id: str) -> dict[str, Any] | None:
    payload = _read_json(_chain_path(root, chain_id))
    return deepcopy(dict(payload)) if isinstance(payload, dict) else None


def _load_review_for_pair(root: Path, old_rule_id: str, proposal_id: str) -> dict[str, Any] | None:
    for path in sorted((root / SUPERSESSION_REVIEW_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict) and str(payload.get("old_rule_id") or "") == old_rule_id and str(payload.get("replacement_proposal_id") or "") == proposal_id:
            return deepcopy(dict(payload))
    return None


def _load_review_by_id(root: Path, review_id: str) -> dict[str, Any] | None:
    payload = _read_json(_review_path(root, review_id))
    return deepcopy(dict(payload)) if isinstance(payload, dict) else None


def _load_receipt_for_review(root: Path, review_id: str) -> dict[str, Any] | None:
    for path in sorted((root / SUPERSESSION_RECEIPT_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict) and str(payload.get("supersession_review_id") or "") == review_id:
            return deepcopy(dict(payload))
    return None


def _load_receipt_for_old_rule(root: Path, old_rule_id: str) -> dict[str, Any] | None:
    for path in sorted((root / SUPERSESSION_RECEIPT_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict) and str(payload.get("old_rule_id") or "") == old_rule_id:
            return deepcopy(dict(payload))
    return None


def _load_receipt_by_id(root: Path, receipt_id: str) -> dict[str, Any] | None:
    payload = _read_json(_receipt_path(root, receipt_id))
    return deepcopy(dict(payload)) if isinstance(payload, dict) else None


def _find_active_successor(root: Path, old_rule_id: str) -> str | None:
    chain = _load_chain_for_rule(root, old_rule_id)
    if not isinstance(chain, dict):
        return None
    current = str(chain.get("current_active_rule_id") or "")
    return current if current and current != old_rule_id else None


def _next_chain_payload(root: Path, existing: Mapping[str, Any] | None, old_rule_id: str, new_rule_id: str) -> dict[str, Any]:
    if isinstance(existing, Mapping):
        payload = deepcopy(dict(existing))
        versions = deepcopy(list(payload.get("versions", [])))
        for item in versions:
            if item.get("rule_id") == old_rule_id:
                item["status"] = "inactive"
                item["superseded_by_rule_id"] = new_rule_id
        versions.append(
            {
                "rule_id": new_rule_id,
                "version_number": len(versions) + 1,
                "status": "active",
                "supersedes_rule_id": old_rule_id,
        "supersession_receipt_id": None,
            }
        )
        payload["versions"] = versions
        payload["current_active_rule_id"] = new_rule_id
        payload["chain_revision"] = int(payload.get("chain_revision") or len(versions) - 1) + 1
        payload["updated_at_utc"] = _now()
        return payload
    return {
        "schema_version": SUPERSESSION_CHAIN_SCHEMA,
        "version_chain_id": f"rule_chain_{_safe_id(old_rule_id)}",
        "root_rule_id": old_rule_id,
        "current_active_rule_id": new_rule_id,
        "versions": [
            {
                "rule_id": old_rule_id,
                "version_number": 1,
                "status": "inactive",
                "superseded_by_rule_id": new_rule_id,
                "supersession_receipt_id": None,
            },
            {
                "rule_id": new_rule_id,
                "version_number": 2,
                "status": "active",
                "supersedes_rule_id": old_rule_id,
                "supersession_receipt_id": None,
            },
        ],
        "chain_revision": 2,
        "created_at_utc": _now(),
        "updated_at_utc": _now(),
    }


def _exactly_one_active_version(root: Path, chain_id: str, old_rule_id: str, new_rule_id: str) -> bool:
    chain = _load_chain_by_id(root, chain_id)
    if not isinstance(chain, dict):
        return False
    if _chain_active_count(chain) != 1 or chain.get("current_active_rule_id") != new_rule_id:
        return False
    index = _load_canonical_rule_index(root)
    active_ids = set(index.get("active_rule_ids", []))
    return old_rule_id not in active_ids and new_rule_id in active_ids


def _supersession_state_matches_receipt(root: Path, receipt: Mapping[str, Any]) -> bool:
    old_rule = _load_rule_record(root, str(receipt.get("old_rule_id") or ""))
    new_rule = _load_rule_record(root, str(receipt.get("new_rule_id") or ""))
    if not isinstance(old_rule, dict) or not isinstance(new_rule, dict):
        return False
    if old_rule.get("status") != "inactive" or new_rule.get("status") != "active":
        return False
    chain = _load_chain_by_id(root, str(receipt.get("version_chain_id") or ""))
    if not isinstance(chain, dict):
        return False
    return chain.get("current_active_rule_id") == receipt.get("new_rule_id") and _chain_active_count(chain) == 1


def _chain_active_count(chain: Mapping[str, Any]) -> int:
    return sum(1 for item in chain.get("versions", []) if isinstance(item, Mapping) and item.get("status") == "active")


def _receipt_revalidation_status(root: Path, receipt: Mapping[str, Any] | None) -> str:
    if not isinstance(receipt, Mapping):
        return "none"
    for path in sorted((root / "source_impact_queue").glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict) and str(payload.get("supersession_receipt_id") or "") == str(receipt.get("supersession_receipt_id") or ""):
            return str(payload.get("status") or "unknown")
    return "none"


def _rule_fingerprint(rule_id: str, root: Path) -> str | None:
    rule = _load_rule_record(root, rule_id)
    return _hash_payload(rule) if isinstance(rule, dict) else None


def _load_canonical_rule_index(root: Path) -> dict[str, Any]:
    payload = _read_json(_canonical_rule_index_path(root))
    return deepcopy(dict(payload)) if isinstance(payload, dict) else {"rule_ids": [], "active_rule_ids": [], "rule_fingerprints": {}}


def _index_with_rule(index: Mapping[str, Any], rule: Mapping[str, Any]) -> dict[str, Any]:
    rule_id = str(rule.get("rule_id") or "")
    rule_ids = sorted({str(item) for item in index.get("rule_ids", [])} | {rule_id})
    active_ids = {str(item) for item in index.get("active_rule_ids", [])}
    if str(rule.get("status") or "") == "active":
        active_ids.add(rule_id)
    else:
        active_ids.discard(rule_id)
    fingerprints = {str(key): str(value) for key, value in dict(index.get("rule_fingerprints", {})).items()}
    fingerprints[rule_id] = str(rule.get("rule_fingerprint") or _rule_fingerprint_from_payload(rule))
    return {
        "schema_version": (index.get("schema_version") or "canonical_rule_index_v1"),
        "rule_ids": rule_ids,
        "active_rule_ids": sorted(active_ids),
        "rule_fingerprints": fingerprints,
        "updated_at_utc": _now(),
    }


def _update_review_index(root: Path) -> None:
    items = []
    for path in sorted((root / SUPERSESSION_REVIEW_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict):
            items.append(
                {
                    "supersession_review_id": payload.get("supersession_review_id"),
                    "old_rule_id": payload.get("old_rule_id"),
                    "replacement_proposal_id": payload.get("replacement_proposal_id"),
                    "review_status": payload.get("review_status"),
                    "candidate_rule_id": payload.get("candidate_rule_id"),
                    "updated_at_utc": payload.get("updated_at_utc"),
                }
            )
    _atomic_write_json(_review_index_path(root), {"schema_version": "rule_supersession_review_index_v1", "items": items, "updated_at_utc": _now()})


def _update_chain_index(root: Path) -> None:
    items = []
    for path in sorted((root / SUPERSESSION_CHAIN_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict):
            items.append(
                {
                    "version_chain_id": payload.get("version_chain_id"),
                    "root_rule_id": payload.get("root_rule_id"),
                    "current_active_rule_id": payload.get("current_active_rule_id"),
                    "chain_revision": payload.get("chain_revision"),
                    "updated_at_utc": payload.get("updated_at_utc"),
                }
            )
    _atomic_write_json(_chain_index_path(root), {"schema_version": "rule_supersession_chain_index_v1", "items": items, "updated_at_utc": _now()})


def _update_receipt_index(root: Path) -> None:
    items = []
    for path in sorted((root / SUPERSESSION_RECEIPT_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict):
            items.append(
                {
                    "supersession_receipt_id": payload.get("supersession_receipt_id"),
                    "supersession_review_id": payload.get("supersession_review_id"),
                    "old_rule_id": payload.get("old_rule_id"),
                    "new_rule_id": payload.get("new_rule_id"),
                    "version_chain_id": payload.get("version_chain_id"),
                    "supersession_status": payload.get("supersession_status"),
                    "created_at_utc": payload.get("created_at_utc"),
                }
            )
    _atomic_write_json(_receipt_index_path(root), {"schema_version": "rule_supersession_receipt_index_v1", "items": items, "updated_at_utc": _now()})


def _update_queue_index(root: Path) -> None:
    queue_dir = root / "source_impact_queue"
    items = []
    if queue_dir.exists():
        for path in sorted(queue_dir.glob("*.json")):
            payload = _read_json(path)
            if isinstance(payload, dict):
                items.append(
                    {
                        "queue_item_id": payload.get("queue_item_id"),
                        "status": payload.get("status"),
                        "reason": payload.get("reason"),
                        "rule_id": payload.get("rule_id"),
                        "supersession_receipt_id": payload.get("supersession_receipt_id"),
                    }
                )
    _atomic_write_json(root / "indexes" / QUEUE_INDEX, {"schema_version": "source_impact_queue_index_v1", "items": items, "updated_at_utc": _now()})


def _rollback_paths(write_targets: Mapping[Path, Any]) -> bool:
    try:
        for path, payload in write_targets.items():
            _restore_json(path, payload)
        return True
    except Exception:
        return False


def _review_path(root: Path, review_id: str) -> Path:
    return root / SUPERSESSION_REVIEW_DIR / f"{_safe_id(review_id)}.json"


def _chain_path(root: Path, chain_id: str) -> Path:
    return root / SUPERSESSION_CHAIN_DIR / f"{_safe_id(chain_id)}.json"


def _receipt_path(root: Path, receipt_id: str) -> Path:
    return root / SUPERSESSION_RECEIPT_DIR / f"{_safe_id(receipt_id)}.json"


def _backup_path(root: Path, receipt_id: str, rule_id: str) -> Path:
    return root / SUPERSESSION_BACKUP_DIR / f"{_safe_id(receipt_id)}__{_safe_id(rule_id)}.json"


def _queue_path(root: Path, queue_item_id: str) -> Path:
    return root / "source_impact_queue" / f"{_safe_id(queue_item_id)}.json"


def _rule_path(root: Path, rule_id: str) -> Path:
    return root / CANONICAL_RULE_DIR / f"{_safe_id(rule_id)}.json"


def _canonical_rule_index_path(root: Path) -> Path:
    return root / "indexes" / CANONICAL_RULE_INDEX


def _review_index_path(root: Path) -> Path:
    return root / "indexes" / SUPERSESSION_REVIEW_INDEX


def _chain_index_path(root: Path) -> Path:
    return root / "indexes" / SUPERSESSION_CHAIN_INDEX


def _receipt_index_path(root: Path) -> Path:
    return root / "indexes" / SUPERSESSION_RECEIPT_INDEX


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(dict(payload), handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            pass
    os.replace(temp_path, path)


def _restore_json(path: Path, payload: Any) -> None:
    if payload is None:
        if path.exists():
            path.unlink()
        return
    _atomic_write_json(path, payload)


def _hash_payload(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _rule_fingerprint_from_payload(payload: Mapping[str, Any]) -> str:
    fingerprint_fields = {
        "schema_version": payload.get("schema_version"),
        "rule_id": payload.get("rule_id"),
        "rule_type": payload.get("rule_type") or payload.get("rule_family"),
        "target": payload.get("target"),
        "scope": payload.get("scope"),
        "condition": payload.get("condition"),
        "operator": payload.get("operator"),
        "value": payload.get("value"),
        "priority": payload.get("priority"),
        "enabled": payload.get("enabled"),
        "status": payload.get("status"),
        "source_proposal_id": payload.get("source_proposal_id"),
        "source_promotion_receipt_id": payload.get("source_promotion_receipt_id"),
        "source_revision": payload.get("source_revision"),
    }
    return _hash_payload(fingerprint_fields)


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"_", "-", "."} else "_" for char in str(value).strip()) or "object"


def _non_empty_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in values if str(item)))


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
