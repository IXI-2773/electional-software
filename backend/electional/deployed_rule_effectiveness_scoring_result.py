from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from . import deployed_rule_effectiveness_scoring_contract as contract_backend
from . import deployed_rule_effectiveness_scoring_dry_run as dry_run_backend
from .canonical_rule_runtime import _atomic_write_json, _hash_payload, _now, _read_json, _restore_json, _safe_id
from .source_documents import SOURCE_DOCUMENT_ROOT

PLAN_DIR = "deployed_rule_effectiveness_scoring_result/plans"
RESULT_DIR = "deployed_rule_effectiveness_scoring_result/results"
RECEIPT_DIR = "deployed_rule_effectiveness_scoring_result/receipts"
PLAN_INDEX = "deployed_rule_effectiveness_scoring_result_plan_index.json"
RESULT_INDEX = "deployed_rule_effectiveness_scoring_result_index.json"
RECEIPT_INDEX = "deployed_rule_effectiveness_scoring_result_receipt_index.json"

MANIFEST_SCHEMA_VERSION = "deployed_rule_effectiveness_scoring_result_manifest_v1"
WORKSPACE_SCHEMA_VERSION = "deployed_rule_effectiveness_scoring_result_workspace_v1"
PLAN_SCHEMA_VERSION = "deployed_rule_effectiveness_scoring_result_plan_v1"
RESULT_SCHEMA_VERSION = "deployed_rule_effectiveness_scoring_result_v1"
RECEIPT_SCHEMA_VERSION = "deployed_rule_effectiveness_scoring_result_receipt_v1"
RESULT_SCHEMA_FAMILY = "deployed_rule_effectiveness_scoring_result_family_v1"
REQUIRED_CONFIRMATION = "RECORD_EFFECTIVENESS_SCORING_RESULT"
AUTHORITY_SCOPE = "registered_outcome_truth_exact_match_accuracy_like"
REQUESTED_METRIC_FAMILIES = ["accuracy_like_contract"]
FORBIDDEN_GENERIC_SCORE_FIELDS = {
    "effectiveness_score",
    "correctness_score",
    "success_rate",
    "failure_rate",
    "production_score",
    "profitability_score",
    "prediction_quality_score",
    "deployment_safety_score",
}
BOUNDARY_FALSE_FLAGS = {
    "deployment_safety_claimed": False,
    "production_correctness_claimed": False,
    "profitability_claimed": False,
    "prediction_quality_claimed": False,
    "phase9w_used_as_scoring_input": False,
    "runtime_completion_used_as_correctness": False,
    "source_availability_used_as_effectiveness": False,
}

__all__ = [
    "build_deployed_rule_effectiveness_scoring_result_summary_surface",
    "build_deployed_rule_effectiveness_scoring_result_public_safe_export_pack",
    "get_deployed_rule_effectiveness_scoring_result_manifest",
    "build_deployed_rule_effectiveness_scoring_result_workspace",
    "validate_deployed_rule_effectiveness_scoring_result_eligibility",
    "build_deployed_rule_effectiveness_scoring_result_plan",
    "record_deployed_rule_effectiveness_scoring_result",
    "load_deployed_rule_effectiveness_scoring_result",
    "get_deployed_rule_effectiveness_scoring_result_health",
    "format_deployed_rule_effectiveness_scoring_result_report",
    "format_deployed_rule_effectiveness_scoring_result_public_safe_export_report",
    "format_deployed_rule_effectiveness_scoring_result_summary_surface_report",
]


def get_deployed_rule_effectiveness_scoring_result_manifest(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "scoring_result_schema_version": RESULT_SCHEMA_FAMILY,
        "required_confirmation": REQUIRED_CONFIRMATION,
        "authority_scope": AUTHORITY_SCOPE,
        "persisted_metric_families": list(REQUESTED_METRIC_FAMILIES),
        "generic_effectiveness_score_supported": False,
        "correctness_score_supported": False,
        "rates_supported": False,
        "persistence_root": str(root),
    }


