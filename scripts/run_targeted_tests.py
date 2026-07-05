from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from test_policy_guard import validate_targets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", action="append", dest="files")
    parser.add_argument("--case", action="append", dest="cases")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)
    result = validate_targets(args.files, args.cases, allow_all=args.all)
    if not result.allowed:
        print(result.reason)
        return 2
    targets = list(args.files or []) + list(args.cases or [])
    command = [sys.executable, "-m", "unittest", *[_target_to_unittest_name(target) for target in targets]]
    return subprocess.call(command)


def _target_to_unittest_name(target: str) -> str:
    if "::" not in target:
        return _path_to_module(target)
    path_text, case_text = target.split("::", 1)
    case = case_text.replace("::", ".")
    return f"{_path_to_module(path_text)}.{case}" if case else _path_to_module(path_text)


def _path_to_module(path_text: str) -> str:
    path = Path(path_text)
    return ".".join(path.with_suffix("").parts)


if __name__ == "__main__":
    raise SystemExit(main())