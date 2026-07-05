"""Compatibility wrapper for electional rule imports.

New code should import from backend.electional.engine.rules.
"""

from .engine.rules import *  # noqa: F401,F403

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from .source_documents import SOURCE_DOCUMENT_ROOT
from .source_knowledge import ensure_source_knowledge_dirs

RULE_REPOSITORY_DIR = "rules"
ACTIVE_RULE_INDEX = "active_rule_index.json"
RULE_SCHEMA_VERSION = "canonical_mutable_rule_v1"
ALLOWED_RULE_STATUSES = {"active", "inactive", "rolled_back"}


def ensure_mutable_rule_repository(root: Path | str = SOURCE_DOCUMENT_ROOT) -> Path:
    base = ensure_source_knowledge_dirs(root)
    (base / RULE_REPOSITORY_DIR).mkdir(parents=True, exist_ok=True)
    index_path = base / "indexes" / ACTIVE_RULE_INDEX
    if not index_path.exists():
        _atomic_write_json(index_path, {"entries": [], "updated_at_utc": _now()})
    return base


def load_rule(rule_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any] | None:
    payload = _read_json(_rule_path(ensure_mutable_rule_repository(root), rule_id))
    return payload if isinstance(payload, dict) else None


def list_rules(
    *,
    status: str | None = None,
    active_only: bool = False,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> list[dict[str, Any]]:
    base = ensure_mutable_rule_repository(root)
    items: list[dict[str, Any]] = []
    for path in sorted((base / RULE_REPOSITORY_DIR).glob("*.json")):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        item_status = str(payload.get("status") or "")
        if active_only and item_status != "active":
            continue
        if status is not None and item_status != status:
            continue
        items.append(payload)
    return items


def validate_mutable_rule_record(payload: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    if str(payload.get("rule_id") or "").strip() == "":
        blockers.append("rule_id_required")
    if str(payload.get("rule_type") or "").strip() == "":
        blockers.append("unsupported_rule_type")
    if str(payload.get("target") or "").strip() == "":
        blockers.append("unsupported_target")
    if str(payload.get("scope") or "").strip() == "":
        blockers.append("unsupported_scope")
    if str(payload.get("operator") or "").strip() == "":
        blockers.append("unsupported_operator")
    status = str(payload.get("status") or "active")
    if status not in ALLOWED_RULE_STATUSES:
        blockers.append("unsupported_rule_status")
    condition = payload.get("condition")
    if not isinstance(condition, Mapping):
        blockers.append("condition_required")
    else:
        if str(condition.get("field") or "").strip() == "":
            blockers.append("condition_field_required")
        if str(condition.get("operator") or "").strip() == "":
            blockers.append("condition_operator_required")
        if condition.get("value") is None:
            blockers.append("condition_value_required")
    priority = payload.get("priority")
    if isinstance(priority, bool) or not isinstance(priority, int) or not (0 <= priority <= 100):
        blockers.append("priority_out_of_range")
    enabled = payload.get("enabled")
    if not isinstance(enabled, bool):
        blockers.append("enabled_flag_required")
    return blockers


def save_rule(
    payload: Mapping[str, Any],
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = ensure_mutable_rule_repository(root)
    normalized = dict(payload)
    normalized.setdefault("schema_version", RULE_SCHEMA_VERSION)
    normalized.setdefault("created_at_utc", _now())
    normalized["updated_at_utc"] = _now()
    blockers = validate_mutable_rule_record(normalized)
    if blockers:
        raise ValueError(",".join(blockers))
    path = _rule_path(base, str(normalized.get("rule_id")))
    existing = _read_json(path)
    if isinstance(existing, dict):
        if _stable_rule_payload(existing) == _stable_rule_payload(normalized):
            return existing
        raise ValueError("conflicting_rule_record")
    before_index = _read_json(base / "indexes" / ACTIVE_RULE_INDEX)
    try:
        _atomic_write_json(path, normalized)
        _update_active_rule_index(base)
    except Exception:
        _restore_json(path, existing)
        _restore_json(base / "indexes" / ACTIVE_RULE_INDEX, before_index)
        raise
    return normalized


def update_rule(rule_id: str, updates: Mapping[str, Any], *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = ensure_mutable_rule_repository(root)
    existing = load_rule(rule_id, root=base)
    if existing is None:
        raise FileNotFoundError(rule_id)
    updated = dict(existing)
    updated.update(dict(updates))
    updated["rule_id"] = rule_id
    updated["updated_at_utc"] = _now()
    blockers = validate_mutable_rule_record(updated)
    if blockers:
        raise ValueError(",".join(blockers))
    path = _rule_path(base, rule_id)
    before_index = _read_json(base / "indexes" / ACTIVE_RULE_INDEX)
    try:
        _atomic_write_json(path, updated)
        _update_active_rule_index(base)
    except Exception:
        _restore_json(path, existing)
        _restore_json(base / "indexes" / ACTIVE_RULE_INDEX, before_index)
        raise
    return updated


def active_rule_index_state(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = ensure_mutable_rule_repository(root)
    index_payload = _read_json(base / "indexes" / ACTIVE_RULE_INDEX)
    return index_payload if isinstance(index_payload, dict) else {"entries": [], "updated_at_utc": _now()}


def active_rule_index_hash(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> str:
    return _hash_payload(active_rule_index_state(root=root))


def _update_active_rule_index(root: Path) -> None:
    entries = []
    for item in list_rules(root=root, active_only=True):
        entries.append(
            {
                "rule_id": item.get("rule_id"),
                "rule_type": item.get("rule_type"),
                "target": item.get("target"),
                "scope": item.get("scope"),
                "priority": item.get("priority"),
                "updated_at_utc": item.get("updated_at_utc"),
            }
        )
    _atomic_write_json(root / "indexes" / ACTIVE_RULE_INDEX, {"entries": entries, "updated_at_utc": _now()})


def _rule_path(root: Path, rule_id: str) -> Path:
    return root / RULE_REPOSITORY_DIR / f"{_safe_id(rule_id)}.json"


def _stable_rule_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "rule_id": payload.get("rule_id"),
        "rule_type": payload.get("rule_type"),
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
