from __future__ import annotations

from datetime import timezone
import unittest

from backend.electional.analysis.tactical import annotate_tactical_analysis
from backend.electional.analysis.strategic_calendar import build_strategic_calendar
from backend.electional.calendar_export import strategic_calendar_csv, strategic_calendar_ics, strategic_calendar_json
from backend.tests._advanced_analysis_fixtures import fixture_snapshot


class CalendarExportPhase2Test(unittest.TestCase):
    def test_calendar_export_json_csv_ics_privacy_safe(self) -> None:
        item = fixture_snapshot()
        item["date"] = item["date"].replace(tzinfo=timezone.utc)
        item = annotate_tactical_analysis([item])[0]
        report = build_strategic_calendar([item])
        entries = [entry.to_json() for entry in report.entries]

        json_text = strategic_calendar_json(report.to_json())
        csv_text = strategic_calendar_csv(entries)
        ics_text = strategic_calendar_ics(entries, location="Test")

        self.assertIn("strategic_calendar", json_text)
        self.assertIn("start,end,best_minute", csv_text)
        self.assertIn("BEGIN:VCALENDAR", ics_text)
        self.assertIn("DTSTART:", ics_text)
        self.assertNotIn("natal", ics_text.lower())


if __name__ == "__main__":
    unittest.main()
