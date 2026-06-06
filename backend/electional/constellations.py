"""Ecliptic constellation span and ascensional speed diagnostics."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Mapping, Sequence

from .ephemeris import normalize_degrees
from .houses import (
    calculate_ascendant,
    local_sidereal_degrees,
    next_sidereal_root,
    previous_sidereal_root,
    signed_angle_distance,
    true_obliquity,
)
from .locations import LocationPreset

SIDEREAL_DEGREES_PER_HOUR = 360.985647 / 24

SOURCE_NOTE = (
    "Approximate unequal IAU ecliptic-crossing constellation spans for planning diagnostics; "
    "the wheel shows ecliptic span, not full sky-polygon outlines, and zodiac signs, houses, "
    "and dignities still use the selected astrological system."
)

ECLIPTIC_CONSTELLATION_SPANS: tuple[dict[str, object], ...] = (
    {"id": "pisces", "name": "Pisces", "abbreviation": "Psc", "start": 351.0, "end": 29.0},
    {"id": "aries", "name": "Aries", "abbreviation": "Ari", "start": 29.0, "end": 54.0},
    {"id": "taurus", "name": "Taurus", "abbreviation": "Tau", "start": 54.0, "end": 91.0},
    {"id": "gemini", "name": "Gemini", "abbreviation": "Gem", "start": 91.0, "end": 120.0},
    {"id": "cancer", "name": "Cancer", "abbreviation": "Cnc", "start": 120.0, "end": 141.0},
    {"id": "leo", "name": "Leo", "abbreviation": "Leo", "start": 141.0, "end": 178.0},
    {"id": "virgo", "name": "Virgo", "abbreviation": "Vir", "start": 178.0, "end": 222.0},
    {"id": "libra", "name": "Libra", "abbreviation": "Lib", "start": 222.0, "end": 246.0},
    {"id": "scorpius", "name": "Scorpius", "abbreviation": "Sco", "start": 246.0, "end": 252.0},
    {"id": "ophiuchus", "name": "Ophiuchus", "abbreviation": "Oph", "start": 252.0, "end": 270.0},
    {"id": "sagittarius", "name": "Sagittarius", "abbreviation": "Sgr", "start": 270.0, "end": 300.0},
    {"id": "capricornus", "name": "Capricornus", "abbreviation": "Cap", "start": 300.0, "end": 327.0},
    {"id": "aquarius", "name": "Aquarius", "abbreviation": "Aqr", "start": 327.0, "end": 351.0},
)


def _span_degrees(start: float, end: float) -> float:
    return (end - start) % 360 or 360.0


def constellation_span_degrees(constellation_id: str) -> float:
    for span in ECLIPTIC_CONSTELLATION_SPANS:
        if span["id"] == constellation_id:
            return _span_degrees(float(span["start"]), float(span["end"]))
    raise KeyError(f"Unknown constellation id: {constellation_id}")


def _contains_longitude(longitude: float, start: float, end: float) -> bool:
    normalized = normalize_degrees(longitude)
    if start <= end:
        return start <= normalized < end
    return normalized >= start or normalized < end


def constellation_for_longitude(longitude: float) -> dict[str, object]:
    """Return the unequal ecliptic constellation span containing a longitude."""

    normalized = normalize_degrees(longitude)
    for index, span in enumerate(ECLIPTIC_CONSTELLATION_SPANS):
        start = float(span["start"])
        end = float(span["end"])
        if _contains_longitude(normalized, start, end):
            width = _span_degrees(start, end)
            degree_into = (normalized - start) % 360
            next_span = ECLIPTIC_CONSTELLATION_SPANS[(index + 1) % len(ECLIPTIC_CONSTELLATION_SPANS)]
            return {
                "id": span["id"],
                "name": span["name"],
                "abbreviation": span["abbreviation"],
                "startLongitude": start,
                "endLongitude": end,
                "spanDegrees": width,
                "spanRatioToSign": width / 30,
                "longitude": normalized,
                "degreeIntoConstellation": degree_into,
                "percentThrough": degree_into / width,
                "distanceToEndDegrees": (end - normalized) % 360,
                "nextConstellation": {
                    "id": next_span["id"],
                    "name": next_span["name"],
                    "abbreviation": next_span["abbreviation"],
                },
            }
    raise ValueError(f"No constellation span found for longitude {longitude}")


def annotate_points_with_constellations(points: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    """Attach unequal ecliptic constellation context to positions or angles."""

    annotated = []
    for point in points:
        longitude = point.get("tropicalLongitude")
        if longitude is None:
            longitude = point.get("longitude", 0)
        annotated.append({**point, "constellation": constellation_for_longitude(float(longitude))})
    return annotated


def _ascendant_longitude(moment: datetime, latitude: float, longitude: float, obliquity: float) -> float:
    return calculate_ascendant(local_sidereal_degrees(moment, longitude), latitude, obliquity)


def ascendant_speed_deg_per_hour(moment: datetime, latitude: float, longitude: float) -> float:
    """Estimate instantaneous ascendant speed with a centered finite difference."""

    obliquity = true_obliquity(moment)
    before = _ascendant_longitude(moment - timedelta(minutes=10), latitude, longitude, obliquity)
    after = _ascendant_longitude(moment + timedelta(minutes=10), latitude, longitude, obliquity)
    return signed_angle_distance(after, before) / (20 / 60)


def _tempo_for_speed(speed: float) -> dict[str, object]:
    if speed >= 24:
        return {"label": "fast", "scoreImpact": 1.0, "summary": "fast-rising ascendant gives a shorter, more responsive window"}
    if speed <= 10:
        return {"label": "slow", "scoreImpact": -1.0, "summary": "slow-rising ascendant stretches the window and can feel less responsive"}
    return {"label": "steady", "scoreImpact": 0.0, "summary": "ascendant tempo is close to the normal planning range"}


def _size_context(span_degrees: float) -> dict[str, object]:
    if span_degrees <= 12:
        return {"label": "narrow", "scoreImpact": -0.5, "summary": "narrow constellation span makes the window more timing-sensitive"}
    if span_degrees >= 38:
        return {"label": "broad", "scoreImpact": 0.5, "summary": "broad constellation span gives a steadier background"}
    return {"label": "moderate", "scoreImpact": 0.0, "summary": "constellation span is moderate"}


def _sidereal_arc_minutes(start_longitude: float, end_longitude: float, current_sidereal: float, latitude: float, obliquity: float) -> float:
    start_root = previous_sidereal_root(start_longitude, current_sidereal, latitude, obliquity)
    end_root = next_sidereal_root(end_longitude, current_sidereal, latitude, obliquity)
    sidereal_arc = (end_root - start_root) % 360
    return sidereal_arc / SIDEREAL_DEGREES_PER_HOUR * 60


def rising_context(moment: datetime, location: LocationPreset, angles: Sequence[Mapping[str, object]]) -> dict[str, object]:
    ascendant = next((angle for angle in angles if angle.get("id") == "asc"), None)
    asc_longitude = float((ascendant or {}).get("tropicalLongitude") or (ascendant or {}).get("longitude") or 0)
    constellation = constellation_for_longitude(asc_longitude)
    speed = ascendant_speed_deg_per_hour(moment, location.latitude, location.longitude)
    tempo = _tempo_for_speed(speed)
    size = _size_context(float(constellation["spanDegrees"]))
    obliquity = true_obliquity(moment)
    current_sidereal = local_sidereal_degrees(moment, location.longitude)
    sign_start = int(asc_longitude // 30) * 30
    sign_end = normalize_degrees(sign_start + 30)
    constellation_minutes = _sidereal_arc_minutes(
        float(constellation["startLongitude"]),
        float(constellation["endLongitude"]),
        current_sidereal,
        location.latitude,
        obliquity,
    )
    sign_minutes = _sidereal_arc_minutes(sign_start, sign_end, current_sidereal, location.latitude, obliquity)
    minutes_to_next = float(constellation["distanceToEndDegrees"]) / max(abs(speed), 0.1) * 60

    return {
        "ascendantLongitude": asc_longitude,
        "ascendantConstellation": constellation,
        "ascendantSpeedDegPerHour": speed,
        "tempo": tempo,
        "spanContext": size,
        "minutesToNextConstellation": minutes_to_next,
        "currentConstellationRisingMinutes": constellation_minutes,
        "currentSignRisingMinutes": sign_minutes,
        "scoreImpact": float(tempo["scoreImpact"]) + float(size["scoreImpact"]),
        "sourceNote": SOURCE_NOTE,
    }


def chart_constellation_context(moment: datetime, location: LocationPreset, positions: Sequence[Mapping[str, object]], angles: Sequence[Mapping[str, object]]) -> dict[str, object]:
    return {
        "sourceNote": SOURCE_NOTE,
        "rising": rising_context(moment, location, angles),
        "positions": [
            {
                "name": point.get("name"),
                "constellation": point.get("constellation"),
            }
            for point in positions
        ],
        "angles": [
            {
                "name": point.get("name"),
                "shortName": point.get("shortName"),
                "constellation": point.get("constellation"),
            }
            for point in angles
        ],
    }
