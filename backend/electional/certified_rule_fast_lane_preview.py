"""Stored read-only Fast Lane compatibility preview for one certified rule."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from . import rule_effectiveness_analysis as analysis_backend
from .analysis.fast_lane import get_fast_lane_capability_manifest
from .canonical_rule_runtime import load_canonical_rule
from .certified_rule_replay_adapter import _rule_has_unresolved_critical_remediation, _rule_pending_supersession
from .document_manifest import load_document_manifest
from .fast_lane_compatibility import (
    evaluate_certified_rule_fast_lane_compatibility,
    format_fast_lane_compatibility_report,
    get_fast_lane_capability_fingerprint,
    get_fast_lane_compatibility_evaluator_fingerprint,
    validate_certified_rule_fast_lane_inputs,
    validate_fast_lane_capability_manifest,
)
from .rule_effectiveness_analysis import _ensure_analysis_dirs, _hash_payload, _load_certification_receipt_for_rule
from .source_documents import SOURCE_DOCUMENT_ROOT

PLAN_DIR = "certified_rule_fast_lane_preview_plans"
RESULT_DIR = "certified_rule_fast_lane_preview_results"
RECEIPT_DIR = "certified_rule_fast_lane_preview_receipts"
PLAN_INDEX = "certified_rule_fast_lane_preview_plan_index.json"
RESULT_INDEX = "certified_rule_fast_lane_preview_result_index.json"
RECEIPT_INDEX = "certified_rule_fast_lane_preview_receipt_index.json"
PLAN_SCHEMA = "certified_rule_fast_lane_preview_plan_v1"
RESULT_SCHEMA = "certified_rule_fast_lane_preview_result_v1"
RECEIPT_SCHEMA = "certified_rule_fast_lane_preview_receipt_v1"
PREVIEW_SCHEMA_VERSION = "certified_rule_fast_lane_preview_v1"
PREVIEW_MODE = "compatibility_only_read_only"


def build_certified_rule_fast_lane_preview_workspace(
    canonical_rule_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    eligibility = validate_certified_rule_fast_lane_preview_eligibility(canonical_rule_id, root=base)
    rule = load_canonical_rule(canonical_rule_id, require_active=False, root=base).get("rule")
    certification = _load_certification_receipt_for_rule(base, canonical_rule_id)
    manifest = get_fast_lane_capability_manifest()
    manifest_validation = validate_fast_lane_capability_manifest(manifest)
    manifest_fp = get_fast_lane_capability_fingerprint(manifest) if manifest_validation["valid"] else None
    evaluator_fp = get_fast_lane_compatibility_evaluator_fingerprint()
    plan = _find_plan(base, canonical_rule_id)
    result = _find_result(base, str((plan or {}).get("fast_lane_preview_plan_id") or ""))
    receipt = _find_receipt_for_result(base, str((result or {}).get("fast_lane_preview_result_id") or ""))
    return {
        "status": "ready_for_planning" if not eligibility.get("blockers") else str(eligibility.get("status") or "blocked"),
        "canonical_rule_id": canonical_rule_id,
        "document_id": (rule or {}).get("document_id"),
        "source_revision": (rule or {}).get("source_revision"),
        "rule_status": (rule or {}).get("status", "missing"),
        "certification_status": (certification or {}).get("certification_status", "missing"),
        "fast_lane_contract_id": manifest.get("fast_lane_contract_id"),
        "fast_lane_contract_version": manifest.get("fast_lane_contract_version"),
        "capability_status": manifest_validation.get("status", "blocked"),
        "capability_fingerprint": manifest_fp,
        "compatibility_evaluator_fingerprint": evaluator_fp,
        "fast_lane_preview_plan_id": (plan or {}).get("fast_lane_preview_plan_id"),
        "fast_lane_preview_result_id": (result or {}).get("fast_lane_preview_result_id"),
        "fast_lane_preview_receipt_id": (receipt or {}).get("fast_lane_preview_receipt_id"),
        "warnings": list(eligibility.get("warnings", [])),
        "blockers": list(eligibility.get("blockers", [])),
        "recommended_action": "Build the Fast Lane compatibility preview plan." if not eligibility.get("blockers") else "Resolve lifecycle, provenance, certification, or contract blockers first.",
    }


def validate_certified_rule_fast_lane_preview_eligibility(
    canonical_rule_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    blockers: list[str] = []
    warnings: list[str] = []
    rule_loaded = load_canonical_rule(canonical_rule_id, require_active=True, root=base)
    rule = rule_loaded.get("rule")
    if rule_loaded.get("status") != "loaded" or not isinstance(rule, Mapping):
        blockers.extend(list(rule_loaded.get("blockers", []) or ["canonical_rule_not_found"]))
        return {
            "status": "blocked",
            "eligibility": "blocked",
            "compatibility_foundation_status": "blocked",
            "rule_status": rule_loaded.get("rule_status", "missing"),
            "certification_status": "missing",
            "provenance_status": "unknown",
            "capability_status": "unknown",
            "warnings": [],
            "blockers": _dedupe(blockers),
            "recommended_action": "Load one active certified rule first.",
        }
    certification = _load_certification_receipt_for_rule(base, canonical_rule_id)
    if not isinstance(certification, Mapping):
        blockers.append("rule_certification_missing")
    elif str(certification.get("certification_status") or "") != "completed":
        blockers.append("rule_certification_not_current")
    elif str(certification.get("rule_hash") or "") != str(rule.get("rule_fingerprint") or ""):
        blockers.append("rule_certification_hash_mismatch")
    manifest_data = load_document_manifest(str(rule.get("document_id") or ""), root=base).get("manifest")
    provenance_status = "current"
    if not isinstance(manifest_data, Mapping):
        blockers.append("document_manifest_missing")
        provenance_status = "unknown"
    elif str(manifest_data.get("source_revision") or "") != str(rule.get("source_revision") or ""):
        blockers.append("source_revision_not_current")
        provenance_status = "stale"
    if _rule_has_unresolved_critical_remediation(base, rule):
        blockers.append("rule_has_unresolved_critical_remediation")
    if _rule_pending_supersession(base, canonical_rule_id):
        blockers.append("rule_pending_supersession")
    capability_manifest = get_fast_lane_capability_manifest()
    capability_validation = validate_fast_lane_capability_manifest(capability_manifest)
    if not capability_validation["valid"]:
        blockers.extend(list(capability_validation.get("blockers", [])))
    capability_fp = get_fast_lane_capability_fingerprint(capability_manifest) if capability_validation["valid"] else None
    evaluator_fp = get_fast_lane_compatibility_evaluator_fingerprint()
    source_context = _source_context(rule)
    foundation = validate_certified_rule_fast_lane_inputs(dict(rule), dict(certification or {}), source_context, capability_manifest)
    blockers.extend(list(foundation.get("blockers", [])))
    status = "eligible" if not blockers else "stale" if "source_revision_not_current" in blockers else "blocked"
    return {
        "status": status,
        "eligibility": "eligible" if not blockers else "blocked",
        "compatibility_foundation_status": foundation.get("status", capability_validation.get("status", "blocked")),
        "canonical_rule_id": canonical_rule_id,
        "document_id": rule.get("document_id"),
        "source_revision": rule.get("source_revision"),
        "rule_status": rule.get("status"),
        "rule_fingerprint": rule.get("rule_fingerprint"),
        "certification_status": (certification or {}).get("certification_status", "missing"),
        "certification_receipt_id": (certification or {}).get("certification_receipt_id"),
        "certification_fingerprint": foundation.get("certification_fingerprint"),
        "provenance_status": provenance_status,
        "capability_status": capability_validation.get("status", "blocked"),
        "fast_lane_contract_id": capability_manifest.get("fast_lane_contract_id"),
        "fast_lane_contract_version": capability_manifest.get("fast_lane_contract_version"),
        "capability_fingerprint": capability_fp,
        "compatibility_evaluator_fingerprint": evaluator_fp,
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
        "recommended_action": "Build the Fast Lane compatibility preview plan." if not blockers else "Resolve Fast Lane compatibility foundation blockers first.",
    }


def build_certified_rule_fast_lane_preview_plan(
    canonical_rule_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    eligibility = validate_certified_rule_fast_lane_preview_eligibility(canonical_rule_id, root=base)
    if eligibility.get("blockers"):
        return {
            "status": str(eligibility.get("status") or "blocked"),
            "canonical_rule_id": canonical_rule_id,
            "warnings": list(eligibility.get("warnings", [])),
            "blockers": list(eligibility.get("blockers", [])),
        }
    manifest = get_fast_lane_capability_manifest()
    plan = {
        "schema_version": PLAN_SCHEMA,
        "preview_schema_version": PREVIEW_SCHEMA_VERSION,
        "fast_lane_preview_plan_id": _plan_id(eligibility, manifest),
        "canonical_rule_id": canonical_rule_id,
        "document_id": eligibility.get("document_id"),
        "source_revision": eligibility.get("source_revision"),
        "rule_schema_version": CANONICAL_RULE_SCHEMA(eligibility=None),
        "rule_fingerprint": eligibility.get("rule_fingerprint"),
        "certification_receipt_id": eligibility.get("certification_receipt_id"),
        "certification_fingerprint": eligibility.get("certification_fingerprint"),
        "fast_lane_contract_id": manifest.get("fast_lane_contract_id"),
        "fast_lane_contract_version": manifest.get("fast_lane_contract_version"),
        "fast_lane_capability_fingerprint": eligibility.get("capability_fingerprint"),
        "compatibility_evaluator_fingerprint": eligibility.get("compatibility_evaluator_fingerprint"),
        "preview_mode": PREVIEW_MODE,
        "warnings": list(eligibility.get("warnings", [])),
        "blockers": [],
        "plan_fingerprint": _plan_fingerprint(eligibility, manifest),
    }
    plan_path = _plan_path(base, str(plan["fast_lane_preview_plan_id"]))
    existing = analysis_backend._read_json(plan_path)
    if isinstance(existing, Mapping):
        if str(existing.get("plan_fingerprint") or "") == str(plan.get("plan_fingerprint") or ""):
            return {"status": "planned", "fast_lane_preview_plan_id": plan["fast_lane_preview_plan_id"], "writes_performed": 0, **_plan_summary(plan)}
        return {"status": "corrupt", "blockers": ["fast_lane_preview_plan_divergence"], "warnings": []}
    before_plan = analysis_backend._read_json(plan_path)
    before_index = analysis_backend._read_json(base / "indexes" / PLAN_INDEX)
    try:
        analysis_backend._atomic_write_json(plan_path, plan)
        _update_plan_index(base)
    except Exception:
        analysis_backend._restore_json(plan_path, before_plan)
        analysis_backend._restore_json(base / "indexes" / PLAN_INDEX, before_index)
        return {"status": "corrupt", "blockers": ["fast_lane_preview_plan_write_failure"], "warnings": []}
    return {"status": "planned", "fast_lane_preview_plan_id": plan["fast_lane_preview_plan_id"], "writes_performed": 1, **_plan_summary(plan)}


def run_certified_rule_fast_lane_preview(
    fast_lane_preview_plan_id: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    if confirmation != "RUN_FAST_LANE_COMPATIBILITY_PREVIEW":
        return {"status": "blocked", "fast_lane_preview_plan_id": fast_lane_preview_plan_id, "blockers": ["run_fast_lane_preview_confirmation_required"], "warnings": []}
    plan = analysis_backend._read_json(_plan_path(base, fast_lane_preview_plan_id))
    if not isinstance(plan, Mapping):
        return {"status": "blocked", "fast_lane_preview_plan_id": fast_lane_preview_plan_id, "blockers": ["fast_lane_preview_plan_missing"], "warnings": []}
    current = _plan_current_status(base, plan)
    if current["status"] != "current":
        return {"status": current["status"], "fast_lane_preview_plan_id": fast_lane_preview_plan_id, "blockers": list(current.get("blockers", [])), "warnings": []}
    existing = _find_result(base, fast_lane_preview_plan_id)
    if isinstance(existing, Mapping) and not _result_is_stale(base, existing):
        receipt = _find_receipt_for_result(base, str(existing.get("fast_lane_preview_result_id") or ""))
        if isinstance(receipt, Mapping) and str(receipt.get("result_fingerprint") or "") == str(existing.get("result_fingerprint") or ""):
            return {
                "status": "already_completed",
                "fast_lane_preview_plan_id": fast_lane_preview_plan_id,
                "fast_lane_preview_result_id": existing.get("fast_lane_preview_result_id"),
                "fast_lane_preview_receipt_id": receipt.get("fast_lane_preview_receipt_id"),
                "writes_performed": 0,
            }
        return {"status": "corrupt", "fast_lane_preview_plan_id": fast_lane_preview_plan_id, "blockers": ["fast_lane_preview_receipt_divergence"], "warnings": []}
    rule = load_canonical_rule(str(plan.get("canonical_rule_id") or ""), require_active=True, root=base).get("rule") or {}
    certification = _load_certification_receipt_for_rule(base, str(plan.get("canonical_rule_id") or "")) or {}
    manifest = get_fast_lane_capability_manifest()
    source_context = _source_context(rule)
    snapshots_before = _read_only_snapshots(rule, certification, source_context, manifest)
    compatibility = evaluate_certified_rule_fast_lane_compatibility(dict(rule), dict(certification), dict(source_context), deepcopy(manifest))
    snapshots_after = _read_only_snapshots(rule, certification, source_context, manifest)
    mutation_detected = snapshots_before != snapshots_after
    preview_status = _preview_status(compatibility, mutation_detected)
    result_id = _result_id(fast_lane_preview_plan_id, plan)
    result = {
        "schema_version": RESULT_SCHEMA,
        "preview_schema_version": PREVIEW_SCHEMA_VERSION,
        "fast_lane_preview_result_id": result_id,
        "fast_lane_preview_plan_id": fast_lane_preview_plan_id,
        "canonical_rule_id": plan.get("canonical_rule_id"),
        "document_id": plan.get("document_id"),
        "source_revision": plan.get("source_revision"),
        "rule_schema_version": plan.get("rule_schema_version"),
        "rule_fingerprint": plan.get("rule_fingerprint"),
        "certification_receipt_id": plan.get("certification_receipt_id"),
        "certification_fingerprint": plan.get("certification_fingerprint"),
        "fast_lane_contract_id": plan.get("fast_lane_contract_id"),
        "fast_lane_contract_version": plan.get("fast_lane_contract_version"),
        "fast_lane_capability_fingerprint": plan.get("fast_lane_capability_fingerprint"),
        "compatibility_evaluator_fingerprint": plan.get("compatibility_evaluator_fingerprint"),
        "dimension_results": list(compatibility.get("dimension_results", [])),
        "supported_operators": list(compatibility.get("supported_operators", [])),
        "unsupported_operators": list(compatibility.get("unsupported_operators", [])),
        "supported_input_fields": list(compatibility.get("supported_input_fields", [])),
        "unsupported_input_fields": list(compatibility.get("unsupported_input_fields", [])),
        "supported_actions": list(compatibility.get("supported_actions", [])),
        "unsupported_actions": list(compatibility.get("unsupported_actions", [])),
        "semantic_loss": compatibility.get("semantic_loss"),
        "overall_compatibility": compatibility.get("overall_status"),
        "blockers": list(compatibility.get("blockers", [])) + (["production_state_mutation_detected"] if mutation_detected else []),
        "warnings": list(compatibility.get("warnings", [])),
        "compatibility_result_fingerprint": compatibility.get("result_fingerprint"),
        "preview_status": preview_status,
        "result_fingerprint": _result_fingerprint(plan, compatibility, preview_status),
    }
    receipt_id = _receipt_id(result_id)
    counts = _dimension_counts(result)
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "fast_lane_preview_receipt_id": receipt_id,
        "fast_lane_preview_result_id": result_id,
        "fast_lane_preview_plan_id": fast_lane_preview_plan_id,
        "canonical_rule_id": plan.get("canonical_rule_id"),
        "document_id": plan.get("document_id"),
        "source_revision": plan.get("source_revision"),
        "certification_receipt_id": plan.get("certification_receipt_id"),
        "certification_fingerprint": plan.get("certification_fingerprint"),
        "fast_lane_contract_id": plan.get("fast_lane_contract_id"),
        "fast_lane_contract_version": plan.get("fast_lane_contract_version"),
        "fast_lane_capability_fingerprint": plan.get("fast_lane_capability_fingerprint"),
        "compatibility_evaluator_fingerprint": plan.get("compatibility_evaluator_fingerprint"),
        "overall_compatibility": result.get("overall_compatibility"),
        "semantic_loss": result.get("semantic_loss"),
        "preview_status": preview_status,
        "summary_counts": counts,
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
        return {"status": "corrupt", "fast_lane_preview_plan_id": fast_lane_preview_plan_id, "blockers": ["fast_lane_preview_result_write_failure"], "warnings": []}
    return {
        "status": preview_status,
        "fast_lane_preview_plan_id": fast_lane_preview_plan_id,
        "fast_lane_preview_result_id": result_id,
        "fast_lane_preview_receipt_id": receipt_id,
        "writes_performed": 2,
        **counts,
    }


def load_certified_rule_fast_lane_preview_result(
    fast_lane_preview_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    result = analysis_backend._read_json(_result_path(base, fast_lane_preview_result_id))
    if not isinstance(result, Mapping):
        return {"status": "not_found", "fast_lane_preview_result_id": fast_lane_preview_result_id, "fast_lane_preview_result": None, "warnings": []}
    payload = dict(result)
    payload["stale"] = _result_is_stale(base, payload)
    return {"status": "loaded", "fast_lane_preview_result_id": fast_lane_preview_result_id, "fast_lane_preview_result": payload, "warnings": []}


def get_certified_rule_fast_lane_preview_health(
    fast_lane_preview_plan_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    plans = _load_all(base / PLAN_DIR)
    results = _load_all(base / RESULT_DIR)
    receipts = _load_all(base / RECEIPT_DIR)
    if fast_lane_preview_plan_id:
        plans = [item for item in plans if str(item.get("fast_lane_preview_plan_id") or "") == fast_lane_preview_plan_id]
        results = [item for item in results if str(item.get("fast_lane_preview_plan_id") or "") == fast_lane_preview_plan_id]
        receipts = [item for item in receipts if str(item.get("fast_lane_preview_plan_id") or "") == fast_lane_preview_plan_id]
    if not plans and not results and not receipts:
        return {"status": "empty", "fast_lane_preview_plan_count": 0, "fast_lane_preview_result_count": 0, "fast_lane_preview_receipt_count": 0, "recommended_action": "Build one Fast Lane compatibility preview plan."}
    warnings: list[str] = []
    stale_count = 0
    if len({str(item.get("fast_lane_preview_plan_id") or "") for item in plans}) != len(plans):
        warnings.append("duplicate_fast_lane_preview_plan_ids")
    if len({str(item.get("fast_lane_preview_result_id") or "") for item in results}) != len(results):
        warnings.append("duplicate_fast_lane_preview_result_ids")
    if len({str(item.get("fast_lane_preview_receipt_id") or "") for item in receipts}) != len(receipts):
        warnings.append("duplicate_fast_lane_preview_receipt_ids")
    for result in results:
        if _result_is_stale(base, result):
            stale_count += 1
        if str(result.get("overall_compatibility") or "") == "compatible" and str(result.get("semantic_loss") or "") == "confirmed":
            warnings.append("compatible_with_confirmed_semantic_loss")
        if not isinstance(result.get("dimension_results"), list) or not result.get("dimension_results"):
            warnings.append("missing_dimension_results")
        if "production_state_mutation_detected" in list(result.get("blockers", []) or []):
            warnings.append("production_state_mutation_detected")
        receipt = _find_receipt_for_result(base, str(result.get("fast_lane_preview_result_id") or ""))
        if not isinstance(receipt, Mapping):
            warnings.append("fast_lane_preview_receipt_missing")
        elif str(receipt.get("result_fingerprint") or "") != str(result.get("result_fingerprint") or ""):
            warnings.append("fast_lane_preview_receipt_fingerprint_mismatch")
    status = "corrupt" if any(item in warnings for item in ("compatible_with_confirmed_semantic_loss", "missing_dimension_results", "fast_lane_preview_receipt_fingerprint_mismatch")) else "stale" if stale_count else "warning" if warnings else "healthy"
    return {
        "status": status,
        "fast_lane_preview_plan_count": len(plans),
        "fast_lane_preview_result_count": len(results),
        "fast_lane_preview_receipt_count": len(receipts),
        "stale_preview_count": stale_count,
        "warnings": _dedupe(warnings),
        "recommended_action": "Rebuild the Fast Lane preview against current dependencies." if stale_count else "Fast Lane compatibility preview health is good.",
    }


def format_certified_rule_fast_lane_preview_report(
    fast_lane_preview_result_id: str | None = None,
    fast_lane_preview_receipt_id: str | None = None,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    base = _ensure_dirs(root)
    receipt = _find_receipt_by_id(base, fast_lane_preview_receipt_id) if fast_lane_preview_receipt_id else None
    result = _find_result_by_id(base, fast_lane_preview_result_id or str((receipt or {}).get("fast_lane_preview_result_id") or ""))
    if not isinstance(result, Mapping):
        return "Certified Rule Fast Lane Preview\n\nStatus: not_found"
    text = format_fast_lane_compatibility_report(
        {
            "canonical_rule_id": result.get("canonical_rule_id"),
            "document_id": result.get("document_id"),
            "source_revision": result.get("source_revision"),
            "certification_status": "completed" if result.get("certification_fingerprint") else "missing",
            "fast_lane_contract_id": result.get("fast_lane_contract_id"),
            "fast_lane_contract_version": result.get("fast_lane_contract_version"),
            "overall_status": result.get("overall_compatibility"),
            "semantic_loss": result.get("semantic_loss"),
            "dimension_results": result.get("dimension_results"),
            "supported_operators": result.get("supported_operators"),
            "unsupported_operators": result.get("unsupported_operators"),
            "supported_input_fields": result.get("supported_input_fields"),
            "unsupported_input_fields": result.get("unsupported_input_fields"),
            "supported_actions": result.get("supported_actions"),
            "unsupported_actions": result.get("unsupported_actions"),
            "blockers": result.get("blockers"),
            "warnings": result.get("warnings"),
            "result_fingerprint": result.get("compatibility_result_fingerprint"),
        },
        public_safe=public_safe,
    )
    extra = [
        "",
        f"Preview Status: {result.get('preview_status')}",
        f"Stale: {'Yes' if _result_is_stale(base, result) else 'No'}",
        "Execution: Fast Lane was not executed.",
        "Safety: no Fast Lane or production state was modified.",
        "Authorization: compatibility does not authorize activation.",
        "Interpretation: a technically completed preview may still conclude that the rule is incompatible.",
    ]
    return text + "\n" + "\n".join(extra)


def get_certified_rule_fast_lane_preview_summary(
    fast_lane_preview_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    result = _find_result_by_id(base, fast_lane_preview_result_id)
    if not isinstance(result, Mapping):
        return {"status": "not_found", "recommended_action": "Run one Fast Lane compatibility preview."}
    counts = _dimension_counts(result)
    return {
        "canonical_rule_id": result.get("canonical_rule_id"),
        "document_id": result.get("document_id"),
        "source_revision": result.get("source_revision"),
        "fast_lane_contract_id": result.get("fast_lane_contract_id"),
        "fast_lane_contract_version": result.get("fast_lane_contract_version"),
        "preview_status": result.get("preview_status"),
        "overall_compatibility": result.get("overall_compatibility"),
        "semantic_loss": result.get("semantic_loss"),
        **counts,
        "stale": _result_is_stale(base, result),
        "recommended_action": _recommended_action(result),
    }


def _ensure_dirs(root: Path | str) -> Path:
    base = _ensure_analysis_dirs(root)
    for folder in (PLAN_DIR, RESULT_DIR, RECEIPT_DIR, "indexes"):
        (base / folder).mkdir(parents=True, exist_ok=True)
    defaults = (
        (PLAN_INDEX, "certified_rule_fast_lane_preview_plan_index_v1"),
        (RESULT_INDEX, "certified_rule_fast_lane_preview_result_index_v1"),
        (RECEIPT_INDEX, "certified_rule_fast_lane_preview_receipt_index_v1"),
    )
    for name, schema in defaults:
        path = base / "indexes" / name
        if not path.exists():
            analysis_backend._atomic_write_json(path, {"schema_version": schema, "items": [], "updated_at_utc": analysis_backend._now()})
    return base


def _source_context(rule: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "document_id": rule.get("document_id"),
        "source_revision": rule.get("source_revision"),
        "current_source_revision": rule.get("source_revision"),
        "rule_fingerprint": rule.get("rule_fingerprint"),
    }


def _plan_path(base: Path, plan_id: str) -> Path:
    return base / PLAN_DIR / f"{analysis_backend._safe_id(plan_id)}.json"


def _result_path(base: Path, result_id: str) -> Path:
    return base / RESULT_DIR / f"{analysis_backend._safe_id(result_id)}.json"


def _receipt_path(base: Path, receipt_id: str) -> Path:
    return base / RECEIPT_DIR / f"{analysis_backend._safe_id(receipt_id)}.json"


def _load_all(directory: Path) -> list[dict[str, Any]]:
    items = []
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
                "fast_lane_preview_plan_id": payload.get("fast_lane_preview_plan_id"),
                "canonical_rule_id": payload.get("canonical_rule_id"),
                "document_id": payload.get("document_id"),
                "source_revision": payload.get("source_revision"),
                "fast_lane_contract_id": payload.get("fast_lane_contract_id"),
                "fast_lane_contract_version": payload.get("fast_lane_contract_version"),
                "plan_fingerprint": payload.get("plan_fingerprint"),
            }
        )
    analysis_backend._atomic_write_json(base / "indexes" / PLAN_INDEX, {"schema_version": "certified_rule_fast_lane_preview_plan_index_v1", "items": items, "updated_at_utc": analysis_backend._now()})


def _update_result_index(base: Path) -> None:
    items = []
    for payload in _load_all(base / RESULT_DIR):
        items.append(
            {
                "fast_lane_preview_result_id": payload.get("fast_lane_preview_result_id"),
                "fast_lane_preview_plan_id": payload.get("fast_lane_preview_plan_id"),
                "canonical_rule_id": payload.get("canonical_rule_id"),
                "document_id": payload.get("document_id"),
                "source_revision": payload.get("source_revision"),
                "preview_status": payload.get("preview_status"),
                "overall_compatibility": payload.get("overall_compatibility"),
                "result_fingerprint": payload.get("result_fingerprint"),
            }
        )
    analysis_backend._atomic_write_json(base / "indexes" / RESULT_INDEX, {"schema_version": "certified_rule_fast_lane_preview_result_index_v1", "items": items, "updated_at_utc": analysis_backend._now()})


def _update_receipt_index(base: Path) -> None:
    items = []
    for payload in _load_all(base / RECEIPT_DIR):
        items.append(
            {
                "fast_lane_preview_receipt_id": payload.get("fast_lane_preview_receipt_id"),
                "fast_lane_preview_result_id": payload.get("fast_lane_preview_result_id"),
                "fast_lane_preview_plan_id": payload.get("fast_lane_preview_plan_id"),
                "preview_status": payload.get("preview_status"),
                "result_fingerprint": payload.get("result_fingerprint"),
            }
        )
    analysis_backend._atomic_write_json(base / "indexes" / RECEIPT_INDEX, {"schema_version": "certified_rule_fast_lane_preview_receipt_index_v1", "items": items, "updated_at_utc": analysis_backend._now()})


def _find_plan(base: Path, canonical_rule_id: str) -> dict[str, Any] | None:
    for payload in _load_all(base / PLAN_DIR):
        if str(payload.get("canonical_rule_id") or "") == canonical_rule_id:
            return payload
    return None


def _find_result(base: Path, plan_id: str) -> dict[str, Any] | None:
    for payload in _load_all(base / RESULT_DIR):
        if str(payload.get("fast_lane_preview_plan_id") or "") == plan_id:
            return payload
    return None


def _find_result_by_id(base: Path, result_id: str) -> dict[str, Any] | None:
    payload = analysis_backend._read_json(_result_path(base, result_id))
    return dict(payload) if isinstance(payload, Mapping) else None


def _find_receipt_for_result(base: Path, result_id: str) -> dict[str, Any] | None:
    for payload in _load_all(base / RECEIPT_DIR):
        if str(payload.get("fast_lane_preview_result_id") or "") == result_id:
            return payload
    return None


def _find_receipt_by_id(base: Path, receipt_id: str | None) -> dict[str, Any] | None:
    if not receipt_id:
        return None
    payload = analysis_backend._read_json(_receipt_path(base, receipt_id))
    return dict(payload) if isinstance(payload, Mapping) else None


def _plan_id(eligibility: Mapping[str, Any], manifest: Mapping[str, Any]) -> str:
    return "fast_lane_preview_" + _hash_payload(
        {
            "schema_version": PLAN_SCHEMA,
            "canonical_rule_id": eligibility.get("canonical_rule_id"),
            "rule_fingerprint": eligibility.get("rule_fingerprint"),
            "certification_receipt_id": eligibility.get("certification_receipt_id"),
            "certification_fingerprint": eligibility.get("certification_fingerprint"),
            "fast_lane_contract_id": manifest.get("fast_lane_contract_id"),
            "fast_lane_contract_version": manifest.get("fast_lane_contract_version"),
            "capability_fingerprint": eligibility.get("capability_fingerprint"),
            "evaluator_fingerprint": eligibility.get("compatibility_evaluator_fingerprint"),
            "preview_mode": PREVIEW_MODE,
        }
    )[:16]


def _plan_fingerprint(eligibility: Mapping[str, Any], manifest: Mapping[str, Any]) -> str:
    return _hash_payload(
        {
            "schema_version": PLAN_SCHEMA,
            "preview_schema_version": PREVIEW_SCHEMA_VERSION,
            "canonical_rule_id": eligibility.get("canonical_rule_id"),
            "document_id": eligibility.get("document_id"),
            "source_revision": eligibility.get("source_revision"),
            "rule_schema_version": CANONICAL_RULE_SCHEMA(eligibility),
            "rule_fingerprint": eligibility.get("rule_fingerprint"),
            "certification_receipt_id": eligibility.get("certification_receipt_id"),
            "certification_fingerprint": eligibility.get("certification_fingerprint"),
            "fast_lane_contract_id": manifest.get("fast_lane_contract_id"),
            "fast_lane_contract_version": manifest.get("fast_lane_contract_version"),
            "fast_lane_capability_fingerprint": eligibility.get("capability_fingerprint"),
            "compatibility_evaluator_fingerprint": eligibility.get("compatibility_evaluator_fingerprint"),
            "preview_mode": PREVIEW_MODE,
        }
    )


def _result_id(plan_id: str, plan: Mapping[str, Any]) -> str:
    return "fast_lane_result_" + _hash_payload(
        {"plan_id": plan_id, "plan_fingerprint": plan.get("plan_fingerprint"), "schema_version": RESULT_SCHEMA}
    )[:16]


def _receipt_id(result_id: str) -> str:
    return f"receipt_{analysis_backend._safe_id(result_id)}"


def _plan_current_status(base: Path, plan: Mapping[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    eligibility = validate_certified_rule_fast_lane_preview_eligibility(str(plan.get("canonical_rule_id") or ""), root=base)
    blockers.extend(list(eligibility.get("blockers", [])))
    manifest = get_fast_lane_capability_manifest()
    if str(plan.get("preview_mode") or "") != PREVIEW_MODE:
        blockers.append("preview_mode_unsupported")
    if str(plan.get("fast_lane_capability_fingerprint") or "") != str(eligibility.get("capability_fingerprint") or ""):
        blockers.append("fast_lane_capability_fingerprint_mismatch")
    if str(plan.get("compatibility_evaluator_fingerprint") or "") != get_fast_lane_compatibility_evaluator_fingerprint():
        blockers.append("fast_lane_compatibility_evaluator_fingerprint_mismatch")
    if str(plan.get("plan_fingerprint") or "") != _plan_fingerprint(eligibility, manifest):
        blockers.append("fast_lane_preview_plan_fingerprint_mismatch")
    if blockers:
        if "source_revision_not_current" in blockers or any(
            item in blockers
            for item in (
                "fast_lane_capability_fingerprint_mismatch",
                "fast_lane_compatibility_evaluator_fingerprint_mismatch",
                "fast_lane_preview_plan_fingerprint_mismatch",
            )
        ):
            return {"status": "stale", "blockers": _dedupe(blockers)}
        if any(item.endswith("_mismatch") for item in blockers):
            return {"status": "corrupt", "blockers": _dedupe(blockers)}
        return {"status": "blocked", "blockers": _dedupe(blockers)}
    return {"status": "current", "blockers": []}


def _result_is_stale(base: Path, result: Mapping[str, Any]) -> bool:
    eligibility = validate_certified_rule_fast_lane_preview_eligibility(str(result.get("canonical_rule_id") or ""), root=base)
    return any(
        [
            str(result.get("preview_schema_version") or "") != PREVIEW_SCHEMA_VERSION,
            str(result.get("rule_schema_version") or "") != CANONICAL_RULE_SCHEMA(eligibility),
            str(result.get("rule_fingerprint") or "") != str(eligibility.get("rule_fingerprint") or ""),
            str(result.get("certification_fingerprint") or "") != str(eligibility.get("certification_fingerprint") or ""),
            str(result.get("document_id") or "") != str(eligibility.get("document_id") or ""),
            str(result.get("source_revision") or "") != str(eligibility.get("source_revision") or ""),
            str(result.get("fast_lane_contract_id") or "") != str(eligibility.get("fast_lane_contract_id") or ""),
            int(result.get("fast_lane_contract_version") or 0) != int(eligibility.get("fast_lane_contract_version") or 0),
            str(result.get("fast_lane_capability_fingerprint") or "") != str(eligibility.get("capability_fingerprint") or ""),
            str(result.get("compatibility_evaluator_fingerprint") or "") != str(eligibility.get("compatibility_evaluator_fingerprint") or ""),
        ]
    )


def _read_only_snapshots(rule: Mapping[str, Any], certification: Mapping[str, Any], source_context: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, str]:
    return {
        "rule": json.dumps(rule, sort_keys=True),
        "certification": json.dumps(certification, sort_keys=True),
        "source_context": json.dumps(source_context, sort_keys=True),
        "manifest": json.dumps(manifest, sort_keys=True),
    }


def _preview_status(compatibility: Mapping[str, Any], mutation_detected: bool) -> str:
    if mutation_detected:
        return "mutation_detected"
    overall = str(compatibility.get("overall_status") or "unknown")
    if overall == "compatible":
        return "completed"
    if overall == "compatible_with_warnings":
        return "completed_with_warnings"
    if overall == "partially_compatible":
        return "partially_compatible"
    if overall == "incompatible":
        return "incompatible"
    if overall == "blocked":
        return "blocked"
    return "corrupt" if overall == "unknown" else overall


def _result_fingerprint(plan: Mapping[str, Any], compatibility: Mapping[str, Any], preview_status: str) -> str:
    return _hash_payload(
        {
            "schema_version": RESULT_SCHEMA,
            "plan_fingerprint": plan.get("plan_fingerprint"),
            "compatibility_result": compatibility,
            "preview_status": preview_status,
        }
    )


def _dimension_counts(result: Mapping[str, Any]) -> dict[str, Any]:
    dimensions = list(result.get("dimension_results", []) or [])
    compatible_count = sum(1 for item in dimensions if str(item.get("status") or "") == "compatible")
    warning_count = sum(1 for item in dimensions if str(item.get("status") or "") == "compatible_with_warning")
    incompatible_count = sum(1 for item in dimensions if str(item.get("status") or "") in {"incompatible", "blocked"})
    blocker_count = len(list(result.get("blockers", []) or []))
    top_warning_count = len(list(result.get("warnings", []) or []))
    return {
        "compatible_dimension_count": compatible_count,
        "warning_dimension_count": warning_count,
        "incompatible_dimension_count": incompatible_count,
        "blocker_count": blocker_count,
        "warning_count": top_warning_count,
    }


def _recommended_action(result: Mapping[str, Any]) -> str:
    preview_status = str(result.get("preview_status") or "")
    if preview_status == "completed":
        return "Review the compatibility preview receipt and report."
    if preview_status == "completed_with_warnings":
        return "Review warnings before any later authorization work."
    if preview_status in {"partially_compatible", "incompatible"}:
        return "Do not execute Fast Lane; resolve unsupported semantics first."
    if preview_status == "stale":
        return "Rebuild the preview against the current rule and contract."
    return "Resolve lifecycle, provenance, or manifest blockers first."


def _plan_summary(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "canonical_rule_id": plan.get("canonical_rule_id"),
        "document_id": plan.get("document_id"),
        "source_revision": plan.get("source_revision"),
        "fast_lane_contract_id": plan.get("fast_lane_contract_id"),
        "fast_lane_contract_version": plan.get("fast_lane_contract_version"),
        "preview_mode": plan.get("preview_mode"),
        "warnings": list(plan.get("warnings", [])),
        "blockers": list(plan.get("blockers", [])),
    }


def CANONICAL_RULE_SCHEMA(eligibility: Mapping[str, Any] | None) -> str:
    return "canonical_mutable_rule_v1"


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in items if str(item)))
