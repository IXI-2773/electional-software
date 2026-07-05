"""Configurable electional window search."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Mapping

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
THRESHOLD_MODES: dict[str, str] = {
    "none": "No Minimum Acceptable Threshold",
    "strict": "Strict",
    "practical": "Practical",
    "emergency": "Emergency",
}
DEFAULT_THRESHOLD_MODE = "none"


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
    target_aspect_text: str = ""
    target_aspect_body_text: str = ""
    target_planet_text: str = ""
    target_sign_text: str = ""
    target_house: int | None = None
    quality_mode: str = DEFAULT_SEARCH_QUALITY_MODE
    refine_candidates: bool = True
    refinement_step_minutes: int = 10
    refinement_seed_count: int = 4
    threshold_mode: str = DEFAULT_THRESHOLD_MODE

    def offsets(self) -> tuple[int, ...]:
        if self.step_minutes <= 0:
            raise ValueError("Search step must be greater than zero minutes.")
        if self.end_offset_minutes < self.start_offset_minutes:
            raise ValueError("Search end must be at or after search start.")
        return tuple(range(self.start_offset_minutes, self.end_offset_minutes + 1, self.step_minutes))


def broad_scan_offsets(config: SearchConfig | None = None) -> tuple[int, ...]:
    """Pass 1: scan the allowed range on a stable 60-minute grid."""

    config = config or DEFAULT_SEARCH_CONFIG
    if config.end_offset_minutes < config.start_offset_minutes:
        raise ValueError("Search end must be at or after search start.")
    step = 60 if config.end_offset_minutes - config.start_offset_minutes >= 60 else max(1, config.step_minutes)
    offsets = set(range(config.start_offset_minutes, config.end_offset_minutes + 1, step))
    offsets.add(config.start_offset_minutes)
    offsets.add(config.end_offset_minutes)
    return tuple(sorted(offsets))


def search_refinement_plan(config: SearchConfig | None = None) -> dict[str, object]:
    """Describe the staged refinement pipeline used by the election search."""

    config = config or DEFAULT_SEARCH_CONFIG
    return {
        "passes": [
            {"pass": 1, "name": "Broad scan", "stepMinutes": 60, "seedCount": None},
            {"pass": 2, "name": "Top candidates", "stepMinutes": 10, "seedCount": 20},
            {"pass": 3, "name": "Minute refinement", "stepMinutes": 1, "seedCount": 10},
            {"pass": 4, "name": "Exact aspect/angle transition solver", "stepMinutes": 1, "seedCount": 10},
            {"pass": 5, "name": "Stability check", "radiusMinutes": 15, "seedCount": 10},
        ],
        "rangeMinutes": [config.start_offset_minutes, config.end_offset_minutes],
    }


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

ELECTION_STRATEGY_PRESETS: dict[str, dict[str, object]] = {
    "Manual": {},
    "Launch Builder": {
        "objective": "Launch or publish",
        "search_preset": "Strict Launch",
        "quality_mode": "Angular Support",
        "target_aspect": "Trine",
        "target_aspect_body": "Sun,Jupiter",
        "target_planet": "Mercury",
        "target_house": "10",
        "scan_hours": "24",
        "step_minutes": "60",
        "require_applying_support": True,
        "require_angular_benefic": True,
        "avoid_major_stress": True,
        "avoid_angular_malefics": True,
        "avoid_objective_antipatterns": True,
    },
    "Negotiation Builder": {
        "objective": "Meeting or negotiation",
        "search_preset": "Clean Negotiation",
        "quality_mode": "Cleanest",
        "target_aspect": "Sextile",
        "target_aspect_body": "Mercury,Venus",
        "target_planet": "Mercury",
        "target_house": "7",
        "scan_hours": "12",
        "step_minutes": "30",
        "require_applying_support": True,
        "avoid_major_stress": True,
        "avoid_angular_malefics": True,
        "avoid_objective_antipatterns": True,
    },
    "Travel Builder": {
        "objective": "Travel departure",
        "search_preset": "Safe Travel",
        "quality_mode": "Moon Safe",
        "target_aspect": "Trine",
        "target_aspect_body": "Moon,Jupiter",
        "target_planet": "Moon",
        "target_house": "9",
        "scan_hours": "24",
        "step_minutes": "60",
        "require_applying_support": True,
        "require_moon_non_void": True,
        "avoid_major_stress": True,
        "avoid_angular_malefics": True,
        "avoid_objective_antipatterns": True,
    },
    "Money Builder": {
        "objective": "Money or business",
        "search_preset": "Conservative Money",
        "quality_mode": "Low Risk",
        "target_aspect": "Trine",
        "target_aspect_body": "Venus,Jupiter",
        "target_planet": "Venus",
        "target_house": "2",
        "scan_hours": "24",
        "step_minutes": "60",
        "require_applying_support": True,
        "require_angular_benefic": True,
        "avoid_major_stress": True,
        "avoid_angular_malefics": True,
        "avoid_objective_antipatterns": True,
    },
}
ELECTION_STRATEGY_NAMES = tuple(ELECTION_STRATEGY_PRESETS)


@dataclass(frozen=True)
class RejectionRecord:
    formatted_time: str
    score: int
    reasons: tuple[str, ...]
    repairs: tuple[str, ...] = ()


REJECTION_REASON_LABELS: dict[str, str] = {
    "moon_void": "Moon void",
    "malefic_angular": "Malefic angular",
    "lord_of_matter_weak": "Lord of Matter weak",
    "natal_profection_conflict": "Natal/profection conflict",
    "low_data_confidence": "Low data confidence",
    "below_score_threshold": "Below score threshold",
    "below_fit_threshold": "Below objective fit threshold",
    "below_cleanliness_threshold": "Below cleanliness threshold",
    "high_volatility": "High volatility",
    "major_stress": "Major stress",
    "missing_applying_support": "Missing applying support",
    "missing_angular_benefic": "Missing angular benefic",
    "objective_antipattern": "Objective anti-pattern",
    "target_aspect_missing": "Target aspect missing",
    "target_placement_missing": "Target placement missing",
    "below_grade_threshold": "Below grade threshold",
    "other": "Other",
}
ACCEPTED_REASON_LABELS: dict[str, str] = {
    "hard_gates_passed": "Hard gates passed",
    "moon_supported": "Moon supported",
    "lord_of_matter_strong": "Lord of Matter strong",
    "benefic_angular": "Benefic angular",
    "malefics_not_angular": "Malefics not angular",
    "natal_profection_aligned": "Natal/profection aligned",
    "data_confidence_acceptable": "Data confidence acceptable",
    "stable_window": "Stable usable window",
}
RARITY_SIMILARITY_THRESHOLD = 0.85


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
    target_aspect_text: str = "",
    target_aspect_body_text: str = "",
    target_planet_text: str = "",
    target_sign_text: str = "",
    target_house_text: str = "",
) -> SearchConfig:
    from ..validation import validate_search_inputs

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
    target_house = int(target_house_text.strip()) if target_house_text.strip() else None
    if target_house is not None and not 1 <= target_house <= 12:
        raise ValueError("Target house must be between 1 and 12.")
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
        target_aspect_text=target_aspect_text.strip(),
        target_aspect_body_text=target_aspect_body_text.strip(),
        target_planet_text=target_planet_text.strip(),
        target_sign_text=target_sign_text.strip(),
        target_house=target_house,
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


def normalize_threshold_mode(value: str | None) -> str:
    candidate = str(value or "").strip()
    if not candidate:
        return DEFAULT_THRESHOLD_MODE
    safe = candidate.lower().replace("_", "-").replace(" ", "-")
    if safe in {"minimum-acceptable", "minimum-threshold"}:
        return "strict"
    return safe if safe in THRESHOLD_MODES else DEFAULT_THRESHOLD_MODE


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
    threshold_mode = normalize_threshold_mode(config.threshold_mode)
    if threshold_mode != "none":
        filters.append(f"threshold: {THRESHOLD_MODES[threshold_mode]}")
    if config.target_aspect_text:
        aspect_target = f"aspect: {config.target_aspect_text}"
        if config.target_aspect_body_text:
            aspect_target += f" involving {config.target_aspect_body_text}"
        filters.append(aspect_target)
    if config.target_planet_text:
        placement_bits = []
        if config.target_sign_text:
            placement_bits.append(f"in {config.target_sign_text}")
        if config.target_house is not None:
            placement_bits.append(f"H{config.target_house}")
        if placement_bits:
            filters.append(f"{config.target_planet_text} {' / '.join(placement_bits)}")
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


def election_strategy_values(name: str) -> dict[str, object]:
    return dict(ELECTION_STRATEGY_PRESETS.get(name, {}))


PLANET_QUERY_ALIASES = {
    "sun": "Sun",
    "moon": "Moon",
    "mercury": "Mercury",
    "venus": "Venus",
    "mars": "Mars",
    "jupiter": "Jupiter",
    "saturn": "Saturn",
    "uranus": "Uranus",
    "neptune": "Neptune",
    "pluto": "Pluto",
}
ASPECT_QUERY_ALIASES = {
    "conjunction": "Conjunction",
    "conj": "Conjunction",
    "opposition": "Opposition",
    "opp": "Opposition",
    "square": "Square",
    "sqr": "Square",
    "trine": "Trine",
    "tri": "Trine",
    "sextile": "Sextile",
    "sex": "Sextile",
    "semisquare": "Semisquare",
    "semi-square": "Semisquare",
    "quincunx": "Quincunx",
    "inconjunct": "Quincunx",
}
SIGN_QUERY_ALIASES = {
    "aries": "Aries",
    "taurus": "Taurus",
    "gemini": "Gemini",
    "cancer": "Cancer",
    "leo": "Leo",
    "virgo": "Virgo",
    "libra": "Libra",
    "scorpio": "Scorpio",
    "sagittarius": "Sagittarius",
    "capricorn": "Capricorn",
    "aquarius": "Aquarius",
    "pisces": "Pisces",
    "ophiuchus": "Ophiuchus",
}


def parse_exact_search_query(query: str) -> dict[str, str]:
    """Parse compact user search text into existing target filters."""

    text = str(query or "").strip()
    lowered = _clean_target_text(text)
    if not lowered:
        return {}
    result: dict[str, str] = {"query": text}
    planet_hits = [label for alias, label in PLANET_QUERY_ALIASES.items() if re.search(rf"\b{re.escape(alias)}\b", lowered)]
    aspect_hits = [label for alias, label in ASPECT_QUERY_ALIASES.items() if re.search(rf"\b{re.escape(alias)}\b", lowered)]
    if aspect_hits:
        result["target_aspect"] = aspect_hits[0]
        if planet_hits:
            result["target_aspect_body"] = ",".join(dict.fromkeys(planet_hits[:2]))
    if planet_hits:
        result["target_planet"] = planet_hits[0]
    sign_hits = [label for alias, label in SIGN_QUERY_ALIASES.items() if re.search(rf"\b{re.escape(alias)}\b", lowered)]
    if sign_hits:
        result["target_sign"] = sign_hits[0]
    house_match = re.search(r"\b(?:h|house\s*)?([1-9]|1[0-2])(?:st|nd|rd|th)?(?:\s*house)?\b", lowered)
    if house_match and ("house" in lowered or " h" in f" {lowered}" or re.search(r"\b\d+(?:st|nd|rd|th)\b", lowered)):
        result["target_house"] = house_match.group(1)
    return result


def exact_search_query_summary(query: str) -> str:
    parsed = parse_exact_search_query(query)
    if not parsed:
        return "Exact search query waiting."
    parts = []
    if parsed.get("target_aspect"):
        aspect = str(parsed["target_aspect"])
        bodies = str(parsed.get("target_aspect_body") or "any body")
        parts.append(f"aspect {aspect} involving {bodies}")
    if parsed.get("target_planet"):
        placement = [str(parsed["target_planet"])]
        if parsed.get("target_sign"):
            placement.append(f"in {parsed['target_sign']}")
        if parsed.get("target_house"):
            placement.append(f"H{parsed['target_house']}")
        parts.append(" ".join(placement))
    return "Exact search: " + "; ".join(parts)


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
    angularity = window.get("angularity", {})
    if isinstance(angularity, dict):
        for name in ("Mars", "Saturn"):
            payload = angularity.get(name)
            if not isinstance(payload, dict) or not payload.get("isAngular"):
                continue
            orb = payload.get("orb", payload.get("distance", 99))
            try:
                if float(orb) <= 8.0:
                    return True
            except (TypeError, ValueError):
                continue
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


def _clean_target_text(value: object) -> str:
    return str(value or "").strip().lower().replace("_", " ").replace("-", " ")


def _target_matches_name(value: object, target: str) -> bool:
    normalized_target = _clean_target_text(target)
    if not normalized_target:
        return True
    normalized_value = _clean_target_text(value)
    return normalized_value == normalized_target or normalized_target in normalized_value


def has_target_aspect(window: dict[str, object], aspect_text: str = "", body_text: str = "") -> bool:
    aspect_target = _clean_target_text(aspect_text)
    body_targets = [
        _clean_target_text(part)
        for part in re.split(r"[,/&+]+|\band\b", str(body_text or ""), flags=re.IGNORECASE)
        if _clean_target_text(part)
    ]
    if not aspect_target and not body_targets:
        return True
    aspects = window.get("detectedAspects", [])
    for aspect in aspects if isinstance(aspects, list) else []:
        if not isinstance(aspect, dict):
            continue
        aspect_values = (
            aspect.get("aspectId"),
            aspect.get("aspectName"),
            aspect.get("aspectAbbreviation"),
            aspect.get("label"),
        )
        if aspect_target and not any(_target_matches_name(value, aspect_target) for value in aspect_values):
            continue
        if body_targets:
            bodies = aspect.get("bodies", [])
            if not isinstance(bodies, list):
                continue
            if not all(any(_target_matches_name(body, target) for body in bodies) for target in body_targets):
                continue
        return True
    return False


def has_planet_placement(window: dict[str, object], planet_text: str = "", sign_text: str = "", house: int | None = None) -> bool:
    planet_target = _clean_target_text(planet_text)
    sign_target = _clean_target_text(sign_text)
    if not planet_target:
        return True
    positions = window.get("positions", [])
    for planet in positions if isinstance(positions, list) else []:
        if not isinstance(planet, dict) or not _target_matches_name(planet.get("name"), planet_target):
            continue
        if house is not None:
            try:
                if int(planet.get("house", 0)) != int(house):
                    continue
            except (TypeError, ValueError):
                continue
        if sign_target:
            zodiac = planet.get("zodiac", {})
            sign_name = zodiac.get("sign") if isinstance(zodiac, dict) else ""
            constellation = planet.get("constellation", {})
            constellation_name = constellation.get("name") if isinstance(constellation, dict) else ""
            if not (_target_matches_name(sign_name, sign_target) or _target_matches_name(constellation_name, sign_target)):
                continue
        return True
    return False


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


def election_grade(score: object) -> str:
    try:
        value = int(score)
    except (TypeError, ValueError):
        value = 0
    if value >= 90:
        return "A"
    if value >= 80:
        return "B"
    if value >= 75:
        return "C+"
    if value >= 70:
        return "C"
    if value >= 60:
        return "D"
    return "F"


def hard_failure_reasons(window: dict[str, object]) -> list[str]:
    reasons: list[str] = []
    calc_conf = window.get("calculationConfidence", {})
    if isinstance(calc_conf, dict):
        reasons.extend(str(warning) for warning in calc_conf.get("hardWarnings", []) if warning)
    if has_major_stress(window):
        reasons.append("major stress present")
    if has_angular_malefic(window):
        reasons.append("angular malefic present")
    if not moon_is_non_void(window):
        reasons.append("Moon is void or uncertain")
    matter = window.get("matterLordContext", {})
    if isinstance(matter, dict):
        try:
            matter_impact = float(matter.get("scoreImpact", 0) or 0)
        except (TypeError, ValueError):
            matter_impact = 0.0
        if matter_impact < -0.75:
            reasons.append("Lord of Matter hard failure")
    if diagnostic_score(window, "confidence") < 55:
        reasons.append("data confidence failure")
    return list(dict.fromkeys(reasons))


def threshold_classification(window: dict[str, object], mode: str = "strict") -> dict[str, object]:
    normalized = normalize_threshold_mode(mode)
    score = int(window.get("score", 0) or 0)
    confidence = diagnostic_score(window, "confidence")
    hard_failures = hard_failure_reasons(window)
    warnings: list[str] = []
    reasons: list[str] = []
    accepted = False

    fragility = window.get("fragility")
    if not isinstance(fragility, dict):
        stability = window.get("windowStability", {})
        fragility = stability.get("fragility", {}) if isinstance(stability, dict) else {}
    fragility_band = str(fragility.get("band") or "") if isinstance(fragility, dict) else ""
    if fragility_band == "Medium":
        warnings.append("medium fragility; timing should be monitored closely")

    if normalized == "strict":
        if score < 80:
            reasons.append(f"grade {election_grade(score)} below B")
        if hard_failures:
            reasons.extend(hard_failures)
        if confidence < 70:
            reasons.append(f"data confidence {confidence} below strict minimum 70")
        accepted = not reasons
    elif normalized == "practical":
        if score < 75:
            reasons.append(f"grade {election_grade(score)} below C+")
        if hard_failures:
            reasons.extend(hard_failures)
        if confidence < 75:
            reasons.append(f"analysis confidence {confidence} is not high enough for Practical mode")
        accepted = not reasons
    elif normalized == "emergency":
        clean = threshold_classification(window, "practical")
        reasons = list(clean.get("reasons", []))
        warnings.extend(str(item) for item in clean.get("warnings", []))
        accepted = bool(clean.get("accepted"))

    return {
        "mode": THRESHOLD_MODES.get(normalized, THRESHOLD_MODES[DEFAULT_THRESHOLD_MODE]),
        "modeId": normalized,
        "accepted": accepted,
        "status": "accepted" if accepted else "rejected",
        "grade": election_grade(score),
        "score": score,
        "confidence": confidence,
        "hardFailures": hard_failures,
        "reasons": list(dict.fromkeys(reasons)),
        "warnings": list(dict.fromkeys(warnings)),
    }


def threshold_rejection_reasons(window: dict[str, object], mode: str) -> list[str]:
    normalized = normalize_threshold_mode(mode)
    if normalized in {"none", "emergency"}:
        return []
    classification = threshold_classification(window, normalized)
    return [str(reason) for reason in classification.get("reasons", [])]


def rejection_reason_codes(
    window: dict[str, object],
    config: SearchConfig,
    reasons: list[str] | tuple[str, ...] | None = None,
) -> list[str]:
    reason_texts = list(reasons if reasons is not None else rejection_reasons(window, config))
    codes: list[str] = []
    for reason in reason_texts:
        lowered = str(reason).lower()
        code = "other"
        if "moon is void" in lowered or "moon void" in lowered:
            code = "moon_void"
        elif "angular malefic" in lowered or "malefic angular" in lowered:
            code = "malefic_angular"
        elif "lord of matter" in lowered:
            code = "lord_of_matter_weak"
        elif "natal" in lowered or "profection" in lowered:
            code = "natal_profection_conflict"
        elif "confidence" in lowered or "data confidence" in lowered:
            code = "low_data_confidence"
        elif "score" in lowered and "below" in lowered:
            code = "below_score_threshold"
        elif "fit" in lowered and "below" in lowered:
            code = "below_fit_threshold"
        elif "cleanliness" in lowered:
            code = "below_cleanliness_threshold"
        elif "volatility" in lowered:
            code = "high_volatility"
        elif "major stress" in lowered:
            code = "major_stress"
        elif "applying support" in lowered:
            code = "missing_applying_support"
        elif "angular benefic" in lowered:
            code = "missing_angular_benefic"
        elif "anti-pattern" in lowered or "antipattern" in lowered:
            code = "objective_antipattern"
        elif "target aspect" in lowered:
            code = "target_aspect_missing"
        elif "target placement" in lowered:
            code = "target_placement_missing"
        elif "grade" in lowered and "below" in lowered:
            code = "below_grade_threshold"
        codes.append(code)
    return list(dict.fromkeys(codes or ["other"]))


def accepted_reason_codes(window: dict[str, object], config: SearchConfig = DEFAULT_SEARCH_CONFIG) -> list[str]:
    codes: list[str] = []
    if not rejection_reasons(window, config):
        codes.append("hard_gates_passed")
    if moon_is_non_void(window) and (_moon_applies_to_benefic(window) or _moon_condition_score(window) > 9):
        codes.append("moon_supported")
    matter = window.get("matterLordContext", {})
    if isinstance(matter, dict):
        try:
            if float(matter.get("scoreImpact", 0) or 0) >= 0.75:
                codes.append("lord_of_matter_strong")
        except (TypeError, ValueError):
            pass
    if has_angular_benefic(window):
        codes.append("benefic_angular")
    if not has_angular_malefic(window):
        codes.append("malefics_not_angular")
    metrics = window.get("multiObjective")
    if not isinstance(metrics, dict):
        metrics = multi_objective_metrics(window)
    if int(metrics.get("natalFit", 0) or 0) >= 70:
        codes.append("natal_profection_aligned")
    if diagnostic_score(window, "confidence") >= 70:
        codes.append("data_confidence_acceptable")
    if int(metrics.get("stability", 0) or 0) >= 70:
        codes.append("stable_window")
    return codes


def search_reason_payload(
    window: dict[str, object],
    config: SearchConfig = DEFAULT_SEARCH_CONFIG,
    *,
    accepted: bool = True,
    rejection_texts: list[str] | tuple[str, ...] | None = None,
) -> dict[str, object]:
    if accepted:
        codes = accepted_reason_codes(window, config)
        labels = [ACCEPTED_REASON_LABELS.get(code, code) for code in codes]
    else:
        codes = rejection_reason_codes(window, config, rejection_texts)
        labels = [REJECTION_REASON_LABELS.get(code, code) for code in codes]
    return {
        "accepted": accepted,
        "reason_codes": codes,
        "primary_reason": codes[0] if codes else "other",
        "labels": labels,
    }


def rarity_quality_score(window: dict[str, object]) -> float:
    metrics = window.get("multiObjective")
    if not isinstance(metrics, dict):
        metrics = multi_objective_metrics(window)
    return round(
        int(window.get("score", 0) or 0) * 0.30
        + int(metrics.get("moon", 0) or 0) * 0.12
        + int(metrics.get("matter", 0) or 0) * 0.11
        + int(metrics.get("lowMaleficDamage", 0) or 0) * 0.13
        + int(metrics.get("dataConfidence", 0) or 0) * 0.13
        + int(metrics.get("stability", 0) or 0) * 0.11
        + int(metrics.get("natalFit", 0) or 0) * 0.10,
        2,
    )


def rarity_eligible(window: dict[str, object], config: SearchConfig = DEFAULT_SEARCH_CONFIG) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if hard_failure_reasons(window):
        reasons.append("hard rejection flags present")
    confidence = diagnostic_score(window, "confidence")
    if confidence < 70:
        reasons.append(f"data confidence {confidence} below rarity minimum 70")
    score = int(window.get("score", 0) or 0)
    if score < 70:
        reasons.append(f"grade {election_grade(score)} below usable minimum C")
    metrics = window.get("multiObjective")
    if not isinstance(metrics, dict):
        metrics = multi_objective_metrics(window)
    if int(metrics.get("stability", 0) or 0) < 45:
        reasons.append("stability critically low")
    fragility = window.get("fragility")
    if not isinstance(fragility, dict):
        stability_payload = window.get("windowStability", {})
        fragility = stability_payload.get("fragility", {}) if isinstance(stability_payload, dict) else {}
    if isinstance(fragility, dict) and str(fragility.get("band") or "") == "High":
        reasons.append("timing fragility high")
    return not reasons, reasons


def similar_quality_count(
    candidate: dict[str, object],
    population: list[dict[str, object]],
    config: SearchConfig = DEFAULT_SEARCH_CONFIG,
    *,
    similarity_threshold: float = RARITY_SIMILARITY_THRESHOLD,
) -> int:
    candidate_quality = rarity_quality_score(candidate)
    candidate_score = int(candidate.get("score", 0) or 0)
    candidate_confidence = diagnostic_score(candidate, "confidence")
    candidate_id = _window_identity(candidate)
    count = 0
    for window in population:
        if _window_identity(window) == candidate_id:
            continue
        eligible, _reasons = rarity_eligible(window, config)
        if not eligible:
            continue
        if int(window.get("score", 0) or 0) < candidate_score - 5:
            continue
        if diagnostic_score(window, "confidence") < candidate_confidence - 5:
            continue
        if rarity_quality_score(window) >= candidate_quality * similarity_threshold:
            count += 1
    return count


def rarity_label_for_candidate(
    candidate: dict[str, object],
    population: list[dict[str, object]],
    config: SearchConfig = DEFAULT_SEARCH_CONFIG,
    *,
    similarity_threshold: float = RARITY_SIMILARITY_THRESHOLD,
) -> dict[str, object]:
    horizon_days = round((config.end_offset_minutes - config.start_offset_minutes) / 1440, 2)
    eligible, eligibility_reasons = rarity_eligible(candidate, config)
    quality = rarity_quality_score(candidate)
    eligible_population = [window for window in population if rarity_eligible(window, config)[0]]
    similar_count = similar_quality_count(candidate, population, config, similarity_threshold=similarity_threshold) if eligible else 0
    if not eligible:
        return {
            "rarity_score": min(49.0, quality),
            "rarity_label": "common",
            "similar_quality_count": similar_count,
            "search_horizon_days": horizon_days,
            "similarity_threshold": similarity_threshold,
            "rarity_reasons": eligibility_reasons,
        }
    comparable_total = max(1, len(eligible_population) - 1)
    scarcity = 100.0 * (1.0 - min(similar_count, comparable_total) / comparable_total)
    rarity_score = round(max(0.0, min(99.0, quality * 0.55 + scarcity * 0.45)), 2)
    if similar_count <= 1 and rarity_score >= 85:
        label = "very_rare"
    elif similar_count <= 3 and rarity_score >= 78:
        label = "rare"
    elif similar_count <= max(5, round(comparable_total * 0.20)):
        label = "uncommon"
    else:
        label = "common"
    return {
        "rarity_score": rarity_score,
        "rarity_label": label,
        "similar_quality_count": similar_count,
        "search_horizon_days": horizon_days,
        "similarity_threshold": similarity_threshold,
        "rarity_reasons": rarity_reasons(candidate, similar_count, horizon_days, label),
    }


def rarity_reasons(candidate: dict[str, object], similar_count: int, horizon_days: float, label: str) -> list[str]:
    if label == "common":
        return [f"Similar or better windows are not scarce in the {horizon_days:g}-day search horizon."]
    return [
        f"Similar quality appears {similar_count} time{'s' if similar_count != 1 else ''} in the {horizon_days:g}-day search horizon.",
        f"Composite rarity quality score is {rarity_quality_score(candidate):.2f}.",
    ]


def election_grade_label(score: object) -> str:
    try:
        value = int(score or 0)
    except (TypeError, ValueError):
        value = 0
    if value >= 94:
        return "A+"
    if value >= 90:
        return "A"
    if value >= 86:
        return "A-"
    if value >= 82:
        return "B+"
    if value >= 80:
        return "B"
    if value >= 75:
        return "C+"
    if value >= 70:
        return "C"
    if value >= 60:
        return "D"
    return "F"


def confidence_band(score: int) -> str:
    if score >= 80:
        return "High"
    if score >= 60:
        return "Medium"
    return "Low"


def search_coverage_label(search_reason_log: dict[str, object] | None = None) -> str:
    if not search_reason_log:
        return "Complete"
    total = int(search_reason_log.get("total_windows_evaluated", 0) or 0)
    if total <= 0:
        return "Weak"
    return "Complete" if search_reason_log.get("reconciles") else "Partial"


def analysis_confidence_payload(
    window: dict[str, object],
    config: SearchConfig = DEFAULT_SEARCH_CONFIG,
    search_reason_log: dict[str, object] | None = None,
) -> dict[str, object]:
    score = int(window.get("score", 0) or 0)
    data_score = diagnostic_score(window, "confidence")
    data_confidence = confidence_band(data_score)
    coverage = search_coverage_label(search_reason_log)
    reasons: list[str] = []

    calculation_confidence = window.get("calculationConfidence", {})
    if isinstance(calculation_confidence, dict):
        hard_warnings = [str(item) for item in calculation_confidence.get("hardWarnings", []) if item]
        reasons.extend(hard_warnings[:3])
        try:
            calc_score = int(calculation_confidence.get("score", data_score) or data_score)
        except (TypeError, ValueError):
            calc_score = data_score
        if calc_score < 60:
            reasons.append(f"calculation confidence {calc_score} below medium threshold")

    moon_condition = window.get("moonCondition", {})
    if isinstance(moon_condition, dict):
        confidence = str(moon_condition.get("confidence") or "")
        if confidence and confidence not in {"solid", "high"}:
            reasons.append(f"Moon condition confidence is {confidence}")
        void_data = moon_condition.get("voidOfCourse", {})
        if isinstance(void_data, dict):
            void_confidence = str(void_data.get("confidence") or "")
            if void_confidence and void_confidence not in {"solid", "high"}:
                reasons.append(f"Moon VOC confidence is {void_confidence}")

    for note in window.get("calculationHealthNotes", []):
        if isinstance(note, str) and ("boundary" in note.lower() or "fallback" in note.lower() or "partial" in note.lower()):
            reasons.append(note)

    if coverage != "Complete":
        reasons.append(f"search coverage is {coverage.lower()}")
    if data_confidence == "Low":
        analysis_confidence = "Low"
    elif coverage == "Weak" or any("hard warning" in reason.lower() for reason in reasons):
        analysis_confidence = "Low"
    elif data_confidence == "Medium" or coverage == "Partial" or reasons:
        analysis_confidence = "Medium"
    else:
        analysis_confidence = "High"

    warning = ""
    if score >= 86 and analysis_confidence == "Low":
        warning = "This chart grades well, but analysis confidence is Low. Treat this result as provisional until data issues are resolved."

    return {
        "election_grade": election_grade_label(score),
        "analysis_confidence": analysis_confidence,
        "data_confidence": data_confidence,
        "search_coverage": coverage,
        "confidence_reasons": list(dict.fromkeys(reasons))[:6],
        "warning": warning,
    }


def annotate_analysis_confidence_metadata(
    accepted_windows: list[dict[str, object]],
    config: SearchConfig = DEFAULT_SEARCH_CONFIG,
    search_reason_log: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    annotated: list[dict[str, object]] = []
    for window in accepted_windows:
        item = dict(window)
        item["confidence"] = analysis_confidence_payload(item, config, search_reason_log)
        annotated.append(item)
    return annotated


def annotate_rarity_metadata(
    accepted_windows: list[dict[str, object]],
    evaluated_population: list[dict[str, object]],
    config: SearchConfig = DEFAULT_SEARCH_CONFIG,
) -> list[dict[str, object]]:
    annotated: list[dict[str, object]] = []
    for window in accepted_windows:
        item = dict(window)
        item["rarity"] = rarity_label_for_candidate(item, evaluated_population, config)
        item["searchReasons"] = search_reason_payload(item, config, accepted=True)
        item["confidence"] = analysis_confidence_payload(item, config)
        annotated.append(item)
    return annotated


def build_search_reason_log(
    evaluated_windows: list[dict[str, object]],
    accepted_windows: list[dict[str, object]],
    rejections: list[RejectionRecord],
    config: SearchConfig = DEFAULT_SEARCH_CONFIG,
) -> dict[str, object]:
    rejection_breakdown = {code: 0 for code in REJECTION_REASON_LABELS}
    accepted_breakdown = {code: 0 for code in ACCEPTED_REASON_LABELS}
    rejected_windows = []
    for rejected in rejections:
        fake_window = {"score": rejected.score, "formattedTime": rejected.formatted_time}
        codes = rejection_reason_codes(fake_window, config, rejected.reasons)
        for code in codes:
            rejection_breakdown[code] = rejection_breakdown.get(code, 0) + 1
        rejected_windows.append(
            {
                "formatted_time": rejected.formatted_time,
                "score": rejected.score,
                "reason_codes": codes,
                "primary_reason": codes[0] if codes else "other",
                "reasons": list(rejected.reasons),
            }
        )
    accepted_items = []
    for window in accepted_windows:
        codes = accepted_reason_codes(window, config)
        for code in codes:
            accepted_breakdown[code] = accepted_breakdown.get(code, 0) + 1
        accepted_items.append(
            {
                "formatted_time": str(window.get("formattedTime") or window.get("time") or "time unavailable"),
                "score": int(window.get("score", 0) or 0),
                "reason_codes": codes,
                "primary_reason": codes[0] if codes else "hard_gates_passed",
            }
        )
    total = len(evaluated_windows)
    accepted_count = len(accepted_windows)
    rejected_count = len(rejections)
    return {
        "search_id": f"search-{config.start_offset_minutes}-{config.end_offset_minutes}-{config.step_minutes}-{total}",
        "total_windows_evaluated": total,
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "reconciles": accepted_count + rejected_count == total,
        "rejection_breakdown": rejection_breakdown,
        "accepted_breakdown": accepted_breakdown,
        "accepted_windows": accepted_items,
        "rejected_windows": rejected_windows,
    }


def least_bad_candidate(windows: list[dict[str, object]]) -> dict[str, object] | None:
    if not windows:
        return None
    return max(
        windows,
        key=lambda window: (
            -len(hard_failure_reasons(window)),
            diagnostic_score(window, "confidence"),
            int(window.get("score", 0) or 0),
            diagnostic_score(window, "cleanliness"),
            -diagnostic_score(window, "volatility", fallback=99),
        ),
    )


def classify_search_results_by_threshold(
    windows: list[dict[str, object]],
    mode: str = "strict",
) -> dict[str, object]:
    normalized = normalize_threshold_mode(mode)
    ranked = sort_search_windows(list(windows), DEFAULT_SEARCH_CONFIG)
    accepted: list[dict[str, object]] = []
    rejected: list[dict[str, object]] = []
    for window in ranked:
        item = dict(window)
        classification = threshold_classification(item, "practical" if normalized == "emergency" else normalized)
        item["thresholdClassification"] = classification
        if classification["accepted"]:
            accepted.append(item)
        else:
            rejected.append(item)

    payload: dict[str, object] = {
        "mode": THRESHOLD_MODES.get(normalized, THRESHOLD_MODES[DEFAULT_THRESHOLD_MODE]),
        "modeId": normalized,
        "accepted": annotate_multi_objective_candidates(accepted),
        "rejected": rejected,
        "status": "accepted" if accepted else "no_acceptable_election",
        "explanation": "Acceptable election found." if accepted else "No clean election was found under the selected thresholds.",
    }
    if normalized == "emergency" and not accepted:
        fallback = least_bad_candidate(ranked)
        if fallback:
            emergency = dict(fallback)
            emergency["thresholdClassification"] = threshold_classification(emergency, "emergency")
            emergency["thresholdClassification"]["status"] = "emergency-only"
            emergency["emergencyOnly"] = True
            emergency["emergencyExplanation"] = "No clean election was found; this is the least-bad available option."
            payload["emergencyCandidate"] = annotate_multi_objective_candidates([emergency])[0]
        payload["status"] = "emergency_only" if fallback else "no_candidates"
        payload["explanation"] = (
            "No clean election was found; Emergency mode returns the least-bad option only."
            if fallback
            else "No candidate windows were available to classify."
        )
    return payload


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
    reasons.extend(threshold_rejection_reasons(window, config.threshold_mode))
    if (config.target_aspect_text or config.target_aspect_body_text) and not has_target_aspect(
        window,
        config.target_aspect_text,
        config.target_aspect_body_text,
    ):
        target = config.target_aspect_text or "any aspect"
        if config.target_aspect_body_text:
            target += f" involving {config.target_aspect_body_text}"
        reasons.append(f"missing target aspect: {target}")
    if config.target_planet_text and not has_planet_placement(
        window,
        config.target_planet_text,
        config.target_sign_text,
        config.target_house,
    ):
        placement = []
        if config.target_sign_text:
            placement.append(f"in {config.target_sign_text}")
        if config.target_house is not None:
            placement.append(f"in house {config.target_house}")
        reasons.append(f"missing target placement: {config.target_planet_text} {' '.join(placement)}".strip())
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
            repairs = tuple(repair_suggestions(window, config, [], reasons))
            rejected.append(
                RejectionRecord(
                    formatted_time=str(window.get("formattedTime", "time unavailable")),
                    score=int(window.get("score", 0)),
                    reasons=tuple(reasons),
                    repairs=repairs,
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
                "repairs": list(rejected.repairs[:3]),
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
        elif "missing target aspect" in lowered:
            suggestion = "Clear the target aspect briefly to see nearby windows, then compare which ones have the contact."
        elif "missing target placement" in lowered:
            suggestion = "Clear the planet sign/house target or widen the scan; placements can require a different time block."
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


def _clamp_score(value: float) -> int:
    return max(0, min(99, round(value)))


def multi_objective_metrics(window: dict[str, object]) -> dict[str, object]:
    """Expose tradeoff dimensions so candidates are not reduced to one score."""

    power = _clamp_score(float(window.get("score", 0) or 0))
    confidence = diagnostic_score(window, "confidence")
    cleanliness = diagnostic_score(window, "cleanliness")
    readiness = diagnostic_score(window, "readiness")
    volatility = diagnostic_score(window, "volatility", fallback=50)
    moon = _clamp_score(50 + _moon_condition_score(window) * 2.5)
    matter = window.get("matterLordContext", {})
    matter_score = 50
    if isinstance(matter, dict):
        matter_score = _clamp_score(50 + float(matter.get("scoreImpact", 0) or 0) * 6.0)
    stability_payload = window.get("windowStability", {})
    stability = 50
    if isinstance(stability_payload, dict):
        classification = str(stability_payload.get("classification") or "")
        samples = stability_payload.get("samples", [])
        sample_count = len(samples) if isinstance(samples, list) else 0
        stability = {"stable": 88, "usable": 72, "fragile": 42, "unmeasured": 50}.get(classification, 50)
        stability = _clamp_score(stability + min(sample_count, 15) * 0.7)
        fragility_payload = window.get("fragility") if isinstance(window.get("fragility"), dict) else stability_payload.get("fragility")
        if isinstance(fragility_payload, dict):
            band = str(fragility_payload.get("band") or "")
            if band == "High":
                stability = _clamp_score(stability - 18)
            elif band == "Medium":
                stability = _clamp_score(stability - 7)
            elif band == "Low":
                stability = _clamp_score(stability + 5)
    malefic_damage = _clamp_score(
        volatility
        + _aspect_count(window, "stress", applying_only=True) * 8
        + (18 if has_angular_malefic(window) else 0)
        + (12 if has_major_stress(window) else 0)
    )
    safety = _clamp_score(cleanliness * 0.38 + confidence * 0.24 + moon * 0.18 + (99 - malefic_damage) * 0.20)
    natal_fit = _clamp_score(float(window.get("natalCompatibilityScore", 50) or 50))
    usability = _clamp_score(stability * 0.45 + safety * 0.35 + readiness * 0.20)
    risk_score = _clamp_score(malefic_damage * 0.50 + (99 - safety) * 0.30 + (99 - stability) * 0.20)
    if risk_score >= 70:
        risk = "High"
    elif risk_score >= 45:
        risk = "Medium"
    else:
        risk = "Low"
    return {
        "power": power,
        "safety": safety,
        "stability": stability,
        "natalFit": natal_fit,
        "moon": moon,
        "matter": matter_score,
        "dataConfidence": confidence,
        "lowMaleficDamage": _clamp_score(99 - malefic_damage),
        "realLifeUsability": usability,
        "risk": risk,
        "riskScore": risk_score,
    }


def pareto_dominates(first: dict[str, object], second: dict[str, object]) -> bool:
    first_metrics = first.get("multiObjective", {})
    second_metrics = second.get("multiObjective", {})
    if not isinstance(first_metrics, dict) or not isinstance(second_metrics, dict):
        return False
    keys = ("power", "safety", "stability", "natalFit", "lowMaleficDamage", "realLifeUsability")
    first_values = [float(first_metrics.get(key, 0) or 0) for key in keys]
    second_values = [float(second_metrics.get(key, 0) or 0) for key in keys]
    return all(a >= b for a, b in zip(first_values, second_values)) and any(a > b for a, b in zip(first_values, second_values))


def assign_pareto_fronts(windows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Annotate candidates with Pareto front rank and tradeoff role."""

    annotated = []
    for window in windows:
        item = dict(window)
        item["multiObjective"] = dict(item.get("multiObjective") or multi_objective_metrics(item))
        annotated.append(item)
    remaining = list(range(len(annotated)))
    front = 1
    while remaining:
        current_front: list[int] = []
        for index in remaining:
            candidate = annotated[index]
            dominated = any(
                other_index != index and pareto_dominates(annotated[other_index], candidate)
                for other_index in remaining
            )
            if not dominated:
                current_front.append(index)
        for index in current_front:
            annotated[index]["paretoFront"] = front
        remaining = [index for index in remaining if index not in current_front]
        front += 1
    return annotated


