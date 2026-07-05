from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.electional import api
from backend.electional.document_structure import build_document_structure_map
from backend.electional.evidence_binder import (
    build_evidence_binder,
    calculate_evidence_coverage,
    detect_cross_document_conflicts,
    detect_cross_document_support,
    detect_weak_or_stale_sources,
    format_evidence_binder_report_text,
    get_evidence_binder_summary,
    get_or_create_source_reliability,
    group_citations_for_proposal,
    score_citation_bundle_strength,
    update_source_reliability_metadata,
)
from backend.electional.source_documents import extract_pdf_text, register_pdf_source
from backend.electional.source_knowledge import chunk_extracted_text, create_manual_proposal, create_source_citation


def _doc(root: Path, name: str, text: str):
    pdf = root / f"{name}.pdf"
    pdf.write_bytes(f"%PDF-1.4\nevidence {name}\n%%EOF".encode("utf-8"))
    record = register_pdf_source(pdf, root=root / "store")
    extract_pdf_text(record.document_id, root=root / "store", extractor=lambda _path: ([text], 1))
    chunk = chunk_extracted_text(record.document_id, root=root / "store")[0]
    build_document_structure_map(record.document_id, root=root / "store")
    return record.document_id, chunk


class EvidenceBinderTest(unittest.TestCase):
    def test_group_citations_for_proposal_no_citations(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc, chunk = _doc(root, "a", "Allow source review when citation is strong.")
            proposal = create_manual_proposal(doc, chunk.chunk_id, "Allow source review.", root=root / "store")
            group = group_citations_for_proposal(proposal.proposal_id, root=root / "store")
            self.assertEqual(group["citation_count"], 0)
            self.assertIn("no_linked_citations", group["warnings"])

    def test_group_citations_for_proposal_with_citations(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc, chunk = _doc(root, "a", "Allow source review when citation is strong.")
            proposal = create_manual_proposal(doc, chunk.chunk_id, "Allow source review.", root=root / "store")
            create_source_citation(doc, chunk.chunk_id, "Citation.", quote_excerpt="Allow source review when citation is strong.", root=root / "store")
            group = group_citations_for_proposal(proposal.proposal_id, root=root / "store")
            self.assertEqual(group["citation_count"], 1)
            self.assertEqual(group["documents_count"], 1)

    def test_get_or_create_source_reliability(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc, _chunk = _doc(root, "a", "Allow source review.")
            rel = get_or_create_source_reliability(doc, root=root / "store")
            self.assertEqual(rel["reliability_band"], "unknown")
            self.assertTrue((root / "store" / "indexes" / "source_reliability_index.json").exists())

    def test_update_source_reliability_metadata(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc, _chunk = _doc(root, "a", "Allow source review.")
            rel = update_source_reliability_metadata(doc, {"source_type": "official_policy", "authority_level": "primary", "publication_date": "2026-01-01"}, root=root / "store")
            self.assertIn(rel["reliability_band"], {"usable", "strong"})
            self.assertEqual(rel["staleness_status"], "current")

    def test_score_citation_bundle_strength_no_citations_blocks(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc, chunk = _doc(root, "a", "Allow source review.")
            proposal = create_manual_proposal(doc, chunk.chunk_id, "Allow source review.", root=root / "store")
            score = score_citation_bundle_strength(proposal.proposal_id, root=root / "store")
            self.assertIn("no_linked_citations", score["blockers"])

    def test_score_citation_bundle_strength_usable(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc1, chunk1 = _doc(root, "a", "Allow source review when citation is strong.")
            doc2, chunk2 = _doc(root, "b", "Allow source review when citation is strong and documented.")
            proposal = create_manual_proposal(doc1, chunk1.chunk_id, "Allow source review.", root=root / "store")
            create_source_citation(doc1, chunk1.chunk_id, "Citation.", quote_excerpt="Allow source review when citation is strong.", root=root / "store")
            create_source_citation(doc2, chunk2.chunk_id, f"Citation for {proposal.proposal_id}.", quote_excerpt="Allow source review when citation is strong.", root=root / "store")
            update_source_reliability_metadata(doc1, {"source_type": "official_policy", "authority_level": "primary"}, root=root / "store")
            score = score_citation_bundle_strength(proposal.proposal_id, root=root / "store")
            self.assertIn(score["band"], {"usable", "strong"})
            self.assertEqual(score["unique_documents"], 2)

    def test_detect_cross_document_support(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc1, chunk1 = _doc(root, "a", "Allow source review when citation is strong.")
            doc2, chunk2 = _doc(root, "b", "Allow source review when citation is strong.")
            proposal = create_manual_proposal(doc1, chunk1.chunk_id, "Allow source review.", root=root / "store")
            create_source_citation(doc1, chunk1.chunk_id, "Citation.", quote_excerpt="Allow source review when citation is strong.", root=root / "store")
            create_source_citation(doc2, chunk2.chunk_id, f"Citation {proposal.proposal_id}.", quote_excerpt="Allow source review when citation is strong.", root=root / "store")
            support = detect_cross_document_support(proposal.proposal_id, root=root / "store")
            self.assertEqual(support["status"], "support_found")

    def test_detect_cross_document_conflicts(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc1, chunk1 = _doc(root, "a", "Allow source review when citation is strong.")
            doc2, chunk2 = _doc(root, "b", "Reject source review when citation is weak.")
            proposal = create_manual_proposal(doc1, chunk1.chunk_id, "Allow source review.", root=root / "store")
            create_source_citation(doc1, chunk1.chunk_id, "Citation.", quote_excerpt="Allow source review when citation is strong.", root=root / "store")
            create_source_citation(doc2, chunk2.chunk_id, f"Citation {proposal.proposal_id}.", quote_excerpt="Reject source review when citation is weak.", root=root / "store")
            conflict = detect_cross_document_conflicts(proposal.proposal_id, root=root / "store")
            self.assertEqual(conflict["status"], "possible_conflict")

    def test_calculate_evidence_coverage(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc, chunk = _doc(root, "a", "Allow source review when citation is strong.")
            proposal = create_manual_proposal(doc, chunk.chunk_id, "Allow source review.", root=root / "store")
            create_source_citation(doc, chunk.chunk_id, "Citation.", quote_excerpt="Allow source review when citation is strong.", root=root / "store")
            coverage = calculate_evidence_coverage(proposal.proposal_id, root=root / "store")
            self.assertTrue(coverage["has_citation"])
            self.assertIn(coverage["coverage_band"], {"weak", "partial", "good", "complete"})

    def test_detect_weak_or_stale_sources_unknown_date(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc, chunk = _doc(root, "a", "Allow source review.")
            proposal = create_manual_proposal(doc, chunk.chunk_id, "Allow source review.", root=root / "store")
            create_source_citation(doc, chunk.chunk_id, "Citation.", quote_excerpt="Allow source review.", root=root / "store")
            weak = detect_weak_or_stale_sources(proposal.proposal_id, root=root / "store")
            self.assertEqual(weak["status"], "warning")
            self.assertTrue(weak["weak_sources"])

    def test_build_evidence_binder_no_proposal_blocks(self) -> None:
        with TemporaryDirectory() as tmp:
            binder = build_evidence_binder("proposal_missing", root=Path(tmp) / "store")
            self.assertIn("proposal_not_found", binder["blockers"])

    def test_build_evidence_binder_no_citations_blocks(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc, chunk = _doc(root, "a", "Allow source review.")
            proposal = create_manual_proposal(doc, chunk.chunk_id, "Allow source review.", root=root / "store")
            binder = build_evidence_binder(proposal.proposal_id, root=root / "store")
            self.assertIn("no_linked_citations", binder["blockers"])

    def test_build_evidence_binder_with_evidence(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc, chunk = _doc(root, "a", "Allow source review.")
            proposal = create_manual_proposal(doc, chunk.chunk_id, "Allow source review.", root=root / "store")
            create_source_citation(doc, chunk.chunk_id, "Citation.", quote_excerpt="Allow source review.", root=root / "store")
            binder = build_evidence_binder(proposal.proposal_id, root=root / "store")
            self.assertEqual(len(binder["linked_citations"]), 1)
            self.assertTrue((root / "store" / "indexes" / "evidence_binder_index.json").exists())

    def test_get_evidence_binder_summary(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc, chunk = _doc(root, "a", "Allow source review.")
            proposal = create_manual_proposal(doc, chunk.chunk_id, "Allow source review.", root=root / "store")
            create_source_citation(doc, chunk.chunk_id, "Citation.", quote_excerpt="Allow source review.", root=root / "store")
            build_evidence_binder(proposal.proposal_id, root=root / "store")
            summary = get_evidence_binder_summary(proposal.proposal_id, root=root / "store")
            self.assertEqual(summary["citation_count"], 1)

    def test_format_evidence_binder_report_text_public_safe(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc, chunk = _doc(root, "a", "Allow source review person@example.com C:/private/source.pdf.")
            proposal = create_manual_proposal(doc, chunk.chunk_id, "Allow source review person@example.com C:/private/source.pdf.", root=root / "store")
            create_source_citation(doc, chunk.chunk_id, "Citation.", quote_excerpt="Allow source review person@example.com C:/private/source.pdf.", root=root / "store")
            report = format_evidence_binder_report_text(proposal.proposal_id, root=root / "store")
            self.assertIn("Evidence Binder Report", report)
            self.assertNotIn("person@example.com", report)
            self.assertNotIn("C:/private/source.pdf", report)

    def test_api_evidence_binder_flow(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc, chunk = _doc(root, "a", "Allow source review.")
            proposal = create_manual_proposal(doc, chunk.chunk_id, "Allow source review.", root=root / "store")
            create_source_citation(doc, chunk.chunk_id, "Citation.", quote_excerpt="Allow source review.", root=root / "store")
            binder = api.build_evidence_binder(proposal.proposal_id, root=root / "store")
            summary = api.get_evidence_binder_summary(proposal.proposal_id, root=root / "store")
            self.assertEqual(binder["proposal_id"], proposal.proposal_id)
            self.assertEqual(summary["citation_count"], 1)


if __name__ == "__main__":
    unittest.main()
