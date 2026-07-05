from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from backend.electional import api
from backend.electional.backend_contract_validation import run_backend_contract_validation
from backend.electional.pdf_text_layer import (
    build_pdf_highlight_overlay,
    extract_pdf_page_text_layer,
    format_pdf_text_selection,
    map_pdf_locator_to_rectangles,
    select_pdf_text_in_rectangle,
)
from backend.electional.pdf_viewport import create_pdf_viewport_session, render_pdf_viewport_page
from backend.tests.test_backend_contract_validation import _prepare_contract_fixture
from backend.tests.test_pdf_viewport import PNG_1X1


def _prepare_certified_fixture(root: Path) -> str:
    document_id, _ = _prepare_contract_fixture(root, with_topics=False)
    run_backend_contract_validation(document_id, regenerate=True, root=root / "store")
    return document_id


def _fake_render_adapter() -> dict[str, object]:
    def page_count(_pdf_path: Path) -> int:
        return 2

    def estimate_pixels(_pdf_path: Path, _page_number: int, zoom_percent: int) -> dict[str, int]:
        scale = zoom_percent / 100.0
        return {"width": int(200 * scale), "height": int(100 * scale)}

    def render_page(_pdf_path: Path, _page_number: int, zoom_percent: int) -> dict[str, object]:
        scale = zoom_percent / 100.0
        return {"png_bytes": PNG_1X1, "width_pixels": int(200 * scale), "height_pixels": int(100 * scale)}

    return {"name": "fake_renderer", "version": "1.0", "page_count": page_count, "estimate_pixels": estimate_pixels, "render_page": render_page}


def _fake_text_layer_adapter() -> dict[str, object]:
    def extract_page_text_layer(_pdf_path: Path, page_number: int) -> dict[str, object]:
        if page_number == 1:
            words = [
                {"text": "Alpha", "bbox": [10.0, 10.0, 40.0, 20.0], "block_index": 0, "line_index": 0, "span_index": 0},
                {"text": "Beta", "bbox": [45.0, 10.0, 75.0, 20.0], "block_index": 0, "line_index": 0, "span_index": 0},
                {"text": "Alpha", "bbox": [10.0, 30.0, 40.0, 40.0], "block_index": 0, "line_index": 1, "span_index": 0},
                {"text": "Beta", "bbox": [45.0, 30.0, 75.0, 40.0], "block_index": 0, "line_index": 1, "span_index": 0},
                {"text": "Gamma", "bbox": [80.0, 30.0, 120.0, 40.0], "block_index": 0, "line_index": 1, "span_index": 0},
            ]
        else:
            words = [{"text": "Delta", "bbox": [15.0, 12.0, 50.0, 22.0], "block_index": 0, "line_index": 0, "span_index": 0}]
        return {"page_width_points": 200.0, "page_height_points": 100.0, "rotation": 0, "words": words, "spans": [], "warnings": []}

    return {"name": "fake_renderer", "version": "1.0", "extract_page_text_layer": extract_page_text_layer}


