# CHANGES.md — 버전 이력

## v1.1.0 — 2026-04-09

### 채팅 시스템 개선
- 채팅 API를 OpenAI (gpt-5.4) → Anthropic Claude (claude-sonnet-4-20250514)로 전환
- 스트리밍 응답 방식을 Anthropic SDK의 `messages.stream()` 기반으로 변경

### 테스트 탭 UX 개선
- "검증 결과를 불러오는 중입니다..." 영구 로딩 버그 수정
- 시나리오 미존재 시 통계 기반 결과 표시 (통과/실패 건수)
- 코드 기반 테스트 결과의 stdout/stderr 로그 표시 추가

### 워크플로우 인터랙션 추가
- Agent 워크플로우 노드 클릭 시 해당 분석 탭으로 자동 이동
- 완료/실패 상태의 노드만 클릭 가능 (hover 효과 포함)
- 노드-탭 매핑: convention→컨벤션, test→테스트, impact→영향도, doc_sync→문서

### 비즈니스 영향도 분석 (신규)
- `impact` 노드에 LLM 기반 비즈니스 관점 영향도 분석 추가
- 시니어 엔지니어 관점의 배포 전 체크리스트 자동 생성
- 사용자 체감 변화, 비즈니스 리스크, 영향 기능 목록 도출
- `BusinessImpact` Pydantic 모델 및 프론트엔드 타입 추가
- `BUSINESS_IMPACT_PROMPT` 프롬프트 템플릿 추가
- LLM 호출 실패 시 graceful skip (코드 분석 결과 유지)

### 문서 업데이트
- `docs/features.md` — 코드 영향도 분석에 비즈니스 임팩트 섹션 추가
- `docs/agent-workflow.md` — impact 노드 설명에 비즈니스 분석 단계 추가

---

## v1.0.0 — 2026-04-08

### 초기 릴리즈

#### 백엔드 (Python)

**Agent 아키텍처**
- LangGraph StateGraph 기반 오케스트레이터 구현 (`agents/orchestrator.py`)
- Pydantic v2 AgentState 모델 정의 (`agents/state.py`)
- 노드별 NodeStatus (pending/running/success/failed/skipped) 추적

**Agent 노드 구현**
- `fetch` — GitHub PR 데이터 수집 (PyGithub + unidiff diff 파싱)
- `convention` — AST + Claude LLM 하이브리드 컨벤션 검증
  - snake_case, PascalCase 네이밍 검사
  - 타입 힌트 누락 검사
  - 매직 넘버 감지
  - bare except 검사
  - 함수 길이 초과 검사
  - LLM 보조 복잡 패턴 분석
- `test_gen` — Claude AI 기반 pytest 테스트 자동 생성
- `test_run` — Docker 격리 환경 또는 로컬 pytest 실행 (5분 타임아웃, 최대 3회 재시도)
- `fix_test` — 테스트 실패 시 LLM으로 코드 자동 수정
- `impact` — AST 정적 분석으로 의존성 추적 및 리스크 레벨 판정
- `domain_explain` — ChromaDB RAG 기반 비즈니스 영향도 설명
- `doc_sync` — FastAPI 엔드포인트 변경 감지 및 Swagger 업데이트 제안
- `comment` — GitHub PR 코멘트 자동 게시 (구조화된 Markdown 리포트)
- `slack` — Slack Block Kit 인터랙티브 메시지 (승인/수정 요청 버튼)

**API 서버**
- FastAPI Webhook 서버 (`api/webhook.py`)
- GitHub Webhook 서명 검증
- SSE 스트리밍 엔드포인트 (`/api/analyze/stream`)
- REST API: 분석 트리거, 결과 조회, 상태 조회
- Slack Interactive Events 처리
- Prometheus 메트릭 (`/metrics`)

**인프라**
- Redis 캐시 (인메모리 폴백 포함)
- ChromaDB 벡터 스토어
- Docker Compose 전체 스택

#### 프론트엔드 (Next.js 14)

**레이아웃**
- 4패널 레이아웃: 좌측 사이드바 + 상단 헤더 + 중앙 워크스페이스 + 우측 채팅
- 다크 모드 전용 디자인 (Agent 플랫폼 테마)
- Framer Motion 애니메이션

**컴포넌트**
- `Sidebar` — PR 목록, 검색, 네비게이션
- `Header` — PR 분석 입력 폼, 실시간 상태 표시
- `AgentWorkflow` — 노드별 실행 상태 실시간 시각화
- `AnalysisResults` — 탭별 분석 결과 (개요/컨벤션/테스트/영향도/문서)
- `ChatPanel` — Claude AI 기반 스트리밍 채팅

**상태 관리**
- Zustand + Immer 전역 상태
- TanStack Query 서버 상태
- SSE 실시간 업데이트

**채팅 API**
- `/api/chat` — Claude claude-haiku-4-5-20251001 기반 스트리밍 채팅
- PR 컨텍스트 포함 대화

#### 문서화
- `docs/overview.md` — 프로젝트 개요 및 핵심 가치
- `docs/architecture.md` — 시스템 아키텍처 및 워크플로우
- `docs/features.md` — 주요 기능 명세
- `docs/tech-stack.md` — 기술 스택 상세
- `docs/pain-analysis.md` — Pain Point → Task → Skill → Tool 분해
- `docs/implementation-guide.md` — Phase별 구현 가이드
- `docs/deployment.md` — 배포 및 운영 가이드
- `README.md` — 프로젝트 소개 및 빠른 시작
- `CLAUDE.md` — Claude Code 작업 지침
- `CHANGES.md` — 버전 이력 (현재 파일)

#### 설정 파일
- `config/conventions.yaml` — 팀 컨벤션 룰북 (네이밍/타입힌트/에러처리/보안)
- `config/prompts.py` — LLM 프롬프트 중앙 관리
- `.env.example` — 환경변수 템플릿
- `requirements.txt` — Python 의존성
- `docker-compose.yml` — 전체 인프라 스택
- `.github/workflows/deploy.yml` — CI/CD 파이프라인

---

## 예정 기능 (v1.1.0)

- [ ] 복잡도 분석 (radon) + 보안 스캔 (bandit) 노드 추가
- [ ] 개발자 과거 리뷰 패턴 학습 (PostgreSQL + 메모리 노드)
- [ ] PR 이력 대시보드 UI
- [ ] GitHub App 지원 (Personal Access Token → GitHub App)
- [ ] Multi-language 지원 (JavaScript, TypeScript, Java)
- [ ] Notion/Confluence 문서 자동 크롤링 및 RAG 인덱싱
- [ ] PR 자동 라벨링 기능
- [ ] 커스텀 컨벤션 룰 UI 편집기
