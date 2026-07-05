from __future__ import annotations

import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional import api
from backend.electional.document_content_curation import load_document_content_curation, save_document_content_curation_change
from backend.electional.document_content_history import (
    compare_document_content_curation_revisions,
    format_document_content_curation_comparison_report,
    format_document_content_curation_history_report,
    format_document_content_curation_restore_report,
    list_document_content_curation_revisions,
    load_document_content_curation_revision,
    restore_document_content_curation_revision,
    save_curation_history_snapshot,
    validate_historical_curation_revision,
)
from backend.tests.test_document_content_curation import _build_detected_map, _write_chunk
from backend.electional.document_content_map import build_document_content_map


class DocumentContentHistoryTest(TestCase):
    def test_effective_change_creates_one_history_snapshot_and_noop_creates_none(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            no_op = save_document_content_curation_change(
                record.document_id,
                {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Access Control"}},
                root=root / "store",
            )
            saved = save_document_content_curation_change(
                record.document_id,
                {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}},
                root=root / "store",
            )
            history = list_document_content_curation_revisions(record.document_id, root=root / "store")
            self.assertEqual(no_op["status"], "unchanged")
            self.assertEqual(saved["status"], "saved")
            self.assertEqual(history["count"], 1)
            self.assertEqual(history["items"][0]["curation_revision"], 1)

    def test_duplicate_snapshot_write_is_idempotent_and_conflict_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            saved = save_document_content_curation_change(
                record.document_id,
                {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}},
                root=root / "store",
            )
            overlay = saved["curation"]
            same = save_curation_history_snapshot(record.document_id, overlay, root=root / "store")
            conflict_overlay = copy.deepcopy(overlay)
            conflict_overlay["section_title_overrides"] = {"section_001_001": "Conflict"}
            conflict_overlay["changes"] = [{"target_type": "section", "target_id": "section_001_001", "operation": "rename", "value": {"title": "Conflict"}, "note": None}]
            conflict = save_curation_history_snapshot(record.document_id, conflict_overlay, root=root / "store")
            self.assertEqual(same["status"], "unchanged")
            self.assertEqual(conflict["status"], "conflict")

    def test_revision_listing_is_deterministic_and_load_is_read_only(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            save_document_content_curation_change(record.document_id, {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}}, root=root / "store")
            save_document_content_curation_change(record.document_id, {"target_type": "section", "target_id": "section_001_001", "operation": "rename", "value": {"title": "Authentication Factors"}}, root=root / "store")
            listing = list_document_content_curation_revisions(record.document_id, root=root / "store")
            loaded = load_document_content_curation_revision(record.document_id, 1, root=root / "store")
            loaded["revision_record"]["overlay"]["chapter_title_overrides"]["chapter_001"] = "Tampered"
            reloaded = load_document_content_curation_revision(record.document_id, 1, root=root / "store")
            self.assertEqual([item["curation_revision"] for item in listing["items"]], [1, 2])
            self.assertEqual(reloaded["revision_record"]["overlay"]["chapter_title_overrides"]["chapter_001"], "Identity Controls")

    def test_history_snapshot_remains_unchanged_after_later_revisions(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            save_document_content_curation_change(record.document_id, {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}}, root=root / "store")
            first = load_document_content_curation_revision(record.document_id, 1, root=root / "store")["revision_record"]
            save_document_content_curation_change(record.document_id, {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Program"}}, root=root / "store")
            again = load_document_content_curation_revision(record.document_id, 1, root=root / "store")["revision_record"]
            self.assertEqual(first, again)

    def test_revision_comparison_detects_added_removed_changed_categories(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            save_document_content_curation_change(record.document_id, {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}}, root=root / "store")
            save_document_content_curation_change(record.document_id, {"target_type": "chapter", "target_id": "chapter_001", "operation": "set_range", "value": {"start_page": 1, "end_page": 2}}, root=root / "store")
            save_document_content_curation_change(record.document_id, {"target_type": "section", "target_id": "section_001_001", "operation": "rename", "value": {"title": "Authentication Factors"}}, root=root / "store")
            save_document_content_curation_change(record.document_id, {"target_type": "section", "target_id": "section_001_001", "operation": "set_range", "value": {"start_page": 1, "end_page": 2}}, root=root / "store")
            save_document_content_curation_change(record.document_id, {"target_type": "section", "target_id": "section_001_002", "operation": "assign_chunk", "value": {"chunk_id": f"chunk_{record.document_id}_0003"}}, root=root / "store")
            save_document_content_curation_change(record.document_id, {"target_type": "chunk", "target_id": f"chunk_{record.document_id}_0003", "operation": "add_tag", "value": {"tag": "identity-management"}}, root=root / "store")
            save_document_content_curation_change(record.document_id, {"target_type": "chunk", "target_id": f"chunk_{record.document_id}_0003", "operation": "remove_tag", "value": {"tag": "identity-management"}}, root=root / "store")
            restored = restore_document_content_curation_revision(record.document_id, 1, root=root / "store")
            compare_added = compare_document_content_curation_revisions(record.document_id, 1, 7, root=root / "store")
            compare_removed = compare_document_content_curation_revisions(record.document_id, 7, restored["curation"]["curation_revision"], root=root / "store")
            self.assertEqual(compare_added["status"], "ready")
            self.assertGreater(compare_added["categories"]["chapter_range_overrides"]["added_count"], 0)
            self.assertGreater(compare_added["categories"]["section_title_overrides"]["added_count"], 0)
            self.assertGreater(compare_added["categories"]["section_range_overrides"]["added_count"], 0)
            self.assertGreater(compare_added["categories"]["chunk_assignment_overrides"]["added_count"], 0)
            self.assertGreater(compare_added["categories"]["manual_tag_removals"]["added_count"], 0)
            self.assertGreater(compare_removed["categories"]["section_title_overrides"]["removed_count"], 0)

    def test_cross_document_comparison_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record_a, _ = _build_detected_map(root, "a")
            record_b, _ = _build_detected_map(root, "b")
            save_document_content_curation_change(record_a.document_id, {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}}, root=root / "store")
            save_document_content_curation_change(record_b.document_id, {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Other Controls"}}, root=root / "store")
            other = load_document_content_curation_revision(record_b.document_id, 1, root=root / "store")["revision_record"]
            path = root / "store" / "document_content_curation_history" / record_a.document_id / "2.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(other, indent=2), encoding="utf-8")
            result = compare_document_content_curation_revisions(record_a.document_id, 1, 2, root=root / "store")
            self.assertEqual(result["status"], "conflict")

    def test_restore_creates_new_revision_records_provenance_and_noop(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            save_document_content_curation_change(record.document_id, {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}}, root=root / "store")
            save_document_content_curation_change(record.document_id, {"target_type": "section", "target_id": "section_001_001", "operation": "rename", "value": {"title": "Authentication Factors"}}, root=root / "store")
            restored = restore_document_content_curation_revision(record.document_id, 1, root=root / "store")
            current = load_document_content_curation(record.document_id, root=root / "store")["curation"]
            history = list_document_content_curation_revisions(record.document_id, root=root / "store")
            no_op = restore_document_content_curation_revision(record.document_id, restored["curation"]["curation_revision"], root=root / "store")
            self.assertEqual(restored["status"], "restored")
            self.assertEqual(current["curation_revision"], 3)
            self.assertEqual(restored["restore_provenance"]["restored_from_revision"], 1)
            self.assertEqual(restored["restore_provenance"]["previous_current_revision"], 2)
            self.assertEqual(history["count"], 3)
            self.assertEqual(no_op["status"], "unchanged")

    def test_restore_blocks_stale_and_invalid_revisions(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            save_document_content_curation_change(record.document_id, {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}}, root=root / "store")
            _write_chunk(root, record.document_id, f"chunk_{record.document_id}_0004", 4, 2, 2, "New text")
            build_document_content_map(record.document_id, regenerate=True, root=root / "store")
            stale = restore_document_content_curation_revision(record.document_id, 1, root=root / "store")
            history_path = root / "store" / "document_content_curation_history" / record.document_id / "1.json"
            payload = json.loads(history_path.read_text(encoding="utf-8"))
            payload["overlay"] = "bad"
            payload["integrity_fingerprint"] = "sha256:bad"
            history_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            invalid = restore_document_content_curation_revision(record.document_id, 1, root=root / "store")
            self.assertEqual(stale["status"], "stale")
            self.assertEqual(invalid["status"], "invalid")

    def test_historical_validation_detects_stale_reference_and_revision_mismatch(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            save_document_content_curation_change(record.document_id, {"target_type": "section", "target_id": "section_001_002", "operation": "assign_chunk", "value": {"chunk_id": f"chunk_{record.document_id}_0003"}}, root=root / "store")
            history_path = root / "store" / "document_content_curation_history" / record.document_id / "1.json"
            payload = json.loads(history_path.read_text(encoding="utf-8"))
            payload["overlay"]["chunk_assignment_overrides"] = {f"chunk_{record.document_id}_9999": "section_001_002"}
            payload["integrity_fingerprint"] = "sha256:" + "0" * 64
            history_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            invalid = validate_historical_curation_revision(record.document_id, 1, root=root / "store")
            payload = json.loads(history_path.read_text(encoding="utf-8"))
            payload["overlay"] = load_document_content_curation(record.document_id, root=root / "store")["curation"]
            payload["overlay"]["source_revision"] = "older"
            payload["integrity_fingerprint"] = "sha256:" + "1" * 64
            history_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            invalid_again = validate_historical_curation_revision(record.document_id, 1, root=root / "store")
            self.assertEqual(invalid["status"], "invalid")
            self.assertEqual(invalid_again["status"], "invalid")

    def test_public_safe_history_comparison_and_restore_reports_exclude_private_content(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            save_document_content_curation_change(record.document_id, {"target_type": "chunk", "target_id": f"chunk_{record.document_id}_0003", "operation": "add_tag", "value": {"tag": "token api key C:\\private"}}, root=root / "store")
            save_document_content_curation_change(record.document_id, {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}}, root=root / "store")
            history_report = format_document_content_curation_history_report(record.document_id, root=root / "store")
            comparison_report = format_document_content_curation_comparison_report(record.document_id, 1, 2, root=root / "store")
            restore_report = format_document_content_curation_restore_report(record.document_id, 1, root=root / "store")
            for text in (history_report, comparison_report, restore_report):
                self.assertNotIn(str(root), text)
                self.assertNotIn("Authentication overview", text)
                self.assertNotIn("token", text.lower())
                self.assertNotIn("api key", text.lower())
                self.assertNotIn("stack trace", text.lower())

    def test_api_history_wrappers_call_real_backend_logic(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            save_document_content_curation_change(record.document_id, {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}}, root=root / "store")
            listing = api.list_document_content_curation_revisions(record.document_id, root=root / "store")
            loaded = api.load_document_content_curation_revision(record.document_id, 1, root=root / "store")
            compared = api.compare_document_content_curation_revisions(record.document_id, 1, 1, root=root / "store")
            restored = api.restore_document_content_curation_revision(record.document_id, 1, root=root / "store")
            self.assertEqual(listing["count"], 1)
            self.assertEqual(loaded["status"], "ready")
            self.assertEqual(compared["status"], "ready")
            self.assertIn(restored["status"], {"unchanged", "restored"})
