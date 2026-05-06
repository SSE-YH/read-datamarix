# Barcode Reader

이미지 파일을 업로드하면 서버에서 Data Matrix / QR Code를 읽고, 결과를 CSV로 내려받을 수 있는 사내 인트라넷용 웹 애플리케이션입니다.

## 주요 기능

- 여러 이미지 동시 업로드
- Data Matrix / QR Code 인식
- 이미지별 성공/실패 상태 표시
- 실패 이미지도 CSV row로 포함
- CSV 다운로드
- Job 단위 처리 로그 저장
- 운영용 health check
- 보존 기간 기반 job cleanup 스크립트

## 기술 스택

### Backend

- Python
- FastAPI
- Uvicorn
- python-multipart

### Barcode / Image Processing

- zxing-cpp: Data Matrix / QR Code 기본 디코더
- OpenCV: QR fallback 및 이미지 전처리
- Pillow: 이미지 로딩, EXIF orientation 보정, 전처리
- NumPy: OpenCV 연동용 이미지 배열 처리
- pylibdmtx / libdmtx: Data Matrix slow fallback 후보
- pyzbar / zbar: 향후 barcode decoder 확장 후보

### Frontend

- Static HTML
- CSS
- Vanilla JavaScript

프론트엔드는 별도 Node/Vite/React 빌드 없이 FastAPI에서 정적 파일로 제공합니다.

### Storage / Operations

- 로컬 파일 시스템 기반 job storage
- JSON metadata
- JSONL event log
- CSV result file
- unittest 기반 자동 테스트

## 데이터 흐름

```text
브라우저
  -> POST /api/uploads
  -> 서버 storage/jobs/{jobId}/uploads 에 원본 이미지 저장
  -> 서버 내부 로컬 decoder로 분석
  -> metadata.json / events.jsonl / results.csv 생성
  -> 브라우저에서 CSV 다운로드
```

외부 클라우드나 제3자 API로 이미지를 보내지 않습니다. 단, 서버를 어떤 네트워크에 노출하느냐에 따라 접근 범위가 달라집니다.

## 설치

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 실행

프로젝트 루트에서 실행합니다.

```powershell
python -m uvicorn barcode_reader.api:app --app-dir src --host 127.0.0.1 --port 8000
```

브라우저에서 접속합니다.

```text
http://127.0.0.1:8000/
```

8000 포트가 사용 중이면 다른 포트를 쓰면 됩니다.

```powershell
python -m uvicorn barcode_reader.api:app --app-dir src --host 127.0.0.1 --port 8001
```

## 사내망에서 접속 허용

서버 PC 외부의 사내망 사용자도 접속해야 한다면 `0.0.0.0`으로 바인딩합니다.

```powershell
python -m uvicorn barcode_reader.api:app --app-dir src --host 0.0.0.0 --port 8000
```

이 경우 방화벽, VPN, reverse proxy, 사내 인증 등으로 접근 범위를 제한하는 것을 권장합니다. 현재 애플리케이션 자체에는 로그인 기능이 없습니다.

## 주요 API

- `GET /` : 업로드 UI
- `GET /upload` : 업로드 UI
- `GET /healthz` : storage 쓰기 가능 여부 확인
- `POST /api/uploads` : 이미지 업로드 및 job 생성
- `GET /api/jobs/{jobId}` : job 상태 조회
- `GET /api/jobs/{jobId}/csv` : CSV 다운로드

## 저장 위치

기본 저장 위치는 다음과 같습니다.

```text
storage/jobs
```

환경 변수로 변경할 수 있습니다.

```powershell
$env:BARCODE_READER_STORAGE_DIR = "D:\barcode-reader\jobs"
```

job 하나는 다음 구조로 저장됩니다.

```text
storage/jobs/{jobId}/
  metadata.json
  events.jsonl
  results.csv
  uploads/
    image_001.jpg
```

## Cleanup

기본 보존 기간은 7일입니다. 먼저 dry-run으로 삭제 후보를 확인합니다.

```powershell
python scripts\cleanup_uploads.py --retention-days 7
```

실제 삭제는 `--execute`를 붙입니다.

```powershell
python scripts\cleanup_uploads.py --retention-days 7 --execute
```

`completed`, `partial_failed`, `failed` 상태의 terminal job만 삭제 대상입니다. `queued`, `processing` 상태는 삭제하지 않습니다.

## Smoke Test

서비스를 띄운 뒤 배포 smoke test를 실행할 수 있습니다.

```powershell
python scripts\smoke_test.py --base-url http://127.0.0.1:8000 --image sample_images\image_01.jfif
```

확인 항목:

- `/healthz`
- 이미지 업로드
- job 상태 조회
- CSV 다운로드
- CSV header 확인

## 테스트

```powershell
python -m unittest discover -s tests -p "test_*.py"
python -m compileall src tests scripts
```

## 참고 문서

- [Backend API](docs/backend-api.md)
- [Web Upload UI](docs/web-upload-ui.md)
- [Upload Policy](docs/upload-policy.md)
- [CSV Schema](docs/csv-schema.md)
- [Deployment](docs/deployment.md)
- [Operations](docs/operations.md)
- [Reliability Report](docs/reliability-report.md)
