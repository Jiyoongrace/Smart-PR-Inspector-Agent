# CLAUDE.md — Smart PR Inspector Agent

Claude Code가 이 프로젝트에서 작업할 때 참고하는 지침입니다.

## 프로젝트 개요

- **목적**: GitHub Pull Request 자동 분석 AI 에이전트 플랫폼
- **핵심 기술**: LangGraph 0.2 + Anthropic Claude + FastAPI + Next.js 14
- **주요 언어**: Python 3.11 (백엔드), TypeScript (프론트엔드)
- **핵심 차별점**: Hybrid RAG (Dense + Sparse + Re-ranking) + HITL + AI 시나리오 검증 + 4가지 Trigger 통합

## 워크플로우 구조 (반드시 숙지)

LangGraph StateGraph 기반 **11개 노드**로 구성:

```
fetch → convention → test_gen → arch_review (분기)
                                     ├─ HITL 승인 대기 → test_run
                                     └─ rejected → comment
test_run (분기) ─ fail → fix_test → test_run (최대 3회 재시도)
              └─ success → impact → domain_explain → doc_sync → comment → slack → END
```

- 모든 노드는 `agents/nodes/` 에 있고, 그래프 조립은 `agents/orchestrator.py`
- 상태 모델은 `agents/state.py`의 `AgentState` (Pydantic v2)

## 코드 규칙

### Python
- 모든 함수에 타입 힌트 필수
- 한국어 docstring 작성
- `logging` 모듈 사용 (print 금지)
- Pydantic v2 BaseModel로 데이터 검증
- 예외 처리: 구체적인 Exception 클래스 지정
- LLM 호출은 항상 `try/except`로 감싸고 fallback 처리

### TypeScript / React
- `"use client"` 지시어는 필요한 컴포넌트에만 표시
- Props 타입은 별도 interface로 정의
- Zustand store 접근은 `useAppStore()` 훅 사용
- Tailwind CSS + `cn()` 유틸리티로 스타일링
- UI 컴포넌트는 Radix UI 헤드리스 기반 (shadcn/ui 사용 안 함)

### 파일 구조 규칙
- Agent 노드는 반드시 `agents/nodes/` 에 추가
- 새 노드 추가 시 `agents/nodes/__init__.py`에 export 추가
- LangGraph 엣지는 `agents/orchestrator.py`에서만 수정
- 프롬프트 문자열은 `config/prompts.py`에 중앙화
- LLM 호출 헬퍼는 `config/llm.py` 사용
- 새 스킬 추가 시 `SKILL.md`에 마크다운으로 선언

## 환경변수

### 필수
- `ANTHROPIC_API_KEY` — Claude API 키 (`sk-ant-...`)
- `GITHUB_TOKEN` — GitHub PAT (`repo`, `pull_requests:write` 권한)

### Slack 인터랙티브 사용 시
- `SLACK_BOT_TOKEN` — **Bot Token 필수** (Webhook URL은 인터랙션 처리 불가)
- `SLACK_SIGNING_SECRET` — 슬랙 요청 서명 검증
- `SLACK_CHANNEL` — 기본 `#pull-requests`

### 선택
- `OPENAI_API_KEY` — Secondary LLM 사용 시
- `REDIS_URL` — 기본 `redis://localhost:6379`
- `CHROMA_HOST`, `CHROMA_PORT` — 기본 `localhost:8001`
- `DATABASE_URL` — 기본 SQLite, PostgreSQL 사용 시 지정

## 핵심 설계 결정 (수정 시 주의)

### 1. test_run은 Docker 실행이 아니라 AI 시나리오 평가
`agents/nodes/test_runner.py`는 **실제 코드를 실행하지 않습니다.** LLM이 BDD 시나리오와 PR diff를 함께 보고 `pass / fail / unclear`를 판단합니다. 환경 의존성과 보안 리스크를 회피하기 위한 의도적 설계입니다. 이 부분을 "진짜 pytest로 바꿔야 한다"고 임의로 변경하지 마세요.

### 2. Re-ranking과 Cross-Encoder의 관계
- **Re-ranking**은 *단계(stage)*
- **Cross-Encoder**는 그 단계에서 사용하는 *모델 아키텍처*
- 둘은 동의어가 아니라 포함 관계입니다
- 정확한 표현: **"Cross-Encoder 기반 Re-ranking"** (`Cross-Encoder Re-ranking`이라고 쓰지 않기)
- 구현은 `memory/vector_store.py`의 `CrossEncoderReranker` 클래스

