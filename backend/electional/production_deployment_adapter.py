"""Stable production deployment adapter over the production activation transaction foundation."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from . import production_activation_transaction as tx_backend
from . import production_target_descriptor as descriptor_backend
from .canonical_rule_runtime import (
    CANONICAL_RULE_SCHEMA_VERSION,
    _hash_payload,
    _rule_fingerprint_from_payload,
    list_canonical_rules,
    load_canonical_rule,
    validate_canonical_rule_record,
)
from .source_documents import SOURCE_DOCUMENT_ROOT

DEPLOYMENT_PACKAGE_SCHEMA_VERSION = "production_deployment_package_v1"
ADAPTER_SCHEMA_VERSION = "production_deployment_adapter_manifest_v1"
APPLY_CONFIRMATION = "APPLY_AUTHORIZED_PRODUCTION_DEPLOYMENT"
COMMIT_CONFIRMATION = "COMMIT_AUTHORIZED_PRODUCTION_DEPLOYMENT"
ROLLBACK_CONFIRMATION = "ROLLBACK_AUTHORIZED_PRODUCTION_DEPLOYMENT"
PUBLIC_FUNCTIONS = [
    "get_production_deployment_adapter_manifest",
    "get_production_deployment_target_workspace",
    "validate_production_deployment_package",
    "preflight_production_deployment",
    "read_production_deployment_state",
    "apply_production_deployment",
    "verify_production_deployment",
    "commit_production_deployment",
    "rollback_production_deployment",
]


def get_production_deployment_adapter_manifest(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    tx_manifest = tx_backend.get_production_activation_transaction_manifest(root=root)
    manifest = {
        "schema_version": ADAPTER_SCHEMA_VERSION,
        "adapter_id": "production_deployment_adapter_v1",
        "adapter_name": "Production Deployment Adapter",
        "adapter_version": "1",
        "environment_class": "production",
        "authoritative_state_owner": "canonical_rule_runtime",
        "target_descriptor_schema_versions": [descriptor_backend.DESCRIPTOR_SCHEMA_VERSION],
        "deployment_package_schema_versions": [DEPLOYMENT_PACKAGE_SCHEMA_VERSION],
        "activation_transaction_schema_versions": [tx_backend.PACKAGE_SCHEMA_VERSION, tx_backend.TRANSACTION_SCHEMA_VERSION],
        "supported_canonical_rule_schemas": [CANONICAL_RULE_SCHEMA_VERSION],
        "transaction_foundation_module": "production_activation_transaction",
        "preflight_mode": "read_only_descriptor_and_transaction_preflight",
        "apply_mode": "pending_only_apply",
        "verification_mode": "independent_persisted_state_readback",
        "commit_mode": "explicit_canonical_rule_commit",
        "rollback_mode": "pending_cleanup_or_exact_committed_rule_deactivation",
        "one_rule_scope": True,
        "deterministic": True,
        "adapter_fingerprint": None,
        "transaction_manifest_fingerprint": tx_manifest.get("manifest_fingerprint"),
    }
    manifest["adapter_fingerprint"] = _hash_payload({key: manifest.get(key) for key in sorted(manifest) if key != "adapter_fingerprint"})
    return manifest


def get_production_deployment_target_workspace(
    production_target_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    descriptor_loaded = descriptor_backend.load_production_target_descriptor(production_target_id, root=root)
    descriptor = descriptor_loaded.get("production_target_descriptor") if isinstance(descriptor_loaded.get("production_target_descriptor"), Mapping) else {}
    descriptor_health = descriptor_backend.get_production_target_descriptor_health(production_target_id, root=root)
    manifest = get_production_deployment_adapter_manifest(root=root)
    blockers = list(descriptor_loaded.get("blockers", []))
    warnings = list(descriptor_loaded.get("warnings", [])) + list(descriptor_health.get("warnings", []))
    if str(descriptor.get("environment_class") or "") != "production":
        blockers.append("production_target_environment_invalid")
    if str(descriptor.get("target_kind") or "") != descriptor_backend.TARGET_KIND:
        blockers.append("production_target_kind_invalid")
    if str(descriptor.get("descriptor_access_mode") or "") != descriptor_backend.ACCESS_MODE:
        blockers.append("production_target_access_mode_invalid")
    if list(descriptor.get("operational_entrypoints_exposed") or []):
        blockers.append("production_target_operational_entrypoints_forbidden")
    current_state_fingerprint = tx_backend._production_state_fingerprint(Path(root))
    active_rules = list_canonical_rules(status="active", limit=500, root=root).get("items", [])
    active_ids = sorted(str(item.get("rule_id") or "") for item in active_rules if isinstance(item, Mapping))
    health_status = "healthy"
    if blockers:
        health_status = "blocked"
    elif str(descriptor_health.get("status") or "") not in {"healthy", "warning"}:
        health_status = "unknown" if str(descriptor_health.get("status") or "") == "empty" else "warning"
    elif warnings:
        health_status = "warning"
    return {
        "status": health_status,
        "production_target_id": production_target_id,
        "production_target_descriptor": descriptor if descriptor else None,
        "descriptor_fingerprint": descriptor.get("descriptor_fingerprint"),
        "adapter_manifest": manifest,
        "adapter_fingerprint": manifest.get("adapter_fingerprint"),
        "environment_class": descriptor.get("environment_class", "unknown"),
        "target_kind": descriptor.get("target_kind", "unknown"),
        "adapter_name": descriptor.get("adapter_name", "unknown"),
        "adapter_version": descriptor.get("adapter_version", "unknown"),
        "production_state_owner": manifest.get("authoritative_state_owner"),
        "current_production_state_fingerprint": current_state_fingerprint,
        "current_active_rule_id": active_ids[0] if len(active_ids) == 1 else None,
        "current_active_rule_ids": active_ids,
        "operation_capability_status": "available",
        "target_health": descriptor_health.get("status", "unknown"),
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
    }


def validate_production_deployment_package(
    production_target_id: str,
    deployment_package: Mapping[str, Any],
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    workspace = get_production_deployment_target_workspace(production_target_id, root=root)
    blockers = list(workspace.get("blockers", []))
    warnings = list(workspace.get("warnings", []))
    if workspace.get("status") not in {"healthy", "warning"}:
        return {
            "status": "blocked",
            "package_fingerprint": None,
            "target_descriptor_fingerprint": workspace.get("descriptor_fingerprint"),
            "transaction_package_fingerprint": None,
            "warnings": warnings,
            "blockers": _dedupe(blockers or ["production_target_workspace_unhealthy"]),
        }
    validation = _validate_package_internal(workspace, deployment_package)
    return {
        "status": "valid" if validation["valid"] else "blocked",
        "package_fingerprint": validation.get("package_fingerprint"),
        "target_descriptor_fingerprint": workspace.get("descriptor_fingerprint"),
        "transaction_package_fingerprint": validation.get("transaction_package_fingerprint"),
        "warnings": list(validation.get("warnings", [])),
        "blockers": list(validation.get("blockers", [])),
    }


def preflight_production_deployment(
    production_target_id: str,
    deployment_package: Mapping[str, Any],
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    workspace = get_production_deployment_target_workspace(production_target_id, root=root)
    if workspace.get("status") not in {"healthy", "warning"}:
        return {
            "status": "target_unhealthy",
            "production_target_id": production_target_id,
            "deployment_package_fingerprint": None,
            "transaction_package_fingerprint": None,
            "transaction_id": None,
            "current_production_state_fingerprint": workspace.get("current_production_state_fingerprint"),
            "current_active_rule_identity": workspace.get("current_active_rule_id"),
            "warnings": list(workspace.get("warnings", [])),
            "blockers": list(workspace.get("blockers", [])) or ["production_target_workspace_unhealthy"],
        }
    package_validation = _validate_package_internal(workspace, deployment_package)
    if not package_validation["valid"]:
        return {
            "status": "blocked",
            "production_target_id": production_target_id,
            "deployment_package_fingerprint": package_validation.get("package_fingerprint"),
            "transaction_package_fingerprint": package_validation.get("transaction_package_fingerprint"),
            "transaction_id": None,
            "current_production_state_fingerprint": workspace.get("current_production_state_fingerprint"),
            "current_active_rule_identity": workspace.get("current_active_rule_id"),
            "warnings": list(package_validation.get("warnings", [])),
            "blockers": list(package_validation.get("blockers", [])),
        }
    tx_package = package_validation["transaction_package"]
    preflight = tx_backend.preflight_production_activation_transaction(tx_package, root=root)
    return {
        "status": str(preflight.get("status") or "unknown"),
        "production_target_id": production_target_id,
        "deployment_package_fingerprint": package_validation.get("package_fingerprint"),
        "transaction_package_fingerprint": package_validation.get("transaction_package_fingerprint"),
        "transaction_id": preflight.get("transaction_id"),
        "current_production_state_fingerprint": preflight.get("production_state_fingerprint"),
        "current_active_rule_identity": workspace.get("current_active_rule_id"),
        "warnings": _dedupe(list(workspace.get("warnings", [])) + list(preflight.get("warnings", []))),
        "blockers": _dedupe(list(preflight.get("blockers", []))),
    }


def read_production_deployment_state(
    production_target_id: str,
    transaction_id: str | None = None,
    canonical_rule_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    workspace = get_production_deployment_target_workspace(production_target_id, root=root)
    if transaction_id and canonical_rule_id:
        blockers = []
    elif not transaction_id and not canonical_rule_id:
        return {
            "status": "blocked",
            "production_target_id": production_target_id,
            "warnings": [],
            "blockers": ["transaction_id_or_canonical_rule_id_required"],
        }
    resolved_transaction_id = transaction_id or _find_transaction_id_for_rule(canonical_rule_id or "", root=root)
    if not resolved_transaction_id:
        return {
            "status": "blocked",
            "production_target_id": production_target_id,
            "warnings": [],
            "blockers": ["transaction_lookup_ambiguous_or_missing"],
        }
    tx_state = tx_backend.read_production_activation_transaction_state(str(resolved_transaction_id), root=root)
    if tx_state.get("status") != "loaded":
        return {
            "status": "missing",
            "production_target_id": production_target_id,
            "transaction_id": resolved_transaction_id,
            "warnings": list(tx_state.get("warnings", [])),
            "blockers": list(tx_state.get("blockers", [])),
        }
    deployed_rule_id = str(tx_state.get("committed_rule_id") or tx_state.get("deployed_rule_id") or "")
    rule_loaded = load_canonical_rule(deployed_rule_id, root=root) if deployed_rule_id else {"status": "not_found"}
    verification_status = "verified_pending"
    if str(tx_state.get("transaction_state") or "") == "committed":
        if rule_loaded.get("status") == "loaded":
            rule = rule_loaded.get("rule") if isinstance(rule_loaded.get("rule"), Mapping) else {}
            verification_status = "verified_committed" if str(rule.get("production_activation_transaction_id") or "") == str(resolved_transaction_id) else "mismatch"
        else:
            verification_status = "missing"
    else:
        verification_status = "verified_pending" if str(tx_state.get("verification_status") or "") == "verified_pending" and rule_loaded.get("status") == "not_found" else "mismatch"
    record = tx_backend._load_transaction_record(Path(root), str(resolved_transaction_id)) or {}
    return {
        "status": "loaded",
        "production_target_id": production_target_id,
        "environment_class": workspace.get("environment_class"),
        "adapter_id": get_production_deployment_adapter_manifest(root=root).get("adapter_id"),
        "transaction_id": resolved_transaction_id,
        "transaction_state": tx_state.get("transaction_state"),
        "canonical_rule_id": tx_state.get("canonical_rule_id"),
        "deployed_rule_id": deployed_rule_id or None,
        "canonical_rule_fingerprint": tx_state.get("canonical_rule_fingerprint"),
        "document_id": tx_state.get("document_id"),
        "source_revision": tx_state.get("source_revision"),
        "certification_fingerprint": record.get("certification_fingerprint"),
        "production_authorization_fingerprint": tx_state.get("production_authorization_fingerprint"),
        "deployment_package_fingerprint": tx_state.get("deployment_package_fingerprint"),
        "transaction_package_fingerprint": tx_state.get("package_fingerprint"),
        "production_state_fingerprint": workspace.get("current_production_state_fingerprint"),
        "pending_state_fingerprint": tx_state.get("pending_state_fingerprint"),
        "verification_status": verification_status,
        "warnings": _dedupe(list(workspace.get("warnings", [])) + list(tx_state.get("warnings", []))),
        "blockers": list(tx_state.get("blockers", [])),
    }


def apply_production_deployment(
    production_target_id: str,
    deployment_package: Mapping[str, Any],
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    if confirmation != APPLY_CONFIRMATION:
        return {"status": "blocked", "warnings": [], "blockers": ["apply_confirmation_required"]}
    package_validation = validate_production_deployment_package(production_target_id, deployment_package, root=root)
    if package_validation.get("status") != "valid":
        return {
            "status": "blocked",
            "warnings": list(package_validation.get("warnings", [])),
            "blockers": list(package_validation.get("blockers", [])),
        }
    tx_package = _to_transaction_package(_normalized_deployment_package(deployment_package), get_production_deployment_target_workspace(production_target_id, root=root))
    preflight = preflight_production_deployment(production_target_id, deployment_package, root=root)
    if preflight.get("status") not in {"ready", "already_committed"}:
        return dict(preflight)
    if preflight.get("status") == "already_committed":
        return dict(preflight)
    applied = tx_backend.apply_production_activation_transaction(tx_package, confirmation=tx_backend.APPLY_CONFIRMATION, root=root)
    return {
        "status": str(applied.get("status") or "unknown"),
        "production_target_id": production_target_id,
        "transaction_id": applied.get("transaction_id"),
        "deployment_package_fingerprint": package_validation.get("package_fingerprint"),
        "transaction_package_fingerprint": package_validation.get("transaction_package_fingerprint"),
        "pending_state_fingerprint": applied.get("pending_state_fingerprint"),
        "warnings": list(applied.get("warnings", [])),
        "blockers": list(applied.get("blockers", [])),
    }


def verify_production_deployment(
    production_target_id: str,
    transaction_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    state = read_production_deployment_state(production_target_id, transaction_id=transaction_id, root=root)
    if state.get("status") != "loaded":
        return {
            "status": "verification_failed",
            "production_target_id": production_target_id,
            "transaction_id": transaction_id,
            "warnings": list(state.get("warnings", [])),
            "blockers": list(state.get("blockers", [])),
        }
    if str(state.get("transaction_state") or "") != "pending_verification":
        return {
            "status": "verification_failed",
            "production_target_id": production_target_id,
            "transaction_id": transaction_id,
            "warnings": list(state.get("warnings", [])),
            "blockers": ["transaction_not_pending_verification"],
        }
    if str(state.get("verification_status") or "") != "verified_pending":
        return {
            "status": "verification_failed",
            "production_target_id": production_target_id,
            "transaction_id": transaction_id,
            "warnings": list(state.get("warnings", [])),
            "blockers": ["pending_state_not_independently_verified"],
        }
    return {
        "status": "verified_pending",
        "production_target_id": production_target_id,
        "transaction_id": transaction_id,
        "pending_state_fingerprint": state.get("pending_state_fingerprint"),
        "deployment_package_fingerprint": state.get("deployment_package_fingerprint"),
        "transaction_package_fingerprint": state.get("transaction_package_fingerprint"),
        "warnings": list(state.get("warnings", [])),
        "blockers": [],
    }


def commit_production_deployment(
    production_target_id: str,
    transaction_id: str,
    expected_pending_state_fingerprint: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    if confirmation != COMMIT_CONFIRMATION:
        return {"status": "blocked", "warnings": [], "blockers": ["commit_confirmation_required"]}
    workspace = get_production_deployment_target_workspace(production_target_id, root=root)
    if workspace.get("status") not in {"healthy", "warning"}:
        return {"status": "blocked", "warnings": list(workspace.get("warnings", [])), "blockers": list(workspace.get("blockers", [])) or ["production_target_workspace_unhealthy"]}
    verified = verify_production_deployment(production_target_id, transaction_id, root=root)
    if verified.get("status") != "verified_pending":
        return {"status": "verification_failed", "warnings": list(verified.get("warnings", [])), "blockers": list(verified.get("blockers", []))}
    committed = tx_backend.commit_production_activation_transaction(
        transaction_id,
        expected_pending_state_fingerprint=expected_pending_state_fingerprint,
        confirmation=tx_backend.COMMIT_CONFIRMATION,
        root=root,
    )
    if str(committed.get("status") or "") not in {"committed", "already_committed"}:
        return {
            "status": str(committed.get("status") or "commit_failed"),
            "warnings": list(committed.get("warnings", [])),
            "blockers": list(committed.get("blockers", [])),
        }
    state = read_production_deployment_state(production_target_id, transaction_id=transaction_id, root=root)
    if str(state.get("verification_status") or "") != "verified_committed":
        return {"status": "commit_failed", "warnings": list(state.get("warnings", [])), "blockers": ["committed_state_verification_failed", *list(state.get("blockers", []))]}
    rule = load_canonical_rule(str(state.get("deployed_rule_id") or ""), require_active=True, root=root)
    if rule.get("status") != "loaded":
        return {"status": "commit_failed", "warnings": [], "blockers": ["committed_rule_missing_after_commit"]}
    loaded_rule = rule.get("rule") if isinstance(rule.get("rule"), Mapping) else {}
    return {
        "status": "committed",
        "production_target_id": production_target_id,
        "transaction_id": transaction_id,
        "canonical_rule_id": state.get("canonical_rule_id"),
        "deployed_rule_id": loaded_rule.get("rule_id"),
        "canonical_rule_fingerprint": loaded_rule.get("rule_fingerprint"),
        "deployment_package_fingerprint": state.get("deployment_package_fingerprint"),
        "transaction_package_fingerprint": state.get("transaction_package_fingerprint"),
        "warnings": [],
        "blockers": [],
    }


def rollback_production_deployment(
    production_target_id: str,
    transaction_id: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    if confirmation != ROLLBACK_CONFIRMATION:
        return {"status": "blocked", "warnings": [], "blockers": ["rollback_confirmation_required"]}
    before_state = read_production_deployment_state(production_target_id, transaction_id=transaction_id, root=root)
    rolled = tx_backend.rollback_production_activation_transaction(transaction_id, confirmation=tx_backend.ROLLBACK_CONFIRMATION, root=root)
    status = str(rolled.get("status") or "rollback_failed")
    if status not in {"completed", "already_rolled_back"}:
        return {"status": status, "warnings": list(rolled.get("warnings", [])), "blockers": list(rolled.get("blockers", []))}
    after_state = read_production_deployment_state(production_target_id, transaction_id=transaction_id, root=root)
    if before_state.get("transaction_state") == "pending_verification":
        record = tx_backend._load_transaction_record(Path(root), transaction_id) or {}
        if str(record.get("transaction_state") or "") != "rolled_back":
            return {"status": "rollback_failed", "warnings": [], "blockers": ["pending_rollback_state_not_persisted"]}
    if before_state.get("transaction_state") == "committed":
        rule = load_canonical_rule(str(before_state.get("deployed_rule_id") or ""), root=root)
        payload = rule.get("rule") if isinstance(rule.get("rule"), Mapping) else {}
        if rule.get("status") != "loaded" or str(payload.get("status") or "") == "active":
            return {"status": "rollback_failed", "warnings": [], "blockers": ["committed_rule_still_active_after_rollback"]}
    return {
        "status": status,
        "production_target_id": production_target_id,
        "transaction_id": transaction_id,
        "warnings": list(after_state.get("warnings", [])),
        "blockers": [],
    }


def _validate_package_internal(workspace: Mapping[str, Any], deployment_package: Mapping[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    if not isinstance(deployment_package, Mapping):
        return {"valid": False, "warnings": [], "blockers": ["deployment_package_invalid"], "package_fingerprint": None, "transaction_package_fingerprint": None}
    disallowed = set(deployment_package.keys()) - {
        "schema_version",
        "package_id",
        "canonical_rule_id",
        "canonical_rule_schema_version",
        "canonical_rule_fingerprint",
        "canonical_rule_payload",
        "document_id",
        "source_revision",
        "certification_id",
        "certification_fingerprint",
        "controlled_integration_result_id",
        "controlled_integration_fingerprint",
        "isolated_committed_state_fingerprint",
        "production_authorization_result_id",
        "production_authorization_fingerprint",
        "production_target_id",
        "production_target_descriptor_fingerprint",
        "production_adapter_manifest_fingerprint",
        "production_adapter_capability_fingerprint",
        "deployment_adapter_fingerprint",
        "package_fingerprint",
    }
    if disallowed:
        blockers.append("deployment_package_contains_unsupported_fields")
    if _contains_unsafe_content(deployment_package):
        blockers.append("deployment_package_contains_unsafe_content")
    package = _normalized_deployment_package(deployment_package)
    if str(package.get("schema_version") or "") != DEPLOYMENT_PACKAGE_SCHEMA_VERSION:
        blockers.append("deployment_package_schema_unsupported")
    if str(package.get("production_target_id") or "") != str(workspace.get("production_target_id") or ""):
        blockers.append("deployment_target_id_mismatch")
    if str(package.get("production_target_descriptor_fingerprint") or "") != str(workspace.get("descriptor_fingerprint") or ""):
        blockers.append("production_target_descriptor_fingerprint_mismatch")
    descriptor = workspace.get("production_target_descriptor") if isinstance(workspace.get("production_target_descriptor"), Mapping) else {}
    if str(package.get("production_adapter_manifest_fingerprint") or "") != str(descriptor.get("adapter_manifest_fingerprint") or ""):
        blockers.append("production_adapter_manifest_fingerprint_mismatch")
    if str(package.get("production_adapter_capability_fingerprint") or "") != str(descriptor.get("adapter_capability_fingerprint") or ""):
        blockers.append("production_adapter_capability_fingerprint_mismatch")
    adapter_manifest = get_production_deployment_adapter_manifest(root=SOURCE_DOCUMENT_ROOT)
    if str(package.get("deployment_adapter_fingerprint") or "") != str(adapter_manifest.get("adapter_fingerprint") or ""):
        blockers.append("deployment_adapter_fingerprint_mismatch")
    if isinstance(package.get("source_revision"), bool) or not isinstance(package.get("source_revision"), int) or int(package.get("source_revision") or 0) <= 0:
        blockers.append("deployment_package_source_revision_invalid")
    for field in (
        "package_id",
        "canonical_rule_id",
        "canonical_rule_schema_version",
        "canonical_rule_fingerprint",
        "document_id",
        "certification_id",
        "certification_fingerprint",
        "controlled_integration_result_id",
        "controlled_integration_fingerprint",
        "isolated_committed_state_fingerprint",
        "production_authorization_result_id",
        "production_authorization_fingerprint",
        "production_target_id",
        "production_target_descriptor_fingerprint",
        "production_adapter_manifest_fingerprint",
        "production_adapter_capability_fingerprint",
        "deployment_adapter_fingerprint",
        "package_fingerprint",
    ):
        if not _text(package.get(field)):
            blockers.append(f"{field}_required")
    rule_payload = package.get("canonical_rule_payload")
    if not isinstance(rule_payload, Mapping):
        blockers.append("canonical_rule_payload_invalid")
    else:
        validation = validate_canonical_rule_record(dict(rule_payload), require_active=True)
        if not validation.get("valid"):
            blockers.extend(list(validation.get("blockers", [])))
        else:
            if str(validation.get("rule_id") or "") != str(package.get("canonical_rule_id") or ""):
                blockers.append("canonical_rule_id_mismatch")
            if str(validation.get("rule_fingerprint") or "") != str(package.get("canonical_rule_fingerprint") or ""):
                blockers.append("canonical_rule_fingerprint_mismatch")
            if str((rule_payload or {}).get("document_id") or "") != str(package.get("document_id") or ""):
                blockers.append("canonical_rule_document_id_mismatch")
            if str((rule_payload or {}).get("source_revision") or "") != str(package.get("source_revision") or ""):
                blockers.append("canonical_rule_source_revision_mismatch")
    serialized = str(package)
    if len(serialized.encode("utf-8")) > 65536:
        blockers.append("deployment_package_size_exceeded")
    computed_package_fingerprint = _deployment_package_fingerprint(package)
    if str(package.get("package_fingerprint") or "") != computed_package_fingerprint:
        blockers.append("deployment_package_fingerprint_mismatch")
    tx_package = _to_transaction_package(package, workspace)
    tx_package_fingerprint = tx_backend._package_fingerprint(tx_package)
    return {
        "valid": not blockers,
        "warnings": warnings,
        "blockers": _dedupe(blockers),
        "package": package,
        "package_fingerprint": computed_package_fingerprint,
        "transaction_package": tx_package,
        "transaction_package_fingerprint": tx_package_fingerprint,
    }


def _to_transaction_package(deployment_package: Mapping[str, Any], workspace: Mapping[str, Any]) -> dict[str, Any]:
    tx_package = {
        "schema_version": tx_backend.PACKAGE_SCHEMA_VERSION,
        "transaction_package_id": f"production_activation_tx_package_{_hash_payload({'package_fingerprint': deployment_package.get('package_fingerprint')})[7:23]}",
        "canonical_rule_id": deployment_package.get("canonical_rule_id"),
        "canonical_rule_schema_version": deployment_package.get("canonical_rule_schema_version"),
        "canonical_rule_fingerprint": deployment_package.get("canonical_rule_fingerprint"),
        "canonical_rule_payload": deepcopy(dict(deployment_package.get("canonical_rule_payload") or {})),
        "document_id": deployment_package.get("document_id"),
        "source_revision": deployment_package.get("source_revision"),
        "certification_id": deployment_package.get("certification_id"),
        "certification_fingerprint": deployment_package.get("certification_fingerprint"),
        "production_authorization_result_id": deployment_package.get("production_authorization_result_id"),
        "production_authorization_fingerprint": deployment_package.get("production_authorization_fingerprint"),
        "production_target_id": deployment_package.get("production_target_id"),
        "production_target_descriptor_fingerprint": deployment_package.get("production_target_descriptor_fingerprint"),
        "deployment_package_fingerprint": deployment_package.get("package_fingerprint"),
        "package_fingerprint": None,
    }
    tx_package["package_fingerprint"] = tx_backend._package_fingerprint(tx_package)
    return tx_package


def _normalized_deployment_package(deployment_package: Mapping[str, Any]) -> dict[str, Any]:
    payload = deepcopy(dict(deployment_package))
    payload["canonical_rule_payload"] = deepcopy(dict(payload.get("canonical_rule_payload") or {}))
    return payload


def _deployment_package_fingerprint(package: Mapping[str, Any]) -> str:
    return _hash_payload({key: package.get(key) for key in sorted(package) if key != "package_fingerprint"})


def _find_transaction_id_for_rule(canonical_rule_id: str, *, root: Path | str) -> str | None:
    base = Path(root)
    matches = [
        item for item in tx_backend._load_all_records(base) if str(item.get("canonical_rule_id") or "") == str(canonical_rule_id or "")
    ]
    if len(matches) != 1:
        return None
    return str(matches[0].get("transaction_id") or "")


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
        "confirmation",
        "confirmations",
        "operation_name",
        "operation_names",
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


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in values if str(item)))
