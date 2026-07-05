from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import api
from backend.electional.evidence_binder import build_evidence_binder
from backend.electional.proposal_review import update_proposal_review_status
from backend.electional.source_documents import extract_pdf_text, register_pdf_source
from backend.electional.source_impact_analysis import create_source_revalidation_item
from backend.electional.source_knowledge import chunk_extracted_text, create_manual_proposal, create_source_citation
from backend.electional.source_revalidation_review import (
    build_revalidation_evidence_recheck,
    build_revalidation_review_workspace,
    finalize_source_revalidation_review,
    format_source_revalidation_resolution_report,
    load_source_revalidation_resolution,
    save_source_revalidation_resolution,
    validate_dependency_dispositions,
    validate_revalidation_queue_closure,
)


def _register(root: Path, name: str):
    pdf = root / f"{name}.pdf"
    pdf.write_bytes(f"%PDF-1.4\n{name}\n%%EOF".encode("utf-8"))
    return register_pdf_source(pdf, root=root / "store")


def _graph(root: Path):
    record = _register(root, "a")
    extract_pdf_text(record.document_id, root=root / "store", extractor=lambda _path: (["Manual review source text. " * 20], 1))
    chunk = chunk_extracted_text(record.document_id, root=root / "store")[0]
    citation = create_source_citation(record.document_id, chunk.chunk_id, "Citation note", root=root / "store")
    proposal = create_manual_proposal(record.document_id, chunk.chunk_id, "Manual proposal", root=root / "store")
    update_proposal_review_status(proposal.proposal_id, "approved_for_later_promotion", "approve", root=root / "store")
    binder = build_evidence_binder(proposal.proposal_id, root=root / "store")
    queue = create_source_revalidation_item(record.document_id, change_type="superseded", root=root / "store")
    return record, citation, proposal, binder, queue


def _all_still_valid(workspace: dict[str, object]) -> dict[str, object]:
    affected = workspace.get("affected_record_ids", {})
    return {
        "citations": {item: "still_valid" for item in affected.get("citation_ids", [])},
        "proposals": {item: "still_valid" for item in affected.get("proposal_ids", [])},
        "proposal_reviews": {item: "still_valid" for item in affected.get("proposal_review_ids", [])},
        "evidence_binders": {item: "still_valid" for item in affected.get("evidence_binder_ids", [])},
    }


