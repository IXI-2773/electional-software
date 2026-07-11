from __future__ import annotations

import inspect
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import api
from backend.electional import deployed_rule_effectiveness_evaluation_spec as spec
from backend.electional import deployed_rule_effectiveness_readiness as readiness
from backend.electional import deployed_rule_effectiveness_scoring_contract as scoring_contract
from backend.electional import deployed_rule_effectiveness_scoring_contract as contract
from backend.electional import deployed_rule_effectiveness_scoring_result as scoring_result
from backend.electional import deployed_rule_execution_runtime as runtime
from backend.electional import deployed_rule_operational_telemetry as telemetry
from backend.electional import deployed_rule_outcome_truth_source as truth
import backend.electional.desktop_right_panel as desktop_panel
from backend.tests.test_certified_rule_post_deployment_acceptance import _deployed_inputs


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
    return {"snapshot": snapshot, "readiness_result": readiness_result, "spec_result": spec_result}


def _valid_records(root: Path, built: dict[str, object]) -> list[dict[str, object]]:
    listing = telemetry.list_deployed_rule_operational_events(
        built["production_deployment_run"]["deployed_rule_id"],
        built["production_deployment_run"]["production_deployment_result_id"],
        root=root,
    )
    items = list(listing.get("items", []))
    first = items[0]
    second = items[1]
    return [
        {
            "execution_event_id": str(first.get("event_id") or ""),
            "input_fingerprint": str(first.get("input_fingerprint") or ""),
            "expected_outcome": "venus_day",
            "actual_or_adjudicated_outcome": "venus_day",
            "outcome_observed_at": "2026-07-10T12:00:00Z",
            "confidence_class": "high",
        },
        {
            "execution_event_id": str(second.get("event_id") or ""),
            "input_fingerprint": str(second.get("input_fingerprint") or ""),
            "expected_outcome": "mars_day",
            "actual_or_adjudicated_outcome": "moon_day",
            "outcome_observed_at": "2026-07-10T12:05:00Z",
            "confidence_class": "high",
        },
    ]


