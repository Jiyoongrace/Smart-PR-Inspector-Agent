# 시스템 아키텍처

## 패턴: Planner + ReAct Hybrid

Smart PR Inspector는 **LangGraph 기반 StateGraph**를 활용한 Planner-ReAct 하이브리드 패턴으로 구현됩니다.

고급 아키텍처 요소:
- **병렬 처리 (Fork/Join)**: Convention + Test Gen 동시 실행
- **HITL (Human-in-the-Loop)**: 아키텍처 룰 위반 시 시니어 승인 대기
- **Hybrid RAG**: Dense + Sparse(BM25) + Cross-Encoder 기반 Re-ranking
- **조건부 재시도**: 테스트 실패 시 최대 3회 자동 수정 루프

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
│  │   test_result, arch_review, impact, domain, ...}    │   │
│  └─────────────────────────────────────────────────────┘   │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
                ┌──────────────┐
                │    FETCH     │
                │  PR 데이터   │
                └──────┬───────┘
                       │
              ┌────────┴────────┐
              │  ⚡ FORK (병렬)  │
              └──┬───────────┬──┘
                 │           │
                 ▼           ▼
        ┌──────────────┐  ┌──────────────┐
        │  Convention  │  │  Test Gen    │
        │  (AST + LLM) │  │  (LLM BDD)   │
        └──────┬───────┘  └──────┬───────┘
               │                 │
               └────────┬────────┘
                        │
               ┌────────┴────────┐
               │  ⚡ JOIN (합류)  │
               └────────┬────────┘
                        │
                        ▼
               ┌────────────────┐
               │ 🧑 ARCH REVIEW │
               │ 아키텍처 룰 점검│
               └────────┬───────┘
                        │
              ┌─────────┴──────────┐
              │                    │
        (위반 → HITL)        (통과)
              │                    │
              ▼                    ▼
     ┌──────────────┐    ┌──────────────┐
     │ 시니어 승인   │    │  Test Runner │
     │ 대기 (HITL)   │    │  (Docker)    │
     └──────┬───────┘    └──────┬───────┘
            │                   │
      ┌─────┴─────┐    ┌───────┴───────┐
    (승인)     (반려)   │   Retry?      │
      │          │     ├───┬───────────┤
      ▼          ▼     │   │ Yes       │
   Test Run   PR반려   │   ▼           │
              + END    │ Fix Code     │
                       │ w/ LLM      │ (최대 3회)
                       │   │          │
                       │   └──→test_run│
                       │              │
                       ▼              │
              ┌────────────────┐      │
              │ Impact Analysis│←─────┘
              │ (AST + LLM)    │
              └────────┬───────┘
                       │
                       ▼
              ┌────────────────┐     ┌──────────────┐
              │ Domain Explain │←───→│ ChromaDB     │
              │ (Hybrid RAG)  │     │ Dense+BM25   │
              │ + Re-ranking  │     │ + Re-ranking │
              └────────┬───────┘     └──────────────┘
                       │
                       ▼
              ┌────────────────┐
              │ Doc Sync Check │
              └────────┬───────┘
                       │
                       ▼
              ┌────────────────┐
              │ GitHub Comment │
              │ + Slack Notify │
              └────────────────┘
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
workflow.add_node("arch_review", arch_review_node)       # HITL 아키텍처 점검
workflow.add_node("test_run", test_runner_node)
workflow.add_node("fix_test", fix_test_code_node)
workflow.add_node("impact", impact_analysis_node)
workflow.add_node("domain_explain", domain_explainer_node)  # Hybrid RAG
workflow.add_node("doc_sync", doc_sync_check_node)
workflow.add_node("comment", generate_comment_node)
workflow.add_node("slack", slack_notify_node)

# 엣지 연결
workflow.set_entry_point("fetch")

# 병렬 분기 (Fork): convention + test_gen 동시 실행
workflow.add_edge("fetch", "convention")
workflow.add_edge("fetch", "test_gen")

# 병렬 합류 (Join): 둘 다 완료 후 arch_review로
workflow.add_edge("convention", "arch_review")
workflow.add_edge("test_gen", "arch_review")

# HITL 분기: 아키텍처 룰 위반 여부에 따라
workflow.add_conditional_edges(
    "arch_review",
    check_arch_approval,
    {"approved": "test_run", "rejected": "comment"}
)

# 테스트 재시도 분기
workflow.add_conditional_edges(
    "test_run",
    should_retry,
    {"retry": "fix_test", "success": "impact", "fail": "impact"}
)
workflow.add_edge("fix_test", "test_run")

# 후속 분석 체인
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
│   ├── orchestrator.py      # LangGraph 워크플로우 (병렬 + HITL + 재시도)
│   ├── state.py             # Pydantic AgentState 모델 (ArchReviewResult 포함)
│   └── nodes/
│       ├── fetcher.py       # GitHub PR 데이터 수집
│       ├── convention.py    # AST + LLM 컨벤션 체크
│       ├── test_gen.py      # LLM 기반 BDD 시나리오 생성
│       ├── test_runner.py   # Docker 격리 실행 + 재시도
│       ├── arch_review.py   # 아키텍처 룰 점검 + HITL 승인
│       ├── impact.py        # 정적 분석 영향도 + 비즈니스 LLM
│       ├── domain_explainer.py  # Hybrid RAG 도메인 설명
│       ├── risk_report.py   # PR Health Score 계산 + 리포트 카드
│       ├── doc_sync.py      # Swagger/README 동기화
│       ├── commenter.py     # GitHub 코멘트 생성 (Health Score 포함)
│       └── slack_notify.py  # Slack 알림 (Health Score + 인터랙션)
├── memory/
│   ├── vector_store.py      # Hybrid RAG (Dense + BM25 + Re-ranking)
│   └── cache.py             # Redis 캐싱
├── api/
│   ├── webhook.py           # FastAPI Webhook 서버
│   └── rag_upload.py        # 팀 문서 업로드 → RAG 인덱싱 API
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
        → [Parallel Fork] Convention Check + Test Generation (동시 실행)
        → [Join] 합류
        → Architecture Rule Check (HITL 분기)
            → 위반 시: 시니어 승인 대기 → 승인/반려
            → 통과 시: 자동 진행
        → Test Runner (with retry, 최대 3회)
        → Impact Analysis (AST + LLM 비즈니스 분석)
        → Domain Explanation (Hybrid RAG: Dense + BM25 + Re-ranking)
        → Doc Sync Check
        → GitHub Comment 생성
        → Slack 알림
    → UI 실시간 업데이트 (SSE)
```
