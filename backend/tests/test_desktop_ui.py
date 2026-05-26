from __future__ import annotations

import unittest

from backend.electional.desktop import (
    DEFAULT_TIMEZONE,
    build_custom_location,
    default_location_for_timezone,
    planet_abbreviation,
    validate_election_inputs,
    wheel_degrees,
)


class DesktopUiHelpersTest(unittest.TestCase):
    def test_planet_abbreviation_uses_compact_labels(self) -> None:
        self.assertEqual(planet_abbreviation("Mercury"), "Me")
        self.assertEqual(planet_abbreviation("Pluto"), "Pl")

    def test_wheel_degrees_places_ascendant_on_left_side(self) -> None:
        self.assertEqual(wheel_degrees(110.0, 110.0), 180)
        self.assertEqual(wheel_degrees(290.0, 110.0), 0)

    def test_validation_accepts_am_pm_time_and_custom_location(self) -> None:
        errors = validate_election_inputs("2026-05-26", "09:00 AM", "34.0522", "-118.2437", "America/Los_Angeles")
        location = build_custom_location("Launch Site", "34.0522", "-118.2437", "America/Los_Angeles")

        self.assertEqual(errors, [])
        self.assertEqual(location.name, "Launch Site")
        self.assertEqual(location.timezone, "America/Los_Angeles")

    def test_validation_reports_bad_coordinate_and_timezone(self) -> None:
        errors = validate_election_inputs("05/26/2026", "morning", "120", "not-west", "Pacific Time")

        self.assertIn("Date must use YYYY-MM-DD.", errors)
        self.assertIn("Time must look like 09:00 or 09:00 AM.", errors)
        self.assertIn("Latitude must be between -90 and 90.", errors)
        self.assertIn("Longitude must be a number.", errors)
        self.assertIn("Time zone must be a valid IANA name like America/Los_Angeles.", errors)

    def test_default_location_matches_local_timezone(self) -> None:
        location = default_location_for_timezone(DEFAULT_TIMEZONE)

        self.assertEqual(location.timezone, "America/Los_Angeles")
        self.assertEqual(location.name, "Los Angeles, CA")


if __name__ == "__main__":
    unittest.main()
