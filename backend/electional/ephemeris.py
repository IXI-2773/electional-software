"""Python ephemeris backed by Astronomy Engine."""

from __future__ import annotations

from datetime import datetime
from math import floor

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


def get_ecliptic_coordinates(body_name: str, moment: datetime) -> dict[str, float | None]:
    time = astronomy.Time(astronomy_time_string(moment))

    if body_name == "Sun":
        ecliptic = astronomy.SunPosition(time)
    else:
        body = getattr(astronomy.Body, body_name)
        vector = astronomy.GeoVector(body, time, True)
        ecliptic = astronomy.Ecliptic(vector)

    vector = getattr(ecliptic, "vec", None)
    distance = vector.Length() if vector is not None and hasattr(vector, "Length") else None

    return {
        "latitude": ecliptic.elat,
        "longitude": ecliptic.elon,
        "distanceAu": distance,
    }


def get_planet_positions(moment: datetime, zodiac_system_id: str = "tropical") -> list[dict[str, object]]:
    positions = []
    for planet in PLANET_MODELS:
        coordinates = get_ecliptic_coordinates(str(planet["astronomy_body"]), moment)
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
            }
        )
    return positions
