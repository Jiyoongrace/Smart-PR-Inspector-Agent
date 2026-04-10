"""
LangGraph 기반 메인 오케스트레이터
PR 분석 워크플로우 전체를 조율하는 StateGraph

SKILL.md에서 스킬 정의를 로드하여 워크플로우를 구성합니다.

고도화 사항:
- SKILL.md: 선언적 스킬 정의 기반 워크플로우 구성
- 병렬 처리: convention + test_gen을 동시 실행 (Fork/Join)
- HITL: 아키텍처 룰 위반 시 시니어 승인 대기
- 재시도: 테스트 실패 시 최대 3회 자동 수정 재시도
- Hybrid RAG: domain_explain 노드에서 Dense+Sparse+Re-ranking 적용
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

from db.history import save_analysis

from langgraph.graph import END, StateGraph

from agents.nodes import (
    arch_review_node,
    check_arch_approval,
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
from config.skills import get_skill_registry

logger = logging.getLogger(__name__)


def create_workflow():
    """
    LangGraph StateGraph 워크플로우 생성 및 컴파일

    SKILL.md에서 스킬 정의를 로드하여 워크플로우 메타데이터로 활용합니다.
    스킬 레지스트리를 통해 각 노드의 모델, 프롬프트, RAG 설정 등을 조회할 수 있습니다.

    워크플로우 구조:
    fetch → FORK → [convention, test_gen] → JOIN
         → arch_review → (HITL 분기)
         → test_run → (재시도 분기) → impact
         → domain_explain (Hybrid RAG) → doc_sync
         → comment → slack → END
    """
    # SKILL.md 로드 — 스킬 메타데이터 참조용
    registry = get_skill_registry()
    logger.info(
        f"SKILL.md 기반 워크플로우 구성: "
        f"{len(registry.skills)}개 스킬 로드, "
        f"병렬 그룹: {registry.get_parallel_skills()}, "
        f"HITL 스킬: {[s.id for s in registry.get_hitl_skills()]}"
    )

    workflow = StateGraph(AgentState)

    # ── 노드 등록 ──────────────────────────────────────────────
    workflow.add_node("fetch", fetch_pr_data_node)

    # 병렬 실행 노드 (Fork/Join)
    workflow.add_node("convention", convention_check_node)
    workflow.add_node("test_gen", test_generator_node)

    # HITL: 아키텍처 룰 점검 + 승인 대기
    workflow.add_node("arch_review", arch_review_node)

    # 테스트 실행 + 재시도
    workflow.add_node("test_run", test_runner_node)
    workflow.add_node("fix_test", fix_test_code_node)

    # 후속 분석
    workflow.add_node("impact", impact_analysis_node)
    workflow.add_node("domain_explain", domain_explainer_node)
    workflow.add_node("doc_sync", doc_sync_check_node)
    workflow.add_node("comment", generate_comment_node)
    workflow.add_node("slack", slack_notify_node)

    # ── 엣지 연결 ──────────────────────────────────────────────

    # 1. 시작점
    workflow.set_entry_point("fetch")

    # 2. fetch → convention → test_gen → arch_review (순차 실행)
    #    NOTE: Pydantic BaseModel 기반 State는 동시 업데이트 불가
    #    병렬 실행을 위해서는 TypedDict + Annotated 리듀서 전환 필요
    #    SKILL.md에 parallel_group: analysis_fork로 선언되어 향후 전환 대비
    workflow.add_edge("fetch", "convention")
    workflow.add_edge("convention", "test_gen")

    # 3. test_gen → arch_review (HITL 점검)
    workflow.add_edge("test_gen", "arch_review")

    # 4. 아키텍처 룰 점검 결과에 따른 분기 (HITL)
    workflow.add_conditional_edges(
        "arch_review",
        check_arch_approval,
        {
            "approved": "test_run",   # 위반 없음 or 승인 → 테스트 진행
            "rejected": "comment",    # 반려 → PR 반려 코멘트 작성
        },
    )

    # 5. test_run → 재시도 / 성공 / 실패 분기
    workflow.add_conditional_edges(
        "test_run",
        should_retry,
        {
            "retry": "fix_test",      # 실패 + 재시도 가능 → 코드 수정
            "success": "impact",      # 성공 → 영향도 분석
            "fail": "impact",         # 실패 (3회 초과) → 분석 계속
        },
    )
    workflow.add_edge("fix_test", "test_run")  # 재시도 루프

    # 6. 후속 분석 체인
    #    impact → domain_explain (Hybrid RAG) → doc_sync → comment → slack → END
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

                    # HITL 대기 상태인 경우 특별 이벤트 발행
                    event_type = "node_complete"
                    extra = {}
                    if (
                        node_name == "arch_review"
                        and state.arch_review
                        and state.arch_review.has_violation
                    ):
                        event_type = "hitl_pending"
                        extra = {
                            "violations": state.arch_review.violations,
                            "approval_status": state.arch_review.approval_status,
                        }

                    yield {
                        "type": event_type,
                        "node": node_name,
                        "status": state.node_status.model_dump(),
                        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                        **extra,
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
