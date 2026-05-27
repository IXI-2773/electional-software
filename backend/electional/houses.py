"""House angle and Whole Sign placement calculations."""

from __future__ import annotations

from datetime import datetime
from math import atan, atan2, cos, floor, radians, sin, tan

import astronomy

from .ephemeris import get_zodiac_position, normalize_degrees
from .systems import apply_zodiac_system
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


def signed_angle_distance(first_longitude: float, second_longitude: float) -> float:
    return (normalize_degrees(first_longitude - second_longitude) + 180) % 360 - 180


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


def equal_house(longitude: float, ascendant_longitude: float) -> int:
    return floor(normalize_degrees(longitude - ascendant_longitude) / 30) + 1


def cusp_house(longitude: float, house_cusps: list[dict[str, object]]) -> int:
    ordered = sorted(((int(cusp["house"]), float(cusp["longitude"])) for cusp in house_cusps), key=lambda item: item[1])
    normalized = normalize_degrees(longitude)
    active_house = ordered[-1][0]
    for house, cusp_longitude in ordered:
        if normalized >= cusp_longitude:
            active_house = house
        else:
            break
    return active_house


def house_number(
    longitude: float,
    ascendant_longitude: float,
    house_system_id: str = "whole-sign",
    house_cusps: list[dict[str, object]] | None = None,
) -> int:
    if house_system_id in {"koch", "topocentric"} and house_cusps:
        return cusp_house(longitude, house_cusps)
    if house_system_id == "equal-house":
        return equal_house(longitude, ascendant_longitude)
    return whole_sign_house(longitude, ascendant_longitude)


def calculate_angles(
    moment: datetime,
    latitude: float,
    longitude: float,
    zodiac_system_id: str = "tropical",
) -> list[dict[str, object]]:
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
            "longitude": apply_zodiac_system(angle_longitude, moment, zodiac_system_id),
            "tropicalLongitude": angle_longitude,
            "zodiac": get_zodiac_position(apply_zodiac_system(angle_longitude, moment, zodiac_system_id)),
        }
        for definition, angle_longitude in zip(ANGLE_DEFINITIONS, longitudes)
    ]


def topocentric_pole(latitude: float, fraction: float) -> float:
    return radians_to_degrees(atan(tan(radians(latitude)) * fraction))


def topocentric_cusp_longitude(
    local_sidereal: float,
    obliquity: float,
    latitude: float,
    right_ascension_offset: float,
    pole_fraction: float,
) -> float:
    pole = topocentric_pole(latitude, pole_fraction)
    return calculate_ascendant(normalize_degrees(local_sidereal + right_ascension_offset), pole, obliquity)


def ascendant_roots_for_longitude(target_longitude: float, latitude: float, obliquity: float) -> list[float]:
    roots = []
    previous_sidereal = 0.0
    previous_delta = signed_angle_distance(calculate_ascendant(previous_sidereal, latitude, obliquity), target_longitude)

    for sidereal in range(1, 361):
        current_sidereal = float(sidereal)
        current_delta = signed_angle_distance(calculate_ascendant(current_sidereal % 360, latitude, obliquity), target_longitude)
        if abs(current_delta) < 0.000001:
            roots.append(current_sidereal % 360)
        elif previous_delta == 0 or (previous_delta < 0 < current_delta) or (previous_delta > 0 > current_delta):
            low = previous_sidereal
            high = current_sidereal
            low_delta = previous_delta
            for _ in range(32):
                midpoint = (low + high) / 2
                midpoint_delta = signed_angle_distance(calculate_ascendant(midpoint % 360, latitude, obliquity), target_longitude)
                if (low_delta < 0 < midpoint_delta) or (low_delta > 0 > midpoint_delta):
                    high = midpoint
                else:
                    low = midpoint
                    low_delta = midpoint_delta
            roots.append(((low + high) / 2) % 360)
        previous_sidereal = current_sidereal
        previous_delta = current_delta

    deduped = []
    for root in roots:
        if not any(angle_distance(root, existing) < 0.01 for existing in deduped):
            deduped.append(root)
    return deduped


def previous_sidereal_root(target_longitude: float, current_sidereal: float, latitude: float, obliquity: float) -> float:
    roots = ascendant_roots_for_longitude(target_longitude, latitude, obliquity)
    if not roots:
        return normalize_degrees(current_sidereal - 90)
    return min(roots, key=lambda root: (current_sidereal - root) % 360)


def next_sidereal_root(target_longitude: float, current_sidereal: float, latitude: float, obliquity: float) -> float:
    roots = ascendant_roots_for_longitude(target_longitude, latitude, obliquity)
    if not roots:
        return normalize_degrees(current_sidereal + 90)
    return min(roots, key=lambda root: (root - current_sidereal) % 360)


