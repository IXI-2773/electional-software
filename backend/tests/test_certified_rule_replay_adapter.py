from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from backend.electional import certified_rule_replay_adapter as replay
from backend.electional.api import (
    build_certified_rule_replay_plan as api_build_plan,
    build_certified_rule_replay_workspace as api_workspace,
    format_certified_rule_replay_report as api_report,
    run_certified_rule_replay as api_run,
    validate_certified_rule_replay_eligibility as api_eligibility,
)
from backend.electional.canonical_rule_runtime import create_canonical_rule


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _setup_rule(root: Path, *, rule_id: str = "rule_replay_1", revision: int = 3) -> dict:
    document_id = "pdf_bench"
    _write_json(
        root / "document_manifests" / f"{document_id}.json",
        {
            "schema_version": "document_manifest_v1",
            "manifest_id": f"manifest_{document_id}",
            "document_id": document_id,
            "source_revision": revision,
            "source_hash": f"sha256:{document_id}_rev{revision}",
            "pipeline_fingerprint": f"sha256:manifest_{document_id}_{revision}",
            "backend_readiness": {"status": "ready"},
            "pipeline": {"preflight": "ready"},
            "warnings": [],
            "blockers": [],
        },
    )
    rule = {
        "rule_id": rule_id,
        "rule_type": "electional_constraint",
        "target": "target_a",
        "scope": "scope_a",
        "condition": {"field": "signal_value", "operator": "equals", "value": "GO"},
        "operator": "equals",
        "value": "GO",
        "priority": 100,
        "enabled": True,
        "status": "active",
        "document_id": document_id,
        "source_proposal_id": "proposal_1",
        "source_revision": revision,
    }
    created = create_canonical_rule(rule, confirmation="CREATE_RULE", root=root)
    assert created["status"] in {"created", "already_created"}
    rule_path = root / "canonical_rules" / f"{rule_id}.json"
    stored = json.loads(rule_path.read_text(encoding="utf-8"))
    _write_json(
        root / "rule_activation_certification_receipts" / f"cert_{rule_id}.json",
        {
            "schema_version": "rule_activation_certification_receipt_v1",
            "certification_receipt_id": f"cert_{rule_id}",
            "revalidation_id": f"reval_{rule_id}",
            "rule_id": rule_id,
            "proposal_id": "proposal_1",
            "document_id": document_id,
            "source_revision": revision,
            "rule_hash": replay._hash_payload(stored),
            "certification_status": "completed",
        },
    )
    return stored


def _setup_dataset(root: Path, dataset_id: str = "dataset_1") -> dict:
    dataset = {
        "schema_version": "historical_rule_dataset_v1",
        "dataset_id": dataset_id,
        "source_description": "controlled replay fixture",
        "start_timestamp": "2020-01-01T00:00:00Z",
        "end_timestamp": "2020-01-03T00:00:00Z",
        "record_count": 3,
        "records": [
            {"dataset_id": dataset_id, "record_id": "r1", "timestamp": "2020-01-01T00:00:00Z", "evaluation_context": {"signal_value": "GO"}},
            {"dataset_id": dataset_id, "record_id": "r2", "timestamp": "2020-01-02T00:00:00Z", "evaluation_context": {"signal_value": "STOP"}},
            {"dataset_id": dataset_id, "record_id": "r3", "timestamp": "2020-01-03T00:00:00Z", "evaluation_context": {"other": "missing"}},
        ],
    }
    dataset["dataset_fingerprint"] = replay._dataset_fingerprint(dataset)
    _write_json(root / "historical_rule_datasets" / f"{dataset_id}.json", dataset)
    return dataset


