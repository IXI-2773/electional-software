"""Location presets for the Python-rendered app."""

from __future__ import annotations

from dataclasses import asdict, dataclass


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
