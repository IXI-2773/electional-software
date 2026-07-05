from __future__ import annotations

import unittest

from backend.electional.analysis.advanced import annotate_advanced_analysis, build_advanced_analysis_report
from backend.electional.locations import LocationPreset
from backend.electional.reporting import build_diagnostics_page, build_transit_search_page, build_window_comparison_page
from backend.tests._advanced_analysis_fixtures import add_aspect, fixture_snapshot


class AdvancedAnalysisIntegrationTest(unittest.TestCase):
    def test_json_annotation_adds_advanced_analysis_payload(self) -> None:
        snapshot = fixture_snapshot()
        add_aspect(snapshot, "Moon", "Jupiter", label="Moon trine Jupiter")

        annotated = annotate_advanced_analysis([snapshot])[0]

        self.assertIn("advancedAnalysis", annotated)
        self.assertIn("advanced_analysis", annotated)
        self.assertEqual(annotated["engine_schema_version"], "phase1_advanced_analysis_v1")
        self.assertIn("control_index", annotated["advancedAnalysis"])

    def test_reports_include_advanced_analysis_sections(self) -> None:
        snapshot = fixture_snapshot()
        snapshot["advancedAnalysis"] = build_advanced_analysis_report(snapshot).to_json()
        snapshot["advanced_analysis"] = snapshot["advancedAnalysis"]
        location = LocationPreset("test", "Test", 0.0, 0.0, "UTC")

        search_text = build_transit_search_page(
            {"date": snapshot["date"], "formattedTime": "search start"},
            snapshot,
            [snapshot],
            location,
            "test search",
        )
        diagnostics_text = build_diagnostics_page(snapshot)
        comparison_text = build_window_comparison_page({"date": snapshot["date"]}, [snapshot], snapshot["objective"])

        self.assertIn("Advanced Analysis", search_text)
        self.assertIn("Control Index", diagnostics_text)
        self.assertIn("Advanced:", comparison_text)

    def test_missing_advanced_inputs_degrade_to_unknown_not_crash(self) -> None:
        snapshot = fixture_snapshot()
        snapshot["positions"] = []
        snapshot["houseCusps"] = []

        report = build_advanced_analysis_report(snapshot)

        self.assertTrue(report.warnings)
        self.assertEqual(report.control_index.band, "unknown")


if __name__ == "__main__":
    unittest.main()
