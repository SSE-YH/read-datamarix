from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from barcode_reader.jobs import JobService, UploadFileInput, UploadValidationError

from .serializers import job_to_response


def build_uploads_router(service: JobService) -> APIRouter:
    router = APIRouter()

    @router.post("/api/uploads", status_code=status.HTTP_202_ACCEPTED)
    async def upload_images(
        images: list[UploadFile] | None = File(default=None),
    ) -> JSONResponse:
        payloads: list[UploadFileInput] = []
        for upload in images or []:
            try:
                payloads.append(
                    UploadFileInput(
                        filename=upload.filename or "",
                        content_type=upload.content_type,
                        data=await upload.read(),
                    )
                )
            finally:
                await upload.close()

        try:
            job = service.create_and_process_job(payloads)
        except UploadValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Upload validation failed.",
                    "errors": [issue.to_dict() for issue in exc.issues],
                },
            ) from exc

        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=job_to_response(job, csv_ready=service.is_csv_ready(job)),
        )

    return router
