# Smart PR Inspector Agent — 프로젝트 종합 문서

---

## 1. 프로젝트 도식

![Smart PR Inspector Agent Workflow](./agent-workflow-diagram.png)

### 다이어그램 범례

| 색상 | 의미 |
|------|------|
| 🟦 파랑 | 외부 Tool 노드 (GitHub API, Docker, Slack) |
| 🟨 주황 | LLM 호출 노드 (Claude / GPT) |
| 🟪 보라 마름모 | 분기 조건 (아키텍처 룰 위반?, 테스트 결과?) |
| 🟥 빨강 | Human-in-the-Loop (시니어 승인 대기) |
| 🟩 초록 | 시작/종료 트리거 |
| 🔵 하늘 | 외부 시스템 (ChromaDB) |
| 🔴 빨강 파선 | 실패/재시도 경로 |

### 고급 아키텍처 요소

| 요소 | 설명 | 왜 필요한가 |
|------|------|------------|
| **Human-in-the-Loop** | 아키텍처 룰 위반 시 시니어 리뷰어에게 알림 → 승인/반려 대기 | AI가 아키텍처 의사결정을 독단하지 않도록 인간의 통제 하에 둠 |
| **재시도/폴백** | 테스트 실패 시 LLM 자동 수정 + 최대 3회 재시도. 실패해도 나머지 분석 계속 | LLM 오류로 전체 파이프라인 중단 방지 |
| **Hybrid RAG** | Dense(벡터) + Sparse(BM25) + Cross-Encoder Re-ranking | 의미 검색 + 키워드 정확 매칭을 결합하여 도메인 문서 정밀 검색 |
| **PR Health Score** | 4영역(컨벤션/테스트/영향도/도메인) 100점 만점 → S~F 등급 | 머지 가능 여부를 한눈에 판단 |

---

## 2. 프로젝트 제목

### **Smart PR Inspector Agent**
> AI 기반 GitHub Pull Request 자동 분석 플랫폼

GitHub PR이 생성되면 자동으로 트리거되어, 코드 컨벤션 검증 → 테스트 시나리오 생성/평가 → 영향도 분석 → 비즈니스 설명 → 문서 동기화 → GitHub 코멘트 → Slack 알림까지 수행하는 지능형 코드 리뷰 에이전트입니다.

---

## 3. 해결하고자 한 Pain Point

| Pain Point | 구체적 문제 | 빈도 | 영향도 |
|------------|-----------|------|--------|
| **리뷰 병목** | 시니어 1명이 하루 10+ PR 리뷰 | 매일 | 높음 |
| **컨벤션 위반 반복** | 네이밍, 타입힌트 등 같은 지적 반복 | PR당 3회 | 중간 |
| **사이드 이펙트 미탐지** | 코드 변경이 타 모듈에 미치는 영향 파악 불가 | 월 5회 | 치명적 |
| **문서 불일치** | API 변경 후 Swagger 미업데이트 | 월 8회 | 높음 |
| **도메인 이해 부족** | 비즈니스 로직 변경 설명 부재 | PR당 1회 | 중간 |

---

## 4. 현재 구현된 정도 (v1.3.0)

| 기능 | 상태 |
|------|------|
| LangGraph 11노드 오케스트레이터 (HITL + 재시도) | ✅ |
| AST + LLM + RAG 하이브리드 컨벤션 검증 | ✅ |
| AI BDD 시나리오 생성/평가 (Given/When/Then) | ✅ |
| 아키텍처 룰 점검 + HITL 승인 대기 | ✅ |
| AST 호출그래프 + LLM 비즈니스 영향도 분석 | ✅ |
| Hybrid RAG 도메인 설명 (Dense+Sparse+Re-ranking) | ✅ |
| 팀 컨벤션/도메인 문서 업로드 → RAG 인덱싱 | ✅ |
| PR Health Score (100점 만점, S~F 등급) | ✅ |
| Slack 인터랙티브 (승인 메시지 + 수정 영역 선택) | ✅ |
| Next.js 14 대시보드 + AI 채팅 | ✅ |
| SKILL.md 선언적 스킬 정의 + 레지스트리 | ✅ |
| SSE 실시간 스트리밍 + 이력 관리 | ✅ |

---

## 5. 사용한 에이전트 프레임워크: LangGraph

