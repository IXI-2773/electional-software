"""Deterministic document content maps, topic lookup, provenance, and reader readiness."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .document_manifest import build_document_manifest, load_document_manifest, validate_source_locator
from .document_structure import load_document_structure_map
from .proposal_review import load_proposal_review
from .source_documents import SOURCE_DOCUMENT_ROOT, STATUS_EXTRACTED, load_source_document
from .source_impact_analysis import list_source_revalidation_queue
from .source_knowledge import ensure_source_knowledge_dirs, list_source_proposals, load_chunks
from .source_revalidation_review import load_source_revalidation_resolution

CONTENT_MAP_SCHEMA_VERSION = "document_content_map_v1"
SCOPED_FINGERPRINT_SCHEMA_VERSION = "document_scoped_fingerprint_v1"
CONTENT_MAP_DIR = "document_content_maps"
CONTENT_MAP_INDEX = "document_content_map_index.json"


def build_document_scoped_fingerprint(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = ensure_document_content_map_dirs(root)
    chunk_records = [chunk.to_json(public_safe=True) for chunk in load_chunks(document_id=document_id, root=base)]
    chunk_ids = {str(item.get("chunk_id") or "") for item in chunk_records}
    citation_records = [item for item in _iter_json(base / "citations", "*.json") if str(item.get("document_id") or "") == document_id]
    citation_ids = {str(item.get("citation_id") or "") for item in citation_records}
    proposal_records = [
        proposal.to_json(public_safe=True)
        for proposal in list_source_proposals(root=base)
        if proposal.document_id == document_id or proposal.chunk_id in chunk_ids or any(str(cid) in citation_ids for cid in getattr(proposal, "citation_ids", []) or [])
    ]
    proposal_ids = {str(item.get("proposal_id") or "") for item in proposal_records}
    review_records = []
    for proposal_id in sorted(proposal_ids):
        review = load_proposal_review(proposal_id, root=base, missing_ok=True)
        if review is not None:
            review_records.append(review.to_json())
    binder_records = []
    for item in _iter_json(base / "evidence_binders", "*.json"):
        linked = [entry for entry in item.get("linked_citations", []) if isinstance(entry, dict)]
        if str(item.get("proposal_id") or "") in proposal_ids or any(str(entry.get("citation_id") or "") in citation_ids for entry in linked) or any(str(entry.get("document_id") or "") == document_id for entry in linked):
            binder_records.append(item)
    impact_items = [item for item in list_source_revalidation_queue(limit=500, root=base).get("items", []) if item.get("document_id") == document_id]
    impact_ids = {str(item.get("queue_item_id") or "") for item in impact_items}
    resolution_records = []
    for queue_item_id in sorted(impact_ids):
        resolution = load_source_revalidation_resolution(queue_item_id, root=base).get("resolution")
        if isinstance(resolution, dict):
            resolution_records.append(resolution)
    content_map = load_document_content_map(document_id, root=base).get("content_map")
    component_payloads = {
        "source": _read_json(base / "indexes" / f"{document_id}.json"),
        "preflight": _read_json(base / "preflight" / f"{document_id}_preflight.json"),
        "extraction": _hash_file(base / "extracted_text" / f"{document_id}.txt"),
        "chunks": chunk_records,
        "page_diagnostics": _read_json(base / "page_diagnostics" / f"{document_id}.json"),
        "structure_map": _read_json(base / "structure_maps" / f"{document_id}_structure.json"),
        "reliability": _read_json(base / "source_reliability" / f"{document_id}_reliability.json"),
        "citations": citation_records,
        "proposals": proposal_records,
        "proposal_reviews": review_records,
        "evidence_binders": binder_records,
        "impact_items": impact_items,
        "revalidation_resolutions": resolution_records,
        "content_map": _content_map_hash_payload(content_map),
    }
    component_hashes = {key: _component_hash(value) for key, value in component_payloads.items()}
    record_counts = {
        "chunks": len(chunk_records),
        "citations": len(citation_records),
        "proposals": len(proposal_records),
        "proposal_reviews": len(review_records),
        "evidence_binders": len(binder_records),
        "impact_items": len(impact_items),
    }
    fingerprint = "sha256:" + hashlib.sha256(json.dumps(component_hashes, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
    warnings = [f"{name}_missing" for name, value in component_hashes.items() if value is None and name not in {"citations", "proposals", "proposal_reviews", "evidence_binders", "impact_items", "revalidation_resolutions", "content_map"}]
    return {
        "schema_version": SCOPED_FINGERPRINT_SCHEMA_VERSION,
        "document_id": document_id,
        "fingerprint": fingerprint,
        "component_hashes": component_hashes,
        "record_counts": record_counts,
        "warnings": list(dict.fromkeys(warnings)),
    }


def detect_document_chapter_section_ranges(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = ensure_document_content_map_dirs(root)
    structure = load_document_structure_map(document_id, root=base)
    chunks = load_chunks(document_id=document_id, root=base)
    if structure.get("status") == "not_built":
        return {"document_id": document_id, "structure_status": "unknown", "chapters": [], "sections": [], "unassigned_chunk_ids": [chunk.chunk_id for chunk in chunks], "warnings": structure.get("warnings", [])}
    headings = [item for item in structure.get("headings", []) if isinstance(item, dict)]
    sections = [item for item in structure.get("sections", []) if isinstance(item, dict)]
    page_count = int(structure.get("page_count") or 0) or None
    chapter_headings = [
        heading
        for heading in headings
        if int(heading.get("level") or 0) <= 1 or str(heading.get("reason") or "") in {"chapter_section_label", "numbered_heading"}
    ]
    chapter_headings.sort(key=lambda item: (int(item.get("page_number") or 10**9), str(item.get("title") or "")))
    chapter_entries = []
    used_chunks: set[str] = set()
    if chapter_headings:
        for index, heading in enumerate(chapter_headings, start=1):
            start_page = int(heading.get("page_number") or 0) or None
            next_page = int(chapter_headings[index].get("page_number") or start_page) if index < len(chapter_headings) else page_count or start_page
            end_page = max(start_page or 1, (next_page or start_page or 1) - (1 if index < len(chapter_headings) else 0))
            chapter_chunks = [chunk for chunk in chunks if chunk.page_start is not None and chunk.page_end is not None and start_page is not None and chunk.page_end >= start_page and chunk.page_start <= end_page]
            chapter_sections = []
            for sec_index, section in enumerate(sections, start=1):
                sec_start = int(section.get("page_start") or 0) or None
                sec_end = int(section.get("page_end") or sec_start or 0) or sec_start
                if start_page is None or sec_start is None or sec_start < start_page or sec_start > end_page:
                    continue
                sec_chunks = [chunk.chunk_id for chunk in chapter_chunks if chunk.page_start is not None and chunk.page_end is not None and chunk.page_end >= sec_start and chunk.page_start <= sec_end]
                used_chunks.update(sec_chunks)
                chapter_sections.append(
                    {
                        "section_id": f"section_{index:03d}_{len(chapter_sections) + 1:03d}",
                        "chapter_id": f"chapter_{index:03d}",
                        "title": section.get("title"),
                        "start_page": sec_start,
                        "end_page": sec_end,
                        "chunk_ids": sec_chunks,
                        "topic_tags": [],
                        "heading_confidence": section.get("confidence", heading.get("confidence", "unknown")),
                        "locator_status": "valid" if sec_chunks else "warning",
                        "warnings": [] if sec_chunks else ["section_chunks_unassigned"],
                    }
                )
            chapter_entries.append(
                {
                    "chapter_id": f"chapter_{index:03d}",
                    "title": heading.get("title"),
                    "chapter_number": index,
                    "start_page": start_page,
                    "end_page": end_page,
                    "start_chunk_id": chapter_chunks[0].chunk_id if chapter_chunks else None,
                    "end_chunk_id": chapter_chunks[-1].chunk_id if chapter_chunks else None,
                    "confidence": heading.get("confidence", "unknown"),
                    "source": heading.get("source", "structure_map_heading"),
                    "sections": chapter_sections,
                }
            )
        return {
            "document_id": document_id,
            "structure_status": "resolved",
            "chapters": chapter_entries,
            "sections": [section for chapter in chapter_entries for section in chapter.get("sections", [])],
            "unassigned_chunk_ids": [chunk.chunk_id for chunk in chunks if chunk.chunk_id not in used_chunks],
            "warnings": [],
        }
    if sections:
        used = set()
        section_entries = []
        for index, section in enumerate(sorted(sections, key=lambda item: (int(item.get("page_start") or 10**9), str(item.get("section_id") or ""))), start=1):
            sec_start = int(section.get("page_start") or 0) or None
            sec_end = int(section.get("page_end") or sec_start or 0) or sec_start
            sec_chunks = [chunk.chunk_id for chunk in chunks if chunk.page_start is not None and chunk.page_end is not None and sec_start is not None and chunk.page_end >= sec_start and chunk.page_start <= sec_end]
            used.update(sec_chunks)
            section_entries.append(
                {
                    "section_id": f"section_000_{index:03d}",
                    "chapter_id": None,
                    "title": section.get("title"),
                    "start_page": sec_start,
                    "end_page": sec_end,
                    "chunk_ids": sec_chunks,
                    "topic_tags": [],
                    "heading_confidence": section.get("confidence", "unknown"),
                    "locator_status": "valid" if sec_chunks else "warning",
                    "warnings": [] if sec_chunks else ["section_chunks_unassigned"],
                }
            )
        return {"document_id": document_id, "structure_status": "section_only", "chapters": [], "sections": section_entries, "unassigned_chunk_ids": [chunk.chunk_id for chunk in chunks if chunk.chunk_id not in used], "warnings": []}
    return {"document_id": document_id, "structure_status": "unknown", "chapters": [], "sections": [], "unassigned_chunk_ids": [chunk.chunk_id for chunk in chunks], "warnings": ["no_resolved_chapters_or_sections"]}


def build_document_content_map(
    document_id: str,
    topic_terms: list[str] | None = None,
    regenerate: bool = False,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = ensure_document_content_map_dirs(root)
    existing = load_document_content_map(document_id, root=base).get("content_map")
    manifest = build_document_manifest(document_id, regenerate=False, root=base)
    fingerprint = build_document_scoped_fingerprint(document_id, root=base)
    if existing and not regenerate and existing.get("document_scoped_fingerprint") == fingerprint.get("fingerprint"):
        return existing
    structure = detect_document_chapter_section_ranges(document_id, root=base)
    tag_result = assign_controlled_topic_tags(document_id, topic_terms=topic_terms, root=base, structure_hint=structure)
    sections = structure.get("sections", [])
    chapters = structure.get("chapters", [])
    topic_tags = sorted({tag for section in sections for tag in section.get("topic_tags", [])} | {tag for chapter in chapters for section in chapter.get("sections", []) for tag in section.get("topic_tags", [])})
    provenance = _validate_document_provenance_contract(document_id, root=base, content_map_hint={"document_id": document_id, "source_revision": manifest.get("source_revision"), "document_scoped_fingerprint": fingerprint.get("fingerprint"), "chapters": chapters, "sections": sections, "unassigned_chunk_ids": structure.get("unassigned_chunk_ids", [])})
    readiness = _get_reader_backend_readiness(document_id, root=base, manifest_hint=manifest, content_map_hint={"structure_status": structure.get("structure_status"), "chapters": chapters, "sections": sections, "topic_tags": topic_tags, "unassigned_chunk_ids": structure.get("unassigned_chunk_ids", []), "provenance_status": provenance.get("status"), "document_scoped_fingerprint": fingerprint.get("fingerprint"), "source_revision": manifest.get("source_revision")}, provenance_hint=provenance)
    content_map = {
        "schema_version": CONTENT_MAP_SCHEMA_VERSION,
        "content_map_id": f"content_map_{document_id}",
        "document_id": document_id,
        "source_revision": manifest.get("source_revision"),
        "document_scoped_fingerprint": fingerprint.get("fingerprint"),
        "structure_status": structure.get("structure_status"),
        "chapters": chapters,
        "sections": sections,
        "section_count": len(sections),
        "chunk_count": len(load_chunks(document_id=document_id, root=base)),
        "topic_tags": topic_tags,
        "unassigned_chunk_ids": structure.get("unassigned_chunk_ids", []),
        "provenance_status": provenance.get("status"),
        "reader_backend_readiness": readiness.get("status"),
        "created_at_utc": (existing or {}).get("created_at_utc") or _now(),
        "updated_at_utc": _now(),
        "warnings": list(dict.fromkeys([*structure.get("warnings", []), *tag_result.get("warnings", []), *provenance.get("warnings", [])])),
        "blockers": list(dict.fromkeys(readiness.get("blockers", []))),
    }
    _atomic_write_json(_content_map_path(base, document_id), content_map)
    _update_content_map_index(base)
    return content_map


def load_document_content_map(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    path = _content_map_path(ensure_document_content_map_dirs(root), document_id)
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return {"document_id": document_id, "status": "not_found", "content_map": None, "warnings": []}
    return {"document_id": document_id, "status": "loaded", "content_map": payload, "warnings": []}


def assign_controlled_topic_tags(
    document_id: str,
    topic_terms: list[str] | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
    structure_hint: dict | None = None,
) -> dict:
    structure = structure_hint or detect_document_chapter_section_ranges(document_id, root=root)
    normalized_input = [_normalize_topic(term) for term in (topic_terms or []) if _normalize_topic(term)]
    if not normalized_input:
        normalized_input = sorted({_normalize_topic(chapter.get("title")) for chapter in structure.get("chapters", []) if _normalize_topic(chapter.get("title"))} | {_normalize_topic(section.get("title")) for section in structure.get("sections", []) if _normalize_topic(section.get("title"))})
    tagged_chapters = 0
    tagged_sections = 0
    tagged_chunks = 0
    matched_terms: set[str] = set()
    for chapter in structure.get("chapters", []):
        chapter_terms = _title_terms(chapter.get("title"))
        for section in chapter.get("sections", []):
            section_terms = _title_terms(section.get("title"))
            tags = [term for term in normalized_input if term == _normalize_topic(section.get("title")) or term == _normalize_topic(chapter.get("title")) or term in section_terms or term in chapter_terms]
            section["topic_tags"] = sorted(set(tags))
            if section["topic_tags"]:
                tagged_sections += 1
                tagged_chunks += len(section.get("chunk_ids", []))
                matched_terms.update(section["topic_tags"])
        if any(section.get("topic_tags") for section in chapter.get("sections", [])):
            tagged_chapters += 1
    if not structure.get("chapters"):
        for section in structure.get("sections", []):
            section_terms = _title_terms(section.get("title"))
            tags = [term for term in normalized_input if term == _normalize_topic(section.get("title")) or term in section_terms]
            section["topic_tags"] = sorted(set(tags))
            if section["topic_tags"]:
                tagged_sections += 1
                tagged_chunks += len(section.get("chunk_ids", []))
                matched_terms.update(section["topic_tags"])
    return {
        "document_id": document_id,
        "topic_terms": normalized_input,
        "tagged_chapters": tagged_chapters,
        "tagged_sections": tagged_sections,
        "tagged_chunks": tagged_chunks,
        "unmatched_topics": [term for term in normalized_input if term not in matched_terms],
        "warnings": [],
    }


def find_related_document_content(
    document_id: str,
    topic: str,
    limit: int = 50,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    content_map = _load_preferred_content_view(document_id, root=root)
    normalized_topic = _normalize_topic(topic)
    results = []
    chapters = content_map.get("chapters", [])
    flat_sections = content_map.get("sections", []) if not chapters else [section for chapter in chapters for section in chapter.get("sections", [])]
    chapter_lookup = {section.get("section_id"): chapter for chapter in chapters for section in chapter.get("sections", [])}
    for order, section in enumerate(flat_sections, start=1):
        section_title = _normalize_topic(section.get("title"))
        chapter = chapter_lookup.get(section.get("section_id"))
        chapter_title = _normalize_topic(chapter.get("title")) if chapter else ""
        matched_tags = [tag for tag in section.get("topic_tags", []) if tag == normalized_topic]
        reason = None
        if matched_tags:
            reason = "exact_topic_tag"
        elif section_title == normalized_topic:
            reason = "exact_section_title"
        elif chapter_title == normalized_topic:
            reason = "exact_chapter_title"
        elif normalized_topic and re.search(rf"(?<!\w){re.escape(normalized_topic)}(?!\w)", section_title):
            reason = "whole_word_keyword"
        if reason:
            results.append(
                {
                    "chapter_id": chapter.get("chapter_id") if chapter else None,
                    "chapter_title": chapter.get("title") if chapter else None,
                    "section_id": section.get("section_id"),
                    "section_title": section.get("title"),
                    "page_start": section.get("start_page"),
                    "page_end": section.get("end_page"),
                    "chunk_ids": section.get("chunk_ids", []),
                    "matched_tags": matched_tags or ([normalized_topic] if reason != "whole_word_keyword" else []),
                    "match_reason": reason,
                    "locator_status": section.get("locator_status", "unknown"),
                    "_sort": (_reason_rank(reason), int((chapter or {}).get("chapter_number") or 10**9), order, int(section.get("start_page") or 10**9)),
                }
            )
    results.sort(key=lambda item: item["_sort"])
    limited = results[: max(0, int(limit or 0))]
    for item in limited:
        item.pop("_sort", None)
    warnings = []
    if content_map.get("_curation_warning"):
        warnings.append(content_map["_curation_warning"])
    return {"document_id": document_id, "topic": normalized_topic, "match_count": len(limited), "results": limited, "warnings": warnings}


def validate_document_provenance_contract(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    return _validate_document_provenance_contract(document_id, root=root, content_map_hint=None)


def get_reader_backend_readiness(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    return _get_reader_backend_readiness(document_id, root=root, manifest_hint=None, content_map_hint=None, provenance_hint=None)


def format_document_content_map_report(document_id: str, public_safe: bool = True, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> str:
    content_map = _load_preferred_content_view(document_id, root=root)
    provenance = validate_document_provenance_contract(document_id, root=root)
    readiness = get_reader_backend_readiness(document_id, root=root)
    lines = [
        "Document Content Map Report",
        "",
        f"Document: {document_id}",
        f"Source Revision: {content_map.get('source_revision')}",
        f"Structure Status: {content_map.get('structure_status')}",
        f"Reader Backend Readiness: {readiness.get('status')}",
        "",
        "Content Structure:",
        f"- Chapters: {len(content_map.get('chapters', []))}",
        f"- Sections: {content_map.get('section_count')}",
        f"- Chunks Assigned: {content_map.get('chunk_count', 0) - len(content_map.get('unassigned_chunk_ids', []))}",
        f"- Chunks Unassigned: {len(content_map.get('unassigned_chunk_ids', []))}",
        f"- Topic Tags: {len(content_map.get('topic_tags', []))}",
        "",
        "Provenance:",
        f"- Status: {provenance.get('status')}",
        f"- Valid Checks: {provenance.get('valid_checks')}",
        f"- Warning Checks: {provenance.get('warning_checks')}",
        f"- Critical Checks: {provenance.get('critical_checks')}",
        "",
        "Topics:",
    ]
    lines.extend([f"- {item}" for item in content_map.get("topic_tags", [])[:20]] or ["- none"])
    lines.extend(["", "Recommended Action:", str(readiness.get("recommended_action"))])
    text = "\n".join(lines)
    return _sanitize(text) if public_safe else text


def get_document_content_map_summary(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    content_map = _load_preferred_content_view(document_id, root=root)
    provenance = validate_document_provenance_contract(document_id, root=root)
    readiness = get_reader_backend_readiness(document_id, root=root)
    curation_status = "not_started"
    curation_readiness = "not_ready"
    try:
        from .document_content_curation import get_document_content_curation_readiness, load_document_content_curation

        curation = load_document_content_curation(document_id, root=root)
        readiness_state = get_document_content_curation_readiness(document_id, root=root)
        curation_status = "current" if curation.get("curation") else "not_started"
        curation_readiness = readiness_state.get("status", "unknown")
    except Exception:
        pass
    return {
        "document_id": document_id,
        "source_revision": content_map.get("source_revision"),
        "structure_status": content_map.get("structure_status"),
        "chapter_count": len(content_map.get("chapters", [])),
        "section_count": content_map.get("section_count", 0),
        "assigned_chunk_count": int(content_map.get("chunk_count", 0) or 0) - len(content_map.get("unassigned_chunk_ids", [])),
        "unassigned_chunk_count": len(content_map.get("unassigned_chunk_ids", [])),
        "topic_tag_count": len(content_map.get("topic_tags", [])),
        "provenance_status": provenance.get("status"),
        "critical_provenance_count": provenance.get("critical_checks", 0),
        "reader_readiness": readiness.get("status"),
        "curation_status": curation_status,
        "curation_readiness": curation_readiness,
        "recommended_action": readiness.get("recommended_action"),
    }


def ensure_document_content_map_dirs(root: Path | str = SOURCE_DOCUMENT_ROOT) -> Path:
    base = ensure_source_knowledge_dirs(root)
    (base / CONTENT_MAP_DIR).mkdir(parents=True, exist_ok=True)
    (base / "indexes").mkdir(parents=True, exist_ok=True)
    index_path = base / "indexes" / CONTENT_MAP_INDEX
    if not index_path.exists():
        _atomic_write_json(index_path, {"entries": [], "updated_at_utc": _now()})
    return base


def _validate_document_provenance_contract(
    document_id: str,
    *,
    root: Path | str,
    content_map_hint: dict | None,
) -> dict:
    base = ensure_document_content_map_dirs(root)
    manifest = load_document_manifest(document_id, root=base).get("manifest") or build_document_manifest(document_id, regenerate=False, root=base)
    content_map = content_map_hint or load_document_content_map(document_id, root=base).get("content_map")
    issues = []
    warnings = []
    checks_run = 0
    chunks = {chunk.chunk_id: chunk for chunk in load_chunks(document_id=document_id, root=base)}
    citations = [item for item in _iter_json(base / "citations", "*.json") if str(item.get("document_id") or "") == document_id]
    citation_ids = {str(item.get("citation_id") or "") for item in citations}
    for citation in citations:
        checks_run += 1
        chunk_id = str(citation.get("chunk_id") or "")
        if chunk_id not in chunks:
            issues.append(_issue("citation_missing_chunk", str(citation.get("citation_id") or ""), "critical", recommended_action="manual_review_required"))
        revision = citation.get("source_revision")
        if revision is not None and revision != manifest.get("source_revision"):
            issues.append(_issue("citation_revision_mismatch", str(citation.get("citation_id") or ""), "warning", expected_revision=manifest.get("source_revision"), actual_revision=revision, recommended_action="manual_revalidation"))
        locator = {
            "document_id": document_id,
            "source_revision": citation.get("source_revision") or manifest.get("source_revision"),
            "page_number": citation.get("page_start"),
            "chunk_id": chunk_id or None,
            "character_start": citation.get("character_start"),
            "character_end": citation.get("character_end"),
        }
        result = validate_source_locator(locator, root=base)
        if not result.get("valid"):
            issues.append(_issue("citation_locator_invalid", str(citation.get("citation_id") or ""), "warning", recommended_action="manual_revalidation"))
    proposals = [proposal.to_json(public_safe=True) for proposal in list_source_proposals(root=base) if proposal.document_id == document_id]
    proposal_ids = {str(item.get("proposal_id") or "") for item in proposals}
    for proposal in proposals:
        checks_run += 1
        for citation_id in proposal.get("citation_ids", []) or []:
            if str(citation_id) not in citation_ids:
                issues.append(_issue("proposal_missing_citation", str(proposal.get("proposal_id") or ""), "warning", recommended_action="manual_review_required"))
    for proposal_id in proposal_ids:
        checks_run += 1
        review = load_proposal_review(proposal_id, root=base, missing_ok=True)
        if review is not None and review.proposal_id != proposal_id:
            issues.append(_issue("proposal_review_mismatch", proposal_id, "critical", recommended_action="manual_review_required"))
    for binder in _iter_json(base / "evidence_binders", "*.json"):
        linked = [item for item in binder.get("linked_citations", []) if isinstance(item, dict)]
        if not (str(binder.get("proposal_id") or "") in proposal_ids or any(str(item.get("document_id") or "") == document_id for item in linked)):
            continue
        checks_run += 1
        if str(binder.get("proposal_id") or "") not in proposal_ids:
            issues.append(_issue("evidence_binder_missing_proposal", str(binder.get("binder_id") or ""), "critical", recommended_action="manual_review_required"))
        for item in linked:
            if str(item.get("citation_id") or "") not in citation_ids:
                issues.append(_issue("evidence_binder_missing_citation", str(binder.get("binder_id") or ""), "critical", recommended_action="manual_review_required"))
    if isinstance(content_map, dict):
        checks_run += 1
        if content_map.get("source_revision") != manifest.get("source_revision"):
            issues.append(_issue("content_map_revision_mismatch", str(content_map.get("content_map_id") or document_id), "warning", expected_revision=manifest.get("source_revision"), actual_revision=content_map.get("source_revision"), recommended_action="rebuild_content_map"))
        current_fp = build_document_scoped_fingerprint(document_id, root=base).get("fingerprint")
        if content_map.get("document_scoped_fingerprint") != current_fp:
            issues.append(_issue("content_map_fingerprint_mismatch", str(content_map.get("content_map_id") or document_id), "warning", recommended_action="rebuild_content_map"))
        for section in content_map.get("sections", []):
            checks_run += 1
            chunk_ids = [str(item) for item in section.get("chunk_ids", [])]
            for chunk_id in chunk_ids:
                if chunk_id not in chunks:
                    issues.append(_issue("content_map_missing_chunk", str(section.get("section_id") or ""), "critical", recommended_action="rebuild_content_map"))
            if chunk_ids:
                start_page = section.get("start_page")
                end_page = section.get("end_page")
                for chunk_id in chunk_ids:
                    chunk = chunks.get(chunk_id)
                    if chunk and start_page is not None and end_page is not None and chunk.page_start is not None and chunk.page_end is not None:
                        if chunk.page_start < start_page or chunk.page_end > end_page:
                            issues.append(_issue("content_map_page_range_mismatch", str(section.get("section_id") or ""), "warning", recommended_action="rebuild_content_map"))
                            break
    status = "critical" if any(item["severity"] == "critical" for item in issues) else "warning" if issues else "valid"
    if not isinstance(content_map, dict):
        warnings.append("content_map_not_available")
        status = "unknown" if status == "valid" else status
    return {
        "document_id": document_id,
        "status": status,
        "checks_run": checks_run,
        "valid_checks": max(0, checks_run - len(issues)),
        "warning_checks": sum(1 for issue in issues if issue["severity"] == "warning"),
        "critical_checks": sum(1 for issue in issues if issue["severity"] == "critical"),
        "issues": issues,
        "warnings": warnings,
    }


def _get_reader_backend_readiness(
    document_id: str,
    *,
    root: Path | str,
    manifest_hint: dict | None,
    content_map_hint: dict | None,
    provenance_hint: dict | None,
) -> dict:
    base = ensure_document_content_map_dirs(root)
    manifest = manifest_hint or load_document_manifest(document_id, root=base).get("manifest")
    if not isinstance(manifest, dict):
        return {"document_id": document_id, "status": "not_ready", "requirements": {"manifest_current": False}, "blockers": ["manifest_missing"], "warnings": [], "recommended_action": "Build the canonical manifest before PDF-reader integration."}
    record = load_source_document(document_id, root=base, missing_ok=True)
    content_map = content_map_hint or load_document_content_map(document_id, root=base).get("content_map")
    provenance = provenance_hint or _validate_document_provenance_contract(document_id, root=base, content_map_hint=content_map)
    current_fp = build_document_scoped_fingerprint(document_id, root=base).get("fingerprint")
    requirements = {
        "manifest_current": True,
        "source_revision_current": not bool(manifest.get("revision_changed")),
        "extraction_complete": (manifest.get("pipeline") or {}).get("extraction") == "complete",
        "chunks_available": (manifest.get("pipeline") or {}).get("chunking") == "complete",
        "page_diagnostics_available": (manifest.get("pipeline") or {}).get("page_diagnostics") == "complete",
        "structure_available": (manifest.get("pipeline") or {}).get("structure_map") == "complete",
        "content_map_available": isinstance(content_map, dict),
        "fingerprint_current": isinstance(content_map, dict) and content_map.get("document_scoped_fingerprint") == current_fp,
        "provenance_valid": provenance.get("critical_checks", 0) == 0 and provenance.get("status") in {"valid", "warning"},
    }
    blockers = []
    warnings = []
    try:
        from .document_content_curation import get_document_content_curation_readiness, load_document_content_curation

        curation = load_document_content_curation(document_id, root=base)
        curation_readiness = get_document_content_curation_readiness(document_id, root=base)
        if curation.get("curation") and curation_readiness.get("status") in {"stale", "invalid"}:
            warnings.append(f"curation_{curation_readiness.get('status')}")
    except Exception:
        pass
    if record is None:
        blockers.append("registered_source_missing")
    if not requirements["extraction_complete"]:
        blockers.append("extraction_missing")
    if not requirements["chunks_available"]:
        blockers.append("chunks_missing")
    if not requirements["page_diagnostics_available"]:
        blockers.append("page_diagnostics_missing")
    if not requirements["structure_available"]:
        blockers.append("structure_map_missing")
    if not requirements["content_map_available"]:
        blockers.append("content_map_missing")
    if provenance.get("critical_checks", 0):
        blockers.append("critical_provenance_issues")
    if manifest.get("revision_changed") or (isinstance(content_map, dict) and content_map.get("source_revision") != manifest.get("source_revision")):
        return {"document_id": document_id, "status": "stale", "requirements": requirements, "blockers": ["source_revision_changed"], "warnings": warnings, "recommended_action": "Refresh dependent backend records before PDF-reader integration."}
    if blockers:
        status = "corrupt" if "critical_provenance_issues" in blockers else "not_ready"
        action = "Build page diagnostics before PDF-reader integration." if "page_diagnostics_missing" in blockers else "Complete the controlled backend content steps before PDF-reader integration."
        return {"document_id": document_id, "status": status, "requirements": requirements, "blockers": blockers, "warnings": warnings, "recommended_action": action}
    if isinstance(content_map, dict):
        if content_map.get("structure_status") == "section_only" or content_map.get("unassigned_chunk_ids"):
            warnings.extend(["section_only_structure" if content_map.get("structure_status") == "section_only" else "", "unassigned_chunks_present" if content_map.get("unassigned_chunk_ids") else ""])
            return {"document_id": document_id, "status": "ready_with_warnings", "requirements": requirements, "blockers": [], "warnings": [item for item in warnings if item], "recommended_action": "Review remaining warnings before PDF-reader integration."}
    return {"document_id": document_id, "status": "ready", "requirements": requirements, "blockers": [], "warnings": [], "recommended_action": "Backend structure is ready for future PDF-reader integration."}


def _content_map_path(root: Path, document_id: str) -> Path:
    return root / CONTENT_MAP_DIR / f"{document_id}.json"


def _update_content_map_index(root: Path) -> None:
    entries = []
    for path in sorted((root / CONTENT_MAP_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict):
            entries.append(
                {
                    "document_id": payload.get("document_id"),
                    "source_revision": payload.get("source_revision"),
                    "structure_status": payload.get("structure_status"),
                    "reader_backend_readiness": payload.get("reader_backend_readiness"),
                    "updated_at_utc": payload.get("updated_at_utc"),
                }
            )
    _atomic_write_json(root / "indexes" / CONTENT_MAP_INDEX, {"entries": entries, "updated_at_utc": _now()})


def _content_map_hash_payload(content_map: dict | None) -> dict | None:
    if not isinstance(content_map, dict):
        return None
    payload = dict(content_map)
    for key in ("document_scoped_fingerprint", "created_at_utc", "updated_at_utc"):
        payload.pop(key, None)
    return payload


def _load_preferred_content_view(document_id: str, *, root: Path | str) -> dict:
    detected = build_document_content_map(document_id, regenerate=False, root=root)
    try:
        from .document_content_curation import build_curated_document_content_map, get_document_content_curation_readiness

        readiness = get_document_content_curation_readiness(document_id, root=root)
        if readiness.get("status") in {"ready", "ready_with_warnings"}:
            return build_curated_document_content_map(document_id, root=root)
        if readiness.get("status") in {"stale", "invalid"}:
            detected = dict(detected)
            detected["_curation_warning"] = "curated_state_not_applied"
    except Exception:
        return detected
    return detected


def _iter_json(folder: Path, pattern: str) -> list[dict[str, object]]:
    items = []
    if not folder.exists():
        return items
    for path in sorted(folder.glob(pattern)):
        payload = _read_json(path)
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _hash_payload(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _component_hash(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, dict)) and not value:
        return None
    return _hash_payload(value)


def _hash_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, object] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


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


def _normalize_topic(value: object) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"[^\w\s\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -")
    return text


def _title_terms(value: object) -> set[str]:
    normalized = _normalize_topic(value)
    if not normalized:
        return set()
    return {normalized} | {item for item in normalized.split(" ") if item}


def _reason_rank(reason: str) -> int:
    return {"exact_topic_tag": 0, "exact_section_title": 1, "exact_chapter_title": 2, "whole_word_keyword": 3}.get(reason, 9)


def _issue(issue_type: str, record_id: str, severity: str, **extra: object) -> dict[str, object]:
    payload = {"issue_type": issue_type, "record_id": record_id, "severity": severity}
    payload.update(extra)
    return payload


def _sanitize(text: str) -> str:
    return text.replace(str(Path.cwd()), "[workspace]").replace(str(SOURCE_DOCUMENT_ROOT), "[source-root]").replace("\\", "/")


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
