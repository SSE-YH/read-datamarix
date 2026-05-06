# Phase 4 Agent Guide: Backend API and Job Processing

## Mission

이 Phase의 목표는 웹 업로드부터 job 상태 조회, CSV 다운로드까지 가능한 backend API를 만드는 것이다. Codex는 Phase 2 core reader와 Phase 3 CSV engine을 서버 흐름에 연결한다.

## Read First

- `../../workflow.md`
- `../phase-2-core-processing/agent.md`
- `../phase-3-csv-result-engine/agent.md`

## Scope

해야 할 일:

- 다중 이미지 업로드 API를 만든다.
- 업로드 파일 검증과 저장 정책을 구현한다.
- job 상태 모델과 결과 저장 방식을 만든다.
- CSV 다운로드 endpoint를 만든다.
- 초기에는 동기 처리로 시작할 수 있으나, 긴 처리 시간에 대비해 worker queue 전환 지점을 분리한다.

하지 않을 일:

- 프론트엔드 UI를 깊게 구현하지 않는다.
- 운영 배포 자동화까지 이 Phase에서 완성하지 않는다.
- 사용자 인증/권한을 요구사항 없이 크게 설계하지 않는다.

## Required Endpoints

- `POST /api/uploads`
- `GET /api/jobs/{jobId}`
- `GET /api/jobs/{jobId}/csv`

## Job Status

기본 상태값:

- `queued`
- `processing`
- `completed`
- `partial_failed`
- `failed`

## Suggested Files

프로젝트에 아직 구조가 없으면 사용하는 framework에 맞춰 다음 책임을 나눈다.

- `src/barcode_reader/api/uploads.py`
- `src/barcode_reader/api/jobs.py`
- `src/barcode_reader/jobs.py`
- `src/barcode_reader/storage.py`
- `tests/test_api_uploads.py`
- `tests/test_api_jobs.py`

## Implementation Notes

- 업로드 field name은 기본적으로 `images`를 사용한다.
- 파일 타입, 파일 크기, 업로드 개수 제한을 서버에서 반드시 재검증한다.
- job별 업로드 파일, 결과, CSV가 섞이지 않도록 job directory 또는 job namespace를 사용한다.
- CSV가 준비되기 전 다운로드 요청에는 명확한 상태 코드와 메시지를 반환한다.
- 처리 중 예외가 발생해도 job 상태와 error row를 남긴다.
- API 응답에는 사용자가 이해할 수 있는 오류 메시지를 포함한다.

## Verification

- 정상 이미지 여러 장을 `POST /api/uploads`로 업로드해 `jobId`가 반환되는지 확인한다.
- 빈 업로드, 지원하지 않는 확장자, 제한 초과 파일이 올바른 오류 응답을 반환하는지 확인한다.
- `GET /api/jobs/{jobId}`가 상태와 처리 요약을 일관되게 반환하는지 확인한다.
- CSV 준비 전 다운로드 요청이 정의된 상태 코드와 메시지를 반환하는지 확인한다.
- 동시에 여러 job을 생성해도 파일, 결과, CSV가 서로 섞이지 않는지 확인한다.

## Deliverables

- Backend API
- Job metadata model
- Upload/result/CSV storage flow
- API integration tests

## Handoff to Phase 5

Phase 5는 이 API를 호출하는 web upload UI를 만든다. API 응답 필드명과 상태값은 UI가 그대로 사용할 수 있도록 문서화해서 넘긴다.

