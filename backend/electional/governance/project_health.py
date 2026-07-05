from __future__ import annotations

from typing import Mapping

from ..reliability.health import check_storage_health
from ..source_knowledge import get_source_knowledge_health
from .dependencies import validate_dependencies
from .docs_coverage import get_docs_coverage
from .performance_budget import get_performance_budget_status
from .roadmap_registry import summarize_roadmap_status


def get_project_health(
    *,
    storage_health: Mapping[str, object] | None = None,
    knowledge_health: Mapping[str, object] | None = None,
    review_items: list[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    storage = dict(storage_health or check_storage_health())
    knowledge_obj = get_source_knowledge_health()
    knowledge = dict(knowledge_health or knowledge_obj.to_json())
    dependencies = validate_dependencies()
    docs = get_docs_coverage()
    performance = get_performance_budget_status()
    roadmap = summarize_roadmap_status()
    critical_issues: list[str] = []
    warnings: list[str] = []
    if storage.get("status") == "critical":
        critical_issues.append("storage_health_critical")
    if knowledge.get("status") == "critical":
        critical_issues.append("source_knowledge_critical")
    if dependencies.get("status") == "blocked":
        critical_issues.append("critical_dependency_missing")
    for item in review_items or []:
        if item.get("severity") == "critical":
            critical_issues.append("critical_review_item_open")
    if docs.get("status") == "warning":
        warnings.append("docs_coverage_warning")
    if performance.get("status") == "warning":
        warnings.append("performance_budget_warning")
    if knowledge.get("warnings"):
        warnings.extend(str(item) for item in knowledge.get("warnings", []))
    status = "critical" if critical_issues else "warning" if warnings or dependencies.get("status") == "warning" else "healthy"
    return {
        "status": status,
        "feature_coverage": roadmap,
        "dependency_health": dependencies,
        "storage_health": storage,
        "knowledge_health": knowledge,
        "docs_coverage": docs,
        "performance_health": performance,
        "critical_issues": critical_issues,
        "warnings": warnings,
        "release_ready": status == "healthy",
    }

