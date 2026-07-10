from __future__ import annotations

import math
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from . import rule_effectiveness_analysis as analysis_backend
from .objective_packs import classify_objective_pack_capability, get_objective_pack_evaluation_fingerprint
from .source_documents import SOURCE_DOCUMENT_ROOT

CONFIG_DIR = "objective_outcome_scoring_configs"
CONFIG_INDEX = "objective_outcome_scoring_config_index.json"
CONFIG_SCHEMA = "objective_outcome_scoring_config_v1"
RESULT_SCHEMA = "objective_outcome_scoring_result_v1"
EVALUATOR_SCHEMA = "objective_outcome_scoring_evaluator_v1"
SUPPORTED_SCORE_DIRECTIONS = {"higher_is_better", "lower_is_better", "neutral_unspecified"}
SUPPORTED_COMPONENT_BEHAVIORS = {"error", "ignore", "zero"}
SUPPORTED_UNMAPPED_BEHAVIORS = {"ignore", "error"}
SUPPORTED_OUTCOME_STATUSES = {
    "satisfied",
    "not_satisfied",
    "unsupported_missing_field",
    "unsupported_invalid_type",
    "unsupported_operator",
    "invalid_objective",
    "evaluator_error",
}


def validate_objective_outcome_scoring_config(
    scoring_config: dict,
    objective_pack: dict | None = None,
) -> dict:
    blockers: list[str] = []
    warnings: list[str] = []
    if not isinstance(scoring_config, Mapping):
        return {"valid": False, "status": "invalid_config", "blockers": ["scoring_config_invalid"], "warnings": []}
    if str(scoring_config.get("schema_version") or "") != CONFIG_SCHEMA:
        blockers.append("scoring_config_schema_unsupported")
    scoring_config_id = _non_empty_text(scoring_config.get("scoring_config_id"))
    if scoring_config_id is None:
        blockers.append("scoring_config_id_required")
    objective_pack_id = _non_empty_text(scoring_config.get("objective_pack_id"))
    if objective_pack_id is None:
        blockers.append("objective_pack_id_required")
    pack_fp = _non_empty_text(scoring_config.get("objective_pack_evaluation_fingerprint"))
    if pack_fp is None:
        blockers.append("objective_pack_evaluation_fingerprint_required")
    if str(scoring_config.get("score_direction") or "") not in SUPPORTED_SCORE_DIRECTIONS:
        blockers.append("score_direction_unsupported")
    if str(scoring_config.get("unmapped_objective_behavior") or "") not in SUPPORTED_UNMAPPED_BEHAVIORS:
        blockers.append("unmapped_objective_behavior_unsupported")
    minimum = scoring_config.get("minimum_score")
    maximum = scoring_config.get("maximum_score")
    if minimum is not None and not _is_finite_number(minimum):
        blockers.append("minimum_score_invalid")
    if maximum is not None and not _is_finite_number(maximum):
        blockers.append("maximum_score_invalid")
    if _is_finite_number(minimum) and _is_finite_number(maximum) and float(minimum) > float(maximum):
        blockers.append("score_bounds_invalid")
    entries = scoring_config.get("entries")
    if not isinstance(entries, list) or not entries:
        blockers.append("scoring_entries_required")
        entries = []
    seen_ids: set[str] = set()
    pack_objective_ids: set[str] = set()
    if objective_pack is not None:
        capability = classify_objective_pack_capability(objective_pack)
        if capability.get("capability") != "evaluable":
            blockers.append("objective_pack_not_evaluable")
        else:
            actual_pack_id = _non_empty_text(objective_pack.get("objective_type"))
            actual_pack_fp = get_objective_pack_evaluation_fingerprint(objective_pack)
            if objective_pack_id is not None and actual_pack_id != objective_pack_id:
                blockers.append("objective_pack_id_mismatch")
            if pack_fp is not None and actual_pack_fp != pack_fp:
                blockers.append("objective_pack_fingerprint_mismatch")
            pack_objective_ids = {
                str(item.get("objective_id") or "")
                for item in list(objective_pack.get("objectives", []) or [])
                if isinstance(item, Mapping) and str(item.get("objective_id") or "")
            }
    for index, entry in enumerate(entries):
        prefix = f"Entry {index + 1}"
        if not isinstance(entry, Mapping):
            blockers.append(f"{prefix} invalid")
            continue
        objective_id = _non_empty_text(entry.get("objective_id"))
        if objective_id is None:
            blockers.append(f"{prefix} objective_id_required")
        elif objective_id in seen_ids:
            blockers.append(f"duplicate_objective_id:{objective_id}")
        else:
            seen_ids.add(objective_id)
            if pack_objective_ids and objective_id not in pack_objective_ids:
                blockers.append(f"unknown_objective_id:{objective_id}")
        if not _is_finite_number(entry.get("score_when_satisfied")):
            blockers.append(f"{prefix} score_when_satisfied_invalid")
        if not _is_finite_number(entry.get("score_when_unsatisfied")):
            blockers.append(f"{prefix} score_when_unsatisfied_invalid")
        if str(entry.get("missing_behavior") or "") not in SUPPORTED_COMPONENT_BEHAVIORS:
            blockers.append(f"{prefix} missing_behavior_unsupported")
        if str(entry.get("unsupported_behavior") or "") not in SUPPORTED_COMPONENT_BEHAVIORS:
            blockers.append(f"{prefix} unsupported_behavior_unsupported")
    return {
        "valid": not blockers,
        "status": "valid" if not blockers else "invalid_config",
        "blockers": blockers,
        "warnings": warnings,
    }


