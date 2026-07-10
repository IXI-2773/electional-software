from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from backend.electional import certified_rule_objective_preview as objective_preview
from backend.electional import certified_rule_scoring_preview as scoring_preview
from backend.electional.api import (
    build_certified_rule_scoring_preview_plan as api_build_plan,
    build_certified_rule_scoring_preview_workspace as api_workspace,
    format_certified_rule_scoring_preview_report as api_report,
    run_certified_rule_scoring_preview as api_run,
    validate_certified_rule_scoring_preview_eligibility as api_validate,
)
from backend.electional.objective_outcome_scoring import save_objective_outcome_scoring_config
from backend.tests.test_certified_rule_objective_preview import _mapping, _scoring_config, _setup_dataset, _setup_pack, _setup_rule


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _build_phase_9o_result(root: Path) -> dict:
    _setup_rule(root)
    pack = _setup_pack(root)
    _setup_dataset(root)
    preview_plan = objective_preview.build_certified_rule_objective_preview_plan("rule_preview_1", "preview_pack", "preview_dataset", _mapping(), root=root)
    preview_run = objective_preview.run_certified_rule_objective_preview(preview_plan["objective_preview_plan_id"], confirmation="RUN_OBJECTIVE_PREVIEW", root=root)
    config = _scoring_config(pack)
    config["scoring_config_id"] = "phase_9p_score_config"
    saved = save_objective_outcome_scoring_config(config, confirmation="SAVE_SCORING_CONFIG", root=root)
    return {
        "pack": pack,
        "config": config,
        "preview_plan": preview_plan,
        "preview_run": preview_run,
        "saved_config": saved,
    }


