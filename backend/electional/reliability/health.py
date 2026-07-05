"""Storage health checks for reliability persistence."""

from __future__ import annotations

import json
from pathlib import Path

from .indexes import check_indexes
from .storage import DEFAULT_ROOT, SUBDIRS, ensure_reliability_storage, load_reliability_object


def check_storage_health(root: Path | str = DEFAULT_ROOT) -> dict[str, object]:
    base = ensure_reliability_storage(root)
    missing_folders = [subdir for subdir in SUBDIRS if not (base / subdir).exists()]
    invalid_files: list[str] = []
    hash_mismatches: list[str] = []
    for folder in ("audit_snapshots", "outcome_logs", "replay_results"):
        for path in (base / folder).glob("*.json"):
            if path.name.startswith("."):
                continue
            try:
                load_reliability_object(path)
            except ValueError as exc:
                if "hash mismatch" in str(exc):
                    hash_mismatches.append(str(path))
                else:
                    invalid_files.append(str(path))
            except (OSError, json.JSONDecodeError):
                invalid_files.append(str(path))
    index_status = check_indexes(base)
    counts = {
        "audit_snapshots": len(list((base / "audit_snapshots").glob("*.json"))),
        "outcome_logs": len(list((base / "outcome_logs").glob("*.json"))),
        "replay_results": len(list((base / "replay_results").glob("*.json"))),
        "review_queue": 1 if (base / "review_queue" / "review_queue.json").exists() else 0,
        "quarantine": len(list((base / "quarantine").glob("*"))),
    }
    status = "critical" if hash_mismatches else "warning" if missing_folders or invalid_files or index_status["status"] != "healthy" else "healthy"
    return {
        "status": status,
        "missing_folders": missing_folders,
        "invalid_json_files": invalid_files,
        "hash_mismatches": hash_mismatches,
        "index_status": index_status,
        "counts": counts,
    }


def format_storage_health(health: dict[str, object]) -> str:
    counts = health.get("counts", {})
    index_status = health.get("index_status", {})
    return "\n".join(
        [
            "Reliability Storage Health:",
            f"Status: {str(health.get('status', 'unknown')).title()}",
            f"Audit snapshots: {counts.get('audit_snapshots', 0) if isinstance(counts, dict) else 0}",
            f"Outcome logs: {counts.get('outcome_logs', 0) if isinstance(counts, dict) else 0}",
            f"Replay results: {counts.get('replay_results', 0) if isinstance(counts, dict) else 0}",
            f"Review items: {counts.get('review_queue', 0) if isinstance(counts, dict) else 0} open",
            f"Invalid files: {len(health.get('invalid_json_files', [])) if isinstance(health.get('invalid_json_files'), list) else 0}",
            f"Unindexed snapshots: {len(index_status.get('unindexed_files', [])) if isinstance(index_status, dict) else 0}",
            f"Hash mismatches: {len(health.get('hash_mismatches', [])) if isinstance(health.get('hash_mismatches'), list) else 0}",
            f"Quarantined files: {counts.get('quarantine', 0) if isinstance(counts, dict) else 0}",
        ]
    )
