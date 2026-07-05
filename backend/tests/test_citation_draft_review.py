from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from backend.electional import api
from backend.electional.backend_contract_validation import run_backend_contract_validation
from backend.electional.citation_draft_review import (
    build_citation_draft_review_workspace,
    create_citation_from_approved_draft,
    detect_citation_draft_duplicates,
    save_citation_draft_review_decision,
    validate_citation_draft_provenance,
)
from backend.electional.pdf_reader_workspace import create_pdf_reader_workspace, draft_citation_from_pdf_selection
from backend.electional.pdf_text_layer import select_pdf_text_in_rectangle
from backend.electional.pdf_viewport import create_pdf_viewport_session, render_pdf_viewport_page
from backend.tests.test_backend_contract_validation import _prepare_contract_fixture
from backend.tests.test_pdf_text_layer import _fake_render_adapter, _fake_text_layer_adapter


def _prepare_certified_fixture(root: Path) -> str:
    document_id, _ = _prepare_contract_fixture(root, with_topics=False)
    run_backend_contract_validation(document_id, regenerate=True, root=root / "store")
    return document_id


def _build_reader_draft(root: Path) -> tuple[str, dict, dict, dict]:
    document_id = _prepare_certified_fixture(root)
    with patch("backend.electional.pdf_viewport._get_renderer_adapter", return_value=_fake_render_adapter()), patch("backend.electional.pdf_text_layer._get_text_layer_adapter", return_value=_fake_text_layer_adapter()):
        viewport = create_pdf_viewport_session(document_id, root=root / "store")["viewport"]
        render_pdf_viewport_page(viewport["viewport_id"], page_number=1, zoom_percent=100, root=root / "store")
        workspace = create_pdf_reader_workspace(document_id, viewport_id=viewport["viewport_id"], root=root / "store")["workspace"]
        selection = select_pdf_text_in_rectangle(viewport["viewport_id"], [8.0, 8.0, 80.0, 22.0], root=root / "store")
        draft = draft_citation_from_pdf_selection(workspace["workspace_id"], selection, note="Possible citation", root=root / "store")["citation_draft"]
    return document_id, viewport, workspace, draft


