from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.electional.source_documents import extract_pdf_text, register_pdf_source
from backend.electional.source_knowledge import chunk_extracted_text
from backend.electional.source_document_reader import (
    copy_snippet_from_selected_result,
    create_citation_from_selected_result,
    create_proposal_from_selected_result,
    get_search_ui_state,
    get_source_search_health,
    mark_selected_result_feedback,
    run_document_search_for_ui,
    select_search_result_for_ui,
)


def _document(root: Path, *, chunk: bool = True) -> str:
    pdf = root / "ui_reader.pdf"
    pdf.write_bytes(b"%PDF-1.4\nreader\n%%EOF")
    record = register_pdf_source(pdf, root=root / "store")
    pages = [
        "Mercury supports exam review. Manual review before citation is required.",
        "Jupiter supports legal doctrine and proposal notes.",
    ]
    extract_pdf_text(record.document_id, root=root / "store", extractor=lambda _path: (pages, 2))
    if chunk:
        chunk_extracted_text(record.document_id, root=root / "store")
    return record.document_id


class DocumentReaderSearchUiTest(unittest.TestCase):
    def test_search_ui_state_no_document(self) -> None:
        with TemporaryDirectory() as tmp:
            state = get_search_ui_state(root=Path(tmp) / "store")
            self.assertEqual(state["status"], "no_document")
            self.assertFalse(state["selected_actions"]["copy_snippet"])

    def test_search_ui_state_not_chunked(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _document(root, chunk=False)
            state = get_search_ui_state(document_id, root=root / "store")
            self.assertEqual(state["status"], "not_chunked")
            self.assertIn("not_chunked", state["warnings"])

    def test_search_results_selectable_and_clears_on_new_search(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _document(root)
            state = run_document_search_for_ui(document_id, "Mercury", root=root / "store")
            selected = select_search_result_for_ui(state, state["results"][0]["result_id"], root=root / "store")
            self.assertIsNotNone(selected["selected_result"])
            self.assertTrue(selected["selected_actions"]["create_citation"])
            next_state = run_document_search_for_ui(document_id, "Jupiter", root=root / "store")
            self.assertIsNone(next_state["selected_result"])

    def test_selected_result_context_and_copy_snippet(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _document(root)
            state = run_document_search_for_ui(document_id, "manual review", mode="exact_phrase", root=root / "store")
            selected = select_search_result_for_ui(state, state["results"][0]["result_id"], root=root / "store")
            snippet = copy_snippet_from_selected_result(selected)
            self.assertIn("Manual review", snippet)
            self.assertIn("context", selected["selected_result"])

    def test_create_proposal_requires_selected_result(self) -> None:
        with TemporaryDirectory() as tmp:
            state = get_search_ui_state(root=Path(tmp) / "store")
            with self.assertRaises(ValueError):
                create_proposal_from_selected_result(state, "No selected result.", root=Path(tmp) / "store")

    def test_create_proposal_and_citation_from_selected_result(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _document(root)
            state = run_document_search_for_ui(document_id, "citation", root=root / "store")
            selected = select_search_result_for_ui(state, state["results"][0]["result_id"], root=root / "store")
            proposal = create_proposal_from_selected_result(selected, "Citation workflow proposal.", root=root / "store")
            citation = create_citation_from_selected_result(selected, "Citation workflow note.", root=root / "store")
            self.assertEqual(proposal.status, "pending_review")
            self.assertIn("proposal_does_not_activate_rule", proposal.warnings)
            self.assertIn("citation_does_not_activate_rule", citation.warnings)
            self.assertFalse((root / "store" / "rules").exists())

    def test_feedback_requires_selected_result_and_records_feedback(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(ValueError):
                mark_selected_result_feedback({}, "useful", root=root / "store")
            document_id = _document(root)
            state = run_document_search_for_ui(document_id, "Mercury", root=root / "store")
            selected = select_search_result_for_ui(state, state["results"][0]["result_id"], root=root / "store")
            record = mark_selected_result_feedback(selected, "bad_extraction", root=root / "store")
            self.assertEqual(record["feedback"], "bad_extraction")
            self.assertTrue((root / "store" / "search_feedback" / f"{record['feedback_id']}.json").exists())

    def test_search_health_for_ui(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _document(root)
            health = get_source_search_health(document_id, root=root / "store")
            self.assertGreaterEqual(health.chunks_indexed, 1)
            self.assertIn(health.status, {"healthy", "warning"})


if __name__ == "__main__":
    unittest.main()
