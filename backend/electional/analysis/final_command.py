"""Generate the direct operational command for an election candidate."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Mapping, Sequence

from .tactical_models import FinalCommand, PracticalityReport, TimingTrapReport


def build_final_command(
    candidate: Mapping[str, object] | None,
    *,
    traps: TimingTrapReport | None = None,
    practicality: PracticalityReport | None = None,
    candidates: Sequence[Mapping[str, object]] | None = None,
    emergency_mode: bool = False,
) -> FinalCommand:
    if not candidate:
        return FinalCommand(
            "SEARCH_NEXT_DAY",
            "No usable window was found in the current result set.",
            None,
            None,
            None,
            None,
            None,
            None,
            "No candidate window was available.",
            (),
            ("No elected moment can be named without a candidate.",),
            False,
            0.5,
            ("Search farther or broaden constraints.",),
        )

    moment = _moment(candidate)
    start, end = _window_bounds(candidate)
    best = _best_minute(candidate) or moment
    cutoff = _cutoff(traps, end)
    warnings: list[str] = []
    risk_reasons: list[str] = []
    supports: list[str] = []

    hard_reasons = _hard_reasons(candidate)
    if hard_reasons:
        return FinalCommand(
            "REJECT",
            "Do not use this election.",
            start,
            end,
            best,
            cutoff,
            None,
            cutoff or end,
            hard_reasons[0],
            (),
            tuple(hard_reasons),
            False,
            0.9,
            (),
        )

    confidence_score = _data_confidence(candidate)
    if confidence_score is not None and confidence_score < 50:
        return FinalCommand(
            "NEEDS_MORE_DATA",
            "Do not treat this as reliable until data confidence improves.",
            start,
            end,
            best,
            cutoff,
            None,
            cutoff,
            f"Data confidence is only {confidence_score}.",
            (),
            ("Low data confidence can invalidate the tactical recommendation.",),
            False,
            0.58,
            ("Resolve calculation/data warnings before use.",),
        )

    score = int(candidate.get("score", 0) or 0)
    grade = _grade(candidate)
    trap_list = list(traps.traps) if traps else []
    major_traps = [trap for trap in trap_list if trap.severity in {"major", "critical"}]
    practical_score = practicality.score if practicality else None
    width = _width_minutes(start, end)
    better_soon = _better_window_soon(candidate, candidates or [])
    if better_soon:
        return FinalCommand(
            "WAIT",
            "Wait for a better nearby window.",
            start,
            end,
            best,
            cutoff,
            None,
            cutoff,
            "A better candidate appears within the next day.",
            (f"Current score {score}; nearby score {better_soon.get('score', '?')}.",),
            ("Do not force this window unless the deadline requires it.",),
            False,
            0.78,
            (),
        )

    if emergency_mode or bool(candidate.get("emergencyOnly")):
        command = "LEAST_BAD_ONLY"
        headline = "Use only as the least-bad emergency option."
        risk_reasons.append("No clean election was found in the current search.")
    elif major_traps or _fragility(candidate) == "High":
        command = "REQUIRES_EXACT_TIMING"
        headline = "Use only if timing can be controlled exactly."
        risk_reasons.extend(trap.title for trap in major_traps[:3])
    elif width is not None and width >= 25 and score >= 80 and (practical_score is None or practical_score >= 75):
        command = "USE_WIDE_WINDOW"
        headline = "Use this broad stable window."
        supports.append("Window is broad enough for real-world execution.")
    elif score >= 85 and grade.startswith(("A", "B")):
        command = "USE"
        headline = "Use this election."
    elif score >= 70:
        command = "USE_IF_NECESSARY"
        headline = "Use only if this timing is necessary."
    else:
        command = "SEARCH_NEXT_DAY"
        headline = "Search farther before using this."
        risk_reasons.append("The candidate is below the normal usability threshold.")

    if traps:
        risk_reasons.extend(trap.title for trap in trap_list[:3])
    if practicality:
        supports.extend(practicality.supports[:2])
        risk_reasons.extend(practicality.risks[:2])
        warnings.extend(practicality.recommendations[:2])
    primary_reason = _primary_reason(candidate, traps, practicality)
    confidence = min(
        0.94,
        max(
            0.45,
            (traps.confidence if traps else 0.75) * 0.35
            + (practicality.confidence if practicality else 0.75) * 0.35
            + 0.3,
        ),
    )
    return FinalCommand(
        command,
        headline,
        start,
        end,
        best,
        cutoff,
        start if command in {"REQUIRES_EXACT_TIMING", "USE"} else None,
        cutoff or end,
        primary_reason,
        tuple(dict.fromkeys(supports))[:5],
        tuple(dict.fromkeys(risk_reasons))[:6],
        command in {"REQUIRES_EXACT_TIMING", "USE_FAST_LANE"},
        round(confidence, 2),
        tuple(dict.fromkeys(warnings))[:5],
    )


def _primary_reason(candidate: Mapping[str, object], traps: TimingTrapReport | None, practicality: PracticalityReport | None) -> str:
    if traps and traps.traps:
        return traps.traps[0].description
    if practicality and practicality.summary:
        return practicality.summary
    evaluation = candidate.get("scoreBreakdown")
    evaluation = evaluation.get("evaluation") if isinstance(evaluation, Mapping) else None
    if isinstance(evaluation, Mapping) and evaluation.get("summary"):
        return str(evaluation.get("summary"))
    return f"Candidate score is {candidate.get('score', 'unknown')}."


def _hard_reasons(candidate: Mapping[str, object]) -> list[str]:
    reasons = candidate.get("rejectionReasons")
    if isinstance(reasons, list) and reasons:
        return [str(reason) for reason in reasons]
    failure = candidate.get("failureAnalysis")
    hard = failure.get("hardFailures") if isinstance(failure, Mapping) else None
    if isinstance(hard, list) and hard:
        return [str(item.get("label") if isinstance(item, Mapping) else item) for item in hard]
    if bool(candidate.get("hardReject")):
        return ["Hard reject flag present."]
    moon = candidate.get("moonCondition")
    void = moon.get("voidOfCourse") if isinstance(moon, Mapping) else None
    if isinstance(void, Mapping) and void.get("isVoid"):
        return ["Moon is void."]
    return []


def _better_window_soon(candidate: Mapping[str, object], candidates: Sequence[Mapping[str, object]]) -> Mapping[str, object] | None:
    now = _moment(candidate)
    if now is None:
        return None
    score = int(candidate.get("score", 0) or 0)
    for other in candidates:
        if other is candidate:
            continue
        other_time = _moment(other)
        if other_time is None or other_time <= now or other_time > now + timedelta(days=1):
            continue
        if int(other.get("score", 0) or 0) >= score + 8 and not _hard_reasons(other):
            return other
    return None


def _data_confidence(candidate: Mapping[str, object]) -> int | None:
    confidence = candidate.get("confidence")
    if isinstance(confidence, Mapping):
        label = str(confidence.get("data_confidence") or "")
        if label == "Low":
            return 45
    breakdown = candidate.get("scoreBreakdown")
    diagnostics = breakdown.get("diagnostics") if isinstance(breakdown, Mapping) else None
    metric = diagnostics.get("confidence") if isinstance(diagnostics, Mapping) else None
    try:
        return int(metric.get("score")) if isinstance(metric, Mapping) and metric.get("score") is not None else None
    except (TypeError, ValueError):
        return None


def _grade(candidate: Mapping[str, object]) -> str:
    breakdown = candidate.get("scoreBreakdown")
    evaluation = breakdown.get("evaluation") if isinstance(breakdown, Mapping) else None
    if isinstance(evaluation, Mapping) and evaluation.get("grade"):
        return str(evaluation.get("grade"))
    score = int(candidate.get("score", 0) or 0)
    if score >= 90:
        return "A"
    if score >= 85:
        return "A-"
    if score >= 80:
        return "B+"
    if score >= 75:
        return "B"
    if score >= 70:
        return "C+"
    return "C"


def _fragility(candidate: Mapping[str, object]) -> str:
    fragility = candidate.get("fragility")
    if isinstance(fragility, Mapping):
        return str(fragility.get("band") or "")
    return ""


def _moment(candidate: Mapping[str, object]) -> datetime | None:
    return _parse_dt(candidate.get("date") or candidate.get("datetime") or candidate.get("peak_time"))


def _best_minute(candidate: Mapping[str, object]) -> datetime | None:
    return _parse_dt(candidate.get("best_minute") or candidate.get("peak_time") or candidate.get("date"))


def _window_bounds(candidate: Mapping[str, object]) -> tuple[datetime | None, datetime | None]:
    cluster = candidate.get("cluster")
    start = _parse_dt(candidate.get("start_time") or candidate.get("startTime") or (cluster.get("start") if isinstance(cluster, Mapping) else None))
    end = _parse_dt(candidate.get("end_time") or candidate.get("endTime") or (cluster.get("end") if isinstance(cluster, Mapping) else None))
    if start is None:
        start = _moment(candidate)
    if end is None and start is not None:
        end = start + timedelta(minutes=10)
    return start, end


def _cutoff(traps: TimingTrapReport | None, end: datetime | None) -> datetime | None:
    safe_until = [trap.safe_until for trap in (traps.traps if traps else ()) if trap.safe_until is not None]
    if safe_until:
        return min(safe_until)
    return end


def _parse_dt(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _width_minutes(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return max(0.0, (end - start).total_seconds() / 60)
