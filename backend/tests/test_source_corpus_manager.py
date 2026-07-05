from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.electional import api
from backend.electional.evidence_binder import build_evidence_binder
from backend.electional.source_corpus_manager import (
    build_source_corpus_inventory,
    bulk_recalculate_source_reliability,
    bulk_refresh_evidence_binders,
    create_corpus_batch_plan,
    create_retry_batch_for_failed_sources,
    detect_corpus_missing_steps,
    detect_source_missing_steps,
    execute_corpus_batch_plan,
    format_source_corpus_report_text,
    get_source_corpus_health,
    list_duplicate_source_queue,
    list_failed_source_tasks,
    list_superseded_source_queue,
)
from backend.electional.source_documents import extract_pdf_text, register_pdf_source
from backend.electional.source_knowledge import chunk_extracted_text, create_manual_proposal, create_source_citation
from backend.electional.source_reliability_manager import (
    detect_duplicate_source_identity,
    link_source_replacement,
    update_source_metadata_for_reliability,
)


def _register(root: Path, name: str):
    pdf = root / f"{name}.pdf"
    pdf.write_bytes(f"%PDF-1.4\n{name}\n%%EOF".encode("utf-8"))
    return register_pdf_source(pdf, root=root / "store")


def _extracted(root: Path, name: str, text: str = "Manual review source text with citation support."):
    record = _register(root, name)
    extract_pdf_text(record.document_id, root=root / "store", extractor=lambda _path: ([text], 1))
    chunks = chunk_extracted_text(record.document_id, root=root / "store")
    return record.document_id, chunks[0] if chunks else None


class SourceCorpusManagerTest(unittest.TestCase):
    def test_build_source_corpus_inventory_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            inventory = build_source_corpus_inventory(regenerate=True, root=Path(tmp) / "store")
            self.assertEqual(inventory["source_count"], 0)
            self.assertEqual(inventory["status"], "empty")

    def test_build_source_corpus_inventory_with_sources(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc, _chunk = _extracted(root, "a")
            update_source_metadata_for_reliability(doc, {"source_type": "official_policy", "authority_level": "primary"}, root=root / "store")
            inventory = build_source_corpus_inventory(regenerate=True, root=root / "store")
            self.assertEqual(inventory["source_count"], 1)
            self.assertEqual(inventory["items"][0]["document_id"], doc)
            self.assertNotIn(str(root), str(inventory["items"][0]))

    def test_detect_source_missing_steps(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            result = detect_source_missing_steps(record.document_id, root=root / "store")
            self.assertIn("preflight", result["missing_steps"])
            self.assertIn("extracted_text", result["missing_steps"])

    def test_detect_corpus_missing_steps(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _register(root, "a")
            result = detect_corpus_missing_steps(root=root / "store")
            self.assertEqual(result["sources_checked"], 1)
            self.assertEqual(result["sources_missing_preflight"], 1)

    def test_get_source_corpus_health_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            health = get_source_corpus_health(root=Path(tmp) / "store")
            self.assertEqual(health["status"], "empty")

    def test_get_source_corpus_health_warning(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _register(root, "a")
            health = get_source_corpus_health(root=root / "store")
            self.assertEqual(health["status"], "warning")
            self.assertEqual(health["source_count"], 1)

    def test_create_corpus_batch_plan_dry_run(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            plan = create_corpus_batch_plan("detect_missing_steps", [record.document_id], root=root / "store")
            self.assertEqual(plan["status"], "planned")
            self.assertEqual(plan["document_ids"], [record.document_id])

    def test_execute_corpus_batch_plan_dry_run(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            plan = create_corpus_batch_plan("detect_missing_steps", [record.document_id], root=root / "store")
            result = execute_corpus_batch_plan(plan["batch_id"], dry_run=True, root=root / "store")
            self.assertTrue(result["dry_run"])
            self.assertEqual(result["items"][0]["status"], "planned")

    def test_execute_corpus_batch_plan_limit(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = _register(root, "a")
            second = _register(root, "b")
            plan = create_corpus_batch_plan("detect_missing_steps", [first.document_id, second.document_id], root=root / "store")
            result = execute_corpus_batch_plan(plan["batch_id"], dry_run=True, limit=1, root=root / "store")
            self.assertEqual(result["processed"], 1)

    def test_list_failed_source_tasks(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _register(root, "a")
            failed = list_failed_source_tasks(root=root / "store")
            self.assertGreaterEqual(failed["failed_count"], 1)

    def test_create_retry_batch_for_failed_sources(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _register(root, "a")
            plan = create_retry_batch_for_failed_sources(root=root / "store")
            self.assertEqual(plan["action"], "detect_missing_steps")
            self.assertEqual(len(plan["document_ids"]), 1)

    def test_bulk_recalculate_source_reliability_dry_run(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            result = bulk_recalculate_source_reliability([record.document_id], dry_run=True, root=root / "store")
            self.assertEqual(result["sources_planned"], 1)
            self.assertEqual(result["sources_recalculated"], 0)

    def test_bulk_refresh_evidence_binders_dry_run(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc, chunk = _extracted(root, "a")
            proposal = create_manual_proposal(doc, chunk.chunk_id, "Allow manual review.", root=root / "store")
            create_source_citation(doc, chunk.chunk_id, "Citation.", quote_excerpt="Allow manual review.", root=root / "store")
            build_evidence_binder(proposal.proposal_id, root=root / "store")
            result = bulk_refresh_evidence_binders([doc], dry_run=True, root=root / "store")
            self.assertEqual(result["binders_found"], 1)
            self.assertEqual(result["binders_refreshed"], 0)

    def test_list_duplicate_source_queue(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = _register(root, "a")
            second = _register(root, "b")
            update_source_metadata_for_reliability(first.document_id, {"manual_title": "Shared"}, root=root / "store")
            update_source_metadata_for_reliability(second.document_id, {"manual_title": "Shared"}, root=root / "store")
            detect_duplicate_source_identity(first.document_id, root=root / "store")
            queue = list_duplicate_source_queue(root=root / "store")
            self.assertGreaterEqual(queue["duplicate_count"], 1)

    def test_list_superseded_source_queue(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = _register(root, "old")
            new = _register(root, "new")
            link_source_replacement(old.document_id, new.document_id, root=root / "store")
            queue = list_superseded_source_queue(root=root / "store")
            self.assertEqual(queue["superseded_count"], 1)

    def test_format_source_corpus_report_text_public_safe(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _register(root, "a")
            report = format_source_corpus_report_text(root=root / "store")
            self.assertIn("Source Corpus Report", report)
            self.assertNotIn(str(root), report)

    def test_api_source_corpus_flow(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _register(root, "a")
            inventory = api.build_source_corpus_inventory(regenerate=True, root=root / "store")
            health = api.get_source_corpus_health(root=root / "store")
            report = api.format_source_corpus_report_text(root=root / "store")
            self.assertEqual(inventory["source_count"], 1)
            self.assertEqual(health["source_count"], 1)
            self.assertIn("Coverage:", report)


if __name__ == "__main__":
    unittest.main()