"""Authoritative isolated controlled-integration adapter."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from .canonical_rule_runtime import CANONICAL_RULE_SCHEMA_VERSION, _atomic_write_json, _hash_payload, _now, _read_json, _restore_json, _safe_id
from .source_documents import SOURCE_DOCUMENT_ROOT

TARGET_ROOT_DIR = "controlled_integration_targets"
TARGET_MANIFEST_SCHEMA_VERSION = "controlled_integration_target_manifest_v1"
TARGET_NAMESPACE_SCHEMA_VERSION = "controlled_integration_target_namespace_v2"
TARGET_NAMESPACE_INDEX_SCHEMA_VERSION = "controlled_integration_target_namespace_index_v2"
TRANSACTION_SCHEMA_VERSION = "controlled_integration_transaction_v1"
ROLLBACK_SCHEMA_VERSION = "controlled_integration_rollback_v1"
PACKAGE_SCHEMA_VERSION = "controlled_integration_package_v1"
ADAPTER_MANIFEST_SCHEMA_VERSION = "controlled_integration_adapter_manifest_v1"
ADAPTER_ID = "filesystem_controlled_integration_target"
ADAPTER_VERSION = "1.1"
DEFAULT_TARGET_ID = "controlled_staging_primary"
MAX_PACKAGE_BYTES = 32768
TRANSACTION_STATES = {
    "applying",
    "pending_verification",
    "committing",
    "committed",
    "apply_failed",
    "commit_failed",
    "rolling_back",
    "rolled_back",
    "rollback_failed",
}
PUBLIC_FUNCTIONS = [
    "get_controlled_integration_adapter_manifest",
    "get_isolated_controlled_integration_target_workspace",
    "validate_controlled_integration_package",
    "preflight_controlled_integration_transaction",
    "apply_controlled_integration_transaction",
    "read_controlled_integration_target_state",
    "commit_controlled_integration_transaction",
    "rollback_controlled_integration_transaction",
    "list_controlled_integration_targets",
    "get_controlled_integration_target_manifest",
    "validate_controlled_integration_target",
    "preflight_controlled_integration_target",
    "apply_controlled_integration_rule",
    "verify_controlled_integration_rule",
    "rollback_controlled_integration_rule",
    "get_controlled_integration_target_health",
]


def get_controlled_integration_adapter_manifest(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_target_dirs(root)
    _ensure_default_target(base)
    manifest = _adapter_manifest()
    return {"status": "loaded", "adapter_manifest": manifest, "warnings": []}


def get_isolated_controlled_integration_target_workspace(target_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_target_dirs(root)
    target_validation = validate_controlled_integration_target(target_id, root=base)
    target_manifest_result = get_controlled_integration_target_manifest(target_id, root=base)
    target_manifest = target_manifest_result.get("manifest") if isinstance(target_manifest_result.get("manifest"), Mapping) else None
    adapter_manifest = _adapter_manifest()
    txs = _load_all_transactions(base, target_id)
    pending_count = len([item for item in txs if str(item.get("transaction_state") or "") in {"applying", "pending_verification", "committing"}])
    failed_count = len([item for item in txs if str(item.get("transaction_state") or "") in {"apply_failed", "commit_failed"}])
    rollback_failed_count = len([item for item in txs if str(item.get("transaction_state") or "") == "rollback_failed"])
    committed_count = len(_committed_namespace_items(base, target_id))
    return {
        "status": "loaded" if target_manifest else "not_found",
        "target_id": target_id,
        "environment_class": (target_manifest or {}).get("environment_class", "unknown"),
        "adapter_manifest": adapter_manifest,
        "target_manifest": target_manifest,
        "adapter_fingerprint": adapter_manifest.get("adapter_fingerprint"),
        "target_fingerprint": (target_manifest or {}).get("target_fingerprint"),
        "target_health": get_controlled_integration_target_health(target_id, root=base),
        "pending_transaction_count": pending_count,
        "committed_namespace_count": committed_count,
        "failed_transaction_count": failed_count,
        "rollback_failed_transaction_count": rollback_failed_count,
        "warnings": list(target_validation.get("warnings", [])),
        "blockers": list(target_validation.get("blockers", [])),
    }


def validate_controlled_integration_package(target_id: str, integration_package: dict, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_target_dirs(root)
    target_validation = validate_controlled_integration_target(target_id, root=base)
    blockers = list(target_validation.get("blockers", []))
    warnings = list(target_validation.get("warnings", []))
    normalized = _normalize_integration_package(integration_package)
    if normalized is None:
        blockers.append("integration_package_invalid")
        return {"valid": False, "status": "blocked", "package_fingerprint": None, "target_fingerprint": target_validation.get("target_fingerprint"), "warnings": _dedupe(warnings), "blockers": _dedupe(blockers)}
    if str(normalized.get("target_id") or "") != str(target_id):
        blockers.append("integration_package_target_mismatch")
    if _package_size_bytes(normalized) > MAX_PACKAGE_BYTES:
        blockers.append("integration_package_oversized")
    package_fingerprint = _integration_package_fingerprint(normalized)
    if str(normalized.get("package_fingerprint") or "") != package_fingerprint:
        blockers.append("integration_package_fingerprint_invalid")
    status = "valid" if not blockers else "blocked"
    return {
        "valid": not blockers,
        "status": status,
        "package_fingerprint": package_fingerprint,
        "target_fingerprint": target_validation.get("target_fingerprint"),
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
    }


def preflight_controlled_integration_transaction(target_id: str, integration_package: dict, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_target_dirs(root)
    target_validation = validate_controlled_integration_target(target_id, root=base)
    package_validation = validate_controlled_integration_package(target_id, integration_package, root=base)
    normalized = _normalize_integration_package(integration_package)
    blockers = _dedupe([*list(target_validation.get("blockers", [])), *list(package_validation.get("blockers", []))])
    warnings = _dedupe([*list(target_validation.get("warnings", [])), *list(package_validation.get("warnings", []))])
    if normalized is None:
        return {"status": "blocked", "target_id": target_id, "target_fingerprint": target_validation.get("target_fingerprint"), "package_fingerprint": None, "transaction_id": None, "namespace_id": None, "pre_apply_target_state_fingerprint": None, "warnings": warnings, "blockers": blockers}
    transaction_id = _transaction_id(target_id, str(normalized.get("package_fingerprint") or ""))
    namespace_id = _namespace_id(normalized)
    pre_apply_fingerprint = _target_state_fingerprint(base, target_id)
    existing_tx = _load_transaction(base, target_id, transaction_id)
    committed = _load_committed_namespace(base, target_id, namespace_id)
    pending = _load_pending_namespace(base, target_id, transaction_id)
    pending_namespace_conflict = next(
        (
            item
            for item in _pending_namespace_items(base, target_id)
            if str(item.get("namespace_id") or "") == namespace_id
            and str(item.get("transaction_id") or "") != transaction_id
        ),
        None,
    )
    if blockers:
        return {"status": "blocked", "target_id": target_id, "target_fingerprint": target_validation.get("target_fingerprint"), "package_fingerprint": normalized.get("package_fingerprint"), "transaction_id": transaction_id, "namespace_id": namespace_id, "pre_apply_target_state_fingerprint": pre_apply_fingerprint, "warnings": warnings, "blockers": blockers}
    if isinstance(committed, Mapping):
        if str(committed.get("package_fingerprint") or "") == str(normalized.get("package_fingerprint") or ""):
            return {"status": "already_committed", "target_id": target_id, "target_fingerprint": target_validation.get("target_fingerprint"), "package_fingerprint": normalized.get("package_fingerprint"), "transaction_id": transaction_id, "namespace_id": namespace_id, "pre_apply_target_state_fingerprint": pre_apply_fingerprint, "warnings": warnings, "blockers": []}
        return {"status": "conflict", "target_id": target_id, "target_fingerprint": target_validation.get("target_fingerprint"), "package_fingerprint": normalized.get("package_fingerprint"), "transaction_id": transaction_id, "namespace_id": namespace_id, "pre_apply_target_state_fingerprint": pre_apply_fingerprint, "warnings": warnings, "blockers": ["committed_namespace_conflict"]}
    if isinstance(existing_tx, Mapping) and str(existing_tx.get("transaction_state") or "") in {"applying", "pending_verification", "committing", "rollback_failed"}:
        return {"status": "conflict", "target_id": target_id, "target_fingerprint": target_validation.get("target_fingerprint"), "package_fingerprint": normalized.get("package_fingerprint"), "transaction_id": transaction_id, "namespace_id": namespace_id, "pre_apply_target_state_fingerprint": pre_apply_fingerprint, "warnings": warnings, "blockers": ["transaction_state_conflict"]}
    if isinstance(pending_namespace_conflict, Mapping):
        return {"status": "conflict", "target_id": target_id, "target_fingerprint": target_validation.get("target_fingerprint"), "package_fingerprint": normalized.get("package_fingerprint"), "transaction_id": transaction_id, "namespace_id": namespace_id, "pre_apply_target_state_fingerprint": pre_apply_fingerprint, "warnings": warnings, "blockers": ["pending_namespace_conflict"]}
    if isinstance(pending, Mapping) and str(pending.get("package_fingerprint") or "") != str(normalized.get("package_fingerprint") or ""):
        return {"status": "conflict", "target_id": target_id, "target_fingerprint": target_validation.get("target_fingerprint"), "package_fingerprint": normalized.get("package_fingerprint"), "transaction_id": transaction_id, "namespace_id": namespace_id, "pre_apply_target_state_fingerprint": pre_apply_fingerprint, "warnings": warnings, "blockers": ["pending_namespace_conflict"]}
    return {"status": "ready", "target_id": target_id, "target_fingerprint": target_validation.get("target_fingerprint"), "package_fingerprint": normalized.get("package_fingerprint"), "transaction_id": transaction_id, "namespace_id": namespace_id, "pre_apply_target_state_fingerprint": pre_apply_fingerprint, "warnings": warnings, "blockers": []}


def apply_controlled_integration_transaction(target_id: str, integration_package: dict, confirmation: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    if confirmation != "APPLY_ISOLATED_INTEGRATION_TRANSACTION":
        return {"status": "blocked", "target_id": target_id, "warnings": [], "blockers": ["apply_transaction_confirmation_required"]}
    base = _ensure_target_dirs(root)
    preflight = preflight_controlled_integration_transaction(target_id, integration_package, root=base)
    if str(preflight.get("status") or "") != "ready":
        return {"status": str(preflight.get("status") or "blocked"), "target_id": target_id, "transaction_id": preflight.get("transaction_id"), "namespace_id": preflight.get("namespace_id"), "warnings": list(preflight.get("warnings", [])), "blockers": list(preflight.get("blockers", []))}
    normalized = _normalize_integration_package(integration_package)
    assert normalized is not None
    transaction_id = str(preflight["transaction_id"])
    namespace_id = str(preflight["namespace_id"])
    tx_path = _transaction_path(base, target_id, transaction_id)
    pending_path = _pending_namespace_path(base, target_id, transaction_id)
    before_tx = _read_json(tx_path)
    before_pending = _read_json(pending_path)
    state = _build_pending_state(target_id, transaction_id, namespace_id, normalized, str(preflight.get("pre_apply_target_state_fingerprint") or ""))
    transaction = _build_transaction(target_id, transaction_id, namespace_id, normalized, state["state_fingerprint"], str(preflight.get("pre_apply_target_state_fingerprint") or ""), "applying")
    try:
        _atomic_write_json(tx_path, transaction)
        _atomic_write_json(pending_path, state)
        pending_read = read_controlled_integration_target_state(target_id, transaction_id=transaction_id, root=base)
        if str(pending_read.get("verification_status") or "") != "verified_pending":
            transaction["transaction_state"] = "apply_failed"
            transaction["updated_at_utc"] = _now()
            _atomic_write_json(tx_path, transaction)
            return {"status": "apply_failed", "target_id": target_id, "transaction_id": transaction_id, "namespace_id": namespace_id, "warnings": list(pending_read.get("warnings", [])), "blockers": list(pending_read.get("blockers", []))}
        transaction["transaction_state"] = "pending_verification"
        transaction["pending_state_fingerprint"] = str(pending_read.get("state_fingerprint") or "")
        transaction["updated_at_utc"] = _now()
        _atomic_write_json(tx_path, transaction)
    except Exception:
        _restore_json(tx_path, before_tx)
        _restore_json(pending_path, before_pending)
        return {"status": "apply_failed", "target_id": target_id, "transaction_id": transaction_id, "namespace_id": namespace_id, "warnings": [], "blockers": ["pending_apply_write_failed"]}
    return {"status": "pending_verification", "target_id": target_id, "transaction_id": transaction_id, "namespace_id": namespace_id, "package_fingerprint": normalized.get("package_fingerprint"), "warnings": [], "blockers": []}


def read_controlled_integration_target_state(target_id: str, transaction_id: str | None = None, namespace_id: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_target_dirs(root)
    ids = [bool(transaction_id), bool(namespace_id)]
    if ids.count(True) != 1:
        return {"status": "blocked", "target_id": target_id, "verification_status": "unknown", "warnings": [], "blockers": ["exactly_one_identifier_required"]}
    target_manifest_result = get_controlled_integration_target_manifest(target_id, root=base)
    target_manifest = target_manifest_result.get("manifest") if isinstance(target_manifest_result.get("manifest"), Mapping) else {}
    if transaction_id:
        transaction = _load_transaction(base, target_id, str(transaction_id))
        if not isinstance(transaction, Mapping):
            return {"status": "missing", "target_id": target_id, "transaction_id": transaction_id, "verification_status": "missing", "warnings": [], "blockers": ["transaction_missing"]}
        pending = _load_pending_namespace(base, target_id, str(transaction_id))
        if not isinstance(pending, Mapping):
            return {"status": "missing", "target_id": target_id, "transaction_id": transaction_id, "namespace_id": transaction.get("namespace_id"), "transaction_state": transaction.get("transaction_state"), "verification_status": "missing", "warnings": [], "blockers": ["pending_state_missing"]}
        actual_pending_fingerprint = _state_fingerprint(pending)
        return _state_payload(target_manifest, transaction, pending, "verified_pending" if str(transaction.get("pending_state_fingerprint") or "") == str(actual_pending_fingerprint or "") else "mismatch")
    committed = _load_committed_namespace(base, target_id, str(namespace_id))
    if not isinstance(committed, Mapping):
        return {"status": "missing", "target_id": target_id, "namespace_id": namespace_id, "verification_status": "missing", "warnings": [], "blockers": ["committed_namespace_missing"]}
    transaction = _load_transaction(base, target_id, str(committed.get("transaction_id") or ""))
    actual_committed_fingerprint = _state_fingerprint(committed)
    return _state_payload(target_manifest, transaction or {}, committed, "verified_committed" if str((transaction or {}).get("committed_state_fingerprint") or actual_committed_fingerprint or "") == str(actual_committed_fingerprint or "") else "mismatch")


def commit_controlled_integration_transaction(target_id: str, transaction_id: str, expected_state_fingerprint: str, confirmation: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    if confirmation != "COMMIT_ISOLATED_INTEGRATION_TRANSACTION":
        return {"status": "blocked", "target_id": target_id, "transaction_id": transaction_id, "warnings": [], "blockers": ["commit_transaction_confirmation_required"]}
    base = _ensure_target_dirs(root)
    transaction = _load_transaction(base, target_id, transaction_id)
    if not isinstance(transaction, Mapping):
        return {"status": "blocked", "target_id": target_id, "transaction_id": transaction_id, "warnings": [], "blockers": ["transaction_missing"]}
    if str(transaction.get("transaction_state") or "") == "committed":
        return {"status": "already_committed", "target_id": target_id, "transaction_id": transaction_id, "namespace_id": transaction.get("namespace_id"), "warnings": [], "blockers": []}
    if str(transaction.get("transaction_state") or "") != "pending_verification":
        return {"status": "blocked", "target_id": target_id, "transaction_id": transaction_id, "warnings": [], "blockers": ["transaction_state_not_pending_verification"]}
    readback = read_controlled_integration_target_state(target_id, transaction_id=transaction_id, root=base)
    if str(readback.get("verification_status") or "") != "verified_pending":
        return {"status": "verification_failed", "target_id": target_id, "transaction_id": transaction_id, "warnings": list(readback.get("warnings", [])), "blockers": list(readback.get("blockers", []))}
    if str(readback.get("state_fingerprint") or "") != str(expected_state_fingerprint or ""):
        return {"status": "conflict", "target_id": target_id, "transaction_id": transaction_id, "warnings": [], "blockers": ["expected_state_fingerprint_mismatch"]}
    namespace_id = str(transaction.get("namespace_id") or "")
    committed_path = _committed_namespace_path(base, target_id, namespace_id)
    pending_path = _pending_namespace_path(base, target_id, transaction_id)
    index_path = _namespace_index_path(base, target_id)
    before_tx = _read_json(_transaction_path(base, target_id, transaction_id))
    before_committed = _read_json(committed_path)
    before_pending = _read_json(pending_path)
    before_index = _read_json(index_path)
    pending = _load_pending_namespace(base, target_id, transaction_id)
    assert isinstance(pending, Mapping)
    committed = deepcopy(dict(pending))
    committed["status"] = "staged_non_production"
    committed["committed_at_utc"] = _now()
    committed["state_fingerprint"] = _state_fingerprint(committed)
    updated_tx = deepcopy(dict(transaction))
    updated_tx["transaction_state"] = "committing"
    updated_tx["updated_at_utc"] = _now()
    try:
        _atomic_write_json(_transaction_path(base, target_id, transaction_id), updated_tx)
        _atomic_write_json(committed_path, committed)
        _atomic_write_json(index_path, _updated_namespace_index(before_index, committed))
        _restore_json(pending_path, None)
        updated_tx["transaction_state"] = "committed"
        updated_tx["committed_state_fingerprint"] = committed["state_fingerprint"]
        updated_tx["updated_at_utc"] = _now()
        _atomic_write_json(_transaction_path(base, target_id, transaction_id), updated_tx)
        committed_read = read_controlled_integration_target_state(target_id, namespace_id=namespace_id, root=base)
        if str(committed_read.get("verification_status") or "") != "verified_committed":
            updated_tx["transaction_state"] = "commit_failed"
            _atomic_write_json(_transaction_path(base, target_id, transaction_id), updated_tx)
            return {"status": "verification_failed", "target_id": target_id, "transaction_id": transaction_id, "namespace_id": namespace_id, "warnings": list(committed_read.get("warnings", [])), "blockers": list(committed_read.get("blockers", []))}
    except Exception:
        _restore_json(_transaction_path(base, target_id, transaction_id), before_tx)
        _restore_json(committed_path, before_committed)
        _restore_json(pending_path, before_pending)
        _restore_json(index_path, before_index)
        return {"status": "commit_failed", "target_id": target_id, "transaction_id": transaction_id, "namespace_id": namespace_id, "warnings": [], "blockers": ["commit_write_failed"]}
    return {"status": "committed", "target_id": target_id, "transaction_id": transaction_id, "namespace_id": namespace_id, "state_fingerprint": committed["state_fingerprint"], "warnings": [], "blockers": []}


def rollback_controlled_integration_transaction(target_id: str, transaction_id: str, confirmation: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    if confirmation != "ROLLBACK_ISOLATED_INTEGRATION_TRANSACTION":
        return {"status": "blocked", "target_id": target_id, "transaction_id": transaction_id, "warnings": [], "blockers": ["rollback_transaction_confirmation_required"]}
    base = _ensure_target_dirs(root)
    transaction = _load_transaction(base, target_id, transaction_id)
    if not isinstance(transaction, Mapping):
        return {"status": "already_rolled_back", "target_id": target_id, "transaction_id": transaction_id, "warnings": [], "blockers": []}
    if str(transaction.get("transaction_state") or "") == "rolled_back":
        return {"status": "already_rolled_back", "target_id": target_id, "transaction_id": transaction_id, "warnings": [], "blockers": []}
    namespace_id = str(transaction.get("namespace_id") or "")
    tx_path = _transaction_path(base, target_id, transaction_id)
    pending_path = _pending_namespace_path(base, target_id, transaction_id)
    committed_path = _committed_namespace_path(base, target_id, namespace_id)
    rollback_path = _rollback_record_path(base, target_id, transaction_id)
    index_path = _namespace_index_path(base, target_id)
    before_tx = _read_json(tx_path)
    before_pending = _read_json(pending_path)
    before_committed = _read_json(committed_path)
    before_index = _read_json(index_path)
    updated_tx = deepcopy(dict(transaction))
    updated_tx["transaction_state"] = "rolling_back"
    updated_tx["updated_at_utc"] = _now()
    try:
        _atomic_write_json(tx_path, updated_tx)
        _restore_json(pending_path, None)
        _restore_json(committed_path, None)
        _atomic_write_json(index_path, _removed_namespace_index(before_index, namespace_id))
        rollback_record = {
            "schema_version": ROLLBACK_SCHEMA_VERSION,
            "target_id": target_id,
            "transaction_id": transaction_id,
            "namespace_id": namespace_id,
            "package_fingerprint": transaction.get("package_fingerprint"),
            "created_at_utc": _now(),
            "status": "completed",
        }
        _atomic_write_json(rollback_path, rollback_record)
        updated_tx["transaction_state"] = "rolled_back"
        updated_tx["updated_at_utc"] = _now()
        _atomic_write_json(tx_path, updated_tx)
    except Exception:
        _restore_json(tx_path, before_tx)
        _restore_json(pending_path, before_pending)
        _restore_json(committed_path, before_committed)
        _restore_json(index_path, before_index)
        return {"status": "rollback_failed", "target_id": target_id, "transaction_id": transaction_id, "warnings": [], "blockers": ["rollback_write_failed"]}
    return {"status": "completed", "target_id": target_id, "transaction_id": transaction_id, "namespace_id": namespace_id, "warnings": [], "blockers": []}


def list_controlled_integration_targets(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_target_dirs(root)
    _ensure_default_target(base)
    items: list[dict[str, Any]] = []
    for path in sorted((base / TARGET_ROOT_DIR).glob("*/manifest.json")):
        manifest = _read_json(path)
        if isinstance(manifest, Mapping):
            items.append(_public_target_manifest(manifest))
    return {"status": "listed", "count": len(items), "items": items, "warnings": []}


def get_controlled_integration_target_manifest(target_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_target_dirs(root)
    manifest = _load_or_bootstrap_manifest(base, target_id)
    if not isinstance(manifest, Mapping):
        return {"status": "not_found", "target_id": target_id, "warnings": [], "blockers": ["integration_target_not_found"]}
    return {"status": "loaded", "target_id": target_id, "manifest": _public_target_manifest(manifest), "warnings": []}


def validate_controlled_integration_target(target_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_target_dirs(root)
    manifest = _load_or_bootstrap_manifest(base, target_id)
    if not isinstance(manifest, Mapping):
        return {"status": "blocked", "target_id": target_id, "warnings": [], "blockers": ["integration_target_not_found"]}
    blockers: list[str] = []
    if str(manifest.get("environment_class") or "") != "isolated_non_production":
        blockers.append("integration_target_not_isolated_non_production")
    if str(manifest.get("adapter_id") or "") != ADAPTER_ID:
        blockers.append("integration_target_adapter_identity_invalid")
    if str(manifest.get("adapter_version") or "") != ADAPTER_VERSION:
        blockers.append("integration_target_adapter_version_invalid")
    if str(manifest.get("target_fingerprint") or "") != _target_manifest_fingerprint(manifest):
        blockers.append("integration_target_fingerprint_mismatch")
    if not bool(manifest.get("supports_transactional_apply")):
        blockers.append("integration_target_transactional_apply_unavailable")
    if not bool(manifest.get("supports_independent_readback")):
        blockers.append("integration_target_readback_unavailable")
    if not bool(manifest.get("supports_explicit_commit")):
        blockers.append("integration_target_commit_unavailable")
    if not bool(manifest.get("supports_rollback")):
        blockers.append("integration_target_rollback_unavailable")
    return {"status": "eligible" if not blockers else "blocked", "target_id": target_id, "environment_class": manifest.get("environment_class"), "adapter_id": manifest.get("adapter_id"), "adapter_version": manifest.get("adapter_version"), "target_fingerprint": manifest.get("target_fingerprint"), "warnings": [], "blockers": blockers}


def preflight_controlled_integration_target(target_id: str, execution_package: Mapping[str, Any], *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    result = preflight_controlled_integration_transaction(target_id, _compatibility_package(target_id, execution_package), root=root)
    status = str(result.get("status") or "blocked")
    return {
        "status": "eligible" if status == "ready" else "eligible" if status == "already_committed" else status,
        "target_id": target_id,
        "isolated_namespace_id": result.get("namespace_id"),
        "execution_package_fingerprint": result.get("package_fingerprint"),
        "warnings": list(result.get("warnings", [])),
        "blockers": list(result.get("blockers", [])),
    }


def apply_controlled_integration_rule(target_id: str, execution_package: Mapping[str, Any], *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    compat_package = _compatibility_package(target_id, execution_package)
    preflight = preflight_controlled_integration_transaction(target_id, compat_package, root=root)
    if str(preflight.get("status") or "") == "already_committed":
        return {"status": "already_applied", "target_id": target_id, "isolated_namespace_id": preflight.get("namespace_id"), "execution_package_fingerprint": preflight.get("package_fingerprint"), "writes_performed": 0, "warnings": []}
    pending = apply_controlled_integration_transaction(target_id, compat_package, confirmation="APPLY_ISOLATED_INTEGRATION_TRANSACTION", root=root)
    if str(pending.get("status") or "") != "pending_verification":
        return {"status": "blocked" if str(pending.get("status") or "") in {"blocked", "conflict", "unknown"} else str(pending.get("status") or ""), "target_id": target_id, "isolated_namespace_id": pending.get("namespace_id"), "warnings": list(pending.get("warnings", [])), "blockers": list(pending.get("blockers", []))}
    readback = read_controlled_integration_target_state(target_id, transaction_id=str(pending.get("transaction_id") or ""), root=root)
    commit = commit_controlled_integration_transaction(target_id, str(pending.get("transaction_id") or ""), str(readback.get("state_fingerprint") or ""), confirmation="COMMIT_ISOLATED_INTEGRATION_TRANSACTION", root=root)
    if str(commit.get("status") or "") == "committed":
        return {"status": "applied", "target_id": target_id, "isolated_namespace_id": commit.get("namespace_id"), "execution_package_fingerprint": preflight.get("package_fingerprint"), "writes_performed": 1, "warnings": []}
    return {"status": str(commit.get("status") or "blocked"), "target_id": target_id, "isolated_namespace_id": commit.get("namespace_id"), "warnings": list(commit.get("warnings", [])), "blockers": list(commit.get("blockers", []))}


def verify_controlled_integration_rule(target_id: str, isolated_namespace_id: str, expected_execution_package_fingerprint: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_target_dirs(root)
    readback = read_controlled_integration_target_state(target_id, namespace_id=isolated_namespace_id, root=root)
    if str(readback.get("verification_status") or "") != "verified_committed":
        return {"status": "blocked", "target_id": target_id, "isolated_namespace_id": isolated_namespace_id, "warnings": list(readback.get("warnings", [])), "blockers": list(readback.get("blockers", []))}
    committed = _load_committed_namespace(base, target_id, isolated_namespace_id)
    compatibility_fingerprint = None
    if isinstance(committed, Mapping):
        package = committed.get("package")
        if isinstance(package, Mapping):
            compatibility_fingerprint = package.get("execution_package_fingerprint")
    if str(compatibility_fingerprint or readback.get("package_fingerprint") or "") != str(expected_execution_package_fingerprint or ""):
        return {"status": "blocked", "target_id": target_id, "isolated_namespace_id": isolated_namespace_id, "warnings": [], "blockers": ["integration_namespace_fingerprint_mismatch"]}
    return {"status": "verified", "target_id": target_id, "isolated_namespace_id": isolated_namespace_id, "canonical_rule_id": readback.get("canonical_rule_id"), "execution_package_fingerprint": readback.get("package_fingerprint"), "warnings": []}


def rollback_controlled_integration_rule(target_id: str, isolated_namespace_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_target_dirs(root)
    committed = _load_committed_namespace(base, target_id, isolated_namespace_id)
    if isinstance(committed, Mapping):
        return rollback_controlled_integration_transaction(target_id, str(committed.get("transaction_id") or ""), confirmation="ROLLBACK_ISOLATED_INTEGRATION_TRANSACTION", root=base)
    for tx in _load_all_transactions(base, target_id):
        if str(tx.get("namespace_id") or "") == str(isolated_namespace_id or ""):
            return rollback_controlled_integration_transaction(target_id, str(tx.get("transaction_id") or ""), confirmation="ROLLBACK_ISOLATED_INTEGRATION_TRANSACTION", root=base)
    return {"status": "already_rolled_back", "target_id": target_id, "isolated_namespace_id": isolated_namespace_id, "writes_performed": 0, "warnings": []}


def get_controlled_integration_target_health(target_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_target_dirs(root)
    manifest = _load_or_bootstrap_manifest(base, target_id)
    if not isinstance(manifest, Mapping):
        return {"status": "unknown", "target_id": target_id, "active_namespace_count": 0, "warnings": ["integration_target_not_found"], "recommended_action": "Create or restore the controlled integration target manifest."}
    txs = _load_all_transactions(base, target_id)
    committed_items = _committed_namespace_items(base, target_id)
    return {
        "status": "healthy" if str(manifest.get("health_status") or "") == "healthy" else "blocked",
        "target_id": target_id,
        "environment_class": manifest.get("environment_class"),
        "target_fingerprint": manifest.get("target_fingerprint"),
        "active_namespace_count": len(committed_items),
        "pending_transaction_count": len([item for item in txs if str(item.get("transaction_state") or "") in {"applying", "pending_verification", "committing"}]),
        "rollback_failed_transaction_count": len([item for item in txs if str(item.get("transaction_state") or "") == "rollback_failed"]),
        "warnings": [],
        "recommended_action": "Ready for controlled non-production integration." if str(manifest.get("health_status") or "") == "healthy" else "Repair the controlled integration target manifest.",
    }


def _ensure_target_dirs(root: Path | str) -> Path:
    base = Path(root)
    (base / TARGET_ROOT_DIR).mkdir(parents=True, exist_ok=True)
    return base


def _adapter_manifest() -> dict[str, Any]:
    manifest = {
        "schema_version": ADAPTER_MANIFEST_SCHEMA_VERSION,
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "environment_class": "isolated_non_production",
        "supported_target_schema_versions": [TARGET_NAMESPACE_SCHEMA_VERSION],
        "supported_package_schema_versions": [PACKAGE_SCHEMA_VERSION],
        "supported_canonical_rule_schema_versions": [CANONICAL_RULE_SCHEMA_VERSION],
        "transaction_mode": "pending_verify_commit",
        "verification_mode": "independent_filesystem_readback",
        "rollback_mode": "transaction_owned_cleanup",
        "supports_preflight": True,
        "supports_transactional_apply": True,
        "supports_independent_readback": True,
        "supports_explicit_commit": True,
        "supports_rollback": True,
        "supports_production": False,
        "executes_rules": False,
        "writes_production_scores": False,
        "executes_fast_lane": False,
        "deterministic": True,
    }
    manifest["adapter_fingerprint"] = _adapter_manifest_fingerprint(manifest)
    return manifest


def _ensure_default_target(base: Path) -> None:
    if not _manifest_path(base, DEFAULT_TARGET_ID).exists():
        manifest = _build_target_manifest(DEFAULT_TARGET_ID)
        _atomic_write_json(_manifest_path(base, DEFAULT_TARGET_ID), manifest)
        _atomic_write_json(_namespace_index_path(base, DEFAULT_TARGET_ID), _empty_namespace_index())


def _load_or_bootstrap_manifest(base: Path, target_id: str) -> Mapping[str, Any] | None:
    if str(target_id or "").strip() == DEFAULT_TARGET_ID:
        _ensure_default_target(base)
    payload = _read_json(_manifest_path(base, target_id))
    return payload if isinstance(payload, Mapping) else None


def _build_target_manifest(target_id: str) -> dict[str, Any]:
    manifest = {
        "schema_version": TARGET_MANIFEST_SCHEMA_VERSION,
        "target_id": _validated_id(target_id),
        "environment_class": "isolated_non_production",
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "target_schema_version": TARGET_NAMESPACE_SCHEMA_VERSION,
        "supported_rule_schema_versions": [CANONICAL_RULE_SCHEMA_VERSION],
        "supported_package_schema_versions": [PACKAGE_SCHEMA_VERSION],
        "isolation_mode": "namespace_scoped",
        "supports_transactional_apply": True,
        "supports_independent_readback": True,
        "supports_explicit_commit": True,
        "supports_rollback": True,
        "health_status": "healthy",
    }
    manifest["target_fingerprint"] = _target_manifest_fingerprint(manifest)
    return manifest


def _normalize_integration_package(integration_package: Mapping[str, Any]) -> dict[str, Any] | None:
    if not isinstance(integration_package, Mapping):
        return None
    prohibited = {"callback", "script", "activate", "deployment", "deploy", "production_route", "path", "file_path", "uri", "external_reference"}
    if prohibited & {str(key) for key in integration_package.keys()}:
        return None
    required = {
        "schema_version",
        "package_id",
        "target_id",
        "canonical_rule_id",
        "canonical_rule_schema_version",
        "canonical_rule_fingerprint",
        "document_id",
        "source_revision",
        "certification_id",
        "certification_fingerprint",
        "release_candidate_result_id",
        "release_candidate_fingerprint",
        "authorization_result_id",
        "authorization_fingerprint",
        "scoring_preview_result_id",
        "scoring_config_id",
        "scoring_config_fingerprint",
        "fast_lane_preview_result_id",
        "fast_lane_contract_id",
        "fast_lane_contract_version",
        "fast_lane_capability_fingerprint",
        "package_fingerprint",
    }
    if any(field not in integration_package for field in required):
        return None
    normalized: dict[str, Any] = {}
    text_fields = required - {"source_revision"}
    for field in sorted(text_fields):
        value = _text(integration_package.get(field))
        if value is None:
            return None
        normalized[field] = value
    normalized["source_revision"] = integration_package.get("source_revision")
    if normalized["schema_version"] != PACKAGE_SCHEMA_VERSION:
        return None
    if normalized["canonical_rule_schema_version"] != CANONICAL_RULE_SCHEMA_VERSION:
        return None
    for field in ("target_id", "package_id", "canonical_rule_id", "release_candidate_result_id", "authorization_result_id", "scoring_preview_result_id", "fast_lane_preview_result_id"):
        if _safe_id(normalized[field]) != normalized[field]:
            return None
    isolated_namespace_id = _text(integration_package.get("isolated_namespace_id"))
    if isolated_namespace_id is not None:
        if _safe_id(isolated_namespace_id) != isolated_namespace_id:
            return None
        normalized["isolated_namespace_id"] = isolated_namespace_id
    execution_package_fingerprint = _text(integration_package.get("execution_package_fingerprint"))
    if execution_package_fingerprint is not None:
        if not _valid_fingerprint(execution_package_fingerprint):
            return None
        normalized["execution_package_fingerprint"] = execution_package_fingerprint
    if not _valid_fingerprint(normalized["package_fingerprint"]):
        return None
    for field in (
        "canonical_rule_fingerprint",
        "certification_fingerprint",
        "release_candidate_fingerprint",
        "authorization_fingerprint",
        "scoring_config_fingerprint",
        "fast_lane_capability_fingerprint",
    ):
        if not _valid_fingerprint(normalized[field]):
            return None
    normalized["package_fingerprint"] = _text(integration_package.get("package_fingerprint"))
    return normalized


def _integration_package_fingerprint(payload: Mapping[str, Any]) -> str:
    return _hash_payload({key: payload.get(key) for key in sorted(payload) if key != "package_fingerprint"})


def _transaction_id(target_id: str, package_fingerprint: str) -> str:
    return f"tx_{_hash_payload({'target_id': target_id, 'package_fingerprint': package_fingerprint})[7:23]}"


def _namespace_id(payload: Mapping[str, Any]) -> str:
    legacy_namespace_id = _text(payload.get("isolated_namespace_id"))
    if legacy_namespace_id is not None:
        return _validated_id(legacy_namespace_id)
    return f"ns_{_hash_payload({'target_id': payload.get('target_id'), 'canonical_rule_id': payload.get('canonical_rule_id'), 'release_candidate_fingerprint': payload.get('release_candidate_fingerprint')})[7:23]}"


def _state_fingerprint(payload: Mapping[str, Any]) -> str:
    return _hash_payload({key: payload.get(key) for key in sorted(payload) if key not in {"created_at_utc", "updated_at_utc", "committed_at_utc", "state_fingerprint"}})


def _target_state_fingerprint(base: Path, target_id: str) -> str:
    committed = _committed_namespace_items(base, target_id)
    transactions = [
        {"transaction_id": item.get("transaction_id"), "state": item.get("transaction_state"), "package_fingerprint": item.get("package_fingerprint")}
        for item in _load_all_transactions(base, target_id)
    ]
    return _hash_payload({"target_id": target_id, "committed": committed, "transactions": transactions})


def _build_pending_state(target_id: str, transaction_id: str, namespace_id: str, package: Mapping[str, Any], pre_apply_target_state_fingerprint: str) -> dict[str, Any]:
    payload = {
        "schema_version": TARGET_NAMESPACE_SCHEMA_VERSION,
        "target_id": target_id,
        "transaction_id": transaction_id,
        "namespace_id": namespace_id,
        "status": "pending_verification",
        "environment_class": "isolated_non_production",
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "package": deepcopy(dict(package)),
        "package_fingerprint": package.get("package_fingerprint"),
        "canonical_rule_id": package.get("canonical_rule_id"),
        "canonical_rule_fingerprint": package.get("canonical_rule_fingerprint"),
        "document_id": package.get("document_id"),
        "source_revision": package.get("source_revision"),
        "certification_fingerprint": package.get("certification_fingerprint"),
        "release_candidate_fingerprint": package.get("release_candidate_fingerprint"),
        "authorization_fingerprint": package.get("authorization_fingerprint"),
        "scoring_config_fingerprint": package.get("scoring_config_fingerprint"),
        "fast_lane_capability_fingerprint": package.get("fast_lane_capability_fingerprint"),
        "pre_apply_target_state_fingerprint": pre_apply_target_state_fingerprint,
        "created_at_utc": _now(),
        "updated_at_utc": _now(),
    }
    payload["state_fingerprint"] = _state_fingerprint(payload)
    return payload


def _build_transaction(target_id: str, transaction_id: str, namespace_id: str, package: Mapping[str, Any], pending_state_fingerprint: str, pre_apply_target_state_fingerprint: str, state: str) -> dict[str, Any]:
    return {
        "schema_version": TRANSACTION_SCHEMA_VERSION,
        "target_id": target_id,
        "transaction_id": transaction_id,
        "namespace_id": namespace_id,
        "package_id": package.get("package_id"),
        "package_fingerprint": package.get("package_fingerprint"),
        "canonical_rule_id": package.get("canonical_rule_id"),
        "transaction_state": state,
        "pending_state_fingerprint": pending_state_fingerprint,
        "committed_state_fingerprint": None,
        "pre_apply_target_state_fingerprint": pre_apply_target_state_fingerprint,
        "created_at_utc": _now(),
        "updated_at_utc": _now(),
    }


def _state_payload(target_manifest: Mapping[str, Any], transaction: Mapping[str, Any], state: Mapping[str, Any], verification_status: str) -> dict[str, Any]:
    actual_state_fingerprint = _state_fingerprint(state)
    blockers: list[str] = []
    if verification_status == "mismatch":
        blockers.append("state_fingerprint_mismatch")
    return {
        "status": "loaded",
        "target_id": state.get("target_id"),
        "environment_class": target_manifest.get("environment_class", state.get("environment_class")),
        "adapter_id": target_manifest.get("adapter_id", state.get("adapter_id")),
        "adapter_version": target_manifest.get("adapter_version", state.get("adapter_version")),
        "transaction_id": transaction.get("transaction_id"),
        "namespace_id": state.get("namespace_id"),
        "transaction_state": transaction.get("transaction_state", state.get("status")),
        "package_fingerprint": state.get("package_fingerprint"),
        "canonical_rule_id": state.get("canonical_rule_id"),
        "canonical_rule_fingerprint": state.get("canonical_rule_fingerprint"),
        "document_id": state.get("document_id"),
        "source_revision": state.get("source_revision"),
        "certification_fingerprint": state.get("certification_fingerprint"),
        "release_candidate_fingerprint": state.get("release_candidate_fingerprint"),
        "authorization_fingerprint": state.get("authorization_fingerprint"),
        "scoring_config_fingerprint": state.get("scoring_config_fingerprint"),
        "fast_lane_capability_fingerprint": state.get("fast_lane_capability_fingerprint"),
        "state_fingerprint": actual_state_fingerprint,
        "verification_status": verification_status,
        "warnings": [],
        "blockers": blockers,
    }


def _adapter_manifest_fingerprint(manifest: Mapping[str, Any]) -> str:
    return _hash_payload({key: manifest.get(key) for key in sorted(manifest) if key != "adapter_fingerprint"})


def _target_manifest_fingerprint(manifest: Mapping[str, Any]) -> str:
    return _hash_payload({key: manifest.get(key) for key in sorted(manifest) if key != "target_fingerprint"})


def _package_size_bytes(payload: Mapping[str, Any]) -> int:
    return len(str(payload).encode("utf-8"))


def _valid_fingerprint(value: str | None) -> bool:
    text = str(value or "")
    return text.startswith("sha256:") and len(text) == 71


def _validated_id(value: str) -> str:
    text = _text(value)
    if text is None or len(text) > 120 or text != _safe_id(text) or any(token in text for token in ("..", "/", "\\", ":", "\x00", "://")):
        raise ValueError("invalid_controlled_integration_id")
    if text.lower().startswith("production"):
        raise ValueError("production_like_target_id_forbidden")
    return text


def _public_target_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": manifest.get("schema_version"),
        "target_id": manifest.get("target_id"),
        "environment_class": manifest.get("environment_class"),
        "adapter_id": manifest.get("adapter_id"),
        "adapter_version": manifest.get("adapter_version"),
        "target_schema_version": manifest.get("target_schema_version"),
        "supported_rule_schema_versions": list(manifest.get("supported_rule_schema_versions", [])),
        "supported_package_schema_versions": list(manifest.get("supported_package_schema_versions", [])),
        "isolation_mode": manifest.get("isolation_mode"),
        "supports_transactional_apply": bool(manifest.get("supports_transactional_apply")),
        "supports_independent_readback": bool(manifest.get("supports_independent_readback")),
        "supports_explicit_commit": bool(manifest.get("supports_explicit_commit")),
        "supports_rollback": bool(manifest.get("supports_rollback")),
        "health_status": manifest.get("health_status"),
        "target_fingerprint": manifest.get("target_fingerprint"),
    }


def _empty_namespace_index() -> dict[str, Any]:
    return {"schema_version": TARGET_NAMESPACE_INDEX_SCHEMA_VERSION, "items": [], "updated_at_utc": _now()}


def _updated_namespace_index(index: Any, namespace_payload: Mapping[str, Any]) -> dict[str, Any]:
    items = list(index.get("items", [])) if isinstance(index, Mapping) else []
    item = {
        "namespace_id": namespace_payload.get("namespace_id"),
        "transaction_id": namespace_payload.get("transaction_id"),
        "canonical_rule_id": namespace_payload.get("canonical_rule_id"),
        "package_fingerprint": namespace_payload.get("package_fingerprint"),
        "status": namespace_payload.get("status"),
    }
    filtered = [entry for entry in items if str(entry.get("namespace_id") or "") != str(item["namespace_id"])]
    filtered.append(item)
    filtered.sort(key=lambda entry: str(entry.get("namespace_id") or ""))
    return {"schema_version": TARGET_NAMESPACE_INDEX_SCHEMA_VERSION, "items": filtered, "updated_at_utc": _now()}


def _removed_namespace_index(index: Any, namespace_id: str) -> dict[str, Any]:
    items = list(index.get("items", [])) if isinstance(index, Mapping) else []
    filtered = [entry for entry in items if str(entry.get("namespace_id") or "") != str(namespace_id or "")]
    filtered.sort(key=lambda entry: str(entry.get("namespace_id") or ""))
    return {"schema_version": TARGET_NAMESPACE_INDEX_SCHEMA_VERSION, "items": filtered, "updated_at_utc": _now()}


def _load_all_transactions(base: Path, target_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(_transactions_dir(base, target_id).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping):
            items.append(dict(payload))
    return items


def _committed_namespace_items(base: Path, target_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(_committed_dir(base, target_id).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping):
            items.append(dict(payload))
    return items


def _pending_namespace_items(base: Path, target_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(_pending_dir(base, target_id).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping):
            items.append(dict(payload))
    return items


def _load_transaction(base: Path, target_id: str, transaction_id: str) -> Mapping[str, Any] | None:
    payload = _read_json(_transaction_path(base, target_id, transaction_id))
    return payload if isinstance(payload, Mapping) else None


def _load_pending_namespace(base: Path, target_id: str, transaction_id: str) -> Mapping[str, Any] | None:
    payload = _read_json(_pending_namespace_path(base, target_id, transaction_id))
    return payload if isinstance(payload, Mapping) else None


def _load_committed_namespace(base: Path, target_id: str, namespace_id: str) -> Mapping[str, Any] | None:
    payload = _read_json(_committed_namespace_path(base, target_id, namespace_id))
    return payload if isinstance(payload, Mapping) else None


def _manifest_path(base: Path, target_id: str) -> Path:
    return _target_dir(base, target_id) / "manifest.json"


def _namespace_index_path(base: Path, target_id: str) -> Path:
    return _target_dir(base, target_id) / "namespace_index.json"


def _target_dir(base: Path, target_id: str) -> Path:
    return base / TARGET_ROOT_DIR / _validated_id(target_id)


def _transactions_dir(base: Path, target_id: str) -> Path:
    return _target_dir(base, target_id) / "transactions"


def _pending_dir(base: Path, target_id: str) -> Path:
    return _target_dir(base, target_id) / "pending"


def _committed_dir(base: Path, target_id: str) -> Path:
    return _target_dir(base, target_id) / "namespaces"


def _rollback_dir(base: Path, target_id: str) -> Path:
    return _target_dir(base, target_id) / "rollback_records"


def _transaction_path(base: Path, target_id: str, transaction_id: str) -> Path:
    return _transactions_dir(base, target_id) / f"{_validated_id(transaction_id)}.json"


def _pending_namespace_path(base: Path, target_id: str, transaction_id: str) -> Path:
    return _pending_dir(base, target_id) / f"{_validated_id(transaction_id)}.json"


def _committed_namespace_path(base: Path, target_id: str, namespace_id: str) -> Path:
    return _committed_dir(base, target_id) / f"{_validated_id(namespace_id)}.json"


def _rollback_record_path(base: Path, target_id: str, transaction_id: str) -> Path:
    return _rollback_dir(base, target_id) / f"{_validated_id(transaction_id)}.json"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in items if str(item)))


def _compatibility_package(target_id: str, execution_package: Mapping[str, Any]) -> dict[str, Any]:
    normalized_target_id = _validated_id(target_id)
    legacy_namespace_id = _validated_id(_text(execution_package.get("isolated_namespace_id")) or "ns_legacy")
    canonical_rule_id = _validated_id(_text(execution_package.get("canonical_rule_id")) or "rule_legacy")
    canonical_rule_fingerprint = _text(execution_package.get("canonical_rule_fingerprint"))
    document_id = _validated_id(_text(execution_package.get("document_id")) or "doc_legacy")
    source_revision = _text(execution_package.get("source_revision"))
    rule_schema_version = _text(execution_package.get("rule_schema_version"))
    execution_package_fingerprint = _text(execution_package.get("execution_package_fingerprint"))
    if canonical_rule_fingerprint is None or source_revision is None or rule_schema_version != CANONICAL_RULE_SCHEMA_VERSION or execution_package_fingerprint is None:
        raise ValueError("invalid_legacy_execution_package")
    legacy_seed = {
        "target_id": normalized_target_id,
        "isolated_namespace_id": legacy_namespace_id,
        "canonical_rule_id": canonical_rule_id,
        "canonical_rule_fingerprint": canonical_rule_fingerprint,
        "rule_schema_version": rule_schema_version,
        "document_id": document_id,
        "source_revision": source_revision,
        "execution_package_fingerprint": execution_package_fingerprint,
    }
    stable_suffix = _hash_payload(legacy_seed)[7:23]
    package = {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "package_id": f"pkg_{stable_suffix}",
        "target_id": normalized_target_id,
        "isolated_namespace_id": legacy_namespace_id,
        "execution_package_fingerprint": execution_package_fingerprint,
        "canonical_rule_id": canonical_rule_id,
        "canonical_rule_schema_version": rule_schema_version,
        "canonical_rule_fingerprint": canonical_rule_fingerprint,
        "document_id": document_id,
        "source_revision": source_revision,
        "certification_id": f"cert_{stable_suffix}",
        "certification_fingerprint": canonical_rule_fingerprint,
        "release_candidate_result_id": legacy_namespace_id,
        "release_candidate_fingerprint": execution_package_fingerprint,
        "authorization_result_id": f"auth_{stable_suffix}",
        "authorization_fingerprint": execution_package_fingerprint,
        "scoring_preview_result_id": f"score_{stable_suffix}",
        "scoring_config_id": f"score_cfg_{stable_suffix}",
        "scoring_config_fingerprint": execution_package_fingerprint,
        "fast_lane_preview_result_id": f"fast_{stable_suffix}",
        "fast_lane_contract_id": f"fast_contract_{stable_suffix}",
        "fast_lane_contract_version": "legacy_compatibility_v1",
        "fast_lane_capability_fingerprint": execution_package_fingerprint,
    }
    package["package_fingerprint"] = _integration_package_fingerprint(package)
    return package


def _execution_package_fingerprint(payload: Mapping[str, Any]) -> str:
    return _hash_payload(
        {
            "target_id": payload.get("target_id"),
            "isolated_namespace_id": payload.get("isolated_namespace_id"),
            "canonical_rule_id": payload.get("canonical_rule_id"),
            "canonical_rule_fingerprint": payload.get("canonical_rule_fingerprint"),
            "rule_schema_version": payload.get("rule_schema_version"),
            "document_id": payload.get("document_id"),
            "source_revision": payload.get("source_revision"),
            "canonical_rule_payload": payload.get("canonical_rule_payload"),
        }
    )
