from __future__ import annotations

from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

from backend.electional.analysis.fast_lane import get_fast_lane_capability_manifest
from backend.electional.canonical_rule_runtime import validate_canonical_rule_record
from backend.electional.fast_lane_compatibility import (
    evaluate_certified_rule_fast_lane_compatibility,
    format_fast_lane_compatibility_report,
    get_fast_lane_capability_fingerprint,
    get_fast_lane_compatibility_evaluator_fingerprint,
    validate_certified_rule_fast_lane_inputs,
    validate_fast_lane_capability_manifest,
)


def _rule(**overrides: object) -> dict[str, object]:
    rule = {
        "schema_version": "canonical_mutable_rule_v1",
        "rule_id": "fast_lane_rule_1",
        "rule_type": "electional_constraint",
        "target": "fast_lane.command",
        "scope": "report_output",
        "condition": {"field": "final_command.command", "operator": "equals", "value": "USE"},
        "operator": "equals",
        "value": "USE",
        "priority": 100,
        "enabled": True,
        "status": "active",
        "document_id": "doc_fast_lane",
        "source_proposal_id": "proposal_fast_lane_1",
        "source_revision": "7",
    }
    rule.update(overrides)
    validation = validate_canonical_rule_record(rule, require_active=False)
    rule["rule_fingerprint"] = validation["rule_fingerprint"]
    return rule


def _certification(rule: dict[str, object], **overrides: object) -> dict[str, object]:
    payload = {
        "certification_receipt_id": "cert_fast_lane_1",
        "rule_id": rule["rule_id"],
        "document_id": rule["document_id"],
        "source_revision": rule["source_revision"],
        "rule_hash": rule["rule_fingerprint"],
        "certification_status": "completed",
    }
    payload.update(overrides)
    return payload


def _source_context(rule: dict[str, object], **overrides: object) -> dict[str, object]:
    payload = {
        "document_id": rule["document_id"],
        "source_revision": rule["source_revision"],
        "current_source_revision": rule["source_revision"],
        "rule_fingerprint": rule["rule_fingerprint"],
    }
    payload.update(overrides)
    return payload


