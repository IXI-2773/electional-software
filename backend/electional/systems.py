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


@dataclass(frozen=True)
class HouseSystem:
    id: str
    name: str
    description: str


DEFAULT_ZODIAC_SYSTEM_ID = "sidereal-lahiri"
DEFAULT_HOUSE_SYSTEM_ID = "whole-sign"

ZODIAC_SYSTEMS: tuple[ZodiacSystem, ...] = (
    ZodiacSystem(
        id="sidereal-lahiri",
        name="Sidereal Lahiri",
        mode="sidereal",
        description="Sidereal zodiac with Lahiri/Chitrapaksha ayanamsha.",
    ),
    ZodiacSystem(
        id="tropical",
        name="Tropical",
        mode="tropical",
        description="Standard seasonal zodiac with no ayanamsha offset.",
    ),
)

HOUSE_SYSTEMS: tuple[HouseSystem, ...] = (
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
        id="topocentric",
        name="Topocentric",
        description="Polich-Page quadrant houses using local latitude-derived pole divisions.",
    ),
    HouseSystem(
        id="koch",
        name="Koch",
        description="Birthplace house system using time trisections from MC and IC arcs.",
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
    """Approximate Lahiri ayanamsha in degrees for UI/system selection.

    This uses a J2000 anchor and mean precession rate. It is suitable for
    display/sign placement in the current Astronomy Engine build; a future
    Swiss Ephemeris integration can replace this with exact ayanamsha tables.
    """

    return 23.853055 + (decimal_year(moment) - 2000.0) * (50.290966 / 3600)


def ayanamsha_for_system(moment: datetime, system_id_or_name: str | None) -> float:
    system = get_zodiac_system(system_id_or_name)
    if system.id == "sidereal-lahiri":
        return lahiri_ayanamsha(moment)
    return 0.0


def apply_zodiac_system(longitude: float, moment: datetime, system_id_or_name: str | None) -> float:
    return (longitude - ayanamsha_for_system(moment, system_id_or_name)) % 360
