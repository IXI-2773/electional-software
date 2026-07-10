"""Read-only effectiveness analytics for certified canonical rules."""

from __future__ import annotations

import hashlib
import json
import math
import os
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from .canonical_rule_runtime import evaluate_canonical_rule, get_canonical_rule_runtime_capability, load_canonical_rule
from .rule_activation_revalidation import CERTIFICATION_RECEIPT_DIR
from .rule_supersession import SUPERSESSION_CHAIN_DIR
from .source_documents import SOURCE_DOCUMENT_ROOT
from .source_knowledge import ensure_source_knowledge_dirs

ANALYSIS_DIR = "rule_effectiveness_analyses"
RECEIPT_DIR = "rule_effectiveness_receipts"
ANALYSIS_INDEX = "rule_effectiveness_analysis_index.json"
RECEIPT_INDEX = "rule_effectiveness_receipt_index.json"
ANALYSIS_SCHEMA = "rule_effectiveness_analysis_v1"
RECEIPT_SCHEMA = "rule_effectiveness_receipt_v1"
PLAN_SCHEMA = "rule_effectiveness_backtest_plan_v1"
DATASET_DIR = "historical_rule_datasets"
REPLAY_DIR = "replay_artifacts"
SUPPORTED_DATASET_SCHEMAS = {"historical_rule_dataset_v1", "rule_replay_artifact_v1"}


