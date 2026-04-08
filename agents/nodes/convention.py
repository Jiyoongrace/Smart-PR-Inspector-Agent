"""
컨벤션 검증 노드
AST 기반 빠른 분석 + LLM 보조 심층 분석
"""

import ast
import json
import logging
import os
import re
from pathlib import Path
from typing import List

import yaml

from agents.state import (
    AgentState,
    ConventionResult,
    ConventionViolation,
    NodeStatus,
)

logger = logging.getLogger(__name__)

# 컨벤션 룰북 경로
CONVENTIONS_PATH = Path(__file__).parent.parent.parent / "config" / "conventions.yaml"


def convention_check_node(state: AgentState) -> AgentState:
    """AST + LLM 하이브리드 컨벤션 검증"""
    state.node_status.convention = NodeStatus.RUNNING

    if not state.pr_data:
        state.node_status.convention = NodeStatus.SKIPPED
        return state

    violations: List[ConventionViolation] = []

    # 1. AST 기반 정적 분석 (빠름, 무료)
    violations.extend(_ast_check(state.pr_data.diff, state.pr_data.changed_files))

    # 2. LLM 보조 분석 (복잡한 패턴, 가독성)
    if len(state.pr_data.diff) < 8000:
        violations.extend(_llm_check(state.pr_data.diff))

    # 심각도 분류
    errors = [v for v in violations if v.severity == "error"]

    state.convention_result = ConventionResult(
        passed=len(errors) == 0,
        violations=violations,
        summary=_make_summary(violations),
    )

    state.node_status.convention = NodeStatus.SUCCESS
    logger.info(
        f"컨벤션 검증 완료: {len(violations)}건 위반 "
        f"(에러 {len(errors)}건)"
    )
    return state


def _ast_check(diff: str, changed_files: List[str]) -> List[ConventionViolation]:
    """AST 파서로 Python 파일 정적 분석"""
    violations = []
    # diff에서 Python 코드 블록 추출 (+로 시작하는 라인)
    python_blocks = _extract_python_from_diff(diff)

    for file_path, code_lines in python_blocks.items():
        code = "\n".join(code_lines)
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            violations.append(ConventionViolation(
                file=file_path,
                line=e.lineno or 0,
                rule="syntax_error",
                message=f"구문 오류: {e.msg}",
                severity="error",
            ))
            continue

        violations.extend(_check_naming(tree, file_path))
        violations.extend(_check_type_hints(tree, file_path))
        violations.extend(_check_magic_numbers(tree, file_path))
        violations.extend(_check_bare_except(tree, file_path))
        violations.extend(_check_function_length(tree, file_path))

    return violations


def _extract_python_from_diff(diff: str) -> dict:
    """diff에서 파일별 추가된 Python 코드 추출"""
    result = {}
    current_file = None
    current_lines = []
    line_offset = 0

    for line in diff.split("\n"):
        if line.startswith("--- a/") or line.startswith("+++ b/"):
            if line.startswith("+++ b/"):
                file_path = line[6:]
                if file_path.endswith(".py"):
                    if current_file and current_lines:
                        result[current_file] = current_lines
                    current_file = file_path
                    current_lines = []
                    line_offset = 0
            continue

        if line.startswith("@@"):
            # @@ -a,b +c,d @@
            match = re.search(r"\+(\d+)", line)
            if match:
                line_offset = int(match.group(1)) - 1
            continue

        if current_file:
            if line.startswith("+") and not line.startswith("+++"):
                current_lines.append(line[1:])
            elif not line.startswith("-"):
                current_lines.append(line)

    if current_file and current_lines:
        result[current_file] = current_lines

    return result


def _check_naming(tree: ast.AST, file_path: str) -> List[ConventionViolation]:
    """함수명/변수명 snake_case 검증"""
    violations = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if not _is_snake_case(node.name) and not node.name.startswith("__"):
                violations.append(ConventionViolation(
                    file=file_path,
                    line=node.lineno,
                    rule="naming_snake_case",
                    message=f"함수명 `{node.name}`은 snake_case를 사용해야 합니다",
                    suggestion=f"`{_to_snake_case(node.name)}`으로 변경",
                    severity="warning",
                ))

        elif isinstance(node, ast.ClassDef):
            if not _is_pascal_case(node.name):
                violations.append(ConventionViolation(
                    file=file_path,
                    line=node.lineno,
                    rule="naming_pascal_case",
                    message=f"클래스명 `{node.name}`은 PascalCase를 사용해야 합니다",
                    severity="warning",
                ))

    return violations


