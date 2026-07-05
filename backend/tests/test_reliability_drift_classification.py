from __future__ import annotations

import unittest

from backend.electional.reliability.regression_replay import compare_regression_snapshots
from backend.electional.reliability.review_queue import build_review_queue


def _snapshot(**updates):
    base = {
        "score": 80,
        "grade": "B+",
        "hardReject": False,
        "tacticalAnalysis": {
            "confidence": 0.9,
            "fast_lane": {"command": "USE", "best": "10:00 AM", "cutoff": "10:30 AM", "action": "Press send."},
            "final_command": {"command": "USE"},
            "timing_traps": {"traps": []},
            "action_moment": {"elected_moment": "send"},
            "practicality": {"band": "practical"},
        },
        "advancedAnalysis": {
            "planet_roles": [],
            "significator_purity": [],
            "contradictions": [],
            "control_index": {"band": "user_has_advantage"},
            "resistance_analysis": {"advantage": "user_advantage"},
        },
    }
    base.update(updates)
    return base


class ReliabilityDriftClassificationTest(unittest.TestCase):
    def test_drift_none(self) -> None:
        result = compare_regression_snapshots(_snapshot(), _snapshot())
        self.assertEqual(result["status"], "unchanged")

    def test_drift_minor_score_change(self) -> None:
        result = compare_regression_snapshots(_snapshot(), _snapshot(score=82))
        self.assertEqual(result["drifts"][0]["severity"], "minor")

    def test_drift_major_score_and_grade_change(self) -> None:
        result = compare_regression_snapshots(_snapshot(), _snapshot(score=99, grade="A"))
        severities = {item["category"]: item["severity"] for item in result["drifts"]}
        self.assertEqual(severities["score_drift"], "major")
        self.assertEqual(severities["grade_drift"], "major")

    def test_drift_critical_hard_gate_change(self) -> None:
        result = compare_regression_snapshots(_snapshot(), _snapshot(hardReject=True))
        self.assertEqual(result["drifts"][0]["category"], "hard_gate_drift")
        self.assertEqual(result["drifts"][0]["severity"], "critical")

    def test_drift_critical_fast_lane_reject_to_use(self) -> None:
        old = _snapshot()
        old["tacticalAnalysis"]["fast_lane"]["command"] = "REJECT"
        new = _snapshot()
        result = compare_regression_snapshots(old, new)
        drift = [item for item in result["drifts"] if item["category"] == "phase2_fast_lane_drift"][0]
        self.assertEqual(drift["severity"], "critical")

    def test_review_item_created_for_major_and_critical_drift(self) -> None:
        drift = [
            {"category": "phase2_fast_lane_drift", "severity": "critical", "title": "Fast Lane changed"},
            {"category": "score_drift", "severity": "major", "title": "Score changed"},
        ]
        items = build_review_queue(replay_drift=drift)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].item_type, "phase2_fast_lane_drift")


if __name__ == "__main__":
    unittest.main()
