from __future__ import annotations

import argparse
import csv
import importlib.metadata
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".jfif", ".png", ".bmp", ".tif", ".tiff"}

DETAIL_FIELDS = [
    "source_filename",
    "image_index",
    "decoder_name",
    "target_barcode_type",
    "variant",
    "barcode_index",
    "barcode_type",
    "decoded_text",
    "status",
    "elapsed_ms",
    "bbox_x",
    "bbox_y",
    "bbox_width",
    "bbox_height",
    "error_message",
]

SELECTED_FIELDS = [
    "job_id",
    "source_filename",
    "image_index",
    "barcode_index",
    "barcode_type",
    "decoded_text",
    "confidence",
    "bbox_x",
    "bbox_y",
    "bbox_width",
    "bbox_height",
    "status",
    "error_message",
]


@dataclass(frozen=True)
class LoadedImage:
    path: Path
    pil_image: object
    cv_image: object | None


@dataclass(frozen=True)
class DecodeResult:
    barcode_type: str
    decoded_text: str
    bbox: tuple[int, int, int, int] | None = None


@dataclass(frozen=True)
class Decoder:
    name: str
    package: str
    target_barcode_type: str
    decode: Callable[[LoadedImage], list[DecodeResult]]


@dataclass(frozen=True)
class DependencyStatus:
    package: str
    status: str
    version: str = ""
    detail: str = ""


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


def bbox_from_points(points: Iterable[object]) -> tuple[int, int, int, int] | None:
    coords: list[tuple[float, float]] = []
    for point in points:
        try:
            coords.append((float(point.x), float(point.y)))
        except AttributeError:
            try:
                coords.append((float(point[0]), float(point[1])))
            except (TypeError, ValueError, IndexError):
                continue
    if not coords:
        return None
    xs = [coord[0] for coord in coords]
    ys = [coord[1] for coord in coords]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    return (
        int(round(min_x)),
        int(round(min_y)),
        int(round(max_x - min_x)),
        int(round(max_y - min_y)),
    )


def bbox_from_zxing_position(position: object) -> tuple[int, int, int, int] | None:
    points = []
    for attr in ("top_left", "top_right", "bottom_right", "bottom_left"):
        try:
            points.append(getattr(position, attr))
        except AttributeError:
            return None
    return bbox_from_points(points)


def bbox_from_rect(rect: object) -> tuple[int, int, int, int] | None:
    if rect is None:
        return None
    try:
        return (int(rect.left), int(rect.top), int(rect.width), int(rect.height))
    except AttributeError:
        pass
    try:
        return (int(rect.x), int(rect.y), int(rect.width), int(rect.height))
    except AttributeError:
        return None


def make_zxing_decoder(target: str) -> tuple[Decoder | None, DependencyStatus]:
    try:
        import zxingcpp
    except Exception as exc:
        return None, DependencyStatus("zxing-cpp", "unavailable", detail=str(exc))

    if target == "DataMatrix":
        formats = [zxingcpp.BarcodeFormat.DataMatrix]
    elif target == "QRCode":
        formats = [zxingcpp.BarcodeFormat.QRCode]
    else:
        formats = [zxingcpp.BarcodeFormat.DataMatrix, zxingcpp.BarcodeFormat.QRCode]

    def decode(image: LoadedImage) -> list[DecodeResult]:
        results = zxingcpp.read_barcodes(image.pil_image, formats=formats)
        decoded: list[DecodeResult] = []
        for result in results:
            text = result.text or text_from_bytes(result.bytes)
            if not text:
                continue
            decoded.append(
                DecodeResult(
                    barcode_type=normalize_barcode_type(result.format),
                    decoded_text=text,
                    bbox=bbox_from_zxing_position(result.position),
                )
            )
        return decoded

    decoder = Decoder(
        name=f"zxing-cpp-{target.lower()}",
        package="zxing-cpp",
        target_barcode_type=target,
        decode=decode,
    )
    return decoder, DependencyStatus("zxing-cpp", "available", package_version("zxing-cpp"))


def make_opencv_qr_decoder() -> tuple[Decoder | None, DependencyStatus]:
    try:
        import cv2
    except Exception as exc:
        return None, DependencyStatus("opencv-python", "unavailable", detail=str(exc))

    def decode(image: LoadedImage) -> list[DecodeResult]:
        if image.cv_image is None:
            return []

        detector = cv2.QRCodeDetector()
        decoded: list[DecodeResult] = []

        try:
            ok, texts, points, _ = detector.detectAndDecodeMulti(image.cv_image)
        except cv2.error:
            ok, texts, points = False, (), None

        if ok and points is not None:
            for text, point_set in zip(texts, points):
                if text:
                    decoded.append(
                        DecodeResult(
                            barcode_type="QRCode",
                            decoded_text=text,
                            bbox=bbox_from_points(point_set),
                        )
                    )

        if decoded:
            return decoded

        text, points, _ = detector.detectAndDecode(image.cv_image)
        if text:
            bbox = None
            if points is not None:
                bbox = bbox_from_points(points.reshape(-1, 2))
            return [DecodeResult("QRCode", text, bbox)]

        return []

    decoder = Decoder("opencv-qrcode", "opencv-python", "QRCode", decode)
    return decoder, DependencyStatus("opencv-python", "available", package_version("opencv-python"))


