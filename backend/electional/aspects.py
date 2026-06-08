"""Aspect definitions, detection logic, and timing estimates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from math import floor
from pathlib import Path
import re
from typing import Any, Callable, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class Aspect:
    id: str
    name: str
    angle: float
    default_orb: float
    tone: str
    meaning: str
    abbreviation: str = ""
    glyph: str = ""
    color: str = "#536d8d"
    enabled: bool = True
    built_in: bool = True

    def to_json(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "angle": self.angle,
            "orb": self.default_orb,
            "defaultOrb": self.default_orb,
            "tone": self.tone,
            "meaning": self.meaning,
            "abbreviation": self.abbreviation,
            "glyph": self.glyph,
            "color": self.color,
            "enabled": self.enabled,
            "builtIn": self.built_in,
        }


@dataclass(frozen=True)
class AspectProfile:
    id: str
    name: str
    description: str
    aspects: tuple[Aspect, ...]

    def to_json(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "aspects": [aspect.to_json() for aspect in self.aspects],
        }


ASPECTS: tuple[Aspect, ...] = (
    Aspect(
        id="conjunction",
        name="Conjunction",
        angle=0,
        default_orb=8,
        tone="mixed",
        meaning="Merges planetary significations and intensifies the elected moment.",
        abbreviation="Conj",
        glyph="\u260c",
        color="#516b92",
    ),
    Aspect(
        id="trine",
        name="Trine",
        angle=120,
        default_orb=7,
        tone="support",
        meaning="Shows ease, flow, and cooperation between the planets involved.",
        abbreviation="Tri",
        glyph="\u25b3",
        color="#286fc2",
    ),
    Aspect(
        id="square",
        name="Square",
        angle=90,
        default_orb=6,
        tone="stress",
        meaning="Signals friction, urgency, and pressure that may require management.",
        abbreviation="Sqr",
        glyph="\u25a1",
        color="#c23f4e",
    ),
    Aspect(
        id="opposition",
        name="Opposition",
        angle=180,
        default_orb=7,
        tone="stress",
        meaning="Highlights polarization, exposure, and competing priorities.",
        abbreviation="Opp",
        glyph="\u260d",
        color="#c93342",
    ),
    Aspect(
        id="sextile",
        name="Sextile",
        angle=60,
        default_orb=5,
        tone="support",
        meaning="Offers opportunity through intentional action and coordination.",
        abbreviation="Sex",
        glyph="\u2736",
        color="#24846f",
    ),
)

ASPECT_BY_ID = {aspect.id: aspect for aspect in ASPECTS}
BUILT_IN_ASPECT_IDS = tuple(aspect.id for aspect in ASPECTS)
DEFAULT_ASPECT_PROFILE_ID = "major-five"
ASPECT_PROFILE_PATH = Path.cwd() / ".electional-aspect-profiles.json"
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


def sanitize_aspect_id(text: str) -> str:
    compact = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return compact or "custom-aspect"


def _float_from_payload(payload: Mapping[str, object], *keys: str, fallback: float = 0.0) -> float:
    for key in keys:
        if key not in payload:
            continue
        try:
            return float(payload[key])
        except (TypeError, ValueError):
            break
    return fallback


def aspect_from_mapping(payload: Mapping[str, object], *, built_in_default: bool = False) -> Aspect:
    name = str(payload.get("name") or payload.get("aspectName") or "").strip()
    aspect_id = str(payload.get("id") or sanitize_aspect_id(name)).strip()
    default = ASPECT_BY_ID.get(aspect_id)
    if default and not name:
        name = default.name
    angle = _float_from_payload(payload, "angle", "exactAngle", fallback=default.angle if default else 0.0)
    orb = _float_from_payload(payload, "orb", "defaultOrb", "default_orb", fallback=default.default_orb if default else 1.0)
    tone = str(payload.get("tone") or (default.tone if default else "mixed")).strip().lower()
    meaning = str(payload.get("meaning") or payload.get("description") or (default.meaning if default else "Custom aspect definition.")).strip()
    abbreviation = str(payload.get("abbreviation") or payload.get("abbr") or (default.abbreviation if default else name[:4])).strip()
    glyph = str(payload.get("glyph") or (default.glyph if default else abbreviation[:2])).strip()
    color = str(payload.get("color") or (default.color if default else "#536d8d")).strip()
    enabled = bool(payload.get("enabled", default.enabled if default else True))
    built_in = bool(payload.get("builtIn", payload.get("built_in", default.built_in if default else built_in_default)))
    return Aspect(
        id=aspect_id,
        name=name or aspect_id.replace("-", " ").title(),
        angle=angle,
        default_orb=orb,
        tone=tone,
        meaning=meaning,
        abbreviation=abbreviation or aspect_id[:4].title(),
        glyph=glyph or abbreviation[:2] or aspect_id[:2].title(),
        color=color or "#536d8d",
        enabled=enabled,
        built_in=built_in,
    )


def validate_aspect(aspect: Aspect, seen_ids: set[str] | None = None) -> list[str]:
    errors: list[str] = []
    if not aspect.name.strip():
        errors.append("Aspect name is required.")
    if not aspect.id.strip():
        errors.append(f"{aspect.name or 'Aspect'} needs an id.")
    if seen_ids is not None and aspect.id in seen_ids:
        errors.append(f"Duplicate aspect id: {aspect.id}.")
    if not 0 <= float(aspect.angle) <= 180:
        errors.append(f"{aspect.name}: exact angle must be between 0 and 180 degrees.")
    if not 0 <= float(aspect.default_orb) <= 30:
        errors.append(f"{aspect.name}: orb must be between 0 and 30 degrees.")
    if aspect.tone not in {"support", "stress", "mixed"}:
        errors.append(f"{aspect.name}: tone must be support, stress, or mixed.")
    return errors


def normalize_aspect_profile(profile: AspectProfile) -> AspectProfile:
    by_id = {aspect.id: aspect for aspect in profile.aspects}
    normalized: list[Aspect] = []
    for built_in in ASPECTS:
        normalized.append(by_id.get(built_in.id, built_in))
    for aspect in profile.aspects:
        if aspect.id not in BUILT_IN_ASPECT_IDS:
            normalized.append(aspect)
    return AspectProfile(profile.id, profile.name, profile.description, tuple(normalized))


def validate_aspect_profile(profile: AspectProfile) -> list[str]:
    errors: list[str] = []
    if not profile.name.strip():
        errors.append("Profile name is required.")
    if not profile.id.strip():
        errors.append("Profile id is required.")
    seen: set[str] = set()
    for aspect in profile.aspects:
        errors.extend(validate_aspect(aspect, seen))
        seen.add(aspect.id)
    return errors


def default_aspect_profile() -> AspectProfile:
    return AspectProfile(
        DEFAULT_ASPECT_PROFILE_ID,
        "Major Five",
        "Built-in conjunction, opposition, square, trine, and sextile profile.",
        ASPECTS,
    )


def aspect_profile_from_mapping(payload: Mapping[str, object]) -> AspectProfile:
    aspects_payload = payload.get("aspects", [])
    aspects: list[Aspect] = []
    if isinstance(aspects_payload, Sequence) and not isinstance(aspects_payload, (str, bytes)):
        for item in aspects_payload:
            if isinstance(item, Mapping):
                aspects.append(aspect_from_mapping(item))
    name = str(payload.get("name") or "Custom Aspect Profile").strip()
    profile = AspectProfile(
        str(payload.get("id") or sanitize_aspect_id(name)).strip(),
        name,
        str(payload.get("description") or "").strip(),
        tuple(aspects or ASPECTS),
    )
    return normalize_aspect_profile(profile)


def load_aspect_profiles(path: Path = ASPECT_PROFILE_PATH) -> list[AspectProfile]:
    profiles = [default_aspect_profile()]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return profiles
    profile_payloads: object = payload.get("profiles", []) if isinstance(payload, dict) else payload
    if not isinstance(profile_payloads, Sequence) or isinstance(profile_payloads, (str, bytes)):
        return profiles
    for item in profile_payloads:
        if not isinstance(item, Mapping):
            continue
        profile = aspect_profile_from_mapping(item)
        if profile.id == DEFAULT_ASPECT_PROFILE_ID:
            continue
        if validate_aspect_profile(profile):
            continue
        profiles.append(profile)
    return profiles


def save_aspect_profiles(profiles: Sequence[AspectProfile], path: Path = ASPECT_PROFILE_PATH) -> None:
    custom_profiles = [profile.to_json() for profile in profiles if profile.id != DEFAULT_ASPECT_PROFILE_ID]
    path.write_text(json.dumps({"profiles": custom_profiles}, indent=2, sort_keys=True), encoding="utf-8")


def aspect_profile_by_id(profile_id: str | None, profiles: Sequence[AspectProfile] | None = None) -> AspectProfile:
    available = list(profiles) if profiles is not None else load_aspect_profiles()
    for profile in available:
        if profile.id == profile_id:
            return profile
    return available[0] if available else default_aspect_profile()


def aspect_definition_signature(aspect_definitions: Iterable[Aspect | Mapping[str, object]] | None) -> tuple[tuple[object, ...], ...]:
    if aspect_definitions is None:
        aspects = ASPECTS
    else:
        aspects = tuple(
            item if isinstance(item, Aspect) else aspect_from_mapping(item)
            for item in aspect_definitions
        )
    return tuple(
        (
            aspect.id,
            aspect.name,
            float(aspect.angle),
            float(aspect.default_orb),
            aspect.tone,
            aspect.meaning,
            aspect.abbreviation,
            aspect.glyph,
            aspect.color,
            bool(aspect.enabled),
            bool(aspect.built_in),
        )
        for aspect in aspects
    )


def aspect_definitions_from_signature(signature: Iterable[tuple[object, ...]]) -> tuple[Aspect, ...]:
    aspects: list[Aspect] = []
    for item in signature:
        if len(item) < 11:
            continue
        aspects.append(
            Aspect(
                id=str(item[0]),
                name=str(item[1]),
                angle=float(item[2]),
                default_orb=float(item[3]),
                tone=str(item[4]),
                meaning=str(item[5]),
                abbreviation=str(item[6]),
                glyph=str(item[7]),
                color=str(item[8]),
                enabled=bool(item[9]),
                built_in=bool(item[10]),
            )
        )
    return tuple(aspects or ASPECTS)


def aspect_map_from_definitions(aspect_definitions: Iterable[Aspect | Mapping[str, object]] | None = None) -> dict[str, Aspect]:
    if aspect_definitions is None:
        return dict(ASPECT_BY_ID)
    return {
        aspect.id: aspect
        for aspect in (
            item if isinstance(item, Aspect) else aspect_from_mapping(item)
            for item in aspect_definitions
        )
    }


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
    aspect_definitions: Iterable[Aspect | Mapping[str, object]] | None = None,
) -> list[dict[str, object]]:
    aspect_map = aspect_map_from_definitions(aspect_definitions)
    selected = [
        aspect_map[aspect_id]
        for aspect_id in selected_aspect_ids
        if aspect_id in aspect_map and aspect_map[aspect_id].enabled
    ]
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
                            "aspectAbbreviation": aspect.abbreviation,
                            "aspectGlyph": aspect.glyph,
                            "aspectColor": aspect.color,
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
