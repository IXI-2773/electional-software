"""Single-PDF scoped batch orchestration for rule effectiveness analysis and recommendations."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from . import rule_effectiveness_analysis as analysis_backend
from . import rule_effectiveness_recommendation as recommendation_backend
from .canonical_rule_runtime import get_canonical_rule_runtime_capability, list_canonical_rules, load_canonical_rule
from .document_manifest import calculate_document_revision_state, load_document_manifest
from .source_documents import SOURCE_DOCUMENT_ROOT, load_source_document

RUN_DIR = "rule_batch_runs"
RECEIPT_DIR = "rule_batch_receipts"
RUN_INDEX = "rule_batch_run_index.json"
RECEIPT_INDEX = "rule_batch_receipt_index.json"
PLAN_SCHEMA = "rule_batch_plan_v2"
LEGACY_PLAN_SCHEMA = "rule_batch_plan_v1"
RUN_SCHEMA = "rule_batch_run_v2"
RECEIPT_SCHEMA = "rule_batch_receipt_v2"
LEGACY_RECEIPT_SCHEMA = "rule_batch_receipt_v1"
DEFAULT_MAX_RULES = 10
HARD_MAX_RULES = 25
DEFAULT_MAX_RECORDS_PER_RULE = 200
HARD_MAX_RECORDS_PER_RULE = 500
HARD_MAX_TOTAL_EVALUATIONS = 5000


def build_rule_batch_workspace(
    document_id: str,
    source_revision: int,
    dataset_id: str,
    policy_id: str = "default_v1",
    rule_ids: list[str] | None = None,
    include_document_certified_rules: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    scope = _validate_document_scope(base, document_id, source_revision)
    validation = _validate_batch_inputs(base, dataset_id, policy_id)
    rules, selection = _select_rules(base, document_id, source_revision, rule_ids, include_document_certified_rules)
    eligible = [item for item in rules if item["classification"] == "eligible"]
    blocked = [item for item in rules if item["classification"] != "eligible"]
    blockers = _dedupe(list(scope["blockers"]) + list(validation["blockers"]))
    if selection["explicit_scope_violation"]:
        blockers.append("rule_batch_explicit_rule_scope_violation")
    warnings = _dedupe(list(scope["warnings"]) + list(validation["warnings"]))
    return {
        "document_id": document_id,
        "source_revision": _normalize_revision(source_revision),
        "document_status": scope["document_status"],
        "revision_lock_status": scope["revision_lock_status"],
        "document_manifest_fingerprint": scope["document_manifest_fingerprint"],
        "dataset_id": dataset_id,
        "dataset_status": "available" if not validation["dataset_blockers"] else "blocked",
        "policy_id": policy_id,
        "policy_status": "valid" if not validation["policy_blockers"] else "invalid",
        "selected_rule_count": len(rules),
        "eligible_rule_count": len(eligible),
        "blocked_rule_count": len(blocked),
        "foreign_document_rule_count": selection["foreign_document_rule_count"],
        "foreign_revision_rule_count": selection["foreign_revision_rule_count"],
        "provenance_missing_rule_count": selection["provenance_missing_rule_count"],
        "provenance_conflict_rule_count": selection["provenance_conflict_rule_count"],
        "estimated_analysis_count": len(eligible),
        "estimated_recommendation_count": len(eligible),
        "items": rules,
        "warnings": warnings,
        "blockers": blockers,
        "recommended_action": "Build the single-PDF batch plan." if not blockers else "Resolve document, revision, dataset, policy, or explicit rule blockers before planning.",
    }


def build_rule_batch_plan(
    document_id: str,
    source_revision: int,
    dataset_id: str,
    policy_id: str = "default_v1",
    rule_ids: list[str] | None = None,
    include_document_certified_rules: bool = True,
    max_rules: int = DEFAULT_MAX_RULES,
    max_records_per_rule: int = DEFAULT_MAX_RECORDS_PER_RULE,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    workspace = build_rule_batch_workspace(
        document_id,
        source_revision,
        dataset_id,
        policy_id=policy_id,
        rule_ids=rule_ids,
        include_document_certified_rules=include_document_certified_rules,
        root=base,
    )
    blockers = list(workspace["blockers"])
    warnings = list(workspace["warnings"])
    max_rules_value = _normalize_positive_int(max_rules, DEFAULT_MAX_RULES)
    max_records_value = _normalize_positive_int(max_records_per_rule, DEFAULT_MAX_RECORDS_PER_RULE)
    if max_rules_value > HARD_MAX_RULES:
        blockers.append("rule_batch_max_rules_exceeds_hard_limit")
    if max_records_value > HARD_MAX_RECORDS_PER_RULE:
        blockers.append("rule_batch_max_records_per_rule_exceeds_hard_limit")
    validation = _validate_batch_inputs(base, dataset_id, policy_id)
    dataset = validation["dataset"]
    policy = validation["policy"]
    eligible_items = [item for item in workspace["items"] if item["classification"] == "eligible"]
    omitted_by_limit = max(0, len(eligible_items) - max_rules_value)
    selected_items = eligible_items[:max_rules_value]
    total_planned_evaluations = len(selected_items) * max_records_value
    if total_planned_evaluations > HARD_MAX_TOTAL_EVALUATIONS:
        blockers.append("rule_batch_total_evaluations_exceeds_hard_limit")
    plan_items = []
    for index, item in enumerate(selected_items):
        plan_items.append(
            {
                "item_index": index,
                "rule_id": item["rule_id"],
                "document_id": document_id,
                "source_revision": workspace["source_revision"],
                "provenance_status": item["provenance_status"],
                "provenance_fingerprint": item["provenance_fingerprint"],
                "provenance_trace": deepcopy(item["provenance_trace"]),
                "rule_fingerprint": item["rule_fingerprint"],
                "certification_receipt_id": item["certification_receipt_id"],
                "status": "pending",
                "analysis_id": None,
                "analysis_receipt_id": None,
                "recommendation_id": None,
                "recommendation_type": None,
                "analysis_status": None,
                "recommendation_status": None,
                "failure_stage": None,
                "failure_classification": None,
                "warnings": list(item["warnings"]),
                "blockers": [],
            }
        )
    plan_core = {
        "schema_version": PLAN_SCHEMA,
        "document_id": document_id,
        "source_revision": workspace["source_revision"],
        "document_manifest_fingerprint": workspace["document_manifest_fingerprint"],
        "dataset_id": dataset_id,
        "dataset_fingerprint": analysis_backend._dataset_fingerprint(dataset) if isinstance(dataset, Mapping) else None,
        "policy_id": policy_id,
        "policy_fingerprint": recommendation_backend._policy_fingerprint(policy) if isinstance(policy, Mapping) else None,
        "ordered_rule_ids": [item["rule_id"] for item in plan_items],
        "ordered_rule_fingerprints": [item["rule_fingerprint"] for item in plan_items],
        "ordered_provenance_fingerprints": [item["provenance_fingerprint"] for item in plan_items],
        "ordered_certification_receipt_ids": [item["certification_receipt_id"] for item in plan_items],
        "max_rules": max_rules_value,
        "max_records_per_rule": max_records_value,
    }
    plan_fingerprint = analysis_backend._hash_payload(plan_core)
    plan = {
        "schema_version": PLAN_SCHEMA,
        "batch_plan_id": _plan_id(plan_fingerprint),
        "document_id": document_id,
        "source_revision": workspace["source_revision"],
        "document_manifest_fingerprint": workspace["document_manifest_fingerprint"],
        "dataset_id": dataset_id,
        "dataset_fingerprint": plan_core["dataset_fingerprint"],
        "policy_id": policy_id,
        "policy_fingerprint": plan_core["policy_fingerprint"],
        "max_rules": max_rules_value,
        "max_records_per_rule": max_records_value,
        "rule_count": len(plan_items),
        "eligible_rule_count": len(eligible_items),
        "rules_omitted_by_limit": omitted_by_limit,
        "foreign_document_rule_count": workspace["foreign_document_rule_count"],
        "foreign_revision_rule_count": workspace["foreign_revision_rule_count"],
        "total_planned_evaluations": total_planned_evaluations,
        "items": plan_items,
        "plan_fingerprint": plan_fingerprint,
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
    }
    path = _plan_path(base, plan["batch_plan_id"])
    before_plan = analysis_backend._read_json(path)
    before_index = analysis_backend._read_json(base / "indexes" / RUN_INDEX)
    try:
        analysis_backend._atomic_write_json(path, plan)
        _update_run_index(base)
    except Exception:
        analysis_backend._restore_json(path, before_plan)
        analysis_backend._restore_json(base / "indexes" / RUN_INDEX, before_index)
        return {**plan, "status": "failed"}
    return plan


def run_rule_batch_analysis(
    batch_plan_id: str,
    resume: bool = True,
    stop_after_items: int | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    plan_payload = _load_plan_record(base, batch_plan_id)
    if not isinstance(plan_payload, dict):
        return {"status": "blocked", "batch_plan_id": batch_plan_id, "warnings": [], "blockers": ["rule_batch_plan_not_found"]}
    if str(plan_payload.get("schema_version") or "") != PLAN_SCHEMA or not _is_scoped_plan(plan_payload):
        return {"status": "blocked", "batch_plan_id": batch_plan_id, "warnings": [], "blockers": ["legacy_unscoped_batch_plan"], "recommended_action": "Rebuild the batch plan with one document ID and source revision."}
    plan = deepcopy(plan_payload)
    if plan.get("blockers"):
        return {"status": "blocked", "batch_plan_id": batch_plan_id, "warnings": list(plan.get("warnings", [])), "blockers": list(plan.get("blockers", []))}
    stale_blockers = _plan_stale_blockers(base, plan)
    if stale_blockers:
        return {"status": "stale", "batch_plan_id": batch_plan_id, "warnings": [], "blockers": stale_blockers}
    run = _load_run_for_plan(base, batch_plan_id)
    if isinstance(run, dict):
        run_status = str(run.get("status") or "")
        if run_status in {"completed", "completed_with_failures"}:
            receipt = _load_receipt_for_run(base, str(run.get("batch_run_id") or ""))
            return {"status": "already_completed", "batch_run_id": run.get("batch_run_id"), "batch_receipt_id": (receipt or {}).get("batch_receipt_id"), "writes_performed": 0}
        if run_status == "cancelled":
            return {"status": "blocked", "batch_run_id": run.get("batch_run_id"), "warnings": [], "blockers": ["rule_batch_run_cancelled"]}
        if not resume and run_status in {"planned", "running", "paused"}:
            return {"status": "blocked", "batch_run_id": run.get("batch_run_id"), "warnings": [], "blockers": ["rule_batch_run_resume_required"]}
        run_stale = _run_stale_blockers(base, run, plan)
        if run_stale:
            run["status"] = "stale"
            run["blockers"] = _dedupe(list(run.get("blockers", [])) + run_stale)
            _persist_run(base, run)
            return {"status": "stale", "batch_run_id": run.get("batch_run_id"), "warnings": [], "blockers": run_stale}
        current_run = deepcopy(run)
    else:
        current_run = _new_run_from_plan(plan)
        if not _persist_run(base, current_run):
            return {"status": "failed", "batch_plan_id": batch_plan_id, "warnings": [], "blockers": ["rule_batch_run_write_failure"]}
    processed_this_call = 0
    current_run["status"] = "running"
    _persist_run(base, current_run)
    items = current_run["items"]
    next_index = int(current_run.get("next_item_index", 0) or 0)
    while next_index < len(items):
        stale_before_item = _run_stale_blockers(base, current_run, plan)
        if stale_before_item:
            current_run["status"] = "stale"
            current_run["blockers"] = _dedupe(list(current_run.get("blockers", [])) + stale_before_item)
            current_run["updated_at_utc"] = analysis_backend._now()
            _persist_run(base, current_run)
            return current_run
        item = items[next_index]
        if str(item.get("status") or "") in {"recommendation_completed", "completed_with_warnings", "blocked", "failed", "skipped_stale", "cancelled"}:
            next_index += 1
            current_run["next_item_index"] = next_index
            continue
        processed_this_call += 1
        result_item = _process_batch_item(base, plan, item)
        items[next_index] = result_item
        current_run["items"] = items
        next_index += 1
        current_run["next_item_index"] = next_index
        _refresh_run_counts(current_run)
        if stop_after_items is not None and processed_this_call >= _normalize_positive_int(stop_after_items, 1):
            current_run["status"] = "paused"
            current_run["updated_at_utc"] = analysis_backend._now()
            _persist_run(base, current_run)
            return current_run
        current_run["updated_at_utc"] = analysis_backend._now()
        _persist_run(base, current_run)
    final_status = "completed"
    if int(current_run.get("failed_count", 0) or 0) or int(current_run.get("blocked_count", 0) or 0):
        final_status = "completed_with_failures"
    current_run["status"] = final_status
    current_run["updated_at_utc"] = analysis_backend._now()
    _persist_run(base, current_run)
    receipt = _create_receipt_if_needed(base, current_run, plan)
    return {**current_run, "batch_receipt_id": (receipt or {}).get("batch_receipt_id")}


def load_rule_batch_run(
    batch_run_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    payload = analysis_backend._read_json(_run_path(base, batch_run_id))
    if not isinstance(payload, dict):
        return {"status": "not_found", "batch_run_id": batch_run_id, "warnings": [], "blockers": ["rule_batch_run_not_found"]}
    return {"status": "loaded", "batch_run": payload, "warnings": []}


def cancel_rule_batch_run(
    batch_run_id: str,
    reason: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    if not _non_empty_text(reason):
        return {"status": "blocked", "batch_run_id": batch_run_id, "warnings": [], "blockers": ["rule_batch_cancellation_reason_required"]}
    run = _load_run_by_id(base, batch_run_id)
    if not isinstance(run, dict):
        return {"status": "blocked", "batch_run_id": batch_run_id, "warnings": [], "blockers": ["rule_batch_run_not_found"]}
    if str(run.get("status") or "") not in {"planned", "running", "paused"}:
        return {"status": "blocked", "batch_run_id": batch_run_id, "warnings": [], "blockers": ["rule_batch_run_not_cancellable"]}
    run["status"] = "cancelled"
    run["cancellation_reason"] = str(reason).strip()
    run["updated_at_utc"] = analysis_backend._now()
    _refresh_run_counts(run)
    if not _persist_run(base, run):
        return {"status": "failed", "batch_run_id": batch_run_id, "warnings": [], "blockers": ["rule_batch_run_write_failure"]}
    receipt = _create_receipt_if_needed(base, run, _load_plan_record(base, str(run.get("batch_plan_id") or "")))
    return {**run, "batch_receipt_id": (receipt or {}).get("batch_receipt_id")}


def get_rule_batch_health(
    batch_run_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    runs = _load_runs(base)
    receipts = _load_receipts(base)
    if batch_run_id:
        runs = [item for item in runs if str(item.get("batch_run_id") or "") == batch_run_id]
        receipts = [item for item in receipts if str(item.get("batch_run_id") or "") == batch_run_id]
    if not runs and not receipts:
        return {"status": "empty", "batch_run_count": 0, "completed_count": 0, "completed_with_failures_count": 0, "paused_count": 0, "cancelled_count": 0, "stale_count": 0, "divergent_state_count": 0, "warnings": [], "recommended_action": "Build one single-PDF rule batch plan."}
    paused = sum(1 for item in runs if str(item.get("status") or "") == "paused")
    completed = sum(1 for item in runs if str(item.get("status") or "") == "completed")
    completed_with_failures = sum(1 for item in runs if str(item.get("status") or "") == "completed_with_failures")
    cancelled = sum(1 for item in runs if str(item.get("status") or "") == "cancelled")
    stale = 0
    divergent = 0
    stale_analysis_skips = 0
    other_stale_skips = 0
    warnings: list[str] = []
    blockers: list[str] = []
    for run in runs:
        plan_record = _load_plan_record(base, str(run.get("batch_plan_id") or ""))
        if not isinstance(plan_record, dict):
            divergent += 1
            blockers.append("rule_batch_plan_missing")
            continue
        if not _is_scoped_plan(plan_record):
            divergent += 1
            blockers.append("legacy_unscoped_batch_plan")
        if _run_stale_blockers(base, run, plan_record):
            stale += 1
        stale_skip_counts = _stale_skip_counts(run.get("items", []))
        stale_analysis_skips += int(stale_skip_counts.get("analysis_stale_before_recommendation", 0) or 0)
        other_stale_skips += int(stale_skip_counts.get("other_stale", 0) or 0)
        if _mixed_source_items(run.get("items", []), run.get("document_id"), run.get("source_revision")):
            divergent += 1
            blockers.append("mixed_source_batch_run_items")
        receipt = _load_receipt_for_run(base, str(run.get("batch_run_id") or ""))
        if str(run.get("status") or "") in {"completed", "completed_with_failures", "cancelled"}:
            if not receipt:
                divergent += 1
                blockers.append("rule_batch_receipt_missing")
            elif receipt.get("document_id") != run.get("document_id"):
                divergent += 1
                blockers.append("receipt_to_run_document_mismatch")
            elif receipt.get("source_revision") != run.get("source_revision"):
                divergent += 1
                blockers.append("receipt_to_run_revision_mismatch")
    if paused:
        warnings.append("one_batch_run_is_paused")
    status = "corrupt" if divergent else "blocked" if stale or blockers else "warning" if warnings else "healthy"
    return {
        "status": status,
        "batch_run_count": len(runs),
        "completed_count": completed,
        "completed_with_failures_count": completed_with_failures,
        "paused_count": paused,
        "cancelled_count": cancelled,
        "stale_count": stale,
        "stale_analysis_skip_count": stale_analysis_skips,
        "other_stale_skip_count": other_stale_skips,
        "divergent_state_count": divergent,
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
        "recommended_action": "Rebuild the batch against the current document revision." if stale else "Batch health is good.",
    }


def format_rule_batch_report(
    batch_run_id: str | None = None,
    batch_receipt_id: str | None = None,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    base = _ensure_dirs(root)
    receipt = _load_receipt_by_id(base, batch_receipt_id) if batch_receipt_id else None
    run = _load_run_by_id(base, batch_run_id or str((receipt or {}).get("batch_run_id") or ""))
    if not isinstance(run, dict):
        if isinstance(receipt, dict) and str(receipt.get("schema_version") or "") == LEGACY_RECEIPT_SCHEMA:
            return "Single-PDF Batch Rule Analysis Report\n\nScope Status: legacy_unscoped"
        return "Single-PDF Batch Rule Analysis Report\n\nStatus: not_found"
    recommendation_counts = _recommendation_counts(run.get("items", []))
    stale_skip_counts = _stale_skip_counts(run.get("items", []))
    stale_skip_reasons = _stale_skip_reason_counts(run.get("items", []))
    top_stale_skip_reasons = ", ".join(
        f"{reason} ({count})"
        for reason, count in sorted(stale_skip_reasons.items(), key=lambda item: (-item[1], item[0]))[:3]
    ) or "none"
    lines = [
        "Single-PDF Batch Rule Analysis Report",
        "",
        f"Document: {run.get('document_id')}",
        f"Source Revision: {run.get('source_revision')}",
        "Scope: One submitted PDF",
        f"Status: {run.get('status')}",
        "",
        "Selection:",
        f"- Eligible Rules Discovered: {run.get('eligible_rule_count', run.get('planned_rule_count', len(run.get('items', []))))}",
        f"- Rules Selected: {run.get('planned_rule_count', len(run.get('items', [])))}",
        f"- Rules Omitted by Limit: {run.get('rules_omitted_by_limit', 0)}",
        f"- Foreign-Document Rules: {run.get('foreign_document_rule_count', 0)}",
        f"- Foreign-Revision Rules: {run.get('foreign_revision_rule_count', 0)}",
        "",
        "Processing:",
        f"- Rules Processed: {run.get('processed_count', 0)}",
        f"- Successful: {run.get('successful_count', 0)}",
        f"- Failed or Blocked: {int(run.get('failed_count', 0) or 0) + int(run.get('blocked_count', 0) or 0)}",
        f"- Stale Analysis Skips: {stale_skip_counts.get('analysis_stale_before_recommendation', 0)}",
        f"- Other Stale Skips: {stale_skip_counts.get('other_stale', 0)}",
        f"- Top Stale Skip Reasons: {top_stale_skip_reasons}",
        "",
        "Recommendations:",
        f"- Continue: {recommendation_counts.get('continue', 0)}",
        f"- Monitor: {recommendation_counts.get('monitor', 0)}",
        f"- Rollback Review Candidate: {recommendation_counts.get('rollback_candidate', 0)}",
        f"- Supersession Review Candidate: {recommendation_counts.get('supersession_review_candidate', 0)}",
        f"- Insufficient Evidence: {recommendation_counts.get('insufficient_evidence', 0)}",
        "",
        "Important:",
        "Every processed rule was required to trace to this document and source revision.",
        "No rules from another PDF or revision were analyzed.",
        "No recommendation was reviewed or executed.",
    ]
    text = "\n".join(lines)
    if public_safe:
        for needle in ("C:\\", "/Users/", "evaluation_context", "Traceback", "reviewer_note", "api_key", "secret", "token", "citation_text", "proposal_content"):
            text = text.replace(needle, "[redacted]")
    return text


def get_rule_batch_summary(
    batch_run_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    run = _load_run_by_id(base, batch_run_id)
    if not isinstance(run, dict):
        return {"status": "not_found", "batch_run_id": batch_run_id}
    stale_skip_counts = _stale_skip_counts(run.get("items", []))
    return {
        "batch_run_id": batch_run_id,
        "status": run.get("status"),
        "document_id": run.get("document_id"),
        "source_revision": run.get("source_revision"),
        "processed_count": run.get("processed_count"),
        "successful_count": run.get("successful_count"),
        "failed_count": run.get("failed_count"),
        "stale_analysis_skip_count": stale_skip_counts.get("analysis_stale_before_recommendation", 0),
        "other_stale_skip_count": stale_skip_counts.get("other_stale", 0),
        "next_item_index": run.get("next_item_index"),
    }


def _ensure_dirs(root: Path | str) -> Path:
    base = analysis_backend._ensure_analysis_dirs(root)
    recommendation_backend._ensure_dirs(base)
    for folder in (RUN_DIR, RECEIPT_DIR, "indexes"):
        (base / folder).mkdir(parents=True, exist_ok=True)
    for path, payload in (
        (base / "indexes" / RUN_INDEX, {"schema_version": "rule_batch_run_index_v1", "items": [], "updated_at_utc": analysis_backend._now()}),
        (base / "indexes" / RECEIPT_INDEX, {"schema_version": "rule_batch_receipt_index_v1", "items": [], "updated_at_utc": analysis_backend._now()}),
    ):
        if not path.exists():
            analysis_backend._atomic_write_json(path, payload)
    return base


def _validate_batch_inputs(base: Path, dataset_id: str, policy_id: str) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    capability = get_canonical_rule_runtime_capability(root=base)
    if not capability.get("repository_available"):
        blockers.append("canonical_rule_repository_unreadable")
    dataset = analysis_backend._load_dataset(base, dataset_id)
    dataset_blockers: list[str] = []
    if not isinstance(dataset, dict):
        dataset_blockers.append("historical_rule_dataset_unavailable")
    else:
        dataset_blockers.extend(analysis_backend._validate_dataset_contract(dataset))
    policy = recommendation_backend._load_policy(policy_id)
    policy_validation = recommendation_backend._validate_policy(policy)
    blockers.extend(dataset_blockers)
    blockers.extend(policy_validation["blockers"])
    warnings.extend(policy_validation["warnings"])
    return {
        "dataset": dataset,
        "policy": policy,
        "dataset_blockers": _dedupe(dataset_blockers),
        "policy_blockers": _dedupe(policy_validation["blockers"]),
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
    }


def _validate_document_scope(base: Path, document_id: str, source_revision: Any) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    normalized_document_id = _non_empty_text(document_id)
    normalized_revision = _normalize_revision(source_revision)
    manifest_fingerprint = None
    document_status = "unknown"
    revision_lock_status = "invalid"
    if not normalized_document_id:
        blockers.append("document_id_required")
    if normalized_revision is None:
        blockers.append("source_revision_required")
    record = load_source_document(normalized_document_id or "", root=base, missing_ok=True) if normalized_document_id else None
    if normalized_document_id and record is None:
        blockers.append("document_not_found")
    manifest_loaded = load_document_manifest(normalized_document_id or "", root=base) if normalized_document_id else {"status": "not_found", "manifest": None}
    manifest = manifest_loaded.get("manifest") if isinstance(manifest_loaded, Mapping) else None
    if normalized_document_id and not isinstance(manifest, dict):
        blockers.append("document_manifest_missing")
    if isinstance(manifest, dict):
        manifest_fingerprint = manifest.get("pipeline_fingerprint")
        readiness_status = str(((manifest.get("backend_readiness") or {}).get("status")) or "")
        lifecycle_status = str(manifest.get("lifecycle_status") or "")
        if lifecycle_status in {"blocked", "corrupt"} or readiness_status in {"blocked", "corrupt"}:
            blockers.append("document_manifest_blocked")
        document_status = "current"
    quarantine_path = base / "quarantine" / f"{analysis_backend._safe_id(normalized_document_id or '')}.json"
    if normalized_document_id and quarantine_path.exists():
        blockers.append("document_quarantined")
    if isinstance(manifest, dict) and normalized_revision is not None:
        current_state = calculate_document_revision_state(normalized_document_id or "", existing_manifest=manifest, root=base)
        current_revision = _normalize_revision(current_state.get("source_revision"))
        if current_revision != normalized_revision:
            blockers.append("source_revision_no_longer_current")
            document_status = "stale"
            revision_lock_status = "stale"
        else:
            revision_lock_status = "valid"
    return {
        "document_status": document_status,
        "revision_lock_status": revision_lock_status,
        "document_manifest_fingerprint": manifest_fingerprint,
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
    }


def _select_rules(
    base: Path,
    document_id: str,
    source_revision: int,
    rule_ids: list[str] | None,
    include_document_certified_rules: bool,
) -> tuple[list[dict[str, Any]], dict[str, int | bool]]:
    explicit = [str(item).strip() for item in (rule_ids or []) if str(item).strip()]
    explicit_ids = sorted(set(explicit))
    explicit_scope_violation = False
    if explicit_ids:
        selected_ids = explicit_ids
    elif include_document_certified_rules:
        listed = list_canonical_rules(status="active", limit=HARD_MAX_RULES * 8, root=base)
        selected_ids = sorted(str(item.get("rule_id") or "") for item in listed.get("items", []) if str(item.get("rule_id") or ""))
    else:
        selected_ids = []
    items = []
    counts = {
        "foreign_document_rule_count": 0,
        "foreign_revision_rule_count": 0,
        "provenance_missing_rule_count": 0,
        "provenance_conflict_rule_count": 0,
        "explicit_scope_violation": False,
    }
    for rule_id in selected_ids:
        item = _classify_rule(base, document_id, source_revision, rule_id, explicit_ids=bool(explicit_ids))
        classification = str(item.get("classification") or "")
        if not explicit_ids and classification in {"foreign_document", "foreign_revision", "provenance_missing", "provenance_conflict", "rule_missing", "uncertified", "stale_rule"}:
            continue
        if classification == "foreign_document":
            counts["foreign_document_rule_count"] += 1
            explicit_scope_violation = explicit_scope_violation or bool(explicit_ids)
        elif classification == "foreign_revision":
            counts["foreign_revision_rule_count"] += 1
            explicit_scope_violation = explicit_scope_violation or bool(explicit_ids)
        elif classification == "provenance_missing":
            counts["provenance_missing_rule_count"] += 1
        elif classification == "provenance_conflict":
            counts["provenance_conflict_rule_count"] += 1
        items.append(item)
    items.sort(key=lambda item: (str(item.get("rule_family") or ""), str(item.get("target") or ""), str(item.get("rule_id") or "")))
    counts["explicit_scope_violation"] = explicit_scope_violation
    return items, counts


def _classify_rule(base: Path, document_id: str, source_revision: int, rule_id: str, *, explicit_ids: bool) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    loaded = load_canonical_rule(rule_id, require_active=False, root=base)
    rule = dict(loaded.get("rule") or {}) if loaded.get("status") in {"loaded", "blocked"} else None
    classification = "eligible"
    certification = analysis_backend._load_certification_receipt_for_rule(base, rule_id) if isinstance(rule, dict) else None
    if not isinstance(rule, dict):
        classification = "rule_missing"
        blockers.append("canonical_rule_not_found")
    elif str(rule.get("status") or "") != "active":
        classification = "stale_rule"
        blockers.append("inactive_rule_not_selected")
    if not isinstance(certification, dict):
        classification = "uncertified" if classification == "eligible" else classification
        blockers.append("rule_certification_missing")
    elif str(certification.get("certification_status") or "") != "completed":
        classification = "uncertified" if classification == "eligible" else classification
        blockers.append("rule_not_certified")
    elif isinstance(rule, dict) and str(certification.get("rule_hash") or "") != analysis_backend._hash_payload(rule):
        classification = "stale_rule" if classification == "eligible" else classification
        blockers.append("rule_certification_hash_mismatch")
    provenance_trace = _resolve_rule_provenance(rule, certification)
    if provenance_trace["provenance_status"] == "missing":
        classification = "provenance_missing"
        blockers.append("rule_document_provenance_missing")
    elif provenance_trace["provenance_status"] == "conflict":
        classification = "provenance_conflict"
        blockers.append("rule_document_provenance_conflict")
    elif provenance_trace["document_id"] != document_id:
        classification = "foreign_document"
        blockers.append("rule_foreign_document")
    elif provenance_trace["source_revision"] != source_revision:
        classification = "foreign_revision"
        blockers.append("rule_foreign_revision")
    elif explicit_ids and blockers:
        classification = "blocked"
    return {
        "rule_id": rule_id,
        "rule_family": (rule or {}).get("rule_type"),
        "target": (rule or {}).get("target"),
        "classification": classification,
        "document_id": provenance_trace.get("document_id"),
        "source_revision": provenance_trace.get("source_revision"),
        "provenance_status": provenance_trace["provenance_status"],
        "provenance_trace": provenance_trace,
        "provenance_fingerprint": provenance_trace["provenance_fingerprint"],
        "rule_fingerprint": analysis_backend._hash_payload(rule) if isinstance(rule, dict) else None,
        "certification_receipt_id": (certification or {}).get("certification_receipt_id"),
        "warnings": warnings,
        "blockers": _dedupe(blockers),
    }


def _resolve_rule_provenance(rule: Mapping[str, Any] | None, certification: Mapping[str, Any] | None) -> dict[str, Any]:
    document_id = _non_empty_text((rule or {}).get("document_id"))
    source_revision = _normalize_revision((rule or {}).get("source_revision"))
    proposal_id = _non_empty_text((rule or {}).get("source_proposal_id"))
    promotion_receipt_id = _non_empty_text((rule or {}).get("source_promotion_receipt_id"))
    activation_receipt_id = _non_empty_text((rule or {}).get("source_rule_activation_review_id"))
    certification_receipt_id = _non_empty_text((certification or {}).get("certification_receipt_id"))
    status = "valid"
    if not document_id or source_revision is None:
        status = "missing"
    payload = {
        "rule_id": (rule or {}).get("rule_id"),
        "document_id": document_id,
        "source_revision": source_revision,
        "citation_ids": [],
        "proposal_id": proposal_id,
        "proposal_promotion_receipt_id": promotion_receipt_id,
        "activation_receipt_id": activation_receipt_id,
        "certification_receipt_id": certification_receipt_id,
        "provenance_status": status,
    }
    payload["provenance_fingerprint"] = analysis_backend._hash_payload(payload)
    return payload


def _plan_id(plan_fingerprint: str) -> str:
    return f"rule_batch_plan_{plan_fingerprint[7:23]}"


def _run_id(plan_id: str) -> str:
    return f"rule_batch_run_{analysis_backend._safe_id(plan_id)[-16:]}"


def _receipt_id(run_id: str) -> str:
    return f"rule_batch_receipt_{analysis_backend._safe_id(run_id)[-16:]}"


def _plan_path(base: Path, batch_plan_id: str) -> Path:
    return base / RUN_DIR / f"{analysis_backend._safe_id(batch_plan_id)}.json"


def _run_path(base: Path, batch_run_id: str) -> Path:
    return base / RUN_DIR / f"{analysis_backend._safe_id(batch_run_id)}.json"


def _receipt_path(base: Path, batch_receipt_id: str) -> Path:
    return base / RECEIPT_DIR / f"{analysis_backend._safe_id(batch_receipt_id)}.json"


def _load_plan_record(base: Path, batch_plan_id: str) -> dict[str, Any] | None:
    payload = analysis_backend._read_json(_plan_path(base, batch_plan_id))
    return deepcopy(dict(payload)) if isinstance(payload, dict) else None


def _load_run_by_id(base: Path, batch_run_id: str) -> dict[str, Any] | None:
    payload = analysis_backend._read_json(_run_path(base, batch_run_id))
    return deepcopy(dict(payload)) if isinstance(payload, dict) and str(payload.get("schema_version") or "") == RUN_SCHEMA else None


def _load_run_for_plan(base: Path, batch_plan_id: str) -> dict[str, Any] | None:
    return _load_run_by_id(base, _run_id(batch_plan_id))


def _load_receipt_by_id(base: Path, batch_receipt_id: str | None) -> dict[str, Any] | None:
    if not batch_receipt_id:
        return None
    payload = analysis_backend._read_json(_receipt_path(base, batch_receipt_id))
    return deepcopy(dict(payload)) if isinstance(payload, dict) else None


def _load_receipt_for_run(base: Path, batch_run_id: str) -> dict[str, Any] | None:
    return _load_receipt_by_id(base, _receipt_id(batch_run_id))


def _new_run_from_plan(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": RUN_SCHEMA,
        "batch_run_id": _run_id(str(plan.get("batch_plan_id") or "")),
        "batch_plan_id": plan.get("batch_plan_id"),
        "plan_fingerprint": plan.get("plan_fingerprint"),
        "document_id": plan.get("document_id"),
        "source_revision": plan.get("source_revision"),
        "document_manifest_fingerprint": plan.get("document_manifest_fingerprint"),
        "dataset_id": plan.get("dataset_id"),
        "dataset_fingerprint": plan.get("dataset_fingerprint"),
        "policy_id": plan.get("policy_id"),
        "policy_fingerprint": plan.get("policy_fingerprint"),
        "status": "planned",
        "next_item_index": 0,
        "processed_count": 0,
        "successful_count": 0,
        "warning_count": 0,
        "failed_count": 0,
        "blocked_count": 0,
        "planned_rule_count": len(plan.get("items", [])),
        "eligible_rule_count": plan.get("eligible_rule_count"),
        "rules_omitted_by_limit": plan.get("rules_omitted_by_limit", 0),
        "foreign_document_rule_count": plan.get("foreign_document_rule_count", 0),
        "foreign_revision_rule_count": plan.get("foreign_revision_rule_count", 0),
        "items": deepcopy(list(plan.get("items", []))),
        "created_at_utc": analysis_backend._now(),
        "updated_at_utc": analysis_backend._now(),
        "warnings": [],
        "blockers": [],
    }


def _refresh_run_counts(run: dict[str, Any]) -> None:
    items = list(run.get("items", []))
    stale_skip_counts = _stale_skip_counts(items)
    run["processed_count"] = sum(1 for item in items if str(item.get("status") or "") != "pending")
    run["successful_count"] = sum(1 for item in items if str(item.get("status") or "") in {"recommendation_completed", "completed_with_warnings"})
    run["warning_count"] = sum(1 for item in items if str(item.get("status") or "") == "completed_with_warnings")
    run["failed_count"] = sum(1 for item in items if str(item.get("status") or "") == "failed")
    run["blocked_count"] = sum(1 for item in items if str(item.get("status") or "") in {"blocked", "skipped_stale"})
    run["stale_analysis_skip_count"] = stale_skip_counts.get("analysis_stale_before_recommendation", 0)
    run["other_stale_skip_count"] = stale_skip_counts.get("other_stale", 0)


def _persist_run(base: Path, run: Mapping[str, Any]) -> bool:
    path = _run_path(base, str(run.get("batch_run_id") or ""))
    before_run = analysis_backend._read_json(path)
    before_index = analysis_backend._read_json(base / "indexes" / RUN_INDEX)
    try:
        analysis_backend._atomic_write_json(path, run)
        _update_run_index(base)
        return True
    except Exception:
        analysis_backend._restore_json(path, before_run)
        analysis_backend._restore_json(base / "indexes" / RUN_INDEX, before_index)
        return False


def _process_batch_item(base: Path, plan: Mapping[str, Any], item: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(item))
    rule_id = str(item.get("rule_id") or "")
    loaded = load_canonical_rule(rule_id, require_active=False, root=base)
    rule = dict(loaded.get("rule") or {}) if loaded.get("status") in {"loaded", "blocked"} else None
    if not isinstance(rule, dict):
        result["status"] = "failed"
        result["failure_stage"] = "rule_load"
        result["failure_classification"] = "canonical_rule_not_found"
        result["blockers"] = ["canonical_rule_not_found"]
        return result
    provenance = _resolve_rule_provenance(rule, analysis_backend._load_certification_receipt_for_rule(base, rule_id))
    if provenance["document_id"] != plan.get("document_id") or provenance["source_revision"] != plan.get("source_revision"):
        result["status"] = "skipped_stale"
        result["failure_stage"] = "rule_load"
        result["failure_classification"] = "document_revision_changed"
        result["blockers"] = ["document_revision_changed"]
        return result
    if analysis_backend._hash_payload(rule) != str(item.get("rule_fingerprint") or ""):
        result["status"] = "skipped_stale"
        result["failure_stage"] = "rule_load"
        result["failure_classification"] = "rule_fingerprint_changed"
        result["blockers"] = ["rule_batch_rule_fingerprint_changed"]
        return result
    if provenance["provenance_fingerprint"] != str(item.get("provenance_fingerprint") or ""):
        result["status"] = "skipped_stale"
        result["failure_stage"] = "rule_load"
        result["failure_classification"] = "rule_provenance_changed"
        result["blockers"] = ["rule_batch_provenance_fingerprint_changed"]
        return result
    certification = analysis_backend._load_certification_receipt_for_rule(base, rule_id)
    if not isinstance(certification, dict) or str(certification.get("certification_receipt_id") or "") != str(item.get("certification_receipt_id") or ""):
        result["status"] = "skipped_stale"
        result["failure_stage"] = "rule_certification"
        result["failure_classification"] = "rule_certification_changed"
        result["blockers"] = ["rule_batch_rule_certification_changed"]
        return result
    analysis_result = analysis_backend.run_rule_effectiveness_backtest(
        rule_id,
        str(plan.get("dataset_id") or ""),
        max_records=int(plan.get("max_records_per_rule", DEFAULT_MAX_RECORDS_PER_RULE) or DEFAULT_MAX_RECORDS_PER_RULE),
        root=base,
    )
    analysis_status = str(analysis_result.get("status") or "")
    result["analysis_status"] = analysis_status
    if analysis_status in {"blocked", "failed"}:
        result["status"] = "failed"
        result["failure_stage"] = "effectiveness_analysis"
        result["failure_classification"] = str((analysis_result.get("blockers") or ["effectiveness_analysis_failed"])[0])
        result["blockers"] = ["effectiveness_analysis_failed"]
        result["warnings"] = list(analysis_result.get("warnings", []))
        return result
    analysis_id = str(analysis_result.get("analysis_id") or "")
    loaded_analysis = analysis_backend.load_rule_effectiveness_analysis(analysis_id, root=base)
    analysis_payload = dict(loaded_analysis.get("analysis") or {}) if loaded_analysis.get("status") == "loaded" else {}
    if str(analysis_payload.get("rule_id") or "") != rule_id or str(analysis_payload.get("rule_fingerprint") or "") != str(item.get("rule_fingerprint") or "") or str(analysis_payload.get("dataset_fingerprint") or "") != str(plan.get("dataset_fingerprint") or ""):
        result["status"] = "failed"
        result["failure_stage"] = "effectiveness_analysis"
        result["failure_classification"] = "analysis_scope_mismatch"
        result["blockers"] = ["analysis_scope_mismatch"]
        return result
    analysis_workspace = analysis_backend.build_rule_effectiveness_workspace(
        rule_id,
        str(plan.get("dataset_id") or ""),
        root=base,
    )
    if analysis_workspace.get("analysis_id") == analysis_id and analysis_workspace.get("analysis_current") is False:
        result["status"] = "skipped_stale"
        result["failure_stage"] = "effectiveness_analysis"
        result["failure_classification"] = "analysis_stale_before_recommendation"
        result["blockers"] = ["effectiveness_analysis_stale"]
        result["warnings"] = _dedupe(list(result.get("warnings", [])) + list(analysis_workspace.get("warnings", [])))
        result["analysis_id"] = analysis_id
        result["analysis_receipt_id"] = analysis_result.get("effectiveness_receipt_id") or analysis_payload.get("effectiveness_receipt_id")
        return result
    result["analysis_id"] = analysis_id
    result["analysis_receipt_id"] = analysis_result.get("effectiveness_receipt_id") or analysis_payload.get("effectiveness_receipt_id")
    recommendation_result = recommendation_backend.generate_rule_effectiveness_recommendation(
        analysis_id,
        policy_id=str(plan.get("policy_id") or "default_v1"),
        root=base,
    )
    recommendation_status = str(recommendation_result.get("status") or "")
    result["recommendation_status"] = recommendation_status
    if recommendation_status in {"blocked", "failed"}:
        result["status"] = "failed"
        result["failure_stage"] = "effectiveness_recommendation"
        result["failure_classification"] = str((recommendation_result.get("blockers") or ["effectiveness_recommendation_failed"])[0])
        result["blockers"] = ["effectiveness_recommendation_failed"]
        result["warnings"] = list(recommendation_result.get("warnings", []))
        return result
    recommendation_id = str(recommendation_result.get("recommendation_id") or "")
    loaded_recommendation = recommendation_backend.load_rule_effectiveness_recommendation(recommendation_id, root=base) if recommendation_id else {"status": "not_found"}
    recommendation_payload = dict(loaded_recommendation.get("recommendation") or {}) if loaded_recommendation.get("status") == "loaded" else {}
    if str(recommendation_payload.get("analysis_id") or "") != analysis_id or str(recommendation_payload.get("rule_id") or "") != rule_id or str(recommendation_payload.get("rule_fingerprint") or "") != str(item.get("rule_fingerprint") or "") or str(recommendation_payload.get("policy_fingerprint") or "") != str(plan.get("policy_fingerprint") or ""):
        result["status"] = "failed"
        result["failure_stage"] = "effectiveness_recommendation"
        result["failure_classification"] = "recommendation_scope_mismatch"
        result["blockers"] = ["recommendation_scope_mismatch"]
        return result
    result["recommendation_id"] = recommendation_payload.get("recommendation_id") or recommendation_id
    result["recommendation_type"] = recommendation_payload.get("recommendation_type") or recommendation_result.get("recommendation_type")
    result["status"] = "completed_with_warnings" if analysis_status == "completed_with_warnings" else "recommendation_completed"
    result["warnings"] = _dedupe(list(result.get("warnings", [])) + list(analysis_result.get("warnings", [])) + list(recommendation_result.get("warnings", [])))
    result["blockers"] = []
    return result


def _plan_stale_blockers(base: Path, plan: Mapping[str, Any]) -> list[str]:
    blockers = []
    if not _is_scoped_plan(plan):
        return ["legacy_unscoped_batch_plan"]
    scope = _validate_document_scope(base, str(plan.get("document_id") or ""), plan.get("source_revision"))
    blockers.extend(scope["blockers"])
    if str(scope.get("document_manifest_fingerprint") or "") != str(plan.get("document_manifest_fingerprint") or ""):
        blockers.append("document_manifest_fingerprint_changed")
    validation = _validate_batch_inputs(base, str(plan.get("dataset_id") or ""), str(plan.get("policy_id") or "default_v1"))
    dataset = validation["dataset"]
    policy = validation["policy"]
    if not isinstance(dataset, dict) or analysis_backend._dataset_fingerprint(dataset) != str(plan.get("dataset_fingerprint") or ""):
        blockers.append("rule_batch_dataset_fingerprint_changed")
    if not isinstance(policy, dict) or recommendation_backend._policy_fingerprint(policy) != str(plan.get("policy_fingerprint") or ""):
        blockers.append("rule_batch_policy_fingerprint_changed")
    for item in plan.get("items", []):
        loaded = load_canonical_rule(str(item.get("rule_id") or ""), require_active=False, root=base)
        rule = dict(loaded.get("rule") or {}) if loaded.get("status") in {"loaded", "blocked"} else None
        if not isinstance(rule, dict) or analysis_backend._hash_payload(rule) != str(item.get("rule_fingerprint") or ""):
            blockers.append("rule_batch_rule_fingerprint_changed")
            break
        certification = analysis_backend._load_certification_receipt_for_rule(base, str(item.get("rule_id") or ""))
        if not isinstance(certification, dict) or str(certification.get("certification_receipt_id") or "") != str(item.get("certification_receipt_id") or ""):
            blockers.append("rule_batch_rule_certification_changed")
            break
        provenance = _resolve_rule_provenance(rule, certification)
        if provenance["document_id"] != plan.get("document_id"):
            blockers.append("rule_batch_foreign_document_detected")
            break
        if provenance["source_revision"] != plan.get("source_revision"):
            blockers.append("source_revision_no_longer_current")
            break
        if provenance["provenance_fingerprint"] != str(item.get("provenance_fingerprint") or ""):
            blockers.append("rule_batch_provenance_fingerprint_changed")
            break
    return _dedupe(blockers)


def _run_stale_blockers(base: Path, run: Mapping[str, Any], plan: Mapping[str, Any]) -> list[str]:
    blockers = _plan_stale_blockers(base, plan)
    if blockers:
        return blockers
    for item in run.get("items", []):
        status = str(item.get("status") or "")
        if status in {"recommendation_completed", "completed_with_warnings"}:
            recommendation_id = str(item.get("recommendation_id") or "")
            loaded = recommendation_backend.load_rule_effectiveness_recommendation(recommendation_id, root=base)
            if loaded.get("status") != "loaded" or loaded.get("stale"):
                blockers.append("rule_batch_completed_recommendation_stale")
                break
    return _dedupe(blockers)


def _create_receipt_if_needed(base: Path, run: Mapping[str, Any], plan: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(plan, Mapping):
        return None
    if str(run.get("status") or "") not in {"completed", "completed_with_failures", "cancelled"}:
        return None
    existing = _load_receipt_for_run(base, str(run.get("batch_run_id") or ""))
    if isinstance(existing, dict):
        return existing
    items = list(run.get("items", []))
    if _mixed_source_items(items, run.get("document_id"), run.get("source_revision")):
        return None
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "batch_receipt_id": _receipt_id(str(run.get("batch_run_id") or "")),
        "batch_run_id": run.get("batch_run_id"),
        "batch_plan_id": run.get("batch_plan_id"),
        "document_id": run.get("document_id"),
        "source_revision": run.get("source_revision"),
        "document_manifest_fingerprint": run.get("document_manifest_fingerprint"),
        "plan_fingerprint": run.get("plan_fingerprint"),
        "dataset_id": run.get("dataset_id"),
        "dataset_fingerprint": run.get("dataset_fingerprint"),
        "policy_id": run.get("policy_id"),
        "policy_fingerprint": run.get("policy_fingerprint"),
        "planned_rule_count": len(items),
        "processed_rule_count": run.get("processed_count"),
        "foreign_document_rule_count": run.get("foreign_document_rule_count", 0),
        "foreign_revision_rule_count": run.get("foreign_revision_rule_count", 0),
        "final_status": run.get("status"),
        "successful_rule_count": run.get("successful_count"),
        "failed_rule_count": int(run.get("failed_count", 0) or 0) + int(run.get("blocked_count", 0) or 0),
        "recommendation_counts": _recommendation_counts(items),
        "item_result_fingerprints": {
            str(item.get("rule_id") or ""): analysis_backend._hash_payload(
                {
                    "document_id": item.get("document_id"),
                    "source_revision": item.get("source_revision"),
                    "provenance_fingerprint": item.get("provenance_fingerprint"),
                    "status": item.get("status"),
                    "analysis_id": item.get("analysis_id"),
                    "recommendation_id": item.get("recommendation_id"),
                    "recommendation_type": item.get("recommendation_type"),
                    "failure_stage": item.get("failure_stage"),
                    "failure_classification": item.get("failure_classification"),
                }
            )
            for item in items
        },
        "created_at_utc": analysis_backend._now(),
        "warnings": list(run.get("warnings", [])),
    }
    path = _receipt_path(base, str(receipt["batch_receipt_id"]))
    before_receipt = analysis_backend._read_json(path)
    before_index = analysis_backend._read_json(base / "indexes" / RECEIPT_INDEX)
    try:
        analysis_backend._atomic_write_json(path, receipt)
        _update_receipt_index(base)
        return receipt
    except Exception:
        analysis_backend._restore_json(path, before_receipt)
        analysis_backend._restore_json(base / "indexes" / RECEIPT_INDEX, before_index)
        return None


def _recommendation_counts(items: list[dict[str, Any]] | list[Any]) -> dict[str, int]:
    counts = {
        "continue": 0,
        "monitor": 0,
        "rollback_candidate": 0,
        "supersession_review_candidate": 0,
        "insufficient_evidence": 0,
        "review_data_quality": 0,
    }
    for item in items:
        recommendation_type = str((item or {}).get("recommendation_type") or "")
        if recommendation_type in counts:
            counts[recommendation_type] += 1
    return counts


def _stale_skip_counts(items: list[dict[str, Any]] | list[Any]) -> dict[str, int]:
    counts = {
        "analysis_stale_before_recommendation": 0,
        "other_stale": 0,
    }
    for item in items:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("status") or "") != "skipped_stale":
            continue
        failure_classification = str(item.get("failure_classification") or "")
        if failure_classification == "analysis_stale_before_recommendation":
            counts["analysis_stale_before_recommendation"] += 1
        else:
            counts["other_stale"] += 1
    return counts


def _stale_skip_reason_counts(items: list[dict[str, Any]] | list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("status") or "") != "skipped_stale":
            continue
        failure_classification = str(item.get("failure_classification") or "")
        if not failure_classification:
            failure_classification = "unknown_stale_reason"
        counts[failure_classification] = counts.get(failure_classification, 0) + 1
    return counts


def _load_runs(base: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted((base / RUN_DIR).glob("*.json")):
        payload = analysis_backend._read_json(path)
        if isinstance(payload, dict) and str(payload.get("schema_version") or "") == RUN_SCHEMA:
            items.append(deepcopy(dict(payload)))
    return items


def _load_receipts(base: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted((base / RECEIPT_DIR).glob("*.json")):
        payload = analysis_backend._read_json(path)
        if isinstance(payload, dict):
            items.append(deepcopy(dict(payload)))
    return items


def _update_run_index(base: Path) -> None:
    items = []
    for path in sorted((base / RUN_DIR).glob("*.json")):
        payload = analysis_backend._read_json(path)
        if not isinstance(payload, dict):
            continue
        items.append(
            {
                "record_id": payload.get("batch_run_id") or payload.get("batch_plan_id"),
                "record_type": "run" if payload.get("schema_version") == RUN_SCHEMA else "plan" if payload.get("schema_version") in {PLAN_SCHEMA, LEGACY_PLAN_SCHEMA} else "unknown",
                "batch_plan_id": payload.get("batch_plan_id"),
                "batch_run_id": payload.get("batch_run_id"),
                "document_id": payload.get("document_id"),
                "source_revision": payload.get("source_revision"),
                "status": payload.get("status"),
                "dataset_id": payload.get("dataset_id"),
                "policy_id": payload.get("policy_id"),
                "updated_at_utc": payload.get("updated_at_utc"),
            }
        )
    analysis_backend._atomic_write_json(base / "indexes" / RUN_INDEX, {"schema_version": "rule_batch_run_index_v1", "items": items, "updated_at_utc": analysis_backend._now()})


def _update_receipt_index(base: Path) -> None:
    items = [
        {
            "batch_receipt_id": item.get("batch_receipt_id"),
            "batch_run_id": item.get("batch_run_id"),
            "batch_plan_id": item.get("batch_plan_id"),
            "document_id": item.get("document_id"),
            "source_revision": item.get("source_revision"),
            "final_status": item.get("final_status"),
            "dataset_id": item.get("dataset_id"),
            "policy_id": item.get("policy_id"),
            "created_at_utc": item.get("created_at_utc"),
        }
        for item in _load_receipts(base)
    ]
    analysis_backend._atomic_write_json(base / "indexes" / RECEIPT_INDEX, {"schema_version": "rule_batch_receipt_index_v1", "items": items, "updated_at_utc": analysis_backend._now()})


def _normalize_positive_int(value: Any, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return max(1, value)


def _normalize_revision(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        normalized = int(value.strip())
        return normalized if normalized > 0 else None
    return None


def _non_empty_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _mixed_source_items(items: list[Any], document_id: Any, source_revision: Any) -> bool:
    expected_document = str(document_id or "")
    expected_revision = _normalize_revision(source_revision)
    for item in items:
        if str((item or {}).get("document_id") or "") != expected_document:
            return True
        if _normalize_revision((item or {}).get("source_revision")) != expected_revision:
            return True
    return False


def _is_scoped_plan(plan: Mapping[str, Any]) -> bool:
    return bool(_non_empty_text(plan.get("document_id"))) and _normalize_revision(plan.get("source_revision")) is not None and bool(_non_empty_text(plan.get("document_manifest_fingerprint")))


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in values if str(item)))


__all__ = [
    "build_rule_batch_workspace",
    "build_rule_batch_plan",
    "run_rule_batch_analysis",
    "load_rule_batch_run",
    "cancel_rule_batch_run",
    "get_rule_batch_health",
    "format_rule_batch_report",
    "get_rule_batch_summary",
]
