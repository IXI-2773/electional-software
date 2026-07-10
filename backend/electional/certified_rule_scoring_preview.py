"""Single-rule read-only scoring impact preview over persisted objective outcomes."""

from __future__ import annotations

import json
import statistics
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from . import certified_rule_objective_preview as objective_preview_backend
from . import objective_outcome_scoring as scoring_backend
from . import rule_effectiveness_analysis as analysis_backend
from .canonical_rule_runtime import load_canonical_rule
from .document_manifest import load_document_manifest
from .objective_packs import load_objective_pack
from .rule_effectiveness_analysis import _load_certification_receipt_for_rule
from .source_documents import SOURCE_DOCUMENT_ROOT

PLAN_DIR = "certified_rule_scoring_preview_plans"
RESULT_DIR = "certified_rule_scoring_preview_results"
RECEIPT_DIR = "certified_rule_scoring_preview_receipts"
PLAN_INDEX = "certified_rule_scoring_preview_plan_index.json"
RESULT_INDEX = "certified_rule_scoring_preview_result_index.json"
RECEIPT_INDEX = "certified_rule_scoring_preview_receipt_index.json"
PLAN_SCHEMA = "certified_rule_scoring_preview_plan_v1"
RESULT_SCHEMA = "certified_rule_scoring_preview_result_v1"
RECEIPT_SCHEMA = "certified_rule_scoring_preview_receipt_v1"
PREVIEW_SCHEMA_VERSION = "certified_rule_scoring_preview_v1"
COMPATIBILITY_CAPABILITY = "baseline_and_rule_enabled_v1"
ALLOWED_PREVIEW_STATUSES = {"completed", "completed_with_unsupported_records"}


