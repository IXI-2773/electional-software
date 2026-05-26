"""House angle and Whole Sign placement calculations."""

from __future__ import annotations

from datetime import datetime
from math import atan2, cos, floor, radians, sin, tan

import astronomy

from .ephemeris import get_zodiac_position, normalize_degrees
from .time_utils import astronomy_time_string

ANGLE_DEFINITIONS = (
    {"id": "asc", "name": "Ascendant", "shortName": "ASC"},
    {"id": "mc", "name": "Midheaven", "shortName": "MC"},
    {"id": "dsc", "name": "Descendant", "shortName": "DSC"},
    {"id": "ic", "name": "Imum Coeli", "shortName": "IC"},
)

ANGULAR_ORB = 8


def radians_to_degrees(value: float) -> float:
    return value * 180 / 3.141592653589793


def julian_day(moment: datetime) -> float:
    time = astronomy.Time(astronomy_time_string(moment))
    return time.ut + 2451545.0


def true_obliquity(moment: datetime) -> float:
    jd = julian_day(moment)
    t = (jd - 2451545.0) / 36525
    seconds = 21.448 - t * (46.8150 + t * (0.00059 - t * 0.001813))
    mean = 23 + (26 + seconds / 60) / 60
    omega = radians(normalize_degrees(125.04452 - 1934.136261 * t + 0.0020708 * t * t + t**3 / 450000))
    sun_longitude = radians(normalize_degrees(280.4665 + 36000.7698 * t))
    moon_longitude = radians(normalize_degrees(218.3165 + 481267.8813 * t))
    nutation = (
        9.20 * cos(omega)
        + 0.57 * cos(2 * sun_longitude)
        + 0.10 * cos(2 * moon_longitude)
        - 0.09 * cos(2 * omega)
    )
    return mean + nutation / 3600


def angle_distance(first_longitude: float, second_longitude: float) -> float:
    distance = normalize_degrees(first_longitude - second_longitude)
    return 360 - distance if distance > 180 else distance


def local_sidereal_degrees(moment: datetime, longitude: float) -> float:
    time = astronomy.Time(astronomy_time_string(moment))
    return normalize_degrees(astronomy.SiderealTime(time) * 15 + longitude)


def calculate_midheaven(local_sidereal: float, obliquity: float) -> float:
    theta = radians(local_sidereal)
    epsilon = radians(obliquity)
    return normalize_degrees(radians_to_degrees(atan2(sin(theta) / cos(epsilon), cos(theta))))


def calculate_ascendant(local_sidereal: float, latitude: float, obliquity: float) -> float:
    theta = radians(local_sidereal)
    lat = radians(latitude)
    epsilon = radians(obliquity)
    numerator = -cos(theta)
    denominator = sin(theta) * cos(epsilon) + tan(lat) * sin(epsilon)
    return normalize_degrees(radians_to_degrees(atan2(numerator, denominator)) + 180)


def whole_sign_house(longitude: float, ascendant_longitude: float) -> int:
    ascendant_sign = floor(normalize_degrees(ascendant_longitude) / 30)
    body_sign = floor(normalize_degrees(longitude) / 30)
    return ((body_sign - ascendant_sign + 12) % 12) + 1


def calculate_angles(moment: datetime, latitude: float, longitude: float) -> list[dict[str, object]]:
    local_sidereal = local_sidereal_degrees(moment, longitude)
    obliquity = true_obliquity(moment)
    ascendant = calculate_ascendant(local_sidereal, latitude, obliquity)
    midheaven = calculate_midheaven(local_sidereal, obliquity)

    longitudes = (
        ascendant,
        midheaven,
        normalize_degrees(ascendant + 180),
        normalize_degrees(midheaven + 180),
    )

    return [
        {
            **definition,
            "longitude": angle_longitude,
            "zodiac": get_zodiac_position(angle_longitude),
        }
        for definition, angle_longitude in zip(ANGLE_DEFINITIONS, longitudes)
    ]


def closest_angle(planet: dict[str, object], angles: list[dict[str, object]]) -> dict[str, object]:
    return sorted(
        (
            {
                **angle,
                "distance": angle_distance(float(planet["longitude"]), float(angle["longitude"])),
            }
            for angle in angles
        ),
        key=lambda angle: float(angle["distance"]),
    )[0]


def enrich_positions_with_houses(positions: list[dict[str, object]], angles: list[dict[str, object]]) -> list[dict[str, object]]:
    ascendant = next(angle for angle in angles if angle["id"] == "asc")
    enriched = []
    for planet in positions:
        nearest = closest_angle(planet, angles)
        enriched.append(
            {
                **planet,
                "house": whole_sign_house(float(planet["longitude"]), float(ascendant["longitude"])),
                "closestAngle": {
                    "id": nearest["id"],
                    "name": nearest["name"],
                    "shortName": nearest["shortName"],
                    "distance": nearest["distance"],
                },
                "isAngular": float(nearest["distance"]) <= ANGULAR_ORB,
            }
        )
    return enriched
