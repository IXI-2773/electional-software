from __future__ import annotations

import unittest

from backend.electional.report_templates import render_report_template


SNAPSHOT = {
    "engine_schema_version": "phase4",
    "advancedAnalysis": {"control_index": {"band": "user_has_advantage"}},
    "auditSnapshot": {"phase3_reliability": {}},
    "tacticalAnalysis": {
        "fast_lane": {"command": "USE", "window": "10:00-10:10", "best": "10:04", "cutoff": "10:12", "main_reason": "clean", "main_risk": "narrow", "action": "Press Send", "confidence": 0.9},
        "strategic_calendar_context": {"entries": [{"id": "x"}]},
    },
}


class ReportTemplatesTest(unittest.TestCase):
    def test_fast_lane_template_short(self) -> None:
        text = render_report_template(SNAPSHOT, "fast_lane")
        self.assertIn("Command: USE", text)
        self.assertNotIn("Developer Debug", text)

    def test_other_templates(self) -> None:
        self.assertIn("Tactical summary", render_report_template(SNAPSHOT, "normal"))
        self.assertIn("Phase 1", render_report_template(SNAPSHOT, "expert"))
        self.assertIn("Reliability", render_report_template(SNAPSHOT, "audit"))
        self.assertIn("Windows: 1", render_report_template(SNAPSHOT, "calendar"))
        self.assertIn("Keys:", render_report_template(SNAPSHOT, "developer_debug"))


if __name__ == "__main__":
    unittest.main()
