from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.electional.desktop import (
    fixed_star_contact_count,
    compact_time_label,
    location_summary,
    planet_abbreviation,
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
    load_user_locations,
    save_user_locations,
    upsert_user_location,
)
from backend.electional.references import dignity_table_lines, lot_reference_lines, system_reference_lines
from backend.electional.reporting import (
    condition_lines,
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
    rule_lines,
)
from backend.electional.search import build_search_config_from_text, format_search_summary
from backend.electional.screening import solar_elongation_summary
from backend.electional.session import clean_session_state, load_session_state, save_session_state
from backend.electional.validation import validate_election_inputs, validate_search_inputs


class DesktopUiHelpersTest(unittest.TestCase):
    def test_planet_abbreviation_uses_compact_labels(self) -> None:
        self.assertEqual(planet_abbreviation("Mercury"), "Me")
        self.assertEqual(planet_abbreviation("Pluto"), "Pl")
        self.assertEqual(star_abbreviation("Galactic Center"), "GC")

    def test_wheel_degrees_places_ascendant_on_left_side(self) -> None:
        self.assertEqual(wheel_degrees(110.0, 110.0), 180)
        self.assertEqual(wheel_degrees(290.0, 110.0), 0)

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
        config = build_search_config_from_text("12", "30", "60", "8")

        self.assertEqual(config.end_offset_minutes, 720)
        self.assertEqual(config.step_minutes, 30)
        self.assertEqual(config.minimum_score, 60)
        self.assertEqual(config.max_results, 8)
        self.assertEqual(format_search_summary(config), "Scan 12h from start, every 30m; score >= 60, top 8.")

    def test_search_validation_rejects_impossible_values(self) -> None:
        errors = validate_search_inputs("1", "90", "100", "0")

        self.assertIn("Step minutes must fit inside the scan range.", errors)
        self.assertIn("Minimum score must be 99 or lower.", errors)
        self.assertIn("Max results must be at least 1.", errors)

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
        self.assertEqual(window_score_color(90), "#d9f4e7")
        self.assertEqual(window_score_color(82), "#e8f6f1")
        self.assertEqual(window_score_color(65), "#fff4d6")
        self.assertEqual(window_score_color(44), "#f8dde3")
        self.assertEqual(score_band_label(90), "Prime")
        self.assertEqual(score_band_label(82), "Strong")
        self.assertEqual(score_band_label(65), "Workable")
        self.assertEqual(score_band_label(44), "Caution")

    def test_summary_chip_lines_surface_chart_context(self) -> None:
        snapshot = {
            "lunarPhase": {"name": "Waxing Gibbous"},
            "detectedAspects": [{"tone": "support"}, {"tone": "stress"}],
            "positions": [{"isAngular": True}, {"isAngular": False}],
            "fixedStarContacts": [{"label": "Venus conjunct Spica"}],
            "planetaryHour": {"available": True, "hourRuler": "Jupiter"},
            "ruleEvaluations": {"rules": [{"title": "Mercury combust"}]},
        }

        self.assertEqual(fixed_star_contact_count(snapshot), 1)
        self.assertIn("Moon: Waxing Gibbous", summary_chip_lines(snapshot))
        self.assertIn("Hour: Jupiter", summary_chip_lines(snapshot))
        self.assertIn("Aspects: +1 / !1", summary_chip_lines(snapshot))
        self.assertIn("Angular: 1", summary_chip_lines(snapshot))
        self.assertIn("Fixed stars: 1", summary_chip_lines(snapshot))
        self.assertIn("Rules: 1", summary_chip_lines(snapshot))

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
                    "rawScore": 72.4,
                    "score": 72,
                },
            }
        )

        self.assertIn("support 1", summary)
        self.assertIn("retrograde pressure 3.0", summary)
        self.assertIn("raw 72.4 -> final 72", summary)

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
                "max_results": "12",
                "display_options": {"show_aspects": False, "compact_wheel": True},
            }

            save_session_state(state, path)
            loaded = clean_session_state(load_session_state(path))

        self.assertEqual(loaded["date"], "2026-05-26")
        self.assertEqual(loaded["time"], "21:30")
        self.assertEqual(loaded["timezone"], "Europe/Paris")
        self.assertEqual(loaded["scan_hours"], "24")
        self.assertEqual(loaded["step_minutes"], "30")
        self.assertEqual(loaded["minimum_score"], "70")
        self.assertEqual(loaded["max_results"], "12")
        self.assertFalse(loaded["display_options"]["show_aspects"])
        self.assertTrue(loaded["display_options"]["compact_wheel"])
        self.assertFalse(loaded["display_options"]["show_fixed_stars"])

    def test_user_locations_round_trip(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "locations.json"
            location = LocationPreset("user-home", "Home Base", 33.12, -117.98, "America/Los_Angeles")

            save_user_locations([location], path)
            loaded = load_user_locations(path)

        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].name, "Home Base")
        self.assertEqual(loaded[0].timezone, "America/Los_Angeles")

    def test_user_location_upsert_replaces_same_name(self) -> None:
        original = LocationPreset("user-home", "Home Base", 33.0, -118.0, "America/Los_Angeles")
        updated = LocationPreset("user-home", "Home Base", 34.0, -119.0, "America/Los_Angeles")

        locations = upsert_user_location([original], updated)

        self.assertEqual(len(locations), 1)
        self.assertEqual(locations[0].latitude, 34.0)

    def test_combined_location_names_include_custom_saved_places(self) -> None:
        names = combined_location_names([LocationPreset("user-temple", "Temple Office", 35.0, -120.0, "America/Los_Angeles")])

        self.assertIn("Los Angeles, CA", names)
        self.assertIn("Temple Office", names)


if __name__ == "__main__":
    unittest.main()
