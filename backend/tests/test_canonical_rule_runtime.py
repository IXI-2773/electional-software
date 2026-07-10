from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from backend.electional.canonical_rule_runtime import (
    create_canonical_rule,
    deactivate_canonical_rule,
    evaluate_canonical_rule,
    get_canonical_rule_runtime_capability,
    list_canonical_rules,
    load_canonical_rule,
)
from backend.electional.proposal_rule_activation import (
    activate_rule_from_promoted_proposal,
    rollback_proposal_rule_activation,
    save_proposal_rule_activation_decision,
)
from backend.electional.rule_activation_revalidation import (
    complete_rule_activation_revalidation,
    run_rule_runtime_contract_validation,
    save_rule_activation_revalidation_decision,
)


def _build_rule_payload(rule_id: str = "rule_021", *, operator: str = "equals", value: object = "controlled_value") -> dict:
    return {
        "schema_version": "canonical_mutable_rule_v1",
        "rule_id": rule_id,
        "rule_type": "electional_constraint",
        "target": "controlled_target_x",
        "scope": "documented_scope",
        "condition": {"field": "controlled_field", "operator": operator, "value": value},
        "operator": operator,
        "value": value,
        "priority": 50,
        "enabled": True,
        "status": "active",
        "source_proposal_id": "proposal_021",
        "source_promotion_receipt_id": "promotion_receipt_021",
        "source_rule_activation_review_id": "review_021",
        "source_revision": "source_rev_021",
    }


