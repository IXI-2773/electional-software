"""Layered electional judgment contexts for chart snapshots."""

from __future__ import annotations

from typing import Mapping, Sequence

from .aspects import angular_distance, format_duration
from .presets import DETRIMENTS, EXALTATIONS, FALLS, RULERS, get_bound_lord

BENEFICS = {"Venus", "Jupiter"}
MALEFICS = {"Mars", "Saturn"}
FAST_TRANSLATORS = {"Moon", "Mercury", "Venus"}
OUT_OF_BOUNDS_DECLINATION = 23.4367
DECLINATION_ORB = 1.0
PLANET_SPEED_BANDS = {
    "Mercury": {"slow": 0.25, "fast": 1.8},
    "Venus": {"slow": 0.10, "fast": 1.25},
    "Mars": {"slow": 0.15, "fast": 0.75},
    "Jupiter": {"slow": 0.02, "fast": 0.25},
    "Saturn": {"slow": 0.01, "fast": 0.13},
    "Uranus": {"slow": 0.005, "fast": 0.06},
    "Neptune": {"slow": 0.003, "fast": 0.04},
    "Pluto": {"slow": 0.002, "fast": 0.04},
}

OBJECTIVE_TOPICS: dict[str, dict[str, object]] = {
    "Launch or publish": {"houses": (10,), "planets": ("Sun", "Mercury"), "label": "public launch"},
    "Meeting or negotiation": {"houses": (3, 7), "planets": ("Mercury", "Venus"), "label": "meeting"},
    "Creative work": {"houses": (5,), "planets": ("Venus", "Sun"), "label": "creative work"},
    "Relationship timing": {"houses": (7,), "planets": ("Venus", "Moon"), "label": "relationship"},
    "Travel departure": {"houses": (9,), "planets": ("Mercury", "Jupiter"), "label": "travel"},
    "Money or business": {"houses": (2, 11), "planets": ("Jupiter", "Venus"), "label": "money or business"},
    "Exam / certification": {"houses": (9,), "planets": ("Mercury", "Jupiter"), "label": "exam"},
    "Legal / dispute": {"houses": (7, 9, 10), "planets": ("Jupiter", "Mars", "Saturn"), "label": "legal dispute"},
    "Message / contact": {"houses": (3,), "planets": ("Mercury", "Moon"), "label": "message / contact"},
    "Health or surgery caution": {"houses": (1, 6, 8), "planets": ("Mars", "Saturn"), "label": "health caution"},
}
OBJECTIVE_MATTER_TOPICS: dict[str, dict[str, object]] = {
    "Launch or publish": {
        "houses": (10,),
        "natural": ("Sun", "Mercury"),
        "label": "public launch / visibility",
    },
    "Meeting or negotiation": {
        "houses": (7,),
        "natural": ("Mercury", "Venus"),
        "label": "agreement / counterpart",
    },
    "Creative work": {
        "houses": (5,),
        "natural": ("Venus", "Sun"),
        "label": "creative production",
    },
    "Relationship timing": {
        "houses": (7,),
        "natural": ("Venus", "Moon"),
        "label": "relationship matter",
    },
    "Travel departure": {
        "houses": (9,),
        "natural": ("Mercury", "Jupiter"),
        "label": "long-distance travel",
    },
    "Money or business": {
        "houses": (2, 11),
        "natural": ("Venus", "Jupiter", "Mercury"),
        "label": "money, profit, and gains",
    },
    "Health or surgery caution": {
        "houses": (1, 6, 8),
        "natural": ("Mars", "Saturn"),
        "label": "health/surgery caution",
    },
    "Exam / certification": {
        "houses": (9,),
        "natural": ("Mercury", "Jupiter"),
        "label": "exam or certification",
    },
    "Legal / dispute": {
        "houses": (7, 9, 10),
        "natural": ("Jupiter", "Mars", "Saturn"),
        "label": "legal dispute / judgment",
    },
    "Message / contact": {
        "houses": (3,),
        "natural": ("Mercury", "Moon"),
        "label": "message, contact, and exchange",
    },
}

DEFAULT_OBJECTIVE = "Launch or publish"
OBJECTIVE_ASPECT_PRIORITIES: dict[str, dict[str, object]] = {
    "Launch or publish": {
        "supportBodies": {"Sun", "Mercury", "Jupiter", "Venus"},
        "cautionBodies": {"Mars", "Saturn"},
        "supportSummary": "public launch visibility",
        "cautionSummary": "public launch drag or conflict",
    },
    "Meeting or negotiation": {
        "supportBodies": {"Mercury", "Venus", "Jupiter", "Moon"},
        "cautionBodies": {"Mars", "Saturn"},
        "supportSummary": "agreement, clarity, and cooperation",
        "cautionSummary": "argument, delay, or hardened positions",
    },
    "Creative work": {
        "supportBodies": {"Venus", "Sun", "Moon", "Mercury"},
        "cautionBodies": {"Mars", "Saturn"},
        "supportSummary": "creative flow and visible expression",
        "cautionSummary": "blockage, friction, or overwork",
    },
    "Relationship timing": {
        "supportBodies": {"Venus", "Moon", "Jupiter"},
        "cautionBodies": {"Mars", "Saturn"},
        "supportSummary": "connection, warmth, and receptivity",
        "cautionSummary": "separation, conflict, or coldness",
    },
    "Travel departure": {
        "supportBodies": {"Mercury", "Jupiter", "Moon"},
        "cautionBodies": {"Mars", "Saturn"},
        "supportSummary": "movement, guidance, and safe passage",
        "cautionSummary": "delay, accident pressure, or travel friction",
    },
    "Money or business": {
        "supportBodies": {"Venus", "Jupiter", "Mercury"},
        "cautionBodies": {"Mars", "Saturn"},
        "supportSummary": "profit, agreement, and growth",
        "cautionSummary": "loss pressure, scarcity, or conflict",
    },
    "Exam / certification": {
        "supportBodies": {"Mercury", "Jupiter", "Moon"},
        "cautionBodies": {"Saturn", "Mars", "Sun"},
        "supportSummary": "clarity, judgment, and successful review",
        "cautionSummary": "delay, pressure, or mental blockage",
    },
    "Legal / dispute": {
        "supportBodies": {"Jupiter", "Mercury", "Moon"},
        "cautionBodies": {"Mars", "Saturn"},
        "supportSummary": "authority, fairness, and strategic advantage",
        "cautionSummary": "conflict, obstruction, or punitive pressure",
    },
    "Message / contact": {
        "supportBodies": {"Mercury", "Moon", "Venus"},
        "cautionBodies": {"Saturn", "Mars"},
        "supportSummary": "clear exchange and responsiveness",
        "cautionSummary": "delay, argument, or blocked communication",
    },
    "Health or surgery caution": {
        "supportBodies": {"Jupiter", "Venus", "Moon"},
        "cautionBodies": {"Mars", "Saturn", "Sun"},
        "supportSummary": "recovery support and steadiness",
        "cautionSummary": "inflammation, cutting pressure, or depletion",
    },
}


def _position_by_name(positions: Sequence[Mapping[str, object]]) -> dict[str, Mapping[str, object]]:
    return {str(position.get("name")): position for position in positions}


def _factor(
    factor_id: str,
    category: str,
    title: str,
    detail: str,
    score: float = 0.0,
    severity: str = "info",
    body: str = "",
) -> dict[str, object]:
    return {
        "id": factor_id,
        "category": category,
        "severity": severity,
        "title": title,
        "detail": detail,
        "body": body,
        "scoreImpact": score,
    }


