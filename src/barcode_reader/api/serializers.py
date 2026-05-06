from __future__ import annotations

from barcode_reader.jobs import JobRecord, UploadedImage


def job_to_response(job: JobRecord, *, csv_ready: bool) -> dict[str, object]:
    return {
        "jobId": job.job_id,
        "status": job.status,
        "totalImages": job.total_images,
        "processedImages": job.processed_images,
        "successCount": job.success_count,
        "failureCount": job.failure_count,
        "resultCount": job.result_count,
        "createdAt": job.created_at,
        "startedAt": job.started_at,
        "completedAt": job.completed_at,
        "csvReady": csv_ready,
        "errorMessage": job.error_message,
        "images": [image_to_response(image) for image in job.images],
        "links": {
            "status": f"/api/jobs/{job.job_id}",
            "csv": f"/api/jobs/{job.job_id}/csv",
        },
    }


def image_to_response(image: UploadedImage) -> dict[str, object]:
    return {
        "imageId": image.image_id,
        "imageIndex": image.image_index,
        "sourceFilename": image.source_filename,
        "contentType": image.content_type,
        "sizeBytes": image.size_bytes,
        "status": image.status,
        "resultCount": image.result_count,
        "errorMessage": image.error_message,
        "processingMs": image.processing_ms,
    }
