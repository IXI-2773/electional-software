from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import deployed_rule_effectiveness_scoring_contract as scoring_contract_backend
from . import deployed_rule_outcome_truth_source as truth_backend

SOURCE_DOCUMENT_ROOT = Path("data/source_documents")
DRY_RUN_SCHEMA_VERSION = "deployed_rule_effectiveness_scoring_dry_run_v1"
MANIFEST_SCHEMA_VERSION = "deployed_rule_effectiveness_scoring_dry_run_manifest_v1"
DEFAULT_REQUESTED_METRIC_FAMILIES = (
    "accuracy_like_contract",
    "runtime_reliability_contract",
)

__all__ = [
    "get_deployed_rule_effectiveness_scoring_dry_run_manifest",
    "build_deployed_rule_effectiveness_scoring_dry_run_workspace",
    "validate_deployed_rule_effectiveness_scoring_dry_run_eligibility",
    "run_deployed_rule_effectiveness_scoring_dry_run",
    "format_deployed_rule_effectiveness_scoring_dry_run_report",
]


def get_deployed_rule_effectiveness_scoring_dry_run_manifest(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "dry_run_schema_version": DRY_RUN_SCHEMA_VERSION,
        "dry_run_only": True,
        "authoritative_result": False,
        "persistence_performed": False,
        "writes_performed": 0,
        "supported_default_metric_families": list(DEFAULT_REQUESTED_METRIC_FAMILIES),
        "root": str(root),
    }


