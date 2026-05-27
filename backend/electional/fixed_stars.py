"""Curated fixed-star support based on Astrolog/Swiss Ephemeris star data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Iterable, Mapping

import astronomy

from .aspects import angular_distance, format_orb
from .ephemeris import get_zodiac_position, normalize_degrees
from .systems import apply_zodiac_system
from .time_utils import astronomy_time_string


@dataclass(frozen=True)
class FixedStar:
    id: str
    name: str
    nomenclature: str
    ra_degrees: float
    dec_degrees: float
    magnitude: float
    nature: str
    electional_note: str


FIXED_STAR_MODELS: tuple[FixedStar, ...] = (
    FixedStar(
        "aldebaran",
        "Aldebaran",
        "alpha Tauri",
        68.98016279166667,
        16.50930236111111,
        0.86,
        "royal-star",
        "Visibility, courage, and decisive starts; watch impulsive Mars-style overreach.",
    ),
    FixedStar(
        "algol",
        "Algol",
        "beta Persei",
        47.04221854166667,
        40.95564666666667,
        2.12,
        "caution",
        "High intensity marker; avoid when calm reputation, safety, or public trust is central.",
    ),
    FixedStar(
        "regulus",
        "Regulus",
        "alpha Leonis",
        152.09296245833333,
        11.967208777777778,
        1.40,
        "royal-star",
        "Prominence, recognition, and leadership; strongest when paired with restraint.",
    ),
    FixedStar(
        "sirius",
        "Sirius",
        "alpha Canis Majoris",
        101.28715533333333,
        -16.71611586111111,
        -1.46,
        "bright-star",
        "Amplifies visibility, heat, and consequence; useful for public launches with containment.",
    ),
    FixedStar(
        "spica",
        "Spica",
        "alpha Virginis",
        201.298247375,
        -11.161319472222222,
        0.97,
        "benefic",
        "Protection, skill, craft, and fruitful outcomes; one of the cleanest electional contacts.",
    ),
    FixedStar(
        "antares",
        "Antares",
        "alpha Scorpii",
        247.35191541666666,
        -26.43200261111111,
        0.91,
        "royal-star",
        "Power, heat, and contest; can empower bold action but increases conflict potential.",
    ),
    FixedStar(
        "galactic-center",
        "Galactic Center",
        "Sgr A*",
        266.416816625,
        -29.007824972222223,
        999.99,
        "deep-focus",
        "Collective signal, orientation, and long-range meaning; not scored like a normal bright star.",
    ),
)

FIXED_STAR_BY_ID = {star.id: star for star in FIXED_STAR_MODELS}
FIXED_STAR_CONTACT_ORB = 1.0
FIXED_STAR_SCORING = {
    "spica": 4.0,
    "regulus": 2.5,
    "aldebaran": 2.0,
    "sirius": 1.5,
    "antares": -1.5,
    "algol": -5.0,
}


@lru_cache(maxsize=2048)
def _cached_star_ecliptic(star_id: str, time_text: str) -> tuple[float, float]:
    star = FIXED_STAR_BY_ID[star_id]
    time = astronomy.Time(time_text)
    equatorial = astronomy.VectorFromSphere(astronomy.Spherical(star.dec_degrees, star.ra_degrees, 1.0), time)
    ecliptic = astronomy.Ecliptic(equatorial)
    return ecliptic.elat, normalize_degrees(ecliptic.elon)


def fixed_star_positions(moment: datetime, zodiac_system_id: str = "tropical") -> list[dict[str, object]]:
    positions = []
    time_text = astronomy_time_string(moment)
    for star in FIXED_STAR_MODELS:
        latitude, tropical_longitude = _cached_star_ecliptic(star.id, time_text)
        longitude = apply_zodiac_system(tropical_longitude, moment, zodiac_system_id)
        positions.append(
            {
                "id": star.id,
                "name": star.name,
                "nomenclature": star.nomenclature,
                "latitude": latitude,
                "longitude": longitude,
                "tropicalLongitude": tropical_longitude,
                "zodiac": get_zodiac_position(longitude),
                "magnitude": star.magnitude,
                "nature": star.nature,
                "electionalNote": star.electional_note,
            }
        )
    return positions


def detect_fixed_star_contacts(
    positions: Iterable[Mapping[str, object]],
    stars: Iterable[Mapping[str, object]],
    orb_limit: float = FIXED_STAR_CONTACT_ORB,
) -> list[dict[str, object]]:
    contacts: list[dict[str, object]] = []
    for body in positions:
        body_name = str(body.get("name", ""))
        if not body_name:
            continue
        for star in stars:
            distance = angular_distance(float(body["longitude"]), float(star["longitude"]))
            if distance <= orb_limit:
                star_id = str(star["id"])
                score = FIXED_STAR_SCORING.get(star_id, 0.0)
                contacts.append(
                    {
                        "body": body_name,
                        "star": star["name"],
                        "starId": star_id,
                        "orb": distance,
                        "orbText": format_orb(distance),
                        "score": score,
                        "tone": "support" if score > 0 else "stress" if score < 0 else "mixed",
                        "note": star["electionalNote"],
                        "label": f"{body_name} conjunct {star['name']}",
                    }
                )

    return sorted(contacts, key=lambda contact: (float(contact["orb"]), str(contact["label"])))


def fixed_star_score(contacts: Iterable[Mapping[str, object]]) -> float:
    score = 0.0
    for contact in contacts:
        score += float(contact.get("score", 0.0))
    return score
