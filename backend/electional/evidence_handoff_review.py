"""Controlled review and completion flow for pending citation evidence handoffs."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from .citation_draft_review import (
    HANDOFF_DIR,
    HANDOFF_INDEX,
    _atomic_write_json,
    _ensure_review_dirs,
    _handoff_path,
    _hash_payload,
    _load_handoffs,
    _now,
    _read_json,
    _restore_json,
)
from .document_manifest import calculate_document_revision_state, validate_source_locator
from .evidence_binder import _binder_path, _linked_citation_item, _update_evidence_binder_index, ensure_evidence_binder_dirs
from .pdf_viewport import _blocked
from .source_documents import SOURCE_DOCUMENT_ROOT, load_source_document
from .source_impact_analysis import (
    QUEUE_INDEX,
    _queue_item_path,
    _update_queue_index,
    ensure_source_impact_dirs,
    list_source_revalidation_queue,
)
from .source_knowledge import _proposal_path, _update_proposal_index, ensure_source_knowledge_dirs

REVIEW_DIR = "evidence_handoff_reviews"
REVIEW_INDEX = "evidence_handoff_review_index.json"
REVIEW_SCHEMA_VERSION = "evidence_handoff_review_v1"
ALLOWED_DECISIONS = {"approve_binder_insert", "approve_proposal_draft", "defer", "reject"}
ALLOWED_HANDOFF_STATUSES = {
    "pending_evidence_review",
    "approved_for_binder",
    "approved_for_proposal",
    "deferred",
    "rejected",
    "completed",
    "blocked",
    "stale",
}
HEALTH_STATUSES = {"healthy", "warning", "blocked", "stale", "corrupt", "empty", "unknown"}


def build_evidence_handoff_review_workspace(evidence_handoff_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = _ensure_handoff_review_dirs(root)
    handoff = _load_handoff(base, evidence_handoff_id)
    if handoff is None:
        return {"evidence_handoff_id": evidence_handoff_id, "status": "not_found", "warnings": ["evidence_handoff_not_found"]}
    validation = validate_evidence_handoff(evidence_handoff_id, root=base)
    review = _load_review_for_handoff(base, evidence_handoff_id)
    candidates = find_evidence_handoff_binder_candidates(evidence_handoff_id, root=base)
    proposals = _existing_proposals_for_handoff(base, handoff)
    revalidations = _revalidation_items_for_handoff(base, evidence_handoff_id)
    blockers = list(dict.fromkeys(validation.get("blockers", [])))
    warnings = list(dict.fromkeys([*validation.get("warnings", []), *candidates.get("warnings", [])]))
    return {
        "evidence_handoff_id": evidence_handoff_id,
        "citation_id": handoff.get("citation_id"),
        "document_id": handoff.get("document_id"),
        "source_revision": handoff.get("source_revision"),
        "handoff_status": handoff.get("status"),
        "review_id": review.get("review_id") if review else None,
        "review_status": (review or {}).get("review_status", "pending"),
        "provenance_status": "valid" if validation.get("valid") else "invalid",
        "binder_candidate_count": candidates.get("candidate_count", 0),
        "existing_proposal_count": len(proposals),
        "pending_revalidation_count": len(revalidations),
        "selected_binder_id": (review or {}).get("target_binder_id"),
        "completed_action": handoff.get("completed_action"),
        "binder_id": handoff.get("binder_id"),
        "proposal_id": handoff.get("proposal_id"),
        "revalidation_id": handoff.get("revalidation_id"),
        "warnings": warnings,
        "blockers": blockers,
        "recommended_action": _recommended_action(handoff, validation, candidates, proposals),
    }


def validate_evidence_handoff(evidence_handoff_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = _ensure_handoff_review_dirs(root)
    handoff = _load_handoff(base, evidence_handoff_id)
    if handoff is None:
        return {"evidence_handoff_id": evidence_handoff_id, "valid": False, "warnings": [], "blockers": ["evidence_handoff_not_found"]}
    blockers: list[str] = []
    warnings: list[str] = []
    if handoff.get("schema_version") != "citation_evidence_handoff_v1":
        blockers.append("handoff_schema_unsupported")
    if str(handoff.get("status") or "") not in ALLOWED_HANDOFF_STATUSES:
        blockers.append("handoff_status_invalid")
    citation = _load_citation(base, str(handoff.get("citation_id") or ""))
    if citation is None:
        blockers.append("citation_missing")
    document_id = str(handoff.get("document_id") or "")
    current_revision = calculate_document_revision_state(document_id, root=base).get("source_revision") if document_id else None
    if current_revision is None:
        blockers.append("source_revision_unavailable")
    elif citation and citation.get("source_revision") != current_revision:
        blockers.append("source_revision_changed")
    if citation:
        if str(citation.get("citation_id") or "") != str(handoff.get("citation_id") or ""):
            blockers.append("handoff_citation_mismatch")
        if str(citation.get("document_id") or "") != document_id:
            blockers.append("citation_document_mismatch")
        if citation.get("source_workspace_id") != handoff.get("source_workspace_id"):
            blockers.append("workspace_provenance_mismatch")
        if citation.get("source_citation_draft_id") != handoff.get("source_citation_draft_id"):
            blockers.append("draft_provenance_mismatch")
        if citation.get("source_review_id") != handoff.get("source_review_id"):
            blockers.append("review_provenance_mismatch")
        locator_validation = validate_source_locator(_citation_locator(citation), root=base)
        if not locator_validation.get("valid"):
            blockers.extend(locator_validation.get("blockers", []))
        if citation.get("selected_text_hash") in {None, ""}:
            blockers.append("selected_text_hash_missing")
    else:
        locator_validation = {"valid": False}
    if handoff.get("status") == "completed":
        completed_actions = [name for name in ("binder_insert", "proposal_draft") if handoff.get("completed_action") == name]
        if len(completed_actions) != 1:
            blockers.append("completed_action_invalid")
    return {
        "evidence_handoff_id": evidence_handoff_id,
        "valid": not blockers,
        "citation_id": handoff.get("citation_id"),
        "document_id": document_id,
        "source_revision_current": citation is not None and citation.get("source_revision") == current_revision,
        "locator_valid": bool(locator_validation.get("valid")),
        "warnings": list(dict.fromkeys(warnings)),
        "blockers": list(dict.fromkeys(blockers)),
    }


def find_evidence_handoff_binder_candidates(
    evidence_handoff_id: str,
    limit: int = 25,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_handoff_review_dirs(root)
    handoff = _load_handoff(base, evidence_handoff_id)
    if handoff is None:
        return {"evidence_handoff_id": evidence_handoff_id, "candidate_count": 0, "candidates": [], "warnings": ["evidence_handoff_not_found"]}
    citation = _load_citation(base, str(handoff.get("citation_id") or ""))
    if citation is None:
        return {"evidence_handoff_id": evidence_handoff_id, "candidate_count": 0, "candidates": [], "warnings": ["citation_missing"]}
    document_id = str(handoff.get("document_id") or "")
    handoff_tags = {str(item).strip().lower() for item in handoff.get("topic_tags", []) if str(item).strip()}
    candidates = []
    for path in sorted((base / "evidence_binders").glob("*.json")):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        linked = [item for item in payload.get("linked_citations", []) if isinstance(item, Mapping)]
        binder_id = str(payload.get("binder_id") or path.stem)
        binder_status = str(payload.get("binder_status") or "active")
        if binder_status == "not_built":
            continue
        reasons: list[str] = []
        citation_ids = {str(item.get("citation_id") or "") for item in linked}
        linked_document_ids = {str(item.get("document_id") or "") for item in linked}
        if str(citation.get("citation_id") or "") in citation_ids:
            reasons.extend(["same_document", "existing_document_citations"])
        elif document_id in linked_document_ids:
            reasons.extend(["same_document", "existing_document_citations"])
        source_scope = payload.get("source_scope", {})
        if isinstance(source_scope, Mapping) and document_id in {str(item) for item in source_scope.get("document_ids", []) if item}:
            reasons.append("same_document_source_scope")
        binder_topics = {str(item).strip().lower() for item in payload.get("topic_tags", []) if str(item).strip()}
        if handoff_tags and binder_topics.intersection(handoff_tags):
            reasons.append("exact_controlled_topic_match")
        if not reasons:
            continue
        candidates.append(
            {
                "binder_id": binder_id,
                "candidate_reason": list(dict.fromkeys(reasons)),
                "citation_already_present": str(citation.get("citation_id") or "") in citation_ids,
                "binder_status": binder_status,
                "warnings": [],
            }
        )
    candidates.sort(
        key=lambda item: (
            0 if item.get("citation_already_present") else 1,
            0 if "same_document" in item.get("candidate_reason", []) else 1,
            0 if "exact_controlled_topic_match" in item.get("candidate_reason", []) else 1,
            str(item.get("binder_id") or ""),
        )
    )
    limited = candidates[: max(0, int(limit or 0))]
    return {"evidence_handoff_id": evidence_handoff_id, "candidate_count": len(limited), "candidates": limited, "warnings": []}


def save_evidence_handoff_review_decision(
    evidence_handoff_id: str,
    decision: str,
    target_binder_id: str | None = None,
    reviewer_note: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    if decision not in ALLOWED_DECISIONS:
        raise ValueError(f"Unsupported handoff decision: {decision}")
    base = _ensure_handoff_review_dirs(root)
    handoff = _load_handoff(base, evidence_handoff_id)
    if handoff is None:
        raise FileNotFoundError(evidence_handoff_id)
    validation = validate_evidence_handoff(evidence_handoff_id, root=base)
    if validation.get("blockers"):
        return _blocked("handoff_invalid", blockers=validation.get("blockers"))
    if handoff.get("status") == "completed":
        return _blocked("handoff_completed", blockers=["handoff_already_completed"])
    binder_id = str(target_binder_id or "").strip() or None
    note = str(reviewer_note or "").strip() or None
    existing_review = _load_review_for_handoff(base, evidence_handoff_id)
    proposals = _existing_proposals_for_handoff(base, handoff)
    blockers: list[str] = []
    if decision == "approve_binder_insert":
        if not binder_id:
            blockers.append("target_binder_id_required")
        else:
            binder_check = _validate_target_binder(base, handoff, binder_id)
            blockers.extend(binder_check.get("blockers", []))
    elif decision == "approve_proposal_draft":
        if proposals:
            blockers.append("proposal_for_handoff_already_exists")
    else:
        if not note:
            blockers.append("reviewer_note_required")
    if blockers:
        return _blocked("decision_blocked", blockers=blockers)
    review_id = (existing_review or {}).get("review_id") or _review_id(evidence_handoff_id)
    payload = {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "review_id": review_id,
        "evidence_handoff_id": evidence_handoff_id,
        "citation_id": handoff.get("citation_id"),
        "document_id": handoff.get("document_id"),
        "source_revision": handoff.get("source_revision"),
        "decision": decision,
        "target_binder_id": binder_id,
        "review_status": "approved" if decision.startswith("approve_") else "deferred" if decision == "defer" else "rejected",
        "review_revision": int((existing_review or {}).get("review_revision") or 0),
        "reviewer_note": note,
        "provenance_snapshot": validation,
        "created_at_utc": (existing_review or {}).get("created_at_utc") or _now(),
        "updated_at_utc": _now(),
        "warnings": [],
    }
    status_map = {
        "approve_binder_insert": "approved_for_binder",
        "approve_proposal_draft": "approved_for_proposal",
        "defer": "deferred",
        "reject": "rejected",
    }
    updated_handoff = dict(handoff)
    updated_handoff["status"] = status_map[decision]
    updated_handoff["updated_at_utc"] = _now()
    updated_handoff["candidate_binder_ids"] = [item.get("binder_id") for item in find_evidence_handoff_binder_candidates(evidence_handoff_id, root=base).get("candidates", [])]
    updated_handoff["candidate_proposal_ids"] = [item.get("proposal_id") for item in proposals]
    if decision.startswith("approve_"):
        updated_handoff["approved_action"] = "binder_insert" if decision == "approve_binder_insert" else "proposal_draft"
        if binder_id:
            updated_handoff["approved_binder_id"] = binder_id
    if existing_review and _same_review_state(existing_review, payload) and _same_handoff_state(handoff, updated_handoff):
        return {"status": "saved", "review": existing_review, "writes_performed": 0}
    payload["review_revision"] = int((existing_review or {}).get("review_revision") or 0) + 1
    review_path = _review_path(base, review_id)
    before_review = _read_json(review_path)
    before_handoff = _read_json(_handoff_path(base, evidence_handoff_id))
    before_index = _read_json(base / "indexes" / REVIEW_INDEX)
    try:
        _atomic_write_json(review_path, payload)
        _atomic_write_json(_handoff_path(base, evidence_handoff_id), updated_handoff)
        _update_review_index(base)
    except Exception:
        _restore_json(review_path, before_review)
        _restore_json(_handoff_path(base, evidence_handoff_id), before_handoff)
        _restore_json(base / "indexes" / REVIEW_INDEX, before_index)
        return {"status": "failed_rolled_back", "classification": "review_write_failure", "warnings": []}
    return {"status": "saved", "review": payload, "handoff_status": updated_handoff["status"], "writes_performed": 2}


def insert_handoff_citation_into_binder(review_id: str, confirmation: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    if confirmation != "INSERT":
        return _blocked("insert_confirmation_required", blockers=["insert_confirmation_required"])
    base = _ensure_handoff_review_dirs(root)
    review = _load_review_by_id(base, review_id)
    if review is None:
        raise FileNotFoundError(review_id)
    handoff = _load_handoff(base, str(review.get("evidence_handoff_id") or ""))
    citation = _load_citation(base, str(review.get("citation_id") or ""))
    if handoff is None or citation is None:
        return _blocked("handoff_invalid", blockers=["handoff_or_citation_missing"])
    validation = validate_evidence_handoff(str(review.get("evidence_handoff_id") or ""), root=base)
    if validation.get("blockers"):
        return _blocked("handoff_invalid", blockers=validation.get("blockers"))
    if review.get("decision") != "approve_binder_insert":
        return _blocked("review_decision_invalid", blockers=["review_not_approved_for_binder_insert"])
    binder_id = str(review.get("target_binder_id") or "")
    proposal_id = binder_id.replace("binder_", "", 1)
    binder_path = _binder_path(base, proposal_id)
    binder = _read_json(binder_path)
    if not isinstance(binder, dict):
        return _blocked("binder_invalid", blockers=["binder_unreadable"])
    linked = [item for item in binder.get("linked_citations", []) if isinstance(item, Mapping)]
    linked_document_ids = {str(item.get("document_id") or "") for item in linked}
    if str(handoff.get("document_id") or "") not in linked_document_ids:
        return _blocked("binder_invalid", blockers=["binder_document_scope_incompatible"])
    citation_id = str(citation.get("citation_id") or "")
    already_present = any(str(item.get("citation_id") or "") == citation_id for item in linked)
    existing_revalidation = _existing_revalidation_for_action(base, str(review.get("evidence_handoff_id") or ""), "binder_insert")
    if already_present:
        if handoff.get("status") == "completed" and handoff.get("completed_action") == "binder_insert" and handoff.get("binder_id") == binder_id and review.get("review_status") == "completed" and existing_revalidation:
            return {
                "status": "already_inserted",
                "review_id": review_id,
                "evidence_handoff_id": handoff.get("evidence_handoff_id"),
                "citation_id": citation_id,
                "binder_id": binder_id,
                "revalidation_id": existing_revalidation.get("queue_item_id"),
                "writes_performed": 0,
            }
        return _blocked("binder_handoff_state_diverged", blockers=["binder_handoff_state_diverged"])
    updated_binder = deepcopy(binder)
    updated_binder["linked_citations"] = list(linked) + [_linked_citation_item(citation, base)]
    updated_binder["updated_at_utc"] = _now()
    updated_handoff = dict(handoff)
    updated_handoff.update(
        {
            "status": "completed",
            "completed_action": "binder_insert",
            "binder_id": binder_id,
            "proposal_id": None,
            "updated_at_utc": _now(),
            "completed_at_utc": _now(),
        }
    )
    updated_review = dict(review)
    updated_review["review_status"] = "completed"
    updated_review["updated_at_utc"] = _now()
    revalidation = _build_revalidation_record(base, handoff, review, "binder_insert", binder_id=binder_id)
    updated_handoff["revalidation_id"] = revalidation["queue_item_id"]
    updated_review["revalidation_id"] = revalidation["queue_item_id"]
    updated_review["binder_id"] = binder_id
    write_targets = {
        binder_path: _read_json(binder_path),
        base / "indexes" / "evidence_binder_index.json": _read_json(base / "indexes" / "evidence_binder_index.json"),
        _handoff_path(base, str(handoff.get("evidence_handoff_id") or "")): _read_json(_handoff_path(base, str(handoff.get("evidence_handoff_id") or ""))),
        _review_path(base, review_id): _read_json(_review_path(base, review_id)),
        _queue_item_path(base, revalidation["queue_item_id"]): _read_json(_queue_item_path(base, revalidation["queue_item_id"])),
        base / "indexes" / QUEUE_INDEX: _read_json(base / "indexes" / QUEUE_INDEX),
    }
    try:
        _atomic_write_json(binder_path, updated_binder)
        _update_evidence_binder_index(base)
        _atomic_write_json(_handoff_path(base, str(handoff.get("evidence_handoff_id") or "")), updated_handoff)
        _atomic_write_json(_review_path(base, review_id), updated_review)
        _atomic_write_json(_queue_item_path(base, revalidation["queue_item_id"]), revalidation)
        _update_queue_index(base)
    except Exception:
        rollback = _rollback_write_targets(write_targets)
        return {"status": "rollback_failed" if not rollback else "failed_rolled_back", "classification": "revalidation_creation_failure" if rollback else "critical_recovery_failure", "records_restored": len(write_targets), "rollback_verified": rollback, "warnings": []}
    return {
        "status": "inserted",
        "review_id": review_id,
        "evidence_handoff_id": handoff.get("evidence_handoff_id"),
        "citation_id": citation_id,
        "binder_id": binder_id,
        "revalidation_id": revalidation["queue_item_id"],
        "handoff_status": "completed",
        "warnings": [],
    }


def create_proposal_draft_from_evidence_handoff(review_id: str, confirmation: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    if confirmation != "DRAFT":
        return _blocked("draft_confirmation_required", blockers=["draft_confirmation_required"])
    base = _ensure_handoff_review_dirs(root)
    review = _load_review_by_id(base, review_id)
    if review is None:
        raise FileNotFoundError(review_id)
    handoff = _load_handoff(base, str(review.get("evidence_handoff_id") or ""))
    citation = _load_citation(base, str(review.get("citation_id") or ""))
    if handoff is None or citation is None:
        return _blocked("handoff_invalid", blockers=["handoff_or_citation_missing"])
    validation = validate_evidence_handoff(str(review.get("evidence_handoff_id") or ""), root=base)
    if validation.get("blockers"):
        return _blocked("handoff_invalid", blockers=validation.get("blockers"))
    if review.get("decision") != "approve_proposal_draft":
        return _blocked("review_decision_invalid", blockers=["review_not_approved_for_proposal_draft"])
    existing_proposals = _existing_proposals_for_handoff(base, handoff)
    if existing_proposals:
        proposal = existing_proposals[0]
        if handoff.get("status") == "completed" and handoff.get("completed_action") == "proposal_draft" and review.get("review_status") == "completed":
            existing_revalidation = _existing_revalidation_for_action(base, str(handoff.get("evidence_handoff_id") or ""), "proposal_draft")
            return {
                "status": "already_created",
                "review_id": review_id,
                "evidence_handoff_id": handoff.get("evidence_handoff_id"),
                "citation_id": citation.get("citation_id"),
                "proposal_id": proposal.get("proposal_id"),
                "revalidation_id": (existing_revalidation or {}).get("queue_item_id"),
                "writes_performed": 0,
            }
        return _blocked("proposal_already_exists", blockers=["proposal_for_handoff_already_exists"])
    proposal = _build_proposal_record(handoff, review, citation)
    proposal_path = _proposal_path(base, str(proposal.get("proposal_id") or ""))
    updated_handoff = dict(handoff)
    updated_handoff.update(
        {
            "status": "completed",
            "completed_action": "proposal_draft",
            "proposal_id": proposal.get("proposal_id"),
            "binder_id": None,
            "updated_at_utc": _now(),
            "completed_at_utc": _now(),
        }
    )
    updated_review = dict(review)
    updated_review["review_status"] = "completed"
    updated_review["proposal_id"] = proposal.get("proposal_id")
    updated_review["updated_at_utc"] = _now()
    revalidation = _build_revalidation_record(base, handoff, review, "proposal_draft", proposal_id=str(proposal.get("proposal_id") or ""))
    updated_handoff["revalidation_id"] = revalidation["queue_item_id"]
    updated_review["revalidation_id"] = revalidation["queue_item_id"]
    write_targets = {
        proposal_path: _read_json(proposal_path),
        base / "indexes" / "proposal_index.json": _read_json(base / "indexes" / "proposal_index.json"),
        _handoff_path(base, str(handoff.get("evidence_handoff_id") or "")): _read_json(_handoff_path(base, str(handoff.get("evidence_handoff_id") or ""))),
        _review_path(base, review_id): _read_json(_review_path(base, review_id)),
        _queue_item_path(base, revalidation["queue_item_id"]): _read_json(_queue_item_path(base, revalidation["queue_item_id"])),
        base / "indexes" / QUEUE_INDEX: _read_json(base / "indexes" / QUEUE_INDEX),
    }
    try:
        _atomic_write_json(proposal_path, proposal)
        _update_proposal_index(base)
        _atomic_write_json(_handoff_path(base, str(handoff.get("evidence_handoff_id") or "")), updated_handoff)
        _atomic_write_json(_review_path(base, review_id), updated_review)
        _atomic_write_json(_queue_item_path(base, revalidation["queue_item_id"]), revalidation)
        _update_queue_index(base)
    except Exception:
        rollback = _rollback_write_targets(write_targets)
        return {"status": "rollback_failed" if not rollback else "failed_rolled_back", "classification": "revalidation_creation_failure" if rollback else "critical_recovery_failure", "records_restored": len(write_targets), "rollback_verified": rollback, "warnings": []}
    return {
        "status": "proposal_draft_created",
        "review_id": review_id,
        "evidence_handoff_id": handoff.get("evidence_handoff_id"),
        "citation_id": citation.get("citation_id"),
        "proposal_id": proposal.get("proposal_id"),
        "proposal_status": proposal.get("status"),
        "revalidation_id": revalidation["queue_item_id"],
        "handoff_status": "completed",
        "warnings": [],
    }


def get_evidence_handoff_review_health(document_id: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = _ensure_handoff_review_dirs(root)
    reviews = _load_reviews(base)
    handoffs = [item for item in _load_handoffs(base) if isinstance(item, Mapping)]
    if document_id:
        reviews = [item for item in reviews if item.get("document_id") == document_id]
        handoffs = [item for item in handoffs if item.get("document_id") == document_id]
    if not reviews and not handoffs:
        return {"status": "empty", "review_count": 0, "pending_handoff_count": 0, "deferred_handoff_count": 0, "completed_binder_count": 0, "completed_proposal_count": 0, "missing_revalidation_count": 0, "divergent_state_count": 0, "warnings": [], "recommended_action": "Create or load an evidence handoff review."}
    warnings: list[str] = []
    missing_revalidation = 0
    divergent = 0
    completed_binder = 0
    completed_proposal = 0
    review_ids_by_handoff: dict[str, int] = {}
    for review in reviews:
        review_ids_by_handoff[str(review.get("evidence_handoff_id") or "")] = review_ids_by_handoff.get(str(review.get("evidence_handoff_id") or ""), 0) + 1
    for handoff in handoffs:
        if handoff.get("status") == "completed":
            if handoff.get("completed_action") == "binder_insert":
                completed_binder += 1
                binder_check = _validate_completed_binder_action(base, handoff)
                if binder_check != "ok":
                    divergent += 1
            elif handoff.get("completed_action") == "proposal_draft":
                completed_proposal += 1
                proposal_check = _validate_completed_proposal_action(base, handoff)
                if proposal_check != "ok":
                    divergent += 1
            else:
                divergent += 1
            if not _existing_revalidation_for_any_action(base, str(handoff.get("evidence_handoff_id") or "")):
                missing_revalidation += 1
        elif handoff.get("status") == "deferred":
            warnings.append("one_handoff_is_deferred")
    duplicates = sum(1 for count in review_ids_by_handoff.values() if count > 1)
    if duplicates:
        warnings.append("duplicate_reviews_present")
    status = "healthy"
    if divergent:
        status = "blocked"
    elif missing_revalidation:
        status = "warning"
    elif any(item.get("status") == "stale" for item in handoffs):
        status = "stale"
    return {
        "status": status if status in HEALTH_STATUSES else "unknown",
        "review_count": len(reviews),
        "pending_handoff_count": sum(1 for item in handoffs if item.get("status") == "pending_evidence_review"),
        "deferred_handoff_count": sum(1 for item in handoffs if item.get("status") == "deferred"),
        "completed_binder_count": completed_binder,
        "completed_proposal_count": completed_proposal,
        "missing_revalidation_count": missing_revalidation,
        "divergent_state_count": divergent + duplicates,
        "warnings": list(dict.fromkeys(warnings)),
        "recommended_action": "Review one deferred evidence handoff." if any(item.get("status") == "deferred" for item in handoffs) else "Review divergent evidence handoff state." if divergent else "Evidence handoff reviews are healthy.",
    }


def format_evidence_handoff_review_report(
    evidence_handoff_id: str | None = None,
    review_id: str | None = None,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    base = _ensure_handoff_review_dirs(root)
    handoff = _load_handoff(base, evidence_handoff_id) if evidence_handoff_id else None
    review = _load_review_by_id(base, review_id) if review_id else None
    if handoff is None and review is not None:
        handoff = _load_handoff(base, str(review.get("evidence_handoff_id") or ""))
    if review is None and handoff is not None:
        review = _load_review_for_handoff(base, str(handoff.get("evidence_handoff_id") or ""))
    if handoff is None:
        return "Evidence Handoff Review Report\n\nStatus: not_found"
    validation = validate_evidence_handoff(str(handoff.get("evidence_handoff_id") or ""), root=base)
    workspace = build_evidence_handoff_review_workspace(str(handoff.get("evidence_handoff_id") or ""), root=base)
    lines = [
        "Evidence Handoff Review Report",
        "",
        f"Document: {handoff.get('document_id')}",
        f"Source Revision: {handoff.get('source_revision')}",
        f"Handoff Status: {handoff.get('status')}",
        "",
        "Citation:",
        f"- Citation ID: {handoff.get('citation_id')}",
        f"- Provenance: {'valid' if validation.get('valid') else 'invalid'}",
        "",
        "Review:",
        f"- Decision: {(review or {}).get('decision', 'not_decided')}",
        f"- Review Status: {(review or {}).get('review_status', 'pending')}",
        "",
        "Evidence Action:",
        f"- Type: {handoff.get('completed_action') or handoff.get('approved_action') or 'none'}",
        f"- Binder ID: {handoff.get('binder_id') or (review or {}).get('target_binder_id') or 'none'}",
        f"- Proposal ID: {handoff.get('proposal_id') or 'none'}",
        f"- Citation Inserted: {'Yes' if handoff.get('completed_action') == 'binder_insert' else 'No'}",
        "",
        "Revalidation:",
        f"- Status: {'pending_review' if handoff.get('revalidation_id') else 'none'}",
        "",
        "Important:",
        "The citation was inserted only after explicit handoff review and INSERT confirmation." if handoff.get("completed_action") == "binder_insert" else "The proposal draft was created only after explicit handoff review and DRAFT confirmation." if handoff.get("completed_action") == "proposal_draft" else "No evidence action has been executed yet.",
        "No proposal was promoted.",
        "",
        "Recommended Action:",
        workspace.get("recommended_action") or "Review the pending revalidation item.",
    ]
    text = "\n".join(lines)
    if public_safe:
        for needle in ("C:\\", "/Users/", "Traceback", "token=", "secret", "reviewer_note", "selected_text", "quote_excerpt"):
            text = text.replace(needle, "[redacted]")
    return text


def _ensure_handoff_review_dirs(root: Path | str) -> Path:
    base = _ensure_review_dirs(root)
    ensure_evidence_binder_dirs(base)
    ensure_source_knowledge_dirs(base)
    ensure_source_impact_dirs(base)
    (base / REVIEW_DIR).mkdir(parents=True, exist_ok=True)
    index_path = base / "indexes" / REVIEW_INDEX
    if not index_path.exists():
        _atomic_write_json(index_path, {"entries": [], "updated_at_utc": _now()})
    return base


def _load_handoff(root: Path, evidence_handoff_id: str | None) -> dict[str, object] | None:
    if not evidence_handoff_id:
        return None
    payload = _read_json(_handoff_path(root, evidence_handoff_id))
    return payload if isinstance(payload, dict) else None


def _load_citation(root: Path, citation_id: str) -> dict[str, object] | None:
    if not citation_id:
        return None
    payload = _read_json(root / "citations" / f"{citation_id}.json")
    return payload if isinstance(payload, dict) else None


def _load_reviews(root: Path) -> list[dict[str, object]]:
    items = []
    for path in sorted((root / REVIEW_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _load_review_for_handoff(root: Path, evidence_handoff_id: str) -> dict[str, object] | None:
    for payload in _load_reviews(root):
        if str(payload.get("evidence_handoff_id") or "") == evidence_handoff_id:
            return payload
    return None


def _load_review_by_id(root: Path, review_id: str) -> dict[str, object] | None:
    payload = _read_json(_review_path(root, review_id))
    return payload if isinstance(payload, dict) else None


def _review_path(root: Path, review_id: str) -> Path:
    return root / REVIEW_DIR / f"{review_id}.json"


def _review_id(evidence_handoff_id: str) -> str:
    return f"handoff_review_{_hash_payload({'evidence_handoff_id': evidence_handoff_id})[7:23]}"


def _update_review_index(root: Path) -> None:
    entries = []
    for item in _load_reviews(root):
        entries.append(
            {
                "review_id": item.get("review_id"),
                "evidence_handoff_id": item.get("evidence_handoff_id"),
                "citation_id": item.get("citation_id"),
                "document_id": item.get("document_id"),
                "decision": item.get("decision"),
                "review_status": item.get("review_status"),
                "updated_at_utc": item.get("updated_at_utc"),
            }
        )
    _atomic_write_json(root / "indexes" / REVIEW_INDEX, {"entries": entries, "updated_at_utc": _now()})


def _citation_locator(citation: Mapping[str, object]) -> dict[str, object]:
    locator = citation.get("locator")
    if isinstance(locator, Mapping):
        payload = dict(locator)
        if "page" in payload and "page_number" not in payload:
            payload["page_number"] = payload.get("page")
        if "start_offset" in payload and "character_start" not in payload:
            payload["character_start"] = payload.get("start_offset")
        if "end_offset" in payload and "character_end" not in payload:
            payload["character_end"] = payload.get("end_offset")
        return payload
    return {
        "document_id": citation.get("document_id"),
        "source_revision": citation.get("source_revision"),
        "chunk_id": citation.get("chunk_id"),
        "page_number": citation.get("page"),
        "character_start": citation.get("start_offset"),
        "character_end": citation.get("end_offset"),
    }


def _existing_proposals_for_handoff(root: Path, handoff: Mapping[str, object]) -> list[dict[str, object]]:
    items = []
    for path in sorted((root / "proposals").glob("*.json")):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        if payload.get("source_evidence_handoff_id") == handoff.get("evidence_handoff_id") or payload.get("source_citation_id") == handoff.get("citation_id"):
            items.append(payload)
    return items


def _revalidation_items_for_handoff(root: Path, evidence_handoff_id: str) -> list[dict[str, object]]:
    return [item for item in list_source_revalidation_queue(limit=500, root=root).get("items", []) if isinstance(item, dict) and item.get("evidence_handoff_id") == evidence_handoff_id]


def _existing_revalidation_for_action(root: Path, evidence_handoff_id: str, action_type: str) -> dict[str, object] | None:
    for item in _revalidation_items_for_handoff(root, evidence_handoff_id):
        if item.get("action_type") == action_type:
            return item
    return None


def _existing_revalidation_for_any_action(root: Path, evidence_handoff_id: str) -> dict[str, object] | None:
    items = _revalidation_items_for_handoff(root, evidence_handoff_id)
    return items[0] if items else None


def _recommended_action(handoff: Mapping[str, object], validation: Mapping[str, object], candidates: Mapping[str, object], proposals: list[dict[str, object]]) -> str:
    if validation.get("blockers"):
        return "Resolve evidence handoff blockers before taking action."
    if handoff.get("status") == "completed":
        return "Review the pending revalidation item."
    if candidates.get("candidate_count"):
        return "Select an existing binder or create a proposal draft."
    if proposals:
        return "Review the existing linked proposal draft."
    return "Create a proposal draft if no binder candidate fits."


def _validate_target_binder(root: Path, handoff: Mapping[str, object], binder_id: str) -> dict[str, object]:
    proposal_id = binder_id.replace("binder_", "", 1)
    binder = _read_json(_binder_path(root, proposal_id))
    if not isinstance(binder, dict):
        return {"blockers": ["target_binder_missing"]}
    linked = [item for item in binder.get("linked_citations", []) if isinstance(item, Mapping)]
    doc_ids = {str(item.get("document_id") or "") for item in linked}
    if str(handoff.get("document_id") or "") not in doc_ids:
        return {"blockers": ["binder_document_scope_incompatible"]}
    if any(str(item.get("citation_id") or "") == str(handoff.get("citation_id") or "") for item in linked):
        return {"blockers": ["citation_already_in_binder"], "proposal_id": proposal_id}
    return {"blockers": [], "proposal_id": proposal_id}


def _same_review_state(existing: Mapping[str, object], payload: Mapping[str, object]) -> bool:
    return all(existing.get(field) == payload.get(field) for field in ("decision", "target_binder_id", "review_status", "reviewer_note"))


def _same_handoff_state(existing: Mapping[str, object], payload: Mapping[str, object]) -> bool:
    return existing.get("status") == payload.get("status") and existing.get("approved_binder_id") == payload.get("approved_binder_id") and existing.get("approved_action") == payload.get("approved_action")


def _build_revalidation_record(
    root: Path,
    handoff: Mapping[str, object],
    review: Mapping[str, object],
    action_type: str,
    *,
    binder_id: str | None = None,
    proposal_id: str | None = None,
) -> dict[str, object]:
    queue_item_id = f"impact_{_hash_payload({'evidence_handoff_id': handoff.get('evidence_handoff_id'), 'action_type': action_type})[7:23]}"
    return {
        "queue_item_id": queue_item_id,
        "revalidation_id": queue_item_id,
        "document_id": handoff.get("document_id"),
        "change_type": "manual_review",
        "impact_severity": "medium",
        "status": "pending_review",
        "affected_counts": {"citations": 1, "proposals": 1 if proposal_id else 0, "proposal_reviews": 0, "evidence_binders": 1 if binder_id else 0},
        "created_at_utc": _now(),
        "updated_at_utc": _now(),
        "review_note": "Evidence handoff action requires downstream review.",
        "warnings": [],
        "dedupe_key": "sha256:" + _hash_payload({"evidence_handoff_id": handoff.get("evidence_handoff_id"), "action_type": action_type}),
        "source_revision": handoff.get("source_revision"),
        "citation_id": handoff.get("citation_id"),
        "evidence_handoff_id": handoff.get("evidence_handoff_id"),
        "handoff_review_id": review.get("review_id"),
        "binder_id": binder_id,
        "proposal_id": proposal_id,
        "reason": "evidence_handoff_action",
        "action_type": action_type,
    }


def _build_proposal_record(handoff: Mapping[str, object], review: Mapping[str, object], citation: Mapping[str, object]) -> dict[str, object]:
    claim_basis = str(citation.get("note") or citation.get("quote_excerpt") or "Citation evidence handoff draft").strip()
    claim = claim_basis[:240]
    proposal_id = f"proposal_{_hash_payload({'evidence_handoff_id': handoff.get('evidence_handoff_id'), 'citation_id': citation.get('citation_id')})[7:23]}"
    return {
        "proposal_id": proposal_id,
        "document_id": citation.get("document_id"),
        "chunk_id": citation.get("chunk_id"),
        "claim": claim,
        "proposed_condition": None,
        "proposed_effect": None,
        "proposal_type": "manual_note",
        "status": "draft",
        "created_by": "citation_evidence_handoff",
        "created_from": "citation_evidence_handoff",
        "created_at_utc": _now(),
        "updated_at_utc": _now(),
        "warnings": ["proposal_does_not_activate_rule"],
        "schema_version": "source_proposal_v1",
        "source_citation_id": citation.get("citation_id"),
        "source_evidence_handoff_id": handoff.get("evidence_handoff_id"),
        "source_handoff_review_id": review.get("review_id"),
        "source_revision": citation.get("source_revision"),
        "locator": _citation_locator(citation),
        "citation_reference": {"citation_id": citation.get("citation_id"), "document_id": citation.get("document_id"), "chunk_id": citation.get("chunk_id")},
    }


def _rollback_write_targets(write_targets: Mapping[Path, Any]) -> bool:
    before = {path: _hash_file(path) for path in write_targets}
    for path, payload in write_targets.items():
        _restore_json(path, payload)
    after = {path: _hash_file(path) for path in write_targets}
    return all(after[path] == before[path] for path in write_targets)


def _hash_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return _hash_payload(_read_json(path))


def _validate_completed_binder_action(root: Path, handoff: Mapping[str, object]) -> str:
    binder_id = str(handoff.get("binder_id") or "")
    proposal_id = binder_id.replace("binder_", "", 1)
    binder = _read_json(_binder_path(root, proposal_id))
    if not isinstance(binder, dict):
        return "missing_binder"
    linked = [item for item in binder.get("linked_citations", []) if isinstance(item, Mapping)]
    return "ok" if any(str(item.get("citation_id") or "") == str(handoff.get("citation_id") or "") for item in linked) else "citation_missing_from_binder"


def _validate_completed_proposal_action(root: Path, handoff: Mapping[str, object]) -> str:
    proposal = _read_json(_proposal_path(root, str(handoff.get("proposal_id") or "")))
    if not isinstance(proposal, dict):
        return "missing_proposal"
    return "ok" if proposal.get("source_evidence_handoff_id") == handoff.get("evidence_handoff_id") else "proposal_provenance_mismatch"
