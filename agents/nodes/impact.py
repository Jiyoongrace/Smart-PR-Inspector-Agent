"""
코드 영향도 분석 노드
AST 기반 정적 분석으로 변경 함수의 의존성 추적
"""

import ast
import logging
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

from agents.state import AgentState, ImpactAnalysis, NodeStatus

logger = logging.getLogger(__name__)


def impact_analysis_node(state: AgentState) -> AgentState:
    """변경된 함수가 영향을 주는 모듈 추적"""
    state.node_status.impact = NodeStatus.RUNNING

    if not state.pr_data:
        state.node_status.impact = NodeStatus.SKIPPED
        return state

    # 변경된 함수명 추출
    changed_functions = _extract_changed_function_names(state.pr_data.diff)
    changed_files = set(state.pr_data.changed_files)

    # API 변경 감지 (FastAPI/Flask 데코레이터)
    has_api_changes = _detect_api_changes(state.pr_data.diff)

    # 현재 작업 디렉토리에서 호출 그래프 생성
    project_root = _find_project_root()
    affected_modules = []
    call_chain = []

    if project_root and changed_functions:
        call_graph = _build_call_graph(project_root)
        affected = _find_affected_modules(changed_functions, call_graph, project_root)
        affected_modules = [
            {
                "module": mod["file"],
                "function": mod["caller"],
                "line": mod["line"],
                "call_chain": mod.get("chain", []),
            }
            for mod in affected
        ]

    # 리스크 레벨 판정
    risk_level = _assess_risk(
        affected_count=len(affected_modules),
        has_api_changes=has_api_changes,
        changed_files=list(changed_files),
    )

    state.impact_analysis = ImpactAnalysis(
        changed_functions=changed_functions,
        affected_modules=affected_modules,
        has_api_changes=has_api_changes,
        call_chain=call_chain,
        risk_level=risk_level,
    )

    state.node_status.impact = NodeStatus.SUCCESS
    logger.info(
        f"영향도 분석 완료: {len(changed_functions)}개 함수 변경, "
        f"{len(affected_modules)}개 모듈 영향, 리스크 {risk_level}"
    )
    return state


def _extract_changed_function_names(diff: str) -> List[str]:
    """diff에서 변경된 함수명 추출"""
    functions = []
    for line in diff.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            # def 함수 정의 라인
            match = re.search(r"def\s+(\w+)\s*\(", line)
            if match:
                func_name = match.group(1)
                if func_name not in functions:
                    functions.append(func_name)
    return functions


def _detect_api_changes(diff: str) -> bool:
    """FastAPI/Flask API 엔드포인트 변경 감지"""
    api_patterns = [
        r"@app\.(get|post|put|delete|patch)\(",
        r"@router\.(get|post|put|delete|patch)\(",
        r"@blueprint\.(route|get|post|put|delete)\(",
    ]
    for line in diff.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            for pattern in api_patterns:
                if re.search(pattern, line):
                    return True
    return False


def _find_project_root() -> Path | None:
    """프로젝트 루트 디렉토리 찾기"""
    cwd = Path.cwd()
    markers = ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"]

    for path in [cwd] + list(cwd.parents):
        if any((path / m).exists() for m in markers):
            return path
        if path == path.parent:
            break

    return cwd  # 현재 디렉토리 반환


def _build_call_graph(project_root: Path) -> Dict[str, List[dict]]:
    """
    프로젝트 내 Python 파일을 AST 파싱하여 함수 호출 그래프 생성
    Returns: {함수명: [{caller, file, line}]}
    """
    call_graph: Dict[str, List[dict]] = defaultdict(list)

    py_files = list(project_root.rglob("*.py"))[:100]  # 최대 100개 파일

    for py_file in py_files:
        if any(part.startswith(".") for part in py_file.parts):
            continue  # 숨김 디렉토리 스킵
        if "venv" in str(py_file) or "node_modules" in str(py_file):
            continue

        try:
            with open(py_file, "r", encoding="utf-8", errors="ignore") as f:
                source = f.read()

            tree = ast.parse(source, filename=str(py_file))
            relative_path = str(py_file.relative_to(project_root))

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    caller_name = node.name
                    # 이 함수가 호출하는 함수들 추적
                    for child in ast.walk(node):
                        if isinstance(child, ast.Call):
                            callee_name = _get_call_name(child)
                            if callee_name:
                                call_graph[callee_name].append({
                                    "caller": caller_name,
                                    "file": relative_path,
                                    "line": child.lineno,
                                })

        except Exception:
            continue

    return dict(call_graph)


def _get_call_name(call_node: ast.Call) -> str | None:
    """AST Call 노드에서 함수명 추출"""
    if isinstance(call_node.func, ast.Name):
        return call_node.func.id
    elif isinstance(call_node.func, ast.Attribute):
        return call_node.func.attr
    return None


def _find_affected_modules(
    changed_functions: List[str],
    call_graph: Dict[str, List[dict]],
    project_root: Path,
    max_depth: int = 3,
) -> List[dict]:
    """변경된 함수를 호출하는 모듈 BFS 탐색"""
    affected = []
    visited: Set[str] = set()

    queue = [(func, [], 0) for func in changed_functions]

    while queue:
        current_func, chain, depth = queue.pop(0)

        if current_func in visited or depth > max_depth:
            continue
        visited.add(current_func)

        callers = call_graph.get(current_func, [])
        for caller_info in callers[:10]:  # 최대 10개 호출자
            entry = {
                **caller_info,
                "chain": chain + [current_func],
            }
            affected.append(entry)

            if depth < max_depth:
                queue.append((caller_info["caller"], chain + [current_func], depth + 1))

    return affected[:20]  # 최대 20개


def _assess_risk(
    affected_count: int,
    has_api_changes: bool,
    changed_files: List[str],
) -> str:
    """리스크 레벨 판정"""
    score = 0

    score += min(affected_count * 2, 10)

    if has_api_changes:
        score += 5

    # 핵심 파일 변경 여부
    critical_patterns = ["auth", "payment", "security", "database", "migration"]
    for f in changed_files:
        if any(p in f.lower() for p in critical_patterns):
            score += 3

    if score >= 15:
        return "critical"
    elif score >= 8:
        return "high"
    elif score >= 4:
        return "medium"
    return "low"
