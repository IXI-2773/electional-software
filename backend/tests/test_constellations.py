from __future__ import annotations

import unittest

from backend.electional.chart import build_snapshot
from backend.electional.constellations import constellation_for_longitude
from backend.electional.ephemeris import get_zodiac_position_for_system
from backend.electional.locations import get_location
from backend.electional.time_utils import zoned_time_to_utc


class ConstellationDiagnosticsTests(unittest.TestCase):
    def test_constellation_lookup_uses_unequal_spans(self) -> None:
        scorpius = constellation_for_longitude(248)
        virgo = constellation_for_longitude(190)

        self.assertEqual(scorpius["name"], "Scorpius")
        self.assertLess(scorpius["spanDegrees"], 30)
        self.assertEqual(virgo["name"], "Virgo")
        self.assertGreater(virgo["spanDegrees"], 30)

    def test_snapshot_includes_constellation_and_rising_context(self) -> None:
        location = get_location("paris")
        snapshot = build_snapshot("2026-05-26", "09:00", location, "traditional-lilly")
        context = snapshot["constellationContext"]
        rising = context["rising"]

        self.assertIn("constellation", snapshot["positions"][0])
        self.assertIn("constellation", snapshot["angles"][0])
        self.assertIn("ascendantSpeedDegPerHour", rising)
        self.assertIn("currentConstellationRisingMinutes", rising)
        self.assertIn("currentSignRisingMinutes", rising)
        self.assertIn("constellationContext", snapshot["ruleEvaluations"])
        self.assertIn("not full sky-polygon outlines", context["sourceNote"])
        self.assertIsInstance(rising["scoreImpact"], float)

    def test_true_13_sign_rounding_rolls_cleanly_to_next_constellation(self) -> None:
        moment = zoned_time_to_utc("2026-06-05", "13:09", "America/Los_Angeles")

        position = get_zodiac_position_for_system(
            90.9999999,
            moment,
            "true-13-sign",
            tropical_longitude=90.9999999,
        )

        self.assertEqual(position["sign"], "Gemini")
        self.assertEqual(position["degree"], 0)
        self.assertEqual(position["minute"], 0)
        self.assertEqual(position["spanDegrees"], 29.0)

    def test_true_13_sign_rounding_handles_wraparound_boundary(self) -> None:
        moment = zoned_time_to_utc("2026-06-05", "13:09", "America/Los_Angeles")

        position = get_zodiac_position_for_system(
            28.9999999,
            moment,
            "true-13-sign",
            tropical_longitude=28.9999999,
        )

        self.assertEqual(position["sign"], "Aries")
        self.assertEqual(position["degree"], 0)
        self.assertEqual(position["spanDegrees"], 25.0)


if __name__ == "__main__":
    unittest.main()
