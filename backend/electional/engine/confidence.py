"""Calculation trust diagnostics for electional charts."""

from __future__ import annotations

from typing import Mapping, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..location_search import expected_timezone_for_coordinates
from ..locations import LocationPreset


def build_calculation_confidence(
    *,
    backend_status: Mapping[str, object] | None,
    accuracy_audit: Mapping[str, object] | None,
    location: LocationPreset,
    house_cusps: Sequence[Mapping[str, object]],
    moon_condition: Mapping[str, object] | None,
    fixed_star_contacts: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Judge how trustworthy the calculation data is, separate from chart quality."""

    penalties: list[dict[str, object]] = []
    hard_warnings: list[str] = []

    def add(code: str, label: str, value: int, detail: str, *, hard: bool = False) -> None:
        penalties.append({"code": code, "label": label, "value": -abs(int(value)), "detail": detail, "hardWarning": hard})
        if hard:
            hard_warnings.append(detail)

    backend_status = backend_status or {}
    accuracy_audit = accuracy_audit or {}
    if backend_status.get("fallbackActive") or accuracy_audit.get("status") == "fallback":
        add("swiss-missing", "Swiss missing", 15, "Swiss Ephemeris is unavailable; fallback planetary calculations are active.")
    elif accuracy_audit.get("verified") is False:
        add("accuracy-warning", "Accuracy warning", 8, str(accuracy_audit.get("summary") or "Accuracy audit did not verify cleanly."))

    cusp_sources = sorted({str(cusp.get("source") or "") for cusp in house_cusps if cusp.get("source")})
    fallback_sources = [source for source in cusp_sources if "fallback" in source.lower()]
    if fallback_sources:
        add("house-fallback", "House fallback active", 12, f"House cusps use fallback source(s): {', '.join(fallback_sources)}.")

    timezone_warning = timezone_trust_warning(location)
    if timezone_warning:
        add("timezone-warning", "Timezone uncertain", 20, timezone_warning, hard=True)

    void_data = moon_condition.get("voidOfCourse", {}) if isinstance(moon_condition, Mapping) else {}
    if isinstance(void_data, Mapping) and str(void_data.get("confidence") or "").lower() == "approximate":
        add("moon-voc-approximate", "Moon VOC approximate", 10, "Moon void-of-course status is approximate and based on selected applying aspects.")

    longitude_only_count = sum(
        1
        for contact in fixed_star_contacts
        if isinstance(contact, Mapping) and str(contact.get("precision") or "") == "longitude-only"
    )
    if longitude_only_count:
        add(
            "fixed-star-longitude-only",
            "Fixed-star longitude-only",
            3,
            f"{longitude_only_count} fixed-star contact(s) are longitude-only without latitude confirmation.",
        )

    total_penalty = sum(abs(int(item["value"])) for item in penalties)
    score = max(0, 99 - total_penalty)
    return {
        "score": score,
        "band": calculation_confidence_band(score, bool(hard_warnings)),
        "penalty": total_penalty,
        "penalties": penalties,
        "hardWarnings": hard_warnings,
        "summary": calculation_confidence_summary(score, total_penalty, hard_warnings),
    }


def timezone_trust_warning(location: LocationPreset) -> str:
    try:
        ZoneInfo(location.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return f"Timezone {location.timezone or 'blank'} is not a valid IANA timezone."
    expected = expected_timezone_for_coordinates(location.latitude, location.longitude, location.name)
    if expected and expected != location.timezone:
        return f"{location.name} looks closer to {expected}, not {location.timezone}."
    return ""


def calculation_confidence_band(score: int, hard_warning: bool = False) -> str:
    if hard_warning:
        return "Hard Warning"
    if score >= 85:
        return "High"
    if score >= 70:
        return "Usable"
    if score >= 55:
        return "Caution"
    return "Weak"


def calculation_confidence_summary(score: int, penalty: int, hard_warnings: Sequence[str]) -> str:
    if hard_warnings:
        return f"Hard warning: calculation trust {score}/99 after -{penalty} confidence penalty."
    if penalty:
        return f"Calculation trust {score}/99 after -{penalty} confidence penalty."
    return "Calculation trust is high; no confidence penalties applied."


def apply_calculation_confidence_penalty(
    score_breakdown: dict[str, object],
    calculation_confidence: Mapping[str, object],
) -> dict[str, object]:
    """Apply calculation trust penalties to the existing confidence diagnostic."""

    diagnostics = score_breakdown.get("diagnostics")
    if not isinstance(diagnostics, dict):
        return score_breakdown
    diagnostics["calculationConfidence"] = dict(calculation_confidence)
    confidence = diagnostics.get("confidence")
    if not isinstance(confidence, dict):
        return score_breakdown
    try:
        original = int(confidence.get("score", 0) or 0)
        penalty = int(calculation_confidence.get("penalty", 0) or 0)
    except (TypeError, ValueError):
        return score_breakdown
    adjusted = max(0, original - penalty)
    confidence["rawScoreBeforeCalculationPenalty"] = original
    confidence["score"] = adjusted
    confidence["band"] = calculation_confidence_band(adjusted, bool(calculation_confidence.get("hardWarnings")))
    confidence["summary"] = (
        f"{confidence.get('summary', 'Confidence adjusted by calculation trust.')} "
        f"Calculation trust penalty -{penalty}; raw confidence {original}."
    )
    return score_breakdown

