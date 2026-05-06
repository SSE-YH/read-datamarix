# Phase 1 Agent Guide: Decoder PoC

## Mission

이 Phase의 목표는 샘플 이미지에서 실제로 바코드를 읽어 보고, 초기 구현에 사용할 디코더 조합을 결정하는 것이다. Codex는 빠른 로컬 PoC를 만들고 디코더별 성공률, 실패 파일, 처리 시간을 비교한다.

## Read First

- `../../workflow.md`
- `../phase-0-requirements/agent.md`
- Phase 0에서 생성한 샘플 기준표와 기대값 fixture

## Scope

해야 할 일:

- `sample_images` 전체를 대상으로 자동 실행 가능한 PoC를 만든다.
- Data Matrix 후보 디코더와 QR 후보 디코더를 최소 1개 이상씩 테스트한다.
- 디코더별 성공/실패 결과와 처리 시간을 기록한다.
- 초기 프로덕션 구현에 사용할 디코더 우선순위를 제안한다.

하지 않을 일:

- 완전한 웹/API 구조를 만들지 않는다.
- 복잡한 비동기 job 처리를 만들지 않는다.
- 모든 난이도 높은 이미지 케이스를 이 Phase에서 해결하려고 하지 않는다.

## Suggested Files

프로젝트에 아직 구조가 없으면 다음 파일을 만들 수 있다.

- `scripts/poc_decode.py`
- `reports/decoder-poc-results.csv`
- `reports/decoder-poc-summary.md`
- `requirements.txt` 또는 해당 언어의 dependency 파일

## Decoder Candidates

우선 검토할 후보:

- Data Matrix: `pylibdmtx`, `libdmtx`, `ZXing`
- QR Code: `OpenCV QRCodeDetector`, `pyzbar`, `ZXing`
- 전처리: `OpenCV`

환경에서 native dependency 설치가 막히면, 설치 실패 사유와 대체 후보를 기록한다.

## Implementation Notes

- 한 번의 명령으로 전체 샘플을 처리할 수 있게 만든다.
- 결과에는 최소한 `source_filename`, `decoder_name`, `barcode_type`, `decoded_text`, `status`, `elapsed_ms`를 포함한다.
- 디코더가 여러 결과를 반환하면 모두 기록한다.
- 예외가 발생해도 전체 실행이 중단되지 않게 파일 단위로 실패를 기록한다.
- Phase 0 기대값과 비교할 수 있도록 결과 파일을 CSV로 남긴다.

## Verification

- PoC 명령을 실행했을 때 `sample_images`의 모든 파일이 처리되는지 확인한다.
- 결과 CSV의 row가 누락 없이 생성되는지 확인한다.
- Phase 0 기대값과 비교해 성공/실패 차이를 기록한다.
- 디코더별 성공률, 실패 파일 목록, 평균 처리 시간을 산출한다.
- 선택한 디코더 조합으로 `DataMatrix`, `QRCode` 각각의 처리 전략을 설명할 수 있어야 한다.

## Deliverables

- 로컬 PoC 스크립트
- 디코더별 결과 CSV
- 디코더 선택 요약 문서
- dependency 설치 메모

## Handoff to Phase 2

Phase 2는 이 Phase의 디코더 우선순위와 실패 사례를 바탕으로 core processing library를 만든다. 실패 이미지는 전처리 전략 설계의 주요 입력으로 넘긴다.

