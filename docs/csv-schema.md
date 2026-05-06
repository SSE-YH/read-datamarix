# CSV Schema

분석 결과 CSV는 성공과 실패를 모두 같은 스키마의 row로 표현한다. 실패한 이미지도 누락하지 않는다.

## Header

```csv
job_id,source_filename,image_index,barcode_index,barcode_type,decoded_text,confidence,bbox_x,bbox_y,bbox_width,bbox_height,status,error_message
```

## Column Rules

| Column | Required | Rule |
| --- | --- | --- |
| `job_id` | yes | 업로드 작업 ID. Fixture에서는 `phase0_baseline`을 사용한다. |
| `source_filename` | yes | 사용자가 업로드한 원본 파일명 basename. |
| `image_index` | yes | 업로드 순서. 1부터 시작한다. |
| `barcode_index` | success only | 한 이미지 안의 바코드 순서. 1부터 시작한다. 실패 row는 비울 수 있다. |
| `barcode_type` | success only | 초기값은 `DataMatrix` 또는 `QRCode`. |
| `decoded_text` | success only | 디코딩된 문자열. CSV escaping은 표준 CSV writer에 맡긴다. |
| `confidence` | no | 0.0부터 1.0 사이의 내부 품질 점수. 없으면 빈 값. |
| `bbox_x` | no | 원본 이미지 기준 바코드 영역 x 좌표. 없으면 빈 값. |
| `bbox_y` | no | 원본 이미지 기준 바코드 영역 y 좌표. 없으면 빈 값. |
| `bbox_width` | no | 바코드 영역 너비. 없으면 빈 값. |
| `bbox_height` | no | 바코드 영역 높이. 없으면 빈 값. |
| `status` | yes | 런타임 CSV는 `success`, `not_found`, `decode_failed`, `error` 중 하나. |
| `error_message` | failure only | 실패나 오류 사유. 성공 row는 빈 값. |

## Status Policy

- `success`: 바코드 타입과 문자열이 확정된 상태.
- `not_found`: 이미지 처리에는 성공했지만 대상 바코드 후보를 찾지 못한 상태.
- `decode_failed`: 대상 바코드 후보는 찾았지만 문자열 디코딩에 실패한 상태.
- `error`: 이미지 로딩, 전처리, 저장소, 디코더 호출 등 시스템 예외가 발생한 상태.
- `needs_review`: Phase 0 fixture에서만 사용하는 임시 상태. 런타임 결과 CSV에는 쓰지 않는다.

## Encoding

- 기본 인코딩은 UTF-8이다.
- 줄바꿈은 플랫폼과 무관하게 표준 CSV reader가 읽을 수 있어야 한다.
- Excel 호환성이 반드시 필요해지면 다운로드 응답에서 UTF-8 BOM 옵션을 별도로 검토한다.

## Examples

```csv
job_id,source_filename,image_index,barcode_index,barcode_type,decoded_text,confidence,bbox_x,bbox_y,bbox_width,bbox_height,status,error_message
job_20260506_001,image_01.jfif,1,1,DataMatrix,ABC123456,0.92,120,80,64,64,success,
job_20260506_001,image_02.jfif,2,,,,,,,,,not_found,barcode not found
job_20260506_001,image_03.jfif,3,,,,,,,,,decode_failed,barcode candidate could not be decoded
job_20260506_001,image_04.jfif,4,,,,,,,,,error,image load failed
```
