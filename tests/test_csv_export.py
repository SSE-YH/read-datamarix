from __future__ import annotations

import csv
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from barcode_reader import BBox, BarcodeResult
from barcode_reader.csv_export import (
    CSV_COLUMNS,
    ImageBarcodeResults,
    build_csv_rows,
    to_csv_string,
    write_results_csv,
)


class CsvExportTest(unittest.TestCase):
    def test_success_row_matches_fixed_schema(self):
        image_results = [
            ImageBarcodeResults(
                source_filename="image_01.jfif",
                image_index=1,
                results=[
                    BarcodeResult(
                        source_filename="image_01.jfif",
                        status="success",
                        barcode_index=1,
                        barcode_type="DataMatrix",
                        decoded_text="ABC123",
                        confidence=0.92,
                        bbox=BBox(120, 80, 64, 64),
                    )
                ],
            )
        ]

        text = to_csv_string("job_1", image_results)

        self.assertEqual(text.splitlines()[0], ",".join(CSV_COLUMNS))
        rows = list(csv.DictReader(io.StringIO(text)))
        self.assertEqual(rows[0]["job_id"], "job_1")
        self.assertEqual(rows[0]["source_filename"], "image_01.jfif")
        self.assertEqual(rows[0]["image_index"], "1")
        self.assertEqual(rows[0]["barcode_index"], "1")
        self.assertEqual(rows[0]["barcode_type"], "DataMatrix")
        self.assertEqual(rows[0]["decoded_text"], "ABC123")
        self.assertEqual(rows[0]["confidence"], "0.92")
        self.assertEqual(rows[0]["bbox_x"], "120")
        self.assertEqual(rows[0]["bbox_y"], "80")
        self.assertEqual(rows[0]["bbox_width"], "64")
        self.assertEqual(rows[0]["bbox_height"], "64")
        self.assertEqual(rows[0]["status"], "success")
        self.assertEqual(rows[0]["error_message"], "")

    def test_empty_image_results_create_not_found_row(self):
        rows = build_csv_rows(
            "job_1",
            [ImageBarcodeResults("empty.png", 2, [])],
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_filename"], "empty.png")
        self.assertEqual(rows[0]["image_index"], "2")
        self.assertEqual(rows[0]["barcode_index"], "")
        self.assertEqual(rows[0]["status"], "not_found")
        self.assertEqual(rows[0]["error_message"], "barcode not found")

    def test_failure_rows_are_kept(self):
        rows = build_csv_rows(
            "job_1",
            [
                ImageBarcodeResults(
                    "candidate.png",
                    1,
                    [
                        BarcodeResult(
                            source_filename="candidate.png",
                            status="decode_failed",
                            error_message="barcode candidate could not be decoded",
                        )
                    ],
                ),
                ImageBarcodeResults(
                    "broken.png",
                    2,
                    [
                        BarcodeResult(
                            source_filename="broken.png",
                            status="error",
                            error_message="image load failed",
                        )
                    ],
                ),
            ],
        )

        self.assertEqual([row["status"] for row in rows], ["decode_failed", "error"])
        self.assertEqual(rows[0]["error_message"], "barcode candidate could not be decoded")
        self.assertEqual(rows[1]["error_message"], "image load failed")

    def test_multiple_successes_are_sorted_and_indexed(self):
        rows = build_csv_rows(
            "job_1",
            [
                ImageBarcodeResults(
                    "multi.png",
                    1,
                    [
                        BarcodeResult(
                            source_filename="multi.png",
                            status="success",
                            barcode_index=2,
                            barcode_type="QRCode",
                            decoded_text="second",
                        ),
                        BarcodeResult(
                            source_filename="multi.png",
                            status="success",
                            barcode_type="DataMatrix",
                            decoded_text="assigned-first",
                        ),
                    ],
                )
            ],
        )

        self.assertEqual([row["decoded_text"] for row in rows], ["assigned-first", "second"])
        self.assertEqual([row["barcode_index"] for row in rows], ["1", "2"])

    def test_csv_writer_escapes_commas_quotes_and_newlines(self):
        decoded_text = 'A,"B"\nC'
        text = to_csv_string(
            "job_1",
            [
                ImageBarcodeResults(
                    "escaped.png",
                    1,
                    [
                        BarcodeResult(
                            source_filename="escaped.png",
                            status="success",
                            barcode_type="DataMatrix",
                            decoded_text=decoded_text,
                        )
                    ],
                )
            ],
        )

        rows = list(csv.DictReader(io.StringIO(text)))
        self.assertEqual(rows[0]["decoded_text"], decoded_text)

    def test_utf8_bom_option_is_available_for_file_writes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "results.csv"

            write_results_csv(
                path,
                "job_1",
                [ImageBarcodeResults("image.png", 1, [])],
                include_bom=True,
            )

            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))


if __name__ == "__main__":
    unittest.main()
