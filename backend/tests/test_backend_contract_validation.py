from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import api
from backend.electional.backend_contract_validation import (
    format_backend_contract_validation_report,
    load_backend_contract_validation,
    run_backend_contract_validation,
)
from backend.electional.document_content_map import build_document_content_map
from backend.electional.document_manifest import build_document_manifest
from backend.electional.evidence_binder import build_evidence_binder
from backend.electional.source_document_reader import build_page_diagnostics
from backend.electional.source_knowledge import create_manual_proposal, create_source_citation
from backend.tests.test_document_content_curation import _prepare_source, _write_chunk, _write_structure_map


def _prepare_contract_fixture(root: Path, *, with_topics: bool = False) -> tuple[str, str]:
    record = _prepare_source(root, "contract")
    _write_chunk(root, record.document_id, f"chunk_{record.document_id}_0001", 1, 1, 1, "Authentication overview")
    _write_chunk(root, record.document_id, f"chunk_{record.document_id}_0002", 2, 2, 2, "Authorization details")
    _write_structure_map(root, record.document_id)
    proposal = create_manual_proposal(record.document_id, f"chunk_{record.document_id}_0001", "Reader-safe proposal", root=root / "store")
    create_source_citation(
        record.document_id,
        f"chunk_{record.document_id}_0001",
        "C:/private/file.pdf token=abc",
        quote_excerpt="secret source text",
        root=root / "store",
    )
    build_evidence_binder(proposal.proposal_id, regenerate=True, root=root / "store")
    build_page_diagnostics(record.document_id, regenerate=True, root=root / "store")
    build_document_manifest(record.document_id, regenerate=True, root=root / "store")
    build_document_content_map(record.document_id, topic_terms=["authentication"] if with_topics else [], regenerate=True, root=root / "store")
    if not with_topics:
        content_path = root / "store" / "document_content_maps" / f"{record.document_id}.json"
        payload = json.loads(content_path.read_text(encoding="utf-8"))
        payload["topic_tags"] = []
        for chapter in payload.get("chapters", []):
            for section in chapter.get("sections", []):
                section["topic_tags"] = []
        for section in payload.get("sections", []):
            section["topic_tags"] = []
        content_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return record.document_id, proposal.proposal_id


def _write_receipt(root: Path, document_id: str, execution_id: str, status: str) -> None:
    payload = {
        "schema_version": "locator_migration_execution_receipt_v1",
        "execution_id": execution_id,
        "document_id": document_id,
        "status": status,
        "after_state_hashes": {"citations/example.json": "sha256:abc"},
        "revalidation_queue_item_id": "impact_example",
    }
    path = root / "store" / "locator_migration_execution_receipts" / f"{execution_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class BackendContractValidationTest(TestCase):
    def test_valid_complete_fixture_is_certified(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, _ = _prepare_contract_fixture(root, with_topics=False)
            result = run_backend_contract_validation(document_id, regenerate=True, root=root / "store")
            self.assertEqual(result["validation"]["certification_status"], "certified")
            self.assertTrue(result["validation"]["validation_current"])

    def test_optional_missing_topic_state_allows_warning_certification(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, _ = _prepare_contract_fixture(root, with_topics=True)
            result = run_backend_contract_validation(document_id, regenerate=True, root=root / "store")
            self.assertEqual(result["validation"]["certification_status"], "certified_with_warnings")
            self.assertIn("topic contribution state could not be verified", " ".join(result["validation"]["warnings"]).lower())

    def test_missing_required_page_diagnostics_prevents_certification(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, _ = _prepare_contract_fixture(root, with_topics=False)
            (root / "store" / "page_diagnostics" / f"{document_id}.json").unlink()
            result = run_backend_contract_validation(document_id, regenerate=True, root=root / "store")
            self.assertEqual(result["validation"]["certification_status"], "not_certified")
            self.assertIn("page_diagnostics_present", {item["check_id"] for item in result["validation"]["checks"] if item["status"] == "fail"})

    def test_cross_document_locator_contradiction_blocks_certification(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, _ = _prepare_contract_fixture(root, with_topics=False)
            citation_path = next((root / "store" / "citations").glob("citation_*.json"))
            payload = json.loads(citation_path.read_text(encoding="utf-8"))
            payload["document_id"] = "pdf_other"
            citation_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            result = run_backend_contract_validation(document_id, regenerate=True, root=root / "store")
            self.assertEqual(result["validation"]["certification_status"], "blocked")
            self.assertIn("cross_document_locator_contradictions_absent", {item["check_id"] for item in result["validation"]["checks"] if item["status"] == "blocked"})

    def test_rollback_failed_receipt_blocks_certification(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, _ = _prepare_contract_fixture(root, with_topics=False)
            _write_receipt(root, document_id, "locator_execution_failed", "rollback_failed")
            result = run_backend_contract_validation(document_id, regenerate=True, root=root / "store")
            self.assertEqual(result["validation"]["certification_status"], "blocked")
            self.assertIn("migration_rollback_failures_absent", {item["check_id"] for item in result["validation"]["checks"] if item["status"] == "blocked"})

    def test_validation_becomes_stale_when_document_state_changes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, _ = _prepare_contract_fixture(root, with_topics=False)
            first = run_backend_contract_validation(document_id, regenerate=True, root=root / "store")["validation"]
            create_source_citation(document_id, f"chunk_{document_id}_0002", "new citation", root=root / "store")
            stale = load_backend_contract_validation(first["validation_id"], root=root / "store")["validation"]
            rebuilt = run_backend_contract_validation(document_id, regenerate=False, root=root / "store")["validation"]
            self.assertEqual(stale["certification_status"], "stale")
            self.assertNotEqual(first["validation_id"], rebuilt["validation_id"])

    def test_validation_does_not_modify_subsystem_records(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, proposal_id = _prepare_contract_fixture(root, with_topics=False)
            files = [
                root / "store" / "indexes" / f"{document_id}.json",
                root / "store" / "document_content_maps" / f"{document_id}.json",
                next((root / "store" / "citations").glob("citation_*.json")),
                root / "store" / "evidence_binders" / f"{proposal_id}_evidence_binder.json",
            ]
            before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
            run_backend_contract_validation(document_id, regenerate=True, root=root / "store")
            after = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
            self.assertEqual(before, after)

    def test_api_backend_contract_validation_flow(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document_id, _ = _prepare_contract_fixture(root, with_topics=False)
            plan = api.build_backend_contract_validation_plan(document_id, root=root / "store")
            result = api.run_backend_contract_validation(document_id, regenerate=True, root=root / "store")
            loaded = api.load_backend_contract_validation(result["validation"]["validation_id"], root=root / "store")
            health = api.get_backend_contract_validation_health(document_id, root=root / "store")
            report = api.format_backend_contract_validation_report(validation_id=result["validation"]["validation_id"], public_safe=True, root=root / "store")
            self.assertEqual(plan["document_id"], document_id)
            self.assertEqual(result["validation"]["document_id"], document_id)
            self.assertEqual(loaded["validation"]["validation_id"], result["validation"]["validation_id"])
            self.assertIn(health["status"], {"healthy", "warning", "critical"})
            self.assertIn("Backend Contract Validation Report", report)
            self.assertNotIn("C:/private/file.pdf", report)
            self.assertNotIn("secret source text", report)
            self.assertNotIn("token=abc", report)
