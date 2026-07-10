from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import certified_rule_post_deployment_acceptance as acceptance
from backend.electional import deployed_rule_effectiveness_evaluation_spec as spec
from backend.electional import deployed_rule_effectiveness_readiness as readiness
from backend.electional import deployed_rule_execution_runtime as runtime
from backend.electional import deployed_rule_operational_telemetry as telemetry
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


def _readiness_result(root: Path, built: dict[str, object], *, attempts: int, post_deployment_result_id: str | None = None) -> dict[str, object]:
    _record_attempts(root, built, attempts)
    snapshot = _snapshot(root, built)
    plan = readiness.build_deployed_rule_effectiveness_readiness_plan(
        built["rule_id"],
        built["production_deployment_run"]["production_deployment_result_id"],
        "production_target_primary",
        built["production_deployment_run"]["deployed_rule_id"],
        snapshot["snapshot_id"],
        "2026-07-10T10:00:00Z",
        "2026-07-10T12:59:00Z",
        post_deployment_result_id=post_deployment_result_id,
        root=root,
    )
    result = readiness.record_deployed_rule_effectiveness_readiness_result(
        plan["effectiveness_readiness_plan_id"],
        confirmation=readiness.REQUIRED_CONFIRMATION,
        root=root,
    )
    return {"snapshot": snapshot, "plan": plan, "result": result}


