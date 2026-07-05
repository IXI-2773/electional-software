"""Regression replay comparison for Core, Phase 1, Phase 2, and Fast Lane drift."""

from __future__ import annotations

from datetime import datetime
from typing import Mapping


def compare_regression_snapshots(old: Mapping[str, object], new: Mapping[str, object]) -> dict[str, object]:
    drifts: list[dict[str, object]] = []
    _compare_hard_gate(old, new, drifts)
    _compare_core_metrics(old, new, drifts)
    _compare_phase1(old, new, drifts)
    _compare_phase2(old, new, drifts)
    review_required = [item for item in drifts if item["severity"] in {"major", "critical"}]
    return {
        "status": "drift" if drifts else "unchanged",
        "drifts": drifts,
        "review_required": review_required,
        "summary": f"{len(drifts)} drift(s), {len(review_required)} requiring review.",
    }


def _compare_core_metrics(old: Mapping[str, object], new: Mapping[str, object], drifts: list[dict[str, object]]) -> None:
    old_score = _number(old.get("score"))
    new_score = _number(new.get("score"))
    if old_score is not None and new_score is not None:
        delta = abs(new_score - old_score)
        if delta > 15:
            _drift(drifts, "score_drift", "major", "Score changed materially", old_score, new_score, "Review score ledger and rule output.")
        elif delta >= 5:
            _drift(drifts, "score_drift", "warning", "Score changed", old_score, new_score, "Review score drift.")
        elif delta > 0:
            _drift(drifts, "score_drift", "minor", "Score changed slightly", old_score, new_score, "Track minor score drift.")
    old_grade = _grade_rank(old.get("grade"))
    new_grade = _grade_rank(new.get("grade"))
    if old_grade is not None and new_grade is not None and old_grade != new_grade:
        severity = "major" if abs(new_grade - old_grade) >= 2 else "warning"
        _drift(drifts, "grade_drift", severity, "Grade changed", old.get("grade"), new.get("grade"), "Review score-to-grade classification.")
    old_conf = _confidence(old)
    new_conf = _confidence(new)
    if old_conf is not None and new_conf is not None:
        delta = old_conf - new_conf
        if delta > 0.20:
            _drift(drifts, "confidence_drift", "major", "Confidence dropped materially", old_conf, new_conf, "Review data and analysis confidence.")
        elif delta >= 0.10:
            _drift(drifts, "confidence_drift", "warning", "Confidence dropped", old_conf, new_conf, "Review confidence drift.")


def _compare_hard_gate(old: Mapping[str, object], new: Mapping[str, object], drifts: list[dict[str, object]]) -> None:
    old_status = _hard_gate_status(old)
    new_status = _hard_gate_status(new)
    if old_status != new_status:
        _drift(drifts, "hard_gate_drift", "critical", "Hard gate status changed", old_status, new_status, "Review hard gates before trusting this result.")


def _compare_phase1(old: Mapping[str, object], new: Mapping[str, object], drifts: list[dict[str, object]]) -> None:
    old_adv = old.get("advancedAnalysis") if isinstance(old.get("advancedAnalysis"), Mapping) else {}
    new_adv = new.get("advancedAnalysis") if isinstance(new.get("advancedAnalysis"), Mapping) else {}
    if _roles(old_adv) != _roles(new_adv):
        _drift(drifts, "phase1_role_drift", "major", "Planet role tags changed", _roles(old_adv), _roles(new_adv), "Review role resolver and rulership inputs.")
    if _purity(old_adv) != _purity(new_adv):
        _drift(drifts, "phase1_purity_drift", "major", "Significator purity changed", _purity(old_adv), _purity(new_adv), "Review purity scoring changes.")
    if _contradictions(old_adv) != _contradictions(new_adv):
        _drift(drifts, "phase1_contradiction_drift", "major", "Contradictions changed", _contradictions(old_adv), _contradictions(new_adv), "Review contradiction detector output.")
    if _control(old_adv).get("band") != _control(new_adv).get("band"):
        _drift(drifts, "phase1_control_index_drift", "major", "Control index band changed", _control(old_adv), _control(new_adv), "Review control index shift.")
    if _resistance(old_adv).get("advantage") != _resistance(new_adv).get("advantage"):
        _drift(drifts, "phase1_resistance_drift", "major", "Resistance advantage changed", _resistance(old_adv), _resistance(new_adv), "Review side comparison.")


