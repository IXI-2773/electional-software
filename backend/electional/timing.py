"""Electional timing summaries derived from calculated aspects."""

from __future__ import annotations

from typing import Mapping, Sequence


def applying_aspects_with_timing(aspects: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    return sorted(
        [
            aspect
            for aspect in aspects
            if aspect.get("isApplying") and aspect.get("daysToExact") is not None
        ],
        key=lambda aspect: float(aspect.get("daysToExact", 999)),
    )


def aspect_brief(aspect: Mapping[str, object] | None) -> dict[str, object] | None:
    if not aspect:
        return None
    return {
        "label": aspect.get("label", "Aspect"),
        "tone": aspect.get("tone", "mixed"),
        "orbText": aspect.get("orbText", ""),
        "timeToExactText": aspect.get("timeToExactText", ""),
        "perfectsAtText": aspect.get("perfectsAtText", ""),
        "timingQuality": aspect.get("timingQuality", ""),
    }


def timing_profile(aspects: Sequence[Mapping[str, object]]) -> dict[str, object]:
    applying = applying_aspects_with_timing(aspects)
    supportive = [aspect for aspect in applying if aspect.get("tone") == "support"]
    stressful = [aspect for aspect in applying if aspect.get("tone") == "stress"]
    mixed = [aspect for aspect in applying if aspect.get("tone") == "mixed"]
    next_aspect = applying[0] if applying else None
    next_support = supportive[0] if supportive else None
    next_stress = stressful[0] if stressful else None
    return {
        "applyingCount": len(applying),
        "supportCount": len(supportive),
        "stressCount": len(stressful),
        "mixedCount": len(mixed),
        "nextAspect": aspect_brief(next_aspect),
        "nextSupport": aspect_brief(next_support),
        "nextStress": aspect_brief(next_stress),
        "summary": timing_summary(next_aspect, next_support, next_stress),
    }


def timing_summary(
    next_aspect: Mapping[str, object] | None,
    next_support: Mapping[str, object] | None,
    next_stress: Mapping[str, object] | None,
) -> str:
    if not next_aspect:
        return "No applying selected aspects have a near-term perfection estimate."
    next_label = str(next_aspect.get("label", "Aspect"))
    next_time = str(next_aspect.get("timeToExactText") or "timing unknown")
    parts = [f"Next exact contact: {next_label} in {next_time}."]
    if next_support:
        parts.append(f"Next support: {next_support.get('label')} in {next_support.get('timeToExactText')}.")
    if next_stress:
        parts.append(f"Next stress: {next_stress.get('label')} in {next_stress.get('timeToExactText')}.")
    return " ".join(parts)
