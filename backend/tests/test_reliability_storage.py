from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.electional.reliability.audit_snapshot import build_audit_snapshot
from backend.electional.reliability.storage import (
    ensure_reliability_storage,
    load_reliability_object,
    save_audit_snapshot,
    save_outcome_log,
    save_replay_result,
    save_review_queue,
    save_reliability_object,
)
from backend.tests.test_audit_snapshot import full_snapshot


class ReliabilityStorageTest(unittest.TestCase):
    def test_storage_creates_directories(self) -> None:
        with TemporaryDirectory() as tmp:
            root = ensure_reliability_storage(tmp)
            for name in ("audit_snapshots", "outcome_logs", "replay_results", "review_queue", "calibration_reports", "rule_performance", "indexes", "quarantine"):
                self.assertTrue((root / name).is_dir())

    def test_save_load_audit_snapshot_outcome_replay_and_review_queue(self) -> None:
        with TemporaryDirectory() as tmp:
            audit = build_audit_snapshot(full_snapshot())
            audit_result = save_audit_snapshot(audit, root=tmp, election_id="exam_2026_07_14")
            outcome_result = save_outcome_log({"outcome_score": 80}, root=tmp, election_id="exam_2026_07_14")
            replay_result = save_replay_result({"run_id": "run1", "results": []}, root=tmp, run_id="run1")
            queue_result = save_review_queue([{"item_type": "x"}], root=tmp)

            self.assertEqual(load_reliability_object(audit_result.path)["object_type"], "audit_snapshot")
            self.assertEqual(load_reliability_object(outcome_result.path)["object_type"], "outcome_log")
            self.assertEqual(load_reliability_object(replay_result.path)["object_type"], "replay_result")
            self.assertEqual(load_reliability_object(queue_result.path)["object_type"], "review_queue")

    def test_immutable_snapshot_not_overwritten_and_explicit_overwrite_allowed(self) -> None:
        with TemporaryDirectory() as tmp:
            audit = build_audit_snapshot(full_snapshot())
            save_audit_snapshot(audit, root=tmp, election_id="immutable")
            with self.assertRaises(FileExistsError):
                save_audit_snapshot(audit, root=tmp, election_id="immutable")
            result = save_audit_snapshot(audit, root=tmp, election_id="immutable", overwrite=True)
            self.assertTrue(result.path.exists())

    def test_atomic_write_temp_removed(self) -> None:
        with TemporaryDirectory() as tmp:
            result = save_outcome_log({"outcome_score": 70}, root=tmp, election_id="atomic")
            self.assertFalse(result.path.with_name(f".{result.path.name}.tmp").exists())

    def test_corrupt_existing_file_quarantined_when_allowed(self) -> None:
        with TemporaryDirectory() as tmp:
            root = ensure_reliability_storage(tmp)
            path = root / "outcome_logs" / "corrupt.json"
            path.write_text("{bad", encoding="utf-8")
            result = save_reliability_object(
                {"outcome_score": 77},
                root=tmp,
                object_type="outcome_log",
                object_id="corrupt",
                overwrite=True,
                quarantine_corrupt_existing=True,
            )
            self.assertTrue(result.path.exists())
            self.assertTrue(list((root / "quarantine").glob("*.quarantine.json")))


if __name__ == "__main__":
    unittest.main()
