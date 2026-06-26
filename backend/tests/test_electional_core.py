from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.electional.aspects import (
    Aspect,
    AspectProfile,
    aspect_profile_by_id,
    aspect_timing,
    default_aspect_profile,
    detect_aspects,
    load_aspect_profiles,
    save_aspect_profiles,
    validate_aspect_profile,
)
from backend.electional.lots import calculate_lots, lot_longitude
from backend.electional.presets import (
    apply_dignities,
    filter_positions_for_preset,
    get_bound_lord,
    get_essential_dignity,
    get_preset,
    summarize_orb,
)
from backend.electional.scoring import angle_testimony, planet_strength_breakdown, score_breakdown, score_breakdown_model, score_window
from backend.electional.search import SearchConfig, format_search_summary, has_planet_placement, has_target_aspect, rejection_reasons
from backend.electional.timing import timing_profile


def position(
    name: str,
    longitude: float,
    sign: str,
    is_angular: bool = False,
    distance: float = 8,
    is_retrograde: bool = False,
    daily_change: float | None = None,
) -> dict:
    payload = {
        "name": name,
        "longitude": longitude,
        "zodiac": {"sign": sign, "degree": int(longitude % 30), "minute": 0},
        "isAngular": is_angular,
        "isRetrograde": is_retrograde,
        "closestAngle": {"shortName": "ASC", "distance": distance},
    }
    if daily_change is not None:
        payload["motion"] = {"dailyLongitudeChange": daily_change}
    return payload


