from __future__ import annotations

import json
import unittest

from backend.electional.server import build_chart_response, build_report_response, build_score_response, build_search_response, decode_json_object, json_default, search_config_from_payload
from backend.electional.professional import engine_name


class ServerApiTest(unittest.TestCase):
    def test_score_response_accepts_explicit_custom_aspect_definitions(self) -> None:
        response = build_score_response(
            {
                "presetId": "traditional-lilly",
                "positions": [
                    {
                        "name": "Sun",
                        "longitude": 10,
                        "zodiac": {"sign": "Aries", "degree": 10, "minute": 0},
                        "isAngular": False,
                        "closestAngle": {"shortName": "ASC", "distance": 12},
                    },
                    {
                        "name": "Moon",
                        "longitude": 55,
                        "zodiac": {"sign": "Taurus", "degree": 25, "minute": 0},
                        "isAngular": False,
                        "closestAngle": {"shortName": "ASC", "distance": 20},
                    },
                ],
                "aspects": ["semisquare"],
                "aspectDefinitions": [
                    {
                        "id": "semisquare",
                        "name": "Semisquare",
                        "abbreviation": "Sem",
                        "glyph": "SS",
                        "angle": 45,
                        "orb": 1,
                        "tone": "stress",
                        "enabled": True,
                    }
                ],
            }
        )

        self.assertEqual(response["detectedAspects"][0]["aspectId"], "semisquare")
        self.assertEqual(response["detectedAspects"][0]["aspectAbbreviation"], "Sem")

    def test_chart_response_is_json_serializable(self) -> None:
        response = build_chart_response(
            {
                "date": "2026-05-26",
                "time": "09:00",
                "locationId": "los-angeles",
                "presetId": "traditional-lilly",
            }
        )

        encoded = json.dumps(response, default=json_default)

        self.assertIn(engine_name(), encoded)
        self.assertIn("scoreBreakdown", encoded)

    def test_search_response_honors_search_config(self) -> None:
        response = build_search_response(
            {
                "date": "2026-05-26",
                "time": "09:00",
                "locationId": "los-angeles",
                "presetId": "traditional-lilly",
                "endOffsetMinutes": 120,
                "stepMinutes": 60,
                "maxResults": 2,
            }
        )

        self.assertLessEqual(len(response["windows"]), 2)
        self.assertEqual(response["resultCount"], len(response["windows"]))
        self.assertEqual(response["search"]["step_minutes"], 60)

    def test_report_response_includes_report_text(self) -> None:
        response = build_report_response(
            {
                "date": "2026-05-26",
                "time": "09:00",
                "locationId": "los-angeles",
                "presetId": "traditional-lilly",
                "maxResults": 2,
            }
        )

        self.assertIn("Electional Software Report", response["reportText"])
        self.assertIn("Score reasons", response["reportText"])
        self.assertIn("Planetary hour", response["reportText"])
        self.assertIn("Calculation backend", response["reportText"])
        self.assertIn("Rules:", response["reportText"])
        self.assertEqual(response["resultCount"], len(response["windows"]))

    def test_search_config_validation_uses_clear_errors(self) -> None:
        with self.assertRaisesRegex(ValueError, "stepMinutes must be a whole number"):
            search_config_from_payload({"stepMinutes": "soon"})

        with self.assertRaisesRegex(ValueError, "minimumScore must be between 10 and 99"):
            search_config_from_payload({"minimumScore": 100})

        with self.assertRaisesRegex(ValueError, "Search step must be greater than zero"):
            search_config_from_payload({"stepMinutes": 0})

    def test_decode_json_object_rejects_array_bodies(self) -> None:
        with self.assertRaisesRegex(ValueError, "JSON body must be an object"):
            decode_json_object(b"[]")


if __name__ == "__main__":
    unittest.main()
