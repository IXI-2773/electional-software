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
    minimum_confidence: int | None = None
    minimum_cleanliness: int | None = None
    maximum_volatility: int | None = None
    avoid_major_stress: bool = False
    require_applying_support: bool = False
    require_angular_benefic: bool = False
    avoid_angular_malefics: bool = False
    require_moon_non_void: bool = False
    avoid_objective_antipatterns: bool = False

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
DEFAULT_MINIMUM_CONFIDENCE = ""
DEFAULT_MINIMUM_CLEANLINESS = ""
DEFAULT_MAXIMUM_VOLATILITY = ""
SEARCH_PRESET_NAMES = (
    "Custom",
    "Strict Launch",
    "Clean Negotiation",
    "Safe Travel",
    "Conservative Money",
)


@dataclass(frozen=True)
class RejectionRecord:
    formatted_time: str
    score: int
    reasons: tuple[str, ...]


SEARCH_PRESET_OVERRIDES: dict[str, dict[str, object]] = {
    "Strict Launch": {
        "minimum_fit": "2",
        "minimum_confidence": "72",
        "minimum_cleanliness": "66",
        "maximum_volatility": "42",
        "require_applying_support": True,
        "require_angular_benefic": True,
        "avoid_major_stress": True,
        "avoid_angular_malefics": True,
        "avoid_objective_antipatterns": True,
    },
    "Clean Negotiation": {
        "minimum_fit": "1",
        "minimum_confidence": "74",
        "minimum_cleanliness": "74",
        "maximum_volatility": "32",
        "require_applying_support": True,
        "avoid_major_stress": True,
        "avoid_angular_malefics": True,
        "avoid_objective_antipatterns": True,
    },
    "Safe Travel": {
        "minimum_fit": "1",
        "minimum_confidence": "76",
        "minimum_cleanliness": "72",
        "maximum_volatility": "28",
        "require_applying_support": True,
        "require_moon_non_void": True,
        "avoid_major_stress": True,
        "avoid_angular_malefics": True,
        "avoid_objective_antipatterns": True,
    },
    "Conservative Money": {
        "minimum_fit": "1",
        "minimum_confidence": "78",
        "minimum_cleanliness": "75",
        "maximum_volatility": "30",
        "require_applying_support": True,
        "require_angular_benefic": True,
        "avoid_major_stress": True,
        "avoid_angular_malefics": True,
        "avoid_objective_antipatterns": True,
    },
}


def build_search_config_from_text(
    scan_hours_text: str,
    step_minutes_text: str,
    minimum_score_text: str = "",
    max_results_text: str = "",
    minimum_fit_text: str = "",
    avoid_major_stress: bool = False,
    require_applying_support: bool = False,
    require_angular_benefic: bool = False,
    avoid_angular_malefics: bool = False,
    require_moon_non_void: bool = False,
    avoid_objective_antipatterns: bool = False,
    minimum_confidence_text: str = "",
    minimum_cleanliness_text: str = "",
    maximum_volatility_text: str = "",
) -> SearchConfig:
    from .validation import validate_search_inputs

    errors = validate_search_inputs(
        scan_hours_text,
        step_minutes_text,
        minimum_score_text,
        max_results_text,
        minimum_fit_text,
        minimum_confidence_text,
        minimum_cleanliness_text,
        maximum_volatility_text,
    )
    if errors:
        raise ValueError("\n".join(errors))
    scan_hours = int(scan_hours_text.strip() or DEFAULT_SCAN_HOURS)
    step_minutes = int(step_minutes_text.strip() or DEFAULT_STEP_MINUTES)
    minimum_score = int(minimum_score_text.strip()) if minimum_score_text.strip() else None
    max_results = int(max_results_text.strip()) if max_results_text.strip() else None
    minimum_fit = int(minimum_fit_text.strip()) if minimum_fit_text.strip() else None
    minimum_confidence = int(minimum_confidence_text.strip()) if minimum_confidence_text.strip() else None
    minimum_cleanliness = int(minimum_cleanliness_text.strip()) if minimum_cleanliness_text.strip() else None
    maximum_volatility = int(maximum_volatility_text.strip()) if maximum_volatility_text.strip() else None
    return SearchConfig(
        end_offset_minutes=scan_hours * 60,
        step_minutes=step_minutes,
        minimum_score=minimum_score,
        max_results=max_results,
        minimum_fit=minimum_fit,
        minimum_confidence=minimum_confidence,
        minimum_cleanliness=minimum_cleanliness,
        maximum_volatility=maximum_volatility,
        avoid_major_stress=avoid_major_stress,
        require_applying_support=require_applying_support,
        require_angular_benefic=require_angular_benefic,
        avoid_angular_malefics=avoid_angular_malefics,
        require_moon_non_void=require_moon_non_void,
        avoid_objective_antipatterns=avoid_objective_antipatterns,
    )


