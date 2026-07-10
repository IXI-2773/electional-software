from __future__ import annotations

import copy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.electional.objective_outcome_scoring import (
    evaluate_objective_outcomes,
    get_objective_outcome_scoring_config_fingerprint,
    get_objective_outcome_scoring_evaluator_fingerprint,
    load_objective_outcome_scoring_config,
    save_objective_outcome_scoring_config,
    validate_objective_outcome_scoring_config,
)
from backend.electional.objective_packs import DEFAULT_OBJECTIVE_PACKS, get_objective_pack_evaluation_fingerprint, save_objective_pack


def _pack() -> dict:
    return {
        "objective_type": "score_pack",
        "version": 1,
        "matter_houses": [1, 10],
        "natural_significators": ["Moon"],
        "action_moment": "Example",
        "objectives": [
            {"objective_id": "eligible_action", "input_field": "eligible_action", "value_type": "boolean", "operator": "equals", "expected_value": True, "success_semantics": "condition_met"},
            {"objective_id": "signal_is_go", "input_field": "signal_value", "value_type": "string", "operator": "equals", "expected_value": "GO", "success_semantics": "condition_met"},
        ],
    }


def _config(pack: dict) -> dict:
    return {
        "schema_version": "objective_outcome_scoring_config_v1",
        "scoring_config_id": "standard_objective_score_v1",
        "objective_pack_id": pack["objective_type"],
        "objective_pack_evaluation_fingerprint": get_objective_pack_evaluation_fingerprint(pack),
        "score_direction": "higher_is_better",
        "unmapped_objective_behavior": "ignore",
        "minimum_score": -100,
        "maximum_score": 100,
        "entries": [
            {"objective_id": "eligible_action", "score_when_satisfied": 2.0, "score_when_unsatisfied": -1.0, "missing_behavior": "error", "unsupported_behavior": "error"},
            {"objective_id": "signal_is_go", "score_when_satisfied": 1.5, "score_when_unsatisfied": -0.5, "missing_behavior": "ignore", "unsupported_behavior": "zero"},
        ],
    }


def _outcomes(pack: dict) -> dict:
    return {
        "objective_pack_id": pack["objective_type"],
        "objective_pack_evaluation_fingerprint": get_objective_pack_evaluation_fingerprint(pack),
        "record_id": "record_001",
        "objective_results": [
            {"objective_id": "eligible_action", "status": "satisfied", "satisfied": True},
            {"objective_id": "signal_is_go", "status": "not_satisfied", "satisfied": False},
        ],
    }


