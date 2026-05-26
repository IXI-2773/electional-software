"""Timezone and date helpers for Python chart calculation."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo


def zoned_time_to_utc(date_text: str, time_text: str, timezone_name: str) -> datetime:
    hour, minute = [int(part) for part in (time_text or "09:00").split(":")[:2]]
    year, month, day = [int(part) for part in date_text.split("-")]
    local = datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(timezone_name or "UTC"))
    return local.astimezone(UTC)


def format_in_timezone(moment: datetime, timezone_name: str) -> str:
    local = moment.astimezone(ZoneInfo(timezone_name or "UTC"))
    hour = local.hour % 12 or 12
    meridiem = "AM" if local.hour < 12 else "PM"
    return f"{local:%a}, {local:%b} {local.day}, {hour}:{local:%M} {meridiem} {local:%Z}"


def astronomy_time_string(moment: datetime) -> str:
    utc = moment.astimezone(UTC)
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ")
