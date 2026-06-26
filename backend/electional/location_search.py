"""Offline-first city lookup and timezone sanity checks for desktop locations."""

from __future__ import annotations

from dataclasses import dataclass
from zoneinfo import ZoneInfo

from .locations import LOCATION_PRESETS, LocationPreset, location_id_from_name


@dataclass(frozen=True)
class LocationSearchResult:
    location: LocationPreset
    source: str
    score: int


CITY_SEARCH_INDEX: tuple[LocationPreset, ...] = (
    LocationPreset("city-indio-ca", "Indio, CA", 33.7206, -116.2156, "America/Los_Angeles"),
    LocationPreset("city-la-quinta-ca", "La Quinta, CA", 33.6634, -116.3100, "America/Los_Angeles"),
    LocationPreset("city-rancho-mirage-ca", "Rancho Mirage, CA", 33.7397, -116.4128, "America/Los_Angeles"),
    LocationPreset("city-palm-springs-ca", "Palm Springs, CA", 33.8303, -116.5453, "America/Los_Angeles"),
    LocationPreset("city-los-angeles-ca", "Los Angeles, CA", 34.0522, -118.2437, "America/Los_Angeles"),
    LocationPreset("city-san-diego-ca", "San Diego, CA", 32.7157, -117.1611, "America/Los_Angeles"),
    LocationPreset("city-san-francisco-ca", "San Francisco, CA", 37.7749, -122.4194, "America/Los_Angeles"),
    LocationPreset("city-seattle-wa", "Seattle, WA", 47.6062, -122.3321, "America/Los_Angeles"),
    LocationPreset("city-denver-co", "Denver, CO", 39.7392, -104.9903, "America/Denver"),
    LocationPreset("city-phoenix-az", "Phoenix, AZ", 33.4484, -112.0740, "America/Phoenix"),
    LocationPreset("city-chicago-il", "Chicago, IL", 41.8781, -87.6298, "America/Chicago"),
    LocationPreset("city-dallas-tx", "Dallas, TX", 32.7767, -96.7970, "America/Chicago"),
    LocationPreset("city-houston-tx", "Houston, TX", 29.7604, -95.3698, "America/Chicago"),
    LocationPreset("city-new-york-ny", "New York, NY", 40.7128, -74.0060, "America/New_York"),
    LocationPreset("city-miami-fl", "Miami, FL", 25.7617, -80.1918, "America/New_York"),
    LocationPreset("city-london-uk", "London, UK", 51.5074, -0.1278, "Europe/London"),
    LocationPreset("city-paris-france", "Paris, France", 48.8566, 2.3522, "Europe/Paris"),
    LocationPreset("city-rome-italy", "Rome, Italy", 41.9028, 12.4964, "Europe/Rome"),
    LocationPreset("city-berlin-germany", "Berlin, Germany", 52.5200, 13.4050, "Europe/Berlin"),
    LocationPreset("city-madrid-spain", "Madrid, Spain", 40.4168, -3.7038, "Europe/Madrid"),
    LocationPreset("city-tokyo-japan", "Tokyo, Japan", 35.6762, 139.6503, "Asia/Tokyo"),
    LocationPreset("city-sydney-australia", "Sydney, Australia", -33.8688, 151.2093, "Australia/Sydney"),
)


def normalize_location_query(query: str | None) -> str:
    return " ".join(str(query or "").strip().lower().replace(",", " ").split())


def _location_tokens(location: LocationPreset) -> set[str]:
    return set(normalize_location_query(location.name).split())


def _match_score(query: str, location: LocationPreset, source_boost: int = 0) -> int | None:
    normalized_name = normalize_location_query(location.name)
    if not query:
        return None
    if normalized_name == query:
        return 0 + source_boost
    if normalized_name.startswith(query):
        return 10 + source_boost
    query_tokens = set(query.split())
    location_tokens = _location_tokens(location)
    if query_tokens and query_tokens.issubset(location_tokens):
        return 18 + source_boost
    if all(token in normalized_name for token in query_tokens):
        return 28 + source_boost
    if query in normalized_name:
        return 36 + source_boost
    query_tokens = set(query.split())
    location_tokens = _location_tokens(location)
    if query_tokens and any(_token_distance(query_token, location_token) <= 1 for query_token in query_tokens for location_token in location_tokens):
        return 54 + source_boost
    return None


