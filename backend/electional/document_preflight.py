"""Preflight quality gate for controlled PDF source documents."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Iterable, Mapping

from .source_documents import SOURCE_DOCUMENT_ROOT, load_source_document


SCHEMA_VERSION = "document_preflight_v1"
PREFLIGHT_DIRS = ("preflight", "indexes")
KEYWORDS = (
    "reject",
    "block",
    "allow",
    "must",
    "should",
    "required",
    "warning",
    "exception",
    "unless",
    "threshold",
    "confidence",
    "score",
    "override",
    "manual review",
    "source",
    "citation",
    "audit",
    "replay",
    "drift",
    "Fast Lane",
    "hard gate",
    "review queue",
    "proposal",
    "rule pack",
    "objective pack",
    "watchlist",
    "source-backed rule",
    "chunk",
    "preflight",
    "privacy",
    "public export",
    "private export",
)


@dataclass(frozen=True)
class DocumentPreflightReport:
    document_id: str
    preflight_id: str
    status: str
    verdict: str
    created_at_utc: str
    file_safety: dict[str, object]
    format_detection: dict[str, object]
    page_structure: dict[str, object]
    font_encoding: dict[str, object]
    metadata: dict[str, object]
    title_detection: dict[str, object]
    keyword_scan: dict[str, object]
    quality_scores: dict[str, object]
    privacy_scan: dict[str, object]
    warnings: tuple[str, ...]
    blockers: tuple[str, ...]
    recommended_action: str
    schema_version: str = SCHEMA_VERSION

    def to_json(self, *, public_safe: bool = False) -> dict[str, object]:
        payload = asdict(self)
        payload["warnings"] = list(self.warnings)
        payload["blockers"] = list(self.blockers)
        if public_safe:
            payload["file_safety"] = _public_file_safety(payload["file_safety"])
            payload["privacy_scan"] = _public_privacy(payload["privacy_scan"])
        return payload


def ensure_preflight_storage(root: Path | str = SOURCE_DOCUMENT_ROOT) -> Path:
    base = Path(root)
    for folder in PREFLIGHT_DIRS:
        (base / folder).mkdir(parents=True, exist_ok=True)
    return base


def run_document_preflight(
    document_id: str,
    *,
    regenerate: bool = False,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
    reader_factory: Callable[[Path], object] | None = None,
) -> DocumentPreflightReport:
    base = ensure_preflight_storage(root)
    existing = load_document_preflight(document_id, root=base, missing_ok=True)
    if existing is not None and not regenerate:
        return existing

    warnings: list[str] = []
    blockers: list[str] = []
    pages_text: list[str] = []
    page_count: int | None = None
    metadata_payload: dict[str, object] = {}
    source_path: Path | None = None

    record = load_source_document(document_id, root=base, missing_ok=True)
    if record is None:
        blockers.append("document_missing")
        file_safety = {"exists": False, "readable": False, "file_type": "unknown", "sha256": None, "size_bytes": 0}
    else:
        source_path = Path(record.stored_pdf_path or record.source_path)
        file_safety = _file_safety(source_path)
        warnings.extend(file_safety.get("warnings", []))
        blockers.extend(file_safety.get("blockers", []))

    reader = None
    if source_path is not None and not blockers:
        try:
            reader = (reader_factory or _default_reader_factory)(source_path)
            if bool(getattr(reader, "is_encrypted", False)):
                blockers.append("encrypted_pdf")
            else:
                raw_pages = list(getattr(reader, "pages", []))
                page_count = len(raw_pages)
                pages_text = [_extract_page_text(page) for page in raw_pages]
                metadata_payload = _metadata_payload(getattr(reader, "metadata", None))
        except ImportError:
            warnings.append("extractor_unavailable")
        except Exception as exc:
            blockers.append("corrupt_pdf")
            warnings.append(f"pdf_read_error:{exc}")

    format_detection = _format_detection(pages_text, page_count)
    page_structure = _page_structure(pages_text, page_count)
    font_encoding = _font_encoding(pages_text)
    metadata_scan = _metadata_scan(metadata_payload)
    title_detection = _title_detection(metadata_payload, pages_text, record.original_filename if record else document_id)
    keyword_scan = _keyword_scan(pages_text)
    privacy_scan = _privacy_scan(pages_text)
    quality_scores = _quality_scores(format_detection, page_structure, font_encoding, title_detection)

    warnings.extend(format_detection.get("warnings", []))
    warnings.extend(page_structure.get("warnings", []))
    warnings.extend(font_encoding.get("warnings", []))
    warnings.extend(metadata_scan.get("warnings", []))
    warnings.extend(title_detection.get("warnings", []))
    warnings.extend(privacy_scan.get("warnings", []))

    extraction_score = int(quality_scores["extraction_quality"]["score"])
    if extraction_score < 25 and "extractor_unavailable" not in warnings:
        blockers.append("extraction_quality_too_low")
    verdict = _verdict(blockers, warnings, extraction_score, int(quality_scores["chunk_readiness"]["score"]))
    status = {"PASS": "preflight_passed", "WARNING": "preflight_warning", "BLOCK": "preflight_blocked", "UNKNOWN": "preflight_pending"}[verdict]
    report = DocumentPreflightReport(
        document_id=document_id,
        preflight_id=f"preflight_{document_id}",
        status=status,
        verdict=verdict,
        created_at_utc=_now(),
        file_safety=file_safety,
        format_detection=format_detection,
        page_structure=page_structure,
        font_encoding=font_encoding,
        metadata=metadata_scan,
        title_detection=title_detection,
        keyword_scan=keyword_scan,
        quality_scores=quality_scores,
        privacy_scan=privacy_scan,
        warnings=tuple(dict.fromkeys(str(item) for item in warnings if item)),
        blockers=tuple(dict.fromkeys(str(item) for item in blockers if item)),
        recommended_action=_recommended_action(verdict),
    )
    _atomic_write_json(_preflight_path(base, document_id), report.to_json())
    _update_preflight_index(base)
    return report


def load_document_preflight(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT, missing_ok: bool = False) -> DocumentPreflightReport | None:
    path = _preflight_path(ensure_preflight_storage(root), document_id)
    if not path.exists():
        if missing_ok:
            return None
        raise FileNotFoundError(str(path))
    return _report_from_json(json.loads(path.read_text(encoding="utf-8")))


def list_document_preflights(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> list[DocumentPreflightReport]:
    base = ensure_preflight_storage(root)
    reports: list[DocumentPreflightReport] = []
    for path in sorted((base / "preflight").glob("*_preflight.json")):
        try:
            reports.append(_report_from_json(json.loads(path.read_text(encoding="utf-8"))))
        except Exception:
            continue
    return reports


def get_document_preflight_summary(document_id: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    if document_id:
        report = load_document_preflight(document_id, root=root, missing_ok=True)
        if report is None:
            return {
                "document_id": document_id,
                "has_preflight": False,
                "verdict": "NOT_RUN",
                "status": "preflight_pending",
                "format": "Unknown",
                "ocr_needed": None,
                "page_count": None,
                "text_pages": None,
                "empty_pages": None,
                "extraction_quality_score": None,
                "extraction_quality_band": "Unknown",
                "chunk_readiness_score": None,
                "chunk_readiness_band": "Unknown",
                "citation_readiness_score": None,
                "citation_readiness_band": "Unknown",
                "privacy_status": "Unknown",
                "public_export_safe": None,
                "warning_count": 0,
                "blocker_count": 0,
                "top_warnings": [],
                "top_blockers": [],
                "keyword_matches": [],
                "privacy_findings": [],
                "recommended_action": "Run preflight before extraction.",
            }
        return _summary_from_report(report)

    reports = list_document_preflights(root=root)
    return {
        "total": len(reports),
        "pass": sum(1 for report in reports if report.verdict == "PASS"),
        "warning": sum(1 for report in reports if report.verdict == "WARNING"),
        "block": sum(1 for report in reports if report.verdict == "BLOCK"),
        "unknown": sum(1 for report in reports if report.verdict == "UNKNOWN"),
    }


def can_extract_after_preflight(document_id: str, *, override: bool = False, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    report = load_document_preflight(document_id, root=root, missing_ok=True)
    if report is None:
        return {
            "allowed": True,
            "requires_override": False,
            "verdict": "NOT_RUN",
            "reason": "Preflight has not been run; extraction is allowed for backward compatibility only.",
            "warnings": ["preflight_not_run"],
            "blockers": [],
        }
    warnings = list(report.warnings)
    blockers = list(report.blockers)
    if report.verdict == "PASS":
        return {"allowed": True, "requires_override": False, "verdict": "PASS", "reason": "Extraction allowed.", "warnings": warnings, "blockers": blockers}
    if report.verdict == "WARNING":
        return {
            "allowed": True,
            "requires_override": False,
            "verdict": "WARNING",
            "reason": "Extraction allowed with caution.",
            "warnings": warnings,
            "blockers": blockers,
        }
    if report.verdict == "BLOCK":
        return {
            "allowed": bool(override),
            "requires_override": True,
            "verdict": "BLOCK",
            "reason": "Preflight blocked extraction." if not override else "Preflight block explicitly overridden.",
            "warnings": warnings,
            "blockers": blockers,
        }
    return {
        "allowed": bool(override),
        "requires_override": True,
        "verdict": report.verdict or "UNKNOWN",
        "reason": "Preflight is uncertain; extraction requires explicit override.",
        "warnings": warnings or ["preflight_unknown"],
        "blockers": blockers,
    }


def format_preflight_report_text(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> str:
    summary = get_document_preflight_summary(document_id, root=root)
    if not summary.get("has_preflight"):
        return "\n".join(
            [
                "Document Preflight Report",
                "",
                "Verdict: NOT RUN",
                "Status: preflight_pending",
                "",
                "Recommended Action:",
                str(summary["recommended_action"]),
            ]
        )
    keyword_lines = [f"- {item['term']}: {item['count']}" for item in summary.get("keyword_matches", []) if isinstance(item, dict)]
    warning_lines = [f"- {item}" for item in summary.get("top_warnings", [])]
    blocker_lines = [f"- {item}" for item in summary.get("top_blockers", [])]
    privacy_findings = summary.get("privacy_findings") or []
    privacy_text = ", ".join(str(item).replace("_", " ") for item in privacy_findings) if privacy_findings else "None"
    return "\n".join(
        [
            "Document Preflight Report",
            "",
            f"Verdict: {summary.get('verdict', 'Unknown')}",
            f"Status: {summary.get('status', 'Unknown')}",
            f"Format: {summary.get('format', 'Unknown')}",
            f"OCR Needed: {_yes_no_unknown(summary.get('ocr_needed'))}",
            "",
            "Pages:",
            f"- Total: {_unknown(summary.get('page_count'))}",
            f"- Text pages: {_unknown(summary.get('text_pages'))}",
            f"- Empty pages: {_unknown(summary.get('empty_pages'))}",
            f"- Low-density pages: {_unknown(summary.get('low_text_density_pages'))}",
            f"- Scanned-like pages: {_unknown(summary.get('scanned_like_pages'))}",
            f"- Image-heavy pages: {_unknown(summary.get('image_heavy_pages'))}",
            "",
            "Quality:",
            f"- Extraction: {_score_line(summary.get('extraction_quality_score'), summary.get('extraction_quality_band'))}",
            f"- Chunk readiness: {_score_line(summary.get('chunk_readiness_score'), summary.get('chunk_readiness_band'))}",
            f"- Citation readiness: {_score_line(summary.get('citation_readiness_score'), summary.get('citation_readiness_band'))}",
            "",
            "Warnings:",
            *(warning_lines or ["- None"]),
            "",
            "Blockers:",
            *(blocker_lines or ["- None"]),
            "",
            "Top Keywords:",
            *(keyword_lines or ["- None"]),
            "",
            "Privacy:",
            f"- Status: {summary.get('privacy_status', 'Unknown')}",
            f"- Public export safe: {_yes_no_unknown(summary.get('public_export_safe'))}",
            f"- Findings: {privacy_text}",
            "",
            "Recommended Action:",
            str(summary.get("recommended_action") or "Unknown"),
        ]
    )


def _summary_from_report(report: DocumentPreflightReport) -> dict[str, object]:
    quality = report.quality_scores or {}
    extraction = dict(quality.get("extraction_quality") or {})
    chunk = dict(quality.get("chunk_readiness") or {})
    citation = dict(quality.get("citation_readiness") or {})
    page = report.page_structure or {}
    fmt = report.format_detection or {}
    privacy = report.privacy_scan or {}
    keywords = report.keyword_scan or {}
    keyword_matches = [dict(item) for item in keywords.get("matches", [])[:5] if isinstance(item, Mapping)]
    findings = [str(item) for item in privacy.get("findings", []) if item]
    warnings = list(report.warnings)
    blockers = list(report.blockers)
    return {
        "document_id": report.document_id,
        "has_preflight": True,
        "verdict": report.verdict,
        "status": report.status,
        "format": fmt.get("source_format") or "Unknown",
        "ocr_needed": fmt.get("ocr_needed"),
        "page_count": page.get("page_count"),
        "text_pages": page.get("text_pages", fmt.get("text_pages")),
        "empty_pages": page.get("blank_or_empty_pages", fmt.get("empty_text_pages")),
        "low_text_density_pages": page.get("low_text_density_pages"),
        "scanned_like_pages": "Unavailable",
        "image_heavy_pages": "Unavailable",
        "extraction_quality_score": extraction.get("score"),
        "extraction_quality_band": extraction.get("band") or "Unknown",
        "chunk_readiness_score": chunk.get("score"),
        "chunk_readiness_band": chunk.get("band") or "Unknown",
        "citation_readiness_score": citation.get("score"),
        "citation_readiness_band": citation.get("band") or "Unknown",
        "privacy_status": "warning" if findings else "safe",
        "public_export_safe": privacy.get("public_export_safe"),
        "privacy_findings": findings,
        "warning_count": len(warnings),
        "blocker_count": len(blockers),
        "top_warnings": warnings[:5],
        "top_blockers": blockers[:5],
        "keyword_matches": keyword_matches,
        "recommended_action": report.recommended_action,
    }


def _unknown(value: object) -> str:
    return "Unknown" if value is None else str(value)


def _yes_no_unknown(value: object) -> str:
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    return "Unknown"


def _score_line(score: object, band: object) -> str:
    if score is None:
        return "Unknown"
    return f"{score}/100 - {band or 'Unknown'}"

def _file_safety(path: Path) -> dict[str, object]:
    warnings: list[str] = []
    blockers: list[str] = []
    exists = path.exists()
    readable = False
    sha256 = None
    size = 0
    if not exists:
        blockers.append("missing_file")
    elif path.suffix.lower() != ".pdf":
        blockers.append("unsupported_file_type")
    else:
        try:
            size = path.stat().st_size
            readable = os.access(path, os.R_OK)
            sha256 = _hash_file(path)
            if size > 25 * 1024 * 1024:
                warnings.append("very_large_file")
        except OSError:
            blockers.append("unreadable_file")
    return {"exists": exists, "readable": readable, "file_type": path.suffix.lower(), "sha256": sha256, "size_bytes": size, "warnings": warnings, "blockers": blockers}


def _format_detection(pages: list[str], page_count: int | None) -> dict[str, object]:
    if page_count is None:
        return {"source_format": "unknown_pdf", "ocr_needed": False, "extraction_confidence": "low", "text_pages": 0, "empty_text_pages": 0, "warnings": ["page_count_unavailable"]}
    text_pages = sum(1 for text in pages if len(text.strip()) >= 20)
    empty = max(0, page_count - text_pages)
    ratio = text_pages / page_count if page_count else 0
    if page_count == 0:
        source_format = "unknown_pdf"
    elif ratio >= 0.8:
        source_format = "text_based_pdf"
    elif ratio <= 0.1:
        source_format = "scanned_pdf"
    else:
        source_format = "mixed_pdf"
    return {
        "source_format": source_format,
        "ocr_needed": source_format in {"scanned_pdf", "image_only_pdf", "mixed_pdf"},
        "extraction_confidence": "high" if source_format == "text_based_pdf" else "medium" if source_format == "mixed_pdf" else "low",
        "text_pages": text_pages,
        "empty_text_pages": empty,
        "warnings": [] if source_format == "text_based_pdf" else ["ocr_may_be_needed"],
    }


def _page_structure(pages: list[str], page_count: int | None) -> dict[str, object]:
    counts = [len(text.strip()) for text in pages]
    avg = round(sum(counts) / len(counts), 1) if counts else 0.0
    warnings = []
    if page_count is None:
        warnings.append("page_count_unavailable")
    if counts and sum(1 for count in counts if count < 20):
        warnings.append("blank_or_low_text_pages")
    return {
        "page_count": page_count,
        "text_pages": sum(1 for count in counts if count >= 20),
        "blank_or_empty_pages": sum(1 for count in counts if count < 20),
        "low_text_density_pages": sum(1 for count in counts if 0 < count < 250),
        "high_text_density_pages": sum(1 for count in counts if count > 4000),
        "average_chars_per_page": avg,
        "possible_repeated_header_footer": False,
        "possible_references_or_appendix": any("references" in text.lower() or "appendix" in text.lower() for text in pages),
        "warnings": warnings,
    }


def _font_encoding(pages: list[str]) -> dict[str, object]:
    text = "\n".join(pages)
    length = max(1, len(text))
    replacement_ratio = text.count("\ufffd") / length
    single_tokens = len(re.findall(r"\b\w\b", text))
    tokens = max(1, len(re.findall(r"\b\w+\b", text)))
    warnings = []
    if replacement_ratio > 0.001:
        warnings.append("replacement_chars_detected")
    if single_tokens / tokens > 0.45:
        warnings.append("weird_spacing_suspected")
    if re.search(r"(.)\1{12,}", text):
        warnings.append("garbled_text_suspected")
    return {"replacement_character_ratio": round(replacement_ratio, 4), "single_character_token_ratio": round(single_tokens / tokens, 3), "warnings": warnings}


def _metadata_payload(metadata: object) -> dict[str, object]:
    if metadata is None:
        return {}
    data: dict[str, object] = {}
    for key in ("title", "author", "creator", "producer", "subject", "keywords", "creation_date", "modification_date"):
        value = getattr(metadata, key, None)
        if value:
            data[key] = str(value)
    if isinstance(metadata, Mapping):
        for key, value in metadata.items():
            clean_key = str(key).lstrip("/").lower()
            if value and clean_key not in data:
                data[clean_key] = str(value)
    return data


def _metadata_scan(metadata: dict[str, object]) -> dict[str, object]:
    warnings = []
    if not metadata:
        warnings.append("metadata_missing")
    title = str(metadata.get("title") or "")
    if not title:
        warnings.append("metadata_title_empty")
    elif title.lower() in {"untitled", "final", "final_v2", "document"}:
        warnings.append("metadata_title_generic")
    return {"fields": metadata, "warnings": warnings}


def _title_detection(metadata: dict[str, object], pages: list[str], fallback: str) -> dict[str, object]:
    meta_title = str(metadata.get("title") or "").strip()
    first_line = ""
    for line in "\n".join(pages[:1]).splitlines():
        if len(line.strip()) >= 6:
            first_line = line.strip()
            break
    detected = first_line or meta_title or fallback
    confidence = 0.75 if first_line else 0.55 if meta_title else 0.35
    warnings = []
    if not meta_title:
        warnings.append("metadata_title_empty")
    return {"pdf_metadata_title": meta_title or None, "detected_title": detected, "title_confidence": confidence, "warnings": warnings}


def _keyword_scan(pages: list[str]) -> dict[str, object]:
    text = "\n".join(pages).lower()
    matches = []
    for term in KEYWORDS:
        count = text.count(term.lower())
        if count:
            matches.append({"term": term, "count": count})
    matches.sort(key=lambda row: (-int(row["count"]), str(row["term"])))
    return {"top_terms": [str(row["term"]) for row in matches[:5]], "matches": matches}


def _quality_scores(format_detection: dict[str, object], page_structure: dict[str, object], font_encoding: dict[str, object], title_detection: dict[str, object]) -> dict[str, object]:
    page_count = int(page_structure.get("page_count") or 0)
    text_pages = int(page_structure.get("text_pages") or 0)
    text_ratio = text_pages / page_count if page_count else 0
    replacement = float(font_encoding.get("replacement_character_ratio") or 0)
    extraction = int(max(0, min(100, 100 * text_ratio - replacement * 2000)))
    if format_detection.get("source_format") in {"scanned_pdf", "image_only_pdf"}:
        extraction = min(extraction, 24)
    chunk = int(max(0, min(100, extraction - int(page_structure.get("blank_or_empty_pages") or 0) * 5)))
    citation = int(max(0, min(100, extraction * 0.7 + (20 if page_count else 0) + int(float(title_detection.get("title_confidence") or 0) * 10))))
    return {
        "extraction_quality": {"score": extraction, "band": _band(extraction, ("clean", "usable", "questionable", "poor", "reject_or_ocr_needed"))},
        "chunk_readiness": {"score": chunk, "band": _band(chunk, ("clean_chunking", "usable_chunking", "review_chunks", "poor_chunking", "do_not_chunk"))},
        "citation_readiness": {"score": citation, "band": "high" if citation >= 75 else "medium" if citation >= 50 else "low" if citation > 0 else "unavailable"},
    }


def _privacy_scan(pages: list[str]) -> dict[str, object]:
    text = "\n".join(pages)
    findings = []
    patterns = (
        ("email_like_pattern_detected", r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),
        ("phone_like_pattern_detected", r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"),
        ("local_path_detected", r"[A-Za-z]:\\[^\s]+|/Users/[^\s]+"),
        ("token_like_pattern_detected", r"\b(?:api[_-]?key|token|secret)[\w\s:=.-]{0,20}[A-Za-z0-9_-]{12,}\b"),
        ("birth_date_like_pattern_detected", r"\b(?:birth|dob|born)[:\s]+\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"),
    )
    for name, pattern in patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            findings.append(name)
    return {"privacy_level_suggested": "private" if findings else "public_safe", "public_export_safe": not findings, "findings": findings, "warnings": ["privacy_findings_detected"] if findings else []}


def _verdict(blockers: list[str], warnings: list[str], extraction_score: int, chunk_score: int) -> str:
    if blockers:
        return "BLOCK"
    if "extractor_unavailable" in warnings:
        return "UNKNOWN"
    if extraction_score >= 75 and chunk_score >= 75 and not warnings:
        return "PASS"
    return "WARNING"


def _recommended_action(verdict: str) -> str:
    if verdict == "BLOCK":
        return "Do not extract unless the block is reviewed and explicitly overridden."
    if verdict == "WARNING":
        return "Proceed with extraction only with review; inspect chunks before proposals."
    if verdict == "PASS":
        return "Proceed with extraction, then review chunks before proposals."
    return "Resolve preflight uncertainty before trusting extraction quality."


def _band(score: int, names: tuple[str, str, str, str, str]) -> str:
    return names[0] if score >= 90 else names[1] if score >= 75 else names[2] if score >= 50 else names[3] if score >= 25 else names[4]


def _default_reader_factory(path: Path) -> object:
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError as exc:
        raise ImportError("pypdf is not installed") from exc
    return PdfReader(str(path))


def _extract_page_text(page: object) -> str:
    try:
        return str(page.extract_text() or "")
    except Exception:
        return ""


def _report_from_json(data: dict[str, object]) -> DocumentPreflightReport:
    return DocumentPreflightReport(
        document_id=str(data["document_id"]),
        preflight_id=str(data.get("preflight_id") or f"preflight_{data['document_id']}"),
        status=str(data.get("status") or "preflight_pending"),
        verdict=str(data.get("verdict") or "UNKNOWN"),
        created_at_utc=str(data.get("created_at_utc") or _now()),
        file_safety=dict(data.get("file_safety") or {}),
        format_detection=dict(data.get("format_detection") or {}),
        page_structure=dict(data.get("page_structure") or {}),
        font_encoding=dict(data.get("font_encoding") or {}),
        metadata=dict(data.get("metadata") or {}),
        title_detection=dict(data.get("title_detection") or {}),
        keyword_scan=dict(data.get("keyword_scan") or {}),
        quality_scores=dict(data.get("quality_scores") or {}),
        privacy_scan=dict(data.get("privacy_scan") or {}),
        warnings=tuple(str(item) for item in data.get("warnings", []) if item),
        blockers=tuple(str(item) for item in data.get("blockers", []) if item),
        recommended_action=str(data.get("recommended_action") or ""),
    )


def _update_preflight_index(root: Path) -> None:
    entries = []
    for report in list_document_preflights(root=root):
        entries.append({"document_id": report.document_id, "preflight_id": report.preflight_id, "path": str(_preflight_path(root, report.document_id)), "verdict": report.verdict, "status": report.status, "created_at_utc": report.created_at_utc})
    _atomic_write_json(root / "indexes" / "preflight_index.json", {"entries": entries})


def _preflight_path(root: Path, document_id: str) -> Path:
    return ensure_preflight_storage(root) / "preflight" / f"{_safe_id(document_id)}_preflight.json"


def _public_file_safety(payload: object) -> dict[str, object]:
    data = dict(payload) if isinstance(payload, Mapping) else {}
    return {"exists": data.get("exists"), "file_type": data.get("file_type"), "sha256": data.get("sha256"), "size_bytes": data.get("size_bytes"), "warnings": data.get("warnings", []), "blockers": data.get("blockers", [])}


def _public_privacy(payload: object) -> dict[str, object]:
    data = dict(payload) if isinstance(payload, Mapping) else {}
    return {"privacy_level_suggested": data.get("privacy_level_suggested"), "public_export_safe": data.get("public_export_safe"), "findings": data.get("findings", []), "warnings": data.get("warnings", [])}


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


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in str(value).strip()) or "document"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")




