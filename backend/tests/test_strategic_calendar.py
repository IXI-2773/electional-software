from __future__ import annotations

from datetime import timedelta
import unittest

from backend.electional.analysis.tactical import annotate_tactical_analysis
from backend.electional.analysis.strategic_calendar import build_strategic_calendar, format_strategic_calendar_text
from backend.tests._advanced_analysis_fixtures import fixture_snapshot


def tactical_window(offset: int, score: int, objective: str = "Exam / certification"):
    item = fixture_snapshot(objective=objective, score=score)
    item["date"] = item["date"] + timedelta(hours=offset)
    item["start_time"] = item["date"]
    item["end_time"] = item["date"] + timedelta(minutes=30)
    return annotate_tactical_analysis([item])[0]


class StrategicCalendarTest(unittest.TestCase):
    def test_strategic_calendar_daily(self) -> None:
        report = build_strategic_calendar([tactical_window(0, 88)], view="daily")
        self.assertEqual(report.view, "daily")
        self.assertTrue(report.entries)

    def test_strategic_calendar_weekly(self) -> None:
        report = build_strategic_calendar([tactical_window(0, 88), tactical_window(24, 82)], view="weekly")
        self.assertIn("weekly", report.summary)

    def test_strategic_calendar_monthly(self) -> None:
        report = build_strategic_calendar([tactical_window(0, 88)], view="monthly")
        self.assertIn("Monthly", format_strategic_calendar_text(report))

    def test_strategic_calendar_avoid_entries(self) -> None:
        item = tactical_window(0, 88)
        item["tacticalAnalysis"]["final_command"]["command"] = "REJECT"
        report = build_strategic_calendar([item])
        self.assertTrue(report.avoid_entries)

    def test_strategic_calendar_tags(self) -> None:
        report = build_strategic_calendar([tactical_window(0, 88)])
        self.assertIn("good_for_exam", report.entries[0].tags)

    def test_strategic_calendar_rare_window(self) -> None:
        item = tactical_window(0, 88)
        item["rarity"] = {"rarity_label": "Rare", "rarity_score": 90}
        report = build_strategic_calendar([item])
        self.assertIn("rare_window", report.entries[0].tags)

    def test_strategic_calendar_least_bad(self) -> None:
        item = tactical_window(0, 72)
        item["tacticalAnalysis"]["final_command"]["command"] = "LEAST_BAD_ONLY"
        report = build_strategic_calendar([item])
        self.assertIn("least_bad", report.entries[0].tags)


if __name__ == "__main__":
    unittest.main()