def build_deployed_rule_effectiveness_scoring_result_summary_surface(
    scoring_result_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = Path(root)
    results = _load_all(base / RESULT_DIR)
    authority_scope_counts: dict[str, int] = {}
    score_family_counts: dict[str, int] = {}
    valid_result_count = 0
    corrupt_result_count = 0
    for item in results:
        loaded = load_deployed_rule_effectiveness_scoring_result(
            str(item.get("effectiveness_scoring_result_id") or ""),
            root=base,
        )
        if str(loaded.get("status") or "") == "corrupt":
            corrupt_result_count += 1
        else:
            valid_result_count += 1
        scope = str(item.get("authority_scope") or "unknown")
        authority_scope_counts[scope] = authority_scope_counts.get(scope, 0) + 1
        family = str(item.get("persisted_metric_family") or "unknown")
        score_family_counts[family] = score_family_counts.get(family, 0) + 1
    blockers: list[str] = []
    warnings: list[str] = []
    loaded_result_summary: dict[str, Any] | None = None
    status = "healthy"
    if scoring_result_id:
        loaded = load_deployed_rule_effectiveness_scoring_result(scoring_result_id, root=base)
        loaded_status = str(loaded.get("status") or "unknown")
        if loaded_status == "corrupt":
            status = "corrupt"
            blockers.extend(list(loaded.get("blockers", [])) if isinstance(loaded.get("blockers"), list) else [])
            loaded_result_summary = {
                "scoring_result_id": scoring_result_id,
                "status": "corrupt",
                "authority_scope": "unknown",
                "score_family": "unknown",
                **BOUNDARY_FALSE_FLAGS,
            }
        elif loaded_status == "blocked":
            status = "blocked"
            blockers.extend(list(loaded.get("blockers", [])) if isinstance(loaded.get("blockers"), list) else [])
        else:
            payload = loaded.get("effectiveness_scoring_result") if isinstance(loaded, Mapping) else None
            if isinstance(payload, Mapping):
                loaded_result_summary = _loaded_result_summary(payload)
                status = "healthy"
    if corrupt_result_count:
        status = "corrupt" if status == "healthy" else status
    return {
        "summary_schema_version": "deployed_rule_effectiveness_scoring_result_summary_surface_v1",
        "status": status,
        "health_scope": "repository-wide",
        "total_result_count": len(results),
        "valid_result_count": valid_result_count,
        "corrupt_result_count": corrupt_result_count,
        "blocked_result_count": 0,
        "authority_scope_counts": authority_scope_counts,
        "score_family_counts": score_family_counts,
        "loaded_result_summary": loaded_result_summary,
        "blockers": _dedupe(blockers),
        "warnings": _dedupe(warnings),
        "recommended_action": "Review corrupt persisted scoring-result records before using them as scoped authority." if blockers else "Load one persisted scoring result when you need a scoped read-only summary.",
        "writes_performed": 0,
    }


def build_deployed_rule_effectiveness_scoring_result_public_safe_export_pack(
    scoring_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    safe_scoring_result_id = str(scoring_result_id or "").strip()
    if not safe_scoring_result_id:
        return {
            "export_schema_version": "deployed_rule_effectiveness_scoring_result_public_safe_export_pack_v1",
            "status": "blocked",
            "public_safe": True,
            "writes_performed": 0,
            "scoring_result_id": "",
            "authority_scope": AUTHORITY_SCOPE,
            "persisted_metric_family": "accuracy_like_contract",
            "persisted_scoring_fields": None,
            "boundary_flags": dict(BOUNDARY_FALSE_FLAGS),
            "limitation_notes": _public_safe_export_limitations(),
            "warnings": [],
            "blockers": ["scoring_result_id_required"],
            "recommended_action": "Provide a persisted scoring-result ID before loading the public-safe export pack.",
        }
    loaded = load_deployed_rule_effectiveness_scoring_result(safe_scoring_result_id, root=root)
    status = str(loaded.get("status") or "unknown")
    if status == "blocked":
        return {
            "export_schema_version": "deployed_rule_effectiveness_scoring_result_public_safe_export_pack_v1",
            "status": "blocked",
            "public_safe": True,
            "writes_performed": 0,
            "scoring_result_id": safe_scoring_result_id,
            "authority_scope": AUTHORITY_SCOPE,
            "persisted_metric_family": "accuracy_like_contract",
            "persisted_scoring_fields": None,
            "boundary_flags": dict(BOUNDARY_FALSE_FLAGS),
            "limitation_notes": _public_safe_export_limitations(),
            "warnings": list(loaded.get("warnings", [])) if isinstance(loaded.get("warnings"), list) else [],
            "blockers": list(loaded.get("blockers", [])) if isinstance(loaded.get("blockers"), list) else [],
            "recommended_action": "Record or load a valid persisted scoring result before exporting a public-safe pack.",
        }
    if status == "corrupt":
        payload = loaded.get("effectiveness_scoring_result") if isinstance(loaded, Mapping) else None
        return {
            "export_schema_version": "deployed_rule_effectiveness_scoring_result_public_safe_export_pack_v1",
            "status": "corrupt",
            "public_safe": True,
            "writes_performed": 0,
            "scoring_result_id": safe_scoring_result_id,
            "authority_scope": AUTHORITY_SCOPE,
            "persisted_metric_family": "accuracy_like_contract",
            "persisted_scoring_fields": None,
            "result_fingerprint": str(payload.get("result_fingerprint") or "") if isinstance(payload, Mapping) else "",
            "boundary_flags": dict(BOUNDARY_FALSE_FLAGS),
            "limitation_notes": _public_safe_export_limitations(),
            "warnings": list(loaded.get("warnings", [])) if isinstance(loaded.get("warnings"), list) else [],
            "blockers": list(loaded.get("blockers", [])) if isinstance(loaded.get("blockers"), list) else [],
            "recommended_action": "Do not use corrupt persisted scoring results as public-safe scoring authority.",
        }
    payload = loaded.get("effectiveness_scoring_result") if isinstance(loaded, Mapping) else None
    if not isinstance(payload, Mapping):
        return {
            "export_schema_version": "deployed_rule_effectiveness_scoring_result_public_safe_export_pack_v1",
            "status": "unknown",
            "public_safe": True,
            "writes_performed": 0,
            "scoring_result_id": safe_scoring_result_id,
            "authority_scope": AUTHORITY_SCOPE,
            "persisted_metric_family": "accuracy_like_contract",
            "persisted_scoring_fields": None,
            "boundary_flags": dict(BOUNDARY_FALSE_FLAGS),
            "limitation_notes": _public_safe_export_limitations(),
            "warnings": [],
            "blockers": ["effectiveness_scoring_result_payload_unavailable"],
            "recommended_action": "Reload the persisted scoring result before exporting a public-safe pack.",
        }
    persisted = _loaded_result_summary(payload)
    return {
        "export_schema_version": "deployed_rule_effectiveness_scoring_result_public_safe_export_pack_v1",
        "status": "export_ready",
        "public_safe": True,
        "writes_performed": 0,
        "scoring_result_id": persisted["scoring_result_id"],
        "result_fingerprint": str(payload.get("result_fingerprint") or ""),
        "authority_scope": persisted["authority_scope"],
        "persisted_metric_family": persisted["score_family"],
        "persisted_scoring_fields": {
            "persisted_accuracy_like_score_ratio": persisted["persisted_accuracy_like_score_ratio"],
            "persisted_accuracy_like_score_percentage": persisted["persisted_accuracy_like_score_percentage"],
            "exact_match_count": persisted["exact_match_count"],
            "mismatch_count": persisted["mismatch_count"],
            "denominator_count": persisted["denominator_count"],
            "eligible_record_count": persisted["eligible_record_count"],
            "excluded_record_count": persisted["excluded_record_count"],
            "duplicate_collapsed_count": persisted["duplicate_collapsed_count"],
            "conflict_count": persisted["conflict_count"],
        },
        "boundary_flags": {flag: persisted[flag] for flag in BOUNDARY_FALSE_FLAGS},
        "limitation_notes": _public_safe_export_limitations(),
        "warnings": [],
        "blockers": [],
        "recommended_action": "Use this export pack as a public-safe read-only summary of the persisted scoped scoring result.",
    }


def build_deployed_rule_effectiveness_scoring_result_workspace(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result_id: str,
    effectiveness_spec_result_id: str,
    outcome_truth_source_result_id: str,
    outcome_truth_record_set_id: str,
    scoring_contract_result_id: str,
    observation_window_start: str,
    observation_window_end: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    context = _scoring_result_context(
        canonical_rule_id=canonical_rule_id,
        production_deployment_result_id=production_deployment_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
        telemetry_snapshot_id=telemetry_snapshot_id,
        readiness_result_id=readiness_result_id,
        effectiveness_spec_result_id=effectiveness_spec_result_id,
        outcome_truth_source_result_id=outcome_truth_source_result_id,
        outcome_truth_record_set_id=outcome_truth_record_set_id,
        scoring_contract_result_id=scoring_contract_result_id,
        observation_window_start=observation_window_start,
        observation_window_end=observation_window_end,
        root=root,
    )
    return _workspace_payload(context)


def validate_deployed_rule_effectiveness_scoring_result_eligibility(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result_id: str,
    effectiveness_spec_result_id: str,
    outcome_truth_source_result_id: str,
    outcome_truth_record_set_id: str,
    scoring_contract_result_id: str,
    observation_window_start: str,
    observation_window_end: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    context = _scoring_result_context(
        canonical_rule_id=canonical_rule_id,
        production_deployment_result_id=production_deployment_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
        telemetry_snapshot_id=telemetry_snapshot_id,
        readiness_result_id=readiness_result_id,
        effectiveness_spec_result_id=effectiveness_spec_result_id,
        outcome_truth_source_result_id=outcome_truth_source_result_id,
        outcome_truth_record_set_id=outcome_truth_record_set_id,
        scoring_contract_result_id=scoring_contract_result_id,
        observation_window_start=observation_window_start,
        observation_window_end=observation_window_end,
        root=root,
    )
    return _eligibility_payload(context)


def build_deployed_rule_effectiveness_scoring_result_plan(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result_id: str,
    effectiveness_spec_result_id: str,
    outcome_truth_source_result_id: str,
    outcome_truth_record_set_id: str,
    scoring_contract_result_id: str,
    observation_window_start: str,
    observation_window_end: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    context = _scoring_result_context(
        canonical_rule_id=canonical_rule_id,
        production_deployment_result_id=production_deployment_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
        telemetry_snapshot_id=telemetry_snapshot_id,
        readiness_result_id=readiness_result_id,
        effectiveness_spec_result_id=effectiveness_spec_result_id,
        outcome_truth_source_result_id=outcome_truth_source_result_id,
        outcome_truth_record_set_id=outcome_truth_record_set_id,
        scoring_contract_result_id=scoring_contract_result_id,
        observation_window_start=observation_window_start,
        observation_window_end=observation_window_end,
        root=base,
    )
    plan = _plan_payload(context)
    path = _plan_path(base, str(plan["effectiveness_scoring_result_plan_id"]))
    existing = _read_json(path)
    if isinstance(existing, Mapping):
        if str(existing.get("plan_fingerprint") or "") == str(plan.get("plan_fingerprint") or ""):
            return {
                "status": "planned",
                "effectiveness_scoring_result_plan_id": plan["effectiveness_scoring_result_plan_id"],
                "writes_performed": 0,
                **_plan_summary(existing),
            }
        return {
            "status": "corrupt",
            "effectiveness_scoring_result_plan_id": plan["effectiveness_scoring_result_plan_id"],
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["effectiveness_scoring_result_plan_divergence"],
        }
    before_plan = _read_json(path)
    before_index = _read_json(base / "indexes" / PLAN_INDEX)
    try:
        _atomic_write_json(path, plan)
        _update_plan_index(base)
    except Exception:
        _restore_json(path, before_plan)
        _restore_json(base / "indexes" / PLAN_INDEX, before_index)
        return {
            "status": "corrupt",
            "effectiveness_scoring_result_plan_id": plan["effectiveness_scoring_result_plan_id"],
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["effectiveness_scoring_result_plan_write_failure"],
        }
    return {
        "status": "planned",
        "effectiveness_scoring_result_plan_id": plan["effectiveness_scoring_result_plan_id"],
        "writes_performed": 1,
        **_plan_summary(plan),
    }


def record_deployed_rule_effectiveness_scoring_result(
    effectiveness_scoring_result_plan_id: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    # Recording is deliberately confirmation-gated because persisted scoring results
    # are authoritative storage, not just another dry-run view.
    if confirmation != REQUIRED_CONFIRMATION:
        return {
            "status": "blocked",
            "effectiveness_scoring_result_plan_id": effectiveness_scoring_result_plan_id,
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["scoring_result_confirmation_exact_match_required"],
        }
    plan = _read_json(_plan_path(base, effectiveness_scoring_result_plan_id))
    if not isinstance(plan, Mapping):
        return {
            "status": "blocked",
            "effectiveness_scoring_result_plan_id": effectiveness_scoring_result_plan_id,
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["scoring_result_plan_id_required"],
        }
    context = _scoring_result_context(
        canonical_rule_id=str(plan.get("canonical_rule_id") or ""),
        production_deployment_result_id=str(plan.get("production_deployment_result_id") or ""),
        production_target_id=str(plan.get("production_target_id") or ""),
        deployed_rule_id=str(plan.get("deployed_rule_id") or ""),
        telemetry_snapshot_id=str(plan.get("telemetry_snapshot_id") or ""),
        readiness_result_id=str(plan.get("readiness_result_id") or ""),
        effectiveness_spec_result_id=str(plan.get("effectiveness_spec_result_id") or ""),
        outcome_truth_source_result_id=str(plan.get("outcome_truth_source_result_id") or ""),
        outcome_truth_record_set_id=str(plan.get("outcome_truth_record_set_id") or ""),
        scoring_contract_result_id=str(plan.get("scoring_contract_result_id") or ""),
        observation_window_start=str(plan.get("observation_window_start") or ""),
        observation_window_end=str(plan.get("observation_window_end") or ""),
        root=base,
    )
    current_plan = _plan_payload(context)
    if str(current_plan.get("plan_fingerprint") or "") != str(plan.get("plan_fingerprint") or ""):
        return {
            "status": "stale",
            "effectiveness_scoring_result_plan_id": effectiveness_scoring_result_plan_id,
            "writes_performed": 0,
            "warnings": list(context["warnings"]),
            "blockers": ["effectiveness_scoring_result_plan_stale"],
        }
    result_id = _result_id(effectiveness_scoring_result_plan_id)
    receipt_id = _receipt_id(result_id)
    result = _result_payload(context, effectiveness_scoring_result_plan_id, result_id, receipt_id)
    receipt = _receipt_payload(result, receipt_id)
    existing = _read_json(_result_path(base, result_id))
    if isinstance(existing, Mapping):
        if str(existing.get("result_fingerprint") or "") == str(result.get("result_fingerprint") or ""):
            return {
                "status": "already_recorded",
                "effectiveness_scoring_result_id": result_id,
                "writes_performed": 0,
                **_result_summary(existing),
            }
        return {
            "status": "corrupt",
            "effectiveness_scoring_result_id": result_id,
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["effectiveness_scoring_result_conflict"],
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
        return {
            "status": "corrupt",
            "effectiveness_scoring_result_id": result_id,
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["effectiveness_scoring_result_write_failure"],
        }
    return {
        "status": "recorded",
        "effectiveness_scoring_result_id": result_id,
        "writes_performed": 2,
        **_result_summary(result),
    }


def load_deployed_rule_effectiveness_scoring_result(
    effectiveness_scoring_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = Path(root)
    payload = _read_json(_result_path(base, effectiveness_scoring_result_id))
    if not isinstance(payload, Mapping):
        return {
            "status": "blocked",
            "warnings": [],
            "blockers": ["effectiveness_scoring_result_missing"],
            "effectiveness_scoring_result_id": effectiveness_scoring_result_id,
        }
    receipt_id = str(payload.get("effectiveness_scoring_result_receipt_id") or "")
    receipt = _read_json(_receipt_path(base, receipt_id)) if receipt_id else None
    integrity_blockers = _result_integrity_blockers(payload, receipt)
    if integrity_blockers:
        return {
            "status": "corrupt",
            "effectiveness_scoring_result": dict(payload),
            "warnings": [],
            "blockers": integrity_blockers,
        }
    return {
        "status": str(payload.get("result_status") or "loaded"),
        "effectiveness_scoring_result": dict(payload),
        "warnings": [],
        "blockers": [],
    }


def get_deployed_rule_effectiveness_scoring_result_health(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = Path(root)
    plans = _load_all(base / PLAN_DIR)
    results = _load_all(base / RESULT_DIR)
    receipts = _load_all(base / RECEIPT_DIR)
    blockers: list[str] = []
    receipt_lookup = {
        str(item.get("effectiveness_scoring_result_receipt_id") or ""): item
        for item in receipts
        if str(item.get("effectiveness_scoring_result_receipt_id") or "")
    }
    if len(results) != len(receipts):
        blockers.append("effectiveness_scoring_result_receipt_mismatch")
    if len({str(item.get("effectiveness_scoring_result_id") or "") for item in results}) != len(results):
        blockers.append("duplicate_effectiveness_scoring_result_ids")
    if len(receipt_lookup) != len(receipts):
        blockers.append("duplicate_effectiveness_scoring_result_receipt_ids")
    for item in results:
        blockers.extend(_result_integrity_blockers(item, receipt_lookup.get(str(item.get("effectiveness_scoring_result_receipt_id") or ""))))
    return {
        "status": "healthy" if not blockers else "corrupt",
        "plan_count": len(plans),
        "result_count": len(results),
        "receipt_count": len(receipts),
        "authority_scope": AUTHORITY_SCOPE,
        "warnings": [],
        "blockers": blockers,
    }


def format_deployed_rule_effectiveness_scoring_result_report(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result_id: str,
    effectiveness_spec_result_id: str,
    outcome_truth_source_result_id: str,
    outcome_truth_record_set_id: str,
    scoring_contract_result_id: str,
    observation_window_start: str,
    observation_window_end: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    result = build_deployed_rule_effectiveness_scoring_result_workspace(
        canonical_rule_id,
        production_deployment_result_id,
        production_target_id,
        deployed_rule_id,
        telemetry_snapshot_id,
        readiness_result_id,
        effectiveness_spec_result_id,
        outcome_truth_source_result_id,
        outcome_truth_record_set_id,
        scoring_contract_result_id,
        observation_window_start,
        observation_window_end,
        root=root,
    )
    lines = [
        "Persisted scoped accuracy-like exact-match scoring result",
        f"Status: {result.get('status')}",
        f"Authority scope: {result.get('authority_scope')}",
        "Authority scope is limited to registered outcome-truth exact-match accuracy-like evidence.",
        "Only registered outcome-truth exact-match accuracy-like fields are persisted.",
        "No generic effectiveness score is produced.",
        "This is not deployment safety.",
        "This is not broad production correctness.",
        "This is not profitability.",
        "This is not prediction quality.",
        "Phase 9W acceptance was not used as scoring input.",
        "Runtime completion was not used as correctness.",
        "Source availability alone was not used as effectiveness.",
        f"Exact-match count: {result.get('exact_match_count', 0)}",
        f"Mismatch count: {result.get('mismatch_count', 0)}",
        f"Denominator count: {result.get('denominator_count', 0)}",
        f"Persisted accuracy-like score ratio: {result.get('persisted_accuracy_like_score_ratio')}",
        f"Persisted accuracy-like score percentage: {result.get('persisted_accuracy_like_score_percentage')}",
    ]
    blockers = result.get("blockers", [])
    warnings = result.get("warnings", [])
    if isinstance(blockers, list) and blockers:
        lines.append("Blockers: " + ", ".join(str(item) for item in blockers))
    if isinstance(warnings, list) and warnings:
        lines.append("Warnings: " + ", ".join(str(item) for item in warnings))
    return "\n".join(lines)


def format_deployed_rule_effectiveness_scoring_result_summary_surface_report(
    scoring_result_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    summary = build_deployed_rule_effectiveness_scoring_result_summary_surface(
        scoring_result_id=scoring_result_id,
        root=root,
    )
    lines = [
        "Read-only persisted scoped accuracy-like exact-match scoring result summary",
        f"Status: {summary.get('status')}",
        f"Health scope: {summary.get('health_scope')}",
        f"Total result count: {summary.get('total_result_count', 0)}",
        f"Valid result count: {summary.get('valid_result_count', 0)}",
        f"Corrupt result count: {summary.get('corrupt_result_count', 0)}",
        f"Blocked result count: {summary.get('blocked_result_count', 0)}",
        f"Authority scope counts: {summary.get('authority_scope_counts', {})}",
        f"Score family counts: {summary.get('score_family_counts', {})}",
        "Authority scope is limited to registered outcome-truth exact-match accuracy-like evidence.",
        "Scoped persisted score fields are not broad effectiveness.",
        "This is not deployment safety.",
        "This is not broad production correctness.",
        "This is not profitability.",
        "This is not prediction quality.",
        "Phase 9W acceptance was not used as scoring input.",
        "Runtime completion was not used as correctness.",
        "Source availability alone was not used as effectiveness.",
        "Corrupt records are not valid authority.",
        "No new score was calculated by the summary.",
    ]
    loaded = summary.get("loaded_result_summary")
    if isinstance(loaded, Mapping):
        lines.extend(
            [
                f"Loaded result status: {loaded.get('status', 'unknown')}",
                f"Loaded result authority scope: {loaded.get('authority_scope', 'unknown')}",
                f"Loaded result score family: {loaded.get('score_family', 'unknown')}",
                f"Persisted accuracy-like score ratio: {loaded.get('persisted_accuracy_like_score_ratio', 'unknown')}",
                f"Persisted accuracy-like score percentage: {loaded.get('persisted_accuracy_like_score_percentage', 'unknown')}",
                f"Exact match count: {loaded.get('exact_match_count', 0)}",
                f"Mismatch count: {loaded.get('mismatch_count', 0)}",
                f"Denominator count: {loaded.get('denominator_count', 0)}",
            ]
        )
    blockers = summary.get("blockers", [])
    warnings = summary.get("warnings", [])
    if isinstance(blockers, list) and blockers:
        lines.append("Blockers: " + ", ".join(str(item) for item in blockers))
    if isinstance(warnings, list) and warnings:
        lines.append("Warnings: " + ", ".join(str(item) for item in warnings))
    return "\n".join(lines)


def format_deployed_rule_effectiveness_scoring_result_public_safe_export_report(
    scoring_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    export_pack = build_deployed_rule_effectiveness_scoring_result_public_safe_export_pack(
        scoring_result_id,
        root=root,
    )
    lines = [
        "Public-safe export pack for persisted scoped accuracy-like exact-match scoring result",
        f"Status: {export_pack.get('status')}",
        f"Scoring Result ID: {export_pack.get('scoring_result_id') or 'none'}",
        f"Authority scope: {export_pack.get('authority_scope')}",
        f"Persisted metric family: {export_pack.get('persisted_metric_family')}",
        "Authority scope is limited to registered outcome-truth exact-match accuracy-like evidence.",
        "No effectiveness score was calculated.",
        "Runtime completion is not correctness.",
        "Phase 9W acceptance is not outcome truth.",
        "Source availability alone is not effectiveness.",
        "This export pack does not claim deployment safety, profitability, or prediction quality.",
    ]
    persisted_fields = export_pack.get("persisted_scoring_fields")
    if isinstance(persisted_fields, Mapping):
        lines.extend(
            [
                f"Persisted accuracy-like score ratio: {persisted_fields.get('persisted_accuracy_like_score_ratio')}",
                f"Persisted accuracy-like score percentage: {persisted_fields.get('persisted_accuracy_like_score_percentage')}",
                f"Exact match count: {persisted_fields.get('exact_match_count', 0)}",
                f"Mismatch count: {persisted_fields.get('mismatch_count', 0)}",
                f"Denominator count: {persisted_fields.get('denominator_count', 0)}",
                f"Eligible record count: {persisted_fields.get('eligible_record_count', 0)}",
                f"Excluded record count: {persisted_fields.get('excluded_record_count', 0)}",
                f"Duplicate collapsed count: {persisted_fields.get('duplicate_collapsed_count', 0)}",
                f"Conflict count: {persisted_fields.get('conflict_count', 0)}",
            ]
        )
    lines.append("Limitation notes: " + "; ".join(_public_safe_export_limitations()))
    blockers = export_pack.get("blockers", [])
    warnings = export_pack.get("warnings", [])
    if isinstance(blockers, list) and blockers:
        lines.append("Blockers: " + ", ".join(str(item) for item in blockers))
    if isinstance(warnings, list) and warnings:
        lines.append("Warnings: " + ", ".join(str(item) for item in warnings))
    return "\n".join(lines)


def _scoring_result_context(
    *,
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result_id: str,
    effectiveness_spec_result_id: str,
    outcome_truth_source_result_id: str,
    outcome_truth_record_set_id: str,
    scoring_contract_result_id: str,
    observation_window_start: str,
    observation_window_end: str,
    root: Path | str,
) -> dict[str, Any]:
    base = Path(root)
    contract_result_path = base / contract_backend.RESULT_DIR / f"{_safe_id(scoring_contract_result_id)}.json"
    if not contract_result_path.exists():
        return {
            "status": "blocked",
            "canonical_rule_id": canonical_rule_id,
            "production_deployment_result_id": production_deployment_result_id,
            "production_target_id": production_target_id,
            "deployed_rule_id": deployed_rule_id,
            "telemetry_snapshot_id": telemetry_snapshot_id,
            "readiness_result_id": readiness_result_id,
            "effectiveness_spec_result_id": effectiveness_spec_result_id,
            "outcome_truth_source_result_id": outcome_truth_source_result_id,
            "outcome_truth_record_set_id": outcome_truth_record_set_id,
            "scoring_contract_result_id": scoring_contract_result_id,
            "observation_window_start": observation_window_start,
            "observation_window_end": observation_window_end,
            "authority_scope": AUTHORITY_SCOPE,
            "requested_metric_families": list(REQUESTED_METRIC_FAMILIES),
            "dry_run_fingerprint": "",
            "dry_run_result": {},
            "persisted_accuracy_like_score_ratio": None,
            "persisted_accuracy_like_score_percentage": None,
            "exact_match_count": 0,
            "mismatch_count": 0,
            "denominator_count": 0,
            "warnings": [],
            "blockers": ["scoring_contract_result_missing", "dry_run_not_ready_for_persisted_scoring_result", "accuracy_like_dry_run_missing", "candidate_accuracy_like_summary_missing"],
            "contract_result_fingerprint": "",
            "recommended_action": "Resolve scoring-result blockers before recording any persisted scoring result.",
        }
    contract_loaded = contract_backend.load_deployed_rule_effectiveness_scoring_contract_result(
        scoring_contract_result_id,
        root=root,
    )
    contract_result = contract_loaded.get("effectiveness_scoring_contract_result") if isinstance(contract_loaded, Mapping) else None
    blockers: list[str] = []
    warnings: list[str] = []
    if not isinstance(contract_result, Mapping):
        blockers.append("scoring_contract_result_missing")
    else:
        if str(contract_result.get("scoring_contract_status") or "") != "scoring_contract_ready_for_engine_design":
            blockers.append("scoring_contract_result_not_ready")
        for key, expected in {
            "canonical_rule_id": canonical_rule_id,
            "production_deployment_result_id": production_deployment_result_id,
            "production_target_id": production_target_id,
            "deployed_rule_id": deployed_rule_id,
            "telemetry_snapshot_id": telemetry_snapshot_id,
            "readiness_result_id": readiness_result_id,
            "effectiveness_spec_result_id": effectiveness_spec_result_id,
            "outcome_truth_source_result_id": outcome_truth_source_result_id,
            "outcome_truth_record_set_id": outcome_truth_record_set_id,
            "observation_window_start": observation_window_start,
            "observation_window_end": observation_window_end,
        }.items():
            if str(contract_result.get(key) or "") != expected:
                blockers.append(f"scoring_contract_result_binding_mismatch:{key}")
    dry_run = dry_run_backend.run_deployed_rule_effectiveness_scoring_dry_run(
        canonical_rule_id,
        production_deployment_result_id,
        production_target_id,
        deployed_rule_id,
        telemetry_snapshot_id,
        readiness_result_id,
        effectiveness_spec_result_id,
        outcome_truth_source_result_id,
        outcome_truth_record_set_id,
        scoring_contract_result_id,
        observation_window_start,
        observation_window_end,
        requested_metric_families=REQUESTED_METRIC_FAMILIES,
        root=root,
    )
    dry_run_status = str(dry_run.get("status") or "")
    if dry_run_status != "dry_run_ready":
        blockers.append("dry_run_not_ready_for_persisted_scoring_result")
    metric_result = (
        dry_run.get("metric_family_results", {}).get("accuracy_like_contract")
        if isinstance(dry_run.get("metric_family_results"), Mapping)
        else None
    )
    if not isinstance(metric_result, Mapping) or str(metric_result.get("status") or "") != "dry_run_calculated":
        blockers.append("accuracy_like_dry_run_missing")
    summary = dry_run.get("candidate_accuracy_like_summary")
    if not isinstance(summary, Mapping):
        blockers.append("candidate_accuracy_like_summary_missing")
        summary = {}
    result_status = "ready_to_record" if not blockers else "blocked"
    return {
        "status": result_status,
        "canonical_rule_id": canonical_rule_id,
        "production_deployment_result_id": production_deployment_result_id,
        "production_target_id": production_target_id,
        "deployed_rule_id": deployed_rule_id,
        "telemetry_snapshot_id": telemetry_snapshot_id,
        "readiness_result_id": readiness_result_id,
        "effectiveness_spec_result_id": effectiveness_spec_result_id,
        "outcome_truth_source_result_id": outcome_truth_source_result_id,
        "outcome_truth_record_set_id": outcome_truth_record_set_id,
        "scoring_contract_result_id": scoring_contract_result_id,
        "observation_window_start": observation_window_start,
        "observation_window_end": observation_window_end,
        "authority_scope": AUTHORITY_SCOPE,
        "requested_metric_families": list(REQUESTED_METRIC_FAMILIES),
        "dry_run_fingerprint": str(dry_run.get("dry_run_fingerprint") or ""),
        "dry_run_result": deepcopy(dry_run),
        "persisted_accuracy_like_score_ratio": summary.get("candidate_accuracy_ratio"),
        "persisted_accuracy_like_score_percentage": summary.get("candidate_accuracy_percentage"),
        "exact_match_count": summary.get("candidate_exact_match_count", 0),
        "mismatch_count": summary.get("candidate_mismatch_count", 0),
        "denominator_count": summary.get("candidate_denominator_count", 0),
        "warnings": _dedupe(warnings + list(dry_run.get("warnings", [])) if isinstance(dry_run.get("warnings"), list) else warnings),
        "blockers": _dedupe(blockers + list(dry_run.get("blockers", [])) if isinstance(dry_run.get("blockers"), list) else blockers),
        "contract_result_fingerprint": str((contract_result or {}).get("result_fingerprint") or ""),
        "recommended_action": "Record the scoped exact-match accuracy-like result only after explicit confirmation." if not blockers else "Resolve scoring-result blockers before recording any persisted scoring result.",
    }


def _workspace_payload(context: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": WORKSPACE_SCHEMA_VERSION,
        "status": context["status"],
        "authority_scope": context["authority_scope"],
        "requested_metric_families": list(context["requested_metric_families"]),
        "persisted_accuracy_like_score_ratio": context["persisted_accuracy_like_score_ratio"],
        "persisted_accuracy_like_score_percentage": context["persisted_accuracy_like_score_percentage"],
        "exact_match_count": context["exact_match_count"],
        "mismatch_count": context["mismatch_count"],
        "denominator_count": context["denominator_count"],
        "dry_run_fingerprint": context["dry_run_fingerprint"],
        "warnings": list(context["warnings"]),
        "blockers": list(context["blockers"]),
        "recommended_action": context["recommended_action"],
    }


def _eligibility_payload(context: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": context["status"],
        "authority_scope": context["authority_scope"],
        "persisted_accuracy_like_score_ratio": context["persisted_accuracy_like_score_ratio"],
        "persisted_accuracy_like_score_percentage": context["persisted_accuracy_like_score_percentage"],
        "exact_match_count": context["exact_match_count"],
        "mismatch_count": context["mismatch_count"],
        "denominator_count": context["denominator_count"],
        "dry_run_fingerprint": context["dry_run_fingerprint"],
        "warnings": list(context["warnings"]),
        "blockers": list(context["blockers"]),
        "recommended_action": context["recommended_action"],
    }


def _plan_payload(context: Mapping[str, Any]) -> dict[str, Any]:
    plan_id = _plan_id(context)
    payload = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "scoring_result_schema_version": RESULT_SCHEMA_FAMILY,
        "effectiveness_scoring_result_plan_id": plan_id,
        "canonical_rule_id": context["canonical_rule_id"],
        "production_deployment_result_id": context["production_deployment_result_id"],
        "production_target_id": context["production_target_id"],
        "deployed_rule_id": context["deployed_rule_id"],
        "telemetry_snapshot_id": context["telemetry_snapshot_id"],
        "readiness_result_id": context["readiness_result_id"],
        "effectiveness_spec_result_id": context["effectiveness_spec_result_id"],
        "outcome_truth_source_result_id": context["outcome_truth_source_result_id"],
        "outcome_truth_record_set_id": context["outcome_truth_record_set_id"],
        "scoring_contract_result_id": context["scoring_contract_result_id"],
        "observation_window_start": context["observation_window_start"],
        "observation_window_end": context["observation_window_end"],
        "authority_scope": context["authority_scope"],
        "requested_metric_families": list(context["requested_metric_families"]),
        "dry_run_fingerprint": context["dry_run_fingerprint"],
        "contract_result_fingerprint": context["contract_result_fingerprint"],
        "status": context["status"],
        "warnings": list(context["warnings"]),
        "blockers": list(context["blockers"]),
    }
    payload["plan_fingerprint"] = _hash_payload({key: payload.get(key) for key in sorted(payload) if key != "plan_fingerprint"})
    return payload


def _result_payload(context: Mapping[str, Any], plan_id: str, result_id: str, receipt_id: str) -> dict[str, Any]:
    payload = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "scoring_result_schema_version": RESULT_SCHEMA_FAMILY,
        "effectiveness_scoring_result_id": result_id,
        "effectiveness_scoring_result_plan_id": plan_id,
        "effectiveness_scoring_result_receipt_id": receipt_id,
        "result_status": "recorded",
        "authority_scope": context["authority_scope"],
        "canonical_rule_id": context["canonical_rule_id"],
        "production_deployment_result_id": context["production_deployment_result_id"],
        "production_target_id": context["production_target_id"],
        "deployed_rule_id": context["deployed_rule_id"],
        "telemetry_snapshot_id": context["telemetry_snapshot_id"],
        "readiness_result_id": context["readiness_result_id"],
        "effectiveness_spec_result_id": context["effectiveness_spec_result_id"],
        "outcome_truth_source_result_id": context["outcome_truth_source_result_id"],
        "outcome_truth_record_set_id": context["outcome_truth_record_set_id"],
        "scoring_contract_result_id": context["scoring_contract_result_id"],
        "observation_window_start": context["observation_window_start"],
        "observation_window_end": context["observation_window_end"],
        "requested_metric_families": list(context["requested_metric_families"]),
        "persisted_metric_family": "accuracy_like_contract",
        "persisted_accuracy_like_score_ratio": context["persisted_accuracy_like_score_ratio"],
        "persisted_accuracy_like_score_percentage": context["persisted_accuracy_like_score_percentage"],
        "exact_match_count": context["exact_match_count"],
        "mismatch_count": context["mismatch_count"],
        "denominator_count": context["denominator_count"],
        "dry_run_fingerprint": context["dry_run_fingerprint"],
        "contract_result_fingerprint": context["contract_result_fingerprint"],
        "recorded_at_utc": _now(),
        "warnings": list(context["warnings"]),
        "blockers": list(context["blockers"]),
        **BOUNDARY_FALSE_FLAGS,
    }
    payload["result_fingerprint"] = _hash_payload(
        {key: payload.get(key) for key in sorted(payload) if key not in {"result_fingerprint", "recorded_at_utc"}}
    )
    return payload


def _receipt_payload(result: Mapping[str, Any], receipt_id: str) -> dict[str, Any]:
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "scoring_result_schema_version": RESULT_SCHEMA_FAMILY,
        "effectiveness_scoring_result_receipt_id": receipt_id,
        "effectiveness_scoring_result_id": result["effectiveness_scoring_result_id"],
        "effectiveness_scoring_result_plan_id": result["effectiveness_scoring_result_plan_id"],
        "authority_scope": result["authority_scope"],
        "result_fingerprint": result["result_fingerprint"],
        "recorded_at_utc": result["recorded_at_utc"],
    }


def _plan_summary(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "plan_fingerprint": plan.get("plan_fingerprint"),
        "authority_scope": plan.get("authority_scope"),
        "warnings": list(plan.get("warnings", [])),
        "blockers": list(plan.get("blockers", [])),
    }


def _result_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "authority_scope": result.get("authority_scope"),
        "result_fingerprint": result.get("result_fingerprint"),
        "persisted_accuracy_like_score_ratio": result.get("persisted_accuracy_like_score_ratio"),
        "persisted_accuracy_like_score_percentage": result.get("persisted_accuracy_like_score_percentage"),
        "exact_match_count": result.get("exact_match_count"),
        "mismatch_count": result.get("mismatch_count"),
        "denominator_count": result.get("denominator_count"),
        "warnings": list(result.get("warnings", [])),
        "blockers": list(result.get("blockers", [])),
    }


def _loaded_result_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "scoring_result_id": str(result.get("effectiveness_scoring_result_id") or ""),
        "status": str(result.get("result_status") or "unknown"),
        "authority_scope": str(result.get("authority_scope") or "unknown"),
        "score_family": str(result.get("persisted_metric_family") or "unknown"),
        "persisted_accuracy_like_score_ratio": result.get("persisted_accuracy_like_score_ratio"),
        "persisted_accuracy_like_score_percentage": result.get("persisted_accuracy_like_score_percentage"),
        "exact_match_count": result.get("exact_match_count", 0),
        "mismatch_count": result.get("mismatch_count", 0),
        "denominator_count": result.get("denominator_count", 0),
        "eligible_record_count": result.get("eligible_record_count", 0),
        "excluded_record_count": result.get("excluded_record_count", 0),
        "duplicate_collapsed_count": result.get("duplicate_collapsed_count", 0),
        "conflict_count": result.get("conflict_count", 0),
        **BOUNDARY_FALSE_FLAGS,
    }


def _public_safe_export_limitations() -> list[str]:
    return [
        "Public-safe export packs are read-only and perform zero writes.",
        "Only persisted scoped exact-match accuracy-like fields are exposed.",
        "Raw outcome-truth payloads, telemetry payloads, local filesystem paths, stack traces, and raw JSON storage are excluded.",
        "Corrupt or missing persisted scoring results are not valid public-scoring authority.",
    ]


def _plan_id(context: Mapping[str, Any]) -> str:
    fingerprint = _hash_payload(
        {
            "canonical_rule_id": context["canonical_rule_id"],
            "production_deployment_result_id": context["production_deployment_result_id"],
            "production_target_id": context["production_target_id"],
            "deployed_rule_id": context["deployed_rule_id"],
            "telemetry_snapshot_id": context["telemetry_snapshot_id"],
            "readiness_result_id": context["readiness_result_id"],
            "effectiveness_spec_result_id": context["effectiveness_spec_result_id"],
            "outcome_truth_source_result_id": context["outcome_truth_source_result_id"],
            "outcome_truth_record_set_id": context["outcome_truth_record_set_id"],
            "scoring_contract_result_id": context["scoring_contract_result_id"],
            "observation_window_start": context["observation_window_start"],
            "observation_window_end": context["observation_window_end"],
            "authority_scope": context["authority_scope"],
        }
    )
    return f"deployed_rule_effectiveness_scoring_result_plan_{fingerprint[:24]}"


def _result_id(plan_id: str) -> str:
    return f"deployed_rule_effectiveness_scoring_result_{_safe_id(plan_id)[-24:]}"


def _receipt_id(result_id: str) -> str:
    return f"deployed_rule_effectiveness_scoring_result_receipt_{_safe_id(result_id)[-24:]}"


def _plan_path(base: Path, plan_id: str) -> Path:
    return base / PLAN_DIR / f"{_safe_id(plan_id)}.json"


def _result_path(base: Path, result_id: str) -> Path:
    return base / RESULT_DIR / f"{_safe_id(result_id)}.json"


def _receipt_path(base: Path, receipt_id: str) -> Path:
    return base / RECEIPT_DIR / f"{_safe_id(receipt_id)}.json"


def _update_plan_index(base: Path) -> None:
    items = [
        {
            "effectiveness_scoring_result_plan_id": item.get("effectiveness_scoring_result_plan_id"),
            "production_deployment_result_id": item.get("production_deployment_result_id"),
            "deployed_rule_id": item.get("deployed_rule_id"),
            "authority_scope": item.get("authority_scope"),
            "plan_fingerprint": item.get("plan_fingerprint"),
        }
        for item in _load_all(base / PLAN_DIR)
    ]
    _atomic_write_json(base / "indexes" / PLAN_INDEX, {"schema_version": "deployed_rule_effectiveness_scoring_result_plan_index_v1", "items": items, "updated_at_utc": _now()})


def _update_result_index(base: Path) -> None:
    items = [
        {
            "effectiveness_scoring_result_id": item.get("effectiveness_scoring_result_id"),
            "effectiveness_scoring_result_plan_id": item.get("effectiveness_scoring_result_plan_id"),
            "production_deployment_result_id": item.get("production_deployment_result_id"),
            "deployed_rule_id": item.get("deployed_rule_id"),
            "authority_scope": item.get("authority_scope"),
            "result_fingerprint": item.get("result_fingerprint"),
        }
        for item in _load_all(base / RESULT_DIR)
    ]
    _atomic_write_json(base / "indexes" / RESULT_INDEX, {"schema_version": "deployed_rule_effectiveness_scoring_result_index_v1", "items": items, "updated_at_utc": _now()})


def _update_receipt_index(base: Path) -> None:
    items = [
        {
            "effectiveness_scoring_result_receipt_id": item.get("effectiveness_scoring_result_receipt_id"),
            "effectiveness_scoring_result_id": item.get("effectiveness_scoring_result_id"),
            "authority_scope": item.get("authority_scope"),
        }
        for item in _load_all(base / RECEIPT_DIR)
    ]
    _atomic_write_json(base / "indexes" / RECEIPT_INDEX, {"schema_version": "deployed_rule_effectiveness_scoring_result_receipt_index_v1", "items": items, "updated_at_utc": _now()})


def _load_all(folder: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not folder.exists():
        return items
    for path in sorted(folder.glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping):
            items.append(dict(payload))
    return items


def _result_integrity_blockers(result: Mapping[str, Any], receipt: Mapping[str, Any] | None) -> list[str]:
    blockers: list[str] = []
    expected_fingerprint = _hash_payload(
        {key: result.get(key) for key in sorted(result) if key not in {"result_fingerprint", "recorded_at_utc"}}
    )
    if str(result.get("result_fingerprint") or "") != expected_fingerprint:
        blockers.append("effectiveness_scoring_result_fingerprint_mismatch")
    if str(result.get("authority_scope") or "") != AUTHORITY_SCOPE:
        blockers.append("effectiveness_scoring_result_authority_scope_mismatch")
    for key in FORBIDDEN_GENERIC_SCORE_FIELDS:
        if key in result:
            blockers.append("effectiveness_scoring_result_forbidden_generic_field_present")
            break
    if not isinstance(receipt, Mapping):
        blockers.append("effectiveness_scoring_result_receipt_missing")
    else:
        if str(receipt.get("effectiveness_scoring_result_id") or "") != str(result.get("effectiveness_scoring_result_id") or ""):
            blockers.append("effectiveness_scoring_result_receipt_binding_mismatch")
        if str(receipt.get("result_fingerprint") or "") != str(result.get("result_fingerprint") or ""):
            blockers.append("effectiveness_scoring_result_receipt_fingerprint_mismatch")
    return _dedupe(blockers)


def _ensure_dirs(root: Path | str) -> Path:
    base = Path(root)
    for folder in (PLAN_DIR, RESULT_DIR, RECEIPT_DIR, "indexes"):
        (base / folder).mkdir(parents=True, exist_ok=True)
    for path, schema in (
        (base / "indexes" / PLAN_INDEX, "deployed_rule_effectiveness_scoring_result_plan_index_v1"),
        (base / "indexes" / RESULT_INDEX, "deployed_rule_effectiveness_scoring_result_index_v1"),
        (base / "indexes" / RECEIPT_INDEX, "deployed_rule_effectiveness_scoring_result_receipt_index_v1"),
    ):
        if not path.exists():
            _atomic_write_json(path, {"schema_version": schema, "items": [], "updated_at_utc": _now()})
    return base


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        text = str(item or "")
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered
