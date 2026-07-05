from __future__ import annotations

from time import perf_counter

from ..source_knowledge import search_source_chunks


def get_performance_budget_status(*, root=None) -> dict[str, object]:
    checks = []
    start = perf_counter()
    search_source_chunks("mercury", root=root) if root is not None else search_source_chunks("mercury")
    elapsed = perf_counter() - start
    checks.append({"name": "source_chunk_search_budget", "target_seconds": 1.0, "observed_seconds": round(elapsed, 4), "status": "pass" if elapsed <= 1.0 else "warning"})
    return {"status": "warning" if any(check["status"] != "pass" for check in checks) else "healthy", "checks": checks}

