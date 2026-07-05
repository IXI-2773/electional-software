"""Phase 2 tactical analysis orchestration."""

from __future__ import annotations

from typing import Mapping, Sequence

from .action_moment import resolve_action_moment_with_pack
from .fast_lane import build_fast_lane_report
from .final_command import build_final_command
from .playbooks import build_event_playbook
from .practicality import build_practicality_report
from .strategic_calendar import build_strategic_calendar
from .tactical_models import TacticalAnalysisReport
from .timing_traps import detect_timing_traps


def build_tactical_analysis_report(
    candidate: Mapping[str, object],
    *,
    neighbors: Sequence[Mapping[str, object]] | None = None,
    candidates: Sequence[Mapping[str, object]] | None = None,
    emergency_mode: bool = False,
) -> TacticalAnalysisReport:
    objective = str(candidate.get("objective") or "general")
    action_moment = resolve_action_moment_with_pack(objective)
    trap_report = detect_timing_traps(candidate, neighbors)
    practicality = build_practicality_report(candidate, action_moment, trap_report)
    final_command = build_final_command(
        candidate,
        traps=trap_report,
        practicality=practicality,
        candidates=candidates,
        emergency_mode=emergency_mode,
    )
    playbook = build_event_playbook(objective)
    fast_lane = build_fast_lane_report(final_command, action_moment, trap_report, practicality)
    calendar_context = build_strategic_calendar([candidate], objective=objective, view="daily", top_n=1)
    warnings = tuple(
        dict.fromkeys(
            list(trap_report.warnings)
            + list(action_moment.warnings)
            + list(final_command.warnings)
            + list(calendar_context.warnings)
        )
    )
    confidence = round(
        max(
            0.2,
            min(
                0.99,
                (
                    trap_report.confidence
                    + practicality.confidence
                    + final_command.confidence
                    + action_moment.confidence
                    + playbook.confidence
                    + fast_lane.confidence
                )
                / 6,
            ),
        ),
        2,
    )
    return TacticalAnalysisReport(
        final_command=final_command,
        timing_traps=trap_report,
        action_moment=action_moment,
        playbook=playbook,
        practicality=practicality,
        strategic_calendar_context=calendar_context,
        fast_lane=fast_lane,
        warnings=warnings[:8],
        confidence=confidence,
    )


def annotate_tactical_analysis(
    windows: Sequence[dict[str, object]],
    *,
    all_candidates: Sequence[Mapping[str, object]] | None = None,
    emergency_mode: bool = False,
) -> list[dict[str, object]]:
    population = list(all_candidates or windows)
    annotated: list[dict[str, object]] = []
    for window in windows:
        item = dict(window)
        report = build_tactical_analysis_report(
            item,
            neighbors=_nearby_samples(item, population),
            candidates=population,
            emergency_mode=emergency_mode or bool(item.get("emergencyOnly")),
        )
        item["tacticalAnalysis"] = report.to_json()
        item["tactical_analysis"] = item["tacticalAnalysis"]
        item["engine_schema_version"] = "phase2_tactical_output_v1"
        annotated.append(item)
    return annotated


def _nearby_samples(candidate: Mapping[str, object], population: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    moment = candidate.get("date")
    if moment is None:
        return list(population)
    return [item for item in population if item is not candidate]
