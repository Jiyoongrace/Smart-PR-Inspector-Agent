"""
API 문서 동기화 노드
FastAPI 엔드포인트 변경 감지 → Swagger/README 업데이트 제안
"""

import ast
import logging
import os
import re
from typing import Dict, List, Optional

import yaml

from agents.state import AgentState, NodeStatus

logger = logging.getLogger(__name__)


def doc_sync_check_node(state: AgentState) -> AgentState:
    """API 스펙 변경 감지 및 문서 업데이트 초안 생성"""
    state.node_status.doc_sync = NodeStatus.RUNNING

    if not state.pr_data:
        state.node_status.doc_sync = NodeStatus.SKIPPED
        return state

    # API 파일 변경 여부 확인
    api_files = [
        f for f in state.pr_data.changed_files
        if f.endswith(".py") and any(p in f for p in ["api", "router", "endpoint", "view"])
    ]

    if not api_files and not (state.impact_analysis and state.impact_analysis.has_api_changes):
        state.doc_updates = None
        state.node_status.doc_sync = NodeStatus.SKIPPED
        logger.info("API 변경 없음 - 문서 동기화 스킵")
        return state

    # diff에서 API 변경 추출
    api_changes = _extract_api_changes_from_diff(state.pr_data.diff)

    if not api_changes:
        state.doc_updates = None
        state.node_status.doc_sync = NodeStatus.SKIPPED
        return state

    # 기존 Swagger 비교
    current_swagger = _load_existing_swagger()

    # 변경사항 분석
    updates = _analyze_swagger_changes(api_changes, current_swagger)

    if updates:
        # LLM으로 업데이트 초안 생성
        draft = _generate_update_draft(api_changes, updates)
        state.doc_updates = draft
    else:
        state.doc_updates = None

    state.node_status.doc_sync = NodeStatus.SUCCESS
    logger.info(f"문서 동기화 체크 완료: {len(updates)}건 업데이트 필요")
    return state


def _extract_api_changes_from_diff(diff: str) -> List[Dict]:
    """diff에서 FastAPI/Flask 엔드포인트 변경 추출"""
    changes = []
    current_file = None

    lines = diff.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("+++ b/"):
            current_file = line[6:]
            continue

        if not current_file or not current_file.endswith(".py"):
            continue

        if line.startswith("+") and not line.startswith("+++"):
            code = line[1:]

            # FastAPI/Flask 라우트 데코레이터 감지
            route_match = re.search(
                r"@(?:app|router|blueprint)\.(get|post|put|delete|patch)\(['\"]([^'\"]+)['\"]",
                code,
            )
            if route_match:
                # 다음 몇 줄에서 함수 시그니처 찾기
                func_sig = ""
                for next_line in lines[i+1:i+5]:
                    if next_line.startswith("+") and "def " in next_line:
                        func_sig = next_line[1:].strip()
                        break

                changes.append({
                    "method": route_match.group(1).upper(),
                    "path": route_match.group(2),
                    "file": current_file,
                    "function_sig": func_sig,
                    "is_new": True,  # 추가된 라인이므로
                })

    return changes


def _load_existing_swagger() -> Dict:
    """기존 swagger.yaml / openapi.json 로드"""
    swagger_paths = [
        "swagger.yaml",
        "openapi.yaml",
        "openapi.json",
        "docs/swagger.yaml",
        "docs/openapi.yaml",
    ]

    for path in swagger_paths:
        try:
            with open(path, "r") as f:
                if path.endswith(".json"):
                    import json
                    return json.load(f)
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            continue

    return {"paths": {}}


def _analyze_swagger_changes(
    api_changes: List[Dict],
    current_swagger: Dict,
) -> List[str]:
    """API 변경사항과 기존 Swagger 비교"""
    updates = []
    existing_paths = current_swagger.get("paths", {})

    for change in api_changes:
        path = change["path"]
        method = change["method"].lower()

        if path not in existing_paths:
            updates.append(f"🆕 신규 엔드포인트: {change['method']} {path}")
        elif method not in existing_paths.get(path, {}):
            updates.append(f"🆕 신규 메서드: {change['method']} {path}")
        else:
            updates.append(f"📝 기존 엔드포인트 변경: {change['method']} {path}")

    return updates


def _generate_update_draft(
    api_changes: List[Dict],
    updates: List[str],
) -> str:
    """LLM으로 Swagger 업데이트 초안 생성"""
    try:
        from config.llm import call_llm

        changes_text = "\n".join([
            f"- {c['method']} {c['path']}: {c.get('function_sig', '')}"
            for c in api_changes
        ])

        prompt = f"""다음 API 변경사항에 대한 Swagger/OpenAPI 문서 업데이트 초안을 YAML 형식으로 작성하세요.

감지된 변경:
{changes_text}

필요한 업데이트:
{chr(10).join(updates)}

간결하게 핵심만 작성하고, 실제 Swagger 경로 정의 형식으로 출력하세요."""

        draft = call_llm(prompt, max_tokens=1024)

        header = "### 📄 Swagger/OpenAPI 업데이트 필요\n\n"
        header += "\n".join(f"- {u}" for u in updates)
        header += "\n\n**제안된 변경사항:**\n```yaml\n"
        header += draft
        header += "\n```"

        return header

    except Exception as e:
        logger.warning(f"Swagger 초안 생성 실패: {e}")
        return "### 📄 Swagger 업데이트 필요\n\n" + "\n".join(f"- {u}" for u in updates)
