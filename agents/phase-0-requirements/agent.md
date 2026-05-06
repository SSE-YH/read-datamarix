# Phase 0 Agent Guide: Requirements and Sample Baseline

## Mission

이 Phase의 목표는 구현 전에 기준선을 확정하는 것이다. Codex는 샘플 이미지, 지원 범위, CSV 스키마, 실패 처리 정책을 명확히 정리해서 이후 Phase가 흔들리지 않도록 만든다.

## Read First

- `../../workflow.md`
- `../../sample_images/`

## Scope

해야 할 일:

- `sample_images`의 전체 파일 목록을 확인한다.
- 각 이미지의 기대 리딩 결과를 정리할 수 있는 fixture 구조를 제안하거나 생성한다.
- 초기 지원 바코드 범위를 `DataMatrix`, `QRCode`로 둔다.
- CSV 컬럼과 실패 row 정책을 확정한다.
- 업로드 파일 제한 정책을 문서화한다.

하지 않을 일:

- 실제 디코더 성능 개선을 깊게 구현하지 않는다.
- 웹 UI나 API를 만들지 않는다.
- 기대값을 확인하지 못한 이미지는 임의로 성공값을 만들어 넣지 않는다.

## Suggested Files

프로젝트에 아직 구조가 없으면 다음 파일을 만들 수 있다.

- `docs/sample-baseline.md`
- `tests/fixtures/expected_results.csv`
- `docs/upload-policy.md`

## Expected CSV Columns

CSV 스키마는 기본적으로 아래 컬럼을 유지한다.

- `job_id`
- `source_filename`
- `image_index`
- `barcode_index`
- `barcode_type`
- `decoded_text`
- `confidence`
- `bbox_x`
- `bbox_y`
- `bbox_width`
- `bbox_height`
- `status`
- `error_message`

## Implementation Notes

- 기대값을 모르면 `status`를 `unknown` 또는 `needs_review`로 두고, 별도 리뷰 대상으로 남긴다.
- 샘플 파일 수, 파일명, 확장자, 대략적인 품질 이슈를 기록한다.
- 이후 자동 테스트가 이 기준 파일을 참조할 수 있도록 machine-readable 형태를 선호한다.
- 사람이 읽는 문서와 테스트 fixture를 분리하면 유지보수가 쉽다.

## Verification

- `sample_images`의 전체 파일 수와 fixture row 수가 일치하는지 확인한다.
- 모든 샘플 파일이 기대값 문서 또는 fixture에 등장하는지 확인한다.
- CSV 헤더가 `workflow.md`의 스키마와 일치하는지 확인한다.
- 성공, 미검출, 디코딩 실패, 시스템 오류의 의미가 구분되어 있는지 확인한다.

## Deliverables

- 샘플 이미지 기준표
- 기대 리딩값 fixture 또는 초안
- CSV 스키마 확정
- 업로드 제한 정책

## Handoff to Phase 1

Phase 1은 이 Phase에서 만든 기대값과 샘플 목록을 기준으로 디코더 PoC 결과를 비교한다. 기대값이 비어 있는 샘플은 PoC 결과가 나오더라도 검증 통과로 간주하지 말고 리뷰 대상으로 표시한다.

