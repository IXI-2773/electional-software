from __future__ import annotations

import unittest

from backend.electional.analysis.advanced import build_advanced_analysis_report
from backend.electional.analysis.tactical import build_tactical_analysis_report
from backend.electional.reliability.audit_snapshot import build_audit_snapshot
from backend.tests._advanced_analysis_fixtures import fixture_snapshot


def full_snapshot():
    snapshot = fixture_snapshot()
    snapshot["advancedAnalysis"] = build_advanced_analysis_report(snapshot).to_json()
    snapshot["advanced_analysis"] = snapshot["advancedAnalysis"]
    snapshot["tacticalAnalysis"] = build_tactical_analysis_report(snapshot).to_json()
    snapshot["tactical_analysis"] = snapshot["tacticalAnalysis"]
    return snapshot


class AuditSnapshotTest(unittest.TestCase):
    def test_audit_snapshot_contains_phase1_all_features(self) -> None:
        audit = build_audit_snapshot(full_snapshot())["audit_snapshot"]
        phase1 = audit["phase1_advanced_analysis"]
        for key in ("planet_roles", "significator_purity", "contradictions", "control_index", "resistance_analysis"):
            self.assertIn(key, phase1)

    def test_audit_snapshot_contains_phase2_all_features_and_fast_lane(self) -> None:
        audit = build_audit_snapshot(full_snapshot())["audit_snapshot"]
        phase2 = audit["phase2_tactical_analysis"]
        for key in ("final_command", "timing_traps", "action_moment", "event_playbook", "practicality", "strategic_calendar_context", "fast_lane"):
            self.assertIn(key, phase2)
        self.assertIn("hard_gate_status", phase2["fast_lane"])

    def test_audit_snapshot_missing_section_marked_unavailable(self) -> None:
        audit = build_audit_snapshot(fixture_snapshot())["audit_snapshot"]
        self.assertEqual(audit["phase1_advanced_analysis"]["planet_roles"]["status"], "unavailable")
        self.assertTrue(audit["warnings"])

    def test_audit_snapshot_does_not_silently_omit_phase_features(self) -> None:
        audit = build_audit_snapshot({})["audit_snapshot"]
        self.assertIn("phase1_advanced_analysis", audit)
        self.assertIn("phase2_tactical_analysis", audit)
        self.assertIn("reproducibility_hash", audit)


if __name__ == "__main__":
    unittest.main()
