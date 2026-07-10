"""Authoritative pending-then-commit production activation transaction boundary."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from .canonical_rule_runtime import (
    CANONICAL_RULE_SCHEMA_VERSION,
    _atomic_write_json,
    _hash_payload,
    _load_index,
    _read_json,
    _restore_json,
    _rule_fingerprint_from_payload,
    _safe_id,
    create_canonical_rule,
    deactivate_canonical_rule,
    get_canonical_rule_runtime_capability,
    load_canonical_rule,
    validate_canonical_rule_record,
)
from .source_documents import SOURCE_DOCUMENT_ROOT
from .source_knowledge import ensure_source_knowledge_dirs

PACKAGE_SCHEMA_VERSION = "production_activation_transaction_package_v1"
MANIFEST_SCHEMA_VERSION = "production_activation_transaction_manifest_v1"
TRANSACTION_SCHEMA_VERSION = "production_activation_transaction_record_v1"
ROLLBACK_SCHEMA_VERSION = "production_activation_transaction_rollback_v1"
INDEX_SCHEMA_VERSION = "production_activation_transaction_index_v1"

TRANSACTION_DIR = "production_activation_transactions"
PENDING_DIR = "pending"
RECORD_DIR = "records"
ROLLBACK_DIR = "rollback_records"
INDEX_NAME = "production_activation_transaction_index.json"

APPLY_CONFIRMATION = "APPLY_PENDING_PRODUCTION_ACTIVATION"
COMMIT_CONFIRMATION = "COMMIT_PRODUCTION_ACTIVATION"
ROLLBACK_CONFIRMATION = "ROLLBACK_PRODUCTION_ACTIVATION"

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
UNRESOLVED_STATES = {"applying", "pending_verification", "committing", "rolling_back", "rollback_failed"}
PUBLIC_FUNCTIONS = [
    "get_production_activation_transaction_manifest",
    "preflight_production_activation_transaction",
    "apply_production_activation_transaction",
    "read_production_activation_transaction_state",
    "commit_production_activation_transaction",
    "rollback_production_activation_transaction",
    "get_production_activation_transaction_health",
]


def get_production_activation_transaction_manifest(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_dirs(root)
    capability = get_canonical_rule_runtime_capability(root=base)
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "adapter_id": "canonical_rule_runtime_production_activation_transaction",
        "adapter_name": "Canonical Rule Runtime Production Activation Transaction",
        "adapter_version": "1",
        "environment_class": "production",
        "authoritative_state_owner": "canonical_rule_runtime",
        "transaction_mode": "pending_then_explicit_commit",
        "verification_mode": "independent_pending_filesystem_readback",
        "commit_mode": "canonical_rule_runtime_create",
        "rollback_mode": "pending_cleanup_or_committed_rule_deactivation",
        "supports_pending_apply": True,
        "supports_independent_verification": True,
        "supports_explicit_commit": True,
        "supports_rollback": True,
        "supports_one_rule_scope": True,
        "deterministic": True,
        "runtime_available": bool(capability.get("available")),
        "supported_canonical_rule_schema_versions": [CANONICAL_RULE_SCHEMA_VERSION],
        "manifest_fingerprint": None,
    }
    manifest["manifest_fingerprint"] = _hash_payload({key: manifest.get(key) for key in sorted(manifest) if key != "manifest_fingerprint"})
    return manifest


def preflight_production_activation_transaction(
    transaction_package: Mapping[str, Any],
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    manifest = get_production_activation_transaction_manifest(root=base)
    validation = _validate_transaction_package(transaction_package)
    if not validation["valid"]:
        return {
            "status": "blocked" if validation.get("blockers") else "corrupt",
            "transaction_id": None,
            "production_state_fingerprint": _production_state_fingerprint(base),
            "warnings": list(validation.get("warnings", [])),
            "blockers": list(validation.get("blockers", [])),
        }
    package = validation["package"]
    transaction_id = _transaction_id(package)
    production_state_fingerprint = _production_state_fingerprint(base)
    existing = _load_transaction_record(base, transaction_id)
    if isinstance(existing, Mapping):
        state = str(existing.get("transaction_state") or "")
        if state == "committed" and _transaction_commit_verified(base, existing):
            return {
                "status": "already_committed",
                "transaction_id": transaction_id,
                "production_state_fingerprint": production_state_fingerprint,
                "warnings": [],
                "blockers": [],
            }
        if state in UNRESOLVED_STATES:
            return {
                "status": "conflict",
                "transaction_id": transaction_id,
                "production_state_fingerprint": production_state_fingerprint,
                "warnings": [],
                "blockers": ["unresolved_transaction_exists"],
            }
    conflicts = _active_rule_conflicts(base, package)
    if conflicts:
        return {
            "status": "conflict",
            "transaction_id": transaction_id,
            "production_state_fingerprint": production_state_fingerprint,
            "warnings": [],
            "blockers": conflicts,
        }
    pending_conflict = _pending_conflict(base, package, transaction_id)
    if pending_conflict:
        return {
            "status": "conflict",
            "transaction_id": transaction_id,
            "production_state_fingerprint": production_state_fingerprint,
            "warnings": [],
            "blockers": [pending_conflict],
        }
    return {
        "status": "ready",
        "transaction_id": transaction_id,
        "production_state_fingerprint": production_state_fingerprint,
        "manifest_fingerprint": manifest.get("manifest_fingerprint"),
        "package_fingerprint": package.get("package_fingerprint"),
        "canonical_rule_fingerprint": package.get("canonical_rule_fingerprint"),
        "warnings": [],
        "blockers": [],
    }


def apply_production_activation_transaction(
    transaction_package: Mapping[str, Any],
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    if confirmation != APPLY_CONFIRMATION:
        return {"status": "blocked", "warnings": [], "blockers": ["apply_confirmation_required"]}
    preflight = preflight_production_activation_transaction(transaction_package, root=base)
    if preflight.get("status") != "ready":
        return dict(preflight)
    package = _validate_transaction_package(transaction_package)["package"]
    transaction_id = str(preflight["transaction_id"])
    record = _build_transaction_record(package, transaction_id, production_state_fingerprint=str(preflight["production_state_fingerprint"]), state="applying")
    pending_state_fingerprint = _pending_state_fingerprint(record)
    record["pending_state_fingerprint"] = pending_state_fingerprint
    before_record = _read_json(_record_path(base, transaction_id))
    before_pending = _read_json(_pending_path(base, transaction_id))
    before_index = _read_json(_index_path(base))
    try:
        _atomic_write_json(_record_path(base, transaction_id), record)
        _atomic_write_json(_pending_path(base, transaction_id), package)
        pending_payload = _read_json(_pending_path(base, transaction_id))
        if not isinstance(pending_payload, Mapping) or str(pending_payload.get("package_fingerprint") or "") != str(package.get("package_fingerprint") or ""):
            raise RuntimeError("pending_readback_failed")
        record["transaction_state"] = "pending_verification"
        record["verification_status"] = "verified_pending"
        record["pending_state_fingerprint"] = _pending_state_fingerprint(record)
        _atomic_write_json(_record_path(base, transaction_id), record)
        _write_index(base)
    except Exception:
        _restore_json(_record_path(base, transaction_id), before_record)
        _restore_json(_pending_path(base, transaction_id), before_pending)
        _restore_json(_index_path(base), before_index)
        return {"status": "apply_failed", "transaction_id": transaction_id, "warnings": [], "blockers": ["pending_apply_write_failure"]}
    return {
        "status": "pending_verification",
        "transaction_id": transaction_id,
        "transaction_state": "pending_verification",
        "pending_state_fingerprint": record["pending_state_fingerprint"],
        "verification_status": "verified_pending",
        "warnings": [],
        "blockers": [],
    }


def read_production_activation_transaction_state(
    transaction_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    record = _load_transaction_record(base, transaction_id)
    if not isinstance(record, Mapping):
        return {"status": "not_found", "transaction_id": transaction_id, "warnings": [], "blockers": ["transaction_not_found"]}
    pending = _read_json(_pending_path(base, transaction_id))
    verification_status = "unverified"
    if str(record.get("transaction_state") or "") == "pending_verification":
        if (
            isinstance(pending, Mapping)
            and str(pending.get("package_fingerprint") or "") == str(record.get("package_fingerprint") or "")
            and str(record.get("pending_state_fingerprint") or "") == _pending_state_fingerprint(record)
        ):
            verification_status = "verified_pending"
    elif str(record.get("transaction_state") or "") == "committed":
        verification_status = "verified_committed" if _transaction_commit_verified(base, record) else "commit_verification_failed"
    return {
        "status": "loaded",
        "transaction_id": transaction_id,
        "transaction_state": record.get("transaction_state"),
        "canonical_rule_id": record.get("canonical_rule_id"),
        "deployed_rule_id": record.get("deployed_rule_id") or record.get("committed_rule_id"),
        "committed_rule_id": record.get("committed_rule_id"),
        "document_id": record.get("document_id"),
        "source_revision": record.get("source_revision"),
        "deployment_package_fingerprint": record.get("deployment_package_fingerprint"),
        "package_fingerprint": record.get("package_fingerprint"),
        "canonical_rule_fingerprint": record.get("canonical_rule_fingerprint"),
        "production_authorization_fingerprint": record.get("production_authorization_fingerprint"),
        "pending_state_fingerprint": record.get("pending_state_fingerprint"),
        "verification_status": verification_status,
        "warnings": [],
        "blockers": [],
    }


def commit_production_activation_transaction(
    transaction_id: str,
    expected_pending_state_fingerprint: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    if confirmation != COMMIT_CONFIRMATION:
        return {"status": "blocked", "transaction_id": transaction_id, "warnings": [], "blockers": ["commit_confirmation_required"]}
    record = _load_transaction_record(base, transaction_id)
    if not isinstance(record, Mapping):
        return {"status": "blocked", "transaction_id": transaction_id, "warnings": [], "blockers": ["transaction_not_found"]}
    state = str(record.get("transaction_state") or "")
    if state == "committed" and _transaction_commit_verified(base, record):
        return {"status": "already_committed", "transaction_id": transaction_id, "warnings": [], "blockers": []}
    if state != "pending_verification":
        return {"status": "blocked", "transaction_id": transaction_id, "warnings": [], "blockers": ["transaction_state_invalid_for_commit"]}
    readback = read_production_activation_transaction_state(transaction_id, root=base)
    if str(readback.get("verification_status") or "") != "verified_pending":
        return {"status": "blocked", "transaction_id": transaction_id, "warnings": [], "blockers": ["pending_state_not_verified"]}
    if str(expected_pending_state_fingerprint or "") != str(record.get("pending_state_fingerprint") or ""):
        return {"status": "blocked", "transaction_id": transaction_id, "warnings": [], "blockers": ["pending_state_fingerprint_mismatch"]}
    current_state_fingerprint = _production_state_fingerprint(base)
    if str(current_state_fingerprint or "") != str(record.get("preflight_production_state_fingerprint") or ""):
        return {"status": "blocked", "transaction_id": transaction_id, "warnings": [], "blockers": ["production_state_fingerprint_drift"]}
    pending_package = _read_json(_pending_path(base, transaction_id))
    if not isinstance(pending_package, Mapping):
        return {"status": "blocked", "transaction_id": transaction_id, "warnings": [], "blockers": ["pending_package_missing"]}
    validation = _validate_transaction_package(pending_package)
    if not validation["valid"]:
        return {"status": "blocked", "transaction_id": transaction_id, "warnings": [], "blockers": list(validation.get("blockers", []))}
    package = validation["package"]
    conflicts = _active_rule_conflicts(base, package)
    if conflicts:
        return {"status": "conflict", "transaction_id": transaction_id, "warnings": [], "blockers": conflicts}
    committing = dict(record)
    committing["transaction_state"] = "committing"
    before_record = _read_json(_record_path(base, transaction_id))
    before_pending = _read_json(_pending_path(base, transaction_id))
    before_index = _read_json(_index_path(base))
    try:
        _atomic_write_json(_record_path(base, transaction_id), committing)
        created = create_canonical_rule(_rule_payload_for_commit(package, transaction_id), confirmation="CREATE_RULE", root=base)
        if str(created.get("status") or "") not in {"created", "already_created"}:
            raise RuntimeError("canonical_rule_create_failed")
        deployed_rule_id = _deployed_rule_id(package, transaction_id)
        loaded = load_canonical_rule(deployed_rule_id, require_active=True, root=base)
        rule = loaded.get("rule") if isinstance(loaded.get("rule"), Mapping) else None
        if loaded.get("status") != "loaded" or not isinstance(rule, Mapping):
            raise RuntimeError("canonical_rule_load_verification_failed")
        if not _committed_rule_matches(rule, package, transaction_id):
            raise RuntimeError("canonical_rule_committed_state_mismatch")
        committed = dict(committing)
        committed["transaction_state"] = "committed"
        committed["committed_rule_id"] = rule.get("rule_id")
        committed["committed_rule_fingerprint"] = rule.get("rule_fingerprint")
        committed["committed_production_state_fingerprint"] = _production_state_fingerprint(base)
        _atomic_write_json(_record_path(base, transaction_id), committed)
        _delete_json(_pending_path(base, transaction_id))
        _write_index(base)
    except Exception:
        _restore_json(_record_path(base, transaction_id), before_record)
        _restore_json(_pending_path(base, transaction_id), before_pending)
        _restore_json(_index_path(base), before_index)
        return {"status": "commit_failed", "transaction_id": transaction_id, "warnings": [], "blockers": ["production_activation_commit_failed"]}
    return {
        "status": "committed",
        "transaction_id": transaction_id,
        "canonical_rule_id": package.get("canonical_rule_id"),
        "committed_rule_id": committed.get("committed_rule_id"),
        "committed_production_state_fingerprint": _production_state_fingerprint(base),
        "warnings": [],
        "blockers": [],
    }


def rollback_production_activation_transaction(
    transaction_id: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    if confirmation != ROLLBACK_CONFIRMATION:
        return {"status": "blocked", "transaction_id": transaction_id, "warnings": [], "blockers": ["rollback_confirmation_required"]}
    record = _load_transaction_record(base, transaction_id)
    if not isinstance(record, Mapping):
        return {"status": "blocked", "transaction_id": transaction_id, "warnings": [], "blockers": ["transaction_not_found"]}
    state = str(record.get("transaction_state") or "")
    if state == "rolled_back":
        return {"status": "already_rolled_back", "transaction_id": transaction_id, "warnings": [], "blockers": []}
    if state not in {"pending_verification", "committed", "apply_failed", "commit_failed"}:
        return {"status": "blocked", "transaction_id": transaction_id, "warnings": [], "blockers": ["transaction_state_invalid_for_rollback"]}
    before_record = _read_json(_record_path(base, transaction_id))
    before_pending = _read_json(_pending_path(base, transaction_id))
    before_index = _read_json(_index_path(base))
    rollback_record_path = _rollback_path(base, transaction_id)
    before_rollback = _read_json(rollback_record_path)
    rolling = dict(record)
    rolling["transaction_state"] = "rolling_back"
    try:
        _atomic_write_json(_record_path(base, transaction_id), rolling)
        if state == "pending_verification":
            _delete_json(_pending_path(base, transaction_id))
            if _pending_path(base, transaction_id).exists():
                raise RuntimeError("pending_cleanup_failed")
        else:
            loaded = load_canonical_rule(str(record.get("committed_rule_id") or record.get("deployed_rule_id") or ""), root=base)
            rule = loaded.get("rule") if isinstance(loaded.get("rule"), Mapping) else None
            if loaded.get("status") != "loaded" or not isinstance(rule, Mapping):
                raise RuntimeError("committed_rule_missing_for_rollback")
            if str(rule.get("production_activation_transaction_id") or "") != transaction_id:
                raise RuntimeError("rollback_transaction_ownership_mismatch")
            deactivated = deactivate_canonical_rule(
                str(rule.get("rule_id") or ""),
                reason=f"production_activation_transaction:{transaction_id}",
                confirmation="DEACTIVATE_RULE",
                root=base,
            )
            if str(deactivated.get("status") or "") not in {"deactivated", "already_deactivated"}:
                raise RuntimeError("canonical_rule_deactivation_failed")
            reloaded = load_canonical_rule(str(rule.get("rule_id") or ""), root=base)
            rerecord = reloaded.get("rule") if isinstance(reloaded.get("rule"), Mapping) else None
            if not isinstance(rerecord, Mapping) or str(rerecord.get("status") or "") == "active":
                raise RuntimeError("committed_rule_still_active_after_rollback")
            rollback_record = {
                "schema_version": ROLLBACK_SCHEMA_VERSION,
                "transaction_id": transaction_id,
                "canonical_rule_id": record.get("canonical_rule_id"),
                "rolled_back_rule_id": rule.get("rule_id"),
                "rolled_back_rule_fingerprint": rerecord.get("rule_fingerprint"),
                "package_fingerprint": record.get("package_fingerprint"),
                "rollback_state_fingerprint": _hash_payload(
                    {
                        "transaction_id": transaction_id,
                        "canonical_rule_id": record.get("canonical_rule_id"),
                        "rolled_back_rule_id": rule.get("rule_id"),
                        "rolled_back_rule_fingerprint": rerecord.get("rule_fingerprint"),
                        "package_fingerprint": record.get("package_fingerprint"),
                    }
                ),
            }
            _atomic_write_json(rollback_record_path, rollback_record)
        rolled = dict(record)
        rolled["transaction_state"] = "rolled_back"
        _atomic_write_json(_record_path(base, transaction_id), rolled)
        _write_index(base)
    except Exception:
        _restore_json(_record_path(base, transaction_id), before_record)
        _restore_json(_pending_path(base, transaction_id), before_pending)
        _restore_json(_index_path(base), before_index)
        _restore_json(rollback_record_path, before_rollback)
        return {"status": "rollback_failed", "transaction_id": transaction_id, "warnings": [], "blockers": ["production_activation_rollback_failed"]}
    return {"status": "completed", "transaction_id": transaction_id, "warnings": [], "blockers": []}


def get_production_activation_transaction_health(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_dirs(root)
    records = _load_all_records(base)
    pending = list((_pending_root(base)).glob("*.json"))
    return {
        "status": "healthy" if not any(str(item.get("transaction_state") or "") in {"apply_failed", "commit_failed", "rollback_failed"} for item in records) else "warning",
        "transaction_count": len(records),
        "pending_count": len(pending),
        "committed_count": sum(1 for item in records if str(item.get("transaction_state") or "") == "committed"),
        "rolled_back_count": sum(1 for item in records if str(item.get("transaction_state") or "") == "rolled_back"),
        "warnings": [],
        "blockers": [],
    }


def _validate_transaction_package(transaction_package: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(transaction_package, Mapping):
        return {"valid": False, "warnings": [], "blockers": ["transaction_package_invalid"]}
    disallowed = set(transaction_package.keys()) - {
        "schema_version",
        "transaction_package_id",
        "canonical_rule_id",
        "canonical_rule_schema_version",
        "canonical_rule_fingerprint",
        "canonical_rule_payload",
        "document_id",
        "source_revision",
        "certification_id",
        "certification_fingerprint",
        "production_authorization_result_id",
        "production_authorization_fingerprint",
        "production_target_id",
        "production_target_descriptor_fingerprint",
        "deployment_package_fingerprint",
        "package_fingerprint",
    }
    blockers: list[str] = []
    if disallowed:
        blockers.append("transaction_package_contains_unsupported_fields")
    if _contains_unsafe_content(transaction_package):
        blockers.append("transaction_package_contains_unsafe_content")
    package = deepcopy(dict(transaction_package))
    if str(package.get("schema_version") or "") != PACKAGE_SCHEMA_VERSION:
        blockers.append("transaction_package_schema_unsupported")
    if str(package.get("canonical_rule_schema_version") or "") != CANONICAL_RULE_SCHEMA_VERSION:
        blockers.append("transaction_package_rule_schema_unsupported")
    if isinstance(package.get("source_revision"), bool) or not isinstance(package.get("source_revision"), int) or int(package.get("source_revision") or 0) <= 0:
        blockers.append("transaction_package_source_revision_invalid")
    for field in (
        "transaction_package_id",
        "canonical_rule_id",
        "document_id",
        "certification_id",
        "certification_fingerprint",
        "production_authorization_result_id",
        "production_authorization_fingerprint",
        "production_target_id",
        "production_target_descriptor_fingerprint",
        "deployment_package_fingerprint",
        "package_fingerprint",
        "canonical_rule_fingerprint",
    ):
        if not _non_empty_text(package.get(field)):
            blockers.append(f"{field}_required")
    rule_payload = package.get("canonical_rule_payload")
    if not isinstance(rule_payload, Mapping):
        blockers.append("canonical_rule_payload_invalid")
    else:
        rule_validation = validate_canonical_rule_record(dict(rule_payload), require_active=True)
        if not rule_validation.get("valid"):
            blockers.extend(list(rule_validation.get("blockers", [])))
        else:
            if str(rule_validation.get("rule_id") or "") != str(package.get("canonical_rule_id") or ""):
                blockers.append("canonical_rule_id_mismatch")
            if str(rule_validation.get("rule_fingerprint") or "") != str(package.get("canonical_rule_fingerprint") or ""):
                blockers.append("canonical_rule_fingerprint_mismatch")
            if str((rule_payload or {}).get("document_id") or "") != str(package.get("document_id") or ""):
                blockers.append("canonical_rule_document_id_mismatch")
            if str((rule_payload or {}).get("source_revision") or "") != str(package.get("source_revision") or ""):
                blockers.append("canonical_rule_source_revision_mismatch")
    normalized = _normalized_package(package)
    if str(package.get("package_fingerprint") or "") != _package_fingerprint(normalized):
        blockers.append("transaction_package_fingerprint_mismatch")
    return {"valid": not blockers, "package": normalized, "warnings": [], "blockers": list(dict.fromkeys(blockers))}


def _normalized_package(package: Mapping[str, Any]) -> dict[str, Any]:
    payload = deepcopy(dict(package))
    payload["canonical_rule_payload"] = deepcopy(dict(payload.get("canonical_rule_payload") or {}))
    return payload


def _rule_payload_for_commit(package: Mapping[str, Any], transaction_id: str) -> dict[str, Any]:
    payload = deepcopy(dict(package.get("canonical_rule_payload") or {}))
    payload["source_canonical_rule_id"] = package.get("canonical_rule_id")
    payload["source_canonical_rule_fingerprint"] = package.get("canonical_rule_fingerprint")
    payload["rule_id"] = _deployed_rule_id(package, transaction_id)
    payload["production_activation_transaction_id"] = transaction_id
    payload["certification_id"] = package.get("certification_id")
    payload["certification_fingerprint"] = package.get("certification_fingerprint")
    payload["production_authorization_result_id"] = package.get("production_authorization_result_id")
    payload["production_authorization_fingerprint"] = package.get("production_authorization_fingerprint")
    payload["production_target_id"] = package.get("production_target_id")
    payload["production_target_descriptor_fingerprint"] = package.get("production_target_descriptor_fingerprint")
    payload["rule_fingerprint"] = _rule_fingerprint_from_payload(payload)
    return payload


def _build_transaction_record(package: Mapping[str, Any], transaction_id: str, *, production_state_fingerprint: str, state: str) -> dict[str, Any]:
    return {
        "schema_version": TRANSACTION_SCHEMA_VERSION,
        "transaction_id": transaction_id,
        "transaction_package_id": package.get("transaction_package_id"),
        "canonical_rule_id": package.get("canonical_rule_id"),
        "document_id": package.get("document_id"),
        "source_revision": package.get("source_revision"),
        "canonical_rule_fingerprint": package.get("canonical_rule_fingerprint"),
        "deployed_rule_id": _deployed_rule_id(package, transaction_id),
        "production_authorization_fingerprint": package.get("production_authorization_fingerprint"),
        "production_target_id": package.get("production_target_id"),
        "production_target_descriptor_fingerprint": package.get("production_target_descriptor_fingerprint"),
        "deployment_package_fingerprint": package.get("deployment_package_fingerprint"),
        "package_fingerprint": package.get("package_fingerprint"),
        "transaction_state": state,
        "verification_status": "pending",
        "preflight_production_state_fingerprint": production_state_fingerprint,
        "pending_state_fingerprint": None,
        "committed_production_state_fingerprint": None,
    }


def _transaction_id(package: Mapping[str, Any]) -> str:
    return "production_activation_tx_" + _hash_payload(
        {
            "canonical_rule_id": package.get("canonical_rule_id"),
            "canonical_rule_fingerprint": package.get("canonical_rule_fingerprint"),
            "document_id": package.get("document_id"),
            "source_revision": package.get("source_revision"),
            "certification_fingerprint": package.get("certification_fingerprint"),
            "production_authorization_fingerprint": package.get("production_authorization_fingerprint"),
            "production_target_id": package.get("production_target_id"),
            "production_target_descriptor_fingerprint": package.get("production_target_descriptor_fingerprint"),
            "package_fingerprint": package.get("package_fingerprint"),
        }
    )[7:23]


def _package_fingerprint(package: Mapping[str, Any]) -> str:
    return _hash_payload({key: package.get(key) for key in sorted(package) if key != "package_fingerprint"})


def _pending_state_fingerprint(record: Mapping[str, Any]) -> str:
    return _hash_payload(
        {
            "transaction_id": record.get("transaction_id"),
            "canonical_rule_id": record.get("canonical_rule_id"),
            "document_id": record.get("document_id"),
            "source_revision": record.get("source_revision"),
            "package_fingerprint": record.get("package_fingerprint"),
            "canonical_rule_fingerprint": record.get("canonical_rule_fingerprint"),
            "production_authorization_fingerprint": record.get("production_authorization_fingerprint"),
            "transaction_state": record.get("transaction_state"),
        }
    )


def _production_state_fingerprint(base: Path) -> str:
    index = _load_index(base)
    active_ids = sorted(str(item) for item in index.get("active_rule_ids", []))
    fingerprints = {rule_id: str((index.get("rule_fingerprints") or {}).get(rule_id) or "") for rule_id in active_ids}
    return _hash_payload(
        {
            "schema_version": "canonical_rule_production_state_snapshot_v1",
            "active_rule_ids": active_ids,
            "rule_fingerprints": fingerprints,
        }
    )


def _active_rule_conflicts(base: Path, package: Mapping[str, Any]) -> list[str]:
    loaded = load_canonical_rule(str(package.get("canonical_rule_id") or ""), require_active=True, root=base)
    if loaded.get("status") == "loaded":
        rule = loaded.get("rule") if isinstance(loaded.get("rule"), Mapping) else {}
        if str(rule.get("rule_fingerprint") or "") != str(package.get("canonical_rule_fingerprint") or ""):
            return ["canonical_rule_id_conflict"]
    else:
        return ["canonical_source_rule_missing"]
    deployed_rule_id = _deployed_rule_id(package, _transaction_id(package))
    deployed_loaded = load_canonical_rule(deployed_rule_id, require_active=True, root=base)
    if deployed_loaded.get("status") == "loaded":
        deployed_rule = deployed_loaded.get("rule") if isinstance(deployed_loaded.get("rule"), Mapping) else {}
        if _committed_rule_matches(deployed_rule, package, _transaction_id(package)):
            return ["deployed_rule_already_active"]
        return ["deployed_rule_id_conflict"]
    conflicts: list[str] = []
    active_rules = []
    from .canonical_rule_runtime import list_canonical_rules  # local import to avoid expanding public surface

    active_rules = list_canonical_rules(status="active", limit=500, root=base).get("items", [])
    target = str(((package.get("canonical_rule_payload") or {}).get("target")) or "")
    scope = str(((package.get("canonical_rule_payload") or {}).get("scope")) or "")
    value = (package.get("canonical_rule_payload") or {}).get("value")
    for item in active_rules:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("target") or "") == target and str(item.get("scope") or "") == scope and item.get("value") != value:
            conflicts.append("active_rule_conflict_exists")
            break
    return conflicts


def _pending_conflict(base: Path, package: Mapping[str, Any], transaction_id: str) -> str | None:
    for item in _load_all_records(base):
        if str(item.get("transaction_id") or "") == transaction_id:
            continue
        if str(item.get("transaction_state") or "") not in UNRESOLVED_STATES:
            continue
        if str(item.get("canonical_rule_id") or "") == str(package.get("canonical_rule_id") or ""):
            return "conflicting_pending_transaction_exists"
    return None


def _transaction_commit_verified(base: Path, record: Mapping[str, Any]) -> bool:
    loaded = load_canonical_rule(str(record.get("committed_rule_id") or record.get("deployed_rule_id") or ""), require_active=True, root=base)
    rule = loaded.get("rule") if isinstance(loaded.get("rule"), Mapping) else None
    return loaded.get("status") == "loaded" and isinstance(rule, Mapping) and _committed_rule_matches(rule, record, str(record.get("transaction_id") or ""))


def _committed_rule_matches(rule: Mapping[str, Any], package_or_record: Mapping[str, Any], transaction_id: str) -> bool:
    payload = package_or_record.get("canonical_rule_payload") if isinstance(package_or_record.get("canonical_rule_payload"), Mapping) else package_or_record
    expected_deployed_rule_id = str(package_or_record.get("committed_rule_id") or package_or_record.get("deployed_rule_id") or _deployed_rule_id(package_or_record, transaction_id))
    expected_target = (payload or {}).get("target") if isinstance(payload, Mapping) else None
    return (
        str(rule.get("rule_id") or "") == expected_deployed_rule_id
        and str(rule.get("document_id") or "") == str(package_or_record.get("document_id") or "")
        and str(rule.get("source_revision") or "") == str(package_or_record.get("source_revision") or "")
        and str(rule.get("certification_id") or "") == str(package_or_record.get("certification_id") or "")
        and str(rule.get("certification_fingerprint") or "") == str(package_or_record.get("certification_fingerprint") or "")
        and str(rule.get("production_authorization_result_id") or "") == str(package_or_record.get("production_authorization_result_id") or "")
        and str(rule.get("production_authorization_fingerprint") or "") == str(package_or_record.get("production_authorization_fingerprint") or "")
        and str(rule.get("source_canonical_rule_id") or "") == str(package_or_record.get("canonical_rule_id") or "")
        and str(rule.get("source_canonical_rule_fingerprint") or "") == str(package_or_record.get("canonical_rule_fingerprint") or "")
        and str(rule.get("production_activation_transaction_id") or "") == transaction_id
        and str(rule.get("status") or "") == "active"
        and str(rule.get("rule_fingerprint") or "") == str(_rule_fingerprint_from_payload(dict(rule)) or "")
        and (expected_target is None or str(expected_target or "") == str(rule.get("target") or ""))
    )


def _deployed_rule_id(package_or_record: Mapping[str, Any], transaction_id: str) -> str:
    return "production_deployed_rule_" + _hash_payload(
        {
            "transaction_id": transaction_id,
            "canonical_rule_id": package_or_record.get("canonical_rule_id"),
            "canonical_rule_fingerprint": package_or_record.get("canonical_rule_fingerprint"),
            "production_target_id": package_or_record.get("production_target_id"),
        }
    )[7:23]


def _contains_unsafe_content(value: Any) -> bool:
    forbidden_keys = {
        "callback",
        "callbacks",
        "script",
        "scripts",
        "credential",
        "credentials",
        "secret",
        "secrets",
        "token",
        "tokens",
        "command",
        "commands",
        "path",
        "paths",
        "route",
        "routes",
        "routing",
    }
    if callable(value):
        return True
    if isinstance(value, Mapping):
        for key, item in value.items():
            text = str(key).lower()
            if text in forbidden_keys:
                return True
            if _contains_unsafe_content(item):
                return True
        return False
    if isinstance(value, (list, tuple, set)):
        return any(_contains_unsafe_content(item) for item in value)
    return False


def _ensure_dirs(root: Path | str) -> Path:
    base = ensure_source_knowledge_dirs(root)
    (_transaction_root(base) / PENDING_DIR).mkdir(parents=True, exist_ok=True)
    (_transaction_root(base) / RECORD_DIR).mkdir(parents=True, exist_ok=True)
    (_transaction_root(base) / ROLLBACK_DIR).mkdir(parents=True, exist_ok=True)
    (base / "indexes").mkdir(parents=True, exist_ok=True)
    if not _index_path(base).exists():
        _atomic_write_json(_index_path(base), {"schema_version": INDEX_SCHEMA_VERSION, "items": []})
    return base


def _transaction_root(base: Path) -> Path:
    return base / TRANSACTION_DIR


def _pending_root(base: Path) -> Path:
    return _transaction_root(base) / PENDING_DIR


def _record_root(base: Path) -> Path:
    return _transaction_root(base) / RECORD_DIR


def _rollback_root(base: Path) -> Path:
    return _transaction_root(base) / ROLLBACK_DIR


def _pending_path(base: Path, transaction_id: str) -> Path:
    return _pending_root(base) / f"{_safe_id(transaction_id)}.json"


def _record_path(base: Path, transaction_id: str) -> Path:
    return _record_root(base) / f"{_safe_id(transaction_id)}.json"


def _rollback_path(base: Path, transaction_id: str) -> Path:
    return _rollback_root(base) / f"{_safe_id(transaction_id)}.json"


def _index_path(base: Path) -> Path:
    return base / "indexes" / INDEX_NAME


def _load_transaction_record(base: Path, transaction_id: str) -> dict[str, Any] | None:
    payload = _read_json(_record_path(base, transaction_id))
    return dict(payload) if isinstance(payload, Mapping) else None


def _load_all_records(base: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(_record_root(base).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping):
            items.append(dict(payload))
    return items


def _write_index(base: Path) -> None:
    items = []
    for item in _load_all_records(base):
        items.append(
            {
                "transaction_id": item.get("transaction_id"),
                "canonical_rule_id": item.get("canonical_rule_id"),
                "document_id": item.get("document_id"),
                "source_revision": item.get("source_revision"),
                "transaction_state": item.get("transaction_state"),
                "package_fingerprint": item.get("package_fingerprint"),
            }
        )
    items.sort(key=lambda entry: str(entry.get("transaction_id") or ""))
    _atomic_write_json(_index_path(base), {"schema_version": INDEX_SCHEMA_VERSION, "items": items})


def _delete_json(path: Path) -> None:
    if path.exists():
        path.unlink()


def _non_empty_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
