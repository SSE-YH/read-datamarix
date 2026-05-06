# Phase 6 Quality and Reliability Summary

## Deliverables

- Job event log storage: `events.jsonl` per job directory
- Image processing duration exposed as `processingMs`
- Optional transient reader retry via `JobService(reader_max_attempts=...)`
- Failure fixture: `tests/fixtures/corrupt-image.jpg`
- Reliability tests:
  - `tests/test_regression_samples.py`
  - `tests/test_failure_cases.py`
  - `tests/test_large_uploads.py`
- Reliability report: `docs/reliability-report.md`

## Verification

- `python -m unittest discover -s tests -p "test_*.py"`: 33 tests passed.
- `python -m compileall src tests`: passed.

## Handoff to Phase 7

Use the full local test command above as the deploy smoke gate. Before production
use, move synchronous `process_job()` execution behind a background worker or
external queue if real decoder latency makes upload requests too slow.
