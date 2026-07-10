from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from typing import Any, Mapping

from .objective_packs import (
    OBJECTIVE_OPERATORS,
    OBJECTIVE_PACK_EVALUATION_SCHEMA_VERSION,
    OBJECTIVE_SUCCESS_SEMANTICS,
    OBJECTIVE_VALUE_TYPES,
    classify_objective_pack_capability,
    get_objective_pack_evaluation_fingerprint,
    validate_objective_pack,
)

INPUT_SCHEMA_VERSION = "objective_evaluation_input_v1"
RESULT_SCHEMA_VERSION = "objective_evaluation_result_v1"
EVALUATOR_SCHEMA_VERSION = "objective_evaluation_v1"
OPERATOR_BEHAVIOR_VERSION = "objective_evaluation_operator_behavior_v1"


def validate_objective_evaluation_input(
    objective_pack: dict,
    controlled_input: dict,
) -> dict:
    pack_errors = _pack_errors(objective_pack)
    capability = classify_objective_pack_capability(objective_pack)
    if capability["capability"] == "metadata_only":
        return {"status": "blocked", "blockers": ["objective_pack_not_evaluable"], "warnings": []}
    if capability["capability"] == "invalid" or pack_errors:
        return {"status": "invalid_pack", "blockers": pack_errors or list(capability.get("blockers", [])), "warnings": []}
    if not isinstance(controlled_input, Mapping):
        return {"status": "invalid_input", "blockers": ["controlled_input_invalid"], "warnings": []}
    blockers: list[str] = []
    warnings: list[str] = []
    if str(controlled_input.get("schema_version") or "") != INPUT_SCHEMA_VERSION:
        blockers.append("objective_evaluation_input_schema_unsupported")
    if not _non_empty_text(controlled_input.get("record_id")):
        blockers.append("record_id_required")
    values = controlled_input.get("values")
    if not isinstance(values, Mapping):
        blockers.append("values_mapping_required")
        values = {}
    timestamp = controlled_input.get("timestamp")
    if timestamp is not None:
        normalized = _normalize_timestamp(timestamp)
        if normalized is None:
            blockers.append("timestamp_invalid")
    if blockers:
        return {"status": "invalid_input", "blockers": blockers, "warnings": warnings}
    unsupported: list[str] = []
    for objective in list(objective_pack.get("objectives", []) or []):
        if not isinstance(objective, Mapping):
            continue
        operator = str(objective.get("operator") or "")
        field = str(objective.get("input_field") or "")
        if operator in {"exists", "not_exists"}:
            continue
        if field not in values:
            unsupported.append(f"missing_required_field:{field}")
            continue
        if not _actual_value_matches_definition(objective, values.get(field)):
            unsupported.append(f"incompatible_input_type:{field}")
    return {
        "status": "valid_with_unsupported_objectives" if unsupported else "valid",
        "blockers": [],
        "warnings": unsupported,
        "record_id": str(controlled_input.get("record_id") or ""),
        "input_fingerprint": _input_fingerprint(controlled_input),
    }


def evaluate_objective(
    objective: dict,
    controlled_input: dict,
) -> dict:
    objective_copy = deepcopy(objective)
    input_copy = deepcopy(controlled_input)
    try:
        objective_errors = _objective_errors(objective_copy)
        if objective_errors:
            return _objective_result(objective_copy, "invalid_objective", None, None, None, "invalid_objective")
        input_error = _basic_input_error(input_copy)
        if input_error:
            return _objective_result(objective_copy, "evaluator_error", None, None, None, input_error)
        field = str(objective_copy.get("input_field") or "")
        operator = str(objective_copy.get("operator") or "")
        values = dict(input_copy.get("values") or {})
        if operator in {"exists", "not_exists"}:
            actual = values.get(field)
            condition_result = (field in values and actual is not None) if operator == "exists" else (field not in values or actual is None)
            satisfied = _apply_success_semantics(str(objective_copy.get("success_semantics") or ""), condition_result)
            return _objective_result(objective_copy, "satisfied" if satisfied else "not_satisfied", condition_result, satisfied, _summarize_value(actual), None)
        if field not in values:
            return _objective_result(objective_copy, "unsupported_missing_field", None, None, None, "missing_field")
        actual = values.get(field)
        if not _actual_value_matches_definition(objective_copy, actual):
            return _objective_result(objective_copy, "unsupported_invalid_type", None, None, _summarize_value(actual), "invalid_type")
        if operator not in OBJECTIVE_OPERATORS:
            return _objective_result(objective_copy, "unsupported_operator", None, None, _summarize_value(actual), "unsupported_operator")
        condition_result = _evaluate_condition(operator, objective_copy, actual)
        satisfied = _apply_success_semantics(str(objective_copy.get("success_semantics") or ""), condition_result)
        return _objective_result(objective_copy, "satisfied" if satisfied else "not_satisfied", condition_result, satisfied, _summarize_value(actual), None)
    except Exception:
        return _objective_result(objective_copy, "evaluator_error", None, None, None, "evaluator_error")


