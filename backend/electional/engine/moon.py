"""Technical Moon condition diagnostics for electional judgment."""

from __future__ import annotations

from typing import Mapping, Sequence

from ..aspects import angular_distance, format_duration, format_orb

BENEFICS = {"Venus", "Jupiter"}
MALEFICS = {"Mars", "Saturn"}


def _position_by_name(positions: Sequence[Mapping[str, object]]) -> dict[str, Mapping[str, object]]:
    return {str(position.get("name")): position for position in positions}


def _factor(
    factor_id: str,
    title: str,
    detail: str,
    score: float = 0.0,
    severity: str = "info",
) -> dict[str, object]:
    return {
        "id": factor_id,
        "category": "moon",
        "severity": severity,
        "title": title,
        "detail": detail,
        "body": "Moon",
        "scoreImpact": score,
    }


def _speed_label(daily_speed: float) -> str:
    speed = abs(daily_speed)
    if speed >= 13.5:
        return "fast"
    if speed <= 11.5:
        return "slow"
    return "normal"


def _cadency_label(house: object) -> str:
    try:
        house_number = int(house)
    except (TypeError, ValueError):
        return "unknown"
    if house_number in {1, 4, 7, 10}:
        return "angular"
    if house_number in {3, 6, 9, 12}:
        return "cadent"
    return "succedent"


def _days_to_sign_exit(moon: Mapping[str, object], daily_speed: float) -> tuple[float, float]:
    zodiac = moon.get("zodiac") if isinstance(moon.get("zodiac"), Mapping) else {}
    degree = float(zodiac.get("degree", 0) or 0) + float(zodiac.get("minute", 0) or 0) / 60
    span = float(zodiac.get("spanDegrees", 30) or 30) if isinstance(zodiac, Mapping) else 30.0
    distance = max(0.0, span - degree)
    days = distance / max(abs(daily_speed), 0.01)
    return distance, days


