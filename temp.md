Smart PR Inspector Agent 개발 가이드
📋 목차

개요
Agent 아키텍처
Pain → Task → Skill → Tool 분해
주요 기능
기술 스택
구현 가이드
배포 및 운영


개요
Agent 정의
Smart PR Inspector Agent는 GitHub Pull Request 생성 시 자동으로 트리거되어, 코드 분석부터 컨벤션 검증, 테스트 실행, 문서 동기화, 비즈니스 영향도 분석까지 수행하는 지능형 코드 품질 관리 에이전트입니다.
핵심 가치 제안

리뷰 병목 해소: 시니어 개발자의 반복적 검토 시간 80% 절감
품질 사전 보장: PR 머지 전 사이드 이펙트 및 컨벤션 위반 자동 탐지
지식 전이: 도메인 문서 기반 비즈니스 영향도 자동 설명
문서 동기화: API 스펙 변경 시 Swagger/README 자동 업데이트 제안

Agent 4요소 정의
요소구현 내용핵심 질문에 대한 답변GoalPR 코드가 병합 가능한 상태인지 자동 검증 및 리뷰"테스트 통과 + 컨벤션 준수 + 문서 동기화 완료"Memory- 과거 PR 리뷰 패턴- 팀 코딩 컨벤션 룰북- 도메인 지식 벡터 DB- 이전 실행 테스트 결과"유사 코드 변경 이력, 컨벤션 위반 패턴, 도메인 용어 정의"ToolGitHub API, 테스트 러너, LLM(GPT-4), 벡터 DB(Pinecone), Slack API, AST 파서"코드 분석, 외부 시스템 연동, 검색, 알림"Control Logic- 테스트 실패 시 최대 3회 재시도- 타임아웃 5분- 실패 시 Fallback 경로"재시도 조건: 문법 에러 검출중단 조건: 타임아웃 or 3회 실패"

Agent 아키텍처
패턴: Planner + ReAct Hybrid
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

Pain → Task → Skill → Tool 분해
1단계: Pain Points 식별
Pain구체적 문제빈도영향도리뷰 병목시니어 1명이 하루 10+ PR 리뷰매일높음컨벤션 위반네이밍, 들여쓰기 등 반복 지적PR당 3회중간사이드 이펙트타 모듈 영향도 파악 안됨월 5회치명적문서 불일치API 변경 후 Swagger 미업데이트월 8회높음도메인 이해 부족비즈니스 로직 변경 설명 부재PR당 1회중간
2단계: Task 분해
Main Task: "PR 자동 품질 검증 및 리뷰"
Sub-task 1: 코드 변경 수집

입력: PR Number, Repository
출력: Diff 파일, 변경된 파일 목록
Skill: GitHub API 호출, Diff 파싱
Tool: PyGithub, unidiff

Sub-task 2: 컨벤션 검증

입력: Diff 파일, 룰북 문서
출력: 위반 항목 리스트
Skill: AST 분석, 규칙 매칭
Tool: ast 모듈, pylint, LLM (GPT-4)

Sub-task 3: 테스트 계획 생성

입력: 변경된 함수/클래스, 기존 테스트 코드
출력: 테스트 스크립트 (.py)
Skill: 코드 문맥 이해, 테스트 템플릿 생성
Tool: LLM (GPT-4), Jinja2

Sub-task 4: 테스트 실행

입력: 테스트 스크립트
출력: Pass/Fail, 에러 로그
Skill: 샌드박스 실행, 타임아웃 관리
Tool: pytest, Docker (격리 환경)

Sub-task 5: 영향도 분석

입력: 변경 함수 시그니처, 호출 그래프
출력: 영향받는 모듈 리스트
Skill: 정적 분석, 의존성 추적
Tool: ast, pyan, LLM

Sub-task 6: 도메인 설명 생성

입력: 변경 내역, 도메인 문서 (RAG)
출력: 비즈니스 영향도 자연어 설명
Skill: 벡터 검색, 문맥 합성
Tool: Pinecone, LangChain

Sub-task 7: 문서 동기화 검사

