# Phase 2 Core Processing Summary

## Deliverables

- Core API: `src/barcode_reader/core.py`
- Result model: `src/barcode_reader/models.py`
- Preprocessing pipeline: `src/barcode_reader/preprocess.py`
- Decoder adapters: `src/barcode_reader/decoders.py`
- Unit tests: `tests/test_core_reader.py`
- Design note: `docs/core-processing.md`

## API

```python
from barcode_reader import read_barcodes

results = read_barcodes("sample_images/image_01.jfif")
```

The API returns `list[BarcodeResult]` for both success and failure cases. Image load failures and total decoder failures are represented as `error` results instead of uncaught exceptions.

## Verification

- `python -m unittest discover -s tests -v`: 9 tests passed.
- `python -m compileall src tests`: passed.

## Sample Image Smoke Result

| Source File | Status | Barcode Type | Decoded Text | Variant | Decoder |
| --- | --- | --- | --- | --- | --- |
| `image_01.jfif` | `success` | `DataMatrix` | `X 4154 110503 1550 ...` | `original` | `zxing-cpp-all` |
| `image_02.jfif` | `decode_failed` |  |  |  |  |
| `image_03.jfif` | `success` | `DataMatrix` | `00520481760071281031611816` | `original` | `zxing-cpp-all` |
| `image_04.jfif` | `decode_failed` |  |  |  |  |
| `image_05.jfif` | `decode_failed` |  |  |  |  |
| `image_06.jfif` | `not_found` |  |  |  |  |
| `image_07.jpg` | `success` | `DataMatrix` | `ABCDEFG1234567` | `scale_2x` | `zxing-cpp-all` |

`image_07.jpg` is a Phase 2 improvement over the Phase 1 selected result because the scale retry made the Data Matrix readable.
