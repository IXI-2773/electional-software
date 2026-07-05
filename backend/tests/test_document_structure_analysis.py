from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.electional import api
from backend.electional.document_structure import (
    analyze_chunk_quality,
    build_document_structure_map,
    detect_document_headings,
    detect_footnotes_and_references,
    detect_possible_figures,
    detect_possible_tables,
    detect_repeated_headers_footers,
    detect_toc_candidates,
    get_document_structure_summary,
    normalize_extracted_page_text,
    recommend_rechunk_plan,
)
from backend.electional.source_documents import extract_pdf_text, register_pdf_source
from backend.electional.source_knowledge import chunk_extracted_text


PAGES = [
    "Document Policy\nTable of Contents\nIntroduction ........ 2\nTables ........ 3\nDocument Policy Footer 1",
    "Document Policy\n1 Introduction\nThis document explains manual review and citation controls. The policy requires review before promotion.\nDocument Policy Footer 2",
    "Document Policy\n2 Tables\nColumn A   Column B   Column C\nMars   10   20\nVenus   30   40\nJupiter   50   60\nFigure 1: Example review chart\n1 First footnote near the bottom\n2 Second footnote near the bottom\nDocument Policy Footer 3",
    "Document Policy\nReferences\nSmith 2020. Source list.\nhttps://example.com/a\nhttps://example.com/b\nhttps://example.com/c\nDocument Policy Footer 4",
]


def _source(root: Path):
    pdf = root / "structure.pdf"
    pdf.write_bytes(b"%PDF-1.4\nstructure\n%%EOF")
    record = register_pdf_source(pdf, root=root / "store")
    extract_pdf_text(record.document_id, root=root / "store", extractor=lambda _path: (PAGES, len(PAGES)))
    chunks = chunk_extracted_text(record.document_id, root=root / "store")
    return record.document_id, chunks


class DocumentStructureAnalysisTest(unittest.TestCase):
    def test_normalize_extracted_page_text(self) -> None:
        with TemporaryDirectory() as tmp:
            document_id, _chunks = _source(Path(tmp))
            cleaned = normalize_extracted_page_text(document_id, root=Path(tmp) / "store")
            self.assertEqual(cleaned["pages_cleaned"], 4)
            self.assertIn("collapsed_whitespace", cleaned["cleanup_actions"])

    def test_detect_repeated_headers_footers(self) -> None:
        with TemporaryDirectory() as tmp:
            document_id, _chunks = _source(Path(tmp))
            normalize_extracted_page_text(document_id, root=Path(tmp) / "store")
            result = detect_repeated_headers_footers(document_id, root=Path(tmp) / "store")
            self.assertTrue(result["header_candidates"])
            self.assertIn("Document Policy", result["header_candidates"][0]["text_preview"])

    def test_detect_document_headings(self) -> None:
        with TemporaryDirectory() as tmp:
            document_id, _chunks = _source(Path(tmp))
            result = detect_document_headings(document_id, root=Path(tmp) / "store")
            titles = [item["title"] for item in result["headings"]]
            self.assertIn("1 Introduction", titles)
            self.assertIn("References", titles)

    def test_detect_toc_candidates(self) -> None:
        with TemporaryDirectory() as tmp:
            document_id, _chunks = _source(Path(tmp))
            result = detect_toc_candidates(document_id, root=Path(tmp) / "store")
            self.assertTrue(result["toc_found"])
            self.assertTrue(result["entries"])

    def test_detect_possible_tables(self) -> None:
        with TemporaryDirectory() as tmp:
            document_id, _chunks = _source(Path(tmp))
            result = detect_possible_tables(document_id, root=Path(tmp) / "store")
            self.assertTrue(result["tables"])
            self.assertEqual(result["tables"][0]["kind"], "possible_table")

    def test_detect_possible_figures(self) -> None:
        with TemporaryDirectory() as tmp:
            document_id, _chunks = _source(Path(tmp))
            result = detect_possible_figures(document_id, root=Path(tmp) / "store")
            self.assertTrue(result["figures"])

    def test_detect_footnotes_and_references(self) -> None:
        with TemporaryDirectory() as tmp:
            document_id, _chunks = _source(Path(tmp))
            result = detect_footnotes_and_references(document_id, root=Path(tmp) / "store")
            self.assertTrue(result["footnotes"])
            self.assertTrue(result["references"]["found"])

    def test_build_document_structure_map(self) -> None:
        with TemporaryDirectory() as tmp:
            document_id, _chunks = _source(Path(tmp))
            structure = build_document_structure_map(document_id, root=Path(tmp) / "store")
            self.assertTrue(structure["headings"])
            self.assertTrue(structure["sections"])
            self.assertTrue((Path(tmp) / "store" / "indexes" / "structure_map_index.json").exists())

    def test_get_document_structure_summary(self) -> None:
        with TemporaryDirectory() as tmp:
            document_id, _chunks = _source(Path(tmp))
            build_document_structure_map(document_id, root=Path(tmp) / "store")
            summary = get_document_structure_summary(document_id, root=Path(tmp) / "store")
            self.assertEqual(summary["status"], "built")
            self.assertGreater(summary["headings"], 0)

    def test_analyze_chunk_quality(self) -> None:
        with TemporaryDirectory() as tmp:
            document_id, _chunks = _source(Path(tmp))
            quality = analyze_chunk_quality(document_id, root=Path(tmp) / "store")
            self.assertGreater(quality["chunk_count"], 0)
            self.assertIn(quality["quality_status"], {"healthy", "warning", "critical"})

    def test_recommend_rechunk_plan(self) -> None:
        with TemporaryDirectory() as tmp:
            document_id, _chunks = _source(Path(tmp))
            plan = recommend_rechunk_plan(document_id, root=Path(tmp) / "store")
            self.assertIn(plan["strategy"], {"keep_existing", "section_aware_chunking", "page_aware_chunking", "paragraph_aware_chunking", "manual_review_required"})
            self.assertFalse((Path(tmp) / "store" / "chunks_old_deleted").exists())

    def test_api_document_structure_flow(self) -> None:
        with TemporaryDirectory() as tmp:
            document_id, _chunks = _source(Path(tmp))
            structure = api.build_document_structure_map(document_id, root=Path(tmp) / "store")
            summary = api.get_document_structure_summary(document_id, root=Path(tmp) / "store")
            quality = api.analyze_chunk_quality(document_id, root=Path(tmp) / "store")
            self.assertTrue(structure["headings"])
            self.assertEqual(summary["document_id"], document_id)
            self.assertGreater(quality["chunk_count"], 0)

    def test_structure_summary_does_not_expose_paths(self) -> None:
        with TemporaryDirectory() as tmp:
            document_id, _chunks = _source(Path(tmp))
            build_document_structure_map(document_id, root=Path(tmp) / "store")
            summary = get_document_structure_summary(document_id, root=Path(tmp) / "store")
            text = str(summary)
            self.assertNotIn(str(Path(tmp)), text)
            self.assertNotIn("structure.pdf", text)


if __name__ == "__main__":
    unittest.main()
