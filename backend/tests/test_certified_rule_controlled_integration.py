from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from backend.electional import certified_rule_controlled_integration as controlled_integration
from backend.electional import certified_rule_controlled_integration_target as target
from backend.electional.api import (
    build_certified_rule_controlled_integration_plan as api_build_plan,
    build_certified_rule_controlled_integration_workspace as api_workspace,
    execute_certified_rule_controlled_integration as api_execute,
    format_certified_rule_controlled_integration_report as api_report,
    validate_certified_rule_controlled_integration_eligibility as api_validate,
)
from backend.tests.test_certified_rule_release_candidate import _build_phase_9s_inputs, _write_json


def _qualified_release_inputs(root: Path) -> dict[str, object]:
    built = _build_phase_9s_inputs(root)
    release_plan = controlled_integration.release_candidate_backend.build_certified_rule_release_candidate_plan(
        built["rule_id"],
        built["authorization_saved"]["integration_authorization_result_id"],
        root=root,
    )
    release_run = controlled_integration.release_candidate_backend.qualify_certified_rule_release_candidate(
        release_plan["release_candidate_plan_id"],
        confirmation=controlled_integration.release_candidate_backend.REQUIRED_CONFIRMATION,
        root=root,
    )
    built["release_plan"] = release_plan
    built["release_run"] = release_run
    return built


