"""
AgentState 모델 테스트
"""

import pytest
from agents.state import (
    AgentState,
    PRData,
    ConventionResult,
    ConventionViolation,
    TestResult,
    ImpactAnalysis,
    NodeStatus,
)


class TestAgentState:
    def test_default_state(self):
        state = AgentState()
        assert state.pr_data is None
        assert state.convention_result is None
        assert state.node_status.fetch == NodeStatus.PENDING

    def test_pr_data_creation(self):
        pr = PRData(
            pr_number=123,
            repo="owner/repo",
            author="testuser",
            title="테스트 PR",
        )
        assert pr.pr_number == 123
        assert pr.repo == "owner/repo"
        assert pr.linked_issues == []

    def test_convention_result(self):
        violation = ConventionViolation(
            file="test.py",
            line=42,
            rule="snake_case",
            message="함수명을 snake_case로",
            severity="warning",
        )
        result = ConventionResult(
            passed=False,
            violations=[violation],
            summary="경고 1건",
        )
        assert result.passed is False
        assert len(result.violations) == 1

    def test_test_result(self):
        result = TestResult(
            passed=True,
            total_tests=5,
            passed_tests=5,
            failed_tests=0,
            duration_seconds=12.3,
        )
        assert result.passed is True
        assert result.total_tests == 5

    def test_impact_analysis(self):
        analysis = ImpactAnalysis(
            changed_functions=["calculate_discount"],
            affected_modules=[{"module": "order.py", "function": "create_order", "line": 42}],
            has_api_changes=True,
            risk_level="high",
        )
        assert analysis.risk_level == "high"
        assert analysis.has_api_changes is True

    def test_node_status_update(self):
        state = AgentState()
        state.node_status.fetch = NodeStatus.SUCCESS
        state.node_status.convention = NodeStatus.RUNNING

        assert state.node_status.fetch == NodeStatus.SUCCESS
        assert state.node_status.convention == NodeStatus.RUNNING
        assert state.node_status.test_gen == NodeStatus.PENDING

    def test_state_serialization(self):
        """JSON 직렬화/역직렬화 테스트"""
        state = AgentState(
            pr_data=PRData(
                pr_number=1,
                repo="test/repo",
                author="user",
                title="Test PR",
            )
        )

        json_str = state.model_dump_json()
        restored = AgentState.model_validate_json(json_str)

        assert restored.pr_data.pr_number == 1
        assert restored.pr_data.repo == "test/repo"
