from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.electional import api
from backend.electional.source_documents import extract_pdf_text, register_pdf_source
from backend.electional.source_knowledge import (
    chunk_extracted_text,
    create_manual_proposal,
    create_source_citation,
    get_source_knowledge_health,
    list_source_proposals,
    search_source_chunks,
    update_proposal_status,
)


def _extracted_document(root: Path) -> str:
    pdf = root / "source.pdf"
    pdf.write_bytes(b"%PDF-1.4\nsource text\n%%EOF")
    record = register_pdf_source(pdf, root=root / "store")
    extract_pdf_text(
        record.document_id,
        root=root / "store",
        extractor=lambda _path: (
            [
                "Mercury supports exams and messages.\n\nJupiter supports legal doctrine.",
                "Saturn supports discipline. Mercury appears again in exam testimony.",
            ],
            2,
        ),
    )
    return record.document_id


class PdfSourceKnowledgeLayerTest(unittest.TestCase):
    def test_chunk_extracted_text(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _extracted_document(root)

            chunks = chunk_extracted_text(document_id, root=root / "store")

            self.assertTrue(chunks)
            self.assertEqual(chunks[0].document_id, document_id)
            self.assertTrue(chunks[0].chunk_id.startswith(f"chunk_{document_id}_"))
            self.assertTrue((root / "store" / "indexes" / "chunk_index.json").exists())

    def test_chunk_rejects_unextracted_document(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "source.pdf"
            pdf.write_bytes(b"%PDF-1.4\nsource text\n%%EOF")
            record = register_pdf_source(pdf, root=root / "store")

            self.assertEqual(chunk_extracted_text(record.document_id, root=root / "store"), [])

    def test_chunk_returns_existing_without_regenerate_and_regenerates_when_requested(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _extracted_document(root)
            first = chunk_extracted_text(document_id, root=root / "store")
            text_path = root / "store" / "extracted_text" / f"{document_id}.txt"
            text_path.write_text("--- Page 1 ---\nVenus replaces Mercury in this version.\n", encoding="utf-8")

            existing = chunk_extracted_text(document_id, root=root / "store")
            regenerated = chunk_extracted_text(document_id, root=root / "store", regenerate=True)

            self.assertEqual(existing[0].text, first[0].text)
            self.assertIn("Venus replaces Mercury", regenerated[0].text)

    def test_search_source_chunks_keyword_document_filter_and_limit(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _extracted_document(root)
            chunk_extracted_text(document_id, root=root / "store")

            results = search_source_chunks("Mercury", document_id=document_id, limit=1, root=root / "store")
            blank = search_source_chunks("", root=root / "store")

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].document_id, document_id)
            self.assertIn("Mercury", results[0].snippet)
            self.assertEqual(blank, [])

    def test_create_manual_proposal_status_update_and_filters(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _extracted_document(root)
            chunk = chunk_extracted_text(document_id, root=root / "store")[0]

            proposal = create_manual_proposal(document_id, chunk.chunk_id, "Mercury is important for exam testimony.", root=root / "store")
            approved = update_proposal_status(proposal.proposal_id, "approved", root=root / "store")
            approved_items = list_source_proposals(status="approved", root=root / "store")

            self.assertEqual(approved.status, "approved")
            self.assertEqual(len(approved_items), 1)
            self.assertIn("proposal_does_not_activate_rule", approved.warnings)
            self.assertFalse((root / "store" / "rules").exists())

    def test_proposal_requires_valid_chunk(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)

            with self.assertRaises(FileNotFoundError):
                create_manual_proposal("missing", "chunk_missing_0001", "No chunk.", root=root / "store")

    def test_create_source_citation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _extracted_document(root)
            chunk = chunk_extracted_text(document_id, root=root / "store")[0]

            citation = create_source_citation(document_id, chunk.chunk_id, "Exam testimony note.", quote_excerpt="Mercury supports exams.", root=root / "store")

            self.assertEqual(citation.document_id, document_id)
            self.assertEqual(citation.chunk_id, chunk.chunk_id)
            self.assertIn("citation_does_not_activate_rule", citation.warnings)
            self.assertTrue((root / "store" / "indexes" / "citation_index.json").exists())

    def test_citation_requires_valid_chunk(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)

            with self.assertRaises(FileNotFoundError):
                create_source_citation("missing", "chunk_missing_0001", "No chunk.", root=root / "store")

    def test_source_knowledge_health(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _extracted_document(root)
            chunk = chunk_extracted_text(document_id, root=root / "store")[0]
            proposal = create_manual_proposal(document_id, chunk.chunk_id, "Pending note.", root=root / "store")
            create_source_citation(document_id, chunk.chunk_id, "Citation note.", root=root / "store")
            update_proposal_status(proposal.proposal_id, "rejected", root=root / "store")

            health = get_source_knowledge_health(root=root / "store")

            self.assertEqual(health.documents, 1)
            self.assertEqual(health.chunks, 1)
            self.assertEqual(health.proposals_rejected, 1)
            self.assertEqual(health.citations, 1)

    def test_api_source_knowledge_flow(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _extracted_document(root)

            chunks = api.chunk_source_document(document_id, root=root / "store")
            results = api.search_source_chunks("Jupiter", root=root / "store")
            proposal = api.create_manual_source_proposal(document_id, chunks[0].chunk_id, "Jupiter legal note.", root=root / "store")
            citation = api.create_source_citation(document_id, chunks[0].chunk_id, "Jupiter citation.", root=root / "store")
            health = api.get_source_knowledge_health(root=root / "store")

            self.assertTrue(results)
            self.assertEqual(proposal.document_id, document_id)
            self.assertEqual(citation.document_id, document_id)
            self.assertEqual(health.chunks, 1)


if __name__ == "__main__":
    unittest.main()
