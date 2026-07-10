from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import autonomous_pdf_benchmark as benchmark
from backend.electional.api import (
    build_autonomous_pdf_benchmark_workspace as api_build_workspace,
    format_autonomous_pdf_benchmark_report as api_format_report,
    get_autonomous_pdf_benchmark_health as api_health,
    run_autonomous_pdf_benchmark as api_run,
    validate_autonomous_pdf_benchmark_manifest as api_validate_manifest,
)

EXPECTED_CITATION_KEY = "pdf_bench|3|chunk_1|1|hash_1"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _source_record(root: Path, document_id: str, source_revision: int, *, page_count: int = 4) -> None:
    extracted_path = root / "extracted_text" / f"{document_id}.txt"
    extracted_path.parent.mkdir(parents=True, exist_ok=True)
    extracted_path.write_text("Native text available", encoding="utf-8")
    _write_json(
        root / "indexes" / f"{document_id}.json",
        {
            "document_id": document_id,
            "original_filename": f"{document_id}.pdf",
            "source_path": f"C:\\private\\{document_id}.pdf",
            "stored_pdf_path": None,
            "sha256": f"sha256:{document_id}_rev{source_revision}",
            "size_bytes": 100,
            "page_count": page_count,
            "privacy_level": "private_local",
            "extraction_status": "extracted",
            "extracted_text_path": str(extracted_path),
            "extracted_char_count": 21,
            "warnings": [],
            "created_at_utc": "2026-01-01T00:00:00Z",
            "updated_at_utc": "2026-01-01T00:00:00Z",
        },
    )


def _document_manifest(root: Path, document_id: str, source_revision: int) -> None:
    _write_json(
        root / "document_manifests" / f"{document_id}.json",
        {
            "schema_version": "document_manifest_v1",
            "manifest_id": f"manifest_{document_id}",
            "document_id": document_id,
            "source_revision": source_revision,
            "source_hash": f"sha256:{document_id}_rev{source_revision}",
            "pipeline_fingerprint": f"sha256:manifest_{document_id}_{source_revision}",
            "backend_readiness": {"status": "ready"},
            "pipeline": {"preflight": "ready"},
            "warnings": [],
            "blockers": [],
        },
    )


def _content_map(root: Path, document_id: str, source_revision: int, sections: list[dict]) -> None:
    _write_json(
        root / "document_content_maps" / f"{document_id}.json",
        {
            "schema_version": "document_content_map_v1",
            "content_map_id": f"content_map_{document_id}",
            "document_id": document_id,
            "source_revision": source_revision,
            "document_scoped_fingerprint": f"sha256:content_map_{document_id}_{source_revision}",
            "structure_status": "chaptered",
            "chapters": [],
            "sections": sections,
            "section_count": len(sections),
            "chunk_count": len(sections),
            "unassigned_chunk_ids": [],
            "topic_tags": [],
        },
    )


def _autonomous_run(root: Path, run_id: str, document_id: str, source_revision: int, item_results: list[dict], *, status: str = "completed", document_class: str = "clean_digital_pdf") -> None:
    _write_json(
        root / "autonomous_pdf_runs" / f"{run_id}.json",
        {
            "schema_version": "autonomous_pdf_run_v1",
            "autonomous_run_id": run_id,
            "autonomous_plan_id": f"plan_{run_id}",
            "document_id": document_id,
            "source_revision": source_revision,
            "document_class": document_class,
            "manifest_fingerprint": f"sha256:manifest_{document_id}_{source_revision}",
            "plan_fingerprint": f"sha256:plan_{run_id}",
            "policy_id": "native_text_autonomy_policy_v1",
            "status": status,
            "item_results": item_results,
            "blocked_items": [item for item in item_results if item.get("blocker")],
        },
    )
    _write_json(
        root / "autonomous_pdf_receipts" / f"autonomous_pdf_receipt_{run_id}.json",
        {
            "schema_version": "autonomous_pdf_receipt_v1",
            "autonomous_receipt_id": f"autonomous_pdf_receipt_{run_id}",
            "autonomous_run_id": run_id,
            "autonomous_plan_id": f"plan_{run_id}",
            "document_id": document_id,
            "source_revision": source_revision,
            "document_class": document_class,
            "manifest_fingerprint": f"sha256:manifest_{document_id}_{source_revision}",
            "plan_fingerprint": f"sha256:plan_{run_id}",
            "policy_id": "native_text_autonomy_policy_v1",
            "final_status": status,
        },
    )