class CertifiedRuleReplayAdapterTest(TestCase):
    def test_active_certified_rule_runs_bounded_shadow_replay(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _setup_rule(root)
            _setup_dataset(root)
            plan = replay.build_certified_rule_replay_plan("rule_replay_1", "dataset_1", root=root)
            result = replay.run_certified_rule_replay(plan["replay_plan_id"], confirmation="RUN_REPLAY", root=root)
            loaded = replay.load_certified_rule_replay_result(result["replay_result_id"], root=root)
        self.assertEqual(result["status"], "completed_with_unsupported_records")
        self.assertEqual(loaded["replay_result"]["metrics"]["match_count"], 1)

    def test_uncertified_inactive_or_stale_rule_is_blocked(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _setup_rule(root, rule_id="rule_blocked")
            _setup_dataset(root)
            (root / "rule_activation_certification_receipts" / "cert_rule_blocked.json").unlink()
            blocked = replay.validate_certified_rule_replay_eligibility("rule_blocked", dataset_id="dataset_1", root=root)
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("rule_certification_missing", blocked["blockers"])

    def test_foreign_document_or_revision_provenance_is_blocked(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _setup_rule(root, revision=5)
            _setup_dataset(root)
            _write_json(
                root / "document_manifests" / "pdf_bench.json",
                {
                    "schema_version": "document_manifest_v1",
                    "manifest_id": "manifest_pdf_bench",
                    "document_id": "pdf_bench",
                    "source_revision": 6,
                    "source_hash": "sha256:pdf_bench_rev6",
                    "pipeline_fingerprint": "sha256:manifest_pdf_bench_6",
                    "backend_readiness": {"status": "ready"},
                    "pipeline": {"preflight": "ready"},
                    "warnings": [],
                    "blockers": [],
                },
            )
            blocked = replay.validate_certified_rule_replay_eligibility("rule_replay_1", dataset_id="dataset_1", root=root)
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("source_revision_not_current", blocked["blockers"])

    def test_dataset_limits_ordering_and_fingerprint_are_enforced(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _setup_rule(root)
            dataset = _setup_dataset(root, "dataset_bad")
            dataset["records"][1]["timestamp"] = "2019-01-01T00:00:00Z"
            _write_json(root / "historical_rule_datasets" / "dataset_bad.json", dataset)
            blocked = replay.validate_certified_rule_replay_eligibility("rule_replay_1", dataset_id="dataset_bad", root=root)
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("dataset_record_order_invalid", blocked["blockers"])

    def test_adapter_preserves_record_identity_and_does_not_infer_missing_values(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            rule = _setup_rule(root)
            _setup_dataset(root)
            adapted = replay._adapt_and_evaluate_record(rule, {"record_id": "x1", "timestamp": "2020-01-05T00:00:00Z", "evaluation_context": {"other": "none"}}, root)
        self.assertEqual(adapted["record_id"], "x1")
        self.assertEqual(adapted["classification"], "unsupported_missing_field")

    def test_replay_uses_canonical_evaluator_without_mutating_production_state(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _setup_rule(root)
            dataset = _setup_dataset(root)
            rule_before = (root / "canonical_rules" / "rule_replay_1.json").read_text(encoding="utf-8")
            dataset_before = json.dumps(dataset, sort_keys=True)
            with patch("backend.electional.certified_rule_replay_adapter.run_historical_replay") as foundation:
                foundation.return_value = {"run_id": "foundation_run_1"}
                plan = replay.build_certified_rule_replay_plan("rule_replay_1", "dataset_1", root=root)
                replay.run_certified_rule_replay(plan["replay_plan_id"], confirmation="RUN_REPLAY", root=root)
            rule_after = (root / "canonical_rules" / "rule_replay_1.json").read_text(encoding="utf-8")
            dataset_after = (root / "historical_rule_datasets" / "dataset_1.json").read_text(encoding="utf-8")
        self.assertTrue(foundation.called)
        self.assertEqual(rule_before, rule_after)
        self.assertEqual(dataset_before, json.dumps(json.loads(dataset_after), sort_keys=True))

    def test_changed_rule_dataset_or_evaluator_makes_result_stale_and_rerun_is_idempotent(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _setup_rule(root)
            dataset = _setup_dataset(root)
            plan = replay.build_certified_rule_replay_plan("rule_replay_1", "dataset_1", root=root)
            first = replay.run_certified_rule_replay(plan["replay_plan_id"], confirmation="RUN_REPLAY", root=root)
            second = replay.run_certified_rule_replay(plan["replay_plan_id"], confirmation="RUN_REPLAY", root=root)
            dataset["records"].append({"dataset_id": "dataset_1", "record_id": "r4", "timestamp": "2020-01-04T00:00:00Z", "evaluation_context": {"signal_value": "GO"}})
            dataset["record_count"] = 4
            dataset["end_timestamp"] = "2020-01-04T00:00:00Z"
            dataset["dataset_fingerprint"] = replay._dataset_fingerprint(dataset)
            _write_json(root / "historical_rule_datasets" / "dataset_1.json", dataset)
            health = replay.get_certified_rule_replay_health(plan["replay_plan_id"], root=root)
        self.assertEqual(second["status"], "already_completed")
        self.assertEqual(health["status"], "stale")

    def test_api_flow_receipt_health_and_public_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _setup_rule(root)
            _setup_dataset(root)
            workspace = api_workspace("rule_replay_1", "dataset_1", root=root)
            eligibility = api_eligibility("rule_replay_1", dataset_id="dataset_1", root=root)
            plan = api_build_plan("rule_replay_1", "dataset_1", root=root)
            result = api_run(plan["replay_plan_id"], confirmation="RUN_REPLAY", root=root)
            health = replay.get_certified_rule_replay_health(plan["replay_plan_id"], root=root)
            report = api_report(replay_result_id=result["replay_result_id"], public_safe=True, root=root)
        self.assertEqual(workspace["document_id"], "pdf_bench")
        self.assertEqual(eligibility["status"], "eligible")
        self.assertIn(result["status"], {"completed", "completed_with_unsupported_records"})
        self.assertEqual(health["status"], "healthy")
        self.assertIn("shadow_read_only", report)
        self.assertNotIn(str(root), report)
