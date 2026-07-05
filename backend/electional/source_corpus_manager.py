"""Corpus-level management for controlled source documents."""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping

from .document_preflight import get_document_preflight_summary, run_document_preflight
from .document_structure import build_document_structure_map, get_document_structure_summary
from .evidence_binder import build_evidence_binder
from .source_document_reader import build_page_diagnostics, get_page_diagnostic_summary
from .source_documents import SOURCE_DOCUMENT_ROOT, extract_pdf_text, list_source_documents, load_source_document
from .source_knowledge import chunk_extracted_text, ensure_source_knowledge_dirs, list_source_proposals, load_chunks
from .source_reliability_manager import (
    detect_duplicate_source_identity,
    get_source_quality_dashboard,
    get_source_relationships,
    list_evidence_binders_using_source,
    recalculate_source_reliability,
    refresh_evidence_binders_for_source,
)

INVENTORY_SCHEMA_VERSION = "source_corpus_inventory_v1"
BATCH_SCHEMA_VERSION = "source_corpus_batch_v1"
CORPUS_DIRS = ("corpus", "corpus_batches", "corpus_reports", "indexes")
ALLOWED_BATCH_ACTIONS = {
    "run_preflight",
    "extract_text",
    "chunk_text",
    "build_page_diagnostics",
    "build_structure_map",
    "recalculate_reliability",
    "refresh_evidence_binders",
    "detect_duplicates",
    "detect_missing_steps",
    "generate_corpus_report",
    "repair_index",
}


def ensure_source_corpus_dirs(root: Path | str = SOURCE_DOCUMENT_ROOT) -> Path:
    base = ensure_source_knowledge_dirs(root)
    for folder in CORPUS_DIRS:
        (base / folder).mkdir(parents=True, exist_ok=True)
    return base


