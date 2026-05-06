from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IMAGE = ROOT / "sample_images" / "image_01.jfif"
TERMINAL_STATUSES = {"completed", "partial_failed", "failed"}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run an HTTP smoke test against a deployed barcode-reader service.",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Service base URL. Default: http://127.0.0.1:8000.",
    )
    parser.add_argument(
        "--image",
        action="append",
        type=Path,
        default=None,
        help=f"Image to upload. Can be passed more than once. Default: {DEFAULT_IMAGE}.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=30.0,
        help="Overall wait timeout for job completion. Default: 30.",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=1.0,
        help="Polling interval while the job is queued or processing. Default: 1.",
    )
    parser.add_argument(
        "--allow-failed-job",
        action="store_true",
        help="Treat a terminal failed job as acceptable if CSV download still works.",
    )
    parser.add_argument(
        "--skip-health",
        action="store_true",
        help="Skip GET /healthz before uploading.",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    images = args.image or [DEFAULT_IMAGE]

    try:
        for image in images:
            if not image.exists():
                raise SmokeTestError(f"image does not exist: {image}")

        if not args.skip_health:
            health = get_json(absolute_url(base_url, "/healthz"), timeout=10)
            if health.get("status") != "ok":
                raise SmokeTestError(f"health check is not ok: {health}")

        upload = post_images(
            absolute_url(base_url, "/api/uploads"),
            images,
            timeout=max(10, int(args.timeout_seconds)),
        )
        job = wait_for_terminal_job(
            base_url,
            upload,
            timeout_seconds=args.timeout_seconds,
            poll_interval_seconds=args.poll_interval_seconds,
        )

        status = str(job.get("status") or "")
        if status == "failed" and not args.allow_failed_job:
            raise SmokeTestError(f"job failed: {json.dumps(job, ensure_ascii=False)}")

        csv_link = extract_link(job, "csv")
        csv_body, csv_content_type = get_bytes(
            absolute_url(base_url, csv_link),
            timeout=10,
        )
        if b"job_id,source_filename,image_index" not in csv_body[:512]:
            raise SmokeTestError("CSV response does not contain the expected header")

        print(
            "smoke ok: "
            f"job_id={job.get('jobId')} "
            f"status={status} "
            f"csv_bytes={len(csv_body)} "
            f"csv_content_type={csv_content_type}"
        )
        return 0
    except Exception as exc:
        print(f"smoke failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


class SmokeTestError(RuntimeError):
    pass


def post_images(url: str, image_paths: list[Path], timeout: int) -> dict[str, object]:
    body, content_type = encode_multipart_images(image_paths)
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": content_type},
        method="POST",
    )
    return fetch_json(request, timeout=timeout)


def wait_for_terminal_job(
    base_url: str,
    initial_job: dict[str, object],
    *,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> dict[str, object]:
    job = initial_job
    deadline = time.monotonic() + timeout_seconds
    while str(job.get("status") or "") not in TERMINAL_STATUSES:
        if time.monotonic() >= deadline:
            raise SmokeTestError(f"job did not finish before timeout: {job}")
        time.sleep(poll_interval_seconds)
        job = get_json(
            absolute_url(base_url, extract_link(job, "status")),
            timeout=max(1, int(poll_interval_seconds + 5)),
        )
    if not job.get("csvReady"):
        raise SmokeTestError(f"terminal job has no CSV ready flag: {job}")
    return job


def encode_multipart_images(image_paths: list[Path]) -> tuple[bytes, str]:
    boundary = f"barcode-reader-{uuid.uuid4().hex}"
    body = bytearray()
    for image_path in image_paths:
        filename = image_path.name.replace('"', "")
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            (
                'Content-Disposition: form-data; name="images"; '
                f'filename="{filename}"\r\n'
            ).encode("utf-8")
        )
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        body.extend(image_path.read_bytes())
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def get_json(url: str, timeout: int) -> dict[str, object]:
    return fetch_json(urllib.request.Request(url, method="GET"), timeout=timeout)


def fetch_json(request: urllib.request.Request, timeout: int) -> dict[str, object]:
    body, _content_type = open_url(request, timeout=timeout)
    try:
        data = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise SmokeTestError(f"response is not JSON: {body[:200]!r}") from exc
    if not isinstance(data, dict):
        raise SmokeTestError(f"JSON response is not an object: {data!r}")
    return data


def get_bytes(url: str, timeout: int) -> tuple[bytes, str]:
    return open_url(urllib.request.Request(url, method="GET"), timeout=timeout)


def open_url(request: urllib.request.Request, timeout: int) -> tuple[bytes, str]:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read(), response.headers.get("content-type", "")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SmokeTestError(f"HTTP {exc.code} from {request.full_url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise SmokeTestError(f"request failed for {request.full_url}: {exc}") from exc


def extract_link(job: dict[str, object], key: str) -> str:
    links = job.get("links")
    if not isinstance(links, dict) or key not in links:
        raise SmokeTestError(f"job response is missing links.{key}: {job}")
    return str(links[key])


def absolute_url(base_url: str, path_or_url: str) -> str:
    return urllib.parse.urljoin(base_url + "/", path_or_url.lstrip("/"))


if __name__ == "__main__":
    raise SystemExit(main())
