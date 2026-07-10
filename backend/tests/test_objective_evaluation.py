from __future__ import annotations

import copy
from unittest import TestCase

from backend.electional.objective_evaluation import (
    evaluate_objective,
    evaluate_objective_pack,
    get_objective_evaluator_fingerprint,
    validate_objective_evaluation_input,
)
from backend.electional.objective_packs import DEFAULT_OBJECTIVE_PACKS


def _pack() -> dict:
    return {
        "objective_type": "example",
        "version": 1,
        "matter_houses": [1, 10],
        "natural_significators": ["Moon"],
        "action_moment": "Example",
        "objectives": [
            {"objective_id": "flag_true", "input_field": "is_combust", "value_type": "boolean", "operator": "equals", "expected_value": False, "success_semantics": "condition_met"},
            {"objective_id": "aspect_match", "input_field": "applying_aspect", "value_type": "string", "operator": "equals", "expected_value": "trine", "success_semantics": "condition_met"},
            {"objective_id": "moon_height", "input_field": "moon_altitude", "value_type": "number", "operator": "greater_than", "expected_value": 0, "success_semantics": "condition_met"},
        ],
    }


def _input() -> dict:
    return {
        "schema_version": "objective_evaluation_input_v1",
        "record_id": "record_001",
        "timestamp": "2026-01-01T00:00:00Z",
        "values": {"moon_altitude": 25.5, "is_combust": False, "applying_aspect": "trine"},
    }


class ObjectiveEvaluationTest(TestCase):
    def test_boolean_and_string_objectives_evaluate_deterministically(self) -> None:
        controlled = _input()
        results = [
            evaluate_objective(_pack()["objectives"][0], controlled),
            evaluate_objective(_pack()["objectives"][1], controlled),
            evaluate_objective(_pack()["objectives"][1], controlled),
        ]
        self.assertEqual(results[0]["status"], "satisfied")
        self.assertEqual(results[1]["status"], "satisfied")
        self.assertEqual(results[1], results[2])

    def test_numeric_comparison_and_between_operators(self) -> None:
        objective = {"objective_id": "height_band", "input_field": "moon_altitude", "value_type": "number", "operator": "between", "expected_value": [20, 30], "success_semantics": "condition_met"}
        result = evaluate_objective(objective, _input())
        self.assertEqual(result["status"], "satisfied")
        self.assertTrue(result["condition_result"])

    def test_in_not_in_exists_and_not_exists_operators(self) -> None:
        controlled = _input()
        enum_obj = {"objective_id": "aspect_in", "input_field": "applying_aspect", "value_type": "enum", "operator": "in", "expected_value": ["trine", "sextile"], "enum_values": ["trine", "square", "sextile"], "success_semantics": "condition_met"}
        missing_obj = {"objective_id": "optional_missing", "input_field": "missing_field", "value_type": "string", "operator": "not_exists", "success_semantics": "condition_met"}
        self.assertEqual(evaluate_objective(enum_obj, controlled)["status"], "satisfied")
        self.assertEqual(evaluate_objective(missing_obj, controlled)["status"], "satisfied")

    def test_missing_field_is_unsupported_without_inference(self) -> None:
        objective = {"objective_id": "needs_field", "input_field": "sun_altitude", "value_type": "number", "operator": "greater_than", "expected_value": 0, "success_semantics": "condition_met"}
        validation = validate_objective_evaluation_input({"objective_type": "x", "version": 1, "matter_houses": [1], "natural_significators": ["Moon"], "action_moment": "Example", "objectives": [objective]}, _input())
        result = evaluate_objective(objective, _input())
        self.assertEqual(validation["status"], "valid_with_unsupported_objectives")
        self.assertEqual(result["status"], "unsupported_missing_field")

    def test_invalid_type_and_unknown_operator_are_rejected(self) -> None:
        controlled = _input()
        controlled["values"]["moon_altitude"] = True
        numeric = {"objective_id": "bad_number", "input_field": "moon_altitude", "value_type": "number", "operator": "greater_than", "expected_value": 0, "success_semantics": "condition_met"}
        unknown = {"objective_id": "unknown_op", "input_field": "moon_altitude", "value_type": "number", "operator": "regex", "expected_value": 0, "success_semantics": "condition_met"}
        self.assertEqual(evaluate_objective(numeric, controlled)["status"], "unsupported_invalid_type")
        self.assertEqual(evaluate_objective(unknown, _input())["status"], "invalid_objective")

    def test_success_semantics_condition_met_and_not_met(self) -> None:
        controlled = _input()
        met = {"objective_id": "met", "input_field": "moon_altitude", "value_type": "number", "operator": "greater_than", "expected_value": 0, "success_semantics": "condition_met"}
        not_met = {"objective_id": "not_met", "input_field": "moon_altitude", "value_type": "number", "operator": "greater_than", "expected_value": 0, "success_semantics": "condition_not_met"}
        self.assertTrue(evaluate_objective(met, controlled)["satisfied"])
        self.assertFalse(evaluate_objective(not_met, controlled)["satisfied"])

    def test_pack_results_order_counts_and_fingerprints_are_stable(self) -> None:
        pack = _pack()
        controlled = _input()
        first = evaluate_objective_pack(pack, controlled)
        second = evaluate_objective_pack(copy.deepcopy(pack), copy.deepcopy(controlled))
        self.assertEqual([item["objective_id"] for item in first["objective_results"]], ["flag_true", "aspect_match", "moon_height"])
        self.assertEqual(first["aggregate_status"], "completed")
        self.assertEqual(first["evaluated_objectives"], 3)
        self.assertEqual(first["satisfied_objectives"], 3)
        self.assertEqual(first["result_fingerprint"], second["result_fingerprint"])
        self.assertEqual(get_objective_evaluator_fingerprint(), get_objective_evaluator_fingerprint())
        blocked = evaluate_objective_pack({"objective_type": "legacy", "version": 1, "matter_houses": [1], "natural_significators": ["Moon"], "action_moment": "Example"}, controlled)
        self.assertEqual(blocked["aggregate_status"], "blocked")

    def test_evaluation_does_not_mutate_pack_input_or_production_state(self) -> None:
        pack = _pack()
        controlled = _input()
        pack_before = copy.deepcopy(pack)
        input_before = copy.deepcopy(controlled)
        defaults_before = copy.deepcopy(DEFAULT_OBJECTIVE_PACKS)
        result = evaluate_objective_pack(pack, controlled)
        self.assertEqual(pack, pack_before)
        self.assertEqual(controlled, input_before)
        self.assertEqual(DEFAULT_OBJECTIVE_PACKS, defaults_before)
        self.assertEqual(result["aggregate_status"], "completed")