class CitationDraftReviewTest(TestCase):
    def test_review_workspace_loads_current_draft(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, _viewport, workspace, draft = _build_reader_draft(root)
            result = build_citation_draft_review_workspace(workspace["workspace_id"], draft["citation_draft_id"], root=root / "store")
        self.assertEqual(result["document_id"], document_id)
        self.assertEqual(result["draft_status"], "draft")
        self.assertEqual(result["review_status"], "pending")
        self.assertEqual(result["provenance_status"], "valid")

    def test_invalid_or_stale_provenance_blocks_approval(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _document_id, _viewport, workspace, draft = _build_reader_draft(root)
            workspace_path = root / "store" / "pdf_reader_workspaces" / f"{workspace['workspace_id']}.json"
            payload = json.loads(workspace_path.read_text(encoding="utf-8"))
            payload["source_revision"] = 0
            workspace_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            provenance = validate_citation_draft_provenance(workspace["workspace_id"], draft["citation_draft_id"], root=root / "store")
            decision = save_citation_draft_review_decision(workspace["workspace_id"], draft["citation_draft_id"], "approve", root=root / "store")
        self.assertFalse(provenance["valid"])
        self.assertIn("source_revision_changed", decision["blockers"])

    def test_exact_duplicate_blocks_creation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _document_id, _viewport, workspace, draft = _build_reader_draft(root)
            citations_dir = root / "store" / "citations"
            citations_dir.mkdir(parents=True, exist_ok=True)
            citation_id = "citation_existing"
            payload = {
                "citation_id": citation_id,
                "document_id": draft["document_id"],
                "chunk_id": draft["chunk_id"],
                "page_start": draft["page"],
                "page_end": draft["page"],
                "note": "Existing citation",
                "quote_excerpt": draft["selected_text"],
                "created_at_utc": "2026-01-01T00:00:00Z",
                "warnings": [],
                "schema_version": "source_citation_v1",
                "source_revision": draft["source_revision"],
                "start_offset": draft["start_offset"],
                "end_offset": draft["end_offset"],
                "selected_text_hash": draft["selected_text_hash"],
            }
            (citations_dir / f"{citation_id}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
            duplicates = detect_citation_draft_duplicates(workspace["workspace_id"], draft["citation_draft_id"], root=root / "store")
        self.assertEqual(duplicates["duplicate_status"], "exact_duplicate")
        self.assertIn("exact_duplicate_exists", duplicates["blockers"])

    def test_near_duplicate_requires_explicit_override(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _document_id, _viewport, workspace, draft = _build_reader_draft(root)
            citations_dir = root / "store" / "citations"
            citations_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "citation_id": "citation_near",
                "document_id": draft["document_id"],
                "chunk_id": draft["chunk_id"],
                "page_start": draft["page"],
                "page_end": draft["page"],
                "note": "Near citation",
                "quote_excerpt": draft["selected_text"],
                "created_at_utc": "2026-01-01T00:00:00Z",
                "warnings": [],
                "schema_version": "source_citation_v1",
                "source_revision": draft["source_revision"],
                "start_offset": draft["start_offset"] + 1,
                "end_offset": draft["end_offset"] - 1,
                "selected_text_hash": draft["selected_text_hash"],
            }
            (citations_dir / "citation_near.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
            blocked = save_citation_draft_review_decision(workspace["workspace_id"], draft["citation_draft_id"], "approve", root=root / "store")
            allowed = save_citation_draft_review_decision(workspace["workspace_id"], draft["citation_draft_id"], "approve", allow_near_duplicate=True, root=root / "store")
        self.assertIn("near_duplicate_requires_override", blocked["blockers"])
        self.assertEqual(allowed["status"], "saved")

    def test_reject_and_request_changes_require_note(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _document_id, _viewport, workspace, draft = _build_reader_draft(root)
            reject = save_citation_draft_review_decision(workspace["workspace_id"], draft["citation_draft_id"], "reject", root=root / "store")
            changes = save_citation_draft_review_decision(workspace["workspace_id"], draft["citation_draft_id"], "request_changes", reviewer_note="Tighten excerpt", root=root / "store")
        self.assertEqual(reject["blocker"], "reviewer_note_required")
        self.assertEqual(changes["review"]["review_status"], "changes_requested")

    def test_approved_draft_requires_create_confirmation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _document_id, _viewport, workspace, draft = _build_reader_draft(root)
            review = save_citation_draft_review_decision(workspace["workspace_id"], draft["citation_draft_id"], "approve", root=root / "store")["review"]
            created = create_citation_from_approved_draft(review["review_id"], confirmation=None, root=root / "store")
        self.assertEqual(created["status"], "blocked")
        self.assertIn("create_confirmation_required", created["blockers"])

    def test_successful_creation_updates_citation_review_workspace_and_handoff_atomically(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _document_id, _viewport, workspace, draft = _build_reader_draft(root)
            review = save_citation_draft_review_decision(workspace["workspace_id"], draft["citation_draft_id"], "approve", root=root / "store")["review"]
            created = create_citation_from_approved_draft(review["review_id"], confirmation="CREATE", root=root / "store")
            review_payload = json.loads((root / "store" / "citation_draft_reviews" / f"{review['review_id']}.json").read_text(encoding="utf-8"))
            workspace_payload = json.loads((root / "store" / "pdf_reader_workspaces" / f"{workspace['workspace_id']}.json").read_text(encoding="utf-8"))
            handoff_files = list((root / "store" / "citation_evidence_handoffs").glob("*.json"))
        self.assertEqual(created["status"], "created")
        self.assertEqual(review_payload["review_status"], "created")
        self.assertTrue(any(item.get("citation_draft_id") == draft["citation_draft_id"] and item.get("status") == "created" for item in workspace_payload["citation_drafts"]))
        self.assertTrue(any(path.stem == created["evidence_handoff_id"] for path in handoff_files))

    def test_api_citation_draft_review_flow(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _document_id, _viewport, workspace, draft = _build_reader_draft(root)
            binder_before = list((root / "store" / "evidence_binders").glob("*.json")) if (root / "store" / "evidence_binders").exists() else []
            proposal_before = list((root / "store" / "proposals").glob("*.json")) if (root / "store" / "proposals").exists() else []
            review_workspace = api.build_citation_draft_review_workspace(workspace["workspace_id"], draft["citation_draft_id"], root=root / "store")
            review = api.save_citation_draft_review_decision(workspace["workspace_id"], draft["citation_draft_id"], "approve", root=root / "store")["review"]
            created = api.create_citation_from_approved_draft(review["review_id"], confirmation="CREATE", root=root / "store")
            second = api.create_citation_from_approved_draft(review["review_id"], confirmation="CREATE", root=root / "store")
            health = api.get_citation_draft_review_health(workspace_id=workspace["workspace_id"], root=root / "store")
            report = api.format_citation_draft_review_report(review_id=review["review_id"], public_safe=True, root=root / "store")
            binder_after = list((root / "store" / "evidence_binders").glob("*.json")) if (root / "store" / "evidence_binders").exists() else []
            proposal_after = list((root / "store" / "proposals").glob("*.json")) if (root / "store" / "proposals").exists() else []
        self.assertEqual(review_workspace["review_status"], "pending")
        self.assertEqual(created["status"], "created")
        self.assertEqual(second["status"], "already_created")
        self.assertEqual(health["status"], "healthy")
        self.assertIn("Citation Draft Review Report", report)
        self.assertNotIn("C:\\", report)
        self.assertNotIn("Possible citation", report)
        self.assertEqual(len(binder_before), len(binder_after))
        self.assertEqual(len(proposal_before), len(proposal_after))
