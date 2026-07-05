"""Evidence binder governance for source-backed proposals and citations."""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime, date
from pathlib import Path
from typing import Mapping

from .document_preflight import get_document_preflight_summary
from .document_structure import analyze_chunk_quality, get_document_structure_summary
from .proposal_review import score_citation_strength
from .source_documents import SOURCE_DOCUMENT_ROOT, load_source_document
from .source_knowledge import ensure_source_knowledge_dirs, list_source_proposals, load_chunk

BINDER_SCHEMA_VERSION = "evidence_binder_v1"
SOURCE_RELIABILITY_SCHEMA_VERSION = "source_reliability_v1"
EVIDENCE_DIRS = ("evidence_binders", "source_reliability", "indexes")
SOURCE_TYPES = {"unknown", "official_policy", "internal_note", "manual_reference", "book", "paper", "web_export", "legal_source", "technical_doc", "user_supplied"}
AUTHORITY_LEVELS = {"unknown", "low", "medium", "high", "primary", "secondary", "tertiary"}
POSITIVE_WORDS = {"allow", "proceed", "approve", "use", "accept", "valid", "ready"}
NEGATIVE_WORDS = {"reject", "block", "avoid", "invalid", "unsafe", "forbidden", "fail"}
CONDITIONAL_WORDS = {"unless", "exception", "only if", "requires", "needs review", "caution", "warning", "must", "required", "optional"}


def ensure_evidence_binder_dirs(root: Path | str = SOURCE_DOCUMENT_ROOT) -> Path:
    base = ensure_source_knowledge_dirs(root)
    for folder in EVIDENCE_DIRS:
        (base / folder).mkdir(parents=True, exist_ok=True)
    return base


