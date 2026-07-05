from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping

from .dependencies import validate_dependencies
from .docs_coverage import get_docs_coverage
from .project_health import get_project_health
from .roadmap_registry import GOVERNANCE_ROOT, get_roadmap_item


def run_release_gate(
    release_id: str = "rc_local",
    *,
    review_items: list[Mapping[str, object]] | None = None,
    project_health: Mapping[str, object] | None = None,
) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    checks.append(_check("roadmap_registry_loads", "pass", "Roadmap registry loaded."))
    fast_lane = get_roadmap_item("phase2_fast_lane")
    checks.append(_check("fast_lane_present", "pass" if fast_lane.status not in {"unknown", "blocked"} else "fail", "Fast Lane roadmap item is present.", "critical"))
    dep = validate_dependencies()
    checks.append(_check("critical_dependencies_satisfied", "pass" if dep["status"] != "blocked" else "fail", "Critical dependencies satisfied." if dep["status"] != "blocked" else "Critical dependencies are missing.", "critical"))
    health = dict(project_health or get_project_health(review_items=review_items))
    checks.append(_check("project_health_not_critical", "pass" if health.get("status") != "critical" else "fail", "Project health is not critical.", "critical"))
    critical_reviews = [item for item in review_items or [] if item.get("severity") == "critical"]
    checks.append(_check("no_critical_review_items", "pass" if not critical_reviews else "fail", f"{len(critical_reviews)} critical review items are open.", "critical"))
    docs = get_docs_coverage()
    checks.append(_check("docs_coverage_acceptable", "pass" if docs["status"] == "healthy" else "warn", "Documentation gaps detected.", "warning"))
    blockers = [check["message"] for check in checks if check["status"] == "fail" and check["severity"] == "critical"]
    status = "blocked" if blockers else "warning" if any(check["status"] == "warn" for check in checks) else "pass"
    return {"release_id": release_id, "created_at_utc": _now(), "status": status, "checks": checks, "warnings": [check["message"] for check in checks if check["status"] == "warn"], "blockers": blockers}


def save_release_gate_result(result: Mapping[str, object], root: Path | str = GOVERNANCE_ROOT) -> Path:
    target = Path(root) / "release_gates" / f"{result.get('release_id', 'release_gate')}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(dict(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def load_release_gate_result(release_id: str, root: Path | str = GOVERNANCE_ROOT) -> dict[str, object]:
    return json.loads((Path(root) / "release_gates" / f"{release_id}.json").read_text(encoding="utf-8"))


def _check(check_id: str, status: str, message: str, severity: str = "warning") -> dict[str, object]:
    return {"check_id": check_id, "status": status, "severity": severity, "message": message}


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")

