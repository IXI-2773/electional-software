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
SHORTLIST_TAG_CHOICES = (
    "Best for launch",
    "Backup",
    "Client-safe",
    "Cleanest",
    "Steady",
    "High visibility",
)


def entry_int(entry: Mapping[str, object], key: str, default: int = 0) -> int:
    try:
        return int(entry.get(key, default))
    except (TypeError, ValueError):
        return default


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


def normalize_shortlist_tags(tags: object) -> list[str]:
    if not isinstance(tags, Sequence) or isinstance(tags, (str, bytes)):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        text = str(tag).strip()
        if not text:
            continue
        lowered = text.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(text)
    return normalized[:6]


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
    breakdown = snapshot.get("scoreBreakdown", {})
    diagnostics = breakdown.get("diagnostics", {}) if isinstance(breakdown, Mapping) else {}
    confidence = diagnostics.get("confidence", {}) if isinstance(diagnostics, Mapping) else {}
    cleanliness = diagnostics.get("cleanliness", {}) if isinstance(diagnostics, Mapping) else {}
    volatility = diagnostics.get("volatility", {}) if isinstance(diagnostics, Mapping) else {}
    readiness = diagnostics.get("readiness", {}) if isinstance(diagnostics, Mapping) else {}

    return {
        "id": shortlist_entry_id(snapshot, location.name, objective),
        "addedAt": added.isoformat(),
        "objective": objective,
        "location": location.name,
        "latitude": float(location.latitude),
        "longitude": float(location.longitude),
        "timezone": location.timezone,
        "datetime": snapshot_datetime_key(snapshot),
        "formattedTime": str(snapshot.get("formattedTime", "time unavailable")),
        "score": int(snapshot.get("score", 0)),
        "confidence": int(confidence.get("score", 0)) if isinstance(confidence, Mapping) else 0,
        "cleanliness": int(cleanliness.get("score", 0)) if isinstance(cleanliness, Mapping) else 0,
        "volatility": int(volatility.get("score", 0)) if isinstance(volatility, Mapping) else 0,
        "readiness": int(readiness.get("score", 0)) if isinstance(readiness, Mapping) else 0,
        "title": str(snapshot.get("title", "Electional window")),
        "note": str(snapshot.get("note", "")),
        "lunarPhase": format_lunar_phase(dict(snapshot)),
        "aspects": aspect_lines,
        "flags": flags,
        "tags": normalize_shortlist_tags(snapshot.get("shortlistTags", [])),
    }


def shortlist_sort_key(entry: Mapping[str, object]) -> tuple[int, int, int, int, int, str]:
    score = entry_int(entry, "score", 0)
    confidence = entry_int(entry, "confidence", 0)
    cleanliness = entry_int(entry, "cleanliness", 0)
    readiness = entry_int(entry, "readiness", 0)
    volatility = -entry_int(entry, "volatility", 99)
    return (score, confidence, cleanliness, readiness, volatility, str(entry.get("formattedTime", "")))


def shortlist_cleanliness_key(entry: Mapping[str, object]) -> tuple[int, int, int, int, int]:
    return (
        entry_int(entry, "cleanliness", 0),
        entry_int(entry, "confidence", 0),
        entry_int(entry, "readiness", 0),
        -entry_int(entry, "volatility", 99),
        entry_int(entry, "score", 0),
    )


def shortlist_confidence_key(entry: Mapping[str, object]) -> tuple[int, int, int, int, int]:
    return (
        entry_int(entry, "confidence", 0),
        entry_int(entry, "cleanliness", 0),
        entry_int(entry, "readiness", 0),
        -entry_int(entry, "volatility", 99),
        entry_int(entry, "score", 0),
    )


def shortlist_steady_key(entry: Mapping[str, object]) -> tuple[int, int, int, int, int]:
    return (
        -entry_int(entry, "volatility", 99),
        entry_int(entry, "cleanliness", 0),
        entry_int(entry, "confidence", 0),
        entry_int(entry, "readiness", 0),
        entry_int(entry, "score", 0),
    )


def clean_shortlist_entries(entries: Sequence[Any]) -> list[dict[str, object]]:
    cleaned = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        if not item.get("id") or not item.get("formattedTime"):
            continue
        normalized = dict(item)
        normalized["tags"] = normalize_shortlist_tags(normalized.get("tags", []))
        if "latitude" in normalized:
            try:
                normalized["latitude"] = float(normalized["latitude"])
            except (TypeError, ValueError):
                normalized.pop("latitude", None)
        if "longitude" in normalized:
            try:
                normalized["longitude"] = float(normalized["longitude"])
            except (TypeError, ValueError):
                normalized.pop("longitude", None)
        cleaned.append(normalized)
    ranked = sorted(cleaned, key=shortlist_sort_key, reverse=True)
    return ranked[:SHORTLIST_LIMIT]


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
    return sorted(updated, key=shortlist_sort_key, reverse=True)[:limit]


