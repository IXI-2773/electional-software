from __future__ import annotations

from tempfile import TemporaryDirectory
import unittest

from backend.electional import api
from backend.electional.search_profiles import default_search_profiles


class ApiPhase4Test(unittest.TestCase):
    def test_api_load_profile_objective_pack_watchlist_and_backup_smoke(self) -> None:
        self.assertEqual(api.load_search_profile("exam_strict")["profile_id"], "exam_strict")
        self.assertEqual(api.load_objective_pack("exam")["version"], "exam_v1")
        result = api.run_watchlist_scan({"watchlist_id": "w", "profile_id": "exam_strict", "range_days": 30}, lambda _p: [])
        self.assertEqual(result["watchlist_id"], "w")
        with TemporaryDirectory() as tmp:
            profile = default_search_profiles()["exam_strict"]
            api.save_search_profile(profile, root=tmp)
            backup = api.backup_reliability_data(output_dir=tmp, root=tmp)
            self.assertTrue(backup["path"])


if __name__ == "__main__":
    unittest.main()