LangGraph의 `StateGraph`를 사용한 이유:
- **조건부 분기**: `add_conditional_edges`로 HITL 승인/반려, 테스트 재시도 자연스럽게 구현
- **비동기 스트리밍**: `astream()`으로 SSE 실시간 업데이트
- **Pydantic State**: 타입 안전한 상태 관리

```python
workflow.set_entry_point("fetch")
workflow.add_edge("fetch", "convention")
workflow.add_edge("convention", "test_gen")
workflow.add_edge("test_gen", "arch_review")

# HITL 분기
workflow.add_conditional_edges("arch_review", check_arch_approval,
    {"approved": "test_run", "rejected": "comment"})

# 테스트 재시도 분기
workflow.add_conditional_edges("test_run", should_retry,
    {"retry": "fix_test", "success": "impact", "fail": "impact"})
```

---

## 6. 유저 쿼리문

| 시나리오 | 흐름 |
|---------|------|
| **Webhook 자동** | PR 생성 → Webhook → 11노드 분석 → GitHub 코멘트 + Slack 알림 |
| **수동 분석** | 대시보드에서 repo/PR# 입력 → SSE 실시간 노드 상태 표시 |
| **AI 채팅** | "이 PR에서 가장 위험한 변경은?" → Claude가 분석 결과 기반 답변 |
| **Slack 승인** | ✅ 버튼 → "~~~ 기능 PR 승인했습니다" 메시지 |
| **Slack 수정요청** | 🔄 버튼 → 수정 영역 선택 → "~~~ 기능 [영역] 수정 요청하였습니다" |

---

## 7. 사용한 Tools

| Tool | 용도 | 노드 |
|------|------|------|
| **ast** | Python AST 파싱, 호출 그래프 | convention, impact |
| **PyGithub** | GitHub REST API | fetcher, commenter |
| **ChromaDB** | Dense 벡터 검색 | domain_explain, convention (RAG) |
| **rank-bm25** | BM25 Sparse 키워드 검색 | domain_explain, convention (RAG) |
| **sentence-transformers** | Cross-Encoder Re-ranking | domain_explain |
| **OpenAI SDK** | GPT-4o-mini LLM 호출 | convention, test_gen, impact 등 |
| **Anthropic SDK** | AI 채팅 | ChatPanel |
| **Slack SDK** | Block Kit 메시지 + 인터랙션 | slack_notify |
| **Redis** | 분석 결과 캐싱 | webhook |
| **SQLAlchemy** | 분석 이력 저장 | history |

---

## 8. 사용한 Skills (SKILL.md)

`SKILL.md`에 11개 스킬을 선언적으로 정의하고, `config/skills.py`의 `SkillRegistry`가 파싱합니다.

```
fetch          | model=none   | PR 데이터 수집
convention     | model=fast   | AST + RAG + LLM 컨벤션 검증
test_gen       | model=smart  | BDD 시나리오 생성
arch_review    | model=none   | 아키텍처 룰 점검 [HITL]
test_run       | model=smart  | 시나리오 평가 [Retry x3]
impact         | model=fast   | 영향도 + 비즈니스 분석
domain_explain | model=fast   | Hybrid RAG 도메인 설명
doc_sync       | model=fast   | Swagger 변경 감지
comment        | model=none   | GitHub 코멘트 + Health Score 카드
slack          | model=none   | Slack Block Kit 알림
```

API: `GET /api/skills` — 전체 스킬 목록 + 워크플로우 정보 조회

---

## 9. RAG 활용 방식

### Hybrid RAG 파이프라인

```
쿼리 (PR diff + title)
  ├── Dense: ChromaDB 벡터 검색 → Top-20
  ├── Sparse: BM25 키워드 검색 → Top-20
  └── RRF 통합 → Cross-Encoder Re-ranking → Top-5 → LLM 컨텍스트
```

### RAG가 활용되는 2곳

| 노드 | RAG 활용 방식 | 벡터스토어 |
|------|-------------|-----------|
| **convention** | 팀 컨벤션 문서를 RAG 검색 → LLM에 팀 규칙 컨텍스트 전달 | `team_conventions` |
| **domain_explain** | 도메인 문서를 RAG 검색 → 비즈니스 영향도 설명 생성 | `domain_docs` |

### 팀 문서 업로드 API

```bash
# 팀 컨벤션 문서 업로드
curl -X POST http://localhost:8000/api/rag/upload/convention \
  -F "file=@team-coding-guide.md" -F "team_name=backend"

# 도메인 문서 업로드
curl -X POST http://localhost:8000/api/rag/upload/domain \
  -F "file=@business-rules.md" -F "team_name=backend"

# RAG 인덱스 통계
curl http://localhost:8000/api/rag/stats
```

