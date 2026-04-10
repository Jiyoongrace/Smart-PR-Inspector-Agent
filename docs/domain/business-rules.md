# 비즈니스 규칙

> "왜 이렇게 구현했는가"에 대한 배경입니다. 코드 리뷰 시 이 규칙을 위반하는 변경은 주의가 필요합니다.

## 파이프라인 규칙

### BR-001: 노드 실패가 전체를 중단시키면 안 됨
- 배경: 초기 버전에서 ChromaDB 다운 시 전체 분석이 실패했음
- 규칙: fetch를 제외한 모든 노드는 실패 시 SKIPPED 처리하고 다음 노드로 진행
- 코드 영향: 모든 노드에 try/except + NodeStatus.SKIPPED 패턴 필수

### BR-002: 테스트 실패해도 나머지 분석은 수행
- 배경: 테스트가 실패해도 컨벤션/영향도/문서 동기화 정보는 가치가 있음
- 규칙: test_run → impact 엣지는 success/fail 모두 연결
- 코드 영향: orchestrator.py의 should_retry 조건부 분기에서 "fail" → impact로 연결

### BR-003: LLM 호출 비용 제어
- 배경: 무분별한 LLM 호출로 월 API 비용이 급증한 적 있음
- 규칙: diff 크기에 따라 LLM 호출 여부/범위를 제한
  - 컨벤션 LLM: 8KB 이하만
  - 도메인 설명: diff 앞 2,000자만
  - 비즈니스 임팩트: diff 앞 4,000자만
- 코드 영향: 각 노드에서 diff 슬라이싱 로직 변경 시 비용 영향

## 인증/보안 규칙

### BR-004: Webhook 서명 검증은 생략 불가
- 배경: 서명 미검증 시 외부에서 가짜 PR 이벤트를 보낼 수 있음
- 규칙: GITHUB_WEBHOOK_SECRET이 설정되어 있으면 반드시 HMAC-SHA256 검증
- 코드 영향: api/webhook.py의 _verify_github_signature 함수

### BR-005: GitHub App 인증을 PAT보다 우선
- 배경: PAT으로는 자기 PR 승인 불가 (GitHub 정책). Bot 계정이 필요
- 규칙: GITHUB_APP_ID가 설정되어 있으면 App 인증 사용, 없으면 PAT 폴백
- 코드 영향: config/github_app.py의 get_github_client()

## 데이터 규칙

### BR-006: 분석 결과는 반드시 영속화
- 배경: 이력 조회, 트렌드 분석, 감사 대응에 필요
- 규칙: 분석 완료 시 SQLite DB에 저장 + Redis 캐시 (24시간)
- 코드 영향: orchestrator.py의 run_pr_analysis_stream에서 save_analysis 호출

### BR-007: 중복 분석 방지
- 배경: PR synchronize 이벤트가 짧은 시간에 여러 번 발생할 수 있음
- 규칙: analyzing:{repo}:{pr} 키로 10분간 중복 차단
- 코드 영향: webhook.py에서 Redis 캐시 확인 로직

## 프론트엔드 규칙

### BR-008: SSE 연결은 반드시 정리
- 배경: EventSource 미해제 시 브라우저 메모리 누수 + 백엔드 커넥션 누적
- 규칙: complete/error 이벤트 수신 시 EventSource.close() 호출
- 코드 영향: Header.tsx의 connectAnalysisStream 콜백

### BR-009: 채팅 RAG 실패는 조용히 처리
- 배경: RAG 검색 실패로 채팅 자체가 안 되면 안 됨
- 규칙: RAG 검색 5초 타임아웃, 실패 시 도메인 문서 없이 LLM만으로 응답
- 코드 영향: frontend/src/app/api/chat/route.ts의 searchRAG 함수
