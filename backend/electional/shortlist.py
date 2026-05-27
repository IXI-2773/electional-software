"""Persistent shortlist helpers for promising electional windows."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Any, Mapping, Sequence

from .locations import LocationPreset
from .reporting import election_flag_lines, format_aspect_summary, format_lunar_phase
from .storage import load_json_list, save_json

SHORTLIST_PATH = Path.cwd() / ".electional-shortlist.json"
SHORTLIST_LIMIT = 30


def snapshot_datetime_key(snapshot: Mapping[str, object]) -> str:
    date_value = snapshot.get("date")
    if hasattr(date_value, "isoformat"):
        return str(date_value.isoformat())
    return str(date_value or snapshot.get("formattedTime") or "unknown-time")


def shortlist_entry_id(snapshot: Mapping[str, object], location_name: str, objective: str) -> str:
    source = "|".join(
        (
            snapshot_datetime_key(snapshot),
            location_name,
            objective,
            str(snapshot.get("score", "")),
            str(getattr(snapshot.get("preset"), "id", snapshot.get("preset", ""))),
        )
    )
    return sha1(source.encode("utf-8")).hexdigest()[:12]


def build_shortlist_entry(
    snapshot: Mapping[str, object],
    location: LocationPreset,
    objective: str,
    *,
    added_at: datetime | None = None,
) -> dict[str, object]:
    added = added_at or datetime.now(timezone.utc)
    aspects = snapshot.get("detectedAspects", [])
    aspect_lines = [
        format_aspect_summary(aspect)
        for aspect in aspects
        if isinstance(aspect, dict)
    ][:4]
    flags = election_flag_lines(dict(snapshot))[:5]

    return {
        "id": shortlist_entry_id(snapshot, location.name, objective),
        "addedAt": added.isoformat(),
        "objective": objective,
        "location": location.name,
        "timezone": location.timezone,
        "datetime": snapshot_datetime_key(snapshot),
        "formattedTime": str(snapshot.get("formattedTime", "time unavailable")),
        "score": int(snapshot.get("score", 0)),
        "title": str(snapshot.get("title", "Electional window")),
        "note": str(snapshot.get("note", "")),
        "lunarPhase": format_lunar_phase(dict(snapshot)),
        "aspects": aspect_lines,
        "flags": flags,
    }


def clean_shortlist_entries(entries: Sequence[Any]) -> list[dict[str, object]]:
    cleaned = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        if not item.get("id") or not item.get("formattedTime"):
            continue
        cleaned.append(dict(item))
    return cleaned[:SHORTLIST_LIMIT]


def load_shortlist(path: Path = SHORTLIST_PATH) -> list[dict[str, object]]:
    return clean_shortlist_entries(load_json_list(path))


def save_shortlist(entries: Sequence[Mapping[str, object]], path: Path = SHORTLIST_PATH) -> None:
    save_json(path, clean_shortlist_entries(list(entries)))


def add_shortlist_entry(
    entries: Sequence[Mapping[str, object]],
    entry: Mapping[str, object],
    limit: int = SHORTLIST_LIMIT,
) -> list[dict[str, object]]:
    existing = [dict(item) for item in entries if item.get("id") != entry.get("id")]
    updated = [dict(entry), *existing]
    return updated[:limit]


def format_shortlist_entries(entries: Sequence[Mapping[str, object]]) -> str:
    if not entries:
        return "No shortlisted windows yet."

    blocks = []
    for index, entry in enumerate(entries, start=1):
        aspects = entry.get("aspects") if isinstance(entry.get("aspects"), list) else []
        flags = entry.get("flags") if isinstance(entry.get("flags"), list) else []
        blocks.append(
            "\n".join(
                [
                    f"{index}. {entry.get('formattedTime', 'time unavailable')}  Score {entry.get('score', '?')}",
                    f"   {entry.get('title', 'Electional window')} - {entry.get('objective', 'Objective')}",
                    f"   Location: {entry.get('location', 'n/a')} ({entry.get('timezone', 'n/a')})",
                    f"   Moon: {entry.get('lunarPhase', 'n/a')}",
                    f"   Note: {entry.get('note', '')}",
                    "   Flags: " + ("; ".join(str(flag).lstrip("- ") for flag in flags[:3]) if flags else "n/a"),
                    "   Aspects: " + ("; ".join(str(aspect) for aspect in aspects[:3]) if aspects else "none in orb"),
                ]
            )
        )
    return "\n\n".join(blocks)
