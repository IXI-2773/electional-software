from __future__ import annotations

import unittest

from backend.electional.aspects import detect_aspects
from backend.electional.lots import calculate_lots, lot_longitude
from backend.electional.presets import (
    apply_dignities,
    filter_positions_for_preset,
    get_essential_dignity,
    get_preset,
    summarize_orb,
)
from backend.electional.scoring import score_window


def position(name: str, longitude: float, sign: str, is_angular: bool = False, distance: float = 8) -> dict:
    return {
        "name": name,
        "longitude": longitude,
        "zodiac": {"sign": sign, "degree": int(longitude % 30), "minute": 0},
        "isAngular": is_angular,
        "closestAngle": {"shortName": "ASC", "distance": distance},
    }


class ElectionalCoreTest(unittest.TestCase):
    def test_transit_one_degree_detects_only_tight_contacts(self) -> None:
        preset = get_preset("transit-1-degree")
        tight = [
            position("Sun", 10, "Aries"),
            position("Moon", 10.5, "Aries"),
            position("Mars", 12, "Aries"),
        ]

        detected = detect_aspects(tight, preset.aspect_ids, preset.aspect_orbs)

        labels = [aspect["label"] for aspect in detected]
        self.assertIn("Sun conjunction Moon", labels)
        self.assertNotIn("Sun conjunction Mars", labels)
        self.assertEqual(summarize_orb(preset), "1 deg")

    def test_traditional_lilly_filters_outer_planets(self) -> None:
        preset = get_preset("traditional-lilly")
        positions = [
            position("Sun", 120, "Leo"),
            position("Saturn", 300, "Aquarius"),
            position("Uranus", 300, "Aquarius"),
        ]

        filtered = filter_positions_for_preset(positions, preset)

        self.assertEqual([planet["name"] for planet in filtered], ["Sun", "Saturn"])

    def test_essential_dignities(self) -> None:
        self.assertEqual(get_essential_dignity(position("Sun", 120, "Leo"))["label"], "Domicile")
        self.assertEqual(get_essential_dignity(position("Mars", 270, "Capricorn"))["label"], "Exalted")
        self.assertEqual(get_essential_dignity(position("Venus", 150, "Virgo"))["label"], "Fall")

    def test_score_window_returns_integer_in_bounds(self) -> None:
        preset = get_preset("medieval-electional")
        positions = apply_dignities(
            [
                position("Jupiter", 95, "Cancer", is_angular=True, distance=1),
                position("Venus", 350, "Pisces"),
                position("Mars", 270, "Capricorn"),
            ],
            preset,
        )
        detected = [
            {
                "aspectId": "trine",
                "tone": "support",
                "orb": 0.5,
            }
        ]

        score = score_window(detected, positions, preset)

        self.assertIsInstance(score, int)
        self.assertGreaterEqual(score, 10)
        self.assertLessEqual(score, 99)

    def test_lot_longitude_wraps_around_zodiac(self) -> None:
        self.assertEqual(lot_longitude(350, 20, 40), 330)
        self.assertEqual(lot_longitude(10, 350, 20), 340)

    def test_calculate_lots_returns_fortune_and_spirit(self) -> None:
        positions = [
            {**position("Sun", 120, "Leo"), "house": 10},
            {**position("Moon", 90, "Cancer"), "house": 9},
        ]
        angles = [
            {"id": "asc", "name": "Ascendant", "shortName": "ASC", "longitude": 30},
            {"id": "mc", "name": "Midheaven", "shortName": "MC", "longitude": 120},
            {"id": "dsc", "name": "Descendant", "shortName": "DSC", "longitude": 210},
            {"id": "ic", "name": "Imum Coeli", "shortName": "IC", "longitude": 300},
        ]
        house_cusps = [{"house": index + 1, "longitude": index * 30} for index in range(12)]

        lots = calculate_lots(positions, angles, house_cusps, "equal-house")

        self.assertEqual([lot["name"] for lot in lots], ["Part of Fortune", "Part of Spirit"])
        self.assertEqual(lots[0]["longitude"], 0)
        self.assertEqual(lots[0]["formula"], "ASC + Moon - Sun")


if __name__ == "__main__":
    unittest.main()