def _token_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if len(left) == len(right):
        differences = [index for index, (left_char, right_char) in enumerate(zip(left, right)) if left_char != right_char]
        if (
            len(differences) == 2
            and differences[1] == differences[0] + 1
            and left[differences[0]] == right[differences[1]]
            and left[differences[1]] == right[differences[0]]
        ):
            return 1
    if not left:
        return len(right)
    if not right:
        return len(left)
    if abs(len(left) - len(right)) > 1:
        return 2
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            cost = 0 if left_char == right_char else 1
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + cost,
                )
            )
        previous = current
    return previous[-1]


def _dedupe_results(results: list[LocationSearchResult]) -> list[LocationSearchResult]:
    unique: dict[str, LocationSearchResult] = {}
    for result in results:
        key = result.location.name.lower()
        existing = unique.get(key)
        if existing is None or result.score < existing.score:
            unique[key] = result
    return sorted(unique.values(), key=lambda result: (result.score, result.location.name.lower()))


def search_city_locations(
    query: str | None,
    *,
    saved_locations: list[LocationPreset] | tuple[LocationPreset, ...] = (),
    recent_locations: list[LocationPreset] | tuple[LocationPreset, ...] = (),
    limit: int = 8,
) -> list[LocationSearchResult]:
    normalized_query = normalize_location_query(query)
    pools: tuple[tuple[str, int, tuple[LocationPreset, ...]], ...] = (
        ("recent", -6, tuple(recent_locations)),
        ("saved", -4, tuple(saved_locations)),
        ("preset", 0, LOCATION_PRESETS),
        ("city", 4, CITY_SEARCH_INDEX),
    )
    results: list[LocationSearchResult] = []
    for source, boost, locations in pools:
        for location in locations:
            score = _match_score(normalized_query, location, boost)
            if score is not None:
                results.append(LocationSearchResult(location, source, score))
    return _dedupe_results(results)[: max(1, int(limit))]


def location_search_result_label(result: LocationSearchResult) -> str:
    location = result.location
    return f"{location.name} | {location.timezone} | {location.latitude:.4f}, {location.longitude:.4f} | {result.source}"


def nearest_index_location(latitude: float, longitude: float) -> LocationPreset | None:
    best_location: LocationPreset | None = None
    best_distance = 999.0
    for location in (*LOCATION_PRESETS, *CITY_SEARCH_INDEX):
        distance = abs(float(latitude) - location.latitude) + abs(float(longitude) - location.longitude)
        if distance < best_distance:
            best_distance = distance
            best_location = location
    return best_location if best_distance <= 0.75 else None


def expected_timezone_for_coordinates(latitude: float, longitude: float, location_name: str = "") -> str | None:
    nearest = nearest_index_location(latitude, longitude)
    if nearest:
        return nearest.timezone
    name = normalize_location_query(location_name)
    if "california" in name or name.endswith(" ca"):
        return "America/Los_Angeles"
    if 24.0 <= latitude <= 50.0 and -125.0 <= longitude <= -66.0:
        if longitude <= -115.0:
            return "America/Los_Angeles"
        if longitude <= -102.0:
            return "America/Denver"
        if longitude <= -85.0:
            return "America/Chicago"
        return "America/New_York"
    return None


def timezone_warning_for_location(location: LocationPreset) -> str:
    try:
        ZoneInfo(location.timezone)
    except Exception:
        return f"Timezone warning: {location.timezone or 'blank'} is not a valid IANA timezone."
    expected = expected_timezone_for_coordinates(location.latitude, location.longitude, location.name)
    if expected and expected != location.timezone:
        return f"Timezone warning: {location.name} looks closer to {expected}, not {location.timezone}."
    return f"Timezone OK: {location.timezone} matches the selected place."


def location_from_search_text(name: str, latitude: float, longitude: float, timezone: str) -> LocationPreset:
    label = name.strip() or "Searched Location"
    return LocationPreset(location_id_from_name(label), label, float(latitude), float(longitude), timezone.strip() or "UTC")
