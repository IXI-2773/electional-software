from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import api
from backend.electional.proposal_promotion import promote_approved_proposal, save_proposal_promotion_decision
from backend.electional.proposal_rule_activation import (
    analyze_proposal_rule_candidate_conflicts,
    activate_rule_from_promoted_proposal,
    build_proposal_rule_activation_workspace,
    rollback_proposal_rule_activation,
    save_proposal_rule_activation_decision,
    validate_promoted_proposal_rule_mapping,
)
from backend.electional.rules import load_rule, save_rule
from backend.tests.test_proposal_promotion import _build_phase_9b_proposal_draft


def _build_promoted_proposal(root: Path, *, structured: bool) -> tuple[str, dict]:
    _document_id, proposal_id, _created, _proposal = _build_phase_9b_proposal_draft(root)
    proposal_path = root / "store" / "proposals" / f"{proposal_id}.json"
    payload = json.loads(proposal_path.read_text(encoding="utf-8"))
    if structured:
        payload["rule_mapping"] = {
            "rule_type": "electional_constraint",
            "target": "controlled_target_x",
            "scope": "documented_scope",
            "condition": {"field": "controlled_field", "operator": "equals", "value": "controlled_value"},
            "operator": "equals",
            "value": "controlled_value",
            "priority": 50,
            "enabled": True,
        }
        proposal_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    review = save_proposal_promotion_decision(proposal_id, "approve", root=root / "store")["review"]
    promoted = promote_approved_proposal(review["promotion_review_id"], confirmation="PROMOTE", root=root / "store")
    return proposal_id, promoted


