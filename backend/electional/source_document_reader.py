"""Controlled document reader, diagnostics, and deep search for source documents."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Mapping

from .document_preflight import get_document_preflight_summary
from .document_structure import get_document_structure_summary
from .source_documents import SOURCE_DOCUMENT_ROOT, STATUS_EXTRACTED, get_extracted_text, list_source_documents, load_source_document
from .source_knowledge import (
    SourceChunk,
    create_manual_proposal,
    create_source_citation,
    ensure_source_knowledge_dirs,
    list_source_proposals,
    load_chunk,
    load_chunks,
)

PAGE_DIAGNOSTICS_SCHEMA_VERSION = "source_page_diagnostics_v1"
SEARCH_SCHEMA_VERSION = "source_document_search_v1"
READER_DIRS = ("page_diagnostics", "indexes", "search_feedback")
KEYWORDS = (
    "hard gate",
    "manual review",
    "confidence",
    "citation",
    "proposal",
    "rule pack",
    "objective pack",
    "preflight",
    "privacy",
    "warning",
    "block",
    "threshold",
    "source",
)


@dataclass(frozen=True)
class PageDiagnostic:
    document_id: str
    page_number: int
    char_count: int
    word_count: int
    line_count: int
    status: str
    quality_score: float
    flags: tuple[str, ...]
    top_keywords: tuple[dict[str, object], ...]
    warnings: tuple[str, ...]
    created_at_utc: str
    schema_version: str = PAGE_DIAGNOSTICS_SCHEMA_VERSION

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["flags"] = list(self.flags)
        payload["top_keywords"] = [dict(item) for item in self.top_keywords]
        payload["warnings"] = list(self.warnings)
        return payload


@dataclass(frozen=True)
class DocumentSearchResult:
    result_id: str
    document_id: str
    chunk_id: str
    page_start: int | None
    page_end: int | None
    match_count: int
    score: float
    snippet: str
    warnings: tuple[str, ...]
    schema_version: str = SEARCH_SCHEMA_VERSION

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["warnings"] = list(self.warnings)
        return payload


@dataclass(frozen=True)
class SourceSearchHealth:
    status: str
    documents: int
    documents_with_chunks: int
    chunks_indexed: int
    broken_chunk_links: int
    low_quality_chunks: int
    documents_without_preflight: int
    documents_without_chunks: int
    proposals_linked: int
    citations_linked: int
    warnings: tuple[str, ...]

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["warnings"] = list(self.warnings)
        return payload


def ensure_document_reader_dirs(root: Path | str = SOURCE_DOCUMENT_ROOT) -> Path:
    base = ensure_source_knowledge_dirs(root)
    for folder in READER_DIRS:
        (base / folder).mkdir(parents=True, exist_ok=True)
    return base


def build_page_diagnostics(document_id: str, *, regenerate: bool = False, root: Path | str = SOURCE_DOCUMENT_ROOT) -> list[PageDiagnostic]:
    base = ensure_document_reader_dirs(root)
    existing = load_page_diagnostics(document_id, root=base)
    if existing and not regenerate:
        return existing
    pages, warnings = _page_text_map(document_id, root=base)
    if not pages:
        _atomic_write_json(_diagnostic_path(base, document_id), {"document_id": document_id, "pages": [], "warnings": warnings, "schema_version": PAGE_DIAGNOSTICS_SCHEMA_VERSION})
        _update_page_diagnostics_index(base)
        return []
    diagnostics = [_diagnose_page(document_id, number, text) for number, text in sorted(pages.items())]
    payload = {
        "document_id": document_id,
        "pages": [item.to_json() for item in diagnostics],
        "warnings": warnings,
        "schema_version": PAGE_DIAGNOSTICS_SCHEMA_VERSION,
    }
    _atomic_write_json(_diagnostic_path(base, document_id), payload)
    _update_page_diagnostics_index(base)
    return diagnostics


def load_page_diagnostics(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> list[PageDiagnostic]:
    path = _diagnostic_path(ensure_document_reader_dirs(root), document_id)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [_page_diagnostic_from_json(item) for item in data.get("pages", []) if isinstance(item, Mapping)]


def get_page_diagnostic_summary(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_document_reader_dirs(root)
    diagnostics = load_page_diagnostics(document_id, root=base)
    pages, warnings = _page_text_map(document_id, root=base)
    page_total = len(pages) if pages else None
    return {
        "document_id": document_id,
        "pages_total": page_total,
        "pages_diagnosed": len(diagnostics),
        "ok_pages": sum(1 for item in diagnostics if item.status == "ok"),
        "low_quality_pages": sum(1 for item in diagnostics if item.quality_score < 0.7 or item.status in {"low_text_density", "garbled_suspected"}),
        "empty_pages": sum(1 for item in diagnostics if item.status == "empty"),
        "garbled_pages": sum(1 for item in diagnostics if item.status == "garbled_suspected"),
        "warnings": list(warnings) + ([] if diagnostics else ["page_diagnostics_unavailable"]),
    }


def get_document_reader_state(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_document_reader_dirs(root)
    record = load_source_document(document_id, root=base, missing_ok=True)
    chunks = load_chunks(document_id=document_id, root=base)
    diagnostics = load_page_diagnostics(document_id, root=base)
    preflight = get_document_preflight_summary(document_id, root=base)
    title = None
    if record:
        title = record.original_filename
    return {
        "document_id": document_id,
        "title": title or document_id,
        "has_extracted_text": bool(record and record.extraction_status == STATUS_EXTRACTED and get_extracted_text(document_id, root=base).strip()),
        "has_chunks": bool(chunks),
        "has_page_diagnostics": bool(diagnostics),
        "chunk_count": len(chunks),
        "page_count": record.page_count if record else None,
        "preflight_verdict": preflight.get("verdict"),
        "warnings": [] if record else ["document_missing"],
    }


def get_document_page_text(document_id: str, page_number: int, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    pages, warnings = _page_text_map(document_id, root=ensure_document_reader_dirs(root))
    if page_number not in pages:
        return {"document_id": document_id, "page_number": page_number, "text": "", "warnings": warnings or ["page_text_unavailable"]}
    return {"document_id": document_id, "page_number": page_number, "text": pages[page_number], "warnings": []}


def get_document_chunk_text(chunk_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    chunk = load_chunk(chunk_id, root=ensure_document_reader_dirs(root))
    return {"document_id": chunk.document_id, "chunk_id": chunk.chunk_id, "page_start": chunk.page_start, "page_end": chunk.page_end, "text": chunk.text, "warnings": list(chunk.warnings)}


def list_document_chunks(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> list[dict[str, object]]:
    return [chunk.to_json(public_safe=True) for chunk in load_chunks(document_id=document_id, root=ensure_document_reader_dirs(root))]


def search_document(
    query: str,
    *,
    document_id: str | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
    mode: str = "keyword",
    case_sensitive: bool = False,
    limit: int = 20,
    filters: dict[str, object] | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> list[DocumentSearchResult]:
    base = ensure_document_reader_dirs(root)
    query_text = query or ""
    if not query_text.strip():
        return []
    filters = filters or {}
    chunks = load_chunks(document_id=document_id, root=base)
    citation_chunks = {item.get("chunk_id") for item in _load_citation_json(base)}
    proposal_chunks = {proposal.chunk_id for proposal in list_source_proposals(root=base)}
    results: list[DocumentSearchResult] = []
    for chunk in chunks:
        if filters.get("chunk_id") and chunk.chunk_id != filters.get("chunk_id"):
            continue
        if page_start is not None and chunk.page_end is not None and chunk.page_end < page_start:
            continue
        if page_end is not None and chunk.page_start is not None and chunk.page_start > page_end:
            continue
        if filters.get("low_quality_only") and chunk.quality_score >= 0.7:
            continue
        if filters.get("has_warning") and not chunk.warnings:
            continue
        if filters.get("has_proposal") and chunk.chunk_id not in proposal_chunks:
            continue
        if filters.get("has_citation") and chunk.chunk_id not in citation_chunks:
            continue
        match_count, score = _match_score(chunk.text, query_text, mode=mode, case_sensitive=case_sensitive)
        if match_count <= 0:
            continue
        result_id = "search_" + _hash_text("|".join([chunk.document_id, chunk.chunk_id, query_text, mode]))[7:23]
        results.append(
            DocumentSearchResult(
                result_id=result_id,
                document_id=chunk.document_id,
                chunk_id=chunk.chunk_id,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                match_count=match_count,
                score=score,
                snippet=_snippet(chunk.text, query_text, mode=mode, case_sensitive=case_sensitive),
                warnings=chunk.warnings,
            )
        )
    results.sort(key=lambda item: (-item.score, item.page_start if item.page_start is not None else 10**9, item.chunk_id))
    return results[: max(0, int(limit or 0))]


def get_search_result_context(result: DocumentSearchResult | Mapping[str, object], *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    payload = result.to_json() if isinstance(result, DocumentSearchResult) else dict(result)
    chunk_id = str(payload.get("chunk_id") or "")
    if not chunk_id:
        return {"warnings": ["search_result_missing_chunk"]}
    chunk = load_chunk(chunk_id, root=ensure_document_reader_dirs(root))
    return {"result": payload, "chunk": chunk.to_json(public_safe=True), "snippet": payload.get("snippet") or "", "warnings": []}


def create_proposal_from_search_result(result: DocumentSearchResult | Mapping[str, object], claim: str, *, proposal_type: str = "manual_note", root: Path | str = SOURCE_DOCUMENT_ROOT):
    payload = result.to_json() if isinstance(result, DocumentSearchResult) else dict(result)
    document_id = str(payload.get("document_id") or "")
    chunk_id = str(payload.get("chunk_id") or "")
    if not document_id or not chunk_id:
        raise ValueError("Search result must include document_id and chunk_id.")
    return create_manual_proposal(document_id, chunk_id, claim, proposal_type=proposal_type, root=ensure_document_reader_dirs(root))


def create_citation_from_search_result(result: DocumentSearchResult | Mapping[str, object], note: str, *, quote_excerpt: str | None = None, root: Path | str = SOURCE_DOCUMENT_ROOT):
    payload = result.to_json() if isinstance(result, DocumentSearchResult) else dict(result)
    document_id = str(payload.get("document_id") or "")
    chunk_id = str(payload.get("chunk_id") or "")
    if not document_id or not chunk_id:
        raise ValueError("Search result must include document_id and chunk_id.")
    excerpt = quote_excerpt or str(payload.get("snippet") or "")
    return create_source_citation(document_id, chunk_id, note, quote_excerpt=excerpt, root=ensure_document_reader_dirs(root))


def mark_search_result_feedback(result: DocumentSearchResult | Mapping[str, object], feedback: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_document_reader_dirs(root)
    payload = result.to_json() if isinstance(result, DocumentSearchResult) else dict(result)
    if feedback not in {"useful", "bad_extraction"}:
        raise ValueError("Unsupported search feedback.")
    feedback_id = "feedback_" + _hash_text("|".join([str(payload.get("result_id") or ""), feedback]))[7:23]
    record = {"feedback_id": feedback_id, "feedback": feedback, "result": payload, "created_at_utc": _now()}
    _atomic_write_json(base / "search_feedback" / f"{feedback_id}.json", record)
    return record


def build_citation_snippet(document_id: str, chunk_id: str, *, query: str | None = None, max_chars: int = 400, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_document_reader_dirs(root)
    chunk = load_chunk(chunk_id, root=base)
    if chunk.document_id != document_id:
        raise ValueError("Snippet document_id must match chunk document_id.")
    excerpt = _snippet(chunk.text, query or "", mode="keyword", case_sensitive=False) if query else chunk.text.strip()
    truncated = len(excerpt) > max_chars
    if truncated:
        excerpt = excerpt[: max(0, max_chars - 3)].rstrip() + "..."
    preflight = get_document_preflight_summary(document_id, root=base)
    warnings: list[str] = []
    redacted = _redact_sensitive(excerpt)
    if preflight.get("privacy_findings") or redacted != excerpt:
        excerpt = redacted
        warnings.append("sensitive_values_redacted")
    return {
        "document_id": document_id,
        "chunk_id": chunk_id,
        "page_start": chunk.page_start,
        "page_end": chunk.page_end,
        "excerpt": excerpt,
        "excerpt_hash": _hash_text(excerpt),
        "truncated": truncated,
        "warnings": warnings,
    }


def get_source_search_health(document_id: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> SourceSearchHealth:
    base = ensure_document_reader_dirs(root)
    documents = [doc for doc in list_source_documents(root=base) if document_id is None or doc.document_id == document_id]
    chunks = load_chunks(document_id=document_id, root=base)
    chunk_ids = {chunk.chunk_id for chunk in chunks}
    proposals = [item for item in list_source_proposals(root=base) if document_id is None or item.document_id == document_id]
    citations = [item for item in _load_citation_json(base) if document_id is None or item.get("document_id") == document_id]
    broken = sum(1 for item in proposals if item.chunk_id not in chunk_ids) + sum(1 for item in citations if item.get("chunk_id") not in chunk_ids)
    docs_with_chunks = {chunk.document_id for chunk in chunks}
    warnings: list[str] = []
    if not chunks:
        warnings.append("no_chunks")
    if broken:
        warnings.append("broken_chunk_links")
    extracted_without_chunks = [doc.document_id for doc in documents if doc.extraction_status == STATUS_EXTRACTED and doc.document_id not in docs_with_chunks]
    if extracted_without_chunks:
        warnings.append("documents_extracted_but_not_chunked")
    docs_without_preflight = sum(1 for doc in documents if not get_document_preflight_summary(doc.document_id, root=base).get("has_preflight"))
    if docs_without_preflight:
        warnings.append("documents_without_preflight")
    low_quality = sum(1 for chunk in chunks if chunk.quality_score < 0.7)
    if low_quality:
        warnings.append("low_quality_chunks")
    status = "critical" if broken else "warning" if warnings else "healthy"
    return SourceSearchHealth(
        status=status,
        documents=len(documents),
        documents_with_chunks=len(docs_with_chunks),
        chunks_indexed=len(chunks),
        broken_chunk_links=broken,
        low_quality_chunks=low_quality,
        documents_without_preflight=docs_without_preflight,
        documents_without_chunks=len(extracted_without_chunks),
        proposals_linked=sum(1 for item in proposals if item.chunk_id in chunk_ids),
        citations_linked=sum(1 for item in citations if item.get("chunk_id") in chunk_ids),
        warnings=tuple(warnings),
    )



def get_search_ui_state(document_id: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    health = get_source_search_health(document_id, root=root)
    if not document_id:
        return {
            "status": "no_document",
            "document_id": None,
            "reader_state": None,
            "search_health": health.to_json(),
            "results": [],
            "selected_result": None,
            "selected_actions": _selected_actions(False),
            "warnings": ["no_document_selected"],
        }
    reader_state = get_document_reader_state(document_id, root=root)
    warnings = list(reader_state.get("warnings", []))
    if not reader_state.get("has_chunks"):
        warnings.append("not_chunked")
    return {
        "status": "ready" if reader_state.get("has_chunks") else "not_chunked",
        "document_id": document_id,
        "reader_state": reader_state,
        "search_health": health.to_json(),
        "results": [],
        "selected_result": None,
        "selected_actions": _selected_actions(False),
        "warnings": warnings,
    }


def run_document_search_for_ui(
    document_id: str | None,
    query: str,
    *,
    mode: str = "keyword",
    page_start: int | None = None,
    page_end: int | None = None,
    limit: int = 20,
    filters: dict[str, object] | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, object]:
    state = get_search_ui_state(document_id, root=root)
    if not document_id:
        return state
    if not query.strip():
        state["status"] = "blank_query"
        state["warnings"] = list(state.get("warnings", [])) + ["blank_query"]
        return state
    if state.get("status") == "not_chunked":
        return state
    results = search_document(
        query,
        document_id=document_id,
        page_start=page_start,
        page_end=page_end,
        mode=mode,
        limit=limit,
        filters=filters,
        root=root,
    )
    state["status"] = "ok" if results else "no_results"
    state["query"] = query
    state["mode"] = mode
    state["results"] = [item.to_json() for item in results]
    state["selected_result"] = None
    state["selected_actions"] = _selected_actions(False)
    return state


def select_search_result_for_ui(search_state: Mapping[str, object], result_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    state = dict(search_state)
    results = [dict(item) for item in state.get("results", []) if isinstance(item, Mapping)]
    selected = next((item for item in results if item.get("result_id") == result_id), None)
    if selected is None:
        state["selected_result"] = None
        state["selected_actions"] = _selected_actions(False)
        state["warnings"] = list(state.get("warnings", [])) + ["selected_result_not_in_current_results"]
        return state
    context = get_search_result_context(selected, root=root)
    snippet = build_citation_snippet(str(selected["document_id"]), str(selected["chunk_id"]), query=str(state.get("query") or ""), root=root)
    state["selected_result"] = {
        "selected_result_id": selected.get("result_id"),
        "selected_document_id": selected.get("document_id"),
        "selected_chunk_id": selected.get("chunk_id"),
        "selected_page_start": selected.get("page_start"),
        "selected_page_end": selected.get("page_end"),
        "selected_snippet": snippet.get("excerpt") or selected.get("snippet") or "",
        "selected_match_count": selected.get("match_count"),
        "selected_warnings": list(selected.get("warnings", [])) + list(snippet.get("warnings", [])),
        "context": context,
    }
    state["selected_actions"] = _selected_actions(True)
    return state


def create_proposal_from_selected_result(search_state: Mapping[str, object], claim: str, *, proposal_type: str = "manual_note", root: Path | str = SOURCE_DOCUMENT_ROOT):
    selected = _require_selected_result(search_state)
    return create_proposal_from_search_result(_selected_to_result_payload(selected), claim, proposal_type=proposal_type, root=root)


def create_citation_from_selected_result(search_state: Mapping[str, object], note: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT):
    selected = _require_selected_result(search_state)
    return create_citation_from_search_result(_selected_to_result_payload(selected), note, quote_excerpt=str(selected.get("selected_snippet") or ""), root=root)


def copy_snippet_from_selected_result(search_state: Mapping[str, object]) -> str:
    selected = _require_selected_result(search_state)
    snippet = str(selected.get("selected_snippet") or "")
    if not snippet:
        raise ValueError("Selected result has no snippet.")
    return snippet


def mark_selected_result_feedback(search_state: Mapping[str, object], feedback: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    selected = _require_selected_result(search_state)
    return mark_search_result_feedback(_selected_to_result_payload(selected), feedback, root=root)


def _selected_actions(enabled: bool) -> dict[str, bool]:
    return {
        "open_chunk": enabled,
        "open_page": enabled,
        "copy_snippet": enabled,
        "create_proposal": enabled,
        "create_citation": enabled,
        "mark_useful": enabled,
        "mark_bad_extraction": enabled,
    }


def _require_selected_result(search_state: Mapping[str, object]) -> Mapping[str, object]:
    selected = search_state.get("selected_result")
    if not isinstance(selected, Mapping) or not selected.get("selected_chunk_id") or not selected.get("selected_document_id"):
        raise ValueError("No valid search result is selected.")
    return selected


def _selected_to_result_payload(selected: Mapping[str, object]) -> dict[str, object]:
    return {
        "result_id": selected.get("selected_result_id"),
        "document_id": selected.get("selected_document_id"),
        "chunk_id": selected.get("selected_chunk_id"),
        "page_start": selected.get("selected_page_start"),
        "page_end": selected.get("selected_page_end"),
        "match_count": selected.get("selected_match_count"),
        "snippet": selected.get("selected_snippet"),
        "warnings": selected.get("selected_warnings", []),
    }
def _page_text_map(document_id: str, *, root: Path) -> tuple[dict[int, str], list[str]]:
    try:
        text = get_extracted_text(document_id, root=root)
    except FileNotFoundError:
        return {}, ["document_missing"]
    if not text.strip():
        return {}, ["extracted_text_unavailable"]
    matches = list(re.finditer(r"---\s*Page\s+(\d+)\s*---", text, flags=re.IGNORECASE))
    if not matches:
        return {}, ["page_text_unavailable"]
    pages: dict[int, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        pages[int(match.group(1))] = text[start:end].strip()
    return pages, []


def _diagnose_page(document_id: str, page_number: int, text: str) -> PageDiagnostic:
    cleaned = text.strip()
    words = re.findall(r"\b\w+\b", cleaned)
    lines = [line for line in cleaned.splitlines() if line.strip()]
    flags: list[str] = []
    warnings: list[str] = []
    if not cleaned:
        status = "empty"
        flags.append("empty")
    elif len(cleaned) < 120:
        status = "low_text_density"
        flags.append("low_text_density")
    elif _garbled_ratio(cleaned) > 0.02:
        status = "garbled_suspected"
        flags.append("garbled_suspected")
        warnings.append("garbled_text_suspected")
    elif _table_like(cleaned):
        status = "table_heavy"
        flags.append("possible_table")
    else:
        status = "ok"
    quality = _page_quality(cleaned)
    return PageDiagnostic(
        document_id=document_id,
        page_number=page_number,
        char_count=len(cleaned),
        word_count=len(words),
        line_count=len(lines),
        status=status,
        quality_score=quality,
        flags=tuple(flags),
        top_keywords=tuple(_top_keywords(cleaned)),
        warnings=tuple(warnings),
        created_at_utc=_now(),
    )


def _match_score(text: str, query: str, *, mode: str, case_sensitive: bool) -> tuple[int, float]:
    haystack = text if case_sensitive else text.lower()
    needle = query if case_sensitive else query.lower()
    terms = [term if case_sensitive else term.lower() for term in re.findall(r"\w+", query)]
    if mode == "exact_phrase":
        count = haystack.count(needle)
        return count, float(count * max(1, len(terms)))
    if mode == "all_terms":
        counts = [haystack.count(term) for term in terms]
        if not terms or any(count <= 0 for count in counts):
            return 0, 0.0
        return sum(counts), float(sum(counts) + len(terms))
    if mode == "any_terms" or mode == "keyword":
        count = sum(haystack.count(term) for term in terms)
        return count, float(count)
    raise ValueError(f"Unsupported search mode: {mode}")


def _snippet(text: str, query: str, *, mode: str, case_sensitive: bool) -> str:
    search_text = text if case_sensitive else text.lower()
    query_text = query if case_sensitive else query.lower()
    terms = [query_text] if mode == "exact_phrase" else [term if case_sensitive else term.lower() for term in re.findall(r"\w+", query)]
    positions = [search_text.find(term) for term in terms if term and search_text.find(term) >= 0]
    if not positions:
        return text[:220].strip()
    start = max(0, min(positions) - 90)
    end = min(len(text), min(positions) + 240)
    return ("..." if start else "") + text[start:end].strip() + ("..." if end < len(text) else "")


def _top_keywords(text: str) -> list[dict[str, object]]:
    lower = text.lower()
    rows = []
    for term in KEYWORDS:
        count = lower.count(term.lower())
        if count:
            rows.append({"term": term, "count": count})
    rows.sort(key=lambda item: (-int(item["count"]), str(item["term"])))
    return rows[:5]


def _page_quality(text: str) -> float:
    if not text.strip():
        return 0.0
    score = 1.0
    if len(text.strip()) < 120:
        score -= 0.35
    score -= min(0.4, _garbled_ratio(text) * 6)
    return round(max(0.0, min(1.0, score)), 2)


def _garbled_ratio(text: str) -> float:
    return (text.count("\ufffd") + sum(1 for char in text if ord(char) < 32 and char not in "\n\r\t")) / max(1, len(text))


def _table_like(text: str) -> bool:
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 4:
        return False
    table_lines = sum(1 for line in lines if line.count("|") >= 2 or len(re.findall(r"\s{2,}", line)) >= 2)
    return table_lines / len(lines) >= 0.5


def _redact_sensitive(text: str) -> str:
    patterns = (
        (r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email redacted]"),
        (r"[A-Za-z]:\\[^\s]+|/Users/[^\s]+", "[local path redacted]"),
        (r"\b(?:api[_-]?key|token|secret)[\w\s:=.-]{0,20}[A-Za-z0-9_-]{8,}\b", "[token redacted]"),
    )
    redacted = text
    for pattern, repl in patterns:
        redacted = re.sub(pattern, repl, redacted, flags=re.IGNORECASE)
    return redacted


def _load_citation_json(root: Path) -> list[dict[str, object]]:
    rows = []
    for path in sorted((root / "citations").glob("*.json")):
        try:
            rows.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return rows


def _page_diagnostic_from_json(data: Mapping[str, object]) -> PageDiagnostic:
    return PageDiagnostic(
        document_id=str(data["document_id"]),
        page_number=int(data["page_number"]),
        char_count=int(data.get("char_count", 0) or 0),
        word_count=int(data.get("word_count", 0) or 0),
        line_count=int(data.get("line_count", 0) or 0),
        status=str(data.get("status") or "unknown"),
        quality_score=float(data.get("quality_score", 0.0) or 0.0),
        flags=tuple(str(item) for item in data.get("flags", []) if item),
        top_keywords=tuple(dict(item) for item in data.get("top_keywords", []) if isinstance(item, Mapping)),
        warnings=tuple(str(item) for item in data.get("warnings", []) if item),
        created_at_utc=str(data.get("created_at_utc") or _now()),
    )


def _update_page_diagnostics_index(root: Path) -> None:
    entries = []
    for path in sorted((root / "page_diagnostics").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        pages = data.get("pages", []) if isinstance(data, dict) else []
        entries.append({"document_id": data.get("document_id"), "path": str(path), "pages_diagnosed": len(pages)})
    _atomic_write_json(root / "indexes" / "page_diagnostics_index.json", {"entries": entries})


def _diagnostic_path(root: Path, document_id: str) -> Path:
    return ensure_document_reader_dirs(root) / "page_diagnostics" / f"{_safe_id(document_id)}.json"


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


