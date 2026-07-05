from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.electional import api
from backend.electional.document_preflight import run_document_preflight, format_preflight_report_text
from backend.electional.source_documents import extract_pdf_text, register_pdf_source
from backend.electional.source_knowledge import chunk_extracted_text
from backend.electional.source_document_reader import (
    build_citation_snippet,
    build_page_diagnostics,
    create_citation_from_search_result,
    create_proposal_from_search_result,
    get_document_chunk_text,
    get_document_page_text,
    get_document_reader_state,
    get_page_diagnostic_summary,
    get_source_search_health,
    list_document_chunks,
    search_document,
)


class FakePage:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self) -> str:
        return self.text


class FakeReader:
    def __init__(self, pages: list[str], *, metadata: dict[str, str] | None = None) -> None:
        self.pages = [FakePage(page) for page in pages]
        self.is_encrypted = False
        self.metadata = metadata or {"title": "Reader Test"}


def _document(root: Path) -> str:
    pdf = root / "reader.pdf"
    pdf.write_bytes(b"%PDF-1.4\nreader\n%%EOF")
    record = register_pdf_source(pdf, root=root / "store")
    pages = [
        "Mercury supports exams and manual review. hard gate confidence citation.",
        "Jupiter supports legal doctrine. Manual review is required before proposal creation.",
        "Low",
    ]
    run_document_preflight(record.document_id, root=root / "store", reader_factory=lambda _path: FakeReader(pages))
    extract_pdf_text(record.document_id, root=root / "store", extractor=lambda _path: (pages, 3))
    chunk_extracted_text(record.document_id, root=root / "store")
    return record.document_id


class DocumentReaderSearchTest(unittest.TestCase):
    def test_page_diagnostics_summary(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _document(root)
            diagnostics = build_page_diagnostics(document_id, root=root / "store")
            summary = get_page_diagnostic_summary(document_id, root=root / "store")
            self.assertEqual(len(diagnostics), 3)
            self.assertEqual(summary["pages_diagnosed"], 3)
            self.assertGreaterEqual(summary["low_quality_pages"], 1)
            self.assertTrue((root / "store" / "indexes" / "page_diagnostics_index.json").exists())

    def test_document_reader_state_and_chunks(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _document(root)
            build_page_diagnostics(document_id, root=root / "store")
            state = get_document_reader_state(document_id, root=root / "store")
            chunks = list_document_chunks(document_id, root=root / "store")
            text = get_document_chunk_text(str(chunks[0]["chunk_id"]), root=root / "store")
            self.assertTrue(state["has_extracted_text"])
            self.assertTrue(state["has_chunks"])
            self.assertTrue(state["has_page_diagnostics"])
            self.assertNotIn("stored_pdf_path", str(state))
            self.assertIn("Mercury", text["text"])

    def test_get_document_page_text_unavailable_warning(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = get_document_page_text("missing", 1, root=root / "store")
            self.assertEqual(result["text"], "")
            self.assertTrue(result["warnings"])

    def test_search_document_modes_and_page_filter(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _document(root)
            keyword = search_document("Mercury", document_id=document_id, root=root / "store")
            phrase = search_document("manual review", document_id=document_id, mode="exact_phrase", root=root / "store")
            all_terms = search_document("Jupiter doctrine", document_id=document_id, mode="all_terms", root=root / "store")
            any_terms = search_document("Mercury Saturn", document_id=document_id, mode="any_terms", root=root / "store")
            page = search_document("Mercury", document_id=document_id, page_start=1, page_end=1, root=root / "store")
            blank = search_document("", root=root / "store")
            self.assertTrue(keyword)
            self.assertTrue(phrase)
            self.assertTrue(all_terms)
            self.assertTrue(any_terms)
            self.assertTrue(page)
            self.assertEqual(blank, [])

    def test_search_document_limit_and_deterministic_sort(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _document(root)
            results = search_document("manual review", document_id=document_id, limit=1, root=root / "store")
            again = search_document("manual review", document_id=document_id, limit=1, root=root / "store")
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].result_id, again[0].result_id)

    def test_search_result_actions(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _document(root)
            result = search_document("Mercury", document_id=document_id, root=root / "store")[0]
            proposal = create_proposal_from_search_result(result, "Mercury exam testimony.", root=root / "store")
            citation = create_citation_from_search_result(result, "Mercury citation.", root=root / "store")
            self.assertEqual(proposal.status, "pending_review")
            self.assertIn("proposal_does_not_activate_rule", proposal.warnings)
            self.assertIn("citation_does_not_activate_rule", citation.warnings)
            self.assertFalse((root / "store" / "rules").exists())

    def test_build_citation_snippet_redacts_and_truncates(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _document(root)
            text_path = root / "store" / "extracted_text" / f"{document_id}.txt"
            text_path.write_text("--- Page 1 ---\nEmail person@example.com C:\\Users\\Name\\file.pdf " + "Mercury " * 100, encoding="utf-8")
            chunk = chunk_extracted_text(document_id, root=root / "store", regenerate=True)[0]
            snippet = build_citation_snippet(document_id, chunk.chunk_id, query="Mercury", max_chars=80, root=root / "store")
            self.assertLessEqual(len(snippet["excerpt"]), 80)
            self.assertNotIn("person@example.com", snippet["excerpt"])
            self.assertNotIn("C:\\Users\\Name", snippet["excerpt"])
            self.assertEqual(snippet["page_start"], 1)

    def test_source_search_health(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _document(root)
            result = search_document("Mercury", document_id=document_id, root=root / "store")[0]
            create_proposal_from_search_result(result, "Health proposal.", root=root / "store")
            create_citation_from_search_result(result, "Health citation.", root=root / "store")
            health = get_source_search_health(document_id, root=root / "store")
            self.assertEqual(health.documents, 1)
            self.assertGreaterEqual(health.chunks_indexed, 1)
            self.assertEqual(health.proposals_linked, 1)
            self.assertEqual(health.citations_linked, 1)

    def test_api_document_reader_search_flow(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _document(root)
            diagnostics = api.build_page_diagnostics(document_id, root=root / "store")
            state = api.get_document_reader_state(document_id, root=root / "store")
            results = api.search_document("confidence", document_id=document_id, root=root / "store")
            snippet = api.build_citation_snippet(document_id, results[0].chunk_id, query="confidence", root=root / "store")
            report = format_preflight_report_text(document_id, root=root / "store")
            self.assertTrue(diagnostics)
            self.assertTrue(state["has_chunks"])
            self.assertTrue(results)
            self.assertIn("excerpt", snippet)
            self.assertIn("Low-density pages", report)


if __name__ == "__main__":
    unittest.main()
