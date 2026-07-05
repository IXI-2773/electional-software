"""Controlled promotion review and promotion receipts for Phase 9B proposal drafts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .citation_draft_review import _atomic_write_json, _hash_payload, _now, _read_json, _restore_json
from .document_manifest import calculate_document_revision_state, validate_source_locator
from .evidence_handoff_review import _existing_revalidation_for_any_action, _load_citation, _load_handoff, _load_review_by_id
from .pdf_viewport import _blocked
from .proposal_review import detect_duplicate_proposals, detect_proposal_conflicts, load_proposal_review
from .source_documents import SOURCE_DOCUMENT_ROOT
from .source_impact_analysis import QUEUE_INDEX, _queue_item_path, _update_queue_index, ensure_source_impact_dirs, list_source_revalidation_queue
from .source_knowledge import _proposal_path, _update_proposal_index, ensure_source_knowledge_dirs, list_source_proposals

PROMOTION_REVIEW_DIR = "proposal_promotion_reviews"
PROMOTION_RECEIPT_DIR = "proposal_promotion_receipts"
PROMOTION_REVIEW_INDEX = "proposal_promotion_review_index.json"
PROMOTION_RECEIPT_INDEX = "proposal_promotion_receipt_index.json"
PROMOTION_REVIEW_SCHEMA_VERSION = "proposal_promotion_review_v1"
PROMOTION_RECEIPT_SCHEMA_VERSION = "proposal_promotion_receipt_v1"
ALLOWED_DECISIONS = {"approve", "reject", "request_changes"}
HEALTH_STATUSES = {"healthy", "warning", "blocked", "stale", "corrupt", "empty", "unknown"}


def build_proposal_promotion_workspace(proposal_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = _ensure_promotion_dirs(root)
    proposal = _load_proposal(base, proposal_id)
    if proposal is None:
        return {"proposal_id": proposal_id, "status": "not_found", "warnings": ["proposal_not_found"]}
    provenance = validate_proposal_promotion_provenance(proposal_id, root=base)
    conflict = analyze_proposal_promotion_conflicts(proposal_id, root=base)
    review = load_proposal_promotion_review(proposal_id=proposal_id, root=base)
    receipt = _load_receipt_for_proposal(base, proposal_id)
    handoff = _load_handoff(base, str(proposal.get("source_evidence_handoff_id") or ""))
    revalidation = _matching_revalidation(base, proposal)
    existing_review = load_proposal_review(proposal_id, root=base, missing_ok=True)
    return {
        "proposal_id": proposal_id,
        "document_id": proposal.get("document_id"),
        "source_revision": proposal.get("source_revision"),
        "proposal_status": proposal.get("status"),
        "promotion_review_status": (review or {}).get("review_status", "pending"),
        "promotion_review_id": (review or {}).get("promotion_review_id"),
        "citation_id": proposal.get("source_citation_id"),
        "citation_provenance_status": "valid" if provenance.get("citation_valid") else "invalid",
        "handoff_status": (handoff or {}).get("status"),
        "handoff_action": (handoff or {}).get("completed_action"),
        "duplicate_status": conflict.get("duplicate_status"),
        "conflict_status": conflict.get("conflict_status"),
        "revalidation_status": (revalidation or {}).get("status"),
        "promotion_receipt_id": (receipt or {}).get("promotion_receipt_id"),
        "proposal_review_status": getattr(existing_review, "review_status", None) if existing_review else None,
        "warnings": list(dict.fromkeys([*provenance.get("warnings", []), *conflict.get("warnings", [])])),
        "blockers": list(dict.fromkeys([*provenance.get("blockers", []), *conflict.get("blockers", [])])),
        "recommended_action": "Review the proposal for controlled promotion." if not provenance.get("blockers") else "Resolve promotion blockers before review.",
    }


def validate_proposal_promotion_provenance(proposal_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = _ensure_promotion_dirs(root)
    proposal = _load_proposal(base, proposal_id)
    if proposal is None:
        return {"proposal_id": proposal_id, "valid": False, "warnings": [], "blockers": ["proposal_not_found"]}
    blockers: list[str] = []
    warnings: list[str] = []
    if str(proposal.get("status") or "") not in {"draft", "changes_requested", "promoted", "rejected"}:
        blockers.append("proposal_status_invalid")
    if proposal.get("created_from") != "citation_evidence_handoff":
        blockers.append("proposal_not_from_evidence_handoff")
    citation = _load_citation(base, str(proposal.get("source_citation_id") or ""))
    handoff = _load_handoff(base, str(proposal.get("source_evidence_handoff_id") or ""))
    handoff_review = _load_review_by_id(base, str(proposal.get("source_handoff_review_id") or ""))
    revalidation = _matching_revalidation(base, proposal)
    if citation is None:
        blockers.append("citation_missing")
    if handoff is None:
        blockers.append("handoff_missing")
    if handoff_review is None:
        blockers.append("handoff_review_missing")
    if revalidation is None:
        blockers.append("matching_revalidation_missing")
    document_id = str(proposal.get("document_id") or "")
    current_revision = calculate_document_revision_state(document_id, root=base).get("source_revision") if document_id else None
    source_revision_current = current_revision is not None and proposal.get("source_revision") == current_revision
    if not source_revision_current:
        blockers.append("source_revision_changed")
    locator_validation = validate_source_locator(_proposal_locator(proposal, citation), root=base) if citation is not None else {"valid": False, "blockers": ["citation_missing"]}
    if citation is not None:
        if citation.get("document_id") != proposal.get("document_id"):
            blockers.append("citation_document_mismatch")
        if citation.get("source_revision") != proposal.get("source_revision"):
            blockers.append("citation_source_revision_mismatch")
        if citation.get("selected_text_hash") in {None, ""}:
            blockers.append("citation_selected_text_hash_missing")
    if not locator_validation.get("valid"):
        blockers.extend(locator_validation.get("blockers", []))
    if handoff is not None and handoff.get("completed_action") != "proposal_draft":
        blockers.append("handoff_not_completed_through_proposal_draft")
    if revalidation is not None and revalidation.get("status") not in {"pending_review", "resolved"}:
        blockers.append("revalidation_status_invalid")
    return {
        "proposal_id": proposal_id,
        "valid": not blockers,
        "document_id": document_id,
        "source_revision_current": source_revision_current,
        "citation_id": proposal.get("source_citation_id"),
        "citation_valid": citation is not None,
        "locator_valid": bool(locator_validation.get("valid")),
        "handoff_valid": handoff is not None and handoff.get("completed_action") == "proposal_draft",
        "revalidation_valid": revalidation is not None,
        "warnings": list(dict.fromkeys(warnings)),
        "blockers": list(dict.fromkeys(blockers)),
    }


def analyze_proposal_promotion_conflicts(proposal_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = _ensure_promotion_dirs(root)
    proposal = _load_proposal(base, proposal_id)
    if proposal is None:
        return {"proposal_id": proposal_id, "duplicate_status": "none", "duplicate_count": 0, "conflict_status": "none", "conflict_count": 0, "matches": [], "promotion_allowed": False, "requires_conflict_acknowledgement": False, "warnings": [], "blockers": ["proposal_not_found"]}
    matches: list[dict[str, object]] = []
    duplicate_status = "none"
    conflict_status = "none"
    blockers: list[str] = []
    warnings: list[str] = []
    exact = _proposal_exact_signature(proposal)
    target = _proposal_target_signature(proposal)
    category = _proposal_category(proposal)
    for other in _all_proposals(base):
        if other.get("proposal_id") == proposal_id:
            continue
        relation = None
        severity = "warning"
        if _proposal_exact_signature(other) == exact:
            relation = "exact_duplicate"
            duplicate_status = "exact_duplicate"
            severity = "critical"
            blockers.append("exact_duplicate_exists")
        elif str(other.get("document_id") or "") == str(proposal.get("document_id") or "") and str(other.get("source_citation_id") or "") == str(proposal.get("source_citation_id") or "") and _proposal_target_signature(other) == target:
            relation = "near_duplicate"
            if duplicate_status == "none":
                duplicate_status = "near_duplicate"
            warnings.append("near_duplicate_requires_acknowledgement")
        elif _proposal_target_signature(other) == target and _proposal_category(other) != category:
            relation = "conflict"
            other_status = str(other.get("status") or "")
            severity = "critical" if other_status == "promoted" else "warning"
            conflict_status = "critical" if severity == "critical" else "warning"
            if severity == "critical":
                blockers.append("critical_conflict_exists")
            else:
                warnings.append("one_noncritical_conflict_requires_acknowledgement")
        if relation:
            matches.append(
                {
                    "proposal_id": other.get("proposal_id"),
                    "relationship": relation,
                    "matching_target": target,
                    "severity": severity,
                }
            )
    base_duplicates = detect_duplicate_proposals(proposal_id, root=base)
    base_conflicts = detect_proposal_conflicts(proposal_id, root=base)
    if duplicate_status == "none" and base_duplicates.get("matches"):
        duplicate_status = "near_duplicate"
        warnings.append("near_duplicate_requires_acknowledgement")
    if conflict_status == "none" and base_conflicts.get("matches"):
        conflict_status = "warning"
        warnings.append("one_noncritical_conflict_requires_acknowledgement")
    promotion_allowed = "exact_duplicate_exists" not in blockers and "critical_conflict_exists" not in blockers
    return {
        "proposal_id": proposal_id,
        "duplicate_status": duplicate_status,
        "duplicate_count": sum(1 for item in matches if item["relationship"] in {"exact_duplicate", "near_duplicate"}),
        "conflict_status": conflict_status,
        "conflict_count": sum(1 for item in matches if item["relationship"] == "conflict"),
        "matches": matches,
        "promotion_allowed": promotion_allowed,
        "requires_conflict_acknowledgement": duplicate_status == "near_duplicate" or conflict_status == "warning",
        "warnings": list(dict.fromkeys(warnings)),
        "blockers": list(dict.fromkeys(blockers)),
    }


def save_proposal_promotion_decision(
    proposal_id: str,
    decision: str,
    reviewer_note: str | None = None,
    acknowledge_near_duplicate: bool = False,
    acknowledge_conflict: bool = False,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    if decision not in ALLOWED_DECISIONS:
        raise ValueError(f"Unsupported promotion decision: {decision}")
    base = _ensure_promotion_dirs(root)
    proposal = _load_proposal(base, proposal_id)
    if proposal is None:
        raise FileNotFoundError(proposal_id)
    provenance = validate_proposal_promotion_provenance(proposal_id, root=base)
    conflict = analyze_proposal_promotion_conflicts(proposal_id, root=base)
    existing = load_proposal_promotion_review(proposal_id=proposal_id, root=base)
    note = str(reviewer_note or "").strip() or None
    blockers: list[str] = []
    if decision == "approve":
        blockers.extend(provenance.get("blockers", []))
        blockers.extend(conflict.get("blockers", []))
        if conflict.get("duplicate_status") == "near_duplicate" and not acknowledge_near_duplicate:
            blockers.append("near_duplicate_acknowledgement_required")
        if conflict.get("conflict_status") == "warning" and not acknowledge_conflict:
            blockers.append("conflict_acknowledgement_required")
    else:
        if not note:
            blockers.append("reviewer_note_required")
    if blockers:
        return _blocked("promotion_review_blocked", blockers=list(dict.fromkeys(blockers)))
    payload = {
        "schema_version": PROMOTION_REVIEW_SCHEMA_VERSION,
        "promotion_review_id": (existing or {}).get("promotion_review_id") or _promotion_review_id(proposal_id),
        "proposal_id": proposal_id,
        "document_id": proposal.get("document_id"),
        "source_revision": proposal.get("source_revision"),
        "decision": decision,
        "review_status": "approved" if decision == "approve" else "rejected" if decision == "reject" else "changes_requested",
        "acknowledge_near_duplicate": bool(acknowledge_near_duplicate),
        "acknowledge_conflict": bool(acknowledge_conflict),
        "reviewer_note": note,
        "provenance_snapshot": provenance,
        "duplicate_conflict_snapshot": conflict,
        "review_revision": int((existing or {}).get("review_revision") or 0),
        "created_at_utc": (existing or {}).get("created_at_utc") or _now(),
        "updated_at_utc": _now(),
        "warnings": conflict.get("warnings", []),
    }
    if existing and _same_review(existing, payload):
        return {"status": "saved", "review": existing, "writes_performed": 0}
    payload["review_revision"] = int((existing or {}).get("review_revision") or 0) + 1
    review_path = _promotion_review_path(base, str(payload["promotion_review_id"]))
    before_review = _read_json(review_path)
    before_index = _read_json(base / "indexes" / PROMOTION_REVIEW_INDEX)
    try:
        _atomic_write_json(review_path, payload)
        _update_promotion_review_index(base)
    except Exception:
        _restore_json(review_path, before_review)
        _restore_json(base / "indexes" / PROMOTION_REVIEW_INDEX, before_index)
        return {"status": "failed_rolled_back", "classification": "promotion_review_write_failure", "warnings": []}
    return {"status": "saved", "review": payload, "writes_performed": 1}


def promote_approved_proposal(promotion_review_id: str, confirmation: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    if confirmation != "PROMOTE":
        return _blocked("promote_confirmation_required", blockers=["promote_confirmation_required"])
    base = _ensure_promotion_dirs(root)
    review = _load_promotion_review_by_id(base, promotion_review_id)
    if review is None:
        raise FileNotFoundError(promotion_review_id)
    proposal_id = str(review.get("proposal_id") or "")
    proposal = _load_proposal(base, proposal_id)
    if proposal is None:
        return _blocked("promotion_invalid", blockers=["proposal_not_found"])
    receipt = _load_receipt_for_proposal(base, proposal_id)
    revalidation = _matching_revalidation(base, proposal)
    provenance = validate_proposal_promotion_provenance(proposal_id, root=base)
    conflicts = analyze_proposal_promotion_conflicts(proposal_id, root=base)
    if review.get("decision") != "approve":
        return _blocked("promotion_invalid", blockers=["promotion_review_not_approved"])
    if provenance.get("blockers"):
        return _blocked("promotion_invalid", blockers=provenance.get("blockers"))
    if conflicts.get("blockers"):
        return _blocked("promotion_invalid", blockers=conflicts.get("blockers"))
    if conflicts.get("duplicate_status") == "near_duplicate" and not review.get("acknowledge_near_duplicate"):
        return _blocked("promotion_invalid", blockers=["near_duplicate_acknowledgement_required"])
    if conflicts.get("conflict_status") == "warning" and not review.get("acknowledge_conflict"):
        return _blocked("promotion_invalid", blockers=["conflict_acknowledgement_required"])
    if receipt is not None and proposal.get("status") == "promoted" and revalidation is not None and revalidation.get("status") == "resolved":
        return {"status": "already_promoted", "proposal_id": proposal_id, "promotion_receipt_id": receipt.get("promotion_receipt_id"), "writes_performed": 0}
    if receipt is not None or proposal.get("status") == "promoted":
        return _blocked("promotion_state_diverged", blockers=["promotion_state_diverged"])
    citation_id = str(proposal.get("source_citation_id") or "")
    before_hash = _hash_payload(proposal)
    updated_proposal = dict(proposal)
    updated_proposal["status"] = "promoted"
    updated_proposal["promotion_review_id"] = promotion_review_id
    updated_proposal["promoted_at_utc"] = _now()
    updated_proposal["accepted_citation_ids"] = sorted({*list(updated_proposal.get("accepted_citation_ids", []) or []), citation_id})
    updated_proposal["updated_at_utc"] = _now()
    updated_proposal["provenance_digest"] = _hash_payload(
        {
            "source_evidence_handoff_id": proposal.get("source_evidence_handoff_id"),
            "source_handoff_review_id": proposal.get("source_handoff_review_id"),
            "source_revision": proposal.get("source_revision"),
            "source_citation_id": citation_id,
        }
    )
    receipt_payload = {
        "schema_version": PROMOTION_RECEIPT_SCHEMA_VERSION,
        "promotion_receipt_id": _promotion_receipt_id(proposal_id),
        "proposal_id": proposal_id,
        "promotion_review_id": promotion_review_id,
        "document_id": proposal.get("document_id"),
        "source_revision": proposal.get("source_revision"),
        "citation_ids": [citation_id],
        "evidence_handoff_id": proposal.get("source_evidence_handoff_id"),
        "handoff_review_id": proposal.get("source_handoff_review_id"),
        "revalidation_id": (revalidation or {}).get("queue_item_id"),
        "before_proposal_hash": before_hash,
        "after_proposal_hash": _hash_payload(updated_proposal),
        "promotion_status": "completed",
        "created_at_utc": _now(),
        "warnings": [],
    }
    updated_proposal["promotion_receipt_id"] = receipt_payload["promotion_receipt_id"]
    updated_review = dict(review)
    updated_review["review_status"] = "completed"
    updated_review["updated_at_utc"] = _now()
    updated_review["promotion_receipt_id"] = receipt_payload["promotion_receipt_id"]
    updated_revalidation = dict(revalidation or {})
    updated_revalidation["status"] = "resolved"
    updated_revalidation["resolution"] = "proposal_promoted"
    updated_revalidation["proposal_id"] = proposal_id
    updated_revalidation["promotion_receipt_id"] = receipt_payload["promotion_receipt_id"]
    updated_revalidation["resolved_at_utc"] = _now()
    proposal_path = _proposal_path(base, proposal_id)
    receipt_path = _promotion_receipt_path(base, str(receipt_payload["promotion_receipt_id"]))
    review_path = _promotion_review_path(base, promotion_review_id)
    revalidation_path = _queue_item_path(base, str(updated_revalidation.get("queue_item_id") or ""))
    write_targets = {
        proposal_path: _read_json(proposal_path),
        base / "indexes" / "proposal_index.json": _read_json(base / "indexes" / "proposal_index.json"),
        review_path: _read_json(review_path),
        receipt_path: _read_json(receipt_path),
        base / "indexes" / PROMOTION_RECEIPT_INDEX: _read_json(base / "indexes" / PROMOTION_RECEIPT_INDEX),
        revalidation_path: _read_json(revalidation_path),
        base / "indexes" / QUEUE_INDEX: _read_json(base / "indexes" / QUEUE_INDEX),
    }
    try:
        _atomic_write_json(proposal_path, updated_proposal)
        _update_proposal_index(base)
        _atomic_write_json(review_path, updated_review)
        _atomic_write_json(receipt_path, receipt_payload)
        _update_promotion_receipt_index(base)
        _atomic_write_json(revalidation_path, updated_revalidation)
        _update_queue_index(base)
        post = _post_promotion_validation(base, updated_proposal, updated_review, receipt_payload, updated_revalidation)
        if post:
            raise RuntimeError(post)
    except Exception:
        rollback = _rollback(write_targets)
        return {
            "status": "rollback_failed" if not rollback else "failed_rolled_back",
            "classification": "critical_recovery_failure" if not rollback else "revalidation_resolution_failure",
            "records_restored": len(write_targets),
            "rollback_verified": rollback,
            "warnings": [],
        }
    return {
        "status": "promoted",
        "proposal_id": proposal_id,
        "promotion_review_id": promotion_review_id,
        "promotion_receipt_id": receipt_payload["promotion_receipt_id"],
        "citation_id": citation_id,
        "citation_evidence_status": "accepted",
        "revalidation_status": "resolved",
        "warnings": [],
    }


def load_proposal_promotion_review(
    proposal_id: str | None = None,
    promotion_review_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict | None:
    base = _ensure_promotion_dirs(root)
    if promotion_review_id:
        payload = _load_promotion_review_by_id(base, promotion_review_id)
        return payload if isinstance(payload, dict) else None
    if proposal_id:
        for item in _load_promotion_reviews(base):
            if str(item.get("proposal_id") or "") == proposal_id:
                return item
    return None


def get_proposal_promotion_health(document_id: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = _ensure_promotion_dirs(root)
    reviews = _load_promotion_reviews(base)
    receipts = _load_promotion_receipts(base)
    proposals = _all_proposals(base)
    if document_id:
        reviews = [item for item in reviews if item.get("document_id") == document_id]
        receipts = [item for item in receipts if item.get("document_id") == document_id]
        proposals = [item for item in proposals if item.get("document_id") == document_id]
    if not reviews and not receipts and not proposals:
        return {"status": "empty", "promotion_review_count": 0, "approved_waiting_count": 0, "promoted_count": 0, "rejected_count": 0, "changes_requested_count": 0, "missing_receipt_count": 0, "missing_revalidation_resolution_count": 0, "divergent_state_count": 0, "warnings": [], "recommended_action": "Load a Phase 9B proposal draft for promotion review."}
    missing_receipt = 0
    missing_revalidation_resolution = 0
    divergent = 0
    warnings: list[str] = []
    review_ids = [str(item.get("promotion_review_id") or "") for item in reviews]
    receipt_ids = [str(item.get("promotion_receipt_id") or "") for item in receipts]
    if len(review_ids) != len(set(review_ids)):
        divergent += 1
    if len(receipt_ids) != len(set(receipt_ids)):
        divergent += 1
    promoted_exact_signatures: set[str] = set()
    for proposal in proposals:
        status = str(proposal.get("status") or "")
        if status == "promoted":
            sig = _proposal_exact_signature(proposal)
            if sig in promoted_exact_signatures:
                divergent += 1
            promoted_exact_signatures.add(sig)
            receipt = _load_receipt_for_proposal(base, str(proposal.get("proposal_id") or ""))
            if receipt is None:
                missing_receipt += 1
            revalidation = _matching_revalidation(base, proposal)
            if revalidation is None or revalidation.get("status") != "resolved":
                missing_revalidation_resolution += 1
    approved_waiting = sum(1 for item in reviews if item.get("review_status") == "approved")
    if approved_waiting:
        warnings.append("one_approved_proposal_is_waiting_for_promotion")
    status = "healthy"
    if divergent:
        status = "blocked"
    elif missing_receipt or missing_revalidation_resolution or approved_waiting:
        status = "warning"
    return {
        "status": status if status in HEALTH_STATUSES else "unknown",
        "promotion_review_count": len(reviews),
        "approved_waiting_count": approved_waiting,
        "promoted_count": sum(1 for item in proposals if item.get("status") == "promoted"),
        "rejected_count": sum(1 for item in reviews if item.get("review_status") == "rejected"),
        "changes_requested_count": sum(1 for item in reviews if item.get("review_status") == "changes_requested"),
        "missing_receipt_count": missing_receipt,
        "missing_revalidation_resolution_count": missing_revalidation_resolution,
        "divergent_state_count": divergent,
        "warnings": warnings,
        "recommended_action": "Review one approved proposal awaiting PROMOTE confirmation." if approved_waiting else "Resolve divergent promotion state." if divergent else "Proposal promotion health is good.",
    }


def format_proposal_promotion_report(
    proposal_id: str | None = None,
    promotion_review_id: str | None = None,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    base = _ensure_promotion_dirs(root)
    review = load_proposal_promotion_review(proposal_id=proposal_id, promotion_review_id=promotion_review_id, root=base)
    proposal = _load_proposal(base, str((review or {}).get("proposal_id") or proposal_id or ""))
    if proposal is None:
        return "Proposal Promotion Report\n\nStatus: not_found"
    workspace = build_proposal_promotion_workspace(str(proposal.get("proposal_id") or ""), root=base)
    receipt = _load_receipt_for_proposal(base, str(proposal.get("proposal_id") or ""))
    report = "\n".join(
        [
            "Proposal Promotion Report",
            "",
            f"Document: {proposal.get('document_id')}",
            f"Source Revision: {proposal.get('source_revision')}",
            f"Proposal: {proposal.get('proposal_id')}",
            f"Proposal Status: {proposal.get('status')}",
            "",
            "Review:",
            f"- Decision: {(review or {}).get('decision', 'not_decided')}",
            f"- Review Status: {(review or {}).get('review_status', 'pending')}",
            f"- Duplicate Status: {workspace.get('duplicate_status')}",
            f"- Conflict Status: {workspace.get('conflict_status')}",
            "",
            "Evidence:",
            f"- Accepted Citations: {len(proposal.get('accepted_citation_ids', []) or [])}",
            f"- Citation Provenance: {workspace.get('citation_provenance_status')}",
            "",
            "Promotion:",
            f"- Receipt: {(receipt or {}).get('promotion_receipt_id', 'none')}",
            f"- Status: {('completed' if receipt else 'pending')}",
            "",
            "Revalidation:",
            f"- Status: {workspace.get('revalidation_status')}",
            f"- Resolution: {('proposal_promoted' if workspace.get('revalidation_status') == 'resolved' else 'pending')}",
            "",
            "Important:",
            "The proposal was promoted only after explicit review and PROMOTE confirmation.",
            "No election rule, scoring behavior, or objective pack was modified.",
            "",
            "Recommended Action:",
            "Use the promoted proposal only through a later controlled integration phase." if proposal.get("status") == "promoted" else workspace.get("recommended_action"),
        ]
    )
    if public_safe:
        for needle in ("C:\\", "/Users/", "Traceback", "reviewer_note", "quote_excerpt", "selected_text", "claim", "token=", "secret"):
            report = report.replace(needle, "[redacted]")
    return report


def _ensure_promotion_dirs(root: Path | str) -> Path:
    base = ensure_source_knowledge_dirs(root)
    ensure_source_impact_dirs(base)
    (base / PROMOTION_REVIEW_DIR).mkdir(parents=True, exist_ok=True)
    (base / PROMOTION_RECEIPT_DIR).mkdir(parents=True, exist_ok=True)
    for index_name in (PROMOTION_REVIEW_INDEX, PROMOTION_RECEIPT_INDEX):
        path = base / "indexes" / index_name
        if not path.exists():
            _atomic_write_json(path, {"entries": [], "updated_at_utc": _now()})
    return base


def _load_proposal(root: Path, proposal_id: str) -> dict[str, object] | None:
    payload = _read_json(_proposal_path(root, proposal_id))
    return payload if isinstance(payload, dict) else None


def _all_proposals(root: Path) -> list[dict[str, object]]:
    items = []
    for path in sorted((root / "proposals").glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _matching_revalidation(root: Path, proposal: Mapping[str, object]) -> dict[str, object] | None:
    for item in list_source_revalidation_queue(limit=500, root=root).get("items", []):
        if not isinstance(item, dict):
            continue
        if item.get("proposal_id") == proposal.get("proposal_id") and item.get("evidence_handoff_id") == proposal.get("source_evidence_handoff_id"):
            return item
    return _existing_revalidation_for_any_action(root, str(proposal.get("source_evidence_handoff_id") or ""))


def _proposal_locator(proposal: Mapping[str, object], citation: Mapping[str, object] | None) -> dict[str, object]:
    locator = proposal.get("locator")
    if isinstance(locator, Mapping):
        payload = dict(locator)
        if "page" in payload and "page_number" not in payload:
            payload["page_number"] = payload.get("page")
        if "start_offset" in payload and "character_start" not in payload:
            payload["character_start"] = payload.get("start_offset")
        if "end_offset" in payload and "character_end" not in payload:
            payload["character_end"] = payload.get("end_offset")
        return payload
    if citation is None:
        return {}
    return {
        "document_id": citation.get("document_id"),
        "source_revision": citation.get("source_revision"),
        "chunk_id": citation.get("chunk_id"),
        "page_number": citation.get("page"),
        "character_start": citation.get("start_offset"),
        "character_end": citation.get("end_offset"),
    }


def _proposal_exact_signature(proposal: Mapping[str, object]) -> str:
    payload = {
        "document_id": proposal.get("document_id"),
        "source_revision": proposal.get("source_revision"),
        "source_citation_id": proposal.get("source_citation_id"),
        "target": _proposal_target_signature(proposal),
        "claim_hash": _hash_payload(_normalize_claim(str(proposal.get("claim") or ""))),
        "locator": _proposal_locator(proposal, None),
    }
    return _hash_payload(payload)


def _proposal_target_signature(proposal: Mapping[str, object]) -> str:
    return "|".join(
        [
            str(proposal.get("document_id") or ""),
            str(proposal.get("chunk_id") or ""),
            str(proposal.get("proposal_type") or ""),
        ]
    )


def _proposal_category(proposal: Mapping[str, object]) -> str:
    text = _normalize_claim(str(proposal.get("claim") or ""))
    if any(word in text for word in ("not ", "reject", "deny", "block", "avoid")):
        return "negative"
    if any(word in text for word in ("allow", "approve", "accept", "promote", "use", "support")):
        return "positive"
    return "neutral"


def _normalize_claim(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _promotion_review_id(proposal_id: str) -> str:
    return f"proposal_promotion_review_{_hash_payload({'proposal_id': proposal_id})[7:23]}"


def _promotion_receipt_id(proposal_id: str) -> str:
    return f"proposal_promotion_receipt_{_hash_payload({'proposal_id': proposal_id})[7:23]}"


def _promotion_review_path(root: Path, promotion_review_id: str) -> Path:
    return root / PROMOTION_REVIEW_DIR / f"{promotion_review_id}.json"


def _promotion_receipt_path(root: Path, receipt_id: str) -> Path:
    return root / PROMOTION_RECEIPT_DIR / f"{receipt_id}.json"


def _load_promotion_reviews(root: Path) -> list[dict[str, object]]:
    items = []
    for path in sorted((root / PROMOTION_REVIEW_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _load_promotion_review_by_id(root: Path, promotion_review_id: str) -> dict[str, object] | None:
    payload = _read_json(_promotion_review_path(root, promotion_review_id))
    return payload if isinstance(payload, dict) else None


def _load_promotion_receipts(root: Path) -> list[dict[str, object]]:
    items = []
    for path in sorted((root / PROMOTION_RECEIPT_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _load_receipt_for_proposal(root: Path, proposal_id: str) -> dict[str, object] | None:
    for item in _load_promotion_receipts(root):
        if str(item.get("proposal_id") or "") == proposal_id:
            return item
    return None


def _update_promotion_review_index(root: Path) -> None:
    entries = []
    for item in _load_promotion_reviews(root):
        entries.append(
            {
                "promotion_review_id": item.get("promotion_review_id"),
                "proposal_id": item.get("proposal_id"),
                "document_id": item.get("document_id"),
                "decision": item.get("decision"),
                "review_status": item.get("review_status"),
                "updated_at_utc": item.get("updated_at_utc"),
            }
        )
    _atomic_write_json(root / "indexes" / PROMOTION_REVIEW_INDEX, {"entries": entries, "updated_at_utc": _now()})


def _update_promotion_receipt_index(root: Path) -> None:
    entries = []
    for item in _load_promotion_receipts(root):
        entries.append(
            {
                "promotion_receipt_id": item.get("promotion_receipt_id"),
                "proposal_id": item.get("proposal_id"),
                "document_id": item.get("document_id"),
                "source_revision": item.get("source_revision"),
                "created_at_utc": item.get("created_at_utc"),
            }
        )
    _atomic_write_json(root / "indexes" / PROMOTION_RECEIPT_INDEX, {"entries": entries, "updated_at_utc": _now()})


def _same_review(existing: Mapping[str, object], payload: Mapping[str, object]) -> bool:
    return all(
        existing.get(field) == payload.get(field)
        for field in ("decision", "review_status", "reviewer_note", "acknowledge_near_duplicate", "acknowledge_conflict")
    )


def _rollback(targets: Mapping[Path, Any]) -> bool:
    before = {path: _hash_file(path) for path in targets}
    for path, payload in targets.items():
        _restore_json(path, payload)
    after = {path: _hash_file(path) for path in targets}
    return all(before[path] == after[path] for path in targets)


def _hash_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return _hash_payload(_read_json(path))


def _post_promotion_validation(
    root: Path,
    proposal: Mapping[str, object],
    review: Mapping[str, object],
    receipt: Mapping[str, object],
    revalidation: Mapping[str, object],
) -> str | None:
    if proposal.get("status") != "promoted":
        return "proposal_not_promoted"
    if review.get("proposal_id") != proposal.get("proposal_id"):
        return "review_proposal_mismatch"
    if receipt.get("proposal_id") != proposal.get("proposal_id") or receipt.get("promotion_review_id") != review.get("promotion_review_id"):
        return "receipt_reference_mismatch"
    if str(proposal.get("source_citation_id") or "") not in set(proposal.get("accepted_citation_ids", []) or []):
        return "accepted_citation_missing"
    provenance = validate_proposal_promotion_provenance(str(proposal.get("proposal_id") or ""), root=root)
    if provenance.get("citation_valid") is not True:
        return "citation_provenance_invalid"
    if revalidation.get("status") != "resolved":
        return "revalidation_not_resolved"
    if analyze_proposal_promotion_conflicts(str(proposal.get("proposal_id") or ""), root=root).get("duplicate_status") == "exact_duplicate":
        return "exact_duplicate_promoted"
    return None
