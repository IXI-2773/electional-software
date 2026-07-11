"""Outcome-truth source discovery and contract validation for deployed-rule effectiveness."""

from __future__ import annotations

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
