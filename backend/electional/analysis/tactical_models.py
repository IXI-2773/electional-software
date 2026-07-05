"""Typed Phase 2 tactical-output models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime


def _dt(value: datetime | None) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


@dataclass(frozen=True)
class FinalCommand:
    command: str
    headline: str
    use_window_start: datetime | None
    use_window_end: datetime | None
    best_minute: datetime | None
    cutoff_time: datetime | None
    do_not_use_before: datetime | None
    do_not_use_after: datetime | None
    primary_reason: str
    supporting_reasons: tuple[str, ...]
    risk_reasons: tuple[str, ...]
    exact_action_required: bool
    confidence: float
    warnings: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        return {
            "command": self.command,
            "headline": self.headline,
            "use_window": {
                "start": _dt(self.use_window_start),
                "end": _dt(self.use_window_end),
                "best_minute": _dt(self.best_minute),
                "cutoff": _dt(self.cutoff_time),
                "do_not_use_before": _dt(self.do_not_use_before),
                "do_not_use_after": _dt(self.do_not_use_after),
            },
            "primary_reason": self.primary_reason,
            "supporting_reasons": list(self.supporting_reasons),
            "risk_reasons": list(self.risk_reasons),
            "exact_action_required": self.exact_action_required,
            "confidence": self.confidence,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class TimingTrap:
    trap_type: str
    severity: str
    title: str
    description: str
    current_time: datetime | None
    trigger_time: datetime | None
    safe_until: datetime | None
    affected_scores: tuple[str, ...]
    recommendation: str
    confidence: float

    def to_json(self) -> dict[str, object]:
        return {
            "trap_type": self.trap_type,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "current_time": _dt(self.current_time),
            "trigger_time": _dt(self.trigger_time),
            "safe_until": _dt(self.safe_until),
            "affected_scores": list(self.affected_scores),
            "recommendation": self.recommendation,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class TimingTrapReport:
    traps: tuple[TimingTrap, ...]
    confidence: float
    warnings: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        return {
            "traps": [trap.to_json() for trap in self.traps],
            "confidence": self.confidence,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class ActionMoment:
    objective_type: str
    elected_moment: str
    preparation_allowed_before_window: bool
    must_happen_inside_window: tuple[str, ...]
    may_happen_before_window: tuple[str, ...]
    avoid_inside_window: tuple[str, ...]
    timestamp_source: str
    instructions: tuple[str, ...]
    warnings: tuple[str, ...]
    confidence: float

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class EventPlaybook:
    objective_type: str
    title: str
    before_window: tuple[str, ...]
    during_window: tuple[str, ...]
    after_window: tuple[str, ...]
    avoid: tuple[str, ...]
    timing_notes: tuple[str, ...]
    confidence: float

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class PracticalityReport:
    score: int | None
    band: str
    summary: str
    supports: tuple[str, ...]
    risks: tuple[str, ...]
    recommendations: tuple[str, ...]
    confidence: float

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class StrategicCalendarEntry:
    start: datetime | None
    end: datetime | None
    best_minute: datetime | None
    objective_type: str
    grade: str
    command: str
    rarity_score: int | None
    practicality_score: int | None
    control_score: int | None
    primary_support: str
    primary_risk: str
    traps: tuple[str, ...]
    tags: tuple[str, ...]

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["start"] = _dt(self.start)
        payload["end"] = _dt(self.end)
        payload["best_minute"] = _dt(self.best_minute)
        payload["traps"] = list(self.traps)
        payload["tags"] = list(self.tags)
        return payload


@dataclass(frozen=True)
class StrategicCalendarReport:
    view: str
    objective_type: str
    entries: tuple[StrategicCalendarEntry, ...]
    avoid_entries: tuple[StrategicCalendarEntry, ...]
    summary: str
    warnings: tuple[str, ...]
    confidence: float

    def to_json(self) -> dict[str, object]:
        return {
            "view": self.view,
            "objective_type": self.objective_type,
            "entries": [entry.to_json() for entry in self.entries],
            "avoid_entries": [entry.to_json() for entry in self.avoid_entries],
            "summary": self.summary,
            "warnings": list(self.warnings),
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class FastLaneReport:
    command: str
    window: str
    best: str
    cutoff: str
    main_reason: str
    main_risk: str
    action: str
    confidence: float
    warnings: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class TacticalAnalysisReport:
    final_command: FinalCommand
    timing_traps: TimingTrapReport
    action_moment: ActionMoment
    playbook: EventPlaybook
    practicality: PracticalityReport
    strategic_calendar_context: StrategicCalendarReport
    fast_lane: FastLaneReport
    warnings: tuple[str, ...]
    confidence: float

    def to_json(self) -> dict[str, object]:
        return {
            "final_command": self.final_command.to_json(),
            "timing_traps": self.timing_traps.to_json(),
            "action_moment": self.action_moment.to_json(),
            "playbook": self.playbook.to_json(),
            "practicality": self.practicality.to_json(),
            "strategic_calendar_context": self.strategic_calendar_context.to_json(),
            "fast_lane": self.fast_lane.to_json(),
            "warnings": list(self.warnings),
            "confidence": self.confidence,
        }
