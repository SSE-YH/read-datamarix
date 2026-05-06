# Phase 3 CSV Result Engine Summary

## Deliverables

- CSV export module: `src/barcode_reader/csv_export.py`
- Public package exports: `src/barcode_reader/__init__.py`
- Unit tests: `tests/test_csv_export.py`
- Design note: `docs/csv-export.md`
- Sample CSV output: `reports/sample-output.csv`

## API

```python
from barcode_reader import ImageBarcodeResults, read_barcodes, to_csv_string, write_results_csv

image_results = [
    ImageBarcodeResults("image_01.jfif", 1, read_barcodes("sample_images/image_01.jfif"))
]

csv_text = to_csv_string("job_id", image_results)
write_results_csv("results.csv", "job_id", image_results)
```

Both APIs accept `include_bom=True` when UTF-8 BOM output is needed.

## Verification

- `python -m unittest discover -s tests -v`: 15 tests passed.
- `python -m compileall src tests`: passed.

## Sample Image Export

`reports/sample-output.csv` was generated from all 7 files in `sample_images`
using `read_barcodes` from Phase 2 and the Phase 3 exporter.

The generated CSV includes:

- 3 `success` rows
- 3 `decode_failed` rows
- 1 `not_found` row
- 0 dropped images

## Handoff to Phase 4

Use `to_csv_string` for HTTP download responses when no intermediate CSV file is
needed. Use `write_results_csv` when the backend stores a generated CSV artifact
for a job.
