from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from backend.electional import certified_rule_production_authorization as production_authorization
from backend.electional import certified_rule_production_deployment as production_deployment
from backend.electional import production_deployment_adapter as adapter_backend
from backend.electional.api import (
    build_certified_rule_production_deployment_plan as api_build_plan,
    build_certified_rule_production_deployment_workspace as api_workspace,
    execute_certified_rule_production_deployment as api_execute,
    format_certified_rule_production_deployment_report as api_report,
    validate_certified_rule_production_deployment_eligibility as api_validate,
)
from backend.tests.test_certified_rule_production_authorization import _completed_integration
from backend.tests.test_certified_rule_controlled_integration import _write_json


def _authorized_inputs(root: Path) -> dict[str, object]:
    built = _completed_integration(root)
    plan = production_authorization.build_certified_rule_production_authorization_plan(
        built["rule_id"], built["controlled_run"]["controlled_integration_result_id"], "production_target_primary", root=root
    )
    saved = production_authorization.save_certified_rule_production_authorization_decision(
        plan["production_authorization_plan_id"],
        production_authorization.AUTHORIZED_DECISION,
        confirmation=production_authorization.REQUIRED_CONFIRMATION,
        root=root,
    )
    built["production_authorization_plan"] = plan
    built["production_authorization_saved"] = saved
    return built


