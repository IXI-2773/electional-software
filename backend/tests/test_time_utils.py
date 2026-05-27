from __future__ import annotations

import unittest

from backend.electional.time_utils import is_valid_timezone, normalize_time_text, parse_local_time


class TimeUtilsTest(unittest.TestCase):
    def test_parse_local_time_accepts_24_hour_and_meridiem_inputs(self) -> None:
        self.assertEqual(parse_local_time("21:30").hour, 21)
        self.assertEqual(parse_local_time("9:30 PM").hour, 21)
        self.assertEqual(normalize_time_text("9:30 PM"), "21:30")

    def test_timezone_validation_accepts_iana_names_and_default(self) -> None:
        self.assertTrue(is_valid_timezone("America/Los_Angeles"))
        self.assertTrue(is_valid_timezone(""))
        self.assertFalse(is_valid_timezone("Pacific Time"))


if __name__ == "__main__":
    unittest.main()