def build_deployed_rule_effectiveness_scoring_dry_run_workspace(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result_id: str,
    effectiveness_spec_result_id: str,
    outcome_truth_source_result_id: str,
    outcome_truth_record_set_id: str,
    scoring_contract_result_id: str,
    observation_window_start: str,
    observation_window_end: str,
    *,
    requested_metric_families: Sequence[str] | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    context = _dry_run_context(
        canonical_rule_id=canonical_rule_id,
        production_deployment_result_id=production_deployment_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
        telemetry_snapshot_id=telemetry_snapshot_id,
        readiness_result_id=readiness_result_id,
        effectiveness_spec_result_id=effectiveness_spec_result_id,
        outcome_truth_source_result_id=outcome_truth_source_result_id,
        outcome_truth_record_set_id=outcome_truth_record_set_id,
        scoring_contract_result_id=scoring_contract_result_id,
        observation_window_start=observation_window_start,
        observation_window_end=observation_window_end,
        requested_metric_families=requested_metric_families,
        root=root,
    )
    return _workspace_payload(context)


def validate_deployed_rule_effectiveness_scoring_dry_run_eligibility(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result_id: str,
    effectiveness_spec_result_id: str,
    outcome_truth_source_result_id: str,
    outcome_truth_record_set_id: str,
    scoring_contract_result_id: str,
    observation_window_start: str,
    observation_window_end: str,
    *,
    requested_metric_families: Sequence[str] | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    context = _dry_run_context(
        canonical_rule_id=canonical_rule_id,
        production_deployment_result_id=production_deployment_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
        telemetry_snapshot_id=telemetry_snapshot_id,
        readiness_result_id=readiness_result_id,
        effectiveness_spec_result_id=effectiveness_spec_result_id,
        outcome_truth_source_result_id=outcome_truth_source_result_id,
        outcome_truth_record_set_id=outcome_truth_record_set_id,
        scoring_contract_result_id=scoring_contract_result_id,
        observation_window_start=observation_window_start,
        observation_window_end=observation_window_end,
        requested_metric_families=requested_metric_families,
        root=root,
    )
    return _eligibility_payload(context)


def run_deployed_rule_effectiveness_scoring_dry_run(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result_id: str,
    effectiveness_spec_result_id: str,
    outcome_truth_source_result_id: str,
    outcome_truth_record_set_id: str,
    scoring_contract_result_id: str,
    observation_window_start: str,
    observation_window_end: str,
    *,
    requested_metric_families: Sequence[str] | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    context = _dry_run_context(
        canonical_rule_id=canonical_rule_id,
        production_deployment_result_id=production_deployment_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
        telemetry_snapshot_id=telemetry_snapshot_id,
        readiness_result_id=readiness_result_id,
        effectiveness_spec_result_id=effectiveness_spec_result_id,
        outcome_truth_source_result_id=outcome_truth_source_result_id,
        outcome_truth_record_set_id=outcome_truth_record_set_id,
        scoring_contract_result_id=scoring_contract_result_id,
        observation_window_start=observation_window_start,
        observation_window_end=observation_window_end,
        requested_metric_families=requested_metric_families,
        root=root,
    )
    return _run_payload(context)


def format_deployed_rule_effectiveness_scoring_dry_run_report(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result_id: str,
    effectiveness_spec_result_id: str,
    outcome_truth_source_result_id: str,
    outcome_truth_record_set_id: str,
    scoring_contract_result_id: str,
    observation_window_start: str,
    observation_window_end: str,
    *,
    requested_metric_families: Sequence[str] | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    result = run_deployed_rule_effectiveness_scoring_dry_run(
        canonical_rule_id,
        production_deployment_result_id,
        production_target_id,
        deployed_rule_id,
        telemetry_snapshot_id,
        readiness_result_id,
        effectiveness_spec_result_id,
        outcome_truth_source_result_id,
        outcome_truth_record_set_id,
        scoring_contract_result_id,
        observation_window_start,
        observation_window_end,
        requested_metric_families=requested_metric_families,
        root=root,
    )
    accuracy = result.get("candidate_accuracy_like_summary", {})
    lines = [
        "Deployed Rule Effectiveness Scoring Dry Run",
        f"Dry-run status: {result.get('status')}",
        "This is a dry run only.",
        "No authoritative effectiveness score was persisted.",
        "No production correctness result was produced.",
        "Dry-run candidate metrics are non-authoritative.",
        "Candidate metrics are not final.",
        "This dry run creates no deployment safety claim.",
        "Runtime completion is not correctness.",
        "Phase 9W acceptance is not scoring input.",
        "Source availability is not effectiveness.",
        "No API or desktop seam exists yet for this dry-run layer.",
        "Future persisted scoring result remains a later phase.",
        f"Requested metric families: {', '.join(result.get('requested_metric_families', [])) or 'none'}",
        f"Eligible record count: {result.get('eligible_record_count', 0)}",
        f"Excluded record count: {result.get('excluded_record_count', 0)}",
        f"Duplicate collapsed count: {result.get('duplicate_collapsed_count', 0)}",
        f"Conflict count: {result.get('conflict_count', 0)}",
        f"Candidate exact match count: {accuracy.get('candidate_exact_match_count', 0)}",
        f"Candidate mismatch count: {accuracy.get('candidate_mismatch_count', 0)}",
        f"Candidate denominator count: {accuracy.get('candidate_denominator_count', 0)}",
        f"Candidate accuracy ratio: {accuracy.get('candidate_accuracy_ratio', 'not_calculated')}",
        f"Candidate accuracy percentage: {accuracy.get('candidate_accuracy_percentage', 'not_calculated')}",
    ]
    metric_results = result.get("metric_family_results", {})
    if isinstance(metric_results, Mapping):
        for metric_name in sorted(metric_results):
            item = metric_results.get(metric_name)
            if not isinstance(item, Mapping):
                continue
            lines.append(f"{metric_name}: {item.get('status')}")
            if item.get("unsupported_reason"):
                lines.append(f"{metric_name} reason: {item.get('unsupported_reason')}")
    blockers = result.get("blockers", [])
    warnings = result.get("warnings", [])
    if isinstance(blockers, list) and blockers:
        lines.append("Blockers: " + ", ".join(str(item) for item in blockers))
    if isinstance(warnings, list) and warnings:
        lines.append("Warnings: " + ", ".join(str(item) for item in warnings))
    lines.append("Recommended next step: " + str(result.get("recommended_action") or "Resolve dry-run blockers before any later persisted scoring phase."))
    return "\n".join(lines)


def _dry_run_context(
    *,
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result_id: str,
    effectiveness_spec_result_id: str,
    outcome_truth_source_result_id: str,
    outcome_truth_record_set_id: str,
    scoring_contract_result_id: str,
    observation_window_start: str,
    observation_window_end: str,
    requested_metric_families: Sequence[str] | None,
    root: Path | str,
) -> dict[str, Any]:
    metric_families = _requested_metric_families(requested_metric_families)
    scoring_loaded = scoring_contract_backend.load_deployed_rule_effectiveness_scoring_contract_result(
        scoring_contract_result_id,
        root=root,
    )
    scoring_result = scoring_loaded.get("effectiveness_scoring_contract_result") if isinstance(scoring_loaded, Mapping) and isinstance(scoring_loaded.get("effectiveness_scoring_contract_result"), Mapping) else None
    truth_loaded = truth_backend.load_deployed_rule_outcome_truth_record_set(
        outcome_truth_record_set_id,
        root=root,
    )
    truth_set = truth_loaded.get("outcome_truth_record_set") if isinstance(truth_loaded, Mapping) and isinstance(truth_loaded.get("outcome_truth_record_set"), Mapping) else None
    truth_records = list(truth_loaded.get("outcome_truth_records", [])) if isinstance(truth_loaded, Mapping) else []
    blockers: list[str] = []
    warnings: list[str] = []
    exclusion_reasons: dict[str, int] = {}
    conflict_details: list[str] = []

    if not isinstance(scoring_result, Mapping):
        blockers.append("scoring_contract_result_missing")
    else:
        expected_bindings = {
            "canonical_rule_id": canonical_rule_id,
            "production_deployment_result_id": production_deployment_result_id,
            "production_target_id": production_target_id,
            "deployed_rule_id": deployed_rule_id,
            "telemetry_snapshot_id": telemetry_snapshot_id,
            "readiness_result_id": readiness_result_id,
            "effectiveness_spec_result_id": effectiveness_spec_result_id,
            "outcome_truth_source_result_id": outcome_truth_source_result_id,
            "outcome_truth_record_set_id": outcome_truth_record_set_id,
            "observation_window_start": observation_window_start,
            "observation_window_end": observation_window_end,
        }
        for key, expected in expected_bindings.items():
            if str(scoring_result.get(key) or "") != expected:
                blockers.append(f"scoring_contract_result_binding_mismatch:{key}")
        if str(scoring_result.get("scoring_contract_status") or "") != "scoring_contract_ready_for_engine_design":
            blockers.append("scoring_contract_result_not_ready_for_dry_run")

    if not isinstance(truth_set, Mapping):
        blockers.append("outcome_truth_record_set_missing")

    eligible_records: list[dict[str, Any]] = []
    duplicate_collapsed_count = 0
    comparable_records: list[dict[str, Any]] = []
    comparable_excluded_count = 0
    exact_match_count = 0
    mismatch_count = 0
    metric_family_results: dict[str, dict[str, Any]] = {}

    if not blockers:
        selected = _select_eligible_records(
            truth_records=truth_records,
            expected_bindings={
                "canonical_rule_id": canonical_rule_id,
                "production_deployment_result_id": production_deployment_result_id,
                "production_target_id": production_target_id,
                "deployed_rule_id": deployed_rule_id,
                "telemetry_snapshot_id": telemetry_snapshot_id,
                "outcome_truth_record_set_id": outcome_truth_record_set_id,
                "observation_window_start": observation_window_start,
                "observation_window_end": observation_window_end,
            },
        )
        eligible_records = selected["eligible_records"]
        duplicate_collapsed_count = selected["duplicate_collapsed_count"]
        exclusion_reasons = selected["exclusion_reasons"]
        conflict_details = selected["conflict_details"]
        if conflict_details:
            blockers.append("conflicting_execution_binding")
        if conflict_details:
            metric_family_results = _conflict_metric_family_results(metric_families)
        else:
            comparable_records, comparable_excluded = _comparable_records(eligible_records)
            comparable_excluded_count = comparable_excluded
            exact_match_count, mismatch_count = _exact_match_counts(comparable_records)
            metric_family_results = _metric_family_results(
                requested_metric_families=metric_families,
                scoring_result=scoring_result or {},
                comparable_records=comparable_records,
                exact_match_count=exact_match_count,
                mismatch_count=mismatch_count,
                comparable_excluded_count=comparable_excluded_count,
            )
            unsupported_blockers = [
                f"{name}:{payload.get('unsupported_reason')}"
                for name, payload in metric_family_results.items()
                if isinstance(payload, Mapping) and payload.get("status") == "blocked_unsupported"
            ]
            warnings.extend(unsupported_blockers)

    status = "dry_run_ready"
    if blockers:
        status = "blocked"
    elif any(
        isinstance(payload, Mapping) and payload.get("status") == "blocked_conflict"
        for payload in metric_family_results.values()
    ):
        status = "conflict"

    return {
        "status": status,
        "canonical_rule_id": canonical_rule_id,
        "production_deployment_result_id": production_deployment_result_id,
        "production_target_id": production_target_id,
        "deployed_rule_id": deployed_rule_id,
        "telemetry_snapshot_id": telemetry_snapshot_id,
        "readiness_result_id": readiness_result_id,
        "effectiveness_spec_result_id": effectiveness_spec_result_id,
        "outcome_truth_source_result_id": outcome_truth_source_result_id,
        "outcome_truth_record_set_id": outcome_truth_record_set_id,
        "scoring_contract_result_id": scoring_contract_result_id,
        "observation_window_start": observation_window_start,
        "observation_window_end": observation_window_end,
        "requested_metric_families": metric_families,
        "eligible_records": eligible_records,
        "eligible_record_count": len(eligible_records),
        "excluded_record_count": sum(exclusion_reasons.values()),
        "duplicate_collapsed_count": duplicate_collapsed_count,
        "conflict_count": len(conflict_details),
        "exclusion_reasons": exclusion_reasons,
        "conflict_details": conflict_details,
        "comparable_records": comparable_records,
        "metric_family_results": metric_family_results,
        "candidate_accuracy_like_summary": {
            "candidate_exact_match_count": exact_match_count,
            "candidate_mismatch_count": mismatch_count,
            "candidate_denominator_count": len(comparable_records),
            "candidate_accuracy_ratio": _ratio(exact_match_count, len(comparable_records)),
            "candidate_accuracy_percentage": _percentage(exact_match_count, len(comparable_records)),
            "calculation_scope": "dry_run_only",
        },
        "blockers": _dedupe(blockers),
        "warnings": _dedupe(warnings),
        "recommended_action": _recommended_action(status),
    }


def _workspace_payload(context: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": DRY_RUN_SCHEMA_VERSION,
        "status": context["status"],
        "dry_run_only": True,
        "authoritative_result": False,
        "persistence_performed": False,
        "writes_performed": 0,
        "requested_metric_families": list(context["requested_metric_families"]),
        "eligible_record_count": context["eligible_record_count"],
        "excluded_record_count": context["excluded_record_count"],
        "duplicate_collapsed_count": context["duplicate_collapsed_count"],
        "conflict_count": context["conflict_count"],
        "exclusion_reasons": dict(context["exclusion_reasons"]),
        "metric_family_results": deepcopy(context["metric_family_results"]),
        "candidate_accuracy_like_summary": deepcopy(context["candidate_accuracy_like_summary"]),
        "blockers": list(context["blockers"]),
        "warnings": list(context["warnings"]),
        "recommended_action": context["recommended_action"],
    }


def _eligibility_payload(context: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": context["status"],
        "dry_run_only": True,
        "authoritative_result": False,
        "persistence_performed": False,
        "writes_performed": 0,
        "requested_metric_families": list(context["requested_metric_families"]),
        "eligible_record_count": context["eligible_record_count"],
        "excluded_record_count": context["excluded_record_count"],
        "duplicate_collapsed_count": context["duplicate_collapsed_count"],
        "conflict_count": context["conflict_count"],
        "exclusion_reasons": dict(context["exclusion_reasons"]),
        "metric_family_results": deepcopy(context["metric_family_results"]),
        "blockers": list(context["blockers"]),
        "warnings": list(context["warnings"]),
        "recommended_action": context["recommended_action"],
    }


def _run_payload(context: Mapping[str, Any]) -> dict[str, Any]:
    fingerprint_payload = {
        "canonical_rule_id": context["canonical_rule_id"],
        "production_deployment_result_id": context["production_deployment_result_id"],
        "production_target_id": context["production_target_id"],
        "deployed_rule_id": context["deployed_rule_id"],
        "telemetry_snapshot_id": context["telemetry_snapshot_id"],
        "readiness_result_id": context["readiness_result_id"],
        "effectiveness_spec_result_id": context["effectiveness_spec_result_id"],
        "outcome_truth_source_result_id": context["outcome_truth_source_result_id"],
        "outcome_truth_record_set_id": context["outcome_truth_record_set_id"],
        "scoring_contract_result_id": context["scoring_contract_result_id"],
        "observation_window_start": context["observation_window_start"],
        "observation_window_end": context["observation_window_end"],
        "requested_metric_families": list(context["requested_metric_families"]),
        "eligible_record_fingerprints": [item.get("record_fingerprint") for item in context["eligible_records"]],
        "candidate_accuracy_like_summary": context["candidate_accuracy_like_summary"],
    }
    fingerprint = _hash_payload(fingerprint_payload)
    return {
        "schema_version": DRY_RUN_SCHEMA_VERSION,
        "status": context["status"],
        "dry_run_id": f"deployed_rule_effectiveness_scoring_dry_run_{fingerprint[:24]}",
        "dry_run_fingerprint": fingerprint,
        "dry_run_only": True,
        "authoritative_result": False,
        "persistence_performed": False,
        "writes_performed": 0,
        "canonical_rule_id": context["canonical_rule_id"],
        "production_deployment_result_id": context["production_deployment_result_id"],
        "production_target_id": context["production_target_id"],
        "deployed_rule_id": context["deployed_rule_id"],
        "telemetry_snapshot_id": context["telemetry_snapshot_id"],
        "readiness_result_id": context["readiness_result_id"],
        "effectiveness_spec_result_id": context["effectiveness_spec_result_id"],
        "outcome_truth_source_result_id": context["outcome_truth_source_result_id"],
        "outcome_truth_record_set_id": context["outcome_truth_record_set_id"],
        "scoring_contract_result_id": context["scoring_contract_result_id"],
        "observation_window_start": context["observation_window_start"],
        "observation_window_end": context["observation_window_end"],
        "requested_metric_families": list(context["requested_metric_families"]),
        "eligible_record_count": context["eligible_record_count"],
        "excluded_record_count": context["excluded_record_count"],
        "duplicate_collapsed_count": context["duplicate_collapsed_count"],
        "conflict_count": context["conflict_count"],
        "exclusion_reasons": dict(context["exclusion_reasons"]),
        "metric_family_results": deepcopy(context["metric_family_results"]),
        "candidate_accuracy_like_summary": deepcopy(context["candidate_accuracy_like_summary"]),
        "blockers": list(context["blockers"]),
        "warnings": list(context["warnings"]),
        "recommended_action": context["recommended_action"],
        "no_persistence_confirmation": "dry_run_only_no_authoritative_result_persisted",
    }


def _requested_metric_families(requested: Sequence[str] | None) -> list[str]:
    values = list(requested) if requested else list(DEFAULT_REQUESTED_METRIC_FAMILIES)
    normalized = [str(item).strip() for item in values if str(item).strip()]
    seen: set[str] = set()
    ordered: list[str] = []
    for item in normalized:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _select_eligible_records(*, truth_records: Sequence[Mapping[str, Any]], expected_bindings: Mapping[str, str]) -> dict[str, Any]:
    exclusion_reasons: dict[str, int] = {}
    eligible: list[dict[str, Any]] = []
    seen_fingerprints: set[str] = set()
    binding_map: dict[str, tuple[Any, Any, str]] = {}
    duplicate_collapsed_count = 0
    conflict_details: list[str] = []

    def exclude(reason: str) -> None:
        exclusion_reasons[reason] = exclusion_reasons.get(reason, 0) + 1

    for raw in truth_records:
        record = dict(raw) if isinstance(raw, Mapping) else {}
        if str(record.get("outcome_truth_record_set_id") or "") != expected_bindings["outcome_truth_record_set_id"]:
            exclude("record_set_id_mismatch")
            continue
        if str(record.get("canonical_rule_id") or "") != expected_bindings["canonical_rule_id"]:
            exclude("canonical_rule_id_mismatch")
            continue
        if str(record.get("production_deployment_result_id") or "") != expected_bindings["production_deployment_result_id"]:
            exclude("production_deployment_result_id_mismatch")
            continue
        if str(record.get("production_target_id") or "") != expected_bindings["production_target_id"]:
            exclude("production_target_id_mismatch")
            continue
        if str(record.get("deployed_rule_id") or "") != expected_bindings["deployed_rule_id"]:
            exclude("deployed_rule_id_mismatch")
            continue
        if str(record.get("telemetry_snapshot_id") or "") != expected_bindings["telemetry_snapshot_id"]:
            exclude("telemetry_snapshot_id_mismatch")
            continue
        if not str(record.get("source_id") or "").strip() or not str(record.get("source_fingerprint") or "").strip():
            exclude("source_identity_or_fingerprint_missing")
            continue
        if record.get("expected_outcome") is None:
            exclude("missing_expected_outcome")
            continue
        if record.get("actual_or_adjudicated_outcome") is None:
            exclude("missing_actual_or_adjudicated_outcome")
            continue
        execution_event_id = str(record.get("execution_event_id") or "").strip()
        input_fingerprint = str(record.get("input_fingerprint") or "").strip()
        if not execution_event_id and not input_fingerprint:
            exclude("missing_execution_binding")
            continue
        if str(record.get("truth_status") or "") == "unsupported":
            exclude("unsupported_source_status")
            continue
        observed_at = str(record.get("outcome_observed_at") or "").strip()
        if (
            str(record.get("observation_window_start") or "") != expected_bindings["observation_window_start"]
            or str(record.get("observation_window_end") or "") != expected_bindings["observation_window_end"]
            or not observed_at
            or observed_at < expected_bindings["observation_window_start"]
            or observed_at > expected_bindings["observation_window_end"]
        ):
            exclude("record_outside_observation_window")
            continue
        if str(record.get("truth_status") or "") != "valid":
            exclude(f"truth_status_{str(record.get('truth_status') or 'unknown')}")
            continue
        record_fingerprint = str(record.get("record_fingerprint") or "").strip()
        if not record_fingerprint:
            exclude("record_fingerprint_missing")
            continue
        if record_fingerprint in seen_fingerprints:
            duplicate_collapsed_count += 1
            continue
        binding_key = execution_event_id or f"input:{input_fingerprint}"
        expected_value = record.get("expected_outcome")
        actual_value = record.get("actual_or_adjudicated_outcome")
        existing = binding_map.get(binding_key)
        if existing is not None:
            existing_expected, existing_actual, existing_fingerprint = existing
            if _deterministic_equal(existing_expected, expected_value) and _deterministic_equal(existing_actual, actual_value):
                duplicate_collapsed_count += 1
                seen_fingerprints.add(record_fingerprint)
                continue
            conflict_details.append(f"conflicting_duplicate_execution_binding:{binding_key}:{existing_fingerprint}:{record_fingerprint}")
            continue
        seen_fingerprints.add(record_fingerprint)
        binding_map[binding_key] = (expected_value, actual_value, record_fingerprint)
        eligible.append(record)
    eligible.sort(key=lambda item: (str(item.get("execution_event_id") or ""), str(item.get("input_fingerprint") or ""), str(item.get("record_fingerprint") or "")))
    return {
        "eligible_records": eligible,
        "duplicate_collapsed_count": duplicate_collapsed_count,
        "exclusion_reasons": exclusion_reasons,
        "conflict_details": conflict_details,
    }


def _comparable_records(records: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    comparable: list[dict[str, Any]] = []
    excluded = 0
    for record in records:
        expected = record.get("expected_outcome")
        actual = record.get("actual_or_adjudicated_outcome")
        if not _comparison_supported(expected, actual):
            excluded += 1
            continue
        comparable.append(dict(record))
    return comparable, excluded


def _metric_family_results(
    *,
    requested_metric_families: Sequence[str],
    scoring_result: Mapping[str, Any],
    comparable_records: Sequence[Mapping[str, Any]],
    exact_match_count: int,
    mismatch_count: int,
    comparable_excluded_count: int,
) -> dict[str, dict[str, Any]]:
    contract_metrics = scoring_result.get("metric_contracts")
    contract_metrics = contract_metrics if isinstance(contract_metrics, Mapping) else {}
    results: dict[str, dict[str, Any]] = {}
    denominator = len(comparable_records)
    for metric_name in requested_metric_families:
        contract_item = contract_metrics.get(metric_name)
        contract_item = contract_item if isinstance(contract_item, Mapping) else {}
        if metric_name == "accuracy_like_contract":
            results[metric_name] = {
                "status": "dry_run_calculated" if denominator > 0 else "blocked_no_eligible_records",
                "requested": True,
                "dry_run_only": True,
                "authoritative_result": False,
                "candidate_exact_match_count": exact_match_count,
                "candidate_mismatch_count": mismatch_count,
                "candidate_denominator_count": denominator,
                "candidate_accuracy_ratio": _ratio(exact_match_count, denominator),
                "candidate_accuracy_percentage": _percentage(exact_match_count, denominator),
                "excluded_from_comparison_count": comparable_excluded_count,
                "unsupported_reason": None if denominator > 0 else "no_deterministically_comparable_records",
                "calculation_scope": "dry_run_only",
            }
            continue
        if metric_name == "runtime_reliability_contract":
            results[metric_name] = {
                "status": "blocked_unsupported",
                "requested": True,
                "dry_run_only": True,
                "authoritative_result": False,
                "unsupported_reason": "runtime_reliability_inputs_not_loaded_in_dry_run",
                "calculation_scope": "dry_run_only",
            }
            continue
        if metric_name == "false_positive_false_negative_contract":
            results[metric_name] = {
                "status": "blocked_unsupported",
                "requested": True,
                "dry_run_only": True,
                "authoritative_result": False,
                "unsupported_reason": "class_semantics_not_defined",
                "calculation_scope": "dry_run_only",
            }
            continue
        if metric_name == "precision_recall_like_contract":
            results[metric_name] = {
                "status": "blocked_unsupported",
                "requested": True,
                "dry_run_only": True,
                "authoritative_result": False,
                "unsupported_reason": "positive_class_semantics_not_defined",
                "calculation_scope": "dry_run_only",
            }
            continue
        if metric_name == "calibration_like_contract":
            results[metric_name] = {
                "status": "blocked_unsupported",
                "requested": True,
                "dry_run_only": True,
                "authoritative_result": False,
                "unsupported_reason": "confidence_or_probability_evidence_missing",
                "calculation_scope": "dry_run_only",
            }
            continue
        results[metric_name] = {
            "status": "blocked_unsupported",
            "requested": True,
            "dry_run_only": True,
            "authoritative_result": False,
            "unsupported_reason": str(contract_item.get("unsupported_reason") or "unsupported_metric_family"),
            "calculation_scope": "dry_run_only",
        }
    return results


def _conflict_metric_family_results(requested_metric_families: Sequence[str]) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for metric_name in requested_metric_families:
        results[metric_name] = {
            "status": "blocked_conflict",
            "requested": True,
            "dry_run_only": True,
            "authoritative_result": False,
            "unsupported_reason": None,
            "conflict_reason": "conflicting_execution_binding",
            "calculation_scope": "dry_run_only",
        }
    return results


def _exact_match_counts(records: Sequence[Mapping[str, Any]]) -> tuple[int, int]:
    exact = 0
    mismatch = 0
    for record in records:
        if _deterministic_equal(record.get("expected_outcome"), record.get("actual_or_adjudicated_outcome")):
            exact += 1
        else:
            mismatch += 1
    return exact, mismatch


def _comparison_supported(expected: Any, actual: Any) -> bool:
    if type(expected) is not type(actual):
        return False
    if isinstance(expected, str):
        return True
    if isinstance(expected, (dict, list, tuple, int, float, bool)) or expected is None:
        try:
            _canonical_json(expected)
            _canonical_json(actual)
            return True
        except TypeError:
            return False
    return False


def _deterministic_equal(expected: Any, actual: Any) -> bool:
    if type(expected) is not type(actual):
        return False
    if isinstance(expected, str):
        return expected.strip() == actual.strip()
    return _canonical_json(expected) == _canonical_json(actual)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def _percentage(numerator: int, denominator: int) -> float | None:
    ratio = _ratio(numerator, denominator)
    if ratio is None:
        return None
    return ratio * 100.0


def _hash_payload(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _recommended_action(status: str) -> str:
    if status == "dry_run_ready":
        return "Review non-authoritative dry-run metrics before designing any persisted scoring phase."
    if status == "conflict":
        return "Resolve conflicting duplicate execution bindings before running any later scoring phase."
    return "Resolve dry-run blockers before using candidate scoring metrics."


def _dedupe(items: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        text = str(item)
        if text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered
