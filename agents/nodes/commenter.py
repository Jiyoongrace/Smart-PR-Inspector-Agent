"""
GitHub PR 코멘트 생성 노드
전체 분석 결과를 구조화된 Markdown 리포트로 작성
"""

import logging

from agents.state import AgentState, NodeStatus
from config.github_app import get_github_client

logger = logging.getLogger(__name__)


def generate_comment_node(state: AgentState) -> AgentState:
    """분석 결과를 GitHub PR 코멘트로 작성"""
    state.node_status.comment = NodeStatus.RUNNING

    if not state.pr_data:
        state.node_status.comment = NodeStatus.SKIPPED
        return state

    # 마크다운 리포트 생성
    comment_body = _build_comment(state)
    state.final_comment = comment_body

    # GitHub에 코멘트 게시
    try:
        comment_id = _post_github_comment(
            repo=state.pr_data.repo,
            pr_number=state.pr_data.pr_number,
            body=comment_body,
        )
        state.github_comment_id = comment_id
        logger.info(f"GitHub 코멘트 게시 완료 (ID: {comment_id})")
    except Exception as e:
        logger.error(f"GitHub 코멘트 게시 실패: {e}")

    state.node_status.comment = NodeStatus.SUCCESS
    return state


def _build_comment(state: AgentState) -> str:
    """전체 분석 결과를 Markdown으로 조합"""
    lines = []

    # 헤더
    lines.append("## 🤖 Smart PR Inspector 분석 결과")
    lines.append("")
    lines.append(f"> PR: **{state.pr_data.title}**  |  작성자: `{state.pr_data.author}`")
    lines.append("")

    # 전체 요약 배지
    lines.append(_build_summary_badges(state))
    lines.append("")
    lines.append("---")
    lines.append("")

    # 1. 컨벤션 검증
    lines.append(_build_convention_section(state))
    lines.append("")

    # 2. 테스트 결과
    lines.append(_build_test_section(state))
    lines.append("")

    # 3. 영향도 분석
    lines.append(_build_impact_section(state))
    lines.append("")

    # 4. 도메인 설명
    if state.domain_explanation:
        lines.append(_build_domain_section(state))
        lines.append("")

    # 5. 문서 동기화
    if state.doc_updates:
        lines.append(state.doc_updates)
        lines.append("")

    # 6. 개발자 맞춤 제안
    if state.author_history:
        lines.append(_build_personalized_section(state))
        lines.append("")

    # 푸터
    lines.append("---")
    lines.append("*⚡ Powered by [Smart PR Inspector](https://github.com) | Claude AI*")

    return "\n".join(lines)


def _build_summary_badges(state: AgentState) -> str:
    """요약 배지 생성"""
    parts = []

    # 컨벤션
    if state.convention_result:
        icon = "✅" if state.convention_result.passed else "❌"
        parts.append(f"{icon} **컨벤션**: {'통과' if state.convention_result.passed else '실패'}")

    # 테스트
    if state.test_result:
        icon = "✅" if state.test_result.passed else "❌"
        test_info = f"{state.test_result.passed_tests}/{state.test_result.total_tests}"
        parts.append(f"{icon} **테스트**: {test_info} 통과")

    # 영향도
    if state.impact_analysis:
        risk_icons = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}
        risk = state.impact_analysis.risk_level
        icon = risk_icons.get(risk, "⚪")
        parts.append(f"{icon} **리스크**: {risk.upper()}")

    # API 변경
    if state.impact_analysis and state.impact_analysis.has_api_changes:
        parts.append("⚠️ **API 변경 감지**")

    return " &nbsp;|&nbsp; ".join(parts)


def _build_convention_section(state: AgentState) -> str:
    if not state.convention_result:
        return "### 📋 컨벤션 검증\n\n> 분석 결과 없음"

    result = state.convention_result
    status = "✅ 통과" if result.passed else f"❌ 위반 {len(result.violations)}건"

    lines = [f"### 📋 컨벤션 검증 — {status}", ""]

    if result.violations:
        lines.append(f"총 {len(result.violations)}건의 위반이 발견되었습니다.")
        lines.append("")

        # 심각도별 그룹화
        errors = [v for v in result.violations if v.severity == "error"]
        warnings = [v for v in result.violations if v.severity == "warning"]
        infos = [v for v in result.violations if v.severity == "info"]

        for severity, items, icon in [
            ("오류", errors, "🔴"),
            ("경고", warnings, "🟡"),
            ("정보", infos, "🔵"),
        ]:
            if items:
                lines.append(f"<details><summary>{icon} {severity} ({len(items)}건)</summary>")
                lines.append("")
                for v in items[:10]:  # 최대 10개 표시
                    lines.append(f"- **{v.file}:{v.line}** `{v.rule}` — {v.message}")
                    if v.suggestion:
                        lines.append(f"  - 💡 제안: {v.suggestion}")
                if len(items) > 10:
                    lines.append(f"- *...외 {len(items) - 10}건 더*")
                lines.append("")
                lines.append("</details>")
    else:
        lines.append("모든 컨벤션 규칙을 준수하고 있습니다. 👍")

    return "\n".join(lines)


