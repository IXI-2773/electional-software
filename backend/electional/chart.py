"""Python chart builder for the electional desktop and diagnostic interfaces."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Iterable, Mapping

from .accuracy import build_accuracy_audit
from .aspects import Aspect, aspect_definition_signature, aspect_definitions_from_signature, detect_aspects
from .angle_timing import annotate_angle_timings
from .constellations import annotate_points_with_constellations, chart_constellation_context
from .ephemeris import format_zodiac_position, get_ecliptic_coordinates, get_planet_positions, lunar_phase_from_positions
from .fixed_stars import detect_fixed_star_contacts, fixed_star_positions
from .houses import calculate_angles, calculate_house_cusps, enrich_positions_with_houses
from .judgment import DEFAULT_OBJECTIVE, build_judgment_contexts, fixed_star_context
from .locations import (
    INDIO_LATITUDE,
    INDIO_LONGITUDE,
    INDIO_TIMEZONE,
    LocationPreset,
    corrected_known_location,
    is_known_indio_name,
)
from .lots import calculate_lots
from .lunar_nodes import calculate_lunar_nodes
from .planetary_hours import planetary_hour_context
from .presets import apply_dignities, filter_positions_for_preset, get_preset
from .professional import calculation_backend_status
from .rules import evaluate_electional_rules
from .scoring import score_breakdown
from .search import (
    DEFAULT_SEARCH_CONFIG,
    SearchConfig,
    annotate_candidate_explanations,
    candidate_refinement_offsets,
    deep_candidate_count,
    fast_deep_candidates,
    rank_search_windows,
    rejection_summary,
    sort_search_windows,
    split_ranked_windows,
)
from .systems import ayanamsha_for_system, get_house_system, get_zodiac_system, zodiac_supports_traditional_rules
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


def build_location_validation_summary(location: LocationPreset, zodiac_system_id: str) -> dict[str, object]:
    corrected_location, corrected = corrected_known_location(location)
    notes: list[str] = []
    if corrected or is_known_indio_name(location.name):
        notes.append(
            f"Using corrected Indio coordinates {INDIO_LATITUDE:.4f}, {INDIO_LONGITUDE:.4f} ({INDIO_TIMEZONE})."
        )
    zodiac_system = get_zodiac_system(zodiac_system_id)
    if zodiac_system.mode == "constellational":
        notes.append("True 13-Sign zodiac is active; traditional dignity and rulership scoring is disabled.")
    notes.append("CapricornPROMETHEUS comparison is ready for an external exported chart, but no reference file is attached to this session yet.")
    return {
        "locationName": corrected_location.name,
        "latitude": corrected_location.latitude,
        "longitude": corrected_location.longitude,
        "timezone": corrected_location.timezone,
        "zodiacSystem": zodiac_system.name,
        "correctedKnownLocation": corrected or is_known_indio_name(location.name),
        "externalReferenceAvailable": False,
        "notes": notes,
    }


def build_snapshot_for_moment(
    moment: datetime,
    location: LocationPreset,
    preset: object,
    aspects: Iterable[str],
    zodiac_system_id: str = "tropical",
    house_system_id: str = "whole-sign",
    objective: str = DEFAULT_OBJECTIVE,
    calculation_mode: str = "full",
    aspect_definitions: Iterable[Aspect | Mapping[str, object]] | None = None,
) -> dict[str, object]:
    signature = aspect_definition_signature(aspect_definitions)
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
            signature,
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
    aspect_signature: tuple[tuple[object, ...], ...],
) -> dict[str, object]:
    moment = datetime.fromisoformat(moment_iso)
    location = LocationPreset(location_id, location_name, latitude, longitude, timezone)
    location, _known_location_corrected = corrected_known_location(location)
    preset = get_preset(preset_id)
    aspect_definitions = aspect_definitions_from_signature(aspect_signature)
    zodiac_system = get_zodiac_system(zodiac_system_id)
    house_system = get_house_system(house_system_id)
    traditional_rules_enabled = zodiac_supports_traditional_rules(zodiac_system.id)
    is_fast = calculation_mode == "fast"
    angles = annotate_points_with_constellations(calculate_angles(moment, location.latitude, location.longitude, zodiac_system.id))
    house_cusps = calculate_house_cusps(moment, location.latitude, location.longitude, zodiac_system.id, house_system.id, angles)
    base_positions = enrich_positions_with_houses(
        get_planet_positions(moment, zodiac_system.id, include_station_diagnostics=not is_fast),
        angles,
        house_system.id,
        house_cusps,
    )
    if not is_fast:
        base_positions = annotate_angle_timings(base_positions, moment, location, zodiac_system.id)
    positions = annotate_points_with_constellations(apply_dignities(base_positions, preset, enabled=traditional_rules_enabled))
    lunar_phase = lunar_phase_from_positions(positions)
    lots = [] if is_fast else calculate_lots(positions, angles, house_cusps, house_system.id, moment, zodiac_system.id)
    lunar_nodes = [] if is_fast else calculate_lunar_nodes(moment, zodiac_system.id, angles, house_cusps, house_system.id)
    longitude_cache: dict[tuple[str, datetime], float] = {}

    def resolve_longitude(body_name: str, sample_moment: datetime) -> float:
        key = (body_name, sample_moment)
        if key not in longitude_cache:
            longitude_cache[key] = float(get_ecliptic_coordinates(body_name, sample_moment)["longitude"])
        return longitude_cache[key]

    detected = detect_aspects(
        filter_positions_for_preset(positions, preset),
        aspects,
        preset.aspect_orbs,
        moment,
        location.timezone,
        None if is_fast else resolve_longitude,
        aspect_definitions,
    )
    timing = timing_profile(detected)
    fixed_stars = [] if is_fast else fixed_star_positions(moment, zodiac_system.id)
    fixed_star_contacts = [] if is_fast else detect_fixed_star_contacts([*positions, *angles], fixed_stars)
    fixed_star_judgment = fixed_star_context(fixed_star_contacts)
    planetary_hour = planetary_hour_context(moment, location)
    constellation_context = chart_constellation_context(moment, location, positions, angles)
    judgment_contexts = build_judgment_contexts(positions, angles, house_cusps, detected, lunar_phase, objective) if traditional_rules_enabled else {}
    rule_evaluations = evaluate_electional_rules(
        positions,
        lunar_phase,
        zodiac_system.id,
        planetary_hour,
        constellation_context,
        judgment_contexts,
        traditional_rules_enabled=traditional_rules_enabled,
    )
    breakdown = score_breakdown(detected, positions, preset, fixed_star_contacts, rule_evaluations, objective)
    diagnostics = breakdown.get("diagnostics", {}) if isinstance(breakdown, dict) else {}
    angle_context = diagnostics.get("angles", {}) if isinstance(diagnostics, dict) else {}
    backend_status = calculation_backend_status()
    location_validation = build_location_validation_summary(location, zodiac_system.id)
    accuracy_audit = (
        {
            "status": "not-run",
            "label": "Fast search estimate",
            "verified": False,
            "summary": "Accuracy audit is deferred until the candidate is deep-built.",
            "checks": [],
        }
        if is_fast
        else build_accuracy_audit(moment, location, positions, angles, house_cusps, house_system.id)
    )

    return {
        "date": moment,
        "formattedTime": format_in_timezone(moment, location.timezone),
        "calculationMode": calculation_mode,
        "engine": str(backend_status["activeEngine"]),
        "calculationBackend": backend_status,
        "accuracyAudit": accuracy_audit,
        "calculationNotes": calculation_notes(
            backend_status,
            house_system.id,
            house_cusps,
            location.latitude,
            planetary_hour,
            traditional_rules_enabled=traditional_rules_enabled,
            location_validation=location_validation,
            zodiac_system_name=zodiac_system.name,
        ),
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
        "locationValidation": location_validation,
        "traditionalRulesEnabled": traditional_rules_enabled,
        "objective": objective,
        **judgment_contexts,
        "timingProfile": timing,
        "ruleEvaluations": rule_evaluations,
        "detectedAspects": detected,
        "score": breakdown["score"],
        "scoreBreakdown": breakdown,
        "angleContext": angle_context if isinstance(angle_context, dict) else {},
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


def snapshot_to_window(
    snapshot: dict[str, object],
    location: LocationPreset,
    *,
    search_stage: str = "full",
    search_resolution_minutes: int | None = None,
) -> dict[str, object]:
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
            "searchStage": search_stage,
            "searchResolutionMinutes": search_resolution_minutes,
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
    aspect_definitions: Iterable[Aspect | Mapping[str, object]] | None = None,
) -> dict[str, object]:
    preset = get_preset(preset_id)
    aspects = tuple(selected_aspects or preset.aspect_ids)
    moment = zoned_time_to_utc(date_text, time_text, location.timezone)
    return build_snapshot_for_moment(moment, location, preset, aspects, zodiac_system_id, house_system_id, objective, aspect_definitions=aspect_definitions)


def calculation_notes(
    backend_status: dict[str, object],
    house_system_id: str,
    house_cusps: list[dict[str, object]],
    latitude: float | None = None,
    planetary_hour: dict[str, object] | None = None,
    *,
    traditional_rules_enabled: bool = True,
    location_validation: dict[str, object] | None = None,
    zodiac_system_name: str = "",
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
    if not traditional_rules_enabled:
        notes.append(
            f"{zodiac_system_name or 'True 13-Sign'} is active: traditional dignity, rulership, and classical rule scoring are disabled."
        )
    elif backend_status.get("swissPythonAvailable") and "sidereal" in (zodiac_system_name or "").lower():
        notes.append(f"{zodiac_system_name} ayanamsha is supplied by Swiss Ephemeris.")
    if isinstance(location_validation, dict):
        for note in location_validation.get("notes", []):
            notes.append(str(note))
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
    aspect_definitions: Iterable[Aspect | Mapping[str, object]] | None = None,
) -> list[dict[str, object]]:
    return list(
        build_election_report(
            date_text,
            time_text,
            location,
            preset_id,
            selected_aspects,
            zodiac_system_id,
            house_system_id,
            search_config,
            objective,
            aspect_definitions,
        )["windows"]
    )


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
    aspect_definitions: Iterable[Aspect | Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Build the input chart and ranked windows without recalculating the base moment twice."""

    base_moment = zoned_time_to_utc(date_text, time_text, location.timezone)
    preset = get_preset(preset_id)
    aspects = tuple(selected_aspects or preset.aspect_ids)
    snapshot = build_snapshot_for_moment(base_moment, location, preset, aspects, zodiac_system_id, house_system_id, objective, aspect_definitions=aspect_definitions)
    offsets = search_config.offsets()
    fast_deep_enabled = bool(search_config.max_results and len(offsets) > search_config.max_results)
    coarse_windows = []
    for offset_minutes in offsets:
        if offset_minutes == 0:
            coarse_windows.append(
                snapshot_to_window(
                    snapshot,
                    location,
                    search_stage="input",
                    search_resolution_minutes=search_config.step_minutes,
                )
            )
            continue
        calculation_mode = "fast" if fast_deep_enabled else "full"
        window_snapshot = build_snapshot_for_moment(
            base_moment + timedelta(minutes=offset_minutes),
            location,
            preset,
            aspects,
            zodiac_system_id,
            house_system_id,
            objective,
            calculation_mode,
            aspect_definitions,
        )
        coarse_windows.append(
            snapshot_to_window(
                window_snapshot,
                location,
                search_stage="coarse",
                search_resolution_minutes=search_config.step_minutes,
            )
        )

    refinement_offsets = candidate_refinement_offsets(coarse_windows, base_moment, search_config)
    refined_fast_windows = [
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
                aspect_definitions,
            ),
            location,
            search_stage="refined",
            search_resolution_minutes=search_config.refinement_step_minutes,
        )
        for offset_minutes in refinement_offsets
    ]

    if fast_deep_enabled:
        candidates, _preliminary_rejections = fast_deep_candidates(
            [*coarse_windows, *refined_fast_windows],
            search_config,
        )
    else:
        refinement_limit = max(
            8,
            (search_config.max_results or 0) * 2,
        )
        candidates = [
            *coarse_windows,
            *sort_search_windows(refined_fast_windows, search_config)[:refinement_limit],
        ]

    windows_by_date: dict[datetime, dict[str, object]] = {}
    for window in candidates:
        moment = window["date"]
        if moment in windows_by_date:
            continue
        if moment == snapshot["date"]:
            deep_window = snapshot_to_window(
                snapshot,
                location,
                search_stage=str(window.get("searchStage") or "input"),
                search_resolution_minutes=window.get("searchResolutionMinutes"),
            )
        elif window.get("calculationMode") == "full":
            deep_window = window
        else:
            deep_snapshot = build_snapshot_for_moment(
                moment,
                location,
                preset,
                aspects,
                zodiac_system_id,
                house_system_id,
                objective,
                "full",
                aspect_definitions,
            )
            deep_window = snapshot_to_window(
                deep_snapshot,
                location,
                search_stage=str(window.get("searchStage") or "refined"),
                search_resolution_minutes=window.get("searchResolutionMinutes"),
            )
        windows_by_date[moment] = deep_window

    windows = list(windows_by_date.values())
    kept, rejections = split_ranked_windows(windows, search_config)
    ranked = rank_search_windows(kept, search_config)
    if search_config.max_results is None:
        ranked = ranked[: len(offsets)]
    ranked = annotate_candidate_explanations(ranked, snapshot, search_config)
    refined_enabled = bool(refinement_offsets)
    search_mode = "fast/deep" if fast_deep_enabled else "full"
    if refined_enabled:
        search_mode += " + refined"

    return {
        "snapshot": snapshot,
        "windows": ranked,
        "rejections": rejections,
        "rejectionSummary": rejection_summary(rejections),
        "searchedWindowCount": len(offsets),
        "evaluatedWindowCount": len(offsets) + len(refinement_offsets),
        "refinedWindowCount": len(refinement_offsets),
        "deepWindowCount": len(windows),
        "matchedWindowCount": len(ranked),
        "searchMode": search_mode,
        "refinement": {
            "enabled": refined_enabled,
            "stepMinutes": search_config.refinement_step_minutes if refined_enabled else None,
            "seedCount": search_config.refinement_seed_count if refined_enabled else 0,
            "evaluatedOffsets": list(refinement_offsets),
        },
        "snapshotCache": snapshot_cache_info(),
    }


def format_angle(angle: dict[str, object]) -> str:
    return f"{angle['shortName']} {format_zodiac_position(angle['zodiac'])}"


def format_position(planet: dict[str, object]) -> str:
    return format_zodiac_position(planet["zodiac"])
