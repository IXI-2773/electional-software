"""Controlled staging orchestration over one qualified release candidate."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from . import certified_rule_controlled_integration_target as target_backend
from . import certified_rule_integration_authorization as authorization_backend
from . import certified_rule_release_candidate as release_candidate_backend
from .canonical_rule_runtime import _atomic_write_json, _now, _read_json, _restore_json, _safe_id, load_canonical_rule
from .certified_rule_replay_adapter import _rule_has_unresolved_critical_remediation, _rule_pending_supersession
from .document_manifest import load_document_manifest
from .rule_effectiveness_analysis import _ensure_analysis_dirs, _hash_payload, _load_certification_receipt_for_rule
from .source_documents import SOURCE_DOCUMENT_ROOT

PLAN_DIR = "certified_rule_controlled_integration_plans"
RESULT_DIR = "certified_rule_controlled_integration_results"
RECEIPT_DIR = "certified_rule_controlled_integration_receipts"
PLAN_INDEX = "certified_rule_controlled_integration_plan_index.json"
RESULT_INDEX = "certified_rule_controlled_integration_result_index.json"
RECEIPT_INDEX = "certified_rule_controlled_integration_receipt_index.json"
PLAN_SCHEMA = "certified_rule_controlled_integration_plan_v1"
RESULT_SCHEMA = "certified_rule_controlled_integration_result_v1"
RECEIPT_SCHEMA = "certified_rule_controlled_integration_receipt_v1"
EXECUTION_SCHEMA_VERSION = "certified_rule_controlled_integration_v1"
EXECUTION_MODE = "isolated_non_production_controlled_integration"
REQUIRED_CONFIRMATION = "EXECUTE_CONTROLLED_INTEGRATION"
AUTHORIZED_DECISION = "authorize_for_later_integration"
QUALIFIED_STATUSES = {"qualified", "qualified_with_warnings"}
ELIGIBILITY_STATUSES = {"eligible", "eligible_with_warnings", "not_eligible", "blocked", "stale", "corrupt", "unknown"}
FINAL_STATUSES = {
    "completed",
    "completed_with_warnings",
    "apply_failed",
    "verification_failed",
    "commit_failed",
    "rollback_completed",
    "rollback_failed",
    "blocked",
    "stale",
    "mutation_detected",
    "corrupt",
    "already_completed",
}


def build_certified_rule_controlled_integration_workspace(
    canonical_rule_id: str,
    release_candidate_result_id: str,
    integration_target_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    eligibility = validate_certified_rule_controlled_integration_eligibility(canonical_rule_id, release_candidate_result_id, integration_target_id, root=base)
    bundle = _load_bundle(base, canonical_rule_id, release_candidate_result_id, integration_target_id)
    plan = _find_plan(base, canonical_rule_id, release_candidate_result_id, integration_target_id)
    result = _find_result(base, str((plan or {}).get("controlled_integration_plan_id") or ""))
    receipt = _find_receipt_for_result(base, str((result or {}).get("controlled_integration_result_id") or ""))
    return {
        "status": "ready_for_planning" if str(eligibility.get("status") or "") in {"eligible", "eligible_with_warnings"} else str(eligibility.get("status") or "blocked"),
        "canonical_rule_id": canonical_rule_id,
        "document_id": eligibility.get("document_id"),
        "source_revision": eligibility.get("source_revision"),
        "certification_status": eligibility.get("certification_status", "unknown"),
        "release_candidate_status": eligibility.get("release_candidate_status", "unknown"),
        "authorization_status": eligibility.get("authorization_status", "unknown"),
        "target_status": eligibility.get("target_status", "unknown"),
        "environment_class": eligibility.get("environment_class", "unknown"),
        "adapter_version": eligibility.get("adapter_version", "unknown"),
        "adapter_manifest_fingerprint": eligibility.get("adapter_fingerprint"),
        "target_fingerprint": eligibility.get("target_fingerprint"),
        "namespace_id": (plan or {}).get("namespace_id"),
        "transaction_id": (plan or {}).get("transaction_id"),
        "controlled_integration_plan_id": (plan or {}).get("controlled_integration_plan_id"),
        "controlled_integration_result_id": (result or {}).get("controlled_integration_result_id"),
        "controlled_integration_receipt_id": (receipt or {}).get("controlled_integration_receipt_id"),
        "warnings": list(eligibility.get("warnings", [])),
        "blockers": list(eligibility.get("blockers", [])),
        "recommended_action": "Build the controlled integration plan." if not eligibility.get("blockers") else eligibility.get("recommended_action", "Resolve blockers before controlled integration."),
        "release_candidate_result": _safe_identity(bundle.get("release_candidate_result")),
        "authorization_result": _safe_identity(bundle.get("authorization_result")),
        "scoring_result": _safe_identity(bundle.get("scoring_result")),
        "fast_lane_result": _safe_identity(bundle.get("fast_lane_result")),
    }


def validate_certified_rule_controlled_integration_eligibility(
    canonical_rule_id: str,
    release_candidate_result_id: str,
    integration_target_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    bundle = _load_bundle(base, canonical_rule_id, release_candidate_result_id, integration_target_id)
    blockers: list[str] = []
    warnings: list[str] = []

    rule_loaded = bundle.get("rule_loaded") if isinstance(bundle.get("rule_loaded"), Mapping) else {}
    rule = bundle.get("rule") if isinstance(bundle.get("rule"), Mapping) else {}
    certification = bundle.get("certification") if isinstance(bundle.get("certification"), Mapping) else {}
    manifest = bundle.get("manifest") if isinstance(bundle.get("manifest"), Mapping) else {}
    release_result = bundle.get("release_candidate_result") if isinstance(bundle.get("release_candidate_result"), Mapping) else {}
    release_receipt = bundle.get("release_candidate_receipt") if isinstance(bundle.get("release_candidate_receipt"), Mapping) else {}
    authorization_result = bundle.get("authorization_result") if isinstance(bundle.get("authorization_result"), Mapping) else {}
    authorization_receipt = bundle.get("authorization_receipt") if isinstance(bundle.get("authorization_receipt"), Mapping) else {}
    scoring_result = bundle.get("scoring_result") if isinstance(bundle.get("scoring_result"), Mapping) else {}
    fast_lane_result = bundle.get("fast_lane_result") if isinstance(bundle.get("fast_lane_result"), Mapping) else {}
    target_workspace = bundle.get("target_workspace") if isinstance(bundle.get("target_workspace"), Mapping) else {}
    target_validation = bundle.get("target_validation") if isinstance(bundle.get("target_validation"), Mapping) else {}
    adapter_manifest = target_workspace.get("adapter_manifest") if isinstance(target_workspace.get("adapter_manifest"), Mapping) else {}
    target_manifest = target_workspace.get("target_manifest") if isinstance(target_workspace.get("target_manifest"), Mapping) else {}
    target_health = target_workspace.get("target_health") if isinstance(target_workspace.get("target_health"), Mapping) else {}

    if str(rule_loaded.get("status") or "") != "loaded" or not rule:
        blockers.append("canonical_rule_not_active")
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

    if not release_result:
        blockers.append("release_candidate_result_missing")
    elif not release_receipt:
        blockers.append("release_candidate_receipt_missing")
    else:
        release_status = str(release_result.get("qualification_status") or release_result.get("status") or "")
        if release_status not in QUALIFIED_STATUSES:
            blockers.append("release_candidate_not_qualified")
        if str(release_receipt.get("result_fingerprint") or "") != str(release_result.get("result_fingerprint") or ""):
            blockers.append("release_candidate_receipt_fingerprint_mismatch")
        if release_candidate_backend._result_is_stale(base, release_result) or bool(release_result.get("stale")):
            blockers.append("release_candidate_result_stale")
        if str(release_result.get("canonical_rule_id") or "") != canonical_rule_id:
            blockers.append("release_candidate_rule_mismatch")
        if rule and str(release_result.get("document_id") or "") != str(rule.get("document_id") or ""):
            blockers.append("release_candidate_document_mismatch")
        if rule and str(release_result.get("source_revision") or "") != str(rule.get("source_revision") or ""):
            blockers.append("release_candidate_source_revision_mismatch")
        if rule and str(release_result.get("rule_fingerprint") or "") != str(rule.get("rule_fingerprint") or ""):
            blockers.append("release_candidate_rule_fingerprint_mismatch")
        if str(release_result.get("certification_fingerprint") or "") != str(_certification_fingerprint(certification) or ""):
            blockers.append("release_candidate_certification_fingerprint_mismatch")
        if str(release_result.get("qualification_status") or "") == "mutation_detected":
            blockers.append("release_candidate_mutation_detected")

    if not authorization_result:
        blockers.append("integration_authorization_result_missing")
    elif not authorization_receipt:
        blockers.append("integration_authorization_receipt_missing")
    else:
        if str(authorization_result.get("status") or "") != "authorized":
            blockers.append("integration_authorization_not_authorized")
        if str(authorization_result.get("decision") or "") != AUTHORIZED_DECISION:
            blockers.append("integration_authorization_decision_invalid")
        if str(authorization_receipt.get("result_fingerprint") or "") != str(authorization_result.get("result_fingerprint") or ""):
            blockers.append("integration_authorization_receipt_fingerprint_mismatch")
        if authorization_backend._result_is_stale(base, authorization_result) or bool(authorization_result.get("stale")):
            blockers.append("integration_authorization_result_stale")

    if not scoring_result:
        blockers.append("scoring_preview_result_missing")
    else:
        if bool(scoring_result.get("stale")):
            blockers.append("scoring_preview_result_stale")
        if str(scoring_result.get("status") or "") not in authorization_backend.FINAL_SCORING_STATUSES:
            blockers.append("scoring_preview_not_completed")

    if not fast_lane_result:
        blockers.append("fast_lane_preview_result_missing")
    else:
        if bool(fast_lane_result.get("stale")):
            blockers.append("fast_lane_preview_result_stale")
        if str(fast_lane_result.get("preview_status") or "") not in authorization_backend.FINAL_FAST_LANE_STATUSES:
            blockers.append("fast_lane_preview_not_completed")

    if release_result and authorization_result:
        _match(blockers, release_result.get("integration_authorization_result_id"), authorization_result.get("integration_authorization_result_id"), "release_candidate_authorization_id_mismatch")
        _match(blockers, release_result.get("integration_authorization_result_fingerprint"), authorization_result.get("result_fingerprint"), "release_candidate_authorization_fingerprint_mismatch")
        _match(blockers, authorization_result.get("canonical_rule_id"), canonical_rule_id, "authorization_rule_mismatch")
        _match(blockers, authorization_result.get("document_id"), rule.get("document_id"), "authorization_document_mismatch")
        _match(blockers, authorization_result.get("source_revision"), rule.get("source_revision"), "authorization_source_revision_mismatch")
        _match(blockers, authorization_result.get("rule_fingerprint"), rule.get("rule_fingerprint"), "authorization_rule_fingerprint_mismatch")
        _match(blockers, authorization_result.get("certification_fingerprint"), _certification_fingerprint(certification), "authorization_certification_fingerprint_mismatch")

    if authorization_result and scoring_result:
        _match(blockers, authorization_result.get("scoring_preview_result_id"), scoring_result.get("scoring_preview_result_id"), "authorization_scoring_preview_id_mismatch")
        _match(blockers, authorization_result.get("scoring_preview_result_fingerprint"), scoring_result.get("result_fingerprint"), "authorization_scoring_preview_fingerprint_mismatch")
        _match(blockers, authorization_result.get("scoring_config_id"), scoring_result.get("scoring_config_id"), "authorization_scoring_config_id_mismatch")
        _match(blockers, authorization_result.get("scoring_config_fingerprint"), scoring_result.get("scoring_config_fingerprint"), "authorization_scoring_config_fingerprint_mismatch")

    if release_result and scoring_result:
        _match(blockers, release_result.get("scoring_preview_result_id"), scoring_result.get("scoring_preview_result_id"), "release_candidate_scoring_preview_id_mismatch")
        _match(blockers, release_result.get("scoring_preview_result_fingerprint"), scoring_result.get("result_fingerprint"), "release_candidate_scoring_preview_fingerprint_mismatch")
        _match(blockers, release_result.get("scoring_config_fingerprint"), scoring_result.get("scoring_config_fingerprint"), "release_candidate_scoring_config_fingerprint_mismatch")

    if authorization_result and fast_lane_result:
        _match(blockers, authorization_result.get("fast_lane_preview_result_id"), fast_lane_result.get("fast_lane_preview_result_id"), "authorization_fast_lane_preview_id_mismatch")
        _match(blockers, authorization_result.get("fast_lane_preview_result_fingerprint"), fast_lane_result.get("result_fingerprint"), "authorization_fast_lane_preview_fingerprint_mismatch")
        _match(blockers, authorization_result.get("fast_lane_capability_fingerprint"), fast_lane_result.get("fast_lane_capability_fingerprint"), "authorization_fast_lane_capability_fingerprint_mismatch")

    if release_result and fast_lane_result:
        _match(blockers, release_result.get("fast_lane_preview_result_id"), fast_lane_result.get("fast_lane_preview_result_id"), "release_candidate_fast_lane_preview_id_mismatch")
        _match(blockers, release_result.get("fast_lane_preview_result_fingerprint"), fast_lane_result.get("result_fingerprint"), "release_candidate_fast_lane_preview_fingerprint_mismatch")
        _match(blockers, release_result.get("fast_lane_contract_id"), fast_lane_result.get("fast_lane_contract_id"), "release_candidate_fast_lane_contract_id_mismatch")
        _match(blockers, release_result.get("fast_lane_contract_version"), fast_lane_result.get("fast_lane_contract_version"), "release_candidate_fast_lane_contract_version_mismatch")
        _match(blockers, release_result.get("fast_lane_capability_fingerprint"), fast_lane_result.get("fast_lane_capability_fingerprint"), "release_candidate_fast_lane_capability_fingerprint_mismatch")

    blockers.extend(list(target_validation.get("blockers", [])))
    if str(target_workspace.get("status") or "") != "loaded":
        blockers.append("integration_target_workspace_unavailable")
    if str(target_manifest.get("environment_class") or "") != "isolated_non_production":
        blockers.append("integration_target_not_isolated_non_production")
    if str(target_health.get("status") or "") not in {"healthy", "loaded"}:
        blockers.append("integration_target_unhealthy")
    if not adapter_manifest:
        blockers.append("integration_adapter_manifest_missing")
    else:
        if str(adapter_manifest.get("environment_class") or "") != "isolated_non_production":
            blockers.append("integration_adapter_environment_invalid")
        if not bool(adapter_manifest.get("supports_transactional_apply")):
            blockers.append("integration_adapter_transaction_capability_missing")
        if not bool(adapter_manifest.get("supports_independent_readback")):
            blockers.append("integration_adapter_verification_capability_missing")
        if not bool(adapter_manifest.get("supports_explicit_commit")):
            blockers.append("integration_adapter_commit_capability_missing")
        if not bool(adapter_manifest.get("supports_rollback")):
            blockers.append("integration_adapter_rollback_capability_missing")
        if bool(adapter_manifest.get("supports_production")):
            blockers.append("integration_adapter_production_support_forbidden")
    status = _eligibility_status(blockers, warnings)
    return {
        "status": status,
        "canonical_rule_id": canonical_rule_id,
        "document_id": rule.get("document_id"),
        "source_revision": rule.get("source_revision"),
        "rule_status": rule.get("status", rule_loaded.get("status", "unknown")),
        "certification_status": certification.get("certification_status", "missing"),
        "release_candidate_status": release_result.get("qualification_status", "missing"),
        "authorization_status": authorization_result.get("status", "missing"),
        "scoring_evidence_status": scoring_result.get("status", "missing"),
        "fast_lane_evidence_status": fast_lane_result.get("preview_status", "missing"),
        "target_status": target_workspace.get("status", "unknown"),
        "environment_status": target_manifest.get("environment_class", "unknown"),
        "adapter_status": "loaded" if adapter_manifest else "missing",
        "transaction_capability": bool(adapter_manifest.get("supports_transactional_apply")) if adapter_manifest else False,
        "verification_capability": bool(adapter_manifest.get("supports_independent_readback")) if adapter_manifest else False,
        "commit_capability": bool(adapter_manifest.get("supports_explicit_commit")) if adapter_manifest else False,
        "rollback_capability": bool(adapter_manifest.get("supports_rollback")) if adapter_manifest else False,
        "environment_class": target_manifest.get("environment_class", "unknown"),
        "adapter_id": adapter_manifest.get("adapter_id", target_manifest.get("adapter_id", "unknown")),
        "adapter_version": adapter_manifest.get("adapter_version", target_manifest.get("adapter_version", "unknown")),
        "adapter_fingerprint": adapter_manifest.get("adapter_fingerprint"),
        "target_fingerprint": target_manifest.get("target_fingerprint"),
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
        "recommended_action": _recommended_action(status),
    }


def build_certified_rule_controlled_integration_plan(
    canonical_rule_id: str,
    release_candidate_result_id: str,
    integration_target_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    eligibility = validate_certified_rule_controlled_integration_eligibility(canonical_rule_id, release_candidate_result_id, integration_target_id, root=base)
    if str(eligibility.get("status") or "") not in {"eligible", "eligible_with_warnings"}:
        return {
            "status": eligibility.get("status", "blocked"),
            "canonical_rule_id": canonical_rule_id,
            "release_candidate_result_id": release_candidate_result_id,
            "integration_target_id": integration_target_id,
            "warnings": list(eligibility.get("warnings", [])),
            "blockers": list(eligibility.get("blockers", [])),
        }
    bundle = _load_bundle(base, canonical_rule_id, release_candidate_result_id, integration_target_id)
    package = _integration_package(bundle)
    package_validation = target_backend.validate_controlled_integration_package(integration_target_id, package, root=base)
    preflight = target_backend.preflight_controlled_integration_transaction(integration_target_id, package, root=base)
    blockers = _dedupe([*list(eligibility.get("blockers", [])), *list(package_validation.get("blockers", [])), *list(preflight.get("blockers", []))])
    warnings = _dedupe([*list(eligibility.get("warnings", [])), *list(package_validation.get("warnings", [])), *list(preflight.get("warnings", []))])
    if str(preflight.get("status") or "") not in {"ready", "already_committed"}:
        return {
            "status": "blocked" if str(preflight.get("status") or "") == "blocked" else str(preflight.get("status") or "blocked"),
            "canonical_rule_id": canonical_rule_id,
            "release_candidate_result_id": release_candidate_result_id,
            "integration_target_id": integration_target_id,
            "warnings": warnings,
            "blockers": blockers or ["integration_preflight_not_ready"],
        }
    release_result = dict(bundle.get("release_candidate_result") or {})
    release_receipt = dict(bundle.get("release_candidate_receipt") or {})
    authorization_result = dict(bundle.get("authorization_result") or {})
    authorization_receipt = dict(bundle.get("authorization_receipt") or {})
    scoring_result = dict(bundle.get("scoring_result") or {})
    fast_lane_result = dict(bundle.get("fast_lane_result") or {})
    target_workspace = dict(bundle.get("target_workspace") or {})
    adapter_manifest = dict(target_workspace.get("adapter_manifest") or {})
    target_manifest = dict(target_workspace.get("target_manifest") or {})
    certification = dict(bundle.get("certification") or {})
    plan = {
        "schema_version": PLAN_SCHEMA,
        "execution_schema_version": EXECUTION_SCHEMA_VERSION,
        "controlled_integration_plan_id": _plan_id(package, preflight),
        "canonical_rule_id": canonical_rule_id,
        "document_id": package.get("document_id"),
        "source_revision": package.get("source_revision"),
        "certification_id": package.get("certification_id"),
        "certification_fingerprint": package.get("certification_fingerprint"),
        "release_candidate_result_id": release_result.get("release_candidate_result_id"),
        "release_candidate_receipt_id": release_receipt.get("release_candidate_receipt_id"),
        "release_candidate_result_fingerprint": release_result.get("result_fingerprint"),
        "integration_authorization_result_id": authorization_result.get("integration_authorization_result_id"),
        "integration_authorization_receipt_id": authorization_receipt.get("integration_authorization_receipt_id"),
        "integration_authorization_result_fingerprint": authorization_result.get("result_fingerprint"),
        "scoring_preview_result_id": scoring_result.get("scoring_preview_result_id"),
        "scoring_preview_receipt_id": scoring_result.get("scoring_preview_receipt_id"),
        "scoring_preview_result_fingerprint": scoring_result.get("result_fingerprint"),
        "scoring_config_id": scoring_result.get("scoring_config_id"),
        "scoring_config_fingerprint": scoring_result.get("scoring_config_fingerprint"),
        "fast_lane_preview_result_id": fast_lane_result.get("fast_lane_preview_result_id"),
        "fast_lane_preview_receipt_id": fast_lane_result.get("fast_lane_preview_receipt_id"),
        "fast_lane_preview_result_fingerprint": fast_lane_result.get("result_fingerprint"),
        "fast_lane_contract_id": fast_lane_result.get("fast_lane_contract_id"),
        "fast_lane_contract_version": fast_lane_result.get("fast_lane_contract_version"),
        "fast_lane_capability_fingerprint": fast_lane_result.get("fast_lane_capability_fingerprint"),
        "adapter_id": adapter_manifest.get("adapter_id"),
        "adapter_version": adapter_manifest.get("adapter_version"),
        "adapter_fingerprint": adapter_manifest.get("adapter_fingerprint"),
        "integration_target_id": integration_target_id,
        "environment_class": target_manifest.get("environment_class"),
        "target_fingerprint": target_manifest.get("target_fingerprint"),
        "package_id": package.get("package_id"),
        "package_fingerprint": package.get("package_fingerprint"),
        "namespace_id": preflight.get("namespace_id"),
        "transaction_id": preflight.get("transaction_id"),
        "pre_apply_target_state_fingerprint": preflight.get("pre_apply_target_state_fingerprint"),
        "preflight_status": preflight.get("status"),
        "execution_mode": EXECUTION_MODE,
        "plan_fingerprint": _plan_fingerprint(package, preflight, adapter_manifest, target_manifest),
        "warnings": warnings,
        "blockers": blockers,
    }
    path = _plan_path(base, str(plan["controlled_integration_plan_id"]))
    existing = _read_json(path)
    if isinstance(existing, Mapping):
        if str(existing.get("plan_fingerprint") or "") == str(plan.get("plan_fingerprint") or ""):
            return {"status": "planned", "controlled_integration_plan_id": plan["controlled_integration_plan_id"], "writes_performed": 0, **_plan_summary(plan)}
        return {"status": "corrupt", "controlled_integration_plan_id": plan["controlled_integration_plan_id"], "warnings": [], "blockers": ["controlled_integration_plan_divergence"]}
    before_plan = _read_json(path)
    before_index = _read_json(base / "indexes" / PLAN_INDEX)
    try:
        _atomic_write_json(path, plan)
        _update_plan_index(base)
    except Exception:
        _restore_json(path, before_plan)
        _restore_json(base / "indexes" / PLAN_INDEX, before_index)
        return {"status": "corrupt", "controlled_integration_plan_id": plan["controlled_integration_plan_id"], "warnings": [], "blockers": ["controlled_integration_plan_write_failure"]}
    return {"status": "planned", "controlled_integration_plan_id": plan["controlled_integration_plan_id"], "writes_performed": 1, **_plan_summary(plan)}


def execute_certified_rule_controlled_integration(
    controlled_integration_plan_id: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    if confirmation != REQUIRED_CONFIRMATION:
        return {"status": "blocked", "controlled_integration_plan_id": controlled_integration_plan_id, "warnings": [], "blockers": ["controlled_integration_confirmation_required"]}
    plan = _read_json(_plan_path(base, controlled_integration_plan_id))
    if not isinstance(plan, Mapping):
        return {"status": "blocked", "controlled_integration_plan_id": controlled_integration_plan_id, "warnings": [], "blockers": ["controlled_integration_plan_missing"]}
    if str(plan.get("execution_mode") or "") != EXECUTION_MODE:
        return {"status": "corrupt", "controlled_integration_plan_id": controlled_integration_plan_id, "warnings": [], "blockers": ["controlled_integration_plan_mode_invalid"]}

    canonical_rule_id = str(plan.get("canonical_rule_id") or "")
    release_candidate_result_id = str(plan.get("release_candidate_result_id") or "")
    target_id = str(plan.get("integration_target_id") or "")
    existing = _find_result(base, controlled_integration_plan_id)
    if isinstance(existing, Mapping):
        existing_receipt = _find_receipt_for_result(base, str(existing.get("controlled_integration_result_id") or ""))
        verification = target_backend.read_controlled_integration_target_state(target_id, namespace_id=str(existing.get("namespace_id") or ""), root=base)
        if (
            str(existing.get("final_status") or "") in {"completed", "completed_with_warnings"}
            and isinstance(existing_receipt, Mapping)
            and not _result_is_stale(base, existing)
            and str(verification.get("verification_status") or "") == "verified_committed"
            and str(verification.get("state_fingerprint") or "") == str(existing.get("committed_state_fingerprint") or "")
            and str(existing_receipt.get("result_fingerprint") or "") == str(existing.get("result_fingerprint") or "")
        ):
            return {
                "status": "already_completed",
                "controlled_integration_plan_id": controlled_integration_plan_id,
                "controlled_integration_result_id": existing.get("controlled_integration_result_id"),
                "controlled_integration_receipt_id": existing_receipt.get("controlled_integration_receipt_id"),
                "writes_performed": 0,
            }
        return {"status": "stale" if _result_is_stale(base, existing) else "corrupt", "controlled_integration_plan_id": controlled_integration_plan_id, "warnings": [], "blockers": ["controlled_integration_existing_state_drift"]}

    eligibility = validate_certified_rule_controlled_integration_eligibility(canonical_rule_id, release_candidate_result_id, target_id, root=base)
    if str(eligibility.get("status") or "") not in {"eligible", "eligible_with_warnings"}:
        return {"status": str(eligibility.get("status") or "blocked"), "controlled_integration_plan_id": controlled_integration_plan_id, "warnings": list(eligibility.get("warnings", [])), "blockers": list(eligibility.get("blockers", []))}

    bundle = _load_bundle(base, canonical_rule_id, release_candidate_result_id, target_id)
    package = _integration_package(bundle)
    target_workspace = bundle.get("target_workspace") if isinstance(bundle.get("target_workspace"), Mapping) else {}
    adapter_manifest = target_workspace.get("adapter_manifest") if isinstance(target_workspace.get("adapter_manifest"), Mapping) else {}
    target_manifest = target_workspace.get("target_manifest") if isinstance(target_workspace.get("target_manifest"), Mapping) else {}
    package_validation = target_backend.validate_controlled_integration_package(target_id, package, root=base)
    if not package_validation.get("valid"):
        return {"status": "blocked", "controlled_integration_plan_id": controlled_integration_plan_id, "warnings": list(package_validation.get("warnings", [])), "blockers": list(package_validation.get("blockers", []))}
    preflight = target_backend.preflight_controlled_integration_transaction(target_id, package, root=base)
    current_plan_fp = _plan_fingerprint(package, preflight, adapter_manifest, target_manifest)
    if any(
        [
            str(plan.get("plan_fingerprint") or "") != str(current_plan_fp or ""),
            str(plan.get("package_fingerprint") or "") != str(package.get("package_fingerprint") or ""),
            str(plan.get("transaction_id") or "") != str(preflight.get("transaction_id") or ""),
            str(plan.get("namespace_id") or "") != str(preflight.get("namespace_id") or ""),
            str(plan.get("pre_apply_target_state_fingerprint") or "") != str(preflight.get("pre_apply_target_state_fingerprint") or ""),
            str(plan.get("adapter_fingerprint") or "") != str(adapter_manifest.get("adapter_fingerprint") or ""),
            str(plan.get("target_fingerprint") or "") != str(target_manifest.get("target_fingerprint") or ""),
        ]
    ):
        return {"status": "stale", "controlled_integration_plan_id": controlled_integration_plan_id, "warnings": [], "blockers": ["controlled_integration_plan_fingerprint_mismatch"]}
    if str(preflight.get("status") or "") != "ready":
        return {"status": "stale" if str(preflight.get("status") or "") == "already_committed" else str(preflight.get("status") or "blocked"), "controlled_integration_plan_id": controlled_integration_plan_id, "warnings": list(preflight.get("warnings", [])), "blockers": list(preflight.get("blockers", []))}

    upstream_before = _upstream_snapshot(bundle)
    apply_result = target_backend.apply_controlled_integration_transaction(
        target_id,
        package,
        confirmation="APPLY_ISOLATED_INTEGRATION_TRANSACTION",
        root=base,
    )
    tx_id = str(apply_result.get("transaction_id") or preflight.get("transaction_id") or "")
    ns_id = str(apply_result.get("namespace_id") or preflight.get("namespace_id") or "")
    if str(apply_result.get("status") or "") != "pending_verification":
        return _finalize_execution(
            base,
            plan,
            bundle,
            package,
            preflight=preflight,
            apply_status=str(apply_result.get("status") or "apply_failed"),
            pending_verification_status="missing",
            pending_state_fingerprint=None,
            commit_status="not_started",
            committed_verification_status="missing",
            committed_state_fingerprint=None,
            rollback_status="not_required",
            production_safety_status="passed",
            final_status="apply_failed",
            warnings=list(apply_result.get("warnings", [])),
            blockers=list(apply_result.get("blockers", [])),
        )

    pending_read = target_backend.read_controlled_integration_target_state(target_id, transaction_id=tx_id, root=base)
    if str(pending_read.get("verification_status") or "") != "verified_pending":
        rollback = target_backend.rollback_controlled_integration_transaction(target_id, tx_id, confirmation="ROLLBACK_ISOLATED_INTEGRATION_TRANSACTION", root=base)
        return _finalize_execution(
            base,
            plan,
            bundle,
            package,
            preflight=preflight,
            apply_status=str(apply_result.get("status") or "pending_verification"),
            pending_verification_status=str(pending_read.get("verification_status") or "missing"),
            pending_state_fingerprint=pending_read.get("state_fingerprint"),
            commit_status="not_started",
            committed_verification_status="missing",
            committed_state_fingerprint=None,
            rollback_status=_rollback_status(rollback),
            production_safety_status="passed",
            final_status="verification_failed" if _rollback_status(rollback) != "rollback_failed" else "rollback_failed",
            warnings=list(_dedupe([*list(pending_read.get("warnings", [])), *list(rollback.get("warnings", []))])),
            blockers=list(_dedupe([*list(pending_read.get("blockers", [])), *list(rollback.get("blockers", []))])),
        )

    commit_result = target_backend.commit_controlled_integration_transaction(
        target_id,
        tx_id,
        str(pending_read.get("state_fingerprint") or ""),
        confirmation="COMMIT_ISOLATED_INTEGRATION_TRANSACTION",
        root=base,
    )
    if str(commit_result.get("status") or "") != "committed":
        rollback = target_backend.rollback_controlled_integration_transaction(target_id, tx_id, confirmation="ROLLBACK_ISOLATED_INTEGRATION_TRANSACTION", root=base)
        return _finalize_execution(
            base,
            plan,
            bundle,
            package,
            preflight=preflight,
            apply_status=str(apply_result.get("status") or "pending_verification"),
            pending_verification_status="verified_pending",
            pending_state_fingerprint=pending_read.get("state_fingerprint"),
            commit_status=str(commit_result.get("status") or "commit_failed"),
            committed_verification_status="missing",
            committed_state_fingerprint=None,
            rollback_status=_rollback_status(rollback),
            production_safety_status="passed",
            final_status="commit_failed" if _rollback_status(rollback) != "rollback_failed" else "rollback_failed",
            warnings=list(_dedupe([*list(commit_result.get("warnings", [])), *list(rollback.get("warnings", []))])),
            blockers=list(_dedupe([*list(commit_result.get("blockers", [])), *list(rollback.get("blockers", []))])),
        )

    committed_read = target_backend.read_controlled_integration_target_state(target_id, namespace_id=ns_id, root=base)
    committed_ok, committed_blockers = _verify_committed_state(committed_read, package, target_id, tx_id, ns_id, adapter_manifest)
    if not committed_ok:
        rollback = target_backend.rollback_controlled_integration_transaction(target_id, tx_id, confirmation="ROLLBACK_ISOLATED_INTEGRATION_TRANSACTION", root=base)
        return _finalize_execution(
            base,
            plan,
            bundle,
            package,
            preflight=preflight,
            apply_status=str(apply_result.get("status") or "pending_verification"),
            pending_verification_status="verified_pending",
            pending_state_fingerprint=pending_read.get("state_fingerprint"),
            commit_status="committed",
            committed_verification_status=str(committed_read.get("verification_status") or "missing"),
            committed_state_fingerprint=committed_read.get("state_fingerprint"),
            rollback_status=_rollback_status(rollback),
            production_safety_status="failed",
            final_status="verification_failed" if _rollback_status(rollback) != "rollback_failed" else "rollback_failed",
            warnings=list(rollback.get("warnings", [])),
            blockers=committed_blockers + list(rollback.get("blockers", [])),
        )

    upstream_after = _upstream_snapshot(_load_bundle(base, canonical_rule_id, release_candidate_result_id, target_id))
    if upstream_before != upstream_after:
        rollback = target_backend.rollback_controlled_integration_transaction(target_id, tx_id, confirmation="ROLLBACK_ISOLATED_INTEGRATION_TRANSACTION", root=base)
        return _finalize_execution(
            base,
            plan,
            bundle,
            package,
            preflight=preflight,
            apply_status=str(apply_result.get("status") or "pending_verification"),
            pending_verification_status="verified_pending",
            pending_state_fingerprint=pending_read.get("state_fingerprint"),
            commit_status="committed",
            committed_verification_status="verified_committed",
            committed_state_fingerprint=committed_read.get("state_fingerprint"),
            rollback_status=_rollback_status(rollback),
            production_safety_status="failed",
            final_status="mutation_detected" if _rollback_status(rollback) != "rollback_failed" else "rollback_failed",
            warnings=list(rollback.get("warnings", [])),
            blockers=["upstream_mutation_detected", *list(rollback.get("blockers", []))],
        )

    final_status = "completed_with_warnings" if eligibility.get("warnings") else "completed"
    return _finalize_execution(
        base,
        plan,
        bundle,
        package,
        preflight=preflight,
        apply_status=str(apply_result.get("status") or "pending_verification"),
        pending_verification_status="verified_pending",
        pending_state_fingerprint=pending_read.get("state_fingerprint"),
        commit_status="committed",
        committed_verification_status="verified_committed",
        committed_state_fingerprint=committed_read.get("state_fingerprint"),
        rollback_status="not_required",
        production_safety_status="passed",
        final_status=final_status,
        warnings=list(eligibility.get("warnings", [])),
        blockers=[],
    )


def load_certified_rule_controlled_integration_result(
    controlled_integration_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    result = _find_result_by_id(base, controlled_integration_result_id)
    if not isinstance(result, Mapping):
        return {"status": "not_found", "controlled_integration_result_id": controlled_integration_result_id, "controlled_integration_result": None, "warnings": []}
    payload = dict(result)
    payload["stale"] = _result_is_stale(base, payload)
    return {"status": "loaded", "controlled_integration_result_id": controlled_integration_result_id, "controlled_integration_result": payload, "warnings": []}


def get_certified_rule_controlled_integration_health(
    controlled_integration_plan_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    plans = _load_all(base / PLAN_DIR)
    results = _load_all(base / RESULT_DIR)
    receipts = _load_all(base / RECEIPT_DIR)
    if controlled_integration_plan_id:
        plans = [item for item in plans if str(item.get("controlled_integration_plan_id") or "") == controlled_integration_plan_id]
        results = [item for item in results if str(item.get("controlled_integration_plan_id") or "") == controlled_integration_plan_id]
        receipts = [item for item in receipts if str(item.get("controlled_integration_plan_id") or "") == controlled_integration_plan_id]
    if not plans and not results and not receipts:
        return {"status": "empty", "controlled_integration_plan_count": 0, "controlled_integration_result_count": 0, "controlled_integration_receipt_count": 0, "recommended_action": "Build one controlled integration plan."}
    warnings: list[str] = []
    blockers: list[str] = []
    stale_count = 0
    for result in results:
        if _result_is_stale(base, result):
            stale_count += 1
        receipt = _find_receipt_for_result(base, str(result.get("controlled_integration_result_id") or ""))
        if not isinstance(receipt, Mapping):
            warnings.append("controlled_integration_receipt_missing")
        elif str(receipt.get("result_fingerprint") or "") != str(result.get("result_fingerprint") or ""):
            blockers.append("controlled_integration_receipt_fingerprint_mismatch")
        if str(result.get("final_status") or "") in {"completed", "completed_with_warnings"}:
            readback = target_backend.read_controlled_integration_target_state(str(result.get("integration_target_id") or ""), namespace_id=str(result.get("namespace_id") or ""), root=base)
            if str(readback.get("verification_status") or "") != "verified_committed":
                blockers.append("controlled_integration_committed_state_unverified")
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
        "controlled_integration_plan_count": len(plans),
        "controlled_integration_result_count": len(results),
        "controlled_integration_receipt_count": len(receipts),
        "stale_count": stale_count,
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
        "recommended_action": _recommended_action(status),
    }


def format_certified_rule_controlled_integration_report(
    controlled_integration_result_id: str | None = None,
    controlled_integration_receipt_id: str | None = None,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    base = _ensure_dirs(root)
    result = _find_result_by_id(base, str(controlled_integration_result_id or ""))
    receipt = _find_receipt_by_id(base, controlled_integration_receipt_id)
    if not isinstance(result, Mapping):
        return "Controlled integration result not found."
    lines = [
        "Certified Rule Controlled Integration",
        f"Status: {result.get('final_status', 'unknown')}",
        f"Canonical Rule ID: {result.get('canonical_rule_id', 'unknown')}",
        f"Document ID: {result.get('document_id', 'unknown')}",
        f"Source Revision: {result.get('source_revision', 'unknown')}",
        f"Target ID: {result.get('integration_target_id', 'unknown')}",
        f"Environment Class: {result.get('environment_class', 'unknown')}",
        f"Transaction ID: {result.get('transaction_id', 'unknown')}",
        f"Namespace ID: {result.get('namespace_id', 'unknown')}",
        f"Pending Verification: {result.get('pending_verification_status', 'unknown')}",
        f"Committed Verification: {result.get('committed_verification_status', 'unknown')}",
        f"Rollback Status: {result.get('rollback_status', 'unknown')}",
        f"Production Safety: {result.get('production_safety_status', 'unknown')}",
        "Integration occurred only in isolated non-production storage.",
        "The staged rule was not activated.",
        "Production scoring was not written.",
        "Live Fast Lane was not executed.",
        "Production deployment did not occur.",
        "Successful Phase 9T execution does not authorize production deployment.",
    ]
    if isinstance(receipt, Mapping):
        lines.append(f"Receipt ID: {receipt.get('controlled_integration_receipt_id', 'unknown')}")
    warnings = list(result.get("warnings", []))
    blockers = list(result.get("blockers", []))
    if warnings:
        lines.append("Warnings: " + ", ".join(str(item) for item in warnings))
    if blockers:
        lines.append("Blockers: " + ", ".join(str(item) for item in blockers))
    return "\n".join(lines)


def get_certified_rule_controlled_integration_summary(
    controlled_integration_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    loaded = load_certified_rule_controlled_integration_result(controlled_integration_result_id, root=root)
    result = loaded.get("controlled_integration_result") if isinstance(loaded.get("controlled_integration_result"), Mapping) else {}
    return {
        "status": result.get("final_status", loaded.get("status", "unknown")),
        "canonical_rule_id": result.get("canonical_rule_id"),
        "document_id": result.get("document_id"),
        "source_revision": result.get("source_revision"),
        "integration_target_id": result.get("integration_target_id"),
        "environment_class": result.get("environment_class"),
        "adapter_version": result.get("adapter_version"),
        "namespace_id": result.get("namespace_id"),
        "transaction_id": result.get("transaction_id"),
        "pending_verification_status": result.get("pending_verification_status"),
        "committed_verification_status": result.get("committed_verification_status"),
        "rollback_status": result.get("rollback_status"),
        "production_safety_status": result.get("production_safety_status"),
        "stale": bool(result.get("stale")),
        "warnings": list(result.get("warnings", [])),
        "blockers": list(result.get("blockers", [])),
        "recommended_action": _recommended_action(str(result.get("final_status") or loaded.get("status") or "unknown")),
    }


def _load_bundle(base: Path, canonical_rule_id: str, release_candidate_result_id: str, integration_target_id: str) -> dict[str, Any]:
    rule_loaded = load_canonical_rule(canonical_rule_id, require_active=True, root=base)
    rule = rule_loaded.get("rule") if isinstance(rule_loaded.get("rule"), Mapping) else None
    certification = _load_certification_receipt_for_rule(base, canonical_rule_id)
    manifest = load_document_manifest(str((rule or {}).get("document_id") or ""), root=base).get("manifest") if isinstance(rule, Mapping) else None
    release_loaded = release_candidate_backend.load_certified_rule_release_candidate_result(release_candidate_result_id, root=base)
    release_result = release_loaded.get("release_candidate_result")
    release_receipt = release_candidate_backend._find_receipt_for_result(base, release_candidate_result_id) if isinstance(release_result, Mapping) else None
    authorization_result = authorization_receipt = scoring_result = fast_lane_result = None
    if isinstance(release_result, Mapping):
        auth_loaded = authorization_backend.load_certified_rule_integration_authorization_result(str(release_result.get("integration_authorization_result_id") or ""), root=base)
        authorization_result = auth_loaded.get("integration_authorization_result")
        authorization_receipt = authorization_backend._find_receipt_for_result(base, str(release_result.get("integration_authorization_result_id") or "")) if isinstance(authorization_result, Mapping) else None
        if isinstance(authorization_result, Mapping):
            scoring_result = authorization_backend.scoring_backend.load_certified_rule_scoring_preview_result(str(authorization_result.get("scoring_preview_result_id") or ""), root=base).get("scoring_preview_result")
            fast_lane_result = authorization_backend.fast_lane_backend.load_certified_rule_fast_lane_preview_result(str(authorization_result.get("fast_lane_preview_result_id") or ""), root=base).get("fast_lane_preview_result")
    target_workspace = target_backend.get_isolated_controlled_integration_target_workspace(integration_target_id, root=base)
    target_validation = target_backend.validate_controlled_integration_target(integration_target_id, root=base)
    return {
        "rule_loaded": rule_loaded,
        "rule": rule,
        "certification": certification,
        "manifest": manifest,
        "release_candidate_result": release_result,
        "release_candidate_receipt": release_receipt,
        "authorization_result": authorization_result,
        "authorization_receipt": authorization_receipt,
        "scoring_result": scoring_result,
        "fast_lane_result": fast_lane_result,
        "target_workspace": target_workspace,
        "target_validation": target_validation,
    }


def _integration_package(bundle: Mapping[str, Any]) -> dict[str, Any]:
    rule = dict(bundle.get("rule") or {})
    certification = dict(bundle.get("certification") or {})
    release_result = dict(bundle.get("release_candidate_result") or {})
    authorization_result = dict(bundle.get("authorization_result") or {})
    scoring_result = dict(bundle.get("scoring_result") or {})
    fast_lane_result = dict(bundle.get("fast_lane_result") or {})
    target_workspace = dict(bundle.get("target_workspace") or {})
    target_manifest = dict(target_workspace.get("target_manifest") or {})
    seed = {
        "canonical_rule_id": rule.get("rule_id"),
        "canonical_rule_fingerprint": rule.get("rule_fingerprint"),
        "document_id": rule.get("document_id"),
        "source_revision": rule.get("source_revision"),
        "certification_fingerprint": _certification_fingerprint(certification),
        "release_candidate_result_fingerprint": release_result.get("result_fingerprint"),
        "authorization_result_fingerprint": authorization_result.get("result_fingerprint"),
        "scoring_result_fingerprint": scoring_result.get("result_fingerprint"),
        "scoring_config_fingerprint": scoring_result.get("scoring_config_fingerprint"),
        "fast_lane_result_fingerprint": fast_lane_result.get("result_fingerprint"),
        "fast_lane_capability_fingerprint": fast_lane_result.get("fast_lane_capability_fingerprint"),
        "target_id": target_manifest.get("target_id"),
        "target_fingerprint": target_manifest.get("target_fingerprint"),
        "adapter_version": (target_workspace.get("adapter_manifest") or {}).get("adapter_version"),
        "package_schema_version": target_backend.PACKAGE_SCHEMA_VERSION,
    }
    package_id = f"controlled_integration_package_{_hash_payload(seed)[7:23]}"
    package = {
        "schema_version": target_backend.PACKAGE_SCHEMA_VERSION,
        "package_id": package_id,
        "target_id": target_manifest.get("target_id"),
        "canonical_rule_id": rule.get("rule_id"),
        "canonical_rule_schema_version": target_backend.CANONICAL_RULE_SCHEMA_VERSION,
        "canonical_rule_fingerprint": rule.get("rule_fingerprint"),
        "document_id": rule.get("document_id"),
        "source_revision": rule.get("source_revision"),
        "certification_id": certification.get("certification_receipt_id"),
        "certification_fingerprint": _certification_fingerprint(certification),
        "release_candidate_result_id": release_result.get("release_candidate_result_id"),
        "release_candidate_fingerprint": release_result.get("result_fingerprint"),
        "authorization_result_id": _package_ref_id("authorization", authorization_result.get("integration_authorization_result_id")),
        "authorization_fingerprint": authorization_result.get("result_fingerprint"),
        "scoring_preview_result_id": _package_ref_id("scoring", scoring_result.get("scoring_preview_result_id")),
        "scoring_config_id": scoring_result.get("scoring_config_id"),
        "scoring_config_fingerprint": scoring_result.get("scoring_config_fingerprint"),
        "fast_lane_preview_result_id": _package_ref_id("fast_lane", fast_lane_result.get("fast_lane_preview_result_id")),
        "fast_lane_contract_id": fast_lane_result.get("fast_lane_contract_id"),
        "fast_lane_contract_version": str(fast_lane_result.get("fast_lane_contract_version") or ""),
        "fast_lane_capability_fingerprint": fast_lane_result.get("fast_lane_capability_fingerprint"),
    }
    package["package_fingerprint"] = target_backend._integration_package_fingerprint(package)
    return package


def _finalize_execution(
    base: Path,
    plan: Mapping[str, Any],
    bundle: Mapping[str, Any],
    package: Mapping[str, Any],
    *,
    preflight: Mapping[str, Any],
    apply_status: str,
    pending_verification_status: str,
    pending_state_fingerprint: str | None,
    commit_status: str,
    committed_verification_status: str,
    committed_state_fingerprint: str | None,
    rollback_status: str,
    production_safety_status: str,
    final_status: str,
    warnings: list[str],
    blockers: list[str],
) -> dict[str, Any]:
    release_result = dict(bundle.get("release_candidate_result") or {})
    authorization_result = dict(bundle.get("authorization_result") or {})
    scoring_result = dict(bundle.get("scoring_result") or {})
    fast_lane_result = dict(bundle.get("fast_lane_result") or {})
    target_manifest = dict((bundle.get("target_workspace") or {}).get("target_manifest") or {})
    result_id = _result_id(str(plan.get("controlled_integration_plan_id") or ""))
    result = {
        "schema_version": RESULT_SCHEMA,
        "execution_schema_version": EXECUTION_SCHEMA_VERSION,
        "controlled_integration_result_id": result_id,
        "controlled_integration_plan_id": plan.get("controlled_integration_plan_id"),
        "canonical_rule_id": plan.get("canonical_rule_id"),
        "document_id": plan.get("document_id"),
        "source_revision": plan.get("source_revision"),
        "certification_id": plan.get("certification_id"),
        "certification_fingerprint": plan.get("certification_fingerprint"),
        "release_candidate_result_id": release_result.get("release_candidate_result_id"),
        "release_candidate_result_fingerprint": release_result.get("result_fingerprint"),
        "integration_authorization_result_id": authorization_result.get("integration_authorization_result_id"),
        "integration_authorization_result_fingerprint": authorization_result.get("result_fingerprint"),
        "scoring_preview_result_id": scoring_result.get("scoring_preview_result_id"),
        "scoring_preview_result_fingerprint": scoring_result.get("result_fingerprint"),
        "scoring_config_id": scoring_result.get("scoring_config_id"),
        "scoring_config_fingerprint": scoring_result.get("scoring_config_fingerprint"),
        "fast_lane_preview_result_id": fast_lane_result.get("fast_lane_preview_result_id"),
        "fast_lane_preview_result_fingerprint": fast_lane_result.get("result_fingerprint"),
        "fast_lane_contract_id": fast_lane_result.get("fast_lane_contract_id"),
        "fast_lane_contract_version": fast_lane_result.get("fast_lane_contract_version"),
        "fast_lane_capability_fingerprint": fast_lane_result.get("fast_lane_capability_fingerprint"),
        "integration_target_id": plan.get("integration_target_id"),
        "environment_class": target_manifest.get("environment_class"),
        "adapter_id": plan.get("adapter_id"),
        "adapter_version": plan.get("adapter_version"),
        "adapter_fingerprint": plan.get("adapter_fingerprint"),
        "target_fingerprint": plan.get("target_fingerprint"),
        "package_id": package.get("package_id"),
        "package_fingerprint": package.get("package_fingerprint"),
        "transaction_id": preflight.get("transaction_id"),
        "namespace_id": preflight.get("namespace_id"),
        "preflight_status": preflight.get("status"),
        "pre_apply_target_state_fingerprint": preflight.get("pre_apply_target_state_fingerprint"),
        "apply_status": apply_status,
        "pending_verification_status": pending_verification_status,
        "pending_state_fingerprint": pending_state_fingerprint,
        "commit_status": commit_status,
        "committed_verification_status": committed_verification_status,
        "committed_state_fingerprint": committed_state_fingerprint,
        "rollback_status": rollback_status,
        "production_safety_status": production_safety_status,
        "final_status": final_status,
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
    }
    result["result_fingerprint"] = _result_fingerprint(result)
    receipt_id = _receipt_id(result_id)
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "controlled_integration_receipt_id": receipt_id,
        "controlled_integration_result_id": result_id,
        "controlled_integration_plan_id": plan.get("controlled_integration_plan_id"),
        "canonical_rule_id": plan.get("canonical_rule_id"),
        "document_id": plan.get("document_id"),
        "source_revision": plan.get("source_revision"),
        "release_candidate_result_id": result.get("release_candidate_result_id"),
        "integration_authorization_result_id": result.get("integration_authorization_result_id"),
        "scoring_preview_result_id": result.get("scoring_preview_result_id"),
        "fast_lane_preview_result_id": result.get("fast_lane_preview_result_id"),
        "integration_target_id": result.get("integration_target_id"),
        "adapter_id": result.get("adapter_id"),
        "adapter_version": result.get("adapter_version"),
        "package_fingerprint": result.get("package_fingerprint"),
        "transaction_id": result.get("transaction_id"),
        "namespace_id": result.get("namespace_id"),
        "committed_state_fingerprint": result.get("committed_state_fingerprint"),
        "verification_status": result.get("committed_verification_status"),
        "rollback_status": result.get("rollback_status"),
        "final_status": result.get("final_status"),
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
        return {"status": "corrupt", "controlled_integration_plan_id": plan.get("controlled_integration_plan_id"), "warnings": [], "blockers": ["controlled_integration_result_write_failure"]}
    return {
        "status": final_status,
        "controlled_integration_plan_id": plan.get("controlled_integration_plan_id"),
        "controlled_integration_result_id": result_id,
        "controlled_integration_receipt_id": receipt_id,
        "writes_performed": 2,
    }


def _verify_committed_state(
    readback: Mapping[str, Any],
    package: Mapping[str, Any],
    target_id: str,
    transaction_id: str,
    namespace_id: str,
    adapter_manifest: Mapping[str, Any],
) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    if str(readback.get("verification_status") or "") != "verified_committed":
        blockers.append("committed_state_not_verified")
    _match(blockers, readback.get("target_id"), target_id, "committed_target_id_mismatch")
    _match(blockers, readback.get("environment_class"), "isolated_non_production", "committed_environment_mismatch")
    _match(blockers, readback.get("adapter_id"), adapter_manifest.get("adapter_id"), "committed_adapter_id_mismatch")
    _match(blockers, readback.get("adapter_version"), adapter_manifest.get("adapter_version"), "committed_adapter_version_mismatch")
    _match(blockers, readback.get("transaction_id"), transaction_id, "committed_transaction_id_mismatch")
    _match(blockers, readback.get("namespace_id"), namespace_id, "committed_namespace_id_mismatch")
    _match(blockers, readback.get("canonical_rule_id"), package.get("canonical_rule_id"), "committed_canonical_rule_id_mismatch")
    _match(blockers, readback.get("canonical_rule_fingerprint"), package.get("canonical_rule_fingerprint"), "committed_rule_fingerprint_mismatch")
    _match(blockers, readback.get("document_id"), package.get("document_id"), "committed_document_id_mismatch")
    _match(blockers, readback.get("source_revision"), package.get("source_revision"), "committed_source_revision_mismatch")
    _match(blockers, readback.get("certification_fingerprint"), package.get("certification_fingerprint"), "committed_certification_fingerprint_mismatch")
    _match(blockers, readback.get("release_candidate_fingerprint"), package.get("release_candidate_fingerprint"), "committed_release_candidate_fingerprint_mismatch")
    _match(blockers, readback.get("authorization_fingerprint"), package.get("authorization_fingerprint"), "committed_authorization_fingerprint_mismatch")
    _match(blockers, readback.get("scoring_config_fingerprint"), package.get("scoring_config_fingerprint"), "committed_scoring_config_fingerprint_mismatch")
    _match(blockers, readback.get("fast_lane_capability_fingerprint"), package.get("fast_lane_capability_fingerprint"), "committed_fast_lane_capability_fingerprint_mismatch")
    _match(blockers, readback.get("package_fingerprint"), package.get("package_fingerprint"), "committed_package_fingerprint_mismatch")
    _match(blockers, readback.get("transaction_state"), "committed", "committed_transaction_state_mismatch")
    return (not blockers, blockers)


def _upstream_snapshot(bundle: Mapping[str, Any]) -> dict[str, Any]:
    rule = dict(bundle.get("rule") or {})
    certification = dict(bundle.get("certification") or {})
    manifest = dict(bundle.get("manifest") or {})
    release_result = dict(bundle.get("release_candidate_result") or {})
    authorization_result = dict(bundle.get("authorization_result") or {})
    scoring_result = dict(bundle.get("scoring_result") or {})
    fast_lane_result = dict(bundle.get("fast_lane_result") or {})
    return {
        "rule_fingerprint": rule.get("rule_fingerprint"),
        "rule_status": rule.get("status"),
        "certification_fingerprint": _certification_fingerprint(certification),
        "certification_status": certification.get("certification_status"),
        "document_id": rule.get("document_id"),
        "source_revision": manifest.get("source_revision"),
        "release_candidate_result_fingerprint": release_result.get("result_fingerprint"),
        "release_candidate_status": release_result.get("qualification_status"),
        "authorization_result_fingerprint": authorization_result.get("result_fingerprint"),
        "authorization_status": authorization_result.get("status"),
        "scoring_result_fingerprint": scoring_result.get("result_fingerprint"),
        "fast_lane_result_fingerprint": fast_lane_result.get("result_fingerprint"),
    }


def _ensure_dirs(root: Path | str) -> Path:
    base = _ensure_analysis_dirs(root)
    for folder in (PLAN_DIR, RESULT_DIR, RECEIPT_DIR, "indexes"):
        (base / folder).mkdir(parents=True, exist_ok=True)
    return base


def _rollback_pending(rule: Mapping[str, Any]) -> bool:
    return bool(rule.get("rollback_pending")) or bool(rule.get("rollback_requested"))


def _package_ref_id(prefix: str, value: Any) -> str:
    text = str(value or "").strip()
    if text and _safe_id(text) == text:
        return text
    return f"{prefix}_{_hash_payload({'prefix': prefix, 'value': text})[7:23]}"


def _plan_id(package: Mapping[str, Any], preflight: Mapping[str, Any]) -> str:
    return f"controlled_integration_plan_{_hash_payload({'package_fingerprint': package.get('package_fingerprint'), 'target_state': preflight.get('pre_apply_target_state_fingerprint'), 'transaction_id': preflight.get('transaction_id')})[7:23]}"


def _result_id(plan_id: str) -> str:
    return f"controlled_integration_result_{_hash_payload({'plan_id': plan_id})[7:23]}"


def _receipt_id(result_id: str) -> str:
    return f"controlled_integration_receipt_{_hash_payload({'result_id': result_id})[7:23]}"


def _plan_fingerprint(
    package: Mapping[str, Any],
    preflight: Mapping[str, Any],
    adapter_manifest: Mapping[str, Any],
    target_manifest: Mapping[str, Any],
) -> str:
    return _hash_payload(
        {
            "schema_version": EXECUTION_SCHEMA_VERSION,
            "package_fingerprint": package.get("package_fingerprint"),
            "adapter_id": adapter_manifest.get("adapter_id"),
            "adapter_version": adapter_manifest.get("adapter_version"),
            "adapter_fingerprint": adapter_manifest.get("adapter_fingerprint"),
            "target_id": target_manifest.get("target_id"),
            "target_fingerprint": target_manifest.get("target_fingerprint"),
            "environment_class": target_manifest.get("environment_class"),
            "transaction_id": preflight.get("transaction_id"),
            "namespace_id": preflight.get("namespace_id"),
            "pre_apply_target_state_fingerprint": preflight.get("pre_apply_target_state_fingerprint"),
        }
    )


def _result_fingerprint(result: Mapping[str, Any]) -> str:
    return _hash_payload(
        {
            "schema_version": EXECUTION_SCHEMA_VERSION,
            "controlled_integration_plan_id": result.get("controlled_integration_plan_id"),
            "package_fingerprint": result.get("package_fingerprint"),
            "transaction_id": result.get("transaction_id"),
            "namespace_id": result.get("namespace_id"),
            "preflight_status": result.get("preflight_status"),
            "apply_status": result.get("apply_status"),
            "pending_verification_status": result.get("pending_verification_status"),
            "pending_state_fingerprint": result.get("pending_state_fingerprint"),
            "commit_status": result.get("commit_status"),
            "committed_verification_status": result.get("committed_verification_status"),
            "committed_state_fingerprint": result.get("committed_state_fingerprint"),
            "rollback_status": result.get("rollback_status"),
            "production_safety_status": result.get("production_safety_status"),
            "final_status": result.get("final_status"),
        }
    )


def _eligibility_status(blockers: list[str], warnings: list[str]) -> str:
    if any("mismatch" in item and "receipt" in item for item in blockers):
        return "corrupt"
    if any("stale" in item or item in {"source_revision_not_current", "rule_has_pending_rollback", "rule_pending_supersession"} for item in blockers):
        return "stale"
    if blockers:
        return "blocked"
    return "eligible_with_warnings" if warnings else "eligible"


def _recommended_action(status: str) -> str:
    if status in {"eligible", "eligible_with_warnings"}:
        return "Build or execute the controlled integration plan."
    if status == "stale":
        return "Refresh the controlled integration plan against current evidence and target state."
    if status == "corrupt":
        return "Repair inconsistent controlled integration records before execution."
    if status in {"completed", "completed_with_warnings"}:
        return "Controlled integration completed in isolated staging only."
    if status == "healthy":
        return "Controlled integration records are internally consistent."
    if status == "warning":
        return "Review controlled integration warnings before relying on staged state."
    return "Resolve blockers before controlled integration execution."


def _plan_summary(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "canonical_rule_id": plan.get("canonical_rule_id"),
        "document_id": plan.get("document_id"),
        "source_revision": plan.get("source_revision"),
        "integration_target_id": plan.get("integration_target_id"),
        "environment_class": plan.get("environment_class"),
        "adapter_id": plan.get("adapter_id"),
        "adapter_version": plan.get("adapter_version"),
        "namespace_id": plan.get("namespace_id"),
        "transaction_id": plan.get("transaction_id"),
        "package_fingerprint": plan.get("package_fingerprint"),
        "target_fingerprint": plan.get("target_fingerprint"),
        "recommended_action": "Execute controlled integration in the isolated non-production target.",
    }


def _result_is_stale(base: Path, result: Mapping[str, Any]) -> bool:
    bundle = _load_bundle(base, str(result.get("canonical_rule_id") or ""), str(result.get("release_candidate_result_id") or ""), str(result.get("integration_target_id") or ""))
    if not bundle.get("rule") or not bundle.get("release_candidate_result") or not bundle.get("authorization_result") or not bundle.get("scoring_result") or not bundle.get("fast_lane_result") or not (bundle.get("target_workspace") or {}).get("target_manifest"):
        return True
    current_package = _integration_package(bundle)
    target_manifest = (bundle.get("target_workspace") or {}).get("target_manifest") or {}
    adapter_manifest = (bundle.get("target_workspace") or {}).get("adapter_manifest") or {}
    return any(
        [
            str(result.get("document_id") or "") != str((bundle.get("rule") or {}).get("document_id") or ""),
            str(result.get("source_revision") or "") != str((bundle.get("rule") or {}).get("source_revision") or ""),
            str(result.get("certification_fingerprint") or "") != str(_certification_fingerprint(bundle.get("certification") or {}) or ""),
            str(result.get("release_candidate_result_fingerprint") or "") != str((bundle.get("release_candidate_result") or {}).get("result_fingerprint") or ""),
            str(result.get("integration_authorization_result_fingerprint") or "") != str((bundle.get("authorization_result") or {}).get("result_fingerprint") or ""),
            str(result.get("scoring_preview_result_fingerprint") or "") != str((bundle.get("scoring_result") or {}).get("result_fingerprint") or ""),
            str(result.get("scoring_config_fingerprint") or "") != str((bundle.get("scoring_result") or {}).get("scoring_config_fingerprint") or ""),
            str(result.get("fast_lane_preview_result_fingerprint") or "") != str((bundle.get("fast_lane_result") or {}).get("result_fingerprint") or ""),
            str(result.get("fast_lane_capability_fingerprint") or "") != str((bundle.get("fast_lane_result") or {}).get("fast_lane_capability_fingerprint") or ""),
            str(result.get("target_fingerprint") or "") != str(target_manifest.get("target_fingerprint") or ""),
            str(result.get("adapter_version") or "") != str(adapter_manifest.get("adapter_version") or ""),
            str(result.get("package_fingerprint") or "") != str(current_package.get("package_fingerprint") or ""),
            str(target_manifest.get("environment_class") or "") != "isolated_non_production",
        ]
    )


def _safe_identity(payload: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    return {key: payload.get(key) for key in payload if key.endswith("_id") or key.endswith("_fingerprint") or key in {"status", "qualification_status", "preview_status", "decision", "document_id", "source_revision", "canonical_rule_id", "scoring_config_id", "fast_lane_contract_id", "fast_lane_contract_version"}}


def _match(blockers: list[str], left: Any, right: Any, code: str) -> None:
    if str(left or "") != str(right or ""):
        blockers.append(code)


def _rollback_status(payload: Mapping[str, Any]) -> str:
    status = str(payload.get("status") or "unknown")
    if status == "completed":
        return "rollback_completed"
    if status == "rollback_failed":
        return "rollback_failed"
    return "not_required" if status == "already_rolled_back" else status


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


def _find_plan(base: Path, canonical_rule_id: str, release_candidate_result_id: str, integration_target_id: str) -> dict[str, Any] | None:
    for item in _load_all(base / PLAN_DIR):
        if (
            str(item.get("canonical_rule_id") or "") == canonical_rule_id
            and str(item.get("release_candidate_result_id") or "") == release_candidate_result_id
            and str(item.get("integration_target_id") or "") == integration_target_id
        ):
            return item
    return None


def _find_result(base: Path, plan_id: str) -> dict[str, Any] | None:
    for item in _load_all(base / RESULT_DIR):
        if str(item.get("controlled_integration_plan_id") or "") == plan_id:
            return item
    return None


def _find_result_by_id(base: Path, result_id: str) -> dict[str, Any] | None:
    payload = _read_json(_result_path(base, result_id))
    return dict(payload) if isinstance(payload, Mapping) else None


def _find_receipt_for_result(base: Path, result_id: str) -> dict[str, Any] | None:
    for item in _load_all(base / RECEIPT_DIR):
        if str(item.get("controlled_integration_result_id") or "") == result_id:
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
            "controlled_integration_plan_id": item.get("controlled_integration_plan_id"),
            "canonical_rule_id": item.get("canonical_rule_id"),
            "release_candidate_result_id": item.get("release_candidate_result_id"),
            "integration_target_id": item.get("integration_target_id"),
            "plan_fingerprint": item.get("plan_fingerprint"),
        }
        for item in _load_all(base / PLAN_DIR)
    ]
    _atomic_write_json(base / "indexes" / PLAN_INDEX, {"schema_version": "certified_rule_controlled_integration_plan_index_v1", "items": items, "updated_at_utc": _now()})


def _update_result_index(base: Path) -> None:
    items = [
        {
            "controlled_integration_result_id": item.get("controlled_integration_result_id"),
            "controlled_integration_plan_id": item.get("controlled_integration_plan_id"),
            "canonical_rule_id": item.get("canonical_rule_id"),
            "integration_target_id": item.get("integration_target_id"),
            "final_status": item.get("final_status"),
        }
        for item in _load_all(base / RESULT_DIR)
    ]
    _atomic_write_json(base / "indexes" / RESULT_INDEX, {"schema_version": "certified_rule_controlled_integration_result_index_v1", "items": items, "updated_at_utc": _now()})


def _update_receipt_index(base: Path) -> None:
    items = [
        {
            "controlled_integration_receipt_id": item.get("controlled_integration_receipt_id"),
            "controlled_integration_result_id": item.get("controlled_integration_result_id"),
            "canonical_rule_id": item.get("canonical_rule_id"),
            "final_status": item.get("final_status"),
        }
        for item in _load_all(base / RECEIPT_DIR)
    ]
    _atomic_write_json(base / "indexes" / RECEIPT_INDEX, {"schema_version": "certified_rule_controlled_integration_receipt_index_v1", "items": items, "updated_at_utc": _now()})


def _certification_fingerprint(certification: Mapping[str, Any] | None) -> str | None:
    return authorization_backend._certification_fingerprint(certification)


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in items if str(item)))
