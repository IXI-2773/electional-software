from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .document_content_curation import _atomic_write_json
from .document_content_map import _normalize_topic
from .source_documents import SOURCE_DOCUMENT_ROOT

TAXONOMY_DIR = "topic_taxonomy"
TAXONOMY_INDEX = "topic_taxonomy_index.json"
SCHEMA_VERSION = "controlled_topic_v1"
ALLOWED_STATUSES = {"active", "deprecated", "review_required", "disabled"}
STATUS_ORDER = {"active": 0, "deprecated": 1, "review_required": 2, "disabled": 3}


def normalize_taxonomy_label(label: str) -> str:
    return _normalize_topic(label)


def save_controlled_topic(
    preferred_label: str,
    aliases: list[str] | None = None,
    parent_topic_ids: list[str] | None = None,
    related_topic_ids: list[str] | None = None,
    status: str = "active",
    replacement_topic_id: str | None = None,
    note: str | None = None,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = Path(root)
    _ensure_storage(base)
    normalized = normalize_taxonomy_label(preferred_label)
    if not normalized:
        return {"status": "invalid", "warnings": ["preferred_label_required"]}
    if status not in ALLOWED_STATUSES:
        return {"status": "invalid", "warnings": ["invalid_topic_status"]}
    topic_id = _topic_id_for_label(normalized)
    records = _load_all_topics(base)
    existing = records.get(topic_id)
    if existing and existing.get("normalized_preferred_label") != normalized:
        return {"status": "invalid", "warnings": ["topic_id_conflict"]}
    for other_id, other in records.items():
        if other_id != topic_id and other.get("normalized_preferred_label") == normalized:
            return {"status": "invalid", "warnings": ["duplicate_preferred_label"]}
    normalized_aliases = _normalize_label_list(aliases or [])
    if normalized in normalized_aliases:
        return {"status": "invalid", "warnings": ["alias_matches_preferred_label"]}
    parent_ids = _normalize_topic_id_list(parent_topic_ids or [])
    related_ids = _normalize_topic_id_list(related_topic_ids or [])
    if topic_id in parent_ids:
        return {"status": "invalid", "warnings": ["self_parent_rejected"]}
    if topic_id in related_ids:
        return {"status": "invalid", "warnings": ["self_related_rejected"]}
    if replacement_topic_id:
        replacement_topic_id = str(replacement_topic_id).strip()
        if replacement_topic_id == topic_id:
            return {"status": "invalid", "warnings": ["replacement_topic_self_reference"]}
    created_at = existing.get("created_at_utc") if isinstance(existing, dict) else _now()
    candidate = {
        "schema_version": SCHEMA_VERSION,
        "topic_id": topic_id,
        "preferred_label": normalized,
        "normalized_preferred_label": normalized,
        "aliases": normalized_aliases,
        "parent_topic_ids": parent_ids,
        "child_topic_ids": [],
        "related_topic_ids": related_ids,
        "status": status,
        "replacement_topic_id": replacement_topic_id or None,
        "note": str(note).strip() if note else None,
        "created_at_utc": created_at,
        "updated_at_utc": _now(),
        "warnings": [],
    }
    staged = {key: json.loads(json.dumps(value, sort_keys=True, default=str)) for key, value in records.items()}
    staged[topic_id] = candidate
    conflict = _validate_topic_save(staged, candidate)
    if conflict:
        return {"status": "invalid", "warnings": [conflict]}
    canonical = _canonicalize_topics(staged)
    validation = _validate_topics(canonical)
    if any(issue["severity"] == "critical" and issue.get("topic_id") == topic_id for issue in validation["issues"]):
        issue = next(issue for issue in validation["issues"] if issue["severity"] == "critical" and issue.get("topic_id") == topic_id)
        return {"status": "invalid", "warnings": [str(issue["issue_type"])]}
    for saved_id, payload in canonical.items():
        _atomic_write_json(_topic_path(base, saved_id), payload)
    _write_index(base, canonical)
    return {"status": "saved", "topic_id": topic_id, "topic": canonical[topic_id], "warnings": []}


def load_controlled_topic(topic_id: str, *, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    if not _safe_topic_id(topic_id):
        return {"topic_id": "topic_unknown", "status": "not_found", "topic": None, "warnings": ["invalid_topic_id"]}
    base = Path(root)
    payload = _read_json(_topic_path(base, topic_id))
    if not isinstance(payload, dict):
        return {"topic_id": "topic_unknown", "status": "not_found", "topic": None, "warnings": []}
    canonical = _canonicalize_topics({topic_id: payload, **_load_all_topics(base)})
    return {"topic_id": topic_id, "status": "found", "topic": canonical.get(topic_id), "warnings": []}


def list_controlled_topics(
    status: str | None = None,
    parent_topic_id: str | None = None,
    limit: int = 100,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    topics = list(_canonicalize_topics(_load_all_topics(Path(root))).values())
    if status:
        topics = [topic for topic in topics if topic.get("status") == status]
    if parent_topic_id:
        topics = [topic for topic in topics if parent_topic_id in topic.get("parent_topic_ids", [])]
    topics.sort(key=lambda topic: (STATUS_ORDER.get(str(topic.get("status")), 9), str(topic.get("normalized_preferred_label") or ""), str(topic.get("topic_id") or "")))
    bounded = topics[: max(0, int(limit or 0))]
    return {"status": "ok", "count": len(bounded), "items": bounded, "warnings": []}


def validate_topic_taxonomy(*, root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    records = _load_all_topics(Path(root))
    return _validate_topics(_canonicalize_topics(records))


def resolve_controlled_topic_label(
    label: str,
    include_deprecated: bool = False,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    normalized = normalize_taxonomy_label(label)
    topics = list(_canonicalize_topics(_load_all_topics(Path(root))).values())
    if not normalized:
        return _unresolved_resolution(label, normalized)
    for topic in topics:
        if topic.get("normalized_preferred_label") != normalized:
            continue
        if topic.get("status") == "deprecated" and not include_deprecated:
            continue
        return _resolution_payload(label, normalized, topic, "deprecated_preferred_label" if topic.get("status") == "deprecated" else "preferred_label")
    for topic in topics:
        if normalized not in topic.get("aliases", []):
            continue
        if topic.get("status") == "deprecated" and not include_deprecated:
            continue
        return _resolution_payload(label, normalized, topic, "deprecated_alias" if topic.get("status") == "deprecated" else "alias")
    return _unresolved_resolution(label, normalized)


def build_taxonomy_search_expansion(
    label: str,
    include_aliases: bool = True,
    include_children: bool = False,
    include_parents: bool = False,
    include_related: bool = False,
    include_replacement: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> dict[str, Any]:
    base = Path(root)
    resolution = resolve_controlled_topic_label(label, include_deprecated=True, root=base)
    if not resolution.get("resolved"):
        return {
            "input_label": label,
            "resolved_topic_id": None,
            "preferred_label": None,
            "search_labels": [],
            "included_topic_ids": [],
            "expansion": {"aliases": include_aliases, "parents": include_parents, "children": include_children, "related": include_related, "replacement": include_replacement},
            "warnings": resolution.get("warnings", []),
        }
    topics = _canonicalize_topics(_load_all_topics(base))
    topic = topics.get(resolution["topic_id"])
    search_labels: list[str] = []
    included_topic_ids: list[str] = []
    _append_label(search_labels, topic.get("preferred_label"))
    _append_topic(included_topic_ids, topic.get("topic_id"))
    if include_aliases:
        for alias in sorted(topic.get("aliases", [])):
            _append_label(search_labels, alias)
    if include_replacement and topic.get("status") == "deprecated" and topic.get("replacement_topic_id") in topics:
        replacement = topics[str(topic.get("replacement_topic_id"))]
        _append_label(search_labels, replacement.get("preferred_label"))
        _append_topic(included_topic_ids, replacement.get("topic_id"))
    for field, enabled in (("parent_topic_ids", include_parents), ("child_topic_ids", include_children), ("related_topic_ids", include_related)):
        if not enabled:
            continue
        for related in sorted(topic.get(field, []), key=lambda item: topics.get(item, {}).get("preferred_label", item)):
            linked = topics.get(related)
            if isinstance(linked, dict):
                _append_label(search_labels, linked.get("preferred_label"))
                _append_topic(included_topic_ids, linked.get("topic_id"))
    return {
        "input_label": label,
        "resolved_topic_id": topic.get("topic_id"),
        "preferred_label": topic.get("preferred_label"),
        "search_labels": search_labels,
        "included_topic_ids": included_topic_ids,
        "expansion": {"aliases": include_aliases, "parents": include_parents, "children": include_children, "related": include_related, "replacement": include_replacement},
        "warnings": resolution.get("warnings", []),
    }


def format_topic_taxonomy_report(
    topic_id: str | None = None,
    public_safe: bool = True,
    *,
    root: Path | str = SOURCE_DOCUMENT_ROOT,
) -> str:
    base = Path(root)
    topics = _canonicalize_topics(_load_all_topics(base))
    if topic_id:
        loaded = load_controlled_topic(topic_id, root=base)
        topic = loaded.get("topic")
        if not isinstance(topic, dict):
            return "Controlled Topic Report\n\nStatus: not_found"
        lines = [
            "Controlled Topic Report",
            "",
            f"Preferred Label: {topic.get('preferred_label', 'unknown')}",
            f"Topic ID: {topic.get('topic_id', 'unknown')}",
            f"Status: {topic.get('status', 'unknown')}",
            "",
            "Aliases:",
        ]
        lines.extend([f"- {alias}" for alias in topic.get("aliases", [])] or ["- none"])
        lines.extend(["", "Parent Topics:"])
        lines.extend(_relationship_lines(topic.get("parent_topic_ids", []), topics))
        lines.extend(["", "Child Topics:"])
        lines.extend(_relationship_lines(topic.get("child_topic_ids", []), topics))
        lines.extend(["", "Related Topics:"])
        lines.extend(_relationship_lines(topic.get("related_topic_ids", []), topics))
        if not public_safe:
            lines.extend(["", f"Note: {topic.get('note') or 'none'}"])
        return "\n".join(lines)
    health = _get_topic_taxonomy_health(base)
    return "\n".join(
        [
            "Topic Taxonomy Report",
            "",
            "Topics:",
            f"- Total: {health['total_topics']}",
            f"- Active: {health['active_topics']}",
            f"- Deprecated: {health['deprecated_topics']}",
            f"- Review Required: {health['review_required_topics']}",
            f"- Disabled: {health['disabled_topics']}",
            "",
            "Relationships:",
            f"- Aliases: {health['alias_count']}",
            f"- Parent Relationships: {health['parent_relationship_count']}",
            f"- Related Relationships: {health['related_relationship_count']}",
            "",
            "Validation:",
            f"- Status: {health['status']}",
            f"- Issue Count: {health['validation_issue_count']}",
            f"- Unresolved References: {health['unresolved_reference_count']}",
            f"- Duplicate Aliases: {health['duplicate_alias_count']}",
            f"- Cycles: {health['cycle_count']}",
            f"- Replacement Issues: {health['replacement_issue_count']}",
            "",
            "Recommended Action:",
            health["recommended_action"],
        ]
    )


def _get_topic_taxonomy_health(root: Path | str = SOURCE_DOCUMENT_ROOT) -> dict[str, Any]:
    topics = list(_canonicalize_topics(_load_all_topics(Path(root))).values())
    validation = validate_topic_taxonomy(root=root)
    issues = validation.get("issues", []) if isinstance(validation.get("issues"), list) else []
    return {
        "status": validation.get("status", "unknown"),
        "total_topics": len(topics),
        "active_topics": sum(1 for topic in topics if topic.get("status") == "active"),
        "deprecated_topics": sum(1 for topic in topics if topic.get("status") == "deprecated"),
        "review_required_topics": sum(1 for topic in topics if topic.get("status") == "review_required"),
        "disabled_topics": sum(1 for topic in topics if topic.get("status") == "disabled"),
        "alias_count": sum(len(topic.get("aliases", [])) for topic in topics),
        "parent_relationship_count": sum(len(topic.get("parent_topic_ids", [])) for topic in topics),
        "related_relationship_count": sum(len(topic.get("related_topic_ids", [])) for topic in topics),
        "unresolved_reference_count": sum(1 for issue in issues if "missing_" in str(issue.get("issue_type"))),
        "duplicate_alias_count": sum(1 for issue in issues if "alias" in str(issue.get("issue_type")) and "duplicate" in str(issue.get("issue_type"))),
        "cycle_count": sum(1 for issue in issues if "cycle" in str(issue.get("issue_type"))),
        "replacement_issue_count": sum(1 for issue in issues if "replacement" in str(issue.get("issue_type"))),
        "validation_issue_count": len(issues),
        "warnings": validation.get("warnings", []),
        "recommended_action": _recommended_action(issues),
    }


def _validate_topic_save(records: dict[str, dict[str, Any]], candidate: dict[str, Any]) -> str | None:
    topic_id = str(candidate.get("topic_id") or "")
    preferred = str(candidate.get("normalized_preferred_label") or "")
    aliases = set(candidate.get("aliases", []))
    status = candidate.get("status")
    replacement_topic_id = candidate.get("replacement_topic_id")
    if replacement_topic_id and replacement_topic_id not in records:
        return "replacement_topic_missing"
    if replacement_topic_id and records.get(str(replacement_topic_id), {}).get("status") != "active":
        return "replacement_topic_not_active"
    for ref in candidate.get("parent_topic_ids", []):
        if ref not in records:
            return "missing_parent_topic"
    for ref in candidate.get("related_topic_ids", []):
        if ref not in records:
            return "missing_related_topic"
    if status == "active":
        for other_id, other in records.items():
            if other_id == topic_id:
                continue
            other_aliases = set(other.get("aliases", []))
            if preferred in other_aliases:
                return "alias_conflict_rejected"
            if other.get("status") == "active" and aliases & ({str(other.get('normalized_preferred_label') or '')} | other_aliases):
                return "alias_conflict_rejected"
    if _graph_cycle_exists(records, "parent_topic_ids"):
        return "parent_cycle"
    if _replacement_cycle_exists(records):
        return "replacement_cycle"
    return None


def _validate_topics(records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {"status": "empty", "topics_checked": 0, "valid_topics": 0, "warning_topics": 0, "critical_topics": 0, "issues": [], "warnings": []}
    issues: list[dict[str, Any]] = []
    alias_owners: dict[str, list[str]] = {}
    preferred_owner: dict[str, str] = {}
    raw = _load_all_topics(SOURCE_DOCUMENT_ROOT) if False else None
    for topic_id, topic in records.items():
        if topic.get("schema_version") != SCHEMA_VERSION:
            issues.append(_issue("unsupported_schema_version", topic_id, None, "critical", "Rewrite the topic record with the current schema version."))
        if topic.get("status") not in ALLOWED_STATUSES:
            issues.append(_issue("invalid_topic_status", topic_id, None, "critical", "Set a supported topic status."))
        normalized = str(topic.get("normalized_preferred_label") or "")
        if normalized in preferred_owner and preferred_owner[normalized] != topic_id:
            issues.append(_issue("duplicate_preferred_label", topic_id, preferred_owner[normalized], "critical", "Use one preferred label per controlled topic."))
        preferred_owner[normalized] = topic_id
        if topic_id in topic.get("parent_topic_ids", []):
            issues.append(_issue("self_parent_relationship", topic_id, topic_id, "critical", "Remove the self-parent relationship."))
        if topic_id in topic.get("child_topic_ids", []):
            issues.append(_issue("self_child_relationship", topic_id, topic_id, "critical", "Remove the self-child relationship."))
        if topic_id in topic.get("related_topic_ids", []):
            issues.append(_issue("self_related_relationship", topic_id, topic_id, "critical", "Remove the self-related relationship."))
        for alias in topic.get("aliases", []):
            alias_owners.setdefault(alias, []).append(topic_id)
            if alias in preferred_owner and preferred_owner.get(alias) != topic_id:
                issues.append(_issue("alias_collides_with_preferred_label", topic_id, preferred_owner.get(alias), "critical", "Change the alias or the preferred label."))
        for parent_id in topic.get("parent_topic_ids", []):
            parent = records.get(parent_id)
            if not parent:
                issues.append(_issue("missing_parent_topic", topic_id, parent_id, "critical", "Point the parent relationship to an existing topic."))
            elif topic_id not in parent.get("child_topic_ids", []):
                issues.append(_issue("parent_child_mismatch", topic_id, parent_id, "warning", "Resave the topic records to restore parent/child reciprocity."))
        for child_id in topic.get("child_topic_ids", []):
            child = records.get(child_id)
            if not child:
                issues.append(_issue("missing_child_topic", topic_id, child_id, "critical", "Remove or repair the missing child relationship."))
            elif topic_id not in child.get("parent_topic_ids", []):
                issues.append(_issue("parent_child_mismatch", topic_id, child_id, "warning", "Resave the topic records to restore parent/child reciprocity."))
        explicit_related = set(_normalize_topic_id_list((_read_json(_topic_path(Path(root := SOURCE_DOCUMENT_ROOT), topic_id)) or {}).get("related_topic_ids", []))) if False else set(topic.get("related_topic_ids", []))
        for related_id in topic.get("related_topic_ids", []):
            related = records.get(related_id)
            if not related:
                issues.append(_issue("missing_related_topic", topic_id, related_id, "critical", "Point the related-topic relationship to an existing topic."))
            elif topic_id not in related.get("related_topic_ids", []):
                issues.append(_issue("related_topic_asymmetry", topic_id, related_id, "warning", "Resave one topic record to restore symmetric related topics."))
        replacement_id = topic.get("replacement_topic_id")
        if topic.get("status") == "deprecated":
            if replacement_id and replacement_id not in records:
                issues.append(_issue("deprecated_topic_replacement_missing", topic_id, replacement_id, "critical", "Point the deprecated topic to an existing replacement topic."))
            if replacement_id == topic_id:
                issues.append(_issue("deprecated_topic_replacement_self", topic_id, replacement_id, "critical", "Choose a different replacement topic."))
    for alias, owners in alias_owners.items():
        active_owners = [owner for owner in owners if records.get(owner, {}).get("status") == "active"]
        if len(active_owners) > 1:
            issues.append(_issue("duplicate_active_alias", active_owners[0], active_owners[1], "critical", "Keep each alias on one active topic only."))
    if _graph_cycle_exists(records, "parent_topic_ids"):
        for topic_id in sorted(records):
            issues.append(_issue("parent_cycle", topic_id, None, "critical", "Remove one parent relationship."))
            break
    if _replacement_cycle_exists(records):
        for topic_id in sorted(records):
            issues.append(_issue("replacement_cycle", topic_id, None, "critical", "Break the deprecated replacement cycle."))
            break
    status = "healthy"
    if issues:
        status = "critical" if any(issue["severity"] == "critical" for issue in issues) else "warning"
    critical_topics = len({issue["topic_id"] for issue in issues if issue["severity"] == "critical"})
    warning_topics = len({issue["topic_id"] for issue in issues if issue["severity"] != "critical"})
    return {
        "status": status,
        "topics_checked": len(records),
        "valid_topics": max(0, len(records) - len({issue["topic_id"] for issue in issues})),
        "warning_topics": warning_topics,
        "critical_topics": critical_topics,
        "issues": sorted(issues, key=lambda issue: (issue["severity"] != "critical", str(issue["issue_type"]), str(issue["topic_id"]), str(issue.get("related_topic_id") or ""))),
        "warnings": [],
    }


def _canonicalize_topics(records: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    canonical: dict[str, dict[str, Any]] = {}
    for topic_id, topic in records.items():
        canonical[topic_id] = {
            "schema_version": topic.get("schema_version", SCHEMA_VERSION),
            "topic_id": topic_id,
            "preferred_label": normalize_taxonomy_label(topic.get("preferred_label", "")),
            "normalized_preferred_label": normalize_taxonomy_label(topic.get("normalized_preferred_label", "") or topic.get("preferred_label", "")),
            "aliases": _normalize_label_list(topic.get("aliases", [])),
            "parent_topic_ids": _normalize_topic_id_list(topic.get("parent_topic_ids", [])),
            "child_topic_ids": [],
            "related_topic_ids": _normalize_topic_id_list(topic.get("related_topic_ids", [])),
            "status": topic.get("status", "review_required"),
            "replacement_topic_id": str(topic.get("replacement_topic_id")).strip() if topic.get("replacement_topic_id") else None,
            "note": str(topic.get("note")).strip() if topic.get("note") else None,
            "created_at_utc": topic.get("created_at_utc") or _now(),
            "updated_at_utc": topic.get("updated_at_utc") or topic.get("created_at_utc") or _now(),
            "warnings": topic.get("warnings", []) if isinstance(topic.get("warnings"), list) else [],
        }
    for topic_id, topic in canonical.items():
        for parent_id in topic.get("parent_topic_ids", []):
            if parent_id in canonical and topic_id not in canonical[parent_id]["child_topic_ids"]:
                canonical[parent_id]["child_topic_ids"].append(topic_id)
        for related_id in list(topic.get("related_topic_ids", [])):
            if related_id in canonical and topic_id not in canonical[related_id]["related_topic_ids"]:
                canonical[related_id]["related_topic_ids"].append(topic_id)
    for topic in canonical.values():
        topic["child_topic_ids"] = sorted(set(topic.get("child_topic_ids", [])))
        topic["related_topic_ids"] = sorted(set(topic.get("related_topic_ids", [])))
    return canonical


def _write_index(root: Path, records: dict[str, dict[str, Any]]) -> None:
    entries = [
        {
            "topic_id": topic.get("topic_id"),
            "preferred_label": topic.get("preferred_label"),
            "normalized_preferred_label": topic.get("normalized_preferred_label"),
            "status": topic.get("status"),
            "alias_count": len(topic.get("aliases", [])),
            "parent_count": len(topic.get("parent_topic_ids", [])),
            "child_count": len(topic.get("child_topic_ids", [])),
            "related_count": len(topic.get("related_topic_ids", [])),
            "updated_at_utc": topic.get("updated_at_utc"),
        }
        for topic in records.values()
    ]
    entries.sort(key=lambda item: (STATUS_ORDER.get(str(item.get("status")), 9), str(item.get("normalized_preferred_label") or ""), str(item.get("topic_id") or "")))
    _atomic_write_json(root / "indexes" / TAXONOMY_INDEX, {"entries": entries, "updated_at_utc": _now()})


def _load_all_topics(root: Path) -> dict[str, dict[str, Any]]:
    directory = root / TAXONOMY_DIR
    if not directory.exists():
        return {}
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict) and _safe_topic_id(payload.get("topic_id")):
            records[str(payload["topic_id"])] = payload
    return records


def _relationship_lines(topic_ids: list[str], records: dict[str, dict[str, Any]]) -> list[str]:
    if not topic_ids:
        return ["- none"]
    return [f"- {records.get(topic_id, {}).get('preferred_label', topic_id)}" for topic_id in sorted(topic_ids, key=lambda item: records.get(item, {}).get("preferred_label", item))]


def _resolution_payload(input_label: str, normalized: str, topic: dict[str, Any], resolution_type: str) -> dict[str, Any]:
    warnings = ["deprecated_topic"] if topic.get("status") == "deprecated" else []
    return {
        "input_label": input_label,
        "normalized_label": normalized,
        "resolved": True,
        "resolution_type": resolution_type,
        "topic_id": topic.get("topic_id"),
        "preferred_label": topic.get("preferred_label"),
        "status": topic.get("status"),
        "replacement_topic_id": topic.get("replacement_topic_id"),
        "warnings": warnings,
    }


def _unresolved_resolution(input_label: str, normalized: str) -> dict[str, Any]:
    return {
        "input_label": input_label,
        "normalized_label": normalized,
        "resolved": False,
        "resolution_type": "unresolved",
        "topic_id": None,
        "preferred_label": None,
        "status": "unresolved",
        "replacement_topic_id": None,
        "warnings": ["controlled_topic_not_found"],
    }


def _recommended_action(issues: list[dict[str, Any]]) -> str:
    if not issues:
        return "No action required."
    first = issues[0]
    return str(first.get("recommended_action") or "Resolve taxonomy validation issues.")


def _append_label(labels: list[str], value: object) -> None:
    normalized = normalize_taxonomy_label(str(value or ""))
    if value and normalized and normalized not in {normalize_taxonomy_label(item) for item in labels}:
        labels.append(str(value))


def _append_topic(topic_ids: list[str], value: object) -> None:
    text = str(value or "").strip()
    if text and text not in topic_ids:
        topic_ids.append(text)


def _graph_cycle_exists(records: dict[str, dict[str, Any]], field: str) -> bool:
    visited: set[str] = set()
    active: set[str] = set()

    def visit(topic_id: str) -> bool:
        if topic_id in active:
            return True
        if topic_id in visited:
            return False
        visited.add(topic_id)
        active.add(topic_id)
        for next_id in records.get(topic_id, {}).get(field, []):
            if next_id in records and visit(next_id):
                return True
        active.remove(topic_id)
        return False

    return any(visit(topic_id) for topic_id in sorted(records))


def _replacement_cycle_exists(records: dict[str, dict[str, Any]]) -> bool:
    graph = {topic_id: [str(topic.get("replacement_topic_id"))] for topic_id, topic in records.items() if topic.get("replacement_topic_id")}
    return _graph_cycle_exists({topic_id: {"parent_topic_ids": edges} for topic_id, edges in graph.items()}, "parent_topic_ids")


def _normalize_label_list(values: list[object]) -> list[str]:
    return sorted({label for label in (normalize_taxonomy_label(value) for value in values if isinstance(values, list)) if label})


def _normalize_topic_id_list(values: list[object]) -> list[str]:
    items = []
    for value in values if isinstance(values, list) else []:
        text = str(value or "").strip()
        if _safe_topic_id(text):
            items.append(text)
    return sorted(set(items))


def _topic_id_for_label(normalized_label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", normalized_label).strip("_")
    return f"topic_{slug}" if slug else "topic_unknown"


def _topic_path(root: Path, topic_id: object) -> Path:
    return root / TAXONOMY_DIR / f"{topic_id}.json"


def _ensure_storage(root: Path) -> None:
    (root / TAXONOMY_DIR).mkdir(parents=True, exist_ok=True)
    index_path = root / "indexes" / TAXONOMY_INDEX
    if not index_path.exists():
        _atomic_write_json(index_path, {"entries": [], "updated_at_utc": _now()})


def _safe_topic_id(value: object) -> bool:
    text = str(value or "").strip()
    return bool(text) and bool(re.fullmatch(r"topic_[a-z0-9_]+", text))


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _issue(issue_type: str, topic_id: str, related_topic_id: str | None, severity: str, recommended_action: str) -> dict[str, Any]:
    return {
        "issue_type": issue_type,
        "topic_id": topic_id,
        "related_topic_id": related_topic_id,
        "severity": severity,
        "recommended_action": recommended_action,
    }


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
