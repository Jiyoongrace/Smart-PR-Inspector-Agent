"""
GitHub 클라이언트 팩토리

GitHub App 인증(우선)과 PAT 인증(폴백)을 지원합니다.
- GitHub App: 자신이 만든 PR도 승인 가능 (Bot으로 동작)
- PAT: 기존 방식 (자기 PR 승인 불가)

환경변수:
  GitHub App 인증:
    GITHUB_APP_ID            — GitHub App ID (앱 설정 페이지에서 확인)
    GITHUB_APP_PRIVATE_KEY   — PEM 형식 비밀키 (줄바꿈은 \\n 또는 실제 개행 모두 허용)
    GITHUB_APP_INSTALLATION_ID — 레포에 앱 설치 후 URL에서 확인

  PAT 인증 (폴백):
    GITHUB_TOKEN             — GitHub Personal Access Token
"""

import logging
import os

from github import Auth, Github

logger = logging.getLogger(__name__)


def get_github_client(timeout: int = 30) -> Github:
    """GitHub App 인증(우선) 또는 PAT 인증으로 Github 클라이언트 반환

    Args:
        timeout: HTTP 타임아웃(초)

    Returns:
        인증된 Github 클라이언트

    Raises:
        ValueError: 인증 정보가 전혀 설정되지 않은 경우
    """
    app_id = os.getenv("GITHUB_APP_ID", "").strip()
    raw_key = os.getenv("GITHUB_APP_PRIVATE_KEY", "")
    installation_id = os.getenv("GITHUB_APP_INSTALLATION_ID", "").strip()

    # GitHub App 인증 시도
    if app_id and raw_key and installation_id:
        try:
            # 환경변수에서 \n 이스케이프를 실제 개행으로 변환
            private_key = raw_key.replace("\\n", "\n")

            app_auth = Auth.AppAuth(int(app_id), private_key)
            auth = Auth.AppInstallationAuth(app_auth, int(installation_id))
            logger.debug("GitHub App 인증 사용 (App ID: %s)", app_id)
            return Github(auth=auth, timeout=timeout)
        except Exception as e:
            logger.warning("GitHub App 인증 실패, PAT 폴백: %s", e)

    # PAT 인증 폴백
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        raise ValueError(
            "GitHub 인증 정보가 없습니다. "
            "GITHUB_TOKEN 또는 "
            "GITHUB_APP_ID / GITHUB_APP_PRIVATE_KEY / GITHUB_APP_INSTALLATION_ID "
            "환경변수를 설정하세요."
        )

    logger.debug("GitHub PAT 인증 사용")
    return Github(token, timeout=timeout)
