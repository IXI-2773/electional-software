from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional.canonical_rule_runtime import create_canonical_rule
from backend.electional.rule_supersession import (
    analyze_rule_supersession_compatibility,
    build_rule_supersession_workspace,
    format_rule_supersession_report,
    rollback_rule_supersession,
    save_rule_supersession_decision,
    supersede_certified_rule,
    validate_rule_supersession_provenance,
)


def _old_rule(rule_id: str = "rule_021", *, scope: str = "documented_scope", value: object = "controlled_value") -> dict:
    return {
        "schema_version": "canonical_mutable_rule_v1",
        "rule_id": rule_id,
        "rule_type": "electional_constraint",
        "target": "controlled_target_x",
        "scope": scope,
        "condition": {"field": "controlled_field", "operator": "equals", "value": value},
        "operator": "equals",
        "value": value,
        "priority": 50,
        "enabled": True,
        "status": "active",
        "document_id": "doc_runtime_021",
        "source_proposal_id": "proposal_old_021",
        "source_promotion_receipt_id": "proposal_promotion_receipt_old_021",
        "source_rule_activation_review_id": "review_old_021",
        "source_revision": "source_rev_021",
        "activation_receipt_id": "proposal_rule_activation_receipt_021",
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _certified_old_rule(root: Path) -> str:
    rule = _old_rule()
    create_canonical_rule(rule, confirmation="CREATE_RULE", root=root)
    activation = {
        "schema_version": "proposal_rule_activation_receipt_v1",
        "activation_receipt_id": "proposal_rule_activation_receipt_021",
        "proposal_id": "proposal_old_021",
        "promotion_receipt_id": "proposal_promotion_receipt_old_021",
        "rule_activation_review_id": "review_old_021",
        "rule_id": "rule_021",
        "document_id": "doc_runtime_021",
        "source_revision": "source_rev_021",
        "citation_ids": ["citation_021"],
        "candidate_fingerprint": "fingerprint_old",
        "before_rule_index_hash": "before",
        "after_rule_index_hash": "after",
        "created_rule_hash": "sha256:" + __import__("hashlib").sha256(json.dumps(json.loads((root / "canonical_rules" / "rule_021.json").read_text(encoding="utf-8")), sort_keys=True, default=str).encode("utf-8")).hexdigest(),
        "activation_status": "completed",
        "rollback_available": True,
        "created_at_utc": "2026-01-01T00:00:00Z",
        "warnings": [],
    }
    revalidation_id = "impact_activation_021"
    certification = {
        "schema_version": "rule_activation_certification_receipt_v1",
        "certification_receipt_id": "rule_certification_receipt_021",
        "revalidation_id": revalidation_id,
        "revalidation_review_id": "rule_revalidation_review_021",
        "runtime_validation_id": "rule_runtime_validation_021",
        "rule_id": "rule_021",
        "proposal_id": "proposal_old_021",
        "activation_receipt_id": "proposal_rule_activation_receipt_021",
        "document_id": "doc_runtime_021",
        "source_revision": "source_rev_021",
        "rule_hash": activation["created_rule_hash"],
        "runtime_validation_fingerprint": "runtime_fingerprint_021",
        "required_case_count": 4,
        "passed_case_count": 4,
        "certification_status": "completed",
        "created_at_utc": "2026-01-02T00:00:00Z",
        "warnings": [],
    }
    queue_item = {
        "queue_item_id": revalidation_id,
        "document_id": "doc_runtime_021",
        "status": "resolved",
        "resolution": "rule_runtime_certified",
        "reason": "proposal_rule_activation",
        "activation_receipt_id": "proposal_rule_activation_receipt_021",
        "rule_id": "rule_021",
        "source_revision": "source_rev_021",
    }
    _write_json(root / "proposal_rule_activation_receipts" / "proposal_rule_activation_receipt_021.json", activation)
    _write_json(root / "rule_activation_certification_receipts" / "rule_certification_receipt_021.json", certification)
    _write_json(root / "source_impact_queue" / f"{revalidation_id}.json", queue_item)
    return "rule_021"


def _replacement_proposal(root: Path, proposal_id: str = "proposal_replace_021", *, scope: str = "documented_scope", value: object = "replacement_value", supersedes: str = "rule_021", status: str = "promoted") -> str:
    proposal = {
        "proposal_id": proposal_id,
        "document_id": "doc_runtime_021",
        "source_revision": "source_rev_021",
        "status": status,
        "accepted_citation_ids": ["citation_021"],
        "supersedes_rule_id": supersedes,
        "rule_mapping": {
            "rule_type": "electional_constraint",
            "target": "controlled_target_x",
            "scope": scope,
            "condition": {"field": "controlled_field", "operator": "equals", "value": value},
            "operator": "equals",
            "value": value,
            "priority": 50,
            "enabled": True,
        },
    }
    receipt = {
        "promotion_receipt_id": f"proposal_promotion_receipt_{proposal_id}",
        "proposal_id": proposal_id,
        "document_id": "doc_runtime_021",
        "source_revision": "source_rev_021",
        "promotion_status": "completed",
        "created_at_utc": "2026-01-03T00:00:00Z",
    }
    _write_json(root / "proposals" / f"{proposal_id}.json", proposal)
    _write_json(root / "proposal_promotion_receipts" / f"{receipt['promotion_receipt_id']}.json", receipt)
    return proposal_id


class RuleSupersessionTest(TestCase):
    def test_certified_active_rule_and_promoted_replacement_load_for_review(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _certified_old_rule(root)
            proposal_id = _replacement_proposal(root)
            workspace = build_rule_supersession_workspace("rule_021", proposal_id, root=root)
        self.assertEqual(workspace["old_rule_status"], "active")
        self.assertEqual(workspace["old_rule_certification_status"], "completed")
        self.assertEqual(workspace["replacement_proposal_status"], "promoted")
        self.assertEqual(workspace["replacement_mapping_status"], "valid")

    def test_uncertified_old_rule_or_stale_replacement_blocks_supersession(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _certified_old_rule(root)
            (root / "rule_activation_certification_receipts" / "rule_certification_receipt_021.json").unlink()
            proposal_id = _replacement_proposal(root)
            proposal = json.loads((root / "proposals" / f"{proposal_id}.json").read_text(encoding="utf-8"))
            proposal["source_revision"] = "changed_revision"
            _write_json(root / "proposals" / f"{proposal_id}.json", proposal)
            result = validate_rule_supersession_provenance("rule_021", proposal_id, root=root)
        self.assertFalse(result["valid"])
        self.assertIn("old_rule_certification_missing", result["blockers"])
        self.assertIn("replacement_source_revision_changed", result["blockers"])

    def test_exact_duplicate_or_incompatible_replacement_is_blocked(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _certified_old_rule(root)
            duplicate_id = _replacement_proposal(root, proposal_id="proposal_duplicate_021", value="controlled_value")
            incompatible_id = _replacement_proposal(root, proposal_id="proposal_incompatible_021", supersedes="rule_021")
            incompatible = json.loads((root / "proposals" / f"{incompatible_id}.json").read_text(encoding="utf-8"))
            incompatible["rule_mapping"]["target"] = "different_target"
            _write_json(root / "proposals" / f"{incompatible_id}.json", incompatible)
            duplicate = analyze_rule_supersession_compatibility("rule_021", duplicate_id, root=root)
            incompatible_result = analyze_rule_supersession_compatibility("rule_021", incompatible_id, root=root)
        self.assertIn("replacement_exact_duplicate", duplicate["blockers"])
        self.assertIn("replacement_incompatible", incompatible_result["blockers"])

    def test_scope_change_requires_explicit_acknowledgement(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _certified_old_rule(root)
            proposal_id = _replacement_proposal(root, scope="documented_scope_narrow")
            blocked = save_rule_supersession_decision("rule_021", proposal_id, "approve", root=root)
            saved = save_rule_supersession_decision("rule_021", proposal_id, "approve", acknowledge_scope_change=True, root=root)
        self.assertIn("scope_change_acknowledgement_required", blocked["blockers"])
        self.assertEqual(saved["review"]["review_status"], "approved")

    def test_reject_and_request_changes_require_note(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _certified_old_rule(root)
            proposal_id = _replacement_proposal(root)
            rejected = save_rule_supersession_decision("rule_021", proposal_id, "reject", root=root)
            changes = save_rule_supersession_decision("rule_021", proposal_id, "request_changes", reviewer_note="Adjust scope", root=root)
        self.assertIn("reviewer_note_required", rejected["blockers"])
        self.assertEqual(changes["review"]["review_status"], "changes_requested")

    def test_approved_replacement_requires_supersede_confirmation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _certified_old_rule(root)
            proposal_id = _replacement_proposal(root)
            review = save_rule_supersession_decision("rule_021", proposal_id, "approve", root=root)["review"]
            blocked = supersede_certified_rule(review["supersession_review_id"], root=root)
        self.assertIn("supersede_confirmation_required", blocked["blockers"])

    def test_successful_supersession_creates_one_active_successor_chain_receipt_and_revalidation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _certified_old_rule(root)
            proposal_id = _replacement_proposal(root)
            review = save_rule_supersession_decision("rule_021", proposal_id, "approve", root=root)["review"]
            result = supersede_certified_rule(review["supersession_review_id"], confirmation="SUPERSEDE", root=root)
            old_rule = json.loads((root / "canonical_rules" / "rule_021.json").read_text(encoding="utf-8"))
            new_rule = json.loads((root / "canonical_rules" / f"{result['new_rule_id']}.json").read_text(encoding="utf-8"))
            index = json.loads((root / "indexes" / "canonical_rule_index.json").read_text(encoding="utf-8"))
            chain = json.loads((root / "rule_supersession_chains" / f"{result['version_chain_id']}.json").read_text(encoding="utf-8"))
            receipt = json.loads((root / "rule_supersession_receipts" / f"{result['supersession_receipt_id']}.json").read_text(encoding="utf-8"))
            revalidation = json.loads((root / "source_impact_queue" / f"{result['revalidation_id']}.json").read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "superseded")
        self.assertEqual(old_rule["status"], "inactive")
        self.assertEqual(new_rule["status"], "active")
        self.assertNotIn("rule_021", index["active_rule_ids"])
        self.assertEqual(index["active_rule_ids"], [result["new_rule_id"]])
        self.assertEqual(chain["current_active_rule_id"], result["new_rule_id"])
        self.assertEqual(sum(1 for item in chain["versions"] if item["status"] == "active"), 1)
        self.assertEqual(receipt["supersession_status"], "completed")
        self.assertEqual(revalidation["status"], "pending_review")
        self.assertNotIn("certification_receipt_id", new_rule)

    def test_api_supersession_idempotency_rollback_and_public_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _certified_old_rule(root)
            proposal_id = _replacement_proposal(root)
            review = save_rule_supersession_decision("rule_021", proposal_id, "approve", reviewer_note="private note", root=root)["review"]
            first = supersede_certified_rule(review["supersession_review_id"], confirmation="SUPERSEDE", root=root)
            second = supersede_certified_rule(review["supersession_review_id"], confirmation="SUPERSEDE", root=root)
            report = format_rule_supersession_report(supersession_review_id=review["supersession_review_id"], supersession_receipt_id=first["supersession_receipt_id"], public_safe=True, root=root)
            rollback = rollback_rule_supersession(first["supersession_receipt_id"], confirmation="ROLLBACK_SUPERSESSION", root=root)
            new_cert = {
                "schema_version": "rule_activation_certification_receipt_v1",
                "certification_receipt_id": "rule_certification_receipt_new",
                "revalidation_id": "impact_new_rule",
                "rule_id": first["new_rule_id"],
                "certification_status": "completed",
            }
            _write_json(root / "rule_activation_certification_receipts" / "rule_certification_receipt_new.json", new_cert)
            blocked = rollback_rule_supersession(first["supersession_receipt_id"], confirmation="ROLLBACK_SUPERSESSION", root=root)
            restored = json.loads((root / "canonical_rules" / "rule_021.json").read_text(encoding="utf-8"))
            rolled_back = json.loads((root / "canonical_rules" / f"{first['new_rule_id']}.json").read_text(encoding="utf-8"))
        self.assertEqual(second["status"], "already_superseded")
        self.assertEqual(rollback["status"], "rollback_completed")
        self.assertEqual(restored["status"], "active")
        self.assertEqual(rolled_back["status"], "rolled_back")
        self.assertIn("Rule Supersession Report", report)
        self.assertNotIn("private note", report)
        self.assertNotIn(str(root), report)
        self.assertIn("rollback_blocked_after_certification", blocked["blockers"])