class CertifiedRuleScoringPreviewTest(TestCase):
    def test_current_phase_9o_result_completes_read_only_scoring_preview(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _build_phase_9o_result(root)
            workspace = scoring_preview.build_certified_rule_scoring_preview_workspace(built["preview_run"]["objective_preview_result_id"], "phase_9p_score_config", root=root)
            eligibility = scoring_preview.validate_certified_rule_scoring_preview_eligibility(built["preview_run"]["objective_preview_result_id"], "phase_9p_score_config", root=root)
            plan = scoring_preview.build_certified_rule_scoring_preview_plan(built["preview_run"]["objective_preview_result_id"], "phase_9p_score_config", root=root)
            run = scoring_preview.run_certified_rule_scoring_preview(plan["scoring_preview_plan_id"], confirmation="RUN_SCORING_PREVIEW", root=root)
            rerun = scoring_preview.run_certified_rule_scoring_preview(plan["scoring_preview_plan_id"], confirmation="RUN_SCORING_PREVIEW", root=root)
            loaded = scoring_preview.load_certified_rule_scoring_preview_result(run["scoring_preview_result_id"], root=root)
        self.assertEqual(workspace["status"], "ready_for_planning")
        self.assertEqual(eligibility["compatibility_status"], "compatible")
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(run["status"], "completed")
        self.assertEqual(rerun["status"], "already_completed")
        self.assertEqual(rerun["writes_performed"], 0)
        result = loaded["scoring_preview_result"]
        self.assertEqual(result["preview_mode"], "shadow_read_only")
        self.assertEqual(result["metrics"]["increased_score_records"], 1)
        self.assertEqual(result["metrics"]["unchanged_score_records"], 1)
        self.assertEqual(result["metrics"]["mean_raw_score_delta"], 1.5)
        self.assertEqual(result["metrics"]["mean_bounded_score_delta"], 1.5)

    def test_legacy_stale_invalid_or_mutated_phase_9o_result_is_blocked(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _build_phase_9o_result(root)
            result_path = root / "certified_rule_objective_preview_results" / f"{objective_preview.analysis_backend._safe_id(built['preview_run']['objective_preview_result_id'])}.json"
            result_payload = json.loads(result_path.read_text(encoding="utf-8"))
            result_payload["objective_outcome_persistence"] = "legacy"
            _write_json(result_path, result_payload)
            legacy = scoring_preview.validate_certified_rule_scoring_preview_eligibility(built["preview_run"]["objective_preview_result_id"], "phase_9p_score_config", root=root)
            result_payload["objective_outcome_persistence"] = objective_preview.OBJECTIVE_OUTCOME_PERSISTENCE
            _write_json(result_path, result_payload)
            manifest_path = root / "document_manifests" / "pdf_bench.json"
            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_payload["source_revision"] = 99
            _write_json(manifest_path, manifest_payload)
            stale = scoring_preview.validate_certified_rule_scoring_preview_eligibility(built["preview_run"]["objective_preview_result_id"], "phase_9p_score_config", root=root)
        self.assertEqual(legacy["compatibility_status"], "legacy_objective_preview")
        self.assertIn("objective_outcome_persistence_incompatible", legacy["blockers"])
        self.assertEqual(stale["status"], "stale")
        self.assertIn("source_revision_not_current", stale["blockers"])

    def test_missing_or_incompatible_scoring_config_is_blocked(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _build_phase_9o_result(root)
            missing = scoring_preview.validate_certified_rule_scoring_preview_eligibility(built["preview_run"]["objective_preview_result_id"], "missing_config", root=root)
            config_path = root / "objective_outcome_scoring_configs" / "phase_9p_score_config.json"
            config_payload = json.loads(config_path.read_text(encoding="utf-8"))
            config_payload["objective_pack_id"] = "other_pack"
            config_payload["objective_pack_evaluation_fingerprint"] = "sha256:other"
            _write_json(config_path, config_payload)
            incompatible = scoring_preview.validate_certified_rule_scoring_preview_eligibility(built["preview_run"]["objective_preview_result_id"], "phase_9p_score_config", root=root)
        self.assertIn("scoring_config_missing", missing["blockers"])
        self.assertEqual(incompatible["compatibility_status"], "incompatible_pack")
        self.assertIn("objective_pack_id_mismatch", incompatible["blockers"])

    def test_baseline_and_rule_enabled_scoring_use_persisted_outcomes_directly(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _build_phase_9o_result(root)
            plan = scoring_preview.build_certified_rule_scoring_preview_plan(built["preview_run"]["objective_preview_result_id"], "phase_9p_score_config", root=root)
            with patch("backend.electional.certified_rule_scoring_preview.scoring_backend.evaluate_objective_outcomes", wraps=scoring_preview.scoring_backend.evaluate_objective_outcomes) as score_mock, patch("backend.electional.certified_rule_scoring_preview.objective_preview_backend.evaluate_objective_pack", side_effect=AssertionError("objective evaluation must not rerun")), patch("backend.electional.certified_rule_scoring_preview.objective_preview_backend.evaluate_canonical_rule", side_effect=AssertionError("rule evaluation must not rerun")):
                run = scoring_preview.run_certified_rule_scoring_preview(plan["scoring_preview_plan_id"], confirmation="RUN_SCORING_PREVIEW", root=root)
        self.assertEqual(run["status"], "completed")
        self.assertEqual(score_mock.call_count, 8)

    def test_score_comparisons_and_metrics_are_deterministic(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _build_phase_9o_result(root)
            plan = scoring_preview.build_certified_rule_scoring_preview_plan(built["preview_run"]["objective_preview_result_id"], "phase_9p_score_config", root=root)
            first = scoring_preview.run_certified_rule_scoring_preview(plan["scoring_preview_plan_id"], confirmation="RUN_SCORING_PREVIEW", root=root)
            loaded = scoring_preview.load_certified_rule_scoring_preview_result(first["scoring_preview_result_id"], root=root)
            result = loaded["scoring_preview_result"]
            first_record = result["per_record_scoring_comparisons"][0]
            second_record = result["per_record_scoring_comparisons"][1]
        self.assertEqual(first_record["record_classification"], "score_increased")
        self.assertEqual(first_record["raw_score_delta"], 3.0)
        self.assertEqual(second_record["record_classification"], "score_unchanged")
        self.assertEqual(result["metrics"]["minimum_raw_score_delta"], 0.0)
        self.assertEqual(result["metrics"]["maximum_raw_score_delta"], 3.0)

    def test_scoring_preview_does_not_mutate_upstream_or_production_state(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _build_phase_9o_result(root)
            plan = scoring_preview.build_certified_rule_scoring_preview_plan(built["preview_run"]["objective_preview_result_id"], "phase_9p_score_config", root=root)
            rule_before = (root / "canonical_rules" / "rule_preview_1.json").read_text(encoding="utf-8")
            pack_before = (root / "objective_packs" / "preview_pack.json").read_text(encoding="utf-8")
            preview_before = (root / "certified_rule_objective_preview_results" / f"{objective_preview.analysis_backend._safe_id(built['preview_run']['objective_preview_result_id'])}.json").read_text(encoding="utf-8")
            config_before = (root / "objective_outcome_scoring_configs" / "phase_9p_score_config.json").read_text(encoding="utf-8")
            scoring_preview.run_certified_rule_scoring_preview(plan["scoring_preview_plan_id"], confirmation="RUN_SCORING_PREVIEW", root=root)
            rule_after = (root / "canonical_rules" / "rule_preview_1.json").read_text(encoding="utf-8")
            pack_after = (root / "objective_packs" / "preview_pack.json").read_text(encoding="utf-8")
            preview_after = (root / "certified_rule_objective_preview_results" / f"{objective_preview.analysis_backend._safe_id(built['preview_run']['objective_preview_result_id'])}.json").read_text(encoding="utf-8")
            config_after = (root / "objective_outcome_scoring_configs" / "phase_9p_score_config.json").read_text(encoding="utf-8")
        self.assertEqual(rule_before, rule_after)
        self.assertEqual(pack_before, pack_after)
        self.assertEqual(preview_before, preview_after)
        self.assertEqual(config_before, config_after)

    def test_dependency_changes_make_preview_stale_and_rerun_is_idempotent(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _build_phase_9o_result(root)
            plan = scoring_preview.build_certified_rule_scoring_preview_plan(built["preview_run"]["objective_preview_result_id"], "phase_9p_score_config", root=root)
            first = scoring_preview.run_certified_rule_scoring_preview(plan["scoring_preview_plan_id"], confirmation="RUN_SCORING_PREVIEW", root=root)
            rerun = scoring_preview.run_certified_rule_scoring_preview(plan["scoring_preview_plan_id"], confirmation="RUN_SCORING_PREVIEW", root=root)
            config_path = root / "objective_outcome_scoring_configs" / "phase_9p_score_config.json"
            config_payload = json.loads(config_path.read_text(encoding="utf-8"))
            config_payload["entries"][0]["score_when_satisfied"] = 5.0
            config_payload["scoring_config_fingerprint"] = scoring_preview.scoring_backend.get_objective_outcome_scoring_config_fingerprint(config_payload)
            _write_json(config_path, config_payload)
            health = scoring_preview.get_certified_rule_scoring_preview_health(plan["scoring_preview_plan_id"], root=root)
            stale_run = scoring_preview.run_certified_rule_scoring_preview(plan["scoring_preview_plan_id"], confirmation="RUN_SCORING_PREVIEW", root=root)
        self.assertEqual(first["status"], "completed")
        self.assertEqual(rerun["status"], "already_completed")
        self.assertEqual(health["status"], "stale")
        self.assertEqual(stale_run["status"], "stale")

    def test_api_flow_receipt_health_summary_and_public_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            built = _build_phase_9o_result(root)
            workspace = api_workspace(built["preview_run"]["objective_preview_result_id"], "phase_9p_score_config", root=root)
            eligibility = api_validate(built["preview_run"]["objective_preview_result_id"], "phase_9p_score_config", root=root)
            plan = api_build_plan(built["preview_run"]["objective_preview_result_id"], "phase_9p_score_config", root=root)
            run = api_run(plan["scoring_preview_plan_id"], confirmation="RUN_SCORING_PREVIEW", root=root)
            health = scoring_preview.get_certified_rule_scoring_preview_health(plan["scoring_preview_plan_id"], root=root)
            summary = scoring_preview.get_certified_rule_scoring_preview_summary(plan["scoring_preview_plan_id"], root=root)
            report = api_report(scoring_preview_result_id=run["scoring_preview_result_id"], scoring_preview_receipt_id=run["scoring_preview_receipt_id"], public_safe=True, root=root)
        self.assertEqual(workspace["status"], "ready_for_planning")
        self.assertEqual(eligibility["compatibility_status"], "compatible")
        self.assertEqual(run["status"], "completed")
        self.assertEqual(health["status"], "healthy")
        self.assertEqual(summary["status"], "completed")
        self.assertIn("Certified Rule Scoring Preview", report)
        self.assertIn("shadow/read-only", report)
        self.assertNotIn(str(root), report)
