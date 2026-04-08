"""
LangGraph 기반 메인 오케스트레이터
PR 분석 워크플로우 전체를 조율하는 StateGraph
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

from db.history import save_analysis

from langgraph.graph import END, StateGraph

from agents.nodes import (
    convention_check_node,
    doc_sync_check_node,
    domain_explainer_node,
    fetch_pr_data_node,
    fix_test_code_node,
    generate_comment_node,
    impact_analysis_node,
    should_retry,
    slack_notify_node,
    test_generator_node,
    test_runner_node,
)
from agents.state import AgentState, NodeStatus, PRData

logger = logging.getLogger(__name__)


def create_workflow():
    """LangGraph StateGraph 워크플로우 생성 및 컴파일"""
    workflow = StateGraph(AgentState)

    # ── 노드 등록 ──────────────────────────────────────────────
    workflow.add_node("fetch", fetch_pr_data_node)
    workflow.add_node("convention", convention_check_node)
    workflow.add_node("test_gen", test_generator_node)
    workflow.add_node("test_run", test_runner_node)
    workflow.add_node("fix_test", fix_test_code_node)
    workflow.add_node("impact", impact_analysis_node)
    workflow.add_node("domain_explain", domain_explainer_node)
    workflow.add_node("doc_sync", doc_sync_check_node)
    workflow.add_node("comment", generate_comment_node)
    workflow.add_node("slack", slack_notify_node)

    # ── 엣지 연결 ──────────────────────────────────────────────
    # 순차 실행: 병렬 실행 시 동일 state key 동시 업데이트 오류 방지
    workflow.set_entry_point("fetch")

    # fetch → convention → test_gen (순차)
    workflow.add_edge("fetch", "convention")
    workflow.add_edge("convention", "test_gen")

    # test_gen → test_run
    workflow.add_edge("test_gen", "test_run")

    # test_run → 재시도 / 성공 / 실패 분기
    workflow.add_conditional_edges(
        "test_run",
        should_retry,
        {
            "retry": "fix_test",
            "success": "impact",
            "fail": "impact",  # 테스트 실패해도 나머지 분석 수행
        },
    )
    workflow.add_edge("fix_test", "test_run")

    # impact → domain_explain → doc_sync → comment → slack → END
    workflow.add_edge("impact", "domain_explain")
    workflow.add_edge("domain_explain", "doc_sync")
    workflow.add_edge("doc_sync", "comment")
    workflow.add_edge("comment", "slack")
    workflow.add_edge("slack", END)

    return workflow.compile()


# 싱글턴 워크플로우 인스턴스
_compiled_workflow = None


def get_workflow():
    global _compiled_workflow
    if _compiled_workflow is None:
        _compiled_workflow = create_workflow()
    return _compiled_workflow


async def run_pr_analysis(
    pr_number: int,
    repo: str,
    progress_callback=None,
) -> AgentState:
    """
    PR 분석 실행 진입점

    Args:
        pr_number: GitHub PR 번호
        repo: "owner/repo" 형식
        progress_callback: 노드 완료 시 호출되는 콜백 (비동기)

    Returns:
        완료된 AgentState
    """
    workflow = get_workflow()

    initial_state = AgentState(
        pr_data=PRData(
            pr_number=pr_number,
            repo=repo,
            author="",
            title="",
        ),
        started_at=datetime.now(tz=timezone.utc).isoformat(),
    )

    logger.info(f"PR #{pr_number} 분석 시작 (repo: {repo})")

    # LangGraph 비동기 스트리밍 실행
    final_state = initial_state
    async for event in workflow.astream(initial_state):
        for node_name, node_output in event.items():
            if isinstance(node_output, AgentState):
                final_state = node_output
                if progress_callback:
                    await progress_callback(node_name, node_output)
                logger.info(f"노드 완료: {node_name}")

    final_state.completed_at = datetime.now(tz=timezone.utc).isoformat()
    logger.info(f"PR #{pr_number} 분석 완료")
    return final_state


async def run_pr_analysis_stream(
    pr_number: int,
    repo: str,
) -> AsyncGenerator[dict, None]:
    """
    SSE 스트리밍용 분석 실행
    각 노드 완료 시 이벤트를 yield
    """
    workflow = get_workflow()

    initial_state = AgentState(
        pr_data=PRData(
            pr_number=pr_number,
            repo=repo,
            author="",
            title="",
        ),
        started_at=datetime.now(tz=timezone.utc).isoformat(),
    )

    yield {
        "type": "start",
        "pr_number": pr_number,
        "repo": repo,
        "timestamp": initial_state.started_at,
    }

    final_state = initial_state  # 최신 상태 추적

    try:
        async for event in workflow.astream(initial_state):
            for node_name, node_output in event.items():
                # LangGraph는 Pydantic 모델 또는 dict로 반환할 수 있음
                state: Optional[AgentState] = None
                if isinstance(node_output, AgentState):
                    state = node_output
                elif isinstance(node_output, dict):
                    try:
                        state = AgentState(**node_output)
                    except Exception:
                        pass

                if state:
                    final_state = state
                    yield {
                        "type": "node_complete",
                        "node": node_name,
                        "status": state.node_status.model_dump(),
                        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    }

        final_state.completed_at = datetime.now(tz=timezone.utc).isoformat()
        state_dict = final_state.model_dump(mode="json")

        # DB에 분석 이력 저장 (별도 스레드에서 실행)
        try:
            await asyncio.to_thread(save_analysis, state_dict)
        except Exception as db_err:
            logger.warning(f"DB 저장 실패 (무시): {db_err}")

        yield {
            "type": "complete",
            # 최종 분석 결과 전체를 포함 (프론트엔드에서 바로 사용)
            "state": state_dict,
            "timestamp": final_state.completed_at,
        }

    except Exception as e:
        logger.error(f"워크플로우 실행 오류: {e}")
        yield {
            "type": "error",
            "message": str(e),
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
