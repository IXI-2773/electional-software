from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from backend.electional.desktop import (
    aspect_curve_points,
    body_marker_offsets,
    fixed_star_contact_count,
    compact_time_label,
    location_summary,
    planet_abbreviation,
    planet_marker_offsets,
    star_abbreviation,
    score_band_label,
    selection_offset_label,
    shift_local_datetime,
    shift_local_datetime_minutes,
    summary_chip_lines,
    wheel_degrees,
    window_score_color,
)
from backend.electional.locations import (
    DEFAULT_TIMEZONE,
    LocationPreset,
    build_custom_location,
    combined_location_names,
    default_location_for_timezone,
    home_location_for_app,
    load_home_location_name,
    load_user_locations,
    save_home_location_name,
    save_user_locations,
    upsert_user_location,
)
from backend.electional.presets import get_preset
from backend.electional.references import dignity_table_lines, lot_reference_lines, system_reference_lines
from backend.electional.reporting import (
    build_classical_point_data_page,
    build_comparison_export_text,
    build_decision_brief_page,
    build_diagnostics_page,
    build_medieval_data_page,
    build_transit_search_page,
    build_window_comparison_page,
    condition_lines,
    constellation_lines,
    election_flag_lines,
    format_aspectarian,
    format_aspect_summary,
    format_dignity_summary,
    format_fixed_star_contact,
    format_lunar_phase,
    format_motion_summary,
    format_planet_focus,
    format_score_breakdown,
    format_window_label,
    factor_explorer_lines,
    judgment_context_lines,
    rule_lines,
    score_accounting_lines,
    score_diagnostic_lines,
    score_evaluation_lines,
)
from backend.electional.scoring import score_breakdown
from backend.electional.search import (
    SEARCH_PRESET_NAMES,
    build_search_config_from_text,
    fails_objective_antipattern,
    format_search_summary,
    has_angular_benefic,
    has_angular_malefic,
    has_applying_support,
    has_major_stress,
    moon_is_non_void,
    rejection_reasons,
    rejection_summary,
    rank_search_windows,
    search_preset_values,
    split_ranked_windows,
)
from backend.electional.screening import solar_elongation_summary
from backend.electional.session import clean_session_state, load_session_state, save_session_state
from backend.electional.shortlist import (
    SHORTLIST_TAG_CHOICES,
    add_shortlist_entry,
    add_shortlist_tag,
    build_shortlist_compare_text,
    build_shortlist_entry,
    format_shortlist_batch_diagnostics,
    format_shortlist_entries,
    normalize_shortlist_tags,
    remove_shortlist_tag,
    shortlist_batch_diagnostics,
    shortlist_entry_by_id,
    update_shortlist_tags,
)
from backend.electional.validation import validate_election_inputs, validate_search_inputs


