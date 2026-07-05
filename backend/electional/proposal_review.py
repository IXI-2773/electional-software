"""Manual proposal review governance for source-backed document proposals."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping

from .document_preflight import get_document_preflight_summary
from .source_documents import SOURCE_DOCUMENT_ROOT, load_source_document
from .source_knowledge import ensure_source_knowledge_dirs, list_source_proposals, load_chunk

SCHEMA_VERSION = "proposal_review_v1"
REVIEW_DIRS = ("proposal_reviews", "indexes")
VALID_REVIEW_STATUSES = {
    "pending_review",
    "in_review",
    "approved_for_later_promotion",
    "rejected",
    "deferred",
    "needs_more_source",
    "needs_better_citation",
    "duplicate",
    "conflict_review",
}
VALID_REVIEW_DECISIONS = {
    "not_decided",
    "approve",
    "reject",
    "defer",
    "needs_more_source",
    "needs_better_citation",
    "mark_duplicate",
    "mark_conflict_review",
}
POSITIVE_WORDS = {"allow", "proceed", "approve", "use", "accept", "valid", "ready"}
NEGATIVE_WORDS = {"reject", "block", "avoid", "invalid", "unsafe", "forbidden", "fail"}
CONDITIONAL_WORDS = {"unless", "exception", "only if", "requires", "needs review", "caution"}


@dataclass(frozen=True)
class ProposalReviewRecord:
    proposal_id: str
    review_id: str
    created_at_utc: str
    updated_at_utc: str
    review_status: str
    review_decision: str
    citation_strength: dict[str, object]
    duplicate_check: dict[str, object]
    conflict_check: dict[str, object]
    promotion_readiness: dict[str, object]
    review_notes: tuple[dict[str, object], ...]
    warnings: tuple[str, ...]
    blockers: tuple[str, ...]
    schema_version: str = SCHEMA_VERSION

    def to_json(self, *, public_safe: bool = False) -> dict[str, object]:
        payload = asdict(self)
        payload["review_notes"] = [dict(item) for item in self.review_notes]
        payload["warnings"] = list(self.warnings)
        payload["blockers"] = list(self.blockers)
        if public_safe:
            payload["review_notes"] = [{"note_id": note.get("note_id"), "note_type": note.get("note_type"), "created_at_utc": note.get("created_at_utc")} for note in self.review_notes]
        return payload


def ensure_proposal_review_dirs(root: Path | str = SOURCE_DOCUMENT_ROOT) -> Path:
    base = ensure_source_knowledge_dirs(root)
    for folder in REVIEW_DIRS:
        (base / folder).mkdir(parents=True, exist_ok=True)
    return base


def load_proposal_review(proposal_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT, missing_ok: bool = True) -> ProposalReviewRecord | None:
    path = _review_path(ensure_proposal_review_dirs(root), proposal_id)
    if not path.exists():
        if missing_ok:
            return None
        raise FileNotFoundError(str(path))
    return _review_from_json(json.loads(path.read_text(encoding="utf-8")))


def score_citation_strength(proposal_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_proposal_review_dirs(root)
    proposal = _get_proposal(proposal_id, base)
    citations = _citations_for_proposal(proposal, base)
    strengths: list[str] = []
    weaknesses: list[str] = []
    blockers: list[str] = []
    score = 0
    if not citations:
        blockers.append("no_citation")
        return _citation_strength_payload(0, strengths, weaknesses, blockers)
    citation = citations[0]
    document_id = str(citation.get("document_id") or "")
    chunk_id = str(citation.get("chunk_id") or "")
    excerpt = str(citation.get("quote_excerpt") or "")
    if document_id:
        strengths.append("citation_links_document")
        score += 15
    else:
        blockers.append("missing_document_id")
    if chunk_id:
        strengths.append("citation_links_chunk")
        score += 15
    else:
        blockers.append("missing_chunk_id")
    document = load_source_document(document_id, root=base, missing_ok=True) if document_id else None
    if document:
        strengths.append("source_document_exists")
        score += 10
        if document.sha256:
            strengths.append("document_hash_present")
            score += 5
        if document.original_filename:
            strengths.append("source_title_present")
            score += 5
    else:
        blockers.append("missing_source_document")
    chunk = None
    if chunk_id:
        try:
            chunk = load_chunk(chunk_id, root=base)
            strengths.append("chunk_exists")
            score += 10
        except Exception:
            blockers.append("missing_chunk")
    if citation.get("page_start") is not None or (chunk and chunk.page_start is not None):
        strengths.append("page_reference_present")
        score += 10
    else:
        weaknesses.append("page_reference_unavailable")
    if excerpt.strip():
        strengths.append("quote_excerpt_present")
        score += 15
        strengths.append("excerpt_hash_present")
        score += 5
        if len(excerpt) > 500:
            weaknesses.append("excerpt_too_long")
            score -= 10
    else:
        blockers.append("empty_excerpt")
    preflight = get_document_preflight_summary(document_id, root=base) if document_id else {}
    if preflight.get("verdict") == "PASS":
        strengths.append("preflight_passed")
        score += 10
    elif preflight.get("verdict") == "WARNING":
        weaknesses.append("preflight_warning")
        score += 5
    elif preflight.get("has_preflight"):
        weaknesses.append("preflight_not_clean")
    else:
        weaknesses.append("preflight_missing")
    extraction_score = int(preflight.get("extraction_quality_score") or 0)
    chunk_score = int(preflight.get("chunk_readiness_score") or 0)
    citation_score = int(preflight.get("citation_readiness_score") or 0)
    if extraction_score and extraction_score < 75:
        weaknesses.append("weak_extraction_quality")
    if chunk_score and chunk_score < 75:
        weaknesses.append("weak_chunk_readiness")
    if citation_score and citation_score < 75:
        weaknesses.append("citation_readiness_below_high")
    if preflight.get("privacy_status") == "warning":
        weaknesses.append("privacy_warning_present")
        score -= 5
    if blockers:
        score = min(score, 24)
    return _citation_strength_payload(score, strengths, weaknesses, blockers)


def get_proposal_review_summary(proposal_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_proposal_review_dirs(root)
    proposal = _get_proposal(proposal_id, base)
    review = _ensure_review(proposal_id, base)
    citation = score_citation_strength(proposal_id, root=base)
    duplicate = detect_duplicate_proposals(proposal_id, root=base)
    conflict = detect_proposal_conflicts(proposal_id, root=base)
    readiness = calculate_promotion_readiness(proposal_id, root=base, _components=(citation, duplicate, conflict, review))
    recommended = _recommended_action(citation, duplicate, conflict, readiness)
    return {
        "proposal_id": proposal_id,
        "status": review.review_status,
        "claim_preview": _preview(proposal.claim),
        "has_citation": citation["score"] > 0 and "no_citation" not in citation.get("blockers", []),
        "citation_strength_band": citation["band"],
        "duplicate_status": duplicate["status"],
        "conflict_status": conflict["status"],
        "promotion_readiness_band": readiness["band"],
        "recommended_action": recommended,
        "warning_count": len(citation.get("weaknesses", [])) + len(duplicate.get("warnings", [])) + len(conflict.get("warnings", [])) + len(readiness.get("warnings", [])),
        "blocker_count": len(citation.get("blockers", [])) + len(readiness.get("blockers", [])),
        "warnings": list(readiness.get("warnings", [])),
        "blockers": list(readiness.get("blockers", [])),
    }


def detect_duplicate_proposals(proposal_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_proposal_review_dirs(root)
    proposal = _get_proposal(proposal_id, base)
    claim_sig = _normalize_claim(proposal.claim)
    matches = []
    for other in list_source_proposals(root=base):
        if other.proposal_id == proposal_id:
            continue
        if _normalize_claim(other.claim) == claim_sig:
            matches.append({"proposal_id": other.proposal_id, "reason": "same_normalized_claim", "confidence": "high"})
        elif other.document_id == proposal.document_id and other.chunk_id == proposal.chunk_id and other.proposal_type == proposal.proposal_type:
            matches.append({"proposal_id": other.proposal_id, "reason": "same_source_chunk_and_type", "confidence": "medium"})
    status = "possible_duplicate" if matches else "none"
    _write_index(base, "proposal_duplicate_index.json", proposal_id, status, matches)
    return {"status": status, "matches": matches, "warnings": []}


def detect_proposal_conflicts(proposal_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_proposal_review_dirs(root)
    proposal = _get_proposal(proposal_id, base)
    category = _decision_category(proposal.claim)
    key_terms = _key_terms(proposal.claim)
    matches = []
    if category == "neutral":
        result = {"status": "none", "matches": [], "warnings": []}
        _write_index(base, "proposal_conflict_index.json", proposal_id, result["status"], [])
        return result
    for other in list_source_proposals(root=base):
        if other.proposal_id == proposal_id:
            continue
        other_category = _decision_category(other.claim)
        if not _opposite_categories(category, other_category):
            continue
        overlap = key_terms & _key_terms(other.claim)
        if overlap:
            matches.append({"proposal_id": other.proposal_id, "reason": "opposite_decision_words_same_key_term", "confidence": "medium", "terms": sorted(overlap)[:5]})
    status = "possible_conflict" if matches else "none"
    _write_index(base, "proposal_conflict_index.json", proposal_id, status, matches)
    return {"status": status, "matches": matches, "warnings": []}


def update_proposal_review_status(proposal_id: str, review_status: str, decision: str, note: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> ProposalReviewRecord:
    if review_status not in VALID_REVIEW_STATUSES:
        raise ValueError(f"Unsupported review status: {review_status}")
    if decision not in VALID_REVIEW_DECISIONS:
        raise ValueError(f"Unsupported review decision: {decision}")
    base = ensure_proposal_review_dirs(root)
    review = _ensure_review(proposal_id, base)
    notes = list(review.review_notes)
    if note and note.strip():
        notes.append(_note(note, "review_decision"))
    updated = ProposalReviewRecord(
        proposal_id=proposal_id,
        review_id=review.review_id,
        created_at_utc=review.created_at_utc,
        updated_at_utc=_now(),
        review_status=review_status,
        review_decision=decision,
        citation_strength=score_citation_strength(proposal_id, root=base),
        duplicate_check=detect_duplicate_proposals(proposal_id, root=base),
        conflict_check=detect_proposal_conflicts(proposal_id, root=base),
        promotion_readiness={},
        review_notes=tuple(notes),
        warnings=review.warnings,
        blockers=review.blockers,
    )
    readiness = calculate_promotion_readiness(proposal_id, root=base, _components=(updated.citation_strength, updated.duplicate_check, updated.conflict_check, updated))
    updated = _replace_readiness(updated, readiness)
    _save_review(updated, base)
    return updated


def add_proposal_review_note(proposal_id: str, note: str, note_type: str = "manual", *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> ProposalReviewRecord:
    if note_type not in {"manual", "citation_issue", "duplicate_issue", "conflict_issue", "source_issue", "review_decision"}:
        raise ValueError(f"Unsupported note type: {note_type}")
    if not note.strip():
        raise ValueError("Review note text is required.")
    base = ensure_proposal_review_dirs(root)
    review = _ensure_review(proposal_id, base)
    updated = ProposalReviewRecord(
        proposal_id=review.proposal_id,
        review_id=review.review_id,
        created_at_utc=review.created_at_utc,
        updated_at_utc=_now(),
        review_status=review.review_status,
        review_decision=review.review_decision,
        citation_strength=review.citation_strength,
        duplicate_check=review.duplicate_check,
        conflict_check=review.conflict_check,
        promotion_readiness=review.promotion_readiness,
        review_notes=(*review.review_notes, _note(note, note_type)),
        warnings=review.warnings,
        blockers=review.blockers,
    )
    _save_review(updated, base)
    return updated


def calculate_promotion_readiness(proposal_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT, _components: tuple | None = None) -> dict[str, object]:
    base = ensure_proposal_review_dirs(root)
    if _components:
        citation, duplicate, conflict, review = _components
    else:
        review = _ensure_review(proposal_id, base)
        citation = score_citation_strength(proposal_id, root=base)
        duplicate = detect_duplicate_proposals(proposal_id, root=base)
        conflict = detect_proposal_conflicts(proposal_id, root=base)
    score = 35
    blockers: list[str] = []
    warnings: list[str] = []
    required: list[str] = []
    citation_score = int(citation.get("score", 0) or 0)
    score += min(35, citation_score // 3)
    if citation.get("blockers"):
        blockers.extend(str(item) for item in citation.get("blockers", []))
    if citation_score < 75:
        required.append("improve_citation_strength")
    if duplicate.get("status") in {"possible_duplicate", "duplicate"}:
        blockers.append("duplicate_unresolved")
        required.append("resolve_duplicate")
    if conflict.get("status") in {"possible_conflict", "conflict_review"}:
        blockers.append("possible_conflict_unresolved")
        required.append("resolve_possible_conflict")
    if review.review_status in {"rejected", "needs_more_source", "needs_better_citation", "duplicate", "conflict_review"}:
        blockers.append(f"review_status_{review.review_status}")
    if review.review_notes:
        score += 10
    else:
        warnings.append("no_review_note")
        required.append("add_review_note")
    if review.review_status == "approved_for_later_promotion":
        score += 10
    if blockers:
        score = min(score, 49)
    score = max(0, min(100, score))
    band = _readiness_band(score)
    return {
        "score": score,
        "band": band,
        "status": "blocked" if blockers else "warning" if warnings or required else "ready",
        "ready_for_promotion_review": bool(score >= 75 and not blockers),
        "required_actions": list(dict.fromkeys(required)),
        "warnings": list(dict.fromkeys(warnings)),
        "blockers": list(dict.fromkeys(blockers)),
    }


def list_proposal_review_queue(status: str | None = None, readiness_band: str | None = None, limit: int = 50, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> list[dict[str, object]]:
    base = ensure_proposal_review_dirs(root)
    items = []
    for proposal in list_source_proposals(root=base):
        summary = get_proposal_review_summary(proposal.proposal_id, root=base)
        if status and summary["status"] != status:
            continue
        if readiness_band and summary["promotion_readiness_band"] != readiness_band:
            continue
        items.append(summary)
    items.sort(key=lambda item: (-int(item.get("blocker_count", 0)), -int(item.get("warning_count", 0)), str(item.get("proposal_id"))))
    return items[: max(0, int(limit or 0))]


def get_proposal_review_ui_state(
    status: str | None = None,
    readiness_band: str | None = None,
    conflict_status: str | None = None,
    duplicate_status: str | None = None,
    limit: int = 50,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, object]:
    """Return a compact, UI-safe proposal review queue state."""
    normalized_status = _normalize_filter(status)
    normalized_readiness = _normalize_filter(readiness_band)
    normalized_conflict = _normalize_filter(conflict_status)
    normalized_duplicate = _normalize_filter(duplicate_status)
    warnings: list[str] = []
    try:
        items = list_proposal_review_queue(normalized_status, normalized_readiness, max(int(limit or 0), 1), root=root)
    except Exception as exc:
        return {
            "queue_count": 0,
            "filters": {
                "status": normalized_status,
                "readiness_band": normalized_readiness,
                "conflict_status": normalized_conflict,
                "duplicate_status": normalized_duplicate,
            },
            "items": [],
            "warnings": [f"proposal_review_queue_unavailable: {exc}"],
        }
    filtered: list[dict[str, object]] = []
    for item in items:
        if normalized_conflict and item.get("conflict_status") != normalized_conflict:
            continue
        if normalized_duplicate and item.get("duplicate_status") != normalized_duplicate:
            continue
        filtered.append(_ui_safe_queue_item(item))
    if not filtered:
        warnings.append("no_proposals_match_current_filters")
    return {
        "queue_count": len(filtered),
        "filters": {
            "status": normalized_status,
            "readiness_band": normalized_readiness,
            "conflict_status": normalized_conflict,
            "duplicate_status": normalized_duplicate,
        },
        "items": filtered[: max(0, int(limit or 0))],
        "warnings": warnings,
    }


def select_proposal_for_review_ui(proposal_id: str | None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    """Return selected proposal detail without source text or local paths."""
    if not proposal_id:
        return {"selected": False, "message": "No proposal selected.", "warnings": ["no_proposal_selected"]}
    try:
        summary = get_proposal_review_summary(proposal_id, root=root)
        review = load_proposal_review(proposal_id, root=root) or _ensure_review(proposal_id, ensure_proposal_review_dirs(root))
        citation_strength = score_citation_strength(proposal_id, root=root)
        duplicate_check = detect_duplicate_proposals(proposal_id, root=root)
        conflict_check = detect_proposal_conflicts(proposal_id, root=root)
        promotion_readiness = calculate_promotion_readiness(proposal_id, root=root)
        review = load_proposal_review(proposal_id, root=root) or review
    except FileNotFoundError:
        return {"selected": False, "message": "No proposal selected.", "warnings": ["proposal_not_found"]}
    except Exception as exc:
        return {"selected": False, "message": "Proposal unavailable.", "warnings": [f"proposal_review_unavailable: {exc}"]}
    warnings = list(dict.fromkeys([*summary.get("warnings", []), *promotion_readiness.get("warnings", [])]))
    blockers = list(dict.fromkeys([*summary.get("blockers", []), *promotion_readiness.get("blockers", [])]))
    return {
        "selected": True,
        "proposal_id": proposal_id,
        "review_status": review.review_status,
        "claim_preview": summary.get("claim_preview", ""),
        "citation_strength": citation_strength,
        "duplicate_check": duplicate_check,
        "conflict_check": conflict_check,
        "promotion_readiness": promotion_readiness,
        "review_notes": list(review.review_notes),
        "recommended_action": summary.get("recommended_action", ""),
        "available_actions": [
            "in_review",
            "needs_more_source",
            "needs_better_citation",
            "reject",
            "defer",
            "mark_duplicate",
            "mark_conflict_review",
            "approve_for_later_promotion",
        ],
        "warnings": warnings,
        "blockers": blockers,
    }


def apply_proposal_review_ui_action(proposal_id: str | None, action: str, note: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    """Apply a manual review action and return refreshed selected-proposal state."""
    if not proposal_id:
        return {"selected": False, "message": "No proposal selected.", "warnings": ["no_proposal_selected"]}
    action_map = {
        "in_review": ("in_review", "not_decided"),
        "needs_more_source": ("needs_more_source", "needs_more_source"),
        "needs_better_citation": ("needs_better_citation", "needs_better_citation"),
        "reject": ("rejected", "reject"),
        "defer": ("deferred", "defer"),
        "mark_duplicate": ("duplicate", "mark_duplicate"),
        "mark_conflict_review": ("conflict_review", "mark_conflict_review"),
        "approve_for_later_promotion": ("approved_for_later_promotion", "approve"),
    }
    if action not in action_map:
        return {"selected": False, "message": "Unsupported review action.", "warnings": [f"unsupported_review_action: {action}"]}
    review_status, decision = action_map[action]
    try:
        update_proposal_review_status(proposal_id, review_status, decision, note, root=root)
    except FileNotFoundError:
        return {"selected": False, "message": "No proposal selected.", "warnings": ["proposal_not_found"]}
    return select_proposal_for_review_ui(proposal_id, root=root)


def copy_proposal_review_summary(proposal_id: str | None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> str:
    """Build a public-safe review summary for clipboard/export use."""
    selected = select_proposal_for_review_ui(proposal_id, root=root)
    if not selected.get("selected"):
        return "Proposal Review Summary\n\nNo proposal selected."
    citation = selected.get("citation_strength") if isinstance(selected.get("citation_strength"), Mapping) else {}
    duplicate = selected.get("duplicate_check") if isinstance(selected.get("duplicate_check"), Mapping) else {}
    conflict = selected.get("conflict_check") if isinstance(selected.get("conflict_check"), Mapping) else {}
    readiness = selected.get("promotion_readiness") if isinstance(selected.get("promotion_readiness"), Mapping) else {}
    warnings = selected.get("warnings") if isinstance(selected.get("warnings"), list) else []
    blockers = selected.get("blockers") if isinstance(selected.get("blockers"), list) else []
    notes = selected.get("review_notes") if isinstance(selected.get("review_notes"), list) else []
    return "\n".join(
        [
            "Proposal Review Summary",
            "",
            f"Proposal ID: {selected.get('proposal_id')}",
            f"Review Status: {selected.get('review_status')}",
            f"Citation Strength: {citation.get('band', 'unknown')}",
            f"Duplicate Status: {duplicate.get('status', 'unknown')}",
            f"Conflict Status: {conflict.get('status', 'unknown')}",
            f"Promotion Readiness: {readiness.get('band', 'unknown')}",
            f"Recommended Action: {selected.get('recommended_action')}",
            f"Warnings: {', '.join(str(item) for item in warnings) if warnings else 'None'}",
            f"Blockers: {', '.join(str(item) for item in blockers) if blockers else 'None'}",
            f"Review Note Count: {len(notes)}",
        ]
    )

def _normalize_filter(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned or cleaned.lower() == "any":
        return None
    return cleaned


def _ui_safe_queue_item(item: Mapping[str, object]) -> dict[str, object]:
    return {
        "proposal_id": item.get("proposal_id"),
        "review_status": item.get("status") or item.get("review_status"),
        "claim_preview": str(item.get("claim_preview") or "")[:180],
        "citation_strength_band": item.get("citation_strength_band"),
        "duplicate_status": item.get("duplicate_status"),
        "conflict_status": item.get("conflict_status"),
        "promotion_readiness_band": item.get("promotion_readiness_band"),
        "recommended_action": item.get("recommended_action"),
        "warning_count": int(item.get("warning_count", 0) or 0),
        "blocker_count": int(item.get("blocker_count", 0) or 0),
    }

def _ensure_review(proposal_id: str, root: Path) -> ProposalReviewRecord:
    existing = load_proposal_review(proposal_id, root=root, missing_ok=True)
    if existing:
        return existing
    _get_proposal(proposal_id, root)
    now = _now()
    review = ProposalReviewRecord(
        proposal_id=proposal_id,
        review_id=f"review_{proposal_id}",
        created_at_utc=now,
        updated_at_utc=now,
        review_status="pending_review",
        review_decision="not_decided",
        citation_strength={},
        duplicate_check={},
        conflict_check={},
        promotion_readiness={},
        review_notes=(),
        warnings=(),
        blockers=(),
    )
    _save_review(review, root)
    return review


def _save_review(review: ProposalReviewRecord, root: Path) -> None:
    _atomic_write_json(_review_path(root, review.proposal_id), review.to_json())
    _update_review_index(root)


def _replace_readiness(review: ProposalReviewRecord, readiness: dict[str, object]) -> ProposalReviewRecord:
    return ProposalReviewRecord(**{**review.to_json(), "promotion_readiness": readiness, "review_notes": tuple(review.review_notes), "warnings": review.warnings, "blockers": review.blockers})


def _get_proposal(proposal_id: str, root: Path):
    for proposal in list_source_proposals(root=root):
        if proposal.proposal_id == proposal_id:
            return proposal
    raise FileNotFoundError(proposal_id)


def _citations_for_proposal(proposal, root: Path) -> list[dict[str, object]]:
    rows = []
    for path in sorted((root / "citations").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("document_id") == proposal.document_id and data.get("chunk_id") == proposal.chunk_id:
            rows.append(data)
    return rows


def _citation_strength_payload(score: int, strengths: list[str], weaknesses: list[str], blockers: list[str]) -> dict[str, object]:
    score = max(0, min(100, int(score)))
    return {
        "score": score,
        "band": _score_band(score),
        "status": "blocked" if blockers else "warning" if weaknesses else "ok",
        "strengths": list(dict.fromkeys(strengths)),
        "weaknesses": list(dict.fromkeys(weaknesses)),
        "blockers": list(dict.fromkeys(blockers)),
    }


def _score_band(score: int) -> str:
    return "strong" if score >= 90 else "usable" if score >= 75 else "weak" if score >= 50 else "poor" if score >= 25 else "unusable"


def _readiness_band(score: int) -> str:
    return "ready" if score >= 90 else "review_ready" if score >= 75 else "not_ready" if score >= 50 else "weak" if score >= 25 else "blocked"


def _recommended_action(citation: Mapping[str, object], duplicate: Mapping[str, object], conflict: Mapping[str, object], readiness: Mapping[str, object]) -> str:
    if duplicate.get("status") != "none":
        return "Review possible duplicate before approval."
    if conflict.get("status") != "none":
        return "Review possible conflict before approval."
    if citation.get("band") in {"unusable", "poor", "weak"}:
        return "Improve citation strength before approval."
    if readiness.get("ready_for_promotion_review"):
        return "Ready for human promotion review; no automatic promotion occurs."
    return "Continue manual review."


def _normalize_claim(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", value.lower())).strip()


def _decision_category(text: str) -> str:
    lower = text.lower()
    pos = any(word in lower for word in POSITIVE_WORDS)
    neg = any(word in lower for word in NEGATIVE_WORDS)
    cond = any(word in lower for word in CONDITIONAL_WORDS)
    if pos and not neg:
        return "positive"
    if neg and not pos:
        return "negative"
    if cond:
        return "conditional"
    return "neutral"


def _opposite_categories(left: str, right: str) -> bool:
    return {left, right} == {"positive", "negative"}


def _key_terms(text: str) -> set[str]:
    stop = POSITIVE_WORDS | NEGATIVE_WORDS | CONDITIONAL_WORDS | {"the", "and", "for", "from", "with", "this", "that", "before", "after", "proposal", "citation"}
    return {word for word in re.findall(r"[a-z0-9]+", text.lower()) if len(word) > 3 and word not in stop}


def _preview(text: str, limit: int = 140) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    return clean if len(clean) <= limit else clean[: limit - 3].rstrip() + "..."


def _note(text: str, note_type: str) -> dict[str, object]:
    clean = _preview(text, 500)
    return {"note_id": "note_" + _hash_text(clean + note_type)[7:23], "created_at_utc": _now(), "note_type": note_type, "text": clean}


def _review_from_json(data: Mapping[str, object]) -> ProposalReviewRecord:
    return ProposalReviewRecord(
        proposal_id=str(data["proposal_id"]),
        review_id=str(data.get("review_id") or f"review_{data['proposal_id']}"),
        created_at_utc=str(data.get("created_at_utc") or _now()),
        updated_at_utc=str(data.get("updated_at_utc") or _now()),
        review_status=str(data.get("review_status") or "pending_review"),
        review_decision=str(data.get("review_decision") or "not_decided"),
        citation_strength=dict(data.get("citation_strength") or {}),
        duplicate_check=dict(data.get("duplicate_check") or {}),
        conflict_check=dict(data.get("conflict_check") or {}),
        promotion_readiness=dict(data.get("promotion_readiness") or {}),
        review_notes=tuple(dict(item) for item in data.get("review_notes", []) if isinstance(item, Mapping)),
        warnings=tuple(str(item) for item in data.get("warnings", []) if item),
        blockers=tuple(str(item) for item in data.get("blockers", []) if item),
    )


def _update_review_index(root: Path) -> None:
    entries = []
    for path in sorted((root / "proposal_reviews").glob("*.json")):
        try:
            review = _review_from_json(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
        entries.append({"proposal_id": review.proposal_id, "review_status": review.review_status, "review_decision": review.review_decision, "updated_at_utc": review.updated_at_utc, "path": str(path)})
    _atomic_write_json(root / "indexes" / "proposal_review_index.json", {"entries": entries})


def _write_index(root: Path, index_name: str, proposal_id: str, status: str, matches: list[dict[str, object]]) -> None:
    path = root / "indexes" / index_name
    payload = {"entries": []}
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = {"entries": []}
    entries = [entry for entry in payload.get("entries", []) if entry.get("proposal_id") != proposal_id]
    entries.append({"proposal_id": proposal_id, "status": status, "matches": matches, "updated_at_utc": _now()})
    _atomic_write_json(path, {"entries": entries})


def _review_path(root: Path, proposal_id: str) -> Path:
    return ensure_proposal_review_dirs(root) / "proposal_reviews" / f"{_safe_id(proposal_id)}_review.json"


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            pass
    os.replace(temp_path, path)


def _hash_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in str(value).strip()) or "object"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
