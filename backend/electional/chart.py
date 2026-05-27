"""Python chart builder for the electional desktop and diagnostic interfaces."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

from .aspects import detect_aspects
from .ephemeris import ENGINE_NAME, format_zodiac_position, get_planet_positions, lunar_phase_from_positions
from .houses import calculate_angles, calculate_house_cusps, enrich_positions_with_houses
from .locations import LocationPreset
from .lots import calculate_lots
from .presets import apply_dignities, filter_positions_for_preset, get_preset
from .scoring import score_breakdown
from .search import DEFAULT_SEARCH_CONFIG, SearchConfig, rank_search_windows
from .systems import ayanamsha_for_system, get_house_system, get_zodiac_system
from .time_utils import format_in_timezone, zoned_time_to_utc

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
    return f"Strongest contact: {strongest['label']} with {strongest['orbText']} orb, {phase}."


def build_snapshot_for_moment(
    moment: datetime,
    location: LocationPreset,
    preset: object,
    aspects: Iterable[str],
    zodiac_system_id: str = "tropical",
    house_system_id: str = "whole-sign",
) -> dict[str, object]:
    zodiac_system = get_zodiac_system(zodiac_system_id)
    house_system = get_house_system(house_system_id)
    angles = calculate_angles(moment, location.latitude, location.longitude, zodiac_system.id)
    house_cusps = calculate_house_cusps(moment, location.latitude, location.longitude, zodiac_system.id, house_system.id, angles)
    base_positions = enrich_positions_with_houses(get_planet_positions(moment, zodiac_system.id), angles, house_system.id, house_cusps)
    positions = apply_dignities(base_positions, preset)
    lunar_phase = lunar_phase_from_positions(positions)
    lots = calculate_lots(positions, angles, house_cusps, house_system.id)
    detected = detect_aspects(filter_positions_for_preset(positions, preset), aspects, preset.aspect_orbs)
    breakdown = score_breakdown(detected, positions, preset)

    return {
        "date": moment,
        "formattedTime": format_in_timezone(moment, location.timezone),
        "engine": ENGINE_NAME,
        "zodiacSystem": zodiac_system,
        "houseSystem": house_system,
        "houseCusps": house_cusps,
        "lots": lots,
        "ayanamsha": ayanamsha_for_system(moment, zodiac_system.id),
        "preset": preset,
        "angles": angles,
        "positions": positions,
        "lunarPhase": lunar_phase,
        "detectedAspects": detected,
        "score": breakdown["score"],
        "scoreBreakdown": breakdown,
    }


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
) -> dict[str, object]:
    preset = get_preset(preset_id)
    aspects = tuple(selected_aspects or preset.aspect_ids)
    moment = zoned_time_to_utc(date_text, time_text, location.timezone)
    return build_snapshot_for_moment(moment, location, preset, aspects, zodiac_system_id, house_system_id)


def build_transit_windows(
    date_text: str,
    time_text: str,
    location: LocationPreset,
    preset_id: str,
    selected_aspects: Iterable[str] | None = None,
    zodiac_system_id: str = "tropical",
    house_system_id: str = "whole-sign",
    search_config: SearchConfig = DEFAULT_SEARCH_CONFIG,
) -> list[dict[str, object]]:
    base_moment = zoned_time_to_utc(date_text, time_text, location.timezone)
    preset = get_preset(preset_id)
    aspects = tuple(selected_aspects or preset.aspect_ids)
    windows = []

    for offset_minutes in search_config.offsets():
        moment = base_moment + timedelta(minutes=offset_minutes)
        snapshot = build_snapshot_for_moment(moment, location, preset, aspects, zodiac_system_id, house_system_id)
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
) -> dict[str, object]:
    """Build the input chart and ranked windows without recalculating the base moment twice."""

    base_moment = zoned_time_to_utc(date_text, time_text, location.timezone)
    preset = get_preset(preset_id)
    aspects = tuple(selected_aspects or preset.aspect_ids)
    snapshot = build_snapshot_for_moment(base_moment, location, preset, aspects, zodiac_system_id, house_system_id)
    windows = []
    for offset_minutes in search_config.offsets():
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
        )
        windows.append(snapshot_to_window(window_snapshot, location))

    return {
        "snapshot": snapshot,
        "windows": rank_search_windows(windows, search_config),
    }


def format_angle(angle: dict[str, object]) -> str:
    return f"{angle['shortName']} {format_zodiac_position(angle['zodiac'])}"


def format_position(planet: dict[str, object]) -> str:
    return format_zodiac_position(planet["zodiac"])
