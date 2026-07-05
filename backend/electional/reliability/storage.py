"""Persistent file storage for Phase 3 reliability artifacts."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping

from .audit_snapshot import _hash


SCHEMA_VERSION = "phase3_reliability_v1"
DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "data" / "reliability"
SUBDIRS = (
    "audit_snapshots",
    "outcome_logs",
    "replay_results",
    "review_queue",
    "calibration_reports",
    "rule_performance",
    "indexes",
    "quarantine",
)
OBJECT_DIRS = {
    "audit_snapshot": "audit_snapshots",
    "outcome_log": "outcome_logs",
    "replay_result": "replay_results",
    "historical_replay_result": "replay_results",
    "review_queue": "review_queue",
    "calibration_report": "calibration_reports",
    "rule_performance_report": "rule_performance",
}


@dataclass(frozen=True)
class StorageResult:
    path: Path
    object_id: str
    object_type: str
    wrote: bool
    warnings: tuple[str, ...] = ()


def ensure_reliability_storage(root: Path | str = DEFAULT_ROOT) -> Path:
    base = Path(root)
    for subdir in SUBDIRS:
        (base / subdir).mkdir(parents=True, exist_ok=True)
    return base


def reliability_path(root: Path | str, object_type: str, object_id: str) -> Path:
    base = ensure_reliability_storage(root)
    subdir = OBJECT_DIRS.get(object_type)
    if not subdir:
        raise ValueError(f"Unsupported reliability object type: {object_type}")
    filename = "review_queue.json" if object_type == "review_queue" else f"{_safe_id(object_id)}.json"
    return base / subdir / filename


def save_reliability_object(
    payload: Mapping[str, object],
    *,
    root: Path | str = DEFAULT_ROOT,
    object_type: str,
    object_id: str | None = None,
    overwrite: bool = False,
    quarantine_corrupt_existing: bool = False,
    privacy_level: str = "public_safe",
) -> StorageResult:
    base = ensure_reliability_storage(root)
    object_id = _safe_id(object_id or str(payload.get("id") or payload.get("run_id") or payload.get("election_id") or object_type))
    path = reliability_path(base, object_type, object_id)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite immutable reliability object: {path}")
    warnings: list[str] = []
    if path.exists() and overwrite and quarantine_corrupt_existing and not _valid_json(path):
        quarantine_file(path, base, reason="corrupt_existing_before_overwrite")
        warnings.append("corrupt existing file quarantined before overwrite")
    record = _with_metadata(dict(payload), object_type=object_type, object_id=object_id, privacy_level=privacy_level)
    _atomic_write_json(path, record)
    from .indexes import update_index_after_save

    update_index_after_save(base, object_type=object_type, path=path, payload=record)
    return StorageResult(path=path, object_id=object_id, object_type=object_type, wrote=True, warnings=tuple(warnings))


def load_reliability_object(path: Path | str) -> dict[str, object]:
    source = Path(path)
    with source.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Reliability object must be a JSON object.")
    if not data.get("id"):
        raise ValueError("Reliability object missing critical id.")
    if not data.get("object_type"):
        raise ValueError("Reliability object missing object_type.")
    stored_hash = data.get("reproducibility_hash")
    if isinstance(stored_hash, str):
        check = dict(data)
        check.pop("reproducibility_hash", None)
        if _hash(check) != stored_hash:
            raise ValueError("hash mismatch")
    data["source_path"] = str(source)
    return data


def save_audit_snapshot(snapshot: Mapping[str, object], *, root: Path | str = DEFAULT_ROOT, election_id: str, overwrite: bool = False) -> StorageResult:
    return save_reliability_object(snapshot, root=root, object_type="audit_snapshot", object_id=election_id, overwrite=overwrite)


def save_outcome_log(payload: Mapping[str, object], *, root: Path | str = DEFAULT_ROOT, election_id: str, overwrite: bool = True) -> StorageResult:
    return save_reliability_object(payload, root=root, object_type="outcome_log", object_id=election_id, overwrite=overwrite)


def save_replay_result(payload: Mapping[str, object], *, root: Path | str = DEFAULT_ROOT, run_id: str, overwrite: bool = False) -> StorageResult:
    return save_reliability_object(payload, root=root, object_type="replay_result", object_id=run_id, overwrite=overwrite)


def save_review_queue(items: list[Mapping[str, object]], *, root: Path | str = DEFAULT_ROOT, overwrite: bool = True) -> StorageResult:
    return save_reliability_object({"items": items}, root=root, object_type="review_queue", object_id="review_queue", overwrite=overwrite)


def quarantine_file(path: Path | str, root: Path | str = DEFAULT_ROOT, *, reason: str, error: str = "") -> dict[str, object]:
    base = ensure_reliability_storage(root)
    source = Path(path)
    timestamp = _now().replace(":", "").replace("-", "")
    quarantine_path = base / "quarantine" / f"{source.stem}_{timestamp}{source.suffix or '.json'}"
    quarantine_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(quarantine_path))
    record = {
        "original_path": str(source),
        "quarantine_path": str(quarantine_path),
        "reason": reason,
        "detected_at_utc": _now(),
        "error": error,
    }
    record_path = quarantine_path.with_suffix(quarantine_path.suffix + ".quarantine.json")
    _atomic_write_json(record_path, record)
    return record


def _with_metadata(payload: dict[str, object], *, object_type: str, object_id: str, privacy_level: str) -> dict[str, object]:
    now = _now()
    payload.setdefault("id", object_id)
    payload.setdefault("object_type", object_type)
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload.setdefault("engine_version", "0.9.0-phase3_reliability_v1")
    payload.setdefault("created_at_utc", now)
    payload["updated_at_utc"] = now
    payload.setdefault("privacy_level", privacy_level)
    payload.pop("reproducibility_hash", None)
    payload["reproducibility_hash"] = _hash(payload)
    return payload


def _atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
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


def _valid_json(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8") as handle:
            json.load(handle)
        return True
    except (OSError, json.JSONDecodeError):
        return False


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in str(value).strip()) or "object"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
