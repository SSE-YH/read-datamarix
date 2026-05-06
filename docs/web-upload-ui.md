# Web Upload UI

Phase 5 adds a static browser client served by the existing FastAPI process.
It is available at `/` and `/upload`, with assets under `/static`.

## Running Locally

```powershell
python -m uvicorn barcode_reader.api:app --app-dir src --reload
```

Open `http://127.0.0.1:8000/`.

## User Flow

1. Select images with the file picker or drag files onto the upload target.
2. Review client-side validation for extension, empty files, per-file size,
   file count, and total upload size.
3. Submit the files with multipart field name `images`.
4. Follow upload progress and job status polling through the Phase 4 endpoints.
5. Download the CSV when the API reports `csvReady: true`.

## API Contracts Used

- `POST /api/uploads`
- `GET /api/jobs/{jobId}`
- `GET /api/jobs/{jobId}/csv`

The UI reads `links.status` and `links.csv` from API responses so future queue
or routing changes can keep the same client behavior.

## Validation Limits

The client mirrors Phase 4 validation for fast feedback:

- extensions: `.jpg`, `.jpeg`, `.jfif`, `.png`, `.bmp`, `.tif`, `.tiff`
- max files: 100
- max file size: 20 MiB
- max total request size: 250 MiB

Server validation remains authoritative. API validation responses are displayed
as per-file user-facing messages.
