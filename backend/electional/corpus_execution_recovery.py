"""Crash-safe corpus execution, recovery, and index repair helpers."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Mapping

from .document_preflight import can_extract_after_preflight, get_document_preflight_summary, run_document_preflight
from .document_structure import build_document_structure_map, get_document_structure_summary
from .evidence_binder import build_evidence_binder
from .source_document_reader import build_page_diagnostics, get_page_diagnostic_summary
from .source_documents import SOURCE_DOCUMENT_ROOT, STATUS_EXTRACTED, extract_pdf_text, get_extracted_text, list_source_documents, load_source_document
from .source_knowledge import chunk_extracted_text, ensure_source_knowledge_dirs, list_source_proposals, load_chunks
from .source_reliability_manager import (
    detect_duplicate_source_identity,
    list_evidence_binders_using_source,
    recalculate_source_reliability,
    refresh_evidence_binders_for_source,
)

EXECUTION_CONFIG_DEFAULTS = {
    "default_dry_run": True,
    "default_limit": 25,
    "maximum_limit": 100,
    "maximum_retries": 2,
    "stale_lock_seconds": 600,
    "stop_on_critical_failure": False,
    "continue_on_item_failure": True,
    "require_backup_before_repair": True,
    "verify_backup_hashes": True,
    "verify_rebuilt_index": True,
}
EXECUTION_SCHEMA_VERSION = "corpus_execution_state_v1"
RECEIPT_SCHEMA_VERSION = "corpus_execution_receipt_v1"
CHECKPOINT_SCHEMA_VERSION = "corpus_execution_checkpoint_v1"
REPAIR_PLAN_SCHEMA_VERSION = "corpus_repair_plan_v1"
REPAIR_BACKUP_SCHEMA_VERSION = "corpus_repair_backup_v1"
QUARANTINE_SCHEMA_VERSION = "corpus_quarantine_record_v1"
ACTION_SCHEMA_VERSION = "source_corpus_batch_v1"
EXECUTION_DIRS = (
    "corpus_execution",
    "corpus_execution_receipts",
    "corpus_execution_locks",
    "corpus_checkpoints",
    "corpus_execution_history",
    "corpus_repairs",
    "corpus_repair_backups",
    "corpus_repair_staging",
    "corpus_quarantine",
    "corpus_audits",
)
EXECUTION_INDEX_FILES = (
    "corpus_execution_index.json",
    "corpus_receipt_index.json",
    "corpus_lock_index.json",
    "corpus_checkpoint_index.json",
    "corpus_repair_index.json",
    "corpus_repair_backup_index.json",
    "corpus_quarantine_index.json",
)
FAILURE_CLASSIFICATIONS = {
    "missing_step",
    "dependency_missing",
    "processing_failure",
    "blocked",
    "unsupported",
    "corrupt_record",
    "interrupted",
    "cancelled",
    "already_completed",
    "skipped_by_policy",
    "stale_execution",
    "rollback_required",
    "unknown",
}
FINAL_RECEIPT_STATUSES = {
    "completed",
    "completed_with_warnings",
    "failed",
    "blocked",
    "unsupported",
    "interrupted",
    "cancelled",
    "skipped",
    "already_completed",
}
SUCCESS_RECEIPT_STATUSES = {"completed", "completed_with_warnings", "already_completed"}
ALLOWED_BATCH_ACTIONS = {
    "run_preflight",
    "extract_text",
    "chunk_text",
    "build_page_diagnostics",
    "build_structure_map",
    "recalculate_reliability",
    "refresh_evidence_binders",
    "detect_duplicates",
    "detect_missing_steps",
    "generate_corpus_report",
    "repair_index",
}


def ensure_corpus_execution_dirs(root: Path | str = SOURCE_DOCUMENT_ROOT) -> Path:
    base = ensure_source_knowledge_dirs(root)
    for folder in EXECUTION_DIRS:
        (base / folder).mkdir(parents=True, exist_ok=True)
    indexes = base / "indexes"
    indexes.mkdir(parents=True, exist_ok=True)
    for name in EXECUTION_INDEX_FILES:
        path = indexes / name
        if not path.exists():
            _atomic_write_json(path, {"entries": [], "updated_at_utc": _now()})
    return base


def get_corpus_execution_config() -> dict[str, object]:
    return dict(EXECUTION_CONFIG_DEFAULTS)


def validate_corpus_execution_config(config: dict) -> dict[str, object]:
    merged = dict(EXECUTION_CONFIG_DEFAULTS)
    merged.update({key: value for key, value in dict(config or {}).items() if value is not None})
    if merged["default_dry_run"] is not True:
        raise ValueError("default_dry_run must remain true.")
    if int(merged["default_limit"]) <= 0:
        raise ValueError("default_limit must be positive.")
    if int(merged["maximum_limit"]) < int(merged["default_limit"]):
        raise ValueError("maximum_limit must be at least default_limit.")
    if int(merged["maximum_limit"]) > 100:
        raise ValueError("maximum_limit exceeds safe bound.")
    if int(merged["maximum_retries"]) < 0:
        raise ValueError("maximum_retries must be non-negative.")
    if int(merged["stale_lock_seconds"]) < 60:
        raise ValueError("stale_lock_seconds is too small.")
    if merged["require_backup_before_repair"] is not True:
        raise ValueError("require_backup_before_repair must remain true.")
    if merged["verify_backup_hashes"] is not True:
        raise ValueError("verify_backup_hashes must remain true.")
    if merged["verify_rebuilt_index"] is not True:
        raise ValueError("verify_rebuilt_index must remain true.")
    return merged


def acquire_corpus_batch_lock(batch_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_corpus_execution_dirs(root)
    existing = get_corpus_batch_lock(batch_id, root=base)
    if existing and existing.get("status") == "active":
        stale = detect_stale_corpus_batch_lock(batch_id, root=base)
        if stale.get("stale"):
            raise RuntimeError("stale_lock")
        raise RuntimeError("active_lock")
    now = _now()
    lock = {
        "lock_id": f"lock_{_safe_id(batch_id)}_{_timestamp_token()}",
        "batch_id": batch_id,
        "acquired_at_utc": now,
        "heartbeat_at_utc": now,
        "status": "active",
        "owner_label": "local_process",
        "warnings": [],
    }
    _atomic_write_json(_lock_path(base, batch_id), lock)
    _update_execution_index(base, "corpus_lock_index.json", _list_lock_index_entries(base))
    _append_history_event(base, "lock_acquired", {"batch_id": batch_id, "lock_id": lock["lock_id"]})
    return lock


def release_corpus_batch_lock(batch_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_corpus_execution_dirs(root)
    lock = get_corpus_batch_lock(batch_id, root=base)
    if not lock:
        return {"batch_id": batch_id, "status": "not_found", "warnings": ["no_lock"]}
    lock["heartbeat_at_utc"] = _now()
    lock["released_at_utc"] = _now()
    lock["status"] = "released"
    _atomic_write_json(_lock_path(base, batch_id), lock)
    _update_execution_index(base, "corpus_lock_index.json", _list_lock_index_entries(base))
    _append_history_event(base, "lock_released", {"batch_id": batch_id, "lock_id": lock.get("lock_id")})
    return lock


def get_corpus_batch_lock(batch_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object] | None:
    path = _lock_path(ensure_corpus_execution_dirs(root), batch_id)
    return _read_json(path, default=None)


def detect_stale_corpus_batch_lock(batch_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_corpus_execution_dirs(root)
    config = validate_corpus_execution_config(get_corpus_execution_config())
    lock = get_corpus_batch_lock(batch_id, root=base)
    if not lock or lock.get("status") != "active":
        return {"batch_id": batch_id, "stale": False, "status": "no_active_lock", "warnings": []}
    heartbeat = _parse_utc(lock.get("heartbeat_at_utc") or lock.get("acquired_at_utc"))
    stale = heartbeat <= datetime.now(UTC) - timedelta(seconds=int(config["stale_lock_seconds"]))
    warnings = ["stale_lock"] if stale else []
    return {"batch_id": batch_id, "stale": stale, "status": lock.get("status"), "warnings": warnings, "lock": lock}


def clear_stale_corpus_batch_lock(batch_id: str, explicit: bool = False, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_corpus_execution_dirs(root)
    stale = detect_stale_corpus_batch_lock(batch_id, root=base)
    if not stale.get("stale"):
        return {"batch_id": batch_id, "status": "not_stale", "warnings": []}
    if not explicit:
        return {"batch_id": batch_id, "status": "blocked", "warnings": ["explicit_action_required", "stale_lock"]}
    lock = stale.get("lock") or {}
    lock["status"] = "cleared_stale"
    lock["cleared_at_utc"] = _now()
    _atomic_write_json(_lock_path(base, batch_id), lock)
    _update_execution_index(base, "corpus_lock_index.json", _list_lock_index_entries(base))
    _append_history_event(base, "stale_lock_cleared", {"batch_id": batch_id, "lock_id": lock.get("lock_id")})
    return {"batch_id": batch_id, "status": "cleared_stale", "warnings": ["stale_lock"]}


def classify_corpus_execution_failure(
    *,
    attempted: bool,
    exception: Exception | None = None,
    dependency_missing: bool = False,
    blocked: bool = False,
    unsupported: bool = False,
    cancelled: bool = False,
    stale: bool = False,
) -> str:
    if cancelled:
        return "cancelled"
    if stale:
        return "stale_execution"
    if unsupported:
        return "unsupported"
    if blocked and dependency_missing:
        return "dependency_missing"
    if blocked:
        return "blocked"
    if attempted and exception is not None:
        return "processing_failure"
    if not attempted:
        return "missing_step"
    return "unknown"


def validate_batch_action_dependencies(
    document_id: str,
    action: str,
    options: dict | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, object]:
    base = ensure_corpus_execution_dirs(root)
    record = load_source_document(document_id, root=base, missing_ok=True)
    missing: list[str] = []
    warnings: list[str] = []
    blockers: list[str] = []
    if action == "repair_index":
        repair_id = str((options or {}).get("repair_id") or "")
        plan = _load_repair_plan(repair_id, base) if repair_id else None
        backup_ok = False
        if plan:
            backup_id = str(plan.get("backup_id") or "")
            if backup_id:
                backup_ok = bool(verify_corpus_repair_backup(backup_id, root=base).get("verified"))
        allowed = bool(plan) and bool(backup_ok or (options or {}).get("dry_run", True))
        if not plan:
            missing.append("repair_plan")
        if not backup_ok and not (options or {}).get("dry_run", True):
            missing.append("verified_backup")
        if missing:
            blockers.append("dependency_missing")
        return {
            "document_id": document_id,
            "action": action,
            "allowed": allowed,
            "missing_dependencies": missing,
            "warnings": warnings,
            "blockers": blockers,
        }
    if record is None:
        missing.append("registered_source")
    if action == "run_preflight":
        pdf_path = Path(record.stored_pdf_path or record.source_path) if record else None
        if record is not None and (not pdf_path or not pdf_path.exists()):
            missing.append("readable_source_file")
    elif action == "extract_text":
        if record is not None:
            gate = can_extract_after_preflight(document_id, root=base)
            verdict = str(gate.get("verdict") or "")
            if verdict == "BLOCK":
                blockers.append("blocked")
            if not gate.get("allowed", True):
                missing.append("preflight_allowance")
        if not callable(getattr(extract_pdf_text, "__call__", None)):
            missing.append("extractor_available")
    elif action == "chunk_text":
        text = get_extracted_text(document_id, root=base)
        if not text.strip():
            missing.append("extracted_text")
        if record is None or record.extraction_status != STATUS_EXTRACTED:
            missing.append("usable_extracted_text_status")
    elif action == "build_page_diagnostics":
        if not get_extracted_text(document_id, root=base).strip():
            missing.append("extracted_page_markers_text")
    elif action == "build_structure_map":
        if not get_extracted_text(document_id, root=base).strip():
            missing.append("extracted_text")
    elif action == "recalculate_reliability":
        pass
    elif action == "refresh_evidence_binders":
        proposals = [item for item in list_source_proposals(root=base) if item.document_id == document_id]
        citations = _load_index_entries(base / "indexes" / "citation_index.json")
        binders = list_evidence_binders_using_source(document_id, root=base)
        if not proposals or not any(item.get("document_id") == document_id for item in citations) or not binders.get("binders_found"):
            missing.append("proposal_citation_binder_linkage")
    elif action == "detect_duplicates":
        reliability_path = base / "source_reliability" / f"{_safe_id(document_id)}_reliability.json"
        if not reliability_path.exists():
            missing.append("registered_source_metadata")
    elif action == "detect_missing_steps":
        pass
    elif action == "generate_corpus_report":
        pass
    else:
        blockers.append("unsupported")
    if missing and "blocked" not in blockers:
        blockers.append("dependency_missing")
    return {
        "document_id": document_id,
        "action": action,
        "allowed": not missing and "unsupported" not in blockers and "blocked" not in blockers,
        "missing_dependencies": list(dict.fromkeys(missing)),
        "warnings": warnings,
        "blockers": blockers,
    }


def build_execution_idempotency_key(
    document_id: str,
    action: str,
    input_state: dict,
    options: dict | None = None,
) -> str:
    payload = {
        "document_id": document_id,
        "action": action,
        "input_state": _json_safe(dict(input_state or {})),
        "options": _json_safe(dict(options or {})),
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "action_schema_version": ACTION_SCHEMA_VERSION,
    }
    return "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def find_completed_execution_by_idempotency_key(
    key: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, object] | None:
    for receipt in list_execution_receipts(root=root).get("receipts", []):
        if receipt.get("idempotency_key") == key and receipt.get("status") in SUCCESS_RECEIPT_STATUSES:
            return receipt
    return None


def create_started_execution_receipt(
    *,
    batch_id: str,
    document_id: str,
    action: str,
    attempt_number: int,
    idempotency_key: str,
    input_hashes: dict[str, object] | None = None,
    input_summary: dict[str, object] | None = None,
    output_summary: dict[str, object] | None = None,
    prior_receipt_id: str | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, object]:
    base = ensure_corpus_execution_dirs(root)
    receipt = {
        "receipt_id": f"receipt_{_safe_id(batch_id)}_{_safe_id(document_id)}_{_safe_id(action)}_{_timestamp_token()}",
        "batch_id": batch_id,
        "document_id": document_id,
        "action": action,
        "attempt_number": int(attempt_number),
        "idempotency_key": idempotency_key,
        "started_at_utc": _now(),
        "completed_at_utc": None,
        "status": "started",
        "classification": None,
        "input_hashes": dict(input_hashes or {}),
        "input_summary": dict(input_summary or {}),
        "output_hashes": {},
        "output_summary": dict(output_summary or {}),
        "prior_receipt_id": prior_receipt_id,
        "warnings": [],
        "blockers": [],
        "error_type": None,
        "error_message": None,
        "schema_version": RECEIPT_SCHEMA_VERSION,
    }
    _atomic_write_json(_receipt_path(base, receipt["receipt_id"]), receipt)
    _update_receipt_index(base)
    _append_history_event(base, "receipt_started", {"batch_id": batch_id, "receipt_id": receipt["receipt_id"], "document_id": document_id, "action": action})
    return receipt


def finalize_execution_receipt(
    receipt_id: str,
    *,
    status: str,
    classification: str,
    output_hashes: dict[str, object] | None = None,
    output_summary: dict[str, object] | None = None,
    warnings: list[str] | None = None,
    blockers: list[str] | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, object]:
    if status not in FINAL_RECEIPT_STATUSES:
        raise ValueError(f"Unsupported final receipt status: {status}")
    if classification not in FAILURE_CLASSIFICATIONS:
        raise ValueError(f"Unsupported receipt classification: {classification}")
    base = ensure_corpus_execution_dirs(root)
    receipt = load_execution_receipt(receipt_id, root=base)
    receipt["completed_at_utc"] = _now()
    receipt["status"] = status
    receipt["classification"] = classification
    receipt["output_hashes"] = dict(output_hashes or {})
    receipt["output_summary"] = dict(output_summary or {})
    receipt["warnings"] = list(dict.fromkeys([*receipt.get("warnings", []), *(warnings or [])]))
    receipt["blockers"] = list(dict.fromkeys([*receipt.get("blockers", []), *(blockers or [])]))
    receipt["error_type"] = error_type
    receipt["error_message"] = _sanitize_text(error_message) if error_message else None
    if status in {"completed", "completed_with_warnings"} and not receipt["output_summary"]:
        raise ValueError("Completed receipts require output summary.")
    _atomic_write_json(_receipt_path(base, receipt_id), receipt)
    _update_receipt_index(base)
    _append_history_event(base, "receipt_finalized", {"batch_id": receipt.get("batch_id"), "receipt_id": receipt_id, "status": status, "classification": classification})
    return receipt


def load_execution_receipt(receipt_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    path = _receipt_path(ensure_corpus_execution_dirs(root), receipt_id)
    data = _read_json(path, default=None)
    if data is None:
        raise FileNotFoundError(str(path))
    return data


def list_execution_receipts(
    *,
    batch_id: str | None = None,
    document_id: str | None = None,
    action: str | None = None,
    limit: int = 100,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, object]:
    base = ensure_corpus_execution_dirs(root)
    receipts: list[dict[str, object]] = []
    for path in sorted((base / "corpus_execution_receipts").glob("*.json"), reverse=True):
        data = _read_json(path, default=None)
        if not isinstance(data, dict):
            continue
        if batch_id is not None and data.get("batch_id") != batch_id:
            continue
        if document_id is not None and data.get("document_id") != document_id:
            continue
        if action is not None and data.get("action") != action:
            continue
        receipts.append(data)
    limited = receipts[: max(0, int(limit or 0))]
    return {"count": len(limited), "receipts": limited}


def execute_corpus_batch_plan(
    batch_id: str,
    dry_run: bool = True,
    limit: int = 25,
    resume: bool = False,
    retry_failures: bool = False,
    force: bool = False,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, object]:
    base = ensure_corpus_execution_dirs(root)
    config = validate_corpus_execution_config(get_corpus_execution_config())
    dry_run = bool(dry_run if dry_run is not None else config["default_dry_run"])
    limit = min(int(limit or config["default_limit"]), int(config["maximum_limit"]))
    plan = _load_batch_plan(batch_id, base)
    _validate_batch_schema(plan)
    registered = {record.document_id for record in list_source_documents(root=base)}
    invalid_docs = [doc for doc in plan.get("document_ids", []) if doc not in registered]
    if invalid_docs:
        raise ValueError("Batch plan contains unregistered documents.")
    state = _load_execution_state(batch_id, base)
    if state.get("status") == "cancelled" and not resume:
        return _build_batch_summary(batch_id, plan, base, dry_run=dry_run, warnings=["batch_cancelled"])
    lock = acquire_corpus_batch_lock(batch_id, root=base)
    try:
        snapshot = _write_execution_snapshot(base, batch_id, plan, dry_run=dry_run, resume=resume, retry_failures=retry_failures, force=force)
        _append_history_event(base, "execution_started", {"batch_id": batch_id, "snapshot_id": snapshot["execution_id"]})
        docs = list(plan.get("document_ids", []))[:limit]
        for document_id in docs:
            control = _load_execution_state(batch_id, base)
            if control.get("status") == "paused":
                break
            if control.get("status") == "cancelled":
                break
            action = str(plan.get("action"))
            attempts = _list_receipts_for_item(base, batch_id, document_id, action)
            last_receipt = attempts[-1] if attempts else None
            if resume and _is_successful_receipt(last_receipt):
                continue
            if last_receipt and last_receipt.get("status") == "interrupted" and not retry_failures:
                retry_failures = True
            if last_receipt and last_receipt.get("status") == "failed" and not retry_failures and not force:
                continue
            retry_state = _retry_budget_state(attempts, config)
            if not retry_state["retry_allowed"] and not force:
                receipt = create_started_execution_receipt(
                    batch_id=batch_id,
                    document_id=document_id,
                    action=action,
                    attempt_number=retry_state["attempt_number"],
                    idempotency_key=retry_state["idempotency_key_placeholder"],
                    input_summary={"dry_run": dry_run, "retry_budget": retry_state},
                    prior_receipt_id=last_receipt.get("receipt_id") if last_receipt else None,
                    root=base,
                )
                finalize_execution_receipt(
                    receipt["receipt_id"],
                    status="blocked",
                    classification="blocked",
                    output_summary={"retry_allowed": False, "attempted": False},
                    blockers=["retry_budget_exhausted"],
                    root=base,
                )
                _write_checkpoint_for_batch(batch_id, plan, base)
                _heartbeat_lock(base, batch_id)
                continue
            dependency = validate_batch_action_dependencies(document_id, action, {"dry_run": dry_run}, root=base)
            input_state = _build_input_state(document_id, action, dependency, base)
            idempotency_key = build_execution_idempotency_key(document_id, action, input_state, {"dry_run": dry_run})
            completed = find_completed_execution_by_idempotency_key(idempotency_key, root=base)
            receipt = create_started_execution_receipt(
                batch_id=batch_id,
                document_id=document_id,
                action=action,
                attempt_number=retry_state["attempt_number"],
                idempotency_key=idempotency_key,
                input_hashes=input_state.get("input_hashes"),
                input_summary=input_state.get("input_summary"),
                prior_receipt_id=completed.get("receipt_id") if (completed and force) else (last_receipt.get("receipt_id") if last_receipt else None),
                root=base,
            )
            if completed and not force:
                finalize_execution_receipt(
                    receipt["receipt_id"],
                    status="already_completed",
                    classification="already_completed",
                    output_summary={"prior_receipt_id": completed.get("receipt_id"), "attempted": False},
                    warnings=["idempotency_skip"],
                    root=base,
                )
                _write_checkpoint_for_batch(batch_id, plan, base)
                _heartbeat_lock(base, batch_id)
                continue
            if dependency.get("blockers"):
                classification = "dependency_missing" if "dependency_missing" in dependency.get("blockers", []) else "blocked"
                finalize_execution_receipt(
                    receipt["receipt_id"],
                    status="blocked",
                    classification=classification,
                    output_summary={"attempted": False, "missing_dependencies": dependency.get("missing_dependencies", [])},
                    blockers=list(dependency.get("blockers", [])),
                    root=base,
                )
                _write_checkpoint_for_batch(batch_id, plan, base)
                _heartbeat_lock(base, batch_id)
                continue
            if dry_run:
                finalize_execution_receipt(
                    receipt["receipt_id"],
                    status="skipped",
                    classification="skipped_by_policy",
                    output_summary={"attempted": False, "dry_run": True, "action": action},
                    warnings=["dry_run_only"],
                    root=base,
                )
                _write_checkpoint_for_batch(batch_id, plan, base)
                _heartbeat_lock(base, batch_id)
                continue
            try:
                result = _execute_action(action, document_id, base)
            except NotImplementedError as exc:
                finalize_execution_receipt(
                    receipt["receipt_id"],
                    status="unsupported",
                    classification="unsupported",
                    output_summary={"attempted": False, "action": action},
                    blockers=["unsupported"],
                    error_type=exc.__class__.__name__,
                    error_message=str(exc),
                    root=base,
                )
                _write_checkpoint_for_batch(batch_id, plan, base)
                _heartbeat_lock(base, batch_id)
                continue
            except Exception as exc:
                finalize_execution_receipt(
                    receipt["receipt_id"],
                    status="failed",
                    classification="processing_failure",
                    output_summary={"attempted": True, "action": action},
                    error_type=exc.__class__.__name__,
                    error_message=str(exc),
                    root=base,
                )
                _write_checkpoint_for_batch(batch_id, plan, base)
                _heartbeat_lock(base, batch_id)
                if not config["continue_on_item_failure"]:
                    break
                continue
            status = "completed_with_warnings" if result.get("warnings") else "completed"
            finalize_execution_receipt(
                receipt["receipt_id"],
                status=status,
                classification="unknown" if status == "completed_with_warnings" else "unknown",
                output_hashes=result.get("output_hashes", {}),
                output_summary=result.get("output_summary", {"attempted": True, "action": action}),
                warnings=result.get("warnings", []),
                root=base,
            )
            _write_checkpoint_for_batch(batch_id, plan, base)
            _heartbeat_lock(base, batch_id)
        return _build_batch_summary(batch_id, plan, base, dry_run=dry_run)
    finally:
        release_corpus_batch_lock(batch_id, root=base)


def resume_corpus_batch_plan(
    batch_id: str,
    dry_run: bool = True,
    limit: int = 25,
    retry_failures: bool = False,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, object]:
    return execute_corpus_batch_plan(batch_id, dry_run=dry_run, limit=limit, resume=True, retry_failures=retry_failures, force=False, root=root)


def pause_corpus_batch_plan(batch_id: str, note: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_corpus_execution_dirs(root)
    state = _load_execution_state(batch_id, base)
    state["status"] = "paused"
    state["note"] = _sanitize_text(note)
    state["updated_at_utc"] = _now()
    _save_execution_state(base, batch_id, state)
    _append_history_event(base, "batch_paused", {"batch_id": batch_id, "note": state.get("note")})
    return state


def cancel_corpus_batch_plan(batch_id: str, note: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_corpus_execution_dirs(root)
    state = _load_execution_state(batch_id, base)
    state["status"] = "cancelled"
    state["note"] = _sanitize_text(note)
    state["updated_at_utc"] = _now()
    _save_execution_state(base, batch_id, state)
    _append_history_event(base, "batch_cancelled", {"batch_id": batch_id, "note": state.get("note")})
    return state


def get_batch_recovery_state(batch_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_corpus_execution_dirs(root)
    receipts = list_execution_receipts(batch_id=batch_id, limit=1000, root=base).get("receipts", [])
    checkpoint = load_corpus_checkpoint(batch_id, root=base)
    state = _load_execution_state(batch_id, base)
    lock = get_corpus_batch_lock(batch_id, root=base)
    resume_available = any(receipt.get("status") in {"started", "failed", "blocked", "interrupted", "cancelled", "skipped"} for receipt in receipts) or bool(checkpoint.get("pending_document_ids"))
    return {
        "batch_id": batch_id,
        "status": state.get("status", "unknown"),
        "resume_available": resume_available,
        "checkpoint_id": checkpoint.get("checkpoint_id"),
        "lock_status": (lock or {}).get("status", "none"),
        "receipt_count": len(receipts),
        "pending_document_ids": checkpoint.get("pending_document_ids", []),
        "warnings": list(dict.fromkeys([*(checkpoint.get("warnings", []) or []), *(state.get("warnings", []) or [])])),
    }


def load_corpus_checkpoint(batch_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    path = _checkpoint_path(ensure_corpus_execution_dirs(root), batch_id)
    data = _read_json(path, default=None)
    if data is None:
        return {"batch_id": batch_id, "status": "no_checkpoint", "warnings": ["no_checkpoint"]}
    return data


def validate_corpus_checkpoint(batch_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    checkpoint = load_corpus_checkpoint(batch_id, root=root)
    if checkpoint.get("status") == "no_checkpoint":
        return {"batch_id": batch_id, "valid": False, "status": "no_checkpoint", "warnings": ["no_checkpoint"]}
    expected = _checkpoint_checksum({key: value for key, value in checkpoint.items() if key != "checksum"})
    valid = checkpoint.get("checksum") == expected
    return {"batch_id": batch_id, "valid": valid, "status": checkpoint.get("status"), "warnings": [] if valid else ["checksum_mismatch"], "checkpoint_id": checkpoint.get("checkpoint_id")}


def detect_stale_executions(batch_id: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_corpus_execution_dirs(root)
    config = validate_corpus_execution_config(get_corpus_execution_config())
    rows = []
    for receipt in list_execution_receipts(batch_id=batch_id, limit=100000, root=base).get("receipts", []):
        if receipt.get("status") != "started":
            continue
        started = _parse_utc(receipt.get("started_at_utc"))
        if started <= datetime.now(UTC) - timedelta(seconds=int(config["stale_lock_seconds"])):
            rows.append({"receipt_id": receipt.get("receipt_id"), "batch_id": receipt.get("batch_id"), "document_id": receipt.get("document_id"), "action": receipt.get("action"), "status": "stale_execution"})
    return {"stale_count": len(rows), "items": rows}


def mark_stale_executions_interrupted(batch_id: str, explicit: bool = False, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    if not explicit:
        return {"batch_id": batch_id, "updated": 0, "warnings": ["explicit_action_required"]}
    base = ensure_corpus_execution_dirs(root)
    stale = detect_stale_executions(batch_id=batch_id, root=base)
    updated = 0
    for item in stale.get("items", []):
        finalize_execution_receipt(
            str(item["receipt_id"]),
            status="interrupted",
            classification="interrupted",
            output_summary={"attempted": True, "interrupted": True},
            warnings=["stale_execution"],
            root=base,
        )
        updated += 1
    if updated:
        plan = _load_batch_plan(batch_id, base)
        _write_checkpoint_for_batch(batch_id, plan, base)
    return {"batch_id": batch_id, "updated": updated, "warnings": ["stale_execution"] if updated else []}


def get_corpus_execution_history(
    batch_id: str | None = None,
    document_id: str | None = None,
    action: str | None = None,
    limit: int = 100,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, object]:
    base = ensure_corpus_execution_dirs(root)
    receipts = list_execution_receipts(batch_id=batch_id, document_id=document_id, action=action, limit=limit, root=base).get("receipts", [])
    counts = Counter(str(item.get("classification") or "unknown") for item in receipts)
    return {
        "receipt_count": len(receipts),
        "classification_counts": dict(counts),
        "receipts": receipts,
    }


def format_corpus_execution_report_text(batch_id: str, public_safe: bool = True, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> str:
    base = ensure_corpus_execution_dirs(root)
    plan = _load_batch_plan(batch_id, base)
    history = get_corpus_execution_history(batch_id=batch_id, limit=1000, root=base)
    checkpoint = load_corpus_checkpoint(batch_id, root=base)
    lock = get_corpus_batch_lock(batch_id, root=base) or {"status": "none"}
    recovery = get_batch_recovery_state(batch_id, root=base)
    summary = _build_batch_summary(batch_id, plan, base, dry_run=_load_execution_state(batch_id, base).get("dry_run", True))
    lines = [
        "Corpus Execution Report",
        "",
        f"Batch ID: {batch_id}",
        f"Action: {plan.get('action')}",
        f"Dry Run: {summary.get('dry_run')}",
        f"Batch Status: {summary.get('status')}",
        f"Lock Status: {lock.get('status', 'none')}",
        "",
        "Receipt Counts:",
        f"- Planned: {summary.get('planned')}",
        f"- Attempted: {summary.get('attempted')}",
        f"- Completed: {summary.get('completed')}",
        f"- Completed With Warnings: {summary.get('completed_with_warnings')}",
        f"- Already Completed: {summary.get('already_completed')}",
        f"- Blocked: {summary.get('blocked')}",
        f"- Failed: {summary.get('failed')}",
        f"- Interrupted: {summary.get('interrupted')}",
        f"- Pending: {summary.get('pending')}",
        "",
        "Checkpoint:",
        f"- Status: {checkpoint.get('status', 'no_checkpoint')}",
        f"- Valid: {validate_corpus_checkpoint(batch_id, root=base).get('valid', False)}",
        f"- Last Processed Document: {checkpoint.get('last_processed_document_id')}",
        "",
        "Recovery:",
        f"- Resume Available: {recovery.get('resume_available')}",
        f"- Retry Counts: {history.get('classification_counts', {})}",
        f"- Recommended Action: {_execution_recommendation(summary, recovery)}",
    ]
    text = "\n".join(lines)
    return _sanitize_text(text) if public_safe else text


def get_corpus_index_registry() -> dict[str, object]:
    return {
        "source_document_index": {
            "index_name": "source_document_index",
            "index_path": "indexes/source_document_index.json",
            "record_directory": "indexes",
            "record_file_suffix": ".json",
            "record_id_field": "document_id",
            "document_id_field": "document_id",
            "entry_id_field": "document_id",
            "optional": False,
            "schema_versions": ["phase6_pdf_source_intake_v1"],
        },
        "chunk_index": {
            "index_name": "chunk_index",
            "index_path": "indexes/chunk_index.json",
            "record_directory": "chunks",
            "record_file_suffix": ".json",
            "record_id_field": "chunk_id",
            "document_id_field": "document_id",
            "entry_id_field": "chunk_id",
            "optional": False,
            "schema_versions": ["source_chunk_v1"],
        },
        "proposal_index": {
            "index_name": "proposal_index",
            "index_path": "indexes/proposal_index.json",
            "record_directory": "proposals",
            "record_file_suffix": ".json",
            "record_id_field": "proposal_id",
            "document_id_field": "document_id",
            "entry_id_field": "proposal_id",
            "optional": False,
            "schema_versions": ["source_proposal_v1"],
        },
        "citation_index": {
            "index_name": "citation_index",
            "index_path": "indexes/citation_index.json",
            "record_directory": "citations",
            "record_file_suffix": ".json",
            "record_id_field": "citation_id",
            "document_id_field": "document_id",
            "entry_id_field": "citation_id",
            "optional": False,
            "schema_versions": ["source_citation_v1"],
        },
        "page_diagnostics_index": {
            "index_name": "page_diagnostics_index",
            "index_path": "indexes/page_diagnostics_index.json",
            "record_directory": "page_diagnostics",
            "record_file_suffix": ".json",
            "record_id_field": "document_id",
            "document_id_field": "document_id",
            "entry_id_field": "document_id",
            "optional": True,
            "schema_versions": ["source_page_diagnostics_v1"],
        },
        "structure_map_index": {
            "index_name": "structure_map_index",
            "index_path": "indexes/structure_map_index.json",
            "record_directory": "structure_maps",
            "record_file_suffix": "_structure.json",
            "record_id_field": "document_id",
            "document_id_field": "document_id",
            "entry_id_field": "document_id",
            "optional": True,
            "schema_versions": ["document_structure_v1"],
        },
        "corpus_execution_index": {
            "index_name": "corpus_execution_index",
            "index_path": "indexes/corpus_execution_index.json",
            "record_directory": "corpus_execution",
            "record_file_suffix": ".json",
            "record_id_field": "execution_id",
            "document_id_field": None,
            "entry_id_field": "execution_id",
            "optional": True,
            "schema_versions": [EXECUTION_SCHEMA_VERSION],
        },
        "corpus_receipt_index": {
            "index_name": "corpus_receipt_index",
            "index_path": "indexes/corpus_receipt_index.json",
            "record_directory": "corpus_execution_receipts",
            "record_file_suffix": ".json",
            "record_id_field": "receipt_id",
            "document_id_field": "document_id",
            "entry_id_field": "receipt_id",
            "optional": True,
            "schema_versions": [RECEIPT_SCHEMA_VERSION],
        },
        "corpus_lock_index": {
            "index_name": "corpus_lock_index",
            "index_path": "indexes/corpus_lock_index.json",
            "record_directory": "corpus_execution_locks",
            "record_file_suffix": ".json",
            "record_id_field": "lock_id",
            "document_id_field": None,
            "entry_id_field": "lock_id",
            "optional": True,
            "schema_versions": [],
        },
        "corpus_checkpoint_index": {
            "index_name": "corpus_checkpoint_index",
            "index_path": "indexes/corpus_checkpoint_index.json",
            "record_directory": "corpus_checkpoints",
            "record_file_suffix": ".json",
            "record_id_field": "checkpoint_id",
            "document_id_field": None,
            "entry_id_field": "checkpoint_id",
            "optional": True,
            "schema_versions": [CHECKPOINT_SCHEMA_VERSION],
        },
        "corpus_repair_index": {
            "index_name": "corpus_repair_index",
            "index_path": "indexes/corpus_repair_index.json",
            "record_directory": "corpus_repairs",
            "record_file_suffix": ".json",
            "record_id_field": "repair_id",
            "document_id_field": None,
            "entry_id_field": "repair_id",
            "optional": True,
            "schema_versions": [REPAIR_PLAN_SCHEMA_VERSION],
        },
        "corpus_repair_backup_index": {
            "index_name": "corpus_repair_backup_index",
            "index_path": "indexes/corpus_repair_backup_index.json",
            "record_directory": "corpus_repair_backups",
            "record_file_suffix": "_manifest.json",
            "record_id_field": "backup_id",
            "document_id_field": None,
            "entry_id_field": "backup_id",
            "optional": True,
            "schema_versions": [REPAIR_BACKUP_SCHEMA_VERSION],
        },
        "corpus_quarantine_index": {
            "index_name": "corpus_quarantine_index",
            "index_path": "indexes/corpus_quarantine_index.json",
            "record_directory": "corpus_quarantine",
            "record_file_suffix": ".json",
            "record_id_field": "quarantine_id",
            "document_id_field": None,
            "entry_id_field": "quarantine_id",
            "optional": True,
            "schema_versions": [QUARANTINE_SCHEMA_VERSION],
        },
    }


def validate_corpus_index_integrity(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    registry = get_corpus_index_registry()
    items = [validate_single_index_integrity(name, root=root) for name in registry]
    return {
        "healthy_index_count": sum(1 for item in items if item.get("severity") == "info" and not item.get("issues")),
        "warning_index_count": sum(1 for item in items if item.get("severity") == "warning"),
        "critical_index_count": sum(1 for item in items if item.get("severity") == "critical"),
        "items": items,
    }


def validate_single_index_integrity(index_name: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_corpus_execution_dirs(root)
    registry = get_corpus_index_registry()
    if index_name not in registry:
        raise ValueError(f"Unknown index: {index_name}")
    spec = registry[index_name]
    path = base / str(spec["index_path"])
    issues: list[dict[str, object]] = []
    severity = "info"
    if not path.exists():
        missing_severity = "info" if spec.get("optional") else "critical"
        issues.append({"code": "index_missing", "severity": missing_severity})
        return {"index_name": index_name, "severity": missing_severity, "issues": issues, "mutated": False}
    data = _read_json(path, default=None)
    if not isinstance(data, dict):
        issues.append({"code": "invalid_json", "severity": "critical"})
        return {"index_name": index_name, "severity": "critical", "issues": issues, "mutated": False}
    entries = data.get("entries")
    if not isinstance(entries, list):
        issues.append({"code": "unsupported_top_level_shape", "severity": "critical"})
        return {"index_name": index_name, "severity": "critical", "issues": issues, "mutated": False}
    entry_id_field = str(spec["entry_id_field"])
    entry_ids = [entry.get(entry_id_field) for entry in entries if isinstance(entry, Mapping)]
    duplicates = [item for item, count in Counter(entry_ids).items() if item and count > 1]
    for duplicate in duplicates:
        issues.append({"code": "duplicate_index_entry", "severity": "critical", "record_id": duplicate})
    record_dir = base / str(spec["record_directory"])
    record_id_field = str(spec["record_id_field"])
    document_id_field = spec.get("document_id_field")
    indexed_ids = {str(item) for item in entry_ids if item}
    for entry in entries:
        if not isinstance(entry, Mapping):
            issues.append({"code": "invalid_entry", "severity": "critical"})
            continue
        record_id = str(entry.get(entry_id_field) or "")
        if not record_id:
            issues.append({"code": "missing_record_id", "severity": "critical"})
            continue
        record_path = _record_path_for_registry(base, spec, record_id)
        if not record_path.exists():
            issues.append({"code": "missing_record", "severity": "critical", "record_id": record_id})
            continue
        record = _read_json(record_path, default=None)
        if not isinstance(record, dict):
            issues.append({"code": "corrupt_record", "severity": "critical", "record_id": record_id})
            continue
        if str(record.get(record_id_field) or "") != record_id:
            issues.append({"code": "record_id_mismatch", "severity": "critical", "record_id": record_id})
        if document_id_field and entry.get(document_id_field) != record.get(document_id_field):
            issues.append({"code": "document_id_mismatch", "severity": "warning", "record_id": record_id})
        allowed_versions = list(spec.get("schema_versions") or [])
        if allowed_versions and record.get("schema_version") not in allowed_versions:
            code = "unsupported_schema_version" if record.get("schema_version") else "invalid_schema_version"
            issues.append({"code": code, "severity": "critical", "record_id": record_id})
    if record_dir.exists():
        for record_path in sorted(record_dir.glob(f"*{spec['record_file_suffix']}")):
            if record_path.name.startswith("."):
                issues.append({"code": "stale_temporary_file", "severity": "warning", "path": record_path.name})
                continue
            record = _read_json(record_path, default=None)
            if not isinstance(record, dict):
                issues.append({"code": "corrupt_record", "severity": "critical", "path": record_path.name})
                continue
            if "entries" in record and record_id_field not in record:
                continue
            record_id = str(record.get(record_id_field) or "")
            if record_id and record_id not in indexed_ids:
                issues.append({"code": "unindexed_record", "severity": "warning", "record_id": record_id})
    if any(item["severity"] == "critical" for item in issues):
        severity = "critical"
    elif issues:
        severity = "warning"
    tmp_path = path.with_name(f".{path.name}.tmp")
    if tmp_path.exists():
        issues.append({"code": "stale_temporary_file", "severity": "warning", "path": tmp_path.name})
        if severity == "info":
            severity = "warning"
    return {"index_name": index_name, "severity": severity, "issues": issues, "mutated": False}


def build_corpus_repair_plan(
    index_names: list[str] | None = None,
    dry_run: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, object]:
    base = ensure_corpus_execution_dirs(root)
    registry = get_corpus_index_registry()
    names = index_names or list(registry.keys())
    items = []
    for name in names:
        validation = validate_single_index_integrity(name, root=base)
        preview = _build_repair_preview(base, registry[name], validation)
        items.append(preview)
    repair_id = f"repair_{_timestamp_token()}"
    plan = {
        "repair_id": repair_id,
        "created_at_utc": _now(),
        "schema_version": REPAIR_PLAN_SCHEMA_VERSION,
        "dry_run": bool(dry_run),
        "status": "planned",
        "items": items,
        "warnings": [],
    }
    _atomic_write_json(_repair_plan_path(base, repair_id), plan)
    _update_execution_index(base, "corpus_repair_index.json", _list_repair_index_entries(base))
    return plan


def create_corpus_repair_backup(repair_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_corpus_execution_dirs(root)
    plan = _load_repair_plan(repair_id, base)
    backup_id = f"backup_{_timestamp_token()}"
    backup_dir = base / "corpus_repair_backups" / backup_id
    if backup_dir.exists():
        raise FileExistsError(str(backup_dir))
    backup_dir.mkdir(parents=True, exist_ok=False)
    files = []
    for item in plan.get("items", []):
        index_name = str(item.get("index_name"))
        spec = get_corpus_index_registry().get(index_name)
        if not spec:
            continue
        source_path = base / str(spec["index_path"])
        if not source_path.exists():
            continue
        destination = backup_dir / source_path.name
        shutil.copy2(source_path, destination)
        files.append({"logical_name": index_name, "sha256": _hash_file(destination), "size_bytes": destination.stat().st_size, "filename": destination.name})
    manifest = {
        "backup_id": backup_id,
        "repair_id": repair_id,
        "created_at_utc": _now(),
        "files": files,
        "schema_version": REPAIR_BACKUP_SCHEMA_VERSION,
        "status": "completed",
    }
    manifest["manifest_hash"] = _hash_json_payload({key: value for key, value in manifest.items() if key != "manifest_hash"})
    _atomic_write_json(backup_dir / f"{backup_id}_manifest.json", manifest)
    _update_execution_index(base, "corpus_repair_backup_index.json", _list_backup_index_entries(base))
    plan["backup_id"] = backup_id
    _atomic_write_json(_repair_plan_path(base, repair_id), plan)
    return manifest


def verify_corpus_repair_backup(backup_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_corpus_execution_dirs(root)
    manifest = _load_backup_manifest(backup_id, base)
    if not manifest:
        return {"backup_id": backup_id, "verified": False, "warnings": ["backup_missing"]}
    expected_manifest_hash = _hash_json_payload({key: value for key, value in manifest.items() if key != "manifest_hash"})
    if manifest.get("manifest_hash") != expected_manifest_hash:
        return {"backup_id": backup_id, "verified": False, "warnings": ["manifest_hash_mismatch"]}
    backup_dir = base / "corpus_repair_backups" / backup_id
    bad = []
    for item in manifest.get("files", []):
        file_path = backup_dir / str(item.get("filename"))
        if not file_path.exists() or _hash_file(file_path) != item.get("sha256"):
            bad.append(str(item.get("logical_name")))
    return {"backup_id": backup_id, "verified": not bad, "warnings": ["backup_hash_mismatch"] if bad else [], "mismatched_files": bad}


def quarantine_corrupt_corpus_record(
    record_type: str,
    record_id: str,
    reason: str,
    repair_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, object]:
    base = ensure_corpus_execution_dirs(root)
    source_path = _find_quarantine_source_path(base, record_type, record_id)
    if source_path is None or not source_path.exists():
        raise FileNotFoundError(record_id)
    quarantine_id = f"quarantine_{_safe_id(record_type)}_{_safe_id(record_id)}_{_timestamp_token()}"
    destination_dir = base / "corpus_quarantine" / _safe_id(record_type)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{_safe_id(record_id)}_{_timestamp_token()}{source_path.suffix}"
    raw = source_path.read_bytes()
    shutil.move(str(source_path), str(destination))
    record = {
        "quarantine_id": quarantine_id,
        "record_type": record_type,
        "record_id": record_id,
        "reason": _sanitize_text(reason),
        "repair_id": repair_id,
        "created_at_utc": _now(),
        "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "stored_name": destination.name,
        "original_name": source_path.name,
        "schema_version": QUARANTINE_SCHEMA_VERSION,
    }
    _atomic_write_json(base / "corpus_quarantine" / f"{quarantine_id}.json", record)
    _update_execution_index(base, "corpus_quarantine_index.json", _list_quarantine_index_entries(base))
    return record


def list_quarantined_corpus_records(
    record_type: str | None = None,
    limit: int = 100,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, object]:
    base = ensure_corpus_execution_dirs(root)
    rows = []
    for path in sorted((base / "corpus_quarantine").glob("quarantine_*.json"), reverse=True):
        data = _read_json(path, default=None)
        if not isinstance(data, dict):
            continue
        if record_type is not None and data.get("record_type") != record_type:
            continue
        rows.append(data)
    limited = rows[: max(0, int(limit or 0))]
    return {"count": len(limited), "items": limited}


def execute_corpus_repair_plan(repair_id: str, dry_run: bool = True, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_corpus_execution_dirs(root)
    plan = _load_repair_plan(repair_id, base)
    if dry_run:
        return {"repair_id": repair_id, "dry_run": True, "status": "dry_run_only", "items": plan.get("items", [])}
    backup_id = str(plan.get("backup_id") or "")
    if not backup_id:
        return {"repair_id": repair_id, "status": "blocked", "warnings": ["missing_backup"]}
    backup = verify_corpus_repair_backup(backup_id, root=base)
    if not backup.get("verified"):
        return {"repair_id": repair_id, "status": "blocked", "warnings": list(backup.get("warnings", []))}
    staging_dir = base / "corpus_repair_staging" / repair_id
    staging_dir.mkdir(parents=True, exist_ok=True)
    replaced = []
    registry = get_corpus_index_registry()
    for item in plan.get("items", []):
        index_name = str(item.get("index_name"))
        spec = registry.get(index_name)
        if not spec:
            continue
        rebuilt = _rebuild_index_payload(base, spec, repair_id=repair_id, quarantine_invalid=True)
        staged_path = staging_dir / Path(str(spec["index_path"])).name
        _atomic_write_json(staged_path, rebuilt)
        staged_validation = _validate_staged_index_payload(base, spec, rebuilt)
        if not staged_validation["valid"]:
            return {"repair_id": repair_id, "status": "blocked", "warnings": ["staged_validation_failed"], "index_name": index_name}
        live_path = base / str(spec["index_path"])
        backup_live = _read_json(live_path, default={})
        try:
            os.replace(staged_path, live_path)
            live_validation = validate_single_index_integrity(index_name, root=base)
            if live_validation.get("severity") == "critical":
                _restore_backup_manifest(base, repair_id, backup_id)
                return {"repair_id": repair_id, "status": "rollback_required", "warnings": ["live_validation_failed"], "index_name": index_name}
            replaced.append({"index_name": index_name, "before": len((backup_live or {}).get("entries", [])), "after": len(rebuilt.get("entries", []))})
        except Exception:
            _restore_backup_manifest(base, repair_id, backup_id)
            return {"repair_id": repair_id, "status": "rollback_required", "warnings": ["atomic_replace_failed"], "index_name": index_name}
    plan["status"] = "completed"
    plan["completed_at_utc"] = _now()
    _atomic_write_json(_repair_plan_path(base, repair_id), plan)
    return {"repair_id": repair_id, "status": "completed", "replaced": replaced}


def rollback_corpus_repair(repair_id: str, explicit: bool = False, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    if not explicit:
        return {"repair_id": repair_id, "status": "blocked", "warnings": ["explicit_action_required"]}
    base = ensure_corpus_execution_dirs(root)
    plan = _load_repair_plan(repair_id, base)
    backup_id = str(plan.get("backup_id") or "")
    if not backup_id:
        return {"repair_id": repair_id, "status": "blocked", "warnings": ["missing_backup"]}
    restored = _restore_backup_manifest(base, repair_id, backup_id)
    _append_history_event(base, "repair_rollback", {"repair_id": repair_id, "restored": restored})
    return {"repair_id": repair_id, "status": "rolled_back", "restored_files": restored}


def detect_partial_corpus_writes(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_corpus_execution_dirs(root)
    items = []
    for path in sorted(base.rglob("*.tmp")):
        items.append({"type": "temporary_json_file", "name": path.name, "relative_path": str(path.relative_to(base))})
    for path in sorted((base / "corpus_repair_staging").glob("*")):
        items.append({"type": "staging_index", "name": path.name, "relative_path": str(path.relative_to(base))})
    for receipt in list_execution_receipts(limit=100000, root=base).get("receipts", []):
        if receipt.get("status") == "started":
            items.append({"type": "receipt_missing_finalization", "receipt_id": receipt.get("receipt_id")})
    return {"count": len(items), "items": items}


def build_partial_write_recovery_plan(dry_run: bool = True, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    detected = detect_partial_corpus_writes(root=root)
    actions = []
    for item in detected.get("items", []):
        if item.get("type") == "temporary_json_file":
            actions.append({"action": "remove_stale_temporary_file_after_backup", "target": item.get("relative_path")})
        elif item.get("type") == "receipt_missing_finalization":
            actions.append({"action": "mark_started_receipt_interrupted", "target": item.get("receipt_id")})
        else:
            actions.append({"action": "leave_unknown_issue_unchanged", "target": item.get("relative_path") or item.get("name")})
    return {"dry_run": bool(dry_run), "count": len(actions), "actions": actions}


def format_corpus_integrity_report_text(public_safe: bool = True, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> str:
    integrity = validate_corpus_index_integrity(root=root)
    lines = [
        "Corpus Index Integrity Report",
        "",
        f"Healthy Indexes: {integrity.get('healthy_index_count')}",
        f"Warning Indexes: {integrity.get('warning_index_count')}",
        f"Critical Indexes: {integrity.get('critical_index_count')}",
    ]
    for item in integrity.get("items", []):
        codes = ", ".join(str(issue.get("code")) for issue in item.get("issues", [])) or "none"
        lines.append(f"- {item.get('index_name')}: {item.get('severity')} ({codes})")
    text = "\n".join(lines)
    return _sanitize_text(text) if public_safe else text


def _build_input_state(document_id: str, action: str, dependency: Mapping[str, object], root: Path) -> dict[str, object]:
    record = load_source_document(document_id, root=root, missing_ok=True)
    preflight = get_document_preflight_summary(document_id, root=root)
    structure = get_document_structure_summary(document_id, root=root)
    diagnostics = get_page_diagnostic_summary(document_id, root=root)
    chunks = load_chunks(document_id=document_id, root=root)
    input_summary = {
        "document_id": document_id,
        "action": action,
        "document_hash": record.sha256 if record else None,
        "extraction_status": record.extraction_status if record else None,
        "preflight_status": preflight.get("status"),
        "structure_status": structure.get("status"),
        "pages_diagnosed": diagnostics.get("pages_diagnosed"),
        "chunk_count": len(chunks),
        "dependency_allowed": dependency.get("allowed"),
        "schema_version": ACTION_SCHEMA_VERSION,
    }
    return {
        "input_hashes": {
            "document_hash": record.sha256 if record else None,
            "state_hash": _hash_json_payload(input_summary),
        },
        "input_summary": input_summary,
    }


def _execute_action(action: str, document_id: str, root: Path) -> dict[str, object]:
    if action == "run_preflight":
        result = run_document_preflight(document_id, root=root)
    elif action == "extract_text":
        result = extract_pdf_text(document_id, root=root).to_json(public_safe=True)
    elif action == "chunk_text":
        chunks = chunk_extracted_text(document_id, root=root)
        result = {"chunk_count": len(chunks)}
    elif action == "build_page_diagnostics":
        diagnostics = build_page_diagnostics(document_id, root=root)
        result = {"pages_diagnosed": len(diagnostics)}
    elif action == "build_structure_map":
        result = build_document_structure_map(document_id, root=root)
    elif action == "recalculate_reliability":
        result = recalculate_source_reliability(document_id, root=root)
    elif action == "refresh_evidence_binders":
        result = refresh_evidence_binders_for_source(document_id, root=root)
    elif action == "detect_duplicates":
        result = detect_duplicate_source_identity(document_id, root=root)
    elif action == "detect_missing_steps":
        from .source_corpus_manager import detect_source_missing_steps

        result = detect_source_missing_steps(document_id, root=root)
    elif action == "generate_corpus_report":
        from .source_corpus_manager import format_source_corpus_report_text

        text = format_source_corpus_report_text(root=root)
        report_id = f"audit_{_timestamp_token()}"
        _atomic_write_json(root / "corpus_audits" / f"{report_id}.json", {"report_id": report_id, "text": _sanitize_text(text), "created_at_utc": _now()})
        result = {"report_id": report_id}
    else:
        raise NotImplementedError(action)
    if hasattr(result, "to_json"):
        result = result.to_json()
    payload = result if isinstance(result, dict) else {"result": str(result)}
    return {
        "output_summary": _json_safe(payload),
        "output_hashes": {"result_hash": _hash_json_payload(_json_safe(payload))},
        "warnings": list(payload.get("warnings", [])) if isinstance(payload, dict) else [],
    }


def _retry_budget_state(receipts: list[dict[str, object]], config: Mapping[str, object]) -> dict[str, object]:
    consumed = [
        item
        for item in receipts
        if item.get("status") not in {"already_completed", "blocked"} and item.get("classification") not in {"dependency_missing", "already_completed"}
    ]
    attempt_number = len(receipts) + 1
    return {
        "attempt_number": attempt_number,
        "maximum_retries": int(config["maximum_retries"]),
        "last_error_type": receipts[-1].get("error_type") if receipts else None,
        "last_error_message": receipts[-1].get("error_message") if receipts else None,
        "retry_allowed": len(consumed) < int(config["maximum_retries"]),
        "idempotency_key_placeholder": f"sha256:pending:{attempt_number}",
    }


def _write_checkpoint_for_batch(batch_id: str, plan: Mapping[str, object], root: Path) -> dict[str, object]:
    base = ensure_corpus_execution_dirs(root)
    prior = load_corpus_checkpoint(batch_id, root=base)
    receipts = list_execution_receipts(batch_id=batch_id, limit=100000, root=base).get("receipts", [])
    grouped = _group_latest_receipts(receipts)
    completed_ids = [item["receipt_id"] for item in grouped.values() if item.get("status") in {"completed", "completed_with_warnings", "already_completed"}]
    failed_ids = [item["receipt_id"] for item in grouped.values() if item.get("status") == "failed"]
    blocked_ids = [item["receipt_id"] for item in grouped.values() if item.get("status") == "blocked"]
    interrupted_ids = [item["receipt_id"] for item in grouped.values() if item.get("status") == "interrupted"]
    pending = [doc for doc in plan.get("document_ids", []) if doc not in {key[0] for key, item in grouped.items() if item.get("status") in FINAL_RECEIPT_STATUSES}]
    checkpoint = {
        "checkpoint_id": f"checkpoint_{_safe_id(batch_id)}_{_timestamp_token()}",
        "batch_id": batch_id,
        "generation": int(prior.get("generation", 0) or 0) + 1,
        "created_at_utc": prior.get("created_at_utc") or _now(),
        "updated_at_utc": _now(),
        "completed_receipt_ids": completed_ids,
        "failed_receipt_ids": failed_ids,
        "blocked_receipt_ids": blocked_ids,
        "interrupted_receipt_ids": interrupted_ids,
        "pending_document_ids": pending,
        "last_processed_document_id": receipts[0].get("document_id") if receipts else None,
        "status": _checkpoint_status(grouped, pending, _load_execution_state(batch_id, base).get("status")),
        "warnings": [],
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
    }
    checkpoint["checksum"] = _checkpoint_checksum(checkpoint)
    _atomic_write_json(_checkpoint_path(base, batch_id), checkpoint)
    _update_execution_index(base, "corpus_checkpoint_index.json", _list_checkpoint_index_entries(base))
    return checkpoint


def _checkpoint_status(grouped: Mapping[tuple[str, str], Mapping[str, object]], pending: list[str], state_status: str | None) -> str:
    if state_status == "cancelled":
        return "cancelled"
    if state_status == "paused":
        return "paused"
    statuses = {item.get("status") for item in grouped.values()}
    if "failed" in statuses or "interrupted" in statuses or pending:
        return "running" if statuses & {"started"} or pending else "completed_with_warnings"
    if "blocked" in statuses or "completed_with_warnings" in statuses or "skipped" in statuses:
        return "completed_with_warnings"
    return "completed"


def _build_batch_summary(batch_id: str, plan: Mapping[str, object], root: Path, *, dry_run: bool) -> dict[str, object]:
    receipts = list_execution_receipts(batch_id=batch_id, limit=100000, root=root).get("receipts", [])
    grouped = _group_latest_receipts(receipts)
    latest = list(grouped.values())
    checkpoint = load_corpus_checkpoint(batch_id, root=root)
    counts = Counter(str(item.get("status")) for item in latest)
    pending = [doc for doc in plan.get("document_ids", []) if doc not in {item.get("document_id") for item in latest if item.get("status") in FINAL_RECEIPT_STATUSES}]
    status = "completed"
    if checkpoint.get("status") in {"paused", "cancelled"}:
        status = checkpoint.get("status")
    elif counts.get("failed") or counts.get("interrupted") or pending:
        status = "completed_with_warnings" if not dry_run else "dry_run"
    elif counts.get("blocked") or counts.get("completed_with_warnings") or counts.get("skipped"):
        status = "completed_with_warnings" if not dry_run else "dry_run"
    elif dry_run:
        status = "dry_run"
    return {
        "batch_id": batch_id,
        "dry_run": dry_run,
        "status": status,
        "planned": len(plan.get("document_ids", [])),
        "attempted": len(latest),
        "completed": counts.get("completed", 0),
        "completed_with_warnings": counts.get("completed_with_warnings", 0),
        "already_completed": counts.get("already_completed", 0),
        "blocked": counts.get("blocked", 0),
        "failed": counts.get("failed", 0),
        "interrupted": counts.get("interrupted", 0),
        "pending": len(pending),
        "checkpoint_id": checkpoint.get("checkpoint_id"),
        "warnings": [],
        "items": latest,
    }


def _group_latest_receipts(receipts: list[dict[str, object]]) -> dict[tuple[str, str], dict[str, object]]:
    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for receipt in sorted(receipts, key=lambda item: (str(item.get("completed_at_utc") or ""), str(item.get("started_at_utc") or ""), str(item.get("receipt_id") or ""))):
        grouped[(str(receipt.get("document_id")), str(receipt.get("action")))] = receipt
    return grouped


def _is_successful_receipt(receipt: Mapping[str, object] | None) -> bool:
    return bool(receipt and receipt.get("status") in SUCCESS_RECEIPT_STATUSES)


def _validate_batch_schema(plan: Mapping[str, object]) -> None:
    if str(plan.get("schema_version") or "") != ACTION_SCHEMA_VERSION:
        raise ValueError("Unsupported batch schema version.")
    if str(plan.get("action") or "") not in ALLOWED_BATCH_ACTIONS:
        raise ValueError("Unsupported batch action.")
    if not isinstance(plan.get("document_ids"), list):
        raise ValueError("Batch document_ids must be a list.")


def _load_batch_plan(batch_id: str, root: Path) -> dict[str, object]:
    path = root / "corpus_batches" / f"{_safe_id(batch_id)}.json"
    data = _read_json(path, default=None)
    if not isinstance(data, dict):
        raise FileNotFoundError(str(path))
    return data


def _write_execution_snapshot(root: Path, batch_id: str, plan: Mapping[str, object], **state: object) -> dict[str, object]:
    current = _load_execution_state(batch_id, root)
    payload = {
        "execution_id": current.get("execution_id") or f"execution_{_safe_id(batch_id)}_{_timestamp_token()}",
        "batch_id": batch_id,
        "action": plan.get("action"),
        "created_at_utc": current.get("created_at_utc") or _now(),
        "updated_at_utc": _now(),
        "status": current.get("status", "running"),
        "schema_version": EXECUTION_SCHEMA_VERSION,
        "plan_hash": _hash_json_payload(_json_safe(dict(plan))),
    }
    payload.update(state)
    _save_execution_state(root, batch_id, payload)
    _update_execution_index(root, "corpus_execution_index.json", _list_execution_index_entries(root))
    return payload


def _load_execution_state(batch_id: str, root: Path) -> dict[str, object]:
    path = root / "corpus_execution" / f"{_safe_id(batch_id)}.json"
    data = _read_json(path, default=None)
    if isinstance(data, dict):
        return data
    return {"batch_id": batch_id, "status": "running", "created_at_utc": _now(), "updated_at_utc": _now()}


def _save_execution_state(root: Path, batch_id: str, payload: Mapping[str, object]) -> None:
    _atomic_write_json(root / "corpus_execution" / f"{_safe_id(batch_id)}.json", dict(payload))
    _update_execution_index(root, "corpus_execution_index.json", _list_execution_index_entries(root))


def _heartbeat_lock(root: Path, batch_id: str) -> None:
    lock = get_corpus_batch_lock(batch_id, root=root)
    if not lock or lock.get("status") != "active":
        return
    lock["heartbeat_at_utc"] = _now()
    _atomic_write_json(_lock_path(root, batch_id), lock)
    _update_execution_index(root, "corpus_lock_index.json", _list_lock_index_entries(root))


def _receipt_path(root: Path, receipt_id: str) -> Path:
    return root / "corpus_execution_receipts" / f"{_safe_id(receipt_id)}.json"


def _checkpoint_path(root: Path, batch_id: str) -> Path:
    return root / "corpus_checkpoints" / f"{_safe_id(batch_id)}.json"


def _lock_path(root: Path, batch_id: str) -> Path:
    return root / "corpus_execution_locks" / f"{_safe_id(batch_id)}.json"


def _repair_plan_path(root: Path, repair_id: str) -> Path:
    return root / "corpus_repairs" / f"{_safe_id(repair_id)}.json"


def _checkpoint_checksum(payload: Mapping[str, object]) -> str:
    return _hash_json_payload(_json_safe(dict(payload)))


def _parse_utc(value: object) -> datetime:
    text = str(value or _now()).replace("Z", "+00:00")
    return datetime.fromisoformat(text).astimezone(UTC)


def _list_receipts_for_item(root: Path, batch_id: str, document_id: str, action: str) -> list[dict[str, object]]:
    receipts = list_execution_receipts(batch_id=batch_id, document_id=document_id, action=action, limit=100000, root=root).get("receipts", [])
    return sorted(receipts, key=lambda item: (item.get("started_at_utc") or "", item.get("receipt_id") or ""))


def _append_history_event(root: Path, event_type: str, payload: Mapping[str, object]) -> None:
    event = {"event_id": f"history_{_timestamp_token()}", "event_type": event_type, "created_at_utc": _now(), **_json_safe(dict(payload))}
    _atomic_write_json(root / "corpus_execution_history" / f"{event['event_id']}.json", event)


def _build_repair_preview(base: Path, spec: Mapping[str, object], validation: Mapping[str, object]) -> dict[str, object]:
    existing_entries = _load_index_entries(base / str(spec["index_path"]))
    rebuilt = _rebuild_index_payload(base, spec, repair_id=None, quarantine_invalid=False)
    issues = validation.get("issues", [])
    actions = []
    if any(item.get("code") in {"invalid_json", "unsupported_top_level_shape"} for item in issues):
        actions.append("rebuild_index_from_valid_records")
    if any(item.get("code") == "unindexed_record" for item in issues):
        actions.append("add_unindexed_valid_record")
    if any(item.get("code") == "missing_record" for item in issues):
        actions.append("omit_missing_record_reference_from_rebuilt_copy")
    if any(item.get("code") in {"corrupt_record"} for item in issues):
        actions.append("quarantine_invalid_record")
    if any(item.get("code") == "unsupported_schema_version" for item in issues):
        actions.append("quarantine_unsupported_schema_record")
    if any(item.get("code") == "stale_temporary_file" for item in issues):
        actions.append("remove_stale_temporary_file_after_backup")
    if not actions and issues:
        actions.append("leave_unknown_issue_unchanged")
    return {
        "index_name": spec["index_name"],
        "planned_actions": list(dict.fromkeys(actions)),
        "before_entries": len(existing_entries),
        "planned_after_entries": len(rebuilt.get("entries", [])),
        "records_to_add": max(0, len(rebuilt.get("entries", [])) - len(existing_entries)),
        "references_to_omit": max(0, len(existing_entries) - len(rebuilt.get("entries", []))),
        "records_to_quarantine": sum(1 for issue in issues if issue.get("code") in {"corrupt_record", "unsupported_schema_version"}),
        "issues": list(issues),
    }


def _rebuild_index_payload(base: Path, spec: Mapping[str, object], *, repair_id: str | None, quarantine_invalid: bool) -> dict[str, object]:
    record_dir = base / str(spec["record_directory"])
    entry_id_field = str(spec["entry_id_field"])
    record_id_field = str(spec["record_id_field"])
    document_id_field = spec.get("document_id_field")
    entries = []
    seen = set()
    if not record_dir.exists():
        return {"entries": []}
    for record_path in sorted(record_dir.glob(f"*{spec['record_file_suffix']}")):
        if record_path.name.startswith("."):
            continue
        record = _read_json(record_path, default=None)
        if not isinstance(record, dict):
            continue
        if "entries" in record and record_id_field not in record:
            continue
        record_id = str(record.get(record_id_field) or "")
        if not record_id or record_id in seen:
            continue
        allowed_versions = list(spec.get("schema_versions") or [])
        if allowed_versions and record.get("schema_version") not in allowed_versions:
            if quarantine_invalid and repair_id:
                _safe_quarantine_for_repair(base, spec, record_id, "unsupported_schema_version", repair_id)
            continue
        if quarantine_invalid and _record_looks_corrupt(record, record_id_field, record_id):
            _safe_quarantine_for_repair(base, spec, record_id, "corrupt_record", repair_id)
            continue
        entries.append(_build_index_entry_for_record(record_path, record, entry_id_field, document_id_field))
        seen.add(record_id)
    return {"entries": entries}


def _record_looks_corrupt(record: Mapping[str, object], record_id_field: str, record_id: str) -> bool:
    return str(record.get(record_id_field) or "") != record_id


def _safe_quarantine_for_repair(base: Path, spec: Mapping[str, object], record_id: str, reason: str, repair_id: str | None) -> None:
    try:
        quarantine_corrupt_corpus_record(str(spec["index_name"]).replace("_index", ""), record_id, reason, repair_id=repair_id, root=base)
    except Exception:
        return


def _build_index_entry_for_record(record_path: Path, record: Mapping[str, object], entry_id_field: str, document_id_field: str | None) -> dict[str, object]:
    if entry_id_field == "document_id" and record_path.parent.name == "indexes" and record.get("original_filename") is not None:
        return {
            "document_id": record.get("document_id"),
            "original_filename": record.get("original_filename"),
            "sha256": record.get("sha256"),
            "size_bytes": record.get("size_bytes"),
            "page_count": record.get("page_count"),
            "extraction_status": record.get("extraction_status"),
            "privacy_level": record.get("privacy_level"),
            "updated_at_utc": record.get("updated_at_utc"),
        }
    entry = {entry_id_field: record.get(entry_id_field)}
    if document_id_field:
        entry[document_id_field] = record.get(document_id_field)
    if record_path.parent.name == "chunks":
        entry.update(
            {
                "path": str(record_path),
                "chunk_number": record.get("chunk_number"),
                "text_hash": record.get("text_hash"),
                "char_count": record.get("char_count"),
                "quality_score": record.get("quality_score"),
                "created_at_utc": record.get("created_at_utc"),
            }
        )
    elif record_path.parent.name == "proposals":
        entry.update({"chunk_id": record.get("chunk_id"), "proposal_type": record.get("proposal_type"), "status": record.get("status"), "updated_at_utc": record.get("updated_at_utc")})
    elif record_path.parent.name == "citations":
        entry.update({"chunk_id": record.get("chunk_id"), "page_start": record.get("page_start"), "page_end": record.get("page_end"), "created_at_utc": record.get("created_at_utc")})
    elif record_path.parent.name == "page_diagnostics":
        entry.update({"path": str(record_path), "pages_diagnosed": len(record.get("pages", []))})
    elif record_path.parent.name == "structure_maps":
        entry.update({"path": str(record_path), "headings": len(record.get("headings", [])), "sections": len(record.get("sections", [])), "schema_version": record.get("schema_version")})
    else:
        entry.update({"path": str(record_path), "schema_version": record.get("schema_version")})
    return entry


def _validate_staged_index_payload(base: Path, spec: Mapping[str, object], payload: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(payload.get("entries"), list):
        return {"valid": False}
    for entry in payload.get("entries", []):
        record_id = str(entry.get(spec["entry_id_field"]) or "")
        if not record_id:
            return {"valid": False}
        if not _record_path_for_registry(base, spec, record_id).exists():
            return {"valid": False}
    return {"valid": True}


def _restore_backup_manifest(base: Path, repair_id: str, backup_id: str) -> list[str]:
    manifest = _load_backup_manifest(backup_id, base)
    if not manifest:
        return []
    restored = []
    registry = get_corpus_index_registry()
    for item in manifest.get("files", []):
        logical_name = str(item.get("logical_name"))
        spec = registry.get(logical_name)
        if not spec:
            continue
        source = base / "corpus_repair_backups" / backup_id / str(item.get("filename"))
        target = base / str(spec["index_path"])
        shutil.copy2(source, target)
        if _hash_file(target) == item.get("sha256"):
            restored.append(target.name)
    plan = _load_repair_plan(repair_id, base)
    plan["status"] = "rolled_back"
    plan["rolled_back_at_utc"] = _now()
    _atomic_write_json(_repair_plan_path(base, repair_id), plan)
    return restored


def _record_path_for_registry(base: Path, spec: Mapping[str, object], record_id: str) -> Path:
    record_dir = base / str(spec["record_directory"])
    suffix = str(spec["record_file_suffix"])
    if suffix == "_structure.json":
        return record_dir / f"{_safe_id(record_id)}{suffix}"
    return record_dir / f"{_safe_id(record_id)}{suffix}"


def _find_quarantine_source_path(base: Path, record_type: str, record_id: str) -> Path | None:
    mapping = {
        "chunk": base / "chunks" / f"{_safe_id(record_id)}.json",
        "proposal": base / "proposals" / f"{_safe_id(record_id)}.json",
        "citation": base / "citations" / f"{_safe_id(record_id)}.json",
        "page_diagnostics": base / "page_diagnostics" / f"{_safe_id(record_id)}.json",
        "structure_map": base / "structure_maps" / f"{_safe_id(record_id)}_structure.json",
        "source_document": base / "indexes" / f"{_safe_id(record_id)}.json",
    }
    return mapping.get(record_type) or next((path for path in mapping.values() if path.exists()), None)


def _list_execution_index_entries(root: Path) -> list[dict[str, object]]:
    rows = []
    for path in sorted((root / "corpus_execution").glob("*.json")):
        data = _read_json(path, default=None)
        if isinstance(data, dict):
            rows.append({"execution_id": data.get("execution_id"), "batch_id": data.get("batch_id"), "status": data.get("status"), "updated_at_utc": data.get("updated_at_utc"), "schema_version": data.get("schema_version")})
    return rows


def _list_receipt_index_entries(root: Path) -> list[dict[str, object]]:
    rows = []
    for path in sorted((root / "corpus_execution_receipts").glob("*.json")):
        data = _read_json(path, default=None)
        if isinstance(data, dict):
            rows.append({"receipt_id": data.get("receipt_id"), "batch_id": data.get("batch_id"), "document_id": data.get("document_id"), "action": data.get("action"), "status": data.get("status"), "classification": data.get("classification"), "completed_at_utc": data.get("completed_at_utc"), "idempotency_key": data.get("idempotency_key")})
    return rows


def _list_lock_index_entries(root: Path) -> list[dict[str, object]]:
    rows = []
    for path in sorted((root / "corpus_execution_locks").glob("*.json")):
        data = _read_json(path, default=None)
        if isinstance(data, dict):
            rows.append({"lock_id": data.get("lock_id"), "batch_id": data.get("batch_id"), "status": data.get("status"), "heartbeat_at_utc": data.get("heartbeat_at_utc")})
    return rows


def _list_checkpoint_index_entries(root: Path) -> list[dict[str, object]]:
    rows = []
    for path in sorted((root / "corpus_checkpoints").glob("*.json")):
        data = _read_json(path, default=None)
        if isinstance(data, dict):
            rows.append({"checkpoint_id": data.get("checkpoint_id"), "batch_id": data.get("batch_id"), "status": data.get("status"), "generation": data.get("generation"), "updated_at_utc": data.get("updated_at_utc")})
    return rows


def _list_repair_index_entries(root: Path) -> list[dict[str, object]]:
    rows = []
    for path in sorted((root / "corpus_repairs").glob("*.json")):
        data = _read_json(path, default=None)
        if isinstance(data, dict):
            rows.append({"repair_id": data.get("repair_id"), "status": data.get("status"), "created_at_utc": data.get("created_at_utc"), "backup_id": data.get("backup_id")})
    return rows


def _list_backup_index_entries(root: Path) -> list[dict[str, object]]:
    rows = []
    for path in sorted((root / "corpus_repair_backups").glob("*/*_manifest.json")):
        data = _read_json(path, default=None)
        if isinstance(data, dict):
            rows.append({"backup_id": data.get("backup_id"), "repair_id": data.get("repair_id"), "status": data.get("status"), "created_at_utc": data.get("created_at_utc")})
    return rows


def _list_quarantine_index_entries(root: Path) -> list[dict[str, object]]:
    rows = []
    for path in sorted((root / "corpus_quarantine").glob("quarantine_*.json")):
        data = _read_json(path, default=None)
        if isinstance(data, dict):
            rows.append({"quarantine_id": data.get("quarantine_id"), "record_type": data.get("record_type"), "record_id": data.get("record_id"), "created_at_utc": data.get("created_at_utc")})
    return rows


def _update_receipt_index(root: Path) -> None:
    _update_execution_index(root, "corpus_receipt_index.json", _list_receipt_index_entries(root))


def _update_execution_index(root: Path, filename: str, entries: list[dict[str, object]]) -> None:
    _atomic_write_json(root / "indexes" / filename, {"entries": entries, "updated_at_utc": _now()})


def _load_index_entries(path: Path) -> list[dict[str, object]]:
    data = _read_json(path, default={})
    entries = data.get("entries") if isinstance(data, dict) else []
    if not isinstance(entries, list):
        return []
    return [item for item in entries if isinstance(item, dict)]


def _load_repair_plan(repair_id: str, root: Path) -> dict[str, object]:
    path = _repair_plan_path(root, repair_id)
    data = _read_json(path, default=None)
    if not isinstance(data, dict):
        raise FileNotFoundError(str(path))
    return data


def _load_backup_manifest(backup_id: str, root: Path) -> dict[str, object] | None:
    path = root / "corpus_repair_backups" / backup_id / f"{backup_id}_manifest.json"
    data = _read_json(path, default=None)
    return data if isinstance(data, dict) else None


def _execution_recommendation(summary: Mapping[str, object], recovery: Mapping[str, object]) -> str:
    if summary.get("failed"):
        return "Review failures before retry."
    if summary.get("blocked"):
        return "Resolve dependencies before resume."
    if recovery.get("resume_available"):
        return "Resume batch to continue pending work."
    return "No further action required."


def _read_json(path: Path, *, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
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


def _hash_json_payload(payload: Mapping[str, object]) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _hash_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _sanitize_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    text = text.replace(str(Path.cwd()), "[workspace]")
    text = text.replace(str(SOURCE_DOCUMENT_ROOT), "[source-root]")
    return text.replace("\\", "/")


def _safe_id(value: object) -> str:
    return "".join(char if str(char).isalnum() or char in {"_", "-", "."} else "_" for char in str(value)) or "object"


def _timestamp_token() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value
