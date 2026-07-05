"""Location presets for the Python-rendered app."""

from __future__ import annotations

from datetime import date
from dataclasses import asdict, dataclass
from pathlib import Path

from .storage import load_json_dict, load_json_list, save_json
from .quarantine import quarantine_location
from .validation import validate_election_inputs

DEFAULT_TIMEZONE = "America/Los_Angeles"
USER_LOCATIONS_PATH = Path.cwd() / ".electional-locations.json"
LOCATION_SETTINGS_PATH = Path.cwd() / ".electional-location-settings.json"
RECENT_LOCATION_LIMIT = 8
INDIO_LATITUDE = 33.7206
INDIO_LONGITUDE = -116.2156
INDIO_TIMEZONE = "America/Los_Angeles"
INDIO_LOCATION_NAMES = {"indio, california", "indio, california d"}


@dataclass(frozen=True)
class LocationPreset:
    id: str
    name: str
    latitude: float
    longitude: float
    timezone: str

    def to_json(self) -> dict[str, object]:
        return asdict(self)


LOCATION_PRESETS: tuple[LocationPreset, ...] = (
    LocationPreset("los-angeles", "Los Angeles, CA", 34.0522, -118.2437, "America/Los_Angeles"),
    LocationPreset("new-york", "New York, NY", 40.7128, -74.0060, "America/New_York"),
    LocationPreset("london", "London, UK", 51.5074, -0.1278, "Europe/London"),
    LocationPreset("paris", "Paris, France", 48.8566, 2.3522, "Europe/Paris"),
    LocationPreset("tokyo", "Tokyo, Japan", 35.6762, 139.6503, "Asia/Tokyo"),
    LocationPreset("sydney", "Sydney, Australia", -33.8688, 151.2093, "Australia/Sydney"),
)

LOCATION_BY_ID = {location.id: location for location in LOCATION_PRESETS}


def is_known_indio_name(name: str | None) -> bool:
    return str(name or "").strip().lower() in INDIO_LOCATION_NAMES


def corrected_known_location(location: LocationPreset) -> tuple[LocationPreset, bool]:
    if not is_known_indio_name(location.name):
        return location, False
    corrected = LocationPreset(
        location.id,
        location.name,
        INDIO_LATITUDE,
        INDIO_LONGITUDE,
        INDIO_TIMEZONE,
    )
    changed = (
        abs(corrected.latitude - location.latitude) > 0.0001
        or abs(corrected.longitude - location.longitude) > 0.0001
        or corrected.timezone != location.timezone
    )
    return corrected, changed


def corrected_known_location_values(
    name: str,
    latitude: float,
    longitude: float,
    timezone: str,
) -> tuple[float, float, str, bool]:
    if not is_known_indio_name(name):
        return latitude, longitude, timezone, False
    changed = (
        abs(float(latitude) - INDIO_LATITUDE) > 0.0001
        or abs(float(longitude) - INDIO_LONGITUDE) > 0.0001
        or str(timezone).strip() != INDIO_TIMEZONE
    )
    return INDIO_LATITUDE, INDIO_LONGITUDE, INDIO_TIMEZONE, changed


def get_location(location_id: str | None) -> LocationPreset:
    if location_id and location_id in LOCATION_BY_ID:
        return LOCATION_BY_ID[location_id]
    return LOCATION_PRESETS[0]


def location_id_from_name(name: str) -> str:
    safe = "".join(character.lower() if character.isalnum() else "-" for character in name.strip())
    return "user-" + "-".join(part for part in safe.split("-") if part)[:60]


def build_custom_location(name: str, latitude_text: str, longitude_text: str, timezone_text: str) -> LocationPreset:
    label = name.strip() or "Custom Location"
    return LocationPreset(location_id_from_name(label), label, float(latitude_text), float(longitude_text), timezone_text.strip() or "UTC")


def load_user_locations(path: Path = USER_LOCATIONS_PATH) -> list[LocationPreset]:
    locations = []
    corrected_any = False
    for item in load_json_list(path):
        if not isinstance(item, dict):
            continue
        try:
            name = str(item["name"]).strip()
            latitude = float(item["latitude"])
            longitude = float(item["longitude"])
            timezone = str(item["timezone"]).strip()
            errors = validate_election_inputs(date.today().isoformat(), "09:00", str(latitude), str(longitude), timezone)
            if errors:
                quarantine_location(item, errors)
                continue
            location = LocationPreset(str(item.get("id") or location_id_from_name(name)), name, latitude, longitude, timezone)
            location, corrected = corrected_known_location(location)
            corrected_any = corrected_any or corrected
            locations.append(location)
        except (KeyError, TypeError, ValueError) as exc:
            quarantine_location(item, [f"Location parse failed: {exc}"])
            continue
    if corrected_any and path.exists():
        save_user_locations(locations, path)
    return locations


def save_user_locations(locations: list[LocationPreset], path: Path = USER_LOCATIONS_PATH) -> None:
    save_json(path, [location.to_json() for location in locations])


def upsert_user_location(locations: list[LocationPreset], location: LocationPreset) -> list[LocationPreset]:
    remaining = [saved for saved in locations if saved.name.lower() != location.name.lower()]
    return sorted([*remaining, location], key=lambda saved: saved.name.lower())


def combined_location_names(user_locations: list[LocationPreset]) -> list[str]:
    names = [location.name for location in LOCATION_PRESETS]
    for location in user_locations:
        if location.name not in names:
            names.append(location.name)
    return names


def combined_visible_location_names(
    user_locations: list[LocationPreset],
    hidden_builtin_ids: set[str] | list[str] | tuple[str, ...] | None = None,
) -> list[str]:
    hidden = {str(location_id) for location_id in (hidden_builtin_ids or set())}
    names = [location.name for location in LOCATION_PRESETS if location.id not in hidden]
    for location in user_locations:
        if location.name not in names:
            names.append(location.name)
    return names


