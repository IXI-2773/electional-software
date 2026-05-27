"""Typed backend data models with JSON-friendly projections."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ScoreReason:
    code: str
    label: str
    value: float
    count: int | None = None
    raw: float | None = None

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        return {key: value for key, value in payload.items() if value is not None}


@dataclass(frozen=True)
class ScoreBreakdown:
    base: int
    support: int
    mixed: int
    stress: int
    applying_support: int
    applying_stress: int
    objective_matches: int
    close_contacts: int
    angularity: float
    dignity: float
    retrograde_pressure: float
    fixed_star: float
    electional_rules: float
    aspect_timing: float
    accounting: dict[str, object]
    evaluation: dict[str, object]
    raw_score: float
    score: int
    reasons: tuple[ScoreReason, ...]

    def to_json(self) -> dict[str, object]:
        return {
            "base": self.base,
            "support": self.support,
            "mixed": self.mixed,
            "stress": self.stress,
            "applyingSupport": self.applying_support,
            "applyingStress": self.applying_stress,
            "objectiveMatches": self.objective_matches,
            "closeContacts": self.close_contacts,
            "angularity": self.angularity,
            "dignity": self.dignity,
            "retrogradePressure": self.retrograde_pressure,
            "fixedStar": self.fixed_star,
            "electionalRules": self.electional_rules,
            "aspectTiming": self.aspect_timing,
            "accounting": self.accounting,
            "evaluation": self.evaluation,
            "rawScore": self.raw_score,
            "score": self.score,
            "reasons": [reason.to_json() for reason in self.reasons],
        }