입력: API 변경 내역, 기존 Swagger/README
출력: 업데이트 초안 (Markdown/YAML)
Skill: Diff 비교, 템플릿 기반 생성
Tool: pydantic, swagger-parser, LLM

Sub-task 8: 리뷰 코멘트 작성

입력: 전체 검증 결과
출력: GitHub PR Comment (Markdown)
Skill: 구조화된 리포트 생성
Tool: GitHub API, Slack API

3단계: Workflow 설계
python# LangGraph StateGraph 구조
from langgraph.graph import StateGraph, END

workflow = StateGraph()

# Nodes
workflow.add_node("fetch_pr_data", fetch_pr_data_node)
workflow.add_node("convention_check", convention_check_node)
workflow.add_node("test_generator", test_generator_node)
workflow.add_node("test_runner", test_runner_node)
workflow.add_node("fix_test_code", fix_test_code_node)  # Retry용
workflow.add_node("impact_analysis", impact_analysis_node)
workflow.add_node("domain_explainer", domain_explainer_node)  # RAG
workflow.add_node("doc_sync_check", doc_sync_check_node)
workflow.add_node("generate_comment", generate_comment_node)
workflow.add_node("slack_notify", slack_notify_node)

# Edges
workflow.add_edge("fetch_pr_data", "convention_check")
workflow.add_edge("fetch_pr_data", "test_generator")  # Parallel
workflow.add_edge("convention_check", "impact_analysis")
workflow.add_edge("test_generator", "test_runner")

# Conditional Edge (Retry Logic)
workflow.add_conditional_edges(
    "test_runner",
    should_retry_test,
    {
        "retry": "fix_test_code",
        "success": "impact_analysis",
        "fail": "generate_comment"  # Fallback
    }
)
workflow.add_edge("fix_test_code", "test_runner")  # 재시도

workflow.add_edge("impact_analysis", "domain_explainer")
workflow.add_edge("domain_explainer", "doc_sync_check")
workflow.add_edge("doc_sync_check", "generate_comment")
workflow.add_edge("generate_comment", "slack_notify")
workflow.add_edge("slack_notify", END)

workflow.set_entry_point("fetch_pr_data")

주요 기능
1. 코드 변경 분석 및 컨벤션 검증 ✅
What: PR에서 변경된 코드를 AST 파싱하여 사내 컨벤션 룰북과 대조
How:

unidiff로 Diff 파싱 → 추가/수정된 라인 추출
ast.parse()로 Python AST 생성
컨벤션 룰북 (JSON/YAML)과 패턴 매칭
위반 시 라인 번호 + 규칙명 + 제안 코드 반환

Example Output:
markdown### ❌ 컨벤션 위반 (3건)
- Line 42: 함수명 `getData` → `get_data` (snake_case 규칙)
- Line 58: 매직넘버 `7` → 상수로 분리 권장
- Line 103: 타입 힌트 누락 → `def process(data: dict) -> List[str]`
2. AI 기반 테스트 자동 생성 및 실행 🧪
What: 변경된 함수에 대해 LLM이 pytest 코드를 생성하고 Docker에서 실행
How:

변경 함수의 시그니처 + docstring 추출
GPT-4에게 "이 함수를 검증하는 pytest 코드 작성" 프롬프트
생성된 코드를 임시 파일로 저장
Docker 컨테이너에서 pytest --tb=short 실행 (타임아웃 5분)
실패 시 에러 로그를 다시 LLM에 전달 → 코드 수정 (최대 3회)

Example:
python# 변경된 함수
def calculate_discount(price: float, user_tier: str) -> float:
    """사용자 등급에 따른 할인가 계산"""
    ...

# AI가 생성한 테스트
def test_calculate_discount_vip():
    assert calculate_discount(100, "VIP") == 85.0

def test_calculate_discount_invalid_tier():
    with pytest.raises(ValueError):
        calculate_discount(100, "INVALID")
3. 코드 영향도 분석 (Static Analysis) 📊
What: 변경된 함수가 어떤 모듈/함수에서 호출되는지 추적
How:

ast 모듈로 전체 프로젝트 파싱 → 호출 그래프 생성
변경된 함수를 시작점으로 DFS/BFS 탐색
영향받는 파일 리스트 + 호출 체인 반환

