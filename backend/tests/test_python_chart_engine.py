from __future__ import annotations

import unittest

from backend.electional.chart import build_election_report, build_snapshot, build_transit_windows
from backend.electional.ephemeris import get_planet_positions, lunar_phase_from_positions, signed_longitude_delta
from backend.electional.fixed_stars import detect_fixed_star_contacts, fixed_star_positions
from backend.electional.houses import calculate_angles, calculate_house_cusps, house_number
from backend.electional.locations import get_location
from backend.electional.lunar_nodes import calculate_lunar_nodes, mean_node_tropical_longitude, true_node_tropical_longitude
from backend.electional.planetary_hours import day_ruler_for_moment, planetary_hour_context
from backend.electional.professional import calculation_backend_status
from backend.electional.rules import evaluate_electional_rules, nakshatra_for_longitude, solar_condition_for_body, tithi_from_phase
from backend.electional.search import SearchConfig
from backend.electional.systems import ayanamsha_for_system, get_zodiac_system
from backend.electional.time_utils import normalize_time_text, zoned_time_to_utc


class PythonChartEngineTest(unittest.TestCase):
    def test_timezone_conversion_uses_iana_zone(self) -> None:
        moment = zoned_time_to_utc("2026-05-26", "09:00", "America/Los_Angeles")

        self.assertEqual(moment.isoformat(), "2026-05-26T16:00:00+00:00")

    def test_time_parser_accepts_desktop_am_pm_input(self) -> None:
        self.assertEqual(normalize_time_text("09:00 AM"), "09:00")
        self.assertEqual(normalize_time_text("9:30 PM"), "21:30")

    def test_ephemeris_matches_jpl_fixture_tolerance(self) -> None:
        moment = zoned_time_to_utc("2026-05-26", "09:00", "America/Los_Angeles")
        planets = get_planet_positions(moment)
        positions = {planet["name"]: planet["longitude"] for planet in planets}

        self.assertAlmostEqual(positions["Sun"], 65.4225, delta=0.01)
        self.assertAlmostEqual(positions["Moon"], 193.2205, delta=0.01)
        self.assertAlmostEqual(positions["Mercury"], 79.3437, delta=0.01)
        self.assertIn("motion", planets[0])
        self.assertIn(planets[0]["motion"]["direction"], {"direct", "retrograde", "stationary"})

    def test_signed_longitude_delta_handles_zodiac_wrap(self) -> None:
        self.assertEqual(signed_longitude_delta(359, 1), 2)
        self.assertEqual(signed_longitude_delta(1, 359), -2)

    def test_lunar_phase_from_positions_labels_fixture_phase(self) -> None:
        moment = zoned_time_to_utc("2026-05-26", "09:00", "America/Los_Angeles")
        phase = lunar_phase_from_positions(get_planet_positions(moment))

        self.assertEqual(phase["name"], "Waxing Gibbous")
        self.assertTrue(phase["isWaxing"])
        self.assertGreater(phase["illumination"], 0.7)

    def test_sidereal_lahiri_offsets_zodiac_positions(self) -> None:
        moment = zoned_time_to_utc("2026-05-26", "09:00", "America/Los_Angeles")
        tropical = {planet["name"]: planet for planet in get_planet_positions(moment)}
        sidereal = {planet["name"]: planet for planet in get_planet_positions(moment, "sidereal-lahiri")}

        self.assertEqual(get_zodiac_system("Sidereal Lahiri").id, "sidereal-lahiri")
        self.assertAlmostEqual(ayanamsha_for_system(moment, "sidereal-lahiri"), 24.22, delta=0.05)
        self.assertAlmostEqual(tropical["Sun"]["longitude"] - sidereal["Sun"]["longitude"], 24.22, delta=0.05)
        self.assertEqual(sidereal["Sun"]["zodiac"]["sign"], "Taurus")

    def test_astrolog_style_sidereal_offsets_are_available(self) -> None:
        moment = zoned_time_to_utc("2026-05-26", "09:00", "America/Los_Angeles")

        lahiri = ayanamsha_for_system(moment, "sidereal-lahiri")
        fagan = ayanamsha_for_system(moment, "sidereal-fagan-bradley")
        krishnamurti = ayanamsha_for_system(moment, "sidereal-krishnamurti")

        self.assertEqual(get_zodiac_system("Sidereal Fagan-Bradley").id, "sidereal-fagan-bradley")
        self.assertAlmostEqual(lahiri - fagan, 0.883208, delta=0.0001)
        self.assertAlmostEqual(krishnamurti - fagan, 0.98006, delta=0.0001)

    def test_fixed_stars_are_projected_into_selected_zodiac(self) -> None:
        moment = zoned_time_to_utc("2026-05-26", "09:00", "America/Los_Angeles")
        stars = fixed_star_positions(moment, "sidereal-lahiri")
        by_name = {star["name"]: star for star in stars}

        self.assertIn("Spica", by_name)
        self.assertIn("electionalNote", by_name["Spica"])
        self.assertIn("zodiac", by_name["Spica"])

    def test_fixed_star_contacts_detect_tight_conjunctions(self) -> None:
        contacts = detect_fixed_star_contacts(
            [{"name": "Venus", "longitude": 10.2}],
            [{"id": "spica", "name": "Spica", "longitude": 10.0, "electionalNote": "Protection"}],
        )

        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0]["label"], "Venus conjunct Spica")
        self.assertGreater(contacts[0]["score"], 0)

    def test_sidereal_lunar_rule_context(self) -> None:
        self.assertEqual(nakshatra_for_longitude(0)["name"], "Ashwini")
        self.assertEqual(nakshatra_for_longitude(50)["name"], "Rohini")
        self.assertEqual(tithi_from_phase(0)["name"], "Pratipada")
        self.assertEqual(tithi_from_phase(180)["name"], "Pratipada")

    def test_solar_condition_rules_identify_combustion(self) -> None:
        rule = solar_condition_for_body({"name": "Mercury", "longitude": 11.0}, {"name": "Sun", "longitude": 10.0})

        self.assertEqual(rule["title"], "Mercury combust")
        self.assertLess(rule["scoreImpact"], 0)

    def test_electional_rules_include_lunar_context_and_score_impact(self) -> None:
        rules = evaluate_electional_rules(
            [
                {"name": "Sun", "longitude": 10.0},
                {"name": "Moon", "longitude": 50.0},
                {"name": "Mercury", "longitude": 11.0},
            ],
            {"phaseAngle": 90, "name": "First Quarter"},
            "sidereal-lahiri",
        )

        self.assertIn("lunarContext", rules)
        self.assertTrue(rules["rules"])
        self.assertLess(rules["scoreImpact"], 0)

    def test_planetary_hour_context_uses_sunrise_sunset(self) -> None:
        location = get_location("los-angeles")
        moment = zoned_time_to_utc("2026-05-26", "09:00", location.timezone)
        context = planetary_hour_context(moment, location)

        self.assertTrue(context["available"])
        self.assertIn(context["period"], {"day", "night"})
        self.assertIn(context["hourRuler"], {"Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"})
        self.assertEqual(day_ruler_for_moment(moment, location), "Mars")

    def test_lunar_nodes_are_available_as_chart_points(self) -> None:
        location = get_location("los-angeles")
        moment = zoned_time_to_utc("2026-05-26", "09:00", location.timezone)
        angles = calculate_angles(moment, location.latitude, location.longitude, "sidereal-lahiri")
        cusps = calculate_house_cusps(moment, location.latitude, location.longitude, "sidereal-lahiri", "whole-sign", angles)

        nodes = calculate_lunar_nodes(moment, "sidereal-lahiri", angles, cusps, "whole-sign")

        self.assertEqual(len(nodes), 4)
        self.assertAlmostEqual((nodes[1]["longitude"] - nodes[0]["longitude"]) % 360, 180, delta=0.001)
        self.assertTrue(all(1 <= node["house"] <= 12 for node in nodes))
        self.assertNotEqual(round(mean_node_tropical_longitude(moment), 4), round(true_node_tropical_longitude(moment), 4))

    def test_angles_match_swiss_fixture_tolerance(self) -> None:
        location = get_location("los-angeles")
        moment = zoned_time_to_utc("2026-05-26", "09:00", location.timezone)
        angles = {angle["id"]: angle["longitude"] for angle in calculate_angles(moment, location.latitude, location.longitude)}

        self.assertAlmostEqual(angles["asc"], 110.13511832023705, delta=0.05)
        self.assertAlmostEqual(angles["mc"], 6.5293592412573105, delta=0.05)

    def test_equal_house_uses_exact_ascendant_start(self) -> None:
        self.assertEqual(house_number(20, 20, "equal-house"), 1)
        self.assertEqual(house_number(49.9, 20, "equal-house"), 1)
        self.assertEqual(house_number(50, 20, "equal-house"), 2)

    def test_topocentric_house_cusps_include_angles(self) -> None:
        location = get_location("los-angeles")
        moment = zoned_time_to_utc("2026-05-26", "09:00", location.timezone)
        angles = {angle["id"]: angle["longitude"] for angle in calculate_angles(moment, location.latitude, location.longitude, "sidereal-lahiri")}
        cusps = {cusp["house"]: cusp["longitude"] for cusp in calculate_house_cusps(moment, location.latitude, location.longitude, "sidereal-lahiri", "topocentric")}

        self.assertEqual(len(cusps), 12)
        self.assertAlmostEqual(cusps[1], angles["asc"], delta=0.001)
        self.assertAlmostEqual(cusps[10], angles["mc"], delta=0.001)
        self.assertAlmostEqual((cusps[7] - cusps[1]) % 360, 180, delta=0.001)

    def test_koch_house_cusps_include_angles(self) -> None:
        location = get_location("los-angeles")
        moment = zoned_time_to_utc("2026-05-26", "09:00", location.timezone)
        angles = {angle["id"]: angle["longitude"] for angle in calculate_angles(moment, location.latitude, location.longitude, "sidereal-lahiri")}
        cusps = {cusp["house"]: cusp["longitude"] for cusp in calculate_house_cusps(moment, location.latitude, location.longitude, "sidereal-lahiri", "koch")}

        self.assertEqual(len(cusps), 12)
        self.assertAlmostEqual(cusps[1], angles["asc"], delta=0.001)
        self.assertAlmostEqual(cusps[10], angles["mc"], delta=0.001)
        self.assertAlmostEqual((cusps[7] - cusps[1]) % 360, 180, delta=0.001)
        self.assertAlmostEqual((cusps[4] - cusps[10]) % 360, 180, delta=0.001)

    def test_professional_backend_status_detects_astrolog_ephemeris(self) -> None:
        status = calculation_backend_status()

        self.assertIn("activeEngine", status)
        self.assertIn("ephemerisPath", status)
        self.assertGreaterEqual(int(status["ephemerisFileCount"]), 0)

    def test_placidus_uses_professional_or_safe_fallback_cusps(self) -> None:
        location = get_location("los-angeles")
        moment = zoned_time_to_utc("2026-05-26", "09:00", location.timezone)
        cusps = calculate_house_cusps(moment, location.latitude, location.longitude, "sidereal-lahiri", "placidus")

        self.assertEqual(len(cusps), 12)
        self.assertTrue(all(1 <= cusp["house"] <= 12 for cusp in cusps))
        self.assertTrue(any(cusp.get("source") in {"Swiss Ephemeris", "Porphyry fallback"} for cusp in cusps))

    def test_snapshot_and_windows_are_python_calculated(self) -> None:
        location = get_location("paris")
        snapshot = build_snapshot("2026-05-26", "09:00", location, "traditional-lilly")
        windows = build_transit_windows("2026-05-26", "09:00", location, "traditional-lilly")

        self.assertEqual(snapshot["engine"], "Astronomy Engine Python")
        self.assertIn("calculationBackend", snapshot)
        self.assertIn("calculationNotes", snapshot)
        self.assertIn("ruleEvaluations", snapshot)
        self.assertIn("lunarContext", snapshot["ruleEvaluations"])
        self.assertIn("planetaryHour", snapshot)
        self.assertIn("constellationContext", snapshot)
        self.assertIn("significatorContext", snapshot)
        self.assertIn("moonCondition", snapshot)
        self.assertIn("houseRulerContext", snapshot)
        self.assertIn("receptionContext", snapshot)
        self.assertIn("planetConditionContext", snapshot)
        self.assertIn("advancedAspectContext", snapshot)
        self.assertIn("timingProfile", snapshot)
        self.assertIn("summary", snapshot["timingProfile"])
        self.assertTrue(snapshot["planetaryHour"]["available"])
        self.assertEqual(len(snapshot["positions"]), 10)
        self.assertEqual(len(snapshot["lunarNodes"]), 4)
        self.assertEqual(len(snapshot["angles"]), 4)
        self.assertEqual(len(snapshot["lots"]), 7)
        self.assertGreaterEqual(len(snapshot["fixedStars"]), 7)
        self.assertIn("fixedStarContacts", snapshot)
        self.assertIn("lunarPhase", snapshot)
        self.assertTrue(all("motion" in planet for planet in snapshot["positions"]))
        self.assertTrue(all("constellation" in planet for planet in snapshot["positions"]))
        self.assertEqual(len(windows), 6)
        self.assertGreaterEqual(windows[0]["score"], windows[-1]["score"])

    def test_objective_changes_significator_selection(self) -> None:
        location = get_location("paris")
        launch = build_snapshot("2026-05-26", "09:00", location, "traditional-lilly", objective="Launch or publish")
        relationship = build_snapshot("2026-05-26", "09:00", location, "traditional-lilly", objective="Relationship timing")

        launch_roles = {
            role
            for point in launch["significatorContext"]["points"]
            for role in point["roles"]
        }
        relationship_roles = {
            role
            for point in relationship["significatorContext"]["points"]
            for role in point["roles"]
        }

        self.assertIn("public launch natural significator", launch_roles)
        self.assertIn("relationship natural significator", relationship_roles)
        self.assertNotEqual(launch["significatorContext"]["points"], relationship["significatorContext"]["points"])

    def test_snapshot_can_use_sidereal_and_equal_house(self) -> None:
        location = get_location("los-angeles")
        snapshot = build_snapshot("2026-05-26", "09:00", location, "traditional-lilly", None, "sidereal-lahiri", "equal-house")
        sun = next(planet for planet in snapshot["positions"] if planet["name"] == "Sun")

        self.assertEqual(snapshot["zodiacSystem"].name, "Sidereal Lahiri")
        self.assertEqual(snapshot["houseSystem"].name, "Equal House")
        self.assertEqual(sun["zodiac"]["sign"], "Taurus")
        self.assertGreater(snapshot["ayanamsha"], 24)

    def test_snapshot_can_use_topocentric_houses(self) -> None:
        location = get_location("los-angeles")
        snapshot = build_snapshot("2026-05-26", "09:00", location, "traditional-lilly", None, "sidereal-lahiri", "topocentric")

        self.assertEqual(snapshot["houseSystem"].name, "Topocentric")
        self.assertEqual(len(snapshot["houseCusps"]), 12)
        self.assertTrue(all(1 <= planet["house"] <= 12 for planet in snapshot["positions"]))

    def test_snapshot_can_use_koch_houses(self) -> None:
        location = get_location("los-angeles")
        snapshot = build_snapshot("2026-05-26", "09:00", location, "traditional-lilly", None, "sidereal-lahiri", "koch")

        self.assertEqual(snapshot["houseSystem"].name, "Koch")
        self.assertEqual(len(snapshot["houseCusps"]), 12)
        self.assertEqual(len(snapshot["lots"]), 7)
        self.assertTrue(all(1 <= planet["house"] <= 12 for planet in snapshot["positions"]))
        self.assertTrue(all(1 <= lot["house"] <= 12 for lot in snapshot["lots"]))

    def test_election_report_reuses_base_snapshot_and_ranks_full_windows(self) -> None:
        location = get_location("los-angeles")
        report = build_election_report("2026-05-26", "09:00", location, "traditional-lilly")
        snapshot = report["snapshot"]
        windows = report["windows"]

        self.assertEqual(len(windows), 6)
        self.assertTrue(any(window["date"] == snapshot["date"] for window in windows))
        self.assertIn("engine", windows[0])
        self.assertIn("formattedTime", windows[0])
        self.assertIn("preset", windows[0])
        self.assertGreaterEqual(windows[0]["score"], windows[-1]["score"])

    def test_configurable_search_controls_range_step_and_limit(self) -> None:
        location = get_location("los-angeles")
        config = SearchConfig(end_offset_minutes=240, step_minutes=60, max_results=3, minimum_score=50)

        windows = build_transit_windows("2026-05-26", "09:00", location, "traditional-lilly", search_config=config)

        self.assertLessEqual(len(windows), 3)
        self.assertTrue(all(window["score"] >= 50 for window in windows))
        self.assertGreaterEqual(windows[0]["score"], windows[-1]["score"])


if __name__ == "__main__":
    unittest.main()