def annotate_multi_objective_candidates(windows: list[dict[str, object]]) -> list[dict[str, object]]:
    annotated = assign_pareto_fronts(windows)
    if not annotated:
        return []
    best_aggressive = max(annotated, key=lambda window: int(window["multiObjective"].get("power", 0)))
    best_safe = max(annotated, key=lambda window: (int(window["multiObjective"].get("safety", 0)), int(window["multiObjective"].get("stability", 0))))
    best_practical = max(annotated, key=lambda window: int(window["multiObjective"].get("realLifeUsability", 0)))
    for window in annotated:
        roles: list[str] = []
        if window is best_aggressive:
            roles.append("Best aggressive")
        if window is best_safe:
            roles.append("Best safe")
        if window is best_practical:
            roles.append("Best practical")
        if not roles and int(window.get("paretoFront", 99) or 99) == 1:
            roles.append("Pareto front")
        window["tradeoffRole"] = ", ".join(roles) if roles else f"Pareto front {window.get('paretoFront', '?')}"
    return annotated


def multi_objective_lines(window: dict[str, object]) -> list[str]:
    metrics = window.get("multiObjective")
    if not isinstance(metrics, dict):
        metrics = multi_objective_metrics(window)
    return [
        (
            f"Power {metrics.get('power', '?')} | Safety {metrics.get('safety', '?')} | "
            f"Stability {metrics.get('stability', '?')} | Natal Fit {metrics.get('natalFit', '?')} | "
            f"Risk {metrics.get('risk', 'n/a')}"
        ),
        (
            f"Moon {metrics.get('moon', '?')} | Matter {metrics.get('matter', '?')} | "
            f"Data {metrics.get('dataConfidence', '?')} | Malefic control {metrics.get('lowMaleficDamage', '?')} | "
            f"Usability {metrics.get('realLifeUsability', '?')}"
        ),
    ]


