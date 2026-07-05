from __future__ import annotations

import unittest

from backend.electional.reliability.review_queue import build_review_queue


class ReviewQueueTest(unittest.TestCase):
    def test_review_queue_fast_lane_and_final_command_drift_items(self) -> None:
        items = build_review_queue(replay_drift=[
            {"category": "phase2_fast_lane_drift", "severity": "critical", "title": "Fast Lane changed"},
            {"category": "phase2_command_drift", "severity": "major", "title": "Final Command changed"},
        ])
        self.assertIn("phase2_fast_lane_drift", [item.item_type for item in items])
        self.assertIn("phase2_command_drift", [item.item_type for item in items])

    def test_review_queue_phase_coverage_missing_feature_item(self) -> None:
        items = build_review_queue(coverage_audit={"missing_features": [{"feature_id": "x", "name": "X"}]})
        self.assertEqual(items[0].item_type, "phase_coverage_missing_feature")

    def test_review_queue_control_index_and_timing_trap_drift_items(self) -> None:
        items = build_review_queue(replay_drift=[
            {"category": "phase1_control_index_drift", "severity": "major"},
            {"category": "phase2_timing_trap_drift", "severity": "major"},
        ])
        self.assertIn("phase1_control_index_drift", [item.item_type for item in items])
        self.assertIn("phase2_timing_trap_drift", [item.item_type for item in items])


if __name__ == "__main__":
    unittest.main()
