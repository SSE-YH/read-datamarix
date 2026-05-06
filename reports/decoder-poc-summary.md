# Phase 1 Decoder PoC Summary

## Inputs

- Sample directory: `sample_images`
- Sample image count: 7
- Phase 0 fixture statuses: {'needs_review': 7}

## Dependency Availability

| Package | Status | Version | Detail |
| --- | --- | --- | --- |
| `zxing-cpp` | available | 3.0.0 |  |
| `opencv-python` | available | 4.13.0.92 |  |
| `pylibdmtx` | available | 0.1.10 |  |
| `pyzbar` | available | 0.1.9 |  |

## Detailed Decoder Results

- Detailed CSV: `reports/decoder-poc-results.csv`
- Selected result CSV: `reports/decoder-poc-selected-results.csv`

| Decoder | Target | Success Rows | Not Found Rows | Error Rows | Avg ms/image |
| --- | --- | ---: | ---: | ---: | ---: |
| `opencv-qrcode` | QRCode | 0 | 7 | 0 | 17.514 |
| `pylibdmtx-datamatrix` | DataMatrix | 2 | 5 | 0 | 2270.177 |
| `pyzbar-qrcode` | QRCode | 0 | 7 | 0 | 9.610 |
| `zxing-cpp-datamatrix` | DataMatrix | 2 | 5 | 0 | 2.679 |
| `zxing-cpp-qrcode` | QRCode | 0 | 7 | 0 | 1.221 |

## Selected Initial Reading

- Selected decoder combination: `zxing-cpp-all` as the primary DataMatrix/QRCode reader.
- Proposed Phase 2 fallback: keep `opencv-qrcode` available as a QR-specific fallback, then add preprocessing variants before retry.

| Source File | Status | Barcode Type | Decoded Text |
| --- | --- | --- | --- |
| `image_01.jfif` | success | DataMatrix | X 4154 110503 1550 N°000010 0.200 2.550 13.0 82.0 |
| `image_02.jfif` | not_found |  |  |
| `image_03.jfif` | success | DataMatrix | 00520481760071281031611816 |
| `image_04.jfif` | not_found |  |  |
| `image_05.jfif` | not_found |  |  |
| `image_06.jfif` | not_found |  |  |
| `image_07.jpg` | not_found |  |  |

## Phase 0 Comparison

- Phase 0 marked every sample as `needs_review`, so these PoC outputs should be manually reviewed before promoting them into `tests/fixtures/expected_results.csv`.
- Successful selected rows: 2
- Unresolved selected rows: 5

## Recommendation

- Use `zxing-cpp` first for Data Matrix and QR Code because it matched the successful Data Matrix reads and was the fastest successful decoder in this sample run.
- Keep `pylibdmtx` as an optional Data Matrix fallback only; it matched the successful Data Matrix reads but was much slower on this sample run.
- Keep `pyzbar` out of the first implementation path for now; it imported successfully but produced no QR reads on the current sample set.
- Carry the five unresolved sample images into Phase 2 preprocessing work: grayscale, threshold, scaling, rotation, and candidate crop retries.
