from __future__ import annotations

import inspect
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from backend.electional import deployed_rule_operational_telemetry as telemetry
from backend.electional import deployed_rule_execution_runtime as execution_runtime
from backend.electional import desktop_right_panel
from backend.electional.api import (
    build_deployed_rule_operational_snapshot as api_build_snapshot,
    build_deployed_rule_operational_telemetry_workspace as api_workspace,
    format_deployed_rule_operational_telemetry_report as api_report,
    get_deployed_rule_operational_telemetry_health as api_health,
    list_deployed_rule_operational_events as api_list_events,
    validate_deployed_rule_operational_telemetry_eligibility as api_validate,
)
from backend.tests.test_certified_rule_post_deployment_acceptance import _deployed_inputs
from backend.tests.test_certified_rule_controlled_integration import _write_json


def _core_state(root: Path) -> dict[str, str]:
    tracked_dirs = [
        "canonical_rules",
        "production_activation_transactions",
        "certified_rule_production_deployment_plans",
        "certified_rule_production_deployment_results",
        "certified_rule_production_deployment_receipts",
        "certified_rule_post_deployment_acceptance_plans",
        "certified_rule_post_deployment_acceptance_results",
        "certified_rule_post_deployment_acceptance_receipts",
    ]
    snapshot: dict[str, str] = {}
    for folder in tracked_dirs:
        path = root / folder
        if not path.exists():
            continue
        for file in sorted(path.glob("*.json")):
            snapshot[str(file.relative_to(root))] = file.read_text(encoding="utf-8")
    return snapshot


