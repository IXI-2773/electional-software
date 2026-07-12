"""Outcome-truth source discovery and contract validation for deployed-rule effectiveness."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from . import deployed_rule_effectiveness_evaluation_spec as spec_backend
from . import deployed_rule_effectiveness_readiness as readiness_backend
from . import deployed_rule_operational_telemetry as telemetry_backend
from .canonical_rule_runtime import _atomic_write_json, _hash_payload, _now, _read_json, _restore_json, _safe_id
from .rule_effectiveness_analysis import _ensure_analysis_dirs
from .source_documents import SOURCE_DOCUMENT_ROOT

PLAN_DIR = "deployed_rule_outcome_truth_sources/plans"
RESULT_DIR = "deployed_rule_outcome_truth_sources/results"
RECEIPT_DIR = "deployed_rule_outcome_truth_sources/receipts"
RECORD_SET_DIR = "deployed_rule_outcome_truth_sources/record_sets"
RECORD_DIR = "deployed_rule_outcome_truth_sources/records"
PLAN_INDEX = "deployed_rule_outcome_truth_source_plan_index.json"
RESULT_INDEX = "deployed_rule_outcome_truth_source_result_index.json"
RECEIPT_INDEX = "deployed_rule_outcome_truth_source_receipt_index.json"
RECORD_SET_INDEX = "deployed_rule_outcome_truth_record_set_index.json"
RECORD_INDEX = "deployed_rule_outcome_truth_record_index.json"

PLAN_SCHEMA = "deployed_rule_outcome_truth_source_plan_v1"
RESULT_SCHEMA = "deployed_rule_outcome_truth_source_result_v1"
RECEIPT_SCHEMA = "deployed_rule_outcome_truth_source_receipt_v1"
RECORD_SET_SCHEMA = "deployed_rule_outcome_truth_record_set_v1"
RECORD_SCHEMA = "deployed_rule_outcome_truth_record_v1"
SOURCE_SCHEMA_VERSION = "deployed_rule_outcome_truth_source_v1"
MANIFEST_SCHEMA = "deployed_rule_outcome_truth_source_manifest_v1"
REQUIRED_CONFIRMATION = "RECORD_OUTCOME_TRUTH_SOURCE_RESULT"
REGISTER_CONFIRMATION = "REGISTER_OUTCOME_TRUTH_RECORD_SET"

ALLOWED_SOURCE_TYPES = {
    "external_authoritative_result",
    "adjudicated_ground_truth",
    "labeled_evaluation_record",
    "verified_actual_outcome",
}
ALLOWED_AUTHORITY_CLASSES = {"authoritative", "adjudicated", "verified", "provisional"}
ALLOWED_TRUTH_STATUSES = {"valid", "incomplete", "unsupported", "stale", "corrupt"}

SOURCE_STATUSES = [
    "outcome_truth_source_available",
    "outcome_truth_source_unavailable",
    "outcome_truth_source_incomplete",
    "outcome_truth_source_unsupported",
    "outcome_truth_source_stale",
    "outcome_truth_source_corrupt",
    "blocked",
]

PUBLIC_FUNCTIONS = [
    "get_deployed_rule_outcome_truth_source_manifest",
    "build_deployed_rule_outcome_truth_source_workspace",
    "validate_deployed_rule_outcome_truth_source_eligibility",
    "build_deployed_rule_outcome_truth_source_plan",
    "record_deployed_rule_outcome_truth_source_result",
    "load_deployed_rule_outcome_truth_source_result",
    "get_deployed_rule_outcome_truth_source_health",
    "format_deployed_rule_outcome_truth_source_report",
    "validate_deployed_rule_outcome_truth_record_set",
    "register_deployed_rule_outcome_truth_record_set",
    "load_deployed_rule_outcome_truth_record_set",
    "list_deployed_rule_outcome_truth_record_sets",
    "build_deployed_rule_outcome_truth_record_set_qa_gate",
    "format_deployed_rule_outcome_truth_record_set_qa_gate_report",
    "build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate",
    "format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report",
    "build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_planning_gate",
    "format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_planning_gate_report",
    "build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan",
    "format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report",
    "validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding",
    "format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_report",
    "build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_planning_gate",
    "format_deployed_rule_outcome_truth_record_set_controlled_registration_execution_planning_gate_report",
    "build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan",
    "format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_report",
    "run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run",
    "format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run_report",
    "validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding",
    "format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding_report",
    "build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate",
    "format_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate_report",
    "build_deployed_rule_outcome_truth_record_set_controlled_registration_authorization_artifact_preview",
    "format_deployed_rule_outcome_truth_record_set_controlled_registration_authorization_artifact_preview_report",
    "run_deployed_rule_outcome_truth_record_set_controlled_registration_confirmation_dry_run",
    "format_deployed_rule_outcome_truth_record_set_controlled_registration_confirmation_dry_run_report",
    "validate_deployed_rule_outcome_truth_record_set_controlled_registration_authorization_preview_confirmation_evidence_binding",
    "format_deployed_rule_outcome_truth_record_set_controlled_registration_authorization_preview_confirmation_evidence_binding_report",
]


def get_deployed_rule_outcome_truth_source_manifest(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    producer = {
        "producer_id": telemetry_backend.EXECUTION_PRODUCER_ID,
        "producer_kind": "authoritative_execution_observer",
        "producer_module": "deployed_rule_execution_runtime",
    }
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "outcome_truth_source_schema_version": SOURCE_SCHEMA_VERSION,
        "required_identifiers": [
            "canonical_rule_id",
            "production_deployment_result_id",
            "production_target_id",
            "deployed_rule_id",
            "telemetry_snapshot_id",
            "readiness_result_id",
            "effectiveness_spec_result_id",
            "observation_window_start",
            "observation_window_end",
        ],
        "source_statuses": list(SOURCE_STATUSES),
        "outcome_truth_types": [
            "adjudicated_ground_truth",
            "verified_actual_outcome",
            "expected_vs_actual_pair",
            "labeled_evaluation_record",
            "external_authoritative_result",
        ],
        "execution_producer_available": True,
        "execution_producer_id": (producer or {}).get("producer_id"),
        "phase_9w_not_outcome_truth": True,
        "runtime_completion_not_correctness": True,
        "effectiveness_evaluation_status": "not_performed",
        "candidate_source_discovery_status": "no_registered_authoritative_source",
    }
    manifest["manifest_fingerprint"] = _hash_payload(
        {key: manifest.get(key) for key in sorted(manifest) if key != "manifest_fingerprint"}
    )
    return manifest


def validate_deployed_rule_outcome_truth_record_set(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    observation_window_start: str,
    observation_window_end: str,
    *,
    source_id: str,
    source_type: str,
    source_authority_class: str,
    records: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    outcome_truth_record_set_id: str | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = Path(root)
    blockers: list[str] = []
    warnings: list[str] = []
    telemetry_snapshot = _read_json(telemetry_backend._snapshot_path(base, telemetry_snapshot_id))
    if not isinstance(telemetry_snapshot, Mapping):
        return {
            "status": "blocked",
            "warnings": [],
            "blockers": ["telemetry_snapshot_missing"],
            "record_count": 0,
            "valid_record_count": 0,
            "incomplete_record_count": 0,
            "unsupported_record_count": 0,
        }
    if not _text(canonical_rule_id) or not _text(production_deployment_result_id) or not _text(production_target_id) or not _text(deployed_rule_id):
        blockers.append("outcome_truth_identity_missing")
    if not _text(observation_window_start) or not _text(observation_window_end):
        blockers.append("outcome_truth_observation_window_missing")
    if str(telemetry_snapshot.get("canonical_rule_id") or "") != canonical_rule_id:
        blockers.append("telemetry_snapshot_canonical_rule_mismatch")
    if str(telemetry_snapshot.get("production_deployment_result_id") or "") != production_deployment_result_id:
        blockers.append("telemetry_snapshot_deployment_result_mismatch")
    if str(telemetry_snapshot.get("production_target_id") or "") != production_target_id:
        blockers.append("telemetry_snapshot_target_mismatch")
    if str(telemetry_snapshot.get("deployed_rule_id") or "") != deployed_rule_id:
        blockers.append("telemetry_snapshot_deployed_rule_mismatch")
    if str(telemetry_snapshot.get("observation_start") or "") != observation_window_start or str(telemetry_snapshot.get("observation_end") or "") != observation_window_end:
        blockers.append("telemetry_snapshot_observation_window_mismatch")
    if not _text(source_id):
        blockers.append("outcome_truth_source_id_missing")
    if source_type not in ALLOWED_SOURCE_TYPES:
        blockers.append("outcome_truth_source_type_unsupported")
    if source_authority_class not in ALLOWED_AUTHORITY_CLASSES:
        blockers.append("outcome_truth_source_authority_class_unsupported")
    if not isinstance(records, (list, tuple)) or not records:
        blockers.append("outcome_truth_records_missing")
        records = []

    snapshot_events = _snapshot_event_lookup(base, telemetry_snapshot)
    normalized_records: list[dict[str, Any]] = []
    valid_count = 0
    incomplete_count = 0
    unsupported_count = 0
    seen_record_ids: set[str] = set()
    seen_fingerprints: set[str] = set()
    record_blockers: list[str] = []
    for index, item in enumerate(records):
        normalized, item_status, item_blockers = _normalize_outcome_truth_record(
            item,
            canonical_rule_id=canonical_rule_id,
            production_deployment_result_id=production_deployment_result_id,
            production_target_id=production_target_id,
            deployed_rule_id=deployed_rule_id,
            telemetry_snapshot_id=telemetry_snapshot_id,
            source_id=source_id,
            source_type=source_type,
            source_authority_class=source_authority_class,
            observation_window_start=observation_window_start,
            observation_window_end=observation_window_end,
            snapshot_events=snapshot_events,
            index=index,
        )
        record_id = str(normalized.get("outcome_truth_record_id") or "")
        if record_id in seen_record_ids:
            item_blockers.append("outcome_truth_record_ids_not_unique")
        else:
            seen_record_ids.add(record_id)
        fingerprint = str(normalized.get("record_fingerprint") or "")
        if fingerprint in seen_fingerprints:
            item_blockers.append("outcome_truth_record_duplicate")
        else:
            seen_fingerprints.add(fingerprint)
        if item_blockers:
            record_blockers.extend(item_blockers)
        normalized_records.append(normalized)
        if item_status == "valid":
            valid_count += 1
        elif item_status == "unsupported":
            unsupported_count += 1
        else:
            incomplete_count += 1
    blockers.extend(record_blockers)

    set_id = outcome_truth_record_set_id or _record_set_id(
        canonical_rule_id,
        production_deployment_result_id,
        production_target_id,
        deployed_rule_id,
        telemetry_snapshot_id,
        source_id,
        source_type,
        source_authority_class,
        normalized_records,
    )
    set_payload = _record_set_payload(
        outcome_truth_record_set_id=set_id,
        canonical_rule_id=canonical_rule_id,
        production_deployment_result_id=production_deployment_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
        telemetry_snapshot_id=telemetry_snapshot_id,
        source_id=source_id,
        source_type=source_type,
        source_authority_class=source_authority_class,
        observation_window_start=observation_window_start,
        observation_window_end=observation_window_end,
        records=normalized_records,
        valid_record_count=valid_count,
        incomplete_record_count=incomplete_count,
        unsupported_record_count=unsupported_count,
    )
    status = "valid" if not blockers and valid_count == len(normalized_records) else "unsupported" if any(
        blocker in {"outcome_truth_source_type_unsupported", "outcome_truth_source_authority_class_unsupported", "outcome_truth_source_substitute_rejected"}
        or blocker.endswith("_not_outcome_truth")
        for blocker in blockers
    ) else "incomplete"
    return {
        "status": status,
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
        "outcome_truth_record_set_id": set_id,
        "record_set_fingerprint": set_payload["record_set_fingerprint"],
        "records": normalized_records,
        "record_count": len(normalized_records),
        "valid_record_count": valid_count,
        "incomplete_record_count": incomplete_count,
        "unsupported_record_count": unsupported_count,
        "record_set": set_payload,
    }


def register_deployed_rule_outcome_truth_record_set(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    observation_window_start: str,
    observation_window_end: str,
    *,
    source_id: str,
    source_type: str,
    source_authority_class: str,
    records: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
    confirmation: str | None = None,
    outcome_truth_record_set_id: str | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    if confirmation != REGISTER_CONFIRMATION:
        return {"status": "blocked", "writes_performed": 0, "warnings": [], "blockers": ["outcome_truth_record_set_confirmation_required"]}
    validation = validate_deployed_rule_outcome_truth_record_set(
        canonical_rule_id,
        production_deployment_result_id,
        production_target_id,
        deployed_rule_id,
        telemetry_snapshot_id,
        observation_window_start,
        observation_window_end,
        source_id=source_id,
        source_type=source_type,
        source_authority_class=source_authority_class,
        records=records,
        outcome_truth_record_set_id=outcome_truth_record_set_id,
        root=base,
    )
    if validation["status"] != "valid":
        return {"status": validation["status"], "writes_performed": 0, **{k: validation[k] for k in ("warnings", "blockers", "outcome_truth_record_set_id", "record_count", "valid_record_count", "incomplete_record_count", "unsupported_record_count")}}
    set_payload = dict(validation["record_set"])
    set_id = str(validation["outcome_truth_record_set_id"])
    set_path = _record_set_path(base, set_id)
    existing_set = _read_json(set_path)
    if isinstance(existing_set, Mapping):
        if str(existing_set.get("record_set_fingerprint") or "") == str(set_payload.get("record_set_fingerprint") or ""):
            if _record_files_match(base, validation["records"]):
                return {"status": "already_registered", "writes_performed": 0, "outcome_truth_record_set_id": set_id, "record_set_fingerprint": set_payload["record_set_fingerprint"], "record_count": validation["record_count"]}
            return {"status": "corrupt", "writes_performed": 0, "warnings": [], "blockers": ["outcome_truth_record_files_missing_for_registered_set"], "outcome_truth_record_set_id": set_id}
        return {"status": "conflict", "writes_performed": 0, "warnings": [], "blockers": ["outcome_truth_record_set_conflict"], "outcome_truth_record_set_id": set_id}
    for record in validation["records"]:
        record_path = _record_path(base, str(record.get("outcome_truth_record_id") or ""))
        existing_record = _read_json(record_path)
        if isinstance(existing_record, Mapping) and str(existing_record.get("record_fingerprint") or "") != str(record.get("record_fingerprint") or ""):
            return {"status": "conflict", "writes_performed": 0, "warnings": [], "blockers": ["outcome_truth_record_conflict"], "outcome_truth_record_set_id": set_id}

    before_set = _read_json(set_path)
    before_records = {str(record.get("outcome_truth_record_id") or ""): _read_json(_record_path(base, str(record.get("outcome_truth_record_id") or ""))) for record in validation["records"]}
    before_set_index = _read_json(base / "indexes" / RECORD_SET_INDEX)
    before_record_index = _read_json(base / "indexes" / RECORD_INDEX)
    try:
        _atomic_write_json(set_path, set_payload)
        for record in validation["records"]:
            _atomic_write_json(_record_path(base, str(record.get("outcome_truth_record_id") or "")), record)
        _update_record_set_index(base)
        _update_record_index(base)
    except Exception:
        _restore_json(set_path, before_set)
        for record_id, payload in before_records.items():
            _restore_json(_record_path(base, record_id), payload)
        _restore_json(base / "indexes" / RECORD_SET_INDEX, before_set_index)
        _restore_json(base / "indexes" / RECORD_INDEX, before_record_index)
        return {"status": "corrupt", "writes_performed": 0, "warnings": [], "blockers": ["outcome_truth_record_set_write_failure"], "outcome_truth_record_set_id": set_id}
    return {
        "status": "registered",
        "writes_performed": 1 + len(validation["records"]),
        "outcome_truth_record_set_id": set_id,
        "record_set_fingerprint": set_payload["record_set_fingerprint"],
        "record_count": validation["record_count"],
        "valid_record_count": validation["valid_record_count"],
        "incomplete_record_count": validation["incomplete_record_count"],
        "unsupported_record_count": validation["unsupported_record_count"],
        "warnings": [],
        "blockers": [],
    }


def load_deployed_rule_outcome_truth_record_set(
    outcome_truth_record_set_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = Path(root)
    payload = _read_json(_record_set_path(base, outcome_truth_record_set_id))
    if not isinstance(payload, Mapping):
        return {"status": "blocked", "warnings": [], "blockers": ["outcome_truth_record_set_missing"], "outcome_truth_record_set_id": outcome_truth_record_set_id}
    records = []
    for record_id in list(payload.get("outcome_truth_record_ids", []) or []):
        record = _read_json(_record_path(base, str(record_id or "")))
        if isinstance(record, Mapping):
            records.append(dict(record))
    if len(records) != len(list(payload.get("outcome_truth_record_ids", []) or [])):
        return {"status": "corrupt", "warnings": [], "blockers": ["outcome_truth_record_set_missing_record"], "outcome_truth_record_set_id": outcome_truth_record_set_id}
    return {"status": "loaded", "outcome_truth_record_set": dict(payload), "outcome_truth_records": records, "warnings": [], "blockers": []}


def list_deployed_rule_outcome_truth_record_sets(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = Path(root)
    items = []
    for entry in _index_items(base / "indexes" / RECORD_SET_INDEX):
        if str(entry.get("canonical_rule_id") or "") != canonical_rule_id:
            continue
        if str(entry.get("production_deployment_result_id") or "") != production_deployment_result_id:
            continue
        if str(entry.get("production_target_id") or "") != production_target_id:
            continue
        if str(entry.get("deployed_rule_id") or "") != deployed_rule_id:
            continue
        if str(entry.get("telemetry_snapshot_id") or "") != telemetry_snapshot_id:
            continue
        items.append(entry)
    items.sort(key=lambda item: (str(item.get("source_id") or ""), str(item.get("outcome_truth_record_set_id") or "")))
    return {"status": "listed", "items": items, "warnings": [], "blockers": []}


def build_deployed_rule_outcome_truth_record_set_qa_gate(
    outcome_truth_record_set_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    safe_record_set_id = str(outcome_truth_record_set_id or "").strip()
    limitations = _outcome_truth_record_set_qa_limitations()
    boundary_flags = _outcome_truth_record_set_qa_boundary_flags()
    if not safe_record_set_id:
        return {
            "qa_gate_schema_version": "deployed_rule_outcome_truth_record_set_qa_gate_v1",
            "qa_gate_type": "outcome_truth_record_set_structural_consistency_qa",
            "status": "missing",
            "outcome_truth_record_set_id": "",
            "record_set_status": "missing",
            "record_count": 0,
            "eligible_record_count": 0,
            "excluded_record_count": 0,
            "duplicate_record_count": 0,
            "conflict_count": 0,
            "missing_required_field_count": 0,
            "missing_expected_outcome_count": 0,
            "missing_actual_outcome_count": 0,
            "invalid_outcome_value_count": 0,
            "missing_source_metadata_count": 0,
            "malformed_record_count": 0,
            "blockers": ["outcome_truth_record_set_id_required"],
            "warnings": [],
            "recommended_action": "Provide an outcome-truth record-set ID before running the structural QA gate.",
            "limitations": limitations,
            "boundary_flags": boundary_flags,
            "writes_performed": 0,
        }
    loaded = load_deployed_rule_outcome_truth_record_set(safe_record_set_id, root=root)
    loaded_status = str(loaded.get("status") or "unknown")
    if loaded_status == "blocked":
        return {
            "qa_gate_schema_version": "deployed_rule_outcome_truth_record_set_qa_gate_v1",
            "qa_gate_type": "outcome_truth_record_set_structural_consistency_qa",
            "status": "missing",
            "outcome_truth_record_set_id": safe_record_set_id,
            "record_set_status": "missing",
            "record_count": 0,
            "eligible_record_count": 0,
            "excluded_record_count": 0,
            "duplicate_record_count": 0,
            "conflict_count": 0,
            "missing_required_field_count": 0,
            "missing_expected_outcome_count": 0,
            "missing_actual_outcome_count": 0,
            "invalid_outcome_value_count": 0,
            "missing_source_metadata_count": 0,
            "malformed_record_count": 0,
            "blockers": list(loaded.get("blockers", [])) if isinstance(loaded.get("blockers"), list) else ["outcome_truth_record_set_missing"],
            "warnings": [],
            "recommended_action": "Register or restore the outcome-truth record set before using it for structural QA.",
            "limitations": limitations,
            "boundary_flags": boundary_flags,
            "writes_performed": 0,
        }
    if loaded_status == "corrupt":
        return {
            "qa_gate_schema_version": "deployed_rule_outcome_truth_record_set_qa_gate_v1",
            "qa_gate_type": "outcome_truth_record_set_structural_consistency_qa",
            "status": "corrupt",
            "outcome_truth_record_set_id": safe_record_set_id,
            "record_set_status": "corrupt",
            "record_count": 0,
            "eligible_record_count": 0,
            "excluded_record_count": 0,
            "duplicate_record_count": 0,
            "conflict_count": 0,
            "missing_required_field_count": 0,
            "missing_expected_outcome_count": 0,
            "missing_actual_outcome_count": 0,
            "invalid_outcome_value_count": 0,
            "missing_source_metadata_count": 0,
            "malformed_record_count": 0,
            "blockers": list(loaded.get("blockers", [])) if isinstance(loaded.get("blockers"), list) else ["outcome_truth_record_set_corrupt"],
            "warnings": [],
            "recommended_action": "Repair or replace the corrupt outcome-truth record set before using it for structural QA.",
            "limitations": limitations,
            "boundary_flags": boundary_flags,
            "writes_performed": 0,
        }
    record_set = loaded.get("outcome_truth_record_set") if isinstance(loaded, Mapping) else None
    records = loaded.get("outcome_truth_records") if isinstance(loaded, Mapping) else None
    if not isinstance(record_set, Mapping) or not isinstance(records, list):
        return {
            "qa_gate_schema_version": "deployed_rule_outcome_truth_record_set_qa_gate_v1",
            "qa_gate_type": "outcome_truth_record_set_structural_consistency_qa",
            "status": "corrupt",
            "outcome_truth_record_set_id": safe_record_set_id,
            "record_set_status": "corrupt",
            "record_count": 0,
            "eligible_record_count": 0,
            "excluded_record_count": 0,
            "duplicate_record_count": 0,
            "conflict_count": 0,
            "missing_required_field_count": 0,
            "missing_expected_outcome_count": 0,
            "missing_actual_outcome_count": 0,
            "invalid_outcome_value_count": 0,
            "missing_source_metadata_count": 0,
            "malformed_record_count": 0,
            "blockers": ["outcome_truth_record_set_payload_malformed"],
            "warnings": [],
            "recommended_action": "Repair the malformed outcome-truth record-set payload before using it for structural QA.",
            "limitations": limitations,
            "boundary_flags": boundary_flags,
            "writes_performed": 0,
        }
    analysis = _analyze_outcome_truth_record_set_for_qa(record_set, records)
    qa_status = "passed"
    if analysis["blockers"]:
        qa_status = "blocked"
    return {
        "qa_gate_schema_version": "deployed_rule_outcome_truth_record_set_qa_gate_v1",
        "qa_gate_type": "outcome_truth_record_set_structural_consistency_qa",
        "status": qa_status,
        "outcome_truth_record_set_id": safe_record_set_id,
        "record_set_status": str(record_set.get("source_status") or "loaded"),
        "record_count": len(records),
        "eligible_record_count": analysis["eligible_record_count"],
        "excluded_record_count": analysis["excluded_record_count"],
        "duplicate_record_count": analysis["duplicate_record_count"],
        "conflict_count": analysis["conflict_count"],
        "missing_required_field_count": analysis["missing_required_field_count"],
        "missing_expected_outcome_count": analysis["missing_expected_outcome_count"],
        "missing_actual_outcome_count": analysis["missing_actual_outcome_count"],
        "invalid_outcome_value_count": analysis["invalid_outcome_value_count"],
        "missing_source_metadata_count": analysis["missing_source_metadata_count"],
        "malformed_record_count": analysis["malformed_record_count"],
        "blockers": analysis["blockers"],
        "warnings": analysis["warnings"],
        "recommended_action": "Proceed only with structurally consistent outcome-truth record sets for scoped exact-match scoring inputs." if qa_status == "passed" else "Resolve structural blockers or warnings in the outcome-truth record set before downstream scoring use.",
        "limitations": limitations,
        "boundary_flags": boundary_flags,
        "writes_performed": 0,
    }


def format_deployed_rule_outcome_truth_record_set_qa_gate_report(
    outcome_truth_record_set_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    qa_gate = build_deployed_rule_outcome_truth_record_set_qa_gate(
        outcome_truth_record_set_id,
        root=root,
    )
    lines = [
        "Outcome-truth record-set structural QA gate",
        f"Status: {qa_gate.get('status')}",
        f"Record-set ID: {qa_gate.get('outcome_truth_record_set_id') or 'none'}",
        f"Record-set status: {qa_gate.get('record_set_status')}",
        f"Record count: {qa_gate.get('record_count', 0)}",
        f"Eligible record count: {qa_gate.get('eligible_record_count', 0)}",
        f"Excluded record count: {qa_gate.get('excluded_record_count', 0)}",
        f"Duplicate record count: {qa_gate.get('duplicate_record_count', 0)}",
        f"Conflict count: {qa_gate.get('conflict_count', 0)}",
        f"Missing required field count: {qa_gate.get('missing_required_field_count', 0)}",
        f"Missing expected outcome count: {qa_gate.get('missing_expected_outcome_count', 0)}",
        f"Missing actual outcome count: {qa_gate.get('missing_actual_outcome_count', 0)}",
        f"Invalid outcome value count: {qa_gate.get('invalid_outcome_value_count', 0)}",
        f"Missing source metadata count: {qa_gate.get('missing_source_metadata_count', 0)}",
        f"Malformed record count: {qa_gate.get('malformed_record_count', 0)}",
        "This QA gate checks structural and internal consistency of an outcome-truth record set.",
        "It does not prove the factual correctness of outcome-truth records.",
        "It does not establish broad rule effectiveness.",
        "It does not establish deployment safety.",
        "It does not establish production correctness.",
        "It does not establish profitability.",
        "It does not establish prediction quality.",
        "It does not establish future performance.",
        "It does not establish aggregate effectiveness.",
        "It does not establish ranking quality.",
    ]
    blockers = qa_gate.get("blockers", [])
    warnings = qa_gate.get("warnings", [])
    if isinstance(blockers, list) and blockers:
        lines.append("Blockers: " + ", ".join(str(item) for item in blockers))
    if isinstance(warnings, list) and warnings:
        lines.append("Warnings: " + ", ".join(str(item) for item in warnings))
    recommended_action = qa_gate.get("recommended_action")
    if recommended_action:
        lines.append(f"Recommended action: {recommended_action}")
    limitations = qa_gate.get("limitations", [])
    if isinstance(limitations, list) and limitations:
        lines.append("Limitations: " + "; ".join(str(item) for item in limitations))
    lines.append(f"Writes performed: {qa_gate.get('writes_performed', 0)}")
    return "\n".join(lines)


def build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate(
    candidate_record_set: Any,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    limitations = _outcome_truth_record_set_registration_pipeline_qa_limitations()
    boundary_flags = _outcome_truth_record_set_registration_pipeline_qa_boundary_flags()
    base_payload = {
        "registration_qa_schema_version": "deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_v1",
        "registration_qa_type": "outcome_truth_record_set_registration_pipeline_structural_qa",
        "candidate_status": "missing",
        "candidate_record_count": 0,
        "candidate_eligible_record_count": 0,
        "candidate_excluded_record_count": 0,
        "duplicate_record_count": 0,
        "conflict_count": 0,
        "missing_required_field_count": 0,
        "missing_expected_outcome_count": 0,
        "missing_actual_outcome_count": 0,
        "invalid_outcome_value_count": 0,
        "missing_source_metadata_count": 0,
        "malformed_record_count": 0,
        "mixed_scope_warning_count": 0,
        "structurally_ready_for_registration": False,
        "blockers": [],
        "warnings": [],
        "recommended_action": "",
        "limitations": limitations,
        "boundary_flags": boundary_flags,
        "writes_performed": 0,
    }
    if not isinstance(candidate_record_set, Mapping):
        return {
            **base_payload,
            "status": "missing" if candidate_record_set is None else "malformed",
            "candidate_status": "missing" if candidate_record_set is None else "malformed",
            "blockers": ["candidate_record_set_missing" if candidate_record_set is None else "candidate_record_set_payload_malformed"],
            "recommended_action": "Provide a candidate outcome-truth record-set payload with registration metadata and records before running preflight structural QA.",
        }

    records = candidate_record_set.get("records")
    if not isinstance(records, (list, tuple)):
        return {
            **base_payload,
            "status": "malformed",
            "candidate_status": "malformed",
            "blockers": ["candidate_record_set_records_missing"],
            "recommended_action": "Provide candidate records in the current registration payload shape before running preflight structural QA.",
        }

    validation = validate_deployed_rule_outcome_truth_record_set(
        str(candidate_record_set.get("canonical_rule_id") or ""),
        str(candidate_record_set.get("production_deployment_result_id") or ""),
        str(candidate_record_set.get("production_target_id") or ""),
        str(candidate_record_set.get("deployed_rule_id") or ""),
        str(candidate_record_set.get("telemetry_snapshot_id") or ""),
        str(candidate_record_set.get("observation_window_start") or ""),
        str(candidate_record_set.get("observation_window_end") or ""),
        source_id=str(candidate_record_set.get("source_id") or ""),
        source_type=str(candidate_record_set.get("source_type") or ""),
        source_authority_class=str(candidate_record_set.get("source_authority_class") or ""),
        records=records,
        outcome_truth_record_set_id=str(candidate_record_set.get("outcome_truth_record_set_id") or "") or None,
        root=root,
    )
    validation_status = str(validation.get("status") or "blocked")
    normalized_records = validation.get("records") if isinstance(validation.get("records"), list) else []
    candidate_count = len(records)
    if validation_status == "blocked":
        return {
            **base_payload,
            "status": "blocked",
            "candidate_status": "blocked",
            "candidate_record_count": candidate_count,
            "blockers": list(validation.get("blockers", [])) if isinstance(validation.get("blockers"), list) else ["candidate_record_set_blocked"],
            "warnings": list(validation.get("warnings", [])) if isinstance(validation.get("warnings"), list) else [],
            "recommended_action": "Resolve candidate metadata or telemetry blockers before later registration.",
        }

    record_set = validation.get("record_set") if isinstance(validation.get("record_set"), Mapping) else None
    if not isinstance(record_set, Mapping):
        return {
            **base_payload,
            "status": "malformed",
            "candidate_status": "malformed",
            "candidate_record_count": candidate_count,
            "blockers": ["candidate_record_set_payload_malformed"],
            "recommended_action": "Repair the malformed candidate payload before later registration.",
        }

    analysis = _analyze_candidate_outcome_truth_record_set_for_registration_qa(candidate_record_set, records)
    warnings = list(analysis.get("warnings", [])) if isinstance(analysis.get("warnings"), list) else []
    blockers = list(analysis.get("blockers", [])) if isinstance(analysis.get("blockers"), list) else []
    validation_blockers = list(validation.get("blockers", [])) if isinstance(validation.get("blockers"), list) else []
    blockers = _dedupe(blockers + validation_blockers)
    mixed_scope_warning_count = sum(1 for item in warnings if "mixed_" in str(item))
    qa_status = "passed" if not blockers else "blocked"
    candidate_status = "valid" if validation_status == "valid" else validation_status
    return {
        **base_payload,
        "status": qa_status,
        "candidate_status": candidate_status,
        "candidate_record_count": candidate_count,
        "candidate_eligible_record_count": int(analysis.get("eligible_record_count", 0)),
        "candidate_excluded_record_count": int(analysis.get("excluded_record_count", 0)),
        "duplicate_record_count": int(analysis.get("duplicate_record_count", 0)),
        "conflict_count": int(analysis.get("conflict_count", 0)),
        "missing_required_field_count": int(analysis.get("missing_required_field_count", 0)),
        "missing_expected_outcome_count": int(analysis.get("missing_expected_outcome_count", 0)),
        "missing_actual_outcome_count": int(analysis.get("missing_actual_outcome_count", 0)),
        "invalid_outcome_value_count": int(analysis.get("invalid_outcome_value_count", 0)),
        "missing_source_metadata_count": int(analysis.get("missing_source_metadata_count", 0)),
        "malformed_record_count": int(analysis.get("malformed_record_count", 0)),
        "mixed_scope_warning_count": mixed_scope_warning_count,
        "structurally_ready_for_registration": qa_status == "passed",
        "blockers": blockers,
        "warnings": warnings,
        "recommended_action": "Candidate payload is structurally ready for later registration only." if qa_status == "passed" else "Resolve structural blockers or warnings before sending this candidate payload to the registration pipeline.",
    }


def format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report(
    candidate_record_set: Any,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    qa_gate = build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate(
        candidate_record_set,
        root=root,
    )
    lines = [
        "Outcome-truth registration-pipeline structural QA gate",
        f"Status: {qa_gate.get('status')}",
        f"Candidate status: {qa_gate.get('candidate_status')}",
        f"Candidate record count: {qa_gate.get('candidate_record_count', 0)}",
        f"Candidate eligible record count: {qa_gate.get('candidate_eligible_record_count', 0)}",
        f"Candidate excluded record count: {qa_gate.get('candidate_excluded_record_count', 0)}",
        f"Duplicate record count: {qa_gate.get('duplicate_record_count', 0)}",
        f"Conflict count: {qa_gate.get('conflict_count', 0)}",
        f"Missing required field count: {qa_gate.get('missing_required_field_count', 0)}",
        f"Missing expected outcome count: {qa_gate.get('missing_expected_outcome_count', 0)}",
        f"Missing actual outcome count: {qa_gate.get('missing_actual_outcome_count', 0)}",
        f"Invalid outcome value count: {qa_gate.get('invalid_outcome_value_count', 0)}",
        f"Missing source metadata count: {qa_gate.get('missing_source_metadata_count', 0)}",
        f"Malformed record count: {qa_gate.get('malformed_record_count', 0)}",
        f"Mixed-scope warning count: {qa_gate.get('mixed_scope_warning_count', 0)}",
        f"Structurally ready for registration: {str(bool(qa_gate.get('structurally_ready_for_registration'))).lower()}",
        "This registration-pipeline QA gate checks structural and internal consistency of a candidate outcome-truth record set before registration.",
        "It does not register the record set.",
        "It does not repair or migrate records.",
        "It does not prove the factual correctness of outcome-truth records.",
        "It does not establish broad rule effectiveness.",
        "It does not establish deployment safety.",
        "It does not establish production correctness.",
        "It does not establish profitability.",
        "It does not establish prediction quality.",
        "It does not establish future performance.",
        "It does not establish aggregate effectiveness.",
        "It does not establish ranking quality.",
    ]
    blockers = qa_gate.get("blockers", [])
    warnings = qa_gate.get("warnings", [])
    if isinstance(blockers, list) and blockers:
        lines.append("Blockers: " + ", ".join(str(item) for item in blockers))
    if isinstance(warnings, list) and warnings:
        lines.append("Warnings: " + ", ".join(str(item) for item in warnings))
    recommended_action = qa_gate.get("recommended_action")
    if recommended_action:
        lines.append(f"Recommended action: {recommended_action}")
    limitations = qa_gate.get("limitations", [])
    if isinstance(limitations, list) and limitations:
        lines.append("Limitations: " + "; ".join(str(item) for item in limitations))
    lines.append(f"Writes performed: {qa_gate.get('writes_performed', 0)}")
    return "\n".join(lines)


def build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_planning_gate(
    candidate_record_set: Any,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    limitations = _outcome_truth_record_set_controlled_registration_workflow_planning_limitations()
    boundary_flags = _outcome_truth_record_set_controlled_registration_workflow_planning_boundary_flags()
    planned_future_workflow_steps = [
        "1. Accept candidate record-set payload.",
        "2. Run registration-pipeline QA gate.",
        "3. Block if candidate QA has blockers or is not structurally ready.",
        "4. Build a controlled registration plan.",
        "5. Require exact future confirmation before any write.",
        "6. Execute registration through the existing registration function only after confirmation.",
        "7. Load the registered record set.",
        "8. Run post-registration record-set QA gate.",
        "9. Produce public-safe registration receipt/report.",
        "10. Do not claim factual truth correctness.",
    ]
    required_future_safeguards = [
        "explicit confirmation before write",
        "no automatic registration from QA",
        "no forced registration",
        "no truth override",
        "no expected or actual outcome override",
        "no score authority",
        "no scoring",
        "post-registration load-back",
        "post-registration QA gate",
        "public-safe receipt/report",
        "no factual truth correctness claim",
        "no broad effectiveness claim",
    ]
    base_payload = {
        "planning_gate_schema_version": "deployed_rule_outcome_truth_record_set_controlled_registration_workflow_planning_gate_v1",
        "planning_gate_type": "controlled_outcome_truth_record_set_registration_workflow_planning_gate",
        "candidate_qa_status": "missing",
        "candidate_structurally_ready_for_registration": False,
        "planning_ready_for_future_controlled_registration_workflow": False,
        "controlled_registration_implemented": False,
        "registration_performed": False,
        "record_set_written": False,
        "records_repaired": False,
        "records_migrated": False,
        "automatic_registration_approval_claimed": False,
        "required_future_confirmation": REGISTER_CONFIRMATION,
        "future_confirmation_is_advisory_only": True,
        "required_future_preconditions": [
            "candidate registration-pipeline QA must pass first",
            "frozen record-set QA surface must remain available",
            "future registration must require exact confirmation",
            "future registration must verify the stored record set after write",
            "future registration must run post-registration record-set QA",
        ],
        "planned_future_workflow_steps": planned_future_workflow_steps,
        "required_future_safeguards": required_future_safeguards,
        "prerequisite_surface_status": {
            "registration_pipeline_qa_build_available": callable(
                build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate
            ),
            "registration_pipeline_qa_report_available": callable(
                format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report
            ),
            "record_set_qa_build_available": callable(build_deployed_rule_outcome_truth_record_set_qa_gate),
            "record_set_qa_report_available": callable(format_deployed_rule_outcome_truth_record_set_qa_gate_report),
            "registration_function_available": callable(register_deployed_rule_outcome_truth_record_set),
        },
        "candidate_qa_summary": {
            "status": "missing",
            "candidate_record_count": 0,
            "duplicate_record_count": 0,
            "conflict_count": 0,
            "missing_required_field_count": 0,
            "missing_expected_outcome_count": 0,
            "missing_actual_outcome_count": 0,
            "structurally_ready_for_registration": False,
            "blockers": [],
            "warnings": [],
        },
        "blockers": [],
        "warnings": [],
        "recommended_action": "",
        "limitations": limitations,
        "boundary_flags": boundary_flags,
        "writes_performed": 0,
    }
    candidate_qa = build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate(
        candidate_record_set,
        root=root,
    )
    candidate_summary = {
        "status": str(candidate_qa.get("status") or "blocked"),
        "candidate_record_count": int(candidate_qa.get("candidate_record_count", 0) or 0),
        "duplicate_record_count": int(candidate_qa.get("duplicate_record_count", 0) or 0),
        "conflict_count": int(candidate_qa.get("conflict_count", 0) or 0),
        "missing_required_field_count": int(candidate_qa.get("missing_required_field_count", 0) or 0),
        "missing_expected_outcome_count": int(candidate_qa.get("missing_expected_outcome_count", 0) or 0),
        "missing_actual_outcome_count": int(candidate_qa.get("missing_actual_outcome_count", 0) or 0),
        "structurally_ready_for_registration": bool(candidate_qa.get("structurally_ready_for_registration")),
        "blockers": list(candidate_qa.get("blockers", [])) if isinstance(candidate_qa.get("blockers"), list) else [],
        "warnings": list(candidate_qa.get("warnings", [])) if isinstance(candidate_qa.get("warnings"), list) else [],
    }
    blockers = list(candidate_summary["blockers"])
    warnings = list(candidate_summary["warnings"])
    surface_status = dict(base_payload["prerequisite_surface_status"])
    if not surface_status["registration_pipeline_qa_build_available"]:
        blockers.append("registration_pipeline_qa_build_unavailable")
    if not surface_status["registration_pipeline_qa_report_available"]:
        blockers.append("registration_pipeline_qa_report_unavailable")
    if not surface_status["record_set_qa_build_available"]:
        blockers.append("record_set_qa_build_unavailable")
    if not surface_status["record_set_qa_report_available"]:
        blockers.append("record_set_qa_report_unavailable")
    if not surface_status["registration_function_available"]:
        blockers.append("registration_function_unavailable")

    candidate_status = str(candidate_qa.get("status") or "blocked")
    if candidate_status in {"missing", "malformed"}:
        status = candidate_status
    elif candidate_status != "passed" or not candidate_summary["structurally_ready_for_registration"]:
        status = "blocked"
        if candidate_status == "blocked" and not blockers:
            blockers.append("candidate_registration_pipeline_qa_blocked")
    elif blockers:
        status = "blocked"
    else:
        status = "planning_ready"

    recommended_action = (
        "Phase 13A planning prerequisites are present. A later backend workflow phase can design controlled registration without enabling writes here."
        if status == "planning_ready"
        else "Resolve candidate QA or prerequisite-surface blockers before designing the future controlled registration workflow."
    )
    return {
        **base_payload,
        "status": status,
        "candidate_qa_status": candidate_status,
        "candidate_structurally_ready_for_registration": candidate_summary["structurally_ready_for_registration"],
        "planning_ready_for_future_controlled_registration_workflow": status == "planning_ready",
        "candidate_qa_summary": candidate_summary,
        "blockers": _dedupe(blockers),
        "warnings": _dedupe(warnings),
        "recommended_action": recommended_action,
    }


def format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_planning_gate_report(
    candidate_record_set: Any,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    planning_gate = build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_planning_gate(
        candidate_record_set,
        root=root,
    )
    candidate_qa_summary = planning_gate.get("candidate_qa_summary", {})
    prerequisite_surface_status = planning_gate.get("prerequisite_surface_status", {})
    lines = [
        "Controlled outcome-truth record-set registration workflow planning gate",
        f"Status: {planning_gate.get('status')}",
        f"Candidate QA status: {planning_gate.get('candidate_qa_status')}",
        "Candidate structurally ready for registration: "
        + str(bool(planning_gate.get("candidate_structurally_ready_for_registration"))).lower(),
        "Planning ready for future controlled registration workflow: "
        + str(bool(planning_gate.get("planning_ready_for_future_controlled_registration_workflow"))).lower(),
        f"Candidate record count: {candidate_qa_summary.get('candidate_record_count', 0)}",
        f"Duplicate record count: {candidate_qa_summary.get('duplicate_record_count', 0)}",
        f"Conflict count: {candidate_qa_summary.get('conflict_count', 0)}",
        f"Missing required field count: {candidate_qa_summary.get('missing_required_field_count', 0)}",
        f"Missing expected outcome count: {candidate_qa_summary.get('missing_expected_outcome_count', 0)}",
        f"Missing actual outcome count: {candidate_qa_summary.get('missing_actual_outcome_count', 0)}",
        "Required future confirmation: "
        + str(planning_gate.get("required_future_confirmation") or REGISTER_CONFIRMATION),
        "Future confirmation is advisory only: "
        + str(bool(planning_gate.get("future_confirmation_is_advisory_only"))).lower(),
        "This planning gate checks readiness to design a future controlled outcome-truth record-set registration workflow.",
        "It does not register records.",
        "It does not create record sets.",
        "It does not repair records.",
        "It does not migrate records.",
        "It does not approve automatic registration.",
        "It does not prove factual correctness of outcome-truth records.",
        "It does not establish broad rule effectiveness.",
        "It does not establish deployment safety.",
        "It does not establish production correctness.",
        "It does not establish profitability.",
        "It does not establish prediction quality.",
        "It does not establish future performance.",
        "It does not establish aggregate effectiveness.",
        "It does not establish ranking quality.",
        "The proposed future confirmation is not active in Phase 13A.",
        "A later implementation phase must enforce confirmation before any write.",
        "Prerequisite surfaces: "
        + ", ".join(
            f"{key}={str(bool(value)).lower()}" for key, value in sorted(prerequisite_surface_status.items())
        ),
        "Planned future workflow steps: "
        + " | ".join(str(item) for item in planning_gate.get("planned_future_workflow_steps", [])),
        "Required future safeguards: "
        + ", ".join(str(item) for item in planning_gate.get("required_future_safeguards", [])),
    ]
    blockers = planning_gate.get("blockers", [])
    warnings = planning_gate.get("warnings", [])
    if isinstance(blockers, list) and blockers:
        lines.append("Blockers: " + ", ".join(str(item) for item in blockers))
    if isinstance(warnings, list) and warnings:
        lines.append("Warnings: " + ", ".join(str(item) for item in warnings))
    recommended_action = planning_gate.get("recommended_action")
    if recommended_action:
        lines.append(f"Recommended action: {recommended_action}")
    limitations = planning_gate.get("limitations", [])
    if isinstance(limitations, list) and limitations:
        lines.append("Limitations: " + "; ".join(str(item) for item in limitations))
    lines.append(f"Writes performed: {planning_gate.get('writes_performed', 0)}")
    return "\n".join(lines)


def build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan(
    candidate_record_set: Any,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    candidate_before_fingerprint = _candidate_fingerprint(candidate_record_set)
    candidate_copy = deepcopy(candidate_record_set)
    limitations = _outcome_truth_record_set_controlled_registration_workflow_backend_plan_limitations()
    boundary_flags = _outcome_truth_record_set_controlled_registration_workflow_backend_plan_boundary_flags()
    planned_future_execution_steps = [
        "1. Accept candidate record-set payload.",
        "2. Run registration-pipeline QA gate.",
        "3. Run controlled registration planning gate.",
        "4. Build backend plan.",
        "5. Require exact confirmation before any write in a later phase.",
        "6. Execute registration through the existing registration function only after confirmation in a later phase.",
        "7. Load the registered record set.",
        "8. Run post-registration record-set QA gate.",
        "9. Produce public-safe registration receipt/report.",
        "10. Do not claim factual truth correctness.",
    ]
    planned_future_post_registration_checks = [
        "load registered record set",
        "verify expected record count",
        "verify registered record-set ID exists",
        "run post-registration record-set QA gate",
        "verify no duplicate or conflict blockers after registration",
        "produce public-safe report",
        "preserve no-overclaim boundary",
    ]
    required_future_safeguards = [
        "explicit confirmation before write",
        "no automatic registration from QA",
        "no forced registration",
        "no truth override",
        "no expected or actual outcome override",
        "no score authority",
        "no scoring",
        "no mutation without plan",
        "no mutation without QA prerequisite",
        "post-registration load-back",
        "post-registration QA gate",
        "public-safe receipt/report",
        "no factual truth correctness claim",
        "no broad effectiveness claim",
    ]
    base_payload = {
        "backend_plan_schema_version": "deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_v1",
        "backend_plan_type": "controlled_outcome_truth_record_set_registration_workflow_backend_plan",
        "backend_plan_identity_schema_version": 1,
        "candidate_fingerprint_algorithm": "sha256",
        "planning_gate_fingerprint_algorithm": "sha256",
        "backend_plan_fingerprint_algorithm": "sha256",
        "identity_deterministic": True,
        "identity_public_safe": True,
        "planning_gate_status": "missing",
        "candidate_qa_status": "missing",
        "candidate_structurally_ready_for_registration": False,
        "backend_plan_ready_for_future_execution": False,
        "candidate_input_mutation_check_performed": True,
        "candidate_input_mutated": False,
        "execution_authorized": False,
        "registration_authorized": False,
        "confirmation_accepted": False,
        "confirmation_enforced": False,
        "backend_plan_persisted": False,
        "controlled_registration_implemented": False,
        "registration_performed": False,
        "record_set_written": False,
        "records_repaired": False,
        "records_migrated": False,
        "automatic_registration_approval_claimed": False,
        "confirmation_accepted_in_this_phase": False,
        "confirmation_enforced_in_this_phase": False,
        "required_future_confirmation": REGISTER_CONFIRMATION,
        "required_future_preconditions": [
            "candidate registration-pipeline QA passed",
            "planning gate passed",
            "backend plan is ready",
            "exact confirmation supplied in future implementation phase",
            "write target isolated",
            "existing registration function available",
            "post-registration load-back required",
            "post-registration record-set QA required",
            "public-safe receipt/report required",
        ],
        "planned_future_execution_steps": planned_future_execution_steps,
        "planned_future_post_registration_checks": planned_future_post_registration_checks,
        "required_future_safeguards": required_future_safeguards,
        "prerequisite_surface_status": {
            "planning_gate_build_available": callable(
                build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_planning_gate
            ),
            "planning_gate_report_available": callable(
                format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_planning_gate_report
            ),
            "registration_pipeline_qa_build_available": callable(
                build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate
            ),
            "registration_pipeline_qa_report_available": callable(
                format_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate_report
            ),
            "record_set_qa_build_available": callable(build_deployed_rule_outcome_truth_record_set_qa_gate),
            "record_set_qa_report_available": callable(format_deployed_rule_outcome_truth_record_set_qa_gate_report),
            "registration_function_available": callable(register_deployed_rule_outcome_truth_record_set),
        },
        "candidate_qa_summary": {
            "candidate_record_count": 0,
            "duplicate_record_count": 0,
            "conflict_count": 0,
            "missing_required_field_count": 0,
            "missing_expected_outcome_count": 0,
            "missing_actual_outcome_count": 0,
            "structurally_ready_for_registration": False,
        },
        "blockers": [],
        "warnings": [],
        "recommended_action": "",
        "limitations": limitations,
        "boundary_flags": boundary_flags,
        "writes_performed": 0,
    }
    planning_gate = build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_planning_gate(
        candidate_copy,
        root=root,
    )
    surface_status = dict(base_payload["prerequisite_surface_status"])
    blockers = list(planning_gate.get("blockers", [])) if isinstance(planning_gate.get("blockers"), list) else []
    warnings = list(planning_gate.get("warnings", [])) if isinstance(planning_gate.get("warnings"), list) else []
    if not surface_status["planning_gate_build_available"]:
        blockers.append("controlled_registration_planning_gate_build_unavailable")
    if not surface_status["planning_gate_report_available"]:
        blockers.append("controlled_registration_planning_gate_report_unavailable")
    if not surface_status["registration_pipeline_qa_build_available"]:
        blockers.append("registration_pipeline_qa_build_unavailable")
    if not surface_status["registration_pipeline_qa_report_available"]:
        blockers.append("registration_pipeline_qa_report_unavailable")
    if not surface_status["record_set_qa_build_available"]:
        blockers.append("record_set_qa_build_unavailable")
    if not surface_status["record_set_qa_report_available"]:
        blockers.append("record_set_qa_report_unavailable")
    if not surface_status["registration_function_available"]:
        blockers.append("registration_function_unavailable")

    planning_gate_status = str(planning_gate.get("status") or "blocked")
    candidate_qa_summary = dict(planning_gate.get("candidate_qa_summary", {})) if isinstance(
        planning_gate.get("candidate_qa_summary"), Mapping
    ) else {}
    candidate_structurally_ready = bool(planning_gate.get("candidate_structurally_ready_for_registration"))
    candidate_qa_status = str(planning_gate.get("candidate_qa_status") or candidate_qa_summary.get("status") or "blocked")
    if planning_gate_status in {"missing", "malformed"}:
        status = planning_gate_status
    elif planning_gate_status != "planning_ready":
        status = "blocked"
        if not blockers:
            blockers.append("controlled_registration_planning_gate_blocked")
    elif blockers:
        status = "blocked"
    else:
        status = "plan_ready"

    recommended_action = (
        "Phase 13B backend planning is ready for a later controlled registration implementation phase without enabling writes here."
        if status == "plan_ready"
        else "Resolve planning-gate or prerequisite-surface blockers before building an executing controlled registration workflow."
    )
    candidate_after_fingerprint = _candidate_fingerprint(candidate_record_set)
    candidate_mutated = candidate_before_fingerprint != candidate_after_fingerprint
    if candidate_mutated:
        status = "blocked"
        blockers.append("candidate_input_mutated_during_plan_build")
    plan = {
        **base_payload,
        "status": status,
        "candidate_fingerprint": candidate_after_fingerprint,
        "planning_gate_fingerprint": _planning_gate_fingerprint(planning_gate),
        "planning_gate_status": planning_gate_status,
        "candidate_qa_status": candidate_qa_status,
        "candidate_structurally_ready_for_registration": candidate_structurally_ready,
        "backend_plan_ready_for_future_execution": status == "plan_ready" and not candidate_mutated,
        "candidate_input_mutated": candidate_mutated,
        "candidate_qa_summary": {
            "candidate_record_count": int(candidate_qa_summary.get("candidate_record_count", 0) or 0),
            "duplicate_record_count": int(candidate_qa_summary.get("duplicate_record_count", 0) or 0),
            "conflict_count": int(candidate_qa_summary.get("conflict_count", 0) or 0),
            "missing_required_field_count": int(candidate_qa_summary.get("missing_required_field_count", 0) or 0),
            "missing_expected_outcome_count": int(candidate_qa_summary.get("missing_expected_outcome_count", 0) or 0),
            "missing_actual_outcome_count": int(candidate_qa_summary.get("missing_actual_outcome_count", 0) or 0),
            "structurally_ready_for_registration": candidate_structurally_ready,
        },
        "blockers": _dedupe(blockers),
        "warnings": _dedupe(warnings),
        "recommended_action": recommended_action,
    }
    plan["backend_plan_fingerprint"] = _backend_plan_fingerprint(plan)
    return plan


def format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_report(
    candidate_record_set: Any,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    backend_plan = build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan(
        candidate_record_set,
        root=root,
    )
    candidate_qa_summary = backend_plan.get("candidate_qa_summary", {})
    prerequisite_surface_status = backend_plan.get("prerequisite_surface_status", {})
    lines = [
        "Controlled outcome-truth record-set registration workflow backend plan",
        f"Status: {backend_plan.get('status')}",
        f"Candidate fingerprint: {backend_plan.get('candidate_fingerprint')}",
        f"Planning-gate fingerprint: {backend_plan.get('planning_gate_fingerprint')}",
        f"Backend-plan fingerprint: {backend_plan.get('backend_plan_fingerprint')}",
        f"Planning gate status: {backend_plan.get('planning_gate_status')}",
        f"Candidate QA status: {backend_plan.get('candidate_qa_status')}",
        "Candidate structurally ready for registration: "
        + str(bool(backend_plan.get("candidate_structurally_ready_for_registration"))).lower(),
        "Backend plan ready for future execution: "
        + str(bool(backend_plan.get("backend_plan_ready_for_future_execution"))).lower(),
        f"Candidate record count: {candidate_qa_summary.get('candidate_record_count', 0)}",
        f"Duplicate record count: {candidate_qa_summary.get('duplicate_record_count', 0)}",
        f"Conflict count: {candidate_qa_summary.get('conflict_count', 0)}",
        f"Missing required field count: {candidate_qa_summary.get('missing_required_field_count', 0)}",
        f"Missing expected outcome count: {candidate_qa_summary.get('missing_expected_outcome_count', 0)}",
        f"Missing actual outcome count: {candidate_qa_summary.get('missing_actual_outcome_count', 0)}",
        "Required future confirmation: "
        + str(backend_plan.get("required_future_confirmation") or REGISTER_CONFIRMATION),
        "Confirmation accepted in this phase: "
        + str(bool(backend_plan.get("confirmation_accepted_in_this_phase"))).lower(),
        "Confirmation enforced in this phase: "
        + str(bool(backend_plan.get("confirmation_enforced_in_this_phase"))).lower(),
        "Execution authorized: " + str(bool(backend_plan.get("execution_authorized"))).lower(),
        "Registration authorized: " + str(bool(backend_plan.get("registration_authorized"))).lower(),
        "Automatic registration approval claimed: "
        + str(bool(backend_plan.get("automatic_registration_approval_claimed"))).lower(),
        "This backend plan is a read-only, non-executing plan for a future controlled outcome-truth record-set registration workflow.",
        "It does not register records.",
        "It does not create record sets.",
        "It does not persist a plan.",
        "It does not create indexes or receipts.",
        "It does not repair records.",
        "It does not migrate records.",
        "It does not accept or enforce confirmation in this phase.",
        "It does not approve automatic registration.",
        "It does not prove factual correctness of outcome-truth records.",
        "It does not establish broad rule effectiveness.",
        "It does not establish deployment safety.",
        "It does not establish production correctness.",
        "It does not establish profitability.",
        "It does not establish prediction quality.",
        "It does not establish future performance.",
        "It does not establish aggregate effectiveness.",
        "It does not establish ranking quality.",
        "The future confirmation is not accepted or enforced in Phase 13B.",
        "A later implementation phase must enforce confirmation before any write.",
        "backend_plan_ready_for_future_execution is structural readiness only.",
        "It is not execution authorization.",
        "It is not registration authorization.",
        "Prerequisite surfaces: "
        + ", ".join(
            f"{key}={str(bool(value)).lower()}" for key, value in sorted(prerequisite_surface_status.items())
        ),
        "Required future preconditions: "
        + ", ".join(str(item) for item in backend_plan.get("required_future_preconditions", [])),
        "Planned future execution steps: "
        + " | ".join(str(item) for item in backend_plan.get("planned_future_execution_steps", [])),
        "Planned future post-registration checks: "
        + ", ".join(str(item) for item in backend_plan.get("planned_future_post_registration_checks", [])),
        "Required future safeguards: "
        + ", ".join(str(item) for item in backend_plan.get("required_future_safeguards", [])),
    ]
    blockers = backend_plan.get("blockers", [])
    warnings = backend_plan.get("warnings", [])
    if isinstance(blockers, list) and blockers:
        lines.append("Blockers: " + ", ".join(str(item) for item in blockers))
    if isinstance(warnings, list) and warnings:
        lines.append("Warnings: " + ", ".join(str(item) for item in warnings))
    recommended_action = backend_plan.get("recommended_action")
    if recommended_action:
        lines.append(f"Recommended action: {recommended_action}")
    limitations = backend_plan.get("limitations", [])
    if isinstance(limitations, list) and limitations:
        lines.append("Limitations: " + "; ".join(str(item) for item in limitations))
    lines.append(f"Writes performed: {backend_plan.get('writes_performed', 0)}")
    return "\n".join(lines)


def validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding(
    backend_plan: Mapping[str, Any],
    candidate_record_set: Any,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    limitations = _outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_limitations()
    boundary_flags = _outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_boundary_flags()
    result = {
        "binding_schema_version": "deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_v1",
        "status": "malformed",
        "binding_valid": False,
        "candidate_binding_valid": False,
        "planning_gate_binding_valid": False,
        "backend_plan_integrity_valid": False,
        "stale_candidate_detected": False,
        "backend_plan_modified_detected": False,
        "missing_identity_field_count": 0,
        "malformed_identity_field_count": 0,
        "expected_candidate_fingerprint": _candidate_fingerprint(candidate_record_set),
        "stored_candidate_fingerprint": None,
        "expected_planning_gate_fingerprint": None,
        "stored_planning_gate_fingerprint": None,
        "expected_backend_plan_fingerprint": None,
        "stored_backend_plan_fingerprint": None,
        "execution_authorized": False,
        "registration_authorized": False,
        "confirmation_accepted": False,
        "confirmation_enforced": False,
        "blockers": [],
        "warnings": [],
        "recommended_action": "",
        "limitations": limitations,
        "boundary_flags": boundary_flags,
        "writes_performed": 0,
    }
    if not isinstance(backend_plan, Mapping):
        result["blockers"] = ["backend_plan_missing_or_malformed"]
        result["missing_identity_field_count"] = 1
        result["recommended_action"] = "Rebuild the backend plan from the current candidate before any later API or UI exposure."
        return result

    identity_fields = [
        "backend_plan_identity_schema_version",
        "candidate_fingerprint_algorithm",
        "planning_gate_fingerprint_algorithm",
        "backend_plan_fingerprint_algorithm",
        "identity_deterministic",
        "identity_public_safe",
        "candidate_fingerprint",
        "planning_gate_fingerprint",
        "backend_plan_fingerprint",
    ]
    missing_fields = [field for field in identity_fields if field not in backend_plan]
    malformed_fields: list[str] = []
    for field in ("candidate_fingerprint", "planning_gate_fingerprint", "backend_plan_fingerprint"):
        value = backend_plan.get(field)
        if not _is_sha256_fingerprint(value):
            malformed_fields.append(field)
    for field in ("candidate_fingerprint_algorithm", "planning_gate_fingerprint_algorithm", "backend_plan_fingerprint_algorithm"):
        if str(backend_plan.get(field) or "") != "sha256":
            malformed_fields.append(field)
    if backend_plan.get("backend_plan_identity_schema_version") != 1:
        malformed_fields.append("backend_plan_identity_schema_version")
    if backend_plan.get("identity_deterministic") is not True:
        malformed_fields.append("identity_deterministic")
    if backend_plan.get("identity_public_safe") is not True:
        malformed_fields.append("identity_public_safe")

    result["missing_identity_field_count"] = len(missing_fields)
    result["malformed_identity_field_count"] = len(dict.fromkeys(malformed_fields))
    result["stored_candidate_fingerprint"] = backend_plan.get("candidate_fingerprint")
    result["stored_planning_gate_fingerprint"] = backend_plan.get("planning_gate_fingerprint")
    result["stored_backend_plan_fingerprint"] = backend_plan.get("backend_plan_fingerprint")

    planning_gate = build_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_planning_gate(
        deepcopy(candidate_record_set),
        root=root,
    )
    result["expected_planning_gate_fingerprint"] = _planning_gate_fingerprint(planning_gate)
    result["expected_backend_plan_fingerprint"] = _backend_plan_fingerprint(backend_plan)

    candidate_match = result["stored_candidate_fingerprint"] == result["expected_candidate_fingerprint"]
    planning_gate_match = result["stored_planning_gate_fingerprint"] == result["expected_planning_gate_fingerprint"]
    backend_plan_match = result["stored_backend_plan_fingerprint"] == result["expected_backend_plan_fingerprint"]

    blockers: list[str] = []
    if missing_fields:
        blockers.extend(f"backend_plan_identity_field_missing:{field}" for field in missing_fields)
    if malformed_fields:
        blockers.extend(f"backend_plan_identity_field_malformed:{field}" for field in dict.fromkeys(malformed_fields))
    if not candidate_match:
        blockers.append("backend_plan_candidate_fingerprint_mismatch")
        result["stale_candidate_detected"] = True
    if not planning_gate_match:
        blockers.append("backend_plan_planning_gate_fingerprint_mismatch")
    if not backend_plan_match:
        blockers.append("backend_plan_fingerprint_mismatch")
        result["backend_plan_modified_detected"] = True

    result["candidate_binding_valid"] = candidate_match and not missing_fields and "candidate_fingerprint" not in malformed_fields
    result["planning_gate_binding_valid"] = planning_gate_match and not missing_fields and "planning_gate_fingerprint" not in malformed_fields
    result["backend_plan_integrity_valid"] = backend_plan_match and not missing_fields and "backend_plan_fingerprint" not in malformed_fields
    result["binding_valid"] = (
        result["candidate_binding_valid"]
        and result["planning_gate_binding_valid"]
        and result["backend_plan_integrity_valid"]
        and not blockers
    )
    if missing_fields or malformed_fields:
        result["status"] = "malformed"
        result["recommended_action"] = "Rebuild the backend plan so deterministic identity fields are restored before exposure."
    elif result["stale_candidate_detected"]:
        result["status"] = "stale"
        result["recommended_action"] = "Rebuild the planning gate and backend plan from the current candidate payload."
    elif result["backend_plan_modified_detected"] or not result["planning_gate_binding_valid"]:
        result["status"] = "modified"
        result["recommended_action"] = "Discard the modified backend plan and rebuild it from the current candidate."
    elif result["binding_valid"]:
        result["status"] = "valid"
        result["recommended_action"] = "Binding is structurally valid, but the plan remains non-executing and non-authoritative."
    else:
        result["status"] = "blocked"
        result["recommended_action"] = "Resolve backend plan binding blockers before any later API or UI seam."
    result["blockers"] = _dedupe(blockers)
    return result


def format_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_report(
    backend_plan: Mapping[str, Any],
    candidate_record_set: Any,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    binding = validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding(
        backend_plan,
        candidate_record_set,
        root=root,
    )
    lines = [
        "Controlled outcome-truth registration backend-plan binding report",
        f"Status: {binding.get('status')}",
        f"Binding valid: {str(bool(binding.get('binding_valid'))).lower()}",
        f"Candidate binding valid: {str(bool(binding.get('candidate_binding_valid'))).lower()}",
        f"Planning-gate binding valid: {str(bool(binding.get('planning_gate_binding_valid'))).lower()}",
        f"Backend-plan integrity valid: {str(bool(binding.get('backend_plan_integrity_valid'))).lower()}",
        f"Stale candidate detected: {str(bool(binding.get('stale_candidate_detected'))).lower()}",
        f"Backend-plan modified detected: {str(bool(binding.get('backend_plan_modified_detected'))).lower()}",
        f"Expected candidate fingerprint: {binding.get('expected_candidate_fingerprint')}",
        f"Stored candidate fingerprint: {binding.get('stored_candidate_fingerprint')}",
        f"Expected planning-gate fingerprint: {binding.get('expected_planning_gate_fingerprint')}",
        f"Stored planning-gate fingerprint: {binding.get('stored_planning_gate_fingerprint')}",
        f"Expected backend-plan fingerprint: {binding.get('expected_backend_plan_fingerprint')}",
        f"Stored backend-plan fingerprint: {binding.get('stored_backend_plan_fingerprint')}",
        "This identity and binding gate proves only deterministic structural binding between a candidate payload, the planning-gate result, and the non-executing backend plan.",
        "It does not authorize registration.",
        "It does not register records.",
        "It does not accept or enforce confirmation.",
        "It does not persist a plan.",
        "It does not prove factual correctness of outcome-truth records.",
        "It does not establish broad rule effectiveness.",
        "It does not establish deployment safety.",
        "It does not establish production correctness.",
        "It does not establish profitability.",
        "It does not establish prediction quality.",
        "It does not establish future performance.",
        "It does not establish aggregate effectiveness.",
        "It does not establish ranking quality.",
        "A valid fingerprint proves integrity against the defined canonical representation only.",
        "It does not prove that the underlying facts are true.",
    ]
    blockers = binding.get("blockers", [])
    warnings = binding.get("warnings", [])
    if isinstance(blockers, list) and blockers:
        lines.append("Blockers: " + ", ".join(str(item) for item in blockers))
    if isinstance(warnings, list) and warnings:
        lines.append("Warnings: " + ", ".join(str(item) for item in warnings))
    recommended_action = binding.get("recommended_action")
    if recommended_action:
        lines.append(f"Recommended action: {recommended_action}")
    limitations = binding.get("limitations", [])
    if isinstance(limitations, list) and limitations:
        lines.append("Limitations: " + "; ".join(str(item) for item in limitations))
    lines.append(f"Writes performed: {binding.get('writes_performed', 0)}")
    return "\n".join(lines)


def build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_planning_gate(
    backend_plan: Mapping[str, Any],
    candidate_record_set: Any,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    limitations = _outcome_truth_record_set_controlled_registration_execution_planning_limitations()
    boundary_flags = _outcome_truth_record_set_controlled_registration_execution_planning_boundary_flags()
    required_future_confirmation = REGISTER_CONFIRMATION
    required_future_preconditions = [
        "candidate registration-pipeline QA passed",
        "Phase 13 backend plan exists",
        "Phase 13 backend-plan binding is valid",
        "candidate is not stale",
        "backend plan is not modified",
        "planning-gate binding is valid",
        "backend-plan integrity is valid",
        "structural backend-plan readiness is true",
        "registration function is available",
        "post-registration loader is available",
        "post-registration QA gate is available",
        "isolated write target is resolved",
        "deterministic candidate fingerprint is preserved",
        "deterministic backend-plan fingerprint is preserved",
        "exact confirmation is supplied in a later phase",
        "idempotency contract is satisfied in a later phase",
    ]
    required_future_transaction_properties = [
        "explicit transaction boundary",
        "single controlled registration attempt per idempotency identity",
        "no partial-success ambiguity",
        "pre-write verification immediately before mutation",
        "exact confirmation immediately before mutation",
        "registration through the existing canonical registration function",
        "post-write load-back",
        "post-write QA",
        "deterministic outcome classification",
        "immutable public-safe receipt",
        "no automatic retry after ambiguous write result",
        "no silent repair",
        "no truth override",
        "no scoring authority",
    ]
    required_future_idempotency_contract = [
        "derive identity from candidate_fingerprint",
        "derive identity from planning_gate_fingerprint",
        "derive identity from backend_plan_fingerprint",
        "bind identity to execution-contract schema version",
        "bind identity to target registration scope or record-set identity",
        "completed identical transaction returns already_completed",
        "ambiguous prior attempt blocks automatic retry",
        "conflicting identity blocks reuse",
        "no caller-supplied idempotency authority",
    ]
    required_future_pre_write_verifications = [
        "re-parse current candidate",
        "recompute current candidate fingerprint",
        "revalidate backend-plan binding",
        "confirm no stale candidate",
        "confirm no plan modification",
        "confirm planning-gate binding",
        "confirm backend-plan integrity",
        "rerun registration-pipeline QA",
        "confirm structural readiness",
        "resolve isolated target",
        "confirm target does not already contain a conflicting registration",
        "confirm registration function availability",
        "confirm exact future confirmation",
        "confirm idempotency state",
        "capture pre-write target state or absence",
        "confirm no write has occurred yet",
    ]
    required_future_write_boundary = [
        "one canonical registration function call",
        "one isolated write target",
        "one mutation boundary after exact confirmation",
        "no auxiliary write helpers outside the canonical boundary",
        "no second write after ambiguous first outcome",
    ]
    required_future_post_write_verifications = [
        "load back the registered record set",
        "confirm registered record-set identity",
        "confirm deterministic candidate fingerprint continuity",
        "confirm deterministic backend-plan fingerprint continuity",
        "run post-registration record-set QA",
        "confirm no duplicate or conflict blockers after registration",
        "produce public-safe result and immutable receipt",
        "do not classify post-write verification failure as clean success",
    ]
    required_future_failure_states = [
        "pre_write_blocked",
        "confirmation_missing_or_mismatched",
        "write_not_attempted",
        "write_attempted_ambiguous",
        "write_attempted_loadback_missing",
        "write_attempted_post_write_qa_failed",
        "already_completed",
        "conflicting_completed_state",
        "manual_review_required",
    ]
    required_future_recovery_contract = [
        "ambiguous future write outcomes must block automatic retry",
        "already_completed requires zero additional writes",
        "post-write verification failure must not be reported as clean success",
        "conflicting completed state requires manual review",
        "rollback support is not assumed",
    ]
    required_future_receipt_contract = [
        "transaction schema version",
        "candidate fingerprint",
        "planning-gate fingerprint",
        "backend-plan fingerprint",
        "pre-write verification result",
        "exact confirmation matched yes/no",
        "registration function invoked yes/no",
        "registration attempt count",
        "post-write load-back result",
        "post-write QA result",
        "final transaction state",
        "writes performed",
        "blockers",
        "warnings",
        "limitations",
        "no-overclaim boundary flags",
    ]
    planned_future_execution_sequence = [
        "1. Accept current candidate and frozen backend plan.",
        "2. Revalidate deterministic backend-plan binding.",
        "3. Rerun registration-pipeline QA.",
        "4. Resolve the isolated registration target.",
        "5. Build the future transactional execution plan.",
        "6. Derive and check future idempotency identity.",
        "7. Run all pre-write verifications.",
        "8. Require exact confirmation immediately before mutation.",
        "9. Call the canonical registration function once.",
        "10. Load back the registered record set.",
        "11. Run post-registration record-set QA.",
        "12. Classify committed or ambiguous state.",
        "13. Produce public-safe result and immutable receipt.",
        "14. Return already_completed with zero writes for an identical completed transaction.",
        "15. Never claim factual truth correctness.",
    ]
    base_payload = {
        "execution_planning_gate_schema_version": 1,
        "execution_planning_gate_type": "controlled_outcome_truth_record_set_registration_execution_planning_gate",
        "status": "missing",
        "backend_plan_status": "missing",
        "binding_status": "blocked",
        "binding_valid": False,
        "candidate_binding_valid": False,
        "planning_gate_binding_valid": False,
        "backend_plan_integrity_valid": False,
        "stale_candidate_detected": False,
        "backend_plan_modified_detected": False,
        "ready_to_design_future_execution_contract": False,
        "future_execution_contract_implemented": False,
        "transaction_implemented": False,
        "registration_execution_implemented": False,
        "required_future_confirmation": required_future_confirmation,
        "confirmation_accepted_in_this_phase": False,
        "confirmation_enforced_in_this_phase": False,
        "execution_authorized": False,
        "registration_authorized": False,
        "automatic_registration_approval_claimed": False,
        "registration_performed": False,
        "record_set_written": False,
        "records_repaired": False,
        "records_migrated": False,
        "execution_plan_persisted": False,
        "idempotency_record_created": False,
        "transaction_created": False,
        "receipt_created": False,
        "required_future_preconditions": required_future_preconditions,
        "required_future_transaction_properties": required_future_transaction_properties,
        "required_future_idempotency_contract": required_future_idempotency_contract,
        "required_future_pre_write_verifications": required_future_pre_write_verifications,
        "required_future_write_boundary": required_future_write_boundary,
        "required_future_post_write_verifications": required_future_post_write_verifications,
        "required_future_failure_states": required_future_failure_states,
        "required_future_recovery_contract": required_future_recovery_contract,
        "required_future_receipt_contract": required_future_receipt_contract,
        "planned_future_execution_sequence": planned_future_execution_sequence,
        "prerequisite_surface_status": {
            "binding_validator_available": callable(
                validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding
            ),
            "registration_pipeline_qa_build_available": callable(
                build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate
            ),
            "registration_function_available": callable(register_deployed_rule_outcome_truth_record_set),
            "post_registration_loader_available": callable(load_deployed_rule_outcome_truth_record_set),
            "post_registration_qa_build_available": callable(build_deployed_rule_outcome_truth_record_set_qa_gate),
            "structural_backend_plan_ready": False,
        },
        "blockers": [],
        "warnings": [],
        "recommended_action": "",
        "limitations": limitations,
        "boundary_flags": boundary_flags,
        "writes_performed": 0,
    }
    if candidate_record_set is None:
        return {
            **base_payload,
            "status": "missing",
            "blockers": ["candidate_record_set_required"],
            "recommended_action": "Provide the current candidate payload before evaluating future registration execution planning.",
        }
    if not isinstance(candidate_record_set, Mapping):
        return {
            **base_payload,
            "status": "malformed",
            "blockers": ["candidate_record_set_malformed"],
            "recommended_action": "Provide the current candidate payload in the current canonical mapping shape before evaluating future registration execution planning.",
        }
    candidate_records = candidate_record_set.get("records")
    if not isinstance(candidate_records, (list, tuple)) or any(
        not isinstance(item, Mapping) for item in candidate_records
    ):
        return {
            **base_payload,
            "status": "malformed",
            "blockers": ["candidate_record_set_malformed"],
            "recommended_action": "Provide the current candidate payload in the current canonical mapping shape before evaluating future registration execution planning.",
        }
    if backend_plan is None:
        return {
            **base_payload,
            "status": "missing",
            "blockers": ["backend_plan_required"],
            "recommended_action": "Build the frozen Phase 13 backend plan before evaluating future registration execution planning.",
        }
    if not isinstance(backend_plan, Mapping):
        return {
            **base_payload,
            "status": "malformed",
            "blockers": ["backend_plan_malformed"],
            "recommended_action": "Provide a valid frozen Phase 13 backend plan before evaluating future registration execution planning.",
        }
    required_backend_plan_fields = (
        "backend_plan_identity_schema_version",
        "candidate_fingerprint",
        "planning_gate_fingerprint",
        "backend_plan_fingerprint",
        "backend_plan_ready_for_future_execution",
        "status",
    )
    if any(field not in backend_plan for field in required_backend_plan_fields):
        return {
            **base_payload,
            "status": "malformed",
            "blockers": ["backend_plan_malformed"],
            "recommended_action": "Provide a valid frozen Phase 13 backend plan before evaluating future registration execution planning.",
        }

    prerequisite_surface_status = dict(base_payload["prerequisite_surface_status"])
    prerequisite_surface_status["structural_backend_plan_ready"] = bool(
        backend_plan.get("backend_plan_ready_for_future_execution")
    )
    unavailable_blockers: list[str] = []
    if not prerequisite_surface_status["binding_validator_available"]:
        unavailable_blockers.append("backend_plan_binding_validator_unavailable")
    if not prerequisite_surface_status["registration_pipeline_qa_build_available"]:
        unavailable_blockers.append("registration_pipeline_qa_build_unavailable")
    if not prerequisite_surface_status["registration_function_available"]:
        unavailable_blockers.append("registration_function_unavailable")
    if not prerequisite_surface_status["post_registration_loader_available"]:
        unavailable_blockers.append("post_registration_loader_unavailable")
    if not prerequisite_surface_status["post_registration_qa_build_available"]:
        unavailable_blockers.append("post_registration_qa_build_unavailable")
    if unavailable_blockers:
        return {
            **base_payload,
            "status": "blocked",
            "backend_plan_status": str(backend_plan.get("status") or "unknown"),
            "prerequisite_surface_status": prerequisite_surface_status,
            "blockers": _dedupe(unavailable_blockers),
            "recommended_action": "Resolve frozen binding, candidate QA, structural readiness, or prerequisite-surface blockers before designing the future transactional registration workflow.",
        }

    candidate_before_fingerprint = _candidate_fingerprint(candidate_record_set)
    backend_plan_before_fingerprint = _hash_payload(_canonicalize_for_identity(dict(backend_plan)))
    binding = validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding(
        backend_plan,
        deepcopy(candidate_record_set),
        root=root,
    )
    candidate_qa = build_deployed_rule_outcome_truth_record_set_registration_pipeline_qa_gate(
        deepcopy(candidate_record_set),
        root=root,
    )
    candidate_after_fingerprint = _candidate_fingerprint(candidate_record_set)
    backend_plan_after_fingerprint = _hash_payload(_canonicalize_for_identity(dict(backend_plan)))

    candidate_qa_status = str(candidate_qa.get("status") or "blocked")
    binding_status = str(binding.get("status") or "blocked")
    structural_backend_plan_ready = bool(backend_plan.get("backend_plan_ready_for_future_execution"))
    prerequisite_surface_status["structural_backend_plan_ready"] = structural_backend_plan_ready

    blockers = list(candidate_qa.get("blockers", [])) if isinstance(candidate_qa.get("blockers"), list) else []
    blockers.extend(list(binding.get("blockers", [])) if isinstance(binding.get("blockers"), list) else [])
    warnings = list(candidate_qa.get("warnings", [])) if isinstance(candidate_qa.get("warnings"), list) else []
    warnings.extend(list(binding.get("warnings", [])) if isinstance(binding.get("warnings"), list) else [])

    if not prerequisite_surface_status["binding_validator_available"]:
        blockers.append("backend_plan_binding_validator_unavailable")
    if not prerequisite_surface_status["registration_pipeline_qa_build_available"]:
        blockers.append("registration_pipeline_qa_build_unavailable")
    if not prerequisite_surface_status["registration_function_available"]:
        blockers.append("registration_function_unavailable")
    if not prerequisite_surface_status["post_registration_loader_available"]:
        blockers.append("post_registration_loader_unavailable")
    if not prerequisite_surface_status["post_registration_qa_build_available"]:
        blockers.append("post_registration_qa_build_unavailable")
    if not structural_backend_plan_ready:
        blockers.append("backend_plan_structural_readiness_required")
    if candidate_before_fingerprint != candidate_after_fingerprint:
        blockers.append("candidate_input_mutated_during_execution_planning_gate")
    if backend_plan_before_fingerprint != backend_plan_after_fingerprint:
        blockers.append("backend_plan_input_mutated_during_execution_planning_gate")

    if candidate_qa_status in {"missing", "malformed"}:
        status = candidate_qa_status
    elif binding_status in {"malformed", "stale", "modified"}:
        status = binding_status
    elif not bool(binding.get("binding_valid")):
        status = "blocked"
    elif candidate_qa_status != "passed" or not bool(candidate_qa.get("structurally_ready_for_registration")):
        status = "blocked"
    elif blockers:
        status = "blocked"
    else:
        status = "planning_ready"

    recommended_action = (
        "Phase 14A planning prerequisites are present. A later read-only transaction-plan phase can define execution intent without enabling writes here."
        if status == "planning_ready"
        else "Resolve frozen binding, candidate QA, structural readiness, or prerequisite-surface blockers before designing the future transactional registration workflow."
    )

    return {
        **base_payload,
        "status": status,
        "backend_plan_status": str(backend_plan.get("status") or "unknown"),
        "binding_status": binding_status,
        "binding_valid": bool(binding.get("binding_valid")),
        "candidate_binding_valid": bool(binding.get("candidate_binding_valid")),
        "planning_gate_binding_valid": bool(binding.get("planning_gate_binding_valid")),
        "backend_plan_integrity_valid": bool(binding.get("backend_plan_integrity_valid")),
        "stale_candidate_detected": bool(binding.get("stale_candidate_detected")),
        "backend_plan_modified_detected": bool(binding.get("backend_plan_modified_detected")),
        "ready_to_design_future_execution_contract": status == "planning_ready",
        "prerequisite_surface_status": prerequisite_surface_status,
        "blockers": _dedupe(blockers),
        "warnings": _dedupe(warnings),
        "recommended_action": recommended_action,
    }


def format_deployed_rule_outcome_truth_record_set_controlled_registration_execution_planning_gate_report(
    backend_plan: Mapping[str, Any],
    candidate_record_set: Any,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    planning_gate = build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_planning_gate(
        backend_plan,
        candidate_record_set,
        root=root,
    )
    prerequisite_surface_status = planning_gate.get("prerequisite_surface_status", {})
    lines = [
        "Controlled outcome-truth record-set registration execution planning gate",
        f"Status: {planning_gate.get('status')}",
        f"Backend-plan status: {planning_gate.get('backend_plan_status')}",
        f"Binding status: {planning_gate.get('binding_status')}",
        f"Binding valid: {str(bool(planning_gate.get('binding_valid'))).lower()}",
        f"Candidate binding valid: {str(bool(planning_gate.get('candidate_binding_valid'))).lower()}",
        f"Planning-gate binding valid: {str(bool(planning_gate.get('planning_gate_binding_valid'))).lower()}",
        f"Backend-plan integrity valid: {str(bool(planning_gate.get('backend_plan_integrity_valid'))).lower()}",
        f"Stale candidate detected: {str(bool(planning_gate.get('stale_candidate_detected'))).lower()}",
        f"Backend-plan modified detected: {str(bool(planning_gate.get('backend_plan_modified_detected'))).lower()}",
        "Ready to design future execution contract: "
        + str(bool(planning_gate.get("ready_to_design_future_execution_contract"))).lower(),
        "Required future confirmation: "
        + str(planning_gate.get("required_future_confirmation") or REGISTER_CONFIRMATION),
        "Confirmation accepted in this phase: "
        + str(bool(planning_gate.get("confirmation_accepted_in_this_phase"))).lower(),
        "Confirmation enforced in this phase: "
        + str(bool(planning_gate.get("confirmation_enforced_in_this_phase"))).lower(),
        "Execution authorized: " + str(bool(planning_gate.get("execution_authorized"))).lower(),
        "Registration authorized: " + str(bool(planning_gate.get("registration_authorized"))).lower(),
        "Registration performed: " + str(bool(planning_gate.get("registration_performed"))).lower(),
        "This planning gate defines planning requirements for a future transactional registration execution workflow.",
        "Phase 14A does not execute registration.",
        "Phase 14A does not call the registration function.",
        "Phase 14A does not create a transaction, idempotency record, execution plan, or receipt.",
        "Phase 14A does not accept or enforce confirmation.",
        "Structural readiness and valid binding are not execution authorization.",
        "Structural readiness and valid binding are not registration authorization.",
        "The future confirmation phrase is advisory only in this phase.",
        "Ambiguous future write outcomes must block automatic retry.",
        "Post-write verification failure must not be reported as clean success.",
        "A valid fingerprint or binding does not prove factual correctness of outcome-truth records.",
        "Prerequisite surfaces: "
        + ", ".join(
            f"{key}={str(bool(value)).lower()}" for key, value in sorted(prerequisite_surface_status.items())
        ),
        "Required future preconditions: "
        + ", ".join(str(item) for item in planning_gate.get("required_future_preconditions", [])),
        "Required future transaction properties: "
        + ", ".join(str(item) for item in planning_gate.get("required_future_transaction_properties", [])),
        "Required future idempotency contract: "
        + ", ".join(str(item) for item in planning_gate.get("required_future_idempotency_contract", [])),
        "Required future pre-write verifications: "
        + ", ".join(str(item) for item in planning_gate.get("required_future_pre_write_verifications", [])),
        "Required future write boundary: "
        + ", ".join(str(item) for item in planning_gate.get("required_future_write_boundary", [])),
        "Required future post-write verifications: "
        + ", ".join(str(item) for item in planning_gate.get("required_future_post_write_verifications", [])),
        "Required future failure states: "
        + ", ".join(str(item) for item in planning_gate.get("required_future_failure_states", [])),
        "Required future recovery contract: "
        + ", ".join(str(item) for item in planning_gate.get("required_future_recovery_contract", [])),
        "Required future receipt contract: "
        + ", ".join(str(item) for item in planning_gate.get("required_future_receipt_contract", [])),
        "Planned future execution sequence: "
        + " | ".join(str(item) for item in planning_gate.get("planned_future_execution_sequence", [])),
    ]
    blockers = planning_gate.get("blockers", [])
    warnings = planning_gate.get("warnings", [])
    if isinstance(blockers, list) and blockers:
        lines.append("Blockers: " + ", ".join(str(item) for item in blockers))
    if isinstance(warnings, list) and warnings:
        lines.append("Warnings: " + ", ".join(str(item) for item in warnings))
    recommended_action = planning_gate.get("recommended_action")
    if recommended_action:
        lines.append(f"Recommended action: {recommended_action}")
    limitations = planning_gate.get("limitations", [])
    if isinstance(limitations, list) and limitations:
        lines.append("Limitations: " + "; ".join(str(item) for item in limitations))
    lines.append(f"Writes performed: {planning_gate.get('writes_performed', 0)}")
    return "\n".join(lines)


def build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan(
    backend_plan: Mapping[str, Any],
    candidate_record_set: Any,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    limitations = _outcome_truth_record_set_controlled_registration_transaction_plan_limitations()
    boundary_flags = _outcome_truth_record_set_controlled_registration_transaction_plan_boundary_flags()
    planned_pre_write_verifications = [
        "parse current candidate",
        "recompute candidate fingerprint",
        "revalidate Phase 13 backend-plan binding",
        "confirm candidate is not stale",
        "confirm backend plan is not modified",
        "confirm planning-gate binding",
        "confirm backend-plan integrity",
        "rerun registration-pipeline QA",
        "confirm structural readiness",
        "derive deterministic target identity",
        "verify target identity is complete and unambiguous",
        "inspect target state through a non-creating read path if safely available",
        "detect known target conflict if safely available",
        "confirm registration function availability",
        "confirm post-registration loader availability",
        "confirm post-registration QA availability",
        "recompute transaction-plan fingerprint",
        "recompute idempotency preview",
        "require future exact confirmation",
        "require future idempotency enforcement",
        "verify writes_performed is still 0",
    ]
    planned_post_write_verifications = [
        "load registered record set using canonical loader",
        "confirm registered target identity exists",
        "compare registered identity with transaction target",
        "compare expected record count",
        "verify candidate fingerprint or equivalent stable identity",
        "run post-registration record-set QA gate",
        "classify committed state",
        "classify committed-with-verification-failure separately",
        "produce public-safe transaction result",
        "produce immutable receipt",
        "preserve exact idempotency identity",
        "preserve no-overclaim boundary",
    ]
    planned_failure_states = [
        "pre_write_blocked",
        "target_identity_missing",
        "target_identity_ambiguous",
        "target_identity_conflict",
        "target_conflict_detected",
        "target_state_unknown",
        "confirmation_missing_or_mismatched",
        "idempotency_conflict",
        "already_completed",
        "write_attempted_ambiguous",
        "write_attempted_post_write_qa_failed",
        "manual_review_required",
    ]
    planned_recovery_requirements = [
        "no automatic retry after ambiguous_registration_result",
        "no silent second registration attempt",
        "no automatic candidate repair",
        "no automatic plan repair",
        "no automatic fingerprint replacement",
        "no rollback claim unless separately supported and verified",
        "already_completed must perform zero additional writes",
        "target conflict must block",
        "idempotency conflict must block",
        "post-write verification failure is not clean success",
        "ambiguous result requires operator review",
    ]
    planned_receipt_fields = [
        "receipt_schema_version",
        "transaction_identity",
        "idempotency_identity",
        "candidate_fingerprint",
        "planning_gate_fingerprint",
        "backend_plan_fingerprint",
        "target_identity_fingerprint",
        "transaction_plan_fingerprint",
        "pre_write_verification_result",
        "exact_confirmation_matched",
        "registration_function_invoked",
        "registration_attempt_count",
        "post_write_load_back_result",
        "post_write_qa_result",
        "final_transaction_state",
        "writes_performed",
        "blockers",
        "warnings",
        "limitations",
        "boundary_flags",
    ]
    planned_execution_sequence = [
        "1. Accept current candidate, frozen backend plan, and planning-gate result.",
        "2. Revalidate Phase 13 backend-plan binding.",
        "3. Rebuild target identity deterministically.",
        "4. Recompute target-identity fingerprint.",
        "5. Recompute the non-authoritative idempotency-key preview.",
        "6. Recompute the transaction-plan fingerprint.",
        "7. Rerun all read-only pre-write checks.",
        "8. Require exact confirmation in a later execution phase.",
        "9. Require enforced idempotency in a later execution phase.",
        "10. Call register_deployed_rule_outcome_truth_record_set once in a later execution phase.",
        "11. Load back the registered record set in a later execution phase.",
        "12. Run post-registration record-set QA in a later execution phase.",
        "13. Classify committed, already_completed, or ambiguous outcomes in a later execution phase.",
        "14. Produce a public-safe result and immutable receipt in a later execution phase.",
        "15. Never claim factual truth correctness.",
    ]
    base_payload = {
        "transaction_plan_schema_version": 1,
        "transaction_plan_type": "controlled_outcome_truth_record_set_registration_transaction_plan",
        "status": "missing",
        "execution_planning_gate_status": "missing",
        "backend_plan_status": "missing",
        "binding_status": "blocked",
        "candidate_fingerprint": _candidate_fingerprint(candidate_record_set),
        "planning_gate_fingerprint": _text((backend_plan or {}).get("planning_gate_fingerprint")) if isinstance(backend_plan, Mapping) else None,
        "backend_plan_fingerprint": _text((backend_plan or {}).get("backend_plan_fingerprint")) if isinstance(backend_plan, Mapping) else None,
        "target_identity_schema_version": 1,
        "target_identity": {},
        "target_identity_fingerprint": None,
        "target_state_at_plan_time": "target_state_unknown",
        "target_state_observation_available": False,
        "target_state_observation_status": "target_state_check_unavailable",
        "target_state_observation_basis": "target_state_check_unavailable",
        "target_state_snapshot": {},
        "target_state_snapshot_fingerprint": None,
        "target_state_snapshot_fingerprint_algorithm": "sha256",
        "target_state_snapshot_deterministic": True,
        "target_state_snapshot_public_safe": True,
        "target_state_freshness_proven_at_plan_time": False,
        "transaction_plan_fingerprint": None,
        "transaction_plan_fingerprint_algorithm": "sha256",
        "transaction_plan_deterministic": True,
        "transaction_plan_public_safe": True,
        "transaction_plan_ready": False,
        "dry_run_eligible": False,
        "transaction_plan_persisted": False,
        "transaction_created": False,
        "transaction_id_created": False,
        "receipt_created": False,
        "idempotency_key_preview": None,
        "idempotency_key_preview_algorithm": "sha256",
        "idempotency_key_preview_authoritative": False,
        "idempotency_key_preview_persisted": False,
        "idempotency_enforced": False,
        "required_future_confirmation": REGISTER_CONFIRMATION,
        "confirmation_accepted_in_this_phase": False,
        "confirmation_enforced_in_this_phase": False,
        "execution_authorized": False,
        "registration_authorized": False,
        "registration_execution_implemented": False,
        "registration_performed": False,
        "record_set_written": False,
        "records_repaired": False,
        "records_migrated": False,
        "automatic_registration_approval_claimed": False,
        "planned_write_function": "register_deployed_rule_outcome_truth_record_set",
        "planned_write_count": 1,
        "planned_pre_write_verifications": planned_pre_write_verifications,
        "planned_post_write_verifications": planned_post_write_verifications,
        "planned_failure_states": planned_failure_states,
        "planned_recovery_requirements": planned_recovery_requirements,
        "planned_receipt_fields": planned_receipt_fields,
        "planned_execution_sequence": planned_execution_sequence,
        "blockers": [],
        "warnings": [],
        "recommended_action": "",
        "limitations": limitations,
        "boundary_flags": boundary_flags,
        "writes_performed": 0,
    }
    planning_gate = build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_planning_gate(
        backend_plan,
        deepcopy(candidate_record_set),
        root=root,
    )
    planning_gate_status = str(planning_gate.get("status") or "blocked")
    if planning_gate_status != "planning_ready" or not bool(planning_gate.get("ready_to_design_future_execution_contract")):
        return {
            **base_payload,
            "status": planning_gate_status if planning_gate_status in {"missing", "malformed", "stale", "modified"} else "blocked",
            "execution_planning_gate_status": planning_gate_status,
            "backend_plan_status": str((backend_plan or {}).get("status") or "missing") if isinstance(backend_plan, Mapping) else "missing",
            "binding_status": str(planning_gate.get("binding_status") or "blocked"),
            "blockers": _dedupe(
                list(planning_gate.get("blockers", [])) + ["execution_planning_gate_not_ready_for_transaction_plan"]
            ),
            "warnings": list(planning_gate.get("warnings", [])) if isinstance(planning_gate.get("warnings"), list) else [],
            "recommended_action": "Resolve Phase 14A execution-planning blockers before building a future transaction-plan preview.",
        }
    target_identity_result = _build_controlled_registration_transaction_target_identity(
        candidate_record_set,
        root=root,
    )
    target_status = str(target_identity_result.get("status") or "blocked")
    if target_status != "ready":
        return {
            **base_payload,
            "status": "blocked",
            "execution_planning_gate_status": planning_gate_status,
            "backend_plan_status": str(backend_plan.get("status") or "unknown"),
            "binding_status": str(planning_gate.get("binding_status") or "blocked"),
            "blockers": _dedupe(list(target_identity_result.get("blockers", []))),
            "warnings": list(target_identity_result.get("warnings", [])) if isinstance(target_identity_result.get("warnings"), list) else [],
            "recommended_action": "Resolve target-identity completeness, ambiguity, or conflict blockers before relying on a transaction-plan preview.",
        }

    target_identity = deepcopy(target_identity_result["target_identity"])
    target_identity_fingerprint = str(target_identity_result["target_identity_fingerprint"])
    planned_registration_scope = deepcopy(target_identity.get("registration_scope", {}))
    target_state_snapshot = _build_controlled_registration_target_state_snapshot(
        {
            "target_identity": target_identity,
            "target_identity_fingerprint": target_identity_fingerprint,
        },
        root=root,
    )
    idempotency_key_preview = _build_controlled_registration_transaction_idempotency_preview(
        candidate_fingerprint=str(base_payload["candidate_fingerprint"] or ""),
        planning_gate_fingerprint=str(base_payload["planning_gate_fingerprint"] or ""),
        backend_plan_fingerprint=str(base_payload["backend_plan_fingerprint"] or ""),
        target_identity_fingerprint=target_identity_fingerprint,
        planned_write_function="register_deployed_rule_outcome_truth_record_set",
        planned_registration_scope=planned_registration_scope,
    )

    transaction_plan = {
        **base_payload,
        "status": "transaction_plan_ready",
        "execution_planning_gate_status": planning_gate_status,
        "backend_plan_status": str(backend_plan.get("status") or "unknown"),
        "binding_status": str(planning_gate.get("binding_status") or "blocked"),
        "target_identity": target_identity,
        "target_identity_fingerprint": target_identity_fingerprint,
        "target_state_at_plan_time": target_state_snapshot.get("target_state"),
        "target_state_observation_available": bool(target_state_snapshot.get("read_path_available")),
        "target_state_observation_status": str(target_state_snapshot.get("observation_status") or "target_state_check_unavailable"),
        "target_state_observation_basis": str(target_state_snapshot.get("observation_basis") or "target_state_check_unavailable"),
        "target_state_snapshot": target_state_snapshot,
        "target_state_snapshot_fingerprint": target_state_snapshot.get("target_state_snapshot_fingerprint"),
        "target_state_freshness_proven_at_plan_time": False,
        "transaction_plan_fingerprint": None,
        "transaction_plan_ready": True,
        "dry_run_eligible": True,
        "idempotency_key_preview": idempotency_key_preview,
        "recommended_action": "Phase 14B defines a deterministic read-only transaction-plan preview. A later integrity phase can validate target binding and stale-target behavior without enabling writes.",
    }
    transaction_plan["transaction_plan_fingerprint"] = _compute_controlled_registration_transaction_plan_fingerprint(
        transaction_plan
    )
    return transaction_plan


def format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_report(
    backend_plan: Mapping[str, Any],
    candidate_record_set: Any,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    plan = build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan(
        backend_plan,
        candidate_record_set,
        root=root,
    )
    target_identity = plan.get("target_identity", {})
    lines = [
        "Controlled outcome-truth registration transaction-plan preview",
        f"Status: {plan.get('status')}",
        f"Execution-planning gate status: {plan.get('execution_planning_gate_status')}",
        f"Backend-plan status: {plan.get('backend_plan_status')}",
        f"Binding status: {plan.get('binding_status')}",
        f"Transaction-plan ready: {str(bool(plan.get('transaction_plan_ready'))).lower()}",
        f"Dry-run eligible: {str(bool(plan.get('dry_run_eligible'))).lower()}",
        f"Candidate fingerprint: {plan.get('candidate_fingerprint')}",
        f"Planning-gate fingerprint: {plan.get('planning_gate_fingerprint')}",
        f"Backend-plan fingerprint: {plan.get('backend_plan_fingerprint')}",
        "Target identity summary: "
        + ", ".join(
            [
                f"record_set_id={target_identity.get('record_set_id') or 'none'}",
                f"source_id={((target_identity.get('registration_scope') or {}).get('source_id') or 'none')}",
                f"deployed_rule_id={((target_identity.get('registration_scope') or {}).get('deployed_rule_id') or 'none')}",
            ]
        ),
        f"Target-identity fingerprint: {plan.get('target_identity_fingerprint')}",
        f"Target state at plan time: {plan.get('target_state_at_plan_time')}",
        f"Target-state observation status: {plan.get('target_state_observation_status')}",
        f"Target-state observation basis: {plan.get('target_state_observation_basis')}",
        f"Target-state observation available: {str(bool(plan.get('target_state_observation_available'))).lower()}",
        f"Target-state snapshot fingerprint: {plan.get('target_state_snapshot_fingerprint')}",
        f"Transaction-plan fingerprint: {plan.get('transaction_plan_fingerprint')}",
        f"Non-authoritative idempotency preview: {plan.get('idempotency_key_preview')}",
        f"Required future confirmation: {plan.get('required_future_confirmation') or REGISTER_CONFIRMATION}",
        f"Planned write function: {plan.get('planned_write_function')}",
        f"Planned write count: {plan.get('planned_write_count')}",
        "Phase 14B builds a deterministic in-memory transaction-plan preview and evaluates it through a read-only dry run.",
        "Phase 14B does not call the registration function.",
        "Phase 14B performs zero writes.",
        "Phase 14B does not create or persist a transaction, idempotency record, execution plan, dry-run result, or receipt.",
        "The idempotency-key preview is deterministic planning metadata only.",
        "It is not authoritative, persisted, reserved, or enforced.",
        "planned_write_count = 1 describes future intent only.",
        "writes_performed = 0 records actual Phase 14B behavior.",
        "A passing dry run does not authorize execution.",
        "A passing dry run does not authorize registration.",
        "A passing dry run does not accept or enforce confirmation.",
        "A passing dry run does not prove the future registration will succeed.",
        "A valid fingerprint proves integrity against the defined canonical representation only.",
        "It does not prove factual correctness of outcome-truth records.",
        "Unknown target state must be reported conservatively.",
        "Ambiguous future write outcomes must block automatic retry.",
        "Post-write verification failure must not be classified as clean success.",
        "Planned pre-write checks: " + ", ".join(str(item) for item in plan.get("planned_pre_write_verifications", [])),
        "Planned post-write checks: " + ", ".join(str(item) for item in plan.get("planned_post_write_verifications", [])),
        "Failure states: " + ", ".join(str(item) for item in plan.get("planned_failure_states", [])),
        "Recovery contract: " + ", ".join(str(item) for item in plan.get("planned_recovery_requirements", [])),
        "Receipt contract: " + ", ".join(str(item) for item in plan.get("planned_receipt_fields", [])),
        "Planned execution sequence: " + " | ".join(str(item) for item in plan.get("planned_execution_sequence", [])),
    ]
    blockers = plan.get("blockers", [])
    warnings = plan.get("warnings", [])
    if isinstance(blockers, list) and blockers:
        lines.append("Blockers: " + ", ".join(str(item) for item in blockers))
    if isinstance(warnings, list) and warnings:
        lines.append("Warnings: " + ", ".join(str(item) for item in warnings))
    if plan.get("recommended_action"):
        lines.append(f"Recommended action: {plan.get('recommended_action')}")
    limitations = plan.get("limitations", [])
    if isinstance(limitations, list) and limitations:
        lines.append("Limitations: " + "; ".join(str(item) for item in limitations))
    lines.append(f"Writes performed: {plan.get('writes_performed', 0)}")
    return "\n".join(lines)


def run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run(
    transaction_plan: Mapping[str, Any],
    backend_plan: Mapping[str, Any],
    candidate_record_set: Any,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    limitations = _outcome_truth_record_set_controlled_registration_transaction_dry_run_limitations()
    boundary_flags = _outcome_truth_record_set_controlled_registration_transaction_dry_run_boundary_flags()
    base_payload = {
        "dry_run_schema_version": 1,
        "dry_run_type": "controlled_outcome_truth_record_set_registration_transaction_dry_run",
        "status": "missing",
        "dry_run": True,
        "dry_run_passed": False,
        "transaction_plan_status": "missing",
        "transaction_plan_integrity_valid": False,
        "transaction_plan_fingerprint_valid": False,
        "target_identity_valid": False,
        "target_identity_fingerprint_valid": False,
        "idempotency_preview_valid": False,
        "idempotency_preview_authoritative": False,
        "backend_plan_binding_valid": False,
        "candidate_stale": False,
        "backend_plan_modified": False,
        "target_state": "target_state_unknown",
        "target_conflict_detected": False,
        "pre_write_checks_evaluated": [],
        "pre_write_checks_passed": [],
        "pre_write_checks_failed": [],
        "would_call_registration_function": False,
        "planned_write_count": 1,
        "writes_performed": 0,
        "confirmation_required": REGISTER_CONFIRMATION,
        "confirmation_accepted": False,
        "confirmation_enforced": False,
        "execution_authorized": False,
        "registration_authorized": False,
        "registration_performed": False,
        "record_set_written": False,
        "transaction_created": False,
        "transaction_persisted": False,
        "receipt_created": False,
        "blockers": [],
        "warnings": [],
        "recommended_action": "",
        "limitations": limitations,
        "boundary_flags": boundary_flags,
    }
    if transaction_plan is None:
        return {**base_payload, "status": "missing", "blockers": ["transaction_plan_required"], "recommended_action": "Build the read-only transaction-plan preview before running the dry run."}
    if not isinstance(transaction_plan, Mapping):
        return {**base_payload, "status": "malformed", "blockers": ["transaction_plan_malformed"], "recommended_action": "Provide the current transaction-plan preview mapping before running the dry run."}

    candidate_before = _candidate_fingerprint(candidate_record_set)
    backend_before = _hash_payload(_canonicalize_for_identity(dict(backend_plan))) if isinstance(backend_plan, Mapping) else None
    transaction_plan_before = _hash_payload(_canonicalize_for_identity(dict(transaction_plan)))
    binding = validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(
        transaction_plan,
        backend_plan,
        deepcopy(candidate_record_set),
        root=root,
    )
    candidate_after = _candidate_fingerprint(candidate_record_set)
    backend_after = _hash_payload(_canonicalize_for_identity(dict(backend_plan))) if isinstance(backend_plan, Mapping) else None
    transaction_plan_after = _hash_payload(_canonicalize_for_identity(dict(transaction_plan)))

    pre_write_checks = list(transaction_plan.get("planned_pre_write_verifications", [])) if isinstance(transaction_plan.get("planned_pre_write_verifications"), list) else []
    target_state = str(binding.get("current_target_state") or "target_state_unknown")
    target_conflict_detected = bool(binding.get("target_conflict_detected"))

    blockers: list[str] = []
    warnings: list[str] = list(binding.get("warnings", [])) if isinstance(binding.get("warnings"), list) else []
    if candidate_before != candidate_after:
        blockers.append("candidate_input_mutated_during_transaction_dry_run")
    if backend_before != backend_after:
        blockers.append("backend_plan_input_mutated_during_transaction_dry_run")
    if transaction_plan_before != transaction_plan_after:
        blockers.append("transaction_plan_input_mutated_during_transaction_dry_run")

    binding_status = str(binding.get("status") or "blocked")
    transaction_plan_fingerprint_valid = bool(binding.get("transaction_plan_fingerprint_valid"))
    target_identity_valid = bool(binding.get("target_identity_binding_valid"))
    target_identity_fingerprint_valid = bool(binding.get("target_identity_fingerprint_valid"))
    idempotency_preview_valid = bool(binding.get("idempotency_preview_valid"))
    backend_plan_binding_valid = bool(binding.get("backend_plan_binding_valid"))
    candidate_stale = bool(binding.get("candidate_stale"))
    backend_plan_modified = bool(binding.get("backend_plan_modified"))

    if binding_status == "valid":
        status = "dry_run_passed"
    elif binding_status == "stale_target":
        status = "stale_target"
        blockers.extend(list(binding.get("blockers", [])) if isinstance(binding.get("blockers"), list) else [])
    elif binding_status == "target_conflict":
        status = "blocked"
        blockers.extend(list(binding.get("blockers", [])) if isinstance(binding.get("blockers"), list) else [])
    elif binding_status == "target_state_unknown":
        status = "blocked"
        blockers.extend(list(binding.get("blockers", [])) if isinstance(binding.get("blockers"), list) else [])
    elif binding_status in {"missing", "malformed", "stale_candidate", "modified_backend_plan", "modified_transaction_plan"}:
        status = binding_status
        blockers.extend(list(binding.get("blockers", [])) if isinstance(binding.get("blockers"), list) else [])
    else:
        status = "blocked"
        blockers.extend(list(binding.get("blockers", [])) if isinstance(binding.get("blockers"), list) else [])

    passed_checks = []
    failed_checks = []
    for item in pre_write_checks:
        text = str(item)
        if status == "dry_run_passed":
            passed_checks.append(text)
            continue
        if "target state" in text and target_state == "target_state_unknown":
            failed_checks.append(text)
        elif "target conflict" in text and target_conflict_detected:
            failed_checks.append(text)
        elif "candidate is not stale" in text and candidate_stale:
            failed_checks.append(text)
        elif "backend plan is not modified" in text and backend_plan_modified:
            failed_checks.append(text)
        elif "recompute transaction-plan fingerprint" in text and not transaction_plan_fingerprint_valid:
            failed_checks.append(text)
        elif "recompute idempotency preview" in text and not idempotency_preview_valid:
            failed_checks.append(text)
        elif "verify target identity is complete and unambiguous" in text and not target_identity_valid:
            failed_checks.append(text)
        else:
            passed_checks.append(text)

    recommended_action = (
        "The read-only dry run passed. A later integrity phase can validate current target binding and stale-target behavior without enabling registration."
        if status == "dry_run_passed"
        else "Resolve transaction-plan integrity, target-state, or stale-input blockers before treating the plan as dry-run eligible."
    )
    return {
        **base_payload,
        "status": status,
        "dry_run_passed": status == "dry_run_passed",
        "transaction_plan_status": str(transaction_plan.get("status") or "unknown"),
        "transaction_plan_integrity_valid": bool(binding.get("transaction_plan_integrity_valid")),
        "transaction_plan_fingerprint_valid": transaction_plan_fingerprint_valid,
        "target_identity_valid": target_identity_valid,
        "target_identity_fingerprint_valid": target_identity_fingerprint_valid,
        "idempotency_preview_valid": idempotency_preview_valid,
        "backend_plan_binding_valid": backend_plan_binding_valid,
        "candidate_stale": candidate_stale,
        "backend_plan_modified": backend_plan_modified,
        "target_state": target_state,
        "target_conflict_detected": target_conflict_detected,
        "pre_write_checks_evaluated": pre_write_checks,
        "pre_write_checks_passed": passed_checks,
        "pre_write_checks_failed": failed_checks,
        "planned_write_count": int(transaction_plan.get("planned_write_count") or 1),
        "blockers": _dedupe(blockers),
        "warnings": _dedupe(warnings),
        "recommended_action": recommended_action,
    }


def format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run_report(
    transaction_plan: Mapping[str, Any],
    backend_plan: Mapping[str, Any],
    candidate_record_set: Any,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    dry_run = run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run(
        transaction_plan,
        backend_plan,
        candidate_record_set,
        root=root,
    )
    lines = [
        "Controlled outcome-truth registration transaction dry run",
        f"Status: {dry_run.get('status')}",
        f"Dry run: {str(bool(dry_run.get('dry_run'))).lower()}",
        f"Dry-run passed: {str(bool(dry_run.get('dry_run_passed'))).lower()}",
        f"Transaction-plan status: {dry_run.get('transaction_plan_status')}",
        f"Transaction-plan fingerprint valid: {str(bool(dry_run.get('transaction_plan_fingerprint_valid'))).lower()}",
        f"Target-identity fingerprint valid: {str(bool(dry_run.get('target_identity_fingerprint_valid'))).lower()}",
        f"Idempotency preview valid: {str(bool(dry_run.get('idempotency_preview_valid'))).lower()}",
        f"Backend-plan binding valid: {str(bool(dry_run.get('backend_plan_binding_valid'))).lower()}",
        f"Candidate stale: {str(bool(dry_run.get('candidate_stale'))).lower()}",
        f"Backend-plan modified: {str(bool(dry_run.get('backend_plan_modified'))).lower()}",
        f"Target state: {dry_run.get('target_state')}",
        f"Target conflict detected: {str(bool(dry_run.get('target_conflict_detected'))).lower()}",
        "A passing dry run does not authorize execution.",
        "A passing dry run does not authorize registration.",
        "A passing dry run does not accept or enforce confirmation.",
        "A passing dry run does not prove the future registration will succeed.",
        "Unknown target state must be reported conservatively.",
        "Evaluated pre-write checks: " + ", ".join(str(item) for item in dry_run.get("pre_write_checks_evaluated", [])),
    ]
    blockers = dry_run.get("blockers", [])
    warnings = dry_run.get("warnings", [])
    if isinstance(blockers, list) and blockers:
        lines.append("Blockers: " + ", ".join(str(item) for item in blockers))
    if isinstance(warnings, list) and warnings:
        lines.append("Warnings: " + ", ".join(str(item) for item in warnings))
    if dry_run.get("recommended_action"):
        lines.append(f"Recommended action: {dry_run.get('recommended_action')}")
    limitations = dry_run.get("limitations", [])
    if isinstance(limitations, list) and limitations:
        lines.append("Limitations: " + "; ".join(str(item) for item in limitations))
    lines.append(f"Planned write count: {dry_run.get('planned_write_count')}")
    lines.append(f"Writes performed: {dry_run.get('writes_performed', 0)}")
    return "\n".join(lines)


def validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(
    transaction_plan: Mapping[str, Any],
    backend_plan: Mapping[str, Any],
    candidate_record_set: Any,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    limitations = _outcome_truth_record_set_controlled_registration_transaction_plan_binding_limitations()
    boundary_flags = _outcome_truth_record_set_controlled_registration_transaction_plan_binding_boundary_flags()
    base_payload = {
        "transaction_plan_binding_schema_version": 1,
        "transaction_plan_binding_type": "controlled_outcome_truth_record_set_registration_transaction_plan_binding",
        "status": "missing",
        "transaction_plan_binding_valid": False,
        "transaction_plan_integrity_valid": False,
        "transaction_plan_fingerprint_valid": False,
        "backend_plan_binding_valid": False,
        "candidate_binding_valid": False,
        "planning_gate_binding_valid": False,
        "backend_plan_integrity_valid": False,
        "target_identity_binding_valid": False,
        "target_identity_fingerprint_valid": False,
        "idempotency_preview_valid": False,
        "target_state_observation_available": False,
        "target_state_binding_valid": False,
        "target_state_freshness_status": "unknown",
        "target_state_freshness_proven": False,
        "stale_target_detected": False,
        "target_state_changed_detected": False,
        "target_conflict_detected": False,
        "candidate_stale": False,
        "backend_plan_modified": False,
        "transaction_plan_modified": False,
        "planned_target_state": "target_state_unknown",
        "current_target_state": "target_state_unknown",
        "planned_target_state_observation_basis": _text((transaction_plan or {}).get("target_state_observation_basis")) if isinstance(transaction_plan, Mapping) else None,
        "current_target_state_observation_basis": None,
        "stored_candidate_fingerprint": _text((transaction_plan or {}).get("candidate_fingerprint")) if isinstance(transaction_plan, Mapping) else None,
        "expected_candidate_fingerprint": _candidate_fingerprint(candidate_record_set),
        "stored_backend_plan_fingerprint": _text((transaction_plan or {}).get("backend_plan_fingerprint")) if isinstance(transaction_plan, Mapping) else None,
        "expected_backend_plan_fingerprint": _text((backend_plan or {}).get("backend_plan_fingerprint")) if isinstance(backend_plan, Mapping) else None,
        "stored_target_identity_fingerprint": _text((transaction_plan or {}).get("target_identity_fingerprint")) if isinstance(transaction_plan, Mapping) else None,
        "expected_target_identity_fingerprint": None,
        "stored_target_state_snapshot_fingerprint": _text((transaction_plan or {}).get("target_state_snapshot_fingerprint")) if isinstance(transaction_plan, Mapping) else None,
        "current_target_state_snapshot_fingerprint": None,
        "stored_transaction_plan_fingerprint": _text((transaction_plan or {}).get("transaction_plan_fingerprint")) if isinstance(transaction_plan, Mapping) else None,
        "expected_transaction_plan_fingerprint": None,
        "stored_idempotency_key_preview": _text((transaction_plan or {}).get("idempotency_key_preview")) if isinstance(transaction_plan, Mapping) else None,
        "expected_idempotency_key_preview": None,
        "execution_authorized": False,
        "registration_authorized": False,
        "confirmation_accepted": False,
        "confirmation_enforced": False,
        "idempotency_enforced": False,
        "registration_performed": False,
        "record_set_written": False,
        "blockers": [],
        "warnings": [],
        "recommended_action": "",
        "limitations": limitations,
        "boundary_flags": boundary_flags,
        "writes_performed": 0,
    }
    if transaction_plan is None:
        return {**base_payload, "status": "missing", "blockers": ["transaction_plan_required"], "recommended_action": "Provide the current transaction plan before validating transaction-plan binding."}
    if not isinstance(transaction_plan, Mapping):
        return {**base_payload, "status": "malformed", "blockers": ["transaction_plan_malformed"], "recommended_action": "Provide a valid transaction-plan mapping before validating transaction-plan binding."}
    required_transaction_plan_fields = (
        "transaction_plan_schema_version",
        "transaction_plan_type",
        "candidate_fingerprint",
        "planning_gate_fingerprint",
        "backend_plan_fingerprint",
        "target_identity",
        "target_identity_fingerprint",
        "target_state_snapshot_fingerprint",
        "transaction_plan_fingerprint",
        "idempotency_key_preview",
    )
    if any(field not in transaction_plan for field in required_transaction_plan_fields):
        return {
            **base_payload,
            "status": "malformed",
            "blockers": ["transaction_plan_malformed"],
            "recommended_action": "Provide a structurally complete transaction-plan mapping before validating transaction-plan binding.",
        }
    if backend_plan is None:
        return {**base_payload, "status": "missing", "blockers": ["backend_plan_required"], "recommended_action": "Provide the current frozen backend plan before validating transaction-plan binding."}
    if not isinstance(backend_plan, Mapping):
        return {**base_payload, "status": "malformed", "blockers": ["backend_plan_malformed"], "recommended_action": "Provide a valid frozen backend plan before validating transaction-plan binding."}
    required_backend_plan_fields = (
        "backend_plan_schema_version",
        "backend_plan_type",
        "status",
        "planning_gate_fingerprint",
        "backend_plan_fingerprint",
    )
    if any(field not in backend_plan for field in required_backend_plan_fields):
        return {
            **base_payload,
            "status": "malformed",
            "blockers": ["backend_plan_malformed"],
            "recommended_action": "Provide a structurally complete frozen backend plan before validating transaction-plan binding.",
        }
    if candidate_record_set is None:
        return {**base_payload, "status": "missing", "blockers": ["candidate_record_set_required"], "recommended_action": "Provide the current candidate record set before validating transaction-plan binding."}
    if not isinstance(candidate_record_set, Mapping) or not isinstance(candidate_record_set.get("records"), (list, tuple)):
        return {**base_payload, "status": "malformed", "blockers": ["candidate_record_set_malformed"], "recommended_action": "Provide a valid candidate record-set mapping before validating transaction-plan binding."}

    candidate_before = _candidate_fingerprint(candidate_record_set)
    backend_before = _hash_payload(_canonicalize_for_identity(dict(backend_plan)))
    transaction_plan_before = _hash_payload(_canonicalize_for_identity(dict(transaction_plan)))
    phase13_binding = validate_deployed_rule_outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding(
        backend_plan,
        deepcopy(candidate_record_set),
        root=root,
    )
    expected_plan = build_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan(
        deepcopy(backend_plan),
        deepcopy(candidate_record_set),
        root=root,
    )
    current_target_state_snapshot = _build_controlled_registration_target_state_snapshot(
        {
            "target_identity": deepcopy(expected_plan.get("target_identity", {})),
            "target_identity_fingerprint": expected_plan.get("target_identity_fingerprint"),
        },
        root=root,
    )
    candidate_after = _candidate_fingerprint(candidate_record_set)
    backend_after = _hash_payload(_canonicalize_for_identity(dict(backend_plan)))
    transaction_plan_after = _hash_payload(_canonicalize_for_identity(dict(transaction_plan)))

    blockers: list[str] = []
    warnings: list[str] = list(current_target_state_snapshot.get("warnings", [])) if isinstance(current_target_state_snapshot.get("warnings"), list) else []
    if candidate_before != candidate_after:
        blockers.append("candidate_input_mutated_during_transaction_plan_binding")
    if backend_before != backend_after:
        blockers.append("backend_plan_input_mutated_during_transaction_plan_binding")
    if transaction_plan_before != transaction_plan_after:
        blockers.append("transaction_plan_input_mutated_during_transaction_plan_binding")

    stored_plan_fingerprint = _text(transaction_plan.get("transaction_plan_fingerprint"))
    expected_plan_for_integrity = deepcopy(expected_plan)
    expected_plan_for_integrity["target_state_at_plan_time"] = transaction_plan.get("target_state_at_plan_time")
    expected_plan_for_integrity["target_state_observation_status"] = transaction_plan.get("target_state_observation_status")
    expected_plan_for_integrity["target_state_observation_available"] = transaction_plan.get("target_state_observation_available")
    expected_plan_for_integrity["target_state_observation_basis"] = transaction_plan.get("target_state_observation_basis")
    expected_plan_for_integrity["target_state_snapshot"] = deepcopy(transaction_plan.get("target_state_snapshot", {}))
    expected_plan_for_integrity["target_state_snapshot_fingerprint"] = transaction_plan.get(
        "target_state_snapshot_fingerprint"
    )
    expected_plan_fingerprint = _compute_controlled_registration_transaction_plan_fingerprint(
        expected_plan_for_integrity
    )
    transaction_plan_fingerprint_valid = bool(
        stored_plan_fingerprint
        and expected_plan_fingerprint
        and stored_plan_fingerprint == expected_plan_fingerprint
        and _is_sha256_fingerprint(stored_plan_fingerprint)
    )
    stored_candidate_fingerprint = _text(transaction_plan.get("candidate_fingerprint"))
    expected_candidate_fingerprint = _candidate_fingerprint(candidate_record_set)
    candidate_binding_valid = bool(
        stored_candidate_fingerprint
        and expected_candidate_fingerprint
        and stored_candidate_fingerprint == expected_candidate_fingerprint
        and _is_sha256_fingerprint(stored_candidate_fingerprint)
    )
    stored_backend_plan_fingerprint = _text(transaction_plan.get("backend_plan_fingerprint"))
    expected_backend_plan_fingerprint = _text(backend_plan.get("backend_plan_fingerprint"))
    backend_plan_fingerprint_valid = bool(
        stored_backend_plan_fingerprint
        and expected_backend_plan_fingerprint
        and stored_backend_plan_fingerprint == expected_backend_plan_fingerprint
        and _is_sha256_fingerprint(stored_backend_plan_fingerprint)
    )
    stored_target_identity_fingerprint = _text(transaction_plan.get("target_identity_fingerprint"))
    expected_target_identity_fingerprint = _text(expected_plan.get("target_identity_fingerprint"))
    target_identity_fingerprint_valid = bool(
        stored_target_identity_fingerprint
        and expected_target_identity_fingerprint
        and stored_target_identity_fingerprint == expected_target_identity_fingerprint
        and _is_sha256_fingerprint(stored_target_identity_fingerprint)
    )
    target_identity_binding_valid = (
        isinstance(transaction_plan.get("target_identity"), Mapping)
        and isinstance(expected_plan.get("target_identity"), Mapping)
        and _canonicalize_for_identity(transaction_plan.get("target_identity")) == _canonicalize_for_identity(expected_plan.get("target_identity"))
        and target_identity_fingerprint_valid
    )
    stored_idempotency = _text(transaction_plan.get("idempotency_key_preview"))
    expected_idempotency = _text(expected_plan.get("idempotency_key_preview"))
    idempotency_preview_valid = bool(
        stored_idempotency
        and expected_idempotency
        and stored_idempotency == expected_idempotency
        and _is_sha256_fingerprint(stored_idempotency)
        and transaction_plan.get("idempotency_key_preview_authoritative") is False
        and transaction_plan.get("idempotency_key_preview_persisted") is False
        and transaction_plan.get("idempotency_enforced") is False
    )
    planned_target_state = str(transaction_plan.get("target_state_at_plan_time") or "target_state_unknown")
    current_target_state = str(current_target_state_snapshot.get("target_state") or "target_state_unknown")
    current_target_state_observation_basis = _text(current_target_state_snapshot.get("observation_basis"))
    stored_target_state_snapshot_fingerprint = _text(transaction_plan.get("target_state_snapshot_fingerprint"))
    current_target_state_snapshot_fingerprint = _text(current_target_state_snapshot.get("target_state_snapshot_fingerprint"))
    target_state_observation_available = bool(current_target_state_snapshot.get("read_path_available"))
    target_state_semantically_observed = (
        str(current_target_state_snapshot.get("observation_status") or "") == "observed"
        and current_target_state in {"target_absent", "target_present_equivalent", "target_present_conflicting"}
    )
    target_state_binding_valid = bool(
        target_state_observation_available
        and target_state_semantically_observed
        and stored_target_state_snapshot_fingerprint
        and current_target_state_snapshot_fingerprint
        and stored_target_state_snapshot_fingerprint == current_target_state_snapshot_fingerprint
        and _is_sha256_fingerprint(stored_target_state_snapshot_fingerprint)
    )
    stale_target_detected = bool(
        target_state_observation_available
        and target_state_semantically_observed
        and stored_target_state_snapshot_fingerprint
        and current_target_state_snapshot_fingerprint
        and stored_target_state_snapshot_fingerprint != current_target_state_snapshot_fingerprint
    )
    target_state_changed_detected = stale_target_detected
    target_conflict_detected = current_target_state == "target_present_conflicting"

    backend_plan_binding_valid = bool(phase13_binding.get("binding_valid"))
    planning_gate_binding_valid = bool(phase13_binding.get("planning_gate_binding_valid"))
    backend_plan_integrity_valid = bool(phase13_binding.get("backend_plan_integrity_valid"))
    candidate_stale = bool(phase13_binding.get("stale_candidate_detected"))
    backend_plan_modified = bool(phase13_binding.get("backend_plan_modified_detected"))
    transaction_plan_modified = not transaction_plan_fingerprint_valid

    if candidate_stale:
        status = "stale_candidate"
        blockers.extend(list(phase13_binding.get("blockers", [])) if isinstance(phase13_binding.get("blockers"), list) else [])
    elif backend_plan_modified or not backend_plan_fingerprint_valid:
        status = "modified_backend_plan"
        blockers.extend(list(phase13_binding.get("blockers", [])) if isinstance(phase13_binding.get("blockers"), list) else [])
        if not backend_plan_fingerprint_valid:
            blockers.append("backend_plan_fingerprint_mismatch")
    elif not planning_gate_binding_valid:
        status = "modified_backend_plan"
        blockers.extend(list(phase13_binding.get("blockers", [])) if isinstance(phase13_binding.get("blockers"), list) else [])
    elif transaction_plan_modified:
        status = "modified_transaction_plan"
        blockers.append("transaction_plan_fingerprint_mismatch")
    elif not candidate_binding_valid:
        status = "modified_transaction_plan"
        blockers.append("transaction_plan_candidate_fingerprint_mismatch")
    elif not target_identity_binding_valid:
        status = "modified_transaction_plan"
        blockers.append("transaction_target_identity_fingerprint_mismatch")
    elif not idempotency_preview_valid:
        status = "modified_transaction_plan"
        blockers.append("transaction_idempotency_preview_mismatch")
    elif target_conflict_detected:
        status = "target_conflict"
        blockers.append("transaction_target_identity_conflict")
    elif not target_state_semantically_observed:
        status = "target_state_unknown"
        blockers.append("target_state_unknown")
    elif not target_state_observation_available:
        status = "target_state_unknown"
        blockers.append("target_state_unknown")
    elif stale_target_detected:
        status = "stale_target"
        blockers.append("stale_target_detected")
    elif not backend_plan_binding_valid or not backend_plan_integrity_valid:
        status = "blocked"
        blockers.extend(list(phase13_binding.get("blockers", [])) if isinstance(phase13_binding.get("blockers"), list) else [])
    else:
        status = "valid"

    if status == "valid":
        recommended_action = "Transaction-plan identity, target binding, and current target-state snapshot are structurally consistent. A later API/UI seam may expose this read-only gate without enabling writes."
    elif status == "stale_target":
        recommended_action = "Rebuild the transaction plan against the current target state. Stale or modified transaction plans must be rebuilt rather than repaired in place."
    elif status == "target_state_unknown":
        recommended_action = "Target-state freshness is unknown. Unknown target state must not be described as current."
    else:
        recommended_action = "Resolve transaction-plan integrity, target-binding, or stale-target blockers before exposing this plan through a later seam."

    return {
        **base_payload,
        "status": status,
        "transaction_plan_binding_valid": status == "valid",
        "transaction_plan_integrity_valid": transaction_plan_fingerprint_valid and target_identity_fingerprint_valid and idempotency_preview_valid,
        "transaction_plan_fingerprint_valid": transaction_plan_fingerprint_valid,
        "backend_plan_binding_valid": backend_plan_binding_valid,
        "candidate_binding_valid": candidate_binding_valid,
        "planning_gate_binding_valid": planning_gate_binding_valid,
        "backend_plan_integrity_valid": backend_plan_integrity_valid,
        "target_identity_binding_valid": target_identity_binding_valid,
        "target_identity_fingerprint_valid": target_identity_fingerprint_valid,
        "idempotency_preview_valid": idempotency_preview_valid,
        "target_state_observation_available": target_state_observation_available,
        "target_state_binding_valid": target_state_binding_valid,
        "target_state_freshness_status": "fresh" if target_state_binding_valid else "stale" if stale_target_detected else "unknown",
        "target_state_freshness_proven": target_state_binding_valid,
        "stale_target_detected": stale_target_detected,
        "target_state_changed_detected": target_state_changed_detected,
        "target_conflict_detected": target_conflict_detected,
        "candidate_stale": candidate_stale,
        "backend_plan_modified": backend_plan_modified,
        "transaction_plan_modified": transaction_plan_modified,
        "planned_target_state": planned_target_state,
        "current_target_state": current_target_state,
        "planned_target_state_observation_basis": _text(transaction_plan.get("target_state_observation_basis")),
        "current_target_state_observation_basis": current_target_state_observation_basis,
        "stored_candidate_fingerprint": stored_candidate_fingerprint,
        "expected_candidate_fingerprint": expected_candidate_fingerprint,
        "stored_backend_plan_fingerprint": stored_backend_plan_fingerprint,
        "expected_backend_plan_fingerprint": expected_backend_plan_fingerprint,
        "stored_target_identity_fingerprint": stored_target_identity_fingerprint,
        "expected_target_identity_fingerprint": expected_target_identity_fingerprint,
        "stored_target_state_snapshot_fingerprint": stored_target_state_snapshot_fingerprint,
        "current_target_state_snapshot_fingerprint": current_target_state_snapshot_fingerprint,
        "stored_transaction_plan_fingerprint": stored_plan_fingerprint,
        "expected_transaction_plan_fingerprint": expected_plan_fingerprint,
        "stored_idempotency_key_preview": stored_idempotency,
        "expected_idempotency_key_preview": expected_idempotency,
        "blockers": _dedupe(blockers),
        "warnings": _dedupe(warnings),
        "recommended_action": recommended_action,
    }


def format_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding_report(
    transaction_plan: Mapping[str, Any],
    backend_plan: Mapping[str, Any],
    candidate_record_set: Any,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    binding = validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(
        transaction_plan,
        backend_plan,
        candidate_record_set,
        root=root,
    )
    lines = [
        "Controlled registration transaction-plan binding report",
        f"Status: {binding.get('status')}",
        f"Transaction-plan binding valid: {str(bool(binding.get('transaction_plan_binding_valid'))).lower()}",
        f"Transaction-plan fingerprint valid: {str(bool(binding.get('transaction_plan_fingerprint_valid'))).lower()}",
        f"Candidate binding valid: {str(bool(binding.get('candidate_binding_valid'))).lower()}",
        f"Backend-plan binding valid: {str(bool(binding.get('backend_plan_binding_valid'))).lower()}",
        f"Target-identity fingerprint valid: {str(bool(binding.get('target_identity_fingerprint_valid'))).lower()}",
        f"Idempotency preview valid: {str(bool(binding.get('idempotency_preview_valid'))).lower()}",
        f"Target-state observation available: {str(bool(binding.get('target_state_observation_available'))).lower()}",
        f"Planned target state: {binding.get('planned_target_state')}",
        f"Planned target-state observation basis: {binding.get('planned_target_state_observation_basis')}",
        f"Current target state: {binding.get('current_target_state')}",
        f"Current target-state observation basis: {binding.get('current_target_state_observation_basis')}",
        f"Stored candidate fingerprint: {binding.get('stored_candidate_fingerprint')}",
        f"Expected candidate fingerprint: {binding.get('expected_candidate_fingerprint')}",
        f"Stored backend-plan fingerprint: {binding.get('stored_backend_plan_fingerprint')}",
        f"Expected backend-plan fingerprint: {binding.get('expected_backend_plan_fingerprint')}",
        f"Stored target-identity fingerprint: {binding.get('stored_target_identity_fingerprint')}",
        f"Expected target-identity fingerprint: {binding.get('expected_target_identity_fingerprint')}",
        f"Stored target-state snapshot fingerprint: {binding.get('stored_target_state_snapshot_fingerprint')}",
        f"Stored transaction-plan fingerprint: {binding.get('stored_transaction_plan_fingerprint')}",
        f"Expected transaction-plan fingerprint: {binding.get('expected_transaction_plan_fingerprint')}",
        f"Stored idempotency preview: {binding.get('stored_idempotency_key_preview')}",
        f"Expected idempotency preview: {binding.get('expected_idempotency_key_preview')}",
        f"Current target-state snapshot fingerprint: {binding.get('current_target_state_snapshot_fingerprint')}",
        "Phase 14C adds deterministic identity, target binding, and stale-target detection to the Phase 14B transaction plan.",
        "Target-state freshness is proven only when a safe non-creating read path is available and the current target-state snapshot matches the snapshot bound into the transaction plan.",
        "Unknown target state must not be described as current.",
        "Lack of detected staleness is not proof of freshness when target observation is unavailable.",
        "A valid transaction-plan binding does not authorize execution.",
        "A valid transaction-plan binding does not authorize registration.",
        "Phase 14C does not call the registration function.",
        "Phase 14C does not accept or enforce confirmation.",
        "Phase 14C does not enforce idempotency.",
        "Phase 14C does not persist target-state snapshots, transaction plans, dry-run results, or receipts.",
        "Stale or modified transaction plans must be rebuilt rather than repaired in place.",
        "A valid fingerprint proves integrity against the defined canonical representation only.",
        "It does not prove factual correctness of outcome-truth records.",
    ]
    blockers = binding.get("blockers", [])
    warnings = binding.get("warnings", [])
    if isinstance(blockers, list) and blockers:
        lines.append("Blockers: " + ", ".join(str(item) for item in blockers))
    if isinstance(warnings, list) and warnings:
        lines.append("Warnings: " + ", ".join(str(item) for item in warnings))
    if binding.get("recommended_action"):
        lines.append(f"Recommended action: {binding.get('recommended_action')}")
    limitations = binding.get("limitations", [])
    if isinstance(limitations, list) and limitations:
        lines.append("Limitations: " + "; ".join(str(item) for item in limitations))
    lines.append(f"Writes performed: {binding.get('writes_performed', 0)}")
    return "\n".join(lines)


def build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate(
    transaction_plan: Mapping[str, Any],
    backend_plan: Mapping[str, Any],
    candidate_record_set: Any,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    limitations = _outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate_limitations()
    boundary_flags = _outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate_boundary_flags()
    base_payload = {
        "authorization_confirmation_contract_gate_schema_version": 1,
        "authorization_confirmation_contract_gate_type": "controlled_outcome_truth_record_set_registration_execution_authorization_confirmation_contract_gate",
        "status": "missing",
        "transaction_plan_status": "missing",
        "transaction_plan_binding_status": "missing",
        "transaction_plan_binding_valid": False,
        "transaction_plan_integrity_valid": False,
        "candidate_binding_valid": False,
        "backend_plan_binding_valid": False,
        "planning_gate_binding_valid": False,
        "target_identity_binding_valid": False,
        "target_state_binding_valid": False,
        "target_state_observation_available": False,
        "target_state_freshness_status": "unknown",
        "target_state_freshness_proven": False,
        "stale_target_detected": False,
        "target_state_changed_detected": False,
        "target_conflict_detected": False,
        "idempotency_preview_valid": False,
        "idempotency_preview_authoritative": False,
        "idempotency_enforced": False,
        "dry_run_status": "missing",
        "dry_run_passed": False,
        "would_call_registration_function": False,
        "planned_write_function": None,
        "planned_write_count": None,
        "ready_to_design_future_authorization_artifact": False,
        "authorization_artifact_required": True,
        "authorization_artifact_implemented": False,
        "authorization_artifact_created": False,
        "authorization_artifact_persisted": False,
        "authorization_id_created": False,
        "authorization_registry_created": False,
        "authorization_granted": False,
        "authorization_consumed": False,
        "required_future_confirmation": REGISTER_CONFIRMATION,
        "confirmation_match_policy": {
            "match_type": "exact_literal",
            "case_sensitive": True,
            "trim_before_compare": False,
            "unicode_normalization": "none",
            "substring_match_allowed": False,
            "implicit_confirmation_allowed": False,
        },
        "confirmation_supplied_in_this_phase": False,
        "confirmation_matched_in_this_phase": False,
        "confirmation_accepted_in_this_phase": False,
        "confirmation_enforced_in_this_phase": False,
        "future_authorization_artifact_required_fields": [
            "authorization_artifact_schema_version",
            "authorization_artifact_type",
            "authorization_artifact_id",
            "authorization_scope",
            "candidate_fingerprint",
            "planning_gate_fingerprint",
            "backend_plan_fingerprint",
            "target_identity_fingerprint",
            "target_state_snapshot_fingerprint",
            "transaction_plan_fingerprint",
            "idempotency_identity",
            "dry_run_evidence_identity",
            "required_confirmation_contract_version",
            "exact_confirmation_matched",
            "planned_write_function",
            "maximum_registration_attempts",
            "single_use",
            "authorization_state",
            "authorization_consumed",
            "issuance_preconditions_verified",
            "pre_write_revalidation_required",
            "invalidation_conditions",
            "boundary_flags",
        ],
        "future_authorization_binding_requirements": [
            "exact current candidate fingerprint",
            "exact current planning-gate fingerprint",
            "exact current backend-plan fingerprint",
            "exact current target-identity fingerprint",
            "exact current target-state snapshot fingerprint",
            "exact current transaction-plan fingerprint",
            "exact future idempotency identity",
            "exact canonical registration function",
            "exact authorization scope",
            "exact planned write count",
            "exact confirmation contract version",
            "exact passing dry-run evidence identity",
        ],
        "future_authorization_scope_requirements": [
            "one candidate identity",
            "one backend-plan identity",
            "one transaction-plan identity",
            "one target identity",
            "one target-state snapshot",
            "one idempotency identity",
            "one canonical registration function",
            "maximum_registration_attempts = 1",
            "no alternate write path",
            "no repair authority",
            "no migration authority",
            "no scoring authority",
            "no rollback authority unless separately designed and verified",
        ],
        "future_authorization_single_use_requirements": [
            "single-use",
            "transaction-bound",
            "target-bound",
            "plan-bound",
            "non-transferable",
            "invalid after successful consumption",
            "invalid after any ambiguous execution attempt until operator review",
            "invalid after candidate change",
            "invalid after backend-plan change",
            "invalid after transaction-plan change",
            "invalid after target-state change",
            "invalid after target conflict appears",
            "invalid after idempotency identity changes",
            "invalid after dry-run evidence becomes stale",
            "unusable for retries unless a separate recovery decision is explicitly created",
        ],
        "future_authorization_invalidation_conditions": [
            "candidate fingerprint mismatch",
            "backend-plan fingerprint mismatch",
            "planning-gate fingerprint mismatch",
            "target-identity mismatch",
            "target-state snapshot mismatch",
            "stale target detected",
            "target conflict detected",
            "transaction-plan fingerprint mismatch",
            "idempotency identity mismatch",
            "dry-run evidence mismatch",
            "dry-run no longer passing",
            "confirmation missing",
            "confirmation invalid",
            "canonical write function mismatch",
            "planned write count not equal to 1",
            "prior authorization consumption",
            "prior ambiguous execution attempt",
            "authorization artifact malformed",
            "authorization artifact binding invalid",
        ],
        "future_pre_authorization_revalidation": [
            "parse current candidate",
            "validate Phase 13 backend-plan binding",
            "validate Phase 14 transaction-plan binding",
            "rebuild current target-state snapshot",
            "prove target-state freshness",
            "confirm no stale target",
            "confirm no target conflict",
            "confirm transaction-plan integrity",
            "confirm target-identity binding",
            "confirm idempotency-preview consistency",
            "rerun transaction dry run",
            "confirm dry_run_passed = true",
            "confirm planned write function is canonical",
            "confirm planned_write_count = 1",
            "confirm writes_performed = 0",
            "confirm exact confirmation match",
            "confirm future idempotency enforcement surface exists",
            "confirm no prior conflicting or consumed authorization",
        ],
        "future_pre_write_revalidation": [
            "authorization artifact integrity",
            "authorization artifact unconsumed state",
            "candidate fingerprint",
            "backend-plan fingerprint",
            "transaction-plan fingerprint",
            "target-identity fingerprint",
            "current target-state snapshot fingerprint",
            "target freshness",
            "target conflict status",
            "dry-run evidence identity",
            "idempotency identity and enforcement status",
            "canonical write function",
            "maximum attempt count",
            "exact authorization scope",
            "confirmation contract evidence",
            "writes performed still zero for the attempt",
        ],
        "future_authorization_failure_states": [
            "blocked_precondition",
            "transaction_plan_missing",
            "transaction_plan_malformed",
            "invalid_transaction_plan_binding",
            "modified_transaction_plan",
            "stale_candidate",
            "modified_backend_plan",
            "target_state_unknown",
            "stale_target",
            "target_conflict",
            "dry_run_failed",
            "idempotency_enforcement_unavailable",
            "confirmation_missing",
            "confirmation_invalid",
            "authorization_artifact_missing",
            "authorization_artifact_malformed",
            "authorization_artifact_binding_mismatch",
            "authorization_artifact_consumed",
            "authorization_artifact_stale",
            "authorization_scope_mismatch",
            "pre_authorization_revalidation_failed",
            "pre_write_revalidation_failed",
            "contract_ready_to_design_authorization_artifact",
        ],
        "future_authorization_receipt_requirements": [
            "authorization receipt schema version",
            "authorization artifact identity",
            "authorization scope",
            "candidate fingerprint",
            "planning-gate fingerprint",
            "backend-plan fingerprint",
            "target-identity fingerprint",
            "target-state snapshot fingerprint",
            "transaction-plan fingerprint",
            "idempotency identity",
            "dry-run evidence identity",
            "confirmation contract version",
            "exact confirmation matched yes/no",
            "authorization artifact created yes/no",
            "authorization granted yes/no",
            "authorization consumed yes/no",
            "pre-authorization revalidation result",
            "pre-write revalidation result",
            "final authorization state",
            "blockers",
            "warnings",
            "limitations",
            "boundary_flags",
            "writes performed",
        ],
        "planned_future_authorization_sequence": [
            "1. Accept the current candidate, backend plan, and transaction plan.",
            "2. Revalidate Phase 13 backend-plan binding.",
            "3. Revalidate Phase 14 transaction-plan binding.",
            "4. Rebuild and compare the current target-state snapshot.",
            "5. Confirm target-state freshness and absence of conflict.",
            "6. Rerun the transaction dry run.",
            "7. Confirm the canonical write function and one-write scope.",
            "8. Resolve and enforce authoritative idempotency identity.",
            "9. Require exact confirmation: REGISTER_OUTCOME_TRUTH_RECORD_SET.",
            "10. Build a deterministic plan-bound authorization artifact.",
            "11. Persist or otherwise authoritatively register the single-use artifact.",
            "12. Revalidate the artifact and all bound identities immediately before mutation.",
            "13. Consume authorization at the future write boundary.",
            "14. Permit at most one canonical registration attempt.",
            "15. Produce public-safe authorization and execution receipts.",
            "16. Block automatic retry after ambiguous execution.",
            "17. Never claim factual truth correctness.",
        ],
        "blockers": [],
        "warnings": [],
        "recommended_action": "",
        "limitations": limitations,
        "boundary_flags": boundary_flags,
        "execution_authorized": False,
        "registration_authorized": False,
        "registration_performed": False,
        "record_set_written": False,
        "writes_performed": 0,
    }
    if transaction_plan is None:
        return {
            **base_payload,
            "status": "missing",
            "blockers": ["transaction_plan_required"],
            "recommended_action": "Provide the current read-only transaction plan before evaluating the future authorization and confirmation contract gate.",
        }
    if not isinstance(transaction_plan, Mapping):
        return {
            **base_payload,
            "status": "malformed",
            "blockers": ["transaction_plan_malformed"],
            "recommended_action": "Provide a valid transaction-plan mapping before evaluating the future authorization and confirmation contract gate.",
        }
    if backend_plan is None:
        return {
            **base_payload,
            "status": "missing",
            "blockers": ["backend_plan_required"],
            "recommended_action": "Provide the current frozen backend plan before evaluating the future authorization and confirmation contract gate.",
        }
    if not isinstance(backend_plan, Mapping):
        return {
            **base_payload,
            "status": "malformed",
            "blockers": ["backend_plan_malformed"],
            "recommended_action": "Provide a valid frozen backend plan before evaluating the future authorization and confirmation contract gate.",
        }
    if candidate_record_set is None:
        return {
            **base_payload,
            "status": "missing",
            "blockers": ["candidate_record_set_required"],
            "recommended_action": "Provide the current candidate record set before evaluating the future authorization and confirmation contract gate.",
        }
    if not isinstance(candidate_record_set, Mapping) or not isinstance(candidate_record_set.get("records"), (list, tuple)):
        return {
            **base_payload,
            "status": "malformed",
            "blockers": ["candidate_record_set_malformed"],
            "recommended_action": "Provide a valid candidate record-set mapping before evaluating the future authorization and confirmation contract gate.",
        }

    candidate_before = _hash_payload(_canonicalize_for_identity(candidate_record_set))
    backend_before = _hash_payload(_canonicalize_for_identity(dict(backend_plan)))
    transaction_plan_before = _hash_payload(_canonicalize_for_identity(dict(transaction_plan)))
    binding = validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(
        deepcopy(transaction_plan),
        deepcopy(backend_plan),
        deepcopy(candidate_record_set),
        root=root,
    )
    dry_run = run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run(
        deepcopy(transaction_plan),
        deepcopy(backend_plan),
        deepcopy(candidate_record_set),
        root=root,
    )
    candidate_after = _hash_payload(_canonicalize_for_identity(candidate_record_set))
    backend_after = _hash_payload(_canonicalize_for_identity(dict(backend_plan)))
    transaction_plan_after = _hash_payload(_canonicalize_for_identity(dict(transaction_plan)))

    blockers = _dedupe(
        list(binding.get("blockers", [])) + list(dry_run.get("blockers", []))
    )
    warnings = _dedupe(
        ["dry_run_evidence_identity_not_yet_implemented"]
        + list(binding.get("warnings", []))
        + list(dry_run.get("warnings", []))
    )
    if candidate_before != candidate_after:
        blockers.append("candidate_input_mutated_during_authorization_contract_gate")
    if backend_before != backend_after:
        blockers.append("backend_plan_input_mutated_during_authorization_contract_gate")
    if transaction_plan_before != transaction_plan_after:
        blockers.append("transaction_plan_input_mutated_during_authorization_contract_gate")
    blockers = _dedupe(blockers)

    planned_write_function = _text(transaction_plan.get("planned_write_function"))
    planned_write_count = _integer_or_none(transaction_plan.get("planned_write_count"))
    writes_performed = _integer_or_none(dry_run.get("writes_performed"))
    transaction_plan_binding_valid = bool(binding.get("transaction_plan_binding_valid"))
    transaction_plan_integrity_valid = bool(binding.get("transaction_plan_integrity_valid"))
    candidate_binding_valid = bool(binding.get("candidate_binding_valid"))
    backend_plan_binding_valid = bool(binding.get("backend_plan_binding_valid"))
    planning_gate_binding_valid = bool(binding.get("planning_gate_binding_valid"))
    target_identity_binding_valid = bool(binding.get("target_identity_binding_valid"))
    target_state_binding_valid = bool(binding.get("target_state_binding_valid"))
    target_state_observation_available = bool(binding.get("target_state_observation_available"))
    target_state_freshness_status = str(binding.get("target_state_freshness_status") or "unknown")
    target_state_freshness_proven = bool(binding.get("target_state_freshness_proven"))
    stale_target_detected = bool(binding.get("stale_target_detected"))
    target_state_changed_detected = bool(binding.get("target_state_changed_detected"))
    target_conflict_detected = bool(binding.get("target_conflict_detected"))
    idempotency_preview_valid = bool(binding.get("idempotency_preview_valid"))
    dry_run_passed = bool(dry_run.get("dry_run_passed"))
    would_call_registration_function = bool(dry_run.get("would_call_registration_function"))

    ready_to_design = all(
        [
            str(transaction_plan.get("status") or "") == "transaction_plan_ready",
            transaction_plan_binding_valid,
            transaction_plan_integrity_valid,
            candidate_binding_valid,
            backend_plan_binding_valid,
            planning_gate_binding_valid,
            target_identity_binding_valid,
            target_state_binding_valid,
            target_state_observation_available,
            target_state_freshness_proven,
            not stale_target_detected,
            not target_state_changed_detected,
            not target_conflict_detected,
            idempotency_preview_valid,
            transaction_plan.get("idempotency_key_preview_authoritative") is False,
            transaction_plan.get("idempotency_enforced") is False,
            bool(dry_run.get("dry_run")) is True,
            dry_run_passed,
            not would_call_registration_function,
            planned_write_function == "register_deployed_rule_outcome_truth_record_set",
            planned_write_count == 1,
            writes_performed == 0,
            dry_run.get("execution_authorized") is False,
            dry_run.get("registration_authorized") is False,
            dry_run.get("confirmation_accepted") is False,
            dry_run.get("confirmation_enforced") is False,
        ]
    )

    if ready_to_design:
        status = "contract_ready"
        recommended_action = (
            "The frozen Phase 14 surfaces are sufficient to design a future authorization artifact and exact confirmation workflow. "
            "Keep Phase 15A read-only and defer authorization creation, confirmation matching, idempotency enforcement, and writes to Phase 15B."
        )
    elif binding.get("status") in {"missing", "malformed"}:
        status = str(binding.get("status"))
        recommended_action = "Resolve missing or malformed frozen prerequisites before evaluating any future authorization contract."
    elif dry_run.get("status") in {"missing", "malformed"}:
        status = str(dry_run.get("status"))
        recommended_action = "Resolve missing or malformed dry-run prerequisites before evaluating any future authorization contract."
    elif target_conflict_detected or str(binding.get("status")) == "target_conflict":
        status = "target_conflict"
        recommended_action = "A detected target conflict blocks future authorization design until the conflicting target state is resolved."
    elif str(binding.get("status")) in {"stale_target", "stale_candidate"} or stale_target_detected or target_state_changed_detected:
        status = "stale"
        recommended_action = "Stale candidate or target-state evidence blocks the future authorization contract until the frozen prerequisites are rebuilt."
    elif str(binding.get("status")) in {"modified_backend_plan", "modified_transaction_plan"}:
        status = "modified"
        recommended_action = "Modified backend-plan or transaction-plan identities block the future authorization contract until the frozen prerequisites are rebuilt."
    elif (
        not target_state_observation_available
        or str(binding.get("status")) == "target_state_unknown"
        or str(dry_run.get("target_state") or "") == "target_state_unknown"
    ):
        status = "target_state_unknown"
        recommended_action = "Unknown target-state freshness blocks the future authorization contract. Unknown target state must remain conservative."
    elif not idempotency_preview_valid:
        status = "idempotency_prerequisite_missing"
        recommended_action = "The non-authoritative idempotency preview is inconsistent. Rebuild the frozen transaction-plan chain before designing future authorization."
    elif not dry_run_passed:
        status = "dry_run_failed"
        recommended_action = "A passing read-only dry run is required before the future authorization artifact can be designed."
    else:
        status = "blocked"
        recommended_action = "Resolve transaction-plan binding, target-state, dry-run, or no-write blockers before using this contract as a future authorization design input."

    return {
        **base_payload,
        "status": status,
        "transaction_plan_status": str(transaction_plan.get("status") or "unknown"),
        "transaction_plan_binding_status": str(binding.get("status") or "unknown"),
        "transaction_plan_binding_valid": transaction_plan_binding_valid,
        "transaction_plan_integrity_valid": transaction_plan_integrity_valid,
        "candidate_binding_valid": candidate_binding_valid,
        "backend_plan_binding_valid": backend_plan_binding_valid,
        "planning_gate_binding_valid": planning_gate_binding_valid,
        "target_identity_binding_valid": target_identity_binding_valid,
        "target_state_binding_valid": target_state_binding_valid,
        "target_state_observation_available": target_state_observation_available,
        "target_state_freshness_status": target_state_freshness_status,
        "target_state_freshness_proven": target_state_freshness_proven,
        "stale_target_detected": stale_target_detected,
        "target_state_changed_detected": target_state_changed_detected,
        "target_conflict_detected": target_conflict_detected,
        "idempotency_preview_valid": idempotency_preview_valid,
        "dry_run_status": str(dry_run.get("status") or "unknown"),
        "dry_run_passed": dry_run_passed,
        "would_call_registration_function": would_call_registration_function,
        "planned_write_function": planned_write_function,
        "planned_write_count": planned_write_count,
        "ready_to_design_future_authorization_artifact": ready_to_design,
        "blockers": blockers,
        "warnings": warnings,
        "recommended_action": recommended_action,
        "writes_performed": 0,
    }


def format_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate_report(
    transaction_plan: Mapping[str, Any],
    backend_plan: Mapping[str, Any],
    candidate_record_set: Any,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    contract_gate = build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate(
        transaction_plan,
        backend_plan,
        candidate_record_set,
        root=root,
    )
    lines = [
        "Controlled registration execution authorization and confirmation contract gate",
        f"Status: {contract_gate.get('status')}",
        f"Transaction-plan status: {contract_gate.get('transaction_plan_status')}",
        f"Transaction-plan binding status: {contract_gate.get('transaction_plan_binding_status')}",
        f"Transaction-plan binding valid: {str(bool(contract_gate.get('transaction_plan_binding_valid'))).lower()}",
        f"Transaction-plan integrity valid: {str(bool(contract_gate.get('transaction_plan_integrity_valid'))).lower()}",
        f"Target-state freshness status: {contract_gate.get('target_state_freshness_status')}",
        f"Target-state observation available: {str(bool(contract_gate.get('target_state_observation_available'))).lower()}",
        f"Target conflict detected: {str(bool(contract_gate.get('target_conflict_detected'))).lower()}",
        f"Dry-run status: {contract_gate.get('dry_run_status')}",
        f"Dry-run passed: {str(bool(contract_gate.get('dry_run_passed'))).lower()}",
        f"Ready to design future authorization artifact: {str(bool(contract_gate.get('ready_to_design_future_authorization_artifact'))).lower()}",
        f"Required future confirmation: {contract_gate.get('required_future_confirmation') or REGISTER_CONFIRMATION}",
        "Confirmation match policy: exact literal, case-sensitive, no trimming, no implicit confirmation.",
        f"Planned write function: {contract_gate.get('planned_write_function')}",
        f"Planned write count: {contract_gate.get('planned_write_count')}",
        "Authorization artifact required fields: "
        + ", ".join(str(item) for item in contract_gate.get("future_authorization_artifact_required_fields", [])),
        "Authorization binding requirements: "
        + ", ".join(str(item) for item in contract_gate.get("future_authorization_binding_requirements", [])),
        "Authorization scope requirements: "
        + ", ".join(str(item) for item in contract_gate.get("future_authorization_scope_requirements", [])),
        "Authorization single-use requirements: "
        + ", ".join(str(item) for item in contract_gate.get("future_authorization_single_use_requirements", [])),
        "Authorization invalidation conditions: "
        + ", ".join(str(item) for item in contract_gate.get("future_authorization_invalidation_conditions", [])),
        "Pre-authorization revalidation: "
        + ", ".join(str(item) for item in contract_gate.get("future_pre_authorization_revalidation", [])),
        "Pre-write revalidation: "
        + ", ".join(str(item) for item in contract_gate.get("future_pre_write_revalidation", [])),
        "Authorization failure states: "
        + ", ".join(str(item) for item in contract_gate.get("future_authorization_failure_states", [])),
        "Authorization receipt requirements: "
        + ", ".join(str(item) for item in contract_gate.get("future_authorization_receipt_requirements", [])),
        "Planned future authorization sequence: "
        + " | ".join(str(item) for item in contract_gate.get("planned_future_authorization_sequence", [])),
        "Phase 15A is backend-only, read-only, deterministic, non-executing, and non-persistent.",
        "Phase 15A does not create an authorization artifact, authorization ID, transaction, receipt, or idempotency registry entry.",
        "Phase 15A does not accept, compare, match, accept, or enforce confirmation.",
        "Phase 15A does not authorize execution or registration.",
        "A passing dry run is necessary but not sufficient for future authorization design.",
        "The current idempotency preview remains non-authoritative and unenforced.",
        "Future execution authorization must require authoritative idempotency enforcement before any write.",
        "No factual truth correctness, broad effectiveness, production correctness, deployment safety, profitability, prediction quality, or ranking claim is made here.",
    ]
    blockers = contract_gate.get("blockers", [])
    warnings = contract_gate.get("warnings", [])
    if isinstance(blockers, list) and blockers:
        lines.append("Blockers: " + ", ".join(str(item) for item in blockers))
    if isinstance(warnings, list) and warnings:
        lines.append("Warnings: " + ", ".join(str(item) for item in warnings))
    if contract_gate.get("recommended_action"):
        lines.append(f"Recommended action: {contract_gate.get('recommended_action')}")
    limitations = contract_gate.get("limitations", [])
    if isinstance(limitations, list) and limitations:
        lines.append("Limitations: " + "; ".join(str(item) for item in limitations))
    lines.append(f"Writes performed: {contract_gate.get('writes_performed', 0)}")
    return "\n".join(lines)


def build_deployed_rule_outcome_truth_record_set_controlled_registration_authorization_artifact_preview(
    transaction_plan: Mapping[str, Any],
    backend_plan: Mapping[str, Any],
    candidate_record_set: Any,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    limitations = _outcome_truth_record_set_controlled_registration_authorization_artifact_preview_limitations()
    boundary_flags = _outcome_truth_record_set_controlled_registration_authorization_artifact_preview_boundary_flags()
    base_payload = {
        "authorization_artifact_preview_schema_version": 1,
        "authorization_artifact_preview_type": "controlled_outcome_truth_record_set_registration_authorization_artifact_preview",
        "status": "missing",
        "contract_gate_status": "missing",
        "contract_gate_ready": False,
        "transaction_plan_status": "missing",
        "transaction_plan_binding_valid": False,
        "transaction_plan_integrity_valid": False,
        "candidate_binding_valid": False,
        "backend_plan_binding_valid": False,
        "target_identity_binding_valid": False,
        "target_state_binding_valid": False,
        "target_state_observation_available": False,
        "target_state_freshness_status": "unknown",
        "target_state_freshness_proven": False,
        "stale_target_detected": False,
        "target_state_changed_detected": False,
        "target_conflict_detected": False,
        "idempotency_preview_valid": False,
        "dry_run_status": "missing",
        "dry_run_passed": False,
        "dry_run_evidence_fingerprint": None,
        "dry_run_evidence_fingerprint_algorithm": "sha256",
        "dry_run_evidence_deterministic": True,
        "candidate_fingerprint": None,
        "planning_gate_fingerprint": None,
        "backend_plan_fingerprint": None,
        "target_identity_fingerprint": None,
        "target_state_snapshot_fingerprint": None,
        "transaction_plan_fingerprint": None,
        "idempotency_key_preview": None,
        "idempotency_preview_authoritative": False,
        "idempotency_preview_persisted": False,
        "idempotency_enforced": False,
        "authorization_scope_preview": {},
        "maximum_registration_attempts": 1,
        "single_use_required": True,
        "required_confirmation": REGISTER_CONFIRMATION,
        "confirmation_match_policy": _controlled_registration_confirmation_match_policy(),
        "planned_write_function": "register_deployed_rule_outcome_truth_record_set",
        "planned_write_count": 1,
        "authorization_artifact_preview_fingerprint": None,
        "authorization_artifact_preview_fingerprint_algorithm": "sha256",
        "authorization_artifact_preview_deterministic": True,
        "authorization_artifact_preview_public_safe": True,
        "authorization_artifact_preview_ready": False,
        "authorization_artifact_preview_authoritative": False,
        "authorization_artifact_preview_persisted": False,
        "authorization_artifact_created": False,
        "authorization_artifact_persisted": False,
        "authorization_id_created": False,
        "authorization_registry_created": False,
        "authorization_granted": False,
        "authorization_consumed": False,
        "confirmation_supplied_in_preview_phase": False,
        "confirmation_matched_in_preview_phase": False,
        "confirmation_accepted": False,
        "confirmation_enforced": False,
        "execution_authorized": False,
        "registration_authorized": False,
        "registration_execution_implemented": False,
        "registration_performed": False,
        "record_set_written": False,
        "blockers": [],
        "warnings": [],
        "recommended_action": "",
        "limitations": limitations,
        "boundary_flags": boundary_flags,
        "writes_performed": 0,
    }
    if transaction_plan is None:
        return {
            **base_payload,
            "status": "missing",
            "blockers": ["transaction_plan_required"],
            "recommended_action": "Provide the current read-only transaction plan before building an authorization-artifact preview.",
        }
    if not isinstance(transaction_plan, Mapping):
        return {
            **base_payload,
            "status": "malformed",
            "blockers": ["transaction_plan_malformed"],
            "recommended_action": "Provide a valid transaction-plan mapping before building an authorization-artifact preview.",
        }
    if backend_plan is None:
        return {
            **base_payload,
            "status": "missing",
            "blockers": ["backend_plan_required"],
            "recommended_action": "Provide the current frozen backend plan before building an authorization-artifact preview.",
        }
    if not isinstance(backend_plan, Mapping):
        return {
            **base_payload,
            "status": "malformed",
            "blockers": ["backend_plan_malformed"],
            "recommended_action": "Provide a valid frozen backend-plan mapping before building an authorization-artifact preview.",
        }
    if candidate_record_set is None:
        return {
            **base_payload,
            "status": "missing",
            "blockers": ["candidate_record_set_required"],
            "recommended_action": "Provide the current candidate record set before building an authorization-artifact preview.",
        }
    if not isinstance(candidate_record_set, Mapping) or not isinstance(candidate_record_set.get("records"), (list, tuple)):
        return {
            **base_payload,
            "status": "malformed",
            "blockers": ["candidate_record_set_malformed"],
            "recommended_action": "Provide a valid candidate record-set mapping before building an authorization-artifact preview.",
        }

    candidate_before = _hash_payload(_canonicalize_for_identity(candidate_record_set))
    backend_before = _hash_payload(_canonicalize_for_identity(dict(backend_plan)))
    transaction_plan_before = _hash_payload(_canonicalize_for_identity(dict(transaction_plan)))
    contract_gate = build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate(
        deepcopy(transaction_plan),
        deepcopy(backend_plan),
        deepcopy(candidate_record_set),
        root=root,
    )
    binding = validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(
        deepcopy(transaction_plan),
        deepcopy(backend_plan),
        deepcopy(candidate_record_set),
        root=root,
    )
    dry_run = run_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_dry_run(
        deepcopy(transaction_plan),
        deepcopy(backend_plan),
        deepcopy(candidate_record_set),
        root=root,
    )
    candidate_after = _hash_payload(_canonicalize_for_identity(candidate_record_set))
    backend_after = _hash_payload(_canonicalize_for_identity(dict(backend_plan)))
    transaction_plan_after = _hash_payload(_canonicalize_for_identity(dict(transaction_plan)))

    blockers = _dedupe(
        list(contract_gate.get("blockers", []))
        + list(binding.get("blockers", []))
        + list(dry_run.get("blockers", []))
    )
    warnings = _dedupe(
        list(contract_gate.get("warnings", []))
        + list(binding.get("warnings", []))
        + list(dry_run.get("warnings", []))
    )
    if candidate_before != candidate_after:
        blockers.append("candidate_input_mutated_during_authorization_preview_build")
    if backend_before != backend_after:
        blockers.append("backend_plan_input_mutated_during_authorization_preview_build")
    if transaction_plan_before != transaction_plan_after:
        blockers.append("transaction_plan_input_mutated_during_authorization_preview_build")
    blockers = _dedupe(blockers)

    candidate_fingerprint = _text(transaction_plan.get("candidate_fingerprint"))
    planning_gate_fingerprint = _text(transaction_plan.get("planning_gate_fingerprint"))
    backend_plan_fingerprint = _text(transaction_plan.get("backend_plan_fingerprint"))
    target_identity_fingerprint = _text(transaction_plan.get("target_identity_fingerprint"))
    target_state_snapshot_fingerprint = _text(transaction_plan.get("target_state_snapshot_fingerprint"))
    transaction_plan_fingerprint = _text(transaction_plan.get("transaction_plan_fingerprint"))
    idempotency_key_preview = _text(transaction_plan.get("idempotency_key_preview"))
    planned_write_function = _text(transaction_plan.get("planned_write_function")) or "register_deployed_rule_outcome_truth_record_set"
    planned_write_count = _integer_or_none(transaction_plan.get("planned_write_count")) or 1
    dry_run_evidence_fingerprint = _compute_controlled_registration_dry_run_evidence_fingerprint(
        dry_run=dry_run,
        transaction_plan=transaction_plan,
        binding=binding,
    )
    authorization_scope_preview = {
        "scope_type": "single_controlled_outcome_truth_record_set_registration_attempt",
        "candidate_fingerprint": candidate_fingerprint,
        "backend_plan_fingerprint": backend_plan_fingerprint,
        "transaction_plan_fingerprint": transaction_plan_fingerprint,
        "target_identity_fingerprint": target_identity_fingerprint,
        "target_state_snapshot_fingerprint": target_state_snapshot_fingerprint,
        "dry_run_evidence_fingerprint": dry_run_evidence_fingerprint,
        "planned_write_function": planned_write_function,
        "maximum_registration_attempts": 1,
        "single_use_required": True,
        "repair_authority": False,
        "migration_authority": False,
        "scoring_authority": False,
        "rollback_authority": False,
    }

    preview = {
        **base_payload,
        "contract_gate_status": str(contract_gate.get("status") or "unknown"),
        "contract_gate_ready": bool(contract_gate.get("ready_to_design_future_authorization_artifact")),
        "transaction_plan_status": str(transaction_plan.get("status") or "unknown"),
        "transaction_plan_binding_valid": bool(binding.get("transaction_plan_binding_valid")),
        "transaction_plan_integrity_valid": bool(binding.get("transaction_plan_integrity_valid")),
        "candidate_binding_valid": bool(binding.get("candidate_binding_valid")),
        "backend_plan_binding_valid": bool(binding.get("backend_plan_binding_valid")),
        "target_identity_binding_valid": bool(binding.get("target_identity_binding_valid")),
        "target_state_binding_valid": bool(binding.get("target_state_binding_valid")),
        "target_state_observation_available": bool(binding.get("target_state_observation_available")),
        "target_state_freshness_status": str(binding.get("target_state_freshness_status") or "unknown"),
        "target_state_freshness_proven": bool(binding.get("target_state_freshness_proven")),
        "stale_target_detected": bool(binding.get("stale_target_detected")),
        "target_state_changed_detected": bool(binding.get("target_state_changed_detected")),
        "target_conflict_detected": bool(binding.get("target_conflict_detected")),
        "idempotency_preview_valid": bool(binding.get("idempotency_preview_valid")),
        "dry_run_status": str(dry_run.get("status") or "unknown"),
        "dry_run_passed": bool(dry_run.get("dry_run_passed")),
        "dry_run_evidence_fingerprint": dry_run_evidence_fingerprint,
        "candidate_fingerprint": candidate_fingerprint,
        "planning_gate_fingerprint": planning_gate_fingerprint,
        "backend_plan_fingerprint": backend_plan_fingerprint,
        "target_identity_fingerprint": target_identity_fingerprint,
        "target_state_snapshot_fingerprint": target_state_snapshot_fingerprint,
        "transaction_plan_fingerprint": transaction_plan_fingerprint,
        "idempotency_key_preview": idempotency_key_preview,
        "idempotency_preview_authoritative": False,
        "idempotency_preview_persisted": False,
        "idempotency_enforced": False,
        "authorization_scope_preview": authorization_scope_preview,
        "planned_write_function": planned_write_function,
        "planned_write_count": planned_write_count,
        "blockers": blockers,
        "warnings": warnings,
    }
    preview["authorization_artifact_preview_fingerprint"] = _compute_controlled_registration_authorization_artifact_preview_fingerprint(
        preview
    )

    gate_status = str(contract_gate.get("status") or "blocked")
    if gate_status == "contract_ready" and bool(contract_gate.get("ready_to_design_future_authorization_artifact")):
        status = "preview_ready"
        preview_ready = True
        recommended_action = (
            "The frozen prerequisites support a deterministic non-authoritative authorization-artifact preview. "
            "Use Phase 15B confirmation dry runs for exact-match evidence only, then defer authority creation to Phase 15C."
        )
    elif gate_status in {"missing", "malformed"}:
        status = gate_status
        preview_ready = False
        recommended_action = "Resolve missing or malformed prerequisites before building an authorization-artifact preview."
    elif gate_status == "target_conflict":
        status = "target_conflict"
        preview_ready = False
        recommended_action = "A target conflict blocks authorization-preview readiness until the conflicting target state is resolved."
    elif gate_status == "stale":
        status = "stale"
        preview_ready = False
        recommended_action = "Stale candidate or target-state evidence blocks authorization-preview readiness until the frozen prerequisites are rebuilt."
    elif gate_status == "modified":
        status = "modified"
        preview_ready = False
        recommended_action = "Modified backend-plan or transaction-plan identities block authorization-preview readiness until the frozen prerequisites are rebuilt."
    elif gate_status == "target_state_unknown":
        status = "target_state_unknown"
        preview_ready = False
        recommended_action = "Unknown target-state freshness blocks authorization-preview readiness. Unknown target state must remain conservative."
    elif gate_status == "dry_run_failed":
        status = "dry_run_failed"
        preview_ready = False
        recommended_action = "A passing read-only Phase 14 dry run is required before building an authorization-artifact preview."
    else:
        status = "contract_gate_blocked"
        preview_ready = False
        recommended_action = "The Phase 15A contract gate remains blocked. Resolve frozen prerequisite blockers before building an authorization-artifact preview."

    return {
        **preview,
        "status": status,
        "authorization_artifact_preview_ready": preview_ready,
        "recommended_action": recommended_action,
        "writes_performed": 0,
    }


def format_deployed_rule_outcome_truth_record_set_controlled_registration_authorization_artifact_preview_report(
    transaction_plan: Mapping[str, Any],
    backend_plan: Mapping[str, Any],
    candidate_record_set: Any,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    preview = build_deployed_rule_outcome_truth_record_set_controlled_registration_authorization_artifact_preview(
        transaction_plan,
        backend_plan,
        candidate_record_set,
        root=root,
    )
    lines = [
        "Controlled registration authorization-artifact preview",
        f"Status: {preview.get('status')}",
        f"Contract-gate status: {preview.get('contract_gate_status')}",
        f"Preview ready: {str(bool(preview.get('authorization_artifact_preview_ready'))).lower()}",
        f"Transaction-plan status: {preview.get('transaction_plan_status')}",
        f"Target-state freshness status: {preview.get('target_state_freshness_status')}",
        f"Dry-run status: {preview.get('dry_run_status')}",
        f"Dry-run evidence fingerprint: {preview.get('dry_run_evidence_fingerprint')}",
        f"Authorization-preview fingerprint: {preview.get('authorization_artifact_preview_fingerprint')}",
        f"Idempotency preview: {preview.get('idempotency_key_preview')}",
        f"Required confirmation: {preview.get('required_confirmation') or REGISTER_CONFIRMATION}",
        "Confirmation match policy: exact literal, case-sensitive, no trimming, no Unicode normalization, no substring/prefix/suffix matching, no implicit confirmation.",
        f"Planned write function: {preview.get('planned_write_function')}",
        f"Planned write count: {preview.get('planned_write_count')}",
        "Authorization scope preview: "
        + ", ".join(
            [
                f"scope_type={((preview.get('authorization_scope_preview') or {}).get('scope_type') or 'none')}",
                f"maximum_registration_attempts={((preview.get('authorization_scope_preview') or {}).get('maximum_registration_attempts') or 'none')}",
                f"single_use_required={str(bool((preview.get('authorization_scope_preview') or {}).get('single_use_required'))).lower()}",
            ]
        ),
        "Phase 15B builds a deterministic non-authoritative authorization-artifact preview and evaluates confirmation matching through a read-only dry run.",
        "Phase 15B does not create an authorization artifact.",
        "Phase 15B does not persist an authorization preview.",
        "Phase 15B does not grant execution authorization.",
        "Phase 15B does not grant registration authorization.",
        "Phase 15B does not accept or enforce confirmation.",
        "The dry-run evidence fingerprint identifies stable structural dry-run evidence only.",
        "The authorization-preview fingerprint identifies the deterministic preview contract only.",
        "Neither fingerprint is an authorization ID.",
        "Neither fingerprint grants authority.",
        "The idempotency-key preview remains non-authoritative, unpersisted, unreserved, and unenforced.",
        "planned_write_count = 1 describes future intent only.",
        "writes_performed = 0 records actual Phase 15B behavior.",
        "Stale, modified, or conflicting status must take precedence over target_state_unknown.",
        "A valid fingerprint proves integrity against the defined canonical representation only.",
        "It does not prove factual correctness of outcome-truth records.",
    ]
    blockers = preview.get("blockers", [])
    warnings = preview.get("warnings", [])
    if isinstance(blockers, list) and blockers:
        lines.append("Blockers: " + ", ".join(str(item) for item in blockers))
    if isinstance(warnings, list) and warnings:
        lines.append("Warnings: " + ", ".join(str(item) for item in warnings))
    if preview.get("recommended_action"):
        lines.append(f"Recommended action: {preview.get('recommended_action')}")
    limitations = preview.get("limitations", [])
    if isinstance(limitations, list) and limitations:
        lines.append("Limitations: " + "; ".join(str(item) for item in limitations))
    lines.append(f"Writes performed: {preview.get('writes_performed', 0)}")
    return "\n".join(lines)


def run_deployed_rule_outcome_truth_record_set_controlled_registration_confirmation_dry_run(
    authorization_artifact_preview: Mapping[str, Any],
    confirmation_text: str,
    transaction_plan: Mapping[str, Any],
    backend_plan: Mapping[str, Any],
    candidate_record_set: Any,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    limitations = _outcome_truth_record_set_controlled_registration_confirmation_dry_run_limitations()
    boundary_flags = _outcome_truth_record_set_controlled_registration_confirmation_dry_run_boundary_flags()
    base_payload = {
        "confirmation_dry_run_schema_version": 1,
        "confirmation_dry_run_type": "controlled_outcome_truth_record_set_registration_confirmation_dry_run",
        "status": "blocked",
        "confirmation_dry_run": True,
        "authorization_artifact_preview_status": "missing",
        "authorization_artifact_preview_ready": False,
        "authorization_artifact_preview_integrity_valid": False,
        "authorization_artifact_preview_fingerprint_valid": False,
        "dry_run_evidence_fingerprint_valid": False,
        "contract_gate_status": "missing",
        "contract_gate_ready": False,
        "transaction_plan_binding_valid": False,
        "transaction_plan_integrity_valid": False,
        "target_identity_binding_valid": False,
        "target_state_binding_valid": False,
        "target_state_observation_available": False,
        "target_state_freshness_status": "unknown",
        "target_state_freshness_proven": False,
        "stale_target_detected": False,
        "target_state_changed_detected": False,
        "target_conflict_detected": False,
        "idempotency_preview_valid": False,
        "idempotency_preview_authoritative": False,
        "idempotency_preview_persisted": False,
        "idempotency_enforced": False,
        "required_confirmation": REGISTER_CONFIRMATION,
        "confirmation_match_policy": _controlled_registration_confirmation_match_policy(),
        "confirmation_supplied": False,
        "confirmation_exact_match": False,
        "confirmation_evidence_fingerprint": None,
        "confirmation_evidence_fingerprint_algorithm": "sha256",
        "confirmation_evidence_deterministic": True,
        "confirmation_evidence_persisted": False,
        "confirmation_input_persisted": False,
        "confirmation_input_echoed": False,
        "confirmation_accepted": False,
        "confirmation_enforced": False,
        "authorization_artifact_created": False,
        "authorization_artifact_persisted": False,
        "authorization_granted": False,
        "authorization_consumed": False,
        "execution_authorized": False,
        "registration_authorized": False,
        "registration_performed": False,
        "would_call_registration_function": False,
        "planned_write_count": 1,
        "writes_performed": 0,
        "blockers": [],
        "warnings": [],
        "recommended_action": "",
        "limitations": limitations,
        "boundary_flags": boundary_flags,
    }
    if authorization_artifact_preview is None:
        return {
            **base_payload,
            "status": "preview_invalid",
            "blockers": ["authorization_artifact_preview_required"],
            "recommended_action": "Provide the current authorization-artifact preview before running the confirmation dry run.",
        }
    if not isinstance(authorization_artifact_preview, Mapping):
        return {
            **base_payload,
            "status": "preview_invalid",
            "blockers": ["authorization_artifact_preview_malformed"],
            "recommended_action": "Provide a valid authorization-artifact preview mapping before running the confirmation dry run.",
        }
    if transaction_plan is None:
        return {
            **base_payload,
            "status": "missing",
            "blockers": ["transaction_plan_required"],
            "recommended_action": "Provide the current transaction plan before running the confirmation dry run.",
        }
    if not isinstance(transaction_plan, Mapping):
        return {
            **base_payload,
            "status": "malformed",
            "blockers": ["transaction_plan_malformed"],
            "recommended_action": "Provide a valid transaction-plan mapping before running the confirmation dry run.",
        }
    if backend_plan is None:
        return {
            **base_payload,
            "status": "missing",
            "blockers": ["backend_plan_required"],
            "recommended_action": "Provide the current backend plan before running the confirmation dry run.",
        }
    if not isinstance(backend_plan, Mapping):
        return {
            **base_payload,
            "status": "malformed",
            "blockers": ["backend_plan_malformed"],
            "recommended_action": "Provide a valid backend-plan mapping before running the confirmation dry run.",
        }
    if candidate_record_set is None:
        return {
            **base_payload,
            "status": "missing",
            "blockers": ["candidate_record_set_required"],
            "recommended_action": "Provide the current candidate record set before running the confirmation dry run.",
        }
    if not isinstance(candidate_record_set, Mapping) or not isinstance(candidate_record_set.get("records"), (list, tuple)):
        return {
            **base_payload,
            "status": "malformed",
            "blockers": ["candidate_record_set_malformed"],
            "recommended_action": "Provide a valid candidate record-set mapping before running the confirmation dry run.",
        }

    preview_before = _hash_payload(_canonicalize_for_identity(dict(authorization_artifact_preview)))
    candidate_before = _hash_payload(_canonicalize_for_identity(candidate_record_set))
    backend_before = _hash_payload(_canonicalize_for_identity(dict(backend_plan)))
    transaction_plan_before = _hash_payload(_canonicalize_for_identity(dict(transaction_plan)))
    expected_preview = build_deployed_rule_outcome_truth_record_set_controlled_registration_authorization_artifact_preview(
        deepcopy(transaction_plan),
        deepcopy(backend_plan),
        deepcopy(candidate_record_set),
        root=root,
    )
    preview_after = _hash_payload(_canonicalize_for_identity(dict(authorization_artifact_preview)))
    candidate_after = _hash_payload(_canonicalize_for_identity(candidate_record_set))
    backend_after = _hash_payload(_canonicalize_for_identity(dict(backend_plan)))
    transaction_plan_after = _hash_payload(_canonicalize_for_identity(dict(transaction_plan)))

    blockers = _dedupe(
        list(expected_preview.get("blockers", []))
    )
    warnings = _dedupe(
        list(expected_preview.get("warnings", []))
    )
    if preview_before != preview_after:
        blockers.append("authorization_artifact_preview_input_mutated_during_confirmation_dry_run")
    if candidate_before != candidate_after:
        blockers.append("candidate_input_mutated_during_confirmation_dry_run")
    if backend_before != backend_after:
        blockers.append("backend_plan_input_mutated_during_confirmation_dry_run")
    if transaction_plan_before != transaction_plan_after:
        blockers.append("transaction_plan_input_mutated_during_confirmation_dry_run")

    supplied_preview_fingerprint = _text(authorization_artifact_preview.get("authorization_artifact_preview_fingerprint"))
    expected_preview_fingerprint = _text(expected_preview.get("authorization_artifact_preview_fingerprint"))
    recomputed_supplied_preview_fingerprint = _compute_controlled_registration_authorization_artifact_preview_fingerprint(
        authorization_artifact_preview
    )
    authorization_artifact_preview_fingerprint_valid = bool(
        supplied_preview_fingerprint
        and recomputed_supplied_preview_fingerprint
        and supplied_preview_fingerprint == recomputed_supplied_preview_fingerprint
        and _is_sha256_fingerprint(supplied_preview_fingerprint)
    )
    authorization_artifact_preview_integrity_valid = bool(
        authorization_artifact_preview_fingerprint_valid
        and expected_preview_fingerprint
        and supplied_preview_fingerprint == expected_preview_fingerprint
    )
    supplied_dry_run_evidence_fingerprint = _text(authorization_artifact_preview.get("dry_run_evidence_fingerprint"))
    expected_dry_run_evidence_fingerprint = _text(expected_preview.get("dry_run_evidence_fingerprint"))
    dry_run_evidence_fingerprint_valid = bool(
        supplied_dry_run_evidence_fingerprint
        and expected_dry_run_evidence_fingerprint
        and supplied_dry_run_evidence_fingerprint == expected_dry_run_evidence_fingerprint
        and _is_sha256_fingerprint(supplied_dry_run_evidence_fingerprint)
    )
    if not authorization_artifact_preview_fingerprint_valid:
        blockers.append("authorization_artifact_preview_fingerprint_mismatch")
    if authorization_artifact_preview_fingerprint_valid and not authorization_artifact_preview_integrity_valid:
        blockers.append("authorization_artifact_preview_integrity_mismatch")
    if not dry_run_evidence_fingerprint_valid:
        blockers.append("dry_run_evidence_fingerprint_mismatch")

    confirmation_supplied = isinstance(confirmation_text, str) and confirmation_text != ""
    confirmation_exact_match = confirmation_text == REGISTER_CONFIRMATION
    confirmation_evidence_fingerprint = _compute_controlled_registration_confirmation_evidence_fingerprint(
        authorization_artifact_preview_fingerprint=expected_preview_fingerprint,
        dry_run_evidence_fingerprint=expected_dry_run_evidence_fingerprint,
        required_confirmation=REGISTER_CONFIRMATION,
        confirmation_match_policy=_controlled_registration_confirmation_match_policy(),
        confirmation_supplied=confirmation_supplied,
        confirmation_exact_match=confirmation_exact_match,
        transaction_plan_fingerprint=_text(transaction_plan.get("transaction_plan_fingerprint")),
        target_state_snapshot_fingerprint=_text(transaction_plan.get("target_state_snapshot_fingerprint")),
        idempotency_key_preview=_text(transaction_plan.get("idempotency_key_preview")),
    )

    preview_status = str(expected_preview.get("status") or "blocked")
    if preview_status in {"stale", "modified", "target_conflict", "target_state_unknown", "dry_run_failed"}:
        status = preview_status
    elif preview_status in {"missing", "malformed"}:
        status = preview_status
    elif not authorization_artifact_preview_integrity_valid or not dry_run_evidence_fingerprint_valid:
        status = "preview_invalid"
    elif preview_status not in {"preview_ready"} or not bool(expected_preview.get("authorization_artifact_preview_ready")):
        status = "contract_gate_blocked"
    elif not bool(expected_preview.get("idempotency_preview_valid")):
        status = "blocked"
    elif not confirmation_supplied:
        status = "confirmation_missing"
    elif confirmation_exact_match:
        status = "confirmation_match"
    else:
        status = "confirmation_mismatch"

    if status == "confirmation_match":
        recommended_action = (
            "Exact confirmation match was evaluated in a dry run only. No authorization was created or granted."
        )
    elif status == "confirmation_mismatch":
        recommended_action = "The supplied confirmation text did not exactly match the frozen literal. No authorization was created or granted."
    elif status == "confirmation_missing":
        recommended_action = "Provide the exact future confirmation phrase in a dry run only if all frozen prerequisites remain valid."
    elif status == "preview_invalid":
        recommended_action = "The supplied authorization-artifact preview is invalid or modified. Rebuild the preview and rerun the confirmation dry run without repairing inputs in place."
    elif status == "contract_gate_blocked":
        recommended_action = "Resolve contract-gate blockers before running confirmation-match evidence."
    elif status == "target_conflict":
        recommended_action = "A target conflict blocks confirmation evidence even if the supplied text matches exactly."
    elif status == "target_state_unknown":
        recommended_action = "Unknown target-state freshness blocks confirmation evidence even if the supplied text matches exactly."
    elif status == "stale":
        recommended_action = "Stale prerequisites block confirmation evidence even if the supplied text matches exactly."
    elif status == "modified":
        recommended_action = "Modified prerequisites block confirmation evidence even if the supplied text matches exactly."
    elif status == "dry_run_failed":
        recommended_action = "A passing Phase 14 dry run remains required before confirmation evidence can be evaluated."
    else:
        recommended_action = "Resolve preview integrity, frozen prerequisite, or confirmation blockers before treating this as confirmation-match evidence."

    return {
        **base_payload,
        "status": status,
        "authorization_artifact_preview_status": preview_status,
        "authorization_artifact_preview_ready": bool(expected_preview.get("authorization_artifact_preview_ready")),
        "authorization_artifact_preview_integrity_valid": authorization_artifact_preview_integrity_valid,
        "authorization_artifact_preview_fingerprint_valid": authorization_artifact_preview_fingerprint_valid,
        "dry_run_evidence_fingerprint_valid": dry_run_evidence_fingerprint_valid,
        "contract_gate_status": str(expected_preview.get("contract_gate_status") or "unknown"),
        "contract_gate_ready": bool(expected_preview.get("contract_gate_ready")),
        "transaction_plan_binding_valid": bool(expected_preview.get("transaction_plan_binding_valid")),
        "transaction_plan_integrity_valid": bool(expected_preview.get("transaction_plan_integrity_valid")),
        "target_identity_binding_valid": bool(expected_preview.get("target_identity_binding_valid")),
        "target_state_binding_valid": bool(expected_preview.get("target_state_binding_valid")),
        "target_state_observation_available": bool(expected_preview.get("target_state_observation_available")),
        "target_state_freshness_status": str(expected_preview.get("target_state_freshness_status") or "unknown"),
        "target_state_freshness_proven": bool(expected_preview.get("target_state_freshness_proven")),
        "stale_target_detected": bool(expected_preview.get("stale_target_detected")),
        "target_state_changed_detected": bool(expected_preview.get("target_state_changed_detected")),
        "target_conflict_detected": bool(expected_preview.get("target_conflict_detected")),
        "idempotency_preview_valid": bool(expected_preview.get("idempotency_preview_valid")),
        "idempotency_preview_authoritative": False,
        "idempotency_preview_persisted": False,
        "idempotency_enforced": False,
        "confirmation_supplied": confirmation_supplied,
        "confirmation_exact_match": confirmation_exact_match,
        "confirmation_evidence_fingerprint": confirmation_evidence_fingerprint,
        "planned_write_count": _integer_or_none(expected_preview.get("planned_write_count")) or 1,
        "blockers": _dedupe(blockers),
        "warnings": _dedupe(warnings),
        "recommended_action": recommended_action,
    }


def format_deployed_rule_outcome_truth_record_set_controlled_registration_confirmation_dry_run_report(
    authorization_artifact_preview: Mapping[str, Any],
    confirmation_text: str,
    transaction_plan: Mapping[str, Any],
    backend_plan: Mapping[str, Any],
    candidate_record_set: Any,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    confirmation_dry_run = run_deployed_rule_outcome_truth_record_set_controlled_registration_confirmation_dry_run(
        authorization_artifact_preview,
        confirmation_text,
        transaction_plan,
        backend_plan,
        candidate_record_set,
        root=root,
    )
    lines = [
        "Controlled registration confirmation dry run",
        f"Status: {confirmation_dry_run.get('status')}",
        f"Authorization-preview status: {confirmation_dry_run.get('authorization_artifact_preview_status')}",
        f"Authorization-preview integrity valid: {str(bool(confirmation_dry_run.get('authorization_artifact_preview_integrity_valid'))).lower()}",
        f"Dry-run evidence fingerprint valid: {str(bool(confirmation_dry_run.get('dry_run_evidence_fingerprint_valid'))).lower()}",
        f"Contract-gate status: {confirmation_dry_run.get('contract_gate_status')}",
        f"Target-state freshness status: {confirmation_dry_run.get('target_state_freshness_status')}",
        f"Confirmation supplied: {str(bool(confirmation_dry_run.get('confirmation_supplied'))).lower()}",
        f"Confirmation exact match: {str(bool(confirmation_dry_run.get('confirmation_exact_match'))).lower()}",
        f"Confirmation evidence fingerprint: {confirmation_dry_run.get('confirmation_evidence_fingerprint')}",
        f"Required confirmation: {confirmation_dry_run.get('required_confirmation') or REGISTER_CONFIRMATION}",
        "Confirmation match policy: exact literal, case-sensitive, no trimming, no Unicode normalization, no substring/prefix/suffix matching, no implicit confirmation.",
        "The confirmation dry run may evaluate whether supplied text exactly matches REGISTER_OUTCOME_TRUTH_RECORD_SET.",
        "Exact matching is case-sensitive and performs no trimming, normalization, substring matching, prefix matching, suffix matching, or implicit confirmation.",
        "An exact confirmation match is dry-run evidence only.",
        "It is not accepted confirmation.",
        "It is not enforced confirmation.",
        "It is not an authorization grant.",
        "The caller-supplied confirmation text is not persisted, echoed, or included in public-safe reports.",
        "Confirmation match must not override any failed prerequisite.",
        "The idempotency-key preview remains non-authoritative, unpersisted, unreserved, and unenforced.",
        "writes_performed = 0 records actual Phase 15B behavior.",
        "A valid fingerprint proves integrity against the defined canonical representation only.",
        "It does not prove factual correctness of outcome-truth records.",
    ]
    blockers = confirmation_dry_run.get("blockers", [])
    warnings = confirmation_dry_run.get("warnings", [])
    if isinstance(blockers, list) and blockers:
        lines.append("Blockers: " + ", ".join(str(item) for item in blockers))
    if isinstance(warnings, list) and warnings:
        lines.append("Warnings: " + ", ".join(str(item) for item in warnings))
    if confirmation_dry_run.get("recommended_action"):
        lines.append(f"Recommended action: {confirmation_dry_run.get('recommended_action')}")
    limitations = confirmation_dry_run.get("limitations", [])
    if isinstance(limitations, list) and limitations:
        lines.append("Limitations: " + "; ".join(str(item) for item in limitations))
    lines.append(f"Writes performed: {confirmation_dry_run.get('writes_performed', 0)}")
    return "\n".join(lines)


def validate_deployed_rule_outcome_truth_record_set_controlled_registration_authorization_preview_confirmation_evidence_binding(
    authorization_artifact_preview: Mapping[str, Any],
    confirmation_dry_run_result: Mapping[str, Any],
    confirmation_text: str,
    transaction_plan: Mapping[str, Any],
    backend_plan: Mapping[str, Any],
    candidate_record_set: Any,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    limitations = _outcome_truth_record_set_controlled_registration_authorization_preview_confirmation_evidence_binding_limitations()
    boundary_flags = _outcome_truth_record_set_controlled_registration_authorization_preview_confirmation_evidence_binding_boundary_flags()
    base_payload = {
        "authorization_preview_binding_schema_version": 1,
        "authorization_preview_binding_type": "controlled_outcome_truth_record_set_registration_authorization_preview_confirmation_evidence_binding",
        "status": "missing",
        "authorization_preview_binding_valid": False,
        "authorization_preview_integrity_valid": False,
        "authorization_preview_fingerprint_valid": False,
        "authorization_preview_current_binding_valid": False,
        "modified_preview_detected": False,
        "stale_preview_detected": False,
        "candidate_binding_valid": False,
        "planning_gate_binding_valid": False,
        "backend_plan_binding_valid": False,
        "transaction_plan_binding_valid": False,
        "target_identity_binding_valid": False,
        "target_state_snapshot_binding_valid": False,
        "target_state_observation_available": False,
        "target_state_freshness_status": "unknown",
        "target_state_freshness_proven": False,
        "stale_target_detected": False,
        "target_state_changed_detected": False,
        "target_conflict_detected": False,
        "dry_run_evidence_binding_valid": False,
        "idempotency_preview_binding_valid": False,
        "authorization_scope_binding_valid": False,
        "authorization_scope_modified_detected": False,
        "confirmation_contract_binding_valid": False,
        "confirmation_policy_modified_detected": False,
        "confirmation_dry_run_integrity_valid": False,
        "confirmation_dry_run_current_binding_valid": False,
        "confirmation_dry_run_modified_detected": False,
        "confirmation_dry_run_stale_detected": False,
        "confirmation_supplied": False,
        "confirmation_exact_match": False,
        "confirmation_evidence_binding_valid": False,
        "confirmation_evidence_fingerprint_valid": False,
        "stored_authorization_preview_fingerprint": None,
        "expected_authorization_preview_fingerprint": None,
        "stored_dry_run_evidence_fingerprint": None,
        "expected_dry_run_evidence_fingerprint": None,
        "stored_confirmation_evidence_fingerprint": None,
        "expected_confirmation_evidence_fingerprint": None,
        "would_call_registration_function": False,
        "planned_write_count": 1,
        "writes_performed": 0,
        "authorization_artifact_created": False,
        "authorization_artifact_persisted": False,
        "authorization_granted": False,
        "authorization_consumed": False,
        "confirmation_accepted": False,
        "confirmation_enforced": False,
        "execution_authorized": False,
        "registration_authorized": False,
        "registration_performed": False,
        "authorization_artifact_preview_authoritative": False,
        "authorization_artifact_preview_persisted": False,
        "confirmation_evidence_persisted": False,
        "idempotency_preview_authoritative": False,
        "idempotency_preview_persisted": False,
        "idempotency_enforced": False,
        "blockers": [],
        "warnings": [],
        "recommended_action": "",
        "limitations": limitations,
        "boundary_flags": boundary_flags,
    }
    if authorization_artifact_preview is None:
        return {
            **base_payload,
            "status": "missing",
            "blockers": ["authorization_artifact_preview_required"],
            "recommended_action": "Provide the current authorization-artifact preview before validating preview/evidence binding.",
        }
    if not isinstance(authorization_artifact_preview, Mapping):
        return {
            **base_payload,
            "status": "malformed",
            "blockers": ["authorization_artifact_preview_malformed"],
            "recommended_action": "Provide a valid authorization-artifact preview mapping before validating preview/evidence binding.",
        }
    if confirmation_dry_run_result is None:
        return {
            **base_payload,
            "status": "missing",
            "blockers": ["confirmation_dry_run_result_required"],
            "recommended_action": "Provide the confirmation dry-run result before validating preview/evidence binding.",
        }
    if not isinstance(confirmation_dry_run_result, Mapping):
        return {
            **base_payload,
            "status": "malformed",
            "blockers": ["confirmation_dry_run_result_malformed"],
            "recommended_action": "Provide a valid confirmation dry-run mapping before validating preview/evidence binding.",
        }
    if not isinstance(confirmation_text, str):
        return {
            **base_payload,
            "status": "malformed",
            "blockers": ["confirmation_text_malformed"],
            "recommended_action": "Provide the confirmation text as a string before validating preview/evidence binding.",
        }
    if transaction_plan is None:
        return {
            **base_payload,
            "status": "missing",
            "blockers": ["transaction_plan_required"],
            "recommended_action": "Provide the current transaction plan before validating preview/evidence binding.",
        }
    if not isinstance(transaction_plan, Mapping):
        return {
            **base_payload,
            "status": "malformed",
            "blockers": ["transaction_plan_malformed"],
            "recommended_action": "Provide a valid transaction-plan mapping before validating preview/evidence binding.",
        }
    if backend_plan is None:
        return {
            **base_payload,
            "status": "missing",
            "blockers": ["backend_plan_required"],
            "recommended_action": "Provide the current backend plan before validating preview/evidence binding.",
        }
    if not isinstance(backend_plan, Mapping):
        return {
            **base_payload,
            "status": "malformed",
            "blockers": ["backend_plan_malformed"],
            "recommended_action": "Provide a valid backend-plan mapping before validating preview/evidence binding.",
        }
    if candidate_record_set is None:
        return {
            **base_payload,
            "status": "missing",
            "blockers": ["candidate_record_set_required"],
            "recommended_action": "Provide the current candidate record set before validating preview/evidence binding.",
        }
    if not isinstance(candidate_record_set, Mapping) or not isinstance(candidate_record_set.get("records"), (list, tuple)):
        return {
            **base_payload,
            "status": "malformed",
            "blockers": ["candidate_record_set_malformed"],
            "recommended_action": "Provide a valid candidate record-set mapping before validating preview/evidence binding.",
        }

    preview_before = _hash_payload(_canonicalize_for_identity(dict(authorization_artifact_preview)))
    confirmation_before = _hash_payload(_canonicalize_for_identity(dict(confirmation_dry_run_result)))
    candidate_before = _hash_payload(_canonicalize_for_identity(candidate_record_set))
    backend_before = _hash_payload(_canonicalize_for_identity(dict(backend_plan)))
    transaction_before = _hash_payload(_canonicalize_for_identity(dict(transaction_plan)))
    expected_preview = build_deployed_rule_outcome_truth_record_set_controlled_registration_authorization_artifact_preview(
        deepcopy(transaction_plan),
        deepcopy(backend_plan),
        deepcopy(candidate_record_set),
        root=root,
    )
    expected_confirmation = run_deployed_rule_outcome_truth_record_set_controlled_registration_confirmation_dry_run(
        deepcopy(expected_preview),
        confirmation_text,
        deepcopy(transaction_plan),
        deepcopy(backend_plan),
        deepcopy(candidate_record_set),
        root=root,
    )
    contract_gate = build_deployed_rule_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate(
        deepcopy(transaction_plan),
        deepcopy(backend_plan),
        deepcopy(candidate_record_set),
        root=root,
    )
    binding = validate_deployed_rule_outcome_truth_record_set_controlled_registration_transaction_plan_binding(
        deepcopy(transaction_plan),
        deepcopy(backend_plan),
        deepcopy(candidate_record_set),
        root=root,
    )
    preview_after = _hash_payload(_canonicalize_for_identity(dict(authorization_artifact_preview)))
    confirmation_after = _hash_payload(_canonicalize_for_identity(dict(confirmation_dry_run_result)))
    candidate_after = _hash_payload(_canonicalize_for_identity(candidate_record_set))
    backend_after = _hash_payload(_canonicalize_for_identity(dict(backend_plan)))
    transaction_after = _hash_payload(_canonicalize_for_identity(dict(transaction_plan)))

    blockers = _dedupe(
        list(expected_preview.get("blockers", []))
        + list(expected_confirmation.get("blockers", []))
        + list(binding.get("blockers", []))
        + list(contract_gate.get("blockers", []))
    )
    warnings = _dedupe(
        list(expected_preview.get("warnings", []))
        + list(expected_confirmation.get("warnings", []))
        + list(binding.get("warnings", []))
        + list(contract_gate.get("warnings", []))
    )
    if preview_before != preview_after:
        blockers.append("authorization_artifact_preview_input_mutated_during_binding_validation")
    if confirmation_before != confirmation_after:
        blockers.append("confirmation_dry_run_result_input_mutated_during_binding_validation")
    if candidate_before != candidate_after:
        blockers.append("candidate_input_mutated_during_binding_validation")
    if backend_before != backend_after:
        blockers.append("backend_plan_input_mutated_during_binding_validation")
    if transaction_before != transaction_after:
        blockers.append("transaction_plan_input_mutated_during_binding_validation")

    stored_authorization_preview_fingerprint = _text(authorization_artifact_preview.get("authorization_artifact_preview_fingerprint"))
    expected_authorization_preview_fingerprint = _text(expected_preview.get("authorization_artifact_preview_fingerprint"))
    recomputed_authorization_preview_fingerprint = _compute_controlled_registration_authorization_artifact_preview_fingerprint(
        authorization_artifact_preview
    )
    authorization_preview_fingerprint_valid = bool(
        stored_authorization_preview_fingerprint
        and recomputed_authorization_preview_fingerprint
        and stored_authorization_preview_fingerprint == recomputed_authorization_preview_fingerprint
        and _is_sha256_fingerprint(stored_authorization_preview_fingerprint)
    )
    authorization_preview_integrity_valid = authorization_preview_fingerprint_valid
    modified_preview_detected = not authorization_preview_fingerprint_valid
    authorization_preview_current_binding_valid = bool(
        authorization_preview_fingerprint_valid
        and expected_authorization_preview_fingerprint
        and stored_authorization_preview_fingerprint == expected_authorization_preview_fingerprint
    )
    stale_preview_detected = bool(authorization_preview_integrity_valid and not authorization_preview_current_binding_valid)
    if modified_preview_detected:
        blockers.append("authorization_artifact_preview_fingerprint_mismatch")

    candidate_binding_valid = bool(binding.get("candidate_binding_valid")) and (
        _text(authorization_artifact_preview.get("candidate_fingerprint")) == _text(expected_preview.get("candidate_fingerprint"))
    )
    planning_gate_binding_valid = bool(binding.get("planning_gate_binding_valid", True)) and (
        _text(authorization_artifact_preview.get("planning_gate_fingerprint")) == _text(expected_preview.get("planning_gate_fingerprint"))
    )
    backend_plan_binding_valid = bool(binding.get("backend_plan_binding_valid")) and (
        _text(authorization_artifact_preview.get("backend_plan_fingerprint")) == _text(expected_preview.get("backend_plan_fingerprint"))
    )
    transaction_plan_binding_valid = bool(binding.get("transaction_plan_binding_valid")) and (
        _text(authorization_artifact_preview.get("transaction_plan_fingerprint")) == _text(expected_preview.get("transaction_plan_fingerprint"))
    )
    target_identity_binding_valid = bool(binding.get("target_identity_binding_valid")) and (
        _text(authorization_artifact_preview.get("target_identity_fingerprint")) == _text(expected_preview.get("target_identity_fingerprint"))
    )
    target_state_snapshot_binding_valid = bool(binding.get("target_state_binding_valid")) and (
        _text(authorization_artifact_preview.get("target_state_snapshot_fingerprint")) == _text(expected_preview.get("target_state_snapshot_fingerprint"))
    )

    stored_dry_run_evidence_fingerprint = _text(authorization_artifact_preview.get("dry_run_evidence_fingerprint"))
    expected_dry_run_evidence_fingerprint = _text(expected_preview.get("dry_run_evidence_fingerprint"))
    dry_run_evidence_binding_valid = bool(
        stored_dry_run_evidence_fingerprint
        and expected_dry_run_evidence_fingerprint
        and stored_dry_run_evidence_fingerprint == expected_dry_run_evidence_fingerprint
        and _is_sha256_fingerprint(stored_dry_run_evidence_fingerprint)
    )
    if not dry_run_evidence_binding_valid:
        blockers.append("authorization_preview_dry_run_evidence_mismatch")

    idempotency_preview_binding_valid = _text(authorization_artifact_preview.get("idempotency_key_preview")) == _text(expected_preview.get("idempotency_key_preview"))
    if not idempotency_preview_binding_valid:
        blockers.append("authorization_preview_idempotency_preview_mismatch")

    supplied_scope = authorization_artifact_preview.get("authorization_scope_preview")
    if not isinstance(supplied_scope, Mapping):
        supplied_scope = {}
    expected_scope = expected_preview.get("authorization_scope_preview")
    if not isinstance(expected_scope, Mapping):
        expected_scope = {}
    authorization_scope_binding_valid = _canonicalize_for_identity(supplied_scope) == _canonicalize_for_identity(expected_scope)
    authorization_scope_modified_detected = not authorization_scope_binding_valid
    if authorization_scope_modified_detected:
        blockers.append("authorization_scope_preview_mismatch")

    supplied_required_confirmation = _text(confirmation_dry_run_result.get("required_confirmation"))
    supplied_confirmation_policy = confirmation_dry_run_result.get("confirmation_match_policy")
    if not isinstance(supplied_confirmation_policy, Mapping):
        supplied_confirmation_policy = {}
    expected_confirmation_policy = _controlled_registration_confirmation_match_policy()
    confirmation_contract_binding_valid = bool(
        supplied_required_confirmation == REGISTER_CONFIRMATION
        and _canonicalize_for_identity(supplied_confirmation_policy) == _canonicalize_for_identity(expected_confirmation_policy)
        and _text(authorization_artifact_preview.get("required_confirmation")) == REGISTER_CONFIRMATION
        and _canonicalize_for_identity(authorization_artifact_preview.get("confirmation_match_policy", {}))
        == _canonicalize_for_identity(expected_confirmation_policy)
    )
    confirmation_policy_modified_detected = not confirmation_contract_binding_valid
    if confirmation_policy_modified_detected:
        blockers.append("confirmation_policy_mismatch")

    confirmation_supplied = bool(expected_confirmation.get("confirmation_supplied"))
    confirmation_exact_match = bool(expected_confirmation.get("confirmation_exact_match"))
    stored_confirmation_evidence_fingerprint = _text(confirmation_dry_run_result.get("confirmation_evidence_fingerprint"))
    expected_confirmation_evidence_fingerprint = _text(expected_confirmation.get("confirmation_evidence_fingerprint"))
    recomputed_supplied_confirmation_evidence_fingerprint = _compute_controlled_registration_confirmation_evidence_fingerprint(
        authorization_artifact_preview_fingerprint=stored_authorization_preview_fingerprint,
        dry_run_evidence_fingerprint=stored_dry_run_evidence_fingerprint,
        required_confirmation=supplied_required_confirmation or "",
        confirmation_match_policy=supplied_confirmation_policy,
        confirmation_supplied=bool(confirmation_dry_run_result.get("confirmation_supplied")),
        confirmation_exact_match=bool(confirmation_dry_run_result.get("confirmation_exact_match")),
        transaction_plan_fingerprint=_text(transaction_plan.get("transaction_plan_fingerprint")),
        target_state_snapshot_fingerprint=_text(transaction_plan.get("target_state_snapshot_fingerprint")),
        idempotency_key_preview=_text(transaction_plan.get("idempotency_key_preview")),
    )
    confirmation_evidence_fingerprint_valid = bool(
        stored_confirmation_evidence_fingerprint
        and recomputed_supplied_confirmation_evidence_fingerprint
        and stored_confirmation_evidence_fingerprint == recomputed_supplied_confirmation_evidence_fingerprint
        and _is_sha256_fingerprint(stored_confirmation_evidence_fingerprint)
    )
    confirmation_dry_run_integrity_valid = confirmation_evidence_fingerprint_valid
    confirmation_dry_run_modified_detected = not confirmation_evidence_fingerprint_valid
    if confirmation_dry_run_modified_detected:
        blockers.append("confirmation_dry_run_integrity_mismatch")
    confirmation_dry_run_current_binding_valid = bool(
        confirmation_evidence_fingerprint_valid
        and expected_confirmation_evidence_fingerprint
        and stored_confirmation_evidence_fingerprint == expected_confirmation_evidence_fingerprint
        and str(confirmation_dry_run_result.get("status") or "") == str(expected_confirmation.get("status") or "")
        and bool(confirmation_dry_run_result.get("confirmation_supplied")) == bool(expected_confirmation.get("confirmation_supplied"))
        and bool(confirmation_dry_run_result.get("confirmation_exact_match")) == bool(expected_confirmation.get("confirmation_exact_match"))
    )
    confirmation_dry_run_stale_detected = bool(
        confirmation_dry_run_integrity_valid and not confirmation_dry_run_current_binding_valid
    )
    confirmation_evidence_binding_valid = bool(
        confirmation_evidence_fingerprint_valid
        and expected_confirmation_evidence_fingerprint
        and stored_confirmation_evidence_fingerprint == expected_confirmation_evidence_fingerprint
    )
    if not confirmation_evidence_binding_valid:
        blockers.append("confirmation_evidence_fingerprint_mismatch")

    target_state_observation_available = bool(binding.get("target_state_observation_available"))
    target_state_freshness_status = str(binding.get("target_state_freshness_status") or "unknown")
    target_state_freshness_proven = bool(binding.get("target_state_freshness_proven"))
    stale_target_detected = bool(binding.get("stale_target_detected"))
    target_state_changed_detected = bool(binding.get("target_state_changed_detected"))
    target_conflict_detected = bool(binding.get("target_conflict_detected"))
    if stale_preview_detected and not any(
        [
            candidate_binding_valid,
            planning_gate_binding_valid,
            backend_plan_binding_valid,
            transaction_plan_binding_valid,
            target_identity_binding_valid,
            target_state_snapshot_binding_valid,
            dry_run_evidence_binding_valid,
            idempotency_preview_binding_valid,
            authorization_scope_binding_valid,
        ]
    ):
        blockers.append("authorization_preview_current_identity_mismatch")

    candidate_changed = not candidate_binding_valid
    backend_changed = not backend_plan_binding_valid
    transaction_changed = not transaction_plan_binding_valid

    if candidate_changed:
        blockers.append("candidate_binding_mismatch")
    if not planning_gate_binding_valid:
        blockers.append("planning_gate_binding_mismatch")
    if backend_changed:
        blockers.append("backend_plan_binding_mismatch")
    if transaction_changed:
        blockers.append("transaction_plan_binding_mismatch")
    if not target_identity_binding_valid:
        blockers.append("target_identity_binding_mismatch")
    if not target_state_snapshot_binding_valid:
        blockers.append("target_state_snapshot_binding_mismatch")
    if target_conflict_detected:
        blockers.append("transaction_target_conflict")
    if stale_target_detected or target_state_changed_detected:
        blockers.append("transaction_target_state_stale")
    if not target_state_observation_available or target_state_freshness_status == "unknown":
        blockers.append("target_state_unknown")

    blockers = _dedupe(blockers)
    warnings = _dedupe(warnings)
    authorization_preview_binding_valid = bool(
        authorization_preview_integrity_valid
        and authorization_preview_current_binding_valid
        and candidate_binding_valid
        and planning_gate_binding_valid
        and backend_plan_binding_valid
        and transaction_plan_binding_valid
        and target_identity_binding_valid
        and target_state_snapshot_binding_valid
        and dry_run_evidence_binding_valid
        and idempotency_preview_binding_valid
        and authorization_scope_binding_valid
        and confirmation_contract_binding_valid
        and confirmation_dry_run_integrity_valid
        and confirmation_dry_run_current_binding_valid
        and confirmation_evidence_binding_valid
        and target_state_observation_available
        and target_state_freshness_proven
        and not stale_target_detected
        and not target_state_changed_detected
        and not target_conflict_detected
    )

    if candidate_changed:
        status = "stale_candidate"
        recommended_action = "Rebuild the authorization preview from the current candidate record set before treating confirmation evidence as current."
    elif backend_changed:
        status = "modified_backend_plan"
        recommended_action = "Rebuild the authorization preview from the current backend plan before treating confirmation evidence as current."
    elif transaction_changed:
        status = "modified_transaction_plan"
        recommended_action = "Rebuild the authorization preview from the current transaction plan before treating confirmation evidence as current."
    elif modified_preview_detected:
        status = "modified_preview"
        recommended_action = "The supplied authorization preview failed integrity validation. Rebuild it and rerun the confirmation dry run without repairing inputs in place."
    elif confirmation_dry_run_modified_detected:
        status = "modified_confirmation_evidence"
        recommended_action = "The supplied confirmation dry-run result failed integrity validation. Rebuild it from the current preview and confirmation text."
    elif target_conflict_detected:
        status = "target_conflict"
        recommended_action = "A target conflict blocks preview/evidence binding even when confirmation text matches exactly."
    elif stale_target_detected or target_state_changed_detected:
        status = "stale_target"
        recommended_action = "The current target state no longer matches the bound snapshot. Rebuild the preview and confirmation evidence."
    elif stale_preview_detected or not dry_run_evidence_binding_valid or not idempotency_preview_binding_valid or authorization_scope_modified_detected:
        status = "stale_preview"
        recommended_action = "The supplied authorization preview remains internally intact but no longer matches current prerequisites. Rebuild it before using confirmation evidence."
    elif not target_state_observation_available or target_state_freshness_status == "unknown":
        status = "target_state_unknown"
        recommended_action = "Unknown target-state freshness blocks preview/evidence binding until a safe current observation is available."
    elif str(expected_preview.get("status") or "") == "dry_run_failed" or str(expected_confirmation.get("status") or "") == "dry_run_failed":
        status = "dry_run_failed"
        recommended_action = "A passing read-only Phase 14 dry run remains required before preview/evidence binding can be treated as current."
    elif not confirmation_supplied:
        status = "confirmation_missing"
        recommended_action = "Provide the exact future confirmation phrase in a dry run only after the current preview/evidence binding remains valid."
    elif not confirmation_exact_match:
        status = "confirmation_mismatch"
        recommended_action = "The supplied confirmation text did not exactly match the frozen literal. No authorization was created or granted."
    elif confirmation_dry_run_stale_detected or not confirmation_evidence_binding_valid:
        status = "stale_confirmation_evidence"
        recommended_action = "The supplied confirmation dry-run result is stale against current preview evidence. Rebuild it before using confirmation evidence."
    elif authorization_preview_binding_valid:
        status = "confirmation_match"
        recommended_action = "Current preview/evidence binding and exact confirmation match were validated in a dry run only. No authorization was created or granted."
    else:
        status = "blocked"
        recommended_action = "Resolve preview integrity, stale prerequisite, or confirmation-evidence blockers before treating this as current binding evidence."

    return {
        **base_payload,
        "status": status,
        "authorization_preview_binding_valid": authorization_preview_binding_valid,
        "authorization_preview_integrity_valid": authorization_preview_integrity_valid,
        "authorization_preview_fingerprint_valid": authorization_preview_fingerprint_valid,
        "authorization_preview_current_binding_valid": authorization_preview_current_binding_valid,
        "modified_preview_detected": modified_preview_detected,
        "stale_preview_detected": stale_preview_detected,
        "candidate_binding_valid": candidate_binding_valid,
        "planning_gate_binding_valid": planning_gate_binding_valid,
        "backend_plan_binding_valid": backend_plan_binding_valid,
        "transaction_plan_binding_valid": transaction_plan_binding_valid,
        "target_identity_binding_valid": target_identity_binding_valid,
        "target_state_snapshot_binding_valid": target_state_snapshot_binding_valid,
        "target_state_observation_available": target_state_observation_available,
        "target_state_freshness_status": target_state_freshness_status,
        "target_state_freshness_proven": target_state_freshness_proven,
        "stale_target_detected": stale_target_detected,
        "target_state_changed_detected": target_state_changed_detected,
        "target_conflict_detected": target_conflict_detected,
        "dry_run_evidence_binding_valid": dry_run_evidence_binding_valid,
        "idempotency_preview_binding_valid": idempotency_preview_binding_valid,
        "authorization_scope_binding_valid": authorization_scope_binding_valid,
        "authorization_scope_modified_detected": authorization_scope_modified_detected,
        "confirmation_contract_binding_valid": confirmation_contract_binding_valid,
        "confirmation_policy_modified_detected": confirmation_policy_modified_detected,
        "confirmation_dry_run_integrity_valid": confirmation_dry_run_integrity_valid,
        "confirmation_dry_run_current_binding_valid": confirmation_dry_run_current_binding_valid,
        "confirmation_dry_run_modified_detected": confirmation_dry_run_modified_detected,
        "confirmation_dry_run_stale_detected": confirmation_dry_run_stale_detected,
        "confirmation_supplied": confirmation_supplied,
        "confirmation_exact_match": confirmation_exact_match,
        "confirmation_evidence_binding_valid": confirmation_evidence_binding_valid,
        "confirmation_evidence_fingerprint_valid": confirmation_evidence_fingerprint_valid,
        "stored_authorization_preview_fingerprint": stored_authorization_preview_fingerprint,
        "expected_authorization_preview_fingerprint": expected_authorization_preview_fingerprint,
        "stored_dry_run_evidence_fingerprint": stored_dry_run_evidence_fingerprint,
        "expected_dry_run_evidence_fingerprint": expected_dry_run_evidence_fingerprint,
        "stored_confirmation_evidence_fingerprint": stored_confirmation_evidence_fingerprint,
        "expected_confirmation_evidence_fingerprint": expected_confirmation_evidence_fingerprint,
        "planned_write_count": _integer_or_none(expected_preview.get("planned_write_count")) or 1,
        "blockers": blockers,
        "warnings": warnings,
        "recommended_action": recommended_action,
    }


def format_deployed_rule_outcome_truth_record_set_controlled_registration_authorization_preview_confirmation_evidence_binding_report(
    authorization_artifact_preview: Mapping[str, Any],
    confirmation_dry_run_result: Mapping[str, Any],
    confirmation_text: str,
    transaction_plan: Mapping[str, Any],
    backend_plan: Mapping[str, Any],
    candidate_record_set: Any,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    binding = validate_deployed_rule_outcome_truth_record_set_controlled_registration_authorization_preview_confirmation_evidence_binding(
        authorization_artifact_preview,
        confirmation_dry_run_result,
        confirmation_text,
        transaction_plan,
        backend_plan,
        candidate_record_set,
        root=root,
    )
    lines = [
        "Controlled registration authorization-preview / confirmation-evidence binding",
        f"Status: {binding.get('status')}",
        f"Preview integrity valid: {str(bool(binding.get('authorization_preview_integrity_valid'))).lower()}",
        f"Preview current binding valid: {str(bool(binding.get('authorization_preview_current_binding_valid'))).lower()}",
        f"Modified preview detected: {str(bool(binding.get('modified_preview_detected'))).lower()}",
        f"Stale preview detected: {str(bool(binding.get('stale_preview_detected'))).lower()}",
        f"Target-state freshness status: {binding.get('target_state_freshness_status')}",
        f"Target-state freshness proven: {str(bool(binding.get('target_state_freshness_proven'))).lower()}",
        f"Dry-run evidence binding valid: {str(bool(binding.get('dry_run_evidence_binding_valid'))).lower()}",
        f"Idempotency preview binding valid: {str(bool(binding.get('idempotency_preview_binding_valid'))).lower()}",
        f"Authorization-scope binding valid: {str(bool(binding.get('authorization_scope_binding_valid'))).lower()}",
        f"Confirmation contract binding valid: {str(bool(binding.get('confirmation_contract_binding_valid'))).lower()}",
        f"Confirmation dry-run integrity valid: {str(bool(binding.get('confirmation_dry_run_integrity_valid'))).lower()}",
        f"Confirmation dry-run current binding valid: {str(bool(binding.get('confirmation_dry_run_current_binding_valid'))).lower()}",
        f"Confirmation supplied: {str(bool(binding.get('confirmation_supplied'))).lower()}",
        f"Confirmation exact match: {str(bool(binding.get('confirmation_exact_match'))).lower()}",
        f"Stored authorization-preview fingerprint: {binding.get('stored_authorization_preview_fingerprint')}",
        f"Expected authorization-preview fingerprint: {binding.get('expected_authorization_preview_fingerprint')}",
        f"Stored confirmation-evidence fingerprint: {binding.get('stored_confirmation_evidence_fingerprint')}",
        f"Expected confirmation-evidence fingerprint: {binding.get('expected_confirmation_evidence_fingerprint')}",
        "Phase 15C treats supplied previews and confirmation dry-run results as untrusted.",
        "Modified previews fail integrity validation.",
        "Stale previews may remain internally intact but no longer match current prerequisites.",
        "Modified and stale previews are not repaired in place.",
        "Confirmation evidence is recomputed from current stable evidence and the supplied confirmation text's match outcome.",
        "An exact confirmation match cannot override a stale, modified, conflicting, unknown, or otherwise blocked prerequisite state.",
        "A valid authorization-preview binding does not create an authorization artifact.",
        "A valid authorization-preview binding does not grant execution authorization.",
        "A valid authorization-preview binding does not grant registration authorization.",
        "Confirmation remains unaccepted and unenforced.",
        "Idempotency remains unenforced.",
        "Phase 15C does not call the registration function.",
        "Phase 15C performs zero writes.",
        "A valid fingerprint proves integrity against the defined canonical representation only.",
        "It does not prove factual correctness of outcome-truth records.",
    ]
    blockers = binding.get("blockers", [])
    warnings = binding.get("warnings", [])
    if isinstance(blockers, list) and blockers:
        lines.append("Blockers: " + ", ".join(str(item) for item in blockers))
    if isinstance(warnings, list) and warnings:
        lines.append("Warnings: " + ", ".join(str(item) for item in warnings))
    if binding.get("recommended_action"):
        lines.append(f"Recommended action: {binding.get('recommended_action')}")
    limitations = binding.get("limitations", [])
    if isinstance(limitations, list) and limitations:
        lines.append("Limitations: " + "; ".join(str(item) for item in limitations))
    lines.append(f"Writes performed: {binding.get('writes_performed', 0)}")
    return "\n".join(lines)


def build_deployed_rule_outcome_truth_source_workspace(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result_id: str,
    effectiveness_spec_result_id: str,
    observation_window_start: str,
    observation_window_end: str,
    *,
    outcome_truth_source_id: str | None = None,
    outcome_truth_record_set_id: str | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    context = _source_context(
        canonical_rule_id=canonical_rule_id,
        production_deployment_result_id=production_deployment_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
        telemetry_snapshot_id=telemetry_snapshot_id,
        readiness_result_id=readiness_result_id,
        effectiveness_spec_result_id=effectiveness_spec_result_id,
        observation_window_start=observation_window_start,
        observation_window_end=observation_window_end,
        outcome_truth_source_id=outcome_truth_source_id,
        outcome_truth_record_set_id=outcome_truth_record_set_id,
        root=root,
    )
    return {
        "status": context["status"],
        "canonical_rule_id": canonical_rule_id,
        "production_deployment_result_id": production_deployment_result_id,
        "production_target_id": production_target_id,
        "deployed_rule_id": deployed_rule_id,
        "telemetry_snapshot_id": telemetry_snapshot_id,
        "readiness_result_id": readiness_result_id,
        "effectiveness_spec_result_id": effectiveness_spec_result_id,
        "observation_window_start": observation_window_start,
        "observation_window_end": observation_window_end,
        "execution_attempt_count": context["execution_attempt_count"],
        "candidate_outcome_truth_source_status": context["source_status"],
        "outcome_truth_record_set_id": context["outcome_truth_record_set_id"],
        "source_type": context["source_type"],
        "outcome_truth_binding_status": context["binding_status"],
        "authority_status": context["authority_status"],
        "record_count": context["record_count"],
        "valid_record_count": context["valid_record_count"],
        "incomplete_record_count": context["incomplete_record_count"],
        "unsupported_record_count": context["unsupported_record_count"],
        "outcome_truth_expected_value_status": context["expected_value_status"],
        "outcome_truth_actual_value_status": context["actual_value_status"],
        "warnings": list(context["warnings"]),
        "blockers": list(context["blockers"]),
        "recommended_action": _recommended_action(context["status"]),
    }


def validate_deployed_rule_outcome_truth_source_eligibility(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result_id: str,
    effectiveness_spec_result_id: str,
    observation_window_start: str,
    observation_window_end: str,
    *,
    outcome_truth_source_id: str | None = None,
    outcome_truth_record_set_id: str | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    context = _source_context(
        canonical_rule_id=canonical_rule_id,
        production_deployment_result_id=production_deployment_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
        telemetry_snapshot_id=telemetry_snapshot_id,
        readiness_result_id=readiness_result_id,
        effectiveness_spec_result_id=effectiveness_spec_result_id,
        observation_window_start=observation_window_start,
        observation_window_end=observation_window_end,
        outcome_truth_source_id=outcome_truth_source_id,
        outcome_truth_record_set_id=outcome_truth_record_set_id,
        root=root,
    )
    return {
        "status": context["status"],
        "criteria": deepcopy(context["criteria"]),
        "blockers": list(context["blockers"]),
        "warnings": list(context["warnings"]),
        "source_status": context["source_status"],
        "outcome_truth_record_set_id": context["outcome_truth_record_set_id"],
        "source_type": context["source_type"],
        "binding_status": context["binding_status"],
        "authority_status": context["authority_status"],
        "expected_value_availability": context["expected_value_status"],
        "actual_or_adjudicated_value_availability": context["actual_value_status"],
        "record_count": context["record_count"],
        "valid_record_count": context["valid_record_count"],
        "incomplete_record_count": context["incomplete_record_count"],
        "unsupported_record_count": context["unsupported_record_count"],
        "scoring_support_status": context["scoring_support_status"],
    }


def build_deployed_rule_outcome_truth_source_plan(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result_id: str,
    effectiveness_spec_result_id: str,
    observation_window_start: str,
    observation_window_end: str,
    *,
    outcome_truth_source_id: str | None = None,
    outcome_truth_record_set_id: str | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    context = _source_context(
        canonical_rule_id=canonical_rule_id,
        production_deployment_result_id=production_deployment_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
        telemetry_snapshot_id=telemetry_snapshot_id,
        readiness_result_id=readiness_result_id,
        effectiveness_spec_result_id=effectiveness_spec_result_id,
        observation_window_start=observation_window_start,
        observation_window_end=observation_window_end,
        outcome_truth_source_id=outcome_truth_source_id,
        outcome_truth_record_set_id=outcome_truth_record_set_id,
        root=base,
    )
    plan = _plan_payload(context)
    path = _plan_path(base, str(plan["outcome_truth_source_plan_id"]))
    existing = _read_json(path)
    if isinstance(existing, Mapping):
        if str(existing.get("plan_fingerprint") or "") == str(plan.get("plan_fingerprint") or ""):
            return {
                "status": "planned",
                "outcome_truth_source_plan_id": plan["outcome_truth_source_plan_id"],
                "writes_performed": 0,
                **_plan_summary(existing),
            }
        return {
            "status": "corrupt",
            "outcome_truth_source_plan_id": plan["outcome_truth_source_plan_id"],
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["outcome_truth_source_plan_divergence"],
        }
    before_plan = _read_json(path)
    before_index = _read_json(base / "indexes" / PLAN_INDEX)
    try:
        _atomic_write_json(path, plan)
        _update_plan_index(base)
    except Exception:
        _restore_json(path, before_plan)
        _restore_json(base / "indexes" / PLAN_INDEX, before_index)
        return {
            "status": "corrupt",
            "outcome_truth_source_plan_id": plan["outcome_truth_source_plan_id"],
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["outcome_truth_source_plan_write_failure"],
        }
    return {
        "status": "planned",
        "outcome_truth_source_plan_id": plan["outcome_truth_source_plan_id"],
        "writes_performed": 1,
        **_plan_summary(plan),
    }


def record_deployed_rule_outcome_truth_source_result(
    outcome_truth_source_plan_id: str,
    confirmation: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    if confirmation != REQUIRED_CONFIRMATION:
        return {
            "status": "blocked",
            "outcome_truth_source_plan_id": outcome_truth_source_plan_id,
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["outcome_truth_source_confirmation_required"],
        }
    plan = _read_json(_plan_path(base, outcome_truth_source_plan_id))
    if not isinstance(plan, Mapping):
        return {
            "status": "blocked",
            "outcome_truth_source_plan_id": outcome_truth_source_plan_id,
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["outcome_truth_source_plan_missing"],
        }
    context = _source_context(
        canonical_rule_id=str(plan.get("canonical_rule_id") or ""),
        production_deployment_result_id=str(plan.get("production_deployment_result_id") or ""),
        production_target_id=str(plan.get("production_target_id") or ""),
        deployed_rule_id=str(plan.get("deployed_rule_id") or ""),
        telemetry_snapshot_id=str(plan.get("telemetry_snapshot_id") or ""),
        readiness_result_id=str(plan.get("readiness_result_id") or ""),
        effectiveness_spec_result_id=str(plan.get("effectiveness_spec_result_id") or ""),
        observation_window_start=str(plan.get("observation_window_start") or ""),
        observation_window_end=str(plan.get("observation_window_end") or ""),
        outcome_truth_source_id=_text(plan.get("outcome_truth_source_id")),
        outcome_truth_record_set_id=_text(plan.get("outcome_truth_record_set_id")),
        root=base,
    )
    current_plan = _plan_payload(context)
    if str(current_plan.get("plan_fingerprint") or "") != str(plan.get("plan_fingerprint") or ""):
        return {
            "status": "outcome_truth_source_stale",
            "outcome_truth_source_plan_id": outcome_truth_source_plan_id,
            "writes_performed": 0,
            "warnings": list(context["warnings"]),
            "blockers": ["outcome_truth_source_plan_stale"],
        }
    result_id = _result_id(outcome_truth_source_plan_id)
    receipt_id = _receipt_id(result_id)
    result = {
        "schema_version": RESULT_SCHEMA,
        "outcome_truth_source_schema_version": SOURCE_SCHEMA_VERSION,
        "outcome_truth_source_result_id": result_id,
        "outcome_truth_source_plan_id": outcome_truth_source_plan_id,
        "outcome_truth_source_receipt_id": receipt_id,
        **{
            key: current_plan.get(key)
            for key in (
                "canonical_rule_id",
                "production_deployment_result_id",
                "production_target_id",
                "deployed_rule_id",
                "telemetry_snapshot_id",
                "readiness_result_id",
                "effectiveness_spec_result_id",
                "observation_window_start",
                "observation_window_end",
                "outcome_truth_source_id",
                "outcome_truth_record_set_id",
                "source_status",
                "binding_status",
                "authority_status",
                "criteria",
                "warnings",
                "blockers",
                "scoring_support_status",
                "readiness_result_fingerprint",
                "effectiveness_spec_result_fingerprint",
                "telemetry_snapshot_fingerprint",
                "plan_fingerprint",
            )
        },
        "recorded_at_utc": _now(),
    }
    result["result_fingerprint"] = _hash_payload(
        {key: result.get(key) for key in sorted(result) if key not in {"result_fingerprint", "recorded_at_utc"}}
    )
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "outcome_truth_source_schema_version": SOURCE_SCHEMA_VERSION,
        "outcome_truth_source_receipt_id": receipt_id,
        "outcome_truth_source_result_id": result_id,
        "outcome_truth_source_plan_id": outcome_truth_source_plan_id,
        "source_status": context["status"],
        "result_fingerprint": result["result_fingerprint"],
        "recorded_at_utc": result["recorded_at_utc"],
    }
    existing = _read_json(_result_path(base, result_id))
    if isinstance(existing, Mapping):
        if str(existing.get("result_fingerprint") or "") == str(result.get("result_fingerprint") or ""):
            return {
                "status": "already_recorded",
                "outcome_truth_source_result_id": result_id,
                "writes_performed": 0,
                **_result_summary(existing),
            }
        return {
            "status": "conflict",
            "outcome_truth_source_result_id": result_id,
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["outcome_truth_source_result_conflict"],
        }
    before_result = _read_json(_result_path(base, result_id))
    before_receipt = _read_json(_receipt_path(base, receipt_id))
    before_result_index = _read_json(base / "indexes" / RESULT_INDEX)
    before_receipt_index = _read_json(base / "indexes" / RECEIPT_INDEX)
    try:
        _atomic_write_json(_result_path(base, result_id), result)
        _atomic_write_json(_receipt_path(base, receipt_id), receipt)
        _update_result_index(base)
        _update_receipt_index(base)
    except Exception:
        _restore_json(_result_path(base, result_id), before_result)
        _restore_json(_receipt_path(base, receipt_id), before_receipt)
        _restore_json(base / "indexes" / RESULT_INDEX, before_result_index)
        _restore_json(base / "indexes" / RECEIPT_INDEX, before_receipt_index)
        return {
            "status": "outcome_truth_source_corrupt",
            "outcome_truth_source_result_id": result_id,
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["outcome_truth_source_result_write_failure"],
        }
    return {
        "status": context["status"],
        "outcome_truth_source_result_id": result_id,
        "writes_performed": 1,
        **_result_summary(result),
    }


def load_deployed_rule_outcome_truth_source_result(
    outcome_truth_source_result_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = Path(root)
    payload = _read_json(_result_path(base, outcome_truth_source_result_id))
    if not isinstance(payload, Mapping):
        return {
            "status": "blocked",
            "outcome_truth_source_result_id": outcome_truth_source_result_id,
            "warnings": [],
            "blockers": ["outcome_truth_source_result_missing"],
        }
    receipt = _read_json(_receipt_path(base, str(payload.get("outcome_truth_source_receipt_id") or "")))
    if not isinstance(receipt, Mapping):
        return {
            "status": "outcome_truth_source_corrupt",
            "outcome_truth_source_result_id": outcome_truth_source_result_id,
            "warnings": [],
            "blockers": ["outcome_truth_source_receipt_missing"],
        }
    return {
        "status": str(payload.get("source_status") or "outcome_truth_source_corrupt"),
        "outcome_truth_source_result": dict(payload),
        "outcome_truth_source_receipt": dict(receipt),
        "warnings": [],
        "blockers": [],
    }


def get_deployed_rule_outcome_truth_source_health(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = Path(root)
    plan_items = _load_all(base / PLAN_DIR)
    result_items = _load_all(base / RESULT_DIR)
    receipt_items = _load_all(base / RECEIPT_DIR)
    warnings: list[str] = []
    blockers: list[str] = []
    result_ids = {str(item.get("outcome_truth_source_result_id") or "") for item in result_items}
    for receipt in receipt_items:
        if str(receipt.get("outcome_truth_source_result_id") or "") not in result_ids:
            blockers.append("outcome_truth_source_receipt_references_missing_result")
    indexed_plan_ids = {str(item.get("outcome_truth_source_plan_id") or "") for item in _index_items(base / "indexes" / PLAN_INDEX)}
    for plan in plan_items:
        if str(plan.get("outcome_truth_source_plan_id") or "") not in indexed_plan_ids:
            warnings.append("outcome_truth_source_plan_missing_from_index")
    status = "healthy" if not blockers and not warnings else "warning" if warnings and not blockers else "blocked"
    return {
        "status": status,
        "plan_count": len(plan_items),
        "result_count": len(result_items),
        "receipt_count": len(receipt_items),
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
    }


def format_deployed_rule_outcome_truth_source_report(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result_id: str,
    effectiveness_spec_result_id: str,
    observation_window_start: str,
    observation_window_end: str,
    *,
    outcome_truth_source_id: str | None = None,
    outcome_truth_record_set_id: str | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    eligibility = validate_deployed_rule_outcome_truth_source_eligibility(
        canonical_rule_id,
        production_deployment_result_id,
        production_target_id,
        deployed_rule_id,
        telemetry_snapshot_id,
        readiness_result_id,
        effectiveness_spec_result_id,
        observation_window_start,
        observation_window_end,
        outcome_truth_source_id=outcome_truth_source_id,
        outcome_truth_record_set_id=outcome_truth_record_set_id,
        root=root,
    )
    lines = [
        "Deployed Rule Outcome-Truth Source",
        f"Canonical rule ID: {canonical_rule_id}",
        f"Deployed rule ID: {deployed_rule_id}",
        f"Production deployment result ID: {production_deployment_result_id}",
        f"Telemetry snapshot ID: {telemetry_snapshot_id}",
        f"Outcome-truth source status: {eligibility.get('status')}",
        "This is outcome-truth source validation only; no effectiveness score was calculated.",
        "Outcome-truth source availability does not mean effectiveness has been evaluated.",
        "Execution completion is not correctness.",
        "Phase 9W acceptance is not outcome truth.",
        "Absence of failures is not success.",
        f"Record-set ID: {eligibility.get('outcome_truth_record_set_id')}",
        f"Source type: {eligibility.get('source_type')}",
        f"Binding status: {eligibility.get('binding_status')}",
        f"Authority status: {eligibility.get('authority_status')}",
        f"Record count: {eligibility.get('record_count')}",
        f"Valid record count: {eligibility.get('valid_record_count')}",
        f"Incomplete record count: {eligibility.get('incomplete_record_count')}",
        f"Unsupported record count: {eligibility.get('unsupported_record_count')}",
        f"Scoring support status: {eligibility.get('scoring_support_status')}",
    ]
    blockers = list(eligibility.get("blockers", []))
    warnings = list(eligibility.get("warnings", []))
    if blockers:
        lines.append("Blockers: " + ", ".join(blockers))
    if warnings:
        lines.append("Warnings: " + ", ".join(warnings))
    lines.append("Recommended next step: " + _recommended_action(str(eligibility.get("status") or "blocked")))
    return "\n".join(lines)


def _source_context(
    *,
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result_id: str,
    effectiveness_spec_result_id: str,
    observation_window_start: str,
    observation_window_end: str,
    outcome_truth_source_id: str | None,
    outcome_truth_record_set_id: str | None,
    root: Path | str,
) -> dict[str, Any]:
    base = Path(root)
    readiness_result_path = readiness_backend._result_path(base, readiness_result_id)
    spec_result_path = spec_backend._result_path(base, effectiveness_spec_result_id)
    snapshot_path = telemetry_backend._snapshot_path(base, telemetry_snapshot_id)
    if not (
        readiness_result_path.exists()
        and spec_result_path.exists()
        and snapshot_path.exists()
    ):
        criteria = {
            "effectiveness_spec_result_exists": spec_result_path.exists(),
            "effectiveness_spec_result_fingerprint_verified": False,
            "readiness_result_exists": readiness_result_path.exists(),
            "readiness_result_ready_or_scoring_blocked_only_by_outcome_truth": False,
            "telemetry_snapshot_exists": snapshot_path.exists(),
            "execution_attempts_present": False,
            "candidate_outcome_truth_source_found": False,
            "record_set_exists": False,
            "record_set_matches_source": False,
            "record_set_binds_to_execution_attempts": False,
            "expected_values_available": False,
            "actual_or_adjudicated_values_available": False,
            "phase9w_not_outcome_truth": True,
            "runtime_completion_not_correctness": True,
            "source_availability_not_effectiveness": True,
            "effectiveness_not_evaluated": True,
        }
        blockers: list[str] = []
        if not criteria["readiness_result_exists"]:
            blockers.append("effectiveness_readiness_result_missing")
        if not criteria["effectiveness_spec_result_exists"]:
            blockers.append("effectiveness_evaluation_spec_result_missing")
        if not criteria["telemetry_snapshot_exists"]:
            blockers.append("telemetry_snapshot_missing")
        return {
            "status": "blocked",
            "canonical_rule_id": canonical_rule_id,
            "production_deployment_result_id": production_deployment_result_id,
            "production_target_id": production_target_id,
            "deployed_rule_id": deployed_rule_id,
            "telemetry_snapshot_id": telemetry_snapshot_id,
            "readiness_result_id": readiness_result_id,
            "effectiveness_spec_result_id": effectiveness_spec_result_id,
            "observation_window_start": observation_window_start,
            "observation_window_end": observation_window_end,
            "criteria": criteria,
            "blockers": blockers,
            "warnings": [],
            "source_status": "outcome_truth_source_unavailable",
            "outcome_truth_record_set_id": outcome_truth_record_set_id,
            "source_type": "unknown",
            "binding_status": "blocked",
            "authority_status": "unknown",
            "expected_value_status": "blocked",
            "actual_value_status": "blocked",
            "record_count": 0,
            "valid_record_count": 0,
            "incomplete_record_count": 0,
            "unsupported_record_count": 0,
            "execution_attempt_count": 0,
            "scoring_support_status": "blocked_missing_outcome_truth",
        }
    manifest = get_deployed_rule_outcome_truth_source_manifest(root=base)
    readiness_loaded = readiness_backend.load_deployed_rule_effectiveness_readiness_result(readiness_result_id, root=base)
    readiness_result = readiness_loaded.get("effectiveness_readiness_result") if isinstance(readiness_loaded.get("effectiveness_readiness_result"), Mapping) else None
    spec_loaded = spec_backend.load_deployed_rule_effectiveness_evaluation_spec_result(effectiveness_spec_result_id, root=base)
    spec_result = spec_loaded.get("effectiveness_evaluation_spec_result") if isinstance(spec_loaded.get("effectiveness_evaluation_spec_result"), Mapping) else None
    telemetry_snapshot = _read_json(telemetry_backend._snapshot_path(base, telemetry_snapshot_id))
    candidate = _discover_candidate_outcome_truth_source(
        base=base,
        canonical_rule_id=canonical_rule_id,
        production_deployment_result_id=production_deployment_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
        telemetry_snapshot_id=telemetry_snapshot_id,
        readiness_result=readiness_result,
        effectiveness_spec_result=spec_result,
        observation_window_start=observation_window_start,
        observation_window_end=observation_window_end,
        outcome_truth_source_id=outcome_truth_source_id,
        outcome_truth_record_set_id=outcome_truth_record_set_id,
    )
    blockers: list[str] = []
    warnings: list[str] = []
    criteria = {
        "effectiveness_spec_result_exists": False,
        "effectiveness_spec_result_fingerprint_verified": False,
        "readiness_result_exists": False,
        "readiness_result_ready_or_scoring_blocked_only_by_outcome_truth": False,
        "telemetry_snapshot_exists": False,
        "execution_attempts_present": False,
        "candidate_outcome_truth_source_found": False,
        "outcome_truth_source_authoritative": False,
        "outcome_truth_binds_to_execution_attempts": False,
        "outcome_truth_has_expected_value": False,
        "outcome_truth_has_actual_or_adjudicated_value": False,
        "outcome_truth_has_observation_window": False,
        "outcome_truth_has_source_fingerprint": False,
        "outcome_truth_no_phase9w_substitution": True,
        "no_effectiveness_score_calculated": True,
    }

    if isinstance(spec_result, Mapping):
        criteria["effectiveness_spec_result_exists"] = True
        if spec_backend._hash_payload({key: spec_result.get(key) for key in sorted(spec_result) if key not in {"result_fingerprint", "recorded_at_utc"}}) == str(spec_result.get("result_fingerprint") or ""):
            criteria["effectiveness_spec_result_fingerprint_verified"] = True
        else:
            blockers.append("effectiveness_spec_result_fingerprint_invalid")
        if (
            str(spec_result.get("canonical_rule_id") or "") != canonical_rule_id
            or str(spec_result.get("production_deployment_result_id") or "") != production_deployment_result_id
            or str(spec_result.get("production_target_id") or "") != production_target_id
            or str(spec_result.get("deployed_rule_id") or "") != deployed_rule_id
            or str(spec_result.get("telemetry_snapshot_id") or "") != telemetry_snapshot_id
            or str(spec_result.get("readiness_result_id") or "") != readiness_result_id
        ):
            blockers.append("effectiveness_spec_result_identity_mismatch")
        if str(spec_result.get("spec_status") or "") == "spec_ready_scoring_blocked_missing_outcome_truth":
            criteria["readiness_result_ready_or_scoring_blocked_only_by_outcome_truth"] = True
    else:
        blockers.append("effectiveness_spec_result_missing")

    if isinstance(readiness_result, Mapping):
        criteria["readiness_result_exists"] = True
        if str(readiness_result.get("readiness_status") or "") == "ready_for_effectiveness_evaluation":
            criteria["readiness_result_ready_or_scoring_blocked_only_by_outcome_truth"] = True
    else:
        blockers.append("readiness_result_missing")

    if isinstance(telemetry_snapshot, Mapping):
        criteria["telemetry_snapshot_exists"] = True
        if int(telemetry_snapshot.get("execution_event_count") or 0) > 0:
            criteria["execution_attempts_present"] = True
        if str(telemetry_snapshot.get("deployed_rule_id") or "") != deployed_rule_id or str(telemetry_snapshot.get("production_deployment_result_id") or "") != production_deployment_result_id:
            blockers.append("telemetry_snapshot_identity_mismatch")
    else:
        blockers.append("telemetry_snapshot_missing")

    if candidate is None:
        source_status = "outcome_truth_source_unavailable"
        binding_status = "no_source_found"
        authority_status = "not_available"
        expected_value_status = "missing"
        actual_value_status = "missing"
        source_type = None
        outcome_truth_record_set_id = None
        record_count = 0
        valid_record_count = 0
        incomplete_record_count = 0
        unsupported_record_count = 0
        blockers.append("outcome_truth_source_unavailable")
    else:
        source_status, binding_status, authority_status, expected_value_status, actual_value_status, candidate_blockers = _evaluate_candidate_source(candidate)
        blockers.extend(candidate_blockers)
        criteria["candidate_outcome_truth_source_found"] = True
        criteria["outcome_truth_source_authoritative"] = authority_status == "authoritative"
        criteria["outcome_truth_binds_to_execution_attempts"] = binding_status == "binds_to_execution_attempts"
        criteria["outcome_truth_has_expected_value"] = expected_value_status == "available"
        criteria["outcome_truth_has_actual_or_adjudicated_value"] = actual_value_status == "available"
        criteria["outcome_truth_has_observation_window"] = bool(_text(candidate.get("observation_window_start")) and _text(candidate.get("observation_window_end")))
        criteria["outcome_truth_has_source_fingerprint"] = bool(_text(candidate.get("source_fingerprint")))
        source_type = _text(candidate.get("source_type"))
        outcome_truth_record_set_id = _text(candidate.get("record_set_id"))
        record_count = int(candidate.get("record_count") or 0)
        valid_record_count = int(candidate.get("valid_record_count") or 0)
        incomplete_record_count = int(candidate.get("incomplete_record_count") or 0)
        unsupported_record_count = int(candidate.get("unsupported_record_count") or 0)

    if not criteria["effectiveness_spec_result_exists"] or not criteria["readiness_result_exists"] or not criteria["telemetry_snapshot_exists"]:
        status = "blocked"
    elif "effectiveness_spec_result_fingerprint_invalid" in blockers:
        status = "outcome_truth_source_corrupt"
    elif any(item.endswith("_identity_mismatch") for item in blockers):
        status = "outcome_truth_source_stale"
    else:
        status = source_status

    scoring_support_status = "blocked_missing_outcome_truth" if status in {
        "outcome_truth_source_unavailable",
        "outcome_truth_source_incomplete",
        "outcome_truth_source_unsupported",
    } else "blocked" if status in {"blocked", "outcome_truth_source_stale", "outcome_truth_source_corrupt"} else "source_available_no_scoring_engine"
    return {
        "base": base,
        "status": status,
        "manifest": manifest,
        "canonical_rule_id": canonical_rule_id,
        "production_deployment_result_id": production_deployment_result_id,
        "production_target_id": production_target_id,
        "deployed_rule_id": deployed_rule_id,
        "telemetry_snapshot_id": telemetry_snapshot_id,
        "readiness_result_id": readiness_result_id,
        "effectiveness_spec_result_id": effectiveness_spec_result_id,
        "observation_window_start": observation_window_start,
        "observation_window_end": observation_window_end,
        "outcome_truth_source_id": _text(outcome_truth_source_id),
        "outcome_truth_record_set_id": _text(outcome_truth_record_set_id),
        "readiness_result_fingerprint": str((readiness_result or {}).get("result_fingerprint") or ""),
        "effectiveness_spec_result_fingerprint": str((spec_result or {}).get("result_fingerprint") or ""),
        "telemetry_snapshot_fingerprint": str((telemetry_snapshot or {}).get("snapshot_fingerprint") or "") if isinstance(telemetry_snapshot, Mapping) else "",
        "execution_attempt_count": int((readiness_result or {}).get("valid_execution_attempt_count") or 0) if isinstance(readiness_result, Mapping) else 0,
        "source_status": source_status,
        "outcome_truth_record_set_id": outcome_truth_record_set_id,
        "source_type": source_type,
        "binding_status": binding_status,
        "authority_status": authority_status,
        "record_count": record_count,
        "valid_record_count": valid_record_count,
        "incomplete_record_count": incomplete_record_count,
        "unsupported_record_count": unsupported_record_count,
        "expected_value_status": expected_value_status,
        "actual_value_status": actual_value_status,
        "criteria": criteria,
        "blockers": _dedupe(blockers),
        "warnings": _dedupe(warnings),
        "scoring_support_status": scoring_support_status,
    }


def _discover_candidate_outcome_truth_source(
    *,
    base: Path,
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result: Mapping[str, Any] | None,
    effectiveness_spec_result: Mapping[str, Any] | None,
    observation_window_start: str,
    observation_window_end: str,
    outcome_truth_source_id: str | None,
    outcome_truth_record_set_id: str | None,
) -> Mapping[str, Any] | None:
    if outcome_truth_record_set_id:
        loaded = load_deployed_rule_outcome_truth_record_set(str(outcome_truth_record_set_id), root=base)
        if str(loaded.get("status") or "") != "loaded":
            return None
        record_set = loaded["outcome_truth_record_set"]
        records = loaded["outcome_truth_records"]
        if outcome_truth_source_id and str(record_set.get("source_id") or "") != outcome_truth_source_id:
            return {
                "source_type": "record_set_identity_mismatch",
                "authority_class": "unsupported",
            }
        return _candidate_from_registered_set(
            record_set=record_set,
            records=records,
            canonical_rule_id=canonical_rule_id,
            production_deployment_result_id=production_deployment_result_id,
            production_target_id=production_target_id,
            deployed_rule_id=deployed_rule_id,
            telemetry_snapshot_id=telemetry_snapshot_id,
            observation_window_start=observation_window_start,
            observation_window_end=observation_window_end,
        )
    listing = list_deployed_rule_outcome_truth_record_sets(
        canonical_rule_id,
        production_deployment_result_id,
        production_target_id,
        deployed_rule_id,
        telemetry_snapshot_id,
        root=base,
    )
    items = list(listing.get("items", []))
    if outcome_truth_source_id:
        items = [item for item in items if str(item.get("source_id") or "") == outcome_truth_source_id]
    if len(items) != 1:
        return None
    loaded = load_deployed_rule_outcome_truth_record_set(str(items[0].get("outcome_truth_record_set_id") or ""), root=base)
    if str(loaded.get("status") or "") != "loaded":
        return None
    return _candidate_from_registered_set(
        record_set=loaded["outcome_truth_record_set"],
        records=loaded["outcome_truth_records"],
        canonical_rule_id=canonical_rule_id,
        production_deployment_result_id=production_deployment_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
        telemetry_snapshot_id=telemetry_snapshot_id,
        observation_window_start=observation_window_start,
        observation_window_end=observation_window_end,
    )


def _candidate_from_registered_set(
    *,
    record_set: Mapping[str, Any],
    records: list[Mapping[str, Any]],
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    observation_window_start: str,
    observation_window_end: str,
) -> dict[str, Any]:
    first = dict(records[0]) if records else {}
    valid_records = [item for item in records if str(item.get("truth_status") or "") == "valid"]
    return {
        "source_type": record_set.get("source_type"),
        "authority_class": record_set.get("source_authority_class"),
        "source_fingerprint": record_set.get("source_fingerprint"),
        "execution_attempt_id": first.get("execution_event_id"),
        "input_fingerprint": first.get("input_fingerprint"),
        "expected_value": first.get("expected_outcome"),
        "actual_value": first.get("actual_or_adjudicated_outcome"),
        "observation_window_start": record_set.get("observation_window_start"),
        "observation_window_end": record_set.get("observation_window_end"),
        "record_set_id": record_set.get("outcome_truth_record_set_id"),
        "record_count": len(records),
        "valid_record_count": len(valid_records),
        "incomplete_record_count": len([item for item in records if str(item.get("truth_status") or "") == "incomplete"]),
        "unsupported_record_count": len([item for item in records if str(item.get("truth_status") or "") == "unsupported"]),
        "canonical_rule_id": record_set.get("canonical_rule_id"),
        "production_deployment_result_id": record_set.get("production_deployment_result_id"),
        "production_target_id": record_set.get("production_target_id"),
        "deployed_rule_id": record_set.get("deployed_rule_id"),
        "telemetry_snapshot_id": record_set.get("telemetry_snapshot_id"),
        "binding_consistent": (
            str(record_set.get("canonical_rule_id") or "") == canonical_rule_id
            and str(record_set.get("production_deployment_result_id") or "") == production_deployment_result_id
            and str(record_set.get("production_target_id") or "") == production_target_id
            and str(record_set.get("deployed_rule_id") or "") == deployed_rule_id
            and str(record_set.get("telemetry_snapshot_id") or "") == telemetry_snapshot_id
            and str(record_set.get("observation_window_start") or "") == observation_window_start
            and str(record_set.get("observation_window_end") or "") == observation_window_end
        ),
    }


def _evaluate_candidate_source(candidate: Mapping[str, Any]) -> tuple[str, str, str, str, str, list[str]]:
    blockers: list[str] = []
    source_type = str(candidate.get("source_type") or "")
    if source_type not in ALLOWED_SOURCE_TYPES:
        return (
            "outcome_truth_source_unsupported",
            "unsupported_source_semantics",
            "unsupported",
            "missing",
            "missing",
            ["outcome_truth_source_semantics_unsupported"],
        )
    authority_class = str(candidate.get("authority_class") or "")
    if authority_class == "phase9w_acceptance":
        return (
            "outcome_truth_source_unsupported",
            "phase9w_substitution_rejected",
            "unsupported",
            "missing",
            "missing",
            ["phase9w_acceptance_not_outcome_truth"],
        )
    if authority_class == "runtime_completion":
        return (
            "outcome_truth_source_unsupported",
            "runtime_completion_substitution_rejected",
            "unsupported",
            "missing",
            "missing",
            ["runtime_completion_not_outcome_truth"],
        )
    authoritative = authority_class in {"authoritative", "adjudicated", "verified"}
    if not authoritative:
        blockers.append("outcome_truth_source_not_authoritative")
    if candidate.get("binding_consistent") is False:
        blockers.append("outcome_truth_registered_set_identity_mismatch")
    has_binding = bool(_text(candidate.get("execution_attempt_id")) or _text(candidate.get("input_fingerprint")))
    has_expected = candidate.get("expected_value") is not None
    has_actual = candidate.get("actual_value") is not None or candidate.get("adjudicated_value") is not None
    has_window = bool(_text(candidate.get("observation_window_start")) and _text(candidate.get("observation_window_end")))
    has_fingerprint = bool(_text(candidate.get("source_fingerprint")))
    if not has_binding:
        blockers.append("outcome_truth_binding_missing")
    if not has_expected:
        blockers.append("outcome_truth_expected_value_missing")
    if not has_actual:
        blockers.append("outcome_truth_actual_or_adjudicated_value_missing")
    if not has_window:
        blockers.append("outcome_truth_observation_window_missing")
    if not has_fingerprint:
        blockers.append("outcome_truth_source_fingerprint_missing")
    if blockers:
        return (
            "outcome_truth_source_incomplete",
            "binds_to_execution_attempts" if has_binding else "binding_missing",
            "authoritative" if authoritative else "not_authoritative",
            "available" if has_expected else "missing",
            "available" if has_actual else "missing",
            blockers,
        )
    return (
        "outcome_truth_source_available",
        "binds_to_execution_attempts",
        "authoritative",
        "available",
        "available",
        [],
    )


def _execution_producer(manifest: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    for item in list((manifest or {}).get("producers", []) or []):
        if isinstance(item, Mapping) and str(item.get("producer_id") or "") == telemetry_backend.EXECUTION_PRODUCER_ID:
            return item
    return None


def _plan_payload(context: Mapping[str, Any]) -> dict[str, Any]:
    plan_id = _plan_id(
        str(context.get("canonical_rule_id") or ""),
        str(context.get("production_deployment_result_id") or ""),
        str(context.get("production_target_id") or ""),
        str(context.get("deployed_rule_id") or ""),
        str(context.get("telemetry_snapshot_id") or ""),
        str(context.get("readiness_result_id") or ""),
        str(context.get("effectiveness_spec_result_id") or ""),
        str(context.get("observation_window_start") or ""),
        str(context.get("observation_window_end") or ""),
        _text(context.get("outcome_truth_source_id")) or "",
        _text(context.get("outcome_truth_record_set_id")) or "",
    )
    plan = {
        "schema_version": PLAN_SCHEMA,
        "outcome_truth_source_schema_version": SOURCE_SCHEMA_VERSION,
        "outcome_truth_source_plan_id": plan_id,
        "canonical_rule_id": context.get("canonical_rule_id"),
        "production_deployment_result_id": context.get("production_deployment_result_id"),
        "production_target_id": context.get("production_target_id"),
        "deployed_rule_id": context.get("deployed_rule_id"),
        "telemetry_snapshot_id": context.get("telemetry_snapshot_id"),
        "readiness_result_id": context.get("readiness_result_id"),
        "effectiveness_spec_result_id": context.get("effectiveness_spec_result_id"),
        "observation_window_start": context.get("observation_window_start"),
        "observation_window_end": context.get("observation_window_end"),
        "outcome_truth_source_id": context.get("outcome_truth_source_id"),
        "outcome_truth_record_set_id": context.get("outcome_truth_record_set_id"),
        "source_status": context.get("source_status"),
        "binding_status": context.get("binding_status"),
        "authority_status": context.get("authority_status"),
        "criteria": deepcopy(context.get("criteria")),
        "warnings": list(context.get("warnings", [])),
        "blockers": list(context.get("blockers", [])),
        "scoring_support_status": context.get("scoring_support_status"),
        "readiness_result_fingerprint": context.get("readiness_result_fingerprint"),
        "effectiveness_spec_result_fingerprint": context.get("effectiveness_spec_result_fingerprint"),
        "telemetry_snapshot_fingerprint": context.get("telemetry_snapshot_fingerprint"),
    }
    plan["plan_fingerprint"] = _hash_payload(
        {key: plan.get(key) for key in sorted(plan) if key != "plan_fingerprint"}
    )
    return plan


def _plan_id(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    readiness_result_id: str,
    effectiveness_spec_result_id: str,
    observation_window_start: str,
    observation_window_end: str,
    outcome_truth_source_id: str,
    outcome_truth_record_set_id: str,
) -> str:
    fingerprint = _hash_payload(
        {
            "canonical_rule_id": canonical_rule_id,
            "production_deployment_result_id": production_deployment_result_id,
            "production_target_id": production_target_id,
            "deployed_rule_id": deployed_rule_id,
            "telemetry_snapshot_id": telemetry_snapshot_id,
            "readiness_result_id": readiness_result_id,
            "effectiveness_spec_result_id": effectiveness_spec_result_id,
            "observation_window_start": observation_window_start,
            "observation_window_end": observation_window_end,
            "outcome_truth_source_id": outcome_truth_source_id,
            "outcome_truth_record_set_id": outcome_truth_record_set_id,
        }
    )
    return f"deployed_rule_outcome_truth_source_plan_{fingerprint[:24]}"


def _plan_summary(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "plan_fingerprint": plan.get("plan_fingerprint"),
        "source_status": plan.get("source_status"),
        "binding_status": plan.get("binding_status"),
        "outcome_truth_record_set_id": plan.get("outcome_truth_record_set_id"),
        "warnings": list(plan.get("warnings", [])),
        "blockers": list(plan.get("blockers", [])),
    }


def _result_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "source_status": result.get("source_status"),
        "result_fingerprint": result.get("result_fingerprint"),
        "warnings": list(result.get("warnings", [])),
        "blockers": list(result.get("blockers", [])),
    }


def _result_id(plan_id: str) -> str:
    return f"deployed_rule_outcome_truth_source_result_{_safe_id(plan_id)[-24:]}"


def _receipt_id(result_id: str) -> str:
    return f"deployed_rule_outcome_truth_source_receipt_{_safe_id(result_id)[-24:]}"


def _plan_path(base: Path, plan_id: str) -> Path:
    return base / PLAN_DIR / f"{_safe_id(plan_id)}.json"


def _result_path(base: Path, result_id: str) -> Path:
    return base / RESULT_DIR / f"{_safe_id(result_id)}.json"


def _receipt_path(base: Path, receipt_id: str) -> Path:
    return base / RECEIPT_DIR / f"{_safe_id(receipt_id)}.json"


def _update_plan_index(base: Path) -> None:
    items = []
    for path in sorted((base / PLAN_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping):
            items.append(
                {
                    "outcome_truth_source_plan_id": payload.get("outcome_truth_source_plan_id"),
                    "canonical_rule_id": payload.get("canonical_rule_id"),
                    "deployed_rule_id": payload.get("deployed_rule_id"),
                    "source_status": payload.get("source_status"),
                    "plan_fingerprint": payload.get("plan_fingerprint"),
                }
            )
    _atomic_write_json(base / "indexes" / PLAN_INDEX, {"schema_version": "deployed_rule_outcome_truth_source_plan_index_v1", "items": items, "updated_at_utc": _now()})


def _update_result_index(base: Path) -> None:
    items = []
    for path in sorted((base / RESULT_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping):
            items.append(
                {
                    "outcome_truth_source_result_id": payload.get("outcome_truth_source_result_id"),
                    "outcome_truth_source_plan_id": payload.get("outcome_truth_source_plan_id"),
                    "source_status": payload.get("source_status"),
                    "result_fingerprint": payload.get("result_fingerprint"),
                }
            )
    _atomic_write_json(base / "indexes" / RESULT_INDEX, {"schema_version": "deployed_rule_outcome_truth_source_result_index_v1", "items": items, "updated_at_utc": _now()})


def _update_receipt_index(base: Path) -> None:
    items = []
    for path in sorted((base / RECEIPT_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping):
            items.append(
                {
                    "outcome_truth_source_receipt_id": payload.get("outcome_truth_source_receipt_id"),
                    "outcome_truth_source_result_id": payload.get("outcome_truth_source_result_id"),
                    "source_status": payload.get("source_status"),
                    "result_fingerprint": payload.get("result_fingerprint"),
                }
            )
    _atomic_write_json(base / "indexes" / RECEIPT_INDEX, {"schema_version": "deployed_rule_outcome_truth_source_receipt_index_v1", "items": items, "updated_at_utc": _now()})


def _update_record_set_index(base: Path) -> None:
    items = []
    for path in sorted((base / RECORD_SET_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping):
            items.append(
                {
                    "outcome_truth_record_set_id": payload.get("outcome_truth_record_set_id"),
                    "source_id": payload.get("source_id"),
                    "source_type": payload.get("source_type"),
                    "source_authority_class": payload.get("source_authority_class"),
                    "canonical_rule_id": payload.get("canonical_rule_id"),
                    "production_deployment_result_id": payload.get("production_deployment_result_id"),
                    "production_target_id": payload.get("production_target_id"),
                    "deployed_rule_id": payload.get("deployed_rule_id"),
                    "telemetry_snapshot_id": payload.get("telemetry_snapshot_id"),
                    "record_count": payload.get("record_count"),
                    "valid_record_count": payload.get("valid_record_count"),
                    "incomplete_record_count": payload.get("incomplete_record_count"),
                    "unsupported_record_count": payload.get("unsupported_record_count"),
                    "source_status": payload.get("source_status"),
                    "record_set_fingerprint": payload.get("record_set_fingerprint"),
                }
            )
    _atomic_write_json(base / "indexes" / RECORD_SET_INDEX, {"schema_version": "deployed_rule_outcome_truth_record_set_index_v1", "items": items, "updated_at_utc": _now()})


def _update_record_index(base: Path) -> None:
    items = []
    for path in sorted((base / RECORD_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping):
            items.append(
                {
                    "outcome_truth_record_id": payload.get("outcome_truth_record_id"),
                    "outcome_truth_record_set_id": payload.get("outcome_truth_record_set_id"),
                    "source_id": payload.get("source_id"),
                    "truth_status": payload.get("truth_status"),
                    "deployed_rule_id": payload.get("deployed_rule_id"),
                    "production_deployment_result_id": payload.get("production_deployment_result_id"),
                    "telemetry_snapshot_id": payload.get("telemetry_snapshot_id"),
                    "execution_event_id": payload.get("execution_event_id"),
                    "input_fingerprint": payload.get("input_fingerprint"),
                    "record_fingerprint": payload.get("record_fingerprint"),
                }
            )
    _atomic_write_json(base / "indexes" / RECORD_INDEX, {"schema_version": "deployed_rule_outcome_truth_record_index_v1", "items": items, "updated_at_utc": _now()})


def _load_all(folder: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping):
            items.append(dict(payload))
    return items


def _index_items(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    if not isinstance(payload, Mapping):
        return []
    return [dict(item) for item in list(payload.get("items", []) or []) if isinstance(item, Mapping)]


def _ensure_dirs(root: Path | str) -> Path:
    base = _ensure_analysis_dirs(root)
    for folder in (PLAN_DIR, RESULT_DIR, RECEIPT_DIR, RECORD_SET_DIR, RECORD_DIR, "indexes"):
        (base / folder).mkdir(parents=True, exist_ok=True)
    for path, payload in (
        (base / "indexes" / PLAN_INDEX, {"schema_version": "deployed_rule_outcome_truth_source_plan_index_v1", "items": [], "updated_at_utc": _now()}),
        (base / "indexes" / RESULT_INDEX, {"schema_version": "deployed_rule_outcome_truth_source_result_index_v1", "items": [], "updated_at_utc": _now()}),
        (base / "indexes" / RECEIPT_INDEX, {"schema_version": "deployed_rule_outcome_truth_source_receipt_index_v1", "items": [], "updated_at_utc": _now()}),
        (base / "indexes" / RECORD_SET_INDEX, {"schema_version": "deployed_rule_outcome_truth_record_set_index_v1", "items": [], "updated_at_utc": _now()}),
        (base / "indexes" / RECORD_INDEX, {"schema_version": "deployed_rule_outcome_truth_record_index_v1", "items": [], "updated_at_utc": _now()}),
    ):
        if not path.exists():
            _atomic_write_json(path, payload)
    return base


def _record_set_payload(
    *,
    outcome_truth_record_set_id: str,
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    source_id: str,
    source_type: str,
    source_authority_class: str,
    observation_window_start: str,
    observation_window_end: str,
    records: list[Mapping[str, Any]],
    valid_record_count: int,
    incomplete_record_count: int,
    unsupported_record_count: int,
) -> dict[str, Any]:
    payload = {
        "schema_version": RECORD_SET_SCHEMA,
        "outcome_truth_source_schema_version": SOURCE_SCHEMA_VERSION,
        "outcome_truth_record_set_id": outcome_truth_record_set_id,
        "source_id": source_id,
        "source_type": source_type,
        "source_authority_class": source_authority_class,
        "source_fingerprint": _hash_payload({"source_id": source_id, "source_type": source_type, "source_authority_class": source_authority_class}),
        "canonical_rule_id": canonical_rule_id,
        "production_deployment_result_id": production_deployment_result_id,
        "production_target_id": production_target_id,
        "deployed_rule_id": deployed_rule_id,
        "telemetry_snapshot_id": telemetry_snapshot_id,
        "observation_window_start": observation_window_start,
        "observation_window_end": observation_window_end,
        "outcome_truth_record_ids": [str(item.get("outcome_truth_record_id") or "") for item in records],
        "record_count": len(records),
        "valid_record_count": valid_record_count,
        "incomplete_record_count": incomplete_record_count,
        "unsupported_record_count": unsupported_record_count,
        "source_status": "outcome_truth_source_available" if valid_record_count == len(records) else "outcome_truth_source_incomplete" if incomplete_record_count else "outcome_truth_source_unsupported",
    }
    payload["record_set_fingerprint"] = _hash_payload({key: payload.get(key) for key in sorted(payload) if key != "record_set_fingerprint"})
    return payload


def _normalize_outcome_truth_record(
    item: Mapping[str, Any],
    *,
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    source_id: str,
    source_type: str,
    source_authority_class: str,
    observation_window_start: str,
    observation_window_end: str,
    snapshot_events: dict[str, dict[str, Any]],
    index: int,
) -> tuple[dict[str, Any], str, list[str]]:
    blockers: list[str] = []
    if not isinstance(item, Mapping):
        item = {}
        blockers.append("outcome_truth_record_invalid")
    execution_event_id = _text(item.get("execution_event_id"))
    input_fingerprint = _text(item.get("input_fingerprint"))
    expected = _normalize_public_value(item.get("expected_outcome"))
    actual = _normalize_public_value(item.get("actual_or_adjudicated_outcome"))
    truth_status = "valid"
    if source_type in {"runtime_completion", "phase9w_acceptance", "readiness_status", "absence_of_failures"}:
        blockers.append("outcome_truth_source_substitute_rejected")
        truth_status = "unsupported"
    if expected is None:
        blockers.append("outcome_truth_expected_value_missing")
        truth_status = "incomplete"
    if actual is None:
        blockers.append("outcome_truth_actual_or_adjudicated_value_missing")
        truth_status = "incomplete"
    if not execution_event_id and not input_fingerprint:
        blockers.append("outcome_truth_execution_binding_missing")
        truth_status = "incomplete"
    if execution_event_id and execution_event_id not in snapshot_events:
        blockers.append("outcome_truth_execution_event_not_found")
        truth_status = "incomplete"
    if input_fingerprint and not any(str(event.get("input_fingerprint") or "") == input_fingerprint for event in snapshot_events.values()):
        blockers.append("outcome_truth_input_fingerprint_not_found")
        truth_status = "incomplete"
    observed_at = _text(item.get("outcome_observed_at"))
    if not observed_at:
        blockers.append("outcome_truth_observed_at_missing")
        truth_status = "incomplete"
    confidence_class = _text(item.get("confidence_class")) or "bounded_public_value"
    record = {
        "schema_version": RECORD_SCHEMA,
        "outcome_truth_source_schema_version": SOURCE_SCHEMA_VERSION,
        "outcome_truth_record_id": _record_id(
            canonical_rule_id,
            production_deployment_result_id,
            deployed_rule_id,
            execution_event_id or "",
            input_fingerprint or "",
            expected,
            actual,
            index,
        ),
        "outcome_truth_record_set_id": "",
        "source_id": source_id,
        "source_type": source_type,
        "source_authority_class": source_authority_class,
        "source_fingerprint": _hash_payload({"source_id": source_id, "source_type": source_type, "source_authority_class": source_authority_class}),
        "canonical_rule_id": canonical_rule_id,
        "production_deployment_result_id": production_deployment_result_id,
        "production_target_id": production_target_id,
        "deployed_rule_id": deployed_rule_id,
        "telemetry_snapshot_id": telemetry_snapshot_id,
        "execution_event_id": execution_event_id,
        "input_fingerprint": input_fingerprint,
        "observation_window_start": observation_window_start,
        "observation_window_end": observation_window_end,
        "expected_outcome": expected,
        "actual_or_adjudicated_outcome": actual,
        "outcome_observed_at": observed_at,
        "truth_status": truth_status if truth_status in ALLOWED_TRUTH_STATUSES else "corrupt",
        "confidence_class": confidence_class,
    }
    record["record_fingerprint"] = _hash_payload({key: record.get(key) for key in sorted(record) if key != "record_fingerprint"})
    return record, record["truth_status"], blockers


def _record_set_id(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    production_target_id: str,
    deployed_rule_id: str,
    telemetry_snapshot_id: str,
    source_id: str,
    source_type: str,
    source_authority_class: str,
    records: list[Mapping[str, Any]],
) -> str:
    fingerprint = _hash_payload(
        {
            "canonical_rule_id": canonical_rule_id,
            "production_deployment_result_id": production_deployment_result_id,
            "production_target_id": production_target_id,
            "deployed_rule_id": deployed_rule_id,
            "telemetry_snapshot_id": telemetry_snapshot_id,
            "source_id": source_id,
            "source_type": source_type,
            "source_authority_class": source_authority_class,
            "record_fingerprints": [str(item.get("record_fingerprint") or "") for item in records],
        }
    )
    for item in records:
        item["outcome_truth_record_set_id"] = f"deployed_rule_outcome_truth_record_set_{fingerprint[:24]}"
    return f"deployed_rule_outcome_truth_record_set_{fingerprint[:24]}"


def _record_id(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    deployed_rule_id: str,
    execution_event_id: str,
    input_fingerprint: str,
    expected: Any,
    actual: Any,
    index: int,
) -> str:
    fingerprint = _hash_payload(
        {
            "canonical_rule_id": canonical_rule_id,
            "production_deployment_result_id": production_deployment_result_id,
            "deployed_rule_id": deployed_rule_id,
            "execution_event_id": execution_event_id,
            "input_fingerprint": input_fingerprint,
            "expected": expected,
            "actual": actual,
            "index": index,
        }
    )
    return f"deployed_rule_outcome_truth_record_{fingerprint[:24]}"


def _record_set_path(base: Path, record_set_id: str) -> Path:
    return base / RECORD_SET_DIR / f"{_safe_id(record_set_id)}.json"


def _record_path(base: Path, record_id: str) -> Path:
    return base / RECORD_DIR / f"{_safe_id(record_id)}.json"


def _snapshot_event_lookup(base: Path, telemetry_snapshot: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    events: dict[str, dict[str, Any]] = {}
    for event_id in list(telemetry_snapshot.get("validated_event_ids", []) or []):
        payload = telemetry_backend._find_event_by_id(base, str(event_id or ""))
        if isinstance(payload, Mapping):
            events[str(payload.get("event_id") or "")] = dict(payload)
    return events


def _record_files_match(base: Path, records: list[Mapping[str, Any]]) -> bool:
    for record in records:
        payload = _read_json(_record_path(base, str(record.get("outcome_truth_record_id") or "")))
        if not isinstance(payload, Mapping):
            return False
        if str(payload.get("record_fingerprint") or "") != str(record.get("record_fingerprint") or ""):
            return False
    return True


def _normalize_public_value(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text or len(text) > 200:
            return None
        return text
    return None


def _analyze_outcome_truth_record_set_for_qa(
    record_set: Mapping[str, Any],
    records: list[Mapping[str, Any]],
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    eligible_record_count = 0
    excluded_record_count = 0
    duplicate_record_count = 0
    conflict_count = 0
    missing_required_field_count = 0
    missing_expected_outcome_count = 0
    missing_actual_outcome_count = 0
    invalid_outcome_value_count = 0
    missing_source_metadata_count = 0
    malformed_record_count = 0
    identity_values: dict[str, set[tuple[Any, Any]]] = {}
    canonical_ids: set[str] = set()
    deployed_ids: set[str] = set()
    observation_windows: set[tuple[str, str]] = set()

    for field_name in (
        "outcome_truth_record_set_id",
        "source_id",
        "source_type",
        "source_authority_class",
        "canonical_rule_id",
        "production_deployment_result_id",
        "production_target_id",
        "deployed_rule_id",
        "telemetry_snapshot_id",
        "observation_window_start",
        "observation_window_end",
    ):
        if not _text(record_set.get(field_name)):
            missing_required_field_count += 1
            blockers.append(f"{field_name}_missing")

    for item in records:
        if not isinstance(item, Mapping):
            malformed_record_count += 1
            missing_required_field_count += 1
            blockers.append("outcome_truth_record_invalid")
            excluded_record_count += 1
            continue
        record_id = _text(item.get("outcome_truth_record_id"))
        source_id = _text(item.get("source_id"))
        source_type = _text(item.get("source_type"))
        source_authority_class = _text(item.get("source_authority_class"))
        expected_value = item.get("expected_outcome")
        actual_value = item.get("actual_or_adjudicated_outcome")
        truth_status = _text(item.get("truth_status")) or "unknown"
        execution_event_id = _text(item.get("execution_event_id"))
        input_fingerprint = _text(item.get("input_fingerprint"))
        canonical_ids.add(_text(item.get("canonical_rule_id")) or "")
        deployed_ids.add(_text(item.get("deployed_rule_id")) or "")
        observation_windows.add((_text(item.get("observation_window_start")) or "", _text(item.get("observation_window_end")) or ""))

        if not record_id:
            missing_required_field_count += 1
            blockers.append("outcome_truth_record_id_missing")
        if not source_id or not source_type or not source_authority_class:
            missing_source_metadata_count += 1
            warnings.append("outcome_truth_source_metadata_missing")
        if _normalize_public_value(expected_value) is None:
            missing_expected_outcome_count += 1
            missing_required_field_count += 1
            blockers.append("outcome_truth_expected_value_missing")
        if _normalize_public_value(actual_value) is None:
            missing_actual_outcome_count += 1
            missing_required_field_count += 1
            blockers.append("outcome_truth_actual_or_adjudicated_value_missing")
        if expected_value is not None and _normalize_public_value(expected_value) is None:
            invalid_outcome_value_count += 1
            blockers.append("outcome_truth_expected_value_invalid")
        if actual_value is not None and _normalize_public_value(actual_value) is None:
            invalid_outcome_value_count += 1
            blockers.append("outcome_truth_actual_or_adjudicated_value_invalid")
        if truth_status not in ALLOWED_TRUTH_STATUSES:
            malformed_record_count += 1
            blockers.append("outcome_truth_truth_status_invalid")
        if not execution_event_id and not input_fingerprint:
            missing_required_field_count += 1
            blockers.append("outcome_truth_execution_binding_missing")

        identity_key = execution_event_id or input_fingerprint or record_id or f"missing_identity_{len(identity_values)}"
        identity_values.setdefault(identity_key, set()).add(
            (_normalize_public_value(expected_value), _normalize_public_value(actual_value))
        )
        if len(identity_values[identity_key]) == 2:
            conflict_count += 1
            blockers.append("outcome_truth_record_conflict_detected")
        elif len(identity_values[identity_key]) > 2:
            blockers.append("outcome_truth_record_conflict_detected")
        if len(identity_values[identity_key]) > 0 and sum(1 for record in records if isinstance(record, Mapping) and ((_text(record.get("execution_event_id")) or _text(record.get("input_fingerprint")) or _text(record.get("outcome_truth_record_id")) or "") == identity_key)) > 1:
            duplicate_record_count = max(duplicate_record_count, 0)

        is_eligible = (
            _normalize_public_value(expected_value) is not None
            and _normalize_public_value(actual_value) is not None
            and truth_status == "valid"
            and bool(execution_event_id or input_fingerprint)
        )
        if is_eligible:
            eligible_record_count += 1
        else:
            excluded_record_count += 1

    duplicate_record_count = 0
    key_counts: dict[str, int] = {}
    for item in records:
        if not isinstance(item, Mapping):
            continue
        identity_key = _text(item.get("execution_event_id")) or _text(item.get("input_fingerprint")) or _text(item.get("outcome_truth_record_id")) or ""
        if not identity_key:
            continue
        key_counts[identity_key] = key_counts.get(identity_key, 0) + 1
    duplicate_record_count = sum(1 for count in key_counts.values() if count > 1)
    if duplicate_record_count:
        warnings.append("outcome_truth_duplicate_records_detected")
    if len({item for item in canonical_ids if item}) > 1:
        warnings.append("outcome_truth_mixed_canonical_rule_scope")
    if len({item for item in deployed_ids if item}) > 1:
        warnings.append("outcome_truth_mixed_deployed_rule_scope")
    if len({item for item in observation_windows if any(part for part in item)}) > 1:
        warnings.append("outcome_truth_mixed_observation_windows")

    return {
        "eligible_record_count": eligible_record_count,
        "excluded_record_count": excluded_record_count,
        "duplicate_record_count": duplicate_record_count,
        "conflict_count": conflict_count,
        "missing_required_field_count": missing_required_field_count,
        "missing_expected_outcome_count": missing_expected_outcome_count,
        "missing_actual_outcome_count": missing_actual_outcome_count,
        "invalid_outcome_value_count": invalid_outcome_value_count,
        "missing_source_metadata_count": missing_source_metadata_count,
        "malformed_record_count": malformed_record_count,
        "blockers": _dedupe(blockers),
        "warnings": _dedupe(warnings),
    }


def _analyze_candidate_outcome_truth_record_set_for_registration_qa(
    candidate_record_set: Mapping[str, Any],
    records: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    eligible_record_count = 0
    excluded_record_count = 0
    duplicate_record_count = 0
    conflict_count = 0
    missing_required_field_count = 0
    missing_expected_outcome_count = 0
    missing_actual_outcome_count = 0
    invalid_outcome_value_count = 0
    missing_source_metadata_count = 0
    malformed_record_count = 0
    identity_values: dict[str, set[tuple[Any, Any]]] = {}
    canonical_ids: set[str] = set()
    deployed_ids: set[str] = set()
    observation_windows: set[tuple[str, str]] = set()
    key_counts: dict[str, int] = {}

    for field_name in (
        "canonical_rule_id",
        "production_deployment_result_id",
        "production_target_id",
        "deployed_rule_id",
        "telemetry_snapshot_id",
        "observation_window_start",
        "observation_window_end",
        "source_id",
        "source_type",
        "source_authority_class",
    ):
        if not _text(candidate_record_set.get(field_name)):
            missing_required_field_count += 1
            blockers.append(f"{field_name}_missing")

    for item in records:
        if not isinstance(item, Mapping):
            malformed_record_count += 1
            missing_required_field_count += 1
            blockers.append("candidate_outcome_truth_record_malformed")
            excluded_record_count += 1
            continue

        expected_value = item.get("expected_outcome")
        actual_value = item.get("actual_or_adjudicated_outcome")
        truth_status = _text(item.get("truth_status")) or "unknown"
        execution_event_id = _text(item.get("execution_event_id"))
        input_fingerprint = _text(item.get("input_fingerprint"))
        observed_at = _text(item.get("outcome_observed_at"))
        canonical_ids.add(_text(item.get("canonical_rule_id")) or _text(candidate_record_set.get("canonical_rule_id")) or "")
        deployed_ids.add(_text(item.get("deployed_rule_id")) or _text(candidate_record_set.get("deployed_rule_id")) or "")
        observation_windows.add(
            (
                _text(item.get("observation_window_start")) or _text(candidate_record_set.get("observation_window_start")) or "",
                _text(item.get("observation_window_end")) or _text(candidate_record_set.get("observation_window_end")) or "",
            )
        )

        if not (_text(item.get("source_id")) and _text(item.get("source_type")) and _text(item.get("source_authority_class"))):
            missing_source_metadata_count += 1
            warnings.append("outcome_truth_source_metadata_missing")
        if _normalize_public_value(expected_value) is None:
            missing_expected_outcome_count += 1
            missing_required_field_count += 1
            blockers.append("outcome_truth_expected_value_missing")
        if _normalize_public_value(actual_value) is None:
            missing_actual_outcome_count += 1
            missing_required_field_count += 1
            blockers.append("outcome_truth_actual_or_adjudicated_value_missing")
        if expected_value is not None and _normalize_public_value(expected_value) is None:
            invalid_outcome_value_count += 1
            blockers.append("outcome_truth_expected_value_invalid")
        if actual_value is not None and _normalize_public_value(actual_value) is None:
            invalid_outcome_value_count += 1
            blockers.append("outcome_truth_actual_or_adjudicated_value_invalid")
        if truth_status not in ALLOWED_TRUTH_STATUSES:
            malformed_record_count += 1
            blockers.append("outcome_truth_truth_status_invalid")
        if not (execution_event_id or input_fingerprint):
            missing_required_field_count += 1
            blockers.append("outcome_truth_execution_binding_missing")
        if not observed_at:
            missing_required_field_count += 1
            blockers.append("outcome_truth_observed_at_missing")

        identity_key = execution_event_id or input_fingerprint or _text(item.get("outcome_truth_record_id")) or f"missing_identity_{len(identity_values)}"
        identity_values.setdefault(identity_key, set()).add(
            (_normalize_public_value(expected_value), _normalize_public_value(actual_value))
        )
        key_counts[identity_key] = key_counts.get(identity_key, 0) + 1
        if len(identity_values[identity_key]) == 2:
            conflict_count += 1
            blockers.append("outcome_truth_record_conflict_detected")
        elif len(identity_values[identity_key]) > 2:
            blockers.append("outcome_truth_record_conflict_detected")

        is_eligible = (
            _normalize_public_value(expected_value) is not None
            and _normalize_public_value(actual_value) is not None
            and truth_status == "valid"
            and bool(execution_event_id or input_fingerprint)
            and bool(observed_at)
        )
        if is_eligible:
            eligible_record_count += 1
        else:
            excluded_record_count += 1

    duplicate_record_count = sum(1 for count in key_counts.values() if count > 1)
    if duplicate_record_count:
        warnings.append("outcome_truth_duplicate_records_detected")
    if len({item for item in canonical_ids if item}) > 1:
        warnings.append("outcome_truth_mixed_canonical_rule_scope")
    if len({item for item in deployed_ids if item}) > 1:
        warnings.append("outcome_truth_mixed_deployed_rule_scope")
    if len({item for item in observation_windows if any(part for part in item)}) > 1:
        warnings.append("outcome_truth_mixed_observation_windows")

    return {
        "eligible_record_count": eligible_record_count,
        "excluded_record_count": excluded_record_count,
        "duplicate_record_count": duplicate_record_count,
        "conflict_count": conflict_count,
        "missing_required_field_count": missing_required_field_count,
        "missing_expected_outcome_count": missing_expected_outcome_count,
        "missing_actual_outcome_count": missing_actual_outcome_count,
        "invalid_outcome_value_count": invalid_outcome_value_count,
        "missing_source_metadata_count": missing_source_metadata_count,
        "malformed_record_count": malformed_record_count,
        "blockers": _dedupe(blockers),
        "warnings": _dedupe(warnings),
    }


def _outcome_truth_record_set_qa_limitations() -> list[str]:
    return [
        "This QA gate checks structural and internal consistency of an outcome-truth record set.",
        "It does not prove the factual correctness of outcome-truth records.",
        "It does not establish broad rule effectiveness.",
        "It does not establish deployment safety.",
        "It does not establish production correctness.",
        "It does not establish profitability.",
        "It does not establish prediction quality.",
        "It does not establish future performance.",
        "It does not establish aggregate effectiveness.",
        "It does not establish ranking quality.",
    ]


def _outcome_truth_record_set_qa_boundary_flags() -> dict[str, bool]:
    return {
        "outcome_truth_factual_correctness_claimed": False,
        "broad_effectiveness_claimed": False,
        "deployment_safety_claimed": False,
        "production_correctness_claimed": False,
        "profitability_claimed": False,
        "prediction_quality_claimed": False,
        "future_performance_claimed": False,
        "aggregate_effectiveness_claimed": False,
        "ranking_quality_claimed": False,
    }


def _outcome_truth_record_set_registration_pipeline_qa_limitations() -> list[str]:
    return [
        "This registration-pipeline QA gate checks structural and internal consistency of a candidate outcome-truth record set before registration.",
        "It does not register the record set.",
        "It does not repair or migrate records.",
        "It does not prove the factual correctness of outcome-truth records.",
        "It does not establish broad rule effectiveness.",
        "It does not establish deployment safety.",
        "It does not establish production correctness.",
        "It does not establish profitability.",
        "It does not establish prediction quality.",
        "It does not establish future performance.",
        "It does not establish aggregate effectiveness.",
        "It does not establish ranking quality.",
    ]


def _outcome_truth_record_set_registration_pipeline_qa_boundary_flags() -> dict[str, bool]:
    return {
        "registration_performed": False,
        "record_set_written": False,
        "records_repaired": False,
        "records_migrated": False,
        "outcome_truth_factual_correctness_claimed": False,
        "broad_effectiveness_claimed": False,
        "deployment_safety_claimed": False,
        "production_correctness_claimed": False,
        "profitability_claimed": False,
        "prediction_quality_claimed": False,
        "future_performance_claimed": False,
        "aggregate_effectiveness_claimed": False,
        "ranking_quality_claimed": False,
    }


def _outcome_truth_record_set_controlled_registration_workflow_planning_limitations() -> list[str]:
    return [
        "This planning gate checks readiness to design a future controlled outcome-truth record-set registration workflow.",
        "It does not register records.",
        "It does not create record sets.",
        "It does not repair records.",
        "It does not migrate records.",
        "It does not approve automatic registration.",
        "It does not prove factual correctness of outcome-truth records.",
        "It does not establish broad rule effectiveness.",
        "It does not establish deployment safety.",
        "It does not establish production correctness.",
        "It does not establish profitability.",
        "It does not establish prediction quality.",
        "It does not establish future performance.",
        "It does not establish aggregate effectiveness.",
        "It does not establish ranking quality.",
    ]


def _outcome_truth_record_set_controlled_registration_workflow_planning_boundary_flags() -> dict[str, bool]:
    return {
        "controlled_registration_implemented": False,
        "registration_performed": False,
        "record_set_written": False,
        "records_repaired": False,
        "records_migrated": False,
        "automatic_registration_approval_claimed": False,
        "outcome_truth_factual_correctness_claimed": False,
        "broad_effectiveness_claimed": False,
        "deployment_safety_claimed": False,
        "production_correctness_claimed": False,
        "profitability_claimed": False,
        "prediction_quality_claimed": False,
        "future_performance_claimed": False,
        "aggregate_effectiveness_claimed": False,
        "ranking_quality_claimed": False,
    }


def _outcome_truth_record_set_controlled_registration_workflow_backend_plan_limitations() -> list[str]:
    return [
        "This backend plan is a read-only, non-executing plan for a future controlled outcome-truth record-set registration workflow.",
        "It does not register records.",
        "It does not create record sets.",
        "It does not persist a plan.",
        "It does not create indexes or receipts.",
        "It does not repair records.",
        "It does not migrate records.",
        "It does not accept or enforce confirmation in this phase.",
        "It does not approve automatic registration.",
        "It does not prove factual correctness of outcome-truth records.",
        "It does not establish broad rule effectiveness.",
        "It does not establish deployment safety.",
        "It does not establish production correctness.",
        "It does not establish profitability.",
        "It does not establish prediction quality.",
        "It does not establish future performance.",
        "It does not establish aggregate effectiveness.",
        "It does not establish ranking quality.",
    ]


def _outcome_truth_record_set_controlled_registration_workflow_backend_plan_boundary_flags() -> dict[str, bool]:
    return {
        "backend_plan_persisted": False,
        "controlled_registration_implemented": False,
        "registration_performed": False,
        "record_set_written": False,
        "records_repaired": False,
        "records_migrated": False,
        "confirmation_accepted_in_this_phase": False,
        "confirmation_enforced_in_this_phase": False,
        "automatic_registration_approval_claimed": False,
        "outcome_truth_factual_correctness_claimed": False,
        "broad_effectiveness_claimed": False,
        "deployment_safety_claimed": False,
        "production_correctness_claimed": False,
        "profitability_claimed": False,
        "prediction_quality_claimed": False,
        "future_performance_claimed": False,
        "aggregate_effectiveness_claimed": False,
        "ranking_quality_claimed": False,
    }


def _outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_limitations() -> list[str]:
    return [
        "This identity and binding gate proves only deterministic structural binding between a candidate payload, the planning-gate result, and the non-executing backend plan.",
        "It does not authorize registration.",
        "It does not register records.",
        "It does not accept or enforce confirmation.",
        "It does not persist a plan.",
        "It does not prove factual correctness of outcome-truth records.",
        "It does not establish broad rule effectiveness.",
        "It does not establish deployment safety.",
        "It does not establish production correctness.",
        "It does not establish profitability.",
        "It does not establish prediction quality.",
        "It does not establish future performance.",
        "It does not establish aggregate effectiveness.",
        "It does not establish ranking quality.",
        "A valid fingerprint proves integrity against the defined canonical representation only.",
        "It does not prove that the underlying facts are true.",
    ]


def _outcome_truth_record_set_controlled_registration_workflow_backend_plan_binding_boundary_flags() -> dict[str, bool]:
    return {
        "execution_authorized": False,
        "registration_authorized": False,
        "confirmation_accepted": False,
        "confirmation_enforced": False,
        "automatic_registration_approval_claimed": False,
        "outcome_truth_factual_correctness_claimed": False,
        "broad_effectiveness_claimed": False,
        "deployment_safety_claimed": False,
        "production_correctness_claimed": False,
        "profitability_claimed": False,
        "prediction_quality_claimed": False,
        "future_performance_claimed": False,
        "aggregate_effectiveness_claimed": False,
        "ranking_quality_claimed": False,
    }


def _outcome_truth_record_set_controlled_registration_execution_planning_limitations() -> list[str]:
    return [
        "Phase 14A defines planning requirements for a future transactional registration execution workflow.",
        "Phase 14A does not execute registration.",
        "Phase 14A does not call the registration function.",
        "Phase 14A does not create a transaction, idempotency record, execution plan, or receipt.",
        "Phase 14A does not accept or enforce confirmation.",
        "Structural readiness and valid binding are not execution authorization.",
        "Structural readiness and valid binding are not registration authorization.",
        "The future confirmation phrase is advisory only in this phase.",
        "A valid fingerprint or binding does not prove factual correctness of outcome-truth records.",
        "It does not establish broad rule effectiveness.",
        "It does not establish deployment safety.",
        "It does not establish production correctness.",
        "It does not establish profitability.",
        "It does not establish prediction quality.",
        "It does not establish future performance.",
        "It does not establish aggregate effectiveness.",
        "It does not establish ranking quality.",
    ]


def _outcome_truth_record_set_controlled_registration_execution_planning_boundary_flags() -> dict[str, bool]:
    return {
        "future_execution_contract_implemented": False,
        "transaction_implemented": False,
        "registration_execution_implemented": False,
        "execution_plan_persisted": False,
        "idempotency_record_created": False,
        "transaction_created": False,
        "receipt_created": False,
        "confirmation_accepted_in_this_phase": False,
        "confirmation_enforced_in_this_phase": False,
        "execution_authorized": False,
        "registration_authorized": False,
        "registration_performed": False,
        "record_set_written": False,
        "records_repaired": False,
        "records_migrated": False,
        "automatic_registration_approval_claimed": False,
        "outcome_truth_factual_correctness_claimed": False,
        "broad_effectiveness_claimed": False,
        "deployment_safety_claimed": False,
        "production_correctness_claimed": False,
        "profitability_claimed": False,
        "prediction_quality_claimed": False,
        "future_performance_claimed": False,
        "aggregate_effectiveness_claimed": False,
        "ranking_quality_claimed": False,
    }


def _outcome_truth_record_set_controlled_registration_transaction_plan_limitations() -> list[str]:
    return [
        "Phase 14B builds a deterministic in-memory transaction-plan preview and evaluates it through a read-only dry run.",
        "Phase 14B does not call the registration function.",
        "Phase 14B performs zero writes.",
        "Phase 14B does not create or persist a transaction, idempotency record, execution plan, dry-run result, or receipt.",
        "The idempotency-key preview is deterministic planning metadata only.",
        "It is not authoritative, persisted, reserved, or enforced.",
        "planned_write_count = 1 describes future intent only.",
        "writes_performed = 0 records actual Phase 14B behavior.",
        "A passing dry run does not authorize execution.",
        "A passing dry run does not authorize registration.",
        "A passing dry run does not accept or enforce confirmation.",
        "A passing dry run does not prove the future registration will succeed.",
        "A valid fingerprint proves integrity against the defined canonical representation only.",
        "It does not prove factual correctness of outcome-truth records.",
        "Unknown target state must be reported conservatively.",
        "Ambiguous future write outcomes must block automatic retry.",
        "Post-write verification failure must not be classified as clean success.",
    ]


def _outcome_truth_record_set_controlled_registration_transaction_plan_boundary_flags() -> dict[str, bool]:
    return {
        "transaction_plan_persisted": False,
        "transaction_created": False,
        "transaction_id_created": False,
        "idempotency_key_preview_authoritative": False,
        "idempotency_key_preview_persisted": False,
        "idempotency_enforced": False,
        "dry_run_persisted": False,
        "receipt_created": False,
        "receipt_persisted": False,
        "confirmation_accepted_in_this_phase": False,
        "confirmation_enforced_in_this_phase": False,
        "execution_authorized": False,
        "registration_authorized": False,
        "registration_execution_implemented": False,
        "registration_performed": False,
        "record_set_written": False,
        "records_repaired": False,
        "records_migrated": False,
        "automatic_registration_approval_claimed": False,
        "outcome_truth_factual_correctness_claimed": False,
        "broad_effectiveness_claimed": False,
        "deployment_safety_claimed": False,
        "production_correctness_claimed": False,
        "profitability_claimed": False,
        "prediction_quality_claimed": False,
        "future_performance_claimed": False,
        "aggregate_effectiveness_claimed": False,
        "ranking_quality_claimed": False,
    }


def _outcome_truth_record_set_controlled_registration_transaction_dry_run_limitations() -> list[str]:
    return _outcome_truth_record_set_controlled_registration_transaction_plan_limitations()


def _outcome_truth_record_set_controlled_registration_transaction_dry_run_boundary_flags() -> dict[str, bool]:
    return _outcome_truth_record_set_controlled_registration_transaction_plan_boundary_flags()


def _outcome_truth_record_set_controlled_registration_transaction_plan_binding_limitations() -> list[str]:
    return [
        "Phase 14C adds deterministic identity, target binding, and stale-target detection to the Phase 14B transaction plan.",
        "Target-state freshness is proven only when a safe non-creating read path is available and the current target-state snapshot matches the snapshot bound into the transaction plan.",
        "Unknown target state must not be described as current.",
        "Lack of detected staleness is not proof of freshness when target observation is unavailable.",
        "A valid transaction-plan binding does not authorize execution.",
        "A valid transaction-plan binding does not authorize registration.",
        "Phase 14C does not call the registration function.",
        "Phase 14C does not accept or enforce confirmation.",
        "Phase 14C does not enforce idempotency.",
        "Phase 14C does not persist target-state snapshots, transaction plans, dry-run results, or receipts.",
        "Stale or modified transaction plans must be rebuilt rather than repaired in place.",
        "A valid fingerprint proves integrity against the defined canonical representation only.",
        "It does not prove factual correctness of outcome-truth records.",
    ]


def _outcome_truth_record_set_controlled_registration_transaction_plan_binding_boundary_flags() -> dict[str, bool]:
    return _outcome_truth_record_set_controlled_registration_transaction_plan_boundary_flags()


def _outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate_limitations() -> list[str]:
    return [
        "Phase 15A is read-only and non-persistent.",
        "Phase 15A does not create or persist an authorization artifact, authorization ID, transaction, receipt, or idempotency registry entry.",
        "Phase 15A does not accept, compare, match, or enforce confirmation.",
        "Phase 15A does not authorize execution or registration.",
        "A passing dry run is necessary but not sufficient for future authorization design.",
        "The current idempotency preview remains deterministic planning metadata only.",
        "It is not authoritative, persisted, reserved, or enforced.",
        "No factual truth correctness, broad effectiveness, production correctness, deployment safety, profitability, prediction quality, or ranking claim is made.",
        "Dry-run evidence identity is a future required field and known contract gap.",
    ]


def _outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate_boundary_flags() -> dict[str, bool]:
    return {
        "authorization_artifact_implemented": False,
        "authorization_artifact_created": False,
        "authorization_artifact_persisted": False,
        "authorization_id_created": False,
        "authorization_registry_created": False,
        "authorization_granted": False,
        "authorization_consumed": False,
        "confirmation_supplied_in_this_phase": False,
        "confirmation_matched_in_this_phase": False,
        "confirmation_accepted_in_this_phase": False,
        "confirmation_enforced_in_this_phase": False,
        "transaction_created": False,
        "transaction_id_created": False,
        "idempotency_identity_authoritative": False,
        "idempotency_identity_persisted": False,
        "idempotency_enforced": False,
        "receipt_created": False,
        "receipt_persisted": False,
        "execution_authorized": False,
        "registration_authorized": False,
        "registration_execution_implemented": False,
        "registration_performed": False,
        "record_set_written": False,
        "records_repaired": False,
        "records_migrated": False,
        "automatic_registration_approval_claimed": False,
        "outcome_truth_factual_correctness_claimed": False,
        "broad_effectiveness_claimed": False,
        "deployment_safety_claimed": False,
        "production_correctness_claimed": False,
        "profitability_claimed": False,
        "prediction_quality_claimed": False,
        "future_performance_claimed": False,
        "aggregate_effectiveness_claimed": False,
        "ranking_quality_claimed": False,
    }


def _outcome_truth_record_set_controlled_registration_authorization_artifact_preview_limitations() -> list[str]:
    return [
        "Phase 15B is read-only and non-persistent.",
        "Phase 15B does not create an authorization artifact, authorization ID, registry entry, transaction, or receipt.",
        "Phase 15B does not grant execution or registration authorization.",
        "Phase 15B does not accept or enforce confirmation.",
        "The authorization preview is non-authoritative and unpersisted.",
        "The dry-run evidence fingerprint identifies stable structural dry-run evidence only.",
        "The authorization-preview fingerprint identifies the deterministic preview contract only.",
        "Neither fingerprint is an authorization ID or authorization grant.",
        "The idempotency-key preview remains non-authoritative, unpersisted, unreserved, and unenforced.",
        "Dry-run evidence projection remains schema-sensitive.",
        "Authorization-preview canonicalization remains schema-sensitive.",
        "No factual truth correctness, broad effectiveness, production correctness, deployment safety, profitability, prediction quality, or ranking claim is made.",
    ]


def _outcome_truth_record_set_controlled_registration_authorization_artifact_preview_boundary_flags() -> dict[str, bool]:
    return {
        **_outcome_truth_record_set_controlled_registration_execution_authorization_confirmation_contract_gate_boundary_flags(),
        "authorization_artifact_preview_authoritative": False,
        "authorization_artifact_preview_persisted": False,
        "dry_run_evidence_persisted": False,
        "confirmation_evidence_persisted": False,
    }


def _outcome_truth_record_set_controlled_registration_confirmation_dry_run_limitations() -> list[str]:
    return [
        "Phase 15B confirmation matching is evaluated in a read-only dry run only.",
        "Exact confirmation match is dry-run evidence only.",
        "It is not accepted confirmation, enforced confirmation, or an authorization grant.",
        "The caller-supplied confirmation text is not persisted, echoed, or included in public-safe reports.",
        "Confirmation match must not override stale, modified, unknown-target, conflicting-target, or failed dry-run prerequisites.",
        "No authorization artifact, transaction, receipt, or registry entry is created.",
        "No idempotency is enforced.",
        "No factual truth correctness, broad effectiveness, production correctness, deployment safety, profitability, prediction quality, or ranking claim is made.",
    ]


def _outcome_truth_record_set_controlled_registration_confirmation_dry_run_boundary_flags() -> dict[str, bool]:
    return _outcome_truth_record_set_controlled_registration_authorization_artifact_preview_boundary_flags()


def _outcome_truth_record_set_controlled_registration_authorization_preview_confirmation_evidence_binding_limitations() -> list[str]:
    return [
        "binding gate remains non-authoritative",
        "authorization preview remains unpersisted",
        "no authorization artifact or registry exists",
        "no accepted-confirmation mechanism exists",
        "no authoritative idempotency registry exists",
        "no authorization-consumption mechanism exists",
        "no registration write boundary is exercised",
        "no ambiguous-outcome recovery exists",
        "no rollback support is claimed",
        "preview/evidence canonicalization remains schema-sensitive",
        "fixture coverage remains narrow",
        "factual truth remains out of scope",
        "broad regression coverage remains unclaimed",
    ]


def _outcome_truth_record_set_controlled_registration_authorization_preview_confirmation_evidence_binding_boundary_flags() -> dict[str, bool]:
    return _outcome_truth_record_set_controlled_registration_confirmation_dry_run_boundary_flags()


def _controlled_registration_confirmation_match_policy() -> dict[str, Any]:
    return {
        "match_type": "exact_literal",
        "case_sensitive": True,
        "trim_before_compare": False,
        "unicode_normalization": "none",
        "substring_match_allowed": False,
        "implicit_confirmation_allowed": False,
    }


def _compute_controlled_registration_dry_run_evidence_fingerprint(
    *,
    dry_run: Mapping[str, Any],
    transaction_plan: Mapping[str, Any],
    binding: Mapping[str, Any],
) -> str:
    payload = {
        "dry_run_schema_version": dry_run.get("dry_run_schema_version"),
        "dry_run_type": dry_run.get("dry_run_type"),
        "status": dry_run.get("status"),
        "dry_run": dry_run.get("dry_run"),
        "dry_run_passed": dry_run.get("dry_run_passed"),
        "transaction_plan_fingerprint": transaction_plan.get("transaction_plan_fingerprint"),
        "transaction_plan_binding_valid": binding.get("transaction_plan_binding_valid"),
        "transaction_plan_integrity_valid": binding.get("transaction_plan_integrity_valid"),
        "candidate_fingerprint": transaction_plan.get("candidate_fingerprint"),
        "backend_plan_fingerprint": transaction_plan.get("backend_plan_fingerprint"),
        "target_identity_fingerprint": transaction_plan.get("target_identity_fingerprint"),
        "target_state_snapshot_fingerprint": transaction_plan.get("target_state_snapshot_fingerprint"),
        "target_state_freshness_status": binding.get("target_state_freshness_status"),
        "target_state_freshness_proven": binding.get("target_state_freshness_proven"),
        "stale_target_detected": binding.get("stale_target_detected"),
        "target_state_changed_detected": binding.get("target_state_changed_detected"),
        "target_conflict_detected": binding.get("target_conflict_detected"),
        "idempotency_preview_valid": binding.get("idempotency_preview_valid"),
        "planned_write_function": transaction_plan.get("planned_write_function"),
        "planned_write_count": transaction_plan.get("planned_write_count"),
        "writes_performed": dry_run.get("writes_performed"),
        "would_call_registration_function": dry_run.get("would_call_registration_function"),
        "execution_authorized": dry_run.get("execution_authorized"),
        "registration_authorized": dry_run.get("registration_authorized"),
        "confirmation_accepted": dry_run.get("confirmation_accepted"),
        "confirmation_enforced": dry_run.get("confirmation_enforced"),
        "idempotency_enforced": dry_run.get("idempotency_enforced"),
    }
    return _hash_payload(_canonicalize_for_identity(payload))


def _compute_controlled_registration_authorization_artifact_preview_fingerprint(
    preview: Mapping[str, Any],
) -> str:
    boundary_flags = preview.get("boundary_flags", {})
    if not isinstance(boundary_flags, Mapping):
        boundary_flags = {}
    payload = {
        "authorization_artifact_preview_schema_version": preview.get("authorization_artifact_preview_schema_version"),
        "authorization_artifact_preview_type": preview.get("authorization_artifact_preview_type"),
        "candidate_fingerprint": preview.get("candidate_fingerprint"),
        "planning_gate_fingerprint": preview.get("planning_gate_fingerprint"),
        "backend_plan_fingerprint": preview.get("backend_plan_fingerprint"),
        "target_identity_fingerprint": preview.get("target_identity_fingerprint"),
        "target_state_snapshot_fingerprint": preview.get("target_state_snapshot_fingerprint"),
        "transaction_plan_fingerprint": preview.get("transaction_plan_fingerprint"),
        "dry_run_evidence_fingerprint": preview.get("dry_run_evidence_fingerprint"),
        "idempotency_key_preview": preview.get("idempotency_key_preview"),
        "authorization_scope_preview": _canonicalize_for_identity(preview.get("authorization_scope_preview", {})),
        "maximum_registration_attempts": preview.get("maximum_registration_attempts"),
        "single_use_required": preview.get("single_use_required"),
        "required_confirmation": preview.get("required_confirmation"),
        "confirmation_match_policy": _canonicalize_for_identity(preview.get("confirmation_match_policy", {})),
        "planned_write_function": preview.get("planned_write_function"),
        "planned_write_count": preview.get("planned_write_count"),
        "boundary_flags": {
            key: boundary_flags.get(key)
            for key in sorted(boundary_flags)
            if key
            in {
                "authorization_artifact_preview_authoritative",
                "authorization_artifact_preview_persisted",
                "authorization_artifact_created",
                "authorization_artifact_persisted",
                "authorization_id_created",
                "authorization_registry_created",
                "authorization_granted",
                "authorization_consumed",
                "confirmation_accepted",
                "confirmation_enforced",
                "execution_authorized",
                "registration_authorized",
                "registration_performed",
                "record_set_written",
            }
        },
    }
    return _hash_payload(_canonicalize_for_identity(payload))


def _compute_controlled_registration_confirmation_evidence_fingerprint(
    *,
    authorization_artifact_preview_fingerprint: str | None,
    dry_run_evidence_fingerprint: str | None,
    required_confirmation: str,
    confirmation_match_policy: Mapping[str, Any],
    confirmation_supplied: bool,
    confirmation_exact_match: bool,
    transaction_plan_fingerprint: str | None,
    target_state_snapshot_fingerprint: str | None,
    idempotency_key_preview: str | None,
) -> str:
    payload = {
        "confirmation_evidence_schema_version": 1,
        "authorization_artifact_preview_fingerprint": authorization_artifact_preview_fingerprint,
        "dry_run_evidence_fingerprint": dry_run_evidence_fingerprint,
        "required_confirmation": required_confirmation,
        "confirmation_match_policy": _canonicalize_for_identity(confirmation_match_policy),
        "confirmation_supplied": confirmation_supplied,
        "confirmation_exact_match": confirmation_exact_match,
        "transaction_plan_fingerprint": transaction_plan_fingerprint,
        "target_state_snapshot_fingerprint": target_state_snapshot_fingerprint,
        "idempotency_key_preview": idempotency_key_preview,
        "false_authority_flags": {
            "confirmation_accepted": False,
            "confirmation_enforced": False,
            "authorization_granted": False,
            "execution_authorized": False,
            "registration_authorized": False,
        },
    }
    return _hash_payload(_canonicalize_for_identity(payload))


def _build_controlled_registration_transaction_target_identity(
    candidate_record_set: Any,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    if not isinstance(candidate_record_set, Mapping):
        return {
            "status": "malformed",
            "target_identity": {},
            "target_identity_fingerprint": None,
            "record_set_fingerprint_preview": None,
            "blockers": ["candidate_record_set_malformed"],
            "warnings": [],
        }
    explicit_ids = [
        _text(candidate_record_set.get("outcome_truth_record_set_id")),
        _text(candidate_record_set.get("record_set_id")),
    ]
    normalized_explicit_ids = [item for item in explicit_ids if item]
    if len(set(normalized_explicit_ids)) > 1:
        return {
            "status": "blocked",
            "target_identity": {},
            "target_identity_fingerprint": None,
            "record_set_fingerprint_preview": None,
            "blockers": ["transaction_target_identity_ambiguous"],
            "warnings": [],
        }
    try:
        validation = validate_deployed_rule_outcome_truth_record_set(
            str(candidate_record_set.get("canonical_rule_id") or ""),
            str(candidate_record_set.get("production_deployment_result_id") or ""),
            str(candidate_record_set.get("production_target_id") or ""),
            str(candidate_record_set.get("deployed_rule_id") or ""),
            str(candidate_record_set.get("telemetry_snapshot_id") or ""),
            str(candidate_record_set.get("observation_window_start") or ""),
            str(candidate_record_set.get("observation_window_end") or ""),
            source_id=str(candidate_record_set.get("source_id") or ""),
            source_type=str(candidate_record_set.get("source_type") or ""),
            source_authority_class=str(candidate_record_set.get("source_authority_class") or ""),
            records=deepcopy(candidate_record_set.get("records", [])),
            root=root,
        )
    except Exception:
        return {
            "status": "blocked",
            "target_identity": {},
            "target_identity_fingerprint": None,
            "record_set_fingerprint_preview": None,
            "blockers": ["transaction_target_identity_missing"],
            "warnings": ["target_identity_validation_unavailable"],
        }

    derived_record_set_id = _text(validation.get("outcome_truth_record_set_id"))
    derived_record_set_fingerprint = _text(validation.get("record_set_fingerprint"))
    if not derived_record_set_id or not derived_record_set_fingerprint:
        return {
            "status": "missing",
            "target_identity": {},
            "target_identity_fingerprint": None,
            "record_set_fingerprint_preview": None,
            "blockers": ["transaction_target_identity_missing"],
            "warnings": list(validation.get("warnings", [])) if isinstance(validation.get("warnings"), list) else [],
        }

    explicit_record_set_id = normalized_explicit_ids[0] if normalized_explicit_ids else None
    if explicit_record_set_id and explicit_record_set_id != derived_record_set_id:
        return {
            "status": "blocked",
            "target_identity": {},
            "target_identity_fingerprint": None,
            "record_set_fingerprint_preview": derived_record_set_fingerprint,
            "blockers": ["transaction_target_identity_conflict"],
            "warnings": list(validation.get("warnings", [])) if isinstance(validation.get("warnings"), list) else [],
        }

    target_identity = {
        "record_set_id": derived_record_set_id,
        "registration_scope": {
            "canonical_rule_id": _text(candidate_record_set.get("canonical_rule_id")),
            "production_deployment_result_id": _text(candidate_record_set.get("production_deployment_result_id")),
            "production_target_id": _text(candidate_record_set.get("production_target_id")),
            "deployed_rule_id": _text(candidate_record_set.get("deployed_rule_id")),
            "telemetry_snapshot_id": _text(candidate_record_set.get("telemetry_snapshot_id")),
            "source_id": _text(candidate_record_set.get("source_id")),
            "source_type": _text(candidate_record_set.get("source_type")),
            "source_authority_class": _text(candidate_record_set.get("source_authority_class")),
        },
        "candidate_fingerprint": _candidate_fingerprint(candidate_record_set),
        "record_set_fingerprint_preview": derived_record_set_fingerprint,
        "record_count_preview": validation.get("record_count"),
    }
    target_identity_fingerprint = _hash_payload(_canonicalize_for_identity(target_identity))
    return {
        "status": "ready",
        "target_identity": target_identity,
        "target_identity_fingerprint": target_identity_fingerprint,
        "record_set_fingerprint_preview": derived_record_set_fingerprint,
        "blockers": [],
        "warnings": list(validation.get("warnings", [])) if isinstance(validation.get("warnings"), list) else [],
    }


def _build_controlled_registration_transaction_idempotency_preview(
    *,
    candidate_fingerprint: str,
    planning_gate_fingerprint: str,
    backend_plan_fingerprint: str,
    target_identity_fingerprint: str,
    planned_write_function: str,
    planned_registration_scope: Mapping[str, Any],
) -> str:
    payload = {
        "transaction_plan_schema_version": 1,
        "candidate_fingerprint": candidate_fingerprint,
        "planning_gate_fingerprint": planning_gate_fingerprint,
        "backend_plan_fingerprint": backend_plan_fingerprint,
        "target_identity_fingerprint": target_identity_fingerprint,
        "planned_write_function": planned_write_function,
        "planned_registration_scope": _canonicalize_for_identity(planned_registration_scope),
    }
    return _hash_payload(_canonicalize_for_identity(payload))


def _inspect_controlled_registration_target_state(
    transaction_plan: Mapping[str, Any],
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = Path(root)
    if not callable(load_deployed_rule_outcome_truth_record_set):
        return {
            "observation_status": "target_state_check_unavailable",
            "observation_basis": "target_state_check_unavailable",
            "read_path_available": False,
            "target_state": "target_state_unknown",
            "target_conflict_detected": False,
            "existing_target_identity_fingerprint": None,
            "existing_record_set_fingerprint": None,
            "existing_record_count": None,
            "target_present": False,
            "target_equivalent": False,
            "target_conflicting": False,
            "limitations": ["safe target-state visibility may remain unavailable"],
            "warnings": ["target_state_check_unavailable"],
        }
    if not base.exists() or not base.is_dir():
        return {
            "observation_status": "root_unavailable",
            "observation_basis": "root_unavailable",
            "read_path_available": False,
            "target_state": "target_state_unknown",
            "target_conflict_detected": False,
            "existing_target_identity_fingerprint": None,
            "existing_record_set_fingerprint": None,
            "existing_record_count": None,
            "target_present": False,
            "target_equivalent": False,
            "target_conflicting": False,
            "limitations": [
                "Target absence is confirmed only when a safe read-only lookup can establish that the exact target is not present.",
                "A missing or unavailable root is not automatically treated as confirmed target absence.",
            ],
            "warnings": ["target_state_root_unavailable"],
        }
    target_identity = transaction_plan.get("target_identity")
    if not isinstance(target_identity, Mapping):
        return {
            "observation_status": "target_state_unknown",
            "observation_basis": "target_identity_missing_for_target_state_check",
            "read_path_available": True,
            "target_state": "target_state_unknown",
            "target_conflict_detected": False,
            "existing_target_identity_fingerprint": None,
            "existing_record_set_fingerprint": None,
            "existing_record_count": None,
            "target_present": False,
            "target_equivalent": False,
            "target_conflicting": False,
            "limitations": ["target-state snapshot coverage is structural only"],
            "warnings": ["target_identity_missing_for_target_state_check"],
        }
    record_set_id = _text(target_identity.get("record_set_id"))
    expected_record_set_fingerprint = _text(target_identity.get("record_set_fingerprint_preview"))
    if not record_set_id or not expected_record_set_fingerprint:
        return {
            "observation_status": "target_state_unknown",
            "observation_basis": "target_identity_missing_for_target_state_check",
            "read_path_available": True,
            "target_state": "target_state_unknown",
            "target_conflict_detected": False,
            "existing_target_identity_fingerprint": None,
            "existing_record_set_fingerprint": None,
            "existing_record_count": None,
            "target_present": False,
            "target_equivalent": False,
            "target_conflicting": False,
            "limitations": ["target-state snapshot coverage is structural only"],
            "warnings": ["target_identity_missing_for_target_state_check"],
        }
    target_path = _record_set_path(base, record_set_id)
    if target_path.exists() and not target_path.is_file():
        return {
            "observation_status": "target_malformed",
            "observation_basis": "target_malformed",
            "read_path_available": True,
            "target_state": "target_state_unknown",
            "target_conflict_detected": False,
            "existing_target_identity_fingerprint": None,
            "existing_record_set_fingerprint": None,
            "existing_record_count": None,
            "target_present": False,
            "target_equivalent": False,
            "target_conflicting": False,
            "limitations": ["Observation errors and malformed target data are not treated as absence."],
            "warnings": ["target_state_malformed"],
        }
    if not target_path.exists():
        return {
            "observation_status": "observed",
            "observation_basis": "safe_direct_target_file_read",
            "read_path_available": True,
            "target_state": "target_absent",
            "target_conflict_detected": False,
            "existing_target_identity_fingerprint": None,
            "existing_record_set_fingerprint": None,
            "existing_record_count": 0,
            "target_present": False,
            "target_equivalent": False,
            "target_conflicting": False,
            "limitations": ["target-state snapshot coverage is structural only"],
            "warnings": [],
        }
    loaded = load_deployed_rule_outcome_truth_record_set(record_set_id, root=base)
    loaded_status = str(loaded.get("status") or "unknown")
    if loaded_status == "blocked":
        try:
            parsed_payload = json.loads(target_path.read_text(encoding="utf-8"))
        except OSError:
            parsed_payload = None
            blocked_observation_status = "target_unreadable"
            blocked_warning = "target_state_unreadable"
        except (TypeError, ValueError, json.JSONDecodeError):
            parsed_payload = None
            blocked_observation_status = "target_malformed"
            blocked_warning = "target_state_malformed"
        else:
            if isinstance(parsed_payload, Mapping):
                blocked_observation_status = "target_unreadable"
                blocked_warning = "target_state_unreadable"
            else:
                blocked_observation_status = "target_malformed"
                blocked_warning = "target_state_malformed"
        return {
            "observation_status": blocked_observation_status,
            "observation_basis": blocked_observation_status,
            "read_path_available": True,
            "target_state": "target_state_unknown",
            "target_conflict_detected": False,
            "existing_target_identity_fingerprint": None,
            "existing_record_set_fingerprint": None,
            "existing_record_count": None,
            "target_present": False,
            "target_equivalent": False,
            "target_conflicting": False,
            "limitations": ["Observation errors and malformed target data are not treated as absence."],
            "warnings": [blocked_warning],
        }
    if loaded_status != "loaded":
        return {
            "observation_status": "target_malformed" if loaded_status == "corrupt" else "target_unreadable",
            "observation_basis": "target_malformed" if loaded_status == "corrupt" else "target_unreadable",
            "read_path_available": True,
            "target_state": "target_state_unknown",
            "target_conflict_detected": False,
            "existing_target_identity_fingerprint": None,
            "existing_record_set_fingerprint": None,
            "existing_record_count": None,
            "target_present": False,
            "target_equivalent": False,
            "target_conflicting": False,
            "limitations": ["Observation errors and malformed target data are not treated as absence."],
            "warnings": ["target_state_malformed" if loaded_status == "corrupt" else "target_state_unreadable"],
        }
    loaded_record_set = loaded.get("outcome_truth_record_set")
    if not isinstance(loaded_record_set, Mapping):
        return {
            "observation_status": "target_malformed",
            "observation_basis": "target_malformed",
            "read_path_available": True,
            "target_state": "target_state_unknown",
            "target_conflict_detected": False,
            "existing_target_identity_fingerprint": None,
            "existing_record_set_fingerprint": None,
            "existing_record_count": None,
            "target_present": False,
            "target_equivalent": False,
            "target_conflicting": False,
            "limitations": ["Observation errors and malformed target data are not treated as absence."],
            "warnings": ["target_state_malformed"],
        }
    existing_record_set_fingerprint = _text(loaded_record_set.get("record_set_fingerprint"))
    existing_record_count = loaded_record_set.get("record_count")
    existing_target_identity_fingerprint = _hash_payload(
        _canonicalize_for_identity(
            {
                "record_set_id": _text(loaded_record_set.get("outcome_truth_record_set_id")),
                "registration_scope": {
                    "canonical_rule_id": _text(loaded_record_set.get("canonical_rule_id")),
                    "production_deployment_result_id": _text(loaded_record_set.get("production_deployment_result_id")),
                    "production_target_id": _text(loaded_record_set.get("production_target_id")),
                    "deployed_rule_id": _text(loaded_record_set.get("deployed_rule_id")),
                    "telemetry_snapshot_id": _text(loaded_record_set.get("telemetry_snapshot_id")),
                    "source_id": _text(loaded_record_set.get("source_id")),
                    "source_type": _text(loaded_record_set.get("source_type")),
                    "source_authority_class": _text(loaded_record_set.get("source_authority_class")),
                },
                "record_set_fingerprint_preview": existing_record_set_fingerprint,
                "record_count_preview": existing_record_count,
            }
        )
    )
    if _text(loaded_record_set.get("record_set_fingerprint")) == expected_record_set_fingerprint:
        return {
            "observation_status": "observed",
            "observation_basis": "safe_existing_root_target_lookup",
            "read_path_available": True,
            "target_state": "target_present_equivalent",
            "target_conflict_detected": False,
            "existing_target_identity_fingerprint": existing_target_identity_fingerprint,
            "existing_record_set_fingerprint": existing_record_set_fingerprint,
            "existing_record_count": existing_record_count,
            "target_present": True,
            "target_equivalent": True,
            "target_conflicting": False,
            "limitations": ["target-state snapshot coverage is structural only"],
            "warnings": [],
        }
    return {
        "observation_status": "observed",
        "observation_basis": "safe_existing_root_target_lookup",
        "read_path_available": True,
        "target_state": "target_present_conflicting",
        "target_conflict_detected": True,
        "existing_target_identity_fingerprint": existing_target_identity_fingerprint,
        "existing_record_set_fingerprint": existing_record_set_fingerprint,
        "existing_record_count": existing_record_count,
        "target_present": True,
        "target_equivalent": False,
        "target_conflicting": True,
        "limitations": ["target-state snapshot coverage is structural only"],
        "warnings": [],
    }


def _build_controlled_registration_target_state_snapshot(
    transaction_plan: Mapping[str, Any],
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    state = _inspect_controlled_registration_target_state(transaction_plan, root=root)
    snapshot = {
        "observation_status": str(state.get("observation_status") or "target_state_check_unavailable"),
        "observation_basis": str(state.get("observation_basis") or "target_state_check_unavailable"),
        "target_state": str(state.get("target_state") or "target_state_unknown"),
        "target_identity_fingerprint": _text(transaction_plan.get("target_identity_fingerprint")),
        "existing_target_identity_fingerprint": _text(state.get("existing_target_identity_fingerprint")),
        "existing_record_set_fingerprint": _text(state.get("existing_record_set_fingerprint")),
        "existing_record_count": state.get("existing_record_count"),
        "target_present": bool(state.get("target_present")),
        "target_equivalent": bool(state.get("target_equivalent")),
        "target_conflicting": bool(state.get("target_conflicting")),
        "read_path_available": bool(state.get("read_path_available")),
        "limitations": list(state.get("limitations", [])) if isinstance(state.get("limitations"), list) else [],
    }
    snapshot["target_state_snapshot_fingerprint"] = _hash_payload(_canonicalize_for_identity(snapshot))
    return snapshot


def _compute_controlled_registration_transaction_plan_fingerprint(
    transaction_plan: Mapping[str, Any],
) -> str:
    payload = {
        "transaction_plan_schema_version": transaction_plan.get("transaction_plan_schema_version"),
        "transaction_plan_type": transaction_plan.get("transaction_plan_type"),
        "candidate_fingerprint": transaction_plan.get("candidate_fingerprint"),
        "planning_gate_fingerprint": transaction_plan.get("planning_gate_fingerprint"),
        "backend_plan_fingerprint": transaction_plan.get("backend_plan_fingerprint"),
        "target_identity": transaction_plan.get("target_identity"),
        "target_identity_fingerprint": transaction_plan.get("target_identity_fingerprint"),
        "target_state_at_plan_time": transaction_plan.get("target_state_at_plan_time"),
        "target_state_observation_status": transaction_plan.get("target_state_observation_status"),
        "target_state_observation_available": transaction_plan.get("target_state_observation_available"),
        "target_state_observation_basis": transaction_plan.get("target_state_observation_basis"),
        "target_state_snapshot_fingerprint": transaction_plan.get("target_state_snapshot_fingerprint"),
        "idempotency_key_preview": transaction_plan.get("idempotency_key_preview"),
        "required_future_confirmation": transaction_plan.get("required_future_confirmation"),
        "planned_write_function": transaction_plan.get("planned_write_function"),
        "planned_write_count": transaction_plan.get("planned_write_count"),
        "planned_pre_write_verifications": transaction_plan.get("planned_pre_write_verifications"),
        "planned_post_write_verifications": transaction_plan.get("planned_post_write_verifications"),
        "planned_failure_states": transaction_plan.get("planned_failure_states"),
        "planned_recovery_requirements": transaction_plan.get("planned_recovery_requirements"),
        "planned_receipt_fields": transaction_plan.get("planned_receipt_fields"),
        "planned_execution_sequence": transaction_plan.get("planned_execution_sequence"),
        "boundary_flags": transaction_plan.get("boundary_flags"),
    }
    return _hash_payload(_canonicalize_for_identity(payload))


def _candidate_fingerprint(candidate_record_set: Any) -> str | None:
    if candidate_record_set is None:
        return None
    return _hash_payload(_canonicalize_for_identity(candidate_record_set))


def _planning_gate_fingerprint(planning_gate: Mapping[str, Any]) -> str:
    payload = {
        "planning_gate_schema_version": planning_gate.get("planning_gate_schema_version"),
        "planning_gate_type": planning_gate.get("planning_gate_type"),
        "status": planning_gate.get("status"),
        "candidate_qa_status": planning_gate.get("candidate_qa_status"),
        "candidate_structurally_ready_for_registration": planning_gate.get("candidate_structurally_ready_for_registration"),
        "prerequisite_surface_status": planning_gate.get("prerequisite_surface_status"),
        "blockers": sorted(str(item) for item in planning_gate.get("blockers", []) if str(item).strip()),
        "warnings": sorted(str(item) for item in planning_gate.get("warnings", []) if str(item).strip()),
        "recommended_action": planning_gate.get("recommended_action"),
        "planned_future_workflow_steps": list(planning_gate.get("planned_future_workflow_steps", [])),
        "required_future_safeguards": list(planning_gate.get("required_future_safeguards", [])),
        "boundary_flags": planning_gate.get("boundary_flags"),
        "candidate_qa_summary": planning_gate.get("candidate_qa_summary"),
    }
    return _hash_payload(_canonicalize_for_identity(payload))


def _backend_plan_fingerprint(backend_plan: Mapping[str, Any]) -> str:
    payload = {
        "backend_plan_identity_schema_version": backend_plan.get("backend_plan_identity_schema_version"),
        "candidate_fingerprint": backend_plan.get("candidate_fingerprint"),
        "planning_gate_fingerprint": backend_plan.get("planning_gate_fingerprint"),
        "status": backend_plan.get("status"),
        "planning_gate_status": backend_plan.get("planning_gate_status"),
        "candidate_qa_status": backend_plan.get("candidate_qa_status"),
        "candidate_structurally_ready_for_registration": backend_plan.get("candidate_structurally_ready_for_registration"),
        "backend_plan_ready_for_future_execution": backend_plan.get("backend_plan_ready_for_future_execution"),
        "required_future_confirmation": backend_plan.get("required_future_confirmation"),
        "required_future_preconditions": list(backend_plan.get("required_future_preconditions", [])),
        "planned_future_execution_steps": list(backend_plan.get("planned_future_execution_steps", [])),
        "planned_future_post_registration_checks": list(backend_plan.get("planned_future_post_registration_checks", [])),
        "required_future_safeguards": list(backend_plan.get("required_future_safeguards", [])),
        "prerequisite_surface_status": backend_plan.get("prerequisite_surface_status"),
        "blockers": sorted(str(item) for item in backend_plan.get("blockers", []) if str(item).strip()),
        "warnings": sorted(str(item) for item in backend_plan.get("warnings", []) if str(item).strip()),
        "recommended_action": backend_plan.get("recommended_action"),
        "boundary_flags": backend_plan.get("boundary_flags"),
        "candidate_qa_summary": backend_plan.get("candidate_qa_summary"),
        "identity_deterministic": backend_plan.get("identity_deterministic"),
        "identity_public_safe": backend_plan.get("identity_public_safe"),
        "candidate_fingerprint_algorithm": backend_plan.get("candidate_fingerprint_algorithm"),
        "planning_gate_fingerprint_algorithm": backend_plan.get("planning_gate_fingerprint_algorithm"),
        "backend_plan_fingerprint_algorithm": backend_plan.get("backend_plan_fingerprint_algorithm"),
    }
    return _hash_payload(_canonicalize_for_identity(payload))


def _canonicalize_for_identity(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonicalize_for_identity(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonicalize_for_identity(item) for item in value]
    if isinstance(value, tuple):
        return [_canonicalize_for_identity(item) for item in value]
    return value


def _is_sha256_fingerprint(value: Any) -> bool:
    text = _text(value)
    if text is None or not text.startswith("sha256:"):
        return False
    digest = text.split(":", 1)[1]
    return len(digest) == 64 and all(character in "0123456789abcdef" for character in digest)


def _recommended_action(status: str) -> str:
    if status == "outcome_truth_source_available":
        return "Proceed to a scoring dry-run contract only after preserving this outcome-truth binding."
    if status == "outcome_truth_source_unavailable":
        return "Design or ingest one authoritative outcome-truth source that binds to deployed execution attempts."
    if status == "outcome_truth_source_incomplete":
        return "Complete the candidate source with expected value, actual/adjudicated value, binding, window, and fingerprint."
    if status == "outcome_truth_source_unsupported":
        return "Replace unsupported substitutes with a real authoritative outcome-truth source."
    if status == "outcome_truth_source_stale":
        return "Rebuild the source plan against current readiness, spec, and telemetry evidence."
    if status == "outcome_truth_source_corrupt":
        return "Repair corrupt source evidence before any scoring design."
    return "Resolve prerequisite evidence blockers before source validation."


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _integer_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered
