from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence, TextIO

from .models import (
    BarcodeResult,
    STATUS_NOT_FOUND,
    STATUS_SUCCESS,
)


CSV_COLUMNS: tuple[str, ...] = (
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
)


@dataclass(frozen=True)
class ImageBarcodeResults:
    source_filename: str
    image_index: int
    results: Sequence[BarcodeResult]


def build_csv_rows(
    job_id: str,
    image_results: Iterable[ImageBarcodeResults],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for image_result in sorted(image_results, key=lambda item: item.image_index):
        rows.extend(_build_image_rows(job_id, image_result))
    return rows


def to_csv_string(
    job_id: str,
    image_results: Iterable[ImageBarcodeResults],
    *,
    include_bom: bool = False,
) -> str:
    output = io.StringIO(newline="")
    _write_rows(output, build_csv_rows(job_id, image_results))
    text = output.getvalue()
    if include_bom:
        return "\ufeff" + text
    return text


def write_results_csv(
    destination: str | Path | TextIO,
    job_id: str,
    image_results: Iterable[ImageBarcodeResults],
    *,
    include_bom: bool = False,
) -> None:
    rows = build_csv_rows(job_id, image_results)
    if hasattr(destination, "write"):
        if include_bom:
            destination.write("\ufeff")  # type: ignore[union-attr]
        _write_rows(destination, rows)  # type: ignore[arg-type]
        return

    encoding = "utf-8-sig" if include_bom else "utf-8"
    with Path(destination).open("w", encoding=encoding, newline="") as csv_file:
        _write_rows(csv_file, rows)


def _build_image_rows(
    job_id: str,
    image_result: ImageBarcodeResults,
) -> list[dict[str, str]]:
    results = list(image_result.results)
    if not results:
        results = [
            BarcodeResult(
                source_filename=image_result.source_filename,
                status=STATUS_NOT_FOUND,
                error_message="barcode not found",
            )
        ]

    rows: list[dict[str, str]] = []
    for result, assigned_index in _assign_and_sort_indexes(results):
        barcode_index = ""
        if result.status == STATUS_SUCCESS:
            barcode_index = str(assigned_index)

        rows.append(
            {
                "job_id": job_id,
                "source_filename": result.source_filename or image_result.source_filename,
                "image_index": str(image_result.image_index),
                "barcode_index": barcode_index,
                "barcode_type": result.barcode_type,
                "decoded_text": result.decoded_text,
                "confidence": _format_optional(result.confidence),
                "bbox_x": _format_optional(result.bbox.x if result.bbox else None),
                "bbox_y": _format_optional(result.bbox.y if result.bbox else None),
                "bbox_width": _format_optional(result.bbox.width if result.bbox else None),
                "bbox_height": _format_optional(result.bbox.height if result.bbox else None),
                "status": result.status,
                "error_message": result.error_message,
            }
        )
    return rows


def _assign_and_sort_indexes(results: Sequence[BarcodeResult]) -> list[tuple[BarcodeResult, int | None]]:
    used_indexes = {
        result.barcode_index
        for result in results
        if result.status == STATUS_SUCCESS and result.barcode_index is not None
    }
    next_index = 1
    indexed_results: list[tuple[int, BarcodeResult, int | None]] = []
    for original_index, result in enumerate(results):
        assigned_index = None
        if result.status == STATUS_SUCCESS:
            if result.barcode_index is not None:
                assigned_index = result.barcode_index
            else:
                while next_index in used_indexes:
                    next_index += 1
                assigned_index = next_index
                used_indexes.add(assigned_index)
                next_index += 1
        indexed_results.append((original_index, result, assigned_index))

    ordered = sorted(
        indexed_results,
        key=lambda item: (
            item[2] is None,
            item[2] or 0,
            item[0],
        ),
    )
    return [(result, assigned_index) for _, result, assigned_index in ordered]


def _format_optional(value: object | None) -> str:
    if value is None:
        return ""
    return str(value)


def _write_rows(destination: TextIO, rows: Sequence[dict[str, str]]) -> None:
    writer = csv.DictWriter(
        destination,
        fieldnames=CSV_COLUMNS,
        lineterminator="\n",
        extrasaction="ignore",
    )
    writer.writeheader()
    writer.writerows(rows)