class DeployedRuleOperationalTelemetryTest(TestCase):
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
            self.status_var = DeployedRuleOperationalTelemetryTest._Var("")
            self.deployed_rule_operational_telemetry_rule_id_var = DeployedRuleOperationalTelemetryTest._Var("canonical_rule_1")
            self.deployed_rule_operational_telemetry_result_id_var = DeployedRuleOperationalTelemetryTest._Var("deployment_result_1")
            self.deployed_rule_operational_telemetry_phase_9w_result_id_var = DeployedRuleOperationalTelemetryTest._Var("phase9w_1")
            self.deployed_rule_operational_telemetry_target_id_var = DeployedRuleOperationalTelemetryTest._Var("production_target_primary")
            self.deployed_rule_operational_telemetry_deployed_rule_id_var = DeployedRuleOperationalTelemetryTest._Var("deployed_rule_1")
            self.deployed_rule_operational_telemetry_start_var = DeployedRuleOperationalTelemetryTest._Var("2026-07-08T10:00:00Z")
            self.deployed_rule_operational_telemetry_end_var = DeployedRuleOperationalTelemetryTest._Var("2026-07-08T11:00:00Z")
            self.deployed_rule_operational_telemetry_event_type_var = DeployedRuleOperationalTelemetryTest._Var("deployment_state_observed")
            self.deployed_rule_operational_telemetry_producer_var = DeployedRuleOperationalTelemetryTest._Var(telemetry.STATE_PRODUCER_ID)
            self.deployed_rule_operational_telemetry_max_results_var = DeployedRuleOperationalTelemetryTest._Var("12")
            self.deployed_rule_operational_telemetry_status_var = DeployedRuleOperationalTelemetryTest._Var("")
            self.copied_text = ""
            self.last_telemetry_payload = None
            self._deployed_rule_operational_telemetry_traces_registered = False

        def clipboard_clear(self) -> None:
            self.copied_text = ""

        def clipboard_append(self, text: str) -> None:
            self.copied_text = text

        def _current_source_document_id(self) -> str:
            return "document_1"

        def _current_viewport_id(self) -> str:
            return ""

        def _set_deployed_rule_operational_telemetry_status(self, payload: dict[str, object] | None) -> None:
            self.last_telemetry_payload = payload

        _deployed_rule_operational_telemetry_common_kwargs = desktop_right_panel.DesktopRightPanelMixin._deployed_rule_operational_telemetry_common_kwargs
        _deployed_rule_operational_telemetry_max_results = desktop_right_panel.DesktopRightPanelMixin._deployed_rule_operational_telemetry_max_results
        _deployed_rule_operational_telemetry_list_kwargs = desktop_right_panel.DesktopRightPanelMixin._deployed_rule_operational_telemetry_list_kwargs
        _deployed_rule_operational_telemetry_snapshot_kwargs = desktop_right_panel.DesktopRightPanelMixin._deployed_rule_operational_telemetry_snapshot_kwargs
        _register_deployed_rule_operational_telemetry_traces = desktop_right_panel.DesktopRightPanelMixin._register_deployed_rule_operational_telemetry_traces
        _on_deployed_rule_operational_telemetry_input_changed = desktop_right_panel.DesktopRightPanelMixin._on_deployed_rule_operational_telemetry_input_changed
        _mark_deployed_rule_operational_telemetry_stale = desktop_right_panel.DesktopRightPanelMixin._mark_deployed_rule_operational_telemetry_stale
        _validate_deployed_rule_operational_telemetry_inputs = desktop_right_panel.DesktopRightPanelMixin._validate_deployed_rule_operational_telemetry_inputs

    def test_manifest_workspace_and_eligibility_bind_one_completed_phase_9v_deployment_without_production_writes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            before = _core_state(root)
            manifest = telemetry.get_deployed_rule_operational_telemetry_manifest(root=root)
            workspace = telemetry.build_deployed_rule_operational_telemetry_workspace(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                production_target_id="production_target_primary",
                deployed_rule_id=built["production_deployment_run"]["deployed_rule_id"],
                root=root,
            )
            eligibility = telemetry.validate_deployed_rule_operational_telemetry_eligibility(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                production_target_id="production_target_primary",
                deployed_rule_id=built["production_deployment_run"]["deployed_rule_id"],
                root=root,
            )
            after = _core_state(root)
        self.assertTrue(manifest["state_telemetry_available"])
        self.assertTrue(manifest["execution_telemetry_available"])
        self.assertIn(telemetry.EXECUTION_PRODUCER_ID, [item["producer_id"] for item in manifest["producers"]])
        self.assertIn(telemetry.EXECUTION_PRODUCER_ID, workspace["execution_producer_ids"])
        self.assertEqual(workspace["status"], "ready")
        self.assertIn(eligibility["status"], {"eligible", "eligible_with_warnings"})
        self.assertEqual(before, after)

    def test_authoritative_state_observation_records_immutable_bound_event(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            recorded = telemetry.record_deployed_rule_operational_event(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                producer_id=telemetry.STATE_PRODUCER_ID,
                event_type="deployment_state_observed",
                production_target_id="production_target_primary",
                deployed_rule_id=built["production_deployment_run"]["deployed_rule_id"],
                _testing_observed_at="2026-07-08T10:00:00Z",
                root=root,
            )
            event_path = root / telemetry.EVENT_DIR / f"{telemetry._safe_id(recorded['event_id'])}.json"
            payload = json.loads(event_path.read_text(encoding="utf-8"))
        self.assertEqual(recorded["status"], "recorded")
        self.assertEqual(payload["canonical_rule_id"], built["rule_id"])
        self.assertEqual(payload["deployed_rule_id"], built["production_deployment_run"]["deployed_rule_id"])
        self.assertEqual(payload["production_transaction_id"], built["production_deployment_run"]["production_transaction_id"])
        self.assertEqual(payload["production_deployment_result_id"], built["production_deployment_run"]["production_deployment_result_id"])
        self.assertEqual(payload["event_status"], "observed")

    def test_unknown_invalid_and_mismatched_inputs_are_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            unknown = telemetry.record_deployed_rule_operational_event(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                producer_id="unknown",
                event_type="deployment_state_observed",
                _testing_observed_at="2026-07-08T10:00:00Z",
                root=root,
            )
            unsupported = telemetry.record_deployed_rule_operational_event(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                producer_id=telemetry.STATE_PRODUCER_ID,
                event_type="evaluation_completed",
                _testing_observed_at="2026-07-08T10:00:00Z",
                root=root,
            )
            invalid_ts = telemetry.record_deployed_rule_operational_event(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                producer_id=telemetry.STATE_PRODUCER_ID,
                event_type="deployment_state_observed",
                _testing_observed_at="bad",
                root=root,
            )
            invalid_duration = telemetry.record_deployed_rule_operational_event(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                producer_id=telemetry.STATE_PRODUCER_ID,
                event_type="deployment_state_observed",
                _testing_observed_at="2026-07-08T10:00:00Z",
                duration_ms=-1,
                root=root,
            )
            mismatched_binding = telemetry.validate_deployed_rule_operational_telemetry_eligibility(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                production_target_id="wrong_target",
                root=root,
            )
        self.assertEqual(unknown["status"], "blocked")
        self.assertEqual(unsupported["status"], "blocked")
        self.assertEqual(invalid_ts["status"], "blocked")
        self.assertEqual(invalid_duration["status"], "blocked")
        self.assertIn("production_target_id_mismatch", mismatched_binding["blockers"])

    def test_event_idempotency_and_conflicting_immutable_id_protection(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            first = telemetry.record_deployed_rule_operational_event(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                producer_id=telemetry.STATE_PRODUCER_ID,
                event_type="deployment_state_observed",
                _testing_observed_at="2026-07-08T10:00:00Z",
                _testing_event_id="event_same",
                root=root,
            )
            second = telemetry.record_deployed_rule_operational_event(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                producer_id=telemetry.STATE_PRODUCER_ID,
                event_type="deployment_state_observed",
                _testing_observed_at="2026-07-08T10:00:00Z",
                _testing_event_id="event_same",
                root=root,
            )
            conflict = telemetry.record_deployed_rule_operational_event(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                producer_id=telemetry.STATE_PRODUCER_ID,
                event_type="deployment_state_observed",
                _testing_observed_at="2026-07-08T10:00:00Z",
                duration_ms=5,
                _testing_event_id="event_same",
                root=root,
            )
        self.assertEqual(first["status"], "recorded")
        self.assertEqual(second["status"], "already_recorded")
        self.assertEqual(second["writes_performed"], 0)
        self.assertEqual(conflict["status"], "conflict")

    def test_event_listing_is_bounded_filtered_deterministic_and_read_only(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            before = _core_state(root)
            telemetry.record_deployed_rule_operational_event(
                built["rule_id"], built["production_deployment_run"]["production_deployment_result_id"],
                producer_id=telemetry.STATE_PRODUCER_ID, event_type="deployment_state_observed",
                producer_sequence=2, _testing_observed_at="2026-07-08T10:00:00Z", _testing_event_id="evt2", root=root,
            )
            telemetry.record_deployed_rule_operational_event(
                built["rule_id"], built["production_deployment_run"]["production_deployment_result_id"],
                producer_id=telemetry.STATE_PRODUCER_ID, event_type="deployment_state_observed",
                producer_sequence=1, _testing_observed_at="2026-07-08T10:00:00Z", _testing_event_id="evt1", root=root,
            )
            telemetry.record_deployed_rule_operational_event(
                built["rule_id"], built["production_deployment_run"]["production_deployment_result_id"],
                producer_id=telemetry.STATE_PRODUCER_ID, event_type="deployment_state_observed",
                producer_sequence=3, _testing_observed_at="2026-07-08T11:00:00Z", _testing_event_id="evt3", root=root,
            )
            listed = telemetry.list_deployed_rule_operational_events(
                built["production_deployment_run"]["deployed_rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                producer_id=telemetry.STATE_PRODUCER_ID,
                max_results=2,
                root=root,
            )
            after = _core_state(root)
        self.assertEqual(listed["status"], "listed")
        self.assertEqual(listed["returned_event_count"], 2)
        self.assertEqual([item["event_id"] for item in listed["items"]], ["evt1", "evt2"])
        self.assertEqual(before, after)

    def test_snapshot_blocks_on_truncation_and_separates_invalid_records(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            for index in range(2):
                telemetry.record_deployed_rule_operational_event(
                    built["rule_id"], built["production_deployment_run"]["production_deployment_result_id"],
                    producer_id=telemetry.STATE_PRODUCER_ID, event_type="deployment_state_observed",
                    _testing_observed_at=f"2026-07-08T10:0{index}:00Z", _testing_event_id=f"valid_{index}", root=root,
                )
            corrupt_payload = {
                "schema_version": telemetry.EVENT_SCHEMA,
                "event_id": "corrupt_event",
                "producer_id": telemetry.STATE_PRODUCER_ID,
            }
            corrupt_path = root / telemetry.EVENT_DIR / "corrupt_event.json"
            _write_json(corrupt_path, corrupt_payload)
            event_index = telemetry._load_event_index_entries(root)
            event_index.append(
                {
                    "event_id": "corrupt_event",
                    "relative_path": str(Path(telemetry.EVENT_DIR) / "corrupt_event.json").replace("\\", "/"),
                    "deployed_rule_id": built["production_deployment_run"]["deployed_rule_id"],
                    "production_deployment_result_id": built["production_deployment_run"]["production_deployment_result_id"],
                    "producer_id": telemetry.STATE_PRODUCER_ID,
                    "event_type": "deployment_state_observed",
                    "observed_at": "2026-07-08T12:00:00Z",
                    "producer_sequence": None,
                    "event_fingerprint": "bad",
                }
            )
            telemetry._atomic_write_json(root / "indexes" / telemetry.EVENT_INDEX, {"schema_version": "deployed_rule_operational_event_index_v1", "items": event_index})
            blocked = telemetry.build_deployed_rule_operational_snapshot(
                built["production_deployment_run"]["deployed_rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                max_events=1,
                root=root,
            )
            snapshot = telemetry.build_deployed_rule_operational_snapshot(
                built["production_deployment_run"]["deployed_rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                max_events=5,
                root=root,
            )
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(snapshot["status"], "recorded")
        self.assertEqual(snapshot["validated_event_count"], 2)
        self.assertEqual(snapshot["invalid_event_count"], 1)
        self.assertEqual(snapshot["effectiveness_evaluation_status"], "not_performed")

    def test_execution_producer_available_without_events_keeps_effectiveness_not_performed(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            telemetry.record_deployed_rule_operational_event(
                built["rule_id"], built["production_deployment_run"]["production_deployment_result_id"],
                producer_id=telemetry.STATE_PRODUCER_ID, event_type="deployment_state_observed",
                _testing_observed_at="2026-07-08T10:00:00Z", root=root,
            )
            manifest = telemetry.get_deployed_rule_operational_telemetry_manifest(root=root)
            snapshot = telemetry.build_deployed_rule_operational_snapshot(
                built["production_deployment_run"]["deployed_rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                root=root,
            )
        self.assertTrue(manifest["execution_telemetry_available"])
        self.assertEqual(snapshot["execution_event_count"], 0)
        self.assertEqual(snapshot["metric_availability"]["execution_completion_count"], "execution_producer_available_no_events_observed")

    def test_health_api_report_and_mutation_guards_prove_read_only_behavior(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            before = _core_state(root)
            telemetry.record_deployed_rule_operational_event(
                built["rule_id"], built["production_deployment_run"]["production_deployment_result_id"],
                producer_id=telemetry.STATE_PRODUCER_ID, event_type="deployment_state_observed",
                _testing_observed_at="2026-07-08T10:00:00Z", root=root,
            )
            workspace = api_workspace(
                built["rule_id"], built["production_deployment_run"]["production_deployment_result_id"],
                production_target_id="production_target_primary", deployed_rule_id=built["production_deployment_run"]["deployed_rule_id"], root=root,
            )
            eligibility = api_validate(
                built["rule_id"], built["production_deployment_run"]["production_deployment_result_id"],
                production_target_id="production_target_primary", deployed_rule_id=built["production_deployment_run"]["deployed_rule_id"], root=root,
            )
            listed = api_list_events(
                built["production_deployment_run"]["deployed_rule_id"], built["production_deployment_run"]["production_deployment_result_id"], root=root,
            )
            snapshot = api_build_snapshot(
                built["production_deployment_run"]["deployed_rule_id"], built["production_deployment_run"]["production_deployment_result_id"], root=root,
            )
            health = telemetry.get_deployed_rule_operational_telemetry_health(
                built["rule_id"], built["production_deployment_run"]["production_deployment_result_id"],
                production_target_id="production_target_primary", deployed_rule_id=built["production_deployment_run"]["deployed_rule_id"], root=root,
            )
            report = api_report(
                built["rule_id"], built["production_deployment_run"]["production_deployment_result_id"],
                production_target_id="production_target_primary", deployed_rule_id=built["production_deployment_run"]["deployed_rule_id"], root=root,
            )
            after = _core_state(root)
        self.assertEqual(workspace["status"], "ready")
        self.assertIn(eligibility["status"], {"eligible", "eligible_with_warnings"})
        self.assertEqual(listed["status"], "listed")
        self.assertIn(snapshot["status"], {"recorded", "already_recorded"})
        self.assertEqual(health["status"], "healthy")
        self.assertIn(f"Execution Producer IDs: {telemetry.EXECUTION_PRODUCER_ID}", report)
        self.assertIn("Effectiveness evaluation remains not_performed.", report)
        self.assertEqual(before, after)

    def test_desktop_seam_exposes_read_only_telemetry_actions_and_correct_wrapper_mapping(self) -> None:
        build_source = inspect.getsource(desktop_right_panel.DesktopRightPanelMixin._build_pdf_intake_page)
        run_source = inspect.getsource(desktop_right_panel.DesktopRightPanelMixin._run_pdf_viewport_action)
        self.assertIn("Deployed Rule Operational Telemetry", build_source)
        self.assertIn("Load Telemetry Workspace", build_source)
        self.assertIn("Validate Telemetry Eligibility", build_source)
        self.assertIn("List Operational Events", build_source)
        self.assertIn("Build Telemetry Snapshot", build_source)
        self.assertIn("Telemetry Health", build_source)
        self.assertIn("Copy Telemetry Report", build_source)
        self.assertNotIn("record_deployed_rule_operational_event", run_source)

        panel = self._Panel()
        with (
            patch.object(desktop_right_panel, "build_deployed_rule_operational_telemetry_workspace", return_value={"status": "ready"}) as workspace_mock,
            patch.object(desktop_right_panel, "validate_deployed_rule_operational_telemetry_eligibility", return_value={"status": "eligible"}) as validate_mock,
            patch.object(desktop_right_panel, "list_deployed_rule_operational_events", return_value={"status": "listed", "returned_event_count": 1}) as list_mock,
            patch.object(desktop_right_panel, "build_deployed_rule_operational_snapshot", return_value={"status": "recorded", "snapshot_id": "snap_1", "effectiveness_evaluation_status": "not_performed"}) as snapshot_mock,
            patch.object(desktop_right_panel, "get_deployed_rule_operational_telemetry_health", return_value={"status": "warning", "state_telemetry_available": True, "execution_telemetry_available": False}) as health_mock,
            patch.object(desktop_right_panel, "format_deployed_rule_operational_telemetry_report", return_value="Effectiveness evaluation remains not_performed.") as report_mock,
        ):
            desktop_right_panel.DesktopRightPanelMixin._run_pdf_viewport_action(panel, "load_deployed_rule_operational_telemetry_workspace")
            desktop_right_panel.DesktopRightPanelMixin._run_pdf_viewport_action(panel, "validate_deployed_rule_operational_telemetry_eligibility")
            desktop_right_panel.DesktopRightPanelMixin._run_pdf_viewport_action(panel, "list_deployed_rule_operational_events")
            desktop_right_panel.DesktopRightPanelMixin._run_pdf_viewport_action(panel, "build_deployed_rule_operational_snapshot")
            desktop_right_panel.DesktopRightPanelMixin._run_pdf_viewport_action(panel, "deployed_rule_operational_telemetry_health")
            desktop_right_panel.DesktopRightPanelMixin._run_pdf_viewport_action(panel, "copy_deployed_rule_operational_telemetry_report")

        workspace_mock.assert_called_once_with(
            canonical_rule_id="canonical_rule_1",
            production_deployment_result_id="deployment_result_1",
            phase_9w_result_id="phase9w_1",
            production_target_id="production_target_primary",
            deployed_rule_id="deployed_rule_1",
        )
        validate_mock.assert_any_call(
            canonical_rule_id="canonical_rule_1",
            production_deployment_result_id="deployment_result_1",
            phase_9w_result_id="phase9w_1",
            production_target_id="production_target_primary",
            deployed_rule_id="deployed_rule_1",
        )
        list_mock.assert_called_once_with(
            deployed_rule_id="deployed_rule_1",
            production_deployment_result_id="deployment_result_1",
            event_type="deployment_state_observed",
            producer_id=telemetry.STATE_PRODUCER_ID,
            start_timestamp="2026-07-08T10:00:00Z",
            end_timestamp="2026-07-08T11:00:00Z",
            max_results=12,
        )
        snapshot_mock.assert_called_once_with(
            deployed_rule_id="deployed_rule_1",
            production_deployment_result_id="deployment_result_1",
            start_timestamp="2026-07-08T10:00:00Z",
            end_timestamp="2026-07-08T11:00:00Z",
            phase_9w_result_id="phase9w_1",
            max_events=12,
        )
        health_mock.assert_called_once_with(
            canonical_rule_id="canonical_rule_1",
            production_deployment_result_id="deployment_result_1",
            phase_9w_result_id="phase9w_1",
            production_target_id="production_target_primary",
            deployed_rule_id="deployed_rule_1",
        )
        report_mock.assert_called_once_with(
            canonical_rule_id="canonical_rule_1",
            production_deployment_result_id="deployment_result_1",
            phase_9w_result_id="phase9w_1",
            production_target_id="production_target_primary",
            deployed_rule_id="deployed_rule_1",
            start_timestamp="2026-07-08T10:00:00Z",
            end_timestamp="2026-07-08T11:00:00Z",
            event_type="deployment_state_observed",
            producer_id=telemetry.STATE_PRODUCER_ID,
            max_results=12,
            public_safe=True,
        )
        self.assertEqual(panel.copied_text, "Effectiveness evaluation remains not_performed.")
        self.assertEqual(panel.last_telemetry_payload["telemetry_health"], "warning")

    def test_api_health_wrapper_passes_through_backend_contract(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            health = api_health(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                production_target_id="production_target_primary",
                deployed_rule_id=built["production_deployment_run"]["deployed_rule_id"],
                root=root,
            )
        self.assertEqual(health["status"], "healthy")
        self.assertTrue(health["state_telemetry_available"])
        self.assertTrue(health["execution_telemetry_available"])

    def test_execution_events_are_counted_in_snapshots_and_are_idempotent(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            first = execution_runtime.execute_deployed_rule(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                execution_input={"score": 7},
                record_operational_telemetry=True,
                _testing_observed_at="2026-07-10T12:00:00Z",
                root=root,
            )
            second = execution_runtime.execute_deployed_rule(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                execution_input={"score": 7},
                record_operational_telemetry=True,
                _testing_observed_at="2026-07-10T12:00:00Z",
                root=root,
            )
            snapshot = telemetry.build_deployed_rule_operational_snapshot(
                built["production_deployment_run"]["deployed_rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                root=root,
            )
        self.assertEqual(first["telemetry_recording_status"], "recorded")
        self.assertEqual(second["telemetry_recording_status"], "already_recorded")
        self.assertEqual(snapshot["execution_event_count"], 1)
        self.assertEqual(snapshot["execution_completion_count"], 1)
        self.assertEqual(snapshot["effectiveness_evaluation_status"], "not_performed")

    def test_desktop_marks_telemetry_state_stale_on_input_change_and_blocks_missing_required_ids(self) -> None:
        panel = self._Panel()
        panel._register_deployed_rule_operational_telemetry_traces()
        panel.deployed_rule_operational_telemetry_rule_id_var.set("changed_rule")
        self.assertIn("stale_due_to_input_change", panel.deployed_rule_operational_telemetry_status_var.get())
        self.assertIn("not_performed", panel.deployed_rule_operational_telemetry_status_var.get())

        panel.deployed_rule_operational_telemetry_rule_id_var.set("")
        panel.deployed_rule_operational_telemetry_result_id_var.set("")
        with patch.object(desktop_right_panel, "build_deployed_rule_operational_telemetry_workspace", side_effect=AssertionError("workspace wrapper should not be called when required ids are missing")):
            desktop_right_panel.DesktopRightPanelMixin._run_pdf_viewport_action(panel, "load_deployed_rule_operational_telemetry_workspace")
        self.assertIn("blocked", panel.deployed_rule_operational_telemetry_status_var.get())
        self.assertIn("canonical_rule_id", panel.deployed_rule_operational_telemetry_status_var.get())
        self.assertIn("production_deployment_result_id", panel.deployed_rule_operational_telemetry_status_var.get())
