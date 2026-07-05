"""Controlled review workspace and resolution records for source revalidation."""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from .source_documents import SOURCE_DOCUMENT_ROOT
from .source_impact_analysis import analyze_source_change_impact, ensure_source_impact_dirs, update_source_revalidation_status
from .evidence_binder import load_evidence_binder

RESOLUTION_DIR = "source_revalidation_resolutions"
RESOLUTION_INDEX = "source_revalidation_resolution_index.json"
RESOLUTION_SCHEMA_VERSION = "source_revalidation_resolution_v1"
ALLOWED_DISPOSITIONS = {
    "still_valid",
    "needs_review",
    "invalid_due_to_source",
    "replacement_source_required",
    "deferred",
    "not_applicable",
    "unknown",
}
ALLOWED_RESOLUTION_DECISIONS = {
    "keep_open",
    "resolved_no_change",
    "resolved_with_manual_followup",
    "replacement_source_required",
    "deferred",
    "dismissed",
}
QUEUE_STATUS_BY_DECISION = {
    "keep_open": "in_review",
    "resolved_no_change": "reviewed",
    "resolved_with_manual_followup": "reviewed",
    "replacement_source_required": "reviewed",
    "deferred": "deferred",
    "dismissed": "dismissed",
}
DEPENDENCY_CATEGORIES = {
    "citations": "citation_ids",
    "proposals": "proposal_ids",
    "proposal_reviews": "proposal_review_ids",
    "evidence_binders": "evidence_binder_ids",
}


