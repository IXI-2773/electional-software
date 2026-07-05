from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import api
from backend.electional.document_manifest import build_document_manifest
from backend.electional.evidence_binder import build_evidence_binder, load_evidence_binder
from backend.electional.locator_migration_execution import (
    build_locator_migration_write_set,
    execute_locator_migration_proposal,
    format_locator_migration_execution_report,
    get_locator_migration_execution_health,
    list_locator_migration_execution_receipts,
    load_locator_migration_execution_receipt,
    rollback_locator_migration_execution,
    validate_locator_migration_execution,
)
from backend.electional.locator_migration_planner import build_locator_migration_plan
from backend.electional.source_impact_analysis import list_source_revalidation_queue
from backend.electional.source_knowledge import create_manual_proposal, create_source_citation
from backend.tests.test_document_content_curation import _build_detected_map


def _prepare_safe_plan(root: Path) -> tuple[str, str, str, Path]:
    record, _ = _build_detected_map(root)
    store = root / "store"
    build_document_manifest(record.document_id, regenerate=True, root=store)
    citation = create_source_citation(record.document_id, f"chunk_{record.document_id}_0001", "migrate note", root=store)
    citation_path = store / "citations" / f"{citation.citation_id}.json"
    payload = json.loads(citation_path.read_text(encoding="utf-8"))
    payload["source_revision"] = 1
    payload["chunk_id"] = "chunk_old_missing"
    payload["page_start"] = 1
    citation_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    build_document_manifest(record.document_id, regenerate=True, root=store)
    plan = build_locator_migration_plan(record.document_id, scope="stale_only", root=store)["plan"]
    proposal = next(item for item in plan["proposals"] if item["classification"] == "safe_candidate")
    return record.document_id, plan["migration_plan_id"], proposal["proposal_id"], citation_path


