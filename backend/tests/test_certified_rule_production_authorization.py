from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from backend.electional import certified_rule_production_authorization as production_authorization
from backend.electional import production_target_descriptor as descriptor_backend
from backend.electional.api import (
    build_certified_rule_production_authorization_plan as api_build_plan,
    build_certified_rule_production_authorization_workspace as api_workspace,
    format_certified_rule_production_authorization_report as api_report,
    save_certified_rule_production_authorization_decision as api_save_decision,
    validate_certified_rule_production_authorization_eligibility as api_validate,
)
from backend.tests.test_certified_rule_controlled_integration import _qualified_release_inputs, _write_json
from backend.electional import certified_rule_controlled_integration as controlled_integration
from backend.electional import certified_rule_controlled_integration_target as target


def _production_descriptor(target_id: str = "production_target_primary") -> dict[str, object]:
    payload = {
        "schema_version": descriptor_backend.DESCRIPTOR_SCHEMA_VERSION,
        "target_id": target_id,
        "environment_class": "production",
        "target_kind": descriptor_backend.TARGET_KIND,
        "adapter_name": "authoritative_production_adapter",
        "adapter_version": "1",
        "adapter_manifest": {
            "schema_version": descriptor_backend.MANIFEST_SCHEMA_VERSION,
            "adapter_name": "authoritative_production_adapter",
            "adapter_version": "1",
        },
        "adapter_capabilities": {
            "schema_version": descriptor_backend.CAPABILITIES_SCHEMA_VERSION,
            "capabilities": ["describe_target", "read_release_state"],
        },
        "descriptor_access_mode": descriptor_backend.ACCESS_MODE,
        "authorization_scope": descriptor_backend.AUTHORIZATION_SCOPE,
        "operational_entrypoints_exposed": [],
        "deployment_executed": False,
        "activation_executed": False,
        "production_scoring_executed": False,
        "live_fast_lane_executed": False,
    }
    normalized = descriptor_backend._normalize_descriptor(payload)
    assert normalized is not None
    return normalized


def _completed_integration(root: Path) -> dict[str, object]:
    built = _qualified_release_inputs(root)
    plan = controlled_integration.build_certified_rule_controlled_integration_plan(
        built["rule_id"], built["release_run"]["release_candidate_result_id"], target.DEFAULT_TARGET_ID, root=root
    )
    run = controlled_integration.execute_certified_rule_controlled_integration(
        plan["controlled_integration_plan_id"], confirmation=controlled_integration.REQUIRED_CONFIRMATION, root=root
    )
    descriptor_backend.register_production_target_descriptor(_production_descriptor(), root=root)
    built["controlled_plan"] = plan
    built["controlled_run"] = run
    return built