class DeployedRuleEffectivenessEvaluationSpecTest(TestCase):
    def test_missing_readiness_result_blocks_spec_without_scoring(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            snapshot = _snapshot(root, built)
            eligibility = spec.validate_deployed_rule_effectiveness_evaluation_spec_eligibility(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                snapshot["snapshot_id"],
                "missing_readiness_result",
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
        self.assertEqual(eligibility["status"], "spec_ready_scoring_blocked_missing_readiness")
        self.assertTrue(eligibility["criteria"]["effectiveness_score_not_calculated"])

    def test_ready_readiness_without_outcome_truth_blocks_scoring(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            ready = _readiness_result(root, built, attempts=readiness.MINIMUM_EXECUTION_ATTEMPTS)
            eligibility = spec.validate_deployed_rule_effectiveness_evaluation_spec_eligibility(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                ready["snapshot"]["snapshot_id"],
                ready["result"]["effectiveness_readiness_result_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
        self.assertEqual(eligibility["status"], "spec_ready_scoring_blocked_missing_outcome_truth")
        self.assertTrue(eligibility["criteria"]["readiness_result_ready_for_effectiveness_evaluation"])
        self.assertFalse(eligibility["criteria"]["outcome_truth_source_available"])

    def test_runtime_completion_is_not_treated_as_correctness(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            ready = _readiness_result(root, built, attempts=readiness.MINIMUM_EXECUTION_ATTEMPTS)
            workspace = spec.build_deployed_rule_effectiveness_evaluation_spec_workspace(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                ready["snapshot"]["snapshot_id"],
                ready["result"]["effectiveness_readiness_result_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
        self.assertEqual(workspace["status"], "spec_ready_scoring_blocked_missing_outcome_truth")
        self.assertIn("latency_or_runtime_reliability_metric", workspace["metric_contract"])
        self.assertEqual(workspace["metric_contract"]["latency_or_runtime_reliability_metric"]["required_numerator"], "successful_runtime_completion_count_or_latency_samples")

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
            ready = _readiness_result(
                root,
                built,
                attempts=readiness.MINIMUM_EXECUTION_ATTEMPTS,
                post_deployment_result_id=acceptance_result["post_deployment_acceptance_result_id"],
            )
            eligibility = spec.validate_deployed_rule_effectiveness_evaluation_spec_eligibility(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                ready["snapshot"]["snapshot_id"],
                ready["result"]["effectiveness_readiness_result_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
        self.assertTrue(eligibility["criteria"]["phase_9w_not_used_as_effectiveness_evidence"])
        self.assertEqual(eligibility["status"], "spec_ready_scoring_blocked_missing_outcome_truth")

    def test_metric_contract_defines_requirements_without_computing_values(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            manifest = spec.get_deployed_rule_effectiveness_evaluation_spec_manifest(root=root)
            contract = spec._metric_contract(outcome_truth_available=False, denominator_contract_available=True)
        self.assertIn("accuracy_like_metric", manifest["supported_metric_categories"])
        self.assertIn("required_inputs", contract["accuracy_like_metric"])
        self.assertNotIn("value", contract["accuracy_like_metric"])
        self.assertEqual(contract["accuracy_like_metric"]["unsupported_reason"], "outcome_truth_source_unavailable")

    def test_spec_plan_is_deterministic_immutable_and_idempotent(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            ready = _readiness_result(root, built, attempts=readiness.MINIMUM_EXECUTION_ATTEMPTS)
            first = spec.build_deployed_rule_effectiveness_evaluation_spec_plan(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                ready["snapshot"]["snapshot_id"],
                ready["result"]["effectiveness_readiness_result_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            second = spec.build_deployed_rule_effectiveness_evaluation_spec_plan(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                ready["snapshot"]["snapshot_id"],
                ready["result"]["effectiveness_readiness_result_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
        self.assertEqual(first["status"], "planned")
        self.assertEqual(second["writes_performed"], 0)
        self.assertEqual(first["plan_fingerprint"], second["plan_fingerprint"])

    def test_spec_result_requires_confirmation_and_is_immutable(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            ready = _readiness_result(root, built, attempts=readiness.MINIMUM_EXECUTION_ATTEMPTS)
            plan = spec.build_deployed_rule_effectiveness_evaluation_spec_plan(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                ready["snapshot"]["snapshot_id"],
                ready["result"]["effectiveness_readiness_result_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
            blocked = spec.record_deployed_rule_effectiveness_evaluation_spec_result(
                plan["effectiveness_evaluation_spec_plan_id"],
                confirmation="wrong",
                root=root,
            )
            first = spec.record_deployed_rule_effectiveness_evaluation_spec_result(
                plan["effectiveness_evaluation_spec_plan_id"],
                confirmation=spec.REQUIRED_CONFIRMATION,
                root=root,
            )
            second = spec.record_deployed_rule_effectiveness_evaluation_spec_result(
                plan["effectiveness_evaluation_spec_plan_id"],
                confirmation=spec.REQUIRED_CONFIRMATION,
                root=root,
            )
            loaded = spec.load_deployed_rule_effectiveness_evaluation_spec_result(
                first["effectiveness_evaluation_spec_result_id"],
                root=root,
            )
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(first["status"], "spec_ready_scoring_blocked_missing_outcome_truth")
        self.assertEqual(first["writes_performed"], 1)
        self.assertEqual(second["status"], "already_recorded")
        self.assertEqual(loaded["status"], "spec_ready_scoring_blocked_missing_outcome_truth")

    def test_report_states_no_effectiveness_score_and_missing_outcome_truth(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _deployed_inputs(root)
            ready = _readiness_result(root, built, attempts=readiness.MINIMUM_EXECUTION_ATTEMPTS)
            report = spec.format_deployed_rule_effectiveness_evaluation_spec_report(
                built["rule_id"],
                built["production_deployment_run"]["production_deployment_result_id"],
                "production_target_primary",
                built["production_deployment_run"]["deployed_rule_id"],
                ready["snapshot"]["snapshot_id"],
                ready["result"]["effectiveness_readiness_result_id"],
                "2026-07-10T10:00:00Z",
                "2026-07-10T12:59:00Z",
                root=root,
            )
        self.assertIn("This is specification only; no effectiveness score was calculated.", report)
        self.assertIn("Outcome-truth status: unavailable_in_repository", report)
        self.assertIn("Execution completion is not correctness.", report)