def _context(summary: str, factors: list[dict[str, object]], confidence: str = "solid") -> dict[str, object]:
    return {
        "summary": summary,
        "factors": factors,
        "scoreImpact": sum(float(factor.get("scoreImpact", 0)) for factor in factors),
        "confidence": confidence,
    }


def _cusp_sign(house_cusps: Sequence[Mapping[str, object]], house_number: int) -> str | None:
    cusp = next((item for item in house_cusps if int(item.get("house", 0)) == house_number), None)
    zodiac = cusp.get("zodiac") if isinstance(cusp, Mapping) else None
    if isinstance(zodiac, Mapping):
        return str(zodiac.get("sign") or "")
    return None


def _house_ruler(house_cusps: Sequence[Mapping[str, object]], house_number: int) -> str | None:
    sign = _cusp_sign(house_cusps, house_number)
    return RULERS.get(sign or "")


def _dignity_score(planet: Mapping[str, object] | None) -> float:
    dignity = planet.get("dignity") if isinstance(planet, Mapping) else None
    if isinstance(dignity, Mapping):
        return float(dignity.get("score", 0))
    return 0.0


def _dignity_label(planet: Mapping[str, object] | None) -> str:
    dignity = planet.get("dignity") if isinstance(planet, Mapping) else None
    return str(dignity.get("label", "Unknown")) if isinstance(dignity, Mapping) else "Unknown"


def _severity_for_score(score: float) -> str:
    if score > 0:
        return "support"
    if score < 0:
        return "caution"
    return "info"


def _slug(text: object) -> str:
    return str(text).replace(" ", "-").replace("/", "-").lower()


def _timing_multiplier(aspect: Mapping[str, object]) -> float:
    timing_quality = str(aspect.get("timingQuality", ""))
    if aspect.get("isApplying"):
        if timing_quality == "soon":
            return 1.2
        if timing_quality == "near-term":
            return 1.0
        if timing_quality == "later":
            return 0.7
        return 0.8
    return 0.4


def _signed_longitude_delta(start_longitude: float, end_longitude: float) -> float:
    return ((end_longitude - start_longitude + 180) % 360) - 180


def solar_visibility_diagnostic(name: str, separation: float, signed_from_sun: float) -> dict[str, object]:
    side = "evening" if signed_from_sun > 0 else "morning" if signed_from_sun < 0 else "solar conjunction"
    if separation <= 0.283333:
        phase = "cazimi"
        label = "Cazimi"
        note = "in the heart of the Sun"
    elif separation <= 8.5:
        phase = "combust"
        label = "Combust"
        note = "hidden by solar glare"
    elif separation <= 15:
        phase = "under beams"
        label = "Under beams"
        note = "weakened by solar glare"
    elif name in {"Mercury", "Venus"} and separation <= 20:
        phase = "emerging"
        label = "Emerging from beams"
        note = "near an approximate heliacal threshold"
    else:
        phase = "clear"
        label = "Clear of beams"
        note = "clear angular separation from the Sun"
    return {
        "body": name,
        "phase": phase,
        "label": label,
        "side": side,
        "solarSeparation": separation,
        "signedSolarDistance": signed_from_sun,
        "confidence": "diagnostic",
        "note": note,
    }


def _visibility_factor_score(phase: object, multiplier: float) -> float:
    match str(phase):
        case "cazimi":
            return round(0.5 * multiplier, 2)
        case "combust":
            return round(-0.5 * multiplier, 2)
        case "under beams":
            return round(-0.3 * multiplier, 2)
        case "emerging":
            return round(0.25 * multiplier, 2)
        case _:
            return 0.0


def _planet_factor_score(planet: Mapping[str, object]) -> float:
    score = 0.0
    dignity = _dignity_score(planet)
    if dignity >= 4:
        score += 1.5
    elif dignity <= -4:
        score -= 1.5
    if planet.get("isAngular"):
        score += 1.0
    if planet.get("isRetrograde"):
        score -= 1.0
    return score


def significator_context(
    positions: Sequence[Mapping[str, object]],
    angles: Sequence[Mapping[str, object]],
    house_cusps: Sequence[Mapping[str, object]],
    objective: str = DEFAULT_OBJECTIVE,
) -> dict[str, object]:
    by_name = _position_by_name(positions)
    topic = OBJECTIVE_TOPICS.get(objective, OBJECTIVE_TOPICS[DEFAULT_OBJECTIVE])
    ascendant = next((angle for angle in angles if angle.get("id") == "asc"), None)
    asc_sign = str((ascendant or {}).get("zodiac", {}).get("sign", ""))
    selected: dict[str, dict[str, object]] = {}

    def add(name: str | None, role: str, house: int | None = None) -> None:
        if not name or name not in by_name:
            return
        existing = selected.setdefault(name, {"name": name, "roles": [], "houseTopics": []})
        existing["roles"].append(role)
        if house is not None:
            existing["houseTopics"].append(house)

    add(RULERS.get(asc_sign), "ASC ruler", 1)
    add("Moon", "Moon")
    for planet_name in topic.get("planets", ()):
        add(str(planet_name), f"{topic['label']} natural significator")
    for house in topic.get("houses", ()):
        add(_house_ruler(house_cusps, int(house)), f"House {house} ruler", int(house))

    factors = []
    selected_points = []
    for name, item in selected.items():
        planet = by_name[name]
        score = _planet_factor_score(planet)
        roles = ", ".join(dict.fromkeys(str(role) for role in item["roles"]))
        selected_points.append(
            {
                "name": name,
                "roles": list(dict.fromkeys(item["roles"])),
                "houseTopics": list(dict.fromkeys(item["houseTopics"])),
                "house": planet.get("house"),
                "dignity": planet.get("dignity"),
                "isAngular": planet.get("isAngular", False),
                "isRetrograde": planet.get("isRetrograde", False),
                "scoreImpact": score,
            }
        )
        details = [
            f"{name} serves as {roles}",
            f"dignity {_dignity_label(planet)}",
            f"house {planet.get('house', 'n/a')}",
        ]
        if planet.get("isAngular"):
            details.append("angular")
        if planet.get("isRetrograde"):
            details.append("retrograde")
        factors.append(
            _factor(
                f"significator-{name.lower()}",
                "significators",
                f"{name} significator condition",
                "; ".join(details) + ".",
                score,
                _severity_for_score(score),
                name,
            )
        )

    return {
        **_context(f"{objective}: {len(selected_points)} primary significator(s) selected.", factors),
        "objective": objective,
        "points": selected_points,
    }


