from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from .pdf_text_layer import _pdf_bbox_to_image_bbox, extract_pdf_page_text_layer
from .pdf_viewport import _blocked, _ensure_dirs, _hash_payload, _latest_current_certification, load_pdf_viewport_session, render_pdf_viewport_page
from .source_documents import SOURCE_DOCUMENT_ROOT, load_source_document
from .source_knowledge import load_chunk


WORKSPACE_SCHEMA_VERSION = "pdf_reader_workspace_v1"
WORKSPACE_DIR = "pdf_reader_workspaces"
WORKSPACE_INDEX = "pdf_reader_workspace_index.json"


def create_pdf_reader_workspace(
    document_id: str,
    viewport_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_workspace_dirs(root)
    record = load_source_document(document_id, root=base, missing_ok=True)
    if record is None:
        return _blocked("document_not_found", document_id=document_id)
    certification = _latest_current_certification(document_id, base)
    if certification is None or certification.get("certification_status") not in {"certified", "certified_with_warnings"}:
        return _blocked("backend_certification_required", document_id=document_id, recommended_action="Run backend certification before opening a reader workspace.")
    active_viewport_id = None
    if viewport_id:
        loaded = load_pdf_viewport_session(viewport_id, root=base)
        if loaded.get("status") != "loaded":
            return {"status": loaded.get("status"), "workspace": None, "blockers": loaded.get("blockers", ["viewport_unavailable"])}
        viewport = loaded["viewport"]
        if viewport.get("document_id") != document_id:
            return _blocked("cross_document_viewport", document_id=document_id, viewport_id=viewport_id)
        active_viewport_id = viewport_id
    workspace_id = _workspace_id(document_id, certification.get("source_revision"))
    path = _workspace_path(base, workspace_id)
    existing = _read_json(path)
    if isinstance(existing, dict) and existing.get("schema_version") == WORKSPACE_SCHEMA_VERSION:
        return {"status": "current", "workspace": existing, "warnings": list(existing.get("warnings", []))}
    now = _now()
    workspace = {
        "schema_version": WORKSPACE_SCHEMA_VERSION,
        "workspace_id": workspace_id,
        "document_id": document_id,
        "source_revision": certification.get("source_revision"),
        "source_hash": record.sha256,
        "certification_validation_id": certification.get("validation_id"),
        "active_viewport_id": active_viewport_id,
        "workspace_revision": 1,
        "bookmark_count": 0,
        "annotation_count": 0,
        "citation_draft_count": 0,
        "bookmarks": [],
        "annotations": [],
        "citation_drafts": [],
        "created_at_utc": now,
        "updated_at_utc": now,
        "warnings": [],
    }
    _atomic_write_json(path, workspace)
    _update_workspace_index(base)
    return {"status": "created", "workspace": workspace, "warnings": []}


def load_pdf_reader_workspace(
    workspace_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_workspace_dirs(root)
    payload = _read_json(_workspace_path(base, workspace_id))
    if not isinstance(payload, dict):
        return {"status": "not_found", "workspace_id": workspace_id, "workspace": None, "warnings": []}
    if payload.get("schema_version") != WORKSPACE_SCHEMA_VERSION:
        return {"status": "corrupt", "workspace_id": workspace_id, "blockers": ["unsupported_workspace_schema"], "recommended_action": "Create a new reader workspace."}
    blockers = _workspace_blockers(payload, base)
    if blockers:
        status = "stale" if any(item in {"source_revision_changed", "source_hash_changed", "backend_certification_changed"} for item in blockers) else "blocked"
        return {"status": status, "workspace_id": workspace_id, "workspace": payload, "blockers": blockers, "recommended_action": "Create a new workspace for the current document revision."}
    warnings = _workspace_warnings(payload, base)
    return {"status": "warning" if warnings else "current", "workspace_id": workspace_id, "workspace": payload, "warnings": warnings}


def save_pdf_reader_bookmark(
    workspace_id: str,
    page_number: int,
    label: str | None = None,
    locator: dict | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_workspace_dirs(root)
    loaded = load_pdf_reader_workspace(workspace_id, root=base)
    if loaded.get("status") not in {"current", "warning"}:
        return {"status": loaded.get("status"), "workspace_id": workspace_id, "blockers": loaded.get("blockers", ["workspace_unavailable"])}
    workspace = dict(loaded["workspace"])
    normalized_label = " ".join(str(label or "").strip().split())[:120] or None
    page = _normalize_positive_int(page_number)
    locator_value = _validate_workspace_locator(workspace, locator, page_number=page, root=base)
    if page is None or page < 1:
        return _blocked("invalid_page_number", workspace_id=workspace_id)
    if locator is not None and locator_value is None:
        return _blocked("invalid_locator", workspace_id=workspace_id)
    identity = _hash_payload({"page": page, "label": normalized_label or "", "locator": locator_value or {}})[7:23]
    for item in workspace.get("bookmarks", []):
        if isinstance(item, Mapping) and item.get("_identity") == identity:
            return {"status": "unchanged", "workspace": workspace, "bookmark": item, "warnings": []}
    bookmark = {
        "bookmark_id": f"bookmark_{identity}",
        "page_number": page,
        "label": normalized_label,
        "locator": locator_value,
        "created_at_utc": _now(),
        "warnings": [],
        "_identity": identity,
    }
    workspace.setdefault("bookmarks", []).append(bookmark)
    _touch_workspace(workspace)
    workspace["bookmark_count"] = len(workspace.get("bookmarks", []))
    _save_workspace(base, workspace)
    return {"status": "saved", "workspace": workspace, "bookmark": bookmark, "warnings": []}


def save_pdf_reader_annotation(
    workspace_id: str,
    page_number: int,
    annotation_type: str,
    rectangles_pdf: list[list[float]],
    note: str | None = None,
    locator: dict | None = None,
    selected_text_hash: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_workspace_dirs(root)
    loaded = load_pdf_reader_workspace(workspace_id, root=base)
    if loaded.get("status") not in {"current", "warning"}:
        return {"status": loaded.get("status"), "workspace_id": workspace_id, "blockers": loaded.get("blockers", ["workspace_unavailable"])}
    workspace = dict(loaded["workspace"])
    page = _normalize_positive_int(page_number)
    if page is None or annotation_type not in {"highlight", "underline", "note", "selection_reference"}:
        return _blocked("invalid_annotation", workspace_id=workspace_id)
    if not _rectangles_valid(rectangles_pdf):
        return _blocked("invalid_annotation_geometry", workspace_id=workspace_id)
    if not _rectangles_within_page(workspace, page, rectangles_pdf, base):
        return _blocked("invalid_annotation_geometry", workspace_id=workspace_id)
    locator_value = _validate_workspace_locator(workspace, locator, page_number=page, root=base)
    if locator is not None and locator_value is None:
        return _blocked("cross_document_locator", workspace_id=workspace_id)
    normalized_note = str(note or "").strip()[:500] or None
    annotation = {
        "annotation_id": f"annotation_{_hash_payload({'page': page, 'type': annotation_type, 'rectangles': rectangles_pdf, 'note': normalized_note or '', 'locator': locator_value or {}, 'selected_text_hash': selected_text_hash or ''})[7:23]}",
        "annotation_type": annotation_type,
        "page_number": page,
        "rectangles_pdf": [[float(v) for v in rect] for rect in rectangles_pdf],
        "note": normalized_note,
        "locator": locator_value,
        "selected_text_hash": str(selected_text_hash or "").strip() or None,
        "created_at_utc": _now(),
        "warnings": [],
    }
    workspace.setdefault("annotations", []).append(annotation)
    _touch_workspace(workspace)
    workspace["annotation_count"] = len(workspace.get("annotations", []))
    _save_workspace(base, workspace)
    return {"status": "saved", "workspace": workspace, "annotation": annotation, "warnings": []}


def draft_citation_from_pdf_selection(
    workspace_id: str,
    selection: dict,
    note: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_workspace_dirs(root)
    loaded = load_pdf_reader_workspace(workspace_id, root=base)
    if loaded.get("status") not in {"current", "warning"}:
        return {"status": loaded.get("status"), "workspace_id": workspace_id, "blockers": loaded.get("blockers", ["workspace_unavailable"])}
    workspace = dict(loaded["workspace"])
    valid = _validate_selection_for_draft(workspace, selection, base)
    if valid is None:
        return _blocked("invalid_selection", workspace_id=workspace_id)
    draft = {
        "citation_draft_id": f"citation_draft_{_hash_payload({'document_id': workspace.get('document_id'), 'page': selection.get('page_number'), 'selected_text_hash': selection.get('selected_text_hash'), 'offsets': [selection.get('start_offset'), selection.get('end_offset')]})[7:23]}",
        "status": "draft",
        "document_id": workspace.get("document_id"),
        "source_revision": workspace.get("source_revision"),
        "page": selection.get("page_number"),
        "chunk_id": selection.get("chunk_id"),
        "start_offset": selection.get("start_offset"),
        "end_offset": selection.get("end_offset"),
        "selected_text": selection.get("selected_text"),
        "selected_text_hash": selection.get("selected_text_hash"),
        "rectangles_pdf": [selection.get("pdf_bbox")],
        "note": str(note or "").strip()[:500] or None,
        "created_from": "pdf_text_selection",
        "created_at_utc": _now(),
        "warnings": [],
    }
    workspace.setdefault("citation_drafts", []).append(draft)
    _touch_workspace(workspace)
    workspace["citation_draft_count"] = len(workspace.get("citation_drafts", []))
    _save_workspace(base, workspace)
    return {"status": "saved", "workspace": workspace, "citation_draft": draft, "warnings": []}


def list_pdf_reader_workspace_items(
    workspace_id: str,
    item_type: str | None = None,
    page_number: int | None = None,
    limit: int = 100,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    loaded = load_pdf_reader_workspace(workspace_id, root=root)
    if loaded.get("status") not in {"current", "warning"}:
        return {"status": loaded.get("status"), "workspace_id": workspace_id, "items": [], "warnings": list(loaded.get("warnings", []))}
    workspace = loaded["workspace"]
    items = []
    requested_page = _normalize_positive_int(page_number) if page_number is not None else None
    for kind, field in (("bookmark", "bookmarks"), ("annotation", "annotations"), ("citation_draft", "citation_drafts")):
        if item_type and item_type != kind:
            continue
        for item in workspace.get(field, []):
            if not isinstance(item, Mapping):
                continue
            item_page = item.get("page_number", item.get("page"))
            if requested_page is not None and item_page != requested_page:
                continue
            items.append({"item_type": kind, **dict(item)})
    items.sort(key=lambda item: (int(item.get("page_number", item.get("page", 10**9)) or 10**9), str(item.get("created_at_utc") or ""), str(item.get("bookmark_id") or item.get("annotation_id") or item.get("citation_draft_id") or "")))
    return {"workspace_id": workspace_id, "item_type": item_type, "page_number": requested_page, "count": len(items[: max(0, int(limit))]), "items": items[: max(0, int(limit))], "warnings": []}


def build_pdf_reader_workspace_overlay(
    workspace_id: str,
    viewport_id: str,
    page_number: int | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_workspace_dirs(root)
    workspace_loaded = load_pdf_reader_workspace(workspace_id, root=base)
    if workspace_loaded.get("status") not in {"current", "warning"}:
        return {"status": workspace_loaded.get("status"), "workspace_id": workspace_id, "rectangles": [], "warnings": []}
    viewport_loaded = load_pdf_viewport_session(viewport_id, root=base)
    if viewport_loaded.get("status") != "loaded":
        return {"status": viewport_loaded.get("status"), "workspace_id": workspace_id, "rectangles": [], "warnings": []}
    workspace = workspace_loaded["workspace"]
    viewport = viewport_loaded["viewport"]
    if workspace.get("document_id") != viewport.get("document_id") or workspace.get("source_revision") != viewport.get("source_revision"):
        return {"status": "stale", "workspace_id": workspace_id, "rectangles": [], "warnings": ["workspace_viewport_revision_mismatch"]}
    target_page = _normalize_positive_int(page_number if page_number is not None else viewport.get("current_page")) or 1
    render = render_pdf_viewport_page(viewport_id, page_number=target_page, zoom_percent=int(viewport.get("zoom_percent") or 100), root=base)
    text_layer_result = extract_pdf_page_text_layer(viewport_id, page_number=target_page, root=base)
    if render.get("render_status") != "rendered" or text_layer_result.get("status") != "ready":
        return {"status": "blocked", "workspace_id": workspace_id, "rectangles": [], "warnings": ["overlay_dependencies_unavailable"]}
    rectangles = []
    seen: set[tuple[Any, ...]] = set()
    for annotation in workspace.get("annotations", []):
        if not isinstance(annotation, Mapping) or annotation.get("page_number") != target_page:
            continue
        for pdf_bbox in annotation.get("rectangles_pdf", []):
            image_bbox = _pdf_bbox_to_image_bbox(pdf_bbox, render, text_layer_result["text_layer"])
            key = tuple(image_bbox)
            if key in seen:
                continue
            seen.add(key)
            rectangles.append({"annotation_id": annotation.get("annotation_id"), "annotation_type": annotation.get("annotation_type"), "pdf_bbox": pdf_bbox, "image_bbox": image_bbox})
    bookmark_count = sum(1 for item in workspace.get("bookmarks", []) if isinstance(item, Mapping) and item.get("page_number") == target_page)
    annotation_count = sum(1 for item in workspace.get("annotations", []) if isinstance(item, Mapping) and item.get("page_number") == target_page)
    draft_count = sum(1 for item in workspace.get("citation_drafts", []) if isinstance(item, Mapping) and item.get("page") == target_page)
    return {"workspace_id": workspace_id, "viewport_id": viewport_id, "page_number": target_page, "bookmark_count": bookmark_count, "annotation_count": annotation_count, "citation_draft_count": draft_count, "rectangles": rectangles, "warnings": []}


def format_pdf_reader_workspace_report(
    workspace_id: str,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    loaded = load_pdf_reader_workspace(workspace_id, root=root)
    if not isinstance(loaded.get("workspace"), Mapping):
        text = "PDF Reader Workspace Report\n\nWorkspace unavailable."
        return _sanitize(text) if public_safe else text
    workspace = loaded["workspace"]
    current_page = None
    if workspace.get("active_viewport_id"):
        viewport_loaded = load_pdf_viewport_session(str(workspace.get("active_viewport_id")), root=root)
        if isinstance(viewport_loaded.get("viewport"), Mapping):
            current_page = viewport_loaded["viewport"].get("current_page")
    current_page_bookmarks = sum(1 for item in workspace.get("bookmarks", []) if isinstance(item, Mapping) and current_page is not None and item.get("page_number") == current_page)
    current_page_annotations = sum(1 for item in workspace.get("annotations", []) if isinstance(item, Mapping) and current_page is not None and item.get("page_number") == current_page)
    current_page_drafts = sum(1 for item in workspace.get("citation_drafts", []) if isinstance(item, Mapping) and current_page is not None and item.get("page") == current_page)
    lines = [
        "PDF Reader Workspace Report",
        "",
        f"Document: {workspace.get('document_id')}",
        f"Source Revision: {workspace.get('source_revision')}",
        f"Workspace Status: {loaded.get('status')}",
        f"Workspace Revision: {workspace.get('workspace_revision')}",
        "",
        "Reader Items:",
        f"- Bookmarks: {workspace.get('bookmark_count', 0)}",
        f"- Annotations: {workspace.get('annotation_count', 0)}",
        f"- Citation Drafts: {workspace.get('citation_draft_count', 0)}",
        "",
        "Current Page:",
        f"- Bookmarks: {current_page_bookmarks}",
        f"- Annotations: {current_page_annotations}",
        f"- Citation Drafts: {current_page_drafts}",
        "",
        "Citation Draft Status:",
        f"- Draft: {sum(1 for item in workspace.get('citation_drafts', []) if isinstance(item, Mapping) and item.get('status') == 'draft')}",
        "- Submitted: 0",
        "- Created as Real Citations: 0",
        "",
        "Important:",
        "Annotations are visual workspace overlays only.",
        "Citation drafts have not been added to the citation repository.",
    ]
    text = "\n".join(lines)
    return _sanitize(text) if public_safe else text


def _workspace_blockers(workspace: Mapping[str, Any], root: Path) -> list[str]:
    blockers: list[str] = []
    record = load_source_document(str(workspace.get("document_id") or ""), root=root, missing_ok=True)
    if record is None:
        blockers.append("document_not_found")
        return blockers
    certification = _latest_current_certification(str(workspace.get("document_id") or ""), root)
    if certification is None or certification.get("validation_id") != workspace.get("certification_validation_id"):
        blockers.append("backend_certification_changed")
    if workspace.get("source_revision") != certification.get("source_revision") if certification else None:
        blockers.append("source_revision_changed")
    if workspace.get("source_hash") != record.sha256:
        blockers.append("source_hash_changed")
    return blockers


def _workspace_warnings(workspace: Mapping[str, Any], root: Path) -> list[str]:
    warnings: list[str] = []
    page_count = _workspace_page_count(workspace)
    for bookmark in workspace.get("bookmarks", []):
        if isinstance(bookmark, Mapping) and (not isinstance(bookmark.get("page_number"), int) or int(bookmark.get("page_number") or 0) < 1 or int(bookmark.get("page_number") or 0) > page_count):
            warnings.append("invalid_bookmark_page")
    for annotation in workspace.get("annotations", []):
        if not isinstance(annotation, Mapping) or not _rectangles_valid(annotation.get("rectangles_pdf")):
            warnings.append("invalid_annotation_geometry")
    for draft in workspace.get("citation_drafts", []):
        if not isinstance(draft, Mapping) or draft.get("status") != "draft":
            warnings.append("invalid_citation_draft_status")
        elif _hash_payload(str(draft.get("selected_text") or "")) != draft.get("selected_text_hash"):
            warnings.append("selected_text_hash_mismatch")
    return sorted(set(warnings))


def _validate_workspace_locator(workspace: Mapping[str, Any], locator: dict | None, *, page_number: int | None, root: Path) -> dict[str, Any] | None:
    if locator is None:
        return None
    if not isinstance(locator, Mapping):
        return None
    if str(locator.get("document_id") or "") != str(workspace.get("document_id") or ""):
        return None
    if locator.get("source_revision") != workspace.get("source_revision"):
        return None
    page = _normalize_positive_int(locator.get("page"))
    if page is None or page_number is None or page != page_number:
        return None
    chunk_id = str(locator.get("chunk_id") or "")
    if chunk_id:
        chunk = load_chunk(chunk_id, root=root)
        if chunk.document_id != workspace.get("document_id"):
            return None
        if chunk.page_start is not None and chunk.page_end is not None and not (chunk.page_start <= page <= chunk.page_end):
            return None
    result = {"document_id": workspace.get("document_id"), "source_revision": workspace.get("source_revision"), "page": page}
    if chunk_id:
        result["chunk_id"] = chunk_id
    return result


def _validate_selection_for_draft(workspace: Mapping[str, Any], selection: Any, root: Path) -> dict[str, Any] | None:
    if not isinstance(selection, Mapping):
        return None
    if selection.get("document_id") != workspace.get("document_id") or selection.get("source_revision") != workspace.get("source_revision"):
        return None
    page = _normalize_positive_int(selection.get("page_number"))
    start_offset = _normalize_non_negative_int(selection.get("start_offset"))
    end_offset = _normalize_non_negative_int(selection.get("end_offset"))
    selected_text = str(selection.get("selected_text") or "").strip()
    selected_hash = str(selection.get("selected_text_hash") or "").strip()
    pdf_bbox = selection.get("pdf_bbox")
    if page is None or start_offset is None or end_offset is None or start_offset >= end_offset or not selected_text or len(selected_text) > 2000:
        return None
    if _hash_payload(selected_text) != selected_hash:
        return None
    if not isinstance(pdf_bbox, list) or len(pdf_bbox) != 4:
        return None
    chunk_id = str(selection.get("chunk_id") or "")
    if chunk_id:
        chunk = load_chunk(chunk_id, root=root)
        if chunk.document_id != workspace.get("document_id"):
            return None
    return dict(selection)


def _workspace_page_count(workspace: Mapping[str, Any]) -> int:
    viewport_id = str(workspace.get("active_viewport_id") or "")
    if viewport_id:
        loaded = load_pdf_viewport_session(viewport_id, root=SOURCE_DOCUMENT_ROOT)
        if isinstance(loaded.get("viewport"), Mapping):
            return int(loaded["viewport"].get("page_count") or 0)
    record = load_source_document(str(workspace.get("document_id") or ""), root=SOURCE_DOCUMENT_ROOT, missing_ok=True)
    return int(record.page_count or 0) if record else 0


def _rectangles_valid(rectangles_pdf: Any) -> bool:
    if not isinstance(rectangles_pdf, list) or not rectangles_pdf:
        return False
    for rect in rectangles_pdf:
        if not isinstance(rect, list) or len(rect) != 4:
            return False
        try:
            x0, y0, x1, y1 = [float(value) for value in rect]
        except Exception:
            return False
        if not all(math.isfinite(value) for value in (x0, y0, x1, y1)) or x1 <= x0 or y1 <= y0:
            return False
    return True


def _rectangles_within_page(workspace: Mapping[str, Any], page_number: int, rectangles_pdf: list[list[float]], root: Path) -> bool:
    viewport_id = str(workspace.get("active_viewport_id") or "")
    if not viewport_id:
        return True
    layer_result = extract_pdf_page_text_layer(viewport_id, page_number=page_number, root=root)
    if layer_result.get("status") != "ready":
        return False
    width = float(layer_result["text_layer"].get("page_width_points") or 0.0)
    height = float(layer_result["text_layer"].get("page_height_points") or 0.0)
    for rect in rectangles_pdf:
        x0, y0, x1, y1 = [float(value) for value in rect]
        if x0 < 0 or y0 < 0 or x1 > width or y1 > height:
            return False
    return True


def _touch_workspace(workspace: dict[str, Any]) -> None:
    workspace["workspace_revision"] = int(workspace.get("workspace_revision") or 0) + 1
    workspace["updated_at_utc"] = _now()


def _save_workspace(root: Path, workspace: Mapping[str, Any]) -> None:
    _atomic_write_json(_workspace_path(root, str(workspace.get("workspace_id") or "")), workspace)
    _update_workspace_index(root)


def _workspace_id(document_id: str, source_revision: Any) -> str:
    return f"reader_workspace_{document_id}_r{int(source_revision or 0)}"


def _workspace_path(root: Path, workspace_id: str) -> Path:
    return root / WORKSPACE_DIR / f"{workspace_id}.json"


def _ensure_workspace_dirs(root: Path | str) -> Path:
    base = _ensure_dirs(root)
    (base / WORKSPACE_DIR).mkdir(parents=True, exist_ok=True)
    index_path = base / "indexes" / WORKSPACE_INDEX
    if not index_path.exists():
        _atomic_write_json(index_path, {"entries": [], "updated_at_utc": _now()})
    return base


def _update_workspace_index(root: Path) -> None:
    entries = []
    for path in sorted((root / WORKSPACE_DIR).glob("reader_workspace_*.json")):
        payload = _read_json(path)
        if not isinstance(payload, Mapping):
            continue
        entries.append(
            {
                "workspace_id": payload.get("workspace_id"),
                "document_id": payload.get("document_id"),
                "source_revision": payload.get("source_revision"),
                "workspace_revision": payload.get("workspace_revision"),
                "bookmark_count": payload.get("bookmark_count"),
                "annotation_count": payload.get("annotation_count"),
                "citation_draft_count": payload.get("citation_draft_count"),
                "updated_at_utc": payload.get("updated_at_utc"),
            }
        )
    _atomic_write_json(root / "indexes" / WORKSPACE_INDEX, {"entries": entries, "updated_at_utc": _now()})


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _normalize_positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return int(value)


def _normalize_non_negative_int(value: Any) -> int | None:
    normalized = _normalize_positive_int(value)
    if normalized is None or normalized < 0:
        return None
    return normalized


def _sanitize(text: str) -> str:
    sanitized = str(text)
    for needle in ("C:\\", "/Users/", "pdf_sources", "pdf_reader_workspaces", "Traceback", "secret", "token="):
        sanitized = sanitized.replace(needle, "" if needle != "token=" else "[redacted]")
    return sanitized


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