def build_rule_effectiveness_workspace(
    rule_id: str,
    dataset_id: str,
    comparison_rule_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_analysis_dirs(root)
    validation = validate_rule_effectiveness_inputs(rule_id, dataset_id, comparison_rule_id=comparison_rule_id, root=base)
    rule = _load_rule_record(base, rule_id)
    dataset = _load_dataset(base, dataset_id)
    comparison = _load_rule_record(base, comparison_rule_id) if comparison_rule_id else None
    analysis = _load_analysis_by_plan(base, None, rule_id=rule_id, dataset_id=dataset_id, comparison_rule_id=comparison_rule_id)
    receipt = _load_receipt_for_analysis(base, str((analysis or {}).get("analysis_id") or "")) if analysis else None
    analysis_current = None
    if analysis:
        current_plan = build_rule_effectiveness_backtest_plan(
            rule_id,
            dataset_id,
            comparison_rule_id=comparison_rule_id,
            root=base,
        )
        if not current_plan.get("blockers"):
            analysis_current = _analysis_current(base, analysis, current_plan, comparison_rule_id)
    return {
        "rule_id": rule_id,
        "rule_status": str((rule or {}).get("status") or "missing"),
        "rule_certification_status": "completed" if validation.get("rule_certified") else "missing",
        "dataset_id": dataset_id,
        "dataset_status": "available" if isinstance(dataset, dict) else "historical_rule_dataset_unavailable",
        "dataset_record_count": len(list((dataset or {}).get("records", []) or [])) if isinstance(dataset, dict) else 0,
        "comparison_rule_id": comparison_rule_id,
        "comparison_status": "available" if comparison_rule_id and isinstance(comparison, dict) else "not_requested" if not comparison_rule_id else "missing",
        "analysis_status": str((analysis or {}).get("status") or "not_run"),
        "analysis_id": (analysis or {}).get("analysis_id"),
        "analysis_current": analysis_current,
        "analysis_freshness_status": "current" if analysis_current is True else "stale" if analysis_current is False else "unknown" if analysis else "not_run",
        "effectiveness_receipt_id": (receipt or {}).get("effectiveness_receipt_id"),
        "warnings": list(validation.get("warnings", [])),
        "blockers": list(validation.get("blockers", [])),
        "recommended_action": (
            "Regenerate the focused backtest against the current rule and dataset state."
            if analysis_current is False
            else "Build and run the focused backtest plan."
            if not validation.get("blockers")
            else "Resolve rule or dataset blockers before analysis."
        ),
    }


def validate_rule_effectiveness_inputs(
    rule_id: str,
    dataset_id: str,
    comparison_rule_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_analysis_dirs(root)
    blockers: list[str] = []
    warnings: list[str] = []
    capability = get_canonical_rule_runtime_capability(root=base)
    if not capability.get("single_rule_evaluator_available"):
        blockers.append("canonical_rule_evaluator_unavailable")
    rule = _load_rule_record(base, rule_id)
    certification = _load_certification_receipt_for_rule(base, rule_id)
    if not isinstance(rule, dict):
        blockers.append("canonical_rule_not_found")
    if not isinstance(certification, dict):
        blockers.append("rule_certification_missing")
    elif certification.get("certification_status") != "completed":
        blockers.append("rule_not_certified")
    elif isinstance(rule, dict) and certification.get("rule_hash") != _hash_payload(rule):
        blockers.append("rule_certification_hash_mismatch")
    dataset = _load_dataset(base, dataset_id)
    if not isinstance(dataset, dict):
        blockers.append("historical_rule_dataset_unavailable")
    else:
        blockers.extend(_validate_dataset_contract(dataset))
    comparison_available = False
    if comparison_rule_id:
        comparison_rule = _load_rule_record(base, comparison_rule_id)
        comparison_certification = _load_certification_receipt_for_rule(base, comparison_rule_id)
        if not isinstance(comparison_rule, dict):
            blockers.append("comparison_rule_missing")
        if not isinstance(comparison_certification, dict):
            blockers.append("comparison_rule_certification_missing")
        elif isinstance(comparison_rule, dict) and comparison_certification.get("rule_hash") != _hash_payload(comparison_rule):
            blockers.append("comparison_rule_hash_mismatch")
        chain = _load_chain_for_rule_pair(base, rule_id, comparison_rule_id)
        if chain is None:
            blockers.append("comparison_rule_not_in_same_version_chain")
        elif isinstance(rule, dict) and isinstance(comparison_rule, dict):
            if str(rule.get("target") or "") != str(comparison_rule.get("target") or "") or str(rule.get("scope") or "") != str(comparison_rule.get("scope") or ""):
                blockers.append("comparison_rule_incompatible")
        comparison_available = "comparison_rule_not_in_same_version_chain" not in blockers and "comparison_rule_incompatible" not in blockers
    if isinstance(dataset, dict) and dataset.get("record_count_limit_exceeded") is True:
        blockers.append("historical_dataset_limit_exceeded")
    return {
        "valid": not blockers,
        "rule_id": rule_id,
        "rule_certified": isinstance(certification, dict) and "rule_certification_hash_mismatch" not in blockers,
        "dataset_id": dataset_id,
        "dataset_valid": isinstance(dataset, dict) and not any(item.startswith("dataset_") or item.startswith("historical_rule_dataset") for item in blockers),
        "outcome_labels_available": _outcome_label_field(dataset) is not None if isinstance(dataset, dict) else False,
        "baseline_available": _baseline_field(dataset) is not None if isinstance(dataset, dict) else False,
        "comparison_available": comparison_available,
        "warnings": warnings,
        "blockers": _dedupe(blockers),
    }


def build_rule_effectiveness_backtest_plan(
    rule_id: str,
    dataset_id: str,
    comparison_rule_id: str | None = None,
    max_records: int = 200,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_analysis_dirs(root)
    validation = validate_rule_effectiveness_inputs(rule_id, dataset_id, comparison_rule_id=comparison_rule_id, root=base)
    if validation.get("blockers"):
        return {"schema_version": PLAN_SCHEMA, "rule_id": rule_id, "dataset_id": dataset_id, "comparison_rule_id": comparison_rule_id, "record_count": 0, "record_ids": [], "warnings": [], "blockers": list(validation.get("blockers", []))}
    dataset = _load_dataset(base, dataset_id) or {}
    bounded = _bounded_records(dataset, max_records)
    rule = _load_rule_record(base, rule_id) or {}
    comparison_rule = _load_rule_record(base, comparison_rule_id) if comparison_rule_id else None
    metrics = ["match_coverage", "evaluation_reliability"]
    if _outcome_label_field(dataset):
        metrics.extend(["precision", "recall", "specificity", "balanced_accuracy"])
    plan = {
        "schema_version": PLAN_SCHEMA,
        "rule_id": rule_id,
        "rule_fingerprint": _hash_payload(rule),
        "dataset_id": dataset_id,
        "dataset_fingerprint": _dataset_fingerprint(dataset),
        "comparison_rule_id": comparison_rule_id,
        "comparison_rule_fingerprint": _hash_payload(comparison_rule) if isinstance(comparison_rule, dict) else None,
        "record_count": len(bounded),
        "record_ids": [str(item.get("record_id") or "") for item in bounded],
        "outcome_label_field": _outcome_label_field(dataset),
        "positive_outcome_value": _positive_outcome_value(dataset),
        "baseline_field": _baseline_field(dataset),
        "metrics_available": metrics,
        "record_limit": _normalize_max_records(max_records),
        "warnings": [],
        "blockers": [],
    }
    plan["plan_fingerprint"] = _hash_payload(
        {
            "schema_version": PLAN_SCHEMA,
            "rule_id": plan["rule_id"],
            "rule_fingerprint": plan["rule_fingerprint"],
            "comparison_rule_id": plan["comparison_rule_id"],
            "comparison_rule_fingerprint": plan["comparison_rule_fingerprint"],
            "dataset_id": plan["dataset_id"],
            "dataset_fingerprint": plan["dataset_fingerprint"],
            "record_ids": plan["record_ids"],
            "outcome_label_field": plan["outcome_label_field"],
            "positive_outcome_value": plan["positive_outcome_value"],
            "baseline_field": plan["baseline_field"],
            "record_limit": plan["record_limit"],
        }
    )
    return plan


def run_rule_effectiveness_backtest(
    rule_id: str,
    dataset_id: str,
    comparison_rule_id: str | None = None,
    max_records: int = 200,
    regenerate: bool = False,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_analysis_dirs(root)
    plan = build_rule_effectiveness_backtest_plan(rule_id, dataset_id, comparison_rule_id=comparison_rule_id, max_records=max_records, root=base)
    if plan.get("blockers"):
        return {"status": "blocked", "rule_id": rule_id, "dataset_id": dataset_id, "comparison_rule_id": comparison_rule_id, "warnings": [], "blockers": list(plan.get("blockers", []))}
    existing = None if regenerate else _load_analysis_by_plan(base, plan["plan_fingerprint"], rule_id=rule_id, dataset_id=dataset_id, comparison_rule_id=comparison_rule_id)
    if isinstance(existing, dict):
        receipt = _load_receipt_for_analysis(base, str(existing.get("analysis_id") or ""))
        if _analysis_current(base, existing, plan, comparison_rule_id):
            if isinstance(receipt, dict):
                return {"status": "already_analyzed", "analysis_id": existing.get("analysis_id"), "effectiveness_receipt_id": receipt.get("effectiveness_receipt_id"), "writes_performed": 0}
            return {"status": "blocked", "blockers": ["effectiveness_analysis_state_diverged"], "warnings": []}
    dataset = _load_dataset(base, dataset_id) or {}
    records = _bounded_records(dataset, max_records)
    rule = _load_rule_record(base, rule_id) or {}
    comparison_rule = _load_rule_record(base, comparison_rule_id) if comparison_rule_id else None
    certification = _load_certification_receipt_for_rule(base, rule_id) or {}
    rule_before = _hash_payload(rule)
    comparison_before = _hash_payload(comparison_rule) if isinstance(comparison_rule, dict) else None
    results = []
    comparison_results = []
    for item in records:
        context = deepcopy(dict(item.get("evaluation_context") or {}))
        primary = evaluate_canonical_rule(rule, context, root=base)
        normalized = _normalized_evaluation(primary, item, dataset)
        results.append(normalized)
        if isinstance(comparison_rule, dict):
            secondary = evaluate_canonical_rule(comparison_rule, context, root=base)
            comparison_results.append(_normalized_evaluation(secondary, item, dataset))
    rule_after = _hash_payload(_load_rule_record(base, rule_id) or {})
    comparison_after = _hash_payload(_load_rule_record(base, comparison_rule_id) or {}) if comparison_rule_id else None
    mutation = rule_before != rule_after or (comparison_rule_id and comparison_before != comparison_after)
    metrics = _core_metrics(results, len(records), mutation)
    comparison = _comparison_metrics(results, comparison_results, dataset, comparison_rule_id) if comparison_rule_id else {}
    outcome = _outcome_metrics(results, dataset)
    status = "failed" if mutation else "completed_with_warnings" if metrics["evaluation_error_count"] else "completed"
    blockers = ["persistent_state_mutated"] if mutation else []
    analysis = {
        "schema_version": ANALYSIS_SCHEMA,
        "analysis_id": _analysis_id(plan["plan_fingerprint"]),
        "rule_id": rule_id,
        "rule_fingerprint": plan["rule_fingerprint"],
        "certification_receipt_id": certification.get("certification_receipt_id"),
        "dataset_id": dataset_id,
        "dataset_fingerprint": plan["dataset_fingerprint"],
        "plan_fingerprint": plan["plan_fingerprint"],
        "status": status,
        "records_planned": len(records),
        "records_evaluated": metrics["records_evaluated"],
        "matched_count": metrics["matched_count"],
        "not_matched_count": metrics["not_matched_count"],
        "missing_context_field_count": metrics["missing_context_field_count"],
        "unsupported_count": metrics["unsupported_count"],
        "blocked_count": metrics["blocked_count"],
        "evaluation_error_count": metrics["evaluation_error_count"],
        "match_coverage": metrics["match_coverage"],
        "evaluation_completion_rate": metrics["evaluation_completion_rate"],
        "evaluation_error_rate": metrics["evaluation_error_rate"],
        "outcome_metrics": outcome,
        "comparison": comparison,
        "persistent_state_mutated": mutation,
        "created_at_utc": _now(),
        "warnings": [],
        "blockers": blockers,
        "record_ids": plan["record_ids"],
        "comparison_rule_id": comparison_rule_id,
        "comparison_rule_fingerprint": plan.get("comparison_rule_fingerprint"),
    }
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "effectiveness_receipt_id": _receipt_id(plan["plan_fingerprint"]),
        "analysis_id": analysis["analysis_id"],
        "rule_id": rule_id,
        "rule_fingerprint": plan["rule_fingerprint"],
        "certification_receipt_id": certification.get("certification_receipt_id"),
        "dataset_id": dataset_id,
        "dataset_fingerprint": plan["dataset_fingerprint"],
        "plan_fingerprint": plan["plan_fingerprint"],
        "records_evaluated": analysis["records_evaluated"],
        "comparison_rule_id": comparison_rule_id,
        "analysis_status": analysis["status"],
        "created_at_utc": _now(),
        "warnings": [],
    }
    analysis_path = _analysis_path(base, analysis["analysis_id"])
    receipt_path = _receipt_path(base, receipt["effectiveness_receipt_id"])
    before_analysis = _read_json(analysis_path)
    before_receipt = _read_json(receipt_path)
    before_analysis_index = _read_json(base / "indexes" / ANALYSIS_INDEX)
    before_receipt_index = _read_json(base / "indexes" / RECEIPT_INDEX)
    try:
        _atomic_write_json(analysis_path, analysis)
        _update_analysis_index(base)
        _atomic_write_json(receipt_path, receipt)
        _update_receipt_index(base)
    except Exception:
        _restore_json(analysis_path, before_analysis)
        _restore_json(receipt_path, before_receipt)
        _restore_json(base / "indexes" / ANALYSIS_INDEX, before_analysis_index)
        _restore_json(base / "indexes" / RECEIPT_INDEX, before_receipt_index)
        return {"status": "failed", "blockers": ["effectiveness_analysis_write_failure"], "warnings": []}
    return {**analysis, "effectiveness_receipt_id": receipt["effectiveness_receipt_id"]}


def load_rule_effectiveness_analysis(
    analysis_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_analysis_dirs(root)
    payload = _read_json(_analysis_path(base, analysis_id))
    if not isinstance(payload, dict):
        return {"status": "not_found", "analysis_id": analysis_id, "warnings": [], "blockers": ["effectiveness_analysis_not_found"]}
    return {"status": "loaded", "analysis": payload, "warnings": []}


def get_rule_effectiveness_health(
    rule_id: str | None = None,
    dataset_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_analysis_dirs(root)
    analyses = _load_analyses(base)
    receipts = _load_receipts(base)
    if rule_id is not None:
        analyses = [item for item in analyses if str(item.get("rule_id") or "") == rule_id]
        receipts = [item for item in receipts if str(item.get("rule_id") or "") == rule_id]
    if dataset_id is not None:
        analyses = [item for item in analyses if str(item.get("dataset_id") or "") == dataset_id]
        receipts = [item for item in receipts if str(item.get("dataset_id") or "") == dataset_id]
    if not analyses and not receipts:
        return {"status": "empty", "analysis_count": 0, "current_analysis_count": 0, "stale_analysis_count": 0, "completed_count": 0, "failed_count": 0, "mutation_detected_count": 0, "warnings": [], "recommended_action": "Run one focused certified rule analysis."}
    stale = 0
    corrupt = 0
    mutation = 0
    for item in analyses:
        dataset = _load_dataset(base, str(item.get("dataset_id") or ""))
        if not isinstance(dataset, dict):
            stale += 1
        elif item.get("dataset_fingerprint") != _dataset_fingerprint(dataset):
            stale += 1
        rule = _load_rule_record(base, str(item.get("rule_id") or ""))
        if not isinstance(rule, dict):
            stale += 1
        elif str(item.get("rule_fingerprint") or "") != _hash_payload(rule):
            stale += 1
        comparison_rule_id = str(item.get("comparison_rule_id") or "")
        if comparison_rule_id:
            comparison_rule = _load_rule_record(base, comparison_rule_id)
            if not isinstance(comparison_rule, dict):
                stale += 1
            elif str(item.get("comparison_rule_fingerprint") or "") != _hash_payload(comparison_rule):
                stale += 1
        receipt = _load_receipt_for_analysis(base, str(item.get("analysis_id") or ""))
        if not isinstance(receipt, dict):
            corrupt += 1
        elif (
            str(receipt.get("analysis_id") or "") != str(item.get("analysis_id") or "")
            or str(receipt.get("rule_fingerprint") or "") != str(item.get("rule_fingerprint") or "")
            or str(receipt.get("dataset_fingerprint") or "") != str(item.get("dataset_fingerprint") or "")
        ):
            corrupt += 1
        if item.get("persistent_state_mutated") is True:
            mutation += 1
        if _invalid_metric_value(item.get("match_coverage")) or _invalid_metric_value(item.get("evaluation_completion_rate")):
            corrupt += 1
    warnings = ["one_analysis_is_stale_after_rule_or_dataset_change"] if stale else []
    status = "corrupt" if corrupt else "blocked" if mutation else "warning" if stale else "healthy"
    return {
        "status": status,
        "analysis_count": len(analyses),
        "current_analysis_count": len(analyses) - stale,
        "stale_analysis_count": stale,
        "completed_count": sum(1 for item in analyses if str(item.get("status") or "").startswith("completed")),
        "failed_count": sum(1 for item in analyses if item.get("status") == "failed"),
        "mutation_detected_count": mutation,
        "warnings": warnings,
        "recommended_action": "Regenerate one stale focused backtest." if stale else "Rule effectiveness health is good.",
    }


def format_rule_effectiveness_report(
    analysis_id: str | None = None,
    rule_id: str | None = None,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    base = _ensure_analysis_dirs(root)
    analysis = _load_analysis_by_id(base, analysis_id) if analysis_id else _latest_analysis_for_rule(base, rule_id)
    if not isinstance(analysis, dict):
        return "Certified Rule Effectiveness Report\n\nStatus: not_found"
    current_plan = build_rule_effectiveness_backtest_plan(
        str(analysis.get("rule_id") or ""),
        str(analysis.get("dataset_id") or ""),
        comparison_rule_id=str(analysis.get("comparison_rule_id") or "") or None,
        root=base,
    )
    analysis_current = None if current_plan.get("blockers") else _analysis_current(
        base,
        analysis,
        current_plan,
        str(analysis.get("comparison_rule_id") or "") or None,
    )
    outcome = analysis.get("outcome_metrics", {})
    comparison = analysis.get("comparison", {})
    text = "\n".join(
        [
            "Certified Rule Effectiveness Report",
            "",
            f"Rule: {analysis.get('rule_id')}",
            "Certification: valid",
            f"Dataset: {analysis.get('dataset_id')}",
            f"Analysis Status: {analysis.get('status')}",
            f"Analysis Freshness: {'current' if analysis_current is True else 'stale' if analysis_current is False else 'unknown'}",
            "",
            "Evaluation:",
            f"- Records Planned: {analysis.get('records_planned', 0)}",
            f"- Records Evaluated: {analysis.get('records_evaluated', 0)}",
            f"- Matched: {analysis.get('matched_count', 0)}",
            f"- Not Matched: {analysis.get('not_matched_count', 0)}",
            f"- Errors: {analysis.get('evaluation_error_count', 0)}",
            f"- Match Coverage: {_percent(analysis.get('match_coverage'))}",
            f"- Persistent Mutation Detected: {'Yes' if analysis.get('persistent_state_mutated') else 'No'}",
            "",
            "Outcome Metrics:",
            f"- Labels Available: {'Yes' if outcome.get('outcome_metrics_status') != 'unavailable' else 'No'}",
            f"- Precision: {_percent(outcome.get('precision'))}",
            f"- Recall: {_percent(outcome.get('recall'))}",
            f"- Specificity: {_percent(outcome.get('specificity'))}",
            f"- Balanced Accuracy: {_percent(outcome.get('balanced_accuracy'))}",
            "",
            "Version Comparison:",
            f"- Comparison Rule: {comparison.get('comparison_rule_id') or 'none'}",
            f"- Match Disagreements: {comparison.get('match_disagreement_count', 0)}",
            f"- Disagreement Rate: {_percent(comparison.get('match_disagreement_rate'))}",
            "",
            "Important:",
            "This is a bounded read-only rule analysis.",
            "No recommendation, scoring change, rule mutation, or production replay action was performed.",
        ]
    )
    if public_safe:
        for needle in ("C:\\", "/Users/", "Traceback", "evaluation_context", "api_key", "secret", "token", "citation_text", "reviewer_note"):
            text = text.replace(needle, "[redacted]")
    return text


def get_rule_effectiveness_summary(
    rule_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_analysis_dirs(root)
    analysis = _latest_analysis_for_rule(base, rule_id)
    if not isinstance(analysis, dict):
        return {"rule_id": rule_id, "status": "not_found"}
    return {
        "rule_id": rule_id,
        "status": analysis.get("status"),
        "dataset_id": analysis.get("dataset_id"),
        "match_coverage": analysis.get("match_coverage"),
        "balanced_accuracy": (analysis.get("outcome_metrics") or {}).get("balanced_accuracy"),
        "comparison_rule_id": (analysis.get("comparison") or {}).get("comparison_rule_id"),
    }


def _ensure_analysis_dirs(root: Path | str) -> Path:
    base = ensure_source_knowledge_dirs(root)
    for folder in (ANALYSIS_DIR, RECEIPT_DIR, "indexes"):
        (base / folder).mkdir(parents=True, exist_ok=True)
    for path, payload in (
        (base / "indexes" / ANALYSIS_INDEX, {"schema_version": "rule_effectiveness_analysis_index_v1", "items": [], "updated_at_utc": _now()}),
        (base / "indexes" / RECEIPT_INDEX, {"schema_version": "rule_effectiveness_receipt_index_v1", "items": [], "updated_at_utc": _now()}),
    ):
        if not path.exists():
            _atomic_write_json(path, payload)
    return base


def _load_rule_record(root: Path, rule_id: str | None) -> dict[str, Any] | None:
    if not rule_id:
        return None
    loaded = load_canonical_rule(str(rule_id), root=root)
    if loaded.get("status") == "loaded":
        return deepcopy(dict(loaded.get("rule") or {}))
    path = root / "canonical_rules" / f"{_safe_id(str(rule_id))}.json"
    payload = _read_json(path)
    return deepcopy(dict(payload)) if isinstance(payload, dict) else None


def _load_certification_receipt_for_rule(root: Path, rule_id: str | None) -> dict[str, Any] | None:
    if not rule_id:
        return None
    matches = []
    for path in sorted((root / CERTIFICATION_RECEIPT_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict) and str(payload.get("rule_id") or "") == str(rule_id):
            matches.append(deepcopy(dict(payload)))
    return matches[-1] if matches else None


def _load_chain_for_rule_pair(root: Path, primary_rule_id: str, comparison_rule_id: str) -> dict[str, Any] | None:
    for path in sorted((root / SUPERSESSION_CHAIN_DIR).glob("*.json")):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        ids = {str(item.get("rule_id") or "") for item in payload.get("versions", []) if isinstance(item, Mapping)}
        if primary_rule_id in ids and comparison_rule_id in ids:
            return deepcopy(dict(payload))
    return None


def _load_dataset(root: Path, dataset_id: str) -> dict[str, Any] | None:
    for folder in (DATASET_DIR, REPLAY_DIR):
        path = root / folder / f"{_safe_id(dataset_id)}.json"
        payload = _read_json(path)
        if isinstance(payload, dict):
            return deepcopy(dict(payload))
    return None


def _validate_dataset_contract(dataset: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    if str(dataset.get("schema_version") or "") not in SUPPORTED_DATASET_SCHEMAS:
        blockers.append("dataset_schema_unsupported")
    records = dataset.get("records")
    if not isinstance(records, list):
        blockers.append("dataset_records_missing")
        return blockers
    seen_ids: set[str] = set()
    outcome_field = _outcome_label_field(dataset)
    baseline_field = _baseline_field(dataset)
    for item in records:
        if not isinstance(item, Mapping):
            blockers.append("dataset_record_invalid")
            continue
        record_id = str(item.get("record_id") or "")
        if not record_id or record_id in seen_ids:
            blockers.append("dataset_record_ids_not_unique")
        seen_ids.add(record_id)
        if not isinstance(item.get("evaluation_context"), Mapping):
            blockers.append("dataset_context_invalid")
        timestamp = item.get("timestamp_utc")
        if timestamp is not None and not isinstance(timestamp, str):
            blockers.append("dataset_timestamp_invalid")
        if outcome_field and outcome_field not in item:
            blockers.append("dataset_outcome_label_missing")
        if baseline_field and baseline_field not in item:
            blockers.append("dataset_baseline_label_missing")
    return _dedupe(blockers)


def _bounded_records(dataset: Mapping[str, Any], max_records: int) -> list[dict[str, Any]]:
    normalized_limit = _normalize_max_records(max_records)
    records = [deepcopy(dict(item)) for item in list(dataset.get("records", []) or []) if isinstance(item, Mapping)]
    records.sort(key=lambda item: (str(item.get("timestamp_utc") or ""), str(item.get("record_id") or "")))
    return records[:normalized_limit]


def _normalize_max_records(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 200
    return max(1, min(500, value))


def _dataset_fingerprint(dataset: Mapping[str, Any]) -> str:
    return _hash_payload(
        {
            "schema_version": dataset.get("schema_version"),
            "dataset_id": dataset.get("dataset_id"),
            "outcome_label_field": _outcome_label_field(dataset),
            "positive_outcome_value": _positive_outcome_value(dataset),
            "baseline_field": _baseline_field(dataset),
            "records": [
                {
                    "record_id": item.get("record_id"),
                    "timestamp_utc": item.get("timestamp_utc"),
                    "evaluation_context": item.get("evaluation_context"),
                    "outcome": item.get(_outcome_label_field(dataset)) if _outcome_label_field(dataset) else None,
                    "baseline": item.get(_baseline_field(dataset)) if _baseline_field(dataset) else None,
                }
                for item in _bounded_records(dataset, 500)
            ],
        }
    )


def _outcome_label_field(dataset: Mapping[str, Any] | None) -> str | None:
    if not isinstance(dataset, Mapping):
        return None
    text = str(dataset.get("outcome_label_field") or "").strip()
    return text or None


def _baseline_field(dataset: Mapping[str, Any] | None) -> str | None:
    if not isinstance(dataset, Mapping):
        return None
    text = str(dataset.get("baseline_field") or "").strip()
    return text or None


def _positive_outcome_value(dataset: Mapping[str, Any] | None) -> Any:
    return None if not isinstance(dataset, Mapping) else dataset.get("positive_outcome_value")


def _normalized_evaluation(result: Mapping[str, Any], record: Mapping[str, Any], dataset: Mapping[str, Any]) -> dict[str, Any]:
    outcome_field = _outcome_label_field(dataset)
    baseline_field = _baseline_field(dataset)
    return {
        "record_id": str(record.get("record_id") or ""),
        "result": result.get("result"),
        "matched": result.get("matched") if isinstance(result.get("matched"), bool) else None,
        "blockers": list(result.get("blockers", [])),
        "outcome_label": record.get(outcome_field) if outcome_field else None,
        "baseline_value": record.get(baseline_field) if baseline_field else None,
    }


def _core_metrics(results: list[dict[str, Any]], planned: int, mutation: bool) -> dict[str, Any]:
    matched = sum(1 for item in results if item.get("result") == "matched")
    not_matched = sum(1 for item in results if item.get("result") == "not_matched")
    blocked = sum(1 for item in results if item.get("result") == "blocked")
    unsupported = sum(1 for item in results if item.get("result") == "unsupported")
    errors = sum(1 for item in results if item.get("result") == "error")
    successful = matched + not_matched
    return {
        "records_evaluated": len(results),
        "matched_count": matched,
        "not_matched_count": not_matched,
        "missing_context_field_count": 0,
        "unsupported_count": unsupported,
        "blocked_count": blocked,
        "evaluation_error_count": errors,
        "match_coverage": _ratio(matched, successful),
        "evaluation_completion_rate": _ratio(successful, planned),
        "evaluation_error_rate": _ratio(errors + blocked + unsupported, planned),
        "persistent_state_mutated": mutation,
    }


def _outcome_metrics(results: list[dict[str, Any]], dataset: Mapping[str, Any]) -> dict[str, Any]:
    field = _outcome_label_field(dataset)
    positive = _positive_outcome_value(dataset)
    if not field:
        return {"outcome_metrics_status": "unavailable", "reason": "controlled_outcome_labels_missing"}
    labeled = [item for item in results if field and item.get("outcome_label") is not None and isinstance(item.get("matched"), bool)]
    if not labeled:
        return {"outcome_metrics_status": "unavailable", "reason": "controlled_outcome_labels_missing"}
    tp = sum(1 for item in labeled if item.get("matched") is True and item.get("outcome_label") == positive)
    fp = sum(1 for item in labeled if item.get("matched") is True and item.get("outcome_label") != positive)
    tn = sum(1 for item in labeled if item.get("matched") is False and item.get("outcome_label") != positive)
    fn = sum(1 for item in labeled if item.get("matched") is False and item.get("outcome_label") == positive)
    prevalence = _ratio(tp + fn, len(labeled))
    return {
        "outcome_metrics_status": "available",
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "precision": _ratio(tp, tp + fp),
        "recall": _ratio(tp, tp + fn),
        "specificity": _ratio(tn, tn + fp),
        "negative_predictive_value": _ratio(tn, tn + fn),
        "accuracy": _ratio(tp + tn, len(labeled)),
        "balanced_accuracy": _mean(_ratio(tp, tp + fn), _ratio(tn, tn + fp)),
        "positive_outcome_prevalence": prevalence,
        "baseline_comparison_status": "available" if _baseline_field(dataset) else "unavailable",
    }


def _comparison_metrics(primary: list[dict[str, Any]], comparison: list[dict[str, Any]], dataset: Mapping[str, Any], comparison_rule_id: str | None) -> dict[str, Any]:
    pairs = list(zip(primary, comparison))
    both = sum(1 for left, right in pairs if left.get("matched") is True and right.get("matched") is True)
    primary_only = sum(1 for left, right in pairs if left.get("matched") is True and right.get("matched") is False)
    comparison_only = sum(1 for left, right in pairs if left.get("matched") is False and right.get("matched") is True)
    neither = sum(1 for left, right in pairs if left.get("matched") is False and right.get("matched") is False)
    disagreements = primary_only + comparison_only
    payload = {
        "comparison_rule_id": comparison_rule_id,
        "primary_matched_count": sum(1 for item in primary if item.get("matched") is True),
        "comparison_matched_count": sum(1 for item in comparison if item.get("matched") is True),
        "both_matched": both,
        "primary_only_matched": primary_only,
        "comparison_only_matched": comparison_only,
        "neither_matched": neither,
        "match_disagreement_count": disagreements,
        "match_disagreement_rate": _ratio(disagreements, len(pairs)),
    }
    if _outcome_label_field(dataset):
        primary_metrics = _outcome_metrics(primary, dataset)
        comparison_metrics = _outcome_metrics(comparison, dataset)
        payload["primary_outcome_metrics"] = primary_metrics
        payload["comparison_outcome_metrics"] = comparison_metrics
        if primary_metrics.get("outcome_metrics_status") == "available" and comparison_metrics.get("outcome_metrics_status") == "available":
            payload["metric_deltas"] = {
                "precision_delta": _delta(primary_metrics.get("precision"), comparison_metrics.get("precision")),
                "recall_delta": _delta(primary_metrics.get("recall"), comparison_metrics.get("recall")),
                "specificity_delta": _delta(primary_metrics.get("specificity"), comparison_metrics.get("specificity")),
                "balanced_accuracy_delta": _delta(primary_metrics.get("balanced_accuracy"), comparison_metrics.get("balanced_accuracy")),
            }
    return payload


def _analysis_current(root: Path, analysis: Mapping[str, Any], plan: Mapping[str, Any], comparison_rule_id: str | None) -> bool:
    dataset = _load_dataset(root, str(plan.get("dataset_id") or ""))
    if not isinstance(dataset, dict):
        return False
    if str(analysis.get("plan_fingerprint") or "") != str(plan.get("plan_fingerprint") or ""):
        return False
    if str(analysis.get("dataset_fingerprint") or "") != _dataset_fingerprint(dataset):
        return False
    if str(analysis.get("rule_fingerprint") or "") != str(plan.get("rule_fingerprint") or ""):
        return False
    if comparison_rule_id and str(analysis.get("comparison_rule_fingerprint") or "") != str(plan.get("comparison_rule_fingerprint") or ""):
        return False
    return True


def _load_analyses(root: Path) -> list[dict[str, Any]]:
    items = []
    for path in sorted((root / ANALYSIS_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _load_receipts(root: Path) -> list[dict[str, Any]]:
    items = []
    for path in sorted((root / RECEIPT_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _analysis_id(plan_fingerprint: str) -> str:
    return f"rule_effectiveness_{plan_fingerprint[7:23]}"


def _receipt_id(plan_fingerprint: str) -> str:
    return f"rule_effectiveness_receipt_{plan_fingerprint[7:23]}"


def _analysis_path(root: Path, analysis_id: str) -> Path:
    return root / ANALYSIS_DIR / f"{_safe_id(analysis_id)}.json"


def _receipt_path(root: Path, receipt_id: str) -> Path:
    return root / RECEIPT_DIR / f"{_safe_id(receipt_id)}.json"


def _load_analysis_by_id(root: Path, analysis_id: str | None) -> dict[str, Any] | None:
    if not analysis_id:
        return None
    payload = _read_json(_analysis_path(root, str(analysis_id)))
    return deepcopy(dict(payload)) if isinstance(payload, dict) else None


def _latest_analysis_for_rule(root: Path, rule_id: str | None) -> dict[str, Any] | None:
    if not rule_id:
        return None
    matches = [item for item in _load_analyses(root) if str(item.get("rule_id") or "") == str(rule_id)]
    matches.sort(key=lambda item: str(item.get("created_at_utc") or ""))
    return deepcopy(dict(matches[-1])) if matches else None


def _load_analysis_by_plan(root: Path, plan_fingerprint: str | None, *, rule_id: str, dataset_id: str, comparison_rule_id: str | None) -> dict[str, Any] | None:
    for item in _load_analyses(root):
        if plan_fingerprint and str(item.get("plan_fingerprint") or "") == plan_fingerprint:
            return deepcopy(dict(item))
        if not plan_fingerprint and str(item.get("rule_id") or "") == rule_id and str(item.get("dataset_id") or "") == dataset_id and str(item.get("comparison_rule_id") or "") == str(comparison_rule_id or ""):
            return deepcopy(dict(item))
    return None


def _load_receipt_for_analysis(root: Path, analysis_id: str) -> dict[str, Any] | None:
    for item in _load_receipts(root):
        if str(item.get("analysis_id") or "") == str(analysis_id):
            return deepcopy(dict(item))
    return None


def _update_analysis_index(root: Path) -> None:
    items = []
    for item in _load_analyses(root):
        items.append(
            {
                "analysis_id": item.get("analysis_id"),
                "rule_id": item.get("rule_id"),
                "dataset_id": item.get("dataset_id"),
                "comparison_rule_id": item.get("comparison_rule_id"),
                "status": item.get("status"),
                "created_at_utc": item.get("created_at_utc"),
            }
        )
    _atomic_write_json(root / "indexes" / ANALYSIS_INDEX, {"schema_version": "rule_effectiveness_analysis_index_v1", "items": items, "updated_at_utc": _now()})


def _update_receipt_index(root: Path) -> None:
    items = []
    for item in _load_receipts(root):
        items.append(
            {
                "effectiveness_receipt_id": item.get("effectiveness_receipt_id"),
                "analysis_id": item.get("analysis_id"),
                "rule_id": item.get("rule_id"),
                "dataset_id": item.get("dataset_id"),
                "analysis_status": item.get("analysis_status"),
                "created_at_utc": item.get("created_at_utc"),
            }
        )
    _atomic_write_json(root / "indexes" / RECEIPT_INDEX, {"schema_version": "rule_effectiveness_receipt_index_v1", "items": items, "updated_at_utc": _now()})


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _mean(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return (left + right) / 2


def _delta(primary: float | None, comparison: float | None) -> float | None:
    if primary is None or comparison is None:
        return None
    return primary - comparison


def _percent(value: Any) -> str:
    if value is None:
        return "null"
    return f"{float(value) * 100:.2f}%"


def _invalid_metric_value(value: Any) -> bool:
    return isinstance(value, float) and (math.isnan(value) or math.isinf(value))


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(dict(payload), handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            pass
    os.replace(temp_path, path)


def _restore_json(path: Path, payload: Any) -> None:
    if payload is None:
        if path.exists():
            path.unlink()
        return
    _atomic_write_json(path, payload)


def _hash_payload(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"_", "-", "."} else "_" for char in str(value).strip()) or "object"


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in values if str(item)))


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
