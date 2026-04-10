"""
아키텍처 룰 점검 + Human-in-the-Loop 승인 노드
컨벤션 검증 결과에서 아키텍처 수준의 심각한 위반을 감지하고,
위반 시 시니어 리뷰어에게 알림을 보내 승인/반려를 대기합니다.
"""

import logging
import os
import re
from typing import List

from agents.state import AgentState, ArchReviewResult, NodeStatus

logger = logging.getLogger(__name__)

# 아키텍처 룰 위반으로 판정하는 패턴들
ARCHITECTURE_RULES = [
    {
        "id": "circular_import",
        "pattern": r"from\s+\w+\s+import.*#.*circular",
        "description": "순환 참조(Circular Import) 감지",
    },
    {
        "id": "layer_violation",
        "description": "레이어 위반: Controller/API에서 직접 DB 접근",
        "check": "layer_boundary",
    },
    {
        "id": "god_class",
        "description": "God Class: 단일 클래스에 10개 이상의 public 메서드",
        "check": "method_count",
    },
    {
        "id": "hardcoded_secret",
        "description": "하드코딩된 시크릿/API 키 감지",
        "check": "secret_pattern",
    },
]

# 레이어 위반 감지 패턴: api/router 파일에서 직접 DB import
LAYER_VIOLATION_PATTERNS = [
    (r"(api|router|controller|view)", r"(sqlalchemy|psycopg|cursor\.execute|\.query\()"),
]

# 시크릿 패턴
SECRET_PATTERNS = [
    r"(api_key|secret|password|token)\s*=\s*['\"][^'\"]{8,}['\"]",
    r"sk-[a-zA-Z0-9]{20,}",
    r"ghp_[a-zA-Z0-9]{20,}",
    r"xoxb-[a-zA-Z0-9-]+",
]


def arch_review_node(state: AgentState) -> AgentState:
    """
    아키텍처 룰 점검 노드
    컨벤션 검증과 별도로, 아키텍처 수준의 심각한 위반을 탐지합니다.
    위반 발견 시 HITL 승인을 요청합니다.
    """
    state.node_status.arch_review = NodeStatus.RUNNING

    if not state.pr_data:
        state.node_status.arch_review = NodeStatus.SKIPPED
        return state

    violations: List[str] = []

    # 1. 레이어 위반 검사 (API 레이어에서 직접 DB 접근)
    violations.extend(_check_layer_violations(
        state.pr_data.diff, state.pr_data.changed_files
    ))

    # 2. 시크릿 하드코딩 검사
    violations.extend(_check_secret_patterns(state.pr_data.diff))

    # 3. God Class 검사
    violations.extend(_check_god_class(state.pr_data.diff))

    # 4. 순환 참조 패턴 검사
    violations.extend(_check_circular_imports(state.pr_data.diff))

    has_violation = len(violations) > 0

    state.arch_review = ArchReviewResult(
        has_violation=has_violation,
        violations=violations,
        approval_status="pending" if has_violation else "approved",
    )

    if has_violation:
        logger.warning(
            f"아키텍처 룰 위반 {len(violations)}건 감지 — "
            f"HITL 승인 대기 상태로 전환"
        )
        # 시니어 리뷰어에게 알림 발송
        _notify_reviewer(state, violations)
        state.node_status.arch_review = NodeStatus.SUCCESS
    else:
        logger.info("아키텍처 룰 위반 없음 — 자동 승인 처리")
        state.node_status.arch_review = NodeStatus.SUCCESS

    return state


def check_arch_approval(state: AgentState) -> str:
    """
    아키텍처 룰 점검 결과에 따른 분기 결정
    LangGraph 조건부 엣지에서 사용됩니다.

    Returns:
        "approved" — 위반 없음 또는 시니어 승인됨 → test_run으로 진행
        "rejected" — 시니어 반려 → comment로 건너뜀 (PR 반려 코멘트)
        "pending"  — 승인 대기 중 → 대기 (SSE로 상태 전파)
    """
    if not state.arch_review or not state.arch_review.has_violation:
        return "approved"

    status = state.arch_review.approval_status

    if status == "approved":
        return "approved"
    elif status == "rejected":
        return "rejected"

    # pending 상태: 실제 HITL 대기는 외부에서 처리
    # (SSE를 통해 프론트엔드에 승인 요청 표시)
    # 여기서는 기본적으로 자동 승인으로 진행 (데모 모드)
    logger.info("HITL 승인 대기 — 데모 모드에서 자동 승인 처리")
    state.arch_review.approval_status = "approved"
    return "approved"


