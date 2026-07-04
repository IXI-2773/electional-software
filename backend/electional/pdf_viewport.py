from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from .backend_contract_validation import list_backend_contract_validations
from .source_documents import SOURCE_DOCUMENT_ROOT, load_source_document
from .source_knowledge import load_chunk


SESSION_SCHEMA_VERSION = "pdf_viewport_session_v1"
RENDER_SCHEMA_VERSION = "pdf_viewport_render_v1"
SESSION_DIR = "pdf_viewport_sessions"
CACHE_DIR = "pdf_viewport_cache"
INDEX_DIR = "indexes"
SESSION_INDEX = "pdf_viewport_session_index.json"
ZOOM_STEPS = (25, 50, 75, 100, 125, 150, 175, 200, 250, 300, 400)
MAX_RENDER_PIXELS = 40_000_000


def get_pdf_renderer_capability() -> dict[str, Any]:
    adapter = _get_renderer_adapter()
    if adapter is None:
        return {
            "available": False,
            "renderer": None,
            "renderer_version": None,
            "supports_png": False,
            "warnings": ["pdf_renderer_unavailable"],
        }
    return {
        "available": True,
        "renderer": adapter["name"],
        "renderer_version": adapter["version"],
        "supports_png": True,
        "warnings": [],
    }


