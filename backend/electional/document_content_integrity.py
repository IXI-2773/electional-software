"""Transaction journals, integrity scans, and recovery for document content curation writes."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from .document_content_curation import (
    _atomic_write_json,
    _ensure_document_content_curation_dirs,
    _now,
    _read_json,
    _safe_revision,
    _sanitize_public_report,
    _save_curation,
    load_document_content_curation,
)
from .document_content_history import (
    _fingerprint_summary,
    _history_record_to_overlay,
    _history_revision_path,
    _overlay_state_payload as _history_overlay_state_payload,
    _update_history_index,
    load_document_content_curation_revision,
    save_curation_history_snapshot,
)
from .document_content_map import load_document_content_map
from .document_content_rebase import _save_workspace, _update_workspace_index, _workspace_path
from .document_content_bulk import _bulk_plan_path, _save_bulk_plan, _update_bulk_index
from .source_documents import SOURCE_DOCUMENT_ROOT

TRANSACTION_SCHEMA_VERSION = "document_content_transaction_v1"
TRANSACTION_DIR = "document_content_transactions"
TRANSACTION_INDEX = "document_content_transaction_index.json"
RECOVERY_PLAN_DIR = "document_content_recovery_plans"
RECOVERY_STATUSES = {"prepared", "overlay_written", "history_written", "source_status_written", "indexes_reconciled", "committed", "recovery_required", "recovering", "recovered", "conflict", "failed", "abandoned", "unknown"}
MANUAL_REVIEW_REQUIRED = "manual_review_required"
_FAIL_STAGE_HOOK = None


def prepare_document_content_transaction(
    transaction_type: str,
    document_id: str,
    *,
    expected_previous_revision: int,
    expected_new_revision: int,
    base_content_map_fingerprint: Any,
    source_revision: Any,
    proposed_overlay_state: dict[str, Any],
    source_workflow_type: str | None = None,
    source_workflow_id: str | None = None,
    source_workflow_revision: int | None = None,
    preview_fingerprint: str | None = None,
    restore_source_revision: int | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_document_content_integrity_dirs(root)
    if not _safe_storage_identifier(document_id) or not _safe_storage_identifier(transaction_type):
        return {"document_id": document_id, "transaction_id": None, "status": "invalid", "transaction": None, "warnings": [], "blockers": ["unsafe_identifier"]}
    commit_fingerprint = _commit_fingerprint(
        transaction_type=transaction_type,
        document_id=document_id,
        expected_previous_revision=expected_previous_revision,
        expected_new_revision=expected_new_revision,
        proposed_overlay_state=proposed_overlay_state,
        source_workflow_type=source_workflow_type,
        source_workflow_id=source_workflow_id,
        source_workflow_revision=source_workflow_revision,
        preview_fingerprint=preview_fingerprint,
        restore_source_revision=restore_source_revision,
    )
    transaction_id = _transaction_id(document_id, transaction_type, commit_fingerprint, source_workflow_id)
    path = _transaction_path(base, document_id, transaction_id)
    existing = _read_json(path)
    if isinstance(existing, dict):
        if str(existing.get("commit_fingerprint") or "") != commit_fingerprint:
            return {"document_id": document_id, "transaction_id": transaction_id, "status": "conflict", "transaction": existing, "warnings": [], "blockers": ["transaction_intent_conflict"]}
        return {"document_id": document_id, "transaction_id": transaction_id, "status": existing.get("transaction_status", "unknown"), "transaction": existing, "warnings": [], "blockers": []}
    transaction = {
        "schema_version": TRANSACTION_SCHEMA_VERSION,
        "transaction_id": transaction_id,
        "transaction_type": transaction_type,
        "document_id": document_id,
        "source_workflow_type": source_workflow_type,
        "source_workflow_id": source_workflow_id,
        "source_workflow_revision": source_workflow_revision,
        "expected_previous_curation_revision": expected_previous_revision,
        "expected_new_curation_revision": expected_new_revision,
        "base_content_map_fingerprint": base_content_map_fingerprint,
        "source_revision": source_revision,
        "preview_fingerprint": preview_fingerprint,
        "restore_source_revision": restore_source_revision,
        "commit_fingerprint": commit_fingerprint,
        "proposed_overlay_state": copy.deepcopy(proposed_overlay_state),
        "created_at_utc": _now(),
        "updated_at_utc": _now(),
        "transaction_status": "prepared",
        "completed_checkpoints": [],
        "pending_checkpoints": _required_checkpoints(transaction_type),
        "failure_summary": [],
        "recovery_attempts": 0,
        "provenance_summary": {
            "workflow_id": source_workflow_id,
            "workflow_revision": source_workflow_revision,
            "preview_fingerprint": preview_fingerprint,
            "restore_source_revision": restore_source_revision,
        },
        "committed_revision": None,
    }
    _atomic_write_json(path, transaction)
    _update_transaction_index(base)
    return {"document_id": document_id, "transaction_id": transaction_id, "status": "prepared", "transaction": transaction, "warnings": [], "blockers": []}


def load_document_content_transaction(document_id: str, transaction_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_integrity_dirs(root)
    if not _safe_storage_identifier(document_id) or not _safe_storage_identifier(transaction_id):
        return {"document_id": document_id, "transaction_id": transaction_id, "status": "invalid", "transaction": None, "warnings": [], "blockers": ["unsafe_identifier"]}
    payload = _read_json(_transaction_path(base, document_id, transaction_id))
    if not isinstance(payload, dict):
        return {"document_id": document_id, "transaction_id": transaction_id, "status": "not_found", "transaction": None, "warnings": [], "blockers": ["transaction_not_found"]}
    if str(payload.get("document_id") or "") != document_id:
        return {"document_id": document_id, "transaction_id": transaction_id, "status": "conflict", "transaction": payload, "warnings": [], "blockers": ["document_id_mismatch"]}
    return {"document_id": document_id, "transaction_id": transaction_id, "status": "loaded", "transaction": payload, "warnings": [], "blockers": []}


def list_document_content_transactions(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_integrity_dirs(root)
    if not _safe_storage_identifier(document_id):
        return {"document_id": document_id, "count": 0, "items": [], "warnings": ["unsafe_identifier"]}
    folder = base / TRANSACTION_DIR / document_id
    items = []
    warnings = []
    if folder.exists():
        for path in sorted(folder.glob("*.json")):
            payload = _read_json(path)
            if not isinstance(payload, dict):
                warnings.append(f"corrupt_transaction:{path.stem}")
                continue
            items.append(_transaction_summary(payload))
    return {"document_id": document_id, "count": len(items), "items": items, "warnings": warnings}


def get_document_content_transaction_status(document_id: str, transaction_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    loaded = load_document_content_transaction(document_id, transaction_id, root=root)
    if loaded["status"] != "loaded":
        return {"document_id": document_id, "transaction_id": transaction_id, "status": loaded.get("status"), "warnings": loaded.get("warnings", []), "blockers": loaded.get("blockers", [])}
    verified = _verify_transaction(loaded["transaction"] or {}, _ensure_document_content_integrity_dirs(root))
    return {
        "document_id": document_id,
        "transaction_id": transaction_id,
        "status": verified.get("transaction_status", "unknown"),
        "warnings": verified.get("warnings", []),
        "blockers": verified.get("blockers", []),
        "completed_checkpoints": verified.get("completed_checkpoints", []),
        "pending_checkpoints": verified.get("pending_checkpoints", []),
    }


def record_document_content_transaction_checkpoint(document_id: str, transaction_id: str, checkpoint: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_integrity_dirs(root)
    if not _safe_storage_identifier(document_id) or not _safe_storage_identifier(transaction_id):
        return {"document_id": document_id, "transaction_id": transaction_id, "status": "invalid", "transaction": None, "warnings": [], "blockers": ["unsafe_identifier"]}
    loaded = load_document_content_transaction(document_id, transaction_id, root=base)
    if loaded["status"] != "loaded":
        return loaded
    transaction = loaded["transaction"] or {}
    completed = list(dict.fromkeys([*(transaction.get("completed_checkpoints") or []), checkpoint]))
    pending = [item for item in _required_checkpoints(transaction.get("transaction_type")) if item not in completed]
    transaction["completed_checkpoints"] = completed
    transaction["pending_checkpoints"] = pending
    transaction["transaction_status"] = checkpoint if checkpoint in RECOVERY_STATUSES else transaction.get("transaction_status", "prepared")
    transaction["updated_at_utc"] = _now()
    _save_transaction(base, transaction)
    return {"document_id": document_id, "transaction_id": transaction_id, "status": transaction.get("transaction_status"), "transaction": transaction, "warnings": [], "blockers": []}


def finalize_document_content_transaction(
    document_id: str,
    transaction_id: str,
    status: str = "committed",
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_document_content_integrity_dirs(root)
    if not _safe_storage_identifier(document_id) or not _safe_storage_identifier(transaction_id):
        return {"document_id": document_id, "transaction_id": transaction_id, "status": "invalid", "warnings": [], "blockers": ["unsafe_identifier"]}
    loaded = load_document_content_transaction(document_id, transaction_id, root=base)
    if loaded["status"] != "loaded":
        return loaded
    transaction = _verify_transaction(loaded["transaction"] or {}, base)
    if status not in {"committed", "recovered", "failed", "conflict", "abandoned", "recovering"}:
        return {"document_id": document_id, "transaction_id": transaction_id, "status": "invalid", "warnings": [], "blockers": ["invalid_transaction_status"]}
    if status in {"committed", "recovered"} and transaction.get("pending_checkpoints"):
        return {
            "document_id": document_id,
            "transaction_id": transaction_id,
            "status": "conflict",
            "transaction": transaction,
            "warnings": [],
            "blockers": ["transaction_checkpoints_incomplete"],
        }
    transaction["transaction_status"] = status
    if status in {"committed", "recovered"}:
        transaction["committed_revision"] = transaction.get("expected_new_curation_revision")
    transaction["updated_at_utc"] = _now()
    _save_transaction(base, transaction)
    return {"document_id": document_id, "transaction_id": transaction_id, "status": status, "transaction": transaction, "warnings": [], "blockers": []}


def abandon_document_content_transaction(
    document_id: str,
    transaction_id: str,
    reason: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_document_content_integrity_dirs(root)
    if not _safe_storage_identifier(document_id) or not _safe_storage_identifier(transaction_id):
        return {"document_id": document_id, "transaction_id": transaction_id, "status": "invalid", "warnings": [], "blockers": ["unsafe_identifier"]}
    loaded = load_document_content_transaction(document_id, transaction_id, root=base)
    if loaded["status"] != "loaded":
        return loaded
    transaction = loaded["transaction"] or {}
    verified = _verify_transaction(transaction, base)
    if verified.get("transaction_status") == "abandoned":
        return {"document_id": document_id, "transaction_id": transaction_id, "status": "abandoned", "transaction": verified, "warnings": [], "blockers": []}
    if verified.get("completed_checkpoints"):
        return {"document_id": document_id, "transaction_id": transaction_id, "status": "conflict", "transaction": verified, "warnings": [], "blockers": ["authoritative_mutation_detected"]}
    verified["transaction_status"] = "abandoned"
    verified["abandoned_at_utc"] = _now()
    clean_reason = " ".join(str(reason or "").split()).strip()
    if clean_reason:
        verified["abandon_reason"] = clean_reason[:200]
    verified["updated_at_utc"] = _now()
    _save_transaction(base, verified)
    return {"document_id": document_id, "transaction_id": transaction_id, "status": "abandoned", "transaction": verified, "warnings": [], "blockers": []}


def scan_document_content_integrity(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_integrity_dirs(root)
    issues: list[dict[str, Any]] = []
    transactions = list_document_content_transactions(document_id, root=base).get("items", [])
    tx_folder = base / TRANSACTION_DIR / document_id
    for item in transactions:
        payload = _read_json(tx_folder / f"{item['transaction_id']}.json")
        if not isinstance(payload, dict):
            continue
        verified = _verify_transaction(payload, base)
        if verified.get("transaction_status") in {"recovery_required", "conflict", "failed"}:
            issues.append(
                _issue(
                    "transaction_incomplete" if verified.get("transaction_status") == "recovery_required" else "transaction_conflict",
                    "high" if verified.get("transaction_status") == "recovery_required" else "critical",
                    document_id,
                    transaction_id=payload.get("transaction_id"),
                    revision=payload.get("expected_new_curation_revision"),
                    workflow_type=payload.get("source_workflow_type"),
                    workflow_id=payload.get("source_workflow_id"),
                    current_state_summary=verified.get("transaction_status"),
                    expected_state_summary="committed",
                    recoverability="recoverable" if verified.get("transaction_status") == "recovery_required" else "manual_review_required",
                    recommended_safe_action="build_recovery_plan" if verified.get("transaction_status") == "recovery_required" else "manual_review",
                    blockers=verified.get("blockers", []),
                    warnings=verified.get("warnings", []),
                )
            )
        elif verified.get("transaction_status") in {"overlay_written", "history_written", "source_status_written", "indexes_reconciled"}:
            issues.append(
                _issue(
                    f"{verified.get('transaction_status')}_without_finalization",
                    "high",
                    document_id,
                    transaction_id=payload.get("transaction_id"),
                    revision=payload.get("expected_new_curation_revision"),
                    workflow_type=payload.get("source_workflow_type"),
                    workflow_id=payload.get("source_workflow_id"),
                    current_state_summary=verified.get("transaction_status"),
                    expected_state_summary="committed",
                    recoverability="recoverable",
                    recommended_safe_action="build_recovery_plan",
                    blockers=verified.get("blockers", []),
                    warnings=verified.get("warnings", []),
                )
            )
    issues.extend(_history_record_issues(document_id, base))
    issues.extend(_index_issues(document_id, base))
    issues.extend(_workflow_issues(document_id, base))
    issues.sort(key=lambda item: (_severity_rank(item.get("severity")), item.get("issue_type"), item.get("issue_id")))
    return {
        "document_id": document_id,
        "status": "ready",
        "issue_count": len(issues),
        "issues": issues,
        "severity_counts": _severity_counts(issues),
        "scan_fingerprint": _scan_fingerprint(issues),
        "warnings": [],
        "blockers": [],
    }


def create_document_content_recovery_plan(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_integrity_dirs(root)
    if not _safe_storage_identifier(document_id):
        return {"document_id": document_id, "plan_id": None, "status": "invalid", "plan": None, "warnings": [], "blockers": ["unsafe_identifier"]}
    scan = scan_document_content_integrity(document_id, root=base)
    actions: list[dict[str, Any]] = []
    blockers: list[str] = []
    for issue in scan.get("issues", []):
        transaction_id = issue.get("affected_transaction_id")
        issue_type = issue.get("issue_type")
        if issue.get("recoverability") == MANUAL_REVIEW_REQUIRED:
            blockers.append(f"manual_review:{issue_type}")
        if transaction_id and issue.get("recoverability") == "recoverable":
            loaded = load_document_content_transaction(document_id, transaction_id, root=base)
            tx = loaded.get("transaction") or {}
            verified = _verify_transaction(tx, base) if isinstance(tx, dict) else {}
            completed = set(verified.get("completed_checkpoints", []))
            required = set(_required_checkpoints(tx.get("transaction_type")))
            if "overlay_written" in completed and "history_written" in required and "history_written" not in completed:
                actions.append({"action": "write_missing_history_if_safe", "transaction_id": transaction_id})
            if "history_written" in completed and "source_status_written" in required and "source_status_written" not in completed:
                actions.append({"action": "complete_workflow_status_if_safe", "transaction_id": transaction_id})
            actions.append({"action": "mark_transaction_committed_if_safe", "transaction_id": transaction_id})
        if issue_type in {"history_index_missing_entry", "history_index_stale_entry"}:
            actions.append({"action": "rebuild_history_index", "transaction_id": None})
        if issue_type == "bulk_index_missing_entry":
            actions.append({"action": "rebuild_bulk_index", "transaction_id": None})
        if issue_type == "rebase_index_missing_entry":
            actions.append({"action": "rebuild_rebase_index", "transaction_id": None})
        if issue_type == "transaction_index_missing_entry":
            actions.append({"action": "rebuild_transaction_index", "transaction_id": None})
    actions = _unique_actions(actions)
    plan_id = _recovery_plan_id(document_id, scan.get("scan_fingerprint"), actions)
    status = "ready" if actions and not blockers else MANUAL_REVIEW_REQUIRED if blockers else "ready"
    plan = {
        "schema_version": TRANSACTION_SCHEMA_VERSION,
        "plan_id": plan_id,
        "document_id": document_id,
        "source_integrity_scan_fingerprint": scan.get("scan_fingerprint"),
        "issue_ids": [item.get("issue_id") for item in scan.get("issues", [])],
        "planned_actions": actions,
        "expected_checkpoints_after_recovery": ["committed", "indexes_reconciled"],
        "blockers": blockers,
        "warnings": [],
        "dry_run": True,
        "created_at_utc": _now(),
        "updated_at_utc": _now(),
        "status": status,
    }
    _atomic_write_json(_recovery_plan_path(base, document_id, plan_id), plan)
    return {"document_id": document_id, "plan_id": plan_id, "status": status, "plan": plan, "warnings": [], "blockers": blockers}


def load_document_content_recovery_plan(document_id: str, plan_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_integrity_dirs(root)
    if not _safe_storage_identifier(document_id) or not _safe_storage_identifier(plan_id):
        return {"document_id": document_id, "plan_id": plan_id, "status": "invalid", "plan": None, "warnings": [], "blockers": ["unsafe_identifier"]}
    payload = _read_json(_recovery_plan_path(base, document_id, plan_id))
    if not isinstance(payload, dict):
        return {"document_id": document_id, "plan_id": plan_id, "status": "not_found", "plan": None, "warnings": [], "blockers": ["recovery_plan_not_found"]}
    blockers = _validate_recovery_plan_payload(payload, document_id, plan_id)
    if blockers:
        return {"document_id": document_id, "plan_id": plan_id, "status": "invalid", "plan": payload, "warnings": [], "blockers": blockers}
    return {"document_id": document_id, "plan_id": plan_id, "status": "loaded", "plan": payload, "warnings": [], "blockers": []}


def apply_document_content_recovery_plan(document_id: str, plan_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_integrity_dirs(root)
    if not _safe_storage_identifier(document_id) or not _safe_storage_identifier(plan_id):
        return {"document_id": document_id, "plan_id": plan_id, "status": "invalid", "warnings": [], "blockers": ["unsafe_identifier"]}
    loaded = load_document_content_recovery_plan(document_id, plan_id, root=base)
    if loaded["status"] != "loaded":
        return loaded
    plan = loaded["plan"] or {}
    blockers = _validate_recovery_plan_payload(plan, document_id, plan_id)
    if blockers:
        plan["status"] = "invalid"
        plan["blockers"] = blockers
        plan["updated_at_utc"] = _now()
        _atomic_write_json(_recovery_plan_path(base, document_id, plan_id), plan)
        return {"document_id": document_id, "plan_id": plan_id, "status": "invalid", "warnings": [], "blockers": blockers}
    if plan.get("status") == MANUAL_REVIEW_REQUIRED:
        return {"document_id": document_id, "plan_id": plan_id, "status": MANUAL_REVIEW_REQUIRED, "warnings": [], "blockers": list(plan.get("blockers") or [])}
    current_scan = scan_document_content_integrity(document_id, root=base)
    if plan.get("source_integrity_scan_fingerprint") != current_scan.get("scan_fingerprint"):
        plan["status"] = "stale"
        plan["updated_at_utc"] = _now()
        _atomic_write_json(_recovery_plan_path(base, document_id, plan_id), plan)
        return {"document_id": document_id, "plan_id": plan_id, "status": "stale", "warnings": [], "blockers": ["recovery_plan_stale"]}
    plan["status"] = "recovering"
    plan["updated_at_utc"] = _now()
    _atomic_write_json(_recovery_plan_path(base, document_id, plan_id), plan)
    results = []
    for action in plan.get("planned_actions", []):
        results.append(_apply_recovery_action(document_id, action, base))
    post_scan = scan_document_content_integrity(document_id, root=base)
    plan["results"] = results
    plan["updated_at_utc"] = _now()
    if any(result.get("status") == "conflict" for result in results):
        plan["status"] = MANUAL_REVIEW_REQUIRED
        plan["blockers"] = ["manual_review_required"]
        _atomic_write_json(_recovery_plan_path(base, document_id, plan_id), plan)
        return {"document_id": document_id, "plan_id": plan_id, "status": MANUAL_REVIEW_REQUIRED, "results": results, "warnings": [], "blockers": ["manual_review_required"], "scan": post_scan}
    if post_scan.get("issue_count", 0) > 0 and any(item.get("recoverability") == MANUAL_REVIEW_REQUIRED for item in post_scan.get("issues", [])):
        plan["status"] = MANUAL_REVIEW_REQUIRED
        plan["blockers"] = ["manual_review_required"]
        _atomic_write_json(_recovery_plan_path(base, document_id, plan_id), plan)
        return {"document_id": document_id, "plan_id": plan_id, "status": MANUAL_REVIEW_REQUIRED, "results": results, "warnings": [], "blockers": ["manual_review_required"], "scan": post_scan}
    plan["status"] = "recovered"
    plan["blockers"] = []
    _atomic_write_json(_recovery_plan_path(base, document_id, plan_id), plan)
    return {"document_id": document_id, "plan_id": plan_id, "status": "recovered", "results": results, "warnings": [], "blockers": [], "scan": post_scan}


def rebuild_document_content_indexes(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_integrity_dirs(root)
    _update_history_index(base)
    _update_workspace_index(base)
    _update_bulk_index(base)
    _update_transaction_index(base)
    return {"document_id": document_id, "status": "rebuilt", "warnings": [], "blockers": []}


def format_document_content_transaction_report(document_id: str, transaction_id: str, public_safe: bool = True, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> str:
    status = get_document_content_transaction_status(document_id, transaction_id, root=root)
    lines = [
        "Document Content Transaction Report",
        "",
        f"Document: {document_id}",
        f"Transaction: {transaction_id}",
        f"Status: {status.get('status')}",
        f"Completed Checkpoints: {', '.join(status.get('completed_checkpoints', [])) or 'none'}",
        f"Pending Checkpoints: {', '.join(status.get('pending_checkpoints', [])) or 'none'}",
        f"Blockers: {', '.join(status.get('blockers', [])) or 'none'}",
        f"Warnings: {', '.join(status.get('warnings', [])) or 'none'}",
    ]
    text = "\n".join(lines)
    return _sanitize_public_report(text) if public_safe else text


def format_document_content_integrity_report(document_id: str, public_safe: bool = True, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> str:
    scan = scan_document_content_integrity(document_id, root=root)
    counts = scan.get("severity_counts", {})
    issue_counts: dict[str, int] = {}
    for item in scan.get("issues", []):
        if isinstance(item, dict):
            issue_type = str(item.get("issue_type") or "unknown")
            issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1
    lines = [
        "Document Content Integrity Report",
        "",
        f"Document: {document_id}",
        f"Issue Count: {scan.get('issue_count', 0)}",
        f"Critical: {counts.get('critical', 0)}",
        f"High: {counts.get('high', 0)}",
        f"Medium: {counts.get('medium', 0)}",
        f"Low: {counts.get('low', 0)}",
        f"Info: {counts.get('info', 0)}",
        f"Manual Review Required: {len([item for item in scan.get('issues', []) if isinstance(item, dict) and item.get('recoverability') == 'manual_review_required'])}",
        "Issue Types: " + (", ".join(f"{key}={issue_counts[key]}" for key in sorted(issue_counts)) or "none"),
    ]
    text = "\n".join(lines)
    return _sanitize_public_report(text) if public_safe else text


def format_document_content_recovery_report(document_id: str, plan_id: str, public_safe: bool = True, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> str:
    loaded = load_document_content_recovery_plan(document_id, plan_id, root=root)
    if loaded["status"] != "loaded":
        text = f"Document Content Recovery Report\n\nDocument: {document_id}\nPlan: {plan_id}\nStatus: {loaded.get('status')}\nBlockers: {', '.join(loaded.get('blockers', [])) or 'none'}"
        return _sanitize_public_report(text) if public_safe else text
    plan = loaded["plan"] or {}
    lines = [
        "Document Content Recovery Report",
        "",
        f"Document: {document_id}",
        f"Plan: {plan_id}",
        f"Status: {plan.get('status')}",
        f"Action Count: {len(plan.get('planned_actions', []))}",
        f"Dry Run: {bool(plan.get('dry_run', True))}",
        f"Blockers: {', '.join(plan.get('blockers', [])) or 'none'}",
    ]
    text = "\n".join(lines)
    return _sanitize_public_report(text) if public_safe else text


def _apply_recovery_action(document_id: str, action: dict[str, Any], root: Path) -> dict[str, Any]:
    kind = action.get("action")
    transaction_id = action.get("transaction_id")
    if kind == "rebuild_history_index":
        _update_history_index(root)
        return {"action": kind, "status": "applied"}
    if kind == "rebuild_bulk_index":
        _update_bulk_index(root)
        return {"action": kind, "status": "applied"}
    if kind == "rebuild_rebase_index":
        _update_workspace_index(root)
        return {"action": kind, "status": "applied"}
    if kind == "rebuild_transaction_index":
        _update_transaction_index(root)
        return {"action": kind, "status": "applied"}
    loaded = load_document_content_transaction(document_id, transaction_id, root=root)
    if loaded["status"] != "loaded":
        return {"action": kind, "status": "blocked"}
    tx = loaded["transaction"] or {}
    verified = _verify_transaction(tx, root)
    if kind == "write_missing_history_if_safe":
        if "overlay_written" not in verified.get("completed_checkpoints", []):
            return {"action": kind, "status": "blocked"}
        current = load_document_content_curation(document_id, root=root).get("curation")
        if not isinstance(current, dict) or not _overlay_matches_transaction(current, tx):
            return {"action": kind, "status": "conflict"}
        result = save_curation_history_snapshot(document_id, current, root=root)
        return {"action": kind, "status": "applied" if result.get("status") in {"saved", "unchanged"} else result.get("status")}
    if kind == "complete_workflow_status_if_safe":
        if "history_written" not in verified.get("completed_checkpoints", []):
            return {"action": kind, "status": "blocked"}
        return _complete_workflow_status(tx, root)
    if kind == "mark_transaction_committed_if_safe":
        verified = _verify_transaction(tx, root)
        if verified.get("transaction_status") not in {"indexes_reconciled", "source_status_written", "history_written", "overlay_written", "recovery_required", "committed", "recovered"}:
            return {"action": kind, "status": "blocked"}
        verified["transaction_status"] = "recovered" if tx.get("transaction_status") not in {"committed", "recovered"} else tx.get("transaction_status")
        verified["recovery_attempts"] = int(tx.get("recovery_attempts") or 0) + 1
        verified["committed_revision"] = verified.get("expected_new_curation_revision")
        verified["updated_at_utc"] = _now()
        _save_transaction(root, verified)
        return {"action": kind, "status": "applied"}
    return {"action": kind, "status": "ignored"}


def _complete_workflow_status(transaction: dict[str, Any], root: Path) -> dict[str, Any]:
    workflow_type = transaction.get("source_workflow_type")
    workflow_id = str(transaction.get("source_workflow_id") or "")
    revision = transaction.get("expected_new_curation_revision")
    overlay = load_document_content_curation(transaction.get("document_id"), root=root).get("curation") or {}
    if workflow_type == "bulk_commit":
        payload = _read_json(_bulk_plan_path(root, transaction.get("document_id"), workflow_id))
        if isinstance(payload, dict):
            payload["status"] = "committed"
            payload["commit_metadata"] = {"committed_at_utc": _now(), "committed_revision": revision}
            _save_bulk_plan(root, payload)
            return {"action": "complete_workflow_status_if_safe", "status": "applied"}
    if workflow_type == "rebase_commit":
        payload = _read_json(_workspace_path(root, transaction.get("document_id"), workflow_id))
        if isinstance(payload, dict):
            payload["status"] = "committed"
            payload["commit_provenance"] = dict(overlay.get("rebase_provenance") or {})
            payload["committed_revision"] = revision
            _save_workspace(root, payload)
            return {"action": "complete_workflow_status_if_safe", "status": "applied"}
    return {"action": "complete_workflow_status_if_safe", "status": "ignored"}


def _verify_transaction(transaction: dict[str, Any], root: Path) -> dict[str, Any]:
    tx = copy.deepcopy(transaction)
    doc_id = str(tx.get("document_id") or "")
    current = load_document_content_curation(doc_id, root=root).get("curation")
    completed = []
    blockers = []
    warnings = []
    if str(tx.get("schema_version") or "") != TRANSACTION_SCHEMA_VERSION:
        tx["transaction_status"] = "unknown"
        tx["blockers"] = ["transaction_schema_unknown"]
        return tx
    if isinstance(current, dict) and _overlay_matches_transaction(current, tx):
        completed.append("overlay_written")
    history_path = _history_revision_path(root, doc_id, _safe_revision(tx.get("expected_new_curation_revision")))
    history = _read_json(history_path)
    if isinstance(history, dict) and _history_matches_transaction(history, tx):
        completed.append("history_written")
    source_status = _workflow_status_matches_transaction(tx, root, current if isinstance(current, dict) else {})
    if source_status:
        completed.append("source_status_written")
    if _indexes_reconciled(doc_id, tx, root):
        completed.append("indexes_reconciled")
    required = _required_checkpoints(tx.get("transaction_type"))
    pending = [item for item in required if item not in completed]
    tx["completed_checkpoints"] = completed
    tx["pending_checkpoints"] = pending
    stored_status = str(tx.get("transaction_status") or "").strip() or "prepared"
    if stored_status == "abandoned":
        tx["transaction_status"] = "abandoned" if not completed else "conflict"
    elif stored_status == "recovering":
        tx["transaction_status"] = "recovering"
    elif stored_status == "failed":
        tx["transaction_status"] = "failed"
    elif not completed:
        tx["transaction_status"] = "prepared"
    elif not pending:
        tx["committed_revision"] = tx.get("expected_new_curation_revision")
        if stored_status in {"committed", "recovered"}:
            tx["transaction_status"] = stored_status
        elif stored_status in {"prepared", "overlay_written", "history_written", "source_status_written", "indexes_reconciled"}:
            tx["transaction_status"] = stored_status if stored_status != "prepared" else "indexes_reconciled"
        else:
            tx["transaction_status"] = "indexes_reconciled"
    elif completed == ["overlay_written"]:
        tx["transaction_status"] = "overlay_written"
    elif set(completed) == {"overlay_written", "history_written"}:
        tx["transaction_status"] = "history_written"
    elif "source_status_written" in completed and "indexes_reconciled" not in completed:
        tx["transaction_status"] = "source_status_written"
    elif "indexes_reconciled" in completed:
        tx["transaction_status"] = "indexes_reconciled"
    elif "overlay_written" in completed:
        tx["transaction_status"] = "recovery_required"
    else:
        tx["transaction_status"] = "unknown"
    tx["warnings"] = warnings
    tx["blockers"] = blockers
    return tx


def _overlay_matches_transaction(overlay: dict[str, Any], transaction: dict[str, Any]) -> bool:
    return (
        str(overlay.get("document_id") or "") == str(transaction.get("document_id") or "")
        and _safe_revision(overlay.get("curation_revision")) == _safe_revision(transaction.get("expected_new_curation_revision"))
        and _history_overlay_state_payload(overlay) == _history_overlay_state_payload(transaction.get("proposed_overlay_state") or {})
    )


def _history_matches_transaction(history: dict[str, Any], transaction: dict[str, Any]) -> bool:
    overlay = _history_record_to_overlay(history)
    return _overlay_matches_transaction(overlay, transaction)


def _workflow_status_matches_transaction(transaction: dict[str, Any], root: Path, overlay: dict[str, Any]) -> bool:
    workflow_type = transaction.get("source_workflow_type")
    workflow_id = str(transaction.get("source_workflow_id") or "")
    revision = _safe_revision(transaction.get("expected_new_curation_revision"))
    if workflow_type == "bulk_commit":
        if not _safe_storage_identifier(workflow_id):
            return False
        payload = _read_json(_bulk_plan_path(root, transaction.get("document_id"), workflow_id))
        return isinstance(payload, dict) and payload.get("status") == "committed" and _safe_revision((payload.get("commit_metadata") or {}).get("committed_revision")) == revision
    if workflow_type == "rebase_commit":
        if not _safe_storage_identifier(workflow_id):
            return False
        payload = _read_json(_workspace_path(root, transaction.get("document_id"), workflow_id))
        return isinstance(payload, dict) and payload.get("status") == "committed" and _safe_revision(payload.get("committed_revision")) == revision
    return False


def _indexes_reconciled(document_id: str, transaction: dict[str, Any], root: Path) -> bool:
    revision = _safe_revision(transaction.get("expected_new_curation_revision"))
    history_index = _read_json(root / "indexes" / "document_content_curation_history_index.json") or {}
    tx_index = _read_json(root / "indexes" / TRANSACTION_INDEX) or {}
    history_entries = history_index.get("entries", []) if isinstance(history_index.get("entries"), list) else []
    tx_entries = tx_index.get("entries", []) if isinstance(tx_index.get("entries"), list) else []
    history_ok = any(entry.get("document_id") == document_id and _safe_revision(entry.get("curation_revision")) == revision for entry in history_entries if isinstance(entry, dict))
    tx_ok = any(entry.get("document_id") == document_id and entry.get("transaction_id") == transaction.get("transaction_id") for entry in tx_entries if isinstance(entry, dict))
    if transaction.get("source_workflow_type") == "bulk_commit":
        bulk_index = _read_json(root / "indexes" / "document_content_bulk_index.json") or {}
        bulk_entries = bulk_index.get("entries", []) if isinstance(bulk_index.get("entries"), list) else []
        return history_ok and tx_ok and any(entry.get("document_id") == document_id and entry.get("batch_id") == transaction.get("source_workflow_id") for entry in bulk_entries if isinstance(entry, dict))
    if transaction.get("source_workflow_type") == "rebase_commit":
        rebase_index = _read_json(root / "indexes" / "document_content_curation_rebase_index.json") or {}
        rebase_entries = rebase_index.get("entries", []) if isinstance(rebase_index.get("entries"), list) else []
        return history_ok and tx_ok and any(entry.get("document_id") == document_id and entry.get("workspace_id") == transaction.get("source_workflow_id") for entry in rebase_entries if isinstance(entry, dict))
    return history_ok and tx_ok


def _history_record_issues(document_id: str, root: Path) -> list[dict[str, Any]]:
    issues = []
    current = load_document_content_curation(document_id, root=root).get("curation") or {}
    current_revision = _safe_revision(current.get("curation_revision"))
    highest_history_revision = 0
    by_claimed_revision: dict[int, list[dict[str, Any]]] = {}
    history_dir = root / "document_content_curation_history" / document_id
    if history_dir.exists():
        for path in sorted(history_dir.glob("*.json")):
            payload = _read_json(path)
            if not isinstance(payload, dict):
                continue
            claimed_revision = _safe_revision(payload.get("curation_revision"))
            highest_history_revision = max(highest_history_revision, claimed_revision)
            by_claimed_revision.setdefault(claimed_revision, []).append({"path": path.stem, "payload": payload})
    if current_revision and highest_history_revision > current_revision:
        issues.append(
            _issue(
                "overlay_revision_behind_history",
                "critical",
                document_id,
                revision=current_revision,
                current_state_summary=f"overlay_revision={current_revision}",
                expected_state_summary=f"history_revision={highest_history_revision}",
                recoverability=MANUAL_REVIEW_REQUIRED,
                recommended_safe_action="manual_review",
                blockers=["overlay_revision_behind_history"],
                warnings=[],
            )
        )
    for revision, records in by_claimed_revision.items():
        if len(records) < 2:
            continue
        fingerprints = {
            _commit_fingerprint(
                overlay=_history_overlay_state_payload(_history_record_to_overlay(record["payload"])),
                provenance=(record["payload"].get("provenance") or {}),
                fingerprint=record["payload"].get("content_fingerprint"),
            )
            for record in records
        }
        if len(fingerprints) > 1:
            issues.append(
                _issue(
                    "duplicate_conflicting_history_revision",
                    "critical",
                    document_id,
                    revision=revision,
                    current_state_summary="duplicate_history_revision",
                    expected_state_summary="single_authoritative_revision",
                    recoverability=MANUAL_REVIEW_REQUIRED,
                    recommended_safe_action="manual_review",
                    blockers=[f"history_records:{','.join(sorted(record['path'] for record in records))}"],
                    warnings=[],
                )
            )
    return issues


def _index_issues(document_id: str, root: Path) -> list[dict[str, Any]]:
    issues = []
    history_dir = root / "document_content_curation_history" / document_id
    history_files = sorted(path.stem for path in history_dir.glob("*.json")) if history_dir.exists() else []
    history_index = _read_json(root / "indexes" / "document_content_curation_history_index.json") or {}
    indexed_history = sorted(str(entry.get("curation_revision")) for entry in history_index.get("entries", []) if isinstance(entry, dict) and entry.get("document_id") == document_id)
    for revision in history_files:
        if revision not in indexed_history:
            issues.append(_issue("history_index_missing_entry", "medium", document_id, revision=int(revision), current_state_summary="snapshot_present", expected_state_summary="indexed", recoverability="recoverable", recommended_safe_action="rebuild_history_index", blockers=[], warnings=[]))
    for revision in indexed_history:
        if revision not in history_files:
            issues.append(_issue("history_index_stale_entry", "medium", document_id, revision=int(revision), current_state_summary="index_present", expected_state_summary="snapshot_present", recoverability="recoverable", recommended_safe_action="rebuild_history_index", blockers=[], warnings=[]))
    tx_index = _read_json(root / "indexes" / TRANSACTION_INDEX) or {}
    tx_entries = tx_index.get("entries", []) if isinstance(tx_index.get("entries"), list) else []
    tx_dir = root / TRANSACTION_DIR / document_id
    tx_files = sorted(path.stem for path in tx_dir.glob("*.json")) if tx_dir.exists() else []
    indexed_txs = sorted(str(entry.get("transaction_id")) for entry in tx_entries if isinstance(entry, dict) and entry.get("document_id") == document_id)
    for txid in tx_files:
        if txid not in indexed_txs:
            issues.append(_issue("transaction_index_missing_entry", "low", document_id, transaction_id=txid, current_state_summary="transaction_present", expected_state_summary="indexed", recoverability="recoverable", recommended_safe_action="rebuild_transaction_index", blockers=[], warnings=[]))
    bulk_index = _read_json(root / "indexes" / "document_content_bulk_index.json") or {}
    bulk_entries = bulk_index.get("entries", []) if isinstance(bulk_index.get("entries"), list) else []
    bulk_dir = root / "document_content_bulk" / document_id
    bulk_files = sorted(path.stem for path in bulk_dir.glob("*.json")) if bulk_dir.exists() else []
    indexed_bulk = sorted(str(entry.get("batch_id")) for entry in bulk_entries if isinstance(entry, dict) and entry.get("document_id") == document_id)
    for batch_id in bulk_files:
        if batch_id not in indexed_bulk:
            issues.append(_issue("bulk_index_missing_entry", "medium", document_id, workflow_type="bulk_commit", workflow_id=batch_id, current_state_summary="batch_present", expected_state_summary="indexed", recoverability="recoverable", recommended_safe_action="rebuild_bulk_index", blockers=[], warnings=[]))
    rebase_index = _read_json(root / "indexes" / "document_content_curation_rebase_index.json") or {}
    rebase_entries = rebase_index.get("entries", []) if isinstance(rebase_index.get("entries"), list) else []
    rebase_dir = root / "document_content_curation_rebase" / document_id
    rebase_files = sorted(path.stem for path in rebase_dir.glob("*.json")) if rebase_dir.exists() else []
    indexed_rebase = sorted(str(entry.get("workspace_id")) for entry in rebase_entries if isinstance(entry, dict) and entry.get("document_id") == document_id)
    for workspace_id in rebase_files:
        if workspace_id not in indexed_rebase:
            issues.append(_issue("rebase_index_missing_entry", "medium", document_id, workflow_type="rebase_commit", workflow_id=workspace_id, current_state_summary="workspace_present", expected_state_summary="indexed", recoverability="recoverable", recommended_safe_action="rebuild_rebase_index", blockers=[], warnings=[]))
    return issues


def _workflow_issues(document_id: str, root: Path) -> list[dict[str, Any]]:
    issues = []
    current = load_document_content_curation(document_id, root=root).get("curation") or {}
    bulk_dir = root / "document_content_bulk" / document_id
    if bulk_dir.exists():
        for path in sorted(bulk_dir.glob("*.json")):
            payload = _read_json(path)
            if isinstance(payload, dict) and payload.get("status") == "approved":
                provenance = current.get("bulk_provenance") if isinstance(current, dict) else {}
                if isinstance(provenance, dict) and provenance.get("bulk_batch_id") == payload.get("batch_id"):
                    issues.append(_issue("orphaned_batch_plan", "high", document_id, workflow_type="bulk_commit", workflow_id=payload.get("batch_id"), current_state_summary="overlay_applied", expected_state_summary="batch_committed", recoverability="recoverable", recommended_safe_action="build_recovery_plan", blockers=[], warnings=[]))
    rebase_dir = root / "document_content_curation_rebase" / document_id
    if rebase_dir.exists():
        for path in sorted(rebase_dir.glob("*.json")):
            payload = _read_json(path)
            if isinstance(payload, dict) and payload.get("status") in {"ready", "ready_with_warnings", "unresolved"}:
                provenance = current.get("rebase_provenance") if isinstance(current, dict) else {}
                if isinstance(provenance, dict) and provenance.get("rebase_workspace_id") == payload.get("workspace_id"):
                    issues.append(_issue("orphaned_rebase_workspace", "high", document_id, workflow_type="rebase_commit", workflow_id=payload.get("workspace_id"), current_state_summary="overlay_applied", expected_state_summary="workspace_committed", recoverability="recoverable", recommended_safe_action="build_recovery_plan", blockers=[], warnings=[]))
    tx_folder = root / TRANSACTION_DIR / document_id
    if tx_folder.exists():
        for path in sorted(tx_folder.glob("*.json")):
            payload = _read_json(path)
            if not isinstance(payload, dict):
                continue
            workflow_type = str(payload.get("source_workflow_type") or "")
            workflow_id = str(payload.get("source_workflow_id") or "")
            if workflow_type == "bulk_commit":
                if not _safe_storage_identifier(workflow_id):
                    workflow_exists = False
                else:
                    workflow_exists = _bulk_plan_path(root, document_id, workflow_id).exists()
            elif workflow_type == "rebase_commit":
                if not _safe_storage_identifier(workflow_id):
                    workflow_exists = False
                else:
                    workflow_exists = _workspace_path(root, document_id, workflow_id).exists()
            else:
                workflow_exists = True
            if workflow_exists or not workflow_type:
                continue
            verified = _verify_transaction(payload, root)
            recoverability = "recoverable" if verified.get("transaction_status") == "prepared" else MANUAL_REVIEW_REQUIRED
            severity = "medium" if verified.get("transaction_status") == "prepared" else "critical"
            recommended = "abandon_transaction" if verified.get("transaction_status") == "prepared" else "manual_review"
            issues.append(
                _issue(
                    "transaction_missing_workflow_record",
                    severity,
                    document_id,
                    transaction_id=payload.get("transaction_id"),
                    revision=_safe_revision(payload.get("expected_new_curation_revision")),
                    workflow_type=workflow_type,
                    workflow_id=workflow_id,
                    current_state_summary=verified.get("transaction_status", "unknown"),
                    expected_state_summary="workflow_record_present",
                    recoverability=recoverability,
                    recommended_safe_action=recommended,
                    blockers=["workflow_record_missing"],
                    warnings=[],
                )
            )
    return issues


def _issue(issue_type: str, severity: str, document_id: str, *, transaction_id: str | None = None, revision: int | None = None, workflow_type: str | None = None, workflow_id: str | None = None, current_state_summary: str, expected_state_summary: str, recoverability: str, recommended_safe_action: str, blockers: list[str], warnings: list[str]) -> dict[str, Any]:
    issue_id = hashlib.sha256(json.dumps({"document_id": document_id, "issue_type": issue_type, "transaction_id": transaction_id, "revision": revision, "workflow_type": workflow_type, "workflow_id": workflow_id}, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12]
    return {
        "issue_id": f"issue_{issue_id}",
        "document_id": document_id,
        "issue_type": issue_type,
        "severity": severity,
        "affected_transaction_id": transaction_id,
        "affected_revision": revision,
        "affected_workflow_type": workflow_type,
        "affected_workflow_id": workflow_id,
        "current_state_summary": current_state_summary,
        "expected_state_summary": expected_state_summary,
        "recoverability": recoverability,
        "recommended_safe_action": recommended_safe_action,
        "blockers": blockers,
        "warnings": warnings,
    }


def _severity_counts(issues: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for item in issues:
        key = str(item.get("severity") or "info")
        counts[key] = counts.get(key, 0) + 1
    return counts


def _severity_rank(severity: Any) -> int:
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    return order.get(str(severity or "info"), 5)


def _required_checkpoints(transaction_type: Any) -> list[str]:
    if transaction_type in {"rebase_commit", "bulk_commit"}:
        return ["overlay_written", "history_written", "source_status_written", "indexes_reconciled"]
    return ["overlay_written", "history_written", "indexes_reconciled"]


def _save_transaction(root: Path, payload: dict[str, Any]) -> None:
    _atomic_write_json(_transaction_path(root, payload.get("document_id"), payload.get("transaction_id")), payload)
    _update_transaction_index(root)


def _update_transaction_index(root: Path) -> None:
    entries = []
    for doc_dir in sorted((root / TRANSACTION_DIR).glob("*")):
        if not doc_dir.is_dir():
            continue
        for path in sorted(doc_dir.glob("*.json")):
            payload = _read_json(path)
            if isinstance(payload, dict):
                entries.append(_transaction_summary(payload))
    _atomic_write_json(root / "indexes" / TRANSACTION_INDEX, {"entries": entries, "updated_at_utc": _now()})


def _transaction_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "document_id": payload.get("document_id"),
        "transaction_id": payload.get("transaction_id"),
        "transaction_type": payload.get("transaction_type"),
        "transaction_status": payload.get("transaction_status"),
        "expected_new_curation_revision": payload.get("expected_new_curation_revision"),
        "source_workflow_type": payload.get("source_workflow_type"),
        "source_workflow_id": payload.get("source_workflow_id"),
        "updated_at_utc": payload.get("updated_at_utc"),
    }


def _ensure_document_content_integrity_dirs(root: Path | str) -> Path:
    base = _ensure_document_content_curation_dirs(root)
    (base / TRANSACTION_DIR).mkdir(parents=True, exist_ok=True)
    (base / RECOVERY_PLAN_DIR).mkdir(parents=True, exist_ok=True)
    index_path = base / "indexes" / TRANSACTION_INDEX
    if not index_path.exists():
        _atomic_write_json(index_path, {"entries": [], "updated_at_utc": _now()})
    return base


def _transaction_path(root: Path, document_id: str, transaction_id: str) -> Path:
    return root / TRANSACTION_DIR / document_id / f"{transaction_id}.json"


def _recovery_plan_path(root: Path, document_id: str, plan_id: str) -> Path:
    return root / RECOVERY_PLAN_DIR / document_id / f"{plan_id}.json"


def _transaction_id(document_id: str, transaction_type: str, commit_fingerprint: str, source_workflow_id: str | None) -> str:
    digest = hashlib.sha256(json.dumps({"document_id": document_id, "transaction_type": transaction_type, "commit_fingerprint": commit_fingerprint, "source_workflow_id": source_workflow_id}, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12]
    return f"tx_{digest}"


def _commit_fingerprint(**payload: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _recovery_plan_id(document_id: str, scan_fingerprint: Any, actions: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256(json.dumps({"document_id": document_id, "scan_fingerprint": scan_fingerprint, "actions": actions}, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12]
    return f"recovery_{digest}"


def _scan_fingerprint(issues: list[dict[str, Any]]) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(issues, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _unique_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    unique = []
    for action in actions:
        key = json.dumps(action, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        unique.append(action)
    return unique


def _maybe_fail(stage: str) -> None:
    hook = _FAIL_STAGE_HOOK
    if callable(hook):
        hook(stage)


def _validate_recovery_plan_payload(plan: dict[str, Any], document_id: str, plan_id: str) -> list[str]:
    blockers: list[str] = []
    if str(plan.get("document_id") or "") != document_id:
        blockers.append("document_id_mismatch")
    if str(plan.get("plan_id") or "") != plan_id:
        blockers.append("plan_id_mismatch")
    if str(plan.get("schema_version") or "") != TRANSACTION_SCHEMA_VERSION:
        blockers.append("recovery_plan_schema_unknown")
    if not str(plan.get("source_integrity_scan_fingerprint") or "").startswith("sha256:"):
        blockers.append("recovery_plan_scan_fingerprint_missing")
    if not isinstance(plan.get("dry_run"), bool):
        blockers.append("recovery_plan_dry_run_invalid")
    if not str(plan.get("status") or "").strip():
        blockers.append("recovery_plan_status_missing")
    actions = plan.get("planned_actions")
    if not isinstance(actions, list):
        blockers.append("recovery_plan_actions_invalid")
        return blockers
    seen = set()
    for action in actions:
        if not isinstance(action, dict):
            blockers.append("recovery_plan_action_invalid")
            continue
        key = json.dumps(action, sort_keys=True, default=str)
        if key in seen:
            blockers.append("recovery_plan_duplicate_action")
            continue
        seen.add(key)
        if str(action.get("action") or "") not in {
            "write_missing_history_if_safe",
            "complete_workflow_status_if_safe",
            "mark_transaction_committed_if_safe",
            "rebuild_history_index",
            "rebuild_bulk_index",
            "rebuild_rebase_index",
            "rebuild_transaction_index",
        }:
            blockers.append("recovery_plan_unsupported_action")
    issue_ids = plan.get("issue_ids")
    if issue_ids is not None and not isinstance(issue_ids, list):
        blockers.append("recovery_plan_issue_ids_invalid")
    return list(dict.fromkeys(blockers))


def _safe_storage_identifier(value: object) -> bool:
    if not isinstance(value, str):
        return False
    candidate = value.strip()
    if not candidate:
        return False
    if candidate != value:
        return False
    if any(ord(char) < 32 for char in candidate):
        return False
    if candidate.startswith(("/", "\\")):
        return False
    if candidate.startswith("..") or candidate.endswith(".."):
        return False
    if "/" in candidate or "\\" in candidate or "\x00" in candidate:
        return False
    if ":" in candidate:
        return False
    return True
