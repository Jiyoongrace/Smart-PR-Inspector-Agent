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
| **테스트 자동 생성** | Claude AI로 pytest 코드 생성 후 Docker에서 실행 |
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
