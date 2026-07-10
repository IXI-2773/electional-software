from __future__ import annotations

import copy
from tempfile import TemporaryDirectory
import unittest

from backend.electional.analysis.action_moment import resolve_action_moment_with_pack
from backend.electional.analysis.tactical import build_tactical_analysis_report
from backend.electional.objective_packs import (
    classify_objective_pack_capability,
    default_objective_pack_ids,
    get_objective_pack_evaluation_fingerprint,
    get_objective_pack_required_input_fields,
    load_objective_pack,
    objective_pack_action_text,
    save_objective_pack,
    validate_objective_pack,
)


class ObjectivePacksTest(unittest.TestCase):
    def test_legacy_metadata_only_pack_remains_valid_and_unchanged(self) -> None:
        pack = load_objective_pack("exam")
        before = copy.deepcopy(pack)
        self.assertEqual(pack["version"], "exam_v1")
        self.assertTrue(validate_objective_pack(pack)[0])
        self.assertEqual(classify_objective_pack_capability(pack)["capability"], "metadata_only")
        self.assertIn("exam", default_objective_pack_ids())
        self.assertIn("Begin", objective_pack_action_text("exam"))
        self.assertEqual(pack, before)

    def test_bad_objective_pack_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                save_objective_pack({"objective_type": "bad"}, root=tmp)

    def test_valid_evaluable_pack_is_classified_and_preserved(self) -> None:
        pack = {
            "objective_type": "example",
            "version": 1,
            "matter_houses": [1, 10],
            "natural_significators": ["Sun"],
            "action_moment": "Example action",
            "objectives": [
                {
                    "objective_id": "moon_above_horizon",
                    "input_field": "moon_altitude",
                    "value_type": "number",
                    "operator": "greater_than",
                    "expected_value": 0,
                    "success_semantics": "condition_met",
                    "required": True,
                },
                {
                    "objective_id": "not_combust",
                    "input_field": "is_combust",
                    "value_type": "boolean",
                    "operator": "equals",
                    "expected_value": False,
                    "success_semantics": "condition_met",
                    "required": False,
                },
            ],
        }
        ok, errors = validate_objective_pack(pack)
        self.assertTrue(ok, errors)
        self.assertEqual(classify_objective_pack_capability(pack)["capability"], "evaluable")
        self.assertEqual(get_objective_pack_required_input_fields(pack), ["moon_altitude"])
        fingerprint = get_objective_pack_evaluation_fingerprint(pack)
        self.assertTrue(fingerprint.startswith("sha256:"))
        with TemporaryDirectory() as tmp:
            save_objective_pack(pack, root=tmp)
            loaded = load_objective_pack("example", root=tmp)
        self.assertEqual(loaded["objectives"], pack["objectives"])
        self.assertEqual(get_objective_pack_evaluation_fingerprint(loaded), fingerprint)

    def test_duplicate_objective_ids_are_rejected(self) -> None:
        pack = {
            "objective_type": "dup",
            "version": 1,
            "matter_houses": [1],
            "natural_significators": ["Moon"],
            "action_moment": "Example",
            "objectives": [
                {"objective_id": "dup", "input_field": "a", "value_type": "number", "operator": "greater_than", "expected_value": 0, "success_semantics": "condition_met"},
                {"objective_id": "dup", "input_field": "b", "value_type": "number", "operator": "greater_than", "expected_value": 1, "success_semantics": "condition_met"},
            ],
        }
        ok, errors = validate_objective_pack(pack)
        self.assertFalse(ok)
        self.assertTrue(any("Duplicate objective_id" in error for error in errors))

    def test_missing_required_fields_are_rejected(self) -> None:
        pack = {
            "objective_type": "missing",
            "version": 1,
            "matter_houses": [1],
            "natural_significators": ["Moon"],
            "action_moment": "Example",
            "objectives": [{"objective_id": "only_id"}],
        }
        ok, errors = validate_objective_pack(pack)
        self.assertFalse(ok)
        self.assertTrue(any("missing input_field" in error for error in errors))
        self.assertEqual(classify_objective_pack_capability(pack)["capability"], "invalid")

    def test_operator_and_value_type_incompatibilities_are_rejected(self) -> None:
        pack = {
            "objective_type": "bad_types",
            "version": 1,
            "matter_houses": [1],
            "natural_significators": ["Moon"],
            "action_moment": "Example",
            "objectives": [
                {"objective_id": "bad_bool", "input_field": "flag", "value_type": "boolean", "operator": "greater_than", "expected_value": True, "success_semantics": "condition_met"},
                {"objective_id": "bad_enum", "input_field": "mode", "value_type": "enum", "operator": "equals", "expected_value": "x", "enum_values": ["a", "b"], "success_semantics": "condition_met"},
            ],
        }
        ok, errors = validate_objective_pack(pack)
        self.assertFalse(ok)
        self.assertTrue(any("incompatible" in error or "must be one of enum_values" in error for error in errors))

    def test_required_input_fields_are_deterministic(self) -> None:
        pack = {
            "objective_type": "fields",
            "version": 1,
            "matter_houses": [1],
            "natural_significators": ["Moon"],
            "action_moment": "Example",
            "objectives": [
                {"objective_id": "a", "input_field": "moon_altitude", "value_type": "number", "operator": "greater_than", "expected_value": 0, "success_semantics": "condition_met"},
                {"objective_id": "b", "input_field": "moon_altitude", "value_type": "number", "operator": "less_than", "expected_value": 90, "success_semantics": "condition_met"},
                {"objective_id": "c", "input_field": "is_combust", "value_type": "boolean", "operator": "equals", "expected_value": False, "success_semantics": "condition_met", "required": False},
                {"objective_id": "d", "input_field": "applying_aspect", "value_type": "string", "operator": "equals", "expected_value": "trine", "success_semantics": "condition_met"},
            ],
        }
        self.assertEqual(get_objective_pack_required_input_fields(pack), ["moon_altitude", "applying_aspect"])

    def test_evaluation_fingerprint_is_stable_for_identical_semantics(self) -> None:
        pack = {
            "objective_type": "stable",
            "version": 1,
            "matter_houses": [1],
            "natural_significators": ["Moon"],
            "action_moment": "Example",
            "objectives": [
                {"objective_id": "a", "input_field": "x", "value_type": "number", "operator": "between", "expected_value": [1, 5], "success_semantics": "condition_met", "label": "Ignored"},
            ],
        }
        altered = copy.deepcopy(pack)
        altered["action_moment"] = "Different text"
        altered["objectives"][0]["label"] = "Also ignored"
        self.assertEqual(get_objective_pack_evaluation_fingerprint(pack), get_objective_pack_evaluation_fingerprint(altered))

    def test_semantic_or_objective_order_changes_alter_fingerprint_and_action_moment_behavior_remains(self) -> None:
        pack = {
            "objective_type": "order",
            "version": 1,
            "matter_houses": [1],
            "natural_significators": ["Moon"],
            "action_moment": "Example",
            "objectives": [
                {"objective_id": "a", "input_field": "x", "value_type": "number", "operator": "greater_than", "expected_value": 0, "success_semantics": "condition_met"},
                {"objective_id": "b", "input_field": "y", "value_type": "string", "operator": "equals", "expected_value": "ok", "success_semantics": "condition_met"},
            ],
        }
        reordered = copy.deepcopy(pack)
        reordered["objectives"] = list(reversed(reordered["objectives"]))
        changed = copy.deepcopy(pack)
        changed["objectives"][0]["expected_value"] = 1
        self.assertNotEqual(get_objective_pack_evaluation_fingerprint(pack), get_objective_pack_evaluation_fingerprint(reordered))
        self.assertNotEqual(get_objective_pack_evaluation_fingerprint(pack), get_objective_pack_evaluation_fingerprint(changed))
        action = resolve_action_moment_with_pack("exam")
        self.assertEqual(action.instructions[-1], "Click Begin inside the elected window.")
        report = build_tactical_analysis_report({"objective": "exam", "score": 82})
        self.assertEqual(report.fast_lane.action, "Click Begin inside the elected window.")


if __name__ == "__main__":
    unittest.main()
