# Agent 워크플로우 아키텍처

> 다이어그램 이미지: [agent-workflow-diagram.png](./agent-workflow-diagram.png)

---

## 전체 흐름 개요

Smart PR Inspector Agent는 **LangGraph StateGraph** 기반의 **병렬 처리 + HITL + 조건부 분기** 패턴으로 동작합니다.  
GitHub PR이 생성되거나 업데이트되면 자동으로 트리거되어, 11개 노드를 실행합니다.

```
GitHub PR 이벤트
  → FastAPI Webhook (:8000)
    → [LangGraph StateGraph]
        fetch → FORK (병렬)
                 ├── convention (AST + LLM)  [Branch A]
                 └── test_gen (BDD 시나리오) [Branch B]
               → JOIN (합류)
               → arch_review (아키텍처 룰 점검)
                   ├── 위반 → HITL (시니어 승인 대기)
                   │           ├── 승인 → test_run
                   │           └── 반려 → comment (PR 반려) → END
                   └── 통과 → test_run
               → test_run
                   ├── retry → fix_test ─┐ (최대 3회, 빨강 파선)
                   └────────────────────←┘
                   ↓ (success / fail 모두)
               → impact → domain_explain (Hybrid RAG) → doc_sync
               → comment → slack → END
```

---

## 실행 계층 구조

### 1. 트리거 레이어

| 구성 요소 | 설명 |
|-----------|------|
| **GitHub Webhook** | PR `created` / `synchronized` 이벤트 수신 |
| **FastAPI Webhook Server** | `:8000`에서 Webhook 검증 후 LangGraph 실행 |

Webhook 서명(HMAC-SHA256)을 검증한 뒤 `AgentState`를 초기화하고 워크플로우를 시작합니다.

---

### 2. AgentState — 공유 상태 객체

모든 노드는 하나의 `AgentState`를 읽고 **새로운 state를 반환**합니다 (불변성 유지).

```python
class AgentState(BaseModel):
    pr_data: PRData               # PR 번호, 레포, 작성자, 제목
    convention_result: ConventionResult  # 컨벤션 위반 목록
    test_result: TestResult       # AI 시나리오 검증 결과
    arch_review: ArchReviewResult # 아키텍처 룰 점검 + HITL 승인 상태
    impact_analysis: ImpactAnalysis  # 영향도 + 비즈니스 분석
    domain_explanation: str       # Hybrid RAG 비즈니스 영향도 요약
    domain_sources: List[str]     # RAG 참조 문서 목록
    doc_updates: str              # Swagger/README 변경 초안
    final_comment: str            # GitHub PR 코멘트 마크다운
    slack_thread_id: str          # Slack 메시지 ID
    node_status: NodeExecutionStatus  # 각 노드 실행 상태 (arch_review 포함)
    started_at: str
    completed_at: str
```

---

## 노드별 상세 설명

### NODE 1 — `fetch`

| 항목 | 내용 |
|------|------|
| **함수** | `fetch_pr_data_node` |
| **역할** | GitHub PR 데이터를 수집하여 AgentState를 초기화 |
| **입력** | `pr_number`, `repo` (owner/repo) |
| **출력** | `pr_data`, `diff`, 변경 파일 목록 |
| **도구** | PyGithub, GitHub REST API, unidiff |

GitHub API를 통해 PR의 diff, 메타데이터(제목, 작성자, 브랜치), 변경된 파일 목록을 수집합니다.  
수집된 diff는 `unidiff`로 파싱하여 추가/수정/삭제된 라인을 구조화합니다.

---

### NODE 2 — `convention`

| 항목 | 내용 |
|------|------|
| **함수** | `convention_check_node` |
| **역할** | 코드 컨벤션 위반 자동 탐지 |
| **입력** | `diff` |
| **출력** | `convention_result` (위반 목록, 라인 번호, 제안 코드) |
| **도구** | `ast`, `pylint`, `radon`, `bandit`, Anthropic Claude |

**동작 방식:**
1. 변경된 코드를 `ast.parse()`로 AST 생성
2. `config/conventions.yaml` 룰북과 패턴 매칭 (snake_case, 타입 힌트, 매직넘버 등)
3. `radon`으로 순환 복잡도(Cyclomatic Complexity) 측정
4. `bandit`으로 보안 취약점 스캔
5. 복잡한 규칙(가독성, 로직 중복)은 Claude에게 위임