def moon_condition_context(
    positions: Sequence[Mapping[str, object]],
    detected_aspects: Sequence[Mapping[str, object]],
    lunar_phase: Mapping[str, object],
) -> dict[str, object]:
    by_name = _position_by_name(positions)
    moon = by_name.get("Moon")
    if not moon:
        return _context("Moon condition unavailable.", [], "approximate")

    motion = moon.get("motion") if isinstance(moon.get("motion"), Mapping) else {}
    daily_speed = float(motion.get("dailyLongitudeChange", 0)) if isinstance(motion, Mapping) else 0.0
    zodiac = moon.get("zodiac") if isinstance(moon.get("zodiac"), Mapping) else {}
    degree = float(zodiac.get("degree", 0)) + float(zodiac.get("minute", 0)) / 60 if isinstance(zodiac, Mapping) else 0.0
    degrees_to_sign_exit = max(0.0, 30 - degree)
    days_to_sign_exit = degrees_to_sign_exit / max(abs(daily_speed), 0.01)
    moon_aspects = [
        aspect
        for aspect in detected_aspects
        if isinstance(aspect, Mapping) and "Moon" in aspect.get("bodies", [])
    ]
    applying = [aspect for aspect in moon_aspects if aspect.get("isApplying")]
    separating = [aspect for aspect in moon_aspects if aspect.get("isApplying") is False]
    next_aspect = min(applying, key=lambda aspect: float(aspect.get("daysToExact") or 99), default=None)
    last_aspect = min(separating, key=lambda aspect: float(aspect.get("orb", 99)), default=None)
    is_void = not any(float(aspect.get("daysToExact") or 99) <= days_to_sign_exit for aspect in applying)

    factors = []
    if moon.get("isAngular"):
        factors.append(_factor("moon-angular", "moon", "Moon angular", "Moon is close to an angle and more active.", 1.0, "support", "Moon"))
    if is_void:
        factors.append(
            _factor(
                "moon-void-estimate",
                "moon",
                "Moon void estimate",
                "No selected applying Moon contact perfects before the Moon leaves its current sign.",
                -2.0,
                "caution",
                "Moon",
            )
        )
    elif next_aspect:
        bodies = [str(body) for body in next_aspect.get("bodies", [])]
        other = next((body for body in bodies if body != "Moon"), "")
        if other in BENEFICS:
            score = 1.5
        elif other in MALEFICS:
            score = -1.5
        else:
            score = 0.5 if next_aspect.get("tone") == "support" else -0.5 if next_aspect.get("tone") == "stress" else 0.0
        factors.append(
            _factor(
                f"moon-next-{other.lower()}",
                "moon",
                f"Moon next applies to {other}",
                f"Next selected Moon contact is {next_aspect.get('label')} in {next_aspect.get('timeToExactText') or 'the scan estimate'}.",
                score,
                _severity_for_score(score),
                "Moon",
            )
        )

    if daily_speed >= 14:
        factors.append(_factor("moon-fast", "moon", "Moon fast", f"Moon speed is {daily_speed:+.2f} deg/day.", 0.5, "support", "Moon"))
    elif 0 < daily_speed <= 11:
        factors.append(_factor("moon-slow", "moon", "Moon slow", f"Moon speed is {daily_speed:+.2f} deg/day.", -0.5, "caution", "Moon"))

    return {
        **_context(f"Moon in {zodiac.get('sign', 'n/a')} House {moon.get('house', 'n/a')}; {lunar_phase.get('name', 'phase unknown')}.", factors, "approximate"),
        "moon": {
            "sign": zodiac.get("sign"),
            "house": moon.get("house"),
            "dignity": moon.get("dignity"),
            "motion": motion,
            "isAngular": moon.get("isAngular", False),
            "closestAngle": moon.get("closestAngle"),
        },
        "lastAspect": dict(last_aspect) if isinstance(last_aspect, Mapping) else None,
        "nextAspect": dict(next_aspect) if isinstance(next_aspect, Mapping) else None,
        "voidOfCourse": {
            "isVoid": is_void,
            "confidence": "approximate",
            "daysToSignExit": days_to_sign_exit,
            "timeToSignExitText": format_duration(days_to_sign_exit),
        },
    }


def house_ruler_context(
    positions: Sequence[Mapping[str, object]],
    house_cusps: Sequence[Mapping[str, object]],
    objective: str = DEFAULT_OBJECTIVE,
) -> dict[str, object]:
    by_name = _position_by_name(positions)
    topic = OBJECTIVE_TOPICS.get(objective, OBJECTIVE_TOPICS[DEFAULT_OBJECTIVE])
    houses = [int(house) for house in topic.get("houses", ())]
    factors = []
    rulers = []
    for house in houses:
        sign = _cusp_sign(house_cusps, house) or ""
        ruler_name = RULERS.get(sign)
        planet = by_name.get(ruler_name or "")
        if not ruler_name or not planet:
            continue
        score = _planet_factor_score(planet)
        rulers.append(
            {
                "house": house,
                "sign": sign,
                "ruler": ruler_name,
                "rulerHouse": planet.get("house"),
                "dignity": planet.get("dignity"),
                "scoreImpact": score,
            }
        )
        factors.append(
            _factor(
                f"house-{house}-ruler-{ruler_name.lower()}",
                "house-rulers",
                f"House {house} ruler {ruler_name}",
                f"House {house} begins in {sign}; {ruler_name} is in House {planet.get('house', 'n/a')} with {_dignity_label(planet)} dignity.",
                score,
                _severity_for_score(score),
                ruler_name,
            )
        )
    return {
        **_context(f"{objective}: evaluated {len(rulers)} topic house ruler(s).", factors),
        "objective": objective,
        "rulers": rulers,
    }


