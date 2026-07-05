from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from .document_content_curation import get_document_content_curation_readiness, load_document_content_curation
from .document_content_map import build_document_scoped_fingerprint, get_reader_backend_readiness, load_document_content_map
from .document_manifest import load_document_manifest
from .document_preflight import get_document_preflight_summary
from .document_structure import load_document_structure_map
from .evidence_binder import load_evidence_binder
from .locator_migration_execution import list_locator_migration_execution_receipts
from .proposal_review import load_proposal_review
from .source_document_reader import get_document_reader_state, load_page_diagnostics
from .source_documents import SOURCE_DOCUMENT_ROOT, STATUS_EXTRACTED, get_extracted_text, list_source_documents, load_source_document
from .source_impact_analysis import list_source_revalidation_queue
from .source_knowledge import list_source_proposals, load_chunks


SCHEMA_VERSION = "backend_contract_validation_v1"
PLAN_SCHEMA_VERSION = "backend_contract_validation_plan_v1"
VALIDATION_DIR = "backend_contract_validations"
INDEX_DIR = "indexes"
INDEX_NAME = "backend_contract_validation_index.json"
ALLOWED_CHECK_STATUSES = {"pass", "warning", "fail", "blocked", "unknown", "not_applicable"}
ALLOWED_SEVERITIES = {"required", "recommended", "optional"}
CERTIFICATION_STATUSES = {
    "certified",
    "certified_with_warnings",
    "not_certified",
    "blocked",
    "stale",
    "corrupt",
    "unknown",
}
TOPIC_INDEX_MODULE = Path(__file__).resolve().parent / "cross_document_topic_index.py"


def build_backend_contract_validation_plan(
    document_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    source = load_source_document(document_id, root=base, missing_ok=True)
    manifest_payload = load_document_manifest(document_id, root=base)
    manifest = manifest_payload.get("manifest") if isinstance(manifest_payload, dict) else None
    warnings: list[str] = []
    blockers: list[str] = []
    if source is None:
        blockers.append("source_not_registered")
    if not isinstance(manifest, dict):
        blockers.append("manifest_missing")
    fingerprint = build_document_scoped_fingerprint(document_id, root=base).get("fingerprint") if source else None
    checks = [
        "source_registration",
        "manifest",
        "preflight",
        "extraction",
        "chunks",
        "page_diagnostics",
        "structure_map",
        "content_map",
        "curation",
        "reader_readiness",
        "citations",
        "proposals",
        "evidence_binders",
        "topic_index_contribution",
        "locator_migration_receipts",
        "revalidation_state",
    ]
    required_checks = [
        check
        for check in checks
        if check
        not in {
            "topic_index_contribution",
            "curation",
        }
    ]
    optional_checks = ["topic_index_contribution"]
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "document_id": document_id,
        "source_revision": (manifest or {}).get("source_revision"),
        "document_scoped_fingerprint": fingerprint,
        "checks": checks,
        "required_checks": required_checks,
        "optional_checks": optional_checks,
        "warnings": warnings,
        "blockers": blockers,
    }