class ProposalRuleActivationTest(TestCase):
    def test_promoted_proposal_loads_as_structured_rule_candidate(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            proposal_id, _promoted = _build_promoted_proposal(root, structured=True)
            mapping = validate_promoted_proposal_rule_mapping(proposal_id, root=root / "store")
            workspace = build_proposal_rule_activation_workspace(proposal_id, root=root / "store")
        self.assertTrue(mapping["mapping_valid"])
        self.assertEqual(workspace["proposal_status"], "promoted")
        self.assertEqual(workspace["rule_mapping_status"], "valid")
        self.assertEqual(workspace["rule_candidate_status"], "ready")

    def test_unstructured_or_stale_proposal_blocks_activation_review(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            proposal_id, _promoted = _build_promoted_proposal(root, structured=False)
            blocked = save_proposal_rule_activation_decision(proposal_id, "approve", root=root / "store")
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("proposal_not_rule_mappable", blocked["blockers"])

    def test_exact_active_rule_duplicate_blocks_activation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            proposal_id, _promoted = _build_promoted_proposal(root, structured=True)
            save_rule(
                {
                    "rule_id": "rule_existing_duplicate",
                    "rule_type": "electional_constraint",
                    "target": "controlled_target_x",
                    "scope": "documented_scope",
                    "condition": {"field": "controlled_field", "operator": "equals", "value": "controlled_value"},
                    "operator": "equals",
                    "value": "controlled_value",
                    "priority": 50,
                    "enabled": True,
                    "status": "active",
                },
                root=root / "store",
            )
            result = analyze_proposal_rule_candidate_conflicts(proposal_id, root=root / "store")
        self.assertEqual(result["duplicate_status"], "exact_duplicate")
        self.assertEqual(result["activation_allowed"], False)
        self.assertIn("exact_active_rule_duplicate_exists", result["blockers"])

    def test_noncritical_conflict_requires_explicit_acknowledgement(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            proposal_id, _promoted = _build_promoted_proposal(root, structured=True)
            save_rule(
                {
                    "rule_id": "rule_existing_warning",
                    "rule_type": "electional_constraint",
                    "target": "controlled_target_x",
                    "scope": "documented_scope",
                    "condition": {"field": "controlled_field", "operator": "equals", "value": "controlled_value"},
                    "operator": "equals",
                    "value": "controlled_value",
                    "priority": 40,
                    "enabled": True,
                    "status": "active",
                },
                root=root / "store",
            )
            blocked = save_proposal_rule_activation_decision(proposal_id, "approve", root=root / "store")
            allowed = save_proposal_rule_activation_decision(proposal_id, "approve", acknowledge_conflict=True, root=root / "store")
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("conflict_acknowledgement_required", blocked["blockers"])
        self.assertEqual(allowed["status"], "saved")

    def test_reject_and_request_changes_require_note(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            proposal_id, _promoted = _build_promoted_proposal(root, structured=True)
            reject = save_proposal_rule_activation_decision(proposal_id, "reject", root=root / "store")
            changes = save_proposal_rule_activation_decision(proposal_id, "request_changes", reviewer_note="Need canonical rule storage", root=root / "store")
        self.assertEqual(reject["status"], "blocked")
        self.assertIn("reviewer_note_required", reject["blockers"])
        self.assertEqual(changes["review"]["review_status"], "changes_requested")

    def test_approved_candidate_requires_activate_confirmation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            proposal_id, _promoted = _build_promoted_proposal(root, structured=True)
            review = save_proposal_rule_activation_decision(proposal_id, "approve", root=root / "store")["review"]
            blocked = api.activate_rule_from_promoted_proposal(review["rule_activation_review_id"], confirmation=None, root=root / "store")
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("activate_confirmation_required", blocked["blockers"])

    def test_successful_activation_creates_rule_receipt_and_revalidation_atomically(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            proposal_id, _promoted = _build_promoted_proposal(root, structured=True)
            review = save_proposal_rule_activation_decision(proposal_id, "approve", root=root / "store")["review"]
            activated = activate_rule_from_promoted_proposal(review["rule_activation_review_id"], confirmation="ACTIVATE", root=root / "store")
            receipt_payload = json.loads((root / "store" / "proposal_rule_activation_receipts" / f"{activated['activation_receipt_id']}.json").read_text(encoding="utf-8"))
            queue_payload = json.loads((root / "store" / "source_impact_queue" / f"{activated['revalidation_id']}.json").read_text(encoding="utf-8"))
            rule_payload = load_rule(activated["rule_id"], root=root / "store")
        self.assertEqual(activated["status"], "activated")
        self.assertEqual(receipt_payload["activation_status"], "completed")
        self.assertEqual(queue_payload["status"], "pending_review")
        self.assertEqual(queue_payload["reason"], "proposal_rule_activation")
        self.assertEqual(rule_payload["status"], "active")

    def test_api_rule_activation_idempotency_rollback_and_public_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            proposal_id, _promoted = _build_promoted_proposal(root, structured=True)
            workspace = api.build_proposal_rule_activation_workspace(proposal_id, root=root / "store")
            review = api.save_proposal_rule_activation_decision(proposal_id, "approve", root=root / "store")["review"]
            first = api.activate_rule_from_promoted_proposal(review["rule_activation_review_id"], confirmation="ACTIVATE", root=root / "store")
            second = api.activate_rule_from_promoted_proposal(review["rule_activation_review_id"], confirmation="ACTIVATE", root=root / "store")
            report = api.format_proposal_rule_activation_report(proposal_id=proposal_id, public_safe=True, root=root / "store")
            rollback = rollback_proposal_rule_activation(first["activation_receipt_id"], confirmation="ROLLBACK", root=root / "store")
            rolled_back_rule = load_rule(first["rule_id"], root=root / "store")
        self.assertEqual(first["status"], "activated")
        self.assertEqual(second["status"], "already_activated")
        self.assertEqual(workspace["rule_candidate_status"], "ready")
        self.assertIn("Proposal Rule Activation Report", report)
        self.assertIn("ACTIVATE confirmation", report)
        self.assertNotIn("C:\\", report)
        self.assertNotIn("reviewer_note", report)
        self.assertEqual(rollback["status"], "rollback_completed")
        self.assertEqual(rolled_back_rule["status"], "rolled_back")
