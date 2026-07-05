"""Practical usability scoring for candidate windows."""

from __future__ import annotations

from datetime import datetime
from typing import Mapping

from .tactical_models import ActionMoment, PracticalityReport, TimingTrapReport


def build_practicality_report(
    candidate: Mapping[str, object],
    action_moment: ActionMoment,
    traps: TimingTrapReport,
) -> PracticalityReport:
    warnings: list[str] = []
    supports: list[str] = []
    risks: list[str] = []
    recommendations: list[str] = []
    score = 72

    width = _window_width(candidate)
    if width is None:
        warnings.append("Missing stable-window bounds: practicality confidence reduced.")
        score -= 8
    elif width >= 30:
        supports.append("Wide stable window.")
        score += 18
    elif width >= 10:
        supports.append("Usable window length.")
        score += 8
    elif width >= 5:
        risks.append("Narrow window.")
        score -= 12
        recommendations.append("Prepare everything before the window.")
    else:
        risks.append("Extremely narrow window.")
        score -= 28
        recommendations.append("Use only if execution timing is fully controlled.")

    fragility = _fragility(candidate)
    if fragility == "High":
        risks.append("Window fragility is high.")
        score -= 18
    elif fragility == "Medium":
        risks.append("Window fragility is medium.")
        score -= 8
    elif fragility == "Low":
        supports.append("Low fragility.")
        score += 6

    if action_moment.preparation_allowed_before_window:
        supports.append("Preparation can be completed before the window.")
        score += 5
    if "proctor" in " ".join(action_moment.warnings).lower():
        risks.append("Third party may control the exact start.")
        score -= 12
    if "market execution" in " ".join(action_moment.warnings).lower():
        risks.append("External execution timestamp may differ from click time.")
        score -= 8
    if "system timestamp" in action_moment.timestamp_source.lower() or "portal" in action_moment.timestamp_source.lower():
        supports.append("Timestamp source is clear.")
        score += 5

    major_traps = [trap for trap in traps.traps if trap.severity in {"major", "critical"}]
    warnings_traps = [trap for trap in traps.traps if trap.severity == "warning"]
    if major_traps:
        risks.append(f"{len(major_traps)} major or critical timing trap(s).")
        score -= 12 * len(major_traps)
    if warnings_traps:
        risks.append(f"{len(warnings_traps)} warning timing trap(s).")
        score -= 4 * len(warnings_traps)

    data_conf = _diagnostic_score(candidate, "confidence")
    if data_conf is None:
        warnings.append("Missing data-confidence metric.")
        score -= 5
    elif data_conf < 55:
        risks.append("Low data confidence.")
        score -= 20
    elif data_conf < 70:
        risks.append("Medium-low data confidence.")
        score -= 8
    else:
        supports.append("Data confidence is acceptable.")

    score = max(0, min(100, round(score)))
    band = _band(score)
    if not recommendations:
        recommendations.append("Use the final command and action-moment instructions.")
    summary = f"{score}/100 - {band.replace('_', ' ')}."
    confidence = 0.9
    if width is None or warnings:
        confidence = 0.72
    if data_conf is not None and data_conf < 55:
        confidence = min(confidence, 0.62)
    return PracticalityReport(
        score=score,
        band=band,
        summary=summary,
        supports=tuple(dict.fromkeys(supports))[:5],
        risks=tuple(dict.fromkeys(risks))[:5],
        recommendations=tuple(dict.fromkeys(recommendations))[:5],
        confidence=confidence,
    )


def _window_width(candidate: Mapping[str, object]) -> float | None:
    start, end = _bounds(candidate)
    if start is None or end is None:
        return None
    return max(0.0, (end - start).total_seconds() / 60)


def _bounds(candidate: Mapping[str, object]) -> tuple[datetime | None, datetime | None]:
    cluster = candidate.get("cluster")
    stability = candidate.get("windowStability")
    start = _parse_dt(candidate.get("start_time") or candidate.get("startTime") or (cluster.get("start") if isinstance(cluster, Mapping) else None))
    end = _parse_dt(candidate.get("end_time") or candidate.get("endTime") or (cluster.get("end") if isinstance(cluster, Mapping) else None))
    if (start is None or end is None) and isinstance(stability, Mapping):
        start = start or _parse_dt(stability.get("start") or stability.get("start_time"))
        end = end or _parse_dt(stability.get("end") or stability.get("end_time"))
    return start, end


def _parse_dt(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _fragility(candidate: Mapping[str, object]) -> str:
    fragility = candidate.get("fragility")
    if isinstance(fragility, Mapping):
        return str(fragility.get("band") or "")
    stability = candidate.get("windowStability")
    if isinstance(stability, Mapping):
        return str(stability.get("fragility") or stability.get("classification") or "")
    return ""


def _diagnostic_score(candidate: Mapping[str, object], key: str) -> int | None:
    breakdown = candidate.get("scoreBreakdown")
    diagnostics = breakdown.get("diagnostics") if isinstance(breakdown, Mapping) else None
    metric = diagnostics.get(key) if isinstance(diagnostics, Mapping) else None
    try:
        return int(metric.get("score")) if isinstance(metric, Mapping) and metric.get("score") is not None else None
    except (TypeError, ValueError):
        return None


def _band(score: int) -> str:
    if score >= 90:
        return "very_practical"
    if score >= 75:
        return "practical"
    if score >= 60:
        return "usable_with_care"
    if score >= 40:
        return "fragile_difficult"
    return "impractical"
