"""Manual, non-destructive curation overlays for detected document content maps."""

from __future__ import annotations

import copy
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .document_content_map import ensure_document_content_map_dirs, load_document_content_map
from .source_documents import SOURCE_DOCUMENT_ROOT
from .source_knowledge import load_chunks

CURATION_SCHEMA_VERSION = "document_content_curation_v2"
LEGACY_CURATION_SCHEMA_VERSIONS = {"document_content_curation_v1"}
CURATED_MAP_SCHEMA_VERSION = "curated_document_content_map_v1"
CURATION_DIR = "document_content_curation"
CURATION_INDEX = "document_content_curation_index.json"
READINESS_STATUSES = {"ready", "ready_with_warnings", "not_ready", "stale", "invalid", "unknown"}
SUPPORTED_OPERATIONS = {
    ("chapter", "rename"),
    ("chapter", "set_range"),
    ("section", "rename"),
    ("section", "set_range"),
    ("section", "assign_chunk"),
    ("section", "unassign_chunk"),
    ("chunk", "add_tag"),
    ("chunk", "remove_tag"),
}
UNSAFE_REPORT_PATTERNS = (
    re.compile(r"[A-Za-z]:\\"),
    re.compile(r"/Users/"),
    re.compile(r"/home/"),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"api[_ -]?key", re.IGNORECASE),
    re.compile(r"stack trace", re.IGNORECASE),
)


