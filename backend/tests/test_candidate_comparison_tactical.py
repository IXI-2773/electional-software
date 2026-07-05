from __future__ import annotations

from datetime import timedelta
import unittest

from backend.electional.analysis.tactical import annotate_tactical_analysis
from backend.electional.reporting import build_window_comparison_page
from backend.tests._advanced_analysis_fixtures import fixture_snapshot


def candidate(score: int, minutes: int):
    item = fixture_snapshot(score=score)
    item["start_time"] = item["date"]
    item["end_time"] = item["date"] + timedelta(minutes=minutes)
    return item


class CandidateComparisonTacticalTest(unittest.TestCase):
    def test_candidate_comparison_includes_command_and_practicality(self) -> None:
        windows = annotate_tactical_analysis([candidate(91, 4), candidate(84, 40)])
        text = build_window_comparison_page({"date": windows[0]["date"]}, windows, "Exam")

        self.assertIn("Tactical:", text)
        self.assertIn("Practicality:", text)

    def test_candidate_comparison_best_option_markers_are_available(self) -> None:
        windows = annotate_tactical_analysis([candidate(94, 4), candidate(84, 40), candidate(70, 10)])

        commands = [window["tacticalAnalysis"]["final_command"]["command"] for window in windows]
        practicalities = [window["tacticalAnalysis"]["practicality"]["score"] for window in windows]

        self.assertIn("REQUIRES_EXACT_TIMING", commands)
        self.assertEqual(max(practicalities), windows[1]["tacticalAnalysis"]["practicality"]["score"])


if __name__ == "__main__":
    unittest.main()
