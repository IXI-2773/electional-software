from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional.api import (
    build_rule_effectiveness_recommendation_workspace as api_build_workspace,
    create_rule_action_candidate_from_recommendation as api_create_candidate,
    format_rule_effectiveness_recommendation_report as api_format_report,
    generate_rule_effectiveness_recommendation as api_generate_recommendation,
    save_rule_effectiveness_recommendation_decision as api_save_decision,
)
from backend.electional.rule_effectiveness_analysis import run_rule_effectiveness_backtest
from backend.electional.rule_effectiveness_recommendation import (
    create_rule_action_candidate_from_recommendation,
    generate_rule_effectiveness_recommendation,
    get_rule_effectiveness_recommendation_health,
    load_rule_effectiveness_recommendation,
    save_rule_effectiveness_recommendation_decision,
    validate_rule_effectiveness_recommendation_inputs,
)
from backend.tests.test_rule_effectiveness_analysis import _certified_rule, _chain, _dataset, _write_json


def _rewrite_outcomes(root: Path, values: list[bool], *, dataset_id: str = "historical_dataset_2025") -> None:
    path = root / "historical_rule_datasets" / f"{dataset_id}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    for record, value in zip(payload["records"], values, strict=True):
        record["observed_outcome"] = value
    _write_json(path, payload)