def trace_document_backend_dependencies(
    document_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    source = load_source_document(document_id, root=base, missing_ok=True)
    manifest = load_document_manifest(document_id, root=base).get("manifest")
    preflight = get_document_preflight_summary(document_id, root=base)
    chunks = load_chunks(document_id=document_id, root=base)
    chunk_ids = sorted({chunk.chunk_id for chunk in chunks})
    diagnostics = load_page_diagnostics(document_id, root=base)
    structure = load_document_structure_map(document_id, root=base)
    content_map = load_document_content_map(document_id, root=base).get("content_map")
    curation = load_document_content_curation(document_id, root=base).get("curation")
    citations = _load_document_citations(document_id, chunk_ids=chunk_ids, root=base)
    proposals = [proposal.to_json(public_safe=True) for proposal in list_source_proposals(document_id=document_id, root=base)]
    proposal_ids = sorted({str(item.get("proposal_id") or "") for item in proposals if item.get("proposal_id")})
    reviews = []
    binder_ids: list[str] = []
    for proposal_id in proposal_ids:
        review = load_proposal_review(proposal_id, root=base, missing_ok=True)
        if review is not None:
            reviews.append({"proposal_id": proposal_id, "review_id": getattr(review, "review_id", f"review_{proposal_id}")})
        binder = load_evidence_binder(proposal_id, root=base)
        if isinstance(binder, dict) and binder.get("binder_status") != "not_built":
            binder_ids.append(str(binder.get("binder_id") or f"binder_{proposal_id}"))
    receipts = list_locator_migration_execution_receipts(document_id=document_id, limit=500, root=base).get("items", [])
    queue = [item for item in list_source_revalidation_queue(limit=500, root=base).get("items", []) if str(item.get("document_id") or "") == document_id]
    pending_queue = [item for item in queue if item.get("status") == "pending_review"]
    planner_ids = sorted(
        {
            str(item.get("migration_plan_id") or "")
            for item in _iter_json(base / "locator_migration_plans", "*.json")
            if str(item.get("document_id") or "") == document_id and item.get("migration_plan_id")
        }
    )
    topic_contributions = _load_topic_index_contributions(document_id, base)
    missing_required_records: list[str] = []
    missing_optional_records: list[str] = []
    if source is None:
        missing_required_records.append("source_record")
    if not isinstance(manifest, dict):
        missing_required_records.append("manifest")
    if not preflight.get("has_preflight"):
        missing_required_records.append("preflight")
    if not chunks:
        missing_required_records.append("chunks")
    if not diagnostics:
        missing_required_records.append("page_diagnostics")
    if not isinstance(structure, dict) or structure.get("status") == "not_built":
        missing_required_records.append("structure_map")
    if not isinstance(content_map, dict):
        missing_required_records.append("content_map")
    if not TOPIC_INDEX_MODULE.exists():
        missing_optional_records.append("topic_index")
    return {
        "document_id": document_id,
        "source_revision": (manifest or {}).get("source_revision"),
        "record_counts": {
            "chunks": len(chunk_ids),
            "citations": len(citations),
            "proposals": len(proposal_ids),
            "proposal_reviews": len(reviews),
            "evidence_binders": len(binder_ids),
            "migration_plans": len(planner_ids),
            "migration_receipts": len(receipts),
            "pending_revalidation": len(pending_queue),
            "topic_index_contributions": len(topic_contributions),
        },
        "record_ids": {
            "source_record": [document_id] if source else [],
            "manifest": [str((manifest or {}).get("manifest_id") or f"manifest_{document_id}")] if manifest else [],
            "chunks": chunk_ids,
            "citations": sorted({str(item.get("citation_id") or "") for item in citations if item.get("citation_id")}),
            "proposals": proposal_ids,
            "proposal_reviews": sorted({str(item.get("review_id") or "") for item in reviews if item.get("review_id")}),
            "evidence_binders": sorted(set(binder_ids)),
            "locator_migration_plans": planner_ids,
            "locator_migration_receipts": sorted({str(item.get("execution_id") or "") for item in receipts if item.get("execution_id")}),
            "revalidation_records": sorted({str(item.get("queue_item_id") or "") for item in queue if item.get("queue_item_id")}),
            "topic_index_contributions": sorted({str(item.get("document_id") or "") for item in topic_contributions if item.get("document_id")}),
            "curation_overlay": [document_id] if isinstance(curation, dict) else [],
        },
        "missing_required_records": missing_required_records,
        "missing_optional_records": missing_optional_records,
        "warnings": [],
    }


def run_backend_contract_validation(
    document_id: str,
    regenerate: bool = False,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    plan = build_backend_contract_validation_plan(document_id, root=base)
    state_signature = _build_state_signature(document_id, root=base)
    if not regenerate:
        existing = _latest_validation_for_document(document_id, root=base)
        if existing:
            existing_sig = existing.get("state_signature")
            if existing.get("schema_version") == SCHEMA_VERSION and existing_sig == state_signature:
                current = _mark_validation_current(existing, True)
                return {"status": current.get("certification_status"), "validation": current, "reused": True}
    trace = trace_document_backend_dependencies(document_id, root=base)
    checks = _run_checks(document_id, plan=plan, trace=trace, root=base)
    certification = _derive_certification(checks)
    counters = Counter(item["status"] for item in checks)
    warnings = [item["message"] for item in checks if item["status"] == "warning"]
    blockers = [item["message"] for item in checks if item["status"] in {"fail", "blocked", "unknown"} and item["severity"] == "required"]
    validation_fingerprint = _json_hash(
        {
            "state_signature": state_signature,
            "checks": [{k: item.get(k) for k in ("check_id", "status", "severity", "record_ids")} for item in checks],
            "certification_status": certification,
        }
    )
    validation_id = f"backend_validation_{document_id}_{validation_fingerprint.split(':', 1)[-1][:16]}"
    existing = load_backend_contract_validation(validation_id, root=base).get("validation")
    now = _now()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "validation_id": validation_id,
        "document_id": document_id,
        "source_revision": state_signature.get("source_revision"),
        "document_scoped_fingerprint": state_signature.get("document_scoped_fingerprint"),
        "validation_fingerprint": validation_fingerprint,
        "certification_status": certification,
        "required_pass_count": len([item for item in checks if item["severity"] == "required" and item["status"] == "pass"]),
        "warning_count": counters.get("warning", 0),
        "failure_count": counters.get("fail", 0),
        "blocked_count": counters.get("blocked", 0),
        "checks": checks,
        "dependency_summary": trace,
        "reader_backend_readiness": _reader_readiness_from_checks(checks),
        "recommended_action": _recommended_action(checks, certification),
        "created_at_utc": existing.get("created_at_utc") if isinstance(existing, dict) else now,
        "updated_at_utc": now,
        "warnings": warnings,
        "blockers": blockers,
        "state_signature": state_signature,
        "validation_current": True,
    }
    _atomic_write_json(_validation_path(base, validation_id), payload)
    _update_validation_index(base)
    return {"status": certification, "validation": payload, "reused": False}


def load_backend_contract_validation(
    validation_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    payload = _read_json(_validation_path(base, validation_id))
    if not isinstance(payload, dict):
        return {"validation_id": validation_id, "status": "not_found", "validation": None, "warnings": []}
    current = _validation_is_current(payload, root=base)
    return {
        "validation_id": validation_id,
        "status": "loaded",
        "validation": _mark_validation_current(payload, current),
        "warnings": [] if current else ["validation_stale"],
    }


def list_backend_contract_validations(
    document_id: str | None = None,
    certification_status: str | None = None,
    limit: int = 100,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    items: list[dict[str, Any]] = []
    for path in sorted((base / VALIDATION_DIR).glob("backend_validation_*.json")):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        if document_id and str(payload.get("document_id") or "") != document_id:
            continue
        if certification_status and str(payload.get("certification_status") or "") != certification_status:
            continue
        items.append(_mark_validation_current(payload, _validation_is_current(payload, root=base)))
    items.sort(key=lambda item: (str(item.get("created_at_utc") or ""), str(item.get("validation_id") or "")), reverse=True)
    limited = items[: max(0, int(limit or 0))]
    return {"count": len(limited), "items": limited}


def get_backend_contract_validation_health(
    document_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    warnings: list[str] = []
    try:
        index = _read_json(base / INDEX_DIR / INDEX_NAME)
    except Exception:
        index = None
    if not isinstance(index, dict):
        warnings.append("validation_index_unreadable")
    items = list_backend_contract_validations(document_id=document_id, limit=500, root=base).get("items", [])
    stale = [item for item in items if not item.get("validation_current")]
    certified = [item for item in items if item.get("certification_status") == "certified"]
    certified_warn = [item for item in items if item.get("certification_status") == "certified_with_warnings"]
    blocked = [item for item in items if item.get("certification_status") == "blocked"]
    corrupt = [item for item in items if item.get("certification_status") == "corrupt"]
    docs = [doc.document_id for doc in list_source_documents(root=base)]
    docs_without = 0
    if document_id:
        docs_without = 0 if items else 1
    else:
        docs_without = len([doc_id for doc_id in docs if not any(str(item.get("document_id") or "") == doc_id for item in items)])
    receipts = list_locator_migration_execution_receipts(document_id=document_id, limit=500, root=base).get("items", [])
    rollback_failed = len([item for item in receipts if item.get("status") == "rollback_failed"])
    critical_pending = len(
        [
            item
            for item in list_source_revalidation_queue(limit=500, root=base).get("items", [])
            if (document_id is None or str(item.get("document_id") or "") == document_id)
            and item.get("status") == "pending_review"
            and str(item.get("impact_severity") or "").lower() == "critical"
        ]
    )
    if stale:
        warnings.append("one_validation_is_stale")
    if docs_without:
        warnings.append("documents_without_validation")
    if rollback_failed:
        warnings.append("rollback_failed_receipts_present")
    if critical_pending:
        warnings.append("critical_revalidation_pending")
    status = "healthy"
    if corrupt or blocked or rollback_failed or critical_pending:
        status = "critical"
    elif warnings:
        status = "warning"
    return {
        "status": status,
        "validation_count": len(items),
        "current_validation_count": len([item for item in items if item.get("validation_current")]),
        "stale_validation_count": len(stale),
        "certified_count": len(certified),
        "certified_with_warnings_count": len(certified_warn),
        "blocked_count": len(blocked),
        "corrupt_count": len(corrupt),
        "warnings": warnings,
        "recommended_action": "Re-run validation for one changed document." if stale else "Run validation for one registered document." if docs_without else "No action required.",
    }


def format_backend_contract_validation_report(
    validation_id: str | None = None,
    document_id: str | None = None,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    validation: dict[str, Any] | None = None
    if validation_id:
        validation = load_backend_contract_validation(validation_id, root=root).get("validation")
    elif document_id:
        items = list_backend_contract_validations(document_id=document_id, limit=1, root=root).get("items", [])
        validation = items[0] if items else None
    if not isinstance(validation, dict):
        return "Backend Contract Validation Report\n\nNo validation record was found."
    dependency = validation.get("dependency_summary", {}) if isinstance(validation.get("dependency_summary"), dict) else {}
    lines = [
        "Backend Contract Validation Report",
        "",
        f"Document: {validation.get('document_id')}",
        f"Source Revision: {validation.get('source_revision')}",
        f"Certification: {validation.get('certification_status')}",
        f"Reader Backend Readiness: {validation.get('reader_backend_readiness')}",
        "",
        "Required Contract Checks:",
        f"- Passed: {validation.get('required_pass_count', 0)}",
        f"- Failed: {validation.get('failure_count', 0)}",
        f"- Blocked: {validation.get('blocked_count', 0)}",
        "",
        "Content:",
        f"- Extraction: {_report_check_status(validation, 'extraction_usable')}",
        f"- Chunks: {_report_check_status(validation, 'chunks_present')}",
        f"- Page Diagnostics: {_report_check_status(validation, 'page_diagnostics_present')}",
        f"- Structure Map: {_report_check_status(validation, 'structure_map_present')}",
        f"- Content Map: {_report_check_status(validation, 'content_map_current')}",
        f"- Curation: {_report_check_status(validation, 'curation_state_safe')}",
        "",
        "Provenance:",
        f"- Citations Checked: {dependency.get('record_counts', {}).get('citations', 0)}",
        f"- Evidence Binders Checked: {dependency.get('record_counts', {}).get('evidence_binders', 0)}",
        f"- Critical Issues: {len([item for item in validation.get('checks', []) if item.get('status') in {'fail', 'blocked'} and item.get('severity') == 'required'])}",
        "",
        "Migration and Revalidation:",
        f"- Completed Locator Migrations: {len([item for item in _as_list(dependency.get('record_ids', {}).get('locator_migration_receipts')) if item])}",
        f"- Rollback Failures: {len([item for item in validation.get('checks', []) if item.get('check_id') == 'migration_rollback_failures_absent' and item.get('status') == 'blocked'])}",
        f"- Pending Revalidation Items: {dependency.get('record_counts', {}).get('pending_revalidation', 0)}",
        "",
        "Recommended Action:",
        str(validation.get("recommended_action") or "No action required."),
    ]
    text = "\n".join(lines)
    return _sanitize_text(text) if public_safe else text


def get_backend_contract_validation_summary(
    document_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    items = list_backend_contract_validations(document_id=document_id, limit=1, root=root).get("items", [])
    if not items:
        return {
            "document_id": document_id,
            "source_revision": None,
            "certification_status": "unknown",
            "validation_current": False,
            "required_pass_count": 0,
            "warning_count": 0,
            "failure_count": 0,
            "blocked_count": 0,
            "reader_backend_readiness": "unknown",
            "citation_count": 0,
            "evidence_binder_count": 0,
            "pending_revalidation_count": 0,
            "rollback_failure_count": 0,
            "recommended_action": "Run contract validation for one registered document.",
        }
    item = items[0]
    dependency = item.get("dependency_summary", {}) if isinstance(item.get("dependency_summary"), dict) else {}
    checks = item.get("checks", []) if isinstance(item.get("checks"), list) else []
    return {
        "document_id": item.get("document_id"),
        "validation_id": item.get("validation_id"),
        "source_revision": item.get("source_revision"),
        "certification_status": item.get("certification_status"),
        "validation_current": bool(item.get("validation_current")),
        "required_pass_count": item.get("required_pass_count", 0),
        "warning_count": item.get("warning_count", 0),
        "failure_count": item.get("failure_count", 0),
        "blocked_count": item.get("blocked_count", 0),
        "reader_backend_readiness": item.get("reader_backend_readiness"),
        "citation_count": dependency.get("record_counts", {}).get("citations", 0),
        "evidence_binder_count": dependency.get("record_counts", {}).get("evidence_binders", 0),
        "pending_revalidation_count": dependency.get("record_counts", {}).get("pending_revalidation", 0),
        "rollback_failure_count": len([entry for entry in checks if entry.get("check_id") == "migration_rollback_failures_absent" and entry.get("status") == "blocked"]),
        "recommended_action": item.get("recommended_action"),
    }


def _run_checks(document_id: str, *, plan: dict[str, Any], trace: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    source = load_source_document(document_id, root=root, missing_ok=True)
    manifest = load_document_manifest(document_id, root=root).get("manifest")
    preflight = get_document_preflight_summary(document_id, root=root)
    content_map = load_document_content_map(document_id, root=root).get("content_map")
    curation = load_document_content_curation(document_id, root=root).get("curation")
    curation_readiness = get_document_content_curation_readiness(document_id, root=root)
    reader_readiness = get_reader_backend_readiness(document_id, root=root)
    diagnostics = load_page_diagnostics(document_id, root=root)
    structure = load_document_structure_map(document_id, root=root)
    chunks = load_chunks(document_id=document_id, root=root)
    chunk_map = {chunk.chunk_id: chunk for chunk in chunks}
    chunk_ids = sorted(chunk_map)
    citations = _load_document_citations(document_id, chunk_ids=chunk_ids, root=root)
    proposals = [proposal.to_json(public_safe=True) for proposal in list_source_proposals(document_id=document_id, root=root)]
    proposal_ids = {str(item.get("proposal_id") or "") for item in proposals if item.get("proposal_id")}
    citation_ids = {str(item.get("citation_id") or "") for item in citations if item.get("citation_id")}
    binder_count = 0
    binder_issues = 0
    for proposal_id in sorted(proposal_ids):
        binder = load_evidence_binder(proposal_id, root=root)
        if not isinstance(binder, dict) or binder.get("binder_status") == "not_built":
            continue
        binder_count += 1
        for linked in _as_list(binder.get("linked_citations")):
            linked_id = str(linked.get("citation_id") or "")
            if linked_id and linked_id not in citation_ids:
                binder_issues += 1
    receipts = list_locator_migration_execution_receipts(document_id=document_id, limit=500, root=root).get("items", [])
    queue_items = [item for item in list_source_revalidation_queue(limit=500, root=root).get("items", []) if str(item.get("document_id") or "") == document_id]
    current_fp = build_document_scoped_fingerprint(document_id, root=root).get("fingerprint") if source else None

    checks.append(_check("source_registered", "source_identity", "pass" if source else "blocked", "required", [document_id], "Registered source exists.", "Register the source document first."))
    checks.append(
        _check(
            "manifest_current",
            "source_identity",
            "pass" if isinstance(manifest, dict) and manifest.get("source_revision") else "fail",
            "required",
            [str((manifest or {}).get("manifest_id") or f"manifest_{document_id}")],
            "Manifest is available for the selected document." if isinstance(manifest, dict) else "Manifest is missing for the selected document.",
            "Build the canonical manifest before certification." if not isinstance(manifest, dict) else None,
        )
    )
    manifest_fp_ok = isinstance(manifest, dict) and bool(manifest.get("pipeline_fingerprint"))
    checks.append(_check("manifest_fingerprint_current", "source_identity", "pass" if manifest_fp_ok else "fail", "required", [str((manifest or {}).get("manifest_id") or f"manifest_{document_id}")], "Manifest fingerprint is current." if manifest_fp_ok else "Manifest fingerprint is missing.", "Refresh the manifest fingerprint."))
    checks.append(
        _check(
            "preflight_not_blocked",
            "reader_foundation",
            "pass" if preflight.get("verdict") != "BLOCK" else "fail",
            "required",
            [f"preflight_{document_id}"] if preflight.get("has_preflight") else [],
            "Preflight is not blocked." if preflight.get("verdict") != "BLOCK" else "Preflight is blocked.",
            preflight.get("recommended_action"),
        )
    )
    text_present = False
    if source and source.extraction_status == STATUS_EXTRACTED:
        try:
            text_present = bool(get_extracted_text(document_id, root=root).strip())
        except Exception:
            text_present = False
    checks.append(_check("extraction_usable", "reader_foundation", "pass" if text_present else "fail", "required", [document_id], "Extraction is usable." if text_present else "Extraction is not usable.", "Extract text before certification."))
    chunks_present = bool(chunks)
    checks.append(_check("chunks_present", "reader_foundation", "pass" if chunks_present else "fail", "required", chunk_ids, "Chunks exist for the document." if chunks_present else "Chunks are missing for the document.", "Create controlled chunks before certification."))
    chunk_unique = len(chunk_ids) == len(chunks)
    checks.append(_check("chunk_ids_unique", "reader_foundation", "pass" if chunk_unique else "fail", "required", chunk_ids, "Chunk IDs are unique." if chunk_unique else "Chunk IDs are not unique.", "Repair chunk identity conflicts."))
    pages_valid = bool(chunks) and all(_valid_page_range(chunk.page_start, chunk.page_end) for chunk in chunks)
    checks.append(_check("chunk_page_ranges_valid", "reader_foundation", "pass" if pages_valid else "fail", "required", chunk_ids, "Chunk page references are valid." if pages_valid else "One or more chunk page references are invalid.", "Repair invalid chunk page references."))
    checks.append(_check("page_diagnostics_present", "reader_foundation", "pass" if diagnostics else "fail", "required", [document_id] if diagnostics else [], "Page diagnostics exist." if diagnostics else "Page diagnostics are missing.", "Build page diagnostics before certification."))
    structure_ok = isinstance(structure, dict) and structure.get("status") != "not_built"
    checks.append(_check("structure_map_present", "reader_foundation", "pass" if structure_ok else "fail", "required", [str((structure or {}).get("structure_id") or f"structure_{document_id}")], "Structure map exists." if structure_ok else "Structure map is missing.", "Build the structure map before certification."))
    content_map_ok = isinstance(content_map, dict)
    checks.append(_check("content_map_current", "content_organization", "pass" if content_map_ok and content_map.get("source_revision") == (manifest or {}).get("source_revision") else "fail", "required", [str((content_map or {}).get("content_map_id") or f"content_map_{document_id}")], "Content map is current." if content_map_ok and content_map.get("source_revision") == (manifest or {}).get("source_revision") else "Content map is missing or stale.", "Rebuild the content map after backend changes."))
    fp_match = content_map_ok and str(content_map.get("document_scoped_fingerprint") or "").startswith("sha256:")
    checks.append(_check("content_map_fingerprint_current", "content_organization", "pass" if fp_match else "fail", "required", [str((content_map or {}).get("content_map_id") or f"content_map_{document_id}")], "Content-map fingerprint matches current document state." if fp_match else "Content-map fingerprint does not match current document state.", "Refresh the content map fingerprint."))
    ranges_valid = _content_ranges_valid(content_map, chunk_ids)
    checks.append(_check("content_ranges_valid", "content_organization", "pass" if ranges_valid else "fail", "required", [str((content_map or {}).get("content_map_id") or f"content_map_{document_id}")], "Chapter and section ranges are valid." if ranges_valid else "Chapter or section ranges are invalid.", "Repair the content-map ranges."))
    unassigned_ok = bool(content_map_ok)
    checks.append(_check("unassigned_chunks_reported", "content_organization", "pass" if unassigned_ok else "unknown", "recommended", [str((content_map or {}).get("content_map_id") or f"content_map_{document_id}")], "Unassigned chunks are reported in the content map." if unassigned_ok else "Content map was unavailable for unassigned chunk reporting.", "Inspect unassigned chunks after rebuilding the content map."))
    curation_status = str(curation_readiness.get("status") or "not_ready")
    curation_check_status = "not_applicable"
    curation_message = "No curation overlay is active."
    if isinstance(curation, dict):
        if curation_status in {"ready", "ready_with_warnings"}:
            curation_check_status = "pass"
            curation_message = "Current curation is active and safe to use."
        elif curation_status in {"stale", "invalid", "unknown", "not_ready"}:
            curation_check_status = "warning"
            curation_message = "Curation is present but is being safely ignored."
    checks.append(_check("curation_state_safe", "content_organization", curation_check_status, "recommended", [document_id] if isinstance(curation, dict) else [], curation_message, "Review the curation overlay state."))
    reader_consistent = str((content_map or {}).get("reader_backend_readiness") or "unknown") == str(reader_readiness.get("status") or "unknown")
    checks.append(_check("reader_backend_readiness_consistent", "content_organization", "pass" if reader_consistent else "fail", "required", [str((content_map or {}).get("content_map_id") or f"content_map_{document_id}")], "Reader-backend readiness is consistent with observed records." if reader_consistent else "Reader-backend readiness is inconsistent with observed records.", reader_readiness.get("recommended_action")))

    citation_doc_ok = True
    citation_chunk_ok = True
    contradictions = False
    citation_record_ids = []
    for citation in citations:
        citation_id = str(citation.get("citation_id") or "")
        citation_record_ids.append(citation_id)
        chunk = chunk_map.get(str(citation.get("chunk_id") or ""))
        if str(citation.get("document_id") or "") != document_id:
            citation_doc_ok = False
        if chunk is None:
            citation_chunk_ok = False
        elif chunk.document_id != str(citation.get("document_id") or ""):
            contradictions = True
    checks.append(_check("citation_document_ids_correct", "provenance", "pass" if citation_doc_ok else "blocked", "required", citation_record_ids, "Citation document IDs are correct." if citation_doc_ok else "One or more citation document IDs contradict the selected document.", "Repair citation document IDs before PDF-reader release."))
    checks.append(_check("citation_chunk_ids_exist", "provenance", "pass" if citation_chunk_ok else "fail", "required", citation_record_ids, "Citation chunk IDs exist." if citation_chunk_ok else "One or more citation chunk IDs are missing.", "Repair stale citation chunk references."))
    checks.append(_check("cross_document_locator_contradictions_absent", "provenance", "blocked" if contradictions else "pass", "required", citation_record_ids, "Cross-document locator contradictions are absent." if not contradictions else "A citation locator contradicts the selected document scope.", "Repair cross-document locator contradictions before certification."))

    proposal_refs_ok = all(set(_as_list(item.get("citation_ids"))).issubset(citation_ids) for item in proposals)
    checks.append(_check("proposal_citation_references_exist", "provenance", "pass" if proposal_refs_ok else "fail", "required", sorted(proposal_ids), "Proposal citation references exist." if proposal_refs_ok else "One or more proposals reference missing citations.", "Repair proposal citation references."))
    review_refs_ok = True
    review_ids: list[str] = []
    for proposal_id in sorted(proposal_ids):
        review = load_proposal_review(proposal_id, root=root, missing_ok=True)
        if review is None:
            continue
        review_ids.append(str(getattr(review, "review_id", f"review_{proposal_id}")))
        if str(getattr(review, "proposal_id", proposal_id)) != proposal_id:
            review_refs_ok = False
    checks.append(_check("proposal_reviews_reference_existing_proposals", "provenance", "pass" if review_refs_ok else "fail", "required", review_ids, "Proposal reviews reference existing proposals." if review_refs_ok else "A proposal review references a missing or mismatched proposal.", "Repair proposal-review references."))
    checks.append(_check("evidence_binder_references_exist", "provenance", "pass" if binder_issues == 0 else "fail", "required", sorted(proposal_ids), "Evidence binder references exist." if binder_issues == 0 else "One or more evidence binders reference missing citations.", "Repair evidence-binder references."))

    topic_contributions = _load_topic_index_contributions(document_id, root)
    topic_status = "not_applicable"
    topic_message = "No topic-index contribution state was required for this document."
    topic_recommended = None
    has_topic_tags = bool(content_map_ok and _as_list((content_map or {}).get("topic_tags")))
    if has_topic_tags and not TOPIC_INDEX_MODULE.exists():
        topic_status = "warning"
        topic_message = "Topic-index support is unavailable; topic contribution state could not be verified."
        topic_recommended = "Review topic-index support before future reader release."
    elif topic_contributions:
        topic_status = "pass"
        topic_message = "Topic contributions are scoped to the selected document."
    checks.append(_check("topic_index_contribution_state", "topic_integration", topic_status, "optional", [str(item.get("document_id") or "") for item in topic_contributions], topic_message, topic_recommended))

    rollback_failed = [item for item in receipts if item.get("status") == "rollback_failed"]
    receipt_schemas_ok = all(str(item.get("schema_version") or "").startswith("locator_migration_execution") for item in receipts if isinstance(item, dict))
    after_hash_ok = all(bool(item.get("after_state_hashes")) for item in receipts if item.get("status") in {"completed", "already_applied"})
    revalidation_receipts_ok = all(bool(item.get("revalidation_queue_item_id")) for item in receipts if item.get("status") == "completed")
    checks.append(_check("migration_receipt_schema_valid", "migration_state", "pass" if receipt_schemas_ok else "fail", "required", [str(item.get("execution_id") or "") for item in receipts], "Completed migration receipts use valid schemas." if receipt_schemas_ok else "One or more migration receipts are malformed.", "Repair malformed migration receipts."))
    checks.append(_check("migration_after_state_hashes_consistent", "migration_state", "pass" if after_hash_ok else "fail", "required", [str(item.get("execution_id") or "") for item in receipts], "Completed migration receipts include after-state hashes." if after_hash_ok else "One or more completed migration receipts are missing after-state hashes.", "Inspect locator migration execution receipts."))
    checks.append(_check("migration_revalidation_items_exist", "migration_state", "pass" if revalidation_receipts_ok else "fail", "required", [str(item.get("execution_id") or "") for item in receipts if item.get("status") == "completed"], "Migration-created revalidation items exist." if revalidation_receipts_ok else "A completed migration receipt is missing its revalidation item.", "Create and review the missing revalidation item manually."))
    checks.append(_check("migration_rollback_failures_absent", "migration_state", "pass" if not rollback_failed else "blocked", "required", [str(item.get("execution_id") or "") for item in rollback_failed], "No rollback-failed locator migration receipts were found." if not rollback_failed else "A rollback-failed locator migration receipt was found.", "Resolve rollback-failed locator migration receipts before release."))

    critical_pending = [item for item in queue_items if item.get("status") == "pending_review" and str(item.get("impact_severity") or "").lower() == "critical"]
    closed_resolution_ok = True
    for item in queue_items:
        if item.get("status") == "pending_review":
            continue
        resolution = _load_revalidation_resolution(str(item.get("queue_item_id") or ""), root)
        if not isinstance(resolution, dict):
            closed_resolution_ok = False
            break
    checks.append(_check("pending_revalidation_reported", "revalidation_state", "warning" if queue_items else "not_applicable", "recommended", [str(item.get("queue_item_id") or "") for item in queue_items], "Pending revalidation items are reported." if queue_items else "No revalidation items were found.", "Review pending revalidation items before PDF-reader release." if queue_items else None))
    checks.append(_check("closed_revalidation_has_resolution", "revalidation_state", "pass" if closed_resolution_ok else "fail", "required", [str(item.get("queue_item_id") or "") for item in queue_items if item.get("status") != "pending_review"], "Closed revalidation items have valid resolutions." if closed_resolution_ok else "One or more closed revalidation items are missing resolutions.", "Repair the missing revalidation resolution records."))
    checks.append(_check("critical_unresolved_provenance_absent", "revalidation_state", "blocked" if critical_pending else "pass", "required", [str(item.get("queue_item_id") or "") for item in critical_pending], "No critical unresolved revalidation items were found." if not critical_pending else "A critical unresolved revalidation item blocks certification.", "Resolve the critical revalidation item before PDF-reader release."))
    return checks


def _derive_certification(checks: list[dict[str, Any]]) -> str:
    if any(item["status"] == "blocked" and item["severity"] == "required" for item in checks):
        return "blocked"
    if any(item["status"] == "unknown" and item["severity"] == "required" for item in checks):
        return "unknown"
    if any(item["status"] == "fail" and item["severity"] == "required" for item in checks):
        return "not_certified"
    if any(item["status"] == "warning" for item in checks):
        return "certified_with_warnings"
    return "certified"


def _build_state_signature(document_id: str, *, root: Path) -> dict[str, Any]:
    source = load_source_document(document_id, root=root, missing_ok=True)
    manifest = load_document_manifest(document_id, root=root).get("manifest")
    content_map = load_document_content_map(document_id, root=root).get("content_map")
    curation = load_document_content_curation(document_id, root=root).get("curation")
    curation_readiness = get_document_content_curation_readiness(document_id, root=root)
    chunk_ids = sorted(chunk.chunk_id for chunk in load_chunks(document_id=document_id, root=root))
    citations = _load_document_citations(document_id, chunk_ids=chunk_ids, root=root)
    receipts = list_locator_migration_execution_receipts(document_id=document_id, limit=500, root=root).get("items", [])
    queue = [item for item in list_source_revalidation_queue(limit=500, root=root).get("items", []) if str(item.get("document_id") or "") == document_id]
    return {
        "document_id": document_id,
        "source_revision": (manifest or {}).get("source_revision"),
        "document_scoped_fingerprint": build_document_scoped_fingerprint(document_id, root=root).get("fingerprint") if source else None,
        "manifest_fingerprint": (manifest or {}).get("pipeline_fingerprint"),
        "content_map_fingerprint": (content_map or {}).get("document_scoped_fingerprint"),
        "content_map_revision": (content_map or {}).get("source_revision"),
        "curation_signature": {
            "status": curation_readiness.get("status"),
            "revision": (curation or {}).get("curation_revision"),
            "source_revision": (curation or {}).get("source_revision"),
            "base_fingerprint": (curation or {}).get("base_content_map_fingerprint"),
        },
        "citation_signature": [
            {
                "citation_id": item.get("citation_id"),
                "chunk_id": item.get("chunk_id"),
                "document_id": item.get("document_id"),
                "source_revision": item.get("source_revision"),
            }
            for item in sorted(citations, key=lambda entry: str(entry.get("citation_id") or ""))
        ],
        "proposal_signature": sorted(
            [
                {
                    "proposal_id": proposal.proposal_id,
                    "chunk_id": proposal.chunk_id,
                    "document_id": proposal.document_id,
                    "citation_ids": list(getattr(proposal, "citation_ids", []) or []),
                }
                for proposal in list_source_proposals(document_id=document_id, root=root)
            ],
            key=lambda item: str(item.get("proposal_id") or ""),
        ),
        "binder_signature": sorted(
            [
                {
                    "proposal_id": proposal.proposal_id,
                    "binder_status": (load_evidence_binder(proposal.proposal_id, root=root) or {}).get("binder_status"),
                }
                for proposal in list_source_proposals(document_id=document_id, root=root)
            ],
            key=lambda item: str(item.get("proposal_id") or ""),
        ),
        "migration_receipts": sorted(
            [
                {
                    "execution_id": item.get("execution_id"),
                    "status": item.get("status"),
                    "revalidation_queue_item_id": item.get("revalidation_queue_item_id"),
                    "after_state_hashes": item.get("after_state_hashes"),
                }
                for item in receipts
            ],
            key=lambda item: str(item.get("execution_id") or ""),
        ),
        "revalidation_state": sorted(
            [
                {
                    "queue_item_id": item.get("queue_item_id"),
                    "status": item.get("status"),
                    "impact_severity": item.get("impact_severity"),
                }
                for item in queue
            ],
            key=lambda item: str(item.get("queue_item_id") or ""),
        ),
    }


def _validation_is_current(validation: Mapping[str, Any], *, root: Path) -> bool:
    document_id = str(validation.get("document_id") or "")
    if not document_id:
        return False
    return validation.get("state_signature") == _build_state_signature(document_id, root=root)


def _mark_validation_current(validation: Mapping[str, Any], current: bool) -> dict[str, Any]:
    payload = json.loads(json.dumps(validation, sort_keys=True, default=str))
    payload["validation_current"] = bool(current)
    if not current and payload.get("certification_status") in CERTIFICATION_STATUSES:
        payload["previous_validation_status"] = payload.get("certification_status")
        payload["certification_status"] = "stale"
    return payload


def _latest_validation_for_document(document_id: str, *, root: Path) -> dict[str, Any] | None:
    items = list_backend_contract_validations(document_id=document_id, limit=1, root=root).get("items", [])
    return items[0] if items else None


def _update_validation_index(root: Path) -> None:
    entries = []
    for path in sorted((root / VALIDATION_DIR).glob("backend_validation_*.json")):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        entries.append(
            {
                "validation_id": payload.get("validation_id"),
                "document_id": payload.get("document_id"),
                "source_revision": payload.get("source_revision"),
                "certification_status": payload.get("certification_status"),
                "created_at_utc": payload.get("created_at_utc"),
                "updated_at_utc": payload.get("updated_at_utc"),
            }
        )
    _atomic_write_json(root / INDEX_DIR / INDEX_NAME, {"entries": entries, "updated_at_utc": _now()})


def _load_document_citations(document_id: str, *, chunk_ids: Iterable[str], root: Path) -> list[dict[str, Any]]:
    chunk_id_set = set(chunk_ids)
    citations = []
    for item in _iter_json(root / "citations", "*.json"):
        item_doc = str(item.get("document_id") or "")
        item_chunk = str(item.get("chunk_id") or "")
        if item_doc == document_id or item_chunk in chunk_id_set:
            citations.append(item)
    citations.sort(key=lambda item: str(item.get("citation_id") or ""))
    return citations


def _load_topic_index_contributions(document_id: str, root: Path) -> list[dict[str, Any]]:
    if not TOPIC_INDEX_MODULE.exists():
        return []
    contributions = []
    for item in _iter_json(root / "indexes", "*topic*.json"):
        if str(item.get("document_id") or "") == document_id:
            contributions.append(item)
        elif isinstance(item.get("entries"), list):
            for entry in item["entries"]:
                if isinstance(entry, dict) and str(entry.get("document_id") or "") == document_id:
                    contributions.append(entry)
    return contributions


def _load_revalidation_resolution(queue_item_id: str, root: Path) -> dict[str, Any] | None:
    path = root / "source_revalidation_resolutions" / f"{queue_item_id}.json"
    payload = _read_json(path)
    return payload if isinstance(payload, dict) else None


def _content_ranges_valid(content_map: Mapping[str, Any] | None, chunk_ids: Iterable[str]) -> bool:
    if not isinstance(content_map, Mapping):
        return False
    known_chunks = set(chunk_ids)
    for chapter in _as_list(content_map.get("chapters")):
        if not _valid_page_range(chapter.get("start_page"), chapter.get("end_page")):
            return False
        if chapter.get("start_chunk_id") and str(chapter.get("start_chunk_id")) not in known_chunks:
            return False
        if chapter.get("end_chunk_id") and str(chapter.get("end_chunk_id")) not in known_chunks:
            return False
    for section in _as_list(content_map.get("sections")):
        if not _valid_page_range(section.get("start_page"), section.get("end_page")):
            return False
        if section.get("start_chunk_id") and str(section.get("start_chunk_id")) not in known_chunks:
            return False
        if section.get("end_chunk_id") and str(section.get("end_chunk_id")) not in known_chunks:
            return False
        for chunk_id in _as_list(section.get("chunk_ids")):
            if str(chunk_id) not in known_chunks:
                return False
    return True


def _valid_page_range(start: Any, end: Any) -> bool:
    if start is None or end is None:
        return False
    if isinstance(start, bool) or isinstance(end, bool):
        return False
    if not isinstance(start, int) or not isinstance(end, int):
        return False
    return start > 0 and end > 0 and start <= end


def _check(
    check_id: str,
    category: str,
    status: str,
    severity: str,
    record_ids: list[str],
    message: str,
    recommended_action: str | None,
) -> dict[str, Any]:
    normalized_status = status if status in ALLOWED_CHECK_STATUSES else "unknown"
    normalized_severity = severity if severity in ALLOWED_SEVERITIES else "optional"
    return {
        "check_id": check_id,
        "category": category,
        "status": normalized_status,
        "severity": normalized_severity,
        "record_ids": sorted({item for item in record_ids if item}),
        "message": message,
        "recommended_action": recommended_action,
    }


def _report_check_status(validation: Mapping[str, Any], check_id: str) -> str:
    for item in _as_list(validation.get("checks")):
        if str(item.get("check_id") or "") == check_id:
            status = str(item.get("status") or "unknown")
            return {
                "pass": "valid",
                "warning": "warning",
                "fail": "invalid",
                "blocked": "blocked",
                "unknown": "unknown",
                "not_applicable": "not_applicable",
            }.get(status, status)
    return "unknown"


def _reader_readiness_from_checks(checks: list[dict[str, Any]]) -> str:
    for item in checks:
        if item.get("check_id") == "reader_backend_readiness_consistent":
            return "ready" if item.get("status") == "pass" else "not_ready"
    return "unknown"


def _recommended_action(checks: list[dict[str, Any]], certification: str) -> str:
    for item in checks:
        if item.get("status") in {"blocked", "fail", "unknown"} and item.get("recommended_action"):
            return str(item.get("recommended_action"))
    if certification == "certified_with_warnings":
        return "Review one pending revalidation item before PDF-reader release."
    if certification == "certified":
        return "Backend contract is ready for future PDF-reader integration."
    return "Review the failed backend contract checks before release."


def _validation_path(root: Path, validation_id: str) -> Path:
    return root / VALIDATION_DIR / f"{_safe_id(validation_id)}.json"


def _ensure_dirs(root: Path | str) -> Path:
    base = Path(root)
    (base / VALIDATION_DIR).mkdir(parents=True, exist_ok=True)
    (base / INDEX_DIR).mkdir(parents=True, exist_ok=True)
    index_path = base / INDEX_DIR / INDEX_NAME
    if not index_path.exists():
        _atomic_write_json(index_path, {"entries": [], "updated_at_utc": _now()})
    return base


def _iter_json(directory: Path, pattern: str) -> Iterable[dict[str, Any]]:
    if not directory.exists():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(directory.glob(pattern)):
        payload = _read_json(path)
        if isinstance(payload, dict):
            items.append(payload)
    return items


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f"{path.name}.tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temp.replace(path)


def _json_hash(payload: Any) -> str:
    import hashlib

    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _safe_id(value: str) -> str:
    return "".join(character if character.isalnum() or character in {"_", "-", "."} else "_" for character in str(value))


def _sanitize_text(text: str) -> str:
    sanitized = str(text)
    for token in ("token=", "api_key", "secret", "credential", "stack trace", "Traceback", "C:\\", "/Users/"):
        sanitized = sanitized.replace(token, "[redacted]" if token.endswith("=") else "")
    return sanitized


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
