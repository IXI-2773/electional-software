from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.electional.source_documents import (
    STATUS_EXTRACTED,
    STATUS_EXTRACTOR_UNAVAILABLE,
    STATUS_NEEDS_OCR,
    extract_pdf_text,
    get_extracted_text,
    list_source_documents,
    register_pdf_source,
    source_document_public_json,
)


class PdfSourceIntakeTest(unittest.TestCase):
    def test_register_pdf_source_metadata_index_and_duplicate_hash(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "source.pdf"
            pdf.write_bytes(b"%PDF-1.4\nsource text\n%%EOF")

            first = register_pdf_source(pdf, root=root / "store")
            second = register_pdf_source(pdf, root=root / "store")

            self.assertEqual(first.document_id, second.document_id)
            self.assertEqual(first.original_filename, "source.pdf")
            self.assertEqual(first.privacy_level, "private_local")
            self.assertTrue((root / "store" / "indexes" / "source_document_index.json").exists())
            self.assertEqual(len(list_source_documents(root=root / "store")), 1)

    def test_extract_text_success_with_injected_extractor(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "source.pdf"
            pdf.write_bytes(b"%PDF-1.4\nsource text\n%%EOF")
            record = register_pdf_source(pdf, root=root / "store")

            extracted = extract_pdf_text(record.document_id, root=root / "store", extractor=lambda _path: (["Hello", "World"], 2))

            self.assertEqual(extracted.extraction_status, STATUS_EXTRACTED)
            self.assertEqual(extracted.page_count, 2)
            self.assertGreater(extracted.extracted_char_count, 0)
            self.assertIn("--- Page 1 ---", get_extracted_text(record.document_id, root=root / "store"))

    def test_extract_text_marks_empty_pdf_as_needing_ocr(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "scan.pdf"
            pdf.write_bytes(b"%PDF-1.4\nimage only\n%%EOF")
            record = register_pdf_source(pdf, root=root / "store")

            extracted = extract_pdf_text(record.document_id, root=root / "store", extractor=lambda _path: (["", ""], 2))

            self.assertEqual(extracted.extraction_status, STATUS_NEEDS_OCR)
            self.assertEqual(extracted.extracted_char_count, 0)
            self.assertIn("OCR", extracted.warnings[0])

    def test_extract_text_missing_dependency_controlled_error(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "source.pdf"
            pdf.write_bytes(b"%PDF-1.4\nsource text\n%%EOF")
            record = register_pdf_source(pdf, root=root / "store")

            def missing(_path: Path) -> tuple[list[str], int | None]:
                raise ImportError("missing")

            extracted = extract_pdf_text(record.document_id, root=root / "store", extractor=missing)

            self.assertEqual(extracted.extraction_status, STATUS_EXTRACTOR_UNAVAILABLE)
            self.assertTrue(extracted.warnings)

    def test_public_export_omits_private_paths(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "source.pdf"
            pdf.write_bytes(b"%PDF-1.4\nsource text\n%%EOF")
            record = register_pdf_source(pdf, root=root / "store")

            public = source_document_public_json(record)

            self.assertIsNone(public["source_path"])
            self.assertIsNone(public["stored_pdf_path"])
            self.assertIsNone(public["extracted_text_path"])
            self.assertEqual(public["document_id"], record.document_id)

    def test_invalid_extension_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.txt"
            path.write_text("not a PDF", encoding="utf-8")

            with self.assertRaises(ValueError):
                register_pdf_source(path, root=Path(tmp) / "store")


if __name__ == "__main__":
    unittest.main()
