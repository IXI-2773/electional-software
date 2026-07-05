"""Minimal operational output for time-sensitive decisions."""

from __future__ import annotations

from datetime import datetime

from .tactical_models import ActionMoment, FastLaneReport, FinalCommand, PracticalityReport, TimingTrapReport


def build_fast_lane_report(
    final_command: FinalCommand,
    action_moment: ActionMoment,
    traps: TimingTrapReport,
    practicality: PracticalityReport,
) -> FastLaneReport:
    window = _range(final_command.use_window_start, final_command.use_window_end)
    best = _time(final_command.best_minute)
    cutoff = _time(final_command.cutoff_time or final_command.do_not_use_after)
    main_risk = (
        traps.traps[0].title
        if traps.traps
        else final_command.risk_reasons[0]
        if final_command.risk_reasons
        else practicality.risks[0]
        if practicality.risks
        else "No major tactical risk surfaced."
    )
    action = action_moment.instructions[-1] if action_moment.instructions else action_moment.elected_moment
    return FastLaneReport(
        command=final_command.command,
        window=window,
        best=best,
        cutoff=cutoff,
        main_reason=final_command.primary_reason,
        main_risk=main_risk,
        action=action,
        confidence=min(final_command.confidence, practicality.confidence, traps.confidence),
        warnings=final_command.warnings + action_moment.warnings[:1],
    )


def format_fast_lane_text(report: FastLaneReport) -> str:
    return (
        "FAST LANE:\n\n"
        f"{report.command.replace('_', ' ')}\n"
        f"Window: {report.window}\n"
        f"Best: {report.best}\n"
        f"Cutoff: {report.cutoff}\n\n"
        f"Main reason:\n{report.main_reason}\n\n"
        f"Main risk:\n{report.main_risk}\n\n"
        f"Action:\n{report.action}"
    )


def _range(start: datetime | None, end: datetime | None) -> str:
    if start is None and end is None:
        return "unknown"
    if start is not None and end is not None:
        return f"{_time(start)}-{_time(end)}"
    return _time(start or end)


def _time(moment: datetime | None) -> str:
    return moment.strftime("%I:%M %p").lstrip("0") if isinstance(moment, datetime) else "unknown"