class PdfTextLayerTest(TestCase):
    def test_text_layer_requires_current_viewport(self) -> None:
        with TemporaryDirectory() as tmp:
            result = extract_pdf_page_text_layer("viewport_missing", root=Path(tmp) / "store")
        self.assertEqual(result["status"], "not_found")

    def test_text_layer_cache_is_revision_aware_but_zoom_independent(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _prepare_certified_fixture(root)
            with patch("backend.electional.pdf_viewport._get_renderer_adapter", return_value=_fake_render_adapter()), patch("backend.electional.pdf_text_layer._get_text_layer_adapter", return_value=_fake_text_layer_adapter()):
                session = create_pdf_viewport_session(document_id, root=root / "store")["viewport"]
                render_pdf_viewport_page(session["viewport_id"], page_number=1, zoom_percent=100, root=root / "store")
                first = extract_pdf_page_text_layer(session["viewport_id"], page_number=1, root=root / "store")
                render_pdf_viewport_page(session["viewport_id"], page_number=1, zoom_percent=125, root=root / "store")
                second = extract_pdf_page_text_layer(session["viewport_id"], page_number=1, root=root / "store")
            self.assertEqual(first["text_layer"]["cache_status"], "created")
            self.assertEqual(second["text_layer"]["cache_status"], "reused")

    def test_exact_locator_offsets_map_to_expected_rectangles(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _prepare_certified_fixture(root)
            with patch("backend.electional.pdf_viewport._get_renderer_adapter", return_value=_fake_render_adapter()), patch("backend.electional.pdf_text_layer._get_text_layer_adapter", return_value=_fake_text_layer_adapter()):
                session = create_pdf_viewport_session(document_id, root=root / "store")["viewport"]
                mapped = map_pdf_locator_to_rectangles(session["viewport_id"], {"document_id": document_id, "source_revision": session["source_revision"], "page": 1, "start_offset": 0, "end_offset": 10}, root=root / "store")
            self.assertEqual(mapped["mapping_status"], "exact")
            self.assertEqual(mapped["rectangles_pdf"], [[10.0, 10.0, 75.0, 20.0]])

    def test_ambiguous_text_match_does_not_choose_rectangle(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _prepare_certified_fixture(root)
            with patch("backend.electional.pdf_viewport._get_renderer_adapter", return_value=_fake_render_adapter()), patch("backend.electional.pdf_text_layer._get_text_layer_adapter", return_value=_fake_text_layer_adapter()):
                session = create_pdf_viewport_session(document_id, root=root / "store")["viewport"]
                mapped = map_pdf_locator_to_rectangles(session["viewport_id"], {"document_id": document_id, "source_revision": session["source_revision"], "page": 1, "selected_text": "Alpha Beta"}, root=root / "store")
            self.assertEqual(mapped["mapping_status"], "ambiguous")
            self.assertEqual(mapped["rectangle_count"], 0)

    def test_cross_document_or_stale_locator_is_blocked(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _prepare_certified_fixture(root)
            with patch("backend.electional.pdf_viewport._get_renderer_adapter", return_value=_fake_render_adapter()), patch("backend.electional.pdf_text_layer._get_text_layer_adapter", return_value=_fake_text_layer_adapter()):
                session = create_pdf_viewport_session(document_id, root=root / "store")["viewport"]
                cross = map_pdf_locator_to_rectangles(session["viewport_id"], {"document_id": "other_doc", "source_revision": session["source_revision"], "page": 1}, root=root / "store")
                stale = map_pdf_locator_to_rectangles(session["viewport_id"], {"document_id": document_id, "source_revision": 999, "page": 1}, root=root / "store")
            self.assertEqual(cross["mapping_status"], "cross_document")
            self.assertEqual(stale["mapping_status"], "stale_revision")

    def test_overlay_deduplicates_rectangles_and_reports_unmapped(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _prepare_certified_fixture(root)
            with patch("backend.electional.pdf_viewport._get_renderer_adapter", return_value=_fake_render_adapter()), patch("backend.electional.pdf_text_layer._get_text_layer_adapter", return_value=_fake_text_layer_adapter()):
                session = create_pdf_viewport_session(document_id, root=root / "store")["viewport"]
                render_pdf_viewport_page(session["viewport_id"], page_number=1, zoom_percent=100, root=root / "store")
                overlay = build_pdf_highlight_overlay(
                    session["viewport_id"],
                    [
                        {"locator_id": "one", "document_id": document_id, "source_revision": session["source_revision"], "page": 1, "start_offset": 0, "end_offset": 10},
                        {"locator_id": "two", "document_id": document_id, "source_revision": session["source_revision"], "page": 1, "start_offset": 0, "end_offset": 10},
                        {"locator_id": "bad", "document_id": document_id, "source_revision": session["source_revision"], "page": 1, "selected_text": "Missing"},
                    ],
                    overlay_type="search",
                    root=root / "store",
                )
            self.assertEqual(len(overlay["rectangles"]), 1)
            self.assertEqual(overlay["mapped_locator_count"], 2)
            self.assertEqual(overlay["unmapped_locator_count"], 1)

    def test_visible_selection_returns_only_intersecting_native_text(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _prepare_certified_fixture(root)
            with patch("backend.electional.pdf_viewport._get_renderer_adapter", return_value=_fake_render_adapter()), patch("backend.electional.pdf_text_layer._get_text_layer_adapter", return_value=_fake_text_layer_adapter()):
                session = create_pdf_viewport_session(document_id, root=root / "store")["viewport"]
                render_pdf_viewport_page(session["viewport_id"], page_number=1, zoom_percent=100, root=root / "store")
                selection = select_pdf_text_in_rectangle(session["viewport_id"], [8.0, 8.0, 80.0, 22.0], root=root / "store")
            self.assertEqual(selection["selection_status"], "selected")
            self.assertEqual(selection["selected_text"], "Alpha Beta")
            self.assertEqual(format_pdf_text_selection(selection, public_safe=True), "Alpha Beta")

    def test_api_pdf_text_layer_flow(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _prepare_certified_fixture(root)
            with patch("backend.electional.pdf_viewport._get_renderer_adapter", return_value=_fake_render_adapter()), patch("backend.electional.pdf_text_layer._get_text_layer_adapter", return_value=_fake_text_layer_adapter()):
                session = create_pdf_viewport_session(document_id, root=root / "store")["viewport"]
                render_pdf_viewport_page(session["viewport_id"], page_number=1, zoom_percent=100, root=root / "store")
                layer = api.extract_pdf_page_text_layer(session["viewport_id"], root=root / "store")
                overlay = api.build_pdf_highlight_overlay(session["viewport_id"], [{"document_id": document_id, "source_revision": session["source_revision"], "page": 1, "start_offset": 0, "end_offset": 10}], root=root / "store")
                selection = api.select_pdf_text_in_rectangle(session["viewport_id"], [8.0, 8.0, 80.0, 22.0], root=root / "store")
                report = api.format_pdf_text_layer_report(viewport_id=session["viewport_id"], public_safe=True, root=root / "store")
            self.assertEqual(layer["status"], "ready")
            self.assertEqual(overlay["mapped_locator_count"], 1)
            self.assertEqual(selection["selected_text"], "Alpha Beta")
            self.assertIn("PDF Text-Layer Report", report)
            self.assertNotIn("pdf_sources", report)
            self.assertNotIn("pdf_text_layers", report)
            self.assertNotIn("Alpha Beta Alpha Beta Gamma", report)
