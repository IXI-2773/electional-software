from __future__ import annotations

import unittest

from backend.electional.analysis.planet_roles import resolve_planet_roles
from backend.electional.analysis.resistance import build_resistance_analysis_report
from backend.electional.analysis.significator_purity import build_significator_purity_profiles
from backend.tests._advanced_analysis_fixtures import DEFAULT_HOUSE_SIGNS, fixture_snapshot, set_planet


def resistance_report(snapshot):
    roles = resolve_planet_roles(snapshot)
    purity = build_significator_purity_profiles(snapshot, roles, snapshot.get("objective"))
    return build_resistance_analysis_report(snapshot, roles, purity, snapshot.get("objective"))


class ResistanceAnalysisTest(unittest.TestCase):
    def test_legal_mode_user_advantage(self) -> None:
        snapshot = fixture_snapshot(objective="Legal dispute")
        set_planet(snapshot, "Jupiter", dignity={"score": -4, "label": "Fall", "boundLord": "Mars", "isOwnBound": False}, isAngular=False)

        report = resistance_report(snapshot)

        self.assertIn(report.advantage, {"user_advantage", "strong_user_advantage"})

    def test_legal_mode_opponent_advantage(self) -> None:
        house_signs = list(DEFAULT_HOUSE_SIGNS)
        house_signs[7] = "Aries"
        snapshot = fixture_snapshot(objective="Legal dispute", house_signs=house_signs)
        set_planet(snapshot, "Mercury", house=12, isAngular=False, isRetrograde=True, solarCondition={"phase": "combust"})
        set_planet(snapshot, "Jupiter", dignity={"score": 5, "label": "Domicile", "boundLord": "Jupiter", "isOwnBound": True}, isAngular=True)

        report = resistance_report(snapshot)

        self.assertIn(report.advantage, {"opponent_advantage", "strong_opponent_advantage"})

    def test_exam_mode_hostile_authority_is_reported(self) -> None:
        snapshot = fixture_snapshot()
        set_planet(snapshot, "Saturn", dignity={"score": -5, "label": "Detriment", "boundLord": "Mars", "isOwnBound": False}, house=12)

        report = resistance_report(snapshot)

        self.assertTrue(any("Authority side is hostile" in risk for risk in report.risks))

    def test_missing_required_data_returns_unknown(self) -> None:
        snapshot = fixture_snapshot()
        snapshot["houseCusps"] = []

        report = resistance_report(snapshot)

        self.assertEqual(report.advantage, "unknown")
        self.assertIsNone(report.advantage_score)


if __name__ == "__main__":
    unittest.main()
