from __future__ import annotations

import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional.document_content_curation import build_curated_document_content_map, load_document_content_curation, save_document_content_curation_change
from backend.electional.document_content_history import list_document_content_curation_revisions, load_document_content_curation_revision
from backend.electional.document_content_map import build_document_content_map
from backend.electional.document_content_rebase import (
    abandon_document_content_rebase_workspace,
    apply_document_content_rebase_resolution,
    commit_document_content_rebase_workspace,
    create_rebase_workspace_from_current_stale_curation,
    create_rebase_workspace_from_historical_revision,
    format_document_content_rebase_report,
    get_document_content_rebase_readiness,
    load_document_content_rebase_workspace,
    refresh_document_content_rebase_conflicts,
)
from backend.tests.test_document_content_curation import _build_detected_map, _write_chunk


class DocumentContentRebaseTest(TestCase):
    def test_workspace_begins_in_draft_and_refresh_is_idempotent(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, detected = _build_detected_map(root)
            save_document_content_curation_change(record.document_id, {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}}, root=root / "store")
            overlay_before = copy.deepcopy(load_document_content_curation(record.document_id, root=root / "store")["curation"])
            detected_before = copy.deepcopy(detected)
            _write_chunk(root, record.document_id, f"chunk_{record.document_id}_0004", 4, 2, 2, "New text")
            build_document_content_map(record.document_id, regenerate=True, root=root / "store")

            created = create_rebase_workspace_from_current_stale_curation(record.document_id, root=root / "store")
            readiness_before = get_document_content_rebase_readiness(record.document_id, created["workspace"]["workspace_id"], root=root / "store")
            refreshed = refresh_document_content_rebase_conflicts(record.document_id, created["workspace"]["workspace_id"], root=root / "store")
            refreshed_again = refresh_document_content_rebase_conflicts(record.document_id, created["workspace"]["workspace_id"], root=root / "store")

            self.assertEqual(created["status"], "draft")
            self.assertEqual(created["workspace"]["status"], "draft")
            self.assertEqual(readiness_before["status"], "draft")
            self.assertIn(refreshed["status"], {"ready", "ready_with_warnings"})
            self.assertIn(refreshed_again["status"], {"ready", "ready_with_warnings"})
            self.assertEqual(refreshed["workspace"]["workspace_revision"], refreshed_again["workspace"]["workspace_revision"])
            self.assertEqual(load_document_content_curation(record.document_id, root=root / "store")["curation"], overlay_before)
            self.assertEqual(detected, detected_before)

    def test_document_mismatch_conflict_is_emitted_and_blocks_commit(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            save_document_content_curation_change(record.document_id, {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}}, root=root / "store")
            overlay_path = root / "store" / "document_content_curation" / f"{record.document_id}.json"
            payload = json.loads(overlay_path.read_text(encoding="utf-8"))
            payload["document_id"] = "other-document"
            overlay_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            created = create_rebase_workspace_from_current_stale_curation(record.document_id, root=root / "store")
            refreshed = refresh_document_content_rebase_conflicts(record.document_id, created["workspace"]["workspace_id"], root=root / "store")
            report = format_document_content_rebase_report(record.document_id, created["workspace"]["workspace_id"], root=root / "store")
            committed = commit_document_content_rebase_workspace(record.document_id, created["workspace"]["workspace_id"], root=root / "store")

            categories = [item["conflict_type"] for item in refreshed["workspace"]["conflicts"]]
            mismatch = next(item for item in refreshed["workspace"]["conflicts"] if item["conflict_type"] == "document_mismatch")
            self.assertIn("document_mismatch", categories)
            self.assertEqual(mismatch["severity"], "blocker")
            self.assertEqual(mismatch["allowed_actions"], [])
            self.assertEqual(refreshed["status"], "unresolved")
            self.assertEqual(committed["status"], "failed")
            self.assertIn("document_mismatch", report)

    def test_malformed_override_is_visible_preserved_and_not_keepable(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            save_document_content_curation_change(record.document_id, {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}}, root=root / "store")
            overlay_path = root / "store" / "document_content_curation" / f"{record.document_id}.json"
            payload = json.loads(overlay_path.read_text(encoding="utf-8"))
            payload["chapter_title_overrides"] = "broken-title-map"
            overlay_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            created = create_rebase_workspace_from_current_stale_curation(record.document_id, root=root / "store")
            refreshed = refresh_document_content_rebase_conflicts(record.document_id, created["workspace"]["workspace_id"], root=root / "store")
            malformed = next(item for item in refreshed["workspace"]["conflicts"] if item["conflict_type"] == "malformed_override")
            bad = apply_document_content_rebase_resolution(record.document_id, created["workspace"]["workspace_id"], malformed["conflict_id"], {"action": "keep"}, root=root / "store")
            loaded_before = load_document_content_rebase_workspace(record.document_id, created["workspace"]["workspace_id"], root=root / "store")["workspace"]
            dropped = apply_document_content_rebase_resolution(record.document_id, created["workspace"]["workspace_id"], malformed["conflict_id"], {"action": "drop"}, root=root / "store")
            report = format_document_content_rebase_report(record.document_id, created["workspace"]["workspace_id"], root=root / "store")

            self.assertEqual(refreshed["status"], "unresolved")
            self.assertEqual(malformed["override_type"], "chapter_title_overrides")
            self.assertEqual(bad["status"], "invalid")
            self.assertEqual(bad["blockers"], ["resolution_action_not_allowed"])
            self.assertEqual(loaded_before["source_overlay"]["chapter_title_overrides"], "broken-title-map")
            self.assertIn(dropped["status"], {"ready", "ready_with_warnings"})
            self.assertIn("malformed_override", report)
            self.assertNotIn("broken-title-map", report)

    def test_invalid_chunk_assignment_remains_distinct_from_missing_entities(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            save_document_content_curation_change(record.document_id, {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}}, root=root / "store")
            overlay_path = root / "store" / "document_content_curation" / f"{record.document_id}.json"
            payload = json.loads(overlay_path.read_text(encoding="utf-8"))
            payload["chunk_assignment_overrides"][f"chunk_{record.document_id}_0001"] = "section_001_001"
            payload["chunk_unassignments"] = [f"chunk_{record.document_id}_0001"]
            payload["chunk_assignment_overrides"][f"chunk_{record.document_id}_9998"] = "section_001_001"
            payload["chunk_assignment_overrides"][f"chunk_{record.document_id}_0002"] = "section_missing"
            payload["changes"] = []
            overlay_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            created = create_rebase_workspace_from_current_stale_curation(record.document_id, root=root / "store")
            refreshed = refresh_document_content_rebase_conflicts(record.document_id, created["workspace"]["workspace_id"], root=root / "store")
            conflict_types = [item["conflict_type"] for item in refreshed["workspace"]["conflicts"]]
            ids = [item["conflict_id"] for item in refreshed["workspace"]["conflicts"]]

            self.assertIn("invalid_chunk_assignment", conflict_types)
            self.assertIn("missing_chunk", conflict_types)
            self.assertIn("missing_assignment_target", conflict_types)
            self.assertEqual(ids, sorted(ids))

    def test_effective_resolution_increments_once_and_failed_resolution_does_not(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            save_document_content_curation_change(record.document_id, {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}}, root=root / "store")
            overlay_path = root / "store" / "document_content_curation" / f"{record.document_id}.json"
            payload = json.loads(overlay_path.read_text(encoding="utf-8"))
            payload["chapter_title_overrides"]["chapter_missing"] = "Ghost"
            payload["changes"] = []
            overlay_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            created = create_rebase_workspace_from_current_stale_curation(record.document_id, root=root / "store")
            refreshed = refresh_document_content_rebase_conflicts(record.document_id, created["workspace"]["workspace_id"], root=root / "store")
            conflict_id = next(item["conflict_id"] for item in refreshed["workspace"]["conflicts"] if item["conflict_type"] == "missing_chapter")
            initial_revision = refreshed["workspace"]["workspace_revision"]
            bad = apply_document_content_rebase_resolution(record.document_id, created["workspace"]["workspace_id"], conflict_id, {"action": "remap_chapter", "chapter_id": "chapter_missing"}, root=root / "store")
            after_bad = load_document_content_rebase_workspace(record.document_id, created["workspace"]["workspace_id"], root=root / "store")["workspace"]
            good = apply_document_content_rebase_resolution(record.document_id, created["workspace"]["workspace_id"], conflict_id, {"action": "drop"}, root=root / "store")
            same = apply_document_content_rebase_resolution(record.document_id, created["workspace"]["workspace_id"], conflict_id, {"action": "drop"}, root=root / "store")

            self.assertEqual(bad["status"], "invalid")
            self.assertEqual(after_bad["workspace_revision"], initial_revision)
            self.assertEqual(good["workspace"]["workspace_revision"], initial_revision + 1)
            self.assertEqual(same["status"], "unchanged")

    def test_stale_historical_revision_workspace_and_history_snapshot_remain_unchanged(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            save_document_content_curation_change(record.document_id, {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}}, root=root / "store")
            history_before = copy.deepcopy(load_document_content_curation_revision(record.document_id, 1, root=root / "store")["revision_record"])
            _write_chunk(root, record.document_id, f"chunk_{record.document_id}_0004", 4, 2, 2, "New text")
            build_document_content_map(record.document_id, regenerate=True, root=root / "store")

            result = create_rebase_workspace_from_historical_revision(record.document_id, 1, root=root / "store")
            refreshed = refresh_document_content_rebase_conflicts(record.document_id, result["workspace"]["workspace_id"], root=root / "store")
            history_after = load_document_content_curation_revision(record.document_id, 1, root=root / "store")["revision_record"]

            self.assertEqual(result["status"], "draft")
            self.assertIn(refreshed["status"], {"ready", "ready_with_warnings", "unresolved"})
            self.assertEqual(history_before, history_after)

    def test_ready_workspace_commits_new_revision_and_existing_behaviors_hold(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            record, _ = _build_detected_map(root)
            save_document_content_curation_change(record.document_id, {"target_type": "chapter", "target_id": "chapter_001", "operation": "rename", "value": {"title": "Identity Controls"}}, root=root / "store")
            overlay_path = root / "store" / "document_content_curation" / f"{record.document_id}.json"
            payload = json.loads(overlay_path.read_text(encoding="utf-8"))
            payload["chapter_title_overrides"]["chapter_missing"] = "Ghost"
            payload["changes"] = []
            overlay_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            stale_source = copy.deepcopy(json.loads(overlay_path.read_text(encoding="utf-8")))

            created = create_rebase_workspace_from_current_stale_curation(record.document_id, root=root / "store")
            refreshed = refresh_document_content_rebase_conflicts(record.document_id, created["workspace"]["workspace_id"], root=root / "store")
            conflict_id = next(item["conflict_id"] for item in refreshed["workspace"]["conflicts"] if item["conflict_type"] == "missing_chapter")
            apply_document_content_rebase_resolution(record.document_id, created["workspace"]["workspace_id"], conflict_id, {"action": "drop"}, root=root / "store")
            readiness = get_document_content_rebase_readiness(record.document_id, created["workspace"]["workspace_id"], root=root / "store")
            committed = commit_document_content_rebase_workspace(record.document_id, created["workspace"]["workspace_id"], root=root / "store")
            current = load_document_content_curation(record.document_id, root=root / "store")["curation"]
            history = list_document_content_curation_revisions(record.document_id, root=root / "store")
            second_commit = commit_document_content_rebase_workspace(record.document_id, created["workspace"]["workspace_id"], root=root / "store")

            _write_chunk(root, record.document_id, f"chunk_{record.document_id}_0004", 4, 2, 2, "New text")
            build_document_content_map(record.document_id, regenerate=True, root=root / "store")
            stale_workspace = create_rebase_workspace_from_current_stale_curation(record.document_id, root=root / "store")
            refresh_document_content_rebase_conflicts(record.document_id, stale_workspace["workspace"]["workspace_id"], root=root / "store")
            _write_chunk(root, record.document_id, f"chunk_{record.document_id}_0005", 5, 3, 3, "More text")
            build_document_content_map(record.document_id, regenerate=True, root=root / "store")
            stale_again = refresh_document_content_rebase_conflicts(record.document_id, stale_workspace["workspace"]["workspace_id"], root=root / "store")
            abandoned = abandon_document_content_rebase_workspace(record.document_id, stale_workspace["workspace"]["workspace_id"], root=root / "store")
            abandoned_commit = commit_document_content_rebase_workspace(record.document_id, stale_workspace["workspace"]["workspace_id"], root=root / "store")
            report = format_document_content_rebase_report(record.document_id, stale_workspace["workspace"]["workspace_id"], root=root / "store")
            curated = build_curated_document_content_map(record.document_id, root=root / "store")

            self.assertIn(readiness["status"], {"ready", "ready_with_warnings"})
            self.assertEqual(committed["status"], "committed")
            self.assertEqual(current["curation_revision"], 2)
            self.assertEqual(current["rebase_provenance"]["rebase_workspace_id"], created["workspace"]["workspace_id"])
            self.assertEqual(history["count"], 2)
            self.assertEqual(stale_source["curation_revision"], 1)
            self.assertEqual(second_commit["status"], "conflict")
            self.assertEqual(stale_again["status"], "stale_again")
            self.assertEqual(abandoned["status"], "abandoned")
            self.assertEqual(abandoned_commit["status"], "failed")
            self.assertNotIn(str(root), report)
            self.assertFalse(curated["curation_applied"])