def make_pylibdmtx_decoder() -> tuple[Decoder | None, DependencyStatus]:
    try:
        from pylibdmtx.pylibdmtx import decode as dmtx_decode
    except Exception as exc:
        return None, DependencyStatus("pylibdmtx", "unavailable", detail=str(exc))

    def decode(image: LoadedImage) -> list[DecodeResult]:
        decoded: list[DecodeResult] = []
        for result in dmtx_decode(image.pil_image):
            text = text_from_bytes(result.data)
            if text:
                decoded.append(DecodeResult("DataMatrix", text, bbox_from_rect(result.rect)))
        return decoded

    decoder = Decoder("pylibdmtx-datamatrix", "pylibdmtx", "DataMatrix", decode)
    return decoder, DependencyStatus("pylibdmtx", "available", package_version("pylibdmtx"))


def make_pyzbar_qr_decoder() -> tuple[Decoder | None, DependencyStatus]:
    try:
        from pyzbar.pyzbar import decode as zbar_decode
    except Exception as exc:
        return None, DependencyStatus("pyzbar", "unavailable", detail=str(exc))

    def decode(image: LoadedImage) -> list[DecodeResult]:
        decoded: list[DecodeResult] = []
        for result in zbar_decode(image.pil_image):
            if str(result.type).upper() != "QRCODE":
                continue
            text = text_from_bytes(result.data)
            if text:
                decoded.append(DecodeResult("QRCode", text, bbox_from_rect(result.rect)))
        return decoded

    decoder = Decoder("pyzbar-qrcode", "pyzbar", "QRCode", decode)
    return decoder, DependencyStatus("pyzbar", "available", package_version("pyzbar"))


def build_decoders() -> tuple[list[Decoder], list[DependencyStatus]]:
    decoder_builders = [
        lambda: make_zxing_decoder("DataMatrix"),
        lambda: make_zxing_decoder("QRCode"),
        make_opencv_qr_decoder,
        make_pylibdmtx_decoder,
        make_pyzbar_qr_decoder,
    ]
    decoders: list[Decoder] = []
    dependencies: list[DependencyStatus] = []
    seen_dependencies: set[str] = set()

    for build in decoder_builders:
        decoder, dependency = build()
        if dependency.package not in seen_dependencies:
            dependencies.append(dependency)
            seen_dependencies.add(dependency.package)
        if decoder is not None:
            decoders.append(decoder)

    return decoders, dependencies


def load_image(path: Path) -> LoadedImage:
    from PIL import Image, ImageOps

    image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    cv_image = None
    try:
        import cv2
        import numpy as np

        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    except Exception:
        cv_image = None
    return LoadedImage(path=path, pil_image=image, cv_image=cv_image)


def iter_images(sample_dir: Path) -> list[Path]:
    return [
        path
        for path in sorted(sample_dir.iterdir())
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]


