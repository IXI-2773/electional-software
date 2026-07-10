"""Human-reviewed integration authorization gate over stored scoring and Fast Lane previews."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from . import certified_rule_fast_lane_preview as fast_lane_backend
from . import certified_rule_scoring_preview as scoring_backend
from . import rule_effectiveness_analysis as analysis_backend
from .canonical_rule_runtime import load_canonical_rule
from .certified_rule_replay_adapter import _rule_has_unresolved_critical_remediation, _rule_pending_supersession
from .document_manifest import load_document_manifest
from .rule_effectiveness_analysis import _ensure_analysis_dirs, _hash_payload, _load_certification_receipt_for_rule
from .source_documents import SOURCE_DOCUMENT_ROOT

PLAN_DIR = "certified_rule_integration_authorization_plans"
RESULT_DIR = "certified_rule_integration_authorization_results"
RECEIPT_DIR = "certified_rule_integration_authorization_receipts"
PLAN_INDEX = "certified_rule_integration_authorization_plan_index.json"
RESULT_INDEX = "certified_rule_integration_authorization_result_index.json"
RECEIPT_INDEX = "certified_rule_integration_authorization_receipt_index.json"
PLAN_SCHEMA = "certified_rule_integration_authorization_plan_v1"
RESULT_SCHEMA = "certified_rule_integration_authorization_result_v1"
RECEIPT_SCHEMA = "certified_rule_integration_authorization_receipt_v1"
AUTH_SCHEMA_VERSION = "certified_rule_integration_authorization_v1"
REQUIRED_CONFIRMATION = "SAVE_INTEGRATION_AUTHORIZATION"
DECISIONS = {"authorize_for_later_integration", "reject_integration", "defer_integration"}
AUTHORIZE_ACKS = {
    "reviewed_scoring_preview",
    "reviewed_fast_lane_preview",
    "no_fast_lane_execution",
    "no_production_scoring_write",
    "no_rule_activation",
}
FINAL_SCORING_STATUSES = {"completed", "completed_with_unsupported_records"}
FINAL_FAST_LANE_STATUSES = {"completed", "incompatible"}
PUBLIC_FUNCTIONS = [
    "build_certified_rule_integration_authorization_workspace",
    "validate_certified_rule_integration_authorization_eligibility",
    "build_certified_rule_integration_authorization_plan",
    "save_certified_rule_integration_authorization_decision",
    "load_certified_rule_integration_authorization_result",
    "get_certified_rule_integration_authorization_health",
    "format_certified_rule_integration_authorization_report",
]


def build_certified_rule_integration_authorization_workspace(
    canonical_rule_id: str,
    scoring_preview_result_id: str | None = None,
    fast_lane_preview_result_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    resolved_scoring = scoring_preview_result_id or _latest_scoring_result_id(base, canonical_rule_id)
    resolved_fast_lane = fast_lane_preview_result_id or _latest_fast_lane_result_id(base, canonical_rule_id)
    eligibility = validate_certified_rule_integration_authorization_eligibility(
        canonical_rule_id,
        resolved_scoring or "",
        resolved_fast_lane or "",
        root=base,
    )
    plan = _find_plan(base, canonical_rule_id, resolved_scoring or "", resolved_fast_lane or "")
    result = _find_result(base, str((plan or {}).get("integration_authorization_plan_id") or ""))
    receipt = _find_receipt_for_result(base, str((result or {}).get("integration_authorization_result_id") or ""))
    return {
        "status": "ready_for_planning" if not eligibility.get("blockers") else str(eligibility.get("status") or "blocked"),
        "canonical_rule_id": canonical_rule_id,
        "document_id": eligibility.get("document_id"),
        "source_revision": eligibility.get("source_revision"),
        "rule_status": eligibility.get("rule_status", "unknown"),
        "certification_status": eligibility.get("certification_status", "unknown"),
        "scoring_preview_result_id": resolved_scoring,
        "fast_lane_preview_result_id": resolved_fast_lane,
        "integration_authorization_plan_id": (plan or {}).get("integration_authorization_plan_id"),
        "integration_authorization_result_id": (result or {}).get("integration_authorization_result_id"),
        "integration_authorization_receipt_id": (receipt or {}).get("integration_authorization_receipt_id"),
        "scoring_preview_status": eligibility.get("scoring_preview_status", "missing"),
        "fast_lane_preview_status": eligibility.get("fast_lane_preview_status", "missing"),
        "overall_compatibility": eligibility.get("overall_compatibility", "unknown"),
        "semantic_loss": eligibility.get("semantic_loss", "unknown"),
        "compatibility_status": eligibility.get("compatibility_status", "blocked"),
        "warnings": list(eligibility.get("warnings", [])),
        "blockers": list(eligibility.get("blockers", [])),
        "recommended_action": "Build the reviewed integration authorization plan." if not eligibility.get("blockers") else "Resolve evidence, lifecycle, or provenance blockers first.",
    }


def validate_certified_rule_integration_authorization_eligibility(
    canonical_rule_id: str,
    scoring_preview_result_id: str,
    fast_lane_preview_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    blockers: list[str] = []
    warnings: list[str] = []
    rule_loaded = load_canonical_rule(canonical_rule_id, require_active=True, root=base)
    rule = rule_loaded.get("rule")
    if rule_loaded.get("status") != "loaded" or not isinstance(rule, Mapping):
        blockers.extend(list(rule_loaded.get("blockers", []) or ["canonical_rule_not_active"]))
        return {"status": "blocked", "compatibility_status": "blocked", "warnings": [], "blockers": _dedupe(blockers)}
    certification = _load_certification_receipt_for_rule(base, canonical_rule_id)
    if not isinstance(certification, Mapping) or str(certification.get("certification_status") or "") != "completed":
        blockers.append("rule_certification_missing_or_stale")
    elif str(certification.get("rule_hash") or "") not in _acceptable_rule_fingerprints(rule):
        blockers.append("rule_certification_hash_mismatch")
    manifest = load_document_manifest(str(rule.get("document_id") or ""), root=base).get("manifest")
    if not isinstance(manifest, Mapping):
        blockers.append("document_manifest_missing")
    elif str(manifest.get("source_revision") or "") != str(rule.get("source_revision") or ""):
        blockers.append("source_revision_not_current")
    if _rule_pending_supersession(base, canonical_rule_id):
        blockers.append("rule_pending_supersession")
    if _rule_has_unresolved_critical_remediation(base, rule):
        blockers.append("rule_has_unresolved_critical_remediation")

    scoring_loaded = scoring_backend.load_certified_rule_scoring_preview_result(scoring_preview_result_id, root=base)
    scoring_result = scoring_loaded.get("scoring_preview_result")
    scoring_receipt = scoring_backend._find_receipt_for_result(base, scoring_preview_result_id) if isinstance(scoring_result, Mapping) else None
    if not isinstance(scoring_result, Mapping):
        blockers.append("scoring_preview_result_missing")
    else:
        if bool(scoring_result.get("stale")):
            blockers.append("scoring_preview_result_stale")
        if str(scoring_result.get("status") or "") not in FINAL_SCORING_STATUSES:
            blockers.append("scoring_preview_not_completed")
        if "production_state_mutation_detected" in list(scoring_result.get("blockers", []) or []):
            blockers.append("scoring_preview_mutation_detected")
        if str(scoring_result.get("canonical_rule_id") or "") != canonical_rule_id:
            blockers.append("scoring_preview_rule_mismatch")
        if str(scoring_result.get("document_id") or "") != str(rule.get("document_id") or ""):
            blockers.append("scoring_preview_document_mismatch")
        if str(scoring_result.get("source_revision") or "") != str(rule.get("source_revision") or ""):
            blockers.append("scoring_preview_source_revision_mismatch")
        if str(scoring_result.get("rule_fingerprint") or "") not in _acceptable_rule_fingerprints(rule):
            blockers.append("scoring_preview_rule_fingerprint_mismatch")
        if str(scoring_result.get("certification_fingerprint") or "") != _objective_certification_fingerprint(certification):
            blockers.append("scoring_preview_certification_fingerprint_mismatch")
        if not isinstance(scoring_receipt, Mapping):
            blockers.append("scoring_preview_receipt_missing")
        elif str(scoring_receipt.get("result_fingerprint") or "") != str(scoring_result.get("result_fingerprint") or ""):
            blockers.append("scoring_preview_receipt_fingerprint_mismatch")

    fast_lane_loaded = fast_lane_backend.load_certified_rule_fast_lane_preview_result(fast_lane_preview_result_id, root=base)
    fast_lane_result = fast_lane_loaded.get("fast_lane_preview_result")
    fast_lane_receipt = fast_lane_backend._find_receipt_for_result(base, fast_lane_preview_result_id) if isinstance(fast_lane_result, Mapping) else None
    if not isinstance(fast_lane_result, Mapping):
        blockers.append("fast_lane_preview_result_missing")
    else:
        if bool(fast_lane_result.get("stale")):
            blockers.append("fast_lane_preview_result_stale")
        if str(fast_lane_result.get("preview_status") or "") not in FINAL_FAST_LANE_STATUSES:
            blockers.append("fast_lane_preview_not_completed")
        if "production_state_mutation_detected" in list(fast_lane_result.get("blockers", []) or []):
            blockers.append("fast_lane_preview_mutation_detected")
        if str(fast_lane_result.get("canonical_rule_id") or "") != canonical_rule_id:
            blockers.append("fast_lane_preview_rule_mismatch")
        if str(fast_lane_result.get("document_id") or "") != str(rule.get("document_id") or ""):
            blockers.append("fast_lane_preview_document_mismatch")
        if str(fast_lane_result.get("source_revision") or "") != str(rule.get("source_revision") or ""):
            blockers.append("fast_lane_preview_source_revision_mismatch")
        if str(fast_lane_result.get("rule_fingerprint") or "") not in _acceptable_rule_fingerprints(rule):
            blockers.append("fast_lane_preview_rule_fingerprint_mismatch")
        if str(fast_lane_result.get("certification_fingerprint") or "") != _certification_fingerprint(certification):
            blockers.append("fast_lane_preview_certification_fingerprint_mismatch")
        if not isinstance(fast_lane_receipt, Mapping):
            blockers.append("fast_lane_preview_receipt_missing")
        elif str(fast_lane_receipt.get("result_fingerprint") or "") != str(fast_lane_result.get("result_fingerprint") or ""):
            blockers.append("fast_lane_preview_receipt_fingerprint_mismatch")
        if str(fast_lane_result.get("overall_compatibility") or "") == "compatible" and str(fast_lane_result.get("semantic_loss") or "") == "confirmed":
            warnings.append("compatible_with_semantic_loss_confirmed")

    status = "stale" if "source_revision_not_current" in blockers or "scoring_preview_result_stale" in blockers or "fast_lane_preview_result_stale" in blockers else "blocked" if blockers else "eligible"
    return {
        "status": status,
        "compatibility_status": "blocked" if blockers else "compatible",
        "canonical_rule_id": canonical_rule_id,
        "document_id": rule.get("document_id"),
        "source_revision": rule.get("source_revision"),
        "rule_status": rule.get("status"),
        "rule_fingerprint": rule.get("rule_fingerprint"),
        "certification_status": (certification or {}).get("certification_status", "missing"),
        "certification_fingerprint": _certification_fingerprint(certification),
        "scoring_preview_result_id": scoring_preview_result_id,
        "scoring_preview_receipt_id": (scoring_receipt or {}).get("scoring_preview_receipt_id"),
        "scoring_preview_status": (scoring_result or {}).get("status", "missing"),
        "scoring_preview_result_fingerprint": (scoring_result or {}).get("result_fingerprint"),
        "scoring_config_id": (scoring_result or {}).get("scoring_config_id"),
        "scoring_config_fingerprint": (scoring_result or {}).get("scoring_config_fingerprint"),
        "scoring_evaluator_fingerprint": (scoring_result or {}).get("scoring_evaluator_fingerprint"),
        "objective_pack_fingerprint": (scoring_result or {}).get("objective_pack_evaluation_fingerprint"),
        "controlled_input_fingerprint": (scoring_result or {}).get("controlled_input_fingerprint"),
        "scoring_metric_summary": _safe_scoring_metric_summary(scoring_result),
        "fast_lane_preview_result_id": fast_lane_preview_result_id,
        "fast_lane_preview_receipt_id": (fast_lane_receipt or {}).get("fast_lane_preview_receipt_id"),
        "fast_lane_preview_status": (fast_lane_result or {}).get("preview_status", "missing"),
        "fast_lane_preview_result_fingerprint": (fast_lane_result or {}).get("result_fingerprint"),
        "fast_lane_capability_fingerprint": (fast_lane_result or {}).get("fast_lane_capability_fingerprint"),
        "fast_lane_evaluator_fingerprint": (fast_lane_result or {}).get("compatibility_evaluator_fingerprint"),
        "overall_compatibility": (fast_lane_result or {}).get("overall_compatibility", "unknown"),
        "semantic_loss": (fast_lane_result or {}).get("semantic_loss", "unknown"),
        "fast_lane_summary": _safe_fast_lane_summary(fast_lane_result),
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
    }


def build_certified_rule_integration_authorization_plan(
    canonical_rule_id: str,
    scoring_preview_result_id: str,
    fast_lane_preview_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    eligibility = validate_certified_rule_integration_authorization_eligibility(
        canonical_rule_id,
        scoring_preview_result_id,
        fast_lane_preview_result_id,
        root=base,
    )
    if eligibility.get("blockers"):
        return {
            "status": str(eligibility.get("status") or "blocked"),
            "canonical_rule_id": canonical_rule_id,
            "scoring_preview_result_id": scoring_preview_result_id,
            "fast_lane_preview_result_id": fast_lane_preview_result_id,
            "warnings": list(eligibility.get("warnings", [])),
            "blockers": list(eligibility.get("blockers", [])),
        }
    plan = {
        "schema_version": PLAN_SCHEMA,
        "authorization_schema_version": AUTH_SCHEMA_VERSION,
        "integration_authorization_plan_id": _plan_id(eligibility),
        "canonical_rule_id": canonical_rule_id,
        "document_id": eligibility.get("document_id"),
        "source_revision": eligibility.get("source_revision"),
        "rule_fingerprint": eligibility.get("rule_fingerprint"),
        "certification_fingerprint": eligibility.get("certification_fingerprint"),
        "scoring_preview_result_id": scoring_preview_result_id,
        "scoring_preview_receipt_id": eligibility.get("scoring_preview_receipt_id"),
        "scoring_preview_result_fingerprint": eligibility.get("scoring_preview_result_fingerprint"),
        "scoring_config_id": eligibility.get("scoring_config_id"),
        "scoring_config_fingerprint": eligibility.get("scoring_config_fingerprint"),
        "scoring_evaluator_fingerprint": eligibility.get("scoring_evaluator_fingerprint"),
        "objective_pack_fingerprint": eligibility.get("objective_pack_fingerprint"),
        "controlled_input_fingerprint": eligibility.get("controlled_input_fingerprint"),
        "fast_lane_preview_result_id": fast_lane_preview_result_id,
        "fast_lane_preview_receipt_id": eligibility.get("fast_lane_preview_receipt_id"),
        "fast_lane_preview_result_fingerprint": eligibility.get("fast_lane_preview_result_fingerprint"),
        "fast_lane_capability_fingerprint": eligibility.get("fast_lane_capability_fingerprint"),
        "fast_lane_evaluator_fingerprint": eligibility.get("fast_lane_evaluator_fingerprint"),
        "overall_compatibility": eligibility.get("overall_compatibility"),
        "semantic_loss": eligibility.get("semantic_loss"),
        "scoring_metric_summary": eligibility.get("scoring_metric_summary"),
        "fast_lane_summary": eligibility.get("fast_lane_summary"),
        "warnings": list(eligibility.get("warnings", [])),
        "blockers": [],
        "plan_fingerprint": _plan_fingerprint(eligibility),
    }
    plan_path = _plan_path(base, str(plan["integration_authorization_plan_id"]))
    existing = analysis_backend._read_json(plan_path)
    if isinstance(existing, Mapping):
        if str(existing.get("plan_fingerprint") or "") == str(plan.get("plan_fingerprint") or ""):
            return {"status": "planned", "integration_authorization_plan_id": plan["integration_authorization_plan_id"], "writes_performed": 0, **_plan_summary(plan)}
        return {"status": "corrupt", "blockers": ["integration_authorization_plan_divergence"], "warnings": []}
    before_plan = analysis_backend._read_json(plan_path)
    before_index = analysis_backend._read_json(base / "indexes" / PLAN_INDEX)
    try:
        analysis_backend._atomic_write_json(plan_path, plan)
        _update_plan_index(base)
    except Exception:
        analysis_backend._restore_json(plan_path, before_plan)
        analysis_backend._restore_json(base / "indexes" / PLAN_INDEX, before_index)
        return {"status": "corrupt", "blockers": ["integration_authorization_plan_write_failure"], "warnings": []}
    return {"status": "planned", "integration_authorization_plan_id": plan["integration_authorization_plan_id"], "writes_performed": 1, **_plan_summary(plan)}


def save_certified_rule_integration_authorization_decision(
    integration_authorization_plan_id: str,
    reviewer_identity: str,
    decision: str,
    rationale: str,
    acknowledgements: list[str] | tuple[str, ...] | None = None,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    if confirmation != REQUIRED_CONFIRMATION:
        return {"status": "blocked", "integration_authorization_plan_id": integration_authorization_plan_id, "blockers": ["integration_authorization_confirmation_required"], "warnings": []}
    plan = analysis_backend._read_json(_plan_path(base, integration_authorization_plan_id))
    if not isinstance(plan, Mapping):
        return {"status": "blocked", "integration_authorization_plan_id": integration_authorization_plan_id, "blockers": ["integration_authorization_plan_missing"], "warnings": []}
    current = _plan_current_status(base, plan)
    if current["status"] != "current":
        return {"status": current["status"], "integration_authorization_plan_id": integration_authorization_plan_id, "blockers": list(current.get("blockers", [])), "warnings": []}
    normalized = _normalize_decision_payload(reviewer_identity, decision, rationale, acknowledgements)
    if normalized["blockers"]:
        return {"status": "blocked", "integration_authorization_plan_id": integration_authorization_plan_id, "blockers": list(normalized["blockers"]), "warnings": []}
    decision_blockers = _decision_specific_blockers(plan, normalized)
    if decision_blockers:
        return {"status": "blocked", "integration_authorization_plan_id": integration_authorization_plan_id, "blockers": decision_blockers, "warnings": []}
    existing = _find_result(base, integration_authorization_plan_id)
    decision_fingerprint = _decision_fingerprint(plan, normalized)
    if isinstance(existing, Mapping) and not _result_is_stale(base, existing):
        if str(existing.get("decision_fingerprint") or "") == decision_fingerprint:
            receipt = _find_receipt_for_result(base, str(existing.get("integration_authorization_result_id") or ""))
            if isinstance(receipt, Mapping) and str(receipt.get("result_fingerprint") or "") == str(existing.get("result_fingerprint") or ""):
                return {
                    "status": "already_completed",
                    "integration_authorization_plan_id": integration_authorization_plan_id,
                    "integration_authorization_result_id": existing.get("integration_authorization_result_id"),
                    "integration_authorization_receipt_id": receipt.get("integration_authorization_receipt_id"),
                    "writes_performed": 0,
                }
        return {"status": "blocked", "integration_authorization_plan_id": integration_authorization_plan_id, "blockers": ["integration_authorization_result_already_recorded"], "warnings": []}
    result_id = _result_id(integration_authorization_plan_id)
    result = {
        "schema_version": RESULT_SCHEMA,
        "authorization_schema_version": AUTH_SCHEMA_VERSION,
        "integration_authorization_result_id": result_id,
        "integration_authorization_plan_id": integration_authorization_plan_id,
        "canonical_rule_id": plan.get("canonical_rule_id"),
        "document_id": plan.get("document_id"),
        "source_revision": plan.get("source_revision"),
        "rule_fingerprint": plan.get("rule_fingerprint"),
        "certification_fingerprint": plan.get("certification_fingerprint"),
        "scoring_preview_result_id": plan.get("scoring_preview_result_id"),
        "scoring_preview_result_fingerprint": plan.get("scoring_preview_result_fingerprint"),
        "scoring_config_id": plan.get("scoring_config_id"),
        "scoring_config_fingerprint": plan.get("scoring_config_fingerprint"),
        "scoring_evaluator_fingerprint": plan.get("scoring_evaluator_fingerprint"),
        "fast_lane_preview_result_id": plan.get("fast_lane_preview_result_id"),
        "fast_lane_preview_result_fingerprint": plan.get("fast_lane_preview_result_fingerprint"),
        "fast_lane_capability_fingerprint": plan.get("fast_lane_capability_fingerprint"),
        "fast_lane_evaluator_fingerprint": plan.get("fast_lane_evaluator_fingerprint"),
        "overall_compatibility": plan.get("overall_compatibility"),
        "semantic_loss": plan.get("semantic_loss"),
        "decision": normalized["decision"],
        "reviewer_identity": normalized["reviewer_identity"],
        "rationale": normalized["rationale"],
        "acknowledgements": list(normalized["acknowledgements"]),
        "decision_fingerprint": decision_fingerprint,
        "status": _decision_status(normalized["decision"]),
        "warnings": [],
        "blockers": [],
        "result_fingerprint": _result_fingerprint(plan, normalized),
    }
    receipt_id = _receipt_id(result_id)
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "integration_authorization_receipt_id": receipt_id,
        "integration_authorization_result_id": result_id,
        "integration_authorization_plan_id": integration_authorization_plan_id,
        "canonical_rule_id": plan.get("canonical_rule_id"),
        "document_id": plan.get("document_id"),
        "source_revision": plan.get("source_revision"),
        "decision": normalized["decision"],
        "reviewer_identity": normalized["reviewer_identity"],
        "decision_fingerprint": decision_fingerprint,
        "result_fingerprint": result.get("result_fingerprint"),
        "created_at_utc": analysis_backend._now(),
    }
    before_result = analysis_backend._read_json(_result_path(base, result_id))
    before_receipt = analysis_backend._read_json(_receipt_path(base, receipt_id))
    before_result_index = analysis_backend._read_json(base / "indexes" / RESULT_INDEX)
    before_receipt_index = analysis_backend._read_json(base / "indexes" / RECEIPT_INDEX)
    try:
        analysis_backend._atomic_write_json(_result_path(base, result_id), result)
        analysis_backend._atomic_write_json(_receipt_path(base, receipt_id), receipt)
        _update_result_index(base)
        _update_receipt_index(base)
    except Exception:
        analysis_backend._restore_json(_result_path(base, result_id), before_result)
        analysis_backend._restore_json(_receipt_path(base, receipt_id), before_receipt)
        analysis_backend._restore_json(base / "indexes" / RESULT_INDEX, before_result_index)
        analysis_backend._restore_json(base / "indexes" / RECEIPT_INDEX, before_receipt_index)
        return {"status": "corrupt", "integration_authorization_plan_id": integration_authorization_plan_id, "blockers": ["integration_authorization_result_write_failure"], "warnings": []}
    return {
        "status": result["status"],
        "integration_authorization_plan_id": integration_authorization_plan_id,
        "integration_authorization_result_id": result_id,
        "integration_authorization_receipt_id": receipt_id,
        "decision": result["decision"],
        "writes_performed": 2,
    }


def load_certified_rule_integration_authorization_result(
    integration_authorization_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    result = analysis_backend._read_json(_result_path(base, integration_authorization_result_id))
    if not isinstance(result, Mapping):
        return {"status": "not_found", "integration_authorization_result_id": integration_authorization_result_id, "integration_authorization_result": None, "warnings": []}
    payload = dict(result)
    payload["stale"] = _result_is_stale(base, payload)
    return {"status": "loaded", "integration_authorization_result_id": integration_authorization_result_id, "integration_authorization_result": payload, "warnings": []}


def get_certified_rule_integration_authorization_health(
    integration_authorization_plan_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    plans = _load_all(base / PLAN_DIR)
    results = _load_all(base / RESULT_DIR)
    receipts = _load_all(base / RECEIPT_DIR)
    if integration_authorization_plan_id:
        plans = [item for item in plans if str(item.get("integration_authorization_plan_id") or "") == integration_authorization_plan_id]
        results = [item for item in results if str(item.get("integration_authorization_plan_id") or "") == integration_authorization_plan_id]
        receipts = [item for item in receipts if str(item.get("integration_authorization_plan_id") or "") == integration_authorization_plan_id]
    if not plans and not results and not receipts:
        return {"status": "empty", "integration_authorization_plan_count": 0, "integration_authorization_result_count": 0, "integration_authorization_receipt_count": 0, "recommended_action": "Build one integration authorization plan."}
    warnings: list[str] = []
    stale_count = 0
    if len({str(item.get("integration_authorization_plan_id") or "") for item in plans}) != len(plans):
        warnings.append("duplicate_integration_authorization_plan_ids")
    if len({str(item.get("integration_authorization_result_id") or "") for item in results}) != len(results):
        warnings.append("duplicate_integration_authorization_result_ids")
    for result in results:
        if _result_is_stale(base, result):
            stale_count += 1
        receipt = _find_receipt_for_result(base, str(result.get("integration_authorization_result_id") or ""))
        if not isinstance(receipt, Mapping):
            warnings.append("integration_authorization_receipt_missing")
        elif str(receipt.get("result_fingerprint") or "") != str(result.get("result_fingerprint") or ""):
            warnings.append("integration_authorization_receipt_fingerprint_mismatch")
    status = "corrupt" if any("mismatch" in item for item in warnings) else "stale" if stale_count else "warning" if warnings else "healthy"
    return {
        "status": status,
        "integration_authorization_plan_count": len(plans),
        "integration_authorization_result_count": len(results),
        "integration_authorization_receipt_count": len(receipts),
        "stale_authorization_count": stale_count,
        "warnings": _dedupe(warnings),
        "recommended_action": "Rebuild the integration authorization plan against current evidence." if stale_count else "Integration authorization health is good.",
    }


def format_certified_rule_integration_authorization_report(
    integration_authorization_result_id: str | None = None,
    integration_authorization_receipt_id: str | None = None,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    base = _ensure_dirs(root)
    receipt = _find_receipt_by_id(base, integration_authorization_receipt_id) if integration_authorization_receipt_id else None
    result = _find_result_by_id(base, integration_authorization_result_id or str((receipt or {}).get("integration_authorization_result_id") or ""))
    if not isinstance(result, Mapping):
        return "Certified Rule Integration Authorization\n\nStatus: not_found"
    rationale = str(result.get("rationale") or "")
    if public_safe:
        rationale = rationale.replace(str(base), "[redacted]")
    lines = [
        "Certified Rule Integration Authorization",
        "",
        f"Decision Status: {result.get('status')}",
        f"Decision: {result.get('decision')}",
        f"Reviewer: {result.get('reviewer_identity')}",
        f"Document ID: {result.get('document_id')}",
        f"Source Revision: {result.get('source_revision')}",
        f"Canonical Rule ID: {result.get('canonical_rule_id')}",
        f"Scoring Preview Result ID: {result.get('scoring_preview_result_id')}",
        f"Fast Lane Preview Result ID: {result.get('fast_lane_preview_result_id')}",
        f"Overall Compatibility: {result.get('overall_compatibility')}",
        f"Semantic Loss: {result.get('semantic_loss')}",
        f"Stale: {'Yes' if _result_is_stale(base, result) else 'No'}",
        f"Acknowledgements: {', '.join(str(item) for item in result.get('acknowledgements', [])) or 'none'}",
        f"Rationale: {rationale or 'none'}",
        "Execution: no Fast Lane, production scoring, or activation was performed.",
        "Safety: this phase records reviewed evidence only.",
    ]
    return "\n".join(lines)


def _ensure_dirs(root: Path | str) -> Path:
    base = _ensure_analysis_dirs(root)
    for folder in (PLAN_DIR, RESULT_DIR, RECEIPT_DIR, "indexes"):
        (base / folder).mkdir(parents=True, exist_ok=True)
    defaults = (
        (PLAN_INDEX, "certified_rule_integration_authorization_plan_index_v1"),
        (RESULT_INDEX, "certified_rule_integration_authorization_result_index_v1"),
        (RECEIPT_INDEX, "certified_rule_integration_authorization_receipt_index_v1"),
    )
    for name, schema in defaults:
        path = base / "indexes" / name
        if not path.exists():
            analysis_backend._atomic_write_json(path, {"schema_version": schema, "items": [], "updated_at_utc": analysis_backend._now()})
    return base


def _plan_path(base: Path, plan_id: str) -> Path:
    return base / PLAN_DIR / f"{analysis_backend._safe_id(plan_id)}.json"


def _result_path(base: Path, result_id: str) -> Path:
    return base / RESULT_DIR / f"{analysis_backend._safe_id(result_id)}.json"


def _receipt_path(base: Path, receipt_id: str) -> Path:
    return base / RECEIPT_DIR / f"{analysis_backend._safe_id(receipt_id)}.json"


def _load_all(directory: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        payload = analysis_backend._read_json(path)
        if isinstance(payload, Mapping):
            items.append(dict(payload))
    return items


def _update_plan_index(base: Path) -> None:
    items = []
    for payload in _load_all(base / PLAN_DIR):
        items.append(
            {
                "integration_authorization_plan_id": payload.get("integration_authorization_plan_id"),
                "canonical_rule_id": payload.get("canonical_rule_id"),
                "document_id": payload.get("document_id"),
                "source_revision": payload.get("source_revision"),
                "scoring_preview_result_id": payload.get("scoring_preview_result_id"),
                "fast_lane_preview_result_id": payload.get("fast_lane_preview_result_id"),
                "plan_fingerprint": payload.get("plan_fingerprint"),
            }
        )
    analysis_backend._atomic_write_json(base / "indexes" / PLAN_INDEX, {"schema_version": "certified_rule_integration_authorization_plan_index_v1", "items": items, "updated_at_utc": analysis_backend._now()})


def _update_result_index(base: Path) -> None:
    items = []
    for payload in _load_all(base / RESULT_DIR):
        items.append(
            {
                "integration_authorization_result_id": payload.get("integration_authorization_result_id"),
                "integration_authorization_plan_id": payload.get("integration_authorization_plan_id"),
                "canonical_rule_id": payload.get("canonical_rule_id"),
                "document_id": payload.get("document_id"),
                "source_revision": payload.get("source_revision"),
                "decision": payload.get("decision"),
                "status": payload.get("status"),
                "result_fingerprint": payload.get("result_fingerprint"),
            }
        )
    analysis_backend._atomic_write_json(base / "indexes" / RESULT_INDEX, {"schema_version": "certified_rule_integration_authorization_result_index_v1", "items": items, "updated_at_utc": analysis_backend._now()})


def _update_receipt_index(base: Path) -> None:
    items = []
    for payload in _load_all(base / RECEIPT_DIR):
        items.append(
            {
                "integration_authorization_receipt_id": payload.get("integration_authorization_receipt_id"),
                "integration_authorization_result_id": payload.get("integration_authorization_result_id"),
                "integration_authorization_plan_id": payload.get("integration_authorization_plan_id"),
                "decision": payload.get("decision"),
                "reviewer_identity": payload.get("reviewer_identity"),
                "result_fingerprint": payload.get("result_fingerprint"),
            }
        )
    analysis_backend._atomic_write_json(base / "indexes" / RECEIPT_INDEX, {"schema_version": "certified_rule_integration_authorization_receipt_index_v1", "items": items, "updated_at_utc": analysis_backend._now()})


def _plan_id(eligibility: Mapping[str, Any]) -> str:
    return "authplan_" + _hash_payload(
        {
            "canonical_rule_id": eligibility.get("canonical_rule_id"),
            "source_revision": eligibility.get("source_revision"),
            "rule_fingerprint": eligibility.get("rule_fingerprint"),
            "scoring_preview_result_id": eligibility.get("scoring_preview_result_id"),
            "scoring_preview_result_fingerprint": eligibility.get("scoring_preview_result_fingerprint"),
            "fast_lane_preview_result_id": eligibility.get("fast_lane_preview_result_id"),
            "fast_lane_preview_result_fingerprint": eligibility.get("fast_lane_preview_result_fingerprint"),
        }
    )[7:23]


def _result_id(plan_id: str) -> str:
    return "authresult_" + analysis_backend._safe_id(plan_id)


def _receipt_id(result_id: str) -> str:
    return "authreceipt_" + analysis_backend._safe_id(result_id)


def _plan_fingerprint(eligibility: Mapping[str, Any]) -> str:
    return _hash_payload(
        {
            "canonical_rule_id": eligibility.get("canonical_rule_id"),
            "document_id": eligibility.get("document_id"),
            "source_revision": eligibility.get("source_revision"),
            "rule_fingerprint": eligibility.get("rule_fingerprint"),
            "certification_fingerprint": eligibility.get("certification_fingerprint"),
            "scoring_preview_result_id": eligibility.get("scoring_preview_result_id"),
            "scoring_preview_result_fingerprint": eligibility.get("scoring_preview_result_fingerprint"),
            "scoring_config_fingerprint": eligibility.get("scoring_config_fingerprint"),
            "scoring_evaluator_fingerprint": eligibility.get("scoring_evaluator_fingerprint"),
            "objective_pack_fingerprint": eligibility.get("objective_pack_fingerprint"),
            "controlled_input_fingerprint": eligibility.get("controlled_input_fingerprint"),
            "fast_lane_preview_result_id": eligibility.get("fast_lane_preview_result_id"),
            "fast_lane_preview_result_fingerprint": eligibility.get("fast_lane_preview_result_fingerprint"),
            "fast_lane_capability_fingerprint": eligibility.get("fast_lane_capability_fingerprint"),
            "fast_lane_evaluator_fingerprint": eligibility.get("fast_lane_evaluator_fingerprint"),
            "overall_compatibility": eligibility.get("overall_compatibility"),
            "semantic_loss": eligibility.get("semantic_loss"),
        }
    )


def _decision_fingerprint(plan: Mapping[str, Any], normalized: Mapping[str, Any]) -> str:
    return _hash_payload(
        {
            "plan_fingerprint": plan.get("plan_fingerprint"),
            "reviewer_identity": normalized.get("reviewer_identity"),
            "decision": normalized.get("decision"),
            "rationale": normalized.get("rationale"),
            "acknowledgements": normalized.get("acknowledgements"),
        }
    )


def _result_fingerprint(plan: Mapping[str, Any], normalized: Mapping[str, Any]) -> str:
    return _hash_payload(
        {
            "plan_fingerprint": plan.get("plan_fingerprint"),
            "decision_fingerprint": _decision_fingerprint(plan, normalized),
            "decision": normalized.get("decision"),
        }
    )


def _safe_scoring_metric_summary(result: Mapping[str, Any] | None) -> dict[str, Any]:
    metrics = dict((result or {}).get("metrics") or {})
    return {
        "compared_records": metrics.get("compared_records"),
        "increased_score_records": metrics.get("increased_score_records"),
        "decreased_score_records": metrics.get("decreased_score_records"),
        "mean_raw_score_delta": metrics.get("mean_raw_score_delta"),
        "mean_bounded_score_delta": metrics.get("mean_bounded_score_delta"),
        "scoring_coverage": metrics.get("scoring_coverage"),
    }


def _safe_fast_lane_summary(result: Mapping[str, Any] | None) -> dict[str, Any]:
    dimensions = list((result or {}).get("dimension_results") or [])
    return {
        "compatible_dimension_count": sum(1 for item in dimensions if isinstance(item, Mapping) and str(item.get("status") or "") == "compatible"),
        "warning_dimension_count": sum(1 for item in dimensions if isinstance(item, Mapping) and str(item.get("status") or "") == "warning"),
        "incompatible_dimension_count": sum(1 for item in dimensions if isinstance(item, Mapping) and str(item.get("status") or "") == "incompatible"),
        "overall_compatibility": (result or {}).get("overall_compatibility"),
        "semantic_loss": (result or {}).get("semantic_loss"),
    }


def _normalize_decision_payload(
    reviewer_identity: str,
    decision: str,
    rationale: str,
    acknowledgements: list[str] | tuple[str, ...] | None,
) -> dict[str, Any]:
    blockers: list[str] = []
    reviewer = str(reviewer_identity or "").strip()
    normalized_decision = str(decision or "").strip()
    normalized_rationale = str(rationale or "").strip()
    ack_items = sorted({str(item or "").strip().lower() for item in list(acknowledgements or []) if str(item or "").strip()})
    if not reviewer:
        blockers.append("reviewer_identity_required")
    if normalized_decision not in DECISIONS:
        blockers.append("unsupported_authorization_decision")
    if not normalized_rationale:
        blockers.append("review_rationale_required")
    if normalized_decision == "authorize_for_later_integration":
        missing = sorted(AUTHORIZE_ACKS.difference(ack_items))
        if missing:
            blockers.extend([f"missing_acknowledgement:{item}" for item in missing])
    elif not ack_items:
        blockers.append("review_acknowledgement_required")
    return {
        "reviewer_identity": reviewer,
        "decision": normalized_decision,
        "rationale": normalized_rationale,
        "acknowledgements": ack_items,
        "blockers": blockers,
    }


def _decision_specific_blockers(plan: Mapping[str, Any], normalized: Mapping[str, Any]) -> list[str]:
    if str(normalized.get("decision") or "") != "authorize_for_later_integration":
        return []
    blockers: list[str] = []
    if str(plan.get("overall_compatibility") or "") != "compatible":
        blockers.append("fast_lane_preview_not_compatible_for_authorization")
    if str(plan.get("semantic_loss") or "") not in {"none", "low_risk"}:
        blockers.append("semantic_loss_blocks_authorization")
    return blockers


def _decision_status(decision: str) -> str:
    return {
        "authorize_for_later_integration": "authorized",
        "reject_integration": "rejected",
        "defer_integration": "deferred",
    }.get(decision, "unknown")


def _plan_current_status(base: Path, plan: Mapping[str, Any]) -> dict[str, Any]:
    current = validate_certified_rule_integration_authorization_eligibility(
        str(plan.get("canonical_rule_id") or ""),
        str(plan.get("scoring_preview_result_id") or ""),
        str(plan.get("fast_lane_preview_result_id") or ""),
        root=base,
    )
    if current.get("blockers"):
        return {"status": str(current.get("status") or "blocked"), "blockers": list(current.get("blockers", []))}
    if str(plan.get("plan_fingerprint") or "") != _plan_fingerprint(current):
        return {"status": "stale", "blockers": ["integration_authorization_plan_fingerprint_mismatch"]}
    return {"status": "current", "blockers": []}


def _result_is_stale(base: Path, result: Mapping[str, Any]) -> bool:
    current = validate_certified_rule_integration_authorization_eligibility(
        str(result.get("canonical_rule_id") or ""),
        str(result.get("scoring_preview_result_id") or ""),
        str(result.get("fast_lane_preview_result_id") or ""),
        root=base,
    )
    if current.get("blockers"):
        return True
    return any(
        str(result.get(key) or "") != str(current.get(key) or "")
        for key in (
            "rule_fingerprint",
            "certification_fingerprint",
            "scoring_preview_result_fingerprint",
            "fast_lane_preview_result_fingerprint",
            "scoring_config_fingerprint",
            "scoring_evaluator_fingerprint",
            "fast_lane_capability_fingerprint",
            "fast_lane_evaluator_fingerprint",
        )
    )


def _find_plan(base: Path, canonical_rule_id: str, scoring_preview_result_id: str, fast_lane_preview_result_id: str) -> dict[str, Any] | None:
    for payload in _load_all(base / PLAN_DIR):
        if (
            str(payload.get("canonical_rule_id") or "") == canonical_rule_id
            and str(payload.get("scoring_preview_result_id") or "") == scoring_preview_result_id
            and str(payload.get("fast_lane_preview_result_id") or "") == fast_lane_preview_result_id
        ):
            return payload
    return None


def _find_result(base: Path, plan_id: str) -> dict[str, Any] | None:
    for payload in _load_all(base / RESULT_DIR):
        if str(payload.get("integration_authorization_plan_id") or "") == plan_id:
            return payload
    return None


def _find_result_by_id(base: Path, result_id: str) -> dict[str, Any] | None:
    payload = analysis_backend._read_json(_result_path(base, result_id))
    return dict(payload) if isinstance(payload, Mapping) else None


def _find_receipt_for_result(base: Path, result_id: str) -> dict[str, Any] | None:
    for payload in _load_all(base / RECEIPT_DIR):
        if str(payload.get("integration_authorization_result_id") or "") == result_id:
            return payload
    return None


def _find_receipt_by_id(base: Path, receipt_id: str | None) -> dict[str, Any] | None:
    if not receipt_id:
        return None
    payload = analysis_backend._read_json(_receipt_path(base, receipt_id))
    return dict(payload) if isinstance(payload, Mapping) else None


def _latest_scoring_result_id(base: Path, canonical_rule_id: str) -> str | None:
    for payload in reversed(_load_all(base / scoring_backend.RESULT_DIR)):
        if str(payload.get("canonical_rule_id") or "") == canonical_rule_id and not scoring_backend._result_is_stale(base, payload):
            return str(payload.get("scoring_preview_result_id") or "") or None
    return None


def _latest_fast_lane_result_id(base: Path, canonical_rule_id: str) -> str | None:
    for payload in reversed(_load_all(base / fast_lane_backend.RESULT_DIR)):
        if str(payload.get("canonical_rule_id") or "") == canonical_rule_id and not fast_lane_backend._result_is_stale(base, payload):
            return str(payload.get("fast_lane_preview_result_id") or "") or None
    return None


def _certification_fingerprint(certification: Mapping[str, Any] | None) -> str:
    if not isinstance(certification, Mapping):
        return ""
    return _hash_payload(
        {
            "certification_receipt_id": certification.get("certification_receipt_id"),
            "rule_id": certification.get("rule_id"),
            "document_id": certification.get("document_id"),
            "source_revision": certification.get("source_revision"),
            "rule_hash": certification.get("rule_hash"),
            "certification_status": certification.get("certification_status"),
        }
    )


def _objective_certification_fingerprint(certification: Mapping[str, Any] | None) -> str:
    if not isinstance(certification, Mapping):
        return ""
    return _hash_payload(
        {
            "certification_receipt_id": certification.get("certification_receipt_id"),
            "rule_id": certification.get("rule_id"),
            "rule_hash": certification.get("rule_hash"),
            "certification_status": certification.get("certification_status"),
        }
    )


def _acceptable_rule_fingerprints(rule: Mapping[str, Any]) -> set[str]:
    return {item for item in {str(rule.get("rule_fingerprint") or ""), _hash_payload(rule)} if item}


def _plan_summary(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "canonical_rule_id": plan.get("canonical_rule_id"),
        "document_id": plan.get("document_id"),
        "source_revision": plan.get("source_revision"),
        "scoring_preview_result_id": plan.get("scoring_preview_result_id"),
        "fast_lane_preview_result_id": plan.get("fast_lane_preview_result_id"),
        "overall_compatibility": plan.get("overall_compatibility"),
        "semantic_loss": plan.get("semantic_loss"),
        "recommended_action": "Record one explicit human authorization decision.",
    }


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in items if str(item)))