Example Output:
markdown### 🔗 영향도 분석
`calculate_discount()` 변경 시 영향받는 모듈:
- `order_service.py` (Line 145: create_order)
- `invoice_generator.py` (Line 78: generate_invoice)
- `api/v1/checkout.py` (Line 203: POST /checkout)

⚠️ **주의**: API 엔드포인트 변경 감지됨 → Swagger 업데이트 필요
4. 도메인 기반 비즈니스 영향도 설명 (RAG) 📚
What: 내부 도메인 문서를 검색하여 변경이 비즈니스적으로 어떤 의미인지 설명
How:

사전에 Confluence/Notion 문서를 크롤링 → 벡터 DB (Pinecone) 저장
변경된 함수명 + 주변 코드를 쿼리로 유사 문서 검색
검색된 문서 + 코드 Diff를 GPT-4에게 전달
"이 변경이 '재고 차감 로직'에 미치는 영향을 300자 이내로 설명하라" 프롬프트

Example Output:
markdown### 📖 도메인 영향도
이번 변경은 **주문 취소 시 포인트 환급 정책**을 수정합니다.
기존에는 결제 금액 기준으로 환급했으나, 변경 후에는 실제 사용한 포인트만 환급됩니다.
이는 "2024 Q2 포인트 제도 개편"과 연관되며, CS 팀과 사전 조율이 필요합니다.

📎 참고 문서: [Confluence - 포인트 정책 v3.2]
5. API 스펙 변경 감지 및 문서 동기화 📝
What: FastAPI/Flask 엔드포인트 변경 시 Swagger/README 업데이트 제안
How:

ast 파서로 @app.post() 데코레이터 + 함수 시그니처 추출
기존 swagger.yaml / openapi.json 파싱
Diff 비교 → 추가/변경/삭제된 필드 탐지
Jinja2 템플릿으로 업데이트 초안 생성
PR 코멘트에 "제안된 Swagger 변경사항" 첨부

Example Output:
yaml# 제안된 Swagger 업데이트
/api/checkout:
  post:
    parameters:
      - name: user_tier  # 🆕 신규 추가
        in: body
        required: true
        type: string
        enum: [BASIC, VIP, PREMIUM]
6. Slack 연동 승인 워크플로우 💬
What: 시니어가 Slack에서 PR 승인/거부를 처리 가능
How:

Agent가 PR 분석 완료 후 Slack 채널에 메시지 전송
Slack Block Kit으로 "승인", "수정 요청", "상세 보기" 버튼 제공
버튼 클릭 시 Slack Webhook → GitHub API로 Review 제출
승인 시 자동 머지 (옵션)

Example Slack Message:
🤖 Smart PR Inspector

PR #1234: "재고 차감 로직 개선"
✅ 컨벤션: 통과
✅ 테스트: 5/5 통과
⚠️ 영향도: 3개 모듈 변경
📄 Swagger 업데이트 필요

[승인] [수정 요청] [상세 보기]
7. 버그 수정 검증 테스트 생성 🐛
What: PR 제목/본문에 "Fix #123" 패턴이 있으면 해당 이슈를 재현하는 테스트 생성
How:

GitHub Issue API로 #123 내용 조회
이슈 설명 + 재현 단계를 GPT-4에게 전달
"이 버그를 재현하는 테스트 코드" 생성 요청
수정 전 코드에서 테스트 실행 → Fail 확인
수정 후 코드에서 재실행 → Pass 확인

Example:
python# Issue #123: "VIP 사용자 할인이 적용 안됨"

# AI 생성 테스트
def test_issue_123_vip_discount_bug():
    """Issue #123: VIP 할인 미적용 버그 재현"""
    result = calculate_discount(100, "VIP")
    assert result == 85.0, "VIP should get 15% off"
8. 메모리 기반 학습 (과거 리뷰 패턴 반영) 🧠
What: 같은 개발자의 과거 PR 리뷰 이력을 학습하여 맞춤형 피드백
How:

PostgreSQL/Redis에 {author: 리뷰 코멘트} 이력 저장
새 PR 분석 시 작성자의 과거 위반 패턴 조회
"이 개발자는 과거에 타입 힌트를 자주 누락했음" → 타입 체크 강화

Example:
markdown### 💡 맞춤 제안 (Based on your history)
과거 3회의 PR에서 `Exception` 대신 구체적 예외를 사용하지 않은 사례가 있었습니다.
이번 PR의 Line 67에서도 동일한 패턴이 발견되었습니다.

기술 스택
Core Framework
yamlOrchestration:
  - LangGraph 0.2.x: State 기반 Agent 워크플로우 (Conditional Edges 지원)
  - LangChain 0.3.x: LLM 체이닝, RAG 파이프라인

LLM:
  - OpenAI GPT-4 Turbo (gpt-4-1106-preview): 코드 분석 및 생성
  - 대안: Anthropic Claude 3 Opus (긴 컨텍스트 처리)

Memory & Vector DB:
  - Pinecone (무료 플랜): 도메인 문서 벡터 저장
  - Redis: 세션 상태 캐싱

Data Validation:
  - Pydantic 2.x: Agent State 스키마 정의
Tools & Integrations
yamlGitHub:
  - PyGithub: PR/Issue/Comment API
  - GitHub Actions: Webhook 트리거

Code Analysis:
  - ast (내장): Python AST 파싱
  - pylint: 린트 규칙 검증
  - radon: 복잡도 분석
  - unidiff: Git Diff 파싱

Testing:
  - pytest: 테스트 실행
  - pytest-timeout: 타임아웃 관리
  - Docker Python SDK: 격리 환경

Documentation:
  - swagger-parser: OpenAPI 스펙 파싱
  - prance: Swagger 검증
  - Jinja2: 문서 템플릿 생성

Communication:
  - Slack SDK: 메시지 전송 및 Interactive Buttons
  - Slack Bolt: 이벤트 핸들링

Monitoring:
  - Sentry: 에러 추적
  - Prometheus + Grafana: 메트릭 수집
Infrastructure
yamlDeployment:
  - FastAPI: Webhook 수신 서버
  - Docker Compose: 로컬 개발 환경
  - Railway / Render (무료 Tier): 프로덕션 배포
  - Cloudflare Workers (대안): Serverless 옵션

Database:
  - PostgreSQL (Supabase 무료): 리뷰 이력 저장
  - Redis Cloud (무료 30MB): 캐싱

CI/CD:
  - GitHub Actions: 자동 배포

구현 가이드
Phase 1: 기본 워크플로우 구축 (Week 1-2)
1.1 프로젝트 초기화
bash# 디렉토리 구조
smart-pr-inspector/
├── agents/
│   ├── __init__.py
│   ├── orchestrator.py      # LangGraph 워크플로우
│   ├── nodes/
│   │   ├── fetcher.py        # GitHub 데이터 수집
│   │   ├── convention.py     # 컨벤션 체크
│   │   ├── test_gen.py       # 테스트 생성
│   │   ├── test_runner.py    # 테스트 실행
│   │   ├── impact.py         # 영향도 분석
│   │   └── commenter.py      # 코멘트 작성
│   └── state.py             # Pydantic State 모델
├── tools/
│   ├── github_tool.py       # PyGithub 래퍼
│   ├── ast_tool.py          # AST 분석
│   └── docker_tool.py       # Docker 실행
├── memory/
│   ├── vector_store.py      # Pinecone 연동
│   └── cache.py             # Redis 캐싱
├── api/
│   └── webhook.py           # FastAPI 서버
├── config/
│   ├── conventions.yaml     # 컨벤션 룰북
│   └── prompts.py           # LLM 프롬프트
├── tests/
├── docker-compose.yml
├── requirements.txt
└── README.md
1.2 State 모델 정의 (Pydantic)
python# agents/state.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class PRData(BaseModel):
    pr_number: int
    repo: str
    author: str
    title: str
    diff: str
    changed_files: List[str]

class ConventionResult(BaseModel):
    passed: bool
    violations: List[Dict[str, str]] = Field(default_factory=list)
    # violations: [{"line": 42, "rule": "snake_case", "message": "..."}]