def matter_lord_context(
    positions: Sequence[Mapping[str, object]],
    angles: Sequence[Mapping[str, object]],
    house_cusps: Sequence[Mapping[str, object]],
    detected_aspects: Sequence[Mapping[str, object]],
    objective: str = DEFAULT_OBJECTIVE,
    planetary_hour: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Evaluate Lord of ASC, Moon, Lord(s) of Matter, natural significators, and hour/year lords."""

    by_name = _position_by_name(positions)
    topic = OBJECTIVE_MATTER_TOPICS.get(objective, OBJECTIVE_MATTER_TOPICS.get(DEFAULT_OBJECTIVE, {}))
    ascendant = next((angle for angle in angles if angle.get("id") == "asc"), None)
    asc_sign = str((ascendant or {}).get("zodiac", {}).get("sign", ""))
    asc_lord = RULERS.get(asc_sign)
    matter_houses = tuple(int(house) for house in topic.get("houses", ()))
    natural = tuple(str(name) for name in topic.get("natural", ()))
    hour_lord = str((planetary_hour or {}).get("hourRuler") or "")
    year_lord = "Sun"

    matter_lords = []
    factors: list[dict[str, object]] = []

    def score_body(name: str, role: str, weight: float = 1.0, house: int | None = None) -> dict[str, object] | None:
        planet = by_name.get(name)
        if not planet:
            return None
        score = _planet_factor_score(planet) * weight
        aspect_support = 0
        aspect_stress = 0
        for aspect in detected_aspects:
            bodies = aspect.get("bodies", [])
            if not isinstance(bodies, list) or name not in [str(body) for body in bodies]:
                continue
            if aspect.get("tone") == "support":
                aspect_support += 1
                if aspect.get("isApplying"):
                    score += 0.35 * weight
            elif aspect.get("tone") == "stress":
                aspect_stress += 1
                if aspect.get("isApplying"):
                    score -= 0.45 * weight
        detail = (
            f"{role}: {name} in H{planet.get('house', 'n/a')}; {_dignity_label(planet)}"
            + ("; angular" if planet.get("isAngular") else "")
            + ("; retrograde" if planet.get("isRetrograde") else "")
            + f"; aspects +{aspect_support}/!{aspect_stress}."
        )
        factors.append(
            _factor(
                f"matter-{_slug(role)}-{_slug(name)}",
                "lord-of-matter",
                f"{role}: {name}",
                detail,
                score,
                _severity_for_score(score),
                name,
            )
        )
        return {
            "role": role,
            "house": house,
            "name": name,
            "sign": planet.get("zodiac", {}).get("sign") if isinstance(planet.get("zodiac"), Mapping) else "",
            "planetHouse": planet.get("house"),
            "dignity": planet.get("dignity"),
            "isAngular": bool(planet.get("isAngular")),
            "isRetrograde": bool(planet.get("isRetrograde")),
            "supportAspects": aspect_support,
            "stressAspects": aspect_stress,
            "scoreImpact": round(score, 2),
        }

    if asc_lord:
        item = score_body(asc_lord, "Lord of ASC", 1.0, 1)
        if item:
            matter_lords.append(item)
    moon_item = score_body("Moon", "Moon", 1.0)
    if moon_item:
        matter_lords.append(moon_item)
    for house in matter_houses:
        sign = _cusp_sign(house_cusps, house) or ""
        ruler = RULERS.get(sign)
        if not ruler:
            continue
        item = score_body(ruler, f"Lord of Matter H{house}", 1.25, house)
        if item:
            item["matterSign"] = sign
            matter_lords.append(item)
    for name in natural:
        item = score_body(name, "Natural significator", 0.9)
        if item:
            matter_lords.append(item)
    if hour_lord:
        hour_item = score_body(hour_lord, "Lord of Hour", 0.55)
        if hour_item:
            matter_lords.append(hour_item)
    year_item = score_body(str(year_lord), "Lord of Year", 0.35)
    if year_item:
        matter_lords.append(year_item)

    # De-duplicate repeated roles for the same body while preserving role detail in factors.
    unique_lords: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for item in matter_lords:
        key = (str(item.get("role")), str(item.get("name")))
        if key in seen:
            continue
        seen.add(key)
        unique_lords.append(item)

    return {
        **_context(
            f"{objective}: Lord of Matter uses house(s) {', '.join(str(h) for h in matter_houses) or 'n/a'} "
            f"for {topic.get('label', 'the matter')}.",
            factors,
        ),
        "objective": objective,
        "matterHouses": list(matter_houses),
        "naturalSignificators": list(natural),
        "hourLord": hour_lord,
        "yearLord": year_lord,
        "lords": unique_lords,
    }


def _planetary_affliction_notes(planet: Mapping[str, object] | None) -> list[str]:
    if not isinstance(planet, Mapping):
        return []
    notes: list[str] = []
    if planet.get("isRetrograde"):
        notes.append("retrograde")
    solar = planet.get("solarCondition")
    if isinstance(solar, Mapping):
        phase = str(solar.get("phase") or "")
        if phase in {"combust", "under beams"}:
            notes.append(phase)
    if _dignity_score(planet) <= -4:
        notes.append("debilitated dignity")
    return notes


def _body_aspect_counts(
    detected_aspects: Sequence[Mapping[str, object]],
    name: str,
    *,
    target_bodies: Sequence[str] = (),
) -> tuple[int, int, int]:
    support = 0
    stress = 0
    applying_support = 0
    targets = {str(body) for body in target_bodies if body}
    for aspect in detected_aspects:
        bodies = aspect.get("bodies", [])
        if not isinstance(bodies, list):
            continue
        body_names = {str(body) for body in bodies}
        if name not in body_names:
            continue
        if targets and not body_names.intersection(targets):
            continue
        if aspect.get("tone") == "support":
            support += 1
            if aspect.get("isApplying"):
                applying_support += 1
        elif aspect.get("tone") == "stress":
            stress += 1
    return support, stress, applying_support


def _objective_planet_factor(
    factors: list[dict[str, object]],
    by_name: Mapping[str, Mapping[str, object]],
    detected_aspects: Sequence[Mapping[str, object]],
    name: str,
    title: str,
    *,
    weight: float = 1.0,
    target_bodies: Sequence[str] = (),
) -> float:
    planet = by_name.get(name)
    if not planet:
        return 0.0
    support, stress, applying_support = _body_aspect_counts(detected_aspects, name, target_bodies=target_bodies)
    score = _planet_factor_score(planet) * weight + applying_support * 0.35 * weight - stress * 0.25 * weight
    details = [f"{name} in H{planet.get('house', 'n/a')}", _dignity_label(planet)]
    if planet.get("isAngular"):
        details.append("angular")
    afflictions = _planetary_affliction_notes(planet)
    if afflictions:
        details.append(", ".join(afflictions))
    details.append(f"aspects +{support}/!{stress}")
    factors.append(
        _factor(
            f"objective-{_slug(title)}-{_slug(name)}",
            "objective-analyzer",
            title,
            "; ".join(details) + ".",
            score,
            _severity_for_score(score),
            name,
        )
    )
    return score


def objective_analyzer_context(
    positions: Sequence[Mapping[str, object]],
    house_cusps: Sequence[Mapping[str, object]],
    detected_aspects: Sequence[Mapping[str, object]],
    objective: str = DEFAULT_OBJECTIVE,
    reception: Mapping[str, object] | None = None,
) -> dict[str, object]:
    by_name = _position_by_name(positions)
    factors: list[dict[str, object]] = []
    notes: list[str] = []
    objective_key = str(objective).lower()
    analyzer_name = "Objective Analyzer"

    if "exam" in objective_key or "cert" in objective_key:
        analyzer_name = "Exam Analyzer"
        _objective_planet_factor(factors, by_name, detected_aspects, "Mercury", "Mercury strength", weight=1.35, target_bodies=("Moon", "Jupiter", "Saturn"))
        ninth_ruler = _house_ruler(house_cusps, 9)
        if ninth_ruler:
            _objective_planet_factor(factors, by_name, detected_aspects, ninth_ruler, "9th-house ruler", weight=1.15, target_bodies=("Moon", "Jupiter", "Saturn"))
        _objective_planet_factor(factors, by_name, detected_aspects, "Jupiter", "Jupiter judgment support", weight=0.95, target_bodies=("Moon", "Mercury"))
        moon_support, moon_stress, moon_apply = _body_aspect_counts(detected_aspects, "Moon", target_bodies=("Mercury", "Jupiter"))
        moon_score = moon_apply * 0.7 - moon_stress * 0.4
        factors.append(_factor("objective-exam-moon", "objective-analyzer", "Moon to Mercury/Jupiter", f"Moon contacts to Mercury/Jupiter: +{moon_support}/!{moon_stress}; applying support {moon_apply}.", moon_score, _severity_for_score(moon_score), "Moon"))
        mercury = by_name.get("Mercury")
        if isinstance(mercury, Mapping):
            afflictions = _planetary_affliction_notes(mercury)
            if afflictions:
                notes.append(f"Mercury caution: {', '.join(afflictions)}.")
        notes.append("Natal/profection support is not fully modeled yet; treat that part as unavailable.")
    elif "legal" in objective_key or "dispute" in objective_key:
        analyzer_name = "Legal / Dispute Analyzer"
        seventh_ruler = _house_ruler(house_cusps, 7)
        ninth_ruler = _house_ruler(house_cusps, 9)
        tenth_ruler = _house_ruler(house_cusps, 10)
        scores: dict[int, float] = {}
        for house, ruler, label in ((7, seventh_ruler, "7th-house ruler"), (9, ninth_ruler, "9th-house ruler"), (10, tenth_ruler, "10th-house ruler")):
            if ruler:
                scores[house] = _objective_planet_factor(factors, by_name, detected_aspects, ruler, label, weight=1.15 if house == 10 else 1.0, target_bodies=("Moon", "Jupiter", "Mars", "Saturn"))
        _objective_planet_factor(factors, by_name, detected_aspects, "Jupiter", "Authority / judge significator", weight=1.05, target_bodies=("Moon",))
        if any(name in by_name and by_name[name].get("isAngular") for name in ("Mars", "Saturn")):
            factors.append(_factor("objective-legal-malefic", "objective-analyzer", "Mars/Saturn angular damage", "Mars or Saturn is angular, which can harden conflict or punitive outcomes.", -1.9, "caution", "Mars"))
        if 7 in scores and 10 in scores and scores[7] > scores[10] + 0.75:
            factors.append(_factor("objective-legal-opponent", "objective-analyzer", "Opponent strength", "The 7th-house side currently looks stronger than the 10th-house authority side.", -1.1, "caution"))
    elif "money" in objective_key or "business" in objective_key:
        analyzer_name = "Money Analyzer"
        second_ruler = _house_ruler(house_cusps, 2)
        eleventh_ruler = _house_ruler(house_cusps, 11)
        if second_ruler:
            _objective_planet_factor(factors, by_name, detected_aspects, second_ruler, "2nd-house ruler", weight=1.2, target_bodies=("Moon", "Venus", "Jupiter"))
        if eleventh_ruler:
            _objective_planet_factor(factors, by_name, detected_aspects, eleventh_ruler, "11th-house ruler", weight=1.1, target_bodies=("Moon", "Venus", "Jupiter"))
        _objective_planet_factor(factors, by_name, detected_aspects, "Venus", "Venus value signal", weight=1.0, target_bodies=("Moon", "Jupiter"))
        _objective_planet_factor(factors, by_name, detected_aspects, "Jupiter", "Jupiter gain signal", weight=1.0, target_bodies=("Moon", "Venus"))
        moon_support, moon_stress, moon_apply = _body_aspect_counts(detected_aspects, "Moon", target_bodies=("Venus", "Jupiter"))
        score = moon_apply * 0.75 - moon_stress * 0.4
        factors.append(_factor("objective-money-moon", "objective-analyzer", "Moon applying to benefic", f"Moon contacts to Venus/Jupiter: +{moon_support}/!{moon_stress}; applying support {moon_apply}.", score, _severity_for_score(score), "Moon"))
        for name in (second_ruler, eleventh_ruler, "Venus", "Jupiter"):
            planet = by_name.get(name or "")
            if isinstance(planet, Mapping) and int(planet.get("house", 0) or 0) == 8:
                factors.append(_factor(f"objective-money-8th-{_slug(name)}", "objective-analyzer", "8th-house trap", f"{name} is in the 8th house, which can redirect value into obligation, debt, or loss pressure.", -1.35, "caution", str(name)))
    elif "message" in objective_key or "contact" in objective_key:
        analyzer_name = "Message / Contact Analyzer"
        third_ruler = _house_ruler(house_cusps, 3)
        if third_ruler:
            _objective_planet_factor(factors, by_name, detected_aspects, third_ruler, "3rd-house ruler", weight=1.2, target_bodies=("Moon", "Mercury", "Saturn"))
        _objective_planet_factor(factors, by_name, detected_aspects, "Mercury", "Mercury clarity", weight=1.35, target_bodies=("Moon", "Venus", "Saturn", "Mars"))
        moon_support, moon_stress, moon_apply = _body_aspect_counts(detected_aspects, "Moon", target_bodies=("Mercury",))
        moon_score = moon_apply * 0.7 - moon_stress * 0.4
        factors.append(_factor("objective-message-moon", "objective-analyzer", "Moon applying support", f"Moon-to-Mercury contacts: +{moon_support}/!{moon_stress}; applying support {moon_apply}.", moon_score, _severity_for_score(moon_score), "Moon"))
        if isinstance(reception, Mapping):
            reception_score = float(reception.get("scoreImpact", 0) or 0)
            factors.append(_factor("objective-message-reception", "objective-analyzer", "Reception", f"Reception context score impact {reception_score:+.1f}.", reception_score * 0.55, _severity_for_score(reception_score), "Mercury"))
        mercury = by_name.get("Mercury")
        afflictions = _planetary_affliction_notes(mercury)
        if afflictions:
            factors.append(_factor("objective-message-affliction", "objective-analyzer", "Mercury affliction", f"Mercury shows {', '.join(afflictions)}.", -1.15, "caution", "Mercury"))
    else:
        topic = OBJECTIVE_TOPICS.get(objective, OBJECTIVE_TOPICS[DEFAULT_OBJECTIVE])
        for planet_name in topic.get("planets", ()):
            _objective_planet_factor(factors, by_name, detected_aspects, str(planet_name), f"{topic.get('label', 'objective').title()} significator", weight=1.0)
        notes.append("Use the specialized analyzers for exam, legal, money, or message objectives when those are the real matter.")

    return {
        **_context(f"{analyzer_name}: {len(factors)} focused factor(s) reviewed for {objective}.", factors, "focused"),
        "objective": objective,
        "analyzer": analyzer_name,
        "sourceNote": " ".join(notes).strip(),
    }


def _receives(receiver_name: str, planet: Mapping[str, object]) -> tuple[bool, str]:
    zodiac = planet.get("zodiac") if isinstance(planet.get("zodiac"), Mapping) else {}
    sign = str(zodiac.get("sign") or "") if isinstance(zodiac, Mapping) else ""
    bound_lord = get_bound_lord(planet)
    if RULERS.get(sign) == receiver_name:
        return True, "domicile"
    if EXALTATIONS.get(sign) == receiver_name:
        return True, "exaltation"
    if bound_lord == receiver_name:
        return True, "bound"
    return False, ""


def reception_context(
    positions: Sequence[Mapping[str, object]],
    detected_aspects: Sequence[Mapping[str, object]],
    significator_ctx: Mapping[str, object],
) -> dict[str, object]:
    by_name = _position_by_name(positions)
    significator_names = [str(point.get("name")) for point in significator_ctx.get("points", []) if isinstance(point, Mapping)]
    factors = []
    receptions = []

    for index, first_name in enumerate(significator_names):
        first = by_name.get(first_name)
        if not first:
            continue
        for second_name in significator_names[index + 1 :]:
            second = by_name.get(second_name)
            if not second:
                continue
            first_receives, first_mode = _receives(first_name, second)
            second_receives, second_mode = _receives(second_name, first)
            if first_receives and second_receives:
                receptions.append({"type": "mutual", "bodies": [first_name, second_name], "modes": [first_mode, second_mode]})
                factors.append(
                    _factor(
                        f"mutual-reception-{first_name.lower()}-{second_name.lower()}",
                        "reception",
                        f"{first_name}-{second_name} mutual reception",
                        f"{first_name} and {second_name} receive one another by {first_mode}/{second_mode}.",
                        2.0,
                        "support",
                        first_name,
                    )
                )

    for aspect in detected_aspects:
        if not aspect.get("isApplying"):
            continue
        bodies = [str(body) for body in aspect.get("bodies", [])]
        if len(bodies) != 2 or not any(body in significator_names for body in bodies):
            continue
        first, second = by_name.get(bodies[0]), by_name.get(bodies[1])
        if not first or not second:
            continue
        second_receives_first, mode_a = _receives(bodies[1], first)
        first_receives_second, mode_b = _receives(bodies[0], second)
        if second_receives_first or first_receives_second:
            mode = mode_a or mode_b
            score = 1.0 if aspect.get("tone") != "stress" else 0.5
            receptions.append({"type": "aspect-reception", "bodies": bodies, "aspect": aspect.get("aspectName"), "mode": mode})
            factors.append(
                _factor(
                    f"aspect-reception-{bodies[0].lower()}-{bodies[1].lower()}",
                    "reception",
                    f"Reception on {aspect.get('aspectName')}",
                    f"{aspect.get('label')} has reception by {mode}, softening or strengthening the contact.",
                    score,
                    "support",
                    bodies[0],
                )
            )

    return {
        **_context(f"Reception scan found {len(receptions)} active relationship(s).", factors),
        "receptions": receptions,
    }


def planet_condition_context(
    positions: Sequence[Mapping[str, object]],
    relevant_names: Sequence[str] = (),
) -> dict[str, object]:
    by_name = _position_by_name(positions)
    sun = by_name.get("Sun")
    factors = []
    conditions = []
    topic_relevant = set(relevant_names) | {"Moon"}
    background_relevant = {"Mercury", "Venus", "Mars", "Jupiter", "Saturn"}
    relevant = topic_relevant | background_relevant
    for planet in positions:
        name = str(planet.get("name"))
        if name == "Sun":
            continue
        motion = planet.get("motion") if isinstance(planet.get("motion"), Mapping) else {}
        daily = float(motion.get("dailyLongitudeChange", 0)) if isinstance(motion, Mapping) else 0.0
        multiplier = 1.0 if name in topic_relevant else 0.4
        condition = {
            "name": name,
            "dailyLongitudeChange": daily,
            "visibility": "unknown",
            "station": "normal",
            "speed": "normal",
            "relevance": "primary" if name in topic_relevant else "background",
        }
        station = motion.get("station") if isinstance(motion, Mapping) else None
        if isinstance(station, Mapping):
            condition["stationDiagnostic"] = dict(station)
        if isinstance(station, Mapping) and station.get("isInStationWindow") and name not in {"Moon"} and name in relevant:
            station_phase = str(station.get("phase", "station window"))
            days = station.get("daysFromStation")
            days_text = f"{float(days):+.1f} days from estimated station" if days is not None else "inside the station scan window"
            score = -1.2 * multiplier
            condition["station"] = station_phase
            factors.append(
                _factor(
                    f"{name.lower()}-station-window",
                    "planet-condition",
                    f"{name} {station_phase}",
                    f"{name} is {days_text}; current speed {daily:+.3f} deg/day.",
                    score,
                    "caution",
                    name,
                )
            )
        elif abs(daily) <= 0.08 and name not in {"Moon"} and name in relevant:
            score = -1.0 * multiplier
            condition["station"] = "stationary"
            factors.append(_factor(f"{name.lower()}-stationary", "planet-condition", f"{name} station pressure", f"{name} is nearly stationary ({daily:+.2f} deg/day).", score, "caution", name))
        elif planet.get("isRetrograde"):
            condition["station"] = "retrograde"
        speed_band = PLANET_SPEED_BANDS.get(name)
        abs_daily = abs(daily)
        if speed_band and name in relevant and condition["station"] == "normal":
            if 0 < abs_daily <= float(speed_band["slow"]):
                condition["speed"] = "very slow"
                factors.append(
                    _factor(
                        f"{name.lower()}-very-slow",
                        "planet-condition",
                        f"{name} very slow",
                        f"{name} is moving only {daily:+.3f} deg/day, below its diagnostic slow threshold.",
                        -0.5 * multiplier,
                        "caution",
                        name,
                    )
                )
            elif abs_daily >= float(speed_band["fast"]) and daily > 0:
                condition["speed"] = "very fast"
                factors.append(
                    _factor(
                        f"{name.lower()}-very-fast",
                        "planet-condition",
                        f"{name} fast motion",
                        f"{name} is moving {daily:+.3f} deg/day, above its diagnostic fast threshold.",
                        0.3 * multiplier,
                        "support",
                        name,
                    )
                )
        if sun:
            separation = angular_distance(float(planet.get("longitude", 0)), float(sun.get("longitude", 0)))
            signed_from_sun = _signed_longitude_delta(float(sun.get("longitude", 0)), float(planet.get("longitude", 0)))
            visibility = solar_visibility_diagnostic(name, separation, signed_from_sun)
            condition["solarSeparation"] = separation
            condition["signedSolarDistance"] = signed_from_sun
            condition["visibility"] = visibility["phase"]
            condition["visibilityDiagnostic"] = visibility
            visibility_score = _visibility_factor_score(visibility["phase"], multiplier)
            if visibility_score and name in relevant:
                factors.append(
                    _factor(
                        f"{name.lower()}-visibility-{visibility['phase']}",
                        "planet-condition",
                        f"{name} {visibility['label']}",
                        (
                            f"{name} is {visibility['label'].lower()} on the {visibility['side']} side "
                            f"of the Sun ({separation:.1f} deg separation; diagnostic confidence)."
                        ),
                        visibility_score,
                        _severity_for_score(visibility_score),
                        name,
                    )
                )
        conditions.append(condition)
    return {
        **_context(f"Planet condition scan found {len(factors)} scored condition(s).", factors, "approximate"),
        "conditions": conditions,
    }


def declination_context(
    positions: Sequence[Mapping[str, object]],
    significator_ctx: Mapping[str, object],
) -> dict[str, object]:
    significator_names = {str(point.get("name")) for point in significator_ctx.get("points", []) if isinstance(point, Mapping)}
    relevant = significator_names | {"Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"}
    points = []
    factors = []
    contacts = []
    usable_positions = [planet for planet in positions if planet.get("declination") is not None]

    for planet in usable_positions:
        name = str(planet.get("name"))
        declination = float(planet.get("declination", 0))
        is_oob = abs(declination) > OUT_OF_BOUNDS_DECLINATION
        points.append(
            {
                "name": name,
                "declination": declination,
                "rightAscensionHours": planet.get("rightAscensionHours"),
                "isOutOfBounds": is_oob,
            }
        )
        if is_oob and name in relevant:
            if name == "Moon":
                score = -1.0
                severity = "caution"
            elif name in MALEFICS:
                score = -0.5
                severity = "caution"
            elif name in BENEFICS:
                score = 0.5
                severity = "support"
            else:
                score = 0.0
                severity = "info"
            factors.append(
                _factor(
                    f"declination-oob-{name.lower()}",
                    "declination",
                    f"{name} out of bounds",
                    f"{name} has declination {declination:+.1f} deg, outside the solar bounds.",
                    score,
                    severity,
                    name,
                )
            )

    for first_index, first in enumerate(usable_positions):
        first_name = str(first.get("name"))
        first_declination = float(first.get("declination", 0))
        for second in usable_positions[first_index + 1 :]:
            second_name = str(second.get("name"))
            second_declination = float(second.get("declination", 0))
            same_side = first_declination * second_declination >= 0
            parallel_orb = abs(first_declination - second_declination)
            contra_orb = abs(first_declination + second_declination)
            contact_type = ""
            orb = 0.0
            if same_side and parallel_orb <= DECLINATION_ORB:
                contact_type = "parallel"
                orb = parallel_orb
            elif not same_side and contra_orb <= DECLINATION_ORB:
                contact_type = "contra-parallel"
                orb = contra_orb
            if not contact_type:
                continue
            involves_key = first_name in relevant or second_name in relevant
            if not involves_key:
                continue
            score = 0.0
            severity = "info"
            bodies = {first_name, second_name}
            if bodies & significator_names:
                if bodies & BENEFICS:
                    score += 0.5
                    severity = "support"
                if bodies & MALEFICS:
                    score -= 0.5
                    severity = "caution" if score < 0 else severity
            contacts.append(
                {
                    "type": contact_type,
                    "bodies": [first_name, second_name],
                    "orb": orb,
                    "declinations": [first_declination, second_declination],
                }
            )
            if score:
                factors.append(
                    _factor(
                        f"declination-{contact_type}-{first_name.lower()}-{second_name.lower()}",
                        "declination",
                        f"{first_name} {contact_type} {second_name}",
                        f"{first_name} and {second_name} are {contact_type} in declination within {orb:.1f} deg.",
                        score,
                        severity,
                        first_name,
                    )
                )

    out_of_bounds_count = sum(1 for point in points if point["isOutOfBounds"])
    return {
        **_context(
            f"Declination scan found {out_of_bounds_count} out-of-bounds body/bodies and {len(contacts)} parallel contact(s).",
            factors,
            "solid",
        ),
        "points": points,
        "contacts": contacts,
        "outOfBoundsLimit": OUT_OF_BOUNDS_DECLINATION,
        "parallelOrb": DECLINATION_ORB,
    }


def advanced_aspect_context(
    detected_aspects: Sequence[Mapping[str, object]],
    positions: Sequence[Mapping[str, object]],
    significator_ctx: Mapping[str, object],
    objective: str = DEFAULT_OBJECTIVE,
) -> dict[str, object]:
    by_name = _position_by_name(positions)
    significator_names = {str(point.get("name")) for point in significator_ctx.get("points", []) if isinstance(point, Mapping)}
    topic = OBJECTIVE_ASPECT_PRIORITIES.get(objective, OBJECTIVE_ASPECT_PRIORITIES[DEFAULT_OBJECTIVE])
    support_bodies = set(topic.get("supportBodies", set()))
    caution_bodies = set(topic.get("cautionBodies", set()))
    factors = []
    patterns = []
    by_body: dict[str, list[Mapping[str, object]]] = {}
    for aspect in detected_aspects:
        for body in aspect.get("bodies", []):
            by_body.setdefault(str(body), []).append(aspect)

    objective_candidates: list[dict[str, object]] = []
    for aspect in detected_aspects:
        bodies = {str(body) for body in aspect.get("bodies", [])}
        if not (bodies & significator_names):
            continue
        timing = _timing_multiplier(aspect)
        label = str(aspect.get("label", "Aspect"))
        tone = str(aspect.get("tone", "mixed"))
        if tone == "support" and bodies & support_bodies:
            score = round(0.6 * timing, 2)
            objective_candidates.append(
                _factor(
                    f"objective-aspect-support-{_slug(label)}",
                    "advanced-aspects",
                    "Objective aspect support",
                    f"{label} supports {topic.get('supportSummary', 'the selected objective')}.",
                    score,
                    "support",
                    next(iter(bodies & significator_names), ""),
                )
            )
        elif tone == "stress" and bodies & caution_bodies:
            score = round(-0.7 * timing, 2)
            objective_candidates.append(
                _factor(
                    f"objective-aspect-caution-{_slug(label)}",
                    "advanced-aspects",
                    "Objective aspect caution",
                    f"{label} can show {topic.get('cautionSummary', 'friction for the selected objective')}.",
                    score,
                    "caution",
                    next(iter(bodies & significator_names), ""),
                )
            )
        elif tone == "mixed" and bodies & support_bodies and not bodies & caution_bodies:
            score = round(0.25 * timing, 2)
            objective_candidates.append(
                _factor(
                    f"objective-aspect-mixed-{_slug(label)}",
                    "advanced-aspects",
                    "Objective aspect emphasis",
                    f"{label} directly involves a key body for {objective}.",
                    score,
                    "support" if score > 0 else "info",
                    next(iter(bodies & significator_names), ""),
                )
            )

    objective_candidates.sort(key=lambda factor: abs(float(factor.get("scoreImpact", 0))), reverse=True)
    for factor in objective_candidates[:3]:
        factors.append(factor)
        patterns.append(
            {
                "type": "objective-importance",
                "objective": objective,
                "title": factor.get("title"),
                "body": factor.get("body"),
                "scoreImpact": factor.get("scoreImpact"),
            }
        )

    for translator in FAST_TRANSLATORS:
        contacts = by_body.get(translator, [])
        applying = [aspect for aspect in contacts if aspect.get("isApplying")]
        separating = [aspect for aspect in contacts if aspect.get("isApplying") is False]
        if applying and separating:
            app = applying[0]
            sep = separating[0]
            app_other = next((str(body) for body in app.get("bodies", []) if body != translator), "")
            sep_other = next((str(body) for body in sep.get("bodies", []) if body != translator), "")
            if app_other and sep_other and {app_other, sep_other} & significator_names:
                patterns.append({"type": "translation", "translator": translator, "from": sep_other, "to": app_other})
                factors.append(
                    _factor(
                        f"translation-{translator.lower()}",
                        "advanced-aspects",
                        f"{translator} translation of light",
                        f"{translator} separates from {sep_other} and applies to {app_other}.",
                        1.0,
                        "support",
                        translator,
                    )
                )

    for collector, contacts in by_body.items():
        applying_contacts = [aspect for aspect in contacts if aspect.get("isApplying")]
        other_bodies = {
            next((str(body) for body in aspect.get("bodies", []) if body != collector), "")
            for aspect in applying_contacts
        }
        other_bodies.discard("")
        if len(other_bodies & significator_names) >= 2:
            speed = abs(float((by_name.get(collector, {}).get("motion") or {}).get("dailyLongitudeChange", 0))) if isinstance(by_name.get(collector, {}).get("motion"), Mapping) else 0
            if speed <= 2:
                patterns.append({"type": "collection", "collector": collector, "bodies": sorted(other_bodies & significator_names)})
                factors.append(
                    _factor(
                        f"collection-{collector.lower()}",
                        "advanced-aspects",
                        f"{collector} collection of light",
                        f"{collector} receives applying contacts from multiple significators.",
                        1.0,
                        "support",
                        collector,
                    )
                )

    applying_with_time = [
        aspect
        for aspect in detected_aspects
        if aspect.get("isApplying") and aspect.get("daysToExact") is not None and len(aspect.get("bodies", [])) == 2
    ]
    applying_with_time.sort(key=lambda aspect: float(aspect.get("daysToExact", 999)))
    seen_interruptions: set[tuple[str, str, str]] = set()
    for primary in applying_with_time:
        primary_bodies = [str(body) for body in primary.get("bodies", [])]
        primary_body_set = set(primary_bodies)
        primary_significators = primary_body_set & significator_names
        if len(primary_significators) < 2:
            continue
        primary_days = float(primary.get("daysToExact", 999))
        for interrupting in applying_with_time:
            if interrupting is primary:
                continue
            interrupt_days = float(interrupting.get("daysToExact", 999))
            if interrupt_days >= primary_days:
                continue
            interrupt_bodies = [str(body) for body in interrupting.get("bodies", [])]
            interrupt_set = set(interrupt_bodies)
            shared = primary_body_set & interrupt_set
            outsiders = interrupt_set - primary_body_set
            if not shared or not outsiders:
                continue
            outsider = next(iter(outsiders))
            shared_body = next(iter(shared))
            key = ("prohibition", str(primary.get("label", "")), str(interrupting.get("label", "")))
            if key in seen_interruptions:
                continue
            seen_interruptions.add(key)
            severity_score = -1.0 if outsider in MALEFICS or interrupting.get("tone") == "stress" else -0.5
            patterns.append(
                {
                    "type": "prohibition",
                    "intendedAspect": primary.get("label"),
                    "interruptingAspect": interrupting.get("label"),
                    "sharedBody": shared_body,
                    "interrupter": outsider,
                    "intendedDaysToExact": primary_days,
                    "interruptingDaysToExact": interrupt_days,
                }
            )
            factors.append(
                _factor(
                    f"prohibition-{_slug(shared_body)}-{_slug(outsider)}",
                    "advanced-aspects",
                    "Possible prohibition",
                    (
                        f"{primary.get('label')} perfects in {primary.get('timeToExactText') or f'{primary_days:.1f}d'}, "
                        f"but {interrupting.get('label')} perfects sooner."
                    ),
                    severity_score,
                    "caution",
                    shared_body,
                )
            )

    seen_frustrations: set[tuple[str, str, str]] = set()
    for target, contacts in by_body.items():
        target_applying = [
            aspect
            for aspect in contacts
            if aspect.get("isApplying") and aspect.get("daysToExact") is not None and len(aspect.get("bodies", [])) == 2
        ]
        if len(target_applying) < 2:
            continue
        target_applying.sort(key=lambda aspect: float(aspect.get("daysToExact", 999)))
        for later in target_applying[1:]:
            later_bodies = {str(body) for body in later.get("bodies", [])}
            if not (later_bodies & significator_names):
                continue
            earlier = target_applying[0]
            earlier_bodies = {str(body) for body in earlier.get("bodies", [])}
            earlier_other = next((body for body in earlier_bodies if body != target), "")
            later_other = next((body for body in later_bodies if body != target), "")
            if not earlier_other or not later_other or earlier_other == later_other:
                continue
            key = ("frustration", target, later_other)
            if key in seen_frustrations:
                continue
            seen_frustrations.add(key)
            earlier_days = float(earlier.get("daysToExact", 999))
            later_days = float(later.get("daysToExact", 999))
            if earlier_days >= later_days:
                continue
            patterns.append(
                {
                    "type": "frustration",
                    "target": target,
                    "earlierAspect": earlier.get("label"),
                    "laterAspect": later.get("label"),
                    "earlierBody": earlier_other,
                    "laterBody": later_other,
                    "earlierDaysToExact": earlier_days,
                    "laterDaysToExact": later_days,
                }
            )
            factors.append(
                _factor(
                    f"frustration-{_slug(target)}-{_slug(later_other)}",
                    "advanced-aspects",
                    "Possible frustration",
                    (
                        f"{target} perfects with {earlier_other} before {later.get('label')} can complete, "
                        f"which may redirect the promised contact."
                    ),
                    -0.75,
                    "caution",
                    target,
                )
            )

    for aspect in detected_aspects:
        bodies = {str(body) for body in aspect.get("bodies", [])}
        if bodies & significator_names and aspect.get("isApplying") and aspect.get("tone") == "stress":
            factors.append(
                _factor(
                    f"significator-stress-{aspect.get('label', '').replace(' ', '-').lower()}",
                    "advanced-aspects",
                    "Applying stress to significator",
                    f"{aspect.get('label')} is tightening and involves a key significator.",
                    -1.0,
                    "caution",
                    next(iter(bodies & significator_names), ""),
                )
            )

    return {
        **_context(f"Advanced aspect scan found {len(patterns)} traditional pattern(s).", factors, "experimental"),
        "patterns": patterns,
    }


def fixed_star_context(contacts: Sequence[Mapping[str, object]]) -> dict[str, object]:
    factors: list[dict[str, object]] = []
    for contact in contacts:
        score = float(contact.get("score", 0))
        label = str(contact.get("label", "Fixed-star contact"))
        star_id = str(contact.get("starId", "fixed-star")).replace(" ", "-").lower()
        body = str(contact.get("body", ""))
        detail_parts = [
            f"{contact.get('orbText', 'n/a')} longitude orb",
            f"limit {contact.get('orbLimitText', 'n/a')}",
        ]
        if contact.get("latitudeDistanceText"):
            detail_parts.append(f"latitude gap {contact.get('latitudeDistanceText')}")
        if contact.get("contactStrength") is not None:
            detail_parts.append(f"strength {float(contact.get('contactStrength', 0)):.2f}")
        if contact.get("precision"):
            detail_parts.append(str(contact.get("precision")))
        factor = _factor(
            f"fixed-star-{body.lower().replace(' ', '-')}-{star_id}",
            "fixed-stars",
            label,
            "; ".join(detail_parts),
            score,
            _severity_for_score(score),
            body,
        )
        factor["star"] = contact.get("star")
        factor["precision"] = contact.get("precision", "longitude-only")
        factor["contactStrength"] = contact.get("contactStrength")
        factors.append(factor)

    if not factors:
        return _context("No fixed-star conjunctions were found inside the diagnostic star orbs.", [], "approximate")
    return _context(f"{len(factors)} fixed-star contact(s) found with diagnostic orb and strength scoring.", factors, "approximate")


def build_judgment_contexts(
    positions: Sequence[Mapping[str, object]],
    angles: Sequence[Mapping[str, object]],
    house_cusps: Sequence[Mapping[str, object]],
    detected_aspects: Sequence[Mapping[str, object]],
    lunar_phase: Mapping[str, object],
    objective: str = DEFAULT_OBJECTIVE,
    planetary_hour: Mapping[str, object] | None = None,
) -> dict[str, dict[str, object]]:
    significators = significator_context(positions, angles, house_cusps, objective)
    moon = moon_condition_context(positions, detected_aspects, lunar_phase)
    house_rulers = house_ruler_context(positions, house_cusps, objective)
    matter_lords = matter_lord_context(positions, angles, house_cusps, detected_aspects, objective, planetary_hour)
    reception = reception_context(positions, detected_aspects, significators)
    objective_analyzer = objective_analyzer_context(positions, house_cusps, detected_aspects, objective, reception)
    relevant_names = [str(point.get("name")) for point in significators.get("points", []) if isinstance(point, Mapping)]
    planet_condition = planet_condition_context(positions, relevant_names)
    declination = declination_context(positions, significators)
    advanced_aspects = advanced_aspect_context(detected_aspects, positions, significators, objective)
    return {
        "significatorContext": significators,
        "moonCondition": moon,
        "houseRulerContext": house_rulers,
        "matterLordContext": matter_lords,
        "receptionContext": reception,
        "objectiveAnalyzer": objective_analyzer,
        "planetConditionContext": planet_condition,
        "declinationContext": declination,
        "advancedAspectContext": advanced_aspects,
    }


def judgment_rule_factors(contexts: Mapping[str, Mapping[str, object]]) -> list[dict[str, object]]:
    rules = []
    for context_key, context in contexts.items():
        factors = context.get("factors", []) if isinstance(context, Mapping) else []
        for factor in factors:
            if not isinstance(factor, Mapping) or not float(factor.get("scoreImpact", 0)):
                continue
            rules.append(
                {
                    "id": str(factor.get("id", context_key)),
                    "category": str(factor.get("category", context_key)),
                    "severity": str(factor.get("severity", "info")),
                    "title": str(factor.get("title", "Judgment factor")),
                    "body": str(factor.get("body", "")),
                    "scoreImpact": float(factor.get("scoreImpact", 0)),
                    "detail": str(factor.get("detail", "")),
                }
            )
    return rules
