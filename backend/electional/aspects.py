"""Aspect definitions and detection logic."""

from __future__ import annotations

from dataclasses import dataclass
from math import floor
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True)
class Aspect:
    id: str
    name: str
    angle: float
    default_orb: float
    tone: str
    meaning: str


ASPECTS: tuple[Aspect, ...] = (
    Aspect(
        id="conjunction",
        name="Conjunction",
        angle=0,
        default_orb=8,
        tone="mixed",
        meaning="Merges planetary significations and intensifies the elected moment.",
    ),
    Aspect(
        id="trine",
        name="Trine",
        angle=120,
        default_orb=7,
        tone="support",
        meaning="Shows ease, flow, and cooperation between the planets involved.",
    ),
    Aspect(
        id="square",
        name="Square",
        angle=90,
        default_orb=6,
        tone="stress",
        meaning="Signals friction, urgency, and pressure that may require management.",
    ),
    Aspect(
        id="opposition",
        name="Opposition",
        angle=180,
        default_orb=7,
        tone="stress",
        meaning="Highlights polarization, exposure, and competing priorities.",
    ),
    Aspect(
        id="sextile",
        name="Sextile",
        angle=60,
        default_orb=5,
        tone="support",
        meaning="Offers opportunity through intentional action and coordination.",
    ),
)

ASPECT_BY_ID = {aspect.id: aspect for aspect in ASPECTS}


def angular_distance(first_longitude: float, second_longitude: float) -> float:
    raw_distance = abs(first_longitude - second_longitude) % 360
    return 360 - raw_distance if raw_distance > 180 else raw_distance


def format_orb(orb: float) -> str:
    degrees = floor(orb)
    minutes = round((orb - degrees) * 60)
    return f"{degrees} deg {minutes:02d} min"


def detect_aspects(
    positions: Sequence[Mapping[str, object]],
    selected_aspect_ids: Iterable[str],
    aspect_orbs: Mapping[str, float] | None = None,
) -> list[dict[str, object]]:
    selected = [ASPECT_BY_ID[aspect_id] for aspect_id in selected_aspect_ids if aspect_id in ASPECT_BY_ID]
    orb_overrides = aspect_orbs or {}
    detected: list[dict[str, object]] = []

    for first_index, first in enumerate(positions):
        for second in positions[first_index + 1 :]:
            distance = angular_distance(float(first["longitude"]), float(second["longitude"]))

            for aspect in selected:
                orb = abs(distance - aspect.angle)
                orb_limit = float(orb_overrides.get(aspect.id, aspect.default_orb))

                if orb <= orb_limit:
                    first_name = str(first["name"])
                    second_name = str(second["name"])
                    detected.append(
                        {
                            "aspectId": aspect.id,
                            "aspectName": aspect.name,
                            "exactAngle": aspect.angle,
                            "tone": aspect.tone,
                            "orb": orb,
                            "orbLimit": orb_limit,
                            "orbText": format_orb(orb),
                            "bodies": [first_name, second_name],
                            "label": f"{first_name} {aspect.name.lower()} {second_name}",
                        }
                    )

    return sorted(detected, key=lambda aspect: float(aspect["orb"]))
