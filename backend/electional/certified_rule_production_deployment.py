"""Authorized production deployment orchestration over production authorization and deployment adapter foundations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from . import certified_rule_production_authorization as authorization_backend
from . import production_deployment_adapter as adapter_backend
from .canonical_rule_runtime import _atomic_write_json, _hash_payload, _now, _read_json, _restore_json, _safe_id, load_canonical_rule
from .certified_rule_replay_adapter import _rule_has_unresolved_critical_remediation, _rule_pending_supersession
from .rule_effectiveness_analysis import _ensure_analysis_dirs
from .source_documents import SOURCE_DOCUMENT_ROOT

PLAN_DIR = "certified_rule_production_deployment_plans"
RESULT_DIR = "certified_rule_production_deployment_results"
RECEIPT_DIR = "certified_rule_production_deployment_receipts"
PLAN_INDEX = "certified_rule_production_deployment_plan_index.json"
RESULT_INDEX = "certified_rule_production_deployment_result_index.json"
RECEIPT_INDEX = "certified_rule_production_deployment_receipt_index.json"

PLAN_SCHEMA = "certified_rule_production_deployment_plan_v1"
RESULT_SCHEMA = "certified_rule_production_deployment_result_v1"
RECEIPT_SCHEMA = "certified_rule_production_deployment_receipt_v1"
DEPLOYMENT_SCHEMA_VERSION = "certified_rule_production_deployment_v1"
REQUIRED_CONFIRMATION = "EXECUTE_AUTHORIZED_PRODUCTION_DEPLOYMENT"
ALLOWED_DECISIONLESS_STATUSES = {"planned", "already_planned"}
PUBLIC_FUNCTIONS = [
    "build_certified_rule_production_deployment_workspace",
    "validate_certified_rule_production_deployment_eligibility",
    "build_certified_rule_production_deployment_plan",
    "execute_certified_rule_production_deployment",
    "load_certified_rule_production_deployment_result",
    "get_certified_rule_production_deployment_health",
    "format_certified_rule_production_deployment_report",
    "get_certified_rule_production_deployment_summary",
]


def build_certified_rule_production_deployment_workspace(
    canonical_rule_id: str,
    production_authorization_result_id: str,
    production_target_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    eligibility = validate_certified_rule_production_deployment_eligibility(
        canonical_rule_id, production_authorization_result_id, production_target_id, root=base
    )
    plan = _find_plan(base, canonical_rule_id, production_authorization_result_id, production_target_id)
    result = _find_result(base, str((plan or {}).get("production_deployment_plan_id") or ""))
    receipt = _find_receipt_for_result(base, str((result or {}).get("production_deployment_result_id") or ""))
    return {
        "status": "ready_for_planning" if not eligibility.get("blockers") else str(eligibility.get("status") or "blocked"),
        "canonical_rule_id": canonical_rule_id,
        "document_id": eligibility.get("document_id"),
        "source_revision": eligibility.get("source_revision"),
        "certification_status": eligibility.get("certification_status", "unknown"),
        "production_authorization_status": eligibility.get("production_authorization_status", "unknown"),
        "phase_9t_verification_status": eligibility.get("phase_9t_verification_status", "unknown"),
        "production_target_status": eligibility.get("production_target_status", "unknown"),
        "adapter_version": eligibility.get("adapter_version", "unknown"),
        "transaction_id": eligibility.get("transaction_id"),
        "deployed_rule_id": eligibility.get("deployed_rule_id"),
        "production_deployment_plan_id": (plan or {}).get("production_deployment_plan_id"),
        "production_deployment_result_id": (result or {}).get("production_deployment_result_id"),
        "production_deployment_receipt_id": (receipt or {}).get("production_deployment_receipt_id"),
        "warnings": list(eligibility.get("warnings", [])),
        "blockers": list(eligibility.get("blockers", [])),
        "recommended_action": "Build the authorized production deployment plan." if not eligibility.get("blockers") else eligibility.get("recommended_action", "Resolve blockers before production deployment."),
    }


def validate_certified_rule_production_deployment_eligibility(
    canonical_rule_id: str,
    production_authorization_result_id: str,
    production_target_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    blockers: list[str] = []
    warnings: list[str] = []
    bundle = _load_bundle(base, canonical_rule_id, production_authorization_result_id, production_target_id)

    rule_loaded = bundle.get("rule_loaded") if isinstance(bundle.get("rule_loaded"), Mapping) else {}
    rule = bundle.get("rule") if isinstance(bundle.get("rule"), Mapping) else {}
    certification = bundle.get("certification") if isinstance(bundle.get("certification"), Mapping) else {}
    authorization_result = bundle.get("production_authorization_result") if isinstance(bundle.get("production_authorization_result"), Mapping) else {}
    authorization_plan = bundle.get("production_authorization_plan") if isinstance(bundle.get("production_authorization_plan"), Mapping) else {}
    authorization_receipt = bundle.get("production_authorization_receipt") if isinstance(bundle.get("production_authorization_receipt"), Mapping) else {}
    committed_state = bundle.get("committed_state") if isinstance(bundle.get("committed_state"), Mapping) else {}
    descriptor = bundle.get("production_target_descriptor") if isinstance(bundle.get("production_target_descriptor"), Mapping) else {}
    target_workspace = bundle.get("target_workspace") if isinstance(bundle.get("target_workspace"), Mapping) else {}
    adapter_manifest = bundle.get("adapter_manifest") if isinstance(bundle.get("adapter_manifest"), Mapping) else {}

    if str(rule_loaded.get("status") or "") != "loaded" or not rule:
        blockers.extend(list(rule_loaded.get("blockers", []) or ["canonical_rule_not_active"]))
    if not certification or str(certification.get("certification_status") or "") != "completed":
        blockers.append("rule_certification_missing_or_stale")
    if rule and _rollback_pending(rule):
        blockers.append("rule_has_pending_rollback")
    if _rule_pending_supersession(base, canonical_rule_id):
        blockers.append("rule_pending_supersession")
    if _rule_has_unresolved_critical_remediation(base, rule):
        blockers.append("rule_has_unresolved_critical_remediation")

    if not authorization_result:
        blockers.append("production_authorization_result_missing")
    else:
        if str(authorization_result.get("status") or "") != "authorized":
            blockers.append("production_authorization_not_authorized")
        if str(authorization_result.get("decision") or "") != authorization_backend.AUTHORIZED_DECISION:
            blockers.append("production_authorization_decision_invalid")
        if authorization_backend._result_is_stale(base, authorization_result) or bool(authorization_result.get("stale")):
            blockers.append("production_authorization_result_stale")
        if str(authorization_result.get("canonical_rule_id") or "") != canonical_rule_id:
            blockers.append("production_authorization_rule_mismatch")
        if str(authorization_result.get("production_target_id") or "") != production_target_id:
            blockers.append("production_authorization_target_mismatch")
    if not authorization_plan:
        blockers.append("production_authorization_plan_missing")
    if not authorization_receipt:
        blockers.append("production_authorization_receipt_missing")
    elif str(authorization_receipt.get("result_fingerprint") or "") != str(authorization_result.get("result_fingerprint") or ""):
        blockers.append("production_authorization_receipt_fingerprint_mismatch")

    if rule and authorization_result:
        if str(authorization_result.get("document_id") or "") != str(rule.get("document_id") or ""):
            blockers.append("production_authorization_document_mismatch")
        if str(authorization_result.get("source_revision") or "") != str(rule.get("source_revision") or ""):
            blockers.append("production_authorization_source_revision_mismatch")

    if not committed_state:
        blockers.append("controlled_integration_committed_state_missing")
    else:
        if str(committed_state.get("verification_status") or "") != "verified_committed":
            blockers.append("controlled_integration_committed_state_unverified")
        if str(committed_state.get("state_fingerprint") or "") != str(authorization_result.get("committed_state_fingerprint") or ""):
            blockers.append("controlled_integration_committed_state_fingerprint_mismatch")
        if str(committed_state.get("environment_class") or "isolated_non_production") != "isolated_non_production":
            blockers.append("controlled_integration_environment_invalid")

    if not descriptor:
        blockers.append("production_target_descriptor_missing")
    else:
        if str(descriptor.get("descriptor_fingerprint") or "") != str(authorization_result.get("production_target_descriptor_fingerprint") or ""):
            blockers.append("production_target_descriptor_fingerprint_mismatch")
        if str(descriptor.get("adapter_manifest_fingerprint") or "") != str(authorization_result.get("production_adapter_manifest_fingerprint") or ""):
            blockers.append("production_target_adapter_manifest_version_mismatch")
        if str(descriptor.get("adapter_capability_fingerprint") or "") != str(authorization_result.get("production_adapter_capability_fingerprint") or ""):
            blockers.append("production_target_adapter_capability_fingerprint_mismatch")
    if str(target_workspace.get("status") or "") not in {"healthy", "warning"}:
        blockers.append("production_target_workspace_unhealthy")
    if str(target_workspace.get("operation_capability_status") or "") != "available":
        blockers.append("production_target_operation_capability_unavailable")

    if not adapter_manifest:
        blockers.append("production_deployment_adapter_manifest_missing")
    else:
        if not bool(adapter_manifest.get("one_rule_scope")):
            blockers.append("production_deployment_adapter_scope_invalid")
    deployment_package = _build_deployment_package(bundle)
    package_validation = adapter_backend.validate_production_deployment_package(production_target_id, deployment_package, root=base)
    preflight = adapter_backend.preflight_production_deployment(production_target_id, deployment_package, root=base)
    if str(package_validation.get("status") or "") != "valid":
        blockers.extend(list(package_validation.get("blockers", [])))
    if str(preflight.get("status") or "") not in {"ready", "already_committed"}:
        blockers.extend(list(preflight.get("blockers", [])))

    status = _eligibility_status(blockers, warnings)
    return {
        "status": status,
        "canonical_rule_id": canonical_rule_id,
        "document_id": rule.get("document_id"),
        "source_revision": rule.get("source_revision"),
        "certification_status": certification.get("certification_status", "missing"),
        "production_authorization_status": authorization_result.get("status", "missing"),
        "phase_9t_verification_status": committed_state.get("verification_status", "missing"),
        "production_target_status": target_workspace.get("status", "missing"),
        "adapter_version": adapter_manifest.get("adapter_version", "missing"),
        "transaction_id": preflight.get("transaction_id"),
        "deployed_rule_id": _predicted_deployed_rule_id(bundle),
        "deployment_package_fingerprint": deployment_package.get("package_fingerprint"),
        "transaction_package_fingerprint": package_validation.get("transaction_package_fingerprint"),
        "pre_deployment_production_state_fingerprint": preflight.get("current_production_state_fingerprint"),
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
        "recommended_action": _recommended_action(status),
    }


def build_certified_rule_production_deployment_plan(
    canonical_rule_id: str,
    production_authorization_result_id: str,
    production_target_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    eligibility = validate_certified_rule_production_deployment_eligibility(
        canonical_rule_id, production_authorization_result_id, production_target_id, root=base
    )
    if eligibility.get("blockers"):
        return {
            "status": str(eligibility.get("status") or "blocked"),
            "canonical_rule_id": canonical_rule_id,
            "production_authorization_result_id": production_authorization_result_id,
            "production_target_id": production_target_id,
            "warnings": list(eligibility.get("warnings", [])),
            "blockers": list(eligibility.get("blockers", [])),
        }
    bundle = _load_bundle(base, canonical_rule_id, production_authorization_result_id, production_target_id)
    deployment_package = _build_deployment_package(bundle)
    package_validation = adapter_backend.validate_production_deployment_package(production_target_id, deployment_package, root=base)
    preflight = adapter_backend.preflight_production_deployment(production_target_id, deployment_package, root=base)
    authorization_result = bundle["production_authorization_result"]
    authorization_plan = bundle["production_authorization_plan"]
    rule = bundle["rule"]
    certification = bundle["certification"]
    descriptor = bundle["production_target_descriptor"]
    adapter_manifest = bundle["adapter_manifest"]
    committed_state = bundle["committed_state"]
    plan = {
        "schema_version": PLAN_SCHEMA,
        "production_deployment_schema_version": DEPLOYMENT_SCHEMA_VERSION,
        "production_deployment_plan_id": _plan_id(bundle),
        "canonical_rule_id": canonical_rule_id,
        "canonical_rule_fingerprint": rule.get("rule_fingerprint"),
        "document_id": rule.get("document_id"),
        "source_revision": int(str(rule.get("source_revision") or "0")),
        "certification_id": certification.get("certification_id"),
        "certification_fingerprint": authorization_plan.get("certification_fingerprint") or authorization_backend._certification_fingerprint(certification),
        "production_authorization_result_id": production_authorization_result_id,
        "production_authorization_plan_id": authorization_result.get("production_authorization_plan_id"),
        "production_authorization_result_fingerprint": authorization_result.get("result_fingerprint"),
        "controlled_integration_result_id": authorization_result.get("controlled_integration_result_id"),
        "controlled_integration_result_fingerprint": authorization_result.get("controlled_integration_result_fingerprint"),
        "release_candidate_result_id": authorization_result.get("release_candidate_result_id"),
        "release_candidate_result_fingerprint": authorization_result.get("release_candidate_result_fingerprint"),
        "integration_authorization_result_id": authorization_result.get("integration_authorization_result_id"),
        "integration_authorization_result_fingerprint": authorization_result.get("integration_authorization_result_fingerprint"),
        "scoring_preview_result_id": authorization_result.get("scoring_preview_result_id"),
        "scoring_preview_result_fingerprint": authorization_result.get("scoring_preview_result_fingerprint"),
        "scoring_config_id": authorization_result.get("scoring_config_id"),
        "scoring_config_fingerprint": authorization_result.get("scoring_config_fingerprint"),
        "fast_lane_preview_result_id": authorization_result.get("fast_lane_preview_result_id"),
        "fast_lane_preview_result_fingerprint": authorization_result.get("fast_lane_preview_result_fingerprint"),
        "fast_lane_contract_id": authorization_result.get("fast_lane_contract_id"),
        "fast_lane_contract_version": authorization_result.get("fast_lane_contract_version"),
        "fast_lane_capability_fingerprint": authorization_result.get("fast_lane_capability_fingerprint"),
        "phase_9t_target_id": authorization_result.get("isolated_target_id"),
        "phase_9t_target_fingerprint": authorization_result.get("isolated_target_fingerprint"),
        "phase_9t_namespace_id": authorization_result.get("namespace_id"),
        "phase_9t_transaction_id": authorization_result.get("transaction_id"),
        "phase_9t_committed_state_fingerprint": committed_state.get("state_fingerprint") or authorization_result.get("committed_state_fingerprint"),
        "production_target_id": production_target_id,
        "production_target_descriptor_fingerprint": descriptor.get("descriptor_fingerprint"),
        "production_adapter_manifest_fingerprint": descriptor.get("adapter_manifest_fingerprint"),
        "production_adapter_capability_fingerprint": descriptor.get("adapter_capability_fingerprint"),
        "production_deployment_adapter_fingerprint": adapter_manifest.get("adapter_fingerprint"),
        "deployment_package_id": deployment_package.get("package_id"),
        "deployment_package_fingerprint": deployment_package.get("package_fingerprint"),
        "transaction_package_fingerprint": package_validation.get("transaction_package_fingerprint"),
        "predicted_transaction_id": preflight.get("transaction_id"),
        "predicted_deployed_rule_id": _predicted_deployed_rule_id(bundle),
        "pre_deployment_production_state_fingerprint": preflight.get("current_production_state_fingerprint"),
        "deployment_mode": "explicitly_authorized_single_rule_production_deployment",
        "rollback_mode": "transaction_owned_deployed_instance_only",
        "plan_fingerprint": _plan_fingerprint(bundle, deployment_package, preflight),
        "warnings": list(eligibility.get("warnings", [])),
        "blockers": list(eligibility.get("blockers", [])),
    }
    path = _plan_path(base, str(plan["production_deployment_plan_id"]))
    existing = _read_json(path)
    if isinstance(existing, Mapping):
        if str(existing.get("plan_fingerprint") or "") == str(plan.get("plan_fingerprint") or ""):
            return {"status": "planned", "production_deployment_plan_id": plan["production_deployment_plan_id"], "writes_performed": 0, **_plan_summary(plan)}
        return {"status": "corrupt", "production_deployment_plan_id": plan["production_deployment_plan_id"], "warnings": [], "blockers": ["production_deployment_plan_divergence"]}
    before_plan = _read_json(path)
    before_index = _read_json(base / "indexes" / PLAN_INDEX)
    try:
        _atomic_write_json(path, plan)
        _update_plan_index(base)
    except Exception:
        _restore_json(path, before_plan)
        _restore_json(base / "indexes" / PLAN_INDEX, before_index)
        return {"status": "corrupt", "production_deployment_plan_id": plan["production_deployment_plan_id"], "warnings": [], "blockers": ["production_deployment_plan_write_failure"]}
    return {"status": "planned", "production_deployment_plan_id": plan["production_deployment_plan_id"], "writes_performed": 1, **_plan_summary(plan)}


def execute_certified_rule_production_deployment(
    production_deployment_plan_id: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    if confirmation != REQUIRED_CONFIRMATION:
        return {"status": "blocked", "production_deployment_plan_id": production_deployment_plan_id, "warnings": [], "blockers": ["production_deployment_confirmation_required"]}
    plan = _read_json(_plan_path(base, production_deployment_plan_id))
    if not isinstance(plan, Mapping):
        return {"status": "blocked", "production_deployment_plan_id": production_deployment_plan_id, "warnings": [], "blockers": ["production_deployment_plan_missing"]}
    existing = _find_result(base, production_deployment_plan_id)
    if isinstance(existing, Mapping):
        existing_receipt = _find_receipt_for_result(base, str(existing.get("production_deployment_result_id") or ""))
        state = adapter_backend.read_production_deployment_state(str(plan.get("production_target_id") or ""), transaction_id=str(existing.get("production_transaction_id") or ""), root=base)
        if (
            str(existing.get("final_status") or "") == "completed"
            and not _result_is_stale(base, existing)
            and isinstance(existing_receipt, Mapping)
            and str(existing_receipt.get("result_fingerprint") or "") == str(existing.get("result_fingerprint") or "")
            and str(state.get("verification_status") or "") == "verified_committed"
            and str(state.get("deployed_rule_id") or "") == str(existing.get("deployed_rule_id") or "")
        ):
            return {
                "status": "already_completed",
                "production_deployment_plan_id": production_deployment_plan_id,
                "production_deployment_result_id": existing.get("production_deployment_result_id"),
                "production_deployment_receipt_id": existing_receipt.get("production_deployment_receipt_id"),
                "writes_performed": 0,
            }
        return {"status": "stale" if _result_is_stale(base, existing) else "corrupt", "production_deployment_plan_id": production_deployment_plan_id, "warnings": [], "blockers": ["production_deployment_existing_state_drift"]}

    canonical_rule_id = str(plan.get("canonical_rule_id") or "")
    production_authorization_result_id = str(plan.get("production_authorization_result_id") or "")
    production_target_id = str(plan.get("production_target_id") or "")
    current_plan = build_certified_rule_production_deployment_plan(
        canonical_rule_id, production_authorization_result_id, production_target_id, root=base
    )
    if str(current_plan.get("status") or "") not in ALLOWED_DECISIONLESS_STATUSES:
        return {"status": str(current_plan.get("status") or "blocked"), "production_deployment_plan_id": production_deployment_plan_id, "warnings": list(current_plan.get("warnings", [])), "blockers": list(current_plan.get("blockers", []))}
    current_plan_record = _read_json(_plan_path(base, str(current_plan.get("production_deployment_plan_id") or "")))
    if not isinstance(current_plan_record, Mapping) or str(current_plan_record.get("plan_fingerprint") or "") != str(plan.get("plan_fingerprint") or ""):
        return {"status": "stale", "production_deployment_plan_id": production_deployment_plan_id, "warnings": [], "blockers": ["production_deployment_plan_fingerprint_mismatch"]}

    bundle = _load_bundle(base, canonical_rule_id, production_authorization_result_id, production_target_id)
    deployment_package = _build_deployment_package(bundle)
    preflight = adapter_backend.preflight_production_deployment(production_target_id, deployment_package, root=base)
    if str(preflight.get("status") or "") != "ready":
        return {"status": _final_blocking_status(preflight), "production_deployment_plan_id": production_deployment_plan_id, "warnings": list(preflight.get("warnings", [])), "blockers": list(preflight.get("blockers", []))}
    if str(preflight.get("transaction_id") or "") != str(plan.get("predicted_transaction_id") or ""):
        return {"status": "stale", "production_deployment_plan_id": production_deployment_plan_id, "warnings": [], "blockers": ["predicted_transaction_id_mismatch"]}
    if str(preflight.get("current_production_state_fingerprint") or "") != str(plan.get("pre_deployment_production_state_fingerprint") or ""):
        return {"status": "stale", "production_deployment_plan_id": production_deployment_plan_id, "warnings": [], "blockers": ["pre_deployment_production_state_fingerprint_mismatch"]}
    if str(plan.get("deployment_mode") or "") != "explicitly_authorized_single_rule_production_deployment":
        return {"status": "corrupt", "production_deployment_plan_id": production_deployment_plan_id, "warnings": [], "blockers": ["production_deployment_mode_invalid"]}

    source_rule_before = load_canonical_rule(canonical_rule_id, require_active=True, root=base)
    source_rule_before_payload = source_rule_before.get("rule") if isinstance(source_rule_before.get("rule"), Mapping) else {}
    transaction_id = str(preflight.get("transaction_id") or "")
    apply_result = adapter_backend.apply_production_deployment(
        production_target_id,
        deployment_package,
        confirmation=adapter_backend.APPLY_CONFIRMATION,
        root=base,
    )
    if str(apply_result.get("status") or "") != "pending_verification":
        return _rollback_outcome(base, plan, transaction_id, "apply_failed", apply_result, source_rule_before_payload)
    verify_pending = adapter_backend.verify_production_deployment(production_target_id, transaction_id, root=base)
    if str(verify_pending.get("status") or "") != "verified_pending":
        return _rollback_outcome(base, plan, transaction_id, "verification_failed", verify_pending, source_rule_before_payload)
    commit_result = adapter_backend.commit_production_deployment(
        production_target_id,
        transaction_id,
        str(verify_pending.get("pending_state_fingerprint") or ""),
        confirmation=adapter_backend.COMMIT_CONFIRMATION,
        root=base,
    )
    if str(commit_result.get("status") or "") != "committed":
        return _rollback_outcome(base, plan, transaction_id, "commit_failed", commit_result, source_rule_before_payload)
    committed_state = adapter_backend.read_production_deployment_state(production_target_id, transaction_id=transaction_id, root=base)
    if str(committed_state.get("verification_status") or "") != "verified_committed":
        return _rollback_outcome(base, plan, transaction_id, "verification_failed", committed_state, source_rule_before_payload)

    deployed_rule = load_canonical_rule(str(committed_state.get("deployed_rule_id") or ""), require_active=True, root=base)
    deployed_rule_payload = deployed_rule.get("rule") if isinstance(deployed_rule.get("rule"), Mapping) else {}
    source_rule_after = load_canonical_rule(canonical_rule_id, require_active=True, root=base)
    source_rule_after_payload = source_rule_after.get("rule") if isinstance(source_rule_after.get("rule"), Mapping) else {}
    if (
        source_rule_after.get("status") != "loaded"
        or str(source_rule_before_payload.get("rule_fingerprint") or "") != str(source_rule_after_payload.get("rule_fingerprint") or "")
    ):
        return _rollback_outcome(base, plan, transaction_id, "mutation_detected", committed_state, source_rule_before_payload)
    if (
        deployed_rule.get("status") != "loaded"
        or str(deployed_rule_payload.get("source_canonical_rule_id") or "") != canonical_rule_id
        or str(deployed_rule_payload.get("production_authorization_result_id") or "") != production_authorization_result_id
    ):
        return _rollback_outcome(base, plan, transaction_id, "verification_failed", committed_state, source_rule_before_payload)

    result_id = _result_id(production_deployment_plan_id)
    result = {
        "schema_version": RESULT_SCHEMA,
        "production_deployment_schema_version": DEPLOYMENT_SCHEMA_VERSION,
        "production_deployment_result_id": result_id,
        "production_deployment_plan_id": production_deployment_plan_id,
        "canonical_rule_id": canonical_rule_id,
        "canonical_rule_fingerprint": source_rule_after_payload.get("rule_fingerprint"),
        "deployed_rule_id": committed_state.get("deployed_rule_id"),
        "deployed_rule_fingerprint": deployed_rule_payload.get("rule_fingerprint"),
        "document_id": plan.get("document_id"),
        "source_revision": plan.get("source_revision"),
        "certification_id": plan.get("certification_id"),
        "certification_fingerprint": plan.get("certification_fingerprint"),
        "production_authorization_result_id": production_authorization_result_id,
        "production_authorization_result_fingerprint": plan.get("production_authorization_result_fingerprint"),
        "controlled_integration_result_id": plan.get("controlled_integration_result_id"),
        "controlled_integration_result_fingerprint": plan.get("controlled_integration_result_fingerprint"),
        "phase_9t_committed_state_fingerprint": plan.get("phase_9t_committed_state_fingerprint"),
        "production_target_id": production_target_id,
        "production_target_descriptor_fingerprint": plan.get("production_target_descriptor_fingerprint"),
        "production_deployment_adapter_fingerprint": plan.get("production_deployment_adapter_fingerprint"),
        "deployment_package_fingerprint": plan.get("deployment_package_fingerprint"),
        "transaction_package_fingerprint": plan.get("transaction_package_fingerprint"),
        "production_transaction_id": transaction_id,
        "preflight_status": preflight.get("status"),
        "pre_deployment_production_state_fingerprint": plan.get("pre_deployment_production_state_fingerprint"),
        "apply_status": apply_result.get("status"),
        "pending_verification_status": verify_pending.get("status"),
        "pending_state_fingerprint": verify_pending.get("pending_state_fingerprint"),
        "commit_status": commit_result.get("status"),
        "committed_verification_status": committed_state.get("verification_status"),
        "committed_production_state_fingerprint": committed_state.get("production_state_fingerprint"),
        "rollback_status": "not_required",
        "production_safety_status": "passed",
        "final_status": "completed",
        "warnings": [],
        "blockers": [],
    }
    result["result_fingerprint"] = _result_fingerprint(result)
    receipt_id = _receipt_id(result_id)
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "production_deployment_receipt_id": receipt_id,
        "production_deployment_result_id": result_id,
        "production_deployment_plan_id": production_deployment_plan_id,
        "canonical_rule_id": canonical_rule_id,
        "document_id": result.get("document_id"),
        "source_revision": result.get("source_revision"),
        "production_authorization_result_id": production_authorization_result_id,
        "controlled_integration_result_id": plan.get("controlled_integration_result_id"),
        "production_target_id": production_target_id,
        "adapter_id": adapter_backend.get_production_deployment_adapter_manifest(root=base).get("adapter_id"),
        "deployment_package_fingerprint": result.get("deployment_package_fingerprint"),
        "production_transaction_id": transaction_id,
        "committed_production_state_fingerprint": result.get("committed_production_state_fingerprint"),
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
        return {"status": "corrupt", "production_deployment_plan_id": production_deployment_plan_id, "warnings": [], "blockers": ["production_deployment_result_write_failure"]}
    return {
        "status": "completed",
        "production_deployment_plan_id": production_deployment_plan_id,
        "production_deployment_result_id": result_id,
        "production_deployment_receipt_id": receipt_id,
        "production_transaction_id": transaction_id,
        "deployed_rule_id": result.get("deployed_rule_id"),
        "writes_performed": 2,
    }


def load_certified_rule_production_deployment_result(
    production_deployment_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    result = _find_result_by_id(base, production_deployment_result_id)
    if not isinstance(result, Mapping):
        return {"status": "not_found", "production_deployment_result_id": production_deployment_result_id, "production_deployment_result": None, "warnings": []}
    payload = dict(result)
    payload["stale"] = _result_is_stale(base, payload)
    return {"status": "loaded", "production_deployment_result_id": production_deployment_result_id, "production_deployment_result": payload, "warnings": []}


def get_certified_rule_production_deployment_health(
    production_deployment_plan_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    plans = _load_all(base / PLAN_DIR)
    results = _load_all(base / RESULT_DIR)
    receipts = _load_all(base / RECEIPT_DIR)
    if production_deployment_plan_id:
        plans = [item for item in plans if str(item.get("production_deployment_plan_id") or "") == production_deployment_plan_id]
        results = [item for item in results if str(item.get("production_deployment_plan_id") or "") == production_deployment_plan_id]
        receipts = [item for item in receipts if str(item.get("production_deployment_plan_id") or "") == production_deployment_plan_id]
    if not plans and not results and not receipts:
        return {"status": "empty", "production_deployment_plan_count": 0, "production_deployment_result_count": 0, "production_deployment_receipt_count": 0, "recommended_action": "Build one production deployment plan."}
    warnings: list[str] = []
    blockers: list[str] = []
    stale_count = 0
    for result in results:
        if _result_is_stale(base, result):
            stale_count += 1
        receipt = _find_receipt_for_result(base, str(result.get("production_deployment_result_id") or ""))
        if not isinstance(receipt, Mapping):
            warnings.append("production_deployment_receipt_missing")
        elif str(receipt.get("result_fingerprint") or "") != str(result.get("result_fingerprint") or ""):
            blockers.append("production_deployment_receipt_fingerprint_mismatch")
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
        "production_deployment_plan_count": len(plans),
        "production_deployment_result_count": len(results),
        "production_deployment_receipt_count": len(receipts),
        "stale_count": stale_count,
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
        "recommended_action": _recommended_action(status),
    }


def format_certified_rule_production_deployment_report(
    production_deployment_result_id: str | None = None,
    production_deployment_receipt_id: str | None = None,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    base = _ensure_dirs(root)
    result = _find_result_by_id(base, str(production_deployment_result_id or ""))
    receipt = _find_receipt_by_id(base, production_deployment_receipt_id)
    if not isinstance(result, Mapping):
        return "Certified rule production deployment result not found."
    lines = [
        "Certified Rule Production Deployment",
        f"Final Status: {result.get('final_status', 'unknown')}",
        f"Canonical Rule ID: {result.get('canonical_rule_id', 'unknown')}",
        f"Deployed Rule ID: {result.get('deployed_rule_id', 'unknown')}",
        f"Document ID: {result.get('document_id', 'unknown')}",
        f"Source Revision: {result.get('source_revision', 'unknown')}",
        f"Production Authorization Result ID: {result.get('production_authorization_result_id', 'unknown')}",
        f"Production Target ID: {result.get('production_target_id', 'unknown')}",
        f"Production Transaction ID: {result.get('production_transaction_id', 'unknown')}",
        f"Apply Status: {result.get('apply_status', 'unknown')}",
        f"Pending Verification: {result.get('pending_verification_status', 'unknown')}",
        f"Commit Status: {result.get('commit_status', 'unknown')}",
        f"Committed Verification: {result.get('committed_verification_status', 'unknown')}",
        f"Rollback Status: {result.get('rollback_status', 'unknown')}",
        "Production deployment occurred only after explicit Phase 9U authorization.",
        "Pending state was independently verified before commit.",
        "Committed production state was independently verified.",
        "Production scoring was not modified.",
        "Live Fast Lane was not executed.",
        "No unrelated canonical rule was changed.",
    ]
    if isinstance(receipt, Mapping):
        lines.append(f"Receipt ID: {receipt.get('production_deployment_receipt_id', 'unknown')}")
    warnings = list(result.get("warnings", []))
    blockers = list(result.get("blockers", []))
    if warnings:
        lines.append("Warnings: " + ", ".join(str(item) for item in warnings))
    if blockers:
        lines.append("Blockers: " + ", ".join(str(item) for item in blockers))
    return "\n".join(lines)


def get_certified_rule_production_deployment_summary(
    production_deployment_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    loaded = load_certified_rule_production_deployment_result(production_deployment_result_id, root=root)
    result = loaded.get("production_deployment_result") if isinstance(loaded.get("production_deployment_result"), Mapping) else {}
    return {
        "status": result.get("final_status", loaded.get("status", "unknown")),
        "canonical_rule_id": result.get("canonical_rule_id"),
        "deployed_rule_id": result.get("deployed_rule_id"),
        "production_target_id": result.get("production_target_id"),
        "production_transaction_id": result.get("production_transaction_id"),
        "committed_verification_status": result.get("committed_verification_status"),
        "rollback_status": result.get("rollback_status"),
        "recommended_action": "Observe post-deployment production behavior." if str(result.get("final_status") or "") == "completed" else _recommended_action(str(result.get("final_status") or loaded.get("status") or "unknown")),
    }


def _load_bundle(base: Path, canonical_rule_id: str, production_authorization_result_id: str, production_target_id: str) -> dict[str, Any]:
    rule_loaded = load_canonical_rule(canonical_rule_id, require_active=True, root=base)
    rule = rule_loaded.get("rule") if isinstance(rule_loaded.get("rule"), Mapping) else None
    authorization_loaded = authorization_backend.load_certified_rule_production_authorization_result(production_authorization_result_id, root=base)
    authorization_result = authorization_loaded.get("production_authorization_result") if isinstance(authorization_loaded.get("production_authorization_result"), Mapping) else None
    authorization_plan = _read_json(authorization_backend._plan_path(base, str((authorization_result or {}).get("production_authorization_plan_id") or "")))
    authorization_receipt = authorization_backend._find_receipt_for_result(base, str((authorization_result or {}).get("production_authorization_result_id") or ""))
    controlled_result_id = str((authorization_result or {}).get("controlled_integration_result_id") or "")
    auth_bundle = authorization_backend._load_bundle(base, canonical_rule_id, controlled_result_id, production_target_id)
    certification = auth_bundle.get("certification") if isinstance(auth_bundle.get("certification"), Mapping) else None
    committed_state = auth_bundle.get("committed_state") if isinstance(auth_bundle.get("committed_state"), Mapping) else None
    descriptor = ((auth_bundle.get("descriptor_loaded") or {}).get("production_target_descriptor")) if isinstance(auth_bundle.get("descriptor_loaded"), Mapping) else None
    target_workspace = adapter_backend.get_production_deployment_target_workspace(production_target_id, root=base)
    adapter_manifest = adapter_backend.get_production_deployment_adapter_manifest(root=base)
    return {
        "rule_loaded": rule_loaded,
        "rule": rule,
        "certification": certification,
        "production_authorization_loaded": authorization_loaded,
        "production_authorization_result": authorization_result,
        "production_authorization_plan": authorization_plan if isinstance(authorization_plan, Mapping) else None,
        "production_authorization_receipt": authorization_receipt,
        "committed_state": committed_state,
        "production_target_descriptor": descriptor,
        "target_workspace": target_workspace,
        "adapter_manifest": adapter_manifest,
        "authorization_bundle": auth_bundle,
    }


def _build_deployment_package(bundle: Mapping[str, Any]) -> dict[str, Any]:
    rule = bundle.get("rule") if isinstance(bundle.get("rule"), Mapping) else {}
    certification = bundle.get("certification") if isinstance(bundle.get("certification"), Mapping) else {}
    authorization_result = bundle.get("production_authorization_result") if isinstance(bundle.get("production_authorization_result"), Mapping) else {}
    authorization_plan = bundle.get("production_authorization_plan") if isinstance(bundle.get("production_authorization_plan"), Mapping) else {}
    descriptor = bundle.get("production_target_descriptor") if isinstance(bundle.get("production_target_descriptor"), Mapping) else {}
    adapter_manifest = bundle.get("adapter_manifest") if isinstance(bundle.get("adapter_manifest"), Mapping) else {}
    package = {
        "schema_version": adapter_backend.DEPLOYMENT_PACKAGE_SCHEMA_VERSION,
        "package_id": _package_id(bundle),
        "canonical_rule_id": rule.get("rule_id"),
        "canonical_rule_schema_version": rule.get("schema_version"),
        "canonical_rule_fingerprint": rule.get("rule_fingerprint"),
        "canonical_rule_payload": dict(rule),
        "document_id": rule.get("document_id"),
        "source_revision": int(str(rule.get("source_revision") or "0")),
        "certification_id": certification.get("certification_id") or authorization_plan.get("certification_id"),
        "certification_fingerprint": authorization_plan.get("certification_fingerprint") or authorization_backend._certification_fingerprint(certification),
        "controlled_integration_result_id": authorization_result.get("controlled_integration_result_id"),
        "controlled_integration_fingerprint": authorization_result.get("controlled_integration_result_fingerprint"),
        "isolated_committed_state_fingerprint": authorization_result.get("committed_state_fingerprint"),
        "production_authorization_result_id": authorization_result.get("production_authorization_result_id"),
        "production_authorization_fingerprint": authorization_result.get("result_fingerprint"),
        "production_target_id": authorization_result.get("production_target_id"),
        "production_target_descriptor_fingerprint": authorization_result.get("production_target_descriptor_fingerprint") or descriptor.get("descriptor_fingerprint"),
        "production_adapter_manifest_fingerprint": authorization_result.get("production_adapter_manifest_fingerprint") or descriptor.get("adapter_manifest_fingerprint"),
        "production_adapter_capability_fingerprint": authorization_result.get("production_adapter_capability_fingerprint") or descriptor.get("adapter_capability_fingerprint"),
        "deployment_adapter_fingerprint": adapter_manifest.get("adapter_fingerprint"),
    }
    package["package_fingerprint"] = adapter_backend._deployment_package_fingerprint(package)
    return package


def _rollback_outcome(
    base: Path,
    plan: Mapping[str, Any],
    transaction_id: str,
    stage_status: str,
    payload: Mapping[str, Any],
    source_rule_before_payload: Mapping[str, Any],
) -> dict[str, Any]:
    rollback_status = "not_attempted"
    if transaction_id:
        rolled = adapter_backend.rollback_production_deployment(
            str(plan.get("production_target_id") or ""),
            transaction_id,
            confirmation=adapter_backend.ROLLBACK_CONFIRMATION,
            root=base,
        )
        rollback_status = "rollback_completed" if str(rolled.get("status") or "") in {"completed", "already_rolled_back"} else "rollback_failed"
    source_rule_after = load_canonical_rule(str(plan.get("canonical_rule_id") or ""), require_active=True, root=base)
    if source_rule_after.get("status") != "loaded":
        rollback_status = "rollback_failed"
    else:
        payload_after = source_rule_after.get("rule") if isinstance(source_rule_after.get("rule"), Mapping) else {}
        if str(source_rule_before_payload.get("rule_fingerprint") or "") != str(payload_after.get("rule_fingerprint") or ""):
            rollback_status = "rollback_failed"
    final_status = rollback_status if rollback_status in {"rollback_completed", "rollback_failed"} else stage_status
    return {
        "status": final_status,
        "production_deployment_plan_id": plan.get("production_deployment_plan_id"),
        "production_transaction_id": transaction_id or None,
        "warnings": list(payload.get("warnings", [])) if isinstance(payload, Mapping) else [],
        "blockers": list(payload.get("blockers", [])) if isinstance(payload, Mapping) else [stage_status],
    }


def _plan_id(bundle: Mapping[str, Any]) -> str:
    authorization_result = bundle.get("production_authorization_result") or {}
    descriptor = bundle.get("production_target_descriptor") or {}
    adapter_manifest = bundle.get("adapter_manifest") or {}
    return "production_deployment_plan_" + _hash_payload(
        {
            "canonical_rule_id": authorization_result.get("canonical_rule_id"),
            "production_authorization_result_id": authorization_result.get("production_authorization_result_id"),
            "production_authorization_result_fingerprint": authorization_result.get("result_fingerprint"),
            "production_target_id": descriptor.get("target_id"),
            "descriptor_fingerprint": descriptor.get("descriptor_fingerprint"),
            "adapter_fingerprint": adapter_manifest.get("adapter_fingerprint"),
        }
    )[7:23]


def _package_id(bundle: Mapping[str, Any]) -> str:
    authorization_result = bundle.get("production_authorization_result") or {}
    rule = bundle.get("rule") or {}
    return "production_deployment_package_" + _hash_payload(
        {
            "canonical_rule_id": rule.get("rule_id"),
            "canonical_rule_fingerprint": rule.get("rule_fingerprint"),
            "production_authorization_result_id": authorization_result.get("production_authorization_result_id"),
            "production_target_id": authorization_result.get("production_target_id"),
        }
    )[7:23]


def _result_id(plan_id: str) -> str:
    return "production_deployment_result_" + _hash_payload({"plan_id": plan_id})[7:23]


def _receipt_id(result_id: str) -> str:
    return "production_deployment_receipt_" + _hash_payload({"result_id": result_id})[7:23]


def _predicted_deployed_rule_id(bundle: Mapping[str, Any]) -> str:
    deployment_package = _build_deployment_package(bundle)
    workspace = bundle.get("target_workspace") if isinstance(bundle.get("target_workspace"), Mapping) else {}
    tx_package = adapter_backend._to_transaction_package(deployment_package, workspace)
    transaction_id = adapter_backend.tx_backend._transaction_id(tx_package)
    return adapter_backend.tx_backend._deployed_rule_id(tx_package, transaction_id)


def _plan_fingerprint(bundle: Mapping[str, Any], deployment_package: Mapping[str, Any], preflight: Mapping[str, Any]) -> str:
    authorization_result = bundle.get("production_authorization_result") or {}
    descriptor = bundle.get("production_target_descriptor") or {}
    adapter_manifest = bundle.get("adapter_manifest") or {}
    rule = bundle.get("rule") or {}
    return _hash_payload(
        {
            "schema_version": DEPLOYMENT_SCHEMA_VERSION,
            "canonical_rule_id": rule.get("rule_id"),
            "canonical_rule_fingerprint": rule.get("rule_fingerprint"),
            "document_id": rule.get("document_id"),
            "source_revision": rule.get("source_revision"),
            "production_authorization_result_id": authorization_result.get("production_authorization_result_id"),
            "production_authorization_result_fingerprint": authorization_result.get("result_fingerprint"),
            "controlled_integration_result_fingerprint": authorization_result.get("controlled_integration_result_fingerprint"),
            "release_candidate_result_fingerprint": authorization_result.get("release_candidate_result_fingerprint"),
            "integration_authorization_result_fingerprint": authorization_result.get("integration_authorization_result_fingerprint"),
            "scoring_preview_result_fingerprint": authorization_result.get("scoring_preview_result_fingerprint"),
            "scoring_config_fingerprint": authorization_result.get("scoring_config_fingerprint"),
            "fast_lane_preview_result_fingerprint": authorization_result.get("fast_lane_preview_result_fingerprint"),
            "fast_lane_capability_fingerprint": authorization_result.get("fast_lane_capability_fingerprint"),
            "phase_9t_committed_state_fingerprint": authorization_result.get("committed_state_fingerprint"),
            "production_target_id": descriptor.get("target_id"),
            "production_target_descriptor_fingerprint": descriptor.get("descriptor_fingerprint"),
            "production_adapter_manifest_fingerprint": descriptor.get("adapter_manifest_fingerprint"),
            "production_adapter_capability_fingerprint": descriptor.get("adapter_capability_fingerprint"),
            "production_deployment_adapter_fingerprint": adapter_manifest.get("adapter_fingerprint"),
            "deployment_package_fingerprint": deployment_package.get("package_fingerprint"),
            "predicted_transaction_id": preflight.get("transaction_id"),
            "predicted_deployed_rule_id": _predicted_deployed_rule_id(bundle),
            "pre_deployment_production_state_fingerprint": preflight.get("current_production_state_fingerprint"),
            "deployment_mode": "explicitly_authorized_single_rule_production_deployment",
        }
    )


def _result_fingerprint(result: Mapping[str, Any]) -> str:
    return _hash_payload(
        {
            "schema_version": DEPLOYMENT_SCHEMA_VERSION,
            "production_deployment_plan_id": result.get("production_deployment_plan_id"),
            "production_authorization_result_fingerprint": result.get("production_authorization_result_fingerprint"),
            "deployment_package_fingerprint": result.get("deployment_package_fingerprint"),
            "production_transaction_id": result.get("production_transaction_id"),
            "deployed_rule_id": result.get("deployed_rule_id"),
            "deployed_rule_fingerprint": result.get("deployed_rule_fingerprint"),
            "final_status": result.get("final_status"),
        }
    )


def _eligibility_status(blockers: list[str], warnings: list[str]) -> str:
    if not blockers:
        return "eligible_with_warnings" if warnings else "eligible"
    if any("stale" in item or "mismatch" in item and "receipt" not in item for item in blockers):
        return "stale"
    if any("receipt" in item or "fingerprint" in item and "mismatch" in item for item in blockers):
        return "corrupt"
    return "blocked"


def _final_blocking_status(payload: Mapping[str, Any]) -> str:
    blockers = [str(item) for item in payload.get("blockers", [])]
    if any("stale" in item or "drift" in item for item in blockers):
        return "stale"
    if any("receipt" in item or "fingerprint" in item for item in blockers):
        return "corrupt"
    return "blocked"


def _recommended_action(status: str) -> str:
    if status in {"eligible", "eligible_with_warnings"}:
        return "Build or execute the authorized production deployment plan."
    if status == "stale":
        return "Refresh the production authorization evidence and deployment target state before deploying."
    if status == "corrupt":
        return "Repair inconsistent deployment evidence before executing production deployment."
    if status == "healthy":
        return "Production deployment records are internally consistent."
    if status == "warning":
        return "Review warnings before relying on the stored production deployment record."
    return "Resolve blockers before production deployment."


def _plan_summary(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "canonical_rule_id": plan.get("canonical_rule_id"),
        "document_id": plan.get("document_id"),
        "source_revision": plan.get("source_revision"),
        "production_authorization_result_id": plan.get("production_authorization_result_id"),
        "production_target_id": plan.get("production_target_id"),
        "predicted_transaction_id": plan.get("predicted_transaction_id"),
        "predicted_deployed_rule_id": plan.get("predicted_deployed_rule_id"),
        "plan_fingerprint": plan.get("plan_fingerprint"),
        "recommended_action": "Execute the authorized production deployment with explicit confirmation.",
    }


def _result_is_stale(base: Path, result: Mapping[str, Any]) -> bool:
    plan = _read_json(_plan_path(base, str(result.get("production_deployment_plan_id") or "")))
    if not isinstance(plan, Mapping):
        return True
    authorization_loaded = authorization_backend.load_certified_rule_production_authorization_result(
        str(result.get("production_authorization_result_id") or ""),
        root=base,
    )
    authorization_result = authorization_loaded.get("production_authorization_result") if isinstance(authorization_loaded.get("production_authorization_result"), Mapping) else {}
    state = adapter_backend.read_production_deployment_state(
        str(result.get("production_target_id") or ""),
        transaction_id=str(result.get("production_transaction_id") or ""),
        root=base,
    )
    deployed_rule = load_canonical_rule(str(result.get("deployed_rule_id") or ""), require_active=True, root=base)
    source_rule = load_canonical_rule(str(result.get("canonical_rule_id") or ""), require_active=True, root=base)
    deployed_rule_payload = deployed_rule.get("rule") if isinstance(deployed_rule.get("rule"), Mapping) else {}
    source_rule_payload = source_rule.get("rule") if isinstance(source_rule.get("rule"), Mapping) else {}
    return any(
        [
            not isinstance(authorization_result, Mapping),
            authorization_backend._result_is_stale(base, authorization_result),
            str(authorization_result.get("result_fingerprint") or "") != str(result.get("production_authorization_result_fingerprint") or ""),
            str(state.get("verification_status") or "") != "verified_committed",
            str(state.get("deployed_rule_id") or "") != str(result.get("deployed_rule_id") or ""),
            str(state.get("canonical_rule_id") or "") != str(result.get("canonical_rule_id") or ""),
            str(deployed_rule_payload.get("rule_fingerprint") or "") != str(result.get("deployed_rule_fingerprint") or ""),
            str(source_rule_payload.get("rule_fingerprint") or "") != str(result.get("canonical_rule_fingerprint") or ""),
        ]
    )


def _find_plan(base: Path, canonical_rule_id: str, production_authorization_result_id: str, production_target_id: str) -> dict[str, Any] | None:
    for item in _load_all(base / PLAN_DIR):
        if (
            str(item.get("canonical_rule_id") or "") == canonical_rule_id
            and str(item.get("production_authorization_result_id") or "") == production_authorization_result_id
            and str(item.get("production_target_id") or "") == production_target_id
        ):
            return item
    return None


def _find_result(base: Path, plan_id: str) -> dict[str, Any] | None:
    for item in _load_all(base / RESULT_DIR):
        if str(item.get("production_deployment_plan_id") or "") == plan_id:
            return item
    return None


def _find_result_by_id(base: Path, result_id: str) -> dict[str, Any] | None:
    payload = _read_json(_result_path(base, result_id))
    return dict(payload) if isinstance(payload, Mapping) else None


def _find_receipt_for_result(base: Path, result_id: str) -> dict[str, Any] | None:
    for item in _load_all(base / RECEIPT_DIR):
        if str(item.get("production_deployment_result_id") or "") == result_id:
            return item
    return None


def _find_receipt_by_id(base: Path, receipt_id: str | None) -> dict[str, Any] | None:
    if not receipt_id:
        return None
    payload = _read_json(_receipt_path(base, receipt_id))
    return dict(payload) if isinstance(payload, Mapping) else None


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


def _update_plan_index(base: Path) -> None:
    items = [
        {
            "production_deployment_plan_id": item.get("production_deployment_plan_id"),
            "canonical_rule_id": item.get("canonical_rule_id"),
            "production_authorization_result_id": item.get("production_authorization_result_id"),
            "production_target_id": item.get("production_target_id"),
            "plan_fingerprint": item.get("plan_fingerprint"),
        }
        for item in _load_all(base / PLAN_DIR)
    ]
    _atomic_write_json(base / "indexes" / PLAN_INDEX, {"schema_version": "certified_rule_production_deployment_plan_index_v1", "items": items, "updated_at_utc": _now()})


def _update_result_index(base: Path) -> None:
    items = [
        {
            "production_deployment_result_id": item.get("production_deployment_result_id"),
            "production_deployment_plan_id": item.get("production_deployment_plan_id"),
            "canonical_rule_id": item.get("canonical_rule_id"),
            "deployed_rule_id": item.get("deployed_rule_id"),
            "production_target_id": item.get("production_target_id"),
            "final_status": item.get("final_status"),
        }
        for item in _load_all(base / RESULT_DIR)
    ]
    _atomic_write_json(base / "indexes" / RESULT_INDEX, {"schema_version": "certified_rule_production_deployment_result_index_v1", "items": items, "updated_at_utc": _now()})


def _update_receipt_index(base: Path) -> None:
    items = [
        {
            "production_deployment_receipt_id": item.get("production_deployment_receipt_id"),
            "production_deployment_result_id": item.get("production_deployment_result_id"),
            "canonical_rule_id": item.get("canonical_rule_id"),
            "final_status": item.get("final_status"),
        }
        for item in _load_all(base / RECEIPT_DIR)
    ]
    _atomic_write_json(base / "indexes" / RECEIPT_INDEX, {"schema_version": "certified_rule_production_deployment_receipt_index_v1", "items": items, "updated_at_utc": _now()})


def _rollback_pending(rule: Mapping[str, Any]) -> bool:
    return bool(rule.get("rollback_pending")) or bool(rule.get("rollback_requested"))


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in items if str(item)))


def _ensure_dirs(root: Path | str) -> Path:
    base = _ensure_analysis_dirs(root)
    for folder in (PLAN_DIR, RESULT_DIR, RECEIPT_DIR, "indexes"):
        (base / folder).mkdir(parents=True, exist_ok=True)
    return base
