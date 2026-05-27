"""Location presets for the Python-rendered app."""

from __future__ import annotations

from datetime import date
from dataclasses import asdict, dataclass
from pathlib import Path

from .storage import load_json_list, save_json
from .validation import validate_election_inputs

DEFAULT_TIMEZONE = "America/Los_Angeles"
USER_LOCATIONS_PATH = Path.cwd() / ".electional-locations.json"


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
    for item in load_json_list(path):
        if not isinstance(item, dict):
            continue
        try:
            name = str(item["name"]).strip()
            latitude = float(item["latitude"])
            longitude = float(item["longitude"])
            timezone = str(item["timezone"]).strip()
            if validate_election_inputs(date.today().isoformat(), "09:00", str(latitude), str(longitude), timezone):
                continue
            locations.append(LocationPreset(str(item.get("id") or location_id_from_name(name)), name, latitude, longitude, timezone))
        except (KeyError, TypeError, ValueError):
            continue
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


def default_location_for_timezone(timezone_name: str = DEFAULT_TIMEZONE) -> LocationPreset:
    for location in LOCATION_PRESETS:
        if location.timezone == timezone_name:
            return location
    return LOCATION_PRESETS[0]