def evaluate_objective_pack(
    objective_pack: dict,
    controlled_input: dict,
) -> dict:
    pack_before = deepcopy(objective_pack)
    input_before = deepcopy(controlled_input)
    validation = validate_objective_evaluation_input(objective_pack, controlled_input)
    if validation["status"] in {"blocked", "invalid_pack", "invalid_input"}:
        return {
            "schema_version": RESULT_SCHEMA_VERSION,
            "objective_pack_id": objective_pack.get("objective_type"),
            "objective_pack_fingerprint": None,
            "objective_evaluator_fingerprint": get_objective_evaluator_fingerprint(),
            "record_id": controlled_input.get("record_id"),
            "objective_results": [],
            "total_objectives": len(list(objective_pack.get("objectives", []) or [])) if isinstance(objective_pack, Mapping) else 0,
            "evaluated_objectives": 0,
            "satisfied_objectives": 0,
            "unsatisfied_objectives": 0,
            "unsupported_objectives": 0,
            "evaluator_errors": 0,
            "aggregate_status": "blocked",
            "result_fingerprint": None,
            "blockers": list(validation.get("blockers", [])),
            "warnings": list(validation.get("warnings", [])),
        }
    objective_results = [evaluate_objective(dict(objective), deepcopy(controlled_input)) for objective in list(objective_pack.get("objectives", []) or []) if isinstance(objective, Mapping)]
    total = len(objective_results)
    evaluated = sum(1 for item in objective_results if item["status"] in {"satisfied", "not_satisfied"})
    satisfied = sum(1 for item in objective_results if item["status"] == "satisfied")
    unsatisfied = sum(1 for item in objective_results if item["status"] == "not_satisfied")
    unsupported = sum(1 for item in objective_results if item["status"] in {"unsupported_missing_field", "unsupported_invalid_type", "unsupported_operator", "invalid_objective"})
    errors = sum(1 for item in objective_results if item["status"] == "evaluator_error")
    aggregate = "evaluator_failed" if errors else "completed_with_unsupported_objectives" if evaluated and unsupported else "completed" if evaluated == total and total > 0 else "no_evaluable_objectives"
    result = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "objective_pack_id": objective_pack.get("objective_type"),
        "objective_pack_fingerprint": get_objective_pack_evaluation_fingerprint(objective_pack),
        "objective_evaluator_fingerprint": get_objective_evaluator_fingerprint(),
        "record_id": controlled_input.get("record_id"),
        "objective_results": objective_results,
        "total_objectives": total,
        "evaluated_objectives": evaluated,
        "satisfied_objectives": satisfied,
        "unsatisfied_objectives": unsatisfied,
        "unsupported_objectives": unsupported,
        "evaluator_errors": errors,
        "aggregate_status": aggregate,
        "result_fingerprint": None,
        "blockers": [],
        "warnings": list(validation.get("warnings", [])),
    }
    result["result_fingerprint"] = _result_fingerprint(objective_pack, controlled_input, result)
    if objective_pack != pack_before or controlled_input != input_before:
        raise AssertionError("Objective evaluation mutated input state.")
    return result


def get_objective_evaluator_fingerprint() -> str:
    payload = {
        "schema_version": EVALUATOR_SCHEMA_VERSION,
        "input_schema_version": INPUT_SCHEMA_VERSION,
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "objective_pack_schema_version": OBJECTIVE_PACK_EVALUATION_SCHEMA_VERSION,
        "supported_operators": sorted(OBJECTIVE_OPERATORS),
        "supported_value_types": sorted(OBJECTIVE_VALUE_TYPES),
        "supported_success_semantics": sorted(OBJECTIVE_SUCCESS_SEMANTICS),
        "operator_behavior_version": OPERATOR_BEHAVIOR_VERSION,
    }
    return _hash_payload(payload)


def _pack_errors(objective_pack: Mapping[str, Any]) -> list[str]:
    ok, errors = validate_objective_pack(objective_pack)
    return [] if ok else list(errors)


def _objective_errors(objective: Mapping[str, Any]) -> list[str]:
    probe_pack = {
        "objective_type": "probe",
        "version": 1,
        "matter_houses": [1],
        "natural_significators": ["Moon"],
        "action_moment": "probe",
        "objectives": [dict(objective)],
    }
    ok, errors = validate_objective_pack(probe_pack)
    return [] if ok else list(errors)


def _basic_input_error(controlled_input: Mapping[str, Any]) -> str | None:
    if str(controlled_input.get("schema_version") or "") != INPUT_SCHEMA_VERSION:
        return "unsupported_input_schema"
    if not _non_empty_text(controlled_input.get("record_id")):
        return "record_id_required"
    values = controlled_input.get("values")
    if not isinstance(values, Mapping):
        return "values_mapping_required"
    timestamp = controlled_input.get("timestamp")
    if timestamp is not None and _normalize_timestamp(timestamp) is None:
        return "timestamp_invalid"
    return None


