"""Python chart builder for the server-rendered electional interface."""

from __future__ import annotations

from datetime import timedelta
from typing import Iterable

from .aspects import detect_aspects
from .ephemeris import ENGINE_NAME, format_zodiac_position, get_planet_positions
from .houses import calculate_angles, enrich_positions_with_houses
from .locations import LocationPreset
from .presets import apply_dignities, filter_positions_for_preset, get_preset
from .scoring import score_window
from .time_utils import format_in_timezone, zoned_time_to_utc

WINDOW_OFFSETS = (0, 2, 4, 6, 8, 10)


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
    return f"Strongest contact: {strongest['label']} with {strongest['orbText']} orb."


def build_snapshot(
    date_text: str,
    time_text: str,
    location: LocationPreset,
    preset_id: str,
    selected_aspects: Iterable[str] | None = None,
) -> dict[str, object]:
    preset = get_preset(preset_id)
    aspects = tuple(selected_aspects or preset.aspect_ids)
    moment = zoned_time_to_utc(date_text, time_text, location.timezone)
    angles = calculate_angles(moment, location.latitude, location.longitude)
    base_positions = enrich_positions_with_houses(get_planet_positions(moment), angles)
    positions = apply_dignities(base_positions, preset)
    detected = detect_aspects(filter_positions_for_preset(positions, preset), aspects, preset.aspect_orbs)

    return {
        "date": moment,
        "formattedTime": format_in_timezone(moment, location.timezone),
        "engine": ENGINE_NAME,
        "preset": preset,
        "angles": angles,
        "positions": positions,
        "detectedAspects": detected,
        "score": score_window(detected, positions, preset),
    }


def build_transit_windows(
    date_text: str,
    time_text: str,
    location: LocationPreset,
    preset_id: str,
    selected_aspects: Iterable[str] | None = None,
) -> list[dict[str, object]]:
    base_moment = zoned_time_to_utc(date_text, time_text, location.timezone)
    preset = get_preset(preset_id)
    aspects = tuple(selected_aspects or preset.aspect_ids)
    windows = []

    for offset in WINDOW_OFFSETS:
        moment = base_moment + timedelta(hours=offset)
        angles = calculate_angles(moment, location.latitude, location.longitude)
        base_positions = enrich_positions_with_houses(get_planet_positions(moment), angles)
        positions = apply_dignities(base_positions, preset)
        detected = detect_aspects(filter_positions_for_preset(positions, preset), aspects, preset.aspect_orbs)
        score = score_window(detected, positions, preset)
        windows.append(
            {
                "date": moment,
                "time": format_in_timezone(moment, location.timezone).split(", ", 1)[-1],
                "score": score,
                "title": "High-priority election" if score >= 76 else "Workable election" if score >= 60 else "Use with caution",
                "note": describe_window(detected, positions, preset),
                "angles": angles,
                "positions": positions,
                "detectedAspects": detected,
            }
        )

    return sorted(windows, key=lambda item: int(item["score"]), reverse=True)


def format_angle(angle: dict[str, object]) -> str:
    return f"{angle['shortName']} {format_zodiac_position(angle['zodiac'])}"


def format_position(planet: dict[str, object]) -> str:
    return format_zodiac_position(planet["zodiac"])
