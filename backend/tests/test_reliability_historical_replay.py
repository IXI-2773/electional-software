from __future__ import annotations

import copy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.electional.reliability.audit_snapshot import build_audit_snapshot
from backend.electional.reliability.historical_replay import format_historical_replay_summary, run_historical_replay
from backend.electional.reliability.storage import ensure_reliability_storage, save_audit_snapshot
from backend.tests.test_audit_snapshot import full_snapshot


def _save_snapshot(root: str, election_id: str = "exam_2026_07_14", objective: str = "Exam / certification") -> Path:
    snapshot = full_snapshot()
    snapshot["objective"] = objective
    return save_audit_snapshot(build_audit_snapshot(snapshot), root=root, election_id=election_id).path


class ReliabilityHistoricalReplayTest(unittest.TestCase):
    def test_replay_uses_audit_snapshots_default_and_no_drift(self) -> None:
        with TemporaryDirectory() as tmp:
            _save_snapshot(tmp)
            result = run_historical_replay(root=tmp)
            self.assertEqual(result["snapshots_loaded"], 1)
            self.assertEqual(result["no_change"], 1)

    def test_replay_rejects_project_root(self) -> None:
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                run_historical_replay(root=tmp, input_path=Path.cwd())

    def test_replay_accepts_specific_snapshot_file_and_does_not_mutate_source(self) -> None:
        with TemporaryDirectory() as tmp:
            path = _save_snapshot(tmp)
            before = path.read_bytes()
            result = run_historical_replay(root=tmp, input_path=path)
            self.assertEqual(result["snapshots_loaded"], 1)
            self.assertEqual(path.read_bytes(), before)

    def test_replay_skips_invalid_json_and_records_skipped_files(self) -> None:
        with TemporaryDirectory() as tmp:
            root = ensure_reliability_storage(tmp)
            _save_snapshot(tmp)
            (root / "audit_snapshots" / "bad.json").write_text("{bad", encoding="utf-8")
            result = run_historical_replay(root=tmp)
            self.assertEqual(result["snapshots_loaded"], 1)
            self.assertEqual(result["snapshots_skipped"], 1)
            self.assertTrue(result["skipped_files"])

    def test_historical_replay_hard_gate_fast_lane_phase1_phase2_and_confidence_drift(self) -> None:
        with TemporaryDirectory() as tmp:
            _save_snapshot(tmp)

            def builder(old_audit):
                current = copy.deepcopy(old_audit)
                current["hard_gates"]["status"] = "failed"
                current["phase1_advanced_analysis"]["control_index"]["band"] = "user_lacks_control"
                current["phase2_tactical_analysis"]["final_command"]["command"] = "REJECT"
                current["phase2_tactical_analysis"]["fast_lane"]["command"] = "REJECT"
                current["confidence"] = 0.4
                return current

            result = run_historical_replay(root=tmp, current_snapshot_builder=builder)
            categories = [drift["category"] for drift in result["results"][0]["replay"]["drifts"]]
            self.assertIn("hard_gate_drift", categories)
            self.assertIn("phase1_control_index_drift", categories)
            self.assertIn("phase2_command_drift", categories)
            self.assertIn("phase2_fast_lane_drift", categories)
            self.assertIn("confidence_drift", categories)
            self.assertEqual(result["critical_drift"], 1)

    def test_historical_replay_dry_run_does_not_save_and_save_result_does(self) -> None:
        with TemporaryDirectory() as tmp:
            _save_snapshot(tmp)
            dry = run_historical_replay(root=tmp, dry_run=True, save_result=True)
            self.assertFalse(list((Path(tmp) / "replay_results").glob("*.json")))
            saved = run_historical_replay(root=tmp, save_result=True)
            self.assertTrue(list((Path(tmp) / "replay_results").glob("*.json")))
            self.assertIn("Replay result saved:", format_historical_replay_summary(saved))
            self.assertNotIn("not saved", format_historical_replay_summary(saved))
            self.assertNotIn("saved_path", dry)

    def test_historical_replay_limit_and_objective_filter(self) -> None:
        with TemporaryDirectory() as tmp:
            _save_snapshot(tmp, "exam1", "Exam / certification")
            _save_snapshot(tmp, "legal1", "Legal dispute")
            limited = run_historical_replay(root=tmp, limit=1)
            filtered = run_historical_replay(root=tmp, objective="Legal dispute")
            self.assertEqual(limited["snapshots_loaded"], 1)
            self.assertEqual(filtered["snapshots_loaded"], 1)

    def test_historical_replay_create_review_items_for_major_drift(self) -> None:
        with TemporaryDirectory() as tmp:
            _save_snapshot(tmp)

            def builder(old_audit):
                current = copy.deepcopy(old_audit)
                current["phase2_tactical_analysis"]["fast_lane"]["command"] = "WAIT"
                return current

            result = run_historical_replay(root=tmp, current_snapshot_builder=builder, create_review_items=True)
            queue = Path(tmp) / "review_queue" / "review_queue.json"
            self.assertGreaterEqual(result["review_items_created"], 1)
            self.assertTrue(queue.exists())


if __name__ == "__main__":
    unittest.main()
