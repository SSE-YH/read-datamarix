from __future__ import annotations

import csv
import importlib.util
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from barcode_reader import read_barcodes
from barcode_reader.csv_export import CSV_COLUMNS, ImageBarcodeResults, to_csv_string


EXPECTED_SAMPLE_RESULTS = {
    "image_01.jfif": {
        "status": "success",
        "barcode_type": "DataMatrix",
        "decoded_text_contains": "X 4154 110503 1550",
    },
    "image_02.jfif": {"status": "decode_failed"},
    "image_03.jfif": {
        "status": "success",
        "barcode_type": "DataMatrix",
        "decoded_text_contains": "00520481760071281031611816",
    },
    "image_04.jfif": {"status": "decode_failed"},
    "image_05.jfif": {"status": "decode_failed"},
    "image_06.jfif": {"status": "not_found"},
    "image_07.jpg": {
        "status": "success",
        "barcode_type": "DataMatrix",
        "decoded_text_contains": "ABCDEFG1234567",
    },
}


@unittest.skipUnless(importlib.util.find_spec("zxingcpp"), "zxing-cpp is not installed")
class SampleRegressionTest(unittest.TestCase):
    def test_sample_images_match_phase2_baseline_and_csv_schema(self):
        image_results: list[ImageBarcodeResults] = []

        for image_index, source_filename in enumerate(EXPECTED_SAMPLE_RESULTS, start=1):
            sample_path = ROOT / "sample_images" / source_filename
            expected = EXPECTED_SAMPLE_RESULTS[source_filename]

            results = read_barcodes(sample_path)
            image_results.append(
                ImageBarcodeResults(
                    source_filename=source_filename,
                    image_index=image_index,
                    results=results,
                )
            )

            if expected["status"] == "success":
                successes = [result for result in results if result.status == "success"]
                self.assertTrue(successes, source_filename)
                self.assertEqual(successes[0].barcode_type, expected["barcode_type"])
                self.assertIn(expected["decoded_text_contains"], successes[0].decoded_text)
            else:
                self.assertEqual(len(results), 1, source_filename)
                self.assertEqual(results[0].status, expected["status"], source_filename)

        text = to_csv_string("phase6_regression", image_results)
        self.assertEqual(text.splitlines()[0], ",".join(CSV_COLUMNS))

        rows = list(csv.DictReader(io.StringIO(text)))
        self.assertEqual(len(rows), len(EXPECTED_SAMPLE_RESULTS))
        self.assertEqual([row["source_filename"] for row in rows], list(EXPECTED_SAMPLE_RESULTS))

        for row in rows:
            expected = EXPECTED_SAMPLE_RESULTS[row["source_filename"]]
            self.assertEqual(row["status"], expected["status"], row["source_filename"])
            if expected["status"] == "success":
                self.assertEqual(row["barcode_type"], expected["barcode_type"])
                self.assertIn(expected["decoded_text_contains"], row["decoded_text"])
            else:
                self.assertEqual(row["barcode_index"], "")
                self.assertNotEqual(row["error_message"], "")


if __name__ == "__main__":
    unittest.main()
