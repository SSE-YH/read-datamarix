from __future__ import annotations

import csv
import io
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from barcode_reader.api import create_app
from barcode_reader.jobs import (
    JOB_STATUS_QUEUED,
    JobRecord,
    JobService,
    UploadedImage,
    utc_now_iso,
)

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover - import guard for incomplete environments
    TestClient = None


@unittest.skipIf(TestClient is None, "fastapi test client is not available")
class ApiJobsTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.service = JobService(storage_root=self.tempdir.name, reader=raising_reader)
        self.client = TestClient(create_app(job_service=self.service))

    def tearDown(self):
        self.tempdir.cleanup()

    def test_unknown_job_returns_404(self):
        response = self.client.get("/api/jobs/job_missing")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"]["message"], "Job not found.")

    def test_csv_before_ready_returns_409(self):
        record = JobRecord(
            job_id="job_waiting",
            status=JOB_STATUS_QUEUED,
            total_images=1,
            processed_images=0,
            success_count=0,
            failure_count=0,
            result_count=0,
            created_at=utc_now_iso(),
            started_at=None,
            completed_at=None,
            csv_path=None,
            error_message="",
            images=[
                UploadedImage(
                    image_id="image_001",
                    image_index=1,
                    source_filename="one.png",
                    stored_path="uploads/image_001.png",
                    content_type="image/png",
                    size_bytes=10,
                )
            ],
        )
        self.service.storage.save_job(record)

        response = self.client.get("/api/jobs/job_waiting/csv")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["message"], "CSV is not ready for this job.")

    def test_processing_exception_becomes_failed_job_with_csv(self):
        response = self.client.post(
            "/api/uploads",
            files=[("images", ("one.png", image_bytes(), "image/png"))],
        )

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["status"], "failed")
        self.assertEqual(body["failureCount"], 1)
        self.assertTrue(body["csvReady"])
        self.assertEqual(body["images"][0]["status"], "error")

        csv_response = self.client.get(body["links"]["csv"])
        self.assertEqual(csv_response.status_code, 200)
        rows = list(csv.DictReader(io.StringIO(csv_response.text)))
        self.assertEqual(rows[0]["status"], "error")
        self.assertIn("processing failed: RuntimeError: boom", rows[0]["error_message"])


def raising_reader(image, *, source_filename=None):
    raise RuntimeError("boom")


def image_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(output, format="PNG")
    return output.getvalue()


if __name__ == "__main__":
    unittest.main()
