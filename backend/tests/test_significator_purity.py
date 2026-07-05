from __future__ import annotations

import unittest

from backend.electional.analysis.planet_roles import resolve_planet_roles
from backend.electional.analysis.significator_purity import build_significator_purity_profiles
from backend.tests._advanced_analysis_fixtures import DEFAULT_HOUSE_SIGNS, add_aspect, fixture_snapshot, set_planet


def purity_by_name(snapshot):
    roles = resolve_planet_roles(snapshot)
    return {
        profile.planet: profile
        for profile in build_significator_purity_profiles(snapshot, roles, snapshot.get("objective"))
    }


class SignificatorPurityTest(unittest.TestCase):
    def test_clean_benefic_scores_as_clean(self) -> None:
        house_signs = list(DEFAULT_HOUSE_SIGNS)
        house_signs[7] = "Aries"
        snapshot = fixture_snapshot(house_signs=house_signs)
        purity = purity_by_name(snapshot)

        self.assertEqual(purity["Jupiter"].purity_band, "clean")
        self.assertGreaterEqual(purity["Jupiter"].purity_score or 0, 85)

    def test_contaminated_benefic_scores_below_clean(self) -> None:
        purity = purity_by_name(fixture_snapshot())

        self.assertIn(purity["Jupiter"].purity_band, {"mixed", "corrupted"})
        self.assertIn("bad-house contamination", purity["Jupiter"].negative_factors)

    def test_matter_ruling_malefic_can_be_useful(self) -> None:
        purity = purity_by_name(fixture_snapshot())

        self.assertEqual(purity["Saturn"].purity_band, "useful")
        self.assertIn("controls the matter", purity["Saturn"].positive_factors)

    def test_combust_significator_is_downgraded(self) -> None:
        clean = fixture_snapshot()
        combust = fixture_snapshot()
        set_planet(combust, "Mercury", solarCondition={"phase": "combust"})

        clean_purity = purity_by_name(clean)["Mercury"]
        combust_purity = purity_by_name(combust)["Mercury"]

        self.assertLess(combust_purity.purity_score or 0, clean_purity.purity_score or 0)
        self.assertIn("combust", combust_purity.negative_factors)

    def test_cadent_lord_of_matter_is_downgraded(self) -> None:
        baseline = purity_by_name(fixture_snapshot())["Saturn"]
        snapshot = fixture_snapshot()
        set_planet(snapshot, "Saturn", house=12, isAngular=False)
        purity = purity_by_name(snapshot)

        self.assertLess(purity["Saturn"].purity_score or 0, baseline.purity_score or 0)
        self.assertTrue(any("12th house" in factor or factor == "cadent" for factor in purity["Saturn"].negative_factors))

    def test_afflicted_moon_is_downgraded(self) -> None:
        snapshot = fixture_snapshot()
        add_aspect(snapshot, "Moon", "Mars", tone="stress", label="Moon square Mars")
        purity = purity_by_name(snapshot)

        self.assertTrue(any("stress" in factor for factor in purity["Moon"].negative_factors))

    def test_missing_data_returns_unknown_with_lower_confidence(self) -> None:
        snapshot = fixture_snapshot()
        snapshot["positions"] = [position for position in snapshot["positions"] if position["name"] != "Mercury"]
        purity = purity_by_name(snapshot)

        self.assertEqual(purity["Mercury"].purity_band, "unknown")
        self.assertLess(purity["Mercury"].confidence, 0.9)


if __name__ == "__main__":
    unittest.main()
