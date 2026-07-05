"""Unified source workflow coordination over existing controlled helpers."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from .corpus_execution_recovery import (
    build_execution_idempotency_key,
    create_started_execution_receipt,
    finalize_execution_receipt,
    find_completed_execution_by_idempotency_key,
    validate_batch_action_dependencies,
)
from .document_manifest import build_document_manifest, load_document_manifest
from .document_preflight import run_document_preflight
from .document_structure import build_document_structure_map
from .source_document_reader import build_page_diagnostics
from .source_documents import SOURCE_DOCUMENT_ROOT, STATUS_EXTRACTED, extract_pdf_text, get_extracted_text, load_source_document
from .source_knowledge import chunk_extracted_text, ensure_source_knowledge_dirs
from .source_reliability_manager import list_evidence_binders_using_source, recalculate_source_reliability, refresh_evidence_binders_for_source

FINGERPRINT_SCHEMA_VERSION = "pipeline_state_fingerprint_v1"
WORKFLOW_PLAN_SCHEMA_VERSION = "source_workflow_plan_v1"
WORKFLOW_PLAN_DIR = "source_workflow_plans"
WORKFLOW_PLAN_INDEX = "source_workflow_plan_index.json"
WORKFLOW_STAGE_ORDER = [
    "run_preflight",
    "extract_text",
    "chunk_text",
    "build_page_diagnostics",
    "build_structure_map",
    "recalculate_reliability",
    "refresh_existing_evidence_binders",
    "refresh_manifest",
]


def calculate_pipeline_state_fingerprint(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = ensure_source_workflow_dirs(root)
    record = load_source_document(document_id, root=base, missing_ok=True)
    from .document_content_map import build_document_scoped_fingerprint

    scoped = build_document_scoped_fingerprint(document_id, root=base)
    components = {
        "source_hash": record.sha256 if record is not None else None,
        "preflight_record_hash": _hash_file(base / "preflight" / f"{document_id}_preflight.json"),
        "extraction_record_hash": _hash_file(base / "extracted_text" / f"{document_id}.txt"),
        "chunk_index_hash": scoped.get("component_hashes", {}).get("chunks"),
        "page_diagnostics_hash": _hash_file(base / "page_diagnostics" / f"{document_id}.json"),
        "structure_map_hash": _hash_file(base / "structure_maps" / f"{document_id}_structure.json"),
        "reliability_record_hash": _hash_file(base / "source_reliability" / f"{document_id}_reliability.json"),
        "citation_index_hash": scoped.get("component_hashes", {}).get("citations"),
        "proposal_index_hash": scoped.get("component_hashes", {}).get("proposals"),
        "evidence_binder_index_hash": scoped.get("component_hashes", {}).get("evidence_binders"),
        "impact_queue_index_hash": scoped.get("component_hashes", {}).get("impact_items"),
        "revalidation_resolution_index_hash": scoped.get("component_hashes", {}).get("revalidation_resolutions"),
    }
    missing = []
    warnings = []
    for key, value in components.items():
        if value is None:
            missing_name = key.replace("_record_hash", "").replace("_index_hash", "").replace("_hash", "")
            missing.append(missing_name)
            warnings.append(f"{missing_name}_missing")
    fingerprint = "sha256:" + hashlib.sha256(json.dumps(components, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
    return {
        "schema_version": FINGERPRINT_SCHEMA_VERSION,
        "document_id": document_id,
        "fingerprint": fingerprint,
        "components": components,
        "missing_components": missing,
        "warnings": list(dict.fromkeys(warnings)),
    }


def synchronize_document_manifest_fingerprint(document_id: str, regenerate: bool = False, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = ensure_source_workflow_dirs(root)
    existing = load_document_manifest(document_id, root=base).get("manifest")
    current = calculate_pipeline_state_fingerprint(document_id, root=base)
    if regenerate or not isinstance(existing, dict):
        return build_document_manifest(document_id, regenerate=True, root=base)
    if existing.get("pipeline_fingerprint") != current.get("fingerprint"):
        return build_document_manifest(document_id, regenerate=True, root=base)
    return build_document_manifest(document_id, regenerate=False, root=base)


def get_source_workflow_stage_registry() -> dict:
    return {
        "run_preflight": {
            "stage": "run_preflight",
            "pipeline_key": "preflight",
            "required_states": ["registered_source"],
            "existing_helper": "run_document_preflight",
            "mutates_controlled_records": True,
            "automatic": False,
            "supported": True,
        },
        "extract_text": {
            "stage": "extract_text",
            "pipeline_key": "extraction",
            "required_states": ["preflight_not_blocked"],
            "existing_helper": "extract_pdf_text",
            "mutates_controlled_records": True,
            "automatic": False,
            "supported": True,
        },
        "chunk_text": {
            "stage": "chunk_text",
            "pipeline_key": "chunking",
            "required_states": ["extraction_complete"],
            "existing_helper": "chunk_extracted_text",
            "mutates_controlled_records": True,
            "automatic": False,
            "supported": True,
        },
        "build_page_diagnostics": {
            "stage": "build_page_diagnostics",
            "pipeline_key": "page_diagnostics",
            "required_states": ["usable_extracted_text"],
            "existing_helper": "build_page_diagnostics",
            "mutates_controlled_records": True,
            "automatic": False,
            "supported": True,
        },
        "build_structure_map": {
            "stage": "build_structure_map",
            "pipeline_key": "structure_map",
            "required_states": ["usable_extracted_text"],
            "existing_helper": "build_document_structure_map",
            "mutates_controlled_records": True,
            "automatic": False,
            "supported": True,
        },
        "recalculate_reliability": {
            "stage": "recalculate_reliability",
            "pipeline_key": "reliability",
            "required_states": ["registered_source"],
            "existing_helper": "recalculate_source_reliability",
            "mutates_controlled_records": True,
            "automatic": False,
            "supported": True,
        },
        "refresh_existing_evidence_binders": {
            "stage": "refresh_existing_evidence_binders",
            "pipeline_key": "impact_review",
            "required_states": ["existing_binders_for_source"],
            "existing_helper": "refresh_evidence_binders_for_source",
            "mutates_controlled_records": True,
            "automatic": False,
            "supported": True,
        },
        "refresh_manifest": {
            "stage": "refresh_manifest",
            "pipeline_key": "manifest",
            "required_states": ["registered_source"],
            "existing_helper": "build_document_manifest",
            "mutates_controlled_records": True,
            "automatic": False,
            "supported": True,
        },
    }


def recommend_next_source_workflow_stage(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = ensure_source_workflow_dirs(root)
    record = load_source_document(document_id, root=base, missing_ok=True)
    if record is None:
        return {"document_id": document_id, "recommended_stage": "none", "reason": "registered_source_missing", "executable": False, "dependencies_satisfied": False, "warnings": ["source_record_missing"]}
    manifest = synchronize_document_manifest_fingerprint(document_id, regenerate=False, root=base)
    pipeline = manifest.get("pipeline", {})
    stale = set(manifest.get("stale_components", []))
    stage_reason_pairs = [
        ("run_preflight", "preflight_missing", pipeline.get("preflight") in {"missing", "stale"}),
        ("extract_text", "extraction_missing", pipeline.get("extraction") in {"missing", "stale"}),
        ("chunk_text", "chunking_missing", pipeline.get("chunking") in {"missing", "stale"}),
        ("build_page_diagnostics", "page_diagnostics_missing", pipeline.get("page_diagnostics") in {"missing", "stale"}),
        ("build_structure_map", "structure_map_missing", pipeline.get("structure_map") in {"missing", "stale"}),
        ("recalculate_reliability", "reliability_missing", pipeline.get("reliability") in {"missing", "stale"}),
        (
            "refresh_existing_evidence_binders",
            "evidence_binder_recheck_required",
            "evidence_binder_recheck" in stale and list_evidence_binders_using_source(document_id, root=base).get("binders_found", 0) > 0,
        ),
    ]
    for stage, reason, active in stage_reason_pairs:
        if not active:
            continue
        deps = validate_source_workflow_stage(document_id, stage, root=base)
        return {
            "document_id": document_id,
            "recommended_stage": stage,
            "reason": reason,
            "executable": bool(deps.get("allowed")),
            "dependencies_satisfied": bool(deps.get("allowed")),
            "warnings": deps.get("warnings", []),
        }
    return {"document_id": document_id, "recommended_stage": "none", "reason": "ready_or_no_supported_stage", "executable": False, "dependencies_satisfied": True, "warnings": []}


def create_source_workflow_plan(
    document_id: str,
    requested_stage: str | None = None,
    dry_run: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = ensure_source_workflow_dirs(root)
    manifest = synchronize_document_manifest_fingerprint(document_id, regenerate=False, root=base)
    recommendation = recommend_next_source_workflow_stage(document_id, root=base)
    stage = requested_stage or recommendation.get("recommended_stage") or "none"
    registry = get_source_workflow_stage_registry()
    if stage != "none" and stage not in registry:
        raise ValueError(f"Unsupported workflow stage: {stage}")
    dependencies = validate_source_workflow_stage(document_id, stage, root=base) if stage != "none" else {"allowed": False, "missing_dependencies": [], "blockers": [], "warnings": []}
    plan = {
        "workflow_plan_id": f"workflow_{document_id}_{_timestamp_token()}",
        "schema_version": WORKFLOW_PLAN_SCHEMA_VERSION,
        "document_id": document_id,
        "requested_stage": stage,
        "recommended_stage": recommendation.get("recommended_stage"),
        "dry_run": bool(dry_run),
        "status": "planned" if stage != "none" else "not_executable",
        "dependencies": {
            "allowed": bool(dependencies.get("allowed")),
            "missing": dependencies.get("missing_dependencies", []),
            "blockers": dependencies.get("blockers", []),
        },
        "before": {
            "pipeline_fingerprint": manifest.get("pipeline_fingerprint"),
            "readiness_status": (manifest.get("backend_readiness") or {}).get("status"),
            "pipeline_stage_status": _stage_status(manifest, stage),
        },
        "expected_effect": {
            "pipeline_key": registry.get(stage, {}).get("pipeline_key"),
            "manifest_refresh_required": True,
        },
        "warnings": list(dict.fromkeys([*recommendation.get("warnings", []), *dependencies.get("warnings", [])])),
        "updated_at_utc": _now(),
    }
    _atomic_write_json(_plan_path(base, plan["workflow_plan_id"]), plan)
    _update_plan_index(base)
    return plan


def validate_source_workflow_stage(document_id: str, stage: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = ensure_source_workflow_dirs(root)
    registry = get_source_workflow_stage_registry()
    if stage not in registry:
        return {"document_id": document_id, "stage": stage, "allowed": False, "missing_dependencies": [], "blockers": ["unsupported"], "warnings": []}
    if stage in {"run_preflight", "extract_text", "chunk_text", "build_page_diagnostics", "build_structure_map", "recalculate_reliability"}:
        mapped = validate_batch_action_dependencies(document_id, _stage_to_batch_action(stage), root=base)
        return {
            "document_id": document_id,
            "stage": stage,
            "allowed": mapped.get("allowed", False),
            "missing_dependencies": mapped.get("missing_dependencies", []),
            "blockers": mapped.get("blockers", []),
            "warnings": mapped.get("warnings", []),
        }
    if stage == "refresh_existing_evidence_binders":
        binders = list_evidence_binders_using_source(document_id, root=base)
        missing = []
        if load_source_document(document_id, root=base, missing_ok=True) is None:
            missing.append("registered_source")
        if int(binders.get("binders_found", 0) or 0) <= 0:
            missing.append("existing_binder_reference")
        if not callable(getattr(refresh_evidence_binders_for_source, "__call__", None)):
            missing.append("binder_refresh_helper")
        return {"document_id": document_id, "stage": stage, "allowed": not missing, "missing_dependencies": missing, "blockers": ["dependency_missing"] if missing else [], "warnings": []}
    if stage == "refresh_manifest":
        missing = []
        if load_source_document(document_id, root=base, missing_ok=True) is None:
            missing.append("registered_source")
        return {"document_id": document_id, "stage": stage, "allowed": not missing, "missing_dependencies": missing, "blockers": ["dependency_missing"] if missing else [], "warnings": []}
    return {"document_id": document_id, "stage": stage, "allowed": False, "missing_dependencies": [], "blockers": ["unsupported"], "warnings": []}


def execute_source_workflow_stage(
    workflow_plan_id: str,
    dry_run: bool = True,
    force: bool = False,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = ensure_source_workflow_dirs(root)
    plan = load_source_workflow_plan(workflow_plan_id, root=base)
    if plan.get("status") == "not_found":
        raise FileNotFoundError(workflow_plan_id)
    document_id = str(plan.get("document_id") or "")
    stage = str(plan.get("requested_stage") or "")
    registry = get_source_workflow_stage_registry()
    if stage not in registry:
        return {"workflow_plan_id": workflow_plan_id, "document_id": document_id, "stage": stage, "status": "failed", "classification": "unsupported", "error_type": "ValueError", "error_message": "Unsupported workflow stage.", "manifest_refreshed": False, "readiness_status": "unknown"}
    manifest_before = synchronize_document_manifest_fingerprint(document_id, regenerate=False, root=base)
    before = {
        "readiness_status": (manifest_before.get("backend_readiness") or {}).get("status"),
        "pipeline_fingerprint": manifest_before.get("pipeline_fingerprint"),
        "stage_status": _stage_status(manifest_before, stage),
    }
    if dry_run:
        result = {
            "workflow_plan_id": workflow_plan_id,
            "document_id": document_id,
            "stage": stage,
            "dry_run": True,
            "status": "dry_run_only",
            "before": before,
            "execution": {"helper": registry[stage]["existing_helper"], "result_status": "not_executed"},
            "after": before,
            "next_recommended_stage": recommend_next_source_workflow_stage(document_id, root=base).get("recommended_stage"),
            "warnings": [],
        }
        _update_plan_execution(base, workflow_plan_id, result)
        return result
    dependencies = validate_source_workflow_stage(document_id, stage, root=base)
    if not dependencies.get("allowed"):
        failed = {
            "workflow_plan_id": workflow_plan_id,
            "document_id": document_id,
            "stage": stage,
            "dry_run": False,
            "status": "blocked",
            "classification": "dependency_missing" if "dependency_missing" in dependencies.get("blockers", []) else "blocked",
            "error_type": None,
            "error_message": "Stage dependencies are not satisfied.",
            "manifest_refreshed": True,
            "readiness_status": before["readiness_status"],
            "warnings": dependencies.get("warnings", []),
        }
        _update_plan_execution(base, workflow_plan_id, failed)
        return failed
    idempotency_key = build_execution_idempotency_key(document_id, stage, {"workflow_plan_id": workflow_plan_id, "pipeline_fingerprint": before["pipeline_fingerprint"]}, {"force": bool(force)})
    prior = None if force else find_completed_execution_by_idempotency_key(idempotency_key, root=base)
    if prior is not None:
        result = {
            "workflow_plan_id": workflow_plan_id,
            "document_id": document_id,
            "stage": stage,
            "dry_run": False,
            "status": "already_completed",
            "classification": "already_completed",
            "before": before,
            "execution": {"helper": registry[stage]["existing_helper"], "result_status": "already_completed", "prior_receipt_id": prior.get("receipt_id")},
            "after": before,
            "next_recommended_stage": recommend_next_source_workflow_stage(document_id, root=base).get("recommended_stage"),
            "warnings": ["idempotency_skip"],
        }
        _update_plan_execution(base, workflow_plan_id, result)
        return result
    attempt_number = _next_attempt_number(workflow_plan_id, document_id, stage, base)
    receipt = create_started_execution_receipt(
        batch_id=workflow_plan_id,
        document_id=document_id,
        action=stage,
        attempt_number=attempt_number,
        idempotency_key=idempotency_key,
        input_summary={"workflow_plan_id": workflow_plan_id, "stage": stage, "before_pipeline_fingerprint": before["pipeline_fingerprint"]},
        root=base,
    )
    try:
        execution_result = _run_stage(document_id, stage, base)
        manifest_after = synchronize_document_manifest_fingerprint(document_id, regenerate=True, root=base)
        after = {
            "readiness_status": (manifest_after.get("backend_readiness") or {}).get("status"),
            "pipeline_fingerprint": manifest_after.get("pipeline_fingerprint"),
            "stage_status": _stage_status(manifest_after, stage),
        }
        finalized = finalize_execution_receipt(
            receipt["receipt_id"],
            status="completed",
            classification="unknown",
            output_summary=_public_execution_summary(execution_result),
            root=base,
        )
        result = {
            "workflow_plan_id": workflow_plan_id,
            "document_id": document_id,
            "stage": stage,
            "dry_run": False,
            "status": "completed",
            "before": before,
            "execution": {"helper": registry[stage]["existing_helper"], "result_status": "completed", "receipt_id": finalized.get("receipt_id")},
            "after": after,
            "next_recommended_stage": recommend_next_source_workflow_stage(document_id, root=base).get("recommended_stage"),
            "warnings": [],
        }
        _update_plan_execution(base, workflow_plan_id, result)
        return result
    except Exception as exc:
        manifest_after = synchronize_document_manifest_fingerprint(document_id, regenerate=True, root=base)
        after_readiness = (manifest_after.get("backend_readiness") or {}).get("status")
        finalized = finalize_execution_receipt(
            receipt["receipt_id"],
            status="failed",
            classification="processing_failure",
            output_summary={"status": "failed"},
            error_type=type(exc).__name__,
            error_message=_sanitize_text(str(exc)),
            root=base,
        )
        result = {
            "workflow_plan_id": workflow_plan_id,
            "document_id": document_id,
            "stage": stage,
            "dry_run": False,
            "status": "failed",
            "classification": "processing_failure",
            "error_type": type(exc).__name__,
            "error_message": _sanitize_text(str(exc)),
            "manifest_refreshed": True,
            "readiness_status": after_readiness,
            "receipt_id": finalized.get("receipt_id"),
            "warnings": [],
        }
        _update_plan_execution(base, workflow_plan_id, result)
        return result


def get_source_workflow_resume_state(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = ensure_source_workflow_dirs(root)
    manifest = synchronize_document_manifest_fingerprint(document_id, regenerate=False, root=base)
    recommendation = recommend_next_source_workflow_stage(document_id, root=base)
    completed = []
    remaining = []
    for stage in WORKFLOW_STAGE_ORDER:
        status = _stage_status(manifest, stage)
        if status == "complete":
            completed.append(stage)
        elif status != "not_applicable":
            remaining.append(stage)
    return {
        "document_id": document_id,
        "current_readiness": (manifest.get("backend_readiness") or {}).get("status"),
        "first_missing_or_stale_stage": recommendation.get("recommended_stage"),
        "recommended_stage": recommendation.get("recommended_stage"),
        "executable": recommendation.get("executable"),
        "completed_stages": completed,
        "remaining_stages": remaining,
        "warnings": recommendation.get("warnings", []),
    }


def load_source_workflow_plan(workflow_plan_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    path = _plan_path(ensure_source_workflow_dirs(root), workflow_plan_id)
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return {"workflow_plan_id": workflow_plan_id, "status": "not_found", "plan": None, "warnings": []}
    return payload


def format_source_workflow_report(document_id: str, public_safe: bool = True, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> str:
    base = ensure_source_workflow_dirs(root)
    manifest = synchronize_document_manifest_fingerprint(document_id, regenerate=False, root=base)
    recommendation = recommend_next_source_workflow_stage(document_id, root=base)
    dependencies = validate_source_workflow_stage(document_id, recommendation.get("recommended_stage"), root=base) if recommendation.get("recommended_stage") not in {None, "none"} else {"allowed": True}
    latest = _latest_plan_for_document(document_id, base)
    last_execution = ((latest or {}).get("last_execution") or {}).get("status", "No stage executed in this report.")
    lines = [
        "Source Workflow Report",
        "",
        f"Document: {document_id}",
        f"Backend Readiness: {(manifest.get('backend_readiness') or {}).get('status')}",
        f"Pipeline Fingerprint Changed: {'Yes' if manifest.get('fingerprint_changed') else 'No'}",
        "",
        "Current Pipeline:",
        f"- Preflight: {(manifest.get('pipeline') or {}).get('preflight')}",
        f"- Extraction: {(manifest.get('pipeline') or {}).get('extraction')}",
        f"- Chunking: {(manifest.get('pipeline') or {}).get('chunking')}",
        f"- Page Diagnostics: {(manifest.get('pipeline') or {}).get('page_diagnostics')}",
        f"- Structure Map: {(manifest.get('pipeline') or {}).get('structure_map')}",
        f"- Reliability: {(manifest.get('pipeline') or {}).get('reliability')}",
        "",
        "Recommended Next Stage:",
        str(recommendation.get("recommended_stage")),
        "",
        "Dependencies:",
        "satisfied" if dependencies.get("allowed") else "not_satisfied",
        "",
        "Last Workflow Result:",
        str(last_execution),
        "",
        "Recommended Action:",
        f"Create a dry-run workflow plan for {recommendation.get('recommended_stage')}." if recommendation.get("recommended_stage") not in {None, 'none'} else str((manifest.get("backend_readiness") or {}).get("recommended_action")),
    ]
    text = "\n".join(lines)
    return _sanitize_text(text) if public_safe else text


def ensure_source_workflow_dirs(root: Path | str = SOURCE_DOCUMENT_ROOT) -> Path:
    base = ensure_source_knowledge_dirs(root)
    (base / WORKFLOW_PLAN_DIR).mkdir(parents=True, exist_ok=True)
    (base / "indexes").mkdir(parents=True, exist_ok=True)
    index_path = base / "indexes" / WORKFLOW_PLAN_INDEX
    if not index_path.exists():
        _atomic_write_json(index_path, {"entries": [], "updated_at_utc": _now()})
    return base


def _stage_to_batch_action(stage: str) -> str:
    return stage


def _stage_status(manifest: dict, stage: str) -> str:
    pipeline = manifest.get("pipeline", {}) if isinstance(manifest, dict) else {}
    stale = set(manifest.get("stale_components", [])) if isinstance(manifest, dict) else set()
    mapping = {
        "run_preflight": pipeline.get("preflight", "unknown"),
        "extract_text": pipeline.get("extraction", "unknown"),
        "chunk_text": pipeline.get("chunking", "unknown"),
        "build_page_diagnostics": pipeline.get("page_diagnostics", "unknown"),
        "build_structure_map": pipeline.get("structure_map", "unknown"),
        "recalculate_reliability": pipeline.get("reliability", "unknown"),
    }
    if stage in mapping:
        return str(mapping[stage])
    if stage == "refresh_existing_evidence_binders":
        return "stale" if "evidence_binder_recheck" in stale else "not_applicable"
    if stage == "refresh_manifest":
        return "stale" if manifest.get("fingerprint_changed") else "complete"
    return "unknown"


def _run_stage(document_id: str, stage: str, root: Path) -> Any:
    helpers: dict[str, Callable[[], Any]] = {
        "run_preflight": lambda: run_document_preflight(document_id, regenerate=True, root=root),
        "extract_text": lambda: extract_pdf_text(document_id, root=root),
        "chunk_text": lambda: chunk_extracted_text(document_id, regenerate=True, root=root),
        "build_page_diagnostics": lambda: build_page_diagnostics(document_id, regenerate=True, root=root),
        "build_structure_map": lambda: build_document_structure_map(document_id, regenerate=True, root=root),
        "recalculate_reliability": lambda: recalculate_source_reliability(document_id, root=root),
        "refresh_existing_evidence_binders": lambda: refresh_evidence_binders_for_source(document_id, root=root),
        "refresh_manifest": lambda: build_document_manifest(document_id, regenerate=True, root=root),
    }
    return helpers[stage]()


def _public_execution_summary(value: Any) -> dict[str, object]:
    if isinstance(value, list):
        return {"result_type": "list", "count": len(value)}
    if hasattr(value, "to_json"):
        try:
            payload = value.to_json(public_safe=True)
        except TypeError:
            payload = value.to_json()
        return {"result_type": type(value).__name__, "keys": sorted(payload.keys())[:12]}
    if isinstance(value, dict):
        return {"result_type": "dict", "keys": sorted(str(key) for key in value.keys())[:12]}
    return {"result_type": type(value).__name__}


def _next_attempt_number(workflow_plan_id: str, document_id: str, stage: str, root: Path) -> int:
    folder = root / "corpus_execution_receipts"
    attempts = 0
    if folder.exists():
        for path in folder.glob("*.json"):
            payload = _read_json(path)
            if not isinstance(payload, dict):
                continue
            if payload.get("batch_id") == workflow_plan_id and payload.get("document_id") == document_id and payload.get("action") == stage:
                attempts = max(attempts, int(payload.get("attempt_number") or 0))
    return attempts + 1


def _latest_plan_for_document(document_id: str, root: Path) -> dict[str, object] | None:
    latest = None
    for path in sorted((root / WORKFLOW_PLAN_DIR).glob("*.json"), reverse=True):
        payload = _read_json(path)
        if isinstance(payload, dict) and payload.get("document_id") == document_id:
            latest = payload
            break
    return latest


def _update_plan_execution(root: Path, workflow_plan_id: str, result: dict[str, object]) -> None:
    payload = load_source_workflow_plan(workflow_plan_id, root=root)
    if not isinstance(payload, dict) or payload.get("status") == "not_found":
        return
    payload["status"] = str(result.get("status") or payload.get("status"))
    payload["last_execution"] = result
    payload["updated_at_utc"] = _now()
    _atomic_write_json(_plan_path(root, workflow_plan_id), payload)
    _update_plan_index(root)


def _plan_path(root: Path, workflow_plan_id: str) -> Path:
    return root / WORKFLOW_PLAN_DIR / f"{workflow_plan_id}.json"


def _update_plan_index(root: Path) -> None:
    entries = []
    for path in sorted((root / WORKFLOW_PLAN_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict):
            entries.append(
                {
                    "workflow_plan_id": payload.get("workflow_plan_id"),
                    "document_id": payload.get("document_id"),
                    "requested_stage": payload.get("requested_stage"),
                    "status": payload.get("status"),
                    "dry_run": payload.get("dry_run"),
                    "updated_at_utc": payload.get("updated_at_utc"),
                }
            )
    _atomic_write_json(root / "indexes" / WORKFLOW_PLAN_INDEX, {"entries": entries, "updated_at_utc": _now()})


def _read_json(path: Path) -> dict[str, object] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _hash_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            pass
    os.replace(temp_path, path)


def _sanitize_text(text: str) -> str:
    return str(text).replace(str(Path.cwd()), "[workspace]").replace(str(SOURCE_DOCUMENT_ROOT), "[source-root]").replace("\\", "/")


def _timestamp_token() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
