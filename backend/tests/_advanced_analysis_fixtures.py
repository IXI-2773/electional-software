from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace


DEFAULT_HOUSE_SIGNS = [
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Taurus",
    "Scorpio",
    "Sagittarius",
    "Pisces",
    "Capricorn",
    "Aquarius",
    "Aries",
    "Libra",
]


def fixture_position(
    name: str,
    sign: str,
    house: int,
    *,
    dignity_score: int = 0,
    dignity_label: str = "Peregrine",
    angular: bool = False,
    retrograde: bool = False,
    phase: str = "free",
    distance: float = 8.0,
) -> dict[str, object]:
    return {
        "name": name,
        "longitude": house * 30.0,
        "zodiac": {"sign": sign, "degree": (house * 2) % 30, "minute": 0},
        "house": house,
        "isAngular": angular,
        "isRetrograde": retrograde,
        "closestAngle": {"shortName": "ASC" if angular else "MC", "distance": distance},
        "dignity": {
            "score": dignity_score,
            "label": dignity_label,
            "boundLord": sign,
            "isOwnBound": False,
        },
        "motion": {
            "label": "Retrograde" if retrograde else "Direct",
            "dailyLongitudeChange": -0.6 if retrograde else 1.0,
            "isStationary": False,
        },
        "solarCondition": {"phase": phase},
    }


def fixture_snapshot(
    *,
    objective: str = "Exam / certification",
    score: int = 88,
    confidence: int = 84,
    cleanliness: int = 78,
    volatility: int = 20,
    readiness: int = 82,
    house_signs: list[str] | None = None,
    aspects: list[dict[str, object]] | None = None,
    fragility: str = "Low",
    moon_void: bool = False,
) -> dict[str, object]:
    house_signs = list(house_signs or DEFAULT_HOUSE_SIGNS)
    snapshot = {
        "date": datetime(2026, 7, 1, 9, 0),
        "formattedTime": "2026-07-01 09:00 AM",
        "time": "09:00 AM",
        "title": "Electional window",
        "note": "Deterministic fixture",
        "objective": objective,
        "engine": "python",
        "preset": SimpleNamespace(name="Classical"),
        "zodiacSystem": SimpleNamespace(name="Tropical"),
        "houseSystem": SimpleNamespace(name="Whole Sign"),
        "ayanamsha": 0.0,
        "angles": [
            {"id": "asc", "zodiac": {"sign": house_signs[0], "degree": 0, "minute": 0}},
            {"id": "mc", "zodiac": {"sign": house_signs[9], "degree": 0, "minute": 0}},
        ],
        "houseCusps": [
            {"house": index + 1, "zodiac": {"sign": sign, "degree": 0, "minute": 0}}
            for index, sign in enumerate(house_signs)
        ],
        "positions": [
            fixture_position("Sun", "Cancer", 2, dignity_score=1),
            fixture_position("Moon", "Taurus", 11, dignity_score=3, dignity_label="Exalted"),
            fixture_position("Mercury", "Gemini", 1, dignity_score=5, dignity_label="Domicile", angular=True, distance=2.0),
            fixture_position("Venus", "Pisces", 10, dignity_score=4, dignity_label="Exalted", angular=True, distance=3.0),
            fixture_position("Mars", "Aries", 11, dignity_score=2, dignity_label="Domicile"),
            fixture_position("Jupiter", "Pisces", 7, dignity_score=4, dignity_label="Domicile", angular=True, distance=4.0),
            fixture_position("Saturn", "Capricorn", 9, dignity_score=5, dignity_label="Domicile"),
        ],
        "detectedAspects": list(aspects or []),
        "planetaryHour": {
            "available": True,
            "dayRuler": "Sun",
            "hourRuler": "Mercury",
            "hourNumber": 2,
            "period": "day",
            "periodStartText": "09:00 AM",
            "periodEndText": "10:00 AM",
        },
        "matterLordContext": {
            "yearLord": "Sun",
            "scoreImpact": 1.8,
            "factors": [{"title": "Matter lord well placed", "scoreImpact": 2.0}],
        },
        "moonCondition": {"voidOfCourse": {"isVoid": moon_void}},
        "lunarPhase": {"name": "Waxing Gibbous", "illumination": 0.74, "ageDays": 10.2, "isWaxing": True},
        "score": score,
        "scoreBreakdown": {
            "score": score,
            "objectiveMatches": 2,
            "diagnostics": {
                "confidence": {"score": confidence},
                "cleanliness": {"score": cleanliness},
                "volatility": {"score": volatility},
                "readiness": {"score": readiness},
            },
            "evaluation": {
                "band": "Strong",
                "grade": "A-" if score >= 85 else "B+",
                "summary": "Fixture evaluation summary.",
                "strengths": ["Moon support", "Strong Mercury"],
                "risks": ["Mars pressure"],
            },
        },
        "timingProfile": {"summary": "Stable timing window."},
        "windowStability": {"classification": "stable", "samples": [{"score": score}] * 6},
        "fragility": {"band": fragility},
        "ruleEvaluations": {},
        "accuracyAudit": {"label": "Pass", "summary": "Fixture audit."},
        "calculationBackend": {},
        "calculationNotes": [],
        "lots": [],
        "lunarNodes": [],
        "fixedStarContacts": [],
        "constellationContext": {},
        "angleContext": {},
    }
    return snapshot


def set_planet(snapshot: dict[str, object], planet_name: str, **updates: object) -> None:
    for position in snapshot.get("positions", []):
        if isinstance(position, dict) and position.get("name") == planet_name:
            position.update(updates)
            return
    raise KeyError(planet_name)


def add_aspect(
    snapshot: dict[str, object],
    first: str,
    second: str,
    *,
    tone: str = "support",
    is_applying: bool = True,
    label: str | None = None,
) -> None:
    snapshot.setdefault("detectedAspects", []).append(
        {
            "label": label or f"{first} {tone} {second}",
            "aspectName": "Trine" if tone == "support" else "Square",
            "orb": 0.8,
            "orbText": "0.8 deg",
            "tone": tone,
            "isApplying": is_applying,
            "phaseLabel": "Applying" if is_applying else "Separating",
            "bodies": [first, second],
        }
    )
