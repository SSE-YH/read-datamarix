# Backend API

Phase 4 exposes upload, job status, and CSV download endpoints over FastAPI.
The first implementation processes jobs synchronously inside the upload request,
but the job model preserves `queued` and `processing` states so a worker queue
can be introduced later without changing response fields.

## Running Locally

```powershell
python -m uvicorn barcode_reader.api:app --app-dir src --reload
```

Set `BARCODE_READER_STORAGE_DIR` to override the default job storage directory
(`storage/jobs`).

## Upload

`POST /api/uploads`

- Content type: `multipart/form-data`
- File field name: `images`
- Response code: `202 Accepted`

The server validates the Phase 0 upload policy before creating a job:

- extensions: `.jpg`, `.jpeg`, `.jfif`, `.png`, `.bmp`, `.tif`, `.tiff`
- MIME types: `image/jpeg`, `image/png`, `image/bmp`, `image/tiff`
- max files per request: 100
- max file size: 20 MiB
- max request size: 250 MiB
- max image edge: 10000 px
- max image pixels: 75 MP

Validation failures return `400 Bad Request`:

```json
{
  "detail": {
    "message": "Upload validation failed.",
    "errors": [
      {
        "filename": "notes.txt",
        "imageIndex": 1,
        "code": "unsupported_extension",
        "message": "Unsupported file extension: .txt."
      }
    ]
  }
}
```

Successful uploads return a job summary:

```json
{
  "jobId": "job_20260506_120000_000000_ab12cd34",
  "status": "completed",
  "totalImages": 2,
  "processedImages": 2,
  "successCount": 2,
  "failureCount": 0,
  "resultCount": 2,
  "csvReady": true,
  "links": {
    "status": "/api/jobs/job_20260506_120000_000000_ab12cd34",
    "csv": "/api/jobs/job_20260506_120000_000000_ab12cd34/csv"
  }
}
```

## Job Status

`GET /api/jobs/{jobId}`

Returns the same job summary plus per-image status entries. Job status values are:

- `queued`
- `processing`
- `completed`
- `partial_failed`
- `failed`

Image status values come from the core reader and CSV schema:

- `success`
- `not_found`
- `decode_failed`
- `error`

## CSV Download

`GET /api/jobs/{jobId}/csv`

Returns `text/csv` with a download filename of `{jobId}.csv`. Failed jobs can
still have a CSV when every image produced a failure row. If a job exists but
the CSV artifact is not available yet, the endpoint returns `409 Conflict`.

## Storage

Each job is isolated under:

```text
{storage_root}/{jobId}/
  metadata.json
  results.csv
  uploads/
      image_001.png
      image_002.jpg
  events.jsonl
```

Original filenames are kept in metadata and CSV as `source_filename`. Stored
file paths use internal image IDs so user-provided filenames are never used as
filesystem paths.

## Reliability Logs

Phase 6 writes one JSON object per line to `{jobId}/events.jsonl`. Events include
`job_id`, `source_filename`, `status`, `error_message`, and `elapsed_ms` so a
failed image can be traced from API response to CSV row to processing log.

Per-image job status responses also include `processingMs`.

## Health Check

`GET /healthz`

Returns `200 OK` when the configured job storage root can be created and
written. Returns `503 Service Unavailable` with `status: "degraded"` when the
storage probe fails. Deployment smoke tests use this endpoint before exercising
upload, status, and CSV download routes.
