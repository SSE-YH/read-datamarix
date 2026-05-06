# Phase 2 Agent Guide: Core Processing Library

## Mission

이 Phase의 목표는 웹/API와 독립적으로 사용할 수 있는 바코드 리딩 core library를 만드는 것이다. Codex는 이미지 입력을 받아 표준 결과 객체를 반환하는 안정적인 처리 파이프라인을 구현한다.

## Read First

- `../../workflow.md`
- `../phase-1-decoder-poc/agent.md`
- Phase 1의 디코더 PoC 결과와 실패 이미지 목록

## Scope

해야 할 일:

- 이미지 로딩, EXIF orientation 보정, 전처리, 디코딩, 중복 제거를 core 함수로 묶는다.
- Data Matrix와 QR Code 리딩을 우선 지원한다.
- 실패도 예외가 아닌 구조화된 결과로 반환한다.
- 단위 테스트로 성공/실패/오류 케이스를 검증한다.

하지 않을 일:

- HTTP endpoint를 만들지 않는다.
- CSV 다운로드 API를 만들지 않는다.
- UI 상태 관리에 맞춰 core result 구조를 과하게 바꾸지 않는다.

## Suggested Files

프로젝트에 아직 구조가 없으면 다음 구조를 고려한다.

- `src/barcode_reader/core.py`
- `src/barcode_reader/preprocess.py`
- `src/barcode_reader/decoders.py`
- `src/barcode_reader/models.py`
- `tests/test_core_reader.py`

## Result Model

Core result는 다음 정보를 담을 수 있어야 한다.

- `source_filename`
- `barcode_index`
- `barcode_type`
- `decoded_text`
- `confidence`
- `bbox`
- `status`
- `error_message`
- `decoder_name`
- `preprocess_variant`

## Implementation Notes

- public API는 단순하게 유지한다. 예: `read_barcodes(image_path) -> list[BarcodeResult]`
- 원본, grayscale, sharpen, threshold, scale, rotate variant를 순차적으로 시도한다.
- 디코더별 결과를 공통 모델로 normalize한다.
- 동일한 `barcode_type + decoded_text + bbox 근접값`은 중복 제거한다.
- bbox가 없는 디코더는 bbox 필드를 비워 두되, 전체 결과 생성을 막지 않는다.
- 로그나 debug mode에서 어떤 variant가 성공했는지 추적 가능하게 한다.

## Verification

- `read_barcodes(image)` 단위 테스트를 작성해 `success`, `not_found`, `decode_failed`, `error`를 검증한다.
- 깨진 이미지나 지원하지 않는 이미지가 들어와도 전체 프로세스가 중단되지 않는지 확인한다.
- 전처리 variant별 시도 순서와 최종 성공 variant가 추적되는지 확인한다.
- 중복 바코드는 하나로 합쳐지고, 서로 다른 바코드는 여러 결과로 유지되는지 확인한다.
- bbox가 반환되는 경우 이미지의 width/height 범위를 벗어나지 않는지 확인한다.

## Deliverables

- Core barcode reading API
- Preprocessing pipeline
- Decoder adapter layer
- Unit tests
- 실패 사유 코드 목록

## Handoff to Phase 3

Phase 3은 이 Phase의 `BarcodeResult` 모델을 CSV row로 변환한다. 모델 필드명을 바꾸면 CSV schema와 테스트 fixture도 함께 업데이트해야 한다.

