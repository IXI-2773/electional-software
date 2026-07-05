from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import api
from backend.electional.proposal_rule_activation import activate_rule_from_promoted_proposal, save_proposal_rule_activation_decision
from backend.electional.rule_activation_revalidation import (
    build_rule_activation_revalidation_workspace,
    build_rule_runtime_contract_plan,
    complete_rule_activation_revalidation,
    run_rule_runtime_contract_validation,
    save_rule_activation_revalidation_decision,
    validate_rule_activation_revalidation_provenance,
)
from backend.electional.rules import load_rule
from backend.tests.test_proposal_rule_activation import _build_promoted_proposal


def _build_active_rule_revalidation(root: Path) -> tuple[str, str, str, dict]:
    proposal_id, _promoted = _build_promoted_proposal(root, structured=True)
    review = save_proposal_rule_activation_decision(proposal_id, "approve", root=root / "store")["review"]
    activation = activate_rule_from_promoted_proposal(review["rule_activation_review_id"], confirmation="ACTIVATE", root=root / "store")
    return proposal_id, activation["revalidation_id"], activation["rule_id"], activation


class RuleActivationRevalidationTest(TestCase):
    def test_pending_phase_9d_revalidation_loads_with_valid_provenance(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _proposal_id, revalidation_id, rule_id, activation = _build_active_rule_revalidation(root)
            workspace = build_rule_activation_revalidation_workspace(revalidation_id, root=root / "store")
            provenance = validate_rule_activation_revalidation_provenance(revalidation_id, root=root / "store")
        self.assertEqual(workspace["revalidation_id"], revalidation_id)
        self.assertEqual(workspace["rule_id"], rule_id)
        self.assertEqual(workspace["activation_receipt_id"], activation["activation_receipt_id"])
        self.assertTrue(provenance["valid"])
        self.assertTrue(provenance["rule_hash_valid"])

    def test_missing_rule_or_receipt_blocks_runtime_validation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _proposal_id, revalidation_id, rule_id, _activation = _build_active_rule_revalidation(root)
            (root / "store" / "rules" / f"{rule_id}.json").unlink()
            result = run_rule_runtime_contract_validation(revalidation_id, root=root / "store")
        self.assertEqual(result["status"], "blocked")
        self.assertIn("active_rule_missing", result["blockers"])

    def test_missing_canonical_evaluator_blocks_without_creating_second_engine(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _proposal_id, revalidation_id, _rule_id, _activation = _build_active_rule_revalidation(root)
            result = run_rule_runtime_contract_validation(revalidation_id, root=root / "store")
            receipts = list((root / "store" / "rule_activation_certification_receipts").glob("*.json")) if (root / "store" / "rule_activation_certification_receipts").exists() else []
        self.assertEqual(result["status"], "blocked")
        self.assertIn("rule_runtime_evaluator_unavailable", result["blockers"])
        self.assertEqual(receipts, [])

    def test_deterministic_positive_and_negative_contract_cases_pass(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _proposal_id, revalidation_id, _rule_id, _activation = _build_active_rule_revalidation(root)
            plan = build_rule_runtime_contract_plan(revalidation_id, root=root / "store")
        self.assertEqual(plan["cases"][0]["case_id"], "positive_match")
        self.assertEqual(plan["cases"][1]["case_id"], "negative_nonmatch")
        self.assertEqual(plan["cases"][0]["expected_match"], True)
        self.assertEqual(plan["cases"][1]["expected_match"], False)

    def test_unexpected_result_or_persistent_mutation_blocks_certification(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _proposal_id, revalidation_id, _rule_id, _activation = _build_active_rule_revalidation(root)
            blocked = save_rule_activation_revalidation_decision(revalidation_id, "certify", root=root / "store")
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("runtime_validation_not_certifiable", blocked["blockers"])

    def test_certification_requires_certify_confirmation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _proposal_id, revalidation_id, _rule_id, _activation = _build_active_rule_revalidation(root)
            review = save_rule_activation_revalidation_decision(revalidation_id, "reject_and_rollback", reviewer_note="Evaluator unavailable; rollback required", root=root / "store")["review"]
            blocked = complete_rule_activation_revalidation(review["revalidation_review_id"], confirmation=None, root=root / "store")
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("rollback_confirmation_required", blocked["blockers"])

    def test_successful_certification_creates_receipt_and_resolves_revalidation_atomically(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _proposal_id, revalidation_id, rule_id, activation = _build_active_rule_revalidation(root)
            review = save_rule_activation_revalidation_decision(revalidation_id, "reject_and_rollback", reviewer_note="Evaluator unavailable; use verified rollback", root=root / "store")["review"]
            result = complete_rule_activation_revalidation(review["revalidation_review_id"], confirmation="ROLLBACK", root=root / "store")
            queue_payload = json.loads((root / "store" / "source_impact_queue" / f"{revalidation_id}.json").read_text(encoding="utf-8"))
            rule_payload = load_rule(rule_id, root=root / "store")
        self.assertEqual(result["status"], "rejected_rolled_back")
        self.assertEqual(result["activation_receipt_id"], activation["activation_receipt_id"])
        self.assertEqual(queue_payload["status"], "resolved")
        self.assertEqual(queue_payload["resolution"], "activation_rolled_back")
        self.assertEqual(rule_payload["status"], "rolled_back")

    def test_api_revalidation_idempotency_rollback_and_public_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _proposal_id, revalidation_id, rule_id, _activation = _build_active_rule_revalidation(root)
            workspace = api.build_rule_activation_revalidation_workspace(revalidation_id, root=root / "store")
            runtime = api.run_rule_runtime_contract_validation(revalidation_id, root=root / "store")
            review = api.save_rule_activation_revalidation_decision(revalidation_id, "reject_and_rollback", reviewer_note="Evaluator unavailable; rollback required", root=root / "store")["review"]
            first = api.complete_rule_activation_revalidation(review["revalidation_review_id"], confirmation="ROLLBACK", root=root / "store")
            second = api.complete_rule_activation_revalidation(review["revalidation_review_id"], confirmation="ROLLBACK", root=root / "store")
            report = api.format_rule_activation_revalidation_report(revalidation_id=revalidation_id, public_safe=True, root=root / "store")
            rule_payload = load_rule(rule_id, root=root / "store")
        self.assertEqual(workspace["runtime_evaluator_status"], "unavailable")
        self.assertEqual(runtime["status"], "blocked")
        self.assertEqual(first["status"], "rejected_rolled_back")
        self.assertEqual(second["status"], "already_rolled_back")
        self.assertEqual(rule_payload["status"], "rolled_back")
        self.assertIn("Rule Activation Revalidation Report", report)
        self.assertIn("No safe single-rule canonical evaluator was discovered", report)
        self.assertNotIn("C:\\", report)
        self.assertNotIn("reviewer_note", report)