---

## 10. 중간 노드 결과값 (요약)

| 노드 | 주요 출력 |
|------|----------|
| fetch | `pr_data` (diff, changed_files, author, title, labels) |
| convention | `convention_result` (violations list, passed, summary) + RAG 팀 규칙 반영 |
| test_gen | `test_result.scenarios` (Given/When/Then BDD 시나리오) |
| arch_review | `arch_review` (violations, approval_status: approved/rejected) |
| test_run | `test_result` (verdict, reasoning, confidence per scenario) |
| impact | `impact_analysis` (risk_level, affected_modules, business_impact) |
| domain_explain | `domain_explanation` (200자 비즈니스 설명, Hybrid RAG 기반) |
| doc_sync | `doc_updates` (Swagger 업데이트 YAML 초안) |

---

## 11. 최종 노드 결과값

### GitHub PR 코멘트 (Health Score 포함)

```markdown
## 🤖 Smart PR Inspector 분석 결과

### 🏆 PR Health Score: S (95/100)
> 즉시 머지 가능

| 영역     | 점수              |
|----------|-------------------|
| 📋 컨벤션 | ██████████ 25/25 |
| 🧪 테스트 | ████████░░ 20/25 |
| 🔗 영향도 | ██████████ 25/25 |
| 📖 도메인 | ██████████ 25/25 |

(컨벤션/테스트/영향도/도메인 상세 결과...)
```

### Slack 메시지 (인터랙티브)

```
🤖 Smart PR Inspector 분석 완료
PR #42: feat: 결제 모듈 리팩토링 | @jiyoon

📊 Convention: ✅ | Tests: ✅ 4/5 | Risk: 🟠 HIGH
🏆 Health Score: A (85/100) — 머지 권장

[✅ 승인]  [🔄 수정 요청]  [📋 GitHub에서 보기]
```

**승인 클릭 시**: "✅ 결제 모듈 리팩토링 기능 PR 승인했습니다. 승인자: jiyoon"
**수정 요청 클릭 시**: 수정 영역 선택 → "🔄 결제 모듈 리팩토링 기능 [보안] 수정 요청하였습니다."

---

## 12. 이 외 사항

| 항목 | 사용 여부 | 설명 |
|------|----------|------|
| **SKILL.md** | ✅ 사용 | 11개 스킬 선언적 정의 + SkillRegistry 파서 |
| **System Prompt** | ✅ 사용 | `config/prompts.py`에 10개 LLM 프롬프트 중앙 관리 |
| **Middleware** | ✅ 사용 | CORS, GitHub Webhook 서명 검증 (HMAC-SHA256) |
| **conventions.yaml** | ✅ 사용 | 팀 코딩 규칙 YAML 정의 (AST 검사용) |
| **Docker 격리** | ✅ 사용 | 테스트 실행 시 컨테이너 격리 (메모리/CPU 제한) |
| **Prometheus** | ✅ 사용 | `/metrics` 분석 횟수, 소요 시간 메트릭 |

---

## 13. 앞으로의 고도화 계획

| 기능 | 우선순위 |
|------|---------|
| LLM 모델 Anthropic Claude로 전환 (분석 품질 향상) | P1 |
| 과거 PR 리뷰 패턴 학습 RAG (개발자별 맞춤 피드백) | P1 |
| Multi-language 지원 (JS, TS, Java AST 분석) | P2 |
| 레포 자동 학습 RAG (새 레포 분석 시 README/구조 자동 인덱싱) | P2 |
| 외부 규제/표준 문서 RAG (PCI-DSS, HIPAA 등 컴플라이언스) | P3 |

---

## 부록: 기술 스택

| 분류 | 기술 |
|------|------|
| 에이전트 | LangGraph 0.2.x (StateGraph) |
| LLM | OpenAI GPT-4o-mini (분석), Anthropic Claude (채팅) |
| RAG | ChromaDB + rank-bm25 + sentence-transformers (Hybrid) |
| 백엔드 | Python 3.11, FastAPI, Pydantic v2 |
| 프론트엔드 | Next.js 14, TypeScript, Tailwind CSS, Zustand |
| 인프라 | Docker Compose, Redis, SQLAlchemy |
| 외부 연동 | GitHub API, Slack API |

---

*v1.3.0 (2026-04-10) 기준*
