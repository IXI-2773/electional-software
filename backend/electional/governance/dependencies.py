from __future__ import annotations

from dataclasses import asdict, dataclass

from .roadmap_registry import RoadmapItem, load_roadmap_registry


@dataclass(frozen=True)
class FeatureDependency:
    feature_id: str
    depends_on: tuple[str, ...]
    blocks: tuple[str, ...] = ()
    risk_if_missing: str = ""
    severity: str = "warning"

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["depends_on"] = list(self.depends_on)
        payload["blocks"] = list(self.blocks)
        return payload


DEFAULT_DEPENDENCIES = (
    FeatureDependency("phase2_fast_lane", ("phase2_final_command", "phase2_action_moment", "phase2_practicality", "phase2_timing_traps", "core_hard_gates"), risk_if_missing="Fast Lane cannot issue trustworthy operational command.", severity="critical"),
    FeatureDependency("phase3_historical_replay", ("phase3_audit_snapshot", "phase3_schema_migration", "phase3_review_queue"), risk_if_missing="Replay cannot compare historical outputs safely.", severity="critical"),
    FeatureDependency("phase6b_source_knowledge", ("phase6_source_intake",), risk_if_missing="Knowledge chunks require controlled source documents.", severity="critical"),
    FeatureDependency("phase7_rule_promotion_future", ("phase6b_source_knowledge", "phase3_review_queue"), risk_if_missing="Future rule promotion must be source-backed and reviewed.", severity="warning"),
    FeatureDependency("phase4_watchlists", ("phase4_search_profiles", "phase2_fast_lane", "phase4_objective_packs"), risk_if_missing="Watchlists need profiles, objective packs, and Fast Lane filtering.", severity="warning"),
)


def load_dependency_map() -> list[FeatureDependency]:
    return list(DEFAULT_DEPENDENCIES)


def find_broken_dependencies(items: dict[str, RoadmapItem] | None = None, dependencies: list[FeatureDependency] | None = None) -> list[dict[str, object]]:
    items = items or load_roadmap_registry()
    broken: list[dict[str, object]] = []
    for dep in dependencies or load_dependency_map():
        for required in dep.depends_on:
            item = items.get(required)
            if item is None or item.status in {"blocked", "unknown", "planned", "deferred"}:
                broken.append({"feature_id": dep.feature_id, "missing_dependency": required, "severity": dep.severity, "risk": dep.risk_if_missing})
    return broken


def validate_dependencies() -> dict[str, object]:
    broken = find_broken_dependencies()
    return {"status": "blocked" if any(item["severity"] == "critical" for item in broken) else "warning" if broken else "pass", "broken_dependencies": broken}


def find_impacted_features(feature_id: str, dependencies: list[FeatureDependency] | None = None) -> list[str]:
    return sorted(dep.feature_id for dep in dependencies or load_dependency_map() if feature_id in dep.depends_on)

