# Phase 6 Agent Guide: Quality and Reliability

## Mission

이 Phase의 목표는 샘플 회귀 테스트, 실패 케이스, 대량 처리, 로그, retry 정책을 정리해서 시스템을 안정화하는 것이다. Codex는 구현된 기능이 반복 실행과 예외 상황에서도 일관되게 동작하는지 검증한다.

## Read First

- `../../workflow.md`
- `../phase-2-core-processing/agent.md`
- `../phase-3-csv-result-engine/agent.md`
- `../phase-4-backend-api-job/agent.md`
- `../phase-5-web-upload-ui/agent.md`

## Scope

해야 할 일:

- `sample_images` 기반 회귀 테스트를 자동화한다.
- 깨진 이미지, 바코드 없는 이미지, 여러 바코드 이미지, 큰 이미지 fixture를 추가한다.
- 처리 시간, 성공률, 실패 사유를 로그로 남긴다.
- 대량 업로드와 timeout 위험을 검증한다.
- worker queue가 도입되었다면 retry와 중복 실행 방지를 검증한다.

하지 않을 일:

- 새로운 기능을 크게 추가하지 않는다.
- 검증 없이 디코더나 전처리 전략을 공격적으로 바꾸지 않는다.
- 운영 배포 환경 설정을 이 Phase의 주 작업으로 삼지 않는다.

## Suggested Files

프로젝트에 아직 구조가 없으면 다음 파일을 고려한다.

- `tests/test_regression_samples.py`
- `tests/test_failure_cases.py`
- `tests/test_large_uploads.py`
- `tests/fixtures/`
- `docs/reliability-report.md`

## Test Categories

- Sample regression
- CSV schema regression
- API integration
- Browser E2E
- Invalid upload
- Corrupted image
- Multiple barcodes
- No barcode
- Large image or many images
- Worker retry and idempotency

## Implementation Notes

- 테스트 결과는 통과/실패뿐 아니라 실패 파일명과 실패 사유를 보여줘야 한다.
- 샘플 기대값이 아직 확정되지 않은 이미지는 별도 `needs_review` 그룹으로 분리한다.
- 대량 처리 테스트는 로컬 환경을 망가뜨리지 않도록 합리적인 상한을 둔다.
- 로그에는 최소한 `job_id`, `source_filename`, `status`, `error_message`, `elapsed_ms`를 포함한다.
- flaky 테스트는 원인을 기록하고, 단순 sleep보다 상태 기반 대기를 사용한다.

## Verification

- 회귀 테스트를 반복 실행해 결과가 안정적인지 확인한다.
- 깨진 이미지, 바코드 없는 이미지, 여러 바코드 이미지, 매우 큰 이미지 fixture를 포함해 테스트한다.
- 대량 업로드 시 처리 시간, 메모리 사용량, timeout 발생 여부를 기록한다.
- 로그에 `job_id`, `source_filename`, `status`, `error_message`가 남는지 확인한다.
- worker queue를 사용하는 경우 재시도, 실패 처리, 중복 실행 방지가 동작하는지 확인한다.

## Deliverables

- Automated regression tests
- Failure-case fixtures
- Reliability report
- Logging and retry policy notes

## Handoff to Phase 7

Phase 7은 이 Phase의 테스트 명령과 reliability report를 배포 smoke test와 운영 점검 항목으로 사용한다. 배포 전에 반드시 통과해야 하는 최소 테스트 세트를 명확히 넘긴다.

