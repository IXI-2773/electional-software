from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import api
from backend.electional.evidence_handoff_review import create_proposal_draft_from_evidence_handoff, save_evidence_handoff_review_decision
from backend.electional.proposal_promotion import (
    analyze_proposal_promotion_conflicts,
    build_proposal_promotion_workspace,
    promote_approved_proposal,
    save_proposal_promotion_decision,
)
from backend.tests.test_evidence_handoff_review import _build_pending_handoff


def _build_phase_9b_proposal_draft(root: Path) -> tuple[str, str, dict, dict]:
    document_id, _workspace, _draft, created = _build_pending_handoff(root)
    review = save_evidence_handoff_review_decision(created["evidence_handoff_id"], "approve_proposal_draft", root=root / "store")["review"]
    proposal = create_proposal_draft_from_evidence_handoff(review["review_id"], confirmation="DRAFT", root=root / "store")
    proposal_payload = json.loads((root / "store" / "proposals" / f"{proposal['proposal_id']}.json").read_text(encoding="utf-8"))
    return document_id, proposal["proposal_id"], created, proposal_payload


class ProposalPromotionTest(TestCase):
    def test_phase_9b_proposal_draft_loads_for_promotion_review(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, proposal_id, created, _proposal = _build_phase_9b_proposal_draft(root)
            workspace = build_proposal_promotion_workspace(proposal_id, root=root / "store")
        self.assertEqual(workspace["document_id"], document_id)
        self.assertEqual(workspace["proposal_status"], "draft")
        self.assertEqual(workspace["citation_id"], created["citation_id"])
        self.assertEqual(workspace["handoff_action"], "proposal_draft")
        self.assertEqual(workspace["revalidation_status"], "pending_review")

    def test_stale_or_invalid_provenance_blocks_approval(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _document_id, proposal_id, _created, _proposal = _build_phase_9b_proposal_draft(root)
            proposal_path = root / "store" / "proposals" / f"{proposal_id}.json"
            payload = json.loads(proposal_path.read_text(encoding="utf-8"))
            payload["source_revision"] = 999
            proposal_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            blocked = save_proposal_promotion_decision(proposal_id, "approve", root=root / "store")
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("source_revision_changed", blocked["blockers"])

    def test_exact_duplicate_blocks_promotion(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _document_id, proposal_id, _created, proposal = _build_phase_9b_proposal_draft(root)
            duplicate = dict(proposal)
            duplicate["proposal_id"] = "proposal_duplicate_manual"
            (root / "store" / "proposals" / "proposal_duplicate_manual.json").write_text(json.dumps(duplicate, indent=2), encoding="utf-8")
            result = save_proposal_promotion_decision(proposal_id, "approve", root=root / "store")
        self.assertEqual(result["status"], "blocked")
        self.assertIn("exact_duplicate_exists", result["blockers"])

    def test_near_duplicate_or_conflict_requires_acknowledgement(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _document_id, proposal_id, _created, proposal = _build_phase_9b_proposal_draft(root)
            near_duplicate = dict(proposal)
            near_duplicate["proposal_id"] = "proposal_near_manual"
            near_duplicate["claim"] = proposal["claim"] + " revised"
            (root / "store" / "proposals" / "proposal_near_manual.json").write_text(json.dumps(near_duplicate, indent=2), encoding="utf-8")
            analysis = analyze_proposal_promotion_conflicts(proposal_id, root=root / "store")
            blocked = save_proposal_promotion_decision(proposal_id, "approve", root=root / "store")
            allowed = save_proposal_promotion_decision(proposal_id, "approve", acknowledge_near_duplicate=True, root=root / "store")
        self.assertEqual(analysis["duplicate_status"], "near_duplicate")
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("near_duplicate_acknowledgement_required", blocked["blockers"])
        self.assertEqual(allowed["status"], "saved")

    def test_reject_and_request_changes_require_note(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _document_id, proposal_id, _created, _proposal = _build_phase_9b_proposal_draft(root)
            reject = save_proposal_promotion_decision(proposal_id, "reject", root=root / "store")
            changes = save_proposal_promotion_decision(proposal_id, "request_changes", reviewer_note="Needs narrower claim", root=root / "store")
        self.assertEqual(reject["status"], "blocked")
        self.assertIn("reviewer_note_required", reject["blockers"])
        self.assertEqual(changes["review"]["review_status"], "changes_requested")

    def test_approved_proposal_requires_promote_confirmation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _document_id, proposal_id, _created, _proposal = _build_phase_9b_proposal_draft(root)
            review = save_proposal_promotion_decision(proposal_id, "approve", root=root / "store")["review"]
            blocked = promote_approved_proposal(review["promotion_review_id"], confirmation=None, root=root / "store")
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("promote_confirmation_required", blocked["blockers"])

    def test_successful_promotion_creates_receipt_and_resolves_revalidation_atomically(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _document_id, proposal_id, _created, _proposal = _build_phase_9b_proposal_draft(root)
            binder_before = list((root / "store" / "evidence_binders").glob("*.json")) if (root / "store" / "evidence_binders").exists() else []
            review = save_proposal_promotion_decision(proposal_id, "approve", root=root / "store")["review"]
            promoted = promote_approved_proposal(review["promotion_review_id"], confirmation="PROMOTE", root=root / "store")
            proposal_payload = json.loads((root / "store" / "proposals" / f"{proposal_id}.json").read_text(encoding="utf-8"))
            receipt_payload = json.loads((root / "store" / "proposal_promotion_receipts" / f"{promoted['promotion_receipt_id']}.json").read_text(encoding="utf-8"))
            queue_payload = json.loads((root / "store" / "source_impact_queue" / f"{receipt_payload['revalidation_id']}.json").read_text(encoding="utf-8"))
            binder_after = list((root / "store" / "evidence_binders").glob("*.json")) if (root / "store" / "evidence_binders").exists() else []
        self.assertEqual(promoted["status"], "promoted")
        self.assertEqual(proposal_payload["status"], "promoted")
        self.assertIn(proposal_payload["source_citation_id"], proposal_payload["accepted_citation_ids"])
        self.assertEqual(receipt_payload["promotion_status"], "completed")
        self.assertEqual(queue_payload["status"], "resolved")
        self.assertEqual(queue_payload["resolution"], "proposal_promoted")
        self.assertEqual(len(binder_before), len(binder_after))

    def test_api_proposal_promotion_flow(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _document_id, proposal_id, _created, _proposal = _build_phase_9b_proposal_draft(root)
            binder_before = list((root / "store" / "evidence_binders").glob("*.json")) if (root / "store" / "evidence_binders").exists() else []
            workspace = api.build_proposal_promotion_workspace(proposal_id, root=root / "store")
            review = api.save_proposal_promotion_decision(proposal_id, "approve", root=root / "store")["review"]
            promoted = api.promote_approved_proposal(review["promotion_review_id"], confirmation="PROMOTE", root=root / "store")
            second = api.promote_approved_proposal(review["promotion_review_id"], confirmation="PROMOTE", root=root / "store")
            health = api.get_proposal_promotion_health(root=root / "store")
            report = api.format_proposal_promotion_report(proposal_id=proposal_id, promotion_review_id=review["promotion_review_id"], public_safe=True, root=root / "store")
            binder_after = list((root / "store" / "evidence_binders").glob("*.json")) if (root / "store" / "evidence_binders").exists() else []
        self.assertEqual(workspace["proposal_status"], "draft")
        self.assertEqual(promoted["status"], "promoted")
        self.assertEqual(second["status"], "already_promoted")
        self.assertIn("promotion_receipt_id", promoted)
        self.assertEqual(health["promoted_count"], 1)
        self.assertEqual(len(binder_before), len(binder_after))
        self.assertIn("Proposal Promotion Report", report)
        self.assertNotIn("C:\\", report)
        self.assertNotIn("Possible citation", report)
        self.assertNotIn("reviewer_note", report)
