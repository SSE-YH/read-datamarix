from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image, ImageFilter, ImageOps

from .models import BBox


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".jfif", ".png", ".bmp", ".tif", ".tiff"}

BBoxMapper = Callable[[BBox | None], BBox | None]


@dataclass(frozen=True)
class LoadedImage:
    source_path: Path | None
    source_filename: str
    pil_image: Image.Image
    width: int
    height: int


@dataclass(frozen=True)
class PreprocessVariant:
    name: str
    pil_image: Image.Image
    cv_image: object | None
    map_bbox: BBoxMapper
    is_slow_fallback_allowed: bool = False
    zxing_binarizer: str | None = None


def load_image(image: str | Path | Image.Image, source_filename: str | None = None) -> LoadedImage:
    source_path: Path | None = None

    if isinstance(image, Image.Image):
        pil_image = ImageOps.exif_transpose(image).convert("RGB")
        filename = source_filename or ""
    else:
        source_path = Path(image)
        filename = source_filename or source_path.name
        with Image.open(source_path) as opened:
            pil_image = ImageOps.exif_transpose(opened).convert("RGB")

    return LoadedImage(
        source_path=source_path,
        source_filename=filename,
        pil_image=pil_image,
        width=pil_image.width,
        height=pil_image.height,
    )


def generate_preprocess_variants(loaded: LoadedImage) -> list[PreprocessVariant]:
    image = loaded.pil_image
    variants: list[PreprocessVariant] = [
        _variant("original", image, _identity_bbox, is_slow_fallback_allowed=True),
    ]

    grayscale = ImageOps.grayscale(image).convert("RGB")
    variants.append(
        _variant("grayscale", grayscale, _identity_bbox, is_slow_fallback_allowed=True)
    )

    sharpened = image.filter(ImageFilter.UnsharpMask(radius=1.2, percent=180, threshold=3))
    variants.append(_variant("sharpen", sharpened, _identity_bbox, is_slow_fallback_allowed=True))

    threshold = _adaptive_threshold(image)
    variants.append(
        _variant("adaptive_threshold", threshold, _identity_bbox, is_slow_fallback_allowed=True)
    )

    for scale in (2.0, 3.0):
        if max(image.size) * scale > 5000:
            continue
        scaled = _resize(image, scale)
        variants.append(
            _variant(
                f"scale_{scale:g}x",
                scaled,
                _scale_bbox_mapper(scale),
                is_slow_fallback_allowed=scale == 2.0,
            )
        )

        if scale == 2.0:
            up_2x_bilateral = _bilateral_filter(scaled)
            variants.append(
                _variant(
                    "up_2x_bilateral_global_histogram",
                    up_2x_bilateral,
                    _scale_bbox_mapper(scale),
                    is_slow_fallback_allowed=True,
                    zxing_binarizer="GlobalHistogram",
                )
            )

        scaled_threshold = _adaptive_threshold(scaled)
        variants.append(
            _variant(
                f"scale_{scale:g}x_adaptive_threshold",
                scaled_threshold,
                _scale_bbox_mapper(scale),
                is_slow_fallback_allowed=scale == 2.0,
            )
        )

    for angle in (90, 180, 270):
        rotated = image.rotate(angle, expand=True)
        variants.append(
            _variant(
                f"rotate_{angle}",
                rotated,
                _rotation_bbox_mapper(angle, loaded.width, loaded.height),
            )
        )

    variants.extend(_crop_variants(image))
    return variants


def pil_to_cv(pil_image: Image.Image) -> object | None:
    try:
        import cv2
        import numpy as np
    except Exception:
        return None

    array = np.array(pil_image.convert("RGB"))
    return cv2.cvtColor(array, cv2.COLOR_RGB2BGR)


