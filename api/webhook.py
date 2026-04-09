"""
FastAPI Webhook 서버
GitHub PR 이벤트 수신 + SSE 스트리밍 + Slack Interactive Events
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
from typing import AsyncGenerator

from dotenv import load_dotenv
load_dotenv()  # 프로젝트 루트의 .env 자동 로드

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from prometheus_client import Counter, Histogram, generate_latest

from agents.orchestrator import run_pr_analysis, run_pr_analysis_stream
from agents.state import AgentState
from db.history import get_analysis_by_id, get_analysis_by_pr, list_analyses
from memory.cache import get_cache, set_cache

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Smart PR Inspector API",
    description="GitHub PR 자동 분석 에이전트 API",
    version="1.0.0",
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", os.getenv("FRONTEND_URL", "*")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus 메트릭
pr_analyzed_counter = Counter("pr_analyzed_total", "Total PRs analyzed")
analysis_duration = Histogram(
    "analysis_duration_seconds",
    "Time spent analyzing PR",
    buckets=[10, 30, 60, 120, 300],
)
webhook_received_counter = Counter(
    "webhook_received_total",
    "Total webhooks received",
    ["event_type"],
)


# ── GitHub Webhook ──────────────────────────────────────────────────────────

@app.post("/webhook/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """GitHub PR 이벤트 수신"""
    # 서명 검증
    body = await request.body()
    _verify_github_signature(request, body)

    payload = json.loads(body)
    event_type = request.headers.get("X-GitHub-Event", "unknown")
    webhook_received_counter.labels(event_type=event_type).inc()

    # PR 이벤트만 처리
    if event_type != "pull_request":
        return {"status": "ignored", "event": event_type}

    action = payload.get("action")
    if action not in ("opened", "synchronize", "reopened"):
        return {"status": "ignored", "action": action}

    pr_number = payload["pull_request"]["number"]
    repo = payload["repository"]["full_name"]

    # 중복 분석 방지 (캐시 확인)
    cache_key = f"analyzing:{repo}:{pr_number}"
    if await get_cache(cache_key):
        return {"status": "already_analyzing", "pr": pr_number}

    await set_cache(cache_key, "1", ttl=600)

    # 백그라운드에서 분석 실행
    background_tasks.add_task(_run_analysis_task, pr_number, repo)

    logger.info(f"PR #{pr_number} 분석 요청 수락 (repo: {repo})")
    return {"status": "accepted", "pr_number": pr_number, "repo": repo}


async def _run_analysis_task(pr_number: int, repo: str):
    """백그라운드 분석 실행"""
    with analysis_duration.time():
        try:
            state = await run_pr_analysis(pr_number, repo)
            pr_analyzed_counter.inc()

            # 결과 캐싱
            cache_key = f"result:{repo}:{pr_number}"
            await set_cache(cache_key, state.model_dump_json(), ttl=86400)

        except Exception as e:
            logger.error(f"PR #{pr_number} 분석 실패: {e}")
        finally:
            # 분석 중 플래그 해제
            await set_cache(f"analyzing:{repo}:{pr_number}", "", ttl=1)


# ── SSE 스트리밍 ──────────────────────────────────────────────────────────

@app.get("/api/analyze/stream")
async def analyze_stream(pr_number: int, repo: str):
    """PR 분석 결과를 SSE로 실시간 스트리밍"""

    async def event_generator() -> AsyncGenerator[str, None]:
        async for event in run_pr_analysis_stream(pr_number, repo):
            data = json.dumps(event, ensure_ascii=False)
            yield f"data: {data}\n\n"
            await asyncio.sleep(0)  # 이벤트 루프 양보

        yield "data: {\"type\": \"done\"}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── REST API ──────────────────────────────────────────────────────────────

@app.post("/api/analyze")
async def analyze_pr(pr_number: int, repo: str, background_tasks: BackgroundTasks):
    """PR 분석 수동 트리거"""
    cache_key = f"analyzing:{repo}:{pr_number}"
    if await get_cache(cache_key):
        raise HTTPException(status_code=409, detail="이미 분석 중입니다")

    await set_cache(cache_key, "1", ttl=600)
    background_tasks.add_task(_run_analysis_task, pr_number, repo)

    return {"status": "started", "pr_number": pr_number}


@app.get("/api/result/{repo:path}/{pr_number}")
async def get_result(repo: str, pr_number: int):
    """분석 결과 조회"""
    cache_key = f"result:{repo}:{pr_number}"
    cached = await get_cache(cache_key)

    if not cached:
        raise HTTPException(status_code=404, detail="분석 결과를 찾을 수 없습니다")

    return json.loads(cached)


@app.get("/api/status/{repo:path}/{pr_number}")
async def get_status(repo: str, pr_number: int):
    """분석 진행 상태 조회"""
    analyzing = await get_cache(f"analyzing:{repo}:{pr_number}")
    result = await get_cache(f"result:{repo}:{pr_number}")

    if analyzing:
        return {"status": "analyzing"}
    elif result:
        return {"status": "completed"}
    else:
        return {"status": "not_started"}


# ── Slack Interactive Events ──────────────────────────────────────────────

@app.post("/slack/events")
async def slack_events(request: Request):
    """Slack Interactive Events 처리"""
    try:
        from slack_bolt.adapter.fastapi import SlackRequestHandler
        from slack_bolt import App

        slack_app = App(
            token=os.getenv("SLACK_BOT_TOKEN"),
            signing_secret=os.getenv("SLACK_SIGNING_SECRET"),
        )

        @slack_app.action("approve_pr")
        def handle_approve(ack, body, client):
            ack()
            pr_number = int(body["actions"][0]["value"])
            repo = os.getenv("GITHUB_REPO", "")
            _github_approve(repo, pr_number)
            client.chat_update(
                channel=body["channel"]["id"],
                ts=body["message"]["ts"],
                text=f"✅ PR #{pr_number} Slack에서 승인 완료",
            )

        @slack_app.action("request_changes")
        def handle_request_changes(ack, body, client):
            ack()
            pr_number = int(body["actions"][0]["value"])
            client.chat_update(
                channel=body["channel"]["id"],
                ts=body["message"]["ts"],
                text=f"🔄 PR #{pr_number} 수정 요청됨",
            )

        handler = SlackRequestHandler(slack_app)
        return await handler.handle(request)

    except Exception as e:
        logger.error(f"Slack 이벤트 처리 실패: {e}")
        return Response(status_code=200)  # Slack은 항상 200 반환 필요


def _github_approve(repo: str, pr_number: int):
    """GitHub PR 승인"""
    from github import Github
    gh = Github(os.getenv("GITHUB_TOKEN"))
    github_repo = gh.get_repo(repo)
    pr = github_repo.get_pull(pr_number)
    pr.create_review(
        event="APPROVE",
        body="✅ Slack에서 Smart PR Inspector를 통해 승인되었습니다.",
    )


# ── 분석 이력 API ──────────────────────────────────────────────────────────

@app.get("/api/history")
async def get_history(limit: int = 50):
    """PR 분석 이력 목록 조회 (DB)"""
    try:
        records = await asyncio.to_thread(list_analyses, limit)
        return {"items": records, "total": len(records)}
    except Exception as e:
        logger.error(f"이력 조회 실패: {e}")
        return {"items": [], "total": 0}


@app.get("/api/history/{record_id}")
async def get_history_item(record_id: int):
    """특정 분석 이력 상세 조회"""
    record = await asyncio.to_thread(get_analysis_by_id, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="분석 이력을 찾을 수 없습니다")
    return record


@app.get("/api/history/pr/{repo:path}/{pr_number}")
async def get_history_by_pr(repo: str, pr_number: int):
    """레포+PR번호로 최신 분석 결과 조회"""
    record = await asyncio.to_thread(get_analysis_by_pr, repo, pr_number)
    if not record:
        raise HTTPException(status_code=404, detail="분석 이력을 찾을 수 없습니다")
    return record


# ── 모니터링 ──────────────────────────────────────────────────────────────

@app.get("/metrics")
async def metrics():
    """Prometheus 메트릭 엔드포인트"""
    return Response(generate_latest(), media_type="text/plain")


@app.get("/health")
async def health():
    """헬스체크"""
    return {"status": "healthy", "version": "1.0.0"}


# ── 서명 검증 ──────────────────────────────────────────────────────────────

def _verify_github_signature(request: Request, body: bytes):
    """GitHub Webhook 서명 검증"""
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    if not secret:
        return  # 개발 환경에서 스킵

    signature = request.headers.get("X-Hub-Signature-256", "")
    expected = "sha256=" + hmac.new(
        secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="서명 검증 실패")