> **병렬 실행:** `convention`과 `test_gen`은 LangGraph Fork/Join 패턴으로 **동시 실행**됩니다.  
> `fetch` 노드에서 두 노드로 엣지가 분기되고, 두 노드 모두 완료 후 `arch_review`로 합류합니다.

---

### NODE 3 — `test_gen`

| 항목 | 내용 |
|------|------|
| **함수** | `test_generator_node` |
| **역할** | 변경 함수에 대한 pytest 테스트 코드 자동 생성 |
| **입력** | `diff`, `pr_data` |
| **출력** | `test_result.generated_code` |
| **도구** | Anthropic Claude, Jinja2 템플릿 |

**동작 방식:**
1. diff에서 변경된 함수의 시그니처와 docstring 추출
2. Claude에게 `"이 함수를 검증하는 pytest 코드 작성"` 프롬프트 전달
3. Jinja2 템플릿으로 테스트 파일 구성
4. 임시 파일로 저장하여 다음 노드(`test_run`)에 전달

---

### NODE 4 — `arch_review` (HITL — 아키텍처 룰 점검)

| 항목 | 내용 |
|------|------|
| **함수** | `arch_review_node` |
| **역할** | 아키텍처 수준의 심각한 위반 탐지 + 시니어 승인 대기 (HITL) |
| **입력** | `diff`, `changed_files`, `convention_result` |
| **출력** | `arch_review` (위반 목록, 승인 상태) |
| **도구** | AST, regex, Slack SDK (알림) |

**점검 항목:**
- 레이어 위반: API 레이어에서 직접 DB 접근 감지
- 보안 위반: 하드코딩된 시크릿/API 키 패턴
- 구조 위반: God Class (public 메서드 10개 이상)
- 순환 참조: 모듈 간 상호 import 패턴

**HITL 분기 로직:**
```python
def check_arch_approval(state: AgentState) -> str:
    if not state.arch_review.has_violation:
        return "approved"    # → test_run으로 자동 진행
    if state.arch_review.approval_status == "rejected":
        return "rejected"    # → comment로 (PR 반려 코멘트)
    return "approved"        # 승인 or 데모 모드 자동 승인
```

| 결과 | 다음 노드 | 설명 |
|------|-----------|------|
| `approved` | `test_run` | 위반 없음 또는 시니어 승인 → 테스트 진행 |
| `rejected` | `comment` | 시니어 반려 → PR 즉시 반려 코멘트 작성 → END |

> **왜 필요한가:** AI가 모든 것을 결정하게 두지 않고, 시스템에 중요한 아키텍처 Rule  
> 의사결정(Merge Block)은 반드시 책임 있는 인간(개발자)의 통제와 승인 하에 두기 위함입니다.

---

### NODE 5 — `test_run` (조건부 분기)

| 항목 | 내용 |
|------|------|
| **함수** | `test_runner_node` |
| **역할** | Docker 격리 환경에서 생성된 테스트 실행 |
| **입력** | `test_result.generated_code` |
| **출력** | `test_result` (pass/fail, 로그, 커버리지) |
| **도구** | Docker Python SDK, pytest, pytest-timeout |
| **분기 함수** | `should_retry(state)` |

**라우팅 로직:**

```python
def should_retry(state: AgentState) -> str:
    if state.retry_count < 3 and state.test_result.has_error:
        return "retry"   # → fix_test 노드로
    elif state.test_result.passed:
        return "success" # → impact 노드로
    else:
        return "fail"    # → impact 노드로 (분석은 계속)
```

| 결과 | 다음 노드 | 설명 |
|------|-----------|------|
| `retry` | `fix_test` | 에러 로그를 LLM에 전달하여 코드 수정 |
| `success` | `impact` | 테스트 통과, 정상 분석 계속 |
| `fail` | `impact` | **테스트 실패해도 나머지 분석은 계속 수행** |

> `fail`도 `impact`로 이어진다는 점이 핵심입니다.  
> 테스트가 실패하더라도 영향도 분석, 문서 동기화, Slack 알림은 모두 실행됩니다.

