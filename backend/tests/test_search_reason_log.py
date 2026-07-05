from __future__ import annotations

from datetime import datetime, timedelta
import unittest

from backend.electional.search import (
    SearchConfig,
    accepted_reason_codes,
    analysis_confidence_payload,
    build_search_reason_log,
    rank_search_windows,
    rarity_eligible,
    rarity_label_for_candidate,
    rejection_reason_codes,
    similar_quality_count,
    split_ranked_windows,
)
from backend.electional.locations import LocationPreset
from backend.electional.reporting import build_transit_search_page


BASE = datetime(2026, 7, 1, 9, 0)


def search_window(
    index: int,
    score: int,
    *,
    confidence: int = 84,
    cleanliness: int = 84,
    volatility: int = 18,
    readiness: int = 82,
    moon_void: bool = False,
    angular_benefic: bool = True,
    angular_malefic: bool = False,
    matter_impact: float = 1.2,
    natal_fit: int = 74,
    stability: str = "stable",
    fragility: str = "Low",
) -> dict[str, object]:
    moment = BASE + timedelta(hours=index)
    positions = [
        {"name": "Moon", "isAngular": False, "dignity": {"score": 2}, "closestAngle": {"distance": 10}},
    ]
    if angular_benefic:
        positions.append({"name": "Jupiter", "isAngular": True, "closestAngle": {"distance": 3}})
    if angular_malefic:
        positions.append({"name": "Mars", "isAngular": True, "closestAngle": {"distance": 2}})
    return {
        "date": moment,
        "formattedTime": moment.strftime("%Y-%m-%d %I:%M %p"),
        "time": moment.strftime("%I:%M %p"),
        "score": score,
        "scoreBreakdown": {
            "objectiveMatches": 2,
            "diagnostics": {
                "confidence": {"score": confidence},
                "cleanliness": {"score": cleanliness},
                "volatility": {"score": volatility},
                "readiness": {"score": readiness},
            },
        },
        "detectedAspects": [{"tone": "support", "isApplying": True, "orb": 0.8, "bodies": ["Moon", "Jupiter"]}],
        "positions": positions,
        "moonCondition": {"voidOfCourse": {"isVoid": moon_void}},
        "matterLordContext": {"scoreImpact": matter_impact},
        "natalCompatibilityScore": natal_fit,
        "windowStability": {"classification": stability, "samples": [{"score": score}] * 6},
        "fragility": {"band": fragility},
    }


