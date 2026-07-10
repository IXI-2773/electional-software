"""Canonical mutable rule storage and pure single-rule runtime evaluation."""

from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from .source_documents import SOURCE_DOCUMENT_ROOT
from .source_knowledge import ensure_source_knowledge_dirs

CANONICAL_RULE_DIR = "canonical_rules"
CANONICAL_RULE_INDEX = "canonical_rule_index.json"
CANONICAL_RULE_SCHEMA_VERSION = "canonical_mutable_rule_v1"
CANONICAL_RULE_INDEX_SCHEMA_VERSION = "canonical_rule_index_v1"
CANONICAL_EVALUATION_SCHEMA_VERSION = "canonical_single_rule_evaluation_v1"
SUPPORTED_OPERATORS = [
    "equals",
    "not_equals",
    "greater_than",
    "greater_than_or_equal",
    "less_than",
    "less_than_or_equal",
    "between",
    "in",
    "contains",
]
ALLOWED_RULE_STATUSES = {"active", "inactive", "rolled_back"}


def get_canonical_rule_runtime_capability(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    try:
        base = _ensure_runtime_dirs(root)
        index = _load_index(base)
    except Exception:
        return {
            "available": False,
            "repository_available": False,
            "active_index_available": False,
            "single_rule_evaluator_available": False,
            "supported_operators": list(SUPPORTED_OPERATORS),
            "warnings": ["canonical_rule_runtime_unavailable"],
        }
    return {
        "available": True,
        "repository_available": (base / CANONICAL_RULE_DIR).exists(),
        "active_index_available": isinstance(index, dict) and index.get("schema_version") == CANONICAL_RULE_INDEX_SCHEMA_VERSION,
        "single_rule_evaluator_available": callable(evaluate_canonical_rule),
        "supported_operators": list(SUPPORTED_OPERATORS),
        "warnings": [],
    }


def validate_canonical_rule_record(rule: dict, require_active: bool = False) -> dict:
    blockers: list[str] = []
    if not isinstance(rule, Mapping):
        return {"valid": False, "rule_id": None, "status": None, "operator": None, "rule_fingerprint": None, "warnings": [], "blockers": ["rule_record_invalid"]}
    payload = deepcopy(dict(rule))
    rule_id = _non_empty_text(payload.get("rule_id"))
    if rule_id is None:
        blockers.append("rule_id_required")
    schema_version = _non_empty_text(payload.get("schema_version"))
    if schema_version not in {CANONICAL_RULE_SCHEMA_VERSION, None}:
        blockers.append("unsupported_rule_schema_version")
    rule_type = _non_empty_text(payload.get("rule_type") or payload.get("rule_family"))
    if rule_type is None:
        blockers.append("unsupported_rule_type")
    if _non_empty_text(payload.get("target")) is None:
        blockers.append("unsupported_target")
    if _non_empty_text(payload.get("scope")) is None:
        blockers.append("unsupported_scope")
    operator = _non_empty_text(payload.get("operator"))
    if operator is None:
        blockers.append("unsupported_operator")
    elif operator not in SUPPORTED_OPERATORS:
        blockers.append("canonical_rule_operator_unsupported")
    status = _non_empty_text(payload.get("status") or ("active" if payload.get("enabled") is True else "inactive"))
    if status not in ALLOWED_RULE_STATUSES:
        blockers.append("unsupported_rule_status")
    if require_active and status != "active":
        blockers.append("canonical_rule_not_active")
    condition = payload.get("condition")
    if not isinstance(condition, Mapping):
        blockers.append("condition_required")
    else:
        if _non_empty_text(condition.get("field")) is None:
            blockers.append("condition_field_required")
        condition_operator = _non_empty_text(condition.get("operator"))
        if condition_operator is None:
            blockers.append("condition_operator_required")
        elif condition_operator not in SUPPORTED_OPERATORS:
            blockers.append("canonical_rule_operator_unsupported")
        if condition.get("value") is None:
            blockers.append("condition_value_required")
    if payload.get("value") is None:
        blockers.append("condition_value_required")
    if isinstance(payload.get("priority"), bool) or not isinstance(payload.get("priority"), int):
        blockers.append("priority_out_of_range")
    if not isinstance(payload.get("enabled"), bool):
        blockers.append("enabled_flag_required")
    if _non_empty_text(payload.get("source_proposal_id")) is None:
        blockers.append("source_proposal_id_required")
    if _non_empty_text(payload.get("source_revision")) is None:
        blockers.append("source_revision_required")
    fingerprint = _rule_fingerprint_from_payload(payload) if not blockers else None
    if payload.get("rule_fingerprint") is not None and payload.get("rule_fingerprint") != fingerprint:
        blockers.append("rule_fingerprint_mismatch")
    return {
        "valid": not blockers,
        "rule_id": rule_id,
        "status": status,
        "operator": operator,
        "rule_fingerprint": fingerprint,
        "warnings": [],
        "blockers": list(dict.fromkeys(blockers)),
    }


def create_canonical_rule(rule: dict, confirmation: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    if confirmation != "CREATE_RULE":
        return {"status": "blocked", "blockers": ["create_rule_confirmation_required"], "warnings": []}
    base = _ensure_runtime_dirs(root)
    validation = validate_canonical_rule_record(rule, require_active=True)
    if not validation["valid"]:
        return {"status": "blocked", "rule_id": validation.get("rule_id"), "blockers": list(validation.get("blockers", [])), "warnings": []}
    payload = _prepare_rule_record(rule, existing=None)
    rule_id = str(payload["rule_id"])
    record_path = _rule_path(base, rule_id)
    existing = _read_json(record_path)
    if isinstance(existing, dict):
        existing_validation = validate_canonical_rule_record(existing)
        if existing_validation.get("rule_fingerprint") == payload["rule_fingerprint"] and str(existing.get("status") or "") == "active":
            return {"status": "already_created", "rule_id": rule_id, "writes_performed": 0}
        return {"status": "blocked", "rule_id": rule_id, "blockers": ["rule_id_content_conflict"], "warnings": []}
    before_index = _load_index(base)
    after_index = _index_with_rule(before_index, payload)
    try:
        _atomic_write_json(record_path, payload)
        _atomic_write_json(_index_path(base), after_index)
    except Exception:
        _restore_json(record_path, existing)
        _restore_json(_index_path(base), before_index)
        return {"status": "failed_rolled_back", "rule_id": rule_id, "rule_status": payload["status"], "rule_fingerprint": payload["rule_fingerprint"], "active_index_updated": False, "warnings": []}
    return {"status": "created", "rule_id": rule_id, "rule_status": payload["status"], "rule_fingerprint": payload["rule_fingerprint"], "active_index_updated": True, "warnings": []}


def load_canonical_rule(rule_id: str, require_active: bool = False, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = _ensure_runtime_dirs(root)
    payload = _read_json(_rule_path(base, rule_id))
    if not isinstance(payload, dict):
        return {"status": "not_found", "rule_id": rule_id, "warnings": [], "blockers": ["canonical_rule_not_found"]}
    validation = validate_canonical_rule_record(payload, require_active=require_active)
    if not validation["valid"]:
        return {"status": "blocked", "rule_id": rule_id, "rule_status": payload.get("status"), "rule": payload, "warnings": [], "blockers": list(validation.get("blockers", []))}
    index = _load_index(base)
    indexed_ids = set(index.get("rule_ids", []))
    active_ids = set(index.get("active_rule_ids", []))
    blockers: list[str] = []
    if rule_id not in indexed_ids:
        blockers.append("canonical_rule_index_missing_rule")
    if (rule_id in active_ids) != (str(payload.get("status") or "") == "active"):
        blockers.append("canonical_rule_state_diverged")
    if blockers:
        return {"status": "blocked", "rule_id": rule_id, "rule_status": payload.get("status"), "rule": payload, "warnings": [], "blockers": blockers}
    return {"status": "loaded", "rule_id": rule_id, "rule_status": payload.get("status"), "rule": payload, "warnings": []}


def list_canonical_rules(
    status: str | None = None,
    rule_type: str | None = None,
    target: str | None = None,
    limit: int = 100,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_runtime_dirs(root)
    if status is not None and status not in ALLOWED_RULE_STATUSES:
        return {"status": "blocked", "items": [], "count": 0, "warnings": [], "blockers": ["unsupported_rule_status_filter"]}
    items: list[dict[str, Any]] = []
    for path in sorted((base / CANONICAL_RULE_DIR).glob("*.json")):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        if status is not None and str(payload.get("status") or "") != status:
            continue
        if rule_type is not None and str(payload.get("rule_type") or payload.get("rule_family") or "") != rule_type:
            continue
        if target is not None and str(payload.get("target") or "") != target:
            continue
        items.append(payload)
    items.sort(key=lambda item: (str(item.get("status") or ""), str(item.get("rule_type") or item.get("rule_family") or ""), str(item.get("target") or ""), str(item.get("rule_id") or "")))
    capped = items[: max(0, int(limit))]
    return {"status": "listed", "count": len(capped), "items": capped, "warnings": []}


def deactivate_canonical_rule(rule_id: str, reason: str, confirmation: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    if confirmation != "DEACTIVATE_RULE":
        return {"status": "blocked", "rule_id": rule_id, "blockers": ["deactivate_rule_confirmation_required"], "warnings": []}
    if _non_empty_text(reason) is None:
        return {"status": "blocked", "rule_id": rule_id, "blockers": ["deactivation_reason_required"], "warnings": []}
    base = _ensure_runtime_dirs(root)
    loaded = load_canonical_rule(rule_id, root=base)
    if loaded.get("status") != "loaded":
        return loaded
    rule = deepcopy(dict(loaded["rule"]))
    index = _load_index(base)
    active_ids = set(index.get("active_rule_ids", []))
    if str(rule.get("status") or "") == "rolled_back" and rule_id not in active_ids:
        return {"status": "already_deactivated", "rule_id": rule_id, "writes_performed": 0}
    if str(rule.get("status") or "") != "active" or rule_id not in active_ids:
        return {"status": "blocked", "rule_id": rule_id, "blockers": ["canonical_rule_state_diverged"], "warnings": []}
    updated = deepcopy(rule)
    updated["status"] = "rolled_back"
    updated["enabled"] = False
    updated["deactivated_at_utc"] = _now()
    updated["deactivation_reason"] = str(reason).strip()
    updated["previous_active_fingerprint"] = str(rule.get("rule_fingerprint") or "")
    updated["updated_at_utc"] = _now()
    updated["rule_fingerprint"] = _rule_fingerprint_from_payload(updated)
    before_index = _load_index(base)
    after_index = _index_with_rule(before_index, updated)
    record_path = _rule_path(base, rule_id)
    try:
        _atomic_write_json(record_path, updated)
        _atomic_write_json(_index_path(base), after_index)
    except Exception:
        _restore_json(record_path, rule)
        _restore_json(_index_path(base), before_index)
        return {"status": "failed_rolled_back", "rule_id": rule_id, "rule_status": "rolled_back", "removed_from_active_index": False, "warnings": []}
    return {"status": "deactivated", "rule_id": rule_id, "rule_status": "rolled_back", "removed_from_active_index": True, "warnings": []}


def evaluate_canonical_rule(rule_or_id: dict | str, context: dict, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    if not isinstance(context, Mapping):
        return _evaluation_result(None, None, None, "blocked", None, blockers=["evaluation_context_invalid"])
    loaded = load_canonical_rule(str(rule_or_id), root=root) if isinstance(rule_or_id, str) else {"status": "loaded", "rule": deepcopy(rule_or_id), "rule_id": (rule_or_id or {}).get("rule_id"), "rule_status": (rule_or_id or {}).get("status")}
    if loaded.get("status") != "loaded":
        return _evaluation_result(str(loaded.get("rule_id") or ""), str(loaded.get("rule_status") or ""), None, "blocked", None, blockers=list(loaded.get("blockers", [])))
    validation = validate_canonical_rule_record(dict(loaded["rule"]))
    if not validation["valid"]:
        return _evaluation_result(str(validation.get("rule_id") or ""), str(validation.get("status") or ""), str(validation.get("operator") or ""), "blocked", None, blockers=list(validation.get("blockers", [])))
    rule = deepcopy(dict(loaded["rule"]))
    condition = deepcopy(dict(rule.get("condition") or {}))
    field = str(condition.get("field"))
    operator = str(condition.get("operator") or rule.get("operator"))
    expected = deepcopy(condition.get("value"))
    actual = deepcopy(dict(context)).get(field)
    if operator not in SUPPORTED_OPERATORS:
        return _evaluation_result(str(rule.get("rule_id") or ""), str(rule.get("status") or ""), operator, "unsupported", field, blockers=["canonical_rule_operator_unsupported"])
    try:
        matched = _evaluate_operator(operator, actual, expected)
    except TypeError:
        return _evaluation_result(str(rule.get("rule_id") or ""), str(rule.get("status") or ""), operator, "error", field, blockers=["canonical_rule_comparison_invalid"])
    return _evaluation_result(str(rule.get("rule_id") or ""), str(rule.get("status") or ""), operator, "matched" if matched else "not_matched", field, matched)


def get_canonical_rule_runtime_health(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    try:
        base = _ensure_runtime_dirs(root)
        index = _load_index(base)
    except Exception:
        return {"status": "unknown", "rule_count": 0, "active_rule_count": 0, "inactive_rule_count": 0, "rolled_back_rule_count": 0, "fingerprint_mismatch_count": 0, "orphan_rule_count": 0, "unsupported_active_operator_count": 0, "warnings": ["canonical_rule_runtime_unavailable"], "recommended_action": "Inspect canonical rule runtime storage."}
    rules = []
    fingerprint_mismatch_count = 0
    unsupported_active_operator_count = 0
    for path in sorted((base / CANONICAL_RULE_DIR).glob("*.json")):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        rules.append(payload)
        validation = validate_canonical_rule_record(payload)
        if "rule_fingerprint_mismatch" in validation.get("blockers", []):
            fingerprint_mismatch_count += 1
        if payload.get("status") == "active" and str(payload.get("operator") or "") not in SUPPORTED_OPERATORS:
            unsupported_active_operator_count += 1
    indexed_rule_ids = set(index.get("rule_ids", []))
    record_rule_ids = {str(item.get("rule_id") or "") for item in rules}
    orphan_rule_count = len(indexed_rule_ids - record_rule_ids)
    if not rules:
        status = "empty"
    elif fingerprint_mismatch_count or unsupported_active_operator_count:
        status = "blocked"
    elif orphan_rule_count:
        status = "warning"
    else:
        status = "healthy"
    return {
        "status": status,
        "rule_count": len(rules),
        "active_rule_count": sum(1 for item in rules if item.get("status") == "active"),
        "inactive_rule_count": sum(1 for item in rules if item.get("status") == "inactive"),
        "rolled_back_rule_count": sum(1 for item in rules if item.get("status") == "rolled_back"),
        "fingerprint_mismatch_count": fingerprint_mismatch_count,
        "orphan_rule_count": orphan_rule_count,
        "unsupported_active_operator_count": unsupported_active_operator_count,
        "warnings": [],
        "recommended_action": None if status == "healthy" else "Inspect canonical rule/index agreement before relying on activation state.",
    }


def _ensure_runtime_dirs(root: Path | str) -> Path:
    base = ensure_source_knowledge_dirs(root)
    (base / CANONICAL_RULE_DIR).mkdir(parents=True, exist_ok=True)
    if not _index_path(base).exists():
        _atomic_write_json(_index_path(base), _empty_index())
    return base


def _prepare_rule_record(rule: Mapping[str, Any], existing: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = deepcopy(dict(rule))
    payload["schema_version"] = CANONICAL_RULE_SCHEMA_VERSION
    payload["rule_id"] = str(payload.get("rule_id") or "").strip()
    payload["rule_type"] = str(payload.get("rule_type") or payload.get("rule_family") or "").strip()
    payload["target"] = str(payload.get("target") or "").strip()
    payload["scope"] = str(payload.get("scope") or "").strip()
    payload["operator"] = str(payload.get("operator") or "").strip()
    payload["condition"] = deepcopy(dict(payload.get("condition") or {}))
    payload["condition"]["field"] = str(payload["condition"].get("field") or "").strip()
    payload["condition"]["operator"] = str(payload["condition"].get("operator") or payload["operator"]).strip()
    payload["status"] = str(payload.get("status") or "active").strip()
    payload["created_at_utc"] = (existing or {}).get("created_at_utc") or _now()
    payload["updated_at_utc"] = _now()
    payload["rule_fingerprint"] = _rule_fingerprint_from_payload(payload)
    return payload


def _index_path(base: Path) -> Path:
    return base / "indexes" / CANONICAL_RULE_INDEX


def _rule_path(base: Path, rule_id: str) -> Path:
    return base / CANONICAL_RULE_DIR / f"{_safe_id(rule_id)}.json"


def _empty_index() -> dict[str, Any]:
    return {
        "schema_version": CANONICAL_RULE_INDEX_SCHEMA_VERSION,
        "rule_ids": [],
        "active_rule_ids": [],
        "rule_fingerprints": {},
        "updated_at_utc": _now(),
    }


def _load_index(base: Path) -> dict[str, Any]:
    payload = _read_json(_index_path(base))
    if not isinstance(payload, dict):
        return _empty_index()
    payload.setdefault("schema_version", CANONICAL_RULE_INDEX_SCHEMA_VERSION)
    payload.setdefault("rule_ids", [])
    payload.setdefault("active_rule_ids", [])
    payload.setdefault("rule_fingerprints", {})
    payload.setdefault("updated_at_utc", _now())
    return payload


def _index_with_rule(index: Mapping[str, Any], rule: Mapping[str, Any]) -> dict[str, Any]:
    rule_id = str(rule.get("rule_id") or "")
    rule_ids = sorted({str(item) for item in index.get("rule_ids", [])} | {rule_id})
    active_ids = {str(item) for item in index.get("active_rule_ids", [])}
    if str(rule.get("status") or "") == "active":
        active_ids.add(rule_id)
    else:
        active_ids.discard(rule_id)
    fingerprints = {str(key): str(value) for key, value in dict(index.get("rule_fingerprints", {})).items()}
    fingerprints[rule_id] = str(rule.get("rule_fingerprint") or "")
    return {
        "schema_version": CANONICAL_RULE_INDEX_SCHEMA_VERSION,
        "rule_ids": rule_ids,
        "active_rule_ids": sorted(active_ids),
        "rule_fingerprints": fingerprints,
        "updated_at_utc": _now(),
    }


def _rule_fingerprint_from_payload(payload: Mapping[str, Any]) -> str:
    return _hash_payload(
        {
            "schema_version": CANONICAL_RULE_SCHEMA_VERSION,
            "rule_id": payload.get("rule_id"),
            "rule_type": payload.get("rule_type") or payload.get("rule_family"),
            "target": payload.get("target"),
            "scope": payload.get("scope"),
            "condition": payload.get("condition"),
            "operator": payload.get("operator"),
            "value": payload.get("value"),
            "priority": payload.get("priority"),
            "enabled": payload.get("enabled"),
            "status": payload.get("status"),
            "source_proposal_id": payload.get("source_proposal_id"),
            "source_promotion_receipt_id": payload.get("source_promotion_receipt_id"),
            "source_rule_activation_review_id": payload.get("source_rule_activation_review_id"),
            "source_revision": payload.get("source_revision"),
            "activation_receipt_id": payload.get("activation_receipt_id"),
        }
    )


def _evaluate_operator(operator: str, actual: Any, expected: Any) -> bool:
    if actual is None:
        return False
    if operator == "equals":
        return actual == expected
    if operator == "not_equals":
        return actual != expected
    if operator == "greater_than":
        _require_comparable(actual, expected)
        return actual > expected
    if operator == "greater_than_or_equal":
        _require_comparable(actual, expected)
        return actual >= expected
    if operator == "less_than":
        _require_comparable(actual, expected)
        return actual < expected
    if operator == "less_than_or_equal":
        _require_comparable(actual, expected)
        return actual <= expected
    if operator == "between":
        if not isinstance(expected, (list, tuple)) or len(expected) != 2:
            raise TypeError("between_requires_two_values")
        lower, upper = expected
        _require_comparable(actual, lower)
        _require_comparable(actual, upper)
        return lower <= actual <= upper
    if operator == "in":
        if not isinstance(expected, (list, tuple, set)):
            raise TypeError("in_requires_collection")
        return actual in expected
    if operator == "contains":
        if not isinstance(actual, (str, list, tuple, set)):
            raise TypeError("contains_requires_collection")
        return expected in actual
    raise TypeError("unsupported_operator")


def _require_comparable(actual: Any, expected: Any) -> None:
    if isinstance(actual, bool) or isinstance(expected, bool) or type(actual) is not type(expected):
        raise TypeError("incompatible_comparison")


def _evaluation_result(
    rule_id: str | None,
    rule_status: str | None,
    operator: str | None,
    result: str,
    evaluated_field: str | None,
    matched: bool | None = None,
    *,
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    normalized_match = matched if result in {"matched", "not_matched"} else None
    if result == "matched":
        normalized_match = True
    elif result == "not_matched":
        normalized_match = False
    return {
        "schema_version": CANONICAL_EVALUATION_SCHEMA_VERSION,
        "rule_id": rule_id,
        "rule_status": rule_status,
        "operator": operator,
        "result": result,
        "matched": normalized_match,
        "evaluated_field": evaluated_field,
        "persistent_writes": 0,
        "warnings": [],
        "blockers": list(blockers or []),
    }


def _non_empty_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(dict(payload), handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            pass
    os.replace(temp_path, path)


def _restore_json(path: Path, payload: Any) -> None:
    if payload is None:
        if path.exists():
            path.unlink()
        return
    _atomic_write_json(path, payload)


def _hash_payload(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"_", "-", "."} else "_" for char in str(value).strip()) or "object"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