def _compare_phase2(old: Mapping[str, object], new: Mapping[str, object], drifts: list[dict[str, object]]) -> None:
    old_tac = old.get("tacticalAnalysis") if isinstance(old.get("tacticalAnalysis"), Mapping) else {}
    new_tac = new.get("tacticalAnalysis") if isinstance(new.get("tacticalAnalysis"), Mapping) else {}
    if _final_command(old_tac).get("command") != _final_command(new_tac).get("command"):
        _drift(drifts, "phase2_command_drift", "major", "Final Command changed", _final_command(old_tac), _final_command(new_tac), "Review final command logic.")
    if _trap_signature(old_tac) != _trap_signature(new_tac):
        _drift(drifts, "phase2_timing_trap_drift", "major", "Timing traps changed", _trap_signature(old_tac), _trap_signature(new_tac), "Review timing trap changes.")
    if _action(old_tac).get("elected_moment") != _action(new_tac).get("elected_moment"):
        _drift(drifts, "phase2_action_moment_drift", "major", "Action moment changed", _action(old_tac), _action(new_tac), "Review objective action mapping.")
    if _practicality(old_tac).get("band") != _practicality(new_tac).get("band"):
        _drift(drifts, "phase2_practicality_drift", "major", "Practicality band changed", _practicality(old_tac), _practicality(new_tac), "Review practicality scoring.")
    _compare_fast_lane(old_tac, new_tac, drifts)
    if _calendar_tags(old_tac) != _calendar_tags(new_tac):
        _drift(drifts, "phase2_calendar_tag_drift", "warning", "Strategic calendar tags changed", _calendar_tags(old_tac), _calendar_tags(new_tac), "Review calendar tag changes.")


def _compare_fast_lane(old_tac: Mapping[str, object], new_tac: Mapping[str, object], drifts: list[dict[str, object]]) -> None:
    old_fast = _fast(old_tac)
    new_fast = _fast(new_tac)
    old_command = old_fast.get("command")
    new_command = new_fast.get("command")
    if old_command != new_command:
        severity = "critical" if {old_command, new_command}.intersection({"REJECT"}) else "major"
        _drift(drifts, "phase2_fast_lane_drift", severity, "Fast Lane command changed", old_fast, new_fast, "Review hard gates, timing traps, and final command logic.")
    old_best = old_fast.get("best") or old_fast.get("best_minute")
    new_best = new_fast.get("best") or new_fast.get("best_minute")
    if _minute_delta(old_best, new_best) > 10:
        _drift(drifts, "phase2_fast_lane_drift", "major", "Fast Lane best minute drifted", old_best, new_best, "Review timing source changes.")
    if old_fast.get("cutoff") != new_fast.get("cutoff"):
        _drift(drifts, "phase2_fast_lane_drift", "warning", "Fast Lane cutoff changed", old_fast.get("cutoff"), new_fast.get("cutoff"), "Review cutoff and trap timing.")
    old_action = old_fast.get("action") or old_fast.get("action_moment")
    new_action = new_fast.get("action") or new_fast.get("action_moment")
    if old_action != new_action:
        _drift(drifts, "phase2_fast_lane_drift", "major", "Fast Lane action moment changed", old_action, new_action, "Review action moment resolver.")


def _drift(drifts: list[dict[str, object]], category: str, severity: str, title: str, old: object, new: object, recommendation: str) -> None:
    drifts.append({
        "category": category,
        "severity": severity,
        "title": title,
        "description": f"Old: {old}; New: {new}",
        "old": old,
        "new": new,
        "recommendation": recommendation,
    })


def _hard_gate_status(snapshot: Mapping[str, object]) -> str:
    if snapshot.get("hardReject"):
        return "failed"
    failure = snapshot.get("failureAnalysis")
    hard = failure.get("hardFailures") if isinstance(failure, Mapping) else None
    return "failed" if isinstance(hard, list) and hard else "passed"


