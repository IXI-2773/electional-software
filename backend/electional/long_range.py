"""Long-range election scouting and rarity scoring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Mapping

from .engine.search import (
    SearchConfig,
    annotate_multi_objective_candidates,
    diagnostic_score,
    election_grade,
    hard_failure_reasons,
    has_angular_benefic,
    has_angular_malefic,
    has_major_stress,
    moon_is_non_void,
    multi_objective_metrics,
    rank_search_windows,
    sort_search_windows,
    threshold_classification,
    window_clusters,
)
from .judgment import DEFAULT_OBJECTIVE
from .locations import LocationPreset

LONG_RANGE_SCAN_DAYS = (30, 60, 90)


@dataclass(frozen=True)
class LongRangeScoutConfig:
    days: int = 60
    top_n: int = 10
    objective: str = DEFAULT_OBJECTIVE
    similar_score_delta: int = 5
    similar_confidence_delta: int = 5
    cluster_gap_minutes: int = 45

    def __post_init__(self) -> None:
        if self.days not in LONG_RANGE_SCAN_DAYS:
            raise ValueError("Long-range scouting supports 30, 60, or 90 days.")
        if self.top_n <= 0:
            raise ValueError("Long-range scouting top_n must be positive.")


def build_long_range_scout(
    date_text: str,
    time_text: str,
    location: LocationPreset,
    preset_id: str,
    *,
    objective: str = DEFAULT_OBJECTIVE,
    days: int = 60,
    top_n: int = 10,
    selected_aspects: Iterable[str] | None = None,
    zodiac_system_id: str = "tropical",
    house_system_id: str = "whole-sign",
) -> dict[str, object]:
    """Run a real long-range scan through the existing chart/search engine."""

    from .engine.chart import build_election_report

    config = LongRangeScoutConfig(days=days, top_n=top_n, objective=objective)
    search_config = SearchConfig(
        end_offset_minutes=days * 24 * 60,
        max_results=max(top_n * 3, top_n + 12),
        quality_mode="balanced",
        refine_candidates=True,
        refinement_step_minutes=10,
        refinement_seed_count=max(20, top_n * 3),
    )
    report = build_election_report(
        date_text,
        time_text,
        location,
        preset_id,
        selected_aspects,
        zodiac_system_id,
        house_system_id,
        search_config,
        objective,
    )
    windows = list(report.get("windows", []))
    scout = build_long_range_scout_from_windows(windows, config)
    scout["scan"] = {
        "mode": "long-range",
        "searchedWindowCount": report.get("searchedWindowCount", 0),
        "evaluatedWindowCount": report.get("evaluatedWindowCount", 0),
        "refinedWindowCount": report.get("refinedWindowCount", 0),
        "searchMode": report.get("searchMode", ""),
    }
    return scout


def build_long_range_scout_from_windows(
    windows: list[dict[str, object]],
    config: LongRangeScoutConfig,
) -> dict[str, object]:
    """Build deterministic long-range scout output from already-calculated windows."""

    objective = config.objective
    pool = [_prepare_window(window, objective) for window in windows]
    ranked_pool = sort_search_windows(pool, SearchConfig())
    acceptable = [
        window
        for window in ranked_pool
        if bool(threshold_classification(window, "practical").get("accepted"))
    ]
    source = acceptable if acceptable else ranked_pool
    clustered = scout_clusters(source, config)
    if not clustered:
        clustered = [
            {
                "startIso": _window_iso(window),
                "endIso": _window_iso(window),
                "peakIso": _window_iso(window),
                "peak": window,
                "durationMinutes": 1,
                "candidateCount": 1,
            }
            for window in source
        ]

    results = [
        build_long_range_result(cluster, ranked_pool, config, emergency_only=not acceptable)
        for cluster in clustered
    ]
    results = sorted(
        results,
        key=lambda item: (
            int(item.get("score", 0) or 0),
            int(item.get("rarity_score", 0) or 0),
            int(item.get("data_confidence", 0) or 0),
            str(item.get("peak_time", "")),
        ),
        reverse=True,
    )[: config.top_n]

    for index, result in enumerate(results, start=1):
        result["rank"] = index

    status = "usable" if acceptable else ("weak" if results else "none")
    return {
        "objective": objective,
        "days": config.days,
        "top_n": config.top_n,
        "status": status,
        "weak": not bool(acceptable),
        "message": (
            "Top usable long-range election windows."
            if acceptable
            else "No clean election was found; returning least-bad weak options."
        ),
        "scanned_window_count": len(ranked_pool),
        "acceptable_window_count": len(acceptable),
        "results": results,
    }


def scout_clusters(windows: list[dict[str, object]], config: LongRangeScoutConfig) -> list[dict[str, object]]:
    if not windows:
        return []
    clusters = window_clusters(
        windows,
        SearchConfig(),
        max_gap_minutes=config.cluster_gap_minutes,
        min_score=0,
    )
    clustered: list[dict[str, object]] = []
    for cluster in clusters:
        peak_iso = str(cluster.get("peakIso") or "")
        peak = _peak_for_cluster(cluster, windows)
        if not peak:
            continue
        item = dict(cluster)
        item["peak"] = peak
        item["peakIso"] = peak_iso or _window_iso(peak)
        clustered.append(item)
    if clustered:
        return clustered
    return [
        {
            "startIso": _window_iso(window),
            "endIso": _window_iso(window),
            "peakIso": _window_iso(window),
            "peak": window,
            "durationMinutes": 1,
            "candidateCount": 1,
        }
        for window in sort_search_windows(windows, SearchConfig())
    ]


def build_long_range_result(
    cluster: Mapping[str, object],
    comparison_pool: list[dict[str, object]],
    config: LongRangeScoutConfig,
    *,
    emergency_only: bool = False,
) -> dict[str, object]:
    peak = cluster.get("peak")
    if not isinstance(peak, dict):
        peak = {}
    rarity = rarity_payload(peak, comparison_pool, config)
    confidence = diagnostic_score(peak, "confidence")
    score = int(peak.get("score", 0) or 0)
    roles = condition_roles(peak, rarity, emergency_only)
    profile = condition_profile(peak, config.objective)
    return {
        "start_time": _cluster_time(cluster, "startIso", peak),
        "end_time": _cluster_time(cluster, "endIso", peak),
        "usable_window": _usable_window(cluster, peak),
        "peak_time": _cluster_time(cluster, "peakIso", peak),
        "objective": config.objective,
        "score": score,
        "grade": long_range_grade(score),
        "data_confidence": confidence,
        "rarity_score": rarity["rarity_score"],
        "rarity_label": rarity["rarity_label"],
        "similar_windows_count": rarity["similar_windows_count"],
        "comparison_range_days": config.days,
        "percentile": rarity["percentile"],
        "rarity_reason": rarity["reason"],
        "top_supporting_factors": top_supporting_factors(peak, config.objective),
        "top_risks": top_risks(peak, emergency_only),
        "condition_profile": profile,
        "condition_groups": profile.split(" + ") if profile else [],
        "classification": roles,
        "action_guidance": action_guidance(rarity, score, emergency_only),
        "cluster": {
            "duration_minutes": int(cluster.get("durationMinutes", 1) or 1),
            "candidate_count": int(cluster.get("candidateCount", 1) or 1),
        },
        "weak": emergency_only,
    }


def rarity_payload(
    candidate: dict[str, object],
    comparison_pool: list[dict[str, object]],
    config: LongRangeScoutConfig,
) -> dict[str, object]:
    scored = [
        (window, rarity_condition_score(window, config.objective))
        for window in comparison_pool
        if not hard_failure_reasons(window)
    ]
    candidate_score = rarity_condition_score(candidate, config.objective)
    if not scored:
        return _rarity_result(
            min(candidate_score, 49),
            "Common",
            0,
            0.0,
            config.days,
            "Hard failures prevent this window from being rare-good.",
        )

    better_or_equal = sum(1 for _window, score in scored if score >= candidate_score)
    total = len(scored)
    percentile = round(100.0 * (total - better_or_equal + 1) / total, 1)
    similar_count = similar_windows_count(candidate, [window for window, _score in scored], config)
    scarcity_score = 100 if similar_count == 0 else max(0, round(100 - (similar_count / max(total, 1)) * 100))
    rarity_score = _clamp(round(candidate_score * 0.55 + percentile * 0.25 + scarcity_score * 0.20))
    label = rarity_label(percentile, better_or_equal, similar_count, total)
    if hard_failure_reasons(candidate):
        label = "Common"
        rarity_score = min(rarity_score, 49)
    reason = (
        f"Only {similar_count} windows in the next {config.days} days have comparable score, "
        "core condition profile, malefic control, and data confidence."
    )
    return _rarity_result(rarity_score, label, similar_count, percentile, config.days, reason)


def rarity_condition_score(window: dict[str, object], objective: str = DEFAULT_OBJECTIVE) -> int:
    metrics = multi_objective_metrics(window)
    score = int(window.get("score", 0) or 0) * 0.22
    score += int(metrics.get("moon", 0) or 0) * 0.13
    score += int(metrics.get("matter", 0) or 0) * 0.11
    score += int(metrics.get("lowMaleficDamage", 0) or 0) * 0.13
    score += int(metrics.get("dataConfidence", 0) or 0) * 0.12
    score += int(metrics.get("stability", 0) or 0) * 0.11
    score += int(metrics.get("natalFit", 0) or 0) * 0.08
    score += 5 if has_angular_benefic(window) else 0
    score += 5 if moon_applying_to_benefic(window) else 0
    score += 4 if mercury_clean(window, objective) else 0
    score -= 18 if hard_failure_reasons(window) else 0
    return _clamp(round(score))


def similar_windows_count(
    candidate: dict[str, object],
    comparison_pool: list[dict[str, object]],
    config: LongRangeScoutConfig,
) -> int:
    candidate_score = int(candidate.get("score", 0) or 0)
    candidate_conf = diagnostic_score(candidate, "confidence")
    candidate_tags = set(condition_profile_tags(candidate, config.objective))
    candidate_time = candidate.get("date")
    count = 0
    for window in comparison_pool:
        if window is candidate:
            continue
        if candidate_time is not None and window.get("date") == candidate_time:
            continue
        if hard_failure_reasons(window):
            continue
        score = int(window.get("score", 0) or 0)
        confidence = diagnostic_score(window, "confidence")
        if score < candidate_score - config.similar_score_delta:
            continue
        if confidence < candidate_conf - config.similar_confidence_delta:
            continue
        tags = set(condition_profile_tags(window, config.objective))
        shared = len(candidate_tags & tags)
        if shared >= 2 or (not candidate_tags and not tags):
            count += 1
    return count


def rarity_label(percentile: float, better_or_equal_count: int, similar_count: int, total: int) -> str:
    peer_limit = max(1, round(total * 0.02))
    if better_or_equal_count == 1 and similar_count == 0:
        return "Unique"
    if better_or_equal_count <= max(2, peer_limit) and percentile >= 98 and similar_count <= 1:
        return "Very Rare"
    if percentile >= 93 and similar_count <= 3:
        return "Rare"
    if percentile >= 80:
        return "Uncommon"
    return "Common"


def condition_profile(window: dict[str, object], objective: str = DEFAULT_OBJECTIVE) -> str:
    tags = condition_profile_tags(window, objective)
    return " + ".join(tags) if tags else "general mixed conditions"


def condition_profile_tags(window: dict[str, object], objective: str = DEFAULT_OBJECTIVE) -> list[str]:
    tags: list[str] = []
    metrics = multi_objective_metrics(window)
    if moon_applying_to_benefic(window):
        tags.append("Moon-benefic")
    if mercury_clean(window, objective):
        tags.append("Mercury-clean")
    if has_angular_benefic(window):
        tags.append("Jupiter/Venus-supported")
    if int(metrics.get("matter", 0) or 0) >= 58:
        tags.append("Lord of Matter strong")
    if int(metrics.get("lowMaleficDamage", 0) or 0) >= 75:
        tags.append("low malefic pressure")
    if int(metrics.get("natalFit", 0) or 0) >= 70:
        tags.append("natal/profection-aligned")
    if int(metrics.get("stability", 0) or 0) >= 72:
        tags.append("stable practical")
    if int(metrics.get("power", 0) or 0) >= 90 and int(metrics.get("stability", 0) or 0) < 55:
        tags.append("aggressive but fragile")
    return tags


def condition_roles(window: dict[str, object], rarity: Mapping[str, object], emergency_only: bool) -> list[str]:
    if emergency_only:
        return ["Least-bad emergency window"]
    metrics = multi_objective_metrics(window)
    roles: list[str] = []
    if int(metrics.get("power", 0) or 0) >= 90:
        roles.append("Best aggressive window")
    if int(metrics.get("safety", 0) or 0) >= 78:
        roles.append("Best safe window")
    if int(metrics.get("realLifeUsability", 0) or 0) >= 76:
        roles.append("Best practical window")
    if str(rarity.get("rarity_label")) in {"Rare", "Very Rare", "Unique"} and int(window.get("score", 0) or 0) >= 80:
        roles.append("Rare high-quality window")
    return roles or ["Usable long-range window"]


def top_supporting_factors(window: dict[str, object], objective: str = DEFAULT_OBJECTIVE) -> list[str]:
    metrics = multi_objective_metrics(window)
    factors: list[tuple[int, str]] = []
    if moon_is_non_void(window):
        factors.append((int(metrics.get("moon", 0) or 0), f"Moon condition {metrics.get('moon', 0)}"))
    if has_angular_benefic(window):
        factors.append((86, "Venus/Jupiter angular support present"))
    if moon_applying_to_benefic(window):
        factors.append((88, "Moon applying to benefic support"))
    if mercury_clean(window, objective):
        factors.append((82, "Mercury clean for the selected objective"))
    factors.extend(
        [
            (int(metrics.get("matter", 0) or 0), f"Lord of Matter strength {metrics.get('matter', 0)}"),
            (int(metrics.get("lowMaleficDamage", 0) or 0), f"Malefic control {metrics.get('lowMaleficDamage', 0)}"),
            (int(metrics.get("dataConfidence", 0) or 0), f"Data confidence {metrics.get('dataConfidence', 0)}"),
            (int(metrics.get("stability", 0) or 0), f"Window stability {metrics.get('stability', 0)}"),
            (int(metrics.get("natalFit", 0) or 0), f"Natal/profection fit {metrics.get('natalFit', 0)}"),
        ]
    )
    return [label for _score, label in sorted(factors, key=lambda item: (-item[0], item[1]))[:3]]


def top_risks(window: dict[str, object], emergency_only: bool = False) -> list[str]:
    risks = list(hard_failure_reasons(window))
    metrics = multi_objective_metrics(window)
    fragility = window.get("fragility")
    if not isinstance(fragility, dict):
        stability = window.get("windowStability", {})
        fragility = stability.get("fragility", {}) if isinstance(stability, dict) else {}
    if isinstance(fragility, dict) and fragility.get("band") in {"Medium", "High"}:
        risks.append(f"{fragility.get('band')} timing fragility")
    volatility = diagnostic_score(window, "volatility", fallback=0)
    if volatility >= 55:
        risks.append(f"Volatility {volatility}")
    if int(metrics.get("stability", 0) or 0) < 55:
        risks.append(f"Window stability only {metrics.get('stability', 0)}")
    if emergency_only:
        risks.append("Emergency-only: no clean election met practical thresholds")
    return list(dict.fromkeys(risks))[:3] or ["No major risk flags in the scanned metrics"]


def action_guidance(rarity: Mapping[str, object], score: int, emergency_only: bool) -> str:
    if emergency_only:
        return "Use only if the election cannot wait; otherwise widen the range or relax the objective."
    label = str(rarity.get("rarity_label") or "")
    similar = int(rarity.get("similar_windows_count", 0) or 0)
    if score >= 85 and label in {"Rare", "Very Rare", "Unique"}:
        return "Act now: this is uncommon enough to prioritize in the selected range."
    if similar >= 5:
        return "Wait or compare: similar-quality windows are available in the same range."
    return "Usable now, but compare the listed peers before committing."


def long_range_grade(score: int) -> str:
    if score >= 94:
        return "A+"
    if score >= 90:
        return "A"
    if score >= 86:
        return "A-"
    if score >= 82:
        return "B+"
    if score >= 78:
        return "B"
    if score >= 75:
        return "C+"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def moon_applying_to_benefic(window: Mapping[str, object]) -> bool:
    for aspect in window.get("detectedAspects", []):
        if not isinstance(aspect, Mapping) or not aspect.get("isApplying") or aspect.get("tone") != "support":
            continue
        bodies = aspect.get("bodies", [])
        if not isinstance(bodies, list):
            label = str(aspect.get("label") or "")
            bodies = [body for body in ("Moon", "Venus", "Jupiter") if body in label]
        names = {str(body) for body in bodies}
        if "Moon" in names and names & {"Venus", "Jupiter"}:
            return True
    return False


def mercury_clean(window: Mapping[str, object], objective: str = DEFAULT_OBJECTIVE) -> bool:
    objective_text = objective.lower()
    if not any(token in objective_text for token in ("exam", "message", "contract", "write", "study", "mercury")):
        return False
    for position in window.get("positions", []):
        if not isinstance(position, Mapping) or position.get("name") != "Mercury":
            continue
        if position.get("isRetrograde"):
            return False
        solar = position.get("solarCondition", {})
        if isinstance(solar, Mapping) and solar.get("phase") in {"combust", "under beams"}:
            return False
        return True
    return False


def format_long_range_scout_text(payload: Mapping[str, object]) -> str:
    objective = payload.get("objective", "Election")
    days = payload.get("days", "?")
    lines = [f"Best {objective} windows in next {days} days:"]
    for result in payload.get("results", []):
        if not isinstance(result, Mapping):
            continue
        lines.extend(
            [
                "",
                f"{result.get('rank')}. {result.get('usable_window')}",
                f"   Peak: {result.get('peak_time')}",
                f"   Grade: {result.get('grade')} | Score: {result.get('score')} | Data confidence: {result.get('data_confidence')}",
                f"   Rarity: {result.get('rarity_label')} ({result.get('rarity_score')})",
                f"   Similar windows in range: {result.get('similar_windows_count')}",
                f"   Condition profile: {result.get('condition_profile')}",
                f"   Reason: {'; '.join(result.get('top_supporting_factors', []))}",
                f"   Risk: {'; '.join(result.get('top_risks', []))}",
                f"   Guidance: {result.get('action_guidance')}",
            ]
        )
    if not payload.get("results"):
        lines.append("No candidate windows were available.")
    return "\n".join(lines)


def _prepare_window(window: dict[str, object], objective: str) -> dict[str, object]:
    item = dict(window)
    item["objective"] = str(item.get("objective") or objective)
    item["multiObjective"] = dict(item.get("multiObjective") or multi_objective_metrics(item))
    return item


def _peak_for_cluster(cluster: Mapping[str, object], windows: list[dict[str, object]]) -> dict[str, object] | None:
    start = _parse_iso(cluster.get("startIso"))
    end = _parse_iso(cluster.get("endIso"))
    if not start or not end:
        return None
    matches = [
        window
        for window in windows
        if isinstance(window.get("date"), datetime)
        and start <= window["date"] <= end
    ]
    if not matches:
        return None
    return max(matches, key=lambda item: (int(item.get("score", 0) or 0), rarity_condition_score(item)))


def _usable_window(cluster: Mapping[str, object], peak: Mapping[str, object]) -> str:
    start = _cluster_time(cluster, "startIso", peak)
    end = _cluster_time(cluster, "endIso", peak)
    return start if start == end else f"{start}-{end}"


def _cluster_time(cluster: Mapping[str, object], key: str, peak: Mapping[str, object]) -> str:
    value = cluster.get(key)
    if value:
        return _format_iso(value)
    return _format_iso(_window_iso(peak))


def _format_iso(value: object) -> str:
    text = str(value or "")
    try:
        return datetime.fromisoformat(text).strftime("%Y-%m-%d %I:%M %p")
    except ValueError:
        return text


def _window_iso(window: Mapping[str, object]) -> str:
    moment = window.get("date")
    if isinstance(moment, datetime):
        return moment.isoformat()
    return str(window.get("formattedTime") or window.get("time") or "")


def _parse_iso(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _rarity_result(
    score: int,
    label: str,
    similar_count: int,
    percentile: float,
    days: int,
    reason: str,
) -> dict[str, object]:
    return {
        "rarity_score": score,
        "rarity_label": label,
        "similar_windows_count": similar_count,
        "comparison_range_days": days,
        "percentile": percentile,
        "reason": reason,
    }


def _clamp(value: int) -> int:
    return max(0, min(99, int(value)))
