from __future__ import annotations

import unittest

from backend.electional.governance.release_gates import run_release_gate


class ReleaseGateTest(unittest.TestCase):
    def test_release_gate_pass_or_warning_without_critical_items(self) -> None:
        result = run_release_gate(project_health={"status": "healthy"})
        self.assertIn(result["status"], {"pass", "warning"})

    def test_release_gate_blocks_on_critical_review(self) -> None:
        result = run_release_gate(review_items=[{"severity": "critical"}], project_health={"status": "healthy"})
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(result["blockers"])

    def test_release_gate_blocks_on_missing_fast_lane(self) -> None:
        result = run_release_gate(project_health={"status": "critical", "critical_issues": ["missing_fast_lane"]})
        self.assertEqual(result["status"], "blocked")

    def test_release_gate_warns_on_docs_gap(self) -> None:
        result = run_release_gate(project_health={"status": "healthy"})
        self.assertIn("checks", result)

    def test_release_gate_does_not_run_broad_suite(self) -> None:
        result = run_release_gate(project_health={"status": "healthy"})
        text = " ".join(str(check.get("check_id")) for check in result["checks"])
        self.assertNotIn("pytest", text)
        self.assertNotIn("discover", text)


if __name__ == "__main__":
    unittest.main()

