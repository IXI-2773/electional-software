from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import certified_rule_objective_preview as preview
from backend.electional.api import (
    build_certified_rule_objective_preview_plan as api_build_plan,
    build_certified_rule_objective_preview_workspace as api_workspace,
    format_certified_rule_objective_preview_report as api_report,
    run_certified_rule_objective_preview as api_run,
    validate_certified_rule_objective_preview_eligibility as api_eligibility,
)
from backend.electional.canonical_rule_runtime import create_canonical_rule
from backend.electional.objective_outcome_scoring import evaluate_objective_outcomes
from backend.electional.objective_packs import get_objective_pack_evaluation_fingerprint
from backend.electional.objective_packs import save_objective_pack


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _setup_rule(root: Path, *, rule_id: str = "rule_preview_1", revision: int = 3) -> dict:
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
            "rule_hash": preview._hash_payload(stored),
            "certification_status": "completed",
        },
    )
    return stored


def _setup_pack(root: Path, objective_type: str = "preview_pack") -> dict:
    pack = {
        "objective_type": objective_type,
        "version": 1,
        "matter_houses": [1, 10],
        "natural_significators": ["Moon"],
        "action_moment": "Example",
        "objectives": [
            {"objective_id": "eligible_action", "input_field": "eligible_action", "value_type": "boolean", "operator": "equals", "expected_value": True, "success_semantics": "condition_met"},
            {"objective_id": "signal_is_go", "input_field": "signal_value", "value_type": "string", "operator": "equals", "expected_value": "GO", "success_semantics": "condition_met"},
        ],
    }
    save_objective_pack(pack, root=root / "objective_packs")
    return pack


def _setup_dataset(root: Path, dataset_id: str = "preview_dataset") -> dict:
    dataset = {
        "schema_version": "historical_rule_dataset_v1",
        "dataset_id": dataset_id,
        "source_description": "controlled objective preview fixture",
        "start_timestamp": "2020-01-01T00:00:00Z",
        "end_timestamp": "2020-01-02T00:00:00Z",
        "record_count": 2,
        "records": [
            {"dataset_id": dataset_id, "record_id": "r1", "timestamp": "2020-01-01T00:00:00Z", "evaluation_context": {"signal_value": "GO", "eligible_action": False}},
            {"dataset_id": dataset_id, "record_id": "r2", "timestamp": "2020-01-02T00:00:00Z", "evaluation_context": {"signal_value": "STOP", "eligible_action": False}},
        ],
    }
    dataset["dataset_fingerprint"] = preview._dataset_fingerprint(dataset)
    _write_json(root / "historical_rule_datasets" / f"{dataset_id}.json", dataset)
    return dataset


def _mapping() -> dict:
    return {
        "mapping_version": "rule_effect_mapping_v1",
        "on_match": {"values": {"eligible_action": True}},
        "on_no_match": {"mode": "preserve_baseline"},
    }


def _scoring_config(pack: dict) -> dict:
    return {
        "schema_version": "objective_outcome_scoring_config_v1",
        "scoring_config_id": "preview_score_config",
        "objective_pack_id": pack["objective_type"],
        "objective_pack_evaluation_fingerprint": get_objective_pack_evaluation_fingerprint(pack),
        "score_direction": "higher_is_better",
        "unmapped_objective_behavior": "ignore",
        "entries": [
            {"objective_id": "eligible_action", "score_when_satisfied": 2.0, "score_when_unsatisfied": -1.0, "missing_behavior": "error", "unsupported_behavior": "error"},
            {"objective_id": "signal_is_go", "score_when_satisfied": 1.0, "score_when_unsatisfied": 0.0, "missing_behavior": "error", "unsupported_behavior": "error"},
        ],
    }


