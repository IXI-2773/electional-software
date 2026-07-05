from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import api
from backend.electional.document_content_map import (
    build_document_content_map,
    build_document_scoped_fingerprint,
    detect_document_chapter_section_ranges,
    find_related_document_content,
    format_document_content_map_report,
    get_reader_backend_readiness,
    validate_document_provenance_contract,
)
from backend.electional.document_preflight import run_document_preflight
from backend.electional.source_documents import extract_pdf_text, register_pdf_source


def _register(root: Path, name: str):
    pdf = root / f"{name}.pdf"
    pdf.write_bytes(
        (
            b"%PDF-1.4\n"
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            b"2 0 obj << /Type /Pages /Count 1 /Kids [3 0 R] >> endobj\n"
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Contents 4 0 R >> endobj\n"
            b"4 0 obj << /Length 44 >> stream\nBT /F1 12 Tf 72 200 Td ("
            + name.encode("utf-8")
            + b" document) Tj ET\nendstream endobj\n"
            b"xref\n0 5\n0000000000 65535 f \n"
            b"trailer << /Root 1 0 R /Size 5 >>\nstartxref\n0\n%%EOF"
        )
    )
    return register_pdf_source(pdf, root=root / "store")


def _prepare_source(root: Path, name: str):
    record = _register(root, name)
    run_document_preflight(record.document_id, root=root / "store")
    extract_pdf_text(
        record.document_id,
        root=root / "store",
        extractor=lambda _path: (["Chapter 1 Access Control\nAuthentication Factors\n" * 20], 2),
        override_preflight_block=True,
    )
    return record


