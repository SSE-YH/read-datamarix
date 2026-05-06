from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Callable, Sequence

from PIL import Image

from .core import read_barcodes
from .csv_export import ImageBarcodeResults, write_results_csv
from .models import BarcodeResult, STATUS_ERROR, STATUS_SUCCESS
from .models import STATUS_NOT_FOUND


LOGGER = logging.getLogger(__name__)


JOB_STATUS_QUEUED = "queued"
JOB_STATUS_PROCESSING = "processing"
JOB_STATUS_COMPLETED = "completed"
JOB_STATUS_PARTIAL_FAILED = "partial_failed"
JOB_STATUS_FAILED = "failed"

JOB_STATUSES = {
    JOB_STATUS_QUEUED,
    JOB_STATUS_PROCESSING,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_PARTIAL_FAILED,
    JOB_STATUS_FAILED,
}

SUPPORTED_UPLOAD_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".jfif",
    ".png",
    ".bmp",
    ".tif",
    ".tiff",
}
SUPPORTED_UPLOAD_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/bmp",
    "image/tiff",
}

MIB = 1024 * 1024
MIN_UPLOAD_BYTES = 1
MAX_UPLOAD_BYTES = 20 * MIB
MAX_UPLOAD_IMAGES = 100
MAX_UPLOAD_TOTAL_BYTES = 250 * MIB
MAX_IMAGE_EDGE_PIXELS = 10_000
MAX_IMAGE_PIXELS = 75_000_000

STORAGE_ROOT_ENV_VAR = "BARCODE_READER_STORAGE_DIR"
DEFAULT_STORAGE_ROOT = Path("storage") / "jobs"
JOB_LOG_FILENAME = "events.jsonl"

Reader = Callable[..., list[BarcodeResult]]


@dataclass(frozen=True)
class UploadFileInput:
    filename: str
    content_type: str | None
    data: bytes


@dataclass(frozen=True)
class UploadValidationIssue:
    filename: str | None
    image_index: int | None
    code: str
    message: str

    def to_dict(self) -> dict[str, object]:
        return {
            "filename": self.filename,
            "imageIndex": self.image_index,
            "code": self.code,
            "message": self.message,
        }


class UploadValidationError(ValueError):
    def __init__(self, issues: Sequence[UploadValidationIssue]):
        super().__init__("upload validation failed")
        self.issues = list(issues)


@dataclass
class UploadedImage:
    image_id: str
    image_index: int
    source_filename: str
    stored_path: str
    content_type: str
    size_bytes: int
    status: str = ""
    result_count: int = 0
    error_message: str = ""
    processing_ms: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "image_id": self.image_id,
            "image_index": self.image_index,
            "source_filename": self.source_filename,
            "stored_path": self.stored_path,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "status": self.status,
            "result_count": self.result_count,
            "error_message": self.error_message,
            "processing_ms": self.processing_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "UploadedImage":
        processing_ms = data.get("processing_ms")
        return cls(
            image_id=str(data["image_id"]),
            image_index=int(data["image_index"]),
            source_filename=str(data["source_filename"]),
            stored_path=str(data["stored_path"]),
            content_type=str(data.get("content_type") or ""),
            size_bytes=int(data["size_bytes"]),
            status=str(data.get("status") or ""),
            result_count=int(data.get("result_count") or 0),
            error_message=str(data.get("error_message") or ""),
            processing_ms=int(processing_ms) if processing_ms is not None else None,
        )


