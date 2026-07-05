"""Reliability JSON and Markdown export helpers."""

from __future__ import annotations

import json
from typing import Mapping

from .dashboard import format_reliability_dashboard


PRIVATE_KEYS = {"natal", "profection", "birth", "birthData", "natalProfile"}


def reliability_json_export(payload: Mapping[str, object], *, include_private: bool = False) -> str:
    clean = payload if include_private else _strip_private(payload)
    return json.dumps(clean, indent=2, sort_keys=True, default=str)


def reliability_markdown_export(payload: Mapping[str, object]) -> str:
    lines = ["# Reliability Export"]
    audit = payload.get("audit_snapshot") if isinstance(payload, Mapping) else None
    dashboard = payload.get("reliability_dashboard") if isinstance(payload, Mapping) else None
    if isinstance(audit, Mapping):
        lines.append("## Audit Snapshot")
        lines.append(f"- Reproducibility: {audit.get('reproducibility_hash', 'n/a')}")
        phase2 = audit.get("phase2_tactical_analysis", {})
        if isinstance(phase2, Mapping):
            fast = phase2.get("fast_lane", {})
            if isinstance(fast, Mapping):
                lines.append(f"- Fast Lane: {fast.get('command', 'n/a')} ({fast.get('hard_gate_status', 'n/a')})")
    if isinstance(dashboard, Mapping):
        lines.append("## Dashboard")
        lines.append(format_reliability_dashboard(dashboard))
    return "\n".join(lines)


def _strip_private(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _strip_private(child)
            for key, child in value.items()
            if not any(private.lower() in str(key).lower() for private in PRIVATE_KEYS)
        }
    if isinstance(value, list):
        return [_strip_private(item) for item in value]
    return value