def read_expected_statuses(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {row["source_filename"]: row["status"] for row in reader}


def detail_row(
    image_path: Path,
    image_index: int,
    decoder: Decoder,
    status: str,
    elapsed_ms: float,
    barcode_index: int = 0,
    result: DecodeResult | None = None,
    error_message: str = "",
) -> dict[str, object]:
    bbox = result.bbox if result and result.bbox else ("", "", "", "")
    return {
        "source_filename": image_path.name,
        "image_index": image_index,
        "decoder_name": decoder.name,
        "target_barcode_type": decoder.target_barcode_type,
        "variant": "original",
        "barcode_index": barcode_index or "",
        "barcode_type": result.barcode_type if result else "",
        "decoded_text": result.decoded_text if result else "",
        "status": status,
        "elapsed_ms": f"{elapsed_ms:.3f}",
        "bbox_x": bbox[0],
        "bbox_y": bbox[1],
        "bbox_width": bbox[2],
        "bbox_height": bbox[3],
        "error_message": error_message,
    }


def selected_row(
    job_id: str,
    image_path: Path,
    image_index: int,
    status: str,
    barcode_index: int = 0,
    result: DecodeResult | None = None,
    error_message: str = "",
) -> dict[str, object]:
    bbox = result.bbox if result and result.bbox else ("", "", "", "")
    return {
        "job_id": job_id,
        "source_filename": image_path.name,
        "image_index": image_index,
        "barcode_index": barcode_index or "",
        "barcode_type": result.barcode_type if result else "",
        "decoded_text": result.decoded_text if result else "",
        "confidence": "",
        "bbox_x": bbox[0],
        "bbox_y": bbox[1],
        "bbox_width": bbox[2],
        "bbox_height": bbox[3],
        "status": status,
        "error_message": error_message,
    }


def run_detailed_decode(
    image_paths: list[Path],
    decoders: list[Decoder],
) -> tuple[list[dict[str, object]], dict[str, list[float]]]:
    rows: list[dict[str, object]] = []
    timings: dict[str, list[float]] = {decoder.name: [] for decoder in decoders}

    for image_index, image_path in enumerate(image_paths, start=1):
        try:
            loaded = load_image(image_path)
        except Exception as exc:
            for decoder in decoders:
                rows.append(
                    detail_row(
                        image_path,
                        image_index,
                        decoder,
                        status="error",
                        elapsed_ms=0,
                        error_message=f"image load failed: {exc}",
                    )
                )
            continue

        for decoder in decoders:
            started = time.perf_counter()
            try:
                results = decoder.decode(loaded)
                elapsed_ms = (time.perf_counter() - started) * 1000
                timings[decoder.name].append(elapsed_ms)
                if results:
                    for barcode_index, result in enumerate(results, start=1):
                        rows.append(
                            detail_row(
                                image_path,
                                image_index,
                                decoder,
                                status="success",
                                elapsed_ms=elapsed_ms,
                                barcode_index=barcode_index,
                                result=result,
                            )
                        )
                else:
                    rows.append(
                        detail_row(
                            image_path,
                            image_index,
                            decoder,
                            status="not_found",
                            elapsed_ms=elapsed_ms,
                            error_message="barcode not found",
                        )
                    )
            except Exception as exc:
                elapsed_ms = (time.perf_counter() - started) * 1000
                timings[decoder.name].append(elapsed_ms)
                rows.append(
                    detail_row(
                        image_path,
                        image_index,
                        decoder,
                        status="error",
                        elapsed_ms=elapsed_ms,
                        error_message=f"{type(exc).__name__}: {exc}",
                    )
                )

    return rows, timings


def run_selected_decode(
    image_paths: list[Path],
    job_id: str,
) -> tuple[list[dict[str, object]], str]:
    decoder, dependency = make_zxing_decoder("all")
    if decoder is None:
        rows = [
            selected_row(
                job_id,
                image_path,
                image_index,
                status="error",
                error_message=f"selected decoder unavailable: {dependency.detail}",
            )
            for image_index, image_path in enumerate(image_paths, start=1)
        ]
        return rows, "zxing-cpp-all"

    rows: list[dict[str, object]] = []
    for image_index, image_path in enumerate(image_paths, start=1):
        try:
            loaded = load_image(image_path)
            results = decoder.decode(loaded)
            if results:
                for barcode_index, result in enumerate(results, start=1):
                    rows.append(
                        selected_row(
                            job_id,
                            image_path,
                            image_index,
                            status="success",
                            barcode_index=barcode_index,
                            result=result,
                        )
                    )
            else:
                rows.append(
                    selected_row(
                        job_id,
                        image_path,
                        image_index,
                        status="not_found",
                        error_message="barcode not found by selected decoder",
                    )
                )
        except Exception as exc:
            rows.append(
                selected_row(
                    job_id,
                    image_path,
                    image_index,
                    status="error",
                    error_message=f"{type(exc).__name__}: {exc}",
                )
            )
    return rows, "zxing-cpp-all"


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def summarize_status(rows: list[dict[str, object]], key: str) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for row in rows:
        bucket = str(row[key])
        status = str(row["status"])
        summary.setdefault(bucket, {})
        summary[bucket][status] = summary[bucket].get(status, 0) + 1
    return summary


def format_ms(values: list[float]) -> str:
    if not values:
        return ""
    return f"{statistics.mean(values):.3f}"


def write_summary(
    path: Path,
    image_paths: list[Path],
    dependencies: list[DependencyStatus],
    detail_rows: list[dict[str, object]],
    selected_rows: list[dict[str, object]],
    timings: dict[str, list[float]],
    expected_statuses: dict[str, str],
    detail_output: Path,
    selected_output: Path,
    selected_decoder_name: str,
) -> None:
    by_decoder = summarize_status(detail_rows, "decoder_name")
    success_rows = [row for row in selected_rows if row["status"] == "success"]
    unresolved_rows = [row for row in selected_rows if row["status"] != "success"]
    phase0_counts: dict[str, int] = {}
    for status in expected_statuses.values():
        phase0_counts[status] = phase0_counts.get(status, 0) + 1

    lines = [
        "# Phase 1 Decoder PoC Summary",
        "",
        "## Inputs",
        "",
        f"- Sample directory: `sample_images`",
        f"- Sample image count: {len(image_paths)}",
        f"- Phase 0 fixture statuses: {phase0_counts or 'not found'}",
        "",
        "## Dependency Availability",
        "",
        "| Package | Status | Version | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for dependency in dependencies:
        lines.append(
            f"| `{dependency.package}` | {dependency.status} | {dependency.version or ''} | {dependency.detail or ''} |"
        )

    lines.extend(
        [
            "",
            "## Detailed Decoder Results",
            "",
            f"- Detailed CSV: `{detail_output.as_posix()}`",
            f"- Selected result CSV: `{selected_output.as_posix()}`",
            "",
            "| Decoder | Target | Success Rows | Not Found Rows | Error Rows | Avg ms/image |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )

    decoder_targets = {
        str(row["decoder_name"]): str(row["target_barcode_type"]) for row in detail_rows
    }
    for decoder_name in sorted(by_decoder):
        counts = by_decoder[decoder_name]
        lines.append(
            "| "
            f"`{decoder_name}` | "
            f"{decoder_targets.get(decoder_name, '')} | "
            f"{counts.get('success', 0)} | "
            f"{counts.get('not_found', 0)} | "
            f"{counts.get('error', 0)} | "
            f"{format_ms(timings.get(decoder_name, []))} |"
        )

    lines.extend(
        [
            "",
            "## Selected Initial Reading",
            "",
            f"- Selected decoder combination: `{selected_decoder_name}` as the primary DataMatrix/QRCode reader.",
            "- Proposed Phase 2 fallback: keep `opencv-qrcode` available as a QR-specific fallback, then add preprocessing variants before retry.",
            "",
            "| Source File | Status | Barcode Type | Decoded Text |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in selected_rows:
        decoded_text = str(row["decoded_text"]).replace("|", "\\|")
        lines.append(
            f"| `{row['source_filename']}` | {row['status']} | {row['barcode_type']} | {decoded_text} |"
        )

    lines.extend(
        [
            "",
            "## Phase 0 Comparison",
            "",
            "- Phase 0 marked every sample as `needs_review`, so these PoC outputs should be manually reviewed before promoting them into `tests/fixtures/expected_results.csv`.",
            f"- Successful selected rows: {len(success_rows)}",
            f"- Unresolved selected rows: {len(unresolved_rows)}",
            "",
            "## Recommendation",
            "",
            "- Use `zxing-cpp` first for Data Matrix and QR Code because it matched the successful Data Matrix reads and was the fastest successful decoder in this sample run.",
            "- Keep `pylibdmtx` as an optional Data Matrix fallback only; it matched the successful Data Matrix reads but was much slower on this sample run.",
            "- Keep `pyzbar` out of the first implementation path for now; it imported successfully but produced no QR reads on the current sample set.",
            "- Carry the five unresolved sample images into Phase 2 preprocessing work: grayscale, threshold, scaling, rotation, and candidate crop retries.",
        ]
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 1 barcode decoder PoC.")
    parser.add_argument("--sample-dir", type=Path, default=Path("sample_images"))
    parser.add_argument("--expected", type=Path, default=Path("tests/fixtures/expected_results.csv"))
    parser.add_argument("--detail-output", type=Path, default=Path("reports/decoder-poc-results.csv"))
    parser.add_argument(
        "--selected-output",
        type=Path,
        default=Path("reports/decoder-poc-selected-results.csv"),
    )
    parser.add_argument("--summary-output", type=Path, default=Path("reports/decoder-poc-summary.md"))
    parser.add_argument("--job-id", default="phase1_poc")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    image_paths = iter_images(args.sample_dir)
    if not image_paths:
        print(f"No supported image files found in {args.sample_dir}", file=sys.stderr)
        return 1

    decoders, dependencies = build_decoders()
    if not decoders:
        print("No decoders are available. Install requirements.txt and retry.", file=sys.stderr)
        return 1

    detail_rows, timings = run_detailed_decode(image_paths, decoders)
    selected_rows, selected_decoder_name = run_selected_decode(image_paths, args.job_id)
    expected_statuses = read_expected_statuses(args.expected)

    write_csv(args.detail_output, detail_rows, DETAIL_FIELDS)
    write_csv(args.selected_output, selected_rows, SELECTED_FIELDS)
    write_summary(
        args.summary_output,
        image_paths,
        dependencies,
        detail_rows,
        selected_rows,
        timings,
        expected_statuses,
        args.detail_output,
        args.selected_output,
        selected_decoder_name,
    )

    success_count = sum(1 for row in selected_rows if row["status"] == "success")
    print(f"Processed {len(image_paths)} images with {len(decoders)} decoders.")
    print(f"Selected decoder successes: {success_count}/{len(image_paths)} images.")
    print(f"Wrote {args.detail_output}, {args.selected_output}, {args.summary_output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