def save_objective_outcome_scoring_config(
    scoring_config: dict,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    if confirmation != "SAVE_SCORING_CONFIG":
        return {"status": "blocked", "blockers": ["save_scoring_config_confirmation_required"], "warnings": []}
    base = _ensure_dirs(root)
    validation = validate_objective_outcome_scoring_config(scoring_config)
    if not validation["valid"]:
        return {"status": "blocked", "blockers": list(validation.get("blockers", [])), "warnings": list(validation.get("warnings", []))}
    config_id = str(scoring_config.get("scoring_config_id") or "")
    fingerprint = get_objective_outcome_scoring_config_fingerprint(scoring_config)
    existing = analysis_backend._read_json(_config_path(base, config_id))
    if isinstance(existing, Mapping):
        existing_fp = str(existing.get("scoring_config_fingerprint") or get_objective_outcome_scoring_config_fingerprint(dict(existing)))
        if existing_fp == fingerprint:
            return {"status": "already_saved", "scoring_config_id": config_id, "scoring_config_fingerprint": fingerprint, "writes_performed": 0}
        return {"status": "blocked", "blockers": ["scoring_config_id_conflict"], "warnings": []}
    payload = dict(scoring_config)
    payload["scoring_config_fingerprint"] = fingerprint
    before_record = analysis_backend._read_json(_config_path(base, config_id))
    before_index = analysis_backend._read_json(base / "indexes" / CONFIG_INDEX)
    try:
        analysis_backend._atomic_write_json(_config_path(base, config_id), payload)
        _update_index(base)
    except Exception:
        analysis_backend._restore_json(_config_path(base, config_id), before_record)
        analysis_backend._restore_json(base / "indexes" / CONFIG_INDEX, before_index)
        return {"status": "corrupt", "blockers": ["scoring_config_write_failure"], "warnings": []}
    written = analysis_backend._read_json(_config_path(base, config_id))
    if not isinstance(written, Mapping) or str(written.get("scoring_config_fingerprint") or "") != fingerprint:
        return {"status": "corrupt", "blockers": ["scoring_config_verification_failed"], "warnings": []}
    return {"status": "saved", "scoring_config_id": config_id, "scoring_config_fingerprint": fingerprint, "writes_performed": 1}


def load_objective_outcome_scoring_config(
    scoring_config_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    payload = analysis_backend._read_json(_config_path(base, scoring_config_id))
    if not isinstance(payload, Mapping):
        return {"status": "not_found", "scoring_config_id": scoring_config_id, "scoring_config": None, "warnings": []}
    return {"status": "loaded", "scoring_config_id": scoring_config_id, "scoring_config": dict(payload), "warnings": []}


def get_objective_outcome_scoring_config_fingerprint(scoring_config: dict) -> str:
    entries = []
    for entry in list(scoring_config.get("entries", []) or []):
        if not isinstance(entry, Mapping):
            continue
        entries.append(
            {
                "objective_id": entry.get("objective_id"),
                "score_when_satisfied": entry.get("score_when_satisfied"),
                "score_when_unsatisfied": entry.get("score_when_unsatisfied"),
                "missing_behavior": entry.get("missing_behavior"),
                "unsupported_behavior": entry.get("unsupported_behavior"),
            }
        )
    payload = {
        "schema_version": CONFIG_SCHEMA,
        "scoring_config_id": scoring_config.get("scoring_config_id"),
        "objective_pack_id": scoring_config.get("objective_pack_id"),
        "objective_pack_evaluation_fingerprint": scoring_config.get("objective_pack_evaluation_fingerprint"),
        "score_direction": scoring_config.get("score_direction"),
        "unmapped_objective_behavior": scoring_config.get("unmapped_objective_behavior"),
        "minimum_score": scoring_config.get("minimum_score"),
        "maximum_score": scoring_config.get("maximum_score"),
        "entries": entries,
    }
    return analysis_backend._hash_payload(payload)


def evaluate_objective_outcomes(
    scoring_config: dict,
    objective_outcomes: dict,
) -> dict:
    config_copy = deepcopy(scoring_config)
    outcomes_copy = deepcopy(objective_outcomes)
    validation = validate_objective_outcome_scoring_config(config_copy)
    if not validation["valid"]:
        return _blocked_result(config_copy, outcomes_copy, list(validation.get("blockers", [])))
    outcome_validation = _validate_objective_outcomes_input(config_copy, outcomes_copy)
    if outcome_validation["status"] != "valid":
        return _blocked_result(config_copy, outcomes_copy, list(outcome_validation.get("blockers", [])))
    try:
        by_id = {
            str(item.get("objective_id") or ""): dict(item)
            for item in list(outcomes_copy.get("objective_results", []) or [])
            if isinstance(item, Mapping) and str(item.get("objective_id") or "")
        }
        component_results: list[dict[str, Any]] = []
        scored = ignored = blocked = 0
        raw_score = 0.0
        for entry in list(config_copy.get("entries", []) or []):
            component = _score_component(dict(entry), by_id.get(str(entry.get("objective_id") or "")))
            component_results.append(component)
            status = str(component.get("component_status") or "")
            contribution = component.get("contribution")
            if status in {"scored_satisfied", "scored_unsatisfied", "scored_zero"}:
                scored += 1
                raw_score += float(contribution or 0.0)
            elif status in {"ignored_missing", "ignored_unsupported"}:
                ignored += 1
            else:
                blocked += 1
        if str(config_copy.get("unmapped_objective_behavior") or "") == "error":
            configured_ids = {str(entry.get("objective_id") or "") for entry in list(config_copy.get("entries", []) or []) if isinstance(entry, Mapping)}
            for objective_id in by_id:
                if objective_id not in configured_ids:
                    component_results.append(
                        {
                            "objective_id": objective_id,
                            "source_outcome_status": by_id[objective_id].get("status"),
                            "component_status": "blocked_missing",
                            "contribution": None,
                            "configured_satisfied_contribution": None,
                            "configured_unsatisfied_contribution": None,
                            "missing_behavior": None,
                            "unsupported_behavior": None,
                            "error_code": "unmapped_objective",
                        }
                    )
                    blocked += 1
        bounded_score = _apply_bounds(raw_score, config_copy.get("minimum_score"), config_copy.get("maximum_score"))
        aggregate_status = (
            "blocked" if blocked else
            "no_scored_components" if scored == 0 else
            "completed_with_ignored_components" if ignored else
            "completed"
        )
        result = {
            "schema_version": RESULT_SCHEMA,
            "scoring_config_id": config_copy.get("scoring_config_id"),
            "scoring_config_fingerprint": get_objective_outcome_scoring_config_fingerprint(config_copy),
            "objective_pack_id": outcomes_copy.get("objective_pack_id"),
            "objective_pack_evaluation_fingerprint": outcomes_copy.get("objective_pack_evaluation_fingerprint"),
            "record_id": outcomes_copy.get("record_id"),
            "component_results": component_results,
            "raw_score": round(raw_score, 6),
            "bounded_score": round(bounded_score, 6) if bounded_score is not None else None,
            "scored_components": scored,
            "ignored_components": ignored,
            "blocked_components": blocked,
            "aggregate_status": aggregate_status,
            "evaluator_fingerprint": get_objective_outcome_scoring_evaluator_fingerprint(),
            "result_fingerprint": None,
            "warnings": [],
            "blockers": [],
        }
        result["result_fingerprint"] = analysis_backend._hash_payload(
            {
                "scoring_config_fingerprint": result["scoring_config_fingerprint"],
                "objective_pack_id": result["objective_pack_id"],
                "objective_pack_evaluation_fingerprint": result["objective_pack_evaluation_fingerprint"],
                "record_id": result["record_id"],
                "component_results": result["component_results"],
                "raw_score": result["raw_score"],
                "bounded_score": result["bounded_score"],
                "scored_components": scored,
                "ignored_components": ignored,
                "blocked_components": blocked,
                "aggregate_status": aggregate_status,
                "evaluator_fingerprint": result["evaluator_fingerprint"],
            }
        )
        if scoring_config != config_copy or objective_outcomes != outcomes_copy:
            raise AssertionError("Objective outcome scoring mutated input state.")
        return result
    except Exception:
        return {
            "schema_version": RESULT_SCHEMA,
            "scoring_config_id": config_copy.get("scoring_config_id"),
            "scoring_config_fingerprint": get_objective_outcome_scoring_config_fingerprint(config_copy),
            "objective_pack_id": outcomes_copy.get("objective_pack_id"),
            "objective_pack_evaluation_fingerprint": outcomes_copy.get("objective_pack_evaluation_fingerprint"),
            "record_id": outcomes_copy.get("record_id"),
            "component_results": [],
            "raw_score": None,
            "bounded_score": None,
            "scored_components": 0,
            "ignored_components": 0,
            "blocked_components": 0,
            "aggregate_status": "scoring_failed",
            "evaluator_fingerprint": get_objective_outcome_scoring_evaluator_fingerprint(),
            "result_fingerprint": None,
            "warnings": [],
            "blockers": ["scoring_evaluator_failed"],
        }


def get_objective_outcome_scoring_evaluator_fingerprint() -> str:
    payload = {
        "schema_version": EVALUATOR_SCHEMA,
        "result_schema_version": RESULT_SCHEMA,
        "supported_outcome_statuses": sorted(SUPPORTED_OUTCOME_STATUSES),
        "supported_component_behaviors": sorted(SUPPORTED_COMPONENT_BEHAVIORS),
        "supported_unmapped_behaviors": sorted(SUPPORTED_UNMAPPED_BEHAVIORS),
        "score_bound_behavior": "clamp_optional_bounds_v1",
        "component_evaluation_behavior_version": "objective_outcome_scoring_component_v1",
    }
    return analysis_backend._hash_payload(payload)


def _ensure_dirs(root: Path | str) -> Path:
    base = analysis_backend._ensure_analysis_dirs(root)
    (base / CONFIG_DIR).mkdir(parents=True, exist_ok=True)
    index_path = base / "indexes" / CONFIG_INDEX
    if not index_path.exists():
        analysis_backend._atomic_write_json(index_path, {"schema_version": "objective_outcome_scoring_config_index_v1", "items": [], "updated_at_utc": analysis_backend._now()})
    return base


def _config_path(base: Path, scoring_config_id: str) -> Path:
    return base / CONFIG_DIR / f"{analysis_backend._safe_id(scoring_config_id)}.json"


def _update_index(base: Path) -> None:
    items = []
    for path in sorted((base / CONFIG_DIR).glob("*.json")):
        payload = analysis_backend._read_json(path)
        if isinstance(payload, Mapping) and payload.get("scoring_config_id"):
            items.append(
                {
                    "scoring_config_id": payload.get("scoring_config_id"),
                    "objective_pack_id": payload.get("objective_pack_id"),
                    "objective_pack_evaluation_fingerprint": payload.get("objective_pack_evaluation_fingerprint"),
                    "scoring_config_fingerprint": payload.get("scoring_config_fingerprint"),
                }
            )
    analysis_backend._atomic_write_json(base / "indexes" / CONFIG_INDEX, {"schema_version": "objective_outcome_scoring_config_index_v1", "items": items, "updated_at_utc": analysis_backend._now()})


def _validate_objective_outcomes_input(scoring_config: Mapping[str, Any], objective_outcomes: Mapping[str, Any]) -> dict:
    blockers: list[str] = []
    if not isinstance(objective_outcomes, Mapping):
        return {"status": "invalid", "blockers": ["objective_outcomes_invalid"]}
    if _non_empty_text(objective_outcomes.get("objective_pack_id")) != _non_empty_text(scoring_config.get("objective_pack_id")):
        blockers.append("objective_pack_id_mismatch")
    if _non_empty_text(objective_outcomes.get("objective_pack_evaluation_fingerprint")) != _non_empty_text(scoring_config.get("objective_pack_evaluation_fingerprint")):
        blockers.append("objective_pack_fingerprint_mismatch")
    if _non_empty_text(objective_outcomes.get("record_id")) is None:
        blockers.append("record_id_required")
    results = objective_outcomes.get("objective_results")
    if not isinstance(results, list):
        blockers.append("objective_results_required")
        results = []
    seen_ids: set[str] = set()
    for item in results:
        if not isinstance(item, Mapping):
            blockers.append("objective_result_invalid")
            continue
        objective_id = _non_empty_text(item.get("objective_id"))
        if objective_id is None:
            blockers.append("objective_result_id_required")
            continue
        if objective_id in seen_ids:
            blockers.append(f"duplicate_objective_result_id:{objective_id}")
        seen_ids.add(objective_id)
        if str(item.get("status") or "") not in SUPPORTED_OUTCOME_STATUSES:
            blockers.append(f"objective_result_status_unsupported:{objective_id}")
    return {"status": "valid" if not blockers else "invalid", "blockers": blockers}


def _score_component(entry: dict[str, Any], outcome: dict[str, Any] | None) -> dict[str, Any]:
    objective_id = str(entry.get("objective_id") or "")
    if outcome is None:
        behavior = str(entry.get("missing_behavior") or "")
        return _component_for_behavior(entry, objective_id, None, behavior, missing=True)
    outcome_status = str(outcome.get("status") or "")
    if outcome_status == "satisfied":
        contribution = float(entry.get("score_when_satisfied") or 0.0)
        return _component_result(entry, outcome_status, "scored_satisfied", contribution, None)
    if outcome_status == "not_satisfied":
        contribution = float(entry.get("score_when_unsatisfied") or 0.0)
        return _component_result(entry, outcome_status, "scored_unsatisfied", contribution, None)
    behavior = str(entry.get("unsupported_behavior") or "")
    return _component_for_behavior(entry, objective_id, outcome_status, behavior, missing=False)


def _component_for_behavior(entry: dict[str, Any], objective_id: str, outcome_status: str | None, behavior: str, *, missing: bool) -> dict[str, Any]:
    if behavior == "ignore":
        return _component_result(entry, outcome_status, "ignored_missing" if missing else "ignored_unsupported", None, None)
    if behavior == "zero":
        return _component_result(entry, outcome_status, "scored_zero", 0.0, None)
    return _component_result(entry, outcome_status, "blocked_missing" if missing else "blocked_unsupported", None, "missing_objective" if missing else "unsupported_objective")


def _component_result(entry: Mapping[str, Any], outcome_status: str | None, component_status: str, contribution: float | None, error_code: str | None) -> dict[str, Any]:
    return {
        "objective_id": entry.get("objective_id"),
        "source_outcome_status": outcome_status,
        "component_status": component_status,
        "contribution": round(float(contribution), 6) if contribution is not None else None,
        "configured_satisfied_contribution": entry.get("score_when_satisfied"),
        "configured_unsatisfied_contribution": entry.get("score_when_unsatisfied"),
        "missing_behavior": entry.get("missing_behavior"),
        "unsupported_behavior": entry.get("unsupported_behavior"),
        "error_code": error_code,
    }


def _apply_bounds(raw_score: float, minimum: Any, maximum: Any) -> float:
    score = float(raw_score)
    if _is_finite_number(minimum):
        score = max(score, float(minimum))
    if _is_finite_number(maximum):
        score = min(score, float(maximum))
    return score


def _blocked_result(scoring_config: Mapping[str, Any], objective_outcomes: Mapping[str, Any], blockers: list[str]) -> dict:
    return {
        "schema_version": RESULT_SCHEMA,
        "scoring_config_id": scoring_config.get("scoring_config_id"),
        "scoring_config_fingerprint": get_objective_outcome_scoring_config_fingerprint(dict(scoring_config)) if isinstance(scoring_config, Mapping) else None,
        "objective_pack_id": objective_outcomes.get("objective_pack_id") if isinstance(objective_outcomes, Mapping) else None,
        "objective_pack_evaluation_fingerprint": objective_outcomes.get("objective_pack_evaluation_fingerprint") if isinstance(objective_outcomes, Mapping) else None,
        "record_id": objective_outcomes.get("record_id") if isinstance(objective_outcomes, Mapping) else None,
        "component_results": [],
        "raw_score": None,
        "bounded_score": None,
        "scored_components": 0,
        "ignored_components": 0,
        "blocked_components": 0,
        "aggregate_status": "blocked",
        "evaluator_fingerprint": get_objective_outcome_scoring_evaluator_fingerprint(),
        "result_fingerprint": None,
        "warnings": [],
        "blockers": blockers,
    }


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _non_empty_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None