def format_search_summary(config: SearchConfig) -> str:
    scan_hours = config.end_offset_minutes / 60
    scan_text = f"{scan_hours:.1f}h" if scan_hours % 1 else f"{int(scan_hours)}h"
    filters = []
    if config.minimum_score is not None:
        filters.append(f"score >= {config.minimum_score}")
    if config.minimum_fit is not None:
        filters.append(f"fit >= {config.minimum_fit}")
    if config.minimum_confidence is not None:
        filters.append(f"confidence >= {config.minimum_confidence}")
    if config.minimum_cleanliness is not None:
        filters.append(f"cleanliness >= {config.minimum_cleanliness}")
    if config.maximum_volatility is not None:
        filters.append(f"volatility <= {config.maximum_volatility}")
    if config.avoid_major_stress:
        filters.append("no major stress")
    if config.require_applying_support:
        filters.append("needs applying support")
    if config.require_angular_benefic:
        filters.append("needs angular benefic")
    if config.avoid_angular_malefics:
        filters.append("avoid angular malefics")
    if config.require_moon_non_void:
        filters.append("Moon non-void")
    if config.avoid_objective_antipatterns:
        filters.append("avoid anti-patterns")
    if config.max_results is not None:
        filters.append(f"top {config.max_results}")
    filter_text = "; " + ", ".join(filters) if filters else ""
    return f"Scan {scan_text} from start, every {config.step_minutes}m{filter_text}."


def search_preset_values(name: str) -> dict[str, object]:
    return dict(SEARCH_PRESET_OVERRIDES.get(name, {}))


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


def has_angular_benefic(window: dict[str, object]) -> bool:
    positions = window.get("positions", [])
    for planet in positions if isinstance(positions, list) else []:
        if not isinstance(planet, dict):
            continue
        if str(planet.get("name")) not in {"Venus", "Jupiter"} or not planet.get("isAngular"):
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


def _position_by_name(window: dict[str, object]) -> dict[str, dict[str, object]]:
    positions = window.get("positions", [])
    return {
        str(position.get("name")): position
        for position in positions
        if isinstance(position, dict)
    }


def objective_antipattern_notes(window: dict[str, object], objective: str | None) -> list[str]:
    objective_key = str(objective or window.get("objective") or "").lower()
    positions = _position_by_name(window)
    notes: list[str] = []
    mercury = positions.get("Mercury")
    venus = positions.get("Venus")
    jupiter = positions.get("Jupiter")

    if "launch" in objective_key or "publish" in objective_key:
        if not has_applying_support(window):
            notes.append("Launch windows work better with applying support already building.")
        if isinstance(mercury, dict) and mercury.get("isRetrograde"):
            notes.append("Mercury retrograde can muddy messaging, releases, or public rollout timing.")
        if has_angular_malefic(window):
            notes.append("Angular Mars or Saturn can weigh down visibility or create avoidable drag.")
    elif "meeting" in objective_key or "negotiation" in objective_key:
        if isinstance(mercury, dict) and mercury.get("isRetrograde"):
            notes.append("Mercury retrograde can complicate terms, revisions, and clear understanding.")
        if has_major_stress(window):
            notes.append("Tight stress can harden tone or make agreement more brittle.")
        if has_angular_malefic(window):
            notes.append("Angular malefics can make the room more combative or defensive.")
    elif "travel" in objective_key:
        if isinstance(mercury, dict) and mercury.get("isRetrograde"):
            notes.append("Mercury retrograde can increase itinerary changes, routing errors, or delays.")
        if not moon_is_non_void(window):
            notes.append("A void Moon can correlate with weak traction or drifting travel timing.")
        if has_major_stress(window):
            notes.append("Tight stress can raise disruption, pressure, or mechanical friction.")
    elif "money" in objective_key or "business" in objective_key:
        if isinstance(venus, dict) and venus.get("isRetrograde"):
            notes.append("Venus retrograde can weaken pricing, value perception, or agreement ease.")
        if isinstance(jupiter, dict) and jupiter.get("isRetrograde"):
            notes.append("Jupiter retrograde can slow expansion, approvals, or expected upside.")
        if has_major_stress(window):
            notes.append("Stressful conditions can increase downside, rework, or avoidable cost.")
        if has_angular_malefic(window):
            notes.append("Angular malefics can increase pressure on financial or business outcomes.")

    return notes


