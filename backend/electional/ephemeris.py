"""Python ephemeris backed by Astronomy Engine."""

from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache
from math import cos, floor, radians

import astronomy

from .systems import apply_zodiac_system
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

ENGINE_NAME = "Astronomy Engine Python"


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
        "degree": degree,
        "minute": minute,
    }


def format_zodiac_position(zodiac: dict[str, object]) -> str:
    return f"{zodiac['degree']} {zodiac['sign']} {int(zodiac['minute']):02d}"


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


def get_ecliptic_coordinates(body_name: str, moment: datetime) -> dict[str, float | None]:
    latitude, longitude, distance = _cached_ecliptic_coordinates(body_name, astronomy_time_string(moment))
    return {
        "latitude": latitude,
        "longitude": longitude,
        "distanceAu": distance,
    }


def get_body_motion(body_name: str, moment: datetime) -> dict[str, object]:
    previous = normalize_degrees(float(get_ecliptic_coordinates(body_name, moment - timedelta(hours=12))["longitude"]))
    next_position = normalize_degrees(float(get_ecliptic_coordinates(body_name, moment + timedelta(hours=12))["longitude"]))
    daily_change = signed_longitude_delta(previous, next_position)
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

    return {
        "direction": direction,
        "label": label,
        "dailyLongitudeChange": daily_change,
        "isRetrograde": is_retrograde,
        "isStationary": is_stationary,
    }


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


def get_planet_positions(moment: datetime, zodiac_system_id: str = "tropical") -> list[dict[str, object]]:
    positions = []
    for planet in PLANET_MODELS:
        coordinates = get_ecliptic_coordinates(str(planet["astronomy_body"]), moment)
        motion = get_body_motion(str(planet["astronomy_body"]), moment)
        tropical_longitude = normalize_degrees(float(coordinates["longitude"]))
        longitude = apply_zodiac_system(tropical_longitude, moment, zodiac_system_id)
        positions.append(
            {
                "id": planet["id"],
                "name": planet["name"],
                "astronomyBody": planet["astronomy_body"],
                "latitude": coordinates["latitude"],
                "longitude": longitude,
                "tropicalLongitude": tropical_longitude,
                "distanceAu": coordinates["distanceAu"],
                "zodiac": get_zodiac_position(longitude),
                "motion": motion,
                "isRetrograde": motion["isRetrograde"],
            }
        )
    return positions
