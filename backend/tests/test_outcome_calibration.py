from __future__ import annotations

import unittest

from backend.electional.analysis.advanced import build_advanced_analysis_report
from backend.electional.analysis.tactical import build_tactical_analysis_report
from backend.electional.reliability.calibration import build_outcome_calibration
from backend.tests._advanced_analysis_fixtures import add_aspect, fixture_snapshot


def record(score: int, command: str = "USE"):
    snapshot = fixture_snapshot()
    add_aspect(snapshot, "Moon", "Jupiter", label="Moon trine Jupiter")
    snapshot["advancedAnalysis"] = build_advanced_analysis_report(snapshot).to_json()
    snapshot["tacticalAnalysis"] = build_tactical_analysis_report(snapshot).to_json()
    snapshot["tacticalAnalysis"]["fast_lane"]["command"] = command
    snapshot["tacticalAnalysis"]["final_command"]["command"] = command
    snapshot["outcome_score"] = score
    return snapshot


class OutcomeCalibrationTest(unittest.TestCase):
    def test_calibration_fast_lane_by_command(self) -> None:
        calibration = build_outcome_calibration([record(81, "USE"), record(43, "LEAST_BAD_ONLY")])
        self.assertIn("USE", calibration["fast_lane_by_command"])

    def test_calibration_final_command_by_command(self) -> None:
        calibration = build_outcome_calibration([record(70, "USE_IF_NECESSARY")])
        self.assertIn("USE_IF_NECESSARY", calibration["final_command_by_command"])

    def test_calibration_practicality_timing_control_resistance_and_contamination(self) -> None:
        calibration = build_outcome_calibration([record(80)])
        self.assertTrue(calibration["practicality_by_band"])
        self.assertTrue(calibration["timing_trap_by_severity"])
        self.assertTrue(calibration["control_index_by_band"])
        self.assertTrue(calibration["resistance_advantage"])
        self.assertTrue(calibration["contaminated_benefic"])
        self.assertTrue(calibration["action_moment_controllability"])

    def test_calibration_small_sample_warning(self) -> None:
        calibration = build_outcome_calibration([record(80)])
        self.assertTrue(calibration["warnings"])


if __name__ == "__main__":
    unittest.main()