class ObjectiveOutcomeScoringTest(TestCase):
    def test_valid_scoring_config_validates_saves_and_loads_idempotently(self) -> None:
        pack = _pack()
        config = _config(pack)
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "store"
            save_objective_pack(pack, root=root / "objective_packs")
            validation = validate_objective_outcome_scoring_config(config, pack)
            first = save_objective_outcome_scoring_config(config, confirmation="SAVE_SCORING_CONFIG", root=root)
            second = save_objective_outcome_scoring_config(copy.deepcopy(config), confirmation="SAVE_SCORING_CONFIG", root=root)
            loaded = load_objective_outcome_scoring_config(config["scoring_config_id"], root=root)
        self.assertTrue(validation["valid"], validation["blockers"])
        self.assertEqual(first["status"], "saved")
        self.assertEqual(second["status"], "already_saved")
        self.assertEqual(loaded["status"], "loaded")
        self.assertEqual(loaded["scoring_config"]["scoring_config_fingerprint"], first["scoring_config_fingerprint"])

    def test_satisfied_and_unsatisfied_objectives_receive_explicit_contributions(self) -> None:
        pack = _pack()
        result = evaluate_objective_outcomes(_config(pack), _outcomes(pack))
        self.assertEqual(result["aggregate_status"], "completed")
        self.assertEqual(result["raw_score"], 1.5)
        self.assertEqual(result["component_results"][0]["component_status"], "scored_satisfied")
        self.assertEqual(result["component_results"][1]["component_status"], "scored_unsatisfied")

    def test_missing_objective_behaviors_error_ignore_and_zero(self) -> None:
        pack = _pack()
        config = _config(pack)
        outcomes = {"objective_pack_id": pack["objective_type"], "objective_pack_evaluation_fingerprint": get_objective_pack_evaluation_fingerprint(pack), "record_id": "record_001", "objective_results": []}
        blocked = evaluate_objective_outcomes(config, outcomes)
        self.assertEqual(blocked["aggregate_status"], "blocked")
        config["entries"][0]["missing_behavior"] = "ignore"
        config["entries"][1]["missing_behavior"] = "zero"
        changed = evaluate_objective_outcomes(config, outcomes)
        self.assertIn(changed["aggregate_status"], {"completed_with_ignored_components", "no_scored_components"})
        self.assertTrue(any(item["component_status"] == "ignored_missing" for item in changed["component_results"]))
        self.assertTrue(any(item["component_status"] == "scored_zero" for item in changed["component_results"]))

    def test_unsupported_objective_behaviors_error_ignore_and_zero(self) -> None:
        pack = _pack()
        config = _config(pack)
        outcomes = _outcomes(pack)
        outcomes["objective_results"][0]["status"] = "unsupported_missing_field"
        blocked = evaluate_objective_outcomes(config, outcomes)
        self.assertEqual(blocked["aggregate_status"], "blocked")
        config["entries"][0]["unsupported_behavior"] = "ignore"
        config["entries"][1]["unsupported_behavior"] = "zero"
        changed = evaluate_objective_outcomes(config, outcomes)
        self.assertTrue(any(item["component_status"] == "ignored_unsupported" for item in changed["component_results"]))

    def test_unknown_objectives_follow_explicit_unmapped_behavior(self) -> None:
        pack = _pack()
        outcomes = _outcomes(pack)
        outcomes["objective_results"].append({"objective_id": "extra", "status": "satisfied", "satisfied": True})
        config = _config(pack)
        ignored = evaluate_objective_outcomes(config, outcomes)
        self.assertEqual(ignored["aggregate_status"], "completed")
        config["unmapped_objective_behavior"] = "error"
        blocked = evaluate_objective_outcomes(config, outcomes)
        self.assertEqual(blocked["aggregate_status"], "blocked")

    def test_score_bounds_component_order_and_fingerprints_are_deterministic(self) -> None:
        pack = _pack()
        config = _config(pack)
        outcomes = _outcomes(pack)
        result_one = evaluate_objective_outcomes(config, outcomes)
        result_two = evaluate_objective_outcomes(copy.deepcopy(config), copy.deepcopy(outcomes))
        self.assertEqual([item["objective_id"] for item in result_one["component_results"]], ["eligible_action", "signal_is_go"])
        self.assertEqual(result_one["result_fingerprint"], result_two["result_fingerprint"])
        self.assertEqual(get_objective_outcome_scoring_config_fingerprint(config), get_objective_outcome_scoring_config_fingerprint(copy.deepcopy(config)))
        self.assertEqual(get_objective_outcome_scoring_evaluator_fingerprint(), get_objective_outcome_scoring_evaluator_fingerprint())

    def test_pack_identity_or_fingerprint_mismatch_is_blocked(self) -> None:
        pack = _pack()
        config = _config(pack)
        outcomes = _outcomes(pack)
        outcomes["objective_pack_id"] = "other_pack"
        blocked = evaluate_objective_outcomes(config, outcomes)
        self.assertEqual(blocked["aggregate_status"], "blocked")
        bad_config = copy.deepcopy(config)
        bad_config["objective_pack_evaluation_fingerprint"] = "sha256:other"
        validation = validate_objective_outcome_scoring_config(bad_config, pack)
        self.assertFalse(validation["valid"])

    def test_evaluation_does_not_mutate_inputs_or_production_state(self) -> None:
        pack = _pack()
        config = _config(pack)
        outcomes = _outcomes(pack)
        pack_before = copy.deepcopy(pack)
        config_before = copy.deepcopy(config)
        outcomes_before = copy.deepcopy(outcomes)
        defaults_before = copy.deepcopy(DEFAULT_OBJECTIVE_PACKS)
        result = evaluate_objective_outcomes(config, outcomes)
        self.assertEqual(pack, pack_before)
        self.assertEqual(config, config_before)
        self.assertEqual(outcomes, outcomes_before)
        self.assertEqual(DEFAULT_OBJECTIVE_PACKS, defaults_before)
        self.assertEqual(result["aggregate_status"], "completed")
