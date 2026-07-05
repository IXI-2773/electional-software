from __future__ import annotations

from tempfile import TemporaryDirectory
import unittest

from backend.electional.analysis.action_moment import resolve_action_moment_with_pack
from backend.electional.analysis.tactical import build_tactical_analysis_report
from backend.electional.objective_packs import default_objective_pack_ids, load_objective_pack, objective_pack_action_text, save_objective_pack, validate_objective_pack


class ObjectivePacksTest(unittest.TestCase):
    def test_load_validate_default_objective_packs_and_action_text(self) -> None:
        pack = load_objective_pack("exam")
        self.assertEqual(pack["version"], "exam_v1")
        self.assertTrue(validate_objective_pack(pack)[0])
        self.assertIn("exam", default_objective_pack_ids())
        self.assertIn("Begin", objective_pack_action_text("exam"))

    def test_bad_objective_pack_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                save_objective_pack({"objective_type": "bad"}, root=tmp)

    def test_objective_pack_used_by_action_moment(self) -> None:
        action = resolve_action_moment_with_pack("exam")
        self.assertEqual(action.instructions[-1], "Click Begin inside the elected window.")

    def test_objective_pack_used_by_fast_lane(self) -> None:
        report = build_tactical_analysis_report({"objective": "exam", "score": 82})
        self.assertEqual(report.fast_lane.action, "Click Begin inside the elected window.")


if __name__ == "__main__":
    unittest.main()