def fails_objective_antipattern(window: dict[str, object], objective: str | None = None) -> bool:
    return bool(objective_antipattern_notes(window, objective))


def diagnostic_score(window: dict[str, object], key: str, fallback: int = 0) -> int:
    breakdown = window.get("scoreBreakdown", {})
    if not isinstance(breakdown, dict):
        return fallback
    diagnostics = breakdown.get("diagnostics", {})
    if not isinstance(diagnostics, dict):
        return fallback
    metric = diagnostics.get(key, {})
    if not isinstance(metric, dict):
        return fallback
    try:
        return int(metric.get("score", fallback))
    except (TypeError, ValueError):
        return fallback


def rejection_reasons(window: dict[str, object], config: SearchConfig) -> list[str]:
    reasons: list[str] = []
    score = int(window.get("score", 0))
    fit = int(window.get("scoreBreakdown", {}).get("objectiveMatches", 0))
    confidence = diagnostic_score(window, "confidence")
    cleanliness = diagnostic_score(window, "cleanliness")
    volatility = diagnostic_score(window, "volatility", fallback=99)

    if config.minimum_score is not None and score < config.minimum_score:
        reasons.append(f"score {score} below minimum {config.minimum_score}")
    if config.minimum_fit is not None and fit < config.minimum_fit:
        reasons.append(f"fit {fit} below minimum {config.minimum_fit}")
    if config.minimum_confidence is not None and confidence < config.minimum_confidence:
        reasons.append(f"confidence {confidence} below minimum {config.minimum_confidence}")
    if config.minimum_cleanliness is not None and cleanliness < config.minimum_cleanliness:
        reasons.append(f"cleanliness {cleanliness} below minimum {config.minimum_cleanliness}")
    if config.maximum_volatility is not None and volatility > config.maximum_volatility:
        reasons.append(f"volatility {volatility} above maximum {config.maximum_volatility}")
    if config.avoid_major_stress and has_major_stress(window):
        reasons.append("major stress present")
    if config.require_applying_support and not has_applying_support(window):
        reasons.append("missing applying support")
    if config.require_angular_benefic and not has_angular_benefic(window):
        reasons.append("missing angular benefic")
    if config.avoid_angular_malefics and has_angular_malefic(window):
        reasons.append("angular malefic present")
    if config.require_moon_non_void and not moon_is_non_void(window):
        reasons.append("Moon is void or uncertain")
    if config.avoid_objective_antipatterns:
        for note in objective_antipattern_notes(window, str(window.get("objective") or "")):
            reasons.append(note)
    return reasons


def split_ranked_windows(
    windows: list[dict[str, object]],
    config: SearchConfig = DEFAULT_SEARCH_CONFIG,
) -> tuple[list[dict[str, object]], list[RejectionRecord]]:
    kept: list[dict[str, object]] = []
    rejected: list[RejectionRecord] = []
    for window in windows:
        reasons = rejection_reasons(window, config)
        if reasons:
            rejected.append(
                RejectionRecord(
                    formatted_time=str(window.get("formattedTime", "time unavailable")),
                    score=int(window.get("score", 0)),
                    reasons=tuple(reasons),
                )
            )
            continue
        kept.append(window)
    return kept, rejected


def rejection_summary(rejections: list[RejectionRecord]) -> dict[str, object]:
    counts: dict[str, int] = {}
    for rejected in rejections:
        for reason in rejected.reasons:
            counts[reason] = counts.get(reason, 0) + 1
    top_reasons = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return {
        "count": len(rejections),
        "topReasons": top_reasons[:6],
        "samples": [
            {
                "formattedTime": rejected.formatted_time,
                "score": rejected.score,
                "reasons": list(rejected.reasons[:3]),
            }
            for rejected in rejections[:5]
        ],
    }


def rank_search_windows(windows: list[dict[str, object]], config: SearchConfig = DEFAULT_SEARCH_CONFIG) -> list[dict[str, object]]:
    filtered, _rejections = split_ranked_windows(windows, config)
    ranked = sorted(
        filtered,
        key=lambda item: (
            int(item["score"]),
            diagnostic_score(item, "confidence"),
            diagnostic_score(item, "cleanliness"),
            diagnostic_score(item, "readiness"),
            -diagnostic_score(item, "volatility", fallback=99),
        ),
        reverse=True,
    )
    return ranked[: config.max_results] if config.max_results else ranked
