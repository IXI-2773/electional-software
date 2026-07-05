from __future__ import annotations

from tempfile import TemporaryDirectory
import unittest

from backend.electional.reliability.audit_snapshot import build_audit_snapshot
from backend.electional.search_profiles import default_search_profiles, load_search_profile, save_search_profile, validate_search_profile


class SearchProfilesTest(unittest.TestCase):
    def test_save_load_validate_profile_and_defaults(self) -> None:
        with TemporaryDirectory() as tmp:
            profile = default_search_profiles()["exam_strict"]
            self.assertTrue(validate_search_profile(profile)[0])
            save_search_profile(profile, root=tmp)
            loaded = load_search_profile("exam_strict", root=tmp)
            self.assertEqual(loaded["profile_id"], "exam_strict")
            self.assertIn("emergency_least_bad", default_search_profiles())

    def test_reject_bad_profile(self) -> None:
        with self.assertRaises(ValueError):
            save_search_profile({"profile_id": "bad", "strictness": "wild"})


    def test_profile_version_in_audit(self) -> None:
        audit = build_audit_snapshot({"search_profile_id": "exam_strict", "search_profile_version": "profile_v1", "objective_pack_version": "exam_v1"})["audit_snapshot"]
        self.assertEqual(audit["phase4_profile"]["search_profile_id"], "exam_strict")
        self.assertEqual(audit["phase4_profile"]["objective_pack_version"], "exam_v1")
if __name__ == "__main__":
    unittest.main()
