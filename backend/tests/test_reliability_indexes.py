from __future__ import annotations

from tempfile import TemporaryDirectory
import unittest

from backend.electional.reliability.audit_snapshot import build_audit_snapshot
from backend.electional.reliability.indexes import check_indexes, load_index, rebuild_indexes
from backend.electional.reliability.storage import ensure_reliability_storage, save_audit_snapshot
from backend.tests.test_audit_snapshot import full_snapshot


class ReliabilityIndexesTest(unittest.TestCase):
    def test_snapshot_index_created_updated_and_includes_fast_lane_flag(self) -> None:
        with TemporaryDirectory() as tmp:
            result = save_audit_snapshot(build_audit_snapshot(full_snapshot()), root=tmp, election_id="idx")
            index = load_index(tmp, "snapshot")
            self.assertTrue(index["entries"])
            self.assertTrue(index["entries"][0]["has_fast_lane"])
            self.assertEqual(index["entries"][0]["path"], str(result.path))

    def test_index_does_not_update_on_failed_write(self) -> None:
        with TemporaryDirectory() as tmp:
            audit = build_audit_snapshot(full_snapshot())
            save_audit_snapshot(audit, root=tmp, election_id="same")
            before = load_index(tmp, "snapshot")
            with self.assertRaises(FileExistsError):
                save_audit_snapshot(audit, root=tmp, election_id="same")
            self.assertEqual(before, load_index(tmp, "snapshot"))

    def test_index_detects_missing_file_and_unindexed_file(self) -> None:
        with TemporaryDirectory() as tmp:
            result = save_audit_snapshot(build_audit_snapshot(full_snapshot()), root=tmp, election_id="missing")
            result.path.unlink()
            status = check_indexes(tmp)
            self.assertTrue(status["missing_indexed_files"])
            root = ensure_reliability_storage(tmp)
            (root / "audit_snapshots" / "loose.json").write_text("{}", encoding="utf-8")
            status = check_indexes(tmp)
            self.assertTrue(status["unindexed_files"])

    def test_index_rebuild_controlled_folder_only(self) -> None:
        with TemporaryDirectory() as tmp:
            save_audit_snapshot(build_audit_snapshot(full_snapshot()), root=tmp, election_id="rebuild")
            rebuilt = rebuild_indexes(tmp)
            self.assertEqual(len(rebuilt["snapshot"]), 1)


if __name__ == "__main__":
    unittest.main()
