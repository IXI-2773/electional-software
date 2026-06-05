"""Optional professional astrology engine integration.

The application remains runnable with Astronomy Engine alone, but this module
centralizes Swiss Ephemeris/Astrolog discovery so higher-precision calculation
support can be enabled without rewriting the chart code.
"""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASTROLOG_ROOT = Path(r"C:\Users\Drago\Downloads\ast78win64")
ASTROLOG_EPHEM_PATH = ASTROLOG_ROOT / "ephem"
ASTROLOG_EXE_PATH = ASTROLOG_ROOT / "Astrolog.exe"

SWISS_BODY_IDS = {
    "Sun": 0,
    "Moon": 1,
    "Mercury": 2,
    "Venus": 3,
    "Mars": 4,
    "Jupiter": 5,
    "Saturn": 6,
    "Uranus": 7,
    "Neptune": 8,
    "Pluto": 9,
}

SWISS_HOUSE_CODES = {
    "placidus": b"P",
    "koch": b"K",
    "equal-house": b"E",
    "campanus": b"C",
    "regiomontanus": b"R",
    "porphyry": b"O",
    "alcabitius": b"B",
    "topocentric": b"T",
}
SWISS_AYANAMSHA_MODES = {
    "sidereal-fagan-bradley": "SIDM_FAGAN_BRADLEY",
    "sidereal-lahiri": "SIDM_LAHIRI",
    "sidereal-krishnamurti": "SIDM_KRISHNAMURTI",
    "sidereal-raman": "SIDM_RAMAN",
}

PROFESSIONAL_HOUSE_SYSTEM_IDS = frozenset(SWISS_HOUSE_CODES)


def normalize_degrees(value: float) -> float:
    return value % 360


@lru_cache(maxsize=1)
def _swisseph_module() -> Any | None:
    try:
        import swisseph as swe  # type: ignore[import-not-found]
    except Exception:
        return None
    if ASTROLOG_EPHEM_PATH.exists():
        swe.set_ephe_path(str(ASTROLOG_EPHEM_PATH))
    return swe


def has_swisseph() -> bool:
    return _swisseph_module() is not None


def has_astrolog_reference() -> bool:
    return ASTROLOG_ROOT.exists() and ASTROLOG_EPHEM_PATH.exists()


def available_ephemeris_files() -> list[str]:
    if not ASTROLOG_EPHEM_PATH.exists():
        return []
    return sorted(path.name for path in ASTROLOG_EPHEM_PATH.glob("*.se1"))


def engine_name() -> str:
    if has_swisseph():
        return "Swiss Ephemeris Python"
    return "Astronomy Engine Python"


def calculation_backend_status() -> dict[str, object]:
    files = available_ephemeris_files()
    return {
        "activeEngine": engine_name(),
        "swissPythonAvailable": has_swisseph(),
        "astrologReferenceAvailable": ASTROLOG_ROOT.exists(),
        "astrologExecutableAvailable": ASTROLOG_EXE_PATH.exists(),
        "ephemerisPath": str(ASTROLOG_EPHEM_PATH),
        "ephemerisFileCount": len(files),
        "ephemerisFiles": files,
        "fallbackActive": not has_swisseph(),
        "fallbackReason": "" if has_swisseph() else "Swiss Ephemeris Python bindings are not installed for this Python runtime.",
    }


def julian_day_ut(moment: datetime) -> float:
    utc = moment.astimezone(timezone.utc)
    swe = _swisseph_module()
    if swe is None:
        raise RuntimeError("Swiss Ephemeris Python bindings are not available.")
    hour = utc.hour + utc.minute / 60 + utc.second / 3600 + utc.microsecond / 3_600_000_000
    return float(swe.julday(utc.year, utc.month, utc.day, hour, swe.GREG_CAL))


def swiss_ecliptic_coordinates(body_name: str, moment: datetime) -> dict[str, float | None] | None:
    swe = _swisseph_module()
    body_id = SWISS_BODY_IDS.get(body_name)
    if swe is None or body_id is None:
        return None
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED
    try:
        result = swe.calc_ut(julian_day_ut(moment), body_id, flags)
    except Exception:
        return None
    values = result[0] if isinstance(result, tuple) else result
    return {
        "latitude": float(values[1]),
        "longitude": normalize_degrees(float(values[0])),
        "distanceAu": float(values[2]),
        "dailyLongitudeChange": float(values[3]),
    }


def swiss_ayanamsha(moment: datetime, zodiac_system_id: str) -> float | None:
    swe = _swisseph_module()
    mode_name = SWISS_AYANAMSHA_MODES.get(zodiac_system_id)
    if swe is None or mode_name is None:
        return None
    mode = getattr(swe, mode_name, None)
    if mode is None:
        return None
    try:
        swe.set_sid_mode(mode, 0, 0)
        return float(swe.get_ayanamsa_ut(julian_day_ut(moment)))
    except Exception:
        return None


def swiss_house_cusps(moment: datetime, latitude: float, longitude: float, house_system_id: str) -> dict[str, object] | None:
    swe = _swisseph_module()
    house_code = SWISS_HOUSE_CODES.get(house_system_id)
    if swe is None or house_code is None:
        return None
    try:
        cusps, ascmc = swe.houses_ex(julian_day_ut(moment), latitude, longitude, house_code)
    except Exception:
        return None

    cusp_values = list(cusps)
    # Swiss bindings differ here: some expose the native 1-based array with a
    # dummy value at index 0, while others return only the twelve real cusps.
    if len(cusp_values) >= 13:
        cusp_values = cusp_values[1:13]
    else:
        cusp_values = cusp_values[:12]
    if len(cusp_values) != 12:
        return None

    return {
        "cusps": [normalize_degrees(float(value)) for value in cusp_values],
        "ascendant": normalize_degrees(float(ascmc[0])),
        "midheaven": normalize_degrees(float(ascmc[1])),
        "source": "Swiss Ephemeris",
        "houseCode": house_code.decode("ascii"),
    }
