from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


REQUIRED_DOCS = {
    "phase4_operations": ("docs/PHASE4_PERFORMANCE.md", "docs/SEARCH_PROFILES.md", "docs/WATCHLISTS.md"),
    "phase6_source_intake": ("docs/PDF_SOURCE_INTAKE.md",),
    "phase6b_source_knowledge": ("docs/PDF_SOURCE_KNOWLEDGE_LAYER.md",),
    "phase7_governance": ("docs/ROADMAP.md", "docs/RELEASE_PROCESS.md", "docs/PROJECT_HEALTH.md", "docs/TARGETED_TESTING_POLICY.md"),
}


def get_docs_coverage(root: Path | str = PROJECT_ROOT) -> dict[str, object]:
    base = Path(root)
    rows = []
    for feature_id, paths in REQUIRED_DOCS.items():
        existing = [path for path in paths if (base / path).exists()]
        rows.append({"feature_id": feature_id, "docs": list(paths), "existing": existing, "status": "healthy" if len(existing) == len(paths) else "warning"})
    return {"status": "warning" if any(row["status"] == "warning" for row in rows) else "healthy", "features": rows}

