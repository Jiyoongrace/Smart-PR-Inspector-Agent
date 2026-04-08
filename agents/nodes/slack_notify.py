"""
Slack 알림 노드
Block Kit 인터랙티브 메시지로 PR 승인 워크플로우 제공
"""

import logging
import os
from typing import List

from agents.state import AgentState, NodeStatus

logger = logging.getLogger(__name__)


def slack_notify_node(state: AgentState) -> AgentState:
    """PR 분석 결과를 Slack에 인터랙티브 메시지로 전송"""
    state.node_status.slack = NodeStatus.RUNNING

    token = os.getenv("SLACK_BOT_TOKEN")
    channel = os.getenv("SLACK_CHANNEL", "#code-review")

    if not token:
        logger.info("SLACK_BOT_TOKEN 미설정 - Slack 알림 스킵")
        state.node_status.slack = NodeStatus.SKIPPED
        return state

    if not state.pr_data:
        state.node_status.slack = NodeStatus.SKIPPED
        return state

    try:
        from slack_sdk import WebClient

        client = WebClient(token=token)
        blocks = _build_blocks(state)

        response = client.chat_postMessage(
            channel=channel,
            text=f"🤖 PR #{state.pr_data.pr_number} 분석 완료: {state.pr_data.title}",
            blocks=blocks,
        )

        state.slack_thread_id = response["ts"]
        state.node_status.slack = NodeStatus.SUCCESS
        logger.info(f"Slack 알림 전송 완료 (thread: {state.slack_thread_id})")

    except Exception as e:
        logger.error(f"Slack 알림 실패: {e}")
        state.node_status.slack = NodeStatus.FAILED

    return state


def _build_blocks(state: AgentState) -> List[dict]:
    """Slack Block Kit 메시지 구성"""
    pr = state.pr_data

    # 상태 아이콘
    convention_icon = "✅" if (state.convention_result and state.convention_result.passed) else "❌"
    test_icon = "✅" if (state.test_result and state.test_result.passed) else "❌"

    risk = "unknown"
    risk_icon = "⚪"
    if state.impact_analysis:
        risk = state.impact_analysis.risk_level
        risk_icons = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}
        risk_icon = risk_icons.get(risk, "⚪")

    # 테스트 통계
    test_stats = ""
    if state.test_result and state.test_result.total_tests > 0:
        test_stats = f"{state.test_result.passed_tests}/{state.test_result.total_tests}"
    else:
        test_stats = "N/A"

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🤖 Smart PR Inspector 분석 완료",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*<{pr.pr_url}|PR #{pr.pr_number}: {pr.title}>*\n작성자: `{pr.author}` | 브랜치: `{pr.head_branch}` → `{pr.base_branch}`",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"{convention_icon} *컨벤션*\n{'통과' if state.convention_result and state.convention_result.passed else '위반 발견'}"},
                {"type": "mrkdwn", "text": f"{test_icon} *테스트*\n{test_stats} 통과"},
                {"type": "mrkdwn", "text": f"{risk_icon} *리스크*\n{risk.upper()}"},
                {"type": "mrkdwn", "text": f"{'⚠️' if state.impact_analysis and state.impact_analysis.has_api_changes else '✓'} *API 변경*\n{'감지됨' if state.impact_analysis and state.impact_analysis.has_api_changes else '없음'}"},
            ],
        },
    ]

    # 도메인 설명 (있을 경우)
    if state.domain_explanation:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"📖 *비즈니스 영향도*\n{state.domain_explanation[:200]}...",
            },
        })

    blocks.append({"type": "divider"})

    # 인터랙티브 버튼
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "✅ 승인"},
                "style": "primary",
                "action_id": "approve_pr",
                "value": str(pr.pr_number),
                "confirm": {
                    "title": {"type": "plain_text", "text": "PR 승인"},
                    "text": {"type": "plain_text", "text": f"PR #{pr.pr_number}을 승인하시겠습니까?"},
                    "confirm": {"type": "plain_text", "text": "승인"},
                    "deny": {"type": "plain_text", "text": "취소"},
                },
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "🔄 수정 요청"},
                "style": "danger",
                "action_id": "request_changes",
                "value": str(pr.pr_number),
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "📋 상세 보기"},
                "action_id": "view_details",
                "url": pr.pr_url,
            },
        ],
    })

    return blocks
