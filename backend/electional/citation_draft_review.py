from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from .pdf_reader_workspace import load_pdf_reader_workspace
from .pdf_viewport import _blocked, _ensure_dirs, _hash_payload, _latest_current_certification
from .source_documents import SOURCE_DOCUMENT_ROOT, load_source_document
from .source_knowledge import ensure_source_knowledge_dirs, load_chunk


REVIEW_SCHEMA_VERSION = "citation_draft_review_v1"
HANDOFF_SCHEMA_VERSION = "citation_evidence_handoff_v1"
REVIEW_DIR = "citation_draft_reviews"
HANDOFF_DIR = "citation_evidence_handoffs"
REVIEW_INDEX = "citation_draft_review_index.json"
HANDOFF_INDEX = "citation_evidence_handoff_index.json"


def build_citation_draft_review_workspace(
    workspace_id: str,
    citation_draft_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_review_dirs(root)
    workspace_loaded = _load_workspace_for_review(workspace_id, root=base)
    draft = _find_draft(workspace_loaded.get("workspace"), citation_draft_id)
    provenance = validate_citation_draft_provenance(workspace_id, citation_draft_id, root=base)
    duplicates = detect_citation_draft_duplicates(workspace_id, citation_draft_id, root=base)
    review = load_citation_draft_review(citation_draft_id=citation_draft_id, workspace_id=workspace_id, root=base)
    handoff = _load_handoff_for_draft(workspace_id, citation_draft_id, root=base)
    return {
        "workspace_id": workspace_id,
        "citation_draft_id": citation_draft_id,
        "document_id": (draft or {}).get("document_id") or ((workspace_loaded.get("workspace") or {}).get("document_id") if isinstance(workspace_loaded.get("workspace"), Mapping) else None),
        "source_revision": (draft or {}).get("source_revision") or ((workspace_loaded.get("workspace") or {}).get("source_revision") if isinstance(workspace_loaded.get("workspace"), Mapping) else None),
        "draft_status": (draft or {}).get("status", "missing"),
        "review_status": (review or {}).get("review_status", "pending"),
        "provenance_status": "valid" if provenance.get("valid") else "blocked" if provenance.get("blockers") else "warning",
        "duplicate_status": duplicates.get("duplicate_status", "none"),
        "duplicate_count": duplicates.get("duplicate_count", 0),
        "real_citation_id": (draft or {}).get("real_citation_id") or (review or {}).get("real_citation_id"),
        "evidence_handoff_id": (draft or {}).get("evidence_handoff_id") or (handoff or {}).get("evidence_handoff_id"),
        "warnings": list(dict.fromkeys(list(provenance.get("warnings", [])) + list(duplicates.get("warnings", [])))),
        "blockers": list(dict.fromkeys(list(provenance.get("blockers", [])) + list(duplicates.get("blockers", [])))),
        "recommended_action": "Review and approve or reject the citation draft." if provenance.get("valid") else "Resolve provenance blockers before review.",
    }


def validate_citation_draft_provenance(
    workspace_id: str,
    citation_draft_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_review_dirs(root)
    workspace_loaded = _load_workspace_for_review(workspace_id, root=base)
    workspace = workspace_loaded.get("workspace") if isinstance(workspace_loaded.get("workspace"), Mapping) else None
    blockers = list(workspace_loaded.get("blockers", [])) if workspace_loaded.get("status") not in {"current", "warning"} else []
    warnings = list(workspace_loaded.get("warnings", []))
    draft = _find_draft(workspace, citation_draft_id)
    if not isinstance(workspace, Mapping):
        blockers.append("workspace_missing")
    if not isinstance(draft, Mapping):
        blockers.append("citation_draft_missing")
        return {"valid": False, "warnings": warnings, "blockers": sorted(set(blockers))}
    if draft.get("document_id") != workspace.get("document_id"):
        blockers.append("draft_document_mismatch")
    if draft.get("source_revision") != workspace.get("source_revision"):
        blockers.extend(["draft_source_revision_mismatch", "source_revision_changed"])
    selected_text = str(draft.get("selected_text") or "")
    if not selected_text:
        blockers.append("selected_text_missing")
    if _hash_payload(selected_text) != draft.get("selected_text_hash"):
        blockers.append("selected_text_hash_mismatch")
    page = _normalize_positive_int(draft.get("page"))
    if page is None or page < 1:
        blockers.append("invalid_page")
    start_offset = _normalize_non_negative_int(draft.get("start_offset"))
    end_offset = _normalize_non_negative_int(draft.get("end_offset"))
    if start_offset is None or end_offset is None or start_offset >= end_offset:
        blockers.append("invalid_offsets")
    chunk_id = str(draft.get("chunk_id") or "")
    if chunk_id:
        try:
            chunk = load_chunk(chunk_id, root=base)
            if chunk.document_id != workspace.get("document_id"):
                blockers.append("chunk_document_mismatch")
            if page is not None and chunk.page_start is not None and chunk.page_end is not None and not (chunk.page_start <= page <= chunk.page_end):
                blockers.append("chunk_page_mismatch")
        except Exception:
            blockers.append("chunk_missing")
    record = load_source_document(str(workspace.get("document_id") or ""), root=base, missing_ok=True) if isinstance(workspace, Mapping) else None
    if record is None:
        blockers.append("document_not_found")
    return {
        "valid": not blockers,
        "document_id": (draft or {}).get("document_id"),
        "source_revision": (draft or {}).get("source_revision"),
        "page": page,
        "chunk_id": chunk_id or None,
        "selected_text_hash_valid": _hash_payload(selected_text) == draft.get("selected_text_hash"),
        "locator_valid": not any(item in blockers for item in {"chunk_document_mismatch", "chunk_page_mismatch", "invalid_page", "invalid_offsets"}),
        "warnings": sorted(set(warnings)),
        "blockers": sorted(set(blockers)),
    }


def detect_citation_draft_duplicates(
    workspace_id: str,
    citation_draft_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_review_dirs(root)
    workspace_loaded = _load_workspace_for_review(workspace_id, root=base)
    draft = _find_draft(workspace_loaded.get("workspace"), citation_draft_id)
    if not isinstance(draft, Mapping):
        return {"citation_draft_id": citation_draft_id, "duplicate_status": "none", "duplicate_count": 0, "matches": [], "creation_allowed": False, "warnings": [], "blockers": ["citation_draft_missing"]}
    matches = []
    for citation in _load_citations(base):
        if citation.get("document_id") != draft.get("document_id"):
            continue
        duplicate_type = None
        matching_fields = []
        if citation.get("source_revision") == draft.get("source_revision"):
            matching_fields.append("source_revision")
        if citation.get("page_start") == draft.get("page") and citation.get("page_end") == draft.get("page"):
            matching_fields.append("page")
        if citation.get("chunk_id") == draft.get("chunk_id"):
            matching_fields.append("chunk_id")
        if citation.get("start_offset") == draft.get("start_offset") and citation.get("end_offset") == draft.get("end_offset"):
            matching_fields.append("offsets")
        if citation.get("selected_text_hash") == draft.get("selected_text_hash"):
            matching_fields.append("selected_text_hash")
        if {"source_revision", "page", "chunk_id", "offsets", "selected_text_hash"}.issubset(set(matching_fields)):
            duplicate_type = "exact_duplicate"
        elif citation.get("source_revision") == draft.get("source_revision") and citation.get("page_start") == draft.get("page") and citation.get("selected_text_hash") == draft.get("selected_text_hash") and _ranges_overlap(citation.get("start_offset"), citation.get("end_offset"), draft.get("start_offset"), draft.get("end_offset")):
            duplicate_type = "near_duplicate"
        if duplicate_type:
            matches.append({"citation_id": citation.get("citation_id"), "duplicate_type": duplicate_type, "matching_fields": ["document_id", *matching_fields]})
    exact = [item for item in matches if item["duplicate_type"] == "exact_duplicate"]
    near = [item for item in matches if item["duplicate_type"] == "near_duplicate"]
    status = "exact_duplicate" if exact else "near_duplicate" if near else "none"
    blockers = ["exact_duplicate_exists"] if exact else []
    return {"citation_draft_id": citation_draft_id, "duplicate_status": status, "duplicate_count": len(matches), "matches": matches, "creation_allowed": not exact, "warnings": [], "blockers": blockers}


def save_citation_draft_review_decision(
    workspace_id: str,
    citation_draft_id: str,
    decision: str,
    reviewer_note: str | None = None,
    allow_near_duplicate: bool = False,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_review_dirs(root)
    if decision not in {"approve", "reject", "request_changes"}:
        return _blocked("invalid_review_decision", workspace_id=workspace_id, citation_draft_id=citation_draft_id)
    note = str(reviewer_note or "").strip()
    if decision in {"reject", "request_changes"} and not note:
        return _blocked("reviewer_note_required", workspace_id=workspace_id, citation_draft_id=citation_draft_id)
    provenance = validate_citation_draft_provenance(workspace_id, citation_draft_id, root=base)
    duplicates = detect_citation_draft_duplicates(workspace_id, citation_draft_id, root=base)
    if decision == "approve":
        if not provenance.get("valid"):
            return {"status": "blocked", "blockers": list(provenance.get("blockers", [])), "warnings": list(provenance.get("warnings", []))}
        if duplicates.get("duplicate_status") == "exact_duplicate":
            return {"status": "blocked", "blockers": ["exact_duplicate_exists"], "warnings": []}
        if duplicates.get("duplicate_status") == "near_duplicate" and not allow_near_duplicate:
            return {"status": "blocked", "blockers": ["near_duplicate_requires_override"], "warnings": []}
    workspace_loaded = _load_workspace_for_review(workspace_id, root=base)
    workspace = dict(workspace_loaded["workspace"])
    draft = _find_draft(workspace, citation_draft_id)
    review_path = _review_path(base, _review_id(workspace_id, citation_draft_id))
    existing = _read_json(review_path)
    if isinstance(existing, Mapping) and existing.get("decision") == decision and existing.get("reviewer_note") == (note or None) and bool(existing.get("allow_near_duplicate")) == bool(allow_near_duplicate):
        return {"status": "unchanged", "review": existing, "warnings": []}
    now = _now()
    review = {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "review_id": _review_id(workspace_id, citation_draft_id),
        "workspace_id": workspace_id,
        "citation_draft_id": citation_draft_id,
        "document_id": draft.get("document_id"),
        "source_revision": draft.get("source_revision"),
        "decision": decision,
        "review_status": {"approve": "approved", "reject": "rejected", "request_changes": "changes_requested"}[decision],
        "allow_near_duplicate": bool(allow_near_duplicate),
        "reviewer_note": note or None,
        "provenance_snapshot": provenance,
        "duplicate_snapshot": duplicates,
        "review_revision": (int(existing.get("review_revision") or 0) + 1) if isinstance(existing, Mapping) else 1,
        "created_at_utc": str(existing.get("created_at_utc") or now) if isinstance(existing, Mapping) else now,
        "updated_at_utc": now,
        "real_citation_id": existing.get("real_citation_id") if isinstance(existing, Mapping) else None,
        "evidence_handoff_id": existing.get("evidence_handoff_id") if isinstance(existing, Mapping) else None,
        "warnings": [],
    }
    _atomic_write_json(review_path, review)
    _update_review_index(base)
    _update_workspace_draft_state(base, workspace, citation_draft_id, review["review_status"], review_id=review["review_id"])
    return {"status": "saved", "review": review, "warnings": []}


def create_citation_from_approved_draft(
    review_id: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_review_dirs(root)
    review = _read_json(_review_path(base, review_id))
    if not isinstance(review, Mapping):
        return {"status": "not_found", "review_id": review_id, "blockers": ["review_missing"]}
    if confirmation != "CREATE":
        return {"status": "blocked", "review_id": review_id, "blockers": ["create_confirmation_required"]}
    workspace_loaded = _load_workspace_for_review(str(review.get("workspace_id") or ""), root=base)
    workspace = dict(workspace_loaded["workspace"]) if isinstance(workspace_loaded.get("workspace"), Mapping) else None
    draft = _find_draft(workspace, str(review.get("citation_draft_id") or ""))
    if review.get("review_status") == "created":
        existing_citation_id = str(review.get("real_citation_id") or "")
        handoff_id = str(review.get("evidence_handoff_id") or "")
        if existing_citation_id and _citation_path(base, existing_citation_id).exists():
            return {"status": "already_created", "citation_id": existing_citation_id, "evidence_handoff_id": handoff_id or None, "writes_performed": 0}
        return {"status": "blocked", "review_id": review_id, "blockers": ["citation_creation_state_diverged"]}
    if review.get("review_status") != "approved":
        return {"status": "blocked", "review_id": review_id, "blockers": ["review_not_approved"]}
    provenance = validate_citation_draft_provenance(str(review.get("workspace_id") or ""), str(review.get("citation_draft_id") or ""), root=base)
    duplicates = detect_citation_draft_duplicates(str(review.get("workspace_id") or ""), str(review.get("citation_draft_id") or ""), root=base)
    if not provenance.get("valid"):
        return {"status": "blocked", "review_id": review_id, "blockers": list(provenance.get("blockers", []))}
    if duplicates.get("duplicate_status") == "exact_duplicate":
        return {"status": "blocked", "review_id": review_id, "blockers": ["exact_duplicate_exists"]}
    if duplicates.get("duplicate_status") == "near_duplicate" and not review.get("allow_near_duplicate"):
        return {"status": "blocked", "review_id": review_id, "blockers": ["near_duplicate_requires_override"]}
    citation_id = _citation_id(draft)
    citation_path = _citation_path(base, citation_id)
    if citation_path.exists():
        return {"status": "blocked", "review_id": review_id, "blockers": ["citation_creation_state_diverged"]}
    handoff = {
        "schema_version": HANDOFF_SCHEMA_VERSION,
        "evidence_handoff_id": f"citation_handoff_{_hash_payload({'review_id': review_id, 'citation_id': citation_id})[7:23]}",
        "citation_id": citation_id,
        "document_id": draft.get("document_id"),
        "source_revision": draft.get("source_revision"),
        "source_workspace_id": review.get("workspace_id"),
        "source_citation_draft_id": review.get("citation_draft_id"),
        "source_review_id": review_id,
        "status": "pending_evidence_review",
        "candidate_binder_ids": [],
        "candidate_proposal_ids": [],
        "created_at_utc": _now(),
        "updated_at_utc": _now(),
        "warnings": [],
    }
    citation = {
        "citation_id": citation_id,
        "document_id": draft.get("document_id"),
        "chunk_id": draft.get("chunk_id"),
        "page_start": draft.get("page"),
        "page_end": draft.get("page"),
        "note": str(draft.get("note") or "Citation draft approved from PDF reader workspace.").strip()[:300],
        "quote_excerpt": str(draft.get("selected_text") or "").strip()[:300],
        "created_at_utc": _now(),
        "warnings": ["citation_does_not_activate_rule"],
        "schema_version": "source_citation_v1",
        "source_revision": draft.get("source_revision"),
        "page": draft.get("page"),
        "start_offset": draft.get("start_offset"),
        "end_offset": draft.get("end_offset"),
        "selected_text": draft.get("selected_text"),
        "selected_text_hash": draft.get("selected_text_hash"),
        "locator": {
            "document_id": draft.get("document_id"),
            "source_revision": draft.get("source_revision"),
            "page": draft.get("page"),
            "chunk_id": draft.get("chunk_id"),
            "start_offset": draft.get("start_offset"),
            "end_offset": draft.get("end_offset"),
        },
        "created_from": "pdf_reader_workspace",
        "source_workspace_id": review.get("workspace_id"),
        "source_citation_draft_id": review.get("citation_draft_id"),
        "source_review_id": review_id,
        "status": "active",
        "updated_at_utc": _now(),
    }
    updated_review = dict(review)
    updated_review["review_status"] = "created"
    updated_review["real_citation_id"] = citation_id
    updated_review["evidence_handoff_id"] = handoff["evidence_handoff_id"]
    updated_review["updated_at_utc"] = _now()
    updated_workspace = dict(workspace)
    if not _apply_workspace_draft_created(updated_workspace, str(review.get("citation_draft_id") or ""), citation_id, review_id, handoff["evidence_handoff_id"]):
        return {"status": "blocked", "review_id": review_id, "blockers": ["citation_draft_missing"]}
    review_path = _review_path(base, review_id)
    handoff_path = _handoff_path(base, handoff["evidence_handoff_id"])
    existing_review = _read_json(review_path)
    existing_workspace = _read_json(_workspace_path(base, str(review.get("workspace_id") or "")))
    existing_citation_index = _read_json(base / "indexes" / "citation_index.json")
    existing_handoff_index = _read_json(base / "indexes" / HANDOFF_INDEX)
    try:
        _atomic_write_json(citation_path, citation)
        _rebuild_citation_index(base)
        _atomic_write_json(review_path, updated_review)
        _atomic_write_json(_workspace_path(base, str(review.get("workspace_id") or "")), updated_workspace)
        _atomic_write_json(handoff_path, handoff)
        _update_handoff_index(base)
    except Exception:
        if citation_path.exists():
            citation_path.unlink()
        if handoff_path.exists():
            handoff_path.unlink()
        _restore_json(review_path, existing_review)
        _restore_json(_workspace_path(base, str(review.get("workspace_id") or "")), existing_workspace)
        _restore_json(base / "indexes" / "citation_index.json", existing_citation_index)
        _restore_json(base / "indexes" / HANDOFF_INDEX, existing_handoff_index)
        return {"status": "failed_rolled_back", "review_id": review_id, "blockers": ["write_set_failed"]}
    return {
        "status": "created",
        "review_id": review_id,
        "citation_draft_id": review.get("citation_draft_id"),
        "citation_id": citation_id,
        "document_id": draft.get("document_id"),
        "source_revision": draft.get("source_revision"),
        "evidence_handoff_id": handoff["evidence_handoff_id"],
        "workspace_draft_status": "created",
        "warnings": [],
    }


def load_citation_draft_review(
    review_id: str | None = None,
    workspace_id: str | None = None,
    citation_draft_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_review_dirs(root)
    effective_review_id = review_id or (_review_id(workspace_id or "", citation_draft_id or "") if workspace_id and citation_draft_id else "")
    payload = _read_json(_review_path(base, effective_review_id))
    if not isinstance(payload, Mapping):
        return {"status": "not_found", "review_id": effective_review_id, "review": None, "warnings": []}
    return {"status": "loaded", "review_id": effective_review_id, "review": payload, "warnings": []}


def get_citation_draft_review_health(
    workspace_id: str | None = None,
    document_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_review_dirs(root)
    reviews = []
    warnings = []
    divergent = 0
    for path in sorted((base / REVIEW_DIR).glob("citation_review_*.json")):
        payload = _read_json(path)
        if not isinstance(payload, Mapping):
            continue
        if workspace_id and payload.get("workspace_id") != workspace_id:
            continue
        if document_id and payload.get("document_id") != document_id:
            continue
        reviews.append(payload)
        if payload.get("review_status") == "created":
            citation_id = str(payload.get("real_citation_id") or "")
            if not citation_id or not _citation_path(base, citation_id).exists():
                divergent += 1
    pending_handoffs = [item for item in _load_handoffs(base) if item.get("status") == "pending_evidence_review" and (not document_id or item.get("document_id") == document_id)]
    approved_pending = [item for item in reviews if item.get("review_status") == "approved"]
    if approved_pending:
        warnings.append("one_approved_draft_has_not_been_created")
    status = "empty" if not reviews and not pending_handoffs else "warning" if warnings else "healthy"
    if divergent:
        status = "blocked"
    return {
        "status": status,
        "review_count": len(reviews),
        "pending_count": sum(1 for item in reviews if item.get("review_status") == "pending"),
        "approved_count": sum(1 for item in reviews if item.get("review_status") == "approved"),
        "created_count": sum(1 for item in reviews if item.get("review_status") == "created"),
        "rejected_count": sum(1 for item in reviews if item.get("review_status") == "rejected"),
        "changes_requested_count": sum(1 for item in reviews if item.get("review_status") == "changes_requested"),
        "pending_handoff_count": len(pending_handoffs),
        "divergent_state_count": divergent,
        "warnings": warnings,
        "recommended_action": "Review one approved draft awaiting citation creation." if approved_pending else "No action required.",
    }


def format_citation_draft_review_report(
    review_id: str | None = None,
    workspace_id: str | None = None,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    base = _ensure_review_dirs(root)
    review_payload = load_citation_draft_review(review_id=review_id, root=base) if review_id else None
    review = review_payload.get("review") if isinstance(review_payload, Mapping) else None
    if not isinstance(review, Mapping) and workspace_id:
        for path in sorted((base / REVIEW_DIR).glob("citation_review_*.json")):
            payload = _read_json(path)
            if isinstance(payload, Mapping) and payload.get("workspace_id") == workspace_id:
                review = payload
                break
    if not isinstance(review, Mapping):
        text = "Citation Draft Review Report\n\nReview unavailable."
        return _sanitize(text) if public_safe else text
    review_workspace = build_citation_draft_review_workspace(str(review.get("workspace_id") or ""), str(review.get("citation_draft_id") or ""), root=base)
    handoff = _load_handoff_by_id(str(review.get("evidence_handoff_id") or ""), root=base)
    lines = [
        "Citation Draft Review Report",
        "",
        f"Document: {review_workspace.get('document_id')}",
        f"Source Revision: {review_workspace.get('source_revision')}",
        f"Workspace: {review_workspace.get('provenance_status')}",
        "",
        "Draft:",
        f"- Status: {review_workspace.get('draft_status')}",
        f"- Page: {(review_workspace.get('page') if review_workspace.get('page') is not None else 'unknown')}",
        f"- Provenance: {review_workspace.get('provenance_status')}",
        f"- Duplicate Status: {review_workspace.get('duplicate_status')}",
        "",
        "Review:",
        f"- Decision: {review.get('decision')}",
        f"- Review Revision: {review.get('review_revision')}",
        "",
        "Citation Creation:",
        f"- Status: {review.get('review_status')}",
        f"- Citation ID: {review.get('real_citation_id') or 'none'}",
        "",
        "Evidence Handoff:",
        f"- Status: {(handoff or {}).get('status', 'none')}",
        "- Added to Binder: No",
        "- Proposal Created: No",
        "",
        "Important:",
        "The citation was created only after explicit review and confirmation.",
        "No evidence binder was modified.",
        "",
        "Recommended Action:",
        "Review the pending evidence handoff." if (handoff or {}).get("status") == "pending_evidence_review" else "Complete review or create the citation after approval.",
    ]
    text = "\n".join(lines)
    return _sanitize(text) if public_safe else text


def _find_draft(workspace: Any, citation_draft_id: str) -> dict[str, Any] | None:
    if not isinstance(workspace, Mapping):
        return None
    for draft in workspace.get("citation_drafts", []):
        if isinstance(draft, Mapping) and str(draft.get("citation_draft_id") or "") == citation_draft_id:
            return dict(draft)
    return None


def _load_workspace_for_review(workspace_id: str, *, root: Path) -> dict[str, Any]:
    loaded = load_pdf_reader_workspace(workspace_id, root=root)
    if loaded.get("status") in {"current", "warning"}:
        return loaded
    payload = _read_json(_workspace_path(root, workspace_id))
    if not isinstance(payload, Mapping):
        return loaded
    blockers = []
    record = load_source_document(str(payload.get("document_id") or ""), root=root, missing_ok=True)
    if record is None:
        blockers.append("document_not_found")
    else:
        if payload.get("source_hash") != record.sha256:
            blockers.append("source_hash_changed")
    return {
        "status": "stale" if any(item in {"source_hash_changed"} for item in blockers) else "current",
        "workspace_id": workspace_id,
        "workspace": payload,
        "warnings": [],
        "blockers": blockers,
    }


def _load_citations(root: Path) -> list[dict[str, Any]]:
    base = ensure_source_knowledge_dirs(root)
    citations = []
    for path in sorted((base / "citations").glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping):
            citations.append(dict(payload))
    return citations


def _citation_id(draft: Mapping[str, Any]) -> str:
    return "citation_" + _hash_payload(
        {
            "document_id": draft.get("document_id"),
            "chunk_id": draft.get("chunk_id"),
            "page": draft.get("page"),
            "start_offset": draft.get("start_offset"),
            "end_offset": draft.get("end_offset"),
            "selected_text_hash": draft.get("selected_text_hash"),
        }
    )[7:23]


def _review_id(workspace_id: str, citation_draft_id: str) -> str:
    return "citation_review_" + _hash_payload({"workspace_id": workspace_id, "citation_draft_id": citation_draft_id})[7:23]


def _ranges_overlap(a_start: Any, a_end: Any, b_start: Any, b_end: Any) -> bool:
    a0 = _normalize_non_negative_int(a_start)
    a1 = _normalize_non_negative_int(a_end)
    b0 = _normalize_non_negative_int(b_start)
    b1 = _normalize_non_negative_int(b_end)
    return None not in {a0, a1, b0, b1} and a0 < b1 and b0 < a1


def _apply_workspace_draft_created(workspace: dict[str, Any], citation_draft_id: str, citation_id: str, review_id: str, handoff_id: str) -> bool:
    updated = False
    for draft in workspace.get("citation_drafts", []):
        if isinstance(draft, dict) and str(draft.get("citation_draft_id") or "") == citation_draft_id:
            draft["status"] = "created"
            draft["real_citation_id"] = citation_id
            draft["review_id"] = review_id
            draft["evidence_handoff_id"] = handoff_id
            draft["created_as_citation_at_utc"] = _now()
            updated = True
            break
    if updated:
        workspace["workspace_revision"] = int(workspace.get("workspace_revision") or 0) + 1
        workspace["updated_at_utc"] = _now()
    return updated


def _update_workspace_draft_state(root: Path, workspace: dict[str, Any], citation_draft_id: str, status: str, *, review_id: str) -> None:
    changed = False
    for draft in workspace.get("citation_drafts", []):
        if isinstance(draft, dict) and str(draft.get("citation_draft_id") or "") == citation_draft_id:
            if draft.get("status") != status or draft.get("review_id") != review_id:
                draft["status"] = status
                draft["review_id"] = review_id
                changed = True
            break
    if changed:
        workspace["workspace_revision"] = int(workspace.get("workspace_revision") or 0) + 1
        workspace["updated_at_utc"] = _now()
        _atomic_write_json(_workspace_path(root, str(workspace.get("workspace_id") or "")), workspace)


def _rebuild_citation_index(root: Path) -> None:
    entries = []
    for citation in _load_citations(root):
        entries.append(
            {
                "citation_id": citation.get("citation_id"),
                "document_id": citation.get("document_id"),
                "chunk_id": citation.get("chunk_id"),
                "page_start": citation.get("page_start"),
                "page_end": citation.get("page_end"),
                "created_at_utc": citation.get("created_at_utc"),
            }
        )
    _atomic_write_json(root / "indexes" / "citation_index.json", {"entries": entries})


def _load_handoffs(root: Path) -> list[dict[str, Any]]:
    items = []
    for path in sorted((root / HANDOFF_DIR).glob("citation_handoff_*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping):
            items.append(dict(payload))
    return items


def _load_handoff_for_draft(workspace_id: str, citation_draft_id: str, *, root: Path) -> dict[str, Any] | None:
    for item in _load_handoffs(root):
        if item.get("source_workspace_id") == workspace_id and item.get("source_citation_draft_id") == citation_draft_id:
            return item
    return None


def _load_handoff_by_id(handoff_id: str, *, root: Path) -> dict[str, Any] | None:
    if not handoff_id:
        return None
    payload = _read_json(_handoff_path(root, handoff_id))
    return dict(payload) if isinstance(payload, Mapping) else None


def _update_review_index(root: Path) -> None:
    entries = []
    for path in sorted((root / REVIEW_DIR).glob("citation_review_*.json")):
        payload = _read_json(path)
        if not isinstance(payload, Mapping):
            continue
        entries.append(
            {
                "review_id": payload.get("review_id"),
                "workspace_id": payload.get("workspace_id"),
                "citation_draft_id": payload.get("citation_draft_id"),
                "document_id": payload.get("document_id"),
                "source_revision": payload.get("source_revision"),
                "review_status": payload.get("review_status"),
                "updated_at_utc": payload.get("updated_at_utc"),
            }
        )
    _atomic_write_json(root / "indexes" / REVIEW_INDEX, {"entries": entries, "updated_at_utc": _now()})


def _update_handoff_index(root: Path) -> None:
    entries = []
    for item in _load_handoffs(root):
        entries.append(
            {
                "evidence_handoff_id": item.get("evidence_handoff_id"),
                "citation_id": item.get("citation_id"),
                "document_id": item.get("document_id"),
                "source_workspace_id": item.get("source_workspace_id"),
                "source_citation_draft_id": item.get("source_citation_draft_id"),
                "status": item.get("status"),
                "updated_at_utc": item.get("updated_at_utc"),
            }
        )
    _atomic_write_json(root / "indexes" / HANDOFF_INDEX, {"entries": entries, "updated_at_utc": _now()})


def _review_path(root: Path, review_id: str) -> Path:
    return root / REVIEW_DIR / f"{review_id}.json"


def _handoff_path(root: Path, handoff_id: str) -> Path:
    return root / HANDOFF_DIR / f"{handoff_id}.json"


def _workspace_path(root: Path, workspace_id: str) -> Path:
    return root / "pdf_reader_workspaces" / f"{workspace_id}.json"


def _citation_path(root: Path, citation_id: str) -> Path:
    return ensure_source_knowledge_dirs(root) / "citations" / f"{citation_id}.json"


def _ensure_review_dirs(root: Path | str) -> Path:
    base = _ensure_dirs(root)
    ensure_source_knowledge_dirs(base)
    (base / REVIEW_DIR).mkdir(parents=True, exist_ok=True)
    (base / HANDOFF_DIR).mkdir(parents=True, exist_ok=True)
    for index_name in (REVIEW_INDEX, HANDOFF_INDEX):
        path = base / "indexes" / index_name
        if not path.exists():
            _atomic_write_json(path, {"entries": [], "updated_at_utc": _now()})
    return base


def _restore_json(path: Path, payload: Any) -> None:
    if payload is None:
        if path.exists():
            path.unlink()
        return
    _atomic_write_json(path, payload)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
    tmp.replace(path)


def _normalize_positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return int(value)


def _normalize_non_negative_int(value: Any) -> int | None:
    normalized = _normalize_positive_int(value)
    if normalized is None or normalized < 0:
        return None
    return normalized


def _sanitize(text: str) -> str:
    sanitized = str(text)
    for needle in ("C:\\", "/Users/", "pdf_sources", "citation_draft_reviews", "citation_evidence_handoffs", "Traceback", "token=", "secret"):
        sanitized = sanitized.replace(needle, "" if needle != "token=" else "[redacted]")
    return sanitized


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
