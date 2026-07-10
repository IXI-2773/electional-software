from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from backend.electional.api import (
    build_rule_batch_plan as api_build_plan,
    build_rule_batch_workspace as api_build_workspace,
    format_rule_batch_report as api_format_report,
    run_rule_batch_analysis as api_run_batch,
)
from backend.electional.canonical_rule_runtime import create_canonical_rule
from backend.electional.rule_batch_analysis import (
    build_rule_batch_plan,
    build_rule_batch_workspace,
    format_rule_batch_report,
    get_rule_batch_health,
    get_rule_batch_summary,
    run_rule_batch_analysis,
)
from backend.electional.rule_effectiveness_analysis import (
    build_rule_effectiveness_workspace,
    run_rule_effectiveness_backtest as run_rule_effectiveness_analysis,
)
from backend.tests.test_rule_effectiveness_analysis import _dataset, _write_json


def _source_record(root: Path, document_id: str, sha256: str) -> None:
    _write_json(
        root / "indexes" / f"{document_id}.json",
        {
            "document_id": document_id,
            "original_filename": f"{document_id}.pdf",
            "source_path": f"C:\\private\\{document_id}.pdf",
            "stored_pdf_path": None,
            "sha256": sha256,
            "size_bytes": 100,
            "page_count": 2,
            "privacy_level": "private_local",
            "extraction_status": "extracted",
            "extracted_text_path": None,
            "extracted_char_count": 10,
            "warnings": [],
            "created_at_utc": "2026-01-01T00:00:00Z",
            "updated_at_utc": "2026-01-01T00:00:00Z",
        },
    )


def _manifest(root: Path, document_id: str, source_revision: int, sha256: str, fingerprint: str | None = None) -> None:
    _write_json(
        root / "document_manifests" / f"{document_id}.json",
        {
            "schema_version": "document_manifest_v1",
            "manifest_id": f"manifest_{document_id}",
            "document_id": document_id,
            "source_revision": source_revision,
            "source_hash": sha256,
            "previous_source_hash": None,
            "revision_changed": False,
            "lifecycle_status": "ready",
            "pipeline_fingerprint": fingerprint or f"sha256:{document_id}_{source_revision}",
            "backend_readiness": {"status": "ready"},
            "warnings": [],
            "blockers": [],
            "created_at_utc": "2026-01-01T00:00:00Z",
            "updated_at_utc": "2026-01-01T00:00:00Z",
        },
    )


def _certified_rule(root: Path, rule_id: str, *, document_id: str, source_revision: int, target: str = "controlled_target_x") -> None:
    payload = {
        "schema_version": "canonical_mutable_rule_v1",
        "rule_id": rule_id,
        "rule_type": "electional_constraint",
        "target": target,
        "scope": "documented_scope",
        "condition": {"field": "controlled_field", "operator": "equals", "value": "controlled_value"},
        "operator": "equals",
        "value": "controlled_value",
        "priority": 50,
        "enabled": True,
        "status": "active",
        "document_id": document_id,
        "source_proposal_id": f"proposal_{rule_id}",
        "source_promotion_receipt_id": f"promotion_{rule_id}",
        "source_rule_activation_review_id": f"review_{rule_id}",
        "source_revision": source_revision,
    }
    create_canonical_rule(payload, confirmation="CREATE_RULE", root=root)
    current = json.loads((root / "canonical_rules" / f"{rule_id}.json").read_text(encoding="utf-8"))
    _write_json(
        root / "rule_activation_certification_receipts" / f"rule_certification_receipt_{rule_id}.json",
        {
            "schema_version": "rule_activation_certification_receipt_v1",
            "certification_receipt_id": f"rule_certification_receipt_{rule_id}",
            "revalidation_id": f"impact_{rule_id}",
            "rule_id": rule_id,
            "rule_hash": "sha256:" + __import__("hashlib").sha256(json.dumps(current, sort_keys=True, default=str).encode("utf-8")).hexdigest(),
            "certification_status": "completed",
            "created_at_utc": "2026-01-02T00:00:00Z",
        },
    )


def _fixture_store(root: Path) -> None:
    _source_record(root, "pdf_a", "sha256:pdf_a_rev1")
    _manifest(root, "pdf_a", 1, "sha256:pdf_a_rev1", "sha256:manifest_pdf_a_rev1")
    _source_record(root, "pdf_b", "sha256:pdf_b_rev1")
    _manifest(root, "pdf_b", 1, "sha256:pdf_b_rev1", "sha256:manifest_pdf_b_rev1")
    _certified_rule(root, "rule_a_001", document_id="pdf_a", source_revision=1, target="target_a")
    _certified_rule(root, "rule_a_002", document_id="pdf_a", source_revision=1, target="target_b")
    _certified_rule(root, "rule_a_rev2", document_id="pdf_a", source_revision=2, target="target_c")
    _certified_rule(root, "rule_b_001", document_id="pdf_b", source_revision=1, target="target_d")
    _dataset(root, count=80, include_labels=False)


