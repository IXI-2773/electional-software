"""Manual stale-curation rebase and conflict resolution workspaces."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from .document_content_curation import (
    CURATION_SCHEMA_VERSION,
    _atomic_write_json,
    _ensure_document_content_curation_dirs,
    _map_lookup,
    _now,
    _overlay_changes_from_state,
    _read_json,
    _safe_revision,
    _sanitize_public_report,
    _save_curation,
    _validate_overlay_payload,
    _validate_range_against_map,
    load_document_content_curation,
)
from .document_content_history import (
    _history_record_to_overlay,
    load_document_content_curation_revision,
    save_curation_history_snapshot,
)
from .document_content_map import load_document_content_map
from .source_documents import SOURCE_DOCUMENT_ROOT

REBASE_SCHEMA_VERSION = "document_content_curation_rebase_v1"
REBASE_DIR = "document_content_curation_rebase"
REBASE_INDEX = "document_content_curation_rebase_index.json"

WORKSPACE_STATUSES = {"draft", "unresolved", "ready", "ready_with_warnings", "stale_again", "invalid", "committed", "abandoned", "unknown"}


def create_rebase_workspace_from_current_stale_curation(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_rebase_dirs(root)
    source = load_document_content_curation(document_id, root=base).get("curation")
    if not isinstance(source, dict):
        return {"document_id": document_id, "status": "not_found", "warnings": [], "blockers": ["curation_not_found"]}
    return _create_workspace(document_id, "current_overlay", source, root=base, source_history_revision=None)


def create_rebase_workspace_from_historical_revision(document_id: str, revision: int, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_rebase_dirs(root)
    loaded = load_document_content_curation_revision(document_id, revision, root=base)
    if loaded.get("status") != "ready":
        return {"document_id": document_id, "status": loaded.get("status", "not_found"), "warnings": loaded.get("warnings", []), "blockers": loaded.get("blockers", [])}
    source = _history_record_to_overlay(loaded.get("revision_record") or {})
    return _create_workspace(document_id, "historical_revision", source, root=base, source_history_revision=revision)


def load_document_content_rebase_workspace(document_id: str, workspace_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_rebase_dirs(root)
    payload = _read_json(_workspace_path(base, document_id, workspace_id))
    if not isinstance(payload, dict):
        return {"document_id": document_id, "workspace_id": workspace_id, "status": "not_found", "workspace": None, "warnings": [], "blockers": ["workspace_not_found"]}
    if str(payload.get("document_id") or "") != document_id:
        return {"document_id": document_id, "workspace_id": workspace_id, "status": "invalid", "workspace": payload, "warnings": [], "blockers": ["document_mismatch"]}
    return {"document_id": document_id, "workspace_id": workspace_id, "status": "loaded", "workspace": payload, "warnings": [], "blockers": []}


def list_document_content_rebase_workspaces(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_rebase_dirs(root)
    folder = base / REBASE_DIR / document_id
    items = []
    warnings = []
    if folder.exists():
        for path in sorted(folder.glob("*.json")):
            payload = _read_json(path)
            if not isinstance(payload, dict):
                warnings.append(f"corrupt_workspace:{path.stem}")
                continue
            items.append(
                {
                    "workspace_id": payload.get("workspace_id"),
                    "document_id": document_id,
                    "status": payload.get("status", "unknown"),
                    "workspace_revision": payload.get("workspace_revision", 0),
                    "source_type": payload.get("source_type"),
                    "source_curation_revision": payload.get("source_curation_revision"),
                    "source_history_revision": payload.get("source_history_revision"),
                    "created_at_utc": payload.get("created_at_utc"),
                    "updated_at_utc": payload.get("updated_at_utc"),
                    "conflict_count": len(payload.get("conflicts", [])) if isinstance(payload.get("conflicts"), list) else 0,
                    "unresolved_conflict_count": len([item for item in payload.get("conflicts", []) if isinstance(item, dict) and item.get("severity") == "blocker" and item.get("resolution_status") != "resolved"]),
                }
            )
    return {"document_id": document_id, "count": len(items), "items": items, "warnings": warnings}


def refresh_document_content_rebase_conflicts(document_id: str, workspace_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_rebase_dirs(root)
    loaded = load_document_content_rebase_workspace(document_id, workspace_id, root=base)
    if loaded["status"] != "loaded":
        return loaded
    workspace = loaded["workspace"] or {}
    if workspace.get("status") in {"committed", "abandoned"}:
        return {"document_id": document_id, "workspace_id": workspace_id, "status": workspace.get("status"), "workspace": workspace, "warnings": [], "blockers": []}
    current_map = load_document_content_map(document_id, root=base).get("content_map")
    if isinstance(current_map, dict) and (
        workspace.get("current_detected_fingerprint") != current_map.get("document_scoped_fingerprint")
        or workspace.get("current_source_revision") != current_map.get("source_revision")
    ):
        workspace["status"] = "stale_again"
        workspace["blockers"] = ["workspace_base_changed"]
        workspace["updated_at_utc"] = _now()
        _save_workspace(base, workspace)
        return {"document_id": document_id, "workspace_id": workspace_id, "status": "stale_again", "workspace": workspace, "warnings": workspace.get("warnings", []), "blockers": workspace.get("blockers", [])}
    source_overlay = copy.deepcopy(workspace.get("source_overlay") or {})
    rebuilt = _build_workspace(document_id, workspace_id, workspace.get("source_type"), source_overlay, workspace.get("source_history_revision"), base, existing_workspace=workspace)
    changed = _canonical_workspace_state(workspace) != _canonical_workspace_state(rebuilt)
    if changed:
        rebuilt["workspace_revision"] = int(workspace.get("workspace_revision") or 0) + 1
        rebuilt["updated_at_utc"] = _now()
        _save_workspace(base, rebuilt)
    return {"document_id": document_id, "workspace_id": workspace_id, "status": rebuilt.get("status"), "workspace": rebuilt, "warnings": rebuilt.get("warnings", []), "blockers": rebuilt.get("blockers", [])}


def apply_document_content_rebase_resolution(document_id: str, workspace_id: str, conflict_id: str, resolution: dict[str, Any], *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_rebase_dirs(root)
    loaded = load_document_content_rebase_workspace(document_id, workspace_id, root=base)
    if loaded["status"] != "loaded":
        return loaded
    workspace = loaded["workspace"] or {}
    if workspace.get("status") in {"committed", "abandoned"}:
        return {"document_id": document_id, "workspace_id": workspace_id, "status": workspace.get("status"), "workspace": workspace, "warnings": [], "blockers": [f"workspace_{workspace.get('status')}"]}
    refreshed = refresh_document_content_rebase_conflicts(document_id, workspace_id, root=base)
    workspace = refreshed.get("workspace") or workspace
    conflict = next((item for item in workspace.get("conflicts", []) if isinstance(item, dict) and item.get("conflict_id") == conflict_id), None)
    if not conflict:
        return {"document_id": document_id, "workspace_id": workspace_id, "status": "invalid", "workspace": workspace, "warnings": [], "blockers": ["conflict_not_found"]}
    validation = _validate_resolution(workspace, conflict, resolution, base)
    if not validation["valid"]:
        return {"document_id": document_id, "workspace_id": workspace_id, "status": "invalid", "workspace": workspace, "warnings": [], "blockers": validation["blockers"]}
    normalized = validation["resolution"]
    current = (workspace.get("manual_resolutions") or {}).get(conflict_id)
    if _canonical(current) == _canonical(normalized):
        return {"document_id": document_id, "workspace_id": workspace_id, "status": "unchanged", "workspace": workspace, "warnings": [], "blockers": []}
    next_workspace = copy.deepcopy(workspace)
    next_workspace.setdefault("manual_resolutions", {})[conflict_id] = normalized
    next_workspace["workspace_revision"] = int(workspace.get("workspace_revision") or 0) + 1
    next_workspace["updated_at_utc"] = _now()
    next_workspace = _rebuild_workspace_from_resolutions(next_workspace, base)
    _save_workspace(base, next_workspace)
    return {"document_id": document_id, "workspace_id": workspace_id, "status": next_workspace.get("status"), "workspace": next_workspace, "warnings": next_workspace.get("warnings", []), "blockers": next_workspace.get("blockers", [])}


def get_document_content_rebase_readiness(document_id: str, workspace_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    loaded = load_document_content_rebase_workspace(document_id, workspace_id, root=root)
    if loaded["status"] != "loaded":
        return {"document_id": document_id, "workspace_id": workspace_id, "status": loaded.get("status"), "warnings": loaded.get("warnings", []), "blockers": loaded.get("blockers", [])}
    workspace = _rebuild_workspace_from_resolutions(copy.deepcopy(loaded["workspace"]), _ensure_document_content_rebase_dirs(root))
    return {
        "document_id": document_id,
        "workspace_id": workspace_id,
        "status": workspace.get("status", "unknown"),
        "warnings": workspace.get("warnings", []),
        "blockers": workspace.get("blockers", []),
        "unresolved_conflict_count": workspace.get("unresolved_conflict_count", 0),
    }


def build_document_content_rebase_proposed_overlay(document_id: str, workspace_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    loaded = load_document_content_rebase_workspace(document_id, workspace_id, root=root)
    if loaded["status"] != "loaded":
        return {"document_id": document_id, "workspace_id": workspace_id, "status": loaded.get("status"), "proposed_overlay": None, "warnings": loaded.get("warnings", []), "blockers": loaded.get("blockers", [])}
    workspace = _rebuild_workspace_from_resolutions(copy.deepcopy(loaded["workspace"]), _ensure_document_content_rebase_dirs(root))
    return {"document_id": document_id, "workspace_id": workspace_id, "status": workspace.get("status"), "proposed_overlay": workspace.get("proposed_overlay"), "warnings": workspace.get("warnings", []), "blockers": workspace.get("blockers", [])}


def commit_document_content_rebase_workspace(document_id: str, workspace_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_rebase_dirs(root)
    loaded = load_document_content_rebase_workspace(document_id, workspace_id, root=base)
    if loaded["status"] != "loaded":
        return {"document_id": document_id, "workspace_id": workspace_id, "status": loaded.get("status"), "warnings": loaded.get("warnings", []), "blockers": loaded.get("blockers", [])}
    workspace = _rebuild_workspace_from_resolutions(copy.deepcopy(loaded["workspace"]), base)
    if workspace.get("status") == "committed":
        return {"document_id": document_id, "workspace_id": workspace_id, "status": "conflict", "warnings": [], "blockers": ["workspace_already_committed"]}
    if workspace.get("status") == "abandoned":
        return {"document_id": document_id, "workspace_id": workspace_id, "status": "failed", "warnings": [], "blockers": ["workspace_abandoned"]}
    if workspace.get("status") == "stale_again":
        return {"document_id": document_id, "workspace_id": workspace_id, "status": "stale_again", "warnings": workspace.get("warnings", []), "blockers": workspace.get("blockers", [])}
    if workspace.get("status") == "invalid":
        return {"document_id": document_id, "workspace_id": workspace_id, "status": "invalid", "warnings": workspace.get("warnings", []), "blockers": workspace.get("blockers", [])}
    if workspace.get("status") not in {"ready", "ready_with_warnings"}:
        return {"document_id": document_id, "workspace_id": workspace_id, "status": "failed", "warnings": workspace.get("warnings", []), "blockers": workspace.get("blockers", [])}
    current_map = load_document_content_map(document_id, root=base).get("content_map")
    if not isinstance(current_map, dict):
        return {"document_id": document_id, "workspace_id": workspace_id, "status": "failed", "warnings": [], "blockers": ["content_map_missing"]}
    if workspace.get("current_detected_fingerprint") != current_map.get("document_scoped_fingerprint") or workspace.get("current_source_revision") != current_map.get("source_revision"):
        workspace["status"] = "stale_again"
        workspace["blockers"] = ["workspace_base_changed"]
        _save_workspace(base, workspace)
        return {"document_id": document_id, "workspace_id": workspace_id, "status": "stale_again", "warnings": workspace.get("warnings", []), "blockers": workspace.get("blockers", [])}
    current_overlay = load_document_content_curation(document_id, root=base).get("curation")
    current_rebase_provenance = (current_overlay or {}).get("rebase_provenance") if isinstance(current_overlay, dict) else {}
    if isinstance(current_rebase_provenance, dict) and current_rebase_provenance.get("rebase_workspace_id") == workspace_id:
        workspace["status"] = "committed"
        workspace["commit_provenance"] = dict(current_rebase_provenance)
        workspace["committed_revision"] = (current_overlay or {}).get("curation_revision")
        _save_workspace(base, workspace)
        from .document_content_integrity import rebuild_document_content_indexes

        rebuild_document_content_indexes(document_id, root=base)
        return {"document_id": document_id, "workspace_id": workspace_id, "status": "committed", "warnings": [], "blockers": [], "curation": current_overlay}
    proposed = copy.deepcopy(workspace.get("proposed_overlay") or {})
    proposed["schema_version"] = CURATION_SCHEMA_VERSION
    proposed["document_id"] = document_id
    proposed["base_content_map_fingerprint"] = current_map.get("document_scoped_fingerprint")
    proposed["source_revision"] = current_map.get("source_revision")
    previous_current_revision = _safe_revision((current_overlay or {}).get("curation_revision"))
    proposed["curation_revision"] = previous_current_revision + 1
    proposed["changes"] = _overlay_changes_from_state(proposed)
    proposed["updated_at_utc"] = _now()
    proposed["rebase_provenance"] = {
        "rebase_workspace_id": workspace_id,
        "rebase_source_type": workspace.get("source_type"),
        "rebased_from_curation_revision": workspace.get("source_curation_revision"),
        "rebased_from_history_revision": workspace.get("source_history_revision"),
        "previous_current_revision": previous_current_revision,
        "committed_at_utc": _now(),
        "resolved_conflict_count": len([item for item in workspace.get("conflicts", []) if isinstance(item, dict) and item.get("resolution_status") == "resolved"]),
        "dropped_override_count": len([item for item in (workspace.get("manual_resolutions") or {}).values() if isinstance(item, dict) and item.get("action") in {"drop", "remove_assignment", "drop_manual_tag_override"}]),
        "remapped_override_count": len([item for item in (workspace.get("manual_resolutions") or {}).values() if isinstance(item, dict) and item.get("action") in {"remap_chapter", "remap_section", "remap_chunk", "replace_chapter_range", "replace_section_range", "replace_assignment_target"}]),
    }
    validation = _validate_overlay_payload(current_map, proposed, base)
    if validation["status"] in {"invalid", "unknown"}:
        return {"document_id": document_id, "workspace_id": workspace_id, "status": "invalid", "warnings": validation["warnings"], "blockers": validation["blockers"]}
    if validation["status"] == "stale":
        return {"document_id": document_id, "workspace_id": workspace_id, "status": "stale_again", "warnings": validation["warnings"], "blockers": validation["blockers"]}
    from .document_content_integrity import (
        _maybe_fail,
        finalize_document_content_transaction,
        prepare_document_content_transaction,
        record_document_content_transaction_checkpoint,
        rebuild_document_content_indexes,
    )

    transaction = prepare_document_content_transaction(
        "rebase_commit",
        document_id,
        expected_previous_revision=previous_current_revision,
        expected_new_revision=_safe_revision(proposed.get("curation_revision")),
        base_content_map_fingerprint=proposed.get("base_content_map_fingerprint"),
        source_revision=proposed.get("source_revision"),
        proposed_overlay_state=proposed,
        source_workflow_type="rebase_commit",
        source_workflow_id=workspace_id,
        source_workflow_revision=_safe_revision(workspace.get("workspace_revision")),
        root=base,
    )
    transaction_id = transaction.get("transaction_id")
    if current_overlay and _overlay_core_state(current_overlay) == _overlay_core_state(proposed):
        return {"document_id": document_id, "workspace_id": workspace_id, "status": "unchanged", "warnings": [], "blockers": [], "curation": current_overlay}
    previous_overlay = copy.deepcopy(current_overlay) if isinstance(current_overlay, dict) else None
    _maybe_fail("rebase_before_overlay")
    _save_curation(base, proposed)
    if transaction_id:
        record_document_content_transaction_checkpoint(document_id, transaction_id, "overlay_written", root=base)
    _maybe_fail("rebase_after_overlay")
    history = save_curation_history_snapshot(document_id, proposed, root=base)
    if history.get("status") == "conflict":
        if previous_overlay is not None:
            _save_curation(base, previous_overlay)
        return {"document_id": document_id, "workspace_id": workspace_id, "status": "failed", "warnings": [], "blockers": history.get("blockers", [])}
    if transaction_id:
        record_document_content_transaction_checkpoint(document_id, transaction_id, "history_written", root=base)
    _maybe_fail("rebase_after_history")
    workspace["status"] = "committed"
    workspace["commit_provenance"] = dict(proposed.get("rebase_provenance") or {})
    workspace["committed_revision"] = proposed.get("curation_revision")
    workspace["updated_at_utc"] = _now()
    _save_workspace(base, workspace)
    if transaction_id:
        record_document_content_transaction_checkpoint(document_id, transaction_id, "source_status_written", root=base)
    _maybe_fail("rebase_after_source_status")
    rebuild_document_content_indexes(document_id, root=base)
    if transaction_id:
        record_document_content_transaction_checkpoint(document_id, transaction_id, "indexes_reconciled", root=base)
        finalize_document_content_transaction(document_id, transaction_id, "committed", root=base)
    return {"document_id": document_id, "workspace_id": workspace_id, "status": "committed", "warnings": [], "blockers": [], "curation": proposed}


def abandon_document_content_rebase_workspace(document_id: str, workspace_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = _ensure_document_content_rebase_dirs(root)
    loaded = load_document_content_rebase_workspace(document_id, workspace_id, root=base)
    if loaded["status"] != "loaded":
        return {"document_id": document_id, "workspace_id": workspace_id, "status": loaded.get("status"), "warnings": loaded.get("warnings", []), "blockers": loaded.get("blockers", [])}
    workspace = loaded["workspace"] or {}
    if workspace.get("status") == "abandoned":
        return {"document_id": document_id, "workspace_id": workspace_id, "status": "unchanged", "workspace": workspace, "warnings": [], "blockers": []}
    workspace["status"] = "abandoned"
    workspace["abandoned_at_utc"] = _now()
    workspace["updated_at_utc"] = _now()
    _save_workspace(base, workspace)
    return {"document_id": document_id, "workspace_id": workspace_id, "status": "abandoned", "workspace": workspace, "warnings": [], "blockers": []}


def format_document_content_rebase_report(document_id: str, workspace_id: str, public_safe: bool = True, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> str:
    loaded = load_document_content_rebase_workspace(document_id, workspace_id, root=root)
    if loaded["status"] != "loaded":
        text = f"Document Content Rebase Report\n\nDocument: {document_id}\nWorkspace: {workspace_id}\nStatus: {loaded.get('status')}\nBlockers: {', '.join(loaded.get('blockers', [])) or 'none'}"
        return _sanitize_public_report(text) if public_safe else text
    workspace = _rebuild_workspace_from_resolutions(copy.deepcopy(loaded["workspace"]), _ensure_document_content_rebase_dirs(root))
    conflicts = workspace.get("conflicts", []) if isinstance(workspace.get("conflicts"), list) else []
    conflict_counts: dict[str, int] = {}
    for item in conflicts:
        if isinstance(item, dict):
            key = str(item.get("conflict_type") or "unknown")
            conflict_counts[key] = conflict_counts.get(key, 0) + 1
    lines = [
        "Document Content Rebase Report",
        "",
        f"Document: {document_id}",
        f"Workspace: {workspace_id}",
        f"Status: {workspace.get('status')}",
        f"Source Type: {workspace.get('source_type')}",
        f"Source Curation Revision: {workspace.get('source_curation_revision')}",
        f"Source History Revision: {workspace.get('source_history_revision')}",
        f"Conflict Count: {len(conflicts)}",
        f"Unresolved Blockers: {workspace.get('unresolved_conflict_count', 0)}",
        f"Readiness: {workspace.get('status')}",
        f"Warnings: {len(workspace.get('warnings', []))}",
        f"Blockers: {', '.join(workspace.get('blockers', [])) or 'none'}",
        f"Conflict Types: {', '.join(f'{key}={conflict_counts[key]}' for key in sorted(conflict_counts)) or 'none'}",
    ]
    text = "\n".join(lines)
    return _sanitize_public_report(text) if public_safe else text


def _create_workspace(document_id: str, source_type: str, source_overlay: dict[str, Any], *, root: Path, source_history_revision: int | None) -> dict[str, Any]:
    workspace_id = _workspace_id(document_id, source_overlay)
    if _workspace_path(root, document_id, workspace_id).exists():
        return load_document_content_rebase_workspace(document_id, workspace_id, root=root)
    current_map = load_document_content_map(document_id, root=root).get("content_map")
    workspace = {
        "schema_version": REBASE_SCHEMA_VERSION,
        "workspace_id": workspace_id,
        "document_id": document_id,
        "source_type": source_type,
        "source_curation_revision": _safe_revision(source_overlay.get("curation_revision")),
        "source_history_revision": source_history_revision,
        "source_base_fingerprint": source_overlay.get("base_content_map_fingerprint"),
        "source_source_revision": source_overlay.get("source_revision"),
        "current_detected_fingerprint": current_map.get("document_scoped_fingerprint") if isinstance(current_map, dict) else None,
        "current_source_revision": current_map.get("source_revision") if isinstance(current_map, dict) else None,
        "created_at_utc": _now(),
        "updated_at_utc": _now(),
        "workspace_revision": 1,
        "status": "draft",
        "analysis_completed": False,
        "conflicts": [],
        "retained_overrides": _empty_overlay_state(),
        "manual_resolutions": {},
        "proposed_overlay": _empty_overlay_state(),
        "warnings": [],
        "blockers": [],
        "source_overlay": copy.deepcopy(source_overlay),
    }
    _save_workspace(root, workspace)
    return {"document_id": document_id, "workspace_id": workspace_id, "status": workspace.get("status"), "workspace": workspace, "warnings": workspace.get("warnings", []), "blockers": workspace.get("blockers", [])}


def _build_workspace(document_id: str, workspace_id: str, source_type: str, source_overlay: dict[str, Any], source_history_revision: int | None, root: Path, existing_workspace: dict[str, Any] | None = None) -> dict[str, Any]:
    current_map = load_document_content_map(document_id, root=root).get("content_map")
    current_fp = current_map.get("document_scoped_fingerprint") if isinstance(current_map, dict) else None
    current_source_revision = current_map.get("source_revision") if isinstance(current_map, dict) else None
    conflicts, retained, warnings, blockers, malformed = _detect_conflicts(document_id, source_overlay, current_map, root)
    workspace = {
        "schema_version": REBASE_SCHEMA_VERSION,
        "workspace_id": workspace_id,
        "document_id": document_id,
        "source_type": source_type,
        "source_curation_revision": _safe_revision(source_overlay.get("curation_revision")),
        "source_history_revision": source_history_revision,
        "source_base_fingerprint": source_overlay.get("base_content_map_fingerprint"),
        "source_source_revision": source_overlay.get("source_revision"),
        "current_detected_fingerprint": current_fp,
        "current_source_revision": current_source_revision,
        "created_at_utc": (existing_workspace or {}).get("created_at_utc") or _now(),
        "updated_at_utc": _now(),
        "workspace_revision": int((existing_workspace or {}).get("workspace_revision") or 1),
        "analysis_completed": True,
        "conflicts": conflicts,
        "retained_overrides": retained,
        "manual_resolutions": copy.deepcopy((existing_workspace or {}).get("manual_resolutions") or {}),
        "proposed_overlay": {},
        "warnings": warnings,
        "blockers": blockers,
        "source_overlay": copy.deepcopy(source_overlay),
    }
    if malformed:
        workspace["status"] = "invalid"
        return workspace
    return _rebuild_workspace_from_resolutions(workspace, root)


def _rebuild_workspace_from_resolutions(workspace: dict[str, Any], root: Path) -> dict[str, Any]:
    current_map = load_document_content_map(workspace.get("document_id"), root=root).get("content_map")
    if str(workspace.get("schema_version") or "") != REBASE_SCHEMA_VERSION:
        workspace["status"] = "unknown"
        workspace["blockers"] = ["workspace_schema_unknown"]
        return workspace
    if workspace.get("status") == "abandoned":
        return workspace
    if workspace.get("status") == "committed":
        return workspace
    if not workspace.get("analysis_completed"):
        workspace["status"] = "draft"
        workspace["blockers"] = []
        workspace["warnings"] = []
        workspace["unresolved_conflict_count"] = 0
        workspace["proposed_overlay"] = _empty_overlay_state()
        return workspace
    if not isinstance(current_map, dict):
        workspace["status"] = "invalid"
        workspace["blockers"] = ["content_map_missing"]
        return workspace
    if workspace.get("current_detected_fingerprint") != current_map.get("document_scoped_fingerprint") or workspace.get("current_source_revision") != current_map.get("source_revision"):
        workspace["status"] = "stale_again"
        workspace["blockers"] = ["workspace_base_changed"]
        workspace["warnings"] = list(dict.fromkeys(list(workspace.get("warnings", []))))
        return workspace
    conflicts = copy.deepcopy(workspace.get("conflicts") or [])
    proposed = _empty_overlay_state()
    _merge_overlay_state(proposed, workspace.get("retained_overrides") or {})
    blockers = []
    for conflict in conflicts:
        if not isinstance(conflict, dict):
            continue
        conflict_id = conflict.get("conflict_id")
        resolution = (workspace.get("manual_resolutions") or {}).get(conflict_id)
        if conflict.get("severity") == "warning" and not conflict.get("allowed_actions"):
            conflict["resolution_status"] = "informational"
            continue
        if not resolution:
            conflict["resolution_status"] = "unresolved"
            if conflict.get("severity") == "blocker":
                blockers.append(conflict_id)
            continue
        apply_result = _apply_resolution_to_proposed(conflict, resolution, proposed, current_map, root)
        if not apply_result["valid"]:
            conflict["resolution_status"] = "invalid"
            blockers.extend(apply_result["blockers"])
            continue
        conflict["resolution_status"] = "resolved"
    workspace["conflicts"] = conflicts
    workspace["unresolved_conflict_count"] = len([item for item in conflicts if isinstance(item, dict) and item.get("severity") == "blocker" and item.get("resolution_status") != "resolved"])
    proposed["changes"] = _overlay_changes_from_state(proposed)
    workspace["proposed_overlay"] = proposed
    workspace["warnings"] = list(dict.fromkeys(workspace.get("warnings", [])))
    if blockers or workspace["unresolved_conflict_count"]:
        workspace["status"] = "unresolved"
        workspace["blockers"] = list(dict.fromkeys([*workspace.get("blockers", []), *blockers]))
        return workspace
    validation = _validate_overlay_payload(current_map, _overlay_for_validation(workspace, proposed), root)
    if validation["status"] in {"invalid", "unknown"}:
        workspace["status"] = "invalid"
        workspace["blockers"] = validation["blockers"]
        workspace["warnings"] = validation["warnings"]
        return workspace
    if validation["status"] == "stale":
        workspace["status"] = "stale_again"
        workspace["blockers"] = validation["blockers"]
        workspace["warnings"] = validation["warnings"]
        return workspace
    workspace["status"] = validation["status"]
    workspace["blockers"] = []
    workspace["warnings"] = validation["warnings"]
    return workspace


def _detect_conflicts(document_id: str, source_overlay: dict[str, Any], current_map: dict[str, Any] | None, root: Path) -> tuple[list[dict[str, Any]], dict[str, Any], list[str], list[str], bool]:
    conflicts = []
    retained = _empty_overlay_state()
    warnings: list[str] = []
    blockers: list[str] = []
    malformed = False
    if not isinstance(current_map, dict):
        return conflicts, retained, warnings, ["content_map_missing"], True
    lookup = _map_lookup(current_map, root)
    if str(source_overlay.get("document_id") or "") != document_id:
        conflicts.append(_conflict("document_mismatch", "meta", "document", source_overlay.get("document_id"), document_id, "blocker", [], {"source_document_id": source_overlay.get("document_id"), "current_document_id": document_id}))
    if source_overlay.get("base_content_map_fingerprint") != current_map.get("document_scoped_fingerprint"):
        conflicts.append(_conflict("base_fingerprint_changed", "meta", "document", None, None, "warning", [], {"from": _fingerprint_summary(source_overlay.get("base_content_map_fingerprint")), "to": _fingerprint_summary(current_map.get("document_scoped_fingerprint"))}))
    if source_overlay.get("source_revision") != current_map.get("source_revision"):
        conflicts.append(_conflict("source_revision_changed", "meta", "document", None, None, "warning", [], {"from": source_overlay.get("source_revision"), "to": current_map.get("source_revision")}))
    state = _source_state(source_overlay)
    for field_name, expected_type in (
        ("chapter_title_overrides", dict),
        ("chapter_range_overrides", dict),
        ("section_title_overrides", dict),
        ("section_range_overrides", dict),
        ("chunk_assignment_overrides", dict),
        ("chunk_unassignments", list),
        ("manual_tag_additions", dict),
        ("manual_tag_removals", dict),
    ):
        raw_value = source_overlay.get(field_name)
        if raw_value is not None and not isinstance(raw_value, expected_type):
            conflict_type = "invalid_chunk_assignment" if field_name == "chunk_assignment_overrides" else "malformed_override"
            allowed_actions = ["drop"] if field_name != "chunk_assignment_overrides" else ["drop", "remove_assignment"]
            conflicts.append(_conflict(conflict_type, field_name, "document", field_name, None, "blocker", allowed_actions, {"field": field_name}))
    for chapter_id, title in sorted(state["chapter_title_overrides"].items()):
        if chapter_id in lookup["chapters"]:
            retained["chapter_title_overrides"][chapter_id] = title
        else:
            conflicts.append(_conflict("missing_chapter", "chapter_title_overrides", "chapter", chapter_id, None, "blocker", ["drop", "remap_chapter"], {"title": title}))
    for chapter_id, value in sorted(state["chapter_range_overrides"].items()):
        if chapter_id not in lookup["chapters"]:
            conflicts.append(_conflict("missing_chapter", "chapter_range_overrides", "chapter", chapter_id, None, "blocker", ["drop", "remap_chapter"], value))
        else:
            range_blockers, _ = _validate_range_against_map(current_map, lookup, "chapter", chapter_id, value)
            if range_blockers:
                conflict_type = "chapter_containment_conflict" if "chapter_range_excludes_section" in range_blockers else "invalid_chapter_range"
                conflicts.append(_conflict(conflict_type, "chapter_range_overrides", "chapter", chapter_id, None, "blocker", ["drop", "replace_chapter_range"], value))
            else:
                retained["chapter_range_overrides"][chapter_id] = value
    for section_id, title in sorted(state["section_title_overrides"].items()):
        if section_id in lookup["sections"]:
            retained["section_title_overrides"][section_id] = title
        else:
            conflicts.append(_conflict("missing_section", "section_title_overrides", "section", section_id, None, "blocker", ["drop", "remap_section"], {"title": title}))
    for section_id, value in sorted(state["section_range_overrides"].items()):
        if section_id not in lookup["sections"]:
            conflicts.append(_conflict("missing_section", "section_range_overrides", "section", section_id, None, "blocker", ["drop", "remap_section"], value))
        else:
            if _range_reversed(value):
                conflicts.append(_conflict("invalid_section_range", "section_range_overrides", "section", section_id, None, "blocker", ["drop", "replace_section_range"], value))
                continue
            range_blockers, _ = _validate_range_against_map(current_map, lookup, "section", section_id, value)
            if range_blockers:
                conflict_type = "section_containment_conflict" if "section_range_outside_chapter" in range_blockers else "invalid_section_range"
                conflicts.append(_conflict(conflict_type, "section_range_overrides", "section", section_id, None, "blocker", ["drop", "replace_section_range"], value))
            else:
                retained["section_range_overrides"][section_id] = value
    for chunk_id, section_id in sorted(state["chunk_assignment_overrides"].items()):
        if chunk_id in set(state["chunk_unassignments"]):
            conflicts.append(_conflict("invalid_chunk_assignment", "chunk_assignment_overrides", "chunk", chunk_id, section_id, "blocker", ["drop", "remove_assignment", "replace_assignment_target", "remap_chunk"], {"section_id": section_id}))
        elif chunk_id not in lookup["chunks"]:
            conflicts.append(_conflict("missing_chunk", "chunk_assignment_overrides", "chunk", chunk_id, section_id, "blocker", ["drop", "remap_chunk"], {"section_id": section_id}))
        elif not isinstance(section_id, str) or not section_id.strip():
            conflicts.append(_conflict("invalid_chunk_assignment", "chunk_assignment_overrides", "chunk", chunk_id, section_id, "blocker", ["drop", "remove_assignment", "replace_assignment_target"], {"section_id": section_id}))
        elif section_id not in lookup["sections"]:
            conflicts.append(_conflict("missing_assignment_target", "chunk_assignment_overrides", "chunk", chunk_id, section_id, "blocker", ["remove_assignment", "replace_assignment_target"], {"section_id": section_id}))
        else:
            retained["chunk_assignment_overrides"][chunk_id] = section_id
    for chunk_id in sorted(state["chunk_unassignments"]):
        if chunk_id not in lookup["chunks"]:
            conflicts.append(_conflict("missing_chunk", "chunk_unassignments", "chunk", chunk_id, None, "blocker", ["drop", "remap_chunk"], {"chunk_id": chunk_id}))
        else:
            retained["chunk_unassignments"].append(chunk_id)
    for field_name, keep_action, drop_action in (("manual_tag_additions", "keep_manual_tag_override", "drop_manual_tag_override"), ("manual_tag_removals", "keep_manual_tag_override", "drop_manual_tag_override")):
        for chunk_id, tags in sorted(state[field_name].items()):
            if chunk_id not in lookup["chunks"]:
                conflicts.append(_conflict("missing_chunk", field_name, "chunk", chunk_id, None, "blocker", [drop_action, "remap_chunk"], {"tags": tags}))
            elif not isinstance(tags, list) or any(not str(tag).strip() for tag in tags):
                conflicts.append(_conflict("invalid_manual_tag_override", field_name, "chunk", chunk_id, None, "blocker", [drop_action], {"tags": tags}))
            else:
                retained[field_name][chunk_id] = list(tags)
    extra_keys = sorted(set(source_overlay) - {"schema_version", "document_id", "curation_revision", "base_content_map_fingerprint", "source_revision", "chapter_title_overrides", "chapter_range_overrides", "section_title_overrides", "section_range_overrides", "chunk_assignment_overrides", "chunk_unassignments", "manual_tag_additions", "manual_tag_removals", "changes", "created_at_utc", "updated_at_utc", "warnings", "restore_provenance", "rebase_provenance", "curation_id"})
    for key in extra_keys:
        conflicts.append(_conflict("unsupported_override", "unsupported", "document", key, None, "warning", ["drop"], {"field": key}))
    for index, item in enumerate(conflicts, start=1):
        item["conflict_id"] = f"conflict_{index:03d}"
    return conflicts, retained, warnings, blockers, malformed


def _validate_resolution(workspace: dict[str, Any], conflict: dict[str, Any], resolution: dict[str, Any], root: Path) -> dict[str, Any]:
    current_map = load_document_content_map(workspace.get("document_id"), root=root).get("content_map")
    if not isinstance(current_map, dict):
        return {"valid": False, "resolution": {}, "blockers": ["content_map_missing"]}
    action = str(resolution.get("action") or "").strip()
    if action not in set(conflict.get("allowed_actions") or []) | {"keep"}:
        return {"valid": False, "resolution": {}, "blockers": ["resolution_action_not_allowed"]}
    if conflict.get("conflict_type") in {"malformed_override", "document_mismatch"} and action == "keep":
        return {"valid": False, "resolution": {}, "blockers": ["resolution_action_not_allowed"]}
    lookup = _map_lookup(current_map, root)
    normalized = {"action": action}
    if action == "remap_chapter":
        chapter_id = str(resolution.get("chapter_id") or "").strip()
        if chapter_id not in lookup["chapters"]:
            return {"valid": False, "resolution": {}, "blockers": ["target_chapter_missing"]}
        normalized["chapter_id"] = chapter_id
    elif action == "remap_section":
        section_id = str(resolution.get("section_id") or "").strip()
        if section_id not in lookup["sections"]:
            return {"valid": False, "resolution": {}, "blockers": ["target_section_missing"]}
        normalized["section_id"] = section_id
    elif action == "remap_chunk":
        chunk_id = str(resolution.get("chunk_id") or "").strip()
        if chunk_id not in lookup["chunks"]:
            return {"valid": False, "resolution": {}, "blockers": ["target_chunk_missing"]}
        normalized["chunk_id"] = chunk_id
    elif action == "replace_chapter_range":
        chapter_id = str(resolution.get("chapter_id") or conflict.get("source_entity_id") or "").strip()
        if chapter_id not in lookup["chapters"]:
            return {"valid": False, "resolution": {}, "blockers": ["target_chapter_missing"]}
        range_value = {
            "start_page": resolution.get("start_page"),
            "end_page": resolution.get("end_page"),
            "start_chunk_id": resolution.get("start_chunk_id"),
            "end_chunk_id": resolution.get("end_chunk_id"),
        }
        normalized["chapter_id"] = chapter_id
        normalized["range"] = _normalized_range_or_error(current_map, lookup, "chapter", chapter_id, range_value)
        if normalized["range"].get("blockers"):
            return {"valid": False, "resolution": {}, "blockers": normalized["range"]["blockers"]}
    elif action == "replace_section_range":
        section_id = str(resolution.get("section_id") or conflict.get("source_entity_id") or "").strip()
        if section_id not in lookup["sections"]:
            return {"valid": False, "resolution": {}, "blockers": ["target_section_missing"]}
        range_value = {
            "start_page": resolution.get("start_page"),
            "end_page": resolution.get("end_page"),
            "start_chunk_id": resolution.get("start_chunk_id"),
            "end_chunk_id": resolution.get("end_chunk_id"),
        }
        normalized["section_id"] = section_id
        normalized["range"] = _normalized_range_or_error(current_map, lookup, "section", section_id, range_value)
        if normalized["range"].get("blockers"):
            return {"valid": False, "resolution": {}, "blockers": normalized["range"]["blockers"]}
    elif action == "replace_assignment_target":
        section_id = str(resolution.get("section_id") or "").strip()
        if section_id not in lookup["sections"]:
            return {"valid": False, "resolution": {}, "blockers": ["target_section_missing"]}
        normalized["section_id"] = section_id
    elif action in {"drop", "remove_assignment", "drop_manual_tag_override", "keep_manual_tag_override", "keep"}:
        pass
    return {"valid": True, "resolution": normalized, "blockers": []}


def _apply_resolution_to_proposed(conflict: dict[str, Any], resolution: dict[str, Any], proposed: dict[str, Any], current_map: dict[str, Any], root: Path) -> dict[str, Any]:
    action = resolution.get("action")
    override_type = conflict.get("override_type")
    source_entity_id = conflict.get("source_entity_id")
    original = conflict.get("original_override") if isinstance(conflict.get("original_override"), dict) else {}
    if action in {"drop", "remove_assignment", "drop_manual_tag_override"}:
        return {"valid": True, "blockers": []}
    if action == "keep":
        return _apply_original_override(conflict, proposed)
    if action == "remap_chapter":
        target = resolution.get("chapter_id")
        if override_type == "chapter_title_overrides":
            proposed["chapter_title_overrides"][target] = original.get("title")
        elif override_type == "chapter_range_overrides":
            proposed["chapter_range_overrides"][target] = dict(original)
        return {"valid": True, "blockers": []}
    if action == "remap_section":
        target = resolution.get("section_id")
        if override_type == "section_title_overrides":
            proposed["section_title_overrides"][target] = original.get("title")
        elif override_type == "section_range_overrides":
            proposed["section_range_overrides"][target] = dict(original)
        return {"valid": True, "blockers": []}
    if action == "remap_chunk":
        target = resolution.get("chunk_id")
        if override_type == "chunk_assignment_overrides":
            proposed["chunk_assignment_overrides"][target] = original.get("section_id") or conflict.get("target_entity_id")
        elif override_type == "chunk_unassignments":
            proposed["chunk_unassignments"].append(target)
            proposed["chunk_unassignments"] = sorted(set(proposed["chunk_unassignments"]))
        elif override_type in {"manual_tag_additions", "manual_tag_removals"}:
            proposed[override_type][target] = list(original.get("tags", []))
        return {"valid": True, "blockers": []}
    if action == "replace_chapter_range":
        proposed["chapter_range_overrides"][resolution.get("chapter_id")] = dict((resolution.get("range") or {}).get("range") or {})
        return {"valid": True, "blockers": []}
    if action == "replace_section_range":
        proposed["section_range_overrides"][resolution.get("section_id")] = dict((resolution.get("range") or {}).get("range") or {})
        return {"valid": True, "blockers": []}
    if action == "replace_assignment_target":
        proposed["chunk_assignment_overrides"][source_entity_id] = resolution.get("section_id")
        return {"valid": True, "blockers": []}
    if action == "keep_manual_tag_override":
        proposed[override_type][source_entity_id] = list(original.get("tags", []))
        return {"valid": True, "blockers": []}
    return {"valid": False, "blockers": ["unsupported_resolution_action"]}


def _apply_original_override(conflict: dict[str, Any], proposed: dict[str, Any]) -> dict[str, Any]:
    override_type = conflict.get("override_type")
    source_entity_id = conflict.get("source_entity_id")
    original = conflict.get("original_override") if isinstance(conflict.get("original_override"), dict) else {}
    if override_type == "chapter_title_overrides":
        proposed["chapter_title_overrides"][source_entity_id] = original.get("title")
    elif override_type == "chapter_range_overrides":
        proposed["chapter_range_overrides"][source_entity_id] = dict(original)
    elif override_type == "section_title_overrides":
        proposed["section_title_overrides"][source_entity_id] = original.get("title")
    elif override_type == "section_range_overrides":
        proposed["section_range_overrides"][source_entity_id] = dict(original)
    elif override_type == "chunk_assignment_overrides":
        proposed["chunk_assignment_overrides"][source_entity_id] = original.get("section_id") or conflict.get("target_entity_id")
    elif override_type == "chunk_unassignments":
        proposed["chunk_unassignments"].append(source_entity_id)
        proposed["chunk_unassignments"] = sorted(set(proposed["chunk_unassignments"]))
    elif override_type in {"manual_tag_additions", "manual_tag_removals"}:
        proposed[override_type][source_entity_id] = list(original.get("tags", []))
    return {"valid": True, "blockers": []}


def _source_state(source_overlay: dict[str, Any]) -> dict[str, Any]:
    return {
        "chapter_title_overrides": dict(source_overlay.get("chapter_title_overrides") or {}) if isinstance(source_overlay.get("chapter_title_overrides"), dict) else {},
        "chapter_range_overrides": dict(source_overlay.get("chapter_range_overrides") or {}) if isinstance(source_overlay.get("chapter_range_overrides"), dict) else {},
        "section_title_overrides": dict(source_overlay.get("section_title_overrides") or {}) if isinstance(source_overlay.get("section_title_overrides"), dict) else {},
        "section_range_overrides": dict(source_overlay.get("section_range_overrides") or {}) if isinstance(source_overlay.get("section_range_overrides"), dict) else {},
        "chunk_assignment_overrides": dict(source_overlay.get("chunk_assignment_overrides") or {}) if isinstance(source_overlay.get("chunk_assignment_overrides"), dict) else {},
        "chunk_unassignments": sorted(str(item) for item in source_overlay.get("chunk_unassignments", []) if str(item).strip()) if isinstance(source_overlay.get("chunk_unassignments"), list) else [],
        "manual_tag_additions": {str(key): list(value) for key, value in (source_overlay.get("manual_tag_additions") or {}).items()} if isinstance(source_overlay.get("manual_tag_additions"), dict) else {},
        "manual_tag_removals": {str(key): list(value) for key, value in (source_overlay.get("manual_tag_removals") or {}).items()} if isinstance(source_overlay.get("manual_tag_removals"), dict) else {},
    }


def _empty_overlay_state() -> dict[str, Any]:
    return {
        "chapter_title_overrides": {},
        "chapter_range_overrides": {},
        "section_title_overrides": {},
        "section_range_overrides": {},
        "chunk_assignment_overrides": {},
        "chunk_unassignments": [],
        "manual_tag_additions": {},
        "manual_tag_removals": {},
    }


def _merge_overlay_state(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key in ("chapter_title_overrides", "chapter_range_overrides", "section_title_overrides", "section_range_overrides", "chunk_assignment_overrides"):
        target[key].update(copy.deepcopy(source.get(key) or {}))
    target["chunk_unassignments"] = sorted(set(target["chunk_unassignments"]) | set(source.get("chunk_unassignments") or []))
    for key in ("manual_tag_additions", "manual_tag_removals"):
        for chunk_id, tags in (source.get(key) or {}).items():
            target[key][chunk_id] = sorted(set(target[key].get(chunk_id, [])) | set(tags))


def _overlay_for_validation(workspace: dict[str, Any], proposed: dict[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(proposed)
    payload["schema_version"] = CURATION_SCHEMA_VERSION
    payload["document_id"] = workspace.get("document_id")
    payload["curation_revision"] = workspace.get("source_curation_revision") or 0
    payload["base_content_map_fingerprint"] = workspace.get("current_detected_fingerprint")
    payload["source_revision"] = workspace.get("current_source_revision")
    payload["changes"] = _overlay_changes_from_state(payload)
    payload["created_at_utc"] = workspace.get("created_at_utc") or _now()
    payload["updated_at_utc"] = _now()
    return payload


def _normalized_range_or_error(current_map: dict[str, Any], lookup: dict[str, Any], target_type: str, target_id: str, range_value: dict[str, Any]) -> dict[str, Any]:
    try:
        start_page = int(range_value.get("start_page"))
        end_page = int(range_value.get("end_page"))
    except Exception:
        return {"blockers": ["page_range_required"]}
    candidate = {
        "start_page": start_page,
        "end_page": end_page,
        "start_chunk_id": str(range_value.get("start_chunk_id") or "").strip() or None,
        "end_chunk_id": str(range_value.get("end_chunk_id") or "").strip() or None,
    }
    blockers, _ = _validate_range_against_map(current_map, lookup, target_type, target_id, candidate)
    return {"blockers": blockers, "range": candidate}


def _save_workspace(root: Path, workspace: dict[str, Any]) -> None:
    _atomic_write_json(_workspace_path(root, workspace.get("document_id"), workspace.get("workspace_id")), workspace)
    _update_workspace_index(root)


def _workspace_path(root: Path, document_id: str, workspace_id: str) -> Path:
    return root / REBASE_DIR / document_id / f"{workspace_id}.json"


def _update_workspace_index(root: Path) -> None:
    entries = []
    for doc_dir in sorted((root / REBASE_DIR).glob("*")):
        if not doc_dir.is_dir():
            continue
        for path in sorted(doc_dir.glob("*.json")):
            payload = _read_json(path)
            if isinstance(payload, dict):
                entries.append(
                    {
                        "document_id": payload.get("document_id"),
                        "workspace_id": payload.get("workspace_id"),
                        "status": payload.get("status"),
                        "workspace_revision": payload.get("workspace_revision"),
                        "updated_at_utc": payload.get("updated_at_utc"),
                    }
                )
    _atomic_write_json(root / "indexes" / REBASE_INDEX, {"entries": entries, "updated_at_utc": _now()})


def _ensure_document_content_rebase_dirs(root: Path | str) -> Path:
    base = _ensure_document_content_curation_dirs(root)
    (base / REBASE_DIR).mkdir(parents=True, exist_ok=True)
    index_path = base / "indexes" / REBASE_INDEX
    if not index_path.exists():
        _atomic_write_json(index_path, {"entries": [], "updated_at_utc": _now()})
    return base


def _workspace_id(document_id: str, source_overlay: dict[str, Any]) -> str:
    digest = hashlib.sha256(json.dumps({"document_id": document_id, "source_revision": source_overlay.get("source_revision"), "base": source_overlay.get("base_content_map_fingerprint"), "curation_revision": source_overlay.get("curation_revision")}, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:10]
    return f"rebase_{document_id}_{digest}"


def _conflict(conflict_type: str, override_type: str, affected_type: str, source_entity_id: Any, target_entity_id: Any, severity: str, allowed_actions: list[str], original_override: Any) -> dict[str, Any]:
    payload = {
        "conflict_id": "",
        "conflict_type": conflict_type,
        "override_type": override_type,
        "affected_override_type": override_type,
        "source_entity_id": source_entity_id,
        "target_entity_id": target_entity_id,
        "severity": severity,
        "allowed_actions": allowed_actions,
        "resolution_status": "unresolved" if severity == "blocker" and allowed_actions else "informational",
        "original_override": copy.deepcopy(original_override if isinstance(original_override, dict) else {"value": original_override}),
        "explanation": conflict_type.replace("_", " "),
    }
    payload["affected_entity_type"] = affected_type
    return payload


def _overlay_core_state(overlay: dict[str, Any]) -> str:
    payload = {
        "chapter_title_overrides": overlay.get("chapter_title_overrides") or {},
        "chapter_range_overrides": overlay.get("chapter_range_overrides") or {},
        "section_title_overrides": overlay.get("section_title_overrides") or {},
        "section_range_overrides": overlay.get("section_range_overrides") or {},
        "chunk_assignment_overrides": overlay.get("chunk_assignment_overrides") or {},
        "chunk_unassignments": sorted(overlay.get("chunk_unassignments") or []),
        "manual_tag_additions": overlay.get("manual_tag_additions") or {},
        "manual_tag_removals": overlay.get("manual_tag_removals") or {},
    }
    return json.dumps(payload, sort_keys=True, default=str)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _range_reversed(value: dict[str, Any]) -> bool:
    try:
        return int(value.get("start_page")) > int(value.get("end_page"))
    except Exception:
        return False


def _canonical_workspace_state(workspace: dict[str, Any]) -> str:
    payload = {
        "conflicts": workspace.get("conflicts"),
        "manual_resolutions": workspace.get("manual_resolutions"),
        "retained_overrides": workspace.get("retained_overrides"),
        "proposed_overlay": workspace.get("proposed_overlay"),
        "status": workspace.get("status"),
        "warnings": workspace.get("warnings"),
        "blockers": workspace.get("blockers"),
    }
    return json.dumps(payload, sort_keys=True, default=str)


def _fingerprint_summary(value: Any) -> str:
    text = str(value or "unknown")
    return text[:20] + ("..." if len(text) > 20 else "")