def group_citations_for_proposal(proposal_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_evidence_binder_dirs(root)
    proposal = _get_proposal(proposal_id, base)
    citations = []
    seen = set()
    claim_terms = set(_keywords(proposal.claim))
    for citation in _load_all_citations(base):
        direct = citation.get("document_id") == proposal.document_id and citation.get("chunk_id") == proposal.chunk_id
        explicit = proposal_id in str(citation.get("note", "")) or proposal_id in str(citation.get("quote_excerpt", ""))
        overlap = len(claim_terms.intersection(_keywords(str(citation.get("quote_excerpt", "")) + " " + str(citation.get("note", ""))))) >= 2
        if not (direct or explicit or overlap):
            continue
        citation_id = str(citation.get("citation_id") or "")
        if not citation_id or citation_id in seen:
            continue
        seen.add(citation_id)
        citations.append(_linked_citation_item(citation, base))
    warnings = [] if citations else ["no_linked_citations"]
    return {
        "proposal_id": proposal_id,
        "citation_count": len(citations),
        "documents_count": len({item["document_id"] for item in citations}),
        "chunks_count": len({item["chunk_id"] for item in citations}),
        "citations": citations,
        "warnings": warnings,
    }


def get_or_create_source_reliability(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_evidence_binder_dirs(root)
    path = _reliability_path(base, document_id)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    record = load_source_document(document_id, root=base, missing_ok=True)
    warnings = [] if record else ["source_document_missing"]
    detected_title = record.original_filename if record else "Unknown"
    payload = {
        "document_id": document_id,
        "schema_version": SOURCE_RELIABILITY_SCHEMA_VERSION,
        "source_type": "unknown",
        "authority_level": "unknown",
        "publication_date": None,
        "modified_date": None,
        "detected_title": detected_title,
        "author": "Unknown",
        "version_label": None,
        "reliability_score": 50,
        "reliability_band": "unknown",
        "staleness_status": "unknown",
        "warnings": warnings + ["source_reliability_unknown"],
        "notes": [],
    }
    _atomic_write_json(path, payload)
    _update_source_reliability_index(base)
    return payload


def update_source_reliability_metadata(document_id: str, metadata: Mapping[str, object], *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_evidence_binder_dirs(root)
    current = get_or_create_source_reliability(document_id, root=base)
    updated = dict(current)
    for key in ("source_type", "authority_level", "publication_date", "modified_date", "detected_title", "author", "version_label"):
        if key in metadata:
            updated[key] = metadata[key]
    if updated.get("source_type") not in SOURCE_TYPES:
        updated["source_type"] = "unknown"
    if updated.get("authority_level") not in AUTHORITY_LEVELS:
        updated["authority_level"] = "unknown"
    updated.update(_reliability_score(updated))
    notes = list(current.get("notes", []))
    if metadata.get("note"):
        notes.append({"created_at_utc": _now(), "text": _safe_preview(str(metadata["note"]), 220)})
    updated["notes"] = notes
    _atomic_write_json(_reliability_path(base, document_id), updated)
    _update_source_reliability_index(base)
    return updated


def score_citation_bundle_strength(proposal_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_evidence_binder_dirs(root)
    group = group_citations_for_proposal(proposal_id, root=base)
    citations = group["citations"]
    blockers = []
    strengths = []
    weaknesses = []
    if not citations:
        blockers.append("no_linked_citations")
    score = 20 if citations else 0
    unique_docs = len({item["document_id"] for item in citations})
    if len(citations) >= 2:
        score += 18
        strengths.append("multiple_citations")
    if unique_docs >= 2:
        score += 18
        strengths.append("multiple_documents")
    if any(item.get("page_start") is not None for item in citations):
        score += 12
        strengths.append("page_references_available")
    else:
        weaknesses.append("page_references_unavailable")
    if any(str(item.get("excerpt_preview") or "").strip() for item in citations):
        score += 8
        strengths.append("excerpt_previews_available")
    reliability_bands = [str(item.get("source_reliability_band")) for item in citations]
    if any(band in {"strong", "usable"} for band in reliability_bands):
        score += 15
        strengths.append("usable_source_reliability")
    if any(band == "unknown" for band in reliability_bands):
        weaknesses.append("one_source_reliability_unknown")
    if all(str(item.get("citation_strength_band")) == "unusable" for item in citations) and citations:
        blockers.append("all_citations_unusable")
    if detect_cross_document_conflicts(proposal_id, root=base).get("status") == "conflict_review_required":
        blockers.append("unresolved_strong_conflict")
    if blockers:
        score = min(score, 24)
    band = _score_band(score)
    return {"score": max(0, min(100, score)), "band": band, "status": "blocked" if blockers else "warning" if weaknesses else "ok", "citation_count": len(citations), "unique_documents": unique_docs, "strengths": list(dict.fromkeys(strengths)), "weaknesses": list(dict.fromkeys(weaknesses)), "blockers": blockers}


def detect_cross_document_support(proposal_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_evidence_binder_dirs(root)
    proposal = _get_proposal(proposal_id, base)
    group = group_citations_for_proposal(proposal_id, root=base)
    claim_terms = set(_keywords(proposal.claim))
    claim_category = _decision_category(proposal.claim)
    matches = []
    for item in group["citations"]:
        text = str(item.get("excerpt_preview", ""))
        overlap = len(claim_terms.intersection(_keywords(text)))
        same_category = _decision_category(text) == claim_category and claim_category != "neutral"
        if overlap >= 2 and same_category:
            matches.append({"citation_id": item["citation_id"], "document_id": item["document_id"], "chunk_id": item["chunk_id"], "reason": "same_key_term_and_decision_category", "confidence": "medium"})
    status = "support_found" if len(matches) >= 2 else "limited_support" if matches else "no_support"
    return {"status": status, "support_count": len(matches), "matches": matches, "warnings": [] if group["citations"] else ["no_linked_citations"]}


def detect_cross_document_conflicts(proposal_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_evidence_binder_dirs(root)
    proposal = _get_proposal(proposal_id, base)
    group = group_citations_for_proposal(proposal_id, root=base)
    claim_terms = set(_keywords(proposal.claim))
    claim_category = _decision_category(proposal.claim)
    matches = []
    for item in group["citations"]:
        text = str(item.get("excerpt_preview", ""))
        overlap = len(claim_terms.intersection(_keywords(text)))
        category = _decision_category(text)
        if overlap >= 1 and _opposite_categories(claim_category, category):
            matches.append({"citation_id": item["citation_id"], "document_id": item["document_id"], "reason": "opposite_decision_category_same_key_term", "confidence": "medium"})
    status = "conflict_review_required" if len(matches) >= 2 else "possible_conflict" if matches else "none"
    return {"status": status, "conflict_count": len(matches), "matches": matches, "warnings": [] if group["citations"] else ["no_linked_citations"]}


def calculate_evidence_coverage(proposal_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_evidence_binder_dirs(root)
    group = group_citations_for_proposal(proposal_id, root=base)
    citations = group["citations"]
    score = 0
    required = []
    warnings = []
    has_citation = bool(citations)
    unique_docs = len({item["document_id"] for item in citations})
    if has_citation:
        score += 25
    else:
        required.append("attach_citation")
    if unique_docs > 1:
        score += 15
    else:
        required.append("add_second_source_if_available")
    if any(item.get("page_start") is not None for item in citations):
        score += 10
    else:
        warnings.append("page_references_unavailable")
    reliabilities = [get_or_create_source_reliability(str(item["document_id"]), root=base) for item in citations]
    has_reliability = any(rel.get("reliability_band") != "unknown" for rel in reliabilities)
    if has_reliability:
        score += 15
    else:
        required.append("add_source_reliability_metadata")
    structures = [get_document_structure_summary(str(item["document_id"]), root=base) for item in citations]
    has_structure = any(item.get("status") == "built" for item in structures)
    if has_structure:
        score += 10
    else:
        warnings.append("structure_map_missing")
    conflict = detect_cross_document_conflicts(proposal_id, root=base)
    unresolved = conflict.get("status") != "none"
    if not unresolved:
        score += 15
    else:
        required.append("resolve_possible_conflict")
    try:
        from .proposal_review import load_proposal_review
        review = load_proposal_review(proposal_id, root=base)
        if review and review.review_notes:
            score += 10
        else:
            warnings.append("review_notes_missing")
    except Exception:
        warnings.append("review_notes_unavailable")
    band = "complete" if score >= 90 else "good" if score >= 75 else "partial" if score >= 50 else "weak" if score >= 25 else "missing"
    return {"coverage_score": score, "coverage_band": band, "has_citation": has_citation, "unique_documents": unique_docs, "has_page_references": any(item.get("page_start") is not None for item in citations), "has_reliability_metadata": has_reliability, "has_structure_map": has_structure, "unresolved_conflicts": unresolved, "required_actions": list(dict.fromkeys(required)), "warnings": list(dict.fromkeys(warnings))}


def detect_weak_or_stale_sources(proposal_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_evidence_binder_dirs(root)
    group = group_citations_for_proposal(proposal_id, root=base)
    weak = []
    stale = []
    for document_id in sorted({str(item["document_id"]) for item in group["citations"]}):
        reliability = get_or_create_source_reliability(document_id, root=base)
        if reliability.get("reliability_band") in {"unknown", "weak", "untrusted"}:
            weak.append({"document_id": document_id, "reason": "source_reliability_unknown" if reliability.get("reliability_band") == "unknown" else "source_reliability_weak"})
        if reliability.get("staleness_status") == "stale":
            stale.append({"document_id": document_id, "reason": "source_stale"})
        preflight = get_document_preflight_summary(document_id, root=base)
        if preflight.get("verdict") in {"WARNING", "BLOCK"}:
            weak.append({"document_id": document_id, "reason": "preflight_warning_or_block"})
        quality = analyze_chunk_quality(document_id, root=base)
        if quality.get("quality_status") in {"warning", "critical"}:
            weak.append({"document_id": document_id, "reason": "chunk_quality_warning"})
    status = "warning" if weak or stale else "ok"
    return {"status": status, "weak_sources": weak, "stale_sources": stale, "warnings": [] if group["citations"] else ["no_linked_citations"]}


def build_evidence_binder(proposal_id: str, *, regenerate: bool = False, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_evidence_binder_dirs(root)
    path = _binder_path(base, proposal_id)
    if path.exists() and not regenerate:
        return json.loads(path.read_text(encoding="utf-8"))
    try:
        proposal = _get_proposal(proposal_id, base)
    except FileNotFoundError:
        payload = _missing_binder(proposal_id, "missing_proposal", "proposal_not_found", "Create or select a proposal before evidence review.")
        _atomic_write_json(path, payload)
        _update_evidence_binder_index(base)
        return payload
    group = group_citations_for_proposal(proposal_id, root=base)
    bundle = score_citation_bundle_strength(proposal_id, root=base)
    support = detect_cross_document_support(proposal_id, root=base)
    conflict = detect_cross_document_conflicts(proposal_id, root=base)
    coverage = calculate_evidence_coverage(proposal_id, root=base)
    weak = detect_weak_or_stale_sources(proposal_id, root=base)
    blockers = [] if group["citations"] else ["no_linked_citations"]
    warnings = list(dict.fromkeys([*group.get("warnings", []), *bundle.get("weaknesses", []), *coverage.get("warnings", []), *weak.get("warnings", [])]))
    if conflict.get("status") != "none":
        warnings.append("possible_conflict_detected")
    recommended = _binder_recommended_action(blockers, conflict, coverage, weak)
    payload = {
        "proposal_id": proposal_id,
        "binder_id": f"binder_{proposal_id}",
        "schema_version": BINDER_SCHEMA_VERSION,
        "created_at_utc": _now(),
        "updated_at_utc": _now(),
        "claim_preview": _safe_preview(proposal.claim, 180),
        "linked_citations": group["citations"],
        "supporting_evidence": support.get("matches", []),
        "conflicting_evidence": conflict.get("matches", []),
        "duplicate_evidence": [],
        "source_reliability": {item["document_id"]: get_or_create_source_reliability(str(item["document_id"]), root=base) for item in group["citations"]},
        "citation_bundle_strength": bundle,
        "evidence_coverage": coverage,
        "weak_or_stale_sources": weak,
        "support": support,
        "conflict": conflict,
        "warnings": list(dict.fromkeys(warnings)),
        "blockers": blockers,
        "recommended_action": recommended,
    }
    _atomic_write_json(path, payload)
    _update_evidence_binder_index(base)
    return payload


def load_evidence_binder(proposal_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    path = _binder_path(ensure_evidence_binder_dirs(root), proposal_id)
    if not path.exists():
        return {"proposal_id": proposal_id, "binder_status": "not_built", "warnings": ["evidence_binder_not_built"]}
    return json.loads(path.read_text(encoding="utf-8"))


def get_evidence_binder_summary(proposal_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    binder = load_evidence_binder(proposal_id, root=root)
    if binder.get("binder_status") == "not_built":
        return {"proposal_id": proposal_id, "binder_status": "not_built", "citation_count": 0, "unique_documents": 0, "bundle_strength_band": "unknown", "coverage_band": "missing", "support_status": "unknown", "conflict_status": "unknown", "weak_source_count": 0, "stale_source_count": 0, "recommended_action": "Build evidence binder.", "warnings": binder.get("warnings", []), "blockers": []}
    citations = binder.get("linked_citations", [])
    weak = binder.get("weak_or_stale_sources", {}) if isinstance(binder.get("weak_or_stale_sources"), Mapping) else {}
    blockers = binder.get("blockers", [])
    warnings = binder.get("warnings", [])
    status = "critical" if blockers else "warning" if warnings else "healthy"
    return {"proposal_id": proposal_id, "binder_status": status, "citation_count": len(citations), "unique_documents": len({item.get("document_id") for item in citations if isinstance(item, Mapping)}), "bundle_strength_band": (binder.get("citation_bundle_strength") or {}).get("band"), "coverage_band": (binder.get("evidence_coverage") or {}).get("coverage_band"), "support_status": (binder.get("support") or {}).get("status"), "conflict_status": (binder.get("conflict") or {}).get("status"), "weak_source_count": len(weak.get("weak_sources", [])), "stale_source_count": len(weak.get("stale_sources", [])), "recommended_action": binder.get("recommended_action"), "warnings": warnings, "blockers": blockers}


def format_evidence_binder_report_text(proposal_id: str, *, public_safe: bool = True, root: Path | str = SOURCE_DOCUMENT_ROOT) -> str:
    binder = build_evidence_binder(proposal_id, root=root)
    summary = get_evidence_binder_summary(proposal_id, root=root)
    return "\n".join([
        "Evidence Binder Report",
        "",
        f"Proposal: {proposal_id}",
        f"Claim Preview: {binder.get('claim_preview', 'Unavailable')}",
        "",
        "Evidence:",
        f"- Citations: {summary.get('citation_count')}",
        f"- Unique Documents: {summary.get('unique_documents')}",
        f"- Bundle Strength: {summary.get('bundle_strength_band')}",
        f"- Coverage: {summary.get('coverage_band')}",
        "",
        "Support:",
        f"- Status: {summary.get('support_status')}",
        f"- Matches: {len(binder.get('supporting_evidence', []))}",
        "",
        "Conflicts:",
        f"- Status: {summary.get('conflict_status')}",
        f"- Matches: {len(binder.get('conflicting_evidence', []))}",
        "",
        "Source Reliability:",
        f"- Weak Sources: {summary.get('weak_source_count')}",
        f"- Stale Sources: {summary.get('stale_source_count')}",
        "",
        "Recommended Action:",
        str(summary.get("recommended_action")),
    ])


def _linked_citation_item(citation: Mapping[str, object], root: Path) -> dict[str, object]:
    document_id = str(citation.get("document_id") or "")
    reliability = get_or_create_source_reliability(document_id, root=root) if document_id else {"reliability_band": "unknown"}
    excerpt = _safe_preview(str(citation.get("quote_excerpt") or ""), 260)
    strength = "usable" if citation.get("chunk_id") and excerpt else "weak"
    return {"citation_id": citation.get("citation_id"), "document_id": document_id, "chunk_id": citation.get("chunk_id"), "page_start": citation.get("page_start"), "page_end": citation.get("page_end"), "excerpt_preview": excerpt, "citation_strength_band": strength, "source_reliability_band": reliability.get("reliability_band", "unknown"), "warnings": list(citation.get("warnings", []))}


def _load_all_citations(root: Path) -> list[dict[str, object]]:
    citations = []
    for path in sorted((root / "citations").glob("*.json")):
        try:
            citations.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return citations


def _get_proposal(proposal_id: str, root: Path):
    for proposal in list_source_proposals(root=root):
        if proposal.proposal_id == proposal_id:
            return proposal
    raise FileNotFoundError(proposal_id)


def _reliability_score(data: Mapping[str, object]) -> dict[str, object]:
    score = 50
    authority = str(data.get("authority_level") or "unknown")
    source_type = str(data.get("source_type") or "unknown")
    if authority in {"primary", "high"}:
        score += 25
    elif authority in {"secondary", "medium"}:
        score += 12
    elif authority == "low":
        score -= 20
    if source_type in {"official_policy", "legal_source", "technical_doc", "paper", "book"}:
        score += 10
    elif source_type == "unknown":
        score -= 5
    staleness = _staleness(data.get("publication_date"))
    if staleness == "stale":
        score -= 15
    score = max(0, min(100, score))
    band = "strong" if score >= 85 else "usable" if score >= 65 else "weak" if score >= 35 else "untrusted"
    if authority == "unknown" and source_type == "unknown":
        band = "unknown"
    warnings = [] if band != "unknown" else ["source_reliability_unknown"]
    if staleness == "unknown":
        warnings.append("publication_date_unknown")
    return {"reliability_score": score, "reliability_band": band, "staleness_status": staleness, "warnings": list(dict.fromkeys(warnings))}


def _staleness(value: object) -> str:
    if not value:
        return "unknown"
    try:
        year = date.fromisoformat(str(value)[:10]).year
    except Exception:
        return "unknown"
    age = datetime.now(UTC).year - year
    return "stale" if age >= 10 else "aging" if age >= 5 else "current"


def _binder_recommended_action(blockers: list[str], conflict: Mapping[str, object], coverage: Mapping[str, object], weak: Mapping[str, object]) -> str:
    if blockers:
        return "Attach at least one citation before evidence review."
    if conflict.get("status") != "none":
        return "Resolve possible conflict before promotion review."
    if weak.get("weak_sources"):
        return "Add source reliability metadata or stronger sources before promotion review."
    if coverage.get("coverage_band") in {"missing", "weak", "partial"}:
        return "Improve evidence coverage before promotion review."
    return "Evidence binder is ready for human review; no automatic promotion occurs."


def _keywords(text: str) -> list[str]:
    stop = {"the", "and", "for", "with", "that", "this", "from", "when", "then", "before", "after", "source", "citation"}
    return [word for word in re.findall(r"[a-z0-9]{4,}", text.lower()) if word not in stop]


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


def _score_band(score: int) -> str:
    return "strong" if score >= 90 else "usable" if score >= 75 else "weak" if score >= 50 else "poor" if score >= 25 else "unusable"


def _missing_binder(proposal_id: str, status: str, blocker: str, action: str) -> dict[str, object]:
    now = _now()
    return {"proposal_id": proposal_id, "binder_id": f"binder_{proposal_id}", "schema_version": BINDER_SCHEMA_VERSION, "created_at_utc": now, "updated_at_utc": now, "claim_preview": "", "linked_citations": [], "supporting_evidence": [], "conflicting_evidence": [], "duplicate_evidence": [], "source_reliability": {}, "citation_bundle_strength": {}, "evidence_coverage": {}, "warnings": [], "blockers": [blocker], "binder_status": status, "recommended_action": action}


def _safe_preview(text: str, limit: int) -> str:
    cleaned = re.sub(r"[A-Za-z]:[/\\][^\s]+", "[local-path]", text)
    cleaned = re.sub(r"[\w.+-]+@[\w.-]+", "[email]", cleaned)
    cleaned = re.sub(r"\b(?:token|api[_-]?key|secret)\s*[:=]\s*\S+", "[secret]", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:limit]


def _binder_path(root: Path, proposal_id: str) -> Path:
    return root / "evidence_binders" / f"{_safe_id(proposal_id)}_evidence_binder.json"


def _reliability_path(root: Path, document_id: str) -> Path:
    return root / "source_reliability" / f"{_safe_id(document_id)}_reliability.json"


def _update_evidence_binder_index(root: Path) -> None:
    entries = []
    for path in sorted((root / "evidence_binders").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        entries.append({"proposal_id": data.get("proposal_id"), "path": str(path), "citation_count": len(data.get("linked_citations", [])), "schema_version": data.get("schema_version")})
    _atomic_write_json(root / "indexes" / "evidence_binder_index.json", {"entries": entries})


def _update_source_reliability_index(root: Path) -> None:
    entries = []
    for path in sorted((root / "source_reliability").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        entries.append({"document_id": data.get("document_id"), "path": str(path), "reliability_band": data.get("reliability_band"), "schema_version": data.get("schema_version")})
    _atomic_write_json(root / "indexes" / "source_reliability_index.json", {"entries": entries})


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_path, path)


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