class TestResult(BaseModel):
    passed: bool
    test_code: str
    stdout: str
    stderr: str
    retry_count: int = 0

class AgentState(BaseModel):
    pr_data: Optional[PRData] = None
    convention_result: Optional[ConventionResult] = None
    test_result: Optional[TestResult] = None
    impact_analysis: Optional[str] = None
    domain_explanation: Optional[str] = None
    doc_updates: Optional[str] = None
    final_comment: Optional[str] = None
    slack_thread_id: Optional[str] = None
1.3 LangGraph 워크플로우 구축
python# agents/orchestrator.py
from langgraph.graph import StateGraph, END
from agents.state import AgentState
from agents.nodes import (
    fetch_pr_data_node,
    convention_check_node,
    test_generator_node,
    test_runner_node,
    fix_test_code_node,
    impact_analysis_node,
    generate_comment_node
)

def create_workflow():
    workflow = StateGraph(AgentState)
    
    # 노드 등록
    workflow.add_node("fetch", fetch_pr_data_node)
    workflow.add_node("convention", convention_check_node)
    workflow.add_node("test_gen", test_generator_node)
    workflow.add_node("test_run", test_runner_node)
    workflow.add_node("fix_test", fix_test_code_node)
    workflow.add_node("impact", impact_analysis_node)
    workflow.add_node("comment", generate_comment_node)
    
    # 엣지 연결
    workflow.add_edge("fetch", "convention")
    workflow.add_edge("fetch", "test_gen")  # Parallel
    workflow.add_edge("convention", "impact")
    workflow.add_edge("test_gen", "test_run")
    
    # 조건부 재시도
    def should_retry(state: AgentState) -> str:
        if not state.test_result:
            return "fail"
        if state.test_result.passed:
            return "success"
        if state.test_result.retry_count < 3:
            return "retry"
        return "fail"
    
    workflow.add_conditional_edges(
        "test_run",
        should_retry,
        {
            "retry": "fix_test",
            "success": "impact",
            "fail": "comment"  # Fallback
        }
    )
    workflow.add_edge("fix_test", "test_run")
    
    workflow.add_edge("impact", "comment")
    workflow.add_edge("comment", END)
    
    workflow.set_entry_point("fetch")
    return workflow.compile()
Phase 2: 각 Node 구현 (Week 3-4)
2.1 GitHub 데이터 수집 Node
python# agents/nodes/fetcher.py
from github import Github
from agents.state import AgentState, PRData
import os

def fetch_pr_data_node(state: AgentState) -> AgentState:
    """GitHub PR 데이터 수집"""
    gh = Github(os.getenv("GITHUB_TOKEN"))
    repo = gh.get_repo(os.getenv("GITHUB_REPO"))
    pr = repo.get_pull(state.pr_data.pr_number)
    
    # Diff 가져오기
    files = pr.get_files()
    diff_text = "\n".join([f.patch for f in files if f.patch])
    
    state.pr_data = PRData(
        pr_number=pr.number,
        repo=repo.full_name,
        author=pr.user.login,
        title=pr.title,
        diff=diff_text,
        changed_files=[f.filename for f in files]
    )
    return state
2.2 컨벤션 체크 Node (AST + LLM Hybrid)
python# agents/nodes/convention.py
import ast
import yaml
from langchain_openai import ChatOpenAI
from agents.state import AgentState, ConventionResult

