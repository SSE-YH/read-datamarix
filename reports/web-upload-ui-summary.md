# Phase 5 Web Upload UI Summary

## Deliverables

- Static upload page: `src/barcode_reader/web/static/index.html`
- Styling: `src/barcode_reader/web/static/styles.css`
- Browser client logic: `src/barcode_reader/web/static/app.js`
- FastAPI web routes: `/`, `/upload`, `/static/*`
- UI smoke tests: `tests/test_web_ui.py`
- Design note: `docs/web-upload-ui.md`

## Behavior

- Multiple image selection through file picker or drag and drop.
- Immediate client validation for extension, empty files, file size, upload
  count, and total upload size.
- Uploads files with the Phase 4 multipart field name `images`.
- Shows upload progress, job status, processed/success/failure counts, per-image
  status, and failure reasons.
- Polls `links.status` until a terminal job state.
- Enables CSV download when `csvReady` is true.

## Handoff to Phase 6

Phase 6 can add browser automation around the static UI and larger reliability
fixtures. The current UI already distinguishes client validation errors, upload
API validation errors, temporary polling failures, terminal failed jobs, and
partial failures.

## Verification

- `python -m unittest discover -s tests -p "test_*.py"`: 26 tests passed.
- `node --check src/barcode_reader/web/static/app.js`: passed.
- Local server smoke test on port 8001:
  - `GET /`: 200 `text/html`
  - `GET /static/app.js`: 200
  - `GET /static/styles.css`: 200
- Sample upload smoke test:
  - `POST /api/uploads` with `sample_images/image_01.jfif` and MIME
    `image/jpeg`: completed, `csvReady: true`
  - `GET /api/jobs/{jobId}/csv`: returned CSV with one successful Data Matrix row
