from __future__ import annotations

from datetime import timedelta
import unittest

from backend.electional.analysis.fast_lane import format_fast_lane_text
from backend.electional.analysis.tactical import build_tactical_analysis_report
from backend.tests._advanced_analysis_fixtures import fixture_snapshot


def tactical(score: int = 88, *, hard: bool = False, confidence: int = 84, emergency: bool = False):
    item = fixture_snapshot(score=score, confidence=confidence)
    item["start_time"] = item["date"]
    item["end_time"] = item["date"] + timedelta(minutes=20)
    if hard:
        item["hardReject"] = True
    return build_tactical_analysis_report(item, emergency_mode=emergency)


class FastLaneTest(unittest.TestCase):
    def test_fast_lane_use(self) -> None:
        report = tactical()
        self.assertIn(report.fast_lane.command, {"USE", "USE_WIDE_WINDOW"})

    def test_fast_lane_reject(self) -> None:
        self.assertEqual(tactical(hard=True).fast_lane.command, "REJECT")

    def test_fast_lane_least_bad(self) -> None:
        self.assertEqual(tactical(72, emergency=True).fast_lane.command, "LEAST_BAD_ONLY")

    def test_fast_lane_low_data_confidence(self) -> None:
        self.assertEqual(tactical(91, confidence=45).fast_lane.command, "NEEDS_MORE_DATA")

    def test_fast_lane_includes_action_moment(self) -> None:
        text = format_fast_lane_text(tactical().fast_lane)
        self.assertIn("Action:", text)

    def test_fast_lane_respects_hard_gate(self) -> None:
        text = format_fast_lane_text(tactical(hard=True).fast_lane)
        self.assertIn("REJECT", text)


if __name__ == "__main__":
    unittest.main()
