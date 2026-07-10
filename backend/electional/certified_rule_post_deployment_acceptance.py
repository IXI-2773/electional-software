"""Read-only post-deployment integrity observation and acceptance over completed Phase 9V deployments."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from . import certified_rule_production_deployment as deployment_backend
from . import production_deployment_adapter as adapter_backend
from .canonical_rule_runtime import _atomic_write_json, _hash_payload, _now, _read_json, _restore_json, _safe_id, load_canonical_rule
from .rule_effectiveness_analysis import _ensure_analysis_dirs
from .source_documents import SOURCE_DOCUMENT_ROOT

PLAN_DIR = "certified_rule_post_deployment_acceptance_plans"
RESULT_DIR = "certified_rule_post_deployment_acceptance_results"
RECEIPT_DIR = "certified_rule_post_deployment_acceptance_receipts"
PLAN_INDEX = "certified_rule_post_deployment_acceptance_plan_index.json"
RESULT_INDEX = "certified_rule_post_deployment_acceptance_result_index.json"
RECEIPT_INDEX = "certified_rule_post_deployment_acceptance_receipt_index.json"

PLAN_SCHEMA = "certified_rule_post_deployment_acceptance_plan_v1"
RESULT_SCHEMA = "certified_rule_post_deployment_acceptance_result_v1"
RECEIPT_SCHEMA = "certified_rule_post_deployment_acceptance_receipt_v1"
ACCEPTANCE_SCHEMA_VERSION = "certified_rule_post_deployment_acceptance_v1"
REQUIRED_CONFIRMATION = "SAVE_POST_DEPLOYMENT_ACCEPTANCE_DECISION"
DECISIONS = ("accept", "reject", "continue_observation")
PUBLIC_FUNCTIONS = [
    "build_certified_rule_post_deployment_acceptance_workspace",
    "validate_certified_rule_post_deployment_acceptance_eligibility",
    "build_certified_rule_post_deployment_acceptance_plan",
    "save_certified_rule_post_deployment_acceptance_decision",
    "load_certified_rule_post_deployment_acceptance_result",
    "get_certified_rule_post_deployment_acceptance_health",
    "format_certified_rule_post_deployment_acceptance_report",
    "get_certified_rule_post_deployment_acceptance_summary",
]


def _optional_telemetry_status(root: Path | str) -> str:
    try:
        from .deployed_rule_operational_telemetry import get_deployed_rule_operational_telemetry_manifest
    except Exception:
        return "unknown"
    manifest = get_deployed_rule_operational_telemetry_manifest(root=root)
    if bool(manifest.get("state_telemetry_available")):
        return "available_not_required"
    return "not_available"


def build_certified_rule_post_deployment_acceptance_workspace(
    production_deployment_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    eligibility = validate_certified_rule_post_deployment_acceptance_eligibility(production_deployment_result_id, root=base)
    plan = _find_plan(base, production_deployment_result_id)
    result = _find_result(base, str((plan or {}).get("post_deployment_acceptance_plan_id") or ""))
    receipt = _find_receipt_for_result(base, str((result or {}).get("post_deployment_acceptance_result_id") or ""))
    return {
        "status": "ready_for_planning" if not eligibility.get("blockers") else str(eligibility.get("status") or "blocked"),
        "canonical_rule_id": eligibility.get("canonical_rule_id"),
        "document_id": eligibility.get("document_id"),
        "source_revision": eligibility.get("source_revision"),
        "production_target_id": eligibility.get("production_target_id"),
        "production_transaction_id": eligibility.get("production_transaction_id"),
        "deployed_rule_id": eligibility.get("deployed_rule_id"),
        "production_deployment_result_id": production_deployment_result_id,
        "post_deployment_acceptance_plan_id": (plan or {}).get("post_deployment_acceptance_plan_id"),
        "post_deployment_acceptance_result_id": (result or {}).get("post_deployment_acceptance_result_id"),
        "post_deployment_acceptance_receipt_id": (receipt or {}).get("post_deployment_acceptance_receipt_id"),
        "warnings": list(eligibility.get("warnings", [])),
        "blockers": list(eligibility.get("blockers", [])),
        "recommended_action": "Build the post-deployment observation plan." if not eligibility.get("blockers") else eligibility.get("recommended_action", "Resolve blockers before recording post-deployment acceptance."),
    }


def validate_certified_rule_post_deployment_acceptance_eligibility(
    production_deployment_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    context = _observation_context(base, production_deployment_result_id)
    blockers = list(context["blockers"])
    warnings = list(context["warnings"])
    status = _eligibility_status(blockers, warnings)
    current_state = context["current_state"]
    deployment_result = context["deployment_result"]
    return {
        "status": status,
        "canonical_rule_id": deployment_result.get("canonical_rule_id"),
        "document_id": deployment_result.get("document_id"),
        "source_revision": deployment_result.get("source_revision"),
        "production_target_id": deployment_result.get("production_target_id"),
        "production_transaction_id": deployment_result.get("production_transaction_id"),
        "deployed_rule_id": deployment_result.get("deployed_rule_id"),
        "phase_9v_result_status": deployment_result.get("final_status", context["deployment_loaded"].get("status", "missing")),
        "current_transaction_status": current_state.get("transaction_state", current_state.get("status", "missing")),
        "current_verification_status": current_state.get("verification_status", "missing"),
        "current_deployed_rule_status": context["deployed_rule_loaded"].get("status", "missing"),
        "canonical_source_rule_status": context["source_rule_loaded"].get("status", "missing"),
        "rollback_status": deployment_result.get("rollback_status", "unknown"),
        "optional_telemetry_status": _optional_telemetry_status(base),
        "optional_telemetry_required": False,
        "warnings": warnings,
        "blockers": blockers,
        "recommended_action": _recommended_action(status),
    }


def build_certified_rule_post_deployment_acceptance_plan(
    production_deployment_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    eligibility = validate_certified_rule_post_deployment_acceptance_eligibility(production_deployment_result_id, root=base)
    if eligibility.get("blockers"):
        return {
            "status": str(eligibility.get("status") or "blocked"),
            "production_deployment_result_id": production_deployment_result_id,
            "warnings": list(eligibility.get("warnings", [])),
            "blockers": list(eligibility.get("blockers", [])),
        }
    context = _observation_context(base, production_deployment_result_id)
    deployment_result = context["deployment_result"]
    deployment_plan = context["deployment_plan"]
    deployment_receipt = context["deployment_receipt"]
    current_state = context["current_state"]
    source_rule = context["source_rule"]
    deployed_rule = context["deployed_rule"]
    plan = {
        "schema_version": PLAN_SCHEMA,
        "post_deployment_acceptance_schema_version": ACCEPTANCE_SCHEMA_VERSION,
        "post_deployment_acceptance_plan_id": _plan_id(deployment_result),
        "production_deployment_result_id": production_deployment_result_id,
        "production_deployment_plan_id": deployment_result.get("production_deployment_plan_id"),
        "production_deployment_receipt_id": deployment_receipt.get("production_deployment_receipt_id"),
        "production_deployment_result_fingerprint": deployment_result.get("result_fingerprint"),
        "production_deployment_plan_fingerprint": deployment_plan.get("plan_fingerprint"),
        "production_deployment_receipt_fingerprint": deployment_receipt.get("result_fingerprint"),
        "canonical_rule_id": deployment_result.get("canonical_rule_id"),
        "canonical_rule_fingerprint": deployment_result.get("canonical_rule_fingerprint"),
        "deployed_rule_id": deployment_result.get("deployed_rule_id"),
        "deployed_rule_fingerprint": deployment_result.get("deployed_rule_fingerprint"),
        "document_id": deployment_result.get("document_id"),
        "source_revision": deployment_result.get("source_revision"),
        "certification_id": deployment_result.get("certification_id"),
        "certification_fingerprint": deployment_result.get("certification_fingerprint"),
        "production_authorization_result_id": deployment_result.get("production_authorization_result_id"),
        "production_authorization_result_fingerprint": deployment_result.get("production_authorization_result_fingerprint"),
        "production_target_id": deployment_result.get("production_target_id"),
        "production_transaction_id": deployment_result.get("production_transaction_id"),
        "deployment_package_fingerprint": deployment_result.get("deployment_package_fingerprint"),
        "committed_production_state_fingerprint": deployment_result.get("committed_production_state_fingerprint"),
        "current_production_state_fingerprint": current_state.get("production_state_fingerprint"),
        "current_transaction_status": current_state.get("transaction_state"),
        "current_verification_status": current_state.get("verification_status"),
        "current_source_rule_fingerprint": source_rule.get("rule_fingerprint"),
        "current_deployed_rule_fingerprint": deployed_rule.get("rule_fingerprint"),
        "current_source_rule_status": context["source_rule_loaded"].get("status"),
        "current_deployed_rule_status": context["deployed_rule_loaded"].get("status"),
        "optional_telemetry_status": _optional_telemetry_status(base),
        "decision_options": list(DECISIONS),
        "warnings": list(eligibility.get("warnings", [])),
        "blockers": list(eligibility.get("blockers", [])),
    }
    plan["plan_fingerprint"] = _hash_payload(
        {
            key: plan[key]
            for key in (
                "production_deployment_result_id",
                "production_deployment_result_fingerprint",
                "production_deployment_plan_fingerprint",
                "production_deployment_receipt_fingerprint",
                "canonical_rule_id",
                "canonical_rule_fingerprint",
                "deployed_rule_id",
                "deployed_rule_fingerprint",
                "document_id",
                "source_revision",
                "certification_id",
                "certification_fingerprint",
                "production_authorization_result_id",
                "production_authorization_result_fingerprint",
                "production_target_id",
                "production_transaction_id",
                "deployment_package_fingerprint",
                "committed_production_state_fingerprint",
                "current_production_state_fingerprint",
                "current_transaction_status",
                "current_verification_status",
                "current_source_rule_fingerprint",
                "current_deployed_rule_fingerprint",
                "optional_telemetry_status",
                "decision_options",
            )
        }
    )
    path = _plan_path(base, str(plan["post_deployment_acceptance_plan_id"]))
    existing = _read_json(path)
    if isinstance(existing, Mapping):
        if str(existing.get("plan_fingerprint") or "") == str(plan.get("plan_fingerprint") or ""):
            return {"status": "planned", "post_deployment_acceptance_plan_id": plan["post_deployment_acceptance_plan_id"], "writes_performed": 0, **_plan_summary(plan)}
        return {"status": "corrupt", "post_deployment_acceptance_plan_id": plan["post_deployment_acceptance_plan_id"], "warnings": [], "blockers": ["post_deployment_acceptance_plan_divergence"]}
    before_plan = _read_json(path)
    before_index = _read_json(base / "indexes" / PLAN_INDEX)
    try:
        _atomic_write_json(path, plan)
        _update_plan_index(base)
    except Exception:
        _restore_json(path, before_plan)
        _restore_json(base / "indexes" / PLAN_INDEX, before_index)
        return {"status": "corrupt", "post_deployment_acceptance_plan_id": plan["post_deployment_acceptance_plan_id"], "warnings": [], "blockers": ["post_deployment_acceptance_plan_write_failure"]}
    return {"status": "planned", "post_deployment_acceptance_plan_id": plan["post_deployment_acceptance_plan_id"], "writes_performed": 1, **_plan_summary(plan)}


def save_certified_rule_post_deployment_acceptance_decision(
    post_deployment_acceptance_plan_id: str,
    decision: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    if confirmation != REQUIRED_CONFIRMATION:
        return {"status": "blocked", "post_deployment_acceptance_plan_id": post_deployment_acceptance_plan_id, "warnings": [], "blockers": ["post_deployment_acceptance_confirmation_required"], "writes_performed": 0}
    normalized_decision = str(decision or "").strip()
    if normalized_decision not in DECISIONS:
        return {"status": "blocked", "post_deployment_acceptance_plan_id": post_deployment_acceptance_plan_id, "warnings": [], "blockers": ["post_deployment_acceptance_decision_invalid"], "writes_performed": 0}
    plan = _read_json(_plan_path(base, post_deployment_acceptance_plan_id))
    if not isinstance(plan, Mapping):
        return {"status": "blocked", "post_deployment_acceptance_plan_id": post_deployment_acceptance_plan_id, "warnings": [], "blockers": ["post_deployment_acceptance_plan_missing"], "writes_performed": 0}

    current_plan = build_certified_rule_post_deployment_acceptance_plan(
        str(plan.get("production_deployment_result_id") or ""),
        root=base,
    )
    if str(current_plan.get("status") or "") != "planned":
        return {
            "status": str(current_plan.get("status") or "blocked"),
            "post_deployment_acceptance_plan_id": post_deployment_acceptance_plan_id,
            "warnings": list(current_plan.get("warnings", [])),
            "blockers": list(current_plan.get("blockers", [])),
            "writes_performed": 0,
        }
    current_plan_record = _read_json(_plan_path(base, str(current_plan.get("post_deployment_acceptance_plan_id") or "")))
    if not isinstance(current_plan_record, Mapping) or str(current_plan_record.get("plan_fingerprint") or "") != str(plan.get("plan_fingerprint") or ""):
        return {"status": "stale", "post_deployment_acceptance_plan_id": post_deployment_acceptance_plan_id, "warnings": [], "blockers": ["post_deployment_acceptance_plan_fingerprint_mismatch"], "writes_performed": 0}

    existing = _find_result(base, post_deployment_acceptance_plan_id)
    if isinstance(existing, Mapping):
        existing_receipt = _find_receipt_for_result(base, str(existing.get("post_deployment_acceptance_result_id") or ""))
        if (
            str(existing.get("decision") or "") == normalized_decision
            and not _result_is_stale(base, existing)
            and isinstance(existing_receipt, Mapping)
            and str(existing_receipt.get("result_fingerprint") or "") == str(existing.get("result_fingerprint") or "")
        ):
            return {
                "status": "already_recorded",
                "post_deployment_acceptance_plan_id": post_deployment_acceptance_plan_id,
                "post_deployment_acceptance_result_id": existing.get("post_deployment_acceptance_result_id"),
                "post_deployment_acceptance_receipt_id": existing_receipt.get("post_deployment_acceptance_receipt_id"),
                "writes_performed": 0,
            }
        return {"status": "conflict", "post_deployment_acceptance_plan_id": post_deployment_acceptance_plan_id, "warnings": [], "blockers": ["post_deployment_acceptance_result_immutable_conflict"], "writes_performed": 0}

    acceptance_status = {
        "accept": "accepted",
        "reject": "rejected",
        "continue_observation": "continue_observation",
    }[normalized_decision]
    result_id = _result_id(post_deployment_acceptance_plan_id)
    result = {
        "schema_version": RESULT_SCHEMA,
        "post_deployment_acceptance_schema_version": ACCEPTANCE_SCHEMA_VERSION,
        "post_deployment_acceptance_result_id": result_id,
        "post_deployment_acceptance_plan_id": post_deployment_acceptance_plan_id,
        "production_deployment_result_id": plan.get("production_deployment_result_id"),
        "production_deployment_plan_id": plan.get("production_deployment_plan_id"),
        "production_deployment_receipt_id": plan.get("production_deployment_receipt_id"),
        "production_deployment_result_fingerprint": plan.get("production_deployment_result_fingerprint"),
        "canonical_rule_id": plan.get("canonical_rule_id"),
        "canonical_rule_fingerprint": plan.get("canonical_rule_fingerprint"),
        "deployed_rule_id": plan.get("deployed_rule_id"),
        "deployed_rule_fingerprint": plan.get("deployed_rule_fingerprint"),
        "document_id": plan.get("document_id"),
        "source_revision": plan.get("source_revision"),
        "certification_id": plan.get("certification_id"),
        "certification_fingerprint": plan.get("certification_fingerprint"),
        "production_authorization_result_id": plan.get("production_authorization_result_id"),
        "production_authorization_result_fingerprint": plan.get("production_authorization_result_fingerprint"),
        "production_target_id": plan.get("production_target_id"),
        "production_transaction_id": plan.get("production_transaction_id"),
        "deployment_package_fingerprint": plan.get("deployment_package_fingerprint"),
        "committed_production_state_fingerprint": plan.get("committed_production_state_fingerprint"),
        "current_production_state_fingerprint": plan.get("current_production_state_fingerprint"),
        "current_transaction_status": plan.get("current_transaction_status"),
        "current_verification_status": plan.get("current_verification_status"),
        "current_source_rule_fingerprint": plan.get("current_source_rule_fingerprint"),
        "current_deployed_rule_fingerprint": plan.get("current_deployed_rule_fingerprint"),
        "optional_telemetry_status": plan.get("optional_telemetry_status"),
        "decision": normalized_decision,
        "decision_status": acceptance_status,
        "rollback_status": "not_invoked",
        "deployment_mutation_status": "not_invoked",
        "warnings": list(plan.get("warnings", [])),
        "blockers": list(plan.get("blockers", [])),
    }
    result["result_fingerprint"] = _hash_payload({key: result[key] for key in sorted(result) if key not in {"schema_version", "post_deployment_acceptance_schema_version", "warnings", "blockers"}})
    receipt_id = _receipt_id(result_id)
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "post_deployment_acceptance_receipt_id": receipt_id,
        "post_deployment_acceptance_result_id": result_id,
        "post_deployment_acceptance_plan_id": post_deployment_acceptance_plan_id,
        "production_deployment_result_id": result.get("production_deployment_result_id"),
        "canonical_rule_id": result.get("canonical_rule_id"),
        "deployed_rule_id": result.get("deployed_rule_id"),
        "decision": normalized_decision,
        "decision_status": acceptance_status,
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
        return {"status": "corrupt", "post_deployment_acceptance_plan_id": post_deployment_acceptance_plan_id, "warnings": [], "blockers": ["post_deployment_acceptance_result_write_failure"], "writes_performed": 0}
    return {
        "status": acceptance_status,
        "post_deployment_acceptance_plan_id": post_deployment_acceptance_plan_id,
        "post_deployment_acceptance_result_id": result_id,
        "post_deployment_acceptance_receipt_id": receipt_id,
        "writes_performed": 2,
        **_result_summary(result),
    }


def load_certified_rule_post_deployment_acceptance_result(
    post_deployment_acceptance_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    result = _find_result_by_id(base, post_deployment_acceptance_result_id)
    if not isinstance(result, Mapping):
        return {"status": "not_found", "post_deployment_acceptance_result_id": post_deployment_acceptance_result_id, "post_deployment_acceptance_result": None, "warnings": []}
    return {"status": "loaded", "post_deployment_acceptance_result_id": post_deployment_acceptance_result_id, "post_deployment_acceptance_result": dict(result), "warnings": []}


def get_certified_rule_post_deployment_acceptance_health(
    post_deployment_acceptance_plan_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    plans = _load_all(base / PLAN_DIR)
    results = _load_all(base / RESULT_DIR)
    receipts = _load_all(base / RECEIPT_DIR)
    if post_deployment_acceptance_plan_id:
        plans = [item for item in plans if str(item.get("post_deployment_acceptance_plan_id") or "") == post_deployment_acceptance_plan_id]
        results = [item for item in results if str(item.get("post_deployment_acceptance_plan_id") or "") == post_deployment_acceptance_plan_id]
        receipts = [item for item in receipts if str(item.get("post_deployment_acceptance_plan_id") or "") == post_deployment_acceptance_plan_id]
    if not plans and not results and not receipts:
        return {"status": "empty", "post_deployment_acceptance_plan_count": 0, "post_deployment_acceptance_result_count": 0, "post_deployment_acceptance_receipt_count": 0, "recommended_action": "Build one post-deployment observation plan."}
    warnings: list[str] = []
    blockers: list[str] = []
    stale_count = 0
    for result in results:
        if _result_is_stale(base, result):
            stale_count += 1
        receipt = _find_receipt_for_result(base, str(result.get("post_deployment_acceptance_result_id") or ""))
        if not isinstance(receipt, Mapping):
            warnings.append("post_deployment_acceptance_receipt_missing")
        elif str(receipt.get("result_fingerprint") or "") != str(result.get("result_fingerprint") or ""):
            blockers.append("post_deployment_acceptance_receipt_fingerprint_mismatch")
    status = "corrupt" if blockers else "stale" if stale_count else "warning" if warnings else "healthy"
    return {
        "status": status,
        "post_deployment_acceptance_plan_count": len(plans),
        "post_deployment_acceptance_result_count": len(results),
        "post_deployment_acceptance_receipt_count": len(receipts),
        "stale_count": stale_count,
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
        "recommended_action": _recommended_action(status),
    }


def format_certified_rule_post_deployment_acceptance_report(
    post_deployment_acceptance_result_id: str | None = None,
    post_deployment_acceptance_receipt_id: str | None = None,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    base = _ensure_dirs(root)
    result = _find_result_by_id(base, str(post_deployment_acceptance_result_id or ""))
    receipt = _find_receipt_by_id(base, post_deployment_acceptance_receipt_id)
    if not isinstance(result, Mapping):
        return "Certified rule post-deployment acceptance result not found."
    lines = [
        "Certified Rule Post-Deployment Acceptance",
        f"Decision Status: {result.get('decision_status', 'unknown')}",
        f"Decision: {result.get('decision', 'unknown')}",
        f"Canonical Rule ID: {result.get('canonical_rule_id', 'unknown')}",
        f"Deployed Rule ID: {result.get('deployed_rule_id', 'unknown')}",
        f"Document ID: {result.get('document_id', 'unknown')}",
        f"Source Revision: {result.get('source_revision', 'unknown')}",
        f"Production Deployment Result ID: {result.get('production_deployment_result_id', 'unknown')}",
        f"Production Transaction ID: {result.get('production_transaction_id', 'unknown')}",
        f"Current Verification Status: {result.get('current_verification_status', 'unknown')}",
        f"Optional Telemetry Status: {result.get('optional_telemetry_status', 'unknown')}",
        "Acceptance reflects deployment integrity and current state only.",
        "No deployment, rollback, scoring, or Fast Lane execution was performed by Phase 9W.",
        "The stored Phase 9V result was not treated as independent current-state verification.",
    ]
    if isinstance(receipt, Mapping):
        lines.append(f"Receipt ID: {receipt.get('post_deployment_acceptance_receipt_id', 'unknown')}")
    warnings = list(result.get("warnings", []))
    blockers = list(result.get("blockers", []))
    if warnings:
        lines.append("Warnings: " + ", ".join(str(item) for item in warnings))
    if blockers:
        lines.append("Blockers: " + ", ".join(str(item) for item in blockers))
    return "\n".join(lines)


def get_certified_rule_post_deployment_acceptance_summary(
    post_deployment_acceptance_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    loaded = load_certified_rule_post_deployment_acceptance_result(post_deployment_acceptance_result_id, root=root)
    result = loaded.get("post_deployment_acceptance_result") if isinstance(loaded.get("post_deployment_acceptance_result"), Mapping) else {}
    return {
        "status": result.get("decision_status", loaded.get("status", "unknown")),
        "canonical_rule_id": result.get("canonical_rule_id"),
        "deployed_rule_id": result.get("deployed_rule_id"),
        "production_target_id": result.get("production_target_id"),
        "production_transaction_id": result.get("production_transaction_id"),
        "current_verification_status": result.get("current_verification_status"),
        "recommended_action": "Proceed to post-deployment observation follow-up." if str(result.get("decision") or "") == "continue_observation" else _recommended_action(str(result.get("decision_status") or loaded.get("status") or "unknown")),
    }


def _observation_context(base: Path, production_deployment_result_id: str) -> dict[str, Any]:
    warnings: list[str] = []
    blockers: list[str] = []
    deployment_loaded = deployment_backend.load_certified_rule_production_deployment_result(production_deployment_result_id, root=base)
    deployment_result = deployment_loaded.get("production_deployment_result") if isinstance(deployment_loaded.get("production_deployment_result"), Mapping) else {}
    deployment_plan = _read_json(deployment_backend._plan_path(base, str(deployment_result.get("production_deployment_plan_id") or ""))) if deployment_result else None
    deployment_receipt = deployment_backend._find_receipt_for_result(base, production_deployment_result_id) if deployment_result else None

    if not isinstance(deployment_result, Mapping) or not deployment_result:
        blockers.append("production_deployment_result_missing")
    else:
        if str(deployment_result.get("final_status") or "") != "completed":
            blockers.append("production_deployment_not_completed")
        if deployment_backend._result_is_stale(base, deployment_result):
            blockers.append("production_deployment_result_stale")
        if str(deployment_result.get("rollback_status") or "") not in {"not_required", "not_invoked"}:
            blockers.append("production_deployment_rollback_recorded")
    if not isinstance(deployment_plan, Mapping):
        blockers.append("production_deployment_plan_missing")
    if not isinstance(deployment_receipt, Mapping):
        blockers.append("production_deployment_receipt_missing")
    elif str(deployment_receipt.get("result_fingerprint") or "") != str(deployment_result.get("result_fingerprint") or ""):
        blockers.append("production_deployment_receipt_fingerprint_mismatch")

    current_state = adapter_backend.read_production_deployment_state(
        str(deployment_result.get("production_target_id") or ""),
        transaction_id=str(deployment_result.get("production_transaction_id") or ""),
        root=base,
    ) if deployment_result else {"status": "missing"}
    if str(current_state.get("status") or "") != "loaded":
        blockers.append("current_production_transaction_state_missing")
    else:
        if str(current_state.get("verification_status") or "") != "verified_committed":
            blockers.append("current_production_transaction_not_verified_committed")
        if str(current_state.get("transaction_id") or "") != str(deployment_result.get("production_transaction_id") or ""):
            blockers.append("production_transaction_id_mismatch")
        if str(current_state.get("deployed_rule_id") or "") != str(deployment_result.get("deployed_rule_id") or ""):
            blockers.append("deployed_rule_id_mismatch")
        if str(current_state.get("canonical_rule_id") or "") != str(deployment_result.get("canonical_rule_id") or ""):
            blockers.append("canonical_rule_id_mismatch")
        if str(current_state.get("production_state_fingerprint") or "") != str(deployment_result.get("committed_production_state_fingerprint") or ""):
            blockers.append("committed_production_state_fingerprint_mismatch")

    source_rule_loaded = load_canonical_rule(str(deployment_result.get("canonical_rule_id") or ""), require_active=True, root=base) if deployment_result else {"status": "not_found"}
    source_rule = source_rule_loaded.get("rule") if isinstance(source_rule_loaded.get("rule"), Mapping) else {}
    if str(source_rule_loaded.get("status") or "") != "loaded":
        blockers.append("canonical_source_rule_missing_or_inactive")
    else:
        if str(source_rule.get("rule_fingerprint") or "") != str(deployment_result.get("canonical_rule_fingerprint") or ""):
            blockers.append("canonical_source_rule_fingerprint_mismatch")
        if str(source_rule.get("document_id") or "") != str(deployment_result.get("document_id") or ""):
            blockers.append("canonical_source_rule_document_mismatch")
        if str(source_rule.get("source_revision") or "") != str(deployment_result.get("source_revision") or ""):
            blockers.append("canonical_source_rule_source_revision_mismatch")

    deployed_rule_loaded = load_canonical_rule(str(deployment_result.get("deployed_rule_id") or ""), require_active=True, root=base) if deployment_result else {"status": "not_found"}
    deployed_rule = deployed_rule_loaded.get("rule") if isinstance(deployed_rule_loaded.get("rule"), Mapping) else {}
    if str(deployed_rule_loaded.get("status") or "") != "loaded":
        blockers.append("deployed_rule_missing_or_inactive")
    else:
        if str(deployed_rule.get("rule_fingerprint") or "") != str(deployment_result.get("deployed_rule_fingerprint") or ""):
            blockers.append("deployed_rule_fingerprint_mismatch")
        if str(deployed_rule.get("source_canonical_rule_id") or "") != str(deployment_result.get("canonical_rule_id") or ""):
            blockers.append("deployed_rule_source_binding_mismatch")
        if str(deployed_rule.get("production_activation_transaction_id") or "") != str(deployment_result.get("production_transaction_id") or ""):
            blockers.append("deployed_rule_transaction_binding_mismatch")

    return {
        "deployment_loaded": deployment_loaded,
        "deployment_result": deployment_result,
        "deployment_plan": deployment_plan if isinstance(deployment_plan, Mapping) else {},
        "deployment_receipt": deployment_receipt if isinstance(deployment_receipt, Mapping) else {},
        "current_state": current_state if isinstance(current_state, Mapping) else {},
        "source_rule_loaded": source_rule_loaded,
        "source_rule": source_rule,
        "deployed_rule_loaded": deployed_rule_loaded,
        "deployed_rule": deployed_rule,
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
    }


def _result_is_stale(base: Path, result: Mapping[str, Any]) -> bool:
    context = _observation_context(base, str(result.get("production_deployment_result_id") or ""))
    if context["blockers"]:
        return True
    return any(
        [
            str(context["deployment_result"].get("result_fingerprint") or "") != str(result.get("production_deployment_result_fingerprint") or ""),
            str(context["current_state"].get("production_state_fingerprint") or "") != str(result.get("current_production_state_fingerprint") or ""),
            str(context["source_rule"].get("rule_fingerprint") or "") != str(result.get("current_source_rule_fingerprint") or ""),
            str(context["deployed_rule"].get("rule_fingerprint") or "") != str(result.get("current_deployed_rule_fingerprint") or ""),
        ]
    )


def _find_plan(base: Path, production_deployment_result_id: str) -> dict[str, Any] | None:
    for item in _load_all(base / PLAN_DIR):
        if str(item.get("production_deployment_result_id") or "") == production_deployment_result_id:
            return item
    return None


def _find_result(base: Path, plan_id: str) -> dict[str, Any] | None:
    for item in _load_all(base / RESULT_DIR):
        if str(item.get("post_deployment_acceptance_plan_id") or "") == plan_id:
            return item
    return None


def _find_result_by_id(base: Path, result_id: str) -> dict[str, Any] | None:
    payload = _read_json(_result_path(base, result_id))
    return dict(payload) if isinstance(payload, Mapping) else None


def _find_receipt_for_result(base: Path, result_id: str) -> dict[str, Any] | None:
    for item in _load_all(base / RECEIPT_DIR):
        if str(item.get("post_deployment_acceptance_result_id") or "") == result_id:
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


def _plan_id(deployment_result: Mapping[str, Any]) -> str:
    return f"post_deployment_acceptance_plan_{_safe_id(str(deployment_result.get('production_deployment_result_id') or 'missing'))}"


def _result_id(plan_id: str) -> str:
    return f"{plan_id}_result"


def _receipt_id(result_id: str) -> str:
    return f"{result_id}_receipt"


def _plan_path(base: Path, plan_id: str) -> Path:
    return base / PLAN_DIR / f"{_safe_id(plan_id)}.json"


def _result_path(base: Path, result_id: str) -> Path:
    return base / RESULT_DIR / f"{_safe_id(result_id)}.json"


def _receipt_path(base: Path, receipt_id: str) -> Path:
    return base / RECEIPT_DIR / f"{_safe_id(receipt_id)}.json"


def _update_plan_index(base: Path) -> None:
    items = [
        {
            "post_deployment_acceptance_plan_id": item.get("post_deployment_acceptance_plan_id"),
            "production_deployment_result_id": item.get("production_deployment_result_id"),
            "canonical_rule_id": item.get("canonical_rule_id"),
            "deployed_rule_id": item.get("deployed_rule_id"),
            "production_target_id": item.get("production_target_id"),
            "plan_fingerprint": item.get("plan_fingerprint"),
        }
        for item in _load_all(base / PLAN_DIR)
    ]
    _atomic_write_json(base / "indexes" / PLAN_INDEX, {"schema_version": "certified_rule_post_deployment_acceptance_plan_index_v1", "items": items, "updated_at_utc": _now()})


def _update_result_index(base: Path) -> None:
    items = [
        {
            "post_deployment_acceptance_result_id": item.get("post_deployment_acceptance_result_id"),
            "post_deployment_acceptance_plan_id": item.get("post_deployment_acceptance_plan_id"),
            "production_deployment_result_id": item.get("production_deployment_result_id"),
            "canonical_rule_id": item.get("canonical_rule_id"),
            "deployed_rule_id": item.get("deployed_rule_id"),
            "decision_status": item.get("decision_status"),
        }
        for item in _load_all(base / RESULT_DIR)
    ]
    _atomic_write_json(base / "indexes" / RESULT_INDEX, {"schema_version": "certified_rule_post_deployment_acceptance_result_index_v1", "items": items, "updated_at_utc": _now()})


def _update_receipt_index(base: Path) -> None:
    items = [
        {
            "post_deployment_acceptance_receipt_id": item.get("post_deployment_acceptance_receipt_id"),
            "post_deployment_acceptance_result_id": item.get("post_deployment_acceptance_result_id"),
            "decision_status": item.get("decision_status"),
        }
        for item in _load_all(base / RECEIPT_DIR)
    ]
    _atomic_write_json(base / "indexes" / RECEIPT_INDEX, {"schema_version": "certified_rule_post_deployment_acceptance_receipt_index_v1", "items": items, "updated_at_utc": _now()})


def _eligibility_status(blockers: list[str], warnings: list[str]) -> str:
    if blockers:
        if any("stale" in item for item in blockers):
            return "stale"
        if any("mismatch" in item or "missing" in item for item in blockers):
            return "blocked"
        return "blocked"
    return "eligible_with_warnings" if warnings else "eligible"


def _recommended_action(status: str) -> str:
    return {
        "eligible": "Record an explicit post-deployment decision.",
        "eligible_with_warnings": "Review warnings, then record an explicit post-deployment decision.",
        "planned": "Record one immutable post-deployment decision.",
        "accepted": "Preserve the accepted deployment evidence and continue later monitoring separately.",
        "rejected": "Deployment rejection was recorded without automatic rollback.",
        "continue_observation": "Keep observing without mutating deployment state.",
        "healthy": "Post-deployment acceptance records are healthy.",
        "stale": "Re-read authoritative production state and rebuild the observation plan.",
        "blocked": "Resolve binding, state, or integrity blockers before acceptance.",
        "corrupt": "Inspect immutable records for divergence or fingerprint mismatch.",
        "conflict": "Existing immutable decision conflicts with the requested decision.",
    }.get(status, "Continue post-deployment integrity review.")


def _plan_summary(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "canonical_rule_id": plan.get("canonical_rule_id"),
        "document_id": plan.get("document_id"),
        "source_revision": plan.get("source_revision"),
        "production_target_id": plan.get("production_target_id"),
        "production_transaction_id": plan.get("production_transaction_id"),
        "deployed_rule_id": plan.get("deployed_rule_id"),
        "plan_fingerprint": plan.get("plan_fingerprint"),
        "warnings": list(plan.get("warnings", [])),
        "blockers": list(plan.get("blockers", [])),
    }


def _result_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "canonical_rule_id": result.get("canonical_rule_id"),
        "document_id": result.get("document_id"),
        "source_revision": result.get("source_revision"),
        "production_target_id": result.get("production_target_id"),
        "production_transaction_id": result.get("production_transaction_id"),
        "deployed_rule_id": result.get("deployed_rule_id"),
        "decision": result.get("decision"),
        "decision_status": result.get("decision_status"),
        "warnings": list(result.get("warnings", [])),
        "blockers": list(result.get("blockers", [])),
    }


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in items if str(item)))


def _ensure_dirs(root: Path | str) -> Path:
    base = _ensure_analysis_dirs(root)
    for folder in (PLAN_DIR, RESULT_DIR, RECEIPT_DIR, "indexes"):
        (base / folder).mkdir(parents=True, exist_ok=True)
    return base