def _variant(
    name: str,
    pil_image: Image.Image,
    map_bbox: BBoxMapper,
    is_slow_fallback_allowed: bool = False,
    zxing_binarizer: str | None = None,
) -> PreprocessVariant:
    return PreprocessVariant(
        name=name,
        pil_image=pil_image,
        cv_image=pil_to_cv(pil_image),
        map_bbox=map_bbox,
        is_slow_fallback_allowed=is_slow_fallback_allowed,
        zxing_binarizer=zxing_binarizer,
    )


def _identity_bbox(bbox: BBox | None) -> BBox | None:
    return bbox


def _resize(image: Image.Image, scale: float) -> Image.Image:
    try:
        resample = Image.Resampling.BICUBIC
    except AttributeError:
        resample = Image.BICUBIC
    return image.resize(
        (max(1, int(round(image.width * scale))), max(1, int(round(image.height * scale)))),
        resample=resample,
    )


def _adaptive_threshold(image: Image.Image) -> Image.Image:
    try:
        import cv2
        import numpy as np

        gray = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
        threshold = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            7,
        )
        return Image.fromarray(threshold).convert("RGB")
    except Exception:
        grayscale = ImageOps.grayscale(image)
        threshold = grayscale.point(lambda pixel: 255 if pixel > 160 else 0)
        return threshold.convert("RGB")


def _bilateral_filter(image: Image.Image) -> Image.Image:
    try:
        import cv2
        import numpy as np

        rgb = np.array(image.convert("RGB"))
        filtered = cv2.bilateralFilter(rgb, d=7, sigmaColor=45, sigmaSpace=45)
        return Image.fromarray(filtered).convert("RGB")
    except Exception:
        return image.filter(ImageFilter.SMOOTH_MORE)


def _scale_bbox_mapper(scale: float) -> BBoxMapper:
    def map_bbox(bbox: BBox | None) -> BBox | None:
        if bbox is None:
            return None
        return BBox(
            x=int(round(bbox.x / scale)),
            y=int(round(bbox.y / scale)),
            width=int(round(bbox.width / scale)),
            height=int(round(bbox.height / scale)),
        )

    return map_bbox


def _rotation_bbox_mapper(angle: int, original_width: int, original_height: int) -> BBoxMapper:
    def map_point(x: float, y: float) -> tuple[float, float]:
        if angle == 90:
            return original_width - y, x
        if angle == 180:
            return original_width - x, original_height - y
        if angle == 270:
            return y, original_height - x
        return x, y

    def map_bbox(bbox: BBox | None) -> BBox | None:
        if bbox is None:
            return None
        return BBox.from_points(map_point(x, y) for x, y in bbox.corners())

    return map_bbox


def _crop_variants(image: Image.Image) -> list[PreprocessVariant]:
    width, height = image.size
    if width < 80 or height < 80:
        return []

    crop_specs = [
        ("crop_center_80", int(width * 0.10), int(height * 0.10), int(width * 0.90), int(height * 0.90)),
        ("crop_top_left", 0, 0, int(width * 0.60), int(height * 0.60)),
        ("crop_top_right", int(width * 0.40), 0, width, int(height * 0.60)),
        ("crop_bottom_left", 0, int(height * 0.40), int(width * 0.60), height),
        ("crop_bottom_right", int(width * 0.40), int(height * 0.40), width, height),
    ]

    variants: list[PreprocessVariant] = []
    for name, left, top, right, bottom in crop_specs:
        if right <= left or bottom <= top:
            continue
        cropped = image.crop((left, top, right, bottom))
        variants.append(_variant(name, cropped, _crop_bbox_mapper(left, top)))
    return variants


def _crop_bbox_mapper(offset_x: int, offset_y: int) -> BBoxMapper:
    def map_bbox(bbox: BBox | None) -> BBox | None:
        if bbox is None:
            return None
        return BBox(
            x=bbox.x + offset_x,
            y=bbox.y + offset_y,
            width=bbox.width,
            height=bbox.height,
        )

    return map_bbox