class SearchReasonLogTest(unittest.TestCase):
    def test_rarity_label_calculation_counts_few_peers_as_rare(self) -> None:
        candidate = search_window(0, 92)
        population = [candidate, search_window(1, 78), search_window(2, 76), search_window(3, 74)]

        rarity = rarity_label_for_candidate(candidate, population, SearchConfig(end_offset_minutes=60 * 24))

        self.assertIn(rarity["rarity_label"], {"rare", "very_rare"})
        self.assertEqual(rarity["similar_quality_count"], 0)
        self.assertGreater(rarity["rarity_score"], 80)

    def test_similar_quality_count_increases_for_many_peers(self) -> None:
        candidate = search_window(0, 88)
        population = [candidate, *[search_window(index, 87) for index in range(1, 8)]]

        count = similar_quality_count(candidate, population, SearchConfig(end_offset_minutes=60 * 24))

        self.assertEqual(count, 7)

    def test_minimum_rarity_eligibility_blocks_weak_dirty_chart(self) -> None:
        dirty = search_window(0, 95, confidence=52, angular_malefic=True, fragility="High")

        eligible, reasons = rarity_eligible(dirty)
        rarity = rarity_label_for_candidate(dirty, [dirty], SearchConfig(end_offset_minutes=60 * 24))

        self.assertFalse(eligible)
        self.assertIn("hard rejection flags present", reasons)
        self.assertEqual(rarity["rarity_label"], "common")
        self.assertLessEqual(rarity["rarity_score"], 49)

    def test_rejection_reason_counting_uses_stable_codes(self) -> None:
        rejected = search_window(0, 64, confidence=58, moon_void=True, angular_malefic=True)
        config = SearchConfig(minimum_score=70, minimum_confidence=70, avoid_angular_malefics=True, require_moon_non_void=True)

        codes = rejection_reason_codes(rejected, config)

        self.assertIn("below_score_threshold", codes)
        self.assertIn("low_data_confidence", codes)
        self.assertIn("malefic_angular", codes)
        self.assertIn("moon_void", codes)

    def test_accepted_reason_counting_uses_support_codes(self) -> None:
        accepted = search_window(0, 86)

        codes = accepted_reason_codes(accepted, SearchConfig(minimum_score=70))

        self.assertIn("hard_gates_passed", codes)
        self.assertIn("moon_supported", codes)
        self.assertIn("lord_of_matter_strong", codes)
        self.assertIn("benefic_angular", codes)
        self.assertIn("malefics_not_angular", codes)
        self.assertIn("data_confidence_acceptable", codes)

    def test_confidence_label_calculation_separates_grade_data_and_coverage(self) -> None:
        window = search_window(0, 86, confidence=72)
        reason_log = {
            "total_windows_evaluated": 3,
            "accepted_count": 2,
            "rejected_count": 1,
            "reconciles": True,
        }

        confidence = analysis_confidence_payload(window, SearchConfig(), reason_log)

        self.assertEqual(confidence["election_grade"], "A-")
        self.assertEqual(confidence["analysis_confidence"], "Medium")
        self.assertEqual(confidence["data_confidence"], "Medium")
        self.assertEqual(confidence["search_coverage"], "Complete")

    def test_confidence_warning_triggers_for_strong_grade_low_confidence(self) -> None:
        window = search_window(0, 91, confidence=48)

        confidence = analysis_confidence_payload(window)

        self.assertEqual(confidence["election_grade"], "A")
        self.assertEqual(confidence["analysis_confidence"], "Low")
        self.assertEqual(confidence["data_confidence"], "Low")
        self.assertIn("grades well", confidence["warning"])

    def test_reason_log_totals_reconcile(self) -> None:
        windows = [search_window(0, 86), search_window(1, 64), search_window(2, 82)]
        config = SearchConfig(minimum_score=70)
        accepted, rejected = split_ranked_windows(windows, config)

        log = build_search_reason_log(windows, accepted, rejected, config)

        self.assertTrue(log["reconciles"])
        self.assertEqual(log["accepted_count"] + log["rejected_count"], log["total_windows_evaluated"])
        self.assertEqual(log["total_windows_evaluated"], 3)

    def test_fake_search_population_attaches_rarity_and_reason_metadata(self) -> None:
        windows = [search_window(0, 91), search_window(1, 85), search_window(2, 63)]
        config = SearchConfig(minimum_score=70, max_results=2)

        ranked = rank_search_windows(windows, config)
        accepted, rejected = split_ranked_windows(windows, config)
        log = build_search_reason_log(windows, accepted, rejected, config)

        self.assertEqual(len(ranked), 2)
        self.assertTrue(all("rarity" in window for window in ranked))
        self.assertTrue(all("searchReasons" in window for window in ranked))
        self.assertTrue(all("confidence" in window for window in ranked))
        self.assertEqual(log["rejection_breakdown"]["below_score_threshold"], 1)

    def test_golden_reason_log_shape_and_labels_are_stable(self) -> None:
        windows = [
            search_window(0, 88),
            search_window(1, 60, confidence=50, moon_void=True),
            search_window(2, 86, angular_malefic=True),
        ]
        config = SearchConfig(minimum_score=70, minimum_confidence=70, avoid_angular_malefics=True, require_moon_non_void=True)
        accepted, rejected = split_ranked_windows(windows, config)

        log = build_search_reason_log(windows, accepted, rejected, config)

        expected = {
            "total_windows_evaluated": 3,
            "accepted_count": 1,
            "rejected_count": 2,
            "below_score_threshold": 1,
            "low_data_confidence": 1,
            "moon_void": 1,
            "malefic_angular": 1,
        }
        self.assertEqual(log["total_windows_evaluated"], expected["total_windows_evaluated"])
        self.assertEqual(log["accepted_count"], expected["accepted_count"])
        self.assertEqual(log["rejected_count"], expected["rejected_count"])
        self.assertIn("data_confidence_acceptable", log["accepted_breakdown"])
        for code in ("below_score_threshold", "low_data_confidence", "moon_void", "malefic_angular"):
            self.assertEqual(log["rejection_breakdown"][code], expected[code])

    def test_rarity_metadata_does_not_mutate_scores_or_ranking_order(self) -> None:
        windows = [search_window(0, 82), search_window(1, 91), search_window(2, 87)]

        ranked = rank_search_windows(windows, SearchConfig(max_results=3))

        self.assertEqual([window["score"] for window in ranked], [91, 87, 82])
        self.assertTrue(all(isinstance(window["rarity"]["rarity_score"], float) for window in ranked))

    def test_report_output_includes_confidence_warning_and_reason_log(self) -> None:
        selected = search_window(0, 91, confidence=48)
        selected["confidence"] = analysis_confidence_payload(selected)
        reason_log = {
            "total_windows_evaluated": 2,
            "accepted_count": 1,
            "rejected_count": 1,
            "reconciles": True,
            "rejection_breakdown": {"below_score_threshold": 1, "moon_void": 0},
        }

        text = build_transit_search_page(
            {"date": BASE, "formattedTime": "start"},
            selected,
            [selected],
            LocationPreset("test", "Test", 0.0, 0.0, "UTC"),
            "test search",
            search_reason_log=reason_log,
        )

        self.assertIn("Election Grade: A", text)
        self.assertIn("Analysis Confidence: Low", text)
        self.assertIn("Data Confidence: Low", text)
        self.assertIn("Search Coverage: Complete", text)
        self.assertIn("Warning:", text)
        self.assertIn("Search Reason Log", text)
        self.assertIn("below_score_threshold: 1", text)


if __name__ == "__main__":
    unittest.main()
