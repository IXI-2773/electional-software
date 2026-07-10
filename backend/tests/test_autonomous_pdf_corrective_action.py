from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from backend.electional import autonomous_pdf_benchmark as benchmark
from backend.electional import autonomous_pdf_corrective_action as corrective
from backend.electional import autonomous_pdf_remediation as remediation
from backend.electional.api import (
    build_autonomous_pdf_corrective_action_plan as api_plan,
    build_autonomous_pdf_corrective_action_workspace as api_workspace,
    execute_autonomous_pdf_corrective_action as api_execute,
    format_autonomous_pdf_corrective_action_report as api_report,
    verify_autonomous_pdf_corrective_action as api_verify,
)
from backend.tests.test_autonomous_pdf_benchmark import EXPECTED_CITATION_KEY, _benchmark_manifest, _proposal, AutonomousPdfBenchmarkTest
from backend.tests.test_autonomous_pdf_remediation import AutonomousPdfRemediationTest


class AutonomousPdfCorrectiveActionTest(TestCase):
    def _reviewed_case(self, root: Path, *, review_decision: str = "no_action", root_cause: str = "unresolved", benchmark_id: str = "bench_action") -> tuple[dict, dict]:
        helper = AutonomousPdfRemediationTest()
        result = helper._failing_result(root, benchmark_id)
        triaged = remediation.run_autonomous_pdf_remediation_triage(result["benchmark_result_id"], confirmation="TRIAGE", root=root)
        loaded = remediation.load_autonomous_pdf_remediation_plan(triaged["remediation_plan_id"], root=root)
        case = loaded["cases"][0]
        case_path = corrective._read_json(corrective._action_path(corrective._ensure_dirs(root), "missing"))  # no-op for import use
        del case_path
        case_file = corrective._ensure_dirs(root) / remediation.CASE_DIR / f"{corrective.analysis_backend._safe_id(case['remediation_case_id'])}.json"
        case_payload = json.loads(case_file.read_text(encoding="utf-8"))
        case_payload["root_cause_classification"] = root_cause
        case_file.write_text(json.dumps(case_payload, indent=2, sort_keys=True), encoding="utf-8")
        reviewed = remediation.review_autonomous_pdf_remediation_case(case["remediation_case_id"], review_decision, confirmation="REVIEW", root=root)
        return case_payload, triaged

    def test_reviewed_case_builds_one_deterministic_corrective_action(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            case, _triaged = self._reviewed_case(root, review_decision="no_action")
            first = corrective.build_autonomous_pdf_corrective_action_plan(case["remediation_case_id"], "close_no_action", root=root)
            second = corrective.build_autonomous_pdf_corrective_action_plan(case["remediation_case_id"], "close_no_action", root=root)
        self.assertEqual(first["status"], "planned")
        self.assertEqual(first["corrective_action_id"], second["corrective_action_id"])

    def test_unreviewed_deferred_or_rejected_case_cannot_execute(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            helper = AutonomousPdfRemediationTest()
            result = helper._failing_result(root, "bench_blocked")
            triaged = remediation.run_autonomous_pdf_remediation_triage(result["benchmark_result_id"], confirmation="TRIAGE", root=root)
            case = remediation.load_autonomous_pdf_remediation_plan(triaged["remediation_plan_id"], root=root)["cases"][0]
            blocked = corrective.build_autonomous_pdf_corrective_action_plan(case["remediation_case_id"], "close_no_action", root=root)
            reviewed_case, _ = self._reviewed_case(root, review_decision="reject", benchmark_id="bench_reject")
            rejected = corrective.build_autonomous_pdf_corrective_action_plan(reviewed_case["remediation_case_id"], "close_no_action", root=root)
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(rejected["status"], "blocked")

    def test_manifest_amendment_is_explicit_bounded_atomic_and_independent(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            case, _triaged = self._reviewed_case(root, review_decision="benchmark_manifest_review", root_cause="benchmark_manifest_defect", benchmark_id="bench_manifest")
            payload = {"operation": "add_expected_record", "collection": "rule_candidates", "record": {"citation_keys": [EXPECTED_CITATION_KEY], "target": "target_manifest", "scope": "scope_manifest", "condition": {"field": "controlled_field", "operator": "equals", "value": "value_manifest"}, "operator": "equals", "value": "value_manifest", "structured_rule_ready": True}}
            plan = corrective.build_autonomous_pdf_corrective_action_plan(case["remediation_case_id"], "apply_benchmark_manifest_amendment", payload, root=root)
            executed = corrective.execute_autonomous_pdf_corrective_action(plan["corrective_action_id"], confirmation="EXECUTE_ACTION", root=root)
            manifest = benchmark.validate_autonomous_pdf_benchmark_manifest("bench_manifest", root=root)["manifest"]
        self.assertEqual(executed["status"], "verification_required")
        self.assertEqual(manifest["benchmark_id"], "bench_manifest")
        self.assertEqual(manifest["document_id"], "pdf_bench")
        self.assertTrue(any(item.get("target") == "target_manifest" for item in (manifest.get("expected") or {}).get("rule_candidates", [])))

    def test_manifest_amendment_failure_restores_original_manifest(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            case, _triaged = self._reviewed_case(root, review_decision="benchmark_manifest_review", root_cause="benchmark_manifest_defect", benchmark_id="bench_manifest_fail")
            payload = {"operation": "add_expected_record", "collection": "rule_candidates", "record": {"citation_keys": [EXPECTED_CITATION_KEY], "target": "target_manifest", "scope": "scope_manifest", "condition": {"field": "controlled_field", "operator": "equals", "value": "value_manifest"}, "operator": "equals", "value": "value_manifest", "structured_rule_ready": True}}
            plan = corrective.build_autonomous_pdf_corrective_action_plan(case["remediation_case_id"], "apply_benchmark_manifest_amendment", payload, root=root)
            manifest_before = benchmark.validate_autonomous_pdf_benchmark_manifest("bench_manifest_fail", root=root)["manifest"]
            with patch("backend.electional.autonomous_pdf_corrective_action._write_manifest_with_validation", return_value="failed_rolled_back"):
                failed = corrective.execute_autonomous_pdf_corrective_action(plan["corrective_action_id"], confirmation="EXECUTE_ACTION", root=root)
            manifest_after = benchmark.validate_autonomous_pdf_benchmark_manifest("bench_manifest_fail", root=root)["manifest"]
        self.assertEqual(failed["status"], "failed_rolled_back")
        self.assertEqual(manifest_before["manifest_fingerprint"], manifest_after["manifest_fingerprint"])

    def test_phase_9j_and_9k_fix_packages_do_not_patch_source_code(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            case, _triaged = self._reviewed_case(root, review_decision="accept_for_targeted_fix", root_cause="phase_9j_pipeline_defect", benchmark_id="bench_fix_pkg")
            target_file = Path("backend/electional/autonomous_pdf_benchmark.py")
            before = target_file.read_text(encoding="utf-8")
            plan = corrective.build_autonomous_pdf_corrective_action_plan(case["remediation_case_id"], "create_phase_9j_fix_package", {"summary": "Investigate bounded stage mismatch."}, root=root)
            executed = corrective.execute_autonomous_pdf_corrective_action(plan["corrective_action_id"], confirmation="EXECUTE_ACTION", root=root)
            after = target_file.read_text(encoding="utf-8")
            loaded = corrective.load_autonomous_pdf_corrective_action(plan["corrective_action_id"], root=root)["corrective_action"]
        self.assertEqual(executed["status"], "verification_required")
        self.assertEqual(before, after)
        self.assertIn("developer_fix_package", loaded)

    def test_foreign_document_revision_or_stale_fingerprint_blocks_action(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            case, _triaged = self._reviewed_case(root, review_decision="benchmark_manifest_review", root_cause="benchmark_manifest_defect", benchmark_id="bench_stale")
            payload = {"operation": "add_expected_record", "collection": "rule_candidates", "record": {"citation_keys": [EXPECTED_CITATION_KEY], "target": "target_manifest", "scope": "scope_manifest", "condition": {"field": "controlled_field", "operator": "equals", "value": "value_manifest"}, "operator": "equals", "value": "value_manifest", "structured_rule_ready": True}}
            plan = corrective.build_autonomous_pdf_corrective_action_plan(case["remediation_case_id"], "apply_benchmark_manifest_amendment", payload, root=root)
            manifest = benchmark.validate_autonomous_pdf_benchmark_manifest("bench_stale", root=root)["manifest"]
            manifest["expected"]["rule_candidates"].append({"citation_keys": [EXPECTED_CITATION_KEY], "target": "other", "scope": "other", "condition": {"field": "controlled_field", "operator": "equals", "value": "other"}, "operator": "equals", "value": "other", "structured_rule_ready": True})
            manifest["manifest_fingerprint"] = benchmark.analysis_backend._hash_payload({k: v for k, v in manifest.items() if k != "manifest_fingerprint"})
            (root / benchmark.BENCHMARK_MANIFEST_DIR / "bench_stale.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
            stale = corrective.execute_autonomous_pdf_corrective_action(plan["corrective_action_id"], confirmation="EXECUTE_ACTION", root=root)
        self.assertEqual(stale["status"], "stale")

    def test_later_benchmark_reuses_phase_9l_verification_and_closes_action(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            helper = AutonomousPdfRemediationTest()
            case, triaged = self._reviewed_case(root, review_decision="accept_for_targeted_fix", root_cause="phase_9j_pipeline_defect", benchmark_id="bench_verify_action")
            plan = corrective.build_autonomous_pdf_corrective_action_plan(case["remediation_case_id"], "create_phase_9j_fix_package", {"summary": "Investigate proposal and candidate generation."}, root=root)
            corrective.execute_autonomous_pdf_corrective_action(plan["corrective_action_id"], confirmation="EXECUTE_ACTION", root=root)
            document_id, run_id = "pdf_bench", "run_1"
            _benchmark_manifest(root, {"schema_version": benchmark.MANIFEST_SCHEMA, "benchmark_id": "bench_verify_action_new", "document_id": document_id, "source_revision": 3, "source_sha256": f"sha256:{document_id}_rev3", "document_class": "clean_digital_pdf", "benchmark_basis": "independent_controlled_annotation", "release_policy_id": benchmark.RELEASE_POLICY_ID, "expected": {"page_count": 4, "section_anchors": [], "citations": [{"document_id": document_id, "source_revision": 3, "page": 1, "chunk_id": "chunk_1", "selected_text_hash": "hash_1"}], "proposals": [{"citation_keys": [EXPECTED_CITATION_KEY], "target": "target_a", "scope": "scope_a", "condition": {"field": "controlled_field", "operator": "equals", "value": "value_a"}, "operator": "equals", "value": "value_a"}], "rule_candidates": [{"citation_keys": [EXPECTED_CITATION_KEY], "target": "target_a", "scope": "scope_a", "condition": {"field": "controlled_field", "operator": "equals", "value": "value_a"}, "operator": "equals", "value": "value_a", "structured_rule_ready": True}], "certified_rules": [{"rule_type": "electional_constraint", "target": "target_a", "scope": "scope_a", "condition": {"field": "controlled_field", "operator": "equals", "value": "value_a"}, "operator": "equals", "value": "value_a"}], "blocked_candidates": []}})
            second = benchmark.run_autonomous_pdf_benchmark("bench_verify_action_new", run_id, confirmation="BENCHMARK", root=root)
            verified = corrective.verify_autonomous_pdf_corrective_action(plan["corrective_action_id"], second["benchmark_result_id"], confirmation="VERIFY_ACTION", root=root)
            closed = corrective.close_autonomous_pdf_corrective_action(plan["corrective_action_id"], confirmation="CLOSE_ACTION", root=root)
        self.assertEqual(verified["status"], "verified")
        self.assertIn(verified["verification_outcome"], {"resolved", "partially_resolved", "persists", "regressed"})
        self.assertEqual(closed["status"], "closed")

    def test_api_flow_idempotency_receipts_health_and_public_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            case, _triaged = self._reviewed_case(root, review_decision="no_action", benchmark_id="bench_api_action")
            workspace = api_workspace(case["remediation_case_id"], root=root)
            plan = api_plan(case["remediation_case_id"], "close_no_action", root=root)
            executed = api_execute(plan["corrective_action_id"], confirmation="EXECUTE_ACTION", root=root)
            executed_again = api_execute(plan["corrective_action_id"], confirmation="EXECUTE_ACTION", root=root)
            report = api_report(plan["corrective_action_id"], public_safe=True, root=root)
            health = corrective.get_autonomous_pdf_corrective_action_health(plan["corrective_action_id"], root=root)
        self.assertEqual(workspace["document_id"], "pdf_bench")
        self.assertEqual(executed["status"], "closed")
        self.assertEqual(executed_again["status"], "already_executed")
        self.assertEqual(health["status"], "healthy")
        self.assertIn("Autonomous PDF Corrective Action", report)
        self.assertNotIn(str(root), report)
        self.assertNotIn("value_a", report)
