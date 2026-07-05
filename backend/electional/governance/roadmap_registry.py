from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path


GOVERNANCE_ROOT = Path(__file__).resolve().parents[3] / "data" / "project_governance"
ROADMAP_PATH = GOVERNANCE_ROOT / "roadmap" / "roadmap_registry.json"
VALID_STATUSES = {"planned", "in_progress", "implemented", "verified", "blocked", "deferred", "deprecated", "unknown"}


@dataclass(frozen=True)
class RoadmapItem:
    item_id: str
    phase: str
    name: str
    status: str
    category: str
    owner: str = "system"
    risk_level: str = "medium"
    dependencies: tuple[str, ...] = ()
    has_tests: bool = False
    has_docs: bool = False
    has_api: bool = False
    has_ui: bool = False
    has_storage: bool = False
    last_verified_at_utc: str | None = None
    warnings: tuple[str, ...] = ()

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["dependencies"] = list(self.dependencies)
        payload["warnings"] = list(self.warnings)
        return payload


def load_roadmap_registry(path: Path | str = ROADMAP_PATH) -> dict[str, RoadmapItem]:
    source = Path(path)
    if not source.exists():
        return {item.item_id: item for item in default_roadmap_items()}
    data = json.loads(source.read_text(encoding="utf-8"))
    items = data.get("items", []) if isinstance(data, dict) else []
    loaded = {_from_json(item).item_id: _from_json(item) for item in items if isinstance(item, dict)}
    for item in default_roadmap_items():
        loaded.setdefault(item.item_id, item)
    return loaded


def save_roadmap_registry(items: dict[str, RoadmapItem], path: Path | str = ROADMAP_PATH) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"updated_at_utc": _now(), "items": [item.to_json() for item in sorted(items.values(), key=lambda row: row.item_id)]}
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def list_roadmap_items(path: Path | str = ROADMAP_PATH) -> list[RoadmapItem]:
    return list(load_roadmap_registry(path).values())


def get_roadmap_item(item_id: str, path: Path | str = ROADMAP_PATH) -> RoadmapItem:
    return load_roadmap_registry(path).get(item_id) or RoadmapItem(item_id, "Unknown", item_id, "unknown", "unknown", warnings=("unknown_feature",))


def update_roadmap_status(item_id: str, status: str, path: Path | str = ROADMAP_PATH) -> RoadmapItem:
    if status not in VALID_STATUSES:
        raise ValueError(f"Unsupported roadmap status: {status}")
    items = load_roadmap_registry(path)
    current = items.get(item_id) or get_roadmap_item(item_id, path)
    updated = RoadmapItem(
        current.item_id, current.phase, current.name, status, current.category, current.owner, current.risk_level,
        current.dependencies, current.has_tests, current.has_docs, current.has_api, current.has_ui, current.has_storage,
        _now() if status == "verified" else current.last_verified_at_utc, current.warnings,
    )
    items[item_id] = updated
    save_roadmap_registry(items, path)
    return updated


def summarize_roadmap_status(path: Path | str = ROADMAP_PATH) -> dict[str, object]:
    items = list_roadmap_items(path)
    counts = {status: sum(1 for item in items if item.status == status) for status in sorted(VALID_STATUSES)}
    phases = sorted({item.phase for item in items})
    return {"total": len(items), "counts": counts, "phases": {phase: sum(1 for item in items if item.phase == phase) for phase in phases}}


