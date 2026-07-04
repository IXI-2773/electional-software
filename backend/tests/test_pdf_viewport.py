from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from backend.electional import api
from backend.electional.backend_contract_validation import run_backend_contract_validation
from backend.electional.pdf_viewport import (
    create_pdf_viewport_session,
    navigate_pdf_viewport,
    render_pdf_viewport_page,
    synchronize_pdf_viewport_to_locator,
)
from backend.tests.test_backend_contract_validation import _prepare_contract_fixture


PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0"
    b"\x00\x00\x03\x01\x01\x00\xc9\xfe\x92\xef\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _prepare_certified_fixture(root: Path) -> str:
    document_id, _ = _prepare_contract_fixture(root, with_topics=False)
    run_backend_contract_validation(document_id, regenerate=True, root=root / "store")
    return document_id


def _fake_adapter(width: int = 100, height: int = 140) -> dict[str, object]:
    def page_count(_pdf_path: Path) -> int:
        return 2

    def estimate_pixels(_pdf_path: Path, _page_number: int, zoom_percent: int) -> dict[str, int]:
        scale = zoom_percent / 100.0
        return {"width": int(width * scale), "height": int(height * scale)}

    def render_page(_pdf_path: Path, _page_number: int, zoom_percent: int) -> dict[str, object]:
        scale = zoom_percent / 100.0
        return {"png_bytes": PNG_1X1, "width_pixels": int(width * scale), "height_pixels": int(height * scale)}

    return {
        "name": "fake_renderer",
        "version": "1.0",
        "page_count": page_count,
        "estimate_pixels": estimate_pixels,
        "render_page": render_page,
    }


