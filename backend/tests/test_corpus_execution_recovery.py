from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

from backend.electional import api
from backend.electional import corpus_execution_recovery as cer
from backend.electional.source_corpus_manager import create_corpus_batch_plan
from backend.electional.source_documents import extract_pdf_text, register_pdf_source
from backend.electional.source_knowledge import chunk_extracted_text


def _register(root: Path, name: str):
    pdf = root / f"{name}.pdf"
    pdf.write_bytes(f"%PDF-1.4\n{name}\n%%EOF".encode("utf-8"))
    return register_pdf_source(pdf, root=root / "store")


def _extracted(root: Path, name: str, text: str = "Manual review source text with citation support. " * 8):
    record = _register(root, name)
    extract_pdf_text(record.document_id, root=root / "store", extractor=lambda _path: ([text], 1))
    chunks = chunk_extracted_text(record.document_id, root=root / "store")
    return record, chunks


class CorpusExecutionRecoveryTest(TestCase):
    def test_failure_classification_missing_step(self) -> None:
        self.assertEqual(cer.classify_corpus_execution_failure(attempted=False), "missing_step")

    def test_failure_classification_processing_failure(self) -> None:
        self.assertEqual(cer.classify_corpus_execution_failure(attempted=True, exception=RuntimeError("boom")), "processing_failure")

    def test_missing_step_not_listed_as_processing_failure(self) -> None:
        classification = cer.classify_corpus_execution_failure(attempted=False)
        self.assertEqual(classification, "missing_step")
        self.assertNotEqual(classification, "processing_failure")

    def test_dependency_validation_blocks_missing_extraction(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            result = cer.validate_batch_action_dependencies(record.document_id, "chunk_text", root=root / "store")
            self.assertFalse(result["allowed"])
            self.assertIn("extracted_text", result["missing_dependencies"])
            self.assertIn("dependency_missing", result["blockers"])

    def test_dependency_validation_does_not_run_prerequisite(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            cer.validate_batch_action_dependencies(record.document_id, "chunk_text", root=root / "store")
            self.assertEqual(len(list((root / "store" / "extracted_text").glob("*.txt"))), 0)

    def test_execution_config_uses_safe_defaults(self) -> None:
        config = cer.validate_corpus_execution_config({})
        self.assertTrue(config["default_dry_run"])
        self.assertTrue(config["require_backup_before_repair"])
        self.assertEqual(config["maximum_retries"], 2)

    def test_batch_lock_prevents_concurrent_execution(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            cer.acquire_corpus_batch_lock("batch_one", root=root)
            with self.assertRaises(RuntimeError):
                cer.acquire_corpus_batch_lock("batch_one", root=root)

    def test_stale_lock_detection_does_not_auto_clear(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            cer.acquire_corpus_batch_lock("batch_one", root=root)
            lock_path = root / "corpus_execution_locks" / "batch_one.json"
            payload = json.loads(lock_path.read_text(encoding="utf-8"))
            payload["heartbeat_at_utc"] = "2000-01-01T00:00:00Z"
            lock_path.write_text(json.dumps(payload), encoding="utf-8")
            stale = cer.detect_stale_corpus_batch_lock("batch_one", root=root)
            active = cer.get_corpus_batch_lock("batch_one", root=root)
            self.assertTrue(stale["stale"])
            self.assertEqual(active["status"], "active")

    def test_idempotency_key_is_stable(self) -> None:
        key1 = cer.build_execution_idempotency_key("doc_a", "detect_missing_steps", {"document_hash": "sha256:x"}, {"dry_run": False})
        key2 = cer.build_execution_idempotency_key("doc_a", "detect_missing_steps", {"document_hash": "sha256:x"}, {"dry_run": False})
        self.assertEqual(key1, key2)

    def test_completed_receipt_prevents_duplicate_execution(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            plan = create_corpus_batch_plan("detect_missing_steps", [record.document_id], root=root / "store")
            cer.execute_corpus_batch_plan(plan["batch_id"], dry_run=False, root=root / "store")
            result = cer.execute_corpus_batch_plan(plan["batch_id"], dry_run=False, root=root / "store")
            self.assertEqual(result["already_completed"], 1)

    def test_force_execution_links_prior_receipt(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            plan = create_corpus_batch_plan("detect_missing_steps", [record.document_id], root=root / "store")
            cer.execute_corpus_batch_plan(plan["batch_id"], dry_run=False, root=root / "store")
            cer.execute_corpus_batch_plan(plan["batch_id"], dry_run=False, force=True, root=root / "store")
            receipts = cer.list_execution_receipts(batch_id=plan["batch_id"], root=root / "store")["receipts"]
            self.assertTrue(receipts[0]["prior_receipt_id"])

    def test_started_receipt_created_before_action(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            plan = create_corpus_batch_plan("detect_missing_steps", [record.document_id], root=root / "store")
            seen = {}

            def fake_execute(action: str, document_id: str, store_root: Path) -> dict[str, object]:
                receipts = cer.list_execution_receipts(batch_id=plan["batch_id"], root=store_root)["receipts"]
                seen["started"] = any(item["status"] == "started" for item in receipts)
                return {"output_summary": {"ok": True}, "output_hashes": {}, "warnings": []}

            with mock.patch.object(cer, "_execute_action", side_effect=fake_execute):
                cer.execute_corpus_batch_plan(plan["batch_id"], dry_run=False, root=root / "store")
            self.assertTrue(seen["started"])

    def test_failed_action_finalizes_failed_receipt(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            plan = create_corpus_batch_plan("detect_missing_steps", [record.document_id], root=root / "store")
            with mock.patch.object(cer, "_execute_action", side_effect=RuntimeError("boom")):
                cer.execute_corpus_batch_plan(plan["batch_id"], dry_run=False, root=root / "store")
            receipts = cer.list_execution_receipts(batch_id=plan["batch_id"], root=root / "store")["receipts"]
            self.assertEqual(receipts[0]["status"], "failed")

    def test_batch_execution_writes_checkpoint(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            plan = create_corpus_batch_plan("detect_missing_steps", [record.document_id], root=root / "store")
            cer.execute_corpus_batch_plan(plan["batch_id"], dry_run=False, root=root / "store")
            checkpoint = cer.load_corpus_checkpoint(plan["batch_id"], root=root / "store")
            self.assertTrue(checkpoint["checkpoint_id"])

    def test_checkpoint_checksum_validation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            plan = create_corpus_batch_plan("detect_missing_steps", [record.document_id], root=root / "store")
            cer.execute_corpus_batch_plan(plan["batch_id"], dry_run=False, root=root / "store")
            valid = cer.validate_corpus_checkpoint(plan["batch_id"], root=root / "store")
            self.assertTrue(valid["valid"])
            checkpoint_path = root / "store" / "corpus_checkpoints" / f"{plan['batch_id']}.json"
            payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            payload["checksum"] = "sha256:bad"
            checkpoint_path.write_text(json.dumps(payload), encoding="utf-8")
            self.assertFalse(cer.validate_corpus_checkpoint(plan["batch_id"], root=root / "store")["valid"])

    def test_resume_skips_completed_receipts(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            plan = create_corpus_batch_plan("detect_missing_steps", [record.document_id], root=root / "store")
            cer.execute_corpus_batch_plan(plan["batch_id"], dry_run=False, root=root / "store")
            before = cer.list_execution_receipts(batch_id=plan["batch_id"], root=root / "store")["count"]
            cer.resume_corpus_batch_plan(plan["batch_id"], dry_run=False, root=root / "store")
            after = cer.list_execution_receipts(batch_id=plan["batch_id"], root=root / "store")["count"]
            self.assertEqual(before, after)

    def test_resume_can_retry_interrupted_item(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            plan = create_corpus_batch_plan("detect_missing_steps", [record.document_id], root=root / "store")
            started = cer.create_started_execution_receipt(
                batch_id=plan["batch_id"],
                document_id=record.document_id,
                action="detect_missing_steps",
                attempt_number=1,
                idempotency_key="sha256:test",
                root=root / "store",
            )
            receipt_path = root / "store" / "corpus_execution_receipts" / f"{started['receipt_id']}.json"
            payload = json.loads(receipt_path.read_text(encoding="utf-8"))
            payload["started_at_utc"] = "2000-01-01T00:00:00Z"
            receipt_path.write_text(json.dumps(payload), encoding="utf-8")
            cer.mark_stale_executions_interrupted(plan["batch_id"], explicit=True, root=root / "store")
            result = cer.resume_corpus_batch_plan(plan["batch_id"], dry_run=False, retry_failures=True, root=root / "store")
            self.assertEqual(result["completed"], 1)

    def test_retry_budget_blocks_excess_retries(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            plan = create_corpus_batch_plan("detect_missing_steps", [record.document_id], root=root / "store")
            with mock.patch.object(cer, "_execute_action", side_effect=RuntimeError("boom")):
                cer.execute_corpus_batch_plan(plan["batch_id"], dry_run=False, retry_failures=True, force=True, root=root / "store")
                cer.execute_corpus_batch_plan(plan["batch_id"], dry_run=False, retry_failures=True, force=True, root=root / "store")
                result = cer.execute_corpus_batch_plan(plan["batch_id"], dry_run=False, retry_failures=True, root=root / "store")
            self.assertEqual(result["blocked"], 1)

    def test_cancel_preserves_checkpoint_and_receipts(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            plan = create_corpus_batch_plan("detect_missing_steps", [record.document_id], root=root / "store")
            cer.execute_corpus_batch_plan(plan["batch_id"], dry_run=False, root=root / "store")
            cer.cancel_corpus_batch_plan(plan["batch_id"], note="stop", root=root / "store")
            state = cer.get_batch_recovery_state(plan["batch_id"], root=root / "store")
            checkpoint = cer.load_corpus_checkpoint(plan["batch_id"], root=root / "store")
            receipts = cer.list_execution_receipts(batch_id=plan["batch_id"], root=root / "store")
            self.assertEqual(state["status"], "cancelled")
            self.assertTrue(checkpoint["checkpoint_id"])
            self.assertEqual(receipts["count"], 1)

    def test_stale_started_receipt_detected(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            started = cer.create_started_execution_receipt(
                batch_id="batch_one",
                document_id="doc_one",
                action="detect_missing_steps",
                attempt_number=1,
                idempotency_key="sha256:test",
                root=root / "store",
            )
            receipt_path = root / "store" / "corpus_execution_receipts" / f"{started['receipt_id']}.json"
            payload = json.loads(receipt_path.read_text(encoding="utf-8"))
            payload["started_at_utc"] = "2000-01-01T00:00:00Z"
            receipt_path.write_text(json.dumps(payload), encoding="utf-8")
            stale = cer.detect_stale_executions(root=root / "store")
            self.assertEqual(stale["stale_count"], 1)

    def test_execution_history_uses_receipts(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            plan = create_corpus_batch_plan("detect_missing_steps", [record.document_id], root=root / "store")
            cer.execute_corpus_batch_plan(plan["batch_id"], dry_run=False, root=root / "store")
            history = cer.get_corpus_execution_history(batch_id=plan["batch_id"], root=root / "store")
            self.assertEqual(history["receipt_count"], 1)

    def test_index_registry_is_allowlisted(self) -> None:
        registry = cer.get_corpus_index_registry()
        self.assertIn("chunk_index", registry)
        self.assertNotIn("random_folder_scan", registry)

    def test_integrity_validation_detects_invalid_json(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            cer.ensure_corpus_execution_dirs(root)
            chunk_index = root / "indexes" / "chunk_index.json"
            chunk_index.write_text("{bad json", encoding="utf-8")
            result = cer.validate_single_index_integrity("chunk_index", root=root)
            self.assertEqual(result["severity"], "critical")
            self.assertEqual(result["issues"][0]["code"], "invalid_json")

    def test_integrity_validation_detects_missing_record(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _record, chunks = _extracted(root, "a")
            chunk_path = root / "store" / "chunks" / f"{chunks[0].chunk_id}.json"
            chunk_path.unlink()
            result = cer.validate_single_index_integrity("chunk_index", root=root / "store")
            self.assertTrue(any(item["code"] == "missing_record" for item in result["issues"]))

    def test_integrity_validation_detects_unindexed_record(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _record, chunks = _extracted(root, "a")
            index_path = root / "store" / "indexes" / "chunk_index.json"
            index_path.write_text(json.dumps({"entries": []}), encoding="utf-8")
            result = cer.validate_single_index_integrity("chunk_index", root=root / "store")
            self.assertTrue(any(item["code"] == "unindexed_record" for item in result["issues"]))

    def test_integrity_validation_detects_duplicate_id(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _record, chunks = _extracted(root, "a")
            index_path = root / "store" / "indexes" / "chunk_index.json"
            payload = json.loads(index_path.read_text(encoding="utf-8"))
            payload["entries"].append(dict(payload["entries"][0]))
            index_path.write_text(json.dumps(payload), encoding="utf-8")
            result = cer.validate_single_index_integrity("chunk_index", root=root / "store")
            self.assertTrue(any(item["code"] == "duplicate_index_entry" for item in result["issues"]))

    def test_integrity_validation_does_not_mutate(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _record, _chunks = _extracted(root, "a")
            index_path = root / "store" / "indexes" / "chunk_index.json"
            before = index_path.read_text(encoding="utf-8")
            cer.validate_single_index_integrity("chunk_index", root=root / "store")
            after = index_path.read_text(encoding="utf-8")
            self.assertEqual(before, after)

    def test_repair_plan_defaults_to_dry_run(self) -> None:
        with TemporaryDirectory() as tmp:
            plan = cer.build_corpus_repair_plan(dry_run=True, root=Path(tmp) / "store")
            self.assertTrue(plan["dry_run"])

    def test_repair_plan_contains_before_after_preview(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _record, _chunks = _extracted(root, "a")
            plan = cer.build_corpus_repair_plan(index_names=["chunk_index"], root=root / "store")
            self.assertIn("before_entries", plan["items"][0])
            self.assertIn("planned_after_entries", plan["items"][0])

    def test_non_dry_run_repair_requires_backup(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _record, _chunks = _extracted(root, "a")
            plan = cer.build_corpus_repair_plan(index_names=["chunk_index"], root=root / "store")
            result = cer.execute_corpus_repair_plan(plan["repair_id"], dry_run=False, root=root / "store")
            self.assertEqual(result["status"], "blocked")

    def test_backup_manifest_contains_hashes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _record, _chunks = _extracted(root, "a")
            plan = cer.build_corpus_repair_plan(index_names=["chunk_index"], root=root / "store")
            backup = cer.create_corpus_repair_backup(plan["repair_id"], root=root / "store")
            self.assertTrue(backup["files"][0]["sha256"].startswith("sha256:"))

    def test_backup_verification_failure_blocks_repair(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _record, _chunks = _extracted(root, "a")
            plan = cer.build_corpus_repair_plan(index_names=["chunk_index"], root=root / "store")
            backup = cer.create_corpus_repair_backup(plan["repair_id"], root=root / "store")
            backup_file = root / "store" / "corpus_repair_backups" / backup["backup_id"] / backup["files"][0]["filename"]
            backup_file.write_text("corrupted", encoding="utf-8")
            result = cer.execute_corpus_repair_plan(plan["repair_id"], dry_run=False, root=root / "store")
            self.assertEqual(result["status"], "blocked")

    def test_quarantine_preserves_record_bytes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _record, chunks = _extracted(root, "a")
            chunk_path = root / "store" / "chunks" / f"{chunks[0].chunk_id}.json"
            before = chunk_path.read_bytes()
            quarantined = cer.quarantine_corrupt_corpus_record("chunk", chunks[0].chunk_id, "test", root=root / "store")
            stored = root / "store" / "corpus_quarantine" / "chunk" / quarantined["stored_name"]
            self.assertEqual(before, stored.read_bytes())

    def test_repair_builds_staged_index(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _record, _chunks = _extracted(root, "a")
            plan = cer.build_corpus_repair_plan(index_names=["chunk_index"], root=root / "store")
            cer.create_corpus_repair_backup(plan["repair_id"], root=root / "store")
            result = cer.execute_corpus_repair_plan(plan["repair_id"], dry_run=False, root=root / "store")
            self.assertEqual(result["status"], "completed")

    def test_repair_validates_before_atomic_replace(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _record, _chunks = _extracted(root, "a")
            plan = cer.build_corpus_repair_plan(index_names=["chunk_index"], root=root / "store")
            cer.create_corpus_repair_backup(plan["repair_id"], root=root / "store")
            with mock.patch.object(cer, "_validate_staged_index_payload", return_value={"valid": False}):
                result = cer.execute_corpus_repair_plan(plan["repair_id"], dry_run=False, root=root / "store")
            self.assertEqual(result["status"], "blocked")

    def test_failed_live_validation_triggers_rollback(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _record, _chunks = _extracted(root, "a")
            plan = cer.build_corpus_repair_plan(index_names=["chunk_index"], root=root / "store")
            cer.create_corpus_repair_backup(plan["repair_id"], root=root / "store")
            with mock.patch.object(cer, "validate_single_index_integrity", return_value={"severity": "critical"}):
                result = cer.execute_corpus_repair_plan(plan["repair_id"], dry_run=False, root=root / "store")
            self.assertEqual(result["status"], "rollback_required")

    def test_rollback_restores_verified_backup(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _record, _chunks = _extracted(root, "a")
            plan = cer.build_corpus_repair_plan(index_names=["chunk_index"], root=root / "store")
            backup = cer.create_corpus_repair_backup(plan["repair_id"], root=root / "store")
            index_path = root / "store" / "indexes" / "chunk_index.json"
            index_path.write_text(json.dumps({"entries": []}), encoding="utf-8")
            result = cer.rollback_corpus_repair(plan["repair_id"], explicit=True, root=root / "store")
            restored_hash = cer.verify_corpus_repair_backup(backup["backup_id"], root=root / "store")
            self.assertEqual(result["status"], "rolled_back")
            self.assertTrue(restored_hash["verified"])

    def test_partial_write_detection(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            cer.ensure_corpus_execution_dirs(root)
            tmp_file = root / "indexes" / ".chunk_index.json.tmp"
            tmp_file.write_text("{}", encoding="utf-8")
            detected = cer.detect_partial_corpus_writes(root=root)
            self.assertEqual(detected["count"], 1)

    def test_public_execution_report_hides_private_paths(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            plan = create_corpus_batch_plan("detect_missing_steps", [record.document_id], root=root / "store")
            cer.execute_corpus_batch_plan(plan["batch_id"], dry_run=False, root=root / "store")
            report = cer.format_corpus_execution_report_text(plan["batch_id"], public_safe=True, root=root / "store")
            self.assertNotIn(str(root), report)

    def test_api_corpus_execution_recovery_flow(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = _register(root, "a")
            plan = api.create_corpus_batch_plan("detect_missing_steps", [record.document_id], root=root / "store")
            api.execute_corpus_batch_plan(plan["batch_id"], dry_run=False, root=root / "store")
            history = api.get_corpus_execution_history(batch_id=plan["batch_id"], root=root / "store")
            integrity = api.validate_corpus_index_integrity(root=root / "store")
            self.assertEqual(history["receipt_count"], 1)
            self.assertIn("healthy_index_count", integrity)
