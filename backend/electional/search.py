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


def build_search_config_from_text(
    scan_hours_text: str,
    step_minutes_text: str,
    minimum_score_text: str = "",
    max_results_text: str = "",
) -> SearchConfig:
    from .validation import validate_search_inputs

    errors = validate_search_inputs(scan_hours_text, step_minutes_text, minimum_score_text, max_results_text)
    if errors:
        raise ValueError("\n".join(errors))
    scan_hours = int(scan_hours_text.strip() or DEFAULT_SCAN_HOURS)
    step_minutes = int(step_minutes_text.strip() or DEFAULT_STEP_MINUTES)
    minimum_score = int(minimum_score_text.strip()) if minimum_score_text.strip() else None
    max_results = int(max_results_text.strip()) if max_results_text.strip() else None
    return SearchConfig(
        end_offset_minutes=scan_hours * 60,
        step_minutes=step_minutes,
        minimum_score=minimum_score,
        max_results=max_results,
    )


def format_search_summary(config: SearchConfig) -> str:
    scan_hours = config.end_offset_minutes / 60
    scan_text = f"{scan_hours:.1f}h" if scan_hours % 1 else f"{int(scan_hours)}h"
    filters = []
    if config.minimum_score is not None:
        filters.append(f"score >= {config.minimum_score}")
    if config.max_results is not None:
        filters.append(f"top {config.max_results}")
    filter_text = "; " + ", ".join(filters) if filters else ""
    return f"Scan {scan_text} from start, every {config.step_minutes}m{filter_text}."


def rank_search_windows(windows: list[dict[str, object]], config: SearchConfig = DEFAULT_SEARCH_CONFIG) -> list[dict[str, object]]:
    filtered = [
        window
        for window in windows
        if config.minimum_score is None or int(window["score"]) >= config.minimum_score
    ]
    ranked = sorted(filtered, key=lambda item: int(item["score"]), reverse=True)
    return ranked[: config.max_results] if config.max_results else ranked
