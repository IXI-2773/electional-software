from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .document_content_curation import _atomic_write_json
from .document_manifest import build_document_manifest, validate_source_locator
from .evidence_binder import _update_evidence_binder_index, load_evidence_binder
from .locator_migration_planner import (
    _document_fingerprint,
    _extract_locator,
    _load_record_payload,
    _plan_path,
    _proposal_id,
    _read_json,
    _to_manifest_locator,
    load_locator_migration_plan,
    validate_locator_correction_proposal,
)
from .proposal_review import load_proposal_review
from .source_documents import SOURCE_DOCUMENT_ROOT
from .source_impact_analysis import (
    QUEUE_DIR,
    QUEUE_INDEX,
    _queue_item_path,
    _update_queue_index,
    analyze_source_change_impact,
    ensure_source_impact_dirs,
)
from .source_knowledge import _update_citation_index, _update_proposal_index

RECEIPT_DIR = "locator_migration_execution_receipts"
BACKUP_DIR = "locator_migration_backups"
RECEIPT_INDEX = "locator_migration_execution_index.json"
RECEIPT_SCHEMA_VERSION = "locator_migration_execution_receipt_v1"
STATUS_STARTED = "started"
STATUS_COMPLETED = "completed"
STATUS_ALREADY_APPLIED = "already_applied"
STATUS_FAILED_ROLLED_BACK = "failed_rolled_back"
STATUS_ROLLBACK_COMPLETED = "rollback_completed"
STATUS_ROLLBACK_FAILED = "rollback_failed"
STATUS_BLOCKED = "blocked"
SUCCESS_STATUSES = {STATUS_COMPLETED, STATUS_ALREADY_APPLIED}


