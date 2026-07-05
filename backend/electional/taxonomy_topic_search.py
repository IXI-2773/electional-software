from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .source_documents import SOURCE_DOCUMENT_ROOT
from .topic_taxonomy import (
    build_taxonomy_search_expansion,
    list_controlled_topics,
    load_controlled_topic,
    normalize_taxonomy_label,
    resolve_controlled_topic_label,
    validate_topic_taxonomy,
)

PLAN_SCHEMA_VERSION = "taxonomy_topic_search_plan_v1"


def resolve_taxonomy_search_query(
    label: str,
    include_deprecated: bool = False,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    resolved = resolve_controlled_topic_label(label, include_deprecated=include_deprecated, root=root)
    return {
        "input_label": resolved.get("input_label", label),
        "normalized_label": resolved.get("normalized_label", normalize_taxonomy_label(label)),
        "resolved": bool(resolved.get("resolved")),
        "resolution_type": resolved.get("resolution_type", "unresolved"),
        "topic_id": resolved.get("topic_id"),
        "preferred_label": resolved.get("preferred_label"),
        "topic_status": resolved.get("status"),
        "replacement_topic_id": resolved.get("replacement_topic_id"),
        "warnings": list(resolved.get("warnings", [])) if isinstance(resolved.get("warnings"), list) else [],
    }


def build_taxonomy_topic_search_plan(
    label: str,
    include_aliases: bool = True,
    include_children: bool = False,
    include_parents: bool = False,
    include_related: bool = False,
    include_replacement: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    resolution = resolve_taxonomy_search_query(label, include_deprecated=True, root=root)
    if not resolution.get("resolved"):
        return {
            "schema_version": PLAN_SCHEMA_VERSION,
            "input_label": label,
            "resolved_topic_id": None,
            "preferred_label": None,
            "search_labels": [],
            "options": _plan_options(include_aliases, include_children, include_parents, include_related, include_replacement),
            "warnings": resolution.get("warnings", []),
        }
    plan = build_taxonomy_search_expansion(
        label,
        include_aliases=include_aliases,
        include_children=include_children,
        include_parents=include_parents,
        include_related=include_related,
        include_replacement=include_replacement,
        root=root,
    )
    topic = load_controlled_topic(str(resolution["topic_id"]), root=root).get("topic") or {}
    topics = _topic_lookup(root)
    search_labels: list[dict[str, Any]] = []
    _append_plan_label(search_labels, topic.get("preferred_label"), "preferred_label", str(topic.get("topic_id") or ""), 0)
    if include_aliases:
        for alias in sorted(topic.get("aliases", [])):
            _append_plan_label(search_labels, alias, "alias", str(topic.get("topic_id") or ""), 1)
    replacement_id = topic.get("replacement_topic_id")
    if include_replacement and topic.get("status") == "deprecated" and replacement_id in topics:
        replacement = topics[str(replacement_id)]
        _append_plan_label(search_labels, replacement.get("preferred_label"), "replacement", str(replacement.get("topic_id") or ""), 1)
    if include_parents:
        for related_id in sorted(topic.get("parent_topic_ids", []), key=lambda item: topics.get(item, {}).get("preferred_label", item)):
            _append_plan_label(search_labels, topics.get(related_id, {}).get("preferred_label"), "parent", related_id, 2)
    if include_children:
        for related_id in sorted(topic.get("child_topic_ids", []), key=lambda item: topics.get(item, {}).get("preferred_label", item)):
            _append_plan_label(search_labels, topics.get(related_id, {}).get("preferred_label"), "child", related_id, 2)
    if include_related:
        for related_id in sorted(topic.get("related_topic_ids", []), key=lambda item: topics.get(item, {}).get("preferred_label", item)):
            _append_plan_label(search_labels, topics.get(related_id, {}).get("preferred_label"), "related", related_id, 2)
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "input_label": label,
        "resolved_topic_id": resolution.get("topic_id"),
        "preferred_label": resolution.get("preferred_label"),
        "search_labels": search_labels,
        "options": _plan_options(include_aliases, include_children, include_parents, include_related, include_replacement),
        "warnings": list(plan.get("warnings", [])) if isinstance(plan.get("warnings"), list) else [],
    }


def search_taxonomy_aware_topic_content(
    label: str,
    limit: int = 100,
    include_aliases: bool = True,
    include_children: bool = False,
    include_parents: bool = False,
    include_related: bool = False,
    include_replacement: bool = True,
    include_warning_documents: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    health = get_taxonomy_topic_search_health(root=root)
    resolution = resolve_taxonomy_search_query(label, include_deprecated=True, root=root)
    plan = build_taxonomy_topic_search_plan(
        label,
        include_aliases=include_aliases,
        include_children=include_children,
        include_parents=include_parents,
        include_related=include_related,
        include_replacement=include_replacement,
        root=root,
    )
    if not resolution.get("resolved"):
        return {
            "status": "unresolved",
            "resolution": resolution,
            "plan": plan,
            "results": [],
            "grouped_results": [],
            "documents_matched": 0,
            "structural_match_count": 0,
            "direct_match_count": 0,
            "expanded_match_count": 0,
            "warnings": resolution.get("warnings", []),
            "blockers": [],
            "health": health,
            "recommended_action": "Create or update a controlled topic before searching.",
        }
    if health.get("status") in {"blocked", "critical"}:
        return {
            "status": "blocked",
            "resolution": resolution,
            "plan": plan,
            "results": [],
            "grouped_results": [],
            "documents_matched": 0,
            "structural_match_count": 0,
            "direct_match_count": 0,
            "expanded_match_count": 0,
            "warnings": list(health.get("warnings", [])),
            "blockers": list(health.get("blockers", [])),
            "health": health,
            "recommended_action": health.get("recommended_action"),
        }
    topic_index = _load_cross_document_topic_index(root)
    topics = topic_index.get("topics", {}) if isinstance(topic_index.get("topics"), dict) else {}
    combined: list[dict[str, Any]] = []
    for search_label in plan.get("search_labels", []):
        normalized_label = str(search_label.get("normalized_label") or "")
        matches = topics.get(normalized_label, [])
        if not isinstance(matches, list):
            continue
        for raw in matches:
            if not isinstance(raw, dict):
                continue
            entry = json.loads(json.dumps(raw, sort_keys=True, default=str))
            entry["matched_search_labels"] = [str(search_label.get("label") or normalized_label)]
            entry["match_provenance"] = [
                {
                    "search_label": str(search_label.get("label") or normalized_label),
                    "source_type": str(search_label.get("source_type") or "unknown"),
                    "source_topic_id": search_label.get("source_topic_id"),
                    "expansion_distance": int(search_label.get("expansion_distance") or 0),
                    "phase_8r_match_reason": entry.get("match_reason", "unknown"),
                    "phase_8r_match_rank": _phase8r_rank(entry.get("match_reason")),
                }
            ]
            entry["direct_match"] = str(search_label.get("source_type")) == "preferred_label" and int(search_label.get("expansion_distance") or 0) == 0
            entry["minimum_expansion_distance"] = int(search_label.get("expansion_distance") or 0)
            entry["best_phase_8r_match_rank"] = _phase8r_rank(entry.get("match_reason"))
            entry["combined_rank_class"] = _combined_rank_class(str(search_label.get("source_type") or "unknown"), str(entry.get("match_reason") or "unknown"))
            combined.append(entry)
    deduped = deduplicate_taxonomy_topic_results(combined)
    ordered = _sort_results(deduped)
    if not include_warning_documents:
        ordered = [item for item in ordered if not item.get("warnings")]
    ordered = ordered[: max(0, int(limit or 0))]
    grouped = group_taxonomy_topic_results(ordered)
    return {
        "status": "ok",
        "resolution": resolution,
        "plan": plan,
        "results": ordered,
        "grouped_results": grouped,
        "documents_matched": len({str(item.get("document_id") or "") for item in ordered}),
        "structural_match_count": len(ordered),
        "direct_match_count": sum(1 for item in ordered if item.get("direct_match")),
        "expanded_match_count": sum(1 for item in ordered if not item.get("direct_match")),
        "warnings": _search_warnings(ordered, health),
        "blockers": [],
        "health": health,
        "recommended_action": _search_recommended_action(ordered, health),
    }


def deduplicate_taxonomy_topic_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for result in results:
        if not isinstance(result, dict):
            continue
        key = _structural_identity(result)
        current = merged.get(key)
        if current is None:
            payload = json.loads(json.dumps(result, sort_keys=True, default=str))
            payload["matched_search_labels"] = sorted(set(payload.get("matched_search_labels", [])))
            payload["match_provenance"] = _sorted_provenance(payload.get("match_provenance", []))
            payload["matched_tags"] = sorted(set(payload.get("matched_tags", []))) if isinstance(payload.get("matched_tags"), list) else []
            merged[key] = payload
            continue
        current["matched_search_labels"] = sorted(set(current.get("matched_search_labels", [])) | set(result.get("matched_search_labels", [])))
        current["matched_tags"] = sorted(set(current.get("matched_tags", [])) | set(result.get("matched_tags", []))) if isinstance(current.get("matched_tags"), list) else sorted(set(result.get("matched_tags", [])))
        current["match_provenance"] = _sorted_provenance(list(current.get("match_provenance", [])) + list(result.get("match_provenance", [])))
        current["direct_match"] = bool(current.get("direct_match")) or bool(result.get("direct_match"))
        current["minimum_expansion_distance"] = min(int(current.get("minimum_expansion_distance", 99)), int(result.get("minimum_expansion_distance", 99)))
        current["best_phase_8r_match_rank"] = min(int(current.get("best_phase_8r_match_rank", 99)), int(result.get("best_phase_8r_match_rank", 99)))
        current["combined_rank_class"] = min(int(current.get("combined_rank_class", 99)), int(result.get("combined_rank_class", 99)))
        current["warnings"] = sorted(set(current.get("warnings", [])) | set(result.get("warnings", []))) if isinstance(current.get("warnings"), list) else sorted(set(result.get("warnings", [])))
    return list(merged.values())


def group_taxonomy_topic_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    documents: dict[str, dict[str, Any]] = {}
    for result in results:
        document_id = str(result.get("document_id") or "unknown")
        document = documents.setdefault(
            document_id,
            {
                "document_id": document_id,
                "document_title": result.get("document_title") or document_id,
                "map_source": result.get("map_source", "unknown"),
                "reader_backend_readiness": result.get("reader_backend_readiness", "unknown"),
                "match_count": 0,
                "direct_match_count": 0,
                "expanded_match_count": 0,
                "chapters": [],
                "warnings": sorted(set(result.get("warnings", []))) if isinstance(result.get("warnings"), list) else [],
            },
        )
        document["match_count"] += 1
        document["direct_match_count"] += 1 if result.get("direct_match") else 0
        document["expanded_match_count"] += 0 if result.get("direct_match") else 1
        chapter_id = str(result.get("chapter_id") or "chapter_unknown")
        chapter = next((item for item in document["chapters"] if item.get("chapter_id") == chapter_id), None)
        if chapter is None:
            chapter = {
                "chapter_id": result.get("chapter_id"),
                "chapter_title": result.get("chapter_title"),
                "chapter_number": result.get("chapter_number"),
                "chapter_start_page": result.get("chapter_start_page"),
                "match_count": 0,
                "sections": [],
            }
            document["chapters"].append(chapter)
        chapter["match_count"] += 1
        section_id = str(result.get("section_id") or "section_unknown")
        if not any(item.get("section_id") == section_id for item in chapter["sections"]):
            chapter["sections"].append(
                {
                    "section_id": result.get("section_id"),
                    "section_title": result.get("section_title"),
                    "page_start": result.get("page_start"),
                    "page_end": result.get("page_end"),
                    "chunk_ids": sorted(result.get("chunk_ids", [])) if isinstance(result.get("chunk_ids"), list) else [],
                    "matched_search_labels": result.get("matched_search_labels", []),
                    "minimum_expansion_distance": result.get("minimum_expansion_distance"),
                    "direct_match": result.get("direct_match", False),
                }
            )
    grouped = list(documents.values())
    for document in grouped:
        document["chapters"].sort(key=lambda item: (_safe_int(item.get("chapter_number"), 10**9), _safe_int(item.get("chapter_start_page"), 10**9), str(item.get("chapter_title") or "")))
        for chapter in document["chapters"]:
            chapter["sections"].sort(key=lambda item: (_safe_int(item.get("page_start"), 10**9), str(item.get("section_title") or ""), str(item.get("section_id") or "")))
    grouped.sort(key=lambda item: (str(item.get("document_title") or "").lower(), str(item.get("document_id") or "")))
    return grouped


def get_taxonomy_topic_search_health(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    taxonomy = validate_topic_taxonomy(root=root)
    topic_index = _load_cross_document_topic_index(root)
    stale = bool(topic_index.get("stale")) or str(topic_index.get("status") or "") == "stale"
    available = bool(topic_index.get("available"))
    critical_count = sum(1 for issue in taxonomy.get("issues", []) if issue.get("severity") == "critical") if isinstance(taxonomy.get("issues"), list) else 0
    unresolved_count = sum(1 for issue in taxonomy.get("issues", []) if "missing_" in str(issue.get("issue_type"))) if isinstance(taxonomy.get("issues"), list) else 0
    warnings: list[str] = []
    blockers: list[str] = []
    if not available:
        blockers.append("cross_document_topic_index_missing")
    if critical_count:
        blockers.append("taxonomy_validation_critical")
    if stale:
        warnings.append("cross_document_topic_index_stale")
    status = "healthy"
    if taxonomy.get("status") == "empty":
        status = "empty"
    if warnings:
        status = "warning"
    if blockers:
        status = "blocked"
    if critical_count:
        status = "critical" if available else "blocked"
    return {
        "status": status,
        "taxonomy_status": taxonomy.get("status", "unknown"),
        "topic_index_status": topic_index.get("status", "missing" if not available else "unknown"),
        "topic_index_available": available,
        "critical_taxonomy_issue_count": critical_count,
        "unresolved_reference_count": unresolved_count,
        "stale_topic_index": stale,
        "warnings": warnings,
        "blockers": blockers,
        "recommended_action": _health_recommended_action(status, blockers, warnings),
    }


def format_taxonomy_topic_search_report(
    label: str,
    public_safe: bool = True,
    **search_options: Any,
) -> str:
    result = search_taxonomy_aware_topic_content(label, **search_options)
    resolution = result.get("resolution", {})
    plan = result.get("plan", {})
    lines = [
        "Taxonomy-Aware Topic Search Report",
        "",
        f"Query: {label}",
        f"Resolved Topic: {resolution.get('preferred_label') or 'unresolved'}",
        f"Resolution Type: {resolution.get('resolution_type', 'unresolved')}",
        "",
        "Expansion:",
        f"- Preferred Label: {plan.get('preferred_label') or 'none'}",
        f"- Aliases Included: {'Yes' if (plan.get('options') or {}).get('aliases') else 'No'}",
        f"- Parents Included: {'Yes' if (plan.get('options') or {}).get('parents') else 'No'}",
        f"- Children Included: {'Yes' if (plan.get('options') or {}).get('children') else 'No'}",
        f"- Related Topics Included: {'Yes' if (plan.get('options') or {}).get('related') else 'No'}",
        "",
        "Results:",
        f"- Documents Matched: {result.get('documents_matched', 0)}",
        f"- Structural Matches: {result.get('structural_match_count', 0)}",
        f"- Direct Matches: {result.get('direct_match_count', 0)}",
        f"- Expanded Matches: {result.get('expanded_match_count', 0)}",
        "",
        "Documents:",
    ]
    grouped = result.get("grouped_results", []) if isinstance(result.get("grouped_results"), list) else []
    if not grouped:
        lines.append("- none")
    for document in grouped:
        lines.append(f"- {document.get('document_title', document.get('document_id', 'unknown'))}")
        for chapter in document.get("chapters", []):
            lines.append(f"  - {chapter.get('chapter_title') or chapter.get('chapter_id') or 'Unknown Chapter'}")
            for section in chapter.get("sections", []):
                source = "preferred label" if section.get("direct_match") else "expanded label"
                lines.append(
                    f"    - {section.get('section_title') or section.get('section_id') or 'Unknown Section'}: "
                    f"pages {section.get('page_start', '?')}-{section.get('page_end', '?')} | Match Source: {source}"
                )
    lines.extend(["", "Warnings:"])
    lines.extend([f"- {warning}" for warning in result.get("warnings", [])] or ["- none"])
    lines.extend(["", "Recommended Action:", str(result.get("recommended_action") or "No action required.")])
    if not public_safe:
        lines.extend(["", f"Health: {json.dumps(result.get('health', {}), sort_keys=True, default=str)}"])
    return "\n".join(lines)


def get_taxonomy_topic_search_summary(
    label: str,
    limit: int = 50,
    include_aliases: bool = True,
    include_children: bool = False,
    include_parents: bool = False,
    include_related: bool = False,
    include_replacement: bool = True,
    include_warning_documents: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    result = search_taxonomy_aware_topic_content(
        label,
        limit=limit,
        include_aliases=include_aliases,
        include_children=include_children,
        include_parents=include_parents,
        include_related=include_related,
        include_replacement=include_replacement,
        include_warning_documents=include_warning_documents,
        root=root,
    )
    return {
        "input_query": label,
        "resolved_topic_id": (result.get("resolution") or {}).get("topic_id"),
        "preferred_label": (result.get("resolution") or {}).get("preferred_label"),
        "resolution_type": (result.get("resolution") or {}).get("resolution_type"),
        "expansion_label_count": len((result.get("plan") or {}).get("search_labels", [])) if isinstance((result.get("plan") or {}).get("search_labels"), list) else 0,
        "documents_matched": result.get("documents_matched", 0),
        "structural_match_count": result.get("structural_match_count", 0),
        "direct_match_count": result.get("direct_match_count", 0),
        "expanded_match_count": result.get("expanded_match_count", 0),
        "topic_index_status": (result.get("health") or {}).get("topic_index_status", "unknown"),
        "taxonomy_status": (result.get("health") or {}).get("taxonomy_status", "unknown"),
        "search_health": (result.get("health") or {}).get("status", "unknown"),
        "recommended_action": result.get("recommended_action"),
        "status": result.get("status"),
    }


def _topic_lookup(root: Path | str) -> dict[str, dict[str, Any]]:
    listing = list_controlled_topics(limit=10_000, root=root)
    return {str(item.get("topic_id")): item for item in listing.get("items", []) if isinstance(item, dict) and item.get("topic_id")}


def _append_plan_label(
    search_labels: list[dict[str, Any]],
    label: object,
    source_type: str,
    source_topic_id: str,
    expansion_distance: int,
) -> None:
    text = str(label or "").strip()
    normalized = normalize_taxonomy_label(text)
    if not normalized:
        return
    for existing in search_labels:
        if existing.get("normalized_label") != normalized:
            continue
        if int(existing.get("expansion_distance", 99)) > expansion_distance:
            existing["label"] = text
            existing["source_type"] = source_type
            existing["source_topic_id"] = source_topic_id
            existing["expansion_distance"] = expansion_distance
        return
    search_labels.append(
        {
            "label": text,
            "normalized_label": normalized,
            "source_type": source_type,
            "source_topic_id": source_topic_id,
            "expansion_distance": expansion_distance,
        }
    )
    search_labels.sort(key=lambda item: (int(item.get("expansion_distance", 99)), _source_type_order(str(item.get("source_type") or "")), str(item.get("label") or "")))


def _plan_options(include_aliases: bool, include_children: bool, include_parents: bool, include_related: bool, include_replacement: bool) -> dict[str, bool]:
    return {
        "aliases": include_aliases,
        "parents": include_parents,
        "children": include_children,
        "related": include_related,
        "replacement": include_replacement,
    }


def _load_cross_document_topic_index(root: Path | str) -> dict[str, Any]:
    base = Path(root)
    index_meta_path = base / "indexes" / "cross_document_topic_index.json"
    if not index_meta_path.exists():
        return {"available": False, "status": "missing", "topics": {}}
    meta = _read_json(index_meta_path) or {}
    topics = meta.get("topics")
    if isinstance(topics, dict):
        return {"available": True, "status": meta.get("status", "healthy"), "stale": bool(meta.get("stale")), "topics": topics}
    index_file = str(meta.get("index_file") or "").strip()
    if index_file:
        payload = _read_json(base / "cross_document_topic_indexes" / index_file) or {}
        if isinstance(payload.get("topics"), dict):
            return {"available": True, "status": meta.get("status", payload.get("status", "healthy")), "stale": bool(meta.get("stale") or payload.get("stale")), "topics": payload["topics"]}
    return {"available": False, "status": "missing", "topics": {}}


def _structural_identity(result: dict[str, Any]) -> str:
    payload = {
        "document_id": result.get("document_id"),
        "chapter_id": result.get("chapter_id"),
        "section_id": result.get("section_id"),
        "page_start": result.get("page_start"),
        "page_end": result.get("page_end"),
        "chunk_ids": sorted(result.get("chunk_ids", [])) if isinstance(result.get("chunk_ids"), list) else [],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sorted_provenance(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dedup: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        key = json.dumps(item, sort_keys=True, separators=(",", ":"), default=str)
        dedup[key] = item
    return sorted(
        dedup.values(),
        key=lambda item: (
            int(item.get("expansion_distance", 99)),
            _source_type_order(str(item.get("source_type") or "")),
            int(item.get("phase_8r_match_rank", 99)),
            str(item.get("search_label") or ""),
        ),
    )


def _sort_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        results,
        key=lambda item: (
            int(item.get("combined_rank_class", 99)),
            int(item.get("minimum_expansion_distance", 99)),
            int(item.get("best_phase_8r_match_rank", 99)),
            0 if str(item.get("reader_backend_readiness") or "").startswith("ready") else 1,
            0 if item.get("map_source") == "curated" else 1,
            str(item.get("document_title") or "").lower(),
            str(item.get("document_id") or ""),
            _safe_int(item.get("chapter_number"), 10**9),
            _safe_int(item.get("chapter_start_page"), 10**9),
            _safe_int(item.get("section_order"), 10**9),
            _safe_int(item.get("page_start"), 10**9),
            _safe_int((item.get("chunk_ids") or [10**9])[0] if isinstance(item.get("chunk_ids"), list) and item.get("chunk_ids") else 10**9, 10**9),
        ),
    )


def _combined_rank_class(source_type: str, match_reason: str) -> int:
    if source_type == "preferred_label":
        return 1 if match_reason == "exact_topic_tag" else 2
    return {
        "alias": 3,
        "replacement": 4,
        "parent": 5,
        "child": 6,
        "related": 7,
    }.get(source_type, 9)


def _phase8r_rank(reason: object) -> int:
    return {"exact_topic_tag": 1, "exact_section_title": 2, "exact_chapter_title": 3, "whole_word_keyword": 4}.get(str(reason or ""), 9)


def _source_type_order(source_type: str) -> int:
    return {"preferred_label": 0, "alias": 1, "replacement": 2, "parent": 3, "child": 4, "related": 5}.get(source_type, 9)


def _safe_int(value: object, default: int) -> int:
    try:
        if isinstance(value, bool):
            return default
        return int(value)
    except Exception:
        return default


def _search_warnings(results: list[dict[str, Any]], health: dict[str, Any]) -> list[str]:
    warnings = set(health.get("warnings", []))
    if any(item.get("map_source") != "curated" for item in results):
        warnings.add("detected_map_fallback_used")
    return sorted(warnings)


def _search_recommended_action(results: list[dict[str, Any]], health: dict[str, Any]) -> str:
    if health.get("blockers"):
        return str(health.get("recommended_action") or "Resolve blocked dependencies.")
    if any(item.get("map_source") != "curated" for item in results):
        return "Review the warning document before relying on all expanded results."
    return "No action required."


def _health_recommended_action(status: str, blockers: list[str], warnings: list[str]) -> str:
    if "cross_document_topic_index_missing" in blockers:
        return "Build the Phase 8R topic index before searching."
    if "taxonomy_validation_critical" in blockers:
        return "Resolve critical taxonomy validation issues before searching."
    if "cross_document_topic_index_stale" in warnings:
        return "Rebuild the Phase 8R topic index before relying on complete results."
    if status == "empty":
        return "Create a controlled topic before searching."
    return "No action required."


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None
