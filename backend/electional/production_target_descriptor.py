"""Read-only production target descriptor foundation."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from .canonical_rule_runtime import _atomic_write_json, _hash_payload, _read_json, _restore_json, _safe_id
from .source_documents import SOURCE_DOCUMENT_ROOT

DESCRIPTOR_DIR = "production_target_descriptors"
DESCRIPTOR_INDEX = "production_target_descriptor_index.json"
DESCRIPTOR_SCHEMA_VERSION = "production_target_descriptor_v1"
MANIFEST_SCHEMA_VERSION = "production_adapter_manifest_v1"
CAPABILITIES_SCHEMA_VERSION = "production_adapter_capabilities_v1"
TARGET_KIND = "intended_production_deployment_target"
ACCESS_MODE = "metadata_only_read_only"
AUTHORIZATION_SCOPE = "later_production_deployment_only"


def validate_production_target_descriptor(descriptor: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    normalized = _normalize_descriptor(descriptor)
    if normalized is None:
        return {
            "valid": False,
            "status": "blocked",
            "target_id": None,
            "adapter_manifest_fingerprint": None,
            "adapter_capability_fingerprint": None,
            "descriptor_fingerprint": None,
            "warnings": warnings,
            "blockers": ["production_target_descriptor_invalid"],
        }
    if str(normalized.get("schema_version") or "") != DESCRIPTOR_SCHEMA_VERSION:
        blockers.append("production_target_descriptor_schema_unsupported")
    if str(normalized.get("environment_class") or "") != "production":
        blockers.append("production_target_environment_invalid")
    if str(normalized.get("target_kind") or "") != TARGET_KIND:
        blockers.append("production_target_kind_invalid")
    if str(normalized.get("descriptor_access_mode") or "") != ACCESS_MODE:
        blockers.append("production_target_access_mode_invalid")
    if str(normalized.get("authorization_scope") or "") != AUTHORIZATION_SCOPE:
        blockers.append("production_target_authorization_scope_invalid")
    if list(normalized.get("operational_entrypoints_exposed") or []):
        blockers.append("production_target_operational_entrypoints_forbidden")
    for field in (
        "deployment_executed",
        "activation_executed",
        "production_scoring_executed",
        "live_fast_lane_executed",
    ):
        if normalized.get(field) is not False:
            blockers.append(f"{field}_must_be_false")
    manifest = normalized.get("adapter_manifest")
    capabilities = normalized.get("adapter_capabilities")
    if not isinstance(manifest, Mapping):
        blockers.append("production_target_adapter_manifest_missing")
    else:
        if str(manifest.get("schema_version") or "") != MANIFEST_SCHEMA_VERSION:
            blockers.append("production_target_adapter_manifest_schema_invalid")
        if str(manifest.get("adapter_name") or "") != str(normalized.get("adapter_name") or ""):
            blockers.append("production_target_adapter_manifest_name_mismatch")
        if str(manifest.get("adapter_version") or "") != str(normalized.get("adapter_version") or ""):
            blockers.append("production_target_adapter_manifest_version_mismatch")
    if not isinstance(capabilities, Mapping):
        blockers.append("production_target_adapter_capabilities_missing")
    else:
        if str(capabilities.get("schema_version") or "") != CAPABILITIES_SCHEMA_VERSION:
            blockers.append("production_target_adapter_capabilities_schema_invalid")
        if not isinstance(capabilities.get("capabilities"), list):
            blockers.append("production_target_capabilities_list_invalid")
    manifest_fp = _manifest_fingerprint(manifest) if isinstance(manifest, Mapping) else None
    capability_fp = _capability_fingerprint(capabilities) if isinstance(capabilities, Mapping) else None
    descriptor_fp = _descriptor_fingerprint(normalized) if manifest_fp and capability_fp else None
    if str(normalized.get("adapter_manifest_fingerprint") or "") != str(manifest_fp or ""):
        blockers.append("production_target_adapter_manifest_fingerprint_mismatch")
    if str(normalized.get("adapter_capability_fingerprint") or "") != str(capability_fp or ""):
        blockers.append("production_target_adapter_capability_fingerprint_mismatch")
    if str(normalized.get("descriptor_fingerprint") or "") != str(descriptor_fp or ""):
        blockers.append("production_target_descriptor_fingerprint_mismatch")
    return {
        "valid": not blockers,
        "status": "valid" if not blockers else "blocked",
        "target_id": normalized.get("target_id"),
        "adapter_manifest_fingerprint": manifest_fp,
        "adapter_capability_fingerprint": capability_fp,
        "descriptor_fingerprint": descriptor_fp,
        "warnings": warnings,
        "blockers": blockers,
    }


def register_production_target_descriptor(
    descriptor: dict[str, Any],
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = Path(root)
    validation = validate_production_target_descriptor(descriptor)
    if not validation["valid"]:
        return {
            "status": "blocked",
            "target_id": validation.get("target_id"),
            "descriptor_fingerprint": validation.get("descriptor_fingerprint"),
            "writes_performed": 0,
            "warnings": list(validation.get("warnings", [])),
            "blockers": list(validation.get("blockers", [])),
        }
    normalized = _normalize_descriptor(descriptor)
    assert normalized is not None
    target_id = str(normalized["target_id"])
    path = _descriptor_path(base, target_id)
    existing = _read_json(path)
    if isinstance(existing, Mapping):
        existing_validation = validate_production_target_descriptor(dict(existing))
        if str(existing_validation.get("descriptor_fingerprint") or "") == str(validation.get("descriptor_fingerprint") or ""):
            return {
                "status": "registered",
                "target_id": target_id,
                "descriptor_fingerprint": validation.get("descriptor_fingerprint"),
                "writes_performed": 0,
                "warnings": [],
                "blockers": [],
            }
        return {
            "status": "conflict",
            "target_id": target_id,
            "descriptor_fingerprint": validation.get("descriptor_fingerprint"),
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["production_target_descriptor_already_registered_with_different_content"],
        }
    before_descriptor = _read_json(path)
    before_index = _read_json(_index_path(base))
    try:
        _atomic_write_json(path, normalized)
        _atomic_write_json(_index_path(base), _build_index(base))
    except Exception:
        _restore_json(path, before_descriptor)
        _restore_json(_index_path(base), before_index)
        return {
            "status": "corrupt",
            "target_id": target_id,
            "descriptor_fingerprint": validation.get("descriptor_fingerprint"),
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["production_target_descriptor_write_failure"],
        }
    return {
        "status": "registered",
        "target_id": target_id,
        "descriptor_fingerprint": validation.get("descriptor_fingerprint"),
        "writes_performed": 1,
        "warnings": [],
        "blockers": [],
    }


def load_production_target_descriptor(target_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = Path(root)
    payload = _read_json(_descriptor_path(base, target_id))
    if not isinstance(payload, Mapping):
        return {
            "status": "not_found",
            "target_id": target_id,
            "production_target_descriptor": None,
            "warnings": [],
            "blockers": ["production_target_descriptor_not_found"],
        }
    descriptor = dict(payload)
    validation = validate_production_target_descriptor(descriptor)
    return {
        "status": "loaded" if validation["valid"] else "corrupt",
        "target_id": descriptor.get("target_id"),
        "production_target_descriptor": descriptor,
        "warnings": list(validation.get("warnings", [])),
        "blockers": list(validation.get("blockers", [])),
    }


def get_production_target_descriptor_fingerprint(descriptor: dict[str, Any]) -> dict[str, Any]:
    validation = validate_production_target_descriptor(descriptor)
    return {
        "status": "computed" if validation["descriptor_fingerprint"] else "blocked",
        "target_id": validation.get("target_id"),
        "adapter_manifest_fingerprint": validation.get("adapter_manifest_fingerprint"),
        "adapter_capability_fingerprint": validation.get("adapter_capability_fingerprint"),
        "descriptor_fingerprint": validation.get("descriptor_fingerprint"),
        "warnings": list(validation.get("warnings", [])),
        "blockers": list(validation.get("blockers", [])),
    }


def get_production_target_descriptor_health(target_id: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = Path(root)
    items = _load_all_descriptors(base)
    if target_id:
        items = [item for item in items if str(item.get("target_id") or "") == str(target_id)]
    if not items:
        return {
            "status": "empty",
            "descriptor_count": 0,
            "warnings": [],
            "blockers": [],
            "recommended_action": "Register one immutable production target descriptor.",
        }
    warnings: list[str] = []
    blockers: list[str] = []
    seen_ids: set[str] = set()
    for item in items:
        current_id = str(item.get("target_id") or "")
        if current_id in seen_ids:
            blockers.append("duplicate_production_target_descriptor_id")
        seen_ids.add(current_id)
        validation = validate_production_target_descriptor(item)
        blockers.extend(list(validation.get("blockers", [])))
    index = _read_json(_index_path(base))
    indexed_items = list(index.get("items", [])) if isinstance(index, Mapping) else []
    expected_index = _build_index(base)
    if not isinstance(index, Mapping):
        warnings.append("production_target_descriptor_index_missing")
    elif indexed_items != expected_index["items"]:
        warnings.append("production_target_descriptor_index_stale")
    status = "healthy" if not blockers and not warnings else "blocked" if blockers else "warning"
    return {
        "status": status,
        "descriptor_count": len(items),
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
        "recommended_action": "Production target descriptors are metadata-only and ready for later authorization use." if status == "healthy" else "Repair descriptor validation or index consistency before later production authorization.",
    }


def format_production_target_descriptor_report(target_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> str:
    loaded = load_production_target_descriptor(target_id, root=root)
    descriptor = loaded.get("production_target_descriptor") if isinstance(loaded.get("production_target_descriptor"), Mapping) else {}
    lines = [
        "Production Target Descriptor",
        f"Status: {loaded.get('status', 'unknown')}",
        f"Target ID: {descriptor.get('target_id', target_id)}",
        f"Environment Class: {descriptor.get('environment_class', 'unknown')}",
        f"Target Kind: {descriptor.get('target_kind', 'unknown')}",
        f"Adapter Name: {descriptor.get('adapter_name', 'unknown')}",
        f"Adapter Version: {descriptor.get('adapter_version', 'unknown')}",
        f"Descriptor Access Mode: {descriptor.get('descriptor_access_mode', 'unknown')}",
        f"Authorization Scope: {descriptor.get('authorization_scope', 'unknown')}",
        f"Adapter Manifest Fingerprint: {descriptor.get('adapter_manifest_fingerprint', 'unknown')}",
        f"Adapter Capability Fingerprint: {descriptor.get('adapter_capability_fingerprint', 'unknown')}",
        f"Descriptor Fingerprint: {descriptor.get('descriptor_fingerprint', 'unknown')}",
        "This record is local metadata only.",
        "No production target connection was attempted.",
        "No deployment, activation, production scoring, or live Fast Lane execution occurred.",
    ]
    warnings = list(loaded.get("warnings", []))
    blockers = list(loaded.get("blockers", []))
    if warnings:
        lines.append("Warnings: " + ", ".join(str(item) for item in warnings))
    if blockers:
        lines.append("Blockers: " + ", ".join(str(item) for item in blockers))
    return "\n".join(lines)


def _normalize_descriptor(descriptor: Mapping[str, Any]) -> dict[str, Any] | None:
    if not isinstance(descriptor, Mapping):
        return None
    manifest = descriptor.get("adapter_manifest")
    capabilities = descriptor.get("adapter_capabilities")
    if not isinstance(manifest, Mapping) or not isinstance(capabilities, Mapping):
        return None
    target_id = _text(descriptor.get("target_id"))
    adapter_name = _text(descriptor.get("adapter_name"))
    adapter_version = _text(descriptor.get("adapter_version"))
    if target_id is None or adapter_name is None or adapter_version is None:
        return None
    if _safe_id(target_id) != target_id or any(token in target_id for token in ("..", "/", "\\", ":", "\x00", "://")):
        return None
    normalized_manifest = deepcopy(dict(manifest))
    normalized_capabilities = deepcopy(dict(capabilities))
    capabilities_list = normalized_capabilities.get("capabilities")
    if not isinstance(capabilities_list, list):
        return None
    normalized_capabilities["capabilities"] = sorted(_normalized_text_list(capabilities_list))
    normalized = {
        "schema_version": _text(descriptor.get("schema_version")),
        "target_id": target_id,
        "environment_class": _text(descriptor.get("environment_class")),
        "target_kind": _text(descriptor.get("target_kind")),
        "adapter_name": adapter_name,
        "adapter_version": adapter_version,
        "adapter_manifest": normalized_manifest,
        "adapter_capabilities": normalized_capabilities,
        "descriptor_access_mode": _text(descriptor.get("descriptor_access_mode")),
        "authorization_scope": _text(descriptor.get("authorization_scope")),
        "operational_entrypoints_exposed": sorted(_normalized_text_list(descriptor.get("operational_entrypoints_exposed") or [])),
        "deployment_executed": descriptor.get("deployment_executed"),
        "activation_executed": descriptor.get("activation_executed"),
        "production_scoring_executed": descriptor.get("production_scoring_executed"),
        "live_fast_lane_executed": descriptor.get("live_fast_lane_executed"),
    }
    manifest_fp = _manifest_fingerprint(normalized_manifest)
    capability_fp = _capability_fingerprint(normalized_capabilities)
    normalized["adapter_manifest_fingerprint"] = _text(descriptor.get("adapter_manifest_fingerprint")) or manifest_fp
    normalized["adapter_capability_fingerprint"] = _text(descriptor.get("adapter_capability_fingerprint")) or capability_fp
    normalized["descriptor_fingerprint"] = _text(descriptor.get("descriptor_fingerprint")) or _descriptor_fingerprint(
        {
            **normalized,
            "adapter_manifest_fingerprint": manifest_fp,
            "adapter_capability_fingerprint": capability_fp,
        }
    )
    return normalized


def _manifest_fingerprint(manifest: Mapping[str, Any]) -> str:
    return _hash_payload(
        {
            "schema_version": manifest.get("schema_version"),
            "adapter_name": manifest.get("adapter_name"),
            "adapter_version": manifest.get("adapter_version"),
            **{key: manifest.get(key) for key in sorted(manifest) if key not in {"schema_version", "adapter_name", "adapter_version"}},
        }
    )


def _capability_fingerprint(capabilities: Mapping[str, Any]) -> str:
    return _hash_payload(
        {
            "schema_version": capabilities.get("schema_version"),
            "capabilities": sorted(_normalized_text_list(capabilities.get("capabilities") or [])),
            **{key: capabilities.get(key) for key in sorted(capabilities) if key not in {"schema_version", "capabilities"}},
        }
    )


def _descriptor_fingerprint(descriptor: Mapping[str, Any]) -> str:
    return _hash_payload(
        {
            "schema_version": descriptor.get("schema_version"),
            "target_id": descriptor.get("target_id"),
            "environment_class": descriptor.get("environment_class"),
            "target_kind": descriptor.get("target_kind"),
            "adapter_name": descriptor.get("adapter_name"),
            "adapter_version": descriptor.get("adapter_version"),
            "adapter_manifest_fingerprint": descriptor.get("adapter_manifest_fingerprint"),
            "adapter_capability_fingerprint": descriptor.get("adapter_capability_fingerprint"),
            "descriptor_access_mode": descriptor.get("descriptor_access_mode"),
            "authorization_scope": descriptor.get("authorization_scope"),
            "operational_entrypoints_exposed": sorted(_normalized_text_list(descriptor.get("operational_entrypoints_exposed") or [])),
            "deployment_executed": descriptor.get("deployment_executed"),
            "activation_executed": descriptor.get("activation_executed"),
            "production_scoring_executed": descriptor.get("production_scoring_executed"),
            "live_fast_lane_executed": descriptor.get("live_fast_lane_executed"),
        }
    )


def _descriptor_path(base: Path, target_id: str) -> Path:
    return base / DESCRIPTOR_DIR / f"{_safe_id(target_id)}.json"


def _index_path(base: Path) -> Path:
    return base / "indexes" / DESCRIPTOR_INDEX


def _load_all_descriptors(base: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted((base / DESCRIPTOR_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping):
            items.append(dict(payload))
    return items


def _build_index(base: Path) -> dict[str, Any]:
    items = [
        {
            "target_id": item.get("target_id"),
            "environment_class": item.get("environment_class"),
            "adapter_name": item.get("adapter_name"),
            "adapter_version": item.get("adapter_version"),
            "descriptor_fingerprint": item.get("descriptor_fingerprint"),
        }
        for item in _load_all_descriptors(base)
    ]
    items.sort(key=lambda entry: str(entry.get("target_id") or ""))
    return {
        "schema_version": "production_target_descriptor_index_v1",
        "items": items,
    }


def _normalized_text_list(values: list[Any]) -> list[str]:
    output: list[str] = []
    for value in values:
        text = _text(value)
        if text is not None:
            output.append(text)
    return list(dict.fromkeys(output))


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in items if str(item)))