def _build_promoted_structured_proposal(root: Path) -> str:
    store = root / "store"
    (store / "proposals").mkdir(parents=True, exist_ok=True)
    (store / "proposal_promotion_receipts").mkdir(parents=True, exist_ok=True)
    proposal_id = "proposal_runtime_021"
    payload = {
        "proposal_id": proposal_id,
        "document_id": "doc_runtime_021",
        "source_revision": "source_rev_021",
        "status": "promoted",
        "created_from": "citation_evidence_handoff",
        "source_citation_id": "citation_021",
        "source_evidence_handoff_id": "handoff_021",
        "source_handoff_review_id": "handoff_review_021",
        "accepted_citation_ids": ["citation_021"],
        "rule_mapping": {
            "rule_type": "electional_constraint",
            "target": "controlled_target_x",
            "scope": "documented_scope",
            "condition": {"field": "controlled_field", "operator": "equals", "value": "controlled_value"},
            "operator": "equals",
            "value": "controlled_value",
            "priority": 50,
            "enabled": True,
        },
    }
    receipt = {
        "promotion_receipt_id": "proposal_promotion_receipt_021",
        "proposal_id": proposal_id,
        "document_id": "doc_runtime_021",
        "source_revision": "source_rev_021",
        "promotion_status": "completed",
        "created_at_utc": "2026-01-01T00:00:00Z",
    }
    (store / "proposals" / f"{proposal_id}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (store / "proposal_promotion_receipts" / f"{receipt['promotion_receipt_id']}.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return proposal_id


def _valid_provenance() -> dict:
    return {
        "valid": True,
        "citation_valid": True,
        "locator_valid": True,
        "handoff_valid": True,
        "revalidation_valid": True,
        "source_revision_current": True,
        "warnings": [],
        "blockers": [],
    }


class CanonicalRuleRuntimeTest(TestCase):
    def test_runtime_capability_reports_repository_and_evaluator_available(self) -> None:
        with TemporaryDirectory() as tmp:
            capability = get_canonical_rule_runtime_capability(root=Path(tmp) / "store")
        self.assertTrue(capability["available"])
        self.assertTrue(capability["repository_available"])
        self.assertTrue(capability["active_index_available"])
        self.assertTrue(capability["single_rule_evaluator_available"])
        self.assertIn("equals", capability["supported_operators"])

    def test_create_rule_persists_record_and_active_index_atomically(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            created = create_canonical_rule(_build_rule_payload(), confirmation="CREATE_RULE", root=root)
            index = json.loads((root / "indexes" / "canonical_rule_index.json").read_text(encoding="utf-8"))
            record = json.loads((root / "canonical_rules" / "rule_021.json").read_text(encoding="utf-8"))
        self.assertEqual(created["status"], "created")
        self.assertIn("rule_021", index["active_rule_ids"])
        self.assertEqual(index["rule_fingerprints"]["rule_021"], record["rule_fingerprint"])

    def test_identical_create_is_idempotent_and_conflicting_id_is_blocked(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            first = create_canonical_rule(_build_rule_payload(), confirmation="CREATE_RULE", root=root)
            second = create_canonical_rule(_build_rule_payload(), confirmation="CREATE_RULE", root=root)
            conflict = create_canonical_rule(_build_rule_payload(value="different_value"), confirmation="CREATE_RULE", root=root)
        self.assertEqual(first["status"], "created")
        self.assertEqual(second["status"], "already_created")
        self.assertEqual(conflict["status"], "blocked")
        self.assertIn("rule_id_content_conflict", conflict["blockers"])

    def test_load_and_list_rules_validate_index_and_fingerprints(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            create_canonical_rule(_build_rule_payload(), confirmation="CREATE_RULE", root=root)
            loaded = load_canonical_rule("rule_021", require_active=True, root=root)
            listed = list_canonical_rules(status="active", rule_type="electional_constraint", target="controlled_target_x", root=root)
        self.assertEqual(loaded["status"], "loaded")
        self.assertEqual(loaded["rule"]["rule_id"], "rule_021")
        self.assertEqual(listed["count"], 1)

    def test_equals_operator_returns_positive_and_negative_results(self) -> None:
        positive = evaluate_canonical_rule(_build_rule_payload(), {"controlled_field": "controlled_value"})
        negative = evaluate_canonical_rule(_build_rule_payload(), {"controlled_field": "different"})
        self.assertEqual(positive["result"], "matched")
        self.assertTrue(positive["matched"])
        self.assertEqual(negative["result"], "not_matched")
        self.assertFalse(negative["matched"])

    def test_supported_numeric_and_collection_operators_are_deterministic(self) -> None:
        numeric = evaluate_canonical_rule(_build_rule_payload(operator="between", value=[2, 5]), {"controlled_field": 4})
        inclusion = evaluate_canonical_rule(_build_rule_payload(rule_id="rule_022", operator="in", value=["alpha", "beta"]), {"controlled_field": "alpha"})
        contains = evaluate_canonical_rule(_build_rule_payload(rule_id="rule_023", operator="contains", value="needle"), {"controlled_field": "haystack needle here"})
        self.assertEqual(numeric["result"], "matched")
        self.assertEqual(inclusion["result"], "matched")
        self.assertEqual(contains["result"], "matched")

    def test_unsupported_operator_returns_unsupported_without_mutation(self) -> None:
        result = evaluate_canonical_rule(_build_rule_payload(operator="starts_with", value="abc"), {"controlled_field": "abcdef"})
        self.assertIn(result["result"], {"blocked", "unsupported"})
        self.assertIn("canonical_rule_operator_unsupported", result["blockers"])
        self.assertEqual(result["persistent_writes"], 0)

    def test_deactivate_rule_removes_active_index_and_preserves_audit_record(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            create_canonical_rule(_build_rule_payload(), confirmation="CREATE_RULE", root=root)
            deactivated = deactivate_canonical_rule("rule_021", reason="verified_rollback", confirmation="DEACTIVATE_RULE", root=root)
            loaded = load_canonical_rule("rule_021", root=root)
            index = json.loads((root / "indexes" / "canonical_rule_index.json").read_text(encoding="utf-8"))
        self.assertEqual(deactivated["status"], "deactivated")
        self.assertEqual(loaded["rule"]["status"], "rolled_back")
        self.assertNotIn("rule_021", index["active_rule_ids"])

    def test_phase_9d_activation_success_path_uses_canonical_repository(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            proposal_id = _build_promoted_structured_proposal(root)
            with patch("backend.electional.proposal_rule_activation.validate_proposal_promotion_provenance", return_value=_valid_provenance()):
                review = save_proposal_rule_activation_decision(proposal_id, "approve", root=root / "store")["review"]
                activated = activate_rule_from_promoted_proposal(review["rule_activation_review_id"], confirmation="ACTIVATE", root=root / "store")
            loaded = load_canonical_rule(activated["rule_id"], require_active=True, root=root / "store")
            rolled_back = rollback_proposal_rule_activation(activated["activation_receipt_id"], confirmation="ROLLBACK", root=root / "store")
        self.assertEqual(activated["status"], "activated")
        self.assertEqual(loaded["status"], "loaded")
        self.assertEqual(loaded["rule"]["status"], "active")
        self.assertEqual(rolled_back["status"], "rollback_completed")

    def test_phase_9e_runtime_certification_success_path_uses_canonical_evaluator(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            proposal_id = _build_promoted_structured_proposal(root)
            with patch("backend.electional.proposal_rule_activation.validate_proposal_promotion_provenance", return_value=_valid_provenance()), patch(
                "backend.electional.rule_activation_revalidation.validate_proposal_promotion_provenance",
                return_value=_valid_provenance(),
            ):
                review = save_proposal_rule_activation_decision(proposal_id, "approve", root=root / "store")["review"]
                activation = activate_rule_from_promoted_proposal(review["rule_activation_review_id"], confirmation="ACTIVATE", root=root / "store")
                runtime = run_rule_runtime_contract_validation(activation["revalidation_id"], root=root / "store")
                revalidation_review = save_rule_activation_revalidation_decision(activation["revalidation_id"], "certify", root=root / "store")["review"]
                certified = complete_rule_activation_revalidation(revalidation_review["revalidation_review_id"], confirmation="CERTIFY", root=root / "store")
            receipt = json.loads((root / "store" / "rule_activation_certification_receipts" / f"{certified['certification_receipt_id']}.json").read_text(encoding="utf-8"))
            queue_item = json.loads((root / "store" / "source_impact_queue" / f"{activation['revalidation_id']}.json").read_text(encoding="utf-8"))
        self.assertEqual(runtime["status"], "passed")
        self.assertEqual(runtime["failed_case_count"], 0)
        self.assertEqual(certified["status"], "certified")
        self.assertEqual(receipt["certification_status"], "completed")
        self.assertEqual(queue_item["status"], "resolved")
        self.assertEqual(queue_item["resolution"], "rule_runtime_certified")
