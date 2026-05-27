from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.electional.locations import LocationPreset
from backend.electional.shortlist import (
    add_shortlist_entry,
    build_shortlist_entry,
    format_shortlist_entries,
    load_shortlist,
    save_shortlist,
    shortlist_entry_id,
)


class ShortlistTest(unittest.TestCase):
    def test_shortlist_entry_is_stable_for_same_window(self) -> None:
        snapshot = {
            "date": datetime(2026, 5, 26, 16, 0, tzinfo=timezone.utc),
            "formattedTime": "Tue, May 26, 2026, 9:00 AM PDT",
            "score": 82,
            "title": "Strong election",
            "note": "Angular benefic emphasis.",
            "lunarPhase": {"name": "Waxing Gibbous", "illumination": 0.82, "ageDays": 10.5, "isWaxing": True},
            "detectedAspects": [
                {
                    "label": "Venus trine Jupiter",
                    "orbText": "1 deg 00 min",
                    "phase": "applying",
                    "phaseLabel": "Applying",
                    "orbChangePerDay": -0.5,
                    "tone": "support",
                    "isApplying": True,
                }
            ],
            "positions": [{"name": "Jupiter", "isAngular": True}],
        }
        location = LocationPreset("la", "Los Angeles, CA", 34.0522, -118.2437, "America/Los_Angeles")

        entry = build_shortlist_entry(snapshot, location, "Launch or publish", added_at=datetime(2026, 1, 1, tzinfo=timezone.utc))

        self.assertEqual(entry["id"], shortlist_entry_id(snapshot, location.name, "Launch or publish"))
        self.assertEqual(entry["score"], 82)
        self.assertIn("Waxing Gibbous", entry["lunarPhase"])
        self.assertIn("Venus trine Jupiter", entry["aspects"][0])
        self.assertTrue(any("Angular benefic" in flag for flag in entry["flags"]))

    def test_add_shortlist_entry_deduplicates_and_keeps_newest_first(self) -> None:
        original = {"id": "same", "formattedTime": "old", "score": 60}
        replacement = {"id": "same", "formattedTime": "new", "score": 80}
        other = {"id": "other", "formattedTime": "other", "score": 70}

        entries = add_shortlist_entry([original, other], replacement)

        self.assertEqual([entry["id"] for entry in entries], ["same", "other"])
        self.assertEqual(entries[0]["formattedTime"], "new")

    def test_shortlist_storage_round_trip_and_formatting(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "shortlist.json"
            entries = [
                {
                    "id": "pick",
                    "formattedTime": "Tue, May 26, 2026, 9:00 AM PDT",
                    "score": 77,
                    "title": "Workable election",
                    "objective": "Meeting",
                    "location": "Paris",
                    "timezone": "Europe/Paris",
                    "lunarPhase": "Waxing Gibbous",
                    "note": "Good support.",
                    "flags": ["- Tightening support: Venus trine Jupiter."],
                    "aspects": ["Venus trine Jupiter"],
                }
            ]

            save_shortlist(entries, path)
            loaded = load_shortlist(path)

        text = format_shortlist_entries(loaded)
        self.assertEqual(loaded[0]["id"], "pick")
        self.assertIn("Score 77", text)
        self.assertIn("Tightening support", text)


if __name__ == "__main__":
    unittest.main()
