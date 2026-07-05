"""Read-only source change impact analysis and manual revalidation queue."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from .evidence_binder import load_evidence_binder
from .proposal_review import load_proposal_review
from .source_documents import SOURCE_DOCUMENT_ROOT, load_source_document
from .source_knowledge import ensure_source_knowledge_dirs, list_source_proposals, load_chunks
from .source_reliability_manager import get_source_relationships

ALLOWED_CHANGE_TYPES = {
    "reliability_changed",
    "reliability_downgraded",
    "stale",
    "superseded",
    "replaced",
    "quarantined",
    "corrupt",
    "missing",
    "manual_review",
}
ALLOWED_QUEUE_STATUSES = {"pending_review", "in_review", "reviewed", "deferred", "dismissed"}
SEVERITY_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4, "unknown": 5}
QUEUE_DIR = "source_impact_queue"
QUEUE_INDEX = "source_impact_queue_index.json"


def analyze_source_change_impact(document_id: str, change_type: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = ensure_source_impact_dirs(root)
    if change_type is not None and change_type not in ALLOWED_CHANGE_TYPES:
        raise ValueError(f"Unsupported change type: {change_type}")
    source_state = _read_source_state(document_id, root=base)
    dependencies = find_source_dependencies(document_id, root=base)
    derived_change = change_type or _derive_change_type(source_state)
    severity = calculate_source_impact_severity(
        {
            **source_state,
            "change_type": derived_change,
            "dependency_unknown": bool(dependencies.get("unknown_dependencies")),
            "has_review_ready_proposals": dependencies.get("has_review_ready_proposals", False),
        },
        dependencies["affected_counts"],
    )
    return {
        "document_id": document_id,
        "change_type": derived_change,
        "source_state": source_state,
        "affected_counts": dependencies["affected_counts"],
        "affected_records": dependencies["affected_records"],
        "impact_severity": severity["impact_severity"],
        "warnings": list(dict.fromkeys([*source_state.get("warnings", []), *dependencies.get("warnings", []), *severity.get("warnings", [])])),
        "recommended_action": severity["recommended_action"],
    }


def find_source_dependencies(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict:
    base = ensure_source_impact_dirs(root)
    warnings: list[str] = []
    unknown_dependencies: list[str] = []
    chunk_ids = {chunk.chunk_id for chunk in load_chunks(document_id=document_id, root=base)}
    citation_entries = _read_index_entries(base / "indexes" / "citation_index.json", "citations", warnings, unknown_dependencies, fallback_dir=base / "citations")
    citation_ids = sorted(
        {
            str(entry.get("citation_id"))
            for entry in citation_entries
            if str(entry.get("document_id") or "") == document_id or str(entry.get("chunk_id") or "") in chunk_ids
        }
    )
    proposals = list_source_proposals(document_id=document_id, root=base)
    proposal_ids = sorted({proposal.proposal_id for proposal in proposals if proposal.document_id == document_id or proposal.chunk_id in chunk_ids})
    review_ids: list[str] = []
    review_ready = False
    for proposal_id in proposal_ids:
        review = load_proposal_review(proposal_id, root=base, missing_ok=True)
        if review is None:
            continue
        review_ids.append(str(getattr(review, "review_id", f"review_{proposal_id}")))
        review_ready = review_ready or str(getattr(review, "review_status", "")) == "approved_for_later_promotion"
    binder_ids: list[str] = []
    for proposal_id in proposal_ids:
        binder = load_evidence_binder(proposal_id, root=base)
        if binder.get("binder_status") == "not_built":
            continue
        linked = binder.get("linked_citations", [])
        if any(str(item.get("document_id") or "") == document_id for item in linked if isinstance(item, dict)):
            binder_ids.append(str(binder.get("binder_id") or f"binder_{proposal_id}"))
    return {
        "document_id": document_id,
        "affected_counts": {
            "citations": len(citation_ids) if "citations" not in unknown_dependencies else "unknown",
            "proposals": len(proposal_ids),
            "proposal_reviews": len(review_ids),
            "evidence_binders": len(sorted(set(binder_ids))),
        },
        "affected_records": {
            "citation_ids": citation_ids,
            "proposal_ids": proposal_ids,
            "proposal_review_ids": sorted(set(review_ids)),
            "evidence_binder_ids": sorted(set(binder_ids)),
        },
        "has_review_ready_proposals": review_ready,
        "unknown_dependencies": unknown_dependencies,
        "warnings": warnings,
    }


def calculate_source_impact_severity(source_state: dict, affected_counts: dict) -> dict:
    warnings: list[str] = []
    if source_state.get("dependency_unknown"):
        warnings.append("dependency_state_unknown")
        return {"impact_severity": "unknown", "warnings": warnings, "recommended_action": "Review controlled records manually before relying on this source."}
    citations = 0 if affected_counts.get("citations") == "unknown" else int(affected_counts.get("citations", 0) or 0)
    proposals = int(affected_counts.get("proposals", 0) or 0)
    reviews = int(affected_counts.get("proposal_reviews", 0) or 0)
    binders = int(affected_counts.get("evidence_binders", 0) or 0)
    total = citations + proposals + reviews + binders
    change_type = str(source_state.get("change_type") or "")
    if total == 0:
        severity = "none"
    elif change_type in {"corrupt", "quarantined", "missing"}:
        severity = "critical"
    elif binders > 0 or source_state.get("has_review_ready_proposals"):
        severity = "high"
    elif proposals > 0 or citations >= 3 or reviews > 0:
        severity = "medium"
    elif 0 < citations <= 2:
        severity = "low"
    else:
        severity = "unknown"
    recommended = {
        "critical": "Review affected citations, proposals, and evidence binders before relying on them.",
        "high": "Review affected citations and evidence binders before relying on them.",
        "medium": "Review affected proposals and citations.",
        "low": "Review the affected citations.",
        "none": "No downstream revalidation is currently required.",
        "unknown": "Review controlled records manually before relying on this source.",
    }[severity]
    return {"impact_severity": severity, "warnings": warnings, "recommended_action": recommended}


def create_source_revalidation_item(
    document_id: str,
    change_type: str | None = None,
    note: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = ensure_source_impact_dirs(root)
    impact = analyze_source_change_impact(document_id, change_type=change_type, root=base)
    dedupe_key = _build_queue_dedupe_key(impact)
    for item in list_source_revalidation_queue(status="pending_review", limit=500, root=base).get("items", []):
        if item.get("dedupe_key") == dedupe_key:
            return item
    payload = {
        "queue_item_id": f"impact_{_timestamp_token()}",
        "document_id": document_id,
        "change_type": impact.get("change_type"),
        "impact_severity": impact.get("impact_severity"),
        "status": "pending_review",
        "affected_counts": impact.get("affected_counts", {}),
        "created_at_utc": _now(),
        "review_note": note,
        "warnings": impact.get("warnings", []),
        "dedupe_key": dedupe_key,
    }
    _atomic_write_json(_queue_item_path(base, str(payload["queue_item_id"])), payload)
    _update_queue_index(base)
    return payload


def list_source_revalidation_queue(
    status: str | None = None,
    minimum_severity: str | None = None,
    limit: int = 50,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    base = ensure_source_impact_dirs(root)
    items = []
    minimum_rank = SEVERITY_ORDER.get(str(minimum_severity), -1) if minimum_severity else -1
    for path in sorted((base / QUEUE_DIR).glob("impact_*.json"), reverse=True):
        item = _read_json(path)
        if not isinstance(item, dict):
            continue
        if status is not None and item.get("status") != status:
            continue
        if minimum_rank >= 0 and SEVERITY_ORDER.get(str(item.get("impact_severity")), -1) < minimum_rank:
            continue
        items.append(item)
    return {"count": len(items[: max(0, int(limit or 0))]), "items": items[: max(0, int(limit or 0))]}


def update_source_revalidation_status(
    queue_item_id: str,
    status: str,
    note: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict:
    if status not in ALLOWED_QUEUE_STATUSES:
        raise ValueError(f"Unsupported queue status: {status}")
    base = ensure_source_impact_dirs(root)
    path = _queue_item_path(base, queue_item_id)
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise FileNotFoundError(queue_item_id)
    payload["status"] = status
    payload["review_note"] = note
    payload["updated_at_utc"] = _now()
    _atomic_write_json(path, payload)
    _update_queue_index(base)
    return payload


def format_source_impact_report_text(document_id: str, public_safe: bool = True, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> str:
    impact = analyze_source_change_impact(document_id, root=root)
    text = "\n".join(
        [
            "Source Change Impact Report",
            "",
            f"Document: {document_id}",
            f"Change Type: {impact.get('change_type') or 'unknown'}",
            f"Impact Severity: {impact.get('impact_severity')}",
            "",
            "Affected Records:",
            f"- Citations: {impact.get('affected_counts', {}).get('citations')}",
            f"- Proposals: {impact.get('affected_counts', {}).get('proposals')}",
            f"- Proposal Reviews: {impact.get('affected_counts', {}).get('proposal_reviews')}",
            f"- Evidence Binders: {impact.get('affected_counts', {}).get('evidence_binders')}",
            "",
            "Source State:",
            f"- Reliability: {impact.get('source_state', {}).get('reliability_band')}",
            f"- Staleness: {impact.get('source_state', {}).get('staleness_status')}",
            f"- Supersession: {impact.get('source_state', {}).get('supersession_status')}",
            "",
            "Recommended Action:",
            str(impact.get("recommended_action")),
        ]
    )
    return _sanitize(text) if public_safe else text


def ensure_source_impact_dirs(root: Path | str = SOURCE_DOCUMENT_ROOT) -> Path:
    base = ensure_source_knowledge_dirs(root)
    (base / QUEUE_DIR).mkdir(parents=True, exist_ok=True)
    index_path = base / "indexes" / QUEUE_INDEX
    if not index_path.exists():
        _atomic_write_json(index_path, {"entries": [], "updated_at_utc": _now()})
    return base


def _read_source_state(document_id: str, *, root: Path) -> dict:
    warnings: list[str] = []
    try:
        document = load_source_document(document_id, root=root, missing_ok=True)
    except Exception:
        document = None
        warnings.append("source_record_unreadable")
    reliability_path = root / "source_reliability" / f"{_safe_id(document_id)}_reliability.json"
    reliability = _read_json(reliability_path) if reliability_path.exists() else {}
    relationships = get_source_relationships(document_id, root=root)
    quarantine_entries = [item for item in _read_index_entries(root / "indexes" / "corpus_quarantine_index.json", "quarantine", warnings, [], fallback_dir=root / "corpus_quarantine") if item.get("record_id") == document_id]
    supersession = "superseded" if any(rel.get("relationship_type") in {"replaced_by", "older_version_of"} for rel in relationships.get("relationships", [])) else "current"
    return {
        "reliability_band": reliability.get("reliability_band", "unknown"),
        "staleness_status": reliability.get("staleness_status", "unknown"),
        "supersession_status": supersession,
        "is_missing": document is None,
        "is_quarantined": bool(quarantine_entries),
        "warnings": warnings,
    }


def _derive_change_type(source_state: dict) -> str | None:
    if source_state.get("is_missing"):
        return "missing"
    if source_state.get("is_quarantined"):
        return "quarantined"
    if source_state.get("supersession_status") == "superseded":
        return "superseded"
    if source_state.get("staleness_status") == "stale":
        return "stale"
    if source_state.get("reliability_band") in {"weak", "untrusted"}:
        return "reliability_downgraded"
    return None


def _build_queue_dedupe_key(impact: dict) -> str:
    payload = {
        "document_id": impact.get("document_id"),
        "change_type": impact.get("change_type"),
        "reliability_band": impact.get("source_state", {}).get("reliability_band"),
        "supersession_status": impact.get("source_state", {}).get("supersession_status"),
        "citation_ids": impact.get("affected_records", {}).get("citation_ids", []),
        "proposal_ids": impact.get("affected_records", {}).get("proposal_ids", []),
        "proposal_review_ids": impact.get("affected_records", {}).get("proposal_review_ids", []),
        "evidence_binder_ids": impact.get("affected_records", {}).get("evidence_binder_ids", []),
    }
    return "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _update_queue_index(root: Path) -> None:
    entries = []
    for path in sorted((root / QUEUE_DIR).glob("impact_*.json")):
        item = _read_json(path)
        if isinstance(item, dict):
            entries.append(
                {
                    "queue_item_id": item.get("queue_item_id"),
                    "document_id": item.get("document_id"),
                    "change_type": item.get("change_type"),
                    "impact_severity": item.get("impact_severity"),
                    "status": item.get("status"),
                    "created_at_utc": item.get("created_at_utc"),
                }
            )
    _atomic_write_json(root / "indexes" / QUEUE_INDEX, {"entries": entries, "updated_at_utc": _now()})


def _read_index_entries(path: Path, label: str, warnings: list[str], unknown_dependencies: list[str], fallback_dir: Path | None = None) -> list[dict]:
    if not path.exists():
        warnings.append(f"{label}_index_missing")
        if fallback_dir is not None and fallback_dir.exists() and not any(fallback_dir.glob("*.json")):
            return []
        unknown_dependencies.append(label)
        return []
    payload = _read_json(path)
    if not isinstance(payload, dict) or not isinstance(payload.get("entries"), list):
        warnings.append(f"{label}_index_unreadable")
        unknown_dependencies.append(label)
        return []
    return [item for item in payload.get("entries", []) if isinstance(item, dict)]


def _queue_item_path(root: Path, queue_item_id: str) -> Path:
    return root / QUEUE_DIR / f"{_safe_id(queue_item_id)}.json"


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


def _timestamp_token() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
