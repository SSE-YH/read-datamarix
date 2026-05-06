from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from barcode_reader.api import create_app
from barcode_reader.jobs import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_PROCESSING,
    JobService,
)
from barcode_reader.operations import cleanup_expired_jobs

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover - import guard for incomplete environments
    TestClient = None


class Phase7OperationsTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.storage_root = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_cleanup_deletes_only_expired_terminal_jobs_when_executed(self):
        now = datetime(2026, 5, 6, tzinfo=timezone.utc)
        expired_at = now - timedelta(days=8)
        fresh_at = now - timedelta(days=2)
        old_processing_at = now - timedelta(days=30)

        expired_dir = write_job(self.storage_root, "job_expired", JOB_STATUS_COMPLETED, expired_at)
        fresh_dir = write_job(self.storage_root, "job_fresh", JOB_STATUS_FAILED, fresh_at)
        processing_dir = write_job(
            self.storage_root,
            "job_processing",
            JOB_STATUS_PROCESSING,
            old_processing_at,
        )

        dry_run = cleanup_expired_jobs(
            self.storage_root,
            retention_days=7,
            dry_run=True,
            now=now,
        )

        self.assertEqual(dry_run.scanned_count, 3)
        self.assertEqual(dry_run.deleted_count, 0)
        self.assertEqual([candidate.job_id for candidate in dry_run.candidates], ["job_expired"])
        self.assertTrue(expired_dir.exists())

        executed = cleanup_expired_jobs(
            self.storage_root,
            retention_days=7,
            dry_run=False,
            now=now,
        )

        self.assertEqual(executed.deleted_count, 1)
        self.assertFalse(expired_dir.exists())
        self.assertTrue(fresh_dir.exists())
        self.assertTrue(processing_dir.exists())

    @unittest.skipIf(TestClient is None, "fastapi test client is not available")
    def test_healthz_reports_writable_storage(self):
        service = JobService(storage_root=self.storage_root, reader=lambda *_args, **_kwargs: [])
        client = TestClient(create_app(job_service=service))

        response = client.get("/healthz")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertTrue(body["storageWritable"])
        self.assertEqual(Path(body["storageRoot"]), self.storage_root.resolve())


def write_job(
    storage_root: Path,
    job_id: str,
    status: str,
    completed_at: datetime,
) -> Path:
    job_dir = storage_root / job_id
    uploads_dir = job_dir / "uploads"
    uploads_dir.mkdir(parents=True)
    (uploads_dir / "image_001.png").write_bytes(b"image")
    (job_dir / "results.csv").write_text("job_id,source_filename\n", encoding="utf-8")
    metadata = {
        "job_id": job_id,
        "status": status,
        "total_images": 1,
        "processed_images": 1,
        "success_count": 1 if status == JOB_STATUS_COMPLETED else 0,
        "failure_count": 0 if status == JOB_STATUS_COMPLETED else 1,
        "result_count": 1,
        "created_at": format_timestamp(completed_at - timedelta(minutes=1)),
        "started_at": format_timestamp(completed_at - timedelta(seconds=30)),
        "completed_at": format_timestamp(completed_at),
        "csv_path": "results.csv",
        "error_message": "",
        "images": [],
    }
    (job_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    return job_dir


def format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    unittest.main()
