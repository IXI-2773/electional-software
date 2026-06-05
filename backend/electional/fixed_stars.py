"""Curated fixed-star support based on Astrolog/Swiss Ephemeris star data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from math import hypot
from typing import Iterable, Mapping

import astronomy

from .aspects import angular_distance, format_orb
from .ephemeris import get_zodiac_position_for_system, normalize_degrees
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


def _float_or_none(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fixed_star_orb_limit(star: Mapping[str, object], base_orb_limit: float = FIXED_STAR_CONTACT_ORB) -> float:
    """Return a magnitude-aware conjunction orb for a fixed-star diagnostic."""
    magnitude = _float_or_none(star.get("magnitude"))
    if magnitude is None:
        return base_orb_limit
    if magnitude > 50:
        return min(base_orb_limit, 0.35)
    if magnitude <= 0:
        return base_orb_limit * 1.25
    if magnitude <= 1:
        return base_orb_limit * 1.15
    if magnitude <= 2:
        return base_orb_limit
    if magnitude <= 3:
        return base_orb_limit * 0.75
    return base_orb_limit * 0.5


def fixed_star_contact_strength(
    longitude_distance: float,
    orb_limit: float,
    latitude_distance: float | None = None,
) -> tuple[float, float, str]:
    longitude_strength = max(0.45, 1.0 - (longitude_distance / max(orb_limit, 0.01)) * 0.45)
    latitude_strength = 1.0
    confidence = "longitude-only"
    if latitude_distance is not None:
        confidence = "longitude+latitude"
        if latitude_distance <= 0.5:
            latitude_strength = 1.0
        elif latitude_distance <= 1.5:
            latitude_strength = 0.85
        elif latitude_distance <= 3.0:
            latitude_strength = 0.65
        elif latitude_distance <= 5.0:
            latitude_strength = 0.4
        else:
            latitude_strength = 0.2
    return round(longitude_strength * latitude_strength, 3), round(latitude_strength, 3), confidence


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
                "zodiac": get_zodiac_position_for_system(longitude, moment, zodiac_system_id, tropical_longitude=tropical_longitude),
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
            longitude_distance = angular_distance(float(body["longitude"]), float(star["longitude"]))
            contact_orb_limit = fixed_star_orb_limit(star, orb_limit)
            if longitude_distance <= contact_orb_limit:
                star_id = str(star["id"])
                body_latitude = _float_or_none(body.get("latitude"))
                star_latitude = _float_or_none(star.get("latitude"))
                latitude_distance = (
                    abs(body_latitude - star_latitude)
                    if body_latitude is not None and star_latitude is not None
                    else None
                )
                ecliptic_distance = (
                    hypot(longitude_distance, latitude_distance)
                    if latitude_distance is not None
                    else longitude_distance
                )
                contact_strength, latitude_strength, precision = fixed_star_contact_strength(
                    longitude_distance,
                    contact_orb_limit,
                    latitude_distance,
                )
                base_score = FIXED_STAR_SCORING.get(star_id, 0.0)
                score = round(base_score * contact_strength, 2)
                contacts.append(
                    {
                        "body": body_name,
                        "star": star["name"],
                        "starId": star_id,
                        "orb": longitude_distance,
                        "orbText": format_orb(longitude_distance),
                        "orbLimit": contact_orb_limit,
                        "orbLimitText": format_orb(contact_orb_limit),
                        "longitudeDistance": longitude_distance,
                        "longitudeDistanceText": format_orb(longitude_distance),
                        "latitudeDistance": latitude_distance,
                        "latitudeDistanceText": format_orb(latitude_distance) if latitude_distance is not None else None,
                        "eclipticDistance": ecliptic_distance,
                        "eclipticDistanceText": format_orb(ecliptic_distance),
                        "contactStrength": contact_strength,
                        "latitudeStrength": latitude_strength,
                        "precision": precision,
                        "baseScore": base_score,
                        "score": score,
                        "tone": "support" if score > 0 else "stress" if score < 0 else "mixed",
                        "note": star["electionalNote"],
                        "label": f"{body_name} conjunct {star['name']}",
                        "magnitude": star.get("magnitude"),
                    }
                )

    return sorted(contacts, key=lambda contact: (float(contact["orb"]), str(contact["label"])))


def fixed_star_score(contacts: Iterable[Mapping[str, object]]) -> float:
    score = 0.0
    for contact in contacts:
        score += float(contact.get("score", 0.0))
    return score
