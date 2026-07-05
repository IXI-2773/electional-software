from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "data" / "project_governance" / "config" / "project_config.json"


def default_project_config() -> dict[str, object]:
    return {
        "testing_policy": {"allow_broad_suite_by_default": False, "max_targeted_test_files": 3},
        "paths": {"reliability": "data/reliability", "source_documents": "data/source_documents", "project_governance": "data/project_governance", "backups": "backups"},
        "performance_budget": {"fast_lane_seconds": 2.0, "single_analysis_seconds": 5.0, "source_search_seconds": 1.0},
        "release_gates": {"strict_blockers": True, "docs_required": False},
        "privacy": {"public_exports_include_private_paths": False},
    }


def load_project_config(path: Path | str = CONFIG_PATH, *, create_paths: bool = True) -> dict[str, object]:
    target = Path(path)
    if target.exists():
        data = json.loads(target.read_text(encoding="utf-8"))
    else:
        data = default_project_config()
    warnings = validate_project_config(data)
    data.setdefault("warnings", warnings)
    if create_paths:
        for rel in data.get("paths", {}).values() if isinstance(data.get("paths"), dict) else []:
            (PROJECT_ROOT / str(rel)).mkdir(parents=True, exist_ok=True)
    return data


def save_project_config(config: dict[str, object], path: Path | str = CONFIG_PATH) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def validate_project_config(config: dict[str, object]) -> list[str]:
    warnings: list[str] = []
    testing = config.get("testing_policy", {})
    if not isinstance(testing, dict) or testing.get("allow_broad_suite_by_default") is not False:
        warnings.append("broad_suite_must_be_disabled_by_default")
    paths = config.get("paths", {})
    if not isinstance(paths, dict) or "project_governance" not in paths:
        warnings.append("project_governance_path_missing")
    return warnings