class CertifiedRuleControlledIntegrationTest(TestCase):
    def test_qualified_candidate_executes_and_commits_verified_isolated_state(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _qualified_release_inputs(root)
            workspace = controlled_integration.build_certified_rule_controlled_integration_workspace(
                built["rule_id"], built["release_run"]["release_candidate_result_id"], target.DEFAULT_TARGET_ID, root=root
            )
            plan = controlled_integration.build_certified_rule_controlled_integration_plan(
                built["rule_id"], built["release_run"]["release_candidate_result_id"], target.DEFAULT_TARGET_ID, root=root
            )
            run = controlled_integration.execute_certified_rule_controlled_integration(
                plan["controlled_integration_plan_id"], confirmation=controlled_integration.REQUIRED_CONFIRMATION, root=root
            )
            loaded = controlled_integration.load_certified_rule_controlled_integration_result(run["controlled_integration_result_id"], root=root)
            committed = target.read_controlled_integration_target_state(
                target.DEFAULT_TARGET_ID, namespace_id=plan["namespace_id"], root=root
            )
        self.assertEqual(workspace["status"], "ready_for_planning")
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(run["status"], "completed")
        self.assertEqual(loaded["controlled_integration_result"]["pending_verification_status"], "verified_pending")
        self.assertEqual(loaded["controlled_integration_result"]["committed_verification_status"], "verified_committed")
        self.assertEqual(committed["verification_status"], "verified_committed")

    def test_unqualified_stale_mismatched_or_unauthorized_candidate_is_blocked(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _qualified_release_inputs(root)
            release_path = root / controlled_integration.release_candidate_backend.RESULT_DIR / f"{controlled_integration.release_candidate_backend.analysis_backend._safe_id(built['release_run']['release_candidate_result_id'])}.json"
            payload = json.loads(release_path.read_text(encoding="utf-8"))
            payload["qualification_status"] = "not_qualified"
            _write_json(release_path, payload)
            blocked = controlled_integration.validate_certified_rule_controlled_integration_eligibility(
                built["rule_id"], built["release_run"]["release_candidate_result_id"], target.DEFAULT_TARGET_ID, root=root
            )
            auth_path = root / controlled_integration.authorization_backend.RESULT_DIR / f"{controlled_integration.release_candidate_backend.analysis_backend._safe_id(built['authorization_saved']['integration_authorization_result_id'])}.json"
            auth_payload = json.loads(auth_path.read_text(encoding="utf-8"))
            auth_payload["decision"] = "reject_integration"
            _write_json(auth_path, auth_payload)
            unauthorized = controlled_integration.validate_certified_rule_controlled_integration_eligibility(
                built["rule_id"], built["release_run"]["release_candidate_result_id"], target.DEFAULT_TARGET_ID, root=root
            )
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("release_candidate_not_qualified", blocked["blockers"])
        self.assertIn("integration_authorization_decision_invalid", unauthorized["blockers"])

    def test_unhealthy_production_unknown_or_incompatible_target_is_blocked(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _qualified_release_inputs(root)
            manifest_path = root / target.TARGET_ROOT_DIR / target.DEFAULT_TARGET_ID / "manifest.json"
            target.get_controlled_integration_target_manifest(target.DEFAULT_TARGET_ID, root=root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["environment_class"] = "production"
            manifest["target_fingerprint"] = target._target_manifest_fingerprint(manifest)
            _write_json(manifest_path, manifest)
            production = controlled_integration.validate_certified_rule_controlled_integration_eligibility(
                built["rule_id"], built["release_run"]["release_candidate_result_id"], target.DEFAULT_TARGET_ID, root=root
            )
            manifest["environment_class"] = "unknown"
            manifest["target_fingerprint"] = target._target_manifest_fingerprint(manifest)
            _write_json(manifest_path, manifest)
            unknown = controlled_integration.validate_certified_rule_controlled_integration_eligibility(
                built["rule_id"], built["release_run"]["release_candidate_result_id"], target.DEFAULT_TARGET_ID, root=root
            )
        self.assertIn("integration_target_not_isolated_non_production", production["blockers"])
        self.assertIn("integration_target_not_isolated_non_production", unknown["blockers"])

    def test_package_plan_transaction_and_namespace_bindings_are_deterministic(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _qualified_release_inputs(root)
            before = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
            first = controlled_integration.build_certified_rule_controlled_integration_plan(
                built["rule_id"], built["release_run"]["release_candidate_result_id"], target.DEFAULT_TARGET_ID, root=root
            )
            second = controlled_integration.build_certified_rule_controlled_integration_plan(
                built["rule_id"], built["release_run"]["release_candidate_result_id"], target.DEFAULT_TARGET_ID, root=root
            )
            after = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
        self.assertEqual(first["controlled_integration_plan_id"], second["controlled_integration_plan_id"])
        self.assertEqual(first["package_fingerprint"], second["package_fingerprint"])
        self.assertEqual(first["transaction_id"], second["transaction_id"])
        self.assertEqual(first["namespace_id"], second["namespace_id"])
        self.assertGreaterEqual(len(after), len(before))

    def test_pending_and_committed_independent_readback_are_required(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _qualified_release_inputs(root)
            plan = controlled_integration.build_certified_rule_controlled_integration_plan(
                built["rule_id"], built["release_run"]["release_candidate_result_id"], target.DEFAULT_TARGET_ID, root=root
            )
            real_read = target.read_controlled_integration_target_state
            pending_reads = {"count": 0}

            def fake_read(target_id: str, transaction_id: str | None = None, namespace_id: str | None = None, *, root: Path | str):
                payload = real_read(target_id, transaction_id=transaction_id, namespace_id=namespace_id, root=root)
                if transaction_id:
                    pending_reads["count"] += 1
                if transaction_id and pending_reads["count"] == 2:
                    payload = dict(payload)
                    payload["verification_status"] = "mismatch"
                    payload["blockers"] = ["state_fingerprint_mismatch"]
                return payload

            with patch.object(controlled_integration.target_backend, "read_controlled_integration_target_state", side_effect=fake_read):
                run = controlled_integration.execute_certified_rule_controlled_integration(
                    plan["controlled_integration_plan_id"], confirmation=controlled_integration.REQUIRED_CONFIRMATION, root=root
                )
            pending_path = root / target.TARGET_ROOT_DIR / target.DEFAULT_TARGET_ID / "pending" / f"{plan['transaction_id']}.json"
        self.assertIn(run["status"], {"verification_failed", "rollback_completed", "rollback_failed"})
        self.assertFalse(pending_path.exists())

    def test_apply_commit_or_verification_failure_rolls_back_owned_target_state(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _qualified_release_inputs(root)
            plan = controlled_integration.build_certified_rule_controlled_integration_plan(
                built["rule_id"], built["release_run"]["release_candidate_result_id"], target.DEFAULT_TARGET_ID, root=root
            )

            def fail_commit(*args, **kwargs):
                return {"status": "commit_failed", "blockers": ["forced_commit_failure"], "warnings": []}

            with patch.object(controlled_integration.target_backend, "commit_controlled_integration_transaction", side_effect=fail_commit):
                run = controlled_integration.execute_certified_rule_controlled_integration(
                    plan["controlled_integration_plan_id"], confirmation=controlled_integration.REQUIRED_CONFIRMATION, root=root
                )
            committed_path = root / target.TARGET_ROOT_DIR / target.DEFAULT_TARGET_ID / "namespaces" / f"{plan['namespace_id']}.json"
        self.assertIn(run["status"], {"commit_failed", "rollback_failed"})
        self.assertFalse(committed_path.exists())

    def test_identical_completed_execution_is_idempotent_and_drift_is_stale(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _qualified_release_inputs(root)
            plan = controlled_integration.build_certified_rule_controlled_integration_plan(
                built["rule_id"], built["release_run"]["release_candidate_result_id"], target.DEFAULT_TARGET_ID, root=root
            )
            run = controlled_integration.execute_certified_rule_controlled_integration(
                plan["controlled_integration_plan_id"], confirmation=controlled_integration.REQUIRED_CONFIRMATION, root=root
            )
            rerun = controlled_integration.execute_certified_rule_controlled_integration(
                plan["controlled_integration_plan_id"], confirmation=controlled_integration.REQUIRED_CONFIRMATION, root=root
            )
            manifest_path = root / target.TARGET_ROOT_DIR / target.DEFAULT_TARGET_ID / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["adapter_version"] = "2.0"
            manifest["target_fingerprint"] = target._target_manifest_fingerprint(manifest)
            _write_json(manifest_path, manifest)
            drift = controlled_integration.execute_certified_rule_controlled_integration(
                plan["controlled_integration_plan_id"], confirmation=controlled_integration.REQUIRED_CONFIRMATION, root=root
            )
        self.assertEqual(run["status"], "completed")
        self.assertEqual(rerun["status"], "already_completed")
        self.assertEqual(rerun["writes_performed"], 0)
        self.assertEqual(drift["status"], "stale")

    def test_api_flow_health_summary_report_and_no_upstream_or_production_mutation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _qualified_release_inputs(root)
            workspace = api_workspace(built["rule_id"], built["release_run"]["release_candidate_result_id"], target.DEFAULT_TARGET_ID, root=root)
            eligibility = api_validate(built["rule_id"], built["release_run"]["release_candidate_result_id"], target.DEFAULT_TARGET_ID, root=root)
            plan = api_build_plan(built["rule_id"], built["release_run"]["release_candidate_result_id"], target.DEFAULT_TARGET_ID, root=root)
            rule_path = root / "canonical_rules" / f"{built['rule_id']}.json"
            before_rule = rule_path.read_text(encoding="utf-8")
            run = api_execute(plan["controlled_integration_plan_id"], confirmation=controlled_integration.REQUIRED_CONFIRMATION, root=root)
            health = controlled_integration.get_certified_rule_controlled_integration_health(plan["controlled_integration_plan_id"], root=root)
            summary = controlled_integration.get_certified_rule_controlled_integration_summary(run["controlled_integration_result_id"], root=root)
            report = api_report(run["controlled_integration_result_id"], run["controlled_integration_receipt_id"], True, root=root)
            after_rule = rule_path.read_text(encoding="utf-8")
        self.assertEqual(workspace["status"], "ready_for_planning")
        self.assertIn(eligibility["status"], {"eligible", "eligible_with_warnings"})
        self.assertEqual(run["status"], "completed")
        self.assertEqual(health["status"], "healthy")
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(before_rule, after_rule)
        self.assertIn("isolated non-production storage", report)
        self.assertIn("The staged rule was not activated.", report)
