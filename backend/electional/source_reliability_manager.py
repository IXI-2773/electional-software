"""Source reliability metadata management and governance."""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Mapping

from .document_preflight import get_document_preflight_summary
from .document_structure import analyze_chunk_quality, get_document_structure_summary
from .evidence_binder import build_evidence_binder, get_or_create_source_reliability, update_source_reliability_metadata
from .source_documents import SOURCE_DOCUMENT_ROOT, list_source_documents, load_source_document
from .source_knowledge import ensure_source_knowledge_dirs

HISTORY_SCHEMA_VERSION = "source_reliability_history_v1"
RELATIONSHIP_SCHEMA_VERSION = "source_relationship_v1"
MANAGER_DIRS = ("source_reliability", "source_reliability_history", "source_relationships", "indexes")
SOURCE_TYPES = {"unknown", "official_policy", "internal_note", "manual_reference", "book", "paper", "web_export", "legal_source", "technical_doc", "user_supplied", "archived_source", "superseded_source"}
AUTHORITY_LEVELS = {"unknown", "low", "medium", "high", "primary", "secondary", "tertiary"}
RELATIONSHIP_TYPES = {"replaced_by", "supersedes", "newer_version_of", "older_version_of", "duplicate_of", "related_source"}
EDITABLE_FIELDS = {"source_type", "authority_level", "publication_date", "modified_date", "detected_title", "manual_title", "author", "publisher", "version_label", "jurisdiction", "source_url_label", "source_notes", "reliability_notes"}


def ensure_source_reliability_manager_dirs(root: Path | str = SOURCE_DOCUMENT_ROOT) -> Path:
    base = ensure_source_knowledge_dirs(root)
    for folder in MANAGER_DIRS:
        (base / folder).mkdir(parents=True, exist_ok=True)
    return base


