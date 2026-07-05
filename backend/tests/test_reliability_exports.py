from __future__ import annotations

import json
import unittest

from backend.electional.reliability.audit_snapshot import build_audit_snapshot
from backend.electional.reliability.dashboard import build_reliability_dashboard
from backend.electional.reliability.exports import reliability_json_export, reliability_markdown_export
from backend.tests.test_audit_snapshot import full_snapshot


class ReliabilityExportsTest(unittest.TestCase):
    def test_json_export_includes_feature_registry_phase_coverage_fast_lane_and_phase3(self) -> None:
        audit = build_audit_snapshot(full_snapshot())["audit_snapshot"]
        text = reliability_json_export({"audit_snapshot": audit, "natalProfile": {"private": True}})
        payload = json.loads(text)
        self.assertIn("feature_registry", payload["audit_snapshot"])
        self.assertIn("phase_coverage_audit", payload["audit_snapshot"])
        self.assertIn("phase1_advanced_analysis", payload["audit_snapshot"])
        self.assertIn("phase2_tactical_analysis", payload["audit_snapshot"])
        self.assertIn("fast_lane", payload["audit_snapshot"]["phase2_tactical_analysis"])
        self.assertIn("phase3_reliability", payload["audit_snapshot"])
        self.assertNotIn("natalProfile", payload)

    def test_markdown_export_includes_fast_lane_summary(self) -> None:
        audit = build_audit_snapshot(full_snapshot())["audit_snapshot"]
        dashboard = build_reliability_dashboard()
        text = reliability_markdown_export({"audit_snapshot": audit, "reliability_dashboard": dashboard})
        self.assertIn("Fast Lane", text)

    def test_public_export_omits_private_natal_data(self) -> None:
        public = reliability_json_export({"birthData": {"secret": True}, "ok": True})
        private = reliability_json_export({"birthData": {"secret": True}, "ok": True}, include_private=True)
        self.assertNotIn("birthData", public)
        self.assertIn("birthData", private)


if __name__ == "__main__":
    unittest.main()