def _write_chunk(root: Path, document_id: str, chunk_id: str, chunk_number: int, page_start: int, page_end: int, text: str) -> None:
    payload = {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "source_document_id": document_id,
        "chunk_number": chunk_number,
        "page_start": page_start,
        "page_end": page_end,
        "section_title": None,
        "text": text,
        "text_hash": "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "char_count": len(text),
        "quality_score": 0.95,
        "created_at_utc": "2026-07-02T00:00:00Z",
        "warnings": [],
        "schema_version": "source_chunk_v1",
    }
    path = root / "store" / "chunks" / f"{chunk_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_structure_map(root: Path, document_id: str, headings: list[dict], sections: list[dict], page_count: int = 2) -> None:
    payload = {
        "document_id": document_id,
        "structure_id": f"structure_{document_id}",
        "schema_version": "document_structure_v1",
        "created_at_utc": "2026-07-02T00:00:00Z",
        "source": "controlled_extracted_text",
        "page_count": page_count,
        "sections": sections,
        "headings": headings,
        "toc_candidates": {"toc_found": False, "entries": []},
        "page_layout": {"page_count": page_count, "confidence": "heuristic"},
        "tables": [],
        "figures": [],
        "footnotes": [],
        "references": {"found": False},
        "header_footer": {},
        "chunk_quality": {},
        "warnings": [],
        "blockers": [],
    }
    path = root / "store" / "structure_maps" / f"{document_id}_structure.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_citation(root: Path, document_id: str, chunk_id: str, citation_id: str, *, source_revision: int | None = None) -> None:
    payload = {
        "citation_id": citation_id,
        "document_id": document_id,
        "chunk_id": chunk_id,
        "page_start": 1,
        "page_end": 1,
        "note": "note",
        "quote_excerpt": "excerpt",
        "created_at_utc": "2026-07-02T00:00:00Z",
        "warnings": [],
        "schema_version": "source_citation_v1",
    }
    if source_revision is not None:
        payload["source_revision"] = source_revision
    path = root / "store" / "citations" / f"{citation_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class DocumentContentMapTest(TestCase):
    def test_document_scoped_fingerprint_ignores_other_documents(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = _prepare_source(root, "a")
            b = _prepare_source(root, "b")
            _write_chunk(root, a.document_id, f"chunk_{a.document_id}_0001", 1, 1, 1, "Authentication text")
            first = build_document_scoped_fingerprint(a.document_id, root=root / "store")
            _write_chunk(root, b.document_id, f"chunk_{b.document_id}_0001", 1, 1, 1, "Other text")
            _write_citation(root, b.document_id, f"chunk_{b.document_id}_0001", "citation_b")
            second = build_document_scoped_fingerprint(a.document_id, root=root / "store")
            self.assertEqual(first["fingerprint"], second["fingerprint"])

    def test_document_scoped_fingerprint_changes_for_own_citation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _prepare_source(root, "a")
            chunk_id = f"chunk_{record.document_id}_0001"
            _write_chunk(root, record.document_id, chunk_id, 1, 1, 1, "Authentication text")
            first = build_document_scoped_fingerprint(record.document_id, root=root / "store")
            _write_citation(root, record.document_id, chunk_id, "citation_a")
            second = build_document_scoped_fingerprint(record.document_id, root=root / "store")
            self.assertNotEqual(first["fingerprint"], second["fingerprint"])

    def test_chapter_ranges_use_existing_structure_map(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _prepare_source(root, "a")
            _write_chunk(root, record.document_id, f"chunk_{record.document_id}_0001", 1, 1, 1, "Authentication overview")
            _write_chunk(root, record.document_id, f"chunk_{record.document_id}_0002", 2, 2, 2, "Authorization details")
            _write_structure_map(
                root,
                record.document_id,
                headings=[{"title": "Access Control", "level": 1, "page_number": 1, "confidence": "high", "source": "structure_map_heading"}],
                sections=[
                    {"section_id": "sec_001", "title": "Authentication Factors", "level": 2, "page_start": 1, "page_end": 1, "confidence": "high"},
                    {"section_id": "sec_002", "title": "Authorization", "level": 2, "page_start": 2, "page_end": 2, "confidence": "high"},
                ],
            )
            result = detect_document_chapter_section_ranges(record.document_id, root=root / "store")
            self.assertEqual(result["structure_status"], "resolved")
            self.assertEqual(result["chapters"][0]["title"], "Access Control")
            self.assertEqual(result["chapters"][0]["start_page"], 1)

    def test_no_fake_chapter_when_structure_unknown(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _prepare_source(root, "a")
            result = detect_document_chapter_section_ranges(record.document_id, root=root / "store")
            self.assertEqual(result["chapters"], [])
            self.assertIn(result["structure_status"], {"unknown", "section_only"})

    def test_content_map_assigns_chunks_to_section_ranges(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _prepare_source(root, "a")
            chunk_id = f"chunk_{record.document_id}_0001"
            _write_chunk(root, record.document_id, chunk_id, 1, 1, 1, "Authentication overview")
            _write_structure_map(
                root,
                record.document_id,
                headings=[{"title": "Access Control", "level": 1, "page_number": 1, "confidence": "high", "source": "structure_map_heading"}],
                sections=[{"section_id": "sec_001", "title": "Authentication Factors", "level": 2, "page_start": 1, "page_end": 1, "confidence": "high"}],
            )
            content_map = build_document_content_map(record.document_id, regenerate=True, root=root / "store")
            self.assertEqual(content_map["sections"][0]["chunk_ids"], [chunk_id])

    def test_topic_tags_use_deterministic_exact_matching(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _prepare_source(root, "a")
            _write_chunk(root, record.document_id, f"chunk_{record.document_id}_0001", 1, 1, 1, "Authentication overview")
            _write_structure_map(
                root,
                record.document_id,
                headings=[{"title": "Access Control", "level": 1, "page_number": 1, "confidence": "high", "source": "structure_map_heading"}],
                sections=[{"section_id": "sec_001", "title": "Authentication Factors", "level": 2, "page_start": 1, "page_end": 1, "confidence": "high"}],
            )
            content_map = build_document_content_map(record.document_id, topic_terms=["authentication", "cryptographic escrow"], regenerate=True, root=root / "store")
            self.assertIn("authentication", content_map["sections"][0]["topic_tags"])
            self.assertNotIn("cryptographic escrow", content_map["sections"][0]["topic_tags"])

    def test_related_content_sorted_by_structure_order(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _prepare_source(root, "a")
            _write_chunk(root, record.document_id, f"chunk_{record.document_id}_0001", 1, 1, 1, "Authentication overview")
            _write_chunk(root, record.document_id, f"chunk_{record.document_id}_0002", 2, 2, 2, "Authentication factors")
            _write_structure_map(
                root,
                record.document_id,
                headings=[{"title": "Access Control", "level": 1, "page_number": 1, "confidence": "high", "source": "structure_map_heading"}],
                sections=[
                    {"section_id": "sec_001", "title": "Authentication Overview", "level": 2, "page_start": 1, "page_end": 1, "confidence": "high"},
                    {"section_id": "sec_002", "title": "Authentication Factors", "level": 2, "page_start": 2, "page_end": 2, "confidence": "high"},
                ],
            )
            build_document_content_map(record.document_id, topic_terms=["authentication"], regenerate=True, root=root / "store")
            related = find_related_document_content(record.document_id, "authentication", root=root / "store")
            self.assertEqual(related["results"][0]["page_start"], 1)
            self.assertEqual(related["results"][1]["page_start"], 2)

    def test_related_content_does_not_use_other_documents(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = _prepare_source(root, "a")
            b = _prepare_source(root, "b")
            _write_chunk(root, a.document_id, f"chunk_{a.document_id}_0001", 1, 1, 1, "Authentication overview")
            _write_chunk(root, b.document_id, f"chunk_{b.document_id}_0001", 1, 1, 1, "Authentication overview")
            for record in (a, b):
                _write_structure_map(
                    root,
                    record.document_id,
                    headings=[{"title": "Access Control", "level": 1, "page_number": 1, "confidence": "high", "source": "structure_map_heading"}],
                    sections=[{"section_id": "sec_001", "title": "Authentication Factors", "level": 2, "page_start": 1, "page_end": 1, "confidence": "high"}],
                )
                build_document_content_map(record.document_id, topic_terms=["authentication"], regenerate=True, root=root / "store")
            related = find_related_document_content(a.document_id, "authentication", root=root / "store")
            self.assertTrue(all(item["section_id"].startswith("section_") for item in related["results"]))
            self.assertEqual(related["document_id"], a.document_id)

    def test_provenance_detects_citation_missing_chunk(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _prepare_source(root, "a")
            chunk_id = f"chunk_{record.document_id}_0001"
            _write_chunk(root, record.document_id, chunk_id, 1, 1, 1, "Authentication overview")
            _write_citation(root, record.document_id, chunk_id, "citation_a")
            (root / "store" / "chunks" / f"{chunk_id}.json").unlink()
            result = validate_document_provenance_contract(record.document_id, root=root / "store")
            issue_types = {item["issue_type"] for item in result["issues"]}
            self.assertIn("citation_missing_chunk", issue_types)

    def test_provenance_detects_revision_mismatch(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _prepare_source(root, "a")
            chunk_id = f"chunk_{record.document_id}_0001"
            _write_chunk(root, record.document_id, chunk_id, 1, 1, 1, "Authentication overview")
            _write_citation(root, record.document_id, chunk_id, "citation_a", source_revision=0)
            result = validate_document_provenance_contract(record.document_id, root=root / "store")
            issue_types = {item["issue_type"] for item in result["issues"]}
            self.assertIn("citation_revision_mismatch", issue_types)

    def test_reader_readiness_blocks_missing_page_diagnostics(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _prepare_source(root, "a")
            _write_chunk(root, record.document_id, f"chunk_{record.document_id}_0001", 1, 1, 1, "Authentication overview")
            _write_structure_map(
                root,
                record.document_id,
                headings=[{"title": "Access Control", "level": 1, "page_number": 1, "confidence": "high", "source": "structure_map_heading"}],
                sections=[{"section_id": "sec_001", "title": "Authentication Factors", "level": 2, "page_start": 1, "page_end": 1, "confidence": "high"}],
            )
            build_document_content_map(record.document_id, regenerate=True, root=root / "store")
            readiness = get_reader_backend_readiness(record.document_id, root=root / "store")
            self.assertEqual(readiness["status"], "not_ready")
            self.assertIn("page_diagnostics_missing", readiness["blockers"])

    def test_api_document_content_map_flow(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _prepare_source(root, "a")
            _write_chunk(root, record.document_id, f"chunk_{record.document_id}_0001", 1, 1, 1, "Authentication overview")
            _write_structure_map(
                root,
                record.document_id,
                headings=[{"title": "Access Control", "level": 1, "page_number": 1, "confidence": "high", "source": "structure_map_heading"}],
                sections=[{"section_id": "sec_001", "title": "Authentication Factors", "level": 2, "page_start": 1, "page_end": 1, "confidence": "high"}],
            )
            fingerprint = api.build_document_scoped_fingerprint(record.document_id, root=root / "store")
            content_map = api.build_document_content_map(record.document_id, topic_terms=["authentication"], regenerate=True, root=root / "store")
            related = api.find_related_document_content(record.document_id, "authentication", root=root / "store")
            provenance = api.validate_document_provenance_contract(record.document_id, root=root / "store")
            readiness = api.get_reader_backend_readiness(record.document_id, root=root / "store")
            report = api.format_document_content_map_report(record.document_id, root=root / "store")
            self.assertIn("fingerprint", fingerprint)
            self.assertEqual(content_map["document_id"], record.document_id)
            self.assertEqual(related["document_id"], record.document_id)
            self.assertIn("status", provenance)
            self.assertIn("status", readiness)
            self.assertIn("Document Content Map Report", report)
