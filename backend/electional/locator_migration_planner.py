from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .document_content_curation import _atomic_write_json
from .document_manifest import build_document_manifest, validate_source_locator
from .evidence_binder import load_evidence_binder
from .proposal_review import load_proposal_review
from .source_documents import SOURCE_DOCUMENT_ROOT
from .source_impact_analysis import find_source_dependencies
from .source_knowledge import list_source_proposals, load_chunks

PLAN_DIR = "locator_migration_plans"
PLAN_INDEX = "locator_migration_plan_index.json"
PLAN_SCHEMA_VERSION = "locator_migration_plan_v1"
AUDIT_SCHEMA_VERSION = "locator_contract_audit_v1"
CLASSIFICATION_ORDER = {"already_valid": 0, "safe_candidate": 1, "manual_review": 2, "blocked": 3, "unsupported": 4}
ALLOWED_SCOPES = {"all", "citations", "proposals", "evidence_binders", "stale_only", "critical_only"}


def audit_document_locator_contracts(
    document_id: str,
    include_dependents: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = Path(root)
    manifest = build_document_manifest(document_id, regenerate=False, root=base)
    current_revision = manifest.get("source_revision")
    chunks = load_chunks(document_id=document_id, root=base)
    chunk_map = {chunk.chunk_id: chunk for chunk in chunks}
    items: list[dict[str, Any]] = []
    blockers: list[str] = []
    warnings: list[str] = []
    citation_dir = base / "citations"
    proposal_dir = base / "proposals"
    for path in sorted(citation_dir.glob("*.json")):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        if str(payload.get("document_id") or "") != document_id and str(payload.get("chunk_id") or "") not in chunk_map:
            continue
        items.append(_audit_record("citation", str(payload.get("citation_id") or path.stem), payload, document_id, current_revision, chunk_map, base))
    for path in sorted(proposal_dir.glob("*.json")):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        if str(payload.get("document_id") or "") != document_id and str(payload.get("chunk_id") or "") not in chunk_map:
            continue
        items.append(_audit_record("proposal", str(payload.get("proposal_id") or path.stem), payload, document_id, current_revision, chunk_map, base))
    if include_dependents:
        dependencies = find_source_dependencies(document_id, root=base)
        warnings.extend(list(dependencies.get("warnings", [])) if isinstance(dependencies.get("warnings"), list) else [])
    stale_count = sum(1 for item in items if item.get("locator_status") in {"stale_revision", "missing_chunk", "missing_page", "page_chunk_mismatch", "invalid_offset"})
    ambiguous_count = sum(1 for item in items if item.get("candidate_status") == "ambiguous")
    critical_count = sum(1 for item in items if item.get("locator_status") in {"cross_document_reference", "corrupt_record"})
    valid_count = sum(1 for item in items if item.get("locator_status") == "valid")
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "document_id": document_id,
        "current_source_revision": current_revision,
        "records_checked": len(items),
        "valid_count": valid_count,
        "stale_count": stale_count,
        "ambiguous_count": ambiguous_count,
        "critical_count": critical_count,
        "items": items,
        "warnings": sorted(set(warnings)),
        "blockers": blockers,
    }