def _citation(root: Path, citation_id: str, document_id: str, source_revision: int, *, page: int, chunk_id: str, text_hash: str) -> None:
    _write_json(
        root / "citations" / f"{citation_id}.json",
        {
            "citation_id": citation_id,
            "document_id": document_id,
            "source_revision": source_revision,
            "page_start": page,
            "page_end": page,
            "page": page,
            "chunk_id": chunk_id,
            "selected_text_hash": text_hash,
            "locator": {"document_id": document_id, "source_revision": source_revision, "page": page, "chunk_id": chunk_id},
        },
    )


def _proposal(root: Path, proposal_id: str, document_id: str, source_revision: int, *, citation_ids: list[str], target: str, scope: str, value: str, operator: str = "equals") -> None:
    _write_json(
        root / "proposals" / f"{proposal_id}.json",
        {
            "proposal_id": proposal_id,
            "document_id": document_id,
            "source_revision": source_revision,
            "accepted_citation_ids": citation_ids,
            "target": target,
            "scope": scope,
            "condition": {"field": "controlled_field", "operator": operator, "value": value},
            "operator": operator,
            "value": value,
            "structured_rule_ready": True,
        },
    )


def _rule(root: Path, rule_id: str, document_id: str, source_revision: int, *, proposal_id: str, target: str, scope: str, value: str, status: str = "active") -> None:
    _write_json(
        root / "canonical_rules" / f"{rule_id}.json",
        {
            "schema_version": "canonical_mutable_rule_v1",
            "rule_id": rule_id,
            "rule_type": "electional_constraint",
            "target": target,
            "scope": scope,
            "condition": {"field": "controlled_field", "operator": "equals", "value": value},
            "operator": "equals",
            "value": value,
            "enabled": True,
            "status": status,
            "document_id": document_id,
            "source_proposal_id": proposal_id,
            "source_promotion_receipt_id": f"promotion_{proposal_id}",
            "source_rule_activation_review_id": f"review_{proposal_id}",
            "source_revision": source_revision,
        },
    )


def _certification_receipt(root: Path, cert_id: str, rule_id: str, document_id: str, source_revision: int, proposal_id: str) -> None:
    _write_json(
        root / "rule_activation_certification_receipts" / f"{cert_id}.json",
        {
            "schema_version": "rule_activation_certification_receipt_v1",
            "certification_receipt_id": cert_id,
            "revalidation_id": f"revalidation_{rule_id}",
            "rule_id": rule_id,
            "proposal_id": proposal_id,
            "document_id": document_id,
            "source_revision": source_revision,
            "certification_status": "completed",
        },
    )


def _benchmark_manifest(root: Path, payload: dict) -> None:
    manifest = dict(payload)
    manifest["manifest_fingerprint"] = benchmark.analysis_backend._hash_payload({k: v for k, v in manifest.items() if k != "manifest_fingerprint"})
    _write_json(root / "autonomous_pdf_benchmark_manifests" / f"{payload['benchmark_id']}.json", manifest)


