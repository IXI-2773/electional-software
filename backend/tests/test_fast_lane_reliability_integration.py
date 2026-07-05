from __future__ import annotations

import copy
import unittest

from backend.electional.reliability.audit_snapshot import build_audit_snapshot
from backend.electional.reliability.dashboard import build_reliability_dashboard
from backend.electional.reliability.regression_replay import compare_regression_snapshots
from backend.electional.reliability.review_queue import build_review_queue
from backend.tests.test_audit_snapshot import full_snapshot


class FastLaneReliabilityIntegrationTest(unittest.TestCase):
    def test_fast_lane_in_audit_snapshot_and_json_export(self) -> None:
        audit = build_audit_snapshot(full_snapshot())["audit_snapshot"]
        fast = audit["phase2_tactical_analysis"]["fast_lane"]
        self.assertIn("command", fast)
        self.assertIn("hard_gate_status", fast)

    def test_fast_lane_regression_command_best_minute_and_hard_reject_drift(self) -> None:
        old = full_snapshot()
        new = copy.deepcopy(old)
        new["tacticalAnalysis"]["fast_lane"]["command"] = "REJECT"
        new["tacticalAnalysis"]["fast_lane"]["best"] = "11:30 AM"
        new["hardReject"] = True
        result = compare_regression_snapshots(old, new)
        self.assertTrue(any(item["category"] == "phase2_fast_lane_drift" for item in result["drifts"]))
        self.assertTrue(any(item["severity"] == "critical" for item in result["drifts"]))

    def test_fast_lane_in_reliability_dashboard_and_review_item(self) -> None:
        replay = {"drifts": [{"category": "phase2_fast_lane_drift", "severity": "critical", "title": "Fast Lane drift"}]}
        dashboard = build_reliability_dashboard(replay_result=replay)
        review = build_review_queue(replay_drift=replay["drifts"])
        self.assertEqual(dashboard["fast_lane_drift_status"]["status"], "drift")
        self.assertEqual(review[0].item_type, "phase2_fast_lane_drift")


if __name__ == "__main__":
    unittest.main()
