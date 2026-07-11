from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import api
from backend.electional import deployed_rule_effectiveness_evaluation_spec as spec
from backend.electional import deployed_rule_effectiveness_readiness as readiness
from backend.electional import deployed_rule_execution_runtime as runtime
from backend.electional import deployed_rule_operational_telemetry as telemetry
from backend.electional import deployed_rule_outcome_truth_source as truth
from backend.electional.desktop_right_panel import DesktopRightPanelMixin
from backend.tests.test_certified_rule_post_deployment_acceptance import _deployed_inputs


def _tracked_state(root: Path) -> dict[str, str]:
    tracked_dirs = [
        "canonical_rules",
        "production_activation_transactions",
        "certified_rule_production_deployment_plans",
        "certified_rule_production_deployment_results",
        "certified_rule_production_deployment_receipts",
        "deployed_rule_operational_telemetry",
        "deployed_rule_effectiveness_readiness",
        "deployed_rule_effectiveness_evaluation_spec",
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


def _readiness_and_spec(root: Path, built: dict[str, object], *, attempts: int) -> dict[str, object]:
    _record_attempts(root, built, attempts)
    snapshot = _snapshot(root, built)
    readiness_plan = readiness.build_deployed_rule_effectiveness_readiness_plan(
        built["rule_id"],
        built["production_deployment_run"]["production_deployment_result_id"],
        "production_target_primary",
        built["production_deployment_run"]["deployed_rule_id"],
        snapshot["snapshot_id"],
        "2026-07-10T10:00:00Z",
        "2026-07-10T12:59:00Z",
        root=root,
    )
    readiness_result = readiness.record_deployed_rule_effectiveness_readiness_result(
        readiness_plan["effectiveness_readiness_plan_id"],
        confirmation=readiness.REQUIRED_CONFIRMATION,
        root=root,
    )
    spec_plan = spec.build_deployed_rule_effectiveness_evaluation_spec_plan(
        built["rule_id"],
        built["production_deployment_run"]["production_deployment_result_id"],
        "production_target_primary",
        built["production_deployment_run"]["deployed_rule_id"],
        snapshot["snapshot_id"],
        readiness_result["effectiveness_readiness_result_id"],
        "2026-07-10T10:00:00Z",
        "2026-07-10T12:59:00Z",
        root=root,
    )
    spec_result = spec.record_deployed_rule_effectiveness_evaluation_spec_result(
        spec_plan["effectiveness_evaluation_spec_plan_id"],
        confirmation=spec.REQUIRED_CONFIRMATION,
        root=root,
    )
    return {
        "snapshot": snapshot,
        "readiness_result": readiness_result,
        "spec_result": spec_result,
    }


def _valid_records(root: Path, built: dict[str, object], snapshot: dict[str, object]) -> list[dict[str, object]]:
    event_ids = list(snapshot.get("validated_event_ids", []) or [])
    if not event_ids:
        listing = telemetry.list_deployed_rule_operational_events(
            built["production_deployment_run"]["deployed_rule_id"],
            built["production_deployment_run"]["production_deployment_result_id"],
            root=root,
        )
        event_ids = [str(item.get("event_id") or "") for item in list(listing.get("items", [])) if str(item.get("event_id") or "")]
    event_id = str(event_ids[0])
    return [
        {
            "execution_event_id": event_id,
            "expected_outcome": "venus_day",
            "actual_or_adjudicated_outcome": "venus_day",
            "outcome_observed_at": "2026-07-10T12:00:00Z",
            "confidence_class": "high",
        }
    ]


class DeployedRuleOutcomeTruthSourceTest(TestCase):
    def test_api_wrappers_and_desktop_outcome_truth_boundary_remains_pre_scoring_only(self) -> None:
        class _Var:
            def __init__(self, value: str = "") -> None:
                self.value = value

            def get(self) -> str:
                return self.value

            def set(self, value: str) -> None:
                self.value = value

            def trace_add(self, *_args: object) -> None:
                return None

        calls: dict[str, tuple[tuple[object, ...], dict[str, object]]] = {}

        def _capture(name: str):
            def inner(*args: object, **kwargs: object) -> dict[str, object]:
                calls[name] = (args, kwargs)
                return {"status": name}
            return inner

        original_workspace = api._build_deployed_rule_outcome_truth_source_workspace_backend
        original_validate = api._validate_deployed_rule_outcome_truth_record_set_backend
        try:
            api._build_deployed_rule_outcome_truth_source_workspace_backend = _capture("workspace")
            api._validate_deployed_rule_outcome_truth_record_set_backend = _capture("validate_record_set")
            workspace_result = api.build_deployed_rule_outcome_truth_source_workspace(
                "rule-1",
                "deploy-1",
                "target-1",
                "deployed-1",
                "snapshot-1",
                "readiness-1",
                "spec-1",
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:00:00Z",
                outcome_truth_source_id="source-1",
                outcome_truth_record_set_id="set-1",
            )
            record_result = api.validate_deployed_rule_outcome_truth_record_set(
                "rule-1",
                "deploy-1",
                "target-1",
                "deployed-1",
                "snapshot-1",
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:00:00Z",
                source_id="source-1",
                source_type="external_authoritative_result",
                source_authority_class="authoritative",
                records=[{"execution_event_id": "evt-1"}],
                outcome_truth_record_set_id="set-1",
            )
        finally:
            api._build_deployed_rule_outcome_truth_source_workspace_backend = original_workspace
            api._validate_deployed_rule_outcome_truth_record_set_backend = original_validate

        self.assertEqual(workspace_result["status"], "workspace")
        self.assertEqual(record_result["status"], "validate_record_set")
        self.assertEqual(
            calls["workspace"][0],
            ("rule-1", "deploy-1", "target-1", "deployed-1", "snapshot-1", "readiness-1", "spec-1", "2026-07-10T10:00:00Z", "2026-07-10T12:00:00Z"),
        )
        self.assertEqual(calls["workspace"][1]["outcome_truth_source_id"], "source-1")
        self.assertEqual(calls["workspace"][1]["outcome_truth_record_set_id"], "set-1")
        self.assertEqual(
            calls["validate_record_set"][0],
            ("rule-1", "deploy-1", "target-1", "deployed-1", "snapshot-1", "2026-07-10T10:00:00Z", "2026-07-10T12:00:00Z"),
        )
        self.assertEqual(calls["validate_record_set"][1]["source_type"], "external_authoritative_result")
        self.assertEqual(calls["validate_record_set"][1]["outcome_truth_record_set_id"], "set-1")

        panel_source = Path(DesktopRightPanelMixin.__module__.replace(".", "/") + ".py")
        panel_text = Path("backend/electional/desktop_right_panel.py").read_text(encoding="utf-8")
        self.assertTrue(panel_source.exists())
        for text in (
            "Deployed Rule Outcome Truth Source",
            "Readiness Result ID",
            "Effectiveness Spec Result ID",
            "Outcome Truth Record JSON",
            "Record Set Registration Confirmation",
            "Outcome Truth Result Confirmation",
            "Load Outcome Truth Workspace",
            "Validate Outcome Truth Eligibility",
            "Build Outcome Truth Plan",
            "Record Outcome Truth Result",
            "Validate Record Set",
            "Register Record Set",
            "Load Record Set",
            "List Record Sets",
            "Outcome Truth Health",
            "Copy Outcome Truth Report",
        ):
            self.assertIn(text, panel_text)
        self.assertNotIn("Score Outcome Truth", panel_text)

        panel = DesktopRightPanelMixin()
        panel.status_var = _Var("")
        panel.deployed_rule_outcome_truth_status_var = _Var("")
        panel.deployed_rule_outcome_truth_rule_id_var = _Var("")
        panel.deployed_rule_outcome_truth_result_id_var = _Var("")
        panel.deployed_rule_outcome_truth_target_id_var = _Var("production_target_primary")
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
        panel.deployed_rule_outcome_truth_registration_confirmation_var = _Var("RECORD_OUTCOME_TRUTH_SOURCE_RESULT")
        panel.deployed_rule_outcome_truth_result_confirmation_var = _Var("REGISTER_OUTCOME_TRUTH_RECORD_SET")

        blocked = panel._validate_deployed_rule_outcome_truth_inputs("register_deployed_rule_outcome_truth_record_set")
        self.assertFalse(blocked)
        self.assertIn("registration_confirmation_exact_match_required", panel.deployed_rule_outcome_truth_status_var.get())
        self.assertIn("blocked", panel.status_var.get())

        panel.deployed_rule_outcome_truth_registration_confirmation_var.set("REGISTER_OUTCOME_TRUTH_RECORD_SET")
        panel.deployed_rule_outcome_truth_result_confirmation_var.set("REGISTER_OUTCOME_TRUTH_RECORD_SET")
        blocked_result = panel._validate_deployed_rule_outcome_truth_inputs("record_deployed_rule_outcome_truth_result")
        self.assertFalse(blocked_result)
        self.assertIn("result_confirmation_exact_match_required", panel.deployed_rule_outcome_truth_status_var.get())

        panel.deployed_rule_outcome_truth_rule_id_var.set("rule-1")
        panel.deployed_rule_outcome_truth_result_id_var.set("deploy-1")
        panel.deployed_rule_outcome_truth_deployed_rule_id_var.set("deployed-1")
        panel.deployed_rule_outcome_truth_snapshot_id_var.set("snapshot-1")
        panel.deployed_rule_outcome_truth_readiness_result_id_var.set("readiness-1")
        panel.deployed_rule_outcome_truth_spec_result_id_var.set("spec-1")
        panel.deployed_rule_outcome_truth_start_var.set("2026-07-10T10:00:00Z")
        panel.deployed_rule_outcome_truth_end_var.set("2026-07-10T12:00:00Z")
        panel.deployed_rule_outcome_truth_registration_confirmation_var.set("")
        panel.deployed_rule_outcome_truth_result_confirmation_var.set("")
        read_only_ok = panel._validate_deployed_rule_outcome_truth_inputs("load_deployed_rule_outcome_truth_workspace")
        self.assertTrue(read_only_ok)

        panel._mark_deployed_rule_outcome_truth_stale()
        stale_text = panel.deployed_rule_outcome_truth_status_var.get()
        self.assertIn("stale_due_to_input_change", stale_text)
        self.assertIn("Effectiveness Score Calculated: no", stale_text)

        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            state = _readiness_and_spec(root, built, attempts=readiness.MINIMUM_EXECUTION_ATTEMPTS)
            truth.register_deployed_rule_outcome_truth_record_set(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                state["snapshot"]["snapshot_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                source_id="boundary-source",
                source_type="external_authoritative_result",
                source_authority_class="authoritative",
                records=_valid_records(root, built, state["snapshot"]),
                confirmation=truth.REGISTER_CONFIRMATION,
                root=root,
            )
            report = truth.format_deployed_rule_outcome_truth_source_report(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                state["snapshot"]["snapshot_id"],
                state["readiness_result"]["effectiveness_readiness_result_id"],
                state["spec_result"]["effectiveness_evaluation_spec_result_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
        self.assertIn("no effectiveness score was calculated", report)
        self.assertIn("Outcome-truth source availability does not mean effectiveness has been evaluated.", report)
        self.assertIn("Execution completion is not correctness.", report)
        self.assertIn("Phase 9W acceptance is not outcome truth.", report)
        self.assertIn("Absence of failures is not success.", report)
        self.assertNotIn("success rate", report.lower())
        self.assertNotIn("failure rate", report.lower())
        self.assertNotIn("profitability", report.lower())
        self.assertNotIn("fast lane", report.lower())
        self.assertNotIn("rollback outcome truth", panel_text.lower())
        self.assertNotIn("score outcome truth", panel_text.lower())
        self.assertNotIn("run effectiveness", panel_text.lower())

    def test_no_outcome_truth_source_reports_unavailable_without_scoring(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            state = _readiness_and_spec(root, built, attempts=readiness.MINIMUM_EXECUTION_ATTEMPTS)
            eligibility = truth.validate_deployed_rule_outcome_truth_source_eligibility(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                state["snapshot"]["snapshot_id"],
                state["readiness_result"]["effectiveness_readiness_result_id"],
                state["spec_result"]["effectiveness_evaluation_spec_result_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
        self.assertEqual(eligibility["status"], "outcome_truth_source_unavailable")
        self.assertEqual(eligibility["scoring_support_status"], "blocked_missing_outcome_truth")

    def test_valid_record_set_registration_makes_source_available_without_scoring(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            state = _readiness_and_spec(root, built, attempts=readiness.MINIMUM_EXECUTION_ATTEMPTS)
            registered = truth.register_deployed_rule_outcome_truth_record_set(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                state["snapshot"]["snapshot_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                source_id="authoritative-feed-1",
                source_type="external_authoritative_result",
                source_authority_class="authoritative",
                records=_valid_records(root, built, state["snapshot"]),
                confirmation=truth.REGISTER_CONFIRMATION,
                root=root,
            )
            eligibility = truth.validate_deployed_rule_outcome_truth_source_eligibility(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                state["snapshot"]["snapshot_id"],
                state["readiness_result"]["effectiveness_readiness_result_id"],
                state["spec_result"]["effectiveness_evaluation_spec_result_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
        self.assertEqual(registered["status"], "registered")
        self.assertEqual(eligibility["status"], "outcome_truth_source_available")
        self.assertEqual(eligibility["source_type"], "external_authoritative_result")
        self.assertEqual(eligibility["record_count"], 1)
        self.assertEqual(eligibility["scoring_support_status"], "source_available_no_scoring_engine")

    def test_missing_expected_outcome_blocks_registration(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            state = _readiness_and_spec(root, built, attempts=readiness.MINIMUM_EXECUTION_ATTEMPTS)
            result = truth.register_deployed_rule_outcome_truth_record_set(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                state["snapshot"]["snapshot_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                source_id="missing-expected",
                source_type="external_authoritative_result",
                source_authority_class="authoritative",
                records=[{
                    "execution_event_id": _valid_records(root, built, state["snapshot"])[0]["execution_event_id"],
                    "actual_or_adjudicated_outcome": "venus_day",
                    "outcome_observed_at": "2026-07-10T12:00:00Z",
                }],
                confirmation=truth.REGISTER_CONFIRMATION,
                root=root,
            )
        self.assertEqual(result["status"], "incomplete")
        self.assertIn("outcome_truth_expected_value_missing", result["blockers"])

    def test_missing_actual_outcome_blocks_registration(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            state = _readiness_and_spec(root, built, attempts=readiness.MINIMUM_EXECUTION_ATTEMPTS)
            result = truth.register_deployed_rule_outcome_truth_record_set(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                state["snapshot"]["snapshot_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                source_id="missing-actual",
                source_type="external_authoritative_result",
                source_authority_class="authoritative",
                records=[{
                    "execution_event_id": _valid_records(root, built, state["snapshot"])[0]["execution_event_id"],
                    "expected_outcome": "venus_day",
                    "outcome_observed_at": "2026-07-10T12:00:00Z",
                }],
                confirmation=truth.REGISTER_CONFIRMATION,
                root=root,
            )
        self.assertEqual(result["status"], "incomplete")
        self.assertIn("outcome_truth_actual_or_adjudicated_value_missing", result["blockers"])

    def test_phase9w_runtime_readiness_and_absence_of_failures_substitutes_are_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            state = _readiness_and_spec(root, built, attempts=readiness.MINIMUM_EXECUTION_ATTEMPTS)
            records = _valid_records(root, built, state["snapshot"])
            phase9w = truth.register_deployed_rule_outcome_truth_record_set(
                built["rule_id"], built["production_deployment_run"]["production_deployment_result_id"], "production_target_primary", built["production_deployment_run"]["deployed_rule_id"], state["snapshot"]["snapshot_id"],
                "2026-07-10T10:00:00Z", "2026-07-10T12:59:00Z", source_id="phase9w", source_type="phase9w_acceptance", source_authority_class="authoritative", records=records, confirmation=truth.REGISTER_CONFIRMATION, root=root
            )
            runtime_result = truth.register_deployed_rule_outcome_truth_record_set(
                built["rule_id"], built["production_deployment_run"]["production_deployment_result_id"], "production_target_primary", built["production_deployment_run"]["deployed_rule_id"], state["snapshot"]["snapshot_id"],
                "2026-07-10T10:00:00Z", "2026-07-10T12:59:00Z", source_id="runtime", source_type="runtime_completion", source_authority_class="authoritative", records=records, confirmation=truth.REGISTER_CONFIRMATION, root=root
            )
            readiness_result = truth.register_deployed_rule_outcome_truth_record_set(
                built["rule_id"], built["production_deployment_run"]["production_deployment_result_id"], "production_target_primary", built["production_deployment_run"]["deployed_rule_id"], state["snapshot"]["snapshot_id"],
                "2026-07-10T10:00:00Z", "2026-07-10T12:59:00Z", source_id="readiness", source_type="readiness_status", source_authority_class="authoritative", records=records, confirmation=truth.REGISTER_CONFIRMATION, root=root
            )
            absence = truth.register_deployed_rule_outcome_truth_record_set(
                built["rule_id"], built["production_deployment_run"]["production_deployment_result_id"], "production_target_primary", built["production_deployment_run"]["deployed_rule_id"], state["snapshot"]["snapshot_id"],
                "2026-07-10T10:00:00Z", "2026-07-10T12:59:00Z", source_id="absence", source_type="absence_of_failures", source_authority_class="authoritative", records=records, confirmation=truth.REGISTER_CONFIRMATION, root=root
            )
        self.assertEqual(phase9w["status"], "unsupported")
        self.assertEqual(runtime_result["status"], "unsupported")
        self.assertEqual(readiness_result["status"], "unsupported")
        self.assertEqual(absence["status"], "unsupported")

    def test_identical_record_set_registration_is_zero_write_idempotent(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            state = _readiness_and_spec(root, built, attempts=readiness.MINIMUM_EXECUTION_ATTEMPTS)
            records = _valid_records(root, built, state["snapshot"])
            first = truth.register_deployed_rule_outcome_truth_record_set(
                built["rule_id"], built["production_deployment_run"]["production_deployment_result_id"], "production_target_primary", built["production_deployment_run"]["deployed_rule_id"], state["snapshot"]["snapshot_id"],
                "2026-07-10T10:00:00Z", "2026-07-10T12:59:00Z", source_id="stable-source", source_type="external_authoritative_result", source_authority_class="authoritative", records=records, confirmation=truth.REGISTER_CONFIRMATION, outcome_truth_record_set_id="stable_set", root=root
            )
            second = truth.register_deployed_rule_outcome_truth_record_set(
                built["rule_id"], built["production_deployment_run"]["production_deployment_result_id"], "production_target_primary", built["production_deployment_run"]["deployed_rule_id"], state["snapshot"]["snapshot_id"],
                "2026-07-10T10:00:00Z", "2026-07-10T12:59:00Z", source_id="stable-source", source_type="external_authoritative_result", source_authority_class="authoritative", records=records, confirmation=truth.REGISTER_CONFIRMATION, outcome_truth_record_set_id="stable_set", root=root
            )
        self.assertEqual(first["status"], "registered")
        self.assertEqual(second["status"], "already_registered")
        self.assertEqual(second["writes_performed"], 0)

    def test_conflicting_record_set_registration_does_not_overwrite(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            state = _readiness_and_spec(root, built, attempts=readiness.MINIMUM_EXECUTION_ATTEMPTS)
            first = truth.register_deployed_rule_outcome_truth_record_set(
                built["rule_id"], built["production_deployment_run"]["production_deployment_result_id"], "production_target_primary", built["production_deployment_run"]["deployed_rule_id"], state["snapshot"]["snapshot_id"],
                "2026-07-10T10:00:00Z", "2026-07-10T12:59:00Z", source_id="stable-source", source_type="external_authoritative_result", source_authority_class="authoritative", records=_valid_records(root, built, state["snapshot"]), confirmation=truth.REGISTER_CONFIRMATION, outcome_truth_record_set_id="stable_set", root=root
            )
            conflict = truth.register_deployed_rule_outcome_truth_record_set(
                built["rule_id"], built["production_deployment_run"]["production_deployment_result_id"], "production_target_primary", built["production_deployment_run"]["deployed_rule_id"], state["snapshot"]["snapshot_id"],
                "2026-07-10T10:00:00Z", "2026-07-10T12:59:00Z", source_id="stable-source", source_type="external_authoritative_result", source_authority_class="authoritative", records=[{
                    **_valid_records(root, built, state["snapshot"])[0],
                    "actual_or_adjudicated_outcome": "mars_day",
                }], confirmation=truth.REGISTER_CONFIRMATION, outcome_truth_record_set_id="stable_set", root=root
            )
        self.assertEqual(first["status"], "registered")
        self.assertEqual(conflict["status"], "conflict")

    def test_report_states_source_availability_but_no_effectiveness_score(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            state = _readiness_and_spec(root, built, attempts=readiness.MINIMUM_EXECUTION_ATTEMPTS)
            truth.register_deployed_rule_outcome_truth_record_set(
                built["rule_id"], built["production_deployment_run"]["production_deployment_result_id"], "production_target_primary", built["production_deployment_run"]["deployed_rule_id"], state["snapshot"]["snapshot_id"],
                "2026-07-10T10:00:00Z", "2026-07-10T12:59:00Z", source_id="report-source", source_type="external_authoritative_result", source_authority_class="authoritative", records=_valid_records(root, built, state["snapshot"]), confirmation=truth.REGISTER_CONFIRMATION, root=root
            )
            report = truth.format_deployed_rule_outcome_truth_source_report(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                state["snapshot"]["snapshot_id"],
                state["readiness_result"]["effectiveness_readiness_result_id"],
                state["spec_result"]["effectiveness_evaluation_spec_result_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
        self.assertIn("outcome_truth_source_available", report)
        self.assertIn("Record count: 1", report)
        self.assertIn("no effectiveness score was calculated", report)

    def test_no_telemetry_readiness_spec_or_lifecycle_mutation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            state = _readiness_and_spec(root, built, attempts=readiness.MINIMUM_EXECUTION_ATTEMPTS)
            before = _tracked_state(root)
            truth.register_deployed_rule_outcome_truth_record_set(
                built["rule_id"], built["production_deployment_run"]["production_deployment_result_id"], "production_target_primary", built["production_deployment_run"]["deployed_rule_id"], state["snapshot"]["snapshot_id"],
                "2026-07-10T10:00:00Z", "2026-07-10T12:59:00Z", source_id="safe-source", source_type="external_authoritative_result", source_authority_class="authoritative", records=_valid_records(root, built, state["snapshot"]), confirmation=truth.REGISTER_CONFIRMATION, root=root
            )
            truth.build_deployed_rule_outcome_truth_source_plan(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                state["snapshot"]["snapshot_id"],
                state["readiness_result"]["effectiveness_readiness_result_id"],
                state["spec_result"]["effectiveness_evaluation_spec_result_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            after = _tracked_state(root)
        self.assertEqual(before, after)
