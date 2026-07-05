from __future__ import annotations

import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional.document_content_bulk import (
    add_document_content_bulk_operation,
    approve_document_content_bulk_plan,
    clear_document_content_bulk_operations,
    commit_document_content_bulk_plan,
    create_document_content_bulk_plan,
    format_document_content_bulk_report,
    list_document_content_bulk_plans,
    list_document_content_bulk_review_queue,
    load_document_content_bulk_plan,
    preview_document_content_bulk_plan,
    reject_document_content_bulk_plan,
    remove_document_content_bulk_operation,
    replace_document_content_bulk_operation,
    validate_document_content_bulk_plan,
)
from backend.electional.document_content_curation import build_curated_document_content_map, load_document_content_curation, save_document_content_curation_change
from backend.electional.document_content_history import list_document_content_curation_revisions
from backend.electional.document_content_map import build_document_content_map
from backend.tests.test_document_content_curation import _build_detected_map, _write_chunk


class DocumentContentBulkTest(TestCase):
    def test_new_plan_is_separate_and_dry_run_preserves_curation_history_and_detected_map(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, detected = _build_detected_map(root)
            created = create_document_content_bulk_plan(record.document_id, root=root / "store")
            curation_before = load_document_content_curation(record.document_id, root=root / "store")["curation"]
            history_before = list_document_content_curation_revisions(record.document_id, root=root / "store")
            detected_before = copy.deepcopy(detected)

            add_document_content_bulk_operation(
                record.document_id,
                created["batch_id"],
                {"operation_type": "add_tag_many", "chunk_ids": [f"chunk_{record.document_id}_0001"], "tag": "Identity Management"},
                root=root / "store",
            )
            preview = preview_document_content_bulk_plan(record.document_id, created["batch_id"], root=root / "store")

            self.assertEqual(created["status"], "draft")
            self.assertTrue((root / "store" / "document_content_bulk" / record.document_id / f"{created['batch_id']}.json").exists())
            self.assertIsNone(curation_before)
            self.assertEqual(load_document_content_curation(record.document_id, root=root / "store")["curation"], curation_before)
            self.assertEqual(list_document_content_curation_revisions(record.document_id, root=root / "store")["count"], history_before["count"])
            self.assertEqual(detected, detected_before)
            self.assertIn(preview["status"], {"ready_for_review", "unchanged"})

    def test_add_remove_replace_clear_and_duplicate_behaviors_are_revision_safe(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            created = create_document_content_bulk_plan(record.document_id, root=root / "store")

            first = add_document_content_bulk_operation(
                record.document_id,
                created["batch_id"],
                {"operation_type": "rename_chapters", "renames": {"chapter_001": "Identity Controls"}},
                root=root / "store",
            )
            first_revision = first["plan"]["batch_revision"]
            duplicate = add_document_content_bulk_operation(
                record.document_id,
                created["batch_id"],
                {"operation_type": "rename_chapters", "renames": {"chapter_001": "Identity Controls"}},
                root=root / "store",
            )
            after_duplicate = load_document_content_bulk_plan(record.document_id, created["batch_id"], root=root / "store")["plan"]
            invalid = add_document_content_bulk_operation(
                record.document_id,
                created["batch_id"],
                {"operation_type": "unsupported"},
                root=root / "store",
            )
            after_invalid = load_document_content_bulk_plan(record.document_id, created["batch_id"], root=root / "store")["plan"]
            operation_id = after_duplicate["operations"][0]["operation_id"]
            replaced = replace_document_content_bulk_operation(
                record.document_id,
                created["batch_id"],
                operation_id,
                {"operation_type": "rename_chapters", "renames": {"chapter_001": "Identity Program"}},
                root=root / "store",
            )
            replace_revision = replaced["plan"]["batch_revision"]
            replaced_same = replace_document_content_bulk_operation(
                record.document_id,
                created["batch_id"],
                replaced["plan"]["operations"][0]["operation_id"],
                {"operation_type": "rename_chapters", "renames": {"chapter_001": "Identity Program"}},
                root=root / "store",
            )
            removed = remove_document_content_bulk_operation(record.document_id, created["batch_id"], replaced["plan"]["operations"][0]["operation_id"], root=root / "store")
            cleared_empty = clear_document_content_bulk_operations(record.document_id, created["batch_id"], root=root / "store")

            self.assertEqual(first_revision, 2)
            self.assertEqual(duplicate["status"], "unchanged")
            self.assertEqual(after_duplicate["batch_revision"], first_revision)
            self.assertEqual(invalid["status"], "invalid")
            self.assertEqual(after_invalid["batch_revision"], first_revision)
            self.assertEqual(replaced["status"], "draft")
            self.assertEqual(replace_revision, first_revision + 1)
            self.assertEqual(replaced_same["status"], "unchanged")
            self.assertEqual(removed["status"], "draft")
            self.assertEqual(removed["plan"]["operation_count"], 0)
            self.assertEqual(cleared_empty["status"], "unchanged")

    def test_clear_operations_resets_preview_validation_counts_and_approval(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            created = create_document_content_bulk_plan(record.document_id, root=root / "store")
            add_document_content_bulk_operation(
                record.document_id,
                created["batch_id"],
                {"operation_type": "rename_sections", "renames": {"section_001_001": "Authentication Factors"}},
                root=root / "store",
            )
            preview_document_content_bulk_plan(record.document_id, created["batch_id"], root=root / "store")
            approved = approve_document_content_bulk_plan(record.document_id, created["batch_id"], root=root / "store")
            before_clear = approved["plan"]["batch_revision"]
            cleared = clear_document_content_bulk_operations(record.document_id, created["batch_id"], root=root / "store")
            loaded = load_document_content_bulk_plan(record.document_id, created["batch_id"], root=root / "store")["plan"]

            self.assertEqual(cleared["status"], "draft")
            self.assertEqual(loaded["batch_revision"], before_clear + 1)
            self.assertEqual(loaded["operations"], [])
            self.assertEqual(loaded["operation_count"], 0)
            self.assertEqual(loaded["effective_change_count"], 0)
            self.assertEqual(loaded["unchanged_operation_count"], 0)
            self.assertEqual(loaded["preview_summary"], {})
            self.assertEqual(loaded["validation_result"], {})
            self.assertEqual(loaded["warnings"], [])
            self.assertEqual(loaded["blockers"], [])
            self.assertIsNone(loaded["approval_metadata"])

    def test_preview_supports_tags_assignments_renames_ranges_and_conflicts(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            created = create_document_content_bulk_plan(record.document_id, root=root / "store")
            for payload in (
                {"operation_type": "add_tag_many", "chunk_ids": [f"chunk_{record.document_id}_0001"], "tag": "Identity"},
                {"operation_type": "remove_tag_many", "chunk_ids": [f"chunk_{record.document_id}_0001"], "tag": "Identity"},
                {"operation_type": "assign_chunks_to_section", "chunk_ids": [f"chunk_{record.document_id}_0003"], "section_id": "section_001_002"},
                {"operation_type": "unassign_chunks", "chunk_ids": [f"chunk_{record.document_id}_0003"]},
                {"operation_type": "rename_chapters", "renames": {"chapter_001": "Identity Controls"}},
                {"operation_type": "rename_sections", "renames": {"section_001_001": "Authentication Factors"}},
                {"operation_type": "set_chapter_ranges", "ranges": {"chapter_001": {"start_page": 1, "end_page": 2}}},
                {"operation_type": "set_section_ranges", "ranges": {"section_001_001": {"start_page": 1, "end_page": 1}}},
            ):
                add_document_content_bulk_operation(record.document_id, created["batch_id"], payload, root=root / "store")
            preview = preview_document_content_bulk_plan(record.document_id, created["batch_id"], root=root / "store")
            summary = preview["plan"]["preview_summary"]
            self.assertIn(preview["status"], {"ready_for_review", "invalid"})
            for key in ("add_tag_many", "remove_tag_many", "assign_chunks_to_section", "rename_chapters", "rename_sections", "set_chapter_ranges", "set_section_ranges"):
                self.assertIn(key, summary["operation_type_counts"])

            conflicting = create_document_content_bulk_plan(record.document_id, root=root / "store")
            add_document_content_bulk_operation(record.document_id, conflicting["batch_id"], {"operation_type": "rename_chapters", "renames": {"chapter_001": "One"}}, root=root / "store")
            add_document_content_bulk_operation(record.document_id, conflicting["batch_id"], {"operation_type": "rename_chapters", "renames": {"chapter_001": "Two"}}, root=root / "store")
            conflict_preview = preview_document_content_bulk_plan(record.document_id, conflicting["batch_id"], root=root / "store")
            self.assertEqual(conflict_preview["status"], "invalid")
            self.assertIn("conflicting_duplicate_operation", conflict_preview["blockers"])

            assignment_conflict = create_document_content_bulk_plan(record.document_id, root=root / "store")
            add_document_content_bulk_operation(record.document_id, assignment_conflict["batch_id"], {"operation_type": "assign_chunks_to_sections", "assignments": {f"chunk_{record.document_id}_0002": "section_001_001"}}, root=root / "store")
            add_document_content_bulk_operation(record.document_id, assignment_conflict["batch_id"], {"operation_type": "assign_chunks_to_sections", "assignments": {f"chunk_{record.document_id}_0002": "section_001_002"}}, root=root / "store")
            assignment_preview = preview_document_content_bulk_plan(record.document_id, assignment_conflict["batch_id"], root=root / "store")
            self.assertEqual(assignment_preview["status"], "invalid")
            self.assertIn("conflicting_duplicate_operation", assignment_preview["blockers"])

            assign_unassign = create_document_content_bulk_plan(record.document_id, root=root / "store")
            add_document_content_bulk_operation(record.document_id, assign_unassign["batch_id"], {"operation_type": "assign_chunks_to_sections", "assignments": {f"chunk_{record.document_id}_0002": "section_001_001"}}, root=root / "store")
            add_document_content_bulk_operation(record.document_id, assign_unassign["batch_id"], {"operation_type": "unassign_chunks", "chunk_ids": [f"chunk_{record.document_id}_0002"]}, root=root / "store")
            assign_unassign_preview = preview_document_content_bulk_plan(record.document_id, assign_unassign["batch_id"], root=root / "store")
            self.assertEqual(assign_unassign_preview["status"], "invalid")
            self.assertIn("conflicting_duplicate_operation", assign_unassign_preview["blockers"])

    def test_validation_approval_invalidation_and_stale_transitions_work(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)

            blocked = create_document_content_bulk_plan(record.document_id, root=root / "store")
            invalid_add = add_document_content_bulk_operation(record.document_id, blocked["batch_id"], {"operation_type": "rename_chapters", "renames": {"chapter_missing": "Ghost"}}, root=root / "store")
            blocked_validation = validate_document_content_bulk_plan(record.document_id, blocked["batch_id"], root=root / "store")
            blocked_approval = approve_document_content_bulk_plan(record.document_id, blocked["batch_id"], root=root / "store")
            self.assertEqual(invalid_add["status"], "invalid")
            self.assertEqual(blocked_validation["status"], "unchanged")
            self.assertEqual(blocked_approval["status"], "unchanged")

            unchanged = create_document_content_bulk_plan(record.document_id, root=root / "store")
            unchanged_preview = preview_document_content_bulk_plan(record.document_id, unchanged["batch_id"], root=root / "store")
            self.assertEqual(unchanged_preview["status"], "unchanged")

            editable = create_document_content_bulk_plan(record.document_id, root=root / "store")
            add_document_content_bulk_operation(record.document_id, editable["batch_id"], {"operation_type": "rename_chapters", "renames": {"chapter_001": "Identity Controls"}}, root=root / "store")
            preview_document_content_bulk_plan(record.document_id, editable["batch_id"], root=root / "store")
            approved = approve_document_content_bulk_plan(record.document_id, editable["batch_id"], root=root / "store")
            approved_revision = approved["plan"]["batch_revision"]
            replaced = replace_document_content_bulk_operation(record.document_id, editable["batch_id"], approved["plan"]["operations"][0]["operation_id"], {"operation_type": "rename_chapters", "renames": {"chapter_001": "Identity Program"}}, root=root / "store")
            self.assertIsNone(replaced["plan"]["approval_metadata"])
            self.assertEqual(replaced["plan"]["batch_revision"], approved_revision + 1)
            self.assertEqual(approve_document_content_bulk_plan(record.document_id, editable["batch_id"], root=root / "store")["status"], "approved")

            fp_stale = create_document_content_bulk_plan(record.document_id, root=root / "store")
            add_document_content_bulk_operation(record.document_id, fp_stale["batch_id"], {"operation_type": "rename_chapters", "renames": {"chapter_001": "Identity Controls"}}, root=root / "store")
            _write_chunk(root, record.document_id, f"chunk_{record.document_id}_0004", 4, 2, 2, "New text")
            build_document_content_map(record.document_id, regenerate=True, root=root / "store")
            self.assertEqual(preview_document_content_bulk_plan(record.document_id, fp_stale["batch_id"], root=root / "store")["status"], "stale")

            src_stale = create_document_content_bulk_plan(record.document_id, root=root / "store")
            add_document_content_bulk_operation(record.document_id, src_stale["batch_id"], {"operation_type": "rename_chapters", "renames": {"chapter_001": "Identity Controls"}}, root=root / "store")
            map_path = root / "store" / "document_content_maps" / f"{record.document_id}.json"
            map_payload = json.loads(map_path.read_text(encoding="utf-8"))
            map_payload["source_revision"] = "changed-source"
            map_path.write_text(json.dumps(map_payload, indent=2), encoding="utf-8")
            self.assertEqual(preview_document_content_bulk_plan(record.document_id, src_stale["batch_id"], root=root / "store")["status"], "stale")

            curation_stale = create_document_content_bulk_plan(record.document_id, root=root / "store")
            add_document_content_bulk_operation(record.document_id, curation_stale["batch_id"], {"operation_type": "rename_chapters", "renames": {"chapter_001": "Identity Controls"}}, root=root / "store")
            save_document_content_curation_change(record.document_id, {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}}, root=root / "store")
            stale_preview = preview_document_content_bulk_plan(record.document_id, curation_stale["batch_id"], root=root / "store")
            stale_commit = commit_document_content_bulk_plan(record.document_id, curation_stale["batch_id"], root=root / "store")
            self.assertEqual(stale_preview["status"], "stale")
            self.assertEqual(stale_commit["status"], "stale")

    def test_commit_creates_one_revision_and_one_snapshot_and_edit_restrictions_hold(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, detected = _build_detected_map(root)
            save_document_content_curation_change(record.document_id, {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}}, root=root / "store")
            created = create_document_content_bulk_plan(record.document_id, root=root / "store")
            add_document_content_bulk_operation(record.document_id, created["batch_id"], {"operation_type": "rename_sections", "renames": {"section_001_001": "Authentication Factors"}}, root=root / "store")
            add_document_content_bulk_operation(record.document_id, created["batch_id"], {"operation_type": "add_tag_many", "chunk_ids": [f"chunk_{record.document_id}_0002"], "tag": "identity-management"}, root=root / "store")
            preview = preview_document_content_bulk_plan(record.document_id, created["batch_id"], root=root / "store")
            queue = list_document_content_bulk_review_queue(record.document_id, root=root / "store")
            approved = approve_document_content_bulk_plan(record.document_id, created["batch_id"], root=root / "store")
            committed = commit_document_content_bulk_plan(record.document_id, created["batch_id"], root=root / "store")
            committed_again = commit_document_content_bulk_plan(record.document_id, created["batch_id"], root=root / "store")
            current = load_document_content_curation(record.document_id, root=root / "store")["curation"]
            history = list_document_content_curation_revisions(record.document_id, root=root / "store")
            report = format_document_content_bulk_report(record.document_id, created["batch_id"], root=root / "store")

            self.assertEqual(preview["status"], "ready_for_review")
            self.assertEqual(queue["actionable_batch_id"], created["batch_id"])
            self.assertEqual(approved["status"], "approved")
            self.assertEqual(committed["status"], "committed")
            self.assertEqual(current["curation_revision"], 2)
            self.assertEqual(history["count"], 2)
            self.assertEqual(current["bulk_provenance"]["bulk_batch_id"], created["batch_id"])
            self.assertEqual(committed_again["status"], "conflict")
            self.assertEqual(detected["document_id"], record.document_id)
            self.assertNotIn(str(root), report)
            self.assertNotIn("token", report.lower())
            self.assertNotIn("api key", report.lower())

            self.assertEqual(clear_document_content_bulk_operations(record.document_id, created["batch_id"], root=root / "store")["status"], "committed")
            self.assertEqual(replace_document_content_bulk_operation(record.document_id, created["batch_id"], created["batch_id"], {"operation_type": "rename_chapters", "renames": {"chapter_001": "Nope"}}, root=root / "store")["status"], "committed")

            rejected = create_document_content_bulk_plan(record.document_id, root=root / "store")
            add_document_content_bulk_operation(record.document_id, rejected["batch_id"], {"operation_type": "rename_chapters", "renames": {"chapter_001": "Reject Me"}}, root=root / "store")
            preview_document_content_bulk_plan(record.document_id, rejected["batch_id"], root=root / "store")
            reject_document_content_bulk_plan(record.document_id, rejected["batch_id"], "no", root=root / "store")
            self.assertEqual(commit_document_content_bulk_plan(record.document_id, rejected["batch_id"], root=root / "store")["status"], "failed")
            self.assertEqual(clear_document_content_bulk_operations(record.document_id, rejected["batch_id"], root=root / "store")["status"], "rejected")
            loaded_rejected = load_document_content_bulk_plan(record.document_id, rejected["batch_id"], root=root / "store")["plan"]
            rejected_op_id = loaded_rejected["operations"][0]["operation_id"]
            self.assertEqual(replace_document_content_bulk_operation(record.document_id, rejected["batch_id"], rejected_op_id, {"operation_type": "rename_chapters", "renames": {"chapter_001": "Still No"}}, root=root / "store")["status"], "rejected")

            curated = build_curated_document_content_map(record.document_id, root=root / "store")
            self.assertTrue(curated["curation_applied"])

    def test_review_queue_is_deterministic_and_summaries_omit_raw_payloads(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            first = create_document_content_bulk_plan(record.document_id, root=root / "store")
            add_document_content_bulk_operation(record.document_id, first["batch_id"], {"operation_type": "rename_chapters", "renames": {"chapter_001": "Identity Controls"}}, root=root / "store")
            preview_document_content_bulk_plan(record.document_id, first["batch_id"], root=root / "store")
            second = create_document_content_bulk_plan(record.document_id, root=root / "store")
            listing = list_document_content_bulk_plans(record.document_id, root=root / "store")
            queue = list_document_content_bulk_review_queue(record.document_id, root=root / "store")

            self.assertEqual(listing["items"][0]["batch_id"], first["batch_id"])
            self.assertEqual(queue["actionable_batch_id"], first["batch_id"])
            self.assertNotIn("operations", listing["items"][0])
            self.assertNotIn("normalized_value", json.dumps(queue))
