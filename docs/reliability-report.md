# Quality and Reliability

Phase 6 adds repeatable reliability checks around the Phase 5 upload workflow
and the Phase 4 job API without changing the public upload endpoints.

## Test Gate

Run the full local gate with:

```powershell
python -m unittest discover -s tests -p "test_*.py"
python -m compileall src tests
```

The Phase 6 test set covers:

- sample image regression against the Phase 2 baseline
- CSV schema regression for sample output
- corrupted image upload rejection
- no-barcode rows in CSV output
- decode failure versus unexpected processing error
- multiple barcode rows from one image
- max-count upload handling with tiny images
- per-job processing logs
- optional retry for transient reader exceptions

The sample regression test uses `zxing-cpp`; it is skipped automatically when
that decoder is not installed.

## Failure Fixtures

- `tests/fixtures/corrupt-image.jpg` is a deliberately invalid image payload.
- Blank and multi-result images are generated inside tests to avoid storing
  large binary fixtures.
- Reader behavior is injected in API tests so failure categories stay stable
  even if decoder libraries change.

## Job Logs

Each job directory now includes `events.jsonl` beside `metadata.json`,
`results.csv`, and `uploads/`.

Every event includes:

- `timestamp`
- `event`
- `job_id`
- `source_filename`
- `status`
- `error_message`
- `elapsed_ms`

Important events are:

- `job_created`
- `job_started`
- `reader_retry`
- `image_processed`
- `job_completed`
- `job_failed`

`image_processed` also records `image_index`, `result_count`, and `attempts`.
Image metadata and API image responses include `processingMs`.

## Retry Policy

`JobService` supports `reader_max_attempts`. The default is `1`, preserving the
Phase 4 synchronous behavior. Set it to `2` or more to retry unexpected reader
exceptions.

Retries are intentionally narrow:

- `not_found` and `decode_failed` are normal reader results and are not retried.
- Upload validation failures are rejected before a job is created.
- Unexpected reader exceptions can be retried and are logged as `reader_retry`.
- If all attempts fail, the image receives an `error` result row in CSV.

## Worker Queue Note

The current implementation still processes uploads synchronously in the API
request. Phase 6 verifies the max-count path with a fast injected reader and
keeps the UI/API contract queue-ready through `queued` and `processing` states.
For real long-running decoder workloads, Phase 7 should move `process_job()` to
a background worker or external queue while preserving the same status and CSV
contracts.