def build_locator_migration_plan(
    document_id: str,
    scope: str = "all",
    regenerate: bool = False,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = Path(root)
    if scope not in ALLOWED_SCOPES:
        return {"status": "invalid", "warnings": ["unsupported_scope"], "blockers": ["unsupported_scope"]}
    _ensure_storage(base)
    if not regenerate:
        reusable = _find_latest_plan(document_id, base)
        if reusable and not _plan_is_stale(reusable, root=base):
            return {"status": reusable.get("status", "planned"), "migration_plan_id": reusable.get("migration_plan_id"), "plan": reusable, "warnings": []}
    audit = audit_document_locator_contracts(document_id, include_dependents=True, root=base)
    manifest = build_document_manifest(document_id, regenerate=False, root=base)
    dependency = find_source_dependencies(document_id, root=base)
    filtered = _filter_audit_items(audit.get("items", []), scope)
    proposals = [_proposal_from_audit(item, dependency) for item in filtered]
    plan = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "migration_plan_id": _plan_id(document_id, audit, filtered, dependency),
        "document_id": document_id,
        "source_revision": manifest.get("source_revision"),
        "document_scoped_fingerprint": _document_fingerprint(document_id, base),
        "scope": scope,
        "status": "planned",
        "proposal_count": len(proposals),
        "safe_candidate_count": sum(1 for proposal in proposals if proposal.get("classification") == "safe_candidate"),
        "manual_review_count": sum(1 for proposal in proposals if proposal.get("classification") == "manual_review"),
        "blocked_count": sum(1 for proposal in proposals if proposal.get("classification") == "blocked"),
        "audit": audit,
        "proposals": proposals,
        "dependency_summary": _dependency_summary(dependency),
        "fingerprint": _plan_fingerprint(document_id, manifest.get("source_revision"), _document_fingerprint(document_id, base), scope, proposals, dependency),
        "created_at_utc": _now(),
        "updated_at_utc": _now(),
        "warnings": sorted(set(audit.get("warnings", [])) | set(dependency.get("warnings", []))),
        "blockers": list(audit.get("blockers", [])),
    }
    _atomic_write_json(_plan_path(base, str(plan["migration_plan_id"])), plan)
    _update_plan_index(base)
    return {"status": "planned", "migration_plan_id": plan["migration_plan_id"], "plan": plan, "warnings": plan["warnings"]}


