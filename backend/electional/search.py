"""Configurable electional window search."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

SEARCH_QUALITY_MODES: dict[str, str] = {
    "balanced": "Balanced",
    "highest-score": "Highest Score",
    "cleanest": "Cleanest",
    "low-risk": "Low Risk",
    "moon-safe": "Moon Safe",
    "angular-support": "Angular Support",
}
SEARCH_QUALITY_MODE_NAMES = tuple(SEARCH_QUALITY_MODES.values())
SEARCH_QUALITY_MODE_IDS_BY_NAME = {name: mode_id for mode_id, name in SEARCH_QUALITY_MODES.items()}
DEFAULT_SEARCH_QUALITY_MODE = "balanced"


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
    quality_mode: str = DEFAULT_SEARCH_QUALITY_MODE
    refine_candidates: bool = True
    refinement_step_minutes: int = 10
    refinement_seed_count: int = 4

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
    search_quality_mode_text: str = "",
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
    quality_mode = normalize_search_quality_mode(search_quality_mode_text)
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
        quality_mode=quality_mode,
    )


def normalize_search_quality_mode(value: str | None) -> str:
    candidate = str(value or "").strip()
    if not candidate:
        return DEFAULT_SEARCH_QUALITY_MODE
    lowered = candidate.lower()
    if lowered in SEARCH_QUALITY_MODES:
        return lowered
    if candidate in SEARCH_QUALITY_MODE_IDS_BY_NAME:
        return SEARCH_QUALITY_MODE_IDS_BY_NAME[candidate]
    safe = lowered.replace("_", "-").replace(" ", "-")
    return safe if safe in SEARCH_QUALITY_MODES else DEFAULT_SEARCH_QUALITY_MODE


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
    mode_label = SEARCH_QUALITY_MODES.get(normalize_search_quality_mode(config.quality_mode), SEARCH_QUALITY_MODES[DEFAULT_SEARCH_QUALITY_MODE])
    filters.append(f"rank: {mode_label}")
    if config.refine_candidates and config.step_minutes > config.refinement_step_minutes:
        filters.append(f"refine leaders to {config.refinement_step_minutes}m")
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
        "suggestedRelaxations": rejection_relaxation_suggestions(top_reasons),
        "samples": [
            {
                "formattedTime": rejected.formatted_time,
                "score": rejected.score,
                "reasons": list(rejected.reasons[:3]),
            }
            for rejected in rejections[:5]
        ],
    }


def rejection_relaxation_suggestions(top_reasons: list[tuple[str, int]]) -> list[str]:
    suggestions: list[str] = []
    for reason, _count in top_reasons:
        lowered = reason.lower()
        suggestion = ""
        if "missing applying support" in lowered:
            suggestion = "Try disabling Require applying support, or widen the scan until applying support appears."
        elif "launch windows work better" in lowered:
            suggestion = "For launch work, widen the scan before dropping objective anti-pattern checks."
        elif "missing angular benefic" in lowered:
            suggestion = "Relax Require angular benefic if clean timing matters more than angular Venus/Jupiter."
        elif "cleanliness" in lowered and "below minimum" in lowered:
            suggestion = "Lower Min cleanliness by 5-10 points to inspect near-miss candidates."
        elif "volatility" in lowered and "above maximum" in lowered:
            suggestion = "Raise Max volatility slightly, then compare the added windows for stress."
        elif "confidence" in lowered and "below minimum" in lowered:
            suggestion = "Lower Min confidence if the aspect pattern is otherwise useful."
        elif "major stress present" in lowered:
            suggestion = "Keep No major stress for final picks, but temporarily disable it to see nearby tradeoffs."
        elif "angular malefic" in lowered:
            suggestion = "Avoid angular malefics for conservative picks; relax it only when the candidate has strong offsetting support."
        elif "moon is void" in lowered:
            suggestion = "Keep Moon non-void for important launches; widen the scan past the void period."
        elif "fit" in lowered and "below minimum" in lowered:
            suggestion = "Lower Minimum fit or switch objective if the chart is being judged against the wrong goal."
        elif "score" in lowered and "below minimum" in lowered:
            suggestion = "Lower Minimum score temporarily, then use confidence/cleanliness to choose."
        if suggestion and suggestion not in suggestions:
            suggestions.append(suggestion)
        if len(suggestions) >= 4:
            break
    return suggestions


def sort_search_windows(
    windows: list[dict[str, object]],
    config: SearchConfig = DEFAULT_SEARCH_CONFIG,
) -> list[dict[str, object]]:
    return sorted(
        windows,
        key=lambda item: search_rank_tuple(item, config),
        reverse=True,
    )


def search_rank_tuple(window: dict[str, object], config: SearchConfig = DEFAULT_SEARCH_CONFIG) -> tuple[float, ...]:
    mode = normalize_search_quality_mode(config.quality_mode)
    score = int(window.get("score", 0))
    quality = search_quality_index(window, mode)
    confidence = diagnostic_score(window, "confidence")
    cleanliness = diagnostic_score(window, "cleanliness")
    readiness = diagnostic_score(window, "readiness")
    volatility = diagnostic_score(window, "volatility", fallback=99)
    support = _aspect_count(window, "support", applying_only=True)
    stress = _aspect_count(window, "stress", applying_only=True)
    angular_benefic = 1 if has_angular_benefic(window) else 0
    angular_malefic = 1 if has_angular_malefic(window) else 0
    moon_safe = 1 if moon_is_non_void(window) else 0
    major_stress = 1 if has_major_stress(window) else 0
    if mode == "highest-score":
        return (score, quality, confidence, cleanliness, readiness, -volatility, -stress)
    if mode == "cleanest":
        return (cleanliness, confidence, -volatility, -major_stress, score, support, -stress)
    if mode == "low-risk":
        return (-major_stress, -angular_malefic, -stress, -volatility, cleanliness, confidence, score)
    if mode == "moon-safe":
        return (moon_safe, _moon_condition_score(window), cleanliness, confidence, -volatility, score, quality)
    if mode == "angular-support":
        return (angular_benefic, -angular_malefic, _angular_support_score(window), support, score, quality)
    return (score, quality, confidence, cleanliness, readiness, -volatility, support, -stress)


def _aspect_count(window: dict[str, object], tone: str, *, applying_only: bool = False) -> int:
    aspects = window.get("detectedAspects", [])
    if not isinstance(aspects, list):
        return 0
    return sum(
        1
        for aspect in aspects
        if isinstance(aspect, dict)
        and aspect.get("tone") == tone
        and (not applying_only or bool(aspect.get("isApplying")))
    )


def _moon_condition_score(window: dict[str, object]) -> int:
    moon = next((item for item in window.get("positions", []) if isinstance(item, dict) and item.get("name") == "Moon"), None)
    score = 10 if moon_is_non_void(window) else -10
    if isinstance(moon, dict):
        if moon.get("isAngular"):
            score += 3
        dignity = moon.get("dignity", {})
        if isinstance(dignity, dict):
            try:
                score += int(float(dignity.get("score", 0)))
            except (TypeError, ValueError):
                pass
    return score


def _angular_support_score(window: dict[str, object]) -> int:
    positions = window.get("positions", [])
    score = 0
    if not isinstance(positions, list):
        return score
    for planet in positions:
        if not isinstance(planet, dict) or not planet.get("isAngular"):
            continue
        name = str(planet.get("name") or "")
        if name in {"Venus", "Jupiter", "Sun", "Moon"}:
            score += 4
        elif name in {"Mars", "Saturn"}:
            score -= 5
        else:
            score += 1
    return score


def search_quality_index(window: dict[str, object], mode: str | None = None) -> float:
    mode = normalize_search_quality_mode(mode)
    breakdown = window.get("scoreBreakdown", {})
    raw_score = float(breakdown.get("rawScore", window.get("score", 0))) if isinstance(breakdown, dict) else float(window.get("score", 0))
    confidence = diagnostic_score(window, "confidence")
    cleanliness = diagnostic_score(window, "cleanliness")
    readiness = diagnostic_score(window, "readiness")
    volatility = diagnostic_score(window, "volatility", fallback=99)
    applying_support = sum(
        1
        for aspect in window.get("detectedAspects", [])
        if isinstance(aspect, dict) and aspect.get("tone") == "support" and aspect.get("isApplying")
    )
    applying_stress = sum(
        1
        for aspect in window.get("detectedAspects", [])
        if isinstance(aspect, dict) and aspect.get("tone") == "stress" and aspect.get("isApplying")
    )
    quality = (
        raw_score
        + confidence * 0.08
        + cleanliness * 0.06
        + readiness * 0.04
        - volatility * 0.05
        + applying_support * 1.5
        - applying_stress * 1.5
    )
    if mode == "cleanest":
        quality += cleanliness * 0.16 + confidence * 0.06 - volatility * 0.12
    elif mode == "low-risk":
        quality += cleanliness * 0.10 - volatility * 0.20 - applying_stress * 2.0
        quality -= 6.0 if has_major_stress(window) else 0.0
        quality -= 5.0 if has_angular_malefic(window) else 0.0
    elif mode == "moon-safe":
        quality += _moon_condition_score(window) * 0.75
    elif mode == "angular-support":
        quality += _angular_support_score(window) * 0.95
    elif mode == "highest-score":
        quality += float(window.get("score", 0)) * 0.08
    return round(quality, 3)


def candidate_explanation_lines(
    window: dict[str, object],
    baseline: dict[str, object] | None = None,
    config: SearchConfig = DEFAULT_SEARCH_CONFIG,
) -> list[str]:
    mode = normalize_search_quality_mode(config.quality_mode)
    breakdown = window.get("scoreBreakdown", {})
    diagnostics = breakdown.get("diagnostics", {}) if isinstance(breakdown, dict) else {}
    support = _aspect_count(window, "support")
    stress = _aspect_count(window, "stress")
    applying_support = _aspect_count(window, "support", applying_only=True)
    applying_stress = _aspect_count(window, "stress", applying_only=True)
    lines = [
        f"Rank mode: {SEARCH_QUALITY_MODES.get(mode, 'Balanced')}; quality index {search_quality_index(window, mode):.1f}.",
        f"Aspect balance: {support} support / {stress} stress; applying {applying_support} support / {applying_stress} stress.",
    ]
    if isinstance(diagnostics, dict):
        cleanliness = diagnostic_score(window, "cleanliness")
        confidence = diagnostic_score(window, "confidence")
        volatility = diagnostic_score(window, "volatility", fallback=99)
        readiness = diagnostic_score(window, "readiness")
        lines.append(f"Diagnostics: confidence {confidence}, cleanliness {cleanliness}, readiness {readiness}, volatility {volatility}.")
    if baseline and isinstance(baseline.get("score"), int | float):
        try:
            delta = int(window.get("score", 0)) - int(baseline.get("score", 0))
            sign = "+" if delta >= 0 else ""
            lines.append(f"Compared with search start: {sign}{delta} score points.")
        except (TypeError, ValueError):
            pass
    if has_angular_benefic(window):
        lines.append("Angular benefic support is present.")
    if has_angular_malefic(window):
        lines.append("Angular malefic pressure needs review.")
    if not moon_is_non_void(window):
        lines.append("Moon is void or uncertain; timing may lack traction.")
    elif mode == "moon-safe":
        lines.append("Moon condition passes the non-void safety check.")
    note = str(window.get("note") or "").strip()
    if note:
        lines.append(note)
    return lines


def explain_candidate_window(
    window: dict[str, object],
    baseline: dict[str, object] | None = None,
    config: SearchConfig = DEFAULT_SEARCH_CONFIG,
) -> str:
    return " ".join(candidate_explanation_lines(window, baseline, config))


def annotate_candidate_explanations(
    windows: list[dict[str, object]],
    baseline: dict[str, object],
    config: SearchConfig = DEFAULT_SEARCH_CONFIG,
) -> list[dict[str, object]]:
    annotated: list[dict[str, object]] = []
    for window in windows:
        item = dict(window)
        lines = candidate_explanation_lines(item, baseline, config)
        item["searchQuality"] = search_quality_index(item, config.quality_mode)
        item["rankReasons"] = lines
        item["whyThisWindow"] = " ".join(lines)
        annotated.append(item)
    return annotated


def candidate_refinement_offsets(
    windows: list[dict[str, object]],
    base_moment: datetime,
    config: SearchConfig = DEFAULT_SEARCH_CONFIG,
) -> tuple[int, ...]:
    if not config.refine_candidates or config.step_minutes <= config.refinement_step_minutes:
        return ()
    refinement_step = max(1, min(config.refinement_step_minutes, config.step_minutes))
    radius = min(30, max(refinement_step, config.step_minutes // 2))
    seed_count = max(1, config.refinement_seed_count)
    seeds = sort_search_windows(windows, config)[:seed_count]
    existing = set(config.offsets())
    refined: set[int] = set()
    for seed in seeds:
        moment = seed.get("date")
        if not isinstance(moment, datetime):
            continue
        seed_offset = round((moment - base_moment).total_seconds() / 60)
        for delta in range(-radius, radius + 1, refinement_step):
            candidate = seed_offset + delta
            if (
                delta
                and config.start_offset_minutes <= candidate <= config.end_offset_minutes
                and candidate not in existing
            ):
                refined.add(candidate)
    return tuple(sorted(refined))


def deep_candidate_count(total_count: int, config: SearchConfig = DEFAULT_SEARCH_CONFIG) -> int:
    if config.max_results:
        return min(total_count, max(config.max_results * 3, config.max_results + 6, 12))
    return total_count


def fast_deep_candidates(
    windows: list[dict[str, object]],
    config: SearchConfig = DEFAULT_SEARCH_CONFIG,
) -> tuple[list[dict[str, object]], list[RejectionRecord]]:
    filtered, rejections = split_ranked_windows(windows, config)
    ranked = sort_search_windows(filtered, config)
    return ranked[: deep_candidate_count(len(ranked), config)], rejections


def rank_search_windows(windows: list[dict[str, object]], config: SearchConfig = DEFAULT_SEARCH_CONFIG) -> list[dict[str, object]]:
    filtered, _rejections = split_ranked_windows(windows, config)
    ranked = sort_search_windows(filtered, config)
    return ranked[: config.max_results] if config.max_results else ranked
