from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

MAX_DEFAULT_TEST_FILES = 3
MAX_DEFAULT_TEST_CASES = 10


@dataclass(frozen=True)
class PolicyResult:
    allowed: bool
    reason: str
    targets: tuple[str, ...] = ()


def validate_targets(files: list[str] | None = None, cases: list[str] | None = None, *, allow_all: bool = False) -> PolicyResult:
    files = list(files or [])
    cases = list(cases or [])
    if allow_all:
        return PolicyResult(False, "Broad suite runs require an explicit user request outside this helper.")
    if not files and not cases:
        return PolicyResult(False, "At least one specific test file or case is required.")
    if len(files) > MAX_DEFAULT_TEST_FILES:
        return PolicyResult(False, f"Too many files: maximum is {MAX_DEFAULT_TEST_FILES}.")
    if len(cases) > MAX_DEFAULT_TEST_CASES:
        return PolicyResult(False, f"Too many cases: maximum is {MAX_DEFAULT_TEST_CASES}.")
    for target in [*files, *cases]:
        failure = _target_failure(target, case="::" in target)
        if failure:
            return PolicyResult(False, failure)
    return PolicyResult(True, "Targeted run accepted.", tuple([*files, *cases]))


def _target_failure(target: str, *, case: bool) -> str:
    text = str(target or "").strip()
    if not text:
        return "Empty test target is not allowed."
    path_text = text.split("::", 1)[0]
    if any(char in path_text for char in "*?[]"):
        return "Broad globs are not allowed."
    path = Path(path_text)
    normalized = path.as_posix().rstrip("/")
    if normalized in {"", ".", "./"}:
        return "Project root is not a targeted test."
    if normalized in {"backend/tests", "tests"}:
        return "Test directories are not targeted tests."
    if path.suffix != ".py":
        return "Target must be a specific Python test file or test case."
    if case and "::" not in text:
        return "Case target must include ::."
    return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", action="append", dest="files")
    parser.add_argument("--case", action="append", dest="cases")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)
    result = validate_targets(args.files, args.cases, allow_all=args.all)
    print(result.reason)
    return 0 if result.allowed else 2


if __name__ == "__main__":
    raise SystemExit(main())
