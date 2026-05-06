from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from barcode_reader.jobs import JobService
from barcode_reader.operations import check_storage_writable

from .jobs import build_jobs_router
from .uploads import build_uploads_router

WEB_STATIC_ROOT = Path(__file__).resolve().parents[1] / "web" / "static"


def create_app(
    *,
    storage_root: str | Path | None = None,
    job_service: JobService | None = None,
) -> FastAPI:
    service = job_service or JobService(storage_root=storage_root)
    application = FastAPI(title="Barcode Reader API")
    application.state.job_service = service
    mount_health_check(application, service)
    application.include_router(build_uploads_router(service))
    application.include_router(build_jobs_router(service))
    mount_web_ui(application)
    return application


def mount_health_check(application: FastAPI, service: JobService) -> None:
    @application.get("/healthz", include_in_schema=False)
    def healthz() -> JSONResponse:
        storage_writable, error_message = check_storage_writable(service.storage.root)
        payload = {
            "status": "ok" if storage_writable else "degraded",
            "storageRoot": str(service.storage.root),
            "storageWritable": storage_writable,
            "errorMessage": error_message,
        }
        return JSONResponse(
            status_code=200 if storage_writable else 503,
            content=payload,
        )


def mount_web_ui(application: FastAPI) -> None:
    if not WEB_STATIC_ROOT.exists():
        return

    application.mount(
        "/static",
        StaticFiles(directory=WEB_STATIC_ROOT),
        name="static",
    )

    @application.get("/", include_in_schema=False)
    @application.get("/upload", include_in_schema=False)
    def upload_page() -> FileResponse:
        return FileResponse(WEB_STATIC_ROOT / "index.html")


app = create_app()
