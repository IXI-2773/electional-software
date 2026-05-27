from __future__ import annotations

import unittest

from backend.electional.point_sets import get_point_set, visible_lots_for_point_set, visible_planets_for_point_set


class PointSetTest(unittest.TestCase):
    def test_classical_point_set_filters_outer_planets(self) -> None:
        point_set = get_point_set("Classical 7")
        positions = [{"name": "Sun"}, {"name": "Saturn"}, {"name": "Uranus"}, {"name": "Pluto"}]

        visible = visible_planets_for_point_set(positions, point_set)

        self.assertEqual([point["name"] for point in visible], ["Sun", "Saturn"])

    def test_planets_fortune_only_shows_fortune_lot(self) -> None:
        point_set = get_point_set("planets-fortune")
        lots = [{"name": "Part of Fortune"}, {"name": "Part of Spirit"}]

        visible = visible_lots_for_point_set(lots, point_set)

        self.assertEqual([lot["name"] for lot in visible], ["Part of Fortune"])

    def test_unknown_point_set_falls_back_to_ten_planets(self) -> None:
        point_set = get_point_set("missing")

        self.assertEqual(point_set.name, "10 Planets")
        self.assertFalse(point_set.show_nodes)


if __name__ == "__main__":
    unittest.main()
