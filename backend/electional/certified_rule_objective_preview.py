"""Single-rule objective-pack read-only impact preview."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from . import autonomous_pdf_benchmark as benchmark_backend
from . import autonomous_pdf_remediation as remediation_backend
from . import rule_effectiveness_analysis as analysis_backend
from .canonical_rule_runtime import evaluate_canonical_rule, get_canonical_rule_runtime_capability, load_canonical_rule
from .certified_rule_replay_adapter import _load_replay_dataset, _plan_current_status as _replay_plan_current_status, _rule_has_unresolved_critical_remediation, _rule_pending_supersession, _validate_dataset
from .document_manifest import load_document_manifest
from .objective_evaluation import INPUT_SCHEMA_VERSION, evaluate_objective_pack, get_objective_evaluator_fingerprint
from .objective_packs import classify_objective_pack_capability, get_objective_pack_evaluation_fingerprint, get_objective_pack_required_input_fields, load_objective_pack, validate_objective_pack
from .rule_effectiveness_analysis import _dataset_fingerprint, _ensure_analysis_dirs, _hash_payload, _load_certification_receipt_for_rule
from .source_documents import SOURCE_DOCUMENT_ROOT

PLAN_DIR = "certified_rule_objective_preview_plans"
RESULT_DIR = "certified_rule_objective_preview_results"
RECEIPT_DIR = "certified_rule_objective_preview_receipts"
PLAN_INDEX = "certified_rule_objective_preview_plan_index.json"
RESULT_INDEX = "certified_rule_objective_preview_result_index.json"
RECEIPT_INDEX = "certified_rule_objective_preview_receipt_index.json"
PLAN_SCHEMA = "certified_rule_objective_preview_plan_v1"
RESULT_SCHEMA = "certified_rule_objective_preview_result_v2"
RECEIPT_SCHEMA = "certified_rule_objective_preview_receipt_v2"
PREVIEW_SCHEMA_VERSION = "certified_rule_objective_preview_v1"
OBJECTIVE_OUTCOME_PERSISTENCE = "baseline_and_rule_enabled_v1"


def build_certified_rule_objective_preview_workspace(
    canonical_rule_id: str,
    objective_pack_id: str,
    controlled_input_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    eligibility = validate_certified_rule_objective_preview_eligibility(canonical_rule_id, objective_pack_id, controlled_input_id=controlled_input_id, root=base)
    rule = load_canonical_rule(canonical_rule_id, require_active=False, root=base).get("rule")
    certification = _load_certification_receipt_for_rule(base, canonical_rule_id)
    dataset = _load_replay_dataset(base, controlled_input_id) if controlled_input_id else None
    plan = _find_plan(base, canonical_rule_id, objective_pack_id, controlled_input_id or "")
    result = _find_result(base, str((plan or {}).get("objective_preview_plan_id") or ""))
    receipt = _find_receipt_for_result(base, str((result or {}).get("objective_preview_result_id") or ""))
    return {
        "status": "ready_for_planning" if not eligibility.get("blockers") else "blocked",
        "canonical_rule_id": canonical_rule_id,
        "objective_pack_id": objective_pack_id,
        "controlled_input_id": controlled_input_id,
        "document_id": (rule or {}).get("document_id"),
        "source_revision": (rule or {}).get("source_revision"),
        "rule_status": (rule or {}).get("status", "missing"),
        "certification_status": (certification or {}).get("certification_status", "missing"),
        "objective_pack_status": eligibility.get("objective_pack_status", "unknown"),
        "controlled_input_status": "available" if isinstance(dataset, Mapping) else "missing" if controlled_input_id else "not_selected",
        "objective_preview_plan_id": (plan or {}).get("objective_preview_plan_id"),
        "objective_preview_result_id": (result or {}).get("objective_preview_result_id"),
        "objective_preview_receipt_id": (receipt or {}).get("objective_preview_receipt_id"),
        "warnings": list(eligibility.get("warnings", [])),
        "blockers": list(eligibility.get("blockers", [])),
        "recommended_action": "Build the shadow read-only objective preview plan." if not eligibility.get("blockers") else "Resolve rule, objective pack, input, or mapping blockers first.",
    }


def validate_certified_rule_objective_preview_eligibility(
    canonical_rule_id: str,
    objective_pack_id: str,
    controlled_input_id: str | None = None,
    effect_mapping: Mapping[str, Any] | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    blockers: list[str] = []
    warnings: list[str] = []
    if not get_canonical_rule_runtime_capability(root=base).get("single_rule_evaluator_available"):
        blockers.append("canonical_rule_evaluator_unavailable")
    loaded = load_canonical_rule(canonical_rule_id, require_active=True, root=base)
    rule = loaded.get("rule")
    if loaded.get("status") != "loaded" or not isinstance(rule, Mapping):
        blockers.extend(list(loaded.get("blockers", []) or ["canonical_rule_not_found"]))
        rule = {}
    certification = _load_certification_receipt_for_rule(base, canonical_rule_id)
    if not isinstance(certification, Mapping):
        blockers.append("rule_certification_missing")
    else:
        if str(certification.get("certification_status") or "") != "completed":
            blockers.append("rule_not_certified")
        if isinstance(rule, Mapping) and str(certification.get("rule_hash") or "") != _hash_payload(rule):
            blockers.append("rule_certification_hash_mismatch")
    manifest = load_document_manifest(str((rule or {}).get("document_id") or ""), root=base).get("manifest") if rule else None
    if isinstance(rule, Mapping) and isinstance(manifest, Mapping):
        if str(rule.get("source_revision") or "") != str(manifest.get("source_revision") or ""):
            blockers.append("source_revision_not_current")
    elif rule:
        blockers.append("document_manifest_missing")
    if _rule_has_unresolved_critical_remediation(base, rule):
        blockers.append("rule_has_unresolved_critical_remediation")
    if _rule_pending_supersession(base, canonical_rule_id):
        blockers.append("rule_pending_supersession")
    try:
        objective_pack = load_objective_pack(objective_pack_id, root=base / "objective_packs")
        pack_ok, pack_errors = validate_objective_pack(objective_pack)
    except Exception:
        objective_pack = None
        pack_ok, pack_errors = False, ["objective_pack_missing"]
    if not pack_ok:
        blockers.extend(pack_errors)
    else:
        capability = classify_objective_pack_capability(objective_pack)
        if capability["capability"] != "evaluable":
            blockers.append("objective_pack_not_evaluable")
        else:
            try:
                get_objective_pack_evaluation_fingerprint(objective_pack)
            except Exception:
                blockers.append("objective_pack_fingerprint_unavailable")
    dataset = _load_replay_dataset(base, controlled_input_id) if controlled_input_id else None
    if controlled_input_id:
        blockers.extend(_validate_dataset(controlled_input_id, dataset))
        if isinstance(dataset, Mapping):
            if len(list(dataset.get("records", []) or [])) > 10000:
                blockers.append("controlled_input_limit_exceeded:10000")
    if effect_mapping is not None and isinstance(objective_pack, Mapping):
        blockers.extend(_validate_effect_mapping(effect_mapping, objective_pack))
    return {
        "status": "eligible" if not blockers else "blocked",
        "canonical_rule_id": canonical_rule_id,
        "objective_pack_id": objective_pack_id,
        "controlled_input_id": controlled_input_id,
        "document_id": (rule or {}).get("document_id"),
        "source_revision": (rule or {}).get("source_revision"),
        "rule_fingerprint": _hash_payload(rule) if isinstance(rule, Mapping) else None,
        "certification_fingerprint": _certification_fingerprint(certification) if isinstance(certification, Mapping) else None,
        "objective_pack_status": "evaluable" if isinstance(objective_pack, Mapping) and not pack_errors and classify_objective_pack_capability(objective_pack)["capability"] == "evaluable" else "invalid",
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
    }


def build_certified_rule_objective_preview_plan(
    canonical_rule_id: str,
    objective_pack_id: str,
    controlled_input_id: str,
    effect_mapping: Mapping[str, Any],
    max_records: int = 10000,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    eligibility = validate_certified_rule_objective_preview_eligibility(canonical_rule_id, objective_pack_id, controlled_input_id=controlled_input_id, effect_mapping=effect_mapping, root=base)
    if eligibility.get("blockers"):
        return {"status": "blocked", "canonical_rule_id": canonical_rule_id, "objective_pack_id": objective_pack_id, "controlled_input_id": controlled_input_id, "blockers": list(eligibility.get("blockers", [])), "warnings": []}
    rule = load_canonical_rule(canonical_rule_id, require_active=True, root=base).get("rule") or {}
    certification = _load_certification_receipt_for_rule(base, canonical_rule_id) or {}
    objective_pack = load_objective_pack(objective_pack_id, root=base / "objective_packs")
    dataset = _load_replay_dataset(base, controlled_input_id) or {}
    records = list(dataset.get("records", []) or [])
    if len(records) > max_records:
        return {"status": "blocked", "canonical_rule_id": canonical_rule_id, "objective_pack_id": objective_pack_id, "controlled_input_id": controlled_input_id, "blockers": [f"controlled_input_limit_exceeded:{max_records}"], "warnings": []}
    mapping_fp = _effect_mapping_fingerprint(effect_mapping)
    plan_id = _plan_id(canonical_rule_id, objective_pack_id, controlled_input_id, max_records, rule, certification, objective_pack, dataset, mapping_fp)
    plan = {
        "schema_version": PLAN_SCHEMA,
        "preview_schema_version": PREVIEW_SCHEMA_VERSION,
        "objective_preview_plan_id": plan_id,
        "canonical_rule_id": canonical_rule_id,
        "document_id": rule.get("document_id"),
        "source_revision": rule.get("source_revision"),
        "rule_fingerprint": _hash_payload(rule),
        "certification_receipt_id": certification.get("certification_receipt_id"),
        "certification_fingerprint": _certification_fingerprint(certification),
        "objective_pack_id": objective_pack_id,
        "objective_pack_fingerprint": get_objective_pack_evaluation_fingerprint(objective_pack),
        "controlled_input_id": controlled_input_id,
        "controlled_input_fingerprint": _dataset_fingerprint(dataset),
        "effect_mapping": deepcopy(dict(effect_mapping)),
        "effect_mapping_fingerprint": mapping_fp,
        "bounded_record_count": len(records),
        "record_limit": max_records,
        "rule_evaluator_fingerprint": _rule_evaluator_fingerprint(),
        "objective_evaluator_fingerprint": get_objective_evaluator_fingerprint(),
        "preview_mode": "shadow_read_only",
        "input_mapping": {"record.values": "evaluation_context|values|context", "record.timestamp": "timestamp", "record.identity": "record_id"},
        "plan_fingerprint": _hash_payload({
            "rule": _hash_payload(rule),
            "certification": _certification_fingerprint(certification),
            "objective_pack": get_objective_pack_evaluation_fingerprint(objective_pack),
            "controlled_input": _dataset_fingerprint(dataset),
            "effect_mapping": mapping_fp,
            "record_count": len(records),
            "max_records": max_records,
            "rule_evaluator": _rule_evaluator_fingerprint(),
            "objective_evaluator": get_objective_evaluator_fingerprint(),
            "schema": PREVIEW_SCHEMA_VERSION,
        }),
        "warnings": [],
        "blockers": [],
    }
    before = _read_json(_plan_path(base, plan_id))
    before_index = _read_json(base / "indexes" / PLAN_INDEX)
    try:
        analysis_backend._atomic_write_json(_plan_path(base, plan_id), plan)
        _update_plan_index(base)
    except Exception:
        _restore_json(_plan_path(base, plan_id), before)
        _restore_json(base / "indexes" / PLAN_INDEX, before_index)
        return {"status": "corrupt", "blockers": ["objective_preview_plan_write_failure"], "warnings": []}
    return {
        "status": "planned",
        "objective_preview_plan_id": plan_id,
        "canonical_rule_id": canonical_rule_id,
        "objective_pack_id": objective_pack_id,
        "controlled_input_id": controlled_input_id,
        "bounded_record_count": len(records),
        "preview_mode": "shadow_read_only",
        "warnings": [],
        "blockers": [],
    }


def run_certified_rule_objective_preview(
    objective_preview_plan_id: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    if confirmation != "RUN_OBJECTIVE_PREVIEW":
        return {"status": "blocked", "objective_preview_plan_id": objective_preview_plan_id, "blockers": ["run_objective_preview_confirmation_required"], "warnings": []}
    plan = _read_json(_plan_path(base, objective_preview_plan_id))
    if not isinstance(plan, Mapping):
        return {"status": "blocked", "objective_preview_plan_id": objective_preview_plan_id, "blockers": ["objective_preview_plan_missing"], "warnings": []}
    current = _plan_current_status(base, plan)
    if current["status"] != "current":
        return {"status": current["status"], "objective_preview_plan_id": objective_preview_plan_id, "blockers": list(current.get("blockers", [])), "warnings": []}
    existing = _find_result(base, objective_preview_plan_id, require_phase_9p_compatible=True)
    if isinstance(existing, Mapping) and not _result_is_stale(base, existing):
        receipt = _find_receipt_for_result(base, str(existing.get("objective_preview_result_id") or ""))
        return {"status": "already_completed", "objective_preview_result_id": existing.get("objective_preview_result_id"), "objective_preview_receipt_id": (receipt or {}).get("objective_preview_receipt_id"), "writes_performed": 0}
    rule = load_canonical_rule(str(plan.get("canonical_rule_id") or ""), require_active=True, root=base).get("rule") or {}
    objective_pack = load_objective_pack(str(plan.get("objective_pack_id") or ""), root=base / "objective_packs")
    dataset = _load_replay_dataset(base, str(plan.get("controlled_input_id") or "")) or {}
    rule_before = json.dumps(rule, sort_keys=True)
    pack_before = json.dumps(objective_pack, sort_keys=True)
    dataset_before = json.dumps(dataset, sort_keys=True)
    per_record_results: list[dict[str, Any]] = []
    objective_summary: dict[str, dict[str, Any]] = {}
    eligible_records = compared = unchanged = improved = worsened = mixed = unsupported = rule_errors = objective_errors = 0
    objectives_evaluated: set[str] = set()
    objectives_changed: set[str] = set()
    for record in list(dataset.get("records", []) or []):
        input_record = _build_controlled_input(record)
        baseline = evaluate_objective_pack(objective_pack, deepcopy(input_record))
        persisted_baseline = _persistable_objective_outcomes(baseline, input_record["record_id"])
        rule_eval = evaluate_canonical_rule(dict(rule), dict(input_record.get("values") or {}), root=base)
        shadow_values = deepcopy(dict(input_record.get("values") or {}))
        rule_status = str(rule_eval.get("result") or "")
        if rule_status == "matched":
            _apply_effect_mapping(shadow_values, dict(plan.get("effect_mapping") or {}), branch="on_match")
        elif rule_status == "not_matched":
            _apply_effect_mapping(shadow_values, dict(plan.get("effect_mapping") or {}), branch="on_no_match")
        elif rule_status == "error":
            record_classification = "rule_evaluator_error"
            per_record_results.append({
                "record_id": input_record["record_id"],
                "timestamp": input_record.get("timestamp"),
                "classification": record_classification,
                "record_classification": record_classification,
                "rule_result": rule_status,
                "rule_evaluation_summary": {"result": rule_status},
                "baseline_objective_outcomes": persisted_baseline,
                "rule_enabled_objective_outcomes": None,
                "objective_comparisons": [],
            })
            rule_errors += 1
            eligible_records += 1
            continue
        elif rule_status not in {"matched", "not_matched"}:
            per_record_results.append({
                "record_id": input_record["record_id"],
                "timestamp": input_record.get("timestamp"),
                "classification": "unsupported",
                "record_classification": "unsupported",
                "rule_result": rule_status,
                "rule_evaluation_summary": {"result": rule_status},
                "baseline_objective_outcomes": persisted_baseline,
                "rule_enabled_objective_outcomes": None,
                "objective_comparisons": [],
            })
            unsupported += 1
            eligible_records += 1
            continue
        preview_input = deepcopy(input_record)
        preview_input["values"] = shadow_values
        preview = evaluate_objective_pack(objective_pack, preview_input)
        persisted_preview = _persistable_objective_outcomes(preview, input_record["record_id"])
        record_objectives = _compare_objective_results(baseline, preview)
        record_classification = _classify_record(record_objectives)
        per_record_results.append({
            "record_id": input_record["record_id"],
            "timestamp": input_record.get("timestamp"),
            "classification": record_classification,
            "record_classification": record_classification,
            "rule_result": rule_status,
            "rule_evaluation_summary": {"result": rule_status},
            "baseline_objective_outcomes": persisted_baseline,
            "rule_enabled_objective_outcomes": persisted_preview,
            "objective_comparisons": record_objectives,
        })
        eligible_records += 1
        if record_classification in {"unchanged", "objective_improved", "objective_worsened", "mixed_objective_change"}:
            compared += 1
        if record_classification == "unchanged":
            unchanged += 1
        elif record_classification == "objective_improved":
            improved += 1
        elif record_classification == "objective_worsened":
            worsened += 1
        elif record_classification == "mixed_objective_change":
            mixed += 1
        elif record_classification == "unsupported":
            unsupported += 1
        elif record_classification == "objective_evaluator_error":
            objective_errors += 1
        for item in record_objectives:
            objective_id = str(item.get("objective_id") or "")
            summary = objective_summary.setdefault(objective_id, {"objective_id": objective_id, "baseline_evaluated_count": 0, "preview_evaluated_count": 0, "baseline_satisfied_count": 0, "preview_satisfied_count": 0, "newly_satisfied_count": 0, "newly_unsatisfied_count": 0, "unchanged_satisfied_count": 0, "unchanged_unsatisfied_count": 0, "unsupported_count": 0, "evaluator_error_count": 0})
            cls = str(item.get("comparison") or "")
            if cls not in {"baseline_unsupported", "preview_unsupported", "evaluator_error"}:
                summary["baseline_evaluated_count"] += 1
                summary["preview_evaluated_count"] += 1
                objectives_evaluated.add(objective_id)
            if cls == "newly_satisfied":
                summary["newly_satisfied_count"] += 1
                summary["preview_satisfied_count"] += 1
                objectives_changed.add(objective_id)
            elif cls == "newly_unsatisfied":
                summary["newly_unsatisfied_count"] += 1
                summary["baseline_satisfied_count"] += 1
                objectives_changed.add(objective_id)
            elif cls == "unchanged_satisfied":
                summary["unchanged_satisfied_count"] += 1
                summary["baseline_satisfied_count"] += 1
                summary["preview_satisfied_count"] += 1
            elif cls == "unchanged_unsatisfied":
                summary["unchanged_unsatisfied_count"] += 1
            elif cls in {"baseline_unsupported", "preview_unsupported"}:
                summary["unsupported_count"] += 1
            elif cls == "evaluator_error":
                summary["evaluator_error_count"] += 1
    metrics = {
        "total_records": len(list(dataset.get("records", []) or [])),
        "eligible_records": eligible_records,
        "compared_records": compared,
        "unchanged_records": unchanged,
        "improved_records": improved,
        "worsened_records": worsened,
        "mixed_records": mixed,
        "unsupported_records": unsupported,
        "rule_evaluator_errors": rule_errors,
        "objective_evaluator_errors": objective_errors,
        "preview_coverage": _ratio(compared, len(list(dataset.get("records", []) or []))),
        "compatibility_rate": _ratio(max(0, eligible_records - unsupported - rule_errors - objective_errors), len(list(dataset.get("records", []) or []))),
        "objective_change_rate": _ratio(improved + worsened + mixed, compared),
        "objective_improvement_rate": _ratio(improved, compared),
        "objective_worsening_rate": _ratio(worsened, compared),
        "objectives_evaluated": len(objectives_evaluated),
        "objectives_with_changed_outcomes": len(objectives_changed),
    }
    mutation_detected = json.dumps(rule, sort_keys=True) != rule_before or json.dumps(objective_pack, sort_keys=True) != pack_before or json.dumps(dataset, sort_keys=True) != dataset_before
    status = (
        "mutation_detected" if mutation_detected else
        "rule_evaluator_failed" if rule_errors else
        "objective_evaluator_failed" if objective_errors else
        "completed_with_unsupported_records" if unsupported else
        "no_eligible_records" if eligible_records == 0 else
        "completed"
    )
    result_id = _result_id(objective_preview_plan_id, plan)
    result = {
        "schema_version": RESULT_SCHEMA,
        "preview_schema_version": PREVIEW_SCHEMA_VERSION,
        "objective_outcome_persistence": OBJECTIVE_OUTCOME_PERSISTENCE,
        "objective_preview_result_id": result_id,
        "objective_preview_plan_id": objective_preview_plan_id,
        "canonical_rule_id": plan.get("canonical_rule_id"),
        "document_id": plan.get("document_id"),
        "source_revision": plan.get("source_revision"),
        "rule_fingerprint": plan.get("rule_fingerprint"),
        "certification_receipt_id": plan.get("certification_receipt_id"),
        "certification_fingerprint": plan.get("certification_fingerprint"),
        "objective_pack_id": plan.get("objective_pack_id"),
        "objective_pack_fingerprint": plan.get("objective_pack_fingerprint"),
        "controlled_input_id": plan.get("controlled_input_id"),
        "controlled_input_fingerprint": plan.get("controlled_input_fingerprint"),
        "effect_mapping_fingerprint": plan.get("effect_mapping_fingerprint"),
        "rule_evaluator_fingerprint": plan.get("rule_evaluator_fingerprint"),
        "objective_evaluator_fingerprint": plan.get("objective_evaluator_fingerprint"),
        "preview_mode": "shadow_read_only",
        "per_record_results": per_record_results,
        "per_objective_comparisons": list(objective_summary.values()),
        "metrics": metrics,
        "warnings": [],
        "blockers": ["production_state_mutation_detected"] if mutation_detected else [],
        "status": status,
        "result_fingerprint": _result_fingerprint(plan, per_record_results, list(objective_summary.values()), metrics, status),
    }
    receipt_id = _receipt_id(result_id)
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "objective_outcome_persistence": OBJECTIVE_OUTCOME_PERSISTENCE,
        "objective_preview_receipt_id": receipt_id,
        "objective_preview_result_id": result_id,
        "objective_preview_plan_id": objective_preview_plan_id,
        "canonical_rule_id": plan.get("canonical_rule_id"),
        "document_id": plan.get("document_id"),
        "source_revision": plan.get("source_revision"),
        "result_schema_version": RESULT_SCHEMA,
        "rule_fingerprint": plan.get("rule_fingerprint"),
        "certification_fingerprint": plan.get("certification_fingerprint"),
        "objective_pack_evaluation_fingerprint": plan.get("objective_pack_fingerprint"),
        "objective_pack_fingerprint": plan.get("objective_pack_fingerprint"),
        "controlled_input_fingerprint": plan.get("controlled_input_fingerprint"),
        "effect_mapping_fingerprint": plan.get("effect_mapping_fingerprint"),
        "rule_evaluator_fingerprint": plan.get("rule_evaluator_fingerprint"),
        "objective_evaluator_fingerprint": plan.get("objective_evaluator_fingerprint"),
        "record_count": len(per_record_results),
        "baseline_outcome_payload_count": sum(1 for item in per_record_results if isinstance(item.get("baseline_objective_outcomes"), Mapping)),
        "rule_enabled_outcome_payload_count": sum(1 for item in per_record_results if isinstance(item.get("rule_enabled_objective_outcomes"), Mapping)),
        "result_fingerprint": result["result_fingerprint"],
        "final_status": status,
        "metric_summary": metrics,
    }
    before_result = _read_json(_result_path(base, result_id))
    before_receipt = _read_json(_receipt_path(base, receipt_id))
    before_result_index = _read_json(base / "indexes" / RESULT_INDEX)
    before_receipt_index = _read_json(base / "indexes" / RECEIPT_INDEX)
    try:
        analysis_backend._atomic_write_json(_result_path(base, result_id), result)
        analysis_backend._atomic_write_json(_receipt_path(base, receipt_id), receipt)
        _update_result_index(base)
        _update_receipt_index(base)
    except Exception:
        _restore_json(_result_path(base, result_id), before_result)
        _restore_json(_receipt_path(base, receipt_id), before_receipt)
        _restore_json(base / "indexes" / RESULT_INDEX, before_result_index)
        _restore_json(base / "indexes" / RECEIPT_INDEX, before_receipt_index)
        return {"status": "corrupt", "objective_preview_plan_id": objective_preview_plan_id, "blockers": ["objective_preview_result_write_failure"], "warnings": []}
    return {"status": status, "objective_preview_plan_id": objective_preview_plan_id, "objective_preview_result_id": result_id, "objective_preview_receipt_id": receipt_id, "writes_performed": 2}


def load_certified_rule_objective_preview_result(
    objective_preview_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    result = _read_json(_result_path(base, objective_preview_result_id))
    if not isinstance(result, Mapping):
        return {"status": "not_found", "objective_preview_result_id": objective_preview_result_id, "objective_preview_result": None, "warnings": []}
    payload = dict(result)
    payload["stale"] = _result_is_stale(base, payload)
    payload["phase_9p_compatible"] = _result_supports_phase_9p(payload)
    payload["compatibility_blockers"] = [] if payload["phase_9p_compatible"] else ["persisted_objective_outcomes_missing", "legacy_objective_preview_result"]
    return {"status": "loaded", "objective_preview_result_id": objective_preview_result_id, "objective_preview_result": payload, "warnings": []}


def get_certified_rule_objective_preview_health(
    objective_preview_plan_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    plans = _load_all_plans(base)
    results = _load_all_results(base)
    receipts = _load_all_receipts(base)
    if objective_preview_plan_id:
        plans = [item for item in plans if str(item.get("objective_preview_plan_id") or "") == objective_preview_plan_id]
        results = [item for item in results if str(item.get("objective_preview_plan_id") or "") == objective_preview_plan_id]
        receipts = [item for item in receipts if str(item.get("objective_preview_plan_id") or "") == objective_preview_plan_id]
    if not plans and not results and not receipts:
        return {"status": "empty", "objective_preview_plan_count": 0, "objective_preview_result_count": 0, "objective_preview_receipt_count": 0, "recommended_action": "Build one certified-rule objective preview plan."}
    warnings: list[str] = []
    stale_count = 0
    legacy_count = 0
    if len({str(item.get("objective_preview_plan_id") or "") for item in plans}) != len(plans):
        warnings.append("duplicate_objective_preview_plan_ids")
    if len({str(item.get("objective_preview_result_id") or "") for item in results}) != len(results):
        warnings.append("duplicate_objective_preview_result_ids")
    if len({str(item.get("objective_preview_receipt_id") or "") for item in receipts}) != len(receipts):
        warnings.append("duplicate_objective_preview_receipt_ids")
    for result in results:
        if not _result_supports_phase_9p(result):
            legacy_count += 1
            warnings.append("legacy_objective_preview_result")
        if _result_is_stale(base, result):
            stale_count += 1
        metrics = result.get("metrics") or {}
        for key in ("preview_coverage", "compatibility_rate", "objective_change_rate", "objective_improvement_rate", "objective_worsening_rate"):
            value = metrics.get(key)
            if isinstance(value, (int, float)) and (value < 0 or value > 1):
                warnings.append("impossible_metric_value")
        if not result.get("per_objective_comparisons"):
            warnings.append("missing_objective_comparisons")
        if "production_state_mutation_detected" in list(result.get("blockers", []) or []):
            warnings.append("production_state_mutation_detected")
        warnings.extend(_compatibility_warnings(result))
    receipt_payload_total = sum(int(item.get("baseline_outcome_payload_count") or 0) + int(item.get("rule_enabled_outcome_payload_count") or 0) for item in receipts)
    result_payload_total = sum(_result_payload_count(item) for item in results)
    if receipts and receipt_payload_total != result_payload_total:
        warnings.append("receipt_outcome_payload_count_mismatch")
    status = "corrupt" if any(item in warnings for item in ("baseline_record_id_mismatch", "rule_enabled_record_id_mismatch", "pack_id_mismatch", "pack_fingerprint_mismatch", "evaluator_fingerprint_mismatch", "objective_order_mismatch", "duplicate_objective_ids", "missing_objective_result_fingerprint")) else "stale" if stale_count else "warning" if warnings else "healthy"
    return {
        "status": status,
        "objective_preview_plan_count": len(plans),
        "objective_preview_result_count": len(results),
        "objective_preview_receipt_count": len(receipts),
        "stale_preview_count": stale_count,
        "legacy_preview_count": legacy_count,
        "warnings": _dedupe(warnings),
        "recommended_action": "Rerun the objective preview against current inputs." if stale_count else "Objective preview health is good.",
    }


def format_certified_rule_objective_preview_report(
    objective_preview_result_id: str | None = None,
    objective_preview_receipt_id: str | None = None,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    base = _ensure_dirs(root)
    receipt = _find_receipt_by_id(base, objective_preview_receipt_id) if objective_preview_receipt_id else None
    result = _find_result_by_id(base, objective_preview_result_id or str((receipt or {}).get("objective_preview_result_id") or ""))
    if not isinstance(result, Mapping):
        return "Certified Rule Objective Preview\n\nStatus: not_found"
    metrics = result.get("metrics") or {}
    lines = [
        "Certified Rule Objective Preview",
        "",
        f"Rule ID: {result.get('canonical_rule_id')}",
        f"Document: {result.get('document_id')}",
        f"Source Revision: {result.get('source_revision')}",
        f"Objective Pack ID: {result.get('objective_pack_id')}",
        f"Objective Outcome Persistence: {'available' if _result_supports_phase_9p(result) else 'unavailable'}",
        f"Phase 9P Compatibility: {'compatible' if _result_supports_phase_9p(result) else 'legacy_incompatible'}",
        f"Controlled Input ID: {result.get('controlled_input_id')}",
        f"Preview Status: {result.get('status')}",
        f"Total Records: {metrics.get('total_records', 0)}",
        f"Compared Records: {metrics.get('compared_records', 0)}",
        f"Improved Records: {metrics.get('improved_records', 0)}",
        f"Worsened Records: {metrics.get('worsened_records', 0)}",
        f"Mixed Records: {metrics.get('mixed_records', 0)}",
        f"Unsupported Records: {metrics.get('unsupported_records', 0)}",
        f"Preview Coverage: {_pct(metrics.get('preview_coverage'))}",
        f"Compatibility Rate: {_pct(metrics.get('compatibility_rate'))}",
        f"Objective Change Rate: {_pct(metrics.get('objective_change_rate'))}",
        f"Baseline Outcome Count: {sum(1 for item in list(result.get('per_record_results', []) or []) if isinstance((item or {}).get('baseline_objective_outcomes'), Mapping))}",
        f"Rule-Enabled Outcome Count: {sum(1 for item in list(result.get('per_record_results', []) or []) if isinstance((item or {}).get('rule_enabled_objective_outcomes'), Mapping))}",
        f"Stale: {'Yes' if _result_is_stale(base, result) else 'No'}",
        "Preview Mode: shadow_read_only",
        "Production Safety: no scoring, Fast Lane, active-rule, objective-pack, or production output was modified.",
        "Interpretation: objective preview is read-only and is not a production score or profitability result.",
    ]
    if not _result_supports_phase_9p(result):
        lines.append("Compatibility Blocker: legacy_objective_preview_result")
    if not public_safe:
        lines.append(f"Result Fingerprint: {result.get('result_fingerprint')}")
    return "\n".join(lines)


def get_certified_rule_objective_preview_summary(
    objective_preview_plan_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    plan = _read_json(_plan_path(base, objective_preview_plan_id))
    result = _find_result(base, objective_preview_plan_id)
    metrics = dict((result or {}).get("metrics") or {})
    return {
        "objective_preview_plan_id": objective_preview_plan_id,
        "canonical_rule_id": (plan or {}).get("canonical_rule_id"),
        "objective_pack_id": (plan or {}).get("objective_pack_id"),
        "controlled_input_id": (plan or {}).get("controlled_input_id"),
        "status": (result or {}).get("status", "not_run"),
        "total_records": metrics.get("total_records", 0),
        "compared_records": metrics.get("compared_records", 0),
        "improved_records": metrics.get("improved_records", 0),
        "worsened_records": metrics.get("worsened_records", 0),
        "recommended_action": "Run the read-only objective preview." if result is None else "Review the public-safe objective preview report.",
    }


def _ensure_dirs(root: Path | str) -> Path:
    base = _ensure_analysis_dirs(root)
    for folder in (PLAN_DIR, RESULT_DIR, RECEIPT_DIR, "indexes"):
        (base / folder).mkdir(parents=True, exist_ok=True)
    defaults = (
        (PLAN_INDEX, "certified_rule_objective_preview_plan_index_v1"),
        (RESULT_INDEX, "certified_rule_objective_preview_result_index_v1"),
        (RECEIPT_INDEX, "certified_rule_objective_preview_receipt_index_v1"),
    )
    for name, schema in defaults:
        path = base / "indexes" / name
        if not path.exists():
            analysis_backend._atomic_write_json(path, {"schema_version": schema, "items": [], "updated_at_utc": analysis_backend._now()})
    return base


def _validate_effect_mapping(effect_mapping: Mapping[str, Any], objective_pack: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    if not isinstance(effect_mapping, Mapping):
        return ["effect_mapping_invalid"]
    if str(effect_mapping.get("mapping_version") or "") != "rule_effect_mapping_v1":
        blockers.append("effect_mapping_schema_unsupported")
    field_types = _objective_field_types(objective_pack)
    protected = {"record_id", "timestamp", "document_id", "source_revision", "source_metadata"}
    for branch in ("on_match", "on_no_match"):
        payload = effect_mapping.get(branch)
        if payload is None:
            continue
        if not isinstance(payload, Mapping):
            blockers.append(f"{branch}_mapping_invalid")
            continue
        mode = str(payload.get("mode") or "")
        values = payload.get("values")
        if mode and mode != "preserve_baseline":
            blockers.append(f"{branch}_mode_unsupported")
        if values is not None:
            if not isinstance(values, Mapping):
                blockers.append(f"{branch}_values_invalid")
                continue
            for field, value in values.items():
                name = str(field or "")
                if name in protected:
                    blockers.append(f"{branch}_field_protected:{name}")
                    continue
                declared = field_types.get(name)
                if declared is None:
                    blockers.append(f"{branch}_field_not_declared:{name}")
                    continue
                if not _mapping_value_matches_type(value, declared):
                    blockers.append(f"{branch}_field_type_invalid:{name}")
    return _dedupe(blockers)


def _mapping_value_matches_type(value: Any, declared: Mapping[str, Any]) -> bool:
    value_type = str(declared.get("value_type") or "")
    enum_values = list(declared.get("enum_values") or [])
    if value_type == "boolean":
        return isinstance(value, bool)
    if value_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if value_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if value_type == "string":
        return isinstance(value, str)
    if value_type == "enum":
        return isinstance(value, str) and value in enum_values
    if value_type == "timestamp":
        return isinstance(value, str) and bool(value.strip())
    return False


def _objective_field_types(objective_pack: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for objective in list(objective_pack.get("objectives", []) or []):
        if not isinstance(objective, Mapping):
            continue
        field = str(objective.get("input_field") or "")
        if field and field not in mapping:
            mapping[field] = {"value_type": objective.get("value_type"), "enum_values": list(objective.get("enum_values") or [])}
    return mapping


def _effect_mapping_fingerprint(effect_mapping: Mapping[str, Any]) -> str:
    return _hash_payload(effect_mapping)


def _build_controlled_input(record: Mapping[str, Any]) -> dict[str, Any]:
    values = record.get("evaluation_context")
    if not isinstance(values, Mapping):
        values = record.get("values")
    if not isinstance(values, Mapping):
        values = record.get("context")
    return {
        "schema_version": INPUT_SCHEMA_VERSION,
        "record_id": str(record.get("record_id") or ""),
        "timestamp": record.get("timestamp"),
        "values": deepcopy(dict(values or {})),
    }


def _apply_effect_mapping(values: dict[str, Any], effect_mapping: Mapping[str, Any], *, branch: str) -> None:
    payload = effect_mapping.get(branch)
    if not isinstance(payload, Mapping):
        return
    if str(payload.get("mode") or "") == "preserve_baseline":
        return
    for key, value in dict(payload.get("values") or {}).items():
        values[str(key)] = deepcopy(value)


def _compare_objective_results(baseline: Mapping[str, Any], preview: Mapping[str, Any]) -> list[dict[str, Any]]:
    base_items = {str(item.get("objective_id") or ""): dict(item) for item in list(baseline.get("objective_results", []) or []) if isinstance(item, Mapping)}
    prev_items = {str(item.get("objective_id") or ""): dict(item) for item in list(preview.get("objective_results", []) or []) if isinstance(item, Mapping)}
    ordered = [str(item.get("objective_id") or "") for item in list(baseline.get("objective_results", []) or []) if isinstance(item, Mapping)]
    comparisons: list[dict[str, Any]] = []
    for objective_id in ordered:
        base_item = base_items.get(objective_id) or {}
        prev_item = prev_items.get(objective_id) or {}
        base_status = str(base_item.get("status") or "")
        prev_status = str(prev_item.get("status") or "")
        base_sat = base_item.get("satisfied")
        prev_sat = prev_item.get("satisfied")
        if base_status == "evaluator_error" or prev_status == "evaluator_error":
            cls = "evaluator_error"
        elif base_status not in {"satisfied", "not_satisfied"}:
            cls = "baseline_unsupported"
        elif prev_status not in {"satisfied", "not_satisfied"}:
            cls = "preview_unsupported"
        elif base_sat is True and prev_sat is True:
            cls = "unchanged_satisfied"
        elif base_sat is False and prev_sat is False:
            cls = "unchanged_unsatisfied"
        elif base_sat is False and prev_sat is True:
            cls = "newly_satisfied"
        else:
            cls = "newly_unsatisfied"
        comparisons.append({"objective_id": objective_id, "baseline_status": base_status, "preview_status": prev_status, "baseline_satisfied": base_sat, "preview_satisfied": prev_sat, "comparison": cls})
    return comparisons


def _classify_record(record_objectives: list[dict[str, Any]]) -> str:
    if any(str(item.get("comparison") or "") == "evaluator_error" for item in record_objectives):
        return "objective_evaluator_error"
    if any(str(item.get("comparison") or "") in {"baseline_unsupported", "preview_unsupported"} for item in record_objectives):
        return "unsupported"
    improved = any(str(item.get("comparison") or "") == "newly_satisfied" for item in record_objectives)
    worsened = any(str(item.get("comparison") or "") == "newly_unsatisfied" for item in record_objectives)
    if improved and worsened:
        return "mixed_objective_change"
    if improved:
        return "objective_improved"
    if worsened:
        return "objective_worsened"
    return "unchanged"


def _plan_current_status(base: Path, plan: Mapping[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    rule_loaded = load_canonical_rule(str(plan.get("canonical_rule_id") or ""), require_active=True, root=base)
    rule = rule_loaded.get("rule")
    if rule_loaded.get("status") != "loaded" or not isinstance(rule, Mapping):
        blockers.append("canonical_rule_not_active")
    certification = _load_certification_receipt_for_rule(base, str(plan.get("canonical_rule_id") or ""))
    if not isinstance(certification, Mapping):
        blockers.append("rule_certification_missing")
    elif str(plan.get("certification_fingerprint") or "") != _certification_fingerprint(certification):
        blockers.append("certification_fingerprint_changed")
    try:
        objective_pack = load_objective_pack(str(plan.get("objective_pack_id") or ""), root=base / "objective_packs")
    except Exception:
        objective_pack = None
    if not isinstance(objective_pack, Mapping):
        blockers.append("objective_pack_missing")
    else:
        if str(plan.get("objective_pack_fingerprint") or "") != get_objective_pack_evaluation_fingerprint(objective_pack):
            blockers.append("objective_pack_fingerprint_changed")
    dataset = _load_replay_dataset(base, str(plan.get("controlled_input_id") or ""))
    if not isinstance(dataset, Mapping):
        blockers.append("controlled_input_missing")
    elif str(plan.get("controlled_input_fingerprint") or "") != str(_dataset_fingerprint(dataset)):
        blockers.append("controlled_input_fingerprint_changed")
    manifest = load_document_manifest(str(plan.get("document_id") or ""), root=base).get("manifest")
    if isinstance(manifest, Mapping) and str(plan.get("source_revision") or "") != str(manifest.get("source_revision") or ""):
        blockers.append("source_revision_changed")
    if str(plan.get("rule_evaluator_fingerprint") or "") != _rule_evaluator_fingerprint():
        blockers.append("rule_evaluator_fingerprint_changed")
    if str(plan.get("objective_evaluator_fingerprint") or "") != get_objective_evaluator_fingerprint():
        blockers.append("objective_evaluator_fingerprint_changed")
    if str(plan.get("effect_mapping_fingerprint") or "") != _effect_mapping_fingerprint(dict(plan.get("effect_mapping") or {})):
        blockers.append("effect_mapping_fingerprint_changed")
    if isinstance(rule, Mapping) and isinstance(certification, Mapping) and isinstance(objective_pack, Mapping) and isinstance(dataset, Mapping):
        expected_plan_fingerprint = _hash_payload({
            "rule": _hash_payload(rule),
            "certification": _certification_fingerprint(certification),
            "objective_pack": get_objective_pack_evaluation_fingerprint(objective_pack),
            "controlled_input": _dataset_fingerprint(dataset),
            "effect_mapping": _effect_mapping_fingerprint(dict(plan.get("effect_mapping") or {})),
            "record_count": int(plan.get("bounded_record_count") or 0),
            "max_records": int(plan.get("record_limit") or 0),
            "rule_evaluator": _rule_evaluator_fingerprint(),
            "objective_evaluator": get_objective_evaluator_fingerprint(),
            "schema": PREVIEW_SCHEMA_VERSION,
        })
        if str(plan.get("plan_fingerprint") or "") != expected_plan_fingerprint:
            blockers.append("plan_fingerprint_changed")
    if str(plan.get("preview_mode") or "") != "shadow_read_only":
        blockers.append("preview_mode_changed")
    if str(plan.get("preview_schema_version") or "") != PREVIEW_SCHEMA_VERSION:
        blockers.append("preview_schema_changed")
    return {"status": "current" if not blockers else "stale", "blockers": blockers}


def _result_is_stale(base: Path, result: Mapping[str, Any]) -> bool:
    plan = _read_json(_plan_path(base, str(result.get("objective_preview_plan_id") or "")))
    if not isinstance(plan, Mapping):
        return True
    current = _plan_current_status(base, plan)
    return current["status"] != "current" or str(result.get("result_fingerprint") or "") != _result_fingerprint(plan, list(result.get("per_record_results", []) or []), list(result.get("per_objective_comparisons", []) or []), dict(result.get("metrics") or {}), str(result.get("status") or ""))


def _find_plan(base: Path, canonical_rule_id: str, objective_pack_id: str, controlled_input_id: str) -> dict[str, Any] | None:
    for item in _load_all_plans(base):
        if str(item.get("canonical_rule_id") or "") == canonical_rule_id and str(item.get("objective_pack_id") or "") == objective_pack_id and str(item.get("controlled_input_id") or "") == controlled_input_id:
            return item
    return None


def _find_result(base: Path, objective_preview_plan_id: str, *, require_phase_9p_compatible: bool = False) -> dict[str, Any] | None:
    legacy: dict[str, Any] | None = None
    for item in _load_all_results(base):
        if str(item.get("objective_preview_plan_id") or "") == objective_preview_plan_id:
            if _result_supports_phase_9p(item):
                return item
            legacy = item
    return None if require_phase_9p_compatible else legacy


def _find_result_by_id(base: Path, objective_preview_result_id: str | None) -> dict[str, Any] | None:
    if not objective_preview_result_id:
        return None
    payload = _read_json(_result_path(base, objective_preview_result_id))
    return dict(payload) if isinstance(payload, Mapping) else None


def _find_receipt_for_result(base: Path, objective_preview_result_id: str) -> dict[str, Any] | None:
    for item in _load_all_receipts(base):
        if str(item.get("objective_preview_result_id") or "") == objective_preview_result_id:
            return item
    return None


def _find_receipt_by_id(base: Path, objective_preview_receipt_id: str | None) -> dict[str, Any] | None:
    if not objective_preview_receipt_id:
        return None
    payload = _read_json(_receipt_path(base, objective_preview_receipt_id))
    return dict(payload) if isinstance(payload, Mapping) else None


def _load_all_plans(base: Path) -> list[dict[str, Any]]:
    return _load_dir_json(base / PLAN_DIR, "objective_preview_plan_id")


def _load_all_results(base: Path) -> list[dict[str, Any]]:
    return _load_dir_json(base / RESULT_DIR, "objective_preview_result_id")


def _load_all_receipts(base: Path) -> list[dict[str, Any]]:
    return _load_dir_json(base / RECEIPT_DIR, "objective_preview_receipt_id")


def _update_plan_index(base: Path) -> None:
    items = [{"objective_preview_plan_id": item.get("objective_preview_plan_id"), "canonical_rule_id": item.get("canonical_rule_id"), "objective_pack_id": item.get("objective_pack_id"), "controlled_input_id": item.get("controlled_input_id"), "document_id": item.get("document_id"), "source_revision": item.get("source_revision")} for item in _load_all_plans(base)]
    analysis_backend._atomic_write_json(base / "indexes" / PLAN_INDEX, {"schema_version": "certified_rule_objective_preview_plan_index_v1", "items": sorted(items, key=lambda item: str(item.get("objective_preview_plan_id") or "")), "updated_at_utc": analysis_backend._now()})


def _update_result_index(base: Path) -> None:
    items = [{"objective_preview_result_id": item.get("objective_preview_result_id"), "objective_preview_plan_id": item.get("objective_preview_plan_id"), "canonical_rule_id": item.get("canonical_rule_id"), "status": item.get("status")} for item in _load_all_results(base)]
    analysis_backend._atomic_write_json(base / "indexes" / RESULT_INDEX, {"schema_version": "certified_rule_objective_preview_result_index_v1", "items": sorted(items, key=lambda item: str(item.get("objective_preview_result_id") or "")), "updated_at_utc": analysis_backend._now()})


def _update_receipt_index(base: Path) -> None:
    items = [{"objective_preview_receipt_id": item.get("objective_preview_receipt_id"), "objective_preview_result_id": item.get("objective_preview_result_id"), "objective_preview_plan_id": item.get("objective_preview_plan_id"), "final_status": item.get("final_status")} for item in _load_all_receipts(base)]
    analysis_backend._atomic_write_json(base / "indexes" / RECEIPT_INDEX, {"schema_version": "certified_rule_objective_preview_receipt_index_v1", "items": sorted(items, key=lambda item: str(item.get("objective_preview_receipt_id") or "")), "updated_at_utc": analysis_backend._now()})


def _load_dir_json(folder: Path, required_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not folder.exists():
        return items
    for path in sorted(folder.glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping) and payload.get(required_id):
            items.append(dict(payload))
    return items


def _plan_id(canonical_rule_id: str, objective_pack_id: str, controlled_input_id: str, max_records: int, rule: Mapping[str, Any], certification: Mapping[str, Any], objective_pack: Mapping[str, Any], dataset: Mapping[str, Any], mapping_fingerprint: str) -> str:
    return f"certified_rule_objective_preview_plan_{_hash_payload({'rule_id': canonical_rule_id, 'objective_pack_id': objective_pack_id, 'controlled_input_id': controlled_input_id, 'max_records': max_records, 'rule': _hash_payload(rule), 'cert': _certification_fingerprint(certification), 'objective_pack': get_objective_pack_evaluation_fingerprint(objective_pack), 'controlled_input': _dataset_fingerprint(dataset), 'mapping': mapping_fingerprint, 'rule_eval': _rule_evaluator_fingerprint(), 'objective_eval': get_objective_evaluator_fingerprint(), 'schema': PREVIEW_SCHEMA_VERSION})[7:23]}"


def _result_id(plan_id: str, plan: Mapping[str, Any]) -> str:
    return f"certified_rule_objective_preview_result_{_hash_payload({'objective_preview_plan_id': plan_id, 'plan_fingerprint': plan.get('plan_fingerprint'), 'objective_outcome_persistence': OBJECTIVE_OUTCOME_PERSISTENCE, 'result_schema': RESULT_SCHEMA})[7:23]}"


def _receipt_id(result_id: str) -> str:
    return f"certified_rule_objective_preview_receipt_{_hash_payload({'result_id': result_id})[7:23]}"


def _rule_evaluator_fingerprint() -> str:
    return _hash_payload({"evaluator": "canonical_rule_runtime.evaluate_canonical_rule", "schema": "canonical_single_rule_evaluation_v1"})


def _certification_fingerprint(receipt: Mapping[str, Any]) -> str:
    return _hash_payload({
        "certification_receipt_id": receipt.get("certification_receipt_id"),
        "rule_id": receipt.get("rule_id"),
        "rule_hash": receipt.get("rule_hash"),
        "certification_status": receipt.get("certification_status"),
    })


def _persistable_objective_outcomes(result: Mapping[str, Any], record_id: str) -> dict[str, Any]:
    payload = deepcopy(dict(result))
    payload["record_id"] = record_id
    payload["objective_pack_evaluation_fingerprint"] = payload.get("objective_pack_fingerprint")
    return payload


def _result_fingerprint(
    plan: Mapping[str, Any],
    per_record_results: list[dict[str, Any]],
    per_objective_comparisons: list[dict[str, Any]],
    metrics: Mapping[str, Any],
    status: str,
) -> str:
    return _hash_payload({
        "plan": plan.get("plan_fingerprint"),
        "result_schema": RESULT_SCHEMA,
        "objective_outcome_persistence": OBJECTIVE_OUTCOME_PERSISTENCE,
        "metrics": metrics,
        "records": per_record_results,
        "objectives": per_objective_comparisons,
        "status": status,
    })


def _result_supports_phase_9p(result: Mapping[str, Any]) -> bool:
    if str(result.get("objective_outcome_persistence") or "") != OBJECTIVE_OUTCOME_PERSISTENCE:
        return False
    records = list(result.get("per_record_results", []) or [])
    return bool(records) and all(
        isinstance(item, Mapping)
        and isinstance(item.get("baseline_objective_outcomes"), Mapping)
        and isinstance(item.get("rule_enabled_objective_outcomes"), Mapping)
        for item in records
    )


def _result_payload_count(result: Mapping[str, Any]) -> int:
    count = 0
    for item in list(result.get("per_record_results", []) or []):
        if isinstance((item or {}).get("baseline_objective_outcomes"), Mapping):
            count += 1
        if isinstance((item or {}).get("rule_enabled_objective_outcomes"), Mapping):
            count += 1
    return count


def _compatibility_warnings(result: Mapping[str, Any]) -> list[str]:
    warnings: list[str] = []
    if not _result_supports_phase_9p(result):
        return warnings
    objective_pack_id = str(result.get("objective_pack_id") or "")
    objective_pack_fingerprint = str(result.get("objective_pack_fingerprint") or "")
    evaluator_fingerprint = str(result.get("objective_evaluator_fingerprint") or "")
    for record in list(result.get("per_record_results", []) or []):
        if not isinstance(record, Mapping):
            continue
        record_id = str(record.get("record_id") or "")
        baseline = record.get("baseline_objective_outcomes")
        preview = record.get("rule_enabled_objective_outcomes")
        if not isinstance(baseline, Mapping):
            warnings.append("persisted_objective_outcomes_missing")
            continue
        if not isinstance(preview, Mapping):
            warnings.append("persisted_objective_outcomes_missing")
            continue
        if str(baseline.get("record_id") or "") != record_id:
            warnings.append("baseline_record_id_mismatch")
        if str(preview.get("record_id") or "") != record_id:
            warnings.append("rule_enabled_record_id_mismatch")
        if str(baseline.get("objective_pack_id") or "") != objective_pack_id or str(preview.get("objective_pack_id") or "") != objective_pack_id:
            warnings.append("pack_id_mismatch")
        if str(baseline.get("objective_pack_evaluation_fingerprint") or "") != objective_pack_fingerprint or str(preview.get("objective_pack_evaluation_fingerprint") or "") != objective_pack_fingerprint:
            warnings.append("pack_fingerprint_mismatch")
        if str(baseline.get("objective_evaluator_fingerprint") or "") != evaluator_fingerprint or str(preview.get("objective_evaluator_fingerprint") or "") != evaluator_fingerprint:
            warnings.append("evaluator_fingerprint_mismatch")
        base_ids = [str(item.get("objective_id") or "") for item in list(baseline.get("objective_results", []) or []) if isinstance(item, Mapping)]
        prev_ids = [str(item.get("objective_id") or "") for item in list(preview.get("objective_results", []) or []) if isinstance(item, Mapping)]
        if base_ids != prev_ids:
            warnings.append("objective_order_mismatch")
        if len(set(base_ids)) != len(base_ids) or len(set(prev_ids)) != len(prev_ids):
            warnings.append("duplicate_objective_ids")
        if not baseline.get("result_fingerprint") or not preview.get("result_fingerprint"):
            warnings.append("missing_objective_result_fingerprint")
    return _dedupe(warnings)


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(float(numerator) / float(denominator), 6)


def _pct(value: Any) -> str:
    return "null" if value is None else f"{float(value) * 100:.2f}%"


def _plan_path(base: Path, objective_preview_plan_id: str) -> Path:
    return base / PLAN_DIR / f"{analysis_backend._safe_id(objective_preview_plan_id)}.json"


def _result_path(base: Path, objective_preview_result_id: str) -> Path:
    return base / RESULT_DIR / f"{analysis_backend._safe_id(objective_preview_result_id)}.json"


def _receipt_path(base: Path, objective_preview_receipt_id: str) -> Path:
    return base / RECEIPT_DIR / f"{analysis_backend._safe_id(objective_preview_receipt_id)}.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    return benchmark_backend._read_json(path)


def _restore_json(path: Path, payload: dict[str, Any] | None) -> None:
    benchmark_backend._restore_json(path, payload)


def _dedupe(values: list[str]) -> list[str]:
    return remediation_backend._dedupe(values)
