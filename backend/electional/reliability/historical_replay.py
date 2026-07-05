"""Controlled historical replay from reliability audit snapshot folders."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Mapping, Sequence

from .loading import load_audit_snapshot_tolerant
from .regression_replay import compare_regression_snapshots
from .review_queue import build_review_queue
from .storage import DEFAULT_ROOT, ensure_reliability_storage, save_replay_result, save_review_queue


SnapshotBuilder = Callable[[Mapping[str, object]], Mapping[str, object]]


def run_historical_replay(
    *,
    root: Path | str = DEFAULT_ROOT,
    input_path: Path | str | None = None,
    dry_run: bool = False,
    limit: int | None = None,
    objective: str | None = None,
    since: str | None = None,
    save_result: bool = False,
    create_review_items: bool = False,
    current_snapshot_builder: SnapshotBuilder | None = None,
) -> dict[str, object]:
    base = ensure_reliability_storage(root)
    input_path = Path(input_path) if input_path else base / "audit_snapshots"
    _validate_input(input_path, base)
    started = _now()
    files = _input_files(input_path)
    results: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    counts = {"none": 0, "minor": 0, "warning": 0, "major": 0, "critical": 0}
    loaded = 0
    for path in files:
        if limit is not None and loaded >= limit:
            break
        try:
            loaded_payload = load_audit_snapshot_tolerant(path)
        except ValueError as exc:
            skipped.append({"path": str(path), "reason": str(exc)})
            continue
        old_audit = loaded_payload["audit_snapshot"]
        if objective and str(old_audit.get("input", {}).get("objective", "")).lower() != objective.lower():
            continue
        if since and str(old_audit.get("input", {}).get("date", "")) < since:
            continue
        current = current_snapshot_builder(old_audit) if current_snapshot_builder else old_audit
        replay = compare_regression_snapshots(_flatten_audit(old_audit), _flatten_audit(current))
        severity = _worst_severity(replay.get("drifts", []))
        counts[severity] += 1
        loaded += 1
        results.append({"path": str(path), "severity": severity, "replay": replay})
    review_items = build_review_queue(replay_drift=[drift for result in results for drift in result["replay"].get("drifts", [])]) if create_review_items else []
    run_id = "historical_replay_" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "run_id": run_id,
        "input_path": str(input_path),
        "engine_version": "0.9.0-phase3_reliability_v1",
        "schema_version": "phase3_reliability_v1",
        "started_at_utc": started,
        "completed_at_utc": _now(),
        "snapshots_loaded": loaded,
        "snapshots_skipped": len(skipped),
        "no_change": counts["none"],
        "minor_drift": counts["minor"] + counts["warning"],
        "major_drift": counts["major"],
        "critical_drift": counts["critical"],
        "review_items_created": len(review_items),
        "skipped_files": skipped,
        "results": results,
    }
    if save_result and not dry_run:
        saved = save_replay_result(payload, root=base, run_id=run_id)
        payload["saved_path"] = str(saved.path)
    if create_review_items and not dry_run:
        save_review_queue([item.to_json() for item in review_items], root=base)
    return payload


def format_historical_replay_summary(result: Mapping[str, object]) -> str:
    saved = result.get("saved_path") or "not saved"
    return "\n".join(
        [
            "Historical Replay:",
            f"Snapshots loaded: {result.get('snapshots_loaded', 0)}",
            f"Skipped: {result.get('snapshots_skipped', 0)}",
            f"No change: {result.get('no_change', 0)}",
            f"Minor drift: {result.get('minor_drift', 0)}",
            f"Major drift: {result.get('major_drift', 0)}",
            f"Critical drift: {result.get('critical_drift', 0)}",
            f"Review items created: {result.get('review_items_created', 0)}",
            f"Replay result saved: {saved}",
        ]
    )


def _validate_input(input_path: Path, root: Path) -> None:
    resolved = input_path.resolve()
    project_root = Path(__file__).resolve().parents[3]
    if resolved == project_root.resolve():
        raise ValueError("Refusing to replay from project root. Use data/reliability/audit_snapshots or a specific snapshot.")
    allowed = (root / "audit_snapshots").resolve()
    if resolved.is_dir() and resolved != allowed and allowed not in resolved.parents:
        raise ValueError("Replay input folder is too broad or outside controlled reliability storage.")


def _input_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(path for path in input_path.glob("*.json") if not path.name.startswith("."))


def _flatten_audit(audit: Mapping[str, object]) -> dict[str, object]:
    phase1 = audit.get("phase1_advanced_analysis", {})
    phase2 = audit.get("phase2_tactical_analysis", {})
    hard = audit.get("hard_gates", {})
    return {
        "advancedAnalysis": {
            "planet_roles": phase1.get("planet_roles", []) if isinstance(phase1, Mapping) else [],
            "significator_purity": phase1.get("significator_purity", []) if isinstance(phase1, Mapping) else [],
            "contradictions": phase1.get("contradictions", []) if isinstance(phase1, Mapping) else [],
            "control_index": phase1.get("control_index", {}) if isinstance(phase1, Mapping) else {},
            "resistance_analysis": phase1.get("resistance_analysis", {}) if isinstance(phase1, Mapping) else {},
        },
        "tacticalAnalysis": {
            "final_command": phase2.get("final_command", {}) if isinstance(phase2, Mapping) else {},
            "timing_traps": phase2.get("timing_traps", {}) if isinstance(phase2, Mapping) else {},
            "action_moment": phase2.get("action_moment", {}) if isinstance(phase2, Mapping) else {},
            "playbook": phase2.get("event_playbook", {}) if isinstance(phase2, Mapping) else {},
            "practicality": phase2.get("practicality", {}) if isinstance(phase2, Mapping) else {},
            "strategic_calendar_context": phase2.get("strategic_calendar_context", {}) if isinstance(phase2, Mapping) else {},
            "fast_lane": phase2.get("fast_lane", {}) if isinstance(phase2, Mapping) else {},
        },
        "hardReject": isinstance(hard, Mapping) and hard.get("status") == "failed",
        "score": audit.get("score"),
        "grade": audit.get("grade"),
        "confidence": audit.get("confidence"),
    }


def _worst_severity(drifts: object) -> str:
    if not isinstance(drifts, list) or not drifts:
        return "none"
    rank = {"critical": 4, "major": 3, "warning": 2, "minor": 1, "none": 0}
    return max((str(item.get("severity", "warning")) for item in drifts if isinstance(item, Mapping)), key=lambda value: rank.get(value, 0), default="none")


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
