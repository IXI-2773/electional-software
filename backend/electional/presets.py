"""Electional presets inspired by the Capricorn Prometheus reference library."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping, Sequence


CLASSICAL_PLANETS = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn")
ALL_MAJOR_PLANETS = (*CLASSICAL_PLANETS, "Uranus", "Neptune", "Pluto")


@dataclass(frozen=True)
class ScoringProfile:
    support_weight: float
    mixed_weight: float
    stress_penalty: float
    preferred_weight: float
    close_contact_orb: float
    close_contact_weight: float
    angular_multiplier: float
    dignity_weight: float


@dataclass(frozen=True)
class ElectionalPreset:
    id: str
    name: str
    short_name: str
    source: str
    description: str
    aspect_ids: tuple[str, ...]
    aspect_orbs: Mapping[str, float]
    point_names: tuple[str, ...]
    preferred_aspects: tuple[str, ...]
    scoring: ScoringProfile

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["shortName"] = payload.pop("short_name")
        payload["aspectIds"] = payload.pop("aspect_ids")
        payload["aspectOrbs"] = payload.pop("aspect_orbs")
        payload["pointNames"] = payload.pop("point_names")
        payload["preferredAspects"] = payload.pop("preferred_aspects")
        scoring = payload["scoring"]
        payload["scoring"] = {
            "supportWeight": scoring["support_weight"],
            "mixedWeight": scoring["mixed_weight"],
            "stressPenalty": scoring["stress_penalty"],
            "preferredWeight": scoring["preferred_weight"],
            "closeContactOrb": scoring["close_contact_orb"],
            "closeContactWeight": scoring["close_contact_weight"],
            "angularMultiplier": scoring["angular_multiplier"],
            "dignityWeight": scoring["dignity_weight"],
        }
        return payload


ELECTIONAL_PRESETS: tuple[ElectionalPreset, ...] = (
    ElectionalPreset(
        id="transit-1-degree",
        name="Transit 1 Degree",
        short_name="Transit 1 deg",
        source="Capricorn Prometheus: transits_1_deg",
        description="Strict transit search mode for exact election windows.",
        aspect_ids=("conjunction", "trine", "sextile", "square", "opposition"),
        aspect_orbs={"conjunction": 1, "trine": 1, "sextile": 1, "square": 1, "opposition": 1},
        point_names=ALL_MAJOR_PLANETS,
        preferred_aspects=("trine", "sextile", "conjunction"),
        scoring=ScoringProfile(
            support_weight=13,
            mixed_weight=4,
            stress_penalty=12,
            preferred_weight=7,
            close_contact_orb=0.35,
            close_contact_weight=9,
            angular_multiplier=1.1,
            dignity_weight=0,
        ),
    ),
    ElectionalPreset(
        id="traditional-lilly",
        name="Traditional Lilly",
        short_name="Lilly",
        source="Capricorn Prometheus: Traditional - Lilly",
        description="Classical seven-planet election mode with essential dignity scoring.",
        aspect_ids=("conjunction", "sextile", "square", "trine", "opposition"),
        aspect_orbs={"conjunction": 6, "sextile": 4, "square": 5, "trine": 5, "opposition": 6},
        point_names=CLASSICAL_PLANETS,
        preferred_aspects=("trine", "sextile"),
        scoring=ScoringProfile(
            support_weight=9,
            mixed_weight=3,
            stress_penalty=9,
            preferred_weight=6,
            close_contact_orb=1.5,
            close_contact_weight=5,
            angular_multiplier=1.35,
            dignity_weight=2,
        ),
    ),
    ElectionalPreset(
        id="medieval-electional",
        name="Medieval Electional",
        short_name="Medieval",
        source="Capricorn Prometheus: Medieval / Bonatti-Ptolemy references",
        description="Strict classical electional mode that rewards dignified benefics.",
        aspect_ids=("conjunction", "trine", "sextile", "square", "opposition"),
        aspect_orbs={"conjunction": 4, "trine": 4, "sextile": 3, "square": 3, "opposition": 4},
        point_names=CLASSICAL_PLANETS,
        preferred_aspects=("trine", "sextile"),
        scoring=ScoringProfile(
            support_weight=11,
            mixed_weight=2,
            stress_penalty=14,
            preferred_weight=7,
            close_contact_orb=1,
            close_contact_weight=6,
            angular_multiplier=1.5,
            dignity_weight=3,
        ),
    ),
)

PRESET_BY_ID = {preset.id: preset for preset in ELECTIONAL_PRESETS}

RULERS = {
    "Aries": "Mars",
    "Taurus": "Venus",
    "Gemini": "Mercury",
    "Cancer": "Moon",
    "Leo": "Sun",
    "Virgo": "Mercury",
    "Libra": "Venus",
    "Scorpio": "Mars",
    "Sagittarius": "Jupiter",
    "Capricorn": "Saturn",
    "Aquarius": "Saturn",
    "Pisces": "Jupiter",
}

EXALTATIONS = {
    "Aries": "Sun",
    "Taurus": "Moon",
    "Cancer": "Jupiter",
    "Virgo": "Mercury",
    "Libra": "Saturn",
    "Capricorn": "Mars",
    "Pisces": "Venus",
}

DETRIMENTS = {
    "Aries": "Venus",
    "Taurus": "Mars",
    "Gemini": "Jupiter",
    "Cancer": "Saturn",
    "Leo": "Saturn",
    "Virgo": "Jupiter",
    "Libra": "Mars",
    "Scorpio": "Venus",
    "Sagittarius": "Mercury",
    "Capricorn": "Moon",
    "Aquarius": "Sun",
    "Pisces": "Mercury",
}

FALLS = {
    "Aries": "Saturn",
    "Cancer": "Mars",
    "Virgo": "Venus",
    "Libra": "Sun",
    "Scorpio": "Moon",
    "Capricorn": "Jupiter",
    "Pisces": "Mercury",
}

EGYPTIAN_BOUNDS = {
    "Aries": ((6, "Jupiter"), (14, "Venus"), (21, "Mercury"), (26, "Mars"), (30, "Saturn")),
    "Taurus": ((8, "Venus"), (15, "Mercury"), (22, "Jupiter"), (27, "Saturn"), (30, "Mars")),
    "Gemini": ((7, "Mercury"), (14, "Jupiter"), (21, "Venus"), (25, "Mars"), (30, "Saturn")),
    "Cancer": ((6, "Mars"), (13, "Venus"), (19, "Mercury"), (26, "Jupiter"), (30, "Saturn")),
    "Leo": ((6, "Jupiter"), (11, "Venus"), (18, "Saturn"), (24, "Mercury"), (30, "Mars")),
    "Virgo": ((7, "Mercury"), (13, "Venus"), (17, "Jupiter"), (21, "Mars"), (30, "Saturn")),
    "Libra": ((6, "Saturn"), (14, "Mercury"), (21, "Jupiter"), (28, "Venus"), (30, "Mars")),
    "Scorpio": ((7, "Mars"), (11, "Venus"), (19, "Mercury"), (24, "Jupiter"), (30, "Saturn")),
    "Sagittarius": ((12, "Jupiter"), (17, "Venus"), (21, "Mercury"), (26, "Saturn"), (30, "Mars")),
    "Capricorn": ((7, "Mercury"), (14, "Jupiter"), (22, "Venus"), (26, "Saturn"), (30, "Mars")),
    "Aquarius": ((7, "Mercury"), (13, "Venus"), (20, "Jupiter"), (25, "Mars"), (30, "Saturn")),
    "Pisces": ((12, "Venus"), (16, "Jupiter"), (19, "Mercury"), (28, "Mars"), (30, "Saturn")),
}


def get_preset(preset_id: str | None) -> ElectionalPreset:
    if preset_id and preset_id in PRESET_BY_ID:
        return PRESET_BY_ID[preset_id]
    return ELECTIONAL_PRESETS[0]


def uses_point(preset: ElectionalPreset, planet_name: str) -> bool:
    return planet_name in preset.point_names


def filter_positions_for_preset(
    positions: Sequence[Mapping[str, object]],
    preset: ElectionalPreset,
) -> list[Mapping[str, object]]:
    return [position for position in positions if uses_point(preset, str(position["name"]))]


def get_bound_lord(planet: Mapping[str, object]) -> str | None:
    zodiac = planet.get("zodiac")
    if not isinstance(zodiac, Mapping):
        return None

    sign = str(zodiac.get("sign") or "")
    bounds = EGYPTIAN_BOUNDS.get(sign)
    if not bounds:
        return None

    try:
        degree = float(zodiac.get("degree", 0)) + float(zodiac.get("minute", 0)) / 60
    except (TypeError, ValueError):
        return None

    for end_degree, lord in bounds:
        if degree < end_degree:
            return lord
    return bounds[-1][1]


def get_essential_dignity(planet: Mapping[str, object]) -> dict[str, object]:
    sign = str(planet["zodiac"]["sign"]) if isinstance(planet.get("zodiac"), Mapping) else str(planet.get("sign"))
    name = str(planet["name"])
    bound_lord = get_bound_lord(planet)
    is_own_bound = bound_lord == name and name in CLASSICAL_PLANETS

    if RULERS.get(sign) == name:
        return {"label": "Domicile", "score": 5 + int(is_own_bound), "boundLord": bound_lord, "isOwnBound": is_own_bound}
    if EXALTATIONS.get(sign) == name:
        return {"label": "Exalted", "score": 4 + int(is_own_bound), "boundLord": bound_lord, "isOwnBound": is_own_bound}
    if DETRIMENTS.get(sign) == name:
        return {"label": "Detriment", "score": -5 + int(is_own_bound), "boundLord": bound_lord, "isOwnBound": is_own_bound}
    if FALLS.get(sign) == name:
        return {"label": "Fall", "score": -4 + int(is_own_bound), "boundLord": bound_lord, "isOwnBound": is_own_bound}
    if name not in CLASSICAL_PLANETS:
        return {"label": "Outer", "score": 0, "boundLord": bound_lord, "isOwnBound": False}
    if is_own_bound:
        return {"label": "Bound", "score": 1, "boundLord": bound_lord, "isOwnBound": True}
    return {"label": "Peregrine", "score": 0, "boundLord": bound_lord, "isOwnBound": False}


def apply_dignities(
    positions: Sequence[Mapping[str, object]],
    preset: ElectionalPreset,
) -> list[dict[str, object]]:
    dignified = []
    for position in positions:
        planet = dict(position)
        planet["isPresetPoint"] = uses_point(preset, str(planet["name"]))
        planet["dignity"] = get_essential_dignity(planet)
        dignified.append(planet)
    return dignified


def dignity_score(positions: Sequence[Mapping[str, object]], preset: ElectionalPreset) -> float:
    return sum(float(position["dignity"]["score"]) for position in filter_positions_for_preset(positions, preset))


def summarize_orb(preset: ElectionalPreset) -> str:
    values = sorted(set(preset.aspect_orbs.values()))
    if len(values) == 1:
        return f"{values[0]:g} deg"
    return f"{values[0]:g}-{values[-1]:g} deg"