class SourceRevalidationReviewTest(TestCase):
    def test_build_review_workspace(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, citation, proposal, binder, queue = _graph(root)
            workspace = build_revalidation_review_workspace(queue["queue_item_id"], root=root / "store")
            self.assertEqual(workspace["document_id"], record.document_id)
            self.assertIn(citation.citation_id, workspace["affected_record_ids"]["citation_ids"])
            self.assertIn(proposal.proposal_id, workspace["affected_record_ids"]["proposal_ids"])
            self.assertIn(binder["binder_id"], workspace["affected_record_ids"]["evidence_binder_ids"])

    def test_build_review_workspace_missing_queue_item(self) -> None:
        with TemporaryDirectory() as tmp:
            result = build_revalidation_review_workspace("impact_missing", root=Path(tmp) / "store")
            self.assertEqual(result["status"], "not_found")

    def test_validate_dispositions_rejects_unknown_id(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _record, _citation, _proposal, _binder, queue = _graph(root)
            validation = validate_dependency_dispositions({"citations": {"citation_missing": "still_valid"}}, queue_item_id=queue["queue_item_id"], root=root / "store")
            self.assertFalse(validation["valid"])
            self.assertIn("unknown_citations_id", validation["blockers"])

    def test_validate_dispositions_rejects_invalid_value(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _record, citation, _proposal, _binder, queue = _graph(root)
            validation = validate_dependency_dispositions({"citations": {citation.citation_id: "bad_value"}}, queue_item_id=queue["queue_item_id"], root=root / "store")
            self.assertFalse(validation["valid"])
            self.assertIn("invalid_citations_disposition", validation["blockers"])

    def test_evidence_recheck_summary(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _record, _citation, _proposal, _binder, queue = _graph(root)
            summary = build_revalidation_evidence_recheck(queue["queue_item_id"], root=root / "store")
            self.assertEqual(summary["evidence_binders_checked"], 1)
            self.assertEqual(summary["binders_available"], 1)

    def test_save_and_load_resolution(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _record, _citation, _proposal, _binder, queue = _graph(root)
            workspace = build_revalidation_review_workspace(queue["queue_item_id"], root=root / "store")
            resolution = save_source_revalidation_resolution(queue["queue_item_id"], "resolved_no_change", _all_still_valid(workspace), review_note="manual review", root=root / "store")
            loaded = load_source_revalidation_resolution(queue["queue_item_id"], root=root / "store")
            self.assertEqual(resolution["queue_item_id"], queue["queue_item_id"])
            self.assertEqual(loaded["resolution"]["resolution_decision"], "resolved_no_change")

    def test_resolved_no_change_requires_safe_dispositions(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _record, _citation, _proposal, _binder, queue = _graph(root)
            workspace = build_revalidation_review_workspace(queue["queue_item_id"], root=root / "store")
            dispositions = _all_still_valid(workspace)
            first_citation = next(iter(dispositions["citations"]))
            dispositions["citations"][first_citation] = "needs_review"
            closure = validate_revalidation_queue_closure(queue["queue_item_id"], "resolved_no_change", dispositions, root=root / "store")
            self.assertFalse(closure["closure_allowed"])

    def test_high_impact_requires_dispositions(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _record, _citation, _proposal, _binder, queue = _graph(root)
            closure = validate_revalidation_queue_closure(queue["queue_item_id"], "keep_open", {}, root=root / "store")
            self.assertFalse(closure["closure_allowed"])
            self.assertIn("high_impact_requires_dependency_dispositions", closure["blockers"])

    def test_replacement_required_needs_matching_disposition(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _record, _citation, _proposal, _binder, queue = _graph(root)
            workspace = build_revalidation_review_workspace(queue["queue_item_id"], root=root / "store")
            closure = validate_revalidation_queue_closure(queue["queue_item_id"], "replacement_source_required", _all_still_valid(workspace), root=root / "store")
            self.assertFalse(closure["closure_allowed"])
            self.assertIn("replacement_source_required_needs_matching_disposition", closure["blockers"])

    def test_finalize_review_updates_queue_status(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _record, _citation, _proposal, _binder, queue = _graph(root)
            workspace = build_revalidation_review_workspace(queue["queue_item_id"], root=root / "store")
            dispositions = _all_still_valid(workspace)
            first_citation = next(iter(dispositions["citations"]))
            dispositions["citations"][first_citation] = "needs_review"
            result = finalize_source_revalidation_review(queue["queue_item_id"], "resolved_with_manual_followup", dispositions, review_note="follow up", root=root / "store")
            self.assertEqual(result["queue_item"]["status"], "reviewed")

    def test_public_report_hides_private_content(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _record, _citation, _proposal, _binder, queue = _graph(root)
            workspace = build_revalidation_review_workspace(queue["queue_item_id"], root=root / "store")
            save_source_revalidation_resolution(queue["queue_item_id"], "resolved_no_change", _all_still_valid(workspace), review_note="private review note", root=root / "store")
            report = format_source_revalidation_resolution_report(queue["queue_item_id"], public_safe=True, root=root / "store")
            self.assertNotIn(str(root), report)
            self.assertNotIn("private review note", report)
            self.assertNotIn("Manual review source text", report)

    def test_api_revalidation_review_flow(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _record, _citation, _proposal, _binder, queue = _graph(root)
            workspace = api.build_revalidation_review_workspace(queue["queue_item_id"], root=root / "store")
            dispositions = _all_still_valid(workspace)
            result = api.finalize_source_revalidation_review(queue["queue_item_id"], "resolved_no_change", dispositions, review_note="done", root=root / "store")
            loaded = api.load_source_revalidation_resolution(queue["queue_item_id"], root=root / "store")
            listed = api.list_source_revalidation_resolutions(root=root / "store")
            report = api.format_source_revalidation_resolution_report(queue["queue_item_id"], root=root / "store")
            self.assertEqual(result["queue_item"]["status"], "reviewed")
            self.assertEqual(loaded["resolution"]["resolution_decision"], "resolved_no_change")
            self.assertEqual(listed["count"], 1)
            self.assertIn("Source Revalidation Resolution Report", report)
