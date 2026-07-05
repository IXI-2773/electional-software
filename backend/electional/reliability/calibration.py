"""Outcome calibration summaries for Phase 1 and Phase 2 signals."""

from __future__ import annotations

from statistics import mean
from typing import Mapping, Sequence


def build_outcome_calibration(records: Sequence[Mapping[str, object]]) -> dict[str, object]:
    return {
        "sample_size": len(records),
        "fast_lane_by_command": _group(records, lambda row: _path(row, "tacticalAnalysis", "fast_lane", "command")),
        "final_command_by_command": _group(records, lambda row: _path(row, "tacticalAnalysis", "final_command", "command")),
        "practicality_by_band": _group(records, lambda row: _path(row, "tacticalAnalysis", "practicality", "band")),
        "timing_trap_by_severity": _trap_group(records),
        "control_index_by_band": _group(records, lambda row: _path(row, "advancedAnalysis", "control_index", "band")),
        "resistance_advantage": _group(records, lambda row: _path(row, "advancedAnalysis", "resistance_analysis", "advantage")),
        "contaminated_benefic": _group(records, _contaminated_benefic_key),
        "action_moment_controllability": _group(records, _action_control_key),
        "warnings": ["Small sample size: calibration confidence is low."] if len(records) < 20 else [],
    }


def format_calibration_summary(calibration: Mapping[str, object]) -> str:
    lines = [f"Outcome Calibration: {calibration.get('sample_size', 0)} logged outcome(s)."]
    fast = calibration.get("fast_lane_by_command", {})
    if isinstance(fast, Mapping):
        lines.append("Fast Lane Calibration:")
        for key, value in fast.items():
            if isinstance(value, Mapping):
                lines.append(f"- {key}: average {value.get('average_outcome')}, sample {value.get('sample_size')}")
    warnings = calibration.get("warnings", [])
    if isinstance(warnings, list):
        lines.extend(f"- Warning: {warning}" for warning in warnings)
    return "\n".join(lines)


def _group(records: Sequence[Mapping[str, object]], key_fn) -> dict[str, object]:
    buckets: dict[str, list[float]] = {}
    for row in records:
        key = key_fn(row) or "unknown"
        try:
            outcome = float(row.get("outcome_score", row.get("outcomeScore", 0)) or 0)
        except (TypeError, ValueError):
            continue
        buckets.setdefault(str(key), []).append(outcome)
    return {
        key: {
            "average_outcome": round(mean(values), 2),
            "sample_size": len(values),
            "confidence": "low" if len(values) < 10 else "medium" if len(values) < 30 else "high",
        }
        for key, values in sorted(buckets.items())
    }


def _trap_group(records: Sequence[Mapping[str, object]]) -> dict[str, object]:
    expanded: list[dict[str, object]] = []
    for row in records:
        traps = _path(row, "tacticalAnalysis", "timing_traps", "traps")
        if isinstance(traps, list) and traps:
            for trap in traps:
                expanded.append({"outcome_score": row.get("outcome_score", row.get("outcomeScore", 0)), "severity": trap.get("severity") if isinstance(trap, Mapping) else "unknown"})
        else:
            expanded.append({"outcome_score": row.get("outcome_score", row.get("outcomeScore", 0)), "severity": "none"})
    return _group(expanded, lambda row: row.get("severity"))


def _contaminated_benefic_key(row: Mapping[str, object]) -> str:
    contradictions = _path(row, "advancedAnalysis", "contradictions")
    if isinstance(contradictions, list):
        return "contaminated_benefic" if any(isinstance(item, Mapping) and item.get("id") == "benefic_contaminated_by_bad_house" for item in contradictions) else "no_contaminated_benefic"
    return "unknown"


def _action_control_key(row: Mapping[str, object]) -> str:
    action = _path(row, "tacticalAnalysis", "action_moment")
    if not isinstance(action, Mapping):
        return "unknown"
    warnings = " ".join(str(item) for item in action.get("warnings", []))
    return "third_party_or_external" if "proctor" in warnings.lower() or "market execution" in warnings.lower() else "user_controlled"


def _path(row: Mapping[str, object], *keys: str) -> object:
    current: object = row
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current
