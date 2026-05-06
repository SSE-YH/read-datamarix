from __future__ import annotations

import importlib.metadata
from dataclasses import dataclass
from typing import Protocol

from .models import BBox
from .preprocess import PreprocessVariant


@dataclass(frozen=True)
class RawDecodeResult:
    barcode_type: str
    decoded_text: str
    bbox: BBox | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class DecodeAttempt:
    results: tuple[RawDecodeResult, ...] = ()
    candidate_found: bool = False


class DecoderAdapter(Protocol):
    name: str
    is_slow: bool

    def decode(self, variant: PreprocessVariant) -> DecodeAttempt:
        ...


def build_default_decoders(enable_slow_fallback: bool = False) -> list[DecoderAdapter]:
    decoders: list[DecoderAdapter] = []

    zxing = make_zxing_decoder()
    if zxing is not None:
        decoders.append(zxing)

    opencv_qr = make_opencv_qr_decoder()
    if opencv_qr is not None:
        decoders.append(opencv_qr)

    if enable_slow_fallback:
        pylibdmtx = make_pylibdmtx_decoder()
        if pylibdmtx is not None:
            decoders.append(pylibdmtx)

    return decoders


def make_zxing_decoder() -> DecoderAdapter | None:
    try:
        import zxingcpp
    except Exception:
        return None

    formats = [zxingcpp.BarcodeFormat.DataMatrix, zxingcpp.BarcodeFormat.QRCode]

    class ZxingDecoder:
        name = "zxing-cpp-all"
        is_slow = False

        def decode(self, variant: PreprocessVariant) -> DecodeAttempt:
            results: list[RawDecodeResult] = []
            for result in zxingcpp.read_barcodes(variant.pil_image, formats=formats):
                text = result.text or text_from_bytes(result.bytes)
                if not text:
                    continue
                results.append(
                    RawDecodeResult(
                        barcode_type=normalize_barcode_type(result.format),
                        decoded_text=text,
                        bbox=bbox_from_zxing_position(result.position),
                    )
                )
            return DecodeAttempt(tuple(results), candidate_found=bool(results))

    return ZxingDecoder()


def make_opencv_qr_decoder() -> DecoderAdapter | None:
    try:
        import cv2
    except Exception:
        return None

    class OpenCvQrDecoder:
        name = "opencv-qrcode"
        is_slow = False

        def decode(self, variant: PreprocessVariant) -> DecodeAttempt:
            if variant.cv_image is None:
                return DecodeAttempt()

            detector = cv2.QRCodeDetector()
            results: list[RawDecodeResult] = []
            candidate_found = False

            try:
                ok, texts, points, _ = detector.detectAndDecodeMulti(variant.cv_image)
            except cv2.error:
                ok, texts, points = False, (), None

            if ok and points is not None:
                candidate_found = True
                for text, point_set in zip(texts, points):
                    if text:
                        results.append(
                            RawDecodeResult(
                                barcode_type="QRCode",
                                decoded_text=text,
                                bbox=bbox_from_points(point_set),
                            )
                        )

            if results:
                return DecodeAttempt(tuple(results), candidate_found=True)

            text, points, _ = detector.detectAndDecode(variant.cv_image)
            if points is not None:
                candidate_found = True
            if text:
                return DecodeAttempt(
                    (
                        RawDecodeResult(
                            barcode_type="QRCode",
                            decoded_text=text,
                            bbox=bbox_from_points(points.reshape(-1, 2)) if points is not None else None,
                        ),
                    ),
                    candidate_found=True,
                )

            return DecodeAttempt(candidate_found=candidate_found)

    return OpenCvQrDecoder()


def make_pylibdmtx_decoder() -> DecoderAdapter | None:
    try:
        from pylibdmtx.pylibdmtx import decode as dmtx_decode
    except Exception:
        return None

    class PylibDmtxDecoder:
        name = "pylibdmtx-datamatrix"
        is_slow = True

        def decode(self, variant: PreprocessVariant) -> DecodeAttempt:
            results: list[RawDecodeResult] = []
            for result in dmtx_decode(variant.pil_image):
                text = text_from_bytes(result.data)
                if text:
                    results.append(
                        RawDecodeResult(
                            barcode_type="DataMatrix",
                            decoded_text=text,
                            bbox=bbox_from_rect(result.rect),
                        )
                    )
            return DecodeAttempt(tuple(results), candidate_found=bool(results))

    return PylibDmtxDecoder()


def package_version(package: str) -> str:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return ""


def normalize_barcode_type(value: object) -> str:
    text = str(value).replace("_", " ").replace("-", " ").strip().lower()
    if "data matrix" in text or "datamatrix" in text:
        return "DataMatrix"
    if "qr" in text:
        return "QRCode"
    return str(value).strip()


def text_from_bytes(data: bytes | str) -> str:
    if isinstance(data, str):
        return data
    for encoding in ("utf-8", "cp1250", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def bbox_from_points(points: object) -> BBox | None:
    coords: list[tuple[float, float]] = []
    for point in points:
        try:
            coords.append((float(point.x), float(point.y)))
            continue
        except AttributeError:
            pass
        try:
            coords.append((float(point[0]), float(point[1])))
        except (TypeError, ValueError, IndexError):
            continue
    return BBox.from_points(coords)


def bbox_from_zxing_position(position: object) -> BBox | None:
    points = []
    for attr in ("top_left", "top_right", "bottom_right", "bottom_left"):
        try:
            points.append(getattr(position, attr))
        except AttributeError:
            return None
    return bbox_from_points(points)


def bbox_from_rect(rect: object) -> BBox | None:
    if rect is None:
        return None
    try:
        return BBox(int(rect.left), int(rect.top), int(rect.width), int(rect.height))
    except AttributeError:
        pass
    try:
        return BBox(int(rect.x), int(rect.y), int(rect.width), int(rect.height))
    except AttributeError:
        return None
