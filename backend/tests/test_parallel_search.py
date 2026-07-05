from __future__ import annotations

import unittest

from backend.electional.parallel_search import run_parallel_search


def worker(item):
    if item.get("fail"):
        raise ValueError("bad worker")
    return {"id": item["id"], "score": item["score"], "best_minute": item.get("best_minute", "")}


class ParallelSearchTest(unittest.TestCase):
    def test_parallel_search_matches_single_thread_and_sort_is_deterministic(self) -> None:
        items = [{"id": "b", "score": 90, "best_minute": "10:02"}, {"id": "a", "score": 90, "best_minute": "10:01"}]
        single = run_parallel_search(items, worker, workers=1)
        parallel = run_parallel_search(items, worker, workers=2)
        self.assertEqual(single["results"], parallel["results"])
        self.assertEqual([item["id"] for item in parallel["results"]], ["a", "b"])

    def test_parallel_search_handles_worker_error(self) -> None:
        result = run_parallel_search([{"id": "x", "score": 1, "fail": True}], worker, workers=2)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["errors"])

    def test_parallel_search_critical_error_fails(self) -> None:
        result = run_parallel_search([{"id": "x", "score": 1, "fail": True, "critical": True}], worker, workers=1)
        self.assertEqual(result["status"], "failed")


if __name__ == "__main__":
    unittest.main()
