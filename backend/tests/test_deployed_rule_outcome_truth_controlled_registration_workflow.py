from __future__ import annotations

import inspect
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import deployed_rule_outcome_truth_source as truth


def _write_telemetry_snapshot_fixture(root: Path) -> dict[str, str]:
    snapshot_id = "snapshot-1"
    snapshot_path = truth.telemetry_backend._snapshot_path(root, snapshot_id)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    event_path = truth.telemetry_backend._event_path(root, "event-1")
    event_path.parent.mkdir(parents=True, exist_ok=True)
    event_path.write_text(json.dumps({"event_id": "event-1", "input_fingerprint": ""}, indent=2, sort_keys=True), encoding="utf-8")
    snapshot_payload = {
        "schema_version": truth.telemetry_backend.SNAPSHOT_SCHEMA,
        "telemetry_schema_version": truth.telemetry_backend.TELEMETRY_SCHEMA_VERSION,
        "telemetry_snapshot_id": snapshot_id,
        "canonical_rule_id": "rule-1",
        "production_deployment_result_id": "deploy-1",
        "production_target_id": "target-1",
        "deployed_rule_id": "deployed-1",
        "observation_start": "2026-07-10T10:00:00Z",
        "observation_end": "2026-07-10T12:00:00Z",
        "event_count": 1,
        "validated_event_ids": ["event-1"],
        "events": [],
    }
    snapshot_path.write_text(json.dumps(snapshot_payload, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "canonical_rule_id": "rule-1",
        "production_deployment_result_id": "deploy-1",
        "production_target_id": "target-1",
        "deployed_rule_id": "deployed-1",
        "telemetry_snapshot_id": snapshot_id,
        "observation_window_start": "2026-07-10T10:00:00Z",
        "observation_window_end": "2026-07-10T12:00:00Z",
    }


class DeployedRuleOutcomeTruthControlledRegistrationWorkflowPlanningGateTest(TestCase):
    def test_controlled_outcome_truth_record_set_registration_workflow_planning_gate_is_read_only_and_no_overclaim(self) -> None:
        self.assertTrue(callable(truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_planning_gate))
        self.assertTrue(callable(truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_planning_gate_report))

        planning_source = inspect.getsource(
            truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_planning_gate
        )
        report_source = inspect.getsource(
            truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_planning_gate_report
        )
        register_source = inspect.getsource(truth.register_deployed_rule_outcome_truth_record_set)
        for forbidden_call in (
            "register_deployed_rule_outcome_truth_record_set(",
            "build_deployed_rule_outcome_truth_source_plan(",
            "record_deployed_rule_outcome_truth_source_result(",
            "_ensure_dirs(",
            "json.dump(",
            "write_text(",
            "_atomic_write_json(",
        ):
            self.assertNotIn(forbidden_call, planning_source)
            self.assertNotIn(forbidden_call, report_source)
        self.assertIn("_ensure_dirs(", register_source)
        self.assertIn("build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate(", planning_source)
        self.assertIn("build_deployed_rule_outcome_truth_record_set_qa_gate", planning_source)
        self.assertIn("format_deployed_rule_outcome_truth_record_set_qa_gate_report", planning_source)
        self.assertIn("register_deployed_rule_outcome_truth_record_set", planning_source)

        for forbidden_surface in (
            "effectiveness_score",
            "correctness_score",
            "success_rate",
            "failure_rate",
            "production_score",
            "profitability_score",
            "prediction_quality_score",
            "deployment_safety_score",
            "overall_score",
            "final_score",
            "quality_score",
            "factual_truth_override",
            "correct_outcome_override",
            "expected_outcome_override",
            "actual_outcome_override",
            "repair_record_set",
            "migrate_record_set",
            "register_from_qa",
            "force_register",
            "auto_register",
            "execute_registration",
            "commit_registration",
        ):
            self.assertNotIn(forbidden_surface, planning_source)
            self.assertNotIn(forbidden_surface, report_source)

        with TemporaryDirectory() as tmp:
            missing_root = Path(tmp) / "missing"
            before_missing = sorted(str(path.relative_to(missing_root)) for path in missing_root.rglob("*")) if missing_root.exists() else []
            missing_gate = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_planning_gate(
                None,
                root=missing_root,
            )
            missing_report = truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_planning_gate_report(
                None,
                root=missing_root,
            )
            after_missing = sorted(str(path.relative_to(missing_root)) for path in missing_root.rglob("*")) if missing_root.exists() else []

            malformed_root = Path(tmp) / "malformed"
            before_malformed = sorted(str(path.relative_to(malformed_root)) for path in malformed_root.rglob("*")) if malformed_root.exists() else []
            malformed_gate = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_planning_gate(
                {"records": "bad"},
                root=malformed_root,
            )
            after_malformed = sorted(str(path.relative_to(malformed_root)) for path in malformed_root.rglob("*")) if malformed_root.exists() else []

            valid_root = Path(tmp) / "valid"
            identity = _write_telemetry_snapshot_fixture(valid_root)
            candidate = {
                **identity,
                "outcome_truth_record_set_id": "candidate-set-1",
                "source_id": "source-1",
                "source_type": "external_authoritative_result",
                "source_authority_class": "authoritative",
                "records": [
                    {
                        "execution_event_id": "event-1",
                        "expected_outcome": "venus_day",
                        "actual_or_adjudicated_outcome": "venus_day",
                        "outcome_observed_at": "2026-07-10T11:00:00Z",
                        "truth_status": "valid",
                        "source_id": "source-1",
                        "source_type": "external_authoritative_result",
                        "source_authority_class": "authoritative",
                    }
                ],
            }
            before_valid = sorted(str(path.relative_to(valid_root)) for path in valid_root.rglob("*"))
            planning_gate = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_planning_gate(
                candidate,
                root=valid_root,
            )
            planning_report = truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_planning_gate_report(
                candidate,
                root=valid_root,
            )
            after_valid = sorted(str(path.relative_to(valid_root)) for path in valid_root.rglob("*"))

        self.assertEqual(before_missing, after_missing)
        self.assertEqual(missing_gate["status"], "missing")
        self.assertEqual(missing_gate["writes_performed"], 0)
        self.assertIn("candidate_record_set_missing", missing_gate["blockers"])
        self.assertIn("writes performed: 0", missing_report.lower())

        self.assertEqual(before_malformed, after_malformed)
        self.assertEqual(malformed_gate["status"], "malformed")
        self.assertEqual(malformed_gate["writes_performed"], 0)
        self.assertIn("candidate_record_set_records_missing", malformed_gate["blockers"])

        self.assertEqual(before_valid, after_valid)
        self.assertEqual(planning_gate["status"], "planning_ready")
        self.assertEqual(planning_gate["candidate_qa_status"], "passed")
        self.assertTrue(planning_gate["candidate_structurally_ready_for_registration"])
        self.assertTrue(planning_gate["planning_ready_for_future_controlled_registration_workflow"])
        self.assertFalse(planning_gate["controlled_registration_implemented"])
        self.assertFalse(planning_gate["registration_performed"])
        self.assertFalse(planning_gate["record_set_written"])
        self.assertFalse(planning_gate["records_repaired"])
        self.assertFalse(planning_gate["records_migrated"])
        self.assertFalse(planning_gate["automatic_registration_approval_claimed"])
        self.assertEqual(planning_gate["writes_performed"], 0)
        self.assertEqual(planning_gate["required_future_confirmation"], truth.REGISTER_CONFIRMATION)
        self.assertTrue(planning_gate["future_confirmation_is_advisory_only"])
        self.assertGreaterEqual(len(planning_gate["planned_future_workflow_steps"]), 10)
        self.assertGreaterEqual(len(planning_gate["required_future_safeguards"]), 10)
        self.assertIn("blockers", planning_gate)
        self.assertIn("warnings", planning_gate)
        self.assertIn("recommended_action", planning_gate)
        self.assertTrue(isinstance(planning_gate["limitations"], list))
        self.assertTrue(isinstance(planning_gate["boundary_flags"], dict))
        self.assertFalse(planning_gate["boundary_flags"]["controlled_registration_implemented"])
        self.assertFalse(planning_gate["boundary_flags"]["registration_performed"])
        self.assertFalse(planning_gate["boundary_flags"]["record_set_written"])
        self.assertFalse(planning_gate["boundary_flags"]["records_repaired"])
        self.assertFalse(planning_gate["boundary_flags"]["records_migrated"])
        self.assertFalse(planning_gate["boundary_flags"]["automatic_registration_approval_claimed"])
        self.assertTrue(all(bool(value) for value in planning_gate["prerequisite_surface_status"].values()))

        report_lower = planning_report.lower()
        self.assertNotIn(str(valid_root).lower(), report_lower)
        self.assertNotIn("c:\\users\\", report_lower)
        self.assertNotIn("/users/", report_lower)
        self.assertNotIn("/home/", report_lower)
        self.assertNotIn("{", planning_report)
        self.assertNotIn('"expected_outcome"', report_lower)
        self.assertNotIn("traceback", report_lower)
        self.assertIn("planned future workflow steps:", report_lower)
        self.assertIn("required future safeguards:", report_lower)
        self.assertIn("future confirmation is advisory only: true", report_lower)
        self.assertIn("it does not register records.", report_lower)
        self.assertIn("it does not create record sets.", report_lower)
        self.assertIn("it does not repair records.", report_lower)
        self.assertIn("it does not migrate records.", report_lower)
        self.assertIn("it does not approve automatic registration.", report_lower)
        self.assertIn("it does not prove factual correctness of outcome-truth records.", report_lower)
        self.assertIn("it does not establish broad rule effectiveness.", report_lower)
        self.assertIn("it does not establish deployment safety.", report_lower)
        self.assertIn("it does not establish production correctness.", report_lower)
        self.assertIn("it does not establish profitability.", report_lower)
        self.assertIn("it does not establish prediction quality.", report_lower)
        self.assertIn("it does not establish future performance.", report_lower)
        self.assertIn("it does not establish aggregate effectiveness.", report_lower)
        self.assertIn("it does not establish ranking quality.", report_lower)

        for forbidden_score in (
            "effectiveness_score",
            "correctness_score",
            "success_rate",
            "failure_rate",
            "production_score",
            "final_score",
            "quality_score",
            "aggregate score",
            "rank results",
            "compare results",
        ):
            self.assertNotIn(forbidden_score, planning_report)
            self.assertNotIn(forbidden_score, json.dumps(planning_gate, sort_keys=True))

        doc_text = Path(
            "docs/PHASE_13A_CONTROLLED_OUTCOME_TRUTH_RECORD_SET_REGISTRATION_WORKFLOW_PLANNING_GATE.md"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "The planning gate checks readiness to design a future controlled outcome-truth record-set registration workflow.",
            doc_text,
        )
        self.assertIn("It does not register records.", doc_text)
        self.assertIn("It does not create record sets.", doc_text)
        self.assertIn("It does not repair records.", doc_text)
        self.assertIn("It does not migrate records.", doc_text)
        self.assertIn("It performs no writes and creates no storage.", doc_text)
        self.assertIn("Phase 13B - Controlled Outcome-Truth Record-Set Registration Workflow Backend Plan", doc_text)
