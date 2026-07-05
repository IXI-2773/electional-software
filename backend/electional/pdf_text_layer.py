from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from .pdf_viewport import (
    CACHE_DIR,
    INDEX_DIR,
    _atomic_write_json,
    _blocked,
    _ensure_dirs,
    _get_renderer_adapter,
    _hash_payload,
    _latest_current_certification,
    _read_json,
    _resolve_controlled_pdf,
    load_pdf_viewport_session,
    render_pdf_viewport_page,
)
from .source_documents import SOURCE_DOCUMENT_ROOT
from .source_knowledge import load_chunk


TEXT_LAYER_SCHEMA_VERSION = "pdf_page_text_layer_v1"
OVERLAY_SCHEMA_VERSION = "pdf_overlay_v1"
TEXT_LAYER_DIR = "pdf_text_layers"
OVERLAY_DIR = "pdf_overlay_cache"
TEXT_LAYER_INDEX = "pdf_text_layer_index.json"


def get_pdf_text_layer_capability() -> dict[str, Any]:
    adapter = _get_text_layer_adapter()
    if adapter is None:
        return {
            "available": False,
            "renderer": "pymupdf" if _get_renderer_adapter() else None,
            "renderer_version": (_get_renderer_adapter() or {}).get("version"),
            "supports_words": False,
            "supports_spans": False,
            "supports_character_boxes": False,
            "warnings": ["native_text_layer_unavailable"],
        }
    return {
        "available": True,
        "renderer": adapter["name"],
        "renderer_version": adapter["version"],
        "supports_words": True,
        "supports_spans": True,
        "supports_character_boxes": False,
        "warnings": [],
    }


