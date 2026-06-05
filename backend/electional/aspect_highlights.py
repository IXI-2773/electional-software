"""Shared strongest-aspect evaluation and time-range scanning."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable, Mapping, Sequence
from zoneinfo import ZoneInfo

ASPECT_BASE_STRENGTH = {
    "Conjunction": 4.0,
    "Opposition": 3.4,
    "Trine": 3.2,
    "Square": 3.0,
    "Sextile": 2.2,
}


def _float_value(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _house_strength(house: object) -> float:
    try:
        house_number = int(house)
    except (TypeError, ValueError):
        return 0.0
    if house_number in {1, 4, 7, 10}:
        return 1.5
    if house_number in {2, 5, 8, 11}:
        return 0.7
    return -0.2


def aspect_strength(
    aspect: Mapping[str, object],
    positions_by_name: Mapping[str, Mapping[str, object]] | None = None,
    priority_bodies: set[str] | None = None,
) -> float:
    """Score one aspect consistently for dashboards, reports, and scans."""

    bodies = aspect.get("bodies", [])
    if not isinstance(bodies, list) or len(bodies) != 2:
        return -999.0
    score = ASPECT_BASE_STRENGTH.get(str(aspect.get("aspectName") or ""), 1.5)
    orb = _float_value(aspect.get("orb"), 8.0)
    score += max(0.0, 6.0 - orb) * 1.4
    if aspect.get("isApplying"):
        score += 1.6
    elif str(aspect.get("phaseLabel", "")).lower().startswith("applying"):
        score += 1.2
    elif str(aspect.get("phaseLabel", "")).lower().startswith("separating"):
        score -= 0.4
    if aspect.get("tone") in {"support", "stress"}:
        score += 0.5

    positions = positions_by_name or {}
    priorities = priority_bodies or set()
    for body in bodies:
        name = str(body)
        if name in priorities:
            score += 2.4
        if name in {"Moon", "Sun"}:
            score += 0.4
        planet = positions.get(name)
        if not planet:
            continue
        score += _house_strength(planet.get("house"))
        dignity = planet.get("dignity")
        if isinstance(dignity, Mapping):
            score += abs(_float_value(dignity.get("score"))) * 0.35
    return round(score, 3)


def strongest_aspect_result(
    snapshot: Mapping[str, object],
    priority_bodies: set[str] | None = None,
) -> dict[str, object] | None:
    positions = snapshot.get("positions", [])
    aspects = snapshot.get("detectedAspects", [])
    if not isinstance(positions, list) or not isinstance(aspects, list):
        return None
    positions_by_name = {
        str(planet.get("name")): planet
        for planet in positions
        if isinstance(planet, Mapping) and planet.get("name")
    }
    candidates = [
        (aspect_strength(aspect, positions_by_name, priority_bodies), aspect)
        for aspect in aspects
        if isinstance(aspect, Mapping)
    ]
    if not candidates:
        return None
    strength, aspect = max(candidates, key=lambda item: (item[0], -_float_value(item[1].get("orb"), 99)))
    moment = snapshot.get("date")
    return {
        **dict(aspect),
        "strength": strength,
        "moment": moment,
        "formattedTime": snapshot.get("formattedTime", ""),
        "score": snapshot.get("score"),
    }


def _iter_moments(start: datetime, end: datetime, step_minutes: int) -> list[datetime]:
    moments: list[datetime] = []
    current = start
    while current < end:
        moments.append(current)
        current += timedelta(minutes=step_minutes)
    return moments


def _best_over_range(
    snapshot_builder: Callable[[datetime], Mapping[str, object]],
    start: datetime,
    end: datetime,
    *,
    coarse_minutes: int = 15,
) -> tuple[dict[str, object] | None, list[dict[str, object]]]:
    coarse_results: list[dict[str, object]] = []
    for moment in _iter_moments(start, end, coarse_minutes):
        result = strongest_aspect_result(snapshot_builder(moment))
        if result:
            coarse_results.append(result)
    if not coarse_results:
        return None, []

    coarse_best = max(
        coarse_results,
        key=lambda result: (float(result.get("strength", -999)), -_float_value(result.get("orb"), 99)),
    )
    coarse_moment = coarse_best.get("moment")
    if not isinstance(coarse_moment, datetime):
        return coarse_best, coarse_results

    refine_start = max(start, coarse_moment - timedelta(minutes=coarse_minutes))
    refine_end = min(end, coarse_moment + timedelta(minutes=coarse_minutes + 1))
    refined: list[dict[str, object]] = []
    for moment in _iter_moments(refine_start, refine_end, 1):
        result = strongest_aspect_result(snapshot_builder(moment))
        if result:
            refined.append(result)
    best = max(
        refined or [coarse_best],
        key=lambda result: (float(result.get("strength", -999)), -_float_value(result.get("orb"), 99)),
    )
    timeline = sorted(
        coarse_results,
        key=lambda result: (float(result.get("strength", -999)), -_float_value(result.get("orb"), 99)),
        reverse=True,
    )[:12]
    return best, timeline


def build_aspect_highlights(
    displayed_snapshot: Mapping[str, object],
    timezone_name: str,
    snapshot_builder: Callable[[datetime], Mapping[str, object]],
) -> dict[str, object]:
    displayed_moment = displayed_snapshot.get("date")
    if not isinstance(displayed_moment, datetime):
        return {"current": None, "localDay": None, "rolling24Hours": None, "timeline": []}

    zone = ZoneInfo(timezone_name)
    local_moment = displayed_moment.astimezone(zone)
    local_start = datetime(local_moment.year, local_moment.month, local_moment.day, tzinfo=zone)
    local_end = local_start + timedelta(days=1)
    day_best, day_timeline = _best_over_range(
        snapshot_builder,
        local_start.astimezone(displayed_moment.tzinfo),
        local_end.astimezone(displayed_moment.tzinfo),
    )
    rolling_end = displayed_moment + timedelta(hours=24)
    rolling_best, rolling_timeline = _best_over_range(snapshot_builder, displayed_moment, rolling_end)

    return {
        "current": strongest_aspect_result(displayed_snapshot),
        "localDay": day_best,
        "rolling24Hours": rolling_best,
        "timeline": day_timeline,
        "rollingTimeline": rolling_timeline,
        "localDayStart": local_start,
        "localDayEnd": local_end,
    }
