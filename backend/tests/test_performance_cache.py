from __future__ import annotations

import unittest

from backend.electional.performance import DeterministicCache, build_cache_key


class PerformanceCacheTest(unittest.TestCase):
    def test_cache_hit(self) -> None:
        cache = DeterministicCache()
        payload = {"datetime_utc": "2026-07-14T10:00:00Z", "location": "A", "zodiac_mode": "tropical", "objective_pack_version": "exam_v1"}
        cache.set("snapshot", payload, {"score": 90})
        self.assertEqual(cache.get("snapshot", payload), {"score": 90})
        self.assertEqual(cache.stats_payload()["cache_hits"], 1)

    def test_cache_miss_on_location_zodiac_rule_and_objective_change(self) -> None:
        base = {"datetime_utc": "2026-07-14T10:00:00Z", "location": "A", "zodiac_mode": "tropical", "rule_pack_version": "r1", "objective_pack_version": "exam_v1"}
        self.assertNotEqual(build_cache_key("x", base), build_cache_key("x", {**base, "location": "B"}))
        self.assertNotEqual(build_cache_key("x", base), build_cache_key("x", {**base, "zodiac_mode": "sidereal"}))
        self.assertNotEqual(build_cache_key("x", base), build_cache_key("x", {**base, "rule_pack_version": "r2"}))
        self.assertNotEqual(build_cache_key("x", base), build_cache_key("x", {**base, "objective_pack_version": "legal_v1"}))

    def test_cache_clear_and_stats(self) -> None:
        cache = DeterministicCache()
        cache.set("x", {"a": 1}, 2)
        cache.get("x", {"a": 2})
        self.assertEqual(cache.stats_payload()["cache_misses"], 1)
        cache.clear()
        self.assertEqual(cache.stats_payload()["cache_misses"], 0)


if __name__ == "__main__":
    unittest.main()
