# 시스템 아키텍처

## 패턴: Planner + ReAct Hybrid

Smart PR Inspector는 **LangGraph 기반 StateGraph**를 활용한 Planner-ReAct 하이브리드 패턴으로 구현됩니다.

```
┌─────────────────────────────────────────────────────────────┐
│                     GitHub Webhook Trigger                   │
│                    (PR Created/Synchronized)                 │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  Orchestrator (LangGraph)                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  State: {pr_data, diff, convention_result,          │   │
│  │          test_result, doc_updates, slack_thread}    │   │
│  └─────────────────────────────────────────────────────┘   │
└───────────────────────┬─────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
        ▼                               ▼
┌──────────────────┐          ┌──────────────────┐
│  Parallel Fork   │          │  Parallel Fork   │
│  Convention Check│          │  Test Generator  │
│  (AST + LLM)     │          │  (LLM + Jinja2)  │
└────────┬─────────┘          └────────┬─────────┘
         │                              │
         └──────────┬───────────────────┘
                    │
                    ▼
        ┌─────────────────────┐
        │   Conditional Node  │
        │  Test Runner (Pytest)│
        │  Timeout: 5min      │
        │  Retry: Max 3       │
        └──────────┬──────────┘
                   │
         ┌─────────┴─────────┐
         │ Success?          │
         ├─────────┬─────────┤
         │ Yes     │ No      │
         ▼         ▼         │
    ┌─────┐   ┌─────────┐   │
    │Pass │   │Fix Code │◄──┘
    └──┬──┘   │w/ LLM   │ (최대 3회)
       │      └─────────┘
       │
       ▼
┌──────────────────────────────┐
│  RAG-based Impact Analysis   │
│  (도메인 문서 검색 + 요약)    │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│  Documentation Sync Check    │
│  (Swagger/README diff 감지)  │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│  GitHub Comment Generator    │
│  + Slack Notification        │
└──────────────────────────────┘
```

---

## LangGraph StateGraph 구조

```python
from langgraph.graph import StateGraph, END

workflow = StateGraph(AgentState)

# 노드 등록
workflow.add_node("fetch", fetch_pr_data_node)
workflow.add_node("convention", convention_check_node)
workflow.add_node("test_gen", test_generator_node)
workflow.add_node("test_run", test_runner_node)
workflow.add_node("fix_test", fix_test_code_node)
workflow.add_node("impact", impact_analysis_node)
workflow.add_node("domain_explain", domain_explainer_node)  # RAG
workflow.add_node("doc_sync", doc_sync_check_node)
workflow.add_node("comment", generate_comment_node)
workflow.add_node("slack", slack_notify_node)

# 엣지 연결
workflow.set_entry_point("fetch")
workflow.add_edge("fetch", "convention")
workflow.add_edge("fetch", "test_gen")  # Parallel

workflow.add_conditional_edges(
    "test_run",
    should_retry,
    {"retry": "fix_test", "success": "impact", "fail": "comment"}
)

workflow.add_edge("impact", "domain_explain")
workflow.add_edge("domain_explain", "doc_sync")
workflow.add_edge("doc_sync", "comment")
workflow.add_edge("comment", "slack")
workflow.add_edge("slack", END)
```

---

## 디렉토리 구조

```
smart-pr-inspector/
├── agents/
│   ├── orchestrator.py      # LangGraph 워크플로우 메인
│   ├── state.py             # Pydantic AgentState 모델
│   └── nodes/
│       ├── fetcher.py       # GitHub PR 데이터 수집
│       ├── convention.py    # AST + LLM 컨벤션 체크
│       ├── test_gen.py      # LLM 기반 테스트 생성
│       ├── test_runner.py   # Docker 격리 실행
│       ├── impact.py        # 정적 분석 영향도
│       ├── domain_explainer.py  # RAG 도메인 설명
│       ├── doc_sync.py      # Swagger/README 동기화
│       ├── commenter.py     # GitHub 코멘트 생성
│       └── slack_notify.py  # Slack 알림
├── tools/
│   ├── github_tool.py       # PyGithub 래퍼
│   ├── ast_tool.py          # AST 분석 유틸
│   └── docker_tool.py       # Docker 실행 유틸
├── memory/
│   ├── vector_store.py      # ChromaDB 연동
│   └── cache.py             # Redis 캐싱
├── api/
│   └── webhook.py           # FastAPI Webhook 서버
├── config/
│   ├── conventions.yaml     # 컨벤션 룰북
│   └── prompts.py           # LLM 프롬프트 관리
├── frontend/                # Next.js UI
│   └── src/
│       ├── components/
│       │   ├── layout/      # Header, Sidebar, ChatPanel
│       │   └── workspace/   # PR 분석 워크스페이스
│       └── app/             # Next.js App Router
├── tests/
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## 데이터 흐름

```
GitHub PR Event
    → Webhook (FastAPI)
    → AgentState 초기화
    → Orchestrator (LangGraph)
        → [Parallel] Convention Check + Test Generation
        → Test Runner (with retry)
        → Impact Analysis (AST)
        → Domain Explanation (RAG + ChromaDB)
        → Doc Sync Check
        → GitHub Comment 생성
        → Slack 알림
    → UI 실시간 업데이트 (WebSocket/SSE)
```
