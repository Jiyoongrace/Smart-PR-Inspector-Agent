"""
Agent 상태 모델 정의 (Pydantic 기반)
LangGraph StateGraph에서 공유되는 불변 상태 스키마
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class NodeStatus(str, Enum):
    """각 Agent 노드의 실행 상태"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class PRData(BaseModel):
    """GitHub PR 기본 데이터"""
    pr_number: int
    repo: str
    author: str
    title: str
    body: str = ""
    diff: str = ""
    changed_files: List[str] = Field(default_factory=list)
    base_branch: str = "main"
    head_branch: str = ""
    pr_url: str = ""
    labels: List[str] = Field(default_factory=list)
    # "Fix #123" 패턴에서 추출된 이슈 번호
    linked_issues: List[int] = Field(default_factory=list)


class ConventionViolation(BaseModel):
    """컨벤션 위반 항목"""
    file: str
    line: int
    rule: str
    message: str
    suggestion: Optional[str] = None
    severity: str = "warning"  # warning | error | info


class ConventionResult(BaseModel):
    """컨벤션 검증 결과"""
    passed: bool
    violations: List[ConventionViolation] = Field(default_factory=list)
    summary: str = ""


class ScenarioVerdict(str, Enum):
    """AI 시나리오 검증 결과"""
    PASS = "pass"
    FAIL = "fail"
    UNCLEAR = "unclear"


class TestScenario(BaseModel):
    """도메인 전문가도 이해할 수 있는 테스트 시나리오 (Given/When/Then)"""
    id: str
    title: str          # 한 줄 요약 (예: "PR 분석 요청 시 결과 반환")
    given: str          # 전제 조건
    when: str           # 동작
    then: str           # 기대 결과
    category: str = ""  # 기능 | 예외 | 경계값 | 보안


class ScenarioResult(BaseModel):
    """AI가 평가한 시나리오별 검증 결과"""
    scenario: TestScenario
    verdict: ScenarioVerdict
    reasoning: str      # AI 판단 근거 (한국어 평문)
    confidence: int = 0  # 0-100, AI 확신도


class TestResult(BaseModel):
    """테스트 검증 결과 (AI 시나리오 방식)"""
    passed: bool = False
    # 코드 실행 방식 호환 필드 (레거시)
    test_code: str = ""
    stdout: str = ""
    stderr: str = ""
    retry_count: int = 0
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    duration_seconds: float = 0.0
    # AI 시나리오 검증 결과
    scenarios: List[ScenarioResult] = Field(default_factory=list)
    verification_mode: str = "ai_scenario"  # "ai_scenario" | "code"


class BusinessImpact(BaseModel):
    """비즈니스 관점 영향도 분석"""
    summary: str = ""
    affected_features: List[str] = Field(default_factory=list)
    user_facing_changes: str = ""
    risk_description: str = ""
    recommendations: List[str] = Field(default_factory=list)


class ImpactAnalysis(BaseModel):
    """코드 영향도 분석 결과"""
    changed_functions: List[str] = Field(default_factory=list)
    affected_modules: List[Dict[str, Any]] = Field(default_factory=list)
    has_api_changes: bool = False
    call_chain: List[str] = Field(default_factory=list)
    risk_level: str = "low"  # low | medium | high | critical
    business_impact: Optional[BusinessImpact] = None


class ComplexityResult(BaseModel):
    """코드 복잡도 분석 결과"""
    cyclomatic_complexity: Dict[str, float] = Field(default_factory=dict)
    security_issues: List[Dict[str, Any]] = Field(default_factory=list)
    high_complexity_functions: List[str] = Field(default_factory=list)


class ArchReviewResult(BaseModel):
    """아키텍처 룰 점검 결과"""
    has_violation: bool = False
    violations: List[str] = Field(default_factory=list)
    # HITL 승인 상태: pending / approved / rejected
    approval_status: str = "pending"
    reviewer: str = ""
    review_comment: str = ""


class NodeExecutionStatus(BaseModel):
    """각 노드의 실행 상태 (UI 실시간 표시용)"""
    fetch: NodeStatus = NodeStatus.PENDING
    convention: NodeStatus = NodeStatus.PENDING
    test_gen: NodeStatus = NodeStatus.PENDING
    arch_review: NodeStatus = NodeStatus.PENDING
    test_run: NodeStatus = NodeStatus.PENDING
    impact: NodeStatus = NodeStatus.PENDING
    domain_explain: NodeStatus = NodeStatus.PENDING
    doc_sync: NodeStatus = NodeStatus.PENDING
    comment: NodeStatus = NodeStatus.PENDING
    slack: NodeStatus = NodeStatus.PENDING


class AgentState(BaseModel):
    """
    LangGraph StateGraph의 공유 상태
    모든 노드가 이 상태를 읽고 수정함
    """
    # PR 기본 정보 (fetch 노드에서 채워짐)
    pr_data: Optional[PRData] = None

    # 각 분석 결과
    convention_result: Optional[ConventionResult] = None
    test_result: Optional[TestResult] = None
    # test_gen → test_run 전달용 시나리오 임시 저장
    pending_scenarios: List[TestScenario] = Field(default_factory=list)
    impact_analysis: Optional[ImpactAnalysis] = None
    complexity_result: Optional[ComplexityResult] = None

    # RAG / 도메인 설명
    domain_explanation: Optional[str] = None
    domain_sources: List[str] = Field(default_factory=list)

    # 문서 동기화
    doc_updates: Optional[str] = None

    # 최종 결과물
    final_comment: Optional[str] = None
    slack_thread_id: Optional[str] = None
    github_comment_id: Optional[int] = None

    # 아키텍처 룰 점검 (HITL)
    arch_review: Optional[ArchReviewResult] = None

    # 실행 메타데이터
    node_status: NodeExecutionStatus = Field(default_factory=NodeExecutionStatus)
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    # 개발자 메모리 (과거 PR 이력)
    author_history: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True
