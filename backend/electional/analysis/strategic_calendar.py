"""Strategic calendar summaries from tactical candidate results."""

from __future__ import annotations

from datetime import datetime
from typing import Mapping, Sequence

from .tactical_models import StrategicCalendarEntry, StrategicCalendarReport


def build_strategic_calendar(
    windows: Sequence[Mapping[str, object]],
    *,
    objective: str | None = None,
    view: str = "daily",
    top_n: int = 10,
) -> StrategicCalendarReport:
    entries = [calendar_entry_from_window(window, objective=objective) for window in windows if isinstance(window, Mapping)]
    entries.sort(key=lambda item: (_avoid_rank(item), -(item.practicality_score or 0), item.start or datetime.max))
    useful = tuple(entry for entry in entries if "avoid" not in entry.tags)[:top_n]
    avoid = tuple(entry for entry in entries if "avoid" in entry.tags)[:top_n]
    summary = _summary(view, useful, avoid)
    return StrategicCalendarReport(
        view=view,
        objective_type=str(objective or (windows[0].get("objective") if windows else "general") or "general"),
        entries=useful,
        avoid_entries=avoid,
        summary=summary,
        warnings=(),
        confidence=0.84 if entries else 0.55,
    )


def calendar_entry_from_window(window: Mapping[str, object], *, objective: str | None = None) -> StrategicCalendarEntry:
    tactical = window.get("tacticalAnalysis")
    final_command = tactical.get("final_command") if isinstance(tactical, Mapping) else {}
    practicality = tactical.get("practicality") if isinstance(tactical, Mapping) else {}
    traps_payload = tactical.get("timing_traps") if isinstance(tactical, Mapping) else {}
    advanced = window.get("advancedAnalysis")
    control = advanced.get("control_index") if isinstance(advanced, Mapping) else {}
    rarity = window.get("rarity")
    evaluation = window.get("scoreBreakdown")
    evaluation = evaluation.get("evaluation") if isinstance(evaluation, Mapping) else {}
    command = str(final_command.get("command") if isinstance(final_command, Mapping) else "") or _fallback_command(window)
    traps = traps_payload.get("traps") if isinstance(traps_payload, Mapping) else []
    traps = traps if isinstance(traps, list) else []
    trap_titles = tuple(str(trap.get("title")) for trap in traps if isinstance(trap, Mapping))
    tags = _tags(window, command, practicality, traps_payload, control, rarity)
    start = _parse_dt(_nested(final_command, "use_window", "start")) or _parse_dt(window.get("date"))
    end = _parse_dt(_nested(final_command, "use_window", "end")) or start
    best = _parse_dt(_nested(final_command, "use_window", "best_minute")) or start
    return StrategicCalendarEntry(
        start=start,
        end=end,
        best_minute=best,
        objective_type=str(objective or window.get("objective") or "general"),
        grade=str(evaluation.get("grade") if isinstance(evaluation, Mapping) else "") or _grade(window),
        command=command,
        rarity_score=_int((rarity or {}).get("rarity_score") if isinstance(rarity, Mapping) else None),
        practicality_score=_int(practicality.get("score") if isinstance(practicality, Mapping) else None),
        control_score=_int(control.get("control_score") if isinstance(control, Mapping) else None),
        primary_support=_primary_support(window, final_command),
        primary_risk=_primary_risk(window, final_command, trap_titles),
        traps=trap_titles,
        tags=tags,
    )


def format_strategic_calendar_text(report: StrategicCalendarReport) -> str:
    title = f"{report.view.title()} Strategic Calendar"
    lines = [title, report.summary, ""]
    if report.entries:
        lines.append("Top Windows:")
        for index, entry in enumerate(report.entries, start=1):
            lines.append(
                f"{index}. {_time_range(entry)} - {entry.command.replace('_', ' ').title()} "
                f"({entry.grade}); practicality {entry.practicality_score if entry.practicality_score is not None else 'n/a'}"
            )
            lines.append(f"   Risk: {entry.primary_risk}")
    if report.avoid_entries:
        lines.extend(["", "Avoid:"])
        for entry in report.avoid_entries[:5]:
            lines.append(f"- {_time_range(entry)} - {entry.primary_risk}")
    return "\n".join(lines).rstrip()


