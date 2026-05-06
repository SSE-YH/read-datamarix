from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from .jobs import (
    DEFAULT_STORAGE_ROOT,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_PARTIAL_FAILED,
    STORAGE_ROOT_ENV_VAR,
)

RETENTION_DAYS_ENV_VAR = "BARCODE_READER_RETENTION_DAYS"
DEFAULT_RETENTION_DAYS = 7
TERMINAL_JOB_STATUSES = {
    JOB_STATUS_COMPLETED,
    JOB_STATUS_PARTIAL_FAILED,
    JOB_STATUS_FAILED,
}


@dataclass(frozen=True)
class CleanupCandidate:
    job_id: str
    path: Path
    status: str
    completed_at: str
    age_days: float
    size_bytes: int

    def to_dict(self) -> dict[str, object]:
        return {
            "jobId": self.job_id,
            "path": str(self.path),
            "status": self.status,
            "completedAt": self.completed_at,
            "ageDays": round(self.age_days, 3),
            "sizeBytes": self.size_bytes,
        }


@dataclass(frozen=True)
class CleanupResult:
    storage_root: Path
    retention_days: int
    dry_run: bool
    scanned_count: int
    deleted_count: int
    skipped_count: int
    candidates: tuple[CleanupCandidate, ...]
    errors: tuple[str, ...] = ()

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    @property
    def candidate_bytes(self) -> int:
        return sum(candidate.size_bytes for candidate in self.candidates)

    def to_dict(self) -> dict[str, object]:
        return {
            "storageRoot": str(self.storage_root),
            "retentionDays": self.retention_days,
            "dryRun": self.dry_run,
            "scannedCount": self.scanned_count,
            "candidateCount": self.candidate_count,
            "deletedCount": self.deleted_count,
            "skippedCount": self.skipped_count,
            "candidateBytes": self.candidate_bytes,
            "errors": list(self.errors),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


def resolve_storage_root(storage_root: str | Path | None = None) -> Path:
    configured_root = storage_root or os.environ.get(STORAGE_ROOT_ENV_VAR) or DEFAULT_STORAGE_ROOT
    return Path(configured_root).resolve()


def resolve_retention_days(retention_days: int | None = None) -> int:
    if retention_days is not None:
        resolved = retention_days
    else:
        configured = os.environ.get(RETENTION_DAYS_ENV_VAR)
        resolved = int(configured) if configured else DEFAULT_RETENTION_DAYS

    if resolved < 0:
        raise ValueError("retention days must be zero or greater")
    return resolved


def cleanup_expired_jobs(
    storage_root: str | Path | None = None,
    *,
    retention_days: int | None = None,
    dry_run: bool = True,
    now: datetime | None = None,
) -> CleanupResult:
    root = resolve_storage_root(storage_root)
    resolved_retention_days = resolve_retention_days(retention_days)
    current_time = _as_utc(now or datetime.now(timezone.utc))
    cutoff = current_time - timedelta(days=resolved_retention_days)

    scanned_count = 0
    deleted_count = 0
    skipped_count = 0
    candidates: list[CleanupCandidate] = []
    errors: list[str] = []

    if not root.exists():
        return CleanupResult(
            storage_root=root,
            retention_days=resolved_retention_days,
            dry_run=dry_run,
            scanned_count=0,
            deleted_count=0,
            skipped_count=0,
            candidates=(),
        )

    for job_dir in _iter_job_dirs(root):
        scanned_count += 1
        metadata = _load_metadata(job_dir)
        if metadata is None:
            skipped_count += 1
            continue

        status = str(metadata.get("status") or "")
        completed_at_text = str(metadata.get("completed_at") or "")
        completed_at = parse_utc_timestamp(completed_at_text)
        if status not in TERMINAL_JOB_STATUSES or completed_at is None:
            skipped_count += 1
            continue

        if completed_at > cutoff:
            skipped_count += 1
            continue

        candidate = CleanupCandidate(
            job_id=str(metadata.get("job_id") or job_dir.name),
            path=job_dir,
            status=status,
            completed_at=completed_at_text,
            age_days=max(0.0, (current_time - completed_at).total_seconds() / 86400),
            size_bytes=directory_size(job_dir),
        )
        candidates.append(candidate)

        if dry_run:
            continue

        try:
            delete_job_dir(root, job_dir)
            deleted_count += 1
        except Exception as exc:
            errors.append(f"{job_dir}: {type(exc).__name__}: {exc}")

    return CleanupResult(
        storage_root=root,
        retention_days=resolved_retention_days,
        dry_run=dry_run,
        scanned_count=scanned_count,
        deleted_count=deleted_count,
        skipped_count=skipped_count,
        candidates=tuple(candidates),
        errors=tuple(errors),
    )


def delete_job_dir(storage_root: Path, job_dir: Path) -> None:
    root = storage_root.resolve()
    target = job_dir.resolve()
    if target == root or root not in target.parents:
        raise ValueError(f"refusing to delete path outside storage root: {target}")
    shutil.rmtree(target)


def check_storage_writable(storage_root: str | Path | None = None) -> tuple[bool, str]:
    root = resolve_storage_root(storage_root)
    probe_path = root / f".healthcheck_{uuid.uuid4().hex}.tmp"
    try:
        root.mkdir(parents=True, exist_ok=True)
        probe_path.write_text("ok", encoding="utf-8")
        probe_path.unlink(missing_ok=True)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    return True, ""


def parse_utc_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_utc(parsed)


def directory_size(path: Path) -> int:
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                continue
    return total


def _iter_job_dirs(root: Path) -> Iterable[Path]:
    return sorted(path for path in root.glob("job_*") if path.is_dir())


def _load_metadata(job_dir: Path) -> dict[str, object] | None:
    metadata_path = job_dir / "metadata.json"
    if not metadata_path.exists():
        return None
    try:
        with metadata_path.open("r", encoding="utf-8") as metadata_file:
            metadata = json.load(metadata_file)
    except (OSError, json.JSONDecodeError):
        return None
    return metadata if isinstance(metadata, dict) else None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
