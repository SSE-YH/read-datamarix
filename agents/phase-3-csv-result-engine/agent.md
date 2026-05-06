# Phase 3 Agent Guide: CSV Result Engine

## Mission

이 Phase의 목표는 core processing 결과를 안정적인 CSV 파일로 변환하는 것이다. Codex는 성공, 미검출, 디코딩 실패, 시스템 오류를 모두 누락 없이 row로 표현한다.

## Read First

- `../../workflow.md`
- `../phase-2-core-processing/agent.md`
- Phase 0의 CSV 스키마
- Phase 2의 `BarcodeResult` 모델

## Scope

해야 할 일:

- `BarcodeResult` 목록을 CSV row로 변환한다.
- 이미지별 결과가 없을 때도 `not_found` row를 만든다.
- 여러 바코드가 있는 이미지에는 `barcode_index`를 순서대로 부여한다.
- CSV escaping, 인코딩, 필수 컬럼 누락을 테스트한다.

하지 않을 일:

- HTTP 다운로드 endpoint를 만들지 않는다.
- UI 전용 컬럼을 CSV에 섣불리 추가하지 않는다.
- 실패 이미지를 CSV에서 누락하지 않는다.

## Required CSV Columns

아래 순서를 기본으로 유지한다.

```text
job_id,source_filename,image_index,barcode_index,barcode_type,decoded_text,confidence,bbox_x,bbox_y,bbox_width,bbox_height,status,error_message
```

## Suggested Files

프로젝트에 아직 구조가 없으면 다음 파일을 고려한다.

- `src/barcode_reader/csv_export.py`
- `tests/test_csv_export.py`
- `reports/sample-output.csv`

## Implementation Notes

- CSV writer는 표준 라이브러리나 검증된 CSV 라이브러리를 사용한다.
- 문자열 결합으로 CSV를 직접 만들지 않는다.
- `decoded_text`에 쉼표, 따옴표, 줄바꿈이 있어도 깨지지 않아야 한다.
- 기본 인코딩은 `UTF-8`로 한다.
- Excel 호환성이 요구되면 `UTF-8 BOM` 옵션을 설정 가능하게 만든다.
- row 순서는 `image_index`, `barcode_index` 기준으로 안정적으로 유지한다.

## Verification

- CSV 헤더가 확정 스키마와 정확히 일치하는지 테스트한다.
- 성공 결과, 미검출 결과, 디코딩 실패 결과, 시스템 오류 결과가 모두 row로 생성되는지 확인한다.
- 쉼표, 따옴표, 줄바꿈이 포함된 `decoded_text`가 정상 escape되는지 확인한다.
- 한 이미지에 여러 결과가 있을 때 `barcode_index`가 순서대로 부여되는지 확인한다.
- 생성된 CSV를 스프레드시트 도구에서 열어 인코딩과 컬럼 분리가 정상인지 확인한다.

## Deliverables

- CSV export module
- CSV schema tests
- 샘플 출력 CSV
- 인코딩 정책

## Handoff to Phase 4

Phase 4는 이 CSV export module을 API 다운로드 응답에 연결한다. CSV 생성 함수는 파일 저장 방식과 HTTP 응답 방식 모두에서 재사용 가능해야 한다.

