from __future__ import annotations

from datetime import timedelta
import unittest

from backend.electional.analysis.tactical import annotate_tactical_analysis
from backend.electional.locations import LocationPreset
from backend.electional.reporting import build_diagnostics_page, build_transit_search_page, build_window_comparison_page
from backend.tests._advanced_analysis_fixtures import fixture_snapshot


class TacticalReportIntegrationTest(unittest.TestCase):
    def test_tactical_report_sections_and_export_are_included(self) -> None:
        item = fixture_snapshot()
        item["start_time"] = item["date"]
        item["end_time"] = item["date"] + timedelta(minutes=20)
        item = annotate_tactical_analysis([item])[0]
        location = LocationPreset("test", "Test", 0.0, 0.0, "UTC")

        diagnostics = build_diagnostics_page(item)
        search = build_transit_search_page({"date": item["date"], "formattedTime": "start"}, item, [item], location, "test")
        comparison = build_window_comparison_page({"date": item["date"]}, [item], item["objective"])

        self.assertIn("Tactical Output", diagnostics)
        self.assertIn("Final Command", diagnostics)
        self.assertIn("Action Moment", diagnostics)
        self.assertIn("Timing Traps", diagnostics)
        self.assertIn("Practical Usability", diagnostics)
        self.assertIn("tacticalAnalysis", item)
        self.assertIn("Tactical Output", search)
        self.assertIn("Tactical:", comparison)


if __name__ == "__main__":
    unittest.main()
