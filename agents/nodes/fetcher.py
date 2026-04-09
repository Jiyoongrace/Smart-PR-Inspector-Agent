"""
GitHub PR 데이터 수집 노드
PyGithub + unidiff 활용
"""

import logging
import os
import re
import socket
from datetime import datetime, timezone

from github import Github, GithubException

from agents.state import AgentState, NodeStatus, PRData

logger = logging.getLogger(__name__)


def fetch_pr_data_node(state: AgentState) -> AgentState:
    """GitHub에서 PR 전체 데이터를 수집하는 노드"""
    state.node_status.fetch = NodeStatus.RUNNING
    logger.info(f"PR #{state.pr_data.pr_number} 데이터 수집 시작")

    # GITHUB_TOKEN 미설정 조기 검증
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        state.node_status.fetch = NodeStatus.FAILED
        state.error_message = "GITHUB_TOKEN 환경변수가 설정되지 않았습니다. .env 파일을 확인하세요."
        logger.error(state.error_message)
        return state

    try:
        # timeout=10: 연결 10초, 읽기 30초 — 무한 대기 방지
        gh = Github(github_token, timeout=10)
        repo_name = state.pr_data.repo
        pr_number = state.pr_data.pr_number

        repo = gh.get_repo(repo_name)
        pr = repo.get_pull(pr_number)

        # PR에서 변경된 파일 및 Diff 수집
        files = list(pr.get_files())
        diff_parts = []

        for f in files:
            if f.patch:
                diff_parts.append(f"--- a/{f.filename}\n+++ b/{f.filename}\n{f.patch}")

        diff_text = "\n".join(diff_parts)

        # "Fix #123", "Closes #456" 패턴에서 이슈 번호 추출
        body_text = pr.body or ""
        issue_pattern = r"(?:fix|fixes|fixed|close|closes|closed|resolve|resolves|resolved)\s+#(\d+)"
        linked_issues = [
            int(m.group(1))
            for m in re.finditer(issue_pattern, body_text, re.IGNORECASE)
        ]

        # 라벨 추출
        labels = [label.name for label in pr.labels]

        state.pr_data = PRData(
            pr_number=pr.number,
            repo=repo.full_name,
            author=pr.user.login,
            title=pr.title,
            body=body_text,
            diff=diff_text,
            changed_files=[f.filename for f in files],
            base_branch=pr.base.ref,
            head_branch=pr.head.ref,
            pr_url=pr.html_url,
            labels=labels,
            linked_issues=linked_issues,
        )

        state.started_at = datetime.now(tz=timezone.utc).isoformat()
        state.node_status.fetch = NodeStatus.SUCCESS
        logger.info(
            f"PR #{pr_number} 수집 완료: "
            f"{len(files)}개 파일, diff {len(diff_text)}자"
        )

    except GithubException as e:
        state.node_status.fetch = NodeStatus.FAILED
        state.error_message = f"GitHub API 오류: {e.status} - {e.data}"
        logger.error(state.error_message)

    except (socket.gaierror, ConnectionError, OSError) as e:
        state.node_status.fetch = NodeStatus.FAILED
        state.error_message = (
            f"GitHub 네트워크 연결 오류: {e}\n"
            "인터넷 연결 또는 DNS 설정을 확인하세요. "
            "VPN/프록시 환경에서는 'api.github.com' 접속이 가능한지 확인하세요."
        )
        logger.error(state.error_message)

    except Exception as e:
        state.node_status.fetch = NodeStatus.FAILED
        state.error_message = f"PR 데이터 수집 실패: {type(e).__name__}: {e}"
        logger.error(state.error_message, exc_info=True)

    return state
