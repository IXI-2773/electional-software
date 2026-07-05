from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

OBJECTIVE_PACK_ROOT = Path(__file__).resolve().parents[2] / "data" / "objective_packs"

DEFAULT_OBJECTIVE_PACKS: dict[str, dict[str, object]] = {
    "exam": {"objective_type": "exam", "version": "exam_v1", "matter_houses": [9], "natural_significators": ["Mercury", "Jupiter"], "action_moment": "official_exam_start", "fast_lane_action_text": "Click Begin inside the elected window.", "watchlist_defaults": {"minimum_grade": "B+", "minimum_practicality": 70, "exclude_critical_traps": True}},
    "legal": {"objective_type": "legal", "version": "legal_v1", "matter_houses": [7, 9, 10, 4], "natural_significators": ["Saturn", "Jupiter"], "action_moment": "timestamped_filing", "fast_lane_action_text": "Submit the filing inside the elected window."},
    "business": {"objective_type": "business", "version": "business_v1", "matter_houses": [10, 2, 11], "natural_significators": ["Mercury", "Jupiter", "Venus"], "action_moment": "public_launch"},
    "money": {"objective_type": "money", "version": "money_v1", "matter_houses": [2, 11], "natural_significators": ["Jupiter", "Venus"], "action_moment": "payment_submit"},
    "message": {"objective_type": "message", "version": "message_v1", "matter_houses": [3], "natural_significators": ["Mercury", "Moon"], "action_moment": "message_sent", "fast_lane_action_text": "Press Send inside the elected window."},
    "relationship": {"objective_type": "relationship", "version": "relationship_v1", "matter_houses": [1, 7], "natural_significators": ["Venus", "Moon"], "action_moment": "message_or_call_sent"},
    "travel": {"objective_type": "travel", "version": "travel_v1", "matter_houses": [3, 9], "natural_significators": ["Moon", "Mercury"], "action_moment": "trip_milestone"},
    "ritual": {"objective_type": "ritual", "version": "ritual_v1", "matter_houses": [9], "natural_significators": ["Moon", "Jupiter"], "action_moment": "formal_start"},
    "job_application": {"objective_type": "job_application", "version": "job_application_v1", "matter_houses": [10, 6], "natural_significators": ["Mercury", "Saturn"], "action_moment": "application_submit"},
    "negotiation": {"objective_type": "negotiation", "version": "negotiation_v1", "matter_houses": [7, 3], "natural_significators": ["Mercury", "Venus"], "action_moment": "offer_sent"},
    "general": {"objective_type": "general", "version": "general_v1", "matter_houses": [1, 10], "natural_significators": ["Moon"], "action_moment": "irreversible_action"},
}


def validate_objective_pack(pack: Mapping[str, object]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    for key in ("objective_type", "version", "matter_houses", "natural_significators", "action_moment"):
        if key not in pack:
            errors.append(f"Missing {key}.")
    if "matter_houses" in pack and not isinstance(pack["matter_houses"], list):
        errors.append("matter_houses must be a list.")
    return not errors, errors


def load_objective_pack(objective_type: str, *, root: Path | str = OBJECTIVE_PACK_ROOT) -> dict[str, object]:
    key = _key(objective_type)
    path = Path(root) / f"{key}.json"
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            pack = json.load(handle)
    else:
        pack = DEFAULT_OBJECTIVE_PACKS.get(key) or DEFAULT_OBJECTIVE_PACKS["general"]
    ok, errors = validate_objective_pack(pack)
    if not ok:
        raise ValueError("; ".join(errors))
    return dict(pack)


def save_objective_pack(pack: Mapping[str, object], *, root: Path | str = OBJECTIVE_PACK_ROOT) -> Path:
    ok, errors = validate_objective_pack(pack)
    if not ok:
        raise ValueError("; ".join(errors))
    base = Path(root)
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{_key(str(pack['objective_type']))}.json"
    path.write_text(json.dumps(dict(pack), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def default_objective_pack_ids() -> tuple[str, ...]:
    return tuple(DEFAULT_OBJECTIVE_PACKS)


def objective_pack_action_text(objective_type: str) -> str:
    pack = load_objective_pack(objective_type)
    return str(pack.get("fast_lane_action_text") or pack.get("action_moment"))


def _key(value: str) -> str:
    return str(value or "general").lower().replace(" ", "_").replace("/", "_")
