"""
Slack 알림 노드
Incoming Webhook URL (우선) 또는 Bot Token으로 PR 분석 결과 전송
"""

import json
import logging
import os
import urllib.request
from typing import List, Optional

from agents.state import AgentState, NodeStatus

logger = logging.getLogger(__name__)


def slack_notify_node(state: AgentState) -> AgentState:
    """PR 분석 결과를 Slack에 전송"""
    state.node_status.slack = NodeStatus.RUNNING

    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")
    bot_token = os.getenv("SLACK_BOT_TOKEN", "")

    if not webhook_url and not bot_token:
        logger.info("SLACK_WEBHOOK_URL / SLACK_BOT_TOKEN 미설정 — Slack 알림 스킵")
        state.node_status.slack = NodeStatus.SKIPPED
        return state

    if not state.pr_data:
        state.node_status.slack = NodeStatus.SKIPPED
        return state

    blocks = _build_blocks(state)
    text = f"🤖 PR #{state.pr_data.pr_number} 분석 완료: {state.pr_data.title}"

    try:
        if bot_token:
            # ── 방법 A: Bot Token (인터랙티브 버튼 처리 가능) ────────────
            channel = os.getenv("SLACK_CHANNEL", "#pull-requests")
            thread_ts = _send_via_bot(bot_token, channel, text, blocks)
        elif webhook_url:
            # ── 방법 B: Incoming Webhook (버튼 클릭 불가) ────────────────
            thread_ts = _send_via_webhook(webhook_url, text, blocks)

        state.slack_thread_id = thread_ts or "sent"
        state.node_status.slack = NodeStatus.SUCCESS
        logger.info(f"Slack 알림 전송 완료 (thread: {state.slack_thread_id})")

    except Exception as e:
        logger.error(f"Slack 알림 실패: {e}")
        state.node_status.slack = NodeStatus.FAILED

    return state


# ── 전송 방법 ──────────────────────────────────────────────────────────────

def _send_via_webhook(webhook_url: str, text: str, blocks: List[dict]) -> Optional[str]:
    """Incoming Webhook으로 메시지 전송 (urllib 사용 — 의존성 없음)"""
    payload = json.dumps({"text": text, "blocks": blocks}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode()
        if body != "ok":
            raise ValueError(f"Webhook 응답 오류: {body}")
    logger.info("Incoming Webhook 전송 성공")
    return None  # webhook은 thread_ts 반환 안 함


def _send_via_bot(token: str, channel: str, text: str, blocks: List[dict]) -> Optional[str]:
    """Bot Token으로 메시지 전송"""
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError

    client = WebClient(token=token)
    ch = _resolve_channel(client, channel)

    try:
        resp = client.chat_postMessage(channel=ch, text=text, blocks=blocks)
        return resp.get("ts")
    except SlackApiError as e:
        err = e.response["error"]

        if err == "not_in_channel":
            # 1차: channels:join 스코프로 자동 참가 시도
            try:
                client.conversations_join(channel=ch)
                resp = client.chat_postMessage(channel=ch, text=text, blocks=blocks)
                return resp.get("ts")
            except SlackApiError:
                pass

            # 2차: chat:write.public 스코프로 직접 전송 시도 (멤버십 불필요)
            try:
                resp = client.chat_postMessage(
                    channel=ch, text=text, blocks=blocks,
                    # 이 플래그가 없어도 chat:write.public 스코프면 동작
                )
                return resp.get("ts")
            except SlackApiError:
                pass

            raise SlackApiError(
                message=(
                    f"봇이 채널 '{channel}'에 없습니다. "
                    f"Slack에서 `/invite @{_get_bot_name(client)}` 명령으로 봇을 초대하거나 "
                    f"SLACK_WEBHOOK_URL을 .env에 설정하세요."
                ),
                response=e.response,
            )
        raise


def _get_bot_name(client) -> str:
    """봇 이름 조회"""
    try:
        return client.auth_test()["user"]
    except Exception:
        return "smart_pr_inspector_ag"


def _resolve_channel(client, channel: str) -> str:
    """채널명 → 채널 ID 변환 (이미 ID면 그대로 반환)"""
    if channel.startswith("C") and len(channel) > 8:
        return channel  # 이미 ID

    ch_name = channel.lstrip("#")
    try:
        result = client.conversations_list(types="public_channel", limit=200)
        for ch in result["channels"]:
            if ch["name"] == ch_name:
                return ch["id"]
    except Exception:
        pass

    return channel  # 못 찾으면 원본 반환 (채널명으로 직접 시도)


# ── Block Kit 메시지 빌더 ─────────────────────────────────────────────────

def _build_blocks(state: AgentState) -> List[dict]:
    """Slack Block Kit 메시지 구성"""
    pr = state.pr_data

    convention_icon = "✅" if (state.convention_result and state.convention_result.passed) else "❌"
    test_icon = "✅" if (state.test_result and state.test_result.passed) else "❌"

    risk = "unknown"
    risk_icon = "⚪"
    if state.impact_analysis:
        risk = state.impact_analysis.risk_level
        risk_icon = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}.get(risk, "⚪")

    test_stats = (
        f"{state.test_result.passed_tests}/{state.test_result.total_tests}"
        if state.test_result and state.test_result.total_tests > 0
        else "N/A"
    )

    blocks: List[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🤖 Smart PR Inspector 분석 완료"},
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*<{pr.pr_url}|PR #{pr.pr_number}: {pr.title}>*\n"
                    f"작성자: `{pr.author}` | `{pr.head_branch}` → `{pr.base_branch}`"
                ),
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"{convention_icon} *컨벤션*\n{'통과' if state.convention_result and state.convention_result.passed else '위반 발견'}"},
                {"type": "mrkdwn", "text": f"{test_icon} *테스트*\n{test_stats} 통과"},
                {"type": "mrkdwn", "text": f"{risk_icon} *리스크*\n{risk.upper()}"},
                {"type": "mrkdwn", "text": f"{'⚠️' if state.impact_analysis and state.impact_analysis.has_api_changes else '✅'} *API 변경*\n{'감지됨' if state.impact_analysis and state.impact_analysis.has_api_changes else '없음'}"},
            ],
        },
    ]

    if state.domain_explanation:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"📖 *비즈니스 영향도*\n{state.domain_explanation[:200]}",
            },
        })

    # PR Health Score 카드 (특색 기능)
    try:
        from agents.nodes.risk_report import calculate_pr_health_score, generate_health_card_slack
        health_score = calculate_pr_health_score(state)
        blocks.append(generate_health_card_slack(health_score))
    except Exception:
        pass

    blocks.append({"type": "divider"})

    # 인터랙티브 버튼 — value 형식: "repo|pr_number|pr_title"
    btn_value = f"{pr.repo}|{pr.pr_number}|{pr.title}"
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "✅ 승인"},
                "style": "primary",
                "action_id": "approve_pr",
                "value": btn_value,
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
                "value": btn_value,
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "📋 GitHub에서 보기"},
                "action_id": "view_pr",
                "url": pr.pr_url,
                "value": btn_value,
            },
        ],
    })

    return blocks
