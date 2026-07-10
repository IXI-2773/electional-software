"""Single-PDF autonomous native-text certification orchestration."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from . import rule_effectiveness_analysis as analysis_backend
from .citation_draft_review import create_citation_from_approved_draft
from .document_content_curation import load_document_content_curation
from .document_content_map import get_document_content_map_summary
from .document_manifest import build_document_manifest, calculate_document_revision_state, load_document_manifest
from .document_structure import get_document_structure_summary
from .evidence_handoff_review import create_proposal_draft_from_evidence_handoff
from .proposal_promotion import promote_approved_proposal, save_proposal_promotion_decision
from .proposal_rule_activation import (
    activate_rule_from_promoted_proposal,
    rollback_proposal_rule_activation,
    save_proposal_rule_activation_decision,
)
from .rule_activation_revalidation import (
    complete_rule_activation_revalidation,
    run_rule_runtime_contract_validation,
    save_rule_activation_revalidation_decision,
)
from .source_document_reader import get_page_diagnostic_summary
from .source_documents import SOURCE_DOCUMENT_ROOT, STATUS_EXTRACTED, get_extracted_text, load_source_document
from .source_knowledge import load_chunks
from .source_workflow_coordinator import create_source_workflow_plan, execute_source_workflow_stage, recommend_next_source_workflow_stage

RUN_DIR = "autonomous_pdf_runs"
RECEIPT_DIR = "autonomous_pdf_receipts"
RUN_INDEX = "autonomous_pdf_run_index.json"
RECEIPT_INDEX = "autonomous_pdf_receipt_index.json"
PLAN_SCHEMA = "autonomous_pdf_plan_v1"
RUN_SCHEMA = "autonomous_pdf_run_v1"
RECEIPT_SCHEMA = "autonomous_pdf_receipt_v1"
POLICY_ID = "native_text_autonomy_policy_v1"
DEFAULT_LIMITS = {
    "max_pages": 300,
    "max_harvest_candidates": 50,
    "max_proposal_candidates": 20,
    "max_rule_candidates": 10,
    "max_certified_rules": 5,
}
HARD_LIMITS = {
    "max_pages": 1000,
    "max_harvest_candidates": 100,
    "max_proposal_candidates": 40,
    "max_rule_candidates": 20,
    "max_certified_rules": 10,
}
STAGE_ORDER = [
    "validate_document",
    "refresh_required_stages",
    "discover_harvest_candidates",
    "validate_citation_candidates",
    "create_citations",
    "complete_evidence_handoffs",
    "create_proposal_drafts",
    "review_and_promote_proposals",
    "build_rule_candidates",
    "activate_rules",
    "run_runtime_contracts",
    "certify_rules",
    "finalize_receipt",
]
FINAL_RUN_STATUSES = {"completed", "completed_with_blocked_items", "no_rule_candidates", "cancelled", "failed_rolled_back", "rollback_failed"}


def build_autonomous_pdf_workspace(
    document_id: str,
    source_revision: int,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    readiness = validate_autonomous_pdf_readiness(document_id, source_revision, root=base)
    manifest = load_document_manifest(document_id, root=base).get("manifest")
    structure = get_document_structure_summary(document_id, root=base)
    content_map = get_document_content_map_summary(document_id, root=base)
    curation = load_document_content_curation(document_id, root=base)
    candidates = _discover_harvest_candidates(base, {"document_id": document_id, "source_revision": _normalize_revision(source_revision)}, limits=DEFAULT_LIMITS)
    certified_rules = _count_certified_rules(base, document_id, _normalize_revision(source_revision))
    run = _load_run_for_document(base, document_id, _normalize_revision(source_revision))
    return {
        "document_id": document_id,
        "source_revision": _normalize_revision(source_revision),
        "document_status": readiness["document_status"],
        "native_text_status": readiness["native_text_status"],
        "document_class": readiness["document_class"],
        "preflight_status": _manifest_pipeline_status(manifest, "preflight"),
        "structure_status": structure.get("status", "unknown"),
        "content_map_status": content_map.get("status", "unknown"),
        "curation_status": curation.get("status", "unknown"),
        "autonomous_readiness": readiness["autonomous_readiness"],
        "existing_certified_rule_count": certified_rules,
        "unprocessed_candidate_count": len(candidates),
        "existing_run_status": (run or {}).get("status"),
        "warnings": list(readiness["warnings"]),
        "blockers": list(readiness["blockers"]),
        "recommended_action": "Build the autonomous single-PDF plan." if not readiness["blockers"] else "Resolve document or native-text blockers before autonomous planning.",
    }


def validate_autonomous_pdf_readiness(
    document_id: str,
    source_revision: int,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    blockers: list[str] = []
    warnings: list[str] = []
    document_status = "unknown"
    native_text_status = "missing"
    document_class = "unknown"
    source_record = load_source_document(document_id, root=base, missing_ok=True)
    manifest = load_document_manifest(document_id, root=base).get("manifest")
    normalized_revision = _normalize_revision(source_revision)
    if not _non_empty_text(document_id):
        blockers.append("document_id_required")
    if normalized_revision is None:
        blockers.append("source_revision_required")
    if source_record is None:
        blockers.append("document_not_found")
    if not isinstance(manifest, Mapping):
        blockers.append("document_manifest_missing")
    else:
        current_state = calculate_document_revision_state(document_id, existing_manifest=manifest, root=base)
        current_revision = _normalize_revision(current_state.get("source_revision"))
        if current_revision != normalized_revision:
            blockers.append("source_revision_changed")
            document_status = "stale"
        else:
            document_status = "current"
        readiness_status = str(((manifest.get("backend_readiness") or {}).get("status")) or "")
        if readiness_status in {"blocked", "corrupt"}:
            blockers.append("blocked_manifest_state")
    quarantine_path = base / "quarantine" / f"{analysis_backend._safe_id(document_id)}.json"
    if quarantine_path.exists():
        blockers.append("document_quarantined")
    extracted_text = get_extracted_text(document_id, root=base) if source_record is not None else ""
    if source_record is not None and source_record.extraction_status == STATUS_EXTRACTED and extracted_text.strip():
        native_text_status = "available"
    elif source_record is not None and source_record.extraction_status != STATUS_EXTRACTED:
        blockers.extend(["native_text_layer_missing", "ocr_required_but_not_supported"])
        document_class = "unsupported_image_only_pdf"
    else:
        blockers.append("native_text_layer_missing")
        document_class = "unsupported_corrupt_text_layer"
    page_summary = get_page_diagnostic_summary(document_id, root=base)
    structure_summary = get_document_structure_summary(document_id, root=base)
    chunks = load_chunks(document_id=document_id, root=base)
    if not chunks:
        blockers.append("chunk_records_missing")
    if int(page_summary.get("pages_diagnosed", 0) or 0) <= 0:
        blockers.append("page_records_missing")
    if source_record is not None and native_text_status == "available":
        complex_signals = any(
            [
                bool(structure_summary.get("tables")),
                bool(structure_summary.get("figures")),
                bool(structure_summary.get("footnotes")),
                bool(structure_summary.get("references_found")),
                bool(structure_summary.get("header_footer_noise")),
            ]
        )
        if complex_signals:
            document_class = "complex_digital_pdf"
            if structure_summary.get("status") != "built":
                blockers.append("reading_order_unresolved")
        else:
            document_class = "clean_digital_pdf"
    autonomous_readiness = "ready" if not blockers else "blocked"
    if document_class == "unknown" and blockers:
        document_class = "unknown"
    return {
        "document_id": document_id,
        "source_revision": normalized_revision,
        "document_status": document_status,
        "native_text_status": native_text_status,
        "document_class": document_class,
        "autonomous_readiness": autonomous_readiness,
        "warnings": _dedupe(warnings),
        "blockers": _dedupe(blockers),
    }


def build_autonomous_pdf_plan(
    document_id: str,
    source_revision: int,
    max_pages: int = 300,
    max_harvest_candidates: int = 50,
    max_proposal_candidates: int = 20,
    max_rule_candidates: int = 10,
    max_certified_rules: int = 5,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    readiness = validate_autonomous_pdf_readiness(document_id, source_revision, root=base)
    manifest = build_document_manifest(document_id, regenerate=False, root=base) if not readiness["blockers"] else load_document_manifest(document_id, root=base).get("manifest")
    limits = {
        "max_pages": _normalize_limit(max_pages, "max_pages"),
        "max_harvest_candidates": _normalize_limit(max_harvest_candidates, "max_harvest_candidates"),
        "max_proposal_candidates": _normalize_limit(max_proposal_candidates, "max_proposal_candidates"),
        "max_rule_candidates": _normalize_limit(max_rule_candidates, "max_rule_candidates"),
        "max_certified_rules": _normalize_limit(max_certified_rules, "max_certified_rules"),
    }
    blockers = list(readiness["blockers"])
    for key, value in limits.items():
        if value > HARD_LIMITS[key]:
            blockers.append(f"{key}_exceeds_hard_limit")
    structure = get_document_structure_summary(document_id, root=base)
    content_map = get_document_content_map_summary(document_id, root=base)
    plan_core = {
        "schema_version": PLAN_SCHEMA,
        "document_id": document_id,
        "source_revision": _normalize_revision(source_revision),
        "manifest_fingerprint": (manifest or {}).get("pipeline_fingerprint"),
        "document_class": readiness["document_class"],
        "policy_id": POLICY_ID,
        "limits": limits,
        "structure_status": structure.get("status"),
        "content_map_status": content_map.get("status"),
    }
    plan_fingerprint = analysis_backend._hash_payload(plan_core)
    plan = {
        "schema_version": PLAN_SCHEMA,
        "autonomous_plan_id": _plan_id(plan_fingerprint),
        "document_id": document_id,
        "source_revision": _normalize_revision(source_revision),
        "document_class": readiness["document_class"],
        "manifest_fingerprint": (manifest or {}).get("pipeline_fingerprint"),
        "policy_id": POLICY_ID,
        "limits": limits,
        "stages": [{"stage": stage, "status": "pending"} for stage in STAGE_ORDER],
        "plan_fingerprint": plan_fingerprint,
        "warnings": list(readiness["warnings"]),
        "blockers": _dedupe(blockers),
    }
    path = _plan_path(base, plan["autonomous_plan_id"])
    before_plan = analysis_backend._read_json(path)
    before_index = analysis_backend._read_json(base / "indexes" / RUN_INDEX)
    try:
        analysis_backend._atomic_write_json(path, plan)
        _update_run_index(base)
    except Exception:
        analysis_backend._restore_json(path, before_plan)
        analysis_backend._restore_json(base / "indexes" / RUN_INDEX, before_index)
        return {**plan, "status": "failed"}
    return plan


def run_autonomous_pdf_pipeline(
    autonomous_plan_id: str,
    confirmation: str | None = None,
    stop_after_stage: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    if confirmation != "AUTO_RUN":
        return {"status": "blocked", "autonomous_plan_id": autonomous_plan_id, "warnings": [], "blockers": ["auto_run_confirmation_required"]}
    plan = _load_plan(base, autonomous_plan_id)
    if not isinstance(plan, dict):
        return {"status": "blocked", "autonomous_plan_id": autonomous_plan_id, "warnings": [], "blockers": ["autonomous_plan_not_found"]}
    if plan.get("blockers"):
        return {"status": "blocked", "autonomous_plan_id": autonomous_plan_id, "warnings": list(plan.get("warnings", [])), "blockers": list(plan.get("blockers", []))}
    stale_blockers = _plan_stale_blockers(base, plan)
    if stale_blockers:
        return {"status": "stale", "autonomous_plan_id": autonomous_plan_id, "warnings": [], "blockers": stale_blockers}
    run = _load_run_for_plan(base, autonomous_plan_id)
    if isinstance(run, dict):
        if str(run.get("status") or "") in FINAL_RUN_STATUSES:
            receipt = _load_receipt_for_run(base, str(run.get("autonomous_run_id") or ""))
            if isinstance(receipt, dict):
                return {
                    "status": "already_completed",
                    "autonomous_run_id": run.get("autonomous_run_id"),
                    "autonomous_receipt_id": receipt.get("autonomous_receipt_id"),
                    "writes_performed": 0,
                }
        if str(run.get("status") or "") == "cancelled":
            return {"status": "cancelled", "autonomous_run_id": run.get("autonomous_run_id"), "warnings": [], "blockers": list(run.get("blockers", []))}
        current_run = deepcopy(run)
    else:
        current_run = _new_run_from_plan(plan)
        if not _persist_run(base, current_run):
            return {"status": "failed_rolled_back", "autonomous_plan_id": autonomous_plan_id, "warnings": [], "blockers": ["autonomous_run_write_failure"]}
    current_run["status"] = "running"
    _persist_run(base, current_run)
    if not _process_validate_document(base, plan, current_run, stop_after_stage):
        receipt = _create_receipt_if_needed(base, current_run, plan)
        return {**current_run, "autonomous_receipt_id": (receipt or {}).get("autonomous_receipt_id")}
    if not _process_refresh_stages(base, plan, current_run, stop_after_stage):
        receipt = _create_receipt_if_needed(base, current_run, plan)
        return {**current_run, "autonomous_receipt_id": (receipt or {}).get("autonomous_receipt_id")}
    if not _process_candidates(base, plan, current_run, stop_after_stage):
        receipt = _create_receipt_if_needed(base, current_run, plan)
        return {**current_run, "autonomous_receipt_id": (receipt or {}).get("autonomous_receipt_id")}
    _finalize_run(base, current_run)
    receipt = _create_receipt_if_needed(base, current_run, plan)
    return {**current_run, "autonomous_receipt_id": (receipt or {}).get("autonomous_receipt_id")}


def load_autonomous_pdf_run(
    autonomous_run_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    payload = analysis_backend._read_json(_run_path(base, autonomous_run_id))
    if not isinstance(payload, dict):
        return {"status": "not_found", "autonomous_run_id": autonomous_run_id, "warnings": [], "blockers": ["autonomous_run_not_found"]}
    return {"status": "loaded", "autonomous_run": payload, "warnings": []}


def cancel_autonomous_pdf_pipeline(
    autonomous_run_id: str,
    reason: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    if not _non_empty_text(reason):
        return {"status": "blocked", "autonomous_run_id": autonomous_run_id, "warnings": [], "blockers": ["autonomous_cancellation_reason_required"]}
    run = _load_run_by_id(base, autonomous_run_id)
    if not isinstance(run, dict):
        return {"status": "blocked", "autonomous_run_id": autonomous_run_id, "warnings": [], "blockers": ["autonomous_run_not_found"]}
    if str(run.get("status") or "") not in {"planned", "running", "paused"}:
        return {"status": "blocked", "autonomous_run_id": autonomous_run_id, "warnings": [], "blockers": ["autonomous_run_not_cancellable"]}
    run["status"] = "cancelled"
    run["cancellation_reason"] = str(reason).strip()
    run["updated_at_utc"] = analysis_backend._now()
    if not _persist_run(base, run):
        return {"status": "failed_rolled_back", "autonomous_run_id": autonomous_run_id, "warnings": [], "blockers": ["autonomous_run_write_failure"]}
    receipt = _create_receipt_if_needed(base, run, _load_plan(base, str(run.get("autonomous_plan_id") or "")))
    return {**run, "autonomous_receipt_id": (receipt or {}).get("autonomous_receipt_id")}


def get_autonomous_pdf_health(
    document_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = _ensure_dirs(root)
    runs = _load_runs(base)
    receipts = _load_receipts(base)
    if document_id:
        runs = [item for item in runs if str(item.get("document_id") or "") == document_id]
        receipts = [item for item in receipts if str(item.get("document_id") or "") == document_id]
    if not runs and not receipts:
        return {"status": "empty", "run_count": 0, "receipt_count": 0, "stale_count": 0, "corrupt_count": 0, "warnings": [], "recommended_action": "Build one autonomous single-PDF plan."}
    stale = 0
    corrupt = 0
    warnings: list[str] = []
    for run in runs:
        plan = _load_plan(base, str(run.get("autonomous_plan_id") or ""))
        if not isinstance(plan, dict):
            corrupt += 1
            continue
        if _plan_stale_blockers(base, plan):
            stale += 1
        if str(run.get("document_id") or "") != str(plan.get("document_id") or ""):
            corrupt += 1
        if _normalize_revision(run.get("source_revision")) != _normalize_revision(plan.get("source_revision")):
            corrupt += 1
    status = "corrupt" if corrupt else "stale" if stale else "healthy"
    if stale:
        warnings.append("one_or_more_autonomous_runs_are_stale")
    return {
        "status": status,
        "run_count": len(runs),
        "receipt_count": len(receipts),
        "stale_count": stale,
        "corrupt_count": corrupt,
        "warnings": _dedupe(warnings),
        "recommended_action": "Rebuild the autonomous plan against the current revision." if stale else "Autonomous PDF health is good.",
    }


def format_autonomous_pdf_report(
    autonomous_run_id: str | None = None,
    autonomous_receipt_id: str | None = None,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    base = _ensure_dirs(root)
    receipt = _load_receipt_by_id(base, autonomous_receipt_id) if autonomous_receipt_id else None
    run = _load_run_by_id(base, autonomous_run_id or str((receipt or {}).get("autonomous_run_id") or ""))
    if not isinstance(run, dict):
        return "Autonomous Single-PDF Certification Report\n\nStatus: not_found"
    lines = [
        "Autonomous Single-PDF Certification Report",
        "",
        f"Document: {run.get('document_id')}",
        f"Source Revision: {run.get('source_revision')}",
        f"Document Class: {run.get('document_class')}",
        f"Native Text: {run.get('native_text_status')}",
        f"Status: {run.get('status')}",
        "",
        "Document Processing:",
        f"- Preflight: {run.get('preflight_status')}",
        f"- Structure Map: {run.get('structure_status')}",
        f"- Content Map: {run.get('content_map_status')}",
        "",
        "Harvesting:",
        f"- Citation Candidates Processed: {run.get('citation_candidate_count', 0)}",
        f"- Citations Created or Reused: {run.get('citation_count', 0)}",
        f"- Blocked Citation Candidates: {run.get('blocked_citation_count', 0)}",
        "",
        "Proposals:",
        f"- Drafts Created or Reused: {run.get('proposal_draft_count', 0)}",
        f"- Promoted: {run.get('promoted_proposal_count', 0)}",
        f"- Preserved as Non-Rule Information: {run.get('non_rule_information_count', 0)}",
        "",
        "Rules:",
        f"- Structured Candidates: {run.get('structured_rule_candidate_count', 0)}",
        f"- Activated: {run.get('activated_rule_count', 0)}",
        f"- Runtime Contracts Passed: {run.get('runtime_contract_passed_count', 0)}",
        f"- Certified: {run.get('certified_rule_count', 0)}",
        "",
        "Blocked Items:",
    ]
    blocker_counts = _blocked_item_counts(run.get("blocked_items", []))
    if blocker_counts:
        for key, value in blocker_counts.items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "Important:",
            "Only native PDF text was processed.",
            "No OCR, cross-PDF processing, rule supersession, scoring, objective-pack, Fast Lane, or production replay operation occurred.",
        ]
    )
    text = "\n".join(lines)
    if public_safe:
        for needle in ("C:\\", "/Users/", "Traceback", "api_key", "secret", "token", "quote_excerpt", "claim", "text"):
            text = text.replace(needle, "[redacted]")
    return text


def _ensure_dirs(root: Path | str) -> Path:
    base = analysis_backend._ensure_analysis_dirs(root)
    for folder in (RUN_DIR, RECEIPT_DIR, "indexes"):
        (base / folder).mkdir(parents=True, exist_ok=True)
    for path, payload in (
        (base / "indexes" / RUN_INDEX, {"schema_version": "autonomous_pdf_run_index_v1", "items": [], "updated_at_utc": analysis_backend._now()}),
        (base / "indexes" / RECEIPT_INDEX, {"schema_version": "autonomous_pdf_receipt_index_v1", "items": [], "updated_at_utc": analysis_backend._now()}),
    ):
        if not path.exists():
            analysis_backend._atomic_write_json(path, payload)
    return base


def _process_validate_document(base: Path, plan: Mapping[str, Any], run: dict[str, Any], stop_after_stage: str | None) -> bool:
    readiness = validate_autonomous_pdf_readiness(str(plan.get("document_id") or ""), int(plan.get("source_revision") or 0), root=base)
    run["document_status"] = readiness.get("document_status")
    run["native_text_status"] = readiness.get("native_text_status")
    run["document_class"] = readiness.get("document_class")
    if readiness.get("blockers"):
        run["status"] = "blocked"
        run["blockers"] = list(readiness.get("blockers", []))
        _persist_run(base, run)
        return False
    _complete_stage(run, "validate_document")
    return _pause_if_requested(base, run, stop_after_stage, "validate_document")


def _process_refresh_stages(base: Path, plan: Mapping[str, Any], run: dict[str, Any], stop_after_stage: str | None) -> bool:
    stage_results = []
    for _ in range(8):
        recommendation = recommend_next_source_workflow_stage(str(plan.get("document_id") or ""), root=base)
        stage = str(recommendation.get("recommended_stage") or "none")
        if stage == "none":
            break
        workflow_plan = create_source_workflow_plan(str(plan.get("document_id") or ""), requested_stage=stage, dry_run=False, root=base)
        workflow_plan_id = _non_empty_text(workflow_plan.get("workflow_plan_id"))
        if not workflow_plan_id:
            run["status"] = "blocked"
            run["blockers"] = _dedupe(list(run.get("blockers", [])) + [f"stage_{stage}_plan_failed"])
            run["stage_results"] = stage_results
            _persist_run(base, run)
            return False
        result = execute_source_workflow_stage(workflow_plan_id, dry_run=False, root=base)
        stage_results.append({"stage": stage, "status": result.get("status")})
        if str(result.get("status") or "") not in {"completed", "already_completed", "ready", "success"}:
            run["status"] = "blocked"
            run["blockers"] = _dedupe(list(run.get("blockers", [])) + [f"stage_{stage}_blocked"])
            run["stage_results"] = stage_results
            _persist_run(base, run)
            return False
    manifest = build_document_manifest(str(plan.get("document_id") or ""), regenerate=False, root=base)
    run["preflight_status"] = _manifest_pipeline_status(manifest, "preflight")
    run["structure_status"] = get_document_structure_summary(str(plan.get("document_id") or ""), root=base).get("status")
    run["content_map_status"] = get_document_content_map_summary(str(plan.get("document_id") or ""), root=base).get("status")
    run["stage_results"] = stage_results
    _complete_stage(run, "refresh_required_stages")
    return _pause_if_requested(base, run, stop_after_stage, "refresh_required_stages")


def _process_candidates(base: Path, plan: Mapping[str, Any], run: dict[str, Any], stop_after_stage: str | None) -> bool:
    workspace = {"document_id": plan.get("document_id"), "source_revision": plan.get("source_revision"), "document_class": plan.get("document_class")}
    candidates = _discover_harvest_candidates(base, workspace, limits=dict(plan.get("limits") or {}))
    run["citation_candidate_count"] = len(candidates)
    if not candidates:
        run["status"] = "no_rule_candidates"
        _complete_stage(run, "discover_harvest_candidates")
        _persist_run(base, run)
        return False
    _complete_stage(run, "discover_harvest_candidates")
    if not _pause_if_requested(base, run, stop_after_stage, "discover_harvest_candidates"):
        return False
    for index, candidate in enumerate(candidates, start=1):
        if _plan_stale_blockers(base, plan):
            run["status"] = "stale"
            run["blockers"] = _dedupe(list(run.get("blockers", [])) + ["source_revision_changed"])
            _persist_run(base, run)
            return False
        result = _process_candidate(base, candidate)
        run.setdefault("item_results", []).append(result)
        _accumulate_result_counts(run, result)
        run["next_item_index"] = index
        run["updated_at_utc"] = analysis_backend._now()
        _persist_run(base, run)
        if str(result.get("status") or "") == "rollback_failed":
            run["status"] = "rollback_failed"
            run["blockers"] = _dedupe(list(run.get("blockers", [])) + ["critical_recovery_failure"])
            run["updated_at_utc"] = analysis_backend._now()
            _persist_run(base, run)
            return False
    for stage in STAGE_ORDER[3:-1]:
        _complete_stage(run, stage)
    return _pause_if_requested(base, run, stop_after_stage, "certify_rules")


def _process_candidate(base: Path, candidate: Mapping[str, Any]) -> dict[str, Any]:
    result = {
        "candidate_id": candidate.get("candidate_id"),
        "document_id": candidate.get("document_id"),
        "source_revision": candidate.get("source_revision"),
        "status": "blocked",
        "blocker": None,
        "citation_id": None,
        "proposal_id": None,
        "promotion_receipt_id": None,
        "activation_receipt_id": None,
        "revalidation_id": None,
        "certification_receipt_id": None,
        "result_type": None,
    }
    if candidate.get("ambiguous") or candidate.get("near_duplicate"):
        result["blocker"] = "ambiguous_or_near_duplicate_evidence"
        return result
    citation_result = _create_or_reuse_citation(base, candidate)
    if citation_result.get("blocked"):
        result["blocker"] = str(citation_result.get("blocked"))
        return result
    result["citation_id"] = citation_result.get("citation_id")
    handoff_result = _complete_evidence_handoff(base, candidate, citation_result)
    if handoff_result.get("blocked"):
        result["blocker"] = str(handoff_result.get("blocked"))
        return result
    proposal_result = _create_or_reuse_proposal(base, candidate, handoff_result)
    if proposal_result.get("blocked"):
        result["blocker"] = str(proposal_result.get("blocked"))
        return result
    result["proposal_id"] = proposal_result.get("proposal_id")
    if not proposal_result.get("structured_rule_ready", False):
        result["status"] = "completed"
        result["result_type"] = "promoted_non_rule_information"
        return result
    promotion_result = _promote_proposal(base, str(proposal_result.get("proposal_id") or ""))
    if promotion_result.get("blocked"):
        result["blocker"] = str(promotion_result.get("blocked"))
        return result
    result["promotion_receipt_id"] = promotion_result.get("promotion_receipt_id")
    activation_result = _activate_rule(base, str(proposal_result.get("proposal_id") or ""))
    if activation_result.get("blocked"):
        result["blocker"] = str(activation_result.get("blocked"))
        return result
    result["activation_receipt_id"] = activation_result.get("activation_receipt_id")
    result["revalidation_id"] = activation_result.get("revalidation_id")
    certification_result = _validate_and_certify_rule(base, activation_result)
    if certification_result.get("rollback_failed"):
        result["status"] = "rollback_failed"
        result["blocker"] = "critical_recovery_failure"
        return result
    if certification_result.get("blocked"):
        result["status"] = "failed_rolled_back" if certification_result.get("rollback_performed") else "blocked"
        result["blocker"] = str(certification_result.get("blocked"))
        return result
    result["status"] = "completed"
    result["result_type"] = "certified_rule"
    result["certification_receipt_id"] = certification_result.get("certification_receipt_id")
    return result


def _create_or_reuse_citation(base: Path, candidate: Mapping[str, Any]) -> dict:
    review_id = _non_empty_text(candidate.get("citation_review_id"))
    if review_id:
        created = create_citation_from_approved_draft(review_id, confirmation="CREATE", root=base)
        if str(created.get("status") or "") in {"created", "already_created"}:
            return {"citation_id": created.get("citation_id"), "evidence_handoff_id": created.get("evidence_handoff_id")}
        return {"blocked": (created.get("blockers") or ["citation_creation_failed"])[0]}
    existing = _non_empty_text(candidate.get("citation_id"))
    if existing:
        return {"citation_id": existing, "evidence_handoff_id": candidate.get("evidence_handoff_id")}
    return {"blocked": "citation_candidate_unavailable"}


def _complete_evidence_handoff(base: Path, candidate: Mapping[str, Any], citation_result: Mapping[str, Any]) -> dict:
    review_id = _non_empty_text(candidate.get("handoff_review_id"))
    if review_id:
        created = create_proposal_draft_from_evidence_handoff(review_id, confirmation="DRAFT", root=base)
        if str(created.get("status") or "") in {"created", "already_created"}:
            return {"proposal_id": created.get("proposal_id")}
        return {"blocked": (created.get("blockers") or ["evidence_handoff_failed"])[0]}
    if _non_empty_text(candidate.get("proposal_id")):
        return {"proposal_id": candidate.get("proposal_id")}
    if _non_empty_text(citation_result.get("evidence_handoff_id")):
        return {"evidence_handoff_id": citation_result.get("evidence_handoff_id")}
    return {"blocked": "evidence_handoff_requires_human_judgment"}


def _create_or_reuse_proposal(base: Path, candidate: Mapping[str, Any], handoff_result: Mapping[str, Any]) -> dict:
    proposal_id = _non_empty_text(handoff_result.get("proposal_id")) or _non_empty_text(candidate.get("proposal_id"))
    if not proposal_id:
        return {"blocked": "proposal_draft_unavailable"}
    return {
        "proposal_id": proposal_id,
        "structured_rule_ready": bool(candidate.get("structured_rule_ready", True)),
    }


def _promote_proposal(base: Path, proposal_id: str) -> dict:
    review = save_proposal_promotion_decision(proposal_id, "approve", root=base)
    if str(review.get("status") or "") not in {"saved"}:
        return {"blocked": (review.get("blockers") or ["autonomous_promotion_requires_human_judgment"])[0]}
    promoted = promote_approved_proposal(str((review.get("review") or {}).get("promotion_review_id") or ""), confirmation="PROMOTE", root=base)
    if str(promoted.get("status") or "") in {"promoted", "already_promoted"}:
        return {"promotion_receipt_id": promoted.get("promotion_receipt_id")}
    return {"blocked": (promoted.get("blockers") or ["autonomous_promotion_requires_human_judgment"])[0]}


def _activate_rule(base: Path, proposal_id: str) -> dict:
    review = save_proposal_rule_activation_decision(proposal_id, "approve", root=base)
    if str(review.get("status") or "") not in {"saved"}:
        return {"blocked": (review.get("blockers") or ["rule_activation_requires_human_judgment"])[0]}
    activated = activate_rule_from_promoted_proposal(str((review.get("review") or {}).get("rule_activation_review_id") or ""), confirmation="ACTIVATE", root=base)
    if str(activated.get("status") or "") in {"activated", "already_activated"}:
        return {
            "activation_receipt_id": activated.get("activation_receipt_id"),
            "revalidation_id": activated.get("revalidation_id"),
        }
    return {"blocked": (activated.get("blockers") or ["rule_activation_requires_human_judgment"])[0]}


def _validate_and_certify_rule(base: Path, activation_result: Mapping[str, Any]) -> dict:
    revalidation_id = _non_empty_text(activation_result.get("revalidation_id"))
    activation_receipt_id = _non_empty_text(activation_result.get("activation_receipt_id"))
    if not revalidation_id:
        return {"blocked": "runtime_revalidation_missing"}
    runtime_validation = run_rule_runtime_contract_validation(revalidation_id, root=base)
    if str(runtime_validation.get("status") or "") not in {"passed", "passed_with_warnings"}:
        if activation_receipt_id:
            rolled = rollback_proposal_rule_activation(activation_receipt_id, confirmation="ROLLBACK", root=base)
            if str(rolled.get("status") or "") == "rollback_completed":
                return {"blocked": "runtime_contract_case_failed", "rollback_performed": True}
            return {"blocked": "runtime_contract_case_failed", "rollback_failed": True}
        return {"blocked": "runtime_contract_case_failed"}
    review = save_rule_activation_revalidation_decision(revalidation_id, "certify", root=base)
    if str(review.get("status") or "") not in {"saved"}:
        return {"blocked": (review.get("blockers") or ["runtime_validation_not_certifiable"])[0]}
    certified = complete_rule_activation_revalidation(str((review.get("review") or {}).get("revalidation_review_id") or ""), confirmation="CERTIFY", root=base)
    if str(certified.get("status") or "") in {"certified", "already_certified"}:
        return {"certification_receipt_id": certified.get("certification_receipt_id")}
    return {"blocked": (certified.get("blockers") or ["runtime_validation_not_certifiable"])[0]}


def _discover_harvest_candidates(base: Path, workspace: Mapping[str, Any], *, limits: Mapping[str, Any]) -> list[dict[str, Any]]:
    _ = (base, workspace, limits)
    return []


def _finalize_run(base: Path, run: dict[str, Any]) -> None:
    blocked = int(run.get("blocked_item_count", 0) or 0)
    certified = int(run.get("certified_rule_count", 0) or 0)
    if certified and blocked:
        run["status"] = "completed_with_blocked_items"
    elif certified:
        run["status"] = "completed"
    elif int(run.get("non_rule_information_count", 0) or 0):
        run["status"] = "completed_with_blocked_items" if blocked else "no_rule_candidates"
    elif blocked:
        run["status"] = "completed_with_blocked_items"
    else:
        run["status"] = "no_rule_candidates"
    run["updated_at_utc"] = analysis_backend._now()
    _persist_run(base, run)


def _accumulate_result_counts(run: dict[str, Any], result: Mapping[str, Any]) -> None:
    if result.get("citation_id"):
        run["citation_count"] = int(run.get("citation_count", 0) or 0) + 1
    if result.get("proposal_id"):
        run["proposal_draft_count"] = int(run.get("proposal_draft_count", 0) or 0) + 1
    if result.get("promotion_receipt_id"):
        run["promoted_proposal_count"] = int(run.get("promoted_proposal_count", 0) or 0) + 1
    if result.get("result_type") == "promoted_non_rule_information":
        run["non_rule_information_count"] = int(run.get("non_rule_information_count", 0) or 0) + 1
    if result.get("activation_receipt_id"):
        run["structured_rule_candidate_count"] = int(run.get("structured_rule_candidate_count", 0) or 0) + 1
        run["activated_rule_count"] = int(run.get("activated_rule_count", 0) or 0) + 1
    if result.get("certification_receipt_id"):
        run["runtime_contract_passed_count"] = int(run.get("runtime_contract_passed_count", 0) or 0) + 1
        run["certified_rule_count"] = int(run.get("certified_rule_count", 0) or 0) + 1
    if result.get("blocker"):
        run["blocked_item_count"] = int(run.get("blocked_item_count", 0) or 0) + 1
        run.setdefault("blocked_items", []).append(
            {
                "candidate_id": result.get("candidate_id"),
                "blocker": result.get("blocker"),
            }
        )
        if str(result.get("blocker") or "") == "ambiguous_or_near_duplicate_evidence":
            run["blocked_citation_count"] = int(run.get("blocked_citation_count", 0) or 0) + 1


def _new_run_from_plan(plan: Mapping[str, Any]) -> dict:
    return {
        "schema_version": RUN_SCHEMA,
        "autonomous_run_id": _run_id(str(plan.get("autonomous_plan_id") or "")),
        "autonomous_plan_id": plan.get("autonomous_plan_id"),
        "document_id": plan.get("document_id"),
        "source_revision": plan.get("source_revision"),
        "document_class": plan.get("document_class"),
        "manifest_fingerprint": plan.get("manifest_fingerprint"),
        "plan_fingerprint": plan.get("plan_fingerprint"),
        "policy_id": plan.get("policy_id"),
        "status": "planned",
        "current_stage": "validate_document",
        "next_item_index": 0,
        "citation_candidate_count": 0,
        "citation_count": 0,
        "blocked_citation_count": 0,
        "proposal_draft_count": 0,
        "promoted_proposal_count": 0,
        "non_rule_information_count": 0,
        "structured_rule_candidate_count": 0,
        "activated_rule_count": 0,
        "runtime_contract_passed_count": 0,
        "certified_rule_count": 0,
        "blocked_item_count": 0,
        "blocked_items": [],
        "item_results": [],
        "warnings": [],
        "blockers": [],
        "created_at_utc": analysis_backend._now(),
        "updated_at_utc": analysis_backend._now(),
    }


def _pause_if_requested(base: Path, run: dict[str, Any], stop_after_stage: str | None, stage: str) -> bool:
    run["current_stage"] = stage
    run["updated_at_utc"] = analysis_backend._now()
    _persist_run(base, run)
    if _non_empty_text(stop_after_stage) == stage:
        run["status"] = "paused"
        run["updated_at_utc"] = analysis_backend._now()
        _persist_run(base, run)
        return False
    return True


def _complete_stage(run: dict[str, Any], stage: str) -> None:
    stages = list(run.get("stages_completed", []))
    if stage not in stages:
        stages.append(stage)
    run["stages_completed"] = stages
    run["current_stage"] = stage


def _load_plan(base: Path, autonomous_plan_id: str) -> dict[str, Any] | None:
    payload = analysis_backend._read_json(_plan_path(base, autonomous_plan_id))
    return deepcopy(dict(payload)) if isinstance(payload, dict) and str(payload.get("schema_version") or "") == PLAN_SCHEMA else None


def _load_run_by_id(base: Path, autonomous_run_id: str) -> dict[str, Any] | None:
    payload = analysis_backend._read_json(_run_path(base, autonomous_run_id))
    return deepcopy(dict(payload)) if isinstance(payload, dict) and str(payload.get("schema_version") or "") == RUN_SCHEMA else None


def _load_run_for_plan(base: Path, autonomous_plan_id: str) -> dict[str, Any] | None:
    return _load_run_by_id(base, _run_id(autonomous_plan_id))


def _load_run_for_document(base: Path, document_id: str, source_revision: int | None) -> dict[str, Any] | None:
    for item in _load_runs(base):
        if str(item.get("document_id") or "") == str(document_id or "") and _normalize_revision(item.get("source_revision")) == source_revision:
            return item
    return None


def _load_receipt_by_id(base: Path, autonomous_receipt_id: str | None) -> dict[str, Any] | None:
    if not autonomous_receipt_id:
        return None
    payload = analysis_backend._read_json(_receipt_path(base, autonomous_receipt_id))
    return deepcopy(dict(payload)) if isinstance(payload, dict) else None


def _load_receipt_for_run(base: Path, autonomous_run_id: str) -> dict[str, Any] | None:
    return _load_receipt_by_id(base, _receipt_id(autonomous_run_id))


def _persist_run(base: Path, run: Mapping[str, Any]) -> bool:
    path = _run_path(base, str(run.get("autonomous_run_id") or ""))
    before_run = analysis_backend._read_json(path)
    before_index = analysis_backend._read_json(base / "indexes" / RUN_INDEX)
    try:
        analysis_backend._atomic_write_json(path, run)
        _update_run_index(base)
        return True
    except Exception:
        analysis_backend._restore_json(path, before_run)
        analysis_backend._restore_json(base / "indexes" / RUN_INDEX, before_index)
        return False


def _create_receipt_if_needed(base: Path, run: Mapping[str, Any], plan: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(plan, Mapping):
        return None
    if str(run.get("status") or "") not in FINAL_RUN_STATUSES:
        return None
    existing = _load_receipt_for_run(base, str(run.get("autonomous_run_id") or ""))
    if isinstance(existing, dict):
        return existing
    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "autonomous_receipt_id": _receipt_id(str(run.get("autonomous_run_id") or "")),
        "autonomous_run_id": run.get("autonomous_run_id"),
        "autonomous_plan_id": run.get("autonomous_plan_id"),
        "document_id": run.get("document_id"),
        "source_revision": run.get("source_revision"),
        "document_class": run.get("document_class"),
        "manifest_fingerprint": run.get("manifest_fingerprint"),
        "plan_fingerprint": run.get("plan_fingerprint"),
        "policy_id": run.get("policy_id"),
        "citation_count": run.get("citation_count", 0),
        "proposal_draft_count": run.get("proposal_draft_count", 0),
        "promoted_proposal_count": run.get("promoted_proposal_count", 0),
        "non_rule_information_count": run.get("non_rule_information_count", 0),
        "activated_rule_count": run.get("activated_rule_count", 0),
        "certified_rule_count": run.get("certified_rule_count", 0),
        "blocked_item_count": run.get("blocked_item_count", 0),
        "final_status": run.get("status"),
        "created_at_utc": analysis_backend._now(),
        "warnings": list(run.get("warnings", [])),
    }
    path = _receipt_path(base, str(receipt["autonomous_receipt_id"]))
    before_receipt = analysis_backend._read_json(path)
    before_index = analysis_backend._read_json(base / "indexes" / RECEIPT_INDEX)
    try:
        analysis_backend._atomic_write_json(path, receipt)
        _update_receipt_index(base)
        return receipt
    except Exception:
        analysis_backend._restore_json(path, before_receipt)
        analysis_backend._restore_json(base / "indexes" / RECEIPT_INDEX, before_index)
        return None


def _count_certified_rules(base: Path, document_id: str, source_revision: int | None) -> int:
    count = 0
    for path in sorted((base / "rule_activation_certification_receipts").glob("*.json")):
        payload = analysis_backend._read_json(path)
        if not isinstance(payload, Mapping):
            continue
        rule_id = _non_empty_text(payload.get("rule_id"))
        if not rule_id:
            continue
        loaded = analysis_backend.load_canonical_rule(rule_id, root=base)
        rule = loaded.get("rule") if loaded.get("status") == "loaded" else None
        if isinstance(rule, Mapping) and str(rule.get("document_id") or "") == document_id and _normalize_revision(rule.get("source_revision")) == source_revision and str(payload.get("certification_status") or "") == "completed":
            count += 1
    return count


def _plan_stale_blockers(base: Path, plan: Mapping[str, Any]) -> list[str]:
    readiness = validate_autonomous_pdf_readiness(str(plan.get("document_id") or ""), int(plan.get("source_revision") or 0), root=base)
    blockers = list(readiness.get("blockers", []))
    manifest = load_document_manifest(str(plan.get("document_id") or ""), root=base).get("manifest")
    if isinstance(manifest, Mapping) and str(manifest.get("pipeline_fingerprint") or "") != str(plan.get("manifest_fingerprint") or ""):
        blockers.append("manifest_fingerprint_changed")
    return _dedupe(blockers)


def _plan_id(plan_fingerprint: str) -> str:
    return f"autonomous_pdf_plan_{plan_fingerprint[7:23]}"


def _run_id(plan_id: str) -> str:
    return f"autonomous_pdf_run_{analysis_backend._safe_id(plan_id)[-16:]}"


def _receipt_id(run_id: str) -> str:
    return f"autonomous_pdf_receipt_{analysis_backend._safe_id(run_id)[-16:]}"


def _plan_path(base: Path, autonomous_plan_id: str) -> Path:
    return base / RUN_DIR / f"{analysis_backend._safe_id(autonomous_plan_id)}.json"


def _run_path(base: Path, autonomous_run_id: str) -> Path:
    return base / RUN_DIR / f"{analysis_backend._safe_id(autonomous_run_id)}.json"


def _receipt_path(base: Path, autonomous_receipt_id: str) -> Path:
    return base / RECEIPT_DIR / f"{analysis_backend._safe_id(autonomous_receipt_id)}.json"


def _update_run_index(base: Path) -> None:
    items = []
    for path in sorted((base / RUN_DIR).glob("*.json")):
        payload = analysis_backend._read_json(path)
        if not isinstance(payload, Mapping):
            continue
        items.append(
            {
                "record_id": payload.get("autonomous_run_id") or payload.get("autonomous_plan_id"),
                "record_type": "run" if payload.get("schema_version") == RUN_SCHEMA else "plan" if payload.get("schema_version") == PLAN_SCHEMA else "unknown",
                "autonomous_plan_id": payload.get("autonomous_plan_id"),
                "autonomous_run_id": payload.get("autonomous_run_id"),
                "document_id": payload.get("document_id"),
                "source_revision": payload.get("source_revision"),
                "status": payload.get("status"),
                "updated_at_utc": payload.get("updated_at_utc"),
            }
        )
    analysis_backend._atomic_write_json(base / "indexes" / RUN_INDEX, {"schema_version": "autonomous_pdf_run_index_v1", "items": items, "updated_at_utc": analysis_backend._now()})


def _update_receipt_index(base: Path) -> None:
    items = []
    for item in _load_receipts(base):
        items.append(
            {
                "autonomous_receipt_id": item.get("autonomous_receipt_id"),
                "autonomous_run_id": item.get("autonomous_run_id"),
                "autonomous_plan_id": item.get("autonomous_plan_id"),
                "document_id": item.get("document_id"),
                "source_revision": item.get("source_revision"),
                "final_status": item.get("final_status"),
                "created_at_utc": item.get("created_at_utc"),
            }
        )
    analysis_backend._atomic_write_json(base / "indexes" / RECEIPT_INDEX, {"schema_version": "autonomous_pdf_receipt_index_v1", "items": items, "updated_at_utc": analysis_backend._now()})


def _load_runs(base: Path) -> list[dict[str, Any]]:
    items = []
    for path in sorted((base / RUN_DIR).glob("*.json")):
        payload = analysis_backend._read_json(path)
        if isinstance(payload, Mapping) and str(payload.get("schema_version") or "") == RUN_SCHEMA:
            items.append(deepcopy(dict(payload)))
    return items


def _load_receipts(base: Path) -> list[dict[str, Any]]:
    items = []
    for path in sorted((base / RECEIPT_DIR).glob("*.json")):
        payload = analysis_backend._read_json(path)
        if isinstance(payload, Mapping):
            items.append(deepcopy(dict(payload)))
    return items


def _manifest_pipeline_status(manifest: Mapping[str, Any] | None, key: str) -> str:
    if not isinstance(manifest, Mapping):
        return "unknown"
    return str(((manifest.get("pipeline") or {}).get(key)) or "unknown")


def _blocked_item_counts(items: list[Mapping[str, Any]] | Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items or []:
        blocker = str((item or {}).get("blocker") or "").strip()
        if blocker:
            counts[blocker] = counts.get(blocker, 0) + 1
    return counts


def _normalize_limit(value: Any, key: str) -> int:
    default = DEFAULT_LIMITS[key]
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return max(1, value)


def _normalize_revision(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        normalized = int(value.strip())
        return normalized if normalized > 0 else None
    return None


def _non_empty_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(str(item) for item in values if str(item)))


__all__ = [
    "build_autonomous_pdf_workspace",
    "validate_autonomous_pdf_readiness",
    "build_autonomous_pdf_plan",
    "run_autonomous_pdf_pipeline",
    "load_autonomous_pdf_run",
    "cancel_autonomous_pdf_pipeline",
    "get_autonomous_pdf_health",
    "format_autonomous_pdf_report",
]