def _check_type_hints(tree: ast.AST, file_path: str) -> List[ConventionViolation]:
    """타입 힌트 누락 검증"""
    violations = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            # 매개변수 타입 힌트 체크
            missing_hints = [
                arg.arg for arg in node.args.args
                if arg.annotation is None and arg.arg != "self"
            ]
            if missing_hints:
                violations.append(ConventionViolation(
                    file=file_path,
                    line=node.lineno,
                    rule="type_hints_missing",
                    message=f"함수 `{node.name}`의 파라미터 타입 힌트 누락: {missing_hints}",
                    severity="info",
                ))

            # 반환 타입 힌트 체크
            if node.returns is None and node.name not in ("__init__", "__str__", "__repr__"):
                violations.append(ConventionViolation(
                    file=file_path,
                    line=node.lineno,
                    rule="return_type_missing",
                    message=f"함수 `{node.name}`의 반환 타입 힌트 누락",
                    severity="info",
                ))

    return violations


def _check_magic_numbers(tree: ast.AST, file_path: str) -> List[ConventionViolation]:
    """매직 넘버 검사"""
    violations = []
    allowed_values = {0, 1, -1, 2, 100}  # 허용되는 리터럴 숫자

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            if node.value not in allowed_values and abs(node.value) > 1:
                violations.append(ConventionViolation(
                    file=file_path,
                    line=getattr(node, "lineno", 0),
                    rule="magic_number",
                    message=f"매직 넘버 `{node.value}` 발견 → 상수로 분리 권장",
                    severity="info",
                ))

    return violations


def _check_bare_except(tree: ast.AST, file_path: str) -> List[ConventionViolation]:
    """bare except 사용 금지 검사"""
    violations = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                violations.append(ConventionViolation(
                    file=file_path,
                    line=node.lineno,
                    rule="bare_except",
                    message="bare `except:` 사용 금지 → 구체적인 예외 클래스 지정",
                    suggestion="`except Exception as e:` 또는 구체적 예외 사용",
                    severity="error",
                ))

    return violations


def _check_function_length(tree: ast.AST, file_path: str) -> List[ConventionViolation]:
    """함수 길이 검사 (50줄 초과 시 경고)"""
    violations = []
    MAX_LINES = 50

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            length = node.end_lineno - node.lineno if hasattr(node, "end_lineno") else 0
            if length > MAX_LINES:
                violations.append(ConventionViolation(
                    file=file_path,
                    line=node.lineno,
                    rule="function_too_long",
                    message=f"함수 `{node.name}`이 {length}줄로 너무 깁니다 (권장: {MAX_LINES}줄 이하)",
                    suggestion="함수를 작은 단위로 분리하세요",
                    severity="warning",
                ))

    return violations


def _llm_check(diff: str) -> List[ConventionViolation]:
    """LLM 보조 컨벤션 분석 (복잡한 패턴)"""
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        rules = _load_conventions()
        prompt = f"""다음 코드 Diff를 분석하여 컨벤션 위반 사항을 JSON 배열로 반환하세요.

컨벤션 규칙:
{yaml.dump(rules, allow_unicode=True)}

코드 Diff:
{diff[:4000]}

반환 형식 (JSON 배열만 출력):
[
  {{"file": "path/to/file.py", "line": 42, "rule": "규칙명", "message": "설명", "severity": "warning"}}
]

위반 사항이 없으면 빈 배열 []을 반환하세요."""

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        content = message.content[0].text.strip()
        # JSON 추출
        json_match = re.search(r"\[.*\]", content, re.DOTALL)
        if json_match:
            raw = json.loads(json_match.group())
            return [
                ConventionViolation(
                    file=item.get("file", "unknown"),
                    line=item.get("line", 0),
                    rule=item.get("rule", "llm_check"),
                    message=item.get("message", ""),
                    severity=item.get("severity", "warning"),
                )
                for item in raw
            ]

    except Exception as e:
        logger.warning(f"LLM 컨벤션 체크 실패 (무시): {e}")

    return []


def _load_conventions() -> dict:
    """conventions.yaml 룰북 로드"""
    if CONVENTIONS_PATH.exists():
        with open(CONVENTIONS_PATH) as f:
            return yaml.safe_load(f) or {}
    return {}


def _make_summary(violations: List[ConventionViolation]) -> str:
    errors = sum(1 for v in violations if v.severity == "error")
    warnings = sum(1 for v in violations if v.severity == "warning")
    infos = sum(1 for v in violations if v.severity == "info")
    return f"오류 {errors}건, 경고 {warnings}건, 정보 {infos}건"


def _is_snake_case(name: str) -> bool:
    return bool(re.match(r"^[a-z][a-z0-9_]*$", name))


def _is_pascal_case(name: str) -> bool:
    return bool(re.match(r"^[A-Z][a-zA-Z0-9]*$", name))


def _to_snake_case(name: str) -> str:
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    return s.lower()
