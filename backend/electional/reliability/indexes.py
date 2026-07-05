"""Reliability storage indexes and controlled-folder rebuilds."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from .storage import DEFAULT_ROOT, ensure_reliability_storage, load_reliability_object, _atomic_write_json


INDEX_FILES = {
    "snapshot": "snapshot_index.json",
    "outcome": "outcome_index.json",
    "replay": "replay_index.json",
}


def index_path(root: Path | str, index_name: str) -> Path:
    if index_name not in INDEX_FILES:
        raise ValueError(f"Unknown reliability index: {index_name}")
    return ensure_reliability_storage(root) / "indexes" / INDEX_FILES[index_name]


def load_index(root: Path | str = DEFAULT_ROOT, index_name: str = "snapshot") -> dict[str, object]:
    path = index_path(root, index_name)
    if not path.exists():
        return {"entries": []}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {"entries": []}


def update_index_after_save(root: Path | str, *, object_type: str, path: Path, payload: Mapping[str, object]) -> None:
    index_name = _index_for_object_type(object_type)
    if not index_name:
        return
    index = load_index(root, index_name)
    entries = [entry for entry in index.get("entries", []) if isinstance(entry, dict)]
    entry = _entry_for(object_type, path, payload)
    entries = [row for row in entries if row.get("id") != entry["id"]]
    entries.append(entry)
    index["entries"] = sorted(entries, key=lambda row: str(row.get("id")))
    _atomic_write_json(index_path(root, index_name), index)


def rebuild_indexes(root: Path | str = DEFAULT_ROOT) -> dict[str, object]:
    base = ensure_reliability_storage(root)
    rebuilt = {"snapshot": [], "outcome": [], "replay": []}
    for object_type, folder, index_name in (
        ("audit_snapshot", "audit_snapshots", "snapshot"),
        ("outcome_log", "outcome_logs", "outcome"),
        ("replay_result", "replay_results", "replay"),
    ):
        entries = []
        for path in sorted((base / folder).glob("*.json")):
            if path.name.startswith("."):
                continue
            try:
                payload = load_reliability_object(path)
            except Exception:
                continue
            entries.append(_entry_for(object_type, path, payload))
        _atomic_write_json(index_path(base, index_name), {"entries": entries})
        rebuilt[index_name] = entries
    return rebuilt


def check_indexes(root: Path | str = DEFAULT_ROOT) -> dict[str, object]:
    base = ensure_reliability_storage(root)
    missing_index_files = [name for name in INDEX_FILES if not index_path(base, name).exists()]
    missing_indexed_files: list[str] = []
    unindexed_files: list[str] = []
    for index_name, folder in (("snapshot", "audit_snapshots"), ("outcome", "outcome_logs"), ("replay", "replay_results")):
        index = load_index(base, index_name)
        indexed = {str(row.get("path")) for row in index.get("entries", []) if isinstance(row, dict)}
        for row_path in indexed:
            if row_path and not Path(row_path).exists():
                missing_indexed_files.append(row_path)
        for file_path in (base / folder).glob("*.json"):
            if file_path.name.startswith("."):
                continue
            if str(file_path) not in indexed:
                unindexed_files.append(str(file_path))
    return {
        "missing_index_files": missing_index_files,
        "missing_indexed_files": missing_indexed_files,
        "unindexed_files": unindexed_files,
        "status": "warning" if missing_index_files or missing_indexed_files or unindexed_files else "healthy",
    }


def _index_for_object_type(object_type: str) -> str | None:
    if object_type == "audit_snapshot":
        return "snapshot"
    if object_type == "outcome_log":
        return "outcome"
    if object_type in {"replay_result", "historical_replay_result"}:
        return "replay"
    return None


def _entry_for(object_type: str, path: Path, payload: Mapping[str, object]) -> dict[str, object]:
    audit = payload.get("audit_snapshot") if isinstance(payload.get("audit_snapshot"), Mapping) else payload
    phase2 = audit.get("phase2_tactical_analysis", {}) if isinstance(audit, Mapping) else {}
    phase1 = audit.get("phase1_advanced_analysis", {}) if isinstance(audit, Mapping) else {}
    phase3 = audit.get("phase3_reliability", {}) if isinstance(audit, Mapping) else {}
    input_data = audit.get("input", {}) if isinstance(audit, Mapping) else {}
    object_id = str(payload.get("id") or payload.get("run_id") or payload.get("election_id") or path.stem)
    return {
        "id": object_id,
        "election_id": object_id,
        "path": str(path),
        "objective_type": input_data.get("objective") if isinstance(input_data, Mapping) else payload.get("objective_type"),
        "election_datetime": input_data.get("date") if isinstance(input_data, Mapping) else payload.get("election_datetime"),
        "engine_version": payload.get("engine_version"),
        "schema_version": payload.get("schema_version"),
        "reproducibility_hash": payload.get("reproducibility_hash") or (audit.get("reproducibility_hash") if isinstance(audit, Mapping) else None),
        "has_phase1": bool(phase1),
        "has_phase2": bool(phase2),
        "has_fast_lane": isinstance(phase2, Mapping) and bool(phase2.get("fast_lane")),
        "has_phase3": bool(phase3),
        "privacy_level": payload.get("privacy_level", "public_safe"),
        "created_at_utc": payload.get("created_at_utc"),
    }
