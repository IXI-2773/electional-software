"""Planetary day and hour calculations."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import astronomy

from .locations import LocationPreset
from .time_utils import astronomy_time_string, format_in_timezone

CHALDEAN_ORDER = ("Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon")
WEEKDAY_RULERS = {
    0: "Moon",
    1: "Mars",
    2: "Mercury",
    3: "Jupiter",
    4: "Venus",
    5: "Saturn",
    6: "Sun",
}
HOUR_SCORE = {
    "Venus": 2.0,
    "Jupiter": 2.0,
    "Sun": 1.0,
    "Moon": 1.0,
    "Mercury": 1.0,
    "Mars": -2.0,
    "Saturn": -2.0,
}


def _utc_datetime(time: astronomy.Time | None) -> datetime | None:
    if time is None:
        return None
    value = time.Utc()
    return value.replace(tzinfo=UTC)


def sun_event(moment: datetime, location: LocationPreset, direction: astronomy.Direction, limit_days: float) -> datetime | None:
    observer = astronomy.Observer(location.latitude, location.longitude, 0)
    found = astronomy.SearchRiseSet(
        astronomy.Body.Sun,
        observer,
        direction,
        astronomy.Time(astronomy_time_string(moment)),
        limit_days,
    )
    return _utc_datetime(found)


def day_ruler_for_moment(moment: datetime, location: LocationPreset) -> str:
    local = moment.astimezone(ZoneInfo(location.timezone))
    return WEEKDAY_RULERS[local.weekday()]


def planetary_hour_context(moment: datetime, location: LocationPreset) -> dict[str, object]:
    previous_rise = sun_event(moment, location, astronomy.Direction.Rise, -2)
    previous_set = sun_event(moment, location, astronomy.Direction.Set, -2)
    next_rise = sun_event(moment, location, astronomy.Direction.Rise, 2)
    next_set = sun_event(moment, location, astronomy.Direction.Set, 2)
    if not previous_rise or not previous_set or not next_rise or not next_set:
        return {
            "available": False,
            "reason": "Sunrise/sunset unavailable for this location and date.",
        }

    is_daytime = previous_rise > previous_set
    period_start = previous_rise if is_daytime else previous_set
    period_end = next_set if is_daytime else next_rise
    day_anchor = previous_rise
    ruler_day = day_ruler_for_moment(day_anchor, location)
    day_index = CHALDEAN_ORDER.index(ruler_day)
    period_seconds = (period_end - period_start).total_seconds()
    segment_seconds = period_seconds / 12
    elapsed = max(0, min(period_seconds - 1, (moment - period_start).total_seconds()))
    hour_number = int(elapsed // segment_seconds) + 1
    sequence_offset = (hour_number - 1) + (0 if is_daytime else 12)
    hour_ruler = CHALDEAN_ORDER[(day_index + sequence_offset) % len(CHALDEAN_ORDER)]

    return {
        "available": True,
        "period": "day" if is_daytime else "night",
        "dayRuler": ruler_day,
        "hourRuler": hour_ruler,
        "hourNumber": hour_number,
        "scoreImpact": HOUR_SCORE.get(hour_ruler, 0.0),
        "periodStart": period_start,
        "periodEnd": period_end,
        "periodStartText": format_in_timezone(period_start, location.timezone),
        "periodEndText": format_in_timezone(period_end, location.timezone),
    }
