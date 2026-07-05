"""Controlled source-document intake for local PDF files."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Iterable


SCHEMA_VERSION = "phase6_pdf_source_intake_v1"
ENGINE_VERSION = "phase6_pdf_source_intake_v1"
SOURCE_DOCUMENT_ROOT = Path(__file__).resolve().parents[2] / "data" / "source_documents"
SUBDIRS = ("pdf_sources", "extracted_text", "indexes", "quarantine")

STATUS_REGISTERED = "registered"
STATUS_EXTRACTED = "extracted"
STATUS_NEEDS_OCR = "needs_ocr_not_supported"
STATUS_EXTRACTOR_UNAVAILABLE = "extractor_unavailable"
STATUS_INVALID_PDF = "invalid_pdf"
STATUS_READ_ERROR = "read_error"


@dataclass(frozen=True)
class SourceDocumentRecord:
    document_id: str
    original_filename: str
    source_path: str
    stored_pdf_path: str | None
    sha256: str
    size_bytes: int
    page_count: int | None
    privacy_level: str
    extraction_status: str
    extracted_text_path: str | None
    extracted_char_count: int
    warnings: tuple[str, ...]
    created_at_utc: str
    updated_at_utc: str
    schema_version: str = SCHEMA_VERSION
    engine_version: str = ENGINE_VERSION
    object_type: str = "source_document"

    def to_json(self, *, public_safe: bool = False) -> dict[str, object]:
        payload = asdict(self)
        payload["warnings"] = list(self.warnings)
        if public_safe:
            payload["source_path"] = None
            payload["stored_pdf_path"] = None
            payload["extracted_text_path"] = None
        return payload


def ensure_source_document_storage(root: Path | str = SOURCE_DOCUMENT_ROOT) -> Path:
    base = Path(root)
    for subdir in SUBDIRS:
        (base / subdir).mkdir(parents=True, exist_ok=True)
    return base


def register_pdf_source(
    path: Path | str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
    copy_into_store: bool = True,
) -> SourceDocumentRecord:
    base = ensure_source_document_storage(root)
    source = Path(path)
    if source.suffix.lower() != ".pdf":
        raise ValueError("PDF source must use a .pdf extension.")
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(str(source))
    digest = _hash_file(source)
    document_id = f"pdf_{digest[:16]}"
    existing = load_source_document(document_id, root=base, missing_ok=True)
    if existing is not None:
        return existing
    stored_pdf_path: str | None = None
    if copy_into_store:
        destination = base / "pdf_sources" / f"{document_id}.pdf"
        _copy_file_atomic(source, destination)
        stored_pdf_path = str(destination)
    now = _now()
    record = SourceDocumentRecord(
        document_id=document_id,
        original_filename=source.name,
        source_path=str(source),
        stored_pdf_path=stored_pdf_path,
        sha256=f"sha256:{digest}",
        size_bytes=source.stat().st_size,
        page_count=None,
        privacy_level="private_local",
        extraction_status=STATUS_REGISTERED,
        extracted_text_path=None,
        extracted_char_count=0,
        warnings=(),
        created_at_utc=now,
        updated_at_utc=now,
    )
    _save_record(record, base)
    return record


def extract_pdf_text(
    document_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
    extractor: Callable[[Path], tuple[list[str], int | None]] | None = None,
    override_preflight_block: bool = False,
) -> SourceDocumentRecord:
    base = ensure_source_document_storage(root)
    record = load_source_document(document_id, root=base)
    try:
        from .document_preflight import can_extract_after_preflight
        gate = can_extract_after_preflight(document_id, root=base, override=override_preflight_block)
    except Exception:
        gate = {"allowed": True, "verdict": "UNKNOWN", "warnings": ["preflight_gate_unavailable"], "blockers": []}
    gate_warning = None
    if gate.get("verdict") == "NOT_RUN":
        gate_warning = "preflight_not_run_extraction_warning"
    elif gate.get("verdict") == "WARNING":
        gate_warning = "preflight_warning_extraction"
    elif gate.get("verdict") == "BLOCK" and not gate.get("allowed"):
        gate_warning = "preflight_blocked_extraction"
    elif gate.get("verdict") == "UNKNOWN" and not gate.get("allowed"):
        gate_warning = "preflight_unknown_extraction_blocked"
    if gate_warning:
        warnings = record.warnings if gate_warning in record.warnings else (*record.warnings, gate_warning)
        if not gate.get("allowed"):
            updated = _replace_record(record, warnings=warnings)
            _save_record(updated, base)
            return updated
        record = _replace_record(record, warnings=warnings)
        _save_record(record, base)
    pdf_path = Path(record.stored_pdf_path or record.source_path)
    if not pdf_path.exists():
        updated = _replace_record(record, extraction_status=STATUS_READ_ERROR, warnings=(*record.warnings, "PDF file is missing."))
        _save_record(updated, base)
        return updated
    try:
        pages, page_count = (extractor or _extract_pdf_pages_with_pypdf)(pdf_path)
    except ImportError:
        updated = _replace_record(
            record,
            extraction_status=STATUS_EXTRACTOR_UNAVAILABLE,
            warnings=(*record.warnings, "pypdf is not installed; text extraction is unavailable."),
        )
        _save_record(updated, base)
        return updated
    except ValueError as exc:
        updated = _replace_record(record, extraction_status=STATUS_INVALID_PDF, warnings=(*record.warnings, str(exc)))
        _save_record(updated, base)
        return updated
    except OSError as exc:
        updated = _replace_record(record, extraction_status=STATUS_READ_ERROR, warnings=(*record.warnings, str(exc)))
        _save_record(updated, base)
        return updated
    char_count = sum(len(str(page).strip()) for page in pages)
    text = _format_extracted_pages(pages)
    if char_count == 0:
        updated = _replace_record(
            record,
            page_count=page_count,
            extraction_status=STATUS_NEEDS_OCR,
            extracted_char_count=0,
            warnings=(*record.warnings, "No extractable text found; scanned PDFs require OCR, which is not supported yet."),
        )
        _save_record(updated, base)
        return updated
    text_path = base / "extracted_text" / f"{record.document_id}.txt"
    _atomic_write_text(text_path, text)
    updated = _replace_record(
        record,
        page_count=page_count,
        extraction_status=STATUS_EXTRACTED,
        extracted_text_path=str(text_path),
        extracted_char_count=char_count,
    )
    _save_record(updated, base)
    return updated


def load_source_document(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT, missing_ok: bool = False) -> SourceDocumentRecord | None:
    path = _record_path(Path(root), document_id)
    if not path.exists():
        if missing_ok:
            return None
        raise FileNotFoundError(str(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    warnings = data.get("warnings", [])
    return SourceDocumentRecord(
        document_id=str(data["document_id"]),
        original_filename=str(data["original_filename"]),
        source_path=str(data.get("source_path") or ""),
        stored_pdf_path=str(data["stored_pdf_path"]) if data.get("stored_pdf_path") else None,
        sha256=str(data["sha256"]),
        size_bytes=int(data.get("size_bytes", 0) or 0),
        page_count=int(data["page_count"]) if data.get("page_count") is not None else None,
        privacy_level=str(data.get("privacy_level") or "private_local"),
        extraction_status=str(data.get("extraction_status") or STATUS_REGISTERED),
        extracted_text_path=str(data["extracted_text_path"]) if data.get("extracted_text_path") else None,
        extracted_char_count=int(data.get("extracted_char_count", 0) or 0),
        warnings=tuple(str(item) for item in warnings if item),
        created_at_utc=str(data.get("created_at_utc") or _now()),
        updated_at_utc=str(data.get("updated_at_utc") or _now()),
    )


def list_source_documents(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> list[SourceDocumentRecord]:
    base = ensure_source_document_storage(root)
    records = []
    for path in sorted((base / "indexes").glob("*.json")):
        if path.name == "source_document_index.json" or path.name.startswith("."):
            continue
        try:
            records.append(load_source_document(path.stem, root=base))
        except Exception:
            continue
    return [record for record in records if record is not None]


def get_extracted_text(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> str:
    record = load_source_document(document_id, root=root)
    if not record or not record.extracted_text_path:
        return ""
    path = Path(record.extracted_text_path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def source_document_public_json(record: SourceDocumentRecord) -> dict[str, object]:
    return record.to_json(public_safe=True)


def _save_record(record: SourceDocumentRecord, root: Path) -> None:
    _atomic_write_json(_record_path(root, record.document_id), record.to_json())
    _update_index(root)


def _record_path(root: Path, document_id: str) -> Path:
    return ensure_source_document_storage(root) / "indexes" / f"{_safe_id(document_id)}.json"


def _update_index(root: Path) -> None:
    entries = []
    for path in sorted((root / "indexes").glob("*.json")):
        if path.name == "source_document_index.json" or path.name.startswith("."):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        entries.append(
            {
                "document_id": data.get("document_id"),
                "original_filename": data.get("original_filename"),
                "sha256": data.get("sha256"),
                "size_bytes": data.get("size_bytes"),
                "page_count": data.get("page_count"),
                "extraction_status": data.get("extraction_status"),
                "privacy_level": data.get("privacy_level"),
                "updated_at_utc": data.get("updated_at_utc"),
            }
        )
    _atomic_write_json(root / "indexes" / "source_document_index.json", {"entries": entries})


def _replace_record(record: SourceDocumentRecord, **changes: object) -> SourceDocumentRecord:
    payload = record.to_json()
    payload.update(changes)
    payload["updated_at_utc"] = _now()
    return SourceDocumentRecord(
        document_id=str(payload["document_id"]),
        original_filename=str(payload["original_filename"]),
        source_path=str(payload.get("source_path") or ""),
        stored_pdf_path=str(payload["stored_pdf_path"]) if payload.get("stored_pdf_path") else None,
        sha256=str(payload["sha256"]),
        size_bytes=int(payload.get("size_bytes", 0) or 0),
        page_count=int(payload["page_count"]) if payload.get("page_count") is not None else None,
        privacy_level=str(payload.get("privacy_level") or "private_local"),
        extraction_status=str(payload.get("extraction_status") or STATUS_REGISTERED),
        extracted_text_path=str(payload["extracted_text_path"]) if payload.get("extracted_text_path") else None,
        extracted_char_count=int(payload.get("extracted_char_count", 0) or 0),
        warnings=tuple(str(item) for item in payload.get("warnings", []) if item),
        created_at_utc=str(payload.get("created_at_utc") or _now()),
        updated_at_utc=str(payload.get("updated_at_utc") or _now()),
    )


def _extract_pdf_pages_with_pypdf(path: Path) -> tuple[list[str], int | None]:
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError as exc:
        raise ImportError("pypdf is not installed") from exc
    try:
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return pages, len(reader.pages)
    except Exception as exc:
        raise ValueError(f"Could not read PDF text: {exc}") from exc


def _format_extracted_pages(pages: Iterable[str]) -> str:
    chunks = []
    for index, text in enumerate(pages, start=1):
        chunks.append(f"--- Page {index} ---\n{str(text).strip()}\n")
    return "\n".join(chunks)


def _copy_file_atomic(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_name(f".{destination.name}.tmp")
    shutil.copyfile(source, temp_path)
    os.replace(temp_path, destination)


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


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        handle.write(text)
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
    return digest.hexdigest()


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in str(value).strip()) or "document"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")

