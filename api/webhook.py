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
from pydantic import BaseModel

from agents.orchestrator import run_pr_analysis, run_pr_analysis_stream
from agents.state import AgentState
from config.github_app import get_github_client
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


# ── Slack Bolt App 싱글턴 ────────────────────────────────────────────────
# 매 요청마다 App을 재생성하면 핸들러 등록이 불안정해지므로,
# 앱 레벨에서 한 번만 초기화하고 재사용한다.

_slack_bolt_handler = None


def _get_slack_handler():
    """Slack Bolt App 싱글턴 반환 (lazy 초기화)"""
    global _slack_bolt_handler
    if _slack_bolt_handler is not None:
        return _slack_bolt_handler

    from slack_bolt import App
    from slack_bolt.adapter.fastapi import SlackRequestHandler

    slack_app = App(
        token=os.getenv("SLACK_BOT_TOKEN"),
        signing_secret=os.getenv("SLACK_SIGNING_SECRET"),
    )

    @slack_app.action("approve_pr")
    def handle_approve(ack, body, client):
        ack()
        repo, pr_number = _parse_button_value(body["actions"][0]["value"])
        try:
            _github_approve(repo, pr_number)
            result_text = f"✅ PR #{pr_number} Slack에서 승인 완료"
        except Exception as e:
            logger.error(f"GitHub 승인 실패: {e}")
            result_text = f"❌ PR #{pr_number} 승인 실패: {e}"
        client.chat_update(
            channel=body["channel"]["id"],
            ts=body["message"]["ts"],
            text=result_text,
            blocks=[],  # 버튼 블록 제거 (완료 상태)
        )

    @slack_app.action("request_changes")
    def handle_request_changes(ack, body, client):
        ack()
        repo, pr_number = _parse_button_value(body["actions"][0]["value"])
        try:
            _github_request_changes(repo, pr_number)
            result_text = f"🔄 PR #{pr_number} GitHub에 수정 요청 완료"
        except Exception as e:
            logger.error(f"GitHub 수정 요청 실패: {e}")
            result_text = f"❌ PR #{pr_number} 수정 요청 실패: {e}"
        client.chat_update(
            channel=body["channel"]["id"],
            ts=body["message"]["ts"],
            text=result_text,
            blocks=[],  # 버튼 블록 제거 (완료 상태)
        )

    @slack_app.action("view_pr")
    def handle_view_pr(ack):
        # URL 버튼 클릭 시 ack만 처리 (브라우저에서 URL로 이동)
        ack()

    _slack_bolt_handler = SlackRequestHandler(slack_app)
    return _slack_bolt_handler


def _parse_button_value(value: str) -> tuple[str, int]:
    """버튼 value에서 (repo, pr_number) 파싱
    형식: "owner/repo|pr_number"
    """
    if "|" in value:
        repo, pr_num = value.split("|", 1)
        return repo, int(pr_num)
    # 구버전 호환: pr_number만 있는 경우
    return os.getenv("GITHUB_REPO", ""), int(value)


# ── Slack Interactive Events ──────────────────────────────────────────────

async def _handle_slack_request(request: Request):
    """Slack Bolt 핸들러 공통 처리"""
    bot_token = os.getenv("SLACK_BOT_TOKEN")
    signing_secret = os.getenv("SLACK_SIGNING_SECRET")

    if not bot_token or not signing_secret:
        logger.warning("SLACK_BOT_TOKEN / SLACK_SIGNING_SECRET 미설정 — Slack 비활성화")
        return Response(status_code=200)

    try:
        handler = _get_slack_handler()
        return await handler.handle(request)
    except Exception as e:
        logger.error(f"Slack 요청 처리 실패: {e}")
        return Response(status_code=200)  # Slack은 항상 200 반환 필요


@app.post("/slack/events")
async def slack_events(request: Request):
    """Slack Event Subscriptions URL (event_callback 처리)"""
    return await _handle_slack_request(request)


