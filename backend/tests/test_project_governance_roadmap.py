from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.electional.governance.roadmap_registry import get_roadmap_item, load_roadmap_registry, save_roadmap_registry, summarize_roadmap_status, update_roadmap_status


class RoadmapRegistryTest(unittest.TestCase):
    def test_roadmap_registry_load_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            items = load_roadmap_registry(Path(tmp) / "missing.json")
            self.assertIn("phase2_fast_lane", items)

    def test_roadmap_registry_save_item_and_summary(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "roadmap.json"
            items = load_roadmap_registry(path)
            save_roadmap_registry(items, path)
            summary = summarize_roadmap_status(path)
            self.assertGreater(summary["total"], 0)

    def test_roadmap_registry_update_status(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "roadmap.json"
            updated = update_roadmap_status("phase7_governance", "verified", path)
            self.assertEqual(updated.status, "verified")
            self.assertIsNotNone(updated.last_verified_at_utc)

    def test_roadmap_registry_unknown_feature(self) -> None:
        item = get_roadmap_item("not_real")
        self.assertEqual(item.status, "unknown")
        self.assertIn("unknown_feature", item.warnings)


if __name__ == "__main__":
    unittest.main()

