"""Configurable electional window search."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchConfig:
    start_offset_minutes: int = 0
    end_offset_minutes: int = 600
    step_minutes: int = 120
    max_results: int | None = None
    minimum_score: int | None = None
    minimum_fit: int | None = None
    avoid_major_stress: bool = False
    require_applying_support: bool = False
    avoid_angular_malefics: bool = False
    require_moon_non_void: bool = False

    def offsets(self) -> tuple[int, ...]:
        if self.step_minutes <= 0:
            raise ValueError("Search step must be greater than zero minutes.")
        if self.end_offset_minutes < self.start_offset_minutes:
            raise ValueError("Search end must be at or after search start.")
        return tuple(range(self.start_offset_minutes, self.end_offset_minutes + 1, self.step_minutes))


DEFAULT_SEARCH_CONFIG = SearchConfig()
DEFAULT_SCAN_HOURS = str(DEFAULT_SEARCH_CONFIG.end_offset_minutes // 60)
DEFAULT_STEP_MINUTES = str(DEFAULT_SEARCH_CONFIG.step_minutes)
DEFAULT_MAX_RESULTS = ""
DEFAULT_MINIMUM_SCORE = ""
DEFAULT_MINIMUM_FIT = ""


def build_search_config_from_text(
    scan_hours_text: str,
    step_minutes_text: str,
    minimum_score_text: str = "",
    max_results_text: str = "",
    minimum_fit_text: str = "",
    avoid_major_stress: bool = False,
    require_applying_support: bool = False,
    avoid_angular_malefics: bool = False,
    require_moon_non_void: bool = False,
) -> SearchConfig:
    from .validation import validate_search_inputs

    errors = validate_search_inputs(scan_hours_text, step_minutes_text, minimum_score_text, max_results_text, minimum_fit_text)
    if errors:
        raise ValueError("\n".join(errors))
    scan_hours = int(scan_hours_text.strip() or DEFAULT_SCAN_HOURS)
    step_minutes = int(step_minutes_text.strip() or DEFAULT_STEP_MINUTES)
    minimum_score = int(minimum_score_text.strip()) if minimum_score_text.strip() else None
    max_results = int(max_results_text.strip()) if max_results_text.strip() else None
    minimum_fit = int(minimum_fit_text.strip()) if minimum_fit_text.strip() else None
    return SearchConfig(
        end_offset_minutes=scan_hours * 60,
        step_minutes=step_minutes,
        minimum_score=minimum_score,
        max_results=max_results,
        minimum_fit=minimum_fit,
        avoid_major_stress=avoid_major_stress,
        require_applying_support=require_applying_support,
        avoid_angular_malefics=avoid_angular_malefics,
        require_moon_non_void=require_moon_non_void,
    )


def format_search_summary(config: SearchConfig) -> str:
    scan_hours = config.end_offset_minutes / 60
    scan_text = f"{scan_hours:.1f}h" if scan_hours % 1 else f"{int(scan_hours)}h"
    filters = []
    if config.minimum_score is not None:
        filters.append(f"score >= {config.minimum_score}")
    if config.minimum_fit is not None:
        filters.append(f"fit >= {config.minimum_fit}")
    if config.avoid_major_stress:
        filters.append("no major stress")
    if config.require_applying_support:
        filters.append("needs applying support")
    if config.avoid_angular_malefics:
        filters.append("avoid angular malefics")
    if config.require_moon_non_void:
        filters.append("Moon non-void")
    if config.max_results is not None:
        filters.append(f"top {config.max_results}")
    filter_text = "; " + ", ".join(filters) if filters else ""
    return f"Scan {scan_text} from start, every {config.step_minutes}m{filter_text}."


def has_major_stress(window: dict[str, object]) -> bool:
    aspects = window.get("detectedAspects", [])
    for aspect in aspects if isinstance(aspects, list) else []:
        if not isinstance(aspect, dict) or aspect.get("tone") != "stress":
            continue
        orb = float(aspect.get("orb", 99))
        if aspect.get("isApplying") and orb <= 2.0:
            return True
        if orb <= 1.0:
            return True
    positions = window.get("positions", [])
    for planet in positions if isinstance(positions, list) else []:
        if not isinstance(planet, dict):
            continue
        if str(planet.get("name")) in {"Mars", "Saturn"} and planet.get("isAngular"):
            closest = planet.get("closestAngle", {})
            if isinstance(closest, dict) and float(closest.get("distance", 99)) <= 3.0:
                return True
    return False


def has_applying_support(window: dict[str, object]) -> bool:
    aspects = window.get("detectedAspects", [])
    return any(
        isinstance(aspect, dict)
        and aspect.get("tone") == "support"
        and aspect.get("isApplying")
        for aspect in (aspects if isinstance(aspects, list) else [])
    )


def has_angular_malefic(window: dict[str, object]) -> bool:
    positions = window.get("positions", [])
    for planet in positions if isinstance(positions, list) else []:
        if not isinstance(planet, dict):
            continue
        if str(planet.get("name")) not in {"Mars", "Saturn"} or not planet.get("isAngular"):
            continue
        closest = planet.get("closestAngle", {})
        if isinstance(closest, dict) and float(closest.get("distance", 99)) <= 8.0:
            return True
    return False


def moon_is_non_void(window: dict[str, object]) -> bool:
    moon_condition = window.get("moonCondition", {})
    if not isinstance(moon_condition, dict):
        return True
    void_data = moon_condition.get("voidOfCourse", {})
    if not isinstance(void_data, dict):
        return True
    return not bool(void_data.get("isVoid"))


def rank_search_windows(windows: list[dict[str, object]], config: SearchConfig = DEFAULT_SEARCH_CONFIG) -> list[dict[str, object]]:
    filtered = [
        window
        for window in windows
        if (config.minimum_score is None or int(window["score"]) >= config.minimum_score)
        and (
            config.minimum_fit is None
            or int(window.get("scoreBreakdown", {}).get("objectiveMatches", 0)) >= config.minimum_fit
        )
        and (not config.avoid_major_stress or not has_major_stress(window))
        and (not config.require_applying_support or has_applying_support(window))
        and (not config.avoid_angular_malefics or not has_angular_malefic(window))
        and (not config.require_moon_non_void or moon_is_non_void(window))
    ]
    ranked = sorted(filtered, key=lambda item: int(item["score"]), reverse=True)
    return ranked[: config.max_results] if config.max_results else ranked
