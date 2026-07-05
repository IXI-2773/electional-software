"""Immutable history, comparison, and restore for document content curation overlays."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from .document_content_curation import (
    CURATION_SCHEMA_VERSION,
    _atomic_write_json,
    _change_type_counts,
    _ensure_document_content_curation_dirs,
    _now,
    _overlay_change_count,
    _overlay_changes_from_state,
    _read_json,
    _safe_revision,
    _sanitize_public_report,
    _save_curation,
    _validate_overlay_payload,
    load_document_content_curation,
)
from .document_content_map import load_document_content_map
from .source_documents import SOURCE_DOCUMENT_ROOT

HISTORY_SCHEMA_VERSION = "document_content_curation_history_v1"
HISTORY_DIR = "document_content_curation_history"
HISTORY_INDEX = "document_content_curation_history_index.json"


def save_curation_history_snapshot(
    document_id: str,
    overlay: dict[str, Any],
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
    restore_provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = _ensure_document_content_history_dirs(root)
    revision = _safe_revision(overlay.get("curation_revision"))
    if revision <= 0:
        return {"document_id": document_id, "status": "failed", "warnings": [], "blockers": ["invalid_revision"]}
    snapshot = _build_snapshot_payload(document_id, overlay, restore_provenance=restore_provenance)
    path = _history_revision_path(base, document_id, revision)
    existing = _read_json(path)
    if isinstance(existing, dict):
        if _canonical(existing) == _canonical(snapshot):
            _update_history_index(base)
            return {"document_id": document_id, "status": "unchanged", "snapshot": existing, "warnings": [], "blockers": []}
        return {"document_id": document_id, "status": "conflict", "snapshot": existing, "warnings": [], "blockers": ["history_revision_conflict"]}
    _atomic_write_json(path, snapshot)
    _update_history_index(base)
    return {"document_id": document_id, "status": "saved", "snapshot": snapshot, "warnings": [], "blockers": []}


def list_document_content_curation_revisions(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_history_dirs(root)
    current = load_document_content_curation(document_id, root=base).get("curation") or {}
    current_revision = _safe_revision(current.get("curation_revision"))
    doc_dir = base / HISTORY_DIR / document_id
    items = []
    warnings = []
    if doc_dir.exists():
        for path in sorted(doc_dir.glob("*.json"), key=lambda item: int(item.stem) if item.stem.isdigit() else 10**9):
            payload = _read_json(path)
            if not isinstance(payload, dict):
                warnings.append(f"corrupt_history_record:{path.stem}")
                continue
            status = validate_historical_curation_revision(document_id, _safe_revision(payload.get("curation_revision")), root=base)
            items.append(
                {
                    "document_id": document_id,
                    "curation_revision": _safe_revision(payload.get("curation_revision")),
                    "created_at_utc": payload.get("created_at_utc"),
                    "base_fingerprint_summary": _fingerprint_summary(payload.get("base_content_map_fingerprint")),
                    "source_revision": payload.get("source_revision"),
                    "change_count": int(payload.get("change_count") or 0),
                    "change_summary": dict(payload.get("change_summary") or {}),
                    "is_current": _safe_revision(payload.get("curation_revision")) == current_revision and current_revision > 0,
                    "status": status.get("status"),
                    "stale_reasons": status.get("stale_reasons", []),
                    "invalid_reasons": status.get("invalid_reasons", []),
                    "restored_from_revision": (payload.get("restore_provenance") or {}).get("restored_from_revision"),
                    "restored": bool(payload.get("restore_provenance")),
                }
            )
    return {"document_id": document_id, "count": len(items), "items": items, "warnings": warnings}


def load_document_content_curation_revision(document_id: str, revision: int, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_history_dirs(root)
    path = _history_revision_path(base, document_id, revision)
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return {"document_id": document_id, "curation_revision": revision, "status": "not_found", "revision_record": None, "warnings": [], "blockers": ["revision_not_found"]}
    validation = _validate_history_record(payload, document_id=document_id, revision=revision)
    status = validation["status"] if validation["status"] != "ready_with_warnings" else "ready"
    return {
        "document_id": document_id,
        "curation_revision": revision,
        "status": status,
        "revision_record": payload,
        "warnings": validation["warnings"],
        "blockers": validation["blockers"],
        "invalid_reasons": validation["invalid_reasons"],
    }


def validate_historical_curation_revision(document_id: str, revision: int, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_history_dirs(root)
    loaded = load_document_content_curation_revision(document_id, revision, root=base)
    if loaded["status"] != "ready":
        return {
            "document_id": document_id,
            "curation_revision": revision,
            "status": "invalid" if loaded["status"] != "not_found" else "not_found",
            "warnings": loaded.get("warnings", []),
            "stale_reasons": [],
            "invalid_reasons": loaded.get("invalid_reasons", []) or loaded.get("blockers", []),
            "blockers": loaded.get("blockers", []),
        }
    content_map = load_document_content_map(document_id, root=base).get("content_map")
    if not isinstance(content_map, dict):
        return {"document_id": document_id, "curation_revision": revision, "status": "not_ready", "warnings": [], "stale_reasons": [], "invalid_reasons": [], "blockers": ["content_map_missing"]}
    overlay = _history_record_to_overlay(loaded["revision_record"] or {})
    validation = _validate_overlay_payload(content_map, overlay, base)
    status = validation["status"]
    if status in {"ready", "ready_with_warnings"}:
        return {"document_id": document_id, "curation_revision": revision, "status": status, "warnings": validation["warnings"], "stale_reasons": [], "invalid_reasons": [], "blockers": []}
    if status == "stale":
        return {"document_id": document_id, "curation_revision": revision, "status": "stale", "warnings": validation["warnings"], "stale_reasons": validation["stale_reasons"], "invalid_reasons": [], "blockers": validation["blockers"]}
    return {"document_id": document_id, "curation_revision": revision, "status": "invalid", "warnings": validation["warnings"], "stale_reasons": [], "invalid_reasons": validation["invalid_reasons"], "blockers": validation["blockers"]}


def compare_document_content_curation_revisions(document_id: str, left_revision: int, right_revision: int, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    if left_revision == right_revision:
        loaded = load_document_content_curation_revision(document_id, left_revision, root=root)
        if loaded["status"] != "ready":
            return {"document_id": document_id, "status": loaded["status"], "warnings": loaded.get("warnings", []), "blockers": loaded.get("blockers", [])}
    left = load_document_content_curation_revision(document_id, left_revision, root=root)
    right = load_document_content_curation_revision(document_id, right_revision, root=root)
    if "document_id_mismatch" in left.get("blockers", []) or "document_id_mismatch" in right.get("blockers", []):
        return {"document_id": document_id, "status": "conflict", "warnings": [], "blockers": ["cross_document_comparison_rejected"]}
    if left["status"] != "ready":
        return {"document_id": document_id, "status": left["status"], "warnings": left.get("warnings", []), "blockers": left.get("blockers", [])}
    if right["status"] != "ready":
        return {"document_id": document_id, "status": right["status"], "warnings": right.get("warnings", []), "blockers": right.get("blockers", [])}
    left_record = left["revision_record"] or {}
    right_record = right["revision_record"] or {}
    if str(left_record.get("document_id") or "") != str(right_record.get("document_id") or ""):
        return {"document_id": document_id, "status": "conflict", "warnings": [], "blockers": ["cross_document_comparison_rejected"]}
    left_overlay = dict((left_record.get("overlay") or {}))
    right_overlay = dict((right_record.get("overlay") or {}))
    categories = {
        "chapter_title_overrides": _compare_mapping(left_overlay.get("chapter_title_overrides"), right_overlay.get("chapter_title_overrides")),
        "chapter_range_overrides": _compare_mapping(left_overlay.get("chapter_range_overrides"), right_overlay.get("chapter_range_overrides")),
        "section_title_overrides": _compare_mapping(left_overlay.get("section_title_overrides"), right_overlay.get("section_title_overrides")),
        "section_range_overrides": _compare_mapping(left_overlay.get("section_range_overrides"), right_overlay.get("section_range_overrides")),
        "chunk_assignment_overrides": _compare_mapping(left_overlay.get("chunk_assignment_overrides"), right_overlay.get("chunk_assignment_overrides")),
        "chunk_unassignments": _compare_collection(left_overlay.get("chunk_unassignments"), right_overlay.get("chunk_unassignments")),
        "manual_tag_additions": _compare_tag_mapping(left_overlay.get("manual_tag_additions"), right_overlay.get("manual_tag_additions")),
        "manual_tag_removals": _compare_tag_mapping(left_overlay.get("manual_tag_removals"), right_overlay.get("manual_tag_removals")),
    }
    metadata = {
        "base_content_map_fingerprint": _compare_scalar(left_record.get("base_content_map_fingerprint"), right_record.get("base_content_map_fingerprint")),
        "source_revision": _compare_scalar(left_record.get("source_revision"), right_record.get("source_revision")),
        "curation_revision": _compare_scalar(left_record.get("curation_revision"), right_record.get("curation_revision")),
    }
    return {
        "document_id": document_id,
        "status": "ready",
        "left_revision": left_revision,
        "right_revision": right_revision,
        "categories": categories,
        "metadata": metadata,
        "warnings": [],
        "blockers": [],
    }


def restore_document_content_curation_revision(document_id: str, revision: int, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_history_dirs(root)
    content_map = load_document_content_map(document_id, root=base).get("content_map")
    if not isinstance(content_map, dict):
        return {"document_id": document_id, "status": "failed", "warnings": [], "blockers": ["content_map_missing"]}
    current = load_document_content_curation(document_id, root=base).get("curation")
    historical = load_document_content_curation_revision(document_id, revision, root=base)
    if historical["status"] != "ready":
        mapped = "not_found" if historical["status"] == "not_found" else "invalid"
        return {"document_id": document_id, "status": mapped, "warnings": historical.get("warnings", []), "blockers": historical.get("blockers", [])}
    historical_validation = validate_historical_curation_revision(document_id, revision, root=base)
    if historical_validation["status"] == "stale":
        return {"document_id": document_id, "status": "stale", "warnings": historical_validation.get("warnings", []), "blockers": historical_validation.get("blockers", []), "stale_reasons": historical_validation.get("stale_reasons", [])}
    if historical_validation["status"] == "invalid":
        return {"document_id": document_id, "status": "invalid", "warnings": historical_validation.get("warnings", []), "blockers": historical_validation.get("blockers", []), "invalid_reasons": historical_validation.get("invalid_reasons", [])}
    historical_overlay = _history_record_to_overlay(historical["revision_record"] or {})
    if current and _overlay_state_payload(current) == _overlay_state_payload(historical_overlay):
        return {"document_id": document_id, "status": "unchanged", "warnings": [], "blockers": [], "curation": current}
    previous_current_revision = _safe_revision((current or {}).get("curation_revision"))
    next_overlay = copy.deepcopy(historical_overlay)
    next_overlay["schema_version"] = CURATION_SCHEMA_VERSION
    next_overlay["document_id"] = document_id
    next_overlay["curation_revision"] = previous_current_revision + 1
    next_overlay["base_content_map_fingerprint"] = content_map.get("document_scoped_fingerprint")
    next_overlay["source_revision"] = content_map.get("source_revision")
    next_overlay["changes"] = _overlay_changes_from_state(next_overlay)
    next_overlay["updated_at_utc"] = _now()
    next_overlay["restore_provenance"] = {
        "restored_from_revision": revision,
        "restored_at_utc": _now(),
        "previous_current_revision": previous_current_revision,
    }
    validation = _validate_overlay_payload(content_map, next_overlay, base)
    if validation["status"] == "stale":
        return {"document_id": document_id, "status": "stale", "warnings": validation["warnings"], "blockers": validation["blockers"], "stale_reasons": validation["stale_reasons"]}
    if validation["status"] in {"invalid", "unknown"}:
        return {"document_id": document_id, "status": "invalid", "warnings": validation["warnings"], "blockers": validation["blockers"], "invalid_reasons": validation["invalid_reasons"]}
    from .document_content_integrity import (
        _maybe_fail,
        finalize_document_content_transaction,
        prepare_document_content_transaction,
        record_document_content_transaction_checkpoint,
        rebuild_document_content_indexes,
    )

    transaction = prepare_document_content_transaction(
        "history_restore",
        document_id,
        expected_previous_revision=previous_current_revision,
        expected_new_revision=_safe_revision(next_overlay.get("curation_revision")),
        base_content_map_fingerprint=next_overlay.get("base_content_map_fingerprint"),
        source_revision=next_overlay.get("source_revision"),
        proposed_overlay_state=next_overlay,
        restore_source_revision=revision,
        root=base,
    )
    transaction_id = transaction.get("transaction_id")
    previous_overlay = copy.deepcopy(current) if isinstance(current, dict) else None
    _maybe_fail("restore_before_overlay")
    _save_curation(base, next_overlay)
    if transaction_id:
        record_document_content_transaction_checkpoint(document_id, transaction_id, "overlay_written", root=base)
    _maybe_fail("restore_after_overlay")
    history_save = save_curation_history_snapshot(document_id, next_overlay, root=base, restore_provenance=next_overlay.get("restore_provenance"))
    if history_save["status"] == "conflict":
        if previous_overlay is not None:
            _save_curation(base, previous_overlay)
        return {"document_id": document_id, "status": "conflict", "warnings": [], "blockers": history_save["blockers"]}
    if transaction_id:
        record_document_content_transaction_checkpoint(document_id, transaction_id, "history_written", root=base)
    _maybe_fail("restore_after_history")
    rebuild_document_content_indexes(document_id, root=base)
    if transaction_id:
        record_document_content_transaction_checkpoint(document_id, transaction_id, "indexes_reconciled", root=base)
        finalize_document_content_transaction(document_id, transaction_id, "committed", root=base)
    return {
        "document_id": document_id,
        "status": "restored",
        "warnings": [],
        "blockers": [],
        "curation": next_overlay,
        "restore_provenance": dict(next_overlay.get("restore_provenance") or {}),
    }


def format_document_content_curation_history_report(document_id: str, public_safe: bool = True, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> str:
    listing = list_document_content_curation_revisions(document_id, root=root)
    lines = ["Document Content Curation History", "", f"Document: {document_id}", f"Revision Count: {listing.get('count', 0)}", ""]
    for item in listing.get("items", []):
        lines.append(
            f"- r{item.get('curation_revision')}: {item.get('status')} | current={item.get('is_current')} | changes={item.get('change_count')} | source={item.get('source_revision')} | fp={item.get('base_fingerprint_summary')}"
        )
    if listing.get("warnings"):
        lines.extend(["", "Warnings:"] + [f"- {item}" for item in listing["warnings"]])
    text = "\n".join(lines)
    return _sanitize_public_report(text) if public_safe else text


def format_document_content_curation_comparison_report(document_id: str, left_revision: int, right_revision: int, public_safe: bool = True, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> str:
    comparison = compare_document_content_curation_revisions(document_id, left_revision, right_revision, root=root)
    lines = [
        "Document Content Curation Revision Comparison",
        "",
        f"Document: {document_id}",
        f"Left Revision: {left_revision}",
        f"Right Revision: {right_revision}",
        f"Status: {comparison.get('status')}",
    ]
    if comparison.get("status") == "ready":
        lines.append("")
        for name, payload in comparison.get("categories", {}).items():
            lines.append(
                f"- {name}: added={payload.get('added_count', 0)} removed={payload.get('removed_count', 0)} changed={payload.get('changed_count', 0)} unchanged={payload.get('unchanged_count', 0)}"
            )
    else:
        lines.append(f"Blockers: {', '.join(comparison.get('blockers', [])) or 'none'}")
    text = "\n".join(lines)
    return _sanitize_public_report(text) if public_safe else text


def format_document_content_curation_restore_report(document_id: str, revision: int, public_safe: bool = True, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> str:
    result = restore_document_content_curation_revision(document_id, revision, root=root)
    lines = [
        "Document Content Curation Restore Report",
        "",
        f"Document: {document_id}",
        f"Requested Revision: {revision}",
        f"Status: {result.get('status')}",
        f"Warnings: {len(result.get('warnings', []))}",
        f"Blockers: {', '.join(result.get('blockers', [])) or 'none'}",
    ]
    provenance = result.get("restore_provenance") if isinstance(result.get("restore_provenance"), dict) else {}
    if provenance:
        lines.extend(
            [
                f"Restored From Revision: {provenance.get('restored_from_revision')}",
                f"Previous Current Revision: {provenance.get('previous_current_revision')}",
                f"Restored At: {provenance.get('restored_at_utc')}",
            ]
        )
    text = "\n".join(lines)
    return _sanitize_public_report(text) if public_safe else text


def _ensure_document_content_history_dirs(root: Path | str) -> Path:
    base = _ensure_document_content_curation_dirs(root)
    (base / HISTORY_DIR).mkdir(parents=True, exist_ok=True)
    index_path = base / "indexes" / HISTORY_INDEX
    if not index_path.exists():
        _atomic_write_json(index_path, {"entries": [], "updated_at_utc": _now()})
    return base


def _build_snapshot_payload(document_id: str, overlay: dict[str, Any], restore_provenance: dict[str, Any] | None = None) -> dict[str, Any]:
    snapshot = {
        "schema_version": HISTORY_SCHEMA_VERSION,
        "document_id": document_id,
        "curation_revision": _safe_revision(overlay.get("curation_revision")),
        "base_content_map_fingerprint": overlay.get("base_content_map_fingerprint"),
        "source_revision": overlay.get("source_revision"),
        "overlay": _overlay_state_payload(overlay),
        "change_count": _overlay_change_count(overlay),
        "change_summary": _change_type_counts(overlay.get("changes", [])),
        "created_at_utc": overlay.get("updated_at_utc") or overlay.get("created_at_utc") or _now(),
        "restore_provenance": copy.deepcopy(restore_provenance) if isinstance(restore_provenance, dict) else copy.deepcopy(overlay.get("restore_provenance") or {}),
        "rebase_provenance": copy.deepcopy(overlay.get("rebase_provenance") or {}),
    }
    snapshot["integrity_fingerprint"] = "sha256:" + hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
    return snapshot


def _validate_history_record(payload: dict[str, Any], *, document_id: str, revision: int) -> dict[str, Any]:
    invalid_reasons = []
    if str(payload.get("schema_version") or "") != HISTORY_SCHEMA_VERSION:
        invalid_reasons.append("history_schema_invalid")
    if str(payload.get("document_id") or "") != document_id:
        invalid_reasons.append("document_id_mismatch")
    if _safe_revision(payload.get("curation_revision")) != revision:
        invalid_reasons.append("revision_mismatch")
    overlay = payload.get("overlay")
    if not isinstance(overlay, dict):
        invalid_reasons.append("overlay_missing")
    if invalid_reasons:
        return {"status": "invalid", "warnings": [], "blockers": invalid_reasons, "invalid_reasons": invalid_reasons}
    expected = dict(payload)
    integrity = str(expected.pop("integrity_fingerprint", "") or "")
    actual = "sha256:" + hashlib.sha256(json.dumps(expected, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
    if integrity != actual:
        invalid_reasons.append("integrity_mismatch")
    return {"status": "invalid" if invalid_reasons else "ready", "warnings": [], "blockers": invalid_reasons, "invalid_reasons": invalid_reasons}


def _compare_mapping(left: Any, right: Any) -> dict[str, Any]:
    left_map = left if isinstance(left, dict) else {}
    right_map = right if isinstance(right, dict) else {}
    added = sorted(key for key in right_map if key not in left_map)
    removed = sorted(key for key in left_map if key not in right_map)
    changed = sorted(key for key in left_map if key in right_map and _canonical(left_map[key]) != _canonical(right_map[key]))
    unchanged = sorted(key for key in left_map if key in right_map and _canonical(left_map[key]) == _canonical(right_map[key]))
    return {"added": added, "removed": removed, "changed": changed, "unchanged_count": len(unchanged), "added_count": len(added), "removed_count": len(removed), "changed_count": len(changed)}


def _compare_collection(left: Any, right: Any) -> dict[str, Any]:
    left_set = set(str(item) for item in left) if isinstance(left, list) else set()
    right_set = set(str(item) for item in right) if isinstance(right, list) else set()
    added = sorted(right_set - left_set)
    removed = sorted(left_set - right_set)
    unchanged = sorted(left_set & right_set)
    return {"added": added, "removed": removed, "changed": [], "unchanged_count": len(unchanged), "added_count": len(added), "removed_count": len(removed), "changed_count": 0}


def _compare_tag_mapping(left: Any, right: Any) -> dict[str, Any]:
    left_map = {str(key): sorted(str(item) for item in value) for key, value in (left or {}).items()} if isinstance(left, dict) else {}
    right_map = {str(key): sorted(str(item) for item in value) for key, value in (right or {}).items()} if isinstance(right, dict) else {}
    return _compare_mapping(left_map, right_map)


def _compare_scalar(left: Any, right: Any) -> dict[str, Any]:
    changed = _canonical(left) != _canonical(right)
    return {"added": [], "removed": [], "changed": ["value"] if changed else [], "unchanged_count": 0 if changed else 1, "added_count": 0, "removed_count": 0, "changed_count": 1 if changed else 0}


def _overlay_state_payload(overlay: dict[str, Any]) -> dict[str, Any]:
    state = {
        "chapter_title_overrides": dict(overlay.get("chapter_title_overrides") or {}),
        "chapter_range_overrides": dict(overlay.get("chapter_range_overrides") or {}),
        "section_title_overrides": dict(overlay.get("section_title_overrides") or {}),
        "section_range_overrides": dict(overlay.get("section_range_overrides") or {}),
        "chunk_assignment_overrides": dict(overlay.get("chunk_assignment_overrides") or {}),
        "chunk_unassignments": sorted(str(item) for item in overlay.get("chunk_unassignments", []) if str(item).strip()) if isinstance(overlay.get("chunk_unassignments"), list) else [],
        "manual_tag_additions": {str(key): sorted(str(item) for item in value) for key, value in (overlay.get("manual_tag_additions") or {}).items()},
        "manual_tag_removals": {str(key): sorted(str(item) for item in value) for key, value in (overlay.get("manual_tag_removals") or {}).items()},
        "changes": list(overlay.get("changes") or []),
    }
    return json.loads(json.dumps(state, sort_keys=True, default=str))


def _history_record_to_overlay(record: dict[str, Any]) -> dict[str, Any]:
    overlay = copy.deepcopy((record.get("overlay") or {}))
    overlay["schema_version"] = CURATION_SCHEMA_VERSION
    overlay["document_id"] = record.get("document_id")
    overlay["curation_revision"] = _safe_revision(record.get("curation_revision"))
    overlay["base_content_map_fingerprint"] = record.get("base_content_map_fingerprint")
    overlay["source_revision"] = record.get("source_revision")
    overlay["changes"] = list((overlay.get("changes") or []))
    overlay.setdefault("chapter_title_overrides", {})
    overlay.setdefault("chapter_range_overrides", {})
    overlay.setdefault("section_title_overrides", {})
    overlay.setdefault("section_range_overrides", {})
    overlay.setdefault("chunk_assignment_overrides", {})
    overlay.setdefault("chunk_unassignments", [])
    overlay.setdefault("manual_tag_additions", {})
    overlay.setdefault("manual_tag_removals", {})
    overlay.setdefault("created_at_utc", record.get("created_at_utc") or _now())
    overlay.setdefault("updated_at_utc", record.get("created_at_utc") or _now())
    if record.get("restore_provenance"):
        overlay["restore_provenance"] = copy.deepcopy(record.get("restore_provenance"))
    return overlay


def _history_revision_path(root: Path, document_id: str, revision: int) -> Path:
    return root / HISTORY_DIR / document_id / f"{int(revision)}.json"


def _update_history_index(root: Path) -> None:
    entries = []
    for doc_dir in sorted((root / HISTORY_DIR).glob("*")):
        if not doc_dir.is_dir():
            continue
        for path in sorted(doc_dir.glob("*.json"), key=lambda item: (doc_dir.name, int(item.stem) if item.stem.isdigit() else 10**9)):
            payload = _read_json(path)
            if isinstance(payload, dict):
                entries.append(
                    {
                        "document_id": payload.get("document_id"),
                        "curation_revision": payload.get("curation_revision"),
                        "source_revision": payload.get("source_revision"),
                        "base_fingerprint_summary": _fingerprint_summary(payload.get("base_content_map_fingerprint")),
                        "change_count": payload.get("change_count"),
                        "created_at_utc": payload.get("created_at_utc"),
                        "restored": bool(payload.get("restore_provenance")),
                    }
                )
    _atomic_write_json(root / "indexes" / HISTORY_INDEX, {"entries": entries, "updated_at_utc": _now()})


def _fingerprint_summary(value: Any) -> str:
    text = str(value or "unknown")
    return text[:20] + ("..." if len(text) > 20 else "")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
