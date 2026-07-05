from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import api
from backend.electional.document_manifest import (
    build_document_manifest,
    calculate_document_revision_state,
    format_document_manifest_report,
    get_document_backend_readiness,
    normalize_source_locator,
    reconcile_document_subsystems,
    validate_source_locator,
)
from backend.electional.document_preflight import run_document_preflight
from backend.electional.source_documents import extract_pdf_text, register_pdf_source
from backend.electional.source_knowledge import chunk_extracted_text, create_source_citation


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


def _prepare_document(root: Path, name: str = "a"):
    record = _register(root, name)
    run_document_preflight(record.document_id, root=root / "store")
    extract_pdf_text(
        record.document_id,
        root=root / "store",
        extractor=lambda _path: (["Page 1\nDocument text. " * 30], 1),
        override_preflight_block=True,
    )
    chunks = chunk_extracted_text(record.document_id, root=root / "store")
    return record, chunks


class DocumentManifestTest(TestCase):
    def test_build_manifest_for_registered_document(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, chunks = _prepare_document(root)
            manifest = build_document_manifest(record.document_id, regenerate=True, root=root / "store")
            self.assertEqual(manifest["document_id"], record.document_id)
            self.assertEqual(manifest["pipeline"]["registered"], "complete")
            self.assertEqual(manifest["pipeline"]["preflight"], "complete")
            self.assertEqual(manifest["pipeline"]["extraction"], "complete")
            self.assertEqual(manifest["pipeline"]["chunking"], "complete")
            self.assertEqual(manifest["record_references"]["chunk_record_ids"], [chunk.chunk_id for chunk in chunks])

    def test_manifest_does_not_mark_missing_stage_complete(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            manifest = build_document_manifest(record.document_id, regenerate=True, root=root / "store")
            self.assertEqual(manifest["pipeline"]["structure_map"], "missing")
            self.assertNotEqual(manifest["pipeline"]["structure_map"], "complete")

    def test_unchanged_source_preserves_revision(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _chunks = _prepare_document(root)
            first = build_document_manifest(record.document_id, regenerate=True, root=root / "store")
            second = build_document_manifest(record.document_id, regenerate=True, root=root / "store")
            self.assertEqual(first["source_revision"], 1)
            self.assertEqual(second["source_revision"], 1)
            self.assertFalse(second["revision_changed"])

    def test_changed_source_increments_revision(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _chunks = _prepare_document(root)
            first = build_document_manifest(record.document_id, regenerate=True, root=root / "store")
            source_index = root / "store" / "indexes" / f"{record.document_id}.json"
            payload = json.loads(source_index.read_text(encoding="utf-8"))
            payload["sha256"] = "sha256:changed"
            source_index.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            changed = calculate_document_revision_state(record.document_id, existing_manifest=first, root=root / "store")
            self.assertEqual(changed["source_revision"], 2)
            self.assertTrue(changed["revision_changed"])

    def test_source_change_marks_components_stale(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _chunks = _prepare_document(root)
            build_document_manifest(record.document_id, regenerate=True, root=root / "store")
            source_index = root / "store" / "indexes" / f"{record.document_id}.json"
            payload = json.loads(source_index.read_text(encoding="utf-8"))
            payload["sha256"] = "sha256:changed"
            source_index.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            manifest = build_document_manifest(record.document_id, regenerate=True, root=root / "store")
            self.assertIn("extraction", manifest["stale_components"])
            self.assertIn("evidence_binder_recheck", manifest["stale_components"])

    def test_validate_source_locator_valid(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, chunks = _prepare_document(root)
            locator = {
                "document_id": record.document_id,
                "source_revision": "1",
                "page_number": "1",
                "chunk_id": chunks[0].chunk_id,
                "character_start": "0",
                "character_end": "12",
            }
            result = validate_source_locator(locator, root=root / "store")
            self.assertTrue(result["valid"])
            self.assertEqual(result["normalized_locator"]["schema_version"], "source_locator_v1")

    def test_validate_source_locator_rejects_invalid_offsets(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _chunks = _prepare_document(root)
            result = validate_source_locator(
                {"document_id": record.document_id, "character_start": 10, "character_end": 5},
                root=root / "store",
            )
            self.assertFalse(result["valid"])
            self.assertIn("character_end_precedes_start", result["blockers"])

    def test_locator_does_not_guess_missing_values(self) -> None:
        locator = normalize_source_locator({"document_id": "pdf_abc123", "page_number": "", "chunk_id": ""})
        self.assertEqual(locator, {"schema_version": "source_locator_v1", "document_id": "pdf_abc123"})

    def test_reconcile_detects_citation_missing_chunk(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, chunks = _prepare_document(root)
            citation = create_source_citation(record.document_id, chunks[0].chunk_id, "Citation note", root=root / "store")
            (root / "store" / "chunks" / f"{chunks[0].chunk_id}.json").unlink()
            result = reconcile_document_subsystems(record.document_id, root=root / "store")
            issue_types = {issue["issue_type"] for issue in result["issues"]}
            self.assertEqual(citation.document_id, record.document_id)
            self.assertIn("citation_missing_chunk", issue_types)

    def test_backend_readiness_not_ready_when_chunks_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            run_document_preflight(record.document_id, root=root / "store")
            extract_pdf_text(
                record.document_id,
                root=root / "store",
                extractor=lambda _path: (["Page 1\nDocument text. " * 30], 1),
                override_preflight_block=True,
            )
            manifest = build_document_manifest(record.document_id, regenerate=True, root=root / "store")
            readiness = get_document_backend_readiness(record.document_id, manifest_hint=manifest, root=root / "store")
            self.assertEqual(readiness["status"], "not_ready")
            self.assertIn("chunks_missing", readiness["blockers"])

    def test_public_report_hides_private_paths(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _chunks = _prepare_document(root)
            report = format_document_manifest_report(record.document_id, public_safe=True, root=root / "store")
            self.assertNotIn(str(root), report)
            self.assertNotIn("pdf_sources", report)

    def test_api_document_manifest_flow(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, chunks = _prepare_document(root)
            manifest = api.build_document_manifest(record.document_id, regenerate=True, root=root / "store")
            loaded = api.load_document_manifest(record.document_id, root=root / "store")
            locator = api.validate_source_locator({"document_id": record.document_id, "chunk_id": chunks[0].chunk_id}, root=root / "store")
            consistency = api.reconcile_document_subsystems(record.document_id, root=root / "store")
            readiness = api.get_document_backend_readiness(record.document_id, root=root / "store")
            report = api.format_document_manifest_report(record.document_id, root=root / "store")
            self.assertEqual(manifest["document_id"], record.document_id)
            self.assertEqual(loaded["status"], "loaded")
            self.assertTrue(locator["valid"])
            self.assertIn("status", consistency)
            self.assertIn("status", readiness)
            self.assertIn("Document Backend Manifest", report)
