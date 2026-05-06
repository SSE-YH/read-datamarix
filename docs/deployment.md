# Deployment

This service is a FastAPI application that serves both the upload API and the
static upload UI.

## Runtime

- Python 3.10 or newer
- A writable job storage directory
- Native image and barcode runtime libraries required by the installed decoder
  packages

Install Python dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Linux shells use the same `pip` commands after activating the virtual
environment.

## Native Dependencies

The Python packages in `requirements.txt` cover the application code, but some
decoder packages rely on native libraries or platform wheels:

| Component | Purpose | Deployment note |
| --- | --- | --- |
| `zxing-cpp` | Primary Data Matrix and QR decoder | Prefer the published wheel for the target Python/platform. |
| OpenCV runtime | QR fallback and preprocessing | `opencv-python` includes common wheels; slim Linux images may also need `libgl1` and `libglib2.0-0`. |
| `libdmtx` | Data Matrix fallback through `pylibdmtx` | Install the OS package when enabling slow fallback decoding. |
| `zbar` | Barcode runtime for `pyzbar` | Keep documented for future decoder expansion; install only if a pyzbar adapter is enabled. |

After installing dependencies, run the local test gate:

```powershell
python -m unittest discover -s tests -p "test_*.py"
python -m compileall src tests
```

## Environment

Copy `.env.example` into your deployment environment and set values there.
Do not store secrets in this repository.

| Variable | Default | Used by | Description |
| --- | --- | --- | --- |
| `BARCODE_READER_STORAGE_DIR` | `storage/jobs` | API, cleanup script | Root directory for job metadata, uploaded images, logs, and CSV files. |
| `BARCODE_READER_RETENTION_DAYS` | `7` | cleanup script | Terminal jobs older than this many days are eligible for deletion. |
| `BARCODE_READER_HOST` | `0.0.0.0` | example process command | Host value for process-manager scripts. |
| `BARCODE_READER_PORT` | `8000` | example process command | Port value for process-manager scripts. |

## Run

Local or single-process deployment:

```powershell
$env:BARCODE_READER_STORAGE_DIR = "D:\barcode-reader\jobs"
python -m uvicorn barcode_reader.api:app --app-dir src --host 0.0.0.0 --port 8000
```

Linux/systemd-style command:

```bash
BARCODE_READER_STORAGE_DIR=/var/lib/barcode-reader/jobs \
python -m uvicorn barcode_reader.api:app --app-dir src --host 0.0.0.0 --port 8000
```

The upload UI is served at `/` and `/upload`. Health checks are available at
`/healthz`; the endpoint verifies that job storage is writable.

## Smoke Test

Run this against the deployed URL after starting the service:

```powershell
python scripts/smoke_test.py --base-url http://127.0.0.1:8000 --image sample_images/image_01.jfif
```

The smoke test checks:

- `GET /healthz`
- `POST /api/uploads`
- `GET /api/jobs/{jobId}`
- `GET /api/jobs/{jobId}/csv`
- CSV header presence

By default a terminal `failed` job fails the smoke test because it usually
means a decoder/runtime dependency is missing. Use `--allow-failed-job` only
when you are testing API plumbing in an intentionally limited environment.

## Worker Scale-Out Path

The current API processes jobs synchronously during `POST /api/uploads`.
The job model is queue-ready: keep the same storage layout, API response fields,
and CSV contract when moving `JobService.process_job(job_id)` behind a worker.

For scale-out:

- API process creates the job and returns `queued`.
- Worker process reads the same `BARCODE_READER_STORAGE_DIR`.
- Worker calls `JobService.process_job(job_id)`.
- UI continues polling `links.status` and downloading `links.csv`.
