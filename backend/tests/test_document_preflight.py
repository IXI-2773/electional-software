from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.electional import api
from backend.electional.document_preflight import can_extract_after_preflight, format_preflight_report_text, get_document_preflight_summary, run_document_preflight
from backend.electional.source_documents import extract_pdf_text, register_pdf_source


class FakePage:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self) -> str:
        return self.text


class FakeReader:
    def __init__(self, pages: list[str], *, encrypted: bool = False, metadata: dict[str, str] | None = None) -> None:
        self.pages = [FakePage(page) for page in pages]
        self.is_encrypted = encrypted
        self.metadata = metadata or {}


def _registered_pdf(root: Path, name: str = "source.pdf") -> str:
    pdf = root / name
    pdf.write_bytes(f"%PDF-1.4\nsource text {name}\n%%EOF".encode("utf-8"))
    return register_pdf_source(pdf, root=root / "store").document_id


class DocumentPreflightTest(unittest.TestCase):
    def test_preflight_missing_document_blocks(self) -> None:
        with TemporaryDirectory() as tmp:
            report = run_document_preflight("missing_doc", root=Path(tmp) / "store")
            self.assertEqual(report.verdict, "BLOCK")
            self.assertIn("document_missing", report.blockers)

    def test_preflight_text_pdf_pass_or_warning(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _registered_pdf(root)
            report = run_document_preflight(
                document_id,
                root=root / "store",
                reader_factory=lambda _path: FakeReader(["Document Preflight Policy\nMust review hard gate warnings."], metadata={"title": "Policy"}),
            )
            self.assertIn(report.verdict, {"PASS", "WARNING"})
            self.assertEqual(report.format_detection["source_format"], "text_based_pdf")

    def test_preflight_saved_indexed_existing_and_regenerate(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _registered_pdf(root)
            first = run_document_preflight(document_id, root=root / "store", reader_factory=lambda _path: FakeReader(["Must allow extraction."], metadata={"title": "Doc"}))
            existing = run_document_preflight(document_id, root=root / "store", reader_factory=lambda _path: FakeReader(["Different text."], metadata={"title": "Doc"}))
            regenerated = run_document_preflight(document_id, root=root / "store", regenerate=True, reader_factory=lambda _path: FakeReader(["Different text."], metadata={"title": "Doc"}))

            self.assertEqual(existing.created_at_utc, first.created_at_utc)
            self.assertNotEqual(regenerated.created_at_utc, first.created_at_utc)
            self.assertTrue((root / "store" / "indexes" / "preflight_index.json").exists())

    def test_preflight_keyword_quality_and_privacy_scan(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _registered_pdf(root)
            report = run_document_preflight(
                document_id,
                root=root / "store",
                reader_factory=lambda _path: FakeReader(
                    ["Hard gate manual review required. Email me@test.com. C:\\Users\\Name\\file.pdf"],
                    metadata={"title": "final_v2"},
                ),
            )
            self.assertIn("hard gate", report.keyword_scan["top_terms"])
            self.assertIn("extraction_quality", report.quality_scores)
            self.assertFalse(report.privacy_scan["public_export_safe"])
            self.assertIn("metadata_title_generic", report.metadata["warnings"])

    def test_api_run_document_preflight(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _registered_pdf(root)
            report = api.run_document_preflight(document_id, root=root / "store", reader_factory=lambda _path: FakeReader(["Fast Lane warning."], metadata={"title": "Doc"}))
            summary = api.get_document_preflight_summary(root=root / "store")
            self.assertEqual(report.document_id, document_id)
            self.assertEqual(summary["total"], 1)

    def test_extraction_blocks_on_blocked_preflight_and_preserves_no_preflight_behavior(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            blocked_id = _registered_pdf(root, "blocked.pdf")
            run_document_preflight(blocked_id, root=root / "store", reader_factory=lambda _path: FakeReader([""], encrypted=True))
            blocked = extract_pdf_text(blocked_id, root=root / "store", extractor=lambda _path: (["Should not extract"], 1))
            self.assertIn("preflight_blocked_extraction", blocked.warnings)
            self.assertEqual(blocked.extracted_char_count, 0)

            clear_id = _registered_pdf(root, "clear.pdf")
            extracted = extract_pdf_text(clear_id, root=root / "store", extractor=lambda _path: (["Existing behavior"], 1))
            self.assertGreater(extracted.extracted_char_count, 0)


    def test_preflight_summary_not_run(self) -> None:
        with TemporaryDirectory() as tmp:
            summary = get_document_preflight_summary("doc_missing", root=Path(tmp) / "store")
            self.assertFalse(summary["has_preflight"])
            self.assertEqual(summary["verdict"], "NOT_RUN")
            self.assertIsNone(summary["extraction_quality_score"])
            self.assertEqual(summary["recommended_action"], "Run preflight before extraction.")

    def test_preflight_summary_pass_warning_block(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pass_id = _registered_pdf(root, "pass.pdf")
            run_document_preflight(
                pass_id,
                root=root / "store",
                reader_factory=lambda _path: FakeReader(["Clean document text that is long enough for extraction quality."], metadata={"title": "Clean Policy"}),
            )
            pass_summary = get_document_preflight_summary(pass_id, root=root / "store")
            self.assertTrue(pass_summary["has_preflight"])
            self.assertIn(pass_summary["verdict"], {"PASS", "WARNING"})
            self.assertIn("extraction_quality_band", pass_summary)

            warning_id = _registered_pdf(root, "warning.pdf")
            run_document_preflight(
                warning_id,
                root=root / "store",
                reader_factory=lambda _path: FakeReader(["Manual review warning email me@test.com C:\\Users\\Name\\file.pdf"], metadata={"title": "final_v2"}),
            )
            warning_summary = get_document_preflight_summary(warning_id, root=root / "store")
            self.assertEqual(warning_summary["verdict"], "WARNING")
            self.assertFalse(warning_summary["public_export_safe"])
            self.assertIn("email_like_pattern_detected", warning_summary["privacy_findings"])

            block_id = _registered_pdf(root, "block.pdf")
            run_document_preflight(block_id, root=root / "store", reader_factory=lambda _path: FakeReader([""], encrypted=True))
            block_summary = get_document_preflight_summary(block_id, root=root / "store")
            self.assertEqual(block_summary["verdict"], "BLOCK")
            self.assertGreater(block_summary["blocker_count"], 0)

    def test_can_extract_after_preflight_no_preflight(self) -> None:
        with TemporaryDirectory() as tmp:
            gate = can_extract_after_preflight("doc_missing", root=Path(tmp) / "store")
            self.assertTrue(gate["allowed"])
            self.assertEqual(gate["verdict"], "NOT_RUN")
            self.assertIn("preflight_not_run", gate["warnings"])

    def test_can_extract_after_preflight_pass_warning_and_block(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pass_id = _registered_pdf(root, "pass.pdf")
            run_document_preflight(
                pass_id,
                root=root / "store",
                reader_factory=lambda _path: FakeReader(["Clean document text that is long enough for extraction quality."], metadata={"title": "Clean Policy"}),
            )
            self.assertTrue(can_extract_after_preflight(pass_id, root=root / "store")["allowed"])

            warning_id = _registered_pdf(root, "warning.pdf")
            run_document_preflight(
                warning_id,
                root=root / "store",
                reader_factory=lambda _path: FakeReader(["Warning and manual review required. me@test.com"], metadata={"title": "Doc"}),
            )
            warning_gate = can_extract_after_preflight(warning_id, root=root / "store")
            self.assertTrue(warning_gate["allowed"])
            self.assertEqual(warning_gate["verdict"], "WARNING")

            block_id = _registered_pdf(root, "block.pdf")
            run_document_preflight(block_id, root=root / "store", reader_factory=lambda _path: FakeReader([""], encrypted=True))
            blocked_gate = can_extract_after_preflight(block_id, root=root / "store")
            override_gate = can_extract_after_preflight(block_id, root=root / "store", override=True)
            self.assertFalse(blocked_gate["allowed"])
            self.assertTrue(blocked_gate["requires_override"])
            self.assertTrue(override_gate["allowed"])

    def test_format_preflight_report_text_not_run(self) -> None:
        with TemporaryDirectory() as tmp:
            text = format_preflight_report_text("doc_missing", root=Path(tmp) / "store")
            self.assertIn("Verdict: NOT RUN", text)
            self.assertIn("Run preflight before extraction.", text)

    def test_format_preflight_report_text_hides_sensitive_values(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _registered_pdf(root)
            run_document_preflight(
                document_id,
                root=root / "store",
                reader_factory=lambda _path: FakeReader(["Email me@test.com and C:\\Users\\Name\\secret.pdf. hard gate hard gate"], metadata={"title": "Doc"}),
            )
            text = format_preflight_report_text(document_id, root=root / "store")
            self.assertIn("email like pattern detected", text)
            self.assertIn("local path detected", text)
            self.assertNotIn("me@test.com", text)
            self.assertNotIn("C:\\Users\\Name", text)

    def test_privacy_summary_hides_sensitive_values(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _registered_pdf(root)
            run_document_preflight(
                document_id,
                root=root / "store",
                reader_factory=lambda _path: FakeReader(["Token secret abcdefghijklmnop and person@example.com"], metadata={"title": "Doc"}),
            )
            summary = get_document_preflight_summary(document_id, root=root / "store")
            self.assertIn("email_like_pattern_detected", summary["privacy_findings"])
            self.assertNotIn("person@example.com", str(summary))
            self.assertNotIn("abcdefghijklmnop", str(summary))
if __name__ == "__main__":
    unittest.main()


