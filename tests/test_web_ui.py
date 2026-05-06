from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from barcode_reader.api import create_app
from barcode_reader.jobs import JobService

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover - import guard for incomplete environments
    TestClient = None


@unittest.skipIf(TestClient is None, "fastapi test client is not available")
class WebUiTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.service = JobService(storage_root=self.tempdir.name, reader=lambda *_args, **_kwargs: [])
        self.client = TestClient(create_app(job_service=self.service))

    def tearDown(self):
        self.tempdir.cleanup()

    def test_upload_page_is_served_at_root_and_upload_path(self):
        for path in ["/", "/upload"]:
            response = self.client.get(path)

            self.assertEqual(response.status_code, 200)
            self.assertIn("text/html", response.headers["content-type"])
            self.assertIn("Barcode Reader", response.text)
            self.assertIn('id="dropzone"', response.text)
            self.assertIn('id="uploadButton"', response.text)

    def test_static_assets_are_served(self):
        script_response = self.client.get("/static/app.js")
        style_response = self.client.get("/static/styles.css")

        self.assertEqual(script_response.status_code, 200)
        self.assertIn("uploadSelectedFiles", script_response.text)
        self.assertEqual(style_response.status_code, 200)
        self.assertIn(".dropzone", style_response.text)


if __name__ == "__main__":
    unittest.main()
