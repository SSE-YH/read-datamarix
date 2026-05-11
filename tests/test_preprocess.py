from __future__ import annotations

import sys
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from barcode_reader import BBox
from barcode_reader.preprocess import LoadedImage, generate_preprocess_variants


class PreprocessVariantTest(unittest.TestCase):
    def test_generates_up_2x_bilateral_global_histogram_variant(self):
        image = Image.new("RGB", (120, 80), "white")
        loaded = LoadedImage(
            source_path=None,
            source_filename="sample.png",
            pil_image=image,
            width=image.width,
            height=image.height,
        )

        variants = generate_preprocess_variants(loaded)
        by_name = {variant.name: variant for variant in variants}

        variant = by_name["up_2x_bilateral_global_histogram"]
        self.assertEqual(variant.pil_image.size, (240, 160))
        self.assertEqual(variant.zxing_binarizer, "GlobalHistogram")
        self.assertTrue(variant.is_slow_fallback_allowed)
        self.assertEqual(variant.map_bbox(BBox(20, 24, 40, 48)), BBox(10, 12, 20, 24))


if __name__ == "__main__":
    unittest.main()
