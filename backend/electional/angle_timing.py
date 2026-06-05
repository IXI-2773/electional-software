"""Timing helpers for planets approaching or leaving chart angles."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Mapping, Sequence

from .aspects import format_duration
from .ephemeris import get_ecliptic_coordinates, normalize_degrees
from .houses import ANGULAR_ORB, angle_distance, calculate_angles
from .locations import LocationPreset
from .systems import apply_zodiac_system
from .time_utils import format_in_timezone

ANGLE_EXACT_TOLERANCE = 0.05
ANGLE_SCAN_HOURS = 24
ANGLE_COARSE_STEP_MINUTES = 15
ANGLE_PHASE_STEP_MINUTES = 10


def _planet_longitude(body_name: str, moment: datetime, zodiac_system_id: str) -> float:
    tropical = float(get_ecliptic_coordinates(body_name, moment)["longitude"])
    return apply_zodiac_system(normalize_degrees(tropical), moment, zodiac_system_id)


def _angle_longitude(angle_id: str, moment: datetime, location: LocationPreset, zodiac_system_id: str) -> float:
    angles = calculate_angles(moment, location.latitude, location.longitude, zodiac_system_id)
    for angle in angles:
        if angle["id"] == angle_id:
            return float(angle["longitude"])
    raise KeyError(f"Unknown angle id: {angle_id}")


def _distance_to_angle(
    body_name: str,
    angle_id: str,
    moment: datetime,
    location: LocationPreset,
    zodiac_system_id: str,
) -> float:
    return angle_distance(
        _planet_longitude(body_name, moment, zodiac_system_id),
        _angle_longitude(angle_id, moment, location, zodiac_system_id),
    )


def _phase_label(current_distance: float, future_distance: float) -> tuple[str, str, bool | None]:
    if current_distance <= ANGLE_EXACT_TOLERANCE:
        return "exact", "On angle", None
    if future_distance < current_distance - 0.01:
        return "applying", "Approaching angle", True
    if future_distance > current_distance + 0.01:
        return "separating", "Leaving angle", False
    return "stationary", "Holding angle", None


def _refine_next_exact(
    body_name: str,
    angle_id: str,
    moment: datetime,
    location: LocationPreset,
    zodiac_system_id: str,
) -> tuple[float, float] | None:
    samples = []
    total_steps = int(ANGLE_SCAN_HOURS * 60 / ANGLE_COARSE_STEP_MINUTES)
    for step in range(total_steps + 1):
        minutes = step * ANGLE_COARSE_STEP_MINUTES
        sample_time = moment + timedelta(minutes=minutes)
        samples.append((minutes / 1440, _distance_to_angle(body_name, angle_id, sample_time, location, zodiac_system_id)))
    best_index = min(range(len(samples)), key=lambda index: samples[index][1])
    best_days, best_distance = samples[best_index]
    if best_distance > max(1.0, float(ANGULAR_ORB)):
        return None

    low = samples[max(0, best_index - 1)][0]
    high = samples[min(len(samples) - 1, best_index + 1)][0]
    if high <= low:
        return (best_days, best_distance)

    ratio = (5**0.5 - 1) / 2
    left = high - ratio * (high - low)
    right = low + ratio * (high - low)
    left_distance = _distance_to_angle(body_name, angle_id, moment + timedelta(days=left), location, zodiac_system_id)
    right_distance = _distance_to_angle(body_name, angle_id, moment + timedelta(days=right), location, zodiac_system_id)
    for _ in range(22):
        if left_distance <= right_distance:
            high = right
            right = left
            right_distance = left_distance
            left = high - ratio * (high - low)
            left_distance = _distance_to_angle(body_name, angle_id, moment + timedelta(days=left), location, zodiac_system_id)
        else:
            low = left
            left = right
            left_distance = right_distance
            right = low + ratio * (high - low)
            right_distance = _distance_to_angle(body_name, angle_id, moment + timedelta(days=right), location, zodiac_system_id)

    refined_days = (low + high) / 2
    refined_distance = _distance_to_angle(body_name, angle_id, moment + timedelta(days=refined_days), location, zodiac_system_id)
    if refined_distance > ANGLE_EXACT_TOLERANCE:
        return None
    return refined_days, refined_distance


def angle_timing_for_position(
    position: Mapping[str, object],
    moment: datetime,
    location: LocationPreset,
    zodiac_system_id: str,
) -> dict[str, object]:
    closest_angle = position.get("closestAngle")
    if not isinstance(closest_angle, Mapping):
        return {}
    body_name = str(position.get("name") or "")
    angle_id = str(closest_angle.get("id") or "")
    if not body_name or not angle_id:
        return {}

    current_distance = float(closest_angle.get("distance", ANGULAR_ORB))
    future = moment + timedelta(minutes=ANGLE_PHASE_STEP_MINUTES)
    try:
        future_distance = _distance_to_angle(body_name, angle_id, future, location, zodiac_system_id)
        phase, phase_label, is_applying = _phase_label(current_distance, future_distance)
    except (KeyError, TypeError, ValueError):
        return {"anglePhase": "unknown", "anglePhaseLabel": "Angle timing unavailable", "isApplyingToAngle": None}

    payload: dict[str, object] = {
        "anglePhase": phase,
        "anglePhaseLabel": phase_label,
        "isApplyingToAngle": is_applying,
        "futureDistance10m": future_distance,
    }
    if is_applying is True or phase == "exact":
        refined = _refine_next_exact(body_name, angle_id, moment, location, zodiac_system_id)
        if refined:
            days_to_exact, exact_distance = refined
            exact_at = moment + timedelta(days=days_to_exact)
            payload.update(
                {
                    "daysToAngleExact": days_to_exact,
                    "timeToAngleExactText": format_duration(days_to_exact),
                    "angleExactAt": exact_at,
                    "angleExactAtText": format_in_timezone(exact_at, location.timezone),
                    "angleExactDistance": exact_distance,
                    "angleTimingMethod": "ephemeris angle scan",
                }
            )
    return payload


def annotate_angle_timings(
    positions: Sequence[Mapping[str, object]],
    moment: datetime,
    location: LocationPreset,
    zodiac_system_id: str,
) -> list[dict[str, object]]:
    annotated = []
    for position in positions:
        updated = dict(position)
        closest_angle = updated.get("closestAngle")
        if isinstance(closest_angle, Mapping):
            timing = angle_timing_for_position(updated, moment, location, zodiac_system_id)
            updated["closestAngle"] = {**dict(closest_angle), **timing}
        annotated.append(updated)
    return annotated