class PdfViewportTest(TestCase):
    def test_uncertified_document_cannot_open_viewport(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, _ = _prepare_contract_fixture(root, with_topics=False)
            result = create_pdf_viewport_session(document_id, root=root / "store")
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["blocker"], "backend_certification_required")

    def test_viewport_resolves_only_registered_controlled_source(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _prepare_certified_fixture(root)
            record_path = root / "store" / "indexes" / f"{document_id}.json"
            payload = json.loads(record_path.read_text(encoding="utf-8"))
            payload["stored_pdf_path"] = None
            (root / "outside.pdf").write_bytes(b"%PDF-1.4")
            record_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            run_backend_contract_validation(document_id, regenerate=True, root=root / "store")
            result = create_pdf_viewport_session(document_id, root=root / "store")
            self.assertEqual(result["status"], "blocked")
            self.assertIn("controlled_pdf_missing", result["blockers"])

    def test_create_session_uses_one_based_page_numbers(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _prepare_certified_fixture(root)
            with patch("backend.electional.pdf_viewport._get_renderer_adapter", return_value=_fake_adapter()):
                result = create_pdf_viewport_session(document_id, initial_page=1, zoom_percent=100, root=root / "store")
            self.assertEqual(result["status"], "created")
            self.assertEqual(result["viewport"]["current_page"], 1)
            self.assertEqual(result["viewport"]["page_count"], 2)

    def test_bool_page_numbers_are_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _prepare_certified_fixture(root)
            with patch("backend.electional.pdf_viewport._get_renderer_adapter", return_value=_fake_adapter()):
                create = create_pdf_viewport_session(document_id, initial_page=True, zoom_percent=100, root=root / "store")
                session = create_pdf_viewport_session(document_id, root=root / "store")["viewport"]
                jump = navigate_pdf_viewport(session["viewport_id"], "jump", page_number=True, root=root / "store")
            self.assertEqual(create["status"], "blocked")
            self.assertEqual(create["blocker"], "invalid_initial_page")
            self.assertEqual(jump["status"], "blocked")
            self.assertEqual(jump["blocker"], "invalid_page_number")

    def test_render_page_uses_revision_zoom_aware_cache(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _prepare_certified_fixture(root)
            adapter = _fake_adapter()
            with patch("backend.electional.pdf_viewport._get_renderer_adapter", return_value=adapter):
                session = create_pdf_viewport_session(document_id, root=root / "store")["viewport"]
                first = render_pdf_viewport_page(session["viewport_id"], page_number=1, zoom_percent=125, root=root / "store")
                second = render_pdf_viewport_page(session["viewport_id"], page_number=1, zoom_percent=125, root=root / "store")
            self.assertEqual(first["cache_status"], "created")
            self.assertEqual(second["cache_status"], "reused")
            self.assertEqual(first["width_pixels"], second["width_pixels"])

    def test_navigation_respects_page_boundaries(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _prepare_certified_fixture(root)
            with patch("backend.electional.pdf_viewport._get_renderer_adapter", return_value=_fake_adapter()):
                session = create_pdf_viewport_session(document_id, root=root / "store")["viewport"]
                first = navigate_pdf_viewport(session["viewport_id"], "previous", root=root / "store")
                last = navigate_pdf_viewport(session["viewport_id"], "last", root=root / "store")
                after_last = navigate_pdf_viewport(session["viewport_id"], "next", root=root / "store")
            self.assertEqual(first["current_page"], 1)
            self.assertIn("already_at_first_page", first["warnings"])
            self.assertEqual(last["current_page"], 2)
            self.assertEqual(after_last["current_page"], 2)
            self.assertIn("already_at_last_page", after_last["warnings"])

    def test_zoom_validation_and_render_pixel_limit(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _prepare_certified_fixture(root)
            huge_adapter = _fake_adapter(width=10000, height=10000)
            with patch("backend.electional.pdf_viewport._get_renderer_adapter", return_value=huge_adapter):
                session = create_pdf_viewport_session(document_id, root=root / "store")["viewport"]
                invalid_zoom = render_pdf_viewport_page(session["viewport_id"], zoom_percent=110, root=root / "store")
                too_large = render_pdf_viewport_page(session["viewport_id"], zoom_percent=400, root=root / "store")
            self.assertEqual(invalid_zoom["status"], "blocked")
            self.assertEqual(invalid_zoom["blocker"], "invalid_zoom_percent")
            self.assertEqual(too_large["status"], "blocked")
            self.assertEqual(too_large["blocker"], "render_size_limit_exceeded")

    def test_locator_sync_moves_to_valid_page_and_blocks_stale_locator(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _prepare_certified_fixture(root)
            with patch("backend.electional.pdf_viewport._get_renderer_adapter", return_value=_fake_adapter()):
                session = create_pdf_viewport_session(document_id, root=root / "store")["viewport"]
                good = synchronize_pdf_viewport_to_locator(
                    session["viewport_id"],
                    {"document_id": document_id, "source_revision": session["source_revision"], "page": 1, "chunk_id": f"chunk_{document_id}_0001"},
                    root=root / "store",
                )
                stale = synchronize_pdf_viewport_to_locator(
                    session["viewport_id"],
                    {"document_id": document_id, "source_revision": 999, "page": 1},
                    root=root / "store",
                )
            self.assertEqual(good["locator_status"], "synchronized")
            self.assertEqual(good["current_page"], 1)
            self.assertEqual(stale["locator_status"], "stale_revision")

    def test_locator_sync_rejects_non_mapping_and_bool_offsets(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _prepare_certified_fixture(root)
            with patch("backend.electional.pdf_viewport._get_renderer_adapter", return_value=_fake_adapter()):
                session = create_pdf_viewport_session(document_id, root=root / "store")["viewport"]
                invalid_payload = synchronize_pdf_viewport_to_locator(session["viewport_id"], None, root=root / "store")
                invalid_offsets = synchronize_pdf_viewport_to_locator(
                    session["viewport_id"],
                    {
                        "document_id": document_id,
                        "source_revision": session["source_revision"],
                        "page": 1,
                        "start_offset": True,
                        "end_offset": False,
                    },
                    root=root / "store",
                )
            self.assertEqual(invalid_payload["locator_status"], "blocked")
            self.assertIn("invalid_locator_payload", invalid_payload["blockers"])
            self.assertEqual(invalid_offsets["locator_status"], "blocked")
            self.assertIn("invalid_locator_offsets", invalid_offsets["blockers"])

    def test_api_pdf_viewport_flow(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _prepare_certified_fixture(root)
            with patch("backend.electional.pdf_viewport._get_renderer_adapter", return_value=_fake_adapter()):
                session = api.create_pdf_viewport_session(document_id, root=root / "store")["viewport"]
                rendered = api.render_pdf_viewport_page(session["viewport_id"], page_number=1, zoom_percent=100, root=root / "store")
                moved = api.navigate_pdf_viewport(session["viewport_id"], "next", root=root / "store")
                synced = api.synchronize_pdf_viewport_to_locator(
                    session["viewport_id"],
                    {"document_id": document_id, "source_revision": session["source_revision"], "page": 1},
                    root=root / "store",
                )
                report = api.format_pdf_viewport_report(viewport_id=session["viewport_id"], public_safe=True, root=root / "store")
            self.assertEqual(rendered["render_status"], "rendered")
            self.assertEqual(moved["status"], "ready")
            self.assertEqual(synced["locator_status"], "synchronized")
            self.assertIn("PDF Viewport Report", report)
            self.assertNotIn("pdf_sources", report)
            self.assertNotIn("pdf_viewport_cache", report)
