from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.electional import api
from backend.electional.evidence_binder import build_evidence_binder
from backend.electional.source_documents import extract_pdf_text, register_pdf_source
from backend.electional.source_knowledge import chunk_extracted_text, create_manual_proposal, create_source_citation
from backend.electional.source_reliability_manager import (
    calculate_source_staleness,
    detect_duplicate_source_identity,
    format_source_reliability_report_text,
    get_source_quality_dashboard,
    get_source_relationships,
    link_source_replacement,
    list_evidence_binders_using_source,
    load_source_reliability_history,
    recalculate_source_reliability,
    refresh_evidence_binders_for_source,
    update_source_metadata_for_reliability,
)


def _doc(root: Path, name: str, text: str = "Source reliability text."):
    pdf = root / f"{name}.pdf"
    pdf.write_bytes(f"%PDF-1.4\n{name}\n%%EOF".encode("utf-8"))
    record = register_pdf_source(pdf, root=root / "store")
    extract_pdf_text(record.document_id, root=root / "store", extractor=lambda _path: ([text], 1))
    chunk = chunk_extracted_text(record.document_id, root=root / "store")[0]
    return record.document_id, chunk


class SourceReliabilityManagerTest(unittest.TestCase):
    def test_update_source_metadata_for_reliability(self) -> None:
        with TemporaryDirectory() as tmp:
            doc, _chunk = _doc(Path(tmp), "a")
            result = update_source_metadata_for_reliability(doc, {"source_type": "official_policy", "authority_level": "primary", "publication_date": "2026-01-01", "version_label": "v1"}, root=Path(tmp) / "store")
            self.assertTrue(result["updated"])
            self.assertIn(result["reliability_band"], {"usable", "strong"})

    def test_update_source_metadata_rejects_invalid_source_type(self) -> None:
        with TemporaryDirectory() as tmp:
            doc, _chunk = _doc(Path(tmp), "a")
            with self.assertRaises(ValueError):
                update_source_metadata_for_reliability(doc, {"source_type": "fake"}, root=Path(tmp) / "store")

    def test_update_source_metadata_rejects_invalid_authority(self) -> None:
        with TemporaryDirectory() as tmp:
            doc, _chunk = _doc(Path(tmp), "a")
            with self.assertRaises(ValueError):
                update_source_metadata_for_reliability(doc, {"authority_level": "fake"}, root=Path(tmp) / "store")

    def test_update_source_metadata_rejects_bad_date(self) -> None:
        with TemporaryDirectory() as tmp:
            doc, _chunk = _doc(Path(tmp), "a")
            with self.assertRaises(ValueError):
                update_source_metadata_for_reliability(doc, {"publication_date": "not-a-date"}, root=Path(tmp) / "store")

    def test_recalculate_source_reliability_unknown(self) -> None:
        with TemporaryDirectory() as tmp:
            doc, _chunk = _doc(Path(tmp), "a")
            rel = recalculate_source_reliability(doc, root=Path(tmp) / "store")
            self.assertEqual(rel["reliability_band"], "unknown")

    def test_recalculate_source_reliability_strong(self) -> None:
        with TemporaryDirectory() as tmp:
            doc, _chunk = _doc(Path(tmp), "a")
            update_source_metadata_for_reliability(doc, {"source_type": "official_policy", "authority_level": "primary", "publication_date": "2026-01-01", "version_label": "v1"}, root=Path(tmp) / "store")
            rel = recalculate_source_reliability(doc, root=Path(tmp) / "store")
            self.assertIn(rel["reliability_band"], {"usable", "strong"})

    def test_calculate_source_staleness_unknown_current_stale(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc, _chunk = _doc(root, "a")
            self.assertEqual(calculate_source_staleness(doc, root=root / "store")["staleness_status"], "unknown")
            update_source_metadata_for_reliability(doc, {"publication_date": "2026-01-01"}, root=root / "store")
            self.assertEqual(calculate_source_staleness(doc, as_of_date="2026-07-01", root=root / "store")["staleness_status"], "current")
            update_source_metadata_for_reliability(doc, {"publication_date": "2020-01-01"}, root=root / "store")
            self.assertEqual(calculate_source_staleness(doc, as_of_date="2026-07-01", root=root / "store")["staleness_status"], "stale")

    def test_link_source_replacement_and_get_relationships(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            old, _ = _doc(root, "old")
            new, _ = _doc(root, "new")
            link_source_replacement(old, new, root=root / "store")
            relationships = get_source_relationships(old, root=root / "store")
            self.assertEqual(relationships["relationships"][0]["target_document_id"], new)

    def test_detect_duplicate_source_identity_same_hash_and_title(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = root / "same.pdf"
            pdf.write_bytes(b"%PDF-1.4\nsame\n%%EOF")
            first = register_pdf_source(pdf, root=root / "store")
            second = register_pdf_source(pdf, root=root / "store", copy_into_store=False)
            duplicate = detect_duplicate_source_identity(first.document_id, root=root / "store")
            self.assertIn(duplicate["status"], {"none", "duplicate"})
            doc, _ = _doc(root, "title")
            other, _ = _doc(root, "title_other")
            update_source_metadata_for_reliability(doc, {"manual_title": "Shared Source"}, root=root / "store")
            update_source_metadata_for_reliability(other, {"manual_title": "Shared Source"}, root=root / "store")
            duplicate = detect_duplicate_source_identity(doc, root=root / "store")
            self.assertEqual(duplicate["status"], "possible_duplicate")
            self.assertEqual(first.document_id, second.document_id)

    def test_get_source_quality_dashboard(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc, _ = _doc(root, "a")
            update_source_metadata_for_reliability(doc, {"source_type": "official_policy", "authority_level": "primary"}, root=root / "store")
            dashboard = get_source_quality_dashboard(root=root / "store")
            self.assertEqual(dashboard["total_sources"], 1)
            self.assertTrue(dashboard["items"])

    def test_format_source_reliability_report_text_public_safe(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc, _ = _doc(root, "a")
            update_source_metadata_for_reliability(doc, {"manual_title": "Policy person@example.com C:/secret/file.pdf"}, root=root / "store")
            report = format_source_reliability_report_text(doc, root=root / "store")
            self.assertIn("Source Reliability Report", report)
            self.assertNotIn("person@example.com", report)
            self.assertNotIn("C:/secret/file.pdf", report)

    def test_reliability_history_appends_event(self) -> None:
        with TemporaryDirectory() as tmp:
            doc, _ = _doc(Path(tmp), "a")
            update_source_metadata_for_reliability(doc, {"source_type": "paper"}, note="Marked paper", root=Path(tmp) / "store")
            history = load_source_reliability_history(doc, root=Path(tmp) / "store")
            self.assertTrue(history["events"])

    def test_refresh_and_list_evidence_binders_for_source(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc, chunk = _doc(root, "a")
            proposal = create_manual_proposal(doc, chunk.chunk_id, "Allow reliability review.", root=root / "store")
            create_source_citation(doc, chunk.chunk_id, "Citation.", quote_excerpt="Allow reliability review.", root=root / "store")
            build_evidence_binder(proposal.proposal_id, root=root / "store")
            listed = list_evidence_binders_using_source(doc, root=root / "store")
            refreshed = refresh_evidence_binders_for_source(doc, root=root / "store")
            self.assertEqual(listed["binders_found"], 1)
            self.assertEqual(refreshed["binders_refreshed"], 1)

    def test_api_source_reliability_flow(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc, _ = _doc(root, "a")
            updated = api.update_source_metadata_for_reliability(doc, {"source_type": "book", "authority_level": "secondary"}, root=root / "store")
            dashboard = api.get_source_quality_dashboard(root=root / "store")
            report = api.format_source_reliability_report_text(doc, root=root / "store")
            self.assertTrue(updated["updated"])
            self.assertEqual(dashboard["total_sources"], 1)
            self.assertIn("Source Reliability Report", report)


if __name__ == "__main__":
    unittest.main()
