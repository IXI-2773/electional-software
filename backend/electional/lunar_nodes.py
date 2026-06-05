"""Lunar node chart points.

The node formulas here are intentionally lightweight: they give the desktop app
usable mean/true node context while the professional Swiss bridge remains
optional on this machine.
"""

from __future__ import annotations

from datetime import datetime
from math import radians, sin

from .ephemeris import get_zodiac_position_for_system, normalize_degrees
from .houses import closest_angle, house_number, julian_day
from .systems import apply_zodiac_system


def julian_centuries(moment: datetime) -> float:
    return (julian_day(moment) - 2451545.0) / 36525


def mean_node_tropical_longitude(moment: datetime) -> float:
    t = julian_centuries(moment)
    return normalize_degrees(125.04455501 - 1934.1361849 * t + 0.0020762 * t * t + t**3 / 467410 - t**4 / 60616000)


def true_node_tropical_longitude(moment: datetime) -> float:
    """Approximate true node from the mean node plus common lunar corrections."""

    t = julian_centuries(moment)
    mean_node = mean_node_tropical_longitude(moment)
    moon_mean_anomaly = normalize_degrees(134.96340251 + 477198.8675605 * t + 0.0088553 * t * t)
    sun_mean_anomaly = normalize_degrees(357.52910918 + 35999.0502911 * t - 0.0001537 * t * t)
    moon_argument_latitude = normalize_degrees(93.27209062 + 483202.0174577 * t - 0.0035420 * t * t)
    moon_elongation = normalize_degrees(297.85019547 + 445267.1114469 * t - 0.0017696 * t * t)

    correction = (
        -1.4979 * sin(radians(2 * moon_elongation))
        - 0.1500 * sin(radians(sun_mean_anomaly))
        - 0.1226 * sin(radians(2 * moon_argument_latitude))
        + 0.1176 * sin(radians(2 * moon_elongation - moon_mean_anomaly))
        - 0.0801 * sin(radians(2 * moon_elongation + moon_mean_anomaly))
    )
    return normalize_degrees(mean_node + correction)


def calculate_lunar_nodes(
    moment: datetime,
    zodiac_system_id: str,
    angles: list[dict[str, object]],
    house_cusps: list[dict[str, object]],
    house_system_id: str,
) -> list[dict[str, object]]:
    ascendant = next(angle for angle in angles if angle["id"] == "asc")
    true_tropical = true_node_tropical_longitude(moment)
    mean_tropical = mean_node_tropical_longitude(moment)
    node_specs = (
        ("true-north-node", "True North Node", "True Node", true_tropical, "Approximate true lunar node"),
        ("true-south-node", "True South Node", "South Node", normalize_degrees(true_tropical + 180), "Opposite true lunar node"),
        ("mean-north-node", "Mean North Node", "Mean Node", mean_tropical, "Mean lunar node"),
        ("mean-south-node", "Mean South Node", "Mean South", normalize_degrees(mean_tropical + 180), "Opposite mean lunar node"),
    )
    nodes = []
    for node_id, name, short_name, tropical_longitude, note in node_specs:
        longitude = apply_zodiac_system(tropical_longitude, moment, zodiac_system_id)
        nearest = closest_angle({"longitude": longitude}, angles)
        nodes.append(
            {
                "id": node_id,
                "name": name,
                "shortName": short_name,
                "longitude": longitude,
                "tropicalLongitude": tropical_longitude,
                "zodiac": get_zodiac_position_for_system(longitude, moment, zodiac_system_id, tropical_longitude=tropical_longitude),
                "house": house_number(longitude, float(ascendant["longitude"]), house_system_id, house_cusps),
                "closestAngle": {
                    "id": nearest["id"],
                    "name": nearest["name"],
                    "shortName": nearest["shortName"],
                    "distance": nearest["distance"],
                },
                "calculation": note,
            }
        )
    return nodes
