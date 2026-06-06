"""Python ephemeris backed by Astronomy Engine."""

from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache
from math import cos, floor, radians

import astronomy

from .professional import engine_name, swiss_ecliptic_coordinates
from .systems import apply_zodiac_system, get_zodiac_system
from .time_utils import astronomy_time_string

ZODIAC_SIGNS = (
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
)

PLANET_MODELS = (
    {"id": "sun", "name": "Sun", "astronomy_body": "Sun"},
    {"id": "moon", "name": "Moon", "astronomy_body": "Moon"},
    {"id": "mercury", "name": "Mercury", "astronomy_body": "Mercury"},
    {"id": "venus", "name": "Venus", "astronomy_body": "Venus"},
    {"id": "mars", "name": "Mars", "astronomy_body": "Mars"},
    {"id": "jupiter", "name": "Jupiter", "astronomy_body": "Jupiter"},
    {"id": "saturn", "name": "Saturn", "astronomy_body": "Saturn"},
    {"id": "uranus", "name": "Uranus", "astronomy_body": "Uranus"},
    {"id": "neptune", "name": "Neptune", "astronomy_body": "Neptune"},
    {"id": "pluto", "name": "Pluto", "astronomy_body": "Pluto"},
)

ENGINE_NAME = engine_name()
STATION_DIAGNOSTIC_BODIES = {"Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"}
STATION_SCAN_DAYS = 7


def normalize_degrees(value: float) -> float:
    return value % 360


def signed_longitude_delta(start_longitude: float, end_longitude: float) -> float:
    return ((end_longitude - start_longitude + 180) % 360) - 180


def get_zodiac_position(longitude: float) -> dict[str, object]:
    normalized = normalize_degrees(longitude)
    sign_index = floor(normalized / 30)
    sign_degree = normalized % 30
    minute = round((sign_degree % 1) * 60)
    degree = floor(sign_degree)

    if minute == 60:
        degree += 1
        minute = 0

    if degree == 30:
        degree = 0
        sign_index = (sign_index + 1) % 12

    return {
        "sign": ZODIAC_SIGNS[sign_index],
        "abbreviation": ZODIAC_SIGNS[sign_index][:2],
        "degree": degree,
        "minute": minute,
        "kind": "sign",
    }


def format_zodiac_position(zodiac: dict[str, object]) -> str:
    sign = str(zodiac.get("sign") or zodiac.get("abbreviation") or "Unknown")
    return f"{int(zodiac.get('degree', 0))} {sign} {int(zodiac.get('minute', 0)):02d}"


def get_zodiac_position_for_system(
    longitude: float,
    moment: datetime,
    system_id_or_name: str | None,
    *,
    tropical_longitude: float | None = None,
) -> dict[str, object]:
    system = get_zodiac_system(system_id_or_name)
    if system.mode != "constellational":
        return get_zodiac_position(longitude)

    from .constellations import constellation_for_longitude, constellation_span_degrees

    reference_longitude = normalize_degrees(tropical_longitude if tropical_longitude is not None else longitude)
    constellation = constellation_for_longitude(reference_longitude)
    total_minutes = round(float(constellation["degreeIntoConstellation"]) * 60)
    span_minutes = round(float(constellation["spanDegrees"]) * 60)
    if total_minutes >= span_minutes:
        next_span = constellation.get("nextConstellation", {})
        if isinstance(next_span, dict) and next_span.get("name"):
            return {
                "sign": str(next_span.get("name")),
                "abbreviation": str(next_span.get("abbreviation") or str(next_span.get("name"))[:3]),
                "degree": 0,
                "minute": 0,
                "kind": "constellation",
                "spanDegrees": constellation_span_degrees(str(next_span.get("id"))),
            }
        total_minutes = max(0, span_minutes - 1)
    degree, minute = divmod(total_minutes, 60)
    return {
        "sign": str(constellation["name"]),
        "abbreviation": str(constellation["abbreviation"]),
        "degree": int(degree),
        "minute": int(minute),
        "kind": "constellation",
        "spanDegrees": float(constellation["spanDegrees"]),
    }


