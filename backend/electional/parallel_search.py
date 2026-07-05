from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping


@dataclass(frozen=True)
class WorkerError:
    item_id: str
    critical: bool
    message: str


def run_parallel_search(
    work_items: Iterable[Mapping[str, object]],
    worker: Callable[[Mapping[str, object]], Mapping[str, object]],
    *,
    workers: int = 1,
) -> dict[str, object]:
    items = list(work_items)
    results: list[dict[str, object]] = []
    errors: list[WorkerError] = []
    if workers <= 1:
        for item in items:
            _run_one(item, worker, results, errors)
    else:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = {pool.submit(worker, item): item for item in items}
            for future in as_completed(futures):
                item = futures[future]
                try:
                    results.append(dict(future.result()))
                except Exception as exc:
                    errors.append(WorkerError(str(item.get("id", "item")), bool(item.get("critical")), str(exc)))
    if any(error.critical for error in errors):
        return {"status": "failed", "results": _sort_results(results), "errors": [error.__dict__ for error in errors]}
    return {"status": "ok", "results": _sort_results(results), "errors": [error.__dict__ for error in errors]}


def _run_one(item: Mapping[str, object], worker: Callable[[Mapping[str, object]], Mapping[str, object]], results: list[dict[str, object]], errors: list[WorkerError]) -> None:
    try:
        results.append(dict(worker(item)))
    except Exception as exc:
        errors.append(WorkerError(str(item.get("id", "item")), bool(item.get("critical")), str(exc)))


def _sort_results(results: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(results, key=lambda item: (-int(item.get("rank_score", item.get("score", 0)) or 0), str(item.get("best_minute", "")), str(item.get("id", item.get("reproducibility_hash", "")))))
