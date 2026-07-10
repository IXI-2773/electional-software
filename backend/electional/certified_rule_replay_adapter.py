"""Single-rule controlled historical replay adapter."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping

from . import autonomous_pdf_benchmark as benchmark_backend
from . import autonomous_pdf_remediation as remediation_backend
from . import rule_effectiveness_analysis as analysis_backend
from .canonical_rule_runtime import evaluate_canonical_rule, get_canonical_rule_runtime_capability, load_canonical_rule
from .document_manifest import load_document_manifest
from .reliability.historical_replay import run_historical_replay
from .rule_effectiveness_analysis import (
    DATASET_DIR,
    _dataset_fingerprint,
    _ensure_analysis_dirs,
    _hash_payload,
    _load_certification_receipt_for_rule,
    _load_dataset,
)
from .source_documents import SOURCE_DOCUMENT_ROOT

PLAN_DIR = "certified_rule_replay_plans"
RESULT_DIR = "certified_rule_replay_results"
RECEIPT_DIR = "certified_rule_replay_receipts"
PLAN_INDEX = "certified_rule_replay_plan_index.json"
RESULT_INDEX = "certified_rule_replay_result_index.json"
RECEIPT_INDEX = "certified_rule_replay_receipt_index.json"
PLAN_SCHEMA = "certified_rule_replay_plan_v1"
RESULT_SCHEMA = "certified_rule_replay_result_v1"
RECEIPT_SCHEMA = "certified_rule_replay_receipt_v1"
REPLAY_SCHEMA_VERSION = "certified_rule_replay_adapter_v1"
SUPPORTED_DATASET_SCHEMAS = {"historical_rule_dataset_v1", "rule_replay_artifact_v1"}
PUBLIC_FUNCTIONS = [
    "build_certified_rule_replay_workspace",
    "validate_certified_rule_replay_eligibility",
    "build_certified_rule_replay_plan",
    "run_certified_rule_replay",
    "load_certified_rule_replay_result",
    "get_certified_rule_replay_health",
    "format_certified_rule_replay_report",
    "get_certified_rule_replay_summary",
]


def build_certified_rule_replay_workspace(
    canonical_rule_id: str,
    dataset_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    eligibility = validate_certified_rule_replay_eligibility(canonical_rule_id, dataset_id=dataset_id, root=base)
    rule = load_canonical_rule(canonical_rule_id, require_active=False, root=base).get("rule")
    certification = _load_certification_receipt_for_rule(base, canonical_rule_id)
    dataset = _load_replay_dataset(base, dataset_id) if dataset_id else None
    plan = _find_plan(base, canonical_rule_id, dataset_id or "")
    result = _find_result(base, str((plan or {}).get("replay_plan_id") or ""))
    receipt = _find_receipt_for_result(base, str((result or {}).get("replay_result_id") or ""))
    return {
        "status": "ready_for_planning" if not eligibility.get("blockers") else "blocked",
        "canonical_rule_id": canonical_rule_id,
        "document_id": (rule or {}).get("document_id"),
        "source_revision": (rule or {}).get("source_revision"),
        "rule_status": (rule or {}).get("status", "missing"),
        "certification_status": (certification or {}).get("certification_status", "missing"),
        "dataset_id": dataset_id,
        "dataset_fingerprint_status": "available" if isinstance(dataset, Mapping) else "missing" if dataset_id else "not_selected",
        "replay_plan_id": (plan or {}).get("replay_plan_id"),
        "replay_result_id": (result or {}).get("replay_result_id"),
        "replay_receipt_id": (receipt or {}).get("replay_receipt_id"),
        "replay_status": (result or {}).get("status", "not_run"),
        "warnings": list(eligibility.get("warnings", [])),
        "blockers": list(eligibility.get("blockers", [])),
        "recommended_action": "Build the shadow/read-only replay plan." if not eligibility.get("blockers") else "Resolve certified-rule or dataset blockers before replay.",
    }


def validate_certified_rule_replay_eligibility(
    canonical_rule_id: str,
    dataset_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    blockers: list[str] = []
    warnings: list[str] = []
    capability = get_canonical_rule_runtime_capability(root=base)
    if not capability.get("single_rule_evaluator_available"):
        blockers.append("canonical_rule_evaluator_unavailable")
    loaded = load_canonical_rule(canonical_rule_id, require_active=True, root=base)
    rule = loaded.get("rule")
    if loaded.get("status") != "loaded" or not isinstance(rule, Mapping):
        blockers.extend(list(loaded.get("blockers", []) or ["canonical_rule_not_found"]))
        rule = {}
    certification = _load_certification_receipt_for_rule(base, canonical_rule_id)
    if not isinstance(certification, Mapping):
        blockers.append("rule_certification_missing")
    else:
        if str(certification.get("certification_status") or "") != "completed":
            blockers.append("rule_not_certified")
        if isinstance(rule, Mapping) and str(certification.get("rule_hash") or "") != _hash_payload(rule):
            blockers.append("rule_certification_hash_mismatch")
    manifest = load_document_manifest(str((rule or {}).get("document_id") or ""), root=base).get("manifest") if rule else None
    if isinstance(rule, Mapping) and isinstance(manifest, Mapping):
        if str(rule.get("source_revision") or "") != str(manifest.get("source_revision") or ""):
            blockers.append("source_revision_not_current")
    elif rule:
        blockers.append("document_manifest_missing")
    if _rule_has_unresolved_critical_remediation(base, rule):
        blockers.append("rule_has_unresolved_critical_remediation")
    if _rule_pending_supersession(base, canonical_rule_id):
        blockers.append("rule_pending_supersession")
    dataset = _load_replay_dataset(base, dataset_id) if dataset_id else None
    if dataset_id:
        dataset_blockers = _validate_dataset(dataset_id, dataset)
        blockers.extend(dataset_blockers)
    return {
        "status": "eligible" if not blockers else "blocked",
        "canonical_rule_id": canonical_rule_id,
        "document_id": (rule or {}).get("document_id"),
        "source_revision": (rule or {}).get("source_revision"),
        "rule_fingerprint": _hash_payload(rule) if isinstance(rule, Mapping) else None,
        "rule_certified": isinstance(certification, Mapping) and "rule_certification_hash_mismatch" not in blockers and "rule_not_certified" not in blockers,
        "dataset_id": dataset_id,
        "warnings": warnings,
        "blockers": _dedupe(blockers),
    }


def build_certified_rule_replay_plan(
    canonical_rule_id: str,
    dataset_id: str,
    max_records: int = 10000,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    eligibility = validate_certified_rule_replay_eligibility(canonical_rule_id, dataset_id=dataset_id, root=base)
    if eligibility.get("blockers"):
        return {"status": "blocked", "canonical_rule_id": canonical_rule_id, "dataset_id": dataset_id, "blockers": list(eligibility.get("blockers", [])), "warnings": []}
    rule = load_canonical_rule(canonical_rule_id, require_active=True, root=base).get("rule") or {}
    certification = _load_certification_receipt_for_rule(base, canonical_rule_id) or {}
    dataset = _load_replay_dataset(base, dataset_id) or {}
    records = list(dataset.get("records", []) or [])
    if len(records) > max_records:
        return {"status": "blocked", "canonical_rule_id": canonical_rule_id, "dataset_id": dataset_id, "blockers": [f"dataset_record_limit_exceeded:{max_records}"], "warnings": []}
    replay_plan_id = _plan_id(canonical_rule_id, dataset_id, max_records, rule, certification, dataset)
    plan = {
        "schema_version": PLAN_SCHEMA,
        "replay_schema_version": REPLAY_SCHEMA_VERSION,
        "replay_plan_id": replay_plan_id,
        "canonical_rule_id": canonical_rule_id,
        "document_id": rule.get("document_id"),
        "source_revision": rule.get("source_revision"),
        "rule_fingerprint": _hash_payload(rule),
        "certification_receipt_id": certification.get("certification_receipt_id"),
        "certification_fingerprint": _certification_fingerprint(certification),
        "dataset_id": dataset_id,
        "dataset_fingerprint": _dataset_fingerprint(dataset),
        "bounded_record_count": len(records),
        "evaluator_fingerprint": _evaluator_fingerprint(),
        "replay_mode": "shadow_read_only",
        "expected_input_mapping": {"record.context": "evaluation_context|context", "record.timestamp": "timestamp", "record.identity": "record_id"},
        "plan_fingerprint": _hash_payload({"rule": _hash_payload(rule), "certification": _certification_fingerprint(certification), "dataset": _dataset_fingerprint(dataset), "record_count": len(records), "max_records": max_records, "evaluator": _evaluator_fingerprint(), "schema": REPLAY_SCHEMA_VERSION}),
        "warnings": [],
        "blockers": [],
    }
    before = _read_json(_plan_path(base, replay_plan_id))
    before_index = _read_json(base / "indexes" / PLAN_INDEX)
    try:
        analysis_backend._atomic_write_json(_plan_path(base, replay_plan_id), plan)
        _update_plan_index(base)
    except Exception:
        _restore_json(_plan_path(base, replay_plan_id), before)
        _restore_json(base / "indexes" / PLAN_INDEX, before_index)
        return {"status": "corrupt", "canonical_rule_id": canonical_rule_id, "dataset_id": dataset_id, "blockers": ["replay_plan_write_failure"], "warnings": []}
    return {
        "status": "planned",
        "replay_plan_id": replay_plan_id,
        "canonical_rule_id": canonical_rule_id,
        "document_id": rule.get("document_id"),
        "source_revision": rule.get("source_revision"),
        "dataset_id": dataset_id,
        "bounded_record_count": len(records),
        "replay_mode": "shadow_read_only",
        "warnings": [],
        "blockers": [],
    }


def run_certified_rule_replay(
    replay_plan_id: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    if confirmation != "RUN_REPLAY":
        return {"status": "blocked", "replay_plan_id": replay_plan_id, "blockers": ["run_replay_confirmation_required"], "warnings": []}
    plan = _read_json(_plan_path(base, replay_plan_id))
    if not isinstance(plan, Mapping):
        return {"status": "blocked", "replay_plan_id": replay_plan_id, "blockers": ["replay_plan_missing"], "warnings": []}
    current = _plan_current_status(base, plan)
    if current["status"] != "current":
        return {"status": current["status"], "replay_plan_id": replay_plan_id, "blockers": list(current.get("blockers", [])), "warnings": []}
    existing = _find_result(base, replay_plan_id)
    if isinstance(existing, Mapping) and not _result_is_stale(base, existing):
        receipt = _find_receipt_for_result(base, str(existing.get("replay_result_id") or ""))
        return {"status": "already_completed", "replay_result_id": existing.get("replay_result_id"), "replay_receipt_id": (receipt or {}).get("replay_receipt_id"), "writes_performed": 0}
    rule = load_canonical_rule(str(plan.get("canonical_rule_id") or ""), require_active=True, root=base).get("rule") or {}
    dataset = _load_replay_dataset(base, str(plan.get("dataset_id") or "")) or {}
    foundation = _run_shadow_foundation(dataset)
    per_record: list[dict[str, Any]] = []
    evaluated_match = evaluated_no_match = unsupported = errors = eligible = 0
    first_ts = last_ts = None
    for record in dataset.get("records", []) or []:
        outcome = _adapt_and_evaluate_record(rule, record, base)
        per_record.append(outcome)
        if outcome["classification"] == "skipped_outside_scope":
            continue
        eligible += 1
        if outcome["classification"] == "evaluated_match":
            evaluated_match += 1
        elif outcome["classification"] == "evaluated_no_match":
            evaluated_no_match += 1
        elif outcome["classification"] in {"unsupported_missing_field", "unsupported_invalid_value"}:
            unsupported += 1
        elif outcome["classification"] == "evaluator_error":
            errors += 1
        if outcome.get("timestamp"):
            if first_ts is None:
                first_ts = outcome["timestamp"]
            last_ts = outcome["timestamp"]
    total = len(dataset.get("records", []) or [])
    evaluated = evaluated_match + evaluated_no_match
    compatibility = eligible - unsupported - errors
    metrics = {
        "total_records": total,
        "eligible_records": eligible,
        "evaluated_records": evaluated,
        "match_count": evaluated_match,
        "no_match_count": evaluated_no_match,
        "unsupported_count": unsupported,
        "evaluator_error_count": errors,
        "replay_coverage": _ratio(evaluated, total),
        "compatibility_rate": _ratio(compatibility, total),
        "match_rate": _ratio(evaluated_match, evaluated),
        "first_evaluated_timestamp": first_ts,
        "last_evaluated_timestamp": last_ts,
    }
    status = "evaluator_failed" if errors else "completed_with_unsupported_records" if unsupported else "no_eligible_records" if eligible == 0 else "completed"
    result_id = _result_id(replay_plan_id, plan)
    result = {
        "schema_version": RESULT_SCHEMA,
        "replay_schema_version": REPLAY_SCHEMA_VERSION,
        "replay_result_id": result_id,
        "replay_plan_id": replay_plan_id,
        "canonical_rule_id": plan.get("canonical_rule_id"),
        "document_id": plan.get("document_id"),
        "source_revision": plan.get("source_revision"),
        "rule_fingerprint": plan.get("rule_fingerprint"),
        "certification_receipt_id": plan.get("certification_receipt_id"),
        "certification_fingerprint": plan.get("certification_fingerprint"),
        "dataset_id": plan.get("dataset_id"),
        "dataset_fingerprint": plan.get("dataset_fingerprint"),
        "evaluator_fingerprint": plan.get("evaluator_fingerprint"),
        "replay_mode": "shadow_read_only",
        "foundation_run_id": foundation.get("run_id"),
        "per_record_results": per_record,
        "metrics": metrics,
        "warnings": [],
        "blockers": [],
        "status": status,
        "result_fingerprint": _hash_payload({"plan": plan.get("plan_fingerprint"), "metrics": metrics, "records": per_record, "status": status}),
        "created_at_utc": analysis_backend._now(),
    }
    receipt_id = _receipt_id(result_id)
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "replay_receipt_id": receipt_id,
        "replay_result_id": result_id,
        "replay_plan_id": replay_plan_id,
        "canonical_rule_id": plan.get("canonical_rule_id"),
        "document_id": plan.get("document_id"),
        "source_revision": plan.get("source_revision"),
        "rule_fingerprint": plan.get("rule_fingerprint"),
        "certification_fingerprint": plan.get("certification_fingerprint"),
        "dataset_fingerprint": plan.get("dataset_fingerprint"),
        "evaluator_fingerprint": plan.get("evaluator_fingerprint"),
        "final_status": status,
        "metric_summary": {key: metrics[key] for key in ("total_records", "evaluated_records", "match_count", "no_match_count", "unsupported_count", "evaluator_error_count", "replay_coverage", "compatibility_rate", "match_rate")},
        "created_at_utc": analysis_backend._now(),
    }
    before_result = _read_json(_result_path(base, result_id))
    before_receipt = _read_json(_receipt_path(base, receipt_id))
    before_result_index = _read_json(base / "indexes" / RESULT_INDEX)
    before_receipt_index = _read_json(base / "indexes" / RECEIPT_INDEX)
    try:
        analysis_backend._atomic_write_json(_result_path(base, result_id), result)
        analysis_backend._atomic_write_json(_receipt_path(base, receipt_id), receipt)
        _update_result_index(base)
        _update_receipt_index(base)
    except Exception:
        _restore_json(_result_path(base, result_id), before_result)
        _restore_json(_receipt_path(base, receipt_id), before_receipt)
        _restore_json(base / "indexes" / RESULT_INDEX, before_result_index)
        _restore_json(base / "indexes" / RECEIPT_INDEX, before_receipt_index)
        return {"status": "corrupt", "replay_plan_id": replay_plan_id, "blockers": ["replay_result_write_failure"], "warnings": []}
    return {"status": status, "replay_plan_id": replay_plan_id, "replay_result_id": result_id, "replay_receipt_id": receipt_id, "writes_performed": 2}


def load_certified_rule_replay_result(
    replay_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    result = _read_json(_result_path(base, replay_result_id))
    if not isinstance(result, Mapping):
        return {"status": "not_found", "replay_result_id": replay_result_id, "replay_result": None, "warnings": []}
    payload = dict(result)
    payload["stale"] = _result_is_stale(base, payload)
    return {"status": "loaded", "replay_result_id": replay_result_id, "replay_result": payload, "warnings": []}


def get_certified_rule_replay_health(
    replay_plan_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    plans = _load_all_plans(base)
    results = _load_all_results(base)
    receipts = _load_all_receipts(base)
    if replay_plan_id:
        plans = [item for item in plans if str(item.get("replay_plan_id") or "") == replay_plan_id]
        results = [item for item in results if str(item.get("replay_plan_id") or "") == replay_plan_id]
        receipts = [item for item in receipts if str(item.get("replay_plan_id") or "") == replay_plan_id]
    if not plans and not results and not receipts:
        return {"status": "empty", "replay_plan_count": 0, "replay_result_count": 0, "replay_receipt_count": 0, "recommended_action": "Build one certified-rule replay plan."}
    warnings: list[str] = []
    stale_count = 0
    if len({str(item.get("replay_plan_id") or "") for item in plans}) != len(plans):
        warnings.append("duplicate_replay_plan_ids")
    if len({str(item.get("replay_result_id") or "") for item in results}) != len(results):
        warnings.append("duplicate_replay_result_ids")
    if len({str(item.get("replay_receipt_id") or "") for item in receipts}) != len(receipts):
        warnings.append("duplicate_replay_receipt_ids")
    for result in results:
        if _result_is_stale(base, result):
            stale_count += 1
        metrics = result.get("metrics") or {}
        for key in ("replay_coverage", "compatibility_rate", "match_rate"):
            value = metrics.get(key)
            if isinstance(value, (int, float)) and (value < 0 or value > 1):
                warnings.append("impossible_metric_value")
    status = "corrupt" if warnings else "stale" if stale_count else "healthy"
    return {
        "status": status,
        "replay_plan_count": len(plans),
        "replay_result_count": len(results),
        "replay_receipt_count": len(receipts),
        "stale_replay_count": stale_count,
        "warnings": _dedupe(warnings),
        "recommended_action": "Rerun replay against the current rule and dataset." if stale_count else "Replay health is good.",
    }


def format_certified_rule_replay_report(
    replay_result_id: str | None = None,
    replay_receipt_id: str | None = None,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    base = _ensure_dirs(root)
    receipt = _find_receipt_by_id(base, replay_receipt_id) if replay_receipt_id else None
    result = _find_result_by_id(base, replay_result_id or str((receipt or {}).get("replay_result_id") or ""))
    if not isinstance(result, Mapping):
        return "Certified Rule Historical Replay\n\nStatus: not_found"
    metrics = result.get("metrics") or {}
    dataset = _load_replay_dataset(base, str(result.get("dataset_id") or "")) or {}
    lines = [
        "Certified Rule Historical Replay",
        "",
        f"Rule ID: {result.get('canonical_rule_id')}",
        f"Document: {result.get('document_id')}",
        f"Source Revision: {result.get('source_revision')}",
        f"Certification Status: completed",
        f"Dataset ID: {result.get('dataset_id')}",
        f"Dataset Range: {dataset.get('start_timestamp', 'unknown')} -> {dataset.get('end_timestamp', 'unknown')}",
        f"Replay Status: {result.get('status')}",
        f"Total Records: {metrics.get('total_records', 0)}",
        f"Evaluated Records: {metrics.get('evaluated_records', 0)}",
        f"Match Count: {metrics.get('match_count', 0)}",
        f"No-Match Count: {metrics.get('no_match_count', 0)}",
        f"Unsupported Count: {metrics.get('unsupported_count', 0)}",
        f"Error Count: {metrics.get('evaluator_error_count', 0)}",
        f"Replay Coverage: {_pct(metrics.get('replay_coverage'))}",
        f"Compatibility Rate: {_pct(metrics.get('compatibility_rate'))}",
        f"Match Rate: {_pct(metrics.get('match_rate'))}",
        f"Stale: {'Yes' if _result_is_stale(base, result) else 'No'}",
        "Replay Mode: shadow_read_only",
        "Production Safety: no scoring, objective-pack, Fast Lane, active-rule, or production output was modified.",
        "Interpretation: match rate is not profitability or production effectiveness.",
        f"Recommended Next Action: {'Inspect unsupported or evaluator-error records.' if result.get('status') != 'completed' else 'Replay summary is current.'}",
    ]
    if not public_safe:
        lines.append(f"Result Fingerprint: {result.get('result_fingerprint')}")
    return "\n".join(lines)


def get_certified_rule_replay_summary(
    replay_plan_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    plan = _read_json(_plan_path(base, replay_plan_id))
    result = _find_result(base, replay_plan_id)
    metrics = dict((result or {}).get("metrics") or {})
    return {
        "replay_plan_id": replay_plan_id,
        "canonical_rule_id": (plan or {}).get("canonical_rule_id"),
        "document_id": (plan or {}).get("document_id"),
        "source_revision": (plan or {}).get("source_revision"),
        "dataset_id": (plan or {}).get("dataset_id"),
        "status": (result or {}).get("status", "not_run"),
        "total_records": metrics.get("total_records", 0),
        "evaluated_records": metrics.get("evaluated_records", 0),
        "match_count": metrics.get("match_count", 0),
        "unsupported_count": metrics.get("unsupported_count", 0),
        "recommended_action": "Run the shadow replay." if result is None else "Review the public-safe replay report.",
    }


def _ensure_dirs(root: Path | str) -> Path:
    base = _ensure_analysis_dirs(root)
    for folder in (PLAN_DIR, RESULT_DIR, RECEIPT_DIR, "indexes"):
        (base / folder).mkdir(parents=True, exist_ok=True)
    defaults = (
        (PLAN_INDEX, "certified_rule_replay_plan_index_v1"),
        (RESULT_INDEX, "certified_rule_replay_result_index_v1"),
        (RECEIPT_INDEX, "certified_rule_replay_receipt_index_v1"),
    )
    for name, schema in defaults:
        path = base / "indexes" / name
        if not path.exists():
            analysis_backend._atomic_write_json(path, {"schema_version": schema, "items": [], "updated_at_utc": analysis_backend._now()})
    return base


def _load_replay_dataset(base: Path, dataset_id: str | None) -> dict[str, Any] | None:
    if not dataset_id:
        return None
    return _load_dataset(base, dataset_id)


def _validate_dataset(dataset_id: str, dataset: Mapping[str, Any] | None) -> list[str]:
    blockers: list[str] = []
    if not isinstance(dataset, Mapping):
        return ["historical_rule_dataset_unavailable"]
    if str(dataset.get("schema_version") or "") not in SUPPORTED_DATASET_SCHEMAS:
        blockers.append("dataset_schema_unsupported")
    records = list(dataset.get("records", []) or [])
    if not dataset.get("dataset_fingerprint"):
        blockers.append("dataset_fingerprint_missing")
    if dataset.get("dataset_id") != dataset_id:
        blockers.append("dataset_identity_mismatch")
    if not dataset.get("start_timestamp") or not dataset.get("end_timestamp"):
        blockers.append("dataset_timestamp_range_required")
    if len(records) != int(dataset.get("record_count") or 0):
        blockers.append("dataset_record_count_mismatch")
    seen_ids: list[str] = []
    last_ts = None
    for record in records:
        if not isinstance(record, Mapping):
            blockers.append("dataset_record_invalid")
            break
        record_id = str(record.get("record_id") or "")
        ts = str(record.get("timestamp") or "")
        if not record_id:
            blockers.append("dataset_record_identity_missing")
        if record_id in seen_ids:
            blockers.append("dataset_duplicate_record_identity")
        seen_ids.append(record_id)
        if not ts:
            blockers.append("dataset_record_timestamp_missing")
        if last_ts and ts < last_ts:
            blockers.append("dataset_record_order_invalid")
        last_ts = ts or last_ts
        if str(record.get("dataset_id") or dataset_id) != dataset_id:
            blockers.append("dataset_record_foreign_identity")
    actual_fp = _dataset_fingerprint(dataset)
    if str(dataset.get("dataset_fingerprint") or "") != str(actual_fp):
        blockers.append("dataset_fingerprint_mismatch")
    if len(records) > 10000:
        blockers.append("dataset_record_limit_exceeded:10000")
    if dataset.get("start_timestamp") and dataset.get("end_timestamp"):
        if str(dataset.get("start_timestamp"))[:4].isdigit() and str(dataset.get("end_timestamp"))[:4].isdigit():
            if int(str(dataset.get("end_timestamp"))[:4]) - int(str(dataset.get("start_timestamp"))[:4]) > 10:
                blockers.append("dataset_time_range_limit_exceeded:10y")
    return _dedupe(blockers)


def _plan_current_status(base: Path, plan: Mapping[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    loaded = load_canonical_rule(str(plan.get("canonical_rule_id") or ""), require_active=True, root=base)
    rule = loaded.get("rule")
    if loaded.get("status") != "loaded" or not isinstance(rule, Mapping):
        blockers.append("canonical_rule_not_active")
    certification = _load_certification_receipt_for_rule(base, str(plan.get("canonical_rule_id") or ""))
    if not isinstance(certification, Mapping):
        blockers.append("rule_certification_missing")
    elif str(plan.get("certification_fingerprint") or "") != _certification_fingerprint(certification):
        blockers.append("certification_fingerprint_changed")
    dataset = _load_replay_dataset(base, str(plan.get("dataset_id") or ""))
    if not isinstance(dataset, Mapping):
        blockers.append("historical_rule_dataset_unavailable")
    elif str(plan.get("dataset_fingerprint") or "") != str(_dataset_fingerprint(dataset)):
        blockers.append("dataset_fingerprint_changed")
    manifest = load_document_manifest(str(plan.get("document_id") or ""), root=base).get("manifest")
    if isinstance(manifest, Mapping) and str(plan.get("source_revision") or "") != str(manifest.get("source_revision") or ""):
        blockers.append("source_revision_changed")
    if str(plan.get("evaluator_fingerprint") or "") != _evaluator_fingerprint():
        blockers.append("evaluator_fingerprint_changed")
    if str(plan.get("replay_mode") or "") != "shadow_read_only":
        blockers.append("replay_mode_changed")
    return {"status": "current" if not blockers else "stale", "blockers": blockers}


def _adapt_and_evaluate_record(rule: Mapping[str, Any], record: Mapping[str, Any], base: Path) -> dict[str, Any]:
    record_id = str(record.get("record_id") or "")
    timestamp = str(record.get("timestamp") or "")
    context = record.get("evaluation_context") if isinstance(record.get("evaluation_context"), Mapping) else record.get("context")
    field = str(((rule.get("condition") or {}).get("field")) or "")
    if not isinstance(context, Mapping):
        return {"record_id": record_id, "timestamp": timestamp, "classification": "unsupported_missing_field"}
    if field not in context:
        return {"record_id": record_id, "timestamp": timestamp, "classification": "unsupported_missing_field"}
    if context.get(field) is None:
        return {"record_id": record_id, "timestamp": timestamp, "classification": "unsupported_invalid_value"}
    evaluation = evaluate_canonical_rule(dict(rule), dict(context), root=base)
    result = str(evaluation.get("result") or "")
    if result == "matched":
        classification = "evaluated_match"
    elif result == "not_matched":
        classification = "evaluated_no_match"
    elif result == "unsupported":
        classification = "unsupported_invalid_value"
    elif result == "error":
        classification = "evaluator_error"
    else:
        classification = "skipped_outside_scope"
    return {"record_id": record_id, "timestamp": timestamp, "classification": classification}


def _run_shadow_foundation(dataset: Mapping[str, Any]) -> dict[str, Any]:
    with TemporaryDirectory() as tmp:
        temp_root = Path(tmp)
        folder = temp_root / "audit_snapshots"
        folder.mkdir(parents=True, exist_ok=True)
        for record in list(dataset.get("records", []) or []):
            snapshot = {
                "input": {"objective": str(dataset.get("dataset_id") or ""), "date": str(record.get("timestamp") or "")},
                "phase1_advanced_analysis": {},
                "phase2_tactical_analysis": {},
                "hard_gates": {},
            }
            (folder / f"{analysis_backend._safe_id(str(record.get('record_id') or 'record'))}.json").write_text(json.dumps(snapshot, sort_keys=True), encoding="utf-8")
        return run_historical_replay(root=temp_root, input_path=folder, dry_run=True, save_result=False, create_review_items=False, current_snapshot_builder=lambda old: old)


def _rule_has_unresolved_critical_remediation(base: Path, rule: Mapping[str, Any] | Any) -> bool:
    if not isinstance(rule, Mapping):
        return False
    for case in remediation_backend._load_all_cases(base):
        if str(case.get("document_id") or "") == str(rule.get("document_id") or "") and str(case.get("source_revision") or "") == str(rule.get("source_revision") or "") and str(case.get("severity") or "") == "critical" and not str(case.get("review_decision") or ""):
            return True
    return False


def _rule_pending_supersession(base: Path, rule_id: str) -> bool:
    try:
        from .rule_supersession import SUPERSESSION_REVIEW_DIR
    except Exception:
        return False
    for path in sorted((base / SUPERSESSION_REVIEW_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping) and str(payload.get("old_rule_id") or "") == rule_id and str(payload.get("review_status") or "") in {"approved", "pending_review"}:
            return True
    return False


def _certification_fingerprint(receipt: Mapping[str, Any]) -> str:
    return _hash_payload({
        "certification_receipt_id": receipt.get("certification_receipt_id"),
        "rule_id": receipt.get("rule_id"),
        "rule_hash": receipt.get("rule_hash"),
        "certification_status": receipt.get("certification_status"),
    })


def _evaluator_fingerprint() -> str:
    return _hash_payload({"evaluator": "canonical_rule_runtime.evaluate_canonical_rule", "schema": "canonical_single_rule_evaluation_v1"})


def _plan_id(canonical_rule_id: str, dataset_id: str, max_records: int, rule: Mapping[str, Any], certification: Mapping[str, Any], dataset: Mapping[str, Any]) -> str:
    return f"certified_rule_replay_plan_{_hash_payload({'rule_id': canonical_rule_id, 'dataset_id': dataset_id, 'max_records': max_records, 'rule': _hash_payload(rule), 'cert': _certification_fingerprint(certification), 'dataset': _dataset_fingerprint(dataset), 'evaluator': _evaluator_fingerprint(), 'schema': REPLAY_SCHEMA_VERSION})[7:23]}"


def _result_id(replay_plan_id: str, plan: Mapping[str, Any]) -> str:
    return f"certified_rule_replay_result_{_hash_payload({'replay_plan_id': replay_plan_id, 'plan_fingerprint': plan.get('plan_fingerprint')})[7:23]}"


def _receipt_id(result_id: str) -> str:
    return f"certified_rule_replay_receipt_{_hash_payload({'result_id': result_id})[7:23]}"


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(float(numerator) / float(denominator), 6)


def _pct(value: Any) -> str:
    return "null" if value is None else f"{float(value) * 100:.2f}%"


def _result_is_stale(base: Path, result: Mapping[str, Any]) -> bool:
    plan = _read_json(_plan_path(base, str(result.get("replay_plan_id") or "")))
    if not isinstance(plan, Mapping):
        return True
    current = _plan_current_status(base, plan)
    return current["status"] != "current" or str(result.get("result_fingerprint") or "") != _hash_payload({"plan": plan.get("plan_fingerprint"), "metrics": result.get("metrics"), "records": result.get("per_record_results"), "status": result.get("status")})


def _find_plan(base: Path, canonical_rule_id: str, dataset_id: str) -> dict[str, Any] | None:
    for item in _load_all_plans(base):
        if str(item.get("canonical_rule_id") or "") == canonical_rule_id and str(item.get("dataset_id") or "") == dataset_id:
            return item
    return None


def _find_result(base: Path, replay_plan_id: str) -> dict[str, Any] | None:
    for item in _load_all_results(base):
        if str(item.get("replay_plan_id") or "") == replay_plan_id:
            return item
    return None


def _find_result_by_id(base: Path, replay_result_id: str | None) -> dict[str, Any] | None:
    if not replay_result_id:
        return None
    payload = _read_json(_result_path(base, replay_result_id))
    return dict(payload) if isinstance(payload, Mapping) else None


def _find_receipt_for_result(base: Path, replay_result_id: str) -> dict[str, Any] | None:
    for item in _load_all_receipts(base):
        if str(item.get("replay_result_id") or "") == replay_result_id:
            return item
    return None


def _find_receipt_by_id(base: Path, replay_receipt_id: str | None) -> dict[str, Any] | None:
    if not replay_receipt_id:
        return None
    payload = _read_json(_receipt_path(base, replay_receipt_id))
    return dict(payload) if isinstance(payload, Mapping) else None


def _load_all_plans(base: Path) -> list[dict[str, Any]]:
    return _load_dir_json(base / PLAN_DIR, "replay_plan_id")


def _load_all_results(base: Path) -> list[dict[str, Any]]:
    return _load_dir_json(base / RESULT_DIR, "replay_result_id")


def _load_all_receipts(base: Path) -> list[dict[str, Any]]:
    return _load_dir_json(base / RECEIPT_DIR, "replay_receipt_id")


def _update_plan_index(base: Path) -> None:
    items = [{"replay_plan_id": item.get("replay_plan_id"), "canonical_rule_id": item.get("canonical_rule_id"), "dataset_id": item.get("dataset_id"), "document_id": item.get("document_id"), "source_revision": item.get("source_revision")} for item in _load_all_plans(base)]
    analysis_backend._atomic_write_json(base / "indexes" / PLAN_INDEX, {"schema_version": "certified_rule_replay_plan_index_v1", "items": sorted(items, key=lambda item: str(item.get("replay_plan_id") or "")), "updated_at_utc": analysis_backend._now()})


def _update_result_index(base: Path) -> None:
    items = [{"replay_result_id": item.get("replay_result_id"), "replay_plan_id": item.get("replay_plan_id"), "canonical_rule_id": item.get("canonical_rule_id"), "status": item.get("status")} for item in _load_all_results(base)]
    analysis_backend._atomic_write_json(base / "indexes" / RESULT_INDEX, {"schema_version": "certified_rule_replay_result_index_v1", "items": sorted(items, key=lambda item: str(item.get("replay_result_id") or "")), "updated_at_utc": analysis_backend._now()})


def _update_receipt_index(base: Path) -> None:
    items = [{"replay_receipt_id": item.get("replay_receipt_id"), "replay_result_id": item.get("replay_result_id"), "replay_plan_id": item.get("replay_plan_id"), "final_status": item.get("final_status")} for item in _load_all_receipts(base)]
    analysis_backend._atomic_write_json(base / "indexes" / RECEIPT_INDEX, {"schema_version": "certified_rule_replay_receipt_index_v1", "items": sorted(items, key=lambda item: str(item.get("replay_receipt_id") or "")), "updated_at_utc": analysis_backend._now()})


def _load_dir_json(folder: Path, required_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not folder.exists():
        return items
    for path in sorted(folder.glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping) and payload.get(required_id):
            items.append(dict(payload))
    return items


def _plan_path(base: Path, replay_plan_id: str) -> Path:
    return base / PLAN_DIR / f"{analysis_backend._safe_id(replay_plan_id)}.json"


def _result_path(base: Path, replay_result_id: str) -> Path:
    return base / RESULT_DIR / f"{analysis_backend._safe_id(replay_result_id)}.json"


def _receipt_path(base: Path, replay_receipt_id: str) -> Path:
    return base / RECEIPT_DIR / f"{analysis_backend._safe_id(replay_receipt_id)}.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    return benchmark_backend._read_json(path)


def _restore_json(path: Path, payload: dict[str, Any] | None) -> None:
    benchmark_backend._restore_json(path, payload)


def _dedupe(values: list[str]) -> list[str]:
    return remediation_backend._dedupe(values)
