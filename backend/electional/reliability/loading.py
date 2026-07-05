"""Tolerant schema loading for stored and legacy audit snapshots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from .storage import quarantine_file


REQUIRED_BLOCKS = (
    "phase1_advanced_analysis",
    "phase2_tactical_analysis",
    "phase3_reliability",
    "feature_registry",
    "phase_coverage_audit",
)


def unavailable_block(reason: str = "missing_legacy_field") -> dict[str, object]:
    return {
        "status": "unavailable",
        "reason": reason,
        "warnings": ["Legacy snapshot did not contain this section."],
    }


def load_audit_snapshot_tolerant(path: Path | str, *, quarantine: bool = False, root: Path | str | None = None) -> dict[str, object]:
    source = Path(path)
    try:
        with source.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        if quarantine and root is not None:
            quarantine_file(source, root, reason="invalid_json", error=str(exc))
        raise ValueError(f"invalid_json: {source}") from exc
    if not isinstance(data, dict):
        raise ValueError("invalid_critical_input")
    audit = data.get("audit_snapshot") if isinstance(data.get("audit_snapshot"), Mapping) else data
    if not isinstance(audit, dict):
        raise ValueError("invalid_critical_input")
    audit.setdefault("version_info", unavailable_block())
    audit.setdefault("input", {})
    for key in REQUIRED_BLOCKS:
        audit.setdefault(key, unavailable_block())
    phase2 = audit.get("phase2_tactical_analysis")
    if isinstance(phase2, dict):
        phase2.setdefault("fast_lane", unavailable_block())
    audit["source_path"] = str(source)
    return {"audit_snapshot": audit, "warnings": _warnings(audit)}


def _warnings(audit: Mapping[str, object]) -> list[str]:
    warnings: list[str] = []
    for key in REQUIRED_BLOCKS:
        value = audit.get(key)
        if isinstance(value, Mapping) and value.get("status") == "unavailable":
            warnings.append(f"{key} unavailable")
    phase2 = audit.get("phase2_tactical_analysis")
    if isinstance(phase2, Mapping):
        fast = phase2.get("fast_lane")
        if isinstance(fast, Mapping) and fast.get("status") == "unavailable":
            warnings.append("fast_lane unavailable")
    return warnings