def build_document_content_curation_workspace(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = _ensure_document_content_curation_dirs(root)
    content_map = load_document_content_map(document_id, root=base).get("content_map")
    overlay = load_document_content_curation(document_id, root=base).get("curation")
    readiness = get_document_content_curation_readiness(document_id, root=base)
    if not isinstance(content_map, dict):
        return {
            "document_id": document_id,
            "source_revision": None,
            "base_content_map_fingerprint": None,
            "curation_revision": int((overlay or {}).get("curation_revision") or 0),
            "curation_status": "not_started" if not overlay else readiness.get("status", "unknown"),
            "chapter_count": 0,
            "section_count": 0,
            "assigned_chunk_count": 0,
            "unassigned_chunk_count": 0,
            "existing_override_count": _overlay_change_count(overlay or {}),
            "chapters": [],
            "unassigned_chunk_ids": [],
            "warnings": list(readiness.get("warnings", [])),
            "recommended_action": readiness.get("recommended_action"),
        }
    return {
        "document_id": document_id,
        "source_revision": content_map.get("source_revision"),
        "base_content_map_fingerprint": content_map.get("document_scoped_fingerprint"),
        "curation_revision": int((overlay or {}).get("curation_revision") or 0),
        "curation_status": "not_started" if not overlay else readiness.get("status", "unknown"),
        "chapter_count": len(content_map.get("chapters", [])),
        "section_count": int(content_map.get("section_count") or len(content_map.get("sections", []))),
        "assigned_chunk_count": int(content_map.get("chunk_count", 0) or 0) - len(content_map.get("unassigned_chunk_ids", [])),
        "unassigned_chunk_count": len(content_map.get("unassigned_chunk_ids", [])),
        "existing_override_count": _overlay_change_count(overlay or {}),
        "chapters": content_map.get("chapters", []),
        "unassigned_chunk_ids": content_map.get("unassigned_chunk_ids", []),
        "warnings": list(readiness.get("warnings", [])),
        "recommended_action": readiness.get("recommended_action"),
    }


def validate_content_curation_change(document_id: str, change: dict, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = _ensure_document_content_curation_dirs(root)
    content_map = load_document_content_map(document_id, root=base).get("content_map")
    if not isinstance(content_map, dict):
        return {"valid": False, "normalized_change": {}, "warnings": [], "blockers": ["content_map_missing"]}
    if document_id != str(content_map.get("document_id") or ""):
        return {"valid": False, "normalized_change": {}, "warnings": [], "blockers": ["document_id_mismatch"]}
    lookup = _map_lookup(content_map, base)
    blockers: list[str] = []
    warnings: list[str] = []
    target_type = str(change.get("target_type") or "").strip().lower()
    target_id = str(change.get("target_id") or "").strip()
    operation = str(change.get("operation") or "").strip().lower()
    if (target_type, operation) not in SUPPORTED_OPERATIONS:
        blockers.append("unsupported_operation")
    if target_type == "chapter" and target_id not in lookup["chapters"]:
        blockers.append("unknown_chapter_id")
    if target_type == "section" and target_id not in lookup["sections"]:
        blockers.append("unknown_section_id")
    if target_type == "chunk" and target_id not in lookup["chunks"]:
        blockers.append("unknown_chunk_id")
    normalized = {
        "target_type": target_type,
        "target_id": target_id,
        "operation": operation,
        "value": {},
        "note": str(change.get("note") or "").strip() or None,
    }
    value = change.get("value") if isinstance(change.get("value"), dict) else {}
    if operation == "rename":
        title = _normalize_title(value.get("title"))
        if not title:
            blockers.append("title_required")
        normalized["value"] = {"title": title}
    elif operation == "set_range":
        range_value = _normalize_range_value(value)
        blockers.extend(range_value["blockers"])
        if not range_value["blockers"]:
            range_data = range_value["range"]
            range_blockers, range_warnings = _validate_range_against_map(content_map, lookup, target_type, target_id, range_data)
            blockers.extend(range_blockers)
            warnings.extend(range_warnings)
            normalized["value"] = range_data
    elif operation in {"assign_chunk", "unassign_chunk"}:
        chunk_id = str(value.get("chunk_id") or "").strip()
        if not chunk_id:
            blockers.append("chunk_id_required")
        elif chunk_id not in lookup["chunks"]:
            blockers.append("unknown_chunk_id")
        elif str(lookup["chunks"][chunk_id].get("document_id") or "") != document_id:
            blockers.append("chunk_from_other_document")
        normalized["value"] = {"chunk_id": chunk_id}
    elif operation in {"add_tag", "remove_tag"}:
        tag = normalize_manual_topic_tag(value.get("tag"))
        if not tag:
            blockers.append("tag_empty")
        normalized["value"] = {"tag": tag}
    return {"valid": not blockers, "normalized_change": normalized if not blockers else {}, "warnings": list(dict.fromkeys(warnings)), "blockers": list(dict.fromkeys(blockers))}


def save_document_content_curation_change(document_id: str, change: dict, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = _ensure_document_content_curation_dirs(root)
    validation = validate_content_curation_change(document_id, change, root=base)
    if not validation.get("valid"):
        return {"document_id": document_id, "status": "rejected", "curation": load_document_content_curation(document_id, root=base).get("curation"), "warnings": validation.get("warnings", []), "blockers": validation.get("blockers", [])}
    content_map = load_document_content_map(document_id, root=base).get("content_map")
    if not isinstance(content_map, dict):
        return {"document_id": document_id, "status": "rejected", "curation": None, "warnings": [], "blockers": ["content_map_missing"]}
    loaded_existing = load_document_content_curation(document_id, root=base).get("curation")
    existing = loaded_existing or _new_overlay(document_id, content_map)
    effective_before = _build_effective_state(content_map, existing, base)
    next_overlay = copy.deepcopy(existing)
    changed, change_warnings = _apply_change_to_overlay_state(content_map, next_overlay, validation["normalized_change"], effective_before)
    if not changed:
        return {"document_id": document_id, "status": "unchanged", "curation": loaded_existing, "warnings": list(dict.fromkeys([*validation.get("warnings", []), *change_warnings])), "blockers": []}
    next_overlay["schema_version"] = CURATION_SCHEMA_VERSION
    next_overlay["document_id"] = document_id
    next_overlay["base_content_map_fingerprint"] = content_map.get("document_scoped_fingerprint")
    next_overlay["source_revision"] = content_map.get("source_revision")
    next_overlay["curation_revision"] = int(existing.get("curation_revision") or 0) + 1
    next_overlay["changes"] = _overlay_changes_from_state(next_overlay)
    next_overlay["updated_at_utc"] = _now()
    overlay_validation = _validate_overlay_payload(content_map, next_overlay, base)
    if overlay_validation["status"] == "invalid":
        return {"document_id": document_id, "status": "rejected", "curation": existing, "warnings": [], "blockers": overlay_validation["invalid_reasons"]}
    from .document_content_integrity import (
        _maybe_fail,
        finalize_document_content_transaction,
        prepare_document_content_transaction,
        record_document_content_transaction_checkpoint,
        rebuild_document_content_indexes,
    )

    transaction = prepare_document_content_transaction(
        "curation_change",
        document_id,
        expected_previous_revision=_safe_revision(existing.get("curation_revision")),
        expected_new_revision=_safe_revision(next_overlay.get("curation_revision")),
        base_content_map_fingerprint=next_overlay.get("base_content_map_fingerprint"),
        source_revision=next_overlay.get("source_revision"),
        proposed_overlay_state=next_overlay,
        root=base,
    )
    transaction_id = transaction.get("transaction_id")
    _maybe_fail("curation_before_overlay")
    _save_curation(base, next_overlay)
    if transaction_id:
        record_document_content_transaction_checkpoint(document_id, transaction_id, "overlay_written", root=base)
    _maybe_fail("curation_after_overlay")
    from .document_content_history import save_curation_history_snapshot

    history_result = save_curation_history_snapshot(document_id, next_overlay, root=base)
    if history_result.get("status") == "conflict":
        if loaded_existing is not None:
            _save_curation(base, loaded_existing)
        else:
            try:
                _curation_path(base, document_id).unlink(missing_ok=True)
            except Exception:
                pass
        return {"document_id": document_id, "status": "rejected", "curation": existing if loaded_existing is not None else None, "warnings": [], "blockers": history_result.get("blockers", [])}
    if transaction_id:
        record_document_content_transaction_checkpoint(document_id, transaction_id, "history_written", root=base)
    _maybe_fail("curation_after_history")
    rebuild_document_content_indexes(document_id, root=base)
    if transaction_id:
        record_document_content_transaction_checkpoint(document_id, transaction_id, "indexes_reconciled", root=base)
        finalize_document_content_transaction(document_id, transaction_id, "committed", root=base)
    return {"document_id": document_id, "status": "saved", "curation": next_overlay, "warnings": list(dict.fromkeys([*validation.get("warnings", []), *change_warnings])), "blockers": []}


def load_document_content_curation(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    path = _curation_path(_ensure_document_content_curation_dirs(root), document_id)
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return {"document_id": document_id, "status": "not_found", "curation": None, "warnings": []}
    return {"document_id": document_id, "status": "loaded", "curation": payload, "warnings": []}


def build_curated_document_content_map(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = _ensure_document_content_curation_dirs(root)
    content_map = load_document_content_map(document_id, root=base).get("content_map")
    overlay = load_document_content_curation(document_id, root=base).get("curation")
    readiness = get_document_content_curation_readiness(document_id, root=base)
    if not isinstance(content_map, dict):
        return {
            "schema_version": CURATED_MAP_SCHEMA_VERSION,
            "document_id": document_id,
            "detected_base_fingerprint": None,
            "source_revision": None,
            "curation_revision": int((overlay or {}).get("curation_revision") or 0),
            "readiness_status": readiness.get("status", "not_ready"),
            "curation_applied": False,
            "detected_fallback_used": False,
            "warnings": list(readiness.get("warnings", [])),
            "stale_reasons": [],
            "invalid_reasons": [],
            "chapters": [],
            "sections": [],
            "effective_chunk_assignments": {},
            "effective_chunk_topic_tags": {},
            "manual_tag_count": 0,
        }
    curated = copy.deepcopy(content_map)
    curated["schema_version"] = CURATED_MAP_SCHEMA_VERSION
    curated["detected_base_fingerprint"] = content_map.get("document_scoped_fingerprint")
    curated["source_revision"] = content_map.get("source_revision")
    curated["curation_revision"] = _safe_revision((overlay or {}).get("curation_revision"))
    curated["readiness_status"] = readiness.get("status", "unknown")
    curated["curation_applied"] = False
    curated["detected_fallback_used"] = False
    curated["warnings"] = list(readiness.get("warnings", []))
    curated["stale_reasons"] = list(readiness.get("stale_reasons", []))
    curated["invalid_reasons"] = list(readiness.get("invalid_reasons", []))
    if not overlay:
        curated["effective_chunk_assignments"] = _chunk_assignment_lookup(curated)
        curated["effective_chunk_topic_tags"] = _chunk_topic_tag_lookup(curated)
        curated["manual_tag_count"] = 0
        return curated
    if readiness.get("status") in {"stale", "invalid", "not_ready", "unknown"}:
        curated["detected_fallback_used"] = bool(overlay)
        curated["effective_chunk_assignments"] = _chunk_assignment_lookup(curated)
        curated["effective_chunk_topic_tags"] = _chunk_topic_tag_lookup(curated)
        curated["manual_tag_count"] = 0
        return curated
    _apply_overlay_to_curated_map(curated, overlay)
    curated["curation_applied"] = True
    curated["effective_chunk_assignments"] = _chunk_assignment_lookup(curated)
    curated["effective_chunk_topic_tags"] = _chunk_topic_tag_lookup(curated)
    curated["manual_tag_count"] = sum(len(tags) for tags in (overlay.get("manual_tag_additions") or {}).values() if isinstance(tags, list))
    return curated


def get_document_content_curation_readiness(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = _ensure_document_content_curation_dirs(root)
    content_map = load_document_content_map(document_id, root=base).get("content_map")
    overlay = load_document_content_curation(document_id, root=base).get("curation")
    if not isinstance(content_map, dict):
        return {
            "document_id": document_id,
            "status": "not_ready",
            "base_fingerprint_current": False,
            "source_revision_current": False,
            "valid_change_count": 0,
            "invalid_change_count": 0,
            "blockers": ["content_map_missing"],
            "warnings": [],
            "stale_reasons": [],
            "invalid_reasons": [],
            "recommended_action": "Build the detected content map before applying curation.",
        }
    if not overlay:
        return {
            "document_id": document_id,
            "status": "not_ready",
            "base_fingerprint_current": True,
            "source_revision_current": True,
            "valid_change_count": 0,
            "invalid_change_count": 0,
            "blockers": ["curation_not_started"],
            "warnings": [],
            "stale_reasons": [],
            "invalid_reasons": [],
            "recommended_action": "Create a manual curation override to build a curated view.",
        }
    validation = _validate_overlay_payload(content_map, overlay, base)
    valid_change_count = _overlay_change_count(overlay) if validation["status"] in {"ready", "ready_with_warnings"} else 0
    invalid_change_count = _overlay_change_count(overlay) if validation["status"] == "invalid" else 0
    return {
        "document_id": document_id,
        "status": validation["status"],
        "base_fingerprint_current": validation["base_fingerprint_current"],
        "source_revision_current": validation["source_revision_current"],
        "valid_change_count": valid_change_count,
        "invalid_change_count": invalid_change_count,
        "blockers": list(validation["blockers"]),
        "warnings": list(validation["warnings"]),
        "stale_reasons": list(validation["stale_reasons"]),
        "invalid_reasons": list(validation["invalid_reasons"]),
        "recommended_action": validation["recommended_action"],
    }


def list_document_content_curations(limit: int = 100, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = _ensure_document_content_curation_dirs(root)
    entries = []
    for path in sorted((base / CURATION_DIR).glob("*.json"))[: max(0, int(limit or 0))]:
        payload = _read_json(path)
        if isinstance(payload, dict):
            entries.append(payload)
    return {"count": len(entries), "items": entries, "warnings": []}


def get_document_content_curation_summary(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    workspace = build_document_content_curation_workspace(document_id, root=root)
    readiness = get_document_content_curation_readiness(document_id, root=root)
    curated = build_curated_document_content_map(document_id, root=root)
    overlay = load_document_content_curation(document_id, root=root).get("curation") or {}
    return {
        "document_id": document_id,
        "source_revision": workspace.get("source_revision"),
        "base_fingerprint_current": readiness.get("base_fingerprint_current"),
        "curation_revision": int(overlay.get("curation_revision") or 0),
        "curation_status": workspace.get("curation_status", "unknown"),
        "curation_readiness": readiness.get("status", "unknown"),
        "override_count": _overlay_change_count(overlay),
        "valid_change_count": readiness.get("valid_change_count", 0),
        "invalid_change_count": readiness.get("invalid_change_count", 0),
        "assigned_chunk_count": len(curated.get("effective_chunk_assignments", {})),
        "unassigned_chunk_count": len(curated.get("unassigned_chunk_ids", [])),
        "manual_tag_count": curated.get("manual_tag_count", 0),
        "recommended_action": readiness.get("recommended_action"),
    }


def format_document_content_curation_report(document_id: str, public_safe: bool = True, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> str:
    overlay = load_document_content_curation(document_id, root=root).get("curation") or {}
    readiness = get_document_content_curation_readiness(document_id, root=root)
    curated = build_curated_document_content_map(document_id, root=root)
    counts = _change_type_counts(overlay.get("changes", []))
    base_fingerprint = str((overlay.get("base_content_map_fingerprint") or curated.get("detected_base_fingerprint") or "unknown"))
    safe_fingerprint = base_fingerprint[:20] + ("..." if len(base_fingerprint) > 20 else "")
    next_action = readiness.get("recommended_action") or "Review readiness and detected fallback state."
    lines = [
        "Document Content Curation Report",
        "",
        f"Document: {document_id}",
        f"Curation Revision: {int(overlay.get('curation_revision') or 0)}",
        f"Source Revision: {curated.get('source_revision')}",
        f"Base Fingerprint: {safe_fingerprint}",
        f"Readiness: {readiness.get('status')}",
        f"Curation Applied: {bool(curated.get('curation_applied'))}",
        f"Detected Fallback Used: {bool(curated.get('detected_fallback_used'))}",
        "",
        "Correction Counts:",
        f"- Chapter Renames: {counts['chapter_renames']}",
        f"- Chapter Range Corrections: {counts['chapter_range_corrections']}",
        f"- Section Renames: {counts['section_renames']}",
        f"- Section Range Corrections: {counts['section_range_corrections']}",
        f"- Chunk Assignments: {counts['chunk_assignments']}",
        f"- Chunk Unassignments: {counts['chunk_unassignments']}",
        f"- Manual Topic Tags Added: {counts['tags_added']}",
        f"- Manual Topic Tags Removed: {counts['tags_removed']}",
        "",
        f"Warnings: {len(readiness.get('warnings', []))}",
        f"Stale Reasons: {', '.join(readiness.get('stale_reasons', [])) or 'none'}",
        f"Invalid Reasons: {', '.join(readiness.get('invalid_reasons', [])) or 'none'}",
        "",
        f"Recommended Next Action: {next_action}",
    ]
    text = "\n".join(lines)
    return _sanitize_public_report(text) if public_safe else text


def normalize_manual_topic_tag(value: object) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("â€“", "-").replace("â€”", "-")
    text = re.sub(r"[^\w\s\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -")
    return text


def _ensure_document_content_curation_dirs(root: Path | str) -> Path:
    base = ensure_document_content_map_dirs(root)
    (base / CURATION_DIR).mkdir(parents=True, exist_ok=True)
    index_path = base / "indexes" / CURATION_INDEX
    if not index_path.exists():
        _atomic_write_json(index_path, {"entries": [], "updated_at_utc": _now()})
    return base


def _new_overlay(document_id: str, content_map: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": CURATION_SCHEMA_VERSION,
        "curation_id": f"curation_{document_id}",
        "document_id": document_id,
        "curation_revision": 0,
        "base_content_map_fingerprint": content_map.get("document_scoped_fingerprint"),
        "source_revision": content_map.get("source_revision"),
        "chapter_title_overrides": {},
        "chapter_range_overrides": {},
        "section_title_overrides": {},
        "section_range_overrides": {},
        "chunk_assignment_overrides": {},
        "chunk_unassignments": [],
        "manual_tag_additions": {},
        "manual_tag_removals": {},
        "changes": [],
        "created_at_utc": _now(),
        "updated_at_utc": _now(),
        "warnings": [],
    }


def _validate_overlay_payload(content_map: dict[str, Any], overlay: dict[str, Any], root: Path) -> dict[str, Any]:
    invalid_reasons: list[str] = []
    stale_reasons: list[str] = []
    warnings: list[str] = []
    blockers: list[str] = []
    schema_version = str(overlay.get("schema_version") or "")
    if schema_version in LEGACY_CURATION_SCHEMA_VERSIONS:
        return _readiness_payload("unknown", overlay, warnings, stale_reasons, ["legacy_schema_requires_manual_review"], blockers)
    if schema_version != CURATION_SCHEMA_VERSION:
        invalid_reasons.append("schema_version_invalid")
    if str(overlay.get("document_id") or "") != str(content_map.get("document_id") or ""):
        invalid_reasons.append("document_id_mismatch")
    revision = overlay.get("curation_revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        invalid_reasons.append("curation_revision_invalid")
    required_fields = (
        "base_content_map_fingerprint",
        "source_revision",
        "chapter_title_overrides",
        "chapter_range_overrides",
        "section_title_overrides",
        "section_range_overrides",
        "chunk_assignment_overrides",
        "chunk_unassignments",
        "manual_tag_additions",
        "manual_tag_removals",
    )
    for field in required_fields:
        if field not in overlay:
            invalid_reasons.append(f"{field}_missing")
    if invalid_reasons:
        return _readiness_payload("invalid", overlay, warnings, stale_reasons, invalid_reasons, blockers)
    lookup = _map_lookup(content_map, root)
    if overlay.get("base_content_map_fingerprint") != content_map.get("document_scoped_fingerprint"):
        stale_reasons.append("base_content_map_changed")
    if overlay.get("source_revision") != content_map.get("source_revision"):
        stale_reasons.append("source_revision_changed")
    invalid_reasons.extend(_validate_override_shape(overlay))
    if invalid_reasons:
        return _readiness_payload("invalid", overlay, warnings, stale_reasons, invalid_reasons, blockers)
    stale_reasons.extend(_validate_override_references(content_map, overlay, lookup))
    if stale_reasons:
        return _readiness_payload("stale", overlay, warnings, stale_reasons, invalid_reasons, blockers)
    changes = overlay.get("changes", [])
    if not isinstance(changes, list):
        invalid_reasons.append("changes_invalid")
        return _readiness_payload("invalid", overlay, warnings, stale_reasons, invalid_reasons, blockers)
    if _overlay_changes_from_state(overlay) != changes:
        invalid_reasons.append("corrupt_normalized_state")
        return _readiness_payload("invalid", overlay, warnings, stale_reasons, invalid_reasons, blockers)
    status = "ready_with_warnings" if warnings else "ready"
    return _readiness_payload(status, overlay, warnings, stale_reasons, invalid_reasons, blockers)


def _readiness_payload(status: str, overlay: dict[str, Any], warnings: list[str], stale_reasons: list[str], invalid_reasons: list[str], blockers: list[str]) -> dict[str, Any]:
    base_current = bool(overlay.get("base_content_map_fingerprint"))
    source_current = bool(overlay.get("source_revision"))
    if status == "stale":
        blockers.extend(stale_reasons)
    if status == "invalid":
        blockers.extend(invalid_reasons)
    return {
        "status": status if status in READINESS_STATUSES else "unknown",
        "base_fingerprint_current": "base_content_map_changed" not in stale_reasons,
        "source_revision_current": "source_revision_changed" not in stale_reasons,
        "warnings": list(dict.fromkeys(warnings)),
        "stale_reasons": list(dict.fromkeys(stale_reasons)),
        "invalid_reasons": list(dict.fromkeys(invalid_reasons)),
        "blockers": list(dict.fromkeys(blockers)),
        "recommended_action": (
            "Correct invalid curation overlay fields before using the curated view."
            if status == "invalid"
            else "Review curation overrides against the current detected content map."
            if status == "stale"
            else "Review and replace the legacy or unclassifiable curation record before using the curated view."
            if status == "unknown"
            else "Build curated view or copy the public-safe curation report."
        ),
    }


def _apply_change_to_overlay_state(content_map: dict[str, Any], overlay: dict[str, Any], change: dict[str, Any], effective_before: dict[str, Any]) -> tuple[bool, list[str]]:
    warnings: list[str] = []
    target_type = str(change.get("target_type"))
    target_id = str(change.get("target_id"))
    operation = str(change.get("operation"))
    value = change.get("value") if isinstance(change.get("value"), dict) else {}
    if operation == "rename":
        current_title = effective_before["chapter_titles"].get(target_id) if target_type == "chapter" else effective_before["section_titles"].get(target_id)
        if current_title == value.get("title"):
            return False, warnings
        key = "chapter_title_overrides" if target_type == "chapter" else "section_title_overrides"
        overlay.setdefault(key, {})[target_id] = value.get("title")
        return True, warnings
    if operation == "set_range":
        current_range = effective_before["chapter_ranges"].get(target_id) if target_type == "chapter" else effective_before["section_ranges"].get(target_id)
        next_range = json.loads(json.dumps(value, sort_keys=True))
        if current_range == next_range:
            return False, warnings
        key = "chapter_range_overrides" if target_type == "chapter" else "section_range_overrides"
        overlay.setdefault(key, {})[target_id] = next_range
        return True, warnings
    if operation == "assign_chunk":
        chunk_id = str(value.get("chunk_id") or "")
        current_assignment = effective_before["chunk_assignments"].get(chunk_id)
        if current_assignment == target_id:
            return False, warnings
        overlay.setdefault("chunk_assignment_overrides", {})[chunk_id] = target_id
        overlay["chunk_unassignments"] = [item for item in overlay.get("chunk_unassignments", []) if item != chunk_id]
        return True, warnings
    if operation == "unassign_chunk":
        chunk_id = str(value.get("chunk_id") or "")
        if chunk_id in effective_before["unassigned_chunk_ids"]:
            return False, warnings
        overlay.setdefault("chunk_assignment_overrides", {}).pop(chunk_id, None)
        overlay["chunk_unassignments"] = sorted(set([str(item) for item in overlay.get("chunk_unassignments", [])] + [chunk_id]))
        return True, warnings
    if operation == "add_tag":
        tag = str(value.get("tag") or "")
        current_tags = set(effective_before["chunk_tags"].get(target_id, []))
        if tag in current_tags:
            return False, warnings
        additions = set(_string_list((overlay.get("manual_tag_additions") or {}).get(target_id, [])))
        removals = set(_string_list((overlay.get("manual_tag_removals") or {}).get(target_id, [])))
        additions.add(tag)
        removals.discard(tag)
        overlay.setdefault("manual_tag_additions", {})[target_id] = sorted(additions)
        if removals:
            overlay.setdefault("manual_tag_removals", {})[target_id] = sorted(removals)
        else:
            (overlay.get("manual_tag_removals") or {}).pop(target_id, None)
        return True, warnings
    if operation == "remove_tag":
        tag = str(value.get("tag") or "")
        current_tags = set(effective_before["chunk_tags"].get(target_id, []))
        if tag not in current_tags:
            return False, warnings
        additions = set(_string_list((overlay.get("manual_tag_additions") or {}).get(target_id, [])))
        removals = set(_string_list((overlay.get("manual_tag_removals") or {}).get(target_id, [])))
        if tag in additions:
            additions.discard(tag)
        else:
            removals.add(tag)
        if additions:
            overlay.setdefault("manual_tag_additions", {})[target_id] = sorted(additions)
        else:
            (overlay.get("manual_tag_additions") or {}).pop(target_id, None)
        overlay.setdefault("manual_tag_removals", {})[target_id] = sorted(removals)
        return True, warnings
    return False, warnings


def _build_effective_state(content_map: dict[str, Any], overlay: dict[str, Any], root: Path) -> dict[str, Any]:
    chapter_titles = {str(chapter.get("chapter_id")): str(chapter.get("title") or "") for chapter in content_map.get("chapters", []) if isinstance(chapter, dict)}
    section_titles = {str(section.get("section_id")): str(section.get("title") or "") for section in content_map.get("sections", []) if isinstance(section, dict)}
    chapter_ranges = {
        str(chapter.get("chapter_id")): _range_from_record(chapter)
        for chapter in content_map.get("chapters", [])
        if isinstance(chapter, dict) and chapter.get("chapter_id")
    }
    section_ranges = {
        str(section.get("section_id")): _range_from_record(section)
        for section in content_map.get("sections", [])
        if isinstance(section, dict) and section.get("section_id")
    }
    chunk_assignments = _chunk_assignment_lookup(content_map)
    chunk_tags = _chunk_topic_tag_lookup(content_map)
    for key, title in (overlay.get("chapter_title_overrides") or {}).items():
        chapter_titles[str(key)] = str(title)
    for key, title in (overlay.get("section_title_overrides") or {}).items():
        section_titles[str(key)] = str(title)
    for key, value in (overlay.get("chapter_range_overrides") or {}).items():
        if isinstance(value, dict):
            chapter_ranges[str(key)] = _range_from_record(value)
    for key, value in (overlay.get("section_range_overrides") or {}).items():
        if isinstance(value, dict):
            section_ranges[str(key)] = _range_from_record(value)
    for chunk_id in _string_list(overlay.get("chunk_unassignments", [])):
        chunk_assignments.pop(chunk_id, None)
    for chunk_id, section_id in (overlay.get("chunk_assignment_overrides") or {}).items():
        chunk_assignments[str(chunk_id)] = str(section_id)
    all_chunk_ids = {chunk.chunk_id for chunk in load_chunks(document_id=content_map.get("document_id"), root=root)}
    for chunk_id, tags in (overlay.get("manual_tag_additions") or {}).items():
        merged = set(chunk_tags.get(str(chunk_id), []))
        merged.update(_string_list(tags))
        chunk_tags[str(chunk_id)] = sorted(merged)
    for chunk_id, tags in (overlay.get("manual_tag_removals") or {}).items():
        reduced = set(chunk_tags.get(str(chunk_id), []))
        reduced.difference_update(_string_list(tags))
        chunk_tags[str(chunk_id)] = sorted(reduced)
    return {
        "chapter_titles": chapter_titles,
        "section_titles": section_titles,
        "chapter_ranges": chapter_ranges,
        "section_ranges": section_ranges,
        "chunk_assignments": chunk_assignments,
        "unassigned_chunk_ids": sorted(all_chunk_ids - set(chunk_assignments)),
        "chunk_tags": chunk_tags,
    }


def _apply_overlay_to_curated_map(curated: dict[str, Any], overlay: dict[str, Any]) -> None:
    chapter_lookup = {str(chapter.get("chapter_id")): chapter for chapter in curated.get("chapters", []) if isinstance(chapter, dict)}
    section_lookup = {str(section.get("section_id")): section for section in curated.get("sections", []) if isinstance(section, dict)}
    for chapter_id, title in sorted((overlay.get("chapter_title_overrides") or {}).items()):
        if chapter_id in chapter_lookup:
            chapter_lookup[chapter_id]["title"] = title
    for section_id, title in sorted((overlay.get("section_title_overrides") or {}).items()):
        if section_id in section_lookup:
            section_lookup[section_id]["title"] = title
    for chapter_id, payload in sorted((overlay.get("chapter_range_overrides") or {}).items()):
        if chapter_id in chapter_lookup and isinstance(payload, dict):
            chapter_lookup[chapter_id].update(payload)
    for section_id, payload in sorted((overlay.get("section_range_overrides") or {}).items()):
        if section_id in section_lookup and isinstance(payload, dict):
            section_lookup[section_id].update(payload)
    chunk_to_section = _chunk_assignment_lookup(curated)
    all_chunks = set(chunk_to_section)
    for chunk_id in _string_list(overlay.get("chunk_unassignments", [])):
        previous = chunk_to_section.pop(chunk_id, None)
        if previous and previous in section_lookup:
            section_lookup[previous]["chunk_ids"] = [item for item in section_lookup[previous].get("chunk_ids", []) if str(item) != chunk_id]
        all_chunks.add(chunk_id)
    for chunk_id, target_section in sorted((overlay.get("chunk_assignment_overrides") or {}).items()):
        previous = chunk_to_section.get(str(chunk_id))
        if previous and previous in section_lookup:
            section_lookup[previous]["chunk_ids"] = [item for item in section_lookup[previous].get("chunk_ids", []) if str(item) != str(chunk_id)]
        if str(target_section) in section_lookup:
            chunk_to_section[str(chunk_id)] = str(target_section)
            if str(chunk_id) not in _string_list(section_lookup[str(target_section)].get("chunk_ids", [])):
                section_lookup[str(target_section)].setdefault("chunk_ids", []).append(str(chunk_id))
                section_lookup[str(target_section)]["chunk_ids"] = sorted(_string_list(section_lookup[str(target_section)]["chunk_ids"]))
        all_chunks.add(str(chunk_id))
    chunk_tags = _chunk_topic_tag_lookup(curated)
    for chunk_id, tags in sorted((overlay.get("manual_tag_additions") or {}).items()):
        merged = set(chunk_tags.get(str(chunk_id), []))
        merged.update(_string_list(tags))
        chunk_tags[str(chunk_id)] = sorted(merged)
    for chunk_id, tags in sorted((overlay.get("manual_tag_removals") or {}).items()):
        merged = set(chunk_tags.get(str(chunk_id), []))
        merged.difference_update(_string_list(tags))
        chunk_tags[str(chunk_id)] = sorted(merged)
    for section in curated.get("sections", []):
        if not isinstance(section, dict):
            continue
        section["chunk_ids"] = sorted(_string_list(section.get("chunk_ids", [])))
        effective_tags = set()
        for chunk_id in section["chunk_ids"]:
            effective_tags.update(chunk_tags.get(chunk_id, []))
        section["topic_tags"] = sorted(effective_tags)
    curated["unassigned_chunk_ids"] = sorted(all_chunks - set(chunk_to_section))
    curated["section_count"] = len(curated.get("sections", []))
    curated["assigned_chunk_count"] = len(chunk_to_section)


def _validate_override_shape(overlay: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    dict_fields = (
        "chapter_title_overrides",
        "chapter_range_overrides",
        "section_title_overrides",
        "section_range_overrides",
        "chunk_assignment_overrides",
        "manual_tag_additions",
        "manual_tag_removals",
    )
    for field in dict_fields:
        if not isinstance(overlay.get(field), dict):
            reasons.append(f"{field}_invalid")
    if not isinstance(overlay.get("chunk_unassignments"), list):
        reasons.append("chunk_unassignments_invalid")
    return reasons


def _validate_override_references(content_map: dict[str, Any], overlay: dict[str, Any], lookup: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for chapter_id in (overlay.get("chapter_title_overrides") or {}):
        if chapter_id not in lookup["chapters"]:
            reasons.append("missing_referenced_chapter")
    for section_id in (overlay.get("section_title_overrides") or {}):
        if section_id not in lookup["sections"]:
            reasons.append("missing_referenced_section")
    for chapter_id, payload in (overlay.get("chapter_range_overrides") or {}).items():
        if chapter_id not in lookup["chapters"]:
            reasons.append("missing_referenced_chapter")
            continue
        if not isinstance(payload, dict):
            reasons.append("invalid_manual_chapter_range")
            continue
        range_blockers, _ = _validate_range_against_map(content_map, lookup, "chapter", chapter_id, payload)
        if range_blockers:
            reasons.append("invalid_manual_chapter_range")
    for section_id, payload in (overlay.get("section_range_overrides") or {}).items():
        if section_id not in lookup["sections"]:
            reasons.append("missing_referenced_section")
            continue
        if not isinstance(payload, dict):
            reasons.append("invalid_manual_section_range")
            continue
        range_blockers, _ = _validate_range_against_map(content_map, lookup, "section", section_id, payload)
        if range_blockers:
            reasons.append("invalid_manual_section_range")
    for chunk_id, section_id in (overlay.get("chunk_assignment_overrides") or {}).items():
        if chunk_id not in lookup["chunks"]:
            reasons.append("missing_referenced_chunk")
        if section_id not in lookup["sections"]:
            reasons.append("missing_assignment_target_section")
    for chunk_id in _string_list(overlay.get("chunk_unassignments", [])):
        if chunk_id not in lookup["chunks"]:
            reasons.append("missing_referenced_chunk")
    for field in ("manual_tag_additions", "manual_tag_removals"):
        for chunk_id, tags in (overlay.get(field) or {}).items():
            if chunk_id not in lookup["chunks"]:
                reasons.append("missing_referenced_chunk")
            if not isinstance(tags, list) or any(not normalize_manual_topic_tag(tag) for tag in tags):
                reasons.append("manual_topic_tags_invalid")
    return list(dict.fromkeys(reasons))


def _normalize_range_value(value: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    start_page = _coerce_int(value.get("start_page"))
    end_page = _coerce_int(value.get("end_page"))
    start_chunk_id = str(value.get("start_chunk_id") or "").strip() or None
    end_chunk_id = str(value.get("end_chunk_id") or "").strip() or None
    if start_page is None or end_page is None:
        blockers.append("page_range_required")
    elif start_page > end_page:
        blockers.append("range_reversed")
    return {
        "blockers": blockers,
        "range": {"start_page": start_page, "end_page": end_page, "start_chunk_id": start_chunk_id, "end_chunk_id": end_chunk_id},
    }


def _validate_range_against_map(content_map: dict[str, Any], lookup: dict[str, Any], target_type: str, target_id: str, range_data: dict[str, Any]) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    start_page = _coerce_int(range_data.get("start_page"))
    end_page = _coerce_int(range_data.get("end_page"))
    if start_page is None or end_page is None:
        return ["page_range_required"], warnings
    doc_pages = _document_page_bounds(lookup)
    if doc_pages[0] is not None and doc_pages[1] is not None and (start_page < doc_pages[0] or end_page > doc_pages[1]):
        blockers.append("page_range_outside_document")
    for chunk_key, blocker_name in (("start_chunk_id", "start_chunk_unknown"), ("end_chunk_id", "end_chunk_unknown")):
        chunk_id = str(range_data.get(chunk_key) or "").strip()
        if chunk_id and chunk_id not in lookup["chunks"]:
            blockers.append(blocker_name)
    if target_type == "section":
        section = lookup["sections"].get(target_id)
        chapter_id = str((section or {}).get("chapter_id") or "")
        chapter = lookup["chapters"].get(chapter_id) if chapter_id else None
        if chapter:
            chapter_start = _coerce_int(chapter.get("start_page"))
            chapter_end = _coerce_int(chapter.get("end_page"))
            if chapter_start is not None and chapter_end is not None and (start_page < chapter_start or end_page > chapter_end):
                blockers.append("section_range_outside_chapter")
    if target_type == "chapter":
        section_pages = [
            (_coerce_int(section.get("start_page")), _coerce_int(section.get("end_page")))
            for section in lookup["sections"].values()
            if str(section.get("chapter_id") or "") == target_id
        ]
        valid_section_pages = [(start, end) for start, end in section_pages if start is not None and end is not None]
        if valid_section_pages:
            min_section = min(start for start, _ in valid_section_pages)
            max_section = max(end for _, end in valid_section_pages)
            if start_page > min_section or end_page < max_section:
                blockers.append("chapter_range_excludes_section")
    return list(dict.fromkeys(blockers)), warnings


def _map_lookup(content_map: dict[str, Any], root: Path) -> dict[str, Any]:
    chapters = {str(chapter.get("chapter_id")): copy.deepcopy(chapter) for chapter in content_map.get("chapters", []) if isinstance(chapter, dict) and chapter.get("chapter_id")}
    sections = {str(section.get("section_id")): copy.deepcopy(section) for section in content_map.get("sections", []) if isinstance(section, dict) and section.get("section_id")}
    chunks = {chunk.chunk_id: chunk.to_json(public_safe=True) for chunk in load_chunks(document_id=content_map.get("document_id"), root=root)}
    return {"chapters": chapters, "sections": sections, "chunks": chunks}


def _overlay_changes_from_state(overlay: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for chapter_id, title in sorted((overlay.get("chapter_title_overrides") or {}).items()):
        changes.append({"target_type": "chapter", "target_id": chapter_id, "operation": "rename", "value": {"title": title}, "note": None})
    for chapter_id, payload in sorted((overlay.get("chapter_range_overrides") or {}).items()):
        changes.append({"target_type": "chapter", "target_id": chapter_id, "operation": "set_range", "value": _range_from_record(payload), "note": None})
    for section_id, title in sorted((overlay.get("section_title_overrides") or {}).items()):
        changes.append({"target_type": "section", "target_id": section_id, "operation": "rename", "value": {"title": title}, "note": None})
    for section_id, payload in sorted((overlay.get("section_range_overrides") or {}).items()):
        changes.append({"target_type": "section", "target_id": section_id, "operation": "set_range", "value": _range_from_record(payload), "note": None})
    for chunk_id in sorted(_string_list(overlay.get("chunk_unassignments", []))):
        changes.append({"target_type": "section", "target_id": str((overlay.get("chunk_assignment_overrides") or {}).get(chunk_id) or ""), "operation": "unassign_chunk", "value": {"chunk_id": chunk_id}, "note": None})
    for chunk_id, section_id in sorted((overlay.get("chunk_assignment_overrides") or {}).items()):
        changes.append({"target_type": "section", "target_id": section_id, "operation": "assign_chunk", "value": {"chunk_id": chunk_id}, "note": None})
    for chunk_id, tags in sorted((overlay.get("manual_tag_additions") or {}).items()):
        for tag in sorted(_string_list(tags)):
            changes.append({"target_type": "chunk", "target_id": chunk_id, "operation": "add_tag", "value": {"tag": tag}, "note": None})
    for chunk_id, tags in sorted((overlay.get("manual_tag_removals") or {}).items()):
        for tag in sorted(_string_list(tags)):
            changes.append({"target_type": "chunk", "target_id": chunk_id, "operation": "remove_tag", "value": {"tag": tag}, "note": None})
    return changes


def _overlay_change_count(overlay: dict[str, Any]) -> int:
    changes = overlay.get("changes", [])
    return len(changes) if isinstance(changes, list) else 0


def _change_type_counts(changes: list[dict]) -> dict[str, int]:
    counts = {
        "chapter_renames": 0,
        "chapter_range_corrections": 0,
        "section_renames": 0,
        "section_range_corrections": 0,
        "chunk_assignments": 0,
        "chunk_unassignments": 0,
        "tags_added": 0,
        "tags_removed": 0,
    }
    for item in changes:
        if not isinstance(item, dict):
            continue
        target_type = item.get("target_type")
        operation = item.get("operation")
        if target_type == "chapter" and operation == "rename":
            counts["chapter_renames"] += 1
        elif target_type == "chapter" and operation == "set_range":
            counts["chapter_range_corrections"] += 1
        elif target_type == "section" and operation == "rename":
            counts["section_renames"] += 1
        elif target_type == "section" and operation == "set_range":
            counts["section_range_corrections"] += 1
        elif operation == "assign_chunk":
            counts["chunk_assignments"] += 1
        elif operation == "unassign_chunk":
            counts["chunk_unassignments"] += 1
        elif operation == "add_tag":
            counts["tags_added"] += 1
        elif operation == "remove_tag":
            counts["tags_removed"] += 1
    return counts


def _chunk_assignment_lookup(content_map: dict[str, Any]) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for section in content_map.get("sections", []):
        if not isinstance(section, dict):
            continue
        section_id = str(section.get("section_id") or "")
        for chunk_id in _string_list(section.get("chunk_ids", [])):
            assignments[chunk_id] = section_id
    return assignments


def _chunk_topic_tag_lookup(content_map: dict[str, Any]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for section in content_map.get("sections", []):
        if not isinstance(section, dict):
            continue
        tags = sorted({normalize_manual_topic_tag(tag) for tag in section.get("topic_tags", []) if normalize_manual_topic_tag(tag)})
        for chunk_id in _string_list(section.get("chunk_ids", [])):
            mapping[chunk_id] = list(tags)
    return mapping


def _range_from_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "start_page": _coerce_int(record.get("start_page")),
        "end_page": _coerce_int(record.get("end_page")),
        "start_chunk_id": str(record.get("start_chunk_id") or "").strip() or None,
        "end_chunk_id": str(record.get("end_chunk_id") or "").strip() or None,
    }


def _document_page_bounds(lookup: dict[str, Any]) -> tuple[int | None, int | None]:
    pages = []
    for record in list(lookup["chapters"].values()) + list(lookup["sections"].values()):
        start_page = _coerce_int(record.get("start_page"))
        end_page = _coerce_int(record.get("end_page"))
        if start_page is not None:
            pages.append(start_page)
        if end_page is not None:
            pages.append(end_page)
    for chunk in lookup["chunks"].values():
        start_page = _coerce_int(chunk.get("page_start"))
        end_page = _coerce_int(chunk.get("page_end"))
        if start_page is not None:
            pages.append(start_page)
        if end_page is not None:
            pages.append(end_page)
    return (min(pages), max(pages)) if pages else (None, None)


def _normalize_title(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _string_list(items: object) -> list[str]:
    return [str(item).strip() for item in items if str(item).strip()] if isinstance(items, list) else []


def _curation_path(root: Path, document_id: str) -> Path:
    return root / CURATION_DIR / f"{document_id}.json"


def _save_curation(root: Path, payload: dict[str, Any]) -> None:
    _atomic_write_json(_curation_path(root, str(payload.get("document_id"))), payload)
    entries = []
    for path in sorted((root / CURATION_DIR).glob("*.json")):
        item = _read_json(path)
        if isinstance(item, dict):
            entries.append(
                {
                    "document_id": item.get("document_id"),
                    "curation_revision": item.get("curation_revision"),
                    "base_content_map_fingerprint": item.get("base_content_map_fingerprint"),
                    "source_revision": item.get("source_revision"),
                    "updated_at_utc": item.get("updated_at_utc"),
                }
            )
    _atomic_write_json(root / "indexes" / CURATION_INDEX, {"entries": entries, "updated_at_utc": _now()})


def _read_json(path: Path) -> dict[str, object] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            pass
    os.replace(temp_path, path)


def _sanitize_public_report(text: str) -> str:
    safe = text.replace(str(Path.cwd()), "[workspace]").replace(str(SOURCE_DOCUMENT_ROOT), "[source-root]").replace("\\", "/")
    lines = []
    for line in safe.splitlines():
        if any(pattern.search(line) for pattern in UNSAFE_REPORT_PATTERNS):
            continue
        lines.append(line)
    return "\n".join(lines)


def _coerce_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except Exception:
        return None


def _safe_revision(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        revision = int(value)
    except Exception:
        return 0
    return revision if revision >= 0 else 0


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