def convention_check_node(state: AgentState) -> AgentState:
    """컨벤션 검증: AST 기반 + LLM 보조"""
    violations = []
    
    # 1. AST 기반 빠른 체크 (네이밍, 타입 힌트 등)
    for file_path in state.pr_data.changed_files:
        if not file_path.endswith(".py"):
            continue
        
        with open(file_path, "r") as f:
            code = f.read()
        
        try:
            tree = ast.parse(code)
        except SyntaxError:
            violations.append({
                "file": file_path,
                "line": 0,
                "rule": "syntax_error",
                "message": "구문 오류 발견"
            })
            continue
        
        # 함수명 snake_case 체크
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if not is_snake_case(node.name):
                    violations.append({
                        "file": file_path,
                        "line": node.lineno,
                        "rule": "snake_case",
                        "message": f"함수명 {node.name}은 snake_case를 사용하세요"
                    })
    
    # 2. LLM으로 복잡한 규칙 검증 (가독성, 로직 중복 등)
    if len(state.pr_data.diff) < 5000:  # 토큰 제한
        llm = ChatOpenAI(model="gpt-4-turbo-preview")
        rules = yaml.safe_load(open("config/conventions.yaml"))
        
        prompt = f"""
다음 코드 변경사항이 우리 팀 컨벤션을 준수하는지 검사하세요.

컨벤션 규칙:
{rules}

코드 Diff:
{state.pr_data.diff}

위반 사항을 JSON 배열로 반환하세요:
[{{"line": 42, "rule": "magic_number", "message": "..."}}]
"""
        response = llm.invoke(prompt)
        # JSON 파싱 및 violations에 추가...
    
    state.convention_result = ConventionResult(
        passed=len(violations) == 0,
        violations=violations
    )
    return state

def is_snake_case(name: str) -> bool:
    return name.islower() and "_" in name or name.islower()
2.3 테스트 생성 Node (LLM)
python# agents/nodes/test_gen.py
from langchain_openai import ChatOpenAI
from agents.state import AgentState

def test_generator_node(state: AgentState) -> AgentState:
    """변경된 함수에 대한 pytest 코드 생성"""
    llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0)
    
    # 변경된 함수 추출 (간단한 예시)
    changed_functions = extract_functions_from_diff(state.pr_data.diff)
    
    prompt = f"""
당신은 Python 테스트 전문가입니다.
다음 함수에 대한 pytest 테스트 코드를 작성하세요.

함수:
{changed_functions[0]}  # 첫 번째 함수만 데모

요구사항:
1. 정상 케이스 3개
2. 예외 케이스 2개
3. 경계값 테스트 1개
4. pytest fixture 사용
5. 주석 없이 코드만 출력

출력 형식:
```python
import pytest
...
```
"""
    
    response = llm.invoke(prompt)
    test_code = extract_code_from_markdown(response.content)
    
    # 임시 파일로 저장
    with open("/tmp/test_generated.py", "w") as f:
        f.write(test_code)
    
    state.test_result = TestResult(
        passed=False,  # 아직 실행 전
        test_code=test_code,
        stdout="",
        stderr=""
    )
    return state
2.4 테스트 실행 Node (Docker)
python# agents/nodes/test_runner.py
import docker
from agents.state import AgentState, TestResult

def test_runner_node(state: AgentState) -> AgentState:
    """Docker 컨테이너에서 pytest 실행"""
    client = docker.from_env()
    
    try:
        container = client.containers.run(
            image="python:3.11-slim",
            command="bash -c 'pip install pytest && pytest /tests/test_generated.py -v'",
            volumes={
                "/tmp": {"bind": "/tests", "mode": "rw"}
            },
            detach=True,
            remove=True
        )
        
        # 5분 타임아웃
        result = container.wait(timeout=300)
        logs = container.logs().decode("utf-8")
        
        passed = result["StatusCode"] == 0
        
        state.test_result = TestResult(
            passed=passed,
            test_code=state.test_result.test_code,
            stdout=logs if passed else "",
            stderr=logs if not passed else "",
            retry_count=state.test_result.retry_count
        )
        
    except docker.errors.ContainerError as e:
        state.test_result.stderr = str(e)
        state.test_result.passed = False
    
    return state
Phase 3: 고급 기능 구현 (Week 5-6)
3.1 RAG 기반 도메인 설명
python# agents/nodes/domain_explainer.py
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_pinecone import PineconeVectorStore
from langchain.chains import RetrievalQA

