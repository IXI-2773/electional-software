from __future__ import annotations

import unittest

from backend.electional.analysis.planet_roles import resolve_planet_roles
from backend.tests._advanced_analysis_fixtures import DEFAULT_HOUSE_SIGNS, fixture_snapshot


def profile_by_name(profiles):
    return {profile.planet: profile for profile in profiles}


class PlanetRoleResolverTest(unittest.TestCase):
    def test_venus_ruling_12th_is_not_treated_as_clean_benefic(self) -> None:
        profiles = profile_by_name(resolve_planet_roles(fixture_snapshot()))

        venus = profiles["Venus"]
        self.assertIn("natural_benefic", venus.roles)
        self.assertIn("election_bad_house_lord", venus.roles)
        self.assertIn("functional_malefic", venus.roles)

    def test_jupiter_ruling_8th_is_flagged_as_contaminated(self) -> None:
        profiles = profile_by_name(resolve_planet_roles(fixture_snapshot()))

        jupiter = profiles["Jupiter"]
        self.assertIn("lord_of_8th", jupiter.roles)
        self.assertIn("functional_malefic", jupiter.roles)
        self.assertIn("contaminated", jupiter.role_summary)

    def test_saturn_ruling_matter_is_not_automatic_pure_harm(self) -> None:
        profiles = profile_by_name(resolve_planet_roles(fixture_snapshot()))

        saturn = profiles["Saturn"]
        self.assertIn("natural_malefic", saturn.roles)
        self.assertIn("lord_of_matter", saturn.roles)
        self.assertIn("functional_benefic", saturn.roles)

    def test_mercury_for_exam_objective_is_tagged_as_key_significator(self) -> None:
        profiles = profile_by_name(resolve_planet_roles(fixture_snapshot()))

        mercury = profiles["Mercury"]
        self.assertIn("lord_of_ascendant", mercury.roles)
        self.assertIn("exam_lord", mercury.roles)
        self.assertIn("communication_lord", mercury.roles)

    def test_ascendant_and_matter_lords_are_resolved(self) -> None:
        profiles = profile_by_name(resolve_planet_roles(fixture_snapshot()))

        self.assertIn("lord_of_ascendant", profiles["Mercury"].roles)
        self.assertIn("lord_of_matter", profiles["Saturn"].roles)

    def test_missing_house_data_produces_warning_not_crash(self) -> None:
        snapshot = fixture_snapshot()
        snapshot["houseCusps"] = []

        profiles = profile_by_name(resolve_planet_roles(snapshot))

        self.assertTrue(profiles["Mercury"].warnings)
        self.assertIn("Missing house cusps", profiles["Mercury"].warnings[0])

    def test_clean_jupiter_variant_drops_bad_house_contamination(self) -> None:
        house_signs = list(DEFAULT_HOUSE_SIGNS)
        house_signs[7] = "Aries"
        profiles = profile_by_name(resolve_planet_roles(fixture_snapshot(house_signs=house_signs)))

        self.assertNotIn("lord_of_8th", profiles["Jupiter"].roles)
        self.assertNotIn("functional_malefic", profiles["Jupiter"].roles)


if __name__ == "__main__":
    unittest.main()
