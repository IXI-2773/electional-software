"""Pure read-only compatibility evaluation for the Fast Lane contract."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Mapping

from .analysis.fast_lane import (
    FAST_LANE_CAPABILITY_SCHEMA_VERSION,
    FAST_LANE_CONTRACT_ID,
    FAST_LANE_CONTRACT_VERSION,
    get_fast_lane_capability_manifest,
)
from .canonical_rule_runtime import CANONICAL_RULE_SCHEMA_VERSION, SUPPORTED_OPERATORS, validate_canonical_rule_record
from .rule_effectiveness_analysis import _hash_payload

COMPATIBILITY_RESULT_SCHEMA = "fast_lane_compatibility_result_v1"
COMPATIBILITY_EVALUATOR_SCHEMA = "fast_lane_compatibility_evaluator_v1"
DIMENSION_ORDER = [
    "lifecycle",
    "provenance",
    "rule_schema",
    "condition_structure",
    "condition_operators",
    "input_fields",
    "value_types",
    "action_or_output_type",
    "determinism",
    "read_only_support",
]
ALLOWED_DIMENSION_STATUSES = {"compatible", "compatible_with_warning", "incompatible", "blocked", "unknown"}
ALLOWED_OVERALL_STATUSES = {"compatible", "compatible_with_warnings", "partially_compatible", "incompatible", "blocked", "unknown"}
ALLOWED_SEMANTIC_LOSS = {"none", "potential", "confirmed", "unknown"}


def validate_fast_lane_capability_manifest(capability_manifest: dict) -> dict:
    blockers: list[str] = []
    warnings: list[str] = []
    if not isinstance(capability_manifest, Mapping):
        return {"valid": False, "status": "blocked", "blockers": ["fast_lane_capability_manifest_invalid"], "warnings": []}
    if str(capability_manifest.get("schema_version") or "") != FAST_LANE_CAPABILITY_SCHEMA_VERSION:
        blockers.append("fast_lane_capability_manifest_schema_unsupported")
    if str(capability_manifest.get("fast_lane_contract_id") or "") != FAST_LANE_CONTRACT_ID:
        blockers.append("fast_lane_contract_id_mismatch")
    if capability_manifest.get("fast_lane_contract_version") != FAST_LANE_CONTRACT_VERSION:
        blockers.append("fast_lane_contract_version_mismatch")
    if capability_manifest.get("deterministic") is not True:
        blockers.append("fast_lane_not_deterministic")
    if capability_manifest.get("supports_read_only_evaluation") is not True:
        blockers.append("fast_lane_read_only_boundary_missing")
    if capability_manifest.get("requires_active_rule") is not True:
        blockers.append("fast_lane_active_rule_requirement_missing")
    if capability_manifest.get("requires_certification") is not True:
        blockers.append("fast_lane_certification_requirement_missing")
    if not isinstance(capability_manifest.get("accepted_input_schema_versions"), list) or not capability_manifest.get("accepted_input_schema_versions"):
        blockers.append("fast_lane_input_schema_versions_missing")
    if not isinstance(capability_manifest.get("supported_rule_schema_versions"), list) or CANONICAL_RULE_SCHEMA_VERSION not in list(capability_manifest.get("supported_rule_schema_versions") or []):
        blockers.append("fast_lane_supported_rule_schemas_missing")
    operators = capability_manifest.get("supported_condition_operators")
    if not isinstance(operators, list) or not operators:
        blockers.append("fast_lane_supported_condition_operators_missing")
    elif any(str(item) not in SUPPORTED_OPERATORS for item in operators):
        blockers.append("fast_lane_supported_condition_operators_invalid")
    if not isinstance(capability_manifest.get("supported_input_fields"), list) or not capability_manifest.get("supported_input_fields"):
        blockers.append("fast_lane_supported_input_fields_missing")
    if not isinstance(capability_manifest.get("supported_action_types"), list) or not capability_manifest.get("supported_action_types"):
        blockers.append("fast_lane_supported_action_types_missing")
    if not isinstance(capability_manifest.get("required_provenance_fields"), list) or not capability_manifest.get("required_provenance_fields"):
        blockers.append("fast_lane_required_provenance_fields_missing")
    value_types = capability_manifest.get("value_types_by_field")
    if not isinstance(value_types, Mapping) or not value_types:
        blockers.append("fast_lane_value_types_by_field_missing")
    else:
        for key, values in value_types.items():
            if not isinstance(key, str) or not key.strip():
                blockers.append("fast_lane_value_type_field_invalid")
                continue
            if not isinstance(values, list) or not values or any(not isinstance(item, str) or not item.strip() for item in values):
                blockers.append(f"fast_lane_value_type_invalid:{key}")
    return {"valid": not blockers, "status": "compatible" if not blockers else "blocked", "blockers": blockers, "warnings": warnings}


def get_fast_lane_capability_fingerprint(capability_manifest: dict) -> str:
    manifest = deepcopy(dict(capability_manifest))
    payload = {
        "schema_version": manifest.get("schema_version"),
        "fast_lane_contract_id": manifest.get("fast_lane_contract_id"),
        "fast_lane_contract_version": manifest.get("fast_lane_contract_version"),
        "accepted_input_schema_versions": list(manifest.get("accepted_input_schema_versions") or []),
        "supported_rule_schema_versions": list(manifest.get("supported_rule_schema_versions") or []),
        "supported_condition_operators": list(manifest.get("supported_condition_operators") or []),
        "supported_input_fields": list(manifest.get("supported_input_fields") or []),
        "supported_input_field_families": list(manifest.get("supported_input_field_families") or []),
        "supported_action_types": list(manifest.get("supported_action_types") or []),
        "supported_action_values": manifest.get("supported_action_values") or {},
        "supported_result_types": list(manifest.get("supported_result_types") or []),
        "required_provenance_fields": list(manifest.get("required_provenance_fields") or []),
        "value_types_by_field": manifest.get("value_types_by_field") or {},
        "requires_active_rule": manifest.get("requires_active_rule"),
        "requires_certification": manifest.get("requires_certification"),
        "supports_read_only_evaluation": manifest.get("supports_read_only_evaluation"),
        "deterministic": manifest.get("deterministic"),
    }
    return _hash_payload(payload)


def validate_certified_rule_fast_lane_inputs(
    canonical_rule: dict,
    certification: dict,
    source_context: dict,
    capability_manifest: dict,
) -> dict:
    blockers: list[str] = []
    warnings: list[str] = []
    rule_copy = deepcopy(canonical_rule)
    cert_copy = deepcopy(certification)
    source_copy = deepcopy(source_context)
    manifest_copy = deepcopy(capability_manifest)
    manifest_validation = validate_fast_lane_capability_manifest(manifest_copy)
    if not manifest_validation["valid"]:
        blockers.extend(list(manifest_validation.get("blockers", [])))
    rule_validation = validate_canonical_rule_record(rule_copy, require_active=True)
    if not rule_validation["valid"]:
        blockers.extend(list(rule_validation.get("blockers", [])))
    if not isinstance(cert_copy, Mapping):
        blockers.append("certification_missing")
    else:
        if str(cert_copy.get("certification_status") or "") != "completed":
            blockers.append("certification_not_completed")
        if str(cert_copy.get("rule_id") or "") != str(rule_copy.get("rule_id") or ""):
            blockers.append("certification_rule_id_mismatch")
        if str(cert_copy.get("document_id") or "") != str(rule_copy.get("document_id") or ""):
            blockers.append("certification_document_id_mismatch")
        if str(cert_copy.get("source_revision") or "") != str(rule_copy.get("source_revision") or ""):
            blockers.append("certification_source_revision_mismatch")
        if str(cert_copy.get("rule_hash") or "") != str(rule_validation.get("rule_fingerprint") or ""):
            blockers.append("certification_rule_fingerprint_mismatch")
    if not isinstance(source_copy, Mapping):
        blockers.append("source_context_invalid")
    else:
        if str(source_copy.get("document_id") or "") != str(rule_copy.get("document_id") or ""):
            blockers.append("source_context_document_id_mismatch")
        if str(source_copy.get("source_revision") or "") != str(rule_copy.get("source_revision") or ""):
            blockers.append("source_context_source_revision_mismatch")
        if str(source_copy.get("current_source_revision") or "") != str(rule_copy.get("source_revision") or ""):
            blockers.append("source_revision_not_current")
        if str(source_copy.get("rule_fingerprint") or "") != str(rule_validation.get("rule_fingerprint") or ""):
            blockers.append("source_context_rule_fingerprint_mismatch")
    return {
        "status": "compatible" if not blockers else "blocked",
        "valid": not blockers,
        "canonical_rule_id": rule_copy.get("rule_id"),
        "document_id": rule_copy.get("document_id"),
        "source_revision": rule_copy.get("source_revision"),
        "rule_fingerprint": rule_validation.get("rule_fingerprint"),
        "certification_fingerprint": _fingerprint_certification(cert_copy) if isinstance(cert_copy, Mapping) else None,
        "fast_lane_capability_fingerprint": get_fast_lane_capability_fingerprint(manifest_copy) if manifest_validation["valid"] else None,
        "warnings": warnings,
        "blockers": _dedupe(blockers),
    }


def evaluate_certified_rule_fast_lane_compatibility(
    canonical_rule: dict,
    certification: dict,
    source_context: dict,
    capability_manifest: dict,
) -> dict:
    rule_copy = deepcopy(canonical_rule)
    cert_copy = deepcopy(certification)
    source_copy = deepcopy(source_context)
    manifest_copy = deepcopy(capability_manifest)
    validation = validate_certified_rule_fast_lane_inputs(rule_copy, cert_copy, source_copy, manifest_copy)
    rule_validation = validate_canonical_rule_record(rule_copy, require_active=True)
    capability_fingerprint = get_fast_lane_capability_fingerprint(manifest_copy) if validate_fast_lane_capability_manifest(manifest_copy)["valid"] else None
    dimension_results = []
    condition = dict(rule_copy.get("condition") or {}) if isinstance(rule_copy.get("condition"), Mapping) else {}
    lifecycle_blockers = []
    if "canonical_rule_not_active" in validation.get("blockers", []):
        lifecycle_blockers.append("canonical_rule_not_active")
    if "certification_not_completed" in validation.get("blockers", []):
        lifecycle_blockers.append("certification_not_completed")
    dimension_results.append(_dimension("lifecycle", "blocked" if lifecycle_blockers else "compatible", [], [], lifecycle_blockers, []))
    provenance_blockers = [item for item in validation.get("blockers", []) if item.startswith("source_") or item.startswith("certification_")]
    dimension_results.append(_dimension("provenance", "blocked" if provenance_blockers else "compatible", [], [], provenance_blockers, []))
    rule_schema_supported = str(rule_copy.get("schema_version") or CANONICAL_RULE_SCHEMA_VERSION) in list(manifest_copy.get("supported_rule_schema_versions") or [])
    dimension_results.append(_dimension("rule_schema", "compatible" if rule_schema_supported else "incompatible", [str(rule_copy.get("schema_version") or CANONICAL_RULE_SCHEMA_VERSION)] if rule_schema_supported else [], [str(rule_copy.get("schema_version") or CANONICAL_RULE_SCHEMA_VERSION)] if not rule_schema_supported else [], ["unsupported_rule_schema"] if not rule_schema_supported else [], []))
    structure_status, structure_blockers, structure_warnings = _condition_structure_status(condition)
    dimension_results.append(_dimension("condition_structure", structure_status, ["single_condition_mapping"] if structure_status == "compatible" else [], ["nested_or_ambiguous_condition"] if structure_status != "compatible" else [], structure_blockers, structure_warnings))
    operator = str(condition.get("operator") or rule_copy.get("operator") or "")
    supported_operators = list(manifest_copy.get("supported_condition_operators") or [])
    op_supported = operator in supported_operators
    dimension_results.append(_dimension("condition_operators", "compatible" if op_supported else "incompatible", [operator] if op_supported else [], [operator] if not op_supported else [], ["unsupported_condition_operator"] if not op_supported else [], []))
    field = str(condition.get("field") or "")
    supported_fields = list(manifest_copy.get("supported_input_fields") or [])
    field_supported = field in supported_fields
    dimension_results.append(_dimension("input_fields", "compatible" if field_supported else "incompatible", [field] if field_supported else [], [field] if not field_supported else [], ["unsupported_input_field"] if not field_supported else [], []))
    field_types = dict(manifest_copy.get("value_types_by_field") or {})
    value_type = _canonical_value_type(condition.get("value"))
    allowed_types = list(field_types.get(field) or [])
    type_supported = _value_type_supported(value_type, allowed_types)
    dimension_results.append(_dimension("value_types", "compatible" if type_supported else "incompatible", [value_type] if type_supported else [], [value_type] if not type_supported else [], ["unsupported_value_type"] if not type_supported else [], []))
    action_status, supported_actions, unsupported_actions, action_blockers = _action_compatibility(rule_copy, manifest_copy)
    dimension_results.append(_dimension("action_or_output_type", action_status, supported_actions, unsupported_actions, action_blockers, []))
    dimension_results.append(_dimension("determinism", "compatible" if manifest_copy.get("deterministic") is True else "blocked", ["deterministic"] if manifest_copy.get("deterministic") is True else [], [] if manifest_copy.get("deterministic") is True else ["non_deterministic"], ["fast_lane_not_deterministic"] if manifest_copy.get("deterministic") is not True else [], []))
    dimension_results.append(_dimension("read_only_support", "compatible" if manifest_copy.get("supports_read_only_evaluation") is True else "blocked", ["read_only"] if manifest_copy.get("supports_read_only_evaluation") is True else [], [] if manifest_copy.get("supports_read_only_evaluation") is True else ["read_only_missing"], ["fast_lane_read_only_boundary_missing"] if manifest_copy.get("supports_read_only_evaluation") is not True else [], []))
    semantic_loss = _semantic_loss(dimension_results)
    blockers = _dedupe(list(validation.get("blockers", [])) + [item for result in dimension_results for item in result["blockers"]])
    warnings = _dedupe([item for result in dimension_results for item in result["warnings"]])
    overall_status = _overall_status(validation, dimension_results, semantic_loss)
    supported_operator_list = sorted({item for result in dimension_results if result["dimension"] == "condition_operators" for item in result["supported_items"]})
    unsupported_operator_list = sorted({item for result in dimension_results if result["dimension"] == "condition_operators" for item in result["unsupported_items"]})
    supported_field_list = sorted({item for result in dimension_results if result["dimension"] == "input_fields" for item in result["supported_items"]})
    unsupported_field_list = sorted({item for result in dimension_results if result["dimension"] == "input_fields" for item in result["unsupported_items"]})
    supported_action_list = sorted({item for result in dimension_results if result["dimension"] == "action_or_output_type" for item in result["supported_items"]})
    unsupported_action_list = sorted({item for result in dimension_results if result["dimension"] == "action_or_output_type" for item in result["unsupported_items"]})
    result = {
        "schema_version": COMPATIBILITY_RESULT_SCHEMA,
        "canonical_rule_id": rule_copy.get("rule_id"),
        "document_id": rule_copy.get("document_id"),
        "source_revision": rule_copy.get("source_revision"),
        "rule_fingerprint": rule_validation.get("rule_fingerprint"),
        "certification_fingerprint": _fingerprint_certification(cert_copy) if isinstance(cert_copy, Mapping) else None,
        "certification_status": cert_copy.get("certification_status") if isinstance(cert_copy, Mapping) else "missing",
        "fast_lane_contract_id": manifest_copy.get("fast_lane_contract_id"),
        "fast_lane_contract_version": manifest_copy.get("fast_lane_contract_version"),
        "fast_lane_capability_fingerprint": capability_fingerprint,
        "compatibility_evaluator_fingerprint": get_fast_lane_compatibility_evaluator_fingerprint(),
        "dimension_results": dimension_results,
        "supported_operators": supported_operator_list,
        "unsupported_operators": unsupported_operator_list,
        "supported_input_fields": supported_field_list,
        "unsupported_input_fields": unsupported_field_list,
        "supported_actions": supported_action_list,
        "unsupported_actions": unsupported_action_list,
        "semantic_loss": semantic_loss,
        "overall_status": overall_status,
        "blockers": blockers,
        "warnings": warnings,
        "result_fingerprint": None,
    }
    result["result_fingerprint"] = _hash_payload(
        {
            "schema_version": COMPATIBILITY_RESULT_SCHEMA,
            "canonical_rule_id": result["canonical_rule_id"],
            "document_id": result["document_id"],
            "source_revision": result["source_revision"],
            "rule_fingerprint": result["rule_fingerprint"],
            "certification_fingerprint": result["certification_fingerprint"],
            "fast_lane_contract_id": result["fast_lane_contract_id"],
            "fast_lane_contract_version": result["fast_lane_contract_version"],
            "fast_lane_capability_fingerprint": result["fast_lane_capability_fingerprint"],
            "compatibility_evaluator_fingerprint": result["compatibility_evaluator_fingerprint"],
            "dimension_results": result["dimension_results"],
            "supported_operators": result["supported_operators"],
            "unsupported_operators": result["unsupported_operators"],
            "supported_input_fields": result["supported_input_fields"],
            "unsupported_input_fields": result["unsupported_input_fields"],
            "supported_actions": result["supported_actions"],
            "unsupported_actions": result["unsupported_actions"],
            "semantic_loss": result["semantic_loss"],
            "overall_status": result["overall_status"],
            "blockers": result["blockers"],
            "warnings": result["warnings"],
        }
    )
    return result


def get_fast_lane_compatibility_evaluator_fingerprint() -> str:
    return _hash_payload(
        {
            "schema_version": COMPATIBILITY_EVALUATOR_SCHEMA,
            "result_schema_version": COMPATIBILITY_RESULT_SCHEMA,
            "dimension_order": DIMENSION_ORDER,
            "dimension_statuses": sorted(ALLOWED_DIMENSION_STATUSES),
            "overall_statuses": sorted(ALLOWED_OVERALL_STATUSES),
            "semantic_loss_statuses": sorted(ALLOWED_SEMANTIC_LOSS),
            "exact_operator_matching": True,
            "exact_field_matching": True,
            "semantic_loss_rule": "confirmed_semantic_loss_blocks_compatible",
            "read_only_validation": True,
        }
    )


def format_fast_lane_compatibility_report(
    compatibility_result: dict,
    public_safe: bool = True,
) -> str:
    result = deepcopy(dict(compatibility_result))
    lines = [
        "Fast Lane Compatibility",
        "",
        f"Canonical Rule ID: {result.get('canonical_rule_id')}",
        f"Document ID: {result.get('document_id')}",
        f"Source Revision: {result.get('source_revision')}",
        f"Certification Status: {result.get('certification_status', 'unknown')}",
        f"Fast Lane Contract: {result.get('fast_lane_contract_id')} v{result.get('fast_lane_contract_version')}",
        f"Overall Compatibility: {result.get('overall_status')}",
        f"Semantic Loss: {result.get('semantic_loss')}",
    ]
    for dimension in list(result.get("dimension_results", []) or []):
        lines.append(f"{dimension.get('dimension')}: {dimension.get('status')}")
    lines.extend(
        [
            f"Supported Operators: {', '.join(result.get('supported_operators', [])) or 'none'}",
            f"Unsupported Operators: {', '.join(result.get('unsupported_operators', [])) or 'none'}",
            f"Supported Fields: {', '.join(result.get('supported_input_fields', [])) or 'none'}",
            f"Unsupported Fields: {', '.join(result.get('unsupported_input_fields', [])) or 'none'}",
            f"Supported Actions: {', '.join(result.get('supported_actions', [])) or 'none'}",
            f"Unsupported Actions: {', '.join(result.get('unsupported_actions', [])) or 'none'}",
            f"Blockers: {', '.join(result.get('blockers', [])) or 'none'}",
            f"Warnings: {', '.join(result.get('warnings', [])) or 'none'}",
            "Execution: Fast Lane was not executed.",
            "Safety: no production state was modified.",
            "Authorization: compatibility does not authorize activation.",
            "Interpretation: partial compatibility is not deployment readiness.",
            f"Recommended Action: {_recommended_action(result)}",
        ]
    )
    if not public_safe:
        lines.append(f"Result Fingerprint: {result.get('result_fingerprint')}")
    return "\n".join(lines)


def _dimension(
    name: str,
    status: str,
    supported_items: list[str],
    unsupported_items: list[str],
    blockers: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "dimension": name,
        "status": status if status in ALLOWED_DIMENSION_STATUSES else "unknown",
        "supported_items": list(supported_items),
        "unsupported_items": list(unsupported_items),
        "blockers": _dedupe(blockers),
        "warnings": _dedupe(warnings),
    }


def _condition_structure_status(condition: Mapping[str, Any]) -> tuple[str, list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    if not condition:
        blockers.append("condition_required")
        return "blocked", blockers, warnings
    nested_keys = [key for key in ("all", "any", "conditions", "or", "and") if key in condition]
    if nested_keys:
        blockers.append("nested_condition_structure_unsupported")
        return "incompatible", blockers, warnings
    if not isinstance(condition.get("field"), str) or not condition.get("field"):
        blockers.append("condition_field_required")
    if not isinstance(condition.get("operator"), str) or not condition.get("operator"):
        blockers.append("condition_operator_required")
    if condition.get("value") is None:
        blockers.append("condition_value_required")
    return ("blocked" if blockers else "compatible"), blockers, warnings


def _canonical_value_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "timestamp" if "T" in value and ":" in value else "string"
    if isinstance(value, list):
        return "list"
    if isinstance(value, tuple):
        return "range" if len(value) == 2 else "tuple"
    return type(value).__name__


def _value_type_supported(value_type: str, allowed_types: list[str]) -> bool:
    if value_type == "boolean":
        return "boolean" in allowed_types
    if value_type == "integer":
        return "integer" in allowed_types or "number" in allowed_types
    if value_type == "number":
        return "number" in allowed_types
    if value_type == "timestamp":
        return "timestamp" in allowed_types or "string" in allowed_types
    if value_type == "string":
        return any(item in allowed_types for item in ("string", "enum:string"))
    if value_type == "list":
        return any(item.startswith("list[") for item in allowed_types)
    return value_type in allowed_types


def _action_compatibility(rule: Mapping[str, Any], manifest: Mapping[str, Any]) -> tuple[str, list[str], list[str], list[str]]:
    target = str(rule.get("target") or "")
    scope = str(rule.get("scope") or "")
    value = rule.get("value")
    blockers: list[str] = []
    supported: list[str] = []
    unsupported: list[str] = []
    if target not in list(manifest.get("supported_action_types") or []):
        blockers.append("unsupported_action_target")
        unsupported.append(target)
    else:
        supported.append(target)
    if scope != "report_output":
        blockers.append("unsupported_action_scope")
        unsupported.append(scope)
    else:
        supported.append(scope)
    supported_values = list((manifest.get("supported_action_values") or {}).get(target) or [])
    if not isinstance(value, str) or value not in supported_values:
        blockers.append("unsupported_action_value")
        unsupported.append(str(value))
    else:
        supported.append(str(value))
    return ("compatible" if not blockers else "incompatible"), supported, unsupported, blockers


def _semantic_loss(dimension_results: list[dict[str, Any]]) -> str:
    for result in dimension_results:
        if result["dimension"] in {"condition_structure", "condition_operators", "input_fields", "value_types", "action_or_output_type"} and result["status"] in {"incompatible", "blocked"}:
            return "confirmed"
    return "none"


def _overall_status(validation: Mapping[str, Any], dimension_results: list[dict[str, Any]], semantic_loss: str) -> str:
    if validation.get("blockers"):
        return "blocked"
    statuses = {result["status"] for result in dimension_results}
    if "blocked" in statuses:
        return "blocked"
    if semantic_loss == "confirmed":
        return "incompatible"
    if "incompatible" in statuses:
        return "partially_compatible"
    if "compatible_with_warning" in statuses or any(result["warnings"] for result in dimension_results):
        return "compatible_with_warnings"
    if statuses == {"compatible"}:
        return "compatible"
    return "unknown"


def _fingerprint_certification(certification: Mapping[str, Any]) -> str:
    return _hash_payload(
        {
            "certification_receipt_id": certification.get("certification_receipt_id"),
            "rule_id": certification.get("rule_id"),
            "document_id": certification.get("document_id"),
            "source_revision": certification.get("source_revision"),
            "rule_hash": certification.get("rule_hash"),
            "certification_status": certification.get("certification_status"),
        }
    )


def _recommended_action(result: Mapping[str, Any]) -> str:
    status = str(result.get("overall_status") or "unknown")
    if status == "compatible":
        return "Phase 9Q preview can consume this compatibility foundation."
    if status == "compatible_with_warnings":
        return "Review warnings before building the later Phase 9Q preview."
    if status == "partially_compatible":
        return "Do not execute Fast Lane; resolve unsupported semantic dimensions first."
    if status == "incompatible":
        return "The rule cannot be represented without semantic loss."
    if status == "blocked":
        return "Resolve lifecycle, provenance, or manifest blockers first."
    return "Compatibility could not be classified reliably."


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in items if str(item)))