def default_roadmap_items() -> tuple[RoadmapItem, ...]:
    return (
        RoadmapItem("core_engine", "Core", "Core Engine", "verified", "engine", has_tests=True, has_docs=True, has_api=True),
        RoadmapItem("phase1_advanced_analysis", "Phase 1", "Advanced Analysis", "verified", "analysis", has_tests=True, has_docs=True, has_api=True),
        RoadmapItem("phase2_fast_lane", "Phase 2", "Fast Lane Mode", "verified", "tactical_output", dependencies=("phase2_final_command", "phase2_action_moment", "phase2_practicality", "core_hard_gates"), has_tests=True, has_docs=True, has_api=True, has_ui=True),
        RoadmapItem("core_hard_gates", "Core", "Hard Gates", "verified", "engine", has_tests=True, has_docs=True, has_api=True),
        RoadmapItem("phase2_final_command", "Phase 2", "Final Command", "verified", "tactical_output", has_tests=True, has_docs=True, has_api=True),
        RoadmapItem("phase2_action_moment", "Phase 2", "Action Moment", "verified", "tactical_output", has_tests=True, has_docs=True, has_api=True),
        RoadmapItem("phase2_practicality", "Phase 2", "Practical Usability", "verified", "tactical_output", has_tests=True, has_docs=True, has_api=True),
        RoadmapItem("phase2_timing_traps", "Phase 2", "Timing Traps", "verified", "tactical_output", has_tests=True, has_docs=True, has_api=True),
        RoadmapItem("phase3_audit_snapshot", "Phase 3", "Audit Snapshot", "verified", "reliability", has_tests=True, has_docs=True, has_api=True, has_storage=True),
        RoadmapItem("phase3_schema_migration", "Phase 3", "Schema Migration", "verified", "reliability", has_tests=True, has_docs=True, has_api=True),
        RoadmapItem("phase3_review_queue", "Phase 3", "Review Queue", "verified", "reliability", has_tests=True, has_docs=True, has_api=True, has_storage=True),
        RoadmapItem("phase4_search_profiles", "Phase 4", "Search Profiles", "implemented", "operations", has_tests=True, has_docs=True, has_api=True, has_storage=True),
        RoadmapItem("phase4_watchlists", "Phase 4", "Watchlists", "implemented", "operations", has_tests=True, has_docs=True, has_api=True, has_storage=True),
        RoadmapItem("phase4_objective_packs", "Phase 4", "Objective Packs", "implemented", "operations", has_tests=True, has_docs=True, has_api=True, has_storage=True),
        RoadmapItem("phase3_reliability", "Phase 3", "Reliability Storage and Replay", "verified", "reliability", has_tests=True, has_docs=True, has_api=True, has_storage=True),
        RoadmapItem("phase4_operations", "Phase 4", "Profiles, Watchlists, Caching", "implemented", "operations", has_tests=True, has_docs=True, has_api=True, has_storage=True),
        RoadmapItem("phase6_source_intake", "Phase 6", "PDF Source Intake", "verified", "source_intake", has_tests=True, has_docs=True, has_api=True, has_ui=True, has_storage=True),
        RoadmapItem("phase6b_source_knowledge", "Phase 6B", "Source Knowledge Layer", "verified", "source_knowledge", dependencies=("phase6_source_intake",), has_tests=True, has_docs=True, has_api=True, has_ui=True, has_storage=True),
        RoadmapItem("phase7_governance", "Phase 7", "Project Governance", "implemented", "governance", dependencies=("phase3_reliability", "phase6b_source_knowledge"), has_tests=True, has_docs=True, has_api=True, has_storage=True),
    )


def _from_json(data: dict[str, object]) -> RoadmapItem:
    return RoadmapItem(
        str(data.get("item_id") or "unknown"), str(data.get("phase") or "Unknown"), str(data.get("name") or data.get("item_id") or "Unknown"),
        str(data.get("status") or "unknown"), str(data.get("category") or "unknown"), str(data.get("owner") or "system"),
        str(data.get("risk_level") or "medium"), tuple(str(item) for item in data.get("dependencies", []) if item),
        bool(data.get("has_tests")), bool(data.get("has_docs")), bool(data.get("has_api")), bool(data.get("has_ui")), bool(data.get("has_storage")),
        str(data["last_verified_at_utc"]) if data.get("last_verified_at_utc") else None,
        tuple(str(item) for item in data.get("warnings", []) if item),
    )


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")

