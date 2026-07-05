from __future__ import annotations

from datetime import datetime, timedelta
import unittest

from backend.electional.long_range import (
    LongRangeScoutConfig,
    build_long_range_scout_from_windows,
    format_long_range_scout_text,
    rarity_payload,
)


BASE = datetime(2026, 7, 1, 9, 0)


def scout_window(
    offset_minutes: int,
    score: int,
    *,
    label: str = "",
    confidence: int = 84,
    cleanliness: int = 84,
    volatility: int = 18,
    readiness: int = 82,
    moon_benefic: bool = True,
    angular_benefic: bool = True,
    angular_malefic: bool = False,
    mercury_clean: bool = True,
    matter_impact: float = 1.5,
    natal_fit: int = 74,
    stability: str = "stable",
    fragility: str = "Low",
) -> dict[str, object]:
    moment = BASE + timedelta(minutes=offset_minutes)
    positions = [
        {
            "name": "Moon",
            "isAngular": False,
            "dignity": {"score": 2 if moon_benefic else 0},
            "closestAngle": {"distance": 12},
        },
        {
            "name": "Mercury",
            "isAngular": False,
            "isRetrograde": not mercury_clean,
            "solarCondition": {"phase": "free" if mercury_clean else "under beams"},
            "closestAngle": {"distance": 12},
        },
    ]
    if angular_benefic:
        positions.append({"name": "Jupiter", "isAngular": True, "closestAngle": {"distance": 3}})
    if angular_malefic:
        positions.append({"name": "Mars", "isAngular": True, "closestAngle": {"distance": 2}})
    aspects = []
    if moon_benefic:
        aspects.append({"tone": "support", "isApplying": True, "orb": 0.8, "bodies": ["Moon", "Jupiter"], "label": "Moon trine Jupiter"})
    return {
        "date": moment,
        "formattedTime": label or moment.strftime("%Y-%m-%d %I:%M %p"),
        "time": moment.strftime("%I:%M %p"),
        "score": score,
        "objective": "Exam",
        "scoreBreakdown": {
            "objectiveMatches": 3,
            "diagnostics": {
                "confidence": {"score": confidence},
                "cleanliness": {"score": cleanliness},
                "volatility": {"score": volatility},
                "readiness": {"score": readiness},
            },
        },
        "detectedAspects": aspects,
        "positions": positions,
        "moonCondition": {"voidOfCourse": {"isVoid": False}},
        "matterLordContext": {"scoreImpact": matter_impact},
        "natalCompatibilityScore": natal_fit,
        "windowStability": {"classification": stability, "samples": [{"score": score}] * 8},
        "fragility": {"band": fragility},
    }


class LongRangeScoutTest(unittest.TestCase):
    def test_30_day_scout_returns_structured_results(self) -> None:
        windows = [scout_window(60, 91), scout_window(24 * 60, 82)]
        payload = build_long_range_scout_from_windows(windows, LongRangeScoutConfig(days=30, objective="Exam"))
        first = payload["results"][0]

        self.assertEqual(payload["days"], 30)
        self.assertEqual(payload["objective"], "Exam")
        self.assertIn("start_time", first)
        self.assertIn("end_time", first)
        self.assertIn("peak_time", first)
        self.assertIn("rarity_score", first)
        self.assertIn("similar_windows_count", first)
        self.assertIn("top_supporting_factors", first)
        self.assertIn("top_risks", first)

    def test_60_day_scout_returns_top_10_or_fewer_windows(self) -> None:
        windows = [scout_window(index * 24 * 60, 75 + (index % 20)) for index in range(18)]

        payload = build_long_range_scout_from_windows(windows, LongRangeScoutConfig(days=60, objective="Exam", top_n=10))

        self.assertLessEqual(len(payload["results"]), 10)
        self.assertTrue(all(result["objective"] == "Exam" for result in payload["results"]))

    def test_90_day_scout_does_not_crash(self) -> None:
        payload = build_long_range_scout_from_windows([], LongRangeScoutConfig(days=90, objective="Exam"))

        self.assertEqual(payload["days"], 90)
        self.assertEqual(payload["results"], [])
        self.assertEqual(payload["status"], "none")

    def test_hard_rejected_windows_are_not_marked_rare_good(self) -> None:
        rejected = scout_window(60, 95, angular_malefic=True)

        payload = build_long_range_scout_from_windows([rejected], LongRangeScoutConfig(days=30, objective="Exam"))
        result = payload["results"][0]

        self.assertEqual(result["rarity_label"], "Common")
        self.assertLess(result["rarity_score"], 50)
        self.assertEqual(result["classification"], ["Least-bad emergency window"])
        self.assertTrue(result["weak"])

    def test_rarity_score_increases_when_similar_windows_are_few(self) -> None:
        rare = scout_window(60, 92)
        common = scout_window(120, 92)
        common_pool = [common, *[scout_window(240 + index * 60, 91) for index in range(8)]]

        rare_payload = rarity_payload(rare, [rare], LongRangeScoutConfig(days=30, objective="Exam"))
        common_payload = rarity_payload(common, common_pool, LongRangeScoutConfig(days=30, objective="Exam"))

        self.assertGreater(rare_payload["rarity_score"], common_payload["rarity_score"])
        self.assertEqual(rare_payload["similar_windows_count"], 0)

    def test_rarity_score_decreases_when_many_similar_windows_exist(self) -> None:
        candidate = scout_window(60, 90)
        pool = [candidate, *[scout_window(120 + index * 60, 90) for index in range(10)]]

        payload = rarity_payload(candidate, pool, LongRangeScoutConfig(days=30, objective="Exam"))

        self.assertEqual(payload["rarity_label"], "Common")
        self.assertGreaterEqual(payload["similar_windows_count"], 8)

    def test_candidates_are_grouped_into_clusters(self) -> None:
        windows = [scout_window(60, 86), scout_window(70, 88), scout_window(80, 87), scout_window(24 * 60, 84)]

        payload = build_long_range_scout_from_windows(windows, LongRangeScoutConfig(days=30, objective="Exam"))
        first = payload["results"][0]

        self.assertGreaterEqual(first["cluster"]["candidate_count"], 3)
        self.assertIn("-", first["usable_window"])

    def test_output_includes_similar_window_count(self) -> None:
        windows = [scout_window(60, 88), scout_window(24 * 60, 87)]

        payload = build_long_range_scout_from_windows(windows, LongRangeScoutConfig(days=30, objective="Exam"))

        self.assertIn("similar_windows_count", payload["results"][0])

    def test_output_is_deterministic(self) -> None:
        windows = [scout_window(60, 88), scout_window(24 * 60, 87), scout_window(48 * 60, 83)]
        config = LongRangeScoutConfig(days=60, objective="Exam")

        first = build_long_range_scout_from_windows(windows, config)
        second = build_long_range_scout_from_windows(windows, config)

        self.assertEqual(first, second)

    def test_minimal_test_entry_point_formats_scout_output(self) -> None:
        payload = build_long_range_scout_from_windows([scout_window(60, 91)], LongRangeScoutConfig(days=60, objective="Exam"))

        text = format_long_range_scout_text(payload)

        self.assertIn("Best Exam windows in next 60 days:", text)
        self.assertIn("Rarity:", text)
        self.assertIn("Similar windows in range:", text)


if __name__ == "__main__":
    unittest.main()
