"""Desktop session-state persistence and cleanup."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from .locations import home_location_for_app
from .point_sets import DEFAULT_POINT_SET_ID, get_point_set
from .presets import ELECTIONAL_PRESETS
from .search import (
    DEFAULT_MAX_RESULTS,
    DEFAULT_MAXIMUM_VOLATILITY,
    DEFAULT_MINIMUM_CLEANLINESS,
    DEFAULT_MINIMUM_CONFIDENCE,
    DEFAULT_MINIMUM_FIT,
    DEFAULT_MINIMUM_SCORE,
    DEFAULT_SCAN_HOURS,
    DEFAULT_STEP_MINUTES,
)
from .storage import load_json_dict, save_json
from .systems import DEFAULT_HOUSE_SYSTEM_ID, DEFAULT_ZODIAC_SYSTEM_ID, get_house_system, get_zodiac_system
from .time_utils import normalize_time_text
from .validation import validate_election_inputs

SESSION_PATH = Path.cwd() / ".electional-session.json"
OBJECTIVES = (
    "Launch or publish",
    "Meeting or negotiation",
    "Creative work",
    "Relationship timing",
    "Travel departure",
    "Money or business",
    "Health or surgery caution",
)
DEFAULT_DISPLAY_OPTIONS = {
    "show_aspects": True,
    "show_lots": False,
    "show_nodes": False,
    "show_fixed_stars": False,
    "compact_wheel": True,
    "wheel_zoom": 0.88,
    "point_set": DEFAULT_POINT_SET_ID,
    "page_mode": "wheel",
}


def infer_point_set_id(display_options: dict[str, Any]) -> str:
    explicit_point_set = display_options.get("point_set")
    if explicit_point_set:
        return get_point_set(explicit_point_set).id
    if display_options.get("show_fixed_stars") or display_options.get("show_lots"):
        return "full-electional"
    if display_options.get("show_nodes"):
        return "planets-nodes"
    return DEFAULT_POINT_SET_ID


def infer_page_mode_id(display_options: dict[str, Any]) -> str:
    page_mode = str(display_options.get("page_mode") or "").strip().lower()
    if page_mode in {"wheel", "wheel-aspectarian", "classical-point-data", "medieval-data", "transit-search"}:
        return page_mode
    return "wheel"


def load_session_state(path: Path = SESSION_PATH) -> dict[str, Any]:
    return load_json_dict(path)


def save_session_state(state: dict[str, Any], path: Path = SESSION_PATH) -> None:
    save_json(path, state)


def clean_session_state(state: dict[str, Any]) -> dict[str, Any]:
    default_location = home_location_for_app()
    date_text = str(state.get("date") or date.today().isoformat())
    time_text = str(state.get("time") or "09:00")
    location_name = str(state.get("location_name") or default_location.name)
    latitude = str(state.get("latitude") or f"{default_location.latitude:.4f}")
    longitude = str(state.get("longitude") or f"{default_location.longitude:.4f}")
    timezone = str(state.get("timezone") or default_location.timezone)
    if validate_election_inputs(date_text, time_text, latitude, longitude, timezone):
        date_text = date.today().isoformat()
        time_text = "09:00"
        location_name = default_location.name
        latitude = f"{default_location.latitude:.4f}"
        longitude = f"{default_location.longitude:.4f}"
        timezone = default_location.timezone

    preset_names = {preset.name for preset in ELECTIONAL_PRESETS}
    objective = str(state.get("objective") or OBJECTIVES[0])
    preset = str(state.get("preset") or ELECTIONAL_PRESETS[1].name)
    zodiac_system = get_zodiac_system(str(state.get("zodiac_system") or DEFAULT_ZODIAC_SYSTEM_ID)).name
    house_system = get_house_system(str(state.get("house_system") or DEFAULT_HOUSE_SYSTEM_ID)).name
    aspects = state.get("aspects") if isinstance(state.get("aspects"), dict) else {}
    display_options = state.get("display_options") if isinstance(state.get("display_options"), dict) else {}
    try:
        wheel_zoom = float(display_options.get("wheel_zoom", DEFAULT_DISPLAY_OPTIONS["wheel_zoom"]))
    except (TypeError, ValueError):
        wheel_zoom = float(DEFAULT_DISPLAY_OPTIONS["wheel_zoom"])

    return {
        "date": date_text,
        "time": normalize_time_text(time_text),
        "location_preset": str(state.get("location_preset") or location_name),
        "location_name": location_name,
        "latitude": latitude,
        "longitude": longitude,
        "timezone": timezone,
        "objective": objective if objective in OBJECTIVES else OBJECTIVES[0],
        "preset": preset if preset in preset_names else ELECTIONAL_PRESETS[1].name,
        "zodiac_system": zodiac_system,
        "house_system": house_system,
        "aspects": {str(key): bool(value) for key, value in aspects.items()},
        "scan_hours": str(state.get("scan_hours") or DEFAULT_SCAN_HOURS),
        "step_minutes": str(state.get("step_minutes") or DEFAULT_STEP_MINUTES),
        "minimum_score": str(state.get("minimum_score") or DEFAULT_MINIMUM_SCORE),
        "minimum_fit": str(state.get("minimum_fit") or DEFAULT_MINIMUM_FIT),
        "minimum_confidence": str(state.get("minimum_confidence") or DEFAULT_MINIMUM_CONFIDENCE),
        "minimum_cleanliness": str(state.get("minimum_cleanliness") or DEFAULT_MINIMUM_CLEANLINESS),
        "maximum_volatility": str(state.get("maximum_volatility") or DEFAULT_MAXIMUM_VOLATILITY),
        "max_results": str(state.get("max_results") or DEFAULT_MAX_RESULTS),
        "avoid_major_stress": bool(state.get("avoid_major_stress", False)),
        "require_applying_support": bool(state.get("require_applying_support", False)),
        "require_angular_benefic": bool(state.get("require_angular_benefic", False)),
        "avoid_angular_malefics": bool(state.get("avoid_angular_malefics", False)),
        "require_moon_non_void": bool(state.get("require_moon_non_void", False)),
        "avoid_objective_antipatterns": bool(state.get("avoid_objective_antipatterns", False)),
        "display_options": {
            **{
                key: bool(display_options.get(key, default_value))
                for key, default_value in DEFAULT_DISPLAY_OPTIONS.items()
                if isinstance(default_value, bool)
            },
            "wheel_zoom": max(0.76, min(1.04, wheel_zoom)),
            "point_set": infer_point_set_id(display_options),
            "page_mode": infer_page_mode_id(display_options),
        },
    }
