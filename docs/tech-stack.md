# 기술 스택

## Core Framework

| 분류 | 기술 | 버전 | 역할 |
|------|------|------|------|
| Orchestration | **LangGraph** | 0.2.x | State 기반 Agent 워크플로우 (Conditional Edges) |
| LLM Chaining | **LangChain** | 0.3.x | LLM 체이닝, RAG 파이프라인 |
| Primary LLM | **Anthropic Claude** | claude-sonnet-4-6 | 코드 분석 및 생성 (긴 컨텍스트 처리) |
| Fallback LLM | **OpenAI GPT-4** | gpt-4-turbo | 대안 LLM |
| Vector DB (Dense) | **ChromaDB** | 0.5.x | 도메인 문서 Dense 벡터 검색 (로컬, 무료) |
| Sparse Search | **rank-bm25** | 0.2.x | BM25 Sparse 키워드 검색 (Hybrid RAG) |
| Re-ranking | **sentence-transformers** | 3.3.x | Cross-Encoder 기반 Re-ranking (ms-marco-MiniLM) |
| Cache | **Redis** | 7.x | 세션 상태 캐싱 |
| Validation | **Pydantic** | 2.x | Agent State 스키마 정의 |

## Tools & Integrations

| 분류 | 기술 | 역할 |
|------|------|------|
| GitHub | **PyGithub** | PR/Issue/Comment API |
| GitHub | **GitHub Actions** | Webhook 트리거 |
| Code Analysis | **ast** (내장) | Python AST 파싱 |
| Code Analysis | **pylint** | 린트 규칙 검증 |
| Code Analysis | **radon** | 순환 복잡도 분석 |
| Code Analysis | **bandit** | 보안 취약점 스캔 |
| Diff Parsing | **unidiff** | Git Diff 파싱 |
| Testing | **pytest** | 테스트 실행 |
| Testing | **pytest-timeout** | 타임아웃 관리 |
| Isolation | **Docker Python SDK** | 격리 실행 환경 |
| Documentation | **prance** | Swagger 검증 |
| Template | **Jinja2** | 문서 템플릿 생성 |
| Slack | **Slack SDK** | 메시지 전송 및 Interactive Buttons |
| Slack | **Slack Bolt** | 이벤트 핸들링 |
| Monitoring | **Prometheus** | 메트릭 수집 |
| Error Tracking | **Sentry** | 에러 추적 |

## Frontend

| 기술 | 역할 |
|------|------|
| **Next.js 14** (App Router) | React 프레임워크 |
| **TypeScript** | 타입 안전성 |
| **Tailwind CSS** | 유틸리티 CSS |
| **shadcn/ui** | UI 컴포넌트 라이브러리 |
| **Zustand** | 클라이언트 상태 관리 |
| **TanStack Query** | 서버 상태 관리 / 데이터 패칭 |
| **Framer Motion** | 애니메이션 |
| **Recharts** | 데이터 시각화 |
| **Monaco Editor** | 코드 에디터 (diff 뷰) |
| **SSE (EventSource)** | 실시간 Agent 상태 스트리밍 |

## Infrastructure

| 분류 | 기술 | 역할 |
|------|------|------|
| API Server | **FastAPI** | Webhook 수신 서버 |
| Local Dev | **Docker Compose** | 로컬 개발 환경 |
| Deployment | **Railway / Render** | 프로덕션 배포 (무료 티어) |
| Database | **PostgreSQL** (Supabase Free) | 리뷰 이력 저장 |
| Cache | **Redis Cloud** (무료 30MB) | 캐싱 |
| CI/CD | **GitHub Actions** | 자동 배포 |

## 무료 외부 API/서비스

| 서비스 | 용도 | 무료 한도 |
|--------|------|-----------|
| **GitHub API** | PR/Issue/Comment | 5,000 req/hour |
| **Anthropic Claude API** | LLM 추론 | 유료 (저렴) |
| **ChromaDB** | 벡터 DB | 무제한 (로컬) |
| **Supabase** | PostgreSQL | 500MB 무료 |
| **Redis Cloud** | 캐시 | 30MB 무료 |
| **Railway** | 배포 | $5 크레딧/월 |
| **Slack API** | 알림/Interactive | 무료 |
| **Sentry** | 에러 추적 | 5K 이벤트/월 무료 |
