from __future__ import annotations

import unittest

from backend.electional.desktop import planet_abbreviation, wheel_degrees


class DesktopUiHelpersTest(unittest.TestCase):
    def test_planet_abbreviation_uses_compact_labels(self) -> None:
        self.assertEqual(planet_abbreviation("Mercury"), "Me")
        self.assertEqual(planet_abbreviation("Pluto"), "Pl")

    def test_wheel_degrees_places_ascendant_on_left_side(self) -> None:
        self.assertEqual(wheel_degrees(110.0, 110.0), 180)
        self.assertEqual(wheel_degrees(290.0, 110.0), 0)


if __name__ == "__main__":
    unittest.main()