---

### RETRY NODE — `fix_test`

| 항목 | 내용 |
|------|------|
| **함수** | `fix_test_code_node` |
| **역할** | 테스트 실패 로그를 LLM에 전달하여 코드 수정 후 재시도 |
| **입력** | `test_result.error_log`, `test_result.generated_code` |
| **출력** | `test_result.generated_code` (수정본), `retry_count + 1` |
| **도구** | Anthropic Claude |

`fix_test → test_run` 루프는 **최대 3회** 반복됩니다.  
3회 초과 시 `should_retry`가 `"fail"`을 반환하여 루프를 종료하고 `impact`로 진행합니다.

---

### NODE 6 — `impact`

| 항목 | 내용 |
|------|------|
| **함수** | `impact_analysis_node` |
| **역할** | 변경된 함수가 어떤 모듈/함수에서 호출되는지 정적 분석 + 비즈니스 임팩트 LLM 분석 |
| **입력** | `diff`, `pr_data` |
| **출력** | `impact` (영향 모듈 리스트, 호출 체인, API 변경 여부, **비즈니스 영향도**) |
| **도구** | `ast`, 내장 DFS/BFS, **Anthropic Claude (비즈니스 분석)** |

**동작 방식:**
1. `ast` 모듈로 전체 프로젝트를 파싱하여 호출 그래프 생성
2. 변경된 함수를 시작점으로 DFS/BFS 탐색
3. 영향받는 파일·함수 목록과 호출 체인 반환
4. `@app.post()` 등 API 데코레이터 감지 → Swagger 업데이트 필요 여부 플래그
5. **비즈니스 영향도 LLM 분석** (신규):
   - 코드 변경의 비즈니스 관점 요약 생성
   - 영향받는 사용자 기능 목록 도출
   - 장애 시 비즈니스 리스크 평가
   - 시니어 엔지니어 관점의 배포 전 체크리스트 생성
   - LLM 호출 실패 시 graceful skip (코드 분석 결과는 유지)

---

### NODE 7 — `domain_explain` (Hybrid RAG)

| 항목 | 내용 |
|------|------|
| **함수** | `domain_explainer_node` |
| **역할** | Hybrid RAG로 도메인 문서 검색 후 비즈니스 영향도 설명 |
| **입력** | `diff`, `impact` |
| **출력** | `domain_explanation` (200자 이내 비즈니스 요약), `domain_sources` |
| **도구** | ChromaDB, BM25 (rank-bm25), Cross-Encoder (sentence-transformers), LLM |

**Hybrid RAG 파이프라인:**
```
쿼리 (PR title + diff snippet)
  │
  ├── Dense Path: ChromaDB 벡터 검색 → Top-20 (의미적 유사도)
  │
  ├── Sparse Path: BM25 키워드 검색 → Top-20 (정확 매칭)
  │
  └── RRF (Reciprocal Rank Fusion) → Top-30 통합
      │
      └── Cross-Encoder 기반 Re-ranking (ms-marco-MiniLM) → Top-5 최종
          │
          └── LLM 컨텍스트로 전달 → 비즈니스 영향도 설명 생성
```

**왜 Hybrid인가:**
- Dense만: 의미 이해는 좋지만 함수명 정확 검색에 약함
- Sparse만: 키워드 매칭은 좋지만 의미적 유사도에 약함
- Hybrid: 둘을 RRF로 통합하여 보완적 효과

**폴백:** Hybrid RAG 실패 시 기존 Dense 검색으로 자동 폴백

---

### NODE 8 — `doc_sync`

| 항목 | 내용 |
|------|------|
| **함수** | `doc_sync_check_node` |
| **역할** | API 스펙 변경 감지 및 Swagger/README 업데이트 초안 생성 |
| **입력** | `diff`, `impact` |
| **출력** | `doc_updates` (변경 초안, 업데이트 필요 여부) |
| **도구** | `ast`, `prance` (Swagger 검증), Jinja2 |

**동작 방식:**
1. `ast` 파서로 FastAPI 데코레이터 + 함수 시그니처 추출
2. 기존 `swagger.yaml` / `openapi.json` 파싱 후 diff 비교
3. 추가/변경/삭제된 필드 탐지
4. Jinja2 템플릿으로 업데이트 초안 생성 → PR 코멘트에 첨부

