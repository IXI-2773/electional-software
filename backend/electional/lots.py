"""Arabic Lots / Parts used by the electional chart engine."""

from __future__ import annotations

from .ephemeris import get_zodiac_position, normalize_degrees
from .houses import closest_angle, house_number

LOT_TOPICS = {
    "fortune": "Body, resources, material fortune",
    "spirit": "Intention, agency, chosen direction",
    "eros": "Desire, attraction, binding interest",
    "necessity": "Constraint, duty, pressure, unavoidable conditions",
    "courage": "Action, conflict, boldness, capacity to push",
    "victory": "Success, advantage, overcoming obstacles",
    "nemesis": "Limits, consequence, accountability, reversal",
}

LOT_NAMES = {
    "fortune": "Part of Fortune",
    "spirit": "Part of Spirit",
    "eros": "Part of Eros",
    "necessity": "Part of Necessity",
    "courage": "Part of Courage",
    "victory": "Part of Victory",
    "nemesis": "Part of Nemesis",
}


def is_day_chart(positions: list[dict[str, object]]) -> bool:
    sun = next(planet for planet in positions if planet["name"] == "Sun")
    return int(sun.get("house", 1)) in {7, 8, 9, 10, 11, 12}


def lot_longitude(ascendant: float, first: float, second: float) -> float:
    return normalize_degrees(ascendant + first - second)


def planet_longitude(positions: list[dict[str, object]], name: str) -> float:
    return float(next(planet for planet in positions if planet["name"] == name)["longitude"])


def calculate_lots(
    positions: list[dict[str, object]],
    angles: list[dict[str, object]],
    house_cusps: list[dict[str, object]],
    house_system_id: str,
) -> list[dict[str, object]]:
    ascendant = next(angle for angle in angles if angle["id"] == "asc")
    asc_longitude = float(ascendant["longitude"])
    sun = planet_longitude(positions, "Sun")
    moon = planet_longitude(positions, "Moon")
    mercury = planet_longitude(positions, "Mercury")
    venus = planet_longitude(positions, "Venus")
    mars = planet_longitude(positions, "Mars")
    jupiter = planet_longitude(positions, "Jupiter")
    saturn = planet_longitude(positions, "Saturn")
    day_chart = is_day_chart(positions)

    fortune = lot_longitude(asc_longitude, moon if day_chart else sun, sun if day_chart else moon)
    spirit = lot_longitude(asc_longitude, sun if day_chart else moon, moon if day_chart else sun)

    formulas = [
        ("fortune", LOT_NAMES["fortune"], "Fortune", fortune, "ASC + Moon - Sun" if day_chart else "ASC + Sun - Moon", LOT_TOPICS["fortune"]),
        ("spirit", LOT_NAMES["spirit"], "Spirit", spirit, "ASC + Sun - Moon" if day_chart else "ASC + Moon - Sun", LOT_TOPICS["spirit"]),
        (
            "eros",
            LOT_NAMES["eros"],
            "Eros",
            lot_longitude(asc_longitude, venus if day_chart else spirit, spirit if day_chart else venus),
            "ASC + Venus - Spirit" if day_chart else "ASC + Spirit - Venus",
            LOT_TOPICS["eros"],
        ),
        (
            "necessity",
            LOT_NAMES["necessity"],
            "Necessity",
            lot_longitude(asc_longitude, fortune if day_chart else mercury, mercury if day_chart else fortune),
            "ASC + Fortune - Mercury" if day_chart else "ASC + Mercury - Fortune",
            LOT_TOPICS["necessity"],
        ),
        (
            "courage",
            LOT_NAMES["courage"],
            "Courage",
            lot_longitude(asc_longitude, fortune if day_chart else mars, mars if day_chart else fortune),
            "ASC + Fortune - Mars" if day_chart else "ASC + Mars - Fortune",
            LOT_TOPICS["courage"],
        ),
        (
            "victory",
            LOT_NAMES["victory"],
            "Victory",
            lot_longitude(asc_longitude, jupiter if day_chart else spirit, spirit if day_chart else jupiter),
            "ASC + Jupiter - Spirit" if day_chart else "ASC + Spirit - Jupiter",
            LOT_TOPICS["victory"],
        ),
        (
            "nemesis",
            LOT_NAMES["nemesis"],
            "Nemesis",
            lot_longitude(asc_longitude, fortune if day_chart else saturn, saturn if day_chart else fortune),
            "ASC + Fortune - Saturn" if day_chart else "ASC + Saturn - Fortune",
            LOT_TOPICS["nemesis"],
        ),
    ]

    lots = []
    for lot_id, name, short_name, longitude, formula, topic in formulas:
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
                "formula": formula,
                "sect": "day" if day_chart else "night",
                "topic": topic,
            }
        )
    return lots
