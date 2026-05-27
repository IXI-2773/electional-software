"""Layered electional judgment contexts for chart snapshots."""

from __future__ import annotations

from typing import Mapping, Sequence

from .aspects import angular_distance, format_duration
from .presets import DETRIMENTS, EXALTATIONS, FALLS, RULERS, get_bound_lord

BENEFICS = {"Venus", "Jupiter"}
MALEFICS = {"Mars", "Saturn"}
FAST_TRANSLATORS = {"Moon", "Mercury", "Venus"}

OBJECTIVE_TOPICS: dict[str, dict[str, object]] = {
    "Launch or publish": {"houses": (10,), "planets": ("Sun", "Mercury"), "label": "public launch"},
    "Meeting or negotiation": {"houses": (3, 7), "planets": ("Mercury", "Venus"), "label": "meeting"},
    "Creative work": {"houses": (5,), "planets": ("Venus", "Sun"), "label": "creative work"},
    "Relationship timing": {"houses": (7,), "planets": ("Venus", "Moon"), "label": "relationship"},
    "Travel departure": {"houses": (9,), "planets": ("Mercury", "Jupiter"), "label": "travel"},
    "Money or business": {"houses": (2, 11), "planets": ("Jupiter", "Venus"), "label": "money or business"},
    "Health or surgery caution": {"houses": (1, 6, 8), "planets": ("Mars", "Saturn"), "label": "health caution"},
}

DEFAULT_OBJECTIVE = "Launch or publish"


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
    relevant = set(relevant_names) | {"Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"}
    for planet in positions:
        name = str(planet.get("name"))
        if name == "Sun":
            continue
        motion = planet.get("motion") if isinstance(planet.get("motion"), Mapping) else {}
        daily = float(motion.get("dailyLongitudeChange", 0)) if isinstance(motion, Mapping) else 0.0
        condition = {"name": name, "dailyLongitudeChange": daily, "visibility": "unknown", "station": "normal"}
        if abs(daily) <= 0.08 and name not in {"Moon"} and name in relevant:
            condition["station"] = "stationary"
            factors.append(_factor(f"{name.lower()}-stationary", "planet-condition", f"{name} station pressure", f"{name} is nearly stationary ({daily:+.2f} deg/day).", -1.0, "caution", name))
        elif planet.get("isRetrograde"):
            condition["station"] = "retrograde"
        if sun:
            separation = angular_distance(float(planet.get("longitude", 0)), float(sun.get("longitude", 0)))
            condition["solarSeparation"] = separation
            if separation <= 0.283333:
                condition["visibility"] = "cazimi"
                if name in relevant:
                    factors.append(_factor(f"{name.lower()}-cazimi-condition", "planet-condition", f"{name} cazimi", f"{name} is in the heart of the Sun; solar-condition rules handle the score.", 0.0, "info", name))
            elif separation <= 8.5:
                condition["visibility"] = "combust"
                if name in relevant:
                    factors.append(_factor(f"{name.lower()}-combust-condition", "planet-condition", f"{name} combust", f"{name} is combust the Sun; solar-condition rules handle the score.", 0.0, "info", name))
            elif separation <= 15:
                condition["visibility"] = "under beams"
                if name in relevant:
                    factors.append(_factor(f"{name.lower()}-under-beams-condition", "planet-condition", f"{name} under beams", f"{name} is under the Sun's beams; solar-condition rules handle the score.", 0.0, "info", name))
            else:
                condition["visibility"] = "clear"
        conditions.append(condition)
    return {
        **_context(f"Planet condition scan found {len(factors)} scored condition(s).", factors, "approximate"),
        "conditions": conditions,
    }


def advanced_aspect_context(
    detected_aspects: Sequence[Mapping[str, object]],
    positions: Sequence[Mapping[str, object]],
    significator_ctx: Mapping[str, object],
) -> dict[str, object]:
    by_name = _position_by_name(positions)
    significator_names = {str(point.get("name")) for point in significator_ctx.get("points", []) if isinstance(point, Mapping)}
    factors = []
    patterns = []
    by_body: dict[str, list[Mapping[str, object]]] = {}
    for aspect in detected_aspects:
        for body in aspect.get("bodies", []):
            by_body.setdefault(str(body), []).append(aspect)

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


def build_judgment_contexts(
    positions: Sequence[Mapping[str, object]],
    angles: Sequence[Mapping[str, object]],
    house_cusps: Sequence[Mapping[str, object]],
    detected_aspects: Sequence[Mapping[str, object]],
    lunar_phase: Mapping[str, object],
    objective: str = DEFAULT_OBJECTIVE,
) -> dict[str, dict[str, object]]:
    significators = significator_context(positions, angles, house_cusps, objective)
    moon = moon_condition_context(positions, detected_aspects, lunar_phase)
    house_rulers = house_ruler_context(positions, house_cusps, objective)
    reception = reception_context(positions, detected_aspects, significators)
    relevant_names = [str(point.get("name")) for point in significators.get("points", []) if isinstance(point, Mapping)]
    planet_condition = planet_condition_context(positions, relevant_names)
    advanced_aspects = advanced_aspect_context(detected_aspects, positions, significators)
    return {
        "significatorContext": significators,
        "moonCondition": moon,
        "houseRulerContext": house_rulers,
        "receptionContext": reception,
        "planetConditionContext": planet_condition,
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
