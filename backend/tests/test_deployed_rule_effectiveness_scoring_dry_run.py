from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import api
from backend.electional import deployed_rule_effectiveness_evaluation_spec as spec
from backend.electional import deployed_rule_effectiveness_readiness as readiness
from backend.electional import deployed_rule_effectiveness_scoring_contract as contract
from backend.electional import deployed_rule_effectiveness_scoring_dry_run as dry_run
from backend.electional import deployed_rule_execution_runtime as runtime
from backend.electional import deployed_rule_operational_telemetry as telemetry
from backend.electional import deployed_rule_outcome_truth_source as truth
from backend.tests.test_certified_rule_post_deployment_acceptance import _deployed_inputs

FORBIDDEN_AUTHORITATIVE_KEYS = {
    "effectiveness_score",
    "correctness_score",
    "success_rate",
    "failure_rate",
    "production_score",
    "authoritative_score",
    "deployed_rule_score",
    "final_score",
    "persisted_score",
    "scoring_result_id",
    "scoring_receipt_id",
}


def _tracked_state(root: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for folder in (
        "canonical_rules",
        "production_activation_transactions",
        "certified_rule_production_deployment_plans",
        "certified_rule_production_deployment_results",
        "certified_rule_production_deployment_receipts",
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


def _tree_snapshot(root: Path) -> set[str]:
    if not root.exists():
        return set()
    snapshot: set[str] = set()
    for path in root.rglob("*"):
        if path.is_file() or path.is_dir():
            snapshot.add(str(path.relative_to(root)))
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


def _event_items(root: Path, built: dict[str, object], minimum: int = 2) -> list[dict[str, object]]:
    listing = telemetry.list_deployed_rule_operational_events(
        built["production_deployment_run"]["deployed_rule_id"],
        built["production_deployment_run"]["production_deployment_result_id"],
        root=root,
    )
    items = list(listing.get("items", []))
    if len(items) < minimum:
        _record_attempts(root, built, minimum)
        listing = telemetry.list_deployed_rule_operational_events(
            built["production_deployment_run"]["deployed_rule_id"],
            built["production_deployment_run"]["production_deployment_result_id"],
            root=root,
        )
        items = list(listing.get("items", []))
    return [dict(item) for item in items]


def _valid_records(root: Path, built: dict[str, object]) -> list[dict[str, object]]:
    items = _event_items(root, built, 2)
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


def _register_truth_and_contract(
    root: Path,
    built: dict[str, object],
    records: list[dict[str, object]],
    *,
    source_id: str = "dry-run-source",
    source_type: str = "external_authoritative_result",
) -> dict[str, object]:
    state = _readiness_and_spec(root, built)
    registered = truth.register_deployed_rule_outcome_truth_record_set(
        built["rule_id"],
        built["production_deployment_run"]["production_deployment_result_id"],
        "production_target_primary",
        built["production_deployment_run"]["deployed_rule_id"],
        state["snapshot"]["snapshot_id"],
        "2026-07-10T10:00:00Z",
        "2026-07-10T12:59:00Z",
        source_id=source_id,
        source_type=source_type,
        source_authority_class="authoritative",
        records=records,
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
        outcome_truth_source_id=source_id,
        outcome_truth_record_set_id=registered["outcome_truth_record_set_id"],
        root=root,
    )
    truth_result = truth.record_deployed_rule_outcome_truth_source_result(
        truth_plan["outcome_truth_source_plan_id"],
        confirmation=truth.REQUIRED_CONFIRMATION,
        root=root,
    )
    scoring_plan = contract.build_deployed_rule_effectiveness_scoring_contract_plan(
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
    scoring_result = contract.record_deployed_rule_effectiveness_scoring_contract_result(
        scoring_plan["effectiveness_scoring_contract_plan_id"],
        confirmation=contract.REQUIRED_CONFIRMATION,
        root=root,
    )
    return {
        "built": built,
        "state": state,
        "registered": registered,
        "truth_result": truth_result,
        "scoring_plan": scoring_plan,
        "scoring_result": scoring_result,
    }


def _run_dry_run(root: Path, chain: dict[str, object], *, requested_metric_families: list[str] | None = None) -> dict[str, object]:
    built = chain["built"]
    state = chain["state"]
    return dry_run.run_deployed_rule_effectiveness_scoring_dry_run(
        built["rule_id"],
        built["production_deployment_run"]["production_deployment_result_id"],
        "production_target_primary",
        built["production_deployment_run"]["deployed_rule_id"],
        state["snapshot"]["snapshot_id"],
        state["readiness_result"]["effectiveness_readiness_result_id"],
        state["spec_result"]["effectiveness_evaluation_spec_result_id"],
        chain["truth_result"]["outcome_truth_source_result_id"],
        chain["registered"]["outcome_truth_record_set_id"],
        chain["scoring_result"]["effectiveness_scoring_contract_result_id"],
        "2026-07-10T10:00:00Z",
        "2026-07-10T12:59:00Z",
        requested_metric_families=requested_metric_families,
        root=root,
    )


def _assert_no_forbidden_keys(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in FORBIDDEN_AUTHORITATIVE_KEYS:
                raise AssertionError(f"forbidden authoritative key found: {key}")
            _assert_no_forbidden_keys(nested)
        return
    if isinstance(value, list):
        for item in value:
            _assert_no_forbidden_keys(item)


def _assert_dry_run_result_shape(result: dict[str, object]) -> None:
    for key, expected in (
        ("dry_run_only", True),
        ("authoritative_result", False),
        ("persistence_performed", False),
    ):
        assert key in result
        assert result[key] is expected
    assert result.get("writes_performed") == 0
    assert isinstance(result.get("metric_family_results"), dict)
    assert isinstance(result.get("blockers"), list)
    assert isinstance(result.get("warnings"), list)
    assert isinstance(result.get("recommended_action"), str)
    summary = result.get("candidate_accuracy_like_summary")
    assert isinstance(summary, dict)
    for key in (
        "candidate_exact_match_count",
        "candidate_mismatch_count",
        "candidate_denominator_count",
        "candidate_accuracy_ratio",
        "candidate_accuracy_percentage",
        "calculation_scope",
    ):
        assert key in summary
    _assert_no_forbidden_keys(result)


class DeployedRuleEffectivenessScoringDryRunTest(TestCase):
    def test_dry_run_boundary_remains_non_authoritative_non_persistent_and_unexposed(self) -> None:
        dry_run_source = Path("backend/electional/deployed_rule_effectiveness_scoring_dry_run.py").read_text(encoding="utf-8")
        api_source = Path("backend/electional/api.py").read_text(encoding="utf-8")
        desktop_source = Path("backend/electional/desktop_right_panel.py").read_text(encoding="utf-8")
        docs_source = Path("docs/DEPLOYED_RULE_EFFECTIVENESS_SCORING_DRY_RUN.md").read_text(encoding="utf-8")

        for exported in (
            "get_deployed_rule_effectiveness_scoring_dry_run_manifest",
            "build_deployed_rule_effectiveness_scoring_dry_run_workspace",
            "validate_deployed_rule_effectiveness_scoring_dry_run_eligibility",
            "run_deployed_rule_effectiveness_scoring_dry_run",
            "format_deployed_rule_effectiveness_scoring_dry_run_report",
        ):
            self.assertTrue(hasattr(dry_run, exported))
            self.assertFalse(hasattr(api, exported))
        for forbidden_api in (
            "def get_deployed_rule_effectiveness_scoring_dry_run_manifest(",
            "def build_deployed_rule_effectiveness_scoring_dry_run_workspace(",
            "def validate_deployed_rule_effectiveness_scoring_dry_run_eligibility(",
            "def run_deployed_rule_effectiveness_scoring_dry_run(",
            "def format_deployed_rule_effectiveness_scoring_dry_run_report(",
        ):
            self.assertNotIn(forbidden_api, api_source)
        for forbidden_ui in (
            "Run Dry-Run Scoring",
            "Calculate Dry-Run",
            "Deployed Rule Effectiveness Scoring Dry Run",
            "Dry-Run Candidate Accuracy",
            "Persist Dry-Run Score",
            "Dry-Run Scoring Workspace",
            "Dry-Run Scoring Report",
        ):
            self.assertNotIn(forbidden_ui, desktop_source)
        for forbidden_desktop_call in (
            "run_deployed_rule_effectiveness_scoring_dry_run(",
            "build_deployed_rule_effectiveness_scoring_dry_run_workspace(",
            "validate_deployed_rule_effectiveness_scoring_dry_run_eligibility(",
            "format_deployed_rule_effectiveness_scoring_dry_run_report(",
        ):
            self.assertNotIn(forbidden_desktop_call, desktop_source)
        for forbidden_write_pattern in (
            "open(",
            "json.dump(",
            "_atomic_write_json",
            "write_text(",
            "write_bytes(",
            "mkdir(",
            "scoring_results",
            "score_history",
            "dry_run_history",
            "record_result",
        ):
            self.assertNotIn(forbidden_write_pattern, dry_run_source)
        self.assertNotIn("receipt", dry_run_source)
        self.assertNotIn("index", dry_run_source)
        self.assertNotIn("save_", dry_run_source)

        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            chain = _register_truth_and_contract(root, built, _valid_records(root, built))
            before_state = _tracked_state(root)
            before_tree = _tree_snapshot(root)

            workspace = dry_run.build_deployed_rule_effectiveness_scoring_dry_run_workspace(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                chain["state"]["snapshot"]["snapshot_id"],
                chain["state"]["readiness_result"]["effectiveness_readiness_result_id"],
                chain["state"]["spec_result"]["effectiveness_evaluation_spec_result_id"],
                chain["truth_result"]["outcome_truth_source_result_id"],
                chain["registered"]["outcome_truth_record_set_id"],
                chain["scoring_result"]["effectiveness_scoring_contract_result_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            eligibility = dry_run.validate_deployed_rule_effectiveness_scoring_dry_run_eligibility(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                chain["state"]["snapshot"]["snapshot_id"],
                chain["state"]["readiness_result"]["effectiveness_readiness_result_id"],
                chain["state"]["spec_result"]["effectiveness_evaluation_spec_result_id"],
                chain["truth_result"]["outcome_truth_source_result_id"],
                chain["registered"]["outcome_truth_record_set_id"],
                chain["scoring_result"]["effectiveness_scoring_contract_result_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                requested_metric_families=[
                    "accuracy_like_contract",
                    "runtime_reliability_contract",
                    "false_positive_false_negative_contract",
                    "precision_recall_like_contract",
                    "calibration_like_contract",
                ],
                root=root,
            )
            result = _run_dry_run(
                root,
                chain,
                requested_metric_families=[
                    "accuracy_like_contract",
                    "runtime_reliability_contract",
                    "false_positive_false_negative_contract",
                    "precision_recall_like_contract",
                    "calibration_like_contract",
                ],
            )
            result_again = _run_dry_run(
                root,
                chain,
                requested_metric_families=[
                    "accuracy_like_contract",
                    "runtime_reliability_contract",
                    "false_positive_false_negative_contract",
                    "precision_recall_like_contract",
                    "calibration_like_contract",
                ],
            )
            report = dry_run.format_deployed_rule_effectiveness_scoring_dry_run_report(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                chain["state"]["snapshot"]["snapshot_id"],
                chain["state"]["readiness_result"]["effectiveness_readiness_result_id"],
                chain["state"]["spec_result"]["effectiveness_evaluation_spec_result_id"],
                chain["truth_result"]["outcome_truth_source_result_id"],
                chain["registered"]["outcome_truth_record_set_id"],
                chain["scoring_result"]["effectiveness_scoring_contract_result_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                requested_metric_families=[
                    "accuracy_like_contract",
                    "runtime_reliability_contract",
                    "false_positive_false_negative_contract",
                    "precision_recall_like_contract",
                    "calibration_like_contract",
                ],
                root=root,
            )
            after_state = _tracked_state(root)
            after_tree = _tree_snapshot(root)

            missing_truth = dry_run.run_deployed_rule_effectiveness_scoring_dry_run(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                chain["state"]["snapshot"]["snapshot_id"],
                chain["state"]["readiness_result"]["effectiveness_readiness_result_id"],
                chain["state"]["spec_result"]["effectiveness_evaluation_spec_result_id"],
                chain["truth_result"]["outcome_truth_source_result_id"],
                "missing-record-set",
                chain["scoring_result"]["effectiveness_scoring_contract_result_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )

        _assert_dry_run_result_shape(result)
        _assert_dry_run_result_shape(result_again)
        self.assertEqual(before_state, after_state)
        self.assertEqual(before_tree, after_tree)
        self.assertEqual(workspace["status"], "dry_run_ready")
        self.assertEqual(eligibility["status"], "dry_run_ready")
        self.assertEqual(result["status"], "dry_run_ready")
        self.assertEqual(result["dry_run_fingerprint"], result_again["dry_run_fingerprint"])
        self.assertEqual(result["candidate_accuracy_like_summary"], result_again["candidate_accuracy_like_summary"])
        self.assertEqual(result["eligible_record_count"], result_again["eligible_record_count"])
        self.assertEqual(result["excluded_record_count"], result_again["excluded_record_count"])
        self.assertEqual(result["duplicate_collapsed_count"], result_again["duplicate_collapsed_count"])
        self.assertEqual(result["conflict_count"], result_again["conflict_count"])
        self.assertEqual(result["metric_family_results"], result_again["metric_family_results"])
        self.assertEqual(result["blockers"], result_again["blockers"])
        self.assertEqual(result["warnings"], result_again["warnings"])
        self.assertTrue(result["dry_run_only"])
        self.assertFalse(result["authoritative_result"])
        self.assertFalse(result["persistence_performed"])
        self.assertEqual(result["writes_performed"], 0)
        self.assertEqual(result["eligible_record_count"], 2)
        self.assertEqual(result["excluded_record_count"], 0)
        self.assertEqual(result["duplicate_collapsed_count"], 0)
        self.assertEqual(result["conflict_count"], 0)
        accuracy = result["candidate_accuracy_like_summary"]
        self.assertEqual(accuracy["candidate_exact_match_count"], 1)
        self.assertEqual(accuracy["candidate_mismatch_count"], 1)
        self.assertEqual(accuracy["candidate_denominator_count"], 2)
        self.assertEqual(accuracy["candidate_accuracy_ratio"], 0.5)
        self.assertEqual(accuracy["candidate_accuracy_percentage"], 50.0)
        self.assertEqual(accuracy["calculation_scope"], "dry_run_only")
        self.assertEqual(result["metric_family_results"]["accuracy_like_contract"]["status"], "dry_run_calculated")
        self.assertEqual(result["metric_family_results"]["accuracy_like_contract"]["calculation_scope"], "dry_run_only")
        self.assertEqual(
            result["metric_family_results"]["runtime_reliability_contract"]["unsupported_reason"],
            "runtime_reliability_inputs_not_loaded_in_dry_run",
        )
        self.assertEqual(
            result["metric_family_results"]["false_positive_false_negative_contract"]["unsupported_reason"],
            "class_semantics_not_defined",
        )
        self.assertEqual(
            result["metric_family_results"]["precision_recall_like_contract"]["unsupported_reason"],
            "positive_class_semantics_not_defined",
        )
        self.assertEqual(
            result["metric_family_results"]["calibration_like_contract"]["unsupported_reason"],
            "confidence_or_probability_evidence_missing",
        )
        self.assertIn("This is a dry run only.", report)
        self.assertIn("No authoritative effectiveness score was persisted.", report)
        self.assertIn("No production correctness result was produced.", report)
        self.assertIn("Dry-run candidate metrics are non-authoritative.", report)
        self.assertIn("Candidate metrics are not final.", report)
        self.assertIn("This dry run creates no deployment safety claim.", report)
        self.assertIn("Runtime completion is not correctness.", report)
        self.assertIn("Phase 9W acceptance is not scoring input.", report)
        self.assertIn("Source availability is not effectiveness.", report)
        self.assertIn("No API or desktop seam exists yet for this dry-run layer.", report)
        self.assertFalse((Path(tmp) / "store" / "deployed_rule_effectiveness_scoring_results").exists())
        self.assertFalse((Path(tmp) / "store" / "deployed_rule_effectiveness_scoring_receipts").exists())
        self.assertFalse((Path(tmp) / "store" / "indexes" / "deployed_rule_effectiveness_scoring_result_index.json").exists())
        self.assertEqual(missing_truth["status"], "blocked")
        self.assertIn("outcome_truth_record_set_missing", missing_truth["blockers"])

        edge_cases = (
            ({"execution_event_id": "", "input_fingerprint": ""}, "missing_execution_binding"),
            ({"expected_outcome": None}, "missing_expected_outcome"),
            ({"actual_or_adjudicated_outcome": None}, "missing_actual_or_adjudicated_outcome"),
            ({"outcome_observed_at": "2026-07-11T12:12:00Z"}, "record_outside_observation_window"),
        )
        for updates, expected_reason in edge_cases:
            with self.subTest(exclusion_reason=expected_reason):
                with TemporaryDirectory() as edge_tmp:
                    edge_root = Path(edge_tmp) / "store"
                    edge_built = _deployed_inputs(edge_root)
                    edge_chain = _register_truth_and_contract(edge_root, edge_built, _valid_records(edge_root, edge_built))
                    record_set = truth.load_deployed_rule_outcome_truth_record_set(
                        edge_chain["registered"]["outcome_truth_record_set_id"],
                        root=edge_root,
                    )
                    edge_record = dict(record_set["outcome_truth_records"][0])
                    edge_record.update(updates)
                    record_path = (
                        edge_root
                        / "deployed_rule_outcome_truth_sources"
                        / "records"
                        / f"{truth._safe_id(str(edge_record['outcome_truth_record_id']))}.json"
                    )
                    record_path.write_text(json.dumps(edge_record, indent=2, sort_keys=True), encoding="utf-8")
                    edge_result = _run_dry_run(edge_root, edge_chain, requested_metric_families=["accuracy_like_contract"])
                self.assertEqual(edge_result["excluded_record_count"], 1)
                self.assertEqual(edge_result["exclusion_reasons"][expected_reason], 1)

        with TemporaryDirectory() as unsupported_tmp:
            unsupported_root = Path(unsupported_tmp) / "store"
            unsupported_built = _deployed_inputs(unsupported_root)
            unsupported_chain = _register_truth_and_contract(
                unsupported_root,
                unsupported_built,
                _valid_records(unsupported_root, unsupported_built),
            )
            unsupported_set = truth.load_deployed_rule_outcome_truth_record_set(
                unsupported_chain["registered"]["outcome_truth_record_set_id"],
                root=unsupported_root,
            )
            unsupported_record = dict(unsupported_set["outcome_truth_records"][0])
            unsupported_record["truth_status"] = "unsupported"
            unsupported_record_path = (
                unsupported_root
                / "deployed_rule_outcome_truth_sources"
                / "records"
                / f"{truth._safe_id(str(unsupported_record['outcome_truth_record_id']))}.json"
            )
            unsupported_record_path.write_text(json.dumps(unsupported_record, indent=2, sort_keys=True), encoding="utf-8")
            unsupported_result = _run_dry_run(unsupported_root, unsupported_chain, requested_metric_families=["accuracy_like_contract"])
        self.assertGreaterEqual(unsupported_result["excluded_record_count"], 1)
        self.assertIn("unsupported_source_status", unsupported_result["exclusion_reasons"])

        with TemporaryDirectory() as conflict_tmp:
            conflict_root = Path(conflict_tmp) / "store"
            conflict_built = _deployed_inputs(conflict_root)
            conflict_events = _event_items(conflict_root, conflict_built, 1)
            first = conflict_events[0]
            conflicting_records = [
                {
                    "execution_event_id": str(first.get("event_id") or ""),
                    "input_fingerprint": str(first.get("input_fingerprint") or ""),
                    "expected_outcome": "venus_day",
                    "actual_or_adjudicated_outcome": "venus_day",
                    "outcome_observed_at": "2026-07-10T12:00:00Z",
                    "confidence_class": "high",
                },
                {
                    "execution_event_id": str(first.get("event_id") or ""),
                    "input_fingerprint": str(first.get("input_fingerprint") or ""),
                    "expected_outcome": "venus_day",
                    "actual_or_adjudicated_outcome": "venus_day",
                    "outcome_observed_at": "2026-07-10T12:00:00Z",
                    "confidence_class": "high",
                },
                {
                    "execution_event_id": str(first.get("event_id") or ""),
                    "input_fingerprint": str(first.get("input_fingerprint") or ""),
                    "expected_outcome": "venus_day",
                    "actual_or_adjudicated_outcome": "mars_day",
                    "outcome_observed_at": "2026-07-10T12:01:00Z",
                    "confidence_class": "high",
                },
            ]
            conflict_chain = _register_truth_and_contract(conflict_root, conflict_built, conflicting_records)
            conflicting = _run_dry_run(conflict_root, conflict_chain, requested_metric_families=["accuracy_like_contract"])
        self.assertEqual(conflicting["status"], "blocked")
        self.assertEqual(conflicting["duplicate_collapsed_count"], 1)
        self.assertEqual(conflicting["conflict_count"], 1)
        self.assertIn("conflicting_execution_binding", conflicting["blockers"])
        self.assertNotEqual(conflicting["metric_family_results"]["accuracy_like_contract"]["status"], "dry_run_calculated")

        self.assertIn("dry-run only", docs_source.lower())
        self.assertIn("non-authoritative", docs_source.lower())
        self.assertIn("no api or desktop seam exists yet for this dry-run layer", docs_source.lower())
        self.assertIn("not deployment safety evidence", docs_source.lower())

    def test_valid_contract_and_truth_records_produce_non_authoritative_dry_run_accuracy(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            chain = _register_truth_and_contract(root, built, _valid_records(root, built))
            result = _run_dry_run(root, chain, requested_metric_families=["accuracy_like_contract"])
        self.assertEqual(result["status"], "dry_run_ready")
        self.assertEqual(result["candidate_accuracy_like_summary"]["candidate_exact_match_count"], 1)
        self.assertEqual(result["candidate_accuracy_like_summary"]["candidate_mismatch_count"], 1)
        self.assertEqual(result["candidate_accuracy_like_summary"]["candidate_denominator_count"], 2)
        self.assertEqual(result["candidate_accuracy_like_summary"]["candidate_accuracy_ratio"], 0.5)
        self.assertEqual(result["candidate_accuracy_like_summary"]["candidate_accuracy_percentage"], 50.0)