class CertifiedRuleObjectivePreviewTest(TestCase):
    def test_preview_persists_baseline_and_rule_enabled_outcomes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _setup_rule(root)
            pack = _setup_pack(root)
            _setup_dataset(root)
            plan = preview.build_certified_rule_objective_preview_plan("rule_preview_1", "preview_pack", "preview_dataset", _mapping(), root=root)
            result = preview.run_certified_rule_objective_preview(plan["objective_preview_plan_id"], confirmation="RUN_OBJECTIVE_PREVIEW", root=root)
            loaded = preview.load_certified_rule_objective_preview_result(result["objective_preview_result_id"], root=root)
        self.assertEqual(result["status"], "completed")
        record = loaded["objective_preview_result"]["per_record_results"][0]
        self.assertEqual(loaded["objective_preview_result"]["objective_outcome_persistence"], "baseline_and_rule_enabled_v1")
        self.assertIsInstance(record["baseline_objective_outcomes"], dict)
        self.assertIsInstance(record["rule_enabled_objective_outcomes"], dict)
        self.assertEqual(loaded["objective_preview_result"]["metrics"]["improved_records"], 1)
        self.assertEqual(loaded["objective_preview_result"]["metrics"]["worsened_records"], 0)
        baseline_score = evaluate_objective_outcomes(_scoring_config(pack), record["baseline_objective_outcomes"])
        preview_score = evaluate_objective_outcomes(_scoring_config(pack), record["rule_enabled_objective_outcomes"])
        self.assertEqual(baseline_score["aggregate_status"], "completed")
        self.assertEqual(preview_score["aggregate_status"], "completed")

    def test_persisted_outcomes_preserve_record_pack_and_objective_order(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _setup_rule(root)
            _setup_pack(root)
            _setup_dataset(root)
            plan = preview.build_certified_rule_objective_preview_plan("rule_preview_1", "preview_pack", "preview_dataset", _mapping(), root=root)
            result = preview.run_certified_rule_objective_preview(plan["objective_preview_plan_id"], confirmation="RUN_OBJECTIVE_PREVIEW", root=root)
            loaded = preview.load_certified_rule_objective_preview_result(result["objective_preview_result_id"], root=root)
        records = loaded["objective_preview_result"]["per_record_results"]
        first = records[0]
        baseline_ids = [item["objective_id"] for item in first["baseline_objective_outcomes"]["objective_results"]]
        preview_ids = [item["objective_id"] for item in first["rule_enabled_objective_outcomes"]["objective_results"]]
        self.assertEqual(first["record_id"], first["baseline_objective_outcomes"]["record_id"])
        self.assertEqual(first["record_id"], first["rule_enabled_objective_outcomes"]["record_id"])
        self.assertEqual(first["baseline_objective_outcomes"]["objective_pack_id"], "preview_pack")
        self.assertEqual(first["rule_enabled_objective_outcomes"]["objective_pack_id"], "preview_pack")
        self.assertEqual(baseline_ids, ["eligible_action", "signal_is_go"])
        self.assertEqual(preview_ids, ["eligible_action", "signal_is_go"])

    def test_existing_objective_comparison_classifications_remain_unchanged(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _setup_rule(root)
            _setup_pack(root)
            _setup_dataset(root)
            plan = preview.build_certified_rule_objective_preview_plan("rule_preview_1", "preview_pack", "preview_dataset", _mapping(), root=root)
            result = preview.run_certified_rule_objective_preview(plan["objective_preview_plan_id"], confirmation="RUN_OBJECTIVE_PREVIEW", root=root)
            loaded = preview.load_certified_rule_objective_preview_result(result["objective_preview_result_id"], root=root)
        first, second = loaded["objective_preview_result"]["per_record_results"]
        self.assertEqual(first["classification"], "objective_improved")
        self.assertEqual(first["record_classification"], "objective_improved")
        self.assertEqual(second["classification"], "unchanged")
        self.assertEqual(first["objective_comparisons"][0]["comparison"], "newly_satisfied")

    def test_baseline_and_preview_use_independent_copies_and_do_not_mutate_state(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _setup_rule(root)
            _setup_pack(root)
            dataset = _setup_dataset(root)
            rule_before = (root / "canonical_rules" / "rule_preview_1.json").read_text(encoding="utf-8")
            pack_before = (root / "objective_packs" / "preview_pack.json").read_text(encoding="utf-8")
            dataset_before = json.dumps(dataset, sort_keys=True)
            plan = preview.build_certified_rule_objective_preview_plan("rule_preview_1", "preview_pack", "preview_dataset", _mapping(), root=root)
            preview.run_certified_rule_objective_preview(plan["objective_preview_plan_id"], confirmation="RUN_OBJECTIVE_PREVIEW", root=root)
            rule_after = (root / "canonical_rules" / "rule_preview_1.json").read_text(encoding="utf-8")
            pack_after = (root / "objective_packs" / "preview_pack.json").read_text(encoding="utf-8")
            dataset_after = (root / "historical_rule_datasets" / "preview_dataset.json").read_text(encoding="utf-8")
        self.assertEqual(rule_before, rule_after)
        self.assertEqual(pack_before, pack_after)
        self.assertEqual(dataset_before, json.dumps(json.loads(dataset_after), sort_keys=True))

    def test_result_and_receipt_fingerprints_cover_persisted_outcomes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _setup_rule(root)
            _setup_pack(root)
            _setup_dataset(root)
            plan = preview.build_certified_rule_objective_preview_plan("rule_preview_1", "preview_pack", "preview_dataset", _mapping(), root=root)
            result = preview.run_certified_rule_objective_preview(plan["objective_preview_plan_id"], confirmation="RUN_OBJECTIVE_PREVIEW", root=root)
            result_path = root / "certified_rule_objective_preview_results" / f"{preview.analysis_backend._safe_id(result['objective_preview_result_id'])}.json"
            receipt_path = root / "certified_rule_objective_preview_receipts" / f"{preview.analysis_backend._safe_id(result['objective_preview_receipt_id'])}.json"
            plan_path = root / "certified_rule_objective_preview_plans" / f"{preview.analysis_backend._safe_id(plan['objective_preview_plan_id'])}.json"
            result_payload = json.loads(result_path.read_text(encoding="utf-8"))
            receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8"))
            plan_payload = json.loads(plan_path.read_text(encoding="utf-8"))
            original_fingerprint = result_payload["result_fingerprint"]
            result_payload["per_record_results"][0]["baseline_objective_outcomes"]["objective_results"][0]["status"] = "satisfied"
            result_payload["per_record_results"][0]["baseline_objective_outcomes"]["objective_results"][0]["satisfied"] = True
            mutated = preview._result_fingerprint(
                {"plan_fingerprint": plan_payload["plan_fingerprint"]},
                result_payload["per_record_results"],
                result_payload["per_objective_comparisons"],
                result_payload["metrics"],
                result_payload["status"],
            )
        self.assertNotEqual(original_fingerprint, mutated)
        self.assertEqual(receipt_payload["result_fingerprint"], original_fingerprint)
        self.assertEqual(receipt_payload["baseline_outcome_payload_count"], 2)
        self.assertEqual(receipt_payload["rule_enabled_outcome_payload_count"], 2)

    def test_changed_rule_pack_input_mapping_or_evaluator_makes_results_stale_and_reruns_remain_idempotent(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _setup_rule(root)
            _setup_pack(root)
            _setup_dataset(root)
            plan = preview.build_certified_rule_objective_preview_plan("rule_preview_1", "preview_pack", "preview_dataset", _mapping(), root=root)
            first = preview.run_certified_rule_objective_preview(plan["objective_preview_plan_id"], confirmation="RUN_OBJECTIVE_PREVIEW", root=root)
            second = preview.run_certified_rule_objective_preview(plan["objective_preview_plan_id"], confirmation="RUN_OBJECTIVE_PREVIEW", root=root)
            changed = _mapping()
            changed["on_match"]["values"]["eligible_action"] = False
            plan_path = root / "certified_rule_objective_preview_plans" / f"{preview.analysis_backend._safe_id(plan['objective_preview_plan_id'])}.json"
            plan_payload = json.loads(plan_path.read_text(encoding="utf-8"))
            plan_payload["effect_mapping"] = changed
            plan_payload["effect_mapping_fingerprint"] = preview._effect_mapping_fingerprint(changed)
            _write_json(plan_path, plan_payload)
            health = preview.get_certified_rule_objective_preview_health(plan["objective_preview_plan_id"], root=root)
        self.assertEqual(second["status"], "already_completed")
        self.assertEqual(health["status"], "stale")

    def test_legacy_results_remain_readable_but_are_not_phase_9p_compatible(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            legacy_id = "legacy_result_1"
            _write_json(
                root / "certified_rule_objective_preview_results" / f"{legacy_id}.json",
                {
                    "schema_version": "certified_rule_objective_preview_result_v1",
                    "objective_preview_result_id": legacy_id,
                    "objective_preview_plan_id": "plan_1",
                    "document_id": "pdf_bench",
                    "source_revision": 3,
                    "objective_pack_id": "preview_pack",
                    "per_record_results": [{"record_id": "r1", "classification": "unchanged", "objective_comparisons": []}],
                    "per_objective_comparisons": [],
                    "metrics": {},
                    "status": "completed",
                    "result_fingerprint": "sha256:legacy",
                },
            )
            loaded = preview.load_certified_rule_objective_preview_result(legacy_id, root=root)
            health = preview.get_certified_rule_objective_preview_health(root=root)
            report = preview.format_certified_rule_objective_preview_report(objective_preview_result_id=legacy_id, root=root)
        self.assertEqual(loaded["status"], "loaded")
        self.assertFalse(loaded["objective_preview_result"]["phase_9p_compatible"])
        self.assertIn(health["status"], {"warning", "stale", "blocked"})
        self.assertIn("legacy_objective_preview_result", report)

    def test_api_flow_creates_result_and_receipt_health_works_and_public_report_is_safe(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _setup_rule(root)
            _setup_pack(root)
            _setup_dataset(root)
            workspace = api_workspace("rule_preview_1", "preview_pack", "preview_dataset", root=root)
            eligibility = api_eligibility("rule_preview_1", "preview_pack", controlled_input_id="preview_dataset", effect_mapping=_mapping(), root=root)
            plan = api_build_plan("rule_preview_1", "preview_pack", "preview_dataset", _mapping(), root=root)
            result = api_run(plan["objective_preview_plan_id"], confirmation="RUN_OBJECTIVE_PREVIEW", root=root)
            health = preview.get_certified_rule_objective_preview_health(plan["objective_preview_plan_id"], root=root)
            report = api_report(objective_preview_result_id=result["objective_preview_result_id"], public_safe=True, root=root)
        self.assertEqual(workspace["document_id"], "pdf_bench")
        self.assertEqual(eligibility["status"], "eligible")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(health["status"], "healthy")
        self.assertIn("shadow_read_only", report)
        self.assertNotIn(str(root), report)
        self.assertIn("Phase 9P Compatibility: compatible", report)
