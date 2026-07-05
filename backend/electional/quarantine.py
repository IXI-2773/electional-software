"""Quarantine invalid imported data without deleting it."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Mapping

QUARANTINE_DIR = Path.cwd() / "data" / "quarantine"
CORRUPTED_ASPECT_PROFILES_PATH = QUARANTINE_DIR / "corrupted_aspect_profiles.json"
BAD_LOCATIONS_PATH = QUARANTINE_DIR / "bad_locations.json"
FAILED_RULES_PATH = QUARANTINE_DIR / "failed_rules.json"
MAX_QUARANTINE_RECORDS = 250


def _load_records(path: Path) -> list[dict[str, object]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def quarantine_record(path: Path, category: str, payload: object, errors: list[str] | tuple[str, ...]) -> dict[str, object]:
    """Append a bad-data record for later review."""

    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "quarantinedAt": datetime.now(timezone.utc).isoformat(),
        "category": category,
        "errors": [str(error) for error in errors],
        "payload": payload,
    }
    records = _load_records(path)
    records.append(record)
    if len(records) > MAX_QUARANTINE_RECORDS:
        records = records[-MAX_QUARANTINE_RECORDS:]
    try:
        path.write_text(json.dumps(records, indent=2, sort_keys=True, default=str), encoding="utf-8")
    except OSError as exc:
        record["writeError"] = str(exc)
    return record


def quarantine_aspect_profile(payload: object, errors: list[str] | tuple[str, ...]) -> dict[str, object]:
    return quarantine_record(CORRUPTED_ASPECT_PROFILES_PATH, "aspect-profile", payload, errors)


def quarantine_location(payload: object, errors: list[str] | tuple[str, ...]) -> dict[str, object]:
    return quarantine_record(BAD_LOCATIONS_PATH, "location", payload, errors)


def quarantine_rule(payload: Mapping[str, object] | object, errors: list[str] | tuple[str, ...]) -> dict[str, object]:
    return quarantine_record(FAILED_RULES_PATH, "rule", payload, errors)
