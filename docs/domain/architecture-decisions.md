# 아키텍처 결정 기록 (ADR)

> 주요 기술 결정과 그 배경입니다. 이 결정을 뒤집는 PR은 특별히 주의해서 리뷰해야 합니다.

## ADR-001: LangGraph StateGraph 기반 파이프라인
- 결정: Agent 노드를 LangGraph StateGraph로 오케스트레이션
- 배경: 노드 간 상태 공유 + 조건부 분기(테스트 재시도)가 필요
- 대안 검토: 단순 함수 체이닝 → 재시도 로직/상태 추적 구현이 복잡해짐
- 영향: orchestrator.py에서만 엣지를 수정해야 함. 노드 내부에서 다른 노드 직접 호출 금지

## ADR-002: pytest 실행 → AI 시나리오 검증 전환
- 결정: Docker에서 pytest 실행 대신 Claude가 시나리오를 평가
- 배경: Docker 의존성 문제, 외부 라이브러리 mock 불일치, 생성 테스트 80% 환경 문제로 실패
- 원래 설계: 코드 생성 → Docker 격리 실행 → 실패 시 LLM으로 코드 수정 (최대 3회 재시도)
- 현재: Given/When/Then 시나리오 생성 → diff 대비 AI 평가 (pass/fail/unclear)
- 영향: test_gen은 시나리오 생성, test_runner는 시나리오 평가로 역할 변경됨

## ADR-003: 컨벤션 검사 하이브리드 (AST + LLM)
- 결정: AST로 빠른 패턴 탐지 + LLM으로 복잡한 패턴 보완
- 배경: AST만으로는 "가독성", "로직 중복" 판단 불가. LLM만으로는 느리고 비쌈
- 제약: diff 8KB 초과 시 LLM 호출 생략 (비용 제어)
- 영향: convention.py에서 AST 검사는 항상 실행, LLM은 조건부

## ADR-004: SSE로 실시간 진행 상황 전달
- 결정: Server-Sent Events로 노드별 상태 스트리밍
- 배경: 분석 30~60초 소요. 사용자에게 "지금 뭐 하고 있는지" 보여줘야 함
- 대안: WebSocket (양방향 불필요), 폴링 (불필요한 요청 증가)
- 영향: SSE 이벤트 포맷(start/node_complete/complete/error) 변경 시 프론트엔드 깨짐

## ADR-005: GitHub App 인증 추가
- 결정: PAT 외에 GitHub App 인증 방식 지원
- 배경: PAT으로는 자기 PR 승인 불가 (GitHub 정책). CI/CD에서 자동 승인이 필요
- 영향: config/github_app.py에서 App ID/Private Key/Installation ID 우선 사용

## ADR-006: RAG로 도메인 컨텍스트 주입
- 결정: docs/domain/ 마크다운을 ChromaDB에 인덱싱, 분석/채팅 시 벡터 검색
- 배경: 코드 diff만으로 "이 변경이 비즈니스에 어떤 영향인지" 설명 불가
- 핵심 가치: 다른 프로젝트에 Agent를 붙일 때 docs/domain/만 교체하면 해당 도메인 맞춤 리뷰 가능
- 영향: domain_explainer 노드 + 채팅 API에서 RAG 검색. ChromaDB 미연결 시 graceful skip

## ADR-007: 병렬 처리 구조 (기획 vs 현실)
- 원래 기획: convention과 test_gen을 병렬(Fork) 실행하여 LLM 대기시간 절반 단축
- 현실: LangGraph에서 동일 state key 동시 업데이트 시 오류 발생
- 결정: 순차 실행으로 변경. 안정성 우선
- 향후: LangGraph 병렬 노드 지원 개선 시 재검토 가능
