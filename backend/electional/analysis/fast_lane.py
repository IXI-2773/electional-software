"""Minimal operational output for time-sensitive decisions."""

from __future__ import annotations

from datetime import datetime

from .tactical_models import ActionMoment, FastLaneReport, FinalCommand, PracticalityReport, TimingTrapReport

FAST_LANE_CONTRACT_ID = "fast_lane_report_v1"
FAST_LANE_CONTRACT_VERSION = 1
FAST_LANE_CAPABILITY_SCHEMA_VERSION = "fast_lane_capability_manifest_v1"
FAST_LANE_ACCEPTED_INPUT_SCHEMA_VERSIONS = [
    "tactical_final_command_v1",
    "tactical_action_moment_v1",
    "tactical_timing_trap_report_v1",
    "tactical_practicality_report_v1",
]
FAST_LANE_SUPPORTED_RULE_SCHEMA_VERSIONS = ["canonical_mutable_rule_v1"]
FAST_LANE_SUPPORTED_CONDITION_OPERATORS = [
    "equals",
    "not_equals",
    "greater_than",
    "greater_than_or_equal",
    "less_than",
    "less_than_or_equal",
    "between",
    "in",
    "contains",
]
FAST_LANE_SUPPORTED_INPUT_FIELDS = [
    "action_moment.elected_moment",
    "action_moment.instructions",
    "action_moment.warnings",
    "fast_lane.action",
    "fast_lane.best",
    "fast_lane.command",
    "fast_lane.confidence",
    "fast_lane.cutoff",
    "fast_lane.main_reason",
    "fast_lane.main_risk",
    "fast_lane.warnings",
    "fast_lane.window",
    "final_command.best_minute",
    "final_command.command",
    "final_command.confidence",
    "final_command.cutoff_time",
    "final_command.do_not_use_after",
    "final_command.primary_reason",
    "final_command.risk_reasons",
    "final_command.use_window_end",
    "final_command.use_window_start",
    "final_command.warnings",
    "practicality.confidence",
    "practicality.risks",
    "timing_traps.confidence",
    "timing_traps.traps.title",
]
FAST_LANE_SUPPORTED_INPUT_FIELD_FAMILIES = [
    "action_moment",
    "fast_lane",
    "final_command",
    "practicality",
    "timing_traps",
]
FAST_LANE_SUPPORTED_ACTION_TYPES = ["fast_lane.command"]
FAST_LANE_SUPPORTED_RESULT_TYPES = ["FastLaneReport"]
FAST_LANE_SUPPORTED_COMMAND_VALUES = [
    "LEAST_BAD_ONLY",
    "NEEDS_MORE_DATA",
    "REJECT",
    "REQUIRES_EXACT_TIMING",
    "SEARCH_NEXT_DAY",
    "USE",
    "USE_IF_NECESSARY",
    "USE_WIDE_WINDOW",
]
FAST_LANE_REQUIRED_PROVENANCE_FIELDS = [
    "canonical_rule_id",
    "document_id",
    "source_revision",
    "rule_fingerprint",
    "certification_receipt_id",
    "certification_fingerprint",
]
FAST_LANE_VALUE_TYPES_BY_FIELD = {
    "action_moment.elected_moment": ["string"],
    "action_moment.instructions": ["list[string]"],
    "action_moment.warnings": ["list[string]"],
    "fast_lane.action": ["string"],
    "fast_lane.best": ["string"],
    "fast_lane.command": ["enum:string"],
    "fast_lane.confidence": ["number"],
    "fast_lane.cutoff": ["string"],
    "fast_lane.main_reason": ["string"],
    "fast_lane.main_risk": ["string"],
    "fast_lane.warnings": ["list[string]"],
    "fast_lane.window": ["string"],
    "final_command.best_minute": ["timestamp"],
    "final_command.command": ["enum:string"],
    "final_command.confidence": ["number"],
    "final_command.cutoff_time": ["timestamp"],
    "final_command.do_not_use_after": ["timestamp"],
    "final_command.primary_reason": ["string"],
    "final_command.risk_reasons": ["list[string]"],
    "final_command.use_window_end": ["timestamp"],
    "final_command.use_window_start": ["timestamp"],
    "final_command.warnings": ["list[string]"],
    "practicality.confidence": ["number"],
    "practicality.risks": ["list[string]"],
    "timing_traps.confidence": ["number"],
    "timing_traps.traps.title": ["list[string]"],
}


