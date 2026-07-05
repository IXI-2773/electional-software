from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.electional import api
from backend.electional.document_preflight import run_document_preflight
from backend.electional.proposal_review import (
    add_proposal_review_note,
    apply_proposal_review_ui_action,
    copy_proposal_review_summary,
    get_proposal_review_ui_state,
    select_proposal_for_review_ui,
)
from backend.electional.source_documents import extract_pdf_text, register_pdf_source
from backend.electional.source_knowledge import chunk_extracted_text, create_manual_proposal, create_source_citation


class FakePage:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self) -> str:
        return self.text


class FakeReader:
    def __init__(self, pages: list[str]) -> None:
        self.pages = [FakePage(page) for page in pages]
        self.is_encrypted = False
        self.metadata = {"title": "Proposal Dashboard"}


def _source(root: Path):
    pdf = root / "dashboard.pdf"
    pdf.write_bytes(b"%PDF-1.4\ndashboard\n%%EOF")
    record = register_pdf_source(pdf, root=root / "store")
    pages = ["Allow Mercury dashboard review when citation is strong and manual review is complete."]
    run_document_preflight(record.document_id, root=root / "store", reader_factory=lambda _path: FakeReader(pages))
    extract_pdf_text(record.document_id, root=root / "store", extractor=lambda _path: (pages, 1))
    chunk = chunk_extracted_text(record.document_id, root=root / "store")[0]
    return record.document_id, chunk


class ProposalReviewDashboardUiTest(unittest.TestCase):
    def test_proposal_review_ui_state_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            state = get_proposal_review_ui_state(root=Path(tmp) / "store")
            self.assertEqual(state["queue_count"], 0)
            self.assertIn("no_proposals_match_current_filters", state["warnings"])

    def test_proposal_review_ui_state_filters(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, chunk = _source(root)
            proposal = create_manual_proposal(document_id, chunk.chunk_id, "Allow Mercury dashboard review.", root=root / "store")
            create_source_citation(document_id, chunk.chunk_id, "Citation.", quote_excerpt="Allow Mercury dashboard review.", root=root / "store")
            apply_proposal_review_ui_action(proposal.proposal_id, "approve_for_later_promotion", "Human reviewed.", root=root / "store")
            state = get_proposal_review_ui_state(status="approved_for_later_promotion", readiness_band="review_ready", root=root / "store")
            self.assertEqual(state["queue_count"], 1)
            self.assertEqual(state["items"][0]["proposal_id"], proposal.proposal_id)

    def test_select_proposal_for_review_ui(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, chunk = _source(root)
            proposal = create_manual_proposal(document_id, chunk.chunk_id, "Allow Mercury dashboard review.", root=root / "store")
            selected = select_proposal_for_review_ui(proposal.proposal_id, root=root / "store")
            self.assertTrue(selected["selected"])
            self.assertIn("citation_strength", selected)
            self.assertIn("approve_for_later_promotion", selected["available_actions"])

    def test_select_missing_proposal_returns_clean_state(self) -> None:
        with TemporaryDirectory() as tmp:
            selected = select_proposal_for_review_ui("proposal_missing", root=Path(tmp) / "store")
            self.assertFalse(selected["selected"])
            self.assertIn("proposal_not_found", selected["warnings"])

    def test_review_action_requires_selected_proposal(self) -> None:
        with TemporaryDirectory() as tmp:
            selected = apply_proposal_review_ui_action(None, "reject", root=Path(tmp) / "store")
            self.assertFalse(selected["selected"])
            self.assertIn("no_proposal_selected", selected["warnings"])

    def test_add_review_note_from_ui(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, chunk = _source(root)
            proposal = create_manual_proposal(document_id, chunk.chunk_id, "Allow Mercury dashboard review.", root=root / "store")
            add_proposal_review_note(proposal.proposal_id, "Needs stronger citation.", root=root / "store")
            selected = select_proposal_for_review_ui(proposal.proposal_id, root=root / "store")
            self.assertEqual(len(selected["review_notes"]), 1)

    def test_update_review_status_from_ui(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, chunk = _source(root)
            proposal = create_manual_proposal(document_id, chunk.chunk_id, "Allow Mercury dashboard review.", root=root / "store")
            selected = apply_proposal_review_ui_action(proposal.proposal_id, "needs_more_source", "Find another source.", root=root / "store")
            self.assertEqual(selected["review_status"], "needs_more_source")
            self.assertEqual(selected["review_notes"][-1]["note_type"], "review_decision")

    def test_approve_for_later_promotion_does_not_promote(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, chunk = _source(root)
            proposal = create_manual_proposal(document_id, chunk.chunk_id, "Proceed with Mercury dashboard review.", root=root / "store")
            create_source_citation(document_id, chunk.chunk_id, "Citation.", quote_excerpt="Proceed with Mercury dashboard review.", root=root / "store")
            selected = apply_proposal_review_ui_action(proposal.proposal_id, "approve_for_later_promotion", root=root / "store")
            self.assertEqual(selected["review_status"], "approved_for_later_promotion")
            self.assertFalse((root / "store" / "rules").exists())

    def test_copy_review_summary_hides_private_values(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, chunk = _source(root)
            proposal = create_manual_proposal(document_id, chunk.chunk_id, "Contact person@example.com from C:/private/source.pdf.", root=root / "store")
            add_proposal_review_note(proposal.proposal_id, "Private note: token abc123", root=root / "store")
            summary = copy_proposal_review_summary(proposal.proposal_id, root=root / "store")
            self.assertIn("Review Note Count: 1", summary)
            self.assertNotIn("person@example.com", summary)
            self.assertNotIn("C:/private/source.pdf", summary)
            self.assertNotIn("abc123", summary)

    def test_queue_filters_no_results_state(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, chunk = _source(root)
            create_manual_proposal(document_id, chunk.chunk_id, "Allow Mercury dashboard review.", root=root / "store")
            state = get_proposal_review_ui_state(status="rejected", root=root / "store")
            self.assertEqual(state["queue_count"], 0)
            self.assertIn("no_proposals_match_current_filters", state["warnings"])

    def test_api_proposal_review_dashboard_helpers(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, chunk = _source(root)
            proposal = create_manual_proposal(document_id, chunk.chunk_id, "Allow Mercury dashboard review.", root=root / "store")
            state = api.get_proposal_review_ui_state(root=root / "store")
            selected = api.select_proposal_for_review_ui(proposal.proposal_id, root=root / "store")
            copied = api.copy_proposal_review_summary(proposal.proposal_id, root=root / "store")
            self.assertEqual(state["queue_count"], 1)
            self.assertTrue(selected["selected"])
            self.assertIn("Proposal Review Summary", copied)


if __name__ == "__main__":
    unittest.main()
