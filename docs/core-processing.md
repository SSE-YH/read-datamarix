# Phase 2 Core Processing

Phase 2는 HTTP/API나 CSV 생성 없이 이미지 하나를 읽어 구조화된 `BarcodeResult` 목록으로 반환하는 core library를 제공한다.

## Public API

```python
from barcode_reader import read_barcodes

results = read_barcodes("sample_images/image_01.jfif")
```

`read_barcodes(image)`는 `str`, `Path`, `PIL.Image.Image` 입력을 받을 수 있다. 반환값은 항상 `list[BarcodeResult]`이며, 실패도 예외 대신 실패 row 1개로 표현한다.

## Result Fields

- `source_filename`
- `barcode_index`
- `barcode_type`
- `decoded_text`
- `confidence`
- `bbox`
- `status`
- `error_message`
- `decoder_name`
- `preprocess_variant`

## Pipeline

1. 이미지 로딩 및 EXIF orientation 보정
2. 전처리 variant 생성
3. decoder adapter 실행
4. 원본 이미지 기준 bbox 보정 및 범위 clamp
5. `barcode_type + decoded_text + bbox 근접값` 기준 중복 제거
6. `barcode_index` 재부여

## Preprocess Variants

- `original`
- `grayscale`
- `sharpen`
- `adaptive_threshold`
- `scale_2x`
- `scale_2x_adaptive_threshold`
- `scale_3x`
- `scale_3x_adaptive_threshold`
- `rotate_90`
- `rotate_180`
- `rotate_270`
- `crop_center_80`
- `crop_top_left`
- `crop_top_right`
- `crop_bottom_left`
- `crop_bottom_right`

## Decoder Priority

- Primary: `zxing-cpp-all` for Data Matrix and QR Code
- QR fallback: `opencv-qrcode`
- Optional slow fallback: `pylibdmtx-datamatrix`, enabled with `read_barcodes(..., enable_slow_fallback=True)`

`pylibdmtx` is kept optional because Phase 1 showed matching Data Matrix reads but much slower processing time.

## Failure Reasons

| Status | Runtime Meaning | Typical `error_message` |
| --- | --- | --- |
| `success` | A barcode type and decoded text were read. | empty |
| `not_found` | Image processing completed but no target barcode was detected. | `barcode not found` |
| `decode_failed` | A candidate was detected but no text could be decoded. | `barcode candidate could not be decoded` |
| `error` | Image loading or every decoder attempt failed. | `image load failed: ...`, `all decoder attempts failed: ...` |

Phase 3 can convert these `BarcodeResult` objects into the fixed CSV schema without changing field names.