def resolve_location_by_name(name: str | None, user_locations: list[LocationPreset]) -> LocationPreset | None:
    candidate = (name or "").strip().lower()
    if not candidate:
        return None
    for location in (*LOCATION_PRESETS, *user_locations):
        if location.name.lower() == candidate:
            return location
    return None


def default_location_for_timezone(timezone_name: str = DEFAULT_TIMEZONE) -> LocationPreset:
    for location in LOCATION_PRESETS:
        if location.timezone == timezone_name:
            return location
    return LOCATION_PRESETS[0]


def load_location_settings(path: Path = LOCATION_SETTINGS_PATH) -> dict[str, object]:
    settings = load_json_dict(path)
    if not isinstance(settings, dict):
        return {}
    return settings


def save_location_settings(settings: dict[str, object], path: Path = LOCATION_SETTINGS_PATH) -> None:
    save_json(path, settings)


def _location_from_settings_item(item: object) -> LocationPreset | None:
    if not isinstance(item, dict):
        quarantine_location(item, ["Location settings item is not an object."])
        return None
    try:
        name = str(item["name"]).strip()
        latitude = float(item["latitude"])
        longitude = float(item["longitude"])
        timezone = str(item["timezone"]).strip()
        errors = validate_election_inputs(date.today().isoformat(), "09:00", str(latitude), str(longitude), timezone)
        if errors:
            quarantine_location(item, errors)
            return None
        location = LocationPreset(str(item.get("id") or location_id_from_name(name)), name, latitude, longitude, timezone)
        return corrected_known_location(location)[0]
    except (KeyError, TypeError, ValueError) as exc:
        quarantine_location(item, [f"Location settings parse failed: {exc}"])
        return None


def load_recent_locations(path: Path = LOCATION_SETTINGS_PATH) -> list[LocationPreset]:
    settings = load_location_settings(path)
    raw_locations = settings.get("recent_locations", [])
    if not isinstance(raw_locations, list):
        return []
    locations: list[LocationPreset] = []
    seen_names: set[str] = set()
    for item in raw_locations:
        location = _location_from_settings_item(item)
        if not location:
            continue
        key = location.name.lower()
        if key in seen_names:
            continue
        seen_names.add(key)
        locations.append(location)
        if len(locations) >= RECENT_LOCATION_LIMIT:
            break
    return locations


def save_recent_locations(locations: list[LocationPreset], path: Path = LOCATION_SETTINGS_PATH) -> None:
    settings = load_location_settings(path)
    unique_locations: list[LocationPreset] = []
    seen_names: set[str] = set()
    for location in locations:
        key = location.name.lower()
        if key in seen_names:
            continue
        seen_names.add(key)
        unique_locations.append(location)
        if len(unique_locations) >= RECENT_LOCATION_LIMIT:
            break
    if unique_locations:
        settings["recent_locations"] = [location.to_json() for location in unique_locations]
    else:
        settings.pop("recent_locations", None)
    save_location_settings(settings, path)


def remember_recent_location(
    location: LocationPreset,
    path: Path = LOCATION_SETTINGS_PATH,
    *,
    limit: int = RECENT_LOCATION_LIMIT,
) -> list[LocationPreset]:
    current = load_recent_locations(path)
    remaining = [saved for saved in current if saved.name.lower() != location.name.lower()]
    updated = [location, *remaining][:limit]
    save_recent_locations(updated, path)
    return updated


def load_home_location_name(path: Path = LOCATION_SETTINGS_PATH) -> str | None:
    settings = load_location_settings(path)
    value = settings.get("home_location_name")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def save_home_location_name(name: str | None, path: Path = LOCATION_SETTINGS_PATH) -> None:
    settings = load_location_settings(path)
    if name and name.strip():
        settings["home_location_name"] = name.strip()
    else:
        settings.pop("home_location_name", None)
    save_location_settings(settings, path)


def load_hidden_builtin_location_ids(path: Path = LOCATION_SETTINGS_PATH) -> set[str]:
    settings = load_location_settings(path)
    raw_ids = settings.get("hidden_builtin_location_ids", [])
    if not isinstance(raw_ids, list):
        return set()
    valid_ids = {location.id for location in LOCATION_PRESETS}
    return {str(location_id) for location_id in raw_ids if str(location_id) in valid_ids}


def save_hidden_builtin_location_ids(hidden_ids: set[str] | list[str] | tuple[str, ...], path: Path = LOCATION_SETTINGS_PATH) -> None:
    settings = load_location_settings(path)
    valid_ids = {location.id for location in LOCATION_PRESETS}
    normalized = sorted({str(location_id) for location_id in hidden_ids if str(location_id) in valid_ids})
    if normalized:
        settings["hidden_builtin_location_ids"] = normalized
    else:
        settings.pop("hidden_builtin_location_ids", None)
    save_location_settings(settings, path)


def reset_location_defaults(path: Path = LOCATION_SETTINGS_PATH) -> None:
    settings = load_location_settings(path)
    settings.pop("home_location_name", None)
    settings.pop("hidden_builtin_location_ids", None)
    save_location_settings(settings, path)


def home_location_for_app(
    timezone_name: str = DEFAULT_TIMEZONE,
    user_locations: list[LocationPreset] | None = None,
    settings_path: Path = LOCATION_SETTINGS_PATH,
) -> LocationPreset:
    available_user_locations = user_locations if user_locations is not None else load_user_locations()
    home_name = load_home_location_name(settings_path)
    preferred = resolve_location_by_name(home_name, available_user_locations)
    if preferred:
        return preferred
    return default_location_for_timezone(timezone_name)
