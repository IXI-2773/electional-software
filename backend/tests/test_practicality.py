from __future__ import annotations

from datetime import timedelta
import unittest

from backend.electional.analysis.action_moment import resolve_action_moment
from backend.electional.analysis.practicality import build_practicality_report
from backend.electional.analysis.timing_traps import detect_timing_traps
from backend.tests._advanced_analysis_fixtures import fixture_snapshot


def practical_window(minutes: int, objective: str = "Email message", confidence: int = 84):
    item = fixture_snapshot(objective=objective, confidence=confidence)
    item["start_time"] = item["date"]
    item["end_time"] = item["date"] + timedelta(minutes=minutes)
    return item


class PracticalityTest(unittest.TestCase):
    def report(self, item):
        action = resolve_action_moment(item.get("objective"))
        traps = detect_timing_traps(item, [])
        return build_practicality_report(item, action, traps)

    def test_practicality_wide_user_controlled_window(self) -> None:
        report = self.report(practical_window(45, "Email message"))
        self.assertGreaterEqual(report.score or 0, 75)

    def test_practicality_fragile_two_minute_window(self) -> None:
        item = practical_window(2, "Email message")
        item["fragility"] = {"band": "High"}
        report = self.report(item)
        self.assertLess(report.score or 100, 60)

    def test_practicality_proctor_controlled_exam(self) -> None:
        report = self.report(practical_window(15, "Exam / certification"))
        self.assertIn("Third party may control the exact start.", report.risks)

    def test_practicality_legal_portal_submit(self) -> None:
        report = self.report(practical_window(20, "Legal portal filing"))
        self.assertIn("Timestamp source is clear.", report.supports)

    def test_practicality_low_timezone_confidence(self) -> None:
        report = self.report(practical_window(20, "Email message", confidence=45))
        self.assertIn("Low data confidence.", report.risks)

    def test_practicality_unknown_data(self) -> None:
        item = fixture_snapshot()
        report = self.report(item)
        self.assertLess(report.confidence, 0.9)


if __name__ == "__main__":
    unittest.main()
