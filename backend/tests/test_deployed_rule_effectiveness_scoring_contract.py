from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import api
from backend.electional import deployed_rule_effectiveness_evaluation_spec as spec
from backend.electional import deployed_rule_effectiveness_readiness as readiness
from backend.electional import deployed_rule_effectiveness_scoring_contract as contract
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
        "deployed_rule_outcome_truth_sources",
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


def _readiness_and_spec(root: Path, built: dict[str, object]) -> dict[str, object]:
    _record_attempts(root, built, readiness.MINIMUM_EXECUTION_ATTEMPTS)
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
    listing = telemetry.list_deployed_rule_operational_events(
        built["production_deployment_run"]["deployed_rule_id"],
        built["production_deployment_run"]["production_deployment_result_id"],
        root=root,
    )
    event_id = str(list(listing.get("items", []))[0].get("event_id") or "")
    return [
        {
            "execution_event_id": event_id,
            "expected_outcome": "venus_day",
            "actual_or_adjudicated_outcome": "venus_day",
            "outcome_observed_at": "2026-07-10T12:00:00Z",
            "confidence_class": "high",
        }
    ]


class DeployedRuleEffectivenessScoringContractTest(TestCase):
    def test_scoring_contract_seam_boundary_remains_pre_score_only(self) -> None:
        class _Var:
            def __init__(self, value: str = "") -> None:
                self.value = value

            def get(self) -> str:
                return self.value

            def set(self, value: str) -> None:
                self.value = value

        calls: dict[str, tuple[tuple[object, ...], dict[str, object]]] = {}

        def _capture(name: str, result: dict[str, object]):
            def inner(*args, **kwargs):
                calls[name] = (args, kwargs)
                return dict(result)

            return inner

        originals = {
            "manifest": api._get_deployed_rule_effectiveness_scoring_contract_manifest_backend,
            "workspace": api._build_deployed_rule_effectiveness_scoring_contract_workspace_backend,
            "eligibility": api._validate_deployed_rule_effectiveness_scoring_contract_eligibility_backend,
            "plan": api._build_deployed_rule_effectiveness_scoring_contract_plan_backend,
            "record": api._record_deployed_rule_effectiveness_scoring_contract_result_backend,
            "load": api._load_deployed_rule_effectiveness_scoring_contract_result_backend,
            "health": api._get_deployed_rule_effectiveness_scoring_contract_health_backend,
            "report": api._format_deployed_rule_effectiveness_scoring_contract_report_backend,
        }
        try:
            api._get_deployed_rule_effectiveness_scoring_contract_manifest_backend = _capture("manifest", {"status": "manifest"})
            api._build_deployed_rule_effectiveness_scoring_contract_workspace_backend = _capture("workspace", {"status": "workspace"})
            api._validate_deployed_rule_effectiveness_scoring_contract_eligibility_backend = _capture("eligibility", {"status": "eligibility"})
            api._build_deployed_rule_effectiveness_scoring_contract_plan_backend = _capture("plan", {"status": "plan"})
            api._record_deployed_rule_effectiveness_scoring_contract_result_backend = _capture("record", {"status": "record"})
            api._load_deployed_rule_effectiveness_scoring_contract_result_backend = _capture("load", {"status": "load"})
            api._get_deployed_rule_effectiveness_scoring_contract_health_backend = _capture("health", {"status": "healthy", "health_scope": "repository-wide"})
            api._format_deployed_rule_effectiveness_scoring_contract_report_backend = _capture("report", {"status": "report"})

            manifest_result = api.get_deployed_rule_effectiveness_scoring_contract_manifest(root=Path("tmp/root"))
            workspace_result = api.build_deployed_rule_effectiveness_scoring_contract_workspace(
                "rule-1",
                "deploy-1",
                "target-1",
                "deployed-1",
                "snapshot-1",
                "readiness-1",
                "spec-1",
                "truth-result-1",
                "record-set-1",
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:00:00Z",
                root=Path("tmp/root"),
            )
            eligibility_result = api.validate_deployed_rule_effectiveness_scoring_contract_eligibility(
                "rule-1",
                "deploy-1",
                "target-1",
                "deployed-1",
                "snapshot-1",
                "readiness-1",
                "spec-1",
                "truth-result-1",
                "record-set-1",
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:00:00Z",
                root=Path("tmp/root"),
            )
            plan_result = api.build_deployed_rule_effectiveness_scoring_contract_plan(
                "rule-1",
                "deploy-1",
                "target-1",
                "deployed-1",
                "snapshot-1",
                "readiness-1",
                "spec-1",
                "truth-result-1",
                "record-set-1",
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:00:00Z",
                root=Path("tmp/root"),
            )
            record_result = api.record_deployed_rule_effectiveness_scoring_contract_result(
                "plan-1",
                confirmation="RECORD_EFFECTIVENESS_SCORING_CONTRACT_RESULT",
                root=Path("tmp/root"),
            )
            load_result = api.load_deployed_rule_effectiveness_scoring_contract_result("result-1", root=Path("tmp/root"))
            health_result = api.get_deployed_rule_effectiveness_scoring_contract_health(root=Path("tmp/root"))
            report_result = api.format_deployed_rule_effectiveness_scoring_contract_report(
                "rule-1",
                "deploy-1",
                "target-1",
                "deployed-1",
                "snapshot-1",
                "readiness-1",
                "spec-1",
                "truth-result-1",
                "record-set-1",
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:00:00Z",
                root=Path("tmp/root"),
            )
        finally:
            api._get_deployed_rule_effectiveness_scoring_contract_manifest_backend = originals["manifest"]
            api._build_deployed_rule_effectiveness_scoring_contract_workspace_backend = originals["workspace"]
            api._validate_deployed_rule_effectiveness_scoring_contract_eligibility_backend = originals["eligibility"]
            api._build_deployed_rule_effectiveness_scoring_contract_plan_backend = originals["plan"]
            api._record_deployed_rule_effectiveness_scoring_contract_result_backend = originals["record"]
            api._load_deployed_rule_effectiveness_scoring_contract_result_backend = originals["load"]
            api._get_deployed_rule_effectiveness_scoring_contract_health_backend = originals["health"]
            api._format_deployed_rule_effectiveness_scoring_contract_report_backend = originals["report"]

        self.assertEqual(manifest_result["status"], "manifest")
        self.assertEqual(workspace_result["status"], "workspace")
        self.assertEqual(eligibility_result["status"], "eligibility")
        self.assertEqual(plan_result["status"], "plan")
        self.assertEqual(record_result["status"], "record")
        self.assertEqual(load_result["status"], "load")
        self.assertEqual(health_result["status"], "healthy")
        self.assertEqual(report_result["status"], "report")
        self.assertEqual(calls["manifest"][1]["root"], Path("tmp/root"))
        self.assertEqual(
            calls["workspace"][0],
            ("rule-1", "deploy-1", "target-1", "deployed-1", "snapshot-1", "readiness-1", "spec-1", "truth-result-1", "record-set-1", "2026-07-10T10:00:00Z", "2026-07-10T12:00:00Z"),
        )
        self.assertEqual(calls["workspace"][1]["root"], Path("tmp/root"))
        self.assertEqual(calls["record"][0], ("plan-1",))
        self.assertEqual(calls["record"][1]["confirmation"], "RECORD_EFFECTIVENESS_SCORING_CONTRACT_RESULT")
        self.assertEqual(calls["load"][0], ("result-1",))
        self.assertEqual(calls["health"][1]["root"], Path("tmp/root"))
        self.assertEqual(
            calls["report"][0],
            ("rule-1", "deploy-1", "target-1", "deployed-1", "snapshot-1", "readiness-1", "spec-1", "truth-result-1", "record-set-1", "2026-07-10T10:00:00Z", "2026-07-10T12:00:00Z"),
        )
        for forbidden_wrapper in (
            "run_deployed_rule_effectiveness_score",
            "build_deployed_rule_effectiveness_scoring_dry_run",
            "override_deployed_rule_effectiveness_metric",
            "override_deployed_rule_effectiveness_numerator",
            "override_deployed_rule_effectiveness_denominator",
            "force_deployed_rule_effectiveness_score",
            "force_deployed_rule_effectiveness",
        ):
            self.assertFalse(hasattr(api, forbidden_wrapper))

        panel_source = Path(DesktopRightPanelMixin.__module__.replace(".", "/") + ".py")
        panel_text = Path("backend/electional/desktop_right_panel.py").read_text(encoding="utf-8")
        self.assertTrue(panel_source.exists())
        section_start = panel_text.index("Deployed Rule Effectiveness Scoring Contract")
        section_end = panel_text.index("Controlled Topic Taxonomy", section_start)
        scoring_section_text = panel_text[section_start:section_end]
        for text in (
            "Deployed Rule Effectiveness Scoring Contract",
            "Canonical Rule ID",
            "Phase 9V Deployment Result ID",
            "Production Target ID",
            "Deployed Rule ID",
            "Telemetry Snapshot ID",
            "Readiness Result ID",
            "Effectiveness Spec Result ID",
            "Outcome Truth Source Result ID",
            "Outcome Truth Record Set ID",
            "Observation Start",
            "Observation End",
            "Scoring Contract Plan ID",
            "Scoring Contract Result ID",
            "Scoring Contract Result Confirmation",
            "Load Scoring Contract Workspace",
            "Validate Scoring Contract Eligibility",
            "Build Scoring Contract Plan",
            "Record Scoring Contract Result",
            "Load Scoring Contract Result",
            "Scoring Contract Health",
            "Copy Scoring Contract Report",
        ):
            self.assertIn(text, scoring_section_text)
        for forbidden in (
            "Score Scoring Contract",
            "Force Score",
            "Force Effectiveness",
            "Deployment Rollback",
            "Fast Lane",
            "Create Telemetry Event",
            "Dry Run Score",
            "Override Metric",
            "Override Numerator",
            "Override Denominator",
        ):
            self.assertNotIn(forbidden, scoring_section_text)
        self.assertIn("text = format_deployed_rule_effectiveness_scoring_contract_report(**self._deployed_rule_effectiveness_scoring_contract_common_kwargs())", panel_text)

        panel = DesktopRightPanelMixin()
        panel.status_var = _Var("")
        panel.deployed_rule_effectiveness_scoring_contract_status_var = _Var("")
        panel.deployed_rule_effectiveness_scoring_contract_rule_id_var = _Var("")
        panel.deployed_rule_effectiveness_scoring_contract_result_id_var = _Var("")
        panel.deployed_rule_effectiveness_scoring_contract_target_id_var = _Var("production_target_primary")
        panel.deployed_rule_effectiveness_scoring_contract_deployed_rule_id_var = _Var("")
        panel.deployed_rule_effectiveness_scoring_contract_snapshot_id_var = _Var("")
        panel.deployed_rule_effectiveness_scoring_contract_readiness_result_id_var = _Var("")
        panel.deployed_rule_effectiveness_scoring_contract_spec_result_id_var = _Var("")
        panel.deployed_rule_effectiveness_scoring_contract_outcome_truth_result_id_var = _Var("")
        panel.deployed_rule_effectiveness_scoring_contract_record_set_id_var = _Var("")
        panel.deployed_rule_effectiveness_scoring_contract_start_var = _Var("")
        panel.deployed_rule_effectiveness_scoring_contract_end_var = _Var("")
        panel.deployed_rule_effectiveness_scoring_contract_plan_id_var = _Var("")
        panel.deployed_rule_effectiveness_scoring_contract_result_record_id_var = _Var("")
        panel.deployed_rule_effectiveness_scoring_contract_confirmation_var = _Var("WRONG")

        blocked = panel._validate_deployed_rule_effectiveness_scoring_contract_inputs("record_deployed_rule_effectiveness_scoring_contract_result")
        self.assertFalse(blocked)
        self.assertIn("scoring_contract_result_confirmation_exact_match_required", panel.deployed_rule_effectiveness_scoring_contract_status_var.get())
        self.assertIn("blocked", panel.status_var.get())

        panel.deployed_rule_effectiveness_scoring_contract_rule_id_var.set("rule-1")
        panel.deployed_rule_effectiveness_scoring_contract_result_id_var.set("deploy-1")
        panel.deployed_rule_effectiveness_scoring_contract_deployed_rule_id_var.set("deployed-1")
        panel.deployed_rule_effectiveness_scoring_contract_snapshot_id_var.set("snapshot-1")
        panel.deployed_rule_effectiveness_scoring_contract_readiness_result_id_var.set("readiness-1")
        panel.deployed_rule_effectiveness_scoring_contract_spec_result_id_var.set("spec-1")
        panel.deployed_rule_effectiveness_scoring_contract_outcome_truth_result_id_var.set("truth-result-1")
        panel.deployed_rule_effectiveness_scoring_contract_record_set_id_var.set("record-set-1")
        panel.deployed_rule_effectiveness_scoring_contract_start_var.set("2026-07-10T10:00:00Z")
        panel.deployed_rule_effectiveness_scoring_contract_end_var.set("2026-07-10T12:00:00Z")
        panel.deployed_rule_effectiveness_scoring_contract_confirmation_var.set("")
        read_only_ok = panel._validate_deployed_rule_effectiveness_scoring_contract_inputs("load_deployed_rule_effectiveness_scoring_contract_workspace")
        self.assertTrue(read_only_ok)

        panel._mark_deployed_rule_effectiveness_scoring_contract_stale()
        stale_text = panel.deployed_rule_effectiveness_scoring_contract_status_var.get()
        self.assertIn("stale_due_to_input_change", stale_text)
        self.assertIn("Effectiveness Score Calculated: no", stale_text)
        self.assertIn("Correctness Calculated: no", stale_text)
        self.assertIn("Rates Calculated: no", stale_text)

        panel._set_deployed_rule_effectiveness_scoring_contract_status(
            {
                "status": "healthy",
                "health_scope": "repository-wide",
                "metric_contracts": {
                    "accuracy_like_contract": {"metric_family_status": "supported_for_engine_design"},
                    "false_positive_false_negative_contract": {"metric_family_status": "blocked_unsupported"},
                    "precision_recall_like_contract": {"metric_family_status": "blocked_unsupported"},
                    "calibration_like_contract": {"metric_family_status": "blocked_unsupported"},
                    "runtime_reliability_contract": {"metric_family_status": "supported_for_engine_design"},
                },
                "numerator_contract": {"numerator_ready": True},
                "denominator_contract": {"denominator_ready": True},
                "blockers": [],
                "warnings": [],
            }
        )
        self.assertIn("Health Scope: repository-wide", panel.deployed_rule_effectiveness_scoring_contract_status_var.get())

        report_text = contract.format_deployed_rule_effectiveness_scoring_contract_report(
            "rule-1",
            "deploy-1",
            "target-1",
            "deployed-1",
            "snapshot-1",
            "readiness-1",
            "spec-1",
            "truth-result-1",
            "record-set-1",
            "2026-07-10T10:00:00Z",
            "2026-07-10T12:00:00Z",
            root=Path("tmp/root"),
        )
        self.assertIn("This is a scoring contract only; no effectiveness score was calculated.", report_text)
        self.assertIn("No correctness score was calculated.", report_text)
        self.assertIn("No rate was calculated.", report_text)
        self.assertIn("Source availability is not effectiveness.", report_text)
        self.assertIn("Execution completion is not correctness.", report_text)
        self.assertIn("Phase 9W acceptance is not scoring input.", report_text)

    def test_valid_outcome_truth_builds_contract_without_score(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            state = _readiness_and_spec(root, built)
            registered = truth.register_deployed_rule_outcome_truth_record_set(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                state["snapshot"]["snapshot_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                source_id="contract-source",
                source_type="external_authoritative_result",
                source_authority_class="authoritative",
                records=_valid_records(root, built, state["snapshot"]),
                confirmation=truth.REGISTER_CONFIRMATION,
                root=root,
            )
            truth_plan = truth.build_deployed_rule_outcome_truth_source_plan(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                state["snapshot"]["snapshot_id"],
                state["readiness_result"]["effectiveness_readiness_result_id"],
                state["spec_result"]["effectiveness_evaluation_spec_result_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                outcome_truth_source_id="contract-source",
                outcome_truth_record_set_id=registered["outcome_truth_record_set_id"],
                root=root,
            )
            truth_result = truth.record_deployed_rule_outcome_truth_source_result(
                truth_plan["outcome_truth_source_plan_id"],
                confirmation=truth.REQUIRED_CONFIRMATION,
                root=root,
            )
            before = _tracked_state(root)
            workspace = contract.build_deployed_rule_effectiveness_scoring_contract_workspace(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                state["snapshot"]["snapshot_id"],
                state["readiness_result"]["effectiveness_readiness_result_id"],
                state["spec_result"]["effectiveness_evaluation_spec_result_id"],
                truth_result["outcome_truth_source_result_id"],
                registered["outcome_truth_record_set_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            eligibility = contract.validate_deployed_rule_effectiveness_scoring_contract_eligibility(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                state["snapshot"]["snapshot_id"],
                state["readiness_result"]["effectiveness_readiness_result_id"],
                state["spec_result"]["effectiveness_evaluation_spec_result_id"],
                truth_result["outcome_truth_source_result_id"],
                registered["outcome_truth_record_set_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            plan = contract.build_deployed_rule_effectiveness_scoring_contract_plan(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                state["snapshot"]["snapshot_id"],
                state["readiness_result"]["effectiveness_readiness_result_id"],
                state["spec_result"]["effectiveness_evaluation_spec_result_id"],
                truth_result["outcome_truth_source_result_id"],
                registered["outcome_truth_record_set_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            result = contract.record_deployed_rule_effectiveness_scoring_contract_result(
                plan["effectiveness_scoring_contract_plan_id"],
                confirmation=contract.REQUIRED_CONFIRMATION,
                root=root,
            )
            again = contract.record_deployed_rule_effectiveness_scoring_contract_result(
                plan["effectiveness_scoring_contract_plan_id"],
                confirmation=contract.REQUIRED_CONFIRMATION,
                root=root,
            )
            loaded = contract.load_deployed_rule_effectiveness_scoring_contract_result(
                result["effectiveness_scoring_contract_result_id"],
                root=root,
            )
            report = contract.format_deployed_rule_effectiveness_scoring_contract_report(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                state["snapshot"]["snapshot_id"],
                state["readiness_result"]["effectiveness_readiness_result_id"],
                state["spec_result"]["effectiveness_evaluation_spec_result_id"],
                truth_result["outcome_truth_source_result_id"],
                registered["outcome_truth_record_set_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            after = _tracked_state(root)
        self.assertEqual(workspace["status"], "scoring_contract_ready_for_engine_design")
        self.assertEqual(eligibility["status"], "scoring_contract_ready_for_engine_design")
        self.assertEqual(result["status"], "scoring_contract_ready_for_engine_design")
        self.assertEqual(again["status"], "already_recorded")
        self.assertEqual(again["writes_performed"], 0)
        self.assertTrue(eligibility["criteria"]["outcome_truth_source_available"])
        self.assertTrue(eligibility["criteria"]["effectiveness_spec_result_allows_scoring_contract"])
        self.assertTrue(eligibility["criteria"]["denominator_inputs_defined"])
        self.assertTrue(eligibility["criteria"]["numerator_inputs_defined"])
        self.assertFalse(eligibility["effectiveness_score_calculated"])
        self.assertFalse(eligibility["correctness_calculated"])
        self.assertFalse(eligibility["rates_calculated"])
        self.assertIn("accuracy_like_contract", eligibility["metric_contracts"])
        self.assertIn("runtime_reliability_contract", eligibility["metric_contracts"])
        self.assertFalse(eligibility["metric_contracts"]["accuracy_like_contract"]["calculation_performed"])
        self.assertFalse(eligibility["denominator_contract"]["calculation_performed"])
        self.assertFalse(eligibility["numerator_contract"]["calculation_performed"])
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(plan["writes_performed"], 1)
        self.assertEqual(loaded["status"], "scoring_contract_ready_for_engine_design")
        self.assertIn("no effectiveness score was calculated", report)
        self.assertIn("No correctness score was calculated.", report)
        self.assertIn("No rate was calculated.", report)
        self.assertIn("Source availability is not effectiveness.", report)
        self.assertIn("Execution completion is not correctness.", report)
        self.assertIn("Phase 9W acceptance is not scoring input.", report)
        self.assertEqual(before, after)