def extract_pdf_page_text_layer(
    viewport_id: str,
    page_number: int | None = None,
    regenerate: bool = False,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_text_layer_dirs(root)
    loaded = load_pdf_viewport_session(viewport_id, root=base)
    if loaded.get("status") != "loaded":
        return {"status": loaded.get("status"), "viewport_id": viewport_id, "blockers": loaded.get("blockers", ["viewport_unavailable"])}
    session = loaded["viewport"]
    capability = get_pdf_text_layer_capability()
    if not capability.get("available"):
        return {"status": "text_layer_unavailable", "viewport_id": viewport_id, "warnings": list(capability.get("warnings", []))}
    target_page = _normalize_positive_int(page_number if page_number is not None else session.get("current_page"))
    if target_page is None or target_page < 1 or target_page > int(session.get("page_count") or 0):
        return _blocked("invalid_page_number", viewport_id=viewport_id, recommended_action="Use a current viewport page.")
    certification = _latest_current_certification(str(session.get("document_id") or ""), base)
    pdf_state = _resolve_controlled_pdf(str(session.get("document_id") or ""), certification=certification, root=base)
    if pdf_state.get("status") != "ready":
        return {"status": "stale", "viewport_id": viewport_id, "blockers": list(pdf_state.get("blockers", ["controlled_pdf_unavailable"]))}
    cache_key = _text_layer_cache_key(session, target_page, capability)
    cache_path = base / TEXT_LAYER_DIR / f"text_layer_{cache_key}.json"
    cache_status = "missing"
    if not regenerate:
        cached = _read_json(cache_path)
        if _is_valid_text_layer_cache(cached, session, target_page, capability):
            reused = dict(cached)
            reused["cache_status"] = "reused"
            return {"status": "ready", "text_layer": reused, "warnings": list(reused.get("warnings", []))}
        if cache_path.exists():
            cache_status = "invalid"
    adapter = _get_text_layer_adapter()
    extracted = adapter["extract_page_text_layer"](pdf_state["pdf_path"], target_page)
    words, spans, normalized_page_text = _normalize_page_text_layer(extracted.get("words", []), extracted.get("spans", []))
    text_layer = {
        "schema_version": TEXT_LAYER_SCHEMA_VERSION,
        "text_layer_id": f"text_layer_{cache_key}",
        "viewport_id": viewport_id,
        "document_id": session.get("document_id"),
        "source_revision": session.get("source_revision"),
        "source_hash": session.get("source_hash"),
        "page_number": target_page,
        "page_width_points": float(extracted.get("page_width_points") or 0.0),
        "page_height_points": float(extracted.get("page_height_points") or 0.0),
        "rotation": int(extracted.get("rotation") or 0),
        "renderer": capability.get("renderer"),
        "renderer_version": capability.get("renderer_version"),
        "words": words,
        "spans": spans,
        "normalized_page_text": normalized_page_text,
        "cache_status": "regenerated" if regenerate or cache_status == "invalid" else "created",
        "warnings": list(extracted.get("warnings", [])),
        "created_at_utc": _now(),
        "updated_at_utc": _now(),
    }
    _atomic_write_json(cache_path, text_layer)
    _update_text_layer_index(base)
    return {"status": "ready", "text_layer": text_layer, "warnings": list(text_layer.get("warnings", []))}


def map_pdf_locator_to_rectangles(
    viewport_id: str,
    locator: dict,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_text_layer_dirs(root)
    loaded = load_pdf_viewport_session(viewport_id, root=base)
    if loaded.get("status") != "loaded":
        return {"viewport_id": viewport_id, "mapping_status": loaded.get("status"), "warnings": [], "rectangle_count": 0}
    session = loaded["viewport"]
    valid = _validate_locator(session, locator, root=base)
    if valid.get("mapping_status") != "ready":
        return valid
    text_layer_result = extract_pdf_page_text_layer(viewport_id, page_number=valid["page_number"], root=base)
    if text_layer_result.get("status") == "text_layer_unavailable":
        return {"viewport_id": viewport_id, "document_id": session.get("document_id"), "page_number": valid["page_number"], "mapping_status": "text_layer_unavailable", "rectangle_count": 0, "warnings": ["text_layer_unavailable"]}
    text_layer = text_layer_result["text_layer"]
    mapped = _map_locator_with_text_layer(locator, text_layer)
    mapped.update({"viewport_id": viewport_id, "document_id": session.get("document_id"), "page_number": valid["page_number"]})
    return mapped


def build_pdf_highlight_overlay(
    viewport_id: str,
    locators: list[dict],
    overlay_type: str = "search",
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_text_layer_dirs(root)
    if overlay_type not in {"search", "citation", "selected_locator"}:
        return _blocked("unsupported_overlay_type", viewport_id=viewport_id)
    rendered = render_pdf_viewport_page(viewport_id, root=base)
    if rendered.get("render_status") != "rendered":
        return {"status": rendered.get("status", "blocked"), "viewport_id": viewport_id, "blockers": rendered.get("blockers", [rendered.get("blocker", "render_unavailable")])}
    rectangles: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[tuple[Any, ...]] = set()
    mapped_count = 0
    unmapped_count = 0
    for index, locator in enumerate(locators):
        result = map_pdf_locator_to_rectangles(viewport_id, locator, root=base)
        locator_id = str((locator or {}).get("locator_id") or (locator or {}).get("citation_id") or (locator or {}).get("result_id") or f"locator_{index}")
        if result.get("mapping_status") not in {"exact", "unique_text_match"}:
            unmapped_count += 1
            warnings.append(f"{locator_id}_{result.get('mapping_status', 'unmappable')}")
            continue
        mapped_count += 1
        for pdf_bbox in result.get("rectangles_pdf", []):
            image_bbox = _pdf_bbox_to_image_bbox(pdf_bbox, rendered, result)
            key = tuple(image_bbox)
            if key in seen:
                continue
            seen.add(key)
            rectangles.append(
                {
                    "locator_id": locator_id,
                    "mapping_status": result.get("mapping_status"),
                    "pdf_bbox": pdf_bbox,
                    "image_bbox": image_bbox,
                }
            )
    overlay = {
        "schema_version": OVERLAY_SCHEMA_VERSION,
        "overlay_id": f"overlay_{_hash_payload({'viewport_id': viewport_id, 'overlay_type': overlay_type, 'page_number': rendered.get('page_number'), 'rectangles': rectangles})[7:23]}",
        "viewport_id": viewport_id,
        "document_id": rendered.get("document_id"),
        "page_number": rendered.get("page_number"),
        "overlay_type": overlay_type,
        "requested_locator_count": len(locators),
        "mapped_locator_count": mapped_count,
        "unmapped_locator_count": unmapped_count,
        "rectangles": rectangles,
        "warnings": warnings,
    }
    _atomic_write_json(base / OVERLAY_DIR / f"{overlay['overlay_id']}.json", overlay)
    return overlay


def select_pdf_text_in_rectangle(
    viewport_id: str,
    canvas_bbox: list[float],
    selection_mode: str = "intersect",
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_text_layer_dirs(root)
    if selection_mode not in {"intersect", "contained"}:
        return _blocked("unsupported_selection_mode", viewport_id=viewport_id)
    rendered = render_pdf_viewport_page(viewport_id, root=base)
    if rendered.get("render_status") != "rendered":
        return {"selection_status": "blocked", "viewport_id": viewport_id, "blockers": rendered.get("blockers", [rendered.get("blocker", "render_unavailable")])}
    text_layer_result = extract_pdf_page_text_layer(viewport_id, page_number=int(rendered.get("page_number") or 0), root=base)
    if text_layer_result.get("status") != "ready":
        return {"selection_status": "blocked", "viewport_id": viewport_id, "blockers": [text_layer_result.get("status", "text_layer_unavailable")]}
    if not isinstance(canvas_bbox, list) or len(canvas_bbox) != 4:
        return _blocked("invalid_canvas_bbox", viewport_id=viewport_id)
    normalized_canvas = _normalize_bbox(canvas_bbox)
    if normalized_canvas is None:
        return _blocked("invalid_canvas_bbox", viewport_id=viewport_id)
    pdf_bbox = _image_bbox_to_pdf_bbox(normalized_canvas, rendered, text_layer_result["text_layer"])
    words = []
    for word in text_layer_result["text_layer"].get("words", []):
        bbox = word.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue
        include = _bbox_contains(pdf_bbox, bbox) if selection_mode == "contained" else _bbox_intersects(pdf_bbox, bbox)
        if include:
            words.append(word)
    if not words:
        return {"viewport_id": viewport_id, "document_id": rendered.get("document_id"), "page_number": rendered.get("page_number"), "selection_status": "no_text_selected", "selection_mode": selection_mode, "selected_word_count": 0, "selected_text": "", "warnings": []}
    selected_text = " ".join(str(word.get("text") or "") for word in words).strip()
    start_offset = min(int(word.get("start_char") or 0) for word in words)
    end_offset = max(int(word.get("end_char") or 0) for word in words)
    return {
        "viewport_id": viewport_id,
        "document_id": rendered.get("document_id"),
        "source_revision": text_layer_result["text_layer"].get("source_revision"),
        "page_number": rendered.get("page_number"),
        "selection_status": "selected",
        "selection_mode": selection_mode,
        "selected_word_count": len(words),
        "selected_text": selected_text,
        "selected_text_hash": _hash_payload(selected_text),
        "pdf_bbox": pdf_bbox,
        "start_offset": start_offset,
        "end_offset": end_offset,
        "word_indexes": [int(word.get("word_index") or 0) for word in words],
        "warnings": [],
    }


def format_pdf_text_selection(selection: dict, include_locator: bool = False, public_safe: bool = True) -> str:
    text = str((selection or {}).get("selected_text") or "")
    if include_locator and (selection or {}).get("selection_status") == "selected":
        text = (
            f"{text}\n\n"
            f"Document: {(selection or {}).get('document_id')}\n"
            f"Revision: {(selection or {}).get('source_revision')}\n"
            f"Page: {(selection or {}).get('page_number')}\n"
            f"Offsets: {(selection or {}).get('start_offset')}–{(selection or {}).get('end_offset')}"
        )
    return _sanitize(text) if public_safe else text


def get_pdf_text_layer_health(
    document_id: str | None = None,
    viewport_id: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = _ensure_text_layer_dirs(root)
    capability = get_pdf_text_layer_capability()
    entries = []
    malformed = 0
    duplicates: set[str] = set()
    seen: set[str] = set()
    for path in sorted((base / TEXT_LAYER_DIR).glob("text_layer_*.json")):
        payload = _read_json(path)
        if not isinstance(payload, dict):
            malformed += 1
            continue
        if document_id and payload.get("document_id") != document_id:
            continue
        if viewport_id and payload.get("viewport_id") != viewport_id:
            continue
        entries.append(payload)
        text_layer_id = str(payload.get("text_layer_id") or "")
        if text_layer_id in seen:
            duplicates.add(text_layer_id)
        seen.add(text_layer_id)
        if not _text_layer_words_valid(payload.get("words", [])):
            malformed += 1
    status = "empty" if not entries and malformed == 0 else "healthy"
    if not capability.get("available"):
        status = "blocked"
    elif malformed:
        status = "corrupt"
    elif duplicates:
        status = "warning"
    return {
        "status": status,
        "renderer_status": "available" if capability.get("available") else "text_layer_unavailable",
        "text_layer_count": len(entries),
        "duplicate_text_layer_id_count": len(duplicates),
        "malformed_text_layer_count": malformed,
        "warnings": list(capability.get("warnings", [])),
    }


def format_pdf_text_layer_report(
    viewport_id: str | None = None,
    document_id: str | None = None,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    base = _ensure_text_layer_dirs(root)
    viewport = load_pdf_viewport_session(viewport_id, root=base).get("viewport") if viewport_id else None
    text_layer = None
    if viewport_id and isinstance(viewport, dict):
        result = extract_pdf_page_text_layer(viewport_id, page_number=int(viewport.get("current_page") or 1), root=base)
        text_layer = result.get("text_layer")
    elif document_id:
        for path in sorted((base / TEXT_LAYER_DIR).glob("text_layer_*.json")):
            payload = _read_json(path)
            if isinstance(payload, dict) and payload.get("document_id") == document_id:
                text_layer = payload
    if not isinstance(text_layer, dict):
        text = "PDF Text-Layer Report\n\nText layer unavailable."
        return _sanitize(text) if public_safe else text
    lines = [
        "PDF Text-Layer Report",
        "",
        f"Document: {text_layer.get('document_id')}",
        f"Source Revision: {text_layer.get('source_revision')}",
        f"Viewport Page: {text_layer.get('page_number')}",
        "Text Layer: available",
        "",
        "Page Geometry:",
        f"- Words: {len(text_layer.get('words', []))}",
        f"- Spans: {len(text_layer.get('spans', []))}",
        f"- Page Size: {int(float(text_layer.get('page_width_points') or 0))} x {int(float(text_layer.get('page_height_points') or 0))} points",
        "",
        "Important:",
        "Highlights are visual overlays only. The PDF and source records were not modified.",
    ]
    text = "\n".join(lines)
    return _sanitize(text) if public_safe else text


def _get_text_layer_adapter() -> dict[str, Any] | None:
    try:
        import fitz  # type: ignore
    except Exception:
        return None
    if not callable(getattr(fitz, "open", None)):
        return None

    def extract_page_text_layer(pdf_path: Path, page_number: int) -> dict[str, Any]:
        with fitz.open(pdf_path) as document:
            page = document.load_page(page_number - 1)
            words = []
            for item in page.get_text("words"):
                x0, y0, x1, y1, text, block_no, line_no, word_no = item
                words.append(
                    {
                        "text": text,
                        "bbox": [float(x0), float(y0), float(x1), float(y1)],
                        "block_index": int(block_no),
                        "line_index": int(line_no),
                        "span_index": 0,
                        "word_no": int(word_no),
                    }
                )
            spans: list[dict[str, Any]] = []
            raw = page.get_text("dict")
            for block_index, block in enumerate(raw.get("blocks", [])):
                for line_index, line in enumerate(block.get("lines", [])):
                    for span_index, span in enumerate(line.get("spans", [])):
                        spans.append(
                            {
                                "text": str(span.get("text") or ""),
                                "bbox": [float(value) for value in span.get("bbox", [0.0, 0.0, 0.0, 0.0])],
                                "block_index": block_index,
                                "line_index": line_index,
                                "span_index": span_index,
                            }
                        )
            return {
                "page_width_points": float(page.rect.width),
                "page_height_points": float(page.rect.height),
                "rotation": int(page.rotation or 0),
                "words": words,
                "spans": spans,
                "warnings": [] if words else ["text_layer_unavailable"],
            }

    return {
        "name": "pymupdf",
        "version": getattr(fitz, "__version__", None) or getattr(fitz, "version", None) or "unknown",
        "extract_page_text_layer": extract_page_text_layer,
    }


def _normalize_page_text_layer(words: list[dict[str, Any]], spans: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    normalized_words: list[dict[str, Any]] = []
    cursor = 0
    ordered = sorted(
        [item for item in words if isinstance(item, Mapping)],
        key=lambda item: (
            int(item.get("block_index") or 0),
            int(item.get("line_index") or 0),
            float((item.get("bbox") or [0, 0, 0, 0])[1]),
            float((item.get("bbox") or [0, 0, 0, 0])[0]),
            str(item.get("text") or ""),
        ),
    )
    page_parts: list[str] = []
    for index, word in enumerate(ordered):
        text = str(word.get("text") or "").strip()
        if not text:
            continue
        if page_parts:
            page_parts.append(" ")
            cursor += 1
        start_char = cursor
        page_parts.append(text)
        cursor += len(text)
        end_char = cursor
        normalized_words.append(
            {
                "word_index": len(normalized_words),
                "text": text,
                "normalized_text": text.casefold(),
                "bbox": [float(value) for value in word.get("bbox", [0.0, 0.0, 0.0, 0.0])],
                "block_index": int(word.get("block_index") or 0),
                "line_index": int(word.get("line_index") or 0),
                "span_index": int(word.get("span_index") or 0),
                "start_char": start_char,
                "end_char": end_char,
            }
        )
    normalized_spans = []
    for index, span in enumerate(spans):
        if not isinstance(span, Mapping):
            continue
        normalized_spans.append(
            {
                "span_index": index,
                "text": str(span.get("text") or ""),
                "bbox": [float(value) for value in span.get("bbox", [0.0, 0.0, 0.0, 0.0])],
                "block_index": int(span.get("block_index") or 0),
                "line_index": int(span.get("line_index") or 0),
            }
        )
    return normalized_words, normalized_spans, "".join(page_parts)


def _validate_locator(session: Mapping[str, Any], locator: Any, *, root: Path) -> dict[str, Any]:
    if not isinstance(locator, Mapping):
        return {"mapping_status": "invalid_locator", "rectangle_count": 0, "warnings": ["invalid_locator"]}
    if str(locator.get("document_id") or "") != str(session.get("document_id") or ""):
        return {"mapping_status": "cross_document", "rectangle_count": 0, "warnings": ["cross_document"]}
    if locator.get("source_revision") != session.get("source_revision"):
        return {"mapping_status": "stale_revision", "rectangle_count": 0, "warnings": ["stale_revision"]}
    page_number = _normalize_positive_int(locator.get("page"))
    if page_number is None or page_number < 1 or page_number > int(session.get("page_count") or 0):
        return {"mapping_status": "invalid_locator", "rectangle_count": 0, "warnings": ["invalid_locator_page"]}
    chunk_id = str(locator.get("chunk_id") or "")
    if chunk_id:
        chunk = load_chunk(chunk_id, root=root)
        if chunk.document_id != session.get("document_id"):
            return {"mapping_status": "cross_document", "rectangle_count": 0, "warnings": ["cross_document_chunk"]}
        if chunk.page_start is not None and chunk.page_end is not None and not (chunk.page_start <= page_number <= chunk.page_end):
            return {"mapping_status": "invalid_locator", "rectangle_count": 0, "warnings": ["chunk_not_on_page"]}
    start_offset = locator.get("start_offset")
    end_offset = locator.get("end_offset")
    if start_offset is not None and end_offset is not None:
        start_offset = _normalize_non_negative_int(start_offset)
        end_offset = _normalize_non_negative_int(end_offset)
        if start_offset is None or end_offset is None or start_offset >= end_offset:
            return {"mapping_status": "invalid_locator", "rectangle_count": 0, "warnings": ["invalid_locator_offsets"]}
    return {"mapping_status": "ready", "page_number": page_number, "rectangle_count": 0, "warnings": []}


def _map_locator_with_text_layer(locator: Mapping[str, Any], text_layer: Mapping[str, Any]) -> dict[str, Any]:
    words = [word for word in text_layer.get("words", []) if isinstance(word, Mapping)]
    start_offset = _normalize_non_negative_int(locator.get("start_offset"))
    end_offset = _normalize_non_negative_int(locator.get("end_offset"))
    if start_offset is not None and end_offset is not None and start_offset < end_offset:
        matched = [word for word in words if int(word.get("start_char") or -1) < end_offset and int(word.get("end_char") or -1) > start_offset]
        return _mapping_result("exact", "page_character_offsets", matched)
    selected_text = str(locator.get("selected_text") or "").strip()
    selected_hash = str(locator.get("selected_text_hash") or "").strip()
    if selected_text or selected_hash:
        matches = _find_exact_text_matches(words, selected_text=selected_text, selected_hash=selected_hash)
        if len(matches) == 1:
            return _mapping_result("unique_text_match", "selected_text_hash" if selected_hash else "selected_text", matches[0])
        if len(matches) > 1:
            return {"mapping_status": "ambiguous", "mapping_basis": "selected_text", "rectangle_count": 0, "rectangles_pdf": [], "matched_word_indexes": [], "warnings": ["ambiguous_text_match"]}
    return {"mapping_status": "unmappable", "mapping_basis": "unmappable", "rectangle_count": 0, "rectangles_pdf": [], "matched_word_indexes": [], "warnings": ["unmappable"]}


def _find_exact_text_matches(words: list[Mapping[str, Any]], *, selected_text: str, selected_hash: str) -> list[list[Mapping[str, Any]]]:
    matches: list[list[Mapping[str, Any]]] = []
    for start in range(len(words)):
        for end in range(start + 1, len(words) + 1):
            candidate = " ".join(str(word.get("text") or "") for word in words[start:end]).strip()
            if not candidate:
                continue
            if selected_text and candidate != selected_text:
                continue
            if selected_hash and _hash_payload(candidate) != selected_hash:
                continue
            matches.append(words[start:end])
    return matches


def _mapping_result(status: str, basis: str, matched_words: list[Mapping[str, Any]]) -> dict[str, Any]:
    rectangles = [_merge_bboxes([word.get("bbox") for word in matched_words if isinstance(word.get("bbox"), list)])]
    rectangles = [bbox for bbox in rectangles if bbox]
    return {
        "mapping_status": status,
        "mapping_basis": basis,
        "rectangle_count": len(rectangles),
        "rectangles_pdf": rectangles,
        "matched_word_indexes": [int(word.get("word_index") or 0) for word in matched_words],
        "matched_text_hash": _hash_payload(" ".join(str(word.get("text") or "") for word in matched_words).strip()),
        "warnings": [],
    }


def _pdf_bbox_to_image_bbox(pdf_bbox: list[float], render: Mapping[str, Any], text_layer: Mapping[str, Any]) -> list[float]:
    page_width = float(text_layer.get("page_width_points") or 1.0)
    page_height = float(text_layer.get("page_height_points") or 1.0)
    image_width = float(render.get("width_pixels") or 1.0)
    image_height = float(render.get("height_pixels") or 1.0)
    x_scale = image_width / page_width
    y_scale = image_height / page_height
    return [round(float(pdf_bbox[0]) * x_scale, 3), round(float(pdf_bbox[1]) * y_scale, 3), round(float(pdf_bbox[2]) * x_scale, 3), round(float(pdf_bbox[3]) * y_scale, 3)]


def _image_bbox_to_pdf_bbox(image_bbox: list[float], render: Mapping[str, Any], text_layer: Mapping[str, Any]) -> list[float]:
    page_width = float(text_layer.get("page_width_points") or 1.0)
    page_height = float(text_layer.get("page_height_points") or 1.0)
    image_width = float(render.get("width_pixels") or 1.0)
    image_height = float(render.get("height_pixels") or 1.0)
    x_scale = page_width / image_width
    y_scale = page_height / image_height
    return [round(float(image_bbox[0]) * x_scale, 3), round(float(image_bbox[1]) * y_scale, 3), round(float(image_bbox[2]) * x_scale, 3), round(float(image_bbox[3]) * y_scale, 3)]


def _text_layer_cache_key(session: Mapping[str, Any], page_number: int, capability: Mapping[str, Any]) -> str:
    return _hash_payload(
        {
            "document_id": session.get("document_id"),
            "source_revision": session.get("source_revision"),
            "source_hash": session.get("source_hash"),
            "page_number": page_number,
            "renderer": capability.get("renderer"),
            "renderer_version": capability.get("renderer_version"),
            "schema_version": TEXT_LAYER_SCHEMA_VERSION,
        }
    )[7:31]


def _is_valid_text_layer_cache(cached: Any, session: Mapping[str, Any], page_number: int, capability: Mapping[str, Any]) -> bool:
    return (
        isinstance(cached, Mapping)
        and cached.get("schema_version") == TEXT_LAYER_SCHEMA_VERSION
        and cached.get("document_id") == session.get("document_id")
        and cached.get("source_revision") == session.get("source_revision")
        and cached.get("source_hash") == session.get("source_hash")
        and cached.get("page_number") == page_number
        and cached.get("renderer") == capability.get("renderer")
        and cached.get("renderer_version") == capability.get("renderer_version")
        and _text_layer_words_valid(cached.get("words", []))
    )


def _text_layer_words_valid(words: Any) -> bool:
    if not isinstance(words, list):
        return False
    for word in words:
        if not isinstance(word, Mapping):
            return False
        if not isinstance(word.get("bbox"), list) or len(word.get("bbox", [])) != 4:
            return False
        start_char = word.get("start_char")
        end_char = word.get("end_char")
        if isinstance(start_char, bool) or isinstance(end_char, bool) or not isinstance(start_char, int) or not isinstance(end_char, int) or start_char >= end_char:
            return False
    return True


def _merge_bboxes(bboxes: list[Any]) -> list[float] | None:
    valid = [bbox for bbox in bboxes if isinstance(bbox, list) and len(bbox) == 4]
    if not valid:
        return None
    return [
        min(float(bbox[0]) for bbox in valid),
        min(float(bbox[1]) for bbox in valid),
        max(float(bbox[2]) for bbox in valid),
        max(float(bbox[3]) for bbox in valid),
    ]


def _bbox_intersects(a: list[float], b: list[float]) -> bool:
    return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])


def _bbox_contains(a: list[float], b: list[float]) -> bool:
    return a[0] <= b[0] and a[1] <= b[1] and a[2] >= b[2] and a[3] >= b[3]


def _normalize_bbox(bbox: list[float]) -> list[float] | None:
    try:
        left, top, right, bottom = [float(value) for value in bbox]
    except Exception:
        return None
    if right <= left or bottom <= top:
        return None
    return [left, top, right, bottom]


def _normalize_positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return int(value)


def _normalize_non_negative_int(value: Any) -> int | None:
    normalized = _normalize_positive_int(value)
    if normalized is None or normalized < 0:
        return None
    return normalized


def _ensure_text_layer_dirs(root: Path | str) -> Path:
    base = _ensure_dirs(root)
    (base / TEXT_LAYER_DIR).mkdir(parents=True, exist_ok=True)
    (base / OVERLAY_DIR).mkdir(parents=True, exist_ok=True)
    index_path = base / INDEX_DIR / TEXT_LAYER_INDEX
    if not index_path.exists():
        _atomic_write_json(index_path, {"entries": [], "updated_at_utc": _now()})
    return base


def _update_text_layer_index(root: Path) -> None:
    entries = []
    for path in sorted((root / TEXT_LAYER_DIR).glob("text_layer_*.json")):
        payload = _read_json(path)
        if not isinstance(payload, Mapping):
            continue
        entries.append(
            {
                "text_layer_id": payload.get("text_layer_id"),
                "viewport_id": payload.get("viewport_id"),
                "document_id": payload.get("document_id"),
                "source_revision": payload.get("source_revision"),
                "page_number": payload.get("page_number"),
                "word_count": len(payload.get("words", [])),
                "updated_at_utc": payload.get("updated_at_utc"),
            }
        )
    _atomic_write_json(root / INDEX_DIR / TEXT_LAYER_INDEX, {"entries": entries, "updated_at_utc": _now()})


def _sanitize(text: str) -> str:
    sanitized = str(text)
    for needle in ("C:\\", "/Users/", "pdf_sources", "pdf_viewport_cache", "pdf_text_layers", "pdf_overlay_cache", "token=", "secret", "Traceback"):
        sanitized = sanitized.replace(needle, "" if needle != "token=" else "[redacted]")
    return sanitized


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
