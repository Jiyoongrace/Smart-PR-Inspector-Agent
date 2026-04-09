# 모듈별 비즈니스 역할

> 각 파일/모듈이 비즈니스적으로 어떤 역할을 하는지 설명합니다.
> 코드만 봐서는 알 수 없는 "왜 이게 중요한지"를 RAG가 답변할 수 있도록 합니다.

## agents/nodes/ — Agent 핵심 노드

### fetcher.py (PR 데이터 수집)
- 비즈니스 역할: 모든 분석의 시작점. 이 노드가 실패하면 전체 파이프라인이 중단됨
- 주의: GitHub API rate limit (5,000 req/hour). 대량 PR 처리 시 한도 초과 가능
- 의존: PyGithub, GitHub REST API

### convention.py (컨벤션 검사)
- 비즈니스 역할: 코드 품질 게이트키퍼. 위반이 있으면 PR 코멘트에 경고 표시
- 비즈니스 임팩트: 컨벤션 위반 재발률을 PR당 2.3회 → 0.5회로 줄이는 것이 KPI
- 주의: LLM 호출은 diff 8KB 이하일 때만. 초과 시 AST만 사용하여 일부 패턴 놓칠 수 있음

### test_gen.py + test_runner.py (테스트 생성/검증)
- 비즈니스 역할: "개발자가 기획 의도대로 코드를 작성했는가"를 자동 검증
- 원래 설계: Docker에서 pytest 실행 → 환경 문제로 실패율 80%
- 현재 방식: Given/When/Then 시나리오를 AI가 diff 대비 평가 (pass/fail/unclear)
- 통과 기준: 전체 시나리오 중 60% 이상 pass

### impact.py (영향도 분석)
- 비즈니스 역할: "이 코드 바꾸면 어디가 터지나"를 사전에 파악
- 비즈니스 임팩트: 사이드 이펙트로 인한 장애를 사전 차단. 시니어 리뷰 요청 70% 감소 목표
- 방법: AST 호출 그래프 BFS (최대 깊이 3) + API 변경 감지 + LLM 비즈니스 임팩트
- 주의: 프로젝트 내 Python 파일 100개까지만 파싱. 대형 모노레포에서는 제한적

### domain_explainer.py (RAG 도메인 설명)
- 비즈니스 역할: 코드 변경의 비즈니스 의미를 비개발자도 이해할 수 있게 설명
- RAG 파이프라인: ChromaDB 벡터 검색 → 관련 문서 3건 → Claude 요약
- 핵심 가치: 다른 프로젝트에 붙일 때 docs/domain/만 교체하면 해당 도메인에 맞는 설명 생성
- 주의: ChromaDB 미연결 시 SKIPPED (코드만으로 추론)

### commenter.py (GitHub 코멘트)
- 비즈니스 역할: 모든 분석 결과를 하나의 PR 코멘트로 통합. 최종 산출물
- 주의: GitHub 코멘트 길이 제한 65,536자

### slack_notify.py (Slack 알림)
- 비즈니스 역할: 리뷰어가 GitHub을 안 열어도 Slack에서 바로 승인/거부 가능
- 인터랙티브: Block Kit 버튼 → /slack/interactions 엔드포인트 → GitHub API 호출

## api/webhook.py — API 서버

- 비즈니스 역할: GitHub Webhook 수신 + SSE 스트리밍 + REST API 제공
- 보안: HMAC-SHA256 서명 검증 필수 (미검증 시 악성 요청 처리 위험)
- 성능: 중복 분석 방지 (Redis 캐시, TTL 10분)

## config/ — 설정 및 프롬프트

### prompts.py
- 비즈니스 역할: 모든 LLM 프롬프트를 중앙 관리. 분석 품질에 직접 영향
- 주의: 프롬프트 수정 시 시나리오 검증 정확도가 달라질 수 있음. A/B 비교 권장

### conventions.yaml
- 비즈니스 역할: 팀 코딩 규칙의 원천. AST 검사와 LLM 검사 모두 이 파일 참조
- 주의: 규칙 추가/삭제 시 convention 노드 동작에 즉시 반영됨

## frontend/ — 웹 대시보드

- 비즈니스 역할: 분석 결과를 실시간 시각화하고 PR 액션(승인/머지)을 원클릭으로 처리
- SSE 의존: EventSource로 노드 상태를 실시간 수신. 백엔드 SSE 엔드포인트 변경 시 프론트 깨짐
- 채팅: RAG 도메인 문서를 검색하여 근거 있는 답변 제공. RAG 미연결 시 코드 기반 추론
