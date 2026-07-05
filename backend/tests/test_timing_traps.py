from __future__ import annotations

from datetime import timedelta
import unittest

from backend.electional.analysis.timing_traps import detect_timing_traps
from backend.tests._advanced_analysis_fixtures import fixture_snapshot, set_planet


def sample(offset: int, score: int):
    item = fixture_snapshot(score=score)
    item["date"] = item["date"] + timedelta(minutes=offset)
    return item


class TimingTrapTest(unittest.TestCase):
    def test_timing_trap_score_cliff(self) -> None:
        current = sample(0, 92)
        traps = detect_timing_traps(current, [sample(8, 70)])
        self.assertIn("score_cliff", [trap.trap_type for trap in traps.traps])

    def test_timing_trap_hard_gate_approaching(self) -> None:
        hard = sample(6, 82)
        hard["hardReject"] = True
        traps = detect_timing_traps(sample(0, 88), [hard])
        self.assertIn("hard_gate_approaching", [trap.trap_type for trap in traps.traps])

    def test_timing_trap_malefic_approaching_angle(self) -> None:
        mars = sample(9, 82)
        set_planet(mars, "Mars", isAngular=True, closestAngle={"shortName": "ASC", "distance": 2})
        traps = detect_timing_traps(sample(0, 88), [mars])
        self.assertIn("malefic_angle_approaching", [trap.trap_type for trap in traps.traps])

    def test_timing_trap_moon_void_soon(self) -> None:
        moon = sample(12, 80)
        moon["moonCondition"] = {"voidOfCourse": {"isVoid": True}}
        traps = detect_timing_traps(sample(0, 88), [moon])
        self.assertIn("moon_void_soon", [trap.trap_type for trap in traps.traps])

    def test_timing_trap_benefic_leaving_angle(self) -> None:
        later = sample(8, 86)
        set_planet(later, "Jupiter", isAngular=False)
        set_planet(later, "Venus", isAngular=False)
        traps = detect_timing_traps(sample(0, 88), [later])
        self.assertIn("benefic_leaving_angle", [trap.trap_type for trap in traps.traps])

    def test_timing_trap_control_index_drop(self) -> None:
        current = sample(0, 88)
        current["advancedAnalysis"] = {"control_index": {"control_score": 72}}
        later = sample(8, 80)
        later["advancedAnalysis"] = {"control_index": {"control_score": 44}}
        traps = detect_timing_traps(current, [later])
        self.assertIn("control_index_cliff", [trap.trap_type for trap in traps.traps])

    def test_timing_trap_window_too_narrow(self) -> None:
        current = sample(0, 88)
        current["start_time"] = current["date"]
        current["end_time"] = current["date"] + timedelta(minutes=1)
        traps = detect_timing_traps(current, [])
        self.assertIn("window_too_narrow", [trap.trap_type for trap in traps.traps])

    def test_timing_trap_no_false_positive_stable_window(self) -> None:
        traps = detect_timing_traps(sample(0, 88), [sample(8, 87)])
        self.assertFalse([trap for trap in traps.traps if trap.severity in {"major", "critical"}])

    def test_timing_trap_missing_neighbor_data_warning(self) -> None:
        current = sample(0, 88)
        current["windowStability"] = {}
        traps = detect_timing_traps(current)
        self.assertTrue(traps.warnings)


if __name__ == "__main__":
    unittest.main()