class FastLaneCompatibilityTest(TestCase):
    def test_real_fast_lane_capability_manifest_is_valid_and_stable(self) -> None:
        manifest_one = get_fast_lane_capability_manifest()
        manifest_two = get_fast_lane_capability_manifest()
        validation = validate_fast_lane_capability_manifest(manifest_one)
        self.assertTrue(validation["valid"], validation["blockers"])
        self.assertEqual(manifest_one, manifest_two)
        self.assertEqual(get_fast_lane_capability_fingerprint(manifest_one), get_fast_lane_capability_fingerprint(manifest_two))

    def test_supported_certified_rule_is_directly_compatible(self) -> None:
        rule = _rule()
        result = evaluate_certified_rule_fast_lane_compatibility(rule, _certification(rule), _source_context(rule), get_fast_lane_capability_manifest())
        self.assertEqual(result["overall_status"], "compatible")
        self.assertEqual(result["semantic_loss"], "none")
        self.assertIn("equals", result["supported_operators"])
        self.assertIn("final_command.command", result["supported_input_fields"])
        self.assertIn("fast_lane.command", result["supported_actions"])

    def test_inactive_uncertified_or_stale_rule_is_blocked(self) -> None:
        manifest = get_fast_lane_capability_manifest()
        cases = [
            (_rule(status="inactive", enabled=False), _certification(_rule()), _source_context(_rule()), "canonical_rule_not_active"),
            (_rule(), _certification(_rule(), certification_status="stale"), _source_context(_rule()), "certification_not_completed"),
            (_rule(), _certification(_rule()), _source_context(_rule(), current_source_revision="8"), "source_revision_not_current"),
        ]
        for rule, certification, source_context, blocker in cases:
            result = evaluate_certified_rule_fast_lane_compatibility(rule, certification, source_context, manifest)
            self.assertEqual(result["overall_status"], "blocked")
            self.assertIn(blocker, result["blockers"])

    def test_unsupported_operator_is_reported_without_translation(self) -> None:
        rule = _rule(operator="not_in", condition={"field": "final_command.command", "operator": "not_in", "value": "USE"})
        result = evaluate_certified_rule_fast_lane_compatibility(rule, _certification(rule), _source_context(rule), get_fast_lane_capability_manifest())
        self.assertIn("unsupported_condition_operator", result["blockers"])
        self.assertIn("not_in", result["unsupported_operators"])
        self.assertNotEqual(result["overall_status"], "compatible")

    def test_unsupported_field_value_type_or_action_is_incompatible(self) -> None:
        manifest = get_fast_lane_capability_manifest()
        field_rule = _rule(condition={"field": "final_command.cmd", "operator": "equals", "value": "USE"})
        field_result = evaluate_certified_rule_fast_lane_compatibility(field_rule, _certification(field_rule), _source_context(field_rule), manifest)
        type_rule = _rule(condition={"field": "final_command.confidence", "operator": "greater_than", "value": True}, operator="greater_than", value="USE")
        type_result = evaluate_certified_rule_fast_lane_compatibility(type_rule, _certification(type_rule), _source_context(type_rule), manifest)
        action_rule = _rule(target="fast_lane.headline", value="headline_change")
        action_result = evaluate_certified_rule_fast_lane_compatibility(action_rule, _certification(action_rule), _source_context(action_rule), manifest)
        self.assertEqual(field_result["overall_status"], "incompatible")
        self.assertIn("unsupported_input_field", field_result["blockers"])
        self.assertEqual(type_result["overall_status"], "incompatible")
        self.assertIn("unsupported_value_type", type_result["blockers"])
        self.assertEqual(action_result["overall_status"], "incompatible")
        self.assertIn("unsupported_action_target", action_result["blockers"])

    def test_nested_or_ambiguous_semantics_are_not_flattened_or_inferred(self) -> None:
        rule = _rule(condition={"field": "final_command.command", "operator": "equals", "value": "USE", "all": [{"field": "practicality.confidence", "operator": "greater_than", "value": 0.8}]})
        result = evaluate_certified_rule_fast_lane_compatibility(rule, _certification(rule), _source_context(rule), get_fast_lane_capability_manifest())
        self.assertEqual(result["semantic_loss"], "confirmed")
        self.assertIn("nested_condition_structure_unsupported", result["blockers"])
        self.assertNotEqual(result["overall_status"], "compatible")

    def test_dimension_order_statuses_and_fingerprints_are_deterministic(self) -> None:
        rule = _rule()
        manifest = get_fast_lane_capability_manifest()
        one = evaluate_certified_rule_fast_lane_compatibility(rule, _certification(rule), _source_context(rule), manifest)
        two = evaluate_certified_rule_fast_lane_compatibility(deepcopy(rule), deepcopy(_certification(rule)), deepcopy(_source_context(rule)), deepcopy(manifest))
        self.assertEqual([item["dimension"] for item in one["dimension_results"]], [item["dimension"] for item in two["dimension_results"]])
        self.assertEqual(one["result_fingerprint"], two["result_fingerprint"])
        self.assertEqual(get_fast_lane_compatibility_evaluator_fingerprint(), get_fast_lane_compatibility_evaluator_fingerprint())

    def test_compatibility_evaluation_does_not_execute_or_mutate_fast_lane(self) -> None:
        rule = _rule()
        certification = _certification(rule)
        source_context = _source_context(rule)
        manifest = get_fast_lane_capability_manifest()
        rule_before = deepcopy(rule)
        certification_before = deepcopy(certification)
        source_before = deepcopy(source_context)
        manifest_before = deepcopy(manifest)
        with patch("backend.electional.fast_lane_compatibility.get_fast_lane_capability_manifest", side_effect=AssertionError("compatibility must use supplied manifest")), patch("backend.electional.analysis.fast_lane.build_fast_lane_report", side_effect=AssertionError("fast lane execution must not run")):
            result = evaluate_certified_rule_fast_lane_compatibility(rule, certification, source_context, manifest)
            report = format_fast_lane_compatibility_report(result, public_safe=True)
        self.assertEqual(rule, rule_before)
        self.assertEqual(certification, certification_before)
        self.assertEqual(source_context, source_before)
        self.assertEqual(manifest, manifest_before)
        self.assertEqual(result["overall_status"], "compatible")
        self.assertIn("Fast Lane was not executed.", report)
        self.assertNotIn("C:\\", report)