def build_source_corpus_inventory(*, regenerate: bool = False, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_source_corpus_dirs(root)
    path = _inventory_path(base)
    if path.exists() and not regenerate:
        return json.loads(path.read_text(encoding="utf-8"))
    items = [_inventory_item(record.document_id, base) for record in list_source_documents(root=base)]
    summary = _inventory_summary(items)
    payload = {"schema_version": INVENTORY_SCHEMA_VERSION, "created_at_utc": _now(), "updated_at_utc": _now(), "source_count": len(items), "status": "empty" if not items else "built", "items": items, "summary": summary, "warnings": [] if items else ["no_sources_registered"], "blockers": []}
    _atomic_write_json(path, payload)
    _atomic_write_json(base / "indexes" / "source_corpus_index.json", {"source_count": len(items), "updated_at_utc": payload["updated_at_utc"], "entries": [{"document_id": item["document_id"], "missing_steps": item["missing_steps"]} for item in items]})
    return payload


def load_source_corpus_inventory(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    path = _inventory_path(ensure_source_corpus_dirs(root))
    if not path.exists():
        return {"schema_version": INVENTORY_SCHEMA_VERSION, "source_count": 0, "status": "not_built", "items": [], "summary": {}, "warnings": ["corpus_inventory_not_built"], "blockers": []}
    return json.loads(path.read_text(encoding="utf-8"))


def detect_source_missing_steps(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_source_corpus_dirs(root)
    record = load_source_document(document_id, root=base, missing_ok=True)
    if record is None:
        return {"document_id": document_id, "missing_steps": ["registered"], "recommended_next_step": "register_source", "warnings": [], "blockers": ["source_document_missing"]}
    missing = []
    preflight = get_document_preflight_summary(document_id, root=base)
    if not preflight.get("has_preflight"):
        missing.append("preflight")
    if record.extraction_status != "extracted":
        missing.append("extracted_text")
    if not load_chunks(document_id=document_id, root=base):
        missing.append("chunked")
    diag = get_page_diagnostic_summary(document_id, root=base)
    if not diag.get("pages_diagnosed"):
        missing.append("page_diagnostics")
    structure = get_document_structure_summary(document_id, root=base)
    if structure.get("status") != "built":
        missing.append("structure_map")
    reliability = _load_existing_reliability(document_id, base)
    if not reliability:
        missing.append("reliability_record")
    proposals = [proposal for proposal in list_source_proposals(root=base) if proposal.document_id == document_id]
    binders = list_evidence_binders_using_source(document_id, root=base)
    if proposals and not binders.get("binders_found"):
        missing.append("evidence_binder_if_proposals_exist")
    return {"document_id": document_id, "missing_steps": list(dict.fromkeys(missing)), "recommended_next_step": _next_step(missing), "warnings": [], "blockers": []}


def detect_corpus_missing_steps(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_source_corpus_dirs(root)
    items = [detect_source_missing_steps(record.document_id, root=base) for record in list_source_documents(root=base)]
    return {
        "sources_checked": len(items),
        "sources_missing_preflight": _count_missing(items, "preflight"),
        "sources_missing_extraction": _count_missing(items, "extracted_text"),
        "sources_missing_chunks": _count_missing(items, "chunked"),
        "sources_missing_structure": _count_missing(items, "structure_map"),
        "sources_missing_reliability": _count_missing(items, "reliability_record"),
        "sources_missing_evidence_binder": _count_missing(items, "evidence_binder_if_proposals_exist"),
        "items": items,
    }


def get_source_corpus_health(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    inventory = build_source_corpus_inventory(regenerate=True, root=root)
    items = inventory.get("items", [])
    total = len(items)
    if total == 0:
        return {"status": "empty", "source_count": 0, "healthy_sources": 0, "warning_sources": 0, "critical_sources": 0, "coverage": {}, "risks": {}, "recommended_action": "Register source documents before corpus review."}
    healthy = sum(1 for item in items if not item.get("missing_steps") and not item.get("warnings") and not item.get("blockers"))
    critical = sum(1 for item in items if item.get("blockers") or item.get("source_status") in {"invalid_pdf", "read_error"})
    warning = max(0, total - healthy - critical)
    coverage = {
        "preflight": _coverage(items, "preflight_status", "not_preflighted"),
        "extraction": _coverage(items, "extraction_status", "extracted"),
        "chunks": _coverage(items, "chunk_status", "chunked"),
        "structure": _coverage(items, "structure_status", "built"),
        "reliability": 1.0 - _ratio(sum(1 for item in items if item.get("reliability_band") == "unknown"), total),
        "evidence_binders": _ratio(sum(1 for item in items if int(item.get("evidence_binder_count", 0)) > 0), total),
    }
    risks = {
        "duplicates": sum(1 for item in items if item.get("duplicate_status") != "none"),
        "stale_sources": sum(1 for item in items if item.get("staleness_status") == "stale"),
        "superseded_sources": sum(1 for item in items if item.get("supersession_status") != "current"),
        "failed_sources": critical,
        "privacy_warnings": sum(1 for item in items if "privacy" in " ".join(item.get("warnings", [])).lower()),
    }
    status = "critical" if critical else "warning" if warning or any(risks.values()) else "healthy"
    return {"status": status, "source_count": total, "healthy_sources": healthy, "warning_sources": warning, "critical_sources": critical, "coverage": coverage, "risks": risks, "recommended_action": "Run missing-step review and reliability recheck." if status != "healthy" else "Corpus health is acceptable."}


def create_corpus_batch_plan(action: str, document_ids: list[str] | None = None, filters: dict[str, object] | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    if action not in ALLOWED_BATCH_ACTIONS:
        raise ValueError(f"Unsupported corpus batch action: {action}")
    base = ensure_source_corpus_dirs(root)
    docs = _select_documents(document_ids, filters or {}, base)
    batch_id = f"batch_{action}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}"
    payload = {"batch_id": batch_id, "schema_version": BATCH_SCHEMA_VERSION, "created_at_utc": _now(), "action": action, "status": "planned", "document_ids": docs, "filters": filters or {}, "items": [{"document_id": doc, "status": "planned", "warnings": [], "blockers": []} for doc in docs], "warnings": [] if docs else ["no_registered_sources_selected"], "blockers": []}
    _atomic_write_json(_batch_path(base, batch_id), payload)
    _update_batch_index(base)
    return payload


def load_corpus_batch_plan(batch_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    path = _batch_path(ensure_source_corpus_dirs(root), batch_id)
    if not path.exists():
        raise FileNotFoundError(batch_id)
    return json.loads(path.read_text(encoding="utf-8"))


def list_corpus_batch_plans(limit: int = 20, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> list[dict[str, object]]:
    base = ensure_source_corpus_dirs(root)
    rows = []
    for path in sorted((base / "corpus_batches").glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows.append({"batch_id": data.get("batch_id"), "action": data.get("action"), "status": data.get("status"), "document_count": len(data.get("document_ids", [])), "created_at_utc": data.get("created_at_utc")})
    return rows[: max(0, int(limit or 0))]


def execute_corpus_batch_plan(
    batch_id: str,
    dry_run: bool = True,
    limit: int = 25,
    resume: bool = False,
    retry_failures: bool = False,
    force: bool = False,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, object]:
    from .corpus_execution_recovery import execute_corpus_batch_plan as execute_with_recovery

    return execute_with_recovery(
        batch_id,
        dry_run=dry_run,
        limit=limit,
        resume=resume,
        retry_failures=retry_failures,
        force=force,
        root=root,
    )


def list_failed_source_tasks(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_source_corpus_dirs(root)
    items = []
    for record in list_source_documents(root=base):
        if record.extraction_status in {"invalid_pdf", "read_error"}:
            items.append({"document_id": record.document_id, "failed_step": "extraction_failed", "reason": record.extraction_status, "recommended_action": "inspect source or re-run extraction after fix"})
        missing = detect_source_missing_steps(record.document_id, root=base)
        if "preflight" in missing.get("missing_steps", []):
            items.append({"document_id": record.document_id, "failed_step": "preflight_missing", "reason": "not_preflighted", "recommended_action": "run preflight"})
    return {"failed_count": len(items), "items": items}


def create_retry_batch_for_failed_sources(action: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    failed = list_failed_source_tasks(root=root)
    docs = list(dict.fromkeys(str(item["document_id"]) for item in failed["items"]))
    return create_corpus_batch_plan(action or "detect_missing_steps", docs, root=root)


def bulk_recalculate_source_reliability(document_ids: list[str] | None = None, dry_run: bool = True, limit: int = 25, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_source_corpus_dirs(root)
    docs = _select_documents(document_ids, {}, base)[: max(0, int(limit or 0))]
    items = []
    for doc in docs:
        if dry_run:
            items.append({"document_id": doc, "status": "planned", "warnings": []})
        else:
            rel = recalculate_source_reliability(doc, root=base)
            items.append({"document_id": doc, "status": "recalculated", "reliability_band": rel.get("reliability_band"), "warnings": rel.get("warnings", [])})
    return {"dry_run": dry_run, "sources_planned": len(docs), "sources_recalculated": 0 if dry_run else len(items), "items": items, "warnings": []}


def bulk_refresh_evidence_binders(document_ids: list[str] | None = None, proposal_ids: list[str] | None = None, dry_run: bool = True, limit: int = 25, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_source_corpus_dirs(root)
    docs = _select_documents(document_ids, {}, base)[: max(0, int(limit or 0))]
    binders_found = 0
    refreshed = 0
    items = []
    for doc in docs:
        listed = list_evidence_binders_using_source(doc, root=base)
        binders_found += int(listed.get("binders_found", 0))
        if dry_run:
            items.append({"document_id": doc, "status": "planned", "binders_found": listed.get("binders_found")})
        else:
            result = refresh_evidence_binders_for_source(doc, root=base)
            refreshed += int(result.get("binders_refreshed", 0))
            items.append({"document_id": doc, "status": "refreshed", "binders_refreshed": result.get("binders_refreshed"), "warnings": result.get("warnings", [])})
    return {"dry_run": dry_run, "binders_found": binders_found, "binders_planned": binders_found if dry_run else 0, "binders_refreshed": refreshed, "items": items, "warnings": []}


def list_duplicate_source_queue(limit: int = 50, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_source_corpus_dirs(root)
    rows = []
    for record in list_source_documents(root=base):
        dup = detect_duplicate_source_identity(record.document_id, root=base)
        for match in dup.get("matches", []):
            rows.append({"document_id": record.document_id, "matched_document_id": match.get("document_id"), "reason": match.get("reason"), "confidence": match.get("confidence"), "recommended_action": "review duplicate identity; do not auto-merge"})
    return {"duplicate_count": len(rows), "items": rows[: max(0, int(limit or 0))]}


def list_superseded_source_queue(limit: int = 50, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_source_corpus_dirs(root)
    rows = []
    for record in list_source_documents(root=base):
        relationships = get_source_relationships(record.document_id, root=base)
        for rel in relationships.get("relationships", []):
            if rel.get("relationship_type") in {"replaced_by", "older_version_of"}:
                rows.append({"document_id": record.document_id, "replacement_document_id": rel.get("target_document_id"), "relationship_type": rel.get("relationship_type"), "recommended_action": "review citations using superseded source"})
    return {"superseded_count": len(rows), "items": rows[: max(0, int(limit or 0))]}


def format_source_corpus_report_text(public_safe: bool = True, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> str:
    health = get_source_corpus_health(root=root)
    coverage = health.get("coverage", {})
    risks = health.get("risks", {})
    return "\n".join([
        "Source Corpus Report",
        "",
        "Sources:",
        f"- Total: {health.get('source_count')}",
        f"- Healthy: {health.get('healthy_sources')}",
        f"- Warning: {health.get('warning_sources')}",
        f"- Critical: {health.get('critical_sources')}",
        "",
        "Coverage:",
        f"- Preflight: {_pct(coverage.get('preflight'))}",
        f"- Extraction: {_pct(coverage.get('extraction'))}",
        f"- Chunking: {_pct(coverage.get('chunks'))}",
        f"- Structure Maps: {_pct(coverage.get('structure'))}",
        f"- Reliability Records: {_pct(coverage.get('reliability'))}",
        f"- Evidence Binders: {_pct(coverage.get('evidence_binders'))}",
        "",
        "Risks:",
        f"- Duplicate Sources: {risks.get('duplicates', 0)}",
        f"- Superseded Sources: {risks.get('superseded_sources', 0)}",
        f"- Stale Sources: {risks.get('stale_sources', 0)}",
        f"- Failed Sources: {risks.get('failed_sources', 0)}",
        f"- Privacy Warnings: {risks.get('privacy_warnings', 0)}",
        "",
        "Recommended Action:",
        str(health.get("recommended_action")),
    ])


def _inventory_item(document_id: str, root: Path) -> dict[str, object]:
    record = load_source_document(document_id, root=root)
    preflight = get_document_preflight_summary(document_id, root=root)
    chunks = load_chunks(document_id=document_id, root=root)
    structure = get_document_structure_summary(document_id, root=root)
    reliability = _load_existing_reliability(document_id, root) or {"reliability_band": "unknown", "staleness_status": "unknown", "warnings": ["reliability_record_missing"]}
    duplicates = _existing_duplicate_status(document_id, root)
    relationships = get_source_relationships(document_id, root=root)
    binders = list_evidence_binders_using_source(document_id, root=root)
    proposals = [p for p in list_source_proposals(root=root) if p.document_id == document_id]
    missing = detect_source_missing_steps(document_id, root=root)
    title = str(reliability.get("manual_title") or reliability.get("detected_title") or record.original_filename or document_id)
    supersession = "superseded" if any(r.get("relationship_type") in {"replaced_by", "older_version_of"} for r in relationships.get("relationships", [])) else "current"
    warnings = list(dict.fromkeys([*record.warnings, *reliability.get("warnings", []), *missing.get("warnings", [])]))
    return {"document_id": document_id, "title": _safe_preview(title, 160), "source_status": record.extraction_status or "registered", "preflight_status": preflight.get("status", "not_preflighted") if preflight.get("has_preflight") else "not_preflighted", "extraction_status": record.extraction_status, "chunk_status": "chunked" if chunks else "not_chunked", "structure_status": structure.get("status", "not_built"), "reliability_band": reliability.get("reliability_band", "unknown"), "staleness_status": reliability.get("staleness_status", "unknown"), "evidence_binder_count": binders.get("binders_found", 0), "proposal_count": len(proposals), "citation_count": _citation_count(document_id, root), "duplicate_status": duplicates.get("status", "unknown"), "supersession_status": supersession, "missing_steps": missing.get("missing_steps", []), "warnings": warnings, "blockers": missing.get("blockers", []), "recommended_action": _next_step(missing.get("missing_steps", []))}


def _execute_action(action: str, document_id: str, dry_run: bool, root: Path) -> dict[str, object]:
    if dry_run:
        return {"document_id": document_id, "status": "planned", "warnings": [], "blockers": []}
    try:
        if action == "run_preflight":
            run_document_preflight(document_id, root=root)
        elif action == "extract_text":
            extract_pdf_text(document_id, root=root)
        elif action == "chunk_text":
            chunk_extracted_text(document_id, root=root)
        elif action == "build_page_diagnostics":
            build_page_diagnostics(document_id, root=root)
        elif action == "build_structure_map":
            build_document_structure_map(document_id, root=root)
        elif action == "recalculate_reliability":
            recalculate_source_reliability(document_id, root=root)
        elif action == "refresh_evidence_binders":
            refresh_evidence_binders_for_source(document_id, root=root)
        elif action == "detect_duplicates":
            detect_duplicate_source_identity(document_id, root=root)
        elif action == "detect_missing_steps":
            detect_source_missing_steps(document_id, root=root)
        elif action == "generate_corpus_report":
            _save_corpus_report(root)
        else:
            return {"document_id": document_id, "status": "unsupported", "warnings": ["helper_unavailable"], "blockers": []}
        return {"document_id": document_id, "status": "completed", "warnings": [], "blockers": []}
    except Exception as exc:
        return {"document_id": document_id, "status": "failed", "warnings": [str(exc)], "blockers": []}


def _select_documents(document_ids: list[str] | None, filters: Mapping[str, object], root: Path) -> list[str]:
    registered = {record.document_id for record in list_source_documents(root=root)}
    if document_ids is not None:
        return [doc for doc in document_ids if doc in registered]
    docs = sorted(registered)
    if filters.get("missing_step"):
        docs = [doc for doc in docs if filters["missing_step"] in detect_source_missing_steps(doc, root=root).get("missing_steps", [])]
    return docs


def _citation_count(document_id: str, root: Path) -> int:
    count = 0
    for path in sorted((root / "citations").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("document_id") == document_id:
            count += 1
    return count



def _load_existing_reliability(document_id: str, root: Path) -> dict[str, object] | None:
    path = root / "source_reliability" / f"{_safe_id(document_id)}_reliability.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"reliability_band": "unknown", "staleness_status": "unknown", "warnings": ["reliability_record_unreadable"]}


def _existing_duplicate_status(document_id: str, root: Path) -> dict[str, object]:
    path = root / "indexes" / "source_duplicate_identity_index.json"
    if not path.exists():
        return {"status": "none", "matches": [], "warnings": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "unknown", "matches": [], "warnings": ["duplicate_index_unreadable"]}
    if data.get("document_id") == document_id:
        return {"status": data.get("status", "unknown"), "matches": data.get("matches", []), "warnings": data.get("warnings", [])}
    return {"status": "none", "matches": [], "warnings": []}
def _inventory_summary(items: list[dict[str, object]]) -> dict[str, object]:
    return {"sources": len(items), "missing_preflight": sum("preflight" in item.get("missing_steps", []) for item in items), "missing_chunks": sum("chunked" in item.get("missing_steps", []) for item in items), "unknown_reliability": sum(item.get("reliability_band") == "unknown" for item in items)}


def _count_missing(items: list[dict[str, object]], step: str) -> int:
    return sum(1 for item in items if step in item.get("missing_steps", []))


def _coverage(items: list[dict[str, object]], field: str, good_value: str) -> float:
    if not items:
        return 0.0
    if field == "preflight_status":
        return _ratio(sum(1 for item in items if item.get(field) != "not_preflighted"), len(items))
    return _ratio(sum(1 for item in items if item.get(field) == good_value), len(items))


def _ratio(count: int, total: int) -> float:
    return round(count / max(1, total), 2)


def _pct(value: object) -> str:
    try:
        return f"{float(value) * 100:.0f}%"
    except Exception:
        return "0%"


def _next_step(missing: list[str]) -> str:
    order = ["preflight", "extracted_text", "chunked", "page_diagnostics", "structure_map", "reliability_record", "evidence_binder_if_proposals_exist"]
    for step in order:
        if step in missing:
            return "run_" + step
    return "No action needed."


def _save_corpus_report(root: Path) -> dict[str, object]:
    report_id = f"corpus_report_{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}"
    payload = {"report_id": report_id, "created_at_utc": _now(), "text": format_source_corpus_report_text(root=root)}
    _atomic_write_json(root / "corpus_reports" / f"{report_id}.json", payload)
    _atomic_write_json(root / "indexes" / "corpus_health_index.json", get_source_corpus_health(root=root))
    return payload


def _batch_path(root: Path, batch_id: str) -> Path:
    return root / "corpus_batches" / f"{_safe_id(batch_id)}.json"


def _inventory_path(root: Path) -> Path:
    return root / "corpus" / "source_corpus_inventory.json"


def _update_batch_index(root: Path) -> None:
    entries = list_corpus_batch_plans(root=root)
    _atomic_write_json(root / "indexes" / "corpus_batch_index.json", {"entries": entries})


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_path, path)


def _safe_preview(value: str, limit: int) -> str:
    text = re.sub(r"[A-Za-z]:[/\\][^\s]+", "[local-path]", str(value))
    text = re.sub(r"[\w.+-]+@[\w.-]+", "[email]", text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