class RuleBatchAnalysisTest(TestCase):
    def test_workspace_discovers_only_rules_from_requested_pdf_revision(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _fixture_store(root)
            workspace = build_rule_batch_workspace("pdf_a", 1, "historical_dataset_2025", include_document_certified_rules=True, root=root)
        self.assertEqual(workspace["document_status"], "current")
        self.assertEqual(workspace["revision_lock_status"], "valid")
        self.assertEqual([item["rule_id"] for item in workspace["items"]], ["rule_a_001", "rule_a_002"])
        self.assertEqual(workspace["foreign_document_rule_count"], 0)
        self.assertEqual(workspace["foreign_revision_rule_count"], 0)

    def test_explicit_mixed_document_rule_ids_block_plan_creation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _fixture_store(root)
            plan = build_rule_batch_plan("pdf_a", 1, "historical_dataset_2025", rule_ids=["rule_a_001", "rule_b_001"], include_document_certified_rules=False, root=root)
            workspace = build_rule_batch_workspace("pdf_a", 1, "historical_dataset_2025", rule_ids=["rule_a_001", "rule_b_001"], include_document_certified_rules=False, root=root)
        self.assertIn("rule_batch_explicit_rule_scope_violation", plan["blockers"])
        classifications = {item["rule_id"]: item["classification"] for item in workspace["items"]}
        self.assertEqual(classifications["rule_b_001"], "foreign_document")

    def test_explicit_mixed_revision_rule_ids_block_plan_creation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _fixture_store(root)
            plan = build_rule_batch_plan("pdf_a", 1, "historical_dataset_2025", rule_ids=["rule_a_001", "rule_a_rev2"], include_document_certified_rules=False, root=root)
            workspace = build_rule_batch_workspace("pdf_a", 1, "historical_dataset_2025", rule_ids=["rule_a_001", "rule_a_rev2"], include_document_certified_rules=False, root=root)
        self.assertIn("rule_batch_explicit_rule_scope_violation", plan["blockers"])
        classifications = {item["rule_id"]: item["classification"] for item in workspace["items"]}
        self.assertEqual(classifications["rule_a_rev2"], "foreign_revision")

    def test_plan_fingerprint_includes_document_revision_and_provenance(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _fixture_store(root)
            plan_a = build_rule_batch_plan("pdf_a", 1, "historical_dataset_2025", rule_ids=["rule_a_001"], include_document_certified_rules=False, root=root)
            plan_b = build_rule_batch_plan("pdf_b", 1, "historical_dataset_2025", rule_ids=["rule_b_001"], include_document_certified_rules=False, root=root)
        self.assertNotEqual(plan_a["plan_fingerprint"], plan_b["plan_fingerprint"])
        self.assertEqual(plan_a["schema_version"], "rule_batch_plan_v2")
        self.assertEqual(plan_a["items"][0]["document_id"], "pdf_a")
        self.assertEqual(plan_a["items"][0]["source_revision"], 1)
        self.assertTrue(str(plan_a["items"][0]["provenance_fingerprint"]).startswith("sha256:"))

    def test_execution_stops_stale_when_document_revision_changes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _fixture_store(root)
            plan = build_rule_batch_plan("pdf_a", 1, "historical_dataset_2025", rule_ids=["rule_a_001", "rule_a_002"], include_document_certified_rules=False, root=root)
            paused = run_rule_batch_analysis(plan["batch_plan_id"], stop_after_items=1, root=root)
            _source_record(root, "pdf_a", "sha256:pdf_a_rev2")
            stale = run_rule_batch_analysis(plan["batch_plan_id"], root=root)
        self.assertEqual(paused["status"], "paused")
        self.assertEqual(stale["status"], "stale")
        self.assertIn("source_revision_no_longer_current", stale["blockers"])

    def test_resume_blocks_after_manifest_or_revision_change(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _fixture_store(root)
            plan = build_rule_batch_plan("pdf_a", 1, "historical_dataset_2025", rule_ids=["rule_a_001", "rule_a_002"], include_document_certified_rules=False, root=root)
            run_rule_batch_analysis(plan["batch_plan_id"], stop_after_items=1, root=root)
            _manifest(root, "pdf_a", 1, "sha256:pdf_a_rev1", "sha256:manifest_pdf_a_rev1_changed")
            stale = run_rule_batch_analysis(plan["batch_plan_id"], root=root)
        self.assertEqual(stale["status"], "stale")
        self.assertIn("document_manifest_fingerprint_changed", stale["blockers"])

    def test_legacy_unscoped_plan_is_blocked_without_automatic_migration(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _fixture_store(root)
            _write_json(
                root / "rule_batch_runs" / "rule_batch_plan_legacy.json",
                {
                    "schema_version": "rule_batch_plan_v1",
                    "batch_plan_id": "rule_batch_plan_legacy",
                    "dataset_id": "historical_dataset_2025",
                    "policy_id": "default_v1",
                    "items": [],
                    "warnings": [],
                    "blockers": [],
                },
            )
            result = run_rule_batch_analysis("rule_batch_plan_legacy", root=root)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("legacy_unscoped_batch_plan", result["blockers"])

    def test_api_single_pdf_batch_flow_receipt_health_and_public_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _fixture_store(root)
            workspace = api_build_workspace("pdf_a", 1, "historical_dataset_2025", rule_ids=["rule_a_001", "rule_a_002"], include_document_certified_rules=False, root=root)
            plan = api_build_plan("pdf_a", 1, "historical_dataset_2025", rule_ids=["rule_a_001", "rule_a_002"], include_document_certified_rules=False, root=root)
            run = api_run_batch(plan["batch_plan_id"], root=root)
            health = get_rule_batch_health(run["batch_run_id"], root=root)
            report = api_format_report(batch_run_id=run["batch_run_id"], public_safe=True, root=root)
            receipt_files = list((root / "rule_batch_receipts").glob("*.json"))
            self.assertEqual(workspace["document_id"], "pdf_a")
            self.assertEqual(workspace["source_revision"], 1)
            self.assertEqual(run["status"], "completed")
            self.assertEqual(len(receipt_files), 1)
            receipt = json.loads(receipt_files[0].read_text(encoding="utf-8"))
        self.assertEqual(receipt["document_id"], "pdf_a")
        self.assertEqual(receipt["source_revision"], 1)
        self.assertEqual(health["status"], "healthy")
        self.assertIn("Single-PDF Batch Rule Analysis Report", report)
        self.assertIn("Scope: One submitted PDF", report)
        self.assertNotIn(str(root), report)
        self.assertFalse((root / "rule_effectiveness_recommendation_reviews").exists() and list((root / "rule_effectiveness_recommendation_reviews").glob("*.json")))
        self.assertFalse((root / "rule_action_candidates").exists() and list((root / "rule_action_candidates").glob("*.json")))

    def test_batch_surfaces_stale_single_rule_analysis_before_recommendation_generation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _fixture_store(root)
            plan = build_rule_batch_plan("pdf_a", 1, "historical_dataset_2025", rule_ids=["rule_a_001"], include_document_certified_rules=False, root=root)
            build_rule_effectiveness_workspace("rule_a_001", "historical_dataset_2025", root=root)
            analysis_result = run_rule_effectiveness_analysis("rule_a_001", "historical_dataset_2025", root=root)
            with patch("backend.electional.rule_batch_analysis.analysis_backend.run_rule_effectiveness_backtest", return_value={"status": "already_analyzed", "analysis_id": analysis_result["analysis_id"], "effectiveness_receipt_id": analysis_result["effectiveness_receipt_id"], "writes_performed": 0}), patch("backend.electional.rule_batch_analysis.analysis_backend.build_rule_effectiveness_workspace", return_value={"analysis_id": analysis_result["analysis_id"], "analysis_current": False, "analysis_freshness_status": "stale", "warnings": [], "blockers": [], "recommended_action": "Regenerate the focused backtest against the current rule and dataset state."}), patch("backend.electional.rule_batch_analysis.recommendation_backend.generate_rule_effectiveness_recommendation", side_effect=AssertionError("recommendation should not run from stale analysis")):
                run = run_rule_batch_analysis(plan["batch_plan_id"], root=root)
            summary = get_rule_batch_summary(run["batch_run_id"], root=root)
            health = get_rule_batch_health(run["batch_run_id"], root=root)
            report = format_rule_batch_report(batch_run_id=run["batch_run_id"], public_safe=True, root=root)
        self.assertEqual(run["status"], "completed_with_failures")
        item = run["items"][0]
        self.assertEqual(item["status"], "skipped_stale")
        self.assertEqual(item["failure_classification"], "analysis_stale_before_recommendation")
        self.assertEqual(item["blockers"], ["effectiveness_analysis_stale"])
        self.assertEqual(run["stale_analysis_skip_count"], 1)
        self.assertEqual(run["other_stale_skip_count"], 0)
        self.assertEqual(summary["stale_analysis_skip_count"], 1)
        self.assertEqual(summary["other_stale_skip_count"], 0)
        self.assertEqual(health["stale_analysis_skip_count"], 1)
        self.assertEqual(health["other_stale_skip_count"], 0)
        self.assertIn("Stale Analysis Skips: 1", report)
        self.assertIn("Other Stale Skips: 0", report)
        self.assertIn("Top Stale Skip Reasons: analysis_stale_before_recommendation (1)", report)