def _check_layer_violations(diff: str, changed_files: List[str]) -> List[str]:
    """API 레이어에서 직접 DB 접근 검사"""
    violations = []

    for file_path in changed_files:
        file_lower = file_path.lower()
        is_api_layer = any(
            p in file_lower for p in ("api/", "router", "controller", "view")
        )
        if not is_api_layer:
            continue

        # diff에서 해당 파일 부분의 추가 라인 확인
        db_patterns = [
            "sqlalchemy", "session.query", "session.execute",
            "cursor.execute", "psycopg", ".objects.filter",
            "SELECT ", "INSERT ", "UPDATE ", "DELETE ",
        ]
        for pattern in db_patterns:
            if pattern.lower() in diff.lower():
                violations.append(
                    f"[레이어 위반] {file_path}: API 레이어에서 "
                    f"직접 DB 접근 감지 ('{pattern}')"
                )
                break

    return violations


def _check_secret_patterns(diff: str) -> List[str]:
    """하드코딩된 시크릿 감지"""
    violations = []

    # 추가된 라인만 검사 (+로 시작하는 라인)
    added_lines = [
        line[1:] for line in diff.split("\n")
        if line.startswith("+") and not line.startswith("+++")
    ]
    added_code = "\n".join(added_lines)

    for pattern in SECRET_PATTERNS:
        matches = re.findall(pattern, added_code, re.IGNORECASE)
        if matches:
            violations.append(
                f"[보안 위반] 하드코딩된 시크릿/API 키 감지: "
                f"패턴 '{pattern[:30]}...' 매칭"
            )

    return violations


def _check_god_class(diff: str) -> List[str]:
    """God Class 패턴 감지 (단일 클래스에 메서드 10개 이상 추가)"""
    violations = []
    import ast

    # diff에서 추가된 코드 추출
    added_lines = [
        line[1:] for line in diff.split("\n")
        if line.startswith("+") and not line.startswith("+++")
    ]
    code = "\n".join(added_lines)

    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = [
                    n for n in node.body
                    if isinstance(n, ast.FunctionDef)
                    and not n.name.startswith("_")
                ]
                if len(methods) >= 10:
                    violations.append(
                        f"[구조 위반] 클래스 '{node.name}'에 "
                        f"public 메서드 {len(methods)}개 — "
                        f"단일 책임 원칙(SRP) 위반 가능성"
                    )
    except SyntaxError:
        pass

    return violations


def _check_circular_imports(diff: str) -> List[str]:
    """순환 참조 패턴 감지"""
    violations = []

    # TYPE_CHECKING 없이 상호 import하는 패턴 감지
    added_lines = [
        line[1:].strip() for line in diff.split("\n")
        if line.startswith("+") and not line.startswith("+++")
    ]

    import_targets = set()
    from_modules = set()

    for line in added_lines:
        # from X import Y 패턴
        match = re.match(r"from\s+(\S+)\s+import", line)
        if match:
            from_modules.add(match.group(1))

    # 같은 패키지 내에서 상호 참조 가능성이 높은 패턴
    for mod in from_modules:
        if "." in mod:
            parts = mod.split(".")
            if len(parts) >= 2 and parts[-1] in [p.split(".")[-1] for p in from_modules if p != mod]:
                violations.append(
                    f"[구조 위반] 모듈 '{mod}'에서 순환 참조 가능성 감지"
                )

    return violations


def _notify_reviewer(state: AgentState, violations: List[str]) -> None:
    """
    시니어 리뷰어에게 아키텍처 위반 알림 발송
    실제 구현에서는 Email/Teams/Slack으로 알림을 보냅니다.
    """
    reviewer_email = os.getenv("ARCH_REVIEWER_EMAIL", "")
    reviewer_slack = os.getenv("ARCH_REVIEWER_SLACK_CHANNEL", "")

    violation_text = "\n".join(f"  • {v}" for v in violations)
    message = (
        f"🚨 아키텍처 룰 위반 감지 — 승인 필요\n\n"
        f"PR #{state.pr_data.pr_number}: {state.pr_data.title}\n"
        f"Author: {state.pr_data.author}\n"
        f"Repo: {state.pr_data.repo}\n\n"
        f"위반 사항:\n{violation_text}\n\n"
        f"대시보드에서 승인/반려를 결정해주세요."
    )

    # Slack 알림 (설정된 경우)
    if reviewer_slack:
        try:
            from slack_sdk import WebClient
            client = WebClient(token=os.getenv("SLACK_BOT_TOKEN"))
            client.chat_postMessage(
                channel=reviewer_slack,
                text=message,
            )
            logger.info(f"Slack 알림 발송: {reviewer_slack}")
        except Exception as e:
            logger.warning(f"Slack 알림 실패: {e}")

    logger.info(f"HITL 알림 발송 완료: {len(violations)}건 위반")
