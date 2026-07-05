"""Detect tactical timing traps around a candidate window."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Mapping, Sequence

from .tactical_models import TimingTrap, TimingTrapReport


def detect_timing_traps(candidate: Mapping[str, object], neighbors: Sequence[Mapping[str, object]] | None = None) -> TimingTrapReport:
    traps: list[TimingTrap] = []
    warnings: list[str] = []
    now = _moment(candidate)
    samples = _timeline(candidate, neighbors)
    if not samples:
        warnings.append("Insufficient neighboring samples for full timing-trap detection.")

    traps.extend(_score_cliff_traps(candidate, samples, now))
    traps.extend(_hard_gate_traps(candidate, samples, now))
    traps.extend(_angle_traps(candidate, samples, now))
    traps.extend(_moon_traps(candidate, samples, now))
    traps.extend(_benefic_leaving_traps(candidate, samples, now))
    traps.extend(_control_traps(candidate, samples, now))
    traps.extend(_window_width_traps(candidate, now))
    traps.extend(_contaminated_support_traps(candidate, now))

    traps.sort(key=lambda item: (_severity_rank(item.severity), item.trigger_time or datetime.max, item.trap_type))
    confidence = 0.9 if samples else 0.55
    if warnings:
        confidence = min(confidence, 0.62)
    return TimingTrapReport(tuple(traps), confidence, tuple(warnings))


def _timeline(candidate: Mapping[str, object], neighbors: Sequence[Mapping[str, object]] | None) -> list[Mapping[str, object]]:
    if neighbors:
        return [sample for sample in neighbors if isinstance(sample, Mapping)]
    stability = candidate.get("windowStability")
    samples = stability.get("samples") if isinstance(stability, Mapping) else None
    return [sample for sample in samples if isinstance(sample, Mapping)] if isinstance(samples, list) else []


def _score_cliff_traps(candidate: Mapping[str, object], samples: list[Mapping[str, object]], now: datetime | None) -> list[TimingTrap]:
    if not samples or now is None:
        return []
    current = int(candidate.get("score", 0) or 0)
    future = [
        (sample, int(sample.get("score", current) or current))
        for sample in samples
        if (_moment(sample) or now) >= now and (_moment(sample) or now) <= now + timedelta(minutes=10)
    ]
    if not future:
        return []
    lowest_sample, lowest = min(future, key=lambda item: item[1])
    drop = current - lowest
    if drop < 10:
        return []
    severity = "critical" if drop >= 25 else "major" if drop >= 15 else "warning"
    trigger = _moment(lowest_sample)
    return [
        TimingTrap(
            "score_cliff",
            severity,
            "Score cliff after peak",
            f"Score drops by {drop} points within 10 minutes.",
            now,
            trigger,
            _safe_until(trigger),
            ("score",),
            "Use before the drop or skip this cluster.",
            0.84,
        )
    ]


def _hard_gate_traps(candidate: Mapping[str, object], samples: list[Mapping[str, object]], now: datetime | None) -> list[TimingTrap]:
    if not samples or now is None:
        return []
    for sample in samples:
        moment = _moment(sample)
        if moment is None or moment < now or moment > now + timedelta(minutes=10):
            continue
        reasons = _hard_reasons(sample)
        if reasons:
            return [
                TimingTrap(
                    "hard_gate_approaching",
                    "critical",
                    "Hard gate approaching",
                    f"Hard failure appears soon: {reasons[0]}.",
                    now,
                    moment,
                    _safe_until(moment),
                    ("hard_gates",),
                    "Do not use after the safe cutoff.",
                    0.9,
                )
            ]
    return []


def _angle_traps(candidate: Mapping[str, object], samples: list[Mapping[str, object]], now: datetime | None) -> list[TimingTrap]:
    if not samples or now is None:
        return []
    for sample in samples:
        moment = _moment(sample)
        if moment is None or moment < now or moment > now + timedelta(minutes=15):
            continue
        malefic = _angular_malefic(sample, max_distance=4.0)
        if malefic:
            severity = "critical" if moment <= now + timedelta(minutes=5) else "major"
            return [
                TimingTrap(
                    "malefic_angle_approaching",
                    severity,
                    f"{malefic} becomes too angular soon",
                    f"{malefic} enters the angular danger orb within {round((moment - now).total_seconds() / 60)} minutes.",
                    now,
                    moment,
                    _safe_until(moment),
                    ("angularity", "risk_profile"),
                    f"Use before {_time_text(_safe_until(moment))} or skip this cluster.",
                    0.88,
                )
            ]
    return []


def _moon_traps(candidate: Mapping[str, object], samples: list[Mapping[str, object]], now: datetime | None) -> list[TimingTrap]:
    if not samples or now is None:
        return []
    for sample in samples:
        moment = _moment(sample)
        if moment is None or moment < now or moment > now + timedelta(minutes=15):
            continue
        moon = sample.get("moonCondition")
        void = moon.get("voidOfCourse") if isinstance(moon, Mapping) else None
        if isinstance(void, Mapping) and void.get("isVoid"):
            return [
                TimingTrap(
                    "moon_void_soon",
                    "major",
                    "Moon goes void soon",
                    "Moon becomes void shortly after the candidate peak.",
                    now,
                    moment,
                    _safe_until(moment),
                    ("moon_condition",),
                    "Use before the Moon void cutoff or skip.",
                    0.84,
                )
            ]
    return []


def _benefic_leaving_traps(candidate: Mapping[str, object], samples: list[Mapping[str, object]], now: datetime | None) -> list[TimingTrap]:
    if not samples or now is None or not _angular_benefic(candidate):
        return []
    for sample in samples:
        moment = _moment(sample)
        if moment is None or moment < now or moment > now + timedelta(minutes=10):
            continue
        if not _angular_benefic(sample):
            return [
                TimingTrap(
                    "benefic_leaving_angle",
                    "warning",
                    "Benefic leaves the angle soon",
                    "A key angular benefic is no longer angular in the nearby samples.",
                    now,
                    moment,
                    _safe_until(moment),
                    ("benefic_support", "angularity"),
                    "Prefer the earlier part of this window.",
                    0.78,
                )
            ]
    return []


def _control_traps(candidate: Mapping[str, object], samples: list[Mapping[str, object]], now: datetime | None) -> list[TimingTrap]:
    if not samples or now is None:
        return []
    current_control = _control_score(candidate)
    if current_control is None or current_control < 50:
        return []
    for sample in samples:
        moment = _moment(sample)
        if moment is None or moment < now or moment > now + timedelta(minutes=15):
            continue
        score = _control_score(sample)
        if score is not None and score < 50:
            return [
                TimingTrap(
                    "control_index_cliff",
                    "major",
                    "Control index drops soon",
                    f"Control falls from {current_control} to {score} in nearby samples.",
                    now,
                    moment,
                    _safe_until(moment),
                    ("control_index",),
                    "Use before control drops below contested territory.",
                    0.82,
                )
            ]
    return []


def _window_width_traps(candidate: Mapping[str, object], now: datetime | None) -> list[TimingTrap]:
    start, end = _window_bounds(candidate)
    if start is None or end is None:
        return []
    width = (end - start).total_seconds() / 60
    if width >= 5:
        return []
    severity = "critical" if width < 2 else "major"
    return [
        TimingTrap(
            "window_too_narrow",
            severity,
            "Window is too narrow",
            f"Usable window is only {width:.0f} minutes wide.",
            now,
            end,
            end,
            ("window_stability", "practicality"),
            "Prepare everything before the window or choose a wider candidate.",
            0.86,
        )
    ]


def _contaminated_support_traps(candidate: Mapping[str, object], now: datetime | None) -> list[TimingTrap]:
    advanced = candidate.get("advancedAnalysis")
    contradictions = advanced.get("contradictions") if isinstance(advanced, Mapping) else None
    if not isinstance(contradictions, list):
        return []
    for item in contradictions:
        if isinstance(item, Mapping) and item.get("id") == "benefic_contaminated_by_bad_house":
            return [
                TimingTrap(
                    "contaminated_support",
                    "major",
                    "Benefic support is contaminated",
                    str(item.get("description") or "A positive testimony carries bad-house contamination."),
                    now,
                    None,
                    None,
                    ("benefic_support", "analysis_confidence"),
                    "Treat the support as mixed and prefer a cleaner benefic if available.",
                    0.82,
                )
            ]
    return []


def _moment(item: Mapping[str, object]) -> datetime | None:
    value = item.get("date") or item.get("datetime") or item.get("start")
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _window_bounds(candidate: Mapping[str, object]) -> tuple[datetime | None, datetime | None]:
    cluster = candidate.get("cluster")
    stability = candidate.get("windowStability")
    start = _parse_dt(candidate.get("start_time") or candidate.get("startTime") or (cluster.get("start") if isinstance(cluster, Mapping) else None))
    end = _parse_dt(candidate.get("end_time") or candidate.get("endTime") or (cluster.get("end") if isinstance(cluster, Mapping) else None))
    if start is None and isinstance(stability, Mapping):
        start = _parse_dt(stability.get("start") or stability.get("start_time"))
        end = _parse_dt(stability.get("end") or stability.get("end_time"))
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


def _hard_reasons(sample: Mapping[str, object]) -> list[str]:
    reasons = sample.get("rejectionReasons")
    if isinstance(reasons, list) and reasons:
        return [str(reason) for reason in reasons]
    failure = sample.get("failureAnalysis")
    hard = failure.get("hardFailures") if isinstance(failure, Mapping) else None
    if isinstance(hard, list) and hard:
        return [str(item.get("label") if isinstance(item, Mapping) else item) for item in hard]
    if bool(sample.get("hardReject")):
        return ["hard reject flag"]
    moon = sample.get("moonCondition")
    void = moon.get("voidOfCourse") if isinstance(moon, Mapping) else None
    if isinstance(void, Mapping) and void.get("isVoid"):
        return ["Moon void"]
    if _angular_malefic(sample, max_distance=3.0):
        return ["angular malefic"]
    return []


def _angular_malefic(item: Mapping[str, object], *, max_distance: float) -> str:
    for position in item.get("positions", []):
        if not isinstance(position, Mapping) or position.get("name") not in {"Mars", "Saturn"}:
            continue
        closest = position.get("closestAngle")
        try:
            distance = float(closest.get("distance", 99) if isinstance(closest, Mapping) else 99)
        except (TypeError, ValueError):
            distance = 99
        if position.get("isAngular") and distance <= max_distance:
            return str(position.get("name"))
    return ""


def _angular_benefic(item: Mapping[str, object]) -> bool:
    return any(
        isinstance(position, Mapping)
        and position.get("name") in {"Venus", "Jupiter"}
        and bool(position.get("isAngular"))
        for position in item.get("positions", [])
    )


def _control_score(item: Mapping[str, object]) -> int | None:
    advanced = item.get("advancedAnalysis")
    control = advanced.get("control_index") if isinstance(advanced, Mapping) else None
    try:
        return int(control.get("control_score")) if isinstance(control, Mapping) and control.get("control_score") is not None else None
    except (TypeError, ValueError):
        return None


def _safe_until(trigger: datetime | None) -> datetime | None:
    return trigger - timedelta(minutes=2) if isinstance(trigger, datetime) else None


def _time_text(moment: datetime | None) -> str:
    return moment.strftime("%I:%M %p").lstrip("0") if isinstance(moment, datetime) else "the cutoff"


def _severity_rank(severity: str) -> int:
    return {"critical": 0, "major": 1, "warning": 2, "info": 3}.get(severity, 4)
