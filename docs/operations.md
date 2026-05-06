# Operations

## Storage Layout

Each job lives under `BARCODE_READER_STORAGE_DIR`:

```text
{storage_root}/{jobId}/
  metadata.json
  events.jsonl
  results.csv
  uploads/
    image_001.png
```

`metadata.json` is the API status source, `events.jsonl` is the per-job
processing log, `results.csv` is the downloadable artifact, and `uploads/`
contains original image payloads under internal image IDs.

## Health Check

`GET /healthz` returns:

```json
{
  "status": "ok",
  "storageRoot": "D:\\project\\read_datamatrix\\storage\\jobs",
  "storageWritable": true,
  "errorMessage": ""
}
```

The endpoint writes and removes a tiny probe file in the storage root. It
returns `503` with `status: "degraded"` if storage cannot be created or written.

## Retention Policy

Default policy:

- Retain job directories for 7 days after `completed_at`.
- Delete only terminal jobs: `completed`, `partial_failed`, or `failed`.
- Never delete `queued` or `processing` jobs.
- Missing or unreadable metadata is skipped for manual review.

Preview cleanup:

```powershell
python scripts/cleanup_uploads.py --retention-days 7
```

Execute cleanup:

```powershell
python scripts/cleanup_uploads.py --retention-days 7 --execute
```

Machine-readable output:

```powershell
python scripts/cleanup_uploads.py --json
```

Schedule the cleanup script with your platform scheduler after confirming the
dry-run output. The API does not delete files automatically.

## Logs

Application logs go through Python logging and uvicorn. Per-job events are also
written to `events.jsonl` with these fields:

- `timestamp`
- `event`
- `job_id`
- `source_filename`
- `status`
- `error_message`
- `elapsed_ms`

Useful events:

- `job_created`
- `job_started`
- `reader_retry`
- `image_processed`
- `job_completed`
- `job_failed`

For an incident, start with the API `jobId`, open `{storage_root}/{jobId}/`, and
compare `metadata.json`, `events.jsonl`, and `results.csv`.

## Operational Gates

Before deployment:

```powershell
python -m unittest discover -s tests -p "test_*.py"
python -m compileall src tests
```

After deployment:

```powershell
python scripts/smoke_test.py --base-url http://127.0.0.1:8000 --image sample_images/image_01.jfif
```

For cleanup verification, create or keep a non-production storage directory and
run:

```powershell
python scripts/cleanup_uploads.py --storage-root .\storage\jobs --retention-days 7
```

Confirm the candidate list before adding `--execute`.

## Failure Triage

- Upload rejected: inspect HTTP `400` detail errors; no job directory should be
  created.
- Job `failed` with CSV ready: inspect CSV `status` and `error_message`, then
  read matching `events.jsonl` entries.
- Health check degraded: verify storage permissions, disk availability, and the
  configured `BARCODE_READER_STORAGE_DIR`.
- Smoke upload failed before job creation: check API logs and native decoder
  installation.
- Smoke job failed: run `python -m unittest discover -s tests -p "test_*.py"`
  on the host and verify `zxing-cpp`/OpenCV runtime availability.

## Backups And Privacy

Uploaded images and decoded CSV output may contain production data. Treat
`BARCODE_READER_STORAGE_DIR` as sensitive application data, limit OS-level
permissions, and align `BARCODE_READER_RETENTION_DAYS` with your privacy and
support requirements.
