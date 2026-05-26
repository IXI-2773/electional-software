"""Arabic Lots / Parts used by the electional chart engine."""

from __future__ import annotations

from .ephemeris import get_zodiac_position, normalize_degrees
from .houses import closest_angle, house_number


def is_day_chart(positions: list[dict[str, object]]) -> bool:
    sun = next(planet for planet in positions if planet["name"] == "Sun")
    return int(sun.get("house", 1)) in {7, 8, 9, 10, 11, 12}


def lot_longitude(ascendant: float, first: float, second: float) -> float:
    return normalize_degrees(ascendant + first - second)


def calculate_lots(
    positions: list[dict[str, object]],
    angles: list[dict[str, object]],
    house_cusps: list[dict[str, object]],
    house_system_id: str,
) -> list[dict[str, object]]:
    ascendant = next(angle for angle in angles if angle["id"] == "asc")
    sun = next(planet for planet in positions if planet["name"] == "Sun")
    moon = next(planet for planet in positions if planet["name"] == "Moon")
    day_chart = is_day_chart(positions)

    formulas = (
        (
            "fortune",
            "Part of Fortune",
            "Fortune",
            moon["longitude"] if day_chart else sun["longitude"],
            sun["longitude"] if day_chart else moon["longitude"],
        ),
        (
            "spirit",
            "Part of Spirit",
            "Spirit",
            sun["longitude"] if day_chart else moon["longitude"],
            moon["longitude"] if day_chart else sun["longitude"],
        ),
    )

    lots = []
    for lot_id, name, short_name, first, second in formulas:
        longitude = lot_longitude(float(ascendant["longitude"]), float(first), float(second))
        nearest = closest_angle({"longitude": longitude}, angles)
        lots.append(
            {
                "id": lot_id,
                "name": name,
                "shortName": short_name,
                "longitude": longitude,
                "zodiac": get_zodiac_position(longitude),
                "house": house_number(longitude, float(ascendant["longitude"]), house_system_id, house_cusps),
                "closestAngle": {
                    "id": nearest["id"],
                    "name": nearest["name"],
                    "shortName": nearest["shortName"],
                    "distance": nearest["distance"],
                },
                "formula": "ASC + Moon - Sun" if (lot_id == "fortune" and day_chart) or (lot_id == "spirit" and not day_chart) else "ASC + Sun - Moon",
                "sect": "day" if day_chart else "night",
            }
        )
    return lots