def update_source_metadata_for_reliability(document_id: str, metadata: Mapping[str, object], note: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_source_reliability_manager_dirs(root)
    _validate_metadata(metadata)
    previous = get_or_create_source_reliability(document_id, root=base)
    clean = {key: metadata[key] for key in EDITABLE_FIELDS if key in metadata}
    if note:
        clean["note"] = note
    updated = update_source_reliability_metadata(document_id, clean, root=base)
    for key in ("manual_title", "publisher", "jurisdiction", "source_url_label", "source_notes", "reliability_notes"):
        if key in clean:
            updated[key] = clean[key]
    _atomic_write_json(_reliability_path(base, document_id), updated)
    recalculated = recalculate_source_reliability(document_id, root=base)
    changed = [key for key in EDITABLE_FIELDS if previous.get(key) != recalculated.get(key) and key in clean]
    _append_history(document_id, "metadata_updated", changed or list(clean.keys()), previous, recalculated, note, base)
    return {"document_id": document_id, "updated": True, "reliability_score": recalculated.get("reliability_score"), "reliability_band": recalculated.get("reliability_band"), "staleness_status": recalculated.get("staleness_status"), "changed_fields": changed or list(clean.keys()), "warnings": recalculated.get("warnings", [])}


def recalculate_source_reliability(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_source_reliability_manager_dirs(root)
    record = load_source_document(document_id, root=base, missing_ok=True)
    current = get_or_create_source_reliability(document_id, root=base)
    strengths: list[str] = []
    weaknesses: list[str] = []
    blockers: list[str] = []
    score = 45
    source_type = str(current.get("source_type") or "unknown")
    authority = str(current.get("authority_level") or "unknown")
    if record is None:
        blockers.append("missing_source_document")
        score = 0
    if authority in {"primary", "high"}:
        score += 25
        strengths.append(f"authority_{authority}")
    elif authority in {"secondary", "medium"}:
        score += 12
        strengths.append(f"authority_{authority}")
    elif authority == "low":
        score -= 15
        weaknesses.append("authority_low")
    else:
        weaknesses.append("authority_unknown")
    if source_type in {"official_policy", "legal_source", "technical_doc", "paper", "book"}:
        score += 12
        strengths.append(f"source_type_{source_type}")
    elif source_type in {"superseded_source", "archived_source"}:
        score -= 15
        weaknesses.append("source_marked_superseded_or_archived")
    else:
        weaknesses.append("source_type_unknown")
    staleness = calculate_source_staleness(document_id, root=base)
    if staleness["staleness_status"] == "current":
        score += 10
        strengths.append("source_current")
    elif staleness["staleness_status"] == "stale":
        score -= 15
        weaknesses.append("source_stale")
    else:
        weaknesses.append("publication_or_modified_date_missing")
    if current.get("version_label"):
        strengths.append("version_label_present")
        score += 5
    else:
        weaknesses.append("version_label_missing")
    preflight = get_document_preflight_summary(document_id, root=base)
    if preflight.get("verdict") == "PASS":
        score += 8
        strengths.append("preflight_passed")
    elif preflight.get("verdict") in {"WARNING", "BLOCK"}:
        weaknesses.append("preflight_warning_or_block")
    structure = get_document_structure_summary(document_id, root=base)
    if structure.get("status") == "built":
        strengths.append("structure_map_available")
    else:
        weaknesses.append("structure_map_missing")
    chunk_quality = analyze_chunk_quality(document_id, root=base)
    if chunk_quality.get("quality_status") in {"warning", "critical"}:
        weaknesses.append("chunk_quality_warning")
    relationships = get_source_relationships(document_id, root=base)
    if any(item.get("relationship_type") == "replaced_by" for item in relationships.get("relationships", [])):
        weaknesses.append("source_has_replacement")
        if source_type == "superseded_source":
            blockers.append("source_marked_superseded_without_replacement" if not relationships.get("relationships") else "source_superseded")
    duplicates = detect_duplicate_source_identity(document_id, root=base)
    if duplicates.get("status") != "none":
        weaknesses.append("duplicate_identity_possible")
    if source_type == "unknown" and authority == "unknown" and not blockers:
        band = "unknown"
    else:
        score = max(0, min(100, score))
        band = "strong" if score >= 85 else "usable" if score >= 65 else "weak" if score >= 35 else "untrusted"
    if blockers:
        band = "untrusted"
        score = min(score, 24)
    updated = dict(current)
    updated.update({"manual_title": current.get("manual_title"), "publisher": current.get("publisher"), "jurisdiction": current.get("jurisdiction"), "source_url_label": current.get("source_url_label"), "source_notes": current.get("source_notes"), "reliability_notes": current.get("reliability_notes"), "reliability_score": score, "reliability_band": band, "staleness_status": staleness["staleness_status"], "strengths": list(dict.fromkeys(strengths)), "weaknesses": list(dict.fromkeys(weaknesses)), "blockers": list(dict.fromkeys(blockers)), "warnings": list(dict.fromkeys(weaknesses))})
    _atomic_write_json(_reliability_path(base, document_id), updated)
    _update_reliability_index(base)
    _append_history(document_id, "reliability_recalculated", ["reliability_score", "reliability_band", "staleness_status"], current, updated, None, base)
    return updated


def calculate_source_staleness(document_id: str, as_of_date: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_source_reliability_manager_dirs(root)
    data = get_or_create_source_reliability(document_id, root=base)
    date_text = data.get("modified_date") or data.get("publication_date")
    if not date_text:
        return {"document_id": document_id, "staleness_status": "unknown", "age_days": None, "date_used": None, "warnings": ["source_date_missing"]}
    source_type = str(data.get("source_type") or "unknown")
    try:
        used = date.fromisoformat(str(date_text)[:10])
        as_of = date.fromisoformat(as_of_date[:10]) if as_of_date else datetime.now(UTC).date()
    except Exception:
        return {"document_id": document_id, "staleness_status": "unknown", "age_days": None, "date_used": str(date_text), "warnings": ["source_date_invalid"]}
    age = (as_of - used).days
    status = "current" if age <= 365 else "aging" if age <= 1095 else "stale"
    warnings = []
    if status == "stale" and source_type in {"book", "legal_source", "manual_reference"}:
        warnings.append("staleness_warning_only_for_source_type")
    return {"document_id": document_id, "staleness_status": status, "age_days": age, "date_used": used.isoformat(), "warnings": warnings}


def link_source_replacement(old_document_id: str, new_document_id: str, relationship_type: str = "replaced_by", note: str | None = None, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    if relationship_type not in RELATIONSHIP_TYPES:
        raise ValueError(f"Unsupported relationship type: {relationship_type}")
    base = ensure_source_reliability_manager_dirs(root)
    if load_source_document(old_document_id, root=base, missing_ok=True) is None or load_source_document(new_document_id, root=base, missing_ok=True) is None:
        raise FileNotFoundError("Both source documents must exist before linking.")
    data = get_source_relationships(old_document_id, root=base)
    relationship = {"target_document_id": new_document_id, "relationship_type": relationship_type, "created_at_utc": _now(), "note": _safe_preview(note or "", 220), "warnings": []}
    existing = data.get("relationships", [])
    if not any(item.get("target_document_id") == new_document_id and item.get("relationship_type") == relationship_type for item in existing):
        existing.append(relationship)
    data["relationships"] = existing
    data["updated_at_utc"] = _now()
    _atomic_write_json(_relationship_path(base, old_document_id), data)
    _update_relationship_index(base)
    _append_history(old_document_id, "supersession_added", ["relationships"], {}, data, note, base)
    return data


def get_source_relationships(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_source_reliability_manager_dirs(root)
    path = _relationship_path(base, document_id)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"document_id": document_id, "schema_version": RELATIONSHIP_SCHEMA_VERSION, "created_at_utc": _now(), "updated_at_utc": _now(), "relationships": [], "warnings": []}


def detect_duplicate_source_identity(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_source_reliability_manager_dirs(root)
    record = load_source_document(document_id, root=base, missing_ok=True)
    if record is None:
        return {"document_id": document_id, "status": "unknown", "matches": [], "warnings": ["source_document_missing"]}
    current_rel = get_or_create_source_reliability(document_id, root=base)
    current_title = _normalize_identity_title(str(current_rel.get("manual_title") or current_rel.get("detected_title") or record.original_filename))
    matches = []
    for other in list_source_documents(root=base):
        if other.document_id == document_id:
            continue
        other_rel = get_or_create_source_reliability(other.document_id, root=base)
        other_title = _normalize_identity_title(str(other_rel.get("manual_title") or other_rel.get("detected_title") or other.original_filename))
        if other.sha256 == record.sha256:
            matches.append({"document_id": other.document_id, "reason": "same_sha256_hash", "confidence": "high"})
        elif current_title and current_title == other_title:
            matches.append({"document_id": other.document_id, "reason": "same_normalized_title", "confidence": "medium"})
        elif current_title and current_title == other_title and current_rel.get("publication_date") == other_rel.get("publication_date"):
            matches.append({"document_id": other.document_id, "reason": "same_title_publication_date", "confidence": "medium"})
    status = "duplicate" if any(item["reason"] == "same_sha256_hash" for item in matches) else "possible_duplicate" if matches else "none"
    payload = {"document_id": document_id, "status": status, "matches": matches, "warnings": []}
    _atomic_write_json(base / "indexes" / "source_duplicate_identity_index.json", payload)
    if matches:
        _append_history(document_id, "duplicate_identity_detected", ["duplicate_identity"], {}, payload, None, base)
    return payload


def get_source_quality_dashboard(reliability_band: str | None = None, staleness_status: str | None = None, source_type: str | None = None, authority_level: str | None = None, limit: int = 50, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_source_reliability_manager_dirs(root)
    items = []
    for record in list_source_documents(root=base):
        rel = recalculate_source_reliability(record.document_id, root=base)
        dup = detect_duplicate_source_identity(record.document_id, root=base)
        relationships = get_source_relationships(record.document_id, root=base)
        item = {"document_id": record.document_id, "title": _safe_preview(str(rel.get("manual_title") or rel.get("detected_title") or record.original_filename), 160), "source_type": rel.get("source_type"), "authority_level": rel.get("authority_level"), "reliability_band": rel.get("reliability_band"), "staleness_status": rel.get("staleness_status"), "warnings": list(rel.get("warnings", [])), "possible_duplicates": len(dup.get("matches", [])), "superseded": any(r.get("relationship_type") == "replaced_by" for r in relationships.get("relationships", [])), "recommended_action": _source_recommended_action(rel, dup, relationships)}
        if reliability_band and item["reliability_band"] != reliability_band:
            continue
        if staleness_status and item["staleness_status"] != staleness_status:
            continue
        if source_type and item["source_type"] != source_type:
            continue
        if authority_level and item["authority_level"] != authority_level:
            continue
        items.append(item)
    items.sort(key=lambda item: (_risk_order(str(item.get("reliability_band"))), str(item.get("staleness_status")), str(item.get("document_id"))))
    all_items = items
    return {"total_sources": len(list_source_documents(root=base)), "strong_sources": sum(1 for item in all_items if item["reliability_band"] == "strong"), "usable_sources": sum(1 for item in all_items if item["reliability_band"] == "usable"), "weak_sources": sum(1 for item in all_items if item["reliability_band"] in {"weak", "untrusted"}), "unknown_sources": sum(1 for item in all_items if item["reliability_band"] == "unknown"), "stale_sources": sum(1 for item in all_items if item["staleness_status"] == "stale"), "sources_missing_dates": sum(1 for item in all_items if item["staleness_status"] == "unknown"), "sources_missing_authority": sum(1 for item in all_items if item["authority_level"] == "unknown"), "possible_duplicates": sum(int(item["possible_duplicates"] > 0) for item in all_items), "superseded_sources": sum(int(bool(item["superseded"])) for item in all_items), "items": all_items[: max(0, int(limit or 0))]}


def list_evidence_binders_using_source(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_source_reliability_manager_dirs(root)
    binders = []
    for path in sorted((base / "evidence_binders").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if any(item.get("document_id") == document_id for item in data.get("linked_citations", []) if isinstance(item, Mapping)):
            binders.append({"proposal_id": data.get("proposal_id"), "path": str(path.name), "binder_status": "available"})
    return {"document_id": document_id, "binders_found": len(binders), "binders": binders, "warnings": []}


def refresh_evidence_binders_for_source(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_source_reliability_manager_dirs(root)
    found = list_evidence_binders_using_source(document_id, root=base)
    refreshed = 0
    warnings = []
    for item in found["binders"]:
        proposal_id = str(item.get("proposal_id") or "")
        if not proposal_id:
            continue
        try:
            build_evidence_binder(proposal_id, regenerate=True, root=base)
            refreshed += 1
        except Exception as exc:
            warnings.append(f"binder_refresh_failed:{proposal_id}:{exc}")
    return {"document_id": document_id, "binders_found": found["binders_found"], "binders_refreshed": refreshed, "warnings": warnings}


def format_source_reliability_report_text(document_id: str, public_safe: bool = True, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> str:
    rel = recalculate_source_reliability(document_id, root=root)
    relationships = get_source_relationships(document_id, root=root)
    duplicate = detect_duplicate_source_identity(document_id, root=root)
    title = _safe_preview(str(rel.get("manual_title") or rel.get("detected_title") or document_id), 180)
    return "\n".join([
        "Source Reliability Report",
        "",
        f"Document: {document_id}",
        f"Title: {title}",
        f"Source Type: {rel.get('source_type')}",
        f"Authority: {rel.get('authority_level')}",
        f"Reliability: {rel.get('reliability_band')}",
        f"Staleness: {rel.get('staleness_status')}",
        f"Version: {rel.get('version_label') or 'Unknown'}",
        "",
        "Strengths:",
        *(f"- {item}" for item in rel.get("strengths", []) or ["None"]),
        "",
        "Warnings:",
        *(f"- {item}" for item in rel.get("warnings", []) or ["None"]),
        "",
        "Relationships:",
        *(f"- {item.get('relationship_type')}: {item.get('target_document_id')}" for item in relationships.get("relationships", []) or [{"relationship_type": "None", "target_document_id": ""}]),
        "",
        "Duplicate Identity:",
        f"- Status: {duplicate.get('status')}",
        "",
        "Recommended Action:",
        _source_recommended_action(rel, duplicate, relationships),
    ])


def load_source_reliability_history(document_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, object]:
    base = ensure_source_reliability_manager_dirs(root)
    path = _history_path(base, document_id)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"document_id": document_id, "schema_version": HISTORY_SCHEMA_VERSION, "created_at_utc": _now(), "updated_at_utc": _now(), "events": [], "warnings": []}


def _validate_metadata(metadata: Mapping[str, object]) -> None:
    if "source_type" in metadata and metadata["source_type"] not in SOURCE_TYPES:
        raise ValueError("Unsupported source_type")
    if "authority_level" in metadata and metadata["authority_level"] not in AUTHORITY_LEVELS:
        raise ValueError("Unsupported authority_level")
    for key in ("publication_date", "modified_date"):
        value = metadata.get(key)
        if value not in (None, ""):
            date.fromisoformat(str(value)[:10])


def _append_history(document_id: str, event_type: str, changed_fields: list[str], previous: Mapping[str, object], new: Mapping[str, object], note: str | None, root: Path) -> None:
    history = load_source_reliability_history(document_id, root=root)
    events = list(history.get("events", []))
    event = {"event_id": f"rel_event_{len(events) + 1:04d}", "created_at_utc": _now(), "event_type": event_type, "changed_fields": changed_fields, "previous_summary": _history_summary(previous), "new_summary": _history_summary(new), "note": _safe_preview(note or "", 220)}
    events.append(event)
    history.update({"updated_at_utc": _now(), "events": events})
    _atomic_write_json(_history_path(root, document_id), history)
    _update_history_index(root)


def _history_summary(data: Mapping[str, object]) -> dict[str, object]:
    return {key: data.get(key) for key in ("source_type", "authority_level", "publication_date", "modified_date", "version_label", "reliability_score", "reliability_band", "staleness_status")}


def _source_recommended_action(rel: Mapping[str, object], duplicate: Mapping[str, object], relationships: Mapping[str, object]) -> str:
    if duplicate.get("status") != "none":
        return "Review possible duplicate source identity."
    if rel.get("authority_level") == "unknown":
        return "Add authority metadata."
    if rel.get("staleness_status") == "unknown":
        return "Add publication or modified date if known."
    if not rel.get("version_label"):
        return "Add version label if available."
    if any(item.get("relationship_type") == "replaced_by" for item in relationships.get("relationships", [])):
        return "Review binders that cite this superseded source."
    return "Source reliability metadata is usable."


def _risk_order(band: str) -> int:
    return {"untrusted": 0, "unknown": 1, "weak": 2, "usable": 3, "strong": 4}.get(band, 1)


def _normalize_identity_title(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", value.lower())).strip()


def _safe_preview(value: str, limit: int) -> str:
    text = re.sub(r"[A-Za-z]:[/\\][^\s]+", "[local-path]", str(value))
    text = re.sub(r"[\w.+-]+@[\w.-]+", "[email]", text)
    text = re.sub(r"\b(?:token|api[_-]?key|secret)\s*[:=]\s*\S+", "[secret]", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _reliability_path(root: Path, document_id: str) -> Path:
    return root / "source_reliability" / f"{_safe_id(document_id)}_reliability.json"


def _history_path(root: Path, document_id: str) -> Path:
    return root / "source_reliability_history" / f"{_safe_id(document_id)}_history.json"


def _relationship_path(root: Path, document_id: str) -> Path:
    return root / "source_relationships" / f"{_safe_id(document_id)}_relationships.json"


def _update_reliability_index(root: Path) -> None:
    entries = []
    for path in sorted((root / "source_reliability").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        entries.append({"document_id": data.get("document_id"), "path": str(path), "reliability_band": data.get("reliability_band"), "staleness_status": data.get("staleness_status")})
    _atomic_write_json(root / "indexes" / "source_reliability_index.json", {"entries": entries})


def _update_history_index(root: Path) -> None:
    entries = []
    for path in sorted((root / "source_reliability_history").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        entries.append({"document_id": data.get("document_id"), "path": str(path), "events": len(data.get("events", []))})
    _atomic_write_json(root / "indexes" / "source_reliability_history_index.json", {"entries": entries})


def _update_relationship_index(root: Path) -> None:
    entries = []
    for path in sorted((root / "source_relationships").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        entries.append({"document_id": data.get("document_id"), "path": str(path), "relationships": len(data.get("relationships", []))})
    _atomic_write_json(root / "indexes" / "source_relationship_index.json", {"entries": entries})


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_path, path)


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