---

### NODE 9 — `comment`

| 항목 | 내용 |
|------|------|
| **함수** | `generate_comment_node` |
| **역할** | 모든 분석 결과를 통합하여 GitHub PR 코멘트 작성 |
| **입력** | `convention_result`, `test_result`, `impact`, `domain_explanation`, `doc_updates` |
| **출력** | GitHub PR에 Markdown 코멘트 게시 |
| **도구** | PyGithub, Anthropic Claude |

컨벤션 위반 목록, 테스트 결과, 영향도 분석, 비즈니스 설명, Swagger 변경 제안을  
하나의 Markdown 리포트로 통합하여 GitHub PR에 코멘트로 게시합니다.

---

### NODE 10 — `slack`

| 항목 | 내용 |
|------|------|
| **함수** | `slack_notify_node` |
| **역할** | 분석 요약과 인터랙티브 버튼을 Slack 채널에 전송 |
| **입력** | `convention_result`, `test_result`, `doc_updates` |
| **출력** | `slack_thread` (메시지 ID) |
| **도구** | Slack SDK, Slack Bolt |

Block Kit으로 구성된 메시지에 **승인 / 수정 요청 / 상세 보기** 버튼을 포함합니다.  
Slack에서 직접 PR 리뷰 액션을 처리할 수 있습니다.

---

## 실시간 스트리밍

각 노드 완료 시 **SSE(Server-Sent Events)** 로 프론트엔드에 이벤트를 전송합니다.

```
type: "start"         → 워크플로우 시작
type: "node_complete"  → 노드 완료 (node 이름 + AgentState 포함)
type: "hitl_pending"   → HITL 승인 대기 (violations 목록 + 승인 상태)
type: "complete"      → 전체 완료 (최종 state 포함, DB 저장)
type: "error"         → 오류 발생
```

Next.js 프론트엔드는 `EventSource`로 이를 구독하여 노드 진행 상태를 실시간으로 시각화합니다.

---

## 인프라 구성

| 구성 요소 | 기술 | 용도 |
|-----------|------|------|
| API 서버 | FastAPI | Webhook 수신, SSE 스트리밍, REST API |
| LLM | Claude claude-sonnet-4-6 | 코드 분석, 테스트 생성, 도메인 설명 |
| Vector DB | ChromaDB (로컬) / Pinecone (클라우드) | RAG 도메인 문서 검색 |
| Cache | Redis 7.x | AgentState 세션 캐싱 |
| Test Isolation | Docker Python SDK | pytest 격리 실행 |
| DB | SQLite | 분석 이력 영속화 |
| 프론트엔드 | Next.js 14 + Zustand + TanStack Query | 실시간 대시보드 |

---

## 관련 파일

| 파일 | 역할 |
|------|------|
| `agents/orchestrator.py` | StateGraph 생성 및 엣지 연결 |
| `agents/state.py` | AgentState Pydantic 모델 정의 |
| `agents/nodes/fetcher.py` | fetch 노드 |
| `agents/nodes/convention.py` | convention 노드 |
| `agents/nodes/test_gen.py` | test_gen 노드 |
| `agents/nodes/arch_review.py` | arch_review 노드 (HITL 아키텍처 점검) |
| `agents/nodes/test_runner.py` | test_run / fix_test 노드 + should_retry |
| `agents/nodes/impact.py` | impact 노드 |
| `agents/nodes/domain_explainer.py` | domain_explain 노드 (Hybrid RAG) |
| `agents/nodes/risk_report.py` | PR Health Score 계산 + 리포트 카드 |
| `api/rag_upload.py` | 팀 문서 업로드 → RAG 인덱싱 API |
| `agents/nodes/doc_sync.py` | doc_sync 노드 |
| `agents/nodes/commenter.py` | comment 노드 |
| `agents/nodes/slack_notify.py` | slack 노드 |
| `api/webhook.py` | FastAPI 진입점, SSE 스트리밍 |
| `config/prompts.py` | LLM 프롬프트 중앙 관리 |
| `config/conventions.yaml` | 컨벤션 룰북 |