class RuleEffectivenessRecommendationTest(TestCase):
    def test_stale_or_invalid_analysis_blocks_recommendation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _certified_rule(root, "rule_027")
            _dataset(root, count=40)
            result = run_rule_effectiveness_backtest("rule_027", "historical_dataset_2025", root=root)
            payload = json.loads((root / "historical_rule_datasets" / "historical_dataset_2025.json").read_text(encoding="utf-8"))
            payload["records"].append({"record_id": "new_record", "timestamp_utc": "2025-02-01T00:00:00Z", "evaluation_context": {"controlled_field": "controlled_value"}, "observed_outcome": True})
            _write_json(root / "historical_rule_datasets" / "historical_dataset_2025.json", payload)
            validation = validate_rule_effectiveness_recommendation_inputs(result["analysis_id"], root=root)
            recommendation = generate_rule_effectiveness_recommendation(result["analysis_id"], root=root)
        self.assertIn("effectiveness_analysis_dataset_fingerprint_changed", validation["blockers"])
        self.assertEqual(recommendation["status"], "blocked")

    def test_default_policy_validation_and_fingerprint_are_deterministic(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _certified_rule(root, "rule_027")
            _dataset(root, count=40)
            result = run_rule_effectiveness_backtest("rule_027", "historical_dataset_2025", root=root)
            first = generate_rule_effectiveness_recommendation(result["analysis_id"], root=root)
            second = generate_rule_effectiveness_recommendation(result["analysis_id"], root=root)
        self.assertEqual(first["status"], "generated")
        self.assertEqual(first["policy_id"], "default_v1")
        self.assertTrue(str(first["policy_fingerprint"]).startswith("sha256:"))
        self.assertEqual(second["status"], "already_generated")

    def test_missing_labels_produces_insufficient_evidence_not_rollback(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _certified_rule(root, "rule_027")
            _dataset(root, count=40, include_labels=False)
            result = run_rule_effectiveness_backtest("rule_027", "historical_dataset_2025", root=root)
            recommendation = generate_rule_effectiveness_recommendation(result["analysis_id"], root=root)
        self.assertEqual(recommendation["recommendation_type"], "insufficient_evidence")
        self.assertNotEqual(recommendation["recommendation_type"], "rollback_candidate")

    def test_explicit_weak_metrics_produce_rollback_candidate(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _certified_rule(root, "rule_027")
            _certified_rule(root, "rule_021", value="different")
            _chain(root)
            _dataset(root, count=40)
            _rewrite_outcomes(root, [False, True] * 20)
            result = run_rule_effectiveness_backtest("rule_027", "historical_dataset_2025", comparison_rule_id="rule_021", root=root)
            recommendation = generate_rule_effectiveness_recommendation(result["analysis_id"], root=root)
        self.assertEqual(recommendation["recommendation_type"], "rollback_candidate")
        self.assertTrue(any(item["condition_id"] == "rollback_balanced_accuracy_below_threshold" for item in recommendation["triggered_conditions"]))

    def test_version_regression_can_produce_supersession_review_candidate(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _certified_rule(root, "rule_027")
            _certified_rule(root, "rule_021", value="different")
            _chain(root)
            _dataset(root, count=40)
            values: list[bool] = []
            even_true_budget = 9
            odd_true_budget = 11
            for index in range(40):
                if index % 2 == 0:
                    values.append(even_true_budget > 0)
                    even_true_budget -= 1
                else:
                    values.append(odd_true_budget > 0)
                    odd_true_budget -= 1
            _rewrite_outcomes(root, values)
            result = run_rule_effectiveness_backtest("rule_027", "historical_dataset_2025", comparison_rule_id="rule_021", root=root)
            recommendation = generate_rule_effectiveness_recommendation(result["analysis_id"], root=root)
        self.assertEqual(recommendation["recommendation_type"], "supersession_review_candidate")
        self.assertTrue(any(item["condition_id"] == "supersession_version_regression_met" for item in recommendation["triggered_conditions"]))

    def test_reject_defer_and_request_more_evidence_require_notes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _certified_rule(root, "rule_027")
            _dataset(root, count=40, include_labels=False)
            result = run_rule_effectiveness_backtest("rule_027", "historical_dataset_2025", root=root)
            recommendation = generate_rule_effectiveness_recommendation(result["analysis_id"], root=root)
            reject = save_rule_effectiveness_recommendation_decision(recommendation["recommendation_id"], "reject", root=root)
            defer = save_rule_effectiveness_recommendation_decision(recommendation["recommendation_id"], "defer", root=root)
            more = save_rule_effectiveness_recommendation_decision(recommendation["recommendation_id"], "request_more_evidence", root=root)
        self.assertEqual(reject["status"], "blocked")
        self.assertEqual(defer["status"], "blocked")
        self.assertEqual(more["status"], "blocked")
        self.assertIn("reviewer_note_required", reject["blockers"])

    def test_accepted_recommendation_requires_queue_confirmation_and_creates_candidate_atomically(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _certified_rule(root, "rule_027")
            _certified_rule(root, "rule_021", value="different")
            _chain(root)
            _dataset(root, count=40)
            _rewrite_outcomes(root, [False, True] * 20)
            analysis = run_rule_effectiveness_backtest("rule_027", "historical_dataset_2025", comparison_rule_id="rule_021", root=root)
            recommendation = generate_rule_effectiveness_recommendation(analysis["analysis_id"], root=root)
            review = save_rule_effectiveness_recommendation_decision(recommendation["recommendation_id"], "accept", root=root)
            blocked = create_rule_action_candidate_from_recommendation(review["recommendation_review_id"], root=root)
            queued = create_rule_action_candidate_from_recommendation(review["recommendation_review_id"], confirmation="QUEUE", root=root)
            receipt_path = root / "rule_effectiveness_recommendation_receipts" / f"rule_recommendation_receipt_{queued['action_candidate_id'][-24:]}.json"
            self.assertEqual(blocked["status"], "blocked")
            self.assertEqual(queued["status"], "queued")
            self.assertTrue((root / "rule_action_candidates" / f"{queued['action_candidate_id']}.json").exists())
            self.assertTrue(receipt_path.exists())

    def test_api_recommendation_idempotency_staleness_and_public_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _certified_rule(root, "rule_027")
            _certified_rule(root, "rule_021", value="different")
            _chain(root)
            _dataset(root, count=40)
            _rewrite_outcomes(root, [False, True] * 20)
            analysis = run_rule_effectiveness_backtest("rule_027", "historical_dataset_2025", comparison_rule_id="rule_021", root=root)
            workspace = api_build_workspace(analysis["analysis_id"], root=root)
            first = api_generate_recommendation(analysis["analysis_id"], root=root)
            second = api_generate_recommendation(analysis["analysis_id"], root=root)
            review = api_save_decision(first["recommendation_id"], "accept", root=root)
            queued = api_create_candidate(review["recommendation_review_id"], confirmation="QUEUE", root=root)
            duplicate_queue = api_create_candidate(review["recommendation_review_id"], confirmation="QUEUE", root=root)
            report = api_format_report(recommendation_id=first["recommendation_id"], action_candidate_id=queued["action_candidate_id"], public_safe=True, root=root)
            payload = json.loads((root / "historical_rule_datasets" / "historical_dataset_2025.json").read_text(encoding="utf-8"))
            payload["records"].append({"record_id": "late_record", "timestamp_utc": "2025-03-01T00:00:00Z", "evaluation_context": {"controlled_field": "controlled_value"}, "observed_outcome": False})
            _write_json(root / "historical_rule_datasets" / "historical_dataset_2025.json", payload)
            stale = load_rule_effectiveness_recommendation(first["recommendation_id"], root=root)
            health = get_rule_effectiveness_recommendation_health(root=root)
        self.assertEqual(workspace["policy_status"], "valid")
        self.assertEqual(second["status"], "already_generated")
        self.assertEqual(duplicate_queue["status"], "already_queued")
        self.assertTrue(stale["stale"])
        self.assertIn("Rule Effectiveness Recommendation Report", report)
        self.assertNotIn(str(root), report)
        self.assertNotIn("evaluation_context", report)
        self.assertNotIn("reviewer_note", report)
        self.assertIn(health["status"], {"stale", "warning"})
