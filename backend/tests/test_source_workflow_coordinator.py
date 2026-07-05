from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import api
from backend.electional.document_manifest import build_document_manifest, load_document_manifest
from backend.electional.document_preflight import run_document_preflight
from backend.electional.source_documents import extract_pdf_text, register_pdf_source
from backend.electional.source_knowledge import chunk_extracted_text, create_source_citation
from backend.electional.source_workflow_coordinator import (
    calculate_pipeline_state_fingerprint,
    create_source_workflow_plan,
    execute_source_workflow_stage,
    format_source_workflow_report,
    get_source_workflow_resume_state,
    recommend_next_source_workflow_stage,
    validate_source_workflow_stage,
)


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


def _prepare_extracted(root: Path, name: str = "a"):
    record = _register(root, name)
    run_document_preflight(record.document_id, root=root / "store")
    extract_pdf_text(
        record.document_id,
        root=root / "store",
        extractor=lambda _path: (["Page 1\nDocument text. " * 30], 1),
        override_preflight_block=True,
    )
    return record


class SourceWorkflowCoordinatorTest(TestCase):
    def test_pipeline_fingerprint_is_stable(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _prepare_extracted(root)
            first = calculate_pipeline_state_fingerprint(record.document_id, root=root / "store")
            second = calculate_pipeline_state_fingerprint(record.document_id, root=root / "store")
            self.assertEqual(first["fingerprint"], second["fingerprint"])

    def test_pipeline_fingerprint_changes_when_chunk_index_changes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _prepare_extracted(root)
            chunk_extracted_text(record.document_id, root=root / "store")
            first = calculate_pipeline_state_fingerprint(record.document_id, root=root / "store")
            index_path = root / "store" / "indexes" / "chunk_index.json"
            payload = json.loads(index_path.read_text(encoding="utf-8"))
            payload["test_marker"] = "changed"
            index_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            second = calculate_pipeline_state_fingerprint(record.document_id, root=root / "store")
            self.assertNotEqual(first["fingerprint"], second["fingerprint"])

    def test_manifest_reuse_invalidated_by_pipeline_change(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _prepare_extracted(root)
            chunks = chunk_extracted_text(record.document_id, root=root / "store")
            first = build_document_manifest(record.document_id, regenerate=True, root=root / "store")
            create_source_citation(record.document_id, chunks[0].chunk_id, "Citation note", root=root / "store")
            second = build_document_manifest(record.document_id, regenerate=False, root=root / "store")
            self.assertEqual(first["source_revision"], second["source_revision"])
            self.assertNotEqual(first["pipeline_fingerprint"], second["pipeline_fingerprint"])
            self.assertTrue(second["fingerprint_changed"])

    def test_recommend_preflight_when_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            result = recommend_next_source_workflow_stage(record.document_id, root=root / "store")
            self.assertEqual(result["recommended_stage"], "run_preflight")

    def test_recommend_chunking_when_extraction_complete(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _prepare_extracted(root)
            result = recommend_next_source_workflow_stage(record.document_id, root=root / "store")
            self.assertEqual(result["recommended_stage"], "chunk_text")

    def test_workflow_plan_defaults_to_dry_run(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _prepare_extracted(root)
            plan = create_source_workflow_plan(record.document_id, root=root / "store")
            self.assertTrue(plan["dry_run"])

    def test_workflow_plan_does_not_execute(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _prepare_extracted(root)
            create_source_workflow_plan(record.document_id, requested_stage="chunk_text", root=root / "store")
            manifest = load_document_manifest(record.document_id, root=root / "store")["manifest"]
            self.assertEqual(manifest["pipeline"]["chunking"], "missing")

    def test_dependency_validation_blocks_missing_extraction(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            result = validate_source_workflow_stage(record.document_id, "chunk_text", root=root / "store")
            self.assertFalse(result["allowed"])
            self.assertIn("extracted_text", result["missing_dependencies"])

    def test_execute_one_stage_does_not_run_next_stage(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _prepare_extracted(root)
            plan = create_source_workflow_plan(record.document_id, requested_stage="chunk_text", dry_run=False, root=root / "store")
            result = execute_source_workflow_stage(plan["workflow_plan_id"], dry_run=False, root=root / "store")
            manifest = load_document_manifest(record.document_id, root=root / "store")["manifest"]
            self.assertEqual(result["status"], "completed")
            self.assertEqual(manifest["pipeline"]["chunking"], "complete")
            self.assertEqual(manifest["pipeline"]["page_diagnostics"], "missing")

    def test_execution_refreshes_manifest_and_readiness(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _prepare_extracted(root)
            before = build_document_manifest(record.document_id, regenerate=True, root=root / "store")
            plan = create_source_workflow_plan(record.document_id, requested_stage="chunk_text", dry_run=False, root=root / "store")
            result = execute_source_workflow_stage(plan["workflow_plan_id"], dry_run=False, root=root / "store")
            after = load_document_manifest(record.document_id, root=root / "store")["manifest"]
            self.assertNotEqual(before["pipeline_fingerprint"], after["pipeline_fingerprint"])
            self.assertEqual(result["after"]["readiness_status"], (after.get("backend_readiness") or {}).get("status"))

    def test_public_report_hides_private_paths(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _prepare_extracted(root)
            report = format_source_workflow_report(record.document_id, public_safe=True, root=root / "store")
            self.assertNotIn(str(root), report)
            self.assertNotIn("Page 1", report)

    def test_api_source_workflow_flow(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _prepare_extracted(root)
            fingerprint = api.calculate_pipeline_state_fingerprint(record.document_id, root=root / "store")
            recommendation = api.recommend_next_source_workflow_stage(record.document_id, root=root / "store")
            plan = api.create_source_workflow_plan(record.document_id, requested_stage="chunk_text", root=root / "store")
            execution = api.execute_source_workflow_stage(plan["workflow_plan_id"], dry_run=True, root=root / "store")
            resume = api.get_source_workflow_resume_state(record.document_id, root=root / "store")
            report = api.format_source_workflow_report(record.document_id, root=root / "store")
            self.assertIn("fingerprint", fingerprint)
            self.assertEqual(recommendation["recommended_stage"], "chunk_text")
            self.assertTrue(plan["dry_run"])
            self.assertEqual(execution["status"], "dry_run_only")
            self.assertEqual(resume["recommended_stage"], "chunk_text")
            self.assertIn("Source Workflow Report", report)