def load_locator_migration_plan(
    migration_plan_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    payload = _read_json(_plan_path(Path(root), migration_plan_id))
    if not isinstance(payload, dict):
        return {"migration_plan_id": migration_plan_id, "status": "not_found", "plan": None, "warnings": []}
    plan = json.loads(json.dumps(payload, sort_keys=True, default=str))
    if _plan_is_stale(plan, root=root):
        plan["status"] = "stale"
    return {"migration_plan_id": migration_plan_id, "status": plan.get("status", "planned"), "plan": plan, "warnings": []}


def list_locator_migration_proposals(
    migration_plan_id: str,
    classification: str | None = None,
    record_type: str | None = None,
    limit: int = 100,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    loaded = load_locator_migration_plan(migration_plan_id, root=root)
    plan = loaded.get("plan")
    if not isinstance(plan, dict):
        return {"migration_plan_id": migration_plan_id, "status": "not_found", "items": [], "warnings": []}
    items = [item for item in plan.get("proposals", []) if isinstance(item, dict)]
    if classification:
        items = [item for item in items if item.get("classification") == classification]
    if record_type:
        items = [item for item in items if item.get("record_type") == record_type]
    items.sort(key=lambda item: (CLASSIFICATION_ORDER.get(str(item.get("classification")), 9), str(item.get("record_type") or ""), str(item.get("record_id") or ""), str(item.get("proposal_id") or "")))
    return {"migration_plan_id": migration_plan_id, "status": loaded.get("status"), "items": items[: max(0, int(limit or 0))], "warnings": list(plan.get("warnings", []))}


def validate_locator_correction_proposal(
    migration_plan_id: str,
    proposal_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    loaded = load_locator_migration_plan(migration_plan_id, root=root)
    plan = loaded.get("plan")
    if not isinstance(plan, dict):
        return {"migration_plan_id": migration_plan_id, "proposal_id": proposal_id, "valid": False, "classification": "blocked", "apply_allowed": False, "warnings": [], "blockers": ["plan_not_found"]}
    proposal = next((item for item in plan.get("proposals", []) if isinstance(item, dict) and item.get("proposal_id") == proposal_id), None)
    if not isinstance(proposal, dict):
        return {"migration_plan_id": migration_plan_id, "proposal_id": proposal_id, "valid": False, "classification": "blocked", "apply_allowed": False, "warnings": [], "blockers": ["proposal_not_found"]}
    blockers: list[str] = []
    warnings: list[str] = []
    if _plan_is_stale(plan, root=root):
        blockers.append("migration_plan_stale")
    record = _load_record_payload(str(proposal.get("record_type") or ""), str(proposal.get("record_id") or ""), Path(root))
    if not isinstance(record, dict):
        blockers.append("record_missing")
    elif _extract_locator(record) != proposal.get("before"):
        blockers.append("locator_before_state_changed")
    after = proposal.get("proposed_after")
    if proposal.get("classification") == "safe_candidate" and isinstance(after, dict):
        locator_validation = validate_source_locator(_to_manifest_locator(after), root=root)
        if not locator_validation.get("valid"):
            blockers.extend(locator_validation.get("blockers", []))
            warnings.extend(locator_validation.get("warnings", []))
        if int(proposal.get("candidate_count", 0) or 0) != 1:
            blockers.append("candidate_count_not_unique")
    return {
        "migration_plan_id": migration_plan_id,
        "proposal_id": proposal_id,
        "valid": not blockers and proposal.get("classification") == "safe_candidate",
        "classification": proposal.get("classification"),
        "apply_allowed": False,
        "warnings": sorted(set(warnings)),
        "blockers": sorted(set(blockers)),
    }


def preview_locator_correction(
    migration_plan_id: str,
    proposal_id: str,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    loaded = load_locator_migration_plan(migration_plan_id, root=root)
    plan = loaded.get("plan")
    proposal = next((item for item in (plan or {}).get("proposals", []) if isinstance(item, dict) and item.get("proposal_id") == proposal_id), None)
    if not isinstance(proposal, dict):
        return {"migration_plan_id": migration_plan_id, "proposal_id": proposal_id, "status": "not_found", "warnings": [], "blockers": ["proposal_not_found"]}
    summary = {
        "migration_plan_id": migration_plan_id,
        "proposal_id": proposal_id,
        "record_type": proposal.get("record_type"),
        "record_id": proposal.get("record_id"),
        "classification": proposal.get("classification"),
        "reason": proposal.get("reason"),
        "before": proposal.get("before"),
        "proposed_after": proposal.get("proposed_after"),
        "dependency_summary": proposal.get("dependency_impact", {}),
        "would_modify": [f"{proposal.get('record_type')} locator"],
        "actually_modified": [],
        "apply_allowed": False,
        "warnings": list(proposal.get("warnings", [])),
    }
    if public_safe:
        return summary
    summary["plan"] = plan
    return summary


def get_locator_migration_health(
    document_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = Path(root)
    _ensure_storage(base)
    plans = []
    for path in sorted((base / PLAN_DIR).glob("*.json")):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        if document_id and str(payload.get("document_id") or "") != document_id:
            continue
        plans.append(payload)
    if not plans:
        return {"status": "empty", "document_id": document_id, "plans_checked": 0, "current_plan_count": 0, "stale_plan_count": 0, "safe_candidate_count": 0, "manual_review_count": 0, "blocked_count": 0, "cross_document_count": 0, "warnings": [], "recommended_action": "Build a locator migration plan."}
    stale_count = sum(1 for plan in plans if _plan_is_stale(plan, root=base))
    safe_count = sum(int(plan.get("safe_candidate_count", 0) or 0) for plan in plans)
    manual_count = sum(int(plan.get("manual_review_count", 0) or 0) for plan in plans)
    blocked_count = sum(int(plan.get("blocked_count", 0) or 0) for plan in plans)
    cross_document = sum(1 for plan in plans for proposal in plan.get("proposals", []) if isinstance(proposal, dict) and proposal.get("classification") == "blocked" and proposal.get("reason") == "cross_document_candidate")
    warnings = []
    if manual_count:
        warnings.append("one_ambiguous_locator_requires_manual_review")
    status = "healthy"
    if stale_count:
        status = "stale"
    elif blocked_count or cross_document:
        status = "critical"
    elif warnings:
        status = "warning"
    return {
        "status": status,
        "document_id": document_id,
        "plans_checked": len(plans),
        "current_plan_count": len(plans) - stale_count,
        "stale_plan_count": stale_count,
        "safe_candidate_count": safe_count,
        "manual_review_count": manual_count,
        "blocked_count": blocked_count,
        "cross_document_count": cross_document,
        "warnings": warnings,
        "recommended_action": "Review one ambiguous locator before migration execution." if manual_count else "No action required.",
    }


def format_locator_migration_report(
    document_id: str | None = None,
    migration_plan_id: str | None = None,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    plan = None
    if migration_plan_id:
        plan = load_locator_migration_plan(migration_plan_id, root=root).get("plan")
    elif document_id:
        plan = _find_latest_plan(document_id, Path(root))
    if not isinstance(plan, dict):
        health = get_locator_migration_health(document_id, root=root)
        return "\n".join(
            [
                "Locator Migration Plan Report",
                "",
                f"Document: {document_id or 'unknown'}",
                f"Plan Status: {health.get('status')}",
                "",
                "Recommended Action:",
                str(health.get("recommended_action") or "Build a migration plan."),
            ]
        )
    audit = plan.get("audit", {})
    dependency = plan.get("dependency_summary", {})
    lines = [
        "Locator Migration Plan Report",
        "",
        f"Document: {plan.get('document_id')}",
        f"Current Source Revision: {plan.get('source_revision')}",
        f"Plan Status: {'stale' if _plan_is_stale(plan, root=root) else plan.get('status')}",
        "",
        "Locator Audit:",
        f"- Records Checked: {audit.get('records_checked', 0)}",
        f"- Valid: {audit.get('valid_count', 0)}",
        f"- Stale: {audit.get('stale_count', 0)}",
        f"- Ambiguous: {audit.get('ambiguous_count', 0)}",
        f"- Critical: {audit.get('critical_count', 0)}",
        "",
        "Correction Proposals:",
        f"- Safe Candidates: {plan.get('safe_candidate_count', 0)}",
        f"- Manual Review: {plan.get('manual_review_count', 0)}",
        f"- Blocked: {plan.get('blocked_count', 0)}",
        "- Applied: 0",
        "",
        "Dependency Impact:",
        f"- Citations: {dependency.get('citation_count', 0)}",
        f"- Proposals: {dependency.get('proposal_count', 0)}",
        f"- Proposal Reviews: {dependency.get('proposal_review_count', 0)}",
        f"- Evidence Binders: {dependency.get('evidence_binder_count', 0)}",
        "",
        "Important:",
        "No records were modified. This plan is a non-destructive preview only.",
        "",
        "Recommended Action:",
        "Review the ambiguous and blocked proposals before any later execution phase.",
    ]
    if not public_safe:
        lines.extend(["", f"Plan Fingerprint: {plan.get('fingerprint')}"])
    return "\n".join(lines)


def _audit_record(record_type: str, record_id: str, payload: dict[str, Any], document_id: str, current_revision: object, chunk_map: dict[str, Any], root: Path) -> dict[str, Any]:
    locator = _extract_locator(payload)
    locator_status = "valid"
    warnings: list[str] = []
    candidate_status = "none"
    candidate_count = 0
    candidates: list[dict[str, Any]] = []
    if not locator:
        locator_status = "unsupported_locator"
    elif str(locator.get("document_id") or "") != document_id:
        locator_status = "cross_document_reference"
    else:
        validation = validate_source_locator(_to_manifest_locator(locator), root=root)
        if validation.get("blockers"):
            blockers = set(validation.get("blockers", []))
            if "chunk_id_document_mismatch" in blockers:
                locator_status = "cross_document_reference"
            elif "page_number_chunk_mismatch" in blockers:
                locator_status = "page_chunk_mismatch"
            elif "page_number_invalid" in blockers:
                locator_status = "missing_page"
            else:
                locator_status = "missing_chunk" if "chunk_id_unverifiable" in validation.get("warnings", []) else "unknown"
        elif "chunk_id_unverifiable" in validation.get("warnings", []) and locator.get("chunk_id"):
            locator_status = "missing_chunk"
        elif "page_number_unverifiable_without_chunk" in validation.get("warnings", []) and locator.get("page") is not None:
            locator_status = "missing_chunk"
        if locator_status == "valid" and locator.get("source_revision") and int(locator.get("source_revision") or 0) != int(current_revision or 0):
            locator_status = "stale_revision"
        if locator_status == "valid" and _invalid_offsets(locator):
            locator_status = "invalid_offset"
        if locator_status != "valid":
            candidates = _find_candidates(locator, document_id, current_revision, chunk_map)
            candidate_count = len(candidates)
            if any(candidate.get("candidate_classification") == "cross_document_candidate" for candidate in candidates):
                candidate_status = "cross_document_candidate"
            elif candidate_count == 1:
                candidate_status = "unique_candidate"
            elif candidate_count > 1:
                candidate_status = "ambiguous"
                if locator_status == "unknown":
                    locator_status = "ambiguous_target"
            else:
                candidate_status = "no_candidate"
    return {
        "record_type": record_type,
        "record_id": record_id,
        "locator_status": locator_status,
        "current_locator": locator,
        "candidate_status": candidate_status,
        "candidate_count": candidate_count,
        "candidate_targets": candidates,
        "warnings": warnings,
    }


def _find_candidates(locator: dict[str, Any], document_id: str, current_revision: object, chunk_map: dict[str, Any]) -> list[dict[str, Any]]:
    chunk_id = str(locator.get("chunk_id") or "")
    page = locator.get("page")
    candidates: list[dict[str, Any]] = []
    if chunk_id and chunk_id in chunk_map:
        chunk = chunk_map[chunk_id]
        candidates.append(
            {
                "candidate_classification": "exact_stable_identity",
                "chunk_id": chunk.chunk_id,
                "page": chunk.page_start,
                "source_revision": current_revision,
                "document_id": chunk.document_id,
            }
        )
        return candidates
    if page is not None:
        page_matches = [chunk for chunk in chunk_map.values() if chunk.page_start is not None and chunk.page_end is not None and int(chunk.page_start) <= int(page) <= int(chunk.page_end)]
        if len(page_matches) == 1:
            chunk = page_matches[0]
            candidates.append(
                {
                    "candidate_classification": "unique_page_offset_match",
                    "chunk_id": chunk.chunk_id,
                    "page": page,
                    "source_revision": current_revision,
                    "document_id": chunk.document_id,
                }
            )
        elif len(page_matches) > 1:
            for chunk in page_matches:
                candidates.append(
                    {
                        "candidate_classification": "multiple_candidates",
                        "chunk_id": chunk.chunk_id,
                        "page": page,
                        "source_revision": current_revision,
                        "document_id": chunk.document_id,
                    }
                )
    if locator.get("document_id") and str(locator.get("document_id")) != document_id:
        candidates.append({"candidate_classification": "cross_document_candidate", "chunk_id": None, "page": page, "source_revision": current_revision, "document_id": locator.get("document_id")})
    return candidates


def _proposal_from_audit(item: dict[str, Any], dependency: dict[str, Any]) -> dict[str, Any]:
    classification = "already_valid"
    reason = item.get("locator_status")
    before = item.get("current_locator")
    proposed_after = None
    if item.get("locator_status") == "valid":
        classification = "already_valid"
    elif item.get("candidate_status") == "unique_candidate" and item.get("candidate_targets"):
        candidate = item["candidate_targets"][0]
        classification = "safe_candidate"
        reason = candidate.get("candidate_classification")
        proposed_after = {
            "document_id": candidate.get("document_id"),
            "source_revision": candidate.get("source_revision"),
            "page": candidate.get("page"),
            "chunk_id": candidate.get("chunk_id"),
            "start_offset": before.get("start_offset") if isinstance(before, dict) else None,
            "end_offset": before.get("end_offset") if isinstance(before, dict) else None,
        }
    elif item.get("candidate_status") == "ambiguous":
        classification = "manual_review"
        reason = "multiple_candidates"
    elif item.get("locator_status") == "cross_document_reference" or item.get("candidate_status") == "cross_document_candidate":
        classification = "blocked"
        reason = "cross_document_candidate"
    elif item.get("locator_status") == "unsupported_locator":
        classification = "unsupported"
        reason = "unsupported"
    else:
        classification = "manual_review"
        reason = "no_candidate"
    return {
        "proposal_id": _proposal_id(item),
        "record_type": item.get("record_type"),
        "record_id": item.get("record_id"),
        "classification": classification,
        "reason": reason,
        "before": before,
        "proposed_after": proposed_after,
        "candidate_count": item.get("candidate_count", 0),
        "confidence_basis": _confidence_basis(classification, reason),
        "dependency_impact": _proposal_dependency_impact(item, dependency),
        "apply_allowed": False,
        "warnings": list(item.get("warnings", [])),
    }


def _proposal_dependency_impact(item: dict[str, Any], dependency: dict[str, Any]) -> dict[str, Any]:
    record_type = str(item.get("record_type") or "")
    record_id = str(item.get("record_id") or "")
    proposal_ids = list(dependency.get("affected_records", {}).get("proposal_ids", []))
    review_ids = list(dependency.get("affected_records", {}).get("proposal_review_ids", []))
    binder_ids = list(dependency.get("affected_records", {}).get("evidence_binder_ids", []))
    citation_ids = list(dependency.get("affected_records", {}).get("citation_ids", []))
    return {
        "citation_count": 1 if record_type == "citation" else 0,
        "proposal_count": len(proposal_ids),
        "proposal_review_count": len(review_ids),
        "evidence_binder_count": len(binder_ids),
        "impact_item_count": 0,
        "revalidation_resolution_count": 0,
        "dependency_ids": {
            "citations": [record_id] if record_type == "citation" else citation_ids,
            "proposals": proposal_ids,
            "proposal_reviews": review_ids,
            "evidence_binders": binder_ids,
        },
    }


def _dependency_summary(dependency: dict[str, Any]) -> dict[str, Any]:
    affected = dependency.get("affected_records", {})
    return {
        "citation_count": len(affected.get("citation_ids", [])),
        "proposal_count": len(affected.get("proposal_ids", [])),
        "proposal_review_count": len(affected.get("proposal_review_ids", [])),
        "evidence_binder_count": len(affected.get("evidence_binder_ids", [])),
        "impact_item_count": 0,
        "revalidation_resolution_count": 0,
        "dependency_ids": {
            "citations": list(affected.get("citation_ids", [])),
            "proposals": list(affected.get("proposal_ids", [])),
            "proposal_reviews": list(affected.get("proposal_review_ids", [])),
            "evidence_binders": list(affected.get("evidence_binder_ids", [])),
        },
    }


def _extract_locator(payload: dict[str, Any]) -> dict[str, Any] | None:
    document_id = str(payload.get("document_id") or "").strip()
    chunk_id = str(payload.get("chunk_id") or "").strip()
    page = payload.get("page")
    if page is None:
        page = payload.get("page_number")
    if page is None:
        page = payload.get("page_start")
    if page is None and payload.get("page_end") is not None:
        page = payload.get("page_end")
    source_revision = payload.get("source_revision")
    start_offset = payload.get("start_offset")
    if start_offset is None:
        start_offset = payload.get("character_start")
    end_offset = payload.get("end_offset")
    if end_offset is None:
        end_offset = payload.get("character_end")
    if not document_id and not chunk_id:
        return None
    return {
        "document_id": document_id or None,
        "source_revision": int(source_revision) if isinstance(source_revision, int) and not isinstance(source_revision, bool) else source_revision,
        "page": int(page) if isinstance(page, int) and not isinstance(page, bool) else page,
        "chunk_id": chunk_id or None,
        "start_offset": int(start_offset) if isinstance(start_offset, int) and not isinstance(start_offset, bool) else start_offset,
        "end_offset": int(end_offset) if isinstance(end_offset, int) and not isinstance(end_offset, bool) else end_offset,
    }


def _to_manifest_locator(locator: dict[str, Any]) -> dict[str, Any]:
    return {
        "document_id": locator.get("document_id"),
        "source_revision": locator.get("source_revision"),
        "page_number": locator.get("page"),
        "chunk_id": locator.get("chunk_id"),
        "character_start": locator.get("start_offset"),
        "character_end": locator.get("end_offset"),
    }


def _invalid_offsets(locator: dict[str, Any]) -> bool:
    start = locator.get("start_offset")
    end = locator.get("end_offset")
    return (start is not None and end is not None and (not isinstance(start, int) or not isinstance(end, int) or start < 0 or end < start))


def _plan_is_stale(plan: dict[str, Any], *, root: Path | str) -> bool:
    manifest = build_document_manifest(str(plan.get("document_id") or ""), regenerate=False, root=root)
    if manifest.get("source_revision") != plan.get("source_revision"):
        return True
    if _document_fingerprint(str(plan.get("document_id") or ""), Path(root)) != plan.get("document_scoped_fingerprint"):
        return True
    expected = _plan_fingerprint(str(plan.get("document_id") or ""), plan.get("source_revision"), plan.get("document_scoped_fingerprint"), str(plan.get("scope") or "all"), plan.get("proposals", []), plan.get("dependency_summary", {}))
    return expected != plan.get("fingerprint")


def _filter_audit_items(items: list[dict[str, Any]], scope: str) -> list[dict[str, Any]]:
    filtered = [item for item in items if isinstance(item, dict)]
    if scope == "citations":
        filtered = [item for item in filtered if item.get("record_type") == "citation"]
    elif scope == "proposals":
        filtered = [item for item in filtered if item.get("record_type") == "proposal"]
    elif scope == "evidence_binders":
        filtered = []
    elif scope == "stale_only":
        filtered = [item for item in filtered if item.get("locator_status") != "valid"]
    elif scope == "critical_only":
        filtered = [item for item in filtered if item.get("locator_status") in {"cross_document_reference", "corrupt_record"}]
    return filtered


def _load_record_payload(record_type: str, record_id: str, root: Path) -> dict[str, Any] | None:
    folder = "citations" if record_type == "citation" else "proposals" if record_type == "proposal" else None
    if not folder:
        return None
    return _read_json(root / folder / f"{record_id}.json")


def _plan_id(document_id: str, audit: dict[str, Any], items: list[dict[str, Any]], dependency: dict[str, Any]) -> str:
    digest = hashlib.sha256(json.dumps({"document_id": document_id, "records": [(item.get("record_type"), item.get("record_id"), item.get("current_locator")) for item in items], "dependency_ids": dependency.get("affected_records", {})}, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()[:12]
    return f"locator_plan_{document_id}_{digest}"


def _proposal_id(item: dict[str, Any]) -> str:
    digest = hashlib.sha256(json.dumps({"record_type": item.get("record_type"), "record_id": item.get("record_id"), "locator": item.get("current_locator")}, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()[:10]
    return f"locator_proposal_{digest}"


def _plan_fingerprint(document_id: str, source_revision: object, document_fingerprint: object, scope: str, proposals: list[dict[str, Any]], dependency: dict[str, Any]) -> str:
    payload = {
        "document_id": document_id,
        "source_revision": source_revision,
        "document_scoped_fingerprint": document_fingerprint,
        "scope": scope,
        "proposals": [
            {
                "record_type": proposal.get("record_type"),
                "record_id": proposal.get("record_id"),
                "classification": proposal.get("classification"),
                "before": proposal.get("before"),
                "proposed_after": proposal.get("proposed_after"),
                "candidate_count": proposal.get("candidate_count"),
            }
            for proposal in proposals
        ],
        "dependency_ids": dependency.get("dependency_ids", {}),
    }
    return "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _document_fingerprint(document_id: str, root: Path) -> str | None:
    path = root / "document_content_maps" / f"{document_id}.json"
    payload = _read_json(path) or {}
    return payload.get("document_scoped_fingerprint")


def _confidence_basis(classification: str, reason: str) -> list[str]:
    if classification == "safe_candidate" and reason == "exact_stable_identity":
        return ["same_document", "exact_stable_identity", "valid_page_chunk_relationship"]
    if classification == "safe_candidate":
        return ["same_document", reason, "valid_page_chunk_relationship"]
    if classification == "blocked":
        return ["cross_document_rejected"]
    if classification == "manual_review":
        return [reason, "manual_review"]
    return [reason]


def _find_latest_plan(document_id: str, root: Path) -> dict[str, Any] | None:
    plans = []
    for path in sorted((root / PLAN_DIR).glob("locator_plan_*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict) and str(payload.get("document_id") or "") == document_id:
            plans.append(payload)
    plans.sort(key=lambda item: str(item.get("updated_at_utc") or ""), reverse=True)
    return plans[0] if plans else None


def _update_plan_index(root: Path) -> None:
    entries = []
    for path in sorted((root / PLAN_DIR).glob("locator_plan_*.json")):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        entries.append(
            {
                "migration_plan_id": payload.get("migration_plan_id"),
                "document_id": payload.get("document_id"),
                "source_revision": payload.get("source_revision"),
                "scope": payload.get("scope"),
                "status": payload.get("status"),
                "proposal_count": payload.get("proposal_count"),
                "updated_at_utc": payload.get("updated_at_utc"),
            }
        )
    _atomic_write_json(root / "indexes" / PLAN_INDEX, {"entries": entries, "updated_at_utc": _now()})


def _plan_path(root: Path, migration_plan_id: str) -> Path:
    return root / PLAN_DIR / f"{migration_plan_id}.json"


def _ensure_storage(root: Path) -> None:
    (root / PLAN_DIR).mkdir(parents=True, exist_ok=True)
    index_path = root / "indexes" / PLAN_INDEX
    if not index_path.exists():
        _atomic_write_json(index_path, {"entries": [], "updated_at_utc": _now()})


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
