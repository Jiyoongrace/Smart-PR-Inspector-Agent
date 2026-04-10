# 🤖 Smart PR Inspector Agent

> GitHub Pull Request를 자동으로 분석하는 AI Agent 플랫폼

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2.x-orange)](https://langchain-ai.github.io/langgraph/)
[![Claude](https://img.shields.io/badge/Claude-Anthropic-purple)](https://anthropic.com)

## 개요

PR이 열릴 때마다 자동으로 트리거되어 코드 품질을 검증하는 지능형 에이전트입니다.

```
시니어 리뷰 시간 78% 절감 | 컨벤션 위반 자동 탐지 | 테스트 자동 생성/실행
```

## 주요 기능

| 기능 | 설명 |
|------|------|
| **컨벤션 검증** | AST + Claude LLM 하이브리드 분석 |
| **테스트 자동 생성** | AI로 pytest 코드 생성 후 Docker에서 실행 |
| **영향도 분석** | 정적 분석으로 변경 함수의 의존성 추적 |
| **도메인 설명** | RAG 기반 비즈니스 영향도 자동 설명 |
| **문서 동기화** | Swagger/README 업데이트 자동 감지 |
| **Slack 연동** | 인터랙티브 버튼으로 PR 승인/거부 |
| **실시간 UI** | SSE 스트리밍으로 Agent 진행 상황 실시간 표시 |

## 기술 스택

**Backend**: Python 3.11, FastAPI, LangGraph, LangChain, Anthropic Claude  
**Vector DB**: ChromaDB (로컬), Pinecone (클라우드)  
**Cache**: Redis  
**Frontend**: Next.js 14, TypeScript, Tailwind CSS, Framer Motion  
**Infra**: Docker Compose, GitHub Actions

## 기술 스택 Detail
### Core Framework

| 분류 | 기술 | 버전 | 역할 |
|------|------|------|------|
| Orchestration | **LangGraph** | 0.2.x | State 기반 Agent 워크플로우 (Conditional Edges) |
| LLM Chaining | **LangChain** | 0.3.x | LLM 체이닝, RAG 파이프라인 |
| Primary LLM | **Anthropic Claude** | claude-sonnet-4-6 | 코드 분석 및 생성 (긴 컨텍스트 처리) |
| Fallback LLM | **OpenAI GPT-4** | gpt-4-turbo | 대안 LLM |
| Vector DB | **ChromaDB** | 최신 | 도메인 문서 벡터 저장 (로컬, 무료) |
| Vector DB (Cloud) | **Pinecone** | Free Tier | 프로덕션 벡터 저장 (옵션) |
| Cache | **Redis** | 7.x | 세션 상태 캐싱 |
| Validation | **Pydantic** | 2.x | Agent State 스키마 정의 |

### Tools & Integrations

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

### Frontend

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

### Infrastructure

| 분류 | 기술 | 역할 |
|------|------|------|
| API Server | **FastAPI** | Webhook 수신 서버 |
| Local Dev | **Docker Compose** | 로컬 개발 환경 |
| Deployment | **Railway / Render** | 프로덕션 배포 (무료 티어) |
| Database | **PostgreSQL** (Supabase Free) | 리뷰 이력 저장 |
| Cache | **Redis Cloud** (무료 30MB) | 캐싱 |
| CI/CD | **GitHub Actions** | 자동 배포 |

### 무료 외부 API/서비스

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

## 빠른 시작

### 1. 의존성 설치

```bash
# Python 환경
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 프론트엔드
cd frontend && npm install
```

### 2. 환경변수 설정

```bash
cp .env.example .env
# .env 파일에서 필수 값 입력:
# - ANTHROPIC_API_KEY
# - GITHUB_TOKEN
```

### 3. 실행

```bash
# Docker Compose (전체 스택)
docker-compose up -d

# 또는 개발 모드 (개별 실행)
uvicorn api.webhook:app --reload --port 8000  # 백엔드
cd frontend && npm run dev                     # 프론트엔드
```

### 4. GitHub Webhook 설정

```bash
# ngrok으로 로컬 서버 외부 노출
ngrok http 8000

# GitHub 레포 → Settings → Webhooks → Add webhook
# Payload URL: https://xxx.ngrok.io/webhook/github
# Events: Pull requests
```

## 프로젝트 구조

```
smart-pr-inspector/
├── agents/              # LangGraph Agent 워크플로우
│   ├── orchestrator.py  # 메인 StateGraph
│   ├── state.py         # Pydantic 상태 모델
│   └── nodes/           # 각 분석 노드
├── api/                 # FastAPI Webhook 서버
├── memory/              # ChromaDB 벡터 스토어 + Redis 캐시
├── config/              # 컨벤션 룰북 + 프롬프트
├── frontend/            # Next.js UI
│   └── src/
│       ├── app/         # App Router
│       ├── components/  # UI 컴포넌트
│       └── store/       # Zustand 상태 관리
├── docs/                # 프로젝트 문서
└── tests/               # 테스트 코드
```

## Agent 워크플로우

```
GitHub PR 이벤트
    → fetch (PR 데이터 수집)
    → [병렬] convention (컨벤션 검증) + test_gen (테스트 생성)
    → test_run (Docker 실행) ← fix_test (실패 시 최대 3회 재시도)
    → impact (영향도 분석)
    → domain_explain (RAG 도메인 설명)
    → doc_sync (문서 동기화 체크)
    → comment (GitHub PR 코멘트 게시)
    → slack (Slack 알림)
```

## 도메인 문서 인덱싱

```python
from agents.nodes.domain_explainer import DomainDocIngester

# Markdown 파일 일괄 인덱싱
ingester = DomainDocIngester()
ingester.ingest_markdown_dir("./docs/domain")
```

## 라이선스

MIT License

## 기여

PR과 Issue 환영합니다! [기여 가이드](docs/implementation-guide.md)를 참고하세요.
