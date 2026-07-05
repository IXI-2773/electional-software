from __future__ import annotations

import unittest

from backend.electional.reliability.feature_registry import build_feature_registry, feature_registry_json, item_by_id


class FeatureRegistryTest(unittest.TestCase):
    def test_feature_registry_detects_fast_lane(self) -> None:
        item = item_by_id("phase2_fast_lane")
        self.assertIsNotNone(item)
        self.assertEqual(item.status, "implemented")
        self.assertTrue(item.has_tests)
        self.assertTrue(item.appears_in_report)
        self.assertTrue(item.appears_in_json_export)
        self.assertTrue(item.appears_in_audit_export)
        self.assertTrue(item.replay_supported)
        self.assertTrue(item.calibration_supported)

    def test_feature_registry_detects_phase1_features(self) -> None:
        ids = {item.feature_id: item for item in build_feature_registry()}
        for feature_id in (
            "phase1_planet_role_resolver",
            "phase1_significator_purity",
            "phase1_contradiction_detection",
            "phase1_chart_control_index",
            "phase1_resistance_analysis",
        ):
            self.assertEqual(ids[feature_id].status, "implemented")

    def test_feature_registry_detects_phase2_features(self) -> None:
        ids = {item.feature_id: item for item in build_feature_registry()}
        for feature_id in (
            "phase2_final_command",
            "phase2_timing_trap_detector",
            "phase2_action_moment_resolver",
            "phase2_event_playbooks",
            "phase2_practical_usability",
            "phase2_strategic_calendar",
            "phase2_calendar_export",
            "phase2_tactical_report",
            "phase2_candidate_comparison_tactical",
            "phase2_fast_lane",
        ):
            self.assertEqual(ids[feature_id].status, "implemented")

    def test_feature_registry_marks_missing_feature(self) -> None:
        item = item_by_id("phase3_rule_weight_experiments")
        self.assertIsNotNone(item)
        self.assertEqual(item.status, "missing")

    def test_feature_registry_json_export_and_audit_export(self) -> None:
        payload = feature_registry_json()
        self.assertIn("features", payload)
        self.assertIn("summary", payload)
        fast = next(item for item in payload["features"] if item["feature_id"] == "phase2_fast_lane")
        self.assertTrue(fast["appears_in_audit_export"])


if __name__ == "__main__":
    unittest.main()
