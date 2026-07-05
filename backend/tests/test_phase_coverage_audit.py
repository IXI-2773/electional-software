from __future__ import annotations

import unittest

from backend.electional.reliability.feature_registry import FeatureRegistryItem, build_feature_registry
from backend.electional.reliability.phase_coverage_audit import build_phase_coverage_audit


class PhaseCoverageAuditTest(unittest.TestCase):
    def test_phase_coverage_audit_all_present_for_phase1_and_phase2(self) -> None:
        audit = build_phase_coverage_audit()
        self.assertEqual(audit["phase1_advanced_analysis_coverage"]["missing"], 0)
        self.assertEqual(audit["phase2_tactical_output_coverage"]["missing"], 0)

    def test_phase_coverage_audit_detects_missing_fast_lane(self) -> None:
        items = [item for item in build_feature_registry() if item.feature_id != "phase2_fast_lane"]
        items.append(FeatureRegistryItem("phase2_fast_lane", "Fast Lane", "phase2", None, None, "missing", False, False, False, False, False, False, ("module missing",)))
        audit = build_phase_coverage_audit(items)
        self.assertIn("phase2_fast_lane", [item["feature_id"] for item in audit["missing_features"]])

    def test_phase_coverage_audit_detects_missing_export_replay_tests(self) -> None:
        item = FeatureRegistryItem("x", "X", "phase2", "v1", "x.py", "implemented", False, True, False, False, False, False, ())
        audit = build_phase_coverage_audit([item])
        self.assertTrue(audit["export_gaps"])
        self.assertTrue(audit["replay_gaps"])
        self.assertTrue(audit["test_gaps"])


if __name__ == "__main__":
    unittest.main()
