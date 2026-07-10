from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

OBJECTIVE_PACK_ROOT = Path(__file__).resolve().parents[2] / "data" / "objective_packs"
OBJECTIVE_PACK_EVALUATION_SCHEMA_VERSION = "objective_pack_evaluation_contract_v1"
OBJECTIVE_VALUE_TYPES = {"boolean", "integer", "number", "string", "enum", "timestamp"}
OBJECTIVE_OPERATORS = {
    "equals",
    "not_equals",
    "greater_than",
    "greater_than_or_equal",
    "less_than",
    "less_than_or_equal",
    "in",
    "not_in",
    "exists",
    "not_exists",
    "between",
}
OBJECTIVE_SUCCESS_SEMANTICS = {"condition_met", "condition_not_met"}

DEFAULT_OBJECTIVE_PACKS: dict[str, dict[str, object]] = {
    "exam": {"objective_type": "exam", "version": "exam_v1", "matter_houses": [9], "natural_significators": ["Mercury", "Jupiter"], "action_moment": "official_exam_start", "fast_lane_action_text": "Click Begin inside the elected window.", "watchlist_defaults": {"minimum_grade": "B+", "minimum_practicality": 70, "exclude_critical_traps": True}},
    "legal": {"objective_type": "legal", "version": "legal_v1", "matter_houses": [7, 9, 10, 4], "natural_significators": ["Saturn", "Jupiter"], "action_moment": "timestamped_filing", "fast_lane_action_text": "Submit the filing inside the elected window."},
    "business": {"objective_type": "business", "version": "business_v1", "matter_houses": [10, 2, 11], "natural_significators": ["Mercury", "Jupiter", "Venus"], "action_moment": "public_launch"},
    "money": {"objective_type": "money", "version": "money_v1", "matter_houses": [2, 11], "natural_significators": ["Jupiter", "Venus"], "action_moment": "payment_submit"},
    "message": {"objective_type": "message", "version": "message_v1", "matter_houses": [3], "natural_significators": ["Mercury", "Moon"], "action_moment": "message_sent", "fast_lane_action_text": "Press Send inside the elected window."},
    "relationship": {"objective_type": "relationship", "version": "relationship_v1", "matter_houses": [1, 7], "natural_significators": ["Venus", "Moon"], "action_moment": "message_or_call_sent"},
    "travel": {"objective_type": "travel", "version": "travel_v1", "matter_houses": [3, 9], "natural_significators": ["Moon", "Mercury"], "action_moment": "trip_milestone"},
    "ritual": {"objective_type": "ritual", "version": "ritual_v1", "matter_houses": [9], "natural_significators": ["Moon", "Jupiter"], "action_moment": "formal_start"},
    "job_application": {"objective_type": "job_application", "version": "job_application_v1", "matter_houses": [10, 6], "natural_significators": ["Mercury", "Saturn"], "action_moment": "application_submit"},
    "negotiation": {"objective_type": "negotiation", "version": "negotiation_v1", "matter_houses": [7, 3], "natural_significators": ["Mercury", "Venus"], "action_moment": "offer_sent"},
    "general": {"objective_type": "general", "version": "general_v1", "matter_houses": [1, 10], "natural_significators": ["Moon"], "action_moment": "irreversible_action"},
}


