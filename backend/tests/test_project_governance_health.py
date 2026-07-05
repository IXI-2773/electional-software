from __future__ import annotations

import unittest

from backend.electional.governance.dependencies import find_broken_dependencies, find_impacted_features
from backend.electional.governance.project_health import get_project_health
from backend.electional.governance.roadmap_registry import RoadmapItem


class ProjectHealthTest(unittest.TestCase):
    def test_project_health_empty_state(self) -> None:
        health = get_project_health(storage_health={"status": "healthy"}, knowledge_health={"status": "healthy", "warnings": []})
        self.assertIn(health["status"], {"healthy", "warning", "critical"})

    def test_project_health_with_warning(self) -> None:
        health = get_project_health(storage_health={"status": "healthy"}, knowledge_health={"status": "warning", "warnings": ["pending_proposals"]})
        self.assertIn("pending_proposals", health["warnings"])

    def test_project_health_critical_review_item(self) -> None:
        health = get_project_health(storage_health={"status": "healthy"}, knowledge_health={"status": "healthy", "warnings": []}, review_items=[{"severity": "critical"}])
        self.assertEqual(health["status"], "critical")

    def test_project_health_missing_dependency(self) -> None:
        broken = find_broken_dependencies(items={"phase2_fast_lane": RoadmapItem("phase2_fast_lane", "Phase 2", "Fast Lane", "verified", "x")})
        self.assertTrue(any(item["severity"] == "critical" for item in broken))

    def test_find_impacted_features(self) -> None:
        self.assertIn("phase2_fast_lane", find_impacted_features("phase2_final_command"))


if __name__ == "__main__":
    unittest.main()

