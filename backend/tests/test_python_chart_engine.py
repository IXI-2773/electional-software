from __future__ import annotations

import unittest

from backend.electional.chart import build_snapshot, build_transit_windows
from backend.electional.ephemeris import get_planet_positions
from backend.electional.houses import calculate_angles
from backend.electional.locations import get_location
from backend.electional.time_utils import normalize_time_text, zoned_time_to_utc


class PythonChartEngineTest(unittest.TestCase):
    def test_timezone_conversion_uses_iana_zone(self) -> None:
        moment = zoned_time_to_utc("2026-05-26", "09:00", "America/Los_Angeles")

        self.assertEqual(moment.isoformat(), "2026-05-26T16:00:00+00:00")

    def test_time_parser_accepts_desktop_am_pm_input(self) -> None:
        self.assertEqual(normalize_time_text("09:00 AM"), "09:00")
        self.assertEqual(normalize_time_text("9:30 PM"), "21:30")

    def test_ephemeris_matches_jpl_fixture_tolerance(self) -> None:
        moment = zoned_time_to_utc("2026-05-26", "09:00", "America/Los_Angeles")
        positions = {planet["name"]: planet["longitude"] for planet in get_planet_positions(moment)}

        self.assertAlmostEqual(positions["Sun"], 65.4225, delta=0.01)
        self.assertAlmostEqual(positions["Moon"], 193.2205, delta=0.01)
        self.assertAlmostEqual(positions["Mercury"], 79.3437, delta=0.01)

    def test_angles_match_swiss_fixture_tolerance(self) -> None:
        location = get_location("los-angeles")
        moment = zoned_time_to_utc("2026-05-26", "09:00", location.timezone)
        angles = {angle["id"]: angle["longitude"] for angle in calculate_angles(moment, location.latitude, location.longitude)}

        self.assertAlmostEqual(angles["asc"], 110.13511832023705, delta=0.05)
        self.assertAlmostEqual(angles["mc"], 6.5293592412573105, delta=0.05)

    def test_snapshot_and_windows_are_python_calculated(self) -> None:
        location = get_location("paris")
        snapshot = build_snapshot("2026-05-26", "09:00", location, "traditional-lilly")
        windows = build_transit_windows("2026-05-26", "09:00", location, "traditional-lilly")

        self.assertEqual(snapshot["engine"], "Astronomy Engine Python")
        self.assertEqual(len(snapshot["positions"]), 10)
        self.assertEqual(len(snapshot["angles"]), 4)
        self.assertEqual(len(windows), 6)
        self.assertGreaterEqual(windows[0]["score"], windows[-1]["score"])


if __name__ == "__main__":
    unittest.main()
