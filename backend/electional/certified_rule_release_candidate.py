"""Qualification-only release-candidate evaluator over authorized certified-rule evidence."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from . import certified_rule_fast_lane_preview as fast_lane_backend
from . import certified_rule_integration_authorization as authorization_backend
from . import certified_rule_scoring_preview as scoring_backend
from . import rule_effectiveness_analysis as analysis_backend
from .canonical_rule_runtime import load_canonical_rule
from .certified_rule_replay_adapter import _rule_has_unresolved_critical_remediation, _rule_pending_supersession
from .document_manifest import load_document_manifest
from .rule_effectiveness_analysis import _ensure_analysis_dirs, _hash_payload, _load_certification_receipt_for_rule
from .source_documents import SOURCE_DOCUMENT_ROOT

PLAN_DIR = "certified_rule_release_candidate_plans"
RESULT_DIR = "certified_rule_release_candidate_results"
RECEIPT_DIR = "certified_rule_release_candidate_receipts"
PLAN_INDEX = "certified_rule_release_candidate_plan_index.json"
RESULT_INDEX = "certified_rule_release_candidate_result_index.json"
RECEIPT_INDEX = "certified_rule_release_candidate_receipt_index.json"
PLAN_SCHEMA = "certified_rule_release_candidate_plan_v1"
RESULT_SCHEMA = "certified_rule_release_candidate_result_v1"
RECEIPT_SCHEMA = "certified_rule_release_candidate_receipt_v1"
QUALIFICATION_SCHEMA_VERSION = "certified_rule_release_candidate_v1"
QUALIFICATION_MODE = "release_candidate_qualification_only"
REQUIRED_CONFIRMATION = "QUALIFY_RELEASE_CANDIDATE"
AUTHORIZED_DECISIONS = {"authorize_for_controlled_integration", "authorize_for_later_integration"}
ALLOWED_ELIGIBILITY_STATUSES = {"eligible", "eligible_with_warnings", "not_eligible", "blocked", "stale", "corrupt", "unknown"}
PUBLIC_FUNCTIONS = [
    "build_certified_rule_release_candidate_workspace",
    "validate_certified_rule_release_candidate_eligibility",
    "build_certified_rule_release_candidate_plan",
    "qualify_certified_rule_release_candidate",
    "load_certified_rule_release_candidate_result",
    "get_certified_rule_release_candidate_health",
    "format_certified_rule_release_candidate_report",
    "get_certified_rule_release_candidate_summary",
]


def build_certified_rule_release_candidate_workspace(
    canonical_rule_id: str,
    integration_authorization_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    bundle = _load_bundle(base, canonical_rule_id, integration_authorization_result_id)
    eligibility = validate_certified_rule_release_candidate_eligibility(canonical_rule_id, integration_authorization_result_id, root=base)
    plan = _find_plan(base, canonical_rule_id, integration_authorization_result_id)
    result = _find_result(base, str((plan or {}).get("release_candidate_plan_id") or ""))
    receipt = _find_receipt_for_result(base, str((result or {}).get("release_candidate_result_id") or ""))
    return {
        "status": "ready_for_planning" if not eligibility.get("blockers") else str(eligibility.get("status") or "blocked"),
        "canonical_rule_id": canonical_rule_id,
        "document_id": eligibility.get("document_id"),
        "source_revision": eligibility.get("source_revision"),
        "rule_status": eligibility.get("rule_status", "unknown"),
        "certification_status": eligibility.get("certification_status", "unknown"),
        "authorization_status": eligibility.get("authorization_status", "missing"),
        "scoring_evidence_status": eligibility.get("scoring_evidence_status", "missing"),
        "compatibility_evidence_status": eligibility.get("compatibility_evidence_status", "missing"),
        "cross_phase_provenance_status": eligibility.get("cross_phase_provenance_status", "unknown"),
        "health_status": eligibility.get("health_status", "unknown"),
        "integration_authorization_result_id": integration_authorization_result_id,
        "scoring_preview_result_id": (bundle["authorization_result"] or {}).get("scoring_preview_result_id"),
        "fast_lane_preview_result_id": (bundle["authorization_result"] or {}).get("fast_lane_preview_result_id"),
        "release_candidate_plan_id": (plan or {}).get("release_candidate_plan_id"),
        "release_candidate_result_id": (result or {}).get("release_candidate_result_id"),
        "release_candidate_receipt_id": (receipt or {}).get("release_candidate_receipt_id"),
        "gate_previews": list(eligibility.get("gate_previews", [])),
        "warnings": list(eligibility.get("warnings", [])),
        "blockers": list(eligibility.get("blockers", [])),
        "recommended_action": "Build the release-candidate qualification plan." if not eligibility.get("blockers") else "Resolve authorization, evidence, lifecycle, or health blockers first.",
    }


def validate_certified_rule_release_candidate_eligibility(
    canonical_rule_id: str,
    integration_authorization_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    bundle = _load_bundle(base, canonical_rule_id, integration_authorization_result_id)
    gates = _evaluate_gates(base, bundle)
    blockers = _aggregate_gate_blockers(gates)
    warnings = _aggregate_gate_warnings(gates)
    status = _eligibility_status(gates)
    return {
        "status": status,
        "canonical_rule_id": canonical_rule_id,
        "document_id": (bundle["rule"] or {}).get("document_id") or (bundle["authorization_result"] or {}).get("document_id"),
        "source_revision": (bundle["rule"] or {}).get("source_revision") or (bundle["authorization_result"] or {}).get("source_revision"),
        "rule_status": (bundle["rule"] or {}).get("status", "missing"),
        "certification_status": (bundle["certification"] or {}).get("certification_status", "missing"),
        "authorization_status": (bundle["authorization_result"] or {}).get("status", "missing"),
        "scoring_evidence_status": (bundle["scoring_result"] or {}).get("status", "missing"),
        "compatibility_evidence_status": (bundle["fast_lane_result"] or {}).get("preview_status", "missing"),
        "cross_phase_provenance_status": _cross_phase_status(gates),
        "health_status": _health_status(gates),
        "gate_previews": gates,
        "warnings": warnings,
        "blockers": blockers,
        "recommended_action": _recommended_action(status),
    }


def build_certified_rule_release_candidate_plan(
    canonical_rule_id: str,
    integration_authorization_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    eligibility = validate_certified_rule_release_candidate_eligibility(canonical_rule_id, integration_authorization_result_id, root=base)
    if eligibility["status"] in {"blocked", "stale", "corrupt", "unknown"}:
        return {
            "status": eligibility["status"],
            "canonical_rule_id": canonical_rule_id,
            "integration_authorization_result_id": integration_authorization_result_id,
            "warnings": list(eligibility.get("warnings", [])),
            "blockers": list(eligibility.get("blockers", [])),
        }
    bundle = _load_bundle(base, canonical_rule_id, integration_authorization_result_id)
    authorization_result = bundle["authorization_result"] or {}
    authorization_receipt = bundle["authorization_receipt"] or {}
    scoring_result = bundle["scoring_result"] or {}
    scoring_receipt = bundle["scoring_receipt"] or {}
    fast_lane_result = bundle["fast_lane_result"] or {}
    fast_lane_receipt = bundle["fast_lane_receipt"] or {}
    rule = bundle["rule"] or {}
    certification = bundle["certification"] or {}
    health = _health_payload(bundle)
    plan = {
        "schema_version": PLAN_SCHEMA,
        "qualification_schema_version": QUALIFICATION_SCHEMA_VERSION,
        "release_candidate_plan_id": _plan_id(bundle),
        "canonical_rule_id": canonical_rule_id,
        "document_id": rule.get("document_id"),
        "source_revision": rule.get("source_revision"),
        "rule_schema_version": "canonical_mutable_rule_v1",
        "rule_fingerprint": rule.get("rule_fingerprint"),
        "certification_receipt_id": certification.get("certification_receipt_id"),
        "certification_fingerprint": _certification_fingerprint(certification),
        "integration_authorization_result_id": integration_authorization_result_id,
        "integration_authorization_receipt_id": authorization_receipt.get("integration_authorization_receipt_id"),
        "integration_authorization_result_fingerprint": authorization_result.get("result_fingerprint"),
        "reviewer_identity": authorization_result.get("reviewer_identity"),
        "authorization_decision": authorization_result.get("decision"),
        "scoring_preview_result_id": authorization_result.get("scoring_preview_result_id"),
        "scoring_preview_receipt_id": scoring_receipt.get("scoring_preview_receipt_id"),
        "scoring_preview_result_fingerprint": scoring_result.get("result_fingerprint"),
        "scoring_config_fingerprint": scoring_result.get("scoring_config_fingerprint"),
        "scoring_evaluator_fingerprint": scoring_result.get("scoring_evaluator_fingerprint"),
        "fast_lane_preview_result_id": authorization_result.get("fast_lane_preview_result_id"),
        "fast_lane_preview_receipt_id": fast_lane_receipt.get("fast_lane_preview_receipt_id"),
        "fast_lane_preview_result_fingerprint": fast_lane_result.get("result_fingerprint"),
        "fast_lane_contract_id": fast_lane_result.get("fast_lane_contract_id"),
        "fast_lane_contract_version": fast_lane_result.get("fast_lane_contract_version"),
        "fast_lane_capability_fingerprint": fast_lane_result.get("fast_lane_capability_fingerprint"),
        "compatibility_evaluator_fingerprint": fast_lane_result.get("compatibility_evaluator_fingerprint"),
        "evidence_health_summaries": health,
        "gate_preview": list(eligibility.get("gate_previews", [])),
        "qualification_mode": QUALIFICATION_MODE,
        "plan_fingerprint": _plan_fingerprint(bundle, eligibility),
        "warnings": list(eligibility.get("warnings", [])),
        "blockers": list(eligibility.get("blockers", [])),
    }
    path = _plan_path(base, str(plan["release_candidate_plan_id"]))
    existing = analysis_backend._read_json(path)
    if isinstance(existing, Mapping):
        if str(existing.get("plan_fingerprint") or "") == str(plan.get("plan_fingerprint") or ""):
            return {"status": "planned", "release_candidate_plan_id": plan["release_candidate_plan_id"], "writes_performed": 0, **_plan_summary(plan)}
        return {"status": "corrupt", "blockers": ["release_candidate_plan_divergence"], "warnings": []}
    before_plan = analysis_backend._read_json(path)
    before_index = analysis_backend._read_json(base / "indexes" / PLAN_INDEX)
    try:
        analysis_backend._atomic_write_json(path, plan)
        _update_plan_index(base)
    except Exception:
        analysis_backend._restore_json(path, before_plan)
        analysis_backend._restore_json(base / "indexes" / PLAN_INDEX, before_index)
        return {"status": "corrupt", "blockers": ["release_candidate_plan_write_failure"], "warnings": []}
    return {"status": "planned", "release_candidate_plan_id": plan["release_candidate_plan_id"], "writes_performed": 1, **_plan_summary(plan)}


def qualify_certified_rule_release_candidate(
    release_candidate_plan_id: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    if confirmation != REQUIRED_CONFIRMATION:
        return {"status": "blocked", "release_candidate_plan_id": release_candidate_plan_id, "blockers": ["release_candidate_confirmation_required"], "warnings": []}
    plan = analysis_backend._read_json(_plan_path(base, release_candidate_plan_id))
    if not isinstance(plan, Mapping):
        return {"status": "blocked", "release_candidate_plan_id": release_candidate_plan_id, "blockers": ["release_candidate_plan_missing"], "warnings": []}
    if str(plan.get("qualification_mode") or "") != QUALIFICATION_MODE:
        return {"status": "corrupt", "release_candidate_plan_id": release_candidate_plan_id, "blockers": ["release_candidate_plan_mode_invalid"], "warnings": []}
    bundle = _load_bundle(base, str(plan.get("canonical_rule_id") or ""), str(plan.get("integration_authorization_result_id") or ""))
    eligibility = validate_certified_rule_release_candidate_eligibility(str(plan.get("canonical_rule_id") or ""), str(plan.get("integration_authorization_result_id") or ""), root=base)
    current_plan_fingerprint = _plan_fingerprint(bundle, eligibility)
    if str(plan.get("plan_fingerprint") or "") != current_plan_fingerprint:
        return {"status": "stale", "release_candidate_plan_id": release_candidate_plan_id, "blockers": ["release_candidate_plan_fingerprint_mismatch"], "warnings": []}
    existing = _find_result(base, release_candidate_plan_id)
    if isinstance(existing, Mapping) and not _result_is_stale(base, existing):
        receipt = _find_receipt_for_result(base, str(existing.get("release_candidate_result_id") or ""))
        if isinstance(receipt, Mapping) and str(receipt.get("result_fingerprint") or "") == str(existing.get("result_fingerprint") or ""):
            return {
                "status": "already_qualified",
                "release_candidate_plan_id": release_candidate_plan_id,
                "release_candidate_result_id": existing.get("release_candidate_result_id"),
                "release_candidate_receipt_id": receipt.get("release_candidate_receipt_id"),
                "writes_performed": 0,
            }
        return {"status": "corrupt", "release_candidate_plan_id": release_candidate_plan_id, "blockers": ["release_candidate_receipt_divergence"], "warnings": []}
    gate_results = list(eligibility.get("gate_previews", []))
    digest = _evidence_digest(bundle)
    status = _qualification_status(gate_results)
    blockers = _aggregate_gate_blockers(gate_results)
    warnings = _aggregate_gate_warnings(gate_results)
    result_id = _result_id(release_candidate_plan_id)
    result = {
        "schema_version": RESULT_SCHEMA,
        "qualification_schema_version": QUALIFICATION_SCHEMA_VERSION,
        "release_candidate_result_id": result_id,
        "release_candidate_plan_id": release_candidate_plan_id,
        "canonical_rule_id": plan.get("canonical_rule_id"),
        "document_id": plan.get("document_id"),
        "source_revision": plan.get("source_revision"),
        "rule_schema_version": plan.get("rule_schema_version"),
        "rule_fingerprint": plan.get("rule_fingerprint"),
        "certification_receipt_id": plan.get("certification_receipt_id"),
        "certification_fingerprint": plan.get("certification_fingerprint"),
        "integration_authorization_result_id": plan.get("integration_authorization_result_id"),
        "integration_authorization_receipt_id": plan.get("integration_authorization_receipt_id"),
        "integration_authorization_result_fingerprint": plan.get("integration_authorization_result_fingerprint"),
        "scoring_preview_result_id": plan.get("scoring_preview_result_id"),
        "scoring_preview_receipt_id": plan.get("scoring_preview_receipt_id"),
        "scoring_preview_result_fingerprint": plan.get("scoring_preview_result_fingerprint"),
        "scoring_config_fingerprint": plan.get("scoring_config_fingerprint"),
        "scoring_evaluator_fingerprint": plan.get("scoring_evaluator_fingerprint"),
        "fast_lane_preview_result_id": plan.get("fast_lane_preview_result_id"),
        "fast_lane_preview_receipt_id": plan.get("fast_lane_preview_receipt_id"),
        "fast_lane_preview_result_fingerprint": plan.get("fast_lane_preview_result_fingerprint"),
        "fast_lane_contract_id": plan.get("fast_lane_contract_id"),
        "fast_lane_contract_version": plan.get("fast_lane_contract_version"),
        "fast_lane_capability_fingerprint": plan.get("fast_lane_capability_fingerprint"),
        "compatibility_evaluator_fingerprint": plan.get("compatibility_evaluator_fingerprint"),
        "qualification_gate_results": gate_results,
        "evidence_digest": digest,
        "qualification_status": status,
        "warnings": warnings,
        "blockers": blockers,
        "release_candidate_scope": _scope_payload(),
        "result_fingerprint": _result_fingerprint(plan, gate_results, digest, status),
    }
    receipt_id = _receipt_id(result_id)
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "release_candidate_receipt_id": receipt_id,
        "release_candidate_result_id": result_id,
        "release_candidate_plan_id": release_candidate_plan_id,
        "canonical_rule_id": plan.get("canonical_rule_id"),
        "document_id": plan.get("document_id"),
        "source_revision": plan.get("source_revision"),
        "integration_authorization_result_id": plan.get("integration_authorization_result_id"),
        "scoring_preview_result_id": plan.get("scoring_preview_result_id"),
        "fast_lane_preview_result_id": plan.get("fast_lane_preview_result_id"),
        "qualification_status": status,
        "result_fingerprint": result.get("result_fingerprint"),
        "gate_summary": [{"gate_name": item.get("gate_name"), "status": item.get("status")} for item in gate_results],
        "release_candidate_scope_summary": _scope_summary(),
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
        return {"status": "corrupt", "release_candidate_plan_id": release_candidate_plan_id, "blockers": ["release_candidate_result_write_failure"], "warnings": []}
    return {
        "status": status,
        "release_candidate_plan_id": release_candidate_plan_id,
        "release_candidate_result_id": result_id,
        "release_candidate_receipt_id": receipt_id,
        "writes_performed": 2,
    }


def load_certified_rule_release_candidate_result(
    release_candidate_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    result = analysis_backend._read_json(_result_path(base, release_candidate_result_id))
    if not isinstance(result, Mapping):
        return {"status": "not_found", "release_candidate_result_id": release_candidate_result_id, "release_candidate_result": None, "warnings": []}
    payload = dict(result)
    payload["stale"] = _result_is_stale(base, payload)
    return {"status": "loaded", "release_candidate_result_id": release_candidate_result_id, "release_candidate_result": payload, "warnings": []}


def get_certified_rule_release_candidate_health(
    release_candidate_plan_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    plans = _load_all(base / PLAN_DIR)
    results = _load_all(base / RESULT_DIR)
    receipts = _load_all(base / RECEIPT_DIR)
    if release_candidate_plan_id:
        plans = [item for item in plans if str(item.get("release_candidate_plan_id") or "") == release_candidate_plan_id]
        results = [item for item in results if str(item.get("release_candidate_plan_id") or "") == release_candidate_plan_id]
        receipts = [item for item in receipts if str(item.get("release_candidate_plan_id") or "") == release_candidate_plan_id]
    if not plans and not results and not receipts:
        return {"status": "empty", "release_candidate_plan_count": 0, "release_candidate_result_count": 0, "release_candidate_receipt_count": 0, "recommended_action": "Build one release-candidate qualification plan."}
    warnings: list[str] = []
    stale_count = 0
    for result in results:
        if _result_is_stale(base, result):
            stale_count += 1
        receipt = _find_receipt_for_result(base, str(result.get("release_candidate_result_id") or ""))
        if not isinstance(receipt, Mapping):
            warnings.append("release_candidate_receipt_missing")
        elif str(receipt.get("result_fingerprint") or "") != str(result.get("result_fingerprint") or ""):
            warnings.append("release_candidate_receipt_fingerprint_mismatch")
    status = "corrupt" if any("mismatch" in item for item in warnings) else "stale" if stale_count else "warning" if warnings else "healthy"
    return {
        "status": status,
        "release_candidate_plan_count": len(plans),
        "release_candidate_result_count": len(results),
        "release_candidate_receipt_count": len(receipts),
        "stale_release_candidate_count": stale_count,
        "warnings": _dedupe(warnings),
        "recommended_action": "Rebuild the release-candidate qualification plan against current evidence." if stale_count else "Release-candidate qualification health is good.",
    }


def format_certified_rule_release_candidate_report(
    release_candidate_result_id: str | None = None,
    release_candidate_receipt_id: str | None = None,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    base = _ensure_dirs(root)
    receipt = _find_receipt_by_id(base, release_candidate_receipt_id) if release_candidate_receipt_id else None
    result = _find_result_by_id(base, release_candidate_result_id or str((receipt or {}).get("release_candidate_result_id") or ""))
    if not isinstance(result, Mapping):
        return "Certified Rule Release Candidate Qualification\n\nStatus: not_found"
    digest = dict(result.get("evidence_digest") or {})
    lines = [
        "Certified Rule Release Candidate Qualification",
        "",
        f"Qualification Status: {result.get('qualification_status')}",
        f"Canonical Rule ID: {result.get('canonical_rule_id')}",
        f"Document ID: {result.get('document_id')}",
        f"Source Revision: {result.get('source_revision')}",
        f"Authorization Decision: {digest.get('authorization_decision', 'unknown')}",
        f"Authorization Reviewer: {digest.get('reviewer_identity', 'unknown')}",
        f"Scoring Status: {digest.get('scoring_status', 'unknown')}",
        f"Scoring Coverage: {digest.get('scoring_coverage', 'null')}",
        f"Fast Lane Status: {digest.get('fast_lane_status', 'unknown')}",
        f"Overall Compatibility: {digest.get('overall_compatibility', 'unknown')}",
        f"Semantic Loss: {digest.get('semantic_loss', 'unknown')}",
        f"Stale: {'Yes' if _result_is_stale(base, result) else 'No'}",
        f"Warnings: {', '.join(str(item) for item in result.get('warnings', [])) or 'none'}",
        f"Blockers: {', '.join(str(item) for item in result.get('blockers', [])) or 'none'}",
        "Execution: no activation, Fast Lane execution, or production scoring was performed.",
        "Safety: qualification is evidence-only and invalidates on lifecycle or fingerprint drift.",
    ]
    if not public_safe:
        lines.append(f"Result Fingerprint: {result.get('result_fingerprint')}")
    return "\n".join(lines)


def get_certified_rule_release_candidate_summary(
    release_candidate_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    result = _find_result_by_id(base, release_candidate_result_id)
    if not isinstance(result, Mapping):
        return {"status": "not_found", "recommended_action": "Run one release-candidate qualification."}
    digest = dict(result.get("evidence_digest") or {})
    return {
        "status": result.get("qualification_status"),
        "canonical_rule_id": result.get("canonical_rule_id"),
        "document_id": result.get("document_id"),
        "source_revision": result.get("source_revision"),
        "authorization_status": digest.get("authorization_status"),
        "scoring_status": digest.get("scoring_status"),
        "fast_lane_status": digest.get("fast_lane_status"),
        "overall_compatibility": digest.get("overall_compatibility"),
        "semantic_loss": digest.get("semantic_loss"),
        "stale": _result_is_stale(base, result),
        "recommended_action": _recommended_action(str(result.get("qualification_status") or "unknown")),
    }


def _ensure_dirs(root: Path | str) -> Path:
    base = _ensure_analysis_dirs(root)
    for folder in (PLAN_DIR, RESULT_DIR, RECEIPT_DIR, "indexes"):
        (base / folder).mkdir(parents=True, exist_ok=True)
    defaults = (
        (PLAN_INDEX, "certified_rule_release_candidate_plan_index_v1"),
        (RESULT_INDEX, "certified_rule_release_candidate_result_index_v1"),
        (RECEIPT_INDEX, "certified_rule_release_candidate_receipt_index_v1"),
    )
    for name, schema in defaults:
        path = base / "indexes" / name
        if not path.exists():
            analysis_backend._atomic_write_json(path, {"schema_version": schema, "items": [], "updated_at_utc": analysis_backend._now()})
    return base


def _load_bundle(base: Path, canonical_rule_id: str, integration_authorization_result_id: str) -> dict[str, Any]:
    rule_loaded = load_canonical_rule(canonical_rule_id, require_active=False, root=base)
    rule = rule_loaded.get("rule") if isinstance(rule_loaded.get("rule"), Mapping) else None
    certification = _load_certification_receipt_for_rule(base, canonical_rule_id)
    manifest = load_document_manifest(str((rule or {}).get("document_id") or ""), root=base).get("manifest") if isinstance(rule, Mapping) else None
    authorization_loaded = authorization_backend.load_certified_rule_integration_authorization_result(integration_authorization_result_id, root=base)
    authorization_result = authorization_loaded.get("integration_authorization_result")
    authorization_receipt = authorization_backend._find_receipt_for_result(base, integration_authorization_result_id) if isinstance(authorization_result, Mapping) else None
    scoring_result = scoring_receipt = None
    fast_lane_result = fast_lane_receipt = None
    if isinstance(authorization_result, Mapping):
        scoring_loaded = scoring_backend.load_certified_rule_scoring_preview_result(str(authorization_result.get("scoring_preview_result_id") or ""), root=base)
        scoring_result = scoring_loaded.get("scoring_preview_result")
        scoring_receipt = scoring_backend._find_receipt_for_result(base, str(authorization_result.get("scoring_preview_result_id") or "")) if isinstance(scoring_result, Mapping) else None
        fast_loaded = fast_lane_backend.load_certified_rule_fast_lane_preview_result(str(authorization_result.get("fast_lane_preview_result_id") or ""), root=base)
        fast_lane_result = fast_loaded.get("fast_lane_preview_result")
        fast_lane_receipt = fast_lane_backend._find_receipt_for_result(base, str(authorization_result.get("fast_lane_preview_result_id") or "")) if isinstance(fast_lane_result, Mapping) else None
    return {
        "rule": rule,
        "rule_loaded": rule_loaded,
        "certification": certification,
        "manifest": manifest,
        "authorization_result": authorization_result,
        "authorization_receipt": authorization_receipt,
        "scoring_result": scoring_result,
        "scoring_receipt": scoring_receipt,
        "fast_lane_result": fast_lane_result,
        "fast_lane_receipt": fast_lane_receipt,
    }


def _evaluate_gates(base: Path, bundle: Mapping[str, Any]) -> list[dict[str, Any]]:
    rule = bundle.get("rule") if isinstance(bundle.get("rule"), Mapping) else {}
    certification = bundle.get("certification") if isinstance(bundle.get("certification"), Mapping) else {}
    manifest = bundle.get("manifest") if isinstance(bundle.get("manifest"), Mapping) else {}
    authorization_result = bundle.get("authorization_result") if isinstance(bundle.get("authorization_result"), Mapping) else {}
    authorization_receipt = bundle.get("authorization_receipt") if isinstance(bundle.get("authorization_receipt"), Mapping) else {}
    scoring_result = bundle.get("scoring_result") if isinstance(bundle.get("scoring_result"), Mapping) else {}
    scoring_receipt = bundle.get("scoring_receipt") if isinstance(bundle.get("scoring_receipt"), Mapping) else {}
    fast_lane_result = bundle.get("fast_lane_result") if isinstance(bundle.get("fast_lane_result"), Mapping) else {}
    fast_lane_receipt = bundle.get("fast_lane_receipt") if isinstance(bundle.get("fast_lane_receipt"), Mapping) else {}
    auth_health = authorization_backend.get_certified_rule_integration_authorization_health(str(authorization_result.get("integration_authorization_plan_id") or "")) if authorization_result else {"status": "empty"}
    scoring_health = scoring_backend.get_certified_rule_scoring_preview_health(str(scoring_result.get("scoring_preview_plan_id") or "")) if scoring_result else {"status": "empty"}
    fast_health = fast_lane_backend.get_certified_rule_fast_lane_preview_health(str(fast_lane_result.get("fast_lane_preview_plan_id") or "")) if fast_lane_result else {"status": "empty"}

    gates: list[dict[str, Any]] = []
    gates.append(_gate("rule lifecycle", _pass() if rule and str(rule.get("status") or "") == "active" else _blocked("canonical_rule_not_active"), {"rule_status": rule.get("status", "missing")}))
    cert_match = str(certification.get("rule_hash") or "") in _acceptable_rule_fingerprints(rule) if certification else False
    gates.append(_gate("certification currency", _pass() if certification and str(certification.get("certification_status") or "") == "completed" and cert_match else _blocked("rule_certification_missing_or_stale" if not certification or str(certification.get("certification_status") or "") != "completed" else "rule_certification_hash_mismatch"), {"certification_status": certification.get("certification_status", "missing")}))
    source_ok = manifest and str(manifest.get("source_revision") or "") == str(rule.get("source_revision") or "")
    gates.append(_gate("document and source revision", _pass() if manifest and source_ok and str(authorization_result.get("document_id") or "") == str(rule.get("document_id") or "") and str(authorization_result.get("source_revision") or "") == str(rule.get("source_revision") or "") else _stale("source_revision_not_current" if manifest else "document_manifest_missing"), {"document_id": rule.get("document_id"), "source_revision": rule.get("source_revision")}))
    remediation_blocked = bool(_rule_has_unresolved_critical_remediation(base, rule))
    gates.append(_gate("remediation state", _pass() if not remediation_blocked else _failed("rule_has_unresolved_critical_remediation"), {"critical_remediation_blocked": remediation_blocked}))
    rollback_pending = _rollback_pending(rule)
    if rollback_pending:
        rollback_status = _blocked("rule_has_pending_rollback")
    elif _rule_pending_supersession(base, str(rule.get("rule_id") or "")):
        rollback_status = _blocked("rule_pending_supersession")
    else:
        rollback_status = _pass()
    gates.append(_gate("rollback and supersession state", rollback_status, {"pending_rollback": rollback_pending, "pending_supersession": bool(_rule_pending_supersession(base, str(rule.get("rule_id") or "")))}))
    auth_ok = authorization_result and authorization_receipt and str(authorization_result.get("status") or "") == "authorized" and str(authorization_result.get("decision") or "") in AUTHORIZED_DECISIONS and not bool(authorization_result.get("stale"))
    auth_gate = _pass()
    auth_warnings: list[str] = []
    auth_blockers: list[str] = []
    if not authorization_result:
        auth_gate = _blocked("integration_authorization_result_missing")
    elif not authorization_receipt:
        auth_gate = _blocked("integration_authorization_receipt_missing")
    elif str(authorization_receipt.get("result_fingerprint") or "") != str(authorization_result.get("result_fingerprint") or ""):
        auth_gate = _corrupt("integration_authorization_receipt_fingerprint_mismatch")
    elif str(authorization_result.get("status") or "") != "authorized":
        auth_gate = _failed("integration_authorization_not_authorized")
    elif str(authorization_result.get("decision") or "") not in AUTHORIZED_DECISIONS:
        auth_gate = _failed("integration_authorization_decision_not_authorizing")
    elif bool(authorization_result.get("stale")):
        auth_gate = _stale("integration_authorization_result_stale")
    gates.append(_gate("Phase 9R authorization validity", auth_gate, {"authorization_status": authorization_result.get("status", "missing"), "authorization_decision": authorization_result.get("decision", "missing")}, auth_blockers, auth_warnings))
    p9p_gate = _pass()
    if not scoring_result:
        p9p_gate = _blocked("scoring_preview_result_missing")
    elif not scoring_receipt:
        p9p_gate = _blocked("scoring_preview_receipt_missing")
    elif str(scoring_receipt.get("result_fingerprint") or "") != str(scoring_result.get("result_fingerprint") or ""):
        p9p_gate = _corrupt("scoring_preview_receipt_fingerprint_mismatch")
    elif bool(scoring_result.get("stale")):
        p9p_gate = _stale("scoring_preview_result_stale")
    elif str(authorization_result.get("scoring_preview_result_id") or "") != str(scoring_result.get("scoring_preview_result_id") or ""):
        p9p_gate = _failed("authorized_scoring_preview_id_mismatch")
    elif str(authorization_result.get("scoring_preview_result_fingerprint") or "") != str(scoring_result.get("result_fingerprint") or ""):
        p9p_gate = _failed("authorized_scoring_preview_fingerprint_mismatch")
    gates.append(_gate("Phase 9P identity and receipt integrity", p9p_gate, {"scoring_status": scoring_result.get("status", "missing") if scoring_result else "missing"}))
    metrics = dict(scoring_result.get("metrics") or {}) if scoring_result else {}
    p9p_complete = _pass()
    if str(scoring_result.get("status") or "") != "completed":
        p9p_complete = _failed("scoring_preview_status_not_completed")
    elif int(metrics.get("total_phase_9o_records") or 0) <= 0:
        p9p_complete = _failed("scoring_total_record_count_invalid")
    elif int(metrics.get("compared_records") or 0) <= 0:
        p9p_complete = _failed("scoring_compared_record_count_invalid")
    elif int(metrics.get("scoreable_records") or 0) <= 0:
        p9p_complete = _failed("scoring_scoreable_record_count_invalid")
    elif int(metrics.get("unsupported_records") or 0) != 0:
        p9p_complete = _failed("scoring_unsupported_records_present")
    elif int(metrics.get("scoring_error_records") or 0) != 0:
        p9p_complete = _failed("scoring_error_records_present")
    elif metrics.get("scoring_coverage") in {None, 0, 0.0}:
        p9p_complete = _failed("scoring_coverage_invalid")
    gates.append(_gate("Phase 9P scoring completeness", p9p_complete, {"compared_records": metrics.get("compared_records"), "scoreable_records": metrics.get("scoreable_records"), "unsupported_records": metrics.get("unsupported_records"), "scoring_error_records": metrics.get("scoring_error_records"), "scoring_coverage": metrics.get("scoring_coverage")}))
    p9q_gate = _pass()
    if not fast_lane_result:
        p9q_gate = _blocked("fast_lane_preview_result_missing")
    elif not fast_lane_receipt:
        p9q_gate = _blocked("fast_lane_preview_receipt_missing")
    elif str(fast_lane_receipt.get("result_fingerprint") or "") != str(fast_lane_result.get("result_fingerprint") or ""):
        p9q_gate = _corrupt("fast_lane_preview_receipt_fingerprint_mismatch")
    elif bool(fast_lane_result.get("stale")):
        p9q_gate = _stale("fast_lane_preview_result_stale")
    elif str(authorization_result.get("fast_lane_preview_result_id") or "") != str(fast_lane_result.get("fast_lane_preview_result_id") or ""):
        p9q_gate = _failed("authorized_fast_lane_preview_id_mismatch")
    elif str(authorization_result.get("fast_lane_preview_result_fingerprint") or "") != str(fast_lane_result.get("result_fingerprint") or ""):
        p9q_gate = _failed("authorized_fast_lane_preview_fingerprint_mismatch")
    gates.append(_gate("Phase 9Q identity and receipt integrity", p9q_gate, {"fast_lane_status": fast_lane_result.get("preview_status", "missing") if fast_lane_result else "missing"}))
    dims = list(fast_lane_result.get("dimension_results") or []) if fast_lane_result else []
    incompatible_dimensions = [item for item in dims if isinstance(item, Mapping) and str(item.get("status") or "") == "incompatible"]
    p9q_complete = _pass()
    p9q_warnings: list[str] = []
    if str(fast_lane_result.get("preview_status") or "") not in {"completed", "completed_with_warnings"}:
        p9q_complete = _failed("fast_lane_preview_status_invalid")
    elif str(fast_lane_result.get("overall_compatibility") or "") not in {"compatible", "compatible_with_warnings"}:
        p9q_complete = _failed("fast_lane_overall_compatibility_invalid")
    elif str(fast_lane_result.get("semantic_loss") or "") != "none":
        p9q_complete = _failed("fast_lane_semantic_loss_not_none")
    elif incompatible_dimensions:
        p9q_complete = _failed("fast_lane_incompatible_dimension_present")
    elif list(fast_lane_result.get("blockers", []) or []):
        p9q_complete = _failed("fast_lane_blockers_present")
    elif str(fast_lane_result.get("overall_compatibility") or "") == "compatible_with_warnings" or str(fast_lane_result.get("preview_status") or "") == "completed_with_warnings" or list(fast_lane_result.get("warnings", []) or []):
        p9q_complete = _warn("fast_lane_non_blocking_warnings_present")
        p9q_warnings = list(fast_lane_result.get("warnings", []) or [])
    gates.append(_gate("Phase 9Q compatibility completeness", p9q_complete, {"overall_compatibility": fast_lane_result.get("overall_compatibility"), "semantic_loss": fast_lane_result.get("semantic_loss"), "incompatible_dimension_count": len(incompatible_dimensions), "blocker_count": len(list(fast_lane_result.get("blockers", []) or []))}, warnings=p9q_warnings))
    cross_gate = _pass()
    if scoring_result and str(scoring_result.get("document_id") or "") != str(rule.get("document_id") or ""):
        cross_gate = _failed("scoring_document_mismatch")
    elif fast_lane_result and str(fast_lane_result.get("document_id") or "") != str(rule.get("document_id") or ""):
        cross_gate = _failed("fast_lane_document_mismatch")
    elif authorization_result and str(authorization_result.get("rule_fingerprint") or "") not in _acceptable_rule_fingerprints(rule):
        cross_gate = _failed("authorization_rule_fingerprint_mismatch")
    gates.append(_gate("cross-phase fingerprint consistency", cross_gate, {"rule_fingerprint": rule.get("rule_fingerprint"), "authorization_rule_fingerprint": authorization_result.get("rule_fingerprint"), "scoring_rule_fingerprint": scoring_result.get("rule_fingerprint"), "fast_lane_rule_fingerprint": fast_lane_result.get("rule_fingerprint")}))
    mutation_gate = _pass()
    mutation_codes = []
    if "production_state_mutation_detected" in list(scoring_result.get("blockers", []) or []):
        mutation_codes.append("scoring_preview_mutation_detected")
    if "production_state_mutation_detected" in list(fast_lane_result.get("blockers", []) or []):
        mutation_codes.append("fast_lane_preview_mutation_detected")
    if "mutation" in str(authorization_result.get("status") or ""):
        mutation_codes.append("integration_authorization_mutation_detected")
    if mutation_codes:
        mutation_gate = {"status": "failed", "blockers": mutation_codes, "warnings": []}
    gates.append(_gate("mutation safety", mutation_gate, {"mutation_codes": mutation_codes}))
    health_gate = _pass()
    health_warnings: list[str] = []
    for name, payload in (("authorization", auth_health), ("scoring", scoring_health), ("fast_lane", fast_health)):
        status = str(payload.get("status") or "unknown")
        if status in {"blocked", "stale", "corrupt"}:
            health_gate = _blocked(f"{name}_health_{status}")
            break
        if status == "warning":
            health_warnings.extend([f"{name}:{item}" for item in list(payload.get("warnings", []) or [])])
    if health_gate["status"] == "passed" and health_warnings:
        health_gate = _warn("non_blocking_evidence_health_warnings")
    gates.append(_gate("evidence health", health_gate, {"authorization_health": auth_health.get("status"), "scoring_health": scoring_health.get("status"), "fast_lane_health": fast_health.get("status")}, warnings=health_warnings))
    gates.append(_gate("release-candidate scope", _pass(), _scope_summary()))
    return gates


def _gate(name: str, outcome: Mapping[str, Any], evidence: Mapping[str, Any], blockers: list[str] | None = None, warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "gate_name": name,
        "status": outcome.get("status", "unknown"),
        "required": True,
        "evidence_summary": dict(evidence),
        "blocker_codes": list(blockers if blockers is not None else outcome.get("blockers", [])),
        "warnings": list(warnings if warnings is not None else outcome.get("warnings", [])),
    }


def _pass() -> dict[str, Any]:
    return {"status": "passed", "blockers": [], "warnings": []}


def _warn(code: str) -> dict[str, Any]:
    return {"status": "passed_with_warning", "blockers": [], "warnings": [code]}


def _failed(code: str) -> dict[str, Any]:
    return {"status": "failed", "blockers": [code], "warnings": []}


def _blocked(code: str) -> dict[str, Any]:
    return {"status": "blocked", "blockers": [code], "warnings": []}


def _stale(code: str) -> dict[str, Any]:
    return {"status": "stale", "blockers": [code], "warnings": []}


def _corrupt(code: str) -> dict[str, Any]:
    return {"status": "unknown", "blockers": [code], "warnings": []}


def _eligibility_status(gates: list[Mapping[str, Any]]) -> str:
    statuses = [str(item.get("status") or "unknown") for item in gates]
    if "unknown" in statuses:
        return "corrupt"
    if "stale" in statuses:
        return "stale"
    if "blocked" in statuses:
        return "blocked"
    if any(status == "failed" for status in statuses):
        return "not_eligible"
    if any(status == "passed_with_warning" for status in statuses):
        return "eligible_with_warnings"
    return "eligible"


def _qualification_status(gates: list[Mapping[str, Any]]) -> str:
    statuses = [str(item.get("status") or "unknown") for item in gates]
    mutation = any("mutation" in code for item in gates for code in list(item.get("blocker_codes", []) or []))
    if mutation:
        return "mutation_detected"
    if "unknown" in statuses:
        return "corrupt"
    if "stale" in statuses:
        return "stale"
    if "blocked" in statuses:
        return "blocked"
    if any(status == "failed" for status in statuses):
        return "not_qualified"
    if any(status == "passed_with_warning" for status in statuses):
        return "qualified_with_warnings"
    return "qualified"


def _aggregate_gate_blockers(gates: list[Mapping[str, Any]]) -> list[str]:
    items: list[str] = []
    for gate in gates:
        items.extend([str(item) for item in list(gate.get("blocker_codes", []) or []) if str(item)])
    return _dedupe(items)


def _aggregate_gate_warnings(gates: list[Mapping[str, Any]]) -> list[str]:
    items: list[str] = []
    for gate in gates:
        items.extend([str(item) for item in list(gate.get("warnings", []) or []) if str(item)])
    return _dedupe(items)


def _cross_phase_status(gates: list[Mapping[str, Any]]) -> str:
    for gate in gates:
        if str(gate.get("gate_name") or "") == "cross-phase fingerprint consistency":
            return str(gate.get("status") or "unknown")
    return "unknown"


def _health_status(gates: list[Mapping[str, Any]]) -> str:
    for gate in gates:
        if str(gate.get("gate_name") or "") == "evidence health":
            return str(gate.get("status") or "unknown")
    return "unknown"


def _health_payload(bundle: Mapping[str, Any]) -> dict[str, Any]:
    authorization_result = bundle.get("authorization_result") if isinstance(bundle.get("authorization_result"), Mapping) else {}
    scoring_result = bundle.get("scoring_result") if isinstance(bundle.get("scoring_result"), Mapping) else {}
    fast_lane_result = bundle.get("fast_lane_result") if isinstance(bundle.get("fast_lane_result"), Mapping) else {}
    return {
        "authorization_health": authorization_backend.get_certified_rule_integration_authorization_health(str(authorization_result.get("integration_authorization_plan_id") or "")),
        "scoring_health": scoring_backend.get_certified_rule_scoring_preview_health(str(scoring_result.get("scoring_preview_plan_id") or "")),
        "fast_lane_health": fast_lane_backend.get_certified_rule_fast_lane_preview_health(str(fast_lane_result.get("fast_lane_preview_plan_id") or "")),
    }


def _evidence_digest(bundle: Mapping[str, Any]) -> dict[str, Any]:
    authorization_result = bundle.get("authorization_result") if isinstance(bundle.get("authorization_result"), Mapping) else {}
    scoring_result = bundle.get("scoring_result") if isinstance(bundle.get("scoring_result"), Mapping) else {}
    fast_lane_result = bundle.get("fast_lane_result") if isinstance(bundle.get("fast_lane_result"), Mapping) else {}
    scoring_metrics = dict(scoring_result.get("metrics") or {})
    dimensions = list(fast_lane_result.get("dimension_results") or [])
    return {
        "reviewer_identity": authorization_result.get("reviewer_identity"),
        "authorization_decision": authorization_result.get("decision"),
        "authorization_status": authorization_result.get("status"),
        "authorization_result_fingerprint": authorization_result.get("result_fingerprint"),
        "scoring_status": scoring_result.get("status"),
        "total_records": scoring_metrics.get("total_phase_9o_records"),
        "scoreable_records": scoring_metrics.get("scoreable_records"),
        "compared_records": scoring_metrics.get("compared_records"),
        "unsupported_records": scoring_metrics.get("unsupported_records"),
        "scoring_error_records": scoring_metrics.get("scoring_error_records"),
        "scoring_coverage": scoring_metrics.get("scoring_coverage"),
        "scoring_config_id": scoring_result.get("scoring_config_id"),
        "mean_score_delta": scoring_metrics.get("mean_bounded_score_delta", scoring_metrics.get("mean_raw_score_delta")),
        "median_score_delta": scoring_metrics.get("median_bounded_score_delta", scoring_metrics.get("median_raw_score_delta")),
        "scoring_result_fingerprint": scoring_result.get("result_fingerprint"),
        "fast_lane_status": fast_lane_result.get("preview_status"),
        "overall_compatibility": fast_lane_result.get("overall_compatibility"),
        "semantic_loss": fast_lane_result.get("semantic_loss"),
        "compatible_dimension_count": sum(1 for item in dimensions if isinstance(item, Mapping) and str(item.get("status") or "") == "compatible"),
        "warning_dimension_count": sum(1 for item in dimensions if isinstance(item, Mapping) and str(item.get("status") or "") == "warning"),
        "incompatible_dimension_count": sum(1 for item in dimensions if isinstance(item, Mapping) and str(item.get("status") or "") == "incompatible"),
        "blocker_count": len(list(fast_lane_result.get("blockers", []) or [])),
        "fast_lane_contract_id": fast_lane_result.get("fast_lane_contract_id"),
        "fast_lane_contract_version": fast_lane_result.get("fast_lane_contract_version"),
        "compatibility_result_fingerprint": fast_lane_result.get("result_fingerprint"),
    }


def _scope_payload() -> dict[str, Any]:
    return {
        "rule_scope": "one certified canonical rule",
        "document_scope": "one document",
        "source_revision_scope": "one source revision",
        "scoring_preview_scope": "one scoring preview",
        "fast_lane_preview_scope": "one Fast Lane compatibility preview",
        "authorization_scope": "one reviewed authorization",
        "activation_performed": False,
        "integration_execution_performed": False,
        "invalidated_by_lifecycle_or_fingerprint_drift": True,
    }


def _scope_summary() -> dict[str, Any]:
    return {
        "rule_count": 1,
        "document_count": 1,
        "source_revision_count": 1,
        "production_activation": "not_performed",
        "integration_execution": "not_performed",
    }


def _plan_id(bundle: Mapping[str, Any]) -> str:
    authorization_result = bundle.get("authorization_result") if isinstance(bundle.get("authorization_result"), Mapping) else {}
    return "release_candidate_plan_" + _hash_payload(
        {
            "canonical_rule_id": authorization_result.get("canonical_rule_id"),
            "source_revision": authorization_result.get("source_revision"),
            "rule_fingerprint": authorization_result.get("rule_fingerprint"),
            "authorization_result_id": authorization_result.get("integration_authorization_result_id"),
            "authorization_result_fingerprint": authorization_result.get("result_fingerprint"),
            "scoring_preview_result_id": authorization_result.get("scoring_preview_result_id"),
            "fast_lane_preview_result_id": authorization_result.get("fast_lane_preview_result_id"),
        }
    )[7:23]


def _plan_fingerprint(bundle: Mapping[str, Any], eligibility: Mapping[str, Any]) -> str:
    authorization_result = bundle.get("authorization_result") if isinstance(bundle.get("authorization_result"), Mapping) else {}
    scoring_result = bundle.get("scoring_result") if isinstance(bundle.get("scoring_result"), Mapping) else {}
    fast_lane_result = bundle.get("fast_lane_result") if isinstance(bundle.get("fast_lane_result"), Mapping) else {}
    rule = bundle.get("rule") if isinstance(bundle.get("rule"), Mapping) else {}
    certification = bundle.get("certification") if isinstance(bundle.get("certification"), Mapping) else {}
    return _hash_payload(
        {
            "canonical_rule_id": rule.get("rule_id"),
            "document_id": rule.get("document_id"),
            "source_revision": rule.get("source_revision"),
            "rule_fingerprint": rule.get("rule_fingerprint"),
            "certification_fingerprint": _certification_fingerprint(certification),
            "integration_authorization_result_id": authorization_result.get("integration_authorization_result_id"),
            "integration_authorization_result_fingerprint": authorization_result.get("result_fingerprint"),
            "authorization_decision": authorization_result.get("decision"),
            "scoring_preview_result_id": scoring_result.get("scoring_preview_result_id"),
            "scoring_preview_result_fingerprint": scoring_result.get("result_fingerprint"),
            "scoring_config_fingerprint": scoring_result.get("scoring_config_fingerprint"),
            "scoring_evaluator_fingerprint": scoring_result.get("scoring_evaluator_fingerprint"),
            "fast_lane_preview_result_id": fast_lane_result.get("fast_lane_preview_result_id"),
            "fast_lane_preview_result_fingerprint": fast_lane_result.get("result_fingerprint"),
            "fast_lane_capability_fingerprint": fast_lane_result.get("fast_lane_capability_fingerprint"),
            "compatibility_evaluator_fingerprint": fast_lane_result.get("compatibility_evaluator_fingerprint"),
            "eligibility_status": eligibility.get("status"),
        }
    )


def _result_id(plan_id: str) -> str:
    return "release_candidate_result_" + analysis_backend._safe_id(plan_id)


def _receipt_id(result_id: str) -> str:
    return "release_candidate_receipt_" + analysis_backend._safe_id(result_id)


def _result_fingerprint(plan: Mapping[str, Any], gates: list[Mapping[str, Any]], digest: Mapping[str, Any], status: str) -> str:
    return _hash_payload(
        {
            "plan_fingerprint": plan.get("plan_fingerprint"),
            "gate_results": gates,
            "evidence_digest": digest,
            "qualification_status": status,
            "scope": _scope_payload(),
        }
    )


def _result_is_stale(base: Path, result: Mapping[str, Any]) -> bool:
    current = validate_certified_rule_release_candidate_eligibility(
        str(result.get("canonical_rule_id") or ""),
        str(result.get("integration_authorization_result_id") or ""),
        root=base,
    )
    if current["status"] in {"blocked", "stale", "corrupt", "unknown"}:
        return True
    bundle = _load_bundle(base, str(result.get("canonical_rule_id") or ""), str(result.get("integration_authorization_result_id") or ""))
    current_plan_fp = _plan_fingerprint(bundle, current)
    return any(
        [
            str(result.get("rule_fingerprint") or "") != str((bundle.get("rule") or {}).get("rule_fingerprint") or ""),
            str(result.get("certification_fingerprint") or "") != _certification_fingerprint(bundle.get("certification") if isinstance(bundle.get("certification"), Mapping) else None),
            str(result.get("integration_authorization_result_fingerprint") or "") != str((bundle.get("authorization_result") or {}).get("result_fingerprint") or ""),
            str(result.get("scoring_preview_result_fingerprint") or "") != str((bundle.get("scoring_result") or {}).get("result_fingerprint") or ""),
            str(result.get("fast_lane_preview_result_fingerprint") or "") != str((bundle.get("fast_lane_result") or {}).get("result_fingerprint") or ""),
            str(result.get("scoring_config_fingerprint") or "") != str((bundle.get("scoring_result") or {}).get("scoring_config_fingerprint") or ""),
            str(result.get("scoring_evaluator_fingerprint") or "") != str((bundle.get("scoring_result") or {}).get("scoring_evaluator_fingerprint") or ""),
            str(result.get("fast_lane_capability_fingerprint") or "") != str((bundle.get("fast_lane_result") or {}).get("fast_lane_capability_fingerprint") or ""),
            str(result.get("compatibility_evaluator_fingerprint") or "") != str((bundle.get("fast_lane_result") or {}).get("compatibility_evaluator_fingerprint") or ""),
            str(result.get("release_candidate_plan_id") or "") != _plan_id(bundle),
            str((analysis_backend._read_json(_plan_path(base, str(result.get("release_candidate_plan_id") or ""))) or {}).get("plan_fingerprint") or "") != current_plan_fp,
        ]
    )


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
                "release_candidate_plan_id": payload.get("release_candidate_plan_id"),
                "canonical_rule_id": payload.get("canonical_rule_id"),
                "document_id": payload.get("document_id"),
                "source_revision": payload.get("source_revision"),
                "integration_authorization_result_id": payload.get("integration_authorization_result_id"),
                "plan_fingerprint": payload.get("plan_fingerprint"),
            }
        )
    analysis_backend._atomic_write_json(base / "indexes" / PLAN_INDEX, {"schema_version": "certified_rule_release_candidate_plan_index_v1", "items": items, "updated_at_utc": analysis_backend._now()})


def _update_result_index(base: Path) -> None:
    items = []
    for payload in _load_all(base / RESULT_DIR):
        items.append(
            {
                "release_candidate_result_id": payload.get("release_candidate_result_id"),
                "release_candidate_plan_id": payload.get("release_candidate_plan_id"),
                "canonical_rule_id": payload.get("canonical_rule_id"),
                "qualification_status": payload.get("qualification_status"),
                "result_fingerprint": payload.get("result_fingerprint"),
            }
        )
    analysis_backend._atomic_write_json(base / "indexes" / RESULT_INDEX, {"schema_version": "certified_rule_release_candidate_result_index_v1", "items": items, "updated_at_utc": analysis_backend._now()})


def _update_receipt_index(base: Path) -> None:
    items = []
    for payload in _load_all(base / RECEIPT_DIR):
        items.append(
            {
                "release_candidate_receipt_id": payload.get("release_candidate_receipt_id"),
                "release_candidate_result_id": payload.get("release_candidate_result_id"),
                "release_candidate_plan_id": payload.get("release_candidate_plan_id"),
                "qualification_status": payload.get("qualification_status"),
                "result_fingerprint": payload.get("result_fingerprint"),
            }
        )
    analysis_backend._atomic_write_json(base / "indexes" / RECEIPT_INDEX, {"schema_version": "certified_rule_release_candidate_receipt_index_v1", "items": items, "updated_at_utc": analysis_backend._now()})


def _find_plan(base: Path, canonical_rule_id: str, integration_authorization_result_id: str) -> dict[str, Any] | None:
    for payload in _load_all(base / PLAN_DIR):
        if str(payload.get("canonical_rule_id") or "") == canonical_rule_id and str(payload.get("integration_authorization_result_id") or "") == integration_authorization_result_id:
            return payload
    return None


def _find_result(base: Path, plan_id: str) -> dict[str, Any] | None:
    for payload in _load_all(base / RESULT_DIR):
        if str(payload.get("release_candidate_plan_id") or "") == plan_id:
            return payload
    return None


def _find_result_by_id(base: Path, result_id: str) -> dict[str, Any] | None:
    payload = analysis_backend._read_json(_result_path(base, result_id))
    return dict(payload) if isinstance(payload, Mapping) else None


def _find_receipt_for_result(base: Path, result_id: str) -> dict[str, Any] | None:
    for payload in _load_all(base / RECEIPT_DIR):
        if str(payload.get("release_candidate_result_id") or "") == result_id:
            return payload
    return None


def _find_receipt_by_id(base: Path, receipt_id: str | None) -> dict[str, Any] | None:
    if not receipt_id:
        return None
    payload = analysis_backend._read_json(_receipt_path(base, receipt_id))
    return dict(payload) if isinstance(payload, Mapping) else None


def _acceptable_rule_fingerprints(rule: Mapping[str, Any]) -> set[str]:
    return {item for item in {str(rule.get("rule_fingerprint") or ""), _hash_payload(rule)} if item}


def _certification_fingerprint(certification: Mapping[str, Any] | None) -> str:
    return authorization_backend._certification_fingerprint(certification)


def _rollback_pending(rule: Mapping[str, Any]) -> bool:
    return bool(rule.get("rollback_pending")) or bool(rule.get("rollback_requested"))


def _plan_summary(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "canonical_rule_id": plan.get("canonical_rule_id"),
        "document_id": plan.get("document_id"),
        "source_revision": plan.get("source_revision"),
        "integration_authorization_result_id": plan.get("integration_authorization_result_id"),
        "qualification_mode": plan.get("qualification_mode"),
        "recommended_action": "Qualify the release candidate with exact confirmation.",
    }


def _recommended_action(status: str) -> str:
    return {
        "eligible": "Build the release-candidate qualification plan.",
        "eligible_with_warnings": "Build the plan and review the non-blocking warnings.",
        "not_eligible": "Review the failed qualification gates before any later execution phase.",
        "qualified": "Candidate is evidence-qualified for a later controlled integration phase.",
        "qualified_with_warnings": "Candidate is qualified, but preserve and review warnings before later execution.",
        "blocked": "Resolve missing or unverifiable evidence first.",
        "stale": "Refresh the authorized evidence chain first.",
        "corrupt": "Inspect evidence integrity before continuing.",
    }.get(status, "Review the qualification state.")


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in items if str(item)))