@dataclass
class JobRecord:
    job_id: str
    status: str
    total_images: int
    processed_images: int
    success_count: int
    failure_count: int
    result_count: int
    created_at: str
    started_at: str | None
    completed_at: str | None
    csv_path: str | None
    error_message: str
    images: list[UploadedImage]

    def to_dict(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "total_images": self.total_images,
            "processed_images": self.processed_images,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "result_count": self.result_count,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "csv_path": self.csv_path,
            "error_message": self.error_message,
            "images": [image.to_dict() for image in self.images],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "JobRecord":
        return cls(
            job_id=str(data["job_id"]),
            status=str(data["status"]),
            total_images=int(data["total_images"]),
            processed_images=int(data.get("processed_images") or 0),
            success_count=int(data.get("success_count") or 0),
            failure_count=int(data.get("failure_count") or 0),
            result_count=int(data.get("result_count") or 0),
            created_at=str(data["created_at"]),
            started_at=data.get("started_at") if data.get("started_at") else None,
            completed_at=data.get("completed_at") if data.get("completed_at") else None,
            csv_path=data.get("csv_path") if data.get("csv_path") else None,
            error_message=str(data.get("error_message") or ""),
            images=[
                UploadedImage.from_dict(image)
                for image in data.get("images", [])
                if isinstance(image, dict)
            ],
        )


class JobStorage:
    def __init__(self, root: str | Path | None = None) -> None:
        configured_root = root or os.environ.get(STORAGE_ROOT_ENV_VAR) or DEFAULT_STORAGE_ROOT
        self.root = Path(configured_root).resolve()

    def create_job(self, uploads: Sequence[UploadFileInput]) -> JobRecord:
        validate_uploads(uploads)
        job_id = _new_job_id()
        job_dir = self.job_dir(job_id)
        while job_dir.exists():
            job_id = _new_job_id()
            job_dir = self.job_dir(job_id)

        uploads_dir = job_dir / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=False)

        images: list[UploadedImage] = []
        for image_index, upload in enumerate(uploads, start=1):
            source_filename = normalize_source_filename(upload.filename)
            suffix = Path(source_filename).suffix.lower()
            image_id = f"image_{image_index:03d}"
            relative_path = f"uploads/{image_id}{suffix}"
            (job_dir / relative_path).write_bytes(upload.data)
            images.append(
                UploadedImage(
                    image_id=image_id,
                    image_index=image_index,
                    source_filename=source_filename,
                    stored_path=relative_path,
                    content_type=normalize_content_type(upload.content_type),
                    size_bytes=len(upload.data),
                )
            )

        record = JobRecord(
            job_id=job_id,
            status=JOB_STATUS_QUEUED,
            total_images=len(images),
            processed_images=0,
            success_count=0,
            failure_count=0,
            result_count=0,
            created_at=utc_now_iso(),
            started_at=None,
            completed_at=None,
            csv_path=None,
            error_message="",
            images=images,
        )
        self.save_job(record)
        return record

    def load_job(self, job_id: str) -> JobRecord | None:
        metadata_path = self.metadata_path(job_id)
        if not metadata_path.exists():
            return None
        with metadata_path.open("r", encoding="utf-8") as metadata_file:
            data = json.load(metadata_file)
        if not isinstance(data, dict):
            return None
        return JobRecord.from_dict(data)

    def save_job(self, record: JobRecord) -> None:
        job_dir = self.job_dir(record.job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = self.metadata_path(record.job_id)
        temp_path = metadata_path.with_suffix(".json.tmp")
        temp_path.write_text(
            json.dumps(record.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(metadata_path)

    def job_dir(self, job_id: str) -> Path:
        return self.root / job_id

    def metadata_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / "metadata.json"

    def image_path(self, record: JobRecord, image: UploadedImage) -> Path:
        return self.job_dir(record.job_id) / image.stored_path

    def csv_file_path(self, record: JobRecord) -> Path:
        if record.csv_path:
            return self.job_dir(record.job_id) / record.csv_path
        return self.job_dir(record.job_id) / "results.csv"

    def log_path(self, job_id: str) -> Path:
        return self.job_dir(job_id) / JOB_LOG_FILENAME

    def append_log_event(self, job_id: str, event: str, **fields: object) -> None:
        payload = {
            "timestamp": utc_now_iso(),
            "event": event,
            "job_id": job_id,
            "source_filename": fields.pop("source_filename", ""),
            "status": fields.pop("status", ""),
            "error_message": fields.pop("error_message", ""),
            "elapsed_ms": fields.pop("elapsed_ms", 0),
        }
        payload.update(fields)

        log_path = self.log_path(job_id)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

        LOGGER.info(
            "%s job_id=%s source_filename=%s status=%s elapsed_ms=%s",
            event,
            payload["job_id"],
            payload["source_filename"],
            payload["status"],
            payload["elapsed_ms"],
        )


class JobService:
    def __init__(
        self,
        storage_root: str | Path | None = None,
        *,
        storage: JobStorage | None = None,
        reader: Reader = read_barcodes,
        include_bom: bool = False,
        reader_max_attempts: int = 1,
    ) -> None:
        self.storage = storage or JobStorage(storage_root)
        self._reader = reader
        self._include_bom = include_bom
        self._reader_max_attempts = max(1, reader_max_attempts)

    def create_and_process_job(self, uploads: Sequence[UploadFileInput]) -> JobRecord:
        record = self.storage.create_job(uploads)
        self.storage.append_log_event(
            record.job_id,
            "job_created",
            status=record.status,
            total_images=record.total_images,
        )
        return self.process_job(record.job_id)

    def process_job(self, job_id: str) -> JobRecord:
        job_started = time.perf_counter()
        record = self.storage.load_job(job_id)
        if record is None:
            raise KeyError(job_id)

        record.status = JOB_STATUS_PROCESSING
        record.started_at = record.started_at or utc_now_iso()
        record.completed_at = None
        record.error_message = ""
        record.processed_images = 0
        record.success_count = 0
        record.failure_count = 0
        record.result_count = 0
        self.storage.save_job(record)
        self.storage.append_log_event(
            record.job_id,
            "job_started",
            status=record.status,
            total_images=record.total_images,
        )

        image_results: list[ImageBarcodeResults] = []
        try:
            for image in record.images:
                image_started = time.perf_counter()
                results, attempts = self._read_image(record, image)
                image.status = image_status(results)
                image.error_message = image_error_message(results)
                image.result_count = len(results)
                image.processing_ms = elapsed_ms(image_started)
                record.processed_images += 1
                record.result_count += len(results)
                image_results.append(
                    ImageBarcodeResults(
                        source_filename=image.source_filename,
                        image_index=image.image_index,
                        results=results,
                    )
                )
                self.storage.save_job(record)
                self.storage.append_log_event(
                    record.job_id,
                    "image_processed",
                    source_filename=image.source_filename,
                    status=image.status,
                    error_message=image.error_message,
                    elapsed_ms=image.processing_ms,
                    image_index=image.image_index,
                    result_count=image.result_count,
                    attempts=attempts,
                )

            record.success_count = sum(1 for image in record.images if image.status == STATUS_SUCCESS)
            record.failure_count = record.total_images - record.success_count
            record.status = final_job_status(record.success_count, record.failure_count)
            record.csv_path = "results.csv"
            write_results_csv(
                self.storage.csv_file_path(record),
                record.job_id,
                image_results,
                include_bom=self._include_bom,
            )
            self.storage.append_log_event(
                record.job_id,
                "job_completed",
                status=record.status,
                elapsed_ms=elapsed_ms(job_started),
                success_count=record.success_count,
                failure_count=record.failure_count,
                result_count=record.result_count,
                csv_path=record.csv_path,
            )
        except Exception as exc:
            record.status = JOB_STATUS_FAILED
            record.error_message = f"job processing failed: {type(exc).__name__}: {exc}"
            self.storage.append_log_event(
                record.job_id,
                "job_failed",
                status=record.status,
                error_message=record.error_message,
                elapsed_ms=elapsed_ms(job_started),
            )
        finally:
            record.completed_at = utc_now_iso()
            self.storage.save_job(record)

        return record

    def get_job(self, job_id: str) -> JobRecord | None:
        return self.storage.load_job(job_id)

    def csv_path_for_job(self, record: JobRecord) -> Path | None:
        if not record.csv_path:
            return None
        csv_path = self.storage.csv_file_path(record)
        if not csv_path.exists():
            return None
        return csv_path

    def is_csv_ready(self, record: JobRecord) -> bool:
        return self.csv_path_for_job(record) is not None

    def _read_image(self, record: JobRecord, image: UploadedImage) -> tuple[list[BarcodeResult], int]:
        for attempt in range(1, self._reader_max_attempts + 1):
            try:
                return (
                    self._reader(
                        self.storage.image_path(record, image),
                        source_filename=image.source_filename,
                    ),
                    attempt,
                )
            except Exception as exc:
                error_message = f"processing failed: {type(exc).__name__}: {exc}"
                if attempt < self._reader_max_attempts:
                    self.storage.append_log_event(
                        record.job_id,
                        "reader_retry",
                        source_filename=image.source_filename,
                        status=STATUS_ERROR,
                        error_message=error_message,
                        attempt=attempt,
                        next_attempt=attempt + 1,
                    )
                    continue
                return (
                    [
                        BarcodeResult(
                            source_filename=image.source_filename,
                            status=STATUS_ERROR,
                            error_message=error_message,
                        )
                    ],
                    attempt,
                )

        raise AssertionError("reader retry loop exited unexpectedly")


def validate_uploads(uploads: Sequence[UploadFileInput]) -> None:
    issues: list[UploadValidationIssue] = []
    if not uploads:
        raise UploadValidationError(
            [
                UploadValidationIssue(
                    filename=None,
                    image_index=None,
                    code="no_files",
                    message="Upload at least one image.",
                )
            ]
        )

    if len(uploads) > MAX_UPLOAD_IMAGES:
        issues.append(
            UploadValidationIssue(
                filename=None,
                image_index=None,
                code="too_many_files",
                message=f"Upload no more than {MAX_UPLOAD_IMAGES} images at once.",
            )
        )

    total_size = sum(len(upload.data) for upload in uploads)
    if total_size > MAX_UPLOAD_TOTAL_BYTES:
        issues.append(
            UploadValidationIssue(
                filename=None,
                image_index=None,
                code="total_size_exceeded",
                message=f"Total upload size must be {MAX_UPLOAD_TOTAL_BYTES} bytes or less.",
            )
        )

    for image_index, upload in enumerate(uploads, start=1):
        issues.extend(validate_upload(upload, image_index))

    if issues:
        raise UploadValidationError(issues)


def validate_upload(upload: UploadFileInput, image_index: int) -> list[UploadValidationIssue]:
    filename = normalize_source_filename(upload.filename)
    content_type = normalize_content_type(upload.content_type)
    size_bytes = len(upload.data)
    suffix = Path(filename).suffix.lower()
    issues: list[UploadValidationIssue] = []

    if suffix not in SUPPORTED_UPLOAD_EXTENSIONS:
        issues.append(
            UploadValidationIssue(
                filename=filename,
                image_index=image_index,
                code="unsupported_extension",
                message=f"Unsupported file extension: {suffix or '(none)'}.",
            )
        )

    if content_type and content_type not in SUPPORTED_UPLOAD_MIME_TYPES:
        issues.append(
            UploadValidationIssue(
                filename=filename,
                image_index=image_index,
                code="unsupported_mime_type",
                message=f"Unsupported MIME type: {content_type}.",
            )
        )

    if size_bytes < MIN_UPLOAD_BYTES:
        issues.append(
            UploadValidationIssue(
                filename=filename,
                image_index=image_index,
                code="empty_file",
                message="Uploaded image is empty.",
            )
        )
    elif size_bytes > MAX_UPLOAD_BYTES:
        issues.append(
            UploadValidationIssue(
                filename=filename,
                image_index=image_index,
                code="file_too_large",
                message=f"Uploaded image must be {MAX_UPLOAD_BYTES} bytes or less.",
            )
        )

    if not issues:
        issues.extend(validate_image_payload(filename, image_index, upload.data))

    return issues


def validate_image_payload(
    filename: str,
    image_index: int,
    data: bytes,
) -> list[UploadValidationIssue]:
    try:
        with Image.open(BytesIO(data)) as image:
            width, height = image.size
            image.verify()
    except Exception as exc:
        return [
            UploadValidationIssue(
                filename=filename,
                image_index=image_index,
                code="invalid_image",
                message=f"File could not be opened as an image: {type(exc).__name__}.",
            )
        ]

    if max(width, height) > MAX_IMAGE_EDGE_PIXELS:
        return [
            UploadValidationIssue(
                filename=filename,
                image_index=image_index,
                code="image_dimensions_exceeded",
                message=f"Image width and height must be {MAX_IMAGE_EDGE_PIXELS} pixels or less.",
            )
        ]

    if width * height > MAX_IMAGE_PIXELS:
        return [
            UploadValidationIssue(
                filename=filename,
                image_index=image_index,
                code="image_pixels_exceeded",
                message=f"Image pixel count must be {MAX_IMAGE_PIXELS} pixels or less.",
            )
        ]

    return []


def image_status(results: Sequence[BarcodeResult]) -> str:
    if any(result.status == STATUS_SUCCESS for result in results):
        return STATUS_SUCCESS
    if results:
        return results[0].status
    return STATUS_NOT_FOUND


def image_error_message(results: Sequence[BarcodeResult]) -> str:
    for result in results:
        if result.status != STATUS_SUCCESS and result.error_message:
            return result.error_message
    if not results:
        return "barcode not found"
    return ""


def final_job_status(success_count: int, failure_count: int) -> str:
    if failure_count == 0:
        return JOB_STATUS_COMPLETED
    if success_count > 0:
        return JOB_STATUS_PARTIAL_FAILED
    return JOB_STATUS_FAILED


def normalize_source_filename(filename: str | None) -> str:
    if not filename:
        return "upload"
    normalized = filename.replace("\\", "/").split("/")[-1].strip().replace("\x00", "")
    return normalized or "upload"


def normalize_content_type(content_type: str | None) -> str:
    return (content_type or "").split(";", 1)[0].strip().lower()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def elapsed_ms(started_at: float) -> int:
    return max(0, int(round((time.perf_counter() - started_at) * 1000)))


def _new_job_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    return f"job_{timestamp}_{uuid.uuid4().hex[:8]}"
