from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from barcode_reader.operations import (  # noqa: E402
    DEFAULT_RETENTION_DAYS,
    cleanup_expired_jobs,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Remove terminal barcode-reader jobs older than the retention period.",
    )
    parser.add_argument(
        "--storage-root",
        help="Job storage root. Defaults to BARCODE_READER_STORAGE_DIR or storage/jobs.",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=None,
        help=f"Delete terminal jobs completed at least this many days ago. Default: {DEFAULT_RETENTION_DAYS}.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete expired job directories. Without this flag the script is a dry run.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of a text summary.",
    )
    args = parser.parse_args()

    try:
        result = cleanup_expired_jobs(
            args.storage_root,
            retention_days=args.retention_days,
            dry_run=not args.execute,
        )
    except Exception as exc:
        print(f"cleanup failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(format_result(result))

    return 1 if result.errors else 0


def format_result(result) -> str:
    mode = "dry-run" if result.dry_run else "execute"
    lines = [
        f"mode: {mode}",
        f"storage_root: {result.storage_root}",
        f"retention_days: {result.retention_days}",
        f"scanned: {result.scanned_count}",
        f"expired_candidates: {result.candidate_count}",
        f"deleted: {result.deleted_count}",
        f"candidate_bytes: {result.candidate_bytes}",
    ]
    for candidate in result.candidates:
        action = "would delete" if result.dry_run else "deleted"
        lines.append(
            f"- {action}: {candidate.job_id} "
            f"status={candidate.status} age_days={candidate.age_days:.2f} "
            f"bytes={candidate.size_bytes}"
        )
    for error in result.errors:
        lines.append(f"- error: {error}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