def _tags(
    window: Mapping[str, object],
    command: str,
    practicality: object,
    traps_payload: object,
    control: object,
    rarity: object,
) -> tuple[str, ...]:
    tags: list[str] = []
    if command in {"REJECT", "NEEDS_MORE_DATA"}:
        tags.append("avoid")
    if command == "LEAST_BAD_ONLY":
        tags.append("least_bad")
    if command == "USE_WIDE_WINDOW":
        tags.append("wide_window")
    if command == "REQUIRES_EXACT_TIMING":
        tags.append("fragile_peak")
    if isinstance(rarity, Mapping) and str(rarity.get("rarity_label")) in {"rare", "very_rare", "Unique", "Very Rare", "Rare"}:
        tags.append("rare_window")
    if isinstance(control, Mapping) and _int(control.get("control_score")) is not None:
        tags.append("high_control" if int(control.get("control_score") or 0) >= 70 else "low_control" if int(control.get("control_score") or 0) < 50 else "contested_control")
    objective = str(window.get("objective") or "").lower()
    for key, tag in (("exam", "good_for_exam"), ("legal", "good_for_legal"), ("business", "good_for_business"), ("message", "good_for_message"), ("money", "good_for_money"), ("relationship", "good_for_relationship")):
        if key in objective:
            tags.append(tag)
    traps = traps_payload.get("traps") if isinstance(traps_payload, Mapping) else []
    for trap in traps if isinstance(traps, list) else []:
        if isinstance(trap, Mapping) and "Moon" in str(trap.get("title")):
            tags.append("moon_risk")
        if isinstance(trap, Mapping) and "Mars" in str(trap.get("title")):
            tags.append("mars_risk")
        if isinstance(trap, Mapping) and "Saturn" in str(trap.get("title")):
            tags.append("saturn_risk")
    if isinstance(practicality, Mapping) and _int(practicality.get("score")) is not None and int(practicality.get("score") or 0) >= 75:
        tags.append("clean_window")
    return tuple(dict.fromkeys(tags))


def _fallback_command(window: Mapping[str, object]) -> str:
    if bool(window.get("hardReject")):
        return "REJECT"
    score = int(window.get("score", 0) or 0)
    return "USE" if score >= 85 else "USE_IF_NECESSARY" if score >= 70 else "SEARCH_NEXT_DAY"


def _summary(view: str, entries: tuple[StrategicCalendarEntry, ...], avoid: tuple[StrategicCalendarEntry, ...]) -> str:
    if not entries and avoid:
        return "Only avoid or emergency entries are present."
    if not entries:
        return "No strategic calendar windows available."
    best = entries[0]
    return f"Best {view} window: {_time_range(best)}. Command: {best.command.replace('_', ' ').title()}."


def _primary_support(window: Mapping[str, object], final_command: object) -> str:
    if isinstance(final_command, Mapping):
        reasons = final_command.get("supporting_reasons")
        if isinstance(reasons, list) and reasons:
            return str(reasons[0])
    return f"Score {window.get('score', 'n/a')}"


def _primary_risk(window: Mapping[str, object], final_command: object, traps: tuple[str, ...]) -> str:
    if traps:
        return traps[0]
    if isinstance(final_command, Mapping):
        risks = final_command.get("risk_reasons")
        if isinstance(risks, list) and risks:
            return str(risks[0])
    return "No primary tactical risk surfaced."


def _time_range(entry: StrategicCalendarEntry) -> str:
    if entry.start is None:
        return "time unknown"
    if entry.end is None or entry.end == entry.start:
        return entry.start.strftime("%Y-%m-%d %I:%M %p").lstrip("0")
    return f"{entry.start.strftime('%Y-%m-%d %I:%M %p').lstrip('0')}-{entry.end.strftime('%I:%M %p').lstrip('0')}"


def _parse_dt(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _nested(mapping: object, first: str, second: str) -> object:
    if not isinstance(mapping, Mapping):
        return None
    child = mapping.get(first)
    return child.get(second) if isinstance(child, Mapping) else None


def _int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _grade(window: Mapping[str, object]) -> str:
    score = int(window.get("score", 0) or 0)
    return "A" if score >= 90 else "A-" if score >= 85 else "B+" if score >= 80 else "B" if score >= 75 else "C+"


def _avoid_rank(entry: StrategicCalendarEntry) -> int:
    return 1 if "avoid" in entry.tags else 0
