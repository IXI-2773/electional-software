from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from backend.electional import certified_rule_post_deployment_acceptance as acceptance
from backend.electional import api as api_module
from backend.electional import desktop_right_panel
from backend.electional import deployed_rule_effectiveness_readiness as readiness
from backend.electional import deployed_rule_execution_runtime as runtime
from backend.electional import deployed_rule_operational_telemetry as telemetry
from backend.tests.test_certified_rule_post_deployment_acceptance import _deployed_inputs


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


def _record_attempts(root: Path, built: dict[str, object], count: int, *, start_hour: int = 10) -> None:
    for offset in range(count):
        runtime.execute_deployed_rule(
            built["rule_id"],
            built["production_deployment_run"]["production_deployment_result_id"],
            "production_target_primary",
            built["production_deployment_run"]["deployed_rule_id"],
            execution_input={"score": 7 + offset},
            record_operational_telemetry=True,
            _testing_observed_at=f"2026-07-10T{start_hour + (offset // 60):02d}:{offset % 60:02d}:00Z",
            root=root,
        )


def _snapshot(root: Path, built: dict[str, object]) -> dict[str, object]:
    return telemetry.build_deployed_rule_operational_snapshot(
        built["production_deployment_run"]["deployed_rule_id"],
        built["production_deployment_run"]["production_deployment_result_id"],
        start_timestamp="2026-07-10T10:00:00Z",
        end_timestamp="2026-07-10T12:59:00Z",
        root=root,
    )


