# Phase 0 Sample Baseline

이 문서는 `sample_images` 폴더의 샘플을 후속 Phase에서 반복 검증할 수 있는 기준선으로 고정한다.
Phase 0에서는 실제 디코더 성능을 판정하지 않으며, 확인되지 않은 리딩값은 임의로 채우지 않는다.

## Scope

- 초기 지원 바코드: `DataMatrix`, `QRCode`
- 이후 확장 후보: `Code128`, `EAN`, `PDF417`
- 런타임 CSV 상태값: `success`, `not_found`, `decode_failed`, `error`
- Phase 0 fixture 전용 상태값: `needs_review`

`needs_review`는 기대 리딩값을 아직 사람 또는 PoC 결과로 확정하지 못했다는 뜻이다. 서비스 런타임 결과 CSV에는 사용하지 않는다.

## Sample Inventory

샘플 파일 수: 7개

| image_index | source_filename | extension | size_bytes | dimensions | pixel_format | sha256 |
| --- | --- | --- | ---: | --- | --- | --- |
| 1 | `image_01.jfif` | `.jfif` | 4708 | 329x153 | Format24bppRgb | `3A1A58DC6B448660C1705831628765D2A9DEB90239F92D632D15ADB220C1DDAA` |
| 2 | `image_02.jfif` | `.jfif` | 8637 | 225x225 | Format24bppRgb | `4037A202A1C6D6480152550E5A980D43E9CC85459CDA7E124F49D91FCB34818F` |
| 3 | `image_03.jfif` | `.jfif` | 8601 | 225x225 | Format24bppRgb | `7C8C1889757946795B0E4E884E12E3B396054F5906654C7BCAE6037F8DD9D0CE` |
| 4 | `image_04.jfif` | `.jfif` | 3624 | 318x159 | Format24bppRgb | `6BA3941BFBC4CE6C46057163193D00647EE35E25262EADD345D3C282E5332417` |
| 5 | `image_05.jfif` | `.jfif` | 9476 | 259x194 | Format24bppRgb | `E8F78495AD7CD4BC9870166E3E9B8E689FDD84B8AFE8DBE260EE0DD163C381EB` |
| 6 | `image_06.jfif` | `.jfif` | 10927 | 299x168 | Format24bppRgb | `5DC927AA6B1F44A56C61E6702C29D3F9AA6ECB5D3E6E1EF4158F4695BD6F897D` |
| 7 | `image_07.jpg` | `.jpg` | 131920 | 1084x657 | Format24bppRgb | `1B7260C7FE7001EB7C29BEE7B4808F945D85220B05C4E2715AEEADACFD742EDA` |

## Quality Notes

- 모든 샘플은 `System.Drawing` 기준으로 열 수 있으며, 24-bit RGB 이미지다.
- `image_01`부터 `image_06`까지는 작은 래스터 이미지이므로 Phase 1/2에서 확대 재시도와 threshold 전처리를 검토한다.
- `image_07`은 다른 샘플보다 큰 실제 촬영 이미지에 가까우므로 처리 시간과 후보 영역 탐지 로그를 함께 기록한다.
- 실제 바코드 타입, 디코딩 가능 여부, 정답 문자열은 Phase 1 Decoder PoC 또는 수동 검수로 확정한다.

## Expected Results Fixture

기준 fixture는 [tests/fixtures/expected_results.csv](../tests/fixtures/expected_results.csv)에 둔다.

현재 모든 샘플은 `needs_review` 상태로 등록되어 있다. Phase 1에서 디코더 PoC 결과가 나오면 다음 규칙으로 fixture를 갱신한다.

- 바코드를 정상 리딩한 경우: `success` row를 바코드 개수만큼 기록하고 `barcode_index`를 1부터 부여한다.
- 바코드가 없다고 판단한 경우: 이미지별로 `not_found` row 1개를 기록한다.
- 바코드 후보는 있으나 문자열을 읽지 못한 경우: `decode_failed` row를 기록한다.
- 이미지 로딩, 전처리, 디코더 예외 등 시스템 문제가 생긴 경우: `error` row를 기록하고 로그에서 추적 가능한 메시지를 남긴다.

## Handoff

Phase 1은 이 문서의 샘플 목록과 fixture를 입력 기준으로 사용한다. `needs_review` row는 PoC 성공으로 자동 통과시키지 말고, 사람이 검수 가능한 결과로 별도 표시한다.
