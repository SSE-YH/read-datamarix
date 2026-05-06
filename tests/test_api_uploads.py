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
from barcode_reader.jobs import JobService, MAX_UPLOAD_IMAGES
from barcode_reader.models import BarcodeResult

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover - import guard for incomplete environments
    TestClient = None


@unittest.skipIf(TestClient is None, "fastapi test client is not available")
class ApiUploadTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.service = JobService(storage_root=self.tempdir.name, reader=self.fake_reader)
        self.client = TestClient(create_app(job_service=self.service))

    def tearDown(self):
        self.tempdir.cleanup()

    def fake_reader(self, image, *, source_filename=None):
        if source_filename == "missing.png":
            return [
                BarcodeResult(
                    source_filename=source_filename or "",
                    status="not_found",
                    error_message="barcode not found",
                )
            ]
        return [
            BarcodeResult(
                source_filename=source_filename or "",
                status="success",
                barcode_index=1,
                barcode_type="QRCode",
                decoded_text=f"decoded:{source_filename}",
            )
        ]

    def test_uploads_multiple_images_and_downloads_csv(self):
        response = self.client.post(
            "/api/uploads",
            files=[
                ("images", ("one.png", image_bytes("PNG"), "image/png")),
                ("images", ("two.jpg", image_bytes("JPEG"), "image/jpeg")),
            ],
        )

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertTrue(body["jobId"].startswith("job_"))
        self.assertEqual(body["status"], "completed")
        self.assertEqual(body["totalImages"], 2)
        self.assertEqual(body["processedImages"], 2)
        self.assertEqual(body["successCount"], 2)
        self.assertTrue(body["csvReady"])

        status_response = self.client.get(body["links"]["status"])
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["jobId"], body["jobId"])

        csv_response = self.client.get(body["links"]["csv"])
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("text/csv", csv_response.headers["content-type"])
        rows = list(csv.DictReader(io.StringIO(csv_response.text)))
        self.assertEqual([row["source_filename"] for row in rows], ["one.png", "two.jpg"])
        self.assertEqual([row["decoded_text"] for row in rows], ["decoded:one.png", "decoded:two.jpg"])

    def test_partial_failed_upload_keeps_failure_row_in_csv(self):
        response = self.client.post(
            "/api/uploads",
            files=[
                ("images", ("ok.png", image_bytes("PNG"), "image/png")),
                ("images", ("missing.png", image_bytes("PNG"), "image/png")),
            ],
        )

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["status"], "partial_failed")
        self.assertEqual(body["successCount"], 1)
        self.assertEqual(body["failureCount"], 1)

        csv_response = self.client.get(body["links"]["csv"])
        rows = list(csv.DictReader(io.StringIO(csv_response.text)))
        self.assertEqual([row["status"] for row in rows], ["success", "not_found"])
        self.assertEqual(rows[1]["error_message"], "barcode not found")

    def test_rejects_empty_upload(self):
        response = self.client.post("/api/uploads")

        self.assertEqual(response.status_code, 400)
        detail = response.json()["detail"]
        self.assertEqual(detail["errors"][0]["code"], "no_files")

    def test_rejects_invalid_file_extension_and_mime_type(self):
        response = self.client.post(
            "/api/uploads",
            files=[("images", ("notes.txt", b"not an image", "text/plain"))],
        )

        self.assertEqual(response.status_code, 400)
        codes = {error["code"] for error in response.json()["detail"]["errors"]}
        self.assertIn("unsupported_extension", codes)
        self.assertIn("unsupported_mime_type", codes)

    def test_rejects_empty_file(self):
        response = self.client.post(
            "/api/uploads",
            files=[("images", ("empty.png", b"", "image/png"))],
        )

        self.assertEqual(response.status_code, 400)
        codes = {error["code"] for error in response.json()["detail"]["errors"]}
        self.assertIn("empty_file", codes)

    def test_rejects_upload_count_limit(self):
        files = [
            ("images", (f"image_{index}.png", image_bytes("PNG"), "image/png"))
            for index in range(MAX_UPLOAD_IMAGES + 1)
        ]

        response = self.client.post("/api/uploads", files=files)

        self.assertEqual(response.status_code, 400)
        codes = {error["code"] for error in response.json()["detail"]["errors"]}
        self.assertIn("too_many_files", codes)


def image_bytes(image_format: str) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(output, format=image_format)
    return output.getvalue()


if __name__ == "__main__":
    unittest.main()