class AutonomousPdfBenchmarkTest(TestCase):
    def _base_fixture(self, root: Path, *, document_class: str = "clean_digital_pdf", run_status: str = "completed") -> tuple[str, str]:
        document_id = "pdf_bench"
        source_revision = 3
        _source_record(root, document_id, source_revision, page_count=4)
        _document_manifest(root, document_id, source_revision)
        _content_map(
            root,
            document_id,
            source_revision,
            [
                {"section_id": "sec_001", "title": "Section One", "page_start": 1},
                {"section_id": "sec_002", "title": "Section Two", "page_start": 2},
            ],
        )
        _citation(root, "citation_1", document_id, source_revision, page=1, chunk_id="chunk_1", text_hash="hash_1")
        _proposal(root, "proposal_1", document_id, source_revision, citation_ids=["citation_1"], target="target_a", scope="scope_a", value="value_a")
        _rule(root, "rule_1", document_id, source_revision, proposal_id="proposal_1", target="target_a", scope="scope_a", value="value_a")
        _certification_receipt(root, "cert_1", "rule_1", document_id, source_revision, "proposal_1")
        _autonomous_run(
            root,
            "run_1",
            document_id,
            source_revision,
            [
                {
                    "candidate_id": "cand_1",
                    "citation_id": "citation_1",
                    "proposal_id": "proposal_1",
                    "activation_receipt_id": "activation_1",
                    "certification_receipt_id": "cert_1",
                }
            ],
            status=run_status,
            document_class=document_class,
        )
        return document_id, "run_1"

    def test_clean_pdf_exact_outputs_pass_clean_release_gate(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            document_id, run_id = self._base_fixture(root)
            _benchmark_manifest(
                root,
                {
                    "schema_version": benchmark.MANIFEST_SCHEMA,
                    "benchmark_id": "benchmark_clean_001",
                    "document_id": document_id,
                    "source_revision": 3,
                    "source_sha256": f"sha256:{document_id}_rev3",
                    "document_class": "clean_digital_pdf",
                    "benchmark_basis": "independent_controlled_annotation",
                    "release_policy_id": benchmark.RELEASE_POLICY_ID,
                    "expected": {
                        "page_count": 4,
                        "section_anchors": [
                            {"page_number": 1, "normalized_heading": "section one", "locator": "page:1"},
                            {"page_number": 2, "normalized_heading": "section two", "locator": "page:2"},
                        ],
                        "citations": [{"document_id": document_id, "source_revision": 3, "page": 1, "chunk_id": "chunk_1", "selected_text_hash": "hash_1"}],
                        "proposals": [{"citation_keys": [EXPECTED_CITATION_KEY], "target": "target_a", "scope": "scope_a", "condition": {"field": "controlled_field", "operator": "equals", "value": "value_a"}, "operator": "equals", "value": "value_a"}],
                        "certified_rules": [{"rule_type": "electional_constraint", "target": "target_a", "scope": "scope_a", "condition": {"field": "controlled_field", "operator": "equals", "value": "value_a"}, "operator": "equals", "value": "value_a"}],
                        "blocked_candidates": [],
                    },
                },
            )
            result = benchmark.run_autonomous_pdf_benchmark("benchmark_clean_001", run_id, confirmation="BENCHMARK", root=root)
            loaded = benchmark.load_autonomous_pdf_benchmark_result(result["benchmark_result_id"], root=root)
        self.assertEqual(result["release_classification"], "passes_clean_pdf_gate")
        self.assertEqual(loaded["benchmark_result"]["stage_metrics"]["citation_precision"]["value"], 1.0)

    def test_complex_pdf_partial_recall_passes_only_when_thresholds_are_met(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            document_id, run_id = self._base_fixture(root, document_class="complex_digital_pdf", run_status="completed_with_blocked_items")
            _content_map(
                root,
                document_id,
                3,
                [
                    {"section_id": "sec_001", "title": "Section One", "page_start": 1},
                    {"section_id": "sec_002", "title": "Section Two", "page_start": 2},
                    {"section_id": "sec_003", "title": "Section Three", "page_start": 3},
                    {"section_id": "sec_004", "title": "Section Four", "page_start": 4},
                ],
            )
            _autonomous_run(
                root,
                run_id,
                document_id,
                3,
                [
                    {
                        "candidate_id": "cand_1",
                        "citation_id": "citation_1",
                        "proposal_id": "proposal_1",
                        "activation_receipt_id": "activation_1",
                        "certification_receipt_id": "cert_1",
                    },
                    {"candidate_id": "cand_blocked", "blocker": "ambiguous_or_near_duplicate_evidence"},
                ],
                status="completed_with_blocked_items",
                document_class="complex_digital_pdf",
            )
            _benchmark_manifest(
                root,
                {
                    "schema_version": benchmark.MANIFEST_SCHEMA,
                    "benchmark_id": "benchmark_complex_001",
                    "document_id": document_id,
                    "source_revision": 3,
                    "source_sha256": f"sha256:{document_id}_rev3",
                    "document_class": "complex_digital_pdf",
                    "benchmark_basis": "independent_controlled_annotation",
                    "release_policy_id": benchmark.RELEASE_POLICY_ID,
                    "expected": {
                        "page_count": 4,
                        "section_anchors": [
                            {"page_number": 1, "normalized_heading": "section one", "locator": "page:1"},
                            {"page_number": 2, "normalized_heading": "section two", "locator": "page:2"},
                            {"page_number": 3, "normalized_heading": "section three", "locator": "page:3"},
                            {"page_number": 4, "normalized_heading": "section four", "locator": "page:4"},
                            {"page_number": 5, "normalized_heading": "section five", "locator": "page:5"},
                        ],
                        "citations": [{"document_id": document_id, "source_revision": 3, "page": 1, "chunk_id": "chunk_1", "selected_text_hash": "hash_1"}],
                        "proposals": [{"citation_keys": [EXPECTED_CITATION_KEY], "target": "target_a", "scope": "scope_a", "condition": {"field": "controlled_field", "operator": "equals", "value": "value_a"}, "operator": "equals", "value": "value_a"}],
                        "certified_rules": [{"rule_type": "electional_constraint", "target": "target_a", "scope": "scope_a", "condition": {"field": "controlled_field", "operator": "equals", "value": "value_a"}, "operator": "equals", "value": "value_a"}],
                        "blocked_candidates": [{"candidate_id": "cand_blocked", "expected_blocker_code": "ambiguous_or_near_duplicate_evidence", "expected_blocked_stage": "blocking"}],
                    },
                },
            )
            result = benchmark.run_autonomous_pdf_benchmark("benchmark_complex_001", run_id, confirmation="BENCHMARK", root=root)
        self.assertEqual(result["release_classification"], "passes_complex_pdf_gate")

    def test_false_positive_rule_activation_fails_safety_gate(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            document_id, run_id = self._base_fixture(root)
            _rule(root, "rule_extra", document_id, 3, proposal_id="proposal_1", target="target_extra", scope="scope_extra", value="value_extra")
            _certification_receipt(root, "cert_extra", "rule_extra", document_id, 3, "proposal_1")
            _autonomous_run(
                root,
                run_id,
                document_id,
                3,
                [
                    {"candidate_id": "cand_1", "citation_id": "citation_1", "proposal_id": "proposal_1", "activation_receipt_id": "activation_1", "certification_receipt_id": "cert_1"},
                    {"candidate_id": "cand_extra", "proposal_id": "proposal_1", "activation_receipt_id": "activation_extra", "certification_receipt_id": "cert_extra"},
                ],
            )
            _benchmark_manifest(
                root,
                {
                    "schema_version": benchmark.MANIFEST_SCHEMA,
                    "benchmark_id": "benchmark_safety_001",
                    "document_id": document_id,
                    "source_revision": 3,
                    "source_sha256": f"sha256:{document_id}_rev3",
                    "document_class": "clean_digital_pdf",
                    "benchmark_basis": "independent_controlled_annotation",
                    "release_policy_id": benchmark.RELEASE_POLICY_ID,
                    "expected": {"page_count": 4, "section_anchors": [], "citations": [], "proposals": [], "certified_rules": [{"rule_type": "electional_constraint", "target": "target_a", "scope": "scope_a", "condition": {"field": "controlled_field", "operator": "equals", "value": "value_a"}, "operator": "equals", "value": "value_a"}], "blocked_candidates": []},
                },
            )
            result = benchmark.run_autonomous_pdf_benchmark("benchmark_safety_001", run_id, confirmation="BENCHMARK", root=root)
        self.assertEqual(result["release_classification"], "fails_safety_gate")

    def test_expected_missing_citation_is_localized_as_false_negative(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            document_id, run_id = self._base_fixture(root)
            _benchmark_manifest(
                root,
                {
                    "schema_version": benchmark.MANIFEST_SCHEMA,
                    "benchmark_id": "benchmark_miss_001",
                    "document_id": document_id,
                    "source_revision": 3,
                    "source_sha256": f"sha256:{document_id}_rev3",
                    "document_class": "clean_digital_pdf",
                    "benchmark_basis": "independent_controlled_annotation",
                    "release_policy_id": benchmark.RELEASE_POLICY_ID,
                    "expected": {
                        "page_count": 4,
                        "section_anchors": [],
                        "citations": [
                            {"document_id": document_id, "source_revision": 3, "page": 1, "chunk_id": "chunk_1", "selected_text_hash": "hash_1"},
                            {"document_id": document_id, "source_revision": 3, "page": 2, "chunk_id": "chunk_2", "selected_text_hash": "hash_2"},
                        ],
                        "proposals": [],
                        "certified_rules": [],
                        "blocked_candidates": [],
                    },
                },
            )
            result = benchmark.run_autonomous_pdf_benchmark("benchmark_miss_001", run_id, confirmation="BENCHMARK", root=root)
            loaded = benchmark.load_autonomous_pdf_benchmark_result(result["benchmark_result_id"], root=root)
        self.assertTrue(any(item["classification"] == "false_negative" and item["stage"] == "citation_creation" for item in loaded["benchmark_result"]["mismatches"]))

    def test_expected_blocker_allowed_through_is_unexpectedly_unblocked(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            document_id, run_id = self._base_fixture(root)
            _benchmark_manifest(
                root,
                {
                    "schema_version": benchmark.MANIFEST_SCHEMA,
                    "benchmark_id": "benchmark_blocker_001",
                    "document_id": document_id,
                    "source_revision": 3,
                    "source_sha256": f"sha256:{document_id}_rev3",
                    "document_class": "clean_digital_pdf",
                    "benchmark_basis": "independent_controlled_annotation",
                    "release_policy_id": benchmark.RELEASE_POLICY_ID,
                    "expected": {"page_count": 4, "section_anchors": [], "citations": [], "proposals": [], "certified_rules": [], "blocked_candidates": [{"candidate_id": "cand_expected_block", "expected_blocker_code": "ambiguous_or_near_duplicate_evidence", "expected_blocked_stage": "blocking"}]},
                },
            )
            result = benchmark.run_autonomous_pdf_benchmark("benchmark_blocker_001", run_id, confirmation="BENCHMARK", root=root)
            loaded = benchmark.load_autonomous_pdf_benchmark_result(result["benchmark_result_id"], root=root)
        self.assertTrue(any(item["classification"] == "unexpectedly_unblocked" for item in loaded["benchmark_result"]["mismatches"]))

    def test_manifest_derived_from_autonomous_output_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            document_id, _run_id = self._base_fixture(root)
            _benchmark_manifest(
                root,
                {
                    "schema_version": benchmark.MANIFEST_SCHEMA,
                    "benchmark_id": "benchmark_invalid_001",
                    "document_id": document_id,
                    "source_revision": 3,
                    "source_sha256": f"sha256:{document_id}_rev3",
                    "document_class": "clean_digital_pdf",
                    "benchmark_basis": "autonomous_output_derived_manifest",
                    "release_policy_id": benchmark.RELEASE_POLICY_ID,
                    "expected": {"page_count": 4, "section_anchors": [], "citations": [], "proposals": [], "certified_rules": [], "blocked_candidates": []},
                },
            )
            result = api_validate_manifest("benchmark_invalid_001", root=root)
        self.assertEqual(result["status"], "invalid")
        self.assertIn("benchmark_basis_not_independent", result["blockers"])

    def test_invalid_expected_citation_locator_blocks_manifest(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            document_id, _run_id = self._base_fixture(root)
            _benchmark_manifest(
                root,
                {
                    "schema_version": benchmark.MANIFEST_SCHEMA,
                    "benchmark_id": "benchmark_invalid_locator_001",
                    "document_id": document_id,
                    "source_revision": 3,
                    "source_sha256": f"sha256:{document_id}_rev3",
                    "document_class": "clean_digital_pdf",
                    "benchmark_basis": "independent_controlled_annotation",
                    "release_policy_id": benchmark.RELEASE_POLICY_ID,
                    "expected": {
                        "page_count": 4,
                        "section_anchors": [],
                        "citations": [{"document_id": document_id, "source_revision": 3, "page": "not-a-page", "chunk_id": "chunk_1", "selected_text_hash": "hash_1"}],
                        "proposals": [],
                        "certified_rules": [],
                        "blocked_candidates": [],
                    },
                },
            )
            result = api_validate_manifest("benchmark_invalid_locator_001", root=root)
        self.assertEqual(result["status"], "invalid")
        self.assertIn("invalid_expected_citation_locator", result["blockers"])

    def test_changed_manifest_or_run_makes_result_stale_and_rerun_idempotent(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            document_id, run_id = self._base_fixture(root)
            payload = {
                "schema_version": benchmark.MANIFEST_SCHEMA,
                "benchmark_id": "benchmark_stale_001",
                "document_id": document_id,
                "source_revision": 3,
                "source_sha256": f"sha256:{document_id}_rev3",
                "document_class": "clean_digital_pdf",
                "benchmark_basis": "independent_controlled_annotation",
                "release_policy_id": benchmark.RELEASE_POLICY_ID,
                "expected": {"page_count": 4, "section_anchors": [], "citations": [], "proposals": [], "certified_rules": [], "blocked_candidates": []},
            }
            _benchmark_manifest(root, payload)
            first = benchmark.run_autonomous_pdf_benchmark("benchmark_stale_001", run_id, confirmation="BENCHMARK", root=root)
            second = benchmark.run_autonomous_pdf_benchmark("benchmark_stale_001", run_id, confirmation="BENCHMARK", root=root)
            payload["expected"]["page_count"] = 5
            _benchmark_manifest(root, payload)
            health = benchmark.get_autonomous_pdf_benchmark_health("benchmark_stale_001", root=root)
            third = benchmark.run_autonomous_pdf_benchmark("benchmark_stale_001", run_id, confirmation="BENCHMARK", root=root)
        self.assertEqual(second["status"], "already_benchmarked")
        self.assertEqual(health["status"], "stale")
        self.assertNotEqual(first["benchmark_result_id"], third["benchmark_result_id"])

    def test_proposal_matching_uses_stable_citation_identity_not_generated_ids(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            document_id, run_id = self._base_fixture(root)
            _citation(root, "citation_alias", document_id, 3, page=1, chunk_id="chunk_1", text_hash="hash_1")
            _proposal(root, "proposal_alias", document_id, 3, citation_ids=["citation_alias"], target="target_a", scope="scope_a", value="value_a")
            _rule(root, "rule_alias", document_id, 3, proposal_id="proposal_alias", target="target_a", scope="scope_a", value="value_a")
            _certification_receipt(root, "cert_alias", "rule_alias", document_id, 3, "proposal_alias")
            _autonomous_run(
                root,
                run_id,
                document_id,
                3,
                [
                    {
                        "candidate_id": "cand_alias",
                        "citation_id": "citation_alias",
                        "proposal_id": "proposal_alias",
                        "activation_receipt_id": "activation_alias",
                        "certification_receipt_id": "cert_alias",
                    }
                ],
            )
            _benchmark_manifest(
                root,
                {
                    "schema_version": benchmark.MANIFEST_SCHEMA,
                    "benchmark_id": "benchmark_stable_ids_001",
                    "document_id": document_id,
                    "source_revision": 3,
                    "source_sha256": f"sha256:{document_id}_rev3",
                    "document_class": "clean_digital_pdf",
                    "benchmark_basis": "independent_controlled_annotation",
                    "release_policy_id": benchmark.RELEASE_POLICY_ID,
                    "expected": {
                        "page_count": 4,
                        "section_anchors": [
                            {"page_number": 1, "normalized_heading": "section one", "locator": "page:1"},
                            {"page_number": 2, "normalized_heading": "section two", "locator": "page:2"},
                        ],
                        "citations": [{"document_id": document_id, "source_revision": 3, "page": 1, "chunk_id": "chunk_1", "selected_text_hash": "hash_1"}],
                        "proposals": [{"citation_keys": [EXPECTED_CITATION_KEY], "target": "target_a", "scope": "scope_a", "condition": {"field": "controlled_field", "operator": "equals", "value": "value_a"}, "operator": "equals", "value": "value_a"}],
                        "certified_rules": [{"rule_type": "electional_constraint", "target": "target_a", "scope": "scope_a", "condition": {"field": "controlled_field", "operator": "equals", "value": "value_a"}, "operator": "equals", "value": "value_a"}],
                        "blocked_candidates": [],
                    },
                },
            )
            result = benchmark.run_autonomous_pdf_benchmark("benchmark_stable_ids_001", run_id, confirmation="BENCHMARK", root=root)
            loaded = benchmark.load_autonomous_pdf_benchmark_result(result["benchmark_result_id"], root=root)
        self.assertEqual(loaded["benchmark_result"]["stage_metrics"]["proposal_precision"]["value"], 1.0)
        self.assertEqual(loaded["benchmark_result"]["stage_metrics"]["proposal_recall"]["value"], 1.0)

    def test_rule_candidates_are_compared_independently_before_activation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            document_id, run_id = self._base_fixture(root)
            _proposal(root, "proposal_extra", document_id, 3, citation_ids=["citation_1"], target="target_extra", scope="scope_extra", value="value_extra")
            _autonomous_run(
                root,
                run_id,
                document_id,
                3,
                [
                    {
                        "candidate_id": "cand_1",
                        "citation_id": "citation_1",
                        "proposal_id": "proposal_1",
                        "activation_receipt_id": "activation_1",
                        "certification_receipt_id": "cert_1",
                    },
                    {
                        "candidate_id": "cand_extra",
                        "citation_id": "citation_1",
                        "proposal_id": "proposal_extra",
                    },
                ],
            )
            _benchmark_manifest(
                root,
                {
                    "schema_version": benchmark.MANIFEST_SCHEMA,
                    "benchmark_id": "benchmark_rule_candidates_001",
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
                        "rule_candidates": [
                            {"citation_keys": [EXPECTED_CITATION_KEY], "target": "target_a", "scope": "scope_a", "condition": {"field": "controlled_field", "operator": "equals", "value": "value_a"}, "operator": "equals", "value": "value_a", "structured_rule_ready": True},
                            {"citation_keys": [EXPECTED_CITATION_KEY], "target": "target_missing", "scope": "scope_missing", "condition": {"field": "controlled_field", "operator": "equals", "value": "value_missing"}, "operator": "equals", "value": "value_missing", "structured_rule_ready": True},
                        ],
                        "certified_rules": [{"rule_type": "electional_constraint", "target": "target_a", "scope": "scope_a", "condition": {"field": "controlled_field", "operator": "equals", "value": "value_a"}, "operator": "equals", "value": "value_a"}],
                        "blocked_candidates": [],
                    },
                },
            )
            result = benchmark.run_autonomous_pdf_benchmark("benchmark_rule_candidates_001", run_id, confirmation="BENCHMARK", root=root)
            loaded = benchmark.load_autonomous_pdf_benchmark_result(result["benchmark_result_id"], root=root)
            metrics = loaded["benchmark_result"]["stage_metrics"]
            mismatches = loaded["benchmark_result"]["mismatches"]
        self.assertEqual(metrics["rule_candidate_precision"]["value"], 0.5)
        self.assertEqual(metrics["rule_candidate_recall"]["value"], 0.5)
        self.assertTrue(any(item["stage"] == "rule_candidate_generation" and item["classification"] == "false_positive" for item in mismatches))
        self.assertTrue(any(item["stage"] == "rule_candidate_generation" and item["classification"] == "false_negative" for item in mismatches))
        self.assertEqual(metrics["rule_activation_precision"]["value"], 1.0)

    def test_api_benchmark_flow_health_receipt_and_public_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            document_id, run_id = self._base_fixture(root)
            _benchmark_manifest(
                root,
                {
                    "schema_version": benchmark.MANIFEST_SCHEMA,
                    "benchmark_id": "benchmark_api_001",
                    "document_id": document_id,
                    "source_revision": 3,
                    "source_sha256": f"sha256:{document_id}_rev3",
                    "document_class": "clean_digital_pdf",
                    "benchmark_basis": "independent_controlled_annotation",
                    "release_policy_id": benchmark.RELEASE_POLICY_ID,
                    "expected": {"page_count": 4, "section_anchors": [], "citations": [{"document_id": document_id, "source_revision": 3, "page": 1, "chunk_id": "chunk_1", "selected_text_hash": "hash_1"}], "proposals": [{"citation_keys": [EXPECTED_CITATION_KEY], "target": "target_a", "scope": "scope_a", "condition": {"field": "controlled_field", "operator": "equals", "value": "value_a"}, "operator": "equals", "value": "value_a"}], "certified_rules": [{"rule_type": "electional_constraint", "target": "target_a", "scope": "scope_a", "condition": {"field": "controlled_field", "operator": "equals", "value": "value_a"}, "operator": "equals", "value": "value_a"}], "blocked_candidates": []},
                },
            )
            workspace = api_build_workspace("benchmark_api_001", autonomous_run_id=run_id, root=root)
            blocked = api_run("benchmark_api_001", run_id, confirmation=None, root=root)
            result = api_run("benchmark_api_001", run_id, confirmation="BENCHMARK", root=root)
            health = api_health("benchmark_api_001", root=root)
            report = api_format_report(benchmark_result_id=result["benchmark_result_id"], public_safe=True, root=root)
        self.assertEqual(workspace["document_id"], document_id)
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(result["status"], "benchmarked")
        self.assertEqual(health["status"], "healthy")
        self.assertIn("Autonomous PDF Quality Benchmark", report)
        self.assertNotIn(str(root), report)
        self.assertNotIn("C:\\private", report)
