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
from barcode_reader.jobs import JobService
from barcode_reader.models import BarcodeResult

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover - import guard for incomplete environments
    TestClient = None


@unittest.skipIf(TestClient is None, "fastapi test client is not available")
class FailureCasesTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_corrupted_image_upload_is_rejected_before_job_creation(self):
        service = JobService(storage_root=self.tempdir.name, reader=success_reader)
        client = TestClient(create_app(job_service=service))
        corrupt_image = (ROOT / "tests" / "fixtures" / "corrupt-image.jpg").read_bytes()

        response = client.post(
            "/api/uploads",
            files=[("images", ("corrupt-image.jpg", corrupt_image, "image/jpeg"))],
        )

        self.assertEqual(response.status_code, 400)
        errors = response.json()["detail"]["errors"]
        self.assertEqual(errors[0]["code"], "invalid_image")
        self.assertEqual(list(Path(self.tempdir.name).glob("job_*")), [])

    def test_empty_reader_result_becomes_not_found_csv_row(self):
        service = JobService(storage_root=self.tempdir.name, reader=lambda *_args, **_kwargs: [])
        client = TestClient(create_app(job_service=service))

        response = client.post(
            "/api/uploads",
            files=[("images", ("blank.png", image_bytes(), "image/png"))],
        )

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["status"], "failed")
        self.assertEqual(body["images"][0]["status"], "not_found")
        self.assertEqual(body["images"][0]["errorMessage"], "barcode not found")

        csv_response = client.get(body["links"]["csv"])
        rows = list(csv.DictReader(io.StringIO(csv_response.text)))
        self.assertEqual(rows[0]["status"], "not_found")
        self.assertEqual(rows[0]["error_message"], "barcode not found")

    def test_multiple_barcodes_are_kept_as_separate_csv_rows(self):
        service = JobService(storage_root=self.tempdir.name, reader=multi_reader)
        client = TestClient(create_app(job_service=service))

        response = client.post(
            "/api/uploads",
            files=[("images", ("multi.png", image_bytes(), "image/png"))],
        )

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["status"], "completed")
        self.assertEqual(body["resultCount"], 2)

        csv_response = client.get(body["links"]["csv"])
        rows = list(csv.DictReader(io.StringIO(csv_response.text)))
        self.assertEqual([row["barcode_index"] for row in rows], ["1", "2"])
        self.assertEqual([row["decoded_text"] for row in rows], ["first", "second"])

    def test_decode_failure_and_reader_exception_remain_distinct(self):
        service = JobService(storage_root=self.tempdir.name, reader=decode_or_raise_reader)
        client = TestClient(create_app(job_service=service))

        response = client.post(
            "/api/uploads",
            files=[
                ("images", ("candidate.png", image_bytes(), "image/png")),
                ("images", ("system.png", image_bytes(), "image/png")),
            ],
        )

        self.assertEqual(response.status_code, 202)
        body = response.json()
        self.assertEqual(body["status"], "failed")
        self.assertEqual(
            [image["status"] for image in body["images"]],
            ["decode_failed", "error"],
        )

        csv_response = client.get(body["links"]["csv"])
        rows = list(csv.DictReader(io.StringIO(csv_response.text)))
        self.assertEqual([row["status"] for row in rows], ["decode_failed", "error"])
        self.assertEqual(rows[0]["error_message"], "barcode candidate could not be decoded")
        self.assertIn("processing failed: RuntimeError: boom", rows[1]["error_message"])


def success_reader(_image, *, source_filename=None):
    return [
        BarcodeResult(
            source_filename=source_filename or "",
            status="success",
            barcode_type="QRCode",
            decoded_text="ok",
        )
    ]


def multi_reader(_image, *, source_filename=None):
    return [
        BarcodeResult(
            source_filename=source_filename or "",
            status="success",
            barcode_index=1,
            barcode_type="DataMatrix",
            decoded_text="first",
        ),
        BarcodeResult(
            source_filename=source_filename or "",
            status="success",
            barcode_index=2,
            barcode_type="QRCode",
            decoded_text="second",
        ),
    ]


def decode_or_raise_reader(_image, *, source_filename=None):
    if source_filename == "candidate.png":
        return [
            BarcodeResult(
                source_filename=source_filename,
                status="decode_failed",
                error_message="barcode candidate could not be decoded",
            )
        ]
    raise RuntimeError("boom")


def image_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(output, format="PNG")
    return output.getvalue()


if __name__ == "__main__":
    unittest.main()
