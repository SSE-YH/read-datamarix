from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from barcode_reader.jobs import JobService

from .serializers import job_to_response


def build_jobs_router(service: JobService) -> APIRouter:
    router = APIRouter()

    @router.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, object]:
        job = service.get_job(job_id)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"message": "Job not found."},
            )
        return job_to_response(job, csv_ready=service.is_csv_ready(job))

    @router.get("/api/jobs/{job_id}/csv")
    def download_job_csv(job_id: str) -> FileResponse:
        job = service.get_job(job_id)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"message": "Job not found."},
            )

        csv_path = service.csv_path_for_job(job)
        if csv_path is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"message": "CSV is not ready for this job."},
            )

        return FileResponse(
            csv_path,
            media_type="text/csv; charset=utf-8",
            filename=f"{job.job_id}.csv",
        )

    return router