def create_pdf_viewport_session(
    document_id: str,
    initial_page: int = 1,
    zoom_percent: int = 100,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    certification = _latest_current_certification(document_id, base)
    if certification is None:
        return _blocked(
            "backend_certification_required",
            document_id=document_id,
            certification_status="missing",
            recommended_action="Run backend contract validation before opening the PDF viewport.",
        )
    if certification.get("certification_status") not in {"certified", "certified_with_warnings"}:
        return _blocked(
            "backend_certification_required",
            document_id=document_id,
            certification_status=certification.get("certification_status"),
            recommended_action="Run backend contract validation before opening the PDF viewport.",
        )
    pdf_state = _resolve_controlled_pdf(document_id, certification=certification, root=base)
    if pdf_state.get("status") != "ready":
        return pdf_state
    zoom = _normalize_zoom(zoom_percent)
    if zoom is None:
        return _blocked("invalid_zoom_percent", document_id=document_id, certification_status=certification.get("certification_status"), recommended_action="Use a supported zoom percent between 25 and 400.")
    page_count = int(pdf_state["page_count"])
    if initial_page < 1 or initial_page > page_count:
        return _blocked("invalid_initial_page", document_id=document_id, certification_status=certification.get("certification_status"), recommended_action="Use an initial page within the document page range.")
    now = _now()
    viewport_id = f"viewport_{document_id}_{_hash_payload({'document_id': document_id, 'source_revision': pdf_state['source_revision'], 'source_hash': pdf_state['source_hash'], 'timestamp': now})[7:23]}"
    capability = get_pdf_renderer_capability()
    warnings = list(capability.get("warnings", []))
    initial_page = _normalize_page_number(initial_page)
    if initial_page is None:
        return _blocked("invalid_initial_page", document_id=document_id, certification_status=certification.get("certification_status"), recommended_action="Use an initial page within the document page range.")
    session = {
        "schema_version": SESSION_SCHEMA_VERSION,
        "viewport_id": viewport_id,
        "document_id": document_id,
        "source_revision": pdf_state["source_revision"],
        "source_hash": pdf_state["source_hash"],
        "certification_validation_id": certification.get("validation_id"),
        "certification_status": certification.get("certification_status"),
        "page_count": page_count,
        "current_page": int(initial_page),
        "zoom_percent": zoom,
        "render_status": "not_rendered",
        "selected_locator": None,
        "renderer": capability.get("renderer"),
        "renderer_version": capability.get("renderer_version"),
        "cache_status": "missing",
        "created_at_utc": now,
        "updated_at_utc": now,
        "warnings": warnings,
    }
    _atomic_write_json(_session_path(base, viewport_id), session)
    _update_session_index(base)
    return {"status": "created", "viewport": session, "warnings": warnings}


def load_pdf_viewport_session(
    viewport_id: str,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    payload = _read_json(_session_path(base, viewport_id))
    if not isinstance(payload, dict):
        return {"status": "not_found", "viewport_id": viewport_id, "viewport": None, "warnings": []}
    if payload.get("schema_version") != SESSION_SCHEMA_VERSION:
        return {"status": "corrupt", "viewport_id": viewport_id, "blockers": ["unsupported_session_schema"], "recommended_action": "Create a new viewport session."}
    certification = _latest_current_certification(str(payload.get("document_id") or ""), base)
    if certification is None or certification.get("validation_id") != payload.get("certification_validation_id"):
        return {
            "status": "stale",
            "viewport_id": viewport_id,
            "blockers": ["backend_certification_changed"],
            "recommended_action": "Run backend certification and create a new viewport session.",
        }
    pdf_state = _resolve_controlled_pdf(str(payload.get("document_id") or ""), certification=certification, root=base)
    if pdf_state.get("status") != "ready":
        return {
            "status": "stale",
            "viewport_id": viewport_id,
            "blockers": list(pdf_state.get("blockers", ["controlled_pdf_unavailable"])),
            "recommended_action": "Run backend certification and create a new viewport session.",
        }
    blockers: list[str] = []
    if payload.get("source_revision") != pdf_state.get("source_revision"):
        blockers.append("source_revision_changed")
    if payload.get("source_hash") != pdf_state.get("source_hash"):
        blockers.append("source_hash_changed")
    if int(payload.get("page_count") or 0) != int(pdf_state.get("page_count") or 0):
        blockers.append("page_count_changed")
    if blockers:
        return {
            "status": "stale",
            "viewport_id": viewport_id,
            "blockers": blockers,
            "recommended_action": "Run backend certification and create a new viewport session.",
        }
    return {"status": "loaded", "viewport_id": viewport_id, "viewport": payload, "warnings": list(payload.get("warnings", []))}


def render_pdf_viewport_page(
    viewport_id: str,
    page_number: int | None = None,
    zoom_percent: int | None = None,
    regenerate: bool = False,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    loaded = load_pdf_viewport_session(viewport_id, root=base)
    if loaded.get("status") != "loaded":
        return {"status": loaded.get("status"), "viewport_id": viewport_id, "blockers": loaded.get("blockers", ["viewport_unavailable"])}
    session = loaded["viewport"]
    target_page = int(page_number if page_number is not None else session.get("current_page") or 1)
    zoom = _normalize_zoom(zoom_percent if zoom_percent is not None else int(session.get("zoom_percent") or 100))
    if zoom is None:
        return {"status": "blocked", "viewport_id": viewport_id, "blocker": "invalid_zoom_percent", "recommended_action": "Use a supported zoom step."}
    if target_page < 1 or target_page > int(session.get("page_count") or 0):
        return {"status": "blocked", "viewport_id": viewport_id, "blocker": "invalid_page_number", "recommended_action": "Use a page within the session page range."}
    capability = get_pdf_renderer_capability()
    if not capability.get("available"):
        return {
            "status": "renderer_unavailable",
            "viewport_id": viewport_id,
            "document_id": session.get("document_id"),
            "page_number": target_page,
            "zoom_percent": zoom,
            "warnings": list(capability.get("warnings", [])),
        }
    certification = _latest_current_certification(str(session.get("document_id") or ""), base)
    pdf_state = _resolve_controlled_pdf(str(session.get("document_id") or ""), certification=certification, root=base)
    adapter = _get_renderer_adapter()
    estimate = adapter["estimate_pixels"](pdf_state["pdf_path"], target_page, zoom)
    if int(estimate["width"]) * int(estimate["height"]) > MAX_RENDER_PIXELS:
        return {
            "status": "blocked",
            "blocker": "render_size_limit_exceeded",
            "viewport_id": viewport_id,
            "recommended_action": "Use a lower zoom level.",
        }
    cache_key = _cache_key(session, target_page, zoom, capability)
    png_path, meta_path = _cache_paths(base, cache_key)
    cache_status = "missing"
    if not regenerate:
        cached = _read_json(meta_path)
        if png_path.exists() and isinstance(cached, dict) and cached.get("cache_key") == cache_key and cached.get("page_number") == target_page and cached.get("zoom_percent") == zoom:
            cache_status = "reused"
            width = int(cached.get("width_pixels") or 0)
            height = int(cached.get("height_pixels") or 0)
            updated_session = dict(session)
            updated_session["current_page"] = target_page
            updated_session["zoom_percent"] = zoom
            updated_session["render_status"] = "rendered"
            updated_session["cache_status"] = cache_status
            updated_session["updated_at_utc"] = _now()
            _atomic_write_json(_session_path(base, viewport_id), updated_session)
            _update_session_index(base)
            return _render_result(updated_session, target_page, zoom, width, height, cache_status, png_path)
        if png_path.exists() or meta_path.exists():
            cache_status = "invalid"
    rendered = adapter["render_page"](pdf_state["pdf_path"], target_page, zoom)
    _atomic_write_bytes(png_path, rendered["png_bytes"])
    _atomic_write_json(
        meta_path,
        {
            "schema_version": RENDER_SCHEMA_VERSION,
            "cache_key": cache_key,
            "document_id": session.get("document_id"),
            "source_revision": session.get("source_revision"),
            "source_hash": session.get("source_hash"),
            "page_number": target_page,
            "zoom_percent": zoom,
            "renderer": capability.get("renderer"),
            "renderer_version": capability.get("renderer_version"),
            "width_pixels": int(rendered["width_pixels"]),
            "height_pixels": int(rendered["height_pixels"]),
            "image_format": "png",
        },
    )
    updated_session = dict(session)
    updated_session["current_page"] = target_page
    updated_session["zoom_percent"] = zoom
    updated_session["render_status"] = "rendered"
    updated_session["cache_status"] = "regenerated" if regenerate or cache_status == "invalid" else "created"
    updated_session["renderer"] = capability.get("renderer")
    updated_session["renderer_version"] = capability.get("renderer_version")
    updated_session["updated_at_utc"] = _now()
    _atomic_write_json(_session_path(base, viewport_id), updated_session)
    _update_session_index(base)
    return _render_result(updated_session, target_page, zoom, int(rendered["width_pixels"]), int(rendered["height_pixels"]), updated_session["cache_status"], png_path)


def navigate_pdf_viewport(
    viewport_id: str,
    action: str,
    page_number: int | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    loaded = load_pdf_viewport_session(viewport_id, root=base)
    if loaded.get("status") != "loaded":
        return {"status": loaded.get("status"), "viewport_id": viewport_id, "blockers": loaded.get("blockers", ["viewport_unavailable"])}
    session = dict(loaded["viewport"])
    current_page = int(session.get("current_page") or 1)
    page_count = int(session.get("page_count") or 1)
    current_zoom = int(session.get("zoom_percent") or 100)
    warnings: list[str] = []
    if action == "first":
        target_page = 1
        target_zoom = current_zoom
    elif action == "previous":
        target_page = max(1, current_page - 1)
        target_zoom = current_zoom
        if current_page == 1:
            warnings.append("already_at_first_page")
    elif action == "next":
        target_page = min(page_count, current_page + 1)
        target_zoom = current_zoom
        if current_page == page_count:
            warnings.append("already_at_last_page")
    elif action == "last":
        target_page = page_count
        target_zoom = current_zoom
    elif action == "jump":
        normalized_page = _normalize_page_number(page_number)
        if normalized_page is None or normalized_page < 1 or normalized_page > page_count:
            return {"status": "blocked", "viewport_id": viewport_id, "blocker": "invalid_page_number", "recommended_action": "Use a page within the document range."}
        target_page = normalized_page
        target_zoom = current_zoom
    elif action == "zoom_in":
        target_page = current_page
        target_zoom = _step_zoom(current_zoom, increase=True)
        if target_zoom == current_zoom:
            warnings.append("already_at_max_zoom")
    elif action == "zoom_out":
        target_page = current_page
        target_zoom = _step_zoom(current_zoom, increase=False)
        if target_zoom == current_zoom:
            warnings.append("already_at_min_zoom")
    else:
        return {"status": "blocked", "viewport_id": viewport_id, "blocker": "unsupported_navigation_action", "recommended_action": "Use a supported viewport navigation action."}
    session["current_page"] = target_page
    session["zoom_percent"] = target_zoom
    session["updated_at_utc"] = _now()
    _atomic_write_json(_session_path(base, viewport_id), session)
    _update_session_index(base)
    return {
        "status": "ready",
        "viewport_id": viewport_id,
        "document_id": session.get("document_id"),
        "current_page": target_page,
        "page_count": page_count,
        "zoom_percent": target_zoom,
        "render_required": True,
        "warnings": warnings,
    }


def synchronize_pdf_viewport_to_locator(
    viewport_id: str,
    locator: dict,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    loaded = load_pdf_viewport_session(viewport_id, root=base)
    if loaded.get("status") != "loaded":
        return {"status": loaded.get("status"), "viewport_id": viewport_id, "blockers": loaded.get("blockers", ["viewport_unavailable"])}
    session = dict(loaded["viewport"])
    if not isinstance(locator, Mapping):
        return {
            "viewport_id": viewport_id,
            "locator_status": "blocked",
            "blockers": ["invalid_locator_payload"],
            "recommended_action": "Use a locator object with document_id, source_revision, and page fields.",
        }
    locator = dict(locator)
    if str(locator.get("document_id") or "") != str(session.get("document_id") or ""):
        return {"viewport_id": viewport_id, "locator_status": "blocked", "blockers": ["cross_document_locator"], "recommended_action": "Use a locator for the active controlled document."}
    if locator.get("source_revision") != session.get("source_revision"):
        return {"viewport_id": viewport_id, "locator_status": "stale_revision", "blockers": ["locator_source_revision_changed"], "recommended_action": "Use a locator from the current controlled revision."}
    target_page = _normalize_page_number(locator.get("page"))
    if target_page < 1 or target_page > int(session.get("page_count") or 0):
        return {"viewport_id": viewport_id, "locator_status": "blocked", "blockers": ["invalid_locator_page"], "recommended_action": "Use a locator page within the document range."}
    chunk_id = str(locator.get("chunk_id") or "")
    if chunk_id:
        chunk = load_chunk(chunk_id, root=base)
        if chunk.document_id != session.get("document_id"):
            return {"viewport_id": viewport_id, "locator_status": "blocked", "blockers": ["locator_chunk_document_mismatch"], "recommended_action": "Use a locator chunk from the active document."}
        if chunk.page_start is not None and chunk.page_end is not None and not (chunk.page_start <= target_page <= chunk.page_end):
            return {"viewport_id": viewport_id, "locator_status": "blocked", "blockers": ["locator_chunk_page_mismatch"], "recommended_action": "Use a locator page that matches the target chunk."}
    start_offset = locator.get("start_offset")
    end_offset = locator.get("end_offset")
    if isinstance(start_offset, bool) or isinstance(end_offset, bool):
        return {"viewport_id": viewport_id, "locator_status": "blocked", "blockers": ["invalid_locator_offsets"], "recommended_action": "Use non-negative locator offsets with start <= end."}
    if (start_offset is not None and (not isinstance(start_offset, int) or start_offset < 0)) or (end_offset is not None and (not isinstance(end_offset, int) or end_offset < 0 or (isinstance(start_offset, int) and end_offset < start_offset))):
        return {"viewport_id": viewport_id, "locator_status": "blocked", "blockers": ["invalid_locator_offsets"], "recommended_action": "Use non-negative locator offsets with start <= end."}
    selected_locator = {
        "document_id": session.get("document_id"),
        "source_revision": session.get("source_revision"),
        "page": target_page,
        "chunk_id": chunk_id or None,
    }
    session["current_page"] = target_page
    session["selected_locator"] = selected_locator
    session["updated_at_utc"] = _now()
    _atomic_write_json(_session_path(base, viewport_id), session)
    _update_session_index(base)
    return {
        "viewport_id": viewport_id,
        "locator_status": "synchronized",
        "target_page": target_page,
        "chunk_id": chunk_id or None,
        "current_page": target_page,
        "render_required": True,
        "selected_locator": selected_locator,
        "warnings": [],
    }


def get_pdf_viewport_health(
    document_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_dirs(root)
    capability = get_pdf_renderer_capability()
    items: list[dict[str, Any]] = []
    corrupt_count = 0
    stale_count = 0
    duplicate_ids: set[str] = set()
    seen_ids: set[str] = set()
    for path in sorted((base / SESSION_DIR).glob("viewport_*.json")):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            corrupt_count += 1
            continue
        if document_id and str(payload.get("document_id") or "") != document_id:
            continue
        items.append(payload)
        viewport_id = str(payload.get("viewport_id") or "")
        if viewport_id in seen_ids:
            duplicate_ids.add(viewport_id)
        seen_ids.add(viewport_id)
        if load_pdf_viewport_session(viewport_id, root=base).get("status") == "stale":
            stale_count += 1
    invalid_cache_entries = 0
    for meta_path in sorted((base / CACHE_DIR).glob("render_*.json")):
        payload = _read_json(meta_path)
        if not isinstance(payload, dict):
            invalid_cache_entries += 1
            continue
        if document_id and str(payload.get("document_id") or "") != document_id:
            continue
        png_path = meta_path.with_suffix(".png")
        if not png_path.exists():
            invalid_cache_entries += 1
    if not items and corrupt_count == 0:
        status = "empty"
    else:
        status = "healthy"
        if stale_count:
            status = "stale"
        if corrupt_count or duplicate_ids:
            status = "corrupt"
        elif not capability.get("available") or invalid_cache_entries:
            status = "warning"
    return {
        "status": status,
        "renderer_status": "available" if capability.get("available") else "renderer_unavailable",
        "session_count": len(items),
        "duplicate_viewport_id_count": len(duplicate_ids),
        "stale_session_count": stale_count,
        "invalid_cache_entry_count": invalid_cache_entries,
        "corrupt_session_count": corrupt_count,
        "warnings": list(capability.get("warnings", [])),
    }


def format_pdf_viewport_report(
    viewport_id: str | None = None,
    document_id: str | None = None,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    session: dict[str, Any] | None = None
    if viewport_id:
        session = load_pdf_viewport_session(viewport_id, root=root).get("viewport")
    elif document_id:
        session = _latest_session_for_document(document_id, root=Path(root))
    capability = get_pdf_renderer_capability()
    if not isinstance(session, dict):
        text = "PDF Viewport Report\n\nNo viewport session was found."
        return _sanitize(text) if public_safe else text
    lines = [
        "PDF Viewport Report",
        "",
        f"Document: {session.get('document_id')}",
        f"Source Revision: {session.get('source_revision')}",
        f"Certification: {session.get('certification_status')}",
        f"Viewport Status: {'ready' if session.get('render_status') in {'not_rendered', 'rendered'} else session.get('render_status')}",
        "",
        "Renderer:",
        f"- Available: {'Yes' if capability.get('available') else 'No'}",
        f"- Engine: {capability.get('renderer') or 'unavailable'}",
        "",
        "Viewport:",
        f"- Pages: {session.get('page_count')}",
        f"- Current Page: {session.get('current_page')}",
        f"- Zoom: {session.get('zoom_percent')}%",
        f"- Render Status: {session.get('render_status')}",
        f"- Cache Status: {session.get('cache_status')}",
        "",
        "Locator Synchronization:",
        f"- Status: {'synchronized' if session.get('selected_locator') else 'not_selected'}",
        f"- Target Page: {(session.get('selected_locator') or {}).get('page', session.get('current_page'))}",
        "- Highlighting: not included in this phase",
        "",
        "Recommended Action:",
        "Continue reading or select another controlled locator." if capability.get("available") else "Install or enable a supported PDF renderer before page rendering.",
    ]
    text = "\n".join(lines)
    return _sanitize(text) if public_safe else text


def _render_result(session: Mapping[str, Any], page_number: int, zoom_percent: int, width: int, height: int, cache_status: str, png_path: Path) -> dict[str, Any]:
    return {
        "viewport_id": session.get("viewport_id"),
        "document_id": session.get("document_id"),
        "source_revision": session.get("source_revision"),
        "page_number": page_number,
        "page_count": session.get("page_count"),
        "zoom_percent": zoom_percent,
        "width_pixels": width,
        "height_pixels": height,
        "image_format": "png",
        "cache_status": cache_status,
        "render_status": "rendered",
        "render_id": f"render_{png_path.stem}",
        "cache_path": str(png_path),
        "warnings": list(session.get("warnings", [])),
    }


def _latest_current_certification(document_id: str, root: Path) -> dict[str, Any] | None:
    items = list_backend_contract_validations(document_id=document_id, limit=20, root=root).get("items", [])
    for item in items:
        if item.get("validation_current"):
            return item
    return None


def _resolve_controlled_pdf(document_id: str, *, certification: Mapping[str, Any] | None, root: Path) -> dict[str, Any]:
    record = load_source_document(document_id, root=root, missing_ok=True)
    if record is None:
        return {"status": "blocked", "document_id": document_id, "blockers": ["document_not_found"], "recommended_action": "Register the source document first."}
    if not record.stored_pdf_path:
        return {"status": "blocked", "document_id": document_id, "blockers": ["controlled_pdf_missing"], "recommended_action": "Store the PDF inside controlled source storage before opening a viewport."}
    pdf_path = Path(record.stored_pdf_path)
    if not pdf_path.exists():
        return {"status": "blocked", "document_id": document_id, "blockers": ["controlled_pdf_missing"], "recommended_action": "Restore the controlled PDF before opening a viewport."}
    try:
        resolved = pdf_path.resolve()
        allowed_root = (root / "pdf_sources").resolve()
        if not resolved.is_relative_to(allowed_root):
            return {"status": "blocked", "document_id": document_id, "blockers": ["controlled_pdf_outside_store"], "recommended_action": "Use the PDF stored by controlled registration."}
    except Exception:
        return {"status": "blocked", "document_id": document_id, "blockers": ["controlled_pdf_resolution_failed"], "recommended_action": "Re-register the controlled PDF source."}
    page_count = int(record.page_count or 0)
    adapter = _get_renderer_adapter()
    if page_count <= 0:
        if adapter is None:
            return {"status": "blocked", "document_id": document_id, "blockers": ["page_count_unavailable", "pdf_renderer_unavailable"], "recommended_action": "Enable a supported PDF renderer or refresh controlled source metadata."}
        page_count = int(adapter["page_count"](resolved))
    return {
        "status": "ready",
        "document_id": document_id,
        "pdf_path": resolved,
        "page_count": page_count,
        "source_revision": certification.get("source_revision") if certification else None,
        "source_hash": getattr(record, "sha256", None),
    }


def _get_renderer_adapter() -> dict[str, Any] | None:
    try:
        import fitz  # type: ignore
    except Exception:
        return None
    if not callable(getattr(fitz, "open", None)):
        return None

    def page_count(pdf_path: Path) -> int:
        with fitz.open(pdf_path) as document:
            return int(document.page_count)

    def estimate_pixels(pdf_path: Path, page_number: int, zoom_percent: int) -> dict[str, int]:
        with fitz.open(pdf_path) as document:
            page = document.load_page(page_number - 1)
            rect = page.rect
            scale = zoom_percent / 100.0
            return {"width": max(1, int(rect.width * scale)), "height": max(1, int(rect.height * scale))}

    def render_page(pdf_path: Path, page_number: int, zoom_percent: int) -> dict[str, Any]:
        with fitz.open(pdf_path) as document:
            page = document.load_page(page_number - 1)
            matrix = fitz.Matrix(zoom_percent / 100.0, zoom_percent / 100.0)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            return {
                "png_bytes": pixmap.tobytes("png"),
                "width_pixels": int(pixmap.width),
                "height_pixels": int(pixmap.height),
            }

    return {
        "name": "pymupdf",
        "version": getattr(fitz, "__version__", None) or getattr(fitz, "version", None) or "unknown",
        "page_count": page_count,
        "estimate_pixels": estimate_pixels,
        "render_page": render_page,
    }


def _latest_session_for_document(document_id: str, *, root: Path) -> dict[str, Any] | None:
    candidates = []
    for path in sorted((root / SESSION_DIR).glob("viewport_*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict) and str(payload.get("document_id") or "") == document_id:
            candidates.append(payload)
    candidates.sort(key=lambda item: (str(item.get("created_at_utc") or ""), str(item.get("viewport_id") or "")), reverse=True)
    return candidates[0] if candidates else None


def _step_zoom(current_zoom: int, *, increase: bool) -> int:
    if current_zoom not in ZOOM_STEPS:
        current_zoom = _normalize_zoom(current_zoom) or 100
    index = ZOOM_STEPS.index(current_zoom)
    if increase:
        return ZOOM_STEPS[min(index + 1, len(ZOOM_STEPS) - 1)]
    return ZOOM_STEPS[max(index - 1, 0)]


def _normalize_zoom(zoom_percent: int) -> int | None:
    if isinstance(zoom_percent, bool) or not isinstance(zoom_percent, int):
        return None
    if zoom_percent not in ZOOM_STEPS:
        return None
    return zoom_percent


def _normalize_page_number(page_number: int | None) -> int | None:
    if isinstance(page_number, bool) or not isinstance(page_number, int):
        return None
    return int(page_number)


def _cache_key(session: Mapping[str, Any], page_number: int, zoom_percent: int, capability: Mapping[str, Any]) -> str:
    return _hash_payload(
        {
            "document_id": session.get("document_id"),
            "source_revision": session.get("source_revision"),
            "source_hash": session.get("source_hash"),
            "page_number": page_number,
            "zoom_percent": zoom_percent,
            "renderer": capability.get("renderer"),
            "renderer_version": capability.get("renderer_version"),
            "render_schema_version": RENDER_SCHEMA_VERSION,
        }
    )[7:31]


def _cache_paths(root: Path, cache_key: str) -> tuple[Path, Path]:
    return root / CACHE_DIR / f"render_{cache_key}.png", root / CACHE_DIR / f"render_{cache_key}.json"


def _session_path(root: Path, viewport_id: str) -> Path:
    return root / SESSION_DIR / f"{_safe_id(viewport_id)}.json"


def _update_session_index(root: Path) -> None:
    entries = []
    for path in sorted((root / SESSION_DIR).glob("viewport_*.json")):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            continue
        entries.append(
            {
                "viewport_id": payload.get("viewport_id"),
                "document_id": payload.get("document_id"),
                "source_revision": payload.get("source_revision"),
                "current_page": payload.get("current_page"),
                "zoom_percent": payload.get("zoom_percent"),
                "render_status": payload.get("render_status"),
                "created_at_utc": payload.get("created_at_utc"),
                "updated_at_utc": payload.get("updated_at_utc"),
            }
        )
    _atomic_write_json(root / INDEX_DIR / SESSION_INDEX, {"entries": entries, "updated_at_utc": _now()})


def _ensure_dirs(root: Path | str) -> Path:
    base = Path(root)
    (base / SESSION_DIR).mkdir(parents=True, exist_ok=True)
    (base / CACHE_DIR).mkdir(parents=True, exist_ok=True)
    (base / INDEX_DIR).mkdir(parents=True, exist_ok=True)
    index_path = base / INDEX_DIR / SESSION_INDEX
    if not index_path.exists():
        _atomic_write_json(index_path, {"entries": [], "updated_at_utc": _now()})
    return base


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


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_bytes(payload)
    tmp.replace(path)


def _hash_payload(payload: Any) -> str:
    import hashlib

    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _blocked(blocker: str, **payload: Any) -> dict[str, Any]:
    result = {"status": "blocked", "blocker": blocker, "blockers": [blocker]}
    result.update(payload)
    return result


def _safe_id(value: str) -> str:
    return "".join(character if character.isalnum() or character in {"_", "-", "."} else "_" for character in str(value))


def _sanitize(text: str) -> str:
    sanitized = str(text)
    for needle in ("C:\\", "/Users/", "pdf_sources", "pdf_viewport_cache", "token=", "secret", "Traceback"):
        sanitized = sanitized.replace(needle, "" if needle != "token=" else "[redacted]")
    return sanitized


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
