from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from backend.electional import api
from backend.electional.backend_contract_validation import run_backend_contract_validation
from backend.electional.citation_draft_review import create_citation_from_approved_draft, save_citation_draft_review_decision
from backend.electional.evidence_binder import build_evidence_binder
from backend.electional.evidence_handoff_review import (
    build_evidence_handoff_review_workspace,
    create_proposal_draft_from_evidence_handoff,
    find_evidence_handoff_binder_candidates,
    insert_handoff_citation_into_binder,
    save_evidence_handoff_review_decision,
)
from backend.electional.pdf_reader_workspace import create_pdf_reader_workspace, draft_citation_from_pdf_selection
from backend.electional.pdf_text_layer import select_pdf_text_in_rectangle
from backend.electional.pdf_viewport import create_pdf_viewport_session, render_pdf_viewport_page
from backend.electional.source_knowledge import create_manual_proposal, create_source_citation, load_chunks
from backend.tests.test_backend_contract_validation import _prepare_contract_fixture
from backend.tests.test_pdf_text_layer import _fake_render_adapter, _fake_text_layer_adapter


def _prepare_certified_fixture(root: Path) -> str:
    document_id, _ = _prepare_contract_fixture(root, with_topics=False)
    run_backend_contract_validation(document_id, regenerate=True, root=root / "store")
    return document_id


def _build_pending_handoff(root: Path) -> tuple[str, dict, dict, dict]:
    document_id = _prepare_certified_fixture(root)
    with patch("backend.electional.pdf_viewport._get_renderer_adapter", return_value=_fake_render_adapter()), patch("backend.electional.pdf_text_layer._get_text_layer_adapter", return_value=_fake_text_layer_adapter()):
        viewport = create_pdf_viewport_session(document_id, root=root / "store")["viewport"]
        render_pdf_viewport_page(viewport["viewport_id"], page_number=1, zoom_percent=100, root=root / "store")
        workspace = create_pdf_reader_workspace(document_id, viewport_id=viewport["viewport_id"], root=root / "store")["workspace"]
        selection = select_pdf_text_in_rectangle(viewport["viewport_id"], [8.0, 8.0, 80.0, 22.0], root=root / "store")
        draft = draft_citation_from_pdf_selection(workspace["workspace_id"], selection, note="Possible citation", root=root / "store")["citation_draft"]
    review = save_citation_draft_review_decision(workspace["workspace_id"], draft["citation_draft_id"], "approve", root=root / "store")["review"]
    created = create_citation_from_approved_draft(review["review_id"], confirmation="CREATE", root=root / "store")
    return document_id, workspace, draft, created


def _build_candidate_binders(root: Path, document_id: str) -> list[str]:
    chunks = load_chunks(document_id=document_id, root=root / "store")
    support_chunk = chunks[1 if len(chunks) > 1 else 0]
    create_source_citation(document_id, support_chunk.chunk_id, "Support note", quote_excerpt="Support excerpt", root=root / "store")
    binder_ids = []
    for claim in ("Binder A", "Binder B"):
        proposal = create_manual_proposal(document_id, support_chunk.chunk_id, claim, root=root / "store")
        binder = build_evidence_binder(proposal.proposal_id, root=root / "store")
        binder_ids.append(str(binder["binder_id"]))
    return sorted(binder_ids)


