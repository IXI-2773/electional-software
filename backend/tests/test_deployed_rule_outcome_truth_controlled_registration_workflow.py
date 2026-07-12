from __future__ import annotations

import inspect
import json
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import api
from backend.electional import desktop_right_panel as desktop_panel
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

    def test_controlled_outcome_truth_record_set_registration_workflow_backend_plan_is_read_only_non_executing_and_no_overclaim(self) -> None:
        self.assertTrue(callable(truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan))
        self.assertTrue(callable(truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report))

        plan_source = inspect.getsource(
            truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan
        )
        report_source = inspect.getsource(
            truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report
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
            self.assertNotIn(forbidden_call, plan_source)
            self.assertNotIn(forbidden_call, report_source)
        self.assertIn("_ensure_dirs(", register_source)
        self.assertIn("build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_planning_gate(", plan_source)
        self.assertIn("build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate", plan_source)
        self.assertIn("build_deployed_rule_outcome_truth_record_set_qa_gate", plan_source)
        self.assertIn("register_deployed_rule_outcome_truth_record_set", plan_source)

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
            self.assertNotIn(forbidden_surface, plan_source)
            self.assertNotIn(forbidden_surface, report_source)

        with TemporaryDirectory() as tmp:
            missing_root = Path(tmp) / "missing-plan"
            before_missing = sorted(str(path.relative_to(missing_root)) for path in missing_root.rglob("*")) if missing_root.exists() else []
            missing_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan(
                None,
                root=missing_root,
            )
            missing_report = truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report(
                None,
                root=missing_root,
            )
            after_missing = sorted(str(path.relative_to(missing_root)) for path in missing_root.rglob("*")) if missing_root.exists() else []

            malformed_root = Path(tmp) / "malformed-plan"
            before_malformed = sorted(str(path.relative_to(malformed_root)) for path in malformed_root.rglob("*")) if malformed_root.exists() else []
            malformed_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan(
                {"records": "bad"},
                root=malformed_root,
            )
            after_malformed = sorted(str(path.relative_to(malformed_root)) for path in malformed_root.rglob("*")) if malformed_root.exists() else []

            valid_root = Path(tmp) / "valid-plan"
            identity = _write_telemetry_snapshot_fixture(valid_root)
            candidate = {
                **identity,
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
            backend_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan(
                candidate,
                root=valid_root,
            )
            backend_report = truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report(
                candidate,
                root=valid_root,
            )
            after_valid = sorted(str(path.relative_to(valid_root)) for path in valid_root.rglob("*"))

        self.assertEqual(before_missing, after_missing)
        self.assertEqual(missing_plan["status"], "missing")
        self.assertEqual(missing_plan["writes_performed"], 0)
        self.assertIn("candidate_record_set_missing", missing_plan["blockers"])
        self.assertIn("writes performed: 0", missing_report.lower())

        self.assertEqual(before_malformed, after_malformed)
        self.assertEqual(malformed_plan["status"], "malformed")
        self.assertEqual(malformed_plan["writes_performed"], 0)
        self.assertIn("candidate_record_set_records_missing", malformed_plan["blockers"])

        self.assertEqual(before_valid, after_valid)
        self.assertEqual(backend_plan["status"], "plan_ready")
        self.assertEqual(backend_plan["planning_gate_status"], "planning_ready")
        self.assertEqual(backend_plan["candidate_qa_status"], "passed")
        self.assertTrue(backend_plan["candidate_structurally_ready_for_registration"])
        self.assertTrue(backend_plan["backend_plan_ready_for_future_execution"])
        self.assertFalse(backend_plan["backend_plan_persisted"])
        self.assertFalse(backend_plan["controlled_registration_implemented"])
        self.assertFalse(backend_plan["registration_performed"])
        self.assertFalse(backend_plan["record_set_written"])
        self.assertFalse(backend_plan["records_repaired"])
        self.assertFalse(backend_plan["records_migrated"])
        self.assertFalse(backend_plan["automatic_registration_approval_claimed"])
        self.assertFalse(backend_plan["confirmation_accepted_in_this_phase"])
        self.assertFalse(backend_plan["confirmation_enforced_in_this_phase"])
        self.assertEqual(backend_plan["required_future_confirmation"], truth.REGISTER_CONFIRMATION)
        self.assertEqual(backend_plan["writes_performed"], 0)
        self.assertGreaterEqual(len(backend_plan["required_future_preconditions"]), 9)
        self.assertGreaterEqual(len(backend_plan["planned_future_execution_steps"]), 10)
        self.assertGreaterEqual(len(backend_plan["planned_future_post_registration_checks"]), 7)
        self.assertGreaterEqual(len(backend_plan["required_future_safeguards"]), 12)
        self.assertIn("blockers", backend_plan)
        self.assertIn("warnings", backend_plan)
        self.assertIn("recommended_action", backend_plan)
        self.assertTrue(isinstance(backend_plan["limitations"], list))
        self.assertTrue(isinstance(backend_plan["boundary_flags"], dict))
        self.assertFalse(backend_plan["boundary_flags"]["backend_plan_persisted"])
        self.assertFalse(backend_plan["boundary_flags"]["controlled_registration_implemented"])
        self.assertFalse(backend_plan["boundary_flags"]["registration_performed"])
        self.assertFalse(backend_plan["boundary_flags"]["record_set_written"])
        self.assertFalse(backend_plan["boundary_flags"]["records_repaired"])
        self.assertFalse(backend_plan["boundary_flags"]["records_migrated"])
        self.assertFalse(backend_plan["boundary_flags"]["confirmation_accepted_in_this_phase"])
        self.assertFalse(backend_plan["boundary_flags"]["confirmation_enforced_in_this_phase"])
        self.assertFalse(backend_plan["boundary_flags"]["automatic_registration_approval_claimed"])
        self.assertTrue(all(bool(value) for value in backend_plan["prerequisite_surface_status"].values()))

        report_lower = backend_report.lower()
        self.assertNotIn(str(valid_root).lower(), report_lower)
        self.assertNotIn("c:\\users\\", report_lower)
        self.assertNotIn("/users/", report_lower)
        self.assertNotIn("/home/", report_lower)
        self.assertNotIn("{", backend_report)
        self.assertNotIn('"expected_outcome"', report_lower)
        self.assertNotIn("traceback", report_lower)
        self.assertIn("required future preconditions:", report_lower)
        self.assertIn("planned future execution steps:", report_lower)
        self.assertIn("planned future post-registration checks:", report_lower)
        self.assertIn("required future safeguards:", report_lower)
        self.assertIn("confirmation accepted in this phase: false", report_lower)
        self.assertIn("confirmation enforced in this phase: false", report_lower)
        self.assertIn("it does not register records.", report_lower)
        self.assertIn("it does not create record sets.", report_lower)
        self.assertIn("it does not persist a plan.", report_lower)
        self.assertIn("it does not create indexes or receipts.", report_lower)
        self.assertIn("it does not repair records.", report_lower)
        self.assertIn("it does not migrate records.", report_lower)
        self.assertIn("it does not accept or enforce confirmation in this phase.", report_lower)
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
            self.assertNotIn(forbidden_score, backend_report)
            self.assertNotIn(forbidden_score, json.dumps(backend_plan, sort_keys=True))

        doc_text = Path(
            "docs/PHASE_13B_CONTROLLED_OUTCOME_TRUTH_RECORD_SET_REGISTRATION_WORKFLOW_BACKEND_PLAN.md"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "The backend plan is a read-only, non-executing plan for a future controlled outcome-truth record-set registration workflow.",
            doc_text,
        )
        self.assertIn("It does not register records.", doc_text)
        self.assertIn("It does not create record sets.", doc_text)
        self.assertIn("It does not persist a plan.", doc_text)
        self.assertIn("It does not create indexes or receipts.", doc_text)
        self.assertIn("It does not repair records.", doc_text)
        self.assertIn("It does not migrate records.", doc_text)
        self.assertIn("It does not accept or enforce confirmation in this phase.", doc_text)
        self.assertIn("It performs no writes and creates no storage.", doc_text)
        self.assertIn("Phase 13C - Controlled Outcome-Truth Registration Workflow Backend Plan API/UI Seam", doc_text)

    def test_controlled_outcome_truth_registration_backend_plan_identity_is_deterministic_candidate_bound_and_stale_safe(self) -> None:
        self.assertTrue(callable(truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan))
        self.assertTrue(callable(truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding))
        self.assertTrue(callable(truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_report))

        plan_source = inspect.getsource(
            truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan
        )
        validator_source = inspect.getsource(
            truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding
        )
        binding_report_source = inspect.getsource(
            truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_report
        )
        for source in (plan_source, validator_source, binding_report_source):
            for forbidden_call in (
                "register_deployed_rule_outcome_truth_record_set(",
                "build_deployed_rule_outcome_truth_source_plan(",
                "record_deployed_rule_outcome_truth_source_result(",
                "_ensure_dirs(",
                "json.dump(",
                "write_text(",
                "_atomic_write_json(",
            ):
                self.assertNotIn(forbidden_call, source)
            for forbidden_nondeterminism in ("uuid.uuid4", "random.", "time.time", "datetime.now", "datetime.utcnow", "tempfile", "id(", "hash("):
                self.assertNotIn(forbidden_nondeterminism, source)

        for signature in (
            inspect.signature(truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan),
            inspect.signature(truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding),
        ):
            for forbidden_parameter in (
                "candidate_fingerprint",
                "planning_gate_fingerprint",
                "backend_plan_fingerprint",
                "execution_authorized",
                "registration_authorized",
                "confirmation_accepted",
                "confirmation_enforced",
                "automatic_registration_approval_claimed",
                "structurally_ready_for_registration",
                "backend_plan_ready_for_future_execution",
            ):
                self.assertNotIn(forbidden_parameter, signature.parameters)

        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "binding"
            identity = _write_telemetry_snapshot_fixture(root)
            candidate = {
                "source_authority_class": "authoritative",
                "source_type": "external_authoritative_result",
                "source_id": "source-1",
                "outcome_truth_record_set_id": "candidate-set-1",
                **identity,
                "records": [
                    {
                        "source_authority_class": "authoritative",
                        "source_type": "external_authoritative_result",
                        "source_id": "source-1",
                        "truth_status": "valid",
                        "outcome_observed_at": "2026-07-10T11:00:00Z",
                        "actual_or_adjudicated_outcome": "venus_day",
                        "expected_outcome": "venus_day",
                        "execution_event_id": "event-1",
                    }
                ],
            }
            reordered_candidate = {
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
                **identity,
                "outcome_truth_record_set_id": "candidate-set-1",
                "source_id": "source-1",
                "source_type": "external_authoritative_result",
                "source_authority_class": "authoritative",
            }
            changed_candidate = deepcopy(candidate)
            changed_candidate["records"][0]["actual_or_adjudicated_outcome"] = "mars_day"

            before_tree = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
            original_candidate = deepcopy(candidate)
            plan_one = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan(candidate, root=root)
            plan_two = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan(deepcopy(candidate), root=root)
            plan_reordered = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan(reordered_candidate, root=root)
            binding_valid = truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding(plan_one, candidate, root=root)
            binding_stale = truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding(plan_one, changed_candidate, root=root)
            modified_plan = deepcopy(plan_one)
            modified_plan["required_future_confirmation"] = "WRONG"
            binding_modified = truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding(modified_plan, candidate, root=root)
            altered_planning_plan = deepcopy(plan_one)
            altered_planning_plan["planning_gate_fingerprint"] = "sha256:" + "0" * 64
            binding_planning_mismatch = truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding(altered_planning_plan, candidate, root=root)
            malformed_identity_plan = deepcopy(plan_one)
            del malformed_identity_plan["candidate_fingerprint"]
            malformed_identity_plan["backend_plan_fingerprint"] = "bad"
            binding_malformed = truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding(malformed_identity_plan, candidate, root=root)
            binding_report = truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_report(plan_one, candidate, root=root)
            after_tree = sorted(str(path.relative_to(root)) for path in root.rglob("*"))

        self.assertEqual(before_tree, after_tree)
        self.assertEqual(candidate, original_candidate)

        self.assertTrue(plan_one["candidate_input_mutation_check_performed"])
        self.assertFalse(plan_one["candidate_input_mutated"])
        self.assertEqual(plan_one["backend_plan_identity_schema_version"], 1)
        self.assertEqual(plan_one["candidate_fingerprint_algorithm"], "sha256")
        self.assertEqual(plan_one["planning_gate_fingerprint_algorithm"], "sha256")
        self.assertEqual(plan_one["backend_plan_fingerprint_algorithm"], "sha256")
        self.assertTrue(plan_one["identity_deterministic"])
        self.assertTrue(plan_one["identity_public_safe"])
        self.assertTrue(plan_one["candidate_fingerprint"].startswith("sha256:"))
        self.assertTrue(plan_one["planning_gate_fingerprint"].startswith("sha256:"))
        self.assertTrue(plan_one["backend_plan_fingerprint"].startswith("sha256:"))
        self.assertEqual(plan_one["candidate_fingerprint"], plan_two["candidate_fingerprint"])
        self.assertEqual(plan_one["planning_gate_fingerprint"], plan_two["planning_gate_fingerprint"])
        self.assertEqual(plan_one["backend_plan_fingerprint"], plan_two["backend_plan_fingerprint"])
        self.assertEqual(plan_one["candidate_fingerprint"], plan_reordered["candidate_fingerprint"])
        self.assertEqual(plan_one["planning_gate_fingerprint"], plan_reordered["planning_gate_fingerprint"])
        self.assertEqual(plan_one["backend_plan_fingerprint"], plan_reordered["backend_plan_fingerprint"])
        changed_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan(changed_candidate, root=root)
        self.assertNotEqual(plan_one["candidate_fingerprint"], changed_plan["candidate_fingerprint"])
        self.assertNotEqual(plan_one["backend_plan_fingerprint"], changed_plan["backend_plan_fingerprint"])

        self.assertEqual(binding_valid["status"], "valid")
        self.assertTrue(binding_valid["binding_valid"])
        self.assertTrue(binding_valid["candidate_binding_valid"])
        self.assertTrue(binding_valid["planning_gate_binding_valid"])
        self.assertTrue(binding_valid["backend_plan_integrity_valid"])
        self.assertFalse(binding_valid["stale_candidate_detected"])
        self.assertFalse(binding_valid["backend_plan_modified_detected"])

        self.assertEqual(binding_stale["status"], "stale")
        self.assertFalse(binding_stale["binding_valid"])
        self.assertFalse(binding_stale["candidate_binding_valid"])
        self.assertTrue(binding_stale["stale_candidate_detected"])
        self.assertFalse(binding_stale["execution_authorized"])
        self.assertFalse(binding_stale["registration_authorized"])
        self.assertIn("backend_plan_candidate_fingerprint_mismatch", binding_stale["blockers"])

        self.assertEqual(binding_modified["status"], "modified")
        self.assertFalse(binding_modified["backend_plan_integrity_valid"])
        self.assertTrue(binding_modified["backend_plan_modified_detected"])
        self.assertFalse(binding_modified["binding_valid"])
        self.assertIn("backend_plan_fingerprint_mismatch", binding_modified["blockers"])

        self.assertFalse(binding_planning_mismatch["planning_gate_binding_valid"])
        self.assertIn("backend_plan_planning_gate_fingerprint_mismatch", binding_planning_mismatch["blockers"])

        self.assertEqual(binding_malformed["status"], "malformed")
        self.assertGreaterEqual(binding_malformed["missing_identity_field_count"], 1)
        self.assertGreaterEqual(binding_malformed["malformed_identity_field_count"], 1)

        for payload in (plan_one, binding_valid, binding_stale, binding_modified):
            self.assertFalse(payload["execution_authorized"])
            self.assertFalse(payload["registration_authorized"])
            self.assertFalse(payload["confirmation_accepted"])
            self.assertFalse(payload["confirmation_enforced"])
            self.assertEqual(payload["writes_performed"], 0)

        self.assertFalse(plan_one["automatic_registration_approval_claimed"])
        self.assertFalse(plan_one["backend_plan_persisted"])
        self.assertFalse(plan_one["controlled_registration_implemented"])
        self.assertFalse(plan_one["registration_performed"])
        self.assertFalse(plan_one["record_set_written"])
        self.assertFalse(plan_one["records_repaired"])
        self.assertFalse(plan_one["records_migrated"])

        report_lower = binding_report.lower()
        self.assertNotIn("venus_day", report_lower)
        self.assertNotIn("mars_day", report_lower)
        self.assertNotIn(str(root).lower(), report_lower)
        self.assertNotIn("c:\\users\\", report_lower)
        self.assertNotIn("/users/", report_lower)
        self.assertNotIn("/home/", report_lower)
        self.assertNotIn("traceback", report_lower)
        self.assertIn("limitations:", report_lower)
        self.assertIn("structural binding", report_lower)
        self.assertIn("does not authorize registration.", report_lower)
        self.assertIn("does not prove factual correctness", report_lower)
        self.assertIn("writes performed: 0", report_lower)

        for forbidden_score in (
            "effectiveness_score",
            "correctness_score",
            "success_rate",
            "failure_rate",
            "final_score",
            "quality_score",
            "aggregate score",
            "rank results",
            "compare results",
        ):
            self.assertNotIn(forbidden_score, binding_report)
            self.assertNotIn(forbidden_score, json.dumps(plan_one, sort_keys=True))
            self.assertNotIn(forbidden_score, json.dumps(binding_valid, sort_keys=True))

        doc_text = Path(
            "docs/PHASE_13C_CONTROLLED_OUTCOME_TRUTH_REGISTRATION_BACKEND_PLAN_IDENTITY_DETERMINISM_STALE_CANDIDATE_GATE.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Phase 13C adds deterministic identity and binding to the non-executing controlled registration backend plan.", doc_text)
        self.assertIn("A valid backend-plan fingerprint proves integrity against the defined canonical representation only.", doc_text)
        self.assertIn("It does not prove factual correctness of the underlying outcome-truth records.", doc_text)
        self.assertIn("backend_plan_ready_for_future_execution is structural readiness only.", doc_text)
        self.assertIn("It is not execution authorization.", doc_text)
        self.assertIn("It is not registration authorization.", doc_text)

    def test_controlled_outcome_truth_registration_backend_plan_api_ui_seam_preserves_identity_binding_stale_state_and_non_authorization(self) -> None:
        self.assertTrue(callable(api.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan))
        self.assertTrue(callable(api.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report))
        self.assertTrue(callable(api.validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding))
        self.assertTrue(callable(api.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_report))

        for signature in (
            inspect.signature(api.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan),
            inspect.signature(api.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report),
            inspect.signature(api.validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding),
            inspect.signature(api.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_report),
        ):
            self.assertIn("root", signature.parameters)
            for forbidden_parameter in (
                "candidate_fingerprint",
                "planning_gate_fingerprint",
                "backend_plan_fingerprint",
                "identity_deterministic",
                "identity_public_safe",
                "binding_valid",
                "candidate_binding_valid",
                "planning_gate_binding_valid",
                "backend_plan_integrity_valid",
                "stale_candidate_detected",
                "backend_plan_modified_detected",
                "backend_plan_ready_for_future_execution",
                "execution_authorized",
                "registration_authorized",
                "confirmation",
                "confirmation_accepted",
                "confirmation_enforced",
                "required_future_confirmation",
                "required_future_preconditions",
                "required_future_safeguards",
                "automatic_registration_approval_claimed",
                "register",
                "execute",
                "commit",
                "repair",
                "migrate",
                "override",
                "force",
                "score",
                "metric",
                "authority_scope",
                "aggregate_method",
                "ranking_method",
            ):
                self.assertNotIn(forbidden_parameter, signature.parameters)

        api_source = inspect.getsource(api)
        desktop_source = inspect.getsource(desktop_panel)
        for expected in (
            "build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan",
            "format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report",
            "validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding",
            "format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_report",
            "Controlled Registration Backend Plan",
            "Build Controlled Registration Backend Plan",
            "Validate Backend Plan Binding",
            "Copy Controlled Registration Backend Plan Report",
            "Copy Backend Plan Binding Report",
        ):
            self.assertIn(expected, api_source if "backend_plan" in expected or "binding_report" in expected else desktop_source)
        self.assertIn("Outcome Truth Record JSON", desktop_source)
        for forbidden_direct_call in (
            "register_deployed_rule_outcome_truth_record_set(",
            "build_deployed_rule_outcome_truth_source_plan(",
            "record_deployed_rule_outcome_truth_source_result(",
            "_ensure_dirs(",
            "json.dump(",
            "write_text(",
            "_atomic_write_json(",
        ):
            self.assertNotIn(forbidden_direct_call, inspect.getsource(api.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan))
            self.assertNotIn(forbidden_direct_call, inspect.getsource(api.validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding))

        class _Var:
            def __init__(self, value: str) -> None:
                self._value = value
            def get(self) -> str:
                return self._value
            def set(self, value: str) -> None:
                self._value = value

        class _FakePanel:
            pass

        panel = _FakePanel()
        panel.deployed_rule_outcome_truth_status_var = _Var("")
        panel.status_var = _Var("")
        panel.deployed_rule_outcome_truth_rule_id_var = _Var("")
        panel.deployed_rule_outcome_truth_result_id_var = _Var("")
        panel.deployed_rule_outcome_truth_target_id_var = _Var("")
        panel.deployed_rule_outcome_truth_deployed_rule_id_var = _Var("")
        panel.deployed_rule_outcome_truth_snapshot_id_var = _Var("")
        panel.deployed_rule_outcome_truth_readiness_result_id_var = _Var("")
        panel.deployed_rule_outcome_truth_spec_result_id_var = _Var("")
        panel.deployed_rule_outcome_truth_start_var = _Var("")
        panel.deployed_rule_outcome_truth_end_var = _Var("")
        panel.deployed_rule_outcome_truth_source_id_var = _Var("")
        panel.deployed_rule_outcome_truth_record_set_id_var = _Var("")
        panel.deployed_rule_outcome_truth_record_json_var = _Var("")
        panel.deployed_rule_outcome_truth_plan_id_var = _Var("")
        panel.deployed_rule_outcome_truth_result_record_id_var = _Var("")
        panel.deployed_rule_outcome_truth_registration_confirmation_var = _Var("")
        panel.deployed_rule_outcome_truth_result_confirmation_var = _Var("")
        panel.pdf_viewport_id_var = _Var("")
        panel.current_controlled_registration_backend_plan = None
        panel.current_controlled_registration_backend_plan_candidate_fingerprint = None
        panel.current_controlled_registration_backend_plan_stale = False
        panel.current_controlled_registration_backend_plan_binding_result = None
        panel.clipboard_value = ""
        panel._current_source_document_id = lambda: "doc-1"
        panel.clipboard_clear = lambda: setattr(panel, "clipboard_value", "")
        panel.clipboard_append = lambda text: setattr(panel, "clipboard_value", text)
        panel._set_deployed_rule_outcome_truth_status = desktop_panel.DesktopRightPanelMixin._set_deployed_rule_outcome_truth_status.__get__(panel, _FakePanel)
        panel._parse_deployed_rule_outcome_truth_candidate_record_set = desktop_panel.DesktopRightPanelMixin._parse_deployed_rule_outcome_truth_candidate_record_set.__get__(panel, _FakePanel)
        panel._mark_deployed_rule_outcome_truth_stale = desktop_panel.DesktopRightPanelMixin._mark_deployed_rule_outcome_truth_stale.__get__(panel, _FakePanel)
        panel._on_deployed_rule_outcome_truth_input_changed = desktop_panel.DesktopRightPanelMixin._on_deployed_rule_outcome_truth_input_changed.__get__(panel, _FakePanel)
        panel._controlled_registration_backend_plan_blocked_payload = desktop_panel.DesktopRightPanelMixin._controlled_registration_backend_plan_blocked_payload.__get__(panel, _FakePanel)
        panel._controlled_registration_backend_plan_loaded = desktop_panel.DesktopRightPanelMixin._controlled_registration_backend_plan_loaded.__get__(panel, _FakePanel)
        panel._run_pdf_viewport_action = desktop_panel.DesktopRightPanelMixin._run_pdf_viewport_action.__get__(panel, _FakePanel)

        self.assertIsNone(panel._parse_deployed_rule_outcome_truth_candidate_record_set())
        self.assertIn("candidate_record_set_required", panel.deployed_rule_outcome_truth_status_var.get())
        panel.deployed_rule_outcome_truth_record_json_var.set("{bad")
        self.assertIsNone(panel._parse_deployed_rule_outcome_truth_candidate_record_set())
        self.assertIn("candidate_record_set_malformed", panel.deployed_rule_outcome_truth_status_var.get())

        original_build = desktop_panel.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan
        original_plan_report = desktop_panel.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report
        original_validate = desktop_panel.validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding
        original_binding_report = desktop_panel.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_report
        try:
            candidate = {
                "b": 2,
                "a": 1,
                "records": [],
            }
            equivalent_candidate = {
                "a": 1,
                "b": 2,
                "records": [],
            }
            changed_candidate = {
                "a": 1,
                "b": 3,
                "records": [],
            }
            build_calls = []
            validate_calls = []

            def _fake_build(candidate_record_set, *, root=Path("data/source_documents")):
                build_calls.append(candidate_record_set)
                status = "plan_ready" if candidate_record_set.get("b") == 2 else "blocked"
                return {
                    "status": status,
                    "backend_plan_status": status,
                    "planning_gate_status": "planning_ready" if status == "plan_ready" else "blocked",
                    "candidate_qa_status": "passed" if status == "plan_ready" else "blocked",
                    "candidate_structurally_ready_for_registration": status == "plan_ready",
                    "backend_plan_ready_for_future_execution": status == "plan_ready",
                    "backend_plan_identity_schema_version": 1,
                    "candidate_fingerprint": "sha256:candidatefull",
                    "planning_gate_fingerprint": "sha256:planningfull",
                    "backend_plan_fingerprint": "sha256:planfull",
                    "execution_authorized": False,
                    "registration_authorized": False,
                    "confirmation_accepted": False,
                    "confirmation_enforced": False,
                    "automatic_registration_approval_claimed": False,
                    "backend_plan_persisted": False,
                    "controlled_registration_implemented": False,
                    "registration_performed": False,
                    "record_set_written": False,
                    "records_repaired": False,
                    "records_migrated": False,
                    "blockers": [] if status == "plan_ready" else ["backend_plan_candidate_input_stale"],
                    "warnings": [],
                    "recommended_action": "Structural readiness is not execution or registration authorization.",
                    "limitations": ["The backend plan is a deterministic, read-only, non-executing structural plan."],
                    "writes_performed": 0,
                }

            def _fake_plan_report(candidate_record_set, *, root=Path("data/source_documents")):
                return (
                    "Controlled backend plan report\n"
                    "Candidate fingerprint: sha256:candidatefull\n"
                    "Planning-gate fingerprint: sha256:planningfull\n"
                    "Backend-plan fingerprint: sha256:planfull\n"
                    "Structural readiness is not execution authorization.\n"
                    "Writes performed: 0"
                )

            def _fake_validate(backend_plan, candidate_record_set, *, root=Path("data/source_documents")):
                validate_calls.append((backend_plan, candidate_record_set))
                stale = candidate_record_set.get("b") != 2
                modified = backend_plan.get("backend_plan_fingerprint") != "sha256:planfull"
                status = "valid"
                blockers = []
                if stale:
                    status = "stale"
                    blockers.append("backend_plan_candidate_fingerprint_mismatch")
                if modified:
                    status = "modified"
                    blockers.append("backend_plan_fingerprint_mismatch")
                return {
                    "status": status,
                    "binding_status": status,
                    "binding_valid": not stale and not modified,
                    "candidate_binding_valid": not stale,
                    "planning_gate_binding_valid": True,
                    "backend_plan_integrity_valid": not modified,
                    "stale_candidate_detected": stale,
                    "backend_plan_modified_detected": modified,
                    "execution_authorized": False,
                    "registration_authorized": False,
                    "confirmation_accepted": False,
                    "confirmation_enforced": False,
                    "automatic_registration_approval_claimed": False,
                    "backend_plan_ready_for_future_execution": not stale and not modified,
                    "backend_plan_identity_schema_version": 1,
                    "candidate_fingerprint": backend_plan.get("candidate_fingerprint", "sha256:candidatefull"),
                    "planning_gate_fingerprint": backend_plan.get("planning_gate_fingerprint", "sha256:planningfull"),
                    "backend_plan_fingerprint": backend_plan.get("backend_plan_fingerprint", "sha256:planfull"),
                    "blockers": blockers,
                    "warnings": [],
                    "recommended_action": "Rebuild the controlled registration backend plan or rerun deterministic binding validation after changing candidate input.",
                    "limitations": ["A valid fingerprint proves integrity against the defined canonical representation only."],
                    "writes_performed": 0,
                }

            def _fake_binding_report(backend_plan, candidate_record_set, *, root=Path("data/source_documents")):
                return (
                    "Controlled binding report\n"
                    "Binding valid: true\n"
                    "Candidate fingerprint: sha256:candidatefull\n"
                    "Planning-gate fingerprint: sha256:planningfull\n"
                    "Backend-plan fingerprint: sha256:planfull\n"
                    "A valid fingerprint proves integrity against the defined canonical representation only.\n"
                    "Writes performed: 0"
                )

            desktop_panel.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan = _fake_build
            desktop_panel.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report = _fake_plan_report
            desktop_panel.validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding = _fake_validate
            desktop_panel.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_report = _fake_binding_report

            panel.deployed_rule_outcome_truth_record_json_var.set(json.dumps(candidate))
            panel._run_pdf_viewport_action("build_deployed_rule_outcome_truth_controlled_registration_backend_plan")
            self.assertEqual(build_calls[-1], candidate)
            self.assertIsInstance(panel.current_controlled_registration_backend_plan, dict)
            status_text = panel.deployed_rule_outcome_truth_status_var.get()
            self.assertIn("Controlled Registration Backend Plan Status: plan_ready", status_text)
            self.assertIn("Identity Schema Version: 1", status_text)
            self.assertIn("Candidate Fingerprint: sha256:candidatefull", status_text)
            self.assertIn("Planning-Gate Fingerprint: sha256:planningfull", status_text)
            self.assertIn("Backend-Plan Fingerprint: sha256:planfull", status_text)
            self.assertIn("Structurally Ready For Future Execution Planning: yes", status_text)
            self.assertIn("Execution Authorized: no", status_text)
            self.assertIn("Registration Authorized: no", status_text)
            self.assertIn("Confirmation Accepted: no", status_text)
            self.assertIn("Confirmation Enforced: no", status_text)
            self.assertIn("Automatic Registration Approval Claimed: no", status_text)

            panel.deployed_rule_outcome_truth_record_json_var.set(json.dumps(changed_candidate))
            panel._on_deployed_rule_outcome_truth_input_changed()
            stale_status = panel.deployed_rule_outcome_truth_status_var.get()
            self.assertIn("Controlled Registration Backend Plan Status: backend_plan_candidate_input_stale", stale_status)
            self.assertIn("Backend Plan Current: no", stale_status)
            self.assertIn("Stale Candidate Detected: yes", stale_status)
            self.assertIn("Execution Authorized: no", stale_status)

            panel._run_pdf_viewport_action("copy_deployed_rule_outcome_truth_controlled_registration_backend_plan_report")
            self.assertIn("backend_plan_candidate_input_stale", panel.status_var.get())

            panel.deployed_rule_outcome_truth_record_json_var.set(json.dumps(equivalent_candidate))
            panel._run_pdf_viewport_action("validate_deployed_rule_outcome_truth_controlled_registration_backend_plan_binding")
            self.assertEqual(validate_calls[-1][1], equivalent_candidate)
            self.assertFalse(panel.current_controlled_registration_backend_plan_stale)
            valid_status = panel.deployed_rule_outcome_truth_status_var.get()
            self.assertIn("Binding Status: valid", valid_status)
            self.assertIn("Candidate Binding Valid: yes", valid_status)
            self.assertIn("Planning-Gate Binding Valid: yes", valid_status)
            self.assertIn("Backend-Plan Integrity Valid: yes", valid_status)
            self.assertIn("Backend Plan Current: yes", valid_status)

            panel._run_pdf_viewport_action("copy_deployed_rule_outcome_truth_controlled_registration_backend_plan_report")
            self.assertIn("sha256:planfull", panel.clipboard_value)
            self.assertNotIn("{", panel.clipboard_value)

            panel._run_pdf_viewport_action("copy_deployed_rule_outcome_truth_controlled_registration_backend_plan_binding_report")
            self.assertIn("A valid fingerprint proves integrity", panel.clipboard_value)
            self.assertNotIn("{", panel.clipboard_value)
            self.assertNotIn("c:\\users\\", panel.clipboard_value.lower())
            self.assertNotIn("traceback", panel.clipboard_value.lower())

            panel.current_controlled_registration_backend_plan = {"bad": "plan"}
            panel.deployed_rule_outcome_truth_record_json_var.set(json.dumps(candidate))
            panel._run_pdf_viewport_action("validate_deployed_rule_outcome_truth_controlled_registration_backend_plan_binding")
            self.assertIn("backend_plan_malformed", panel.deployed_rule_outcome_truth_status_var.get())

            panel.current_controlled_registration_backend_plan = None
            panel._run_pdf_viewport_action("validate_deployed_rule_outcome_truth_controlled_registration_backend_plan_binding")
            self.assertIn("backend_plan_required", panel.deployed_rule_outcome_truth_status_var.get())
        finally:
            desktop_panel.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan = original_build
            desktop_panel.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report = original_plan_report
            desktop_panel.validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding = original_validate
            desktop_panel.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_report = original_binding_report

        doc_text = Path(
            "docs/PHASE_13D_CONTROLLED_OUTCOME_TRUTH_REGISTRATION_BACKEND_PLAN_API_UI_SEAM.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Phase 13D exposes the deterministic backend plan and its binding validator through a read-only API/UI seam.", doc_text)
        self.assertIn("The backend plan remains in memory only.", doc_text)
        self.assertIn("No plan is persisted.", doc_text)
        self.assertIn("No registration is executed.", doc_text)
        self.assertIn("No confirmation is accepted or enforced.", doc_text)
        self.assertIn("backend_plan_ready_for_future_execution is structural readiness only.", doc_text)
        self.assertIn("It is not execution authorization.", doc_text)
        self.assertIn("It is not registration authorization.", doc_text)
        self.assertIn("Candidate input changes make the displayed plan stale until deterministic binding is validated or the plan is rebuilt.", doc_text)

    def test_controlled_registration_backend_plan_ui_renders_explicit_blockers_and_preserves_stale_safe_statuses(self) -> None:
        status_source = inspect.getsource(desktop_panel.DesktopRightPanelMixin._set_deployed_rule_outcome_truth_status)
        stale_source = inspect.getsource(desktop_panel.DesktopRightPanelMixin._mark_deployed_rule_outcome_truth_stale)
        self.assertIn("Blockers:", status_source)
        self.assertIn("Warnings:", status_source)
        self.assertIn("Recommended Action:", status_source)
        self.assertIn("Limitations:", status_source)
        self.assertIn("backend_plan_candidate_input_stale", stale_source)

        class _Var:
            def __init__(self, value: str) -> None:
                self._value = value
            def get(self) -> str:
                return self._value
            def set(self, value: str) -> None:
                self._value = value

        class _FakePanel:
            pass

        panel = _FakePanel()
        panel.deployed_rule_outcome_truth_status_var = _Var("")
        panel.status_var = _Var("")
        panel.deployed_rule_outcome_truth_rule_id_var = _Var("")
        panel.deployed_rule_outcome_truth_result_id_var = _Var("")
        panel.deployed_rule_outcome_truth_target_id_var = _Var("")
        panel.deployed_rule_outcome_truth_deployed_rule_id_var = _Var("")
        panel.deployed_rule_outcome_truth_snapshot_id_var = _Var("")
        panel.deployed_rule_outcome_truth_readiness_result_id_var = _Var("")
        panel.deployed_rule_outcome_truth_spec_result_id_var = _Var("")
        panel.deployed_rule_outcome_truth_start_var = _Var("")
        panel.deployed_rule_outcome_truth_end_var = _Var("")
        panel.deployed_rule_outcome_truth_source_id_var = _Var("")
        panel.deployed_rule_outcome_truth_record_set_id_var = _Var("")
        panel.deployed_rule_outcome_truth_record_json_var = _Var("")
        panel.deployed_rule_outcome_truth_plan_id_var = _Var("")
        panel.deployed_rule_outcome_truth_result_record_id_var = _Var("")
        panel.deployed_rule_outcome_truth_registration_confirmation_var = _Var("")
        panel.deployed_rule_outcome_truth_result_confirmation_var = _Var("")
        panel.pdf_viewport_id_var = _Var("")
        panel.current_controlled_registration_backend_plan = None
        panel.current_controlled_registration_backend_plan_candidate_fingerprint = None
        panel.current_controlled_registration_backend_plan_stale = False
        panel.current_controlled_registration_backend_plan_binding_result = None
        panel.clipboard_value = ""
        panel._current_source_document_id = lambda: "doc-1"
        panel.clipboard_clear = lambda: setattr(panel, "clipboard_value", "")
        panel.clipboard_append = lambda text: setattr(panel, "clipboard_value", text)
        panel._set_deployed_rule_outcome_truth_status = desktop_panel.DesktopRightPanelMixin._set_deployed_rule_outcome_truth_status.__get__(panel, _FakePanel)
        panel._parse_deployed_rule_outcome_truth_candidate_record_set = desktop_panel.DesktopRightPanelMixin._parse_deployed_rule_outcome_truth_candidate_record_set.__get__(panel, _FakePanel)
        panel._mark_deployed_rule_outcome_truth_stale = desktop_panel.DesktopRightPanelMixin._mark_deployed_rule_outcome_truth_stale.__get__(panel, _FakePanel)
        panel._on_deployed_rule_outcome_truth_input_changed = desktop_panel.DesktopRightPanelMixin._on_deployed_rule_outcome_truth_input_changed.__get__(panel, _FakePanel)
        panel._controlled_registration_backend_plan_blocked_payload = desktop_panel.DesktopRightPanelMixin._controlled_registration_backend_plan_blocked_payload.__get__(panel, _FakePanel)
        panel._controlled_registration_backend_plan_loaded = desktop_panel.DesktopRightPanelMixin._controlled_registration_backend_plan_loaded.__get__(panel, _FakePanel)
        panel._run_pdf_viewport_action = desktop_panel.DesktopRightPanelMixin._run_pdf_viewport_action.__get__(panel, _FakePanel)

        panel.deployed_rule_outcome_truth_record_json_var.set("")
        self.assertIsNone(panel._parse_deployed_rule_outcome_truth_candidate_record_set())
        self.assertIn("candidate_record_set_required", panel.deployed_rule_outcome_truth_status_var.get())
        self.assertIn("Blockers: candidate_record_set_required", panel.deployed_rule_outcome_truth_status_var.get())

        panel.deployed_rule_outcome_truth_record_json_var.set("{bad")
        self.assertIsNone(panel._parse_deployed_rule_outcome_truth_candidate_record_set())
        self.assertIn("candidate_record_set_malformed", panel.deployed_rule_outcome_truth_status_var.get())
        self.assertIn("Blockers: candidate_record_set_malformed", panel.deployed_rule_outcome_truth_status_var.get())
        self.assertNotIn("traceback", panel.deployed_rule_outcome_truth_status_var.get().lower())

        panel.deployed_rule_outcome_truth_record_json_var.set("[]")
        self.assertIsNone(panel._parse_deployed_rule_outcome_truth_candidate_record_set())
        self.assertIn("candidate_record_set_malformed", panel.deployed_rule_outcome_truth_status_var.get())

        original_build = desktop_panel.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan
        original_plan_report = desktop_panel.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report
        original_validate = desktop_panel.validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding
        original_binding_report = desktop_panel.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_report
        try:
            candidate = {"a": 1, "b": 2, "records": []}
            equivalent_candidate = {"records": [], "b": 2, "a": 1}
            changed_candidate = {"a": 1, "b": 3, "records": []}

            def _fake_build(candidate_record_set, *, root=Path("data/source_documents")):
                return {
                    "status": "plan_ready",
                    "backend_plan_status": "plan_ready",
                    "planning_gate_status": "planning_ready",
                    "candidate_qa_status": "passed",
                    "candidate_structurally_ready_for_registration": True,
                    "backend_plan_ready_for_future_execution": True,
                    "backend_plan_identity_schema_version": 1,
                    "candidate_fingerprint": "sha256:candidatefull",
                    "planning_gate_fingerprint": "sha256:planningfull",
                    "backend_plan_fingerprint": "sha256:planfull",
                    "execution_authorized": False,
                    "registration_authorized": False,
                    "confirmation_accepted": False,
                    "confirmation_enforced": False,
                    "automatic_registration_approval_claimed": False,
                    "backend_plan_persisted": False,
                    "controlled_registration_implemented": False,
                    "registration_performed": False,
                    "record_set_written": False,
                    "records_repaired": False,
                    "records_migrated": False,
                    "blockers": [],
                    "warnings": ["structurally_ready_only"],
                    "recommended_action": "Structurally ready only; execution and registration remain unauthorized.",
                    "limitations": ["The backend plan is a deterministic, read-only, non-executing structural plan."],
                    "writes_performed": 0,
                }

            def _fake_plan_report(candidate_record_set, *, root=Path("data/source_documents")):
                return (
                    "Controlled backend plan report\n"
                    "Status: plan_ready\n"
                    "Blockers: none\n"
                    "Warnings: structurally_ready_only\n"
                    "Candidate fingerprint: sha256:candidatefull\n"
                    "Planning-gate fingerprint: sha256:planningfull\n"
                    "Backend-plan fingerprint: sha256:planfull\n"
                    "Structurally ready only; execution and registration remain unauthorized.\n"
                    "Limitations: The backend plan is a deterministic, read-only, non-executing structural plan.\n"
                    "Writes performed: 0"
                )

            def _fake_validate(backend_plan, candidate_record_set, *, root=Path("data/source_documents")):
                stale = candidate_record_set.get("b") != 2
                planning_gate_mismatch = backend_plan.get("planning_gate_fingerprint") != "sha256:planningfull"
                modified = backend_plan.get("backend_plan_fingerprint") != "sha256:planfull"
                blockers = []
                status = "valid"
                if stale:
                    status = "stale"
                    blockers.append("backend_plan_candidate_fingerprint_mismatch")
                if planning_gate_mismatch:
                    status = "modified"
                    blockers.append("backend_plan_planning_gate_fingerprint_mismatch")
                if modified:
                    status = "modified"
                    blockers.append("backend_plan_fingerprint_mismatch")
                return {
                    "status": status,
                    "binding_status": status,
                    "binding_valid": not blockers,
                    "candidate_binding_valid": not stale,
                    "planning_gate_binding_valid": not planning_gate_mismatch,
                    "backend_plan_integrity_valid": not modified,
                    "stale_candidate_detected": stale,
                    "backend_plan_modified_detected": modified,
                    "execution_authorized": False,
                    "registration_authorized": False,
                    "confirmation_accepted": False,
                    "confirmation_enforced": False,
                    "automatic_registration_approval_claimed": False,
                    "backend_plan_ready_for_future_execution": not blockers,
                    "backend_plan_identity_schema_version": 1,
                    "candidate_fingerprint": backend_plan.get("candidate_fingerprint", "sha256:candidatefull"),
                    "planning_gate_fingerprint": backend_plan.get("planning_gate_fingerprint", "sha256:planningfull"),
                    "backend_plan_fingerprint": backend_plan.get("backend_plan_fingerprint", "sha256:planfull"),
                    "blockers": blockers,
                    "warnings": ["binding_review_only"],
                    "recommended_action": "Rebuild the controlled registration backend plan or rerun deterministic binding validation after changing candidate input.",
                    "limitations": ["A valid fingerprint proves integrity against the defined canonical representation only."],
                    "writes_performed": 0,
                }

            def _fake_binding_report(backend_plan, candidate_record_set, *, root=Path("data/source_documents")):
                result = _fake_validate(backend_plan, candidate_record_set, root=root)
                return (
                    "Controlled binding report\n"
                    f"Status: {result['status']}\n"
                    f"Blockers: {', '.join(result['blockers']) if result['blockers'] else 'none'}\n"
                    f"Warnings: {', '.join(result['warnings']) if result['warnings'] else 'none'}\n"
                    f"Candidate fingerprint: {result['candidate_fingerprint']}\n"
                    f"Planning-gate fingerprint: {result['planning_gate_fingerprint']}\n"
                    f"Backend-plan fingerprint: {result['backend_plan_fingerprint']}\n"
                    f"Recommended action: {result['recommended_action']}\n"
                    "Limitations: A valid fingerprint proves integrity against the defined canonical representation only.\n"
                    "Writes performed: 0"
                )

            desktop_panel.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan = _fake_build
            desktop_panel.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report = _fake_plan_report
            desktop_panel.validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding = _fake_validate
            desktop_panel.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_report = _fake_binding_report

            panel.deployed_rule_outcome_truth_record_json_var.set(json.dumps(candidate))
            panel._run_pdf_viewport_action("build_deployed_rule_outcome_truth_controlled_registration_backend_plan")
            build_status = panel.deployed_rule_outcome_truth_status_var.get()
            self.assertIn("Controlled Registration Backend Plan Status: plan_ready", build_status)
            self.assertIn("Candidate Fingerprint: sha256:candidatefull", build_status)
            self.assertIn("Planning-Gate Fingerprint: sha256:planningfull", build_status)
            self.assertIn("Backend-Plan Fingerprint: sha256:planfull", build_status)
            self.assertIn("Backend Plan Current: yes", build_status)
            self.assertIn("Blockers: none", build_status)
            self.assertIn("Warnings: structurally_ready_only", build_status)
            self.assertIn("Recommended Action: Structurally ready only; execution and registration remain unauthorized.", build_status)
            self.assertIn("Limitations: The backend plan is a deterministic, read-only, non-executing structural plan.", build_status)
            self.assertIn("Execution Authorized: no", build_status)
            self.assertIn("Registration Authorized: no", build_status)

            panel._run_pdf_viewport_action("validate_deployed_rule_outcome_truth_controlled_registration_backend_plan_binding")
            valid_status = panel.deployed_rule_outcome_truth_status_var.get()
            self.assertIn("Binding Status: valid", valid_status)
            self.assertIn("Candidate Binding Valid: yes", valid_status)
            self.assertIn("Planning-Gate Binding Valid: yes", valid_status)
            self.assertIn("Backend-Plan Integrity Valid: yes", valid_status)
            self.assertIn("Backend Plan Current: yes", valid_status)
            self.assertIn("Warnings: binding_review_only", valid_status)
            self.assertIn("Execution Authorized: no", valid_status)
            self.assertIn("Registration Authorized: no", valid_status)

            panel.deployed_rule_outcome_truth_record_json_var.set(json.dumps(changed_candidate))
            panel._on_deployed_rule_outcome_truth_input_changed()
            stale_status = panel.deployed_rule_outcome_truth_status_var.get()
            self.assertIn("Controlled Registration Backend Plan Status: backend_plan_candidate_input_stale", stale_status)
            self.assertIn("Backend Plan Current: no", stale_status)
            self.assertIn("Blockers: backend_plan_candidate_input_stale", stale_status)
            self.assertIn("Warnings: none", stale_status)
            self.assertIn("Recommended Action: Rebuild the controlled registration backend plan or rerun deterministic binding validation after changing candidate input.", stale_status)

            panel.clipboard_value = "unchanged"
            panel._run_pdf_viewport_action("copy_deployed_rule_outcome_truth_controlled_registration_backend_plan_report")
            self.assertEqual(panel.clipboard_value, "unchanged")
            self.assertIn("backend_plan_candidate_input_stale", panel.status_var.get())

            panel._run_pdf_viewport_action("copy_deployed_rule_outcome_truth_controlled_registration_backend_plan_binding_report")
            self.assertIn("Status: stale", panel.clipboard_value)
            self.assertIn("backend_plan_candidate_fingerprint_mismatch", panel.clipboard_value)
            self.assertNotIn("{", panel.clipboard_value)
            self.assertNotIn("c:\\users\\", panel.clipboard_value.lower())
            self.assertNotIn("traceback", panel.clipboard_value.lower())

            panel.deployed_rule_outcome_truth_record_json_var.set(json.dumps(equivalent_candidate))
            panel._run_pdf_viewport_action("validate_deployed_rule_outcome_truth_controlled_registration_backend_plan_binding")
            revalidated_status = panel.deployed_rule_outcome_truth_status_var.get()
            self.assertIn("Binding Status: valid", revalidated_status)
            self.assertIn("Backend Plan Current: yes", revalidated_status)
            self.assertFalse(panel.current_controlled_registration_backend_plan_stale)

            panel.current_controlled_registration_backend_plan = dict(panel.current_controlled_registration_backend_plan or {})
            panel.current_controlled_registration_backend_plan["backend_plan_fingerprint"] = "sha256:changed"
            panel._run_pdf_viewport_action("validate_deployed_rule_outcome_truth_controlled_registration_backend_plan_binding")
            modified_status = panel.deployed_rule_outcome_truth_status_var.get()
            self.assertIn("backend_plan_fingerprint_mismatch", modified_status)
            self.assertIn("Backend-Plan Modified Detected: yes", modified_status)
            self.assertIn("Backend Plan Current: no", modified_status)

            panel.current_controlled_registration_backend_plan = dict(panel.current_controlled_registration_backend_plan or {})
            panel.current_controlled_registration_backend_plan["backend_plan_fingerprint"] = "sha256:planfull"
            panel.current_controlled_registration_backend_plan["planning_gate_fingerprint"] = "sha256:wrongplanning"
            panel._run_pdf_viewport_action("validate_deployed_rule_outcome_truth_controlled_registration_backend_plan_binding")
            planning_status = panel.deployed_rule_outcome_truth_status_var.get()
            self.assertIn("backend_plan_planning_gate_fingerprint_mismatch", planning_status)
            self.assertIn("Planning-Gate Binding Valid: no", planning_status)
            self.assertIn("Backend Plan Current: no", planning_status)

            panel.current_controlled_registration_backend_plan = {"bad": "plan"}
            panel._run_pdf_viewport_action("validate_deployed_rule_outcome_truth_controlled_registration_backend_plan_binding")
            malformed_status = panel.deployed_rule_outcome_truth_status_var.get()
            self.assertIn("backend_plan_malformed", malformed_status)
            self.assertIn("Backend Plan Current: no", malformed_status)

            panel.current_controlled_registration_backend_plan = None
            panel._run_pdf_viewport_action("validate_deployed_rule_outcome_truth_controlled_registration_backend_plan_binding")
            missing_status = panel.deployed_rule_outcome_truth_status_var.get()
            self.assertIn("backend_plan_required", missing_status)
            self.assertIn("Backend Plan Current: no", missing_status)
        finally:
            desktop_panel.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan = original_build
            desktop_panel.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report = original_plan_report
            desktop_panel.validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding = original_validate
            desktop_panel.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_report = original_binding_report

        doc_text = Path(
            "docs/PHASE_13D_CONTROLLED_OUTCOME_TRUTH_REGISTRATION_BACKEND_PLAN_API_UI_SEAM.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Explicit Status and Blocker Rendering", doc_text)
        self.assertIn("Backend/API status codes are rendered explicitly", doc_text)
        self.assertIn("candidate_record_set_required", doc_text)
        self.assertIn("backend_plan_candidate_input_stale", doc_text)
        self.assertIn("backend_plan_candidate_fingerprint_mismatch", doc_text)
        self.assertIn("backend_plan_planning_gate_fingerprint_mismatch", doc_text)
        self.assertIn("backend_plan_fingerprint_mismatch", doc_text)

    def test_controlled_registration_backend_plan_api_ui_boundary_audit_and_operator_handoff_preserve_read_only_non_authorization_contract(self) -> None:
        handoff_path = Path(
            "docs/PHASE_13E_CONTROLLED_OUTCOME_TRUTH_REGISTRATION_BACKEND_PLAN_API_UI_BOUNDARY_AUDIT_OPERATOR_HANDOFF.md"
        )
        self.assertTrue(handoff_path.exists())
        handoff_text = handoff_path.read_text(encoding="utf-8")

        for required_heading in (
            "## 1. Purpose",
            "## 2. Scope",
            "## 3. Frozen Feature Surface",
            "## 4. Operator Workflow",
            "## 5. Build Backend Plan",
            "## 6. Validate Backend Plan Binding",
            "## 7. Interpret Identity and Fingerprints",
            "## 8. Interpret Structural Readiness",
            "## 9. Status and Blocker Reference",
            "## 10. Stale-Candidate Workflow",
            "## 11. Modified-Plan Workflow",
            "## 12. Equivalent Candidate JSON Workflow",
            "## 13. Public-Safe Copy Reports",
            "## 14. In-Memory-Only Boundary",
            "## 15. No-Registration / No-Authorization Boundary",
            "## 16. Exact Validation Evidence",
            "## 17. Skipped Broad Tests by Policy",
            "## 18. Known Risks",
            "## 19. Recommended Next Phase",
        ):
            self.assertIn(required_heading, handoff_text)

        for required_phrase in (
            "This handoff covers the deterministic, candidate-bound, stale-safe, read-only controlled-registration backend-plan API/UI seam.",
            "Build Controlled Registration Backend Plan.",
            "Validate Backend Plan Binding",
            "Structurally ready only; execution and registration remain unauthorized.",
            "backend_plan_ready_for_future_execution` is structural readiness only.",
            "candidate_record_set_required",
            "candidate_record_set_malformed",
            "backend_plan_required",
            "backend_plan_malformed",
            "backend_plan_candidate_input_stale",
            "backend_plan_candidate_fingerprint_mismatch",
            "backend_plan_planning_gate_fingerprint_mismatch",
            "backend_plan_fingerprint_mismatch",
            "The backend plan remains in memory only.",
            "The binding result remains in memory only.",
            "No plan ID is created.",
            "No plan index is created.",
            "No receipt is created.",
            "Raw plan dictionaries are not copied.",
            "Raw binding dictionaries are not copied.",
            "Raw candidate JSON is not copied.",
            "Stale plans are not copied as current.",
            "A valid binding proves deterministic identity and integrity against the current canonical representation only.",
            "It does not authorize execution.",
            "It does not authorize registration.",
            "It does not accept or enforce confirmation.",
            "It does not prove factual correctness of outcome-truth records.",
            "test_controlled_outcome_truth_registration_backend_plan_identity_is_deterministic_candidate_bound_and_stale_safe",
            "test_controlled_outcome_truth_registration_backend_plan_api_ui_seam_preserves_identity_binding_stale_state_and_non_authorization",
            "test_controlled_registration_backend_plan_ui_renders_explicit_blockers_and_preserves_stale_safe_statuses",
            "Phase 13F - Controlled Outcome-Truth Registration Backend-Plan API/UI Release Packet and Final Freeze",
            "broad regression coverage remains unclaimed",
        ):
            self.assertIn(required_phrase, handoff_text)

        self.test_controlled_outcome_truth_registration_backend_plan_api_ui_seam_preserves_identity_binding_stale_state_and_non_authorization()
        self.test_controlled_registration_backend_plan_ui_renders_explicit_blockers_and_preserves_stale_safe_statuses()

        for wrapper in (
            api.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan,
            api.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report,
            api.validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding,
            api.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_report,
        ):
            self.assertTrue(callable(wrapper))

        for signature in (
            inspect.signature(api.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan),
            inspect.signature(api.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report),
            inspect.signature(api.validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding),
            inspect.signature(api.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_report),
        ):
            for forbidden_parameter in (
                "candidate_fingerprint",
                "planning_gate_fingerprint",
                "backend_plan_fingerprint",
                "binding_valid",
                "candidate_binding_valid",
                "planning_gate_binding_valid",
                "backend_plan_integrity_valid",
                "confirmation",
                "execution_authorized",
                "registration_authorized",
                "override",
                "force",
                "repair",
                "migrate",
                "score",
            ):
                self.assertNotIn(forbidden_parameter, signature.parameters)

        viewport_action_source = inspect.getsource(desktop_panel.DesktopRightPanelMixin._run_pdf_viewport_action)
        branch_start = viewport_action_source.index('elif action == "build_deployed_rule_outcome_truth_controlled_registration_backend_plan":')
        branch_end = viewport_action_source.index('elif action == "load_deployed_rule_outcome_truth_result":')
        controlled_branch_source = viewport_action_source[branch_start:branch_end]

        relevant_functions = (
            inspect.getsource(api.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan),
            inspect.getsource(api.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report),
            inspect.getsource(api.validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding),
            inspect.getsource(api.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_report),
            controlled_branch_source,
        )
        for forbidden_call in (
            "register_deployed_rule_outcome_truth_record_set(",
            "build_deployed_rule_outcome_truth_source_plan(",
            "record_deployed_rule_outcome_truth_source_result(",
            "_ensure_dirs(",
            "json.dump(",
            "write_text(",
            "_atomic_write_json(",
        ):
            for source in relevant_functions:
                self.assertNotIn(forbidden_call, source)

        desktop_source = inspect.getsource(desktop_panel)
        self.assertIn("current_controlled_registration_backend_plan = None", desktop_source)
        self.assertIn("current_controlled_registration_backend_plan_binding_result = None", desktop_source)
        self.assertIn("Copy Controlled Registration Backend Plan Report", desktop_source)
        self.assertIn("Copy Backend Plan Binding Report", desktop_source)
        for forbidden_control in (
            'text="Register"',
            'text="Execute"',
            'text="Commit"',
            'text="Confirm Registration"',
            'text="Authorize Registration"',
            'text="Auto Register"',
            'text="Force Register"',
            'text="Override Fingerprint"',
            'text="Override Readiness"',
            'text="Override Binding"',
            'text="Manual Score"',
            'text="Aggregate Score"',
            'text="Rank Results"',
        ):
            self.assertNotIn(forbidden_control, desktop_source)

        phase_13d_text = Path(
            "docs/PHASE_13D_CONTROLLED_OUTCOME_TRUTH_REGISTRATION_BACKEND_PLAN_API_UI_SEAM.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Boundary audit/operator handoff:", phase_13d_text)
        self.assertIn(
            "docs/PHASE_13E_CONTROLLED_OUTCOME_TRUTH_REGISTRATION_BACKEND_PLAN_API_UI_BOUNDARY_AUDIT_OPERATOR_HANDOFF.md",
            phase_13d_text,
        )

    def test_controlled_registration_backend_plan_api_ui_release_packet_and_final_freeze_preserve_identity_stale_safety_and_non_authorization(self) -> None:
        release_path = Path(
            "docs/PHASE_13F_CONTROLLED_OUTCOME_TRUTH_REGISTRATION_BACKEND_PLAN_API_UI_RELEASE_PACKET.md"
        )
        self.assertTrue(release_path.exists())
        release_text = release_path.read_text(encoding="utf-8")

        for required_heading in (
            "## 1. Purpose",
            "## 2. Release Scope",
            "## 3. Phase 13C-13F History",
            "## 4. Frozen Backend Surface",
            "## 5. Frozen API Surface",
            "## 6. Frozen Desktop Surface",
            "## 7. Identity and Fingerprint Contract",
            "## 8. Binding Contract",
            "## 9. Stale-Candidate Contract",
            "## 10. Modified-Plan Contract",
            "## 11. Status and Blocker Reference",
            "## 12. Operator Workflow",
            "## 13. Equivalent Candidate JSON Behavior",
            "## 14. Structural Readiness Versus Authorization",
            "## 15. Public-Safe Reports",
            "## 16. In-Memory-Only Boundary",
            "## 17. No-Registration / No-Execution Boundary",
            "## 18. Explicit Non-Claims",
            "## 19. Exact Validation Evidence",
            "## 20. Skipped Broad Tests by Policy",
            "## 21. Known Risks",
            "## 22. Final Freeze Status",
            "## 23. Recommended Next Phase",
        ):
            self.assertIn(required_heading, release_text)

        for required_phrase in (
            "Phase 13C established deterministic identity",
            "Phase 13D exposed the backend plan and binding validator through a narrow read-only API/UI seam.",
            "Phase 13D.1 corrected explicit rendering of existing backend/API status and blocker codes.",
            "Phase 13E completed the API/UI boundary audit and operator handoff.",
            "build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan",
            "format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report",
            "validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding",
            "format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_report",
            "Build Controlled Registration Backend Plan",
            "Validate Backend Plan Binding",
            "Copy Controlled Registration Backend Plan Report",
            "Copy Backend Plan Binding Report",
            "backend_plan_identity_schema_version",
            "candidate_fingerprint",
            "planning_gate_fingerprint",
            "backend_plan_fingerprint",
            "binding_valid",
            "candidate_binding_valid",
            "planning_gate_binding_valid",
            "backend_plan_integrity_valid",
            "backend_plan_candidate_input_stale",
            "backend_plan_candidate_fingerprint_mismatch",
            "backend_plan_planning_gate_fingerprint_mismatch",
            "backend_plan_fingerprint_mismatch",
            "candidate_record_set_required",
            "candidate_record_set_malformed",
            "backend_plan_required",
            "backend_plan_malformed",
            "Equivalent candidate mappings can revalidate.",
            "Modified plans remain invalid.",
            "Structurally ready only; execution and registration remain unauthorized.",
            "It is not execution authorization.",
            "It is not registration authorization.",
            "No plan persistence.",
            "No binding-result persistence.",
            "No plan ID.",
            "No plan index.",
            "No receipt.",
            "No registration.",
            "No execution.",
            "No commit.",
            "No confirmation input.",
            "No writes.",
            "factual truth correctness",
            "broad rule effectiveness",
            "test_controlled_outcome_truth_registration_backend_plan_identity_is_deterministic_candidate_bound_and_stale_safe",
            "test_controlled_outcome_truth_registration_backend_plan_api_ui_seam_preserves_identity_binding_stale_state_and_non_authorization",
            "test_controlled_registration_backend_plan_ui_renders_explicit_blockers_and_preserves_stale_safe_statuses",
            "test_controlled_registration_backend_plan_api_ui_boundary_audit_and_operator_handoff_preserve_read_only_non_authorization_contract",
            "broad candidate fixture matrix",
            "Backend identity/binding contract: frozen",
            "API wrapper contract: frozen",
            "Desktop plan/binding seam: frozen",
            "Mutation authority: none",
            "Registration authority: none",
            "Phase 14A - Controlled Outcome-Truth Record-Set Registration Execution Planning Gate",
        ):
            self.assertIn(required_phrase, release_text)

        self.test_controlled_outcome_truth_registration_backend_plan_identity_is_deterministic_candidate_bound_and_stale_safe()
        self.test_controlled_outcome_truth_registration_backend_plan_api_ui_seam_preserves_identity_binding_stale_state_and_non_authorization()
        self.test_controlled_registration_backend_plan_ui_renders_explicit_blockers_and_preserves_stale_safe_statuses()
        self.test_controlled_registration_backend_plan_api_ui_boundary_audit_and_operator_handoff_preserve_read_only_non_authorization_contract()

        for function_name in (
            "build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan",
            "format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report",
            "validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding",
            "format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_report",
        ):
            self.assertTrue(callable(getattr(truth, function_name)))
            self.assertTrue(callable(getattr(api, function_name)))

        for signature in (
            inspect.signature(api.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan),
            inspect.signature(api.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report),
            inspect.signature(api.validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding),
            inspect.signature(api.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_report),
        ):
            for forbidden_parameter in (
                "candidate_fingerprint",
                "planning_gate_fingerprint",
                "backend_plan_fingerprint",
                "identity_deterministic",
                "identity_public_safe",
                "binding_valid",
                "candidate_binding_valid",
                "planning_gate_binding_valid",
                "backend_plan_integrity_valid",
                "stale_candidate_detected",
                "backend_plan_modified_detected",
                "backend_plan_ready_for_future_execution",
                "execution_authorized",
                "registration_authorized",
                "confirmation",
                "confirmation_accepted",
                "confirmation_enforced",
                "automatic_registration_approval_claimed",
                "override",
                "force",
                "repair",
                "migrate",
                "score",
                "ranking",
                "aggregate",
            ):
                self.assertNotIn(forbidden_parameter, signature.parameters)

        viewport_action_source = inspect.getsource(desktop_panel.DesktopRightPanelMixin._run_pdf_viewport_action)
        branch_start = viewport_action_source.index('elif action == "build_deployed_rule_outcome_truth_controlled_registration_backend_plan":')
        branch_end = viewport_action_source.index('elif action == "load_deployed_rule_outcome_truth_result":')
        controlled_branch_source = viewport_action_source[branch_start:branch_end]
        relevant_sources = (
            inspect.getsource(truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan),
            inspect.getsource(truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report),
            inspect.getsource(truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding),
            inspect.getsource(truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_report),
            inspect.getsource(api.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan),
            inspect.getsource(api.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report),
            inspect.getsource(api.validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding),
            inspect.getsource(api.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_report),
            controlled_branch_source,
        )
        for forbidden_call in (
            "register_deployed_rule_outcome_truth_record_set(",
            "build_deployed_rule_outcome_truth_source_plan(",
            "record_deployed_rule_outcome_truth_source_result(",
            "_ensure_dirs(",
            "json.dump(",
            "write_text(",
            "_atomic_write_json(",
        ):
            for source in relevant_sources:
                self.assertNotIn(forbidden_call, source)

        desktop_source = inspect.getsource(desktop_panel)
        self.assertIn('("Build Controlled Registration Backend Plan"', desktop_source)
        self.assertIn('("Validate Backend Plan Binding"', desktop_source)
        self.assertIn('("Copy Controlled Registration Backend Plan Report"', desktop_source)
        self.assertIn('("Copy Backend Plan Binding Report"', desktop_source)
        for forbidden_control in (
            'text="Register"',
            'text="Execute"',
            'text="Commit"',
            'text="Confirm Registration"',
            'text="Authorize Registration"',
            'text="Approve Registration"',
            'text="Auto Register"',
            'text="Force Register"',
            'text="Register From Plan"',
            'text="Register From QA"',
            'text="Edit Fingerprint"',
            'text="Override Fingerprint"',
            'text="Override Identity"',
            'text="Override Readiness"',
            'text="Override Binding"',
            'text="Override Authorization"',
            'text="Manual Score"',
            'text="Aggregate Score"',
            'text="Rank Results"',
        ):
            self.assertNotIn(forbidden_control, desktop_source)

        for pointer_path in (
            "docs/PHASE_13C_CONTROLLED_OUTCOME_TRUTH_REGISTRATION_BACKEND_PLAN_IDENTITY_DETERMINISM_STALE_CANDIDATE_GATE.md",
            "docs/PHASE_13D_CONTROLLED_OUTCOME_TRUTH_REGISTRATION_BACKEND_PLAN_API_UI_SEAM.md",
            "docs/PHASE_13E_CONTROLLED_OUTCOME_TRUTH_REGISTRATION_BACKEND_PLAN_API_UI_BOUNDARY_AUDIT_OPERATOR_HANDOFF.md",
        ):
            doc_text = Path(pointer_path).read_text(encoding="utf-8")
            self.assertIn("Final release packet:", doc_text)
            self.assertIn(
                "docs/PHASE_13F_CONTROLLED_OUTCOME_TRUTH_REGISTRATION_BACKEND_PLAN_API_UI_RELEASE_PACKET.md",
                doc_text,
            )

    def test_controlled_outcome_truth_registration_execution_planning_gate_is_read_only_transactional_advisory_and_non_authoritative(self) -> None:
        self.assertTrue(
            callable(truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_planning_gate)
        )
        self.assertTrue(
            callable(truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_execution_planning_gate_report)
        )

        planning_source = inspect.getsource(
            truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_planning_gate
        )
        report_source = inspect.getsource(
            truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_execution_planning_gate_report
        )

        for forbidden_call in (
            "register_deployed_rule_outcome_truth_record_set(",
            "build_deployed_rule_outcome_truth_source_plan(",
            "record_deployed_rule_outcome_truth_source_result(",
            "_ensure_dirs(",
            "json.dump(",
            "write_text(",
            "_atomic_write_json(",
            "uuid.uuid4",
            "time.time",
            "datetime.now",
            "datetime.utcnow",
            "random.",
            "tempfile",
            "Path.mkdir",
            "os.makedirs",
        ):
            self.assertNotIn(forbidden_call, planning_source)
            self.assertNotIn(forbidden_call, report_source)

        planning_signature = inspect.signature(
            truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_planning_gate
        )
        self.assertEqual(tuple(planning_signature.parameters), ("backend_plan", "candidate_record_set", "root"))
        for forbidden_parameter in (
            "confirmation",
            "transaction_id",
            "idempotency_key",
            "authorization",
            "repair",
            "migrate",
            "score",
            "ranking",
            "aggregate",
        ):
            self.assertNotIn(forbidden_parameter, planning_signature.parameters)

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            valid_root = root / "valid"
            identity = _write_telemetry_snapshot_fixture(valid_root)
            candidate = {
                **identity,
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
            backend_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan(
                deepcopy(candidate),
                root=valid_root,
            )
            candidate_before = deepcopy(candidate)
            backend_plan_before = deepcopy(backend_plan)
            before_valid = sorted(str(path.relative_to(valid_root)) for path in valid_root.rglob("*"))
            planning_gate = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_planning_gate(
                backend_plan,
                candidate,
                root=valid_root,
            )
            planning_report = truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_execution_planning_gate_report(
                backend_plan,
                candidate,
                root=valid_root,
            )
            after_valid = sorted(str(path.relative_to(valid_root)) for path in valid_root.rglob("*"))

            missing_candidate = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_planning_gate(
                backend_plan,
                None,
                root=valid_root,
            )
            malformed_candidate = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_planning_gate(
                backend_plan,
                {"records": "bad"},
                root=valid_root,
            )
            missing_backend_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_planning_gate(
                None,
                candidate,
                root=valid_root,
            )
            malformed_backend_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_planning_gate(
                {"bad": "plan"},
                candidate,
                root=valid_root,
            )

            stale_candidate = deepcopy(candidate)
            stale_candidate["records"][0]["actual_or_adjudicated_outcome"] = "mars_day"
            stale_gate = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_planning_gate(
                backend_plan,
                stale_candidate,
                root=valid_root,
            )

            modified_backend_plan = deepcopy(backend_plan)
            modified_backend_plan["backend_plan_fingerprint"] = "sha256:" + ("0" * 64)
            modified_gate = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_planning_gate(
                modified_backend_plan,
                candidate,
                root=valid_root,
            )

            planning_mismatch_backend_plan = deepcopy(backend_plan)
            planning_mismatch_backend_plan["planning_gate_fingerprint"] = "sha256:" + ("1" * 64)
            planning_mismatch_gate = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_planning_gate(
                planning_mismatch_backend_plan,
                candidate,
                root=valid_root,
            )

            structurally_unready_backend_plan = deepcopy(backend_plan)
            structurally_unready_backend_plan["backend_plan_ready_for_future_execution"] = False
            structurally_unready_backend_plan["backend_plan_fingerprint"] = truth._backend_plan_fingerprint(
                structurally_unready_backend_plan
            )
            structural_gate = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_planning_gate(
                structurally_unready_backend_plan,
                candidate,
                root=valid_root,
            )

            original_register = truth.register_deployed_rule_outcome_truth_record_set
            original_loader = truth.load_deployed_rule_outcome_truth_record_set
            original_post_qa = truth.build_deployed_rule_outcome_truth_record_set_qa_gate
            original_pipeline_qa = truth.build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate
            try:
                truth.register_deployed_rule_outcome_truth_record_set = None
                truth.load_deployed_rule_outcome_truth_record_set = None
                truth.build_deployed_rule_outcome_truth_record_set_qa_gate = None
                truth.build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate = None
                unavailable_gate = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_planning_gate(
                    backend_plan,
                    candidate,
                    root=valid_root,
                )
            finally:
                truth.register_deployed_rule_outcome_truth_record_set = original_register
                truth.load_deployed_rule_outcome_truth_record_set = original_loader
                truth.build_deployed_rule_outcome_truth_record_set_qa_gate = original_post_qa
                truth.build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate = original_pipeline_qa

        self.assertEqual(candidate, candidate_before)
        self.assertEqual(backend_plan, backend_plan_before)
        self.assertEqual(before_valid, after_valid)

        self.assertEqual(planning_gate["status"], "planning_ready")
        self.assertTrue(planning_gate["binding_valid"])
        self.assertTrue(planning_gate["candidate_binding_valid"])
        self.assertTrue(planning_gate["planning_gate_binding_valid"])
        self.assertTrue(planning_gate["backend_plan_integrity_valid"])
        self.assertTrue(planning_gate["ready_to_design_future_execution_contract"])
        self.assertFalse(planning_gate["future_execution_contract_implemented"])
        self.assertFalse(planning_gate["transaction_implemented"])
        self.assertFalse(planning_gate["registration_execution_implemented"])
        self.assertFalse(planning_gate["execution_authorized"])
        self.assertFalse(planning_gate["registration_authorized"])
        self.assertFalse(planning_gate["registration_performed"])
        self.assertFalse(planning_gate["record_set_written"])
        self.assertFalse(planning_gate["records_repaired"])
        self.assertFalse(planning_gate["records_migrated"])
        self.assertFalse(planning_gate["execution_plan_persisted"])
        self.assertFalse(planning_gate["idempotency_record_created"])
        self.assertFalse(planning_gate["transaction_created"])
        self.assertFalse(planning_gate["receipt_created"])
        self.assertEqual(planning_gate["required_future_confirmation"], truth.REGISTER_CONFIRMATION)
        self.assertTrue(planning_gate["required_future_preconditions"])
        self.assertTrue(planning_gate["required_future_transaction_properties"])
        self.assertTrue(planning_gate["required_future_idempotency_contract"])
        self.assertTrue(planning_gate["required_future_pre_write_verifications"])
        self.assertTrue(planning_gate["required_future_write_boundary"])
        self.assertTrue(planning_gate["required_future_post_write_verifications"])
        self.assertTrue(planning_gate["required_future_failure_states"])
        self.assertTrue(planning_gate["required_future_recovery_contract"])
        self.assertTrue(planning_gate["required_future_receipt_contract"])
        self.assertTrue(planning_gate["planned_future_execution_sequence"])
        self.assertEqual(planning_gate["writes_performed"], 0)
        self.assertTrue(planning_gate["prerequisite_surface_status"]["registration_function_available"])
        self.assertTrue(planning_gate["prerequisite_surface_status"]["registration_pipeline_qa_build_available"])
        self.assertTrue(planning_gate["prerequisite_surface_status"]["post_registration_loader_available"])
        self.assertTrue(planning_gate["prerequisite_surface_status"]["post_registration_qa_build_available"])
        self.assertTrue(planning_gate["prerequisite_surface_status"]["structural_backend_plan_ready"])

        self.assertEqual(missing_candidate["status"], "missing")
        self.assertIn("candidate_record_set_required", missing_candidate["blockers"])
        self.assertEqual(missing_candidate["writes_performed"], 0)

        self.assertEqual(malformed_candidate["status"], "malformed")
        self.assertIn("candidate_record_set_malformed", malformed_candidate["blockers"])
        self.assertEqual(malformed_candidate["writes_performed"], 0)

        self.assertEqual(missing_backend_plan["status"], "missing")
        self.assertIn("backend_plan_required", missing_backend_plan["blockers"])

        self.assertEqual(malformed_backend_plan["status"], "malformed")
        self.assertIn("backend_plan_malformed", malformed_backend_plan["blockers"])

        self.assertEqual(stale_gate["status"], "stale")
        self.assertIn("backend_plan_candidate_fingerprint_mismatch", stale_gate["blockers"])
        self.assertTrue(stale_gate["stale_candidate_detected"])

        self.assertEqual(modified_gate["status"], "modified")
        self.assertIn("backend_plan_fingerprint_mismatch", modified_gate["blockers"])
        self.assertTrue(modified_gate["backend_plan_modified_detected"])

        self.assertEqual(planning_mismatch_gate["status"], "modified")
        self.assertIn("backend_plan_planning_gate_fingerprint_mismatch", planning_mismatch_gate["blockers"])

        self.assertEqual(structural_gate["status"], "blocked")
        self.assertIn("backend_plan_structural_readiness_required", structural_gate["blockers"])

        self.assertEqual(unavailable_gate["status"], "blocked")
        self.assertIn("registration_function_unavailable", unavailable_gate["blockers"])
        self.assertIn("post_registration_loader_unavailable", unavailable_gate["blockers"])
        self.assertIn("post_registration_qa_build_unavailable", unavailable_gate["blockers"])
        self.assertIn("registration_pipeline_qa_build_unavailable", unavailable_gate["blockers"])

        report_lower = planning_report.lower()
        self.assertIn("controlled outcome-truth record-set registration execution planning gate", report_lower)
        self.assertIn("required future confirmation: register_outcome_truth_record_set", report_lower)
        self.assertIn("phase 14a does not execute registration.", report_lower)
        self.assertIn("phase 14a does not call the registration function.", report_lower)
        self.assertIn("phase 14a does not create a transaction, idempotency record, execution plan, or receipt.", report_lower)
        self.assertIn("phase 14a does not accept or enforce confirmation.", report_lower)
        self.assertIn("structural readiness and valid binding are not execution authorization.", report_lower)
        self.assertIn("structural readiness and valid binding are not registration authorization.", report_lower)
        self.assertIn("the future confirmation phrase is advisory only in this phase.", report_lower)
        self.assertIn("ambiguous future write outcomes must block automatic retry.", report_lower)
        self.assertIn("post-write verification failure must not be reported as clean success.", report_lower)
        self.assertIn("writes performed: 0", report_lower)
        self.assertNotIn('"expected_outcome"', report_lower)
        self.assertNotIn("c:\\users\\", report_lower)
        self.assertNotIn("/users/", report_lower)
        self.assertNotIn("/home/", report_lower)
        self.assertNotIn("traceback", report_lower)
        self.assertNotIn("{", planning_report)

        api_source = inspect.getsource(api)
        desktop_source = inspect.getsource(desktop_panel)
        self.assertNotIn(
            "build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_planning_gate",
            api_source,
        )
        self.assertNotIn(
            "format_deployed_rule_outcome_truth_record_set_controlled_registration_execution_planning_gate_report",
            api_source,
        )
        self.assertNotIn("Execution Planning Gate", desktop_source)
        self.assertNotIn("Controlled Registration Execution", desktop_source)

        doc_text = Path(
            "docs/PHASE_14A_CONTROLLED_OUTCOME_TRUTH_RECORD_SET_REGISTRATION_EXECUTION_PLANNING_GATE.md"
        ).read_text(encoding="utf-8")
        for required_phrase in (
            "Phase 14A defines planning requirements for a future transactional registration execution workflow.",
            "Phase 14A does not execute registration.",
            "Phase 14A does not call the registration function.",
            "Phase 14A does not create a transaction, idempotency record, execution plan, or receipt.",
            "Phase 14A does not accept or enforce confirmation.",
            "Structural readiness and valid binding are not execution authorization.",
            "Structural readiness and valid binding are not registration authorization.",
            "The future confirmation phrase is advisory only in this phase.",
            "Ambiguous future write outcomes must block automatic retry.",
            "Post-write verification failure must not be reported as clean success.",
            "A valid fingerprint or binding does not prove factual correctness of outcome-truth records.",
            "Phase 14B - Controlled Outcome-Truth Registration Transaction Plan and Dry-Run Contract",
        ):
            self.assertIn(required_phrase, doc_text)

    def test_controlled_outcome_truth_registration_transaction_plan_and_dry_run_are_deterministic_read_only_and_non_authoritative(self) -> None:
        self.assertTrue(
            callable(truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan)
        )
        self.assertTrue(
            callable(truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_report)
        )
        self.assertTrue(
            callable(truth.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run)
        )
        self.assertTrue(
            callable(truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run_report)
        )

        plan_source = inspect.getsource(
            truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan
        )
        plan_report_source = inspect.getsource(
            truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_report
        )
        dry_run_source = inspect.getsource(
            truth.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run
        )
        dry_run_report_source = inspect.getsource(
            truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run_report
        )
        for source in (plan_source, plan_report_source, dry_run_source, dry_run_report_source):
            for forbidden_call in (
                "register_deployed_rule_outcome_truth_record_set(",
                "build_deployed_rule_outcome_truth_source_plan(",
                "record_deployed_rule_outcome_truth_source_result(",
                "_ensure_dirs(",
                "json.dump(",
                "write_text(",
                "_atomic_write_json(",
                "uuid.uuid4",
                "random.",
                "time.time",
                "datetime.now",
                "datetime.utcnow",
                "tempfile",
                "Path.mkdir",
                "os.makedirs",
                "hash(",
            ):
                self.assertNotIn(forbidden_call, source)

        self.assertIn(
            "build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_planning_gate(",
            plan_source,
        )
        self.assertIn(
            "validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(",
            dry_run_source,
        )
        target_state_helper_source = inspect.getsource(truth._inspect_controlled_registration_target_state)
        self.assertIn("load_deployed_rule_outcome_truth_record_set(", target_state_helper_source)

        plan_signature = inspect.signature(
            truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan
        )
        self.assertEqual(tuple(plan_signature.parameters), ("backend_plan", "candidate_record_set", "root"))
        dry_run_signature = inspect.signature(
            truth.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run
        )
        self.assertEqual(
            tuple(dry_run_signature.parameters),
            ("transaction_plan", "backend_plan", "candidate_record_set", "root"),
        )
        for signature in (plan_signature, dry_run_signature):
            for forbidden_parameter in (
                "confirmation",
                "confirmation_token",
                "confirmation_phrase",
                "transaction_id",
                "idempotency_key",
                "authoritative_idempotency_key",
                "receipt_id",
                "execution_authorized",
                "registration_authorized",
                "registration_performed",
                "execute",
                "commit",
                "force",
                "override",
                "repair",
                "migrate",
                "score",
                "ranking",
                "aggregate",
            ):
                self.assertNotIn(forbidden_parameter, signature.parameters)

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            valid_root = root / "valid"
            identity = _write_telemetry_snapshot_fixture(valid_root)
            candidate = {
                **identity,
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
            backend_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan(
                deepcopy(candidate),
                root=valid_root,
            )
            candidate_before = deepcopy(candidate)
            backend_plan_before = deepcopy(backend_plan)
            before_valid = sorted(str(path.relative_to(valid_root)) for path in valid_root.rglob("*"))

            plan_one = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan(
                backend_plan,
                candidate,
                root=valid_root,
            )
            plan_two = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan(
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )
            reordered_candidate = {
                "records": deepcopy(candidate["records"]),
                "source_authority_class": candidate["source_authority_class"],
                "source_type": candidate["source_type"],
                "source_id": candidate["source_id"],
                "observation_window_end": candidate["observation_window_end"],
                "observation_window_start": candidate["observation_window_start"],
                "telemetry_snapshot_id": candidate["telemetry_snapshot_id"],
                "deployed_rule_id": candidate["deployed_rule_id"],
                "production_target_id": candidate["production_target_id"],
                "production_deployment_result_id": candidate["production_deployment_result_id"],
                "canonical_rule_id": candidate["canonical_rule_id"],
            }
            reordered_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan(
                backend_plan,
                reordered_candidate,
                root=valid_root,
            )
            plan_report = truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_report(
                backend_plan,
                candidate,
                root=valid_root,
            )
            dry_run = truth.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run(
                plan_one,
                backend_plan,
                candidate,
                root=valid_root,
            )
            dry_run_report = truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run_report(
                plan_one,
                backend_plan,
                candidate,
                root=valid_root,
            )

            stale_candidate = deepcopy(candidate)
            stale_candidate["records"][0]["actual_or_adjudicated_outcome"] = "mars_day"
            stale_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan(
                backend_plan,
                stale_candidate,
                root=valid_root,
            )

            modified_backend_plan = deepcopy(backend_plan)
            modified_backend_plan["backend_plan_fingerprint"] = "sha256:" + ("0" * 64)
            modified_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan(
                modified_backend_plan,
                candidate,
                root=valid_root,
            )

            planning_mismatch_backend_plan = deepcopy(backend_plan)
            planning_mismatch_backend_plan["planning_gate_fingerprint"] = "sha256:" + ("1" * 64)
            planning_mismatch_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan(
                planning_mismatch_backend_plan,
                candidate,
                root=valid_root,
            )

            structurally_unready_backend_plan = deepcopy(backend_plan)
            structurally_unready_backend_plan["backend_plan_ready_for_future_execution"] = False
            structurally_unready_backend_plan["backend_plan_fingerprint"] = truth._backend_plan_fingerprint(
                structurally_unready_backend_plan
            )
            structural_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan(
                structurally_unready_backend_plan,
                candidate,
                root=valid_root,
            )

            original_target_builder = truth._build_controlled_registration_transaction_target_identity
            try:
                def _missing_target_identity(*args, **kwargs):
                    return {
                        "status": "missing",
                        "target_identity": {},
                        "target_identity_fingerprint": None,
                        "record_set_fingerprint_preview": None,
                        "blockers": ["transaction_target_identity_missing"],
                        "warnings": [],
                    }

                truth._build_controlled_registration_transaction_target_identity = _missing_target_identity
                missing_target_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan(
                    backend_plan,
                    candidate,
                    root=valid_root,
                )
            finally:
                truth._build_controlled_registration_transaction_target_identity = original_target_builder

            try:
                def _ambiguous_target_identity(*args, **kwargs):
                    return {
                        "status": "blocked",
                        "target_identity": {},
                        "target_identity_fingerprint": None,
                        "record_set_fingerprint_preview": None,
                        "blockers": ["transaction_target_identity_ambiguous"],
                        "warnings": [],
                    }

                truth._build_controlled_registration_transaction_target_identity = _ambiguous_target_identity
                ambiguous_target_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan(
                    backend_plan,
                    candidate,
                    root=valid_root,
                )
            finally:
                truth._build_controlled_registration_transaction_target_identity = original_target_builder

            changed_target_candidate = deepcopy(candidate)
            changed_target_candidate["source_id"] = "source-2"
            changed_target_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan(
                backend_plan,
                changed_target_candidate,
                root=valid_root,
            )

            mutated_transaction_plan = deepcopy(plan_one)
            mutated_transaction_plan["transaction_plan_fingerprint"] = "sha256:" + ("2" * 64)
            dry_run_modified_plan = truth.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run(
                mutated_transaction_plan,
                backend_plan,
                candidate,
                root=valid_root,
            )

            dry_run_stale_candidate = truth.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run(
                plan_one,
                backend_plan,
                stale_candidate,
                root=valid_root,
            )

            dry_run_modified_backend_plan = truth.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run(
                plan_one,
                modified_backend_plan,
                candidate,
                root=valid_root,
            )

            original_loader = truth.load_deployed_rule_outcome_truth_record_set
            try:
                def _conflicting_loader(*args, **kwargs):
                    return {
                        "status": "loaded",
                        "outcome_truth_record_set": {"record_set_fingerprint": "sha256:" + ("f" * 64)},
                        "outcome_truth_records": [],
                        "warnings": [],
                        "blockers": [],
                    }

                truth.load_deployed_rule_outcome_truth_record_set = _conflicting_loader
                dry_run_target_conflict = truth.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run(
                    plan_one,
                    backend_plan,
                    candidate,
                    root=valid_root,
                )

                def _unknown_loader(*args, **kwargs):
                    return {"status": "corrupt", "warnings": [], "blockers": ["target_state_unknown"]}

                truth.load_deployed_rule_outcome_truth_record_set = _unknown_loader
                dry_run_unknown_state = truth.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run(
                    plan_one,
                    backend_plan,
                    candidate,
                    root=valid_root,
                )
            finally:
                truth.load_deployed_rule_outcome_truth_record_set = original_loader

            after_valid = sorted(str(path.relative_to(valid_root)) for path in valid_root.rglob("*"))

        self.assertEqual(candidate, candidate_before)
        self.assertEqual(backend_plan, backend_plan_before)
        self.assertEqual(before_valid, after_valid)

        self.assertEqual(plan_one["status"], "transaction_plan_ready")
        self.assertTrue(plan_one["transaction_plan_ready"])
        self.assertTrue(plan_one["dry_run_eligible"])
        self.assertEqual(plan_one["planned_write_function"], "register_deployed_rule_outcome_truth_record_set")
        self.assertEqual(plan_one["planned_write_count"], 1)
        self.assertEqual(plan_one["writes_performed"], 0)
        self.assertFalse(plan_one["transaction_plan_persisted"])
        self.assertFalse(plan_one["transaction_created"])
        self.assertFalse(plan_one["transaction_id_created"])
        self.assertFalse(plan_one["receipt_created"])
        self.assertEqual(plan_one["required_future_confirmation"], truth.REGISTER_CONFIRMATION)
        self.assertFalse(plan_one["confirmation_accepted_in_this_phase"])
        self.assertFalse(plan_one["confirmation_enforced_in_this_phase"])
        self.assertFalse(plan_one["execution_authorized"])
        self.assertFalse(plan_one["registration_authorized"])
        self.assertTrue(plan_one["target_identity"])
        self.assertTrue(plan_one["target_identity_fingerprint"])
        self.assertTrue(plan_one["transaction_plan_fingerprint"])
        self.assertTrue(plan_one["idempotency_key_preview"])
        self.assertFalse(plan_one["idempotency_key_preview_authoritative"])
        self.assertFalse(plan_one["idempotency_key_preview_persisted"])
        self.assertFalse(plan_one["idempotency_enforced"])
        self.assertTrue(plan_one["planned_pre_write_verifications"])
        self.assertTrue(plan_one["planned_post_write_verifications"])
        self.assertTrue(plan_one["planned_failure_states"])
        self.assertTrue(plan_one["planned_recovery_requirements"])
        self.assertTrue(plan_one["planned_receipt_fields"])
        self.assertTrue(plan_one["planned_execution_sequence"])

        self.assertEqual(plan_one["target_identity_fingerprint"], plan_two["target_identity_fingerprint"])
        self.assertEqual(plan_one["transaction_plan_fingerprint"], plan_two["transaction_plan_fingerprint"])
        self.assertEqual(plan_one["idempotency_key_preview"], plan_two["idempotency_key_preview"])
        self.assertEqual(plan_one["target_identity_fingerprint"], reordered_plan["target_identity_fingerprint"])
        self.assertEqual(plan_one["transaction_plan_fingerprint"], reordered_plan["transaction_plan_fingerprint"])
        self.assertNotEqual(plan_one["transaction_plan_fingerprint"], changed_target_plan["transaction_plan_fingerprint"])

        self.assertEqual(missing_target_plan["status"], "blocked")
        self.assertIn("transaction_target_identity_missing", missing_target_plan["blockers"])
        self.assertEqual(ambiguous_target_plan["status"], "blocked")
        self.assertIn("transaction_target_identity_ambiguous", ambiguous_target_plan["blockers"])

        self.assertEqual(stale_plan["status"], "stale")
        self.assertIn("backend_plan_candidate_fingerprint_mismatch", stale_plan["blockers"])
        self.assertEqual(modified_plan["status"], "modified")
        self.assertIn("backend_plan_fingerprint_mismatch", modified_plan["blockers"])
        self.assertEqual(planning_mismatch_plan["status"], "modified")
        self.assertIn("backend_plan_planning_gate_fingerprint_mismatch", planning_mismatch_plan["blockers"])
        self.assertEqual(structural_plan["status"], "blocked")
        self.assertIn("backend_plan_structural_readiness_required", structural_plan["blockers"])

        self.assertEqual(dry_run["status"], "dry_run_passed")
        self.assertTrue(dry_run["dry_run"])
        self.assertTrue(dry_run["dry_run_passed"])
        self.assertTrue(dry_run["transaction_plan_fingerprint_valid"])
        self.assertTrue(dry_run["target_identity_fingerprint_valid"])
        self.assertTrue(dry_run["idempotency_preview_valid"])
        self.assertTrue(dry_run["backend_plan_binding_valid"])
        self.assertFalse(dry_run["candidate_stale"])
        self.assertFalse(dry_run["backend_plan_modified"])
        self.assertEqual(dry_run["planned_write_count"], 1)
        self.assertEqual(dry_run["writes_performed"], 0)
        self.assertFalse(dry_run["would_call_registration_function"])
        self.assertFalse(dry_run["confirmation_accepted"])
        self.assertFalse(dry_run["confirmation_enforced"])
        self.assertFalse(dry_run["execution_authorized"])
        self.assertFalse(dry_run["registration_authorized"])

        self.assertEqual(dry_run_modified_plan["status"], "modified_transaction_plan")
        self.assertIn("transaction_plan_fingerprint_mismatch", dry_run_modified_plan["blockers"])
        self.assertEqual(dry_run_stale_candidate["status"], "stale_candidate")
        self.assertTrue(dry_run_stale_candidate["candidate_stale"])
        self.assertEqual(dry_run_modified_backend_plan["status"], "modified_backend_plan")
        self.assertTrue(dry_run_modified_backend_plan["backend_plan_modified"])
        self.assertEqual(dry_run_target_conflict["status"], "blocked")
        self.assertTrue(dry_run_target_conflict["target_conflict_detected"])
        self.assertEqual(dry_run_target_conflict["target_state"], "target_present_conflicting")
        self.assertEqual(dry_run_unknown_state["status"], "stale_target")
        self.assertEqual(dry_run_unknown_state["target_state"], "target_state_unknown")
        self.assertIn("stale_target_detected", dry_run_unknown_state["blockers"])

        plan_report_lower = plan_report.lower()
        dry_run_report_lower = dry_run_report.lower()
        for report_lower in (plan_report_lower, dry_run_report_lower):
            self.assertNotIn('"expected_outcome"', report_lower)
            self.assertNotIn("c:\\users\\", report_lower)
            self.assertNotIn("/users/", report_lower)
            self.assertNotIn("/home/", report_lower)
            self.assertNotIn("traceback", report_lower)
        self.assertNotIn("{", plan_report)
        self.assertNotIn("{", dry_run_report)
        self.assertIn("phase 14b builds a deterministic in-memory transaction-plan preview", plan_report_lower)
        self.assertIn("phase 14b does not call the registration function.", plan_report_lower)
        self.assertIn("the idempotency-key preview is deterministic planning metadata only.", plan_report_lower)
        self.assertIn("a passing dry run does not authorize execution.", plan_report_lower)
        self.assertIn("unknown target state must be reported conservatively.", plan_report_lower)
        self.assertIn("controlled outcome-truth registration transaction dry run", dry_run_report_lower)
        self.assertIn("dry-run passed: true", dry_run_report_lower)
        self.assertIn("writes performed: 0", dry_run_report_lower)

        for forbidden_score in (
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
            "registration_confidence_score",
            "execution_safety_score",
            "transaction_success_probability",
            "aggregate score",
            "rank results",
        ):
            self.assertNotIn(forbidden_score, json.dumps(plan_one, sort_keys=True))
            self.assertNotIn(forbidden_score, json.dumps(dry_run, sort_keys=True))
            self.assertNotIn(forbidden_score, plan_report)
            self.assertNotIn(forbidden_score, dry_run_report)

        doc_text = Path(
            "docs/PHASE_14B_CONTROLLED_OUTCOME_TRUTH_REGISTRATION_TRANSACTION_PLAN_DRY_RUN_CONTRACT.md"
        ).read_text(encoding="utf-8")
        for required_phrase in (
            "Phase 14B builds a deterministic in-memory transaction-plan preview and evaluates it through a read-only dry run.",
            "Phase 14B does not call the registration function.",
            "Phase 14B performs zero writes.",
            "Phase 14B does not create or persist a transaction, idempotency record, execution plan, dry-run result, or receipt.",
            "The idempotency-key preview is deterministic planning metadata only.",
            "It is not authoritative, persisted, reserved, or enforced.",
            "planned_write_count = 1 describes future intent only.",
            "writes_performed = 0 records actual Phase 14B behavior.",
            "A passing dry run does not authorize execution.",
            "A passing dry run does not authorize registration.",
            "A passing dry run does not accept or enforce confirmation.",
            "A passing dry run does not prove the future registration will succeed.",
            "A valid fingerprint proves integrity against the defined canonical representation only.",
            "It does not prove factual correctness of outcome-truth records.",
            "Unknown target state must be reported conservatively.",
            "Ambiguous future write outcomes must block automatic retry.",
            "Post-write verification failure must not be classified as clean success.",
            "Phase 14C - Controlled Registration Transaction-Plan Identity, Target-Binding, and Stale-Target Gate",
        ):
            self.assertIn(required_phrase, doc_text)

    def test_controlled_registration_transaction_plan_identity_target_binding_and_stale_target_gate_is_deterministic_read_only_and_non_authoritative(self) -> None:
        self.assertTrue(
            callable(truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding)
        )
        self.assertTrue(
            callable(
                truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding_report
            )
        )

        binding_source = inspect.getsource(
            truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding
        )
        report_source = inspect.getsource(
            truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding_report
        )
        snapshot_source = inspect.getsource(truth._build_controlled_registration_target_state_snapshot)
        dry_run_source = inspect.getsource(
            truth.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run
        )
        for source in (binding_source, report_source, snapshot_source, dry_run_source):
            for forbidden_call in (
                "register_deployed_rule_outcome_truth_record_set(",
                "build_deployed_rule_outcome_truth_source_plan(",
                "record_deployed_rule_outcome_truth_source_result(",
                "_ensure_dirs(",
                "json.dump(",
                "write_text(",
                "_atomic_write_json(",
                "uuid.uuid4",
                "random.",
                "time.time",
                "datetime.now",
                "datetime.utcnow",
                "tempfile",
                "Path.mkdir",
                "os.makedirs",
                "hash(",
            ):
                self.assertNotIn(forbidden_call, source)
        self.assertIn(
            "validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(",
            dry_run_source,
        )

        binding_signature = inspect.signature(
            truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding
        )
        report_signature = inspect.signature(
            truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding_report
        )
        self.assertEqual(
            tuple(binding_signature.parameters),
            ("transaction_plan", "backend_plan", "candidate_record_set", "root"),
        )
        self.assertEqual(
            tuple(report_signature.parameters),
            ("transaction_plan", "backend_plan", "candidate_record_set", "root"),
        )
        for signature in (binding_signature, report_signature):
            for forbidden_parameter in (
                "confirmation",
                "confirmation_token",
                "confirmation_phrase",
                "transaction_id",
                "idempotency_key",
                "authoritative_idempotency_key",
                "target_identity",
                "target_identity_fingerprint",
                "target_state",
                "target_state_snapshot",
                "target_state_snapshot_fingerprint",
                "execution_authorized",
                "registration_authorized",
                "execute",
                "commit",
                "force",
                "override",
                "repair",
                "migrate",
                "score",
                "ranking",
                "aggregate",
            ):
                self.assertNotIn(forbidden_parameter, signature.parameters)

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            valid_root = root / "valid"
            identity = _write_telemetry_snapshot_fixture(valid_root)
            candidate = {
                **identity,
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
            backend_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan(
                deepcopy(candidate),
                root=valid_root,
            )
            plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan(
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )
            candidate_before = deepcopy(candidate)
            backend_plan_before = deepcopy(backend_plan)
            plan_before = deepcopy(plan)
            before_read_only = sorted(str(path.relative_to(valid_root)) for path in valid_root.rglob("*"))

            binding = truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(
                deepcopy(plan),
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )
            binding_report = truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding_report(
                deepcopy(plan),
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )
            dry_run = truth.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run(
                deepcopy(plan),
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )
            after_read_only = sorted(str(path.relative_to(valid_root)) for path in valid_root.rglob("*"))

            reordered_candidate = {
                "records": deepcopy(candidate["records"]),
                "source_authority_class": candidate["source_authority_class"],
                "source_type": candidate["source_type"],
                "source_id": candidate["source_id"],
                "observation_window_end": candidate["observation_window_end"],
                "observation_window_start": candidate["observation_window_start"],
                "telemetry_snapshot_id": candidate["telemetry_snapshot_id"],
                "deployed_rule_id": candidate["deployed_rule_id"],
                "production_target_id": candidate["production_target_id"],
                "production_deployment_result_id": candidate["production_deployment_result_id"],
                "canonical_rule_id": candidate["canonical_rule_id"],
            }
            reordered_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan(
                deepcopy(backend_plan),
                deepcopy(reordered_candidate),
                root=valid_root,
            )

            def _write_registered_target(
                root_path: Path,
                candidate_record_set: dict[str, object],
                *,
                conflicting: bool = False,
            ) -> dict[str, object]:
                validation = truth.validate_deployed_rule_outcome_truth_record_set(
                    str(candidate_record_set["canonical_rule_id"]),
                    str(candidate_record_set["production_deployment_result_id"]),
                    str(candidate_record_set["production_target_id"]),
                    str(candidate_record_set["deployed_rule_id"]),
                    str(candidate_record_set["telemetry_snapshot_id"]),
                    str(candidate_record_set["observation_window_start"]),
                    str(candidate_record_set["observation_window_end"]),
                    source_id=str(candidate_record_set["source_id"]),
                    source_type=str(candidate_record_set["source_type"]),
                    source_authority_class=str(candidate_record_set["source_authority_class"]),
                    records=deepcopy(candidate_record_set["records"]),
                    outcome_truth_record_set_id=str(plan["target_identity"]["record_set_id"]),
                    root=root_path,
                )
                self.assertEqual(validation["status"], "valid")
                set_payload = deepcopy(validation["record_set"])
                if conflicting:
                    set_payload["record_set_fingerprint"] = "sha256:" + ("f" * 64)
                set_path = truth._record_set_path(root_path, str(validation["outcome_truth_record_set_id"]))
                set_path.parent.mkdir(parents=True, exist_ok=True)
                set_path.write_text(json.dumps(set_payload, indent=2, sort_keys=True), encoding="utf-8")
                for record in validation["records"]:
                    record_path = truth._record_path(root_path, str(record["outcome_truth_record_id"]))
                    record_path.parent.mkdir(parents=True, exist_ok=True)
                    record_path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
                return validation

            equivalent_write = _write_registered_target(valid_root, deepcopy(candidate))
            stale_binding = truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(
                deepcopy(plan),
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )
            stale_dry_run = truth.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run(
                deepcopy(plan),
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )

            _write_registered_target(valid_root, deepcopy(candidate), conflicting=True)
            conflict_binding = truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(
                deepcopy(plan),
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )
            conflict_dry_run = truth.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run(
                deepcopy(plan),
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )

            mutated_plan = deepcopy(plan)
            mutated_plan["transaction_plan_fingerprint"] = "sha256:" + ("2" * 64)
            mutated_binding = truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(
                mutated_plan,
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )

            stale_candidate = deepcopy(candidate)
            stale_candidate["records"][0]["actual_or_adjudicated_outcome"] = "mars_day"
            stale_candidate_binding = truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(
                deepcopy(plan),
                deepcopy(backend_plan),
                stale_candidate,
                root=valid_root,
            )

            modified_backend_plan = deepcopy(backend_plan)
            modified_backend_plan["backend_plan_fingerprint"] = "sha256:" + ("0" * 64)
            modified_backend_binding = truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(
                deepcopy(plan),
                modified_backend_plan,
                deepcopy(candidate),
                root=valid_root,
            )

            target_identity_mismatch_plan = deepcopy(plan)
            target_identity_mismatch_plan["target_identity_fingerprint"] = "sha256:" + ("3" * 64)
            target_identity_mismatch_binding = truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(
                target_identity_mismatch_plan,
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )

            idempotency_mismatch_plan = deepcopy(plan)
            idempotency_mismatch_plan["idempotency_key_preview"] = "sha256:" + ("4" * 64)
            idempotency_mismatch_binding = truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(
                idempotency_mismatch_plan,
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )

            original_snapshot_builder = truth._build_controlled_registration_target_state_snapshot
            try:
                call_count = {"value": 0}

                def _unknown_current_snapshot(transaction_plan_mapping, *, root):
                    call_count["value"] += 1
                    if call_count["value"] == 1:
                        return original_snapshot_builder(transaction_plan_mapping, root=root)
                    snapshot = deepcopy(plan["target_state_snapshot"])
                    snapshot["observation_status"] = "target_state_check_unavailable"
                    snapshot["target_state"] = "target_state_unknown"
                    snapshot["read_path_available"] = False
                    snapshot["target_present"] = False
                    snapshot["target_equivalent"] = False
                    snapshot["target_conflicting"] = False
                    snapshot["limitations"] = ["safe target-state visibility may remain unavailable"]
                    snapshot["target_state_snapshot_fingerprint"] = truth._hash_payload(
                        truth._canonicalize_for_identity(
                            {key: snapshot.get(key) for key in sorted(snapshot) if key != "target_state_snapshot_fingerprint"}
                        )
                    )
                    return snapshot

                truth._build_controlled_registration_target_state_snapshot = _unknown_current_snapshot
                unknown_binding = truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(
                    deepcopy(plan),
                    deepcopy(backend_plan),
                    deepcopy(candidate),
                    root=valid_root,
                )
                call_count["value"] = 0
                unknown_dry_run = truth.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run(
                    deepcopy(plan),
                    deepcopy(backend_plan),
                    deepcopy(candidate),
                    root=valid_root,
                )
            finally:
                truth._build_controlled_registration_target_state_snapshot = original_snapshot_builder

        self.assertEqual(candidate, candidate_before)
        self.assertEqual(backend_plan, backend_plan_before)
        self.assertEqual(plan, plan_before)
        self.assertEqual(before_read_only, after_read_only)

        for key in (
            "target_state_at_plan_time",
            "target_state_observation_available",
            "target_state_observation_status",
            "target_state_snapshot",
            "target_state_snapshot_fingerprint",
            "target_state_snapshot_fingerprint_algorithm",
            "target_state_snapshot_deterministic",
            "target_state_snapshot_public_safe",
            "target_state_freshness_proven_at_plan_time",
        ):
            self.assertIn(key, plan)
        self.assertEqual(plan["target_state_snapshot_fingerprint_algorithm"], "sha256")
        self.assertTrue(plan["target_state_snapshot_deterministic"])
        self.assertTrue(plan["target_state_snapshot_public_safe"])
        self.assertFalse(plan["target_state_freshness_proven_at_plan_time"])
        self.assertEqual(plan["target_state_at_plan_time"], "target_absent")
        self.assertEqual(plan["target_state_observation_status"], "observed")
        self.assertTrue(plan["target_state_observation_available"])
        self.assertTrue(plan["target_state_snapshot_fingerprint"])
        self.assertEqual(
            plan["target_state_snapshot"]["target_state_snapshot_fingerprint"],
            plan["target_state_snapshot_fingerprint"],
        )
        self.assertEqual(
            plan["target_state_snapshot"]["target_identity_fingerprint"],
            plan["target_identity_fingerprint"],
        )

        self.assertEqual(plan["target_state_snapshot_fingerprint"], reordered_plan["target_state_snapshot_fingerprint"])
        self.assertEqual(plan["transaction_plan_fingerprint"], reordered_plan["transaction_plan_fingerprint"])

        self.assertEqual(binding["status"], "valid")
        self.assertTrue(binding["transaction_plan_binding_valid"])
        self.assertTrue(binding["transaction_plan_integrity_valid"])
        self.assertTrue(binding["transaction_plan_fingerprint_valid"])
        self.assertTrue(binding["candidate_binding_valid"])
        self.assertTrue(binding["backend_plan_binding_valid"])
        self.assertTrue(binding["planning_gate_binding_valid"])
        self.assertTrue(binding["backend_plan_integrity_valid"])
        self.assertTrue(binding["target_identity_binding_valid"])
        self.assertTrue(binding["target_identity_fingerprint_valid"])
        self.assertTrue(binding["idempotency_preview_valid"])
        self.assertTrue(binding["target_state_observation_available"])
        self.assertTrue(binding["target_state_binding_valid"])
        self.assertEqual(binding["target_state_freshness_status"], "fresh")
        self.assertTrue(binding["target_state_freshness_proven"])
        self.assertFalse(binding["stale_target_detected"])
        self.assertFalse(binding["target_state_changed_detected"])
        self.assertFalse(binding["target_conflict_detected"])
        self.assertFalse(binding["execution_authorized"])
        self.assertFalse(binding["registration_authorized"])
        self.assertFalse(binding["confirmation_accepted"])
        self.assertFalse(binding["confirmation_enforced"])
        self.assertFalse(binding["idempotency_enforced"])
        self.assertFalse(binding["registration_performed"])
        self.assertFalse(binding["record_set_written"])
        self.assertEqual(binding["writes_performed"], 0)
        self.assertEqual(binding["planned_target_state"], "target_absent")
        self.assertEqual(binding["current_target_state"], "target_absent")
        self.assertEqual(dry_run["status"], "dry_run_passed")
        self.assertTrue(dry_run["dry_run_passed"])
        self.assertFalse(dry_run["execution_authorized"])
        self.assertFalse(dry_run["registration_authorized"])
        self.assertFalse(dry_run["would_call_registration_function"])
        self.assertEqual(dry_run["writes_performed"], 0)

        missing_transaction_plan = truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(
            None,
            deepcopy(backend_plan),
            deepcopy(candidate),
            root=valid_root,
        )
        malformed_transaction_plan = truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(
            {"bad": "plan"},
            deepcopy(backend_plan),
            deepcopy(candidate),
            root=valid_root,
        )
        missing_backend_plan = truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(
            deepcopy(plan),
            None,
            deepcopy(candidate),
            root=valid_root,
        )
        malformed_backend_plan = truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(
            deepcopy(plan),
            {"bad": "backend"},
            deepcopy(candidate),
            root=valid_root,
        )
        missing_candidate = truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(
            deepcopy(plan),
            deepcopy(backend_plan),
            None,
            root=valid_root,
        )
        malformed_candidate = truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(
            deepcopy(plan),
            deepcopy(backend_plan),
            {"records": "bad"},
            root=valid_root,
        )

        self.assertEqual(missing_transaction_plan["status"], "missing")
        self.assertIn("transaction_plan_required", missing_transaction_plan["blockers"])
        self.assertEqual(malformed_transaction_plan["status"], "malformed")
        self.assertIn("transaction_plan_malformed", malformed_transaction_plan["blockers"])
        self.assertEqual(missing_backend_plan["status"], "missing")
        self.assertIn("backend_plan_required", missing_backend_plan["blockers"])
        self.assertEqual(malformed_backend_plan["status"], "malformed")
        self.assertIn("backend_plan_malformed", malformed_backend_plan["blockers"])
        self.assertEqual(missing_candidate["status"], "missing")
        self.assertIn("candidate_record_set_required", missing_candidate["blockers"])
        self.assertEqual(malformed_candidate["status"], "malformed")
        self.assertIn("candidate_record_set_malformed", malformed_candidate["blockers"])

        self.assertEqual(stale_candidate_binding["status"], "stale_candidate")
        self.assertTrue(stale_candidate_binding["candidate_stale"])
        self.assertEqual(modified_backend_binding["status"], "modified_backend_plan")
        self.assertTrue(modified_backend_binding["backend_plan_modified"])
        self.assertEqual(mutated_binding["status"], "modified_transaction_plan")
        self.assertTrue(mutated_binding["transaction_plan_modified"])
        self.assertEqual(target_identity_mismatch_binding["status"], "modified_transaction_plan")
        self.assertFalse(target_identity_mismatch_binding["target_identity_fingerprint_valid"])
        self.assertEqual(idempotency_mismatch_binding["status"], "modified_transaction_plan")
        self.assertFalse(idempotency_mismatch_binding["idempotency_preview_valid"])

        self.assertEqual(equivalent_write["outcome_truth_record_set_id"], plan["target_identity"]["record_set_id"])
        self.assertEqual(stale_binding["status"], "stale_target")
        self.assertTrue(stale_binding["stale_target_detected"])
        self.assertTrue(stale_binding["target_state_changed_detected"])
        self.assertFalse(stale_binding["target_state_freshness_proven"])
        self.assertEqual(stale_binding["target_state_freshness_status"], "stale")
        self.assertEqual(stale_binding["current_target_state"], "target_present_equivalent")
        self.assertIn("stale_target_detected", stale_binding["blockers"])
        self.assertIn("rebuilt rather than repaired", stale_binding["recommended_action"].lower())
        self.assertEqual(stale_dry_run["status"], "stale_target")

        self.assertEqual(conflict_binding["status"], "target_conflict")
        self.assertTrue(conflict_binding["target_conflict_detected"])
        self.assertEqual(conflict_binding["current_target_state"], "target_present_conflicting")
        self.assertEqual(conflict_dry_run["status"], "blocked")
        self.assertTrue(conflict_dry_run["target_conflict_detected"])

        self.assertEqual(unknown_binding["status"], "target_state_unknown")
        self.assertFalse(unknown_binding["target_state_observation_available"])
        self.assertFalse(unknown_binding["target_state_freshness_proven"])
        self.assertEqual(unknown_binding["target_state_freshness_status"], "unknown")
        self.assertNotEqual(unknown_binding["current_target_state"], "target_present_equivalent")
        self.assertEqual(unknown_dry_run["status"], "blocked")
        self.assertIn("target_state_unknown", unknown_dry_run["blockers"])

        binding_report_lower = binding_report.lower()
        self.assertIn("phase 14c adds deterministic identity, target binding, and stale-target detection", binding_report_lower)
        self.assertIn("a valid transaction-plan binding does not authorize execution.", binding_report_lower)
        self.assertIn("a valid transaction-plan binding does not authorize registration.", binding_report_lower)
        self.assertIn("it does not prove factual correctness of outcome-truth records.", binding_report_lower)
        self.assertIn("stored transaction-plan fingerprint:", binding_report_lower)
        self.assertIn("current target-state snapshot fingerprint:", binding_report_lower)
        self.assertNotIn('"expected_outcome"', binding_report_lower)
        self.assertNotIn("c:\\users\\", binding_report_lower)
        self.assertNotIn("/users/", binding_report_lower)
        self.assertNotIn("/home/", binding_report_lower)
        self.assertNotIn("traceback", binding_report_lower)
        self.assertNotIn("{", binding_report)

        for forbidden_score in (
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
        ):
            self.assertNotIn(forbidden_score, json.dumps(binding, sort_keys=True))
            self.assertNotIn(forbidden_score, binding_report)

        doc_text = Path(
            "docs/PHASE_14C_CONTROLLED_REGISTRATION_TRANSACTION_PLAN_IDENTITY_TARGET_BINDING_STALE_TARGET_GATE.md"
        ).read_text(encoding="utf-8")
        for required_phrase in (
            "Phase 14C adds deterministic identity, target binding, and stale-target detection to the Phase 14B transaction plan.",
            "Target-state freshness is proven only when a safe non-creating read path is available and the current target-state snapshot matches the snapshot bound into the transaction plan.",
            "Unknown target state must not be described as current.",
            "Lack of detected staleness is not proof of freshness when target observation is unavailable.",
            "A valid transaction-plan binding does not authorize execution.",
            "A valid transaction-plan binding does not authorize registration.",
            "Phase 14C does not call the registration function.",
            "Phase 14C does not accept or enforce confirmation.",
            "Phase 14C does not enforce idempotency.",
            "Phase 14C does not persist target-state snapshots, transaction plans, dry-run results, or receipts.",
            "Stale or modified transaction plans must be rebuilt rather than repaired in place.",
            "A valid fingerprint proves integrity against the defined canonical representation only.",
            "It does not prove factual correctness of outcome-truth records.",
            "Phase 14D - Controlled Registration Transaction-Plan Identity/Binding and Dry-Run API/UI Seam",
        ):
            self.assertIn(required_phrase, doc_text)

    def test_controlled_registration_target_state_observer_distinguishes_unknown_absent_present_and_changed_without_writes(self) -> None:
        observer_source = inspect.getsource(truth._inspect_controlled_registration_target_state)
        snapshot_source = inspect.getsource(truth._build_controlled_registration_target_state_snapshot)
        plan_source = inspect.getsource(
            truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan
        )
        binding_source = inspect.getsource(
            truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding
        )
        dry_run_source = inspect.getsource(
            truth.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run
        )
        self.assertIn("_build_controlled_registration_target_state_snapshot(", plan_source)
        self.assertIn("_build_controlled_registration_target_state_snapshot(", binding_source)
        self.assertIn("_inspect_controlled_registration_target_state(", snapshot_source)
        self.assertIn(
            "validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(",
            dry_run_source,
        )
        for source in (observer_source, snapshot_source, plan_source, binding_source, dry_run_source):
            for forbidden_call in (
                "register_deployed_rule_outcome_truth_record_set(",
                "build_deployed_rule_outcome_truth_source_plan(",
                "record_deployed_rule_outcome_truth_source_result(",
                "_ensure_dirs(",
                "json.dump(",
                "write_text(",
                "_atomic_write_json(",
                "Path.mkdir",
                "os.makedirs",
                "open(",
                "uuid.uuid4",
                "random.",
                "time.time",
                "datetime.now",
                "datetime.utcnow",
                "tempfile",
                "hash(",
            ):
                self.assertNotIn(forbidden_call, source)

        observer_signature = inspect.signature(truth._inspect_controlled_registration_target_state)
        self.assertEqual(tuple(observer_signature.parameters), ("transaction_plan", "root"))
        for forbidden_parameter in (
            "target_state",
            "target_state_snapshot",
            "target_state_snapshot_fingerprint",
            "target_state_observation_status",
            "target_state_observation_available",
            "target_state_freshness_proven",
            "stale_target_detected",
            "target_conflict_detected",
            "target_identity",
            "target_identity_fingerprint",
            "transaction_plan_fingerprint",
            "idempotency_key",
            "execution_authorized",
            "registration_authorized",
            "confirmation",
            "execute",
            "commit",
            "force",
            "override",
            "repair",
            "migrate",
            "score",
            "ranking",
            "aggregate",
        ):
            self.assertNotIn(forbidden_parameter, observer_signature.parameters)

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing_root = root / "missing-root"
            missing_context = {
                "target_identity": {
                    "record_set_id": "deployed_rule_outcome_truth_record_set_missing",
                    "record_set_fingerprint_preview": "sha256:" + ("1" * 64),
                },
                "target_identity_fingerprint": "sha256:" + ("2" * 64),
            }
            missing_before = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
            missing_state_one = truth._inspect_controlled_registration_target_state(
                deepcopy(missing_context),
                root=missing_root,
            )
            missing_snapshot_one = truth._build_controlled_registration_target_state_snapshot(
                deepcopy(missing_context),
                root=missing_root,
            )
            missing_state_two = truth._inspect_controlled_registration_target_state(
                deepcopy(missing_context),
                root=missing_root,
            )
            missing_snapshot_two = truth._build_controlled_registration_target_state_snapshot(
                deepcopy(missing_context),
                root=missing_root,
            )
            missing_after = sorted(str(path.relative_to(root)) for path in root.rglob("*"))

            valid_root = root / "valid"
            identity = _write_telemetry_snapshot_fixture(valid_root)
            candidate = {
                **identity,
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
            backend_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan(
                deepcopy(candidate),
                root=valid_root,
            )
            plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan(
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )
            candidate_before = deepcopy(candidate)
            backend_plan_before = deepcopy(backend_plan)
            plan_before = deepcopy(plan)
            before_absent_production = sorted(str(path.relative_to(valid_root)) for path in valid_root.rglob("*"))

            absent_state_one = truth._inspect_controlled_registration_target_state(
                {"target_identity": deepcopy(plan["target_identity"]), "target_identity_fingerprint": plan["target_identity_fingerprint"]},
                root=valid_root,
            )
            absent_snapshot_one = truth._build_controlled_registration_target_state_snapshot(
                {"target_identity": deepcopy(plan["target_identity"]), "target_identity_fingerprint": plan["target_identity_fingerprint"]},
                root=valid_root,
            )
            absent_state_two = truth._inspect_controlled_registration_target_state(
                {"target_identity": deepcopy(plan["target_identity"]), "target_identity_fingerprint": plan["target_identity_fingerprint"]},
                root=valid_root,
            )
            absent_snapshot_two = truth._build_controlled_registration_target_state_snapshot(
                {"target_identity": deepcopy(plan["target_identity"]), "target_identity_fingerprint": plan["target_identity_fingerprint"]},
                root=valid_root,
            )
            after_absent_production = sorted(str(path.relative_to(valid_root)) for path in valid_root.rglob("*"))

            malformed_root = root / "malformed"
            malformed_identity = _write_telemetry_snapshot_fixture(malformed_root)
            malformed_candidate = {
                **malformed_identity,
                "source_id": "source-1",
                "source_type": "external_authoritative_result",
                "source_authority_class": "authoritative",
                "records": deepcopy(candidate["records"]),
            }
            malformed_backend_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan(
                deepcopy(malformed_candidate),
                root=malformed_root,
            )
            malformed_plan_seed = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan(
                deepcopy(malformed_backend_plan),
                deepcopy(malformed_candidate),
                root=malformed_root,
            )
            malformed_path = truth._record_set_path(malformed_root, str(malformed_plan_seed["target_identity"]["record_set_id"]))
            malformed_path.parent.mkdir(parents=True, exist_ok=True)
            malformed_path.write_text("{not-json", encoding="utf-8")
            malformed_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan(
                deepcopy(malformed_backend_plan),
                deepcopy(malformed_candidate),
                root=malformed_root,
            )
            malformed_binding = truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(
                deepcopy(malformed_plan),
                deepcopy(malformed_backend_plan),
                deepcopy(malformed_candidate),
                root=malformed_root,
            )
            malformed_dry_run = truth.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run(
                deepcopy(malformed_plan),
                deepcopy(malformed_backend_plan),
                deepcopy(malformed_candidate),
                root=malformed_root,
            )

            def _write_registered_target(
                root_path: Path,
                candidate_record_set: dict[str, object],
                *,
                conflicting: bool = False,
            ) -> dict[str, object]:
                validation = truth.validate_deployed_rule_outcome_truth_record_set(
                    str(candidate_record_set["canonical_rule_id"]),
                    str(candidate_record_set["production_deployment_result_id"]),
                    str(candidate_record_set["production_target_id"]),
                    str(candidate_record_set["deployed_rule_id"]),
                    str(candidate_record_set["telemetry_snapshot_id"]),
                    str(candidate_record_set["observation_window_start"]),
                    str(candidate_record_set["observation_window_end"]),
                    source_id=str(candidate_record_set["source_id"]),
                    source_type=str(candidate_record_set["source_type"]),
                    source_authority_class=str(candidate_record_set["source_authority_class"]),
                    records=deepcopy(candidate_record_set["records"]),
                    outcome_truth_record_set_id=str(plan["target_identity"]["record_set_id"]),
                    root=root_path,
                )
                self.assertEqual(validation["status"], "valid")
                set_payload = deepcopy(validation["record_set"])
                if conflicting:
                    set_payload["record_set_fingerprint"] = "sha256:" + ("f" * 64)
                set_path = truth._record_set_path(root_path, str(validation["outcome_truth_record_set_id"]))
                set_path.parent.mkdir(parents=True, exist_ok=True)
                set_path.write_text(json.dumps(set_payload, indent=2, sort_keys=True), encoding="utf-8")
                for record in validation["records"]:
                    record_path = truth._record_path(root_path, str(record["outcome_truth_record_id"]))
                    record_path.parent.mkdir(parents=True, exist_ok=True)
                    record_path.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
                return validation

            equivalent_write = _write_registered_target(valid_root, deepcopy(candidate))
            before_equivalent_production = sorted(str(path.relative_to(valid_root)) for path in valid_root.rglob("*"))
            equivalent_state = truth._inspect_controlled_registration_target_state(
                {"target_identity": deepcopy(plan["target_identity"]), "target_identity_fingerprint": plan["target_identity_fingerprint"]},
                root=valid_root,
            )
            equivalent_snapshot = truth._build_controlled_registration_target_state_snapshot(
                {"target_identity": deepcopy(plan["target_identity"]), "target_identity_fingerprint": plan["target_identity_fingerprint"]},
                root=valid_root,
            )
            stale_binding = truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(
                deepcopy(plan),
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )
            stale_dry_run = truth.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run(
                deepcopy(plan),
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )
            after_equivalent_production = sorted(str(path.relative_to(valid_root)) for path in valid_root.rglob("*"))

            _write_registered_target(valid_root, deepcopy(candidate), conflicting=True)
            before_conflict_production = sorted(str(path.relative_to(valid_root)) for path in valid_root.rglob("*"))
            conflict_state = truth._inspect_controlled_registration_target_state(
                {"target_identity": deepcopy(plan["target_identity"]), "target_identity_fingerprint": plan["target_identity_fingerprint"]},
                root=valid_root,
            )
            conflict_snapshot = truth._build_controlled_registration_target_state_snapshot(
                {"target_identity": deepcopy(plan["target_identity"]), "target_identity_fingerprint": plan["target_identity_fingerprint"]},
                root=valid_root,
            )
            conflict_binding = truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(
                deepcopy(plan),
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )
            conflict_dry_run = truth.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run(
                deepcopy(plan),
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )
            binding_report = truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding_report(
                deepcopy(plan),
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )
            after_conflict_production = sorted(str(path.relative_to(valid_root)) for path in valid_root.rglob("*"))

        self.assertEqual(missing_before, missing_after)
        self.assertEqual(missing_state_one["observation_status"], "root_unavailable")
        self.assertEqual(missing_state_one["observation_basis"], "root_unavailable")
        self.assertEqual(missing_state_one["target_state"], "target_state_unknown")
        self.assertFalse(missing_state_one["read_path_available"])
        self.assertNotEqual(missing_state_one["target_state"], "target_absent")
        self.assertEqual(missing_snapshot_one["target_state_snapshot_fingerprint"], missing_snapshot_two["target_state_snapshot_fingerprint"])
        self.assertEqual(missing_snapshot_one["observation_basis"], "root_unavailable")

        self.assertEqual(candidate, candidate_before)
        self.assertEqual(backend_plan, backend_plan_before)
        self.assertEqual(plan, plan_before)
        self.assertEqual(before_absent_production, after_absent_production)
        self.assertEqual(before_equivalent_production, after_equivalent_production)
        self.assertEqual(before_conflict_production, after_conflict_production)

        self.assertEqual(absent_state_one["observation_status"], "observed")
        self.assertEqual(absent_state_one["observation_basis"], "safe_direct_target_file_read")
        self.assertEqual(absent_state_one["target_state"], "target_absent")
        self.assertTrue(absent_state_one["read_path_available"])
        self.assertFalse(absent_state_one["target_present"])
        self.assertEqual(absent_snapshot_one["observation_basis"], "safe_direct_target_file_read")
        self.assertEqual(absent_snapshot_one["target_state_snapshot_fingerprint"], absent_snapshot_two["target_state_snapshot_fingerprint"])
        self.assertEqual(absent_state_one, absent_state_two)

        self.assertEqual(malformed_plan["target_state_at_plan_time"], "target_state_unknown")
        self.assertEqual(malformed_plan["target_state_observation_basis"], "target_malformed")
        self.assertEqual(malformed_binding["status"], "target_state_unknown")
        self.assertFalse(malformed_binding["target_state_freshness_proven"])
        self.assertEqual(malformed_binding["target_state_freshness_status"], "unknown")
        self.assertFalse(malformed_binding["target_state_binding_valid"])
        self.assertEqual(malformed_dry_run["status"], "blocked")
        self.assertEqual(malformed_dry_run["target_state"], "target_state_unknown")

        self.assertEqual(equivalent_write["outcome_truth_record_set_id"], plan["target_identity"]["record_set_id"])
        self.assertEqual(equivalent_state["observation_status"], "observed")
        self.assertEqual(equivalent_state["observation_basis"], "safe_existing_root_target_lookup")
        self.assertEqual(equivalent_state["target_state"], "target_present_equivalent")
        self.assertTrue(equivalent_state["target_equivalent"])
        self.assertNotEqual(absent_snapshot_one["target_state_snapshot_fingerprint"], equivalent_snapshot["target_state_snapshot_fingerprint"])
        self.assertEqual(stale_binding["status"], "stale_target")
        self.assertTrue(stale_binding["stale_target_detected"])
        self.assertTrue(stale_binding["target_state_changed_detected"])
        self.assertFalse(stale_binding["target_state_freshness_proven"])
        self.assertIn("rebuilt rather than repaired", stale_binding["recommended_action"].lower())
        self.assertEqual(stale_dry_run["status"], "stale_target")

        self.assertEqual(conflict_state["observation_basis"], "safe_existing_root_target_lookup")
        self.assertEqual(conflict_state["target_state"], "target_present_conflicting")
        self.assertTrue(conflict_state["target_conflicting"])
        self.assertNotEqual(equivalent_snapshot["target_state_snapshot_fingerprint"], conflict_snapshot["target_state_snapshot_fingerprint"])
        self.assertEqual(conflict_binding["status"], "target_conflict")
        self.assertTrue(conflict_binding["target_conflict_detected"])
        self.assertFalse(conflict_binding["transaction_plan_binding_valid"])
        self.assertEqual(conflict_dry_run["status"], "blocked")
        self.assertTrue(conflict_dry_run["target_conflict_detected"])

        binding_report_lower = binding_report.lower()
        self.assertIn("planned target-state observation basis:", binding_report_lower)
        self.assertIn("current target-state observation basis:", binding_report_lower)
        self.assertIn("limitations:", binding_report_lower)
        self.assertNotIn('"expected_outcome"', binding_report_lower)
        self.assertNotIn("c:\\users\\", binding_report_lower)
        self.assertNotIn("/users/", binding_report_lower)
        self.assertNotIn("/home/", binding_report_lower)
        self.assertNotIn(str(valid_root).lower(), binding_report_lower)
        self.assertNotIn(str(malformed_root).lower(), binding_report_lower)
        self.assertNotIn("traceback", binding_report_lower)

        for payload_text in (
            json.dumps(absent_snapshot_one, sort_keys=True),
            json.dumps(missing_snapshot_one, sort_keys=True),
            json.dumps(conflict_binding, sort_keys=True),
        ):
            self.assertNotIn(str(valid_root), payload_text)
            self.assertNotIn(str(malformed_root), payload_text)
            self.assertNotIn("effectiveness_score", payload_text)
            self.assertNotIn("correctness_score", payload_text)
            self.assertNotIn("success_rate", payload_text)
            self.assertNotIn("failure_rate", payload_text)

        doc_text = Path(
            "docs/PHASE_14C_1_NARROW_TRANSACTION_PLAN_TARGET_STATE_OBSERVATION_BINDING_FOLLOW_UP.md"
        ).read_text(encoding="utf-8")
        for required_phrase in (
            "Phase 14C.1 hardens the read-only target-state observation boundary used by transaction-plan construction, binding validation, and dry run.",
            "A missing or unavailable root is not automatically confirmed target absence.",
            "Target absence is confirmed only when a safe read-only lookup establishes that the exact target is not present.",
            "Unknown target state is not current target state.",
            "Matching unknown-state snapshots do not prove target freshness.",
            "Observation errors and malformed target data are not treated as absence.",
            "Production target-state observation creates no files or directories and performs no writes.",
            "A valid target-state binding does not authorize execution.",
            "A valid target-state binding does not authorize registration.",
            "Phase 14C.1 does not call the registration function.",
            "Phase 14C.1 does not accept or enforce confirmation.",
            "Phase 14C.1 does not enforce idempotency.",
            "A structural target comparison does not prove factual correctness of outcome-truth records.",
            "Phase 14D - Controlled Registration Transaction-Plan Identity/Binding and Dry-Run API/UI Seam",
        ):
            self.assertIn(required_phrase, doc_text)

    def test_controlled_registration_transaction_plan_binding_and_dry_run_api_ui_seam_preserves_target_freshness_and_non_authorization(self) -> None:
        doc_path = Path(
            "docs/PHASE_14D_CONTROLLED_REGISTRATION_TRANSACTION_PLAN_BINDING_DRY_RUN_API_UI_SEAM.md"
        )
        self.assertTrue(doc_path.exists())
        doc_text = doc_path.read_text(encoding="utf-8")
        for required_phrase in (
            "Phase 14D exposes the deterministic transaction plan, transaction-plan binding validator, and transaction dry run through a read-only API/UI seam.",
            "Transaction plans, binding results, target-state snapshots, dry-run results, idempotency previews, and receipts remain unpersisted.",
            "Unknown target state is not current target state.",
            "A missing or unavailable root is not confirmed target absence.",
            "Matching unknown-state snapshots do not prove target freshness.",
            "A valid transaction-plan binding does not authorize execution.",
            "A valid transaction-plan binding does not authorize registration.",
            "A passing dry run does not authorize execution.",
            "A passing dry run does not authorize registration.",
            "The idempotency-key preview is non-authoritative and unenforced.",
            "planned_write_count = 1 is future intent only.",
            "writes_performed = 0 is actual Phase 14D behavior.",
            "Phase 14D does not call the registration function.",
            "Phase 14D does not accept or enforce confirmation.",
            "A valid fingerprint proves integrity against the defined canonical representation only.",
            "It does not prove factual correctness of outcome-truth records.",
            "Phase 14E - Controlled Registration Transaction-Plan/Dry-Run API/UI Boundary Audit and Operator Handoff",
        ):
            self.assertIn(required_phrase, doc_text)

        wrappers = (
            api.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan,
            api.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_report,
            api.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding,
            api.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding_report,
            api.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run,
            api.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run_report,
        )
        for wrapper in wrappers:
            self.assertTrue(callable(wrapper))
        for signature in map(inspect.signature, wrappers):
            for forbidden_parameter in (
                "candidate_fingerprint",
                "planning_gate_fingerprint",
                "backend_plan_fingerprint",
                "transaction_plan_fingerprint",
                "target_identity",
                "target_identity_fingerprint",
                "target_state",
                "target_state_snapshot",
                "target_state_snapshot_fingerprint",
                "target_state_observation_status",
                "target_state_freshness_proven",
                "idempotency_key",
                "idempotency_key_preview",
                "dry_run_passed",
                "execution_authorized",
                "registration_authorized",
                "confirmation",
                "execute",
                "commit",
                "force",
                "override",
                "repair",
                "migrate",
                "score",
                "ranking",
                "aggregate",
            ):
                self.assertNotIn(forbidden_parameter, signature.parameters)

        desktop_source = inspect.getsource(desktop_panel)
        self.assertIn("Controlled Registration Transaction Plan", desktop_source)
        for required_control in (
            "Build Registration Transaction Plan",
            "Validate Transaction Plan Binding",
            "Run Registration Transaction Dry Run",
            "Copy Registration Transaction Plan Report",
            "Copy Transaction Plan Binding Report",
            "Copy Registration Transaction Dry-Run Report",
            "current_controlled_registration_transaction_plan = None",
            "current_controlled_registration_transaction_plan_binding_result = None",
            "current_controlled_registration_transaction_dry_run_result = None",
            "Transaction-Plan Binding Valid",
            "Target-State Freshness Status",
            "Would Call Registration Function",
        ):
            self.assertIn(required_control, desktop_source)
        transaction_ui_start = desktop_source.index('text="Controlled Registration Transaction Plan"')
        transaction_ui_end = desktop_source.index("scoring_contract_box = ttk.Frame")
        transaction_ui_source = desktop_source[transaction_ui_start:transaction_ui_end]
        for forbidden_control in (
            'text="Execute Registration"',
            'text="Commit Registration"',
            'text="Confirm Registration"',
            'text="Authorize Registration"',
            'text="Approve Registration"',
            'text="Auto Register"',
            'text="Force Register"',
            'text="Reserve Idempotency Key"',
            'text="Persist Transaction"',
            'text="Create Receipt"',
            'text="Override Target State"',
            'text="Override Fingerprint"',
            'text="Manual Score"',
            'text="Aggregate Score"',
            'text="Rank Results"',
        ):
            self.assertNotIn(forbidden_control, transaction_ui_source)

        viewport_action_source = inspect.getsource(desktop_panel.DesktopRightPanelMixin._run_pdf_viewport_action)
        branch_start = viewport_action_source.index('elif action == "build_deployed_rule_outcome_truth_controlled_registration_transaction_plan":')
        branch_end = viewport_action_source.index('elif action == "load_deployed_rule_outcome_truth_result":')
        transaction_branch_source = viewport_action_source[branch_start:branch_end]
        for forbidden_call in (
            "register_deployed_rule_outcome_truth_record_set(",
            "build_deployed_rule_outcome_truth_source_plan(",
            "record_deployed_rule_outcome_truth_source_result(",
            "_ensure_dirs(",
            "json.dump(",
            "write_text(",
            "_atomic_write_json(",
        ):
            self.assertNotIn(forbidden_call, transaction_branch_source)

        class _Var:
            def __init__(self, value: str) -> None:
                self._value = value
            def get(self) -> str:
                return self._value
            def set(self, value: str) -> None:
                self._value = value

        class _FakePanel:
            pass

        panel = _FakePanel()
        panel.deployed_rule_outcome_truth_status_var = _Var("")
        panel.status_var = _Var("")
        panel.deployed_rule_outcome_truth_rule_id_var = _Var("")
        panel.deployed_rule_outcome_truth_result_id_var = _Var("")
        panel.deployed_rule_outcome_truth_target_id_var = _Var("")
        panel.deployed_rule_outcome_truth_deployed_rule_id_var = _Var("")
        panel.deployed_rule_outcome_truth_snapshot_id_var = _Var("")
        panel.deployed_rule_outcome_truth_readiness_result_id_var = _Var("")
        panel.deployed_rule_outcome_truth_spec_result_id_var = _Var("")
        panel.deployed_rule_outcome_truth_start_var = _Var("")
        panel.deployed_rule_outcome_truth_end_var = _Var("")
        panel.deployed_rule_outcome_truth_source_id_var = _Var("")
        panel.deployed_rule_outcome_truth_record_set_id_var = _Var("")
        panel.deployed_rule_outcome_truth_record_json_var = _Var("")
        panel.deployed_rule_outcome_truth_plan_id_var = _Var("")
        panel.deployed_rule_outcome_truth_result_record_id_var = _Var("")
        panel.deployed_rule_outcome_truth_registration_confirmation_var = _Var("")
        panel.deployed_rule_outcome_truth_result_confirmation_var = _Var("")
        panel.pdf_viewport_id_var = _Var("")
        panel.current_controlled_registration_backend_plan = None
        panel.current_controlled_registration_backend_plan_candidate_fingerprint = None
        panel.current_controlled_registration_backend_plan_stale = False
        panel.current_controlled_registration_backend_plan_binding_result = None
        panel.current_controlled_registration_transaction_plan = None
        panel.current_controlled_registration_transaction_plan_stale = False
        panel.current_controlled_registration_transaction_plan_binding_result = None
        panel.current_controlled_registration_transaction_binding_stale = False
        panel.current_controlled_registration_transaction_dry_run_result = None
        panel.current_controlled_registration_transaction_dry_run_stale = False
        panel.clipboard_value = ""
        panel._current_source_document_id = lambda: "doc-1"
        panel.clipboard_clear = lambda: setattr(panel, "clipboard_value", "")
        panel.clipboard_append = lambda text: setattr(panel, "clipboard_value", text)
        panel._set_deployed_rule_outcome_truth_status = desktop_panel.DesktopRightPanelMixin._set_deployed_rule_outcome_truth_status.__get__(panel, _FakePanel)
        panel._parse_deployed_rule_outcome_truth_candidate_record_set = desktop_panel.DesktopRightPanelMixin._parse_deployed_rule_outcome_truth_candidate_record_set.__get__(panel, _FakePanel)
        panel._mark_deployed_rule_outcome_truth_stale = desktop_panel.DesktopRightPanelMixin._mark_deployed_rule_outcome_truth_stale.__get__(panel, _FakePanel)
        panel._on_deployed_rule_outcome_truth_input_changed = desktop_panel.DesktopRightPanelMixin._on_deployed_rule_outcome_truth_input_changed.__get__(panel, _FakePanel)
        panel._controlled_registration_backend_plan_blocked_payload = desktop_panel.DesktopRightPanelMixin._controlled_registration_backend_plan_blocked_payload.__get__(panel, _FakePanel)
        panel._controlled_registration_backend_plan_loaded = desktop_panel.DesktopRightPanelMixin._controlled_registration_backend_plan_loaded.__get__(panel, _FakePanel)
        panel._controlled_registration_transaction_plan_blocked_payload = desktop_panel.DesktopRightPanelMixin._controlled_registration_transaction_plan_blocked_payload.__get__(panel, _FakePanel)
        panel._controlled_registration_transaction_plan_binding_blocked_payload = desktop_panel.DesktopRightPanelMixin._controlled_registration_transaction_plan_binding_blocked_payload.__get__(panel, _FakePanel)
        panel._controlled_registration_transaction_dry_run_blocked_payload = desktop_panel.DesktopRightPanelMixin._controlled_registration_transaction_dry_run_blocked_payload.__get__(panel, _FakePanel)
        panel._controlled_registration_transaction_plan_loaded = desktop_panel.DesktopRightPanelMixin._controlled_registration_transaction_plan_loaded.__get__(panel, _FakePanel)
        panel._run_pdf_viewport_action = desktop_panel.DesktopRightPanelMixin._run_pdf_viewport_action.__get__(panel, _FakePanel)

        original_build_backend_plan = desktop_panel.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan
        original_backend_plan_report = desktop_panel.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report
        original_validate_backend_plan = desktop_panel.validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding
        original_backend_binding_report = desktop_panel.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_report
        original_build_transaction_plan = desktop_panel.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan
        original_transaction_plan_report = desktop_panel.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_report
        original_validate_transaction_plan = desktop_panel.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding
        original_transaction_binding_report = desktop_panel.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding_report
        original_run_dry_run = desktop_panel.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run
        original_dry_run_report = desktop_panel.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run_report
        try:
            with TemporaryDirectory() as tmp:
                root = Path(tmp)
                identity = _write_telemetry_snapshot_fixture(root)
                candidate = {
                    **identity,
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
                equivalent_candidate = {
                    "records": deepcopy(candidate["records"]),
                    "source_authority_class": "authoritative",
                    "source_id": "source-1",
                    "source_type": "external_authoritative_result",
                    **identity,
                }
                changed_candidate = deepcopy(candidate)
                changed_candidate["source_id"] = "source-2"

                desktop_panel.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan = (
                    lambda candidate_record_set: api.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan(
                        candidate_record_set,
                        root=root,
                    )
                )
                desktop_panel.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report = (
                    lambda candidate_record_set: api.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report(
                        candidate_record_set,
                        root=root,
                    )
                )
                desktop_panel.validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding = (
                    lambda backend_plan, candidate_record_set: api.validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding(
                        backend_plan,
                        candidate_record_set,
                        root=root,
                    )
                )
                desktop_panel.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_report = (
                    lambda backend_plan, candidate_record_set: api.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_report(
                        backend_plan,
                        candidate_record_set,
                        root=root,
                    )
                )
                desktop_panel.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan = (
                    lambda backend_plan, candidate_record_set: api.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan(
                        backend_plan,
                        candidate_record_set,
                        root=root,
                    )
                )
                desktop_panel.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_report = (
                    lambda backend_plan, candidate_record_set: api.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_report(
                        backend_plan,
                        candidate_record_set,
                        root=root,
                    )
                )
                desktop_panel.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding = (
                    lambda transaction_plan, backend_plan, candidate_record_set: api.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(
                        transaction_plan,
                        backend_plan,
                        candidate_record_set,
                        root=root,
                    )
                )
                desktop_panel.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding_report = (
                    lambda transaction_plan, backend_plan, candidate_record_set: api.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding_report(
                        transaction_plan,
                        backend_plan,
                        candidate_record_set,
                        root=root,
                    )
                )
                desktop_panel.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run = (
                    lambda transaction_plan, backend_plan, candidate_record_set: api.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run(
                        transaction_plan,
                        backend_plan,
                        candidate_record_set,
                        root=root,
                    )
                )
                desktop_panel.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run_report = (
                    lambda transaction_plan, backend_plan, candidate_record_set: api.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run_report(
                        transaction_plan,
                        backend_plan,
                        candidate_record_set,
                        root=root,
                    )
                )

                panel._run_pdf_viewport_action("build_deployed_rule_outcome_truth_controlled_registration_transaction_plan")
                self.assertIn("candidate_record_set_required", panel.deployed_rule_outcome_truth_status_var.get())

                panel.deployed_rule_outcome_truth_record_json_var.set(json.dumps(candidate, sort_keys=True))
                panel._run_pdf_viewport_action("build_deployed_rule_outcome_truth_controlled_registration_transaction_plan")
                self.assertIn("backend_plan_required", panel.deployed_rule_outcome_truth_status_var.get())

                panel._run_pdf_viewport_action("build_deployed_rule_outcome_truth_controlled_registration_backend_plan")
                panel._run_pdf_viewport_action("validate_deployed_rule_outcome_truth_controlled_registration_transaction_plan_binding")
                self.assertIn("transaction_plan_required", panel.deployed_rule_outcome_truth_status_var.get())

                panel._run_pdf_viewport_action("build_deployed_rule_outcome_truth_controlled_registration_transaction_plan")
                build_status = panel.deployed_rule_outcome_truth_status_var.get()
                self.assertIn("Controlled Registration Transaction Plan Status: transaction_plan_ready", build_status)
                self.assertIn("Transaction Plan Current: yes", build_status)
                self.assertIn("Target-State Observation Status: observed", build_status)
                self.assertIn("Target-State Observation Basis: safe_direct_target_file_read", build_status)
                self.assertIn("Transaction-Plan Fingerprint: sha256:", build_status)
                self.assertIn("Non-Authoritative Idempotency Preview: sha256:", build_status)

                panel._run_pdf_viewport_action("copy_deployed_rule_outcome_truth_controlled_registration_transaction_plan_report")
                self.assertIn("A passing dry run does not authorize registration.", panel.clipboard_value)
                self.assertNotIn("{", panel.clipboard_value)

                panel._run_pdf_viewport_action("validate_deployed_rule_outcome_truth_controlled_registration_transaction_plan_binding")
                binding_status = panel.deployed_rule_outcome_truth_status_var.get()
                self.assertIn("Transaction-Plan Binding Status: valid", binding_status)
                self.assertIn("Transaction-Plan Binding Valid: yes", binding_status)
                self.assertIn("Target-State Freshness Status: fresh", binding_status)
                self.assertIn("Target-State Freshness Proven: yes", binding_status)
                self.assertIn("Target-Conflict Detected: no", binding_status)
                panel._run_pdf_viewport_action("copy_deployed_rule_outcome_truth_controlled_registration_transaction_plan_binding_report")
                self.assertIn("A valid transaction-plan binding does not authorize registration.", panel.clipboard_value)
                self.assertNotIn("{", panel.clipboard_value)

                panel._run_pdf_viewport_action("run_deployed_rule_outcome_truth_controlled_registration_transaction_dry_run")
                dry_run_status = panel.deployed_rule_outcome_truth_status_var.get()
                self.assertIn("Transaction Dry-Run Status: dry_run_passed", dry_run_status)
                self.assertIn("Dry Run Passed: yes", dry_run_status)
                self.assertIn("Would Call Registration Function: no", dry_run_status)
                self.assertIn("Execution Authorized: no", dry_run_status)
                self.assertIn("Registration Authorized: no", dry_run_status)
                self.assertIn("Transaction Writes Performed: 0", dry_run_status)
                panel._run_pdf_viewport_action("copy_deployed_rule_outcome_truth_controlled_registration_transaction_dry_run_report")
                self.assertIn("A passing dry run does not authorize registration.", panel.clipboard_value)
                self.assertNotIn("{", panel.clipboard_value)

                panel.deployed_rule_outcome_truth_record_json_var.set(json.dumps(equivalent_candidate, sort_keys=True))
                panel._on_deployed_rule_outcome_truth_input_changed()
                stale_status = panel.deployed_rule_outcome_truth_status_var.get()
                self.assertTrue(panel.current_controlled_registration_transaction_plan_stale)
                self.assertTrue(panel.current_controlled_registration_transaction_binding_stale)
                self.assertTrue(panel.current_controlled_registration_transaction_dry_run_stale)
                self.assertIn("Controlled Registration Transaction Plan Status: transaction_plan_candidate_input_stale", stale_status)
                self.assertIn("Transaction Plan Current: no", stale_status)
                self.assertIn("Transaction-Plan Binding Status: transaction_plan_binding_candidate_input_stale", stale_status)
                self.assertIn("Transaction Dry-Run Status: transaction_dry_run_candidate_input_stale", stale_status)

                panel._run_pdf_viewport_action("build_deployed_rule_outcome_truth_controlled_registration_backend_plan")
                self.assertIsNone(panel.current_controlled_registration_transaction_plan)
                panel._run_pdf_viewport_action("build_deployed_rule_outcome_truth_controlled_registration_transaction_plan")
                panel._run_pdf_viewport_action("validate_deployed_rule_outcome_truth_controlled_registration_transaction_plan_binding")
                panel._run_pdf_viewport_action("run_deployed_rule_outcome_truth_controlled_registration_transaction_dry_run")
                self.assertIn("Dry Run Passed: yes", panel.deployed_rule_outcome_truth_status_var.get())

                panel.deployed_rule_outcome_truth_record_json_var.set(json.dumps(changed_candidate, sort_keys=True))
                panel._on_deployed_rule_outcome_truth_input_changed()
                panel._run_pdf_viewport_action("validate_deployed_rule_outcome_truth_controlled_registration_transaction_plan_binding")
                changed_status = panel.deployed_rule_outcome_truth_status_var.get()
                self.assertTrue(
                    any(
                        token in changed_status
                        for token in (
                            "stale_candidate",
                            "transaction_plan_candidate_fingerprint_mismatch",
                            "backend_plan_candidate_fingerprint_mismatch",
                        )
                    )
                )
                self.assertIn("Execution Authorized: no", changed_status)
                self.assertIn("Registration Authorized: no", changed_status)
        finally:
            desktop_panel.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan = original_build_backend_plan
            desktop_panel.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report = original_backend_plan_report
            desktop_panel.validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding = original_validate_backend_plan
            desktop_panel.format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_report = original_backend_binding_report
            desktop_panel.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan = original_build_transaction_plan
            desktop_panel.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_report = original_transaction_plan_report
            desktop_panel.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding = original_validate_transaction_plan
            desktop_panel.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding_report = original_transaction_binding_report
            desktop_panel.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run = original_run_dry_run
            desktop_panel.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run_report = original_dry_run_report

    def test_controlled_registration_transaction_plan_dry_run_api_ui_boundary_audit_and_operator_handoff_preserve_target_semantics_and_non_authorization(self) -> None:
        handoff_path = Path(
            "docs/PHASE_14E_CONTROLLED_REGISTRATION_TRANSACTION_PLAN_DRY_RUN_API_UI_BOUNDARY_AUDIT_OPERATOR_HANDOFF.md"
        )
        self.assertTrue(handoff_path.exists())
        handoff_text = handoff_path.read_text(encoding="utf-8")

        for required_heading in (
            "## 1. Purpose",
            "## 2. Scope",
            "## 3. Frozen Feature Surface",
            "## 4. Prerequisites",
            "## 5. Complete Operator Workflow",
            "## 6. Build-Plan Workflow",
            "## 7. Binding-Validation Workflow",
            "## 8. Dry-Run Workflow",
            "## 9. Transaction Identity Interpretation",
            "## 10. Target-State Interpretation",
            "## 11. Unknown-Target Workflow",
            "## 12. Confirmed-Absent Workflow",
            "## 13. Present-Equivalent Workflow",
            "## 14. Conflicting-Target Workflow",
            "## 15. Candidate/Backend-Plan Stale Workflow",
            "## 16. Modified Transaction-Plan Workflow",
            "## 17. Changed-Target Workflow",
            "## 18. Equivalent-Candidate Revalidation",
            "## 19. Idempotency-Preview Limits",
            "## 20. Dry-Run Versus Authorization",
            "## 21. Status and Blocker Reference",
            "## 22. Public-Safe Copy Behavior",
            "## 23. In-Memory-Only Boundary",
            "## 24. No-Registration / No-Authorization Boundary",
            "## 25. Exact Focused Validation Evidence",
            "## 26. Skipped Broad Tests by Policy",
            "## 27. Known Risks",
            "## 28. Recommended Next Phase",
        ):
            self.assertIn(required_heading, handoff_text)

        for required_phrase in (
            "deterministic, read-only controlled-registration transaction-plan and dry-run API/UI seam",
            "current candidate -> current Phase 13 backend plan -> current transaction plan where required",
            "Build Registration Transaction Plan",
            "Validate Transaction Plan Binding",
            "Run Registration Transaction Dry Run",
            "Copy Registration Transaction Plan Report",
            "Copy Transaction Plan Binding Report",
            "Copy Registration Transaction Dry-Run Report",
            "Unknown target state is not current target state.",
            "A missing or unavailable root is not confirmed target absence.",
            "Matching unknown-state snapshots do not prove freshness.",
            "structural equivalence only",
            "remains blocking",
            "Equivalent candidate mappings can revalidate",
            "non-authoritative and unenforced",
            "It does not authorize execution.",
            "It does not authorize registration.",
            "It does not accept or enforce confirmation.",
            "It does not enforce idempotency.",
            "candidate_record_set_required",
            "backend_plan_required",
            "transaction_plan_required",
            "transaction_plan_candidate_fingerprint_mismatch",
            "transaction_plan_backend_plan_fingerprint_mismatch",
            "transaction_plan_target_identity_mismatch",
            "transaction_plan_fingerprint_mismatch",
            "transaction_plan_idempotency_preview_mismatch",
            "transaction_plan_target_state_changed",
            "target_state_check_unavailable",
            "transaction_target_conflict",
            "Raw plan dictionaries are not copied.",
            "Raw candidate JSON is not copied.",
            "Raw target records are not copied.",
            "Transaction plan remains in memory only.",
            "Binding result remains in memory only.",
            "Dry-run result remains in memory only.",
            "No transaction ID exists.",
            "No receipt exists.",
            "test_controlled_outcome_truth_registration_transaction_plan_and_dry_run_are_deterministic_read_only_and_non_authoritative",
            "test_controlled_registration_transaction_plan_identity_target_binding_and_stale_target_gate_is_deterministic_read_only_and_non_authoritative",
            "test_controlled_registration_target_state_observer_distinguishes_unknown_absent_present_and_changed_without_writes",
            "test_controlled_registration_transaction_plan_binding_and_dry_run_api_ui_seam_preserves_target_freshness_and_non_authorization",
            "Phase 14F - Controlled Registration Transaction-Plan/Dry-Run API/UI Release Packet and Final Freeze",
            "broad regression coverage remains unclaimed",
        ):
            self.assertIn(required_phrase, handoff_text)

        self.test_controlled_registration_transaction_plan_binding_and_dry_run_api_ui_seam_preserves_target_freshness_and_non_authorization()

        wrappers = (
            api.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan,
            api.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_report,
            api.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding,
            api.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding_report,
            api.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run,
            api.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run_report,
        )
        for wrapper in wrappers:
            self.assertTrue(callable(wrapper))
        for signature in map(inspect.signature, wrappers):
            for forbidden_parameter in (
                "candidate_fingerprint",
                "backend_plan_fingerprint",
                "planning_gate_fingerprint",
                "transaction_plan_fingerprint",
                "target_identity",
                "target_identity_fingerprint",
                "target_state",
                "target_state_snapshot",
                "target_state_snapshot_fingerprint",
                "target_state_observation_status",
                "target_state_freshness_status",
                "target_state_freshness_proven",
                "stale_target_detected",
                "target_conflict_detected",
                "idempotency_key",
                "idempotency_key_preview",
                "transaction_plan_binding_valid",
                "dry_run_passed",
                "execution_authorized",
                "registration_authorized",
                "confirmation",
                "execute",
                "commit",
                "force",
                "override",
                "repair",
                "migrate",
                "score",
                "ranking",
                "aggregate",
            ):
                self.assertNotIn(forbidden_parameter, signature.parameters)

        desktop_source = inspect.getsource(desktop_panel)
        for required_control in (
            "Build Registration Transaction Plan",
            "Validate Transaction Plan Binding",
            "Run Registration Transaction Dry Run",
            "Copy Registration Transaction Plan Report",
            "Copy Transaction Plan Binding Report",
            "Copy Registration Transaction Dry-Run Report",
        ):
            self.assertIn(required_control, desktop_source)
        for required_memory_field in (
            "current_controlled_registration_transaction_plan = None",
            "current_controlled_registration_transaction_plan_binding_result = None",
            "current_controlled_registration_transaction_dry_run_result = None",
        ):
            self.assertIn(required_memory_field, desktop_source)
        for forbidden_control in (
            'text="Execute Registration"',
            'text="Commit Registration"',
            'text="Confirm Registration"',
            'text="Authorize Registration"',
            'text="Approve Registration"',
            'text="Auto Register"',
            'text="Force Register"',
            'text="Reserve Idempotency Key"',
            'text="Persist Transaction"',
            'text="Create Receipt"',
            'text="Override Target State"',
            'text="Override Fingerprint"',
            'text="Override Readiness"',
            'text="Override Binding"',
            'text="Override Authorization"',
            'text="Manual Score"',
            'text="Aggregate Score"',
            'text="Rank Results"',
        ):
            self.assertNotIn(forbidden_control, desktop_source)

        viewport_action_source = inspect.getsource(desktop_panel.DesktopRightPanelMixin._run_pdf_viewport_action)
        branch_start = viewport_action_source.index('elif action == "build_deployed_rule_outcome_truth_controlled_registration_transaction_plan":')
        branch_end = viewport_action_source.index('elif action == "load_deployed_rule_outcome_truth_result":')
        transaction_branch_source = viewport_action_source[branch_start:branch_end]
        for forbidden_call in (
            "register_deployed_rule_outcome_truth_record_set(",
            "build_deployed_rule_outcome_truth_source_plan(",
            "record_deployed_rule_outcome_truth_source_result(",
            "_ensure_dirs(",
            "json.dump(",
            "write_text(",
            "_atomic_write_json(",
        ):
            self.assertNotIn(forbidden_call, transaction_branch_source)

    def test_controlled_registration_transaction_plan_dry_run_api_ui_release_packet_and_final_freeze_preserve_target_semantics_and_non_authorization(self) -> None:
        release_path = Path(
            "docs/PHASE_14F_CONTROLLED_REGISTRATION_TRANSACTION_PLAN_DRY_RUN_API_UI_RELEASE_PACKET.md"
        )
        self.assertTrue(release_path.exists())
        release_text = release_path.read_text(encoding="utf-8")

        for required_heading in (
            "## 1. Release Scope",
            "## 2. Phase 14B-14F History",
            "## 3. Frozen Backend Surface",
            "## 4. Frozen API Surface",
            "## 5. Frozen Desktop Surface",
            "## 6. Prerequisite Chain",
            "## 7. Transaction-Plan Identity Contract",
            "## 8. Target-Identity Contract",
            "## 9. Target-State Observation Contract",
            "## 10. Target-State Snapshot/Fingerprint Contract",
            "## 11. Binding Contract",
            "## 12. Stale/Modified Contracts",
            "## 13. Unknown Target-State Contract",
            "## 14. Equivalent-Candidate Behavior",
            "## 15. Idempotency-Preview Contract",
            "## 16. Dry-Run Contract",
            "## 17. Readiness/Binding/Dry-Run Versus Authorization",
            "## 18. Status/Blocker Reference",
            "## 19. Operator Workflow",
            "## 20. Public-Safe Reports",
            "## 21. In-Memory-Only Boundary",
            "## 22. No-Registration / No-Execution Boundary",
            "## 23. Forbidden Controls and Authority",
            "## 24. Explicit Non-Claims",
            "## 25. Exact Validation Evidence",
            "## 26. Skipped Broad Tests by Policy",
            "## 27. Known Risks",
            "## 28. Final Freeze Status",
            "## 29. Recommended Next Phase",
        ):
            self.assertIn(required_heading, release_text)

        for required_phrase in (
            "Phase 14B established the deterministic transaction-plan and read-only dry-run contract.",
            "Phase 14C added transaction-plan identity validation",
            "Phase 14C.1 hardened the production target-state observer",
            "Phase 14D exposed the frozen transaction plan, binding validator, and dry run through a narrow read-only API/UI seam.",
            "Phase 14E completed the focused boundary audit and operator handoff.",
            "Build Registration Transaction Plan",
            "Validate Transaction Plan Binding",
            "Run Registration Transaction Dry Run",
            "Copy Registration Transaction Plan Report",
            "Copy Transaction Plan Binding Report",
            "Copy Registration Transaction Dry-Run Report",
            "current candidate -> current Phase 13 backend plan -> current transaction plan for validation and dry run",
            "candidate_fingerprint",
            "backend_plan_fingerprint",
            "target_identity_fingerprint",
            "target_state_snapshot_fingerprint",
            "transaction_plan_fingerprint",
            "idempotency_key_preview",
            "Unknown target state remains unknown.",
            "Unavailable root is not confirmed absent.",
            "Confirmed absence requires safe observation.",
            "Present equivalent remains structural only.",
            "Conflicting target remains blocking.",
            "Equivalent candidate mapping can revalidate",
            "non-authoritative, unpersisted, unreserved, and unenforced",
            "dry_run_passed remains structural only.",
            "execution_authorized = false",
            "registration_authorized = false",
            "confirmation_accepted = false",
            "confirmation_enforced = false",
            "idempotency_enforced = false",
            "would_call_registration_function = false",
            "planned_write_count = 1",
            "writes_performed = 0",
            "candidate_record_set_required",
            "backend_plan_required",
            "transaction_plan_required",
            "transaction_plan_candidate_fingerprint_mismatch",
            "transaction_plan_backend_plan_fingerprint_mismatch",
            "transaction_plan_target_identity_mismatch",
            "transaction_plan_fingerprint_mismatch",
            "transaction_plan_idempotency_preview_mismatch",
            "transaction_plan_target_state_changed",
            "target_state_check_unavailable",
            "transaction_target_conflict",
            "Raw plan dictionaries are not copied.",
            "Raw candidate JSON is not copied.",
            "Raw target records are not copied.",
            "Transaction plan remains unpersisted.",
            "Binding result remains unpersisted.",
            "Target-state snapshot remains unpersisted.",
            "Dry-run result remains unpersisted.",
            "No transaction ID exists.",
            "No receipt exists.",
            "factual truth correctness",
            "duplicate prevention",
            "broad regression coverage remains unclaimed",
            "Backend feature surface: frozen.",
            "API wrapper contract: frozen.",
            "Desktop transaction-plan/dry-run seam: frozen.",
            "Mutation authority: none.",
            "Registration authority: none.",
            "Phase 15A - Controlled Registration Transaction Execution Authorization and Confirmation Contract Gate",
        ):
            self.assertIn(required_phrase, release_text)

        self.test_controlled_registration_transaction_plan_dry_run_api_ui_boundary_audit_and_operator_handoff_preserve_target_semantics_and_non_authorization()

        backend_functions = (
            truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan,
            truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_report,
            truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding,
            truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding_report,
            truth.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run,
            truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run_report,
        )
        api_wrappers = (
            api.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan,
            api.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_report,
            api.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding,
            api.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding_report,
            api.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run,
            api.format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run_report,
        )
        for function in backend_functions + api_wrappers:
            self.assertTrue(callable(function))

        for signature in map(inspect.signature, api_wrappers):
            for forbidden_parameter in (
                "confirmation",
                "execution_authorized",
                "registration_authorized",
                "candidate_fingerprint",
                "backend_plan_fingerprint",
                "planning_gate_fingerprint",
                "transaction_plan_fingerprint",
                "target_identity",
                "target_identity_fingerprint",
                "target_state",
                "target_state_snapshot",
                "target_state_snapshot_fingerprint",
                "target_state_observation_status",
                "target_state_freshness_status",
                "target_state_freshness_proven",
                "idempotency_key",
                "idempotency_key_preview",
            ):
                self.assertNotIn(forbidden_parameter, signature.parameters)

        backend_sources = [inspect.getsource(fn) for fn in backend_functions]
        api_sources = [inspect.getsource(fn) for fn in api_wrappers]
        desktop_source = inspect.getsource(desktop_panel)
        relevant_sources = backend_sources + api_sources + [desktop_source]

        for forbidden_call in (
            "register_deployed_rule_outcome_truth_record_set(",
            "build_deployed_rule_outcome_truth_source_plan(",
            "record_deployed_rule_outcome_truth_source_result(",
            "_ensure_dirs(",
            "json.dump(",
            "write_text(",
            "_atomic_write_json(",
        ):
            for source in relevant_sources:
                if source is desktop_source:
                    pass
            for source in backend_sources + api_sources:
                self.assertNotIn(forbidden_call, source)

        for required_control in (
            "Build Registration Transaction Plan",
            "Validate Transaction Plan Binding",
            "Run Registration Transaction Dry Run",
            "Copy Registration Transaction Plan Report",
            "Copy Transaction Plan Binding Report",
            "Copy Registration Transaction Dry-Run Report",
        ):
            self.assertIn(required_control, desktop_source)
        transaction_ui_start = desktop_source.index('text="Controlled Registration Transaction Plan"')
        transaction_ui_end = desktop_source.index("scoring_contract_box = ttk.Frame")
        transaction_ui_source = desktop_source[transaction_ui_start:transaction_ui_end]
        for forbidden_control in (
            'text="Register"',
            'text="Execute Registration"',
            'text="Commit Registration"',
            'text="Confirm Registration"',
            'text="Authorize Registration"',
            'text="Approve Registration"',
            'text="Auto Register"',
            'text="Force Register"',
            'text="Register From Plan"',
            'text="Register From Dry Run"',
            'text="Persist Transaction Plan"',
            'text="Persist Binding Result"',
            'text="Persist Dry Run"',
            'text="Reserve Idempotency Key"',
            'text="Enforce Idempotency"',
            'text="Create Receipt"',
            'text="Repair Transaction Plan"',
            'text="Repair Target"',
            'text="Migrate Target"',
            'text="Override Fingerprint"',
            'text="Override Target Identity"',
            'text="Override Target State"',
            'text="Override Freshness"',
            'text="Override Binding"',
            'text="Override Readiness"',
            'text="Override Authorization"',
            'text="Manual Score"',
            'text="Aggregate Score"',
            'text="Rank Results"',
        ):
            self.assertNotIn(forbidden_control, transaction_ui_source)

    def test_controlled_registration_execution_authorization_confirmation_contract_gate_is_read_only_advisory_and_non_authoritative(self) -> None:
        self.assertTrue(
            callable(
                truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate
            )
        )
        self.assertTrue(
            callable(
                truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate_report
            )
        )

        gate_source = inspect.getsource(
            truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate
        )
        report_source = inspect.getsource(
            truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate_report
        )
        for source in (gate_source, report_source):
            for forbidden_call in (
                "register_deployed_rule_outcome_truth_record_set(",
                "build_deployed_rule_outcome_truth_source_plan(",
                "record_deployed_rule_outcome_truth_source_result(",
                "_ensure_dirs(",
                "json.dump(",
                "write_text(",
                "_atomic_write_json(",
                "uuid.uuid4",
                "random.",
                "time.time",
                "datetime.now",
                "datetime.utcnow",
                "tempfile",
                "Path.mkdir",
                "os.makedirs",
            ):
                self.assertNotIn(forbidden_call, source)
        self.assertIn(
            "validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(",
            gate_source,
        )
        self.assertIn(
            "run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run(",
            gate_source,
        )

        gate_signature = inspect.signature(
            truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate
        )
        report_signature = inspect.signature(
            truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate_report
        )
        self.assertEqual(
            tuple(gate_signature.parameters),
            ("transaction_plan", "backend_plan", "candidate_record_set", "root"),
        )
        self.assertEqual(
            tuple(report_signature.parameters),
            ("transaction_plan", "backend_plan", "candidate_record_set", "root"),
        )
        for signature in (gate_signature, report_signature):
            for forbidden_parameter in (
                "confirmation",
                "confirmation_text",
                "confirmation_phrase",
                "authorization_artifact",
                "authorization_artifact_id",
                "authorization_id",
                "binding_result",
                "dry_run_result",
                "idempotency_key",
                "authoritative_idempotency_key",
                "execution_authorized",
                "registration_authorized",
                "execute",
                "commit",
                "register",
                "force",
                "override",
                "repair",
                "migrate",
                "score",
                "ranking",
                "aggregate",
            ):
                self.assertNotIn(forbidden_parameter, signature.parameters)

        missing_transaction_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate(
            None,
            {},
            {},
        )
        malformed_transaction_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate(
            [],
            {},
            {},
        )
        missing_backend_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate(
            {},
            None,
            {},
        )
        malformed_backend_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate(
            {},
            [],
            {},
        )
        missing_candidate = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate(
            {},
            {},
            None,
        )
        malformed_candidate = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate(
            {},
            {},
            [],
        )
        self.assertEqual(missing_transaction_plan["status"], "missing")
        self.assertIn("transaction_plan_required", missing_transaction_plan["blockers"])
        self.assertEqual(malformed_transaction_plan["status"], "malformed")
        self.assertIn("transaction_plan_malformed", malformed_transaction_plan["blockers"])
        self.assertEqual(missing_backend_plan["status"], "missing")
        self.assertIn("backend_plan_required", missing_backend_plan["blockers"])
        self.assertEqual(malformed_backend_plan["status"], "malformed")
        self.assertIn("backend_plan_malformed", malformed_backend_plan["blockers"])
        self.assertEqual(missing_candidate["status"], "missing")
        self.assertIn("candidate_record_set_required", missing_candidate["blockers"])
        self.assertEqual(malformed_candidate["status"], "malformed")
        self.assertIn("candidate_record_set_malformed", malformed_candidate["blockers"])

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            valid_root = root / "valid"
            identity = _write_telemetry_snapshot_fixture(valid_root)
            candidate = {
                **identity,
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
            backend_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan(
                deepcopy(candidate),
                root=valid_root,
            )
            transaction_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan(
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )
            candidate_before = deepcopy(candidate)
            backend_plan_before = deepcopy(backend_plan)
            transaction_plan_before = deepcopy(transaction_plan)
            before_valid = sorted(str(path.relative_to(valid_root)) for path in valid_root.rglob("*"))

            contract_gate = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate(
                transaction_plan,
                backend_plan,
                candidate,
                root=valid_root,
            )
            contract_report = truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate_report(
                transaction_plan,
                backend_plan,
                candidate,
                root=valid_root,
            )

            stale_candidate = deepcopy(candidate)
            stale_candidate["records"][0]["actual_or_adjudicated_outcome"] = "mars_day"
            stale_contract = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate(
                transaction_plan,
                backend_plan,
                stale_candidate,
                root=valid_root,
            )

            modified_transaction_plan = deepcopy(transaction_plan)
            modified_transaction_plan["transaction_plan_fingerprint"] = "sha256:" + ("2" * 64)
            modified_contract = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate(
                modified_transaction_plan,
                backend_plan,
                candidate,
                root=valid_root,
            )

            wrong_write_function_plan = deepcopy(transaction_plan)
            wrong_write_function_plan["planned_write_function"] = "not_register"
            wrong_write_function_contract = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate(
                wrong_write_function_plan,
                backend_plan,
                candidate,
                root=valid_root,
            )

            wrong_write_count_plan = deepcopy(transaction_plan)
            wrong_write_count_plan["planned_write_count"] = 2
            wrong_write_count_contract = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate(
                wrong_write_count_plan,
                backend_plan,
                candidate,
                root=valid_root,
            )

            base_binding = truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(
                transaction_plan,
                backend_plan,
                candidate,
                root=valid_root,
            )
            original_binding = (
                truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding
            )
            try:
                def _conflict_binding(*args, **kwargs):
                    payload = deepcopy(base_binding)
                    payload["status"] = "target_conflict"
                    payload["target_conflict_detected"] = True
                    payload["current_target_state"] = "target_present_conflicting"
                    payload["blockers"] = ["transaction_target_conflict"]
                    return payload

                truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding = _conflict_binding
                conflict_contract = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate(
                    transaction_plan,
                    backend_plan,
                    candidate,
                    root=valid_root,
                )

                def _unknown_binding(*args, **kwargs):
                    payload = deepcopy(base_binding)
                    payload["status"] = "target_state_unknown"
                    payload["target_state_observation_available"] = False
                    payload["target_state_binding_valid"] = False
                    payload["target_state_freshness_status"] = "unknown"
                    payload["target_state_freshness_proven"] = False
                    payload["current_target_state"] = "target_state_unknown"
                    payload["blockers"] = ["target_state_unknown"]
                    return payload

                truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding = _unknown_binding
                unknown_contract = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate(
                    transaction_plan,
                    backend_plan,
                    candidate,
                    root=valid_root,
                )
            finally:
                truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding = original_binding

            original_dry_run = (
                truth.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run
            )
            try:
                def _failed_dry_run(*args, **kwargs):
                    payload = deepcopy(
                        original_dry_run(
                            *args,
                            **kwargs,
                        )
                    )
                    payload["status"] = "blocked"
                    payload["dry_run_passed"] = False
                    payload["blockers"] = ["synthetic_dry_run_failure"]
                    return payload

                truth.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run = _failed_dry_run
                dry_run_failed_contract = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate(
                    transaction_plan,
                    backend_plan,
                    candidate,
                    root=valid_root,
                )
            finally:
                truth.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run = original_dry_run

            after_valid = sorted(str(path.relative_to(valid_root)) for path in valid_root.rglob("*"))

        self.assertEqual(candidate, candidate_before)
        self.assertEqual(backend_plan, backend_plan_before)
        self.assertEqual(transaction_plan, transaction_plan_before)
        self.assertEqual(before_valid, after_valid)

        self.assertEqual(contract_gate["status"], "contract_ready")
        self.assertTrue(contract_gate["ready_to_design_future_authorization_artifact"])
        self.assertEqual(contract_gate["transaction_plan_status"], "transaction_plan_ready")
        self.assertEqual(contract_gate["transaction_plan_binding_status"], "valid")
        self.assertTrue(contract_gate["transaction_plan_binding_valid"])
        self.assertTrue(contract_gate["transaction_plan_integrity_valid"])
        self.assertTrue(contract_gate["candidate_binding_valid"])
        self.assertTrue(contract_gate["backend_plan_binding_valid"])
        self.assertTrue(contract_gate["planning_gate_binding_valid"])
        self.assertTrue(contract_gate["target_identity_binding_valid"])
        self.assertTrue(contract_gate["target_state_binding_valid"])
        self.assertTrue(contract_gate["target_state_observation_available"])
        self.assertEqual(contract_gate["target_state_freshness_status"], "fresh")
        self.assertTrue(contract_gate["target_state_freshness_proven"])
        self.assertFalse(contract_gate["stale_target_detected"])
        self.assertFalse(contract_gate["target_state_changed_detected"])
        self.assertFalse(contract_gate["target_conflict_detected"])
        self.assertTrue(contract_gate["idempotency_preview_valid"])
        self.assertFalse(contract_gate["idempotency_preview_authoritative"])
        self.assertFalse(contract_gate["idempotency_enforced"])
        self.assertEqual(contract_gate["dry_run_status"], "dry_run_passed")
        self.assertTrue(contract_gate["dry_run_passed"])
        self.assertFalse(contract_gate["would_call_registration_function"])
        self.assertEqual(contract_gate["planned_write_function"], "register_deployed_rule_outcome_truth_record_set")
        self.assertEqual(contract_gate["planned_write_count"], 1)
        self.assertEqual(contract_gate["required_future_confirmation"], truth.REGISTER_CONFIRMATION)
        self.assertEqual(contract_gate["confirmation_match_policy"]["match_type"], "exact_literal")
        self.assertTrue(contract_gate["confirmation_match_policy"]["case_sensitive"])
        self.assertFalse(contract_gate["confirmation_match_policy"]["trim_before_compare"])
        self.assertEqual(contract_gate["confirmation_match_policy"]["unicode_normalization"], "none")
        self.assertFalse(contract_gate["confirmation_match_policy"]["substring_match_allowed"])
        self.assertFalse(contract_gate["confirmation_match_policy"]["implicit_confirmation_allowed"])
        self.assertFalse(contract_gate["confirmation_supplied_in_this_phase"])
        self.assertFalse(contract_gate["confirmation_matched_in_this_phase"])
        self.assertFalse(contract_gate["confirmation_accepted_in_this_phase"])
        self.assertFalse(contract_gate["confirmation_enforced_in_this_phase"])
        self.assertTrue(contract_gate["authorization_artifact_required"])
        self.assertFalse(contract_gate["authorization_artifact_implemented"])
        self.assertFalse(contract_gate["authorization_artifact_created"])
        self.assertFalse(contract_gate["authorization_artifact_persisted"])
        self.assertFalse(contract_gate["authorization_id_created"])
        self.assertFalse(contract_gate["authorization_registry_created"])
        self.assertFalse(contract_gate["authorization_granted"])
        self.assertFalse(contract_gate["authorization_consumed"])
        self.assertFalse(contract_gate["execution_authorized"])
        self.assertFalse(contract_gate["registration_authorized"])
        self.assertFalse(contract_gate["registration_performed"])
        self.assertFalse(contract_gate["record_set_written"])
        self.assertEqual(contract_gate["writes_performed"], 0)
        self.assertIn("dry_run_evidence_identity", contract_gate["future_authorization_artifact_required_fields"])
        self.assertIn("exact current transaction-plan fingerprint", contract_gate["future_authorization_binding_requirements"])
        self.assertIn("maximum_registration_attempts = 1", contract_gate["future_authorization_scope_requirements"])
        self.assertIn("single-use", contract_gate["future_authorization_single_use_requirements"])
        self.assertIn("dry-run no longer passing", contract_gate["future_authorization_invalidation_conditions"])
        self.assertIn("confirm exact confirmation match", contract_gate["future_pre_authorization_revalidation"])
        self.assertIn("authorization artifact integrity", contract_gate["future_pre_write_revalidation"])
        self.assertIn("dry_run_failed", contract_gate["future_authorization_failure_states"])
        self.assertIn("authorization artifact identity", contract_gate["future_authorization_receipt_requirements"])
        self.assertTrue(contract_gate["planned_future_authorization_sequence"])
        self.assertIn("dry_run_evidence_identity_not_yet_implemented", contract_gate["warnings"])
        self.assertIn("dry_run_evidence_identity_not_yet_implemented", contract_report)

        self.assertEqual(stale_contract["status"], "stale")
        self.assertFalse(stale_contract["ready_to_design_future_authorization_artifact"])
        self.assertEqual(modified_contract["status"], "modified")
        self.assertFalse(modified_contract["ready_to_design_future_authorization_artifact"])
        self.assertEqual(conflict_contract["status"], "target_conflict")
        self.assertFalse(conflict_contract["ready_to_design_future_authorization_artifact"])
        self.assertEqual(unknown_contract["status"], "target_state_unknown")
        self.assertFalse(unknown_contract["ready_to_design_future_authorization_artifact"])
        self.assertEqual(dry_run_failed_contract["status"], "dry_run_failed")
        self.assertIn("synthetic_dry_run_failure", dry_run_failed_contract["blockers"])
        self.assertEqual(wrong_write_function_contract["status"], "blocked")
        self.assertEqual(wrong_write_count_contract["status"], "blocked")

        contract_report_lower = contract_report.lower()
        for forbidden_text in (
            '"expected_outcome"',
            '"records"',
            "c:\\users\\",
            "/users/",
            "/home/",
            "traceback",
            "stack trace",
            "caller confirmation",
        ):
            self.assertNotIn(forbidden_text, contract_report_lower)
        for forbidden_key in (
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
            "registration_confidence_score",
            "execution_safety_score",
            "transaction_success_probability",
            "authorization_confidence_score",
            "confirmation_confidence_score",
        ):
            self.assertNotIn(forbidden_key, json.dumps(contract_gate, sort_keys=True))
            self.assertNotIn(forbidden_key, contract_report)
        for required_phrase in (
            "Phase 15A is backend-only, read-only, deterministic, non-executing, and non-persistent.",
            "Phase 15A does not authorize execution or registration.",
            "The current idempotency preview remains non-authoritative and unenforced.",
            "Future execution authorization must require authoritative idempotency enforcement before any write.",
            "No factual truth correctness",
        ):
            self.assertIn(required_phrase, contract_report)

        doc_path = Path(
            "docs/PHASE_15A_CONTROLLED_REGISTRATION_TRANSACTION_EXECUTION_AUTHORIZATION_CONFIRMATION_CONTRACT_GATE.md"
        )
        self.assertTrue(doc_path.exists())
        doc_text = doc_path.read_text(encoding="utf-8")
        for required_phrase in (
            "Phase 15A defines a backend-only, read-only authorization/confirmation contract gate.",
            "REGISTER_OUTCOME_TRUTH_RECORD_SET",
            "The gate is design-ready only.",
            "It does not create an authorization artifact.",
            "It does not accept or enforce confirmation.",
            "It does not authorize execution or registration.",
            "The current idempotency preview remains non-authoritative and unenforced.",
            "Recommended next phase: Phase 15B.",
        ):
            self.assertIn(required_phrase, doc_text)

    def test_controlled_registration_authorization_artifact_preview_and_confirmation_dry_run_are_deterministic_read_only_and_non_authoritative(self) -> None:
        preview_builder = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_authorization_artifact_preview
        preview_reporter = truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_authorization_artifact_preview_report
        confirmation_runner = truth.run_deployed_rule_outcome_truth_record_set_controlled_registration_confirmation_dry_run
        confirmation_reporter = truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_confirmation_dry_run_report

        for function in (preview_builder, preview_reporter, confirmation_runner, confirmation_reporter):
            self.assertTrue(callable(function))

        preview_source = inspect.getsource(preview_builder)
        preview_report_source = inspect.getsource(preview_reporter)
        confirmation_source = inspect.getsource(confirmation_runner)
        confirmation_report_source = inspect.getsource(confirmation_reporter)
        helper_source = inspect.getsource(truth._compute_controlled_registration_dry_run_evidence_fingerprint)
        preview_fingerprint_source = inspect.getsource(
            truth._compute_controlled_registration_authorization_artifact_preview_fingerprint
        )
        confirmation_fingerprint_source = inspect.getsource(
            truth._compute_controlled_registration_confirmation_evidence_fingerprint
        )
        for source in (
            preview_source,
            preview_report_source,
            confirmation_source,
            confirmation_report_source,
            helper_source,
            preview_fingerprint_source,
            confirmation_fingerprint_source,
        ):
            for forbidden_call in (
                "register_deployed_rule_outcome_truth_record_set(",
                "build_deployed_rule_outcome_truth_source_plan(",
                "record_deployed_rule_outcome_truth_source_result(",
                "_ensure_dirs(",
                "json.dump(",
                "write_text(",
                "_atomic_write_json(",
                "uuid.uuid4",
                "random.",
                "time.time",
                "datetime.now",
                "datetime.utcnow",
                "tempfile",
                "Path.mkdir",
                "os.makedirs",
                "confirmation_text in ",
            ):
                self.assertNotIn(forbidden_call, source)
        self.assertIn(
            "build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate(",
            preview_source,
        )
        self.assertIn(
            "build_deployed_rule_outcome_truth_record_set_controlled_registration_authorization_artifact_preview(",
            confirmation_source,
        )

        preview_signature = inspect.signature(preview_builder)
        preview_report_signature = inspect.signature(preview_reporter)
        confirmation_signature = inspect.signature(confirmation_runner)
        confirmation_report_signature = inspect.signature(confirmation_reporter)
        self.assertEqual(
            tuple(preview_signature.parameters),
            ("transaction_plan", "backend_plan", "candidate_record_set", "root"),
        )
        self.assertEqual(
            tuple(preview_report_signature.parameters),
            ("transaction_plan", "backend_plan", "candidate_record_set", "root"),
        )
        self.assertEqual(
            tuple(confirmation_signature.parameters),
            ("authorization_artifact_preview", "confirmation_text", "transaction_plan", "backend_plan", "candidate_record_set", "root"),
        )
        self.assertEqual(
            tuple(confirmation_report_signature.parameters),
            ("authorization_artifact_preview", "confirmation_text", "transaction_plan", "backend_plan", "candidate_record_set", "root"),
        )
        for signature in (preview_signature, preview_report_signature):
            self.assertNotIn("confirmation_text", signature.parameters)
            self.assertNotIn("confirmation", signature.parameters)
        for signature in (confirmation_signature, confirmation_report_signature):
            for forbidden_parameter in (
                "confirmation_matched",
                "confirmation_accepted",
                "confirmation_enforced",
                "authorization_artifact_id",
                "authorization_id",
                "authorization_granted",
                "authorization_consumed",
                "authorization_scope_override",
                "dry_run_result",
                "binding_result",
                "idempotency_key",
                "authoritative_idempotency_key",
                "execution_authorized",
                "registration_authorized",
                "transaction_id",
                "receipt_id",
                "execute",
                "commit",
                "register",
                "force",
                "override",
                "repair",
                "migrate",
                "score",
                "ranking",
                "aggregate",
            ):
                self.assertNotIn(forbidden_parameter, signature.parameters)

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            valid_root = root / "valid"
            identity = _write_telemetry_snapshot_fixture(valid_root)
            candidate = {
                **identity,
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
            reordered_candidate = {
                "records": deepcopy(candidate["records"]),
                "source_authority_class": candidate["source_authority_class"],
                "source_type": candidate["source_type"],
                "source_id": candidate["source_id"],
                "observation_window_end": candidate["observation_window_end"],
                "observation_window_start": candidate["observation_window_start"],
                "telemetry_snapshot_id": candidate["telemetry_snapshot_id"],
                "deployed_rule_id": candidate["deployed_rule_id"],
                "production_target_id": candidate["production_target_id"],
                "production_deployment_result_id": candidate["production_deployment_result_id"],
                "canonical_rule_id": candidate["canonical_rule_id"],
            }
            backend_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan(
                deepcopy(candidate),
                root=valid_root,
            )
            transaction_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan(
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )
            candidate_before = deepcopy(candidate)
            backend_plan_before = deepcopy(backend_plan)
            transaction_plan_before = deepcopy(transaction_plan)
            before_valid = sorted(str(path.relative_to(valid_root)) for path in valid_root.rglob("*"))

            preview_one = preview_builder(transaction_plan, backend_plan, candidate, root=valid_root)
            preview_two = preview_builder(deepcopy(transaction_plan), deepcopy(backend_plan), deepcopy(candidate), root=valid_root)
            preview_reordered = preview_builder(transaction_plan, backend_plan, reordered_candidate, root=valid_root)
            preview_report = preview_reporter(transaction_plan, backend_plan, candidate, root=valid_root)

            exact_confirmation = confirmation_runner(
                preview_one,
                truth.REGISTER_CONFIRMATION,
                transaction_plan,
                backend_plan,
                candidate,
                root=valid_root,
            )
            exact_confirmation_repeat = confirmation_runner(
                deepcopy(preview_one),
                truth.REGISTER_CONFIRMATION,
                deepcopy(transaction_plan),
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )
            lowercase_confirmation = confirmation_runner(
                preview_one,
                truth.REGISTER_CONFIRMATION.lower(),
                transaction_plan,
                backend_plan,
                candidate,
                root=valid_root,
            )
            leading_whitespace_confirmation = confirmation_runner(
                preview_one,
                " " + truth.REGISTER_CONFIRMATION,
                transaction_plan,
                backend_plan,
                candidate,
                root=valid_root,
            )
            trailing_whitespace_confirmation = confirmation_runner(
                preview_one,
                truth.REGISTER_CONFIRMATION + " ",
                transaction_plan,
                backend_plan,
                candidate,
                root=valid_root,
            )
            newline_confirmation = confirmation_runner(
                preview_one,
                truth.REGISTER_CONFIRMATION + "\n",
                transaction_plan,
                backend_plan,
                candidate,
                root=valid_root,
            )
            prefix_confirmation = confirmation_runner(
                preview_one,
                "X" + truth.REGISTER_CONFIRMATION,
                transaction_plan,
                backend_plan,
                candidate,
                root=valid_root,
            )
            suffix_confirmation = confirmation_runner(
                preview_one,
                truth.REGISTER_CONFIRMATION + "X",
                transaction_plan,
                backend_plan,
                candidate,
                root=valid_root,
            )
            empty_confirmation = confirmation_runner(
                preview_one,
                "",
                transaction_plan,
                backend_plan,
                candidate,
                root=valid_root,
            )
            confirmation_report = confirmation_reporter(
                preview_one,
                truth.REGISTER_CONFIRMATION,
                transaction_plan,
                backend_plan,
                candidate,
                root=valid_root,
            )

            stale_candidate = deepcopy(candidate)
            stale_candidate["records"][0]["actual_or_adjudicated_outcome"] = "mars_day"
            stale_preview = preview_builder(transaction_plan, backend_plan, stale_candidate, root=valid_root)
            stale_confirmation = confirmation_runner(
                stale_preview,
                truth.REGISTER_CONFIRMATION,
                transaction_plan,
                backend_plan,
                stale_candidate,
                root=valid_root,
            )

            modified_transaction_plan = deepcopy(transaction_plan)
            modified_transaction_plan["transaction_plan_fingerprint"] = "sha256:" + ("2" * 64)
            modified_preview = preview_builder(modified_transaction_plan, backend_plan, candidate, root=valid_root)
            modified_confirmation = confirmation_runner(
                modified_preview,
                truth.REGISTER_CONFIRMATION,
                modified_transaction_plan,
                backend_plan,
                candidate,
                root=valid_root,
            )

            modified_preview_payload = deepcopy(preview_one)
            modified_preview_payload["maximum_registration_attempts"] = 2
            modified_preview_confirmation = confirmation_runner(
                modified_preview_payload,
                truth.REGISTER_CONFIRMATION,
                transaction_plan,
                backend_plan,
                candidate,
                root=valid_root,
            )

            original_contract_gate = (
                truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate
            )
            base_contract_gate = original_contract_gate(transaction_plan, backend_plan, candidate, root=valid_root)
            try:
                def _stale_gate(*args, **kwargs):
                    payload = deepcopy(base_contract_gate)
                    payload["status"] = "stale"
                    payload["ready_to_design_future_authorization_artifact"] = False
                    payload["target_state_observation_available"] = False
                    payload["blockers"] = ["synthetic_stale_gate"]
                    return payload

                truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate = _stale_gate
                stale_precedence_preview = preview_builder(transaction_plan, backend_plan, candidate, root=valid_root)

                def _modified_gate(*args, **kwargs):
                    payload = deepcopy(base_contract_gate)
                    payload["status"] = "modified"
                    payload["ready_to_design_future_authorization_artifact"] = False
                    payload["target_state_observation_available"] = False
                    payload["blockers"] = ["synthetic_modified_gate"]
                    return payload

                truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate = _modified_gate
                modified_precedence_preview = preview_builder(transaction_plan, backend_plan, candidate, root=valid_root)

                def _conflict_gate(*args, **kwargs):
                    payload = deepcopy(base_contract_gate)
                    payload["status"] = "target_conflict"
                    payload["ready_to_design_future_authorization_artifact"] = False
                    payload["target_conflict_detected"] = True
                    payload["target_state_observation_available"] = False
                    payload["blockers"] = ["synthetic_conflict_gate"]
                    return payload

                truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate = _conflict_gate
                conflict_precedence_preview = preview_builder(transaction_plan, backend_plan, candidate, root=valid_root)

                def _unknown_gate(*args, **kwargs):
                    payload = deepcopy(base_contract_gate)
                    payload["status"] = "target_state_unknown"
                    payload["ready_to_design_future_authorization_artifact"] = False
                    payload["target_state_observation_available"] = False
                    payload["blockers"] = ["synthetic_unknown_gate"]
                    return payload

                truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate = _unknown_gate
                unknown_precedence_preview = preview_builder(transaction_plan, backend_plan, candidate, root=valid_root)
                unknown_precedence_confirmation = confirmation_runner(
                    unknown_precedence_preview,
                    truth.REGISTER_CONFIRMATION,
                    transaction_plan,
                    backend_plan,
                    candidate,
                    root=valid_root,
                )
            finally:
                truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate = original_contract_gate

            original_dry_run = truth.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run
            try:
                def _failed_dry_run(*args, **kwargs):
                    payload = deepcopy(original_dry_run(*args, **kwargs))
                    payload["status"] = "blocked"
                    payload["dry_run_passed"] = False
                    payload["blockers"] = ["synthetic_dry_run_failure"]
                    return payload

                truth.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run = _failed_dry_run
                failed_dry_run_preview = preview_builder(transaction_plan, backend_plan, candidate, root=valid_root)
            finally:
                truth.run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run = original_dry_run

            original_binding = truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding
            base_binding = original_binding(transaction_plan, backend_plan, candidate, root=valid_root)
            try:
                def _unknown_binding(*args, **kwargs):
                    payload = deepcopy(base_binding)
                    payload["status"] = "target_state_unknown"
                    payload["target_state_observation_available"] = False
                    payload["target_state_binding_valid"] = False
                    payload["target_state_freshness_status"] = "unknown"
                    payload["target_state_freshness_proven"] = False
                    payload["current_target_state"] = "target_state_unknown"
                    payload["blockers"] = ["target_state_unknown"]
                    return payload

                truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding = _unknown_binding
                unknown_preview = preview_builder(transaction_plan, backend_plan, candidate, root=valid_root)

                def _conflict_binding(*args, **kwargs):
                    payload = deepcopy(base_binding)
                    payload["status"] = "target_conflict"
                    payload["target_conflict_detected"] = True
                    payload["current_target_state"] = "target_present_conflicting"
                    payload["blockers"] = ["transaction_target_conflict"]
                    return payload

                truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding = _conflict_binding
                conflict_preview = preview_builder(transaction_plan, backend_plan, candidate, root=valid_root)
            finally:
                truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding = original_binding

            changed_target_candidate = deepcopy(candidate)
            changed_target_candidate["source_id"] = "source-2"
            changed_target_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan(
                deepcopy(backend_plan),
                deepcopy(changed_target_candidate),
                root=valid_root,
            )
            changed_target_preview = preview_builder(changed_target_plan, backend_plan, changed_target_candidate, root=valid_root)

            changed_idempotency_plan = deepcopy(transaction_plan)
            changed_idempotency_plan["idempotency_key_preview"] = "sha256:" + ("3" * 64)
            changed_idempotency_preview = preview_builder(changed_idempotency_plan, backend_plan, candidate, root=valid_root)

            changed_backend_plan = deepcopy(backend_plan)
            changed_backend_plan["backend_plan_fingerprint"] = "sha256:" + ("4" * 64)
            changed_backend_preview = preview_builder(transaction_plan, changed_backend_plan, candidate, root=valid_root)

            changed_candidate = deepcopy(candidate)
            changed_candidate["records"][0]["expected_outcome"] = "mars_day"
            changed_candidate_preview = preview_builder(transaction_plan, backend_plan, changed_candidate, root=valid_root)

            after_valid = sorted(str(path.relative_to(valid_root)) for path in valid_root.rglob("*"))

        self.assertEqual(candidate, candidate_before)
        self.assertEqual(backend_plan, backend_plan_before)
        self.assertEqual(transaction_plan, transaction_plan_before)
        self.assertEqual(preview_one, preview_one)
        self.assertEqual(before_valid, after_valid)

        self.assertEqual(preview_one["status"], "preview_ready")
        self.assertTrue(preview_one["authorization_artifact_preview_ready"])
        self.assertFalse(preview_one["authorization_artifact_preview_authoritative"])
        self.assertFalse(preview_one["authorization_artifact_preview_persisted"])
        self.assertFalse(preview_one["authorization_artifact_created"])
        self.assertFalse(preview_one["authorization_artifact_persisted"])
        self.assertFalse(preview_one["authorization_id_created"])
        self.assertFalse(preview_one["authorization_registry_created"])
        self.assertFalse(preview_one["authorization_granted"])
        self.assertFalse(preview_one["authorization_consumed"])
        self.assertFalse(preview_one["execution_authorized"])
        self.assertFalse(preview_one["registration_authorized"])
        self.assertFalse(preview_one["registration_performed"])
        self.assertFalse(preview_one["record_set_written"])
        self.assertEqual(preview_one["maximum_registration_attempts"], 1)
        self.assertTrue(preview_one["single_use_required"])
        self.assertEqual(preview_one["planned_write_function"], "register_deployed_rule_outcome_truth_record_set")
        self.assertEqual(preview_one["planned_write_count"], 1)
        self.assertTrue(preview_one["dry_run_evidence_fingerprint"])
        self.assertTrue(preview_one["authorization_artifact_preview_fingerprint"])
        self.assertEqual(preview_one["dry_run_evidence_fingerprint_algorithm"], "sha256")
        self.assertEqual(preview_one["authorization_artifact_preview_fingerprint_algorithm"], "sha256")
        self.assertTrue(preview_one["dry_run_evidence_deterministic"])
        self.assertTrue(preview_one["authorization_artifact_preview_deterministic"])
        self.assertTrue(preview_one["authorization_artifact_preview_public_safe"])
        self.assertEqual(preview_one["required_confirmation"], truth.REGISTER_CONFIRMATION)
        self.assertEqual(preview_one["confirmation_match_policy"]["match_type"], "exact_literal")
        self.assertTrue(preview_one["confirmation_match_policy"]["case_sensitive"])
        self.assertFalse(preview_one["confirmation_match_policy"]["trim_before_compare"])
        self.assertEqual(preview_one["confirmation_match_policy"]["unicode_normalization"], "none")
        self.assertFalse(preview_one["confirmation_match_policy"]["substring_match_allowed"])
        self.assertFalse(preview_one["confirmation_match_policy"]["implicit_confirmation_allowed"])
        self.assertEqual(preview_one["dry_run_evidence_fingerprint"], preview_two["dry_run_evidence_fingerprint"])
        self.assertEqual(preview_one["authorization_artifact_preview_fingerprint"], preview_two["authorization_artifact_preview_fingerprint"])
        self.assertEqual(preview_one["dry_run_evidence_fingerprint"], preview_reordered["dry_run_evidence_fingerprint"])
        self.assertEqual(preview_one["authorization_artifact_preview_fingerprint"], preview_reordered["authorization_artifact_preview_fingerprint"])
        self.assertEqual(
            (preview_one["authorization_scope_preview"] or {}).get("scope_type"),
            "single_controlled_outcome_truth_record_set_registration_attempt",
        )
        self.assertEqual(
            (preview_one["authorization_scope_preview"] or {}).get("maximum_registration_attempts"),
            1,
        )
        self.assertTrue((preview_one["authorization_scope_preview"] or {}).get("single_use_required"))
        self.assertFalse((preview_one["authorization_scope_preview"] or {}).get("repair_authority"))
        self.assertFalse((preview_one["authorization_scope_preview"] or {}).get("migration_authority"))
        self.assertFalse((preview_one["authorization_scope_preview"] or {}).get("scoring_authority"))
        self.assertFalse((preview_one["authorization_scope_preview"] or {}).get("rollback_authority"))

        self.assertEqual(exact_confirmation["status"], "confirmation_match")
        self.assertTrue(exact_confirmation["confirmation_supplied"])
        self.assertTrue(exact_confirmation["confirmation_exact_match"])
        self.assertFalse(exact_confirmation["confirmation_accepted"])
        self.assertFalse(exact_confirmation["confirmation_enforced"])
        self.assertFalse(exact_confirmation["authorization_granted"])
        self.assertFalse(exact_confirmation["execution_authorized"])
        self.assertFalse(exact_confirmation["registration_authorized"])
        self.assertFalse(exact_confirmation["would_call_registration_function"])
        self.assertEqual(exact_confirmation["writes_performed"], 0)
        self.assertTrue(exact_confirmation["authorization_artifact_preview_integrity_valid"])
        self.assertTrue(exact_confirmation["authorization_artifact_preview_fingerprint_valid"])
        self.assertTrue(exact_confirmation["dry_run_evidence_fingerprint_valid"])
        self.assertTrue(exact_confirmation["confirmation_evidence_fingerprint"])
        self.assertEqual(
            exact_confirmation["confirmation_evidence_fingerprint"],
            exact_confirmation_repeat["confirmation_evidence_fingerprint"],
        )
        self.assertEqual(lowercase_confirmation["status"], "confirmation_mismatch")
        self.assertTrue(lowercase_confirmation["confirmation_supplied"])
        self.assertFalse(lowercase_confirmation["confirmation_exact_match"])
        self.assertEqual(leading_whitespace_confirmation["status"], "confirmation_mismatch")
        self.assertFalse(leading_whitespace_confirmation["confirmation_exact_match"])
        self.assertEqual(trailing_whitespace_confirmation["status"], "confirmation_mismatch")
        self.assertFalse(trailing_whitespace_confirmation["confirmation_exact_match"])
        self.assertEqual(newline_confirmation["status"], "confirmation_mismatch")
        self.assertFalse(newline_confirmation["confirmation_exact_match"])
        self.assertEqual(prefix_confirmation["status"], "confirmation_mismatch")
        self.assertFalse(prefix_confirmation["confirmation_exact_match"])
        self.assertEqual(suffix_confirmation["status"], "confirmation_mismatch")
        self.assertFalse(suffix_confirmation["confirmation_exact_match"])
        self.assertEqual(empty_confirmation["status"], "confirmation_missing")
        self.assertFalse(empty_confirmation["confirmation_supplied"])
        self.assertFalse(empty_confirmation["confirmation_exact_match"])
        self.assertNotEqual(
            exact_confirmation["confirmation_evidence_fingerprint"],
            lowercase_confirmation["confirmation_evidence_fingerprint"],
        )

        self.assertEqual(stale_preview["status"], "stale")
        self.assertEqual(stale_confirmation["status"], "stale")
        self.assertEqual(modified_preview["status"], "modified")
        self.assertEqual(modified_confirmation["status"], "modified")
        self.assertEqual(unknown_preview["status"], "target_state_unknown")
        self.assertEqual(conflict_preview["status"], "target_conflict")
        self.assertEqual(failed_dry_run_preview["status"], "dry_run_failed")
        self.assertIn("synthetic_dry_run_failure", failed_dry_run_preview["blockers"])
        self.assertEqual(stale_precedence_preview["status"], "stale")
        self.assertEqual(modified_precedence_preview["status"], "modified")
        self.assertEqual(conflict_precedence_preview["status"], "target_conflict")
        self.assertEqual(unknown_precedence_preview["status"], "target_state_unknown")
        self.assertEqual(unknown_precedence_confirmation["status"], "target_state_unknown")
        self.assertEqual(modified_preview_confirmation["status"], "preview_invalid")
        self.assertFalse(modified_preview_confirmation["authorization_artifact_preview_integrity_valid"])
        self.assertFalse(modified_preview_confirmation["authorization_artifact_preview_fingerprint_valid"])
        self.assertIn("authorization_artifact_preview_fingerprint_mismatch", modified_preview_confirmation["blockers"])

        self.assertNotEqual(preview_one["authorization_artifact_preview_fingerprint"], changed_target_preview["authorization_artifact_preview_fingerprint"])
        self.assertNotEqual(preview_one["dry_run_evidence_fingerprint"], changed_target_preview["dry_run_evidence_fingerprint"])
        self.assertEqual(changed_idempotency_preview["status"], "modified")
        self.assertEqual(changed_backend_preview["status"], "modified")
        self.assertEqual(changed_candidate_preview["status"], "stale")

        for forbidden_key in (
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
            "registration_confidence_score",
            "execution_safety_score",
            "transaction_success_probability",
            "authorization_confidence_score",
            "confirmation_confidence_score",
            "authorization_probability",
        ):
            self.assertNotIn(forbidden_key, json.dumps(preview_one, sort_keys=True))
            self.assertNotIn(forbidden_key, json.dumps(exact_confirmation, sort_keys=True))
            self.assertNotIn(forbidden_key, preview_report)
            self.assertNotIn(forbidden_key, confirmation_report)

        preview_report_lower = preview_report.lower()
        confirmation_report_lower = confirmation_report.lower()
        for report_lower in (preview_report_lower, confirmation_report_lower):
            self.assertNotIn('"expected_outcome"', report_lower)
            self.assertNotIn('"records"', report_lower)
            self.assertNotIn("c:\\users\\", report_lower)
            self.assertNotIn("/users/", report_lower)
            self.assertNotIn("/home/", report_lower)
            self.assertNotIn("traceback", report_lower)
            self.assertNotIn("stack trace", report_lower)
        self.assertIn(truth.REGISTER_CONFIRMATION, preview_report)
        self.assertIn(truth.REGISTER_CONFIRMATION, confirmation_report)
        self.assertIn("Limitations:", preview_report)
        self.assertIn("Limitations:", confirmation_report)
        self.assertIn("Phase 15B builds a deterministic non-authoritative authorization-artifact preview", preview_report)
        self.assertIn("The confirmation dry run may evaluate whether supplied text exactly matches REGISTER_OUTCOME_TRUTH_RECORD_SET.", confirmation_report)
        self.assertIn("Exact confirmation match was evaluated in a dry run only. No authorization was created or granted.", confirmation_report)

        self.assertEqual(candidate, candidate_before)
        self.assertEqual(backend_plan, backend_plan_before)
        self.assertEqual(transaction_plan, transaction_plan_before)
        self.assertEqual(before_valid, after_valid)

        doc_path = Path(
            "docs/PHASE_15B_CONTROLLED_REGISTRATION_AUTHORIZATION_ARTIFACT_PREVIEW_CONFIRMATION_DRY_RUN_CONTRACT.md"
        )
        self.assertTrue(doc_path.exists())
        doc_text = doc_path.read_text(encoding="utf-8")
        for required_heading in (
            "## 1. Purpose",
            "## 2. Scope",
            "## 3. Phase 15A Prerequisite",
            "## 4. Backend Functions",
            "## 5. Authorization-Preview Inputs",
            "## 6. Authorization-Preview Output",
            "## 7. Dry-Run Evidence Identity",
            "## 8. Authorization Scope Preview",
            "## 9. Authorization-Preview Fingerprint",
            "## 10. Confirmation Dry-Run Inputs",
            "## 11. Exact Confirmation Comparison",
            "## 12. Confirmation Dry-Run Output",
            "## 13. Confirmation Evidence Fingerprint",
            "## 14. Status Precedence",
            "## 15. Stale, Modified, Unknown, and Conflict Behavior",
            "## 16. Idempotency Boundary",
            "## 17. Preview and Confirmation Match Versus Authorization",
            "## 18. Read-Only / Non-Persistent Boundary",
            "## 19. Public-Safe Report Limits",
            "## 20. Explicit Non-Claims",
            "## 21. Exact Test Command",
            "## 22. Known Risks",
            "## 23. Recommended Next Phase",
        ):
            self.assertIn(required_heading, doc_text)
        for required_phrase in (
            "Phase 15B builds a deterministic non-authoritative authorization-artifact preview and evaluates confirmation matching through a read-only dry run.",
            "Phase 15B does not create an authorization artifact.",
            "Phase 15B does not persist an authorization preview.",
            "Phase 15B does not grant execution authorization.",
            "Phase 15B does not grant registration authorization.",
            "Phase 15B does not accept or enforce confirmation.",
            "The confirmation dry run may evaluate whether supplied text exactly matches REGISTER_OUTCOME_TRUTH_RECORD_SET.",
            "Exact matching is case-sensitive and performs no trimming, normalization, substring matching, prefix matching, suffix matching, or implicit confirmation.",
            "An exact confirmation match is dry-run evidence only.",
            "It is not accepted confirmation.",
            "It is not enforced confirmation.",
            "It is not an authorization grant.",
            "The caller-supplied confirmation text is not persisted, echoed, or included in public-safe reports.",
            "The dry-run evidence fingerprint identifies stable structural dry-run evidence only.",
            "The authorization-preview fingerprint identifies the deterministic preview contract only.",
            "Neither fingerprint is an authorization ID.",
            "Neither fingerprint grants authority.",
            "The idempotency-key preview remains non-authoritative, unpersisted, unreserved, and unenforced.",
            "planned_write_count = 1 describes future intent only.",
            "writes_performed = 0 records actual Phase 15B behavior.",
            "Stale, modified, or conflicting status must take precedence over target_state_unknown.",
            "Confirmation match must not override any failed prerequisite.",
            "A valid fingerprint proves integrity against the defined canonical representation only.",
            "It does not prove factual correctness of outcome-truth records.",
            "Phase 15C — Controlled Registration Authorization-Preview Identity, Confirmation-Evidence Binding, and Stale-Preview Gate",
        ):
            self.assertIn(required_phrase, doc_text)
    def test_controlled_registration_authorization_preview_identity_confirmation_evidence_binding_and_stale_preview_gate_is_deterministic_read_only_and_non_authoritative(self) -> None:
        validator = truth.validate_deployed_rule_outcome_truth_record_set_controlled_registration_authorization_preview_confirmation_evidence_binding
        reporter = truth.format_deployed_rule_outcome_truth_record_set_controlled_registration_authorization_preview_confirmation_evidence_binding_report
        self.assertTrue(callable(validator))
        self.assertTrue(callable(reporter))
        self.assertEqual(
            tuple(inspect.signature(validator).parameters),
            (
                "authorization_artifact_preview",
                "confirmation_dry_run_result",
                "confirmation_text",
                "transaction_plan",
                "backend_plan",
                "candidate_record_set",
                "root",
            ),
        )
        self.assertEqual(
            tuple(inspect.signature(reporter).parameters),
            (
                "authorization_artifact_preview",
                "confirmation_dry_run_result",
                "confirmation_text",
                "transaction_plan",
                "backend_plan",
                "candidate_record_set",
                "root",
            ),
        )
        validator_source = inspect.getsource(validator)
        reporter_source = inspect.getsource(reporter)
        for source in (validator_source, reporter_source):
            for forbidden_call in (
                "register_deployed_rule_outcome_truth_record_set(",
                "build_deployed_rule_outcome_truth_source_plan(",
                "record_deployed_rule_outcome_truth_source_result(",
                "_ensure_dirs(",
                "json.dump(",
                "write_text(",
                "_atomic_write_json(",
                "Path.mkdir",
                "os.makedirs",
                "open(",
                "uuid.uuid4",
                "random.",
                "time.time",
                "datetime.now",
                "datetime.utcnow",
                "tempfile",
                "hash(",
            ):
                self.assertNotIn(forbidden_call, source)
        self.assertIn(
            "build_deployed_rule_outcome_truth_record_set_controlled_registration_authorization_artifact_preview(",
            validator_source,
        )
        self.assertIn(
            "run_deployed_rule_outcome_truth_record_set_controlled_registration_confirmation_dry_run(",
            validator_source,
        )

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            valid_root = root / "valid"
            identity = _write_telemetry_snapshot_fixture(valid_root)
            candidate = {
                **identity,
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
            backend_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan(
                deepcopy(candidate),
                root=valid_root,
            )
            transaction_plan = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan(
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )
            preview = truth.build_deployed_rule_outcome_truth_record_set_controlled_registration_authorization_artifact_preview(
                deepcopy(transaction_plan),
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )
            confirmation = truth.run_deployed_rule_outcome_truth_record_set_controlled_registration_confirmation_dry_run(
                deepcopy(preview),
                truth.REGISTER_CONFIRMATION,
                deepcopy(transaction_plan),
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )
            candidate_before = deepcopy(candidate)
            backend_before = deepcopy(backend_plan)
            transaction_before = deepcopy(transaction_plan)
            preview_before = deepcopy(preview)
            confirmation_before = deepcopy(confirmation)
            before_tree = sorted(str(path.relative_to(valid_root)) for path in valid_root.rglob("*"))

            valid_binding = validator(
                deepcopy(preview),
                deepcopy(confirmation),
                truth.REGISTER_CONFIRMATION,
                deepcopy(transaction_plan),
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )
            valid_report = reporter(
                deepcopy(preview),
                deepcopy(confirmation),
                truth.REGISTER_CONFIRMATION,
                deepcopy(transaction_plan),
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )

            modified_preview = deepcopy(preview)
            modified_preview["planned_write_count"] = 2
            modified_binding = validator(
                modified_preview,
                deepcopy(confirmation),
                truth.REGISTER_CONFIRMATION,
                deepcopy(transaction_plan),
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )

            changed_candidate = deepcopy(candidate)
            changed_candidate["records"][0]["actual_or_adjudicated_outcome"] = "mars_day"
            stale_binding = validator(
                deepcopy(preview),
                deepcopy(confirmation),
                truth.REGISTER_CONFIRMATION,
                deepcopy(transaction_plan),
                deepcopy(backend_plan),
                changed_candidate,
                root=valid_root,
            )

            modified_confirmation = deepcopy(confirmation)
            modified_confirmation["confirmation_exact_match"] = False
            modified_confirmation_binding = validator(
                deepcopy(preview),
                modified_confirmation,
                truth.REGISTER_CONFIRMATION,
                deepcopy(transaction_plan),
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )
            missing_confirmation_binding = validator(
                deepcopy(preview),
                deepcopy(confirmation),
                "",
                deepcopy(transaction_plan),
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )
            malformed_text_binding = validator(
                deepcopy(preview),
                deepcopy(confirmation),
                3,
                deepcopy(transaction_plan),
                deepcopy(backend_plan),
                deepcopy(candidate),
                root=valid_root,
            )
            after_tree = sorted(str(path.relative_to(valid_root)) for path in valid_root.rglob("*"))

        self.assertEqual(candidate, candidate_before)
        self.assertEqual(backend_plan, backend_before)
        self.assertEqual(transaction_plan, transaction_before)
        self.assertEqual(preview, preview_before)
        self.assertEqual(confirmation, confirmation_before)
        self.assertEqual(before_tree, after_tree)

        self.assertEqual(valid_binding["status"], "confirmation_match")
        self.assertTrue(valid_binding["authorization_preview_binding_valid"])
        self.assertTrue(valid_binding["authorization_preview_integrity_valid"])
        self.assertTrue(valid_binding["authorization_preview_fingerprint_valid"])
        self.assertTrue(valid_binding["authorization_preview_current_binding_valid"])
        self.assertTrue(valid_binding["candidate_binding_valid"])
        self.assertTrue(valid_binding["planning_gate_binding_valid"])
        self.assertTrue(valid_binding["backend_plan_binding_valid"])
        self.assertTrue(valid_binding["transaction_plan_binding_valid"])
        self.assertTrue(valid_binding["target_identity_binding_valid"])
        self.assertTrue(valid_binding["target_state_snapshot_binding_valid"])
        self.assertTrue(valid_binding["target_state_observation_available"])
        self.assertTrue(valid_binding["target_state_freshness_proven"])
        self.assertTrue(valid_binding["dry_run_evidence_binding_valid"])
        self.assertTrue(valid_binding["idempotency_preview_binding_valid"])
        self.assertTrue(valid_binding["authorization_scope_binding_valid"])
        self.assertTrue(valid_binding["confirmation_contract_binding_valid"])
        self.assertTrue(valid_binding["confirmation_dry_run_integrity_valid"])
        self.assertTrue(valid_binding["confirmation_dry_run_current_binding_valid"])
        self.assertTrue(valid_binding["confirmation_evidence_binding_valid"])
        self.assertTrue(valid_binding["confirmation_evidence_fingerprint_valid"])
        self.assertTrue(valid_binding["confirmation_supplied"])
        self.assertTrue(valid_binding["confirmation_exact_match"])
        self.assertFalse(valid_binding["would_call_registration_function"])
        self.assertEqual(valid_binding["writes_performed"], 0)

        self.assertEqual(modified_binding["status"], "modified_preview")
        self.assertTrue(modified_binding["modified_preview_detected"])
        self.assertFalse(modified_binding["authorization_preview_binding_valid"])
        self.assertIn("authorization_artifact_preview_fingerprint_mismatch", modified_binding["blockers"])

        self.assertEqual(stale_binding["status"], "stale_candidate")
        self.assertFalse(stale_binding["candidate_binding_valid"])
        self.assertTrue(stale_binding["stale_preview_detected"])
        self.assertIn("candidate_binding_mismatch", stale_binding["blockers"])

        self.assertEqual(modified_confirmation_binding["status"], "modified_confirmation_evidence")
        self.assertTrue(modified_confirmation_binding["confirmation_dry_run_modified_detected"])
        self.assertFalse(modified_confirmation_binding["confirmation_dry_run_integrity_valid"])
        self.assertIn("confirmation_dry_run_integrity_mismatch", modified_confirmation_binding["blockers"])

        self.assertEqual(missing_confirmation_binding["status"], "confirmation_missing")
        self.assertFalse(missing_confirmation_binding["confirmation_supplied"])
        self.assertFalse(missing_confirmation_binding["confirmation_exact_match"])

        self.assertEqual(malformed_text_binding["status"], "malformed")
        self.assertIn("confirmation_text_malformed", malformed_text_binding["blockers"])

        report_lower = valid_report.lower()
        self.assertIn("controlled registration authorization-preview / confirmation-evidence binding", report_lower)
        self.assertIn("Modified previews fail integrity validation.", valid_report)
        self.assertIn("phase 15c performs zero writes.", report_lower)
        self.assertNotIn('"expected_outcome"', report_lower)
        self.assertNotIn('"records"', report_lower)
        self.assertNotIn("c:\\users\\", report_lower)
        self.assertNotIn("/users/", report_lower)
        self.assertNotIn("/home/", report_lower)
        self.assertNotIn("traceback", report_lower)

        for forbidden_key in (
            "effectiveness_score",
            "correctness_score",
            "success_rate",
            "failure_rate",
            "production_score",
            "profitability_score",
            "prediction_quality_score",
            "deployment_safety_score",
        ):
            self.assertNotIn(forbidden_key, json.dumps(valid_binding, sort_keys=True))
            self.assertNotIn(forbidden_key, valid_report)

        doc_path = Path(
            "docs/PHASE_15C_CONTROLLED_REGISTRATION_AUTHORIZATION_PREVIEW_IDENTITY_CONFIRMATION_EVIDENCE_BINDING_STALE_PREVIEW_GATE.md"
        )
        self.assertTrue(doc_path.exists())
        doc_text = doc_path.read_text(encoding="utf-8")
        for required_heading in (
            "## 1. Purpose",
            "## 2. Scope",
            "## 3. Phase 15B Prerequisite",
            "## 4. Backend Functions",
            "## 5. Binding-Gate Inputs",
            "## 6. Input Validation",
            "## 7. Expected Preview Reconstruction",
            "## 8. Authorization-Preview Integrity",
            "## 9. Current Identity Rebinding",
            "## 10. Authorization-Scope Binding",
            "## 11. Confirmation-Policy Binding",
            "## 12. Dry-Run Evidence Binding",
            "## 13. Confirmation Dry-Run Integrity",
            "## 14. Confirmation-Evidence Binding",
            "## 15. Modified Preview Behavior",
            "## 16. Stale Preview Behavior",
            "## 17. Unknown, Stale-Target, and Conflict Behavior",
            "## 18. Status Precedence",
            "## 19. Valid Binding Versus Authorization",
            "## 20. Read-Only / Non-Persistent Boundary",
            "## 21. Public-Safe Report Limits",
            "## 22. Explicit Non-Claims",
            "## 23. Exact Test Command",
            "## 24. Known Risks",
            "## 25. Recommended Next Phase",
        ):
            self.assertIn(required_heading, doc_text)
        for required_phrase in (
            "Phase 15C validates deterministic binding between the current candidate, backend plan, transaction plan, target state, dry-run evidence, authorization preview, confirmation policy, and confirmation evidence.",
            "Phase 15C treats supplied previews and confirmation dry-run results as untrusted.",
            "Modified previews fail integrity validation.",
            "Stale previews may remain internally intact but no longer match current prerequisites.",
            "Modified and stale previews are not repaired in place.",
            "Confirmation evidence is recomputed from current stable evidence and the supplied confirmation text's match outcome.",
            "The raw confirmation text is not persisted, echoed, returned, or included in public-safe reports.",
            "An exact confirmation match cannot override a stale, modified, conflicting, unknown, or otherwise blocked prerequisite state.",
            "A valid authorization-preview binding does not create an authorization artifact.",
            "A valid authorization-preview binding does not grant execution authorization.",
            "A valid authorization-preview binding does not grant registration authorization.",
            "Confirmation remains unaccepted and unenforced.",
            "Idempotency remains unenforced.",
            "Phase 15C does not call the registration function.",
            "Phase 15C performs zero writes.",
            "A valid fingerprint proves integrity against the defined canonical representation only.",
            "It does not prove factual correctness of outcome-truth records.",
            "Phase 15D - Controlled Registration Authorization Preview, Confirmation Dry Run, and Evidence-Binding API/UI Seam",
        ):
            self.assertIn(required_phrase, doc_text)