def domain_explainer_node(state: AgentState) -> AgentState:
    """도메인 문서 검색 + LLM 설명 생성"""
    
    # Pinecone 벡터 검색
    embeddings = OpenAIEmbeddings()
    vectorstore = PineconeVectorStore(
        index_name="domain-docs",
        embedding=embeddings
    )
    
    # 변경 함수명 + 주변 코드를 쿼리로
    query = f"{state.pr_data.title}\n{state.pr_data.diff[:500]}"
    
    # 유사 문서 3개 검색
    docs = vectorstore.similarity_search(query, k=3)
    
    # RetrievalQA 체인
    llm = ChatOpenAI(model="gpt-4-turbo-preview")
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=vectorstore.as_retriever(),
        return_source_documents=True
    )
    
    prompt = f"""
다음 코드 변경이 비즈니스적으로 어떤 의미인지 300자 이내로 설명하세요.
관련 도메인 문서를 참고하여 작성하고, 주의사항이 있다면 언급하세요.

변경 내역:
{state.pr_data.diff[:1000]}
"""
    
    result = qa_chain.invoke({"query": prompt})
    
    # 출처 문서 링크 추가
    sources = "\n".join([
        f"- [{doc.metadata.get('title', 'Untitled')}]({doc.metadata.get('url', '#')})"
        for doc in result["source_documents"]
    ])
    
    explanation = f"{result['result']}\n\n📎 참고 문서:\n{sources}"
    
    state.domain_explanation = explanation
    return state
3.2 Swagger 동기화 체크
python# agents/nodes/doc_sync.py
import ast
import yaml
from typing import List, Dict

def doc_sync_check_node(state: AgentState) -> AgentState:
    """API 변경 시 Swagger 업데이트 제안"""
    
    # FastAPI 엔드포인트 추출
    api_changes = []
    for file_path in state.pr_data.changed_files:
        if "api" not in file_path or not file_path.endswith(".py"):
            continue
        
        with open(file_path, "r") as f:
            tree = ast.parse(f.read())
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # @app.post() 데코레이터 찾기
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call):
                        if hasattr(decorator.func, 'attr'):
                            if decorator.func.attr in ['post', 'get', 'put', 'delete']:
                                # 엔드포인트 경로 추출
                                path = decorator.args[0].s if decorator.args else "unknown"
                                
                                # 파라미터 추출
                                params = [arg.arg for arg in node.args.args]
                                
                                api_changes.append({
                                    "method": decorator.func.attr.upper(),
                                    "path": path,
                                    "function": node.name,
                                    "params": params
                                })
    
    if not api_changes:
        state.doc_updates = None
        return state
    
    # 기존 Swagger 비교
    try:
        with open("docs/swagger.yaml", "r") as f:
            swagger = yaml.safe_load(f)
    except FileNotFoundError:
        swagger = {"paths": {}}
    
    # 변경사항 감지 및 초안 생성
    updates = []
    for change in api_changes:
        path = change["path"]
        method = change["method"].lower()
        
        if path not in swagger.get("paths", {}):
            updates.append(f"🆕 신규 엔드포인트: {method.upper()} {path}")
            # Jinja2로 초안 생성...
        else:
            existing_params = swagger["paths"][path].get(method, {}).get("parameters", [])
            new_params = set(change["params"]) - set([p["name"] for p in existing_params])
            if new_params:
                updates.append(f"📝 파라미터 추가: {path} → {', '.join(new_params)}")
    
    state.doc_updates = "\n".join(updates) if updates else None
    return state
Phase 4: Slack 연동 (Week 7)
4.1 Slack 알림 및 Interactive Buttons
python# agents/nodes/slack_notify.py
from slack_sdk import WebClient
from slack_sdk.models.blocks import SectionBlock, ActionsBlock, ButtonElement

def slack_notify_node(state: AgentState) -> AgentState:
    """Slack으로 리뷰 요청 전송"""
    client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))
    
    # 메시지 블록 생성
    blocks = [
        SectionBlock(text=f"🤖 *Smart PR Inspector*\n\nPR #{state.pr_data.pr_number}: {state.pr_data.title}"),
        SectionBlock(fields=[
            f"✅ 컨벤션: {'통과' if state.convention_result.passed else '실패'}",
            f"🧪 테스트: {'통과' if state.test_result.passed else '실패'}",
            f"📊 영향도: {len(state.pr_data.changed_files)}개 파일 변경"
        ]),
        ActionsBlock(elements=[
            ButtonElement(text="승인", action_id="approve_pr", style="primary", value=str(state.pr_data.pr_number)),
            ButtonElement(text="수정 요청", action_id="request_changes", style="danger", value=str(state.pr_data.pr_number)),
            ButtonElement(text="상세 보기", action_id="view_details", url=f"https://github.com/{state.pr_data.repo}/pull/{state.pr_data.pr_number}")
        ])
    ]
    
    response = client.chat_postMessage(
        channel="#code-review",
        blocks=blocks
    )
    
    state.slack_thread_id = response["ts"]
    return state
