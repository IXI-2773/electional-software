from __future__ import annotations

import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

import backend.electional.document_content_integrity as integrity
from backend.electional.document_content_bulk import (
    add_document_content_bulk_operation,
    approve_document_content_bulk_plan,
    commit_document_content_bulk_plan,
    create_document_content_bulk_plan,
    preview_document_content_bulk_plan,
)
from backend.electional.document_content_curation import load_document_content_curation, save_document_content_curation_change
from backend.electional.document_content_history import list_document_content_curation_revisions, restore_document_content_curation_revision
from backend.electional.document_content_rebase import (
    apply_document_content_rebase_resolution,
    commit_document_content_rebase_workspace,
    create_rebase_workspace_from_current_stale_curation,
    refresh_document_content_rebase_conflicts,
)
from backend.tests.test_document_content_curation import _build_detected_map


class DocumentContentIntegrityTest(TestCase):
    def tearDown(self) -> None:
        integrity._FAIL_STAGE_HOOK = None

    def _tx_id(self, document_id: str, root: Path) -> str:
        listing = integrity.list_document_content_transactions(document_id, root=root)
        self.assertEqual(listing["count"], 1)
        return str(listing["items"][0]["transaction_id"])

    def _tx_path(self, document_id: str, transaction_id: str, root: Path) -> Path:
        return root / integrity.TRANSACTION_DIR / document_id / f"{transaction_id}.json"

    def _save_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def test_transaction_statuses_are_first_class(self) -> None:
        cases = [
            ("prepared", "curation_before_overlay", "curation_change"),
            ("overlay_written", "curation_after_overlay", "curation_change"),
            ("history_written", "curation_after_history", "curation_change"),
            ("source_status_written", "bulk_after_source_status", "bulk_commit"),
        ]
        for expected, fail_stage, flow in cases:
            with self.subTest(expected=expected):
                with TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    record, _ = _build_detected_map(root)

                    def fail(stage: str) -> None:
                        if stage == fail_stage:
                            raise RuntimeError("boom")

                    integrity._FAIL_STAGE_HOOK = fail
                    if flow == "curation_change":
                        with self.assertRaises(RuntimeError):
                            save_document_content_curation_change(
                                record.document_id,
                                {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}},
                                root=root / "store",
                            )
                    else:
                        plan = create_document_content_bulk_plan(record.document_id, root=root / "store")
                        add_document_content_bulk_operation(
                            record.document_id,
                            plan["batch_id"],
                            {"operation_type": "rename_sections", "renames": {"section_001_001": "Authentication Factors Two"}},
                            root=root / "store",
                        )
                        preview_document_content_bulk_plan(record.document_id, plan["batch_id"], root=root / "store")
                        approve_document_content_bulk_plan(record.document_id, plan["batch_id"], root=root / "store")
                        with self.assertRaises(RuntimeError):
                            commit_document_content_bulk_plan(record.document_id, plan["batch_id"], root=root / "store")
                    integrity._FAIL_STAGE_HOOK = None
                    tx_id = self._tx_id(record.document_id, root / "store")
                    status = integrity.get_document_content_transaction_status(record.document_id, tx_id, root=root / "store")
                    self.assertEqual(status["status"], expected)

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            save_document_content_curation_change(
                record.document_id,
                {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}},
                root=root / "store",
            )
            tx_id = self._tx_id(record.document_id, root / "store")
            self.assertEqual(integrity.get_document_content_transaction_status(record.document_id, tx_id, root=root / "store")["status"], "committed")
            tx_path = self._tx_path(record.document_id, tx_id, root / "store")
            payload = json.loads(tx_path.read_text(encoding="utf-8"))
            payload["transaction_status"] = "indexes_reconciled"
            self._save_json(tx_path, payload)
            self.assertEqual(integrity.get_document_content_transaction_status(record.document_id, tx_id, root=root / "store")["status"], "indexes_reconciled")
            payload["schema_version"] = "legacy_v0"
            self._save_json(tx_path, payload)
            self.assertEqual(integrity.get_document_content_transaction_status(record.document_id, tx_id, root=root / "store")["status"], "unknown")

    def test_recovery_persists_recovering_and_recovered_and_keeps_retry_idempotent(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)

            def fail(stage: str) -> None:
                if stage == "curation_after_overlay":
                    raise RuntimeError("boom")

            integrity._FAIL_STAGE_HOOK = fail
            with self.assertRaises(RuntimeError):
                save_document_content_curation_change(
                    record.document_id,
                    {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}},
                    root=root / "store",
                )
            integrity._FAIL_STAGE_HOOK = None
            plan = integrity.create_document_content_recovery_plan(record.document_id, root=root / "store")
            seen_statuses: list[str] = []
            original_action = integrity._apply_recovery_action

            def wrapped_action(document_id: str, action: dict[str, object], store_root: Path) -> dict[str, object]:
                loaded_plan = integrity.load_document_content_recovery_plan(document_id, plan["plan_id"], root=store_root)
                seen_statuses.append(str((loaded_plan.get("plan") or {}).get("status")))
                return original_action(document_id, action, store_root)

            integrity._apply_recovery_action = wrapped_action
            try:
                applied = integrity.apply_document_content_recovery_plan(record.document_id, plan["plan_id"], root=root / "store")
            finally:
                integrity._apply_recovery_action = original_action
            self.assertIn("recovering", seen_statuses)
            self.assertEqual(applied["status"], "recovered")
            loaded_plan = integrity.load_document_content_recovery_plan(record.document_id, plan["plan_id"], root=root / "store")
            self.assertEqual(loaded_plan["plan"]["status"], "recovered")
            tx_id = self._tx_id(record.document_id, root / "store")
            self.assertEqual(integrity.get_document_content_transaction_status(record.document_id, tx_id, root=root / "store")["status"], "recovered")

            retry = save_document_content_curation_change(
                record.document_id,
                {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}},
                root=root / "store",
            )
            self.assertEqual(retry["status"], "unchanged")

    def test_transaction_finalization_refuses_incomplete_journal(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)

            def fail(stage: str) -> None:
                if stage == "curation_after_overlay":
                    raise RuntimeError("boom")

            integrity._FAIL_STAGE_HOOK = fail
            with self.assertRaises(RuntimeError):
                save_document_content_curation_change(
                    record.document_id,
                    {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}},
                    root=root / "store",
                )
            integrity._FAIL_STAGE_HOOK = None
            tx_id = self._tx_id(record.document_id, root / "store")
            finalized = integrity.finalize_document_content_transaction(record.document_id, tx_id, "committed", root=root / "store")
            self.assertEqual(finalized["status"], "conflict")
            self.assertIn("transaction_checkpoints_incomplete", finalized["blockers"])
            status = integrity.get_document_content_transaction_status(record.document_id, tx_id, root=root / "store")
            self.assertEqual(status["status"], "overlay_written")

    def test_unsafe_transaction_identifier_is_rejected_before_any_write(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            result = integrity.prepare_document_content_transaction(
                "curation_change",
                f"../{record.document_id}_escape",
                expected_previous_revision=0,
                expected_new_revision=1,
                base_content_map_fingerprint="sha256:test",
                source_revision=1,
                proposed_overlay_state={"document_id": record.document_id, "curation_revision": 1},
                root=root / "store",
            )
            self.assertEqual(result["status"], "invalid")
            self.assertIn("unsafe_identifier", result["blockers"])
            self.assertFalse((root / f"{record.document_id}_escape").exists())

    def test_overlay_revision_behind_history_and_duplicate_history_conflicts_are_detected(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            save_document_content_curation_change(record.document_id, {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}}, root=root / "store")
            save_document_content_curation_change(record.document_id, {"target_type": "section", "target_id": "section_001_001", "operation": "rename", "value": {"title": "Authentication Factors"}}, root=root / "store")
            overlay_path = root / "store" / "document_content_curation" / f"{record.document_id}.json"
            overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
            overlay["curation_revision"] = 1
            self._save_json(overlay_path, overlay)

            history_one = integrity._history_revision_path(root / "store", record.document_id, 1)
            duplicate_same = root / "store" / "document_content_curation_history" / record.document_id / "101.json"
            duplicate_conflict = root / "store" / "document_content_curation_history" / record.document_id / "102.json"
            same_payload = json.loads(history_one.read_text(encoding="utf-8"))
            conflict_payload = copy.deepcopy(same_payload)
            conflict_payload["overlay"]["chapter_title_overrides"] = {"chapter_001": "Different"}
            conflict_payload["integrity_fingerprint"] = "sha256:conflict"
            self._save_json(duplicate_same, same_payload)
            identical_scan = integrity.scan_document_content_integrity(record.document_id, root=root / "store")
            self.assertFalse(any(item["issue_type"] == "duplicate_conflicting_history_revision" for item in identical_scan["issues"]))
            self._save_json(duplicate_conflict, conflict_payload)

            before_overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
            scan = integrity.scan_document_content_integrity(record.document_id, root=root / "store")
            issue_types = {item["issue_type"] for item in scan["issues"]}
            self.assertIn("overlay_revision_behind_history", issue_types)
            self.assertIn("duplicate_conflicting_history_revision", issue_types)
            self.assertEqual(json.loads(overlay_path.read_text(encoding="utf-8")), before_overlay)

            plan = integrity.create_document_content_recovery_plan(record.document_id, root=root / "store")
            self.assertEqual(plan["status"], "manual_review_required")
            self.assertEqual(integrity.apply_document_content_recovery_plan(record.document_id, plan["plan_id"], root=root / "store")["status"], "manual_review_required")

    def test_transaction_missing_workflow_record_and_abandonment_rules(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            prepared = integrity.prepare_document_content_transaction(
                "bulk_commit",
                record.document_id,
                expected_previous_revision=0,
                expected_new_revision=1,
                base_content_map_fingerprint="fp",
                source_revision=1,
                proposed_overlay_state={"document_id": record.document_id, "curation_revision": 1},
                source_workflow_type="bulk_commit",
                source_workflow_id="missing_batch",
                source_workflow_revision=1,
                root=root / "store",
            )
            scan = integrity.scan_document_content_integrity(record.document_id, root=root / "store")
            issue = next(item for item in scan["issues"] if item["issue_type"] == "transaction_missing_workflow_record")
            self.assertEqual(issue["recoverability"], "recoverable")
            abandoned = integrity.abandon_document_content_transaction(record.document_id, prepared["transaction_id"], "safe to abandon", root=root / "store")
            self.assertEqual(abandoned["status"], "abandoned")
            abandoned_again = integrity.abandon_document_content_transaction(record.document_id, prepared["transaction_id"], "safe to abandon", root=root / "store")
            self.assertEqual(abandoned_again["status"], "abandoned")
            self.assertIsNone(load_document_content_curation(record.document_id, root=root / "store")["curation"])
            self.assertEqual(list_document_content_curation_revisions(record.document_id, root=root / "store")["count"], 0)

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)

            def fail(stage: str) -> None:
                if stage == "curation_after_overlay":
                    raise RuntimeError("boom")

            integrity._FAIL_STAGE_HOOK = fail
            with self.assertRaises(RuntimeError):
                save_document_content_curation_change(
                    record.document_id,
                    {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}},
                    root=root / "store",
                )
            integrity._FAIL_STAGE_HOOK = None
            tx_id = self._tx_id(record.document_id, root / "store")
            blocked = integrity.abandon_document_content_transaction(record.document_id, tx_id, root=root / "store")
            self.assertEqual(blocked["status"], "conflict")

    def test_missing_bulk_and_rebase_workflow_records_require_manual_review_after_mutation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            bulk = create_document_content_bulk_plan(record.document_id, root=root / "store")
            add_document_content_bulk_operation(record.document_id, bulk["batch_id"], {"operation_type": "rename_sections", "renames": {"section_001_001": "Authentication Factors Two"}}, root=root / "store")
            preview_document_content_bulk_plan(record.document_id, bulk["batch_id"], root=root / "store")
            approve_document_content_bulk_plan(record.document_id, bulk["batch_id"], root=root / "store")

            def fail_bulk(stage: str) -> None:
                if stage == "bulk_after_history":
                    raise RuntimeError("boom")

            integrity._FAIL_STAGE_HOOK = fail_bulk
            with self.assertRaises(RuntimeError):
                commit_document_content_bulk_plan(record.document_id, bulk["batch_id"], root=root / "store")
            integrity._FAIL_STAGE_HOOK = None
            (root / "store" / "document_content_bulk" / record.document_id / f"{bulk['batch_id']}.json").unlink()
            scan = integrity.scan_document_content_integrity(record.document_id, root=root / "store")
            issue = next(item for item in scan["issues"] if item["issue_type"] == "transaction_missing_workflow_record")
            self.assertEqual(issue["recoverability"], "manual_review_required")
            plan = integrity.create_document_content_recovery_plan(record.document_id, root=root / "store")
            self.assertEqual(plan["status"], "manual_review_required")

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            save_document_content_curation_change(record.document_id, {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}}, root=root / "store")
            overlay_path = root / "store" / "document_content_curation" / f"{record.document_id}.json"
            payload = json.loads(overlay_path.read_text(encoding="utf-8"))
            payload["chapter_title_overrides"]["chapter_missing"] = "Ghost"
            payload["changes"] = []
            self._save_json(overlay_path, payload)
            workspace = create_rebase_workspace_from_current_stale_curation(record.document_id, root=root / "store")["workspace"]
            refreshed = refresh_document_content_rebase_conflicts(record.document_id, workspace["workspace_id"], root=root / "store")
            conflict_id = next(item["conflict_id"] for item in refreshed["workspace"]["conflicts"] if item["conflict_type"] == "missing_chapter")
            apply_document_content_rebase_resolution(record.document_id, workspace["workspace_id"], conflict_id, {"action": "drop"}, root=root / "store")

            def fail_rebase(stage: str) -> None:
                if stage == "rebase_after_history":
                    raise RuntimeError("boom")

            integrity._FAIL_STAGE_HOOK = fail_rebase
            with self.assertRaises(RuntimeError):
                commit_document_content_rebase_workspace(record.document_id, workspace["workspace_id"], root=root / "store")
            integrity._FAIL_STAGE_HOOK = None
            (root / "store" / "document_content_curation_rebase" / record.document_id / f"{workspace['workspace_id']}.json").unlink()
            scan = integrity.scan_document_content_integrity(record.document_id, root=root / "store")
            issue = next(item for item in scan["issues"] if item["issue_type"] == "transaction_missing_workflow_record")
            self.assertEqual(issue["affected_workflow_type"], "rebase_commit")
            self.assertEqual(issue["recoverability"], "manual_review_required")

    def test_recovery_plan_loading_validation_and_stale_rejection(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)

            def fail(stage: str) -> None:
                if stage == "curation_after_overlay":
                    raise RuntimeError("boom")

            integrity._FAIL_STAGE_HOOK = fail
            with self.assertRaises(RuntimeError):
                save_document_content_curation_change(
                    record.document_id,
                    {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}},
                    root=root / "store",
                )
            integrity._FAIL_STAGE_HOOK = None
            plan = integrity.create_document_content_recovery_plan(record.document_id, root=root / "store")
            loaded = integrity.load_document_content_recovery_plan(record.document_id, plan["plan_id"], root=root / "store")
            self.assertEqual(loaded["status"], "loaded")
            self.assertEqual(integrity.apply_document_content_recovery_plan(record.document_id, plan["plan_id"], root=root / "store")["status"], "recovered")

            invalid_path = root / "store" / integrity.RECOVERY_PLAN_DIR / record.document_id / "broken.json"
            self._save_json(invalid_path, {"document_id": record.document_id})
            self.assertEqual(integrity.load_document_content_recovery_plan(record.document_id, "broken", root=root / "store")["status"], "invalid")

            unsupported_path = root / "store" / integrity.RECOVERY_PLAN_DIR / record.document_id / f"{plan['plan_id']}.json"
            edited = json.loads(unsupported_path.read_text(encoding="utf-8"))
            edited["planned_actions"] = [{"action": "drop_the_world", "transaction_id": None}]
            self._save_json(unsupported_path, edited)
            rejected = integrity.apply_document_content_recovery_plan(record.document_id, plan["plan_id"], root=root / "store")
            self.assertEqual(rejected["status"], "invalid")
            self.assertIn("recovery_plan_unsupported_action", rejected["blockers"])

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)

            def fail(stage: str) -> None:
                if stage == "curation_after_overlay":
                    raise RuntimeError("boom")

            integrity._FAIL_STAGE_HOOK = fail
            with self.assertRaises(RuntimeError):
                save_document_content_curation_change(
                    record.document_id,
                    {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}},
                    root=root / "store",
                )
            integrity._FAIL_STAGE_HOOK = None
            plan = integrity.create_document_content_recovery_plan(record.document_id, root=root / "store")
            plan_path = root / "store" / integrity.RECOVERY_PLAN_DIR / record.document_id / f"{plan['plan_id']}.json"
            payload = json.loads(plan_path.read_text(encoding="utf-8"))
            payload["source_integrity_scan_fingerprint"] = "sha256:stale"
            self._save_json(plan_path, payload)
            stale = integrity.apply_document_content_recovery_plan(record.document_id, plan["plan_id"], root=root / "store")
            self.assertEqual(stale["status"], "stale")
            self.assertEqual(integrity.load_document_content_recovery_plan(record.document_id, plan["plan_id"], root=root / "store")["plan"]["status"], "stale")
            self.assertEqual(integrity.load_document_content_recovery_plan("wrong-doc", plan["plan_id"], root=root / "store")["status"], "not_found")

    def test_restore_and_bulk_retry_remain_idempotent(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            save_document_content_curation_change(record.document_id, {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}}, root=root / "store")
            save_document_content_curation_change(record.document_id, {"target_type": "section", "target_id": "section_001_001", "operation": "rename", "value": {"title": "Authentication Factors"}}, root=root / "store")

            def fail_restore(stage: str) -> None:
                if stage == "restore_after_overlay":
                    raise RuntimeError("boom")

            integrity._FAIL_STAGE_HOOK = fail_restore
            with self.assertRaises(RuntimeError):
                restore_document_content_curation_revision(record.document_id, 1, root=root / "store")
            integrity._FAIL_STAGE_HOOK = None
            plan = integrity.create_document_content_recovery_plan(record.document_id, root=root / "store")
            integrity.apply_document_content_recovery_plan(record.document_id, plan["plan_id"], root=root / "store")
            retry = restore_document_content_curation_revision(record.document_id, 1, root=root / "store")
            self.assertEqual(retry["status"], "unchanged")

            bulk = create_document_content_bulk_plan(record.document_id, root=root / "store")
            add_document_content_bulk_operation(record.document_id, bulk["batch_id"], {"operation_type": "rename_sections", "renames": {"section_001_001": "Authentication Factors Three"}}, root=root / "store")
            preview_document_content_bulk_plan(record.document_id, bulk["batch_id"], root=root / "store")
            approve_document_content_bulk_plan(record.document_id, bulk["batch_id"], root=root / "store")

            def fail_bulk(stage: str) -> None:
                if stage == "bulk_after_history":
                    raise RuntimeError("boom")

            integrity._FAIL_STAGE_HOOK = fail_bulk
            with self.assertRaises(RuntimeError):
                commit_document_content_bulk_plan(record.document_id, bulk["batch_id"], root=root / "store")
            integrity._FAIL_STAGE_HOOK = None
            bulk_plan = integrity.create_document_content_recovery_plan(record.document_id, root=root / "store")
            integrity.apply_document_content_recovery_plan(record.document_id, bulk_plan["plan_id"], root=root / "store")
            bulk_retry = commit_document_content_bulk_plan(record.document_id, bulk["batch_id"], root=root / "store")
            self.assertIn(bulk_retry["status"], {"committed", "conflict"})

    def test_reports_include_new_issue_types_and_exclude_sensitive_content(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            save_document_content_curation_change(record.document_id, {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}}, root=root / "store")
            save_document_content_curation_change(record.document_id, {"target_type": "section", "target_id": "section_001_001", "operation": "rename", "value": {"title": "Authentication Factors"}}, root=root / "store")
            overlay_path = root / "store" / "document_content_curation" / f"{record.document_id}.json"
            overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
            overlay["curation_revision"] = 1
            self._save_json(overlay_path, overlay)
            history_one = integrity._history_revision_path(root / "store", record.document_id, 1)
            conflict_payload = json.loads(history_one.read_text(encoding="utf-8"))
            conflict_payload["overlay"]["chapter_title_overrides"] = {"chapter_001": "Different"}
            conflict_payload["integrity_fingerprint"] = "sha256:conflict"
            self._save_json(root / "store" / "document_content_curation_history" / record.document_id / "102.json", conflict_payload)

            prepared = integrity.prepare_document_content_transaction(
                "bulk_commit",
                record.document_id,
                expected_previous_revision=0,
                expected_new_revision=9,
                base_content_map_fingerprint="fp",
                source_revision=1,
                proposed_overlay_state={"document_id": record.document_id, "curation_revision": 9},
                source_workflow_type="bulk_commit",
                source_workflow_id="missing_batch",
                source_workflow_revision=1,
                root=root / "store",
            )
            scan = integrity.scan_document_content_integrity(record.document_id, root=root / "store")
            plan = integrity.create_document_content_recovery_plan(record.document_id, root=root / "store")
            tx_report = integrity.format_document_content_transaction_report(record.document_id, prepared["transaction_id"], root=root / "store")
            integrity_report = integrity.format_document_content_integrity_report(record.document_id, root=root / "store")
            recovery_report = integrity.format_document_content_recovery_report(record.document_id, plan["plan_id"], root=root / "store")
            self.assertIn("Status:", tx_report)
            self.assertIn("overlay_revision_behind_history", integrity_report)
            self.assertIn("duplicate_conflicting_history_revision", integrity_report)
            self.assertIn("transaction_missing_workflow_record", integrity_report)
            self.assertIn("manual_review_required", recovery_report)
            for text in (tx_report, integrity_report, recovery_report):
                self.assertNotIn(str(root), text)
                self.assertNotIn("Authentication overview", text)
                self.assertNotIn("token", text.lower())
                self.assertNotIn("credential", text.lower())
                self.assertNotIn("stack trace", text.lower())