class ElectionalCoreTest(unittest.TestCase):
    def test_search_targets_match_aspects_and_planet_placements(self) -> None:
        window = {
            "detectedAspects": [
                {
                    "aspectId": "trine",
                    "aspectName": "Trine",
                    "aspectAbbreviation": "Tri",
                    "bodies": ["Sun", "Jupiter"],
                    "label": "Sun trine Jupiter",
                }
            ],
            "positions": [
                {"name": "Venus", "house": 10, "zodiac": {"sign": "Gemini"}},
                {"name": "Mars", "house": 7, "zodiac": {"sign": "Aries"}},
            ],
            "score": 80,
            "scoreBreakdown": {"objectiveMatches": 2},
        }

        self.assertTrue(has_target_aspect(window, "trine", "Jupiter"))
        self.assertTrue(has_planet_placement(window, "Venus", "Gemini", 10))
        self.assertFalse(has_planet_placement(window, "Venus", "Taurus", 10))

        config = SearchConfig(target_aspect_text="square", target_planet_text="Venus", target_sign_text="Taurus", target_house=10)
        reasons = rejection_reasons(window, config)

        self.assertIn("missing target aspect: square", reasons)
        self.assertTrue(any("missing target placement: Venus" in reason for reason in reasons))
        self.assertIn("aspect: square", format_search_summary(config))
        self.assertIn("Venus in Taurus / H10", format_search_summary(config))

    def test_planet_strength_breakdown_surfaces_condition_scores(self) -> None:
        preset = get_preset("traditional-lilly")
        strong = position("Venus", 80, "Gemini", is_angular=True, distance=1, daily_change=1.2)
        strong["dignity"] = {"score": 2}
        weak = position("Mars", 20, "Aries", is_retrograde=True, daily_change=0.1)
        weak["dignity"] = {"score": -1}

        rows = planet_strength_breakdown([weak, strong], preset)
        by_name = {row["planet"]: row for row in rows}

        self.assertGreater(by_name["Venus"]["score"], by_name["Mars"]["score"])
        self.assertEqual(by_name["Venus"]["band"], "Strong")
        self.assertIn("motion", by_name["Venus"]["note"])
        self.assertIn("retrograde pressure", by_name["Mars"]["note"])

    def test_default_aspect_profile_contains_major_five(self) -> None:
        profile = default_aspect_profile()

        self.assertEqual(profile.id, "major-five")
        self.assertEqual(
            [aspect.id for aspect in profile.aspects],
            ["conjunction", "trine", "square", "opposition", "sextile"],
        )
        self.assertTrue(all(aspect.glyph for aspect in profile.aspects))

    def test_custom_aspect_profile_saves_and_loads(self) -> None:
        custom = Aspect(
            id="quincunx",
            name="Quincunx",
            angle=150,
            default_orb=2,
            tone="mixed",
            meaning="Adjustment and mismatch contact.",
            abbreviation="Qnx",
            glyph="Qx",
            color="#7755aa",
            enabled=True,
            built_in=False,
        )
        profile = AspectProfile("custom-test", "Custom Test", "test profile", (*default_aspect_profile().aspects, custom))
        with TemporaryDirectory() as directory:
            path = Path(directory) / "profiles.json"

            save_aspect_profiles([default_aspect_profile(), profile], path)
            loaded = load_aspect_profiles(path)

        loaded_profile = aspect_profile_by_id("custom-test", loaded)
        self.assertEqual(loaded_profile.name, "Custom Test")
        self.assertIn("quincunx", [aspect.id for aspect in loaded_profile.aspects])

    def test_aspect_profile_validation_rejects_bad_values(self) -> None:
        profile = AspectProfile(
            "bad",
            "",
            "",
            (
                Aspect("semi", "", -1, 2, "support", "bad"),
                Aspect("semi", "Duplicate", 45, 31, "wild", "bad"),
            ),
        )

        errors = validate_aspect_profile(profile)

        self.assertTrue(any("Profile name" in error for error in errors))
        self.assertTrue(any("Duplicate aspect id" in error for error in errors))
        self.assertTrue(any("exact angle" in error for error in errors))
        self.assertTrue(any("orb" in error for error in errors))
        self.assertTrue(any("tone" in error for error in errors))

    def test_detect_aspects_uses_custom_aspect_definitions(self) -> None:
        semisquare = Aspect(
            id="semisquare",
            name="Semisquare",
            angle=45,
            default_orb=1,
            tone="stress",
            meaning="Minor friction.",
            abbreviation="Sem",
            glyph="SS",
            color="#aa4455",
            enabled=True,
            built_in=False,
        )
        detected = detect_aspects(
            [
                position("Sun", 10, "Aries", daily_change=0),
                position("Moon", 55.5, "Taurus", daily_change=0),
            ],
            ["semisquare"],
            aspect_definitions=(*default_aspect_profile().aspects, semisquare),
        )

        self.assertEqual(len(detected), 1)
        self.assertEqual(detected[0]["aspectId"], "semisquare")
        self.assertEqual(detected[0]["aspectAbbreviation"], "Sem")
        self.assertEqual(detected[0]["aspectGlyph"], "SS")
        self.assertEqual(detected[0]["tone"], "stress")

    def test_transit_one_degree_detects_only_tight_contacts(self) -> None:
        preset = get_preset("transit-1-degree")
        tight = [
            position("Sun", 10, "Aries"),
            position("Moon", 10.5, "Aries"),
            position("Mars", 12, "Aries"),
        ]

        detected = detect_aspects(tight, preset.aspect_ids, preset.aspect_orbs)

        labels = [aspect["label"] for aspect in detected]
        self.assertIn("Sun conjunction Moon", labels)
        self.assertNotIn("Sun conjunction Mars", labels)
        self.assertEqual(summarize_orb(preset), "1 deg")

    def test_aspect_detection_marks_applying_and_separating_contacts(self) -> None:
        preset = get_preset("medieval-electional")
        applying = detect_aspects(
            [
                position("Venus", 0, "Aries", daily_change=0),
                position("Jupiter", 118, "Cancer", daily_change=3),
            ],
            ["trine"],
            preset.aspect_orbs,
        )
        separating = detect_aspects(
            [
                position("Venus", 0, "Aries", daily_change=0),
                position("Jupiter", 118, "Cancer", daily_change=-3),
            ],
            ["trine"],
            preset.aspect_orbs,
        )

        self.assertEqual(applying[0]["phase"], "applying")
        self.assertTrue(applying[0]["isApplying"])
        self.assertEqual(separating[0]["phase"], "separating")
        self.assertFalse(separating[0]["isApplying"])

    def test_applying_aspects_include_perfection_timing(self) -> None:
        preset = get_preset("medieval-electional")
        detected = detect_aspects(
            [
                position("Venus", 0, "Aries", daily_change=0),
                position("Jupiter", 118, "Cancer", daily_change=4),
            ],
            ["trine"],
            preset.aspect_orbs,
            datetime(2026, 5, 26, 16, tzinfo=timezone.utc),
            "America/Los_Angeles",
        )

        self.assertEqual(detected[0]["phase"], "applying")
        self.assertAlmostEqual(float(detected[0]["daysToExact"]), 0.5, delta=0.01)
        self.assertEqual(detected[0]["timeToExactText"], "12h")
        self.assertTrue(detected[0]["crossesExactWithinDay"])
        self.assertEqual(detected[0]["timingQuality"], "soon")
        self.assertIn("PDT", detected[0]["perfectsAtText"])

    def test_separating_aspect_has_no_perfection_timing(self) -> None:
        timing = aspect_timing({"isApplying": False, "orb": 1, "orbChangePerDay": 1})

        self.assertIsNone(timing["daysToExact"])
        self.assertEqual(timing["timingQuality"], "not applying")

    def test_ephemeris_refinement_replaces_linear_aspect_estimate(self) -> None:
        start = datetime(2026, 5, 26, 16, tzinfo=timezone.utc)

        def longitude_at(body_name: str, moment: datetime) -> float:
            elapsed_days = (moment - start).total_seconds() / 86400
            return 0 if body_name == "Venus" else 118 + 5 * elapsed_days

        detected = detect_aspects(
            [
                position("Venus", 0, "Aries", daily_change=0),
                position("Jupiter", 118, "Cancer", daily_change=4),
            ],
            ["trine"],
            moment=start,
            timezone_name="America/Los_Angeles",
            longitude_resolver=longitude_at,
        )

        self.assertAlmostEqual(float(detected[0]["daysToExact"]), 0.4, delta=0.001)
        self.assertEqual(detected[0]["timingMethod"], "ephemeris refined")
        self.assertLess(float(detected[0]["perfectionOrb"]), 0.02)

    def test_timing_profile_summarizes_next_support_and_stress(self) -> None:
        profile = timing_profile(
            [
                {
                    "label": "Venus trine Jupiter",
                    "tone": "support",
                    "isApplying": True,
                    "daysToExact": 0.5,
                    "timeToExactText": "12h",
                },
                {
                    "label": "Mars square Saturn",
                    "tone": "stress",
                    "isApplying": True,
                    "daysToExact": 1.5,
                    "timeToExactText": "1d 12h",
                },
            ]
        )

        self.assertEqual(profile["applyingCount"], 2)
        self.assertEqual(profile["nextSupport"]["label"], "Venus trine Jupiter")
        self.assertEqual(profile["nextStress"]["label"], "Mars square Saturn")
        self.assertIn("Next exact contact", profile["summary"])

    def test_traditional_lilly_filters_outer_planets(self) -> None:
        preset = get_preset("traditional-lilly")
        positions = [
            position("Sun", 120, "Leo"),
            position("Saturn", 300, "Aquarius"),
            position("Uranus", 300, "Aquarius"),
        ]

        filtered = filter_positions_for_preset(positions, preset)

        self.assertEqual([planet["name"] for planet in filtered], ["Sun", "Saturn"])

    def test_essential_dignities(self) -> None:
        self.assertEqual(get_essential_dignity(position("Sun", 120, "Leo"))["label"], "Domicile")
        self.assertEqual(get_essential_dignity(position("Mars", 270, "Capricorn"))["label"], "Exalted")
        self.assertEqual(get_essential_dignity(position("Venus", 150, "Virgo"))["label"], "Fall")

    def test_egyptian_bounds_add_minor_dignity(self) -> None:
        self.assertEqual(get_bound_lord(position("Jupiter", 5, "Aries")), "Jupiter")
        self.assertEqual(get_bound_lord(position("Saturn", 27, "Aries")), "Saturn")

        dignity = get_essential_dignity(position("Mercury", 15, "Aries"))

        self.assertEqual(dignity["label"], "Bound")
        self.assertEqual(dignity["score"], 1)
        self.assertEqual(dignity["boundLord"], "Mercury")

    def test_score_window_returns_integer_in_bounds(self) -> None:
        preset = get_preset("medieval-electional")
        positions = apply_dignities(
            [
                position("Jupiter", 95, "Cancer", is_angular=True, distance=1),
                position("Venus", 350, "Pisces"),
                position("Mars", 270, "Capricorn"),
            ],
            preset,
        )
        detected = [
            {
                "aspectId": "trine",
                "tone": "support",
                "orb": 0.5,
            }
        ]

        score = score_window(detected, positions, preset)

        self.assertIsInstance(score, int)
        self.assertGreaterEqual(score, 10)
        self.assertLessEqual(score, 99)

    def test_score_breakdown_exposes_formula_inputs(self) -> None:
        preset = get_preset("traditional-lilly")
        positions = apply_dignities(
            [
                position("Venus", 45, "Taurus", is_angular=True, distance=2),
                position("Mars", 215, "Scorpio"),
            ],
            preset,
        )
        detected = [{"aspectId": "trine", "tone": "support", "orb": 0.25}]

        breakdown = score_breakdown(detected, positions, preset)

        self.assertEqual(breakdown["base"], 58)
        self.assertEqual(breakdown["support"], 1)
        self.assertEqual(breakdown["objectiveMatches"], 1)
        self.assertEqual(breakdown["closeContacts"], 1)
        self.assertEqual(breakdown["applyingSupport"], 0)
        self.assertIn("accounting", breakdown)
        self.assertIn("evaluation", breakdown)
        self.assertIn("Aspect quality", breakdown["accounting"]["categoryTotals"])
        self.assertGreaterEqual(breakdown["accounting"]["positiveTotal"], 0)
        self.assertIn(breakdown["evaluation"]["band"], {"Prime", "Strong", "Workable", "Fragile", "Avoid"})
        self.assertEqual(breakdown["score"], score_window(detected, positions, preset))
        self.assertTrue(any(reason["code"] == "support-aspects" for reason in breakdown["reasons"]))

    def test_angle_testimony_splits_benefic_and_malefic_pressure(self) -> None:
        preset = get_preset("traditional-lilly")
        positions = apply_dignities(
            [
                {**position("Jupiter", 95, "Cancer", is_angular=True, distance=1), "closestAngle": {"id": "mc", "shortName": "MC", "distance": 1}},
                {**position("Mars", 215, "Scorpio", is_angular=True, distance=2), "closestAngle": {"id": "asc", "shortName": "ASC", "distance": 2}},
                {**position("Moon", 45, "Taurus", is_angular=True, distance=4), "closestAngle": {"id": "dsc", "shortName": "DSC", "distance": 4}},
            ],
            preset,
        )

        testimony = angle_testimony(positions)
        breakdown = score_breakdown([], positions, preset)
        reasons = {reason["code"]: reason for reason in breakdown["reasons"]}

        self.assertGreater(testimony["beneficSupport"], 0)
        self.assertLess(testimony["maleficPressure"], 0)
        self.assertGreater(testimony["luminarySupport"], 0)
        self.assertIn("angle-benefic-support", reasons)
        self.assertIn("angle-malefic-pressure", reasons)
        self.assertIn("angles", breakdown["diagnostics"])
        self.assertIn("Jupiter strengthens MC", breakdown["diagnostics"]["angles"]["summary"])

    def test_angle_testimony_weights_applying_angles_above_separating(self) -> None:
        applying = [
            {
                **position("Jupiter", 95, "Cancer", is_angular=True, distance=1),
                "closestAngle": {
                    "id": "mc",
                    "shortName": "MC",
                    "distance": 1,
                    "anglePhase": "applying",
                    "anglePhaseLabel": "Approaching angle",
                    "timeToAngleExactText": "18m",
                },
            }
        ]
        separating = [
            {
                **position("Jupiter", 95, "Cancer", is_angular=True, distance=1),
                "closestAngle": {
                    "id": "mc",
                    "shortName": "MC",
                    "distance": 1,
                    "anglePhase": "separating",
                    "anglePhaseLabel": "Leaving angle",
                },
            }
        ]

        applying_testimony = angle_testimony(applying)
        separating_testimony = angle_testimony(separating)

        self.assertGreater(applying_testimony["score"], separating_testimony["score"])
        self.assertIn("exact in 18m", applying_testimony["factors"][0]["detail"])

    def test_score_breakdown_counts_applying_aspect_pressure(self) -> None:
        preset = get_preset("traditional-lilly")
        positions = apply_dignities([position("Venus", 45, "Taurus"), position("Moon", 165, "Virgo")], preset)
        detected = [{"aspectId": "trine", "tone": "support", "orb": 0.5, "isApplying": True}]

        breakdown = score_breakdown(detected, positions, preset)

        self.assertEqual(breakdown["applyingSupport"], 1)
        self.assertTrue(any(reason["code"] == "applying-support" for reason in breakdown["reasons"]))

    def test_score_breakdown_rewards_supportive_aspects_perfecting_soon(self) -> None:
        preset = get_preset("traditional-lilly")
        positions = apply_dignities([position("Venus", 45, "Taurus"), position("Moon", 165, "Virgo")], preset)
        later = [{"aspectId": "trine", "tone": "support", "orb": 0.5, "isApplying": True, "timingQuality": "later"}]
        soon = [{"aspectId": "trine", "tone": "support", "orb": 0.5, "isApplying": True, "timingQuality": "soon"}]

        later_breakdown = score_breakdown(later, positions, preset)
        soon_breakdown = score_breakdown(soon, positions, preset)

        self.assertGreater(soon_breakdown["aspectTiming"], later_breakdown["aspectTiming"])
        self.assertTrue(any(reason["code"] == "aspect-timing" for reason in soon_breakdown["reasons"]))

    def test_score_breakdown_penalizes_retrograde_pressure(self) -> None:
        preset = get_preset("traditional-lilly")
        direct_positions = apply_dignities([position("Mercury", 45, "Taurus")], preset)
        retrograde_positions = apply_dignities([position("Mercury", 45, "Taurus", is_retrograde=True)], preset)

        direct = score_breakdown([], direct_positions, preset)
        retrograde = score_breakdown([], retrograde_positions, preset)

        self.assertEqual(retrograde["retrogradePressure"], 4)
        self.assertLess(retrograde["score"], direct["score"])
        self.assertTrue(any(reason["code"] == "retrograde-pressure" for reason in retrograde["reasons"]))

    def test_score_breakdown_model_projects_to_legacy_json_shape(self) -> None:
        preset = get_preset("traditional-lilly")
        positions = apply_dignities([position("Venus", 45, "Taurus")], preset)

        model = score_breakdown_model([], positions, preset)
        payload = model.to_json()

        self.assertEqual(payload["objectiveMatches"], model.objective_matches)
        self.assertEqual(payload["rawScore"], model.raw_score)
        self.assertEqual(payload["accounting"]["finalScore"], model.score)
        self.assertIn("summary", payload["evaluation"])
        self.assertIsInstance(payload["reasons"][0], dict)


    def test_lot_longitude_wraps_around_zodiac(self) -> None:
        self.assertEqual(lot_longitude(350, 20, 40), 330)
        self.assertEqual(lot_longitude(10, 350, 20), 340)

    def test_calculate_lots_returns_seven_hermetic_lots(self) -> None:
        positions = [
            {**position("Sun", 120, "Leo"), "house": 10},
            {**position("Moon", 90, "Cancer"), "house": 9},
            {**position("Mercury", 100, "Cancer"), "house": 9},
            {**position("Venus", 150, "Virgo"), "house": 11},
            {**position("Mars", 180, "Libra"), "house": 12},
            {**position("Jupiter", 210, "Scorpio"), "house": 1},
            {**position("Saturn", 240, "Sagittarius"), "house": 2},
        ]
        angles = [
            {"id": "asc", "name": "Ascendant", "shortName": "ASC", "longitude": 30},
            {"id": "mc", "name": "Midheaven", "shortName": "MC", "longitude": 120},
            {"id": "dsc", "name": "Descendant", "shortName": "DSC", "longitude": 210},
            {"id": "ic", "name": "Imum Coeli", "shortName": "IC", "longitude": 300},
        ]
        house_cusps = [{"house": index + 1, "longitude": index * 30} for index in range(12)]

        lots = calculate_lots(positions, angles, house_cusps, "equal-house")

        self.assertEqual(
            [lot["name"] for lot in lots],
            [
                "Part of Fortune",
                "Part of Spirit",
                "Part of Eros",
                "Part of Necessity",
                "Part of Courage",
                "Part of Victory",
                "Part of Nemesis",
            ],
        )
        self.assertEqual(lots[0]["longitude"], 0)
        self.assertEqual(lots[0]["formula"], "ASC + Moon - Sun")
        self.assertEqual(lots[2]["formula"], "ASC + Venus - Spirit")
        self.assertIn("topic", lots[6])


if __name__ == "__main__":
    unittest.main()