def shortlist_entry_by_id(entries: Sequence[Mapping[str, object]], entry_id: str) -> dict[str, object] | None:
    for entry in entries:
        if str(entry.get("id")) == str(entry_id):
            return dict(entry)
    return None


def update_shortlist_tags(
    entries: Sequence[Mapping[str, object]],
    entry_id: str,
    tags: Sequence[str],
) -> list[dict[str, object]]:
    updated: list[dict[str, object]] = []
    normalized_tags = normalize_shortlist_tags(tags)
    for entry in entries:
        current = dict(entry)
        if str(current.get("id")) == str(entry_id):
            current["tags"] = normalized_tags
        updated.append(current)
    return clean_shortlist_entries(updated)


def add_shortlist_tag(
    entries: Sequence[Mapping[str, object]],
    entry_id: str,
    tag: str,
) -> list[dict[str, object]]:
    target = shortlist_entry_by_id(entries, entry_id)
    if not target:
        return clean_shortlist_entries(entries)
    tags = normalize_shortlist_tags([*(target.get("tags", []) if isinstance(target.get("tags"), list) else []), tag])
    return update_shortlist_tags(entries, entry_id, tags)


def remove_shortlist_tag(
    entries: Sequence[Mapping[str, object]],
    entry_id: str,
    tag: str,
) -> list[dict[str, object]]:
    target = shortlist_entry_by_id(entries, entry_id)
    if not target:
        return clean_shortlist_entries(entries)
    tags = [
        existing
        for existing in normalize_shortlist_tags(target.get("tags", []))
        if existing.casefold() != str(tag).strip().casefold()
    ]
    return update_shortlist_tags(entries, entry_id, tags)


def shortlist_batch_diagnostics(entries: Sequence[Mapping[str, object]]) -> dict[str, object]:
    cleaned = [
        dict(entry)
        for entry in entries
        if isinstance(entry, Mapping) and entry.get("formattedTime")
    ]
    if not cleaned:
        return {
            "count": 0,
            "averages": {"score": 0, "confidence": 0, "cleanliness": 0, "readiness": 0, "volatility": 0},
            "objectiveMix": [],
            "topOverall": [],
            "topCleanest": [],
            "topConfident": [],
            "topSteady": [],
        }
    cleaned = sorted(cleaned, key=shortlist_sort_key, reverse=True)

    count = len(cleaned)
    averages = {
        "score": round(sum(entry_int(entry, "score", 0) for entry in cleaned) / count),
        "confidence": round(sum(entry_int(entry, "confidence", 0) for entry in cleaned) / count),
        "cleanliness": round(sum(entry_int(entry, "cleanliness", 0) for entry in cleaned) / count),
        "readiness": round(sum(entry_int(entry, "readiness", 0) for entry in cleaned) / count),
        "volatility": round(sum(entry_int(entry, "volatility", 0) for entry in cleaned) / count),
    }

    objective_counts: dict[str, int] = {}
    for entry in cleaned:
        objective = str(entry.get("objective", "Objective"))
        objective_counts[objective] = objective_counts.get(objective, 0) + 1

    objective_mix = sorted(objective_counts.items(), key=lambda item: (-item[1], item[0]))
    top_overall = sorted(cleaned, key=shortlist_sort_key, reverse=True)[:3]
    top_cleanest = sorted(cleaned, key=shortlist_cleanliness_key, reverse=True)[:3]
    top_confident = sorted(cleaned, key=shortlist_confidence_key, reverse=True)[:3]
    top_steady = sorted(cleaned, key=shortlist_steady_key, reverse=True)[:3]
    return {
        "count": count,
        "averages": averages,
        "objectiveMix": objective_mix,
        "topOverall": top_overall,
        "topCleanest": top_cleanest,
        "topConfident": top_confident,
        "topSteady": top_steady,
    }


