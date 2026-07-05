"""Deterministic document structure analysis for controlled source documents."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping

from .source_documents import SOURCE_DOCUMENT_ROOT, STATUS_EXTRACTED, get_extracted_text, load_source_document
from .source_knowledge import ensure_source_knowledge_dirs, load_chunks

SCHEMA_VERSION = "document_structure_v1"
CLEANED_TEXT_SCHEMA_VERSION = "document_cleaned_text_v1"
RECHUNK_SCHEMA_VERSION = "document_rechunk_plan_v1"
STRUCTURE_DIRS = ("structure_maps", "cleaned_text", "rechunk_plans", "indexes")


def ensure_document_structure_dirs(root: Path | str = SOURCE_DOCUMENT_ROOT) -> Path:
    base = ensure_source_knowledge_dirs(root)
    for folder in STRUCTURE_DIRS:
        (base / folder).mkdir(parents=True, exist_ok=True)
    return base


def normalize_extracted_page_text(document_id: str, *, regenerate: bool = False, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_document_structure_dirs(root)
    path = _cleaned_text_path(base, document_id)
    if path.exists() and not regenerate:
        return json.loads(path.read_text(encoding="utf-8"))
    pages, warnings = _page_text_map(document_id, root=base)
    if not pages:
        payload = {"document_id": document_id, "cleaned_text_id": f"cleaned_{document_id}", "schema_version": CLEANED_TEXT_SCHEMA_VERSION, "pages_cleaned": 0, "pages": [], "cleanup_actions": [], "warnings": warnings or ["no_page_text"]}
        _atomic_write_json(path, payload)
        _update_cleaned_text_index(base)
        return payload
    cleaned_pages = []
    actions = {"collapsed_whitespace", "normalized_line_breaks", "repaired_hyphenated_line_breaks"}
    for number, text in sorted(pages.items()):
        cleaned = _clean_page_text(text)
        cleaned_pages.append({"page_number": number, "text": cleaned, "char_count": len(cleaned)})
    payload = {
        "document_id": document_id,
        "cleaned_text_id": f"cleaned_{document_id}",
        "schema_version": CLEANED_TEXT_SCHEMA_VERSION,
        "created_at_utc": _now(),
        "pages_cleaned": len(cleaned_pages),
        "pages": cleaned_pages,
        "cleanup_actions": sorted(actions),
        "warnings": warnings,
    }
    _atomic_write_json(path, payload)
    _update_cleaned_text_index(base)
    return payload


def detect_repeated_headers_footers(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    pages, warnings = _cleaned_or_raw_pages(document_id, root=ensure_document_structure_dirs(root))
    if not pages:
        return {"header_candidates": [], "footer_candidates": [], "warnings": warnings or ["no_page_text"]}
    first_lines: dict[str, set[int]] = {}
    last_lines: dict[str, set[int]] = {}
    for number, text in pages.items():
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            continue
        for line in lines[:2]:
            key = _normalize_repeated_line(line)
            if key:
                first_lines.setdefault(key, set()).add(number)
        for line in lines[-2:]:
            key = _normalize_repeated_line(line)
            if key:
                last_lines.setdefault(key, set()).add(number)
    total = max(1, len(pages))
    return {
        "header_candidates": _repeated_candidates(first_lines, total),
        "footer_candidates": _repeated_candidates(last_lines, total),
        "warnings": warnings,
    }


def detect_document_headings(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    pages, warnings = _cleaned_or_raw_pages(document_id, root=ensure_document_structure_dirs(root))
    headings = []
    for page_number, text in sorted(pages.items()):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for index, line in enumerate(lines):
            reason = _heading_reason(line)
            if not reason:
                continue
            confidence = "high" if reason in {"numbered_heading", "chapter_section_label", "appendix_or_references"} else "medium"
            headings.append({"title": line[:160], "level": _heading_level(line), "page_number": page_number, "confidence": confidence, "reason": reason, "source": "heuristic_heading_detection"})
    if not headings:
        warnings.append("no_headings_detected")
    return {"headings": headings, "warnings": warnings}


def detect_toc_candidates(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    pages, warnings = _cleaned_or_raw_pages(document_id, root=ensure_document_structure_dirs(root))
    entries = []
    toc_pages = []
    for page_number, text in sorted(pages.items()):
        if re.search(r"table\s+of\s+contents|contents", text, flags=re.IGNORECASE):
            toc_pages.append(page_number)
        for line in text.splitlines():
            match = re.match(r"^(.{4,90}?)(?:\.{2,}|\s{2,})(\d{1,4})$", line.strip())
            if match:
                entries.append({"title": match.group(1).strip(), "page_number": int(match.group(2)), "confidence": "medium", "source": "toc_candidate"})
    return {"toc_found": bool(toc_pages or entries), "toc_pages": toc_pages, "entries": entries[:100], "warnings": warnings}


def detect_possible_tables(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    pages, warnings = _cleaned_or_raw_pages(document_id, root=ensure_document_structure_dirs(root))
    tables = []
    for page_number, text in sorted(pages.items()):
        lines = [line for line in text.splitlines() if line.strip()]
        delimiter_lines = sum(1 for line in lines if "|" in line or "\t" in line or re.search(r"\S\s{3,}\S", line))
        numeric_rows = sum(1 for line in lines if len(re.findall(r"\d+(?:\.\d+)?%?|[$]\d+", line)) >= 2)
        if delimiter_lines >= 3 or numeric_rows >= 4:
            tables.append({"page_number": page_number, "kind": "possible_table", "confidence": "medium" if delimiter_lines + numeric_rows >= 6 else "low", "reason": "delimiter_or_numeric_row_density"})
    return {"tables": tables, "warnings": warnings}


def detect_possible_figures(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    pages, warnings = _cleaned_or_raw_pages(document_id, root=ensure_document_structure_dirs(root))
    figures = []
    for page_number, text in sorted(pages.items()):
        captions = re.findall(r"\b(?:figure|fig\.|diagram|chart|image)\s+\d+[:.\-]?[^\n]{0,120}", text, flags=re.IGNORECASE)
        if captions:
            figures.append({"page_number": page_number, "kind": "possible_figure", "confidence": "medium", "reason": "caption_keyword", "caption_preview": captions[0][:140]})
    return {"figures": figures, "warnings": warnings}


def detect_footnotes_and_references(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    pages, warnings = _cleaned_or_raw_pages(document_id, root=ensure_document_structure_dirs(root))
    footnotes = []
    references = {"found": False, "pages": [], "url_heavy_pages": []}
    for page_number, text in sorted(pages.items()):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        short_numbered = [line for line in lines[-12:] if re.match(r"^(\d{1,3}|[*†])\s+.{8,160}$", line)]
        if len(short_numbered) >= 2:
            footnotes.append({"page_number": page_number, "kind": "possible_footnotes", "confidence": "medium", "reason": "numbered_notes_near_page_bottom"})
        if re.search(r"\b(references|bibliography|works cited)\b", text, flags=re.IGNORECASE):
            references["found"] = True
            references["pages"].append(page_number)
        if len(re.findall(r"https?://|www\.", text, flags=re.IGNORECASE)) >= 3:
            references["url_heavy_pages"].append(page_number)
    return {"footnotes": footnotes, "references": references, "warnings": warnings}


def build_document_structure_map(document_id: str, *, regenerate: bool = False, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_document_structure_dirs(root)
    path = _structure_path(base, document_id)
    if path.exists() and not regenerate:
        return json.loads(path.read_text(encoding="utf-8"))
    record = load_source_document(document_id, root=base, missing_ok=True)
    if record is None or record.extraction_status != STATUS_EXTRACTED:
        payload = _empty_structure(document_id, ["not_extracted"], ["extract text first"])
        _atomic_write_json(path, payload)
        _update_structure_index(base)
        return payload
    normalize_extracted_page_text(document_id, root=base)
    header_footer = detect_repeated_headers_footers(document_id, root=base)
    heading_result = detect_document_headings(document_id, root=base)
    toc = detect_toc_candidates(document_id, root=base)
    tables = detect_possible_tables(document_id, root=base)
    figures = detect_possible_figures(document_id, root=base)
    refs = detect_footnotes_and_references(document_id, root=base)
    sections = _sections_from_headings(heading_result["headings"], record.page_count)
    chunk_quality = analyze_chunk_quality(document_id, root=base)
    payload = {
        "document_id": document_id,
        "structure_id": f"structure_{document_id}",
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": _now(),
        "source": "controlled_extracted_text",
        "page_count": record.page_count,
        "sections": sections,
        "headings": heading_result["headings"],
        "toc_candidates": toc,
        "page_layout": {"page_count": record.page_count, "confidence": "heuristic"},
        "tables": tables["tables"],
        "figures": figures["figures"],
        "footnotes": refs["footnotes"],
        "references": refs["references"],
        "header_footer": header_footer,
        "chunk_quality": chunk_quality,
        "warnings": list(dict.fromkeys([*heading_result.get("warnings", []), *toc.get("warnings", []), *tables.get("warnings", []), *figures.get("warnings", []), *refs.get("warnings", [])])),
        "blockers": [],
    }
    _atomic_write_json(path, payload)
    _update_structure_index(base)
    recommend_rechunk_plan(document_id, root=base)
    return payload


def load_document_structure_map(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    path = _structure_path(ensure_document_structure_dirs(root), document_id)
    if not path.exists():
        return {"document_id": document_id, "status": "not_built", "warnings": ["structure_map_not_built"]}
    return json.loads(path.read_text(encoding="utf-8"))


def get_document_structure_summary(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    data = load_document_structure_map(document_id, root=root)
    if data.get("status") == "not_built":
        return {"document_id": document_id, "status": "not_built", "headings": 0, "sections": 0, "tables": 0, "figures": 0, "references_found": False, "chunk_quality_status": "unknown", "rechunk_strategy": "unknown", "warnings": data.get("warnings", [])}
    plan = recommend_rechunk_plan(document_id, root=root)
    header_footer = data.get("header_footer") if isinstance(data.get("header_footer"), Mapping) else {}
    noise = bool(header_footer.get("header_candidates") or header_footer.get("footer_candidates"))
    return {
        "document_id": document_id,
        "status": "built",
        "page_count": data.get("page_count"),
        "headings": len(data.get("headings", [])),
        "sections": len(data.get("sections", [])),
        "toc_found": bool((data.get("toc_candidates") or {}).get("toc_found")) if isinstance(data.get("toc_candidates"), Mapping) else False,
        "tables": len(data.get("tables", [])),
        "figures": len(data.get("figures", [])),
        "footnotes": len(data.get("footnotes", [])),
        "references_found": bool((data.get("references") or {}).get("found")) if isinstance(data.get("references"), Mapping) else False,
        "header_footer_noise": noise,
        "chunk_quality_status": (data.get("chunk_quality") or {}).get("quality_status") if isinstance(data.get("chunk_quality"), Mapping) else "unknown",
        "rechunk_strategy": plan.get("strategy"),
        "warnings": data.get("warnings", []),
    }


def analyze_chunk_quality(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_document_structure_dirs(root)
    chunks = load_chunks(document_id=document_id, root=base)
    if not chunks:
        return {"document_id": document_id, "chunk_count": 0, "quality_status": "not_chunked", "warnings": ["not_chunked"]}
    header_footer = detect_repeated_headers_footers(document_id, root=base)
    noise_terms = [item.get("text_preview", "") for item in header_footer.get("header_candidates", []) + header_footer.get("footer_candidates", []) if isinstance(item, Mapping)]
    very_short = [chunk.chunk_id for chunk in chunks if chunk.char_count < 250]
    very_long = [chunk.chunk_id for chunk in chunks if chunk.char_count > 2600]
    no_pages = [chunk.chunk_id for chunk in chunks if chunk.page_start is None]
    low_quality = [chunk.chunk_id for chunk in chunks if chunk.quality_score < 0.7 or chunk.warnings]
    header_noise = [chunk.chunk_id for chunk in chunks if any(term and term in chunk.text for term in noise_terms)]
    duplicate_hashes = len(chunks) - len({chunk.text_hash for chunk in chunks})
    warnings = []
    if very_short:
        warnings.append("very_short_chunks")
    if very_long:
        warnings.append("very_long_chunks")
    if no_pages:
        warnings.append("chunks_without_page_reference")
    if header_noise:
        warnings.append("header_footer_noise_detected")
    if duplicate_hashes:
        warnings.append("duplicate_chunks_detected")
    status = "healthy" if not warnings else "warning"
    if len(low_quality) > max(3, len(chunks) // 3):
        status = "critical"
        warnings.append("many_low_quality_chunks")
    return {
        "document_id": document_id,
        "chunk_count": len(chunks),
        "quality_status": status,
        "very_short_chunks": len(very_short),
        "very_long_chunks": len(very_long),
        "chunks_crossing_sections": 0,
        "chunks_with_header_footer_noise": len(header_noise),
        "chunks_without_page_reference": len(no_pages),
        "low_quality_chunks": len(low_quality),
        "duplicate_chunks": duplicate_hashes,
        "warnings": list(dict.fromkeys(warnings)),
    }


def recommend_rechunk_plan(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_document_structure_dirs(root)
    path = _rechunk_path(base, document_id)
    quality = analyze_chunk_quality(document_id, root=base)
    warnings = list(quality.get("warnings", []))
    actions = []
    if quality.get("quality_status") == "not_chunked":
        strategy = "manual_review_required"
        recommended = False
        reason = "document_not_chunked"
        actions.append("chunk_extracted_text_first")
    elif quality.get("chunks_with_header_footer_noise", 0):
        strategy = "section_aware_chunking"
        recommended = True
        reason = "header_footer_noise_detected"
        actions.extend(["remove_header_footer_noise_from_chunk_input", "prefer_section_boundaries", "preserve_page_references"])
    elif quality.get("very_long_chunks", 0):
        strategy = "paragraph_aware_chunking"
        recommended = True
        reason = "very_long_chunks"
        actions.extend(["split_long_chunks_at_paragraphs", "preserve_page_references"])
    elif quality.get("chunks_without_page_reference", 0):
        strategy = "page_aware_chunking"
        recommended = True
        reason = "missing_page_references"
        actions.append("preserve_page_references")
    elif quality.get("quality_status") == "critical":
        strategy = "manual_review_required"
        recommended = True
        reason = "low_chunk_quality"
        actions.append("review_extraction_before_rechunk")
    else:
        strategy = "keep_existing"
        recommended = False
        reason = "chunk_quality_acceptable"
    payload = {"document_id": document_id, "schema_version": RECHUNK_SCHEMA_VERSION, "created_at_utc": _now(), "recommended": recommended, "reason": reason, "strategy": strategy, "actions": list(dict.fromkeys(actions)), "warnings": warnings}
    _atomic_write_json(path, payload)
    _update_rechunk_index(base)
    return payload


def _clean_page_text(text: str) -> str:
    value = str(text).replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"(\w)-\n(\w)", r"\1\2", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    value = re.sub(r"(?m)^\s+", "", value)
    return value.strip()


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


def _cleaned_or_raw_pages(document_id: str, *, root: Path) -> tuple[dict[int, str], list[str]]:
    cleaned_path = _cleaned_text_path(root, document_id)
    if cleaned_path.exists():
        try:
            data = json.loads(cleaned_path.read_text(encoding="utf-8"))
            pages = {int(item["page_number"]): str(item.get("text") or "") for item in data.get("pages", []) if isinstance(item, Mapping)}
            if pages:
                return pages, list(data.get("warnings", []))
        except Exception:
            pass
    return _page_text_map(document_id, root=root)


def _heading_reason(line: str) -> str | None:
    stripped = line.strip()
    if len(stripped) < 4 or len(stripped) > 120 or stripped.endswith(".") and len(stripped.split()) > 9:
        return None
    if re.match(r"^(chapter|section|article)\s+\w+", stripped, flags=re.IGNORECASE):
        return "chapter_section_label"
    if re.match(r"^(appendix|references|bibliography|works cited)\b", stripped, flags=re.IGNORECASE):
        return "appendix_or_references"
    if re.match(r"^\d+(?:\.\d+){0,3}\s+\S", stripped):
        return "numbered_heading"
    words = stripped.split()
    if 1 <= len(words) <= 8 and stripped.upper() == stripped and re.search(r"[A-Z]", stripped):
        return "all_caps_short_line"
    if 1 <= len(words) <= 9 and sum(1 for word in words if word[:1].isupper()) >= max(1, len(words) - 1):
        return "title_case_short_line"
    return None


def _heading_level(line: str) -> int:
    match = re.match(r"^(\d+(?:\.\d+){0,3})\s+", line.strip())
    if match:
        return min(4, match.group(1).count(".") + 1)
    if re.match(r"^(chapter|appendix|references|bibliography|works cited)", line.strip(), flags=re.IGNORECASE):
        return 1
    return 2


def _sections_from_headings(headings: list[dict[str, object]], page_count: int | None) -> list[dict[str, object]]:
    sections = []
    for index, heading in enumerate(headings):
        start = int(heading.get("page_number") or 1)
        next_start = int(headings[index + 1].get("page_number") or start) if index + 1 < len(headings) else page_count or start
        sections.append({"section_id": f"sec_{index + 1:03d}", "title": heading.get("title"), "level": heading.get("level", 1), "page_start": start, "page_end": max(start, next_start), "confidence": heading.get("confidence", "low"), "source": "heading_detection"})
    return sections


def _normalize_repeated_line(line: str) -> str:
    value = re.sub(r"\b\d+\b", "#", line.strip())
    value = re.sub(r"\s+", " ", value)
    if len(value) < 4 or len(value) > 100:
        return ""
    return value


def _repeated_candidates(lines: dict[str, set[int]], total_pages: int) -> list[dict[str, object]]:
    candidates = []
    threshold = max(2, int(total_pages * 0.4))
    for text, pages in sorted(lines.items(), key=lambda item: (-len(item[1]), item[0])):
        if len(pages) >= threshold:
            confidence = "high" if len(pages) >= max(2, int(total_pages * 0.7)) else "medium"
            candidates.append({"text_preview": text[:100], "pages_seen": len(pages), "confidence": confidence})
    return candidates[:10]


def _empty_structure(document_id: str, warnings: list[str], blockers: list[str]) -> dict[str, object]:
    return {"document_id": document_id, "structure_id": f"structure_{document_id}", "schema_version": SCHEMA_VERSION, "created_at_utc": _now(), "source": "controlled_extracted_text", "page_count": None, "sections": [], "headings": [], "toc_candidates": {"toc_found": False, "entries": []}, "page_layout": {}, "tables": [], "figures": [], "footnotes": [], "references": {"found": False}, "header_footer": {}, "chunk_quality": {}, "warnings": warnings, "blockers": blockers, "recommended_action": "Extract text first."}


def _structure_path(root: Path, document_id: str) -> Path:
    return root / "structure_maps" / f"{_safe_id(document_id)}_structure.json"


def _cleaned_text_path(root: Path, document_id: str) -> Path:
    return root / "cleaned_text" / f"{_safe_id(document_id)}_cleaned.json"


def _rechunk_path(root: Path, document_id: str) -> Path:
    return root / "rechunk_plans" / f"{_safe_id(document_id)}_rechunk.json"


def _update_structure_index(root: Path) -> None:
    entries = []
    for path in sorted((root / "structure_maps").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        entries.append({"document_id": data.get("document_id"), "path": str(path), "headings": len(data.get("headings", [])), "sections": len(data.get("sections", [])), "schema_version": data.get("schema_version")})
    _atomic_write_json(root / "indexes" / "structure_map_index.json", {"entries": entries})


def _update_cleaned_text_index(root: Path) -> None:
    entries = []
    for path in sorted((root / "cleaned_text").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        entries.append({"document_id": data.get("document_id"), "path": str(path), "pages_cleaned": data.get("pages_cleaned"), "schema_version": data.get("schema_version")})
    _atomic_write_json(root / "indexes" / "cleaned_text_index.json", {"entries": entries})


def _update_rechunk_index(root: Path) -> None:
    entries = []
    for path in sorted((root / "rechunk_plans").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        entries.append({"document_id": data.get("document_id"), "path": str(path), "recommended": data.get("recommended"), "strategy": data.get("strategy"), "schema_version": data.get("schema_version")})
    _atomic_write_json(root / "indexes" / "rechunk_plan_index.json", {"entries": entries})


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
