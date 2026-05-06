# Phase 7 Agent Guide: Deploy and Operations

## Mission

이 Phase의 목표는 서비스를 실제 환경에서 실행하고 운영할 수 있게 만드는 것이다. Codex는 dependency, 환경 변수, 파일 보관 정책, smoke test, 운영 로그를 정리한다.

## Read First

- `../../workflow.md`
- `../phase-6-quality-reliability/agent.md`
- Phase 6의 최소 통과 테스트 세트와 reliability report

## Scope

해야 할 일:

- 배포 환경에 필요한 native dependency를 문서화한다.
- 환경 변수와 설정값을 정리한다.
- 업로드 이미지, 결과, CSV의 보관/삭제 정책을 구현하거나 문서화한다.
- 운영 smoke test 절차를 만든다.
- 로그와 오류 추적 경로를 확인한다.

하지 않을 일:

- 핵심 디코딩 로직을 크게 다시 설계하지 않는다.
- 운영 중 사용할 수 없는 실험용 dependency를 추가하지 않는다.
- 비밀값을 저장소에 커밋하지 않는다.

## Dependencies to Check

환경에 따라 아래 항목이 필요할 수 있다.

- OpenCV runtime
- `libdmtx`
- `zbar`
- `ZXing`
- 이미지 처리 관련 native library
- worker queue runtime 또는 broker

## Suggested Files

프로젝트에 아직 구조가 없으면 다음 파일을 고려한다.

- `docs/deployment.md`
- `docs/operations.md`
- `.env.example`
- `scripts/smoke_test.*`
- `scripts/cleanup_uploads.*`

## Implementation Notes

- 설치 문서는 새 환경에서 그대로 따라 할 수 있어야 한다.
- `.env.example`에는 키 이름과 설명만 넣고 실제 비밀값은 넣지 않는다.
- cleanup 작업은 job 상태와 파일 보관 기간을 고려해서 안전하게 동작해야 한다.
- smoke test는 업로드, 상태 조회, CSV 다운로드까지 최소 흐름을 확인한다.
- 로그에서 특정 job의 실패 원인을 추적할 수 있어야 한다.

## Verification

- 배포 환경에서 native dependency 설치 후 샘플 이미지 smoke test를 실행한다.
- 운영 URL에서 업로드, 상태 조회, CSV 다운로드가 정상 동작하는지 확인한다.
- 파일 보관 기간이 지난 업로드 이미지와 CSV가 삭제되는지 cleanup 동작을 확인한다.
- 장애 상황을 가정해 오류 로그와 job 상태가 추적 가능한지 확인한다.
- 새 환경에서 문서만 보고 서비스를 재설치할 수 있는지 검증한다.

## Deliverables

- Deployment guide
- Operations guide
- Environment variable example
- Smoke test script or checklist
- File retention and cleanup policy

## Final Handoff

이 Phase가 끝나면 시스템은 샘플 이미지 기준으로 업로드, 분석, CSV 다운로드, 운영 점검까지 가능한 상태여야 한다. 남은 리스크는 known issues로 정리하고, 다음 개선 항목은 별도 backlog로 넘긴다.

