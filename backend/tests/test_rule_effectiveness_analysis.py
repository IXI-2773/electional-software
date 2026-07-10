from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional.canonical_rule_runtime import create_canonical_rule
from backend.electional.rule_effectiveness_analysis import (
    build_rule_effectiveness_backtest_plan,
    build_rule_effectiveness_workspace,
    format_rule_effectiveness_report,
    get_rule_effectiveness_health,
    run_rule_effectiveness_backtest,
    validate_rule_effectiveness_inputs,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _rule(rule_id: str, *, scope: str = "documented_scope", value: object = "controlled_value") -> dict:
    return {
        "schema_version": "canonical_mutable_rule_v1",
        "rule_id": rule_id,
        "rule_type": "electional_constraint",
        "target": "controlled_target_x",
        "scope": scope,
        "condition": {"field": "controlled_field", "operator": "equals", "value": value},
        "operator": "equals",
        "value": value,
        "priority": 50,
        "enabled": True,
        "status": "active" if rule_id == "rule_027" else "inactive",
        "document_id": "doc_runtime_021",
        "source_proposal_id": f"proposal_{rule_id}",
        "source_promotion_receipt_id": f"promotion_{rule_id}",
        "source_rule_activation_review_id": f"review_{rule_id}",
        "source_revision": "source_rev_021",
    }


def _certified_rule(root: Path, rule_id: str, *, scope: str = "documented_scope", value: object = "controlled_value") -> None:
    payload = _rule(rule_id, scope=scope, value=value)
    create_canonical_rule({**payload, "status": "active", "enabled": True}, confirmation="CREATE_RULE", root=root)
    if rule_id != "rule_027":
        record = json.loads((root / "canonical_rules" / f"{rule_id}.json").read_text(encoding="utf-8"))
        record["status"] = "inactive"
        record["enabled"] = False
        record["updated_at_utc"] = "2026-01-02T00:00:00Z"
        record["rule_fingerprint"] = None
        (root / "canonical_rules" / f"{rule_id}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        index = json.loads((root / "indexes" / "canonical_rule_index.json").read_text(encoding="utf-8"))
        index["active_rule_ids"] = [item for item in index.get("active_rule_ids", []) if item != rule_id]
        index.setdefault("rule_fingerprints", {}).pop(rule_id, None)
        (root / "indexes" / "canonical_rule_index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    current = json.loads((root / "canonical_rules" / f"{rule_id}.json").read_text(encoding="utf-8"))
    certification = {
        "schema_version": "rule_activation_certification_receipt_v1",
        "certification_receipt_id": f"rule_certification_receipt_{rule_id}",
        "revalidation_id": f"impact_{rule_id}",
        "rule_id": rule_id,
        "rule_hash": "sha256:" + __import__("hashlib").sha256(json.dumps(current, sort_keys=True, default=str).encode("utf-8")).hexdigest(),
        "certification_status": "completed",
        "created_at_utc": "2026-01-02T00:00:00Z",
    }
    _write_json(root / "rule_activation_certification_receipts" / f"rule_certification_receipt_{rule_id}.json", certification)


def _chain(root: Path) -> None:
    chain = {
        "schema_version": "rule_version_chain_v1",
        "version_chain_id": "rule_chain_rule_021",
        "root_rule_id": "rule_021",
        "current_active_rule_id": "rule_027",
        "versions": [
            {"rule_id": "rule_021", "version_number": 1, "status": "inactive"},
            {"rule_id": "rule_027", "version_number": 2, "status": "active"},
        ],
        "chain_revision": 2,
        "created_at_utc": "2026-01-03T00:00:00Z",
        "updated_at_utc": "2026-01-03T00:00:00Z",
    }
    _write_json(root / "rule_supersession_chains" / "rule_chain_rule_021.json", chain)


def _dataset(root: Path, dataset_id: str = "historical_dataset_2025", *, count: int = 4, include_labels: bool = True, baseline: bool = False) -> None:
    records = []
    for index in range(count):
        matched_value = "controlled_value" if index % 2 == 0 else "different"
        record = {
            "record_id": f"record_{index:03d}",
            "timestamp_utc": f"2025-01-{index+1:02d}T00:00:00Z",
            "evaluation_context": {"controlled_field": matched_value},
        }
        if include_labels:
            record["observed_outcome"] = index in {0, 2}
        if baseline:
            record["baseline_prediction"] = index == 0
        records.append(record)
    payload = {
        "schema_version": "historical_rule_dataset_v1",
        "dataset_id": dataset_id,
        "outcome_label_field": "observed_outcome" if include_labels else None,
        "positive_outcome_value": True if include_labels else None,
        "baseline_field": "baseline_prediction" if baseline else None,
        "records": records,
    }
    _write_json(root / "historical_rule_datasets" / f"{dataset_id}.json", payload)


class RuleEffectivenessAnalysisTest(TestCase):
    def test_uncertified_rule_or_invalid_dataset_blocks_analysis(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _dataset(root)
            result = validate_rule_effectiveness_inputs("rule_027", "historical_dataset_2025", root=root)
        self.assertFalse(result["valid"])
        self.assertIn("canonical_rule_not_found", result["blockers"])

    def test_bounded_plan_is_deterministic_and_respects_hard_limit(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _certified_rule(root, "rule_027")
            _dataset(root, count=600)
            plan = build_rule_effectiveness_backtest_plan("rule_027", "historical_dataset_2025", max_records=999, root=root)
            plan_again = build_rule_effectiveness_backtest_plan("rule_027", "historical_dataset_2025", max_records=999, root=root)
        self.assertEqual(plan["record_count"], 500)
        self.assertEqual(plan["plan_fingerprint"], plan_again["plan_fingerprint"])

    def test_backtest_uses_canonical_single_rule_evaluator_without_mutation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _certified_rule(root, "rule_027")
            before = (root / "canonical_rules" / "rule_027.json").read_text(encoding="utf-8")
            _dataset(root)
            result = run_rule_effectiveness_backtest("rule_027", "historical_dataset_2025", root=root)
            after = (root / "canonical_rules" / "rule_027.json").read_text(encoding="utf-8")
        self.assertEqual(result["status"], "completed")
        self.assertFalse(result["persistent_state_mutated"])
        self.assertEqual(before, after)

    def test_core_coverage_and_reliability_metrics_are_correct(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _certified_rule(root, "rule_027")
            _dataset(root)
            result = run_rule_effectiveness_backtest("rule_027", "historical_dataset_2025", root=root)
        self.assertEqual(result["matched_count"], 2)
        self.assertEqual(result["not_matched_count"], 2)
        self.assertEqual(result["records_evaluated"], 4)
        self.assertEqual(result["match_coverage"], 0.5)
        self.assertEqual(result["evaluation_completion_rate"], 1.0)

    def test_outcome_metrics_require_explicit_valid_labels(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _certified_rule(root, "rule_027")
            _dataset(root, include_labels=False)
            result = run_rule_effectiveness_backtest("rule_027", "historical_dataset_2025", root=root)
        self.assertEqual(result["outcome_metrics"]["outcome_metrics_status"], "unavailable")
        self.assertEqual(result["outcome_metrics"]["reason"], "controlled_outcome_labels_missing")

    def test_version_comparison_uses_identical_ordered_records(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _certified_rule(root, "rule_027", value="controlled_value")
            _certified_rule(root, "rule_021", value="different")
            _chain(root)
            _dataset(root)
            result = run_rule_effectiveness_backtest("rule_027", "historical_dataset_2025", comparison_rule_id="rule_021", root=root)
        self.assertEqual(result["comparison"]["comparison_rule_id"], "rule_021")
        self.assertEqual(result["comparison"]["match_disagreement_count"], 4)

    def test_identical_analysis_is_idempotent_and_changed_dataset_is_stale(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _certified_rule(root, "rule_027")
            _dataset(root)
            first = run_rule_effectiveness_backtest("rule_027", "historical_dataset_2025", root=root)
            second = run_rule_effectiveness_backtest("rule_027", "historical_dataset_2025", root=root)
            payload = json.loads((root / "historical_rule_datasets" / "historical_dataset_2025.json").read_text(encoding="utf-8"))
            payload["records"].append({"record_id": "record_extra", "timestamp_utc": "2025-02-01T00:00:00Z", "evaluation_context": {"controlled_field": "controlled_value"}, "observed_outcome": True})
            _write_json(root / "historical_rule_datasets" / "historical_dataset_2025.json", payload)
            workspace = build_rule_effectiveness_workspace("rule_027", "historical_dataset_2025", root=root)
            report = format_rule_effectiveness_report(analysis_id=first["analysis_id"], public_safe=True, root=root)
        self.assertEqual(second["status"], "already_analyzed")
        self.assertEqual(workspace["analysis_status"], "completed")
        self.assertFalse(workspace["analysis_current"])
        self.assertEqual(workspace["analysis_freshness_status"], "stale")
        self.assertIn("Analysis Freshness: stale", report)

    def test_api_effectiveness_flow_and_public_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _certified_rule(root, "rule_027")
            _certified_rule(root, "rule_021", value="different")
            _chain(root)
            _dataset(root, baseline=True)
            workspace = build_rule_effectiveness_workspace("rule_027", "historical_dataset_2025", comparison_rule_id="rule_021", root=root)
            result = run_rule_effectiveness_backtest("rule_027", "historical_dataset_2025", comparison_rule_id="rule_021", root=root)
            report = format_rule_effectiveness_report(analysis_id=result["analysis_id"], public_safe=True, root=root)
            self.assertEqual(workspace["rule_certification_status"], "completed")
            self.assertTrue((root / "rule_effectiveness_analyses" / f"{result['analysis_id']}.json").exists())
            self.assertTrue((root / "rule_effectiveness_receipts" / f"{result['effectiveness_receipt_id']}.json").exists())
            self.assertIn("Certified Rule Effectiveness Report", report)
            self.assertNotIn(str(root), report)
            self.assertNotIn("evaluation_context", report)

    def test_health_detects_rule_drift_and_receipt_divergence(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _certified_rule(root, "rule_027")
            _dataset(root)
            result = run_rule_effectiveness_backtest("rule_027", "historical_dataset_2025", root=root)
            health_before = get_rule_effectiveness_health(rule_id="rule_027", dataset_id="historical_dataset_2025", root=root)
            rule_path = root / "canonical_rules" / "rule_027.json"
            rule_payload = json.loads(rule_path.read_text(encoding="utf-8"))
            rule_payload["value"] = "changed_value"
            rule_payload["condition"]["value"] = "changed_value"
            rule_payload["rule_fingerprint"] = None
            rule_path.write_text(json.dumps(rule_payload, indent=2), encoding="utf-8")
            receipt_path = root / "rule_effectiveness_receipts" / f"{result['effectiveness_receipt_id']}.json"
            receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt_payload["rule_fingerprint"] = "sha256:diverged"
            receipt_path.write_text(json.dumps(receipt_payload, indent=2), encoding="utf-8")
            health_after = get_rule_effectiveness_health(rule_id="rule_027", dataset_id="historical_dataset_2025", root=root)
        self.assertEqual(health_before["status"], "healthy")
        self.assertEqual(health_after["status"], "corrupt")
        self.assertEqual(health_after["stale_analysis_count"], 1)
        self.assertEqual(health_after["current_analysis_count"], 0)
