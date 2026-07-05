from __future__ import annotations

from tempfile import TemporaryDirectory
import unittest

from backend.electional.watchlists import load_watchlist, run_watchlist_scan, save_watchlist


def provider(_profile):
    return [
        {"id": "a", "grade": "A-", "practicality_score": 80, "control_score": 70, "fast_lane_command": "USE", "rarity_label": "Rare"},
        {"id": "b", "grade": "B+", "practicality_score": 80, "control_score": 70, "fast_lane_command": "REJECT"},
        {"id": "c", "grade": "A", "practicality_score": 90, "control_score": 80, "fast_lane_command": "USE", "trap_severities": ["critical"]},
        {"id": "a", "grade": "A-", "practicality_score": 80, "control_score": 70, "fast_lane_command": "USE"},
    ]


class WatchlistsTest(unittest.TestCase):
    def test_watchlist_create_scan_filters_and_no_duplicates(self) -> None:
        watchlist = {"watchlist_id": "exam_next_60_days", "profile_id": "exam_strict", "range_days": 60, "minimum_grade": "B+", "minimum_practicality": 75, "minimum_control": 65, "require_fast_lane_not_reject": True, "exclude_critical_traps": True}
        result = run_watchlist_scan(watchlist, provider, profile={"profile_id": "exam_strict", "version": "profile_v1"})
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["window_id"], "a")
        self.assertTrue(result["rare_windows_found"])
        self.assertEqual(result["results"][0]["profile_version"], "profile_v1")

    def test_watchlist_save_load_and_detects_downgrade(self) -> None:
        with TemporaryDirectory() as tmp:
            watchlist = {"watchlist_id": "w", "profile_id": "exam_strict", "range_days": 60, "results": [{"window_id": "a", "grade": "A"}]}
            save_watchlist(watchlist, root=tmp)
            loaded = load_watchlist("w", root=tmp)
            result = run_watchlist_scan(loaded, lambda _p: [{"id": "a", "grade": "B+", "practicality_score": 0, "control_score": 0}])
            self.assertTrue(result["windows_downgraded"])


if __name__ == "__main__":
    unittest.main()
