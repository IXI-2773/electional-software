from __future__ import annotations

from datetime import timedelta
import unittest

from backend.electional.analysis.final_command import build_final_command
from backend.electional.analysis.practicality import build_practicality_report
from backend.electional.analysis.timing_traps import detect_timing_traps
from backend.electional.analysis.action_moment import resolve_action_moment
from backend.tests._advanced_analysis_fixtures import fixture_snapshot


def window(score: int = 88, *, minutes: int = 30, confidence: int = 84, fragility: str = "Low"):
    item = fixture_snapshot(score=score, confidence=confidence, fragility=fragility)
    item["start_time"] = item["date"]
    item["end_time"] = item["date"] + timedelta(minutes=minutes)
    item["peak_time"] = item["date"] + timedelta(minutes=minutes // 2)
    return item


def command_for(item, population=None, emergency=False):
    traps = detect_timing_traps(item, population)
    action = resolve_action_moment(item.get("objective"))
    practicality = build_practicality_report(item, action, traps)
    return build_final_command(item, traps=traps, practicality=practicality, candidates=population, emergency_mode=emergency)


class FinalCommandTest(unittest.TestCase):
    def test_final_command_hard_reject(self) -> None:
        item = window()
        item["hardReject"] = True

        command = command_for(item)

        self.assertEqual(command.command, "REJECT")

    def test_final_command_clean_use(self) -> None:
        command = command_for(window(88, minutes=14))

        self.assertEqual(command.command, "USE")

    def test_final_command_wide_window(self) -> None:
        command = command_for(window(88, minutes=45))

        self.assertEqual(command.command, "USE_WIDE_WINDOW")

    def test_final_command_fragile_peak(self) -> None:
        command = command_for(window(91, minutes=4, fragility="High"))

        self.assertEqual(command.command, "REQUIRES_EXACT_TIMING")
        self.assertTrue(command.exact_action_required)

    def test_final_command_least_bad(self) -> None:
        command = command_for(window(72), emergency=True)

        self.assertEqual(command.command, "LEAST_BAD_ONLY")

    def test_final_command_low_data_confidence(self) -> None:
        command = command_for(window(91, confidence=45))

        self.assertEqual(command.command, "NEEDS_MORE_DATA")

    def test_final_command_no_window_found(self) -> None:
        command = build_final_command(None)

        self.assertEqual(command.command, "SEARCH_NEXT_DAY")

    def test_final_command_better_window_tomorrow(self) -> None:
        current = window(78)
        better = window(91)
        better["date"] = current["date"] + timedelta(hours=4)
        population = [current, better]

        command = command_for(current, population)

        self.assertEqual(command.command, "WAIT")


if __name__ == "__main__":
    unittest.main()