def koch_cusp_longitudes(local_sidereal: float, obliquity: float, latitude: float, ascendant: float, midheaven: float) -> dict[int, float]:
    ic = normalize_degrees(midheaven + 180)
    mc_rise_sidereal = previous_sidereal_root(midheaven, local_sidereal, latitude, obliquity)
    mc_arc = (local_sidereal - mc_rise_sidereal) % 360
    ic_rise_sidereal = next_sidereal_root(ic, local_sidereal, latitude, obliquity)
    ic_arc = (ic_rise_sidereal - local_sidereal) % 360

    tropical = {
        1: ascendant,
        10: midheaven,
        12: calculate_ascendant(normalize_degrees(mc_rise_sidereal + mc_arc / 3), latitude, obliquity),
        11: calculate_ascendant(normalize_degrees(mc_rise_sidereal + 2 * mc_arc / 3), latitude, obliquity),
        3: calculate_ascendant(normalize_degrees(local_sidereal + ic_arc / 3), latitude, obliquity),
        2: calculate_ascendant(normalize_degrees(local_sidereal + 2 * ic_arc / 3), latitude, obliquity),
    }
    tropical.update({4: ic, 5: normalize_degrees(tropical[11] + 180), 6: normalize_degrees(tropical[12] + 180)})
    tropical.update({7: normalize_degrees(ascendant + 180), 8: normalize_degrees(tropical[2] + 180), 9: normalize_degrees(tropical[3] + 180)})
    return tropical


def calculate_house_cusps(
    moment: datetime,
    latitude: float,
    longitude: float,
    zodiac_system_id: str = "tropical",
    house_system_id: str = "whole-sign",
    angles: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    angles = angles or calculate_angles(moment, latitude, longitude, zodiac_system_id)
    ascendant = next(angle for angle in angles if angle["id"] == "asc")
    midheaven = next(angle for angle in angles if angle["id"] == "mc")
    asc = float(ascendant["longitude"])
    mc = float(midheaven["longitude"])

    if house_system_id == "equal-house":
        longitudes = [normalize_degrees(asc + index * 30) for index in range(12)]
    elif house_system_id in {"koch", "topocentric"}:
        local_sidereal = local_sidereal_degrees(moment, longitude)
        obliquity = true_obliquity(moment)
        if house_system_id == "koch":
            tropical = koch_cusp_longitudes(
                local_sidereal,
                obliquity,
                latitude,
                float(ascendant["tropicalLongitude"]),
                float(midheaven["tropicalLongitude"]),
            )
        else:
            tropical = {
                10: float(midheaven["tropicalLongitude"]),
                11: topocentric_cusp_longitude(local_sidereal, obliquity, latitude, 30, 1 / 3),
                12: topocentric_cusp_longitude(local_sidereal, obliquity, latitude, 60, 2 / 3),
                1: float(ascendant["tropicalLongitude"]),
                2: topocentric_cusp_longitude(local_sidereal, obliquity, latitude, 120, 2 / 3),
                3: topocentric_cusp_longitude(local_sidereal, obliquity, latitude, 150, 1 / 3),
            }
            tropical.update({house + 6 if house <= 6 else house - 6: normalize_degrees(value + 180) for house, value in list(tropical.items())})
        return [
            {
                "house": house,
                "longitude": apply_zodiac_system(tropical[house], moment, zodiac_system_id),
                "tropicalLongitude": tropical[house],
                "zodiac": get_zodiac_position(apply_zodiac_system(tropical[house], moment, zodiac_system_id)),
            }
            for house in range(1, 13)
        ]
    else:
        ascendant_sign_start = floor(asc / 30) * 30
        longitudes = [normalize_degrees(ascendant_sign_start + index * 30) for index in range(12)]

    return [
        {
            "house": index + 1,
            "longitude": longitude_value,
            "tropicalLongitude": None,
            "zodiac": get_zodiac_position(longitude_value),
        }
        for index, longitude_value in enumerate(longitudes)
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


def enrich_positions_with_houses(
    positions: list[dict[str, object]],
    angles: list[dict[str, object]],
    house_system_id: str = "whole-sign",
    house_cusps: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    ascendant = next(angle for angle in angles if angle["id"] == "asc")
    enriched = []
    for planet in positions:
        nearest = closest_angle(planet, angles)
        enriched.append(
            {
                **planet,
                "house": house_number(float(planet["longitude"]), float(ascendant["longitude"]), house_system_id, house_cusps),
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
