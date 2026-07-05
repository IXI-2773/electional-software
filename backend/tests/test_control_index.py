from __future__ import annotations

import unittest

from backend.electional.analysis.control_index import build_control_index_report
from backend.electional.analysis.planet_roles import resolve_planet_roles
from backend.electional.analysis.significator_purity import build_significator_purity_profiles
from backend.tests._advanced_analysis_fixtures import DEFAULT_HOUSE_SIGNS, add_aspect, fixture_snapshot, set_planet


def control_report(snapshot):
    roles = resolve_planet_roles(snapshot)
    purity = build_significator_purity_profiles(snapshot, roles, snapshot.get("objective"))
    return build_control_index_report(snapshot, roles, purity)


class ControlIndexTest(unittest.TestCase):
    def test_strong_ascendant_side_beats_weak_seventh_side(self) -> None:
        snapshot = fixture_snapshot()
        set_planet(snapshot, "Jupiter", dignity={"score": -4, "label": "Fall", "boundLord": "Mars", "isOwnBound": False}, isAngular=False)

        report = control_report(snapshot)

        self.assertIn(report.band, {"user_has_advantage", "user_has_strong_control"})
        self.assertGreater(report.control_score or 0, 64)

    def test_weak_ascendant_side_loses_to_strong_opponent(self) -> None:
        house_signs = list(DEFAULT_HOUSE_SIGNS)
        house_signs[7] = "Aries"
        snapshot = fixture_snapshot(house_signs=house_signs)
        set_planet(snapshot, "Mercury", house=12, isAngular=False, isRetrograde=True, solarCondition={"phase": "combust"})
        set_planet(snapshot, "Jupiter", dignity={"score": 5, "label": "Domicile", "boundLord": "Jupiter", "isOwnBound": True}, isAngular=True)

        report = control_report(snapshot)

        self.assertIn(report.band, {"resistance_has_advantage", "user_lacks_control"})
        self.assertLess(report.control_score or 100, 50)

    def test_moon_support_and_angular_malefic_change_control_score(self) -> None:
        support_snapshot = fixture_snapshot()
        add_aspect(support_snapshot, "Moon", "Saturn", label="Moon trine Saturn")
        support_report = control_report(support_snapshot)

        stressed_snapshot = fixture_snapshot()
        add_aspect(stressed_snapshot, "Moon", "Jupiter", tone="stress", label="Moon square Jupiter")
        set_planet(stressed_snapshot, "Mars", isAngular=True, closestAngle={"shortName": "ASC", "distance": 1.5})
        stressed_report = control_report(stressed_snapshot)

        self.assertGreater(support_report.control_score or 0, stressed_report.control_score or 0)

    def test_authority_support_improves_control(self) -> None:
        strong_authority = fixture_snapshot()
        weak_authority = fixture_snapshot()
        set_planet(weak_authority, "Saturn", dignity={"score": -5, "label": "Detriment", "boundLord": "Mars", "isOwnBound": False}, house=12)

        strong_report = control_report(strong_authority)
        weak_report = control_report(weak_authority)

        self.assertGreaterEqual(strong_report.control_score or 0, (weak_report.control_score or 0) + 4)

    def test_insufficient_data_returns_unknown(self) -> None:
        snapshot = fixture_snapshot()
        snapshot["houseCusps"] = []

        report = control_report(snapshot)

        self.assertEqual(report.band, "unknown")
        self.assertIsNone(report.control_score)


if __name__ == "__main__":
    unittest.main()
