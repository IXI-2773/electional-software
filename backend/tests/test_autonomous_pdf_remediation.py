from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import autonomous_pdf_benchmark as benchmark
from backend.electional import autonomous_pdf_remediation as remediation
from backend.electional.api import (
    build_autonomous_pdf_remediation_workspace as api_workspace,
    format_autonomous_pdf_remediation_report as api_report,
    review_autonomous_pdf_remediation_case as api_review,
    run_autonomous_pdf_remediation_triage as api_triage,
    verify_autonomous_pdf_remediation as api_verify,
)
from backend.tests.test_autonomous_pdf_benchmark import (
    EXPECTED_CITATION_KEY,
    _autonomous_run,
    _benchmark_manifest,
    _content_map,
    _proposal,
    _rule,
    AutonomousPdfBenchmarkTest,
)


class AutonomousPdfRemediationTest(TestCase):
    def _fixture(self, root: Path) -> tuple[str, str]:
        helper = AutonomousPdfBenchmarkTest()
        return helper._base_fixture(root)

    def _failing_result(self, root: Path, benchmark_id: str = "bench_remediate_001") -> dict:
        document_id, run_id = self._fixture(root)
        _proposal(root, "proposal_extra", document_id, 3, citation_ids=["citation_1"], target="target_extra", scope="scope_extra", value="value_extra")
        _autonomous_run(
            root,
            run_id,
            document_id,
            3,
            [
                {"candidate_id": "cand_1", "citation_id": "citation_1", "proposal_id": "proposal_1", "activation_receipt_id": "activation_1", "certification_receipt_id": "cert_1"},
                {"candidate_id": "cand_extra", "citation_id": "citation_1", "proposal_id": "proposal_extra"},
            ],
        )
        _benchmark_manifest(
            root,
            {
                "schema_version": benchmark.MANIFEST_SCHEMA,
                "benchmark_id": benchmark_id,
                "document_id": document_id,
                "source_revision": 3,
                "source_sha256": f"sha256:{document_id}_rev3",
                "document_class": "clean_digital_pdf",
                "benchmark_basis": "independent_controlled_annotation",
                "release_policy_id": benchmark.RELEASE_POLICY_ID,
                    "expected": {
                        "page_count": 4,
                        "section_anchors": [],
                        "citations": [{"document_id": document_id, "source_revision": 3, "page": 1, "chunk_id": "chunk_1", "selected_text_hash": "hash_1"}],
                        "proposals": [{"citation_keys": [EXPECTED_CITATION_KEY], "target": "target_a", "scope": "scope_a", "condition": {"field": "controlled_field", "operator": "equals", "value": "value_a"}, "operator": "equals", "value": "value_a"}],
                        "rule_candidates": [{"citation_keys": [EXPECTED_CITATION_KEY], "target": "target_a", "scope": "scope_a", "condition": {"field": "controlled_field", "operator": "equals", "value": "value_a"}, "operator": "equals", "value": "value_a", "structured_rule_ready": True}],
                        "certified_rules": [{"rule_type": "electional_constraint", "target": "target_a", "scope": "scope_a", "condition": {"field": "controlled_field", "operator": "equals", "value": "value_a"}, "operator": "equals", "value": "value_a"}],
                        "blocked_candidates": [],
                    },
                },
            )
        return benchmark.run_autonomous_pdf_benchmark(benchmark_id, run_id, confirmation="BENCHMARK", root=root)

    def test_failing_benchmark_creates_ordered_stage_specific_remediation_cases(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            result = self._failing_result(root)
            triaged = remediation.run_autonomous_pdf_remediation_triage(result["benchmark_result_id"], confirmation="TRIAGE", root=root)
            loaded = remediation.load_autonomous_pdf_remediation_plan(triaged["remediation_plan_id"], root=root)
        cases = loaded["cases"]
        self.assertEqual(triaged["status"], "triaged")
        self.assertTrue(cases)
        self.assertIn("proposal_generation", {case["stage"] for case in cases})
        self.assertTrue(all(c["document_id"] == "pdf_bench" and c["source_revision"] == 3 for c in cases))

    def test_critical_safety_violation_cannot_be_downgraded_by_quality_metrics(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            document_id, run_id = self._fixture(root)
            _rule(root, "rule_extra", document_id, 3, proposal_id="proposal_1", target="target_extra", scope="scope_extra", value="value_extra")
            from backend.tests.test_autonomous_pdf_benchmark import _certification_receipt
            _certification_receipt(root, "cert_extra", "rule_extra", document_id, 3, "proposal_1")
            _autonomous_run(root, run_id, document_id, 3, [{"candidate_id": "cand_extra", "proposal_id": "proposal_1", "certification_receipt_id": "cert_extra"}])
            _benchmark_manifest(root, {"schema_version": benchmark.MANIFEST_SCHEMA, "benchmark_id": "bench_critical_001", "document_id": document_id, "source_revision": 3, "source_sha256": f"sha256:{document_id}_rev3", "document_class": "clean_digital_pdf", "benchmark_basis": "independent_controlled_annotation", "release_policy_id": benchmark.RELEASE_POLICY_ID, "expected": {"page_count": 4, "section_anchors": [], "citations": [], "proposals": [], "rule_candidates": [], "certified_rules": [], "blocked_candidates": []}})
            result = benchmark.run_autonomous_pdf_benchmark("bench_critical_001", run_id, confirmation="BENCHMARK", root=root)
            triaged = remediation.run_autonomous_pdf_remediation_triage(result["benchmark_result_id"], confirmation="TRIAGE", root=root)
            loaded = remediation.load_autonomous_pdf_remediation_plan(triaged["remediation_plan_id"], root=root)
        self.assertEqual(result["release_classification"], "fails_safety_gate")
        self.assertTrue(any(case["severity"] == "critical" for case in loaded["cases"]))

    def test_rule_candidate_failure_stays_separate_from_activation_and_certification(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            result = self._failing_result(root, "bench_candidates_001")
            triaged = remediation.run_autonomous_pdf_remediation_triage(result["benchmark_result_id"], confirmation="TRIAGE", root=root)
            loaded = remediation.load_autonomous_pdf_remediation_plan(triaged["remediation_plan_id"], root=root)
        stages = {case["stage"] for case in loaded["cases"]}
        self.assertIn("rule_candidate_generation", stages)
        self.assertNotIn("rule_activation", stages)
        self.assertNotIn("certification", stages)

    def test_unproven_root_cause_remains_unresolved(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            result = self._failing_result(root, "bench_unresolved_001")
            triaged = remediation.run_autonomous_pdf_remediation_triage(result["benchmark_result_id"], confirmation="TRIAGE", root=root)
            loaded = remediation.load_autonomous_pdf_remediation_plan(triaged["remediation_plan_id"], root=root)
        self.assertTrue(all(case["root_cause_classification"] == "unresolved" for case in loaded["cases"]))

    def test_foreign_document_or_revision_blocks_triage_and_verification(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            result = self._failing_result(root, "bench_foreign_001")
            triaged = remediation.run_autonomous_pdf_remediation_triage(result["benchmark_result_id"], confirmation="TRIAGE", root=root)
            document_id, run_id = self._fixture(root)
            _benchmark_manifest(root, {"schema_version": benchmark.MANIFEST_SCHEMA, "benchmark_id": "bench_foreign_new", "document_id": document_id, "source_revision": 4, "source_sha256": f"sha256:{document_id}_rev4", "document_class": "clean_digital_pdf", "benchmark_basis": "independent_controlled_annotation", "release_policy_id": benchmark.RELEASE_POLICY_ID, "expected": {"page_count": 4, "section_anchors": [], "citations": [], "proposals": [], "rule_candidates": [], "certified_rules": [], "blocked_candidates": []}})
            blocked = remediation.verify_autonomous_pdf_remediation(triaged["remediation_plan_id"], result["benchmark_result_id"], confirmation="VERIFY", root=root)
        self.assertEqual(blocked["status"], "blocked")

    def test_review_requires_confirmation_and_does_not_mutate_pipeline_records(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            result = self._failing_result(root, "bench_review_001")
            triaged = remediation.run_autonomous_pdf_remediation_triage(result["benchmark_result_id"], confirmation="TRIAGE", root=root)
            case = remediation.load_autonomous_pdf_remediation_plan(triaged["remediation_plan_id"], root=root)["cases"][0]
            proposal_before = (root / "proposals" / "proposal_1.json").read_text(encoding="utf-8")
            blocked = remediation.review_autonomous_pdf_remediation_case(case["remediation_case_id"], "accept_for_targeted_fix", confirmation=None, root=root)
            reviewed = remediation.review_autonomous_pdf_remediation_case(case["remediation_case_id"], "accept_for_targeted_fix", confirmation="REVIEW", root=root)
            proposal_after = (root / "proposals" / "proposal_1.json").read_text(encoding="utf-8")
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(reviewed["status"], "reviewed")
        self.assertEqual(proposal_before, proposal_after)

    def test_later_benchmark_marks_cases_resolved_persisting_and_regressed(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            first = self._failing_result(root, "bench_verify_old")
            triaged = remediation.run_autonomous_pdf_remediation_triage(first["benchmark_result_id"], confirmation="TRIAGE", root=root)
            plan = remediation.load_autonomous_pdf_remediation_plan(triaged["remediation_plan_id"], root=root)
            for case in plan["cases"]:
                remediation.review_autonomous_pdf_remediation_case(case["remediation_case_id"], "accept_for_targeted_fix", confirmation="REVIEW", root=root)
            document_id, run_id = "pdf_bench", "run_1"
            _content_map(root, document_id, 3, [{"section_id": "sec_001", "title": "Section One", "page_start": 1}])
            _benchmark_manifest(root, {"schema_version": benchmark.MANIFEST_SCHEMA, "benchmark_id": "bench_verify_new", "document_id": document_id, "source_revision": 3, "source_sha256": f"sha256:{document_id}_rev3", "document_class": "clean_digital_pdf", "benchmark_basis": "independent_controlled_annotation", "release_policy_id": benchmark.RELEASE_POLICY_ID, "expected": {"page_count": 4, "section_anchors": [{"page_number": 1, "normalized_heading": "section one", "locator": "page:1"}], "citations": [{"document_id": document_id, "source_revision": 3, "page": 1, "chunk_id": "chunk_1", "selected_text_hash": "hash_1"}], "proposals": [{"citation_keys": [EXPECTED_CITATION_KEY], "target": "target_a", "scope": "scope_a", "condition": {"field": "controlled_field", "operator": "equals", "value": "value_a"}, "operator": "equals", "value": "value_a"}], "rule_candidates": [{"citation_keys": [EXPECTED_CITATION_KEY], "target": "target_a", "scope": "scope_a", "condition": {"field": "controlled_field", "operator": "equals", "value": "value_a"}, "operator": "equals", "value": "value_a", "structured_rule_ready": True}], "certified_rules": [{"rule_type": "electional_constraint", "target": "target_a", "scope": "scope_a", "condition": {"field": "controlled_field", "operator": "equals", "value": "value_a"}, "operator": "equals", "value": "value_a"}], "blocked_candidates": []}})
            second = benchmark.run_autonomous_pdf_benchmark("bench_verify_new", run_id, confirmation="BENCHMARK", root=root)
            verified = remediation.verify_autonomous_pdf_remediation(triaged["remediation_plan_id"], second["benchmark_result_id"], confirmation="VERIFY", root=root)
        self.assertEqual(verified["status"], "verified")
        self.assertGreaterEqual(verified["resolved_count"], 1)
        self.assertGreaterEqual(verified["regressed_count"], 0)

    def test_api_flow_idempotency_receipts_health_and_public_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            result = self._failing_result(root, "bench_api_001")
            workspace = api_workspace(result["benchmark_result_id"], root=root)
            triaged = api_triage(result["benchmark_result_id"], confirmation="TRIAGE", root=root)
            triaged_again = api_triage(result["benchmark_result_id"], confirmation="TRIAGE", root=root)
            case = remediation.load_autonomous_pdf_remediation_plan(triaged["remediation_plan_id"], root=root)["cases"][0]
            api_review(case["remediation_case_id"], "accept_for_targeted_fix", confirmation="REVIEW", root=root)
            report = api_report(triaged["remediation_plan_id"], public_safe=True, root=root)
            health = remediation.get_autonomous_pdf_remediation_health(triaged["remediation_plan_id"], root=root)
        self.assertEqual(workspace["document_id"], "pdf_bench")
        self.assertEqual(triaged_again["status"], "already_triaged")
        self.assertEqual(health["status"], "healthy")
        self.assertIn("Autonomous PDF Remediation", report)
        self.assertNotIn(str(root), report)
        self.assertNotIn("value_a", report)