def build_fast_lane_report(
    final_command: FinalCommand,
    action_moment: ActionMoment,
    traps: TimingTrapReport,
    practicality: PracticalityReport,
) -> FastLaneReport:
    window = _range(final_command.use_window_start, final_command.use_window_end)
    best = _time(final_command.best_minute)
    cutoff = _time(final_command.cutoff_time or final_command.do_not_use_after)
    main_risk = (
        traps.traps[0].title
        if traps.traps
        else final_command.risk_reasons[0]
        if final_command.risk_reasons
        else practicality.risks[0]
        if practicality.risks
        else "No major tactical risk surfaced."
    )
    action = action_moment.instructions[-1] if action_moment.instructions else action_moment.elected_moment
    return FastLaneReport(
        command=final_command.command,
        window=window,
        best=best,
        cutoff=cutoff,
        main_reason=final_command.primary_reason,
        main_risk=main_risk,
        action=action,
        confidence=min(final_command.confidence, practicality.confidence, traps.confidence),
        warnings=final_command.warnings + action_moment.warnings[:1],
    )


def format_fast_lane_text(report: FastLaneReport) -> str:
    return (
        "FAST LANE:\n\n"
        f"{report.command.replace('_', ' ')}\n"
        f"Window: {report.window}\n"
        f"Best: {report.best}\n"
        f"Cutoff: {report.cutoff}\n\n"
        f"Main reason:\n{report.main_reason}\n\n"
        f"Main risk:\n{report.main_risk}\n\n"
        f"Action:\n{report.action}"
    )


def get_fast_lane_capability_manifest() -> dict[str, object]:
    return {
        "schema_version": FAST_LANE_CAPABILITY_SCHEMA_VERSION,
        "fast_lane_contract_id": FAST_LANE_CONTRACT_ID,
        "fast_lane_contract_version": FAST_LANE_CONTRACT_VERSION,
        "accepted_input_schema_versions": list(FAST_LANE_ACCEPTED_INPUT_SCHEMA_VERSIONS),
        "supported_rule_schema_versions": list(FAST_LANE_SUPPORTED_RULE_SCHEMA_VERSIONS),
        "supported_condition_operators": list(FAST_LANE_SUPPORTED_CONDITION_OPERATORS),
        "supported_input_fields": list(FAST_LANE_SUPPORTED_INPUT_FIELDS),
        "supported_input_field_families": list(FAST_LANE_SUPPORTED_INPUT_FIELD_FAMILIES),
        "supported_action_types": list(FAST_LANE_SUPPORTED_ACTION_TYPES),
        "supported_action_values": {"fast_lane.command": list(FAST_LANE_SUPPORTED_COMMAND_VALUES)},
        "supported_result_types": list(FAST_LANE_SUPPORTED_RESULT_TYPES),
        "required_provenance_fields": list(FAST_LANE_REQUIRED_PROVENANCE_FIELDS),
        "value_types_by_field": {key: list(value) for key, value in FAST_LANE_VALUE_TYPES_BY_FIELD.items()},
        "requires_active_rule": True,
        "requires_certification": True,
        "supports_read_only_evaluation": True,
        "deterministic": True,
    }


def _range(start: datetime | None, end: datetime | None) -> str:
    if start is None and end is None:
        return "unknown"
    if start is not None and end is not None:
        return f"{_time(start)}-{_time(end)}"
    return _time(start or end)


def _time(moment: datetime | None) -> str:
    return moment.strftime("%I:%M %p").lstrip("0") if isinstance(moment, datetime) else "unknown"
