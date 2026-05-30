from __future__ import annotations

import unittest

from backend.electional.chart import build_snapshot
from backend.electional.constellations import constellation_for_longitude
from backend.electional.locations import get_location


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


if __name__ == "__main__":
    unittest.main()