class DeployedRuleEffectivenessReadinessTest(TestCase):
    class _Var:
        def __init__(self, value: str = "") -> None:
            self.value = value
            self._traces = []

        def get(self) -> str:
            return self.value

        def set(self, value: str) -> None:
            self.value = value
            for callback in list(self._traces):
                callback("var", "", "write")

        def trace_add(self, _mode: str, callback) -> str:
            self._traces.append(callback)
            return f"trace_{len(self._traces)}"

    class _Panel:
        def __init__(self) -> None:
            self.status_var = DeployedRuleEffectivenessReadinessTest._Var("")
            self.pdf_viewport_id_var = DeployedRuleEffectivenessReadinessTest._Var("")
            self.deployed_rule_effectiveness_readiness_rule_id_var = DeployedRuleEffectivenessReadinessTest._Var("canonical_rule_1")
            self.deployed_rule_effectiveness_readiness_result_id_var = DeployedRuleEffectivenessReadinessTest._Var("deployment_result_1")
            self.deployed_rule_effectiveness_readiness_target_id_var = DeployedRuleEffectivenessReadinessTest._Var("production_target_primary")
            self.deployed_rule_effectiveness_readiness_deployed_rule_id_var = DeployedRuleEffectivenessReadinessTest._Var("deployed_rule_1")
            self.deployed_rule_effectiveness_readiness_snapshot_id_var = DeployedRuleEffectivenessReadinessTest._Var("snapshot_1")
            self.deployed_rule_effectiveness_readiness_start_var = DeployedRuleEffectivenessReadinessTest._Var("2026-07-10T10:00:00Z")
            self.deployed_rule_effectiveness_readiness_end_var = DeployedRuleEffectivenessReadinessTest._Var("2026-07-10T12:59:00Z")
            self.deployed_rule_effectiveness_readiness_phase_9w_result_id_var = DeployedRuleEffectivenessReadinessTest._Var("")
            self.deployed_rule_effectiveness_readiness_plan_id_var = DeployedRuleEffectivenessReadinessTest._Var("readiness_plan_1")
            self.deployed_rule_effectiveness_readiness_loaded_result_id_var = DeployedRuleEffectivenessReadinessTest._Var("readiness_result_1")
            self.deployed_rule_effectiveness_readiness_confirmation_var = DeployedRuleEffectivenessReadinessTest._Var("RECORD_EFFECTIVENESS_READINESS_RESULT")
            self.deployed_rule_effectiveness_readiness_status_var = DeployedRuleEffectivenessReadinessTest._Var("")
            self.copied_text = ""
            self._deployed_rule_effectiveness_readiness_traces_registered = False

        def clipboard_clear(self) -> None:
            self.copied_text = ""

        def clipboard_append(self, text: str) -> None:
            self.copied_text = text

        def _current_source_document_id(self) -> str:
            return "document_1"

        _deployed_rule_effectiveness_readiness_common_kwargs = desktop_right_panel.DesktopRightPanelMixin._deployed_rule_effectiveness_readiness_common_kwargs
        _register_deployed_rule_effectiveness_readiness_traces = desktop_right_panel.DesktopRightPanelMixin._register_deployed_rule_effectiveness_readiness_traces
        _on_deployed_rule_effectiveness_readiness_input_changed = desktop_right_panel.DesktopRightPanelMixin._on_deployed_rule_effectiveness_readiness_input_changed
        _mark_deployed_rule_effectiveness_readiness_stale = desktop_right_panel.DesktopRightPanelMixin._mark_deployed_rule_effectiveness_readiness_stale
        _validate_deployed_rule_effectiveness_readiness_inputs = desktop_right_panel.DesktopRightPanelMixin._validate_deployed_rule_effectiveness_readiness_inputs
        _set_deployed_rule_effectiveness_readiness_status = desktop_right_panel.DesktopRightPanelMixin._set_deployed_rule_effectiveness_readiness_status

    def test_no_execution_producer_blocks_readiness_without_effectiveness(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            snapshot = _snapshot(root, built)
            with patch.object(readiness.telemetry_backend, "get_deployed_rule_operational_telemetry_manifest", return_value={"producers": [], "effectiveness_evaluation_status": "not_performed", "manifest_fingerprint": "missing"}):
                eligibility = readiness.validate_deployed_rule_effectiveness_readiness_eligibility(
                    built["rule_id"],
                    built["production_deployment_run"]["production_deployment_result_id"],
                    "production_target_primary",
                    built["production_deployment_run"]["deployed_rule_id"],
                    snapshot["snapshot_id"],
                    "2026-07-10T10:00:00Z",
                    "2026-07-10T12:59:00Z",
                    root=root,
                )
        self.assertEqual(eligibility["status"], "blocked_no_execution_producer")
        self.assertEqual(eligibility["effectiveness_evaluation_status"], "not_performed")

    def test_execution_producer_with_no_events_blocks_readiness(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            snapshot = _snapshot(root, built)
            eligibility = readiness.validate_deployed_rule_effectiveness_readiness_eligibility(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                snapshot["snapshot_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
        self.assertEqual(eligibility["status"], "blocked_no_execution_events")
        self.assertIn("execution_events_absent", eligibility["blockers"])

    def test_valid_execution_events_below_sample_threshold_returns_not_ready(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            _record_attempts(root, built, 5)
            snapshot = _snapshot(root, built)
            eligibility = readiness.validate_deployed_rule_effectiveness_readiness_eligibility(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                snapshot["snapshot_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
        self.assertEqual(eligibility["status"], "not_ready")
        self.assertEqual(eligibility["valid_execution_attempt_count"], 5)
        self.assertEqual(eligibility["sample_sufficiency_status"], "not_met")

    def test_valid_execution_snapshot_builds_deterministic_readiness_plan(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            _record_attempts(root, built, 5)
            snapshot = _snapshot(root, built)
            first = readiness.build_deployed_rule_effectiveness_readiness_plan(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                snapshot["snapshot_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            second = readiness.build_deployed_rule_effectiveness_readiness_plan(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                snapshot["snapshot_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
        self.assertEqual(first["status"], "planned")
        self.assertEqual(second["writes_performed"], 0)
        self.assertEqual(first["plan_fingerprint"], second["plan_fingerprint"])

    def test_ready_status_requires_minimum_valid_execution_attempts(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            _record_attempts(root, built, readiness.MINIMUM_EXECUTION_ATTEMPTS)
            snapshot = _snapshot(root, built)
            eligibility = readiness.validate_deployed_rule_effectiveness_readiness_eligibility(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                snapshot["snapshot_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
        self.assertEqual(eligibility["status"], "ready_for_effectiveness_evaluation")
        self.assertEqual(eligibility["valid_execution_attempt_count"], readiness.MINIMUM_EXECUTION_ATTEMPTS)

    def test_phase_9w_acceptance_is_not_effectiveness_evidence(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            acceptance_plan = acceptance.build_certified_rule_post_deployment_acceptance_plan(
                built["production_deployment_run"]["production_deployment_result_id"],
                root=root,
            )
            acceptance_result = acceptance.save_certified_rule_post_deployment_acceptance_decision(
                acceptance_plan["post_deployment_acceptance_plan_id"],
                "accept",
                confirmation=acceptance.REQUIRED_CONFIRMATION,
                root=root,
            )
            _record_attempts(root, built, 3)
            snapshot = _snapshot(root, built)
            eligibility = readiness.validate_deployed_rule_effectiveness_readiness_eligibility(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                snapshot["snapshot_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                post_deployment_result_id=acceptance_result["post_deployment_acceptance_result_id"],
                root=root,
            )
        self.assertTrue(eligibility["criteria"]["phase_9w_not_used_as_effectiveness_evidence"])
        self.assertEqual(eligibility["status"], "not_ready")
        self.assertEqual(eligibility["valid_execution_attempt_count"], 3)

    def test_readiness_result_requires_confirmation_and_is_immutable(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            _record_attempts(root, built, readiness.MINIMUM_EXECUTION_ATTEMPTS)
            snapshot = _snapshot(root, built)
            plan = readiness.build_deployed_rule_effectiveness_readiness_plan(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                snapshot["snapshot_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            blocked = readiness.record_deployed_rule_effectiveness_readiness_result(
                plan["effectiveness_readiness_plan_id"],
                confirmation="WRONG",
                root=root,
            )
            first = readiness.record_deployed_rule_effectiveness_readiness_result(
                plan["effectiveness_readiness_plan_id"],
                confirmation=readiness.REQUIRED_CONFIRMATION,
                root=root,
            )
            second = readiness.record_deployed_rule_effectiveness_readiness_result(
                plan["effectiveness_readiness_plan_id"],
                confirmation=readiness.REQUIRED_CONFIRMATION,
                root=root,
            )
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(first["status"], "ready_for_effectiveness_evaluation")
        self.assertEqual(second["status"], "already_recorded")
        self.assertEqual(second["writes_performed"], 0)

    def test_readiness_does_not_mutate_deployment_canonical_phase9v_phase9w_or_telemetry_state(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            _record_attempts(root, built, 2)
            snapshot = _snapshot(root, built)
            before = _tracked_state(root)
            plan = readiness.build_deployed_rule_effectiveness_readiness_plan(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                snapshot["snapshot_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            readiness.record_deployed_rule_effectiveness_readiness_result(
                plan["effectiveness_readiness_plan_id"],
                confirmation=readiness.REQUIRED_CONFIRMATION,
                root=root,
            )
            after = _tracked_state(root)
        self.assertEqual(before, after)

    def test_api_wrappers_and_desktop_readiness_seam_follow_backend_contract(self) -> None:
        self.assertIs(api_module.build_deployed_rule_effectiveness_readiness_workspace, readiness.build_deployed_rule_effectiveness_readiness_workspace)
        self.assertIs(api_module.validate_deployed_rule_effectiveness_readiness_eligibility, readiness.validate_deployed_rule_effectiveness_readiness_eligibility)
        self.assertIs(api_module.build_deployed_rule_effectiveness_readiness_plan, readiness.build_deployed_rule_effectiveness_readiness_plan)
        self.assertIs(api_module.record_deployed_rule_effectiveness_readiness_result, readiness.record_deployed_rule_effectiveness_readiness_result)
        self.assertIs(api_module.load_deployed_rule_effectiveness_readiness_result, readiness.load_deployed_rule_effectiveness_readiness_result)
        self.assertIs(api_module.get_deployed_rule_effectiveness_readiness_health, readiness.get_deployed_rule_effectiveness_readiness_health)
        self.assertIs(api_module.format_deployed_rule_effectiveness_readiness_report, readiness.format_deployed_rule_effectiveness_readiness_report)
        self.assertIs(api_module.get_deployed_rule_effectiveness_readiness_manifest, readiness.get_deployed_rule_effectiveness_readiness_manifest)

        build_source = Path(desktop_right_panel.__file__).read_text(encoding="utf-8")
        self.assertIn("Deployed Rule Effectiveness Readiness", build_source)
        for label in (
            "Canonical Rule ID",
            "Phase 9V Deployment Result ID",
            "Production Target ID",
            "Deployed Rule ID",
            "Telemetry Snapshot ID",
            "Observation Start",
            "Observation End",
            "Optional Phase 9W Result ID",
            "Readiness Plan ID",
            "Readiness Result ID",
            "Confirmation",
            "Load Readiness Workspace",
            "Validate Readiness Eligibility",
            "Build Readiness Plan",
            "Load Readiness Result",
            "Record Readiness Result",
            "Readiness Health",
            "Copy Readiness Report",
        ):
            self.assertIn(label, build_source)
        for forbidden in (
            "Force Readiness",
            "Force Effectiveness",
            "Record Readiness Event",
            "Trigger Readiness Execution",
        ):
            self.assertNotIn(forbidden, build_source)

        panel = self._Panel()
        panel._register_deployed_rule_effectiveness_readiness_traces()
        panel.deployed_rule_effectiveness_readiness_rule_id_var.set("changed_rule")
        self.assertIn("stale_due_to_input_change", panel.deployed_rule_effectiveness_readiness_status_var.get())
        self.assertIn("not_performed", panel.deployed_rule_effectiveness_readiness_status_var.get())

        panel.deployed_rule_effectiveness_readiness_rule_id_var.set("")
        panel.deployed_rule_effectiveness_readiness_result_id_var.set("")
        with patch.object(desktop_right_panel, "build_deployed_rule_effectiveness_readiness_workspace", side_effect=AssertionError("wrapper should not be called when required ids are missing")):
            desktop_right_panel.DesktopRightPanelMixin._run_pdf_viewport_action(panel, "load_deployed_rule_effectiveness_readiness_workspace")
        self.assertIn("blocked", panel.deployed_rule_effectiveness_readiness_status_var.get())
        self.assertIn("canonical_rule_id", panel.deployed_rule_effectiveness_readiness_status_var.get())
        self.assertIn("production_deployment_result_id", panel.deployed_rule_effectiveness_readiness_status_var.get())

        panel.deployed_rule_effectiveness_readiness_rule_id_var.set("canonical_rule_1")
        panel.deployed_rule_effectiveness_readiness_result_id_var.set("deployment_result_1")
        panel.deployed_rule_effectiveness_readiness_loaded_result_id_var.set("")
        with patch.object(desktop_right_panel, "load_deployed_rule_effectiveness_readiness_result", side_effect=AssertionError("result wrapper should not be called without result id")):
            desktop_right_panel.DesktopRightPanelMixin._run_pdf_viewport_action(panel, "load_deployed_rule_effectiveness_readiness_result")
        self.assertIn("effectiveness_readiness_result_id", panel.deployed_rule_effectiveness_readiness_status_var.get())
        panel.deployed_rule_effectiveness_readiness_loaded_result_id_var.set("readiness_result_1")
        panel.deployed_rule_effectiveness_readiness_confirmation_var.set("WRONG")
        with patch.object(desktop_right_panel, "record_deployed_rule_effectiveness_readiness_result", side_effect=AssertionError("record wrapper should not be called with wrong confirmation")):
            desktop_right_panel.DesktopRightPanelMixin._run_pdf_viewport_action(panel, "record_deployed_rule_effectiveness_readiness_result")
        self.assertIn("confirmation_exact_match_required", panel.deployed_rule_effectiveness_readiness_status_var.get())

        panel.deployed_rule_effectiveness_readiness_confirmation_var.set("RECORD_EFFECTIVENESS_READINESS_RESULT")
        with patch.object(desktop_right_panel, "load_deployed_rule_effectiveness_readiness_result", return_value={"status": "ready_for_effectiveness_evaluation", "effectiveness_readiness_result": {"effectiveness_readiness_result_id": "readiness_result_1", "effectiveness_readiness_plan_id": "readiness_plan_1", "execution_event_count": 30, "valid_execution_attempt_count": 30, "sample_sufficiency_status": "met", "denominator_readiness": "ready", "effectiveness_evaluation_status": "not_performed", "warnings": [], "blockers": []}}) as load_mock:
            desktop_right_panel.DesktopRightPanelMixin._run_pdf_viewport_action(panel, "load_deployed_rule_effectiveness_readiness_result")
        load_mock.assert_called_once_with("readiness_result_1")
        self.assertIn("not_performed", panel.deployed_rule_effectiveness_readiness_status_var.get())
        with patch.object(desktop_right_panel, "format_deployed_rule_effectiveness_readiness_report", return_value="Effectiveness evaluation status: not_performed") as report_mock:
            desktop_right_panel.DesktopRightPanelMixin._run_pdf_viewport_action(panel, "copy_deployed_rule_effectiveness_readiness_report")
        report_mock.assert_called_once()
        self.assertEqual(panel.copied_text, "Effectiveness evaluation status: not_performed")
        panel._set_deployed_rule_effectiveness_readiness_status({"status": "healthy", "readiness_health": "healthy", "health_scope": "repository-wide", "effectiveness_evaluation_status": "not_performed", "warnings": [], "blockers": []})
        self.assertIn("Health Scope: repository-wide", panel.deployed_rule_effectiveness_readiness_status_var.get())

    def test_readiness_reports_and_docs_keep_boundary_separate_from_effectiveness(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            _record_attempts(root, built, readiness.MINIMUM_EXECUTION_ATTEMPTS)
            snapshot = _snapshot(root, built)
            report = readiness.format_deployed_rule_effectiveness_readiness_report(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                snapshot["snapshot_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
        docs_text = Path("docs/DEPLOYED_RULE_EFFECTIVENESS_READINESS.md").read_text(encoding="utf-8").lower()
        self.assertIn("eligible for later effectiveness evaluation only", report.lower())
        self.assertIn("evaluation_completed means runtime returned normally", report)
        self.assertIn("evaluation_failed means runtime failed", report)
        self.assertIn("unavailable, not zero effectiveness", report.lower())
        self.assertNotIn("success rate", report.lower())
        self.assertNotIn("failure rate", report.lower())
        self.assertNotIn("correctness rate", report.lower())
        self.assertIn("gate only", docs_text)
        self.assertIn("not zero effectiveness", docs_text)
        self.assertIn("not treated as success", docs_text)