def _tracked_state(root: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for folder in (
        "deployed_rule_operational_telemetry",
        "deployed_rule_effectiveness_readiness",
        "deployed_rule_effectiveness_evaluation_spec",
        "deployed_rule_outcome_truth_sources",
        "deployed_rule_effectiveness_scoring_contract",
    ):
        path = root / folder
        if not path.exists():
            continue
        for file in sorted(path.rglob("*.json")):
            snapshot[str(file.relative_to(root))] = file.read_text(encoding="utf-8")
    return snapshot


class DeployedRuleEffectivenessScoringResultTest(TestCase):
    def test_persisted_scoring_result_records_only_accuracy_like_scope_and_recomputes_dry_run(self) -> None:
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
                source_id="scoring-result-source",
                source_type="external_authoritative_result",
                source_authority_class="authoritative",
                records=_valid_records(root, built),
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
                outcome_truth_source_id="scoring-result-source",
                outcome_truth_record_set_id=registered["outcome_truth_record_set_id"],
                root=root,
            )
            truth_result = truth.record_deployed_rule_outcome_truth_source_result(
                truth_plan["outcome_truth_source_plan_id"],
                confirmation=truth.REQUIRED_CONFIRMATION,
                root=root,
            )
            contract_plan = contract.build_deployed_rule_effectiveness_scoring_contract_plan(
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
            contract_result = contract.record_deployed_rule_effectiveness_scoring_contract_result(
                contract_plan["effectiveness_scoring_contract_plan_id"],
                confirmation=contract.REQUIRED_CONFIRMATION,
                root=root,
            )

            before = _tracked_state(root)
            manifest = scoring_result.get_deployed_rule_effectiveness_scoring_result_manifest(root=root)
            workspace = scoring_result.build_deployed_rule_effectiveness_scoring_result_workspace(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                state["snapshot"]["snapshot_id"],
                state["readiness_result"]["effectiveness_readiness_result_id"],
                state["spec_result"]["effectiveness_evaluation_spec_result_id"],
                truth_result["outcome_truth_source_result_id"],
                registered["outcome_truth_record_set_id"],
                contract_result["effectiveness_scoring_contract_result_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            eligibility = scoring_result.validate_deployed_rule_effectiveness_scoring_result_eligibility(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                state["snapshot"]["snapshot_id"],
                state["readiness_result"]["effectiveness_readiness_result_id"],
                state["spec_result"]["effectiveness_evaluation_spec_result_id"],
                truth_result["outcome_truth_source_result_id"],
                registered["outcome_truth_record_set_id"],
                contract_result["effectiveness_scoring_contract_result_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            plan = scoring_result.build_deployed_rule_effectiveness_scoring_result_plan(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                state["snapshot"]["snapshot_id"],
                state["readiness_result"]["effectiveness_readiness_result_id"],
                state["spec_result"]["effectiveness_evaluation_spec_result_id"],
                truth_result["outcome_truth_source_result_id"],
                registered["outcome_truth_record_set_id"],
                contract_result["effectiveness_scoring_contract_result_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            wrong = scoring_result.record_deployed_rule_effectiveness_scoring_result(
                plan["effectiveness_scoring_result_plan_id"],
                confirmation="WRONG_CONFIRMATION",
                root=root,
            )
            result = scoring_result.record_deployed_rule_effectiveness_scoring_result(
                plan["effectiveness_scoring_result_plan_id"],
                confirmation=scoring_result.REQUIRED_CONFIRMATION,
                root=root,
            )
            again = scoring_result.record_deployed_rule_effectiveness_scoring_result(
                plan["effectiveness_scoring_result_plan_id"],
                confirmation=scoring_result.REQUIRED_CONFIRMATION,
                root=root,
            )
            loaded = scoring_result.load_deployed_rule_effectiveness_scoring_result(
                result["effectiveness_scoring_result_id"],
                root=root,
            )
            health = scoring_result.get_deployed_rule_effectiveness_scoring_result_health(root=root)
            report = scoring_result.format_deployed_rule_effectiveness_scoring_result_report(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                state["snapshot"]["snapshot_id"],
                state["readiness_result"]["effectiveness_readiness_result_id"],
                state["spec_result"]["effectiveness_evaluation_spec_result_id"],
                truth_result["outcome_truth_source_result_id"],
                registered["outcome_truth_record_set_id"],
                contract_result["effectiveness_scoring_contract_result_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            result_path = root / "deployed_rule_effectiveness_scoring_result" / "results" / f"{result['effectiveness_scoring_result_id']}.json"
            receipt_path = root / "deployed_rule_effectiveness_scoring_result" / "receipts" / f"{loaded['effectiveness_scoring_result']['effectiveness_scoring_result_receipt_id']}.json"
            result_payload = json.loads(result_path.read_text(encoding="utf-8"))
            receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8"))
            after = _tracked_state(root)

        self.assertEqual(manifest["required_confirmation"], "RECORD_EFFECTIVENESS_SCORING_RESULT")
        self.assertEqual(manifest["authority_scope"], "registered_outcome_truth_exact_match_accuracy_like")
        self.assertEqual(workspace["status"], "ready_to_record")
        self.assertEqual(eligibility["status"], "ready_to_record")
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(wrong["status"], "blocked")
        self.assertIn("scoring_result_confirmation_exact_match_required", wrong["blockers"])
        self.assertEqual(result["status"], "recorded")
        self.assertEqual(again["status"], "already_recorded")
        self.assertEqual(again["writes_performed"], 0)
        self.assertEqual(loaded["status"], "recorded")
        self.assertEqual(health["status"], "healthy")
        self.assertEqual(before, after)

        persisted = loaded["effectiveness_scoring_result"]
        self.assertEqual(persisted["authority_scope"], "registered_outcome_truth_exact_match_accuracy_like")
        self.assertEqual(persisted["persisted_accuracy_like_score_ratio"], 0.5)
        self.assertEqual(persisted["persisted_accuracy_like_score_percentage"], 50.0)
        self.assertEqual(persisted["exact_match_count"], 1)
        self.assertEqual(persisted["mismatch_count"], 1)
        self.assertEqual(persisted["denominator_count"], 2)
        self.assertEqual(persisted["requested_metric_families"], ["accuracy_like_contract"])
        self.assertTrue(str(persisted["dry_run_fingerprint"]))
        self.assertTrue(str(persisted["result_fingerprint"]))
        self.assertEqual(result_payload["result_fingerprint"], persisted["result_fingerprint"])
        self.assertEqual(receipt_payload["result_fingerprint"], persisted["result_fingerprint"])

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
            self.assertNotIn(forbidden_key, persisted)

        self.assertFalse(persisted["deployment_safety_claimed"])
        self.assertFalse(persisted["production_correctness_claimed"])
        self.assertFalse(persisted["profitability_claimed"])
        self.assertFalse(persisted["prediction_quality_claimed"])
        self.assertFalse(persisted["phase9w_used_as_scoring_input"])
        self.assertFalse(persisted["runtime_completion_used_as_correctness"])
        self.assertFalse(persisted["source_availability_used_as_effectiveness"])
        self.assertIn("Only registered outcome-truth exact-match accuracy-like fields are persisted.", report)
        self.assertIn("No generic effectiveness score is produced.", report)
        self.assertIn("This is not broad production correctness.", report)
        self.assertIn("Phase 9W acceptance was not used as scoring input.", report)

    def test_persisted_scoring_result_detects_tamper_and_read_only_paths_do_not_write(self) -> None:
        with TemporaryDirectory() as tmp:
            empty_root = Path(tmp) / "empty-store"
            before_empty = sorted(str(path.relative_to(empty_root)) for path in empty_root.rglob("*")) if empty_root.exists() else []
            missing = scoring_result.load_deployed_rule_effectiveness_scoring_result("missing-result", root=empty_root)
            health_empty = scoring_result.get_deployed_rule_effectiveness_scoring_result_health(root=empty_root)
            after_empty = sorted(str(path.relative_to(empty_root)) for path in empty_root.rglob("*")) if empty_root.exists() else []

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
                source_id="tamper-source",
                source_type="external_authoritative_result",
                source_authority_class="authoritative",
                records=_valid_records(root, built),
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
                outcome_truth_source_id="tamper-source",
                outcome_truth_record_set_id=registered["outcome_truth_record_set_id"],
                root=root,
            )
            truth_result = truth.record_deployed_rule_outcome_truth_source_result(
                truth_plan["outcome_truth_source_plan_id"],
                confirmation=truth.REQUIRED_CONFIRMATION,
                root=root,
            )
            contract_plan = contract.build_deployed_rule_effectiveness_scoring_contract_plan(
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
            contract_result = contract.record_deployed_rule_effectiveness_scoring_contract_result(
                contract_plan["effectiveness_scoring_contract_plan_id"],
                confirmation=contract.REQUIRED_CONFIRMATION,
                root=root,
            )
            plan = scoring_result.build_deployed_rule_effectiveness_scoring_result_plan(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                state["snapshot"]["snapshot_id"],
                state["readiness_result"]["effectiveness_readiness_result_id"],
                state["spec_result"]["effectiveness_evaluation_spec_result_id"],
                truth_result["outcome_truth_source_result_id"],
                registered["outcome_truth_record_set_id"],
                contract_result["effectiveness_scoring_contract_result_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            recorded = scoring_result.record_deployed_rule_effectiveness_scoring_result(
                plan["effectiveness_scoring_result_plan_id"],
                confirmation=scoring_result.REQUIRED_CONFIRMATION,
                root=root,
            )
            result_path = root / "deployed_rule_effectiveness_scoring_result" / "results" / f"{recorded['effectiveness_scoring_result_id']}.json"
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            payload["persisted_accuracy_like_score_ratio"] = 0.75
            payload["effectiveness_score"] = 0.75
            result_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            corrupted = scoring_result.load_deployed_rule_effectiveness_scoring_result(
                recorded["effectiveness_scoring_result_id"],
                root=root,
            )
            health_corrupt = scoring_result.get_deployed_rule_effectiveness_scoring_result_health(root=root)

        self.assertEqual(before_empty, after_empty)
        self.assertEqual(missing["status"], "blocked")
        self.assertEqual(health_empty["status"], "healthy")
        self.assertEqual(corrupted["status"], "corrupt")
        self.assertIn("effectiveness_scoring_result_fingerprint_mismatch", corrupted["blockers"])
        self.assertIn("effectiveness_scoring_result_forbidden_generic_field_present", corrupted["blockers"])
        self.assertEqual(health_corrupt["status"], "corrupt")
        self.assertIn("effectiveness_scoring_result_fingerprint_mismatch", health_corrupt["blockers"])
        self.assertIn("effectiveness_scoring_result_forbidden_generic_field_present", health_corrupt["blockers"])

    def test_persisted_scoring_result_controlled_write_api_ui_seam_requires_confirmation_and_no_overrides(self) -> None:
        self.assertTrue(callable(api.get_deployed_rule_effectiveness_scoring_result_manifest))
        self.assertTrue(callable(api.build_deployed_rule_effectiveness_scoring_result_workspace))
        self.assertTrue(callable(api.build_deployed_rule_effectiveness_scoring_result_plan))
        self.assertTrue(callable(api.validate_deployed_rule_effectiveness_scoring_result_eligibility))
        self.assertTrue(callable(api.load_deployed_rule_effectiveness_scoring_result))
        self.assertTrue(callable(api.get_deployed_rule_effectiveness_scoring_result_health))
        self.assertTrue(callable(api.format_deployed_rule_effectiveness_scoring_result_report))
        self.assertTrue(callable(api.record_deployed_rule_effectiveness_scoring_result))

        panel_source = Path(desktop_panel.__file__).read_text(encoding="utf-8")
        for expected in (
            "Persisted Effectiveness Scoring Result",
            "Build Persisted Scoring Result Plan",
            "Record Persisted Scoring Result",
            "Scoring Result ID",
            "Scoring Result Plan ID",
            "Scoring Result Confirmation",
            "Load Persisted Scoring Result",
            "Validate Persisted Scoring Result Eligibility",
            "Persisted Scoring Result Health",
            "Copy Persisted Scoring Result Report",
        ):
            self.assertIn(expected, panel_source)
        for forbidden in (
            "Build Scoring Result Plan",
            "Record Effectiveness Scoring Result",
            "Persist Score",
            "Create Score",
            "Force Score",
            "Override Score",
            "Edit Score",
            "Delete Score",
            "Recalculate Score",
            "Override Numerator",
            "Override Denominator",
            "Override Metric",
            "Override Outcome Truth",
            "Override Authority Scope",
            "Score Dashboard",
        ):
            self.assertNotIn(forbidden, panel_source)
        self.assertIn(
            "text = format_deployed_rule_effectiveness_scoring_result_report(**self._deployed_rule_effectiveness_scoring_result_common_kwargs())",
            panel_source,
        )

        class _Var:
            def __init__(self, value: str = "") -> None:
                self.value = value

            def get(self) -> str:
                return self.value

            def set(self, value: str) -> None:
                self.value = value

            def trace_add(self, _mode: str, _callback) -> None:
                return None

        captured: dict[str, object] = {"clipboard": []}

        def _fake_load(result_id: str):
            captured["load"] = (result_id,)
            return {"status": "corrupt", "blockers": ["tampered_result"], "authority_scope": "registered_outcome_truth_exact_match_accuracy_like"}

        ordered_keys = (
            "canonical_rule_id",
            "production_deployment_result_id",
            "production_target_id",
            "deployed_rule_id",
            "telemetry_snapshot_id",
            "readiness_result_id",
            "effectiveness_spec_result_id",
            "outcome_truth_source_result_id",
            "outcome_truth_record_set_id",
            "effectiveness_scoring_contract_result_id",
            "observation_window_start",
            "observation_window_end",
        )

        def _fake_plan(*args, **kwargs):
            captured["plan"] = args or tuple(kwargs[key] for key in ordered_keys)
            return {
                "status": "ready",
                "authority_scope": "registered_outcome_truth_exact_match_accuracy_like",
                "effectiveness_scoring_result_plan_id": "plan-1",
                "score_family": "accuracy_like_contract",
            }

        def _fake_validate(*args, **kwargs):
            captured["validate"] = args or tuple(kwargs[key] for key in ordered_keys)
            return {
                "status": "eligible",
                "authority_scope": "registered_outcome_truth_exact_match_accuracy_like",
                "persisted_accuracy_like_score_ratio": 0.5,
                "persisted_accuracy_like_score_percentage": 50.0,
            }

        def _fake_health():
            captured["health"] = ()
            return {"status": "healthy"}

        def _fake_report(*args, **kwargs):
            captured["report"] = args or tuple(kwargs[key] for key in ordered_keys)
            return "public-safe scoring result report"

        def _fake_record(plan_id: str, *, confirmation: str | None = None):
            captured["record"] = (plan_id, confirmation)
            return {
                "status": "recorded",
                "effectiveness_scoring_result_id": "score-1",
                "effectiveness_scoring_result_plan_id": plan_id,
                "authority_scope": "registered_outcome_truth_exact_match_accuracy_like",
            }

        original_plan = desktop_panel.build_deployed_rule_effectiveness_scoring_result_plan
        original_load = desktop_panel.load_deployed_rule_effectiveness_scoring_result
        original_validate = desktop_panel.validate_deployed_rule_effectiveness_scoring_result_eligibility
        original_health = desktop_panel.get_deployed_rule_effectiveness_scoring_result_health
        original_report = desktop_panel.format_deployed_rule_effectiveness_scoring_result_report
        original_record = desktop_panel.record_deployed_rule_effectiveness_scoring_result
        try:
            desktop_panel.build_deployed_rule_effectiveness_scoring_result_plan = _fake_plan
            desktop_panel.load_deployed_rule_effectiveness_scoring_result = _fake_load
            desktop_panel.validate_deployed_rule_effectiveness_scoring_result_eligibility = _fake_validate
            desktop_panel.get_deployed_rule_effectiveness_scoring_result_health = _fake_health
            desktop_panel.format_deployed_rule_effectiveness_scoring_result_report = _fake_report
            desktop_panel.record_deployed_rule_effectiveness_scoring_result = _fake_record

            panel = object.__new__(desktop_panel.DesktopRightPanelMixin)
            panel._current_source_document_id = lambda: "doc-1"
            panel.status_var = _Var("")
            panel.clipboard_clear = lambda: captured["clipboard"].clear()
            panel.clipboard_append = lambda text: captured["clipboard"].append(text)
            panel.deployed_rule_effectiveness_scoring_result_id_var = _Var("")
            panel.deployed_rule_effectiveness_scoring_result_rule_id_var = _Var("rule-1")
            panel.deployed_rule_effectiveness_scoring_result_deployment_result_id_var = _Var("deploy-1")
            panel.deployed_rule_effectiveness_scoring_result_target_id_var = _Var("production_target_primary")
            panel.deployed_rule_effectiveness_scoring_result_deployed_rule_id_var = _Var("deployed-1")
            panel.deployed_rule_effectiveness_scoring_result_snapshot_id_var = _Var("snapshot-1")
            panel.deployed_rule_effectiveness_scoring_result_readiness_result_id_var = _Var("readiness-1")
            panel.deployed_rule_effectiveness_scoring_result_spec_result_id_var = _Var("spec-1")
            panel.deployed_rule_effectiveness_scoring_result_outcome_truth_result_id_var = _Var("truth-result-1")
            panel.deployed_rule_effectiveness_scoring_result_record_set_id_var = _Var("record-set-1")
            panel.deployed_rule_effectiveness_scoring_result_contract_result_id_var = _Var("contract-result-1")
            panel.deployed_rule_effectiveness_scoring_result_start_var = _Var("2026-07-10T10:00:00Z")
            panel.deployed_rule_effectiveness_scoring_result_end_var = _Var("2026-07-10T12:00:00Z")
            panel.deployed_rule_effectiveness_scoring_result_plan_id_var = _Var("")
            panel.deployed_rule_effectiveness_scoring_result_confirmation_var = _Var("RECORD_EFFECTIVENESS_SCORING_RESULT")
            panel.deployed_rule_effectiveness_scoring_result_status_var = _Var("")

            panel._run_pdf_viewport_action("build_deployed_rule_effectiveness_scoring_result_plan")
            self.assertEqual(
                captured["plan"],
                (
                    "rule-1",
                    "deploy-1",
                    "production_target_primary",
                    "deployed-1",
                    "snapshot-1",
                    "readiness-1",
                    "spec-1",
                    "truth-result-1",
                    "record-set-1",
                    "contract-result-1",
                    "2026-07-10T10:00:00Z",
                    "2026-07-10T12:00:00Z",
                ),
            )
            self.assertEqual(panel.deployed_rule_effectiveness_scoring_result_plan_id_var.get(), "plan-1")

            panel._run_pdf_viewport_action("load_deployed_rule_effectiveness_scoring_result")
            self.assertIn("scoring_result_id_required", panel.deployed_rule_effectiveness_scoring_result_status_var.get())

            panel.deployed_rule_effectiveness_scoring_result_id_var.set("score-1")
            panel._run_pdf_viewport_action("load_deployed_rule_effectiveness_scoring_result")
            self.assertEqual(captured["load"], ("score-1",))
            self.assertIn("Persisted Scoring Result Status: corrupt", panel.deployed_rule_effectiveness_scoring_result_status_var.get())

            panel.deployed_rule_effectiveness_scoring_result_rule_id_var.set("")
            panel._run_pdf_viewport_action("validate_deployed_rule_effectiveness_scoring_result_eligibility")
            self.assertIn("scoring_result_identity_required", panel.deployed_rule_effectiveness_scoring_result_status_var.get())

            panel.deployed_rule_effectiveness_scoring_result_rule_id_var.set("rule-1")
            panel._run_pdf_viewport_action("validate_deployed_rule_effectiveness_scoring_result_eligibility")
            self.assertEqual(
                captured["validate"],
                (
                    "rule-1",
                    "deploy-1",
                    "production_target_primary",
                    "deployed-1",
                    "snapshot-1",
                    "readiness-1",
                    "spec-1",
                    "truth-result-1",
                    "record-set-1",
                    "contract-result-1",
                    "2026-07-10T10:00:00Z",
                    "2026-07-10T12:00:00Z",
                ),
            )

            panel.deployed_rule_effectiveness_scoring_result_plan_id_var.set("")
            panel._run_pdf_viewport_action("record_deployed_rule_effectiveness_scoring_result")
            self.assertIn("scoring_result_plan_id_required", panel.deployed_rule_effectiveness_scoring_result_status_var.get())
            self.assertNotIn("record", captured)

            panel.deployed_rule_effectiveness_scoring_result_plan_id_var.set("plan-1")
            panel.deployed_rule_effectiveness_scoring_result_confirmation_var.set("WRONG")
            panel._run_pdf_viewport_action("record_deployed_rule_effectiveness_scoring_result")
            self.assertIn("scoring_result_confirmation_exact_match_required", panel.deployed_rule_effectiveness_scoring_result_status_var.get())
            self.assertNotIn("record", captured)

            panel.deployed_rule_effectiveness_scoring_result_confirmation_var.set("RECORD_EFFECTIVENESS_SCORING_RESULT")
            panel._run_pdf_viewport_action("record_deployed_rule_effectiveness_scoring_result")
            self.assertEqual(captured["record"], ("plan-1", "RECORD_EFFECTIVENESS_SCORING_RESULT"))
            self.assertEqual(panel.deployed_rule_effectiveness_scoring_result_id_var.get(), "score-1")

            panel._run_pdf_viewport_action("deployed_rule_effectiveness_scoring_result_health")
            self.assertEqual(captured["health"], ())
            self.assertIn("Health Scope: repository-wide", panel.deployed_rule_effectiveness_scoring_result_status_var.get())

            panel._mark_deployed_rule_effectiveness_scoring_result_stale()
            stale_status = panel.deployed_rule_effectiveness_scoring_result_status_var.get()
            self.assertIn("Scoring Result Plan ID: plan-1", stale_status)
            self.assertIn("Deployment Safety Claimed: no", stale_status)
            self.assertIn("Production Correctness Claimed: no", stale_status)
            self.assertIn("Profitability Claimed: no", stale_status)
            self.assertIn("Prediction Quality Claimed: no", stale_status)
            self.assertIn("Phase 9W Used As Scoring Input: no", stale_status)
            self.assertIn("Runtime Completion Used As Correctness: no", stale_status)
            self.assertIn("Source Availability Used As Effectiveness: no", stale_status)

            panel._run_pdf_viewport_action("copy_deployed_rule_effectiveness_scoring_result_report")
            self.assertEqual(
                captured["report"],
                (
                    "rule-1",
                    "deploy-1",
                    "production_target_primary",
                    "deployed-1",
                    "snapshot-1",
                    "readiness-1",
                    "spec-1",
                    "truth-result-1",
                    "record-set-1",
                    "contract-result-1",
                    "2026-07-10T10:00:00Z",
                    "2026-07-10T12:00:00Z",
                ),
            )
            self.assertEqual(captured["clipboard"], ["public-safe scoring result report"])
        finally:
            desktop_panel.build_deployed_rule_effectiveness_scoring_result_plan = original_plan
            desktop_panel.load_deployed_rule_effectiveness_scoring_result = original_load
            desktop_panel.validate_deployed_rule_effectiveness_scoring_result_eligibility = original_validate
            desktop_panel.get_deployed_rule_effectiveness_scoring_result_health = original_health
            desktop_panel.format_deployed_rule_effectiveness_scoring_result_report = original_report
            desktop_panel.record_deployed_rule_effectiveness_scoring_result = original_record

    def test_persisted_scoring_result_controlled_write_seam_boundary_blocks_overrides_and_preserves_scope(self) -> None:
        plan_signature = inspect.signature(api.build_deployed_rule_effectiveness_scoring_result_plan)
        record_signature = inspect.signature(api.record_deployed_rule_effectiveness_scoring_result)
        self.assertEqual(
            tuple(plan_signature.parameters.keys()),
            (
                "canonical_rule_id",
                "production_deployment_result_id",
                "production_target_id",
                "deployed_rule_id",
                "telemetry_snapshot_id",
                "readiness_result_id",
                "effectiveness_spec_result_id",
                "outcome_truth_source_result_id",
                "outcome_truth_record_set_id",
                "effectiveness_scoring_contract_result_id",
                "observation_window_start",
                "observation_window_end",
                "root",
            ),
        )
        self.assertEqual(
            tuple(record_signature.parameters.keys()),
            ("effectiveness_scoring_result_plan_id", "confirmation", "root"),
        )
        forbidden_params = {
            "score_ratio",
            "score_percentage",
            "exact_match_count",
            "mismatch_count",
            "denominator_count",
            "dry_run_payload",
            "candidate_summary",
            "manual_score",
            "authority_scope",
            "metric_override",
            "numerator_override",
            "denominator_override",
        }
        self.assertTrue(forbidden_params.isdisjoint(plan_signature.parameters))
        self.assertTrue(forbidden_params.isdisjoint(record_signature.parameters))
        for forbidden_name in (
            "force_score",
            "override_score",
            "set_score",
            "update_score",
            "edit_score",
            "delete_score",
            "recalculate_score",
            "persist_caller_score",
        ):
            self.assertFalse(hasattr(api, forbidden_name))

        panel_source = Path(desktop_panel.__file__).read_text(encoding="utf-8")
        for expected in (
            "Persisted Effectiveness Scoring Result",
            "Build Persisted Scoring Result Plan",
            "Record Persisted Scoring Result",
            "Scoring Result Plan ID",
            "Scoring Result Confirmation",
        ):
            self.assertIn(expected, panel_source)
        for forbidden in (
            "Force Score",
            "Override Score",
            "Edit Score",
            "Delete Score",
            "Recalculate Score",
            "Persist Caller Score",
            "Manual Score",
            "Override Numerator",
            "Override Denominator",
            "Override Metric",
            "Override Outcome Truth",
            "Override Authority Scope",
            "Score Dashboard",
            '("Score Ratio", self.deployed_rule_effectiveness_scoring_result',
            '("Score Percentage", self.deployed_rule_effectiveness_scoring_result',
            '("Exact Match Count", self.deployed_rule_effectiveness_scoring_result',
            '("Mismatch Count", self.deployed_rule_effectiveness_scoring_result',
            '("Denominator Count", self.deployed_rule_effectiveness_scoring_result',
        ):
            self.assertNotIn(forbidden, panel_source)

        docs_text = Path("docs/DEPLOYED_RULE_EFFECTIVENESS_SCORING_RESULT.md").read_text(encoding="utf-8")
        for expected in (
            "RECORD_EFFECTIVENESS_SCORING_RESULT",
            "The API/UI seam does not accept caller-supplied score values",
            "registered_outcome_truth_exact_match_accuracy_like",
            "Phase 9W acceptance was not used as scoring input.",
            "Runtime completion was not used as correctness.",
            "Source availability alone was not used as effectiveness.",
        ):
            self.assertIn(expected, docs_text)

        class _Var:
            def __init__(self, value: str = "") -> None:
                self.value = value

            def get(self) -> str:
                return self.value

            def set(self, value: str) -> None:
                self.value = value

            def trace_add(self, _mode: str, _callback) -> None:
                return None

        captured: dict[str, object] = {"clipboard": []}

        ordered_keys = (
            "canonical_rule_id",
            "production_deployment_result_id",
            "production_target_id",
            "deployed_rule_id",
            "telemetry_snapshot_id",
            "readiness_result_id",
            "effectiveness_spec_result_id",
            "outcome_truth_source_result_id",
            "outcome_truth_record_set_id",
            "effectiveness_scoring_contract_result_id",
            "observation_window_start",
            "observation_window_end",
        )

        def _fake_plan(*args, **kwargs):
            captured["plan"] = args or tuple(kwargs[key] for key in ordered_keys)
            return {
                "status": "ready",
                "authority_scope": "registered_outcome_truth_exact_match_accuracy_like",
                "effectiveness_scoring_result_plan_id": "plan-1",
                "score_family": "accuracy_like_contract",
                "deployment_safety_claimed": False,
                "production_correctness_claimed": False,
                "profitability_claimed": False,
                "prediction_quality_claimed": False,
                "phase9w_used_as_scoring_input": False,
                "runtime_completion_used_as_correctness": False,
                "source_availability_used_as_effectiveness": False,
            }

        def _fake_record(plan_id: str, *, confirmation: str | None = None):
            captured["record"] = (plan_id, confirmation)
            return {
                "status": "blocked",
                "effectiveness_scoring_result_plan_id": plan_id,
                "authority_scope": "registered_outcome_truth_exact_match_accuracy_like",
                "blockers": ["backend_refused_record"],
                "deployment_safety_claimed": False,
                "production_correctness_claimed": False,
                "profitability_claimed": False,
                "prediction_quality_claimed": False,
                "phase9w_used_as_scoring_input": False,
                "runtime_completion_used_as_correctness": False,
                "source_availability_used_as_effectiveness": False,
            }

        def _fake_load(result_id: str):
            captured["load"] = (result_id,)
            return {"status": "corrupt", "blockers": ["tampered_result"], "authority_scope": "registered_outcome_truth_exact_match_accuracy_like"}

        def _fake_health():
            captured["health"] = ()
            return {"status": "healthy"}

        def _fake_report(*args, **kwargs):
            captured["report"] = args or tuple(kwargs[key] for key in ordered_keys)
            return "public-safe scoring result report"

        original_plan = desktop_panel.build_deployed_rule_effectiveness_scoring_result_plan
        original_record = desktop_panel.record_deployed_rule_effectiveness_scoring_result
        original_load = desktop_panel.load_deployed_rule_effectiveness_scoring_result
        original_health = desktop_panel.get_deployed_rule_effectiveness_scoring_result_health
        original_report = desktop_panel.format_deployed_rule_effectiveness_scoring_result_report
        try:
            desktop_panel.build_deployed_rule_effectiveness_scoring_result_plan = _fake_plan
            desktop_panel.record_deployed_rule_effectiveness_scoring_result = _fake_record
            desktop_panel.load_deployed_rule_effectiveness_scoring_result = _fake_load
            desktop_panel.get_deployed_rule_effectiveness_scoring_result_health = _fake_health
            desktop_panel.format_deployed_rule_effectiveness_scoring_result_report = _fake_report

            panel = object.__new__(desktop_panel.DesktopRightPanelMixin)
            panel._current_source_document_id = lambda: "doc-1"
            panel.status_var = _Var("")
            panel.clipboard_clear = lambda: captured["clipboard"].clear()
            panel.clipboard_append = lambda text: captured["clipboard"].append(text)
            panel.deployed_rule_effectiveness_scoring_result_id_var = _Var("")
            panel.deployed_rule_effectiveness_scoring_result_rule_id_var = _Var("rule-1")
            panel.deployed_rule_effectiveness_scoring_result_deployment_result_id_var = _Var("deploy-1")
            panel.deployed_rule_effectiveness_scoring_result_target_id_var = _Var("production_target_primary")
            panel.deployed_rule_effectiveness_scoring_result_deployed_rule_id_var = _Var("deployed-1")
            panel.deployed_rule_effectiveness_scoring_result_snapshot_id_var = _Var("snapshot-1")
            panel.deployed_rule_effectiveness_scoring_result_readiness_result_id_var = _Var("readiness-1")
            panel.deployed_rule_effectiveness_scoring_result_spec_result_id_var = _Var("spec-1")
            panel.deployed_rule_effectiveness_scoring_result_outcome_truth_result_id_var = _Var("truth-result-1")
            panel.deployed_rule_effectiveness_scoring_result_record_set_id_var = _Var("record-set-1")
            panel.deployed_rule_effectiveness_scoring_result_contract_result_id_var = _Var("contract-result-1")
            panel.deployed_rule_effectiveness_scoring_result_start_var = _Var("2026-07-10T10:00:00Z")
            panel.deployed_rule_effectiveness_scoring_result_end_var = _Var("2026-07-10T12:00:00Z")
            panel.deployed_rule_effectiveness_scoring_result_plan_id_var = _Var("")
            panel.deployed_rule_effectiveness_scoring_result_confirmation_var = _Var("")
            panel.deployed_rule_effectiveness_scoring_result_status_var = _Var("")

            panel._run_pdf_viewport_action("build_deployed_rule_effectiveness_scoring_result_plan")
            self.assertEqual(captured["plan"], (
                "rule-1",
                "deploy-1",
                "production_target_primary",
                "deployed-1",
                "snapshot-1",
                "readiness-1",
                "spec-1",
                "truth-result-1",
                "record-set-1",
                "contract-result-1",
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:00:00Z",
            ))
            self.assertEqual(panel.deployed_rule_effectiveness_scoring_result_plan_id_var.get(), "plan-1")

            panel.deployed_rule_effectiveness_scoring_result_plan_id_var.set("")
            panel._run_pdf_viewport_action("record_deployed_rule_effectiveness_scoring_result")
            self.assertIn("scoring_result_plan_id_required", panel.deployed_rule_effectiveness_scoring_result_status_var.get())
            self.assertNotIn("record", captured)

            panel.deployed_rule_effectiveness_scoring_result_plan_id_var.set("plan-1")
            panel._run_pdf_viewport_action("record_deployed_rule_effectiveness_scoring_result")
            self.assertIn("scoring_result_confirmation_exact_match_required", panel.deployed_rule_effectiveness_scoring_result_status_var.get())
            self.assertNotIn("record", captured)

            panel.deployed_rule_effectiveness_scoring_result_confirmation_var.set("RECORD_EFFECTIVENESS_SCORING_RESULT")
            panel._run_pdf_viewport_action("record_deployed_rule_effectiveness_scoring_result")
            self.assertEqual(captured["record"], ("plan-1", "RECORD_EFFECTIVENESS_SCORING_RESULT"))
            blocked_status = panel.deployed_rule_effectiveness_scoring_result_status_var.get()
            self.assertIn("Persisted Scoring Result Status: blocked", blocked_status)
            self.assertIn("Deployment Safety Claimed: no", blocked_status)
            self.assertIn("Production Correctness Claimed: no", blocked_status)
            self.assertIn("Profitability Claimed: no", blocked_status)
            self.assertIn("Prediction Quality Claimed: no", blocked_status)
            self.assertIn("Phase 9W Used As Scoring Input: no", blocked_status)
            self.assertIn("Runtime Completion Used As Correctness: no", blocked_status)
            self.assertIn("Source Availability Used As Effectiveness: no", blocked_status)

            panel._mark_deployed_rule_effectiveness_scoring_result_stale()
            stale_status = panel.deployed_rule_effectiveness_scoring_result_status_var.get()
            self.assertIn("Scoring Result Plan ID: plan-1", stale_status)
            self.assertIn("Deployment Safety Claimed: no", stale_status)
            self.assertIn("Production Correctness Claimed: no", stale_status)

            panel.deployed_rule_effectiveness_scoring_result_confirmation_var.set("")
            panel.deployed_rule_effectiveness_scoring_result_id_var.set("score-1")
            panel._run_pdf_viewport_action("load_deployed_rule_effectiveness_scoring_result")
            self.assertEqual(captured["load"], ("score-1",))
            panel._run_pdf_viewport_action("deployed_rule_effectiveness_scoring_result_health")
            self.assertEqual(captured["health"], ())
            panel._run_pdf_viewport_action("copy_deployed_rule_effectiveness_scoring_result_report")
            self.assertEqual(captured["clipboard"], ["public-safe scoring result report"])
        finally:
            desktop_panel.build_deployed_rule_effectiveness_scoring_result_plan = original_plan
            desktop_panel.record_deployed_rule_effectiveness_scoring_result = original_record
            desktop_panel.load_deployed_rule_effectiveness_scoring_result = original_load
            desktop_panel.get_deployed_rule_effectiveness_scoring_result_health = original_health
            desktop_panel.format_deployed_rule_effectiveness_scoring_result_report = original_report

    def test_persisted_scoring_result_operator_workflow_polish_preserves_safe_sequence(self) -> None:
        panel_source = Path(desktop_panel.__file__).read_text(encoding="utf-8")
        self.assertIn("Persisted Effectiveness Scoring Result", panel_source)
        self.assertIn("Operator Workflow: 1. Validate eligibility", panel_source)
        validate_index = panel_source.index("Validate Persisted Scoring Result Eligibility")
        build_index = panel_source.index("Build Persisted Scoring Result Plan")
        record_index = panel_source.index("Record Persisted Scoring Result")
        load_index = panel_source.index("Load Persisted Scoring Result")
        self.assertLess(validate_index, build_index)
        self.assertLess(build_index, record_index)
        self.assertLess(record_index, load_index)

        for forbidden in (
            "Force Score",
            "Override Score",
            "Manual Score",
            "Edit Score",
            "Delete Score",
            "Recalculate Score",
            "Aggregate Score",
            "Rank Results",
            "Compare Results",
            "Persist Caller Score",
            "Override Numerator",
            "Override Denominator",
            "Override Metric",
            "Override Outcome Truth",
            "Override Authority Scope",
        ):
            self.assertNotIn(forbidden, panel_source)

        docs_text = Path("docs/DEPLOYED_RULE_EFFECTIVENESS_SCORING_RESULT.md").read_text(encoding="utf-8")
        for expected in (
            "## Operator Workflow",
            "1. Validate eligibility.",
            "2. Build a persisted scoring-result plan.",
            "3. Record only with exact confirmation: `RECORD_EFFECTIVENESS_SCORING_RESULT`.",
            "4. Load the recorded result and inspect health.",
            "5. Use summary/report as read-only views.",
            "It does not establish broad rule effectiveness, deployment safety, production correctness, profitability, prediction quality, aggregate effectiveness, ranking quality, or future performance.",
        ):
            self.assertIn(expected, docs_text)

        api_signatures = {
            "workspace": inspect.signature(api.build_deployed_rule_effectiveness_scoring_result_workspace),
            "eligibility": inspect.signature(api.validate_deployed_rule_effectiveness_scoring_result_eligibility),
            "plan": inspect.signature(api.build_deployed_rule_effectiveness_scoring_result_plan),
            "record": inspect.signature(api.record_deployed_rule_effectiveness_scoring_result),
            "load": inspect.signature(api.load_deployed_rule_effectiveness_scoring_result),
            "report": inspect.signature(api.format_deployed_rule_effectiveness_scoring_result_report),
            "summary": inspect.signature(api.build_deployed_rule_effectiveness_scoring_result_summary_surface),
        }
        forbidden_params = {
            "score",
            "score_value",
            "ratio",
            "percentage",
            "exact_match_count",
            "mismatch_count",
            "denominator_count",
            "numerator",
            "denominator",
            "metric",
            "metric_family",
            "authority_scope",
            "dry_run_payload",
            "candidate_summary",
            "manual_score",
            "override",
            "force",
            "aggregate_method",
            "ranking_method",
            "weight",
            "threshold",
        }
        for signature in api_signatures.values():
            self.assertTrue(forbidden_params.isdisjoint(signature.parameters))

        class _Var:
            def __init__(self, value: str = "") -> None:
                self.value = value

            def get(self) -> str:
                return self.value

            def set(self, value: str) -> None:
                self.value = value

            def trace_add(self, _mode: str, _callback) -> None:
                return None

        captured: dict[str, object] = {"clipboard": []}

        def _fake_report(*_args, **_kwargs):
            captured["report_called"] = True
            return "public-safe scoring result report"

        original_report = desktop_panel.format_deployed_rule_effectiveness_scoring_result_report
        try:
            desktop_panel.format_deployed_rule_effectiveness_scoring_result_report = _fake_report

            panel = object.__new__(desktop_panel.DesktopRightPanelMixin)
            panel.status_var = _Var("")
            panel.clipboard_clear = lambda: captured["clipboard"].clear()
            panel.clipboard_append = lambda text: captured["clipboard"].append(text)
            panel.deployed_rule_effectiveness_scoring_result_status_var = _Var("")
            panel.deployed_rule_effectiveness_scoring_result_id_var = _Var("")
            panel.deployed_rule_effectiveness_scoring_result_rule_id_var = _Var("rule-1")
            panel.deployed_rule_effectiveness_scoring_result_deployment_result_id_var = _Var("deploy-1")
            panel.deployed_rule_effectiveness_scoring_result_target_id_var = _Var("target-1")
            panel.deployed_rule_effectiveness_scoring_result_deployed_rule_id_var = _Var("deployed-1")
            panel.deployed_rule_effectiveness_scoring_result_snapshot_id_var = _Var("snapshot-1")
            panel.deployed_rule_effectiveness_scoring_result_readiness_result_id_var = _Var("readiness-1")
            panel.deployed_rule_effectiveness_scoring_result_spec_result_id_var = _Var("spec-1")
            panel.deployed_rule_effectiveness_scoring_result_outcome_truth_result_id_var = _Var("truth-result-1")
            panel.deployed_rule_effectiveness_scoring_result_record_set_id_var = _Var("record-set-1")
            panel.deployed_rule_effectiveness_scoring_result_contract_result_id_var = _Var("contract-result-1")
            panel.deployed_rule_effectiveness_scoring_result_start_var = _Var("2026-07-10T10:00:00Z")
            panel.deployed_rule_effectiveness_scoring_result_end_var = _Var("2026-07-10T12:00:00Z")
            panel.deployed_rule_effectiveness_scoring_result_plan_id_var = _Var("plan-1")
            panel.deployed_rule_effectiveness_scoring_result_confirmation_var = _Var("WRONG")

            panel._mark_deployed_rule_effectiveness_scoring_result_stale()
            stale_status = panel.deployed_rule_effectiveness_scoring_result_status_var.get()
            for expected in (
                "Workflow Sequence: 1. Validate eligibility 2. Build persisted scoring result plan 3. Record persisted scoring result with exact confirmation 4. Load result / health / summary / report",
                "Required Confirmation: RECORD_EFFECTIVENESS_SCORING_RESULT",
                "Current Confirmation Input: WRONG",
                "Canonical Rule ID: rule-1",
                "Phase 9V Deployment Result ID: deploy-1",
                "Production Target ID: target-1",
                "Deployed Rule ID: deployed-1",
                "Telemetry Snapshot ID: snapshot-1",
                "Readiness Result ID: readiness-1",
                "Effectiveness Spec Result ID: spec-1",
                "Outcome Truth Source Result ID: truth-result-1",
                "Outcome Truth Record Set ID: record-set-1",
                "Scoring Contract Result ID: contract-result-1",
                "Scoring Result Plan ID: plan-1",
                "Deployment Safety Claimed: no",
                "Production Correctness Claimed: no",
                "Profitability Claimed: no",
                "Prediction Quality Claimed: no",
                "Phase 9W Used As Scoring Input: no",
                "Runtime Completion Used As Correctness: no",
                "Source Availability Used As Effectiveness: no",
            ):
                self.assertIn(expected, stale_status)

            panel.deployed_rule_effectiveness_scoring_result_rule_id_var.set("")
            self.assertFalse(panel._validate_deployed_rule_effectiveness_scoring_result_inputs("build_deployed_rule_effectiveness_scoring_result_plan"))
            blocked_identity = panel.deployed_rule_effectiveness_scoring_result_status_var.get()
            self.assertIn("scoring_result_identity_required", blocked_identity)
            self.assertIn("Required Confirmation: RECORD_EFFECTIVENESS_SCORING_RESULT", blocked_identity)

            panel.deployed_rule_effectiveness_scoring_result_rule_id_var.set("rule-1")
            panel.deployed_rule_effectiveness_scoring_result_plan_id_var.set("")
            panel.deployed_rule_effectiveness_scoring_result_confirmation_var.set("")
            self.assertFalse(panel._validate_deployed_rule_effectiveness_scoring_result_inputs("record_deployed_rule_effectiveness_scoring_result"))
            self.assertIn("scoring_result_plan_id_required", panel.deployed_rule_effectiveness_scoring_result_status_var.get())

            panel.deployed_rule_effectiveness_scoring_result_plan_id_var.set("plan-1")
            panel.deployed_rule_effectiveness_scoring_result_confirmation_var.set("WRONG")
            self.assertFalse(panel._validate_deployed_rule_effectiveness_scoring_result_inputs("record_deployed_rule_effectiveness_scoring_result"))
            self.assertIn("scoring_result_confirmation_exact_match_required", panel.deployed_rule_effectiveness_scoring_result_status_var.get())

            panel._set_deployed_rule_effectiveness_scoring_result_status(
                {
                    "status": "corrupt",
                    "effectiveness_scoring_result_plan_id": "plan-1",
                    "effectiveness_scoring_result_id": "score-1",
                    "authority_scope": "registered_outcome_truth_exact_match_accuracy_like",
                    "score_family": "accuracy_like_contract",
                    "blockers": ["tampered_result"],
                    "warnings": ["receipt_missing"],
                    "recommended_action": "Inspect corrupt persisted scoring-result records before using them as scoped authority.",
                    "deployment_safety_claimed": False,
                    "production_correctness_claimed": False,
                    "profitability_claimed": False,
                    "prediction_quality_claimed": False,
                    "phase9w_used_as_scoring_input": False,
                    "runtime_completion_used_as_correctness": False,
                    "source_availability_used_as_effectiveness": False,
                }
            )
            corrupt_status = panel.deployed_rule_effectiveness_scoring_result_status_var.get()
            self.assertIn("Persisted Scoped Accuracy-Like Exact-Match Scoring Result Status: corrupt", corrupt_status)
            self.assertIn("Blockers: tampered_result", corrupt_status)
            self.assertIn("Warnings: receipt_missing", corrupt_status)
            self.assertIn("Authority Scope: registered_outcome_truth_exact_match_accuracy_like", corrupt_status)
            self.assertNotIn("Deployment Safety Claimed: yes", corrupt_status)

            panel.deployed_rule_effectiveness_scoring_result_rule_id_var.set("rule-1")
            panel.deployed_rule_effectiveness_scoring_result_confirmation_var.set("")
            text = desktop_panel.format_deployed_rule_effectiveness_scoring_result_report(**panel._deployed_rule_effectiveness_scoring_result_common_kwargs())
            panel.clipboard_clear()
            panel.clipboard_append(text)
            self.assertTrue(captured.get("report_called"))
            self.assertEqual(captured["clipboard"], ["public-safe scoring result report"])
        finally:
            desktop_panel.format_deployed_rule_effectiveness_scoring_result_report = original_report

    def test_persisted_scoring_result_optimization_shortcut_audit_preserves_boundaries(self) -> None:
        plan_signature = inspect.signature(api.build_deployed_rule_effectiveness_scoring_result_plan)
        record_signature = inspect.signature(api.record_deployed_rule_effectiveness_scoring_result)
        for forbidden_param in (
            "score",
            "score_value",
            "ratio",
            "percentage",
            "exact_match_count",
            "mismatch_count",
            "denominator_count",
            "numerator",
            "denominator",
            "metric",
            "metric_family",
            "authority_scope",
            "dry_run_payload",
            "candidate_summary",
            "manual_score",
            "override",
            "force",
        ):
            self.assertNotIn(forbidden_param, plan_signature.parameters)
            self.assertNotIn(forbidden_param, record_signature.parameters)

        panel_source = Path(desktop_panel.__file__).read_text(encoding="utf-8")
        scoring_section = panel_source.split("Persisted Effectiveness Scoring Result", 1)[1].split("Controlled Topic Taxonomy", 1)[0]
        for forbidden in (
            "Force Score",
            "Override Score",
            "Edit Score",
            "Delete Score",
            "Recalculate Score",
            "Manual Score",
            "Persist Caller Score",
            "Override Numerator",
            "Override Denominator",
            "Override Metric",
            "Override Outcome Truth",
            "Override Authority Scope",
            "Aggregate Score",
            "Rank Results",
            "Compare Results",
            '("Score Ratio", self.deployed_rule_effectiveness_scoring_result',
            '("Score Percentage", self.deployed_rule_effectiveness_scoring_result',
            '("Exact Match Count", self.deployed_rule_effectiveness_scoring_result',
            '("Mismatch Count", self.deployed_rule_effectiveness_scoring_result',
            '("Denominator Count", self.deployed_rule_effectiveness_scoring_result',
        ):
            self.assertNotIn(forbidden, scoring_section)
        for allowed in (
            "Persisted Accuracy-Like Score Ratio",
            "Persisted Accuracy-Like Score Percentage",
            "Build Persisted Scoring Result Plan",
            "Record Persisted Scoring Result",
        ):
            self.assertIn(allowed, panel_source)

        docs_text = Path("docs/DEPLOYED_RULE_EFFECTIVENESS_SCORING_RESULT.md").read_text(encoding="utf-8")
        for required in (
            "The API/UI seam does not accept caller-supplied score values",
            "The backend still recomputes the dry run internally",
            "registered_outcome_truth_exact_match_accuracy_like",
            "This seam does not claim deployment safety, broad production correctness, profitability, or prediction quality.",
        ):
            self.assertIn(required, docs_text)

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
                source_id="shortcut-audit-source",
                source_type="external_authoritative_result",
                source_authority_class="authoritative",
                records=_valid_records(root, built),
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
                outcome_truth_source_id="shortcut-audit-source",
                outcome_truth_record_set_id=registered["outcome_truth_record_set_id"],
                root=root,
            )
            truth_result = truth.record_deployed_rule_outcome_truth_source_result(
                truth_plan["outcome_truth_source_plan_id"],
                confirmation=truth.REQUIRED_CONFIRMATION,
                root=root,
            )
            contract_plan = contract.build_deployed_rule_effectiveness_scoring_contract_plan(
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
            contract_result = contract.record_deployed_rule_effectiveness_scoring_contract_result(
                contract_plan["effectiveness_scoring_contract_plan_id"],
                confirmation=contract.REQUIRED_CONFIRMATION,
                root=root,
            )
            plan = scoring_result.build_deployed_rule_effectiveness_scoring_result_plan(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                state["snapshot"]["snapshot_id"],
                state["readiness_result"]["effectiveness_readiness_result_id"],
                state["spec_result"]["effectiveness_evaluation_spec_result_id"],
                truth_result["outcome_truth_source_result_id"],
                registered["outcome_truth_record_set_id"],
                contract_result["effectiveness_scoring_contract_result_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            before_read_only = _tracked_state(root)
            wrong = scoring_result.record_deployed_rule_effectiveness_scoring_result(
                plan["effectiveness_scoring_result_plan_id"],
                confirmation="WRONG",
                root=root,
            )
            after_wrong = _tracked_state(root)
            health = scoring_result.get_deployed_rule_effectiveness_scoring_result_health(root=root)
            report = scoring_result.format_deployed_rule_effectiveness_scoring_result_report(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                state["snapshot"]["snapshot_id"],
                state["readiness_result"]["effectiveness_readiness_result_id"],
                state["spec_result"]["effectiveness_evaluation_spec_result_id"],
                truth_result["outcome_truth_source_result_id"],
                registered["outcome_truth_record_set_id"],
                contract_result["effectiveness_scoring_contract_result_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            recorded = scoring_result.record_deployed_rule_effectiveness_scoring_result(
                plan["effectiveness_scoring_result_plan_id"],
                confirmation=scoring_result.REQUIRED_CONFIRMATION,
                root=root,
            )
            loaded = scoring_result.load_deployed_rule_effectiveness_scoring_result(
                recorded["effectiveness_scoring_result_id"],
                root=root,
            )

        self.assertEqual(wrong["status"], "blocked")
        self.assertIn("scoring_result_confirmation_exact_match_required", wrong["blockers"])
        self.assertEqual(before_read_only, after_wrong)
        self.assertEqual(health["status"], "healthy")
        self.assertNotIn("effectiveness_score", report)
        self.assertNotIn("success_rate", report)
        self.assertIn("Persisted accuracy-like score ratio", report)
        self.assertIn("No generic effectiveness score is produced.", report)
        persisted = loaded["effectiveness_scoring_result"]
        self.assertEqual(persisted["authority_scope"], scoring_result.AUTHORITY_SCOPE)
        self.assertEqual(persisted["persisted_metric_family"], "accuracy_like_contract")
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
        ):
            self.assertNotIn(forbidden_key, persisted)
        for flag in (
            "deployment_safety_claimed",
            "production_correctness_claimed",
            "profitability_claimed",
            "prediction_quality_claimed",
            "phase9w_used_as_scoring_input",
            "runtime_completion_used_as_correctness",
            "source_availability_used_as_effectiveness",
        ):
            self.assertIn(flag, persisted)
            self.assertFalse(persisted[flag])

    def test_persisted_scoring_result_summary_surface_is_read_only_scoped_and_no_overclaiming(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            empty_before = sorted(str(path.relative_to(root)) for path in root.rglob("*.json")) if root.exists() else []
            empty_summary = scoring_result.build_deployed_rule_effectiveness_scoring_result_summary_surface(root=root)
            empty_report = scoring_result.format_deployed_rule_effectiveness_scoring_result_summary_surface_report(root=root)
            empty_after = sorted(str(path.relative_to(root)) for path in root.rglob("*.json")) if root.exists() else []

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
                source_id="scoring-result-summary-source",
                source_type="external_authoritative_result",
                source_authority_class="authoritative",
                records=_valid_records(root, built),
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
                outcome_truth_source_id="scoring-result-summary-source",
                outcome_truth_record_set_id=registered["outcome_truth_record_set_id"],
                root=root,
            )
            truth_result = truth.record_deployed_rule_outcome_truth_source_result(
                truth_plan["outcome_truth_source_plan_id"],
                confirmation=truth.REQUIRED_CONFIRMATION,
                root=root,
            )
            contract_plan = contract.build_deployed_rule_effectiveness_scoring_contract_plan(
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
            contract_result = contract.record_deployed_rule_effectiveness_scoring_contract_result(
                contract_plan["effectiveness_scoring_contract_plan_id"],
                confirmation=contract.REQUIRED_CONFIRMATION,
                root=root,
            )
            plan = scoring_result.build_deployed_rule_effectiveness_scoring_result_plan(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                state["snapshot"]["snapshot_id"],
                state["readiness_result"]["effectiveness_readiness_result_id"],
                state["spec_result"]["effectiveness_evaluation_spec_result_id"],
                truth_result["outcome_truth_source_result_id"],
                registered["outcome_truth_record_set_id"],
                contract_result["effectiveness_scoring_contract_result_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            recorded = scoring_result.record_deployed_rule_effectiveness_scoring_result(
                plan["effectiveness_scoring_result_plan_id"],
                confirmation=scoring_result.REQUIRED_CONFIRMATION,
                root=root,
            )
            before_summary = _tracked_state(root)
            summary = scoring_result.build_deployed_rule_effectiveness_scoring_result_summary_surface(
                recorded["effectiveness_scoring_result_id"],
                root=root,
            )
            report = scoring_result.format_deployed_rule_effectiveness_scoring_result_summary_surface_report(
                recorded["effectiveness_scoring_result_id"],
                root=root,
            )
            after_summary = _tracked_state(root)
            result_path = root / scoring_result.RESULT_DIR / f"{recorded['effectiveness_scoring_result_id']}.json"
            tampered = json.loads(result_path.read_text(encoding="utf-8"))
            tampered["effectiveness_score"] = 0.99
            result_path.write_text(json.dumps(tampered, indent=2, sort_keys=True), encoding="utf-8")
            corrupt_summary = scoring_result.build_deployed_rule_effectiveness_scoring_result_summary_surface(
                recorded["effectiveness_scoring_result_id"],
                root=root,
            )
            corrupt_report = scoring_result.format_deployed_rule_effectiveness_scoring_result_summary_surface_report(
                recorded["effectiveness_scoring_result_id"],
                root=root,
            )

        self.assertEqual(empty_before, empty_after)
        self.assertEqual(empty_summary["writes_performed"], 0)
        self.assertEqual(empty_summary["total_result_count"], 0)
        self.assertEqual(empty_summary["valid_result_count"], 0)
        self.assertIn("No new score was calculated by the summary.", empty_report)
        self.assertEqual(summary["writes_performed"], 0)
        self.assertEqual(before_summary, after_summary)
        self.assertEqual(summary["status"], "healthy")
        self.assertEqual(summary["total_result_count"], 1)
        self.assertEqual(summary["valid_result_count"], 1)
        self.assertEqual(summary["corrupt_result_count"], 0)
        self.assertEqual(summary["authority_scope_counts"], {scoring_result.AUTHORITY_SCOPE: 1})
        self.assertEqual(summary["score_family_counts"], {"accuracy_like_contract": 1})
        loaded_summary = summary["loaded_result_summary"]
        self.assertEqual(loaded_summary["authority_scope"], scoring_result.AUTHORITY_SCOPE)
        self.assertEqual(loaded_summary["score_family"], "accuracy_like_contract")
        self.assertEqual(loaded_summary["persisted_accuracy_like_score_ratio"], 0.5)
        self.assertEqual(loaded_summary["persisted_accuracy_like_score_percentage"], 50.0)
        self.assertEqual(loaded_summary["exact_match_count"], 1)
        self.assertEqual(loaded_summary["mismatch_count"], 1)
        self.assertEqual(loaded_summary["denominator_count"], 2)
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
            self.assertNotIn(forbidden_key, loaded_summary)
        for flag in (
            "deployment_safety_claimed",
            "production_correctness_claimed",
            "profitability_claimed",
            "prediction_quality_claimed",
            "phase9w_used_as_scoring_input",
            "runtime_completion_used_as_correctness",
            "source_availability_used_as_effectiveness",
        ):
            self.assertIn(flag, loaded_summary)
            self.assertFalse(loaded_summary[flag])
        self.assertIn("Scoped persisted score fields are not broad effectiveness.", report)
        self.assertIn("Phase 9W was not scoring input.", report)
        self.assertIn("Runtime completion was not correctness.", report)
        self.assertIn("Source availability alone was not effectiveness.", report)
        self.assertNotIn("effectiveness_score", report)
        self.assertNotIn("success_rate", report)
        self.assertEqual(corrupt_summary["status"], "corrupt")
        self.assertEqual(corrupt_summary["loaded_result_summary"]["status"], "corrupt")
        self.assertEqual(corrupt_summary["loaded_result_summary"]["authority_scope"], "unknown")
        self.assertIn("Corrupt records are not valid authority.", corrupt_report)
        self.assertTrue(callable(api.build_deployed_rule_effectiveness_scoring_result_summary_surface))
        self.assertTrue(callable(api.format_deployed_rule_effectiveness_scoring_result_summary_surface_report))
        desktop_source = inspect.getsource(desktop_panel)
        self.assertIn("Load Persisted Scoring Result Summary", desktop_source)
        self.assertIn("Copy Persisted Scoring Result Summary Report", desktop_source)
        self.assertNotIn("Build Persisted Scoring Result Summary Plan", desktop_source)
        self.assertNotIn("Record Persisted Scoring Result Summary", desktop_source)

    def test_persisted_scoring_result_public_safe_export_pack_is_read_only_sanitized_and_no_overclaim(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            empty_before = sorted(str(path.relative_to(root)) for path in root.rglob("*.json")) if root.exists() else []
            empty_export = scoring_result.build_deployed_rule_effectiveness_scoring_result_public_safe_export_pack("", root=root)
            empty_report = scoring_result.format_deployed_rule_effectiveness_scoring_result_public_safe_export_report("", root=root)
            empty_after = sorted(str(path.relative_to(root)) for path in root.rglob("*.json")) if root.exists() else []

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
                source_id="scoring-result-export-source",
                source_type="external_authoritative_result",
                source_authority_class="authoritative",
                records=_valid_records(root, built),
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
                outcome_truth_source_id="scoring-result-export-source",
                outcome_truth_record_set_id=registered["outcome_truth_record_set_id"],
                root=root,
            )
            truth_result = truth.record_deployed_rule_outcome_truth_source_result(
                truth_plan["outcome_truth_source_plan_id"],
                confirmation=truth.REQUIRED_CONFIRMATION,
                root=root,
            )
            contract_plan = contract.build_deployed_rule_effectiveness_scoring_contract_plan(
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
            contract_result = contract.record_deployed_rule_effectiveness_scoring_contract_result(
                contract_plan["effectiveness_scoring_contract_plan_id"],
                confirmation=contract.REQUIRED_CONFIRMATION,
                root=root,
            )
            plan = scoring_result.build_deployed_rule_effectiveness_scoring_result_plan(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                state["snapshot"]["snapshot_id"],
                state["readiness_result"]["effectiveness_readiness_result_id"],
                state["spec_result"]["effectiveness_evaluation_spec_result_id"],
                truth_result["outcome_truth_source_result_id"],
                registered["outcome_truth_record_set_id"],
                contract_result["effectiveness_scoring_contract_result_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            recorded = scoring_result.record_deployed_rule_effectiveness_scoring_result(
                plan["effectiveness_scoring_result_plan_id"],
                confirmation=scoring_result.REQUIRED_CONFIRMATION,
                root=root,
            )
            before_export = _tracked_state(root)
            export_pack = scoring_result.build_deployed_rule_effectiveness_scoring_result_public_safe_export_pack(
                recorded["effectiveness_scoring_result_id"],
                root=root,
            )
            export_report = scoring_result.format_deployed_rule_effectiveness_scoring_result_public_safe_export_report(
                recorded["effectiveness_scoring_result_id"],
                root=root,
            )
            loaded = scoring_result.load_deployed_rule_effectiveness_scoring_result(
                recorded["effectiveness_scoring_result_id"],
                root=root,
            )
            after_export = _tracked_state(root)

        self.assertEqual(empty_before, empty_after)
        self.assertEqual(empty_export["status"], "blocked")
        self.assertEqual(empty_export["writes_performed"], 0)
        self.assertTrue(empty_export["public_safe"])
        self.assertIn("scoring_result_id_required", empty_export["blockers"])
        self.assertIn("No effectiveness score was calculated.", empty_report)
        self.assertEqual(before_export, after_export)
        self.assertEqual(export_pack["status"], "export_ready")
        self.assertEqual(export_pack["writes_performed"], 0)
        self.assertTrue(export_pack["public_safe"])
        self.assertEqual(export_pack["authority_scope"], scoring_result.AUTHORITY_SCOPE)
        self.assertEqual(export_pack["persisted_metric_family"], "accuracy_like_contract")
        persisted_fields = export_pack["persisted_scoring_fields"]
        self.assertEqual(persisted_fields["persisted_accuracy_like_score_ratio"], 0.5)
        self.assertEqual(persisted_fields["persisted_accuracy_like_score_percentage"], 50.0)
        self.assertEqual(persisted_fields["exact_match_count"], 1)
        self.assertEqual(persisted_fields["mismatch_count"], 1)
        self.assertEqual(persisted_fields["denominator_count"], 2)
        stored_payload = loaded["effectiveness_scoring_result"]
        self.assertEqual(persisted_fields["eligible_record_count"], stored_payload.get("eligible_record_count", 0))
        self.assertEqual(persisted_fields["excluded_record_count"], stored_payload.get("excluded_record_count", 0))
        self.assertEqual(persisted_fields["duplicate_collapsed_count"], stored_payload.get("duplicate_collapsed_count", 0))
        self.assertEqual(persisted_fields["conflict_count"], stored_payload.get("conflict_count", 0))
        for flag, expected in scoring_result.BOUNDARY_FALSE_FLAGS.items():
            self.assertIn(flag, export_pack["boundary_flags"])
            self.assertEqual(export_pack["boundary_flags"][flag], expected)
        export_json = json.dumps(export_pack, sort_keys=True)
        report_lower = export_report.lower()
        for forbidden_key in (
            "effectiveness_score",
            "correctness_score",
            "success_rate",
            "failure_rate",
            "production_score",
            "profitability_score",
            "prediction_quality_score",
            "deployment_safety_score",
            "raw_outcome_truth",
            "raw_telemetry",
            "traceback",
        ):
            self.assertNotIn(forbidden_key, export_json)
            self.assertNotIn(forbidden_key, report_lower)
        self.assertNotIn(str(root).lower(), report_lower)
        self.assertIn("Phase 9W acceptance is not outcome truth.", export_report)
        self.assertIn("Runtime completion is not correctness.", export_report)
        self.assertIn("Source availability alone is not effectiveness.", export_report)
        self.assertTrue(callable(api.build_deployed_rule_effectiveness_scoring_result_public_safe_export_pack))
        self.assertTrue(callable(api.format_deployed_rule_effectiveness_scoring_result_public_safe_export_report))
        export_pack_signature = inspect.signature(api.build_deployed_rule_effectiveness_scoring_result_public_safe_export_pack)
        export_report_signature = inspect.signature(api.format_deployed_rule_effectiveness_scoring_result_public_safe_export_report)
        self.assertEqual(set(export_pack_signature.parameters), {"scoring_result_id", "root"})
        self.assertEqual(set(export_report_signature.parameters), {"scoring_result_id", "root"})
        for forbidden_parameter in (
            "score",
            "score_value",
            "ratio",
            "percentage",
            "exact_match_count",
            "mismatch_count",
            "denominator_count",
            "numerator",
            "denominator",
            "metric",
            "metric_family",
            "authority_scope",
            "dry_run_payload",
            "candidate_summary",
            "manual_score",
            "override",
            "force",
            "aggregate_method",
            "ranking_method",
            "weight",
            "threshold",
        ):
            self.assertNotIn(forbidden_parameter, export_pack_signature.parameters)
            self.assertNotIn(forbidden_parameter, export_report_signature.parameters)
        export_pack_source = inspect.getsource(scoring_result.build_deployed_rule_effectiveness_scoring_result_public_safe_export_pack)
        export_report_source = inspect.getsource(scoring_result.format_deployed_rule_effectiveness_scoring_result_public_safe_export_report)
        for forbidden_call in (
            "build_deployed_rule_effectiveness_scoring_result_plan(",
            "record_deployed_rule_effectiveness_scoring_result(",
            "_ensure_dirs(",
            "_atomic_write_json(",
            "write_text(",
            "json.dump(",
        ):
            self.assertNotIn(forbidden_call, export_pack_source)
            self.assertNotIn(forbidden_call, export_report_source)
        desktop_source = inspect.getsource(desktop_panel)
        self.assertIn("Load Public-Safe Scoring Export Pack", desktop_source)
        self.assertIn("Copy Public-Safe Scoring Export Report", desktop_source)
        docs_text = Path("docs/DEPLOYED_RULE_EFFECTIVENESS_SCORING_RESULT.md").read_text(encoding="utf-8")
        self.assertIn("## Public-Safe Export Pack", docs_text)
        self.assertIn("public-safe scoring export pack", docs_text.lower())

    def test_persisted_scoring_result_release_packet_and_final_operator_qa_preserve_boundaries(self) -> None:
        release_packet_path = Path("docs/DEPLOYED_RULE_EFFECTIVENESS_SCORING_RESULT_RELEASE_PACKET.md")
        self.assertTrue(release_packet_path.exists())
        release_packet = release_packet_path.read_text(encoding="utf-8")
        main_doc = Path("docs/DEPLOYED_RULE_EFFECTIVENESS_SCORING_RESULT.md").read_text(encoding="utf-8")
        backend_source = inspect.getsource(scoring_result)
        api_source = inspect.getsource(api)
        desktop_source = inspect.getsource(desktop_panel)

        for heading in (
            "## 1. Release Scope",
            "## 2. Feature Surface",
            "## 3. Operator Workflow",
            "## 4. Authority and Confirmation",
            "## 5. Public-Safe Export Pack",
            "## 6. Read/Write Boundaries",
            "## 7. Integrity and Corruption Handling",
            "## 8. Explicit Non-Claims",
            "## 9. Validation Evidence",
            "## 10. Skipped Broad Tests by Policy",
            "## 11. Known Risks",
            "## 12. Next Recommended Work",
        ):
            self.assertIn(heading, release_packet)
        self.assertIn(
            "This release covers persisted scoped accuracy-like exact-match scoring results from registered outcome-truth records only.",
            release_packet,
        )
        self.assertIn("1. Enter evidence IDs.", release_packet)
        self.assertIn("11. Copy public-safe export report.", release_packet)
        self.assertIn(scoring_result.AUTHORITY_SCOPE, release_packet)
        self.assertIn(scoring_result.REQUIRED_CONFIRMATION, release_packet)
        for field_name in (
            "persisted_accuracy_like_score_ratio",
            "persisted_accuracy_like_score_percentage",
            "exact_match_count",
            "mismatch_count",
            "denominator_count",
            "eligible_record_count",
            "excluded_record_count",
            "duplicate_collapsed_count",
            "conflict_count",
        ):
            self.assertIn(field_name, release_packet)
        for corruption_item in (
            "fingerprint mismatch",
            "receipt mismatch",
            "receipt missing",
            "authority-scope mismatch",
            "forbidden generic fields",
            "malformed result payload",
        ):
            self.assertIn(corruption_item, release_packet)
        self.assertIn("Phase 11A — Outcome-Truth Record-Set QA Gate", release_packet)
        self.assertIn("Final release packet:", main_doc)
        self.assertIn("DEPLOYED_RULE_EFFECTIVENESS_SCORING_RESULT_RELEASE_PACKET.md", main_doc)

        self.assertTrue(callable(scoring_result.build_deployed_rule_effectiveness_scoring_result_public_safe_export_pack))
        self.assertTrue(callable(scoring_result.format_deployed_rule_effectiveness_scoring_result_public_safe_export_report))
        self.assertTrue(callable(api.build_deployed_rule_effectiveness_scoring_result_public_safe_export_pack))
        self.assertTrue(callable(api.format_deployed_rule_effectiveness_scoring_result_public_safe_export_report))
        self.assertIn("Load Public-Safe Scoring Export Pack", desktop_source)
        self.assertIn("Copy Public-Safe Scoring Export Report", desktop_source)
        self.assertEqual(api_source.count("def build_deployed_rule_effectiveness_scoring_result_public_safe_export_pack("), 1)
        self.assertEqual(api_source.count("def format_deployed_rule_effectiveness_scoring_result_public_safe_export_report("), 1)
        self.assertEqual(api_source.count('"build_deployed_rule_effectiveness_scoring_result_public_safe_export_pack"'), 1)
        self.assertEqual(api_source.count('"format_deployed_rule_effectiveness_scoring_result_public_safe_export_report"'), 1)
        self.assertEqual(scoring_result.AUTHORITY_SCOPE, "registered_outcome_truth_exact_match_accuracy_like")
        self.assertEqual(scoring_result.REQUIRED_CONFIRMATION, "RECORD_EFFECTIVENESS_SCORING_RESULT")

        export_pack_signature = inspect.signature(api.build_deployed_rule_effectiveness_scoring_result_public_safe_export_pack)
        export_report_signature = inspect.signature(api.format_deployed_rule_effectiveness_scoring_result_public_safe_export_report)
        self.assertEqual(set(export_pack_signature.parameters), {"scoring_result_id", "root"})
        self.assertEqual(set(export_report_signature.parameters), {"scoring_result_id", "root"})
        for forbidden_parameter in (
            "score",
            "score_value",
            "ratio",
            "percentage",
            "exact_match_count",
            "mismatch_count",
            "denominator_count",
            "manual_score",
            "override",
            "force",
        ):
            self.assertNotIn(forbidden_parameter, export_pack_signature.parameters)
            self.assertNotIn(forbidden_parameter, export_report_signature.parameters)

        export_pack_source = inspect.getsource(scoring_result.build_deployed_rule_effectiveness_scoring_result_public_safe_export_pack)
        export_report_source = inspect.getsource(scoring_result.format_deployed_rule_effectiveness_scoring_result_public_safe_export_report)
        for forbidden_call in (
            "build_deployed_rule_effectiveness_scoring_result_plan(",
            "record_deployed_rule_effectiveness_scoring_result(",
            "_ensure_dirs(",
            "_atomic_write_json(",
            "write_text(",
            "json.dump(",
        ):
            self.assertNotIn(forbidden_call, export_pack_source)
            self.assertNotIn(forbidden_call, export_report_source)

        for forbidden_ui in (
            "Force Score",
            "Override Score",
            "Manual Score",
            "Recalculate Score",
            "Aggregate Score",
            "Rank Results",
            "Compare Results",
        ):
            self.assertNotIn(forbidden_ui, desktop_source)
        for forbidden_field in (
            "effectiveness_score",
            "success_rate",
            "final_score",
        ):
            self.assertNotIn(f"`{forbidden_field}`", release_packet)
        release_packet_lower = release_packet.lower()
        for forbidden_claim in (
            "broad effectiveness proven",
            "production correctness proven",
            "deployment safety proven",
            "profitability proven",
            "prediction quality proven",
            "broad regression passed",
            "full suite passed",
            "release fully verified",
        ):
            self.assertNotIn(forbidden_claim, release_packet_lower)
        self.assertIn("does not establish:", release_packet_lower)
        self.assertIn("broad rule effectiveness", release_packet_lower)
        self.assertIn("production correctness", release_packet_lower)
        self.assertIn("deployment safety", release_packet_lower)
        self.assertIn("profitability", release_packet_lower)
        self.assertIn("prediction quality", release_packet_lower)
        self.assertIn("broad regression safety", release_packet_lower)
        self.assertIn("test_persisted_scoring_result_public_safe_export_pack_is_read_only_sanitized_and_no_overclaim", release_packet)
        self.assertIn("full project suite", release_packet_lower)
        self.assertIn("all electional tests", release_packet_lower)
        self.assertIn("only focused exact nodes were run", release_packet_lower)

    def test_persisted_scoring_result_end_to_end_release_checklist_preserves_boundaries(self) -> None:
        backend_public = {
            "get_deployed_rule_effectiveness_scoring_result_manifest",
            "build_deployed_rule_effectiveness_scoring_result_workspace",
            "validate_deployed_rule_effectiveness_scoring_result_eligibility",
            "build_deployed_rule_effectiveness_scoring_result_plan",
            "record_deployed_rule_effectiveness_scoring_result",
            "load_deployed_rule_effectiveness_scoring_result",
            "get_deployed_rule_effectiveness_scoring_result_health",
            "format_deployed_rule_effectiveness_scoring_result_report",
            "build_deployed_rule_effectiveness_scoring_result_summary_surface",
            "format_deployed_rule_effectiveness_scoring_result_summary_surface_report",
        }
        forbidden_public = {
            "force_score",
            "override_score",
            "manual_score",
            "set_score",
            "update_score",
            "delete_score",
            "edit_score",
            "recalculate_score",
            "aggregate_effectiveness_score",
            "rank_scoring_results",
            "compare_scoring_results",
            "persist_caller_score",
        }
        forbidden_api_params = {
            "score",
            "score_value",
            "ratio",
            "percentage",
            "exact_match_count",
            "mismatch_count",
            "denominator_count",
            "numerator",
            "denominator",
            "metric",
            "metric_family",
            "authority_scope",
            "dry_run_payload",
            "candidate_summary",
            "manual_score",
            "override",
            "force",
            "aggregate_method",
            "ranking_method",
            "weight",
            "threshold",
        }

        for name in backend_public:
            self.assertTrue(callable(getattr(scoring_result, name, None)))
        for name in forbidden_public:
            self.assertFalse(hasattr(scoring_result, name))
            self.assertFalse(hasattr(api, name))
        for name in (
            "build_deployed_rule_effectiveness_scoring_result_plan",
            "record_deployed_rule_effectiveness_scoring_result",
            "build_deployed_rule_effectiveness_scoring_result_summary_surface",
            "format_deployed_rule_effectiveness_scoring_result_summary_surface_report",
            "load_deployed_rule_effectiveness_scoring_result",
            "get_deployed_rule_effectiveness_scoring_result_health",
        ):
            self.assertTrue(callable(getattr(api, name, None)))

        plan_signature = inspect.signature(api.build_deployed_rule_effectiveness_scoring_result_plan)
        record_signature = inspect.signature(api.record_deployed_rule_effectiveness_scoring_result)
        summary_signature = inspect.signature(api.build_deployed_rule_effectiveness_scoring_result_summary_surface)
        for forbidden_param in forbidden_api_params:
            self.assertNotIn(forbidden_param, plan_signature.parameters)
            self.assertNotIn(forbidden_param, record_signature.parameters)
            self.assertNotIn(forbidden_param, summary_signature.parameters)

        panel_source = Path(desktop_panel.__file__).read_text(encoding="utf-8")
        scoring_section = panel_source.split("Persisted Effectiveness Scoring Result", 1)[1].split("Controlled Topic Taxonomy", 1)[0]
        for required in (
            "Load Persisted Scoring Result",
            "Validate Persisted Scoring Result Eligibility",
            "Persisted Scoring Result Health",
            "Copy Persisted Scoring Result Report",
            "Build Persisted Scoring Result Plan",
            "Record Persisted Scoring Result",
            "Load Persisted Scoring Result Summary",
            "Copy Persisted Scoring Result Summary Report",
        ):
            self.assertIn(required, scoring_section)
        for forbidden in (
            "Force Score",
            "Override Score",
            "Manual Score",
            "Edit Score",
            "Delete Score",
            "Recalculate Score",
            "Aggregate Score",
            "Rank Results",
            "Compare Results",
            "Persist Caller Score",
            "Override Numerator",
            "Override Denominator",
            "Override Metric",
            "Override Outcome Truth",
            "Override Authority Scope",
            "Score Dashboard",
            '("Score Ratio", self.deployed_rule_effectiveness_scoring_result',
            '("Score Percentage", self.deployed_rule_effectiveness_scoring_result',
            '("Exact Match Count", self.deployed_rule_effectiveness_scoring_result',
            '("Mismatch Count", self.deployed_rule_effectiveness_scoring_result',
            '("Denominator Count", self.deployed_rule_effectiveness_scoring_result',
            '("Authority Scope", self.deployed_rule_effectiveness_scoring_result',
            '("Metric Family", self.deployed_rule_effectiveness_scoring_result',
        ):
            self.assertNotIn(forbidden, scoring_section)

        docs_text = Path("docs/DEPLOYED_RULE_EFFECTIVENESS_SCORING_RESULT.md").read_text(encoding="utf-8")
        for required in (
            "registered_outcome_truth_exact_match_accuracy_like",
            "RECORD_EFFECTIVENESS_SCORING_RESULT",
            "Wrong confirmation returns a blocked result and performs no writes.",
            "The API/UI seam does not accept caller-supplied score values",
            "The desktop seam does not expose:",
            "score overrides",
            "Phase 9W acceptance was not used as scoring input.",
            "Runtime completion was not used as correctness.",
            "Source availability alone was not used as effectiveness.",
            "performs zero writes;",
            "corrupt persisted scoring-result records as not valid authority.",
        ):
            self.assertIn(required, docs_text)
        for forbidden in ("effectiveness_score", "success_rate", "final_score"):
            self.assertIn(forbidden, docs_text)

        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"

            def _all_json_state() -> dict[str, str]:
                if not root.exists():
                    return {}
                return {
                    str(path.relative_to(root)): path.read_text(encoding="utf-8")
                    for path in sorted(root.rglob("*.json"))
                }

            read_only_before = _all_json_state()
            manifest = scoring_result.get_deployed_rule_effectiveness_scoring_result_manifest(root=root)
            workspace = scoring_result.build_deployed_rule_effectiveness_scoring_result_workspace(
                "rule-missing",
                "deployment-missing",
                "target-missing",
                "deployed-missing",
                "snapshot-missing",
                "readiness-missing",
                "spec-missing",
                "truth-result-missing",
                "record-set-missing",
                "contract-missing",
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            eligibility = scoring_result.validate_deployed_rule_effectiveness_scoring_result_eligibility(
                "rule-missing",
                "deployment-missing",
                "target-missing",
                "deployed-missing",
                "snapshot-missing",
                "readiness-missing",
                "spec-missing",
                "truth-result-missing",
                "record-set-missing",
                "contract-missing",
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            load_missing = scoring_result.load_deployed_rule_effectiveness_scoring_result("missing", root=root)
            health_empty = scoring_result.get_deployed_rule_effectiveness_scoring_result_health(root=root)
            report_empty = scoring_result.format_deployed_rule_effectiveness_scoring_result_report(
                "rule-missing",
                "deployment-missing",
                "target-missing",
                "deployed-missing",
                "snapshot-missing",
                "readiness-missing",
                "spec-missing",
                "truth-result-missing",
                "record-set-missing",
                "contract-missing",
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            summary_empty = scoring_result.build_deployed_rule_effectiveness_scoring_result_summary_surface(root=root)
            summary_report_empty = scoring_result.format_deployed_rule_effectiveness_scoring_result_summary_surface_report(root=root)
            read_only_after = _all_json_state()

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
                source_id="release-checklist-source",
                source_type="external_authoritative_result",
                source_authority_class="authoritative",
                records=_valid_records(root, built),
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
                outcome_truth_source_id="release-checklist-source",
                outcome_truth_record_set_id=registered["outcome_truth_record_set_id"],
                root=root,
            )
            truth_result = truth.record_deployed_rule_outcome_truth_source_result(
                truth_plan["outcome_truth_source_plan_id"],
                confirmation=truth.REQUIRED_CONFIRMATION,
                root=root,
            )
            contract_plan = contract.build_deployed_rule_effectiveness_scoring_contract_plan(
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
            contract_result = contract.record_deployed_rule_effectiveness_scoring_contract_result(
                contract_plan["effectiveness_scoring_contract_plan_id"],
                confirmation=contract.REQUIRED_CONFIRMATION,
                root=root,
            )
            plan_before = _all_json_state()
            plan = scoring_result.build_deployed_rule_effectiveness_scoring_result_plan(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                state["snapshot"]["snapshot_id"],
                state["readiness_result"]["effectiveness_readiness_result_id"],
                state["spec_result"]["effectiveness_evaluation_spec_result_id"],
                truth_result["outcome_truth_source_result_id"],
                registered["outcome_truth_record_set_id"],
                contract_result["effectiveness_scoring_contract_result_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            plan_after = _all_json_state()
            wrong_confirmation = scoring_result.record_deployed_rule_effectiveness_scoring_result(
                plan["effectiveness_scoring_result_plan_id"],
                confirmation="WRONG",
                root=root,
            )
            missing_plan = scoring_result.record_deployed_rule_effectiveness_scoring_result(
                "missing-plan",
                confirmation=scoring_result.REQUIRED_CONFIRMATION,
                root=root,
            )
            record_before = _all_json_state()
            recorded = scoring_result.record_deployed_rule_effectiveness_scoring_result(
                plan["effectiveness_scoring_result_plan_id"],
                confirmation=scoring_result.REQUIRED_CONFIRMATION,
                root=root,
            )
            record_after = _all_json_state()
            loaded = scoring_result.load_deployed_rule_effectiveness_scoring_result(
                recorded["effectiveness_scoring_result_id"],
                root=root,
            )
            healthy = scoring_result.get_deployed_rule_effectiveness_scoring_result_health(root=root)
            summary = scoring_result.build_deployed_rule_effectiveness_scoring_result_summary_surface(
                recorded["effectiveness_scoring_result_id"],
                root=root,
            )
            summary_report = scoring_result.format_deployed_rule_effectiveness_scoring_result_summary_surface_report(
                recorded["effectiveness_scoring_result_id"],
                root=root,
            )
            result_path = root / scoring_result.RESULT_DIR / f"{recorded['effectiveness_scoring_result_id']}.json"
            tampered = json.loads(result_path.read_text(encoding="utf-8"))
            tampered["effectiveness_score"] = 1.0
            result_path.write_text(json.dumps(tampered, indent=2, sort_keys=True), encoding="utf-8")
            corrupt_loaded = scoring_result.load_deployed_rule_effectiveness_scoring_result(
                recorded["effectiveness_scoring_result_id"],
                root=root,
            )
            corrupt_health = scoring_result.get_deployed_rule_effectiveness_scoring_result_health(root=root)
            corrupt_summary = scoring_result.build_deployed_rule_effectiveness_scoring_result_summary_surface(
                recorded["effectiveness_scoring_result_id"],
                root=root,
            )

        self.assertEqual(read_only_before, read_only_after)
        self.assertFalse((root / "deployed_rule_effectiveness_scoring_result").exists())
        self.assertEqual(manifest["required_confirmation"], scoring_result.REQUIRED_CONFIRMATION)
        self.assertEqual(workspace["status"], "blocked")
        self.assertEqual(eligibility["status"], "blocked")
        self.assertEqual(load_missing["status"], "blocked")
        self.assertEqual(health_empty["status"], "healthy")
        self.assertEqual(summary_empty["writes_performed"], 0)
        self.assertIn("No generic effectiveness score is produced.", report_empty)
        self.assertIn("No new score was calculated by the summary.", summary_report_empty)
        self.assertEqual(plan["writes_performed"], 1)
        self.assertNotEqual(plan_before, plan_after)
        self.assertEqual(wrong_confirmation["status"], "blocked")
        self.assertIn("scoring_result_confirmation_exact_match_required", wrong_confirmation["blockers"])
        self.assertEqual(missing_plan["status"], "blocked")
        self.assertIn("scoring_result_plan_id_required", missing_plan["blockers"])
        self.assertEqual(recorded["writes_performed"], 2)
        self.assertNotEqual(record_before, record_after)
        persisted = loaded["effectiveness_scoring_result"]
        self.assertEqual(persisted["authority_scope"], scoring_result.AUTHORITY_SCOPE)
        self.assertEqual(healthy["authority_scope"], scoring_result.AUTHORITY_SCOPE)
        self.assertEqual(summary["loaded_result_summary"]["authority_scope"], scoring_result.AUTHORITY_SCOPE)
        for flag, expected in scoring_result.BOUNDARY_FALSE_FLAGS.items():
            self.assertIn(flag, persisted)
            self.assertEqual(persisted[flag], expected)
            self.assertEqual(summary["loaded_result_summary"][flag], expected)
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
        ):
            self.assertNotIn(forbidden_key, persisted)
            self.assertNotIn(forbidden_key, summary["loaded_result_summary"])
            self.assertNotIn(forbidden_key, report_empty)
            self.assertNotIn(forbidden_key, summary_report)
        self.assertEqual(corrupt_loaded["status"], "corrupt")
        self.assertEqual(corrupt_health["status"], "corrupt")
        self.assertEqual(corrupt_summary["status"], "corrupt")
        self.assertEqual(corrupt_summary["loaded_result_summary"]["status"], "corrupt")
        self.assertNotEqual(summary["status"], "already_recorded")
        self.assertIn("Only registered outcome-truth exact-match accuracy-like fields are persisted.", report_empty)
        self.assertIn("This is not broad production correctness.", report_empty)
        self.assertIn("This is not profitability.", report_empty)
        self.assertIn("This is not prediction quality.", report_empty)
        self.assertIn("Scoped persisted score fields are not broad effectiveness.", summary_report)
        self.assertIn("Corrupt records are not valid authority.", summary_report)

    def test_persisted_scoring_result_release_polish_user_facing_qa_preserves_boundaries(self) -> None:
        panel_source = Path(desktop_panel.__file__).read_text(encoding="utf-8")
        scoring_section = panel_source.split("Persisted Effectiveness Scoring Result", 1)[1].split("Controlled Topic Taxonomy", 1)[0]
        docs_text = Path("docs/DEPLOYED_RULE_EFFECTIVENESS_SCORING_RESULT.md").read_text(encoding="utf-8")

        for required_text in (
            "Persisted Scoped Accuracy-Like Exact-Match Scoring Result Status",
            "Authority Scope:",
            "Score Family:",
            "Persisted Accuracy-Like Score Ratio:",
            "Persisted Accuracy-Like Score Percentage:",
            "Exact Match Count:",
            "Mismatch Count:",
            "Denominator Count:",
            "Deployment Safety Claimed:",
            "Production Correctness Claimed:",
            "Profitability Claimed:",
            "Prediction Quality Claimed:",
            "Phase 9W Used As Scoring Input:",
            "Runtime Completion Used As Correctness:",
            "Source Availability Used As Effectiveness:",
            "Recommended Action:",
        ):
            self.assertIn(required_text, panel_source)
        for forbidden_text in (
            "effective rule",
            "correct rule",
            "safe deployment",
            "successful deployment",
            "production score",
            "final effectiveness",
            "Score Dashboard",
            "Force Score",
            "Override Score",
            "Manual Score",
            "Edit Score",
            "Delete Score",
            "Recalculate Score",
            "Aggregate Score",
            "Rank Results",
            "Compare Results",
            "Persist Caller Score",
            "Override Numerator",
            "Override Denominator",
            "Override Metric",
            "Override Outcome Truth",
            "Override Authority Scope",
            '("Score Ratio", self.deployed_rule_effectiveness_scoring_result',
            '("Score Percentage", self.deployed_rule_effectiveness_scoring_result',
            '("Exact Match Count", self.deployed_rule_effectiveness_scoring_result',
            '("Mismatch Count", self.deployed_rule_effectiveness_scoring_result',
            '("Denominator Count", self.deployed_rule_effectiveness_scoring_result',
            '("Authority Scope", self.deployed_rule_effectiveness_scoring_result',
            '("Metric Family", self.deployed_rule_effectiveness_scoring_result',
        ):
            self.assertNotIn(forbidden_text, scoring_section)
        for required_doc_text in (
            "persisted scoped accuracy-like exact-match scoring result",
            "registered outcome-truth exact-match accuracy-like scope",
            "Public-safe persisted scoring-result reports and summary reports are limited",
            "Focused validation does not establish:",
            "global regression safety",
        ):
            self.assertIn(required_doc_text, docs_text)

        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            read_only_before = sorted(str(path.relative_to(root)) for path in root.rglob("*.json")) if root.exists() else []
            manifest = scoring_result.get_deployed_rule_effectiveness_scoring_result_manifest(root=root)
            workspace = scoring_result.build_deployed_rule_effectiveness_scoring_result_workspace(
                "rule-missing",
                "deployment-missing",
                "target-missing",
                "deployed-missing",
                "snapshot-missing",
                "readiness-missing",
                "spec-missing",
                "truth-result-missing",
                "record-set-missing",
                "contract-missing",
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            eligibility = scoring_result.validate_deployed_rule_effectiveness_scoring_result_eligibility(
                "rule-missing",
                "deployment-missing",
                "target-missing",
                "deployed-missing",
                "snapshot-missing",
                "readiness-missing",
                "spec-missing",
                "truth-result-missing",
                "record-set-missing",
                "contract-missing",
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            load_missing = scoring_result.load_deployed_rule_effectiveness_scoring_result("missing", root=root)
            health = scoring_result.get_deployed_rule_effectiveness_scoring_result_health(root=root)
            report = scoring_result.format_deployed_rule_effectiveness_scoring_result_report(
                "rule-missing",
                "deployment-missing",
                "target-missing",
                "deployed-missing",
                "snapshot-missing",
                "readiness-missing",
                "spec-missing",
                "truth-result-missing",
                "record-set-missing",
                "contract-missing",
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            summary = scoring_result.build_deployed_rule_effectiveness_scoring_result_summary_surface(root=root)
            summary_report = scoring_result.format_deployed_rule_effectiveness_scoring_result_summary_surface_report(root=root)
            read_only_after = sorted(str(path.relative_to(root)) for path in root.rglob("*.json")) if root.exists() else []

            panel = object.__new__(desktop_panel.DesktopRightPanelMixin)
            class _Var:
                def __init__(self, value: str = "") -> None:
                    self._value = value
                def get(self) -> str:
                    return self._value
                def set(self, value: str) -> None:
                    self._value = value

            panel.deployed_rule_effectiveness_scoring_result_status_var = _Var("")
            panel.deployed_rule_effectiveness_scoring_result_plan_id_var = _Var("plan-1")
            panel.deployed_rule_effectiveness_scoring_result_id_var = _Var("score-1")
            panel._set_deployed_rule_effectiveness_scoring_result_status({
                "status": "corrupt",
                "authority_scope": "unknown",
                "score_family": "unknown",
                "blockers": ["forbidden_field"],
                "warnings": [],
                "recommended_action": "Review corrupt persisted scoped accuracy-like exact-match scoring result data.",
            })
            corrupt_status = panel.deployed_rule_effectiveness_scoring_result_status_var.get()

        self.assertEqual(manifest["required_confirmation"], scoring_result.REQUIRED_CONFIRMATION)
        self.assertEqual(read_only_before, read_only_after)
        self.assertEqual(workspace["status"], "blocked")
        self.assertEqual(eligibility["status"], "blocked")
        self.assertEqual(load_missing["status"], "blocked")
        self.assertEqual(health["status"], "healthy")
        self.assertEqual(summary["writes_performed"], 0)
        self.assertIn("Authority scope is limited to registered outcome-truth exact-match accuracy-like evidence.", report)
        self.assertIn("This is not deployment safety.", report)
        self.assertIn("This is not broad production correctness.", report)
        self.assertIn("This is not profitability.", report)
        self.assertIn("This is not prediction quality.", report)
        self.assertIn("Phase 9W acceptance was not used as scoring input.", report)
        self.assertIn("Runtime completion was not used as correctness.", report)
        self.assertIn("Source availability alone was not used as effectiveness.", report)
        self.assertNotIn("success rate", report.lower())
        self.assertNotIn("production score", report.lower())
        self.assertNotIn("overall score", report.lower())
        self.assertIn("Authority scope is limited to registered outcome-truth exact-match accuracy-like evidence.", summary_report)
        self.assertIn("No new score was calculated by the summary.", summary_report)
        self.assertNotIn("raw telemetry", summary_report.lower())
        self.assertNotIn("stack trace", summary_report.lower())
        self.assertNotIn(str(root), report)
        self.assertNotIn(str(root), summary_report)
        self.assertIn("Status: corrupt", corrupt_status)
        self.assertNotIn("Persisted Accuracy-Like Score Ratio: 0.", corrupt_status)
        self.assertNotIn("Persisted Accuracy-Like Score Percentage: 0.", corrupt_status)
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
        ):
            self.assertNotIn(forbidden_key, report)
            self.assertNotIn(forbidden_key, summary_report)

    def test_persisted_scoring_result_final_freeze_and_handoff_notes_preserve_release_boundaries(self) -> None:
        backend_public = {
            "get_deployed_rule_effectiveness_scoring_result_manifest",
            "build_deployed_rule_effectiveness_scoring_result_workspace",
            "validate_deployed_rule_effectiveness_scoring_result_eligibility",
            "build_deployed_rule_effectiveness_scoring_result_plan",
            "record_deployed_rule_effectiveness_scoring_result",
            "load_deployed_rule_effectiveness_scoring_result",
            "get_deployed_rule_effectiveness_scoring_result_health",
            "format_deployed_rule_effectiveness_scoring_result_report",
            "build_deployed_rule_effectiveness_scoring_result_summary_surface",
            "format_deployed_rule_effectiveness_scoring_result_summary_surface_report",
        }
        forbidden_public = {
            "force_score",
            "override_score",
            "manual_score",
            "set_score",
            "update_score",
            "delete_score",
            "edit_score",
            "recalculate_score",
            "aggregate_effectiveness_score",
            "rank_scoring_results",
            "compare_scoring_results",
            "persist_caller_score",
        }
        forbidden_api_params = {
            "score",
            "score_value",
            "ratio",
            "percentage",
            "exact_match_count",
            "mismatch_count",
            "denominator_count",
            "numerator",
            "denominator",
            "metric",
            "metric_family",
            "authority_scope",
            "dry_run_payload",
            "candidate_summary",
            "manual_score",
            "override",
            "force",
            "aggregate_method",
            "ranking_method",
            "weight",
            "threshold",
        }

        for name in backend_public:
            self.assertTrue(callable(getattr(scoring_result, name, None)))
            self.assertTrue(callable(getattr(api, name, None)))
        for name in forbidden_public:
            self.assertFalse(hasattr(scoring_result, name))
            self.assertFalse(hasattr(api, name))

        for signature_target in (
            api.build_deployed_rule_effectiveness_scoring_result_plan,
            api.record_deployed_rule_effectiveness_scoring_result,
            api.build_deployed_rule_effectiveness_scoring_result_summary_surface,
        ):
            signature = inspect.signature(signature_target)
            for forbidden_param in forbidden_api_params:
                self.assertNotIn(forbidden_param, signature.parameters)

        panel_source = Path(desktop_panel.__file__).read_text(encoding="utf-8")
        scoring_section = panel_source.split("Persisted Effectiveness Scoring Result", 1)[1].split("Controlled Topic Taxonomy", 1)[0]
        for required in (
            "Load Persisted Scoring Result",
            "Validate Persisted Scoring Result Eligibility",
            "Persisted Scoring Result Health",
            "Copy Persisted Scoring Result Report",
            "Build Persisted Scoring Result Plan",
            "Record Persisted Scoring Result",
            "Load Persisted Scoring Result Summary",
            "Copy Persisted Scoring Result Summary Report",
        ):
            self.assertIn(required, scoring_section)
        for forbidden in (
            "Force Score",
            "Override Score",
            "Manual Score",
            "Edit Score",
            "Delete Score",
            "Recalculate Score",
            "Aggregate Score",
            "Rank Results",
            "Compare Results",
            "Persist Caller Score",
            "Override Numerator",
            "Override Denominator",
            "Override Metric",
            "Override Outcome Truth",
            "Override Authority Scope",
            "Score Dashboard",
            '("Score Ratio", self.deployed_rule_effectiveness_scoring_result',
            '("Score Percentage", self.deployed_rule_effectiveness_scoring_result',
            '("Exact Match Count", self.deployed_rule_effectiveness_scoring_result',
            '("Mismatch Count", self.deployed_rule_effectiveness_scoring_result',
            '("Denominator Count", self.deployed_rule_effectiveness_scoring_result',
            '("Authority Scope", self.deployed_rule_effectiveness_scoring_result',
            '("Metric Family", self.deployed_rule_effectiveness_scoring_result',
        ):
            self.assertNotIn(forbidden, scoring_section)

        docs_text = Path("docs/DEPLOYED_RULE_EFFECTIVENESS_SCORING_RESULT.md").read_text(encoding="utf-8")
        for required in (
            "## Final Release Handoff Notes",
            "This feature records and displays persisted scoped accuracy-like exact-match scoring results only.",
            "It does not establish broad rule effectiveness, deployment safety, production correctness, profitability, prediction quality, future performance, ranking quality, or aggregate effectiveness.",
            "Focused exact-node tests were run by policy; broad regression coverage was intentionally not claimed.",
            "## Focused Validation Limits",
            "Known risks remain limited to prerequisite modules outside this feature path",
        ):
            self.assertIn(required, docs_text)
        for forbidden_phrase in (
            "broad regression coverage is established",
            "safe deployment",
            "successful deployment",
            "final effectiveness",
            "overall score",
            "production score",
        ):
            self.assertNotIn(forbidden_phrase, docs_text.lower())

        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            read_only_before = sorted(str(path.relative_to(root)) for path in root.rglob("*.json")) if root.exists() else []
            manifest = scoring_result.get_deployed_rule_effectiveness_scoring_result_manifest(root=root)
            workspace = scoring_result.build_deployed_rule_effectiveness_scoring_result_workspace(
                "rule-missing",
                "deployment-missing",
                "target-missing",
                "deployed-missing",
                "snapshot-missing",
                "readiness-missing",
                "spec-missing",
                "truth-result-missing",
                "record-set-missing",
                "contract-missing",
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            eligibility = scoring_result.validate_deployed_rule_effectiveness_scoring_result_eligibility(
                "rule-missing",
                "deployment-missing",
                "target-missing",
                "deployed-missing",
                "snapshot-missing",
                "readiness-missing",
                "spec-missing",
                "truth-result-missing",
                "record-set-missing",
                "contract-missing",
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            load_missing = scoring_result.load_deployed_rule_effectiveness_scoring_result("missing", root=root)
            health = scoring_result.get_deployed_rule_effectiveness_scoring_result_health(root=root)
            report = scoring_result.format_deployed_rule_effectiveness_scoring_result_report(
                "rule-missing",
                "deployment-missing",
                "target-missing",
                "deployed-missing",
                "snapshot-missing",
                "readiness-missing",
                "spec-missing",
                "truth-result-missing",
                "record-set-missing",
                "contract-missing",
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            summary = scoring_result.build_deployed_rule_effectiveness_scoring_result_summary_surface(root=root)
            summary_report = scoring_result.format_deployed_rule_effectiveness_scoring_result_summary_surface_report(root=root)
            read_only_after = sorted(str(path.relative_to(root)) for path in root.rglob("*.json")) if root.exists() else []

            panel = object.__new__(desktop_panel.DesktopRightPanelMixin)

            class _Var:
                def __init__(self, value: str = "") -> None:
                    self._value = value
                def get(self) -> str:
                    return self._value
                def set(self, value: str) -> None:
                    self._value = value

            panel.deployed_rule_effectiveness_scoring_result_status_var = _Var("")
            panel.deployed_rule_effectiveness_scoring_result_plan_id_var = _Var("plan-1")
            panel.deployed_rule_effectiveness_scoring_result_id_var = _Var("score-1")
            panel._set_deployed_rule_effectiveness_scoring_result_status({
                "status": "corrupt",
                "authority_scope": "unknown",
                "score_family": "unknown",
                "blockers": ["forbidden_field"],
                "warnings": [],
                "recommended_action": "Review corrupt persisted scoped accuracy-like exact-match scoring result data.",
            })
            corrupt_status = panel.deployed_rule_effectiveness_scoring_result_status_var.get()

        self.assertEqual(manifest["required_confirmation"], scoring_result.REQUIRED_CONFIRMATION)
        self.assertEqual(read_only_before, read_only_after)
        self.assertEqual(workspace["status"], "blocked")
        self.assertEqual(eligibility["status"], "blocked")
        self.assertEqual(load_missing["status"], "blocked")
        self.assertEqual(health["status"], "healthy")
        self.assertEqual(summary["writes_performed"], 0)
        self.assertEqual(summary["loaded_result_summary"], None)
        self.assertIn("Authority scope is limited to registered outcome-truth exact-match accuracy-like evidence.", report)
        self.assertIn("This is not deployment safety.", report)
        self.assertIn("This is not broad production correctness.", report)
        self.assertIn("This is not profitability.", report)
        self.assertIn("This is not prediction quality.", report)
        self.assertIn("Phase 9W acceptance was not used as scoring input.", report)
        self.assertIn("Runtime completion was not used as correctness.", report)
        self.assertIn("Source availability alone was not used as effectiveness.", report)
        self.assertIn("No new score was calculated by the summary.", summary_report)
        self.assertNotIn("success rate", summary_report.lower())
        self.assertNotIn("rank", summary_report.lower())
        self.assertNotIn("compare", summary_report.lower())
        self.assertNotIn(str(root), report)
        self.assertNotIn(str(root), summary_report)
        self.assertIn("Status: corrupt", corrupt_status)
        self.assertNotIn("Persisted Accuracy-Like Score Ratio: 0.", corrupt_status)
        self.assertNotIn("Persisted Accuracy-Like Score Percentage: 0.", corrupt_status)
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
        ):
            self.assertNotIn(forbidden_key, report)
            self.assertNotIn(forbidden_key, summary_report)

    def test_phase_10a_next_feature_planning_gate_documents_safe_next_scope(self) -> None:
        planning_doc = Path("docs/PHASE_10A_NEXT_FEATURE_PLANNING_GATE.md")
        self.assertTrue(planning_doc.exists())
        text = planning_doc.read_text(encoding="utf-8")
        lower_text = text.lower()

        for required in (
            "# Phase 10A Next Feature Planning Gate",
            "## Known Risks",
            "Option A",
            "Phase 10B — Prerequisite Read-Path No-Write Audit",
            "registered_outcome_truth_exact_match_accuracy_like",
            "no aggregate effectiveness",
            "no ranking or comparison",
        ):
            self.assertIn(required, text)
        self.assertIn(
            "prerequisite modules outside the persisted scoring-result path may still create storage eagerly in their own read paths",
            lower_text,
        )

        for forbidden in (
            "recommended phase 10b title:\n\n- `phase 10b — operator workflow polish`",
            "new metric family is recommended as the immediate next step",
            "broad regression coverage is established",
        ):
            self.assertNotIn(forbidden, lower_text)

    def test_scoring_contract_and_outcome_truth_read_paths_do_not_create_storage_when_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"

            def _snapshot_tree() -> tuple[list[str], dict[str, str]]:
                if not root.exists():
                    return ([], {})
                directories = sorted(
                    str(path.relative_to(root))
                    for path in root.rglob("*")
                    if path.is_dir()
                )
                files = {
                    str(path.relative_to(root)): path.read_text(encoding="utf-8")
                    for path in sorted(root.rglob("*"))
                    if path.is_file()
                }
                return directories, files

            before_dirs, before_files = _snapshot_tree()
            contract_manifest = scoring_contract.get_deployed_rule_effectiveness_scoring_contract_manifest(root=root)
            contract_loaded = scoring_contract.load_deployed_rule_effectiveness_scoring_contract_result(
                "missing-contract",
                root=root,
            )
            contract_health = scoring_contract.get_deployed_rule_effectiveness_scoring_contract_health(root=root)
            contract_report = scoring_contract.format_deployed_rule_effectiveness_scoring_contract_report(
                "rule-missing",
                "deployment-missing",
                "target-missing",
                "deployed-missing",
                "snapshot-missing",
                "readiness-missing",
                "spec-missing",
                "truth-result-missing",
                "record-set-missing",
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            truth_manifest = truth.get_deployed_rule_outcome_truth_source_manifest(root=root)
            truth_loaded = truth.load_deployed_rule_outcome_truth_source_result(
                "missing-truth-source",
                root=root,
            )
            truth_health = truth.get_deployed_rule_outcome_truth_source_health(root=root)
            truth_report = truth.format_deployed_rule_outcome_truth_source_report(
                "rule-missing",
                "deployment-missing",
                "target-missing",
                "deployed-missing",
                "snapshot-missing",
                "readiness-missing",
                "spec-missing",
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                outcome_truth_source_id="missing-source-id",
                outcome_truth_record_set_id="missing-record-set",
                root=root,
            )
            record_set_loaded = truth.load_deployed_rule_outcome_truth_record_set(
                "missing-record-set",
                root=root,
            )
            listed_sets = truth.list_deployed_rule_outcome_truth_record_sets(
                "rule-missing",
                "deployment-missing",
                "target-missing",
                "deployed-missing",
                "snapshot-missing",
                root=root,
            )
            truth_record_validation = truth.validate_deployed_rule_outcome_truth_record_set(
                "rule-missing",
                "deployment-missing",
                "target-missing",
                "deployed-missing",
                "snapshot-missing",
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                source_id="missing-source-id",
                source_type="external_authoritative_result",
                source_authority_class="authoritative",
                records=[{"execution_event_id": "event-1"}],
                root=root,
            )
            after_dirs, after_files = _snapshot_tree()

        self.assertEqual(before_dirs, [])
        self.assertEqual(before_files, {})
        self.assertEqual(after_dirs, [])
        self.assertEqual(after_files, {})
        self.assertEqual(contract_manifest["required_identifiers"][0], "canonical_rule_id")
        self.assertEqual(truth_manifest["required_identifiers"][0], "canonical_rule_id")
        self.assertEqual(contract_loaded["status"], "blocked")
        self.assertEqual(contract_loaded.get("writes_performed", 0), 0)
        self.assertEqual(contract_health["status"], "healthy")
        self.assertIn(contract_report.splitlines()[1], ("Scoring-contract status: blocked", "Scoring-contract status: corrupt"))
        self.assertEqual(truth_loaded["status"], "blocked")
        self.assertEqual(truth_loaded.get("writes_performed", 0), 0)
        self.assertEqual(truth_health["status"], "healthy")
        self.assertIn("Outcome-truth source status: blocked", truth_report)
        self.assertEqual(record_set_loaded["status"], "blocked")
        self.assertEqual(record_set_loaded.get("writes_performed", 0), 0)
        self.assertEqual(listed_sets["status"], "listed")
        self.assertEqual(listed_sets["items"], [])
        self.assertEqual(truth_record_validation["status"], "blocked")
        self.assertEqual(truth_record_validation.get("writes_performed", 0), 0)

        contract_read_only = (
            scoring_contract.get_deployed_rule_effectiveness_scoring_contract_manifest,
            scoring_contract.build_deployed_rule_effectiveness_scoring_contract_workspace,
            scoring_contract.validate_deployed_rule_effectiveness_scoring_contract_eligibility,
            scoring_contract.load_deployed_rule_effectiveness_scoring_contract_result,
            scoring_contract.get_deployed_rule_effectiveness_scoring_contract_health,
            scoring_contract.format_deployed_rule_effectiveness_scoring_contract_report,
        )
        truth_read_only = (
            truth.get_deployed_rule_outcome_truth_source_manifest,
            truth.build_deployed_rule_outcome_truth_source_workspace,
            truth.validate_deployed_rule_outcome_truth_source_eligibility,
            truth.load_deployed_rule_outcome_truth_source_result,
            truth.get_deployed_rule_outcome_truth_source_health,
            truth.format_deployed_rule_outcome_truth_source_report,
            truth.validate_deployed_rule_outcome_truth_record_set,
            truth.load_deployed_rule_outcome_truth_record_set,
            truth.list_deployed_rule_outcome_truth_record_sets,
        )
        forbidden_calls = (
            "_ensure_dirs(",
            "build_deployed_rule_effectiveness_scoring_contract_plan(",
            "record_deployed_rule_effectiveness_scoring_contract_result(",
            "build_deployed_rule_outcome_truth_source_plan(",
            "record_deployed_rule_outcome_truth_source_result(",
            "register_deployed_rule_outcome_truth_record_set(",
        )
        for func in contract_read_only + truth_read_only:
            source = inspect.getsource(func)
            for forbidden in forbidden_calls:
                self.assertNotIn(forbidden, source, msg=f"{func.__name__} unexpectedly contains {forbidden}")

        self.assertEqual(scoring_result.AUTHORITY_SCOPE, "registered_outcome_truth_exact_match_accuracy_like")
