"""Aspect definitions, detection logic, and timing estimates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
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
ASPECT_PHASE_EPSILON = 0.02
MAX_PERFECTION_DAYS = 14.0


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
        }

    days = orb / abs(change)
    timing_quality = "soon" if days <= 1 else "near-term" if days <= 3 else "later" if days <= MAX_PERFECTION_DAYS else "beyond scan"
    payload: dict[str, object] = {
        "daysToExact": days,
        "timeToExactText": format_duration(days),
        "perfectsAt": None,
        "perfectsAtText": "",
        "timingQuality": timing_quality,
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


def annotate_aspect_timings(
    aspects: Sequence[Mapping[str, object]],
    moment: datetime | None = None,
    timezone_name: str | None = None,
) -> list[dict[str, object]]:
    return [{**dict(aspect), **aspect_timing(aspect, moment, timezone_name)} for aspect in aspects]


def detect_aspects(
    positions: Sequence[Mapping[str, object]],
    selected_aspect_ids: Iterable[str],
    aspect_orbs: Mapping[str, float] | None = None,
    moment: datetime | None = None,
    timezone_name: str | None = None,
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

    timed = annotate_aspect_timings(detected, moment, timezone_name)
    return sorted(timed, key=lambda aspect: float(aspect["orb"]))