def build_revalidation_review_workspace(queue_item_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = ensure_source_revalidation_review_dirs(root)
    queue_item = _load_queue_item(queue_item_id, base)
    if queue_item is None:
        return {"queue_item_id": queue_item_id, "status": "not_found", "warnings": ["queue_item_not_found"]}
    impact = analyze_source_change_impact(str(queue_item.get("document_id") or ""), change_type=queue_item.get("change_type"), root=base)
    evidence_recheck = build_revalidation_evidence_recheck(queue_item_id, root=base)
    existing_resolution = load_source_revalidation_resolution(queue_item_id, root=base).get("resolution")
    warnings = list(dict.fromkeys([*queue_item.get("warnings", []), *impact.get("warnings", []), *evidence_recheck.get("warnings", [])]))
    return {
        "queue_item_id": queue_item_id,
        "document_id": queue_item.get("document_id"),
        "change_type": queue_item.get("change_type"),
        "impact_severity": queue_item.get("impact_severity") or impact.get("impact_severity"),
        "queue_status": queue_item.get("status"),
        "source_state": impact.get("source_state", {}),
        "affected_counts": impact.get("affected_counts", {}),
        "affected_record_ids": impact.get("affected_records", {}),
        "evidence_recheck": evidence_recheck,
        "existing_resolution": existing_resolution,
        "warnings": warnings,
        "recommended_action": impact.get("recommended_action"),
    }


def validate_dependency_dispositions(dispositions: dict, *, queue_item_id: str, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    workspace = build_revalidation_review_workspace(queue_item_id, root=root)
    if workspace.get("status") == "not_found":
        return {"valid": False, "blockers": ["queue_item_not_found"], "warnings": [], "normalized": {}}
    normalized = {category: {} for category in DEPENDENCY_CATEGORIES}
    blockers: list[str] = []
    for category, ids_field in DEPENDENCY_CATEGORIES.items():
        expected_ids = set(str(item) for item in workspace.get("affected_record_ids", {}).get(ids_field, []))
        provided = dispositions.get(category, {}) if isinstance(dispositions, dict) else {}
        if not isinstance(provided, dict):
            blockers.append(f"{category}_dispositions_invalid")
            continue
        for record_id, value in provided.items():
            if str(record_id) not in expected_ids:
                blockers.append(f"unknown_{category}_id")
                continue
            if str(value) not in ALLOWED_DISPOSITIONS:
                blockers.append(f"invalid_{category}_disposition")
                continue
            normalized[category][str(record_id)] = str(value)
    return {"valid": not blockers, "blockers": list(dict.fromkeys(blockers)), "warnings": workspace.get("warnings", []), "normalized": normalized}


def build_revalidation_evidence_recheck(queue_item_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    workspace = build_revalidation_review_workspace(queue_item_id, root=root) if False else None
    base = ensure_source_revalidation_review_dirs(root)
    queue_item = _load_queue_item(queue_item_id, base)
    if queue_item is None:
        return {"queue_item_id": queue_item_id, "status": "not_found", "warnings": ["queue_item_not_found"]}
    impact = analyze_source_change_impact(str(queue_item.get("document_id") or ""), change_type=queue_item.get("change_type"), root=base)
    binder_ids = list(impact.get("affected_records", {}).get("evidence_binder_ids", []))
    available = 0
    missing = 0
    weak = 0
    stale = 0
    conflict = 0
    coverage_statuses = {"strong": 0, "usable": 0, "weak": 0, "unknown": 0}
    warnings: list[str] = []
    for binder_id in binder_ids:
        proposal_id = str(binder_id).replace("binder_", "", 1)
        binder = load_evidence_binder(proposal_id, root=base)
        if binder.get("binder_status") == "not_built":
            missing += 1
            warnings.append("evidence_binder_missing")
            continue
        available += 1
        weak_state = binder.get("weak_or_stale_sources", {}) if isinstance(binder.get("weak_or_stale_sources"), dict) else {}
        weak += len(weak_state.get("weak_sources", []))
        stale += len(weak_state.get("stale_sources", []))
        if (binder.get("conflict") or {}).get("status") not in {None, "none"}:
            conflict += 1
        band = str((binder.get("evidence_coverage") or {}).get("coverage_band") or "unknown")
        if band not in coverage_statuses:
            band = "unknown"
        coverage_statuses[band] += 1
    recommended = "Review the affected binder before closure." if binder_ids else "No evidence binder recheck is currently required."
    return {
        "queue_item_id": queue_item_id,
        "evidence_binders_checked": len(binder_ids),
        "binders_available": available,
        "binders_missing": missing,
        "weak_source_warnings": weak,
        "stale_source_warnings": stale,
        "conflict_flags": conflict,
        "coverage_statuses": coverage_statuses,
        "warnings": list(dict.fromkeys(warnings)),
        "recommended_action": recommended,
    }


def save_source_revalidation_resolution(
    queue_item_id: str,
    resolution_decision: str,
    dispositions: dict,
    review_note: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    if resolution_decision not in ALLOWED_RESOLUTION_DECISIONS:
        raise ValueError(f"Unsupported resolution decision: {resolution_decision}")
    base = ensure_source_revalidation_review_dirs(root)
    queue_item = _load_queue_item(queue_item_id, base)
    if queue_item is None:
        raise FileNotFoundError(queue_item_id)
    validation = validate_dependency_dispositions(dispositions, queue_item_id=queue_item_id, root=base)
    closure = validate_revalidation_queue_closure(queue_item_id, resolution_decision, validation.get("normalized", {}), root=base)
    current = load_source_revalidation_resolution(queue_item_id, root=base).get("resolution")
    payload = {
        "resolution_id": current.get("resolution_id") if isinstance(current, dict) else f"resolution_{queue_item_id}",
        "queue_item_id": queue_item_id,
        "document_id": queue_item.get("document_id"),
        "change_type": queue_item.get("change_type"),
        "impact_severity": queue_item.get("impact_severity"),
        "resolution_decision": resolution_decision,
        "dispositions": validation.get("normalized", {}),
        "review_note": review_note,
        "created_at_utc": current.get("created_at_utc") if isinstance(current, dict) else _now(),
        "updated_at_utc": _now(),
        "closure_allowed": bool(closure.get("closure_allowed")),
        "warnings": list(dict.fromkeys([*validation.get("warnings", []), *closure.get("warnings", []), *closure.get("blockers", [])])),
        "schema_version": RESOLUTION_SCHEMA_VERSION,
    }
    _atomic_write_json(_resolution_path(base, queue_item_id), payload)
    _update_resolution_index(base)
    return payload


def validate_revalidation_queue_closure(
    queue_item_id: str,
    resolution_decision: str,
    dispositions: dict,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = ensure_source_revalidation_review_dirs(root)
    workspace = build_revalidation_review_workspace(queue_item_id, root=base)
    if workspace.get("status") == "not_found":
        return {"queue_item_id": queue_item_id, "closure_allowed": False, "target_queue_status": "pending_review", "blockers": ["queue_item_not_found"], "warnings": []}
    blockers: list[str] = []
    warnings: list[str] = []
    if resolution_decision not in ALLOWED_RESOLUTION_DECISIONS:
        blockers.append("missing_resolution_decision")
    validation = validate_dependency_dispositions(dispositions, queue_item_id=queue_item_id, root=base)
    blockers.extend(validation.get("blockers", []))
    normalized = validation.get("normalized", {})
    flattened = [value for category in normalized.values() for value in category.values()]
    total_affected = sum(len(workspace.get("affected_record_ids", {}).get(ids_field, [])) for ids_field in DEPENDENCY_CATEGORIES.values())
    if workspace.get("impact_severity") in {"high", "critical"} and total_affected > 0 and not flattened:
        blockers.append("high_impact_requires_dependency_dispositions")
    if resolution_decision == "resolved_no_change":
        safe_values = {"still_valid", "not_applicable", "unknown"}
        if any(value not in safe_values for value in flattened):
            blockers.append("resolved_no_change_requires_safe_dispositions")
        if workspace.get("impact_severity") == "critical" and "unknown" in flattened and total_affected > 0:
            blockers.append("critical_item_resolved_no_change_with_unknown_dependencies")
        if total_affected > 0 and not _covers_all_dependencies(workspace, normalized):
            blockers.append("resolved_no_change_requires_all_dependency_dispositions")
            warnings.append("missing_dependency_dispositions")
    elif resolution_decision == "replacement_source_required":
        if not any(value in {"replacement_source_required", "invalid_due_to_source"} for value in flattened):
            blockers.append("replacement_source_required_needs_matching_disposition")
    elif resolution_decision == "resolved_with_manual_followup":
        if not any(value in {"needs_review", "deferred"} for value in flattened):
            blockers.append("manual_followup_requires_followup_disposition")
    target_status = QUEUE_STATUS_BY_DECISION.get(resolution_decision, workspace.get("queue_status", "pending_review"))
    return {
        "queue_item_id": queue_item_id,
        "closure_allowed": not blockers,
        "target_queue_status": target_status if not blockers else workspace.get("queue_status", "pending_review"),
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": warnings,
    }


def finalize_source_revalidation_review(
    queue_item_id: str,
    resolution_decision: str,
    dispositions: dict,
    review_note: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = ensure_source_revalidation_review_dirs(root)
    validation = validate_dependency_dispositions(dispositions, queue_item_id=queue_item_id, root=base)
    closure = validate_revalidation_queue_closure(queue_item_id, resolution_decision, validation.get("normalized", {}), root=base)
    resolution = save_source_revalidation_resolution(
        queue_item_id,
        resolution_decision,
        validation.get("normalized", {}),
        review_note=review_note,
        root=base,
    )
    queue_item = _load_queue_item(queue_item_id, base)
    if queue_item is None:
        raise FileNotFoundError(queue_item_id)
    if closure.get("closure_allowed"):
        queue_item = update_source_revalidation_status(queue_item_id, str(closure.get("target_queue_status")), note=review_note, root=base)
    return {
        "queue_item": queue_item,
        "resolution": resolution,
        "closure": closure,
    }


def load_source_revalidation_resolution(queue_item_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    path = _resolution_path(ensure_source_revalidation_review_dirs(root), queue_item_id)
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return {"queue_item_id": queue_item_id, "status": "not_found", "resolution": None, "warnings": []}
    return {"queue_item_id": queue_item_id, "status": "loaded", "resolution": payload, "warnings": []}


def format_source_revalidation_resolution_report(queue_item_id: str, public_safe: bool = True, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> str:
    workspace = build_revalidation_review_workspace(queue_item_id, root=root)
    resolution = load_source_revalidation_resolution(queue_item_id, root=root).get("resolution") or {}
    evidence = build_revalidation_evidence_recheck(queue_item_id, root=root)
    disposition_counts = Counter(value for category in (resolution.get("dispositions", {}) or {}).values() for value in category.values())
    lines = [
        "Source Revalidation Resolution Report",
        "",
        f"Document: {workspace.get('document_id')}",
        f"Change Type: {workspace.get('change_type')}",
        f"Impact Severity: {workspace.get('impact_severity')}",
        f"Queue Status: {workspace.get('queue_status')}",
        f"Resolution: {resolution.get('resolution_decision') or 'not_recorded'}",
        "",
        "Affected Records:",
        f"- Citations: {workspace.get('affected_counts', {}).get('citations')}",
        f"- Proposals: {workspace.get('affected_counts', {}).get('proposals')}",
        f"- Proposal Reviews: {workspace.get('affected_counts', {}).get('proposal_reviews')}",
        f"- Evidence Binders: {workspace.get('affected_counts', {}).get('evidence_binders')}",
        "",
        "Dependency Dispositions:",
        f"- Still Valid: {disposition_counts.get('still_valid', 0)}",
        f"- Needs Review: {disposition_counts.get('needs_review', 0)}",
        f"- Replacement Source Required: {disposition_counts.get('replacement_source_required', 0)}",
        f"- Deferred: {disposition_counts.get('deferred', 0)}",
        "",
        "Evidence Recheck:",
        f"- Binders Available: {evidence.get('binders_available')}",
        f"- Weak Source Warnings: {evidence.get('weak_source_warnings')}",
        f"- Stale Source Warnings: {evidence.get('stale_source_warnings')}",
        "",
        "Review Result:",
        _resolution_result_text(str(resolution.get("resolution_decision") or "")),
    ]
    if not public_safe and resolution.get("review_note"):
        lines.extend(["", "Review Note:", str(resolution.get("review_note"))])
    text = "\n".join(lines)
    return _sanitize(text) if public_safe else text


def list_source_revalidation_resolutions(limit: int = 50, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = ensure_source_revalidation_review_dirs(root)
    items = []
    for path in sorted((base / RESOLUTION_DIR).glob("*.json"), reverse=True):
        payload = _read_json(path)
        if isinstance(payload, dict):
            items.append(payload)
    return {"count": len(items[: max(0, int(limit or 0))]), "items": items[: max(0, int(limit or 0))]}


def get_source_revalidation_resolution_summary(queue_item_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    workspace = build_revalidation_review_workspace(queue_item_id, root=root)
    resolution = load_source_revalidation_resolution(queue_item_id, root=root)
    evidence = build_revalidation_evidence_recheck(queue_item_id, root=root)
    return {
        "queue_item_id": queue_item_id,
        "document_id": workspace.get("document_id"),
        "queue_status": workspace.get("queue_status"),
        "impact_severity": workspace.get("impact_severity"),
        "resolution_status": resolution.get("status"),
        "resolution_decision": (resolution.get("resolution") or {}).get("resolution_decision"),
        "closure_allowed": (resolution.get("resolution") or {}).get("closure_allowed"),
        "evidence_warnings": len(evidence.get("warnings", [])),
    }


def ensure_source_revalidation_review_dirs(root: Path | str = SOURCE_DOCUMENT_ROOT) -> Path:
    base = ensure_source_impact_dirs(root)
    (base / RESOLUTION_DIR).mkdir(parents=True, exist_ok=True)
    index_path = base / "indexes" / RESOLUTION_INDEX
    if not index_path.exists():
        _atomic_write_json(index_path, {"entries": [], "updated_at_utc": _now()})
    return base


def _load_queue_item(queue_item_id: str, root: Path) -> dict | None:
    path = root / "source_impact_queue" / f"{_safe_id(queue_item_id)}.json"
    payload = _read_json(path)
    return payload if isinstance(payload, dict) else None


def _covers_all_dependencies(workspace: dict, dispositions: dict) -> bool:
    for category, ids_field in DEPENDENCY_CATEGORIES.items():
        expected_ids = set(str(item) for item in workspace.get("affected_record_ids", {}).get(ids_field, []))
        provided_ids = set(str(item) for item in (dispositions.get(category, {}) or {}).keys())
        if expected_ids - provided_ids:
            return False
    return True


def _resolution_path(root: Path, queue_item_id: str) -> Path:
    return root / RESOLUTION_DIR / f"{_safe_id(queue_item_id)}.json"


def _update_resolution_index(root: Path) -> None:
    entries = []
    for path in sorted((root / RESOLUTION_DIR).glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict):
            entries.append(
                {
                    "resolution_id": payload.get("resolution_id"),
                    "queue_item_id": payload.get("queue_item_id"),
                    "document_id": payload.get("document_id"),
                    "resolution_decision": payload.get("resolution_decision"),
                    "closure_allowed": payload.get("closure_allowed"),
                    "updated_at_utc": payload.get("updated_at_utc"),
                }
            )
    _atomic_write_json(root / "indexes" / RESOLUTION_INDEX, {"entries": entries, "updated_at_utc": _now()})


def _resolution_result_text(decision: str) -> str:
    mapping = {
        "keep_open": "Review remains open and no downstream records were changed.",
        "resolved_no_change": "No downstream record changes were recorded during review.",
        "resolved_with_manual_followup": "Manual follow-up is required before relying on all affected records.",
        "replacement_source_required": "A replacement source is required before relying on affected records.",
        "deferred": "Review was deferred for later manual follow-up.",
        "dismissed": "Review was dismissed without downstream record changes.",
    }
    return mapping.get(decision, "No resolution has been recorded.")


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


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


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"_", "-", "."} else "_" for char in str(value)) or "object"


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
