# CSV Export

Phase 3 converts per-image `BarcodeResult` values from the core reader into the
fixed CSV schema used by later API and download phases.

## Public API

```python
from barcode_reader import ImageBarcodeResults, read_barcodes, write_results_csv

image_results = [
    ImageBarcodeResults(
        source_filename="image_01.jfif",
        image_index=1,
        results=read_barcodes("sample_images/image_01.jfif"),
    )
]

write_results_csv("reports/sample-output.csv", "job_20260506_001", image_results)
```

For in-memory responses, use `to_csv_string(job_id, image_results)`.

## Row Policy

- Header order is defined by `CSV_COLUMNS` in `src/barcode_reader/csv_export.py`.
- Every image produces at least one row.
- If an image has no results, the exporter writes one `not_found` row.
- Success rows receive a 1-based `barcode_index`. Existing indexes from the core
  reader are preserved, and missing indexes are filled deterministically.
- BBox and confidence fields are left blank when unavailable.
- Failure rows keep `status` and `error_message` while barcode fields remain blank.

## Encoding

The default file encoding is UTF-8 without BOM. If Excel compatibility requires
a BOM, pass `include_bom=True` to `to_csv_string` or `write_results_csv`.