@lru_cache(maxsize=4096)
def _cached_ecliptic_coordinates(body_name: str, time_text: str) -> tuple[float, float, float | None]:
    time = astronomy.Time(time_text)

    if body_name == "Sun":
        ecliptic = astronomy.SunPosition(time)
    else:
        body = getattr(astronomy.Body, body_name)
        vector = astronomy.GeoVector(body, time, True)
        ecliptic = astronomy.Ecliptic(vector)

    vector = getattr(ecliptic, "vec", None)
    distance = vector.Length() if vector is not None and hasattr(vector, "Length") else None

    return ecliptic.elat, ecliptic.elon, distance


@lru_cache(maxsize=4096)
def _cached_equatorial_coordinates(body_name: str, time_text: str) -> tuple[float, float]:
    time = astronomy.Time(time_text)
    body = getattr(astronomy.Body, body_name)
    equatorial = astronomy.Equator(body, time, astronomy.Observer(0, 0, 0), True, True)
    return equatorial.ra, equatorial.dec


def get_ecliptic_coordinates(body_name: str, moment: datetime) -> dict[str, float | None]:
    professional = swiss_ecliptic_coordinates(body_name, moment)
    right_ascension, declination = _cached_equatorial_coordinates(body_name, astronomy_time_string(moment))
    if professional:
        return {
            **professional,
            "rightAscensionHours": right_ascension,
            "declination": declination,
        }
    latitude, longitude, distance = _cached_ecliptic_coordinates(body_name, astronomy_time_string(moment))
    return {
        "latitude": latitude,
        "longitude": longitude,
        "distanceAu": distance,
        "rightAscensionHours": right_ascension,
        "declination": declination,
    }


@lru_cache(maxsize=8192)
def _cached_daily_longitude_change(body_name: str, time_text: str) -> float:
    moment = datetime.fromisoformat(time_text)
    current = get_ecliptic_coordinates(body_name, moment)
    swiss_speed = current.get("dailyLongitudeChange")
    if swiss_speed is not None:
        return float(swiss_speed)
    previous = normalize_degrees(float(get_ecliptic_coordinates(body_name, moment - timedelta(hours=12))["longitude"]))
    next_position = normalize_degrees(float(get_ecliptic_coordinates(body_name, moment + timedelta(hours=12))["longitude"]))
    return signed_longitude_delta(previous, next_position)


def _daily_longitude_change(body_name: str, moment: datetime) -> float:
    return _cached_daily_longitude_change(body_name, astronomy_time_string(moment))


def station_diagnostic(body_name: str, moment: datetime, window_days: int = STATION_SCAN_DAYS) -> dict[str, object]:
    if body_name not in STATION_DIAGNOSTIC_BODIES:
        return {"available": False, "reason": "Luminaries do not station in this diagnostic."}

    samples: list[tuple[int, float]] = [
        (offset, _daily_longitude_change(body_name, moment + timedelta(days=offset)))
        for offset in range(-window_days, window_days + 1)
    ]
    closest_offset, closest_speed = min(samples, key=lambda item: abs(item[1]))
    current_speed = next(speed for offset, speed in samples if offset == 0)
    crossing_offsets = []
    for (first_offset, first_speed), (second_offset, second_speed) in zip(samples, samples[1:]):
        if first_speed == 0 or second_speed == 0 or (first_speed < 0 < second_speed) or (first_speed > 0 > second_speed):
            crossing_offsets.append((first_offset + second_offset) / 2)

    nearest_crossing = min(crossing_offsets, key=abs) if crossing_offsets else None
    if nearest_crossing is None and abs(closest_speed) <= 0.08:
        nearest_crossing = float(closest_offset)
    if nearest_crossing is None:
        phase = "normal"
    elif nearest_crossing < -0.5:
        phase = "leaving station"
    elif nearest_crossing > 0.5:
        phase = "approaching station"
    else:
        phase = "station window"

    return {
        "available": True,
        "windowDays": window_days,
        "phase": phase,
        "daysFromStation": nearest_crossing,
        "closestSampleOffsetDays": closest_offset,
        "closestSampleSpeed": closest_speed,
        "currentSpeed": current_speed,
        "isInStationWindow": phase != "normal",
    }


