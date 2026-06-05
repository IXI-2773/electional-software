"""Aspect definitions, detection logic, and timing estimates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import floor
from typing import Callable, Iterable, Mapping, Sequence


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
ASPECT_PHASE_EPSILON = 0.02
MAX_PERFECTION_DAYS = 14.0
EXACT_TIMING_TOLERANCE = 0.02
LongitudeResolver = Callable[[str, datetime], float]


def angular_distance(first_longitude: float, second_longitude: float) -> float:
    raw_distance = abs(first_longitude - second_longitude) % 360
    return 360 - raw_distance if raw_distance > 180 else raw_distance


def format_orb(orb: float) -> str:
    degrees = floor(orb)
    minutes = round((orb - degrees) * 60)
    return f"{degrees} deg {minutes:02d} min"


def format_duration(days: float) -> str:
    total_minutes = max(0, round(days * 24 * 60))
    if total_minutes < 60:
        return f"{total_minutes} min"
    hours, minutes = divmod(total_minutes, 60)
    if hours < 24:
        return f"{hours}h {minutes:02d}m" if minutes else f"{hours}h"
    day_count, remaining_hours = divmod(hours, 24)
    if remaining_hours:
        return f"{day_count}d {remaining_hours}h"
    return f"{day_count}d"


def daily_longitude_change(position: Mapping[str, object]) -> float | None:
    motion = position.get("motion")
    if not isinstance(motion, Mapping):
        return None
    try:
        return float(motion["dailyLongitudeChange"])
    except (KeyError, TypeError, ValueError):
        return None


def opposite_signs(first: float, second: float) -> bool:
    return (first < 0 < second) or (second < 0 < first)


def aspect_phase(first: Mapping[str, object], second: Mapping[str, object], aspect: Aspect, orb: float) -> dict[str, object]:
    first_motion = daily_longitude_change(first)
    second_motion = daily_longitude_change(second)
    if first_motion is None or second_motion is None:
        return {
            "phase": "unknown",
            "phaseLabel": "Unknown",
            "isApplying": None,
            "orbChangePerDay": 0.0,
        }

    current_signed_orb = distance_to_aspect = angular_distance(float(first["longitude"]), float(second["longitude"])) - aspect.angle
    future_distance = angular_distance(
        float(first["longitude"]) + first_motion,
        float(second["longitude"]) + second_motion,
    )
    future_signed_orb = future_distance - aspect.angle
    future_orb = abs(future_signed_orb)
    orb_change = future_orb - orb
    crossed_exact = abs(distance_to_aspect) > ASPECT_PHASE_EPSILON and opposite_signs(current_signed_orb, future_signed_orb)
    days_to_exact_estimate = None
    if crossed_exact:
        denominator = abs(current_signed_orb) + abs(future_signed_orb)
        days_to_exact_estimate = abs(current_signed_orb) / denominator if denominator else 0.0

    if orb <= ASPECT_PHASE_EPSILON:
        phase = "exact"
        label = "Near exact"
        is_applying = None
    elif crossed_exact:
        phase = "applying"
        label = "Applying"
        is_applying = True
        orb_change = -orb
    elif abs(orb_change) <= ASPECT_PHASE_EPSILON:
        phase = "exact"
        label = "Near exact"
        is_applying = None
    elif orb_change < 0:
        phase = "applying"
        label = "Applying"
        is_applying = True
    else:
        phase = "separating"
        label = "Separating"
        is_applying = False

    return {
        "phase": phase,
        "phaseLabel": label,
        "isApplying": is_applying,
        "orbChangePerDay": orb_change,
        "crossesExactWithinDay": crossed_exact,
        "daysToExactEstimate": days_to_exact_estimate,
    }


def aspect_timing(aspect: Mapping[str, object], moment: datetime | None = None, timezone_name: str | None = None) -> dict[str, object]:
    if not aspect.get("isApplying"):
        return {
            "daysToExact": None,
            "timeToExactText": "",
            "perfectsAt": None,
            "perfectsAtText": "",
            "timingQuality": "not applying",
            "timingMethod": "not applicable",
        }
    try:
        orb = float(aspect.get("orb", 0))
        change = float(aspect.get("orbChangePerDay", 0))
    except (TypeError, ValueError):
        return {
            "daysToExact": None,
            "timeToExactText": "",
            "perfectsAt": None,
            "perfectsAtText": "",
            "timingQuality": "unknown",
            "timingMethod": "unavailable",
        }
    estimate = aspect.get("daysToExactEstimate")
    if estimate is not None:
        try:
            days = float(estimate)
        except (TypeError, ValueError):
            days = None
        if days is not None:
            timing_quality = "soon" if days <= 1 else "near-term" if days <= 3 else "later" if days <= MAX_PERFECTION_DAYS else "beyond scan"
            payload: dict[str, object] = {
                "daysToExact": days,
                "timeToExactText": format_duration(days),
                "perfectsAt": None,
                "perfectsAtText": "",
                "timingQuality": timing_quality,
                "timingMethod": "linear speed",
            }
            if moment is not None and days <= MAX_PERFECTION_DAYS:
                perfection = moment + timedelta(days=days)
                payload["perfectsAt"] = perfection
                if timezone_name:
                    from .time_utils import format_in_timezone

                    payload["perfectsAtText"] = format_in_timezone(perfection, timezone_name)
                else:
                    payload["perfectsAtText"] = perfection.isoformat()
            return payload

    if change >= -ASPECT_PHASE_EPSILON:
        return {
            "daysToExact": None,
            "timeToExactText": "",
            "perfectsAt": None,
            "perfectsAtText": "",
            "timingQuality": "unknown",
            "timingMethod": "unavailable",
        }

    days = orb / abs(change)
    timing_quality = "soon" if days <= 1 else "near-term" if days <= 3 else "later" if days <= MAX_PERFECTION_DAYS else "beyond scan"
    payload: dict[str, object] = {
        "daysToExact": days,
        "timeToExactText": format_duration(days),
        "perfectsAt": None,
        "perfectsAtText": "",
        "timingQuality": timing_quality,
        "timingMethod": "linear speed",
    }
    if moment is not None and days <= MAX_PERFECTION_DAYS:
        perfection = moment + timedelta(days=days)
        payload["perfectsAt"] = perfection
        if timezone_name:
            from .time_utils import format_in_timezone

            payload["perfectsAtText"] = format_in_timezone(perfection, timezone_name)
        else:
            payload["perfectsAtText"] = perfection.isoformat()
    return payload


def refine_aspect_timing(
    aspect: Mapping[str, object],
    moment: datetime,
    timezone_name: str | None,
    longitude_resolver: LongitudeResolver,
) -> dict[str, object]:
    """Refine an applying aspect's linear estimate against real ephemeris positions."""
    baseline = aspect_timing(aspect, moment, timezone_name)
    try:
        initial_days = float(baseline["daysToExact"])
        body_names = [str(name) for name in aspect["bodies"]]
        exact_angle = float(aspect["exactAngle"])
    except (KeyError, TypeError, ValueError):
        return baseline
    if len(body_names) != 2 or not 0 <= initial_days <= MAX_PERFECTION_DAYS:
        return baseline

    def orb_at(days: float) -> float:
        sample_time = moment + timedelta(days=days)
        first = longitude_resolver(body_names[0], sample_time)
        second = longitude_resolver(body_names[1], sample_time)
        return abs(angular_distance(first, second) - exact_angle)

    radius = max(0.2, min(1.5, initial_days * 0.35))
    low = max(0.0, initial_days - radius)
    high = min(MAX_PERFECTION_DAYS, initial_days + radius)
    sample_count = 8
    samples = [
        (low + (high - low) * index / sample_count, 0.0)
        for index in range(sample_count + 1)
    ]
    try:
        samples = [(days, orb_at(days)) for days, _ in samples]
    except (KeyError, TypeError, ValueError):
        return baseline
    best_index = min(range(len(samples)), key=lambda index: samples[index][1])
    bracket_low = samples[max(0, best_index - 1)][0]
    bracket_high = samples[min(len(samples) - 1, best_index + 1)][0]

    # Golden-section minimization is stable at conjunction/opposition wrap points
    # because it works on absolute orb rather than a discontinuous signed angle.
    ratio = (5**0.5 - 1) / 2
    left = bracket_high - ratio * (bracket_high - bracket_low)
    right = bracket_low + ratio * (bracket_high - bracket_low)
    left_orb = orb_at(left)
    right_orb = orb_at(right)
    for _ in range(24):
        if left_orb <= right_orb:
            bracket_high = right
            right = left
            right_orb = left_orb
            left = bracket_high - ratio * (bracket_high - bracket_low)
            left_orb = orb_at(left)
        else:
            bracket_low = left
            left = right
            left_orb = right_orb
            right = bracket_low + ratio * (bracket_high - bracket_low)
            right_orb = orb_at(right)

    refined_days = (bracket_low + bracket_high) / 2
    refined_orb = orb_at(refined_days)
    current_orb = float(aspect.get("orb", 999))
    if refined_orb > EXACT_TIMING_TOLERANCE or refined_orb >= current_orb:
        return baseline

    perfection = moment + timedelta(days=refined_days)
    if timezone_name:
        from .time_utils import format_in_timezone

        perfection_text = format_in_timezone(perfection, timezone_name)
    else:
        perfection_text = perfection.isoformat()
    return {
        "daysToExact": refined_days,
        "timeToExactText": format_duration(refined_days),
        "perfectsAt": perfection,
        "perfectsAtText": perfection_text,
        "timingQuality": "soon" if refined_days <= 1 else "near-term" if refined_days <= 3 else "later",
        "timingMethod": "ephemeris refined",
        "perfectionOrb": refined_orb,
    }


