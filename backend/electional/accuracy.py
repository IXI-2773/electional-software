"""Independent integration checks against the active Swiss Ephemeris backend."""

from __future__ import annotations

from datetime import datetime
from typing import Mapping, Sequence

from .locations import LocationPreset
from .professional import has_swisseph, swiss_ecliptic_coordinates, swiss_house_cusps

POSITION_TOLERANCE_DEGREES = 0.001
ANGLE_TOLERANCE_DEGREES = 0.001
HOUSE_TOLERANCE_DEGREES = 0.001


def angular_delta(first: float, second: float) -> float:
    return abs((first - second + 180) % 360 - 180)


def _maximum(values: Sequence[float]) -> float | None:
    return max(values) if values else None


def build_accuracy_audit(
    moment: datetime,
    location: LocationPreset,
    positions: Sequence[Mapping[str, object]],
    angles: Sequence[Mapping[str, object]],
    house_cusps: Sequence[Mapping[str, object]],
    house_system_id: str,
) -> dict[str, object]:
    if not has_swisseph():
        return {
            "status": "fallback",
            "label": "Fallback engine",
            "verified": False,
            "summary": "Swiss Ephemeris is unavailable; integration deltas cannot be verified.",
            "checks": [],
        }

    position_checks = []
    position_deltas = []
    speed_deltas = []
    for position in positions:
        body_name = str(position.get("name") or "")
        reference = swiss_ecliptic_coordinates(body_name, moment)
        tropical = position.get("tropicalLongitude")
        motion = position.get("motion")
        if not reference or tropical is None:
            continue
        longitude_delta = angular_delta(float(tropical), float(reference["longitude"]))
        position_deltas.append(longitude_delta)
        speed_delta = None
        if isinstance(motion, Mapping) and reference.get("dailyLongitudeChange") is not None:
            speed_delta = abs(
                float(motion.get("dailyLongitudeChange", 0))
                - float(reference["dailyLongitudeChange"])
            )
            speed_deltas.append(speed_delta)
        position_checks.append(
            {
                "body": body_name,
                "longitudeDelta": longitude_delta,
                "speedDelta": speed_delta,
            }
        )

    angle_reference = swiss_house_cusps(moment, location.latitude, location.longitude, "placidus")
    angle_deltas = []
    if angle_reference:
        reference_angles = {
            "asc": float(angle_reference["ascendant"]),
            "mc": float(angle_reference["midheaven"]),
            "dsc": (float(angle_reference["ascendant"]) + 180) % 360,
            "ic": (float(angle_reference["midheaven"]) + 180) % 360,
        }
        for angle in angles:
            angle_id = str(angle.get("id") or "")
            tropical = angle.get("tropicalLongitude")
            if angle_id in reference_angles and tropical is not None:
                angle_deltas.append(angular_delta(float(tropical), reference_angles[angle_id]))

    house_reference = swiss_house_cusps(moment, location.latitude, location.longitude, house_system_id)
    house_deltas = []
    if house_reference:
        reference_cusps = list(house_reference["cusps"])
        for cusp, reference_longitude in zip(house_cusps, reference_cusps):
            tropical = cusp.get("tropicalLongitude")
            if tropical is not None:
                house_deltas.append(angular_delta(float(tropical), float(reference_longitude)))

    max_position_delta = _maximum(position_deltas)
    max_speed_delta = _maximum(speed_deltas)
    max_angle_delta = _maximum(angle_deltas)
    max_house_delta = _maximum(house_deltas)
    failures = []
    if max_position_delta is None or max_position_delta > POSITION_TOLERANCE_DEGREES:
        failures.append("planet longitude integration")
    if max_angle_delta is None or max_angle_delta > ANGLE_TOLERANCE_DEGREES:
        failures.append("angle integration")
    if house_reference and (max_house_delta is None or max_house_delta > HOUSE_TOLERANCE_DEGREES):
        failures.append("house cusp integration")

    verified = not failures
    coverage = f"{len(position_checks)} planets, {len(angle_deltas)} angles"
    if house_reference:
        coverage += f", {len(house_deltas)} cusps"
    summary = (
        f"Swiss integration verified across {coverage}."
        if verified
        else f"Accuracy warning: review {', '.join(failures)}."
    )
    return {
        "status": "verified" if verified else "warning",
        "label": "Swiss verified" if verified else "Accuracy warning",
        "verified": verified,
        "summary": summary,
        "positionCount": len(position_checks),
        "angleCount": len(angle_deltas),
        "houseCuspCount": len(house_deltas),
        "maxPositionDeltaDegrees": max_position_delta,
        "maxSpeedDeltaDegreesPerDay": max_speed_delta,
        "maxAngleDeltaDegrees": max_angle_delta,
        "maxHouseDeltaDegrees": max_house_delta,
        "houseReferenceAvailable": bool(house_reference),
        "checks": position_checks,
        "failures": failures,
    }
