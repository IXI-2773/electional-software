from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

_SPEC = importlib.util.spec_from_file_location("test_policy_guard", Path("scripts/test_policy_guard.py"))
assert _SPEC and _SPEC.loader
guard = importlib.util.module_from_spec(_SPEC)
sys.modules["test_policy_guard"] = guard
_SPEC.loader.exec_module(guard)

_RUNNER_SPEC = importlib.util.spec_from_file_location("run_targeted_tests", Path("scripts/run_targeted_tests.py"))
assert _RUNNER_SPEC and _RUNNER_SPEC.loader
runner = importlib.util.module_from_spec(_RUNNER_SPEC)
sys.modules["run_targeted_tests"] = runner
_RUNNER_SPEC.loader.exec_module(runner)


class TestingPolicyGuardTest(unittest.TestCase):
    def test_policy_guard_rejects_empty_run(self) -> None:
        self.assertFalse(guard.validate_targets().allowed)

    def test_policy_guard_rejects_project_root(self) -> None:
        self.assertFalse(guard.validate_targets(files=["."]).allowed)

    def test_policy_guard_rejects_test_directory(self) -> None:
        self.assertFalse(guard.validate_targets(files=["backend/tests"]).allowed)

    def test_policy_guard_accepts_specific_file(self) -> None:
        self.assertTrue(guard.validate_targets(files=["backend/tests/test_cache.py"]).allowed)

    def test_policy_guard_accepts_specific_case(self) -> None:
        self.assertTrue(guard.validate_targets(cases=["backend/tests/test_cache.py::CacheTest.test_cache_hit"]).allowed)

    def test_targeted_runner_converts_case_to_unittest_name(self) -> None:
        self.assertEqual(
            runner._target_to_unittest_name("backend/tests/test_cache.py::CacheTest.test_cache_hit"),
            "backend.tests.test_cache.CacheTest.test_cache_hit",
        )


if __name__ == "__main__":
    unittest.main()