# Upload Policy

이 정책은 Phase 4 API와 Phase 5 UI가 같은 기준으로 파일을 검증하도록 고정한다.

## Accepted Files

지원 확장자:

- `.jpg`
- `.jpeg`
- `.jfif`
- `.png`
- `.bmp`
- `.tif`
- `.tiff`

지원 MIME 타입:

- `image/jpeg`
- `image/png`
- `image/bmp`
- `image/tiff`

검증은 확장자와 MIME 타입만 믿지 않고, 서버에서 이미지 parser로 실제 로딩 가능한지 확인한다.

## Limits

| Limit | Value |
| --- | ---: |
| 최소 파일 크기 | 1 byte |
| 이미지 1개 최대 파일 크기 | 20 MiB |
| 1회 업로드 최대 이미지 수 | 100 |
| 1회 업로드 총 파일 크기 | 250 MiB |
| 최대 이미지 한 변 길이 | 10000 px |
| 최대 디코딩 픽셀 수 | 75 MP |

현재 `sample_images` 7개는 위 제한을 모두 통과한다.

## Upload Field

- API field name: `images`
- Content type: `multipart/form-data`
- 빈 업로드는 `400 Bad Request`로 거부한다.
- 일부 파일이 제한을 넘으면 전체 요청을 거부하고, 파일별 오류 목록을 반환한다.

## Filename And Storage Rules

- 원본 파일명은 metadata와 CSV의 `source_filename`에 보존한다.
- 저장 경로에는 원본 파일명을 직접 쓰지 않고, job ID와 안전한 내부 파일 ID를 사용한다.
- 경로 구분자, 제어 문자, 앞뒤 공백은 저장 전에 제거하거나 치환한다.
- 동일 이름의 파일이 여러 개 올라와도 `image_index`로 순서를 구분한다.

## Error Categories

| Case | API Result | CSV Result |
| --- | --- | --- |
| 지원하지 않는 확장자 또는 MIME 타입 | 업로드 거부 | CSV 생성 전 오류 |
| 빈 파일 | 업로드 거부 | CSV 생성 전 오류 |
| 파일 크기 또는 개수 제한 초과 | 업로드 거부 | CSV 생성 전 오류 |
| 이미지 parser로 열 수 없음 | 업로드 거부 또는 `error` row | `error` |
| 바코드 후보 없음 | 업로드 성공 | `not_found` |
| 바코드 후보는 있으나 디코딩 실패 | 업로드 성공 | `decode_failed` |

업로드 단계에서 확정할 수 있는 잘못된 파일은 즉시 거부한다. 처리 중에 발생한 이미지별 실패는 CSV row로 남긴다.
