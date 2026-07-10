from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from backend.electional import deployed_rule_execution_runtime as runtime
from backend.electional import deployed_rule_operational_telemetry as telemetry
from backend.tests.test_certified_rule_post_deployment_acceptance import _deployed_inputs
from backend.tests.test_certified_rule_controlled_integration import _write_json


def _tracked_state(root: Path) -> dict[str, str]:
    tracked_dirs = [
        "canonical_rules",
        "production_activation_transactions",
        "certified_rule_production_deployment_plans",
        "certified_rule_production_deployment_results",
        "certified_rule_production_deployment_receipts",
        "certified_rule_post_deployment_acceptance_plans",
        "certified_rule_post_deployment_acceptance_results",
        "certified_rule_post_deployment_acceptance_receipts",
        "deployed_rule_operational_telemetry",
    ]
    snapshot: dict[str, str] = {}
    for folder in tracked_dirs:
        path = root / folder
        if not path.exists():
            continue
        for file in sorted(path.rglob("*.json")):
            snapshot[str(file.relative_to(root))] = file.read_text(encoding="utf-8")
    return snapshot


class DeployedRuleExecutionRuntimeTest(TestCase):
    def test_execution_workspace_binds_phase9v_deployed_instance_and_canonical_rule(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            workspace = runtime.build_deployed_rule_execution_workspace(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                execution_input={"score": 7},
                root=root,
            )
        self.assertEqual(workspace["status"], "ready")
        self.assertEqual(workspace["canonical_rule_id"], built["rule_id"])
        self.assertEqual(workspace["deployed_rule_id"], built["production_deployment_run"]["deployed_rule_id"])
        self.assertEqual(workspace["production_transaction_id"], built["production_deployment_run"]["production_transaction_id"])

    def test_execution_eligibility_blocks_mismatched_deployed_rule_or_transaction(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            bad_rule = runtime.validate_deployed_rule_execution_eligibility(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                "wrong_rule",
                execution_input={"score": 7},
                root=root,
            )
            deployed_path = root / "canonical_rules" / f"{built['production_deployment_run']['deployed_rule_id']}.json"
            deployed_payload = runtime.load_canonical_rule(built["production_deployment_run"]["deployed_rule_id"], root=root)["rule"]
            deployed_payload["production_activation_transaction_id"] = "wrong_tx"
            _write_json(deployed_path, deployed_payload)
            bad_tx = runtime.validate_deployed_rule_execution_eligibility(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                execution_input={"score": 7},
                root=root,
            )
        self.assertIn("deployed_rule_id_mismatch", bad_rule["blockers"])
        self.assertIn("production_transaction_id_mismatch", bad_tx["blockers"])

    def test_execute_deployed_rule_calls_existing_canonical_evaluator_through_deployed_binding(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            with patch.object(runtime, "evaluate_canonical_rule", return_value={"result": "matched", "persistent_writes": 0, "warnings": [], "blockers": []}) as evaluator:
                runtime.execute_deployed_rule(
                    built["rule_id"],
                    built["production_deployment_run"]["production_deployment_result_id"],
                    "production_target_primary",
                    built["production_deployment_run"]["deployed_rule_id"],
                    execution_input={"score": 7},
                    root=root,
                )
        self.assertEqual(evaluator.call_count, 1)
        args, kwargs = evaluator.call_args
        self.assertEqual(args[0]["rule_id"], built["production_deployment_run"]["deployed_rule_id"])
        self.assertEqual(kwargs["root"], root)

    def test_execute_deployed_rule_preserves_return_value_and_identity_envelope(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            result = runtime.execute_deployed_rule(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                execution_input={"score": 7},
                root=root,
            )
        self.assertEqual(result["execution_status"], "completed")
        self.assertIn(result["runtime_outcome_status"], {"matched", "not_matched"})
        self.assertEqual(result["evaluation"]["persistent_writes"], 0)
        self.assertEqual(result["canonical_rule_id"], built["rule_id"])
        self.assertEqual(result["deployed_rule_id"], built["production_deployment_run"]["deployed_rule_id"])
        self.assertEqual(result["production_deployment_result_id"], built["production_deployment_run"]["production_deployment_result_id"])
        self.assertEqual(result["telemetry_recording_status"], "not_recorded")

    def test_execute_deployed_rule_preserves_exception_behavior(self) -> None:
        class Boom(RuntimeError):
            pass

        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            with patch.object(runtime, "evaluate_canonical_rule", side_effect=Boom("explode")):
                with self.assertRaisesRegex(Boom, "explode"):
                    runtime.execute_deployed_rule(
                        built["rule_id"],
                        built["production_deployment_run"]["production_deployment_result_id"],
                        "production_target_primary",
                        built["production_deployment_run"]["deployed_rule_id"],
                        execution_input={"score": 7},
                        record_operational_telemetry=True,
                        _testing_observed_at="2026-07-10T10:00:00Z",
                        root=root,
                    )
            listed = telemetry.list_deployed_rule_operational_events(
                built["production_deployment_run"]["deployed_rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                producer_id=telemetry.EXECUTION_PRODUCER_ID,
                root=root,
            )
        self.assertEqual(listed["total_matching_event_count"], 1)
        self.assertEqual(listed["items"][0]["event_type"], "evaluation_failed")

    def test_execution_envelope_exposes_telemetry_compatible_identity_fields(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            result = runtime.execute_deployed_rule(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                execution_input={"score": 7},
                root=root,
            )
        for field in (
            "canonical_rule_id",
            "canonical_rule_fingerprint",
            "deployed_rule_id",
            "deployed_rule_fingerprint",
            "production_deployment_result_id",
            "production_target_id",
            "production_transaction_id",
            "document_id",
            "source_revision",
            "certification_id",
            "certification_fingerprint",
            "production_authorization_result_id",
            "deployment_package_fingerprint",
            "committed_production_state_fingerprint",
            "input_fingerprint",
            "output_fingerprint",
        ):
            self.assertTrue(result.get(field))

    def test_execution_does_not_mutate_deployment_canonical_phase9v_phase9w_or_telemetry_state(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            before = _tracked_state(root)
            runtime.execute_deployed_rule(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                execution_input={"score": 7},
                root=root,
            )
            after = _tracked_state(root)
        self.assertEqual(before, after)

    def test_execution_with_telemetry_records_one_completed_event_and_preserves_runtime_output(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            result = runtime.execute_deployed_rule(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                execution_input={"score": 7},
                record_operational_telemetry=True,
                _testing_observed_at="2026-07-10T11:00:00Z",
                root=root,
            )
            listed = telemetry.list_deployed_rule_operational_events(
                built["production_deployment_run"]["deployed_rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                producer_id=telemetry.EXECUTION_PRODUCER_ID,
                root=root,
            )
        self.assertEqual(result["execution_status"], "completed")
        self.assertEqual(result["telemetry_recording_status"], "recorded")
        self.assertEqual(listed["total_matching_event_count"], 1)
        self.assertEqual(listed["items"][0]["event_type"], "evaluation_completed")
        self.assertEqual(listed["items"][0]["canonical_rule_id"], built["rule_id"])
        self.assertEqual(listed["items"][0]["production_transaction_id"], built["production_deployment_run"]["production_transaction_id"])

    def test_no_effectiveness_scoring_success_rate_or_phase9w_evidence_is_used(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            report = runtime.format_deployed_rule_execution_report(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                execution_input={"score": 7},
                root=root,
            )
        self.assertIn("Effectiveness evaluation: not performed", report)
        self.assertIn("execution_telemetry_producer_available", report)
        self.assertNotIn("success rate", report.lower())
