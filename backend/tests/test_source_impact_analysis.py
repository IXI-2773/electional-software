from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import api
from backend.electional.evidence_binder import build_evidence_binder
from backend.electional.proposal_review import update_proposal_review_status
from backend.electional.source_documents import extract_pdf_text, register_pdf_source
from backend.electional.source_impact_analysis import (
    analyze_source_change_impact,
    create_source_revalidation_item,
    find_source_dependencies,
    format_source_impact_report_text,
    list_source_revalidation_queue,
    update_source_revalidation_status,
)
from backend.electional.source_knowledge import chunk_extracted_text, create_manual_proposal, create_source_citation
from backend.electional.source_reliability_manager import update_source_metadata_for_reliability


def _register(root: Path, name: str):
    pdf = root / f"{name}.pdf"
    pdf.write_bytes(f"%PDF-1.4\n{name}\n%%EOF".encode("utf-8"))
    return register_pdf_source(pdf, root=root / "store")


def _graph(root: Path, name: str = "a"):
    record = _register(root, name)
    extract_pdf_text(record.document_id, root=root / "store", extractor=lambda _path: (["Manual review source text. " * 20], 1))
    chunk = chunk_extracted_text(record.document_id, root=root / "store")[0]
    citation = create_source_citation(record.document_id, chunk.chunk_id, "Citation note", root=root / "store")
    proposal = create_manual_proposal(record.document_id, chunk.chunk_id, "Manual proposal", root=root / "store")
    update_proposal_review_status(proposal.proposal_id, "approved_for_later_promotion", "approve", root=root / "store")
    binder = build_evidence_binder(proposal.proposal_id, root=root / "store")
    return record, chunk, citation, proposal, binder


class SourceImpactAnalysisTest(TestCase):
    def test_find_source_dependencies_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            result = find_source_dependencies(record.document_id, root=root / "store")
            self.assertEqual(result["affected_counts"]["citations"], 0)
            self.assertEqual(result["affected_counts"]["proposals"], 0)

    def test_find_source_dependencies_with_citation_and_proposal(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _chunk, citation, proposal, binder = _graph(root)
            result = find_source_dependencies(record.document_id, root=root / "store")
            self.assertIn(citation.citation_id, result["affected_records"]["citation_ids"])
            self.assertIn(proposal.proposal_id, result["affected_records"]["proposal_ids"])
            self.assertIn(binder["binder_id"], result["affected_records"]["evidence_binder_ids"])

    def test_analyze_source_change_impact_none(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            result = analyze_source_change_impact(record.document_id, change_type="manual_review", root=root / "store")
            self.assertEqual(result["impact_severity"], "none")

    def test_analyze_source_change_impact_high(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _chunk, _citation, _proposal, _binder = _graph(root)
            update_source_metadata_for_reliability(record.document_id, {"manual_title": "Shared", "authority_level": "low"}, root=root / "store")
            result = analyze_source_change_impact(record.document_id, change_type="superseded", root=root / "store")
            self.assertEqual(result["impact_severity"], "high")

    def test_corrupt_source_with_dependencies_is_critical(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _chunk, _citation, _proposal, _binder = _graph(root)
            result = analyze_source_change_impact(record.document_id, change_type="corrupt", root=root / "store")
            self.assertEqual(result["impact_severity"], "critical")

    def test_missing_index_returns_unknown_warning(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _chunk, _citation, _proposal, _binder = _graph(root)
            (root / "store" / "indexes" / "citation_index.json").unlink(missing_ok=True)
            result = analyze_source_change_impact(record.document_id, root=root / "store")
            self.assertEqual(result["impact_severity"], "unknown")
            self.assertTrue(any("citations_index_missing" == item for item in result["warnings"]))

    def test_create_source_revalidation_item(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            item = create_source_revalidation_item(record.document_id, change_type="manual_review", root=root / "store")
            self.assertEqual(item["status"], "pending_review")

    def test_duplicate_pending_queue_item_is_not_created(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            first = create_source_revalidation_item(record.document_id, change_type="manual_review", root=root / "store")
            second = create_source_revalidation_item(record.document_id, change_type="manual_review", root=root / "store")
            self.assertEqual(first["queue_item_id"], second["queue_item_id"])

    def test_list_source_revalidation_queue_filter(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _chunk, _citation, _proposal, _binder = _graph(root)
            create_source_revalidation_item(record.document_id, change_type="superseded", root=root / "store")
            result = list_source_revalidation_queue(minimum_severity="high", root=root / "store")
            self.assertEqual(result["count"], 1)

    def test_update_source_revalidation_status(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            item = create_source_revalidation_item(record.document_id, change_type="manual_review", root=root / "store")
            updated = update_source_revalidation_status(item["queue_item_id"], "reviewed", note="done", root=root / "store")
            self.assertEqual(updated["status"], "reviewed")

    def test_public_safe_report_hides_private_content(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            report = format_source_impact_report_text(record.document_id, public_safe=True, root=root / "store")
            self.assertNotIn(str(root), report)
            self.assertNotIn("Manual review source text", report)

    def test_api_source_impact_flow(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            analysis = api.analyze_source_change_impact(record.document_id, change_type="manual_review", root=root / "store")
            item = api.create_source_revalidation_item(record.document_id, change_type="manual_review", root=root / "store")
            queue = api.list_source_revalidation_queue(root=root / "store")
            report = api.format_source_impact_report_text(record.document_id, root=root / "store")
            self.assertEqual(analysis["document_id"], record.document_id)
            self.assertEqual(item["document_id"], record.document_id)
            self.assertEqual(queue["count"], 1)
            self.assertIn("Source Change Impact Report", report)