class LocatorMigrationExecutionTest(TestCase):
    def test_validate_requires_apply_for_live_execution(self) -> None:
        with TemporaryDirectory() as tmp:
            document_id, plan_id, proposal_id, _ = _prepare_safe_plan(Path(tmp))
            dry = validate_locator_migration_execution(plan_id, proposal_id, dry_run=True, root=Path(tmp) / "store")
            live = validate_locator_migration_execution(plan_id, proposal_id, dry_run=False, root=Path(tmp) / "store")
            self.assertTrue(dry["valid"])
            self.assertFalse(dry["confirmation_valid"])
            self.assertFalse(live["valid"])
            self.assertIn("apply_confirmation_required", live["blockers"])
            self.assertEqual(dry["migration_plan_id"], plan_id)
            self.assertIn(document_id, dry["migration_plan_id"])

    def test_write_set_builds_before_and_after_hashes(self) -> None:
        with TemporaryDirectory() as tmp:
            _, plan_id, proposal_id, _ = _prepare_safe_plan(Path(tmp))
            write_set = build_locator_migration_write_set(plan_id, proposal_id, root=Path(tmp) / "store")
            self.assertEqual(len(write_set["record_updates"]), 1)
            self.assertTrue(write_set["record_updates"][0]["before_hash"].startswith("sha256:"))
            self.assertTrue(write_set["record_updates"][0]["after_hash"].startswith("sha256:"))
            self.assertIn("citation_index.json", write_set["indexes_to_update"])

    def test_dry_run_does_not_write_receipts_or_revalidation(self) -> None:
        with TemporaryDirectory() as tmp:
            _, plan_id, proposal_id, citation_path = _prepare_safe_plan(Path(tmp))
            before = citation_path.read_bytes()
            result = execute_locator_migration_proposal(plan_id, proposal_id, dry_run=True, root=Path(tmp) / "store")
            after = citation_path.read_bytes()
            self.assertEqual(before, after)
            self.assertEqual(result["status"], "dry_run")
            self.assertEqual(list_locator_migration_execution_receipts(root=Path(tmp) / "store")["count"], 0)
            self.assertEqual(list_source_revalidation_queue(root=Path(tmp) / "store")["count"], 0)

    def test_live_execution_updates_record_and_creates_receipt(self) -> None:
        with TemporaryDirectory() as tmp:
            document_id, plan_id, proposal_id, citation_path = _prepare_safe_plan(Path(tmp))
            result = execute_locator_migration_proposal(plan_id, proposal_id, dry_run=False, confirmation="APPLY", root=Path(tmp) / "store")
            payload = json.loads(citation_path.read_text(encoding="utf-8"))
            receipt = load_locator_migration_execution_receipt(result["execution_id"], root=Path(tmp) / "store")["receipt"]
            self.assertEqual(result["status"], "completed")
            self.assertEqual(payload["document_id"], document_id)
            self.assertEqual(payload["chunk_id"], f"chunk_{document_id}_0001")
            self.assertTrue(receipt["rollback_available"])
            self.assertEqual(list_source_revalidation_queue(root=Path(tmp) / "store")["count"], 1)

    def test_execution_is_idempotent_after_success(self) -> None:
        with TemporaryDirectory() as tmp:
            _, plan_id, proposal_id, _ = _prepare_safe_plan(Path(tmp))
            first = execute_locator_migration_proposal(plan_id, proposal_id, dry_run=False, confirmation="APPLY", root=Path(tmp) / "store")
            second = execute_locator_migration_proposal(plan_id, proposal_id, dry_run=False, confirmation="APPLY", root=Path(tmp) / "store")
            receipts = list_locator_migration_execution_receipts(root=Path(tmp) / "store")["items"]
            self.assertEqual(first["execution_id"], second["execution_id"])
            self.assertEqual(second["status"], "already_applied")
            self.assertEqual(len(receipts), 1)

    def test_rollback_restores_record_and_marks_receipt(self) -> None:
        with TemporaryDirectory() as tmp:
            _, plan_id, proposal_id, citation_path = _prepare_safe_plan(Path(tmp))
            before = json.loads(citation_path.read_text(encoding="utf-8"))
            executed = execute_locator_migration_proposal(plan_id, proposal_id, dry_run=False, confirmation="APPLY", root=Path(tmp) / "store")
            rolled = rollback_locator_migration_execution(executed["execution_id"], confirmation="ROLLBACK", root=Path(tmp) / "store")
            after = json.loads(citation_path.read_text(encoding="utf-8"))
            receipt = load_locator_migration_execution_receipt(executed["execution_id"], root=Path(tmp) / "store")["receipt"]
            self.assertEqual(rolled["status"], "rollback_completed")
            self.assertEqual(before["chunk_id"], after["chunk_id"])
            self.assertEqual(receipt["status"], "rollback_completed")
            self.assertEqual(list_source_revalidation_queue(root=Path(tmp) / "store")["count"], 2)

    def test_diverged_record_blocks_execution(self) -> None:
        with TemporaryDirectory() as tmp:
            _, plan_id, proposal_id, citation_path = _prepare_safe_plan(Path(tmp))
            payload = json.loads(citation_path.read_text(encoding="utf-8"))
            payload["chunk_id"] = "chunk_diverged"
            citation_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            result = execute_locator_migration_proposal(plan_id, proposal_id, dry_run=False, confirmation="APPLY", root=Path(tmp) / "store")
            self.assertEqual(result["status"], "blocked")
            self.assertIn("locator_before_state_changed", result["blockers"])

    def test_health_and_report_are_public_safe(self) -> None:
        with TemporaryDirectory() as tmp:
            document_id, plan_id, proposal_id, citation_path = _prepare_safe_plan(Path(tmp))
            payload = json.loads(citation_path.read_text(encoding="utf-8"))
            payload["note"] = "C:/private/file.pdf token=abc"
            payload["quote_excerpt"] = "secret excerpt text"
            citation_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            result = execute_locator_migration_proposal(plan_id, proposal_id, dry_run=False, confirmation="APPLY", root=Path(tmp) / "store")
            health = get_locator_migration_execution_health(document_id, root=Path(tmp) / "store")
            report = format_locator_migration_execution_report(execution_id=result["execution_id"], public_safe=True, root=Path(tmp) / "store")
            self.assertIn(health["status"], {"healthy", "warning", "critical"})
            self.assertNotIn("C:/private/file.pdf", report)
            self.assertNotIn("secret excerpt text", report)
            self.assertNotIn("token=abc", report)

    def test_api_wrappers_cover_execution_flow(self) -> None:
        with TemporaryDirectory() as tmp:
            _, plan_id, proposal_id, _ = _prepare_safe_plan(Path(tmp))
            validation = api.validate_locator_migration_execution(plan_id, proposal_id, dry_run=True, root=Path(tmp) / "store")
            executed = api.execute_locator_migration_proposal(plan_id, proposal_id, dry_run=False, confirmation="APPLY", root=Path(tmp) / "store")
            receipt = api.load_locator_migration_execution_receipt(executed["execution_id"], root=Path(tmp) / "store")
            report = api.format_locator_migration_execution_report(execution_id=executed["execution_id"], public_safe=True, root=Path(tmp) / "store")
            rolled = api.rollback_locator_migration_execution(executed["execution_id"], confirmation="ROLLBACK", root=Path(tmp) / "store")
            self.assertTrue(validation["valid"])
            self.assertEqual(executed["status"], "completed")
            self.assertEqual(receipt["status"], "completed")
            self.assertIn("Locator Migration Execution Report", report)
            self.assertEqual(rolled["status"], "rollback_completed")

    def test_execution_updates_and_rollback_restores_binder_locator_snapshot(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            store = root / "store"
            build_document_manifest(record.document_id, regenerate=True, root=store)
            proposal = create_manual_proposal(record.document_id, f"chunk_{record.document_id}_0001", "Binder linked proposal", root=store)
            citation = create_source_citation(record.document_id, f"chunk_{record.document_id}_0001", f"binder note {proposal.proposal_id}", root=store)
            citation_path = store / "citations" / f"{citation.citation_id}.json"
            payload = json.loads(citation_path.read_text(encoding="utf-8"))
            payload["source_revision"] = 1
            payload["chunk_id"] = "chunk_old_missing"
            payload["page_start"] = 1
            citation_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            build_evidence_binder(proposal.proposal_id, regenerate=True, root=store)
            plan = build_locator_migration_plan(record.document_id, scope="stale_only", root=store)["plan"]
            proposal_item = next(item for item in plan["proposals"] if item["record_id"] == citation.citation_id)
            before_binder = load_evidence_binder(proposal.proposal_id, root=store)
            self.assertEqual(before_binder["linked_citations"][0]["chunk_id"], "chunk_old_missing")
            executed = execute_locator_migration_proposal(plan["migration_plan_id"], proposal_item["proposal_id"], dry_run=False, confirmation="APPLY", root=store)
            after_binder = load_evidence_binder(proposal.proposal_id, root=store)
            self.assertEqual(executed["embedded_dependencies_updated"], 1)
            self.assertEqual(after_binder["linked_citations"][0]["chunk_id"], f"chunk_{record.document_id}_0001")
            rolled = rollback_locator_migration_execution(executed["execution_id"], confirmation="ROLLBACK", root=store)
            rolled_binder = load_evidence_binder(proposal.proposal_id, root=store)
            self.assertEqual(rolled["status"], "rollback_completed")
            self.assertEqual(rolled_binder["linked_citations"][0]["chunk_id"], "chunk_old_missing")
