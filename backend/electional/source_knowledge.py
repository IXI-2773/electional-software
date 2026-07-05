"""Controlled knowledge layer for extracted PDF source text."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from .source_documents import SOURCE_DOCUMENT_ROOT, STATUS_EXTRACTED, get_extracted_text, list_source_documents, load_source_document


CHUNK_SCHEMA_VERSION = "source_chunk_v1"
PROPOSAL_SCHEMA_VERSION = "source_proposal_v1"
CITATION_SCHEMA_VERSION = "source_citation_v1"
KNOWLEDGE_SCHEMA_VERSION = "phase6b_source_knowledge_v1"
KNOWLEDGE_DIRS = ("chunks", "proposals", "citations", "indexes", "quarantine")
VALID_PROPOSAL_STATUSES = {"pending_review", "needs_edit", "approved", "rejected", "archived"}
VALID_PROPOSAL_TYPES = {
    "manual_note",
    "possible_rule",
    "quality_gate",
    "threshold",
    "reporting_note",
    "objective_pack_note",
    "fast_lane_wording_note",
}


@dataclass(frozen=True)
class SourceChunk:
    chunk_id: str
    document_id: str
    source_document_id: str
    chunk_number: int
    page_start: int | None
    page_end: int | None
    section_title: str | None
    text: str
    text_hash: str
    char_count: int
    quality_score: float
    created_at_utc: str
    warnings: tuple[str, ...]
    schema_version: str = CHUNK_SCHEMA_VERSION

    def to_json(self, *, public_safe: bool = False) -> dict[str, object]:
        payload = asdict(self)
        payload["warnings"] = list(self.warnings)
        if public_safe:
            payload.pop("text", None)
        return payload


@dataclass(frozen=True)
class SourceSearchResult:
    chunk_id: str
    document_id: str
    page_start: int | None
    page_end: int | None
    snippet: str
    score: float
    warnings: tuple[str, ...]

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["warnings"] = list(self.warnings)
        return payload


@dataclass(frozen=True)
class SourceProposal:
    proposal_id: str
    document_id: str
    chunk_id: str
    claim: str
    proposed_condition: str | None
    proposed_effect: str | None
    proposal_type: str
    status: str
    created_by: str
    created_at_utc: str
    updated_at_utc: str
    warnings: tuple[str, ...]
    schema_version: str = PROPOSAL_SCHEMA_VERSION

    def to_json(self, *, public_safe: bool = False) -> dict[str, object]:
        payload = asdict(self)
        payload["warnings"] = list(self.warnings)
        if public_safe:
            payload["claim"] = ""
            payload["proposed_condition"] = None
            payload["proposed_effect"] = None
        return payload


@dataclass(frozen=True)
class SourceCitation:
    citation_id: str
    document_id: str
    chunk_id: str
    page_start: int | None
    page_end: int | None
    note: str
    quote_excerpt: str
    created_at_utc: str
    warnings: tuple[str, ...]
    schema_version: str = CITATION_SCHEMA_VERSION

    def to_json(self, *, public_safe: bool = False) -> dict[str, object]:
        payload = asdict(self)
        payload["warnings"] = list(self.warnings)
        if public_safe:
            payload["note"] = ""
            payload["quote_excerpt"] = ""
        return payload


@dataclass(frozen=True)
class SourceKnowledgeHealth:
    status: str
    documents: int
    registered_documents: int
    extracted_documents: int
    needs_ocr: int
    invalid_documents: int
    chunks: int
    low_quality_chunks: int
    proposals_total: int
    proposals_pending: int
    proposals_approved: int
    proposals_rejected: int
    citations: int
    warnings: tuple[str, ...]
    schema_version: str = KNOWLEDGE_SCHEMA_VERSION

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["warnings"] = list(self.warnings)
        return payload


def ensure_source_knowledge_dirs(root: Path | str = SOURCE_DOCUMENT_ROOT) -> Path:
    base = Path(root)
    for folder in KNOWLEDGE_DIRS:
        (base / folder).mkdir(parents=True, exist_ok=True)
    return base


def chunk_extracted_text(document_id: str, *, regenerate: bool = False, root: Path | str = SOURCE_DOCUMENT_ROOT) -> list[SourceChunk]:
    base = ensure_source_knowledge_dirs(root)
    record = load_source_document(document_id, root=base, missing_ok=True)
    if record is None or record.extraction_status != STATUS_EXTRACTED:
        return []
    existing = load_chunks(document_id=document_id, root=base)
    if existing and not regenerate:
        return existing
    text = get_extracted_text(document_id, root=base)
    if not text.strip():
        return []
    if regenerate:
        _delete_chunks(document_id, base)
    chunks = _split_text_into_chunks(text)
    records: list[SourceChunk] = []
    for number, chunk_text in enumerate(chunks, start=1):
        normalized = chunk_text.strip()
        if not normalized:
            continue
        page_start, page_end = _page_range(normalized)
        warnings = []
        if page_start is None:
            warnings.append("page_info_unavailable")
        if len(normalized) < 250:
            warnings.append("short_chunk")
        quality = _quality_score(normalized)
        if quality < 0.7:
            warnings.append("garbled_text_suspected")
        text_hash = _hash_text(normalized)
        chunk_id = f"chunk_{document_id}_{number:04d}"
        records.append(
            SourceChunk(
                chunk_id=chunk_id,
                document_id=document_id,
                source_document_id=document_id,
                chunk_number=number,
                page_start=page_start,
                page_end=page_end,
                section_title=None,
                text=normalized,
                text_hash=text_hash,
                char_count=len(normalized),
                quality_score=quality,
                created_at_utc=_now(),
                warnings=tuple(warnings),
            )
        )
    for chunk in records:
        _atomic_write_json(_chunk_path(base, chunk.chunk_id), chunk.to_json())
    _update_chunk_index(base)
    return records


def load_chunks(*, document_id: str | None = None, root: Path | str = SOURCE_DOCUMENT_ROOT) -> list[SourceChunk]:
    base = ensure_source_knowledge_dirs(root)
    chunks: list[SourceChunk] = []
    for path in sorted((base / "chunks").glob("*.json")):
        if path.name.startswith("."):
            continue
        try:
            chunk = _load_chunk_file(path)
        except Exception:
            continue
        if document_id is None or chunk.document_id == document_id:
            chunks.append(chunk)
    return chunks


def search_source_chunks(
    query: str,
    *,
    document_id: str | None = None,
    limit: int = 20,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> list[SourceSearchResult]:
    terms = [term.lower() for term in re.findall(r"\w+", query or "") if term]
    if not terms:
        return []
    results: list[SourceSearchResult] = []
    for chunk in load_chunks(document_id=document_id, root=root):
        text_lower = chunk.text.lower()
        score = float(sum(text_lower.count(term) for term in terms))
        if score <= 0:
            continue
        results.append(
            SourceSearchResult(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                snippet=_snippet(chunk.text, terms),
                score=score,
                warnings=chunk.warnings,
            )
        )
    results.sort(key=lambda item: (-item.score, item.document_id, item.chunk_id))
    return results[: max(0, int(limit or 0))]


def create_manual_proposal(
    document_id: str,
    chunk_id: str,
    claim: str,
    *,
    proposal_type: str = "manual_note",
    proposed_condition: str | None = None,
    proposed_effect: str | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> SourceProposal:
    base = ensure_source_knowledge_dirs(root)
    chunk = load_chunk(chunk_id, root=base)
    if chunk.document_id != document_id:
        raise ValueError("Proposal document_id must match chunk document_id.")
    if not claim.strip():
        raise ValueError("Proposal claim is required.")
    if proposal_type not in VALID_PROPOSAL_TYPES:
        raise ValueError(f"Unsupported proposal type: {proposal_type}")
    now = _now()
    proposal_id = "proposal_" + _hash_text("|".join([document_id, chunk_id, claim.strip(), proposal_type]))[7:23]
    proposal = SourceProposal(
        proposal_id=proposal_id,
        document_id=document_id,
        chunk_id=chunk_id,
        claim=claim.strip(),
        proposed_condition=proposed_condition,
        proposed_effect=proposed_effect,
        proposal_type=proposal_type,
        status="pending_review",
        created_by="manual",
        created_at_utc=now,
        updated_at_utc=now,
        warnings=("proposal_does_not_activate_rule",),
    )
    _atomic_write_json(_proposal_path(base, proposal_id), proposal.to_json())
    _update_proposal_index(base)
    return proposal


def list_source_proposals(
    *,
    document_id: str | None = None,
    status: str | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> list[SourceProposal]:
    base = ensure_source_knowledge_dirs(root)
    proposals = []
    for path in sorted((base / "proposals").glob("*.json")):
        try:
            proposal = _load_proposal_file(path)
        except Exception:
            continue
        if document_id is not None and proposal.document_id != document_id:
            continue
        if status is not None and proposal.status != status:
            continue
        proposals.append(proposal)
    return proposals


def update_proposal_status(proposal_id: str, status: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> SourceProposal:
    if status not in VALID_PROPOSAL_STATUSES:
        raise ValueError(f"Unsupported proposal status: {status}")
    base = ensure_source_knowledge_dirs(root)
    proposal = _load_proposal_file(_proposal_path(base, proposal_id))
    updated = SourceProposal(
        proposal_id=proposal.proposal_id,
        document_id=proposal.document_id,
        chunk_id=proposal.chunk_id,
        claim=proposal.claim,
        proposed_condition=proposal.proposed_condition,
        proposed_effect=proposal.proposed_effect,
        proposal_type=proposal.proposal_type,
        status=status,
        created_by=proposal.created_by,
        created_at_utc=proposal.created_at_utc,
        updated_at_utc=_now(),
        warnings=proposal.warnings,
    )
    _atomic_write_json(_proposal_path(base, proposal_id), updated.to_json())
    _update_proposal_index(base)
    return updated


def create_source_citation(
    document_id: str,
    chunk_id: str,
    note: str,
    *,
    quote_excerpt: str | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> SourceCitation:
    base = ensure_source_knowledge_dirs(root)
    chunk = load_chunk(chunk_id, root=base)
    if chunk.document_id != document_id:
        raise ValueError("Citation document_id must match chunk document_id.")
    if not note.strip():
        raise ValueError("Citation note is required.")
    excerpt = (quote_excerpt or chunk.text[:240]).strip()
    if len(excerpt) > 300:
        excerpt = excerpt[:297].rstrip() + "..."
    citation_id = "citation_" + _hash_text("|".join([document_id, chunk_id, note.strip(), excerpt]))[7:23]
    citation = SourceCitation(
        citation_id=citation_id,
        document_id=document_id,
        chunk_id=chunk_id,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        note=note.strip(),
        quote_excerpt=excerpt,
        created_at_utc=_now(),
        warnings=("citation_does_not_activate_rule",),
    )
    _atomic_write_json(_citation_path(base, citation_id), citation.to_json())
    _update_citation_index(base)
    return citation


def get_source_knowledge_health(root: Path | str = SOURCE_DOCUMENT_ROOT) -> SourceKnowledgeHealth:
    base = ensure_source_knowledge_dirs(root)
    warnings: list[str] = []
    documents = list_source_documents(root=base)
    chunks = load_chunks(root=base)
    proposals = list_source_proposals(root=base)
    citations = _load_citations(root=base)
    for index_name in ("chunk_index.json", "proposal_index.json", "citation_index.json"):
        if not (base / "indexes" / index_name).exists():
            warnings.append(f"missing_{index_name}")
    if documents and not any(doc.extraction_status == STATUS_EXTRACTED for doc in documents):
        warnings.append("no_extracted_documents")
    if documents and not chunks:
        warnings.append("no_chunks")
    if any(proposal.status == "pending_review" for proposal in proposals):
        warnings.append("pending_proposals")
    needs_ocr = sum(1 for doc in documents if doc.extraction_status == "needs_ocr_not_supported")
    invalid = sum(1 for doc in documents if doc.extraction_status in {"invalid_pdf", "read_error"})
    low_quality = sum(1 for chunk in chunks if chunk.quality_score < 0.7)
    if needs_ocr:
        warnings.append("needs_ocr_documents")
    if invalid:
        warnings.append("invalid_documents")
    if low_quality:
        warnings.append("low_quality_chunks")
    status = "critical" if invalid else "warning" if warnings else "healthy"
    return SourceKnowledgeHealth(
        status=status,
        documents=len(documents),
        registered_documents=sum(1 for doc in documents if doc.extraction_status == "registered"),
        extracted_documents=sum(1 for doc in documents if doc.extraction_status == STATUS_EXTRACTED),
        needs_ocr=needs_ocr,
        invalid_documents=invalid,
        chunks=len(chunks),
        low_quality_chunks=low_quality,
        proposals_total=len(proposals),
        proposals_pending=sum(1 for item in proposals if item.status == "pending_review"),
        proposals_approved=sum(1 for item in proposals if item.status == "approved"),
        proposals_rejected=sum(1 for item in proposals if item.status == "rejected"),
        citations=len(citations),
        warnings=tuple(warnings),
    )


def load_chunk(chunk_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> SourceChunk:
    return _load_chunk_file(_chunk_path(ensure_source_knowledge_dirs(root), chunk_id))


def _split_text_into_chunks(text: str, *, target_size: int = 1600, max_size: int = 2000) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if not paragraphs:
        paragraphs = [text.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > max_size:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(paragraph[index : index + target_size].strip() for index in range(0, len(paragraph), target_size))
            continue
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) > max_size and current:
            chunks.append(current.strip())
            current = paragraph
        else:
            current = candidate
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _page_range(text: str) -> tuple[int | None, int | None]:
    pages = [int(match) for match in re.findall(r"---\s*Page\s+(\d+)\s*---", text, flags=re.IGNORECASE)]
    if not pages:
        return None, None
    return min(pages), max(pages)


def _quality_score(text: str) -> float:
    if not text.strip():
        return 0.0
    replacement_ratio = text.count("\ufffd") / max(1, len(text))
    control_ratio = sum(1 for char in text if ord(char) < 32 and char not in "\n\r\t") / max(1, len(text))
    score = 1.0 - min(0.5, replacement_ratio * 5) - min(0.3, control_ratio * 5)
    if len(text.strip()) < 250:
        score -= 0.1
    return round(max(0.0, min(1.0, score)), 2)


def _snippet(text: str, terms: list[str]) -> str:
    lower = text.lower()
    positions = [lower.find(term) for term in terms if lower.find(term) >= 0]
    if not positions:
        return text[:180].strip()
    start = max(0, min(positions) - 70)
    end = min(len(text), min(positions) + 170)
    prefix = "..." if start else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end].strip()}{suffix}"


def _delete_chunks(document_id: str, root: Path) -> None:
    for path in (root / "chunks").glob(f"chunk_{document_id}_*.json"):
        if path.is_file():
            path.unlink()
    _update_chunk_index(root)


def _load_chunk_file(path: Path) -> SourceChunk:
    data = json.loads(path.read_text(encoding="utf-8"))
    return SourceChunk(
        chunk_id=str(data["chunk_id"]),
        document_id=str(data["document_id"]),
        source_document_id=str(data.get("source_document_id") or data["document_id"]),
        chunk_number=int(data["chunk_number"]),
        page_start=int(data["page_start"]) if data.get("page_start") is not None else None,
        page_end=int(data["page_end"]) if data.get("page_end") is not None else None,
        section_title=str(data["section_title"]) if data.get("section_title") else None,
        text=str(data["text"]),
        text_hash=str(data["text_hash"]),
        char_count=int(data.get("char_count", 0) or 0),
        quality_score=float(data.get("quality_score", 0.0) or 0.0),
        created_at_utc=str(data.get("created_at_utc") or _now()),
        warnings=tuple(str(item) for item in data.get("warnings", []) if item),
    )


def _load_proposal_file(path: Path) -> SourceProposal:
    data = json.loads(path.read_text(encoding="utf-8"))
    return SourceProposal(
        proposal_id=str(data["proposal_id"]),
        document_id=str(data["document_id"]),
        chunk_id=str(data["chunk_id"]),
        claim=str(data["claim"]),
        proposed_condition=str(data["proposed_condition"]) if data.get("proposed_condition") else None,
        proposed_effect=str(data["proposed_effect"]) if data.get("proposed_effect") else None,
        proposal_type=str(data.get("proposal_type") or "manual_note"),
        status=str(data.get("status") or "pending_review"),
        created_by=str(data.get("created_by") or "manual"),
        created_at_utc=str(data.get("created_at_utc") or _now()),
        updated_at_utc=str(data.get("updated_at_utc") or _now()),
        warnings=tuple(str(item) for item in data.get("warnings", []) if item),
    )


def _load_citation_file(path: Path) -> SourceCitation:
    data = json.loads(path.read_text(encoding="utf-8"))
    return SourceCitation(
        citation_id=str(data["citation_id"]),
        document_id=str(data["document_id"]),
        chunk_id=str(data["chunk_id"]),
        page_start=int(data["page_start"]) if data.get("page_start") is not None else None,
        page_end=int(data["page_end"]) if data.get("page_end") is not None else None,
        note=str(data["note"]),
        quote_excerpt=str(data.get("quote_excerpt") or ""),
        created_at_utc=str(data.get("created_at_utc") or _now()),
        warnings=tuple(str(item) for item in data.get("warnings", []) if item),
    )


def _load_citations(*, root: Path) -> list[SourceCitation]:
    citations = []
    for path in sorted((root / "citations").glob("*.json")):
        try:
            citations.append(_load_citation_file(path))
        except Exception:
            continue
    return citations


def _update_chunk_index(root: Path) -> None:
    entries = [
        {
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "path": str(_chunk_path(root, chunk.chunk_id)),
            "chunk_number": chunk.chunk_number,
            "text_hash": chunk.text_hash,
            "char_count": chunk.char_count,
            "quality_score": chunk.quality_score,
            "created_at_utc": chunk.created_at_utc,
        }
        for chunk in load_chunks(root=root)
    ]
    _atomic_write_json(root / "indexes" / "chunk_index.json", {"entries": entries})


def _update_proposal_index(root: Path) -> None:
    entries = [
        {
            "proposal_id": proposal.proposal_id,
            "document_id": proposal.document_id,
            "chunk_id": proposal.chunk_id,
            "proposal_type": proposal.proposal_type,
            "status": proposal.status,
            "updated_at_utc": proposal.updated_at_utc,
        }
        for proposal in list_source_proposals(root=root)
    ]
    _atomic_write_json(root / "indexes" / "proposal_index.json", {"entries": entries})


def _update_citation_index(root: Path) -> None:
    entries = [
        {
            "citation_id": citation.citation_id,
            "document_id": citation.document_id,
            "chunk_id": citation.chunk_id,
            "page_start": citation.page_start,
            "page_end": citation.page_end,
            "created_at_utc": citation.created_at_utc,
        }
        for citation in _load_citations(root=root)
    ]
    _atomic_write_json(root / "indexes" / "citation_index.json", {"entries": entries})


def _chunk_path(root: Path, chunk_id: str) -> Path:
    return ensure_source_knowledge_dirs(root) / "chunks" / f"{_safe_id(chunk_id)}.json"


def _proposal_path(root: Path, proposal_id: str) -> Path:
    return ensure_source_knowledge_dirs(root) / "proposals" / f"{_safe_id(proposal_id)}.json"


def _citation_path(root: Path, citation_id: str) -> Path:
    return ensure_source_knowledge_dirs(root) / "citations" / f"{_safe_id(citation_id)}.json"


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
