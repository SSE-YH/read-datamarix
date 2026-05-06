# Phase 5 Agent Guide: Web Upload UI

## Mission

이 Phase의 목표는 사용자가 브라우저에서 이미지를 업로드하고, 처리 상태를 확인한 뒤 CSV를 다운로드할 수 있는 실제 작업 화면을 만드는 것이다.

## Read First

- `../../workflow.md`
- `../phase-4-backend-api-job/agent.md`
- Phase 4 API 응답 형식

## Scope

해야 할 일:

- 다중 이미지 선택과 드래그 앤 드롭 업로드 UI를 만든다.
- 파일명, 크기, 검증 상태를 보여준다.
- 업로드 진행률과 job 처리 상태를 표시한다.
- 완료 또는 부분 실패 상태에서 CSV 다운로드 버튼을 제공한다.
- 실패한 파일과 사유를 사용자에게 보여준다.

하지 않을 일:

- 랜딩 페이지나 마케팅 페이지를 만들지 않는다.
- 디코딩 로직을 브라우저에 중복 구현하지 않는다.
- 서버 검증을 클라이언트 검증으로 대체하지 않는다.

## UI Principles

- 첫 화면은 바로 업로드 작업을 할 수 있는 도구 화면이어야 한다.
- 상태는 `대기`, `업로드 중`, `분석 중`, `완료`, `부분 실패`, `실패`처럼 명확히 구분한다.
- 업로드 제한은 사용자가 파일을 선택한 즉시 알려준다.
- CSV 다운로드는 완료 상태에서 눈에 잘 띄어야 한다.
- 모바일과 데스크톱에서 텍스트와 버튼이 겹치지 않아야 한다.

## Suggested Files

프로젝트에 아직 구조가 없으면 사용하는 frontend framework에 맞춰 다음 책임을 나눈다.

- `src/pages/upload` 또는 `src/app/page`
- `src/components/FileDropzone`
- `src/components/JobStatus`
- `src/components/ResultSummary`
- `src/lib/api`
- UI/E2E 테스트 파일

## Implementation Notes

- API field name은 `images`를 사용한다.
- 사용자가 같은 파일을 다시 선택할 수 있도록 input reset 흐름을 처리한다.
- job polling은 중복 timer가 생기지 않게 관리한다.
- 네트워크 오류는 재시도 가능한 상태와 최종 실패 상태를 구분한다.
- 다운로드는 Phase 4의 CSV endpoint를 사용한다.
- 서버 오류 메시지를 그대로 노출하기 전에 사용자에게 의미 있는 문장으로 정리한다.

## Verification

- 브라우저에서 `sample_images` 여러 장을 선택해 업로드부터 CSV 다운로드까지 확인한다.
- 드래그 앤 드롭, 파일 선택, 선택 취소, 재업로드 흐름이 깨지지 않는지 확인한다.
- 클라이언트 파일 검증과 서버 검증 오류가 사용자에게 이해 가능한 문장으로 표시되는지 확인한다.
- job polling 중 새로고침하거나 네트워크가 잠시 실패해도 복구 가능한지 확인한다.
- 데스크톱과 모바일 폭에서 파일 목록, 상태, 다운로드 버튼이 겹치지 않는지 확인한다.

## Deliverables

- Web upload page
- Upload/progress/result UI
- CSV download interaction
- Browser-level verification notes

## Handoff to Phase 6

Phase 6은 이 UI와 API를 대상으로 회귀 테스트, 실패 fixture, 대량 처리 검증을 추가한다. UI에서 발견한 모호한 상태나 오류 메시지는 개선 대상으로 넘긴다.

