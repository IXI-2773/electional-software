"""Canonical per-document backend manifest and locator validation."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .document_preflight import load_document_preflight
from .document_structure import get_document_structure_summary, load_document_structure_map
from .source_document_reader import get_page_diagnostic_summary
from .source_documents import SOURCE_DOCUMENT_ROOT, STATUS_EXTRACTED, load_source_document
from .source_knowledge import load_chunks

MANIFEST_SCHEMA_VERSION = "document_manifest_v1"
LOCATOR_SCHEMA_VERSION = "source_locator_v1"
MANIFEST_DIR = "document_manifests"
MANIFEST_INDEX = "document_manifest_index.json"
LIFECYCLE_STATUSES = {"registered", "processing", "ready", "warning", "stale", "blocked", "corrupt", "unknown"}
PIPELINE_STATUSES = {"complete", "missing", "stale", "blocked", "failed", "unknown", "not_applicable"}
READINESS_STATUSES = {"ready", "ready_with_warnings", "not_ready", "blocked", "stale", "corrupt", "unknown"}


def build_document_manifest(document_id: str, regenerate: bool = False, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = ensure_document_manifest_dirs(root)
    existing = load_document_manifest(document_id, root=base).get("manifest")
    current_source = load_source_document(document_id, root=base, missing_ok=True)
    fingerprint = _current_pipeline_fingerprint(document_id, base)
    if (
        existing
        and not regenerate
        and current_source is not None
        and current_source.sha256 == existing.get("source_hash")
        and existing.get("pipeline_fingerprint") == fingerprint.get("fingerprint")
        and existing.get("schema_version") == MANIFEST_SCHEMA_VERSION
    ):
        return existing
    if current_source is None:
        raise FileNotFoundError(document_id)
    revision = calculate_document_revision_state(document_id, existing_manifest=existing, root=base)
    pipeline, references, record_hashes, warnings, blockers = _collect_pipeline_state(document_id, revision, base)
    stale_components = _detect_stale_components(existing, revision, record_hashes, pipeline)
    consistency = reconcile_document_subsystems(document_id, root=base)
    readiness = get_document_backend_readiness(document_id, manifest_hint={"pipeline": pipeline, "consistency": consistency, "stale_components": stale_components, "source_revision": revision["source_revision"], "revision_changed": revision["revision_changed"]}, root=base)
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "manifest_id": f"manifest_{document_id}",
        "document_id": document_id,
        "source_revision": revision["source_revision"],
        "source_hash": revision["source_hash"],
        "previous_source_hash": revision["previous_source_hash"],
        "revision_changed": revision["revision_changed"],
        "lifecycle_status": _lifecycle_status(readiness["status"], pipeline),
        "pipeline": pipeline,
        "record_references": references,
        "record_hashes": record_hashes,
        "pipeline_fingerprint": fingerprint.get("fingerprint"),
        "pipeline_fingerprint_components": fingerprint.get("components", {}),
        "fingerprint_changed": bool(existing and existing.get("pipeline_fingerprint") and existing.get("pipeline_fingerprint") != fingerprint.get("fingerprint")),
        "fingerprint_updated_at_utc": _now(),
        "stale_components": stale_components,
        "consistency": consistency,
        "backend_readiness": readiness,
        "created_at_utc": (existing or {}).get("created_at_utc") or _now(),
        "updated_at_utc": _now(),
        "warnings": list(dict.fromkeys(warnings + fingerprint.get("warnings", []) + consistency.get("warnings", []) + readiness.get("warnings", []))),
        "blockers": list(dict.fromkeys(blockers + readiness.get("blockers", []))),
    }
    _atomic_write_json(_manifest_path(base, document_id), manifest)
    _update_manifest_index(base)
    return manifest


def load_document_manifest(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    path = _manifest_path(ensure_document_manifest_dirs(root), document_id)
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return {"document_id": document_id, "status": "not_found", "manifest": None, "warnings": []}
    return {"document_id": document_id, "status": "loaded", "manifest": payload, "warnings": []}


def list_document_manifests(
    lifecycle_status: str | None = None,
    readiness_status: str | None = None,
    limit: int = 100,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = ensure_document_manifest_dirs(root)
    items = []
    for path in sorted((base / MANIFEST_DIR).glob("*.json"), reverse=True):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        if lifecycle_status is not None and payload.get("lifecycle_status") != lifecycle_status:
            continue
        if readiness_status is not None and (payload.get("backend_readiness") or {}).get("status") != readiness_status:
            continue
        items.append(payload)
    return {"count": len(items[: max(0, int(limit or 0))]), "items": items[: max(0, int(limit or 0))]}


def validate_source_locator(locator: dict, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = ensure_document_manifest_dirs(root)
    normalized = normalize_source_locator(locator)
    blockers: list[str] = []
    warnings: list[str] = []
    document_id = normalized.get("document_id")
    if not document_id:
        blockers.append("document_id_missing")
    elif load_source_document(str(document_id), root=base, missing_ok=True) is None:
        blockers.append("document_id_missing")
    source_revision = normalized.get("source_revision")
    if source_revision is not None and int(source_revision) <= 0:
        blockers.append("source_revision_invalid")
    page_number = normalized.get("page_number")
    if page_number is not None and int(page_number) < 1:
        blockers.append("page_number_invalid")
    start = normalized.get("character_start")
    end = normalized.get("character_end")
    if start is not None and int(start) < 0:
        blockers.append("character_start_invalid")
    if end is not None and start is not None and int(end) < int(start):
        blockers.append("character_end_precedes_start")
    chunk_id = normalized.get("chunk_id")
    if chunk_id:
        matching = next((chunk for chunk in load_chunks(root=base) if chunk.chunk_id == chunk_id), None)
        if matching is None:
            warnings.append("chunk_id_unverifiable")
        else:
            if document_id and matching.document_id != document_id:
                blockers.append("chunk_id_document_mismatch")
            if page_number is not None:
                if matching.page_start is not None and matching.page_end is not None:
                    if not (int(matching.page_start) <= int(page_number) <= int(matching.page_end)):
                        blockers.append("page_number_chunk_mismatch")
                else:
                    warnings.append("page_number_chunk_unverifiable")
    elif page_number is not None:
        warnings.append("page_number_unverifiable_without_chunk")
    return {"valid": not blockers, "normalized_locator": normalized, "warnings": list(dict.fromkeys(warnings)), "blockers": list(dict.fromkeys(blockers))}


def normalize_source_locator(locator: dict) -> dict:
    payload = dict(locator or {})
    normalized: dict[str, Any] = {"schema_version": LOCATOR_SCHEMA_VERSION}
    for field in ("document_id", "chunk_id"):
        value = payload.get(field)
        if value not in {None, ""}:
            normalized[field] = str(value)
    for field in ("source_revision", "page_number", "character_start", "character_end"):
        value = payload.get(field)
        if value in {None, ""}:
            continue
        try:
            normalized[field] = int(value)
        except Exception:
            normalized[field] = value
    return normalized


def calculate_document_revision_state(document_id: str, existing_manifest: dict | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    record = load_source_document(document_id, root=root, missing_ok=True)
    if record is None or not record.sha256:
        return {"document_id": document_id, "source_revision": None, "source_hash": None, "previous_source_hash": None, "revision_changed": False, "warnings": ["source_hash_unavailable"]}
    existing = existing_manifest or {}
    previous_hash = existing.get("source_hash")
    if not previous_hash:
        return {"document_id": document_id, "source_revision": 1, "source_hash": record.sha256, "previous_source_hash": None, "revision_changed": False, "warnings": []}
    if previous_hash == record.sha256:
        return {"document_id": document_id, "source_revision": int(existing.get("source_revision") or 1), "source_hash": record.sha256, "previous_source_hash": previous_hash, "revision_changed": False, "warnings": []}
    return {"document_id": document_id, "source_revision": int(existing.get("source_revision") or 1) + 1, "source_hash": record.sha256, "previous_source_hash": previous_hash, "revision_changed": True, "warnings": []}


def reconcile_document_subsystems(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = ensure_document_manifest_dirs(root)
    issues: list[dict[str, object]] = []
    warnings: list[str] = []
    checks_run = 0
    source = load_source_document(document_id, root=base, missing_ok=True)
    checks_run += 1
    if source is None:
        issues.append(_issue("source_record_missing", document_id, "critical"))
    preflight = _read_json(base / "preflight" / f"{document_id}_preflight.json")
    checks_run += 1
    if isinstance(preflight, dict) and preflight.get("document_id") != document_id:
        issues.append(_issue("preflight_document_mismatch", str(preflight.get("preflight_id") or document_id), "critical"))
    chunks = load_chunks(document_id=document_id, root=base)
    checks_run += 1
    if source is not None and source.extraction_status != STATUS_EXTRACTED and chunks:
        issues.append(_issue("chunks_without_extraction", document_id, "warning"))
    chunk_ids = {chunk.chunk_id for chunk in chunks}
    for chunk in chunks:
        checks_run += 1
        if chunk.document_id != document_id:
            issues.append(_issue("chunk_document_mismatch", chunk.chunk_id, "critical"))
    diagnostics = _read_json(base / "page_diagnostics" / f"{document_id}.json")
    checks_run += 1
    if isinstance(diagnostics, dict) and diagnostics.get("document_id") != document_id:
        issues.append(_issue("page_diagnostics_document_mismatch", document_id, "critical"))
    structure = _read_json(base / "structure_maps" / f"{document_id}_structure.json")
    checks_run += 1
    if isinstance(structure, dict) and structure.get("document_id") != document_id:
        issues.append(_issue("structure_map_document_mismatch", document_id, "critical"))
    reliability = _read_json(base / "source_reliability" / f"{document_id}_reliability.json")
    checks_run += 1
    if isinstance(reliability, dict) and reliability.get("document_id") not in {None, document_id}:
        issues.append(_issue("reliability_document_mismatch", document_id, "critical"))
    for path in sorted((base / "citations").glob("*.json")):
        citation = _read_json(path)
        if not isinstance(citation, dict) or citation.get("document_id") != document_id:
            continue
        checks_run += 1
        chunk_id = str(citation.get("chunk_id") or "")
        if chunk_id and chunk_id not in chunk_ids:
            issues.append(_issue("citation_missing_chunk", str(citation.get("citation_id") or path.stem), "critical"))
    proposal_ids = set()
    for path in sorted((base / "proposals").glob("*.json")):
        proposal = _read_json(path)
        if not isinstance(proposal, dict) or proposal.get("document_id") != document_id:
            continue
        proposal_ids.add(str(proposal.get("proposal_id") or ""))
        checks_run += 1
        if proposal.get("citation_ids"):
            for citation_id in proposal.get("citation_ids", []):
                if not (base / "citations" / f"{citation_id}.json").exists():
                    issues.append(_issue("proposal_missing_citation", str(proposal.get("proposal_id") or path.stem), "warning"))
    for path in sorted((base / "evidence_binders").glob("*.json")):
        binder = _read_json(path)
        if not isinstance(binder, dict):
            continue
        linked = [item for item in binder.get("linked_citations", []) if isinstance(item, dict)]
        if not any(str(item.get("document_id") or "") == document_id for item in linked):
            continue
        checks_run += 1
        if str(binder.get("proposal_id") or "") not in proposal_ids:
            issues.append(_issue("evidence_binder_missing_proposal", str(binder.get("binder_id") or path.stem), "critical"))
        for item in linked:
            citation_id = str(item.get("citation_id") or "")
            if citation_id and not (base / "citations" / f"{citation_id}.json").exists():
                issues.append(_issue("evidence_binder_missing_citation", str(binder.get("binder_id") or path.stem), "critical"))
    for path in sorted((base / "source_impact_queue").glob("impact_*.json")):
        queue = _read_json(path)
        if not isinstance(queue, dict):
            continue
        checks_run += 1
        if queue.get("document_id") != document_id:
            continue
    for path in sorted((base / "source_revalidation_resolutions").glob("*.json")):
        resolution = _read_json(path)
        if not isinstance(resolution, dict) or resolution.get("document_id") != document_id:
            continue
        checks_run += 1
        queue_item_id = str(resolution.get("queue_item_id") or "")
        if not (base / "source_impact_queue" / f"{queue_item_id}.json").exists():
            issues.append(_issue("resolution_missing_queue_item", str(resolution.get("resolution_id") or path.stem), "critical"))
    if not (base / "indexes" / "citation_index.json").exists():
        warnings.append("citation_index_missing")
    valid_checks = checks_run - len(issues)
    warning_checks = sum(1 for issue in issues if issue["severity"] == "warning")
    critical_checks = sum(1 for issue in issues if issue["severity"] == "critical")
    status = "critical" if critical_checks else "warning" if warning_checks or warnings else "info"
    return {
        "document_id": document_id,
        "status": status,
        "checks_run": checks_run,
        "valid_checks": max(0, valid_checks),
        "warning_checks": warning_checks,
        "critical_checks": critical_checks,
        "issues": issues,
        "warnings": warnings,
    }


def get_document_backend_readiness(document_id: str, manifest_hint: dict | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = ensure_document_manifest_dirs(root)
    manifest = manifest_hint or {}
    pipeline = manifest.get("pipeline") or _collect_pipeline_state(document_id, calculate_document_revision_state(document_id, root=base), base)[0]
    consistency = manifest.get("consistency") or reconcile_document_subsystems(document_id, root=base)
    source = load_source_document(document_id, root=base, missing_ok=True)
    requirements = {
        "registered": source is not None,
        "preflight": pipeline.get("preflight") == "complete",
        "extraction": pipeline.get("extraction") == "complete",
        "chunks": pipeline.get("chunking") == "complete",
        "consistency_valid": int(consistency.get("critical_checks", 0)) == 0,
        "revision_current": not bool(manifest.get("revision_changed")) and not any(item in {"preflight", "extraction", "chunking", "page_diagnostics", "structure_map", "reliability"} for item in manifest.get("stale_components", [])),
    }
    blockers: list[str] = []
    warnings: list[str] = []
    if not requirements["registered"]:
        blockers.append("document_missing")
    if pipeline.get("preflight") == "blocked":
        return {"document_id": document_id, "status": "blocked", "core_requirements": requirements, "blockers": ["preflight_blocked"], "warnings": [], "recommended_action": "Resolve the controlled preflight gate before reader integration."}
    if int(consistency.get("critical_checks", 0)) > 0:
        return {"document_id": document_id, "status": "corrupt", "core_requirements": requirements, "blockers": ["critical_consistency_issues"], "warnings": [], "recommended_action": "Review the controlled record inconsistencies before future use."}
    if manifest.get("stale_components") and not manifest.get("revision_changed", False):
        warnings.append("stale_components_present")
    if not requirements["preflight"]:
        blockers.append("preflight_missing")
    if not requirements["extraction"]:
        blockers.append("extraction_missing")
    if not requirements["chunks"]:
        blockers.append("chunks_missing")
    if manifest.get("revision_changed") or not requirements["revision_current"]:
        return {"document_id": document_id, "status": "stale", "core_requirements": requirements, "blockers": ["source_revision_changed"], "warnings": warnings, "recommended_action": "Re-run the controlled source pipeline before future reader integration."}
    if blockers:
        return {"document_id": document_id, "status": "not_ready", "core_requirements": requirements, "blockers": blockers, "warnings": warnings, "recommended_action": "Run controlled chunking before reader integration." if "chunks_missing" in blockers else "Complete the controlled source pipeline before reader integration."}
    if pipeline.get("page_diagnostics") != "complete" or pipeline.get("structure_map") != "complete" or pipeline.get("reliability") not in {"complete", "not_applicable"}:
        return {"document_id": document_id, "status": "ready_with_warnings", "core_requirements": requirements, "blockers": [], "warnings": ["non_core_components_incomplete"], "recommended_action": "Core reader readiness is satisfied; review non-core warnings as needed."}
    return {"document_id": document_id, "status": "ready", "core_requirements": requirements, "blockers": [], "warnings": warnings, "recommended_action": "Document backend is ready for future workflow integration."}


def format_document_manifest_report(document_id: str, public_safe: bool = True, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> str:
    manifest = build_document_manifest(document_id, regenerate=False, root=root)
    consistency = manifest.get("consistency", {})
    readiness = manifest.get("backend_readiness", {})
    lines = [
        "Document Backend Manifest",
        "",
        f"Document: {document_id}",
        f"Source Revision: {manifest.get('source_revision')}",
        f"Lifecycle Status: {manifest.get('lifecycle_status')}",
        f"Backend Readiness: {readiness.get('status')}",
        "",
        "Pipeline:",
        f"- Registered: {manifest.get('pipeline', {}).get('registered')}",
        f"- Preflight: {manifest.get('pipeline', {}).get('preflight')}",
        f"- Extraction: {manifest.get('pipeline', {}).get('extraction')}",
        f"- Chunking: {manifest.get('pipeline', {}).get('chunking')}",
        f"- Page Diagnostics: {manifest.get('pipeline', {}).get('page_diagnostics')}",
        f"- Structure Map: {manifest.get('pipeline', {}).get('structure_map')}",
        f"- Reliability: {manifest.get('pipeline', {}).get('reliability')}",
        "",
        "Consistency:",
        f"- Valid Checks: {consistency.get('valid_checks')}",
        f"- Warnings: {consistency.get('warning_checks')}",
        f"- Critical Issues: {consistency.get('critical_checks')}",
        "",
        "Stale Components:",
    ]
    lines.extend([f"- {item}" for item in manifest.get("stale_components", [])] or ["- none"])
    lines.extend(["", "Recommended Action:", str(readiness.get("recommended_action"))])
    text = "\n".join(lines)
    return _sanitize(text) if public_safe else text


def get_document_manifest_summary(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    manifest = build_document_manifest(document_id, regenerate=False, root=root)
    consistency = manifest.get("consistency", {})
    readiness = manifest.get("backend_readiness", {})
    return {
        "document_id": document_id,
        "source_revision": manifest.get("source_revision"),
        "lifecycle_status": manifest.get("lifecycle_status"),
        "backend_readiness": readiness.get("status"),
        "preflight_status": manifest.get("pipeline", {}).get("preflight"),
        "extraction_status": manifest.get("pipeline", {}).get("extraction"),
        "chunk_status": manifest.get("pipeline", {}).get("chunking"),
        "diagnostics_status": manifest.get("pipeline", {}).get("page_diagnostics"),
        "structure_status": manifest.get("pipeline", {}).get("structure_map"),
        "reliability_status": manifest.get("pipeline", {}).get("reliability"),
        "content_map_status": manifest.get("pipeline", {}).get("content_map"),
        "pipeline_fingerprint_changed": bool(manifest.get("fingerprint_changed")),
        "stale_component_count": len(manifest.get("stale_components", [])),
        "consistency_warning_count": consistency.get("warning_checks", 0),
        "consistency_critical_count": consistency.get("critical_checks", 0),
        "recommended_action": readiness.get("recommended_action"),
    }


def ensure_document_manifest_dirs(root: Path | str = SOURCE_DOCUMENT_ROOT) -> Path:
    base = Path(root)
    (base / MANIFEST_DIR).mkdir(parents=True, exist_ok=True)
    (base / "indexes").mkdir(parents=True, exist_ok=True)
    index_path = base / "indexes" / MANIFEST_INDEX
    if not index_path.exists():
        _atomic_write_json(index_path, {"entries": [], "updated_at_utc": _now()})
    return base


def _collect_pipeline_state(document_id: str, revision: dict, root: Path) -> tuple[dict, dict, dict, list[str], list[str]]:
    warnings: list[str] = []
    blockers: list[str] = []
    record = load_source_document(document_id, root=root, missing_ok=True)
    preflight = load_document_preflight(document_id, root=root, missing_ok=True)
    chunks = load_chunks(document_id=document_id, root=root)
    diag_summary = get_page_diagnostic_summary(document_id, root=root)
    structure_summary = get_document_structure_summary(document_id, root=root)
    reliability = _read_json(root / "source_reliability" / f"{document_id}_reliability.json")
    content_map = _read_json(root / "document_content_maps" / f"{document_id}.json")
    queue_items = [item for item in _iter_json(root / "source_impact_queue", "impact_*.json") if item.get("document_id") == document_id]
    resolutions = [item for item in _iter_json(root / "source_revalidation_resolutions", "*.json") if item.get("document_id") == document_id]
    pipeline = {
        "registered": "complete" if record is not None else "missing",
        "preflight": "missing",
        "extraction": "missing",
        "chunking": "missing",
        "page_diagnostics": "missing",
        "structure_map": "missing",
        "reliability": "missing",
        "content_map": "missing",
        "impact_review": "not_applicable",
    }
    if preflight is not None:
        pipeline["preflight"] = "blocked" if preflight.verdict == "BLOCK" else "complete"
    if record is not None:
        if record.extraction_status == STATUS_EXTRACTED:
            pipeline["extraction"] = "complete"
        elif record.extraction_status in {"invalid_pdf", "read_error"}:
            pipeline["extraction"] = "failed"
        elif record.extraction_status in {"extractor_unavailable", "needs_ocr_not_supported"}:
            pipeline["extraction"] = "blocked"
    if chunks:
        pipeline["chunking"] = "complete"
    elif pipeline["extraction"] == "complete":
        pipeline["chunking"] = "missing"
    if int(diag_summary.get("pages_diagnosed", 0) or 0) > 0:
        pipeline["page_diagnostics"] = "complete"
    elif pipeline["extraction"] in {"missing", "blocked", "failed"}:
        pipeline["page_diagnostics"] = "blocked" if pipeline["extraction"] == "blocked" else "missing"
    if structure_summary.get("status") == "built":
        pipeline["structure_map"] = "complete"
    elif pipeline["extraction"] in {"missing", "blocked", "failed"}:
        pipeline["structure_map"] = "blocked" if pipeline["extraction"] == "blocked" else "missing"
    if isinstance(reliability, dict):
        pipeline["reliability"] = "complete"
    if isinstance(content_map, dict):
        pipeline["content_map"] = "complete"
    if queue_items:
        reviewed = any(item.get("status") in {"reviewed", "dismissed"} for item in queue_items)
        pipeline["impact_review"] = "complete" if reviewed or resolutions else "stale"
    if revision.get("revision_changed"):
        for field in ("preflight", "extraction", "chunking", "page_diagnostics", "structure_map", "reliability", "content_map"):
            if pipeline[field] == "complete":
                pipeline[field] = "stale"
    references = {
        "source_record_id": document_id if record else None,
        "preflight_record_id": f"preflight_{document_id}" if preflight else None,
        "extraction_record_id": f"extraction_{document_id}" if record and record.extraction_status == STATUS_EXTRACTED else None,
        "chunk_record_ids": [chunk.chunk_id for chunk in chunks],
        "page_diagnostics_record_id": document_id if int(diag_summary.get("pages_diagnosed", 0) or 0) > 0 else None,
        "structure_map_record_id": f"structure_{document_id}" if structure_summary.get("status") == "built" else None,
        "reliability_record_id": f"reliability_{document_id}" if isinstance(reliability, dict) else None,
        "document_content_map_id": f"content_map_{document_id}" if isinstance(content_map, dict) else None,
    }
    record_hashes = {
        "source_record": _hash_file(root / "indexes" / f"{document_id}.json"),
        "preflight_record": _hash_file(root / "preflight" / f"{document_id}_preflight.json"),
        "extraction_text": _hash_file(root / "extracted_text" / f"{document_id}.txt"),
        "chunk_records": _hash_json_payload(sorted(chunk.chunk_id for chunk in chunks)),
        "page_diagnostics": _hash_file(root / "page_diagnostics" / f"{document_id}.json"),
        "structure_map": _hash_file(root / "structure_maps" / f"{document_id}_structure.json"),
        "reliability_record": _hash_file(root / "source_reliability" / f"{document_id}_reliability.json"),
        "content_map_record": _hash_file(root / "document_content_maps" / f"{document_id}.json"),
    }
    if record is None:
        blockers.append("source_record_missing")
    return pipeline, references, record_hashes, warnings, blockers


def _detect_stale_components(existing: dict | None, revision: dict, record_hashes: dict, pipeline: dict) -> list[str]:
    stale: list[str] = []
    if revision.get("revision_changed"):
        stale.extend(["preflight", "extraction", "chunking", "page_diagnostics", "structure_map", "reliability", "citations_revalidation", "proposals_revalidation", "evidence_binder_recheck"])
    previous_hashes = (existing or {}).get("record_hashes", {})
    if previous_hashes and previous_hashes.get("extraction_text") and previous_hashes.get("extraction_text") != record_hashes.get("extraction_text"):
        stale.extend(["chunking", "page_diagnostics", "structure_map"])
    if previous_hashes and previous_hashes.get("chunk_records") and previous_hashes.get("chunk_records") != record_hashes.get("chunk_records"):
        stale.extend(["citation_locators_revalidation", "proposals_revalidation", "evidence_binder_recheck"])
    return list(dict.fromkeys(item for item in stale if item))


def _lifecycle_status(readiness_status: str, pipeline: dict) -> str:
    if readiness_status == "ready":
        return "ready"
    if readiness_status == "ready_with_warnings":
        return "warning"
    if readiness_status in {"blocked", "corrupt", "stale", "unknown"}:
        return readiness_status
    if pipeline.get("registered") == "complete" and any(value == "complete" for key, value in pipeline.items() if key != "registered"):
        return "processing"
    if pipeline.get("registered") == "complete":
        return "registered"
    return "warning"


def _issue(issue_type: str, record_id: str, severity: str) -> dict[str, object]:
    return {"issue_type": issue_type, "record_id": record_id, "severity": severity, "repair_action": "manual_review_required"}


def _manifest_path(root: Path, document_id: str) -> Path:
    return root / MANIFEST_DIR / f"{document_id}.json"


def _update_manifest_index(root: Path) -> None:
    entries = []
    for path in sorted((root / MANIFEST_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict):
            entries.append(
                {
                    "document_id": payload.get("document_id"),
                    "source_revision": payload.get("source_revision"),
                    "lifecycle_status": payload.get("lifecycle_status"),
                    "backend_readiness": (payload.get("backend_readiness") or {}).get("status"),
                    "updated_at_utc": payload.get("updated_at_utc"),
                }
            )
    _atomic_write_json(root / "indexes" / MANIFEST_INDEX, {"entries": entries, "updated_at_utc": _now()})


def _iter_json(folder: Path, pattern: str):
    if not folder.exists():
        return []
    items = []
    for path in sorted(folder.glob(pattern)):
        payload = _read_json(path)
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _hash_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _hash_json_payload(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _atomic_write_json(path: Path, payload: dict) -> None:
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


def _sanitize(text: str) -> str:
    return text.replace(str(Path.cwd()), "[workspace]").replace(str(SOURCE_DOCUMENT_ROOT), "[source-root]").replace("\\", "/")


def _current_pipeline_fingerprint(document_id: str, root: Path) -> dict[str, object]:
    from .source_workflow_coordinator import calculate_pipeline_state_fingerprint

    return calculate_pipeline_state_fingerprint(document_id, root=root)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