def _build_test_section(state: AgentState) -> str:
    if not state.test_result:
        return "### 🧪 시나리오 검증\n\n> 검증 대상 없음"

    result = state.test_result
    status = "✅ 통과" if result.passed else "❌ 검토 필요"
    lines = [f"### 🧪 시나리오 검증 — {status}", ""]

    # AI 시나리오 모드
    if result.verification_mode == "ai_scenario" and result.scenarios:
        passed = sum(1 for s in result.scenarios if s.verdict == "pass")
        failed = sum(1 for s in result.scenarios if s.verdict == "fail")
        unclear = sum(1 for s in result.scenarios if s.verdict == "unclear")

        lines.append(f"총 {len(result.scenarios)}개 시나리오 중 **{passed}개 구현 확인**, {failed}개 미구현, {unclear}개 판단불가")
        lines.append("")

        verdict_icons = {"pass": "✅", "fail": "❌", "unclear": "⚠️"}

        for sr in result.scenarios:
            icon = verdict_icons.get(sr.verdict, "⚪")
            lines.append(f"<details><summary>{icon} {sr.scenario.title} [{sr.scenario.category}]</summary>")
            lines.append("")
            lines.append(f"- **전제 조건**: {sr.scenario.given}")
            lines.append(f"- **동작**: {sr.scenario.when}")
            lines.append(f"- **기대 결과**: {sr.scenario.then}")
            lines.append("")
            lines.append(f"**검증 결과**: {sr.reasoning}")
            if sr.confidence > 0:
                lines.append(f"*(확신도 {sr.confidence}%)*")
            lines.append("")
            lines.append("</details>")
    else:
        # 레거시: 코드 실행 방식
        if result.total_tests > 0:
            lines.append(f"- 총 {result.total_tests}개 중 {result.passed_tests}개 통과")
        if not result.passed and result.stderr:
            lines.append("")
            lines.append("<details><summary>오류 로그</summary>")
            lines.append("")
            lines.append(f"```\n{result.stderr[:500]}\n```")
            lines.append("")
            lines.append("</details>")

    return "\n".join(lines)


def _build_impact_section(state: AgentState) -> str:
    if not state.impact_analysis:
        return "### 🔗 영향도 분석\n\n> 분석 결과 없음"

    analysis = state.impact_analysis
    risk_labels = {"low": "낮음", "medium": "보통", "high": "높음", "critical": "위험"}
    risk_icons = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}

    risk = analysis.risk_level
    lines = [
        f"### 🔗 영향도 분석 — {risk_icons.get(risk, '⚪')} 리스크 {risk_labels.get(risk, risk)}",
        "",
    ]

    if analysis.changed_functions:
        lines.append(f"**변경된 함수**: `{'`, `'.join(analysis.changed_functions[:5])}`")
        lines.append("")

    if analysis.affected_modules:
        lines.append(f"**영향받는 모듈** ({len(analysis.affected_modules)}개):")
        lines.append("")
        for mod in analysis.affected_modules[:5]:
            lines.append(f"- `{mod['module']}` → `{mod['function']}()` (line {mod['line']})")
        if len(analysis.affected_modules) > 5:
            lines.append(f"- *...외 {len(analysis.affected_modules) - 5}개*")
    else:
        lines.append("영향받는 외부 모듈 없음")

    if analysis.has_api_changes:
        lines.append("")
        lines.append("⚠️ **API 엔드포인트 변경이 감지되었습니다.** Swagger 문서 업데이트를 확인하세요.")

    return "\n".join(lines)


def _build_domain_section(state: AgentState) -> str:
    lines = ["### 📖 비즈니스 영향도", ""]
    lines.append(state.domain_explanation)

    if state.domain_sources:
        lines.append("")
        lines.append("**참고 문서:**")
        for src in state.domain_sources[:3]:
            lines.append(f"- {src}")

    return "\n".join(lines)


def _build_personalized_section(state: AgentState) -> str:
    history = state.author_history
    if not history:
        return ""

    lines = ["### 💡 맞춤 제안 (과거 리뷰 기반)", ""]
    if "common_violations" in history:
        for v in history["common_violations"][:3]:
            lines.append(f"- 과거 PR에서 `{v['rule']}`이 반복 발견되었습니다 — 이번에도 확인해보세요")

    return "\n".join(lines)


def _post_github_comment(repo: str, pr_number: int, body: str) -> int:
    """GitHub API로 PR 코멘트 게시"""
    gh = get_github_client()
    github_repo = gh.get_repo(repo)
    pr = github_repo.get_pull(pr_number)
    comment = pr.create_issue_comment(body)
    return comment.id
