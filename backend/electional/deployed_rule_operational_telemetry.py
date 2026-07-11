"""Authoritative operational telemetry foundation for one deployed production rule instance."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from . import certified_rule_post_deployment_acceptance as acceptance_backend
from . import certified_rule_production_deployment as deployment_backend
from . import production_deployment_adapter as adapter_backend
from .canonical_rule_runtime import _atomic_write_json, _hash_payload, _now, _read_json, _restore_json, _safe_id, load_canonical_rule
from .rule_effectiveness_analysis import _ensure_analysis_dirs
from .source_documents import SOURCE_DOCUMENT_ROOT

TELEMETRY_DIR = "deployed_rule_operational_telemetry"
EVENT_DIR = "deployed_rule_operational_telemetry/events"
SNAPSHOT_DIR = "deployed_rule_operational_telemetry/snapshots"
EVENT_INDEX = "deployed_rule_operational_event_index.json"
SNAPSHOT_INDEX = "deployed_rule_operational_snapshot_index.json"

MANIFEST_SCHEMA = "deployed_rule_operational_telemetry_manifest_v1"
EVENT_SCHEMA = "deployed_rule_operational_event_v1"
SNAPSHOT_SCHEMA = "deployed_rule_operational_snapshot_v1"
TELEMETRY_SCHEMA_VERSION = "deployed_rule_operational_telemetry_v1"

STATE_PRODUCER_ID = "authoritative_deployment_state_observer"
STATE_EVENT_TYPES = {
    "deployment_state_observed",
    "deployed_instance_active_observed",
    "deployed_instance_inactive_observed",
    "deployment_state_mismatch_observed",
    "deployment_state_corruption_observed",
}
EXECUTION_PRODUCER_ID = "deployed_rule_execution_runtime_observer"
EXECUTION_EVENT_TYPES = {
    "evaluation_completed",
    "evaluation_failed",
}
MAX_SNAPSHOT_EVENTS = 250

PUBLIC_FUNCTIONS = [
    "get_deployed_rule_operational_telemetry_manifest",
    "build_deployed_rule_operational_telemetry_workspace",
    "validate_deployed_rule_operational_telemetry_eligibility",
    "record_deployed_rule_operational_event",
    "list_deployed_rule_operational_events",
    "build_deployed_rule_operational_snapshot",
    "get_deployed_rule_operational_telemetry_health",
    "format_deployed_rule_operational_telemetry_report",
]


def get_deployed_rule_operational_telemetry_manifest(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    base = Path(root)
    state_producer = {
        "producer_id": STATE_PRODUCER_ID,
        "producer_kind": "authoritative_state_observer",
        "producer_version": "1",
        "supported_event_types": sorted(STATE_EVENT_TYPES),
        "sequence_mode": "not_observed",
        "timestamp_authority": "internal_observation_time",
        "event_statuses": ["observed", "mismatch", "corrupt", "inactive"],
    }
    state_producer["producer_fingerprint"] = _hash_payload({key: state_producer[key] for key in sorted(state_producer)})
    execution_producer = {
        "producer_id": EXECUTION_PRODUCER_ID,
        "producer_kind": "authoritative_execution_observer",
        "producer_version": "1",
        "producer_module": "deployed_rule_execution_runtime",
        "supported_event_types": sorted(EXECUTION_EVENT_TYPES),
        "supported_optional_fields": [
            "duration_ms",
            "runtime_outcome_status",
            "input_fingerprint",
            "output_fingerprint",
            "error_class",
            "public_metadata",
        ],
        "authoritative_source": "deployed_rule_execution_runtime.execute_deployed_rule",
        "timestamp_authority": "execution_observation_time",
        "event_statuses": ["completed", "failed"],
    }
    execution_producer["producer_fingerprint"] = _hash_payload({key: execution_producer[key] for key in sorted(execution_producer)})
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "telemetry_schema_version": TELEMETRY_SCHEMA_VERSION,
        "state_telemetry_available": True,
        "execution_telemetry_available": True,
        "effectiveness_evaluation_status": "not_performed",
        "producers": [state_producer, execution_producer],
        "missing_execution_producer_path": None,
        "storage_root": str(base / TELEMETRY_DIR).replace("\\", "/"),
    }
    manifest["manifest_fingerprint"] = _hash_payload(
        {
            "telemetry_schema_version": manifest["telemetry_schema_version"],
            "state_telemetry_available": manifest["state_telemetry_available"],
            "execution_telemetry_available": manifest["execution_telemetry_available"],
            "effectiveness_evaluation_status": manifest["effectiveness_evaluation_status"],
            "producers": manifest["producers"],
            "missing_execution_producer_path": manifest["missing_execution_producer_path"],
        }
    )
    return manifest


def build_deployed_rule_operational_telemetry_workspace(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    phase_9w_result_id: str | None = None,
    production_target_id: str | None = None,
    deployed_rule_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = Path(root)
    eligibility = validate_deployed_rule_operational_telemetry_eligibility(
        canonical_rule_id,
        production_deployment_result_id,
        phase_9w_result_id=phase_9w_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
        root=base,
    )
    return {
        "status": "ready" if not eligibility.get("blockers") else str(eligibility.get("status") or "blocked"),
        **{key: eligibility.get(key) for key in (
            "canonical_rule_id",
            "document_id",
            "source_revision",
            "production_target_id",
            "production_transaction_id",
            "deployed_rule_id",
            "phase_9v_result_status",
            "current_transaction_status",
            "current_verification_status",
            "state_telemetry_available",
            "execution_telemetry_available",
            "missing_execution_producer_path",
            "producer_ids",
            "execution_producer_ids",
            "manifest_fingerprint",
            "warnings",
            "blockers",
            "recommended_action",
        )},
    }


def validate_deployed_rule_operational_telemetry_eligibility(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    phase_9w_result_id: str | None = None,
    production_target_id: str | None = None,
    deployed_rule_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = Path(root)
    manifest = get_deployed_rule_operational_telemetry_manifest(root=base)
    context = _telemetry_context(
        base,
        canonical_rule_id=canonical_rule_id,
        production_deployment_result_id=production_deployment_result_id,
        phase_9w_result_id=phase_9w_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
    )
    blockers = list(context["blockers"])
    warnings = list(context["warnings"])
    status = "eligible_with_warnings" if warnings and not blockers else "eligible" if not blockers else "stale" if any("stale" in item for item in blockers) else "blocked"
    return {
        "status": status,
        "canonical_rule_id": context["deployment_result"].get("canonical_rule_id"),
        "document_id": context["deployment_result"].get("document_id"),
        "source_revision": context["deployment_result"].get("source_revision"),
        "production_target_id": context["deployment_result"].get("production_target_id"),
        "production_transaction_id": context["deployment_result"].get("production_transaction_id"),
        "deployed_rule_id": context["deployment_result"].get("deployed_rule_id"),
        "phase_9v_result_status": context["deployment_result"].get("final_status", context["deployment_loaded"].get("status", "missing")),
        "phase_9w_status": context["acceptance_result"].get("decision_status") if context["acceptance_result"] else "not_provided",
        "current_transaction_status": context["current_state"].get("transaction_state", context["current_state"].get("status", "missing")),
        "current_verification_status": context["current_state"].get("verification_status", "missing"),
        "state_telemetry_available": manifest.get("state_telemetry_available"),
        "execution_telemetry_available": manifest.get("execution_telemetry_available"),
        "missing_execution_producer_path": manifest.get("missing_execution_producer_path"),
        "producer_ids": [item.get("producer_id") for item in manifest.get("producers", []) if isinstance(item, Mapping)],
        "execution_producer_ids": [item.get("producer_id") for item in manifest.get("producers", []) if isinstance(item, Mapping) and str(item.get("producer_kind") or "") == "authoritative_execution_observer"],
        "manifest_fingerprint": manifest.get("manifest_fingerprint"),
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
        "recommended_action": _recommended_action(status),
    }


def record_deployed_rule_operational_event(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    *,
    producer_id: str,
    event_type: str,
    phase_9w_result_id: str | None = None,
    production_target_id: str | None = None,
    deployed_rule_id: str | None = None,
    duration_ms: int | None = None,
    producer_sequence: int | None = None,
    _testing_observed_at: str | None = None,
    _testing_event_id: str | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    manifest = get_deployed_rule_operational_telemetry_manifest(root=base)
    producer = _producer_definition(manifest, producer_id)
    if not isinstance(producer, Mapping):
        return {"status": "blocked", "warnings": [], "blockers": ["unknown_telemetry_producer"], "writes_performed": 0}
    if event_type not in STATE_EVENT_TYPES:
        return {"status": "blocked", "warnings": [], "blockers": ["unsupported_telemetry_event_type"], "writes_performed": 0}
    if isinstance(duration_ms, bool) or (duration_ms is not None and (not isinstance(duration_ms, int) or duration_ms < 0)):
        return {"status": "blocked", "warnings": [], "blockers": ["telemetry_duration_invalid"], "writes_performed": 0}
    if producer_sequence is not None and (isinstance(producer_sequence, bool) or not isinstance(producer_sequence, int) or producer_sequence < 0):
        return {"status": "blocked", "warnings": [], "blockers": ["telemetry_producer_sequence_invalid"], "writes_performed": 0}
    observed_at = _normalize_timestamp(_testing_observed_at or _now())
    if not observed_at:
        return {"status": "blocked", "warnings": [], "blockers": ["telemetry_timestamp_invalid"], "writes_performed": 0}

    context = _telemetry_context(
        base,
        canonical_rule_id=canonical_rule_id,
        production_deployment_result_id=production_deployment_result_id,
        phase_9w_result_id=phase_9w_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
    )
    if context["blockers"]:
        return {"status": "blocked", "warnings": list(context["warnings"]), "blockers": list(context["blockers"]), "writes_performed": 0}
    derived_event_type, event_status = _derived_state_event_type(context)
    if event_type != derived_event_type:
        return {"status": "blocked", "warnings": [], "blockers": ["telemetry_event_type_not_supported_for_current_state"], "writes_performed": 0}

    event = {
        "schema_version": EVENT_SCHEMA,
        "telemetry_schema_version": TELEMETRY_SCHEMA_VERSION,
        "producer_id": producer_id,
        "producer_fingerprint": producer.get("producer_fingerprint"),
        "producer_version": producer.get("producer_version"),
        "event_type": event_type,
        "event_status": event_status,
        "observed_at": observed_at,
        "producer_sequence": producer_sequence,
        "duration_ms": duration_ms,
        "canonical_rule_id": context["deployment_result"].get("canonical_rule_id"),
        "canonical_rule_fingerprint": context["source_rule"].get("rule_fingerprint"),
        "deployed_rule_id": context["deployment_result"].get("deployed_rule_id"),
        "deployed_rule_fingerprint": context["deployed_rule"].get("rule_fingerprint"),
        "production_deployment_result_id": production_deployment_result_id,
        "production_deployment_result_fingerprint": context["deployment_result"].get("result_fingerprint"),
        "production_target_id": context["deployment_result"].get("production_target_id"),
        "production_transaction_id": context["deployment_result"].get("production_transaction_id"),
        "document_id": context["deployment_result"].get("document_id"),
        "source_revision": context["deployment_result"].get("source_revision"),
        "certification_id": _resolved_certification_id(context),
        "certification_fingerprint": context["deployment_result"].get("certification_fingerprint") or context["deployment_plan"].get("certification_fingerprint"),
        "production_authorization_result_id": context["deployment_result"].get("production_authorization_result_id"),
        "deployment_package_fingerprint": context["deployment_result"].get("deployment_package_fingerprint"),
        "committed_production_state_fingerprint": context["deployment_result"].get("committed_production_state_fingerprint"),
        "current_production_state_fingerprint": context["current_state"].get("production_state_fingerprint"),
        "current_transaction_status": context["current_state"].get("transaction_state"),
        "current_verification_status": context["current_state"].get("verification_status"),
        "canonical_binding_status": "matched",
        "deployment_binding_status": "matched",
        "effectiveness_evaluation_status": "not_performed",
    }
    event_id = _testing_event_id or _event_id(event)
    event["event_id"] = event_id
    event["event_fingerprint"] = _event_fingerprint(event)
    validation = _validate_event_payload(event, manifest, allow_event_id_override=_testing_event_id is not None)
    if validation:
        return {"status": "blocked", "warnings": [], "blockers": validation, "writes_performed": 0}

    path = _event_path(base, event_id)
    existing = _read_json(path)
    if isinstance(existing, Mapping):
        if str(existing.get("event_fingerprint") or "") == str(event.get("event_fingerprint") or ""):
            index_ok = _index_contains_event(base, event_id, context["deployment_result"].get("deployed_rule_id"), production_deployment_result_id)
            return {
                "status": "already_recorded" if index_ok else "corrupt",
                "event_id": event_id,
                "writes_performed": 0,
                "warnings": [],
                "blockers": [] if index_ok else ["telemetry_event_index_missing_entry"],
            }
        return {"status": "conflict", "event_id": event_id, "writes_performed": 0, "warnings": [], "blockers": ["telemetry_event_id_semantic_conflict"]}
    before_event = _read_json(path)
    before_index = _read_json(base / "indexes" / EVENT_INDEX)
    try:
        _atomic_write_json(path, event)
        _update_event_index(base)
    except Exception:
        orphaned = isinstance(_read_json(path), Mapping)
        _restore_json(path, before_event)
        _restore_json(base / "indexes" / EVENT_INDEX, before_index)
        return {
            "status": "corrupt",
            "event_id": event_id,
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["telemetry_event_write_failure_or_orphaned_record" if orphaned else "telemetry_event_write_failure"],
        }
    return {
        "status": "recorded",
        "event_id": event_id,
        "writes_performed": 1,
        "producer_id": producer_id,
        "event_type": event_type,
        "deployed_rule_id": event.get("deployed_rule_id"),
        "production_deployment_result_id": production_deployment_result_id,
        "event_fingerprint": event.get("event_fingerprint"),
        "warnings": [],
        "blockers": [],
    }


def record_deployed_rule_execution_event(
    execution_envelope: Mapping[str, Any],
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
    _testing_observed_at: str | None = None,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    manifest = get_deployed_rule_operational_telemetry_manifest(root=base)
    producer = _producer_definition(manifest, EXECUTION_PRODUCER_ID)
    if not isinstance(producer, Mapping):
        return {"status": "blocked", "warnings": [], "blockers": ["unknown_telemetry_producer"], "writes_performed": 0}
    if not isinstance(execution_envelope, Mapping):
        return {"status": "blocked", "warnings": [], "blockers": ["execution_envelope_invalid"], "writes_performed": 0}
    event_type = _execution_event_type(execution_envelope)
    if event_type not in EXECUTION_EVENT_TYPES:
        return {"status": "blocked", "warnings": [], "blockers": ["unsupported_execution_telemetry_event_type"], "writes_performed": 0}
    observed_at = _normalize_timestamp(_testing_observed_at or _now())
    if not observed_at:
        return {"status": "blocked", "warnings": [], "blockers": ["telemetry_timestamp_invalid"], "writes_performed": 0}
    public_metadata = {"execution_status": str(execution_envelope.get("execution_status") or "")}
    event = {
        "schema_version": EVENT_SCHEMA,
        "telemetry_schema_version": TELEMETRY_SCHEMA_VERSION,
        "producer_id": EXECUTION_PRODUCER_ID,
        "producer_fingerprint": producer.get("producer_fingerprint"),
        "producer_version": producer.get("producer_version"),
        "event_type": event_type,
        "event_status": "completed" if event_type == "evaluation_completed" else "failed",
        "observed_at": observed_at,
        "producer_sequence": None,
        "duration_ms": execution_envelope.get("duration_ms"),
        "runtime_outcome_status": execution_envelope.get("runtime_outcome_status"),
        "input_fingerprint": execution_envelope.get("input_fingerprint"),
        "output_fingerprint": execution_envelope.get("output_fingerprint"),
        "error_class": execution_envelope.get("error_class"),
        "public_metadata": public_metadata,
        "canonical_rule_id": execution_envelope.get("canonical_rule_id"),
        "canonical_rule_fingerprint": execution_envelope.get("canonical_rule_fingerprint"),
        "deployed_rule_id": execution_envelope.get("deployed_rule_id"),
        "deployed_rule_fingerprint": execution_envelope.get("deployed_rule_fingerprint"),
        "production_deployment_result_id": execution_envelope.get("production_deployment_result_id"),
        "production_deployment_result_fingerprint": execution_envelope.get("production_deployment_result_fingerprint") or execution_envelope.get("deployment_result_fingerprint"),
        "production_target_id": execution_envelope.get("production_target_id"),
        "production_transaction_id": execution_envelope.get("production_transaction_id"),
        "document_id": execution_envelope.get("document_id"),
        "source_revision": execution_envelope.get("source_revision"),
        "certification_id": execution_envelope.get("certification_id"),
        "certification_fingerprint": execution_envelope.get("certification_fingerprint"),
        "production_authorization_result_id": execution_envelope.get("production_authorization_result_id"),
        "deployment_package_fingerprint": execution_envelope.get("deployment_package_fingerprint"),
        "committed_production_state_fingerprint": execution_envelope.get("committed_production_state_fingerprint"),
        "current_production_state_fingerprint": execution_envelope.get("current_production_state_fingerprint") or execution_envelope.get("committed_production_state_fingerprint"),
        "current_transaction_status": execution_envelope.get("current_transaction_status") or "committed",
        "current_verification_status": execution_envelope.get("current_verification_status") or "verified_committed",
        "canonical_binding_status": "matched",
        "deployment_binding_status": "matched",
        "effectiveness_evaluation_status": "not_performed",
    }
    return _record_event_payload(base, event, manifest=manifest)


def list_deployed_rule_operational_events(
    deployed_rule_id: str,
    production_deployment_result_id: str,
    *,
    event_type: str | None = None,
    producer_id: str | None = None,
    start_timestamp: str | None = None,
    end_timestamp: str | None = None,
    max_results: int = 100,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = Path(root)
    if not _text(deployed_rule_id) or not _text(production_deployment_result_id):
        return {"status": "blocked", "items": [], "warnings": [], "blockers": ["deployed_rule_id_and_deployment_result_id_required"]}
    if isinstance(max_results, bool) or not isinstance(max_results, int) or max_results <= 0:
        return {"status": "blocked", "items": [], "warnings": [], "blockers": ["max_results_invalid"]}
    start_norm = _normalize_timestamp(start_timestamp) if start_timestamp else None
    end_norm = _normalize_timestamp(end_timestamp) if end_timestamp else None
    if (start_timestamp and not start_norm) or (end_timestamp and not end_norm):
        return {"status": "blocked", "items": [], "warnings": [], "blockers": ["telemetry_timestamp_filter_invalid"]}

    entries, event_index_issues = _load_event_index_entries(base)
    if event_index_issues:
        return {
            "status": "corrupt",
            "deployed_rule_id": deployed_rule_id,
            "production_deployment_result_id": production_deployment_result_id,
            "total_matching_event_count": 0,
            "returned_event_count": 0,
            "items": [],
            "invalid_or_corrupt_records": [],
            "warnings": [],
            "blockers": list(event_index_issues),
            "writes_performed": 0,
        }
    matching = []
    corrupt_entries = []
    for entry in entries:
        if str(entry.get("deployed_rule_id") or "") != deployed_rule_id:
            continue
        if str(entry.get("production_deployment_result_id") or "") != production_deployment_result_id:
            continue
        if event_type and str(entry.get("event_type") or "") != event_type:
            continue
        if producer_id and str(entry.get("producer_id") or "") != producer_id:
            continue
        observed_at = str(entry.get("observed_at") or "")
        if start_norm and observed_at < start_norm:
            continue
        if end_norm and observed_at > end_norm:
            continue
        payload = _read_json(base / str(entry.get("relative_path") or ""))
        if not isinstance(payload, Mapping):
            corrupt_entries.append({"event_id": entry.get("event_id"), "reason": "index_to_file_missing"})
            continue
        validation = _validate_event_payload(payload, get_deployed_rule_operational_telemetry_manifest(root=base))
        if validation:
            corrupt_entries.append({"event_id": payload.get("event_id"), "reason": validation[0]})
            continue
        matching.append(dict(payload))
    matching.sort(key=lambda item: (
        str(item.get("observed_at") or ""),
        str(item.get("producer_id") or ""),
        -1 if item.get("producer_sequence") is None else int(item.get("producer_sequence") or 0),
        str(item.get("event_id") or ""),
    ))
    total_matching = len(matching)
    return {
        "status": "listed",
        "deployed_rule_id": deployed_rule_id,
        "production_deployment_result_id": production_deployment_result_id,
        "total_matching_event_count": total_matching,
        "returned_event_count": min(total_matching, max_results),
        "items": matching[:max_results],
        "invalid_or_corrupt_records": corrupt_entries,
        "warnings": [],
        "blockers": [],
    }


def build_deployed_rule_operational_snapshot(
    deployed_rule_id: str,
    production_deployment_result_id: str,
    *,
    start_timestamp: str | None = None,
    end_timestamp: str | None = None,
    max_events: int = MAX_SNAPSHOT_EVENTS,
    phase_9w_result_id: str | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    if isinstance(max_events, bool) or not isinstance(max_events, int) or max_events <= 0:
        return {"status": "blocked", "warnings": [], "blockers": ["snapshot_max_events_invalid"]}
    deployment_loaded = deployment_backend.load_certified_rule_production_deployment_result(production_deployment_result_id, root=base)
    deployment_result = deployment_loaded.get("production_deployment_result") if isinstance(deployment_loaded.get("production_deployment_result"), Mapping) else {}
    if str(deployment_result.get("deployed_rule_id") or "") != deployed_rule_id:
        return {"status": "blocked", "warnings": [], "blockers": ["snapshot_deployed_rule_binding_mismatch"]}
    listing = list_deployed_rule_operational_events(
        deployed_rule_id,
        production_deployment_result_id,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        max_results=max_events + 1,
        root=base,
    )
    if str(listing.get("status") or "") != "listed":
        return listing
    total_matching = int(listing.get("total_matching_event_count") or 0)
    if total_matching > max_events:
        return {
            "status": "blocked",
            "deployed_rule_id": deployed_rule_id,
            "production_deployment_result_id": production_deployment_result_id,
            "warnings": [],
            "blockers": ["snapshot_event_limit_exceeded"],
            "total_matching_event_count": total_matching,
            "supported_snapshot_maximum": max_events,
        }
    events = list(listing.get("items", []))
    manifest = get_deployed_rule_operational_telemetry_manifest(root=base)
    invalid_records = list(listing.get("invalid_or_corrupt_records", []))
    valid_events = [item for item in events if not _validate_event_payload(item, manifest)]
    execution_events = [item for item in valid_events if str(item.get("producer_id") or "") == EXECUTION_PRODUCER_ID]
    completed_execution_events = [item for item in execution_events if str(item.get("event_type") or "") == "evaluation_completed"]
    failed_execution_events = [item for item in execution_events if str(item.get("event_type") or "") == "evaluation_failed"]
    duration_values = [int(item.get("duration_ms") or 0) for item in execution_events if item.get("duration_ms") is not None]
    snapshot = {
        "schema_version": SNAPSHOT_SCHEMA,
        "telemetry_schema_version": TELEMETRY_SCHEMA_VERSION,
        "snapshot_id": _snapshot_id(
            deployed_rule_id=deployed_rule_id,
            production_deployment_result_id=production_deployment_result_id,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            manifest_fingerprint=str(manifest.get("manifest_fingerprint") or ""),
            event_ids=[str(item.get("event_id") or "") for item in valid_events],
            producer_fingerprints=[str(item.get("producer_fingerprint") or "") for item in valid_events],
        ),
        "deployed_rule_id": deployed_rule_id,
        "production_deployment_result_id": production_deployment_result_id,
        "phase_9w_result_id": phase_9w_result_id,
        "canonical_rule_id": deployment_result.get("canonical_rule_id"),
        "production_target_id": deployment_result.get("production_target_id"),
        "production_transaction_id": deployment_result.get("production_transaction_id"),
        "observation_start": start_timestamp,
        "observation_end": end_timestamp,
        "manifest_fingerprint": manifest.get("manifest_fingerprint"),
        "validated_event_ids": [str(item.get("event_id") or "") for item in valid_events],
        "validated_event_count": len(valid_events),
        "total_matching_event_count": total_matching,
        "invalid_event_count": len(invalid_records),
        "corrupt_event_count": len(invalid_records),
        "stale_historical_event_count": 0,
        "current_binding_mismatch_count": 0,
        "producer_ids": sorted({str(item.get("producer_id") or "") for item in valid_events}),
        "producer_fingerprints": sorted({str(item.get("producer_fingerprint") or "") for item in valid_events}),
        "sequence_gap_count_by_producer": _sequence_gap_count_by_producer(valid_events),
        "execution_event_count": len(execution_events),
        "execution_telemetry_available": bool(_producer_definition(manifest, EXECUTION_PRODUCER_ID)),
        "effectiveness_evaluation_status": "not_performed",
        "metric_availability": {
            "execution_completion_count": "available" if execution_events else "execution_producer_available_no_events_observed",
            "execution_failure_count": "available" if execution_events else "execution_producer_available_no_events_observed",
            "execution_skip_count": "unsupported_by_producer",
            "fallback_count": "unsupported_by_producer",
            "duration_statistics": "available" if duration_values else "execution_producer_available_no_events_observed",
        },
        "execution_completion_count": len(completed_execution_events),
        "execution_failure_count": len(failed_execution_events),
        "execution_skip_count": 0,
        "fallback_count": 0,
        "duration_summary_ms": {
            "count": len(duration_values),
            "min": min(duration_values) if duration_values else None,
            "max": max(duration_values) if duration_values else None,
        },
        "invalid_or_corrupt_reasons": sorted({str(item.get("reason") or "unknown") for item in invalid_records}),
        "snapshot_completeness_status": "complete",
    }
    snapshot["snapshot_fingerprint"] = _snapshot_fingerprint(snapshot)
    path = _snapshot_path(base, str(snapshot["snapshot_id"]))
    existing = _read_json(path)
    if isinstance(existing, Mapping):
        if str(existing.get("snapshot_fingerprint") or "") == str(snapshot.get("snapshot_fingerprint") or ""):
            return {"status": "already_recorded", "snapshot_id": snapshot["snapshot_id"], "writes_performed": 0, **_snapshot_summary(snapshot)}
        return {"status": "conflict", "snapshot_id": snapshot["snapshot_id"], "writes_performed": 0, "warnings": [], "blockers": ["telemetry_snapshot_id_semantic_conflict"]}
    before_snapshot = _read_json(path)
    before_index = _read_json(base / "indexes" / SNAPSHOT_INDEX)
    try:
        _atomic_write_json(path, snapshot)
        _update_snapshot_index(base)
    except Exception:
        orphaned = isinstance(_read_json(path), Mapping)
        _restore_json(path, before_snapshot)
        _restore_json(base / "indexes" / SNAPSHOT_INDEX, before_index)
        return {"status": "corrupt", "snapshot_id": snapshot["snapshot_id"], "writes_performed": 0, "warnings": [], "blockers": ["telemetry_snapshot_write_failure_or_orphaned_record" if orphaned else "telemetry_snapshot_write_failure"]}
    return {"status": "recorded", "snapshot_id": snapshot["snapshot_id"], "writes_performed": 1, **_snapshot_summary(snapshot)}


def get_deployed_rule_operational_telemetry_health(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    *,
    phase_9w_result_id: str | None = None,
    production_target_id: str | None = None,
    deployed_rule_id: str | None = None,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = Path(root)
    manifest = get_deployed_rule_operational_telemetry_manifest(root=base)
    context = _telemetry_context(
        base,
        canonical_rule_id=canonical_rule_id,
        production_deployment_result_id=production_deployment_result_id,
        phase_9w_result_id=phase_9w_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
    )
    warnings = list(context["warnings"])
    blockers = list(context["blockers"])
    event_index_entries, event_index_issues = _load_event_index_entries(base)
    snapshot_index_entries, snapshot_index_issues = _load_snapshot_index_entries(base)
    blockers.extend(event_index_issues)
    blockers.extend(snapshot_index_issues)
    orphan_event_files = _orphan_files(base / EVENT_DIR, {str(item.get("relative_path") or "") for item in event_index_entries})
    orphan_snapshot_files = _orphan_files(base / SNAPSHOT_DIR, {str(item.get("relative_path") or "") for item in snapshot_index_entries})
    event_index_missing = []
    for path in sorted((base / EVENT_DIR).glob("*.json")):
        payload = _read_json(path)
        if not isinstance(payload, Mapping):
            blockers.append("telemetry_event_unreadable")
            continue
        if _validate_event_payload(payload, manifest):
            blockers.append("telemetry_event_invalid")
        if not any(str(item.get("event_id") or "") == str(payload.get("event_id") or "") for item in event_index_entries):
            warnings.append("telemetry_event_file_missing_from_index")
            event_index_missing.append(str(payload.get("event_id") or ""))
    for entry in event_index_entries:
        payload = _read_json(base / str(entry.get("relative_path") or ""))
        if not isinstance(payload, Mapping):
            blockers.append("telemetry_event_index_points_to_missing_file")
            continue
        if str(payload.get("event_id") or "") != str(entry.get("event_id") or ""):
            blockers.append("telemetry_event_index_identity_mismatch")
    for entry in snapshot_index_entries:
        payload = _read_json(base / str(entry.get("relative_path") or ""))
        if not isinstance(payload, Mapping):
            blockers.append("telemetry_snapshot_index_points_to_missing_file")
            continue
        if str(payload.get("snapshot_id") or "") != str(entry.get("snapshot_id") or ""):
            blockers.append("telemetry_snapshot_index_identity_mismatch")
        for event_id in payload.get("validated_event_ids", []):
            if not isinstance(_find_event_by_id(base, str(event_id or "")), Mapping):
                blockers.append("telemetry_snapshot_references_missing_event")
                break
    if orphan_event_files:
        warnings.append("telemetry_orphan_event_file_present")
    if orphan_snapshot_files:
        warnings.append("telemetry_orphan_snapshot_file_present")
    status = "healthy" if not blockers and not warnings else "warning" if warnings and not blockers else "blocked"
    return {
        "status": status,
        "canonical_rule_id": context["deployment_result"].get("canonical_rule_id"),
        "deployed_rule_id": context["deployment_result"].get("deployed_rule_id"),
        "production_deployment_result_id": production_deployment_result_id,
        "production_target_id": context["deployment_result"].get("production_target_id"),
        "production_transaction_id": context["deployment_result"].get("production_transaction_id"),
        "manifest_fingerprint": manifest.get("manifest_fingerprint"),
        "state_telemetry_available": manifest.get("state_telemetry_available"),
        "execution_telemetry_available": manifest.get("execution_telemetry_available"),
        "execution_producer_ids": [item.get("producer_id") for item in manifest.get("producers", []) if isinstance(item, Mapping) and str(item.get("producer_kind") or "") == "authoritative_execution_observer"],
        "event_count": len(_load_all(base / EVENT_DIR)),
        "snapshot_count": len(_load_all(base / SNAPSHOT_DIR)),
        "orphan_event_file_count": len(orphan_event_files),
        "orphan_snapshot_file_count": len(orphan_snapshot_files),
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
        "recommended_action": _recommended_action(status),
    }


def format_deployed_rule_operational_telemetry_report(
    canonical_rule_id: str,
    production_deployment_result_id: str,
    *,
    phase_9w_result_id: str | None = None,
    production_target_id: str | None = None,
    deployed_rule_id: str | None = None,
    start_timestamp: str | None = None,
    end_timestamp: str | None = None,
    event_type: str | None = None,
    producer_id: str | None = None,
    max_results: int = 100,
    public_safe: bool = True,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    workspace = build_deployed_rule_operational_telemetry_workspace(
        canonical_rule_id,
        production_deployment_result_id,
        phase_9w_result_id=phase_9w_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
        root=root,
    )
    health = get_deployed_rule_operational_telemetry_health(
        canonical_rule_id,
        production_deployment_result_id,
        phase_9w_result_id=phase_9w_result_id,
        production_target_id=production_target_id,
        deployed_rule_id=deployed_rule_id,
        root=root,
    )
    listing = list_deployed_rule_operational_events(
        workspace.get("deployed_rule_id") or str(deployed_rule_id or ""),
        production_deployment_result_id,
        event_type=event_type,
        producer_id=producer_id,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        max_results=max_results,
        root=root,
    )
    lines = [
        "Deployed Rule Operational Telemetry",
        f"Canonical Rule ID: {workspace.get('canonical_rule_id', 'unknown')}",
        f"Deployed Rule ID: {workspace.get('deployed_rule_id', 'unknown')}",
        f"Production Deployment Result ID: {production_deployment_result_id}",
        f"Production Transaction ID: {workspace.get('production_transaction_id', 'unknown')}",
        f"Phase 9V Deployment Status: {workspace.get('phase_9v_result_status', workspace.get('status', 'unknown'))}",
        f"Current Transaction Status: {workspace.get('current_transaction_status', 'unknown')}",
        f"Current Verification Status: {workspace.get('current_verification_status', 'unknown')}",
        f"State Telemetry Available: {workspace.get('state_telemetry_available', False)}",
        f"Execution Telemetry Available: {workspace.get('execution_telemetry_available', False)}",
        f"Execution Producer IDs: {', '.join(workspace.get('execution_producer_ids', [])) if isinstance(workspace.get('execution_producer_ids'), list) else 'none'}",
        f"Producer IDs: {', '.join(workspace.get('producer_ids', [])) if isinstance(workspace.get('producer_ids'), list) else 'none'}",
        f"Total Matching Event Count: {listing.get('total_matching_event_count', 0)}",
        f"Returned Event Count: {listing.get('returned_event_count', 0)}",
        f"Telemetry Health: {health.get('status', 'unknown')}",
        "Effectiveness evaluation remains not_performed.",
        "Phase 9W acceptance is not used as effectiveness evidence.",
    ]
    if manifest_execution_available := workspace.get("execution_telemetry_available"):
        if int(listing.get("total_matching_event_count") or 0) == 0:
            lines.append("Execution Telemetry Status: execution_producer_available_no_events_observed")
    if workspace.get("warnings"):
        lines.append("Warnings: " + ", ".join(str(item) for item in workspace.get("warnings", [])))
    if workspace.get("blockers"):
        lines.append("Blockers: " + ", ".join(str(item) for item in workspace.get("blockers", [])))
    if health.get("warnings"):
        lines.append("Health Warnings: " + ", ".join(str(item) for item in health.get("warnings", [])))
    if health.get("blockers"):
        lines.append("Health Blockers: " + ", ".join(str(item) for item in health.get("blockers", [])))
    return "\n".join(lines)


def _telemetry_context(
    base: Path,
    *,
    canonical_rule_id: str,
    production_deployment_result_id: str,
    phase_9w_result_id: str | None,
    production_target_id: str | None,
    deployed_rule_id: str | None,
) -> dict[str, Any]:
    warnings: list[str] = []
    blockers: list[str] = []
    deployment_result_path = deployment_backend._result_path(base, production_deployment_result_id)
    acceptance_result_path = acceptance_backend._result_path(base, phase_9w_result_id) if phase_9w_result_id else None
    if not deployment_result_path.exists() or (acceptance_result_path is not None and not acceptance_result_path.exists()):
        if not deployment_result_path.exists():
            blockers.extend(
                [
                    "phase_9v_result_missing",
                    "phase_9v_plan_missing",
                    "phase_9v_receipt_missing",
                    "production_transaction_state_missing",
                    "canonical_source_rule_missing_or_inactive",
                    "deployed_rule_missing",
                ]
            )
        if acceptance_result_path is not None and not acceptance_result_path.exists():
            blockers.append("phase_9w_result_missing")
        return {
            "deployment_loaded": {"status": "missing"},
            "deployment_result": {},
            "deployment_plan": {},
            "deployment_receipt": {},
            "acceptance_result": None,
            "current_state": {"status": "missing"},
            "source_rule": {},
            "deployed_rule": {},
            "warnings": _dedupe(warnings),
            "blockers": _dedupe(blockers),
        }
    deployment_loaded = deployment_backend.load_certified_rule_production_deployment_result(production_deployment_result_id, root=base)
    deployment_result = deployment_loaded.get("production_deployment_result") if isinstance(deployment_loaded.get("production_deployment_result"), Mapping) else {}
    deployment_plan = _read_json(deployment_backend._plan_path(base, str(deployment_result.get("production_deployment_plan_id") or ""))) if deployment_result else None
    deployment_receipt = deployment_backend._find_receipt_for_result(base, production_deployment_result_id) if deployment_result else None
    if not deployment_result:
        blockers.append("phase_9v_result_missing")
    else:
        if str(deployment_result.get("final_status") or "") != "completed":
            blockers.append("phase_9v_result_not_completed")
        if deployment_backend._result_is_stale(base, deployment_result):
            blockers.append("phase_9v_result_stale")
        if str(deployment_result.get("canonical_rule_id") or "") != canonical_rule_id:
            blockers.append("canonical_rule_id_mismatch")
        if production_target_id and str(deployment_result.get("production_target_id") or "") != production_target_id:
            blockers.append("production_target_id_mismatch")
        if deployed_rule_id and str(deployment_result.get("deployed_rule_id") or "") != deployed_rule_id:
            blockers.append("deployed_rule_id_mismatch")
    if not isinstance(deployment_plan, Mapping):
        blockers.append("phase_9v_plan_missing")
    if not isinstance(deployment_receipt, Mapping):
        blockers.append("phase_9v_receipt_missing")
    elif str(deployment_receipt.get("result_fingerprint") or "") != str(deployment_result.get("result_fingerprint") or ""):
        blockers.append("phase_9v_receipt_fingerprint_mismatch")

    acceptance_result = None
    if phase_9w_result_id:
        acceptance_loaded = acceptance_backend.load_certified_rule_post_deployment_acceptance_result(phase_9w_result_id, root=base)
        acceptance_result = acceptance_loaded.get("post_deployment_acceptance_result") if isinstance(acceptance_loaded.get("post_deployment_acceptance_result"), Mapping) else None
        if not isinstance(acceptance_result, Mapping):
            blockers.append("phase_9w_result_missing")
        elif str(acceptance_result.get("production_deployment_result_id") or "") != production_deployment_result_id:
            blockers.append("phase_9w_result_binding_mismatch")

    current_state = adapter_backend.read_production_deployment_state(
        str(deployment_result.get("production_target_id") or ""),
        transaction_id=str(deployment_result.get("production_transaction_id") or ""),
        root=base,
    ) if deployment_result else {"status": "missing"}
    if str(current_state.get("status") or "") != "loaded":
        blockers.append("production_transaction_state_missing")
    else:
        if str(current_state.get("transaction_id") or "") != str(deployment_result.get("production_transaction_id") or ""):
            blockers.append("production_transaction_id_mismatch")
        if str(current_state.get("deployed_rule_id") or "") != str(deployment_result.get("deployed_rule_id") or ""):
            blockers.append("deployed_rule_id_mismatch")
        if str(current_state.get("canonical_rule_id") or "") != str(deployment_result.get("canonical_rule_id") or ""):
            blockers.append("current_canonical_binding_mismatch")

    source_loaded = load_canonical_rule(str(deployment_result.get("canonical_rule_id") or ""), require_active=True, root=base) if deployment_result else {"status": "not_found"}
    source_rule = source_loaded.get("rule") if isinstance(source_loaded.get("rule"), Mapping) else {}
    if str(source_loaded.get("status") or "") != "loaded":
        blockers.append("canonical_source_rule_missing_or_inactive")
    elif str(source_rule.get("rule_fingerprint") or "") != str(deployment_result.get("canonical_rule_fingerprint") or ""):
        blockers.append("canonical_source_rule_fingerprint_mismatch")

    deployed_loaded = load_canonical_rule(str(deployment_result.get("deployed_rule_id") or ""), require_active=False, root=base) if deployment_result else {"status": "not_found"}
    deployed_rule = deployed_loaded.get("rule") if isinstance(deployed_loaded.get("rule"), Mapping) else {}
    if str(deployed_loaded.get("status") or "") == "not_found":
        blockers.append("deployed_rule_missing")
    elif str(deployed_rule.get("source_canonical_rule_id") or "") != str(deployment_result.get("canonical_rule_id") or ""):
        blockers.append("deployed_rule_canonical_binding_mismatch")

    return {
        "deployment_loaded": deployment_loaded,
        "deployment_result": deployment_result,
        "deployment_plan": deployment_plan if isinstance(deployment_plan, Mapping) else {},
        "deployment_receipt": deployment_receipt if isinstance(deployment_receipt, Mapping) else {},
        "acceptance_result": acceptance_result,
        "current_state": current_state if isinstance(current_state, Mapping) else {},
        "source_rule": source_rule,
        "deployed_rule": deployed_rule,
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
    }


def _producer_definition(manifest: Mapping[str, Any], producer_id: str) -> Mapping[str, Any] | None:
    for item in manifest.get("producers", []):
        if isinstance(item, Mapping) and str(item.get("producer_id") or "") == producer_id:
            return item
    return None


def _resolved_certification_id(context: Mapping[str, Any]) -> str:
    deployment_result = context.get("deployment_result") if isinstance(context.get("deployment_result"), Mapping) else {}
    deployment_plan = context.get("deployment_plan") if isinstance(context.get("deployment_plan"), Mapping) else {}
    explicit = _text(deployment_result.get("certification_id")) or _text(deployment_plan.get("certification_id"))
    if explicit:
        return explicit
    fingerprint = _text(deployment_result.get("certification_fingerprint")) or _text(deployment_plan.get("certification_fingerprint"))
    if fingerprint:
        return "certification_from_" + _hash_payload({"certification_fingerprint": fingerprint})[7:23]
    return ""


def _derived_state_event_type(context: Mapping[str, Any]) -> tuple[str, str]:
    state = context.get("current_state") if isinstance(context.get("current_state"), Mapping) else {}
    deployed = context.get("deployed_rule") if isinstance(context.get("deployed_rule"), Mapping) else {}
    blockers = list(context.get("blockers", []))
    if any("corrupt" in item for item in blockers):
        return "deployment_state_corruption_observed", "corrupt"
    if any("mismatch" in item for item in blockers):
        return "deployment_state_mismatch_observed", "mismatch"
    if str(deployed.get("status") or deployed.get("rule_status") or deployed.get("status")) == "inactive" or str(state.get("verification_status") or "") != "verified_committed":
        return "deployed_instance_inactive_observed", "inactive"
    return "deployment_state_observed", "observed"


def _validate_event_payload(
    event: Mapping[str, Any],
    manifest: Mapping[str, Any],
    *,
    allow_event_id_override: bool = False,
) -> list[str]:
    blockers: list[str] = []
    required_text_fields = (
        "event_id",
        "event_fingerprint",
        "producer_id",
        "producer_fingerprint",
        "producer_version",
        "event_type",
        "event_status",
        "observed_at",
        "canonical_rule_id",
        "canonical_rule_fingerprint",
        "deployed_rule_id",
        "deployed_rule_fingerprint",
        "production_deployment_result_id",
        "production_deployment_result_fingerprint",
        "production_target_id",
        "production_transaction_id",
        "document_id",
        "certification_id",
        "certification_fingerprint",
        "production_authorization_result_id",
        "deployment_package_fingerprint",
        "committed_production_state_fingerprint",
        "current_production_state_fingerprint",
    )
    if str(event.get("schema_version") or "") != EVENT_SCHEMA:
        blockers.append("telemetry_event_schema_unsupported")
    producer = _producer_definition(manifest, str(event.get("producer_id") or ""))
    if not isinstance(producer, Mapping):
        blockers.append("telemetry_event_unknown_producer")
    else:
        if str(event.get("producer_fingerprint") or "") != str(producer.get("producer_fingerprint") or ""):
            blockers.append("telemetry_event_producer_fingerprint_mismatch")
        if str(event.get("event_type") or "") not in set(producer.get("supported_event_types", [])):
            blockers.append("telemetry_event_type_unsupported_by_producer")
    for field in required_text_fields:
        if not _text(event.get(field)):
            blockers.append(f"{field}_required")
    if isinstance(event.get("source_revision"), bool) or not isinstance(event.get("source_revision"), int) or int(event.get("source_revision") or 0) <= 0:
        blockers.append("telemetry_event_source_revision_invalid")
    if event.get("duration_ms") is not None and (isinstance(event.get("duration_ms"), bool) or not isinstance(event.get("duration_ms"), int) or int(event.get("duration_ms") or 0) < 0):
        blockers.append("telemetry_event_duration_invalid")
    if event.get("producer_sequence") is not None and (isinstance(event.get("producer_sequence"), bool) or not isinstance(event.get("producer_sequence"), int) or int(event.get("producer_sequence") or 0) < 0):
        blockers.append("telemetry_event_producer_sequence_invalid")
    if not _normalize_timestamp(str(event.get("observed_at") or "")):
        blockers.append("telemetry_event_timestamp_invalid")
    if str(event.get("event_fingerprint") or "") != _event_fingerprint(event):
        blockers.append("telemetry_event_fingerprint_mismatch")
    return _dedupe(blockers)


def _load_event_index_entries(base: Path) -> tuple[list[dict[str, Any]], list[str]]:
    return _load_index_entries(base / "indexes" / EVENT_INDEX, "telemetry_event_index")


def _load_snapshot_index_entries(base: Path) -> tuple[list[dict[str, Any]], list[str]]:
    return _load_index_entries(base / "indexes" / SNAPSHOT_INDEX, "telemetry_snapshot_index")


def _load_index_entries(path: Path, issue_prefix: str) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.exists():
        return [], []
    payload = _read_json(path)
    if not isinstance(payload, Mapping):
        return [], [f"{issue_prefix}_corrupt"]
    items = payload.get("items", [])
    if not isinstance(items, list):
        return [], [f"{issue_prefix}_invalid_structure"]
    entries = [dict(item) for item in items if isinstance(item, Mapping)]
    if len(entries) != len(items):
        return entries, [f"{issue_prefix}_invalid_structure"]
    return entries, []


def _update_event_index(base: Path) -> None:
    items = []
    for path in sorted((base / EVENT_DIR).glob("*.json")):
        payload = _read_json(path)
        if not isinstance(payload, Mapping):
            continue
        items.append(
            {
                "event_id": payload.get("event_id"),
                "relative_path": str(Path(EVENT_DIR) / path.name).replace("\\", "/"),
                "deployed_rule_id": payload.get("deployed_rule_id"),
                "production_deployment_result_id": payload.get("production_deployment_result_id"),
                "producer_id": payload.get("producer_id"),
                "event_type": payload.get("event_type"),
                "observed_at": payload.get("observed_at"),
                "producer_sequence": payload.get("producer_sequence"),
                "event_fingerprint": payload.get("event_fingerprint"),
            }
        )
    _atomic_write_json(base / "indexes" / EVENT_INDEX, {"schema_version": "deployed_rule_operational_event_index_v1", "items": items, "updated_at_utc": _now()})


def _update_snapshot_index(base: Path) -> None:
    items = []
    for path in sorted((base / SNAPSHOT_DIR).glob("*.json")):
        payload = _read_json(path)
        if not isinstance(payload, Mapping):
            continue
        items.append(
            {
                "snapshot_id": payload.get("snapshot_id"),
                "relative_path": str(Path(SNAPSHOT_DIR) / path.name).replace("\\", "/"),
                "deployed_rule_id": payload.get("deployed_rule_id"),
                "production_deployment_result_id": payload.get("production_deployment_result_id"),
                "validated_event_count": payload.get("validated_event_count"),
                "snapshot_fingerprint": payload.get("snapshot_fingerprint"),
                "observation_start": payload.get("observation_start"),
                "observation_end": payload.get("observation_end"),
            }
        )
    _atomic_write_json(base / "indexes" / SNAPSHOT_INDEX, {"schema_version": "deployed_rule_operational_snapshot_index_v1", "items": items, "updated_at_utc": _now()})


def _event_path(base: Path, event_id: str) -> Path:
    return base / EVENT_DIR / f"{_safe_id(event_id)}.json"


def _snapshot_path(base: Path, snapshot_id: str) -> Path:
    return base / SNAPSHOT_DIR / f"{_safe_id(snapshot_id)}.json"


def _event_id(event: Mapping[str, Any]) -> str:
    return "deployed_rule_event_" + _hash_payload(
        {
            "producer_id": event.get("producer_id"),
            "event_type": event.get("event_type"),
            "observed_at": event.get("observed_at"),
            "canonical_rule_id": event.get("canonical_rule_id"),
            "deployed_rule_id": event.get("deployed_rule_id"),
            "production_deployment_result_id": event.get("production_deployment_result_id"),
            "production_transaction_id": event.get("production_transaction_id"),
            "current_production_state_fingerprint": event.get("current_production_state_fingerprint"),
            "current_verification_status": event.get("current_verification_status"),
            "producer_sequence": event.get("producer_sequence"),
            "runtime_outcome_status": event.get("runtime_outcome_status"),
            "input_fingerprint": event.get("input_fingerprint"),
            "output_fingerprint": event.get("output_fingerprint"),
        }
    )[7:31]


def _event_fingerprint(event: Mapping[str, Any]) -> str:
    return _hash_payload({key: event.get(key) for key in sorted(event) if key not in {"event_fingerprint"}})


def _snapshot_id(
    *,
    deployed_rule_id: str,
    production_deployment_result_id: str,
    start_timestamp: str | None,
    end_timestamp: str | None,
    manifest_fingerprint: str,
    event_ids: list[str],
    producer_fingerprints: list[str],
) -> str:
    return "deployed_rule_snapshot_" + _hash_payload(
        {
            "deployed_rule_id": deployed_rule_id,
            "production_deployment_result_id": production_deployment_result_id,
            "start_timestamp": start_timestamp,
            "end_timestamp": end_timestamp,
            "manifest_fingerprint": manifest_fingerprint,
            "event_ids": sorted(event_ids),
            "producer_fingerprints": sorted(producer_fingerprints),
        }
    )[7:31]


def _snapshot_fingerprint(snapshot: Mapping[str, Any]) -> str:
    return _hash_payload({key: snapshot.get(key) for key in sorted(snapshot) if key != "snapshot_fingerprint"})


def _snapshot_summary(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "deployed_rule_id": snapshot.get("deployed_rule_id"),
        "production_deployment_result_id": snapshot.get("production_deployment_result_id"),
        "validated_event_count": snapshot.get("validated_event_count"),
        "invalid_event_count": snapshot.get("invalid_event_count"),
        "corrupt_event_count": snapshot.get("corrupt_event_count"),
        "snapshot_completeness_status": snapshot.get("snapshot_completeness_status"),
        "effectiveness_evaluation_status": snapshot.get("effectiveness_evaluation_status"),
        "metric_availability": snapshot.get("metric_availability"),
        "execution_event_count": snapshot.get("execution_event_count"),
        "execution_completion_count": snapshot.get("execution_completion_count"),
        "execution_failure_count": snapshot.get("execution_failure_count"),
    }


def _find_event_by_id(base: Path, event_id: str) -> dict[str, Any] | None:
    payload = _read_json(_event_path(base, event_id))
    return dict(payload) if isinstance(payload, Mapping) else None


def _record_event_payload(base: Path, event: Mapping[str, Any], *, manifest: Mapping[str, Any]) -> dict[str, Any]:
    event_id = _event_id(event)
    payload = dict(event)
    payload["event_id"] = event_id
    payload["event_fingerprint"] = _event_fingerprint(payload)
    validation = _validate_event_payload(payload, manifest)
    if validation:
        return {"status": "blocked", "warnings": [], "blockers": validation, "writes_performed": 0}
    path = _event_path(base, event_id)
    existing = _read_json(path)
    if isinstance(existing, Mapping):
        if str(existing.get("event_fingerprint") or "") == str(payload.get("event_fingerprint") or ""):
            index_ok = _index_contains_event(base, event_id, payload.get("deployed_rule_id"), str(payload.get("production_deployment_result_id") or ""))
            return {
                "status": "already_recorded" if index_ok else "corrupt",
                "event_id": event_id,
                "writes_performed": 0,
                "warnings": [],
                "blockers": [] if index_ok else ["telemetry_event_index_missing_entry"],
            }
        return {"status": "conflict", "event_id": event_id, "writes_performed": 0, "warnings": [], "blockers": ["telemetry_event_id_semantic_conflict"]}
    before_event = _read_json(path)
    before_index = _read_json(base / "indexes" / EVENT_INDEX)
    try:
        _atomic_write_json(path, payload)
        _update_event_index(base)
    except Exception:
        orphaned = isinstance(_read_json(path), Mapping)
        _restore_json(path, before_event)
        _restore_json(base / "indexes" / EVENT_INDEX, before_index)
        return {
            "status": "corrupt",
            "event_id": event_id,
            "writes_performed": 0,
            "warnings": [],
            "blockers": ["telemetry_event_write_failure_or_orphaned_record" if orphaned else "telemetry_event_write_failure"],
        }
    return {
        "status": "recorded",
        "event_id": event_id,
        "writes_performed": 1,
        "producer_id": payload.get("producer_id"),
        "event_type": payload.get("event_type"),
        "deployed_rule_id": payload.get("deployed_rule_id"),
        "production_deployment_result_id": payload.get("production_deployment_result_id"),
        "event_fingerprint": payload.get("event_fingerprint"),
        "warnings": [],
        "blockers": [],
    }


def _load_all(folder: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping):
            items.append(dict(payload))
    return items


def _orphan_files(folder: Path, indexed_relative_paths: set[str]) -> list[str]:
    indexed_names = {Path(item).name for item in indexed_relative_paths if item}
    return [path.name for path in sorted(folder.glob("*.json")) if path.name not in indexed_names]


def _execution_event_type(execution_envelope: Mapping[str, Any]) -> str:
    execution_status = str(execution_envelope.get("execution_status") or "")
    if execution_status == "completed":
        return "evaluation_completed"
    if execution_status == "failed":
        return "evaluation_failed"
    if execution_status == "skipped":
        return "evaluation_skipped"
    return ""


def _index_contains_event(base: Path, event_id: str, deployed_rule_id: Any, result_id: str) -> bool:
    entries, _issues = _load_event_index_entries(base)
    for item in entries:
        if (
            str(item.get("event_id") or "") == event_id
            and str(item.get("deployed_rule_id") or "") == str(deployed_rule_id or "")
            and str(item.get("production_deployment_result_id") or "") == result_id
        ):
            return True
    return False


def _sequence_gap_count_by_producer(events: list[Mapping[str, Any]]) -> dict[str, int]:
    grouped: dict[str, list[int]] = {}
    for item in events:
        if item.get("producer_sequence") is None:
            continue
        key = str(item.get("producer_id") or "")
        grouped.setdefault(key, []).append(int(item.get("producer_sequence") or 0))
    gaps: dict[str, int] = {}
    for key, values in grouped.items():
        ordered = sorted(set(values))
        gap_count = 0
        for left, right in zip(ordered, ordered[1:]):
            if right - left > 1:
                gap_count += right - left - 1
        gaps[key] = gap_count
    return gaps


def _normalize_timestamp(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in items if str(item)))


def _recommended_action(status: str) -> str:
    return {
        "eligible": "Record one authoritative state-telemetry event through the trusted producer boundary.",
        "eligible_with_warnings": "Review warnings, then record one authoritative state-telemetry event.",
        "ready": "Record an authoritative state observation or build a snapshot from existing events.",
        "healthy": "Telemetry records and indexes are healthy.",
        "warning": "Review orphaned or incomplete telemetry index state.",
        "blocked": "Resolve deployment binding, runtime state, or telemetry validation blockers first.",
        "stale": "Re-read current authoritative deployment state before building telemetry artifacts.",
    }.get(status, "Continue authoritative deployed-rule telemetry review.")


def _ensure_dirs(root: Path | str) -> Path:
    base = _ensure_analysis_dirs(root)
    for folder in (EVENT_DIR, SNAPSHOT_DIR, "indexes"):
        (base / folder).mkdir(parents=True, exist_ok=True)
    return base
