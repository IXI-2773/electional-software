from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping

CHECKPOINT_ROOT = Path(__file__).resolve().parents[2] / "data" / "runtime" / "search_checkpoints"


@dataclass(frozen=True)
class ResumeResult:
    accepted: bool
    checkpoint: dict[str, object] | None
    warning: str = ""


def save_search_checkpoint(payload: Mapping[str, object], *, root: Path | str = CHECKPOINT_ROOT) -> Path:
    base = Path(root)
    base.mkdir(parents=True, exist_ok=True)
    data = dict(payload)
    search_id = _safe_id(str(data.get("search_id") or "search"))
    now = _now()
    data.setdefault("created_at_utc", now)
    data["updated_at_utc"] = now
    path = base / f"{search_id}.json"
    temp = path.with_name(f".{path.name}.tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            pass
    os.replace(temp, path)
    return path


def load_search_checkpoint(search_id: str, *, root: Path | str = CHECKPOINT_ROOT) -> dict[str, object]:
    path = Path(root) / f"{_safe_id(search_id)}.json"
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Checkpoint must be a JSON object.")
    return data


def resume_search_checkpoint(search_id: str, expected_versions: Mapping[str, object], *, root: Path | str = CHECKPOINT_ROOT) -> ResumeResult:
    checkpoint = load_search_checkpoint(search_id, root=root)
    for key, expected in expected_versions.items():
        if checkpoint.get(key) != expected:
            return ResumeResult(False, checkpoint, f"Version mismatch for {key}.")
    return ResumeResult(True, checkpoint)


def cancel_search_checkpoint(search_id: str, *, root: Path | str = CHECKPOINT_ROOT) -> dict[str, object]:
    checkpoint = load_search_checkpoint(search_id, root=root)
    checkpoint["status"] = "cancelled"
    save_search_checkpoint(checkpoint, root=root)
    return checkpoint


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value) or "search"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
