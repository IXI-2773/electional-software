from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.electional import api
from backend.electional.document_preflight import run_document_preflight
from backend.electional.proposal_review import (
    add_proposal_review_note,
    calculate_promotion_readiness,
    detect_duplicate_proposals,
    detect_proposal_conflicts,
    get_proposal_review_summary,
    list_proposal_review_queue,
    score_citation_strength,
    update_proposal_review_status,
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
        self.metadata = {"title": "Proposal Review"}


def _source(root: Path):
    pdf = root / "review.pdf"
    pdf.write_bytes(b"%PDF-1.4\nreview\n%%EOF")
    record = register_pdf_source(pdf, root=root / "store")
    pages = ["Allow Mercury proposal when citation is strong and review is complete."]
    run_document_preflight(record.document_id, root=root / "store", reader_factory=lambda _path: FakeReader(pages))
    extract_pdf_text(record.document_id, root=root / "store", extractor=lambda _path: (pages, 1))
    chunk = chunk_extracted_text(record.document_id, root=root / "store")[0]
    return record.document_id, chunk


class ProposalReviewQueueTest(unittest.TestCase):
    def test_score_citation_strength_no_citation_blocks(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, chunk = _source(root)
            proposal = create_manual_proposal(document_id, chunk.chunk_id, "Allow Mercury proposal.", root=root / "store")
            strength = score_citation_strength(proposal.proposal_id, root=root / "store")
            self.assertEqual(strength["band"], "unusable")
            self.assertIn("no_citation", strength["blockers"])

    def test_score_citation_strength_usable(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, chunk = _source(root)
            proposal = create_manual_proposal(document_id, chunk.chunk_id, "Allow Mercury proposal.", root=root / "store")
            create_source_citation(document_id, chunk.chunk_id, "Strong citation.", quote_excerpt="Allow Mercury proposal when citation is strong.", root=root / "store")
            strength = score_citation_strength(proposal.proposal_id, root=root / "store")
            self.assertIn(strength["band"], {"usable", "strong"})
            self.assertIn("citation_links_document", strength["strengths"])

    def test_get_proposal_review_summary(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, chunk = _source(root)
            proposal = create_manual_proposal(document_id, chunk.chunk_id, "Allow Mercury proposal.", root=root / "store")
            summary = get_proposal_review_summary(proposal.proposal_id, root=root / "store")
            self.assertEqual(summary["proposal_id"], proposal.proposal_id)
            self.assertIn("claim_preview", summary)

    def test_detect_duplicate_proposals_same_claim_and_chunk(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, chunk = _source(root)
            first = create_manual_proposal(document_id, chunk.chunk_id, "Allow Mercury proposal.", root=root / "store")
            create_manual_proposal(document_id, chunk.chunk_id, "Allow Mercury proposal!", root=root / "store")
            duplicate = detect_duplicate_proposals(first.proposal_id, root=root / "store")
            self.assertEqual(duplicate["status"], "possible_duplicate")
            self.assertTrue(duplicate["matches"])
            self.assertTrue((root / "store" / "indexes" / "proposal_duplicate_index.json").exists())

    def test_detect_proposal_conflicts_opposite_decision_words(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, chunk = _source(root)
            allow = create_manual_proposal(document_id, chunk.chunk_id, "Allow Mercury review when citation is strong.", root=root / "store")
            create_manual_proposal(document_id, chunk.chunk_id, "Reject Mercury review when citation is weak.", root=root / "store")
            conflict = detect_proposal_conflicts(allow.proposal_id, root=root / "store")
            self.assertEqual(conflict["status"], "possible_conflict")
            self.assertTrue(conflict["matches"])

    def test_update_proposal_review_status_and_note(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, chunk = _source(root)
            proposal = create_manual_proposal(document_id, chunk.chunk_id, "Allow Mercury proposal.", root=root / "store")
            review = update_proposal_review_status(proposal.proposal_id, "in_review", "not_decided", "Checking source.", root=root / "store")
            review = add_proposal_review_note(proposal.proposal_id, "Needs stronger citation.", "citation_issue", root=root / "store")
            self.assertEqual(review.review_status, "in_review")
            self.assertEqual(len(review.review_notes), 2)
            self.assertTrue((root / "store" / "indexes" / "proposal_review_index.json").exists())

    def test_calculate_promotion_readiness_blocks_unresolved_conflict(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, chunk = _source(root)
            proposal = create_manual_proposal(document_id, chunk.chunk_id, "Allow Mercury review when citation is strong.", root=root / "store")
            create_manual_proposal(document_id, chunk.chunk_id, "Reject Mercury review when citation is weak.", root=root / "store")
            readiness = calculate_promotion_readiness(proposal.proposal_id, root=root / "store")
            self.assertFalse(readiness["ready_for_promotion_review"])
            self.assertIn("possible_conflict_unresolved", readiness["blockers"])

    def test_calculate_promotion_readiness_ready(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, chunk = _source(root)
            proposal = create_manual_proposal(document_id, chunk.chunk_id, "Proceed with Mercury source review.", root=root / "store")
            create_source_citation(document_id, chunk.chunk_id, "Strong citation.", quote_excerpt="Allow Mercury proposal when citation is strong.", root=root / "store")
            update_proposal_review_status(proposal.proposal_id, "approved_for_later_promotion", "approve", "Human reviewed.", root=root / "store")
            readiness = calculate_promotion_readiness(proposal.proposal_id, root=root / "store")
            self.assertTrue(readiness["ready_for_promotion_review"])
            self.assertFalse((root / "store" / "rules").exists())

    def test_list_proposal_review_queue(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, chunk = _source(root)
            create_manual_proposal(document_id, chunk.chunk_id, "Allow Mercury proposal!", root=root / "store")
            queue = list_proposal_review_queue(root=root / "store")
            self.assertEqual(len(queue), 1)
            self.assertIn("promotion_readiness_band", queue[0])

    def test_api_proposal_review_flow(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, chunk = _source(root)
            proposal = create_manual_proposal(document_id, chunk.chunk_id, "Allow Mercury proposal.", root=root / "store")
            create_source_citation(document_id, chunk.chunk_id, "Citation.", quote_excerpt="Allow Mercury proposal.", root=root / "store")
            strength = api.score_citation_strength(proposal.proposal_id, root=root / "store")
            review = api.update_proposal_review_status(proposal.proposal_id, "in_review", "not_decided", "API review.", root=root / "store")
            queue = api.list_proposal_review_queue(root=root / "store")
            self.assertGreater(strength["score"], 0)
            self.assertEqual(review.review_status, "in_review")
            self.assertTrue(queue)


if __name__ == "__main__":
    unittest.main()

