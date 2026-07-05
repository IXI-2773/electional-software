"""iCalendar export helpers for electional windows."""

from __future__ import annotations

import csv
import json
from io import StringIO
from datetime import datetime, timedelta, timezone
from typing import Mapping, Sequence


def ics_escape(value: object) -> str:
    text = str(value)
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def parse_ics_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        moment = value
    else:
        text = str(value)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def format_ics_datetime(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def fold_ics_line(line: str, limit: int = 74) -> list[str]:
    if len(line) <= limit:
        return [line]
    lines = []
    current = line
    while len(current) > limit:
        lines.append(current[:limit])
        current = " " + current[limit:]
    lines.append(current)
    return lines


def calendar_event_from_entry(
    entry: Mapping[str, object],
    *,
    duration_minutes: int = 60,
    product_id: str = "-//Electional Software//Candidate Windows//EN",
) -> str:
    start = parse_ics_datetime(entry.get("datetime"))
    end = start + timedelta(minutes=duration_minutes)
    flags = entry.get("flags") if isinstance(entry.get("flags"), list) else []
    aspects = entry.get("aspects") if isinstance(entry.get("aspects"), list) else []
    description_parts = [
        f"Score: {entry.get('score', '?')}",
        f"Objective: {entry.get('objective', 'n/a')}",
        f"Moon: {entry.get('lunarPhase', 'n/a')}",
        f"Note: {entry.get('note', '')}",
    ]
    if flags:
        description_parts.append("Flags: " + "; ".join(str(flag).lstrip("- ") for flag in flags[:5]))
    if aspects:
        description_parts.append("Aspects: " + "; ".join(str(aspect) for aspect in aspects[:5]))
    tactical = entry.get("tacticalAnalysis")
    if isinstance(tactical, Mapping):
        command = tactical.get("final_command", {})
        action = tactical.get("action_moment", {})
        traps = tactical.get("timing_traps", {})
        if isinstance(command, Mapping):
            description_parts.append(f"Command: {command.get('command', 'n/a')}")
            description_parts.append(f"Best minute: {(command.get('use_window') or {}).get('best_minute', 'n/a') if isinstance(command.get('use_window'), Mapping) else 'n/a'}")
            description_parts.append(f"Primary risk: {'; '.join(str(item) for item in command.get('risk_reasons', [])[:2]) if isinstance(command.get('risk_reasons'), list) else 'n/a'}")
        if isinstance(action, Mapping):
            description_parts.append(f"Action moment: {action.get('elected_moment', 'n/a')}")
        trap_items = traps.get("traps") if isinstance(traps, Mapping) else None
        if isinstance(trap_items, list) and trap_items:
            description_parts.append("Timing traps: " + "; ".join(str(item.get("title")) for item in trap_items[:3] if isinstance(item, Mapping)))

    lines = [
        "BEGIN:VEVENT",
        f"UID:{ics_escape(entry.get('id', format_ics_datetime(start)))}@electional-software",
        f"DTSTAMP:{format_ics_datetime(datetime.now(timezone.utc))}",
        f"DTSTART:{format_ics_datetime(start)}",
        f"DTEND:{format_ics_datetime(end)}",
        f"SUMMARY:{ics_escape('Electional window ' + str(entry.get('score', '?')) + ' - ' + str(entry.get('objective', 'Objective')))}",
        f"LOCATION:{ics_escape(entry.get('location', ''))}",
        f"DESCRIPTION:{ics_escape(chr(10).join(description_parts))}",
        "END:VEVENT",
    ]
    return "\r\n".join(line for raw in lines for line in fold_ics_line(raw))


def calendar_from_entries(
    entries: Sequence[Mapping[str, object]],
    *,
    duration_minutes: int = 60,
) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "PRODID:-//Electional Software//Candidate Windows//EN",
    ]
    lines.extend(calendar_event_from_entry(entry, duration_minutes=duration_minutes) for entry in entries)
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def strategic_calendar_json(payload: Mapping[str, object]) -> str:
    return json.dumps({"strategic_calendar": payload}, indent=2, sort_keys=True, default=str)


def strategic_calendar_csv(entries: Sequence[Mapping[str, object]]) -> str:
    fields = [
        "start",
        "end",
        "best_minute",
        "objective_type",
        "grade",
        "command",
        "rarity_score",
        "practicality_score",
        "control_score",
        "primary_support",
        "primary_risk",
        "tags",
    ]
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for entry in entries:
        row = {field: entry.get(field, "") for field in fields}
        tags = row.get("tags")
        if isinstance(tags, list):
            row["tags"] = ";".join(str(tag) for tag in tags)
        writer.writerow(row)
    return buffer.getvalue()


def strategic_calendar_ics(entries: Sequence[Mapping[str, object]], *, location: str = "") -> str:
    event_entries = []
    for index, entry in enumerate(entries):
        start = entry.get("start") or entry.get("best_minute")
        if not start:
            continue
        event_entries.append(
            {
                "id": f"strategic-{index}-{entry.get('command', 'window')}",
                "datetime": start,
                "score": entry.get("grade", ""),
                "objective": entry.get("objective_type", "Objective"),
                "location": location,
                "note": (
                    f"Best minute: {entry.get('best_minute', 'n/a')}\n"
                    f"Command: {entry.get('command', 'n/a')}\n"
                    f"Primary support: {entry.get('primary_support', 'n/a')}\n"
                    f"Primary risk: {entry.get('primary_risk', 'n/a')}"
                ),
                "flags": entry.get("tags", []),
                "aspects": [],
            }
        )
    return calendar_from_entries(event_entries, duration_minutes=30)
