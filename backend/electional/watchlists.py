from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Mapping, Sequence

WATCHLIST_ROOT = Path(__file__).resolve().parents[2] / "data" / "watchlists"


def save_watchlist(watchlist: Mapping[str, object], *, root: Path | str = WATCHLIST_ROOT) -> Path:
    _validate_watchlist(watchlist)
    base = Path(root)
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{_safe_id(str(watchlist['watchlist_id']))}.json"
    path.write_text(json.dumps(dict(watchlist), indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    return path


def load_watchlist(watchlist_id: str, *, root: Path | str = WATCHLIST_ROOT) -> dict[str, object]:
    path = Path(root) / f"{_safe_id(watchlist_id)}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    _validate_watchlist(data)
    return dict(data)


def run_watchlist_scan(
    watchlist: Mapping[str, object],
    candidate_provider: Callable[[Mapping[str, object]], Sequence[Mapping[str, object]]],
    *,
    profile: Mapping[str, object] | None = None,
) -> dict[str, object]:
    _validate_watchlist(watchlist)
    previous = {str(item.get("window_id")): item for item in watchlist.get("results", []) if isinstance(item, Mapping)}
    candidates = [_normalize_candidate(item) for item in candidate_provider(profile or watchlist)]
    filtered = [_with_versions(item, profile) for item in candidates if _passes_filters(item, watchlist)]
    deduped: dict[str, dict[str, object]] = {}
    for item in filtered:
        deduped.setdefault(str(item["window_id"]), item)
    new_ids = set(deduped) - set(previous)
    removed_ids = set(previous) - set(deduped)
    downgraded = [item for key, item in deduped.items() if key in previous and _grade_rank(str(item.get("grade"))) < _grade_rank(str(previous[key].get("grade")))]
    upgraded = [item for key, item in deduped.items() if key in previous and _grade_rank(str(item.get("grade"))) > _grade_rank(str(previous[key].get("grade")))]
    return {
        "watchlist_id": watchlist["watchlist_id"],
        "scanned_at_utc": _now(),
        "results": list(deduped.values()),
        "new_windows": [deduped[key] for key in sorted(new_ids)],
        "windows_removed": [previous[key] for key in sorted(removed_ids)],
        "windows_upgraded": upgraded,
        "windows_downgraded": downgraded,
        "rare_windows_found": [item for item in deduped.values() if str(item.get("rarity_label")).lower() in {"rare", "very_rare", "unique"}],
        "least_bad_windows_found": [item for item in deduped.values() if item.get("emergency_only")],
    }


def _passes_filters(candidate: Mapping[str, object], watchlist: Mapping[str, object]) -> bool:
    if watchlist.get("require_fast_lane_not_reject") and str(candidate.get("fast_lane_command")) == "REJECT":
        return False
    if watchlist.get("exclude_critical_traps") and "critical" in [str(item).lower() for item in candidate.get("trap_severities", [])]:
        return False
    if _grade_rank(str(candidate.get("grade"))) < _grade_rank(str(watchlist.get("minimum_grade", "F"))):
        return False
    if int(candidate.get("practicality_score", 0) or 0) < int(watchlist.get("minimum_practicality", 0) or 0):
        return False
    if int(candidate.get("control_score", 0) or 0) < int(watchlist.get("minimum_control", 0) or 0):
        return False
    return True


def _normalize_candidate(item: Mapping[str, object]) -> dict[str, object]:
    window_id = str(item.get("window_id") or item.get("id") or item.get("best_minute") or item.get("start") or "window")
    return {"window_id": window_id, **dict(item)}


def _with_versions(item: dict[str, object], profile: Mapping[str, object] | None) -> dict[str, object]:
    item = dict(item)
    item.setdefault("engine_version", "phase4_operational_v1")
    if profile:
        item.setdefault("profile_id", profile.get("profile_id"))
        item.setdefault("profile_version", profile.get("version"))
    return item


def _validate_watchlist(watchlist: Mapping[str, object]) -> None:
    for key in ("watchlist_id", "profile_id", "range_days"):
        if not watchlist.get(key):
            raise ValueError(f"Missing {key}.")


def _grade_rank(grade: str) -> int:
    return {"A+": 12, "A": 11, "A-": 10, "B+": 9, "B": 8, "B-": 7, "C+": 6, "C": 5, "D": 3, "F": 1}.get(grade.upper(), 0)


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value) or "watchlist"


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")