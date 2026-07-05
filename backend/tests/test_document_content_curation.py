from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import api
from backend.electional.document_content_curation import (
    build_curated_document_content_map,
    format_document_content_curation_report,
    get_document_content_curation_readiness,
    load_document_content_curation,
    normalize_manual_topic_tag,
    save_document_content_curation_change,
    validate_content_curation_change,
)
from backend.electional.document_content_map import build_document_content_map
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


def _write_structure_map(root: Path, document_id: str) -> None:
    payload = {
        "document_id": document_id,
        "structure_id": f"structure_{document_id}",
        "schema_version": "document_structure_v1",
        "created_at_utc": "2026-07-02T00:00:00Z",
        "source": "controlled_extracted_text",
        "page_count": 3,
        "sections": [
            {"section_id": "sec_001", "title": "Authentication Overview", "level": 2, "page_start": 1, "page_end": 1, "confidence": "high"},
            {"section_id": "sec_002", "title": "Authorization", "level": 2, "page_start": 2, "page_end": 2, "confidence": "high"},
        ],
        "headings": [{"title": "Access Control", "level": 1, "page_number": 1, "confidence": "high", "source": "structure_map_heading"}],
        "toc_candidates": {"toc_found": False, "entries": []},
        "page_layout": {"page_count": 3, "confidence": "heuristic"},
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


def _build_detected_map(root: Path, name: str = "a"):
    record = _prepare_source(root, name)
    _write_chunk(root, record.document_id, f"chunk_{record.document_id}_0001", 1, 1, 1, "Authentication overview")
    _write_chunk(root, record.document_id, f"chunk_{record.document_id}_0002", 2, 2, 2, "Authorization details")
    _write_chunk(root, record.document_id, f"chunk_{record.document_id}_0003", 3, 3, 3, "Unassigned appendix")
    _write_structure_map(root, record.document_id)
    content_map = build_document_content_map(record.document_id, topic_terms=["authentication"], regenerate=True, root=root / "store")
    return record, content_map


class DocumentContentCurationTest(TestCase):
    def test_unknown_readiness_for_legacy_overlay_propagates_to_api_report_and_curated_view(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            overlay_path = root / "store" / "document_content_curation" / f"{record.document_id}.json"
            legacy_payload = {
                "schema_version": "document_content_curation_v1",
                "document_id": record.document_id,
                "curation_revision": 1,
                "base_content_map_fingerprint": "legacy-fingerprint",
                "source_revision": "legacy-revision",
                "changes": [],
                "created_at_utc": "2026-07-03T00:00:00Z",
                "updated_at_utc": "2026-07-03T00:00:00Z",
            }
            overlay_path.parent.mkdir(parents=True, exist_ok=True)
            overlay_path.write_text(json.dumps(legacy_payload, indent=2), encoding="utf-8")
            readiness = get_document_content_curation_readiness(record.document_id, root=root / "store")
            curated = api.build_curated_document_content_map(record.document_id, root=root / "store")
            summary = api.get_document_content_curation_summary(record.document_id, root=root / "store")
            report = api.format_document_content_curation_report(record.document_id, root=root / "store")
            self.assertEqual(readiness["status"], "unknown")
            self.assertFalse(curated["curation_applied"])
            self.assertTrue(curated["detected_fallback_used"])
            self.assertEqual(curated["readiness_status"], "unknown")
            self.assertEqual(summary["curation_readiness"], "unknown")
            self.assertIn("Readiness: unknown", report)

    def test_overlay_is_stored_separately_and_detected_map_record_is_unchanged(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, detected = _build_detected_map(root)
            detected_path = root / "store" / "document_content_maps" / f"{record.document_id}.json"
            detected_before = json.loads(detected_path.read_text(encoding="utf-8"))
            result = save_document_content_curation_change(
                record.document_id,
                {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}},
                root=root / "store",
            )
            overlay_path = root / "store" / "document_content_curation" / f"{record.document_id}.json"
            self.assertEqual(result["status"], "saved")
            self.assertTrue(overlay_path.exists())
            self.assertEqual(json.loads(detected_path.read_text(encoding="utf-8")), detected_before)
            self.assertEqual(detected["chapters"][0]["title"], "Access Control")

    def test_chapter_and_section_corrections_apply_only_to_curated_view(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, detected = _build_detected_map(root)
            detected_copy = copy.deepcopy(detected)
            save_document_content_curation_change(
                record.document_id,
                {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}},
                root=root / "store",
            )
            save_document_content_curation_change(
                record.document_id,
                {"target_type": "chapter", "target_id": "chapter_001", "operation": "set_range", "value": {"start_page": 1, "end_page": 2}},
                root=root / "store",
            )
            save_document_content_curation_change(
                record.document_id,
                {"target_type": "section", "target_id": "section_001_001", "operation": "rename", "value": {"title": "Authentication Factors"}},
                root=root / "store",
            )
            save_document_content_curation_change(
                record.document_id,
                {"target_type": "section", "target_id": "section_001_001", "operation": "set_range", "value": {"start_page": 1, "end_page": 2}},
                root=root / "store",
            )
            curated = build_curated_document_content_map(record.document_id, root=root / "store")
            self.assertEqual(detected, detected_copy)
            self.assertEqual(curated["chapters"][0]["title"], "Identity Controls")
            self.assertEqual(curated["chapters"][0]["end_page"], 2)
            self.assertEqual(curated["sections"][0]["title"], "Authentication Factors")
            self.assertEqual(curated["sections"][0]["end_page"], 2)
            self.assertEqual(detected["chapters"][0]["end_page"], 3)
            self.assertEqual(detected["sections"][0]["title"], "Authentication Overview")
            self.assertEqual(detected["sections"][0]["end_page"], 1)

    def test_assign_unassign_and_manual_tag_changes_are_effective_and_idempotent(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            chunk_id = f"chunk_{record.document_id}_0003"
            assign = {"target_type": "section", "target_id": "section_001_002", "operation": "assign_chunk", "value": {"chunk_id": chunk_id}}
            first = save_document_content_curation_change(record.document_id, assign, root=root / "store")
            second = save_document_content_curation_change(record.document_id, assign, root=root / "store")
            save_document_content_curation_change(
                record.document_id,
                {"target_type": "chunk", "target_id": chunk_id, "operation": "add_tag", "value": {"tag": " Identity-Management!! "}},
                root=root / "store",
            )
            save_document_content_curation_change(
                record.document_id,
                {"target_type": "chunk", "target_id": chunk_id, "operation": "remove_tag", "value": {"tag": "identity-management"}},
                root=root / "store",
            )
            unassign = save_document_content_curation_change(
                record.document_id,
                {"target_type": "section", "target_id": "section_001_002", "operation": "unassign_chunk", "value": {"chunk_id": chunk_id}},
                root=root / "store",
            )
            curated = build_curated_document_content_map(record.document_id, root=root / "store")
            target_section = next(item for item in curated["sections"] if item["section_id"] == "section_001_002")
            self.assertEqual(first["curation"]["curation_revision"], 1)
            self.assertEqual(second["status"], "unchanged")
            self.assertEqual(second["curation"]["curation_revision"], 1)
            self.assertGreater(unassign["curation"]["curation_revision"], second["curation"]["curation_revision"])
            self.assertNotIn(chunk_id, target_section["chunk_ids"])
            self.assertIn(chunk_id, curated["unassigned_chunk_ids"])
            self.assertNotIn(normalize_manual_topic_tag("Identity-Management!!"), curated["effective_chunk_topic_tags"].get(chunk_id, []))

    def test_no_op_rename_does_not_increment_revision(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            result = save_document_content_curation_change(
                record.document_id,
                {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Access Control"}},
                root=root / "store",
            )
            self.assertEqual(result["status"], "unchanged")
            self.assertIsNone(result["curation"])

    def test_effective_change_increments_revision_exactly_once(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            result = save_document_content_curation_change(
                record.document_id,
                {"target_type": "section", "target_id": "section_001_001", "operation": "rename", "value": {"title": "Authentication Factors"}},
                root=root / "store",
            )
            self.assertEqual(result["status"], "saved")
            self.assertEqual(result["curation"]["curation_revision"], 1)

    def test_invalid_range_and_unsupported_operation_are_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            reversed_range = validate_content_curation_change(
                record.document_id,
                {"target_type": "section", "target_id": "section_001_001", "operation": "set_range", "value": {"start_page": 2, "end_page": 1}},
                root=root / "store",
            )
            unsupported = validate_content_curation_change(
                record.document_id,
                {"target_type": "chapter", "target_id": "chapter_001", "operation": "delete", "value": {}},
                root=root / "store",
            )
            self.assertFalse(reversed_range["valid"])
            self.assertIn("range_reversed", reversed_range["blockers"])
            self.assertFalse(unsupported["valid"])
            self.assertIn("unsupported_operation", unsupported["blockers"])

    def test_fingerprint_change_marks_overlay_stale_and_falls_back_to_detected_map(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, detected = _build_detected_map(root)
            save_document_content_curation_change(
                record.document_id,
                {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}},
                root=root / "store",
            )
            _write_chunk(root, record.document_id, f"chunk_{record.document_id}_0004", 4, 2, 2, "New text")
            build_document_content_map(record.document_id, regenerate=True, root=root / "store")
            readiness = get_document_content_curation_readiness(record.document_id, root=root / "store")
            curated = build_curated_document_content_map(record.document_id, root=root / "store")
            overlay = load_document_content_curation(record.document_id, root=root / "store").get("curation")
            self.assertEqual(readiness["status"], "stale")
            self.assertIn("base_content_map_changed", readiness["stale_reasons"])
            self.assertFalse(curated["curation_applied"])
            self.assertTrue(curated["detected_fallback_used"])
            self.assertEqual(overlay["curation_revision"], 1)
            self.assertEqual(detected["chapters"][0]["title"], "Access Control")

    def test_source_revision_change_marks_overlay_stale_not_unknown(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            save_document_content_curation_change(
                record.document_id,
                {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}},
                root=root / "store",
            )
            overlay_path = root / "store" / "document_content_curation" / f"{record.document_id}.json"
            payload = json.loads(overlay_path.read_text(encoding="utf-8"))
            payload["source_revision"] = "older-revision"
            overlay_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            readiness = get_document_content_curation_readiness(record.document_id, root=root / "store")
            curated = build_curated_document_content_map(record.document_id, root=root / "store")
            self.assertEqual(readiness["status"], "stale")
            self.assertNotEqual(readiness["status"], "unknown")
            self.assertIn("source_revision_changed", readiness["stale_reasons"])
            self.assertFalse(curated["curation_applied"])
            self.assertTrue(curated["detected_fallback_used"])

    def test_invalid_overlay_is_preserved_and_not_applied(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            save_document_content_curation_change(
                record.document_id,
                {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}},
                root=root / "store",
            )
            overlay_path = root / "store" / "document_content_curation" / f"{record.document_id}.json"
            payload = json.loads(overlay_path.read_text(encoding="utf-8"))
            payload["curation_revision"] = "bad"
            overlay_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            readiness = get_document_content_curation_readiness(record.document_id, root=root / "store")
            curated = build_curated_document_content_map(record.document_id, root=root / "store")
            self.assertEqual(readiness["status"], "invalid")
            self.assertNotEqual(readiness["status"], "unknown")
            self.assertIn("curation_revision_invalid", readiness["invalid_reasons"])
            self.assertFalse(curated["curation_applied"])
            self.assertTrue(curated["detected_fallback_used"])

    def test_bool_revision_is_invalid_in_stored_overlay(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            overlay_path = root / "store" / "document_content_curation" / f"{record.document_id}.json"
            payload = {
                "schema_version": "document_content_curation_v2",
                "document_id": record.document_id,
                "curation_revision": True,
                "base_content_map_fingerprint": "sha256:test",
                "source_revision": 1,
                "chapter_title_overrides": {},
                "chapter_range_overrides": {},
                "section_title_overrides": {},
                "section_range_overrides": {},
                "chunk_assignment_overrides": {},
                "chunk_unassignments": [],
                "manual_tag_additions": {},
                "manual_tag_removals": {},
                "changes": [],
                "created_at_utc": "2026-07-03T00:00:00Z",
                "updated_at_utc": "2026-07-03T00:00:00Z",
            }
            overlay_path.parent.mkdir(parents=True, exist_ok=True)
            overlay_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            readiness = get_document_content_curation_readiness(record.document_id, root=root / "store")
            self.assertEqual(readiness["status"], "invalid")
            self.assertIn("curation_revision_invalid", readiness["invalid_reasons"])

    def test_public_safe_report_omits_paths_text_and_tokens(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            save_document_content_curation_change(
                record.document_id,
                {"target_type": "chunk", "target_id": f"chunk_{record.document_id}_0001", "operation": "add_tag", "value": {"tag": "secret token path C:\\private"}},
                root=root / "store",
            )
            report = format_document_content_curation_report(record.document_id, public_safe=True, root=root / "store")
            self.assertIn("Document Content Curation Report", report)
            self.assertNotIn(str(root), report)
            self.assertNotIn("Authentication overview", report)
            self.assertNotIn("token", report.lower())
            self.assertNotIn("api key", report.lower())
            self.assertNotIn("stack trace", report.lower())
            self.assertNotIn("C:\\", report)

    def test_api_wrappers_call_real_backend_logic(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            validate = api.validate_content_curation_change(
                record.document_id,
                {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}},
                root=root / "store",
            )
            saved = api.save_document_content_curation_change(
                record.document_id,
                {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}},
                root=root / "store",
            )
            summary = api.get_document_content_curation_summary(record.document_id, root=root / "store")
            curated = api.build_curated_document_content_map(record.document_id, root=root / "store")
            report = api.format_document_content_curation_report(record.document_id, root=root / "store")
            self.assertTrue(validate["valid"])
            self.assertEqual(saved["status"], "saved")
            self.assertEqual(summary["curation_revision"], 1)
            self.assertTrue(curated["curation_applied"])
            self.assertIn("Document Content Curation Report", report)
