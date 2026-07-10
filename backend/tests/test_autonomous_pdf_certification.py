from __future__ import annotations

import json
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from backend.electional import autonomous_pdf_certification as certification
from backend.electional.api import (
    build_autonomous_pdf_plan as api_build_plan,
    build_autonomous_pdf_workspace as api_build_workspace,
    format_autonomous_pdf_report as api_format_report,
    run_autonomous_pdf_pipeline as api_run_pipeline,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _source_record(root: Path, document_id: str, source_revision: int, *, extracted_text: str = "Native text paragraph.") -> None:
    extracted_path = root / "extracted_text" / f"{document_id}.txt"
    extracted_path.parent.mkdir(parents=True, exist_ok=True)
    extracted_path.write_text(extracted_text, encoding="utf-8")
    _write_json(
        root / "indexes" / f"{document_id}.json",
        {
            "document_id": document_id,
            "original_filename": f"{document_id}.pdf",
            "source_path": f"C:\\private\\{document_id}.pdf",
            "stored_pdf_path": None,
            "sha256": f"sha256:{document_id}_rev{source_revision}",
            "size_bytes": 100,
            "page_count": 2,
            "privacy_level": "private_local",
            "extraction_status": "extracted",
            "extracted_text_path": str(extracted_path),
            "extracted_char_count": len(extracted_text),
            "warnings": [],
            "created_at_utc": "2026-01-01T00:00:00Z",
            "updated_at_utc": "2026-01-01T00:00:00Z",
        },
    )


def _manifest(root: Path, document_id: str, source_revision: int, *, fingerprint: str | None = None) -> None:
    _write_json(
        root / "document_manifests" / f"{document_id}.json",
        {
            "schema_version": "document_manifest_v1",
            "manifest_id": f"manifest_{document_id}",
            "document_id": document_id,
            "source_revision": source_revision,
            "source_hash": f"sha256:{document_id}_rev{source_revision}",
            "previous_source_hash": None,
            "revision_changed": False,
            "lifecycle_status": "ready",
            "pipeline_fingerprint": fingerprint or f"sha256:manifest_{document_id}_rev{source_revision}",
            "backend_readiness": {"status": "ready"},
            "pipeline": {"preflight": "ready"},
            "warnings": [],
            "blockers": [],
            "created_at_utc": "2026-01-01T00:00:00Z",
            "updated_at_utc": "2026-01-01T00:00:00Z",
        },
    )


def _ready_structure(*, complex_pdf: bool = False) -> dict:
    return {
        "document_id": "pdf_a",
        "status": "built",
        "tables": 1 if complex_pdf else 0,
        "figures": 0,
        "footnotes": 1 if complex_pdf else 0,
        "references_found": complex_pdf,
        "header_footer_noise": complex_pdf,
        "warnings": [],
    }


class AutonomousPdfCertificationTest(TestCase):
    def _patch_ready_dependencies(self, *, complex_pdf: bool = False, candidates: list[dict] | None = None) -> ExitStack:
        stack = ExitStack()
        stack.enter_context(patch.object(certification, "get_document_structure_summary", return_value=_ready_structure(complex_pdf=complex_pdf)))
        stack.enter_context(patch.object(certification, "get_document_content_map_summary", return_value={"status": "built"}))
        stack.enter_context(patch.object(certification, "load_document_content_curation", return_value={"status": "ready"}))
        stack.enter_context(patch.object(certification, "get_page_diagnostic_summary", return_value={"pages_diagnosed": 2}))
        stack.enter_context(patch.object(certification, "load_chunks", return_value=[object()]))
        stack.enter_context(patch.object(certification, "build_document_manifest", side_effect=lambda document_id, regenerate=False, root=None: json.loads((Path(root) / "document_manifests" / f"{document_id}.json").read_text(encoding="utf-8"))))
        stack.enter_context(patch.object(certification, "recommend_next_source_workflow_stage", return_value={"recommended_stage": "none"}))
        stack.enter_context(patch.object(certification, "_count_certified_rules", return_value=0))
        stack.enter_context(patch.object(certification, "_discover_harvest_candidates", return_value=candidates or []))
        return stack

    def test_clean_native_text_pdf_reaches_certified_rule_end_to_end(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _source_record(root, "pdf_a", 1)
            _manifest(root, "pdf_a", 1)
            candidate = {"candidate_id": "cand_1", "document_id": "pdf_a", "source_revision": 1, "structured_rule_ready": True}
            with self._patch_ready_dependencies(candidates=[candidate]) as stack:
                stack.enter_context(patch.object(certification, "_create_or_reuse_citation", return_value={"citation_id": "citation_1", "evidence_handoff_id": "handoff_1"}))
                stack.enter_context(patch.object(certification, "_complete_evidence_handoff", return_value={"proposal_id": "proposal_1"}))
                stack.enter_context(patch.object(certification, "_create_or_reuse_proposal", return_value={"proposal_id": "proposal_1", "structured_rule_ready": True}))
                stack.enter_context(patch.object(certification, "_promote_proposal", return_value={"promotion_receipt_id": "promotion_1"}))
                stack.enter_context(patch.object(certification, "_activate_rule", return_value={"activation_receipt_id": "activation_1", "revalidation_id": "revalidation_1"}))
                stack.enter_context(patch.object(certification, "_validate_and_certify_rule", return_value={"certification_receipt_id": "cert_1"}))
                workspace = certification.build_autonomous_pdf_workspace("pdf_a", 1, root=root)
                plan = certification.build_autonomous_pdf_plan("pdf_a", 1, root=root)
                run = certification.run_autonomous_pdf_pipeline(plan["autonomous_plan_id"], confirmation="AUTO_RUN", root=root)
        self.assertEqual(workspace["document_class"], "clean_digital_pdf")
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["certified_rule_count"], 1)
        self.assertTrue(str(run.get("autonomous_receipt_id") or "").startswith("autonomous_pdf_receipt_"))

    def test_complex_native_text_pdf_uses_structure_and_exact_locators(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _source_record(root, "pdf_a", 1)
            _manifest(root, "pdf_a", 1)
            candidate = {"candidate_id": "cand_complex", "document_id": "pdf_a", "source_revision": 1, "structured_rule_ready": False}
            with self._patch_ready_dependencies(complex_pdf=True, candidates=[candidate]) as stack:
                stack.enter_context(patch.object(certification, "_create_or_reuse_citation", return_value={"citation_id": "citation_complex"}))
                stack.enter_context(patch.object(certification, "_complete_evidence_handoff", return_value={"proposal_id": "proposal_complex"}))
                stack.enter_context(patch.object(certification, "_create_or_reuse_proposal", return_value={"proposal_id": "proposal_complex", "structured_rule_ready": False}))
                workspace = certification.build_autonomous_pdf_workspace("pdf_a", 1, root=root)
                plan = certification.build_autonomous_pdf_plan("pdf_a", 1, root=root)
                run = certification.run_autonomous_pdf_pipeline(plan["autonomous_plan_id"], confirmation="AUTO_RUN", root=root)
        self.assertEqual(workspace["document_class"], "complex_digital_pdf")
        self.assertEqual(run["status"], "no_rule_candidates")
        self.assertEqual(run["non_rule_information_count"], 1)

    def test_image_only_pdf_blocks_without_attempting_ocr(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            extracted_path = root / "extracted_text" / "pdf_img.txt"
            extracted_path.parent.mkdir(parents=True, exist_ok=True)
            extracted_path.write_text("", encoding="utf-8")
            _write_json(
                root / "indexes" / "pdf_img.json",
                {
                    "document_id": "pdf_img",
                    "original_filename": "pdf_img.pdf",
                    "source_path": "C:\\private\\pdf_img.pdf",
                    "stored_pdf_path": None,
                    "sha256": "sha256:pdf_img_rev1",
                    "size_bytes": 10,
                    "page_count": 1,
                    "privacy_level": "private_local",
                    "extraction_status": "registered",
                    "extracted_text_path": str(extracted_path),
                    "extracted_char_count": 0,
                    "warnings": [],
                    "created_at_utc": "2026-01-01T00:00:00Z",
                    "updated_at_utc": "2026-01-01T00:00:00Z",
                },
            )
            _manifest(root, "pdf_img", 1)
            with self._patch_ready_dependencies() as stack:
                stack.enter_context(patch.object(certification, "_discover_harvest_candidates", side_effect=AssertionError("candidate discovery should not run")))
                readiness = certification.validate_autonomous_pdf_readiness("pdf_img", 1, root=root)
        self.assertEqual(readiness["document_class"], "unsupported_image_only_pdf")
        self.assertIn("ocr_required_but_not_supported", readiness["blockers"])

    def test_stale_revision_or_cross_document_provenance_blocks_run(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _source_record(root, "pdf_a", 1)
            _manifest(root, "pdf_a", 1)
            with self._patch_ready_dependencies():
                plan = certification.build_autonomous_pdf_plan("pdf_a", 1, root=root)
            _manifest(root, "pdf_a", 2, fingerprint="sha256:manifest_pdf_a_rev2")
            stale = certification.run_autonomous_pdf_pipeline(plan["autonomous_plan_id"], confirmation="AUTO_RUN", root=root)
        self.assertEqual(stale["status"], "stale")
        self.assertIn("source_revision_changed", stale["blockers"])

    def test_ambiguous_or_near_duplicate_evidence_is_preserved_as_blocked(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _source_record(root, "pdf_a", 1)
            _manifest(root, "pdf_a", 1)
            candidate = {"candidate_id": "cand_blocked", "document_id": "pdf_a", "source_revision": 1, "ambiguous": True}
            with self._patch_ready_dependencies(candidates=[candidate]):
                plan = certification.build_autonomous_pdf_plan("pdf_a", 1, root=root)
                run = certification.run_autonomous_pdf_pipeline(plan["autonomous_plan_id"], confirmation="AUTO_RUN", root=root)
        self.assertEqual(run["status"], "completed_with_blocked_items")
        self.assertEqual(run["blocked_item_count"], 1)
        self.assertEqual(run["blocked_items"][0]["blocker"], "ambiguous_or_near_duplicate_evidence")

    def test_runtime_failure_triggers_verified_existing_rollback(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _source_record(root, "pdf_a", 1)
            _manifest(root, "pdf_a", 1)
            candidate = {"candidate_id": "cand_runtime", "document_id": "pdf_a", "source_revision": 1, "structured_rule_ready": True}
            with self._patch_ready_dependencies(candidates=[candidate]) as stack:
                stack.enter_context(patch.object(certification, "_create_or_reuse_citation", return_value={"citation_id": "citation_runtime"}))
                stack.enter_context(patch.object(certification, "_complete_evidence_handoff", return_value={"proposal_id": "proposal_runtime"}))
                stack.enter_context(patch.object(certification, "_create_or_reuse_proposal", return_value={"proposal_id": "proposal_runtime", "structured_rule_ready": True}))
                stack.enter_context(patch.object(certification, "_promote_proposal", return_value={"promotion_receipt_id": "promotion_runtime"}))
                stack.enter_context(patch.object(certification, "_activate_rule", return_value={"activation_receipt_id": "activation_runtime", "revalidation_id": "revalidation_runtime"}))
                stack.enter_context(patch.object(certification, "run_rule_runtime_contract_validation", return_value={"status": "failed"}))
                stack.enter_context(patch.object(certification, "rollback_proposal_rule_activation", return_value={"status": "rollback_completed"}))
                run = certification.run_autonomous_pdf_pipeline(certification.build_autonomous_pdf_plan("pdf_a", 1, root=root)["autonomous_plan_id"], confirmation="AUTO_RUN", root=root)
        self.assertEqual(run["status"], "completed_with_blocked_items")
        self.assertEqual(run["blocked_items"][0]["blocker"], "runtime_contract_case_failed")

    def test_refresh_stages_uses_workflow_plan_execution_contract(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _source_record(root, "pdf_a", 1)
            _manifest(root, "pdf_a", 1)
            with self._patch_ready_dependencies() as stack:
                stage_calls = [{"recommended_stage": "build_structure_map"}, {"recommended_stage": "none"}]
                recommend_mock = stack.enter_context(patch.object(certification, "recommend_next_source_workflow_stage", side_effect=stage_calls))
                plan_mock = stack.enter_context(patch.object(certification, "create_source_workflow_plan", return_value={"workflow_plan_id": "wf_1"}))
                execute_mock = stack.enter_context(patch.object(certification, "execute_source_workflow_stage", return_value={"status": "completed"}))
                plan = certification.build_autonomous_pdf_plan("pdf_a", 1, root=root)
                run = certification.run_autonomous_pdf_pipeline(plan["autonomous_plan_id"], confirmation="AUTO_RUN", root=root)
        self.assertEqual(run["status"], "no_rule_candidates")
        recommend_mock.assert_called()
        plan_mock.assert_called_once_with("pdf_a", requested_stage="build_structure_map", dry_run=False, root=root)
        execute_mock.assert_called_once_with("wf_1", dry_run=False, root=root)

    def test_rollback_failure_stops_run_without_ordinary_completion(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _source_record(root, "pdf_a", 1)
            _manifest(root, "pdf_a", 1)
            candidate = {"candidate_id": "cand_rollback", "document_id": "pdf_a", "source_revision": 1, "structured_rule_ready": True}
            with self._patch_ready_dependencies(candidates=[candidate]) as stack:
                stack.enter_context(patch.object(certification, "_create_or_reuse_citation", return_value={"citation_id": "citation_rollback"}))
                stack.enter_context(patch.object(certification, "_complete_evidence_handoff", return_value={"proposal_id": "proposal_rollback"}))
                stack.enter_context(patch.object(certification, "_create_or_reuse_proposal", return_value={"proposal_id": "proposal_rollback", "structured_rule_ready": True}))
                stack.enter_context(patch.object(certification, "_promote_proposal", return_value={"promotion_receipt_id": "promotion_rollback"}))
                stack.enter_context(patch.object(certification, "_activate_rule", return_value={"activation_receipt_id": "activation_rollback", "revalidation_id": "revalidation_rollback"}))
                stack.enter_context(patch.object(certification, "_validate_and_certify_rule", return_value={"rollback_failed": True}))
                plan = certification.build_autonomous_pdf_plan("pdf_a", 1, root=root)
                run = certification.run_autonomous_pdf_pipeline(plan["autonomous_plan_id"], confirmation="AUTO_RUN", root=root)
        self.assertEqual(run["status"], "rollback_failed")
        self.assertIn("critical_recovery_failure", run["blockers"])
        self.assertTrue(str(run.get("autonomous_receipt_id") or "").startswith("autonomous_pdf_receipt_"))

    def test_api_autonomous_flow_idempotency_health_and_public_report(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            _source_record(root, "pdf_a", 1)
            _manifest(root, "pdf_a", 1)
            candidate = {"candidate_id": "cand_api", "document_id": "pdf_a", "source_revision": 1, "structured_rule_ready": True}
            with self._patch_ready_dependencies(candidates=[candidate]) as stack:
                stack.enter_context(patch.object(certification, "_create_or_reuse_citation", return_value={"citation_id": "citation_api"}))
                stack.enter_context(patch.object(certification, "_complete_evidence_handoff", return_value={"proposal_id": "proposal_api"}))
                stack.enter_context(patch.object(certification, "_create_or_reuse_proposal", return_value={"proposal_id": "proposal_api", "structured_rule_ready": True}))
                stack.enter_context(patch.object(certification, "_promote_proposal", return_value={"promotion_receipt_id": "promotion_api"}))
                stack.enter_context(patch.object(certification, "_activate_rule", return_value={"activation_receipt_id": "activation_api", "revalidation_id": "revalidation_api"}))
                stack.enter_context(patch.object(certification, "_validate_and_certify_rule", return_value={"certification_receipt_id": "cert_api"}))
                workspace = api_build_workspace("pdf_a", 1, root=root)
                plan = api_build_plan("pdf_a", 1, root=root)
                first = api_run_pipeline(plan["autonomous_plan_id"], confirmation="AUTO_RUN", root=root)
                second = api_run_pipeline(plan["autonomous_plan_id"], confirmation="AUTO_RUN", root=root)
                health = certification.get_autonomous_pdf_health("pdf_a", root=root)
                report = api_format_report(autonomous_run_id=first["autonomous_run_id"], public_safe=True, root=root)
        self.assertEqual(workspace["document_id"], "pdf_a")
        self.assertEqual(first["status"], "completed")
        self.assertEqual(second["status"], "already_completed")
        self.assertEqual(health["status"], "healthy")
        self.assertIn("Autonomous Single-PDF Certification Report", report)
        self.assertNotIn(str(root), report)
        self.assertNotIn("C:\\private", report)
