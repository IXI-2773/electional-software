"""Small reliability command entry point.

Usage examples:
  python -m backend.electional.reliability.cli reliability index rebuild
  python -m backend.electional.reliability.cli reliability index check
  python -m backend.electional.reliability.cli reliability storage check
  python -m backend.electional.reliability.cli reliability backup --output backups/
  python -m backend.electional.reliability.cli reliability restore --input backups/file.zip --dry-run
  python -m backend.electional.reliability.cli replay historical --dry-run
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ..backup_restore import backup_reliability_data, restore_reliability_data
from .health import check_storage_health, format_storage_health
from .historical_replay import format_historical_replay_summary, run_historical_replay
from .indexes import check_indexes, rebuild_indexes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="election")
    sub = parser.add_subparsers(dest="area", required=True)
    reliability = sub.add_parser("reliability")
    reliability_sub = reliability.add_subparsers(dest="command", required=True)
    index = reliability_sub.add_parser("index")
    index_sub = index.add_subparsers(dest="index_command", required=True)
    index_sub.add_parser("rebuild")
    index_sub.add_parser("check")
    storage = reliability_sub.add_parser("storage")
    storage_sub = storage.add_subparsers(dest="storage_command", required=True)
    storage_sub.add_parser("check")
    backup = reliability_sub.add_parser("backup")
    backup.add_argument("--output", required=True)
    restore = reliability_sub.add_parser("restore")
    restore.add_argument("--input", required=True)
    restore.add_argument("--dry-run", action="store_true")
    restore.add_argument("--commit", action="store_true")
    restore.add_argument("--overwrite", action="store_true")
    replay = sub.add_parser("replay")
    replay_sub = replay.add_subparsers(dest="command", required=True)
    historical = replay_sub.add_parser("historical")
    historical.add_argument("--input", dest="input_path")
    historical.add_argument("--dry-run", action="store_true")
    historical.add_argument("--limit", type=int)
    historical.add_argument("--objective")
    historical.add_argument("--since")
    historical.add_argument("--save-result", action="store_true")
    historical.add_argument("--create-review-items", action="store_true")
    args = parser.parse_args(argv)

    if args.area == "reliability" and args.command == "index" and args.index_command == "rebuild":
        result = rebuild_indexes()
        print(f"Rebuilt reliability indexes: snapshots {len(result['snapshot'])}, outcomes {len(result['outcome'])}, replays {len(result['replay'])}.")
        return 0
    if args.area == "reliability" and args.command == "index" and args.index_command == "check":
        print(check_indexes())
        return 0
    if args.area == "reliability" and args.command == "storage" and args.storage_command == "check":
        print(format_storage_health(check_storage_health()))
        return 0
    if args.area == "reliability" and args.command == "backup":
        result = backup_reliability_data(output_dir=args.output)
        print(f"Backup created: {result['path']}")
        return 0
    if args.area == "reliability" and args.command == "restore":
        if not args.dry_run and not args.commit:
            print("Restore requires --dry-run or --commit.")
            return 2
        result = restore_reliability_data(input_zip=args.input, dry_run=not args.commit, overwrite=args.overwrite)
        print(f"Restore {'dry-run' if result['dry_run'] else 'commit'}: {len(result['files'])} files.")
        return 0
    if args.area == "replay" and args.command == "historical":
        result = run_historical_replay(
            input_path=Path(args.input_path) if args.input_path else None,
            dry_run=args.dry_run,
            limit=args.limit,
            objective=args.objective,
            since=args.since,
            save_result=args.save_result,
            create_review_items=args.create_review_items,
        )
        print(format_historical_replay_summary(result))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())