class EvidenceHandoffReviewTest(TestCase):
    def test_pending_handoff_loads_for_review(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, _workspace, _draft, created = _build_pending_handoff(root)
            result = build_evidence_handoff_review_workspace(created["evidence_handoff_id"], root=root / "store")
        self.assertEqual(result["document_id"], document_id)
        self.assertEqual(result["handoff_status"], "pending_evidence_review")
        self.assertEqual(result["review_status"], "pending")
        self.assertEqual(result["provenance_status"], "valid")

    def test_stale_or_invalid_citation_blocks_action(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _document_id, _workspace, _draft, created = _build_pending_handoff(root)
            citation_path = root / "store" / "citations" / f"{created['citation_id']}.json"
            payload = json.loads(citation_path.read_text(encoding="utf-8"))
            payload["source_revision"] = 999
            citation_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            blocked = save_evidence_handoff_review_decision(created["evidence_handoff_id"], "approve_proposal_draft", root=root / "store")
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("source_revision_changed", blocked["blockers"])

    def test_binder_candidates_are_document_scoped_and_deterministic(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, _workspace, _draft, created = _build_pending_handoff(root)
            binder_ids = _build_candidate_binders(root, document_id)
            result = find_evidence_handoff_binder_candidates(created["evidence_handoff_id"], root=root / "store")
            second = find_evidence_handoff_binder_candidates(created["evidence_handoff_id"], root=root / "store")
        self.assertGreaterEqual(result["candidate_count"], 2)
        self.assertTrue(set(binder_ids).issubset({item["binder_id"] for item in result["candidates"]}))
        self.assertEqual([item["binder_id"] for item in result["candidates"]], [item["binder_id"] for item in second["candidates"]])
        self.assertTrue(all("same_document" in item["candidate_reason"] for item in result["candidates"]))

    def test_binder_insert_requires_approval_and_insert_confirmation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, _workspace, _draft, created = _build_pending_handoff(root)
            binder_id = _build_candidate_binders(root, document_id)[0]
            blocked_before = insert_handoff_citation_into_binder("handoff_review_missing", confirmation=None, root=root / "store") if False else None
            review = save_evidence_handoff_review_decision(created["evidence_handoff_id"], "approve_binder_insert", target_binder_id=binder_id, root=root / "store")["review"]
            blocked = insert_handoff_citation_into_binder(review["review_id"], confirmation=None, root=root / "store")
        self.assertIsNone(blocked_before)
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("insert_confirmation_required", blocked["blockers"])

    def test_successful_binder_insert_creates_revalidation_atomically(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, _workspace, _draft, created = _build_pending_handoff(root)
            binder_id = _build_candidate_binders(root, document_id)[0]
            review = save_evidence_handoff_review_decision(created["evidence_handoff_id"], "approve_binder_insert", target_binder_id=binder_id, root=root / "store")["review"]
            inserted = insert_handoff_citation_into_binder(review["review_id"], confirmation="INSERT", root=root / "store")
            binder_path = root / "store" / "evidence_binders" / f"{binder_id.replace('binder_', '', 1)}_evidence_binder.json"
            binder_payload = json.loads(binder_path.read_text(encoding="utf-8"))
            handoff_payload = json.loads((root / "store" / "citation_evidence_handoffs" / f"{created['evidence_handoff_id']}.json").read_text(encoding="utf-8"))
            queue_payload = json.loads((root / "store" / "source_impact_queue" / f"{inserted['revalidation_id']}.json").read_text(encoding="utf-8"))
        self.assertEqual(inserted["status"], "inserted")
        self.assertTrue(any(item.get("citation_id") == created["citation_id"] for item in binder_payload["linked_citations"]))
        self.assertEqual(handoff_payload["completed_action"], "binder_insert")
        self.assertEqual(queue_payload["status"], "pending_review")

    def test_proposal_draft_requires_approval_and_draft_confirmation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _document_id, _workspace, _draft, created = _build_pending_handoff(root)
            review = save_evidence_handoff_review_decision(created["evidence_handoff_id"], "approve_proposal_draft", root=root / "store")["review"]
            blocked = create_proposal_draft_from_evidence_handoff(review["review_id"], confirmation=None, root=root / "store")
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("draft_confirmation_required", blocked["blockers"])

    def test_successful_proposal_draft_does_not_promote_or_modify_binder(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _document_id, _workspace, _draft, created = _build_pending_handoff(root)
            binder_before = list((root / "store" / "evidence_binders").glob("*.json")) if (root / "store" / "evidence_binders").exists() else []
            review = save_evidence_handoff_review_decision(created["evidence_handoff_id"], "approve_proposal_draft", root=root / "store")["review"]
            result = create_proposal_draft_from_evidence_handoff(review["review_id"], confirmation="DRAFT", root=root / "store")
            proposal_payload = json.loads((root / "store" / "proposals" / f"{result['proposal_id']}.json").read_text(encoding="utf-8"))
            binder_after = list((root / "store" / "evidence_binders").glob("*.json")) if (root / "store" / "evidence_binders").exists() else []
        self.assertEqual(result["status"], "proposal_draft_created")
        self.assertEqual(proposal_payload["status"], "draft")
        self.assertEqual(proposal_payload["created_from"], "citation_evidence_handoff")
        self.assertEqual(len(binder_before), len(binder_after))

    def test_api_evidence_handoff_review_flow(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, _workspace, _draft, created = _build_pending_handoff(root)
            binder_id = _build_candidate_binders(root, document_id)[0]
            proposal_before = list((root / "store" / "proposals").glob("*.json")) if (root / "store" / "proposals").exists() else []
            workspace = api.build_evidence_handoff_review_workspace(created["evidence_handoff_id"], root=root / "store")
            candidates = find_evidence_handoff_binder_candidates(created["evidence_handoff_id"], root=root / "store")
            review = api.save_evidence_handoff_review_decision(created["evidence_handoff_id"], "approve_binder_insert", target_binder_id=binder_id, root=root / "store")["review"]
            inserted = api.insert_handoff_citation_into_binder(review["review_id"], confirmation="INSERT", root=root / "store")
            second = api.insert_handoff_citation_into_binder(review["review_id"], confirmation="INSERT", root=root / "store")
            report = api.format_evidence_handoff_review_report(evidence_handoff_id=created["evidence_handoff_id"], review_id=review["review_id"], public_safe=True, root=root / "store")
            proposal_files = list((root / "store" / "proposals").glob("*.json")) if (root / "store" / "proposals").exists() else []
        self.assertEqual(workspace["handoff_status"], "pending_evidence_review")
        self.assertGreaterEqual(candidates["candidate_count"], 2)
        self.assertEqual(inserted["status"], "inserted")
        self.assertEqual(second["status"], "already_inserted")
        self.assertEqual(len(proposal_files), len(proposal_before))
        self.assertIn("Evidence Handoff Review Report", report)
        self.assertNotIn("C:\\", report)
        self.assertNotIn("Support excerpt", report)
        self.assertNotIn("reviewer_note", report)
