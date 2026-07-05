from __future__ import annotations

import unittest

from backend.electional.analysis.contradictions import detect_contradictions
from backend.electional.analysis.planet_roles import resolve_planet_roles
from backend.electional.analysis.significator_purity import build_significator_purity_profiles
from backend.tests._advanced_analysis_fixtures import DEFAULT_HOUSE_SIGNS, add_aspect, fixture_snapshot, set_planet


def contradiction_ids(snapshot):
    roles = resolve_planet_roles(snapshot)
    purity = build_significator_purity_profiles(snapshot, roles, snapshot.get("objective"))
    return {
        item.id: item
        for item in detect_contradictions(snapshot, roles, purity)
    }


class ContradictionDetectionTest(unittest.TestCase):
    def test_contaminated_benefic_contradiction(self) -> None:
        snapshot = fixture_snapshot()
        add_aspect(snapshot, "Moon", "Jupiter", label="Moon trine Jupiter")

        findings = contradiction_ids(snapshot)

        self.assertIn("benefic_contaminated_by_bad_house", findings)

    def test_strong_but_combust_mercury_contradiction(self) -> None:
        snapshot = fixture_snapshot()
        set_planet(snapshot, "Mercury", solarCondition={"phase": "combust"})

        findings = contradiction_ids(snapshot)

        self.assertIn("mercury_strong_but_combust", findings)

    def test_matter_ruling_malefic_contradiction(self) -> None:
        findings = contradiction_ids(fixture_snapshot())

        self.assertIn("matter_ruling_malefic", findings)

    def test_high_score_fragile_window_contradiction(self) -> None:
        snapshot = fixture_snapshot(score=91, fragility="High")
        findings = contradiction_ids(snapshot)

        self.assertIn("high_score_fragile_window", findings)

    def test_clean_benefic_does_not_trigger_false_contamination(self) -> None:
        house_signs = list(DEFAULT_HOUSE_SIGNS)
        house_signs[7] = "Aries"
        snapshot = fixture_snapshot(house_signs=house_signs)
        add_aspect(snapshot, "Moon", "Jupiter", label="Moon trine Jupiter")

        findings = contradiction_ids(snapshot)

        self.assertNotIn("benefic_contaminated_by_bad_house", findings)

    def test_missing_role_data_does_not_crash(self) -> None:
        snapshot = fixture_snapshot()
        snapshot["positions"] = []

        findings = contradiction_ids(snapshot)

        self.assertIsInstance(findings, dict)


if __name__ == "__main__":
    unittest.main()
