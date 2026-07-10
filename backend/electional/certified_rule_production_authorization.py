"""Certified-rule production authorization over completed controlled integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from . import certified_rule_controlled_integration as integration_backend
from . import certified_rule_controlled_integration_target as target_backend
from . import certified_rule_integration_authorization as integration_authorization_backend
from . import certified_rule_release_candidate as release_candidate_backend
from . import production_target_descriptor as descriptor_backend
from .canonical_rule_runtime import _atomic_write_json, _hash_payload, _read_json, _restore_json, _safe_id, _now, load_canonical_rule
from .certified_rule_replay_adapter import _rule_has_unresolved_critical_remediation, _rule_pending_supersession
from .document_manifest import load_document_manifest
from .rule_effectiveness_analysis import _ensure_analysis_dirs, _load_certification_receipt_for_rule
from .source_documents import SOURCE_DOCUMENT_ROOT

PLAN_DIR = "certified_rule_production_authorization_plans"
RESULT_DIR = "certified_rule_production_authorization_results"
RECEIPT_DIR = "certified_rule_production_authorization_receipts"
PLAN_INDEX = "certified_rule_production_authorization_plan_index.json"
RESULT_INDEX = "certified_rule_production_authorization_result_index.json"
RECEIPT_INDEX = "certified_rule_production_authorization_receipt_index.json"
PLAN_SCHEMA = "certified_rule_production_authorization_plan_v1"
RESULT_SCHEMA = "certified_rule_production_authorization_result_v1"
RECEIPT_SCHEMA = "certified_rule_production_authorization_receipt_v1"
AUTH_SCHEMA_VERSION = "certified_rule_production_authorization_v1"
REQUIRED_CONFIRMATION = "SAVE_PRODUCTION_AUTHORIZATION"
AUTHORIZED_DECISION = "authorize_for_later_production_deployment"
SOURCE_AUTHORIZED_DECISION = "authorize_for_later_integration"
DECISIONS = {AUTHORIZED_DECISION, "defer_production_deployment", "reject_production_deployment"}
PUBLIC_FUNCTIONS = [
    "build_certified_rule_production_authorization_workspace",
    "validate_certified_rule_production_authorization_eligibility",
    "build_certified_rule_production_authorization_plan",
    "save_certified_rule_production_authorization_decision",
    "load_certified_rule_production_authorization_result",
    "get_certified_rule_production_authorization_health",
    "format_certified_rule_production_authorization_report",
]


def build_certified_rule_production_authorization_workspace(
    canonical_rule_id: str,
    controlled_integration_result_id: str,
    production_target_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    eligibility = validate_certified_rule_production_authorization_eligibility(
        canonical_rule_id, controlled_integration_result_id, production_target_id, root=base
    )
    plan = _find_plan(base, canonical_rule_id, controlled_integration_result_id, production_target_id)
    result = _find_result(base, str((plan or {}).get("production_authorization_plan_id") or ""))
    receipt = _find_receipt_for_result(base, str((result or {}).get("production_authorization_result_id") or ""))
    return {
        "status": "ready_for_planning" if not eligibility.get("blockers") else str(eligibility.get("status") or "blocked"),
        "canonical_rule_id": canonical_rule_id,
        "document_id": eligibility.get("document_id"),
        "source_revision": eligibility.get("source_revision"),
        "controlled_integration_status": eligibility.get("controlled_integration_status", "unknown"),
        "release_candidate_status": eligibility.get("release_candidate_status", "unknown"),
        "authorization_status": eligibility.get("authorization_status", "unknown"),
        "production_target_status": eligibility.get("production_target_status", "unknown"),
        "descriptor_access_mode": eligibility.get("descriptor_access_mode", "unknown"),
        "namespace_id": eligibility.get("namespace_id"),
        "transaction_id": eligibility.get("transaction_id"),
        "production_authorization_plan_id": (plan or {}).get("production_authorization_plan_id"),
        "production_authorization_result_id": (result or {}).get("production_authorization_result_id"),
        "production_authorization_receipt_id": (receipt or {}).get("production_authorization_receipt_id"),
        "warnings": list(eligibility.get("warnings", [])),
        "blockers": list(eligibility.get("blockers", [])),
        "recommended_action": "Build the production authorization plan." if not eligibility.get("blockers") else eligibility.get("recommended_action", "Resolve blockers before production authorization."),
    }


def validate_certified_rule_production_authorization_eligibility(
    canonical_rule_id: str,
    controlled_integration_result_id: str,
    production_target_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    blockers: list[str] = []
    warnings: list[str] = []
    bundle = _load_bundle(base, canonical_rule_id, controlled_integration_result_id, production_target_id)

    rule_loaded = bundle.get("rule_loaded") if isinstance(bundle.get("rule_loaded"), Mapping) else {}
    rule = bundle.get("rule") if isinstance(bundle.get("rule"), Mapping) else {}
    certification = bundle.get("certification") if isinstance(bundle.get("certification"), Mapping) else {}
    manifest = bundle.get("manifest") if isinstance(bundle.get("manifest"), Mapping) else {}
    integration_loaded = bundle.get("controlled_integration_loaded") if isinstance(bundle.get("controlled_integration_loaded"), Mapping) else {}
    integration_result = bundle.get("controlled_integration_result") if isinstance(bundle.get("controlled_integration_result"), Mapping) else {}
    integration_receipt = bundle.get("controlled_integration_receipt") if isinstance(bundle.get("controlled_integration_receipt"), Mapping) else {}
    release_result = bundle.get("release_candidate_result") if isinstance(bundle.get("release_candidate_result"), Mapping) else {}
    release_receipt = bundle.get("release_candidate_receipt") if isinstance(bundle.get("release_candidate_receipt"), Mapping) else {}
    source_auth = bundle.get("integration_authorization_result") if isinstance(bundle.get("integration_authorization_result"), Mapping) else {}
    source_auth_receipt = bundle.get("integration_authorization_receipt") if isinstance(bundle.get("integration_authorization_receipt"), Mapping) else {}
    scoring_result = bundle.get("scoring_result") if isinstance(bundle.get("scoring_result"), Mapping) else {}
    fast_lane_result = bundle.get("fast_lane_result") if isinstance(bundle.get("fast_lane_result"), Mapping) else {}
    descriptor_loaded = bundle.get("descriptor_loaded") if isinstance(bundle.get("descriptor_loaded"), Mapping) else {}
    descriptor = descriptor_loaded.get("production_target_descriptor") if isinstance(descriptor_loaded.get("production_target_descriptor"), Mapping) else {}
    descriptor_health = bundle.get("descriptor_health") if isinstance(bundle.get("descriptor_health"), Mapping) else {}
    committed_state = bundle.get("committed_state") if isinstance(bundle.get("committed_state"), Mapping) else {}

    if str(rule_loaded.get("status") or "") != "loaded" or not rule:
        blockers.extend(list(rule_loaded.get("blockers", []) or ["canonical_rule_not_active"]))
    if not certification or str(certification.get("certification_status") or "") != "completed":
        blockers.append("rule_certification_missing_or_stale")
    if not manifest:
        blockers.append("document_manifest_missing")
    if rule and manifest and str(manifest.get("source_revision") or "") != str(rule.get("source_revision") or ""):
        blockers.append("source_revision_not_current")
    if _rollback_pending(rule):
        blockers.append("rule_has_pending_rollback")
    if _rule_pending_supersession(base, canonical_rule_id):
        blockers.append("rule_pending_supersession")
    if _rule_has_unresolved_critical_remediation(base, rule):
        blockers.append("rule_has_unresolved_critical_remediation")

    if str(integration_loaded.get("status") or "") != "loaded" or not integration_result:
        blockers.append("controlled_integration_result_missing")
    else:
        if bool(integration_result.get("stale")):
            blockers.append("controlled_integration_result_stale")
        if str(integration_result.get("final_status") or "") not in {"completed", "completed_with_warnings"}:
            blockers.append("controlled_integration_not_completed")
        if str(integration_result.get("production_safety_status") or "") != "passed":
            blockers.append("controlled_integration_production_safety_failed")
        if str(integration_result.get("pending_verification_status") or "") != "verified_pending":
            blockers.append("controlled_integration_pending_verification_missing")
        if str(integration_result.get("committed_verification_status") or "") != "verified_committed":
            blockers.append("controlled_integration_committed_verification_missing")
        if str(integration_result.get("rollback_status") or "") != "not_required":
            blockers.append("controlled_integration_rollback_unresolved")
        _match(blockers, integration_result.get("canonical_rule_id"), canonical_rule_id, "controlled_integration_rule_mismatch")
        _match(blockers, integration_result.get("document_id"), rule.get("document_id"), "controlled_integration_document_mismatch")
        _match(blockers, integration_result.get("source_revision"), rule.get("source_revision"), "controlled_integration_source_revision_mismatch")
        _match(blockers, integration_result.get("certification_fingerprint"), _certification_fingerprint(certification), "controlled_integration_certification_fingerprint_mismatch")
    if not integration_receipt:
        blockers.append("controlled_integration_receipt_missing")
    elif str(integration_receipt.get("result_fingerprint") or "") != str(integration_result.get("result_fingerprint") or ""):
        blockers.append("controlled_integration_receipt_fingerprint_mismatch")

    if not release_result:
        blockers.append("release_candidate_result_missing")
    else:
        if str(release_result.get("qualification_status") or "") not in integration_backend.QUALIFIED_STATUSES:
            blockers.append("release_candidate_not_qualified")
        if release_candidate_backend._result_is_stale(base, release_result) or bool(release_result.get("stale")):
            blockers.append("release_candidate_result_stale")
        _match(blockers, integration_result.get("release_candidate_result_id"), release_result.get("release_candidate_result_id"), "controlled_integration_release_candidate_id_mismatch")
        _match(blockers, integration_result.get("release_candidate_result_fingerprint"), release_result.get("result_fingerprint"), "controlled_integration_release_candidate_fingerprint_mismatch")
    if not release_receipt:
        blockers.append("release_candidate_receipt_missing")
    elif str(release_receipt.get("result_fingerprint") or "") != str(release_result.get("result_fingerprint") or ""):
        blockers.append("release_candidate_receipt_fingerprint_mismatch")

    if not source_auth:
        blockers.append("integration_authorization_result_missing")
    else:
        if str(source_auth.get("status") or "") != "authorized":
            blockers.append("integration_authorization_not_authorized")
        if str(source_auth.get("decision") or "") != SOURCE_AUTHORIZED_DECISION:
            blockers.append("integration_authorization_decision_invalid")
        if integration_authorization_backend._result_is_stale(base, source_auth) or bool(source_auth.get("stale")):
            blockers.append("integration_authorization_result_stale")
        _match(blockers, integration_result.get("integration_authorization_result_id"), source_auth.get("integration_authorization_result_id"), "controlled_integration_authorization_id_mismatch")
        _match(blockers, integration_result.get("integration_authorization_result_fingerprint"), source_auth.get("result_fingerprint"), "controlled_integration_authorization_fingerprint_mismatch")
    if not source_auth_receipt:
        blockers.append("integration_authorization_receipt_missing")
    elif str(source_auth_receipt.get("result_fingerprint") or "") != str(source_auth.get("result_fingerprint") or ""):
        blockers.append("integration_authorization_receipt_fingerprint_mismatch")

    if not scoring_result:
        blockers.append("scoring_preview_result_missing")
    else:
        _match(blockers, integration_result.get("scoring_preview_result_id"), scoring_result.get("scoring_preview_result_id"), "controlled_integration_scoring_preview_id_mismatch")
        _match(blockers, integration_result.get("scoring_preview_result_fingerprint"), scoring_result.get("result_fingerprint"), "controlled_integration_scoring_preview_fingerprint_mismatch")
        _match(blockers, integration_result.get("scoring_config_fingerprint"), scoring_result.get("scoring_config_fingerprint"), "controlled_integration_scoring_config_fingerprint_mismatch")

    if not fast_lane_result:
        blockers.append("fast_lane_preview_result_missing")
    else:
        _match(blockers, integration_result.get("fast_lane_preview_result_id"), fast_lane_result.get("fast_lane_preview_result_id"), "controlled_integration_fast_lane_preview_id_mismatch")
        _match(blockers, integration_result.get("fast_lane_preview_result_fingerprint"), fast_lane_result.get("result_fingerprint"), "controlled_integration_fast_lane_preview_fingerprint_mismatch")
        _match(blockers, integration_result.get("fast_lane_contract_id"), fast_lane_result.get("fast_lane_contract_id"), "controlled_integration_fast_lane_contract_id_mismatch")
        _match(blockers, integration_result.get("fast_lane_contract_version"), fast_lane_result.get("fast_lane_contract_version"), "controlled_integration_fast_lane_contract_version_mismatch")
        _match(blockers, integration_result.get("fast_lane_capability_fingerprint"), fast_lane_result.get("fast_lane_capability_fingerprint"), "controlled_integration_fast_lane_capability_fingerprint_mismatch")

    if not descriptor:
        blockers.append("production_target_descriptor_missing")
    else:
        descriptor_validation = descriptor_backend.validate_production_target_descriptor(dict(descriptor))
        if not descriptor_validation.get("valid"):
            blockers.extend(list(descriptor_validation.get("blockers", [])))
        if str(descriptor.get("environment_class") or "") != "production":
            blockers.append("production_target_environment_invalid")
        if str(descriptor.get("descriptor_access_mode") or "") != descriptor_backend.ACCESS_MODE:
            blockers.append("production_target_access_mode_invalid")
        if str(descriptor.get("authorization_scope") or "") != descriptor_backend.AUTHORIZATION_SCOPE:
            blockers.append("production_target_authorization_scope_invalid")
        if str(descriptor.get("target_id") or "") != production_target_id:
            blockers.append("production_target_descriptor_id_mismatch")
        if list(descriptor.get("operational_entrypoints_exposed") or []):
            blockers.append("production_target_operational_entrypoints_forbidden")
    if str(descriptor_health.get("status") or "") not in {"healthy", "warning"}:
        blockers.append("production_target_descriptor_unhealthy")

    if not committed_state:
        blockers.append("controlled_integration_committed_namespace_missing")
    else:
        if str(committed_state.get("verification_status") or "") != "verified_committed":
            blockers.append("controlled_integration_committed_namespace_unverified")
        _match(blockers, committed_state.get("state_fingerprint"), integration_result.get("committed_state_fingerprint"), "controlled_integration_committed_state_fingerprint_mismatch")
        _match(blockers, committed_state.get("transaction_id"), integration_result.get("transaction_id"), "controlled_integration_transaction_id_mismatch")
        _match(blockers, committed_state.get("namespace_id"), integration_result.get("namespace_id"), "controlled_integration_namespace_id_mismatch")
        _match(blockers, committed_state.get("target_id"), integration_result.get("integration_target_id"), "controlled_integration_target_id_mismatch")
        _match(blockers, committed_state.get("adapter_id"), integration_result.get("adapter_id"), "controlled_integration_adapter_id_mismatch")
        _match(blockers, committed_state.get("adapter_version"), integration_result.get("adapter_version"), "controlled_integration_adapter_version_mismatch")
        _match(blockers, committed_state.get("package_fingerprint"), integration_result.get("package_fingerprint"), "controlled_integration_package_fingerprint_mismatch")

    status = _eligibility_status(blockers, warnings)
    return {
        "status": status,
        "canonical_rule_id": canonical_rule_id,
        "document_id": rule.get("document_id"),
        "source_revision": rule.get("source_revision"),
        "controlled_integration_status": integration_result.get("final_status", integration_loaded.get("status", "missing")),
        "release_candidate_status": release_result.get("qualification_status", "missing"),
        "authorization_status": source_auth.get("status", "missing"),
        "production_target_status": descriptor_loaded.get("status", descriptor_health.get("status", "missing")),
        "descriptor_access_mode": descriptor.get("descriptor_access_mode", "unknown"),
        "descriptor_fingerprint": descriptor.get("descriptor_fingerprint"),
        "namespace_id": integration_result.get("namespace_id"),
        "transaction_id": integration_result.get("transaction_id"),
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
        "recommended_action": _recommended_action(status),
    }


def build_certified_rule_production_authorization_plan(
    canonical_rule_id: str,
    controlled_integration_result_id: str,
    production_target_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    eligibility = validate_certified_rule_production_authorization_eligibility(
        canonical_rule_id, controlled_integration_result_id, production_target_id, root=base
    )
    if eligibility.get("blockers"):
        return {
            "status": str(eligibility.get("status") or "blocked"),
            "canonical_rule_id": canonical_rule_id,
            "controlled_integration_result_id": controlled_integration_result_id,
            "production_target_id": production_target_id,
            "warnings": list(eligibility.get("warnings", [])),
            "blockers": list(eligibility.get("blockers", [])),
        }
    bundle = _load_bundle(base, canonical_rule_id, controlled_integration_result_id, production_target_id)
    integration_result = bundle["controlled_integration_result"]
    descriptor = bundle["descriptor_loaded"]["production_target_descriptor"]
    plan = {
        "schema_version": PLAN_SCHEMA,
        "production_authorization_schema_version": AUTH_SCHEMA_VERSION,
        "production_authorization_plan_id": _plan_id(bundle),
        "canonical_rule_id": canonical_rule_id,
        "document_id": integration_result.get("document_id"),
        "source_revision": integration_result.get("source_revision"),
        "certification_id": integration_result.get("certification_id"),
        "certification_fingerprint": integration_result.get("certification_fingerprint"),
        "controlled_integration_result_id": integration_result.get("controlled_integration_result_id"),
        "controlled_integration_result_fingerprint": integration_result.get("result_fingerprint"),
        "controlled_integration_plan_id": integration_result.get("controlled_integration_plan_id"),
        "release_candidate_result_id": integration_result.get("release_candidate_result_id"),
        "release_candidate_result_fingerprint": integration_result.get("release_candidate_result_fingerprint"),
        "integration_authorization_result_id": integration_result.get("integration_authorization_result_id"),
        "integration_authorization_result_fingerprint": integration_result.get("integration_authorization_result_fingerprint"),
        "scoring_preview_result_id": integration_result.get("scoring_preview_result_id"),
        "scoring_preview_result_fingerprint": integration_result.get("scoring_preview_result_fingerprint"),
        "scoring_config_id": integration_result.get("scoring_config_id"),
        "scoring_config_fingerprint": integration_result.get("scoring_config_fingerprint"),
        "fast_lane_preview_result_id": integration_result.get("fast_lane_preview_result_id"),
        "fast_lane_preview_result_fingerprint": integration_result.get("fast_lane_preview_result_fingerprint"),
        "fast_lane_contract_id": integration_result.get("fast_lane_contract_id"),
        "fast_lane_contract_version": integration_result.get("fast_lane_contract_version"),
        "fast_lane_capability_fingerprint": integration_result.get("fast_lane_capability_fingerprint"),
        "isolated_target_id": integration_result.get("integration_target_id"),
        "isolated_target_fingerprint": integration_result.get("target_fingerprint"),
        "adapter_id": integration_result.get("adapter_id"),
        "adapter_version": integration_result.get("adapter_version"),
        "adapter_fingerprint": integration_result.get("adapter_fingerprint"),
        "package_id": integration_result.get("package_id"),
        "package_fingerprint": integration_result.get("package_fingerprint"),
        "transaction_id": integration_result.get("transaction_id"),
        "namespace_id": integration_result.get("namespace_id"),
        "committed_state_fingerprint": integration_result.get("committed_state_fingerprint"),
        "production_target_id": descriptor.get("target_id"),
        "production_target_descriptor_fingerprint": descriptor.get("descriptor_fingerprint"),
        "production_adapter_manifest_fingerprint": descriptor.get("adapter_manifest_fingerprint"),
        "production_adapter_capability_fingerprint": descriptor.get("adapter_capability_fingerprint"),
        "plan_fingerprint": _plan_fingerprint(bundle),
        "warnings": list(eligibility.get("warnings", [])),
        "blockers": list(eligibility.get("blockers", [])),
    }
    path = _plan_path(base, str(plan["production_authorization_plan_id"]))
    existing = _read_json(path)
    if isinstance(existing, Mapping):
        if str(existing.get("plan_fingerprint") or "") == str(plan.get("plan_fingerprint") or ""):
            return {"status": "planned", "production_authorization_plan_id": plan["production_authorization_plan_id"], "writes_performed": 0, **_plan_summary(plan)}
        return {"status": "corrupt", "production_authorization_plan_id": plan["production_authorization_plan_id"], "warnings": [], "blockers": ["production_authorization_plan_divergence"]}
    before_plan = _read_json(path)
    before_index = _read_json(base / "indexes" / PLAN_INDEX)
    try:
        _atomic_write_json(path, plan)
        _update_plan_index(base)
    except Exception:
        _restore_json(path, before_plan)
        _restore_json(base / "indexes" / PLAN_INDEX, before_index)
        return {"status": "corrupt", "production_authorization_plan_id": plan["production_authorization_plan_id"], "warnings": [], "blockers": ["production_authorization_plan_write_failure"]}
    return {"status": "planned", "production_authorization_plan_id": plan["production_authorization_plan_id"], "writes_performed": 1, **_plan_summary(plan)}


def save_certified_rule_production_authorization_decision(
    production_authorization_plan_id: str,
    decision: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    if confirmation != REQUIRED_CONFIRMATION:
        return {"status": "blocked", "production_authorization_plan_id": production_authorization_plan_id, "warnings": [], "blockers": ["production_authorization_confirmation_required"]}
    normalized_decision = str(decision or "").strip()
    if normalized_decision not in DECISIONS:
        return {"status": "blocked", "production_authorization_plan_id": production_authorization_plan_id, "warnings": [], "blockers": ["production_authorization_decision_invalid"]}
    plan = _read_json(_plan_path(base, production_authorization_plan_id))
    if not isinstance(plan, Mapping):
        return {"status": "blocked", "production_authorization_plan_id": production_authorization_plan_id, "warnings": [], "blockers": ["production_authorization_plan_missing"]}

    canonical_rule_id = str(plan.get("canonical_rule_id") or "")
    controlled_integration_result_id = str(plan.get("controlled_integration_result_id") or "")
    production_target_id = str(plan.get("production_target_id") or "")
    eligibility = validate_certified_rule_production_authorization_eligibility(
        canonical_rule_id, controlled_integration_result_id, production_target_id, root=base
    )
    bundle = _load_bundle(base, canonical_rule_id, controlled_integration_result_id, production_target_id)
    current_plan_fingerprint = _plan_fingerprint(bundle)
    if any(
        [
            str(eligibility.get("status") or "") not in {"eligible", "eligible_with_warnings"},
            str(plan.get("plan_fingerprint") or "") != str(current_plan_fingerprint or ""),
        ]
    ):
        stale_due_to_drift = str(plan.get("plan_fingerprint") or "") != str(current_plan_fingerprint or "")
        return {
            "status": "stale" if stale_due_to_drift or str(eligibility.get("status") or "") == "stale" else str(eligibility.get("status") or "blocked"),
            "production_authorization_plan_id": production_authorization_plan_id,
            "warnings": list(eligibility.get("warnings", [])),
            "blockers": list(eligibility.get("blockers", [])) or ["production_authorization_plan_fingerprint_mismatch"],
        }

    existing = _find_result(base, production_authorization_plan_id)
    if isinstance(existing, Mapping):
        existing_receipt = _find_receipt_for_result(base, str(existing.get("production_authorization_result_id") or ""))
        if (
            str(existing.get("decision") or "") == normalized_decision
            and str(existing.get("status") or "") == "authorized"
            and not _result_is_stale(base, existing)
            and isinstance(existing_receipt, Mapping)
            and str(existing_receipt.get("result_fingerprint") or "") == str(existing.get("result_fingerprint") or "")
        ):
            return {
                "status": "already_authorized",
                "production_authorization_plan_id": production_authorization_plan_id,
                "production_authorization_result_id": existing.get("production_authorization_result_id"),
                "production_authorization_receipt_id": existing_receipt.get("production_authorization_receipt_id"),
                "writes_performed": 0,
            }
        return {"status": "stale" if _result_is_stale(base, existing) else "corrupt", "production_authorization_plan_id": production_authorization_plan_id, "warnings": [], "blockers": ["production_authorization_existing_state_drift"]}

    integration_result = bundle["controlled_integration_result"]
    descriptor = bundle["descriptor_loaded"]["production_target_descriptor"]
    result_id = _result_id(production_authorization_plan_id)
    result = {
        "schema_version": RESULT_SCHEMA,
        "production_authorization_schema_version": AUTH_SCHEMA_VERSION,
        "production_authorization_result_id": result_id,
        "production_authorization_plan_id": production_authorization_plan_id,
        "canonical_rule_id": canonical_rule_id,
        "document_id": plan.get("document_id"),
        "source_revision": plan.get("source_revision"),
        "controlled_integration_result_id": controlled_integration_result_id,
        "controlled_integration_result_fingerprint": plan.get("controlled_integration_result_fingerprint"),
        "release_candidate_result_id": plan.get("release_candidate_result_id"),
        "release_candidate_result_fingerprint": plan.get("release_candidate_result_fingerprint"),
        "integration_authorization_result_id": plan.get("integration_authorization_result_id"),
        "integration_authorization_result_fingerprint": plan.get("integration_authorization_result_fingerprint"),
        "scoring_preview_result_id": plan.get("scoring_preview_result_id"),
        "scoring_preview_result_fingerprint": plan.get("scoring_preview_result_fingerprint"),
        "scoring_config_id": plan.get("scoring_config_id"),
        "scoring_config_fingerprint": plan.get("scoring_config_fingerprint"),
        "fast_lane_preview_result_id": plan.get("fast_lane_preview_result_id"),
        "fast_lane_preview_result_fingerprint": plan.get("fast_lane_preview_result_fingerprint"),
        "fast_lane_contract_id": plan.get("fast_lane_contract_id"),
        "fast_lane_contract_version": plan.get("fast_lane_contract_version"),
        "fast_lane_capability_fingerprint": plan.get("fast_lane_capability_fingerprint"),
        "isolated_target_id": plan.get("isolated_target_id"),
        "isolated_target_fingerprint": plan.get("isolated_target_fingerprint"),
        "namespace_id": plan.get("namespace_id"),
        "transaction_id": plan.get("transaction_id"),
        "committed_state_fingerprint": plan.get("committed_state_fingerprint"),
        "production_target_id": production_target_id,
        "production_target_descriptor_fingerprint": descriptor.get("descriptor_fingerprint"),
        "production_adapter_manifest_fingerprint": descriptor.get("adapter_manifest_fingerprint"),
        "production_adapter_capability_fingerprint": descriptor.get("adapter_capability_fingerprint"),
        "decision": normalized_decision,
        "status": "authorized" if normalized_decision == AUTHORIZED_DECISION else "recorded",
        "controlled_integration_status": integration_result.get("final_status"),
        "committed_verification_status": integration_result.get("committed_verification_status"),
        "production_safety_status": integration_result.get("production_safety_status"),
        "warnings": list(eligibility.get("warnings", [])),
        "blockers": [],
    }
    result["result_fingerprint"] = _result_fingerprint(result)
    receipt_id = _receipt_id(result_id)
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "production_authorization_receipt_id": receipt_id,
        "production_authorization_result_id": result_id,
        "production_authorization_plan_id": production_authorization_plan_id,
        "canonical_rule_id": canonical_rule_id,
        "document_id": result.get("document_id"),
        "source_revision": result.get("source_revision"),
        "controlled_integration_result_id": controlled_integration_result_id,
        "production_target_id": production_target_id,
        "decision": normalized_decision,
        "status": result.get("status"),
        "committed_state_fingerprint": result.get("committed_state_fingerprint"),
        "descriptor_fingerprint": result.get("production_target_descriptor_fingerprint"),
        "result_fingerprint": result.get("result_fingerprint"),
        "created_at_utc": _now(),
    }
    before_result = _read_json(_result_path(base, result_id))
    before_receipt = _read_json(_receipt_path(base, receipt_id))
    before_result_index = _read_json(base / "indexes" / RESULT_INDEX)
    before_receipt_index = _read_json(base / "indexes" / RECEIPT_INDEX)
    try:
        _atomic_write_json(_result_path(base, result_id), result)
        _atomic_write_json(_receipt_path(base, receipt_id), receipt)
        _update_result_index(base)
        _update_receipt_index(base)
    except Exception:
        _restore_json(_result_path(base, result_id), before_result)
        _restore_json(_receipt_path(base, receipt_id), before_receipt)
        _restore_json(base / "indexes" / RESULT_INDEX, before_result_index)
        _restore_json(base / "indexes" / RECEIPT_INDEX, before_receipt_index)
        return {"status": "corrupt", "production_authorization_plan_id": production_authorization_plan_id, "warnings": [], "blockers": ["production_authorization_result_write_failure"]}
    return {
        "status": result["status"],
        "production_authorization_plan_id": production_authorization_plan_id,
        "production_authorization_result_id": result_id,
        "production_authorization_receipt_id": receipt_id,
        "writes_performed": 2,
    }


def load_certified_rule_production_authorization_result(
    production_authorization_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    result = _find_result_by_id(base, production_authorization_result_id)
    if not isinstance(result, Mapping):
        return {"status": "not_found", "production_authorization_result_id": production_authorization_result_id, "production_authorization_result": None, "warnings": []}
    payload = dict(result)
    payload["stale"] = _result_is_stale(base, payload)
    return {"status": "loaded", "production_authorization_result_id": production_authorization_result_id, "production_authorization_result": payload, "warnings": []}


def get_certified_rule_production_authorization_health(
    production_authorization_plan_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    plans = _load_all(base / PLAN_DIR)
    results = _load_all(base / RESULT_DIR)
    receipts = _load_all(base / RECEIPT_DIR)
    if production_authorization_plan_id:
        plans = [item for item in plans if str(item.get("production_authorization_plan_id") or "") == production_authorization_plan_id]
        results = [item for item in results if str(item.get("production_authorization_plan_id") or "") == production_authorization_plan_id]
        receipts = [item for item in receipts if str(item.get("production_authorization_plan_id") or "") == production_authorization_plan_id]
    if not plans and not results and not receipts:
        return {"status": "empty", "production_authorization_plan_count": 0, "production_authorization_result_count": 0, "production_authorization_receipt_count": 0, "recommended_action": "Build one production authorization plan."}
    warnings: list[str] = []
    blockers: list[str] = []
    stale_count = 0
    for result in results:
        if _result_is_stale(base, result):
            stale_count += 1
        receipt = _find_receipt_for_result(base, str(result.get("production_authorization_result_id") or ""))
        if not isinstance(receipt, Mapping):
            warnings.append("production_authorization_receipt_missing")
        elif str(receipt.get("result_fingerprint") or "") != str(result.get("result_fingerprint") or ""):
            blockers.append("production_authorization_receipt_fingerprint_mismatch")
    if blockers:
        status = "corrupt"
    elif stale_count:
        status = "stale"
    elif warnings:
        status = "warning"
    else:
        status = "healthy"
    return {
        "status": status,
        "production_authorization_plan_count": len(plans),
        "production_authorization_result_count": len(results),
        "production_authorization_receipt_count": len(receipts),
        "stale_count": stale_count,
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
        "recommended_action": _recommended_action(status),
    }


def format_certified_rule_production_authorization_report(
    production_authorization_result_id: str | None = None,
    production_authorization_receipt_id: str | None = None,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    base = _ensure_dirs(root)
    result = _find_result_by_id(base, str(production_authorization_result_id or ""))
    receipt = _find_receipt_by_id(base, production_authorization_receipt_id)
    if not isinstance(result, Mapping):
        return "Production authorization result not found."
    lines = [
        "Certified Rule Production Authorization",
        f"Status: {result.get('status', 'unknown')}",
        f"Decision: {result.get('decision', 'unknown')}",
        f"Canonical Rule ID: {result.get('canonical_rule_id', 'unknown')}",
        f"Document ID: {result.get('document_id', 'unknown')}",
        f"Source Revision: {result.get('source_revision', 'unknown')}",
        f"Controlled Integration Result ID: {result.get('controlled_integration_result_id', 'unknown')}",
        f"Production Target ID: {result.get('production_target_id', 'unknown')}",
        f"Descriptor Fingerprint: {result.get('production_target_descriptor_fingerprint', 'unknown')}",
        f"Committed Namespace ID: {result.get('namespace_id', 'unknown')}",
        f"Committed State Fingerprint: {result.get('committed_state_fingerprint', 'unknown')}",
        "This phase records authorization only.",
        "No production deployment, activation, commit, rollback, scoring, or live Fast Lane execution occurred.",
    ]
    if isinstance(receipt, Mapping):
        lines.append(f"Receipt ID: {receipt.get('production_authorization_receipt_id', 'unknown')}")
    warnings = list(result.get("warnings", []))
    blockers = list(result.get("blockers", []))
    if warnings:
        lines.append("Warnings: " + ", ".join(str(item) for item in warnings))
    if blockers:
        lines.append("Blockers: " + ", ".join(str(item) for item in blockers))
    return "\n".join(lines)


def _load_bundle(base: Path, canonical_rule_id: str, controlled_integration_result_id: str, production_target_id: str) -> dict[str, Any]:
    rule_loaded = load_canonical_rule(canonical_rule_id, require_active=True, root=base)
    rule = rule_loaded.get("rule") if isinstance(rule_loaded.get("rule"), Mapping) else None
    certification = _load_certification_receipt_for_rule(base, canonical_rule_id)
    manifest = load_document_manifest(str((rule or {}).get("document_id") or ""), root=base).get("manifest") if isinstance(rule, Mapping) else None
    controlled_loaded = integration_backend.load_certified_rule_controlled_integration_result(controlled_integration_result_id, root=base)
    controlled_result = controlled_loaded.get("controlled_integration_result")
    controlled_receipt = _find_ci_receipt_for_result(base, controlled_integration_result_id) if isinstance(controlled_result, Mapping) else None
    release_result = release_receipt = source_auth = source_auth_receipt = scoring_result = fast_lane_result = None
    if isinstance(controlled_result, Mapping):
        release_result = release_candidate_backend.load_certified_rule_release_candidate_result(str(controlled_result.get("release_candidate_result_id") or ""), root=base).get("release_candidate_result")
        if isinstance(release_result, Mapping):
            release_receipt = release_candidate_backend._find_receipt_for_result(base, str(release_result.get("release_candidate_result_id") or ""))
        source_auth = integration_authorization_backend.load_certified_rule_integration_authorization_result(str(controlled_result.get("integration_authorization_result_id") or ""), root=base).get("integration_authorization_result")
        if isinstance(source_auth, Mapping):
            source_auth_receipt = integration_authorization_backend._find_receipt_for_result(base, str(source_auth.get("integration_authorization_result_id") or ""))
            scoring_result = integration_authorization_backend.scoring_backend.load_certified_rule_scoring_preview_result(str(source_auth.get("scoring_preview_result_id") or ""), root=base).get("scoring_preview_result")
            fast_lane_result = integration_authorization_backend.fast_lane_backend.load_certified_rule_fast_lane_preview_result(str(source_auth.get("fast_lane_preview_result_id") or ""), root=base).get("fast_lane_preview_result")
    committed_state = None
    if isinstance(controlled_result, Mapping):
        committed_state = target_backend.read_controlled_integration_target_state(
            str(controlled_result.get("integration_target_id") or ""),
            namespace_id=str(controlled_result.get("namespace_id") or ""),
            root=base,
        )
    descriptor_loaded = descriptor_backend.load_production_target_descriptor(production_target_id, root=base)
    descriptor_health = descriptor_backend.get_production_target_descriptor_health(production_target_id, root=base)
    return {
        "rule_loaded": rule_loaded,
        "rule": rule,
        "certification": certification,
        "manifest": manifest,
        "controlled_integration_loaded": controlled_loaded,
        "controlled_integration_result": controlled_result,
        "controlled_integration_receipt": controlled_receipt,
        "release_candidate_result": release_result,
        "release_candidate_receipt": release_receipt,
        "integration_authorization_result": source_auth,
        "integration_authorization_receipt": source_auth_receipt,
        "scoring_result": scoring_result,
        "fast_lane_result": fast_lane_result,
        "committed_state": committed_state,
        "descriptor_loaded": descriptor_loaded,
        "descriptor_health": descriptor_health,
    }


def _ensure_dirs(root: Path | str) -> Path:
    base = _ensure_analysis_dirs(root)
    for folder in (PLAN_DIR, RESULT_DIR, RECEIPT_DIR, "indexes"):
        (base / folder).mkdir(parents=True, exist_ok=True)
    return base


def _rollback_pending(rule: Mapping[str, Any]) -> bool:
    return bool(rule.get("rollback_pending")) or bool(rule.get("rollback_requested"))


def _plan_id(bundle: Mapping[str, Any]) -> str:
    result = bundle.get("controlled_integration_result") or {}
    descriptor = (bundle.get("descriptor_loaded") or {}).get("production_target_descriptor") or {}
    return "production_authorization_plan_" + _hash_payload(
        {
            "canonical_rule_id": result.get("canonical_rule_id"),
            "controlled_integration_result_id": result.get("controlled_integration_result_id"),
            "controlled_integration_result_fingerprint": result.get("result_fingerprint"),
            "production_target_id": descriptor.get("target_id"),
            "descriptor_fingerprint": descriptor.get("descriptor_fingerprint"),
        }
    )[7:23]


def _result_id(plan_id: str) -> str:
    return "production_authorization_result_" + _hash_payload({"plan_id": plan_id})[7:23]


def _receipt_id(result_id: str) -> str:
    return "production_authorization_receipt_" + _hash_payload({"result_id": result_id})[7:23]


def _plan_fingerprint(bundle: Mapping[str, Any]) -> str:
    result = bundle.get("controlled_integration_result") or {}
    descriptor = (bundle.get("descriptor_loaded") or {}).get("production_target_descriptor") or {}
    committed = bundle.get("committed_state") or {}
    return _hash_payload(
        {
            "schema_version": AUTH_SCHEMA_VERSION,
            "canonical_rule_id": result.get("canonical_rule_id"),
            "document_id": result.get("document_id"),
            "source_revision": result.get("source_revision"),
            "controlled_integration_result_id": result.get("controlled_integration_result_id"),
            "controlled_integration_result_fingerprint": result.get("result_fingerprint"),
            "release_candidate_result_fingerprint": result.get("release_candidate_result_fingerprint"),
            "integration_authorization_result_fingerprint": result.get("integration_authorization_result_fingerprint"),
            "scoring_preview_result_fingerprint": result.get("scoring_preview_result_fingerprint"),
            "scoring_config_fingerprint": result.get("scoring_config_fingerprint"),
            "fast_lane_preview_result_fingerprint": result.get("fast_lane_preview_result_fingerprint"),
            "fast_lane_contract_version": result.get("fast_lane_contract_version"),
            "fast_lane_capability_fingerprint": result.get("fast_lane_capability_fingerprint"),
            "isolated_target_id": result.get("integration_target_id"),
            "isolated_target_fingerprint": result.get("target_fingerprint"),
            "adapter_id": result.get("adapter_id"),
            "adapter_version": result.get("adapter_version"),
            "adapter_fingerprint": result.get("adapter_fingerprint"),
            "package_fingerprint": result.get("package_fingerprint"),
            "transaction_id": result.get("transaction_id"),
            "namespace_id": result.get("namespace_id"),
            "committed_state_fingerprint": committed.get("state_fingerprint") or result.get("committed_state_fingerprint"),
            "production_target_id": descriptor.get("target_id"),
            "descriptor_fingerprint": descriptor.get("descriptor_fingerprint"),
            "production_adapter_manifest_fingerprint": descriptor.get("adapter_manifest_fingerprint"),
            "production_adapter_capability_fingerprint": descriptor.get("adapter_capability_fingerprint"),
        }
    )


def _result_fingerprint(result: Mapping[str, Any]) -> str:
    return _hash_payload(
        {
            "schema_version": AUTH_SCHEMA_VERSION,
            "production_authorization_plan_id": result.get("production_authorization_plan_id"),
            "controlled_integration_result_fingerprint": result.get("controlled_integration_result_fingerprint"),
            "production_target_descriptor_fingerprint": result.get("production_target_descriptor_fingerprint"),
            "decision": result.get("decision"),
            "status": result.get("status"),
            "committed_state_fingerprint": result.get("committed_state_fingerprint"),
        }
    )


def _eligibility_status(blockers: list[str], warnings: list[str]) -> str:
    if blockers and all("fingerprint_mismatch" in item or "receipt" in item for item in blockers):
        return "corrupt"
    if any(
        "stale" in item
        or item
        in {
            "source_revision_not_current",
            "rule_has_pending_rollback",
            "rule_pending_supersession",
            "production_target_adapter_manifest_version_mismatch",
            "production_target_descriptor_fingerprint_mismatch",
        }
        for item in blockers
    ):
        return "stale"
    if blockers:
        return "blocked"
    return "eligible_with_warnings" if warnings else "eligible"


def _recommended_action(status: str) -> str:
    if status in {"eligible", "eligible_with_warnings"}:
        return "Build or record the production authorization decision."
    if status == "stale":
        return "Refresh the evidence chain or production target descriptor before authorizing."
    if status == "corrupt":
        return "Repair inconsistent authorization evidence before saving a production authorization decision."
    if status == "healthy":
        return "Production authorization records are internally consistent."
    if status == "warning":
        return "Review warnings before relying on the stored authorization record."
    return "Resolve blockers before production authorization."


def _plan_summary(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "canonical_rule_id": plan.get("canonical_rule_id"),
        "document_id": plan.get("document_id"),
        "source_revision": plan.get("source_revision"),
        "controlled_integration_result_id": plan.get("controlled_integration_result_id"),
        "production_target_id": plan.get("production_target_id"),
        "namespace_id": plan.get("namespace_id"),
        "transaction_id": plan.get("transaction_id"),
        "plan_fingerprint": plan.get("plan_fingerprint"),
        "committed_state_fingerprint": plan.get("committed_state_fingerprint"),
        "production_target_descriptor_fingerprint": plan.get("production_target_descriptor_fingerprint"),
        "descriptor_fingerprint": plan.get("production_target_descriptor_fingerprint"),
        "recommended_action": "Save the explicit production authorization decision.",
    }


def _result_is_stale(base: Path, result: Mapping[str, Any]) -> bool:
    bundle = _load_bundle(
        base,
        str(result.get("canonical_rule_id") or ""),
        str(result.get("controlled_integration_result_id") or ""),
        str(result.get("production_target_id") or ""),
    )
    if not bundle.get("controlled_integration_result") or not (bundle.get("descriptor_loaded") or {}).get("production_target_descriptor"):
        return True
    current_plan_fingerprint = _plan_fingerprint(bundle)
    return any(
        [
            str(result.get("controlled_integration_result_fingerprint") or "") != str((bundle.get("controlled_integration_result") or {}).get("result_fingerprint") or ""),
            str(result.get("production_target_descriptor_fingerprint") or "") != str(((bundle.get("descriptor_loaded") or {}).get("production_target_descriptor") or {}).get("descriptor_fingerprint") or ""),
            str(result.get("committed_state_fingerprint") or "") != str(((bundle.get("committed_state") or {}).get("state_fingerprint")) or ""),
            str(result.get("production_authorization_plan_id") or "") != _plan_id(bundle),
            str((_read_json(_plan_path(base, str(result.get("production_authorization_plan_id") or ""))) or {}).get("plan_fingerprint") or "") != current_plan_fingerprint,
        ]
    )


def _find_ci_receipt_for_result(base: Path, result_id: str) -> dict[str, Any] | None:
    receipt_path = base / integration_backend.RECEIPT_DIR
    for payload in _load_all(receipt_path):
        if str(payload.get("controlled_integration_result_id") or "") == result_id:
            return payload
    return None


def _load_all(folder: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping):
            items.append(dict(payload))
    return items


def _plan_path(base: Path, plan_id: str) -> Path:
    return base / PLAN_DIR / f"{_safe_id(plan_id)}.json"


def _result_path(base: Path, result_id: str) -> Path:
    return base / RESULT_DIR / f"{_safe_id(result_id)}.json"


def _receipt_path(base: Path, receipt_id: str) -> Path:
    return base / RECEIPT_DIR / f"{_safe_id(receipt_id)}.json"


def _find_plan(base: Path, canonical_rule_id: str, controlled_integration_result_id: str, production_target_id: str) -> dict[str, Any] | None:
    for item in _load_all(base / PLAN_DIR):
        if (
            str(item.get("canonical_rule_id") or "") == canonical_rule_id
            and str(item.get("controlled_integration_result_id") or "") == controlled_integration_result_id
            and str(item.get("production_target_id") or "") == production_target_id
        ):
            return item
    return None


def _find_result(base: Path, plan_id: str) -> dict[str, Any] | None:
    for item in _load_all(base / RESULT_DIR):
        if str(item.get("production_authorization_plan_id") or "") == plan_id:
            return item
    return None


def _find_result_by_id(base: Path, result_id: str) -> dict[str, Any] | None:
    payload = _read_json(_result_path(base, result_id))
    return dict(payload) if isinstance(payload, Mapping) else None


def _find_receipt_for_result(base: Path, result_id: str) -> dict[str, Any] | None:
    for item in _load_all(base / RECEIPT_DIR):
        if str(item.get("production_authorization_result_id") or "") == result_id:
            return item
    return None


def _find_receipt_by_id(base: Path, receipt_id: str | None) -> dict[str, Any] | None:
    if not receipt_id:
        return None
    payload = _read_json(_receipt_path(base, receipt_id))
    return dict(payload) if isinstance(payload, Mapping) else None


def _update_plan_index(base: Path) -> None:
    items = [
        {
            "production_authorization_plan_id": item.get("production_authorization_plan_id"),
            "canonical_rule_id": item.get("canonical_rule_id"),
            "controlled_integration_result_id": item.get("controlled_integration_result_id"),
            "production_target_id": item.get("production_target_id"),
            "plan_fingerprint": item.get("plan_fingerprint"),
        }
        for item in _load_all(base / PLAN_DIR)
    ]
    _atomic_write_json(base / "indexes" / PLAN_INDEX, {"schema_version": "certified_rule_production_authorization_plan_index_v1", "items": items, "updated_at_utc": _now()})


def _update_result_index(base: Path) -> None:
    items = [
        {
            "production_authorization_result_id": item.get("production_authorization_result_id"),
            "production_authorization_plan_id": item.get("production_authorization_plan_id"),
            "canonical_rule_id": item.get("canonical_rule_id"),
            "production_target_id": item.get("production_target_id"),
            "status": item.get("status"),
            "decision": item.get("decision"),
        }
        for item in _load_all(base / RESULT_DIR)
    ]
    _atomic_write_json(base / "indexes" / RESULT_INDEX, {"schema_version": "certified_rule_production_authorization_result_index_v1", "items": items, "updated_at_utc": _now()})


def _update_receipt_index(base: Path) -> None:
    items = [
        {
            "production_authorization_receipt_id": item.get("production_authorization_receipt_id"),
            "production_authorization_result_id": item.get("production_authorization_result_id"),
            "canonical_rule_id": item.get("canonical_rule_id"),
            "status": item.get("status"),
        }
        for item in _load_all(base / RECEIPT_DIR)
    ]
    _atomic_write_json(base / "indexes" / RECEIPT_INDEX, {"schema_version": "certified_rule_production_authorization_receipt_index_v1", "items": items, "updated_at_utc": _now()})


def _certification_fingerprint(certification: Mapping[str, Any] | None) -> str | None:
    return integration_authorization_backend._certification_fingerprint(certification)


def _match(blockers: list[str], left: Any, right: Any, code: str) -> None:
    if str(left or "") != str(right or ""):
        blockers.append(code)


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in items if str(item)))
