# Codex Agent References

이 폴더는 `workflow.md`의 각 Phase를 수행할 때 Codex가 참조할 작업 지시서를 담는다.
각 Phase 작업을 시작하기 전에 해당 폴더의 `agent.md`를 먼저 읽는다.

| Phase | Agent Guide |
| --- | --- |
| Phase 0: Requirements and Sample Baseline | `phase-0-requirements/agent.md` |
| Phase 1: Decoder PoC | `phase-1-decoder-poc/agent.md` |
| Phase 2: Core Processing Library | `phase-2-core-processing/agent.md` |
| Phase 3: CSV Result Engine | `phase-3-csv-result-engine/agent.md` |
| Phase 4: Backend API and Job Processing | `phase-4-backend-api-job/agent.md` |
| Phase 5: Web Upload UI | `phase-5-web-upload-ui/agent.md` |
| Phase 6: Quality and Reliability | `phase-6-quality-reliability/agent.md` |
| Phase 7: Deploy and Operations | `phase-7-deploy-operations/agent.md` |

공통 원칙:

- `workflow.md`를 상위 계획으로 삼고, 각 `agent.md`를 해당 Phase의 실행 지침으로 삼는다.
- 이전 Phase의 산출물이 없으면 먼저 누락을 기록하고, 필요한 최소 산출물을 만든 뒤 진행한다.
- 각 Phase는 검증 단계를 통과해야 다음 Phase로 넘어간다.
- 새 파일이나 API를 만들 때는 후속 Phase가 재사용할 수 있도록 이름과 결과 구조를 안정적으로 유지한다.

