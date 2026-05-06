# Phase 7 Deploy and Operations Summary

## Deliverables

- Deployment guide: `docs/deployment.md`
- Operations guide: `docs/operations.md`
- Environment example: `.env.example`
- HTTP smoke test: `scripts/smoke_test.py`
- Retention cleanup script: `scripts/cleanup_uploads.py`
- Storage cleanup helpers: `src/barcode_reader/operations.py`
- API health check: `GET /healthz`
- Phase 7 tests: `tests/test_phase7_operations.py`

## Operational Policy

- Store jobs under `BARCODE_READER_STORAGE_DIR`.
- Retain terminal job directories for `BARCODE_READER_RETENTION_DAYS` days.
- Cleanup is dry-run by default and deletes only `completed`, `partial_failed`,
  or `failed` jobs after `--execute`.
- `queued` and `processing` jobs are never removed by cleanup.
- Per-job troubleshooting uses `metadata.json`, `events.jsonl`, and
  `results.csv`.

## Verification

Run before deployment:

```powershell
python -m unittest discover -s tests -p "test_*.py"
python -m compileall src tests
```

Run after deployment:

```powershell
python scripts/smoke_test.py --base-url http://127.0.0.1:8000 --image sample_images/image_01.jfif
```

Run cleanup preview:

```powershell
python scripts/cleanup_uploads.py --retention-days 7
```

## Known Operations Note

Uploads are still processed synchronously in the API request. The Phase 7
deployment guide documents the worker scale-out path: keep the API/CSV contract
and move `JobService.process_job(job_id)` into a background worker when decoder
latency or request volume requires it.