class CertifiedRuleProductionAuthorizationTest(TestCase):
    def test_completed_controlled_integration_authorizes_and_persists_receipt(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _completed_integration(root)
            workspace = production_authorization.build_certified_rule_production_authorization_workspace(
                built["rule_id"], built["controlled_run"]["controlled_integration_result_id"], "production_target_primary", root=root
            )
            plan = production_authorization.build_certified_rule_production_authorization_plan(
                built["rule_id"], built["controlled_run"]["controlled_integration_result_id"], "production_target_primary", root=root
            )
            saved = production_authorization.save_certified_rule_production_authorization_decision(
                plan["production_authorization_plan_id"],
                production_authorization.AUTHORIZED_DECISION,
                confirmation=production_authorization.REQUIRED_CONFIRMATION,
                root=root,
            )
            loaded = production_authorization.load_certified_rule_production_authorization_result(
                saved["production_authorization_result_id"], root=root
            )
        self.assertEqual(workspace["status"], "ready_for_planning")
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(saved["status"], "authorized")
        self.assertEqual(loaded["production_authorization_result"]["status"], "authorized")
        self.assertEqual(loaded["production_authorization_result"]["decision"], production_authorization.AUTHORIZED_DECISION)

    def test_incomplete_stale_or_failed_controlled_integration_is_blocked(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _completed_integration(root)
            result_path = root / controlled_integration.RESULT_DIR / f"{controlled_integration._safe_id(built['controlled_run']['controlled_integration_result_id'])}.json"
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            payload["final_status"] = "commit_failed"
            payload["result_fingerprint"] = controlled_integration._result_fingerprint(payload)
            _write_json(result_path, payload)
            blocked = production_authorization.validate_certified_rule_production_authorization_eligibility(
                built["rule_id"], built["controlled_run"]["controlled_integration_result_id"], "production_target_primary", root=root
            )
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("controlled_integration_not_completed", blocked["blockers"])

    def test_missing_or_invalid_production_target_descriptor_is_blocked(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _completed_integration(root)
            missing = production_authorization.validate_certified_rule_production_authorization_eligibility(
                built["rule_id"], built["controlled_run"]["controlled_integration_result_id"], "missing_target", root=root
            )
            path = root / descriptor_backend.DESCRIPTOR_DIR / "production_target_primary.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["environment_class"] = "isolated_non_production"
            _write_json(path, payload)
            invalid = production_authorization.validate_certified_rule_production_authorization_eligibility(
                built["rule_id"], built["controlled_run"]["controlled_integration_result_id"], "production_target_primary", root=root
            )
        self.assertIn("production_target_descriptor_missing", missing["blockers"])
        self.assertIn("production_target_environment_invalid", invalid["blockers"])

    def test_plan_is_deterministic_and_uses_read_only_descriptor_and_committed_state(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _completed_integration(root)
            first = production_authorization.build_certified_rule_production_authorization_plan(
                built["rule_id"], built["controlled_run"]["controlled_integration_result_id"], "production_target_primary", root=root
            )
            second = production_authorization.build_certified_rule_production_authorization_plan(
                built["rule_id"], built["controlled_run"]["controlled_integration_result_id"], "production_target_primary", root=root
            )
        self.assertEqual(first["production_authorization_plan_id"], second["production_authorization_plan_id"])
        self.assertEqual(first["plan_fingerprint"], second["plan_fingerprint"])
        self.assertEqual(first["committed_state_fingerprint"], second["committed_state_fingerprint"])
        self.assertEqual(first["production_target_descriptor_fingerprint"], second["production_target_descriptor_fingerprint"])

    def test_decision_requires_exact_confirmation_and_does_not_call_production_writes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _completed_integration(root)
            plan = production_authorization.build_certified_rule_production_authorization_plan(
                built["rule_id"], built["controlled_run"]["controlled_integration_result_id"], "production_target_primary", root=root
            )
            blocked = production_authorization.save_certified_rule_production_authorization_decision(
                plan["production_authorization_plan_id"], production_authorization.AUTHORIZED_DECISION, confirmation=None, root=root
            )
            with patch.object(production_authorization.target_backend, "apply_controlled_integration_transaction", side_effect=AssertionError("should not write")):
                with patch.object(production_authorization.target_backend, "commit_controlled_integration_transaction", side_effect=AssertionError("should not write")):
                    with patch.object(production_authorization.target_backend, "rollback_controlled_integration_transaction", side_effect=AssertionError("should not write")):
                        saved = production_authorization.save_certified_rule_production_authorization_decision(
                            plan["production_authorization_plan_id"],
                            production_authorization.AUTHORIZED_DECISION,
                            confirmation=production_authorization.REQUIRED_CONFIRMATION,
                            root=root,
                        )
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(saved["status"], "authorized")

    def test_identical_authorized_rerun_is_idempotent_and_drift_is_stale(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
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
            rerun = production_authorization.save_certified_rule_production_authorization_decision(
                plan["production_authorization_plan_id"],
                production_authorization.AUTHORIZED_DECISION,
                confirmation=production_authorization.REQUIRED_CONFIRMATION,
                root=root,
            )
            descriptor_path = root / descriptor_backend.DESCRIPTOR_DIR / "production_target_primary.json"
            payload = json.loads(descriptor_path.read_text(encoding="utf-8"))
            payload["adapter_version"] = "2"
            normalized = descriptor_backend._normalize_descriptor(payload)
            assert normalized is not None
            _write_json(descriptor_path, normalized)
            drift = production_authorization.save_certified_rule_production_authorization_decision(
                plan["production_authorization_plan_id"],
                production_authorization.AUTHORIZED_DECISION,
                confirmation=production_authorization.REQUIRED_CONFIRMATION,
                root=root,
            )
        self.assertEqual(saved["status"], "authorized")
        self.assertEqual(rerun["status"], "already_authorized")
        self.assertEqual(rerun["writes_performed"], 0)
        self.assertEqual(drift["status"], "stale")

    def test_api_health_report_and_no_upstream_mutation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _completed_integration(root)
            rule_path = root / "canonical_rules" / f"{built['rule_id']}.json"
            release_path = root / controlled_integration.release_candidate_backend.RESULT_DIR / f"{controlled_integration.release_candidate_backend.analysis_backend._safe_id(built['release_run']['release_candidate_result_id'])}.json"
            before = {path: path.read_text(encoding="utf-8") for path in (rule_path, release_path)}
            workspace = api_workspace(built["rule_id"], built["controlled_run"]["controlled_integration_result_id"], "production_target_primary", root=root)
            eligibility = api_validate(built["rule_id"], built["controlled_run"]["controlled_integration_result_id"], "production_target_primary", root=root)
            plan = api_build_plan(built["rule_id"], built["controlled_run"]["controlled_integration_result_id"], "production_target_primary", root=root)
            saved = api_save_decision(
                plan["production_authorization_plan_id"],
                production_authorization.AUTHORIZED_DECISION,
                confirmation=production_authorization.REQUIRED_CONFIRMATION,
                root=root,
            )
            health = production_authorization.get_certified_rule_production_authorization_health(plan["production_authorization_plan_id"], root=root)
            report = api_report(saved["production_authorization_result_id"], saved["production_authorization_receipt_id"], True, root=root)
            after = {path: path.read_text(encoding="utf-8") for path in (rule_path, release_path)}
        self.assertEqual(workspace["status"], "ready_for_planning")
        self.assertIn(eligibility["status"], {"eligible", "eligible_with_warnings"})
        self.assertEqual(saved["status"], "authorized")
        self.assertEqual(health["status"], "healthy")
        self.assertEqual(before, after)
        self.assertIn("No production deployment, activation, commit, rollback, scoring, or live Fast Lane execution occurred.", report)