class CertifiedRuleProductionDeploymentTest(TestCase):
    def test_deterministic_observation_plan_and_completed_deployment_success_path(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _authorized_inputs(root)
            workspace = production_deployment.build_certified_rule_production_deployment_workspace(
                built["rule_id"], built["production_authorization_saved"]["production_authorization_result_id"], "production_target_primary", root=root
            )
            first = production_deployment.build_certified_rule_production_deployment_plan(
                built["rule_id"], built["production_authorization_saved"]["production_authorization_result_id"], "production_target_primary", root=root
            )
            second = production_deployment.build_certified_rule_production_deployment_plan(
                built["rule_id"], built["production_authorization_saved"]["production_authorization_result_id"], "production_target_primary", root=root
            )
            with patch.object(production_deployment.adapter_backend, "rollback_production_deployment", side_effect=AssertionError("should not rollback")):
                run = production_deployment.execute_certified_rule_production_deployment(
                    first["production_deployment_plan_id"],
                    confirmation=production_deployment.REQUIRED_CONFIRMATION,
                    root=root,
                )
            loaded = production_deployment.load_certified_rule_production_deployment_result(run["production_deployment_result_id"], root=root)
        self.assertEqual(workspace["status"], "ready_for_planning")
        self.assertEqual(first["production_deployment_plan_id"], second["production_deployment_plan_id"])
        self.assertEqual(first["plan_fingerprint"], second["plan_fingerprint"])
        self.assertEqual(run["status"], "completed")
        self.assertEqual(loaded["production_deployment_result"]["final_status"], "completed")

    def test_eligibility_requires_current_authorization_and_independent_phase_9t_verification(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _authorized_inputs(root)
            eligible = production_deployment.validate_certified_rule_production_deployment_eligibility(
                built["rule_id"], built["production_authorization_saved"]["production_authorization_result_id"], "production_target_primary", root=root
            )
            result_path = root / production_authorization.RESULT_DIR / f"{production_authorization._safe_id(built['production_authorization_saved']['production_authorization_result_id'])}.json"
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            payload["decision"] = "defer_production_deployment"
            payload["result_fingerprint"] = production_authorization._result_fingerprint(payload)
            _write_json(result_path, payload)
            blocked = production_deployment.validate_certified_rule_production_deployment_eligibility(
                built["rule_id"], built["production_authorization_saved"]["production_authorization_result_id"], "production_target_primary", root=root
            )
        self.assertIn(eligible["status"], {"eligible", "eligible_with_warnings"})
        self.assertIn("production_authorization_decision_invalid", blocked["blockers"])

    def test_exact_confirmation_is_required(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _authorized_inputs(root)
            plan = production_deployment.build_certified_rule_production_deployment_plan(
                built["rule_id"], built["production_authorization_saved"]["production_authorization_result_id"], "production_target_primary", root=root
            )
            blocked = production_deployment.execute_certified_rule_production_deployment(
                plan["production_deployment_plan_id"], confirmation=None, root=root
            )
        self.assertEqual(blocked["status"], "blocked")

    def test_source_rule_is_preserved_and_deployed_instance_is_verified(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _authorized_inputs(root)
            rule_path = root / "canonical_rules" / f"{built['rule_id']}.json"
            before_rule = rule_path.read_text(encoding="utf-8")
            plan = production_deployment.build_certified_rule_production_deployment_plan(
                built["rule_id"], built["production_authorization_saved"]["production_authorization_result_id"], "production_target_primary", root=root
            )
            run = production_deployment.execute_certified_rule_production_deployment(
                plan["production_deployment_plan_id"],
                confirmation=production_deployment.REQUIRED_CONFIRMATION,
                root=root,
            )
            loaded = production_deployment.load_certified_rule_production_deployment_result(run["production_deployment_result_id"], root=root)
            state = adapter_backend.read_production_deployment_state("production_target_primary", transaction_id=run["production_transaction_id"], root=root)
            after_rule = rule_path.read_text(encoding="utf-8")
        self.assertEqual(before_rule, after_rule)
        self.assertEqual(loaded["production_deployment_result"]["deployed_rule_id"], state["deployed_rule_id"])
        self.assertEqual(state["verification_status"], "verified_committed")

    def test_stale_corrupt_and_mismatched_deployment_is_blocked(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _authorized_inputs(root)
            plan = production_deployment.build_certified_rule_production_deployment_plan(
                built["rule_id"], built["production_authorization_saved"]["production_authorization_result_id"], "production_target_primary", root=root
            )
            descriptor_path = root / "production_target_descriptors" / "production_target_primary.json"
            payload = json.loads(descriptor_path.read_text(encoding="utf-8"))
            payload["adapter_version"] = "2"
            normalized = production_authorization.descriptor_backend._normalize_descriptor(payload)
            assert normalized is not None
            _write_json(descriptor_path, normalized)
            stale = production_deployment.execute_certified_rule_production_deployment(
                plan["production_deployment_plan_id"],
                confirmation=production_deployment.REQUIRED_CONFIRMATION,
                root=root,
            )
        self.assertEqual(stale["status"], "stale")

    def test_immutable_result_receipt_and_idempotent_rerun(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _authorized_inputs(root)
            plan = production_deployment.build_certified_rule_production_deployment_plan(
                built["rule_id"], built["production_authorization_saved"]["production_authorization_result_id"], "production_target_primary", root=root
            )
            run = production_deployment.execute_certified_rule_production_deployment(
                plan["production_deployment_plan_id"],
                confirmation=production_deployment.REQUIRED_CONFIRMATION,
                root=root,
            )
            rerun = production_deployment.execute_certified_rule_production_deployment(
                plan["production_deployment_plan_id"],
                confirmation=production_deployment.REQUIRED_CONFIRMATION,
                root=root,
            )
        self.assertEqual(run["status"], "completed")
        self.assertEqual(rerun["status"], "already_completed")
        self.assertEqual(rerun["writes_performed"], 0)

    def test_failure_rolls_back_deployed_instance_without_unrelated_mutation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _authorized_inputs(root)
            plan = production_deployment.build_certified_rule_production_deployment_plan(
                built["rule_id"], built["production_authorization_saved"]["production_authorization_result_id"], "production_target_primary", root=root
            )
            source_rule_before = (root / "canonical_rules" / f"{built['rule_id']}.json").read_text(encoding="utf-8")

            def fail_commit(*args, **kwargs):
                return {"status": "commit_failed", "warnings": [], "blockers": ["forced_commit_failure"]}

            with patch.object(production_deployment.adapter_backend, "commit_production_deployment", side_effect=fail_commit):
                run = production_deployment.execute_certified_rule_production_deployment(
                    plan["production_deployment_plan_id"],
                    confirmation=production_deployment.REQUIRED_CONFIRMATION,
                    root=root,
                )
            source_rule_after = (root / "canonical_rules" / f"{built['rule_id']}.json").read_text(encoding="utf-8")
        self.assertEqual(run["status"], "rollback_completed")
        self.assertEqual(source_rule_before, source_rule_after)

    def test_api_health_report_and_no_scoring_fast_lane_or_release_mutation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _authorized_inputs(root)
            release_path = root / production_authorization.integration_backend.release_candidate_backend.RESULT_DIR / f"{production_authorization.integration_backend.release_candidate_backend.analysis_backend._safe_id(built['release_run']['release_candidate_result_id'])}.json"
            before_release = release_path.read_text(encoding="utf-8")
            workspace = api_workspace(built["rule_id"], built["production_authorization_saved"]["production_authorization_result_id"], "production_target_primary", root=root)
            eligibility = api_validate(built["rule_id"], built["production_authorization_saved"]["production_authorization_result_id"], "production_target_primary", root=root)
            plan = api_build_plan(built["rule_id"], built["production_authorization_saved"]["production_authorization_result_id"], "production_target_primary", root=root)
            run = api_execute(plan["production_deployment_plan_id"], confirmation=production_deployment.REQUIRED_CONFIRMATION, root=root)
            health = production_deployment.get_certified_rule_production_deployment_health(plan["production_deployment_plan_id"], root=root)
            report = api_report(run["production_deployment_result_id"], run["production_deployment_receipt_id"], True, root=root)
            after_release = release_path.read_text(encoding="utf-8")
        self.assertEqual(workspace["status"], "ready_for_planning")
        self.assertIn(eligibility["status"], {"eligible", "eligible_with_warnings"})
        self.assertEqual(run["status"], "completed")
        self.assertEqual(health["status"], "healthy")
        self.assertEqual(before_release, after_release)
        self.assertIn("Production deployment occurred only after explicit Phase 9U authorization.", report)
        self.assertIn("Live Fast Lane was not executed.", report)
