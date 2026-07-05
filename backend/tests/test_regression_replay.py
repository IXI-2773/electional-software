from __future__ import annotations

import copy
import unittest

from backend.electional.analysis.advanced import build_advanced_analysis_report
from backend.electional.analysis.tactical import build_tactical_analysis_report
from backend.electional.reliability.regression_replay import compare_regression_snapshots
from backend.tests._advanced_analysis_fixtures import fixture_snapshot


def replay_snapshot():
    snapshot = fixture_snapshot()
    snapshot["advancedAnalysis"] = build_advanced_analysis_report(snapshot).to_json()
    snapshot["tacticalAnalysis"] = build_tactical_analysis_report(snapshot).to_json()
    return snapshot


class RegressionReplayTest(unittest.TestCase):
    def test_regression_replay_no_change(self) -> None:
        snapshot = replay_snapshot()
        result = compare_regression_snapshots(snapshot, copy.deepcopy(snapshot))
        self.assertEqual(result["status"], "unchanged")

    def test_regression_replay_phase1_purity_drift(self) -> None:
        old = replay_snapshot()
        new = copy.deepcopy(old)
        new["advancedAnalysis"]["significator_purity"][0]["purity_band"] = "hostile"
        result = compare_regression_snapshots(old, new)
        self.assertIn("phase1_purity_drift", [item["category"] for item in result["drifts"]])

    def test_regression_replay_phase1_control_index_and_resistance_drift(self) -> None:
        old = replay_snapshot()
        new = copy.deepcopy(old)
        new["advancedAnalysis"]["control_index"]["band"] = "user_lacks_control"
        new["advancedAnalysis"]["resistance_analysis"]["advantage"] = "opponent_advantage"
        result = compare_regression_snapshots(old, new)
        categories = [item["category"] for item in result["drifts"]]
        self.assertIn("phase1_control_index_drift", categories)
        self.assertIn("phase1_resistance_drift", categories)

    def test_regression_replay_phase2_final_command_and_fast_lane_drift(self) -> None:
        old = replay_snapshot()
        new = copy.deepcopy(old)
        new["tacticalAnalysis"]["final_command"]["command"] = "REJECT"
        new["tacticalAnalysis"]["fast_lane"]["command"] = "REJECT"
        result = compare_regression_snapshots(old, new)
        categories = [item["category"] for item in result["drifts"]]
        self.assertIn("phase2_command_drift", categories)
        self.assertIn("phase2_fast_lane_drift", categories)

    def test_regression_replay_phase2_timing_action_practicality_drift(self) -> None:
        old = replay_snapshot()
        new = copy.deepcopy(old)
        new["tacticalAnalysis"]["timing_traps"]["traps"] = [{"trap_type": "score_cliff", "severity": "critical"}]
        new["tacticalAnalysis"]["action_moment"]["elected_moment"] = "different"
        new["tacticalAnalysis"]["practicality"]["band"] = "impractical"
        result = compare_regression_snapshots(old, new)
        categories = [item["category"] for item in result["drifts"]]
        self.assertIn("phase2_timing_trap_drift", categories)
        self.assertIn("phase2_action_moment_drift", categories)
        self.assertIn("phase2_practicality_drift", categories)

    def test_regression_replay_fast_lane_best_minute_and_hard_reject_drift(self) -> None:
        old = replay_snapshot()
        new = copy.deepcopy(old)
        new["tacticalAnalysis"]["fast_lane"]["best"] = "11:30 AM"
        new["hardReject"] = True
        result = compare_regression_snapshots(old, new)
        self.assertTrue(any(item["severity"] == "critical" for item in result["drifts"]))


if __name__ == "__main__":
    unittest.main()
