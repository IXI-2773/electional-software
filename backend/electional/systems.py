"""Chart system selection for zodiac and house calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ZodiacSystem:
    id: str
    name: str
    mode: str
    description: str
    astrolog_offset: float | None = None
    traditional_compatible: bool = True


@dataclass(frozen=True)
class HouseSystem:
    id: str
    name: str
    description: str


DEFAULT_ZODIAC_SYSTEM_ID = "sidereal-lahiri"
DEFAULT_HOUSE_SYSTEM_ID = "whole-sign"
ASTROLOG_LAHIRI_OFFSET_FROM_FAGAN = 0.883208

ZODIAC_SYSTEMS: tuple[ZodiacSystem, ...] = (
    ZodiacSystem(
        id="sidereal-lahiri",
        name="Sidereal Lahiri",
        mode="sidereal",
        description="Sidereal zodiac with Lahiri/Chitrapaksha ayanamsha.",
        astrolog_offset=ASTROLOG_LAHIRI_OFFSET_FROM_FAGAN,
    ),
    ZodiacSystem(
        id="sidereal-fagan-bradley",
        name="Sidereal Fagan-Bradley",
        mode="sidereal",
        description="Sidereal zodiac using the Fagan-Bradley ayanamsha.",
        astrolog_offset=0.0,
    ),
    ZodiacSystem(
        id="sidereal-krishnamurti",
        name="Sidereal Krishnamurti",
        mode="sidereal",
        description="Sidereal zodiac using the Krishnamurti ayanamsha.",
        astrolog_offset=0.98006,
    ),
    ZodiacSystem(
        id="sidereal-raman",
        name="Sidereal B.V. Raman",
        mode="sidereal",
        description="Sidereal zodiac using the B.V. Raman ayanamsha.",
        astrolog_offset=2.329509,
    ),
    ZodiacSystem(
        id="tropical",
        name="Tropical",
        mode="tropical",
        description="Standard seasonal zodiac with no ayanamsha offset.",
    ),
    ZodiacSystem(
        id="true-13-sign",
        name="True 13-Sign",
        mode="constellational",
        description="Unequal ecliptic constellation zodiac using the 13-sign IAU-style spans, including Ophiuchus.",
        traditional_compatible=False,
    ),
)

HOUSE_SYSTEMS: tuple[HouseSystem, ...] = (
    HouseSystem(
        id="placidus",
        name="Placidus",
        description="Standard quadrant house system; uses Swiss Ephemeris when available and Porphyry fallback otherwise.",
    ),
    HouseSystem(
        id="whole-sign",
        name="Whole Sign",
        description="Each sign from the ascendant sign becomes one house.",
    ),
    HouseSystem(
        id="equal-house",
        name="Equal House",
        description="Twelve 30 degree houses starting from the exact ascendant.",
    ),
    HouseSystem(
        id="porphyry",
        name="Porphyry",
        description="Quadrants between ASC/MC/DSC/IC are trisected; stable fallback for quadrant-style work.",
    ),
    HouseSystem(
        id="topocentric",
        name="Topocentric",
        description="Polich-Page quadrant houses using local latitude-derived pole divisions.",
    ),
    HouseSystem(
        id="koch",
        name="Koch",
        description="Birthplace house system using time trisections from MC and IC arcs.",
    ),
    HouseSystem(
        id="campanus",
        name="Campanus",
        description="Prime-vertical quadrant system; uses Swiss Ephemeris when available and Porphyry fallback otherwise.",
    ),
    HouseSystem(
        id="regiomontanus",
        name="Regiomontanus",
        description="Equatorial quadrant system; uses Swiss Ephemeris when available and Porphyry fallback otherwise.",
    ),
    HouseSystem(
        id="alcabitius",
        name="Alcabitius",
        description="Classical time-based quadrant system; uses Swiss Ephemeris when available and Porphyry fallback otherwise.",
    ),
    HouseSystem(
        id="sripati",
        name="Sripati",
        description="Vedic quadrant-style house division modeled through Porphyry-style quadrant trisection.",
    ),
)

ZODIAC_SYSTEM_BY_ID = {system.id: system for system in ZODIAC_SYSTEMS}
ZODIAC_SYSTEM_BY_NAME = {system.name: system for system in ZODIAC_SYSTEMS}
HOUSE_SYSTEM_BY_ID = {system.id: system for system in HOUSE_SYSTEMS}
HOUSE_SYSTEM_BY_NAME = {system.name: system for system in HOUSE_SYSTEMS}


def get_zodiac_system(system_id_or_name: str | None) -> ZodiacSystem:
    key = system_id_or_name or DEFAULT_ZODIAC_SYSTEM_ID
    return ZODIAC_SYSTEM_BY_ID.get(key) or ZODIAC_SYSTEM_BY_NAME.get(key) or ZODIAC_SYSTEM_BY_ID[DEFAULT_ZODIAC_SYSTEM_ID]


def get_house_system(system_id_or_name: str | None) -> HouseSystem:
    key = system_id_or_name or DEFAULT_HOUSE_SYSTEM_ID
    return HOUSE_SYSTEM_BY_ID.get(key) or HOUSE_SYSTEM_BY_NAME.get(key) or HOUSE_SYSTEM_BY_ID[DEFAULT_HOUSE_SYSTEM_ID]


def decimal_year(moment: datetime) -> float:
    start = datetime(moment.year, 1, 1, tzinfo=moment.tzinfo)
    end = datetime(moment.year + 1, 1, 1, tzinfo=moment.tzinfo)
    return moment.year + (moment - start).total_seconds() / (end - start).total_seconds()


def lahiri_ayanamsha(moment: datetime) -> float:
    """Approximate Lahiri ayanamsha used when Swiss tables are unavailable.

    This uses a J2000 anchor and mean precession rate so the app remains
    runnable in environments without Swiss Ephemeris Python bindings.
    """

    return 23.853055 + (decimal_year(moment) - 2000.0) * (50.290966 / 3600)


def ayanamsha_for_system(moment: datetime, system_id_or_name: str | None) -> float:
    system = get_zodiac_system(system_id_or_name)
    if system.mode == "sidereal":
        from .professional import swiss_ayanamsha

        professional = swiss_ayanamsha(moment, system.id)
        if professional is not None:
            return professional
        fagan_base = lahiri_ayanamsha(moment) - ASTROLOG_LAHIRI_OFFSET_FROM_FAGAN
        return fagan_base + float(system.astrolog_offset or 0.0)
    return 0.0


def apply_zodiac_system(longitude: float, moment: datetime, system_id_or_name: str | None) -> float:
    system = get_zodiac_system(system_id_or_name)
    if system.mode == "constellational":
        return longitude % 360
    return (longitude - ayanamsha_for_system(moment, system_id_or_name)) % 360


def zodiac_supports_traditional_rules(system_id_or_name: str | None) -> bool:
    return bool(get_zodiac_system(system_id_or_name).traditional_compatible)
