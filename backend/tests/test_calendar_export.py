from __future__ import annotations

from datetime import datetime, timezone
import unittest

from backend.electional.calendar_export import calendar_from_entries, format_ics_datetime, ics_escape, parse_ics_datetime


class CalendarExportTest(unittest.TestCase):
    def test_ics_escape_handles_special_characters_and_newlines(self) -> None:
        self.assertEqual(ics_escape("A, B; C\nD"), "A\\, B\\; C\\nD")

    def test_datetime_helpers_emit_utc_ics_format(self) -> None:
        moment = parse_ics_datetime("2026-05-26T16:00:00+00:00")

        self.assertEqual(format_ics_datetime(moment), "20260526T160000Z")

    def test_calendar_from_entries_contains_event_fields(self) -> None:
        calendar = calendar_from_entries(
            [
                {
                    "id": "abc123",
                    "datetime": datetime(2026, 5, 26, 16, 0, tzinfo=timezone.utc),
                    "score": 87,
                    "objective": "Launch or publish",
                    "location": "Los Angeles, CA",
                    "lunarPhase": "Waxing Gibbous",
                    "note": "Good support.",
                    "flags": ["- Tightening support: Venus trine Jupiter."],
                    "aspects": ["Venus trine Jupiter"],
                }
            ]
        )

        self.assertIn("BEGIN:VCALENDAR", calendar)
        self.assertIn("BEGIN:VEVENT", calendar)
        self.assertIn("UID:abc123@electional-software", calendar)
        self.assertIn("DTSTART:20260526T160000Z", calendar)
        self.assertIn("SUMMARY:Electional window 87 - Launch or publish", calendar)
        self.assertIn("LOCATION:Los Angeles\\, CA", calendar)


if __name__ == "__main__":
    unittest.main()
