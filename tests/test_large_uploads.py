from __future__ import annotations

import json
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from barcode_reader.api import create_app
from barcode_reader.jobs import MAX_UPLOAD_IMAGES, JobService
from barcode_reader.models import BarcodeResult

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover - import guard for incomplete environments
    TestClient = None


@unittest.skipIf(TestClient is None, "fastapi test client is not available")
class LargeUploadReliabilityTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_max_count_tiny_upload_records_timings_and_image_logs(self):
        service = JobService(storage_root=self.tempdir.name, reader=success_reader)
        client = TestClient(create_app(job_service=service))
        png = image_bytes()
        files = [
            ("images", (f"image_{index:03d}.png", png, "image/png"))
            for index in range(1, MAX_UPLOAD_IMAGES + 1)
        ]

        response = client.post("/api/uploads", files=files)

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["status"], "completed")
        self.assertEqual(body["totalImages"], MAX_UPLOAD_IMAGES)
        self.assertEqual(body["processedImages"], MAX_UPLOAD_IMAGES)
        self.assertEqual(body["successCount"], MAX_UPLOAD_IMAGES)
        self.assertTrue(all(image["processingMs"] is not None for image in body["images"]))

        events = read_log_events(service, body["jobId"])
        image_events = [event for event in events if event["event"] == "image_processed"]
        self.assertEqual(len(image_events), MAX_UPLOAD_IMAGES)
        for event in image_events[:5]:
            self.assertEqual(event["status"], "success")
            self.assertEqual(event["error_message"], "")
            self.assertIn("job_id", event)
            self.assertIn("source_filename", event)
            self.assertIsInstance(event["elapsed_ms"], int)

    def test_reader_retry_can_recover_from_transient_exception(self):
        reader = FlakyReader()
        service = JobService(
            storage_root=self.tempdir.name,
            reader=reader,
            reader_max_attempts=2,
        )
        client = TestClient(create_app(job_service=service))

        response = client.post(
            "/api/uploads",
            files=[("images", ("transient.png", image_bytes(), "image/png"))],
        )

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["status"], "completed")
        self.assertEqual(reader.calls, 2)

        events = read_log_events(service, body["jobId"])
        retry_events = [event for event in events if event["event"] == "reader_retry"]
        image_events = [event for event in events if event["event"] == "image_processed"]
        self.assertEqual(len(retry_events), 1)
        self.assertEqual(retry_events[0]["status"], "error")
        self.assertIn("temporary", retry_events[0]["error_message"])
        self.assertEqual(image_events[0]["attempts"], 2)
        self.assertEqual(image_events[0]["status"], "success")


class FlakyReader:
    def __init__(self):
        self.calls = 0

    def __call__(self, _image, *, source_filename=None):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary decoder failure")
        return success_reader(_image, source_filename=source_filename)


def success_reader(_image, *, source_filename=None):
    return [
        BarcodeResult(
            source_filename=source_filename or "",
            status="success",
            barcode_index=1,
            barcode_type="QRCode",
            decoded_text=f"decoded:{source_filename}",
        )
    ]


def image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (8, 8), "white").save(output, format="PNG")
    return output.getvalue()


def read_log_events(service: JobService, job_id: str) -> list[dict[str, object]]:
    log_path = service.storage.log_path(job_id)
    with log_path.open("r", encoding="utf-8") as log_file:
        return [json.loads(line) for line in log_file]


if __name__ == "__main__":
    unittest.main()
