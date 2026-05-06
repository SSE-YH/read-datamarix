# Phase 4 Backend API and Job Processing Summary

## Deliverables

- Backend API: `src/barcode_reader/api/`
- Job service and storage model: `src/barcode_reader/jobs.py`
- API tests: `tests/test_api_uploads.py`, `tests/test_api_jobs.py`
- Design note: `docs/backend-api.md`

## API

```text
POST /api/uploads
GET  /api/jobs/{jobId}
GET  /api/jobs/{jobId}/csv
```

Upload requests use multipart field name `images`. The current implementation
processes synchronously, so the upload response usually returns a final status
with `csvReady: true`.

## Job Storage

Jobs are stored below `storage/jobs` by default. Set
`BARCODE_READER_STORAGE_DIR` to override that path. Each job has an isolated
directory with `metadata.json`, uploaded images, and `results.csv`.

## Handoff to Phase 5

The web UI can use the response `links.status` and `links.csv` fields directly.
Display job-level `status`, `processedImages`, `totalImages`, `successCount`,
`failureCount`, and per-image `errorMessage` for partial or failed jobs.
