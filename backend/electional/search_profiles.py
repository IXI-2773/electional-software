from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

PROFILE_ROOT = Path(__file__).resolve().parents[2] / "data" / "profiles" / "search_profiles"

DEFAULT_PROFILE_IDS = (
    "exam_strict",
    "legal_filing_strict",
    "message_fast_lane",
    "business_launch",
    "money_practical",
    "relationship_message",
    "emergency_least_bad",
    "natal_profection_heavy",
    "general_practical",
)


def default_search_profiles() -> dict[str, dict[str, object]]:
    return {profile_id: _default_profile(profile_id) for profile_id in DEFAULT_PROFILE_IDS}


def validate_search_profile(profile: Mapping[str, object]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    for key in ("profile_id", "name", "objective_type", "timezone", "date_range_default", "strictness", "objective_pack"):
        if not profile.get(key):
            errors.append(f"Missing {key}.")
    if profile.get("strictness") not in {"strict", "practical", "emergency"}:
        errors.append("strictness must be strict, practical, or emergency.")
    return not errors, errors


def save_search_profile(profile: Mapping[str, object], *, root: Path | str = PROFILE_ROOT) -> Path:
    ok, errors = validate_search_profile(profile)
    if not ok:
        raise ValueError("; ".join(errors))
    base = Path(root)
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{_safe_id(str(profile['profile_id']))}.json"
    path.write_text(json.dumps(dict(profile), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_search_profile(profile_id: str, *, root: Path | str = PROFILE_ROOT) -> dict[str, object]:
    path = Path(root) / f"{_safe_id(profile_id)}.json"
    profile = json.loads(path.read_text(encoding="utf-8")) if path.exists() else _default_profile(profile_id)
    ok, errors = validate_search_profile(profile)
    if not ok:
        raise ValueError("; ".join(errors))
    return dict(profile)


def _default_profile(profile_id: str) -> dict[str, object]:
    objective = "general" if profile_id == "general_practical" else profile_id.split("_", 1)[0]
    strictness = "emergency" if "emergency" in profile_id else "strict" if "strict" in profile_id else "practical"
    return {
        "profile_id": profile_id,
        "name": profile_id.replace("_", " ").title(),
        "objective_type": objective,
        "location": {},
        "timezone": "America/Los_Angeles",
        "date_range_default": "60d",
        "strictness": strictness,
        "rule_pack": "project_default",
        "scoring_profile": f"{objective}_{strictness}_v1",
        "objective_pack": f"{objective}_v1",
        "house_system": "whole-sign",
        "zodiac_mode": "tropical",
        "ayanamsha": "active_project_default",
        "natal_enabled": profile_id == "natal_profection_heavy",
        "profection_enabled": profile_id == "natal_profection_heavy",
        "fast_lane_enabled": True,
        "emergency_mode": strictness == "emergency",
        "version": "profile_v1",
        "export_settings": {},
    }


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value) or "profile"