4.2 Slack Interactivity Handler (FastAPI)
python# api/webhook.py
from fastapi import FastAPI, Request
from slack_bolt.adapter.fastapi import SlackRequestHandler
from slack_bolt import App

app = FastAPI()
slack_app = App(token=os.getenv("SLACK_BOT_TOKEN"))
handler = SlackRequestHandler(slack_app)

@slack_app.action("approve_pr")
def handle_approve(ack, body, client):
    ack()
    pr_number = int(body["actions"][0]["value"])
    
    # GitHub API로 Approve Review 제출
    gh = Github(os.getenv("GITHUB_TOKEN"))
    repo = gh.get_repo(os.getenv("GITHUB_REPO"))
    pr = repo.get_pull(pr_number)
    pr.create_review(event="APPROVE", body="Approved via Slack by Smart PR Inspector")
    
    client.chat_update(
        channel=body["channel"]["id"],
        ts=body["message"]["ts"],
        text=f"✅ PR #{pr_number} 승인 완료!"
    )

@app.post("/slack/events")
async def slack_events(req: Request):
    return await handler.handle(req)

배포 및 운영
Docker Compose 설정
yaml# docker-compose.yml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - PINECONE_API_KEY=${PINECONE_API_KEY}
      - SLACK_BOT_TOKEN=${SLACK_BOT_TOKEN}
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
    volumes:
      - ./agents:/app/agents
      - /var/run/docker.sock:/var/run/docker.sock  # Docker in Docker

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  worker:
    build: .
    command: python -m agents.orchestrator
    environment:
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - redis
GitHub Actions Workflow
yaml# .github/workflows/deploy.yml
name: Deploy Smart PR Inspector

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy to Railway
        run: |
          curl -fsSL https://railway.app/install.sh | sh
          railway up --service smart-pr-inspector
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
모니터링 설정 (Prometheus)
python# api/webhook.py (메트릭 추가)
from prometheus_client import Counter, Histogram, generate_latest

pr_analyzed = Counter('pr_analyzed_total', 'Total PRs analyzed')
analysis_duration = Histogram('analysis_duration_seconds', 'Time spent analyzing PR')

@app.post("/webhook/github")
async def github_webhook(request: Request):
    with analysis_duration.time():
        # ... Agent 실행
        pr_analyzed.inc()

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")

학습 리소스
추천 학습 순서

LangGraph 기초 (3일)

LangGraph Quickstart
StateGraph, Conditional Edges 이해


Pydantic AI (2일)

Pydantic V2 Docs
Agent State 모델링 실습


RAG 구현 (5일)

LangChain RAG Tutorial
Pinecone 벡터 DB 연동


Docker & Testing (3일)

Docker Python SDK 실습
pytest fixture 작성


Slack Bolt (2일)

Slack Bolt for Python
Interactive Component 구현



참고 자료

LangChain Academy - 무료 강의
OpenAI Cookbook - GPT-4 활용 예제
Anthropic Claude Docs - 대안 LLM
GitHub REST API Docs


예상 성과
지표현재목표 (3개월 후)평균 리뷰 시간45분10분 (78% 감소)컨벤션 위반 재발PR당 2.3회0.5회 (78% 감소)문서 불일치월 8건월 1건 (87% 감소)시니어 리뷰 요청일 10회일 3회 (70% 감소)

다음 단계

✅ 이 가이드를 Claude Code에 제공
✅ Phase 1 구현 시작 (기본 워크플로우)
✅ 테스트 데이터로 검증 (실제 PR 3개)
✅ Phase 2-3 점진적 확장
✅ 팀 파일럿 운영 (2주)
✅ 프로덕션 배포