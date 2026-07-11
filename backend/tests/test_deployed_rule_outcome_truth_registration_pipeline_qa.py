from __future__ import annotations

import inspect
import json
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
    for event_id in ("event-1", "event-4"):
        event_path = truth.telemetry_backend._event_path(root, event_id)
        event_path.parent.mkdir(parents=True, exist_ok=True)
        event_path.write_text(
            json.dumps({"event_id": event_id, "input_fingerprint": ""}, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    payload = {
        "schema_version": truth.telemetry_backend.SNAPSHOT_SCHEMA,
        "telemetry_schema_version": truth.telemetry_backend.TELEMETRY_SCHEMA_VERSION,
        "telemetry_snapshot_id": snapshot_id,
        "canonical_rule_id": "rule-1",
        "production_deployment_result_id": "deploy-1",
        "production_target_id": "target-1",
        "deployed_rule_id": "deployed-1",
        "observation_start": "2026-07-10T10:00:00Z",
        "observation_end": "2026-07-10T12:00:00Z",
        "event_count": 2,
        "validated_event_ids": ["event-1", "event-4"],
        "events": [],
    }
    snapshot_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "telemetry_snapshot_id": snapshot_id,
        "canonical_rule_id": "rule-1",
        "production_deployment_result_id": "deploy-1",
        "production_target_id": "target-1",
        "deployed_rule_id": "deployed-1",
        "observation_window_start": "2026-07-10T10:00:00Z",
        "observation_window_end": "2026-07-10T12:00:00Z",
    }


class DeployedRuleOutcomeTruthRegistrationPipelineQAGateTest(TestCase):
    def test_outcome_truth_record_set_registration_pipeline_qa_gate_is_read_only_preflight_and_no_overclaim(self) -> None:
        self.assertTrue(callable(truth.build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate))
        self.assertTrue(callable(truth.format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report))

        gate_source = inspect.getsource(truth.build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate)
        report_source = inspect.getsource(truth.format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report)
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
            self.assertNotIn(forbidden_call, gate_source)
            self.assertNotIn(forbidden_call, report_source)
        self.assertIn("_ensure_dirs(", register_source)

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
        ):
            self.assertNotIn(forbidden_surface, gate_source)
            self.assertNotIn(forbidden_surface, report_source)

        with TemporaryDirectory() as tmp:
            missing_root = Path(tmp) / "missing"
            before_missing = sorted(str(path.relative_to(missing_root)) for path in missing_root.rglob("*")) if missing_root.exists() else []
            missing_gate = truth.build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate(None, root=missing_root)
            missing_report = truth.format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report(None, root=missing_root)
            after_missing = sorted(str(path.relative_to(missing_root)) for path in missing_root.rglob("*")) if missing_root.exists() else []

            malformed_root = Path(tmp) / "malformed"
            before_malformed = sorted(str(path.relative_to(malformed_root)) for path in malformed_root.rglob("*")) if malformed_root.exists() else []
            malformed_gate = truth.build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate({"records": "bad"}, root=malformed_root)
            after_malformed = sorted(str(path.relative_to(malformed_root)) for path in malformed_root.rglob("*")) if malformed_root.exists() else []

            fixture_root = Path(tmp) / "fixture"
            identity = _write_telemetry_snapshot_fixture(fixture_root)
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
                    },
                    {
                        "execution_event_id": "event-1",
                        "expected_outcome": "venus_day",
                        "actual_or_adjudicated_outcome": "mars_day",
                        "outcome_observed_at": "2026-07-10T11:05:00Z",
                        "truth_status": "valid",
                        "source_id": "source-1",
                        "source_type": "external_authoritative_result",
                        "source_authority_class": "authoritative",
                    },
                    {
                        "input_fingerprint": "input-3",
                        "expected_outcome": None,
                        "actual_or_adjudicated_outcome": "venus_day",
                        "truth_status": "incomplete",
                        "source_id": "",
                        "source_type": "",
                        "source_authority_class": "",
                    },
                    {
                        "execution_event_id": "event-4",
                        "expected_outcome": "venus_day",
                        "actual_or_adjudicated_outcome": {"invalid": "value"},
                        "truth_status": "invalid",
                        "source_id": "source-1",
                        "source_type": "external_authoritative_result",
                        "source_authority_class": "authoritative",
                    },
                ],
            }
            before_fixture = sorted(str(path.relative_to(fixture_root)) for path in fixture_root.rglob("*"))
            qa_gate = truth.build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate(candidate, root=fixture_root)
            qa_report = truth.format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report(candidate, root=fixture_root)
            after_fixture = sorted(str(path.relative_to(fixture_root)) for path in fixture_root.rglob("*"))

        self.assertEqual(before_missing, after_missing)
        self.assertEqual(missing_gate["status"], "missing")
        self.assertEqual(missing_gate["writes_performed"], 0)
        self.assertIn("candidate_record_set_missing", missing_gate["blockers"])
        self.assertEqual(before_malformed, after_malformed)
        self.assertEqual(malformed_gate["status"], "malformed")
        self.assertEqual(malformed_gate["writes_performed"], 0)
        self.assertIn("candidate_record_set_records_missing", malformed_gate["blockers"])

        self.assertEqual(before_fixture, after_fixture)
        self.assertEqual(qa_gate["status"], "blocked")
        self.assertEqual(qa_gate["candidate_status"], "incomplete")
        self.assertEqual(qa_gate["candidate_record_count"], 4)
        self.assertEqual(qa_gate["candidate_eligible_record_count"], 2)
        self.assertEqual(qa_gate["candidate_excluded_record_count"], 2)
        self.assertEqual(qa_gate["duplicate_record_count"], 1)
        self.assertEqual(qa_gate["conflict_count"], 1)
        self.assertGreaterEqual(qa_gate["missing_required_field_count"], 1)
        self.assertGreaterEqual(qa_gate["missing_expected_outcome_count"], 1)
        self.assertGreaterEqual(qa_gate["missing_actual_outcome_count"], 1)
        self.assertGreaterEqual(qa_gate["invalid_outcome_value_count"], 1)
        self.assertGreaterEqual(qa_gate["missing_source_metadata_count"], 1)
        self.assertGreaterEqual(qa_gate["malformed_record_count"], 1)
        self.assertIn("mixed_scope_warning_count", qa_gate)
        self.assertIn("structurally_ready_for_registration", qa_gate)
        self.assertFalse(qa_gate["structurally_ready_for_registration"])
        self.assertIn("blockers", qa_gate)
        self.assertIn("warnings", qa_gate)
        self.assertIn("recommended_action", qa_gate)
        self.assertTrue(isinstance(qa_gate["limitations"], list))
        self.assertTrue(isinstance(qa_gate["boundary_flags"], dict))
        self.assertFalse(qa_gate["boundary_flags"]["registration_performed"])
        self.assertFalse(qa_gate["boundary_flags"]["record_set_written"])
        self.assertFalse(qa_gate["boundary_flags"]["records_repaired"])
        self.assertFalse(qa_gate["boundary_flags"]["records_migrated"])
        self.assertFalse(qa_gate["boundary_flags"]["outcome_truth_factual_correctness_claimed"])
        self.assertEqual(qa_gate["writes_performed"], 0)

        report_lower = qa_report.lower()
        self.assertNotIn(str(fixture_root).lower(), report_lower)
        self.assertNotIn("c:\\users\\", report_lower)
        self.assertNotIn("/users/", report_lower)
        self.assertNotIn("/home/", report_lower)
        self.assertNotIn("{", qa_report)
        self.assertNotIn('"expected_outcome"', report_lower)
        self.assertNotIn("traceback", report_lower)
        self.assertIn("limitations:", report_lower)
        self.assertIn("writes performed: 0", report_lower)
        self.assertIn("does not prove the factual correctness", report_lower)
        self.assertIn("does not establish broad rule effectiveness", report_lower)
        self.assertIn("does not establish deployment safety", report_lower)
        self.assertIn("does not establish production correctness", report_lower)
        self.assertIn("does not establish profitability", report_lower)
        self.assertIn("does not establish prediction quality", report_lower)
        self.assertIn("does not establish future performance", report_lower)
        self.assertIn("does not establish aggregate effectiveness", report_lower)
        self.assertIn("does not establish ranking quality", report_lower)

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
            self.assertNotIn(forbidden_score, qa_report)
            self.assertNotIn(forbidden_score, json.dumps(qa_gate, sort_keys=True))

        doc_text = Path("docs/PHASE_12A_OUTCOME_TRUTH_RECORD_SET_REGISTRATION_PIPELINE_QA_GATE.md").read_text(encoding="utf-8")
        self.assertIn("The registration-pipeline QA gate checks structural and internal consistency of a candidate outcome-truth record set before registration.", doc_text)
        self.assertIn("It does not register records.", doc_text)
        self.assertIn("It does not repair records.", doc_text)
        self.assertIn("It does not migrate records.", doc_text)
        self.assertIn("It performs no writes and creates no storage.", doc_text)
        self.assertIn("Phase 12B", doc_text)

    def test_outcome_truth_record_set_registration_pipeline_qa_api_ui_seam_is_read_only_and_no_overclaim(self) -> None:
        self.assertTrue(callable(truth.build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate))
        self.assertTrue(callable(truth.format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report))
        self.assertTrue(callable(api.build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate))
        self.assertTrue(callable(api.format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report))

        gate_signature = inspect.signature(api.build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate)
        report_signature = inspect.signature(api.format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report)
        self.assertEqual(set(gate_signature.parameters), {"candidate_record_set", "root"})
        self.assertEqual(set(report_signature.parameters), {"candidate_record_set", "root"})
        for forbidden_parameter in (
            "score", "score_value", "ratio", "percentage", "numerator", "denominator", "metric", "metric_family",
            "authority_scope", "dry_run_payload", "candidate_summary", "manual_score", "override", "force",
            "aggregate_method", "ranking_method", "weight", "threshold", "factual_truth_override",
            "correct_outcome_override", "expected_outcome_override", "actual_outcome_override", "register", "write",
            "repair", "migrate", "auto_register", "force_register",
        ):
            self.assertNotIn(forbidden_parameter, gate_signature.parameters)
            self.assertNotIn(forbidden_parameter, report_signature.parameters)

        api_gate_source = inspect.getsource(api.build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate)
        api_report_source = inspect.getsource(api.format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report)
        desktop_source = inspect.getsource(desktop_panel)
        desktop_action_source = inspect.getsource(desktop_panel.DesktopRightPanelMixin._run_pdf_viewport_action)
        desktop_status_source = inspect.getsource(desktop_panel.DesktopRightPanelMixin._set_deployed_rule_outcome_truth_status)
        parser_source = inspect.getsource(desktop_panel.DesktopRightPanelMixin._parse_deployed_rule_outcome_truth_candidate_record_set)
        stale_source = inspect.getsource(desktop_panel.DesktopRightPanelMixin._mark_deployed_rule_outcome_truth_stale)
        for forbidden_call in (
            "register_deployed_rule_outcome_truth_record_set(",
            "build_deployed_rule_outcome_truth_source_plan(",
            "record_deployed_rule_outcome_truth_source_result(",
            "_ensure_dirs(",
            "json.dump(",
            "write_text(",
            "_atomic_write_json(",
        ):
            self.assertNotIn(forbidden_call, api_gate_source)
            self.assertNotIn(forbidden_call, api_report_source)
        self.assertIn("Load Registration Pipeline QA Gate", desktop_source)
        self.assertIn("Copy Registration Pipeline QA Report", desktop_source)
        self.assertIn("load_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate", desktop_action_source)
        self.assertIn("copy_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report", desktop_action_source)
        self.assertIn("candidate_record_set_required", parser_source)
        self.assertIn("candidate_record_set_malformed", parser_source)
        self.assertIn("Candidate Payload Status: stale_due_to_input_change", stale_source)
        self.assertIn("Structurally Ready For Registration:", desktop_status_source)
        self.assertIn("Recommended Action:", desktop_status_source)
        self.assertIn("Limitations:", desktop_status_source)
        for forbidden_ui in (
            "Force Score", "Override Score", "Manual Score", "Aggregate Score", "Rank Results", "Compare Results",
            "Register From QA", "Auto Register", "Force Register", "Repair Record Set", "Migrate Record Set",
        ):
            self.assertNotIn(forbidden_ui, desktop_source)

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
        panel.clipboard_value = ""
        panel._current_source_document_id = lambda: "doc-1"
        panel.clipboard_clear = lambda: setattr(panel, "clipboard_value", "")
        panel.clipboard_append = lambda text: setattr(panel, "clipboard_value", text)
        panel._set_deployed_rule_outcome_truth_status = desktop_panel.DesktopRightPanelMixin._set_deployed_rule_outcome_truth_status.__get__(panel, _FakePanel)
        panel._parse_deployed_rule_outcome_truth_candidate_record_set = desktop_panel.DesktopRightPanelMixin._parse_deployed_rule_outcome_truth_candidate_record_set.__get__(panel, _FakePanel)
        panel._run_pdf_viewport_action = desktop_panel.DesktopRightPanelMixin._run_pdf_viewport_action.__get__(panel, _FakePanel)
        panel._mark_deployed_rule_outcome_truth_stale = desktop_panel.DesktopRightPanelMixin._mark_deployed_rule_outcome_truth_stale.__get__(panel, _FakePanel)

        self.assertIsNone(panel._parse_deployed_rule_outcome_truth_candidate_record_set())
        self.assertIn("candidate_record_set_required", panel.deployed_rule_outcome_truth_status_var.get())
        panel.deployed_rule_outcome_truth_record_json_var.set("{bad")
        self.assertIsNone(panel._parse_deployed_rule_outcome_truth_candidate_record_set())
        self.assertIn("candidate_record_set_malformed", panel.deployed_rule_outcome_truth_status_var.get())

        panel._mark_deployed_rule_outcome_truth_stale()
        self.assertIn("Candidate Payload Status: stale_due_to_input_change", panel.deployed_rule_outcome_truth_status_var.get())

        qa_payload = {
            "status": "blocked",
            "candidate_status": "incomplete",
            "candidate_record_count": 3,
            "candidate_eligible_record_count": 2,
            "candidate_excluded_record_count": 1,
            "duplicate_record_count": 1,
            "conflict_count": 1,
            "missing_expected_outcome_count": 1,
            "missing_actual_outcome_count": 1,
            "missing_source_metadata_count": 1,
            "mixed_scope_warning_count": 1,
            "structurally_ready_for_registration": False,
            "blockers": ["record_blocker"],
            "warnings": ["scope_warning"],
            "recommended_action": "Review candidate blockers.",
            "limitations": ["It does not prove factual correctness."],
            "writes_performed": 0,
        }
        panel._set_deployed_rule_outcome_truth_status(qa_payload)
        status_text = panel.deployed_rule_outcome_truth_status_var.get()
        self.assertIn("Record Count: 3", status_text)
        self.assertIn("Eligible Record Count: 2", status_text)
        self.assertIn("Excluded Record Count: 1", status_text)
        self.assertIn("Duplicate Record Count: 1", status_text)
        self.assertIn("Conflict Count: 1", status_text)
        self.assertIn("Missing Expected Outcome Count: 1", status_text)
        self.assertIn("Source Metadata Warning Count: 1", status_text)
        self.assertIn("Structurally Ready For Registration: no", status_text)
        self.assertIn("Recommended Action: Review candidate blockers.", status_text)
        self.assertIn("Limitations: It does not prove factual correctness.", status_text)
        self.assertIn("Writes Performed: 0", status_text)

        original_report = desktop_panel.format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report
        original_build = desktop_panel.build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate
        try:
            panel.deployed_rule_outcome_truth_record_json_var.set(json.dumps({"records": []}))

            def _fake_build(candidate_record_set, *, root=Path("data/source_documents")):
                self.assertEqual(candidate_record_set, {"records": []})
                return qa_payload

            def _fake_report(candidate_record_set, *, root=Path("data/source_documents")):
                self.assertEqual(candidate_record_set, {"records": []})
                return "Outcome-truth registration-pipeline QA report\nStatus: blocked\nIt does not prove the factual correctness of outcome-truth records."

            desktop_panel.build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate = _fake_build
            desktop_panel.format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report = _fake_report
            panel._run_pdf_viewport_action("load_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate")
            panel._run_pdf_viewport_action("copy_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report")
        finally:
            desktop_panel.build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate = original_build
            desktop_panel.format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report = original_report

        self.assertIn("factual correctness", panel.clipboard_value.lower())
        self.assertNotIn("{", panel.clipboard_value)
        self.assertNotIn("c:\\users\\", panel.clipboard_value.lower())
        self.assertNotIn("traceback", panel.clipboard_value.lower())

        doc_text = Path("docs/PHASE_12B_OUTCOME_TRUTH_RECORD_SET_REGISTRATION_PIPELINE_QA_API_UI_SEAM.md").read_text(encoding="utf-8")
        self.assertIn("The API/UI seam exposes the structural registration-pipeline QA gate only.", doc_text)
        self.assertIn("It does not register records.", doc_text)
        self.assertIn("It does not repair records.", doc_text)
        self.assertIn("It does not migrate records.", doc_text)
        self.assertIn("The seam is read-only and performs no registration, repair, migration, storage creation, or scoring.", doc_text)

    def test_outcome_truth_registration_pipeline_qa_export_operator_handoff_preserves_public_safe_read_only_no_registration_boundaries(self) -> None:
        handoff_path = Path("docs/PHASE_12C_OUTCOME_TRUTH_REGISTRATION_PIPELINE_QA_EXPORT_OPERATOR_HANDOFF.md")
        self.assertTrue(handoff_path.exists())
        handoff_doc = handoff_path.read_text(encoding="utf-8")
        doc_12a = Path("docs/PHASE_12A_OUTCOME_TRUTH_RECORD_SET_REGISTRATION_PIPELINE_QA_GATE.md").read_text(encoding="utf-8")
        doc_12b = Path("docs/PHASE_12B_OUTCOME_TRUTH_RECORD_SET_REGISTRATION_PIPELINE_QA_API_UI_SEAM.md").read_text(encoding="utf-8")

        for heading in (
            "## 1. Purpose",
            "## 2. Release Scope",
            "## 3. Operator Workflow",
            "## 4. Public-Safe Registration-Pipeline QA Export / Report",
            "## 5. Allowed QA Fields and Counters",
            "## 6. Read-Only / No-Registration Boundary",
            "## 7. Explicit Non-Claims",
            "## 8. API/UI Surface",
            "## 9. Validation Evidence",
            "## 10. Skipped Broad Tests by Policy",
            "## 11. Known Risks",
            "## 12. Recommended Next Phase",
        ):
            self.assertIn(heading, handoff_doc)

        self.assertIn(
            "This handoff describes the read-only structural Outcome-Truth Record-Set Registration Pipeline QA Gate and its API/UI seam.",
            handoff_doc,
        )
        self.assertIn(
            "The registration-pipeline QA gate checks structural and internal consistency of candidate outcome-truth record sets before registration only.",
            handoff_doc,
        )
        self.assertIn("1. Paste or enter Candidate Outcome-Truth Record Set JSON.", handoff_doc)
        self.assertIn("4. Copy Registration Pipeline QA Report.", handoff_doc)
        self.assertIn("The QA report is the public-safe export surface.", handoff_doc)
        for field_name in (
            "candidate_record_count",
            "candidate_eligible_record_count",
            "candidate_excluded_record_count",
            "duplicate_record_count",
            "conflict_count",
            "missing_required_field_count",
            "missing_expected_outcome_count",
            "missing_actual_outcome_count",
            "invalid_outcome_value_count",
            "missing_source_metadata_count",
            "malformed_record_count",
            "mixed_scope_warning_count",
            "structurally_ready_for_registration",
        ):
            self.assertIn(field_name, handoff_doc)
        self.assertIn("writes_performed = 0", handoff_doc)
        self.assertIn("build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate", handoff_doc)
        self.assertIn("format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report", handoff_doc)
        self.assertIn("Load Registration Pipeline QA Gate", handoff_doc)
        self.assertIn("Copy Registration Pipeline QA Report", handoff_doc)
        self.assertIn("test_outcome_truth_record_set_registration_pipeline_qa_gate_is_read_only_preflight_and_no_overclaim", handoff_doc)
        self.assertIn("test_outcome_truth_record_set_registration_pipeline_qa_api_ui_seam_is_read_only_and_no_overclaim", handoff_doc)
        self.assertIn("pytest", handoff_doc)
        self.assertIn("broad end-to-end registration variants", handoff_doc)
        self.assertIn("Phase 12D", handoff_doc)
        self.assertIn("Operator handoff/export packet:", doc_12a)
        self.assertIn("Operator handoff/export packet:", doc_12b)

        self.assertTrue(callable(truth.build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate))
        self.assertTrue(callable(truth.format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report))
        self.assertTrue(callable(api.build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate))
        self.assertTrue(callable(api.format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report))

        gate_source = inspect.getsource(truth.build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate)
        report_source = inspect.getsource(truth.format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report)
        api_gate_source = inspect.getsource(api.build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate)
        api_report_source = inspect.getsource(api.format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report)
        desktop_source = inspect.getsource(desktop_panel)
        action_source = inspect.getsource(desktop_panel.DesktopRightPanelMixin._run_pdf_viewport_action)
        parser_source = inspect.getsource(desktop_panel.DesktopRightPanelMixin._parse_deployed_rule_outcome_truth_candidate_record_set)
        stale_source = inspect.getsource(desktop_panel.DesktopRightPanelMixin._mark_deployed_rule_outcome_truth_stale)

        self.assertIn("Load Registration Pipeline QA Gate", desktop_source)
        self.assertIn("Copy Registration Pipeline QA Report", desktop_source)
        self.assertIn("load_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate", action_source)
        self.assertIn("copy_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report", action_source)
        self.assertIn("format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report(", action_source)
        self.assertNotIn("json.dumps(", action_source)
        self.assertIn("candidate_record_set_required", parser_source)
        self.assertIn("candidate_record_set_malformed", parser_source)
        self.assertIn("Candidate Payload Status: stale_due_to_input_change", stale_source)

        for source_text in (gate_source, report_source, api_gate_source, api_report_source):
            for forbidden_call in (
                "register_deployed_rule_outcome_truth_record_set(",
                "build_deployed_rule_outcome_truth_source_plan(",
                "record_deployed_rule_outcome_truth_source_result(",
                "_ensure_dirs(",
                "json.dump(",
                "write_text(",
                "_atomic_write_json(",
            ):
                self.assertNotIn(forbidden_call, source_text)

        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            report = truth.format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report(None, root=root)
            report_lower = report.lower()
            self.assertIn("limitations:", report_lower)
            self.assertIn("writes performed: 0", report_lower)
            self.assertNotIn(str(root).lower(), report_lower)
            self.assertNotIn("c:\\users\\", report_lower)
            self.assertNotIn("/users/", report_lower)
            self.assertNotIn("/home/", report_lower)
            self.assertNotIn("traceback", report_lower)
            self.assertNotIn("{", report)
            self.assertNotIn('"', report)

        for forbidden_ui in (
            "Force Score",
            "Override Score",
            "Manual Score",
            "Aggregate Score",
            "Rank Results",
            "Compare Results",
            "Repair Record Set",
            "Migrate Record Set",
            "Register From QA",
            "Auto Register",
            "Force Register",
        ):
            self.assertNotIn(forbidden_ui, desktop_source)

        handoff_lower = handoff_doc.lower()
        for forbidden_claim in (
            "factual truth correctness proven",
            "truth correctness proven",
            "automatic registration approved",
            "broad effectiveness proven",
            "production correctness proven",
            "deployment safety proven",
            "profitability proven",
            "prediction quality proven",
            "future performance proven",
            "aggregate effectiveness proven",
            "ranking quality proven",
            "broad regression passed",
        ):
            self.assertNotIn(forbidden_claim, handoff_lower)
        for required_non_claim in (
            "factual truth correctness",
            "automatic registration approval",
            "broad rule effectiveness",
            "production correctness",
            "deployment safety",
            "profitability",
            "prediction quality",
            "future performance",
            "aggregate effectiveness",
            "ranking quality",
        ):
            self.assertIn(required_non_claim, handoff_lower)

    def test_outcome_truth_registration_pipeline_qa_release_packet_and_final_freeze_preserve_boundaries(self) -> None:
        release_path = Path("docs/PHASE_12D_OUTCOME_TRUTH_REGISTRATION_PIPELINE_QA_RELEASE_PACKET.md")
        self.assertTrue(release_path.exists())
        release_doc = release_path.read_text(encoding="utf-8")
        doc_12a = Path("docs/PHASE_12A_OUTCOME_TRUTH_RECORD_SET_REGISTRATION_PIPELINE_QA_GATE.md").read_text(encoding="utf-8")
        doc_12b = Path("docs/PHASE_12B_OUTCOME_TRUTH_RECORD_SET_REGISTRATION_PIPELINE_QA_API_UI_SEAM.md").read_text(encoding="utf-8")
        doc_12c = Path("docs/PHASE_12C_OUTCOME_TRUTH_REGISTRATION_PIPELINE_QA_EXPORT_OPERATOR_HANDOFF.md").read_text(encoding="utf-8")

        for heading in (
            "## 1. Release Scope",
            "## 2. Feature Surface",
            "## 3. Operator Workflow",
            "## 4. Registration-Pipeline QA Checks and Counters",
            "## 5. Public-Safe Registration-Pipeline QA Report",
            "## 6. Read-Only / No-Registration Boundary",
            "## 7. API/UI Surface",
            "## 8. Explicit Non-Claims",
            "## 9. Validation Evidence",
            "## 10. Skipped Broad Tests by Policy",
            "## 11. Known Risks",
            "## 12. Final Freeze Status",
            "## 13. Recommended Next Phase",
        ):
            self.assertIn(heading, release_doc)

        self.assertIn("This release covers the read-only structural Outcome-Truth Record-Set Registration Pipeline QA Gate.", release_doc)
        self.assertIn("The registration-pipeline QA gate checks structural and internal consistency of candidate outcome-truth record sets before registration only.", release_doc)
        self.assertIn("It does not register records.", release_doc)
        self.assertIn("It does not repair records.", release_doc)
        self.assertIn("It does not migrate records.", release_doc)
        self.assertIn("It does not score rules.", release_doc)
        self.assertIn("It does not validate factual truth.", release_doc)
        self.assertIn("build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate", release_doc)
        self.assertIn("format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report", release_doc)
        self.assertIn("Load Registration Pipeline QA Gate", release_doc)
        self.assertIn("Copy Registration Pipeline QA Report", release_doc)
        self.assertIn("1. Paste or enter Candidate Outcome-Truth Record Set JSON.", release_doc)
        self.assertIn("4. Copy Registration Pipeline QA Report.", release_doc)
        self.assertIn("No confirmation is required.", release_doc)
        self.assertIn("No scoring occurs.", release_doc)
        self.assertIn("No registration occurs.", release_doc)
        self.assertIn("No repair occurs.", release_doc)
        self.assertIn("No migration occurs.", release_doc)
        self.assertIn("No storage creation occurs.", release_doc)
        self.assertIn("Raw JSON is not copied as the public-safe report.", release_doc)
        for field_name in (
            "candidate parseability",
            "candidate_record_count",
            "candidate_eligible_record_count",
            "candidate_excluded_record_count",
            "duplicate_record_count",
            "conflict_count",
            "missing_required_field_count",
            "missing_expected_outcome_count",
            "missing_actual_outcome_count",
            "invalid_outcome_value_count",
            "missing_source_metadata_count",
            "malformed_record_count",
            "mixed_scope_warning_count",
            "structurally_ready_for_registration",
            "blockers",
            "warnings",
            "recommended_action",
            "limitations",
            "writes_performed",
        ):
            self.assertIn(field_name, release_doc)
        self.assertIn("writes_performed = 0", release_doc)
        self.assertIn("API wrappers accept only the candidate record-set payload and optional test root.", release_doc)
        self.assertIn("Missing candidate blocks explicitly.", release_doc)
        self.assertIn("Malformed candidate blocks explicitly where UI parsing exists.", release_doc)
        self.assertIn("Stale-state includes candidate input.", release_doc)
        self.assertIn("Copy action uses formatter, not raw JSON.", release_doc)
        self.assertIn("Candidate input currently uses Outcome Truth Record JSON rather than a dedicated structured editor.", release_doc)
        self.assertIn("test_outcome_truth_record_set_registration_pipeline_qa_gate_is_read_only_preflight_and_no_overclaim", release_doc)
        self.assertIn("test_outcome_truth_record_set_registration_pipeline_qa_api_ui_seam_is_read_only_and_no_overclaim", release_doc)
        self.assertIn("test_outcome_truth_registration_pipeline_qa_export_operator_handoff_preserves_public_safe_read_only_no_registration_boundaries", release_doc)
        self.assertIn("Phase 13A - Controlled Outcome-Truth Record-Set Registration Workflow Planning Gate", release_doc)
        self.assertIn("Backend registration-pipeline QA gate: frozen", release_doc)
        self.assertIn("API/UI seam: frozen", release_doc)
        self.assertIn("Operator handoff/report surface: frozen", release_doc)
        self.assertIn("Authority: structural pre-registration QA only", release_doc)
        self.assertIn("No-overclaim boundary: preserved", release_doc)

        self.assertIn("Final release packet:", doc_12a)
        self.assertIn("Final release packet:", doc_12b)
        self.assertIn("Final release packet:", doc_12c)

        self.assertTrue(callable(truth.build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate))
        self.assertTrue(callable(truth.format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report))
        self.assertTrue(callable(api.build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate))
        self.assertTrue(callable(api.format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report))

        gate_source = inspect.getsource(truth.build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate)
        report_source = inspect.getsource(truth.format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report)
        api_gate_source = inspect.getsource(api.build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate)
        api_report_source = inspect.getsource(api.format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report)
        desktop_source = inspect.getsource(desktop_panel)
        action_source = inspect.getsource(desktop_panel.DesktopRightPanelMixin._run_pdf_viewport_action)
        parser_source = inspect.getsource(desktop_panel.DesktopRightPanelMixin._parse_deployed_rule_outcome_truth_candidate_record_set)
        stale_source = inspect.getsource(desktop_panel.DesktopRightPanelMixin._mark_deployed_rule_outcome_truth_stale)

        for source_text in (gate_source, report_source, api_gate_source, api_report_source):
            for forbidden_call in (
                "register_deployed_rule_outcome_truth_record_set(",
                "build_deployed_rule_outcome_truth_source_plan(",
                "record_deployed_rule_outcome_truth_source_result(",
                "_ensure_dirs(",
                "json.dump(",
                "write_text(",
                "_atomic_write_json(",
            ):
                self.assertNotIn(forbidden_call, source_text)

        self.assertIn("Load Registration Pipeline QA Gate", desktop_source)
        self.assertIn("Copy Registration Pipeline QA Report", desktop_source)
        self.assertIn("load_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate", action_source)
        self.assertIn("copy_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report", action_source)
        self.assertIn("format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report(", action_source)
        self.assertNotIn("json.dumps(", action_source)
        self.assertIn("candidate_record_set_required", parser_source)
        self.assertIn("candidate_record_set_malformed", parser_source)
        self.assertIn("Candidate Payload Status: stale_due_to_input_change", stale_source)

        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            report = truth.format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report(None, root=root)
            report_lower = report.lower()
            self.assertIn("limitations:", report_lower)
            self.assertIn("writes performed: 0", report_lower)
            self.assertNotIn(str(root).lower(), report_lower)
            self.assertNotIn("c:\\users\\", report_lower)
            self.assertNotIn("/users/", report_lower)
            self.assertNotIn("/home/", report_lower)
            self.assertNotIn("traceback", report_lower)
            self.assertNotIn("{", report)
            self.assertNotIn('"', report)

        for forbidden_ui in (
            "Force Score",
            "Override Score",
            "Manual Score",
            "Aggregate Score",
            "Rank Results",
            "Compare Results",
            "Repair Record Set",
            "Migrate Record Set",
            "Register From QA",
            "Auto Register",
            "Force Register",
        ):
            self.assertNotIn(forbidden_ui, desktop_source)

        release_lower = release_doc.lower()
        for forbidden_claim in (
            "factual truth correctness proven",
            "truth correctness proven",
            "automatic registration approved",
            "broad effectiveness proven",
            "production correctness proven",
            "deployment safety proven",
            "profitability proven",
            "prediction quality proven",
            "future performance proven",
            "aggregate effectiveness proven",
            "ranking quality proven",
            "broad regression passed",
            "full suite passed",
        ):
            self.assertNotIn(forbidden_claim, release_lower)
        for required_non_claim in (
            "factual truth correctness",
            "automatic registration approval",
            "broad rule effectiveness",
            "production correctness",
            "deployment safety",
            "profitability",
            "prediction quality",
            "future performance",
            "aggregate effectiveness",
            "ranking quality",
        ):
            self.assertIn(required_non_claim, release_lower)