def _candidate_label(index: int) -> str:
    return f"Candidate {chr(ord('A') + index)}"


def _candidate_name(window: dict[str, object], index: int) -> str:
    return str(window.get("formattedTime") or window.get("time") or _candidate_label(index))


def _metric_value(window: dict[str, object], key: str) -> int:
    metrics = window.get("multiObjective")
    if not isinstance(metrics, dict):
        metrics = multi_objective_metrics(window)
    try:
        return int(metrics.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def candidate_advantages(first: dict[str, object], second: dict[str, object], *, minimum_delta: int = 5) -> list[str]:
    checks = (
        ("moon", "stronger Moon condition"),
        ("matter", "better Lord of Matter placement"),
        ("natalFit", "higher natal/profection compatibility"),
        ("power", "stronger overall election power"),
        ("safety", "safer"),
        ("stability", "wider stable window"),
        ("lowMaleficDamage", "less malefic angular pressure"),
        ("dataConfidence", "higher analysis confidence"),
        ("realLifeUsability", "better practical reliability"),
    )
    advantages = [
        label
        for key, label in checks
        if _metric_value(first, key) - _metric_value(second, key) >= minimum_delta
    ]
    return advantages or ["no decisive objective edge; compare context and timing constraints"]


def candidate_debate_payload(
    windows: list[dict[str, object]],
    config: SearchConfig = DEFAULT_SEARCH_CONFIG,
    *,
    top_n: int = 2,
) -> dict[str, object]:
    ranked = annotate_multi_objective_candidates(sort_search_windows(list(windows), config))
    candidates = ranked[: max(0, top_n)]
    payload_candidates = [
        {
            "label": _candidate_label(index),
            "name": _candidate_name(window, index),
            "score": int(window.get("score", 0) or 0),
            "grade": election_grade(window.get("score", 0)),
            "tradeoffRole": window.get("tradeoffRole"),
            "multiObjective": dict(window.get("multiObjective", {})),
        }
        for index, window in enumerate(candidates)
    ]
    if len(candidates) < 2:
        return {
            "mode": "Candidate Debate",
            "candidates": payload_candidates,
            "matchups": [],
            "finalRecommendation": "At least two candidates are required for debate mode.",
        }

    first, second = candidates[0], candidates[1]
    first_advantages = candidate_advantages(first, second)
    second_advantages = candidate_advantages(second, first)
    first_practical = _metric_value(first, "realLifeUsability") + _metric_value(first, "safety") + _metric_value(first, "stability")
    second_practical = _metric_value(second, "realLifeUsability") + _metric_value(second, "safety") + _metric_value(second, "stability")
    if second_practical > first_practical and _metric_value(first, "power") > _metric_value(second, "power"):
        recommendation = "Use Candidate B for practical reliability. Use Candidate A only if exact timing and aggressive strength matter."
    elif first_practical > second_practical and _metric_value(second, "power") > _metric_value(first, "power"):
        recommendation = "Use Candidate A for practical reliability. Use Candidate B only if exact timing and aggressive strength matter."
    elif first_practical >= second_practical:
        recommendation = "Use Candidate A as the more reliable all-around election."
    else:
        recommendation = "Use Candidate B as the more reliable all-around election."

    return {
        "mode": "Candidate Debate",
        "candidates": payload_candidates,
        "matchups": [
            {
                "first": "Candidate A",
                "second": "Candidate B",
                "firstAdvantages": first_advantages,
                "secondAdvantages": second_advantages,
            }
        ],
        "finalRecommendation": recommendation,
    }


def candidate_debate_lines(
    windows: list[dict[str, object]],
    config: SearchConfig = DEFAULT_SEARCH_CONFIG,
    *,
    top_n: int = 2,
) -> list[str]:
    payload = candidate_debate_payload(windows, config, top_n=top_n)
    if not payload.get("matchups"):
        return [str(payload["finalRecommendation"])]
    matchup = payload["matchups"][0]
    lines = [
        "Candidate Debate Mode",
        "Candidate A beats Candidate B because:",
        *[f"- {reason}" for reason in matchup["firstAdvantages"]],
        "",
        "Candidate B beats Candidate A because:",
        *[f"- {reason}" for reason in matchup["secondAdvantages"]],
        "",
        "Final recommendation:",
    ]
    lines.extend(str(payload["finalRecommendation"]).split(". "))
    return [line if line.endswith(".") or not line.startswith("Use ") else f"{line}." for line in lines]


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


def _moon_applies_to_benefic(window: dict[str, object]) -> bool:
    aspects = window.get("detectedAspects", [])
    for aspect in aspects if isinstance(aspects, list) else []:
        if not isinstance(aspect, dict) or aspect.get("tone") != "support" or not aspect.get("isApplying"):
            continue
        bodies = aspect.get("bodies", [])
        if not isinstance(bodies, list):
            label = str(aspect.get("label") or "")
            bodies = [body for body in ("Moon", "Venus", "Jupiter") if body in label]
        names = {str(body) for body in bodies}
        if "Moon" in names and names & {"Venus", "Jupiter"}:
            return True
    return False


def _window_identity(window: dict[str, object]) -> str:
    moment = window.get("date")
    if isinstance(moment, datetime):
        return moment.isoformat()
    return str(window.get("formattedTime") or window.get("time") or id(window))


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
    tradeoff = str(window.get("tradeoffRole") or "").strip()
    if tradeoff:
        lines.append(f"Tradeoff role: {tradeoff}; Pareto front {window.get('paretoFront', 'n/a')}.")
    lines.extend(multi_objective_lines(window))
    if isinstance(diagnostics, dict):
        cleanliness = diagnostic_score(window, "cleanliness")
        confidence = diagnostic_score(window, "confidence")
        volatility = diagnostic_score(window, "volatility", fallback=99)
        readiness = diagnostic_score(window, "readiness")
        lines.append(f"Diagnostics: confidence {confidence}, cleanliness {cleanliness}, readiness {readiness}, volatility {volatility}.")
        planet_strength = diagnostics.get("planetStrength", [])
        if isinstance(planet_strength, list) and planet_strength:
            valid_rows = [row for row in planet_strength if isinstance(row, dict)]
            if valid_rows:
                strongest = max(valid_rows, key=lambda row: int(row.get("score", 0) or 0))
                weakest = min(valid_rows, key=lambda row: int(row.get("score", 0) or 0))
                lines.append(
                    f"Planet strength: strongest {strongest.get('planet')} {strongest.get('score')} {strongest.get('band')}; "
                    f"weakest {weakest.get('planet')} {weakest.get('score')} {weakest.get('band')}."
                )
    passed_filters = []
    if config.minimum_score is not None:
        passed_filters.append(f"score >= {config.minimum_score}")
    if config.minimum_confidence is not None:
        passed_filters.append(f"confidence >= {config.minimum_confidence}")
    if config.minimum_cleanliness is not None:
        passed_filters.append(f"cleanliness >= {config.minimum_cleanliness}")
    if config.maximum_volatility is not None:
        passed_filters.append(f"volatility <= {config.maximum_volatility}")
    if config.avoid_major_stress:
        passed_filters.append("no major stress")
    if config.require_applying_support:
        passed_filters.append("applying support")
    if config.require_angular_benefic:
        passed_filters.append("angular benefic")
    if config.avoid_angular_malefics:
        passed_filters.append("no angular malefic")
    if passed_filters:
        lines.append("Passed filters: " + ", ".join(passed_filters) + ".")
    if config.target_aspect_text or config.target_aspect_body_text:
        target = config.target_aspect_text or "any aspect"
        if config.target_aspect_body_text:
            target += f" involving {config.target_aspect_body_text}"
        matched = "matched" if has_target_aspect(window, config.target_aspect_text, config.target_aspect_body_text) else "not matched"
        lines.append(f"Target aspect {matched}: {target}.")
    if config.target_planet_text:
        placement = []
        if config.target_sign_text:
            placement.append(f"in {config.target_sign_text}")
        if config.target_house is not None:
            placement.append(f"H{config.target_house}")
        matched = "matched" if has_planet_placement(window, config.target_planet_text, config.target_sign_text, config.target_house) else "not matched"
        lines.append(f"Target placement {matched}: {config.target_planet_text} {' / '.join(placement) or 'anywhere'}.")
    strongest_support = _strongest_aspect_label(window, "support")
    strongest_stress = _strongest_aspect_label(window, "stress")
    if strongest_support:
        lines.append(f"Strongest support: {strongest_support}.")
    if strongest_stress:
        lines.append(f"Strongest stress: {strongest_stress}.")
    lines.extend(timing_precision_lines(window))
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


def why_not_time_lines(
    window: dict[str, object],
    config: SearchConfig = DEFAULT_SEARCH_CONFIG,
    baseline: dict[str, object] | None = None,
    alternatives: list[dict[str, object]] | None = None,
) -> list[str]:
    """Explain why the displayed chart does or does not pass the active search gates."""

    reasons = rejection_reasons(window, config)
    score = int(window.get("score", 0) or 0)
    time_text = str(window.get("formattedTime") or window.get("time") or "time unavailable")
    lines = [
        "Why Not This Time?",
        f"Time: {time_text}",
        f"Score: {score}",
        "",
    ]
    if reasons:
        lines.append("Failed active filters:")
        lines.extend(f"- {reason}" for reason in reasons)
    else:
        lines.append("This time passes the active search filters.")
    repairs = repair_suggestions(window, config, alternatives or [], reasons)
    if repairs:
        lines.extend(["", "Repair suggestions:", *(f"- {repair}" for repair in repairs)])
    nearby = best_nearby_option(window, alternatives or [])
    if nearby:
        lines.extend(["", f"Better nearby option: Use {nearby.get('formattedTime') or nearby.get('time') or 'nearby candidate'} instead."])
        lines.extend(counterfactual_lines(window, nearby))
    lines.extend(
        [
            "",
            "What the engine sees:",
            *(f"- {line}" for line in candidate_explanation_lines(window, baseline, config)),
        ]
    )
    antipatterns = objective_antipattern_notes(window, str(window.get("objective") or ""))
    if antipatterns:
        lines.extend(["", "Objective cautions:", *(f"- {line}" for line in antipatterns)])
    return lines


def best_nearby_option(window: dict[str, object], alternatives: list[dict[str, object]], *, radius_minutes: int = 180) -> dict[str, object] | None:
    current_moment = window.get("date")
    if not isinstance(current_moment, datetime):
        return alternatives[0] if alternatives else None
    candidates = [
        candidate
        for candidate in alternatives
        if isinstance(candidate, dict)
        and isinstance(candidate.get("date"), datetime)
        and candidate.get("date") != current_moment
        and abs(round((candidate["date"] - current_moment).total_seconds() / 60)) <= radius_minutes
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda candidate: (
            int(candidate.get("score", 0) or 0),
            int(multi_objective_metrics(candidate).get("safety", 0)),
            int(multi_objective_metrics(candidate).get("stability", 0)),
        ),
    )


def repair_suggestions(
    window: dict[str, object],
    config: SearchConfig = DEFAULT_SEARCH_CONFIG,
    alternatives: list[dict[str, object]] | None = None,
    reasons: list[str] | None = None,
) -> list[str]:
    """Suggest tactical timing fixes for weak or rejected charts."""

    alternatives = alternatives or []
    reasons = reasons if reasons is not None else rejection_reasons(window, config)
    suggestions: list[str] = []
    current_moment = window.get("date")
    nearby = best_nearby_option(window, alternatives)

    def add_once(text: str) -> None:
        if text and text not in suggestions:
            suggestions.append(text)

    for reason in reasons:
        lowered = reason.lower()
        if "angular malefic" in lowered or "major stress" in lowered:
            repair = _repair_from_nearby(window, nearby, "malefic/stress pressure eases")
            add_once(repair or "Search later in the same day for Mars/Saturn to move away from the angles.")
        elif "moon is void" in lowered or "moon" in lowered and "non-void" in lowered:
            repair = _repair_from_nearby(window, nearby, "Moon condition improves")
            add_once(repair or "Search after the Moon changes sign or reaches its next applying aspect.")
        elif "missing applying support" in lowered:
            repair = _repair_from_nearby(window, nearby, "applying support appears")
            add_once(repair or "Widen the scan until the Moon or matter significator applies to a benefic.")
        elif "confidence" in lowered:
            add_once("Keep the time only for exploration; fix calculation confidence or choose a verified nearby candidate.")
        elif "cleanliness" in lowered or "volatility" in lowered:
            repair = _repair_from_nearby(window, nearby, "cleanliness/stability improves")
            add_once(repair or "Search a nearby plateau with lower volatility before committing.")
        elif "fit" in lowered or "target" in lowered:
            add_once("Change the target/objective or search a wider range; this time does not match the stated matter cleanly.")
        elif "score" in lowered:
            repair = _repair_from_nearby(window, nearby, "overall score improves")
            add_once(repair or "No short-term repair found from the current data; search the next day.")

    moon_condition = window.get("moonCondition", {})
    if isinstance(moon_condition, dict):
        moon = moon_condition.get("moon", {})
        if isinstance(moon, dict) and moon.get("cadency") == "cadent":
            repair = _repair_from_nearby(window, nearby, "Moon leaves cadency or the chart gains safer support")
            add_once(repair or "Moon is cadent; search later for an angular/succedent Moon or stronger applying support.")
    if has_angular_malefic(window):
        repair = _repair_from_nearby(window, nearby, "Mars/Saturn leaves the angle")
        add_once(repair or "Mars/Saturn is angular; search later until the malefic is outside the angular orb.")
    matter = window.get("matterLordContext", {})
    if isinstance(matter, dict) and float(matter.get("scoreImpact", 0) or 0) < -1.0:
        repair = _repair_from_nearby(window, nearby, "Lord of Matter improves")
        add_once(repair or "Lord of Matter is weak. No reliable short-term repair found; search the next day.")
    if not suggestions and int(window.get("score", 0) or 0) < 60:
        add_once(_repair_from_nearby(window, nearby, "score and safety improve") or "No short-term repair found; widen the search.")
    return suggestions[:5]


def _repair_from_nearby(window: dict[str, object], nearby: dict[str, object] | None, reason: str) -> str:
    if not nearby:
        return ""
    current_moment = window.get("date")
    target_moment = nearby.get("date")
    if not isinstance(current_moment, datetime) or not isinstance(target_moment, datetime):
        return f"Use {nearby.get('formattedTime') or nearby.get('time')}: {reason}."
    minutes = round((target_moment - current_moment).total_seconds() / 60)
    direction = "later" if minutes > 0 else "earlier"
    hours, remaining = divmod(abs(minutes), 60)
    if hours and remaining:
        duration = f"{hours}h {remaining}m"
    elif hours:
        duration = f"{hours}h"
    else:
        duration = f"{remaining}m"
    return f"Move chart {duration} {direction}. {reason}; candidate score {nearby.get('score', 'n/a')}."


def counterfactual_payload(before: dict[str, object], after: dict[str, object]) -> dict[str, object]:
    before_metrics = multi_objective_metrics(before)
    after_metrics = multi_objective_metrics(after)
    return {
        "beforeTime": before.get("formattedTime") or before.get("time") or "before",
        "afterTime": after.get("formattedTime") or after.get("time") or "after",
        "before": before_metrics,
        "after": after_metrics,
        "delta": {
            "power": int(after_metrics.get("power", 0)) - int(before_metrics.get("power", 0)),
            "safety": int(after_metrics.get("safety", 0)) - int(before_metrics.get("safety", 0)),
            "stability": int(after_metrics.get("stability", 0)) - int(before_metrics.get("stability", 0)),
            "riskScore": int(after_metrics.get("riskScore", 0)) - int(before_metrics.get("riskScore", 0)),
        },
    }


def counterfactual_lines(before: dict[str, object], after: dict[str, object]) -> list[str]:
    payload = counterfactual_payload(before, after)
    delta = payload["delta"]
    before_metrics = payload["before"]
    after_metrics = payload["after"]
    safety_delta = int(delta["safety"])
    power_delta = int(delta["power"])
    risk_delta = int(delta["riskScore"])
    recommendation = "use the later/alternate time" if safety_delta > 0 and risk_delta <= 0 else "keep comparing; tradeoff is mixed"
    return [
        "Counterfactual analysis:",
        f"- At {payload['beforeTime']}: power {before_metrics.get('power')} safety {before_metrics.get('safety')} stability {before_metrics.get('stability')} risk {before_metrics.get('risk')}.",
        f"- At {payload['afterTime']}: power {after_metrics.get('power')} safety {after_metrics.get('safety')} stability {after_metrics.get('stability')} risk {after_metrics.get('risk')}.",
        f"- Net change: {power_delta:+d} power, {safety_delta:+d} safety, {int(delta['stability']):+d} stability, {risk_delta:+d} risk pressure.",
        f"- Recommendation: {recommendation}.",
    ]


def diagnostic_metric(window: Mapping[str, object], key: str, fallback: int = 50) -> int:
    breakdown = window.get("scoreBreakdown", {})
    diagnostics = breakdown.get("diagnostics", {}) if isinstance(breakdown, Mapping) else {}
    metric = diagnostics.get(key, {}) if isinstance(diagnostics, Mapping) else {}
    if isinstance(metric, Mapping):
        try:
            return int(metric.get("score", fallback) or fallback)
        except (TypeError, ValueError):
            return fallback
    return fallback


def failure_analysis_payload(
    window: dict[str, object],
    config: SearchConfig = DEFAULT_SEARCH_CONFIG,
    alternatives: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Classify why a weak or rejected election fails and how repairable it is."""

    alternatives = alternatives or []
    failure_types: list[str] = []
    reasons: list[str] = []
    moon_condition = window.get("moonCondition", {})
    moon = moon_condition.get("moon", {}) if isinstance(moon_condition, dict) else {}
    if not moon_is_non_void(window):
        failure_types.append("Moon failure")
        reasons.append("Moon is void or lacks a selected applying contact before sign exit.")
    elif isinstance(moon, dict) and moon.get("cadency") == "cadent":
        failure_types.append("Moon failure")
        reasons.append("Moon is cadent and less able to carry the election.")

    matter = window.get("matterLordContext", {})
    if isinstance(matter, dict):
        matter_score = float(matter.get("scoreImpact", 0) or 0)
        if matter_score < -0.75:
            failure_types.append("Lord of Matter failure")
            reasons.append("Lord of Matter judgment is net negative.")

    natal_fit = int(window.get("natalCompatibilityScore", window.get("multiObjective", {}).get("natalFit", 50)) or 50)
    if natal_fit < 45:
        failure_types.append("Natal/profection conflict")
        reasons.append("Natal/profection compatibility is weak or unavailable.")

    if has_angular_malefic(window):
        failure_types.append("Malefic angular damage")
        reasons.append("Mars or Saturn is too close to an angle.")

    afflicted = []
    for planet in window.get("positions", []):
        if not isinstance(planet, dict):
            continue
        solar = planet.get("solarCondition", {})
        if isinstance(solar, dict) and solar.get("phase") in {"combust", "under beams"}:
            afflicted.append(str(planet.get("name") or "planet"))
    if afflicted:
        failure_types.append("Combustion/under beams weakness")
        reasons.append(f"Solar affliction present: {', '.join(afflicted[:3])}.")

    fragility = window.get("fragility")
    if not isinstance(fragility, dict):
        stability_payload = window.get("windowStability", {})
        fragility = stability_payload.get("fragility", {}) if isinstance(stability_payload, dict) else {}
    if isinstance(fragility, dict) and str(fragility.get("band") or "") == "High":
        failure_types.append("Timing fragility")
        reasons.append("The best-looking minute collapses quickly if timing drifts.")

    confidence = diagnostic_metric(window, "confidence")
    hard_warnings = []
    calc_conf = window.get("calculationConfidence", {})
    if isinstance(calc_conf, dict):
        hard_warnings = [str(item) for item in calc_conf.get("hardWarnings", []) if item]
    if confidence < 55 or hard_warnings:
        failure_types.append("Data confidence failure")
        if hard_warnings:
            reasons.append(hard_warnings[0])
        else:
            reasons.append(f"Confidence is only {confidence}.")

    failure_types = list(dict.fromkeys(failure_types))
    if not failure_types and int(window.get("score", 0) or 0) < 60:
        failure_types.append("General weakness")
        reasons.append("The chart does not build enough overall support to justify use.")

    repairs = repair_suggestions(window, config, alternatives, rejection_reasons(window, config))
    nearby = best_nearby_option(window, alternatives)
    repairability = "low"
    if nearby and isinstance(window.get("date"), datetime) and isinstance(nearby.get("date"), datetime):
        minutes = abs(round((nearby["date"] - window["date"]).total_seconds() / 60))
        if minutes <= 30:
            repairability = "high"
        elif minutes <= 120:
            repairability = "medium"
    elif repairs and all("No short-term repair" not in repair for repair in repairs):
        repairability = "medium"

    return {
        "failureTypes": failure_types,
        "failureSummary": " + ".join(failure_types[:2]) if failure_types else "No major failure mode classified.",
        "repairability": repairability,
        "nearestRepair": repairs[0] if repairs else "No nearby repair identified.",
        "reasons": reasons[:5],
        "repairSuggestions": repairs[:4],
    }


def annotate_failure_analysis(
    windows: list[dict[str, object]],
    alternatives: list[dict[str, object]],
    config: SearchConfig = DEFAULT_SEARCH_CONFIG,
) -> list[dict[str, object]]:
    annotated: list[dict[str, object]] = []
    for window in windows:
        item = dict(window)
        item["failureAnalysis"] = failure_analysis_payload(item, config, alternatives)
        annotated.append(item)
    return annotated


def _aspect_match_label(aspect: dict[str, object]) -> str:
    bodies = aspect.get("bodies", [])
    if isinstance(bodies, list) and len(bodies) >= 2:
        body_text = f"{bodies[0]} {aspect.get('aspectName') or aspect.get('label') or 'aspect'} {bodies[1]}"
    else:
        body_text = str(aspect.get("label") or aspect.get("aspectName") or "Aspect")
    return body_text


def aspect_peak_rows(
    windows: list[dict[str, object]],
    aspect_text: str = "",
    body_text: str = "",
    *,
    limit: int = 8,
) -> list[dict[str, object]]:
    """Return closest sampled aspect contacts from already-calculated windows."""

    rows: list[dict[str, object]] = []
    for window in windows:
        aspects = window.get("detectedAspects", [])
        for aspect in aspects if isinstance(aspects, list) else []:
            if not isinstance(aspect, dict):
                continue
            if aspect_text and not any(
                _target_matches_name(value, aspect_text)
                for value in (
                    aspect.get("aspectId"),
                    aspect.get("aspectName"),
                    aspect.get("aspectAbbreviation"),
                    aspect.get("label"),
                )
            ):
                continue
            if body_text:
                bodies = aspect.get("bodies", [])
                if not isinstance(bodies, list) or not any(_target_matches_name(body, body_text) for body in bodies):
                    continue
            try:
                orb = float(aspect.get("orb", 99))
            except (TypeError, ValueError):
                orb = 99.0
            try:
                perfection_orb = float(aspect.get("perfectionOrb", orb))
            except (TypeError, ValueError):
                perfection_orb = orb
            try:
                days_to_exact = abs(float(aspect.get("daysToExact", 9999)))
            except (TypeError, ValueError):
                days_to_exact = 9999.0
            rows.append(
                {
                    "time": str(window.get("formattedTime") or "time unavailable"),
                    "peakTime": str(aspect.get("perfectsAtText") or window.get("formattedTime") or "time unavailable"),
                    "score": int(window.get("score", 0) or 0),
                    "label": _aspect_match_label(aspect),
                    "bodies": tuple(str(body) for body in aspect.get("bodies", []) if body),
                    "aspect": str(aspect.get("aspectName") or aspect.get("label") or "Aspect"),
                    "tone": str(aspect.get("tone") or "mixed"),
                    "orb": orb,
                    "perfectionOrb": perfection_orb,
                    "daysToExact": days_to_exact,
                    "orbText": str(aspect.get("orbText") or f"{orb:.2f} deg"),
                    "phase": "applying" if aspect.get("isApplying") else "separating",
                    "strength": float(aspect.get("strength", max(0.0, 10.0 - orb))),
                    "method": str(aspect.get("timingMethod") or ("ephemeris refined" if aspect.get("perfectsAtText") else "sampled")),
                    "relevance": str(aspect.get("electionalRelevance") or _aspect_peak_relevance(aspect, window)),
                }
            )
    rows.sort(
        key=lambda row: (
            0 if row.get("phase") == "applying" else 1,
            float(row.get("perfectionOrb", row.get("orb", 99))),
            float(row.get("daysToExact", 9999)),
            float(row.get("orb", 99)),
            -int(row.get("score", 0)),
        )
    )
    return rows[: max(0, int(limit))]


def _aspect_peak_relevance(aspect: dict[str, object], window: dict[str, object]) -> str:
    tone = str(aspect.get("tone") or "mixed")
    applying = bool(aspect.get("isApplying"))
    score = int(window.get("score", 0) or 0)
    if tone == "support" and applying:
        return "strong electional support building"
    if tone == "support":
        return "supportive contact, but already separating"
    if tone == "stress" and applying:
        return "active stress to avoid or deliberately manage"
    if tone == "stress":
        return "stress is separating; verify it is fading fast enough"
    if score >= 80:
        return "mixed contact in an otherwise strong window"
    return "mixed contact; compare with cleaner alternatives"


def aspect_peak_lines(
    windows: list[dict[str, object]],
    aspect_text: str = "",
    body_text: str = "",
    *,
    limit: int = 8,
) -> list[str]:
    target = aspect_text or "active aspects"
    if body_text:
        target += f" involving {body_text}"
    rows = aspect_peak_rows(windows, aspect_text, body_text, limit=limit)
    method_note = "exact/perfection timing when available; otherwise closest sampled contact"
    lines = [
        "Aspect Peak Finder",
        f"Target: {target}",
        f"Method: {method_note}.",
        "",
    ]
    if not rows:
        lines.append("No matching aspect contacts were found. Run a wider search or clear the target aspect/body filters.")
        return lines
    for index, row in enumerate(rows, start=1):
        lines.append(
            f"{index}. peak {row['peakTime']} | sampled {row['time']} | {row['label']} | {row['tone']} | "
            f"{row['orbText']} | {row['phase']} | strength {float(row['strength']):.1f} | "
            f"score {row['score']} | {row['method']} | {row['relevance']}"
        )
    return lines


def election_alert_lines(
    windows: list[dict[str, object]],
    config: SearchConfig = DEFAULT_SEARCH_CONFIG,
    *,
    min_score: int | None = None,
    limit: int = 12,
) -> list[str]:
    """Summarize windows that are strong enough to deserve active attention."""

    threshold = int(min_score if min_score is not None else (config.minimum_score if config.minimum_score is not None else 80))
    hits: list[dict[str, object]] = []
    blocked: list[RejectionRecord] = []
    for window in windows:
        score = int(window.get("score", 0) or 0)
        reasons = rejection_reasons(window, config)
        if score >= threshold and not reasons:
            hits.append(window)
        elif reasons:
            repairs = tuple(repair_suggestions(window, config, [], reasons))
            blocked.append(
                RejectionRecord(
                    formatted_time=str(window.get("formattedTime") or "time unavailable"),
                    score=score,
                    reasons=tuple(reasons),
                    repairs=repairs,
                )
            )
    hits = sort_search_windows(hits, config)[: max(0, int(limit))]
    lines = [
        "Election Alerts",
        f"Alert rule: score >= {threshold} and passes active filters.",
        "",
    ]
    if hits:
        lines.append("Alert windows:")
        for index, window in enumerate(hits, start=1):
            reason = candidate_explanation_lines(window, None, config)[-1] if candidate_explanation_lines(window, None, config) else ""
            lines.append(f"{index}. {window.get('formattedTime', 'time unavailable')} | score {window.get('score', 'n/a')} | {reason}")
        return lines
    lines.append("No alert windows passed the current gates.")
    if blocked:
        summary = rejection_summary(blocked)
        top = summary.get("topReasons", [])
        if isinstance(top, list) and top:
            lines.extend(["", "Top blockers:"])
            lines.extend(f"- {reason} ({count})" for reason, count in top[:5])
        suggestions = summary.get("suggestedRelaxations", [])
        if isinstance(suggestions, list) and suggestions:
            lines.extend(["", "Suggested relaxations:"])
            lines.extend(f"- {suggestion}" for suggestion in suggestions[:4])
    return lines


def _strongest_aspect_label(window: dict[str, object], tone: str) -> str:
    aspects = [
        aspect
        for aspect in window.get("detectedAspects", [])
        if isinstance(aspect, dict) and aspect.get("tone") == tone
    ]
    if not aspects:
        return ""
    strongest = min(aspects, key=lambda aspect: float(aspect.get("orb", 99)))
    phase = "applying" if strongest.get("isApplying") else "separating"
    return f"{strongest.get('label', strongest.get('aspectName', 'Aspect'))} ({strongest.get('orbText', 'orb n/a')}, {phase})"


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
    multi_windows = annotate_multi_objective_candidates(windows)
    for window in multi_windows:
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
    seed_count = max(20, config.refinement_seed_count)
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


def final_minute_refinement_offsets(
    windows: list[dict[str, object]],
    base_moment: datetime,
    config: SearchConfig = DEFAULT_SEARCH_CONFIG,
    *,
    seed_count: int = 10,
    radius_minutes: int = 15,
) -> tuple[int, ...]:
    """Return a final 1-minute refinement grid around the strongest candidates."""

    if not config.refine_candidates:
        return ()
    seeds = sort_search_windows(windows, config)[: max(1, int(seed_count))]
    existing = set(config.offsets())
    refined: set[int] = set()
    radius = max(1, int(radius_minutes))
    for seed in seeds:
        moment = seed.get("date")
        if not isinstance(moment, datetime):
            continue
        seed_offset = round((moment - base_moment).total_seconds() / 60)
        for delta in range(-radius, radius + 1):
            candidate = seed_offset + delta
            if config.start_offset_minutes <= candidate <= config.end_offset_minutes and candidate not in existing:
                refined.add(candidate)
    return tuple(sorted(refined))


def exact_transition_refinement_offsets(
    windows: list[dict[str, object]],
    base_moment: datetime,
    config: SearchConfig = DEFAULT_SEARCH_CONFIG,
    *,
    seed_count: int = 10,
    radius_minutes: int = 2,
) -> tuple[int, ...]:
    """Pass 4: add offsets around exact aspect and angle transitions already detected."""

    if not config.refine_candidates:
        return ()
    existing = set(broad_scan_offsets(config))
    refined: set[int] = set()
    radius = max(0, int(radius_minutes))
    seeds = sort_search_windows(windows, config)[: max(1, int(seed_count))]
    for seed in seeds:
        transition_times: list[datetime] = []
        for aspect in seed.get("detectedAspects", []):
            if isinstance(aspect, dict) and isinstance(aspect.get("perfectsAt"), datetime):
                transition_times.append(aspect["perfectsAt"])
        for position in seed.get("positions", []):
            if not isinstance(position, dict):
                continue
            closest_angle = position.get("closestAngle", {})
            if isinstance(closest_angle, dict) and isinstance(closest_angle.get("angleExactAt"), datetime):
                transition_times.append(closest_angle["angleExactAt"])
        for transition in transition_times:
            center_offset = round((transition - base_moment).total_seconds() / 60)
            for delta in range(-radius, radius + 1):
                candidate = center_offset + delta
                if config.start_offset_minutes <= candidate <= config.end_offset_minutes and candidate not in existing:
                    refined.add(candidate)
    return tuple(sorted(refined))


def annotate_timing_precision(
    windows: list[dict[str, object]],
    minute_windows: list[dict[str, object]],
    config: SearchConfig = DEFAULT_SEARCH_CONFIG,
) -> list[dict[str, object]]:
    """Attach best-minute, safe-range, and danger-after timing notes to ranked windows."""

    if not windows:
        return []
    pool = sort_search_windows([*windows, *minute_windows], config)
    annotated: list[dict[str, object]] = []
    for window in windows:
        item = dict(window)
        item["timingPrecision"] = timing_precision_payload(item, pool)
        item["windowStability"] = window_stability_payload(item, pool)
        if isinstance(item["windowStability"], dict):
            item["fragility"] = item["windowStability"].get("fragility", {})
        item["engineRedTeam"] = red_team_payload(item, pool)
        annotated.append(item)
    return annotated


def timing_precision_payload(window: dict[str, object], minute_pool: list[dict[str, object]]) -> dict[str, object]:
    moment = window.get("date")
    if not isinstance(moment, datetime):
        return {}
    score = int(window.get("score", 0) or 0)
    nearby = [
        candidate
        for candidate in minute_pool
        if isinstance(candidate.get("date"), datetime)
        and abs(round((candidate["date"] - moment).total_seconds() / 60)) <= 18
    ]
    safe = [
        candidate
        for candidate in nearby
        if int(candidate.get("score", 0) or 0) >= max(0, score - 4)
        and not has_major_stress(candidate)
    ]
    danger_after = next(
        (
            candidate
            for candidate in sorted(nearby, key=lambda item: item["date"])
            if candidate["date"] > moment and _candidate_danger_score(candidate) >= 2
        ),
        None,
    )
    return {
        "bestWorkingMinute": str(window.get("formattedTime") or window.get("time") or "time unavailable"),
        "safeRange": _safe_range_label(safe),
        "reason": _precision_reason(window),
        "dangerAfter": _danger_after_label(danger_after),
        "method": "60m scan -> top-20 10m refine -> top-10 1m refine -> exact transition solver -> +/-15m stability",
    }


def window_stability_payload(window: dict[str, object], minute_pool: list[dict[str, object]]) -> dict[str, object]:
    """Score the practical tolerance around a chosen minute."""

    moment = window.get("date")
    if not isinstance(moment, datetime):
        return {}
    score = int(window.get("score", 0) or 0)
    nearby = sorted(
        [
            candidate
            for candidate in minute_pool
            if isinstance(candidate.get("date"), datetime)
            and abs(round((candidate["date"] - moment).total_seconds() / 60)) <= 15
        ],
        key=lambda candidate: candidate["date"],
    )
    if not nearby:
        return {
            "classification": "unmeasured",
            "bestMinute": str(window.get("formattedTime") or window.get("time") or "n/a"),
            "stableRange": "No minute-by-minute stability sample available.",
            "dropOffAfter": "Unknown",
            "samples": [],
        }
    samples = [
        {
            "time": str(candidate.get("time") or candidate.get("formattedTime") or ""),
            "score": int(candidate.get("score", 0) or 0),
            "offsetMinutes": round((candidate["date"] - moment).total_seconds() / 60),
        }
        for candidate in nearby
    ]
    stable_threshold = max(0, score - 4)
    stable = [candidate for candidate in nearby if int(candidate.get("score", 0) or 0) >= stable_threshold and _candidate_danger_score(candidate) < 2]
    drop_after = next(
        (
            candidate
            for candidate in nearby
            if candidate["date"] > moment and int(candidate.get("score", 0) or 0) < max(45, score - 8)
        ),
        None,
    )
    stable_minutes = len(stable)
    if stable_minutes >= 7:
        classification = "stable"
    elif stable_minutes >= 3:
        classification = "usable"
    else:
        classification = "fragile"
    fragility = fragility_score_payload(window, nearby, stable_minutes, stable_threshold)
    return {
        "classification": classification,
        "bestMinute": str(window.get("formattedTime") or window.get("time") or "n/a"),
        "stableRange": _safe_range_label(stable),
        "dropOffAfter": _danger_after_label(drop_after) if drop_after else "No sharp drop-off in the sampled range.",
        "threshold": stable_threshold,
        "fragility": fragility,
        "samples": samples,
    }


def fragility_score_payload(
    window: dict[str, object],
    minute_pool: list[dict[str, object]],
    stable_minutes: int | None = None,
    stable_threshold: int | None = None,
) -> dict[str, object]:
    """Estimate how easily a good-looking election collapses if timing drifts."""

    moment = window.get("date")
    nearby = [
        candidate
        for candidate in minute_pool
        if isinstance(candidate.get("date"), datetime)
        and (not isinstance(moment, datetime) or abs(round((candidate["date"] - moment).total_seconds() / 60)) <= 15)
    ]
    scores = [int(candidate.get("score", 0) or 0) for candidate in nearby]
    score = int(window.get("score", 0) or 0)
    threshold = int(stable_threshold if stable_threshold is not None else max(0, score - 4))
    if stable_minutes is None:
        stable_minutes = sum(
            1
            for candidate in nearby
            if int(candidate.get("score", 0) or 0) >= threshold and _candidate_danger_score(candidate) < 2
        )
    reasons: list[str] = []
    fragility = 45
    if stable_minutes >= 25:
        fragility -= 24
        reasons.append("good for roughly 30 minutes in the refined sample")
    elif stable_minutes >= 10:
        fragility -= 7
        reasons.append("usable for about 10-20 minutes")
    else:
        fragility += 22
        reasons.append("good only for a few refined minutes")
    if scores:
        drop = max(scores) - min(scores)
        if drop >= 18:
            fragility += 22
            reasons.append(f"nearby score drops {drop} points")
        elif drop >= 9:
            fragility += 10
            reasons.append(f"nearby score shifts {drop} points")
        else:
            fragility -= 8
            reasons.append("nearby scores stay fairly even")
    if has_angular_malefic(window):
        fragility += 14
        reasons.append("Mars/Saturn angular pressure can flip quickly")
    if _has_near_angle_transition(window, minutes=10):
        fragility += 12
        reasons.append("angle timing is close to a transition")
    if _has_boundary_closeness(window):
        fragility += 8
        reasons.append("body near sign/house boundary")
    if not moon_is_non_void(window):
        fragility += 12
        reasons.append("Moon condition is void or uncertain")
    fragility = _clamp_score(fragility)
    if fragility <= 34:
        band = "Low"
        label = "Low: good for 30+ minutes"
    elif fragility <= 64:
        band = "Medium"
        label = "Medium: good for 10-20 minutes"
    else:
        band = "High"
        label = "High: good only for a few minutes"
    return {
        "score": fragility,
        "band": band,
        "label": label,
        "stableMinutes": int(stable_minutes),
        "threshold": threshold,
        "reasons": reasons[:5],
    }


def window_clusters(
    windows: list[dict[str, object]],
    config: SearchConfig = DEFAULT_SEARCH_CONFIG,
    *,
    max_gap_minutes: int = 12,
    min_score: int | None = None,
) -> list[dict[str, object]]:
    """Group nearby good minutes into user-friendly election windows."""

    dated = [
        window
        for window in windows
        if isinstance(window, dict)
        and isinstance(window.get("date"), datetime)
        and not rejection_reasons(window, config)
    ]
    if not dated:
        return []
    best_score = max(int(window.get("score", 0) or 0) for window in dated)
    threshold = int(min_score if min_score is not None else max(config.minimum_score or 0, 70, best_score - 12))
    candidates = sorted(
        [window for window in dated if int(window.get("score", 0) or 0) >= threshold],
        key=lambda item: item["date"],
    )
    if not candidates:
        return []
    groups: list[list[dict[str, object]]] = []
    for candidate in candidates:
        if not groups:
            groups.append([candidate])
            continue
        gap = round((candidate["date"] - groups[-1][-1]["date"]).total_seconds() / 60)
        if gap <= max(1, int(max_gap_minutes)):
            groups[-1].append(candidate)
        else:
            groups.append([candidate])
    clusters: list[dict[str, object]] = []
    for index, group in enumerate(groups, start=1):
        peak = max(group, key=lambda item: (int(item.get("score", 0) or 0), -_candidate_danger_score(item)))
        start = group[0]
        end = group[-1]
        duration = max(1, round((end["date"] - start["date"]).total_seconds() / 60) + 1)
        fragility = _cluster_fragility(peak, group)
        clusters.append(
            {
                "id": f"cluster-{index}",
                "index": index,
                "startTime": start.get("time") or start.get("formattedTime") or "",
                "endTime": end.get("time") or end.get("formattedTime") or "",
                "startIso": start["date"].isoformat(),
                "endIso": end["date"].isoformat(),
                "range": _cluster_range_label(start, end),
                "peakTime": peak.get("time") or peak.get("formattedTime") or "",
                "peakScore": int(peak.get("score", 0) or 0),
                "type": _cluster_type(peak, duration, fragility),
                "fragility": fragility,
                "durationMinutes": duration,
                "candidateCount": len(group),
                "threshold": threshold,
            }
        )
    return clusters


def annotate_window_clusters(windows: list[dict[str, object]], clusters: list[dict[str, object]]) -> list[dict[str, object]]:
    if not clusters:
        return [dict(window) for window in windows]
    annotated: list[dict[str, object]] = []
    for window in windows:
        item = dict(window)
        moment = item.get("date")
        if isinstance(moment, datetime):
            for cluster in clusters:
                start = _parse_cluster_endpoint(cluster.get("startIso") or cluster.get("startTime"), windows)
                end = _parse_cluster_endpoint(cluster.get("endIso") or cluster.get("endTime"), windows)
                if start and end and start <= moment <= end:
                    item["windowCluster"] = {
                        "index": cluster.get("index"),
                        "range": cluster.get("range"),
                        "type": cluster.get("type"),
                        "fragility": cluster.get("fragility"),
                    }
                    break
        annotated.append(item)
    return annotated


def window_cluster_lines(clusters: list[dict[str, object]], *, limit: int = 5) -> list[str]:
    if not clusters:
        return ["- No window clusters found in the refined candidates."]
    lines: list[str] = []
    for cluster in clusters[: max(1, int(limit))]:
        fragility = cluster.get("fragility", {})
        fragility_label = fragility.get("label", "fragility n/a") if isinstance(fragility, dict) else "fragility n/a"
        lines.extend(
            [
                f"Window Cluster {cluster.get('index', '?')}: {cluster.get('range', 'time unavailable')}",
                f"- Peak: {cluster.get('peakTime', 'n/a')} score {cluster.get('peakScore', 'n/a')}",
                f"- Type: {cluster.get('type', 'workable window')}",
                f"- Fragility: {fragility_label}",
            ]
        )
    return lines


def red_team_payload(window: dict[str, object], minute_pool: list[dict[str, object]]) -> dict[str, object]:
    """Attack a good-looking window so weak spots are explicit."""

    risks: list[str] = []
    repairs: list[str] = []
    stress = _strongest_aspect_label(window, "stress")
    if stress:
        risks.append(f"{stress} is active pressure in the chart.")
    if has_angular_malefic(window):
        risks.append("Mars or Saturn is too close to an angle.")
    if not moon_is_non_void(window):
        risks.append("Moon is void or has no selected applying contact before sign exit.")
    moon_condition = window.get("moonCondition", {})
    if isinstance(moon_condition, dict):
        moon = moon_condition.get("moon", {})
        if isinstance(moon, dict):
            if moon.get("cadency") == "cadent":
                risks.append("Moon is cadent, reducing its ability to carry the election.")
            solar = moon.get("solarCondition", {})
            if isinstance(solar, dict) and solar.get("phase") in {"under beams", "combust"}:
                risks.append(f"Moon is {solar.get('phase')}, so lunar visibility is weakened.")
        final_aspect = moon_condition.get("finalAspectBeforeSignExit")
        next_aspect = moon_condition.get("nextAspect")
        if isinstance(next_aspect, dict) and isinstance(final_aspect, dict) and final_aspect.get("label") != next_aspect.get("label"):
            risks.append(f"Moon's next contact is not the final word; final aspect before exit is {final_aspect.get('label')}.")
    breakdown = window.get("scoreBreakdown", {})
    diagnostics = breakdown.get("diagnostics", {}) if isinstance(breakdown, dict) else {}
    if isinstance(diagnostics, dict):
        cleanliness = diagnostics.get("cleanliness", {})
        if isinstance(cleanliness, dict) and int(cleanliness.get("score", 99) or 99) < 60:
            risks.append(f"Cleanliness is only {cleanliness.get('score')}.")
        confidence = diagnostics.get("confidence", {})
        if isinstance(confidence, dict) and int(confidence.get("score", 99) or 99) < 55:
            risks.append(f"Confidence is only {confidence.get('score')}; treat the result cautiously.")

    moment = window.get("date")
    if isinstance(moment, datetime):
        alternatives = [
            candidate
            for candidate in minute_pool
            if isinstance(candidate.get("date"), datetime)
            and candidate["date"] != moment
            and abs(round((candidate["date"] - moment).total_seconds() / 60)) <= 45
            and int(candidate.get("score", 0) or 0) >= int(window.get("score", 0) or 0) - 3
            and _candidate_danger_score(candidate) < _candidate_danger_score(window)
        ]
        for candidate in sorted(alternatives, key=lambda item: (abs((item["date"] - moment).total_seconds()), -int(item.get("score", 0) or 0)))[:2]:
            offset = round((candidate["date"] - moment).total_seconds() / 60)
            direction = "later" if offset > 0 else "earlier"
            repairs.append(
                f"Move {abs(offset)} minutes {direction}: score {candidate.get('score')} with lower visible risk."
            )
    if not repairs:
        repairs.append("No cleaner nearby repair was found in the refined minute sample; widen the scan or relax constraints.")
    return {
        "summary": "Why this election may fail" if risks else "No major red-team objection surfaced in the active diagnostics.",
        "risks": risks[:6] or ["No major red-team objection surfaced in the active diagnostics."],
        "repairs": repairs[:3],
    }


def timing_precision_lines(window: dict[str, object]) -> list[str]:
    precision = window.get("timingPrecision")
    if not isinstance(precision, dict) or not precision:
        return []
    return [
        f"Best working minute: {precision.get('bestWorkingMinute', 'n/a')}",
        f"Safe range: {precision.get('safeRange', 'n/a')}",
        f"Reason: {precision.get('reason', 'n/a')}",
        f"Danger after: {precision.get('dangerAfter', 'none found in final pass')}",
    ]


def window_stability_lines(window: dict[str, object], *, sample_limit: int = 8) -> list[str]:
    stability = window.get("windowStability")
    if not isinstance(stability, dict) or not stability:
        return ["- Window stability unavailable."]
    lines = [
        f"- Stability: {stability.get('classification', 'n/a')}",
        f"- Best minute: {stability.get('bestMinute', 'n/a')}",
        f"- Stable range: {stability.get('stableRange', 'n/a')}",
        f"- Drop-off after: {stability.get('dropOffAfter', 'n/a')}",
    ]
    samples = stability.get("samples", [])
    if isinstance(samples, list) and samples:
        rows = []
        for sample in samples[:sample_limit]:
            if not isinstance(sample, dict):
                continue
            rows.append(f"{sample.get('time', 'n/a')} score {sample.get('score', '?')}")
        if rows:
            lines.append("- Nearby curve: " + "; ".join(rows))
    return lines


def red_team_lines(window: dict[str, object]) -> list[str]:
    payload = window.get("engineRedTeam")
    if not isinstance(payload, dict) or not payload:
        return ["- Red-team review unavailable."]
    lines = [str(payload.get("summary") or "Why this election may fail")]
    risks = payload.get("risks", [])
    if isinstance(risks, list):
        lines.extend(f"- {risk}" for risk in risks[:6])
    repairs = payload.get("repairs", [])
    if isinstance(repairs, list) and repairs:
        lines.append("Can this be repaired?")
        lines.extend(f"- {repair}" for repair in repairs[:3])
    return lines


def _safe_range_label(windows: list[dict[str, object]]) -> str:
    if not windows:
        return "No clean safe range found around this minute."
    ordered = sorted(windows, key=lambda item: item.get("date"))
    start = str(ordered[0].get("time") or ordered[0].get("formattedTime") or "start")
    end = str(ordered[-1].get("time") or ordered[-1].get("formattedTime") or "end")
    return start if start == end else f"{start} - {end}"


def _precision_reason(window: dict[str, object]) -> str:
    reasons: list[str] = []
    support = _strongest_aspect_label(window, "support")
    if support:
        reasons.append(f"{support} supports the timing")
    if has_angular_benefic(window):
        reasons.append("benefic angularity is present")
    if not has_angular_malefic(window):
        reasons.append("Mars/Saturn are not dominating the angles")
    if moon_is_non_void(window):
        reasons.append("Moon is not void")
    if not reasons:
        reasons.append(str(window.get("note") or "best score among the final refined minutes"))
    return "; ".join(reasons[:3]) + "."


def _danger_after_label(window: dict[str, object] | None) -> str:
    if not isinstance(window, dict):
        return "No immediate danger found in the refined range."
    stress = _strongest_aspect_label(window, "stress")
    reason = stress or str(window.get("note") or "risk rises")
    return f"{window.get('time') or window.get('formattedTime')}: {reason}"


def _candidate_danger_score(window: dict[str, object]) -> int:
    danger = 0
    if has_major_stress(window):
        danger += 1
    if has_angular_malefic(window):
        danger += 1
    if not moon_is_non_void(window):
        danger += 1
    try:
        if int(window.get("score", 0) or 0) < 60:
            danger += 1
    except (TypeError, ValueError):
        pass
    return danger


def _has_near_angle_transition(window: dict[str, object], *, minutes: int = 10) -> bool:
    moment = window.get("date")
    if not isinstance(moment, datetime):
        return False
    for position in window.get("positions", []):
        if not isinstance(position, dict):
            continue
        closest = position.get("closestAngle", {})
        if not isinstance(closest, dict):
            continue
        exact = closest.get("angleExactAt")
        if isinstance(exact, datetime) and abs(round((exact - moment).total_seconds() / 60)) <= minutes:
            return True
    return False


def _has_boundary_closeness(window: dict[str, object], *, degrees: float = 1.0) -> bool:
    for position in window.get("positions", []):
        if not isinstance(position, dict):
            continue
        zodiac = position.get("zodiac", {})
        degree = zodiac.get("degree") if isinstance(zodiac, dict) else None
        try:
            degree_float = float(degree)
        except (TypeError, ValueError):
            continue
        if degree_float <= degrees or degree_float >= 30.0 - degrees:
            return True
    return False


def _cluster_fragility(peak: dict[str, object], group: list[dict[str, object]]) -> dict[str, object]:
    existing = peak.get("fragility")
    if isinstance(existing, dict) and existing:
        return existing
    stability = peak.get("windowStability", {})
    if isinstance(stability, dict):
        nested = stability.get("fragility")
        if isinstance(nested, dict) and nested:
            return nested
    return fragility_score_payload(peak, group)


def _cluster_type(peak: dict[str, object], duration_minutes: int, fragility: dict[str, object]) -> str:
    score = int(peak.get("score", 0) or 0)
    band = str(fragility.get("band") or "")
    risk = str(multi_objective_metrics(peak).get("risk") or "")
    if risk == "High" and score >= 85:
        return "powerful but risky"
    if band == "High" or duration_minutes < 10:
        return "strong but narrow" if score >= 80 else "fragile watch window"
    if band == "Low" or duration_minutes >= 25:
        return "stable practical window"
    if score >= 90:
        return "strong usable window"
    return "workable window"


def _cluster_range_label(start: dict[str, object], end: dict[str, object]) -> str:
    start_label = str(start.get("time") or start.get("formattedTime") or "start")
    end_label = str(end.get("time") or end.get("formattedTime") or "end")
    return start_label if start_label == end_label else f"{start_label}-{end_label}"


def _parse_cluster_endpoint(label: object, windows: list[dict[str, object]]) -> datetime | None:
    label_text = str(label or "")
    try:
        return datetime.fromisoformat(label_text)
    except ValueError:
        pass
    for window in windows:
        if not isinstance(window.get("date"), datetime):
            continue
        if label_text in {
            str(window.get("time") or ""),
            str(window.get("formattedTime") or ""),
        }:
            return window["date"]
    return None


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
    limited = ranked[: config.max_results] if config.max_results else ranked
    threshold_mode = normalize_threshold_mode(config.threshold_mode)
    if threshold_mode == "emergency":
        classified = classify_search_results_by_threshold(limited, "emergency")
        accepted = classified.get("accepted", [])
        if accepted:
            return annotate_rarity_metadata(list(accepted), filtered, config)
        emergency = classified.get("emergencyCandidate")
        return annotate_rarity_metadata([emergency], filtered, config) if isinstance(emergency, dict) else []
    return annotate_rarity_metadata(annotate_multi_objective_candidates(limited), filtered, config)
