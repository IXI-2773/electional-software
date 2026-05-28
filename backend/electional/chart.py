"""Python chart builder for the electional desktop and diagnostic interfaces."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Iterable

from .aspects import detect_aspects
from .constellations import annotate_points_with_constellations, chart_constellation_context
from .ephemeris import ENGINE_NAME, format_zodiac_position, get_planet_positions, lunar_phase_from_positions
from .fixed_stars import detect_fixed_star_contacts, fixed_star_positions
from .houses import calculate_angles, calculate_house_cusps, enrich_positions_with_houses
from .judgment import DEFAULT_OBJECTIVE, build_judgment_contexts, fixed_star_context
from .locations import LocationPreset
from .lots import calculate_lots
from .lunar_nodes import calculate_lunar_nodes
from .planetary_hours import planetary_hour_context
from .presets import apply_dignities, filter_positions_for_preset, get_preset
from .professional import calculation_backend_status
from .rules import evaluate_electional_rules
from .scoring import score_breakdown
from .search import DEFAULT_SEARCH_CONFIG, SearchConfig, fast_deep_candidates, rank_search_windows, rejection_summary, split_ranked_windows
from .systems import ayanamsha_for_system, get_house_system, get_zodiac_system
from .time_utils import format_in_timezone, zoned_time_to_utc
from .timing import timing_profile

def describe_window(detected_aspects: list[dict[str, object]], positions: list[dict[str, object]], preset: object) -> str:
    scoring_positions = filter_positions_for_preset(positions, preset)
    angular_bodies = [
        f"{planet['name']} near {planet['closestAngle']['shortName']}"
        for planet in scoring_positions
        if planet.get("isAngular")
    ]

    if angular_bodies:
        return f"Angular emphasis: {', '.join(angular_bodies[:2])}."

    if not detected_aspects:
        return "Quiet window with no selected major aspects in orb."

    strongest = detected_aspects[0]
    phase = str(strongest.get("phaseLabel") or "phase unknown").lower()
    if strongest.get("isApplying") and strongest.get("timeToExactText"):
        return f"Strongest contact: {strongest['label']} with {strongest['orbText']} orb, {phase}; exact in {strongest['timeToExactText']}."
    return f"Strongest contact: {strongest['label']} with {strongest['orbText']} orb, {phase}."


def build_snapshot_for_moment(
    moment: datetime,
    location: LocationPreset,
    preset: object,
    aspects: Iterable[str],
    zodiac_system_id: str = "tropical",
    house_system_id: str = "whole-sign",
    objective: str = DEFAULT_OBJECTIVE,
    calculation_mode: str = "full",
) -> dict[str, object]:
    return deepcopy(
        _cached_snapshot_for_moment(
            moment.isoformat(),
            location.id,
            location.name,
            float(location.latitude),
            float(location.longitude),
            location.timezone,
            str(preset.id),
            tuple(aspects),
            zodiac_system_id,
            house_system_id,
            objective,
            calculation_mode,
        )
    )


@lru_cache(maxsize=768)
def _cached_snapshot_for_moment(
    moment_iso: str,
    location_id: str,
    location_name: str,
    latitude: float,
    longitude: float,
    timezone: str,
    preset_id: str,
    aspects: tuple[str, ...],
    zodiac_system_id: str,
    house_system_id: str,
    objective: str,
    calculation_mode: str,
) -> dict[str, object]:
    moment = datetime.fromisoformat(moment_iso)
    location = LocationPreset(location_id, location_name, latitude, longitude, timezone)
    preset = get_preset(preset_id)
    zodiac_system = get_zodiac_system(zodiac_system_id)
    house_system = get_house_system(house_system_id)
    is_fast = calculation_mode == "fast"
    angles = annotate_points_with_constellations(calculate_angles(moment, location.latitude, location.longitude, zodiac_system.id))
    house_cusps = calculate_house_cusps(moment, location.latitude, location.longitude, zodiac_system.id, house_system.id, angles)
    base_positions = enrich_positions_with_houses(
        get_planet_positions(moment, zodiac_system.id, include_station_diagnostics=not is_fast),
        angles,
        house_system.id,
        house_cusps,
    )
    positions = annotate_points_with_constellations(apply_dignities(base_positions, preset))
    lunar_phase = lunar_phase_from_positions(positions)
    lots = [] if is_fast else calculate_lots(positions, angles, house_cusps, house_system.id)
    lunar_nodes = [] if is_fast else calculate_lunar_nodes(moment, zodiac_system.id, angles, house_cusps, house_system.id)
    detected = detect_aspects(filter_positions_for_preset(positions, preset), aspects, preset.aspect_orbs, moment, location.timezone)
    timing = timing_profile(detected)
    fixed_stars = [] if is_fast else fixed_star_positions(moment, zodiac_system.id)
    fixed_star_contacts = [] if is_fast else detect_fixed_star_contacts([*positions, *angles], fixed_stars)
    fixed_star_judgment = fixed_star_context(fixed_star_contacts)
    planetary_hour = planetary_hour_context(moment, location)
    constellation_context = chart_constellation_context(moment, location, positions, angles)
    judgment_contexts = build_judgment_contexts(positions, angles, house_cusps, detected, lunar_phase, objective)
    rule_evaluations = evaluate_electional_rules(
        positions,
        lunar_phase,
        zodiac_system.id,
        planetary_hour,
        constellation_context,
        judgment_contexts,
    )
    breakdown = score_breakdown(detected, positions, preset, fixed_star_contacts, rule_evaluations, objective)
    backend_status = calculation_backend_status()

    return {
        "date": moment,
        "formattedTime": format_in_timezone(moment, location.timezone),
        "calculationMode": calculation_mode,
        "engine": ENGINE_NAME,
        "calculationBackend": backend_status,
        "calculationNotes": calculation_notes(backend_status, house_system.id, house_cusps, location.latitude, planetary_hour),
        "zodiacSystem": zodiac_system,
        "houseSystem": house_system,
        "houseCusps": house_cusps,
        "lots": lots,
        "lunarNodes": lunar_nodes,
        "fixedStars": fixed_stars,
        "fixedStarContacts": fixed_star_contacts,
        "fixedStarContext": fixed_star_judgment,
        "ayanamsha": ayanamsha_for_system(moment, zodiac_system.id),
        "preset": preset,
        "angles": angles,
        "positions": positions,
        "lunarPhase": lunar_phase,
        "planetaryHour": planetary_hour,
        "constellationContext": constellation_context,
        "objective": objective,
        **judgment_contexts,
        "timingProfile": timing,
        "ruleEvaluations": rule_evaluations,
        "detectedAspects": detected,
        "score": breakdown["score"],
        "scoreBreakdown": breakdown,
    }


def snapshot_cache_info() -> dict[str, int]:
    info = _cached_snapshot_for_moment.cache_info()
    return {
        "hits": info.hits,
        "misses": info.misses,
        "maxsize": int(info.maxsize or 0),
        "currsize": info.currsize,
    }


def clear_snapshot_cache() -> None:
    _cached_snapshot_for_moment.cache_clear()


def snapshot_to_window(snapshot: dict[str, object], location: LocationPreset) -> dict[str, object]:
    detected = snapshot["detectedAspects"]
    positions = snapshot["positions"]
    preset = snapshot["preset"]
    score = int(snapshot["score"])
    window = dict(snapshot)
    window.update(
        {
            "time": format_in_timezone(snapshot["date"], location.timezone).split(", ", 1)[-1],
            "title": "High-priority election" if score >= 76 else "Workable election" if score >= 60 else "Use with caution",
            "note": describe_window(detected, positions, preset),
        }
    )
    return window


def build_snapshot(
    date_text: str,
    time_text: str,
    location: LocationPreset,
    preset_id: str,
    selected_aspects: Iterable[str] | None = None,
    zodiac_system_id: str = "tropical",
    house_system_id: str = "whole-sign",
    objective: str = DEFAULT_OBJECTIVE,
) -> dict[str, object]:
    preset = get_preset(preset_id)
    aspects = tuple(selected_aspects or preset.aspect_ids)
    moment = zoned_time_to_utc(date_text, time_text, location.timezone)
    return build_snapshot_for_moment(moment, location, preset, aspects, zodiac_system_id, house_system_id, objective)


def calculation_notes(
    backend_status: dict[str, object],
    house_system_id: str,
    house_cusps: list[dict[str, object]],
    latitude: float | None = None,
    planetary_hour: dict[str, object] | None = None,
) -> list[str]:
    notes = []
    if backend_status.get("fallbackActive"):
        notes.append("Swiss Ephemeris Python bindings are not active; planetary positions use Astronomy Engine fallback.")
    cusp_sources = sorted({str(cusp.get("source")) for cusp in house_cusps if cusp.get("source")})
    if cusp_sources:
        notes.append(f"House cusps source for {house_system_id}: {', '.join(cusp_sources)}.")
    if latitude is not None and abs(latitude) >= 60:
        notes.append("High-latitude chart: sunrise/sunset, quadrant cusps, and planetary-hour timing may need extra review.")
    if planetary_hour and not planetary_hour.get("available"):
        notes.append(f"Planetary hour unavailable: {planetary_hour.get('reason', 'sunrise/sunset could not be resolved')}.")
    return notes


def build_transit_windows(
    date_text: str,
    time_text: str,
    location: LocationPreset,
    preset_id: str,
    selected_aspects: Iterable[str] | None = None,
    zodiac_system_id: str = "tropical",
    house_system_id: str = "whole-sign",
    search_config: SearchConfig = DEFAULT_SEARCH_CONFIG,
    objective: str = DEFAULT_OBJECTIVE,
) -> list[dict[str, object]]:
    base_moment = zoned_time_to_utc(date_text, time_text, location.timezone)
    preset = get_preset(preset_id)
    aspects = tuple(selected_aspects or preset.aspect_ids)
    offsets = search_config.offsets()
    if search_config.max_results and len(offsets) > search_config.max_results:
        fast_windows = [
            snapshot_to_window(
                build_snapshot_for_moment(
                    base_moment + timedelta(minutes=offset_minutes),
                    location,
                    preset,
                    aspects,
                    zodiac_system_id,
                    house_system_id,
                    objective,
                    "fast",
                ),
                location,
            )
            for offset_minutes in offsets
        ]
        candidates, _rejections = fast_deep_candidates(fast_windows, search_config)
        deep_windows = [
            snapshot_to_window(
                build_snapshot_for_moment(
                    window["date"],
                    location,
                    preset,
                    aspects,
                    zodiac_system_id,
                    house_system_id,
                    objective,
                    "full",
                ),
                location,
            )
            for window in candidates
        ]
        return rank_search_windows(deep_windows, search_config)

    windows = []

    for offset_minutes in offsets:
        moment = base_moment + timedelta(minutes=offset_minutes)
        snapshot = build_snapshot_for_moment(moment, location, preset, aspects, zodiac_system_id, house_system_id, objective)
        windows.append(snapshot_to_window(snapshot, location))

    return rank_search_windows(windows, search_config)


def build_election_report(
    date_text: str,
    time_text: str,
    location: LocationPreset,
    preset_id: str,
    selected_aspects: Iterable[str] | None = None,
    zodiac_system_id: str = "tropical",
    house_system_id: str = "whole-sign",
    search_config: SearchConfig = DEFAULT_SEARCH_CONFIG,
    objective: str = DEFAULT_OBJECTIVE,
) -> dict[str, object]:
    """Build the input chart and ranked windows without recalculating the base moment twice."""

    base_moment = zoned_time_to_utc(date_text, time_text, location.timezone)
    preset = get_preset(preset_id)
    aspects = tuple(selected_aspects or preset.aspect_ids)
    snapshot = build_snapshot_for_moment(base_moment, location, preset, aspects, zodiac_system_id, house_system_id, objective)
    offsets = search_config.offsets()
    fast_deep_enabled = bool(search_config.max_results and len(offsets) > search_config.max_results)
    if fast_deep_enabled:
        fast_windows = []
        for offset_minutes in offsets:
            if offset_minutes == 0:
                fast_windows.append(snapshot_to_window(snapshot, location))
                continue
            fast_snapshot = build_snapshot_for_moment(
                base_moment + timedelta(minutes=offset_minutes),
                location,
                preset,
                aspects,
                zodiac_system_id,
                house_system_id,
                objective,
                "fast",
            )
            fast_windows.append(snapshot_to_window(fast_snapshot, location))
        candidates, rejections = fast_deep_candidates(fast_windows, search_config)
        windows = []
        for window in candidates:
            if window["date"] == snapshot["date"]:
                windows.append(snapshot_to_window(snapshot, location))
                continue
            deep_snapshot = build_snapshot_for_moment(
                window["date"],
                location,
                preset,
                aspects,
                zodiac_system_id,
                house_system_id,
                objective,
                "full",
            )
            windows.append(snapshot_to_window(deep_snapshot, location))
        ranked = rank_search_windows(windows, search_config)
    else:
        windows = []
        for offset_minutes in offsets:
            if offset_minutes == 0:
                windows.append(snapshot_to_window(snapshot, location))
                continue
            window_snapshot = build_snapshot_for_moment(
                base_moment + timedelta(minutes=offset_minutes),
                location,
                preset,
                aspects,
                zodiac_system_id,
                house_system_id,
                objective,
            )
            windows.append(snapshot_to_window(window_snapshot, location))
        ranked, rejections = split_ranked_windows(windows, search_config)
        ranked = rank_search_windows(windows, search_config)

    return {
        "snapshot": snapshot,
        "windows": ranked,
        "rejections": rejections,
        "rejectionSummary": rejection_summary(rejections),
        "searchedWindowCount": len(offsets),
        "deepWindowCount": len(windows),
        "matchedWindowCount": len(ranked),
        "searchMode": "fast/deep" if fast_deep_enabled else "full",
        "snapshotCache": snapshot_cache_info(),
    }


def format_angle(angle: dict[str, object]) -> str:
    return f"{angle['shortName']} {format_zodiac_position(angle['zodiac'])}"


def format_position(planet: dict[str, object]) -> str:
    return format_zodiac_position(planet["zodiac"])