def get_body_motion(body_name: str, moment: datetime, include_station_diagnostic: bool = True) -> dict[str, object]:
    current = get_ecliptic_coordinates(body_name, moment)
    swiss_speed = current.get("dailyLongitudeChange")
    if swiss_speed is not None:
        daily_change = float(swiss_speed)
    else:
        daily_change = _daily_longitude_change(body_name, moment)
    is_retrograde = daily_change < -0.02
    is_stationary = abs(daily_change) <= 0.02

    if is_stationary:
        direction = "stationary"
        label = "Stationary"
    elif is_retrograde:
        direction = "retrograde"
        label = "Retrograde"
    else:
        direction = "direct"
        label = "Direct"

    motion = {
        "direction": direction,
        "label": label,
        "dailyLongitudeChange": daily_change,
        "isRetrograde": is_retrograde,
        "isStationary": is_stationary,
    }
    if include_station_diagnostic:
        motion["station"] = station_diagnostic(body_name, moment)
    return motion


def lunar_phase_from_positions(positions: list[dict[str, object]]) -> dict[str, object]:
    by_name = {str(planet["name"]): planet for planet in positions}
    sun = by_name["Sun"]
    moon = by_name["Moon"]
    phase_angle = normalize_degrees(float(moon["longitude"]) - float(sun["longitude"]))
    age_days = phase_angle / 360 * 29.530588
    illumination = (1 - cos(radians(phase_angle))) / 2

    if phase_angle < 22.5 or phase_angle >= 337.5:
        name = "New Moon"
    elif phase_angle < 67.5:
        name = "Waxing Crescent"
    elif phase_angle < 112.5:
        name = "First Quarter"
    elif phase_angle < 157.5:
        name = "Waxing Gibbous"
    elif phase_angle < 202.5:
        name = "Full Moon"
    elif phase_angle < 247.5:
        name = "Waning Gibbous"
    elif phase_angle < 292.5:
        name = "Last Quarter"
    else:
        name = "Waning Crescent"

    return {
        "name": name,
        "phaseAngle": phase_angle,
        "ageDays": age_days,
        "illumination": illumination,
        "isWaxing": 0 < phase_angle < 180,
    }


def get_planet_positions(
    moment: datetime,
    zodiac_system_id: str = "tropical",
    include_station_diagnostics: bool = True,
) -> list[dict[str, object]]:
    positions = []
    for planet in PLANET_MODELS:
        coordinates = get_ecliptic_coordinates(str(planet["astronomy_body"]), moment)
        motion = get_body_motion(str(planet["astronomy_body"]), moment, include_station_diagnostics)
        tropical_longitude = normalize_degrees(float(coordinates["longitude"]))
        longitude = apply_zodiac_system(tropical_longitude, moment, zodiac_system_id)
        positions.append(
            {
                "id": planet["id"],
                "name": planet["name"],
                "astronomyBody": planet["astronomy_body"],
                "latitude": coordinates["latitude"],
                "declination": coordinates["declination"],
                "rightAscensionHours": coordinates["rightAscensionHours"],
                "longitude": longitude,
                "tropicalLongitude": tropical_longitude,
                "distanceAu": coordinates["distanceAu"],
                "zodiac": get_zodiac_position_for_system(longitude, moment, zodiac_system_id, tropical_longitude=tropical_longitude),
                "motion": motion,
                "isRetrograde": motion["isRetrograde"],
            }
        )
    return positions