@app.post("/slack/interactions")
async def slack_interactions(request: Request):
    """Slack Interactivity Request URL (버튼 클릭 등 Interactive Components 처리)

    Slack 앱 설정 > Interactivity & Shortcuts > Request URL 에 이 경로를 등록해야 합니다.
    예: https://<your-domain>/slack/interactions
    """
    return await _handle_slack_request(request)


def _github_approve(repo: str, pr_number: int) -> None:
    """GitHub PR Approve Review 제출"""
    gh = get_github_client()
    github_repo = gh.get_repo(repo)
    pr = github_repo.get_pull(pr_number)
    pr.create_review(
        event="APPROVE",
        body="✅ Slack에서 Smart PR Inspector를 통해 승인되었습니다.",
    )


def _github_request_changes(repo: str, pr_number: int) -> None:
    """GitHub PR REQUEST_CHANGES Review 제출"""
    gh = get_github_client()
    github_repo = gh.get_repo(repo)
    pr = github_repo.get_pull(pr_number)
    pr.create_review(
        event="REQUEST_CHANGES",
        body="🔄 Slack에서 Smart PR Inspector를 통해 수정 요청되었습니다.",
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


# ── PR 자동 생성 ─────────────────────────────────────────────────────────

class CreatePRRequest(BaseModel):
    """PR 생성 요청 모델"""
    repo: str
    head: str
    base: str = "main"
    draft: bool = False


async def _generate_pr_content(
    repo: str,
    head: str,
    base: str,
    commits: list,
    commit_messages: str,
) -> tuple[str, str]:
    """Claude로 PR 제목/본문 생성, 실패 시 커밋 기반 폴백"""
    try:
        from config.llm import call_llm
        from config.prompts import PR_CREATION_PROMPT

        prompt = PR_CREATION_PROMPT.substitute(
            repo=repo,
            head=head,
            base=base,
            commit_count=len(commits),
            commits=commit_messages,
        )
        generated = call_llm(prompt, max_tokens=1024)

        # TITLE: / BODY: 파싱
        title = ""
        body_lines: list[str] = []
        in_body = False
        for line in generated.split("\n"):
            if line.startswith("TITLE:"):
                title = line.replace("TITLE:", "").strip()
            elif line.startswith("BODY:"):
                in_body = True
            elif in_body:
                body_lines.append(line)

        if not title:
            title = generated.split("\n")[0].strip() or f"{head} → {base}"
        body = "\n".join(body_lines).strip() if body_lines else generated
        return title, body

    except Exception as e:
        # Claude 실패 시 커밋 메시지 기반으로 자동 생성
        logger.warning(f"Claude PR 생성 실패, 폴백 사용: {e}")
        first_msg = commits[0].commit.message.split("\n")[0][:70] if commits else f"{head} → {base}"
        title = first_msg
        body = f"## 변경 사항\n\n{commit_messages}\n\n## 체크리스트\n- [ ] 코드 리뷰 완료\n- [ ] 테스트 통과 확인"
        return title, body


@app.post("/api/create-pr")
async def create_pull_request(req: CreatePRRequest):
    """커밋 목록을 Claude로 요약하여 GitHub PR 자동 생성"""
    try:
        from github import GithubException

        gh = get_github_client()
        try:
            github_repo = gh.get_repo(req.repo)
        except GithubException as e:
            raise HTTPException(status_code=404, detail=f"레포지토리를 찾을 수 없습니다: {req.repo}")

        # base와 head 사이의 커밋 수집
        try:
            comparison = github_repo.compare(req.base, req.head)
            commits = list(comparison.commits)
        except GithubException as e:
            raise HTTPException(status_code=400, detail=f"브랜치 비교 실패: {str(e)}")

        if not commits:
            raise HTTPException(status_code=400, detail="두 브랜치 사이에 새로운 커밋이 없습니다")

        # 커밋 메시지 정리 (첫 줄만, 최대 50개)
        commit_messages = "\n".join([
            f"- {c.commit.message.split(chr(10))[0][:100]} ({c.sha[:7]})"
            for c in commits[:50]
        ])

        # Claude로 PR 제목 + 본문 생성 (실패 시 커밋 기반 폴백)
        title, body = await _generate_pr_content(
            repo=req.repo,
            head=req.head,
            base=req.base,
            commits=commits,
            commit_messages=commit_messages,
        )

        # GitHub PR 생성
        try:
            pr = github_repo.create_pull(
                title=title,
                body=body,
                head=req.head,
                base=req.base,
                draft=req.draft,
            )
        except GithubException as e:
            detail = e.data.get("message", str(e)) if isinstance(e.data, dict) else str(e)
            raise HTTPException(status_code=422, detail=f"PR 생성 실패: {detail}")

        logger.info(f"PR #{pr.number} 생성 완료: {req.repo} ({req.head} → {req.base})")

        return {
            "pr_number": pr.number,
            "pr_url": pr.html_url,
            "title": pr.title,
            "body": pr.body,
            "head": req.head,
            "base": req.base,
            "draft": req.draft,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PR 생성 중 예기치 않은 오류: {e}")
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")


# ── PR 승인 / 머지 ────────────────────────────────────────────────────────

@app.post("/api/approve-pr")
async def approve_pull_request(repo: str, pr_number: int, comment: str = ""):
    """GitHub PR 승인 (Approve Review 제출)"""
    try:
        gh = get_github_client()
        github_repo = gh.get_repo(repo)
        pr = github_repo.get_pull(pr_number)
        body = comment or "✅ Smart PR Inspector를 통해 승인되었습니다."
        pr.create_review(event="APPROVE", body=body)
        logger.info(f"PR #{pr_number} 승인 완료 (repo: {repo})")
        return {"status": "approved", "pr_number": pr_number}
    except Exception as e:
        err_str = str(e)
        logger.error(f"PR 승인 실패: {err_str}")
        # GitHub 정책: 자신이 작성한 PR은 자신이 승인 불가
        if "Review Can not approve your own pull request" in err_str or "approve your own pull request" in err_str:
            raise HTTPException(
                status_code=422,
                detail="자신이 작성한 PR은 직접 승인할 수 없습니다 (GitHub 정책). 다른 팀원에게 리뷰를 요청하세요.",
            )
        raise HTTPException(status_code=500, detail=f"PR 승인 실패: {err_str}")


@app.post("/api/merge-pr")
async def merge_pull_request(
    repo: str,
    pr_number: int,
    merge_method: str = "squash",
    commit_message: str = "",
):
    """GitHub PR 머지"""
    try:
        from github import GithubException
        gh = get_github_client()
        github_repo = gh.get_repo(repo)
        pr = github_repo.get_pull(pr_number)

        if not pr.mergeable:
            raise HTTPException(status_code=409, detail="PR을 머지할 수 없습니다 (충돌 또는 필수 체크 미통과)")

        merge_msg = commit_message or f"Merge PR #{pr_number}: {pr.title}"
        result = pr.merge(
            commit_message=merge_msg,
            merge_method=merge_method,  # merge | squash | rebase
        )
        logger.info(f"PR #{pr_number} 머지 완료 (repo: {repo}, SHA: {result.sha})")
        return {"status": "merged", "pr_number": pr_number, "sha": result.sha, "message": result.message}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PR 머지 실패: {e}")
        raise HTTPException(status_code=500, detail=f"PR 머지 실패: {str(e)}")


# ── 모니터링 ──────────────────────────────────────────────────────────────

@app.get("/metrics")
async def metrics():
    """Prometheus 메트릭 엔드포인트"""
    return Response(generate_latest(), media_type="text/plain")


# ── RAG 검색 API ─────────────────────────────────────────────────────────────

@app.get("/api/rag/search")
async def rag_search(query: str, n_results: int = 3):
    """도메인 문서 벡터 검색 (채팅/외부 연동용)"""
    try:
        from agents.nodes.domain_explainer import _search_domain_docs
        docs, sources = _search_domain_docs(query)
        return {
            "documents": docs,
            "sources": sources,
            "count": len(docs),
            "rag_used": len(docs) > 0,
        }
    except Exception as e:
        logger.warning(f"RAG 검색 실패: {e}")
        return {"documents": [], "sources": [], "count": 0, "rag_used": False}


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
