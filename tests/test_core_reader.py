from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from barcode_reader import BBox, read_barcodes
from barcode_reader.decoders import DecodeAttempt, RawDecodeResult


class FakeDecoder:
    name = "fake"
    is_slow = False

    def __init__(self, attempts: dict[str, DecodeAttempt] | None = None):
        self.attempts = attempts or {}
        self.calls: list[str] = []

    def decode(self, variant):
        self.calls.append(variant.name)
        return self.attempts.get(variant.name, DecodeAttempt())


class RaisingDecoder:
    name = "raising"
    is_slow = False

    def decode(self, variant):
        raise RuntimeError(f"boom on {variant.name}")


class CoreReaderTest(unittest.TestCase):
    def test_returns_success_and_tracks_variant(self):
        with temporary_image() as path:
            decoder = FakeDecoder(
                {
                    "adaptive_threshold": DecodeAttempt(
                        (
                            RawDecodeResult(
                                barcode_type="DataMatrix",
                                decoded_text="ABC123",
                                bbox=BBox(10, 12, 24, 24),
                            ),
                        ),
                        candidate_found=True,
                    )
                }
            )

            results = read_barcodes(path, decoders=[decoder])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "success")
        self.assertEqual(results[0].source_filename, "sample.png")
        self.assertEqual(results[0].barcode_index, 1)
        self.assertEqual(results[0].barcode_type, "DataMatrix")
        self.assertEqual(results[0].decoded_text, "ABC123")
        self.assertEqual(results[0].decoder_name, "fake")
        self.assertEqual(results[0].preprocess_variant, "adaptive_threshold")

    def test_returns_not_found_when_no_decoder_finds_code(self):
        with temporary_image() as path:
            results = read_barcodes(path, decoders=[FakeDecoder()])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "not_found")
        self.assertEqual(results[0].error_message, "barcode not found")

    def test_returns_decode_failed_when_candidate_has_no_text(self):
        with temporary_image() as path:
            decoder = FakeDecoder({"original": DecodeAttempt(candidate_found=True)})
            results = read_barcodes(path, decoders=[decoder])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "decode_failed")

    def test_returns_error_for_broken_image(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "broken.jpg"
            path.write_bytes(b"not an image")

            results = read_barcodes(path, decoders=[FakeDecoder()])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "error")
        self.assertIn("image load failed", results[0].error_message)

    def test_returns_error_when_all_decoder_attempts_raise(self):
        with temporary_image() as path:
            results = read_barcodes(path, decoders=[RaisingDecoder()])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "error")
        self.assertIn("all decoder attempts failed", results[0].error_message)

    def test_deduplicates_nearby_results_and_keeps_distinct_barcodes(self):
        with temporary_image(size=(140, 140)) as path:
            decoder = FakeDecoder(
                {
                    "original": DecodeAttempt(
                        (
                            RawDecodeResult("DataMatrix", "SAME", BBox(10, 10, 20, 20)),
                            RawDecodeResult("DataMatrix", "SAME", BBox(90, 90, 20, 20)),
                        ),
                        candidate_found=True,
                    ),
                    "grayscale": DecodeAttempt(
                        (RawDecodeResult("DataMatrix", "SAME", BBox(14, 13, 20, 20)),),
                        candidate_found=True,
                    ),
                }
            )

            results = read_barcodes(path, decoders=[decoder])

        self.assertEqual(len(results), 2)
        self.assertEqual([result.barcode_index for result in results], [1, 2])
        self.assertEqual([result.decoded_text for result in results], ["SAME", "SAME"])
        self.assertEqual(results[0].bbox, BBox(10, 10, 20, 20))
        self.assertEqual(results[1].bbox, BBox(90, 90, 20, 20))

    def test_clamps_bbox_to_image_bounds(self):
        with temporary_image(size=(50, 40)) as path:
            decoder = FakeDecoder(
                {
                    "original": DecodeAttempt(
                        (RawDecodeResult("QRCode", "Q", BBox(-10, -4, 80, 60)),),
                        candidate_found=True,
                    )
                }
            )

            results = read_barcodes(path, decoders=[decoder])

        self.assertEqual(results[0].bbox, BBox(0, 0, 50, 40))

    def test_slow_fallback_is_skipped_after_normal_success(self):
        with temporary_image() as path:
            normal = FakeDecoder(
                {
                    "original": DecodeAttempt(
                        (RawDecodeResult("QRCode", "fast", BBox(1, 1, 10, 10)),),
                        candidate_found=True,
                    )
                }
            )
            slow = FakeDecoder({"original": DecodeAttempt(candidate_found=True)})
            slow.name = "slow"
            slow.is_slow = True

            results = read_barcodes(path, decoders=[normal, slow])

        self.assertEqual(results[0].decoded_text, "fast")
        self.assertEqual(slow.calls, [])

    @unittest.skipUnless(importlib.util.find_spec("zxingcpp"), "zxing-cpp is not installed")
    def test_default_decoder_reads_phase1_success_sample(self):
        sample = ROOT / "sample_images" / "image_01.jfif"

        results = read_barcodes(sample)

        self.assertTrue(any(result.status == "success" for result in results))
        self.assertTrue(
            any("X 4154 110503 1550" in result.decoded_text for result in results),
            [result.decoded_text for result in results],
        )


class temporary_image:
    def __init__(self, size: tuple[int, int] = (100, 100)):
        self.size = size
        self.directory: tempfile.TemporaryDirectory[str] | None = None
        self.path: Path | None = None

    def __enter__(self) -> Path:
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "sample.png"
        Image.new("RGB", self.size, "white").save(self.path)
        return self.path

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self.directory is not None:
            self.directory.cleanup()


if __name__ == "__main__":
    unittest.main()
