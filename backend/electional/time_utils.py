"""Timezone and date helpers for Python chart calculation."""

from __future__ import annotations

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo


def parse_local_time(time_text: str | None) -> time:
    cleaned = (time_text or "09:00").strip().upper().replace(".", "")
    formats = ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p")
    for time_format in formats:
        try:
            return datetime.strptime(cleaned, time_format).time()
        except ValueError:
            continue
    raise ValueError("Time must look like 09:00 or 09:00 AM.")


def normalize_time_text(time_text: str | None) -> str:
    parsed = parse_local_time(time_text)
    return f"{parsed.hour:02d}:{parsed.minute:02d}"


def zoned_time_to_utc(date_text: str, time_text: str, timezone_name: str) -> datetime:
    year, month, day = [int(part) for part in date_text.split("-")]
    parsed_time = parse_local_time(time_text)
    local = datetime(year, month, day, parsed_time.hour, parsed_time.minute, tzinfo=ZoneInfo(timezone_name or "UTC"))
    return local.astimezone(UTC)


def format_in_timezone(moment: datetime, timezone_name: str) -> str:
    local = moment.astimezone(ZoneInfo(timezone_name or "UTC"))
    hour = local.hour % 12 or 12
    meridiem = "AM" if local.hour < 12 else "PM"
    return f"{local:%a}, {local:%b} {local.day}, {hour}:{local:%M} {meridiem} {local:%Z}"


def astronomy_time_string(moment: datetime) -> str:
    utc = moment.astimezone(UTC)
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ")