def _objective_result(
    objective: Mapping[str, Any],
    status: str,
    condition_result: bool | None,
    satisfied: bool | None,
    actual_value_summary: Any,
    error_code: str | None,
) -> dict[str, Any]:
    operator = str(objective.get("operator") or "")
    expected_value = None if operator in {"exists", "not_exists"} else _summarize_value(objective.get("expected_value"))
    return {
        "objective_id": objective.get("objective_id"),
        "input_field": objective.get("input_field"),
        "value_type": objective.get("value_type"),
        "operator": objective.get("operator"),
        "success_semantics": objective.get("success_semantics"),
        "condition_result": condition_result,
        "satisfied": satisfied,
        "status": status,
        "actual_value_summary": actual_value_summary,
        "expected_value_summary": expected_value,
        "error_code": error_code,
    }


def _actual_value_matches_definition(objective: Mapping[str, Any], actual: Any) -> bool:
    value_type = str(objective.get("value_type") or "")
    if actual is None:
        return False
    if value_type == "boolean":
        return isinstance(actual, bool)
    if value_type == "integer":
        return isinstance(actual, int) and not isinstance(actual, bool)
    if value_type == "number":
        return isinstance(actual, (int, float)) and not isinstance(actual, bool)
    if value_type == "string":
        return isinstance(actual, str)
    if value_type == "enum":
        return isinstance(actual, str) and actual in list(objective.get("enum_values") or [])
    if value_type == "timestamp":
        return _normalize_timestamp(actual) is not None
    return False


def _evaluate_condition(operator: str, objective: Mapping[str, Any], actual: Any) -> bool:
    expected = objective.get("expected_value")
    value_type = str(objective.get("value_type") or "")
    normalized_actual = _comparable_value(actual, value_type)
    if operator == "equals":
        return normalized_actual == _comparable_value(expected, value_type)
    if operator == "not_equals":
        return normalized_actual != _comparable_value(expected, value_type)
    if operator == "greater_than":
        return normalized_actual > _comparable_value(expected, value_type)
    if operator == "greater_than_or_equal":
        return normalized_actual >= _comparable_value(expected, value_type)
    if operator == "less_than":
        return normalized_actual < _comparable_value(expected, value_type)
    if operator == "less_than_or_equal":
        return normalized_actual <= _comparable_value(expected, value_type)
    if operator == "in":
        return normalized_actual in [_comparable_value(item, value_type) for item in list(expected or [])]
    if operator == "not_in":
        return normalized_actual not in [_comparable_value(item, value_type) for item in list(expected or [])]
    if operator == "between":
        lower = _comparable_value(expected[0], value_type)
        upper = _comparable_value(expected[1], value_type)
        return lower <= normalized_actual <= upper
    raise ValueError("unsupported_operator")


def _apply_success_semantics(success_semantics: str, condition_result: bool) -> bool:
    if success_semantics == "condition_met":
        return condition_result
    if success_semantics == "condition_not_met":
        return not condition_result
    raise ValueError("unsupported_success_semantics")


def _comparable_value(value: Any, value_type: str) -> Any:
    if value_type == "timestamp":
        normalized = _normalize_timestamp(value)
        if normalized is None:
            raise ValueError("invalid_timestamp")
        return normalized
    return value


def _normalize_timestamp(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone().astimezone(parsed.tzinfo).isoformat().replace("+00:00", "Z")


def _input_fingerprint(controlled_input: Mapping[str, Any]) -> str:
    payload = {
        "schema_version": controlled_input.get("schema_version"),
        "record_id": controlled_input.get("record_id"),
        "timestamp": _normalize_timestamp(controlled_input.get("timestamp")) if controlled_input.get("timestamp") is not None else None,
        "values": deepcopy(dict(controlled_input.get("values") or {})),
    }
    return _hash_payload(payload)


def _result_fingerprint(objective_pack: Mapping[str, Any], controlled_input: Mapping[str, Any], result: Mapping[str, Any]) -> str:
    payload = {
        "pack_fingerprint": get_objective_pack_evaluation_fingerprint(objective_pack),
        "evaluator_fingerprint": get_objective_evaluator_fingerprint(),
        "input_fingerprint": _input_fingerprint(controlled_input),
        "objective_results": deepcopy(list(result.get("objective_results") or [])),
        "aggregate_status": result.get("aggregate_status"),
        "counts": {
            "total_objectives": result.get("total_objectives"),
            "evaluated_objectives": result.get("evaluated_objectives"),
            "satisfied_objectives": result.get("satisfied_objectives"),
            "unsatisfied_objectives": result.get("unsatisfied_objectives"),
            "unsupported_objectives": result.get("unsupported_objectives"),
            "evaluator_errors": result.get("evaluator_errors"),
        },
    }
    return _hash_payload(payload)


def _summarize_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return deepcopy(value)
    return str(value)


def _hash_payload(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def _non_empty_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None