def _roles(advanced: object) -> dict[str, tuple[str, ...]]:
    roles = advanced.get("planet_roles", []) if isinstance(advanced, Mapping) else []
    return {str(item.get("planet")): tuple(item.get("roles", [])) for item in roles if isinstance(item, Mapping)}


def _purity(advanced: object) -> dict[str, tuple[object, object]]:
    rows = advanced.get("significator_purity", []) if isinstance(advanced, Mapping) else []
    return {str(item.get("planet")): (item.get("purity_score"), item.get("purity_band")) for item in rows if isinstance(item, Mapping)}


def _contradictions(advanced: object) -> tuple[tuple[object, object], ...]:
    rows = advanced.get("contradictions", []) if isinstance(advanced, Mapping) else []
    return tuple((item.get("id"), item.get("severity")) for item in rows if isinstance(item, Mapping))


def _control(advanced: object) -> Mapping[str, object]:
    return advanced.get("control_index", {}) if isinstance(advanced, Mapping) and isinstance(advanced.get("control_index"), Mapping) else {}


def _resistance(advanced: object) -> Mapping[str, object]:
    return advanced.get("resistance_analysis", {}) if isinstance(advanced, Mapping) and isinstance(advanced.get("resistance_analysis"), Mapping) else {}


def _final_command(tactical: object) -> Mapping[str, object]:
    return tactical.get("final_command", {}) if isinstance(tactical, Mapping) and isinstance(tactical.get("final_command"), Mapping) else {}


def _fast(tactical: object) -> Mapping[str, object]:
    return tactical.get("fast_lane", {}) if isinstance(tactical, Mapping) and isinstance(tactical.get("fast_lane"), Mapping) else {}


def _action(tactical: object) -> Mapping[str, object]:
    return tactical.get("action_moment", {}) if isinstance(tactical, Mapping) and isinstance(tactical.get("action_moment"), Mapping) else {}


def _practicality(tactical: object) -> Mapping[str, object]:
    return tactical.get("practicality", {}) if isinstance(tactical, Mapping) and isinstance(tactical.get("practicality"), Mapping) else {}


def _trap_signature(tactical: object) -> tuple[tuple[object, object], ...]:
    report = tactical.get("timing_traps", {}) if isinstance(tactical, Mapping) else {}
    rows = report.get("traps", []) if isinstance(report, Mapping) else []
    return tuple((item.get("trap_type"), item.get("severity")) for item in rows if isinstance(item, Mapping))


def _calendar_tags(tactical: object) -> tuple[str, ...]:
    calendar = tactical.get("strategic_calendar_context", {}) if isinstance(tactical, Mapping) else {}
    entries = calendar.get("entries", []) if isinstance(calendar, Mapping) else []
    tags: list[str] = []
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, Mapping):
            tags.extend(str(tag) for tag in entry.get("tags", []))
    return tuple(sorted(set(tags)))


def _minute_delta(first: object, second: object) -> float:
    a = _parse_time(first)
    b = _parse_time(second)
    if a is None or b is None:
        return 0.0
    return abs((a - b).total_seconds() / 60)


def _parse_time(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        for fmt in ("%I:%M %p", "%H:%M", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                pass
    return None


def _number(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _confidence(snapshot: Mapping[str, object]) -> float | None:
    top_level = _number(snapshot.get("confidence"))
    if top_level is not None:
        return top_level
    tactical = snapshot.get("tacticalAnalysis")
    if isinstance(tactical, Mapping):
        value = tactical.get("confidence")
        number = _number(value)
        if number is not None:
            return number
    advanced = snapshot.get("advancedAnalysis")
    if isinstance(advanced, Mapping):
        number = _number(advanced.get("confidence"))
        if number is not None:
            return number
    return None


def _grade_rank(value: object) -> int | None:
    ranks = {
        "A+": 12,
        "A": 11,
        "A-": 10,
        "B+": 9,
        "B": 8,
        "B-": 7,
        "C+": 6,
        "C": 5,
        "C-": 4,
        "D": 3,
        "F": 2,
        "REJECT": 1,
    }
    return ranks.get(str(value).upper()) if value is not None else None