def annotate_aspect_timings(
    aspects: Sequence[Mapping[str, object]],
    moment: datetime | None = None,
    timezone_name: str | None = None,
    longitude_resolver: LongitudeResolver | None = None,
) -> list[dict[str, object]]:
    annotated = []
    for aspect in aspects:
        timing = aspect_timing(aspect, moment, timezone_name)
        if moment is not None and longitude_resolver is not None and aspect.get("isApplying"):
            timing = refine_aspect_timing(aspect, moment, timezone_name, longitude_resolver)
        annotated.append({**dict(aspect), **timing})
    return annotated


def detect_aspects(
    positions: Sequence[Mapping[str, object]],
    selected_aspect_ids: Iterable[str],
    aspect_orbs: Mapping[str, float] | None = None,
    moment: datetime | None = None,
    timezone_name: str | None = None,
    longitude_resolver: LongitudeResolver | None = None,
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
                    phase = aspect_phase(first, second, aspect, orb)
                    detected.append(
                        {
                            "aspectId": aspect.id,
                            "aspectName": aspect.name,
                            "exactAngle": aspect.angle,
                            "tone": aspect.tone,
                            "orb": orb,
                            "orbLimit": orb_limit,
                            "orbText": format_orb(orb),
                            **phase,
                            "bodies": [first_name, second_name],
                            "label": f"{first_name} {aspect.name.lower()} {second_name}",
                        }
                    )

    timed = annotate_aspect_timings(detected, moment, timezone_name, longitude_resolver)
    return sorted(timed, key=lambda aspect: float(aspect["orb"]))