### 3. RAG 폴백 전략
벡터 컬렉션이 비어있을 때(`store.count() == 0`)는 검색을 스킵하고 LLM이 코드만 보고 추론합니다. PR 코멘트의 도메인 섹션에 **🔍 RAG 문서 기반 / 🤖 코드 추론** 배지를 표시해 분석 근거를 명시합니다. 이 폴백을 제거하지 마세요.

### 4. Slack 인터랙션 응답 폴백
`api/webhook.py`의 `_send_slack_response()` 헬퍼는 3단계 폴백을 사용합니다:
1. `chat_update` (봇이 원본 메시지 작성자일 때만 동작)
2. `response_url`로 in_channel 응답
3. `chat_postMessage`로 스레드에 새 메시지

이 폴백 구조 덕분에 Webhook으로 보낸 메시지든 권한 문제든 사용자에게 응답이 반드시 표시됩니다. 단순히 `chat_update`만 쓰도록 되돌리지 마세요.

### 5. 4가지 Trigger 통일성
4가지 Trigger(GitHub Webhook / 대시보드 수동 / AI 채팅 / Slack 인터랙티브)는 모두 동일한 LangGraph StateGraph + AgentState를 공유합니다. 새 진입점을 추가할 때도 이 원칙을 유지하세요. 단, **AI 채팅은 그래프를 재실행하지 않고** 기존 분석 결과를 컨텍스트로 사용합니다.

## 주요 파일 가이드

| 파일 | 역할 |
|------|------|
| `agents/orchestrator.py` | StateGraph 조립 (엣지/분기) |
| `agents/state.py` | AgentState Pydantic 모델 |
| `agents/nodes/risk_report.py` | PR Health Score 계산 + 카드 생성 |
| `api/webhook.py` | FastAPI 메인 (Webhook + SSE + Slack 핸들러) |
| `api/rag_upload.py` | 팀 문서 업로드/조회/삭제 API |
| `memory/vector_store.py` | Hybrid RAG (Dense + BM25 + Reranker) |
| `config/prompts.py` | LLM 프롬프트 중앙 관리 |
| `config/llm.py` | LLM 호출 헬퍼 (`call_llm`) |
| `config/skills.py` | SKILL.md 파서 + SkillRegistry |
| `config/conventions.yaml` | AST 검사용 컨벤션 룰 |
| `SKILL.md` | 11개 스킬 선언 |

## 개발 시 주의사항

1. **LangGraph StateGraph**: `AgentState`는 불변성 유지, 각 노드는 새 state 반환
2. **LLM 호출**: 항상 `try/except`로 감싸고 fallback 처리
3. **SSE 스트리밍**: `yield` 기반 비동기 제너레이터 사용
4. **Rate Limiting**: GitHub API는 5000 req/hour 제한 주의
5. **Slack 인터랙티브**: Bot Token 필수, Webhook URL로는 버튼 클릭 처리 불가
6. **벡터스토어**: ChromaDB와 BM25 인덱스를 *동시에* 갱신해야 Hybrid 검색이 정확해짐 (`VectorStore.add_documents()` 사용)

## 로컬 개발 실행

```bash
# 인프라만 Docker로 실행 (Redis + ChromaDB)
docker-compose up -d redis chromadb

# 백엔드 개발 모드
uvicorn api.webhook:app --reload --port 8000

# 프론트엔드 개발 모드
cd frontend && npm run dev
```

대시보드: <http://localhost:3000>
API 문서: <http://localhost:8000/docs>

## 테스트

```bash
pytest tests/ -v                                # 전체
pytest tests/test_convention.py -v              # 특정 노드
pytest tests/ --cov=agents --cov-report=html    # 커버리지
```

## 버전 관리

변경사항은 `CHANGES.md`에 기록합니다.
형식: `## v{버전} — {날짜}\n- {변경 내용}`

기능별로 커밋을 분리하고 한국어 커밋 메시지를 사용합니다.

## 보안 주의사항

- `.env` 파일을 절대 커밋하지 마세요
- API 키는 항상 환경변수로 관리
- GitHub Webhook 서명은 반드시 HMAC-SHA256으로 검증
- Slack 요청도 `SLACK_SIGNING_SECRET`으로 서명 검증
- 사용자 업로드 문서(`api/rag_upload.py`)는 확장자 화이트리스트(`.md`, `.txt`, `.yaml`, `.yml`)로 제한

## 주요 문서 위치

- `README.md` — 프로젝트 소개 + 워크플로우 도식 + 빠른 시작
- `docs/project-presentation.md` — 종합 문서 + 발표 대본
- `docs/architecture.md` — 시스템 아키텍처
- `docs/agent-workflow.md` — 11노드 상세
- `docs/features.md` — 기능별 설명
- `docs/tech-stack.md` — 기술 스택
- `CHANGES.md` — 버전 이력
