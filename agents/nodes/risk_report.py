"""
PR 리스크 리포트 카드 생성 노드
분석 결과를 종합하여 한눈에 볼 수 있는 리스크 점수 + 요약 카드를 생성합니다.

특색 기능:
- 100점 만점 PR 건강도 점수 (PR Health Score)
- 컨벤션/테스트/영향도/도메인 4개 영역 각 25점
- 점수에 따른 머지 권장 여부 자동 판정
- GitHub 코멘트에 시각적 프로그레스 바로 표시
"""

import logging
from dataclasses import dataclass

from agents.state import AgentState

logger = logging.getLogger(__name__)


@dataclass
class PRHealthScore:
    """PR 건강도 점수"""
    convention_score: int = 0     # 0~25
    test_score: int = 0           # 0~25
    impact_score: int = 0         # 0~25
    domain_score: int = 0         # 0~25
    total_score: int = 0          # 0~100
    grade: str = "F"              # S, A, B, C, D, F
    merge_recommendation: str = ""
    summary: str = ""


def calculate_pr_health_score(state: AgentState) -> PRHealthScore:
    """
    PR 건강도 점수 계산

    4개 영역 각 25점 만점:
    - 컨벤션: 위반 0건=25, error 있으면 감점
    - 테스트: 통과율 기반
    - 영향도: 리스크 레벨 기반
    - 도메인: RAG 문서 활용 여부 + 설명 품질
    """
    score = PRHealthScore()

    # 1. 컨벤션 점수 (25점)
    if state.convention_result:
        if state.convention_result.passed:
            score.convention_score = 25
        else:
            errors = sum(1 for v in state.convention_result.violations if v.severity == "error")
            warnings = sum(1 for v in state.convention_result.violations if v.severity == "warning")
            score.convention_score = max(0, 25 - (errors * 8) - (warnings * 3))
    else:
        score.convention_score = 15  # 검증 안 됨

    # 2. 테스트 점수 (25점)
    if state.test_result and state.test_result.total_tests > 0:
        pass_rate = state.test_result.passed_tests / state.test_result.total_tests
        score.test_score = int(25 * pass_rate)
    else:
        score.test_score = 10  # 테스트 없음

    # 3. 영향도 점수 (25점 — 낮을수록 좋음)
    if state.impact_analysis:
        risk_scores = {"low": 25, "medium": 18, "high": 10, "critical": 3}
        score.impact_score = risk_scores.get(state.impact_analysis.risk_level, 15)
    else:
        score.impact_score = 20

    # 4. 도메인 점수 (25점 — RAG 활용 여부)
    if state.domain_explanation and state.domain_sources:
        score.domain_score = 25  # RAG 문서 기반 설명 생성됨
    elif state.domain_explanation:
        score.domain_score = 18  # 코드 추론만으로 설명
    else:
        score.domain_score = 8   # 설명 없음

    # 총점 계산
    score.total_score = (
        score.convention_score + score.test_score +
        score.impact_score + score.domain_score
    )

    # 등급 판정
    if score.total_score >= 90:
        score.grade = "S"
        score.merge_recommendation = "즉시 머지 가능"
    elif score.total_score >= 80:
        score.grade = "A"
        score.merge_recommendation = "머지 권장"
    elif score.total_score >= 65:
        score.grade = "B"
        score.merge_recommendation = "경미한 수정 후 머지"
    elif score.total_score >= 50:
        score.grade = "C"
        score.merge_recommendation = "수정 필요"
    elif score.total_score >= 30:
        score.grade = "D"
        score.merge_recommendation = "주요 수정 필요"
    else:
        score.grade = "F"
        score.merge_recommendation = "전면 재작업 권장"

    score.summary = (
        f"PR 건강도: {score.grade} ({score.total_score}/100) — "
        f"{score.merge_recommendation}"
    )

    logger.info(f"PR Health Score: {score.total_score}/100 ({score.grade})")
    return score


def generate_health_card_markdown(score: PRHealthScore) -> str:
    """GitHub 코멘트용 리스크 리포트 카드 마크다운 생성"""

    grade_emoji = {
        "S": "🏆", "A": "🟢", "B": "🔵",
        "C": "🟡", "D": "🟠", "F": "🔴",
    }
    emoji = grade_emoji.get(score.grade, "⚪")

    def progress_bar(value: int, max_val: int = 25) -> str:
        """텍스트 프로그레스 바 생성"""
        filled = int((value / max_val) * 10)
        empty = 10 - filled
        return f"{'█' * filled}{'░' * empty} {value}/{max_val}"

    card = f"""
### {emoji} PR Health Score: **{score.grade}** ({score.total_score}/100)

> {score.merge_recommendation}

| 영역 | 점수 | 상세 |
|------|------|------|
| 📋 컨벤션 | {progress_bar(score.convention_score)} | 코드 규칙 준수도 |
| 🧪 테스트 | {progress_bar(score.test_score)} | 시나리오 검증 통과율 |
| 🔗 영향도 | {progress_bar(score.impact_score)} | 변경 리스크 (높을수록 안전) |
| 📖 도메인 | {progress_bar(score.domain_score)} | RAG 문서 기반 분석 품질 |

"""
    return card.strip()


def generate_health_card_slack(score: PRHealthScore) -> dict:
    """Slack Block Kit용 리스크 리포트 카드"""
    grade_emoji = {
        "S": "🏆", "A": "🟢", "B": "🔵",
        "C": "🟡", "D": "🟠", "F": "🔴",
    }
    emoji = grade_emoji.get(score.grade, "⚪")

    return {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": (
                f"{emoji} *PR Health Score: {score.grade} ({score.total_score}/100)*\n"
                f"_{score.merge_recommendation}_\n\n"
                f"📋 컨벤션: {score.convention_score}/25 | "
                f"🧪 테스트: {score.test_score}/25 | "
                f"🔗 영향도: {score.impact_score}/25 | "
                f"📖 도메인: {score.domain_score}/25"
            ),
        },
    }