def validate_objective_pack(pack: Mapping[str, object]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    for key in ("objective_type", "version", "matter_houses", "natural_significators", "action_moment"):
        if key not in pack:
            errors.append(f"Missing {key}.")
    if "matter_houses" in pack and not isinstance(pack["matter_houses"], list):
        errors.append("matter_houses must be a list.")
    objectives = pack.get("objectives")
    if objectives is not None:
        if not isinstance(objectives, list):
            errors.append("objectives must be an ordered list.")
        else:
            seen_ids: set[str] = set()
            for index, objective in enumerate(objectives):
                prefix = f"Objective {index + 1}"
                if not isinstance(objective, Mapping):
                    errors.append(f"{prefix} must be a mapping.")
                    continue
                objective_id = _non_empty_text(objective.get("objective_id"))
                input_field = _non_empty_text(objective.get("input_field"))
                value_type = _non_empty_text(objective.get("value_type"))
                operator = _non_empty_text(objective.get("operator"))
                success_semantics = _non_empty_text(objective.get("success_semantics"))
                if objective_id is None:
                    errors.append(f"{prefix} missing objective_id.")
                elif objective_id in seen_ids:
                    errors.append(f"Duplicate objective_id: {objective_id}.")
                else:
                    seen_ids.add(objective_id)
                if input_field is None:
                    errors.append(f"{prefix} missing input_field.")
                elif not _is_safe_input_field(input_field):
                    errors.append(f"{prefix} input_field is invalid.")
                if value_type is None:
                    errors.append(f"{prefix} missing value_type.")
                elif value_type not in OBJECTIVE_VALUE_TYPES:
                    errors.append(f"{prefix} value_type is unsupported.")
                if operator is None:
                    errors.append(f"{prefix} missing operator.")
                elif operator not in OBJECTIVE_OPERATORS:
                    errors.append(f"{prefix} operator is unsupported.")
                if success_semantics is None:
                    errors.append(f"{prefix} missing success_semantics.")
                elif success_semantics not in OBJECTIVE_SUCCESS_SEMANTICS:
                    errors.append(f"{prefix} success_semantics is unsupported.")
                if "required" in objective and not isinstance(objective.get("required"), bool):
                    errors.append(f"{prefix} required must be boolean.")
                enum_values = objective.get("enum_values")
                if value_type == "enum":
                    if not isinstance(enum_values, list) or not enum_values or any(not isinstance(item, str) or not item.strip() for item in enum_values):
                        errors.append(f"{prefix} enum_values must be a non-empty string list.")
                elif enum_values is not None and (not isinstance(enum_values, list) or any(not isinstance(item, str) for item in enum_values)):
                    errors.append(f"{prefix} enum_values must be a string list when present.")
                if operator not in {"exists", "not_exists"} and "expected_value" not in objective:
                    errors.append(f"{prefix} missing expected_value.")
                if operator in {"exists", "not_exists"} and "expected_value" in objective:
                    errors.append(f"{prefix} must not declare expected_value for {operator}.")
                if value_type and operator and operator in OBJECTIVE_OPERATORS and value_type in OBJECTIVE_VALUE_TYPES:
                    errors.extend(_validate_objective_semantics(prefix, objective, value_type, operator))
    return not errors, errors


def classify_objective_pack_capability(pack: Mapping[str, object]) -> dict[str, object]:
    ok, errors = validate_objective_pack(pack)
    if not ok:
        return {"capability": "invalid", "blockers": list(errors)}
    objectives = pack.get("objectives")
    if not isinstance(objectives, list) or not objectives:
        return {"capability": "metadata_only", "blockers": []}
    return {"capability": "evaluable", "blockers": []}


def get_objective_pack_required_input_fields(pack: Mapping[str, object]) -> list[str]:
    capability = classify_objective_pack_capability(pack)
    if capability["capability"] != "evaluable":
        raise ValueError("Objective pack is not evaluable.")
    ordered: list[str] = []
    seen: set[str] = set()
    for objective in list(pack.get("objectives", []) or []):
        if not isinstance(objective, Mapping):
            continue
        if objective.get("required", True) is False:
            continue
        field = str(objective.get("input_field") or "")
        if field and field not in seen:
            seen.add(field)
            ordered.append(field)
    return ordered


def get_objective_pack_evaluation_fingerprint(pack: Mapping[str, object]) -> str:
    capability = classify_objective_pack_capability(pack)
    if capability["capability"] != "evaluable":
        raise ValueError("Objective pack is not evaluable.")
    objectives = []
    for objective in list(pack.get("objectives", []) or []):
        if not isinstance(objective, Mapping):
            continue
        operator = str(objective.get("operator") or "")
        semantics: dict[str, Any] = {
            "objective_id": str(objective.get("objective_id") or ""),
            "input_field": str(objective.get("input_field") or ""),
            "value_type": str(objective.get("value_type") or ""),
            "operator": operator,
            "success_semantics": str(objective.get("success_semantics") or ""),
            "required": bool(objective.get("required", True)),
        }
        if operator not in {"exists", "not_exists"}:
            semantics["expected_value"] = objective.get("expected_value")
        if objective.get("enum_values") is not None:
            semantics["enum_values"] = list(objective.get("enum_values") or [])
        objectives.append(semantics)
    payload = {
        "schema_version": OBJECTIVE_PACK_EVALUATION_SCHEMA_VERSION,
        "objective_type": pack.get("objective_type"),
        "version": pack.get("version"),
        "objectives": objectives,
    }
    return "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def load_objective_pack(objective_type: str, *, root: Path | str = OBJECTIVE_PACK_ROOT) -> dict[str, object]:
    key = _key(objective_type)
    path = Path(root) / f"{key}.json"
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            pack = json.load(handle)
    else:
        pack = DEFAULT_OBJECTIVE_PACKS.get(key) or DEFAULT_OBJECTIVE_PACKS["general"]
    ok, errors = validate_objective_pack(pack)
    if not ok:
        raise ValueError("; ".join(errors))
    return dict(pack)


def save_objective_pack(pack: Mapping[str, object], *, root: Path | str = OBJECTIVE_PACK_ROOT) -> Path:
    ok, errors = validate_objective_pack(pack)
    if not ok:
        raise ValueError("; ".join(errors))
    base = Path(root)
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{_key(str(pack['objective_type']))}.json"
    path.write_text(json.dumps(dict(pack), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def default_objective_pack_ids() -> tuple[str, ...]:
    return tuple(DEFAULT_OBJECTIVE_PACKS)


def objective_pack_action_text(objective_type: str) -> str:
    pack = load_objective_pack(objective_type)
    return str(pack.get("fast_lane_action_text") or pack.get("action_moment"))


def _key(value: str) -> str:
    return str(value or "general").lower().replace(" ", "_").replace("/", "_")


def _non_empty_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _is_safe_input_field(value: str) -> bool:
    return value.replace("_", "").isalnum()


def _validate_objective_semantics(prefix: str, objective: Mapping[str, object], value_type: str, operator: str) -> list[str]:
    errors: list[str] = []
    expected = objective.get("expected_value")
    if operator in {"exists", "not_exists"}:
        return errors
    if operator in {"greater_than", "greater_than_or_equal", "less_than", "less_than_or_equal"} and value_type not in {"integer", "number", "timestamp"}:
        errors.append(f"{prefix} operator {operator} is incompatible with {value_type}.")
    if operator == "between":
        if value_type not in {"integer", "number", "timestamp"}:
            errors.append(f"{prefix} operator between is incompatible with {value_type}.")
        elif not isinstance(expected, list) or len(expected) != 2:
            errors.append(f"{prefix} between requires a deterministic two-value range.")
    elif operator in {"in", "not_in"}:
        if not isinstance(expected, list) or not expected:
            errors.append(f"{prefix} operator {operator} requires a non-empty list.")
    elif operator in {"equals", "not_equals", "greater_than", "greater_than_or_equal", "less_than", "less_than_or_equal"}:
        if not _is_valid_expected_value(expected, value_type):
            errors.append(f"{prefix} expected_value is incompatible with {value_type}.")
    if value_type == "enum" and operator in {"equals", "not_equals"} and isinstance(objective.get("enum_values"), list) and isinstance(expected, str) and expected not in list(objective.get("enum_values") or []):
        errors.append(f"{prefix} expected_value must be one of enum_values.")
    if value_type == "enum" and operator in {"in", "not_in"} and isinstance(expected, list):
        allowed = set(objective.get("enum_values") or [])
        if any(not isinstance(item, str) or item not in allowed for item in expected):
            errors.append(f"{prefix} expected_value list must stay within enum_values.")
    return errors


def _is_valid_expected_value(value: Any, value_type: str) -> bool:
    if value_type == "boolean":
        return isinstance(value, bool)
    if value_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if value_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if value_type == "string":
        return isinstance(value, str)
    if value_type == "enum":
        return isinstance(value, str)
    if value_type == "timestamp":
        return isinstance(value, str) and bool(value.strip())
    return False
