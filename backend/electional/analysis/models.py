"""Typed advanced-analysis models with JSON-friendly projections."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PlanetRoleProfile:
    planet: str
    roles: tuple[str, ...]
    role_summary: str
    confidence: float
    warnings: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SignificatorPurityProfile:
    planet: str
    purity_score: int | None
    purity_band: str
    summary: str
    positive_factors: tuple[str, ...]
    negative_factors: tuple[str, ...]
    confidence: float
    warnings: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ContradictionFinding:
    id: str
    severity: str
    title: str
    description: str
    affected_planets: tuple[str, ...]
    affected_scores: tuple[str, ...]
    recommendation: str
    confidence: float
    impact: str = "explanatory"

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ControlSideReport:
    planets: tuple[str, ...]
    strength: int | None

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ControlIndexReport:
    control_score: int | None
    band: str
    summary: str
    user_side: ControlSideReport
    resistance_side: ControlSideReport
    authority_side: ControlSideReport
    main_supports: tuple[str, ...]
    main_risks: tuple[str, ...]
    confidence: float
    warnings: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        return {
            "control_score": self.control_score,
            "band": self.band,
            "summary": self.summary,
            "user_side": self.user_side.to_json(),
            "resistance_side": self.resistance_side.to_json(),
            "authority_side": self.authority_side.to_json(),
            "main_supports": list(self.main_supports),
            "main_risks": list(self.main_risks),
            "confidence": self.confidence,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class ResistanceSideReport:
    significators: tuple[str, ...]
    strength: int | None
    purity: int | None
    summary: str

    def to_json(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ResistanceAnalysisReport:
    resistance_mode: str
    user_side: ResistanceSideReport
    opponent_side: ResistanceSideReport
    authority_side: ResistanceSideReport
    outcome_side: ResistanceSideReport
    advantage: str
    advantage_score: int | None
    main_reasons: tuple[str, ...]
    risks: tuple[str, ...]
    confidence: float
    warnings: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        return {
            "resistance_mode": self.resistance_mode,
            "user_side": self.user_side.to_json(),
            "opponent_side": self.opponent_side.to_json(),
            "authority_side": self.authority_side.to_json(),
            "outcome_side": self.outcome_side.to_json(),
            "advantage": self.advantage,
            "advantage_score": self.advantage_score,
            "main_reasons": list(self.main_reasons),
            "risks": list(self.risks),
            "confidence": self.confidence,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class AdvancedAnalysisReport:
    planet_roles: tuple[PlanetRoleProfile, ...]
    significator_purity: tuple[SignificatorPurityProfile, ...]
    contradictions: tuple[ContradictionFinding, ...]
    control_index: ControlIndexReport
    resistance_analysis: ResistanceAnalysisReport
    final_tactical_interpretation: str
    warnings: tuple[str, ...]
    confidence: float

    def to_json(self) -> dict[str, object]:
        return {
            "planet_roles": [item.to_json() for item in self.planet_roles],
            "significator_purity": [item.to_json() for item in self.significator_purity],
            "contradictions": [item.to_json() for item in self.contradictions],
            "control_index": self.control_index.to_json(),
            "resistance_analysis": self.resistance_analysis.to_json(),
            "final_tactical_interpretation": self.final_tactical_interpretation,
            "warnings": list(self.warnings),
            "confidence": self.confidence,
        }