def format_shortlist_batch_diagnostics(entries: Sequence[Mapping[str, object]]) -> str:
    diagnostics = shortlist_batch_diagnostics(entries)
    if not diagnostics["count"]:
        return "Shortlist Diagnostics\nNo shortlisted windows yet."

    def format_compact_entry(entry: Mapping[str, object]) -> str:
        return (
            f"- {entry.get('formattedTime', 'time unavailable')} | "
            f"Score {entry_int(entry, 'score', 0)} | "
            f"Conf {entry_int(entry, 'confidence', 0)} | "
            f"Clean {entry_int(entry, 'cleanliness', 0)} | "
            f"Read {entry_int(entry, 'readiness', 0)} | "
            f"Vol {entry_int(entry, 'volatility', 0)} | "
            f"{entry.get('objective', 'Objective')}"
        )

    averages = diagnostics["averages"]
    objective_mix = diagnostics["objectiveMix"]
    lines = [
        "Shortlist Diagnostics",
        f"Saved picks: {diagnostics['count']}",
        (
            "Batch averages: "
            f"Score {averages['score']}  "
            f"Conf {averages['confidence']}  "
            f"Clean {averages['cleanliness']}  "
            f"Read {averages['readiness']}  "
            f"Vol {averages['volatility']}"
        ),
        "Objective mix: " + "; ".join(f"{objective} x{count}" for objective, count in objective_mix[:4]),
        "",
        "Best Overall",
        *(format_compact_entry(entry) for entry in diagnostics["topOverall"]),
        "",
        "Cleanest Saved Windows",
        *(format_compact_entry(entry) for entry in diagnostics["topCleanest"]),
        "",
        "Highest-Confidence Windows",
        *(format_compact_entry(entry) for entry in diagnostics["topConfident"]),
        "",
        "Steadiest Windows",
        *(format_compact_entry(entry) for entry in diagnostics["topSteady"]),
    ]
    return "\n".join(lines)


def build_shortlist_compare_text(
    entries: Sequence[Mapping[str, object]],
    first_id: str | None,
    second_id: str | None,
) -> str:
    if not first_id or not second_id:
        return "Shortlist Compare\nChoose two shortlisted windows from the board to compare them side by side."
    first = shortlist_entry_by_id(entries, first_id)
    second = shortlist_entry_by_id(entries, second_id)
    if not first or not second:
        return "Shortlist Compare\nOne or both shortlist selections are no longer available."

    def metric_winner(key: str, lower_is_better: bool = False) -> str:
        first_value = entry_int(first, key, 0)
        second_value = entry_int(second, key, 0)
        if first_value == second_value:
            return "Tie"
        if lower_is_better:
            return "A" if first_value < second_value else "B"
        return "A" if first_value > second_value else "B"

    def format_entry(label: str, entry: Mapping[str, object]) -> list[str]:
        tags = normalize_shortlist_tags(entry.get("tags", []))
        return [
            f"{label}: {entry.get('formattedTime', 'time unavailable')}",
            f"Objective: {entry.get('objective', 'Objective')}",
            f"Score {entry_int(entry, 'score', 0)} | Conf {entry_int(entry, 'confidence', 0)} | Clean {entry_int(entry, 'cleanliness', 0)} | Read {entry_int(entry, 'readiness', 0)} | Vol {entry_int(entry, 'volatility', 0)}",
            f"Tags: {', '.join(tags) if tags else 'none'}",
            f"Note: {entry.get('note', '')}",
        ]

    lines = [
        "Shortlist Compare",
        "",
        *format_entry("A", first),
        "",
        *format_entry("B", second),
        "",
        "Metric Edge",
        f"- Score: {metric_winner('score')}",
        f"- Confidence: {metric_winner('confidence')}",
        f"- Cleanliness: {metric_winner('cleanliness')}",
        f"- Readiness: {metric_winner('readiness')}",
        f"- Volatility: {metric_winner('volatility', lower_is_better=True)}",
    ]
    return "\n".join(lines)


def format_shortlist_entries(entries: Sequence[Mapping[str, object]]) -> str:
    if not entries:
        return "No shortlisted windows yet."

    diagnostics = format_shortlist_batch_diagnostics(entries)
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
                    (
                        f"   Diagnostics: Conf {entry.get('confidence', '?')}  "
                        f"Clean {entry.get('cleanliness', '?')}  "
                        f"Read {entry.get('readiness', '?')}  "
                        f"Vol {entry.get('volatility', '?')}"
                    ),
                    "   Tags: " + (", ".join(normalize_shortlist_tags(entry.get("tags", []))) or "none"),
                    f"   Moon: {entry.get('lunarPhase', 'n/a')}",
                    f"   Note: {entry.get('note', '')}",
                    "   Flags: " + ("; ".join(str(flag).lstrip("- ") for flag in flags[:3]) if flags else "n/a"),
                    "   Aspects: " + ("; ".join(str(aspect) for aspect in aspects[:3]) if aspects else "none in orb"),
                ]
            )
        )
    return diagnostics + "\n\nDetailed Picks\n\n" + "\n\n".join(blocks)