def build_certified_rule_scoring_preview_workspace(
    objective_preview_result_id: str,
    scoring_config_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    preview_loaded = objective_preview_backend.load_certified_rule_objective_preview_result(objective_preview_result_id, root=base)
    preview_result = preview_loaded.get("objective_preview_result")
    preview_receipt = (
        objective_preview_backend._find_receipt_for_result(base, objective_preview_result_id)
        if isinstance(preview_result, Mapping)
        else None
    )
    config_loaded = (
        scoring_backend.load_objective_outcome_scoring_config(scoring_config_id, root=base)
        if scoring_config_id
        else {"status": "not_selected", "scoring_config": None}
    )
    config = config_loaded.get("scoring_config")
    eligibility = (
        validate_certified_rule_scoring_preview_eligibility(objective_preview_result_id, scoring_config_id, root=base)
        if scoring_config_id
        else {"status": "blocked", "compatibility_status": "blocked", "warnings": [], "blockers": ["scoring_config_required"]}
    )
    plan = _find_plan(base, objective_preview_result_id, scoring_config_id or "")
    result = _find_result(base, str((plan or {}).get("scoring_preview_plan_id") or ""))
    receipt = _find_receipt_for_result(base, str((result or {}).get("scoring_preview_result_id") or ""))
    rule_status = "missing"
    certification_status = "missing"
    if isinstance(preview_result, Mapping):
        rule_loaded = load_canonical_rule(str(preview_result.get("canonical_rule_id") or ""), require_active=False, root=base)
        rule_status = str((rule_loaded.get("rule") or {}).get("status") or rule_loaded.get("status") or "missing")
        certification_status = str((_load_certification_receipt_for_rule(base, str(preview_result.get("canonical_rule_id") or "")) or {}).get("certification_status") or "missing")
    return {
        "status": "ready_for_planning" if not eligibility.get("blockers") else str(eligibility.get("status") or "blocked"),
        "objective_preview_result_id": objective_preview_result_id,
        "objective_preview_receipt_id": (preview_receipt or {}).get("objective_preview_receipt_id"),
        "document_id": (preview_result or {}).get("document_id"),
        "source_revision": (preview_result or {}).get("source_revision"),
        "canonical_rule_id": (preview_result or {}).get("canonical_rule_id"),
        "rule_status": rule_status,
        "certification_status": certification_status,
        "objective_preview_status": (preview_result or {}).get("status", preview_loaded.get("status", "missing")),
        "phase_9o_compatibility": "compatible" if (preview_result or {}).get("phase_9p_compatible") else "legacy_objective_preview",
        "scoring_config_id": scoring_config_id,
        "scoring_config_status": config_loaded.get("status", "not_selected"),
        "scoring_config_fingerprint": (config or {}).get("scoring_config_fingerprint"),
        "compatibility_status": eligibility.get("compatibility_status", "blocked"),
        "scoring_preview_plan_id": (plan or {}).get("scoring_preview_plan_id"),
        "scoring_preview_result_id": (result or {}).get("scoring_preview_result_id"),
        "scoring_preview_receipt_id": (receipt or {}).get("scoring_preview_receipt_id"),
        "warnings": list(eligibility.get("warnings", [])),
        "blockers": list(eligibility.get("blockers", [])),
        "recommended_action": (
            "Build the shadow read-only scoring preview plan."
            if not eligibility.get("blockers")
            else "Resolve Phase 9O compatibility, scoring configuration, or staleness blockers first."
        ),
    }


def validate_certified_rule_scoring_preview_eligibility(
    objective_preview_result_id: str,
    scoring_config_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    blockers: list[str] = []
    warnings: list[str] = []
    compatibility_status = "compatible"
    preview_loaded = objective_preview_backend.load_certified_rule_objective_preview_result(objective_preview_result_id, root=base)
    preview_result = preview_loaded.get("objective_preview_result")
    if not isinstance(preview_result, Mapping):
        return {"status": "blocked", "compatibility_status": "blocked", "warnings": [], "blockers": ["objective_preview_result_missing"]}
    preview_receipt = objective_preview_backend._find_receipt_for_result(base, objective_preview_result_id)
    if not isinstance(preview_receipt, Mapping):
        blockers.append("objective_preview_receipt_missing")
    if str(preview_result.get("schema_version") or "") != objective_preview_backend.RESULT_SCHEMA:
        blockers.append("objective_preview_result_schema_unsupported")
        compatibility_status = "corrupt"
    if str(preview_result.get("objective_outcome_persistence") or "") != COMPATIBILITY_CAPABILITY:
        blockers.append("objective_outcome_persistence_incompatible")
        compatibility_status = "legacy_objective_preview"
    if not bool(preview_result.get("phase_9p_compatible")):
        blockers.extend(list(preview_result.get("compatibility_blockers", []) or ["legacy_objective_preview_result"]))
        compatibility_status = "legacy_objective_preview"
    if str(preview_result.get("status") or "") not in ALLOWED_PREVIEW_STATUSES:
        blockers.append("objective_preview_result_not_completed")
    if bool(preview_result.get("stale")) or objective_preview_backend._result_is_stale(base, preview_result):
        blockers.append("objective_preview_result_stale")
        compatibility_status = "stale"
    if "production_state_mutation_detected" in list(preview_result.get("blockers", []) or []):
        blockers.append("objective_preview_mutation_detected")
    result_rule_id = str(preview_result.get("canonical_rule_id") or "")
    rule_loaded = load_canonical_rule(result_rule_id, require_active=True, root=base)
    rule = rule_loaded.get("rule")
    if rule_loaded.get("status") != "loaded" or not isinstance(rule, Mapping):
        blockers.append("canonical_rule_not_active")
    certification = _load_certification_receipt_for_rule(base, result_rule_id)
    if not isinstance(certification, Mapping) or str(certification.get("certification_status") or "") != "completed":
        blockers.append("rule_certification_missing_or_stale")
    elif isinstance(rule, Mapping) and str(certification.get("rule_hash") or "") != objective_preview_backend._hash_payload(rule):
        blockers.append("rule_certification_hash_mismatch")
    manifest = load_document_manifest(str(preview_result.get("document_id") or ""), root=base).get("manifest")
    if not isinstance(manifest, Mapping):
        blockers.append("document_manifest_missing")
    elif str(manifest.get("source_revision") or "") != str(preview_result.get("source_revision") or ""):
        blockers.append("source_revision_not_current")
    if isinstance(preview_receipt, Mapping):
        if str(preview_receipt.get("objective_preview_result_id") or "") != objective_preview_result_id:
            blockers.append("objective_preview_receipt_result_mismatch")
        if str(preview_receipt.get("result_fingerprint") or "") != str(preview_result.get("result_fingerprint") or ""):
            blockers.append("objective_preview_receipt_fingerprint_mismatch")
    config_loaded = scoring_backend.load_objective_outcome_scoring_config(scoring_config_id, root=base)
    config = config_loaded.get("scoring_config")
    if not isinstance(config, Mapping):
        blockers.append("scoring_config_missing")
        return {
            "status": "blocked",
            "compatibility_status": compatibility_status if blockers else "blocked",
            "warnings": [],
            "blockers": analysis_backend._dedupe(blockers) if hasattr(analysis_backend, "_dedupe") else list(dict.fromkeys(blockers)),
        }
    objective_pack = load_objective_pack(str(preview_result.get("objective_pack_id") or ""), root=base / "objective_packs")
    config_validation = scoring_backend.validate_objective_outcome_scoring_config(dict(config), objective_pack)
    if not config_validation.get("valid"):
        blockers.extend(list(config_validation.get("blockers", [])))
        compatibility_status = "incompatible_pack" if any("objective_pack_" in item for item in config_validation.get("blockers", [])) else "blocked"
    config_fingerprint = scoring_backend.get_objective_outcome_scoring_config_fingerprint(dict(config))
    if str(config.get("scoring_config_fingerprint") or config_fingerprint) != config_fingerprint:
        blockers.append("scoring_config_fingerprint_mismatch")
    if str(config.get("objective_pack_id") or "") != str(preview_result.get("objective_pack_id") or ""):
        blockers.append("objective_pack_id_mismatch")
        compatibility_status = "incompatible_pack"
    result_pack_fp = str(preview_result.get("objective_pack_fingerprint") or "")
    config_pack_fp = str(config.get("objective_pack_evaluation_fingerprint") or "")
    if config_pack_fp != result_pack_fp:
        blockers.append("objective_pack_fingerprint_mismatch")
        compatibility_status = "incompatible_pack"
    scoreable_records = 0
    ignored_records = 0
    for record in list(preview_result.get("per_record_results", []) or []):
        if not isinstance(record, Mapping):
            blockers.append("per_record_result_invalid")
            compatibility_status = "corrupt"
            continue
        baseline = record.get("baseline_objective_outcomes")
        enabled = record.get("rule_enabled_objective_outcomes")
        if baseline is None or enabled is None:
            continue
        if not isinstance(baseline, Mapping) or not isinstance(enabled, Mapping):
            blockers.append("persisted_objective_outcomes_invalid")
            compatibility_status = "corrupt"
            continue
        if str(record.get("record_id") or "") != str(baseline.get("record_id") or "") or str(record.get("record_id") or "") != str(enabled.get("record_id") or ""):
            blockers.append("record_id_mismatch")
            compatibility_status = "corrupt"
            continue
        baseline_validation = scoring_backend.evaluate_objective_outcomes(dict(config), dict(baseline))
        enabled_validation = scoring_backend.evaluate_objective_outcomes(dict(config), dict(enabled))
        if baseline_validation.get("aggregate_status") == "blocked" or enabled_validation.get("aggregate_status") == "blocked":
            blocked_codes = list(baseline_validation.get("blockers", [])) + list(enabled_validation.get("blockers", []))
            blockers.extend(blocked_codes)
            if any(item.startswith("unknown_objective_id:") or item.startswith("duplicate_objective_result_id:") or item == "unmapped_objective" for item in blocked_codes):
                compatibility_status = "incompatible_objectives"
        if baseline_validation.get("aggregate_status") == "completed_with_ignored_components" or enabled_validation.get("aggregate_status") == "completed_with_ignored_components":
            ignored_records += 1
        scoreable_records += 1
    if scoreable_records == 0:
        warnings.append("no_scoreable_records")
        if not blockers:
            compatibility_status = "compatible"
    elif ignored_records and not blockers and compatibility_status == "compatible":
        compatibility_status = "compatible_with_ignored_objectives"
    final_status = (
        "corrupt" if compatibility_status == "corrupt" else
        "stale" if compatibility_status == "stale" else
        "blocked" if blockers else
        compatibility_status
    )
    return {
        "status": final_status,
        "compatibility_status": compatibility_status if blockers or warnings or scoreable_records >= 0 else "unknown",
        "document_id": preview_result.get("document_id"),
        "source_revision": preview_result.get("source_revision"),
        "canonical_rule_id": preview_result.get("canonical_rule_id"),
        "objective_pack_id": preview_result.get("objective_pack_id"),
        "objective_preview_result_id": objective_preview_result_id,
        "objective_preview_receipt_id": (preview_receipt or {}).get("objective_preview_receipt_id"),
        "scoring_config_id": scoring_config_id,
        "scoreable_records": scoreable_records,
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
    }


def build_certified_rule_scoring_preview_plan(
    objective_preview_result_id: str,
    scoring_config_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    eligibility = validate_certified_rule_scoring_preview_eligibility(objective_preview_result_id, scoring_config_id, root=base)
    if eligibility.get("blockers"):
        return {
            "status": str(eligibility.get("status") or "blocked"),
            "objective_preview_result_id": objective_preview_result_id,
            "scoring_config_id": scoring_config_id,
            "warnings": list(eligibility.get("warnings", [])),
            "blockers": list(eligibility.get("blockers", [])),
        }
    preview_result = objective_preview_backend.load_certified_rule_objective_preview_result(objective_preview_result_id, root=base).get("objective_preview_result") or {}
    preview_receipt = objective_preview_backend._find_receipt_for_result(base, objective_preview_result_id) or {}
    config = scoring_backend.load_objective_outcome_scoring_config(scoring_config_id, root=base).get("scoring_config") or {}
    total_records = len(list(preview_result.get("per_record_results", []) or []))
    scoreable_records = _scoreable_record_count(preview_result)
    plan = {
        "schema_version": PLAN_SCHEMA,
        "preview_schema_version": PREVIEW_SCHEMA_VERSION,
        "scoring_preview_plan_id": _plan_id(preview_result, config),
        "objective_preview_result_id": objective_preview_result_id,
        "objective_preview_receipt_id": preview_receipt.get("objective_preview_receipt_id"),
        "canonical_rule_id": preview_result.get("canonical_rule_id"),
        "document_id": preview_result.get("document_id"),
        "source_revision": preview_result.get("source_revision"),
        "rule_fingerprint": preview_result.get("rule_fingerprint"),
        "certification_fingerprint": preview_result.get("certification_fingerprint"),
        "objective_pack_id": preview_result.get("objective_pack_id"),
        "objective_pack_evaluation_fingerprint": preview_result.get("objective_pack_fingerprint"),
        "controlled_input_id": preview_result.get("controlled_input_id"),
        "controlled_input_fingerprint": preview_result.get("controlled_input_fingerprint"),
        "objective_preview_result_fingerprint": preview_result.get("result_fingerprint"),
        "objective_preview_compatibility_capability": preview_result.get("objective_outcome_persistence"),
        "scoring_config_id": config.get("scoring_config_id"),
        "scoring_config_fingerprint": scoring_backend.get_objective_outcome_scoring_config_fingerprint(dict(config)),
        "scoring_evaluator_fingerprint": scoring_backend.get_objective_outcome_scoring_evaluator_fingerprint(),
        "total_record_count": total_records,
        "scoreable_record_count": scoreable_records,
        "preview_mode": "shadow_read_only",
        "warnings": list(eligibility.get("warnings", [])),
        "blockers": [],
        "plan_fingerprint": _plan_fingerprint(preview_result, preview_receipt, config, total_records, scoreable_records),
    }
    plan_path = _plan_path(base, str(plan["scoring_preview_plan_id"]))
    existing = analysis_backend._read_json(plan_path)
    if isinstance(existing, Mapping):
        if str(existing.get("plan_fingerprint") or "") == str(plan.get("plan_fingerprint") or ""):
            return {"status": "planned", "scoring_preview_plan_id": plan["scoring_preview_plan_id"], "writes_performed": 0, **_plan_summary(plan)}
        return {"status": "corrupt", "blockers": ["scoring_preview_plan_divergence"], "warnings": []}
    before_plan = analysis_backend._read_json(plan_path)
    before_index = analysis_backend._read_json(base / "indexes" / PLAN_INDEX)
    try:
        analysis_backend._atomic_write_json(plan_path, plan)
        _update_plan_index(base)
    except Exception:
        analysis_backend._restore_json(plan_path, before_plan)
        analysis_backend._restore_json(base / "indexes" / PLAN_INDEX, before_index)
        return {"status": "corrupt", "blockers": ["scoring_preview_plan_write_failure"], "warnings": []}
    return {"status": "planned", "scoring_preview_plan_id": plan["scoring_preview_plan_id"], "writes_performed": 1, **_plan_summary(plan)}


def run_certified_rule_scoring_preview(
    scoring_preview_plan_id: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    if confirmation != "RUN_SCORING_PREVIEW":
        return {"status": "blocked", "scoring_preview_plan_id": scoring_preview_plan_id, "blockers": ["run_scoring_preview_confirmation_required"], "warnings": []}
    plan = analysis_backend._read_json(_plan_path(base, scoring_preview_plan_id))
    if not isinstance(plan, Mapping):
        return {"status": "blocked", "scoring_preview_plan_id": scoring_preview_plan_id, "blockers": ["scoring_preview_plan_missing"], "warnings": []}
    current = _plan_current_status(base, plan)
    if current["status"] != "current":
        return {"status": current["status"], "scoring_preview_plan_id": scoring_preview_plan_id, "blockers": list(current.get("blockers", [])), "warnings": []}
    existing = _find_result(base, scoring_preview_plan_id)
    if isinstance(existing, Mapping) and not _result_is_stale(base, existing):
        receipt = _find_receipt_for_result(base, str(existing.get("scoring_preview_result_id") or ""))
        if isinstance(receipt, Mapping) and str(receipt.get("result_fingerprint") or "") == str(existing.get("result_fingerprint") or ""):
            return {
                "status": "already_completed",
                "scoring_preview_plan_id": scoring_preview_plan_id,
                "scoring_preview_result_id": existing.get("scoring_preview_result_id"),
                "scoring_preview_receipt_id": receipt.get("scoring_preview_receipt_id"),
                "writes_performed": 0,
            }
        return {"status": "corrupt", "scoring_preview_plan_id": scoring_preview_plan_id, "blockers": ["scoring_preview_receipt_divergence"], "warnings": []}
    preview_result = objective_preview_backend.load_certified_rule_objective_preview_result(str(plan.get("objective_preview_result_id") or ""), root=base).get("objective_preview_result") or {}
    preview_receipt = objective_preview_backend._find_receipt_for_result(base, str(plan.get("objective_preview_result_id") or "")) or {}
    config = scoring_backend.load_objective_outcome_scoring_config(str(plan.get("scoring_config_id") or ""), root=base).get("scoring_config") or {}
    if str(plan.get("plan_fingerprint") or "") != _plan_fingerprint(preview_result, preview_receipt, config, int(plan.get("total_record_count") or 0), int(plan.get("scoreable_record_count") or 0)):
        return {"status": "stale", "scoring_preview_plan_id": scoring_preview_plan_id, "blockers": ["scoring_preview_plan_fingerprint_mismatch"], "warnings": []}
    before_snapshots = _read_only_snapshots(base, preview_result, config)
    per_record = []
    raw_deltas: list[float] = []
    bounded_deltas: list[float] = []
    baseline_raw_scores: list[float] = []
    enabled_raw_scores: list[float] = []
    baseline_bounded_scores: list[float] = []
    enabled_bounded_scores: list[float] = []
    increased = decreased = unchanged = mixed = unsupported = scoring_errors = compared = changed_components = evaluated_components = 0
    for record in list(preview_result.get("per_record_results", []) or []):
        if not isinstance(record, Mapping):
            continue
        baseline_outcomes = record.get("baseline_objective_outcomes")
        enabled_outcomes = record.get("rule_enabled_objective_outcomes")
        if not isinstance(baseline_outcomes, Mapping) or not isinstance(enabled_outcomes, Mapping):
            unsupported += 1
            per_record.append(
                {
                    "record_id": record.get("record_id"),
                    "baseline_scoring_status": "unsupported",
                    "rule_enabled_scoring_status": "unsupported",
                    "baseline_raw_score": None,
                    "rule_enabled_raw_score": None,
                    "raw_score_delta": None,
                    "baseline_bounded_score": None,
                    "rule_enabled_bounded_score": None,
                    "bounded_score_delta": None,
                    "changed_component_ids": [],
                    "unchanged_component_ids": [],
                    "ignored_component_count": 0,
                    "blocked_component_count": 0,
                    "safe_error_codes": [],
                    "record_classification": "unsupported",
                }
            )
            continue
        baseline_score = scoring_backend.evaluate_objective_outcomes(dict(config), dict(baseline_outcomes))
        enabled_score = scoring_backend.evaluate_objective_outcomes(dict(config), dict(enabled_outcomes))
        if baseline_score.get("aggregate_status") in {"blocked", "scoring_failed"} or enabled_score.get("aggregate_status") in {"blocked", "scoring_failed"}:
            scoring_errors += 1
            per_record.append(
                {
                    "record_id": record.get("record_id"),
                    "baseline_scoring_status": baseline_score.get("aggregate_status"),
                    "rule_enabled_scoring_status": enabled_score.get("aggregate_status"),
                    "baseline_raw_score": baseline_score.get("raw_score"),
                    "rule_enabled_raw_score": enabled_score.get("raw_score"),
                    "raw_score_delta": None,
                    "baseline_bounded_score": baseline_score.get("bounded_score"),
                    "rule_enabled_bounded_score": enabled_score.get("bounded_score"),
                    "bounded_score_delta": None,
                    "changed_component_ids": [],
                    "unchanged_component_ids": [],
                    "ignored_component_count": int(baseline_score.get("ignored_components", 0) or 0) + int(enabled_score.get("ignored_components", 0) or 0),
                    "blocked_component_count": int(baseline_score.get("blocked_components", 0) or 0) + int(enabled_score.get("blocked_components", 0) or 0),
                    "safe_error_codes": _safe_error_codes(baseline_score, enabled_score),
                    "record_classification": "scoring_error",
                }
            )
            continue
        component_compare = _compare_components(baseline_score, enabled_score)
        raw_delta = _delta(baseline_score.get("raw_score"), enabled_score.get("raw_score"))
        bounded_delta = _delta(baseline_score.get("bounded_score"), enabled_score.get("bounded_score"))
        classification = _classify_scored_record(component_compare, raw_delta, bounded_delta)
        if classification == "score_increased":
            increased += 1
        elif classification == "score_decreased":
            decreased += 1
        elif classification == "mixed_component_change":
            mixed += 1
        else:
            unchanged += 1
        compared += 1
        changed_components += len(component_compare["changed_component_ids"])
        evaluated_components += len(component_compare["changed_component_ids"]) + len(component_compare["unchanged_component_ids"])
        baseline_raw_scores.append(float(baseline_score.get("raw_score") or 0.0))
        enabled_raw_scores.append(float(enabled_score.get("raw_score") or 0.0))
        if baseline_score.get("bounded_score") is not None and enabled_score.get("bounded_score") is not None:
            baseline_bounded_scores.append(float(baseline_score.get("bounded_score") or 0.0))
            enabled_bounded_scores.append(float(enabled_score.get("bounded_score") or 0.0))
        raw_deltas.append(float(raw_delta or 0.0))
        if bounded_delta is not None:
            bounded_deltas.append(float(bounded_delta))
        per_record.append(
            {
                "record_id": record.get("record_id"),
                "baseline_scoring_status": baseline_score.get("aggregate_status"),
                "rule_enabled_scoring_status": enabled_score.get("aggregate_status"),
                "baseline_raw_score": baseline_score.get("raw_score"),
                "rule_enabled_raw_score": enabled_score.get("raw_score"),
                "raw_score_delta": raw_delta,
                "baseline_bounded_score": baseline_score.get("bounded_score"),
                "rule_enabled_bounded_score": enabled_score.get("bounded_score"),
                "bounded_score_delta": bounded_delta,
                "changed_component_ids": component_compare["changed_component_ids"],
                "unchanged_component_ids": component_compare["unchanged_component_ids"],
                "ignored_component_count": int(baseline_score.get("ignored_components", 0) or 0) + int(enabled_score.get("ignored_components", 0) or 0),
                "blocked_component_count": int(baseline_score.get("blocked_components", 0) or 0) + int(enabled_score.get("blocked_components", 0) or 0),
                "safe_error_codes": _safe_error_codes(baseline_score, enabled_score),
                "record_classification": classification,
            }
        )
    mutation_detected = _read_only_snapshots(base, preview_result, config) != before_snapshots
    metrics = {
        "total_phase_9o_records": len(list(preview_result.get("per_record_results", []) or [])),
        "scoreable_records": _scoreable_record_count(preview_result),
        "compared_records": compared,
        "increased_score_records": increased,
        "decreased_score_records": decreased,
        "unchanged_score_records": unchanged,
        "mixed_component_records": mixed,
        "unsupported_records": unsupported,
        "scoring_error_records": scoring_errors,
        "scoring_coverage": _ratio(compared, len(list(preview_result.get("per_record_results", []) or []))),
        "scoring_compatibility_rate": _ratio(_scoreable_record_count(preview_result), len(list(preview_result.get("per_record_results", []) or []))),
        "mean_raw_score_delta": _round_or_none(_mean(raw_deltas)),
        "median_raw_score_delta": _round_or_none(_median(raw_deltas)),
        "minimum_raw_score_delta": _round_or_none(min(raw_deltas) if raw_deltas else None),
        "maximum_raw_score_delta": _round_or_none(max(raw_deltas) if raw_deltas else None),
        "mean_bounded_score_delta": _round_or_none(_mean(bounded_deltas)),
        "median_bounded_score_delta": _round_or_none(_median(bounded_deltas)),
        "minimum_bounded_score_delta": _round_or_none(min(bounded_deltas) if bounded_deltas else None),
        "maximum_bounded_score_delta": _round_or_none(max(bounded_deltas) if bounded_deltas else None),
        "positive_delta_rate": _ratio(increased, compared),
        "negative_delta_rate": _ratio(decreased, compared),
        "zero_delta_rate": _ratio(unchanged, compared),
        "baseline_mean_raw_score": _round_or_none(_mean(baseline_raw_scores)),
        "rule_enabled_mean_raw_score": _round_or_none(_mean(enabled_raw_scores)),
        "baseline_mean_bounded_score": _round_or_none(_mean(baseline_bounded_scores)),
        "rule_enabled_mean_bounded_score": _round_or_none(_mean(enabled_bounded_scores)),
        "evaluated_component_count": evaluated_components,
        "changed_component_count": changed_components,
    }
    status = (
        "mutation_detected" if mutation_detected else
        "scoring_evaluator_failed" if scoring_errors else
        "no_scoreable_records" if metrics["scoreable_records"] == 0 else
        "completed_with_unsupported_records" if unsupported else
        "completed"
    )
    result_id = _result_id(scoring_preview_plan_id, plan)
    result = {
        "schema_version": RESULT_SCHEMA,
        "preview_schema_version": PREVIEW_SCHEMA_VERSION,
        "scoring_preview_result_id": result_id,
        "scoring_preview_plan_id": scoring_preview_plan_id,
        "objective_preview_result_id": plan.get("objective_preview_result_id"),
        "objective_preview_receipt_id": plan.get("objective_preview_receipt_id"),
        "objective_preview_compatibility_capability": plan.get("objective_preview_compatibility_capability"),
        "canonical_rule_id": plan.get("canonical_rule_id"),
        "document_id": plan.get("document_id"),
        "source_revision": plan.get("source_revision"),
        "rule_fingerprint": plan.get("rule_fingerprint"),
        "certification_fingerprint": plan.get("certification_fingerprint"),
        "objective_pack_id": plan.get("objective_pack_id"),
        "objective_pack_evaluation_fingerprint": plan.get("objective_pack_evaluation_fingerprint"),
        "controlled_input_id": plan.get("controlled_input_id"),
        "controlled_input_fingerprint": plan.get("controlled_input_fingerprint"),
        "objective_preview_result_fingerprint": plan.get("objective_preview_result_fingerprint"),
        "scoring_config_id": plan.get("scoring_config_id"),
        "scoring_config_fingerprint": plan.get("scoring_config_fingerprint"),
        "scoring_evaluator_fingerprint": plan.get("scoring_evaluator_fingerprint"),
        "preview_mode": "shadow_read_only",
        "per_record_scoring_comparisons": per_record,
        "metrics": metrics,
        "warnings": [],
        "blockers": ["production_state_mutation_detected"] if mutation_detected else [],
        "status": status,
        "result_fingerprint": _result_fingerprint(plan, per_record, metrics, status),
    }
    receipt_id = _receipt_id(result_id)
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "scoring_preview_receipt_id": receipt_id,
        "scoring_preview_result_id": result_id,
        "scoring_preview_plan_id": scoring_preview_plan_id,
        "objective_preview_result_id": plan.get("objective_preview_result_id"),
        "objective_preview_receipt_id": plan.get("objective_preview_receipt_id"),
        "canonical_rule_id": plan.get("canonical_rule_id"),
        "document_id": plan.get("document_id"),
        "source_revision": plan.get("source_revision"),
        "rule_fingerprint": plan.get("rule_fingerprint"),
        "certification_fingerprint": plan.get("certification_fingerprint"),
        "objective_pack_evaluation_fingerprint": plan.get("objective_pack_evaluation_fingerprint"),
        "controlled_input_fingerprint": plan.get("controlled_input_fingerprint"),
        "objective_preview_result_fingerprint": plan.get("objective_preview_result_fingerprint"),
        "scoring_config_id": plan.get("scoring_config_id"),
        "scoring_config_fingerprint": plan.get("scoring_config_fingerprint"),
        "scoring_evaluator_fingerprint": plan.get("scoring_evaluator_fingerprint"),
        "total_record_count": metrics["total_phase_9o_records"],
        "compared_record_count": metrics["compared_records"],
        "unsupported_record_count": metrics["unsupported_records"],
        "error_record_count": metrics["scoring_error_records"],
        "final_status": status,
        "result_fingerprint": result["result_fingerprint"],
        "metric_summary": {
            "scoring_coverage": metrics["scoring_coverage"],
            "scoring_compatibility_rate": metrics["scoring_compatibility_rate"],
            "mean_raw_score_delta": metrics["mean_raw_score_delta"],
            "mean_bounded_score_delta": metrics["mean_bounded_score_delta"],
        },
        "created_at_utc": analysis_backend._now(),
    }
    before_result = analysis_backend._read_json(_result_path(base, result_id))
    before_receipt = analysis_backend._read_json(_receipt_path(base, receipt_id))
    before_result_index = analysis_backend._read_json(base / "indexes" / RESULT_INDEX)
    before_receipt_index = analysis_backend._read_json(base / "indexes" / RECEIPT_INDEX)
    try:
        analysis_backend._atomic_write_json(_result_path(base, result_id), result)
        analysis_backend._atomic_write_json(_receipt_path(base, receipt_id), receipt)
        _update_result_index(base)
        _update_receipt_index(base)
    except Exception:
        analysis_backend._restore_json(_result_path(base, result_id), before_result)
        analysis_backend._restore_json(_receipt_path(base, receipt_id), before_receipt)
        analysis_backend._restore_json(base / "indexes" / RESULT_INDEX, before_result_index)
        analysis_backend._restore_json(base / "indexes" / RECEIPT_INDEX, before_receipt_index)
        return {"status": "corrupt", "scoring_preview_plan_id": scoring_preview_plan_id, "blockers": ["scoring_preview_result_write_failure"], "warnings": []}
    return {
        "status": status,
        "scoring_preview_plan_id": scoring_preview_plan_id,
        "scoring_preview_result_id": result_id,
        "scoring_preview_receipt_id": receipt_id,
        "writes_performed": 2,
        "metrics": metrics,
    }


def load_certified_rule_scoring_preview_result(
    scoring_preview_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    result = analysis_backend._read_json(_result_path(base, scoring_preview_result_id))
    if not isinstance(result, Mapping):
        return {"status": "not_found", "scoring_preview_result_id": scoring_preview_result_id, "scoring_preview_result": None, "warnings": []}
    payload = dict(result)
    payload["stale"] = _result_is_stale(base, payload)
    return {"status": "loaded", "scoring_preview_result_id": scoring_preview_result_id, "scoring_preview_result": payload, "warnings": []}


def get_certified_rule_scoring_preview_health(
    scoring_preview_plan_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    plans = _load_all(base / PLAN_DIR)
    results = _load_all(base / RESULT_DIR)
    receipts = _load_all(base / RECEIPT_DIR)
    if scoring_preview_plan_id:
        plans = [item for item in plans if str(item.get("scoring_preview_plan_id") or "") == scoring_preview_plan_id]
        results = [item for item in results if str(item.get("scoring_preview_plan_id") or "") == scoring_preview_plan_id]
        receipts = [item for item in receipts if str(item.get("scoring_preview_plan_id") or "") == scoring_preview_plan_id]
    if not plans and not results and not receipts:
        return {"status": "empty", "scoring_preview_plan_count": 0, "scoring_preview_result_count": 0, "scoring_preview_receipt_count": 0, "recommended_action": "Build one certified-rule scoring preview plan."}
    warnings: list[str] = []
    stale_count = 0
    for result in results:
        if _result_is_stale(base, result):
            stale_count += 1
        metrics = result.get("metrics") or {}
        total = int(metrics.get("total_phase_9o_records", 0) or 0)
        compared = int(metrics.get("compared_records", 0) or 0)
        if compared > total:
            warnings.append("compared_record_count_invalid")
        for item in list(result.get("per_record_scoring_comparisons", []) or []):
            if item.get("raw_score_delta") is not None:
                expected = _delta(item.get("baseline_raw_score"), item.get("rule_enabled_raw_score"))
                if expected != item.get("raw_score_delta"):
                    warnings.append("raw_score_delta_mismatch")
        receipt = _find_receipt_for_result(base, str(result.get("scoring_preview_result_id") or ""))
        if not isinstance(receipt, Mapping):
            warnings.append("scoring_preview_receipt_missing")
        elif str(receipt.get("result_fingerprint") or "") != str(result.get("result_fingerprint") or ""):
            warnings.append("scoring_preview_receipt_fingerprint_mismatch")
    status = "corrupt" if any(item in warnings for item in ("compared_record_count_invalid", "raw_score_delta_mismatch", "scoring_preview_receipt_fingerprint_mismatch")) else "stale" if stale_count else "warning" if warnings else "healthy"
    return {
        "status": status,
        "scoring_preview_plan_count": len(plans),
        "scoring_preview_result_count": len(results),
        "scoring_preview_receipt_count": len(receipts),
        "stale_preview_count": stale_count,
        "warnings": _dedupe(warnings),
        "recommended_action": "Rerun the scoring preview against current dependencies." if stale_count else "Scoring preview health is good.",
    }


def format_certified_rule_scoring_preview_report(
    scoring_preview_result_id: str | None = None,
    scoring_preview_receipt_id: str | None = None,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    base = _ensure_dirs(root)
    receipt = _find_receipt_by_id(base, scoring_preview_receipt_id) if scoring_preview_receipt_id else None
    result = _find_result_by_id(base, scoring_preview_result_id or str((receipt or {}).get("scoring_preview_result_id") or ""))
    if not isinstance(result, Mapping):
        return "Certified Rule Scoring Preview\n\nStatus: not_found"
    preview = objective_preview_backend.load_certified_rule_objective_preview_result(str(result.get("objective_preview_result_id") or ""), root=base).get("objective_preview_result") or {}
    config = scoring_backend.load_objective_outcome_scoring_config(str(result.get("scoring_config_id") or ""), root=base).get("scoring_config") or {}
    metrics = result.get("metrics") or {}
    lines = [
        "Certified Rule Scoring Preview",
        "",
        f"Rule ID: {result.get('canonical_rule_id')}",
        f"Document ID: {result.get('document_id')}",
        f"Source Revision: {result.get('source_revision')}",
        f"Phase 9O Result Status: {preview.get('status', 'unknown')}",
        f"Phase 9O Compatibility: {'compatible' if preview.get('phase_9p_compatible') else 'legacy_incompatible'}",
        f"Objective Pack ID: {result.get('objective_pack_id')}",
        f"Scoring Config ID: {result.get('scoring_config_id')}",
        f"Configured Score Direction: {config.get('score_direction', 'unknown')}",
        f"Phase 9P Status: {result.get('status')}",
        f"Total Records: {metrics.get('total_phase_9o_records', 0)}",
        f"Scoreable Records: {metrics.get('scoreable_records', 0)}",
        f"Compared Records: {metrics.get('compared_records', 0)}",
        f"Increased Records: {metrics.get('increased_score_records', 0)}",
        f"Decreased Records: {metrics.get('decreased_score_records', 0)}",
        f"Unchanged Records: {metrics.get('unchanged_score_records', 0)}",
        f"Mixed Records: {metrics.get('mixed_component_records', 0)}",
        f"Unsupported Records: {metrics.get('unsupported_records', 0)}",
        f"Error Count: {metrics.get('scoring_error_records', 0)}",
        f"Scoring Coverage: {_pct(metrics.get('scoring_coverage'))}",
        f"Compatibility Rate: {_pct(metrics.get('scoring_compatibility_rate'))}",
        f"Baseline Mean Raw Score: {metrics.get('baseline_mean_raw_score')}",
        f"Rule-Enabled Mean Raw Score: {metrics.get('rule_enabled_mean_raw_score')}",
        f"Baseline Mean Bounded Score: {metrics.get('baseline_mean_bounded_score')}",
        f"Rule-Enabled Mean Bounded Score: {metrics.get('rule_enabled_mean_bounded_score')}",
        f"Mean Raw Delta: {metrics.get('mean_raw_score_delta')}",
        f"Median Raw Delta: {metrics.get('median_raw_score_delta')}",
        f"Minimum Raw Delta: {metrics.get('minimum_raw_score_delta')}",
        f"Maximum Raw Delta: {metrics.get('maximum_raw_score_delta')}",
        f"Mean Bounded Delta: {metrics.get('mean_bounded_score_delta')}",
        f"Median Bounded Delta: {metrics.get('median_bounded_score_delta')}",
        f"Minimum Bounded Delta: {metrics.get('minimum_bounded_score_delta')}",
        f"Maximum Bounded Delta: {metrics.get('maximum_bounded_score_delta')}",
        f"Stale: {'Yes' if _result_is_stale(base, result) else 'No'}",
        "Preview Mode: shadow_read_only",
        "Production Safety: scoring was shadow/read-only; production scoring was not modified; chart scoring was not modified; Fast Lane was not activated.",
        "Interpretation: numerical score changes do not prove profitability, safety, or deployment readiness.",
        f"Recommended Action: {_recommended_action(result)}",
    ]
    if not public_safe:
        lines.append(f"Result Fingerprint: {result.get('result_fingerprint')}")
    return "\n".join(lines)


def get_certified_rule_scoring_preview_summary(
    scoring_preview_plan_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    if not scoring_preview_plan_id:
        return {"status": "empty", "recommended_action": "Build one scoring preview plan."}
    plan = analysis_backend._read_json(_plan_path(base, scoring_preview_plan_id))
    result = _find_result(base, scoring_preview_plan_id)
    metrics = dict((result or {}).get("metrics") or {})
    return {
        "scoring_preview_plan_id": scoring_preview_plan_id,
        "objective_preview_result_id": (plan or {}).get("objective_preview_result_id"),
        "canonical_rule_id": (plan or {}).get("canonical_rule_id"),
        "document_id": (plan or {}).get("document_id"),
        "source_revision": (plan or {}).get("source_revision"),
        "status": (result or {}).get("status", "not_run"),
        "compatibility": (plan or {}).get("objective_preview_compatibility_capability", "unknown"),
        "scoreable_records": metrics.get("scoreable_records", (plan or {}).get("scoreable_record_count", 0)),
        "compared_records": metrics.get("compared_records", 0),
        "increased_records": metrics.get("increased_score_records", 0),
        "decreased_records": metrics.get("decreased_score_records", 0),
        "unchanged_records": metrics.get("unchanged_score_records", 0),
        "mean_score_delta": metrics.get("mean_bounded_score_delta", metrics.get("mean_raw_score_delta")),
        "scoring_coverage": metrics.get("scoring_coverage"),
        "recommended_action": "Run the read-only scoring preview." if result is None else _recommended_action(result),
    }


def _ensure_dirs(root: Path | str) -> Path:
    base = analysis_backend._ensure_analysis_dirs(root)
    for folder in (PLAN_DIR, RESULT_DIR, RECEIPT_DIR, "indexes"):
        (base / folder).mkdir(parents=True, exist_ok=True)
    defaults = (
        (PLAN_INDEX, "certified_rule_scoring_preview_plan_index_v1"),
        (RESULT_INDEX, "certified_rule_scoring_preview_result_index_v1"),
        (RECEIPT_INDEX, "certified_rule_scoring_preview_receipt_index_v1"),
    )
    for name, schema in defaults:
        path = base / "indexes" / name
        if not path.exists():
            analysis_backend._atomic_write_json(path, {"schema_version": schema, "items": [], "updated_at_utc": analysis_backend._now()})
    return base


def _plan_path(base: Path, scoring_preview_plan_id: str) -> Path:
    return base / PLAN_DIR / f"{analysis_backend._safe_id(scoring_preview_plan_id)}.json"


def _result_path(base: Path, scoring_preview_result_id: str) -> Path:
    return base / RESULT_DIR / f"{analysis_backend._safe_id(scoring_preview_result_id)}.json"


def _receipt_path(base: Path, scoring_preview_receipt_id: str) -> Path:
    return base / RECEIPT_DIR / f"{analysis_backend._safe_id(scoring_preview_receipt_id)}.json"


def _load_all(directory: Path) -> list[dict[str, Any]]:
    items = []
    for path in sorted(directory.glob("*.json")):
        payload = analysis_backend._read_json(path)
        if isinstance(payload, Mapping):
            items.append(dict(payload))
    return items


def _update_plan_index(base: Path) -> None:
    items = []
    for payload in _load_all(base / PLAN_DIR):
        items.append(
            {
                "scoring_preview_plan_id": payload.get("scoring_preview_plan_id"),
                "objective_preview_result_id": payload.get("objective_preview_result_id"),
                "scoring_config_id": payload.get("scoring_config_id"),
                "canonical_rule_id": payload.get("canonical_rule_id"),
                "document_id": payload.get("document_id"),
                "source_revision": payload.get("source_revision"),
                "plan_fingerprint": payload.get("plan_fingerprint"),
            }
        )
    analysis_backend._atomic_write_json(base / "indexes" / PLAN_INDEX, {"schema_version": "certified_rule_scoring_preview_plan_index_v1", "items": items, "updated_at_utc": analysis_backend._now()})


def _update_result_index(base: Path) -> None:
    items = []
    for payload in _load_all(base / RESULT_DIR):
        items.append(
            {
                "scoring_preview_result_id": payload.get("scoring_preview_result_id"),
                "scoring_preview_plan_id": payload.get("scoring_preview_plan_id"),
                "objective_preview_result_id": payload.get("objective_preview_result_id"),
                "canonical_rule_id": payload.get("canonical_rule_id"),
                "document_id": payload.get("document_id"),
                "source_revision": payload.get("source_revision"),
                "status": payload.get("status"),
                "result_fingerprint": payload.get("result_fingerprint"),
            }
        )
    analysis_backend._atomic_write_json(base / "indexes" / RESULT_INDEX, {"schema_version": "certified_rule_scoring_preview_result_index_v1", "items": items, "updated_at_utc": analysis_backend._now()})


def _update_receipt_index(base: Path) -> None:
    items = []
    for payload in _load_all(base / RECEIPT_DIR):
        items.append(
            {
                "scoring_preview_receipt_id": payload.get("scoring_preview_receipt_id"),
                "scoring_preview_result_id": payload.get("scoring_preview_result_id"),
                "scoring_preview_plan_id": payload.get("scoring_preview_plan_id"),
                "final_status": payload.get("final_status"),
                "result_fingerprint": payload.get("result_fingerprint"),
            }
        )
    analysis_backend._atomic_write_json(base / "indexes" / RECEIPT_INDEX, {"schema_version": "certified_rule_scoring_preview_receipt_index_v1", "items": items, "updated_at_utc": analysis_backend._now()})


def _find_plan(base: Path, objective_preview_result_id: str, scoring_config_id: str) -> dict[str, Any] | None:
    for payload in _load_all(base / PLAN_DIR):
        if str(payload.get("objective_preview_result_id") or "") == objective_preview_result_id and str(payload.get("scoring_config_id") or "") == scoring_config_id:
            return payload
    return None


def _find_result(base: Path, scoring_preview_plan_id: str) -> dict[str, Any] | None:
    for payload in _load_all(base / RESULT_DIR):
        if str(payload.get("scoring_preview_plan_id") or "") == scoring_preview_plan_id:
            return payload
    return None


def _find_result_by_id(base: Path, scoring_preview_result_id: str) -> dict[str, Any] | None:
    payload = analysis_backend._read_json(_result_path(base, scoring_preview_result_id))
    return dict(payload) if isinstance(payload, Mapping) else None


def _find_receipt_for_result(base: Path, scoring_preview_result_id: str) -> dict[str, Any] | None:
    for payload in _load_all(base / RECEIPT_DIR):
        if str(payload.get("scoring_preview_result_id") or "") == scoring_preview_result_id:
            return payload
    return None


def _find_receipt_by_id(base: Path, scoring_preview_receipt_id: str | None) -> dict[str, Any] | None:
    if not scoring_preview_receipt_id:
        return None
    payload = analysis_backend._read_json(_receipt_path(base, scoring_preview_receipt_id))
    return dict(payload) if isinstance(payload, Mapping) else None


def _plan_id(preview_result: Mapping[str, Any], config: Mapping[str, Any]) -> str:
    return "scoring_preview_" + analysis_backend._hash_payload(
        {
            "schema_version": PLAN_SCHEMA,
            "objective_preview_result_id": preview_result.get("objective_preview_result_id"),
            "objective_preview_result_fingerprint": preview_result.get("result_fingerprint"),
            "scoring_config_id": config.get("scoring_config_id"),
            "scoring_config_fingerprint": scoring_backend.get_objective_outcome_scoring_config_fingerprint(dict(config)),
            "scoring_evaluator_fingerprint": scoring_backend.get_objective_outcome_scoring_evaluator_fingerprint(),
        }
    )[:16]


def _result_id(scoring_preview_plan_id: str, plan: Mapping[str, Any]) -> str:
    return "scoring_result_" + analysis_backend._hash_payload(
        {
            "plan_id": scoring_preview_plan_id,
            "plan_fingerprint": plan.get("plan_fingerprint"),
            "schema_version": RESULT_SCHEMA,
        }
    )[:16]


def _receipt_id(scoring_preview_result_id: str) -> str:
    return f"receipt_{analysis_backend._safe_id(scoring_preview_result_id)}"


def _plan_fingerprint(
    preview_result: Mapping[str, Any],
    preview_receipt: Mapping[str, Any],
    config: Mapping[str, Any],
    total_records: int,
    scoreable_records: int,
) -> str:
    return analysis_backend._hash_payload(
        {
            "schema_version": PLAN_SCHEMA,
            "preview_schema_version": PREVIEW_SCHEMA_VERSION,
            "objective_preview_result_id": preview_result.get("objective_preview_result_id"),
            "objective_preview_receipt_id": preview_receipt.get("objective_preview_receipt_id"),
            "canonical_rule_id": preview_result.get("canonical_rule_id"),
            "document_id": preview_result.get("document_id"),
            "source_revision": preview_result.get("source_revision"),
            "rule_fingerprint": preview_result.get("rule_fingerprint"),
            "certification_fingerprint": preview_result.get("certification_fingerprint"),
            "objective_pack_id": preview_result.get("objective_pack_id"),
            "objective_pack_fingerprint": preview_result.get("objective_pack_fingerprint"),
            "controlled_input_id": preview_result.get("controlled_input_id"),
            "controlled_input_fingerprint": preview_result.get("controlled_input_fingerprint"),
            "objective_preview_result_fingerprint": preview_result.get("result_fingerprint"),
            "compatibility_capability": preview_result.get("objective_outcome_persistence"),
            "scoring_config_id": config.get("scoring_config_id"),
            "scoring_config_fingerprint": scoring_backend.get_objective_outcome_scoring_config_fingerprint(dict(config)),
            "scoring_evaluator_fingerprint": scoring_backend.get_objective_outcome_scoring_evaluator_fingerprint(),
            "total_records": total_records,
            "scoreable_records": scoreable_records,
            "preview_mode": "shadow_read_only",
        }
    )


def _result_fingerprint(plan: Mapping[str, Any], per_record: list[dict[str, Any]], metrics: Mapping[str, Any], status: str) -> str:
    return analysis_backend._hash_payload(
        {
            "schema_version": RESULT_SCHEMA,
            "plan_fingerprint": plan.get("plan_fingerprint"),
            "per_record_scoring_comparisons": per_record,
            "metrics": metrics,
            "status": status,
            "scoring_evaluator_fingerprint": plan.get("scoring_evaluator_fingerprint"),
        }
    )


def _plan_current_status(base: Path, plan: Mapping[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    eligibility = validate_certified_rule_scoring_preview_eligibility(
        str(plan.get("objective_preview_result_id") or ""),
        str(plan.get("scoring_config_id") or ""),
        root=base,
    )
    blockers.extend(list(eligibility.get("blockers", [])))
    if str(plan.get("preview_mode") or "") != "shadow_read_only":
        blockers.append("preview_mode_unsupported")
    if str(plan.get("scoring_evaluator_fingerprint") or "") != scoring_backend.get_objective_outcome_scoring_evaluator_fingerprint():
        blockers.append("scoring_evaluator_fingerprint_mismatch")
    if blockers:
        if "objective_preview_result_stale" in blockers or "source_revision_not_current" in blockers:
            return {"status": "stale", "blockers": _dedupe(blockers)}
        if any(item.endswith("_mismatch") for item in blockers):
            return {"status": "corrupt", "blockers": _dedupe(blockers)}
        return {"status": "blocked", "blockers": _dedupe(blockers)}
    return {"status": "current", "blockers": []}


def _result_is_stale(base: Path, result: Mapping[str, Any]) -> bool:
    preview_loaded = objective_preview_backend.load_certified_rule_objective_preview_result(str(result.get("objective_preview_result_id") or ""), root=base)
    preview_result = preview_loaded.get("objective_preview_result")
    if not isinstance(preview_result, Mapping):
        return True
    config_loaded = scoring_backend.load_objective_outcome_scoring_config(str(result.get("scoring_config_id") or ""), root=base)
    config = config_loaded.get("scoring_config")
    if not isinstance(config, Mapping):
        return True
    return any(
        [
            str(result.get("preview_schema_version") or "") != PREVIEW_SCHEMA_VERSION,
            str(result.get("objective_preview_result_fingerprint") or "") != str(preview_result.get("result_fingerprint") or ""),
            str(result.get("rule_fingerprint") or "") != str(preview_result.get("rule_fingerprint") or ""),
            str(result.get("certification_fingerprint") or "") != str(preview_result.get("certification_fingerprint") or ""),
            str(result.get("source_revision") or "") != str(preview_result.get("source_revision") or ""),
            str(result.get("objective_pack_evaluation_fingerprint") or "") != str(preview_result.get("objective_pack_fingerprint") or ""),
            str(result.get("controlled_input_fingerprint") or "") != str(preview_result.get("controlled_input_fingerprint") or ""),
            str(result.get("scoring_config_fingerprint") or "") != scoring_backend.get_objective_outcome_scoring_config_fingerprint(dict(config)),
            str(result.get("scoring_evaluator_fingerprint") or "") != scoring_backend.get_objective_outcome_scoring_evaluator_fingerprint(),
        ]
    )


def _scoreable_record_count(preview_result: Mapping[str, Any]) -> int:
    count = 0
    for record in list(preview_result.get("per_record_results", []) or []):
        if isinstance((record or {}).get("baseline_objective_outcomes"), Mapping) and isinstance((record or {}).get("rule_enabled_objective_outcomes"), Mapping):
            count += 1
    return count


def _compare_components(baseline_score: Mapping[str, Any], enabled_score: Mapping[str, Any]) -> dict[str, list[str]]:
    baseline_by_id = {
        str(item.get("objective_id") or ""): dict(item)
        for item in list(baseline_score.get("component_results", []) or [])
        if isinstance(item, Mapping)
    }
    enabled_by_id = {
        str(item.get("objective_id") or ""): dict(item)
        for item in list(enabled_score.get("component_results", []) or [])
        if isinstance(item, Mapping)
    }
    ordered_ids = [str(item.get("objective_id") or "") for item in list(baseline_score.get("component_results", []) or []) if isinstance(item, Mapping)]
    changed: list[str] = []
    unchanged: list[str] = []
    for objective_id in ordered_ids:
        left = baseline_by_id.get(objective_id) or {}
        right = enabled_by_id.get(objective_id) or {}
        left_view = {
            "component_status": left.get("component_status"),
            "contribution": left.get("contribution"),
            "error_code": left.get("error_code"),
            "source_outcome_status": left.get("source_outcome_status"),
        }
        right_view = {
            "component_status": right.get("component_status"),
            "contribution": right.get("contribution"),
            "error_code": right.get("error_code"),
            "source_outcome_status": right.get("source_outcome_status"),
        }
        if left_view == right_view:
            unchanged.append(objective_id)
        else:
            changed.append(objective_id)
    return {"changed_component_ids": changed, "unchanged_component_ids": unchanged}


def _classify_scored_record(component_compare: Mapping[str, list[str]], raw_delta: float | None, bounded_delta: float | None) -> str:
    primary = bounded_delta if bounded_delta is not None else raw_delta
    if primary is None:
        return "scoring_error"
    if primary > 0:
        return "score_increased"
    if primary < 0:
        return "score_decreased"
    return "mixed_component_change" if component_compare.get("changed_component_ids") else "score_unchanged"


def _safe_error_codes(*scores: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for score in scores:
        values.extend(str(item) for item in list(score.get("blockers", []) or []))
        for component in list(score.get("component_results", []) or []):
            if isinstance(component, Mapping) and component.get("error_code"):
                values.append(str(component.get("error_code")))
    return _dedupe(values)


def _delta(left: Any, right: Any) -> float | None:
    if left is None or right is None:
        return None
    return _round_or_none(float(right) - float(left))


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _round_or_none(value: float | None) -> float | None:
    return round(float(value), 6) if value is not None else None


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 6)


def _pct(value: float | None) -> str:
    return "null" if value is None else f"{round(value * 100, 2)}%"


def _read_only_snapshots(base: Path, preview_result: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, str]:
    rule_id = str(preview_result.get("canonical_rule_id") or "")
    preview_result_id = str(preview_result.get("objective_preview_result_id") or "")
    return {
        "rule": json.dumps(load_canonical_rule(rule_id, require_active=False, root=base).get("rule") or {}, sort_keys=True),
        "certification": json.dumps(_load_certification_receipt_for_rule(base, rule_id) or {}, sort_keys=True),
        "objective_pack": json.dumps(load_objective_pack(str(preview_result.get("objective_pack_id") or ""), root=base / "objective_packs"), sort_keys=True),
        "objective_preview_result": json.dumps(analysis_backend._read_json(objective_preview_backend._result_path(base, preview_result_id)) or {}, sort_keys=True),
        "objective_preview_receipt": json.dumps(objective_preview_backend._find_receipt_for_result(base, preview_result_id) or {}, sort_keys=True),
        "scoring_config": json.dumps(scoring_backend.load_objective_outcome_scoring_config(str(config.get("scoring_config_id") or ""), root=base).get("scoring_config") or {}, sort_keys=True),
    }


def _recommended_action(result: Mapping[str, Any]) -> str:
    status = str(result.get("status") or "unknown")
    if status == "completed":
        return "Review the read-only scoring deltas and receipt."
    if status == "completed_with_unsupported_records":
        return "Review unsupported records before downstream preview work."
    if status == "no_scoreable_records":
        return "Resolve Phase 9O unsupported or non-scoreable records first."
    if status == "stale":
        return "Rebuild the scoring preview plan against current dependencies."
    return "Resolve blockers before continuing the scoring preview workflow."


def _plan_summary(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "objective_preview_result_id": plan.get("objective_preview_result_id"),
        "objective_preview_receipt_id": plan.get("objective_preview_receipt_id"),
        "canonical_rule_id": plan.get("canonical_rule_id"),
        "document_id": plan.get("document_id"),
        "source_revision": plan.get("source_revision"),
        "objective_pack_id": plan.get("objective_pack_id"),
        "scoring_config_id": plan.get("scoring_config_id"),
        "total_record_count": plan.get("total_record_count"),
        "scoreable_record_count": plan.get("scoreable_record_count"),
        "preview_mode": plan.get("preview_mode"),
        "warnings": list(plan.get("warnings", [])),
        "blockers": list(plan.get("blockers", [])),
    }


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in items if str(item)))
