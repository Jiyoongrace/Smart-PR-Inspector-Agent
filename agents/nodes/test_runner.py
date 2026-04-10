"""
AI 시나리오 검증 노드

코드 실행 없이 LLM이 각 시나리오를 코드 변경(diff)과 대조하여 평가합니다.
도메인 전문가가 이해할 수 있는 평문 결과를 제공합니다.
"""

import json
import logging
import re
import time
from typing import List

from agents.state import (
    AgentState,
    NodeStatus,
    ScenarioResult,
    ScenarioVerdict,
    TestResult,
    TestScenario,
)
from config.prompts import SCENARIO_EVALUATION_PROMPT

logger = logging.getLogger(__name__)

# 시나리오당 LLM 호출 타임아웃(초)
EVAL_TIMEOUT = 30
# 통과 기준: 전체의 몇 % 이상이 pass여야 전체 PASS
PASS_THRESHOLD = 0.6


def test_runner_node(state: AgentState) -> AgentState:
    """생성된 시나리오를 AI로 평가하여 ScenarioResult 목록 생성"""
    state.node_status.test_run = NodeStatus.RUNNING

    # 시나리오가 없으면 스킵
    pending: List[TestScenario] = state.pending_scenarios
    if not pending or not state.pr_data:
        state.node_status.test_run = NodeStatus.SKIPPED
        return state

    diff = state.pr_data.diff[:6000]  # LLM 컨텍스트 절약
    start = time.time()

    results: List[ScenarioResult] = []
    for scenario in pending:
        result = _evaluate_scenario(scenario, diff)
        results.append(result)
        logger.debug(
            "시나리오 [%s] %s — %s",
            scenario.id, result.verdict, scenario.title
        )

    duration = round(time.time() - start, 2)

    passed_count = sum(1 for r in results if r.verdict == ScenarioVerdict.PASS)
    failed_count = sum(1 for r in results if r.verdict == ScenarioVerdict.FAIL)
    unclear_count = sum(1 for r in results if r.verdict == ScenarioVerdict.UNCLEAR)
    total = len(results)
    overall_passed = total > 0 and (passed_count / total) >= PASS_THRESHOLD

    state.test_result = TestResult(
        passed=overall_passed,
        verification_mode="ai_scenario",
        total_tests=total,
        passed_tests=passed_count,
        failed_tests=failed_count + unclear_count,
        duration_seconds=duration,
        scenarios=results,
    )

    state.node_status.test_run = (
        NodeStatus.SUCCESS if overall_passed else NodeStatus.FAILED
    )
    logger.info(
        "시나리오 검증 완료: %d/%d 통과, %.1f초",
        passed_count, total, duration,
    )
    return state


def fix_test_code_node(state: AgentState) -> AgentState:
    """AI 시나리오 방식에서는 재시도 불필요 — 노-옵"""
    return state


def should_retry(state: AgentState) -> str:
    """LangGraph conditional edge: 시나리오 방식은 재시도 없이 바로 완료"""
    if not state.test_result:
        return "fail"
    return "success" if state.test_result.passed else "fail"


# ── 내부 함수 ─────────────────────────────────────────────────────────────

def _evaluate_scenario(scenario: TestScenario, diff: str) -> ScenarioResult:
    """LLM 한 번 호출로 시나리오 평가 → ScenarioResult 반환"""
    try:
        from config.llm import call_llm

        prompt = SCENARIO_EVALUATION_PROMPT.substitute(
            diff=diff,
            title=scenario.title,
            given=scenario.given,
            when=scenario.when,
            then=scenario.then,
        )

        raw = call_llm(prompt, max_tokens=512)
        return _parse_evaluation(scenario, raw)

    except Exception as e:
        logger.error("시나리오 [%s] 평가 실패: %s", scenario.id, e)
        return ScenarioResult(
            scenario=scenario,
            verdict=ScenarioVerdict.UNCLEAR,
            reasoning=f"평가 중 오류가 발생했습니다: {e}",
            confidence=0,
        )


def _parse_evaluation(scenario: TestScenario, raw: str) -> ScenarioResult:
    """LLM 응답 JSON 파싱 → ScenarioResult"""
    cleaned = re.sub(r"```(?:json)?\n?", "", raw).strip().rstrip("`")

    match = re.search(r"\{[\s\S]+\}", cleaned)
    if not match:
        return ScenarioResult(
            scenario=scenario,
            verdict=ScenarioVerdict.UNCLEAR,
            reasoning="AI 응답을 파싱할 수 없었습니다.",
            confidence=0,
        )

    try:
        data = json.loads(match.group())
        raw_verdict = str(data.get("verdict", "unclear")).lower()
        verdict_map = {
            "pass": ScenarioVerdict.PASS,
            "fail": ScenarioVerdict.FAIL,
            "unclear": ScenarioVerdict.UNCLEAR,
        }
        verdict = verdict_map.get(raw_verdict, ScenarioVerdict.UNCLEAR)

        return ScenarioResult(
            scenario=scenario,
            verdict=verdict,
            reasoning=data.get("reasoning", ""),
            confidence=int(data.get("confidence", 50)),
        )
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("평가 JSON 디코딩 실패: %s — raw: %s", e, raw[:100])
        return ScenarioResult(
            scenario=scenario,
            verdict=ScenarioVerdict.UNCLEAR,
            reasoning="응답 형식 오류로 판단할 수 없습니다.",
            confidence=0,
        )