def validate_locator_migration_execution(
    migration_plan_id: str,
    proposal_id: str,
    dry_run: bool = True,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = Path(root)
    _ensure_storage(base)
    loaded = load_locator_migration_plan(migration_plan_id, root=base)
    plan = loaded.get("plan")
    blockers: list[str] = []
    warnings: list[str] = []
    if not isinstance(plan, dict):
        return {
            "migration_plan_id": migration_plan_id,
            "proposal_id": proposal_id,
            "valid": False,
            "dry_run": bool(dry_run),
            "confirmation_valid": False,
            "proposal_classification": "blocked",
            "before_state_current": False,
            "target_current": False,
            "dependencies_readable": False,
            "blockers": ["plan_not_found"],
            "warnings": [],
        }
    proposal = _find_proposal(plan, proposal_id)
    if not isinstance(proposal, dict):
        blockers.append("proposal_not_found")
    validation = validate_locator_correction_proposal(migration_plan_id, proposal_id, root=base)
    inherited_blockers = [item for item in list(validation.get("blockers", [])) if item != "migration_plan_stale"]
    blockers.extend(inherited_blockers)
    warnings.extend(list(validation.get("warnings", [])))
    if not _plan_current_for_execution(plan, base):
        blockers.append("migration_plan_stale")
    classification = str((proposal or {}).get("classification") or validation.get("classification") or "blocked")
    if classification != "safe_candidate":
        blockers.append("proposal_not_safe_candidate")
    if int((proposal or {}).get("candidate_count", 0) or 0) != 1:
        blockers.append("candidate_count_not_unique")
    record = _load_record_payload(str((proposal or {}).get("record_type") or ""), str((proposal or {}).get("record_id") or ""), base)
    before = (proposal or {}).get("before")
    before_state_current = isinstance(record, dict) and _extract_locator(record) == before
    if not before_state_current:
        blockers.append("locator_before_state_changed")
    after = (proposal or {}).get("proposed_after")
    target_validation = validate_source_locator(_to_manifest_locator(after), root=base) if isinstance(after, dict) else {"valid": False, "blockers": ["missing_target_locator"], "warnings": []}
    target_current = bool(target_validation.get("valid"))
    if not target_current:
        blockers.extend(list(target_validation.get("blockers", [])))
        warnings.extend(list(target_validation.get("warnings", [])))
    dependency_check = _dependency_records_readable(proposal or {}, base)
    if not dependency_check["readable"]:
        blockers.extend(dependency_check["blockers"])
    warnings.extend(dependency_check["warnings"])
    confirmation_valid = (not dry_run) and confirmation == "APPLY"
    if not dry_run and not confirmation_valid:
        blockers.append("apply_confirmation_required")
    return {
        "migration_plan_id": migration_plan_id,
        "proposal_id": proposal_id,
        "valid": not blockers,
        "dry_run": bool(dry_run),
        "confirmation_valid": confirmation_valid,
        "proposal_classification": classification,
        "before_state_current": before_state_current,
        "target_current": target_current,
        "dependencies_readable": dependency_check["readable"],
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
    }


def build_locator_migration_write_set(
    migration_plan_id: str,
    proposal_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = Path(root)
    validation = validate_locator_migration_execution(migration_plan_id, proposal_id, dry_run=True, root=base)
    loaded = load_locator_migration_plan(migration_plan_id, root=base)
    plan = loaded.get("plan") if isinstance(loaded.get("plan"), dict) else {}
    proposal = _find_proposal(plan, proposal_id) if isinstance(plan, dict) else None
    if not validation.get("valid") or not isinstance(proposal, dict):
        return {
            "migration_plan_id": migration_plan_id,
            "proposal_id": proposal_id,
            "record_updates": [],
            "embedded_dependency_updates": [],
            "new_records": [],
            "files_to_backup": [],
            "indexes_to_update": [],
            "warnings": list(validation.get("warnings", [])),
            "blockers": list(validation.get("blockers", [])),
        }
    record_type = str(proposal.get("record_type") or "")
    record_id = str(proposal.get("record_id") or "")
    record = _load_record_payload(record_type, record_id, base) or {}
    updated = _build_updated_record(record, proposal.get("proposed_after") or {})
    record_path = _primary_record_path(base, record_type, record_id)
    dependency_updates = _build_embedded_dependency_updates(proposal, updated, base)
    revalidation_preview = _build_revalidation_payload(
        execution_id=_execution_id(plan, proposal),
        plan=plan,
        proposal=proposal,
        root=base,
        suffix="pending",
    )
    queue_path = _queue_item_path(base, str(revalidation_preview.get("queue_item_id")))
    primary_index = _primary_index_name(record_type)
    record_updates = [
        {
            "record_type": record_type,
            "record_id": record_id,
            "before_hash": _json_hash(record),
            "after_hash": _json_hash(updated),
            "changes": _locator_change_fields(record, updated),
        }
    ]
    return {
        "migration_plan_id": migration_plan_id,
        "proposal_id": proposal_id,
        "record_updates": record_updates,
        "embedded_dependency_updates": dependency_updates["updates"],
        "new_records": [
            {"record_type": "revalidation_item", "record_id": revalidation_preview.get("queue_item_id")},
            {"record_type": "execution_receipt", "record_id": _execution_id(plan, proposal)},
        ],
        "files_to_backup": [
            str(_relative(base, record_path)),
            str(_relative(base, base / "indexes" / primary_index)),
            str(_relative(base, base / "indexes" / QUEUE_INDEX)),
            str(_relative(base, base / "indexes" / RECEIPT_INDEX)),
            *dependency_updates["backup_paths"],
        ],
        "indexes_to_update": [primary_index, QUEUE_INDEX, RECEIPT_INDEX, *dependency_updates["index_names"]],
        "warnings": list(validation.get("warnings", [])),
        "blockers": list(validation.get("blockers", [])),
        "preview_record_count": 1 + len(dependency_updates["updates"]),
        "preview_after_state": updated,
        "preview_revalidation_item_id": revalidation_preview.get("queue_item_id"),
        "preview_revalidation_path": str(_relative(base, queue_path)),
    }


def execute_locator_migration_proposal(
    migration_plan_id: str,
    proposal_id: str,
    dry_run: bool = True,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = Path(root)
    _ensure_storage(base)
    loaded = load_locator_migration_plan(migration_plan_id, root=base)
    plan = loaded.get("plan") if isinstance(loaded.get("plan"), dict) else {}
    proposal = _find_proposal(plan, proposal_id) if isinstance(plan, dict) else None
    if not isinstance(plan, dict) or not isinstance(proposal, dict):
        return {
            "migration_plan_id": migration_plan_id,
            "proposal_id": proposal_id,
            "status": STATUS_BLOCKED,
            "dry_run": bool(dry_run),
            "warnings": [],
            "blockers": ["plan_or_proposal_not_found"],
        }
    execution_id = _execution_id(plan, proposal)
    existing = load_locator_migration_execution_receipt(execution_id, root=base)
    if existing.get("receipt"):
        existing_receipt = existing["receipt"]
        if existing_receipt.get("status") in SUCCESS_STATUSES and _receipt_after_state_current(existing_receipt, base):
            _update_receipt_index(base)
            return {
                "execution_id": execution_id,
                "migration_plan_id": migration_plan_id,
                "proposal_id": proposal_id,
                "document_id": plan.get("document_id"),
                "status": STATUS_ALREADY_APPLIED,
                "dry_run": False,
                "records_updated": len(existing_receipt.get("updated_record_ids", [])),
                "embedded_dependencies_updated": len(existing_receipt.get("embedded_dependency_record_ids", [])),
                "revalidation_records_created": len([item for item in existing_receipt.get("created_record_ids", []) if str(item).startswith("impact_")]),
                "impact_records_created": 1 if existing_receipt.get("revalidation_queue_item_id") else 0,
                "post_write_provenance_status": existing_receipt.get("post_write_provenance_status", "valid"),
                "rollback_available": bool(existing_receipt.get("rollback_available")),
                "warnings": list(existing_receipt.get("warnings", [])),
            }
    validation = validate_locator_migration_execution(
        migration_plan_id,
        proposal_id,
        dry_run=dry_run,
        confirmation=confirmation,
        root=base,
    )
    write_set = build_locator_migration_write_set(migration_plan_id, proposal_id, root=base)
    if dry_run:
        return {
            "execution_id": execution_id,
            "migration_plan_id": migration_plan_id,
            "proposal_id": proposal_id,
            "document_id": plan.get("document_id"),
            "status": "dry_run",
            "dry_run": True,
            "write_set": write_set,
            "records_updated": len(write_set.get("record_updates", [])),
            "embedded_dependencies_updated": len(write_set.get("embedded_dependency_updates", [])),
            "revalidation_records_created": 0,
            "impact_records_created": 0,
            "post_write_provenance_status": "not_run",
            "rollback_available": False,
            "warnings": list(validation.get("warnings", [])),
            "blockers": list(validation.get("blockers", [])),
        }
    if not validation.get("valid"):
        receipt = _build_receipt(execution_id, plan, proposal, status=STATUS_BLOCKED, warnings=list(validation.get("warnings", [])), blockers=list(validation.get("blockers", [])))
        _save_receipt(base, receipt)
        return {
            "execution_id": execution_id,
            "migration_plan_id": migration_plan_id,
            "proposal_id": proposal_id,
            "document_id": plan.get("document_id"),
            "status": STATUS_BLOCKED,
            "dry_run": False,
            "records_updated": 0,
            "embedded_dependencies_updated": 0,
            "revalidation_records_created": 0,
            "impact_records_created": 0,
            "post_write_provenance_status": "not_run",
            "rollback_available": False,
            "warnings": list(validation.get("warnings", [])),
            "blockers": list(validation.get("blockers", [])),
        }
    receipt = _build_receipt(execution_id, plan, proposal, status=STATUS_STARTED, warnings=list(validation.get("warnings", [])))
    _save_receipt(base, receipt)
    created_paths: list[Path] = []
    try:
        backup_info = _create_backups(base, execution_id, write_set.get("files_to_backup", []))
        receipt["backup_hashes"] = backup_info["hashes"]
        _save_receipt(base, receipt)
        record_type = str(proposal.get("record_type") or "")
        record_id = str(proposal.get("record_id") or "")
        record_path = _primary_record_path(base, record_type, record_id)
        record = _load_record_payload(record_type, record_id, base) or {}
        updated = _build_updated_record(record, proposal.get("proposed_after") or {})
        _atomic_write_json(record_path, updated)
        _refresh_primary_index(base, record_type)
        dependency_updates = _build_embedded_dependency_updates(proposal, updated, base)
        for item in dependency_updates["updates"]:
            _atomic_write_json(base / str(item["relative_path"]), item["after_payload"])
        if dependency_updates["updates"]:
            _update_evidence_binder_index(base)
        queue_item = _build_revalidation_payload(execution_id=execution_id, plan=plan, proposal=proposal, root=base)
        queue_path = _queue_item_path(base, str(queue_item["queue_item_id"]))
        _atomic_write_json(queue_path, queue_item)
        created_paths.append(queue_path)
        _update_queue_index(base)
        receipt["before_state_hashes"] = {
            str(_relative(base, record_path)): _json_hash(record),
        }
        receipt["after_state_hashes"] = {
            str(_relative(base, record_path)): _json_hash(updated),
            str(_relative(base, queue_path)): _json_hash(queue_item),
        }
        for item in dependency_updates["updates"]:
            receipt["before_state_hashes"][str(item["relative_path"])] = item["before_hash"]
            receipt["after_state_hashes"][str(item["relative_path"])] = item["after_hash"]
        receipt["updated_record_ids"] = [record_id, *[str(item["record_id"]) for item in dependency_updates["updates"]]]
        receipt["embedded_dependency_record_ids"] = [str(item["record_id"]) for item in dependency_updates["updates"]]
        receipt["created_record_ids"] = [str(queue_item["queue_item_id"])]
        receipt["revalidation_queue_item_id"] = queue_item["queue_item_id"]
        post = _post_write_validate(base, proposal, updated, queue_item, dependency_updates["updates"])
        if post["status"] != "valid":
            raise ValueError("post_write_validation_failure")
        receipt["post_write_provenance_status"] = "valid"
        receipt["rollback_available"] = True
        receipt["status"] = STATUS_COMPLETED
        receipt["completed_at_utc"] = _now()
        _save_receipt(base, receipt)
        return {
            "execution_id": execution_id,
            "migration_plan_id": migration_plan_id,
            "proposal_id": proposal_id,
            "document_id": plan.get("document_id"),
            "status": STATUS_COMPLETED,
            "dry_run": False,
            "records_updated": 1,
            "embedded_dependencies_updated": len(dependency_updates["updates"]),
            "revalidation_records_created": 1,
            "impact_records_created": 1,
            "post_write_provenance_status": "valid",
            "rollback_available": True,
            "warnings": list(validation.get("warnings", [])),
        }
    except Exception as exc:
        rollback = _rollback_failed_execution(base, execution_id, created_paths)
        receipt = load_locator_migration_execution_receipt(execution_id, root=base).get("receipt") or receipt
        receipt["status"] = STATUS_FAILED_ROLLED_BACK if rollback["rollback_verified"] else STATUS_ROLLBACK_FAILED
        receipt["classification"] = "post_write_validation_failure" if "post_write_validation_failure" in str(exc) else "execution_failure"
        receipt["rollback_available"] = False
        receipt["rollback_verified"] = bool(rollback["rollback_verified"])
        receipt["records_restored"] = rollback["records_restored"]
        receipt["error_type"] = exc.__class__.__name__
        receipt["error_message"] = "Execution failed and rollback was attempted."
        receipt["completed_at_utc"] = _now()
        _save_receipt(base, receipt)
        return {
            "execution_id": execution_id,
            "migration_plan_id": migration_plan_id,
            "proposal_id": proposal_id,
            "document_id": plan.get("document_id"),
            "status": receipt["status"],
            "classification": receipt["classification"],
            "records_restored": rollback["records_restored"],
            "rollback_verified": rollback["rollback_verified"],
            "error_type": exc.__class__.__name__,
            "error_message": "Sanitized error message.",
            "warnings": list(receipt.get("warnings", [])),
        }


def load_locator_migration_execution_receipt(
    execution_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    payload = _read_json(_receipt_path(Path(root), execution_id))
    if not isinstance(payload, dict):
        return {"execution_id": execution_id, "status": "not_found", "receipt": None}
    return {"execution_id": execution_id, "status": str(payload.get("status") or "unknown"), "receipt": json.loads(json.dumps(payload, sort_keys=True, default=str))}


def list_locator_migration_execution_receipts(
    document_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = Path(root)
    _ensure_storage(base)
    items: list[dict[str, Any]] = []
    for path in sorted((base / RECEIPT_DIR).glob("locator_execution_*.json")):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        if document_id and str(payload.get("document_id") or "") != document_id:
            continue
        if status and str(payload.get("status") or "") != status:
            continue
        items.append(payload)
    items.sort(key=lambda item: (str(item.get("created_at_utc") or ""), str(item.get("execution_id") or "")), reverse=True)
    limited = items[: max(0, int(limit or 0))]
    return {"count": len(limited), "items": limited}


def rollback_locator_migration_execution(
    execution_id: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = Path(root)
    loaded = load_locator_migration_execution_receipt(execution_id, root=base)
    receipt = loaded.get("receipt")
    if not isinstance(receipt, dict):
        return {"execution_id": execution_id, "status": STATUS_BLOCKED, "blockers": ["receipt_not_found"], "warnings": []}
    if confirmation != "ROLLBACK":
        return {"execution_id": execution_id, "status": STATUS_BLOCKED, "blockers": ["rollback_confirmation_required"], "warnings": []}
    if receipt.get("status") != STATUS_COMPLETED:
        return {"execution_id": execution_id, "status": STATUS_BLOCKED, "blockers": ["receipt_not_completed"], "warnings": []}
    if not _backup_manifest_path(base, execution_id).exists():
        return {"execution_id": execution_id, "status": STATUS_BLOCKED, "blockers": ["backup_missing"], "warnings": []}
    if not _receipt_after_state_current(receipt, base):
        return {"execution_id": execution_id, "status": STATUS_BLOCKED, "blockers": ["record_state_diverged"], "warnings": []}
    if _has_later_successful_overlap(base, receipt):
        return {"execution_id": execution_id, "status": STATUS_BLOCKED, "blockers": ["later_successful_migration_exists"], "warnings": []}
    restored = _restore_backups(base, execution_id)
    if not restored["rollback_verified"]:
        receipt["status"] = STATUS_ROLLBACK_FAILED
        receipt["rollback_verified"] = False
        receipt["completed_at_utc"] = _now()
        _save_receipt(base, receipt)
        return {"execution_id": execution_id, "status": STATUS_ROLLBACK_FAILED, "records_restored": restored["records_restored"], "indexes_restored": restored["indexes_restored"], "rollback_verified": False, "revalidation_record_created": False, "warnings": []}
    rollback_queue_item = _build_reversal_revalidation_payload(execution_id, receipt, base)
    queue_path = _queue_item_path(base, str(rollback_queue_item["queue_item_id"]))
    _atomic_write_json(queue_path, rollback_queue_item)
    _mark_execution_revalidation_reversed(base, receipt, rollback_queue_item)
    _update_queue_index(base)
    receipt["status"] = STATUS_ROLLBACK_COMPLETED
    receipt["rollback_verified"] = True
    receipt["rollback_available"] = False
    receipt["rollback_completed_at_utc"] = _now()
    receipt["rollback_revalidation_queue_item_id"] = rollback_queue_item["queue_item_id"]
    _save_receipt(base, receipt)
    return {
        "execution_id": execution_id,
        "status": STATUS_ROLLBACK_COMPLETED,
        "records_restored": restored["records_restored"],
        "indexes_restored": restored["indexes_restored"],
        "rollback_verified": True,
        "revalidation_record_created": True,
        "warnings": [],
    }


def get_locator_migration_execution_health(
    document_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = Path(root)
    _ensure_storage(base)
    warnings: list[str] = []
    index_payload = _read_json(base / "indexes" / RECEIPT_INDEX)
    if not isinstance(index_payload, dict) or not isinstance(index_payload.get("entries"), list):
        warnings.append("receipt_index_unreadable")
    receipts = list_locator_migration_execution_receipts(document_id=document_id, limit=500, root=base).get("items", [])
    if any(str(item.get("schema_version") or "") != RECEIPT_SCHEMA_VERSION for item in receipts):
        warnings.append("unsupported_receipt_schema")
    execution_ids = [str(item.get("execution_id") or "") for item in receipts]
    if len(execution_ids) != len(set(execution_ids)):
        warnings.append("duplicate_execution_id_detected")
    completed = [item for item in receipts if item.get("status") == STATUS_COMPLETED]
    already_applied = [item for item in receipts if item.get("status") == STATUS_ALREADY_APPLIED]
    failed = [item for item in receipts if item.get("status") == STATUS_FAILED_ROLLED_BACK]
    pending = [item for item in receipts if item.get("status") == STATUS_STARTED]
    rollback_failed = [item for item in receipts if item.get("status") == STATUS_ROLLBACK_FAILED]
    missing_revalidation = [item for item in completed if not item.get("revalidation_queue_item_id")]
    for item in completed:
        if not _backup_manifest_path(base, str(item.get("execution_id"))).exists():
            warnings.append("completed_execution_missing_verified_backup")
        elif not _backup_hashes_verified(base, str(item.get("execution_id"))):
            warnings.append("completed_execution_backup_hash_mismatch")
        if not _receipt_after_state_current(item, base):
            warnings.append("completed_execution_after_state_drifted")
        if not item.get("revalidation_queue_item_id"):
            warnings.append("completed_execution_missing_revalidation")
    if failed:
        warnings.append("one_previous_execution_failed_and_was_rolled_back")
        if any(not item.get("rollback_verified") for item in failed):
            warnings.append("failed_execution_missing_verified_rollback")
    status = "healthy"
    if rollback_failed:
        status = "critical"
    elif pending or missing_revalidation or warnings:
        status = "warning"
    return {
        "status": status,
        "completed_execution_count": len(completed),
        "already_applied_count": len(already_applied),
        "failed_rolled_back_count": len(failed),
        "pending_execution_count": len(pending),
        "rollback_failed_count": len(rollback_failed),
        "missing_revalidation_count": len(missing_revalidation),
        "warnings": sorted(set(warnings)),
        "recommended_action": "Review the failed execution receipt." if failed or rollback_failed else "No action required.",
    }


def format_locator_migration_execution_report(
    execution_id: str | None = None,
    document_id: str | None = None,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    receipt = None
    if execution_id:
        receipt = load_locator_migration_execution_receipt(execution_id, root=root).get("receipt")
    elif document_id:
        items = list_locator_migration_execution_receipts(document_id=document_id, limit=1, root=root).get("items", [])
        receipt = items[0] if items else None
    if not isinstance(receipt, dict):
        health = get_locator_migration_execution_health(document_id, root=root)
        return "\n".join(
            [
                "Locator Migration Execution Report",
                "",
                f"Document: {document_id or 'unknown'}",
                f"Status: {health.get('status')}",
                "",
                "Recommended Action:",
                str(health.get("recommended_action") or "No completed execution receipt found."),
            ]
        )
    lines = [
        "Locator Migration Execution Report",
        "",
        f"Document: {receipt.get('document_id')}",
        f"Execution: {receipt.get('execution_id')}",
        f"Status: {receipt.get('status')}",
        "",
        "Migration:",
        f"- Locator Records Updated: {len(receipt.get('updated_record_ids', []))}",
        f"- Embedded Dependencies Updated: {len(receipt.get('embedded_dependency_record_ids', []))}",
        f"- Impact Records Created: {1 if receipt.get('revalidation_queue_item_id') else 0}",
        f"- Revalidation Records Created: {1 if receipt.get('revalidation_queue_item_id') else 0}",
        f"- Post-Write Provenance: {receipt.get('post_write_provenance_status', 'unknown')}",
        "",
        "Recovery:",
        f"- Verified Backups: {'Yes' if bool(receipt.get('backup_hashes')) else 'No'}",
        f"- Rollback Available: {'Yes' if bool(receipt.get('rollback_available')) else 'No'}",
        f"- Rollback Performed: {'Yes' if receipt.get('status') == STATUS_ROLLBACK_COMPLETED else 'No'}",
        "",
        "Recommended Action:",
        "Review the pending revalidation item." if receipt.get("revalidation_queue_item_id") else "No revalidation item was recorded.",
    ]
    if not public_safe:
        lines.extend(["", f"Proposal: {receipt.get('proposal_id')}", f"Plan: {receipt.get('migration_plan_id')}"])
    return "\n".join(lines)


def _ensure_storage(root: Path) -> None:
    (root / RECEIPT_DIR).mkdir(parents=True, exist_ok=True)
    (root / BACKUP_DIR).mkdir(parents=True, exist_ok=True)
    (root / "indexes").mkdir(parents=True, exist_ok=True)
    index_path = root / "indexes" / RECEIPT_INDEX
    if not index_path.exists():
        _atomic_write_json(index_path, {"entries": [], "updated_at_utc": _now()})


def _find_proposal(plan: dict[str, Any], proposal_id: str) -> dict[str, Any] | None:
    return next((item for item in plan.get("proposals", []) if isinstance(item, dict) and item.get("proposal_id") == proposal_id), None)


def _plan_current_for_execution(plan: dict[str, Any], root: Path) -> bool:
    document_id = str(plan.get("document_id") or "")
    manifest = build_document_manifest(document_id, regenerate=False, root=root)
    if manifest.get("source_revision") != plan.get("source_revision"):
        return False
    if _document_fingerprint(document_id, root) != plan.get("document_scoped_fingerprint"):
        return False
    return True


def _execution_id(plan: dict[str, Any], proposal: dict[str, Any]) -> str:
    payload = {
        "migration_plan_id": plan.get("migration_plan_id"),
        "proposal_id": proposal.get("proposal_id"),
        "document_id": plan.get("document_id"),
        "fingerprint": plan.get("fingerprint"),
        "before": proposal.get("before"),
        "after": proposal.get("proposed_after"),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()[:12]
    return f"locator_execution_{digest}"


def _receipt_path(root: Path, execution_id: str) -> Path:
    return root / RECEIPT_DIR / f"{execution_id}.json"


def _backup_dir(root: Path, execution_id: str) -> Path:
    return root / BACKUP_DIR / execution_id


def _backup_manifest_path(root: Path, execution_id: str) -> Path:
    return _backup_dir(root, execution_id) / "manifest.json"


def _build_receipt(
    execution_id: str,
    plan: dict[str, Any],
    proposal: dict[str, Any],
    *,
    status: str,
    warnings: list[str] | None = None,
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "execution_id": execution_id,
        "migration_plan_id": plan.get("migration_plan_id"),
        "proposal_id": proposal.get("proposal_id"),
        "document_id": plan.get("document_id"),
        "status": status,
        "before_state_hashes": {},
        "after_state_hashes": {},
        "backup_hashes": {},
        "updated_record_ids": [],
        "created_record_ids": [],
        "post_write_provenance_status": "not_run",
        "rollback_available": False,
        "created_at_utc": _now(),
        "completed_at_utc": None,
        "warnings": list(warnings or []),
        "blockers": list(blockers or []),
    }


def _save_receipt(root: Path, receipt: dict[str, Any]) -> None:
    _atomic_write_json(_receipt_path(root, str(receipt.get("execution_id"))), receipt)
    _update_receipt_index(root)


def _update_receipt_index(root: Path) -> None:
    entries: list[dict[str, Any]] = []
    for path in sorted((root / RECEIPT_DIR).glob("locator_execution_*.json")):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        entries.append(
            {
                "execution_id": payload.get("execution_id"),
                "document_id": payload.get("document_id"),
                "migration_plan_id": payload.get("migration_plan_id"),
                "proposal_id": payload.get("proposal_id"),
                "status": payload.get("status"),
                "created_at_utc": payload.get("created_at_utc"),
                "completed_at_utc": payload.get("completed_at_utc"),
            }
        )
    _atomic_write_json(root / "indexes" / RECEIPT_INDEX, {"entries": entries, "updated_at_utc": _now()})


def _dependency_records_readable(proposal: dict[str, Any], root: Path) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    dependency_ids = (((proposal.get("dependency_impact") or {}).get("dependency_ids")) or {})
    for citation_id in dependency_ids.get("citations", []):
        if _load_record_payload("citation", str(citation_id), root) is None:
            blockers.append("dependency_citation_unreadable")
    for proposal_id in dependency_ids.get("proposals", []):
        if _load_record_payload("proposal", str(proposal_id), root) is None:
            blockers.append("dependency_proposal_unreadable")
    for review_id in dependency_ids.get("proposal_reviews", []):
        proposal_id = str(review_id).replace("review_", "", 1)
        if load_proposal_review(proposal_id, root=root, missing_ok=True) is None:
            warnings.append("dependency_proposal_review_missing")
    for binder_id in dependency_ids.get("evidence_binders", []):
        proposal_id = str(binder_id).replace("binder_", "", 1)
        binder = load_evidence_binder(proposal_id, root=root)
        if binder.get("binder_status") == "not_built":
            warnings.append("dependency_evidence_binder_missing")
    return {"readable": not blockers, "blockers": blockers, "warnings": warnings}


def _build_embedded_dependency_updates(proposal: dict[str, Any], updated_record: dict[str, Any], root: Path) -> dict[str, Any]:
    updates: list[dict[str, Any]] = []
    backup_paths: list[str] = []
    index_names: list[str] = []
    dependency_ids = (((proposal.get("dependency_impact") or {}).get("dependency_ids")) or {})
    citation_id = str(proposal.get("record_id") or "")
    for binder_id in dependency_ids.get("evidence_binders", []):
        proposal_id = str(binder_id).replace("binder_", "", 1)
        binder = load_evidence_binder(proposal_id, root=root)
        if binder.get("binder_status") == "not_built":
            continue
        linked = binder.get("linked_citations", [])
        if not isinstance(linked, list):
            continue
        changed = False
        next_linked: list[dict[str, Any]] = []
        for item in linked:
            if not isinstance(item, dict):
                next_linked.append(item)
                continue
            next_item = json.loads(json.dumps(item, sort_keys=True, default=str))
            if str(item.get("citation_id") or "") == citation_id:
                next_item["document_id"] = updated_record.get("document_id")
                next_item["chunk_id"] = updated_record.get("chunk_id")
                next_item["page_start"] = updated_record.get("page_start")
                next_item["page_end"] = updated_record.get("page_end")
                changed = changed or _json_hash(next_item) != _json_hash(item)
            next_linked.append(next_item)
        if not changed:
            continue
        updated_binder = json.loads(json.dumps(binder, sort_keys=True, default=str))
        updated_binder["linked_citations"] = next_linked
        updated_binder["updated_at_utc"] = _now()
        relative_path = f"evidence_binders/{proposal_id}_evidence_binder.json"
        updates.append(
            {
                "record_type": "evidence_binder",
                "record_id": binder_id,
                "relative_path": relative_path,
                "before_hash": _json_hash(binder),
                "after_hash": _json_hash(updated_binder),
                "changes": ["linked_citations"],
                "before_payload": binder,
                "after_payload": updated_binder,
            }
        )
        backup_paths.append(relative_path)
        if "evidence_binder_index.json" not in index_names:
            index_names.append("evidence_binder_index.json")
            backup_paths.append("indexes/evidence_binder_index.json")
    return {"updates": updates, "backup_paths": backup_paths, "index_names": index_names}


def _primary_record_path(root: Path, record_type: str, record_id: str) -> Path:
    folder = "citations" if record_type == "citation" else "proposals" if record_type == "proposal" else ""
    return root / folder / f"{record_id}.json"


def _primary_index_name(record_type: str) -> str:
    return "citation_index.json" if record_type == "citation" else "proposal_index.json"


def _refresh_primary_index(root: Path, record_type: str) -> None:
    if record_type == "citation":
        _update_citation_index(root)
    elif record_type == "proposal":
        _update_proposal_index(root)


def _build_updated_record(record: dict[str, Any], proposed_after: dict[str, Any]) -> dict[str, Any]:
    updated = json.loads(json.dumps(record, sort_keys=True, default=str))
    if "document_id" in updated or proposed_after.get("document_id") is not None:
        updated["document_id"] = proposed_after.get("document_id")
    if proposed_after.get("source_revision") is not None:
        updated["source_revision"] = proposed_after.get("source_revision")
    if proposed_after.get("chunk_id") is not None:
        updated["chunk_id"] = proposed_after.get("chunk_id")
    if proposed_after.get("page") is not None:
        updated["page_start"] = proposed_after.get("page")
        if "page_end" in updated:
            updated["page_end"] = proposed_after.get("page")
        if "page_number" in updated:
            updated["page_number"] = proposed_after.get("page")
    if proposed_after.get("start_offset") is not None or "start_offset" in updated or "character_start" in updated:
        updated["start_offset"] = proposed_after.get("start_offset")
        if "character_start" in updated:
            updated["character_start"] = proposed_after.get("start_offset")
    if proposed_after.get("end_offset") is not None or "end_offset" in updated or "character_end" in updated:
        updated["end_offset"] = proposed_after.get("end_offset")
        if "character_end" in updated:
            updated["character_end"] = proposed_after.get("end_offset")
    return updated


def _locator_change_fields(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    fields = []
    before_locator = _extract_locator(before) or {}
    after_locator = _extract_locator(after) or {}
    for source, label in (
        ("document_id", "document_id"),
        ("source_revision", "source_revision"),
        ("page", "page"),
        ("chunk_id", "chunk_id"),
        ("start_offset", "start_offset"),
        ("end_offset", "end_offset"),
    ):
        if before_locator.get(source) != after_locator.get(source):
            fields.append(label)
    return fields


def _json_hash(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _relative(root: Path, path: Path) -> Path:
    return path.relative_to(root)


def _create_backups(root: Path, execution_id: str, relative_paths: list[str]) -> dict[str, Any]:
    backup_root = _backup_dir(root, execution_id)
    backup_root.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    manifest_entries: list[dict[str, str]] = []
    for relative in relative_paths:
        source = root / relative
        if not source.exists():
            continue
        backup_path = backup_root / relative
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        data = source.read_bytes()
        backup_path.write_bytes(data)
        digest = "sha256:" + hashlib.sha256(data).hexdigest()
        hashes[relative] = digest
        manifest_entries.append({"path": relative, "hash": digest})
    _atomic_write_json(_backup_manifest_path(root, execution_id), {"execution_id": execution_id, "entries": manifest_entries, "created_at_utc": _now()})
    return {"hashes": hashes}


def _backup_hashes_verified(root: Path, execution_id: str) -> bool:
    manifest = _read_json(_backup_manifest_path(root, execution_id)) or {}
    entries = manifest.get("entries", []) if isinstance(manifest.get("entries"), list) else []
    for entry in entries:
        relative = str((entry or {}).get("path") or "")
        if not relative:
            continue
        backup_path = _backup_dir(root, execution_id) / relative
        if not backup_path.exists():
            return False
        if "sha256:" + hashlib.sha256(backup_path.read_bytes()).hexdigest() != entry.get("hash"):
            return False
    return True


def _restore_backups(root: Path, execution_id: str) -> dict[str, Any]:
    manifest = _read_json(_backup_manifest_path(root, execution_id)) or {}
    entries = manifest.get("entries", []) if isinstance(manifest.get("entries"), list) else []
    records_restored = 0
    indexes_restored = 0
    for entry in entries:
        relative = str((entry or {}).get("path") or "")
        if not relative:
            continue
        source = _backup_dir(root, execution_id) / relative
        target = root / relative
        if not source.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if "/indexes/" in relative.replace("\\", "/") or relative.startswith("indexes/"):
            indexes_restored += 1
        else:
            records_restored += 1
    verified = True
    for entry in entries:
        relative = str((entry or {}).get("path") or "")
        if not relative:
            continue
        data = (root / relative).read_bytes() if (root / relative).exists() else b""
        if "sha256:" + hashlib.sha256(data).hexdigest() != entry.get("hash"):
            verified = False
            break
    return {"records_restored": records_restored, "indexes_restored": indexes_restored, "rollback_verified": verified}


def _rollback_failed_execution(root: Path, execution_id: str, created_paths: list[Path]) -> dict[str, Any]:
    for path in created_paths:
        path.unlink(missing_ok=True)
    _update_queue_index(root)
    restored = _restore_backups(root, execution_id)
    _update_receipt_index(root)
    return {"records_restored": restored["records_restored"], "rollback_verified": restored["rollback_verified"]}


def _build_revalidation_payload(
    execution_id: str,
    plan: dict[str, Any],
    proposal: dict[str, Any],
    root: Path,
    suffix: str = "execution",
) -> dict[str, Any]:
    dependency_ids = (((proposal.get("dependency_impact") or {}).get("dependency_ids")) or {})
    impact = analyze_source_change_impact(str(plan.get("document_id") or ""), change_type="manual_review", root=root)
    queue_item_id = f"impact_{execution_id}_{suffix}"
    return {
        "queue_item_id": queue_item_id,
        "document_id": plan.get("document_id"),
        "change_type": "manual_review",
        "impact_severity": impact.get("impact_severity"),
        "status": "pending_review",
        "affected_counts": impact.get("affected_counts", {}),
        "created_at_utc": _now(),
        "updated_at_utc": _now(),
        "review_note": "locator_migration",
        "warnings": impact.get("warnings", []),
        "dedupe_key": _json_hash(
            {
                "execution_id": execution_id,
                "document_id": plan.get("document_id"),
                "proposal_id": proposal.get("proposal_id"),
                "reason": "locator_migration",
            }
        ),
        "execution_id": execution_id,
        "old_source_revision": (proposal.get("before") or {}).get("source_revision"),
        "new_source_revision": (proposal.get("proposed_after") or {}).get("source_revision"),
        "changed_locator_record_ids": [proposal.get("record_id")],
        "affected_proposal_ids": list(dependency_ids.get("proposals", [])),
        "affected_review_ids": list(dependency_ids.get("proposal_reviews", [])),
        "affected_binder_ids": list(dependency_ids.get("evidence_binders", [])),
        "reason": "locator_migration",
    }


def _build_reversal_revalidation_payload(execution_id: str, receipt: dict[str, Any], root: Path) -> dict[str, Any]:
    impact = analyze_source_change_impact(str(receipt.get("document_id") or ""), change_type="manual_review", root=root)
    return {
        "queue_item_id": f"impact_{execution_id}_rollback",
        "document_id": receipt.get("document_id"),
        "change_type": "manual_review",
        "impact_severity": impact.get("impact_severity"),
        "status": "pending_review",
        "affected_counts": impact.get("affected_counts", {}),
        "created_at_utc": _now(),
        "updated_at_utc": _now(),
        "review_note": "locator_migration_rollback",
        "warnings": impact.get("warnings", []),
        "dedupe_key": _json_hash({"execution_id": execution_id, "reason": "locator_migration_rollback"}),
        "execution_id": execution_id,
        "reason": "locator_migration_rollback",
    }


def _post_write_validate(root: Path, proposal: dict[str, Any], updated_record: dict[str, Any], queue_item: dict[str, Any], dependency_updates: list[dict[str, Any]]) -> dict[str, Any]:
    record = _load_record_payload(str(proposal.get("record_type") or ""), str(proposal.get("record_id") or ""), root)
    if not isinstance(record, dict):
        return {"status": "invalid", "blockers": ["record_missing_after_write"]}
    if _json_hash(record) != _json_hash(updated_record):
        return {"status": "invalid", "blockers": ["post_write_record_hash_mismatch"]}
    for item in dependency_updates:
        payload = _read_json(root / str(item["relative_path"]))
        if payload is None or _json_hash(payload) != item["after_hash"]:
            return {"status": "invalid", "blockers": ["post_write_dependency_hash_mismatch"]}
    queue_path = _queue_item_path(root, str(queue_item.get("queue_item_id")))
    if _read_json(queue_path) is None:
        return {"status": "invalid", "blockers": ["revalidation_record_missing_after_write"]}
    return {"status": "valid", "blockers": []}


def _mark_execution_revalidation_reversed(root: Path, receipt: dict[str, Any], rollback_queue_item: dict[str, Any]) -> None:
    queue_item_id = str(receipt.get("revalidation_queue_item_id") or "")
    if not queue_item_id:
        return
    path = _queue_item_path(root, queue_item_id)
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return
    payload["reversed_by_execution_id"] = receipt.get("execution_id")
    payload["superseded_by_queue_item_id"] = rollback_queue_item.get("queue_item_id")
    payload["updated_at_utc"] = _now()
    _atomic_write_json(path, payload)


def _receipt_after_state_current(receipt: dict[str, Any], root: Path) -> bool:
    for relative, expected_hash in (receipt.get("after_state_hashes") or {}).items():
        if not str(relative).endswith(".json"):
            continue
        if str(relative).startswith(f"{QUEUE_DIR}/"):
            continue
        path = root / str(relative)
        payload = _read_json(path)
        if payload is None or _json_hash(payload) != expected_hash:
            return False
    return True


def _has_later_successful_overlap(root: Path, receipt: dict[str, Any]) -> bool:
    completed_at = str(receipt.get("completed_at_utc") or "")
    updated_ids = set(str(item) for item in receipt.get("updated_record_ids", []))
    for item in list_locator_migration_execution_receipts(document_id=str(receipt.get("document_id") or ""), limit=500, root=root).get("items", []):
        if item.get("execution_id") == receipt.get("execution_id"):
            continue
        if item.get("status") != STATUS_COMPLETED:
            continue
        if str(item.get("completed_at_utc") or "") <= completed_at:
            continue
        if updated_ids.intersection(str(record_id) for record_id in item.get("updated_record_ids", [])):
            return True
    return False


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