def _moon_aspects(detected_aspects: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    return [
        aspect
        for aspect in detected_aspects
        if isinstance(aspect, Mapping) and "Moon" in [str(body) for body in aspect.get("bodies", [])]
    ]


def _aspect_days(aspect: Mapping[str, object]) -> float | None:
    value = aspect.get("daysToExact")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _aspect_other_body(aspect: Mapping[str, object]) -> str:
    bodies = [str(body) for body in aspect.get("bodies", [])]
    return next((body for body in bodies if body != "Moon"), "")


def _aspect_snapshot(aspect: Mapping[str, object] | None) -> dict[str, object] | None:
    if not isinstance(aspect, Mapping):
        return None
    return {
        "label": aspect.get("label"),
        "aspectId": aspect.get("aspectId"),
        "aspectName": aspect.get("aspectName"),
        "aspectGlyph": aspect.get("aspectGlyph"),
        "tone": aspect.get("tone"),
        "orb": aspect.get("orb"),
        "orbText": aspect.get("orbText"),
        "phase": aspect.get("phase"),
        "phaseLabel": aspect.get("phaseLabel"),
        "isApplying": aspect.get("isApplying"),
        "daysToExact": aspect.get("daysToExact"),
        "timeToExactText": aspect.get("timeToExactText"),
        "perfectsAtText": aspect.get("perfectsAtText"),
        "timingMethod": aspect.get("timingMethod"),
        "bodies": list(aspect.get("bodies", [])),
    }


def _solar_status(moon: Mapping[str, object], sun: Mapping[str, object] | None) -> dict[str, object]:
    if not isinstance(sun, Mapping):
        return {"phase": "unknown", "separation": None, "detail": "Solar distance unavailable."}
    separation = angular_distance(float(moon.get("longitude", 0)), float(sun.get("longitude", 0)))
    if separation <= 0.283333:
        phase = "cazimi"
        score = 1.0
        detail = f"Moon is in the heart of the Sun ({format_orb(separation)})."
    elif separation <= 8.5:
        phase = "combust"
        score = -2.0
        detail = f"Moon is combust the Sun ({format_orb(separation)})."
    elif separation <= 15:
        phase = "under beams"
        score = -1.0
        detail = f"Moon is under the Sun's beams ({format_orb(separation)})."
    else:
        phase = "clear"
        score = 0.0
        detail = f"Moon is clear of the Sun's beams ({format_orb(separation)})."
    return {"phase": phase, "separation": separation, "scoreImpact": score, "detail": detail}


def build_moon_condition(
    positions: Sequence[Mapping[str, object]],
    detected_aspects: Sequence[Mapping[str, object]],
    lunar_phase: Mapping[str, object],
) -> dict[str, object]:
    """Return strict Moon diagnostics independent of traditional rulership scoring."""

    by_name = _position_by_name(positions)
    moon = by_name.get("Moon")
    if not isinstance(moon, Mapping):
        return {
            "summary": "Moon condition unavailable.",
            "factors": [],
            "scoreImpact": 0.0,
            "confidence": "low",
        }

    motion = moon.get("motion") if isinstance(moon.get("motion"), Mapping) else {}
    daily_speed = float(motion.get("dailyLongitudeChange", 0) or 0) if isinstance(motion, Mapping) else 0.0
    speed = _speed_label(daily_speed)
    distance_to_exit, days_to_exit = _days_to_sign_exit(moon, daily_speed)
    aspects = _moon_aspects(detected_aspects)
    applying = [aspect for aspect in aspects if aspect.get("isApplying") is True and _aspect_days(aspect) is not None]
    separating = [aspect for aspect in aspects if aspect.get("isApplying") is False]
    applying_before_exit = [
        aspect for aspect in applying if (_aspect_days(aspect) or 999.0) <= days_to_exit
    ]
    next_aspect = min(applying_before_exit, key=lambda aspect: float(_aspect_days(aspect) or 999.0), default=None)
    final_aspect = max(applying_before_exit, key=lambda aspect: float(_aspect_days(aspect) or -1.0), default=None)
    recent_separating = min(separating, key=lambda aspect: float(aspect.get("orb", 999) or 999), default=None)
    is_void = next_aspect is None
    house = moon.get("house")
    cadency = _cadency_label(house)
    solar = _solar_status(moon, by_name.get("Sun"))

    factors: list[dict[str, object]] = []
    if is_void:
        factors.append(
            _factor(
                "moon-void-exact",
                "Moon void of course",
                "No applying selected Moon aspect perfects before the Moon exits its current sign.",
                -3.0,
                "warning",
            )
        )
    else:
        other = _aspect_other_body(next_aspect)
        score = 1.5 if other in BENEFICS else -1.5 if other in MALEFICS else 0.5 if next_aspect.get("tone") == "support" else -0.5 if next_aspect.get("tone") == "stress" else 0.0
        factors.append(
            _factor(
                f"moon-next-{other.lower() or 'aspect'}",
                f"Next Moon aspect: {next_aspect.get('label', 'Moon aspect')}",
                f"Perfects in {next_aspect.get('timeToExactText') or format_duration(float(_aspect_days(next_aspect) or 0))}; method {next_aspect.get('timingMethod', 'timing estimate')}.",
                score,
                "support" if score > 0 else "caution" if score < 0 else "info",
            )
        )
    if final_aspect and final_aspect is not next_aspect:
        factors.append(
            _factor(
                "moon-final-before-exit",
                f"Final Moon aspect before sign exit: {final_aspect.get('label', 'Moon aspect')}",
                f"Final selected lunar contact before exit perfects in {final_aspect.get('timeToExactText') or 'the sign-exit window'}.",
                0.5 if final_aspect.get("tone") == "support" else -0.5 if final_aspect.get("tone") == "stress" else 0.0,
                "support" if final_aspect.get("tone") == "support" else "caution" if final_aspect.get("tone") == "stress" else "info",
            )
        )
    if speed == "fast":
        factors.append(_factor("moon-fast", "Moon fast", f"Moon speed is {daily_speed:+.2f} deg/day.", 0.5, "support"))
    elif speed == "slow":
        factors.append(_factor("moon-slow", "Moon slow", f"Moon speed is {daily_speed:+.2f} deg/day.", -0.5, "caution"))
    if cadency == "angular":
        factors.append(_factor("moon-angular", "Moon angular", f"Moon is in House {house}, an angular house.", 1.0, "support"))
    elif cadency == "cadent":
        factors.append(_factor("moon-cadent", "Moon cadent", f"Moon is in House {house}, a cadent house.", -1.0, "caution"))
    if solar.get("phase") in {"combust", "under beams"}:
        factors.append(
            _factor(
                f"moon-{str(solar.get('phase')).replace(' ', '-')}",
                f"Moon {solar.get('phase')}",
                str(solar.get("detail")),
                float(solar.get("scoreImpact", 0) or 0),
                "warning" if solar.get("phase") == "combust" else "caution",
            )
        )

    score_impact = sum(float(factor.get("scoreImpact", 0) or 0) for factor in factors)
    zodiac = moon.get("zodiac") if isinstance(moon.get("zodiac"), Mapping) else {}
    confidence = "high" if aspects and abs(daily_speed) > 0 else "medium" if abs(daily_speed) > 0 else "low"
    status = "Void" if is_void else "Not void"
    next_label = next_aspect.get("label") if isinstance(next_aspect, Mapping) else "none before sign exit"
    summary = (
        f"{status}; next aspect: {next_label}; speed {speed}; "
        f"House {house or 'n/a'} ({cadency}); {lunar_phase.get('name', 'phase unknown')}."
    )
    return {
        "summary": summary,
        "factors": factors,
        "scoreImpact": score_impact,
        "confidence": confidence,
        "moon": {
            "sign": zodiac.get("sign"),
            "degree": zodiac.get("degree"),
            "minute": zodiac.get("minute"),
            "house": house,
            "cadency": cadency,
            "dignity": moon.get("dignity"),
            "motion": motion,
            "speedClass": speed,
            "dailySpeed": daily_speed,
            "latitude": moon.get("latitude"),
            "declination": moon.get("declination"),
            "isAngular": moon.get("isAngular", False),
            "closestAngle": moon.get("closestAngle"),
            "solarCondition": solar,
        },
        "lastAspect": _aspect_snapshot(recent_separating),
        "nextAspect": _aspect_snapshot(next_aspect),
        "finalAspectBeforeSignExit": _aspect_snapshot(final_aspect),
        "voidOfCourse": {
            "isVoid": is_void,
            "confidence": confidence,
            "method": "applying aspects before sign exit",
            "daysToSignExit": days_to_exit,
            "degreesToSignExit": distance_to_exit,
            "timeToSignExitText": format_duration(days_to_exit),
        },
        "applyingCount": len(applying),
        "applyingBeforeSignExitCount": len(applying_before_exit),
        "separatingCount": len(separating),
    }
