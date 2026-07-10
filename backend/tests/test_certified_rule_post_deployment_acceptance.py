from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from backend.electional import certified_rule_post_deployment_acceptance as acceptance
from backend.electional import certified_rule_production_deployment as production_deployment
from backend.electional import canonical_rule_runtime as runtime
from backend.electional import production_deployment_adapter as adapter_backend
from backend.electional import production_target_descriptor as descriptor_backend
from backend.tests.test_certified_rule_controlled_integration import _write_json
from backend.tests.test_certified_rule_production_authorization import _production_descriptor
from backend.tests.test_certified_rule_production_deployment import _authorized_inputs


def _deployed_inputs(root: Path) -> dict[str, object]:
    built = _authorized_inputs(root)
    plan = production_deployment.build_certified_rule_production_deployment_plan(
        built["rule_id"], built["production_authorization_saved"]["production_authorization_result_id"], "production_target_primary", root=root
    )
    run = production_deployment.execute_certified_rule_production_deployment(
        plan["production_deployment_plan_id"],
        confirmation=production_deployment.REQUIRED_CONFIRMATION,
        root=root,
    )
    built["production_deployment_plan"] = plan
    built["production_deployment_run"] = run
    return built


class CertifiedRulePostDeploymentAcceptanceTest(TestCase):
    def test_accept_uses_current_state_rereads_and_missing_optional_telemetry_does_not_block(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            workspace = acceptance.build_certified_rule_post_deployment_acceptance_workspace(
                built["production_deployment_run"]["production_deployment_result_id"], root=root
            )
            first = acceptance.build_certified_rule_post_deployment_acceptance_plan(
                built["production_deployment_run"]["production_deployment_result_id"], root=root
            )
            second = acceptance.build_certified_rule_post_deployment_acceptance_plan(
                built["production_deployment_run"]["production_deployment_result_id"], root=root
            )
            saved = acceptance.save_certified_rule_post_deployment_acceptance_decision(
                first["post_deployment_acceptance_plan_id"],
                "accept",
                confirmation=acceptance.REQUIRED_CONFIRMATION,
                root=root,
            )
            loaded = acceptance.load_certified_rule_post_deployment_acceptance_result(
                saved["post_deployment_acceptance_result_id"], root=root
            )
        self.assertEqual(workspace["status"], "ready_for_planning")
        self.assertEqual(first["plan_fingerprint"], second["plan_fingerprint"])
        self.assertEqual(saved["status"], "accepted")
        self.assertEqual(loaded["post_deployment_acceptance_result"]["optional_telemetry_status"], "available_not_required")
        self.assertEqual(loaded["post_deployment_acceptance_result"]["current_verification_status"], "verified_committed")

    def test_missing_required_phase_9v_evidence_blocks_and_wrong_confirmation_writes_nothing(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            receipt_path = root / production_deployment.RECEIPT_DIR / f"{production_deployment._safe_id(built['production_deployment_run']['production_deployment_receipt_id'])}.json"
            receipt_path.unlink()
            blocked = acceptance.validate_certified_rule_post_deployment_acceptance_eligibility(
                built["production_deployment_run"]["production_deployment_result_id"], root=root
            )

            root2 = Path(tmp) / "store2"
            built2 = _deployed_inputs(root2)
            plan = acceptance.build_certified_rule_post_deployment_acceptance_plan(
                built2["production_deployment_run"]["production_deployment_result_id"], root=root2
            )
            before = list((root2 / acceptance.RESULT_DIR).glob("*.json"))
            wrong = acceptance.save_certified_rule_post_deployment_acceptance_decision(
                plan["post_deployment_acceptance_plan_id"], "accept", confirmation="WRONG", root=root2
            )
            after = list((root2 / acceptance.RESULT_DIR).glob("*.json"))
        self.assertIn("production_deployment_receipt_missing", blocked["blockers"])
        self.assertEqual(wrong["status"], "blocked")
        self.assertEqual(before, after)

    def test_accept_cannot_be_recorded_after_rollback_or_deactivation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            rollback = adapter_backend.rollback_production_deployment(
                "production_target_primary",
                built["production_deployment_run"]["production_transaction_id"],
                confirmation=adapter_backend.ROLLBACK_CONFIRMATION,
                root=root,
            )
            plan = acceptance.build_certified_rule_post_deployment_acceptance_plan(
                built["production_deployment_run"]["production_deployment_result_id"], root=root
            )
        self.assertEqual(rollback["status"], "completed")
        self.assertEqual(plan["status"], "stale")
        self.assertIn("current_production_transaction_not_verified_committed", plan["blockers"])

    def test_reject_does_not_roll_back_or_mutate_deployment(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            state_before = adapter_backend.read_production_deployment_state(
                "production_target_primary",
                transaction_id=built["production_deployment_run"]["production_transaction_id"],
                root=root,
            )
            deployed_rule_before = (root / "canonical_rules" / f"{built['production_deployment_run']['deployed_rule_id']}.json").read_text(encoding="utf-8")
            plan = acceptance.build_certified_rule_post_deployment_acceptance_plan(
                built["production_deployment_run"]["production_deployment_result_id"], root=root
            )
            with patch.object(acceptance.adapter_backend, "rollback_production_deployment", side_effect=AssertionError("should not rollback")):
                saved = acceptance.save_certified_rule_post_deployment_acceptance_decision(
                    plan["post_deployment_acceptance_plan_id"], "reject", confirmation=acceptance.REQUIRED_CONFIRMATION, root=root
                )
            state_after = adapter_backend.read_production_deployment_state(
                "production_target_primary",
                transaction_id=built["production_deployment_run"]["production_transaction_id"],
                root=root,
            )
            deployed_rule_after = (root / "canonical_rules" / f"{built['production_deployment_run']['deployed_rule_id']}.json").read_text(encoding="utf-8")
        self.assertEqual(saved["status"], "rejected")
        self.assertEqual(state_before["production_state_fingerprint"], state_after["production_state_fingerprint"])
        self.assertEqual(deployed_rule_before, deployed_rule_after)

    def test_continue_observation_does_not_mutate_and_stored_phase_9v_result_is_not_current_verification(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            plan = acceptance.build_certified_rule_post_deployment_acceptance_plan(
                built["production_deployment_run"]["production_deployment_result_id"], root=root
            )
            continued = acceptance.save_certified_rule_post_deployment_acceptance_decision(
                plan["post_deployment_acceptance_plan_id"],
                "continue_observation",
                confirmation=acceptance.REQUIRED_CONFIRMATION,
                root=root,
            )
            deployed_rule_path = root / "canonical_rules" / f"{built['production_deployment_run']['deployed_rule_id']}.json"
            deployed_payload = json.loads(deployed_rule_path.read_text(encoding="utf-8"))
            deployed_payload["status"] = "inactive"
            _write_json(deployed_rule_path, deployed_payload)
            blocked = acceptance.validate_certified_rule_post_deployment_acceptance_eligibility(
                built["production_deployment_run"]["production_deployment_result_id"], root=root
            )
        self.assertEqual(continued["status"], "continue_observation")
        self.assertIn("deployed_rule_missing_or_inactive", blocked["blockers"])

    def test_conflicting_decisions_do_not_overwrite_and_identical_rerun_is_zero_write(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            plan = acceptance.build_certified_rule_post_deployment_acceptance_plan(
                built["production_deployment_run"]["production_deployment_result_id"], root=root
            )
            first = acceptance.save_certified_rule_post_deployment_acceptance_decision(
                plan["post_deployment_acceptance_plan_id"], "accept", confirmation=acceptance.REQUIRED_CONFIRMATION, root=root
            )
            rerun = acceptance.save_certified_rule_post_deployment_acceptance_decision(
                plan["post_deployment_acceptance_plan_id"], "accept", confirmation=acceptance.REQUIRED_CONFIRMATION, root=root
            )
            conflict = acceptance.save_certified_rule_post_deployment_acceptance_decision(
                plan["post_deployment_acceptance_plan_id"], "reject", confirmation=acceptance.REQUIRED_CONFIRMATION, root=root
            )
        self.assertEqual(first["status"], "accepted")
        self.assertEqual(rerun["status"], "already_recorded")
        self.assertEqual(rerun["writes_performed"], 0)
        self.assertEqual(conflict["status"], "conflict")

    def test_unrelated_deployed_instance_remains_unchanged(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            secondary_descriptor = _production_descriptor("production_target_secondary")
            descriptor_backend.register_production_target_descriptor(secondary_descriptor, root=root)
            seed = _authorized_inputs(root)
            bundle = production_deployment._load_bundle(
                root,
                seed["rule_id"],
                seed["production_authorization_saved"]["production_authorization_result_id"],
                "production_target_primary",
            )
            package = production_deployment._build_deployment_package(bundle)
            original_source_rule = runtime.load_canonical_rule(seed["rule_id"], require_active=True, root=root)["rule"]
            assert isinstance(original_source_rule, dict)
            secondary_source_rule = dict(original_source_rule)
            secondary_source_rule["rule_id"] = f"{seed['rule_id']}_secondary_source"
            secondary_source_rule["target"] = "production_target_secondary"
            secondary_source_rule["rule_fingerprint"] = runtime._rule_fingerprint_from_payload(secondary_source_rule)
            _write_json(root / "canonical_rules" / f"{runtime._safe_id(secondary_source_rule['rule_id'])}.json", secondary_source_rule)
            runtime_base = runtime._ensure_runtime_dirs(root)
            runtime_index = runtime._index_with_rule(runtime._load_index(runtime_base), secondary_source_rule)
            runtime._atomic_write_json(runtime._index_path(runtime_base), runtime_index)
            package["canonical_rule_id"] = secondary_source_rule["rule_id"]
            package["canonical_rule_fingerprint"] = secondary_source_rule["rule_fingerprint"]
            package["canonical_rule_payload"] = secondary_source_rule
            package["production_target_id"] = "production_target_secondary"
            package["production_target_descriptor_fingerprint"] = secondary_descriptor["descriptor_fingerprint"]
            package["production_adapter_manifest_fingerprint"] = secondary_descriptor["adapter_manifest_fingerprint"]
            package["production_adapter_capability_fingerprint"] = secondary_descriptor["adapter_capability_fingerprint"]
            package = adapter_backend._normalized_deployment_package(package)
            package["package_fingerprint"] = adapter_backend._deployment_package_fingerprint(package)
            applied = adapter_backend.apply_production_deployment("production_target_secondary", package, confirmation=adapter_backend.APPLY_CONFIRMATION, root=root)
            self.assertEqual(applied["status"], "pending_verification")
            committed = adapter_backend.commit_production_deployment("production_target_secondary", applied["transaction_id"], applied["pending_state_fingerprint"], confirmation=adapter_backend.COMMIT_CONFIRMATION, root=root)
            other_state_before = adapter_backend.read_production_deployment_state("production_target_secondary", transaction_id=applied["transaction_id"], root=root)
            other_rule_before = (root / "canonical_rules" / f"{committed['deployed_rule_id']}.json").read_text(encoding="utf-8")
            primary_plan = production_deployment.build_certified_rule_production_deployment_plan(
                seed["rule_id"], seed["production_authorization_saved"]["production_authorization_result_id"], "production_target_primary", root=root
            )
            primary_run = production_deployment.execute_certified_rule_production_deployment(
                primary_plan["production_deployment_plan_id"],
                confirmation=production_deployment.REQUIRED_CONFIRMATION,
                root=root,
            )
            plan = acceptance.build_certified_rule_post_deployment_acceptance_plan(
                primary_run["production_deployment_result_id"], root=root
            )
            saved = acceptance.save_certified_rule_post_deployment_acceptance_decision(
                plan["post_deployment_acceptance_plan_id"], "accept", confirmation=acceptance.REQUIRED_CONFIRMATION, root=root
            )
            other_state_after = adapter_backend.read_production_deployment_state("production_target_secondary", transaction_id=applied["transaction_id"], root=root)
            other_rule_after = (root / "canonical_rules" / f"{committed['deployed_rule_id']}.json").read_text(encoding="utf-8")
        self.assertEqual(saved["status"], "accepted")
        self.assertEqual(other_state_before["transaction_id"], other_state_after["transaction_id"])
        self.assertEqual(other_state_before["deployed_rule_id"], other_state_after["deployed_rule_id"])
        self.assertEqual(other_state_after["verification_status"], "verified_committed")
        self.assertEqual(other_rule_before, other_rule_after)

    def test_health_summary_and_report_are_public_safe(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            plan = acceptance.build_certified_rule_post_deployment_acceptance_plan(
                built["production_deployment_run"]["production_deployment_result_id"], root=root
            )
            saved = acceptance.save_certified_rule_post_deployment_acceptance_decision(
                plan["post_deployment_acceptance_plan_id"], "accept", confirmation=acceptance.REQUIRED_CONFIRMATION, root=root
            )
            health = acceptance.get_certified_rule_post_deployment_acceptance_health(plan["post_deployment_acceptance_plan_id"], root=root)
            summary = acceptance.get_certified_rule_post_deployment_acceptance_summary(saved["post_deployment_acceptance_result_id"], root=root)
            report = acceptance.format_certified_rule_post_deployment_acceptance_report(saved["post_deployment_acceptance_result_id"], saved["post_deployment_acceptance_receipt_id"], True, root=root)
        self.assertEqual(health["status"], "healthy")
        self.assertEqual(summary["status"], "accepted")
        self.assertIn("No deployment, rollback, scoring, or Fast Lane execution was performed by Phase 9W.", report)
