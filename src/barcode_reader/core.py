from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Iterable

from PIL import Image

from .decoders import DecoderAdapter, build_default_decoders
from .models import (
    BBox,
    BarcodeResult,
    STATUS_DECODE_FAILED,
    STATUS_ERROR,
    STATUS_NOT_FOUND,
    STATUS_SUCCESS,
)
from .preprocess import PreprocessVariant, generate_preprocess_variants, load_image


def read_barcodes(
    image: str | Path | Image.Image,
    *,
    source_filename: str | None = None,
    decoders: Iterable[DecoderAdapter] | None = None,
    enable_slow_fallback: bool = False,
) -> list[BarcodeResult]:
    try:
        loaded = load_image(image, source_filename=source_filename)
    except Exception as exc:
        return [
            BarcodeResult(
                source_filename=_fallback_source_filename(image, source_filename),
                status=STATUS_ERROR,
                error_message=f"image load failed: {type(exc).__name__}: {exc}",
            )
        ]

    decoder_list = (
        list(decoders)
        if decoders is not None
        else build_default_decoders(enable_slow_fallback=enable_slow_fallback)
    )
    if not decoder_list:
        return [
            BarcodeResult(
                source_filename=loaded.source_filename,
                status=STATUS_ERROR,
                error_message="no barcode decoders are available",
            )
        ]

    variants = generate_preprocess_variants(loaded)
    successes: list[BarcodeResult] = []
    saw_candidate = False
    errors: list[str] = []
    attempt_stats = {"attempted": 0, "completed": 0}

    normal_decoders = [decoder for decoder in decoder_list if not getattr(decoder, "is_slow", False)]
    slow_decoders = [decoder for decoder in decoder_list if getattr(decoder, "is_slow", False)]

    if normal_decoders:
        saw_candidate = _run_decode_plan(
            loaded.source_filename,
            loaded.width,
            loaded.height,
            variants,
            normal_decoders,
            successes,
            errors,
            attempt_stats,
            saw_candidate,
        )

    if (not normal_decoders or not successes) and slow_decoders:
        slow_variants = [variant for variant in variants if variant.is_slow_fallback_allowed]
        saw_candidate = _run_decode_plan(
            loaded.source_filename,
            loaded.width,
            loaded.height,
            slow_variants,
            slow_decoders,
            successes,
            errors,
            attempt_stats,
            saw_candidate,
        )

    deduped = _deduplicate_results(successes)
    if deduped:
        return [replace(result, barcode_index=index) for index, result in enumerate(deduped, start=1)]

    if saw_candidate:
        return [
            BarcodeResult(
                source_filename=loaded.source_filename,
                status=STATUS_DECODE_FAILED,
                error_message="barcode candidate could not be decoded",
            )
        ]

    if attempt_stats["attempted"] > 0 and attempt_stats["completed"] == 0 and errors:
        return [
            BarcodeResult(
                source_filename=loaded.source_filename,
                status=STATUS_ERROR,
                error_message="all decoder attempts failed: " + "; ".join(errors[:3]),
            )
        ]

    return [
        BarcodeResult(
            source_filename=loaded.source_filename,
            status=STATUS_NOT_FOUND,
            error_message="barcode not found",
        )
    ]


def _run_decode_plan(
    source_filename: str,
    image_width: int,
    image_height: int,
    variants: Iterable[PreprocessVariant],
    decoders: Iterable[DecoderAdapter],
    successes: list[BarcodeResult],
    errors: list[str],
    attempt_stats: dict[str, int],
    saw_candidate: bool,
) -> bool:
    for variant in variants:
        for decoder in decoders:
            attempt_stats["attempted"] += 1
            try:
                attempt = decoder.decode(variant)
            except Exception as exc:
                errors.append(f"{decoder.name}@{variant.name}: {type(exc).__name__}: {exc}")
                continue

            attempt_stats["completed"] += 1
            saw_candidate = saw_candidate or attempt.candidate_found
            for raw_result in attempt.results:
                if not raw_result.decoded_text:
                    saw_candidate = True
                    continue

                bbox = _map_and_clamp_bbox(raw_result.bbox, variant, image_width, image_height)
                successes.append(
                    BarcodeResult(
                        source_filename=source_filename,
                        status=STATUS_SUCCESS,
                        barcode_type=raw_result.barcode_type,
                        decoded_text=raw_result.decoded_text,
                        confidence=raw_result.confidence,
                        bbox=bbox,
                        decoder_name=decoder.name,
                        preprocess_variant=variant.name,
                    )
                )
    return saw_candidate


def _map_and_clamp_bbox(
    bbox: BBox | None,
    variant: PreprocessVariant,
    image_width: int,
    image_height: int,
) -> BBox | None:
    if bbox is None:
        return None
    mapped = variant.map_bbox(bbox)
    if mapped is None:
        return None
    return mapped.clamped(image_width, image_height)


def _deduplicate_results(results: Iterable[BarcodeResult]) -> list[BarcodeResult]:
    deduped: list[BarcodeResult] = []
    for result in results:
        duplicate_index = _find_duplicate_index(deduped, result)
        if duplicate_index is None:
            deduped.append(result)
            continue

        existing = deduped[duplicate_index]
        if _is_better_duplicate(result, existing):
            deduped[duplicate_index] = result
    return deduped


def _find_duplicate_index(results: list[BarcodeResult], candidate: BarcodeResult) -> int | None:
    for index, existing in enumerate(results):
        if _is_duplicate(existing, candidate):
            return index
    return None


def _is_duplicate(left: BarcodeResult, right: BarcodeResult) -> bool:
    if left.barcode_type != right.barcode_type:
        return False
    if left.decoded_text != right.decoded_text:
        return False

    if left.bbox is None or right.bbox is None:
        return True

    return left.bbox.is_near(right.bbox) or left.bbox.intersection_over_union(right.bbox) >= 0.50


def _is_better_duplicate(candidate: BarcodeResult, existing: BarcodeResult) -> bool:
    if existing.bbox is None and candidate.bbox is not None:
        return True
    if existing.confidence is None and candidate.confidence is not None:
        return True
    return False


def _fallback_source_filename(image: object, source_filename: str | None) -> str:
    if source_filename is not None:
        return source_filename
    if isinstance(image, (str, Path)):
        return Path(image).name
    return ""
