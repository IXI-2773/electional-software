"""iCalendar export helpers for electional windows."""

from __future__ import annotations

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
