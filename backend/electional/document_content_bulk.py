"""Bulk curation plans, review queue, and one-shot commit."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from .document_content_curation import (
    CURATION_SCHEMA_VERSION,
    _atomic_write_json,
    _apply_change_to_overlay_state,
    _build_effective_state,
    _change_type_counts,
    _ensure_document_content_curation_dirs,
    _new_overlay,
    _normalize_range_value,
    _normalize_title,
    _now,
    _overlay_change_count,
    _overlay_changes_from_state,
    _read_json,
    _safe_revision,
    _sanitize_public_report,
    _save_curation,
    _validate_overlay_payload,
    load_document_content_curation,
    normalize_manual_topic_tag,
    validate_content_curation_change,
)
from .document_content_history import save_curation_history_snapshot
from .document_content_map import load_document_content_map
from .source_documents import SOURCE_DOCUMENT_ROOT

BULK_SCHEMA_VERSION = "document_content_bulk_v1"
BULK_DIR = "document_content_bulk"
BULK_INDEX = "document_content_bulk_index.json"
BULK_STATUSES = {"draft", "ready_for_review", "approved", "rejected", "stale", "invalid", "unchanged", "committed", "failed", "unknown"}
FINAL_BATCH_STATUSES = {"committed", "rejected"}
EDITABLE_BATCH_STATUSES = {"draft", "ready_for_review", "approved", "unchanged", "stale", "invalid", "failed", "unknown"}
SUPPORTED_BULK_OPERATION_TYPES = {
    "add_tag_many",
    "remove_tag_many",
    "assign_chunks_to_section",
    "assign_chunks_to_sections",
    "unassign_chunks",
    "rename_chapters",
    "rename_sections",
    "set_chapter_ranges",
    "set_section_ranges",
}


def create_document_content_bulk_plan(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_bulk_dirs(root)
    content_map = load_document_content_map(document_id, root=base).get("content_map")
    current_overlay = load_document_content_curation(document_id, root=base).get("curation")
    batch_id = _batch_id(document_id, content_map, current_overlay)
    existing = _read_json(_bulk_plan_path(base, document_id, batch_id))
    if isinstance(existing, dict):
        return {"document_id": document_id, "batch_id": batch_id, "status": existing.get("status", "unknown"), "plan": existing, "warnings": [], "blockers": []}
    plan = {
        "schema_version": BULK_SCHEMA_VERSION,
        "batch_id": batch_id,
        "document_id": document_id,
        "base_content_map_fingerprint": (content_map or {}).get("document_scoped_fingerprint"),
        "source_revision": (content_map or {}).get("source_revision"),
        "base_curation_revision": _safe_revision((current_overlay or {}).get("curation_revision")),
        "created_at_utc": _now(),
        "updated_at_utc": _now(),
        "batch_revision": 1,
        "status": "draft",
        "operations": [],
        "operation_count": 0,
        "effective_change_count": 0,
        "unchanged_operation_count": 0,
        "warnings": [],
        "blockers": [],
        "preview_summary": {},
        "validation_result": {},
        "approval_metadata": None,
        "rejection_metadata": None,
        "commit_metadata": None,
        "provenance": {},
    }
    _save_bulk_plan(base, plan)
    return {"document_id": document_id, "batch_id": batch_id, "status": "draft", "plan": plan, "warnings": [], "blockers": []}


def load_document_content_bulk_plan(document_id: str, batch_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_bulk_dirs(root)
    payload = _read_json(_bulk_plan_path(base, document_id, batch_id))
    if not isinstance(payload, dict):
        return {"document_id": document_id, "batch_id": batch_id, "status": "not_found", "plan": None, "warnings": [], "blockers": ["batch_not_found"]}
    if str(payload.get("document_id") or "") != document_id:
        return {"document_id": document_id, "batch_id": batch_id, "status": "invalid", "plan": payload, "warnings": [], "blockers": ["document_id_mismatch"]}
    return {"document_id": document_id, "batch_id": batch_id, "status": "loaded", "plan": payload, "warnings": [], "blockers": []}


def list_document_content_bulk_plans(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_bulk_dirs(root)
    folder = base / BULK_DIR / document_id
    items = []
    warnings = []
    if folder.exists():
        for path in sorted(folder.glob("*.json")):
            payload = _read_json(path)
            if not isinstance(payload, dict):
                warnings.append(f"corrupt_batch:{path.stem}")
                continue
            items.append(_queue_item(payload))
    items.sort(key=lambda item: (item.get("status") != "ready_for_review", item.get("created_at_utc") or "", item.get("batch_id") or ""))
    return {"document_id": document_id, "count": len(items), "items": items, "warnings": warnings}


def list_document_content_bulk_review_queue(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    listing = list_document_content_bulk_plans(document_id, root=root)
    actionable = next((item for item in listing.get("items", []) if item.get("status") in {"ready_for_review", "approved"}), None)
    return {"document_id": document_id, "count": listing.get("count", 0), "items": listing.get("items", []), "warnings": listing.get("warnings", []), "actionable_batch_id": (actionable or {}).get("batch_id")}


def add_document_content_bulk_operation(document_id: str, batch_id: str, operation: dict[str, Any], *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    return _edit_bulk_plan(document_id, batch_id, "add", operation=operation, root=root)


def remove_document_content_bulk_operation(document_id: str, batch_id: str, operation_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    return _edit_bulk_plan(document_id, batch_id, "remove", operation_id=operation_id, root=root)


def replace_document_content_bulk_operation(document_id: str, batch_id: str, operation_id: str, operation: dict[str, Any], *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    return _edit_bulk_plan(document_id, batch_id, "replace", operation_id=operation_id, operation=operation, root=root)


def clear_document_content_bulk_operations(document_id: str, batch_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_bulk_dirs(root)
    loaded = load_document_content_bulk_plan(document_id, batch_id, root=base)
    if loaded["status"] != "loaded":
        return loaded
    plan = copy.deepcopy(loaded["plan"] or {})
    if plan.get("status") in FINAL_BATCH_STATUSES:
        return {"document_id": document_id, "batch_id": batch_id, "status": plan.get("status"), "plan": plan, "warnings": [], "blockers": [f"batch_{plan.get('status')}"]}
    if not plan.get("operations"):
        return {"document_id": document_id, "batch_id": batch_id, "status": "unchanged", "plan": plan, "warnings": [], "blockers": []}
    plan["operations"] = []
    plan["operation_count"] = 0
    plan["effective_change_count"] = 0
    plan["unchanged_operation_count"] = 0
    plan["preview_summary"] = {}
    plan["validation_result"] = {}
    plan["warnings"] = []
    plan["blockers"] = []
    plan["approval_metadata"] = None
    plan["status"] = "draft"
    plan["batch_revision"] = int(plan.get("batch_revision") or 0) + 1
    plan["updated_at_utc"] = _now()
    _save_bulk_plan(base, plan)
    return {"document_id": document_id, "batch_id": batch_id, "status": "draft", "plan": plan, "warnings": [], "blockers": []}


def preview_document_content_bulk_plan(document_id: str, batch_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_bulk_dirs(root)
    loaded = load_document_content_bulk_plan(document_id, batch_id, root=base)
    if loaded["status"] != "loaded":
        return loaded
    plan = copy.deepcopy(loaded["plan"] or {})
    preview = _evaluate_bulk_plan(plan, base)
    changed = _preview_state(plan) != _preview_state(preview)
    preview["updated_at_utc"] = _now() if changed else plan.get("updated_at_utc")
    _save_bulk_plan(base, preview)
    return {"document_id": document_id, "batch_id": batch_id, "status": preview.get("status"), "plan": preview, "warnings": preview.get("warnings", []), "blockers": preview.get("blockers", []), "preview_summary": preview.get("preview_summary", {})}


def validate_document_content_bulk_plan(document_id: str, batch_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    preview = preview_document_content_bulk_plan(document_id, batch_id, root=root)
    plan = preview.get("plan") or {}
    return {"document_id": document_id, "batch_id": batch_id, "status": preview.get("status"), "validation_result": plan.get("validation_result", {}), "warnings": preview.get("warnings", []), "blockers": preview.get("blockers", [])}


def approve_document_content_bulk_plan(document_id: str, batch_id: str, reviewer_label: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_bulk_dirs(root)
    preview = preview_document_content_bulk_plan(document_id, batch_id, root=base)
    if preview.get("status") != "ready_for_review":
        return {"document_id": document_id, "batch_id": batch_id, "status": preview.get("status"), "warnings": preview.get("warnings", []), "blockers": preview.get("blockers", []) or ["batch_not_ready_for_review"]}
    plan = preview.get("plan") or {}
    summary = plan.get("preview_summary") or {}
    if not summary.get("preview_fingerprint"):
        return {"document_id": document_id, "batch_id": batch_id, "status": "invalid", "warnings": [], "blockers": ["preview_fingerprint_missing"]}
    plan["approval_metadata"] = {
        "approved_batch_revision": plan.get("batch_revision"),
        "approved_at_utc": _now(),
        "reviewer_label": str(reviewer_label or "").strip() or None,
        "preview_fingerprint": summary.get("preview_fingerprint"),
        "expected_base_curation_revision": plan.get("base_curation_revision"),
        "expected_resulting_curation_revision": summary.get("expected_next_curation_revision"),
    }
    plan["status"] = "approved"
    plan["updated_at_utc"] = _now()
    _save_bulk_plan(base, plan)
    return {"document_id": document_id, "batch_id": batch_id, "status": "approved", "plan": plan, "warnings": [], "blockers": []}


def reject_document_content_bulk_plan(document_id: str, batch_id: str, reason: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_bulk_dirs(root)
    loaded = load_document_content_bulk_plan(document_id, batch_id, root=base)
    if loaded["status"] != "loaded":
        return loaded
    plan = loaded["plan"] or {}
    normalized_reason = str(reason or "").strip() or None
    current = plan.get("rejection_metadata") or {}
    if plan.get("status") == "rejected" and current.get("reason") == normalized_reason:
        return {"document_id": document_id, "batch_id": batch_id, "status": "unchanged", "plan": plan, "warnings": [], "blockers": []}
    plan["rejection_metadata"] = {"rejected_at_utc": _now(), "reason": normalized_reason}
    plan["status"] = "rejected"
    plan["updated_at_utc"] = _now()
    _save_bulk_plan(base, plan)
    return {"document_id": document_id, "batch_id": batch_id, "status": "rejected", "plan": plan, "warnings": [], "blockers": []}


def refresh_document_content_bulk_plan(document_id: str, batch_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_bulk_dirs(root)
    loaded = load_document_content_bulk_plan(document_id, batch_id, root=base)
    if loaded["status"] != "loaded":
        return loaded
    plan = copy.deepcopy(loaded["plan"] or {})
    if plan.get("status") in FINAL_BATCH_STATUSES:
        return {"document_id": document_id, "batch_id": batch_id, "status": plan.get("status"), "plan": plan, "warnings": [], "blockers": []}
    content_map = load_document_content_map(document_id, root=base).get("content_map")
    overlay = load_document_content_curation(document_id, root=base).get("curation")
    plan["base_content_map_fingerprint"] = (content_map or {}).get("document_scoped_fingerprint")
    plan["source_revision"] = (content_map or {}).get("source_revision")
    plan["base_curation_revision"] = _safe_revision((overlay or {}).get("curation_revision"))
    plan["approval_metadata"] = None
    plan["rejection_metadata"] = None
    rebuilt = _evaluate_bulk_plan(plan, base)
    if _preview_state(rebuilt) != _preview_state(loaded["plan"] or {}):
        rebuilt["batch_revision"] = int(plan.get("batch_revision") or 0) + 1
        rebuilt["updated_at_utc"] = _now()
    _save_bulk_plan(base, rebuilt)
    return {"document_id": document_id, "batch_id": batch_id, "status": rebuilt.get("status"), "plan": rebuilt, "warnings": rebuilt.get("warnings", []), "blockers": rebuilt.get("blockers", [])}


def commit_document_content_bulk_plan(document_id: str, batch_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_bulk_dirs(root)
    loaded = load_document_content_bulk_plan(document_id, batch_id, root=base)
    if loaded["status"] != "loaded":
        return {"document_id": document_id, "batch_id": batch_id, "status": loaded.get("status"), "warnings": loaded.get("warnings", []), "blockers": loaded.get("blockers", [])}
    plan = loaded["plan"] or {}
    if plan.get("status") == "committed":
        return {"document_id": document_id, "batch_id": batch_id, "status": "conflict", "warnings": [], "blockers": ["batch_already_committed"]}
    if plan.get("status") == "rejected":
        return {"document_id": document_id, "batch_id": batch_id, "status": "failed", "warnings": [], "blockers": ["batch_rejected"]}
    approval = plan.get("approval_metadata") or {}
    if plan.get("status") != "approved":
        return {"document_id": document_id, "batch_id": batch_id, "status": plan.get("status"), "warnings": plan.get("warnings", []), "blockers": plan.get("blockers", []) or ["batch_not_approved"]}
    if approval.get("approved_batch_revision") != plan.get("batch_revision"):
        return {"document_id": document_id, "batch_id": batch_id, "status": "stale", "warnings": [], "blockers": ["approval_revision_mismatch"]}
    refreshed = _evaluate_bulk_plan(copy.deepcopy(plan), base)
    if refreshed.get("status") == "stale":
        refreshed["updated_at_utc"] = _now()
        _save_bulk_plan(base, refreshed)
        return {"document_id": document_id, "batch_id": batch_id, "status": "stale", "warnings": refreshed.get("warnings", []), "blockers": refreshed.get("blockers", [])}
    if refreshed.get("status") not in {"ready_for_review", "approved"}:
        refreshed["status"] = "failed" if refreshed.get("status") not in BULK_STATUSES else refreshed.get("status")
        refreshed["updated_at_utc"] = _now()
        _save_bulk_plan(base, refreshed)
        return {"document_id": document_id, "batch_id": batch_id, "status": refreshed.get("status"), "warnings": refreshed.get("warnings", []), "blockers": refreshed.get("blockers", [])}
    if approval.get("preview_fingerprint") != (refreshed.get("preview_summary") or {}).get("preview_fingerprint"):
        refreshed["status"] = "stale"
        refreshed["blockers"] = list(dict.fromkeys([*(refreshed.get("blockers") or []), "preview_fingerprint_changed"]))
        refreshed["updated_at_utc"] = _now()
        _save_bulk_plan(base, refreshed)
        return {"document_id": document_id, "batch_id": batch_id, "status": "stale", "warnings": refreshed.get("warnings", []), "blockers": refreshed.get("blockers", [])}
    current_map = load_document_content_map(document_id, root=base).get("content_map")
    current_overlay = load_document_content_curation(document_id, root=base).get("curation")
    if not isinstance(current_map, dict):
        return {"document_id": document_id, "batch_id": batch_id, "status": "failed", "warnings": [], "blockers": ["content_map_missing"]}
    current_bulk_provenance = (current_overlay or {}).get("bulk_provenance") if isinstance(current_overlay, dict) else {}
    if isinstance(current_bulk_provenance, dict) and current_bulk_provenance.get("bulk_batch_id") == batch_id and _safe_revision(current_bulk_provenance.get("bulk_batch_revision")) == _safe_revision(refreshed.get("batch_revision")):
        refreshed["status"] = "committed"
        refreshed["commit_metadata"] = {
            "committed_at_utc": current_bulk_provenance.get("committed_at_utc"),
            "committed_revision": current_bulk_provenance.get("committed_revision"),
        }
        _save_bulk_plan(base, refreshed)
        from .document_content_integrity import rebuild_document_content_indexes

        rebuild_document_content_indexes(document_id, root=base)
        return {"document_id": document_id, "batch_id": batch_id, "status": "committed", "curation": current_overlay, "warnings": [], "blockers": []}
    previous_overlay = copy.deepcopy(current_overlay) if isinstance(current_overlay, dict) else None
    proposed = copy.deepcopy((refreshed.get("preview_summary") or {}).get("proposed_overlay") or {})
    previous_current_revision = _safe_revision((current_overlay or {}).get("curation_revision"))
    proposed["schema_version"] = CURATION_SCHEMA_VERSION
    proposed["document_id"] = document_id
    proposed["base_content_map_fingerprint"] = current_map.get("document_scoped_fingerprint")
    proposed["source_revision"] = current_map.get("source_revision")
    proposed["curation_revision"] = previous_current_revision + 1
    proposed["changes"] = _overlay_changes_from_state(proposed)
    proposed["updated_at_utc"] = _now()
    proposed["bulk_provenance"] = {
        "bulk_batch_id": batch_id,
        "bulk_batch_revision": refreshed.get("batch_revision"),
        "previous_current_revision": previous_current_revision,
        "committed_revision": previous_current_revision + 1,
        "committed_at_utc": _now(),
        "operation_count": refreshed.get("operation_count", 0),
        "effective_change_count": refreshed.get("effective_change_count", 0),
        "unchanged_operation_count": refreshed.get("unchanged_operation_count", 0),
        "operation_type_counts": dict((refreshed.get("preview_summary") or {}).get("operation_type_counts") or {}),
        "approval_timestamp": approval.get("approved_at_utc"),
        "preview_fingerprint": approval.get("preview_fingerprint"),
    }
    from .document_content_integrity import (
        _maybe_fail,
        finalize_document_content_transaction,
        prepare_document_content_transaction,
        record_document_content_transaction_checkpoint,
        rebuild_document_content_indexes,
    )

    transaction = prepare_document_content_transaction(
        "bulk_commit",
        document_id,
        expected_previous_revision=previous_current_revision,
        expected_new_revision=_safe_revision(proposed.get("curation_revision")),
        base_content_map_fingerprint=proposed.get("base_content_map_fingerprint"),
        source_revision=proposed.get("source_revision"),
        proposed_overlay_state=proposed,
        source_workflow_type="bulk_commit",
        source_workflow_id=batch_id,
        source_workflow_revision=_safe_revision(refreshed.get("batch_revision")),
        preview_fingerprint=approval.get("preview_fingerprint"),
        root=base,
    )
    transaction_id = transaction.get("transaction_id")
    validation = _validate_overlay_payload(current_map, proposed, base)
    if validation["status"] in {"invalid", "unknown"}:
        refreshed["status"] = "invalid"
        refreshed["blockers"] = validation["blockers"]
        _save_bulk_plan(base, refreshed)
        return {"document_id": document_id, "batch_id": batch_id, "status": "invalid", "warnings": validation["warnings"], "blockers": validation["blockers"]}
    if validation["status"] == "stale":
        refreshed["status"] = "stale"
        refreshed["blockers"] = validation["blockers"]
        _save_bulk_plan(base, refreshed)
        return {"document_id": document_id, "batch_id": batch_id, "status": "stale", "warnings": validation["warnings"], "blockers": validation["blockers"]}
    if previous_overlay and _overlay_state_payload(previous_overlay) == _overlay_state_payload(proposed):
        refreshed["status"] = "unchanged"
        _save_bulk_plan(base, refreshed)
        return {"document_id": document_id, "batch_id": batch_id, "status": "unchanged", "warnings": [], "blockers": [], "curation": previous_overlay}
    _maybe_fail("bulk_before_overlay")
    _save_curation(base, proposed)
    if transaction_id:
        record_document_content_transaction_checkpoint(document_id, transaction_id, "overlay_written", root=base)
    _maybe_fail("bulk_after_overlay")
    history_result = save_curation_history_snapshot(document_id, proposed, root=base)
    if history_result.get("status") == "conflict":
        if previous_overlay is not None:
            _save_curation(base, previous_overlay)
        refreshed["status"] = "failed"
        refreshed["blockers"] = history_result.get("blockers", [])
        _save_bulk_plan(base, refreshed)
        return {"document_id": document_id, "batch_id": batch_id, "status": "failed", "warnings": [], "blockers": history_result.get("blockers", [])}
    if transaction_id:
        record_document_content_transaction_checkpoint(document_id, transaction_id, "history_written", root=base)
    _maybe_fail("bulk_after_history")
    refreshed["status"] = "committed"
    refreshed["commit_metadata"] = {
        "committed_at_utc": _now(),
        "committed_revision": proposed.get("curation_revision"),
    }
    refreshed["updated_at_utc"] = _now()
    _save_bulk_plan(base, refreshed)
    if transaction_id:
        record_document_content_transaction_checkpoint(document_id, transaction_id, "source_status_written", root=base)
    _maybe_fail("bulk_after_source_status")
    rebuild_document_content_indexes(document_id, root=base)
    if transaction_id:
        record_document_content_transaction_checkpoint(document_id, transaction_id, "indexes_reconciled", root=base)
        finalize_document_content_transaction(document_id, transaction_id, "committed", root=base)
    return {"document_id": document_id, "batch_id": batch_id, "status": "committed", "curation": proposed, "warnings": [], "blockers": []}


def format_document_content_bulk_report(document_id: str, batch_id: str, public_safe: bool = True, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> str:
    loaded = load_document_content_bulk_plan(document_id, batch_id, root=root)
    if loaded["status"] != "loaded":
        text = f"Document Content Bulk Report\n\nDocument: {document_id}\nBatch: {batch_id}\nStatus: {loaded.get('status')}\nBlockers: {', '.join(loaded.get('blockers', [])) or 'none'}"
        return _sanitize_public_report(text) if public_safe else text
    plan = loaded["plan"] or {}
    summary = plan.get("preview_summary") or {}
    lines = [
        "Document Content Bulk Report",
        "",
        f"Document: {document_id}",
        f"Batch: {batch_id}",
        f"Batch Revision: {plan.get('batch_revision')}",
        f"Status: {plan.get('status')}",
        f"Operation Count: {plan.get('operation_count', 0)}",
        f"Effective Change Count: {plan.get('effective_change_count', 0)}",
        f"Unchanged Operation Count: {plan.get('unchanged_operation_count', 0)}",
        f"Warning Count: {len(plan.get('warnings', []))}",
        f"Blocker Count: {len(plan.get('blockers', []))}",
        f"Expected Next Curation Revision: {summary.get('expected_next_curation_revision')}",
        f"Operation Types: {', '.join(f'{k}={v}' for k, v in sorted((summary.get('operation_type_counts') or {}).items())) or 'none'}",
        f"Preview Fingerprint: {str(summary.get('preview_fingerprint') or 'unknown')[:20]}",
    ]
    return _sanitize_public_report("\n".join(lines)) if public_safe else "\n".join(lines)


def _edit_bulk_plan(document_id: str, batch_id: str, action: str, *, operation: dict[str, Any] | None = None, operation_id: str | None = None, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_bulk_dirs(root)
    loaded = load_document_content_bulk_plan(document_id, batch_id, root=base)
    if loaded["status"] != "loaded":
        return loaded
    plan = copy.deepcopy(loaded["plan"] or {})
    if plan.get("status") in FINAL_BATCH_STATUSES:
        return {"document_id": document_id, "batch_id": batch_id, "status": plan.get("status"), "plan": plan, "warnings": [], "blockers": [f"batch_{plan.get('status')}"]}
    operations = list(plan.get("operations") or [])
    if action == "add":
        normalization = _normalize_bulk_operation(document_id, operation or {}, base)
        if not normalization["valid"]:
            return {"document_id": document_id, "batch_id": batch_id, "status": "invalid", "plan": plan, "warnings": normalization["warnings"], "blockers": normalization["blockers"]}
        normalized = normalization["operation"]
        if any(item.get("operation_id") == normalized.get("operation_id") for item in operations):
            return {"document_id": document_id, "batch_id": batch_id, "status": "unchanged", "plan": plan, "warnings": [], "blockers": []}
        normalized["operation_order"] = len(operations) + 1
        operations.append(normalized)
    elif action == "remove":
        next_ops = [item for item in operations if item.get("operation_id") != operation_id]
        if len(next_ops) == len(operations):
            return {"document_id": document_id, "batch_id": batch_id, "status": "unchanged", "plan": plan, "warnings": [], "blockers": []}
        for index, item in enumerate(next_ops, start=1):
            item["operation_order"] = index
        operations = next_ops
    elif action == "replace":
        normalization = _normalize_bulk_operation(document_id, operation or {}, base)
        if not normalization["valid"]:
            return {"document_id": document_id, "batch_id": batch_id, "status": "invalid", "plan": plan, "warnings": normalization["warnings"], "blockers": normalization["blockers"]}
        normalized = normalization["operation"]
        replaced = False
        next_ops = []
        for item in operations:
            if item.get("operation_id") == operation_id:
                normalized["operation_order"] = item.get("operation_order")
                next_ops.append(normalized)
                replaced = True
            else:
                next_ops.append(item)
        if not replaced:
            return {"document_id": document_id, "batch_id": batch_id, "status": "invalid", "plan": plan, "warnings": [], "blockers": ["operation_not_found"]}
        operations = next_ops
    if _canonical(plan.get("operations") or []) == _canonical(operations):
        return {"document_id": document_id, "batch_id": batch_id, "status": "unchanged", "plan": plan, "warnings": [], "blockers": []}
    plan["operations"] = operations
    plan["operation_count"] = len(operations)
    plan["approval_metadata"] = None
    plan["rejection_metadata"] = None
    plan["status"] = "draft"
    plan["batch_revision"] = int(plan.get("batch_revision") or 0) + 1
    plan["updated_at_utc"] = _now()
    plan["preview_summary"] = {}
    plan["validation_result"] = {}
    plan["warnings"] = []
    plan["blockers"] = []
    _save_bulk_plan(base, plan)
    return {"document_id": document_id, "batch_id": batch_id, "status": "draft", "plan": plan, "warnings": [], "blockers": []}


def _normalize_bulk_operation(document_id: str, operation: dict[str, Any], root: Path) -> dict[str, Any]:
    operation_type = str(operation.get("operation_type") or "").strip()
    if operation_type not in SUPPORTED_BULK_OPERATION_TYPES:
        return {"valid": False, "operation": {}, "warnings": [], "blockers": ["unsupported_bulk_operation"]}
    subchanges: list[dict[str, Any]] = []
    warnings: list[str] = []
    blockers: list[str] = []
    normalized_value: dict[str, Any] = {}
    if operation_type in {"add_tag_many", "remove_tag_many"}:
        tag = normalize_manual_topic_tag(operation.get("tag"))
        chunk_ids = sorted({str(item).strip() for item in (operation.get("chunk_ids") or []) if str(item).strip()})
        normalized_value = {"tag": tag, "chunk_ids": chunk_ids}
        for chunk_id in chunk_ids:
            change = {"target_type": "chunk", "target_id": chunk_id, "operation": "add_tag" if operation_type == "add_tag_many" else "remove_tag", "value": {"tag": tag}}
            validation = validate_content_curation_change(document_id, change, root=root)
            warnings.extend(validation.get("warnings", []))
            blockers.extend(validation.get("blockers", []))
            if validation.get("valid"):
                subchanges.append(validation["normalized_change"])
    elif operation_type == "assign_chunks_to_section":
        section_id = str(operation.get("section_id") or "").strip()
        chunk_ids = sorted({str(item).strip() for item in (operation.get("chunk_ids") or []) if str(item).strip()})
        normalized_value = {"section_id": section_id, "chunk_ids": chunk_ids}
        for chunk_id in chunk_ids:
            change = {"target_type": "section", "target_id": section_id, "operation": "assign_chunk", "value": {"chunk_id": chunk_id}}
            validation = validate_content_curation_change(document_id, change, root=root)
            warnings.extend(validation.get("warnings", []))
            blockers.extend(validation.get("blockers", []))
            if validation.get("valid"):
                subchanges.append(validation["normalized_change"])
    elif operation_type == "assign_chunks_to_sections":
        assignments = {str(key).strip(): str(value).strip() for key, value in (operation.get("assignments") or {}).items() if str(key).strip() and str(value).strip()}
        normalized_value = {"assignments": dict(sorted(assignments.items()))}
        for chunk_id, section_id in sorted(assignments.items()):
            change = {"target_type": "section", "target_id": section_id, "operation": "assign_chunk", "value": {"chunk_id": chunk_id}}
            validation = validate_content_curation_change(document_id, change, root=root)
            warnings.extend(validation.get("warnings", []))
            blockers.extend(validation.get("blockers", []))
            if validation.get("valid"):
                subchanges.append(validation["normalized_change"])
    elif operation_type == "unassign_chunks":
        chunk_ids = sorted({str(item).strip() for item in (operation.get("chunk_ids") or []) if str(item).strip()})
        normalized_value = {"chunk_ids": chunk_ids}
        for chunk_id in chunk_ids:
            current_map = load_document_content_map(document_id, root=root).get("content_map")
            if not isinstance(current_map, dict):
                blockers.append("content_map_missing")
                continue
            effective = _build_effective_state(current_map, load_document_content_curation(document_id, root=root).get("curation") or _new_overlay(document_id, current_map), root)
            section_id = effective.get("chunk_assignments", {}).get(chunk_id)
            if not section_id:
                change = {"target_type": "section", "target_id": "missing_section", "operation": "unassign_chunk", "value": {"chunk_id": chunk_id}}
                validation = {"valid": False, "warnings": [], "blockers": ["chunk_not_assigned"]}
            else:
                change = {"target_type": "section", "target_id": section_id, "operation": "unassign_chunk", "value": {"chunk_id": chunk_id}}
                validation = validate_content_curation_change(document_id, change, root=root)
            warnings.extend(validation.get("warnings", []))
            blockers.extend(validation.get("blockers", []))
            if validation.get("valid"):
                subchanges.append(validation["normalized_change"])
    elif operation_type == "rename_chapters":
        renames = {str(key).strip(): _normalize_title(value) for key, value in (operation.get("renames") or {}).items() if str(key).strip()}
        normalized_value = {"renames": dict(sorted(renames.items()))}
        for target_id, title in sorted(renames.items()):
            change = {"target_type": "chapter", "target_id": target_id, "operation": "rename", "value": {"title": title}}
            validation = validate_content_curation_change(document_id, change, root=root)
            warnings.extend(validation.get("warnings", []))
            blockers.extend(validation.get("blockers", []))
            if validation.get("valid"):
                subchanges.append(validation["normalized_change"])
    elif operation_type == "rename_sections":
        renames = {str(key).strip(): _normalize_title(value) for key, value in (operation.get("renames") or {}).items() if str(key).strip()}
        normalized_value = {"renames": dict(sorted(renames.items()))}
        for target_id, title in sorted(renames.items()):
            change = {"target_type": "section", "target_id": target_id, "operation": "rename", "value": {"title": title}}
            validation = validate_content_curation_change(document_id, change, root=root)
            warnings.extend(validation.get("warnings", []))
            blockers.extend(validation.get("blockers", []))
            if validation.get("valid"):
                subchanges.append(validation["normalized_change"])
    elif operation_type in {"set_chapter_ranges", "set_section_ranges"}:
        ranges = {}
        target_type = "chapter" if operation_type == "set_chapter_ranges" else "section"
        for key, value in sorted((operation.get("ranges") or {}).items()):
            target_id = str(key).strip()
            range_value = _normalize_range_value(value if isinstance(value, dict) else {})
            ranges[target_id] = range_value.get("range")
            change = {"target_type": target_type, "target_id": target_id, "operation": "set_range", "value": range_value.get("range") or {}}
            validation = validate_content_curation_change(document_id, change, root=root)
            warnings.extend(validation.get("warnings", []))
            blockers.extend(validation.get("blockers", []))
            if validation.get("valid"):
                subchanges.append(validation["normalized_change"])
        normalized_value = {"ranges": ranges}
    normalized = {
        "operation_id": _operation_id(document_id, operation_type, normalized_value),
        "operation_type": operation_type,
        "normalized_value": normalized_value,
        "subchanges": subchanges,
        "validation_status": "invalid" if blockers else "valid",
        "effective_change_status": "unknown",
        "warnings": list(dict.fromkeys(warnings)),
        "blockers": list(dict.fromkeys(blockers)),
        "operation_order": int(operation.get("operation_order") or 0),
    }
    return {"valid": not blockers, "operation": normalized, "warnings": normalized["warnings"], "blockers": normalized["blockers"]}


def _evaluate_bulk_plan(plan: dict[str, Any], root: Path) -> dict[str, Any]:
    current_map = load_document_content_map(plan.get("document_id"), root=root).get("content_map")
    current_overlay = load_document_content_curation(plan.get("document_id"), root=root).get("curation")
    proposed_overlay = copy.deepcopy(current_overlay) if isinstance(current_overlay, dict) else (_new_overlay(plan.get("document_id"), current_map) if isinstance(current_map, dict) else {})
    warnings: list[str] = []
    blockers: list[str] = []
    stale_reasons: list[str] = []
    if str(plan.get("schema_version") or "") != BULK_SCHEMA_VERSION:
        plan["status"] = "unknown"
        plan["warnings"] = []
        plan["blockers"] = ["batch_schema_unknown"]
        return plan
    if not isinstance(current_map, dict):
        plan["status"] = "invalid"
        plan["warnings"] = []
        plan["blockers"] = ["content_map_missing"]
        return plan
    if plan.get("base_content_map_fingerprint") != current_map.get("document_scoped_fingerprint"):
        stale_reasons.append("base_content_map_changed")
    if plan.get("source_revision") != current_map.get("source_revision"):
        stale_reasons.append("source_revision_changed")
    if plan.get("base_curation_revision") != _safe_revision((current_overlay or {}).get("curation_revision")):
        stale_reasons.append("curation_revision_changed")
    operations = sorted((copy.deepcopy(plan.get("operations") or [])), key=lambda item: (int(item.get("operation_order") or 0), str(item.get("operation_id") or "")))
    seen_keys: dict[str, str] = {}
    effective_changes = 0
    unchanged_operations = 0
    operation_type_counts: dict[str, int] = {}
    for operation in operations:
        op_type = str(operation.get("operation_type") or "")
        operation_type_counts[op_type] = operation_type_counts.get(op_type, 0) + 1
        operation["warnings"] = list(operation.get("warnings", []))
        operation["blockers"] = list(operation.get("blockers", []))
        if operation.get("validation_status") == "invalid":
            blockers.extend(operation.get("blockers", []))
            operation["effective_change_status"] = "blocked"
            continue
        op_blockers = []
        op_changed = False
        for change in operation.get("subchanges", []):
            key = _change_conflict_key(change)
            serialized = _canonical(change)
            if key in seen_keys and seen_keys[key] != serialized:
                op_blockers.append("conflicting_duplicate_operation")
                continue
            seen_keys[key] = serialized
            effective_before = _build_effective_state(current_map, proposed_overlay, root)
            changed, change_warnings = _apply_change_to_overlay_state(current_map, proposed_overlay, change, effective_before)
            operation["warnings"] = list(dict.fromkeys([*operation.get("warnings", []), *change_warnings]))
            op_changed = op_changed or changed
        if op_blockers:
            operation["blockers"] = list(dict.fromkeys([*operation.get("blockers", []), *op_blockers]))
            blockers.extend(op_blockers)
            operation["validation_status"] = "invalid"
            operation["effective_change_status"] = "blocked"
        elif op_changed:
            operation["effective_change_status"] = "effective"
            effective_changes += 1
        else:
            operation["effective_change_status"] = "unchanged"
            unchanged_operations += 1
    if stale_reasons:
        plan["status"] = "stale"
        blockers.extend(stale_reasons)
    proposed_overlay["schema_version"] = CURATION_SCHEMA_VERSION
    proposed_overlay["document_id"] = plan.get("document_id")
    proposed_overlay["base_content_map_fingerprint"] = current_map.get("document_scoped_fingerprint")
    proposed_overlay["source_revision"] = current_map.get("source_revision")
    proposed_overlay["curation_revision"] = _safe_revision((current_overlay or {}).get("curation_revision"))
    proposed_overlay["changes"] = _overlay_changes_from_state(proposed_overlay)
    validation = _validate_overlay_payload(current_map, proposed_overlay, root)
    if validation["status"] in {"invalid", "unknown"}:
        blockers.extend(validation["blockers"])
    if validation["status"] == "stale":
        stale_reasons.extend(validation["stale_reasons"])
        blockers.extend(validation["blockers"])
    if blockers and plan.get("status") != "stale":
        plan["status"] = "invalid"
    elif plan.get("status") != "stale" and effective_changes == 0:
        plan["status"] = "unchanged"
    elif plan.get("status") != "stale":
        plan["status"] = "approved" if plan.get("approval_metadata") else "ready_for_review"
    plan["operations"] = operations
    plan["operation_count"] = len(operations)
    plan["effective_change_count"] = effective_changes
    plan["unchanged_operation_count"] = unchanged_operations
    plan["warnings"] = list(dict.fromkeys(warnings + validation.get("warnings", [])))
    plan["blockers"] = list(dict.fromkeys(blockers))
    plan["validation_result"] = {
        "status": plan.get("status"),
        "blockers": plan.get("blockers", []),
        "warnings": plan.get("warnings", []),
        "stale_reasons": list(dict.fromkeys(stale_reasons)),
    }
    plan["preview_summary"] = {
        "preview_fingerprint": _preview_fingerprint(proposed_overlay),
        "expected_next_curation_revision": _safe_revision((current_overlay or {}).get("curation_revision")) + (1 if effective_changes > 0 and not blockers and not stale_reasons else 0),
        "expected_history_snapshot_count": 1 if effective_changes > 0 and not blockers and not stale_reasons else 0,
        "operation_type_counts": operation_type_counts,
        "override_change_count": _overlay_change_count(proposed_overlay),
        "change_type_counts": _change_type_counts(proposed_overlay.get("changes", [])),
        "proposed_overlay": proposed_overlay,
    }
    return plan


def _queue_item(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "batch_id": payload.get("batch_id"),
        "document_id": payload.get("document_id"),
        "status": payload.get("status", "unknown"),
        "batch_revision": payload.get("batch_revision", 0),
        "operation_count": payload.get("operation_count", 0),
        "effective_change_count": payload.get("effective_change_count", 0),
        "blocker_count": len(payload.get("blockers", [])) if isinstance(payload.get("blockers"), list) else 0,
        "warning_count": len(payload.get("warnings", [])) if isinstance(payload.get("warnings"), list) else 0,
        "created_at_utc": payload.get("created_at_utc"),
        "updated_at_utc": payload.get("updated_at_utc"),
        "approval_timestamp": ((payload.get("approval_metadata") or {}).get("approved_at_utc")),
        "commit_revision": ((payload.get("commit_metadata") or {}).get("committed_revision")),
    }


def _preview_state(plan: dict[str, Any]) -> str:
    payload = {
        "status": plan.get("status"),
        "warnings": plan.get("warnings"),
        "blockers": plan.get("blockers"),
        "preview_summary": plan.get("preview_summary"),
        "validation_result": plan.get("validation_result"),
        "effective_change_count": plan.get("effective_change_count"),
        "unchanged_operation_count": plan.get("unchanged_operation_count"),
        "operations": plan.get("operations"),
    }
    return _canonical(payload)


def _change_conflict_key(change: dict[str, Any]) -> str:
    operation = str(change.get("operation") or "")
    target_type = str(change.get("target_type") or "")
    target_id = str(change.get("target_id") or "")
    value = change.get("value") if isinstance(change.get("value"), dict) else {}
    if operation in {"rename", "set_range"}:
        return f"{target_type}:{target_id}:{operation}"
    if operation in {"assign_chunk", "unassign_chunk"}:
        return f"chunk:{value.get('chunk_id')}:assignment_state"
    if operation in {"add_tag", "remove_tag"}:
        return f"chunk:{target_id}:tag:{value.get('tag')}"
    return _canonical(change)


def _overlay_state_payload(overlay: dict[str, Any]) -> str:
    return _canonical(
        {
            "chapter_title_overrides": overlay.get("chapter_title_overrides") or {},
            "chapter_range_overrides": overlay.get("chapter_range_overrides") or {},
            "section_title_overrides": overlay.get("section_title_overrides") or {},
            "section_range_overrides": overlay.get("section_range_overrides") or {},
            "chunk_assignment_overrides": overlay.get("chunk_assignment_overrides") or {},
            "chunk_unassignments": sorted(overlay.get("chunk_unassignments") or []),
            "manual_tag_additions": overlay.get("manual_tag_additions") or {},
            "manual_tag_removals": overlay.get("manual_tag_removals") or {},
        }
    )


def _save_bulk_plan(root: Path, payload: dict[str, Any]) -> None:
    _atomic_write_json(_bulk_plan_path(root, payload.get("document_id"), payload.get("batch_id")), payload)
    _update_bulk_index(root)


def _update_bulk_index(root: Path) -> None:
    entries = []
    for doc_dir in sorted((root / BULK_DIR).glob("*")):
        if not doc_dir.is_dir():
            continue
        for path in sorted(doc_dir.glob("*.json")):
            payload = _read_json(path)
            if isinstance(payload, dict):
                entries.append(_queue_item(payload))
    _atomic_write_json(root / "indexes" / BULK_INDEX, {"entries": entries, "updated_at_utc": _now()})


def _ensure_document_content_bulk_dirs(root: Path | str) -> Path:
    base = _ensure_document_content_curation_dirs(root)
    (base / BULK_DIR).mkdir(parents=True, exist_ok=True)
    index_path = base / "indexes" / BULK_INDEX
    if not index_path.exists():
        _atomic_write_json(index_path, {"entries": [], "updated_at_utc": _now()})
    return base


def _bulk_plan_path(root: Path, document_id: str, batch_id: str) -> Path:
    return root / BULK_DIR / document_id / f"{batch_id}.json"


def _batch_id(document_id: str, content_map: dict[str, Any] | None, overlay: dict[str, Any] | None) -> str:
    digest = hashlib.sha256(
        json.dumps(
            {
                "document_id": document_id,
                "base_content_map_fingerprint": (content_map or {}).get("document_scoped_fingerprint"),
                "source_revision": (content_map or {}).get("source_revision"),
                "base_curation_revision": _safe_revision((overlay or {}).get("curation_revision")),
            },
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()[:10]
    return f"bulk_{document_id}_{digest}"


def _operation_id(document_id: str, operation_type: str, normalized_value: dict[str, Any]) -> str:
    digest = hashlib.sha256(json.dumps({"document_id": document_id, "operation_type": operation_type, "normalized_value": normalized_value}, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:10]
    return f"op_{digest}"


def _preview_fingerprint(proposed_overlay: dict[str, Any]) -> str:
    return hashlib.sha256(_overlay_state_payload(proposed_overlay).encode("utf-8")).hexdigest()[:16]


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
