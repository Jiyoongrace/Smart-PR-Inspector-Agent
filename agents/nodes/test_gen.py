"""
AI 시나리오 생성 노드

pytest 코드 대신 도메인 전문가도 이해할 수 있는
Given/When/Then 형식의 테스트 시나리오를 AI로 생성합니다.
"""

import json
import logging
import re
from typing import List

from agents.state import AgentState, NodeStatus, TestResult, TestScenario
from config.prompts import SCENARIO_GENERATION_PROMPT

logger = logging.getLogger(__name__)

# 시나리오 최소/최대 개수
MIN_SCENARIOS = 3
MAX_SCENARIOS = 6


def test_generator_node(state: AgentState) -> AgentState:
    """PR diff를 분석하여 도메인 친화적 테스트 시나리오 생성"""
    state.node_status.test_gen = NodeStatus.RUNNING

    if not state.pr_data or not state.pr_data.diff:
        state.node_status.test_gen = NodeStatus.SKIPPED
        return state

    try:
        scenarios = _generate_scenarios(state)

        if not scenarios:
            logger.warning("시나리오 생성 결과가 없음 — 스킵 처리")
            state.node_status.test_gen = NodeStatus.SKIPPED
            state.test_result = TestResult(
                passed=True,
                verification_mode="ai_scenario",
                total_tests=0,
            )
            return state

        # test_runner가 평가할 수 있도록 TestResult에 시나리오 저장
        state.test_result = TestResult(
            passed=False,  # 아직 평가 전
            verification_mode="ai_scenario",
            total_tests=len(scenarios),
            # ScenarioResult 없이 TestScenario만 임시 저장 (직렬화용)
            # test_runner에서 ScenarioResult로 채워짐
        )
        # 시나리오를 state에 보관 (test_runner에서 사용)
        state.pending_scenarios = scenarios

        state.node_status.test_gen = NodeStatus.SUCCESS
        logger.info(f"시나리오 {len(scenarios)}개 생성 완료")

    except Exception as e:
        logger.error(f"시나리오 생성 실패: {e}")
        state.node_status.test_gen = NodeStatus.FAILED
        state.test_result = TestResult(
            passed=False,
            verification_mode="ai_scenario",
            stderr=str(e),
        )

    return state


def _generate_scenarios(state: AgentState) -> List[TestScenario]:
    """SCENARIO_GENERATION_PROMPT로 LLM 호출 → TestScenario 리스트 반환"""
    from config.llm import call_llm

    pr = state.pr_data
    issue_context = ""
    if pr.linked_issues:
        nums = ", ".join(f"#{n}" for n in pr.linked_issues)
        issue_context = f"이 PR은 이슈 {nums}를 수정합니다. 버그 재현 시나리오도 포함하세요."

    prompt = SCENARIO_GENERATION_PROMPT.substitute(
        pr_title=pr.title,
        pr_body=pr.body[:500] if pr.body else "(없음)",
        diff_snippet=pr.diff[:4000],
        issue_context=issue_context,
    )

    raw = call_llm(prompt, max_tokens=2048)
    return _parse_scenarios(raw)


def _parse_scenarios(raw: str) -> List[TestScenario]:
    """LLM 응답에서 JSON 배열 파싱 → TestScenario 리스트"""
    # 코드블록 제거
    cleaned = re.sub(r"```(?:json)?\n?", "", raw).strip().rstrip("`")

    # JSON 배열 추출
    match = re.search(r"\[[\s\S]+\]", cleaned)
    if not match:
        logger.warning("시나리오 JSON 파싱 실패 — 응답: %s", raw[:200])
        return []

    try:
        data = json.loads(match.group())
    except json.JSONDecodeError as e:
        logger.warning("시나리오 JSON 디코딩 실패: %s", e)
        return []

    scenarios: List[TestScenario] = []
    for item in data[:MAX_SCENARIOS]:
        try:
            scenarios.append(TestScenario(
                id=str(item.get("id", f"s{len(scenarios)+1}")),
                title=item.get("title", ""),
                given=item.get("given", ""),
                when=item.get("when", ""),
                then=item.get("then", ""),
                category=item.get("category", "기능"),
            ))
        except Exception as e:
            logger.debug("시나리오 항목 파싱 오류 — 건너뜀: %s", e)

    return scenarios
