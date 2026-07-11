from __future__ import annotations

import inspect
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import api
from backend.electional import desktop_right_panel as desktop_panel
from backend.electional import deployed_rule_outcome_truth_source as truth


def _write_record_set_fixture(root: Path) -> str:
    (root / truth.RECORD_SET_DIR).mkdir(parents=True, exist_ok=True)
    (root / truth.RECORD_DIR).mkdir(parents=True, exist_ok=True)
    record_set_id = "deployed_rule_outcome_truth_record_set_fixture"
    record_ids = [
        "deployed_rule_outcome_truth_record_1",
        "deployed_rule_outcome_truth_record_2",
        "deployed_rule_outcome_truth_record_3",
        "deployed_rule_outcome_truth_record_4",
    ]
    records = [
        {
            "schema_version": truth.RECORD_SCHEMA,
            "outcome_truth_source_schema_version": truth.SOURCE_SCHEMA_VERSION,
            "outcome_truth_record_id": record_ids[0],
            "outcome_truth_record_set_id": record_set_id,
            "source_id": "fixture-source",
            "source_type": "external_authoritative_result",
            "source_authority_class": "authoritative",
            "source_fingerprint": truth._hash_payload({"source_id": "fixture-source", "source_type": "external_authoritative_result", "source_authority_class": "authoritative"}),
            "canonical_rule_id": "rule-1",
            "production_deployment_result_id": "deploy-1",
            "production_target_id": "target-1",
            "deployed_rule_id": "deployed-1",
            "telemetry_snapshot_id": "snapshot-1",
            "execution_event_id": "event-1",
            "input_fingerprint": "",
            "observation_window_start": "2026-07-10T10:00:00Z",
            "observation_window_end": "2026-07-10T12:00:00Z",
            "expected_outcome": "venus_day",
            "actual_or_adjudicated_outcome": "venus_day",
            "outcome_observed_at": "2026-07-10T11:00:00Z",
            "truth_status": "valid",
            "confidence_class": "bounded_public_value",
        },
        {
            "schema_version": truth.RECORD_SCHEMA,
            "outcome_truth_source_schema_version": truth.SOURCE_SCHEMA_VERSION,
            "outcome_truth_record_id": record_ids[1],
            "outcome_truth_record_set_id": record_set_id,
            "source_id": "fixture-source",
            "source_type": "external_authoritative_result",
            "source_authority_class": "authoritative",
            "source_fingerprint": truth._hash_payload({"source_id": "fixture-source", "source_type": "external_authoritative_result", "source_authority_class": "authoritative"}),
            "canonical_rule_id": "rule-1",
            "production_deployment_result_id": "deploy-1",
            "production_target_id": "target-1",
            "deployed_rule_id": "deployed-1",
            "telemetry_snapshot_id": "snapshot-1",
            "execution_event_id": "event-1",
            "input_fingerprint": "",
            "observation_window_start": "2026-07-10T10:00:00Z",
            "observation_window_end": "2026-07-10T12:00:00Z",
            "expected_outcome": "venus_day",
            "actual_or_adjudicated_outcome": "mars_day",
            "outcome_observed_at": "2026-07-10T11:05:00Z",
            "truth_status": "valid",
            "confidence_class": "bounded_public_value",
        },
        {
            "schema_version": truth.RECORD_SCHEMA,
            "outcome_truth_source_schema_version": truth.SOURCE_SCHEMA_VERSION,
            "outcome_truth_record_id": record_ids[2],
            "outcome_truth_record_set_id": record_set_id,
            "source_id": "",
            "source_type": "",
            "source_authority_class": "",
            "source_fingerprint": "",
            "canonical_rule_id": "rule-1",
            "production_deployment_result_id": "deploy-1",
            "production_target_id": "target-1",
            "deployed_rule_id": "deployed-1",
            "telemetry_snapshot_id": "snapshot-1",
            "execution_event_id": "event-3",
            "input_fingerprint": "",
            "observation_window_start": "2026-07-10T10:00:00Z",
            "observation_window_end": "2026-07-10T12:00:00Z",
            "expected_outcome": None,
            "actual_or_adjudicated_outcome": "venus_day",
            "outcome_observed_at": "2026-07-10T11:10:00Z",
            "truth_status": "incomplete",
            "confidence_class": "bounded_public_value",
        },
        {
            "schema_version": truth.RECORD_SCHEMA,
            "outcome_truth_source_schema_version": truth.SOURCE_SCHEMA_VERSION,
            "outcome_truth_record_id": record_ids[3],
            "outcome_truth_record_set_id": record_set_id,
            "source_id": "fixture-source",
            "source_type": "external_authoritative_result",
            "source_authority_class": "authoritative",
            "source_fingerprint": truth._hash_payload({"source_id": "fixture-source", "source_type": "external_authoritative_result", "source_authority_class": "authoritative"}),
            "canonical_rule_id": "rule-1",
            "production_deployment_result_id": "deploy-1",
            "production_target_id": "target-1",
            "deployed_rule_id": "deployed-1",
            "telemetry_snapshot_id": "snapshot-1",
            "execution_event_id": "event-4",
            "input_fingerprint": "",
            "observation_window_start": "2026-07-10T10:00:00Z",
            "observation_window_end": "2026-07-10T12:00:00Z",
            "expected_outcome": "venus_day",
            "actual_or_adjudicated_outcome": {"invalid": "value"},
            "outcome_observed_at": "2026-07-10T11:20:00Z",
            "truth_status": "incomplete",
            "confidence_class": "bounded_public_value",
        },
    ]
    for record in records:
        record["record_fingerprint"] = truth._hash_payload(
            {key: record.get(key) for key in sorted(record) if key != "record_fingerprint"}
        )
        (root / truth.RECORD_DIR / f"{record['outcome_truth_record_id']}.json").write_text(
            json.dumps(record, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    record_set = {
        "schema_version": truth.RECORD_SET_SCHEMA,
        "outcome_truth_source_schema_version": truth.SOURCE_SCHEMA_VERSION,
        "outcome_truth_record_set_id": record_set_id,
        "source_id": "fixture-source",
        "source_type": "external_authoritative_result",
        "source_authority_class": "authoritative",
        "source_fingerprint": truth._hash_payload({"source_id": "fixture-source", "source_type": "external_authoritative_result", "source_authority_class": "authoritative"}),
        "canonical_rule_id": "rule-1",
        "production_deployment_result_id": "deploy-1",
        "production_target_id": "target-1",
        "deployed_rule_id": "deployed-1",
        "telemetry_snapshot_id": "snapshot-1",
        "observation_window_start": "2026-07-10T10:00:00Z",
        "observation_window_end": "2026-07-10T12:00:00Z",
        "outcome_truth_record_ids": record_ids,
        "record_count": len(record_ids),
        "valid_record_count": 2,
        "incomplete_record_count": 2,
        "unsupported_record_count": 0,
        "source_status": "outcome_truth_source_incomplete",
    }
    record_set["record_set_fingerprint"] = truth._hash_payload(
        {key: record_set.get(key) for key in sorted(record_set) if key != "record_set_fingerprint"}
    )
    (root / truth.RECORD_SET_DIR / f"{record_set_id}.json").write_text(
        json.dumps(record_set, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return record_set_id


class DeployedRuleOutcomeTruthRecordSetQAGateTest(TestCase):
    def test_outcome_truth_record_set_qa_gate_is_read_only_structural_and_no_overclaim(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            missing_before = sorted(str(path.relative_to(root)) for path in root.rglob("*")) if root.exists() else []
            missing_gate = truth.build_deployed_rule_outcome_truth_record_set_qa_gate("missing-set", root=root)
            missing_report = truth.format_deployed_rule_outcome_truth_record_set_qa_gate_report("missing-set", root=root)
            missing_after = sorted(str(path.relative_to(root)) for path in root.rglob("*")) if root.exists() else []

            fixture_root = Path(tmp) / "fixture"
            record_set_id = _write_record_set_fixture(fixture_root)
            before_state = sorted(str(path.relative_to(fixture_root)) for path in fixture_root.rglob("*"))
            qa_gate = truth.build_deployed_rule_outcome_truth_record_set_qa_gate(record_set_id, root=fixture_root)
            qa_report = truth.format_deployed_rule_outcome_truth_record_set_qa_gate_report(record_set_id, root=fixture_root)
            after_state = sorted(str(path.relative_to(fixture_root)) for path in fixture_root.rglob("*"))

            corrupt_root = Path(tmp) / "corrupt"
            (corrupt_root / truth.RECORD_SET_DIR).mkdir(parents=True, exist_ok=True)
            corrupt_id = "corrupt-record-set"
            corrupt_payload = {
                "schema_version": truth.RECORD_SET_SCHEMA,
                "outcome_truth_source_schema_version": truth.SOURCE_SCHEMA_VERSION,
                "outcome_truth_record_set_id": corrupt_id,
                "source_id": "corrupt-source",
                "source_type": "external_authoritative_result",
                "source_authority_class": "authoritative",
                "canonical_rule_id": "rule-1",
                "production_deployment_result_id": "deploy-1",
                "production_target_id": "target-1",
                "deployed_rule_id": "deployed-1",
                "telemetry_snapshot_id": "snapshot-1",
                "observation_window_start": "2026-07-10T10:00:00Z",
                "observation_window_end": "2026-07-10T12:00:00Z",
                "outcome_truth_record_ids": ["missing-record"],
            }
            (corrupt_root / truth.RECORD_SET_DIR / f"{corrupt_id}.json").write_text(
                json.dumps(corrupt_payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            corrupt_before = sorted(str(path.relative_to(corrupt_root)) for path in corrupt_root.rglob("*"))
            corrupt_gate = truth.build_deployed_rule_outcome_truth_record_set_qa_gate(corrupt_id, root=corrupt_root)
            corrupt_after = sorted(str(path.relative_to(corrupt_root)) for path in corrupt_root.rglob("*"))

        self.assertTrue(callable(truth.build_deployed_rule_outcome_truth_record_set_qa_gate))
        self.assertTrue(callable(truth.format_deployed_rule_outcome_truth_record_set_qa_gate_report))
        self.assertEqual(missing_before, missing_after)
        self.assertEqual(missing_gate["status"], "missing")
        self.assertEqual(missing_gate["writes_performed"], 0)
        self.assertIn("outcome_truth_record_set_missing", missing_gate["blockers"])
        self.assertIn("does not prove the factual correctness", missing_report)
        self.assertEqual(corrupt_gate["status"], "corrupt")
        self.assertEqual(corrupt_gate["writes_performed"], 0)
        self.assertEqual(corrupt_before, corrupt_after)

        self.assertEqual(before_state, after_state)
        self.assertEqual(qa_gate["writes_performed"], 0)
        self.assertEqual(qa_gate["record_count"], 4)
        self.assertEqual(qa_gate["eligible_record_count"], 2)
        self.assertEqual(qa_gate["excluded_record_count"], 2)
        self.assertEqual(qa_gate["duplicate_record_count"], 1)
        self.assertEqual(qa_gate["conflict_count"], 1)
        self.assertGreaterEqual(qa_gate["missing_expected_outcome_count"], 1)
        self.assertGreaterEqual(qa_gate["missing_actual_outcome_count"], 1)
        self.assertGreaterEqual(qa_gate["invalid_outcome_value_count"], 1)
        self.assertGreaterEqual(qa_gate["missing_source_metadata_count"], 1)
        self.assertGreaterEqual(qa_gate["missing_required_field_count"], 1)
        self.assertIn("recommended_action", qa_gate)
        self.assertTrue(isinstance(qa_gate["blockers"], list))
        self.assertTrue(isinstance(qa_gate["warnings"], list))
        self.assertTrue(isinstance(qa_gate["limitations"], list))
        self.assertIn("outcome_truth_duplicate_records_detected", qa_gate["warnings"])
        for flag_name, expected in truth._outcome_truth_record_set_qa_boundary_flags().items():
            self.assertIn(flag_name, qa_gate["boundary_flags"])
            self.assertEqual(qa_gate["boundary_flags"][flag_name], expected)

        report_lower = qa_report.lower()
        self.assertNotIn(str(fixture_root).lower(), report_lower)
        self.assertNotIn("c:\\users\\", report_lower)
        self.assertNotIn("/users/", report_lower)
        self.assertNotIn("/home/", report_lower)
        self.assertNotIn("traceback", report_lower)
        self.assertNotIn("raw json", report_lower)
        self.assertNotIn('"expected_outcome"', report_lower)
        self.assertIn("structural and internal consistency", report_lower)
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
            "profitability_score",
            "prediction_quality_score",
            "deployment_safety_score",
            "overall_score",
            "final_score",
            "quality_score",
        ):
            self.assertNotIn(forbidden_score, qa_report)
            self.assertNotIn(forbidden_score, json.dumps(qa_gate, sort_keys=True))
        self.assertNotIn("aggregate", qa_report.split("does not establish aggregate effectiveness")[0].lower())
        self.assertNotIn("ranking", qa_report.split("does not establish ranking quality")[0].lower())

        gate_source = inspect.getsource(truth.build_deployed_rule_outcome_truth_record_set_qa_gate)
        report_source = inspect.getsource(truth.format_deployed_rule_outcome_truth_record_set_qa_gate_report)
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

        existing_write_source = inspect.getsource(truth.register_deployed_rule_outcome_truth_record_set)
        existing_read_source = inspect.getsource(truth.load_deployed_rule_outcome_truth_record_set)
        existing_list_source = inspect.getsource(truth.list_deployed_rule_outcome_truth_record_sets)
        self.assertIn("_ensure_dirs(", existing_write_source)
        self.assertNotIn("_ensure_dirs(", existing_read_source)
        self.assertNotIn("_ensure_dirs(", existing_list_source)

        doc_text = Path("docs/PHASE_11A_OUTCOME_TRUTH_RECORD_SET_QA_GATE.md").read_text(encoding="utf-8")
        self.assertIn("The QA gate checks structural and internal consistency of outcome-truth record sets only.", doc_text)
        self.assertIn("It does not prove factual correctness of the outcome-truth records.", doc_text)
        self.assertIn("It performs no writes and creates no storage.", doc_text)
        self.assertIn("Phase 11B", doc_text)

    def test_outcome_truth_record_set_qa_api_ui_seam_is_read_only_and_no_overclaim(self) -> None:
        self.assertTrue(callable(truth.build_deployed_rule_outcome_truth_record_set_qa_gate))
        self.assertTrue(callable(truth.format_deployed_rule_outcome_truth_record_set_qa_gate_report))
        self.assertTrue(callable(api.build_deployed_rule_outcome_truth_record_set_qa_gate))
        self.assertTrue(callable(api.format_deployed_rule_outcome_truth_record_set_qa_gate_report))

        gate_signature = inspect.signature(api.build_deployed_rule_outcome_truth_record_set_qa_gate)
        report_signature = inspect.signature(api.format_deployed_rule_outcome_truth_record_set_qa_gate_report)
        self.assertEqual(set(gate_signature.parameters), {"outcome_truth_record_set_id", "root"})
        self.assertEqual(set(report_signature.parameters), {"outcome_truth_record_set_id", "root"})
        for forbidden_parameter in (
            "score",
            "score_value",
            "ratio",
            "percentage",
            "numerator",
            "denominator",
            "metric",
            "metric_family",
            "authority_scope",
            "manual_score",
            "override",
            "force",
            "aggregate_method",
            "ranking_method",
            "factual_truth_override",
            "correct_outcome_override",
            "expected_outcome_override",
            "actual_outcome_override",
            "register",
            "write",
            "repair",
            "migrate",
        ):
            self.assertNotIn(forbidden_parameter, gate_signature.parameters)
            self.assertNotIn(forbidden_parameter, report_signature.parameters)

        api_gate_source = inspect.getsource(api.build_deployed_rule_outcome_truth_record_set_qa_gate)
        api_report_source = inspect.getsource(api.format_deployed_rule_outcome_truth_record_set_qa_gate_report)
        desktop_source = inspect.getsource(desktop_panel)
        desktop_validate_source = inspect.getsource(desktop_panel.DesktopRightPanelMixin._validate_deployed_rule_outcome_truth_inputs)
        desktop_action_source = inspect.getsource(desktop_panel.DesktopRightPanelMixin._run_pdf_viewport_action)
        desktop_status_source = inspect.getsource(desktop_panel.DesktopRightPanelMixin._set_deployed_rule_outcome_truth_status)
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
        self.assertIn("Outcome-Truth Record-Set QA", desktop_source)
        self.assertIn("Load Outcome-Truth Record-Set QA Gate", desktop_source)
        self.assertIn("Copy Outcome-Truth Record-Set QA Report", desktop_source)
        self.assertIn("outcome_truth_record_set_id_required", desktop_validate_source)
        self.assertIn("load_deployed_rule_outcome_truth_record_set_qa_gate", desktop_action_source)
        self.assertIn("copy_deployed_rule_outcome_truth_record_set_qa_gate_report", desktop_action_source)
        self.assertIn("Writes Performed:", desktop_status_source)
        self.assertIn("Limitations:", desktop_status_source)
        self.assertIn("Recommended Action:", desktop_status_source)
        self.assertNotIn("Force Score", desktop_source)
        self.assertNotIn("Override Score", desktop_source)
        self.assertNotIn("Manual Score", desktop_source)
        self.assertNotIn("Aggregate Score", desktop_source)
        self.assertNotIn("Rank Results", desktop_source)
        self.assertNotIn("Compare Results", desktop_source)
        self.assertNotIn("Repair Record Set", desktop_source)
        self.assertNotIn("Migrate Record Set", desktop_source)
        self.assertNotIn("Register From QA", desktop_source)

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

        def _clipboard_clear() -> None:
            panel.clipboard_value = ""

        def _clipboard_append(text: str) -> None:
            panel.clipboard_value = text

        panel.clipboard_clear = _clipboard_clear
        panel.clipboard_append = _clipboard_append
        panel._validate_deployed_rule_outcome_truth_inputs = desktop_panel.DesktopRightPanelMixin._validate_deployed_rule_outcome_truth_inputs.__get__(panel, _FakePanel)
        panel._set_deployed_rule_outcome_truth_status = desktop_panel.DesktopRightPanelMixin._set_deployed_rule_outcome_truth_status.__get__(panel, _FakePanel)
        panel._run_pdf_viewport_action = desktop_panel.DesktopRightPanelMixin._run_pdf_viewport_action.__get__(panel, _FakePanel)

        blocked = panel._validate_deployed_rule_outcome_truth_inputs("load_deployed_rule_outcome_truth_record_set_qa_gate")
        self.assertFalse(blocked)
        self.assertIn("outcome_truth_record_set_id_required", panel.deployed_rule_outcome_truth_status_var.get())
        self.assertIn("Writes Performed: 0", panel.deployed_rule_outcome_truth_status_var.get())
        self.assertIn("Effectiveness Score Calculated: no", panel.deployed_rule_outcome_truth_status_var.get())

        qa_payload = {
            "status": "passed",
            "outcome_truth_record_set_id": "set-1",
            "record_count": 3,
            "eligible_record_count": 2,
            "excluded_record_count": 1,
            "duplicate_record_count": 1,
            "conflict_count": 1,
            "missing_expected_outcome_count": 1,
            "missing_actual_outcome_count": 1,
            "missing_source_metadata_count": 1,
            "blockers": ["record_blocker"],
            "warnings": ["scope_warning"],
            "recommended_action": "Review structural blockers.",
            "limitations": ["It does not prove factual correctness."],
            "writes_performed": 0,
            "boundary_flags": truth._outcome_truth_record_set_qa_boundary_flags(),
        }
        panel._set_deployed_rule_outcome_truth_status(qa_payload)
        status_text = panel.deployed_rule_outcome_truth_status_var.get()
        self.assertIn("Eligible Record Count: 2", status_text)
        self.assertIn("Excluded Record Count: 1", status_text)
        self.assertIn("Duplicate Record Count: 1", status_text)
        self.assertIn("Conflict Count: 1", status_text)
        self.assertIn("Missing Expected Outcome Count: 1", status_text)
        self.assertIn("Source Metadata Warning Count: 1", status_text)
        self.assertIn("Recommended Action: Review structural blockers.", status_text)
        self.assertIn("Limitations: It does not prove factual correctness.", status_text)

        original_report = desktop_panel.format_deployed_rule_outcome_truth_record_set_qa_gate_report
        try:
            panel.deployed_rule_outcome_truth_record_set_id_var.set("set-1")

            def _fake_report(outcome_truth_record_set_id: str, *, root=Path("data/source_documents")) -> str:
                self.assertEqual(outcome_truth_record_set_id, "set-1")
                return "Outcome-truth QA report\nStatus: passed\nIt does not prove the factual correctness of outcome-truth records."

            desktop_panel.format_deployed_rule_outcome_truth_record_set_qa_gate_report = _fake_report
            panel._run_pdf_viewport_action("copy_deployed_rule_outcome_truth_record_set_qa_gate_report")
        finally:
            desktop_panel.format_deployed_rule_outcome_truth_record_set_qa_gate_report = original_report

        self.assertIn("factual correctness", panel.clipboard_value.lower())
        self.assertNotIn("{", panel.clipboard_value)
        self.assertNotIn("c:\\users\\", panel.clipboard_value.lower())
        self.assertNotIn("traceback", panel.clipboard_value.lower())

        doc_text = Path("docs/PHASE_11B_OUTCOME_TRUTH_RECORD_SET_QA_API_UI_SEAM.md").read_text(encoding="utf-8")
        self.assertIn("The API/UI seam exposes the structural Outcome-Truth Record-Set QA Gate only.", doc_text)
        self.assertIn("It does not prove factual correctness of outcome-truth records.", doc_text)
        self.assertIn("The seam is read-only and performs no registration, repair, migration, or scoring.", doc_text)
        self.assertIn("Phase 11C", doc_text)

    def test_outcome_truth_record_set_qa_export_operator_handoff_preserves_public_safe_read_only_boundaries(self) -> None:
        handoff_path = Path("docs/PHASE_11C_OUTCOME_TRUTH_RECORD_SET_QA_EXPORT_OPERATOR_HANDOFF.md")
        self.assertTrue(handoff_path.exists())
        handoff_doc = handoff_path.read_text(encoding="utf-8")
        doc_11a = Path("docs/PHASE_11A_OUTCOME_TRUTH_RECORD_SET_QA_GATE.md").read_text(encoding="utf-8")
        doc_11b = Path("docs/PHASE_11B_OUTCOME_TRUTH_RECORD_SET_QA_API_UI_SEAM.md").read_text(encoding="utf-8")

        for heading in (
            "## 1. Purpose",
            "## 2. Release Scope",
            "## 3. Operator Workflow",
            "## 4. Public-Safe QA Export / Report",
            "## 5. Allowed QA Fields and Counters",
            "## 6. Read-Only / No-Mutation Boundary",
            "## 7. Explicit Non-Claims",
            "## 8. API/UI Surface",
            "## 9. Validation Evidence",
            "## 10. Skipped Broad Tests by Policy",
            "## 11. Known Risks",
            "## 12. Recommended Next Phase",
        ):
            self.assertIn(heading, handoff_doc)

        self.assertIn(
            "This handoff describes the read-only structural Outcome-Truth Record-Set QA Gate and its API/UI seam.",
            handoff_doc,
        )
        self.assertIn(
            "The QA gate checks structural and internal consistency of outcome-truth record sets only.",
            handoff_doc,
        )
        self.assertIn("1. Enter Outcome Truth Record Set ID.", handoff_doc)
        self.assertIn("4. Copy Outcome-Truth Record-Set QA Report.", handoff_doc)
        self.assertIn("The QA report is the public-safe export surface.", handoff_doc)
        for field_name in (
            "record_count",
            "eligible_record_count",
            "excluded_record_count",
            "duplicate_record_count",
            "conflict_count",
            "missing_required_field_count",
            "missing_expected_outcome_count",
            "missing_actual_outcome_count",
            "invalid_outcome_value_count",
            "missing_source_metadata_count",
            "malformed_record_count",
        ):
            self.assertIn(field_name, handoff_doc)
        self.assertIn("writes_performed = 0", handoff_doc)
        self.assertIn("build_deployed_rule_outcome_truth_record_set_qa_gate", handoff_doc)
        self.assertIn("format_deployed_rule_outcome_truth_record_set_qa_gate_report", handoff_doc)
        self.assertIn("Load Outcome-Truth Record-Set QA Gate", handoff_doc)
        self.assertIn("Copy Outcome-Truth Record-Set QA Report", handoff_doc)
        self.assertIn("test_outcome_truth_record_set_qa_gate_is_read_only_structural_and_no_overclaim", handoff_doc)
        self.assertIn("test_outcome_truth_record_set_qa_api_ui_seam_is_read_only_and_no_overclaim", handoff_doc)
        self.assertIn("pytest", handoff_doc)
        self.assertIn("broad end-to-end record-set variants", handoff_doc)
        self.assertIn("Phase 11D", handoff_doc)
        self.assertIn("Operator handoff/export packet:", doc_11a)
        self.assertIn("Operator handoff/export packet:", doc_11b)

        self.assertTrue(callable(truth.build_deployed_rule_outcome_truth_record_set_qa_gate))
        self.assertTrue(callable(truth.format_deployed_rule_outcome_truth_record_set_qa_gate_report))
        self.assertTrue(callable(api.build_deployed_rule_outcome_truth_record_set_qa_gate))
        self.assertTrue(callable(api.format_deployed_rule_outcome_truth_record_set_qa_gate_report))

        desktop_source = inspect.getsource(desktop_panel)
        action_source = inspect.getsource(desktop_panel.DesktopRightPanelMixin._run_pdf_viewport_action)
        validate_source = inspect.getsource(desktop_panel.DesktopRightPanelMixin._validate_deployed_rule_outcome_truth_inputs)
        gate_source = inspect.getsource(truth.build_deployed_rule_outcome_truth_record_set_qa_gate)
        report_source = inspect.getsource(truth.format_deployed_rule_outcome_truth_record_set_qa_gate_report)
        api_gate_source = inspect.getsource(api.build_deployed_rule_outcome_truth_record_set_qa_gate)
        api_report_source = inspect.getsource(api.format_deployed_rule_outcome_truth_record_set_qa_gate_report)

        self.assertIn("Load Outcome-Truth Record-Set QA Gate", desktop_source)
        self.assertIn("Copy Outcome-Truth Record-Set QA Report", desktop_source)
        self.assertIn("load_deployed_rule_outcome_truth_record_set_qa_gate", action_source)
        self.assertIn("copy_deployed_rule_outcome_truth_record_set_qa_gate_report", action_source)
        self.assertIn("format_deployed_rule_outcome_truth_record_set_qa_gate_report(", action_source)
        self.assertNotIn("json.dumps(", action_source)
        self.assertIn("outcome_truth_record_set_id_required", validate_source)
        self.assertIn("self.deployed_rule_outcome_truth_record_set_id_var", validate_source)

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
            report = truth.format_deployed_rule_outcome_truth_record_set_qa_gate_report("missing-set", root=root)
            self.assertIn("Limitations:", report)
            self.assertIn("writes_performed", handoff_doc.lower())
            self.assertNotIn(str(root).lower(), report.lower())
            self.assertNotIn("c:\\users\\", report.lower())
            self.assertNotIn("/users/", report.lower())
            self.assertNotIn("/home/", report.lower())
            self.assertNotIn("traceback", report.lower())
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
        ):
            self.assertNotIn(forbidden_ui, desktop_source)

        handoff_lower = handoff_doc.lower()
        for forbidden_claim in (
            "factual truth correctness proven",
            "truth correctness proven",
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
        self.assertIn("does not validate factual truth", handoff_lower)
        self.assertIn("factual truth correctness", handoff_lower)
        self.assertIn("broad rule effectiveness", handoff_lower)
        self.assertIn("production correctness", handoff_lower)
        self.assertIn("deployment safety", handoff_lower)
        self.assertIn("profitability", handoff_lower)
        self.assertIn("prediction quality", handoff_lower)
        self.assertIn("future performance", handoff_lower)
        self.assertIn("aggregate effectiveness", handoff_lower)
        self.assertIn("ranking quality", handoff_lower)

    def test_outcome_truth_record_set_qa_release_packet_and_final_freeze_preserve_boundaries(self) -> None:
        release_path = Path("docs/PHASE_11D_OUTCOME_TRUTH_RECORD_SET_QA_RELEASE_PACKET.md")
        self.assertTrue(release_path.exists())
        release_doc = release_path.read_text(encoding="utf-8")
        doc_11a = Path("docs/PHASE_11A_OUTCOME_TRUTH_RECORD_SET_QA_GATE.md").read_text(encoding="utf-8")
        doc_11b = Path("docs/PHASE_11B_OUTCOME_TRUTH_RECORD_SET_QA_API_UI_SEAM.md").read_text(encoding="utf-8")
        doc_11c = Path("docs/PHASE_11C_OUTCOME_TRUTH_RECORD_SET_QA_EXPORT_OPERATOR_HANDOFF.md").read_text(encoding="utf-8")

        for heading in (
            "## 1. Release Scope",
            "## 2. Feature Surface",
            "## 3. Operator Workflow",
            "## 4. QA Checks and Counters",
            "## 5. Public-Safe QA Report",
            "## 6. Read-Only / No-Mutation Boundary",
            "## 7. API/UI Surface",
            "## 8. Explicit Non-Claims",
            "## 9. Validation Evidence",
            "## 10. Skipped Broad Tests by Policy",
            "## 11. Known Risks",
            "## 12. Final Freeze Status",
            "## 13. Recommended Next Phase",
        ):
            self.assertIn(heading, release_doc)

        self.assertIn("This release covers the read-only structural Outcome-Truth Record-Set QA Gate.", release_doc)
        self.assertIn("The QA gate checks structural and internal consistency of outcome-truth record sets only.", release_doc)
        self.assertIn("It does not validate factual truth.", release_doc)
        self.assertIn("build_deployed_rule_outcome_truth_record_set_qa_gate", release_doc)
        self.assertIn("format_deployed_rule_outcome_truth_record_set_qa_gate_report", release_doc)
        self.assertIn("Load Outcome-Truth Record-Set QA Gate", release_doc)
        self.assertIn("Copy Outcome-Truth Record-Set QA Report", release_doc)
        self.assertIn("1. Enter Outcome Truth Record Set ID.", release_doc)
        self.assertIn("4. Copy Outcome-Truth Record-Set QA Report.", release_doc)
        self.assertIn("No confirmation is required.", release_doc)
        self.assertIn("No scoring occurs.", release_doc)
        self.assertIn("No registration occurs.", release_doc)
        self.assertIn("No repair occurs.", release_doc)
        self.assertIn("No migration occurs.", release_doc)
        self.assertIn("Raw JSON is not copied.", release_doc)
        for field_name in (
            "loadability",
            "record_count",
            "eligible_record_count",
            "excluded_record_count",
            "duplicate_record_count",
            "conflict_count",
            "missing_required_field_count",
            "missing_expected_outcome_count",
            "missing_actual_outcome_count",
            "invalid_outcome_value_count",
            "missing_source_metadata_count",
            "malformed_record_count",
            "mixed-scope warnings",
            "blockers",
            "warnings",
            "recommended_action",
            "limitations",
            "writes_performed",
        ):
            self.assertIn(field_name, release_doc)
        self.assertIn("writes_performed = 0", release_doc)
        self.assertIn("API wrappers accept only the record-set ID and optional test root.", release_doc)
        self.assertIn("Missing Outcome Truth Record Set ID blocks explicitly.", release_doc)
        self.assertIn("Stale-state includes Outcome Truth Record Set ID.", release_doc)
        self.assertIn("Copy action uses formatter, not raw JSON.", release_doc)
        self.assertIn("test_outcome_truth_record_set_qa_gate_is_read_only_structural_and_no_overclaim", release_doc)
        self.assertIn("test_outcome_truth_record_set_qa_api_ui_seam_is_read_only_and_no_overclaim", release_doc)
        self.assertIn("test_outcome_truth_record_set_qa_export_operator_handoff_preserves_public_safe_read_only_boundaries", release_doc)
        self.assertIn("Phase 12A - Outcome-Truth Record-Set Registration Pipeline QA Gate", release_doc)
        self.assertIn("Backend QA gate: frozen", release_doc)
        self.assertIn("API/UI seam: frozen", release_doc)
        self.assertIn("Operator handoff/report surface: frozen", release_doc)
        self.assertIn("Authority: structural QA only", release_doc)
        self.assertIn("No-overclaim boundary: preserved", release_doc)

        self.assertIn("Final release packet:", doc_11a)
        self.assertIn("Final release packet:", doc_11b)
        self.assertIn("Final release packet:", doc_11c)

        self.assertTrue(callable(truth.build_deployed_rule_outcome_truth_record_set_qa_gate))
        self.assertTrue(callable(truth.format_deployed_rule_outcome_truth_record_set_qa_gate_report))
        self.assertTrue(callable(api.build_deployed_rule_outcome_truth_record_set_qa_gate))
        self.assertTrue(callable(api.format_deployed_rule_outcome_truth_record_set_qa_gate_report))

        gate_source = inspect.getsource(truth.build_deployed_rule_outcome_truth_record_set_qa_gate)
        report_source = inspect.getsource(truth.format_deployed_rule_outcome_truth_record_set_qa_gate_report)
        api_gate_source = inspect.getsource(api.build_deployed_rule_outcome_truth_record_set_qa_gate)
        api_report_source = inspect.getsource(api.format_deployed_rule_outcome_truth_record_set_qa_gate_report)
        desktop_source = inspect.getsource(desktop_panel)
        desktop_action_source = inspect.getsource(desktop_panel.DesktopRightPanelMixin._run_pdf_viewport_action)
        desktop_validate_source = inspect.getsource(desktop_panel.DesktopRightPanelMixin._validate_deployed_rule_outcome_truth_inputs)

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

        self.assertIn("Load Outcome-Truth Record-Set QA Gate", desktop_source)
        self.assertIn("Copy Outcome-Truth Record-Set QA Report", desktop_source)
        self.assertIn("load_deployed_rule_outcome_truth_record_set_qa_gate", desktop_action_source)
        self.assertIn("copy_deployed_rule_outcome_truth_record_set_qa_gate_report", desktop_action_source)
        self.assertIn("format_deployed_rule_outcome_truth_record_set_qa_gate_report(", desktop_action_source)
        self.assertNotIn("json.dumps(", desktop_action_source)
        self.assertIn("outcome_truth_record_set_id_required", desktop_validate_source)
        self.assertIn("self.deployed_rule_outcome_truth_record_set_id_var", desktop_validate_source)

        for forbidden_surface in (
            "force_score",
            "override_score",
            "manual_score",
            "recalculate_score",
            "aggregate_score",
            "rank_results",
            "compare_results",
            "factual_truth_override",
            "correct_outcome_override",
            "expected_outcome_override",
            "actual_outcome_override",
            "repair_record_set",
            "migrate_record_set",
            "register_from_qa",
        ):
            self.assertNotIn(forbidden_surface, api_gate_source)
            self.assertNotIn(forbidden_surface, api_report_source)
            self.assertNotIn(forbidden_surface, desktop_source)

        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            report = truth.format_deployed_rule_outcome_truth_record_set_qa_gate_report("missing-set", root=root)
            report_lower = report.lower()
            self.assertIn("limitations:", report_lower)
            self.assertIn("writes performed: 0", report_lower)
            self.assertNotIn(str(root).lower(), report_lower)
            self.assertNotIn("c:\\users\\", report_lower)
            self.assertNotIn("/users/", report_lower)
            self.assertNotIn("/home/", report_lower)
            self.assertNotIn("{", report)
            self.assertNotIn('"expected_outcome"', report_lower)
            self.assertNotIn("traceback", report_lower)

        release_lower = release_doc.lower()
        for forbidden_claim in (
            "factual truth correctness proven",
            "truth correctness proven",
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
        for allowed_non_claim in (
            "factual truth correctness",
            "broad rule effectiveness",
            "production correctness",
            "deployment safety",
            "profitability",
            "prediction quality",
            "future performance",
            "aggregate effectiveness",
            "ranking quality",
            "broad regression safety",
        ):
            self.assertIn(allowed_non_claim, release_lower)

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
            self.assertNotIn(forbidden_score, release_doc)
