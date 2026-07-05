from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from backend.electional import api
from backend.electional.backend_contract_validation import run_backend_contract_validation
from backend.electional.pdf_reader_workspace import (
    build_pdf_reader_workspace_overlay,
    create_pdf_reader_workspace,
    draft_citation_from_pdf_selection,
    load_pdf_reader_workspace,
    save_pdf_reader_annotation,
    save_pdf_reader_bookmark,
)
from backend.electional.pdf_text_layer import select_pdf_text_in_rectangle
from backend.electional.pdf_viewport import create_pdf_viewport_session, render_pdf_viewport_page
from backend.tests.test_backend_contract_validation import _prepare_contract_fixture
from backend.tests.test_pdf_text_layer import _fake_render_adapter, _fake_text_layer_adapter


def _prepare_certified_fixture(root: Path) -> str:
    document_id, _ = _prepare_contract_fixture(root, with_topics=False)
    run_backend_contract_validation(document_id, regenerate=True, root=root / "store")
    return document_id


class PdfReaderWorkspaceTest(TestCase):
    def test_create_workspace_requires_current_document_state(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, _ = _prepare_contract_fixture(root, with_topics=False)
            result = create_pdf_reader_workspace(document_id, root=root / "store")
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blocker"], "backend_certification_required")

    def test_workspace_is_bound_to_source_revision(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _prepare_certified_fixture(root)
            with patch("backend.electional.pdf_viewport._get_renderer_adapter", return_value=_fake_render_adapter()):
                viewport = create_pdf_viewport_session(document_id, root=root / "store")["viewport"]
                workspace = create_pdf_reader_workspace(document_id, viewport_id=viewport["viewport_id"], root=root / "store")["workspace"]
            workspace_path = root / "store" / "pdf_reader_workspaces" / f"{workspace['workspace_id']}.json"
            payload = json.loads(workspace_path.read_text(encoding="utf-8"))
            payload["source_revision"] = 0
            workspace_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            loaded = load_pdf_reader_workspace(workspace["workspace_id"], root=root / "store")
        self.assertEqual(loaded["status"], "stale")
        self.assertIn("source_revision_changed", loaded["blockers"])

    def test_duplicate_bookmark_is_idempotent(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _prepare_certified_fixture(root)
            with patch("backend.electional.pdf_viewport._get_renderer_adapter", return_value=_fake_render_adapter()):
                viewport = create_pdf_viewport_session(document_id, root=root / "store")["viewport"]
                workspace = create_pdf_reader_workspace(document_id, viewport_id=viewport["viewport_id"], root=root / "store")["workspace"]
                first = save_pdf_reader_bookmark(workspace["workspace_id"], 1, label=" Intro ", locator={"document_id": document_id, "source_revision": workspace["source_revision"], "page": 1}, root=root / "store")
                second = save_pdf_reader_bookmark(workspace["workspace_id"], 1, label="Intro", locator={"document_id": document_id, "source_revision": workspace["source_revision"], "page": 1}, root=root / "store")
        self.assertEqual(first["status"], "saved")
        self.assertEqual(second["status"], "unchanged")
        self.assertEqual(second["workspace"]["bookmark_count"], 1)

    def test_annotation_rejects_invalid_or_cross_document_geometry(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _prepare_certified_fixture(root)
            with patch("backend.electional.pdf_viewport._get_renderer_adapter", return_value=_fake_render_adapter()), patch("backend.electional.pdf_text_layer._get_text_layer_adapter", return_value=_fake_text_layer_adapter()):
                viewport = create_pdf_viewport_session(document_id, root=root / "store")["viewport"]
                workspace = create_pdf_reader_workspace(document_id, viewport_id=viewport["viewport_id"], root=root / "store")["workspace"]
                bad_rect = save_pdf_reader_annotation(workspace["workspace_id"], 1, "highlight", [[50.0, 20.0, 10.0, 10.0]], root=root / "store")
                cross = save_pdf_reader_annotation(workspace["workspace_id"], 1, "highlight", [[10.0, 10.0, 40.0, 20.0]], locator={"document_id": "other_doc", "source_revision": workspace["source_revision"], "page": 1}, root=root / "store")
        self.assertEqual(bad_rect["status"], "blocked")
        self.assertEqual(bad_rect["blocker"], "invalid_annotation_geometry")
        self.assertEqual(cross["status"], "blocked")
        self.assertEqual(cross["blocker"], "cross_document_locator")

    def test_selection_creates_draft_not_real_citation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _prepare_certified_fixture(root)
            with patch("backend.electional.pdf_viewport._get_renderer_adapter", return_value=_fake_render_adapter()), patch("backend.electional.pdf_text_layer._get_text_layer_adapter", return_value=_fake_text_layer_adapter()):
                viewport = create_pdf_viewport_session(document_id, root=root / "store")["viewport"]
                render_pdf_viewport_page(viewport["viewport_id"], page_number=1, zoom_percent=100, root=root / "store")
                workspace = create_pdf_reader_workspace(document_id, viewport_id=viewport["viewport_id"], root=root / "store")["workspace"]
                selection = select_pdf_text_in_rectangle(viewport["viewport_id"], [8.0, 8.0, 80.0, 22.0], root=root / "store")
                drafted = draft_citation_from_pdf_selection(workspace["workspace_id"], selection, note="Possible citation", root=root / "store")
        self.assertEqual(drafted["status"], "saved")
        self.assertEqual(drafted["citation_draft"]["status"], "draft")
        self.assertFalse((root / "store" / "citations").exists() and any((root / "store" / "citations").glob("*.json")))

    def test_workspace_becomes_stale_after_source_revision_change(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _prepare_certified_fixture(root)
            with patch("backend.electional.pdf_viewport._get_renderer_adapter", return_value=_fake_render_adapter()):
                viewport = create_pdf_viewport_session(document_id, root=root / "store")["viewport"]
                workspace = create_pdf_reader_workspace(document_id, viewport_id=viewport["viewport_id"], root=root / "store")["workspace"]
            workspace_path = root / "store" / "pdf_reader_workspaces" / f"{workspace['workspace_id']}.json"
            payload = json.loads(workspace_path.read_text(encoding="utf-8"))
            payload["source_hash"] = "sha256:old"
            workspace_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            loaded = load_pdf_reader_workspace(workspace["workspace_id"], root=root / "store")
        self.assertEqual(loaded["status"], "stale")
        self.assertIn("source_hash_changed", loaded["blockers"])

    def test_current_page_overlay_returns_only_matching_page_items(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _prepare_certified_fixture(root)
            with patch("backend.electional.pdf_viewport._get_renderer_adapter", return_value=_fake_render_adapter()), patch("backend.electional.pdf_text_layer._get_text_layer_adapter", return_value=_fake_text_layer_adapter()):
                viewport = create_pdf_viewport_session(document_id, root=root / "store")["viewport"]
                render_pdf_viewport_page(viewport["viewport_id"], page_number=1, zoom_percent=100, root=root / "store")
                workspace = create_pdf_reader_workspace(document_id, viewport_id=viewport["viewport_id"], root=root / "store")["workspace"]
                save_pdf_reader_annotation(workspace["workspace_id"], 1, "highlight", [[10.0, 10.0, 40.0, 20.0]], root=root / "store")
                save_pdf_reader_annotation(workspace["workspace_id"], 2, "highlight", [[15.0, 12.0, 50.0, 22.0]], root=root / "store")
                overlay = build_pdf_reader_workspace_overlay(workspace["workspace_id"], viewport["viewport_id"], page_number=1, root=root / "store")
        self.assertEqual(overlay["page_number"], 1)
        self.assertEqual(overlay["annotation_count"], 1)
        self.assertEqual(len(overlay["rectangles"]), 1)

    def test_api_pdf_reader_workspace_flow(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id = _prepare_certified_fixture(root)
            with patch("backend.electional.pdf_viewport._get_renderer_adapter", return_value=_fake_render_adapter()), patch("backend.electional.pdf_text_layer._get_text_layer_adapter", return_value=_fake_text_layer_adapter()):
                viewport = create_pdf_viewport_session(document_id, root=root / "store")["viewport"]
                render_pdf_viewport_page(viewport["viewport_id"], page_number=1, zoom_percent=100, root=root / "store")
                workspace = api.create_pdf_reader_workspace(document_id, viewport_id=viewport["viewport_id"], root=root / "store")["workspace"]
                api.save_pdf_reader_bookmark(workspace["workspace_id"], 1, label="Intro", locator={"document_id": document_id, "source_revision": workspace["source_revision"], "page": 1}, root=root / "store")
                api.save_pdf_reader_annotation(workspace["workspace_id"], 1, "highlight", [[10.0, 10.0, 40.0, 20.0]], root=root / "store")
                selection = select_pdf_text_in_rectangle(viewport["viewport_id"], [8.0, 8.0, 80.0, 22.0], root=root / "store")
                drafted = api.draft_citation_from_pdf_selection(workspace["workspace_id"], selection, note="Possible citation", root=root / "store")
                report = api.format_pdf_reader_workspace_report(workspace["workspace_id"], public_safe=True, root=root / "store")
        self.assertEqual(drafted["citation_draft"]["status"], "draft")
        self.assertNotIn("pdf_sources", report)
        self.assertNotIn("Alpha Beta", report)
        self.assertFalse((root / "store" / "citations").exists() and any((root / "store" / "citations").glob("*.json")))
