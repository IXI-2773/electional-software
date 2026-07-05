from __future__ import annotations

import unittest

from backend.electional.reliability.dashboard import build_reliability_dashboard, format_reliability_dashboard


class ReliabilityDashboardTest(unittest.TestCase):
    def test_dashboard_shows_feature_registry_phase_coverage_and_fast_lane(self) -> None:
        dashboard = build_reliability_dashboard()
        text = format_reliability_dashboard(dashboard)
        self.assertIn("feature_registry_summary", dashboard)
        self.assertIn("phase_coverage_audit", dashboard)
        self.assertIn("fast_lane_status", dashboard)
        self.assertIn("Fast Lane", text)

    def test_dashboard_shows_fast_lane_drift(self) -> None:
        dashboard = build_reliability_dashboard(replay_result={"drifts": [{"category": "phase2_fast_lane_drift"}]})
        self.assertEqual(dashboard["fast_lane_drift_status"]["status"], "drift")

    def test_dashboard_shows_phase_signal_calibration(self) -> None:
        dashboard = build_reliability_dashboard(outcomes=[{"outcome_score": 80}])
        self.assertIn("outcome_calibration", dashboard)
        self.assertIn("rule_performance", dashboard)


if __name__ == "__main__":
    unittest.main()