class DesktopUiHelpersTest(unittest.TestCase):
    def test_planet_abbreviation_uses_compact_labels(self) -> None:
        self.assertEqual(planet_abbreviation("Mercury"), "Me")
        self.assertEqual(planet_abbreviation("Pluto"), "Pl")
        self.assertEqual(star_abbreviation("Galactic Center"), "GC")

    def test_wheel_degrees_places_ascendant_on_left_side(self) -> None:
        self.assertEqual(wheel_degrees(110.0, 110.0), 180)
        self.assertEqual(wheel_degrees(290.0, 110.0), 0)

    def test_planet_marker_offsets_spread_close_cluster_symmetrically(self) -> None:
        offsets = planet_marker_offsets([10.0, 13.0, 16.0], compact=False)

        self.assertLess(offsets[0][0], offsets[1][0])
        self.assertLess(offsets[1][0], offsets[2][0])
        self.assertGreater(offsets[0][1], offsets[1][1])
        self.assertGreater(offsets[2][1], offsets[1][1])

    def test_planet_marker_offsets_merge_wraparound_cluster(self) -> None:
        offsets = planet_marker_offsets([358.0, 2.0, 6.0], compact=True)

        self.assertTrue(all(radial > 0 for _, radial in offsets))
        self.assertLess(offsets[0][0], offsets[1][0])
        self.assertLess(offsets[1][0], offsets[2][0])

    def test_body_marker_offsets_support_lots_and_nodes_too(self) -> None:
        offsets = body_marker_offsets([120.0, 123.0], compact=False, crowd_threshold=10.0, angle_step=4.5, radial_step=10.0)

        self.assertEqual(len(offsets), 2)
        self.assertLess(offsets[0][0], offsets[1][0])
        self.assertTrue(all(radial > 0 for _, radial in offsets))

    def test_aspect_curve_points_route_through_inner_control_point(self) -> None:
        points = aspect_curve_points(0.0, 0.0, 100.0, 20.0, 140.0, compact=False, lane_index=1)

        self.assertEqual(len(points), 6)
        control_x, control_y = points[2], points[3]
        control_radius = (control_x ** 2 + control_y ** 2) ** 0.5
        self.assertLess(control_radius, 100.0)

    def test_header_helpers_keep_timing_and_location_readable(self) -> None:
        snapshot = {"formattedTime": "Tue, May 26, 2026, 9:23 PM PDT"}
        location = LocationPreset("user-home", "Home Base", 33.12, -117.98, "America/Los_Angeles")

        self.assertIn("May 26 9:23 PM PDT", compact_time_label(snapshot))
        self.assertIn("Home Base", location_summary(location))
        self.assertIn("America/Los_Angeles", location_summary(location))

    def test_validation_accepts_am_pm_time_and_custom_location(self) -> None:
        errors = validate_election_inputs("2026-05-26", "09:00 AM", "34.0522", "-118.2437", "America/Los_Angeles")
        location = build_custom_location("Launch Site", "34.0522", "-118.2437", "America/Los_Angeles")

        self.assertEqual(errors, [])
        self.assertEqual(location.name, "Launch Site")
        self.assertEqual(location.timezone, "America/Los_Angeles")

    def test_validation_reports_bad_coordinate_and_timezone(self) -> None:
        errors = validate_election_inputs("05/26/2026", "morning", "120", "not-west", "Pacific Time")

        self.assertIn("Date must use YYYY-MM-DD.", errors)
        self.assertIn("Time must look like 09:00 or 09:00 AM.", errors)
        self.assertIn("Latitude must be between -90 and 90.", errors)
        self.assertIn("Longitude must be a number.", errors)
        self.assertIn("Time zone must be a valid IANA name like America/Los_Angeles.", errors)

    def test_search_config_parses_optional_desktop_controls(self) -> None:
        config = build_search_config_from_text("12", "30", "60", "8", "2", True)

        self.assertEqual(config.end_offset_minutes, 720)
        self.assertEqual(config.step_minutes, 30)
        self.assertEqual(config.minimum_score, 60)
        self.assertEqual(config.max_results, 8)
        self.assertEqual(config.minimum_fit, 2)
        self.assertTrue(config.avoid_major_stress)
        self.assertEqual(format_search_summary(config), "Scan 12h from start, every 30m; score >= 60, fit >= 2, no major stress, top 8.")

    def test_search_config_parses_diagnostic_filters(self) -> None:
        config = build_search_config_from_text(
            "12",
            "30",
            "60",
            "8",
            "2",
            require_applying_support=True,
            require_angular_benefic=True,
            minimum_confidence_text="70",
            minimum_cleanliness_text="68",
            maximum_volatility_text="35",
        )

        self.assertEqual(config.minimum_confidence, 70)
        self.assertEqual(config.minimum_cleanliness, 68)
        self.assertEqual(config.maximum_volatility, 35)
        self.assertTrue(config.require_applying_support)
        self.assertTrue(config.require_angular_benefic)
        self.assertIn("confidence >= 70", format_search_summary(config))
        self.assertIn("cleanliness >= 68", format_search_summary(config))
        self.assertIn("volatility <= 35", format_search_summary(config))
        self.assertIn("needs angular benefic", format_search_summary(config))

    def test_objective_search_presets_expose_expected_names_and_filters(self) -> None:
        self.assertIn("Strict Launch", SEARCH_PRESET_NAMES)
        launch = search_preset_values("Strict Launch")
        travel = search_preset_values("Safe Travel")

        self.assertTrue(launch["require_angular_benefic"])
        self.assertTrue(launch["avoid_objective_antipatterns"])
        self.assertTrue(travel["require_moon_non_void"])
        self.assertEqual(search_preset_values("Custom"), {})

    def test_search_validation_rejects_impossible_values(self) -> None:
        errors = validate_search_inputs("1", "90", "100", "0", "9")

        self.assertIn("Step minutes must fit inside the scan range.", errors)
        self.assertIn("Minimum score must be 99 or lower.", errors)
        self.assertIn("Max results must be at least 1.", errors)
        self.assertIn("Minimum fit must be 5 or lower.", errors)

    def test_search_validation_rejects_out_of_range_diagnostic_filters(self) -> None:
        errors = validate_search_inputs("12", "60", "50", "5", "2", "100", "101", "120")

        self.assertIn("Minimum confidence must be 99 or lower.", errors)
        self.assertIn("Minimum cleanliness must be 99 or lower.", errors)
        self.assertIn("Maximum volatility must be 99 or lower.", errors)

    def test_rank_search_windows_can_filter_for_fit_and_major_stress(self) -> None:
        clean_high_fit = {
            "score": 90,
            "scoreBreakdown": {"objectiveMatches": 2},
            "detectedAspects": [{"tone": "support", "orb": 1.1, "isApplying": True}],
            "positions": [{"name": "Jupiter", "isAngular": True, "closestAngle": {"distance": 2.0}}],
        }
        stressed = {
            "score": 95,
            "scoreBreakdown": {"objectiveMatches": 3},
            "detectedAspects": [{"tone": "stress", "orb": 0.8, "isApplying": True}],
            "positions": [{"name": "Mars", "isAngular": True, "closestAngle": {"distance": 2.0}}],
        }
        low_fit = {
            "score": 92,
            "scoreBreakdown": {"objectiveMatches": 0},
            "detectedAspects": [],
            "positions": [],
        }

        ranked = rank_search_windows(
            [stressed, clean_high_fit, low_fit],
            build_search_config_from_text("12", "30", "60", "", "2", True),
        )

        self.assertEqual(ranked, [clean_high_fit])

    def test_rank_search_windows_can_require_support_avoid_angular_malefics_and_keep_moon_non_void(self) -> None:
        clean = {
            "score": 88,
            "scoreBreakdown": {"objectiveMatches": 2},
            "detectedAspects": [{"tone": "support", "orb": 1.2, "isApplying": True}],
            "positions": [{"name": "Jupiter", "isAngular": True, "closestAngle": {"distance": 2.0}}],
            "moonCondition": {"voidOfCourse": {"isVoid": False}},
        }
        no_support = {
            "score": 90,
            "scoreBreakdown": {"objectiveMatches": 2},
            "detectedAspects": [{"tone": "support", "orb": 2.8, "isApplying": False}],
            "positions": [],
            "moonCondition": {"voidOfCourse": {"isVoid": False}},
        }
        angular_malefic = {
            "score": 92,
            "scoreBreakdown": {"objectiveMatches": 2},
            "detectedAspects": [{"tone": "support", "orb": 1.0, "isApplying": True}],
            "positions": [{"name": "Mars", "isAngular": True, "closestAngle": {"distance": 2.0}}],
            "moonCondition": {"voidOfCourse": {"isVoid": False}},
        }
        void_moon = {
            "score": 89,
            "scoreBreakdown": {"objectiveMatches": 2},
            "detectedAspects": [{"tone": "support", "orb": 1.0, "isApplying": True}],
            "positions": [],
            "moonCondition": {"voidOfCourse": {"isVoid": True}},
        }

        ranked = rank_search_windows(
            [void_moon, angular_malefic, no_support, clean],
            build_search_config_from_text(
                "12",
                "30",
                "60",
                "",
                "2",
                require_applying_support=True,
                avoid_angular_malefics=True,
                require_moon_non_void=True,
            ),
        )

        self.assertEqual(ranked, [clean])

    def test_rank_search_windows_can_avoid_objective_antipatterns(self) -> None:
        clean = {
            "score": 87,
            "objective": "Meeting or negotiation",
            "scoreBreakdown": {"objectiveMatches": 2},
            "detectedAspects": [{"tone": "support", "orb": 1.0, "isApplying": True}],
            "positions": [{"name": "Jupiter", "isAngular": False, "isRetrograde": False}],
            "moonCondition": {"voidOfCourse": {"isVoid": False}},
        }
        bad_negotiation = {
            "score": 93,
            "objective": "Meeting or negotiation",
            "scoreBreakdown": {"objectiveMatches": 2},
            "detectedAspects": [{"tone": "stress", "orb": 0.8, "isApplying": True}],
            "positions": [{"name": "Mercury", "isAngular": False, "isRetrograde": True}],
            "moonCondition": {"voidOfCourse": {"isVoid": False}},
        }

        ranked = rank_search_windows(
            [bad_negotiation, clean],
            build_search_config_from_text(
                "12",
                "30",
                "60",
                "",
                "1",
                avoid_objective_antipatterns=True,
            ),
        )

        self.assertTrue(fails_objective_antipattern(bad_negotiation, "Meeting or negotiation"))
        self.assertEqual(ranked, [clean])

    def test_rank_search_windows_can_filter_by_diagnostics_and_angular_benefic(self) -> None:
        strongest = {
            "score": 90,
            "scoreBreakdown": {
                "objectiveMatches": 2,
                "diagnostics": {
                    "confidence": {"score": 84},
                    "cleanliness": {"score": 79},
                    "volatility": {"score": 28},
                    "readiness": {"score": 81},
                },
            },
            "detectedAspects": [{"tone": "support", "orb": 1.0, "isApplying": True}],
            "positions": [{"name": "Venus", "isAngular": True, "closestAngle": {"distance": 2.0}}],
        }
        noisy = {
            "score": 95,
            "scoreBreakdown": {
                "objectiveMatches": 3,
                "diagnostics": {
                    "confidence": {"score": 59},
                    "cleanliness": {"score": 52},
                    "volatility": {"score": 64},
                    "readiness": {"score": 75},
                },
            },
            "detectedAspects": [{"tone": "support", "orb": 1.0, "isApplying": True}],
            "positions": [{"name": "Jupiter", "isAngular": False, "closestAngle": {"distance": 12.0}}],
        }

        ranked = rank_search_windows(
            [noisy, strongest],
            build_search_config_from_text(
                "12",
                "30",
                "60",
                "",
                "1",
                require_applying_support=True,
                require_angular_benefic=True,
                minimum_confidence_text="70",
                minimum_cleanliness_text="70",
                maximum_volatility_text="35",
            ),
        )

        self.assertTrue(has_angular_benefic(strongest))
        self.assertEqual(ranked, [strongest])

    def test_rejection_reasons_and_summary_explain_why_windows_failed(self) -> None:
        window = {
            "formattedTime": "Tue, May 26, 2026, 1:00 PM PDT",
            "score": 63,
            "objective": "Safe Travel",
            "scoreBreakdown": {
                "objectiveMatches": 0,
                "diagnostics": {
                    "confidence": {"score": 58},
                    "cleanliness": {"score": 60},
                    "volatility": {"score": 52},
                },
            },
            "detectedAspects": [{"tone": "stress", "orb": 0.8, "isApplying": True}],
            "positions": [{"name": "Mars", "isAngular": True, "closestAngle": {"distance": 2.0}}],
            "moonCondition": {"voidOfCourse": {"isVoid": True}},
        }
        config = build_search_config_from_text(
            "12",
            "30",
            "70",
            "",
            "1",
            avoid_major_stress=True,
            avoid_angular_malefics=True,
            require_moon_non_void=True,
            minimum_confidence_text="70",
            maximum_volatility_text="35",
        )

        reasons = rejection_reasons(window, config)
        kept, rejected = split_ranked_windows([window], config)
        summary = rejection_summary(rejected)

        self.assertEqual(kept, [])
        self.assertIn("score 63 below minimum 70", reasons)
        self.assertIn("confidence 58 below minimum 70", reasons)
        self.assertIn("major stress present", reasons)
        self.assertEqual(summary["count"], 1)
        self.assertTrue(any("major stress present" == reason for reason, _count in summary["topReasons"]))

    def test_has_major_stress_detects_tight_stress_or_angular_malefic(self) -> None:
        self.assertTrue(
            has_major_stress(
                {
                    "detectedAspects": [{"tone": "stress", "orb": 0.9, "isApplying": False}],
                    "positions": [],
                }
            )
        )

    def test_deeper_search_helpers_detect_support_malefics_and_void_moon(self) -> None:
        self.assertTrue(has_applying_support({"detectedAspects": [{"tone": "support", "isApplying": True}]}))
        self.assertTrue(
            has_angular_malefic({"positions": [{"name": "Saturn", "isAngular": True, "closestAngle": {"distance": 3.0}}]})
        )
        self.assertFalse(moon_is_non_void({"moonCondition": {"voidOfCourse": {"isVoid": True}}}))
        self.assertTrue(
            has_major_stress(
                {
                    "detectedAspects": [],
                    "positions": [{"name": "Saturn", "isAngular": True, "closestAngle": {"distance": 2.5}}],
                }
            )
        )

    def test_default_location_matches_local_timezone(self) -> None:
        location = default_location_for_timezone(DEFAULT_TIMEZONE)

        self.assertEqual(location.timezone, "America/Los_Angeles")
        self.assertEqual(location.name, "Los Angeles, CA")

    def test_shift_local_datetime_crosses_midnight(self) -> None:
        next_date, next_time = shift_local_datetime("2026-05-26", "11:30 PM", "America/Los_Angeles", 2)

        self.assertEqual(next_date, "2026-05-27")
        self.assertEqual(next_time, "01:30")

    def test_shift_local_datetime_minutes_supports_electional_fine_tuning(self) -> None:
        next_date, next_time = shift_local_datetime_minutes("2026-05-26", "23:58", "America/Los_Angeles", 5)

        self.assertEqual(next_date, "2026-05-27")
        self.assertEqual(next_time, "00:03")

    def test_window_label_summarizes_support_and_stress_counts(self) -> None:
        label = format_window_label(
            1,
            {
                "time": "9:00 AM PDT",
                "score": 77,
                "title": "High-priority election",
                "detectedAspects": [
                    {"tone": "support"},
                    {"tone": "support"},
                    {"tone": "stress"},
                ],
            },
        )

        self.assertIn("+2/!1", label)
        self.assertIn("Score 77", label)

    def test_window_label_handles_empty_aspects(self) -> None:
        label = format_window_label(2, {"time": "11:00 AM PDT", "score": 61, "title": "Workable election", "detectedAspects": []})

        self.assertIn("+0/!0", label)
        self.assertIn("Workable election", label)

    def test_window_score_color_groups_score_ranges(self) -> None:
        self.assertEqual(window_score_color(90), "#e6f6ef")
        self.assertEqual(window_score_color(82), "#eef7f5")
        self.assertEqual(window_score_color(65), "#fff5df")
        self.assertEqual(window_score_color(44), "#f9e7eb")
        self.assertEqual(score_band_label(90), "Prime")
        self.assertEqual(score_band_label(82), "Strong")
        self.assertEqual(score_band_label(65), "Workable")
        self.assertEqual(score_band_label(44), "Caution")

    def test_summary_chip_lines_surface_chart_context(self) -> None:
        snapshot = {
            "lunarPhase": {"name": "Waxing Gibbous"},
            "fixedStarContacts": [{"label": "Venus conjunct Spica"}],
            "planetaryHour": {"available": True, "hourRuler": "Jupiter"},
            "zodiacSystem": type("System", (), {"name": "Sidereal Lahiri"})(),
            "houseSystem": type("HouseSystem", (), {"name": "Koch"})(),
        }

        self.assertEqual(fixed_star_contact_count(snapshot), 1)
        chips = summary_chip_lines(snapshot, "Classical 7")

        self.assertIn("Moon: Waxing Gibbous", chips)
        self.assertIn("Hour: Jupiter", chips)
        self.assertIn("Points: Classical 7", chips)
        self.assertIn("Zodiac: Sidereal Lahiri", chips)
        self.assertIn("Houses: Koch", chips)

    def test_selection_offset_label_explains_current_vs_selected(self) -> None:
        start = {"date": datetime(2026, 5, 26, 16, 0)}
        same = {"date": datetime(2026, 5, 26, 16, 0)}
        later = {"date": datetime(2026, 5, 26, 18, 30)}
        earlier = {"date": datetime(2026, 5, 26, 15, 45)}

        self.assertEqual(selection_offset_label(start, same), "Selected equals search start")
        self.assertEqual(selection_offset_label(start, later), "Selected +2h 30m from start")
        self.assertEqual(selection_offset_label(start, earlier), "Selected -15m from start")

    def test_planet_focus_includes_dignity_and_contacts(self) -> None:
        planet = {
            "id": "venus",
            "name": "Venus",
            "zodiac": {"sign": "Cancer", "degree": 9, "minute": 23},
            "house": 10,
            "dignity": {"label": "Peregrine", "boundLord": "Venus", "isOwnBound": True},
            "closestAngle": {"shortName": "MC", "distance": 3.2},
            "isAngular": True,
            "motion": {"label": "Direct", "dailyLongitudeChange": 1.2},
        }
        focus = format_planet_focus(planet, [{"label": "Venus trine Moon", "orbText": "1 deg", "bodies": ["Venus", "Moon"]}])

        self.assertIn("Venus", focus)
        self.assertIn("Dignity: Peregrine", focus)
        self.assertIn("Egyptian bound: Venus", focus)
        self.assertIn("Motion: Direct", focus)
        self.assertIn("own Egyptian bound", focus)
        self.assertIn("Venus trine Moon", focus)

    def test_dignity_summary_includes_bound_context(self) -> None:
        summary = format_dignity_summary({"dignity": {"label": "Bound", "boundLord": "Mercury", "isOwnBound": True}})

        self.assertEqual(summary, "Bound / Bound Mercury own bound")

    def test_score_breakdown_summary_is_human_readable(self) -> None:
        summary = format_score_breakdown(
            {
                "score": 72,
                "scoreBreakdown": {
                    "base": 58,
                    "support": 1,
                    "mixed": 0,
                    "stress": 1,
                    "objectiveMatches": 1,
                    "closeContacts": 1,
                    "angularity": 4.5,
                    "dignity": 2,
                    "retrogradePressure": 3,
                    "accounting": {
                        "startingScore": 58,
                        "positiveTotal": 20,
                        "negativeTotal": -5,
                        "netAdjustment": 15,
                        "rawScore": 72.4,
                        "finalScore": 72,
                        "categoryTotals": {"Aspect quality": 7, "Risk pressure": -3},
                    },
                    "evaluation": {
                        "band": "Workable",
                        "grade": "C",
                        "summary": "Workable electional window with net +15.0 points.",
                        "strengths": ["Aspect quality +7.0"],
                        "risks": ["Risk pressure -3.0"],
                    },
                    "rawScore": 72.4,
                    "score": 72,
                },
            }
        )

        self.assertIn("support 1", summary)
        self.assertIn("retrograde pressure 3.0", summary)
        self.assertIn("raw 72.4 -> final 72", summary)

    def test_score_breakdown_applies_objective_specific_weighting(self) -> None:
        preset = get_preset("traditional-lilly")
        positions = [
            {
                "name": "Mercury",
                "isAngular": False,
                "isRetrograde": True,
                "dignity": {"score": 0},
            },
            {
                "name": "Jupiter",
                "isAngular": True,
                "isRetrograde": False,
                "closestAngle": {"distance": 2.0},
                "dignity": {"score": 3},
            },
        ]
        aspects = [
            {"aspectId": "trine", "tone": "support", "orb": 1.0, "isApplying": True, "timingQuality": "soon"},
            {"aspectId": "square", "tone": "stress", "orb": 1.0, "isApplying": True, "timingQuality": "soon"},
        ]

        launch = score_breakdown(aspects, positions, preset, objective="Launch or publish")
        travel = score_breakdown(aspects, positions, preset, objective="Travel departure")

        self.assertNotEqual(launch["score"], travel["score"])
        reasons = travel["reasons"]
        self.assertTrue(any(reason.get("code") == "objective-weighting" for reason in reasons))

    def test_score_breakdown_includes_backend_diagnostics(self) -> None:
        preset = get_preset("traditional-lilly")
        positions = [
            {
                "name": "Mercury",
                "isAngular": False,
                "isRetrograde": False,
                "dignity": {"score": 0},
            },
            {
                "name": "Jupiter",
                "isAngular": True,
                "isRetrograde": False,
                "closestAngle": {"distance": 2.0},
                "dignity": {"score": 3},
            },
        ]
        aspects = [
            {"aspectId": "trine", "tone": "support", "orb": 1.0, "isApplying": True, "timingQuality": "soon"},
        ]

        breakdown = score_breakdown(aspects, positions, preset, objective="Launch or publish")
        diagnostics = breakdown.get("diagnostics", {})

        self.assertIn("readiness", diagnostics)
        self.assertIn("volatility", diagnostics)
        self.assertIn("cleanliness", diagnostics)
        self.assertIn("confidence", diagnostics)
        self.assertIn("signals", diagnostics)
        self.assertIsInstance(diagnostics["confidence"]["score"], int)

    def test_score_accounting_and_evaluation_lines_are_human_readable(self) -> None:
        snapshot = {
            "scoreBreakdown": {
                "score": 72,
                "accounting": {
                    "startingScore": 58,
                    "positiveTotal": 18.5,
                    "negativeTotal": -4,
                    "netAdjustment": 14.5,
                    "rawScore": 72.5,
                    "finalScore": 72,
                    "categoryTotals": {"Aspect quality": 7, "Risk pressure": -4},
                },
                "evaluation": {
                    "band": "Workable",
                    "grade": "C",
                    "summary": "Workable electional window with net +14.5 points.",
                    "strengths": ["Aspect quality +7.0"],
                    "risks": ["Risk pressure -4.0"],
                },
            }
        }

        self.assertIn("positive +18.5", "\n".join(score_accounting_lines(snapshot)))
        self.assertIn("Aspect quality", "\n".join(score_accounting_lines(snapshot)))
        self.assertIn("Grade C", "\n".join(score_evaluation_lines(snapshot)))

    def test_score_diagnostic_lines_and_page_are_human_readable(self) -> None:
        snapshot = {
            "score": 78,
            "scoreBreakdown": {
                "evaluation": {"band": "Strong", "grade": "B"},
                "diagnostics": {
                    "readiness": {"score": 82, "band": "Strong", "summary": "Ready to act."},
                    "volatility": {"score": 36, "band": "Moderate", "summary": "Some motion remains."},
                    "cleanliness": {"score": 76, "band": "Usable", "summary": "Mostly coherent chart."},
                    "confidence": {"score": 71, "band": "Solid", "summary": "Signals agree well enough."},
                    "signals": {
                        "applyingSupport": True,
                        "angularBenefic": True,
                        "majorStress": False,
                        "angularMalefic": False,
                        "moonNonVoid": True,
                        "objectiveAntiPatterns": [],
                    },
                },
            },
        }

        diagnostic_text = "\n".join(score_diagnostic_lines(snapshot))
        page = build_diagnostics_page(snapshot)

        self.assertIn("Readiness: 82", diagnostic_text)
        self.assertIn("Signal: applying support is present.", diagnostic_text)
        self.assertIn("Signal: angular benefic emphasis is present.", diagnostic_text)
        self.assertIn("Window Diagnostics", page)
        self.assertIn("Confidence: 71", page)

    def test_constellation_lines_explain_rising_size_and_speed(self) -> None:
        snapshot = {
            "constellationContext": {
                "sourceNote": "diagnostic note",
                "rising": {
                    "ascendantConstellation": {
                        "name": "Scorpius",
                        "spanDegrees": 6,
                        "spanRatioToSign": 0.2,
                        "percentThrough": 0.5,
                        "distanceToEndDegrees": 3,
                        "nextConstellation": {"name": "Ophiuchus"},
                    },
                    "ascendantSpeedDegPerHour": 25,
                    "tempo": {"label": "fast", "scoreImpact": 1},
                    "spanContext": {"label": "narrow", "scoreImpact": -0.5},
                    "currentConstellationRisingMinutes": 16,
                    "currentSignRisingMinutes": 110,
                    "minutesToNextConstellation": 7,
                },
                "positions": [
                    {"name": "Sun", "constellation": {"name": "Virgo", "spanDegrees": 44}},
                    {"name": "Moon", "constellation": {"name": "Libra", "spanDegrees": 24}},
                ],
            }
        }
        text = "\n".join(constellation_lines(snapshot))

        self.assertIn("Scorpius", text)
        self.assertIn("25.0 deg/hour", text)
        self.assertIn("current 30 deg sign", text)

    def test_judgment_and_factor_explorer_lines_are_human_readable(self) -> None:
        snapshot = {
            "score": 71,
            "significatorContext": {
                "summary": "Launch or publish: 3 primary significator(s) selected.",
                "scoreImpact": 1.5,
                "confidence": "solid",
                "factors": [
                    {
                        "title": "Mercury significator condition",
                        "detail": "Mercury serves as public launch natural significator.",
                        "scoreImpact": 1.5,
                        "severity": "support",
                    }
                ],
            },
            "moonCondition": {"summary": "Moon available.", "scoreImpact": 0, "confidence": "approximate", "factors": []},
            "houseRulerContext": {"summary": "House ruler available.", "scoreImpact": 0, "confidence": "solid", "factors": []},
            "receptionContext": {"summary": "No reception.", "scoreImpact": 0, "confidence": "solid", "factors": []},
            "planetConditionContext": {"summary": "No conditions.", "scoreImpact": 0, "confidence": "approximate", "factors": []},
            "advancedAspectContext": {"summary": "No patterns.", "scoreImpact": 0, "confidence": "experimental", "factors": []},
        }

        self.assertIn("Mercury significator", "\n".join(judgment_context_lines(snapshot, "significatorContext")))
        self.assertIn("Significators", "\n".join(factor_explorer_lines(snapshot)))

    def test_lunar_and_motion_summaries_are_human_readable(self) -> None:
        phase = format_lunar_phase(
            {
                "lunarPhase": {
                    "name": "Waxing Gibbous",
                    "illumination": 0.82,
                    "ageDays": 10.5,
                    "isWaxing": True,
                }
            }
        )
        motion = format_motion_summary({"motion": {"label": "Retrograde", "dailyLongitudeChange": -0.42}})

        self.assertIn("Waxing Gibbous", phase)
        self.assertIn("82% lit", phase)
        self.assertEqual(motion, "Retrograde -0.42 deg/day")

    def test_aspect_summary_includes_applying_phase(self) -> None:
        summary = format_aspect_summary(
            {
                "label": "Venus trine Jupiter",
                "orbText": "1 deg 30 min",
                "phase": "applying",
                "phaseLabel": "Applying",
                "orbChangePerDay": -0.75,
                "isApplying": True,
                "timeToExactText": "2d",
                "perfectsAtText": "Thu, May 28, 2026, 9:00 AM PDT",
            }
        )

        self.assertIn("applying", summary)
        self.assertIn("-0.75 deg/day", summary)
        self.assertIn("exact in 2d", summary)

    def test_condition_lines_collect_lunar_phase_and_retrogrades(self) -> None:
        lines = condition_lines(
            {
                "lunarPhase": {
                    "name": "Waning Gibbous",
                    "illumination": 0.73,
                    "ageDays": 18.2,
                    "isWaxing": False,
                },
                "positions": [
                    {
                        "name": "Mercury",
                        "isRetrograde": True,
                        "motion": {"label": "Retrograde", "dailyLongitudeChange": -0.35},
                    }
                ],
                "detectedAspects": [
                    {"label": "Venus trine Jupiter", "tone": "support", "isApplying": True},
                ],
            }
        )
        text = "\n".join(lines)

        self.assertIn("Waning Gibbous", text)
        self.assertIn("Retrograde: Mercury", text)
        self.assertIn("Election Flags", text)

    def test_election_flags_call_out_tightening_and_angular_conditions(self) -> None:
        flags = election_flag_lines(
            {
                "lunarPhase": {"name": "Waxing Crescent", "isWaxing": True},
                "detectedAspects": [
                    {"label": "Venus trine Jupiter", "tone": "support", "isApplying": True},
                    {"label": "Mars square Moon", "tone": "stress", "isApplying": True},
                ],
                "positions": [
                    {"name": "Jupiter", "isAngular": True},
                    {"name": "Mars", "isAngular": True},
                ],
            }
        )
        text = "\n".join(flags)

        self.assertIn("Tightening support", text)
        self.assertIn("Tightening stress", text)
        self.assertIn("Angular benefic", text)
        self.assertIn("Angular malefic", text)
        self.assertIn("favors building", text)

    def test_rule_lines_format_active_electional_rules(self) -> None:
        lines = rule_lines(
            {
                "ruleEvaluations": {
                    "rules": [
                        {
                            "title": "Mercury combust",
                            "detail": "Mercury is combust the Sun.",
                            "scoreImpact": -5,
                        }
                    ]
                }
            }
        )

        self.assertIn("Mercury combust", lines[0])
        self.assertIn("-5.0", lines[0])

    def test_dignity_table_includes_classical_rulerships(self) -> None:
        lines = dignity_table_lines()
        reference = "\n".join(lines)

        self.assertIn("Sign", lines[0])
        self.assertTrue(any("Aries" in line and "Mars" in line for line in lines))
        self.assertTrue(any("Libra" in line and "Venus" in line for line in lines))
        self.assertIn("Egyptian Bounds", reference)
        self.assertIn("0-6 Jupiter", reference)

    def test_system_reference_includes_sidereal_and_topocentric(self) -> None:
        reference = "\n".join(system_reference_lines())

        self.assertIn("Sidereal Lahiri", reference)
        self.assertIn("Sidereal Fagan-Bradley", reference)
        self.assertIn("Topocentric", reference)
        self.assertIn("Polich-Page", reference)
        self.assertIn("Koch", reference)
        self.assertIn("sefstars.txt", reference)

    def test_fixed_star_contact_summary_is_human_readable(self) -> None:
        summary = format_fixed_star_contact(
            {
                "label": "Venus conjunct Spica",
                "orbText": "0 deg 14 min",
                "tone": "support",
                "score": 4.0,
            }
        )

        self.assertIn("Venus conjunct Spica", summary)
        self.assertIn("+4.0", summary)

    def test_aspectarian_formats_detected_contacts(self) -> None:
        table = format_aspectarian(
            {
                "positions": [{"name": "Sun"}, {"name": "Moon"}, {"name": "Venus"}],
                "detectedAspects": [
                    {
                        "bodies": ["Sun", "Moon"],
                        "aspectName": "Trine",
                        "tone": "support",
                    },
                    {
                        "bodies": ["Moon", "Venus"],
                        "aspectName": "Square",
                        "tone": "stress",
                    },
                ],
            }
        )

        self.assertIn("Aspectarian", table)
        self.assertIn("+Tri", table)
        self.assertIn("!Sqr", table)

    def test_lot_reference_includes_new_hermetic_lots(self) -> None:
        reference = "\n".join(lot_reference_lines())

        self.assertIn("Seven Hermetic Lots", reference)
        self.assertIn("Part of Eros", reference)
        self.assertIn("Part of Nemesis", reference)

    def test_solar_elongation_summary_lists_inner_planets(self) -> None:
        snapshot = {
            "positions": [
                {"name": "Sun", "longitude": 10.0, "zodiac": {"sign": "Aries", "degree": 10, "minute": 0}},
                {"name": "Mercury", "longitude": 18.0, "zodiac": {"sign": "Aries", "degree": 18, "minute": 0}},
                {"name": "Venus", "longitude": 50.0, "zodiac": {"sign": "Taurus", "degree": 20, "minute": 0}},
            ]
        }
        summary = "\n".join(solar_elongation_summary(snapshot))

        self.assertIn("Mercury", summary)
        self.assertIn("Under beams", summary)
        self.assertIn("Venus", summary)

    def test_session_state_round_trip(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "session.json"
            state = {
                "date": "2026-05-26",
                "time": "9:30 PM",
                "location_name": "Paris",
                "latitude": "48.8566",
                "longitude": "2.3522",
                "timezone": "Europe/Paris",
                "scan_hours": "24",
                "step_minutes": "30",
                "minimum_score": "70",
                "minimum_confidence": "72",
                "minimum_cleanliness": "69",
                "maximum_volatility": "34",
                "max_results": "12",
                "require_angular_benefic": True,
                "avoid_objective_antipatterns": True,
                "display_options": {"show_aspects": False, "compact_wheel": True, "wheel_zoom": 0.94},
            }

            save_session_state(state, path)
            loaded = clean_session_state(load_session_state(path))

        self.assertEqual(loaded["date"], "2026-05-26")
        self.assertEqual(loaded["time"], "21:30")
        self.assertEqual(loaded["timezone"], "Europe/Paris")
        self.assertEqual(loaded["scan_hours"], "24")
        self.assertEqual(loaded["step_minutes"], "30")
        self.assertEqual(loaded["minimum_score"], "70")
        self.assertEqual(loaded["minimum_confidence"], "72")
        self.assertEqual(loaded["minimum_cleanliness"], "69")
        self.assertEqual(loaded["maximum_volatility"], "34")
        self.assertEqual(loaded["max_results"], "12")
        self.assertTrue(loaded["require_angular_benefic"])
        self.assertTrue(loaded["avoid_objective_antipatterns"])
        self.assertFalse(loaded["display_options"]["show_aspects"])
        self.assertTrue(loaded["display_options"]["compact_wheel"])
        self.assertFalse(loaded["display_options"]["show_fixed_stars"])
        self.assertEqual(loaded["display_options"]["wheel_zoom"], 0.94)
        self.assertEqual(loaded["display_options"]["point_set"], "ten-planets")
        self.assertEqual(loaded["display_options"]["page_mode"], "wheel")

    def test_user_locations_round_trip(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "locations.json"
            location = LocationPreset("user-home", "Home Base", 33.12, -117.98, "America/Los_Angeles")

            save_user_locations([location], path)
            loaded = load_user_locations(path)

        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].name, "Home Base")
        self.assertEqual(loaded[0].timezone, "America/Los_Angeles")

    def test_home_location_name_round_trip(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "location-settings.json"

            save_home_location_name("Temple Office", path)
            loaded = load_home_location_name(path)
            save_home_location_name(None, path)
            cleared = load_home_location_name(path)

        self.assertEqual(loaded, "Temple Office")
        self.assertIsNone(cleared)

    def test_home_location_for_app_prefers_saved_home(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "location-settings.json"
            save_home_location_name("Temple Office", settings_path)
            location = home_location_for_app(
                user_locations=[LocationPreset("user-temple", "Temple Office", 35.0, -120.0, "America/Los_Angeles")],
                settings_path=settings_path,
            )

        self.assertEqual(location.name, "Temple Office")

    def test_session_state_infers_full_point_set_from_legacy_lot_display(self) -> None:
        loaded = clean_session_state({"display_options": {"show_lots": True}})

        self.assertEqual(loaded["display_options"]["point_set"], "full-electional")

    def test_user_location_upsert_replaces_same_name(self) -> None:
        original = LocationPreset("user-home", "Home Base", 33.0, -118.0, "America/Los_Angeles")
        updated = LocationPreset("user-home", "Home Base", 34.0, -119.0, "America/Los_Angeles")

        locations = upsert_user_location([original], updated)

        self.assertEqual(len(locations), 1)
        self.assertEqual(locations[0].latitude, 34.0)

    def test_medieval_data_page_summarizes_classical_context(self) -> None:
        snapshot = {
            "preset": type("Preset", (), {"name": "Traditional Lilly"})(),
            "zodiacSystem": type("System", (), {"name": "Sidereal Lahiri"})(),
            "houseSystem": type("HouseSystem", (), {"name": "Koch"})(),
            "ayanamsha": 24.1,
            "score": 92,
            "lunarPhase": {"name": "Waxing Gibbous", "illumination": 0.72, "ageDays": 10.2, "isWaxing": True},
            "judgmentContexts": {
                "significatorContext": {"summaryLines": ["- Jupiter signifies launch success."]},
                "moonCondition": {"summaryLines": ["- Moon applies to a benefic."]},
                "houseRulerContext": {"summaryLines": ["- 10th ruler is dignified."]},
                "receptionContext": {"summaryLines": ["- Venus receives Mercury by sign."]},
                "planetConditionContext": {"summaryLines": ["- Jupiter is angular."]},
            },
            "lots": [{"name": "Part of Fortune", "zodiac": {"sign": "Aries", "degree": 12, "minute": 0}, "house": 10, "formula": "ASC + Moon - Sun"}],
        }

        text = build_medieval_data_page(snapshot)

        self.assertIn("Medieval Data Page", text)
        self.assertIn("Traditional Lilly", text)
        self.assertIn("Part of Fortune", text)
        self.assertIn("Verdict", text)
        self.assertIn("Balance of Testimony", text)
        self.assertIn("Moon and Significators", text)

    def test_classical_point_data_page_summarizes_positions_lots_and_nodes(self) -> None:
        snapshot = {
            "preset": type("Preset", (), {"name": "Traditional Lilly"})(),
            "zodiacSystem": type("System", (), {"name": "Sidereal Lahiri"})(),
            "houseSystem": type("HouseSystem", (), {"name": "Koch"})(),
            "ayanamsha": 24.1,
            "score": 92,
            "positions": [
                {
                    "name": "Jupiter",
                    "house": 10,
                    "zodiac": {"sign": "Aries", "degree": 12, "minute": 0},
                    "dignity": {"label": "Domicile", "boundLord": "Jupiter", "isOwnBound": False},
                    "motion": {"label": "Direct", "dailyLongitudeChange": 0.23},
                    "closestAngle": {"shortName": "MC", "distance": 2.1},
                }
            ],
            "angles": [{"shortName": "ASC", "zodiac": {"sign": "Cancer", "degree": 20, "minute": 8}}],
            "houseCusps": [{"house": 10, "zodiac": {"sign": "Aries", "degree": 6, "minute": 32}}],
            "lots": [
                {
                    "name": "Part of Fortune",
                    "zodiac": {"sign": "Aries", "degree": 12, "minute": 0},
                    "house": 10,
                    "formula": "ASC + Moon - Sun",
                    "topic": "Prosperity",
                }
            ],
            "lunarNodes": [
                {
                    "name": "True North Node",
                    "zodiac": {"sign": "Pisces", "degree": 18, "minute": 30},
                    "house": 9,
                    "calculation": "true node",
                }
            ],
            "fixedStarContacts": [{"label": "Venus conjunct Spica", "orbText": "0 deg 14 min", "tone": "support", "score": 4.0}],
        }

        text = build_classical_point_data_page(snapshot)

        self.assertIn("Classical Point Data", text)
        self.assertIn("Jupiter", text)
        self.assertIn("House Cusps", text)
        self.assertIn("Part of Fortune", text)
        self.assertIn("True North Node", text)
        self.assertIn("Venus conjunct Spica", text)

    def test_transit_search_page_summarizes_ranked_windows(self) -> None:
        input_snapshot = {"date": datetime(2026, 5, 26, 9, 0), "formattedTime": "Tue, May 26, 2026, 9:00 AM PDT"}
        selected_window = {
            "date": datetime(2026, 5, 26, 11, 0),
            "formattedTime": "Tue, May 26, 2026, 11:00 AM PDT",
            "title": "Launch or publish",
            "score": 94,
            "note": "Strong angular benefic support.",
            "detectedAspects": [{"label": "Sun trine Jupiter"}],
            "timingProfile": {"summary": "Next support perfects within the hour."},
            "preset": type("Preset", (), {"name": "Traditional Lilly"})(),
        }
        windows = [selected_window]
        location = LocationPreset("los-angeles", "Los Angeles, CA", 34.0522, -118.2437, "America/Los_Angeles")

        text = build_transit_search_page(input_snapshot, selected_window, windows, location, "Scan 12h from start, every 30m; score >= 70.")

        self.assertIn("Transit Search Page", text)
        self.assertIn("Difference: +2h", text)
        self.assertIn("Los Angeles, CA", text)
        self.assertIn("Sun trine Jupiter", text)

    def test_transit_search_page_can_include_rejection_reasons(self) -> None:
        input_snapshot = {"date": datetime(2026, 5, 26, 9, 0), "formattedTime": "Tue, May 26, 2026, 9:00 AM PDT"}
        selected_window = {
            "date": datetime(2026, 5, 26, 11, 0),
            "formattedTime": "Tue, May 26, 2026, 11:00 AM PDT",
            "title": "Launch or publish",
            "score": 94,
            "note": "Strong angular benefic support.",
            "detectedAspects": [{"label": "Sun trine Jupiter"}],
            "timingProfile": {"summary": "Next support perfects within the hour."},
            "preset": type("Preset", (), {"name": "Traditional Lilly"})(),
            "scoreBreakdown": {"diagnostics": {"readiness": {"score": 80, "band": "Strong", "summary": "Ready."}}},
        }
        location = LocationPreset("los-angeles", "Los Angeles, CA", 34.0522, -118.2437, "America/Los_Angeles")
        summary = {
            "count": 2,
            "topReasons": [("major stress present", 2)],
            "samples": [{"formattedTime": "Tue, May 26, 2026, 1:00 PM PDT", "score": 71, "reasons": ["major stress present"]}],
        }

        text = build_transit_search_page(input_snapshot, selected_window, [selected_window], location, "Scan 12h from start.", summary)

        self.assertIn("Rejected Windows", text)
        self.assertIn("major stress present: 2", text)
        self.assertIn("Rejected Samples", text)

    def test_decision_brief_page_translates_score_into_guidance(self) -> None:
        input_snapshot = {"date": datetime(2026, 5, 26, 9, 0)}
        selected_window = {
            "date": datetime(2026, 5, 26, 11, 0),
            "formattedTime": "Tue, May 26, 2026, 11:00 AM PDT",
            "score": 94,
            "note": "Strong angular benefic support.",
            "detectedAspects": [
                {"label": "Sun trine Jupiter", "tone": "support"},
                {"label": "Mars square Pluto", "tone": "stress"},
            ],
            "timingProfile": {"summary": "Next support perfects within the hour."},
            "scoreBreakdown": {
                "objectiveMatches": 2,
                "evaluation": {
                    "band": "Prime",
                    "grade": "A",
                    "strengths": ["Objective fit +8.0"],
                    "risks": ["Risk pressure -2.0"],
                },
                "reasons": [{"label": "Preferred aspect types", "value": 8.0, "count": 2}],
            },
        }
        location = LocationPreset("los-angeles", "Los Angeles, CA", 34.0522, -118.2437, "America/Los_Angeles")

        text = build_decision_brief_page(input_snapshot, selected_window, "Launch or publish", location)

        self.assertIn("Decision Brief", text)
        self.assertIn("Objective fit: High fit", text)
        self.assertIn("Why It Matches", text)
        self.assertIn("Watchouts", text)
        self.assertIn("Sun trine Jupiter", text)

    def test_decision_brief_page_uses_objective_specific_guidance(self) -> None:
        input_snapshot = {"date": datetime(2026, 5, 26, 9, 0)}
        selected_window = {
            "date": datetime(2026, 5, 26, 11, 0),
            "formattedTime": "Tue, May 26, 2026, 11:00 AM PDT",
            "score": 83,
            "note": "Strong angular benefic support.",
            "detectedAspects": [{"label": "Venus trine Jupiter", "tone": "support"}],
            "positions": [{"name": "Jupiter", "isAngular": True}],
            "timingProfile": {"summary": "Support perfects soon."},
            "scoreBreakdown": {
                "objectiveMatches": 1,
                "evaluation": {"band": "Strong", "grade": "B", "strengths": ["Objective fit +4.0"], "risks": []},
                "reasons": [{"label": "Preferred aspect types", "value": 4.0, "count": 1}],
            },
        }
        location = LocationPreset("los-angeles", "Los Angeles, CA", 34.0522, -118.2437, "America/Los_Angeles")

        launch_text = build_decision_brief_page(input_snapshot, selected_window, "Launch or publish", location)
        money_text = build_decision_brief_page(input_snapshot, selected_window, "Money or business", location)

        self.assertIn("visibility, momentum", launch_text)
        self.assertIn("steadier value, practical gains", money_text)

    def test_window_comparison_page_summarizes_top_candidates(self) -> None:
        input_snapshot = {"date": datetime(2026, 5, 26, 9, 0)}
        windows = [
            {
                "date": datetime(2026, 5, 26, 11, 0),
                "formattedTime": "Tue, May 26, 2026, 11:00 AM PDT",
                "score": 94,
                "title": "High-priority election",
                "note": "Strong angular benefic support.",
                "detectedAspects": [{"tone": "support"}],
                "positions": [{"isAngular": True}],
                "timingProfile": {"summary": "Next support perfects within the hour."},
                "scoreBreakdown": {
                    "objectiveMatches": 2,
                    "evaluation": {"band": "Prime", "strengths": ["Objective fit +8.0"], "risks": ["Risk pressure -2.0"]},
                },
            }
        ]

        text = build_window_comparison_page(input_snapshot, windows, "Launch or publish")

        self.assertIn("Candidate Comparison", text)
        self.assertIn("Fit 2", text)
        self.assertIn("Strength: Objective fit +8.0", text)
        self.assertIn("Risk: Risk pressure -2.0", text)

    def test_comparison_export_text_combines_brief_and_comparison(self) -> None:
        input_snapshot = {"date": datetime(2026, 5, 26, 9, 0)}
        selected_window = {
            "date": datetime(2026, 5, 26, 11, 0),
            "formattedTime": "Tue, May 26, 2026, 11:00 AM PDT",
            "score": 94,
            "title": "High-priority election",
            "note": "Strong angular benefic support.",
            "detectedAspects": [{"label": "Sun trine Jupiter", "tone": "support"}],
            "positions": [{"name": "Jupiter", "isAngular": True}],
            "timingProfile": {"summary": "Next support perfects within the hour."},
            "scoreBreakdown": {
                "objectiveMatches": 2,
                "evaluation": {"band": "Prime", "grade": "A", "strengths": ["Objective fit +8.0"], "risks": []},
                "reasons": [{"label": "Preferred aspect types", "value": 8.0, "count": 2}],
            },
        }
        location = LocationPreset("los-angeles", "Los Angeles, CA", 34.0522, -118.2437, "America/Los_Angeles")
        text = build_comparison_export_text(input_snapshot, selected_window, [selected_window], "Launch or publish", location)

        self.assertIn("Electional Decision Sheet", text)
        self.assertIn("Decision Brief", text)
        self.assertIn("Candidate Comparison", text)

    def test_shortlist_entries_rank_by_quality_not_just_insertion_order(self) -> None:
        location = LocationPreset("los-angeles", "Los Angeles, CA", 34.0522, -118.2437, "America/Los_Angeles")
        stronger = build_shortlist_entry(
            {
                "date": datetime(2026, 5, 26, 11, 0),
                "formattedTime": "Tue, May 26, 2026, 11:00 AM PDT",
                "score": 90,
                "title": "High-priority election",
                "note": "Strong angular benefic support.",
                "lunarPhase": {"name": "Waxing Gibbous", "illumination": 0.7, "ageDays": 10.0, "isWaxing": True},
                "detectedAspects": [],
                "scoreBreakdown": {
                    "diagnostics": {
                        "confidence": {"score": 84},
                        "cleanliness": {"score": 79},
                        "volatility": {"score": 24},
                        "readiness": {"score": 83},
                    }
                },
            },
            location,
            "Launch or publish",
        )
        weaker = build_shortlist_entry(
            {
                "date": datetime(2026, 5, 26, 12, 0),
                "formattedTime": "Tue, May 26, 2026, 12:00 PM PDT",
                "score": 90,
                "title": "High-priority election",
                "note": "More mixed support.",
                "lunarPhase": {"name": "Waxing Gibbous", "illumination": 0.7, "ageDays": 10.0, "isWaxing": True},
                "detectedAspects": [],
                "scoreBreakdown": {
                    "diagnostics": {
                        "confidence": {"score": 68},
                        "cleanliness": {"score": 61},
                        "volatility": {"score": 44},
                        "readiness": {"score": 72},
                    }
                },
            },
            location,
            "Launch or publish",
        )

        ranked = add_shortlist_entry([weaker], stronger)
        text = format_shortlist_entries(ranked)

        self.assertEqual(ranked[0]["formattedTime"], "Tue, May 26, 2026, 11:00 AM PDT")
        self.assertIn("Shortlist Diagnostics", text)
        self.assertIn("Best Overall", text)
        self.assertIn("Diagnostics: Conf 84  Clean 79  Read 83  Vol 24", text)

    def test_shortlist_batch_diagnostics_highlight_cleanest_confident_and_steadiest_windows(self) -> None:
        entries = [
            {
                "formattedTime": "Tue, May 26, 2026, 11:00 AM PDT",
                "objective": "Launch or publish",
                "score": 90,
                "confidence": 82,
                "cleanliness": 74,
                "readiness": 79,
                "volatility": 28,
            },
            {
                "formattedTime": "Tue, May 26, 2026, 1:00 PM PDT",
                "objective": "Meeting or negotiation",
                "score": 88,
                "confidence": 91,
                "cleanliness": 86,
                "readiness": 84,
                "volatility": 18,
            },
            {
                "formattedTime": "Tue, May 26, 2026, 3:00 PM PDT",
                "objective": "Travel departure",
                "score": 87,
                "confidence": 73,
                "cleanliness": 80,
                "readiness": 76,
                "volatility": 12,
            },
        ]

        diagnostics = shortlist_batch_diagnostics(entries)
        text = format_shortlist_batch_diagnostics(entries)

        self.assertEqual(diagnostics["count"], 3)
        self.assertEqual(diagnostics["topCleanest"][0]["formattedTime"], "Tue, May 26, 2026, 1:00 PM PDT")
        self.assertEqual(diagnostics["topConfident"][0]["formattedTime"], "Tue, May 26, 2026, 1:00 PM PDT")
        self.assertEqual(diagnostics["topSteady"][0]["formattedTime"], "Tue, May 26, 2026, 3:00 PM PDT")
        self.assertIn("Cleanest Saved Windows", text)
        self.assertIn("Highest-Confidence Windows", text)
        self.assertIn("Steadiest Windows", text)
        self.assertIn("Objective mix:", text)

    def test_shortlist_tags_can_be_added_removed_and_normalized(self) -> None:
        entries = [
            {
                "id": "abc123",
                "formattedTime": "Tue, May 26, 2026, 11:00 AM PDT",
                "score": 90,
                "confidence": 82,
                "cleanliness": 74,
                "readiness": 79,
                "volatility": 28,
                "tags": ["Backup"],
            }
        ]

        tagged = add_shortlist_tag(entries, "abc123", "Client-safe")
        tagged = add_shortlist_tag(tagged, "abc123", "backup")
        normalized = normalize_shortlist_tags([" Backup ", "backup", "", "Client-safe"])
        cleaned = shortlist_entry_by_id(tagged, "abc123")
        removed = remove_shortlist_tag(tagged, "abc123", "Backup")
        retagged = update_shortlist_tags(removed, "abc123", ["Best for launch"])

        self.assertIn("Client-safe", SHORTLIST_TAG_CHOICES)
        self.assertEqual(normalized, ["Backup", "Client-safe"])
        self.assertEqual(cleaned["tags"], ["Backup", "Client-safe"])
        self.assertEqual(shortlist_entry_by_id(removed, "abc123")["tags"], ["Client-safe"])
        self.assertEqual(shortlist_entry_by_id(retagged, "abc123")["tags"], ["Best for launch"])

    def test_shortlist_compare_text_summarizes_two_saved_windows(self) -> None:
        entries = [
            {
                "id": "a1",
                "formattedTime": "Tue, May 26, 2026, 11:00 AM PDT",
                "objective": "Launch or publish",
                "score": 90,
                "confidence": 82,
                "cleanliness": 74,
                "readiness": 79,
                "volatility": 28,
                "note": "Faster launch momentum.",
                "tags": ["Best for launch"],
            },
            {
                "id": "b2",
                "formattedTime": "Tue, May 26, 2026, 1:00 PM PDT",
                "objective": "Meeting or negotiation",
                "score": 88,
                "confidence": 91,
                "cleanliness": 86,
                "readiness": 84,
                "volatility": 18,
                "note": "Cleaner client-facing option.",
                "tags": ["Client-safe"],
            },
        ]

        text = build_shortlist_compare_text(entries, "a1", "b2")

        self.assertIn("Shortlist Compare", text)
        self.assertIn("A: Tue, May 26, 2026, 11:00 AM PDT", text)
        self.assertIn("B: Tue, May 26, 2026, 1:00 PM PDT", text)
        self.assertIn("Metric Edge", text)
        self.assertIn("Volatility: B", text)
        self.assertIn("Tags: Best for launch", text)
        self.assertIn("Tags: Client-safe", text)

    def test_combined_location_names_include_custom_saved_places(self) -> None:
        names = combined_location_names([LocationPreset("user-temple", "Temple Office", 35.0, -120.0, "America/Los_Angeles")])

        self.assertIn("Los Angeles, CA", names)
        self.assertIn("Temple Office", names)


if __name__ == "__main__":
    unittest.main()
